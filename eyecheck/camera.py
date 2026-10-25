"""Bounded latest-frame capture with optional Qt preview and local landmarks."""
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import threading
import time

from .common import command, stats, write_report
from .features import extract


def disable_dynamic_fps(device):
    result = command(["v4l2-ctl", f"--device={device}",
                      "--set-ctrl=exposure_dynamic_framerate=0",
                      "--get-ctrl=exposure_dynamic_framerate"], timeout=2)
    value = None
    for line in result.get("stdout", "").splitlines():
        key, sep, raw = line.partition(":")
        if sep and key.strip() == "exposure_dynamic_framerate":
            value = raw.strip()
    if result["status"] != "ok" or value != "0":
        raise RuntimeError(f"Could not verify exposure_dynamic_framerate=0: {result}")
    return {"requested": 0, "readback_before_capture": 0, "method": "v4l2-ctl",
            "note": "Setting is left applied. Readback does not guarantee delivered FPS."}


class LatestCapture:
    def __init__(self, cv2, args):
        self.cv2, self.args = cv2, args
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.latest = None
        self.error = None
        self.actual = None
        self.dynamic_fps_control = None
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
            if getattr(self.args, "disable_dynamic_fps", False):
                self.dynamic_fps_control = disable_dynamic_fps(self.args.device)
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
                    print(f"MEASURING LIVE CAMERA for {self.args.seconds:g}s. "
                          + ("Follow the on-screen prompts." if getattr(self.args, "command", "camera") == "guided"
                             else "Stay seated until the final report."), flush=True)
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
    timeline = None
    if getattr(args, "diagnostic_timeline", False):
        from .timeline import FrameTimeline
        timeline = FrameTimeline()
        print("DIAGNOSTIC TIMELINE: one-second aggregates enabled. Use the elapsed counter for cover/uncover timing.", flush=True)
    print(f"LIVE CAMERA: {args.device}. "
          + ("The .task file supplies model weights; your current webcam frames are the input."
             if args.model else "Capture-only run; no landmark model enabled."), flush=True)
    print(f"Keep your face visible, use your usual glasses, and maintain the same distance and lighting. "
          f"Warmup: {args.warmup:g}s after camera setup. No video is saved.", flush=True)
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
    stop_reason = None
    started_unix_ns = time.time_ns()
    next_progress = 0
    start = time.monotonic()
    cpu_start = time.process_time()
    capture.thread.start()
    try:
        while True:
            if app:
                app.processEvents()
                if not window.isVisible():
                    early_stop = True
                    stop_reason = "preview_closed_or_hidden"
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
            face_count = 0
            frame_reason = None
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            if timeline is not None:
                sampled = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)[::8, ::8]
                gray_mean, gray_std = float(sampled.mean()), float(sampled.std())
                dark_fraction = float((sampled < 16).mean())
            if detector:
                timestamp = max(last_timestamp + 1, int(captured * 1000))
                last_timestamp = timestamp
                inference_start = time.monotonic()
                result = detector.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), timestamp)
                measures["inference_ms"].append((time.monotonic() - inference_start) * 1000)
                face_count = len(result.face_landmarks)
                if not result.face_landmarks:
                    frame_reason = "no_face"
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
                        frame_reason = str(exc)
                        reasons[str(exc)] += 1
            if timeline is not None:
                timeline.add(captured - (capture.started or start), frame_id, face_count, eyes,
                             frame_reason, gray_mean, gray_std, dark_fraction, age)
            measures["dequeue_to_result_ms"].append((time.monotonic() - captured) * 1000)
            elapsed_live = time.monotonic() - (capture.started or start)
            if elapsed_live >= next_progress:
                print(f"LIVE {elapsed_live:.0f}/{args.seconds:g}s | processed {processed} | "
                      f"basic geometry {geometry if detector else 'disabled'} | remain in view", flush=True)
                if timeline is not None:
                    print(f"DIAG {elapsed_live:.1f}s | frame {frame_id} | faces {face_count} | "
                          f"geometry {eyes is not None} | gray {gray_mean:.1f} | dark {dark_fraction:.1%}", flush=True)
                next_progress = elapsed_live + (1 if timeline is not None else 10)
            if app:
                from .preview import composite
                preview = composite(rgb, eyes)
                q = QImage(preview.data, preview.shape[1], preview.shape[0], preview.strides[0], QImage.Format_RGB888).copy()
                label.setPixmap(QPixmap.fromImage(q))
                info.setText(f"{elapsed_live:.1f}/{args.seconds:g}s | CURRENT geometry {'available' if eyes else 'unavailable'} | "
                             f"processed {processed} | total geometry {geometry} | no pointer input | unmirrored")
    except KeyboardInterrupt:
        early_stop = True
        stop_reason = "keyboard_interrupt"
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
              "input_source": "live_v4l2_camera", "dynamic_fps_control": capture.dynamic_fps_control,
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
    if timeline is not None:
        report["diagnostic_timeline"] = timeline.report(elapsed)
        report["run_started_unix_ns"] = started_unix_ns
        report["stop_reason"] = stop_reason or ("capture_error" if report["status"] == "error" else "capture_finished")
        report["source_sha256"] = {
            name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
            for name in ("camera.py", "features.py", "timeline.py")}
    write_report(args.out, report)
    print(json.dumps({"status": report["status"], "report": args.out, "processed_fps": report["processed_fps"],
                      "geometry_fps": report["geometry_fps"]}))
    return 1 if report["status"] == "error" else 2 if early_stop else 0
