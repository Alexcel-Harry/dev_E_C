"""MediaPipe 478-landmark diagnostic adapter v1. Geometry is not gaze accuracy."""
import math

# Subject's right and left eyes in unmirrored camera coordinates.
EYES = {"right": (33, 133, 159, 145, 468), "left": (362, 263, 386, 374, 473)}


def extract(landmarks, width, height):
    if len(landmarks) != 478:
        raise ValueError(f"Expected 478 landmarks, got {len(landmarks)}; review adapter")
    def point(i):
        p = landmarks[i]
        return (p.x * width, p.y * height)
    result = {}
    for name, indices in EYES.items():
        a, b, upper, lower, iris = [point(i) for i in indices]
        if not all(math.isfinite(v) for p in (a, b, upper, lower, iris) for v in p):
            raise ValueError("Nonfinite eye geometry")
        if not all(0 <= p[0] < width and 0 <= p[1] < height for p in (a, b, upper, lower, iris)):
            raise ValueError("Eye geometry outside frame")
        dx, dy = b[0] - a[0], b[1] - a[1]
        span = math.hypot(dx, dy)
        if span < 2:
            raise ValueError("Degenerate eye width")
        ux, uy = dx / span, dy / span
        ix, iy = iris[0] - (a[0] + b[0]) / 2, iris[1] - (a[1] + b[1]) / 2
        result[name] = {"width_px": span, "openness": math.dist(upper, lower) / span,
                        "iris_x": (ix * ux + iy * uy) / span,
                        "iris_y": (-ix * uy + iy * ux) / span,
                        "points": [a, b, upper, lower, iris]}
    return result
