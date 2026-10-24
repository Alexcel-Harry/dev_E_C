# Next step

Updated: 2026-10-23 (America/Los_Angeles).

**Status: run 18 reviewed; basic eye-motion and closure response accepted provisionally. Next: native Wayland motion and global pause validation.**

## Current position

The one-minute seated runs at 720p and 1080p and the ten-minute 720p run are complete. Capture and basic landmark stability are satisfactory for continuing a prototype at approximately 15 FPS. Full hardware/desktop validation is not complete. The initial 20 usable gaze updates/s target has not been demonstrated; 15 FPS is a provisional development baseline, not a release acceptance result.

Read [the validation status](docs/VALIDATION_STATUS.md) for evidence and limitations. Do not repeat the completed baseline runs without a changed setup or a specific diagnostic reason.

## Completed: guided eye movement and closure feasibility

[Run 18](reports/18-guided-targets.json) completed at 14.84 FPS. Left/right and up/down produce clearer directional feature separation. Both eyes show lower openness in all three closures; the first two reopenings recover toward their open baselines. The user confirms late reopening or additional blinking/closure in the third reopening window, and confirms readable fullscreen targets in the correct positions. Face reacquisition is observed. See [validation status](docs/VALIDATION_STATUS.md) for values and limits.

This is sufficient to continue environment validation, not a claim of gaze accuracy or gesture reliability. Iris geometry can still look plausible during closed eyes. Do not tune thresholds from this single run, or count prompt windows as verified action labels. No full guided rerun is requested now.

A reporting bug captured window geometry before fullscreen configuration completed. Primary display metadata now records geometry at measurement start, preserving the earlier snapshot separately. Run 18 is unchanged; its saved target-card coordinates are not suitable for calibration. The fix and existing logic pass 35 Windows tests; eventual Linux verification remains pending.

- [x] Complete controlled short and sustained capture baselines.
- [x] Implement versioned feature checks, separate eyelid/iris summaries and buffered target-local cues.
- [x] Review run 18 and user notes for basic directional, closure and reacquisition responses.
- [ ] Retain measured distance/lighting, audio observations and Linux unit-test results when supplied.

## Next action: complete remaining environment checks

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

| 2026-10-23 | Reviewed run 18 and user clarification; accepted basic eye/closure response. Fixed premature display metadata snapshot; 35 tests pass. | Native Wayland motion, coordinate mapping and global pause checks; no full guided rerun required. |
