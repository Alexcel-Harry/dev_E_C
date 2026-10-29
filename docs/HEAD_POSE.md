# Joint eye/head gaze extension

Implemented protocol: `eyecheck-head-pose-v2`. The original collector remains available without `--head-pose`. This extension records estimated camera-relative rotation, fits a personalized residual model offline, evaluates independent sessions, and displays gaze during a dedicated practice block. It does not send desktop pointer events. Accuracy, physical axis signs, motion response, glasses behavior and extra inference cost still require the Linux pilot.

## Linux pilot

From the repository with its validation environment activated:

```bash
python -m eyecheck collect --head-pose \
  --device /dev/video0 --width 1920 --height 1080 --fps 30 \
  --fourcc MJPG --disable-dynamic-fps --model models/face_landmarker.task \
  --lighting daylight --distance-cm 70 --notes "usual glasses; usual desk" \
  --sitting-id head-pilot-01 --split pilot \
  --trials-per-pattern 1 --reading-seconds 30 --max-minutes 45
```

Use the correct verified camera device and mode. Inspect the schedule without camera access using `python -m eyecheck collect --head-pose --plan`.

Workflow: neutral center pose reference; four corners with stable reference posture; independent center check; original 50 gaze targets; nine targets each under neutral, left/right turn, up/down nod, natural movement and fixation-with-head-motion conditions; gesture references/trials and reading. A two-second preparation precedes each item. Every added pose trial has a review break: Space accepts, R repeats, Escape stops. Accept only trials where fixation and instructions were followed. Use a fresh session after a setup change; retain the sitting ID across related runs.

The neutral reference requires 20 fresh, open-eye, valid-pose observations. Rotation spread above 8 degrees or position spread above .04 image fraction requires a retry. Calibration anchors accept only relative rotations within 8 degrees, position changes within .04 image fraction and log-scale changes within .1. These are provisional engineering gates, not accuracy guarantees. At approximately 15 FPS a two-second reference usually provides about 30 observations; repeat if insufficient.

Matrix decomposition uses nearest proper rotation and Rz(roll) Ry(yaw) Rx(pitch), with degree angles. Relative rotations compose matrices rather than subtracting Euler angles. Matrix singularities/reflections/nonfinite values are rejected. Face location/size are image proxies, not metric XYZ. Unmirrored camera input is retained. Verify displayed/logged axes on the actual device before formal acquisition.

## Training and independent evaluation

After the pilot, collect full sessions using `--split train`, `dev`, or `test` and unique sitting identifiers. Related sessions from one sitting belong to one split. Formal sessions retain the default gesture/reading budgets. Train requires at least two independent training sittings; development/test inputs cannot enter training. Example paths below stand for actual printed dataset folders:

```bash
python -m eyecheck train-gaze --sessions /path/train-session-1 /path/train-session-2 --out joint-profile.json
python -m eyecheck evaluate-gaze --profile joint-profile.json --split dev --sessions /path/dev-session --out dev-results.json
python -m eyecheck evaluate-gaze --profile joint-profile.json --split test --sessions /path/test-session --out test-results.json
```

Session completion, protocol, hashes, final attempt status, camera resolution, landmark model hash, feature schema and display logical size are checked. Invalidated retries, anchors, center checks, neutral references, gestures and practice are excluded from fitting. Predictions never determine training eligibility. Mean/scale and all regression coefficients are fitted only on training data, with equal sitting/session/fixation weighting. `--alpha` is a positive ridge penalty, default .01; choose it on development data and freeze before testing. Output paths must be fresh.

The ten inputs are two calibrated coordinates per eye plus relative yaw/pitch/roll, image position x/y and log apparent scale. The residual ridge model adds 22 coefficients to the existing session maps. Stored profile metadata includes training sitting/session IDs and feature compatibility. Numeric evidence cannot support appearance-network fine-tuning.

Evaluation reports per-condition median/p95 errors in Qt logical pixels for the eye-only baseline and joint model. Baseline results on exactly the joint model's accepted frames are included to expose coverage tradeoffs. Joint coverage is relative to eligible gaze frames, not all camera frames; inspect the session ledger's frames/eligible counts for total availability. Inspect fixation-with-head-motion trials for drift and compare natural targeting separately. The profile rejects relative poses outside recorded per-feature training minima/maxima; this rectangular envelope does not prove coverage of every feature combination or calibrated confidence.

## Live practice

Use the same collection options as the pilot, adding:

```text
--gaze-profile joint-profile.json --tracking-only --split pilot
```

This runs a fresh neutral reference, four corners, independent center check and up to ten minutes of visible tracking practice. The blue dot is the predicted gaze. Short tracking gaps clear the dot after 250ms; invalid observations/out-of-range poses reset smoothing. Display smoothing has an 80ms time constant; raw estimates remain in observations. Camera absence still uses the existing bounded-stop behavior. P pauses; Escape saves an incomplete session if stopped early. No pointer movement or button actions occur.

Adding `--gaze-profile` to a normal head-pose collection run saves joint predictions without displaying them on labeled trials. Practice frames have no target labels and never train the model. Changing hardware, screen layout or posture beyond the tested range calls for renewed validation/calibration. The same model hash and resolution do not prove that two physical cameras are interchangeable.
