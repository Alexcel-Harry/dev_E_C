# Next step

Updated: 2026-10-25 (America/Los_Angeles).

**Status: the collection/toggle approach is accepted. SSS is reserved for middle-button toggle; other detailed bindings are deferred. Plans now separate gaze fitting, gesture threshold fitting, negative-reading evaluation and controller tests. Next implement acquisition with calibration and continuous gesture records, then three Linux pilots. No acquisition, model fitting or desktop-button behavior has started.**

## Current position

The one-minute seated runs at 720p and 1080p and the ten-minute 720p run are complete. Capture and basic landmark stability are satisfactory for continuing a prototype at approximately 15 FPS. Full hardware/desktop validation is not complete. The initial 20 usable gaze updates/s target has not been demonstrated; 15 FPS is a provisional development baseline, not a release acceptance result.

Read [the validation status](docs/VALIDATION_STATUS.md) for evidence and limitations. Do not repeat the completed baseline runs without a changed setup or a specific diagnostic reason.

## Current: documented collection and calibration design

See [DATA_COLLECTION_PLAN.md](docs/DATA_COLLECTION_PLAN.md) for conditions, timing, UI flow, storage, dataset scale and evaluation separation, and [MODEL_ARCHITECTURE.md](docs/MODEL_ARCHITECTURE.md) for the pretrained front end, per-session fitting and personal correction alternatives.

The requested four-corner calibration is specified here in clockwise order: top-left, top-right, bottom-right and bottom-left, before tracking/collection. The proposal adds a separate center check, two-second preparation intervals, a 1080p pilot and numeric-only local records by default. Calibration anchors, readiness checks and main measurement samples have distinct roles. Image recording is not enabled. Numerical quality gates and the benefit of a shared correction remain pilot/development questions.

The user accepts held-button toggles and reserves SSS for physical middle-button press/release. Other detailed assignments remain open. See [action design](docs/ACTION_GESTURE_DESIGN.md) and [gesture collection/training](docs/GESTURE_COLLECTION_TRAINING.md): the initial separate budget is 375 sequences and 45 minutes of negative reading across 15 sessions, subject to three-pilot review. Fit personalized thresholds/timing on training/development data; a learned classifier is conditional. Wait for complete S/SS/SSS recognition before dispatch. The historical 1.5-second stop duration is not a frozen concurrent normal-action binding.

Next implement the collector with four-corner calibration, continuous gesture/negative roles and reliable labels, without desktop input. Review pilots, freeze acquisition/split rules, collect both datasets, fit/evaluate both components, then test stateful mock button scenarios before live control. This update changes documentation only. Historical entries below preserve prior decisions; this section is the current queue.

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

## Completed: consent denial and portal revocation

Reviewed the user's pasted report 37 and terminal output. Cancellation at Start returned permission cancelled or denied (1), no commands or motion calls, and `session_closed: true`. Accept denial behavior. The raw file is not synced at this review; do not fabricate or overwrite it. The subsequent cleanup error came from attempting Close on the already-closed session object.

Adjusted cleanup to skip Close only after receiving the portal Closed signal. It reports `session_cleanup: already_closed_by_portal` and `session_close_acknowledged: null` because no redundant Close call is made. Close errors without a Closed signal remain visible. All 66 local tests pass with native interfaces mocked; the already-closed cleanup branch is now exercised on Linux in pasted run 38.

Reviewed pasted report 38: one center target submitted, `session_closed: true`, `pause_observed: false`, `sequence_complete: false`, no primary error, EIS context released, and `session_cleanup: already_closed_by_portal`. Accept stopping on portal revocation for the tested setup. The raw report is not synced at this review. `session_close_acknowledged: null` correctly means the redundant Close was skipped. The console Broken pipe warning is consistent with EIS teardown sending a stop-emulating message after the peer disconnected; the log does not identify the exact call. No later target is recorded, and no stop-latency bound is inferred.

## Completed: single-instance exclusion; next: camera/offline closeout

Reviewed synced reports 39/40 and the user's passing observation. Run 39 completed all six targets normally with no error and successful EIS/portal cleanup; it was not paused, which is not required for this lock check. Run 40 rejected with `Another pointer probe is running`. Its schema-1 error report has no motion history fields; code acquires the lock before clearing pause or opening a portal connection. Together these establish single-instance exclusion in this trial. Do not infer simultaneous-run timing from file timestamps alone.

Reports 37/38 are now synced and agree with the previously reviewed pasted denial/revocation results. No native-pointer repeat is requested. Mapping, global pause, denial, revocation and single-instance exclusion are accepted for this tested configuration; production controller safety and gaze accuracy remain outside this acceptance.

## Camera failure/recovery review: runs 41/42

Run 41 returned the expected Cannot open camera error, zero reads/processed frames, and no stuck capture thread. Accept invalid-device handling. Run 42 successfully opened the real 1280x720 MJPG camera and local model in a fresh process: 417/417 processed frames with valid basic geometry, 14.76 processed FPS, no reported error or stuck capture thread. Accept fresh-process recovery and local-model execution; geometry availability is not gaze accuracy.

The user explicitly confirms run 42 was executed with networking off. Accept offline startup and local-model inference as a smoke test, based on that confirmation and the recorded inference. The local report still contains the same 28.249-second, 417-frame result and status `incomplete`; no newer full-duration result was found at this review. Preserve that distinction rather than claiming a completed 30-second repeat. Code uses incomplete for early stop (preview invisibility or KeyboardInterrupt); the user's exact early-stop action is not yet recorded. This does not negate observed offline startup/inference, but an unexpected preview exit should be reported and investigated. No repeat is requested solely to reach 30 seconds. Network-disabled operation is user-reported, not a monitored audit of attempted network access.

Synced reports currently contain 33 JSON and 7 text files, with no media files visible in that directory. This is a limited inspection of the synced reports, not a full Linux storage/cache or network audit. Linux file permissions cannot be established from this Windows copy. Finish applicable shutter/contention observations, Linux retained-file permissions and setup notes using sections 6/8 of [the Linux checklist](docs/LINUX_CHECKLIST.md) and the results template. Do not manufacture integrated-camera unplug or permission-revocation scenarios; mark unperformed checks explicitly. Guided-run face loss/reacquisition and desktop checks already have accepted evidence. No new code, package or blanket baseline rerun is requested.

## Ready to execute: remaining validation checklist (43-48)

Follow [VALIDATION_CLOSEOUT.md](docs/VALIDATION_CLOSEOUT.md) on Linux. It contains copyable commands and expected outcomes for shutter/lens-cover response (43), overlapping camera readers (44/45), fresh-process recovery after those challenges (46), and read-only report metadata/permission inspection (47). Fill [CLOSEOUT_RESULTS_TEMPLATE.txt](docs/CLOSEOUT_RESULTS_TEMPLATE.txt) into `reports/48-closeout-notes.txt` with actual setup and manual observations. Use fresh filenames; preserve earlier evidence. If a shutter is unavailable, record that or explicitly label the optional lens-cover substitute.

No runtime change, package installation, long baseline repeat or additional desktop-input test is needed. Return the reports and notes for review before data collection. A busy-camera rejection and supported concurrent readers are both possible outcomes; review what happened to both processes rather than assuming one required result. The privacy check inspects reports only, not all system caches. Integrated-camera disconnect and forced device-permission changes are not requested. Retain the run-42 early-stop uncertainty in the notes if its cause is unknown.

## Completed: controlled camera-cover response (49)

Reviewed synced run 49: normal 40.184-second completion, no error/stuck capture thread, 594 processed frames, 437 geometry-valid frames and 157 no-face frames. The one-second bin counts reconcile with the totals; camera/features/timeline source hashes match the local diagnostic files. Geometry is valid on all processed frames during seconds 0-11; second 12 contains 7 geometry frames and 8 no-face frames. Seconds 13-22 contain no face or geometry detections and dark image statistics (median per-bin grayscale mean ~5-6/255). Geometry returns on all processed frames in seconds 23-39. The final empty partial bin is not a detection failure.

Accept controlled camera-cover loss/recovery for this setup. The 73.57% whole-run geometry fraction includes the intentional cover and is not a tracking-quality regression. Bin timing describes observations, not exact hand action times or end-to-end recovery latency. Run 43's conflicting summary remains unexplained; preserve it, do not retroactively mark it passed or claim the timeline changed the model. No further cover repeat is needed now.

Reports 44-47 are now synced and reviewed below. No further cover, contention or recovery repeat is requested. Keep run 49 and ordinary eye-closure interpretation separate: the current adapter still does not classify closed eyes or usable gaze.

## Closeout accepted; next: collection-protocol design

Run 44 completed 60.027 s with 890 frames at 14.83 FPS, no error or stuck capture thread. Run 45 rejected its camera open with zero frames and no stuck thread. Run 46 then completed 15.195 s, 223/223 geometry-valid frames at 14.68 FPS, no error or stuck thread. With the user's confirmation of executing the requested checks, accept the contention/recovery trial. The generic open error alone does not prove its cause, and these reports do not independently timestamp cross-process overlap; no additional overlap measurement is claimed.

Report 47 records the Linux reports directory as 700 and the listed JSON reports as 600. Older diagnostic text logs are 664; the 700 parent restricts access through this directory, but those modes would matter if copied elsewhere. No subdirectories, symlinks or media files are listed. Report 46 is absent from that listing, so its Linux mode is unverified; do not infer all files or all caches were audited. This scoped inspection is sufficient for prototype closeout; no blind chmod or repeat run is requested.

The user did not create notes file 48. It is an optional recording format, not a validation dependency. Do not fabricate it or block protocol design on its absence. Historical distance/lighting/power/fan details remain unspecified. Capture the current measured viewing distance, lighting, glasses and power source in chat or collection-session metadata before actual collection, rather than reconstructing old observations.

Next design the personal-data collection protocol and review it before recording training examples. Define target presentation, settling/measurement intervals, per-session setup metadata, handling missing faces and closed eyes, separate training/evaluation sessions, permitted saved data and stop controls. Implement only the collection stage after agreement; training, calibration and deployment follow sequentially. The original 20-update/s goal, eye-closure reliability, gaze accuracy, production input/watchdog behavior, full network/cache audit and unperformed forced-disconnect/permission cases remain outside this prototype acceptance. Run 43 stays unexplained historical evidence; run 49 supplies the accepted controlled cover result.

## Environment closeout checklist

- [x] Native Wayland motion: EIS coordinates visually verified in run 34 at the tested display configuration.
- [x] Verify the GNOME global pause shortcut: Ctrl+Alt+Space, active EIS pause accepted from run 36 retry1 and manual observation. The GlobalShortcuts portal remains unavailable in the supplied inventory.
- [x] Consent denial at Start sends no motion (pasted report 37).
- [x] Portal revocation stops further scheduled targets (pasted report 38).
- [x] Single-instance exclusion: run 40 rejected while run 39 completed normally; reviewed synced reports and user confirmation.
- [x] Invalid-device failure (41) and working-camera/model recovery in a fresh process (42).
- [x] Offline startup/inference smoke test: recorded model execution plus explicit user confirmation that networking was off. The local run-42 report remains an early-stopped 28.249-second record.
- [x] Controlled camera-cover response accepted from run 49; run 43 remains unexplained.
- [x] Contention/recovery (44-46) and scoped Linux report-directory inspection (47) accepted with the limits above. Forced integrated-camera disconnect/permission changes remain NOT TESTED / not applicable.
- [ ] Record current distance, lighting, glasses, display and power metadata before actual collection. Historical unreported setup/fan observations remain unknown; no file 48 is required.

Completion evidence: coordinate/pause behavior and remaining applicable validation checks reviewed; unresolved issues either fixed or explicitly recorded with their scope. No production clicking, watchdog, lock/suspend recovery or button-release lifecycle is implemented or certified yet.

## Deferred investigation

Direct V4L2 reached approximately 29.7 FPS with dynamic frame rate disabled; OpenCV runs remain near 14.8 FPS despite a zero readback before capture. The cause is unresolved. Defer further tuning while assessing feature usefulness at the accepted provisional rate. Revisit if responsiveness, blink timing or the later acceptance tests require it. Do not mark the discrepancy fixed.

## Later stages

Implement the documented collector and per-session calibration, review Linux pilots and freeze the protocol, collect the personal dataset, train the personal estimator, independently evaluate new sessions after their permitted calibration, then implement deployment. Keep these stages sequential. No collection, personal training, actual calibration or deployment has started.

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

| 2026-10-24 | Reviewed pasted run 38: one target, portal closure, no pause, incomplete sequence, EIS released and redundant Close skipped. Accept revocation behavior; retain Broken pipe warning without claiming its exact source. | Single-instance tests 39/40; no repeat revocation required. |

| 2026-10-24 | Reviewed synced 39/40: first EIS probe completes normally, second rejected by lock; user confirms pass. Reports 37/38 now synced too. | Accept diagnostic desktop checks; proceed to remaining camera failure/recovery, offline and retained-file checks before collection protocol. |

| 2026-10-24 | Reviewed synced 41/42: expected invalid-device error; fresh-process recovery at 14.76 FPS with geometry on 417/417 frames, no error/stuck thread. Run 42 ended early at 28.249 s. | Confirm networking off and intentional preview closure; finish applicable closeout observations, then collection-protocol review. |

| 2026-10-24 | User explicitly confirms run 42 was executed with networking off. Local JSON still holds 28.249 s / 417 frames / incomplete. | Accept offline startup/inference smoke test without claiming a full-duration repeat; finish applicable setup/validation notes. |

| 2026-10-24 | User requested proceeding. Prepared focused closeout commands (43-47) and setup/manual notes template (48), with expected outcomes and explicit unsupported cases. | Execute on Linux and return evidence; no runtime code change or new packages. |

| 2026-10-24 | Reviewed run 43 and user-confirmed face disappearance during lens cover: 668/668 geometry and no loss counters conflict with observation. Added optional one-second diagnostic aggregates; 70 mocked tests pass. | Sync code, run controlled cover-only diagnostic 49; do not mark occlusion check passed or start collection yet. |

| 2026-10-24 | Reviewed run 49: image darkens, 157 no-face frames, no geometry in full-cover bins, geometry returns after uncovering, normal completion. Totals reconcile and source hashes match. | Accept cover/recovery for this setup; resume missing contention/recovery/permissions/setup evidence (44-48), without another cover repeat. |

| 2026-10-24 | Reviewed 44-47: first camera run completes, second open rejected, recovery succeeds; report directory 700 and listed JSON 600. User omits optional notes file 48. | Proceed to collection-protocol design; capture setup in chat/session metadata before recording data. |

| 2026-10-25 | Documented the collection protocol and model architecture, incorporating the user-requested four-corner calibration before each setup. | Implement collector/calibration flow, review three Linux pilots, then freeze the full collection protocol. No runtime change or dataset recorded. |

| 2026-10-25 | Documented requested left/right/middle press-release behavior and tentative blink-toggle design; wheel action clarified as middle button. | Review gesture pilot and timing/stop conflicts; keep acquisition separate from gaze fitting and defer live button dispatch. |

| 2026-10-25 | User accepts toggles, reserves SSS for middle and defers other bindings. Revised Word/Markdown plans distinguish gaze and gesture fitting. | Pilot S/SS/SSS and L/SL candidates plus negative reading; fit/evaluate recognition and test explicit controller states. |
