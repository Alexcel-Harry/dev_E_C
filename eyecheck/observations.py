"""Diagnostic v2: separate eyelid plausibility from iris usability.

Limits are broad engineering sanity checks, not calibrated confidence thresholds.
Legacy features.extract remains unchanged for historical camera comparisons.
"""
import math
from .features import EYES

SCHEMA = "mediapipe478-eye-diagnostic-v2"
LIMITS = {"min_eye_width_px": 2.0, "max_lid_openness": .65,
          "max_lid_axis_offset": .75, "max_lid_perpendicular_offset": .5,
          "max_iris_axis_offset": .75, "max_iris_perpendicular_offset": .5,
          "min_iris_openness": .06}


def observe(landmarks, width, height):
    output = {"face_present": bool(landmarks), "eyes": {}, "eyelids_valid": False,
              "iris_valid": False, "reasons": [], "pose": {}}
    if not landmarks:
        output["reasons"] = ["no_face"]
        return output
    if len(landmarks) != 478:
        output["reasons"] = ["unsupported_landmark_schema"]
        return output

    def point(i):
        p = landmarks[i]
        return (p.x * width, p.y * height)

    def inside(p):
        return all(math.isfinite(v) for v in p) and 0 <= p[0] < width and 0 <= p[1] < height

    centers = []
    for name, indices in EYES.items():
        a, b, upper, lower, iris = [point(i) for i in indices]
        eye = {"eyelids_valid": False, "iris_valid": False, "reasons": [], "points": []}
        output["eyes"][name] = eye
        if not all(inside(p) for p in (a, b, upper, lower)):
            eye["reasons"].append("invalid_lid_coordinates")
            continue
        span = math.dist(a, b)
        if span < LIMITS["min_eye_width_px"]:
            eye["reasons"].append("degenerate_eye_width")
            continue
        mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        ux, uy = (b[0] - a[0]) / span, (b[1] - a[1]) / span
        def project(p):
            x, y = p[0] - mid[0], p[1] - mid[1]
            return ((x * ux + y * uy) / span, (-x * uy + y * ux) / span)
        lid_xy = [project(p) for p in (upper, lower)]
        openness = math.dist(upper, lower) / span
        if openness > LIMITS["max_lid_openness"] or any(
            abs(x) > LIMITS["max_lid_axis_offset"] or abs(y) > LIMITS["max_lid_perpendicular_offset"]
            for x, y in lid_xy
        ):
            eye["reasons"].append("implausible_lid_geometry")
            continue
        eye.update(eyelids_valid=True, width_px=span, openness=openness, points=[a, b, upper, lower])
        centers.append(mid)
        if openness <= LIMITS["min_iris_openness"]:
            eye["reasons"].append("iris_not_used_near_closure")
        elif not inside(iris):
            eye["reasons"].append("invalid_iris_coordinates")
        else:
            x, y = project(iris)
            if abs(x) > LIMITS["max_iris_axis_offset"] or abs(y) > LIMITS["max_iris_perpendicular_offset"]:
                eye["reasons"].append("implausible_iris_position")
            else:
                eye.update(iris_valid=True, iris_x=x, iris_y=y)
                eye["points"].append(iris)
    output["eyelids_valid"] = all(e["eyelids_valid"] for e in output["eyes"].values())
    output["iris_valid"] = all(e["iris_valid"] for e in output["eyes"].values())
    output["reasons"] = [f"{name}:{reason}" for name, eye in output["eyes"].items() for reason in eye["reasons"]]
    if len(centers) == 2:
        a, b = centers
        output["pose"] = {"eye_midpoint_x": (a[0] + b[0]) / (2 * width),
                          "eye_midpoint_y": (a[1] + b[1]) / (2 * height),
                          "interocular_width_fraction": math.dist(a, b) / width,
                          "eye_line_roll_degrees": math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))}
    return output
