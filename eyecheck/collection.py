"""Collection protocol and session-only calibration. No GUI, camera or input APIs."""
from dataclasses import asdict, dataclass
import math
import random

PROTOCOL = "eyecheck-collection-pilot-v1"
PATTERNS = ("S", "SS", "SSS", "L", "SL")
CORNERS = ((.05, .05), (.95, .05), (.95, .95), (.05, .95))


@dataclass(frozen=True)
class Step:
    role: str
    label: str
    target: tuple = (.5, .5)
    seconds: float = 1.5
    block: str = ""
    review: bool = False
    condition: str = "neutral"


def schedule(seed, trials=5, reading_seconds=180, include_ll=False, head_pose=False, tracking=False):
    """Independent deterministic random streams; preserve schedule in the manifest."""
    steps = [Step("calibration_anchor", name, point, 2, "corners")
             for name, point in zip(("top_left", "top_right", "bottom_right", "bottom_left"), CORNERS)]
    steps.append(Step("calibration_check", "center", review=True))
    grid = [(round(.05 + .225 * x, 8), round(.05 + .225 * y, 8)) for y in range(5) for x in range(5)]
    random.Random(seed).shuffle(grid)
    rng = random.Random(seed + 1)
    jitter = [(.05 + .18 * (x + rng.random()), .05 + .18 * (y + rng.random()))
              for y in range(5) for x in range(5)]
    rng.shuffle(jitter)
    for name, points in (("grid", grid), ("jitter", jitter)):
        steps.extend(Step("gaze_target", f"{name}_{i+1:02}", point, block=name, review=i == 24)
                     for i, point in enumerate(points))
    steps.extend((Step("gesture_reference", "open", seconds=3, review=True),
                  Step("gesture_reference", "closed", seconds=2, review=True)))
    patterns = list(PATTERNS) * trials + (["LL"] * 2 if include_ll else [])
    random.Random(seed + 2).shuffle(patterns)
    duration = {"S": 5, "SS": 6, "SSS": 7, "L": 6, "SL": 8, "LL": 9}
    steps.extend(Step("gesture_trial", p, seconds=duration[p], review=True) for p in patterns)
    steps.append(Step("negative_reading", "ordinary_reading", seconds=reading_seconds, review=True))
    if head_pose:
        steps.insert(0, Step("pose_reference", "neutral", seconds=2, review=True))
        grid9 = [(x, y) for y in (.15, .5, .85) for x in (.15, .5, .85)]
        additions = []
        for condition in ("neutral", "turn_left", "turn_right", "nod_up", "nod_down", "natural", "fixation_head_motion"):
            points = grid9.copy()
            random.Random(seed + 20 + len(additions)).shuffle(points)
            additions.extend(Step("gaze_target", f"{condition}_{i}", p, seconds=4 if condition == "fixation_head_motion" else 1.5,
                                  block=condition, review=True, condition=condition) for i, p in enumerate(points))
        steps[56:56] = additions
        if tracking:
            steps = steps[:6] + [Step("tracking", "practice", seconds=600, review=True)]
    return steps


def gaze_features(observation):
    if not observation.get("iris_valid"):
        return None
    values = []
    for name in ("left", "right"):
        eye = observation.get("eyes", {}).get(name, {})
        values.extend((eye.get("iris_x"), eye.get("iris_y")))
    return values if all(isinstance(v, (int, float)) and math.isfinite(v) for v in values) else None


def fit_anchors(anchors):
    """Four median summaries, equal weight; center/main targets cannot enter this fit."""
    import numpy as np
    if len(anchors) != 4 or any(a["role"] != "calibration_anchor" for a in anchors):
        raise ValueError("Exactly four designated anchors are required")
    if [tuple(a["target"]) for a in anchors] != list(CORNERS):
        raise ValueError("Anchors must follow the specified corner order")
    if any(len(a["samples"]) < 20 for a in anchors):
        raise ValueError("Each corner requires at least 20 eligible frames")
    medians = np.array([np.median(a["samples"], axis=0) for a in anchors])
    targets = np.array(CORNERS)
    result = {"method": "per_eye_affine_four_equal_weight_medians", "eyes": {},
              "anchor_medians": medians.tolist(), "targets": targets.tolist(),
              "anchor_attempt_ids": [a.get("id") for a in anchors],
              "anchor_sample_counts_at_fit": [len(a["samples"]) for a in anchors],
              "anchor_read_timestamps_used": [list(a.get("sample_read_times", [])) for a in anchors]}
    for i, name in enumerate(("left", "right")):
        x = np.column_stack((medians[:, 2*i:2*i+2], np.ones(4)))
        if not np.isfinite(x).all() or np.linalg.matrix_rank(x) < 3:
            raise ValueError(f"{name} corner geometry is degenerate; recalibrate in a fresh session")
        weights, _, _, _ = np.linalg.lstsq(x, targets, rcond=None)
        result["eyes"][name] = {"weights_3x2": weights.tolist(),
                                "condition_number": float(np.linalg.cond(x)),
                                "anchor_rmse_normalized": float(np.sqrt(np.mean((x @ weights-targets)**2)))}
    return result


def predict(calibration, features):
    predictions = []
    for i, name in enumerate(("left", "right")):
        row = (*features[2*i:2*i+2], 1)
        w = calibration["eyes"][name]["weights_3x2"]
        predictions.append([sum(row[k] * w[k][j] for k in range(3)) for j in range(2)])
    return [sum(p[j] for p in predictions) / 2 for j in range(2)]  # deliberately unclamped


class Protocol:
    """Paint-acknowledged phases; observations are assigned by read-completion time.

    Invalidated attempts remain in the ledger. Consumers must join final attempt
    status; row-level eligibility alone is not a training inclusion decision.
    """
    def __init__(self, steps, emit=lambda row: None, head_pose=False, model=None):
        self.steps, self.emit = steps, emit
        self.index = 0
        self.state = "setup"
        self.version = 0
        self.pending_paint = False
        self.phase_start = None
        self.spans = []
        self.contexts = []
        self.attempts = []
        self.current = None
        self.calibration = None
        self.head_pose = head_pose
        self.pose_reference = None
        self.model = model
        self.smoother = None
        if model:
            from .gaze_model import Smoother
            self.smoother = Smoother()
        self.latest_prediction = None
        self.message = "Check the preview and setup; press Space when ready."
        self.completed = False

    @property
    def step(self):
        return self.steps[self.index]

    def event(self, kind, now, **fields):
        self.emit({"event": kind, "monotonic_s": now, **fields})

    def transition(self, state, now):
        # End the previous labeling interval immediately on a control transition.
        if self.spans and self.spans[-1]["end"] is None:
            self.spans[-1]["end"] = now
        self.state, self.phase_start = state, None
        self.version += 1
        self.pending_paint = state in ("prepare", "measure")
        self.contexts.append({"start": now, "phase": state, "step_index": self.index,
                              "attempt_id": self.current["id"] if self.current else None})
        self.event("state", now, state=state, step_index=self.index,
                   attempt_id=self.current["id"] if self.current else None, version=self.version)

    def painted(self, version, now, display):
        if version != self.version or not self.pending_paint:
            return
        self.pending_paint, self.phase_start = False, now
        span = {"start": now, "end": None, "phase": self.state,
                "attempt_id": self.current["id"], "step_index": self.index,
                "limit": 2 if self.state == "prepare" else (4 if self.step.role == "calibration_anchor" else self.step.seconds)}
        self.spans.append(span)
        self.event("paint_ack", now, **span, display=display)

    def begin(self, now):
        if self.step.role == "pose_reference":
            self.pose_reference = None
        self.current = {"id": len(self.attempts) + 1, "step_index": self.index,
                        **asdict(self.step), "status": "active", "samples": [], "sample_read_times": [],
                        "poses": [], "frames": 0, "lid_frames": 0, "confirmed_pattern": None,
                        "confirmation_source": None}
        self.attempts.append(self.current)
        self.transition("prepare", now)

    def invalidate(self, now, reason):
        if self.current:
            self.current["status"] = "invalidated"
            self.current["invalidation_reason"] = reason
            self.event("attempt_invalidated", now, attempt_id=self.current["id"], reason=reason)

    def pause(self, now, reason="user"):
        if self.state in ("prepare", "measure"):
            self.invalidate(now, reason)
            self.transition("paused", now)
            self.message = "Paused. Space restarts this item with 2 seconds preparation. Setup changed? Stop and start a new session."

    def confirm(self, now, confirmation):
        allowed = (set(PATTERNS) | {"LL", "uncertain", "failed"} if self.step.role == "gesture_trial" else
                   {"open", "closed", "uncertain", "failed"} if self.step.role == "gesture_reference" else
                   {"no_command", "commands_present", "uncertain"})
        if confirmation not in allowed:
            raise ValueError("Unknown user confirmation for this role")
        self.current.update(confirmed_pattern=confirmation, confirmation_source="user_after_trial")
        self.event("confirmation", now, attempt_id=self.current["id"],
                   prompted_pattern=self.step.label, confirmed_pattern=confirmation, source="user_after_trial")

    def repeat(self, now, confirmation=None):
        if self.state in ("review", "retry"):
            if confirmation is not None and self.step.role in ("gesture_trial", "gesture_reference", "negative_reading"):
                self.confirm(now, confirmation)
            self.invalidate(now, "user_repeat")
            self.begin(now)
        elif self.state in ("prepare", "measure") and self.step.role == "gaze_target":
            self.invalidate(now, "user_repeat")
            if self.state == "prepare" and self.index > 0 and self.steps[self.index-1].block == self.step.block:
                self.index -= 1
                previous = next(a for a in reversed(self.attempts) if a["step_index"] == self.index and a["status"] == "recorded")
                previous.update(status="invalidated", invalidation_reason="repeat_previous_target")
                self.event("attempt_invalidated", now, attempt_id=previous["id"], reason="repeat_previous_target")
            self.begin(now)

    def advance(self, now, confirmation=None):
        if self.state in ("setup", "paused"):
            self.begin(now)
        elif self.state == "retry":
            self.repeat(now)
        elif self.state == "review":
            if self.step.role in ("gesture_trial", "gesture_reference", "negative_reading"):
                if confirmation is None:
                    return  # A prompt is never its own ground truth.
                self.confirm(now, confirmation)
            if self.step.role == "calibration_check":
                self.current["readiness_accepted_by_user"] = True
            self.next(now)

    def next(self, now):
        self.index += 1
        if self.index == len(self.steps):
            self.index -= 1
            self.completed = True
            self.transition("complete", now)
        else:
            self.begin(now)

    def assign(self, captured):
        for span in reversed(self.spans):
            end = min(span["end"] if span["end"] is not None else math.inf,
                      span["start"] + span["limit"])
            if span["start"] <= captured < end:
                return span
        return None

    def observation(self, captured, inference_end, observation):
        span = self.assign(captured)
        context = next((c for c in reversed(self.contexts) if c["start"] <= captured), None)
        features = gaze_features(observation)
        head = observation.get("head_pose", {})
        pose_ok = not self.head_pose or head.get("valid", False)
        delta = None
        if self.head_pose and pose_ok and self.pose_reference:
            from .head_pose import relative
            delta = relative(head, self.pose_reference)
            if span and self.steps[span["step_index"]].role == "calibration_anchor":
                pose_ok = max(abs(v) for v in delta[:3]) <= 8 and max(abs(v) for v in delta[3:5]) <= .04 and abs(delta[5]) <= .1
        if not pose_ok:
            features = None
        self.latest_prediction = None
        fresh = 0 <= inference_end - captured <= .25
        row = {"read_completed_monotonic_s": captured, "inference_end_monotonic_s": inference_end,
               "phase": span["phase"] if span else "unscored", "attempt_id": (span or context or {}).get("attempt_id"),
               "role": self.steps[(span or context)["step_index"]].role if span or context else "setup",
               "condition": self.steps[(span or context)["step_index"]].condition if span or context else "setup",
               "relative_pose": delta, "pose_eligible": bool(pose_ok),
               "context_phase": context["phase"] if context else "setup",
               "fresh_within_250ms": fresh, "gaze_eligible": False, "observation": observation}
        if span:
            attempt = self.attempts[span["attempt_id"] - 1]
            measuring = span["phase"] == "measure"
            gaze_role = attempt["role"] in ("pose_reference", "calibration_anchor", "calibration_check", "gaze_target")
            row.update(target_normalized=attempt["target"] if gaze_role else None,
                       prompted_pattern=attempt["label"] if attempt["role"].startswith("gesture") else None)
            row["gaze_eligible"] = bool(measuring and gaze_role and fresh and features is not None)
            if measuring:
                attempt["frames"] += 1
                if fresh and features is not None and head.get("valid"):
                    attempt["poses"].append(head)
                attempt["lid_frames"] += int(observation.get("eyelids_valid", False) and fresh)
                if row["gaze_eligible"]:
                    attempt["samples"].append(features)
                    attempt["sample_read_times"].append(captured)
                    if self.calibration:
                        row["session_gaze_normalized"] = predict(self.calibration, features)
        if self.model and self.calibration and delta is not None and features is not None and fresh:
            from .gaze_model import estimate
            self.latest_prediction = estimate(self.model, self.calibration, features, delta)
            row["joint_gaze"] = self.latest_prediction
            self.latest_prediction = self.smoother.update(self.latest_prediction, captured)
        elif self.smoother:
            self.smoother.update(None, captured)
        return row

    def tick(self, now):
        if self.pending_paint or self.phase_start is None:
            return
        elapsed = now - self.phase_start
        if self.state == "prepare" and elapsed >= 2:
            self.transition("measure", now)
        elif self.state == "measure" and elapsed >= self.step.seconds:
            if self.step.role == "calibration_anchor" and len(self.current["samples"]) < 20 and elapsed < 4:
                return
            self.finish(now)

    def finish(self, now):
        a = self.current
        gaze_role = self.step.role in ("pose_reference", "calibration_anchor", "calibration_check", "gaze_target")
        minimum = 20 if self.step.role in ("pose_reference", "calibration_anchor") else 10
        if (gaze_role and len(a["samples"]) < minimum) or (not gaze_role and a["lid_frames"] < 5):
            a["status"] = "insufficient"
            self.message = f"Insufficient usable observations: {len(a['samples'])} gaze / {a['lid_frames']} eyelid frames. R or Space retries; Escape stops."
            self.transition("retry", now)
            return
        if self.step.role == "pose_reference":
            from .head_pose import reference
            try:
                self.pose_reference = reference(a["poses"])
            except ValueError as exc:
                self.message = str(exc)
                self.transition("retry", now)
                return
            self.event("pose_reference", now, reference=self.pose_reference)
        a["status"] = "recorded"
        if self.step.role == "calibration_anchor" and self.step.target == CORNERS[-1]:
            anchors = [v for v in self.attempts if v["role"] == "calibration_anchor" and v["status"] == "recorded"]
            self.calibration = fit_anchors(anchors)
            self.event("calibration_fit", now, calibration=self.calibration)
        if self.step.role == "calibration_check":
            import statistics
            errors = [math.dist(predict(self.calibration, f), (.5, .5)) for f in a["samples"]]
            a["median_error_normalized"] = statistics.median(errors)
            self.message = (f"Center check: median error {a['median_error_normalized']:.3f} in normalized screen coordinates. "
                            "Pilot diagnostic, not an accuracy pass. Space accepts and starts gaze collection; R repeats; Escape stops to recalibrate.")
        elif self.step.role in ("pose_reference", "tracking"):
            self.message = "Reference/tracking block complete. Space continues; R repeats."
        elif self.step.role == "gaze_target":
            block = [v for v in self.attempts if v["block"] == self.step.block and v["status"] == "recorded"]
            self.message = f"Break: {self.step.block} finished ({len(block)} targets, {sum(len(v['samples']) for v in block)} eligible frames). Space continues; R repeats the last target."
        elif self.step.role == "negative_reading":
            self.message = "Confirm whether you read normally without intentional commands. Natural blinks are expected."
        else:
            self.message = f"Prompt was {self.step.label}. Confirm what you actually performed, or mark uncertain/failed."
        if self.step.review:
            self.transition("review", now)
        else:
            self.next(now)

    def stop(self, now):
        if not self.completed:
            if self.current and self.current["status"] == "active":
                self.current["status"] = "interrupted"
            self.transition("stopped", now)

    def summary(self):
        confirmed = {p: sum(a["role"] == "gesture_trial" and a["status"] == "recorded" and
                            a["label"] == p and a["confirmed_pattern"] == p for a in self.attempts)
                     for p in PATTERNS}
        return {"completed": self.completed, "calibration": self.calibration, "pose_reference": self.pose_reference,
                "confirmed_matching_core_trials": confirmed,
                "gesture_quota_met": all(confirmed[p] >= sum(s.role == "gesture_trial" and s.label == p for s in self.steps) for p in PATTERNS),
                "negative_reading_confirmed": any(a["role"] == "negative_reading" and a["status"] == "recorded" and a["confirmed_pattern"] == "no_command" for a in self.attempts),
                "attempts": [{k: v for k, v in a.items() if k not in ("samples", "sample_read_times", "poses")} |
                             {"eligible_gaze_frames": len(a["samples"])} for a in self.attempts],
                "note": "Recorded and user-confirmed do not establish true fixation or blink timing. Join attempt status before training."}
