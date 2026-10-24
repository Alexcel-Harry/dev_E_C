import contextlib
import io
import json
import math
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

from eyecheck.cli import main
from eyecheck.features import EYES
from eyecheck.guided import DURATION, PHASES, PhaseResults, phase_at
from eyecheck.observations import observe
from eyecheck.preview import fit_size
from eyecheck.guided_ui import TARGETS, display_text, target_for, target_rect


def landmarks(openness=.2, iris_offset=(.05, 0)):
    points = [types.SimpleNamespace(x=.5, y=.5) for _ in range(478)]
    for name, (a, b, upper, lower, iris) in EYES.items():
        center = .3 if name == "right" else .7
        for index, x, y in ((a, center-.1, .5), (b, center+.1, .5),
                            (upper, center, .5-.1*openness), (lower, center, .5+.1*openness),
                            (iris, center+iris_offset[0], .5+iris_offset[1])):
            points[index] = types.SimpleNamespace(x=x, y=y)
    return points


def phase_start(name):
    start = 0
    for p in PHASES:
        if p.name == name:
            return start
        start += p.seconds
    raise AssertionError(name)


class ObservationTests(unittest.TestCase):
    def test_valid_geometry_scale_invariance(self):
        a = observe(landmarks(), 500, 500)
        b = observe(landmarks(), 1000, 1000)
        self.assertTrue(a["eyelids_valid"] and a["iris_valid"])
        self.assertAlmostEqual(a["eyes"]["right"]["iris_x"], .25)
        self.assertAlmostEqual(a["eyes"]["right"]["openness"], .2)
        self.assertEqual(a["eyes"]["right"]["iris_x"], b["eyes"]["right"]["iris_x"])

    def test_extreme_iris_does_not_invalidate_lids(self):
        points = landmarks(iris_offset=(0, .3))
        out = observe(points, 1000, 1000)
        self.assertTrue(out["eyelids_valid"])
        self.assertFalse(out["iris_valid"])
        self.assertIn("left:implausible_iris_position", out["reasons"])
        self.assertNotIn("iris_y", out["eyes"]["left"])

    def test_nonfinite_iris_preserves_closed_lid_measurement(self):
        points = landmarks(openness=0)
        points[468].x = math.nan
        points[473].y = math.inf
        out = observe(points, 1000, 1000)
        self.assertTrue(out["eyelids_valid"])
        self.assertFalse(out["iris_valid"])
        self.assertEqual(out["eyes"]["left"]["openness"], 0)
        json.dumps(out, allow_nan=False)

    def test_invalid_lid_does_not_produce_closed_measurement(self):
        points = landmarks()
        points[159].x = math.nan
        out = observe(points, 1000, 1000)
        self.assertFalse(out["eyelids_valid"])
        self.assertNotIn("openness", out["eyes"]["right"])
        self.assertFalse(out["iris_valid"])

    def test_no_face_and_wrong_schema_are_explicit(self):
        out = observe([], 1000, 1000)
        self.assertFalse(out["eyelids_valid"])
        self.assertFalse(out["face_present"])
        self.assertEqual(out["reasons"], ["no_face"])
        self.assertIn("unsupported_landmark_schema", observe(landmarks()[:468], 1000, 1000)["reasons"])

    def test_degenerate_and_impossible_lids_rejected(self):
        points = landmarks(openness=.8)
        self.assertFalse(observe(points, 1000, 1000)["eyelids_valid"])
        points = landmarks()
        points[33] = points[133]
        self.assertFalse(observe(points, 1000, 1000)["eyelids_valid"])

    def test_rotation_invariance(self):
        points = landmarks()
        expected = observe(points, 1000, 1000)
        angle = .2
        rotated = [types.SimpleNamespace(x=.5 + (p.x-.5)*math.cos(angle)-(p.y-.5)*math.sin(angle),
                                        y=.5 + (p.x-.5)*math.sin(angle)+(p.y-.5)*math.cos(angle)) for p in points]
        actual = observe(rotated, 1000, 1000)
        self.assertTrue(actual["iris_valid"])
        self.assertAlmostEqual(actual["eyes"]["right"]["iris_x"], expected["eyes"]["right"]["iris_x"])


class GuidedTests(unittest.TestCase):
    def test_buffers_exclude_observations_at_both_edges(self):
        results = PhaseResults()
        good = observe(landmarks(), 1000, 1000)
        missing = observe([], 1000, 1000)
        # Center: [0,1) excluded, [1,7) measured, [7,8) excluded.
        for t, observation in ((.999, missing), (1, good), (6.999, good), (7, missing), (7.999, missing)):
            results.add(t, observation, 10)
        row = results.report(8)["phases"][0]
        self.assertEqual((row["settling_frames"], row["frames"], row["trailing_frames"]), (1, 2, 2))
        self.assertEqual(row["face_fraction"], 1)
        self.assertEqual(row["reasons"], {})
        self.assertEqual(row["metrics"]["right_openness"]["n"], 2)
        self.assertEqual(row["observed_window_seconds"], 6)
        self.assertEqual(results.report(7.5)["phases"][0]["observed_window_seconds"], 6)
        self.assertEqual(row["measurement_start_seconds"], 1)
        self.assertEqual(row["measurement_end_seconds"], 7)

    def test_all_phases_have_two_buffers_and_positive_measurement_windows(self):
        for phase in PHASES:
            self.assertEqual((phase.settle, phase.tail), (1, 1))
            self.assertGreaterEqual(phase.seconds - phase.settle - phase.tail, 2)
            self.assertEqual(phase.window(.99), "settling")
            self.assertEqual(phase.window(1), "measuring")
            self.assertEqual(phase.window(phase.seconds - 1), "trailing")
        closure = next(p for p in PHASES if p.name == "closure_1")
        self.assertEqual(closure.seconds, 4)

    def test_target_cards_follow_direction_and_stay_on_screen(self):
        for width, height in ((1648, 1030), (1280, 720), (800, 600)):
            for name, target in TARGETS.items():
                x, y, w, h = target_rect(width, height, target_for(name))
                self.assertGreaterEqual(min(x, y), 0)
                self.assertLessEqual(x + w, width)
                self.assertLessEqual(y + h, height)
                self.assertAlmostEqual((x + w/2) / width, target[0], delta=.001)
                self.assertAlmostEqual((y + h/2) / height, target[1], delta=.001)
        self.assertEqual(target_for("closure_1"), TARGETS["center"])
        phase = next(p for p in PHASES if p.name == "left")
        self.assertIn("Look HERE", display_text(phase, 2))
        self.assertIn("Measuring", display_text(phase, 2))
        self.assertIn("Keep holding - samples excluded", display_text(phase, 4))

    def test_phase_boundaries(self):
        self.assertEqual(DURATION, 116)
        self.assertIsNone(phase_at(-1))
        self.assertEqual(phase_at(7.99)[1].name, "center")
        self.assertEqual(phase_at(8)[1].name, "left")
        self.assertIsNone(phase_at(DURATION))

    def test_settling_and_no_face_counted_separately(self):
        results = PhaseResults()
        results.add(.5, observe(landmarks(), 1000, 1000), 10)
        results.add(1.1, observe([], 1000, 1000), 10)
        row = results.report(2)["phases"][0]
        self.assertEqual(row["settling_frames"], 1)
        self.assertEqual(row["frames"], 1)
        self.assertEqual(row["eyelid_fraction"], 0)
        self.assertNotIn("right_openness", row["metrics"])
        self.assertEqual(row["status"], "partial")
        self.assertEqual(results.report(2)["phases"][1]["status"], "not_reached")

    def test_closed_lids_and_absent_face_are_not_conflated(self):
        results = PhaseResults()
        for i in range(10):
            results.add(phase_start("prepare_closure_1") + 1 + i*.1, observe(landmarks(), 1000, 1000), 10)
            results.add(phase_start("closure_1") + 1 + i*.1, observe(landmarks(openness=.02), 1000, 1000), 10)
            results.add(phase_start("face_loss") + 1 + i*.1, observe([], 1000, 1000), 10)
        report = results.report(DURATION)
        ratio = report["comparisons"]["closure_to_open_openness_ratio"]["closure_1"]["right"]
        self.assertAlmostEqual(ratio, .1)
        loss = next(p for p in report["phases"] if p["phase"] == "face_loss")
        self.assertEqual(loss["face_fraction"], 0)
        self.assertNotIn("right_openness", loss["metrics"])
        self.assertIsNone(report["comparisons"]["closure_to_open_openness_ratio"]["closure_2"]["right"])
        json.dumps(report, allow_nan=False)

    def test_incomplete_phase_cannot_supply_comparison(self):
        results = PhaseResults()
        for i in range(6):
            results.add(1+i*.1, observe(landmarks(), 1000, 1000), 10)
        report = results.report(2)
        self.assertIsNone(report["comparisons"]["direction_deltas_from_center"]["left"]["right_iris_x"])

    def test_per_phase_gaps_do_not_cross_phase_boundary(self):
        results = PhaseResults()
        for t in (1.0, 1.3, 9.1, 9.2):
            results.add(t, observe(landmarks(), 1000, 1000), 10)
        report = results.report(14)
        self.assertAlmostEqual(report["phases"][0]["metrics"]["iris_gap_ms"]["max"], 300)
        self.assertAlmostEqual(report["phases"][1]["metrics"]["iris_gap_ms"]["max"], 100)

    def test_letterbox_dimensions_preserve_ratio(self):
        self.assertEqual(fit_size(100, 25, 400, 180), (400, 100))
        self.assertEqual(fit_size(25, 100, 400, 180), (45, 180))
        with self.assertRaises(ValueError):
            fit_size(0, 100, 400, 180)

    def test_guided_dispatch_and_fixed_duration(self):
        with tempfile.TemporaryDirectory() as folder:
            model = Path(folder) / "test.task"
            model.write_bytes(b"stub")
            with patch("eyecheck.cli.platform.system", return_value="Linux"), patch("eyecheck.guided_run.run", return_value=0) as run:
                self.assertEqual(main(["guided", "--device", "/dev/video0", "--model", str(model),
                                       "--out", str(Path(folder)/"out.json"), "--worker"]), 0)
            self.assertEqual(run.call_args.args[0].seconds, DURATION)
            self.assertFalse(run.call_args.args[0].preview)

    def test_guided_rejects_missing_model_and_preserves_existing_output(self):
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stderr(io.StringIO()):
            out = Path(folder)/"out.json"
            out.write_text("KEEP")
            for extra in ([], ["--model", "unused.task"], ["--model", "unused.task", "--seconds", "10"]):
                with self.assertRaises(SystemExit):
                    main(["guided", "--device", "/dev/video0", "--out", str(out), *extra])
                self.assertEqual(out.read_text(), "KEEP")


if __name__ == "__main__":
    unittest.main()
