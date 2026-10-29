"""Bounded acquisition worker; never imports or invokes desktop input backends."""
from dataclasses import asdict
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import secrets
import subprocess
import sys
import time

from .collection import PROTOCOL, Protocol, schedule
from .collection_store import SessionStore, mark_interrupted, reserve


def add_parser(sub):
    q = sub.add_parser("collect", help="Fullscreen combined pilot: calibration, gaze, gestures, ordinary reading; no input control")
    q.add_argument("--head-pose", action="store_true", help="Joint eye/head collection protocol v2")
    q.add_argument("--gaze-profile", help="Evaluate a trained joint gaze profile; predictions hidden in scored trials")
    q.add_argument("--tracking-only", action="store_true", help="Reference, calibration and visible gaze practice; requires --gaze-profile")
    q.add_argument("--plan", action="store_true", help="Print the protocol without opening a camera or saving data")
    q.add_argument("--device")
    q.add_argument("--model", help="Local MediaPipe .task weights; no downloads")
    q.add_argument("--width", type=int, default=1920)
    q.add_argument("--height", type=int, default=1080)
    q.add_argument("--fps", type=float, default=30)
    q.add_argument("--fourcc", default="MJPG")
    q.add_argument("--warmup", type=float, default=3)
    q.add_argument("--disable-dynamic-fps", action="store_true")
    q.add_argument("--lighting")
    q.add_argument("--distance-cm", type=float)
    q.add_argument("--notes", help="Glasses, laptop height/facing, ambient changes and other setup notes")
    q.add_argument("--sitting-id", help="Same identifier for runs in the same sitting; never split these across training/test")
    q.add_argument("--split", choices=("pilot", "train", "dev", "test"), default="pilot")
    q.add_argument("--seed", type=int)
    q.add_argument("--trials-per-pattern", type=int, default=5)
    q.add_argument("--reading-seconds", type=float, default=180)
    q.add_argument("--include-ll", action="store_true", help="Add two optional LL trials to a pilot")
    q.add_argument("--max-minutes", type=float, default=30, help="Overall worker deadline, including user breaks (maximum 60)")
    q.add_argument("--worker-session", help=__import__("argparse").SUPPRESS)


def dispatch(args, raw):
    import math
    for value in (args.fps, args.warmup, args.reading_seconds, args.max_minutes):
        if not math.isfinite(value) or value <= 0:
            raise ValueError("Timing/rate arguments must be positive and finite")
    if not 1 <= args.trials_per_pattern <= 20 or not 10 <= args.reading_seconds <= 600:
        raise ValueError("Use 1–20 trials per pattern and 10–600 seconds reading")
    if args.width <= 0 or args.height <= 0 or args.warmup > 60 or args.max_minutes > 60:
        raise ValueError("Positive dimensions required; warmup <=60s and total deadline <=60min")
    if len(args.fourcc) != 4 or not args.fourcc.isascii():
        raise ValueError("FOURCC must be four ASCII characters")
    if args.split != "pilot" and (args.include_ll or args.trials_per_pattern != 5 or args.reading_seconds != 180):
        raise ValueError("Reduced/custom budgets and LL exploration are pilot-only")
    if args.tracking_only and args.split != "pilot":
        raise ValueError("Tracking practice must use --split pilot")
    if args.tracking_only and not args.gaze_profile:
        raise ValueError("--tracking-only requires --gaze-profile")
    if args.gaze_profile or args.tracking_only:
        args.head_pose = True
    if args.plan:
        seed = 1 if args.seed is None else args.seed
        steps = schedule(seed, args.trials_per_pattern, args.reading_seconds, args.include_ll, args.head_pose, args.tracking_only)
        print(json.dumps({"protocol": ("eyecheck-head-pose-v2" if args.head_pose else PROTOCOL), "seed": seed, "seeds": [seed, seed+1, seed+2],
                          "preparation_seconds_each_item": 2,
                          "minimum_timed_seconds_excluding_reviews": sum(2+s.seconds for s in steps),
                          "steps": [asdict(s) for s in steps]}, indent=2))
        return 0
    if platform.system() != "Linux":
        raise RuntimeError("Live collection requires the Linux desktop and V4L2; --plan works offline")
    if not all((args.device, args.model, args.lighting, args.notes, args.sitting_id)):
        raise ValueError("Live collection requires --device, --model, --lighting, --distance-cm, --notes and --sitting-id")
    if args.distance_cm is None or not math.isfinite(args.distance_cm) or args.distance_cm <= 0:
        raise ValueError("Record a positive finite viewing distance with --distance-cm")
    if not Path(args.model).is_file():
        raise ValueError("Local model file does not exist")
    if args.worker_session:
        return run(args, Path(args.worker_session))
    # A separate process bounds native capture/inference/cleanup hangs.
    import fcntl
    from .pointer import state_dir  # shared pause-file convention, no input calls
    with (state_dir() / "collection.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("Another collector is running") from exc
        metadata = {"protocol": ("eyecheck-head-pose-v2" if args.head_pose else PROTOCOL), "settings": {k: v for k, v in vars(args).items() if k != "worker_session"},
                    "seed": args.seed if args.seed is not None else secrets.randbits(31),
                    "sitting_id": args.sitting_id, "split": args.split,
                    "numeric_only": True, "desktop_input_enabled": False}
        path = reserve(metadata)
        print(f"Private dataset: {path}", flush=True)
        child = None
        try:
            child = subprocess.Popen([sys.executable, "-m", "eyecheck", *raw, "--worker-session", str(path)])
            code = child.wait(timeout=args.max_minutes * 60 + args.warmup + 45)
            manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
            if code not in (0, 1, 2) or manifest["status"] in ("reserved", "running"):
                mark_interrupted(path, f"Unexpected worker exit {code}")
                return 1
            return code
        except BaseException as exc:
            if child is not None and child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()
            mark_interrupted(path, f"{type(exc).__name__}: {exc}")
            print(f"Collection interrupted; partial evidence retained: {path}", file=sys.stderr)
            return 2 if isinstance(exc, KeyboardInterrupt) else 1


def display_signature(metadata):
    return {k: metadata[k] for k in ("window_logical_size", "screen_name", "screen_logical_geometry", "device_pixel_ratio")}


def run(args, path):
    store = SessionStore(path, {}, resume_reserved=True)
    seed = store.manifest["seed"]
    steps = schedule(seed, args.trials_per_pattern, args.reading_seconds, args.include_ll, args.head_pose, args.tracking_only)
    gaze_model = None
    if args.gaze_profile:
        from .gaze_model import load_profile
        gaze_model = load_profile(args.gaze_profile)
    protocol = Protocol(steps, lambda row: store.append("events", row), args.head_pose, gaze_model)
    capture = detector = view = None
    status, error = "incomplete", None
    details = {"schedule": [asdict(s) for s in steps], "seeds": [seed, seed+1, seed+2],
               "timing_note": "Read completion is not sensor exposure. Paint acknowledgement is not physical scanout. 250ms is a provisional latency gate, not measured alignment accuracy."}
    try:
        import cv2
        import mediapipe as mp
        from mediapipe.tasks import python
        from mediapipe.tasks.python import vision
        from PySide6.QtWidgets import QApplication
        from .camera import LatestCapture
        from .collection_ui import create_view
        from .observations import observe, SCHEMA, LIMITS
        from .pointer import state_dir
        from .common import stats
        details.update(feature_schema=SCHEMA, feature_limits=LIMITS,
                       python=sys.version, platform=platform.platform(),
                       model_sha256=hashlib.sha256(Path(args.model).read_bytes()).hexdigest(),
                       source_sha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                      for p in Path(__file__).parent.glob("*.py")})
        details["versions"] = {}
        for package in ("numpy", "mediapipe", "opencv-contrib-python", "opencv-python", "PySide6"):
            try:
                details["versions"][package] = importlib.metadata.version(package)
            except importlib.metadata.PackageNotFoundError:
                details["versions"][package] = None
        app = QApplication.instance() or QApplication([])
        def action(kind, value):
            now = time.monotonic()
            if kind == "advance":
                protocol.advance(now, value)
            elif kind == "pause":
                protocol.pause(now)
            elif kind == "repeat":
                protocol.repeat(now, value)
        view = create_view(app, protocol, store.manifest["settings"], action)
        detector = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(
            base_options=python.BaseOptions(model_asset_path=args.model),
            running_mode=vision.RunningMode.VIDEO, num_faces=1,
            output_facial_transformation_matrixes=args.head_pose))
        args.seconds = args.max_minutes * 60
        capture = LatestCapture(cv2, args)
        store.checkpoint(**details)
        pause_file = state_dir() / "pause"
        def pause_stamp():
            try:
                s = pause_file.stat()
                return s.st_mtime_ns, s.st_ctime_ns
            except FileNotFoundError:
                return None
        seen_pause = pause_stamp()  # ignore old signals; never remove another probe's pause flag
        last_id, last_timestamp, consecutive_ready = 0, -1, 0
        profile = actual_shape = None
        last_frame = start = time.monotonic()
        processing_intervals = []
        inference_ms = []
        previous_read = None
        if gaze_model:
            from .gaze_model import compatibility
            current = {**details, "actual_frame_size": [args.width, args.height], "display": view.metadata()}
            if compatibility(current) != gaze_model.get("compatibility"):
                raise ValueError("Gaze profile camera/model/display mismatch")
            details["gaze_profile_sha256"] = hashlib.sha256(Path(args.gaze_profile).read_bytes()).hexdigest()
        capture.thread.start()
        while True:
            if time.monotonic()-last_frame > .25:
                protocol.latest_prediction = None
                if protocol.smoother:
                    protocol.smoother.update(None, time.monotonic())
            view.refresh()
            app.processEvents()
            now = time.monotonic()
            if protocol.completed:
                status = "recorded"
                break
            if not view.isVisible():
                break
            if not view.isActiveWindow() or view.isMinimized():
                protocol.pause(now, "window_not_active")
            if capture.error:
                raise RuntimeError(capture.error)
            if not capture.thread.is_alive():
                raise RuntimeError("Capture stopped or overall recording deadline was reached")
            signal = pause_stamp()
            if signal is not None and signal != seen_pause:
                protocol.pause(now, "global_pause_signal")
            seen_pause = signal
            if protocol.state != "setup":
                signature = display_signature(view.metadata())
                if profile is None:
                    profile = signature
                    details["display"] = profile
                elif profile != signature:
                    raise RuntimeError("Display geometry changed; start a fresh session and recalibrate")
            with capture.lock:
                latest = capture.latest
            if latest is not None and latest[0] != last_id:
                frame_id, captured, frame = latest
                last_id, last_frame = frame_id, captured
                shape = [frame.shape[1], frame.shape[0]]
                if shape != [args.width, args.height]:
                    details["actual_frame_size"] = shape
                    raise RuntimeError(f"Requested {args.width}x{args.height}, received {shape[0]}x{shape[1]}; select a verified mode explicitly")
                if actual_shape is not None and actual_shape != shape:
                    raise RuntimeError("Camera frame dimensions changed; recalibration requires a fresh session")
                actual_shape = shape
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                timestamp = max(last_timestamp + 1, int(captured * 1000))
                last_timestamp = timestamp
                inference_start = time.monotonic()
                result = detector.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), timestamp)
                observation = observe(result.face_landmarks[0] if result.face_landmarks else [], *shape)
                if args.head_pose:
                    from .head_pose import extract
                    matrices = getattr(result, "facial_transformation_matrixes", [])
                    observation["head_pose"] = extract(matrices[0] if len(matrices) else None, observation["pose"])
                inference_end = time.monotonic()
                row = protocol.observation(captured, inference_end, observation)
                row.update(frame_id=frame_id, inference_start_monotonic_s=inference_start,
                           mediapipe_timestamp_ms=timestamp, actual_frame_size=shape)
                store.append("observations", row)
                inference_ms.append((inference_end-inference_start)*1000)
                if previous_read is not None:
                    processing_intervals.append((captured-previous_read)*1000)
                previous_read = captured
                consecutive_ready = consecutive_ready + 1 if observation["iris_valid"] and row["fresh_within_250ms"] and (not args.head_pose or observation["head_pose"]["valid"]) else 0
                view.set_preview(rgb, consecutive_ready >= 10,
                    f"Actual frames: {shape[0]}×{shape[1]}; both-eye geometry ready: {consecutive_ready}/10. "
                    "Sanity checks do not prove eye visibility or accurate gaze.")
            now = time.monotonic()
            if now-last_frame > (args.warmup+10 if capture.started is None else 5):
                raise RuntimeError("No fresh distinct camera frame within the startup/5-second allowance")
            old_version = protocol.version
            protocol.tick(now)
            if protocol.version != old_version and protocol.state in ("review", "retry"):
                app.beep()  # no timing/ground-truth claim; useful while eyes are closed
                store.checkpoint(summary=protocol.summary())
            time.sleep(.005)
        details.update(actual_frame_size=actual_shape, camera_actual=capture.actual,
                       dynamic_fps_control=capture.dynamic_fps_control,
                       capture_reads=capture.count, capture_duplicates=capture.duplicates,
                       read_intervals_ms=stats(capture.intervals), processed_intervals_ms=stats(processing_intervals),
                       inference_ms=stats(inference_ms))
    except KeyboardInterrupt:
        error = "KeyboardInterrupt"
    except Exception as exc:
        status, error = "error", f"{type(exc).__name__}: {exc}"
    finally:
        protocol.stop(time.monotonic())
        if capture is not None:
            capture.stop.set()
            if capture.thread.ident is not None:
                capture.thread.join(timeout=2)
            details["capture_thread_still_alive"] = capture.thread.is_alive()
            details["camera_actual"] = capture.actual
            if capture.thread.is_alive():
                status, error = "error", "Camera thread did not stop; parent deadline bounds worker lifetime"
        if detector is not None:
            try:
                detector.close()
            except Exception as exc:
                status, error = "error", f"Model cleanup failed: {exc}"
        if view is not None:
            view.close()
        store.finish(status, error=error, summary=protocol.summary(), **details)
    print(f"{status}: {path}", flush=True)
    if error:
        print(error, file=sys.stderr)
    return 0 if status == "recorded" else 2 if status == "incomplete" else 1
