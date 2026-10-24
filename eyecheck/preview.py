"""Aspect-preserving display only. No image persistence."""


def fit_size(width, height, box_width, box_height):
    if min(width, height, box_width, box_height) <= 0:
        raise ValueError("Image and box dimensions must be positive")
    scale = min(box_width / width, box_height / height)
    return max(1, round(width * scale)), max(1, round(height * scale))


def letterbox(image, box_width, box_height):
    import cv2
    import numpy as np
    w, h = fit_size(image.shape[1], image.shape[0], box_width, box_height)
    output = np.zeros((box_height, box_width, 3), dtype=np.uint8)
    left, top = (box_width - w) // 2, (box_height - h) // 2
    output[top:top + h, left:left + w] = cv2.resize(image, (w, h))
    return output


def composite(rgb, eyes):
    import cv2
    import numpy as np
    full = letterbox(rgb, 800, 450)
    crops = []
    for name in ("right", "left"):
        eye = (eyes or {}).get(name, {})
        tile = np.zeros((180, 400, 3), dtype=np.uint8)
        pts = eye.get("points", [])
        if pts:
            margin = max(5, int(eye["width_px"] * .3))
            x0 = max(0, int(min(p[0] for p in pts)) - margin)
            x1 = min(rgb.shape[1], int(max(p[0] for p in pts)) + margin + 1)
            y0 = max(0, int(min(p[1] for p in pts)) - margin)
            y1 = min(rgb.shape[0], int(max(p[1] for p in pts)) + margin + 1)
            crop = rgb[y0:y1, x0:x1].copy()
            if crop.size:
                for x, y in pts:
                    cv2.circle(crop, (round(x - x0), round(y - y0)), 1, (0, 255, 0), -1)
                tile = letterbox(crop, 400, 180)
                cv2.putText(tile, f"{name} eye: crop {x1-x0}x{y1-y0}px", (8, 172), cv2.FONT_HERSHEY_SIMPLEX, .4, (255, 255, 255), 1)
        else:
            cv2.putText(tile, f"{name} eye: unavailable", (12, 90), cv2.FONT_HERSHEY_SIMPLEX, .5, (255, 255, 255), 1)
        crops.append(tile)
    return np.ascontiguousarray(np.vstack((full, np.hstack(crops))))
