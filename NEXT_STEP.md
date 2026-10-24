# Next step

Updated: 2026-10-24 (America/Los_Angeles).

**Status: legacy coordinate mapping failed. Desktop versions reviewed; EIS/libei motion validation is implemented and awaits Linux execution (reports 30-32).**

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

## Next action: validate native EIS/libei coordinates

User-supplied desktop versions: GNOME Shell 46.0 (`46.0-0ubuntu6~24.04.16`), Mutter `46.2-1ubuntu0.24.04.18`, xdg-desktop-portal `1.18.4-1ubuntu2.24.04.3`, GNOME portal `46.2-0ubuntu1`. Existing inventory already lists `libei1 1.2.1-1`. The requested version information is complete; no need to rerun report 29.

Run 20 retry moved the cursor but failed visual alignment. Run 28's scale-2 override acknowledged two moves, then exceeded the portal's advertised bounds; the photograph also showed residual upper-left offset. Keep both reports unchanged. A new preflight check rejects a legacy sequence that would exceed bounds before sending its first move. Do not repeat scale-2 or clamp the failed targets.

Implemented an explicit `--backend eis` option. It keeps the portal consent/session and pause/lock logic, obtains the EIS connection, binds only absolute motion, waits for a resumed device, and maps normalized targets into the compositor's EIS region. Region offset and dimensions determine coordinates; physical scale is recorded but not multiplied. A stream mapping ID selects its matching region when supplied; otherwise exactly one region is required. Ambiguity or lifecycle loss stops the probe without falling back to the legacy path. EIS calls are logged as submitted, not acknowledged cursor positions.

Sync `eyecheck/`, `tests/`, `docs/`, `README.md`, and this file, preserving Linux environments/models/reports. Follow the current procedure in [POINTER_VALIDATION.md](docs/POINTER_VALIDATION.md): verify the pause shortcut, run tests to report 32, open the static chart (30), and run the EIS motion test (31). Keep the same display settings, select the laptop screen with Allow Remote Interaction, focus the chart during the five-second countdown, then keep hands off. Return reports 30-32 plus arrow-tip alignment at each cross on both axes. Stop for review before active pause/denial/revocation trials.

Sixty Windows tests pass using simulated native interfaces, including region mapping, descriptor cleanup, device lifecycle loss, pause, no legacy fallback, and the legacy bounds regression. This does not establish the actual Linux libei ABI, compositor handshake or visible mapping. No new pip dependency, compiler, or system upgrade is required; the native library is already in the supplied inventory. If it cannot load or the handshake fails, return the error report instead of installing guessed packages.

## Remaining environment checks

- [ ] Native Wayland motion: visually verify known positions at the actual display scale using the explicit EIS motion-only probe.
- [ ] Configure a GNOME custom keyboard shortcut for `python -m eyecheck pause` via the absolute virtual-environment interpreter path; verify it while another application is focused. The GlobalShortcuts portal is unavailable in the supplied inventory.
- [ ] Check consent denial, session revocation where supported, and single-instance behavior. Repeat the remaining behavior checks on EIS after its visual mapping is confirmed.
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
