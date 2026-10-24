# Validation status

Updated: 2026-10-24 (America/Los_Angeles). This record summarizes user-executed Linux tests and synced reports. Windows is the development/review device. Guided runs 17 and 18 have been reviewed; basic eye-motion/closure response is accepted provisionally; [NEXT_STEP.md](../NEXT_STEP.md) is the maintained action queue.

## Decision

The one-minute controlled runs at 720p/1080p and ten-minute 720p run support continuing the prototype with the current camera. Select **1280x720 MJPG, approximately 15 observed updates/s**, as the provisional baseline because it provides comparable basic detection coverage with lower processing cost. Retain 1080p for a later accuracy comparison. No new camera purchase is indicated by these measurements.

This is acceptance of capture and basic-landmark stability for development, not full hardware validation, gaze accuracy, blink recognition, or release readiness. The original plan's 20 usable gaze updates/s target remains unmet. The user accepts exploring slower tracking; the FPS investigation is deferred, not resolved.

The original `Linux_Eye_Tracking_Technical_Plan.docx` (19 October 2026, v1.1) remains the historical design reference. This status record documents observed differences from its assumptions: Python 3.13.5 rather than proposed 3.12, a provisional ~15 FPS application baseline, and EIS native mapping/active pause now verified for the tested setup, with remaining permission/lifecycle checks pending. No later plan milestone is declared complete.

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

## Pointer run 20: no input grant (2026-10-24)

Initially reviewed from JSON pasted by the user from `~/Desktop/YihaoSun/temp/reports/20-wayland-motion.json`; the original error report is now also synced as [20-wayland-motion.json](../reports/20-wayland-motion.json). Status `error`, stage `Start`, message `Pointer permission was not granted`, `granted_devices: 0`, no commands or motion calls, and acknowledged session close. The program therefore stopped before native coordinate dispatch. This run does not test coordinate mapping or active-motion pause.

The user saw a screen-selection dialog. Manual pointer movement to complete consent is expected. GNOME's upstream dialog separately gates input devices on its Allow Remote Interaction switch. A disabled switch is a plausible explanation, not a confirmed account of the user's selection. Next: retry with that option explicitly enabled and a fresh output path from the project root. If absent/already enabled or still failing, inspect the consent screenshot and new JSON before changing the backend. No runtime changes were made for this troubleshooting step.

## Pointer run 20 retry: motion dispatch completed (2026-10-24)

Sources: [20-wayland-motion-retry1.json](../reports/20-wayland-motion-retry1.json) and [19-pointer-targets.json](../reports/19-pointer-targets.json). The retry completed with status `recorded`, no error, `granted_devices: 2`, six acknowledged absolute-motion calls and `sequence_complete: true`. There was no unexpected session closure during the sequence, and final Session.Close was acknowledged. The user confirms no manual mouse movement during the automatic sequence. The previous missing pointer grant is resolved for this retry; no backend/code change was needed.

The portal's `size` is 1648x1030, matching the chart's fullscreen logical dimensions on eDP-1, DPR 2. Sent coordinates match chart marker coordinates within rounding (at most 0.5 logical units per axis). This establishes consistent coordinate inputs, not the resulting on-screen cursor positions. The later user observation below establishes that visual hotspot-to-cross alignment failed.

`pause_observed: false` is expected in this uninterrupted trial. The chart requested pause on close after the motion report was written; this does not demonstrate stopping an active sequence or a global shortcut. Reports 21–26 were not present at review, so shortcut acknowledgement, active pause, full consent cancellation, revocation and single-instance behavior are still unreviewed. The original no-device grant test is not equivalent to cancelling the whole consent dialog.

The initial proposed next step was visual confirmation followed by active pause. The later failed-alignment observation supersedes that plan: investigate coordinate mapping before report 22. This establishes only the existing legacy portal compatibility path; libei remains untested.

## Pointer visual mapping failed; scale diagnostic prepared (2026-10-24)

The user reports no manual movement during the sequence, but the cursor never reached the right half; upper-right appeared near upper-center, center was too far left, and upper-left did not land on its numbered target. This is a failed coordinate-mapping check. Permission/dispatch success remains valid. Raw reports 19 and 20 retry are preserved unchanged. The observation supplies no precise measured offsets or complete vertical positions.

The chart's DPR is 2. Dividing the sent x coordinate by 2 would place nominal center near 25% and nominal right near 45% of the display, consistent with the horizontal observation. This is a hypothesis, not a measured transform.

Supporting source evidence: [GNOME Mutter's gnome-46 monitor-stream implementation](https://raw.githubusercontent.com/GNOME/mutter/gnome-46/src/backends/meta-screen-cast-monitor-stream.c) advertises logical monitor dimensions as `size`, while its legacy position transformation divides stream coordinates by monitor scale when stage views are scaled. This can explain the symptom. The installed compositor version and effective transform have not yet been confirmed; do not assume all Wayland or GNOME versions need the multiplier.

Added explicit `--portal-coordinate-scale` (finite, greater than 0 and at most 4; default 1). It is restricted to Wayland when non-default, scales both submitted axes, retains advertised metadata, and records the multiplier, formula, unscaled and submitted coordinates. It does not change display settings or infer a multiplier from Qt DPR. Tests cover unchanged default dispatch, compensation for a simulated 2x backend division, pause with the override, propagation through the runner, and invalid/X11 rejection. All 49 Windows tests pass with simulated native interfaces; no Linux success is claimed.

Historical next action (superseded by the run 28 review below): focused scale diagnostic, reports 27-29. Use multiplier 2 at the unchanged display setup, retain desktop versions, and obtain visual arrow-tip alignment for all targets on both axes. If confirmed, record a configuration-specific legacy workaround; preferred libei and active global pause remain separate unfinished checks. If it fails, inspect the new evidence before selecting another transform. No camera rerun or gaze-model adjustment is indicated by this desktop mapping failure.

## Run 28: scale-2 diagnostic rejected (2026-10-24)

Reviewed [27-pointer-targets-scale2.json](../reports/27-pointer-targets-scale2.json), [28-wayland-motion-scale2.json](../reports/28-wayland-motion-scale2.json), and the user's upper-left photograph. Report 27 retains fullscreen logical 1648x1030, eDP-1, DPR 2. Report 28 has pointer grant 2, multiplier 2, two completed moves, and an attempted third move. Center [1647,1029] and upper-left [329.4,205.8] were acknowledged; upper-right [2964.6,205.8] failed with `NotifyPointerMotionAbsolute: org.freedesktop.DBus.Error.Failed: ['Invalid position']`. Sequence incomplete, pause false, session close acknowledged.

The attempted third x coordinate is outside the advertised 1648-wide stream. Upstream [xdg-desktop-portal 1.18.4 bounds validation](https://raw.githubusercontent.com/flatpak/xdg-desktop-portal/1.18.4/src/remote-desktop.c) checks submitted positions against advertised stream dimensions and emits this error when outside. This explains the observed rejection; the exact installed version remains unprovided. The earlier 2x diagnostic considered the compositor transformation but overlooked this frontend constraint. It is not a usable full-screen correction. Do not clamp coordinates and call mapping fixed: that would discard the intended target location.

The photograph shows the arrow tip below/right of the upper-left cross. This is qualitative evidence of residual offset, not a calibrated measurement; perspective and cropping prevent an exact desktop-coordinate estimate. The right-side targets were never acknowledged in this run. A compositor scaling mismatch remains plausible but is not fully characterized by these records.

Decision: retire the scale-2 rerun instruction, retain reports unchanged, and obtain missing report 29's desktop versions before selecting an EIS/libei or version-specific backend correction. No runtime code changed in this review. Previous simulated test success omitted this bounds interaction and does not certify the failed native path. Add that case when implementing the backend correction. Active pause and later validation remain pending.

## Desktop versions reviewed; EIS validation implemented

The user supplied GNOME Shell 46.0 (`46.0-0ubuntu6~24.04.16`), Mutter `46.2-1ubuntu0.24.04.18`, xdg-desktop-portal `1.18.4-1ubuntu2.24.04.3` and xdg-desktop-portal-gnome `46.2-0ubuntu1`. These align with the upstream major-version code paths investigated, although downstream packages can include patches. Version information is complete from chat; a raw report 29 is not fabricated. The existing [inventory](../reports/02-inventory.json) already lists libei1/libeis1 `1.2.1-1` and RemoteDesktop interface version 2.

Decision: test the preferred EIS transport, retaining portal consent and unchanged display configuration, rather than using the failed multiplier as a workaround. Added explicit `--backend eis`: ConnectToEIS with Unix-fd negotiation, an absolute-motion-only libei sender, device readiness/lifecycle processing, mapping-ID region selection or an unambiguous single-region fallback, region-relative normalized targets including the region offset, and bounded waits. Physical scale is recorded, never multiplied into the absolute positions. No legacy Notify method is called on an EIS session, and failures do not fall back. Existing motion opt-in, pause polling, single-instance lock and worker deadline remain. EIS submissions are recorded as `submitted`, not cursor acknowledgements. Errors are now printed in the terminal as well as saved.

The old legacy probe now preflights every target against the advertised bounds and rejects the failed scale-2 sequence before motion. Its tests now include this missing constraint. Sixty Windows tests pass using mocked native interfaces: direct region coordinates and offsets, matching/ambiguous region handling, readiness, device/seat/disconnect loss after a move, global pause, descriptor cleanup, handshake failure cleanup, no legacy fallback, and existing validations. No actual Linux libei handshake, ABI execution or cursor position has been tested on Windows.

Next: [EIS procedure](POINTER_VALIDATION.md#current-diagnostic-eis-motion-at-unchanged-display-scale), fresh reports 30 (chart), 31 (motion), 32 (Linux unit tests), and manual alignment observations. No additional dependencies are expected from the supplied inventory. Do not repeat camera validation or change gaze features for this desktop-coordinate issue. After visual mapping is confirmed, test active pause and permission/session behavior on the EIS path; collection/training remains deferred.

## Run 31: native EIS connection works; equivalent regions triggered a false stop

Evidence: JSON and console output pasted by the user; the user also reports that all Linux tests passed. The raw run-31 JSON was not present locally at this review. Portal pointer grant is 2. EIS event types are `[1,3,5,8,5,8]`: connection, seat added, then two added/resumed device pairs. Both advertised regions have offset (0,0), dimensions 1648x1030, physical scale 1.7475727796554565 and the same nonempty mapping ID, matching the portal's mapping ID. The first region was selected before the second device was processed; the movement-time guard required exactly one candidate and incorrectly raised `EIS display configuration changed; repeat validation`.

No commands or motion calls were sent. EIS context release and portal session close both completed. This confirms native library loading, EIS connection and device readiness on Linux, but not motion submission or visual alignment. The error does not establish that the user changed displays. The physical-scale value differs from Qt DPR 2; keep it as reported metadata and do not use either as an absolute-coordinate multiplier.

Fixed candidate handling at readiness and before each move: equivalent candidates must share a nonempty mapping ID and identical geometry/physical-scale metadata. Select one resumed device, retain it through later equivalent announcements, and send each target only once. Regions with conflicting geometry, scale or unidentified duplicates are rejected. Selected-device pause/removal still stops the probe even if an equivalent device remains; there is no automatic failover. The report records the number of equivalent candidates while preserving all announcements.

The [libei region API](https://libinput.pages.freedesktop.org/libei/api/group__libei-region.html) explicitly allows duplicate mapping IDs, including during resize transitions. An ID alone is therefore insufficient, which is why this correction also checks complete region metadata. It does not claim to support monitor resizing during a trial.

All 64 local tests pass with mocked native interfaces. Four regression tests cover the run-31 event order with early/late duplicates, selecting a resumed equivalent device without later switching, rejecting conflicting/unidentified regions, and stopping on selected-device loss despite another equivalent device. Earlier 60 tests remain covered. Next: sync the fix, run fresh chart 33, motion 34 and tests 35, and return manual arrow-tip alignment. Preserve original run 31; no camera rerun, new packages or display-setting changes are requested.

## Run 34: native EIS motion and visual mapping accepted

Reviewed synced [33-pointer-targets-eis-retry1.json](../reports/33-pointer-targets-eis-retry1.json) and [34-wayland-eis-motion-retry1.json](../reports/34-wayland-eis-motion-retry1.json). The user confirms that mapping is now very accurate. Run 34 has status recorded, no error, pointer grant 2, all six expected normalized targets in order, six submitted motion calls and sequence_complete true. Both equivalent regions have the same mapping ID as the portal, origin (0,0), size 1648x1030 and physical_scale 1.7475727796554565. No extra motion was emitted for the duplicate. The selected EIS region matches the chart's logical geometry; sent coordinates differ from its rounded marker coordinates by at most 0.5 logical units per axis. That is an input-math comparison, not a measured cursor-error bound.

No unexpected session closure occurred. EIS context release and final portal close succeeded. `pause_observed: false` is normal for the uninterrupted sequence. Chart close requested pause afterward, which does not validate the global shortcut or stopping active motion. Both raw reports retain `manual_coordinate_verification: REQUIRED`; the user's confirmation is recorded here rather than rewriting the raw evidence.

Decision: accept qualitative visual coordinate mapping for the current EIS/laptop/display configuration. Native motion and duplicate-region handling are now exercised on Linux; this does not establish eye-to-screen calibration, gaze accuracy, multi-monitor behavior, behavior after display changes, clicks or controller safety. The earlier legacy path remains failed; use explicit `--backend eis` for subsequent input validation.

The original run 31 is now synced too. The user previously reported Linux tests passed, but raw logs 32/35 are absent; do not invent a retained test result. No runtime changes or test rerun in this review. Next: shortcut acknowledgement report 21 and active EIS pause report 36 with another application focused; then consent denial, available revocation and single-instance behavior. No coordinate rerun is needed now.

## Latest pause-trial clarification: shortcut not exercised

The user pasted another successful six-target EIS report with `pause_observed: false`, `sequence_complete: true`, no error and successful context/session cleanup. Its portal and EIS regions match, with two equivalent candidates. The user then clarified that the shortcut was not pressed / is not configured. This establishes another uninterrupted run, not a pause failure; active stopping remains NOT TESTED. The pasted JSON has no filename, and reports 21/36 are not locally synced at this review, so no raw file is fabricated or assigned to it.

Next: configure the custom keyboard shortcut, verify its acknowledgement while Text Editor is focused, then perform an actual active-pause trial after the first move using `36-eis-pause-retry1.json`. No runtime change is indicated by this result. Previously accepted visual EIS mapping remains accepted.

## Active pause accepted: run 36 retry1 (2026-10-24)

Reviewed synced [36-eis-pause-retry1.json](../reports/36-eis-pause-retry1.json) and [21-shortcut.json](../reports/21-shortcut.json). Run 36 retry1 records `status: recorded`, no error, exactly one submitted target at normalized (0.5,0.5), absolute (823.5,514.5), `pause_observed: true` and `sequence_complete: false`. EIS context release and portal Session.Close acknowledgement are both true. Report 21 records a pause request at `1792831879779439197` Unix nanoseconds. These reports do not contain enough timing information to measure stop latency.

The user confirms physically pressing the laptop shortcut and manually observing movement stop after changing the binding from Ctrl+Alt+P to Ctrl+Alt+Space. Accept active global pause for the diagnostic EIS probe on this setup. Keep the working shell-wrapped command and binding. Earlier Ctrl+Alt+P attempts did not stop the sequence; touch-command and standalone pause checks demonstrated some shortcut launches but did not establish the cause of the failure. Do not label it a proven hardware fault or runtime-directory mismatch.

This result supersedes the earlier pending active-pause status. Raw reports are unchanged. No runtime code changed and no tests were rerun for this documentation review. Next: consent denial (37), available revocation (38), and single-instance behavior (39/40). Production watchdogs, clicks and suspend/lock recovery remain outside this acceptance.

## Consent denial accepted: report 37 (2026-10-24)

Evidence is the user's pasted JSON and terminal output for `reports/37-eis-denied.json`; the raw file is not locally synced at this review. Status error and `Start: permission cancelled or denied (1)` are the expected rejection result. Both commands_sent and motion_calls are empty, sequence_complete is false, and the portal reported session_closed true. Accept consent denial with no native motion dispatched.

The secondary `Close: org.freedesktop.DBus.Error.UnknownMethod` says the session object no longer exists. Code inspection found unconditional final Close even after the Closed signal. This is redundant cleanup after observed closure, not evidence of unauthorized motion or a live session leak. Raw session_close_acknowledged false accurately records that failed redundant call and is not rewritten.

Cleanup now skips Close when closure is already observed, reports `session_cleanup: already_closed_by_portal` and `session_close_acknowledged: null` (no Close call), and still disconnects the bus/releases any EIS context. Without a Closed signal, Close is still attempted and any failure remains visible. The original denial error remains the primary result. All 66 local mocked tests pass, including new EIS denial/Closed regression and preservation of unconfirmed Close failures, plus existing revocation coverage. Linux execution of the fix remains pending; no repeat denial trial is required solely for report formatting.

Next: sync the code and test available desktop revocation during motion (38), then single-instance checks (39/40). Keep Ctrl+Alt+Space as fallback and record whether it was used. No further camera, mapping or active-pause baseline run is requested.

## Portal revocation accepted: report 38 (2026-10-24)

Evidence is the user's pasted JSON and terminal output for `reports/38-eis-revoked.json`; the raw file is not locally synced at this review. Exactly one center target was submitted at (823.5,514.5), then the portal reported `session_closed: true`. The sequence is incomplete, `pause_observed: false`, status recorded, and error null. Accept the diagnostic's response to portal revocation: no subsequent target was submitted. This does not measure stop latency or establish production controller safety.

`eis_context_released: true`, `session_cleanup: already_closed_by_portal` and `session_close_acknowledged: null` confirm the new cleanup branch ran on Linux and skipped the redundant portal Close. Null is not a failed Close acknowledgement; no such call was made. A runtime WARN states `failed to send message: Broken pipe`. Inspection shows EIS cleanup can call stop-emulating and dispatch after portal closure, before the native sender has processed disconnection. That is consistent with the warning, but the console does not identify the exact originating call. Resource release still completed, no eis_cleanup_error is recorded, and no second target was submitted. Do not suppress unrelated errors or claim all teardown messaging is warning-free.

No further runtime change or test rerun is indicated by this result. The prior 66 mocked tests remain the local baseline. Next: single-instance checks 39/40, then review the remaining environment checklist before data collection. Raw reports 37/38 should be synced when available; none is fabricated here.

## Single-instance exclusion accepted: reports 39/40 (2026-10-24)

Reviewed synced [39-eis-lock-holder.json](../reports/39-eis-lock-holder.json) and [40-eis-second-instance.json](../reports/40-eis-second-instance.json), together with the user's passing observation. Run 39 completed all six targets, has no error, sequence_complete true, pause_observed false, EIS context released and portal Close acknowledged. Run 40 is a schema-1 pointer error with `Another pointer probe is running`; it contains no commands_sent or motion_calls fields. Code takes the nonblocking lock before clearing the pause flag or connecting to the portal. Accept exclusion of a second active probe in this test; do not invent zero-count fields or claim measured overlap timing from these reports.

Reports [37](../reports/37-eis-denied.json) and [38](../reports/38-eis-revoked.json) are now synced and consistent with the earlier pasted results. Mapping, active global pause using Ctrl+Alt+Space, denial, portal revocation and single-instance behavior are accepted for this diagnostic setup. No runtime changes or tests were needed for this review; the existing 66 mocked-test baseline remains.

Full environment validation is not declared complete. Next are applicable camera failure/recovery, offline startup, retained-file/permission checks and setup observations in the Linux checklist. Start with invalid-device report 41 and offline recovery report 42. Personal collection, estimator training, calibration and deployment remain sequential later stages.

## Camera failure and recovery: reports 41/42 (2026-10-24)

Reviewed synced [41-invalid-device.json](../reports/41-invalid-device.json) and [42-offline-recovery.json](../reports/42-offline-recovery.json). Run 41 has the expected camera-open error, zero reads/processed frames, and capture_thread_stuck false. Its ~5.5 ms measured interval and startup-inclusive CPU percentage are not useful steady-state performance measurements. Accept invalid-device failure handling.

Run 42 opens 1280x720 MJPG with dynamic-FPS control readback zero, loads the local model, and processes 417 frames with basic geometry valid on all 417 (100%). Processed/geometry rate is 14.7616 FPS; no duplicate frames or geometry failure reasons are recorded. Inference median/p95 are 19.58/29.69 ms, and dequeue-to-result median/p95 are 30.16/41.24 ms; neither is end-to-end gaze latency. Error is null and capture_thread_stuck is false. Accept working-camera/model recovery in a fresh process after the invalid-device attempt.

Status is incomplete, with 28.249 seconds measured of 30 requested. The implementation uses incomplete for early stop, including preview invisibility or KeyboardInterrupt. The user now explicitly confirms run 42 was executed with networking off. Accept the offline startup/local-model inference smoke test from that confirmation and recorded inference. Network state is user-reported, not measured in the JSON or audited for attempted connections.

Although the user reports updated records, the local run-42 file still contains the previously reviewed 28.249-second/417-frame result; do not claim a new full-duration run. The exact early-stop action remains unspecified, and any unexpected preview closure warrants investigation. The early stop does not invalidate observed offline startup/inference, and no repeat is requested merely to reach 30 seconds.

Local inspection of synced reports found 33 JSON and 7 text files, no media files in that directory. Linux permissions, files outside the synced directory and dependency caches are not established. Shutter/contention observations and setup notes remain unprovided; absent tests must not silently become passes. No runtime changes or test rerun in this review.

## Evidence limits and unfinished checks

- Earlier reports 05, 09 and 10 are exploratory: the user moved away or changed setup. They cannot establish comparative resolution performance or sustained detection reliability. Report 10 contains model results despite a pasted command omitting `--model`.
- Earlier screenshots showed strong backlighting. The exact lighting arrangement, measured viewing distance, display brightness/lid angle, power source and thermal observations for the controlled runs are not recorded. Approximately 70 cm is the intended condition, not a verified measurement.
- Basic direction-related and deliberate-closure feature responses were demonstrated in run 18. Gaze accuracy, repeated-session stability, ordinary-blink separation, glare challenges and distance tolerance remain unverified.
- The 340 ms observation gap must lead to appropriate freeze/cancellation/disarming in a future controller. That controller behavior is not implemented or tested by these camera probes; loss of tracking must not be interpreted as a blink.
- EIS native motion and qualitative visual mapping passed in run 34 for the current display setup. The legacy mapping path remains failed. Active global pause passed in run 36 retry1 using Ctrl+Alt+Space. Consent denial passed in pasted report 37. Portal revocation passed in pasted report 38. Single-instance behavior passed in synced reports 39/40. Invalid-device failure and fresh-process recovery passed in 41/42; remaining applicable shutter/contention observations are pending.
- Run 42 demonstrates local-model startup/inference and the user confirms networking was off; the offline smoke test is accepted, with the early-stop duration retained as recorded. Synced reports contain JSON/text only. Linux file permissions, wider persisted-file inspection and network-attempt auditing remain unverified.
- Personal dataset collection, estimator training, calibration, independent gaze validation, click testing and deployment have not started.

Next work is defined in [NEXT_STEP.md](../NEXT_STEP.md). No further baseline rerun is required unless conditions change or a new diagnostic question justifies it.
