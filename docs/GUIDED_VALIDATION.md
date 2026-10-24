# Guided eye movement and closure validation

This is the next validation stage after the seated stability checks. It uses the LIVE webcam and the existing local Face Landmarker model. The screen prompts you through eye motion, ordinary blinks, three gentle closures, and brief face loss. It does not train a gaze model, move the pointer, click, or save images/video/continuous numeric traces.

Implementation is ready for the Lenovo Linux test. Thirty-one automated tests passed on Windows using synthetic geometry and mocked GUI/camera/model interfaces. Real Qt rendering, sound, camera timing and landmark response during these phases still need target-device validation. No new dependencies are required beyond `requirements.txt`.

## Sync and start

Sync the updated `eyecheck/`, `tests/`, `docs/`, `README.md` and `NEXT_STEP.md` to Linux. Preserve Linux `.venv/`, `models/` and existing `reports/`. The editable install uses the updated code without reinstalling packages.

From the Linux project root with the virtual environment active:

```bash
python -m unittest discover -s tests -v
python -m eyecheck guided --help
python -m eyecheck guided \
  --device /dev/video0 --width 1280 --height 720 \
  --fps 30 --fourcc MJPG --disable-dynamic-fps \
  --warmup 10 \
  --model models/face_landmarker.task \
  --label guided-baseline \
  --out reports/17-guided-baseline.json
```

Optional metadata flags: `--distance-cm` with your measured eye-to-camera distance, `--lighting` with a brief description, and `--notes` with other setup details. Example: append `--distance-cm 68 --lighting "diffuse lamp beside camera"` only if those values describe your actual setup. Do not copy example measurements as facts.

Do not pass `--seconds`: the guided protocol has a fixed 106-second duration, plus warmup and setup. Preview is always enabled. An existing output filename is refused to preserve results; for a repeat use `17-guided-baseline-repeat1.json` or another fresh name. The program displays the live image, eye crops, current validity and a countdown. Close the window or press Escape to stop early; expect an `incomplete` report and exit code 2. Errors return exit code 1. A completed run returns `recorded`, not an automatic pass.

## How to perform the test

Use the usual glasses and the lighting/position that worked during the seated checks. Keep keyboard/touchpad access. Keep the whole face visible except when explicitly asked to move out of view. Move your eyes without deliberately moving your head during the direction phases; do not strain at the edges. Natural small head movements are expected and summarized through pose proxies.

Make sure you can read the prompts. A system beep is requested at phase changes, but desktop sound configuration may make it inaudible. During each closure, count TWO seconds yourself and reopen; during face loss, count THREE seconds and return. Do not stay closed or out of view waiting for a sound. These long closures are for checking observable eyelid features, not the eventual 500-900 ms click gesture. Do not squeeze your eyes shut.

| Sequence | Duration | Action |
| --- | --- | --- |
| Initial center | 8s | Look at the center, eyes naturally open. |
| Left, right, up, down | 5s each | Look toward the indicated side; follow the intervening center prompts. |
| Center returns | 3s after left/right/up, 5s after down | Return to center without moving your head deliberately. |
| Natural blinks | 15s | Look naturally at the screen and blink normally. |
| Three closure cycles | 4s prepare, 2s close, 4s reopen per cycle | Keep open while preparing; close gently when prompted, then reopen. |
| Prepare face loss | 4s | Stay visible and prepare to move out of view. |
| Face loss | 3s | Move your whole face out of view, then return. |
| Return | 6s | Resume the original position and look at center. |
| Final center | 6s | Keep eyes naturally open until completion. |

If you miss a cue or change lighting/distance, finish or stop as appropriate and describe it in the notes. Prompt windows are not proof that the intended action occurred. Camera buffering and reaction time can blur the boundaries, particularly during two-second closures.

## What the preview means

- The full image is unmirrored. The left displayed crop is the subject's right eye.
- Crops retain their aspect ratio and are padded to fit; resizing does not add optical detail. Crop dimensions are shown in source pixels, including margins.
- `eyelids plausible` means both eyes passed broad corner/eyelid geometry checks. It does not mean eyes are open, or that the model is certainly correct.
- `iris plausible` means both irises passed the additional sanity checks. It does not mean the gaze position is accurate.
- `iris NOT USABLE` during closure can be expected while eyelid measurements remain available. A missing face or implausible eyelid geometry does not become a zero openness value or a blink event.
- If new frames stop for more than 250 ms, the displayed image is cleared and marked stale. A longer capture stall stops the run; no input is emitted.

## What the report contains

Guided reports use schema 2, feature schema `mediapipe478-eye-diagnostic-v2`, and protocol `eye-motion-closure-v1`. Ordinary `camera` reports retain legacy v1 feature semantics for historical comparison; only their preview layout/current-validity wording changed.

Per-phase summaries include face, eyelid and iris availability; rejection reasons; eye width/openness/iris-coordinate statistics; simple head-position/scale/roll proxies; processing timing and within-phase gaps. The first second of most phases is excluded as settling time; closure and face-loss windows exclude their first 0.5 seconds. Settling counts are reported. Whole-run totals still include these frames and the intentionally invalid phases.

The report also compares direction-phase median iris features against initial center and closure median openness against the preceding open preparation phase, separately for each eye. A closure/open ratio below 1 means measured openness decreased; there is no automatic passing threshold. Ratios/deltas become null if a phase is incomplete or a relevant statistic has fewer than five samples. All summaries remain descriptive; no blink count, deliberate-gesture success rate, gaze accuracy or calibrated thresholds are produced.

Gross sanity limits are stored under `sanity_limits`. They reject such cases as an iris many eye widths away, nonfinite/out-of-frame landmarks, impossible lid spread, and degenerate eye width. They are broad engineering settings, not clinically or experimentally validated confidence limits. A nearly closed lid causes iris features to be withheld, while valid lid measurements remain available. Plausible hallucinations and glare can still escape these checks.

Expected qualitative evidence: repeatable direction-related feature changes with approximately steady head pose; lower measured openness for each instructed closure in both eyes; recovery after reopening; explicit no-face observations during face loss followed by reacquisition. No-face during the requested face-loss phase is expected. Missing eyelid observations during closure are important evidence of a limitation. Do not optimize a whole-run recognition percentage for this protocol.

## Return results

Sync `reports/17-guided-baseline.json`, the Linux unit-test result, and completed [manual notes](GUIDED_RESULTS_TEMPLATE.md). Report whether the UI and cues were readable and whether the beep was audible. Raw video is not requested. We will review the evidence before moving to native pointer/pause validation or collecting a personal training dataset.

`--disable-dynamic-fps` leaves the setting applied and verifies it only before capture. It still does not guarantee 30 FPS; the application baseline is approximately 15 FPS. Restore the earlier value of 1 after the test if desired:

```bash
v4l2-ctl -d /dev/video0 --set-ctrl=exposure_dynamic_framerate=1
```
