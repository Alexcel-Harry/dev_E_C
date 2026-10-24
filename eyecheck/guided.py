"""Timed diagnostic protocol. Aggregates only; no blink events or gaze model."""
from collections import Counter, defaultdict
from dataclasses import dataclass
from .common import stats


@dataclass(frozen=True)
class Phase:
    name: str
    seconds: float
    instruction: str
    settle: float = 1.0


PHASES = [
    Phase("center", 8, "Look at the center of the screen. Keep your head comfortably still."),
    Phase("left", 5, "Move only your eyes toward the LEFT side of the screen. Do not strain."),
    Phase("center_after_left", 3, "Look back at the CENTER."),
    Phase("right", 5, "Move only your eyes toward the RIGHT side of the screen."),
    Phase("center_after_right", 3, "Look back at the CENTER."),
    Phase("up", 5, "Move only your eyes toward the TOP of the screen."),
    Phase("center_after_up", 3, "Look back at the CENTER."),
    Phase("down", 5, "Move only your eyes toward the BOTTOM of the screen."),
    Phase("center_after_down", 5, "Look back at the CENTER."),
    Phase("natural_blinks", 15, "Look naturally at the screen and blink normally. Do not force blinks."),
]
for i in range(1, 4):
    PHASES.extend([
        Phase(f"prepare_closure_{i}", 4, "Keep eyes OPEN. Next: close gently for TWO seconds, then reopen. No squeezing."),
        Phase(f"closure_{i}", 2, "CLOSE gently now. Count two seconds, then OPEN. A beep also marks reopening.", .5),
        Phase(f"reopen_{i}", 4, "OPEN both eyes and look at the center."),
    ])
PHASES.extend([
    Phase("prepare_face_loss", 4, "Next: move your FACE out of camera view for THREE seconds, then return."),
    Phase("face_loss", 3, "Move out of camera view now. Count three seconds, then return.", .5),
    Phase("return", 6, "Return to your original position. Look at the center."),
    Phase("final_center", 6, "Look at the center with eyes open. Finishing shortly."),
])
DURATION = sum(p.seconds for p in PHASES)
PROTOCOL = "eye-motion-closure-v1"


def phase_at(elapsed):
    start = 0.0
    for i, phase in enumerate(PHASES):
        if start <= elapsed < start + phase.seconds:
            return i, phase, elapsed - start
        start += phase.seconds
    return None


class PhaseResults:
    def __init__(self):
        self.rows = [{"frames": 0, "settling_frames": 0, "face_frames": 0, "eyelid_frames": 0,
                      "iris_frames": 0, "reasons": Counter(), "values": defaultdict(list),
                      "last_iris": None, "last_observation": None} for _ in PHASES]

    def add(self, elapsed, observation, latency_ms):
        active = phase_at(elapsed)
        if active is None:
            return
        i, phase, offset = active
        row = self.rows[i]
        if offset < phase.settle:
            row["settling_frames"] += 1
            return
        row["frames"] += 1
        row["face_frames"] += int(observation["face_present"])
        row["eyelid_frames"] += int(observation["eyelids_valid"])
        row["iris_frames"] += int(observation["iris_valid"])
        row["reasons"].update(observation["reasons"])
        row["values"]["dequeue_to_result_ms"].append(latency_ms)
        if row["last_observation"] is not None:
            row["values"]["processed_gap_ms"].append(1000 * (elapsed - row["last_observation"]))
        row["last_observation"] = elapsed
        if observation["iris_valid"]:
            if row["last_iris"] is not None:
                row["values"]["iris_gap_ms"].append(1000 * (elapsed - row["last_iris"]))
            row["last_iris"] = elapsed
        for name, eye in observation["eyes"].items():
            if eye["eyelids_valid"]:
                for key in ("width_px", "openness"):
                    row["values"][f"{name}_{key}"].append(eye[key])
            if eye["iris_valid"]:
                for key in ("iris_x", "iris_y"):
                    row["values"][f"{name}_{key}"].append(eye[key])
        for key, value in observation["pose"].items():
            row["values"][key].append(value)

    def report(self, elapsed):
        results = []
        start = 0.0
        for phase, row in zip(PHASES, self.rows):
            window = max(0, min(elapsed - start, phase.seconds) - phase.settle)
            n = row["frames"]
            results.append({"phase": phase.name, "instruction": phase.instruction,
                "status": "complete" if elapsed >= start + phase.seconds else "partial" if elapsed > start else "not_reached",
                "planned_seconds": phase.seconds, "excluded_settling_seconds": phase.settle,
                "observed_window_seconds": window, "frames": n, "settling_frames": row["settling_frames"],
                "face_fraction": row["face_frames"] / n if n else None,
                "eyelid_fraction": row["eyelid_frames"] / n if n else None,
                "iris_fraction": row["iris_frames"] / n if n else None,
                "iris_fps": row["iris_frames"] / window if window else None,
                "reasons": dict(row["reasons"]), "metrics": {k: stats(v) for k, v in row["values"].items()},
                "review": "INSUFFICIENT_SAMPLES" if n < 5 else "MANUAL_REVIEW_REQUIRED"})
            start += phase.seconds
        return {"protocol": PROTOCOL, "planned_seconds": DURATION, "phases": results,
                "comparisons": comparisons(results),
                "interpretation": "Prompt windows are not verified action labels. No blink events, accuracy scores, or automatic pass/fail are produced."}


def comparisons(rows):
    by_name = {r["phase"]: r for r in rows}
    def median(phase, metric):
        row = by_name[phase]
        values = row["metrics"].get(metric, {})
        return values.get("median") if row["status"] == "complete" and values.get("n", 0) >= 5 else None
    output = {"direction_deltas_from_center": {}, "closure_to_open_openness_ratio": {}}
    for phase in ("left", "right", "up", "down", "final_center"):
        output["direction_deltas_from_center"][phase] = {}
        for eye in ("right", "left"):
            for axis in ("iris_x", "iris_y"):
                key = f"{eye}_{axis}"
                base, value = median("center", key), median(phase, key)
                output["direction_deltas_from_center"][phase][key] = value - base if base is not None and value is not None else None
    for i in range(1, 4):
        phase = f"closure_{i}"
        output["closure_to_open_openness_ratio"][phase] = {}
        for eye in ("right", "left"):
            base = median(f"prepare_closure_{i}", f"{eye}_openness")
            closed = median(phase, f"{eye}_openness")
            output["closure_to_open_openness_ratio"][phase][eye] = closed / base if base and closed is not None else None
    return output
