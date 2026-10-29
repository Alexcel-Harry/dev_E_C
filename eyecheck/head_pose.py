"""Versioned camera-relative pose estimates; no metric-depth claims."""
import math
import numpy as np

SCHEMA = 'face-matrix-pose-v1'
KEYS = ('yaw', 'pitch', 'roll', 'eye_midpoint_x', 'eye_midpoint_y', 'interocular_width_fraction')

def extract(matrix, proxies):
    result = {'schema': SCHEMA, 'valid': False, 'reasons': []}
    try:
        m = np.asarray(matrix, dtype=float)
        if m.shape != (4, 4) or not np.isfinite(m).all():
            raise ValueError('missing_or_nonfinite_matrix')
        if not np.allclose(m[3], [0, 0, 0, 1], atol=1e-4):
            raise ValueError('invalid_homogeneous_matrix')
        u, s, vt = np.linalg.svd(m[:3, :3])
        if min(s) < 1e-6 or max(s)/min(s) > 1.2 or np.linalg.det(u @ vt) < 0:
            raise ValueError('invalid_rotation_geometry')
        r = u @ vt
        # Intrinsic XYZ represented as Rz(roll) Ry(yaw) Rx(pitch).
        yaw = math.asin(float(np.clip(-r[2, 0], -1, 1)))
        if abs(math.cos(yaw)) < .05:
            raise ValueError('rotation_singularity')
        pitch = math.atan2(r[2, 1], r[2, 2])
        roll = math.atan2(r[1, 0], r[0, 0])
        values = [proxies[k] for k in KEYS[3:]]
        if not all(math.isfinite(v) for v in values) or values[-1] <= 0:
            raise ValueError('invalid_position_proxies')
        result.update(valid=True, matrix=m.tolist(), rotation=r.tolist(),
                      yaw=math.degrees(yaw), pitch=math.degrees(pitch), roll=math.degrees(roll),
                      **dict(zip(KEYS[3:], values)))
    except (ValueError, TypeError, KeyError, np.linalg.LinAlgError) as exc:
        result['reasons'] = [str(exc)]
    return result

def reference(poses):
    usable = [p for p in poses if p.get('valid')]
    if len(usable) < 20:
        raise ValueError('Reference requires 20 valid pose frames')
    rotations = np.array([p['rotation'] for p in usable])
    u, _, vt = np.linalg.svd(rotations.mean(axis=0))
    r = u @ np.diag([1, 1, np.linalg.det(u @ vt)]) @ vt
    out = {k: float(np.median([p[k] for p in usable])) for k in KEYS}
    out.update(rotation=r.tolist(), schema=SCHEMA)
    deltas = np.array([relative(p, out) for p in usable])
    if np.ptp(deltas[:, :3], axis=0).max() > 8 or np.ptp(deltas[:, 3:5], axis=0).max() > .04:
        raise ValueError('Hold a stable neutral pose and repeat reference')
    return out

def relative(pose, ref):
    if not pose.get('valid') or ref.get('schema') != SCHEMA:
        raise ValueError('Missing or incompatible pose/reference')
    # Relative rotations compose; subtracting Euler angles is not equivalent.
    r = np.asarray(ref['rotation']).T @ np.asarray(pose['rotation'])
    local = extract(np.block([[r, np.zeros((3, 1))], [np.zeros((1, 3)), np.ones((1, 1))]]), pose)
    if not local['valid']:
        raise ValueError('Invalid relative pose')
    return [local[k] for k in KEYS[:3]] + [pose[k]-ref[k] for k in KEYS[3:5]] + [math.log(pose[KEYS[-1]]/ref[KEYS[-1]])]
