import contextlib
import io
import json
from pathlib import Path
import tempfile
import threading
import types
import unittest
from unittest.mock import patch

from eyecheck import camera
from eyecheck.cli import main, parser
from eyecheck.features import EYES
from eyecheck.timeline import FrameTimeline


class TimelineTests(unittest.TestCase):
    def test_missing_intervals_are_not_counted_as_no_face(self):
        timeline = FrameTimeline()
        eyes = {side: {"openness": .2} for side in ("left", "right")}
        timeline.add(.2, 1, 1, eyes, None, 100, 20, .1, 2)
        timeline.add(2.2, 3, 0, None, "no_face", 0, 0, 1, 3)
        rows = timeline.report(2.5)["bins"]
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[1]["processed_frames"], 0)
        self.assertEqual(rows[1]["reasons"], {})
        self.assertEqual(rows[2]["reasons"], {"no_face": 1})
        self.assertEqual(rows[2]["end_seconds"], 2.5)
        self.assertEqual(rows[2]["metrics"]["left_openness"]["n"], 0)

    def test_face_with_invalid_geometry_is_distinguished(self):
        timeline = FrameTimeline()
        timeline.add(.1, 1, 1, None, "Eye geometry outside frame", 90, 15, 0, 3)
        row = timeline.report(.5)["bins"][0]
        self.assertEqual(row["face_frames"], 1)
        self.assertEqual(row["geometry_frames"], 0)
        self.assertIn("Eye geometry outside frame", row["reasons"])

    def test_cli_requires_model_and_rejects_guided_or_existing_output(self):
        self.assertFalse(parser().parse_args(["camera", "--device", "0", "--out", "unused"]).diagnostic_timeline)
        with tempfile.TemporaryDirectory() as directory:
            existing = Path(directory) / "keep.json"
            existing.write_text("original")
            for argv in (
                ["camera", "--device", "0", "--out", "unused"],
                ["guided", "--device", "0", "--out", "unused", "--model", "model"],
                ["camera", "--device", "0", "--out", str(existing), "--model", "model"],
            ):
                with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                    main([*argv, "--diagnostic-timeline"])
            self.assertEqual(existing.read_text(), "original")

    def test_camera_timeline_tracks_visible_covered_visible_without_stale_geometry(self):
        clock = types.SimpleNamespace(value=100.0)

        class Frame:
            shape = (100, 100, 3)
            def __init__(self, value): self.value = value
            def __getitem__(self, key): return self
            def mean(self): return self.value
            def std(self): return 0
            def __lt__(self, threshold): return Frame(float(self.value < threshold))

        frames = iter([Frame(100), Frame(0), Frame(120)])
        capture = types.SimpleNamespace(
            lock=threading.Lock(), stop=threading.Event(), started=100.0,
            error=None, count=0, duplicates=0, intervals=[], latest=None,
            actual={}, dynamic_fps_control=None)

        class Thread:
            stopped = False
            def start(self): pass
            def join(self, timeout): self.stopped = True
            def is_alive(self):
                if self.stopped: return False
                frame = next(frames, None)
                if frame is None: return False
                capture.count += 1
                capture.latest = (capture.count, clock.value, frame)
                clock.value += 1
                return True
        capture.thread = Thread()
        pts = [types.SimpleNamespace(x=.5, y=.5) for _ in range(478)]
        for a, b, upper, lower, iris in EYES.values():
            for index, x, y in ((a,.4,.5),(b,.6,.5),(upper,.5,.48),(lower,.5,.52),(iris,.5,.5)):
                pts[index] = types.SimpleNamespace(x=x, y=y)
        detector = types.SimpleNamespace(
            detect_for_video=lambda image, timestamp: types.SimpleNamespace(face_landmarks=[pts] if image.value else []),
            close=lambda: None)
        vision = types.SimpleNamespace(
            FaceLandmarker=types.SimpleNamespace(create_from_options=lambda options: detector),
            FaceLandmarkerOptions=lambda **kwargs: kwargs,
            RunningMode=types.SimpleNamespace(VIDEO=1))
        python = types.SimpleNamespace(BaseOptions=lambda **kwargs: kwargs, vision=vision)
        mp = types.SimpleNamespace(Image=lambda **kwargs: kwargs["data"], image_format=None,
                                   ImageFormat=types.SimpleNamespace(SRGB=1))
        cv = types.SimpleNamespace(COLOR_BGR2RGB=1, COLOR_BGR2GRAY=2, cvtColor=lambda frame, mode: frame)
        modules = {"cv2": cv, "mediapipe": mp, "mediapipe.tasks": types.SimpleNamespace(python=python),
                   "mediapipe.tasks.python": python}
        with tempfile.TemporaryDirectory() as directory:
            model, out = Path(directory) / "model.task", Path(directory) / "report.json"
            model.write_bytes(b"test weights")
            args = types.SimpleNamespace(device="fake", model=str(model), preview=False, warmup=1,
                seconds=3, out=str(out), width=100, height=100, fps=30, fourcc="MJPG", label="test",
                diagnostic_timeline=True)
            with patch.dict("sys.modules", modules), patch.object(camera, "LatestCapture", return_value=capture), \
                 patch.object(camera.time, "monotonic", side_effect=lambda: clock.value), \
                 contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(camera.run(args), 0)
            report = json.loads(out.read_text())
        self.assertEqual(report["processed_frames"], 3)
        self.assertEqual(report["geometry_frames"], 2)
        self.assertEqual(report["reasons"], {"no_face": 1})
        rows = report["diagnostic_timeline"]["bins"]
        self.assertEqual([r["geometry_frames"] for r in rows], [1, 0, 1])
        self.assertEqual(rows[1]["metrics"]["sampled_gray_mean"]["median"], 0)
        self.assertEqual(rows[1]["metrics"]["sampled_dark_fraction"]["median"], 1)
        self.assertEqual(report["stop_reason"], "capture_finished")
        self.assertEqual(len(report["source_sha256"]["camera.py"]), 64)
