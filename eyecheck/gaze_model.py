"""Offline grouped residual fitting and abstaining joint-gaze inference."""
import hashlib
import json
from pathlib import Path
import numpy as np
from .collection import gaze_features, predict
from .head_pose import SCHEMA as POSE_SCHEMA

SCHEMA = 'joint-gaze-ridge-v1'
FEATURES = ['left_x', 'left_y', 'right_x', 'right_y', 'yaw', 'pitch', 'roll', 'position_x', 'position_y', 'log_scale']

def inputs(calibration, eyes, delta):
    calibrated = []
    for i, name in enumerate(('left', 'right')):
        calibrated.extend(np.array([*eyes[2*i:2*i+2], 1.]) @ calibration['eyes'][name]['weights_3x2'])
    z = np.array(calibrated + list(delta), dtype=float)
    if z.shape != (10,) or not np.isfinite(z).all():
        raise ValueError('Invalid joint gaze features')
    return z

def fit(x, target, baseline, weights, alpha=1.):
    x, target, baseline, weights = map(np.asarray, (x, target, baseline, weights))
    if x.ndim != 2 or x.shape[1] != 10 or target.shape != (len(x), 2) or baseline.shape != target.shape or weights.shape != (len(x),):
        raise ValueError('Invalid fitting dimensions')
    if not all(np.isfinite(a).all() for a in (x, target, baseline, weights)) or np.any(weights <= 0) or not np.isfinite(alpha) or alpha <= 0:
        raise ValueError('Invalid training values or regularization')
    weights = weights / weights.sum()
    mean = np.average(x, axis=0, weights=weights)
    scale = np.sqrt(np.average((x-mean)**2, axis=0, weights=weights))
    scale[scale < 1e-8] = 1.
    design = np.column_stack(((x-mean)/scale, np.ones(len(x))))
    penalty = np.diag([alpha]*10 + [0.])
    coef = np.linalg.solve(design.T @ (weights[:, None]*design)+penalty,
                           design.T @ (weights[:, None]*(target-baseline)))
    return {'schema': SCHEMA, 'pose_schema': POSE_SCHEMA, 'features': FEATURES,
            'mean': mean.tolist(), 'scale': scale.tolist(), 'coefficients': coef.tolist(),
            'pose_min': x[:, 4:].min(axis=0).tolist(), 'pose_max': x[:, 4:].max(axis=0).tolist(), 'alpha': alpha}

def load_profile(path):
    p = json.loads(Path(path).read_text(encoding='utf-8'))
    if p.get('schema') != SCHEMA or p.get('pose_schema') != POSE_SCHEMA or p.get('features') != FEATURES:
        raise ValueError('Incompatible gaze profile')
    for key, shape in [('mean', (10,)), ('scale', (10,)), ('coefficients', (11, 2)), ('pose_min', (6,)), ('pose_max', (6,))]:
        a = np.asarray(p[key], dtype=float)
        if a.shape != shape or not np.isfinite(a).all():
            raise ValueError('Invalid profile '+key)
    if min(p['scale']) <= 0 or np.any(np.array(p['pose_min']) > p['pose_max']):
        raise ValueError('Invalid profile bounds/scaling')
    return p

def estimate(profile, calibration, eyes, delta):
    try:
        z = inputs(calibration, eyes, delta)
        if np.any(z[4:] < np.array(profile['pose_min'])-1e-6) or np.any(z[4:] > np.array(profile['pose_max'])+1e-6):
            return {'valid': False, 'reason': 'Head pose outside training range; reposition or recalibrate'}
        row = np.r_[(z-np.array(profile['mean']))/profile['scale'], 1.]
        gaze = np.array(predict(calibration, eyes)) + row @ profile['coefficients']
        if not np.isfinite(gaze).all():
            raise ValueError('Nonfinite prediction')
        return {'valid': True, 'gaze': gaze.tolist(), 'reason': 'within recorded pose ranges; accuracy unverified'}
    except (ValueError, TypeError, KeyError):
        return {'valid': False, 'reason': 'Invalid eye/head observation'}

def compatibility(m):
    return {k: m[k] for k in ('model_sha256', 'actual_frame_size', 'feature_schema')} | {
        'window_logical_size': m['display']['window_logical_size']}

class Smoother:
    """Time-based display smoothing, reset on invalid data or a >250ms gap."""
    def __init__(self, tau=.08):
        self.tau, self.last_time, self.value = tau, None, None

    def update(self, result, now):
        if not result or not result.get('valid'):
            self.last_time = self.value = None
            return result
        point = np.array(result['gaze'], dtype=float)
        dt = None if self.last_time is None else now-self.last_time
        if dt is None or dt <= 0 or dt > .25:
            self.value = point
        else:
            self.value += (1-np.exp(-dt/self.tau))*(point-self.value)
        self.last_time = now
        return {**result, 'gaze': self.value.tolist(), 'unsmoothed_gaze': result['gaze']}

def dataset(paths, split):
    records, manifests = [], []
    seen = set()
    for directory in paths:
        directory = Path(directory)
        m = json.loads((directory/'manifest.json').read_text(encoding='utf-8'))
        if m['session_id'] in seen:
            raise ValueError('Duplicate session')
        seen.add(m['session_id'])
        if m.get('protocol') != 'eyecheck-head-pose-v2' or m.get('split') != split or m.get('status') != 'recorded' or not m['summary']['completed']:
            raise ValueError('Use completed head-pose sessions assigned to '+split)
        for name in ('observations.jsonl', 'events.jsonl'):
            if hashlib.sha256((directory/name).read_bytes()).hexdigest() != m['file_sha256'][name]:
                raise ValueError('Session evidence hash mismatch')
        if manifests and compatibility(m) != compatibility(manifests[0]):
            raise ValueError('Incompatible camera/model/display sessions')
        manifests.append(m)
        attempts = {a['id']: a for a in m['summary']['attempts']}
        calibration = m['summary']['calibration']
        for line in (directory/'observations.jsonl').read_text(encoding='utf-8').splitlines():
            row = json.loads(line)
            a = attempts.get(row.get('attempt_id'), {})
            if row.get('gaze_eligible') and row.get('role') == 'gaze_target' and a.get('status') == 'recorded':
                eyes = gaze_features(row['observation'])
                records.append({'x': inputs(calibration, eyes, row['relative_pose']),
                    'baseline': predict(calibration, eyes), 'target': row['target_normalized'],
                    'sitting': m['sitting_id'], 'session': m['session_id'], 'attempt': a['id'],
                    'condition': row['condition']})
    if not records:
        raise ValueError('No eligible gaze target observations')
    return records, manifests

def balanced_weights(rows):
    # Equal sittings, equal sessions within sitting, equal fixations within session.
    from collections import Counter, defaultdict
    sessions, fixations = defaultdict(set), defaultdict(set)
    counts = Counter((r['session'], r['attempt']) for r in rows)
    for r in rows:
        sessions[r['sitting']].add(r['session'])
        fixations[r['session']].add(r['attempt'])
    return [1 / (len(sessions[r['sitting']])*len(fixations[r['session']])*counts[r['session'], r['attempt']]) for r in rows]

def write_new(path, data):
    with Path(path).open('x', encoding='utf-8') as f:
        json.dump(data, f, indent=2, allow_nan=False)
        f.write('\n')

def add_parser(sub):
    for name in ('train-gaze', 'evaluate-gaze'):
        p = sub.add_parser(name, help='Offline joint eye/head residual model; no camera/input control')
        p.add_argument('--sessions', nargs='+', required=True)
        p.add_argument('--out', required=True)
        if name == 'train-gaze':
            p.add_argument('--alpha', type=float, default=.01, help='Preselected ridge penalty; do not tune on test')
        else:
            p.add_argument('--profile', required=True)
            p.add_argument('--split', choices=('dev', 'test'), required=True)

def dispatch(args):
    train = args.command == 'train-gaze'
    rows, manifests = dataset(args.sessions, 'train' if train else args.split)
    sittings = sorted({r['sitting'] for r in rows})
    if train:
        if len(sittings) < 2:
            raise ValueError('Training requires at least two independent sittings')
        model = fit([r['x'] for r in rows], [r['target'] for r in rows], [r['baseline'] for r in rows], balanced_weights(rows), args.alpha)
        model.update(training_sittings=sittings, training_sessions=[m['session_id'] for m in manifests], compatibility=compatibility(manifests[0]))
        write_new(args.out, model)
    else:
        model = load_profile(args.profile)
        if set(sittings) & set(model['training_sittings']):
            raise ValueError('Evaluation sitting overlaps training')
        if compatibility(manifests[0]) != model['compatibility']:
            raise ValueError('Profile/session compatibility mismatch')
        result = {'split': args.split, 'sittings': sittings, 'conditions': {}}
        size = np.asarray(model['compatibility']['window_logical_size'])
        for condition in sorted({r['condition'] for r in rows}):
            group = [r for r in rows if r['condition'] == condition]
            errors, baseline, covered_baseline = [], [], []
            for r in group:
                b = np.array(r['baseline'])
                e = float(np.linalg.norm((b-r['target'])*size))
                baseline.append(e)
                z = r['x']
                if np.all(z[4:] >= np.array(model['pose_min'])-1e-6) and np.all(z[4:] <= np.array(model['pose_max'])+1e-6):
                    pred = b + np.r_[(z-model['mean'])/model['scale'], 1.] @ model['coefficients']
                    errors.append(float(np.linalg.norm((pred-r['target'])*size)))
                    covered_baseline.append(e)
            def metrics(values):
                return {'median': float(np.median(values)), 'p95': float(np.percentile(values,95))} if values else None
            result['conditions'][condition] = {'eligible_frames': len(group), 'joint_coverage_of_eligible': len(errors)/len(group),
                'baseline_logical_px': metrics(baseline), 'baseline_same_frames_logical_px': metrics(covered_baseline), 'joint_logical_px': metrics(errors)}
        result['note'] = 'Errors conditional on eligible frames; pose coverage is not total camera availability. No accuracy pass threshold implied.'
        write_new(args.out, result)
    print('Saved: '+str(args.out))
    return 0
