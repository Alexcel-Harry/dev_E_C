# Next step

Updated: 2026-10-23 (America/Los_Angeles).

**Status: target-local instructions and both one-second buffers implemented. Awaiting Linux run 18 using protocol v2.**

## Current position

The one-minute seated runs at 720p and 1080p and the ten-minute 720p run are complete. Capture and basic landmark stability are satisfactory for continuing a prototype at approximately 15 FPS. Full hardware/desktop validation is not complete. The initial 20 usable gaze updates/s target has not been demonstrated; 15 FPS is a provisional development baseline, not a release acceptance result.

Read [the validation status](docs/VALIDATION_STATUS.md) for evidence and limitations. Do not repeat the completed baseline runs without a changed setup or a specific diagnostic reason.

## Next action: execute protocol v2 on Linux and return run 18

The first [guided report](reports/17-guided-baseline.json) completed successfully at 14.83 processed FPS. The user reports possibly closing late, reopening early in the first trial, and looking back at instructions/preview during directional phases. These action notes are recorded in the status document; measured setup details remain missing. Horizontal iris-feature separation is weak relative to center variation; closure phases retain plausible iris geometry throughout despite lower eyelid openness. These are feature-validation concerns, not a new capture failure. See [the reviewed evidence](docs/VALIDATION_STATUS.md).

Implemented fullscreen target-local instructions, no competing camera preview, one-second leading/trailing exclusions, and four-second closure prompts with two measured seconds. Phase-change beeps remain desktop-dependent. Follow [the updated procedure](docs/GUIDED_VALIDATION.md) and return `reports/18-guided-targets.json` plus actual-action notes. Hold the target/action throughout both buffers. Protocol v2 lasts 116 seconds plus warmup; run 17 is preserved as exploratory evidence. No detector thresholds changed.

- [x] Review the geometry validity checks: earlier exploratory runs counted clearly implausible iris positions. Add and test gross-outlier rejection before presenting any new metric as usable-eye validity. Version changed feature/validity semantics and retain the old reports.
- [x] Make the preview preserve eye-crop aspect ratio and clearly label current observation validity. Enlarged pixels must not be described as recovered eye detail.
- [x] Prepare explicit phases: eyes open at center; look left/right/up/down with head approximately still; ordinary blinks; several comfortable deliberate closures; brief face loss and return.
- [x] Summarize observations by phase so overall availability cannot conceal a failure specifically during closure. Do not require visible irises as a condition for reliable eyelid closure observations.
- [ ] Verify that eye-only movement changes iris features plausibly and repeatably, and that eyelid features distinguish open and closed eyes. Treat face loss and unreliable landmarks as invalid, not as a blink.
- [x] Implement aggregate-only reporting and a manual results template; no images, raw video or numeric traces are saved.
- [x] Execute the guided run on Linux and sync the JSON: report 17 completed all phases.
- [x] Record user-reported closure timing and return of gaze to instructions/preview.
- [ ] Supply remaining setup/UI/audio observations and Linux unit-test output. A completed JSON does not verify prompt compliance, UI readability or audio cues.

Implementation: `guided` uses version 2 feature sanity checks with independent eyelid and iris validity; historical `camera` reports retain version 1 semantics. All 34 unit tests passed on Windows using synthetic observations and mocked runtime paths.

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
| 2026-10-23 | User resumed. Implemented guided phases, separate eyelid/iris sanity checks, aspect-preserving preview and aggregate reports; 31 tests passed. | Run guided validation on Linux; review phase results before native input checks or data collection. |

| 2026-10-23 | Reviewed guided report 17: stable capture and face reacquisition; weak horizontal iris separation and incomplete closure interpretation. | Confirm performed actions, then target feature validation; defer training and input validation progression. |

| 2026-10-23 | User reported possibly late closures, early reopening in trial 1, and looking back at instructions/preview. Run 17 is confounded for feature-quality conclusions. | Improve fixation targets and closure cues, then request a controlled repeat; keep raw report unchanged. |

| 2026-10-23 | Implemented user-requested target-local instructions and 1s / measure / 1s windows, protocol v2; 34 tests passed. | Execute run 18 on Linux; review fixation/closure response with manual action notes. |
