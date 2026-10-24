"""Exercise report/cleanup paths without a GUI, camera, or ML installation."""
import json
from pathlib import Path
import tempfile
import time
import types
import unittest
from unittest.mock import patch

from eyecheck.guided_run import run
from test_guided import landmarks


class GuidedRunnerTests(unittest.TestCase):
    def execute(self, inference_fails=False):
        class Signal:
            def connect(self, callback): pass
        class Widget:
            def __init__(self, *args): pass
            def __getattr__(self, name): return lambda *args: None
            def isVisible(self): return app.events < 3
        class App:
            events = 0
            @staticmethod
            def instance(): return app
            @staticmethod
            def beep(): pass
            def processEvents(self): self.events += 1
        app = App()
        class Layout(Widget): pass
        class Image:
            Format_RGB888 = 1
            def __init__(self, *args, **kwargs): pass
            def copy(self): return self
        class Pixmap:
            @staticmethod
            def fromImage(image): return image
        class Shortcut:
            def __init__(self, *args): self.activated = Signal()
        class Detector:
            closed = False
            def detect_for_video(self, *args):
                if inference_fails:
                    raise RuntimeError("synthetic inference failure")
                return types.SimpleNamespace(face_landmarks=[landmarks()])
            def close(self): self.closed = True
        detector = Detector()
        class Stop:
            requested = False
            def set(self): self.requested = True
        class Lock:
            def __enter__(self): return self
            def __exit__(self, *args): pass
        class Thread:
            ident = None
            alive = False
            def start(self): self.ident = 1; self.alive = True
            def is_alive(self): return self.alive
            def join(self, timeout): self.alive = False
        capture = types.SimpleNamespace(started=time.monotonic()-2, error=None, thread=Thread(),
            stop=Stop(), lock=Lock(), latest=(1, time.monotonic(), types.SimpleNamespace(shape=(1000, 1000, 3))),
            count=1, duplicates=0, intervals=[], actual={"width": 1000}, dynamic_fps_control=None)
        widgets = types.ModuleType("PySide6.QtWidgets")
        widgets.QApplication, widgets.QWidget, widgets.QLabel, widgets.QVBoxLayout = App, Widget, Widget, Layout
        gui = types.ModuleType("PySide6.QtGui")
        gui.QImage, gui.QPixmap, gui.QFont = Image, Pixmap, Widget
        gui.QShortcut, gui.QKeySequence = Shortcut, Widget
        mp = types.ModuleType("mediapipe")
        mp.Image = lambda **kwargs: kwargs
        mp.ImageFormat = types.SimpleNamespace(SRGB=1)
        tasks = types.ModuleType("mediapipe.tasks")
        python = types.ModuleType("mediapipe.tasks.python")
        python.BaseOptions = lambda **kwargs: kwargs
        vision = types.ModuleType("mediapipe.tasks.python.vision")
        vision.FaceLandmarkerOptions = lambda **kwargs: kwargs
        vision.FaceLandmarker = types.SimpleNamespace(create_from_options=lambda options: detector)
        vision.RunningMode = types.SimpleNamespace(VIDEO=1)
        tasks.python = python
        python.vision = vision
        cv = types.ModuleType("cv2")
        cv.COLOR_BGR2RGB = 1
        cv.cvtColor = lambda frame, mode: frame
        modules = {"cv2": cv, "mediapipe": mp, "mediapipe.tasks": tasks, "mediapipe.tasks.python": python,
                   "mediapipe.tasks.python.vision": vision, "PySide6": types.ModuleType("PySide6"),
                   "PySide6.QtWidgets": widgets, "PySide6.QtGui": gui}
        with tempfile.TemporaryDirectory() as folder:
            model, output = Path(folder)/"model.task", Path(folder)/"result.json"
            model.write_bytes(b"fake weights")
            args = types.SimpleNamespace(model=str(model), warmup=10, label="synthetic", distance_cm=70,
                lighting="test", notes="", width=1280, height=720, fps=30, fourcc="MJPG", out=str(output))
            view = Widget()
            view.metadata = lambda: {"mode": "fullscreen_target_local_text_no_preview"}
            with patch.dict("sys.modules", modules), patch("eyecheck.guided_run.LatestCapture", return_value=capture), \
                 patch("eyecheck.guided_run.create_view", return_value=view):
                code = run(args)
            report = json.loads(output.read_text())
        self.assertTrue(capture.stop.requested)
        self.assertTrue(detector.closed)
        self.assertFalse(capture.thread.is_alive())
        self.assertNotIn('"points"', json.dumps(report))
        return code, report

    def test_window_close_writes_partial_report_and_releases_resources(self):
        code, report = self.execute()
        self.assertEqual(code, 2)
        self.assertEqual(report["status"], "incomplete")
        self.assertEqual(report["processed_frames"], 1)
        self.assertEqual(report["guided"]["phases"][0]["status"], "partial")
        self.assertEqual(report["guided"]["phases"][1]["status"], "not_reached")

    def test_inference_failure_preserves_error_report_and_releases_resources(self):
        code, report = self.execute(inference_fails=True)
        self.assertEqual(code, 1)
        self.assertEqual(report["status"], "error")
        self.assertIn("synthetic inference failure", report["error"])


if __name__ == "__main__":
    unittest.main()
