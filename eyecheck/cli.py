import argparse
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

from .common import positive, write_report
from .pointer import validate_coordinate_scale


def parser():
    p = argparse.ArgumentParser(description="Linux eye tracking validation and numeric collection and joint eye/head model training")
    sub = p.add_subparsers(dest="command", required=True)
    from .collection_run import add_parser
    add_parser(sub)
    for name in ("train-gaze", "evaluate-gaze"):
        q = sub.add_parser(name, help="Offline joint eye/head gaze model")
        q.add_argument("--sessions", nargs="+", required=True)
        q.add_argument("--out", required=True)
        if name == "train-gaze":
            q.add_argument("--alpha", type=float, default=.01)
        else:
            q.add_argument("--profile", required=True)
            q.add_argument("--split", choices=("dev", "test"), required=True)
    for name in ("inventory", "imports", "displays"):
        q = sub.add_parser(name)
        q.add_argument("--out", required=True)
    q = sub.add_parser("pause")
    q.add_argument("--out", help="Optional acknowledgement report for testing a desktop shortcut")
    q = sub.add_parser("pointer-targets", help="Static fullscreen coordinate chart; sends no pointer input")
    q.add_argument("--out", required=True)
    q = sub.add_parser("pointer")
    q.add_argument("--out", required=True)
    q.add_argument("--enable-motion", action="store_true")
    q.add_argument("--allow-screen-share", action="store_true")
    q.add_argument("--backend", choices=("legacy", "eis"), default="legacy",
                   help="Wayland input transport; eis uses libei regions with no scale override")
    q.add_argument("--portal-coordinate-scale", type=validate_coordinate_scale, default=1.0,
                   help="Explicit legacy Wayland coordinate multiplier (0 < scale <= 4; default 1). Diagnostic only; verify visually.")
    q.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    q = sub.add_parser("camera", aliases=["guided"], help="Live camera; 'guided' runs a timed on-screen diagnostic")
    q.add_argument("--device", required=True, help="Verified RGB /dev/videoN or stable symlink")
    q.add_argument("--width", type=int, default=1280)
    q.add_argument("--height", type=int, default=720)
    q.add_argument("--fps", type=positive, default=30)
    q.add_argument("--fourcc", help="Four-character format advertised by v4l2-ctl, e.g. MJPG")
    q.add_argument("--seconds", type=positive, default=30, help="Camera duration; omit for the fixed guided protocol")
    q.add_argument("--warmup", type=positive, default=3)
    q.add_argument("--model", help="Local pretrained model weights, NOT an input video. Inference uses the live camera.")
    q.add_argument("--disable-dynamic-fps", action="store_true",
                   help="Set and verify V4L2 exposure_dynamic_framerate=0 after mode setup; leaves setting applied")
    q.add_argument("--preview", action="store_true", help="Show camera preview; guided uses targets and hides preview")
    q.add_argument("--diagnostic-timeline", action="store_true",
                   help="Camera only, with --model: save one-second image/face/geometry aggregates, no images")
    q.add_argument("--label", default="baseline")
    q.add_argument("--distance-cm", type=positive, help="Guided run: measured viewing distance, recorded as user-reported")
    q.add_argument("--lighting", default="not recorded", help="Guided run: brief lighting description")
    q.add_argument("--notes", default="", help="Guided run: optional setup notes; stored in the report")
    q.add_argument("--out", required=True)
    q.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    return p


def main(argv=None):
    raw = list(sys.argv[1:] if argv is None else argv)
    p = parser()
    args = p.parse_args(raw)
    if getattr(args, "diagnostic_timeline", False):
        if args.command != "camera" or not args.model:
            p.error("--diagnostic-timeline requires camera with --model")
        if not args.worker and Path(args.out).exists():
            p.error("Output already exists; use a fresh filename to preserve diagnostic evidence")
    # Protect generated state by default on Linux. Existing parent directories are untouched.
    os.umask(0o077)
    try:
        if args.command in ("train-gaze", "evaluate-gaze"):
            from .gaze_model import dispatch as gaze_dispatch
            return gaze_dispatch(args)
        if args.command == "collect":
            from .collection_run import dispatch
            return dispatch(args, raw)
        if args.command in ("pointer", "pointer-targets") and not getattr(args, "worker", False) and Path(args.out).exists():
            p.error("Output already exists; use a fresh filename to preserve evidence")
        from . import inventory
        if args.command in ("pause", "pointer"):
            if platform.system() != "Linux":
                raise RuntimeError("Native pointer probes require Linux")
            from . import pointer
            if args.command == "pause":
                result = pointer.pause()
                if args.out:
                    write_report(args.out, result)
                return 0
            if not args.enable_motion:
                raise RuntimeError("Pointer movement requires explicit --enable-motion")
            if not args.worker:
                write_report(args.out, {"schema": 1, "kind": "pointer", "status": "running"})
                child = subprocess.Popen([sys.executable, "-m", "eyecheck", *raw, "--worker"])
                try:
                    code = child.wait(timeout=195)
                    if code not in (0, 1) or json.loads(Path(args.out).read_text())["status"] == "running":
                        raise RuntimeError(f"Pointer worker exited unexpectedly ({code})")
                    return code
                except (subprocess.TimeoutExpired, KeyboardInterrupt):
                    child.terminate()
                    try:
                        child.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        child.kill()
                        child.wait()
                    raise RuntimeError("Pointer probe interrupted or timed out; session disconnected")
            result = pointer.run(args)
        elif args.command == "pointer-targets":
            if platform.system() != "Linux":
                raise RuntimeError("Pointer target validation must run on the Linux desktop")
            from .pointer_targets import run
            result = run(args)
        elif args.command == "inventory":
            result = inventory.inventory()
        elif args.command == "imports":
            result = inventory.imports()
            if result["dependency_consistency"]["status"] != "ok":
                result["status"] = "blocked"
        elif args.command == "displays":
            p2 = subprocess.run([sys.executable, "-c", "from eyecheck.inventory import displays; displays()"],
                                capture_output=True, text=True, timeout=20)
            if p2.returncode:
                raise RuntimeError("Qt display probe failed: " + p2.stderr[-3000:])
            result = json.loads(p2.stdout)
        else:
            if args.command == "guided":
                from .guided import DURATION
                if any(x == "--seconds" or x.startswith("--seconds=") for x in raw):
                    p.error("Guided protocol has a fixed duration; omit --seconds")
                if not args.model:
                    p.error("Guided validation requires --model with a local .task file")
                if not args.worker and Path(args.out).exists():
                    p.error("Guided output already exists; choose a new filename to preserve results")
                args.seconds = DURATION
                args.preview = False
            if args.width <= 0 or args.height <= 0 or args.seconds > 3600 or args.warmup > 60:
                p.error("Positive dimensions required; maximum duration 3600s and warmup 60s")
            if args.fourcc and (len(args.fourcc) != 4 or not args.fourcc.isascii()):
                p.error("--fourcc must be four ASCII characters")
            if platform.system() != "Linux":
                raise RuntimeError("Camera validation must run on Linux using V4L2")
            if args.model and not Path(args.model).is_file():
                raise RuntimeError("Local model file not found; no automatic download is performed")
            if args.worker:
                if args.command == "guided":
                    from .guided_run import run
                else:
                    from .camera import run
                return run(args)
            # Native driver/model calls can hang. Bound the entire child, including imports and release.
            write_report(args.out, {"schema": 1, "kind": args.command, "status": "running"})
            child = subprocess.Popen([sys.executable, "-m", "eyecheck", *raw, "--worker"])
            try:
                code = child.wait(timeout=args.seconds + args.warmup + 45)
            except (subprocess.TimeoutExpired, KeyboardInterrupt) as exc:
                child.terminate()
                try:
                    child.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()
                raise RuntimeError("Camera worker timed out or was interrupted; do not treat run as passing") from exc
            if code not in (0, 1, 2) or json.loads(Path(args.out).read_text())["status"] == "running":
                raise RuntimeError(f"Camera worker exited unexpectedly ({code})")
            return code
        write_report(args.out, result)
        print(f"{result['status']}: {args.out}")
        if result.get("error"):
            print(f"ERROR: {result['error']}", file=sys.stderr)
        return 1 if result["status"] in ("blocked", "error") else 0
    except Exception as exc:
        if getattr(args, "out", None):
            write_report(args.out, {"schema": 1, "kind": args.command, "status": "error", "error": str(exc)})
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
