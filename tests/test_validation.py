import asyncio
import json
import math
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

from eyecheck.common import command, positive, redact, stats, write_report
from eyecheck.features import EYES, extract
from eyecheck.camera import LatestCapture
from eyecheck.pointer import POINTS, sequence
from eyecheck.cli import main, parser


class DiagnosticTests(unittest.TestCase):
    def test_statistics_and_empty_data(self):
        self.assertIsNone(stats([])["median"])
        self.assertEqual(stats([1, 2, 3, math.nan])["median"], 2)
        self.assertAlmostEqual(stats([0, 10])["p95"], 9.5)

    def test_nonfinite_arguments_rejected(self):
        for x in ("nan", "inf", "0", "-2"):
            with self.assertRaises(ValueError):
                positive(x)

    def test_geometry_scale_invariance(self):
        pts = [types.SimpleNamespace(x=.5, y=.5) for _ in range(478)]
        for a, b, upper, lower, iris in EYES.values():
            for i, x, y in ((a, .4, .5), (b, .6, .5), (upper, .5, .48),
                            (lower, .5, .52), (iris, .55, .5)):
                pts[i] = types.SimpleNamespace(x=x, y=y)
        x = extract(pts, 1000, 500)
        y = extract(pts, 2000, 1000)
        self.assertAlmostEqual(x["right"]["iris_x"], .25)
        self.assertAlmostEqual(x["right"]["openness"], .1)
        self.assertEqual(x["left"]["iris_x"], y["left"]["iris_x"])
        self.assertEqual(y["right"]["width_px"], 2 * x["right"]["width_px"])
        pts[468].x = math.nan
        with self.assertRaises(ValueError):
            extract(pts, 1000, 500)

    def test_adapter_rejects_wrong_schema_and_degenerate_eyes(self):
        with self.assertRaises(ValueError):
            extract([], 640, 480)
        pts = [types.SimpleNamespace(x=.5, y=.5) for _ in range(478)]
        with self.assertRaises(ValueError):
            extract(pts, 640, 480)

    def test_private_atomic_json_and_no_nan(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "report.json"
            write_report(path, {"status": "recorded"})
            with self.assertRaises(ValueError):
                write_report(path, {"bad": math.nan})
            self.assertEqual(json.loads(path.read_text())["status"], "recorded")
            self.assertEqual(len(list(Path(folder).iterdir())), 1)

    def test_redaction(self):
        text = redact("Serial Number: ABC123\n/home/alice/project\nDriver: uvcvideo")
        self.assertNotIn("ABC123", text)
        self.assertNotIn("alice", text)
        self.assertIn("uvcvideo", text)

    def test_missing_executable_is_reported(self):
        self.assertEqual(command(["eyecheck-nonexistent-executable-57951"])["status"], "missing")

    def test_capture_failure_releases_device(self):
        class Capture:
            released = False
            def isOpened(self): return True
            def set(self, *args): return True
            def get(self, *args): return 0
            def read(self): return False, None
            def release(self): self.released = True
        cap = Capture()
        fake_cv = types.SimpleNamespace(VideoCapture=lambda *args: cap, CAP_V4L2=0,
            CAP_PROP_FRAME_WIDTH=1, CAP_PROP_FRAME_HEIGHT=2, CAP_PROP_FPS=3,
            CAP_PROP_BUFFERSIZE=4, CAP_PROP_FOURCC=5)
        args = types.SimpleNamespace(device="fake", fourcc=None, width=640, height=480,
                                     fps=30, warmup=1, seconds=1)
        c = LatestCapture(fake_cv, args)
        c.run()
        self.assertIn("read failed", c.error)
        self.assertTrue(cap.released)
        self.assertEqual(c.count, 0)

    def test_pause_before_first_move(self):
        sent = []
        async def move(x, y): sent.append((x, y))
        result, stopped = asyncio.run(sequence(move, lambda: True))
        self.assertTrue(stopped)
        self.assertEqual(result, [])
        self.assertEqual(sent, [])

    def test_pause_after_one_move(self):
        sent = []
        async def move(x, y): sent.append((x, y))
        result, stopped = asyncio.run(sequence(move, lambda: bool(sent), initial_delay=0, interval=0))
        self.assertTrue(stopped)
        self.assertEqual(len(result), 1)
        self.assertEqual(sent, [POINTS[0]])

    def test_pointer_requires_opt_in(self):
        args = parser().parse_args(["pointer", "--out", "unused.json"])
        self.assertFalse(args.enable_motion)
        with tempfile.TemporaryDirectory() as folder, patch("eyecheck.cli.platform.system", return_value="Linux"):
            out = Path(folder) / "error.json"
            self.assertEqual(main(["pointer", "--out", str(out)]), 1)
            self.assertIn("explicit", json.loads(out.read_text())["error"])

    def test_inventory_on_windows_never_certifies_linux(self):
        from eyecheck.inventory import inventory
        with patch("eyecheck.inventory.platform.system", return_value="Windows"):
            report = inventory()
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["native_absolute_input"], "NOT_TESTED")


if __name__ == "__main__":
    unittest.main()
