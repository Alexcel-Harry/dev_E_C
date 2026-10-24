# Validation status

Updated: 2026-10-23 (America/Los_Angeles). This record summarizes user-executed Linux tests and synced reports. Windows is the development/review device. Guided runs 17 and 18 have been reviewed; basic eye-motion/closure response is accepted provisionally; [NEXT_STEP.md](../NEXT_STEP.md) is the maintained action queue.

## Decision

The one-minute controlled runs at 720p/1080p and ten-minute 720p run support continuing the prototype with the current camera. Select **1280x720 MJPG, approximately 15 observed updates/s**, as the provisional baseline because it provides comparable basic detection coverage with lower processing cost. Retain 1080p for a later accuracy comparison. No new camera purchase is indicated by these measurements.

This is acceptance of capture and basic-landmark stability for development, not full hardware validation, gaze accuracy, blink recognition, or release readiness. The original plan's 20 usable gaze updates/s target remains unmet. The user accepts exploring slower tracking; the FPS investigation is deferred, not resolved.

The original `Linux_Eye_Tracking_Technical_Plan.docx` (19 October 2026, v1.1) remains the historical design reference. This status record documents observed differences from its assumptions: Python 3.13.5 rather than proposed 3.12, a provisional ~15 FPS application baseline, and a still-unverified desktop backend. No later plan milestone is declared complete.

## Observed environment

| Item | Evidence |
| --- | --- |
| Machine | Lenovo XiaoXinPro 14 IMH9; product 83D2 |
| OS / architecture | Reported Ubuntu 24.04.5 LTS, x86_64 |
| Kernel / Python | Reported 7.0.0-38-generic / 3.13.5 |
| Desktop | Ubuntu GNOME, Wayland |
| Qt display | One screen; logical 1648x1030; device-pixel ratio 2; approximately 120 Hz. Physical resolution and native input mapping are not established by these values. |
| RGB camera | `/dev/video0`, Bison USB 5986:2169, `uvcvideo` |
| Advertised relevant modes | MJPG: 1280x720 and 1920x1080 at 30 FPS. YUYV: 720p at 10 FPS, 1080p at 5 FPS. |
| Other nodes | `/dev/video1` and `/dev/video3`: metadata. `/dev/video2`: grayscale capture; not selected. |
| Desktop portals | RemoteDesktop v2 advertises device types 7. GlobalShortcuts interface unavailable. Permission flow, pointer coordinates and pause have not yet been demonstrated. |
| Dependencies | All recorded imports, MediaPipe Tasks import and `pip check` passed. Installed versions retained in reports; no portable hash lock/offline bundle yet. |

Sources: [imports](../reports/01-imports.json), [inventory](../reports/02-inventory.json), [display report](../reports/03-displays.json), [package snapshot](../reports/installed-packages.txt). Reports are local ignored artifacts; sync them separately when needed. Thirty-one unit tests passed on Windows after the guided implementation (synthetic observations and mocked runtime, without camera/model/Qt execution); a target-Linux unit-test result was not supplied for review.

## Controlled camera results

| Run | Captured / processed | Basic geometry | Geometry FPS | Software time median / p95 | Maximum geometry gap |
| --- | --- | --- | --- | --- | --- |
| [720p seated, 60s](../reports/14-seated-720.json) | 890 / 890 | 890 (100%) | 14.80 | 28.71 / 39.59 ms | 76.77 ms |
| [1080p seated, 60s](../reports/15-seated-1080.json) | 890 / 890 | 890 (100%) | 14.80 | 36.68 / 47.44 ms | 86.31 ms |
| [720p seated, 600s](../reports/16-seated-720-ten-minutes.json) | 8,898 / 8,898 | 8,892 (99.9326%) | 14.82 | 28.98 / 39.17 ms | 340.41 ms |

All three runs completed with the requested dimensions and MJPG format, no reported capture errors, no stuck capture thread and no identical consecutive frames. The ten-minute run had six `no_face` observations. Its longest capture-read gap was 77.79 ms; the longer 340.41 ms geometry gap reflects missing observations, rather than a comparably long camera-read stall. The aggregate report does not identify the cause or exact timeline of those six observations.

Software timing is read-completion to processing result; it excludes exposure, sensor/driver buffering and desktop dispatch. It is not end-to-end eye-to-pointer latency. Aggregate timing is comparable to the short runs; per-minute thermal or performance trends cannot be reconstructed from these reports.

Median eye widths were approximately 41/40 pixels at 720p and 57/55 pixels at 1080p in the short runs, and 36/36 pixels in the sustained run. These are predicted corner-to-corner spans, not pupil resolution. The extreme normalized iris positions seen in exploratory reports are absent from these controlled reports. This supports plausibility, not measured landmark or gaze accuracy.

## FPS investigation

1. Initial OpenCV runs delivered approximately 14.8 FPS, with and without inference/preview; processing kept up with captured frames.
2. [Direct V4L2 with dynamic frame rate enabled](../reports/12-v4l2-direct.txt) captured 300 frames in 29.918s, approximately 10 FPS. [Before](../reports/12-controls-before.txt) and [after](../reports/12-controls-after.txt) control snapshots both showed `exposure_dynamic_framerate=1`.
3. [Direct V4L2 with the control set to zero in the same invocation](../reports/13-v4l2-dynamic-off.txt) approached 29.66 FPS and took 10.389s for 300 frames. The camera has therefore demonstrated approximately 30 FPS at 720p MJPG.
4. The application now offers `--disable-dynamic-fps`, applies it after mode setup and verifies zero before capture. Reports 14-16 confirm this readback, but measured capture delivery remains near 14.8 FPS. Readback during streaming is not recorded. Do not attribute the remaining difference to a proven cause.

The option leaves the control applied. Restoring the earlier value is explicit: `v4l2-ctl -d /dev/video0 --set-ctrl=exposure_dynamic_framerate=1`. The verified setting improves the direct V4L2 test; it has not restored 30 FPS in the application.

## Model and interpretation

`--model models/face_landmarker.task` loads pretrained weights. Camera commands always read LIVE `/dev/video0`; absence of `--preview` hides the window, not capture. Frames and temporary crops remain in memory. The task is Face Landmarker, with a Face Mesh V2 landmark model; the preview is ordinary OpenCV crop/resize/drawing, not an image enhancement model. Five displayed markers per eye represent two corners, upper/lower eyelid points and iris center.

Synced model SHA-256 matches the inference reports:

```text
64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff
```

The hash establishes consistency of the tested local bytes, not independent publisher authentication. Model weights are not being trained or personalized in these runs.

The existing `mediapipe478-eye-diagnostic-v1` adapter checks finite, in-frame landmarks and nondegenerate eye width. It can accept implausible iris positions, so `geometry_fraction` is basic geometry availability, not recognition accuracy. It also cannot certify lid tracking during closure. The new `guided` command uses `mediapipe478-eye-diagnostic-v2`: independent eyelid and iris validity, broad outlier rejection, and per-phase summaries. The existing `camera` command retains version 1 measurement semantics. Do not compare these validity counts as identical metrics.

## Guided run 17 review

Source: [17-guided-baseline.json](../reports/17-guided-baseline.json). All 23 phases completed over 106 seconds; status `recorded`, no error, 1,572 captured and processed frames, no exact consecutive duplicates, 14.83 processed FPS. Read-gap maximum was 76.80 ms. Read-completion-to-result median/p95 was 26.13/33.51 ms, excluding exposure and display latency. The tested model hash is unchanged.

The analyzed face-loss window contained 35 no-face observations out of 37 frames. Both subsequent return and final-center windows had 100% face/eyelid/iris availability. This supports reacquisition; these aggregates do not establish exact recovery latency. All other analyzed windows had 100% face and eyelid availability. A few iris outliers occurred during preparation for face loss. The report has 43 no-face frames overall, including settling periods.

Two issues prevent treating this as gaze/closure validation passing:

1. **Horizontal feature response is weak.** Left-versus-right median iris-x separation is 0.01075/0.01088 eye widths for the right/left eye, approximately 0.41/0.42 source pixels using the initial median eye widths. Initial-to-final center change is larger, 0.02301/0.02528 eye widths. Vertical medians show an up/down response, but one trial with overlapping ranges and some pose variation does not establish repeatability or screen accuracy. The user subsequently confirmed looking back to read instructions or watch the preview, so these windows mix intended fixation with other gaze directions.
2. **Closures change the signal but visibility is not established.** Closure/open median openness ratios are below 1 in both eyes (table below), with reopening returning toward open values. However, every analyzed closure frame still passes iris sanity checks; no `iris_not_used_near_closure` rejection occurs. Broad geometric plausibility must not be used as proof of iris visibility. If the eyes were fully closed as prompted, this indicates the current predicted geometry and fixed near-closure gate do not reliably exclude closed-eye iris estimates. Do not raise a threshold from these aggregates alone or declare blink recognition successful.

| Closure | Right closed/open openness | Left closed/open openness |
| --- | --- | --- |
| 1 | 0.686 | 0.647 |
| 2 | 0.726 | 0.707 |
| 3 | 0.658 | 0.559 |

These ratios are diagnostic feature ratios, not physical percentages of eyelid opening. Natural-blink timing/count cannot be recovered from the saved aggregates. The manual template remains blank, but subsequent chat clarification supplies action notes: the user thinks closures started late, explicitly reports reopening early in trial 1, and confirms looking back at instructions/preview during directional phases. Exact closure durations remain unknown. Report setup distance is null and lighting is not recorded. Successful execution supports camera/model integration; UI readability, cue audibility and target-Linux unit-test output remain unconfirmed.

Interpretation after clarification: all three closure windows show lower median openness in both eyes, but their timing cannot establish a clean fully-closed interval. Looking back at the preview confounds directional separation. Neither finding proves a model failure, and timing alone is not proven to explain all of the residual openness or iris estimates. Preserve report 17 as exploratory feature evidence. Next: improve fixation targets, preparation time and audible closure/reopening cues, then repeat with confirmed actions before assessing feature quality. Do not change detection thresholds to fit this run. Keep capture accepted provisionally at ~15 FPS. Do not advance to dataset collection or calibrated gaze/blink claims on this evidence. The [guided procedure](GUIDED_VALIDATION.md) remains the protocol reference.

## Protocol v2 implementation

Following the user's proposal, instructions now appear at the requested fixation location in a fullscreen window with no camera preview. Each phase excludes its first and last second from phase aggregates; inference continues through those buffers. Closure prompts last four seconds, leaving a two-second measured middle window. The updated 116-second sequence is `eye-motion-closure-v2`; feature sanity limits are unchanged. Run 17 and its interpretation above remain historical evidence.

Thirty-four automated tests passed on Windows, including buffer exclusion, denominator boundaries, target-card geometry and mocked interrupted/error paths. Run 18 subsequently exercised this implementation; see the reviewed results below. See [the updated procedure](GUIDED_VALIDATION.md). This is an implementation change, not new evidence of gaze or closure accuracy.

## Guided run 18 review and user clarification

Source: [18-guided-targets.json](../reports/18-guided-targets.json), protocol v2. All 23 phases completed over 116 seconds, with 1,721 captured/processed frames, no reported errors or exact consecutive duplicates, and 14.84 processed FPS. Software timing median/p95 was 25.77/34.25 ms. Counts reconcile: 338 leading-buffer + 1,040 measured-window + 343 trailing-buffer observations = 1,721. The model hash and sanity thresholds are unchanged.

**Decision:** accept basic direction-related feature response, deliberate closure response and eventual face reacquisition as sufficient to proceed to remaining native desktop validation. This is a prototype feasibility checkpoint, not gaze accuracy, repeatability across sessions or reliable blink/click classification. No full guided rerun is currently needed.

- Horizontal median iris-x separation between left and right is 0.05096/0.04935 eye widths (right/left eye), versus 0.01075/0.01088 in run 17: approximately 4.74/4.54 times larger. These are descriptive feature separations under different protocols, not accuracy improvements. Both eyes shift in opposite directions for left versus right relative to initial center; vertical medians similarly separate up and down. The initial-to-final center horizontal differences, 0.00360/0.01442 eye widths, are smaller than left-right separation. Head-pose proxies vary somewhat, and there is only one trial per direction.
- All three measured closure windows have 100% face and eyelid availability, with substantially lower openness in both eyes. First and second reopening medians return to approximately 98-99% (right) and 95% (left) of their respective preparation values. The third reopening medians remain at 36%/26%; the user confirmed reopening late or blinking/closing again during that phase. Do not count it as a verified failure to recognize open eyes.
- Iris plausibility is still not a visibility detector. Both eyes pass iris checks throughout closure 1; the left-eye near-closure gate rejects 18/30 and 12/30 measured frames in closures 2/3, while the right-eye gate does not reject these closure observations. A future controller needs calibrated closure handling; it must not treat remaining iris coordinates as usable gaze simply because geometry is plausible.
- All 30 measured face-loss observations have no face. The return window has 58/60 faces and final center has 60/60 faces with valid eyelid/iris geometry. This supports reacquisition but does not measure its exact latency or validate controller recovery behavior.

| Closure | Right closed/open openness | Left closed/open openness |
| --- | --- | --- |
| 1 | 0.572 | 0.334 |
| 2 | 0.484 | 0.218 |
| 3 | 0.504 | 0.239 |

The user confirms fullscreen operation, readable instructions and correct left/right/top/bottom positioning. The saved `display.window_logical_size` is nevertheless 100x30, with correspondingly tiny card coordinates, while screen geometry is 1648x1030. Code inspection found the metadata was sampled immediately after requesting fullscreen, before later GUI events/warmup. That snapshot is not trustworthy as the measurement-time target layout. The user-confirmed layout and feature response remain usable qualitative evidence; do not use the saved card coordinates for calibration.

Fixed reporting for future runs: preserve `display_before_capture` separately and populate primary `display` at the first measured phase after GUI event processing and warmup. It is null if no phase begins. This does not alter stimulus timing or feature math, and does not reconstruct run 18's true layout; the raw report remains unchanged. A regression test simulates delayed geometry. All 35 automated tests pass on Windows; the metadata fix still awaits an eventual Linux run, with no extra full run requested just for this fix.

Next: validate native Wayland motion, display-coordinate mapping, global pause and remaining applicable environment checks before personal data collection. Measured viewing distance, lighting details, audio-cue observations and target-Linux unit-test output remain unprovided.

## Native pointer validation prepared; Linux results pending

Added a static fullscreen target chart with geometry recorded on close, optional pause-command acknowledgement output for testing a GNOME shortcut, and portal reports preserving completed moves plus attempted/acknowledged absolute calls after normal failures. Pointer outputs refuse overwrite; phase permissions and stop behavior remain explicit. Closing the chart requests pause, but only the configured GNOME shortcut tests stopping while an unrelated application is focused.

Forty-six automated tests pass on Windows with mocked native interfaces, including consent denial, session revocation, pause, partial failures, lock rejection and coordinate conversion. No actual cursor movement or desktop integration was tested on Windows. Follow [the Linux procedure](POINTER_VALIDATION.md) for reports 19–26. No new hardware/desktop acceptance is claimed; native coordinates, global pause and preferred libei support remain unresolved.

## Evidence limits and unfinished checks

- Earlier reports 05, 09 and 10 are exploratory: the user moved away or changed setup. They cannot establish comparative resolution performance or sustained detection reliability. Report 10 contains model results despite a pasted command omitting `--model`.
- Earlier screenshots showed strong backlighting. The exact lighting arrangement, measured viewing distance, display brightness/lid angle, power source and thermal observations for the controlled runs are not recorded. Approximately 70 cm is the intended condition, not a verified measurement.
- Basic direction-related and deliberate-closure feature responses were demonstrated in run 18. Gaze accuracy, repeated-session stability, ordinary-blink separation, glare challenges and distance tolerance remain unverified.
- The 340 ms observation gap must lead to appropriate freeze/cancellation/disarming in a future controller. That controller behavior is not implemented or tested by these camera probes; loss of tracking must not be interpreted as a blink.
- Native motion, global pause, consent denial/revocation and applicable capture recovery checks remain pending. Portal availability is not proof of functional input. The preferred libei path remains untested.
- Offline startup was designed for local operation, but a reviewed offline smoke test, network-attempt audit and persisted-file inspection have not been provided.
- Personal dataset collection, estimator training, calibration, independent gaze validation, click testing and deployment have not started.

Next work is defined in [NEXT_STEP.md](../NEXT_STEP.md). No further baseline rerun is required unless conditions change or a new diagnostic question justifies it.
