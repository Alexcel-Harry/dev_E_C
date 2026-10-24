# Next step

Updated: 2026-10-24 (America/Los_Angeles).

**Status: EIS visual mapping and active global pause verified. Ctrl+Alt+Space is the working binding. Consent denial (37) passed. Next: sync the cleanup fix, test available revocation (38), then single-instance checks (39/40).**

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

## Completed: native EIS coordinate mapping

Reviewed [chart 33](reports/33-pointer-targets-eis-retry1.json), [motion 34](reports/34-wayland-eis-motion-retry1.json) and the user's confirmation that mapping is now very accurate. All six target requests were submitted once in the expected order, with no error or unexpected session closure. Two equivalent EIS regions were accepted; context release and portal session close both completed. EIS geometry is 1648x1030 at origin (0,0), using mapping-ID selection and no scale multiplier. The chart matches that logical geometry; its DPR 2 and EIS physical-scale metadata (~1.74757) are not applied to absolute targets.

Accept visual native-pointer mapping for this tested laptop/display configuration. This is qualitative alignment evidence, not a measured pixel-error bound or eye-to-screen calibration. Preserve earlier failed legacy and EIS reports. No coordinate or camera baseline repeat is needed unless configuration changes or a new diagnostic issue appears.

## Completed: active global pause; next: permission and lifecycle checks

Reviewed synced `reports/36-eis-pause-retry1.json` and `reports/21-shortcut.json`. The active EIS probe submitted only the first center target, reported `pause_observed: true`, `sequence_complete: false`, no error, and successful EIS context release and portal session close. The user manually confirms movement stopped using Ctrl+Alt+Space on the laptop keyboard. Accept active diagnostic pause for this setup; no stop-latency bound or production watchdog certification is inferred.

Keep the existing working Ctrl+Alt+Space shortcut and its shell-wrapped command. Ctrl+Alt+P did not reliably invoke the intended pause action during troubleshooting; a keyboard fault, shortcut conflict or environment mismatch has not been established. No further diagnosis of that unused binding is needed now. Preserve the raw reports. Do not repeat the accepted mapping or pause tests unless conditions change.

## Completed: consent denial; next: active revocation

Reviewed the user's pasted report 37 and terminal output. Cancellation at Start returned permission cancelled or denied (1), no commands or motion calls, and `session_closed: true`. Accept denial behavior. The raw file is not synced at this review; do not fabricate or overwrite it. The subsequent cleanup error came from attempting Close on the already-closed session object.

Adjusted cleanup to skip Close only after receiving the portal Closed signal. It reports `session_cleanup: already_closed_by_portal` and `session_close_acknowledged: null` because no redundant Close call is made. Close errors without a Closed signal remain visible. All 66 local tests pass with native interfaces mocked; the change still needs execution on Linux.

Sync `eyecheck/pointer.py` and `tests/test_pointer.py`, then follow section 3 of [the pointer checklist](docs/POINTER_VALIDATION.md): grant consent for run 38 and revoke it using GNOME's stop-sharing/remote-control control during movement. Keep Ctrl+Alt+Space available as a fallback; using it does not substitute for revocation. Record NOT TESTED if the desktop offers no revocation control. Then test single-instance rejection (39/40). Return reports and manual observations. No accepted denial, mapping or pause rerun is requested, and no new packages are needed.

## Remaining environment checks

- [x] Native Wayland motion: EIS coordinates visually verified in run 34 at the tested display configuration.
- [x] Verify the GNOME global pause shortcut: Ctrl+Alt+Space, active EIS pause accepted from run 36 retry1 and manual observation. The GlobalShortcuts portal remains unavailable in the supplied inventory.
- [x] Consent denial at Start sends no motion (pasted report 37).
- [ ] Check session revocation where supported and single-instance behavior on EIS (38-40).
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

| 2026-10-23 | Prepared static pointer target chart, pause acknowledgement, partial portal reports and Linux checklist. 46 automated tests pass with simulated native interfaces. | User executes native pointer/pause validation and returns reports plus visual observations. |

| 2026-10-24 | Reviewed pasted run 20: no input grant, no motion, clean session close. Clarified separate interaction permission and relative report paths. | Retry with Allow Remote Interaction enabled; inspect dialog/new JSON if the permission is still missing. |

| 2026-10-24 | Reviewed run 20 retry and chart: pointer permission granted, six moves acknowledged, matching logical coordinate sizes, clean session close. User kept hands off. | Confirm visual alignment, then global-shortcut pause during motion; remaining consent/revocation/lock checks pending. |

| 2026-10-24 | User reported failed visual alignment in run 20 retry. Added an explicit logged coordinate-scale diagnostic; 49 simulated tests pass. | Run 27/28 with multiplier 2, retain desktop versions in 29, and review both-axis alignment before active pause validation. |

| 2026-10-24 | Reviewed reports 27/28 and photo: two moves acknowledged, third rejected as Invalid position, upper-left still misaligned, clean session close. Scale-2 workaround rejected. | Obtain missing desktop versions (29), assess backend correction, then prepare a targeted mapping check. |

| 2026-10-24 | Reviewed supplied GNOME/Mutter/portal versions and existing libei inventory. Implemented EIS region-based motion, native lifecycle handling and legacy bounds preflight; 60 simulated tests pass. | Run EIS mapping validation (30-32) at unchanged display settings, then review before active pause. |

| 2026-10-24 | User reports Linux tests passed. Reviewed pasted run 31: EIS ready, equivalent second region triggered a false display-change error, zero motion, clean cleanup. Fixed duplicate handling; 64 local tests pass. | Sync correction and run fresh EIS chart/motion/tests reports 33-35; inspect visual alignment. |

| 2026-10-24 | Reviewed synced chart 33/motion 34 and user-confirmed accurate mapping: six submitted targets, duplicate regions handled, clean cleanup. Accepted visual EIS mapping for this setup. | Verify shortcut acknowledgement (21), then active EIS global pause (36); no alignment rerun needed. |

| 2026-10-24 | Reviewed latest pasted uninterrupted EIS run. User confirms no pause shortcut was pressed / configured, so active stopping was not tested. | Configure and verify shortcut acknowledgement (21), then retry active pause to 36-eis-pause-retry1.json. |

| 2026-10-24 | Reviewed synced 36-eis-pause-retry1 and 21: one center move, pause observed, incomplete sequence, clean cleanup; user manually confirms Ctrl+Alt+Space stopped movement. | Accept active diagnostic pause; proceed to EIS denial (37), available revocation (38), and lock checks (39/40). |

| 2026-10-24 | Reviewed pasted report 37: denial at Start, zero motion, portal closure observed; redundant Close produced a secondary cleanup error. Skip Close after confirmed closure; 66 mocked tests pass. | Sync cleanup fix, test available revocation (38), then single-instance behavior (39/40). |
