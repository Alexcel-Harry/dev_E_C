# Next step

Updated: 2026-10-23 (America/Los_Angeles).

**Status: paused after documentation, at the user's request. Do not start the tasks below until the user resumes work.**

## Current position

The one-minute seated runs at 720p and 1080p and the ten-minute 720p run are complete. Capture and basic landmark stability are satisfactory for continuing a prototype at approximately 15 FPS. Full hardware/desktop validation is not complete. The initial 20 usable gaze updates/s target has not been demonstrated; 15 FPS is a provisional development baseline, not a release acceptance result.

Read [the validation status](docs/VALIDATION_STATUS.md) for evidence and limitations. Do not repeat the completed baseline runs without a changed setup or a specific diagnostic reason.

## First task after resuming: eye movement and closure validation

Prepare a short guided diagnostic using live camera input, with no mouse output and no training dataset collection. Keep the selected 720p MJPG mode, usual glasses, and repeatable lighting. Measure and record the actual viewing distance; 70 cm remains nominal rather than a confirmed measurement.

- [ ] Review the geometry validity checks: earlier exploratory runs counted clearly implausible iris positions. Add and test gross-outlier rejection before presenting any new metric as usable-eye validity. Version changed feature/validity semantics and retain the old reports.
- [ ] Make the preview preserve eye-crop aspect ratio and clearly label current observation validity. Enlarged pixels must not be described as recovered eye detail.
- [ ] Prepare explicit phases: eyes open at center; look left/right/up/down with head approximately still; ordinary blinks; several comfortable deliberate closures; brief face loss and return.
- [ ] Summarize observations by phase so overall availability cannot conceal a failure specifically during closure. Do not require visible irises as a condition for reliable eyelid closure observations.
- [ ] Verify that eye-only movement changes iris features plausibly and repeatably, and that eyelid features distinguish open and closed eyes. Treat face loss and unreliable landmarks as invalid, not as a blink.
- [ ] Return aggregate results plus manual notes; do not save images, raw video, or continuous numeric traces by default. Any optional trace must be explicit, bounded and described.

Completion evidence: a reviewed phase-by-phase report showing whether the features are suitable for subsequent gaze and gesture work. This does not certify screen-pointing accuracy or deliberate-blink click recognition. If features are unreliable, adjust lighting/pose or the feature approach before collecting training data.

## Then: complete remaining environment checks

- [ ] Native Wayland motion: visually verify known positions at the actual display scale using the existing motion-only probe.
- [ ] Configure a GNOME custom keyboard shortcut for `python -m eyecheck pause` via the absolute virtual-environment interpreter path; verify it while another application is focused. The GlobalShortcuts portal is unavailable in the supplied inventory.
- [ ] Check consent denial, session revocation where supported, and single-instance behavior. The legacy portal probe does not certify the preferred libei backend.
- [ ] Complete applicable capture failure/recovery checks, offline smoke test and retained-file inspection from [the Linux checklist](docs/LINUX_CHECKLIST.md). Record unsupported/unperformed checks as NOT TESTED.
- [ ] Record remaining setup details: actual distance, lighting, screen settings, power source and fan/heat observations.

Completion evidence: coordinate/pause behavior and remaining applicable validation checks reviewed; unresolved issues either fixed or explicitly recorded with their scope. No production clicking, watchdog, lock/suspend recovery or button-release lifecycle is implemented or certified yet.

## Deferred investigation

Direct V4L2 reached approximately 29.7 FPS with dynamic frame rate disabled; OpenCV runs remain near 14.8 FPS despite a zero readback before capture. The cause is unresolved. Defer further tuning while assessing feature usefulness at the accepted provisional rate. Revisit if responsiveness, blink timing or the later acceptance tests require it. Do not mark the discrepancy fixed.

## Later stages

After the remaining validation issues are resolved: agree on the collection protocol, collect the personal dataset, train the personal estimator, perform model calibration and independent evaluation, then implement deployment. Keep these stages sequential. No training, calibration or deployment has started.

## Maintenance rules

Update this file after each reviewed result: record the completed step in the history, identify the next concrete task and its completion evidence, and retain unresolved limitations. Put detailed measurements in `docs/VALIDATION_STATUS.md` rather than duplicating all report contents here. Use fresh report filenames and preserve previous evidence.

| Date | Completed / decision | Next action |
| --- | --- | --- |
| 2026-10-23 | Reviewed seated 720p/1080p runs and ten-minute 720p run. Accepted basic stability at a provisional ~15 FPS. Updated documentation. | Paused; on user resume, prepare guided eye-motion/closure validation. |
