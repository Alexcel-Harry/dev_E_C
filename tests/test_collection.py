"""Synthetic protocol tests: chronology, calibration leakage, data roles and retention."""
from collections import Counter
from contextlib import redirect_stdout, redirect_stderr
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from eyecheck.collection import CORNERS, PATTERNS, Protocol, Step, fit_anchors, predict, schedule
from eyecheck.collection_store import SessionStore, mark_interrupted, reserve
from eyecheck.cli import main


def observation(x=.5, y=.5, closed=False):
    return {"face_present": True, "iris_valid": not closed, "eyelids_valid": True,
            "eyes": {name: {"iris_x": x, "iris_y": y, "openness": .01 if closed else .2,
                            "iris_valid": not closed, "eyelids_valid": True} for name in ("left", "right")}}


class ProtocolTests(unittest.TestCase):
    def measuring(self, steps=None):
        p = Protocol(steps or [Step("gaze_target", "a", review=True)])
        p.advance(0)
        p.painted(p.version, 1, {})
        p.tick(3)
        p.painted(p.version, 3.1, {})
        return p

    def feed(self, p, closed=False, count=25):
        for i in range(count):
            t = p.phase_start + .01 + i * .04
            p.observation(t, t+.01, observation(*p.step.target, closed=closed))

    def test_plan_counts_independent_seeds_and_bounds(self):
        a, b = schedule(10), schedule(11)
        self.assertEqual(a, schedule(10))
        self.assertNotEqual(a[5:55], b[5:55])
        self.assertEqual([s.target for s in a[:4]], list(CORNERS))
        self.assertEqual(Counter(s.label for s in a if s.role == "gesture_trial"), {p: 5 for p in PATTERNS})
        self.assertEqual(len([s for s in a if s.role == "gaze_target"]), 50)
        self.assertTrue(all(.05 <= v <= .95 for s in a for v in s.target))
        self.assertEqual(a[-1].seconds, 180)
        self.assertEqual(sum(s.label == "LL" for s in schedule(10, include_ll=True)), 2)

    def test_preparation_starts_at_paint_not_dispatch(self):
        p = Protocol([Step("gaze_target", "a")])
        p.advance(0)
        p.tick(50)
        self.assertEqual(p.state, "prepare")
        p.painted(p.version-1, 50, {})
        self.assertTrue(p.pending_paint)
        p.painted(p.version, 51, {})
        p.tick(52.9)
        self.assertEqual(p.state, "prepare")
        p.tick(53)
        self.assertEqual(p.state, "measure")
        self.assertIsNone(p.assign(53))  # not yet painted; no measurement label

    def test_late_result_uses_acquisition_phase_and_hard_end(self):
        p = self.measuring()
        row = p.observation(3.0, 3.15, observation())
        self.assertFalse(row["gaze_eligible"])
        self.assertIsNone(p.assign(4.6))
        row = p.observation(3.2, 3.3, observation())
        self.assertTrue(row["gaze_eligible"])
        row = p.observation(3.3, 3.6, observation())
        self.assertFalse(row["gaze_eligible"])

    def test_late_result_after_next_target_still_points_to_previous(self):
        p = self.measuring([Step("gaze_target", "a"), Step("gaze_target", "b")])
        self.feed(p)
        p.tick(4.61)
        self.assertEqual(p.index, 1)
        row = p.observation(4.5, 4.62, observation())
        self.assertEqual(row["attempt_id"], 1)
        self.assertEqual(len(p.attempts[0]["samples"]), 26)
        self.assertEqual(len(p.current["samples"]), 0)

    def test_closed_eye_trace_retained_but_not_gaze_training(self):
        p = self.measuring([Step("gesture_trial", "S", seconds=5, review=True)])
        row = p.observation(3.2, 3.22, observation(closed=True))
        self.assertEqual(row["role"], "gesture_trial")
        self.assertFalse(row["gaze_eligible"])
        self.assertEqual(row["observation"]["eyes"]["left"]["openness"], .01)
        self.assertEqual(p.current["lid_frames"], 1)

    def test_pause_invalidates_and_resume_restarts_preparation(self):
        p = self.measuring()
        self.feed(p, count=5)
        p.pause(3.4)
        self.assertIsNone(p.assign(3.4))
        self.assertEqual(p.current["status"], "invalidated")
        p.advance(10)
        self.assertEqual(p.state, "prepare")
        self.assertEqual(p.current["id"], 2)
        self.assertEqual(p.current["samples"], [])

    def test_corner_extends_then_requires_retry(self):
        p = self.measuring([Step("calibration_anchor", "a", CORNERS[0], seconds=2)])
        self.feed(p, count=19)
        p.tick(5.2)
        self.assertEqual(p.state, "measure")
        p.tick(7.2)
        self.assertEqual(p.state, "retry")
        p.advance(8)
        self.assertEqual(p.current["id"], 2)
        self.assertEqual(p.attempts[0]["status"], "invalidated")

    def test_explicit_confirmation_not_prompt_or_detector(self):
        p = self.measuring([Step("gesture_trial", "SSS", seconds=7, review=True)])
        self.feed(p, closed=True)
        p.tick(10.2)
        self.assertEqual(p.state, "review")
        self.assertIsNone(p.current["confirmed_pattern"])
        p.advance(11)
        self.assertFalse(p.completed)
        p.advance(12, "SS")
        self.assertTrue(p.completed)
        self.assertEqual(p.current["confirmed_pattern"], "SS")
        self.assertFalse(p.summary()["gesture_quota_met"])
        self.assertEqual(p.summary()["confirmed_matching_core_trials"]["SSS"], 0)

    def test_repeated_trial_retains_original_confirmation(self):
        p = self.measuring()
        self.feed(p)
        p.tick(4.7)
        p.repeat(5)
        self.assertEqual(len(p.attempts), 2)
        self.assertEqual(p.attempts[0]["status"], "invalidated")
        self.assertEqual(len(p.attempts[0]["samples"]), 25)
        p.stop(5.5)
        self.assertEqual(p.current["status"], "interrupted")

    def test_unscored_trial_gap_keeps_context_without_claiming_measurement(self):
        p = self.measuring([Step("gesture_trial", "S", seconds=5, review=True)])
        self.feed(p)
        p.tick(8.2)
        row = p.observation(8.3, 8.4, observation())
        self.assertEqual((row["phase"], row["context_phase"], row["role"]), ("unscored", "review", "gesture_trial"))
        self.assertFalse(row["gaze_eligible"])

    def test_repeat_gesture_can_save_correction_before_invalidating(self):
        p = self.measuring([Step("gesture_trial", "SSS", seconds=7, review=True)])
        self.feed(p)
        p.tick(10.2)
        p.repeat(11, "SS")
        self.assertEqual(p.attempts[0]["confirmed_pattern"], "SS")
        self.assertEqual(p.attempts[0]["status"], "invalidated")
        self.assertIsNone(p.current["confirmed_pattern"])

    def test_repeat_previous_during_next_gaze_preparation(self):
        p = self.measuring([Step("gaze_target", "a", block="grid"), Step("gaze_target", "b", block="grid")])
        self.feed(p)
        p.tick(4.61)
        p.repeat(4.7)
        self.assertEqual(p.index, 0)
        self.assertEqual(p.current["id"], 3)
        self.assertEqual([a["status"] for a in p.attempts], ["invalidated", "invalidated", "active"])

    def test_full_campaign_with_synthetic_time_and_features(self):
        events = []
        p = Protocol(schedule(4, trials=1, reading_seconds=10), events.append)
        now = 1
        p.advance(now)
        while not p.completed:
            self.assertEqual(p.state, "prepare")
            p.painted(p.version, now, {})
            now += 2.001
            p.tick(now)
            p.painted(p.version, now, {})
            self.feed(p, closed=p.step.label == "closed")
            now += p.step.seconds + .001
            p.tick(now)
            if p.state == "review":
                confirmation = "no_command" if p.step.role == "negative_reading" else p.step.label
                p.advance(now, confirmation)
        self.assertEqual(len(p.attempts), len(p.steps))
        self.assertTrue(p.summary()["gesture_quota_met"])
        self.assertTrue(p.summary()["negative_reading_confirmed"])
        self.assertEqual(len([e for e in events if e["event"] == "calibration_fit"]), 1)
        self.assertLess(p.attempts[4]["median_error_normalized"], 1e-12)


class CalibrationTests(unittest.TestCase):
    def anchors(self):
        return [{"role": "calibration_anchor", "target": p,
                 "samples": [[2*p[0]+1, 3*p[1]-2, p[0]*4-1, p[1]*2+2]]*20} for p in CORNERS]

    def test_affine_prediction_and_no_clamping(self):
        c = fit_anchors(self.anchors())
        self.assertAlmostEqual(predict(c, [2, -.5, 1, 3])[0], .5)
        self.assertAlmostEqual(predict(c, [2, -.5, 1, 3])[1], .5)
        self.assertAlmostEqual(predict(c, [5, -.5, 7, 3])[0], 2)

    def test_center_or_missing_anchor_cannot_enter_fit(self):
        a = self.anchors()
        a[3]["role"] = "calibration_check"
        with self.assertRaises(ValueError):
            fit_anchors(a)
        with self.assertRaises(ValueError):
            fit_anchors(a[:3])

    def test_degenerate_geometry_rejected(self):
        a = self.anchors()
        for anchor in a:
            anchor["samples"] = [[1, 1, 1, 1]] * 20
        with self.assertRaises(ValueError):
            fit_anchors(a)

    def test_summary_medians_resist_one_outlier_and_unequal_counts(self):
        a = self.anchors()
        a[0]["samples"] = a[0]["samples"]*5 + [[100, 100, 100, 100]]
        c = fit_anchors(a)
        self.assertAlmostEqual(predict(c, [2, -.5, 1, 3])[0], .5)


class StorageAndCLITests(unittest.TestCase):
    def test_exclusive_storage_hashes_and_partial_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/"session"
            store = SessionStore(path, {"split": "pilot"})
            store.append("observations", {"frame_id": 1})
            with self.assertRaises(FileExistsError):
                SessionStore(path, {})
            with self.assertRaises(ValueError):
                store.append("observations", {"bad": float("nan")})
            store.finish("incomplete", reason="user_stop")
            manifest = json.loads((path/"manifest.json").read_text())
            self.assertEqual(manifest["status"], "incomplete")
            self.assertEqual(manifest["file_sha256"]["observations.jsonl"], hashlib.sha256((path/"observations.jsonl").read_bytes()).hexdigest())
            self.assertEqual(len((path/"observations.jsonl").read_text().splitlines()), 1)
            if os.name == "posix":
                self.assertEqual(path.stat().st_mode & 0o777, 0o700)
                self.assertEqual((path/"observations.jsonl").stat().st_mode & 0o777, 0o600)

    def test_reservation_and_interrupted_child_preserve_records(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {"XDG_STATE_HOME": folder}):
            path = reserve({"seed": 3})
            store = SessionStore(path, {}, resume_reserved=True)
            store.append("events", {"event": "test"})
            store.finish("error")
            mark_interrupted(path, "test crash")
            self.assertEqual(json.loads((path/"manifest.json").read_text())["status"], "incomplete")
            self.assertEqual(json.loads((path/"events.jsonl").read_text())["event"], "test")
            with self.assertRaises(ValueError):
                SessionStore(path, {}, resume_reserved=True)

    def test_offline_plan_needs_no_camera_or_optional_imports(self):
        output = io.StringIO()
        with redirect_stdout(output):
            code = main(["collect", "--plan", "--seed", "42"])
        plan = json.loads(output.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(len(plan["steps"]), 83)
        self.assertEqual(plan["seed"], 42)

    def test_cli_rejects_nonfinite_and_nonpilot_budget_override(self):
        for args in (["--fps", "nan"], ["--warmup", "inf"], ["--reading-seconds", "0"],
                     ["--split", "test", "--trials-per-pattern", "1"]):
            with redirect_stderr(io.StringIO()):
                self.assertEqual(main(["collect", "--plan", *args]), 1)


if __name__ == "__main__":
    unittest.main()
