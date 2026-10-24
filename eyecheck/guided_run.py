"""Linux live-camera runner for the guided diagnostic; no input backend imports."""
import hashlib
import json
from pathlib import Path
import time
from collections import Counter

from .camera import LatestCapture
from .common import stats, write_report
from .guided import DURATION, PHASES, PhaseResults, phase_at
from .observations import LIMITS, SCHEMA, observe
from .preview import composite


def run(args):
    import cv2
    import mediapipe as mp
    from mediapipe.tasks import python
    from mediapipe.tasks.python import vision
    from PySide6.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout
    from PySide6.QtGui import QImage, QPixmap, QFont

    model_hash = hashlib.sha256(Path(args.model).read_bytes()).hexdigest()
    capture = LatestCapture(cv2, args)
    results = PhaseResults()
    reasons = Counter()
    latency, inference = [], []
    processed = eyelid_count = iris_count = 0
    last_id = 0
    last_timestamp = -1
    last_phase = None
    actual_shape = None
    stopped = False
    error = None
    detector = None
    started = time.monotonic()
    measurement_elapsed = 0.0
    cpu_started = time.process_time()
    app = QApplication.instance() or QApplication([])
    window = QWidget()
    window.setWindowTitle("Eyecheck - LIVE guided validation - close or Escape to stop")
    layout = QVBoxLayout(window)
    prompt = QLabel("Opening LIVE camera. Stay seated. Instructions will appear here after warmup.")
    prompt.setFont(QFont("Sans Serif", 14))
    prompt.setWordWrap(True)
    prompt.setMinimumHeight(110)
    prompt.setMaximumWidth(800)
    picture = QLabel("Waiting for camera frames. No video or numeric trace is saved.")
    picture.setMinimumSize(800, 630)
    feedback = QLabel("Landmark plausibility is not gaze accuracy. No pointer input.")
    feedback.setWordWrap(True)
    feedback.setMaximumWidth(800)
    for widget in (prompt, picture, feedback):
        layout.addWidget(widget)
    from PySide6.QtGui import QShortcut, QKeySequence
    escape = QShortcut(QKeySequence("Escape"), window)
    escape.activated.connect(window.close)
    window.show()
    print(f"LIVE GUIDED CAMERA: {DURATION:g}s + {args.warmup:g}s warmup. Follow the on-screen prompts. "
          "Closed-eye prompts last two seconds; count two then reopen even if the beep is inaudible. "
          "Close the window or press Escape to stop. No clicks or recordings.", flush=True)
    try:
        app.processEvents()
        detector = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(
            base_options=python.BaseOptions(model_asset_path=args.model),
            running_mode=vision.RunningMode.VIDEO, num_faces=1))
        started = time.monotonic()
        cpu_started = time.process_time()
        capture.thread.start()
        while True:
            app.processEvents()
            now = time.monotonic()
            if capture.started is not None:
                measurement_elapsed = min(DURATION, max(0, now - capture.started))
            if not window.isVisible():
                stopped = True
                break
            if capture.error:
                error = capture.error
                break
            active = phase_at(measurement_elapsed) if capture.started is not None else None
            if active is not None:
                index, phase, offset = active
                if index != last_phase:
                    QApplication.beep()
                    print(f"PHASE {index + 1}/{len(PHASES)} [{phase.name}] {phase.instruction}", flush=True)
                    last_phase = index
                prompt.setText(f"{index + 1}/{len(PHASES)} | {phase.seconds - offset:.1f}s remaining\n{phase.instruction}")
            if not capture.thread.is_alive():
                break
            with capture.lock:
                latest = capture.latest
            if latest is None or latest[0] == last_id:
                age = now - (latest[1] if latest else started)
                if latest and age > .25:
                    picture.clear()
                    picture.setText("STALE CAMERA FRAME - no current observation")
                    feedback.setText("No fresh frame. Do not interpret this as eye closure.")
                if age > (5 if latest else args.warmup + 5):
                    error = "No fresh frame within the camera timeout"
                    break
                time.sleep(.005)
                continue
            frame_id, captured, frame = latest
            last_id = frame_id
            if now - captured > .25:
                reasons["stale_over_250ms"] += 1
                continue
            actual_shape = [frame.shape[1], frame.shape[0]]
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            timestamp = max(last_timestamp + 1, int(captured * 1000))
            last_timestamp = timestamp
            before = time.monotonic()
            detected = detector.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), timestamp)
            inference.append(1000 * (time.monotonic() - before))
            observation = observe(detected.face_landmarks[0] if detected.face_landmarks else [], *actual_shape)
            delay = 1000 * (time.monotonic() - captured)
            latency.append(delay)
            processed += 1
            eyelid_count += int(observation["eyelids_valid"])
            iris_count += int(observation["iris_valid"])
            reasons.update(observation["reasons"])
            results.add(captured - capture.started, observation, delay)
            preview = composite(rgb, observation["eyes"])
            qimage = QImage(preview.data, preview.shape[1], preview.shape[0], preview.strides[0], QImage.Format_RGB888).copy()
            picture.setPixmap(QPixmap.fromImage(qimage))
            feedback.setText(
                f"CURRENT FRAME: eyelids {'plausible' if observation['eyelids_valid'] else 'INVALID'} | "
                f"iris {'plausible' if observation['iris_valid'] else 'NOT USABLE'}\n"
                + (", ".join(observation["reasons"]) or "Broad geometry checks passed; visual review still required.")
                + "\nUnmirrored live image; subject's right eye crop on left. No pointer input.")
    except KeyboardInterrupt:
        stopped = True
    except Exception as exc:
        error = str(exc)
    finally:
        # Snapshot before cleanup so cleanup time cannot mark unfinished phases complete.
        if capture.started is not None:
            measurement_elapsed = min(DURATION, max(0, time.monotonic() - capture.started))
        capture.stop.set()
        if capture.thread.ident is not None:
            capture.thread.join(timeout=2)
        if capture.thread.is_alive():
            error = error or "Capture thread did not stop"
        if detector:
            try:
                detector.close()
            except Exception as exc:
                error = error or f"Model cleanup failed: {exc}"
        window.close()
    status = "error" if error or capture.error else "incomplete" if stopped or measurement_elapsed < DURATION else "recorded"
    elapsed = max(.001, measurement_elapsed)
    report = {"schema": 2, "kind": "guided", "status": status, "error": error or capture.error,
        "input_source": "live_v4l2_camera", "feature_schema": SCHEMA, "sanity_limits": LIMITS,
        "model_sha256": model_hash, "label": args.label,
        "setup": {"distance_cm_user_reported": args.distance_cm, "lighting_user_reported": args.lighting,
                  "notes_user_reported": args.notes},
        "requested": {"width": args.width, "height": args.height, "fps": args.fps, "fourcc": args.fourcc},
        "driver_reported": capture.actual, "frame_dimensions": actual_shape,
        "dynamic_fps_control": capture.dynamic_fps_control,
        "measured_seconds": measurement_elapsed, "capture_reads": capture.count,
        "identical_consecutive_frames": capture.duplicates,
        "capture_read_fps": max(0, capture.count - 1) / elapsed,
        "processed_frames": processed, "processed_fps": processed / elapsed,
        "eyelid_frames": eyelid_count, "iris_frames": iris_count,
        "reasons": dict(reasons), "read_gap_ms": stats(capture.intervals),
        "inference_ms": stats(inference), "dequeue_to_result_ms": stats(latency),
        "cpu_one_core_percent_including_startup": 100 * (time.process_time() - cpu_started) / max(.001, time.monotonic() - started),
        "guided": results.report(measurement_elapsed),
        "limits": ["Whole-run rates include deliberate closures and face loss; use individual phases.",
                   "No automatic gaze, blink, identity, or action-compliance recognition.",
                   "Broad geometric sanity checks cannot detect every reflection or model hallucination.",
                   "Eyelid plausibility is independent of iris validity, not proof of eyelid accuracy.",
                   "The closure probe is two seconds for observability, not the final click-gesture duration.",
                   "Phase prompts use host monotonic time; camera buffering and human reaction affect alignment.",
                   "Numeric samples are summarized in memory and not persisted as a trace."]}
    write_report(args.out, report)
    print(json.dumps({"status": status, "report": args.out, "processed_fps": report["processed_fps"],
                      "review": "Review phase summaries and manual notes; no automatic pass/fail."}))
    return 1 if status == "error" else 2 if status == "incomplete" else 0
