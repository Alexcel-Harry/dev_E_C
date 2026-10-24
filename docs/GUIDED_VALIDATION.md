# Guided eye movement and closure validation — protocol v2

This version implements target-local instructions and a one-second buffer on each side of every measurement window. It addresses the timing and gaze shifts reported during run 17. It uses the LIVE webcam and existing local Face Landmarker model, with no pointer input, training dataset, images/video or saved per-frame traces.

## Sync and run

Sync updated `eyecheck/`, `tests/`, `docs/`, `README.md` and `NEXT_STEP.md`. Preserve the Linux `.venv/`, `models/` and previous `reports/`. The editable install needs no package reinstall or new dependency.

From the Linux project root, with the virtual environment active:

```bash
python -m unittest discover -s tests -v
python -m eyecheck guided \
  --device /dev/video0 --width 1280 --height 720 \
  --fps 30 --fourcc MJPG --disable-dynamic-fps \
  --warmup 10 \
  --model models/face_landmarker.task \
  --label target-local-buffered \
  --out reports/18-guided-targets.json
```

The protocol lasts **116 seconds plus warmup/setup**. Omit `--seconds` and `--preview`: guided mode uses fullscreen instructions and hides the camera preview. An existing output filename is refused. Use a new name for any repeat. Optional `--distance-cm`, `--lighting` and `--notes` store actual user-reported setup details; do not invent measurements.

## What to do

Use the same camera position, usual glasses and repeatable lighting as the seated runs. Keep your head comfortably still and follow the instruction card with your eyes. Instructions for left/right/up/down appear at that location on the screen; center and closure instructions appear centrally. No central status panel or live eye crop competes for attention. Stay looking at the card until it moves or gives the next action. Text covers a small region, so this is a coarse direction test rather than exact gaze ground truth.

Each phase follows:

```text
1 second: get ready       | measured middle window | 1 second: keep holding
phase samples excluded   | phase samples retained | phase samples excluded
```

Keep holding the SAME gaze/action during the trailing second. It is a buffer, not a cue to return early. The countdown and stage status stay at the same target. Camera capture and model inference continue through both buffers to preserve tracking. Only middle-window observations enter phase statistics and comparisons. Whole-run throughput/timing counters include buffers, clearly separated from phase evidence. These buffers reduce transition contamination but cannot verify your actions or remove unknown camera buffering.

| Phases | Total time per phase | Measured middle window |
| --- | --- | --- |
| Initial center | 8s | 6s |
| Left/right/up/down | 5s each | 3s each |
| Center after left/right/up | 4s each | 2s each |
| Center after down | 5s | 3s |
| Natural blinking | 15s | 13s |
| Each closure cycle: prepare / close / reopen | 4s / 4s / 4s | 2s / 2s / 2s |
| Prepare face loss / face loss | 4s / 4s | 2s / 2s |
| Return / final center | 6s / 6s | 4s / 4s |

Three closure cycles are included. Read the preparation cue with eyes open. At CLOSE, gently close both eyes for FOUR seconds; then reopen at the next cue. No squeezing is needed. A system beep is requested on phase changes, including reopening; its audibility depends on desktop sound settings. If it is inaudible, count four yourself and mention any timing uncertainty. During face loss, count FOUR seconds out of view and return. These diagnostic closures are longer than the eventual click gesture.

Escape stops immediately at the next event-loop opportunity and saves an incomplete report (exit 2). Errors return exit 1; completed collection returns `recorded` (exit 0), not an automatic pass. Stop if instructions are clipped or difficult to read and report the issue. A camera stall is indicated at the current target; no images are displayed and no cursor input is emitted.

## Report interpretation

Reports retain schema 2 and feature schema `mediapipe478-eye-diagnostic-v2`; the **protocol is now `eye-motion-closure-v2`**. Do not compare phase fractions directly with run 17's older timing protocol. Its raw report remains unchanged. Ordinary `camera` measurements still use legacy feature v1; `camera --preview` remains available separately for visual inspection.

Per-phase output includes `settling_frames`, `trailing_frames`, middle-window `frames`, measurement start/end times relative to the run, face/eyelid/iris availability, rejection reasons, feature summaries and processing timing. Buffer frames contribute to neither phase metrics nor their FPS denominator. Phase comparisons require complete phases and at least five relevant samples. Display metadata records logical screen geometry, scale and intended target-card positions, not verified eye fixation.

Eyelid plausibility remains independent of iris plausibility. Geometric sanity checks are not visibility/accuracy guarantees: run 17 still reported plausible iris geometry during instructed closures. No thresholds were changed to fit that run. Assess closure openness, recovery and repeatability together with actual-action notes. No face is an unavailable observation, not a blink or zero openness. Expected face loss is not a failed recognition test. No blink counts or gaze-accuracy scores are claimed.

## Return evidence

Sync `reports/18-guided-targets.json`, Linux unit-test output and [manual notes](GUIDED_RESULTS_TEMPLATE.md). Include whether text appeared at the correct locations and was readable, whether you held each target through the final buffer, closure timing, audible cues and any looking back or missed instructions. No raw video is requested.

All 34 automated tests passed on Windows using synthetic observations and mocked runtime paths, including buffer-boundary exclusion and target layout geometry. Actual Qt rendering/fullscreen placement, cue audibility and camera behavior still require this Linux run.

`--disable-dynamic-fps` leaves the control set to zero and verifies it before capture only; it does not guarantee 30 FPS. The accepted provisional application baseline is approximately 15 FPS. Optional restoration:

```bash
v4l2-ctl -d /dev/video0 --set-ctrl=exposure_dynamic_framerate=1
```
