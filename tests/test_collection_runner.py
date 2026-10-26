"""Exercise worker lifecycle and parent recovery without camera/GUI/input hardware."""
from contextlib import redirect_stdout, redirect_stderr
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import types
import unittest
from unittest.mock import Mock, patch

from eyecheck.cli import parser
from eyecheck.collection_run import dispatch, run
from eyecheck.collection_store import reserve
from test_guided import landmarks


class RunnerTests(unittest.TestCase):
    def execute_worker(self, fail=False, change_display=False, close_model_fails=False):
        class App:
            events = 0
            @staticmethod
            def instance(): return app
            @staticmethod
            def beep(): pass
            def processEvents(self): self.events += 1
        app = App()
        view = Mock()
        view.isVisible.side_effect = lambda: app.events < 4
        view.isActiveWindow.return_value = True
        view.isMinimized.return_value = False
        def metadata():
            return {"window_logical_size": [1000 if app.events < 2 or not change_display else 900, 800],
                    "screen_name": "synthetic", "screen_logical_geometry": [0, 0, 1000, 800], "device_pixel_ratio": 1}
        view.metadata.side_effect = metadata
        def create_view(app, protocol, settings, action):
            action("advance", None)
            return view
        detector = Mock()
        detector.detect_for_video.side_effect = RuntimeError("synthetic inference failure") if fail else lambda *args: types.SimpleNamespace(face_landmarks=[landmarks(openness=.01)])
        if close_model_fails:
            detector.close.side_effect = RuntimeError("synthetic cleanup failure")
        thread = Mock(ident=1)
        thread.is_alive.side_effect = lambda: not capture.stop.is_set()
        import threading
        capture = types.SimpleNamespace(thread=thread, stop=threading.Event(), lock=threading.Lock(),
            latest=(1, time.monotonic(), types.SimpleNamespace(shape=(800, 1000, 3))), error=None,
            started=time.monotonic(), actual={"width": 1000, "height": 800},
            dynamic_fps_control=None, count=1, duplicates=0, intervals=[])
        widgets = types.ModuleType("PySide6.QtWidgets")
        widgets.QApplication = App
        mp = types.ModuleType("mediapipe")
        mp.Image = lambda **kwargs: kwargs
        mp.ImageFormat = types.SimpleNamespace(SRGB=1)
        python = types.ModuleType("mediapipe.tasks.python")
        python.BaseOptions = lambda **kwargs: kwargs
        vision = types.ModuleType("mediapipe.tasks.python.vision")
        vision.FaceLandmarkerOptions = lambda **kwargs: kwargs
        vision.FaceLandmarker = types.SimpleNamespace(create_from_options=lambda options: detector)
        vision.RunningMode = types.SimpleNamespace(VIDEO=1)
        python.vision = vision
        tasks = types.ModuleType("mediapipe.tasks")
        tasks.python = python
        cv = types.ModuleType("cv2")
        cv.COLOR_BGR2RGB = 1
        cv.cvtColor = lambda frame, mode: frame
        modules = {"cv2": cv, "mediapipe": mp, "mediapipe.tasks": tasks, "mediapipe.tasks.python": python,
                   "mediapipe.tasks.python.vision": vision, "PySide6": types.ModuleType("PySide6"), "PySide6.QtWidgets": widgets}
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {"XDG_STATE_HOME": folder}):
            model = Path(folder)/"model.task"
            model.write_bytes(b"synthetic model")
            args = parser().parse_args(["collect", "--model", str(model), "--width", "1000", "--height", "800"])
            path = reserve({"seed": 1, "settings": {"lighting": "synthetic", "distance_cm": 70, "notes": "test"}})
            with patch.dict("sys.modules", modules), patch("eyecheck.camera.LatestCapture", return_value=capture), \
                 patch("eyecheck.collection_ui.create_view", side_effect=create_view), \
                 patch("eyecheck.pointer.state_dir", return_value=Path(folder)), \
                 redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                code = run(args, path)
            manifest = json.loads((path/"manifest.json").read_text())
            rows = [json.loads(x) for x in (path/"observations.jsonl").read_text().splitlines()]
            self.assertTrue(capture.stop.is_set())
            detector.close.assert_called_once()
            view.close.assert_called_once()
            self.assertEqual(manifest["summary"]["attempts"][0]["status"], "interrupted")
            return code, manifest, rows

    def test_user_close_preserves_closed_eye_numeric_trace(self):
        code, manifest, rows = self.execute_worker()
        self.assertEqual(code, 2)
        self.assertEqual(manifest["status"], "incomplete")
        self.assertEqual(len(rows), 1)
        self.assertFalse(rows[0]["observation"]["iris_valid"])
        self.assertTrue(rows[0]["observation"]["eyelids_valid"])

    def test_inference_error_finalizes_and_closes_resources(self):
        code, manifest, rows = self.execute_worker(fail=True)
        self.assertEqual(code, 1)
        self.assertIn("synthetic inference failure", manifest["error"])
        self.assertEqual(rows, [])

    def test_display_change_stops_instead_of_reusing_calibration(self):
        code, manifest, _ = self.execute_worker(change_display=True)
        self.assertEqual(code, 1)
        self.assertIn("Display geometry changed", manifest["error"])

    def test_model_cleanup_failure_is_not_success(self):
        code, manifest, _ = self.execute_worker(close_model_fails=True)
        self.assertEqual(code, 1)
        self.assertIn("Model cleanup failed", manifest["error"])

    def test_parent_timeout_terminates_child_and_marks_partial(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {"XDG_STATE_HOME": folder}):
            model = Path(folder)/"model.task"
            model.write_bytes(b"synthetic")
            raw = ["collect", "--model", str(model), "--device", "/dev/fake", "--lighting", "test",
                   "--distance-cm", "70", "--notes", "synthetic", "--sitting-id", "synthetic"]
            args = parser().parse_args(raw)
            child = Mock()
            child.wait.side_effect = [subprocess.TimeoutExpired("synthetic", 1), 0]
            child.poll.return_value = None
            fcntl = types.SimpleNamespace(LOCK_EX=1, LOCK_NB=2, flock=Mock())
            with patch.dict("sys.modules", {"fcntl": fcntl}), patch("eyecheck.collection_run.platform.system", return_value="Linux"), \
                 patch("eyecheck.pointer.state_dir", return_value=Path(folder)), \
                 patch("eyecheck.collection_run.subprocess.Popen", return_value=child), \
                 redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                self.assertEqual(dispatch(args, raw), 1)
            child.terminate.assert_called_once()
            manifest = next(Path(folder).glob("eyecheck/datasets/*/manifest.json"))
            self.assertEqual(json.loads(manifest.read_text())["status"], "incomplete")


if __name__ == "__main__":
    unittest.main()
