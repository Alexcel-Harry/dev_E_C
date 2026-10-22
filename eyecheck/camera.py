"""Bounded latest-frame capture with optional Qt preview and local landmarks."""
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import threading
import time

from .common import stats, write_report
from .features import extract


class LatestCapture:
    def __init__(self, cv2, args):
        self.cv2, self.args = cv2, args
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.latest = None
        self.error = None
        self.actual = None
        self.count = 0
        self.duplicates = 0
        self.intervals = []
        self.started = None
        self.finished = None
        self.thread = threading.Thread(target=self.run, daemon=True)

    def run(self):
        cap = None
        try:
            cap = self.cv2.VideoCapture(self.args.device, self.cv2.CAP_V4L2)
            if not cap.isOpened():
                raise RuntimeError("Cannot open camera; check node, permission, shutter, and contention")
            if self.args.fourcc:
                cap.set(self.cv2.CAP_PROP_FOURCC, self.cv2.VideoWriter_fourcc(*self.args.fourcc))
            cap.set(self.cv2.CAP_PROP_FRAME_WIDTH, self.args.width)
            cap.set(self.cv2.CAP_PROP_FRAME_HEIGHT, self.args.height)
            cap.set(self.cv2.CAP_PROP_FPS, self.args.fps)
            cap.set(self.cv2.CAP_PROP_BUFFERSIZE, 1)
            code = int(cap.get(self.cv2.CAP_PROP_FOURCC))
            self.actual = {"width": cap.get(self.cv2.CAP_PROP_FRAME_WIDTH),
                           "height": cap.get(self.cv2.CAP_PROP_FRAME_HEIGHT),
                           "driver_fps": cap.get(self.cv2.CAP_PROP_FPS),
                           "fourcc": ''.join(chr((code >> (8 * i)) & 255) for i in range(4))}
            # Discard warmup frames; measured period starts afterwards.
            warm_end = time.monotonic() + self.args.warmup
            previous_hash = previous_time = None
            while not self.stop.is_set():
                ok, frame = cap.read()
                now = time.monotonic()
                if not ok or frame is None or frame.size == 0:
                    raise RuntimeError("Camera read failed; run stopped without reconnecting")
                if now < warm_end:
                    continue
                if self.started is None:
                    self.started = now
                if now - self.started >= self.args.seconds:
                    break
                digest = hashlib.blake2b(frame.tobytes(), digest_size=8).digest()
                with self.lock:
                    self.count += 1
                    if previous_time is not None:
                        self.intervals.append((now - previous_time) * 1000)
                    if digest == previous_hash:
                        self.duplicates += 1
                    else:
                        self.latest = (self.count, now, frame)
                previous_hash, previous_time = digest, now
            self.finished = time.monotonic()
        except Exception as exc:
            self.error = str(exc)
        finally:
            if cap is not None:
                cap.release()


def run(args):
    import cv2
    capture = LatestCapture(cv2, args)
    detector = mp = None
    model_hash = None
    if args.model:
        import mediapipe as mp
        from mediapipe.tasks import python
        from mediapipe.tasks.python import vision
        model_hash = hashlib.sha256(Path(args.model).read_bytes()).hexdigest()
        detector = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(
            base_options=python.BaseOptions(model_asset_path=args.model),
            running_mode=vision.RunningMode.VIDEO, num_faces=1))
    app = label = info = None
    if args.preview:
        from PySide6.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout
        from PySide6.QtGui import QImage, QPixmap
        app = QApplication([])
        window = QWidget()
        window.setWindowTitle("Eyecheck — diagnostics only — close to stop")
        layout = QVBoxLayout(window)
        label, info = QLabel(), QLabel("Opening camera; no images are saved")
        layout.addWidget(label)
        layout.addWidget(info)
        window.show()
    reasons = Counter()
    measures = defaultdict(list)
    processed = geometry = 0
    last_id = 0
    last_timestamp = -1
    last_valid = None
    actual_shape = None
    early_stop = False
    start = time.monotonic()
    cpu_start = time.process_time()
    capture.thread.start()
    try:
        while True:
            if app:
                app.processEvents()
                if not window.isVisible():
                    early_stop = True
                    break
            now = time.monotonic()
            if capture.error:
                break
            if not capture.thread.is_alive():
                break
            with capture.lock:
                latest = capture.latest
            if latest is None or latest[0] == last_id:
                if now - (latest[1] if latest else start) > max(5, args.warmup + 5 if latest is None else 5):
                    capture.error = "No fresh frame for five seconds (after startup allowance)"
                    break
                time.sleep(.005)
                continue
            frame_id, captured, frame = latest
            last_id = frame_id
            age = (now - captured) * 1000
            if age > 250:
                reasons["stale_over_250ms"] += 1
                continue
            processed += 1
            actual_shape = [frame.shape[1], frame.shape[0]]
            eyes = None
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            if detector:
                timestamp = max(last_timestamp + 1, int(captured * 1000))
                last_timestamp = timestamp
                inference_start = time.monotonic()
                result = detector.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), timestamp)
                measures["inference_ms"].append((time.monotonic() - inference_start) * 1000)
                if not result.face_landmarks:
                    reasons["no_face"] += 1
                else:
                    try:
                        eyes = extract(result.face_landmarks[0], *actual_shape)
                        geometry += 1
                        if last_valid is not None:
                            measures["geometry_gap_ms"].append((captured - last_valid) * 1000)
                        last_valid = captured
                        for name, eye in eyes.items():
                            for metric in ("width_px", "openness", "iris_x", "iris_y"):
                                measures[f"{name}_{metric}"].append(eye[metric])
                    except ValueError as exc:
                        reasons[str(exc)] += 1
            measures["dequeue_to_result_ms"].append((time.monotonic() - captured) * 1000)
            if app:
                # A temporary composite includes enlarged eye crops, never written to disk.
                import numpy as np
                preview = cv2.resize(rgb, (800, max(1, round(rgb.shape[0] * 800 / rgb.shape[1]))))
                if eyes:
                    crops = []
                    for eye in eyes.values():
                        pts = eye["points"]
                        margin = max(5, int(eye["width_px"] * .3))
                        x0 = max(0, int(min(p[0] for p in pts)) - margin)
                        x1 = min(rgb.shape[1], int(max(p[0] for p in pts)) + margin + 1)
                        y0 = max(0, int(min(p[1] for p in pts)) - margin)
                        y1 = min(rgb.shape[0], int(max(p[1] for p in pts)) + margin + 1)
                        crop = rgb[y0:y1, x0:x1].copy()
                        for x, y in pts:
                            cv2.circle(crop, (round(x - x0), round(y - y0)), 1, (0, 255, 0), -1)
                        crops.append(cv2.resize(crop, (400, 180)))
                    preview = np.vstack((preview, np.hstack(crops)))
                preview = np.ascontiguousarray(preview)
                q = QImage(preview.data, preview.shape[1], preview.shape[0], preview.strides[0], QImage.Format_RGB888).copy()
                label.setPixmap(QPixmap.fromImage(q))
                info.setText(f"Frames processed {processed} | geometry {geometry} | no pointer input | unmirrored")
    except KeyboardInterrupt:
        early_stop = True
    finally:
        capture.stop.set()
        capture.thread.join(timeout=2)
        if detector:
            detector.close()
        if app:
            window.close()
    elapsed = max(.001, time.monotonic() - (capture.started or start))
    report = {"schema": 1, "kind": "camera", "status": "error" if capture.error or capture.thread.is_alive() else
              "incomplete" if early_stop else "recorded", "error": capture.error,
              "capture_thread_stuck": capture.thread.is_alive(), "label": args.label,
              "requested": {"width": args.width, "height": args.height, "fps": args.fps, "fourcc": args.fourcc},
              "driver_reported": capture.actual, "frame_dimensions": actual_shape,
              "requested_seconds": args.seconds, "measured_seconds": elapsed,
              "capture_reads": capture.count, "identical_consecutive_frames": capture.duplicates,
              "capture_read_fps": max(0, capture.count - 1) / elapsed,
              "processed_frames": processed, "processed_fps": processed / elapsed,
              "geometry_frames": geometry if detector else None,
              "geometry_fraction": geometry / processed if detector and processed else None,
              "geometry_fps": geometry / elapsed if detector else None,
              "cpu_one_core_percent_including_startup": 100 * (time.process_time() - cpu_start) / max(.001, time.monotonic() - start),
              "read_gap_ms": stats(capture.intervals), "reasons": dict(reasons),
              "metrics": {k: stats(v) for k, v in measures.items()}, "model_sha256": model_hash,
              "feature_schema": "mediapipe478-eye-diagnostic-v1", "preview": args.preview,
              "limits": ["Geometry validity does not establish visible pupils, reliable blinks, or usable gaze.",
                         "No automatic closure exclusion; baseline throughput includes natural blinks.",
                         "Software timing begins at read completion, not camera exposure or eye movement.",
                         "Exact pixel duplicates are excluded from processing; freshness is not sensor-timestamp verified.",
                         "Single latest frame slot intentionally skips frames when inference is slower than capture."]}
    write_report(args.out, report)
    print(json.dumps({"status": report["status"], "report": args.out, "processed_fps": report["processed_fps"],
                      "geometry_fps": report["geometry_fps"]}))
    return 1 if report["status"] == "error" else 2 if early_stop else 0
