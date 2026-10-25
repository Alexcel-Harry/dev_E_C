"""Optional per-second aggregates, never images or per-frame landmark traces."""
import math

from .common import stats


class FrameTimeline:
    def __init__(self):
        self.bins = {}

    def add(self, seconds, frame_id, face_count, eyes, reason, gray_mean, gray_std, dark_fraction, age_ms):
        index = max(0, int(seconds))
        row = self.bins.setdefault(index, {
            "processed_frames": 0, "face_frames": 0, "geometry_frames": 0,
            "reasons": {}, "first_frame_id": frame_id, "last_frame_id": frame_id,
            "metrics": {name: [] for name in (
                "sampled_gray_mean", "sampled_gray_std", "sampled_dark_fraction",
                "capture_age_ms", "left_openness", "right_openness")}})
        row["processed_frames"] += 1
        row["face_frames"] += int(face_count > 0)
        row["geometry_frames"] += int(eyes is not None)
        row["last_frame_id"] = frame_id
        if reason:
            row["reasons"][reason] = row["reasons"].get(reason, 0) + 1
        for name, value in (("sampled_gray_mean", gray_mean), ("sampled_gray_std", gray_std),
                            ("sampled_dark_fraction", dark_fraction), ("capture_age_ms", age_ms)):
            row["metrics"][name].append(float(value))
        if eyes is not None:
            for name in ("left", "right"):
                row["metrics"][name + "_openness"].append(eyes[name]["openness"])

    def report(self, elapsed):
        # Include empty intervals explicitly; they are not face-negative frames.
        count = max(math.ceil(elapsed), max(self.bins, default=-1) + 1)
        rows = []
        for index in range(count):
            row = self.bins.get(index)
            out = {"start_seconds": index, "end_seconds": min(index + 1, elapsed),
                   "processed_frames": 0, "face_frames": 0, "geometry_frames": 0,
                   "reasons": {}, "first_frame_id": None, "last_frame_id": None, "metrics": {}}
            if row:
                out.update({k: v for k, v in row.items() if k != "metrics"})
                out["metrics"] = {k: stats(v) for k, v in row["metrics"].items()}
            rows.append(out)
        return {"schema": "camera-one-second-aggregates-v1", "bins": rows,
                "basis": "Processed frames bucketed by read-completion time since measurement start; empty bins are not no-face detections.",
                "image_metrics": "Grayscale samples every 8 pixels; dark fraction uses intensity < 16 of 255. Not an occlusion classifier.",
                "limits": "No images or per-frame landmarks saved. Observed brightness and geometry do not establish visibility or gaze accuracy."}
