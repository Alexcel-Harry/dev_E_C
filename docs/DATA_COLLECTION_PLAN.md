# Personal gaze data collection plan

Updated: 2026-10-25 (America/Los_Angeles). Protocol design revision: `personal-gaze-collection-v2`.

Status: the overall collection/toggle approach is accepted; numerical settings and remaining bindings await pilot selection. The combined pilot collector is implemented; no live dataset has been produced by this coding task. [COLLECTOR_PILOT.md](COLLECTOR_PILOT.md) describes executable protocol `eyecheck-collection-pilot-v1`, concrete numeric gates and storage. This first version uses one calibration per session: a setup change requires a fresh session with the same sitting ID. The user requests four-corner calibration before tracking/collection in each setup. Other numerical settings below are initial engineering proposals to check in the pilot, not measured accuracy limits. Existing validation reports remain unchanged.

## 1. Purpose and current evidence

Collect labeled observations for one user, one laptop display, and the same pair of glasses across ordinary lighting and small position changes. Preserve enough session context to distinguish a setup change from a change in gaze. Use the same calibration procedure during collection and eventual use.

The reviewed prototype checks support progression at approximately 15 FPS. The seated one-minute 720p and 1080p runs both delivered 14.8 FPS and basic geometry on 890/890 frames. Predicted eye widths were approximately 41/40 pixels at 720p and 57/55 at 1080p. Only 720p has a completed ten-minute baseline. These are capture/geometry observations, not gaze accuracy or reliable blink classification. See [validation status](VALIDATION_STATUS.md) and [next step](../NEXT_STEP.md).

Propose native 1920x1080 MJPG for the collection pilot; retain actual mode and model hash in every session. Assess the new UI and storage workload in that pilot without repeating completed environment checks by default. Do not silently substitute 720p or mix modes in one profile. More source pixels may help eye detail but do not increase the neural network's parameter count or establish better gaze accuracy.

## 2. Session flow: calibrate first

1. Setup: enter lighting, approximate distance, laptop placement, glasses and power details; inspect the live eye preview; let exposure settle.
2. Enter fullscreen and record its actual settled display geometry. Hide the setup preview and ordinary pointer during target presentation.
3. Calibrate in this fixed clockwise order: **top-left, top-right, bottom-right, bottom-left**.
4. Fit the session mapping from those four anchor fixations. Show a separate center check with the predicted gaze dot hidden.
5. Continue to labeled target collection, or later to tracking practice/use when an estimator is available. A new dataset does not require a previously trained personal model.
6. Offer a break between passes; finish with a quality summary and optional center drift check.

Calibration belongs to the current setup, not permanently to the user. A declared change of lighting, viewing distance, lid angle, laptop height, facing direction, or glasses placement starts a new calibration segment before further measurement. Store both `session_id` and `calibration_id`. Keep all segments from one sitting in the same dataset split.

Calibration is not required to know where the displayed collection target is. Its purpose here is to establish a session reference and reproduce eventual use conditions. The known target remains the label; never replace it with the preliminary model's prediction.

## 3. Four corners and the center check

Use targets inset 5% from the display edges so their centers are fully visible. With top-left as the origin, their normalized centers are `(0.05, 0.05)`, `(0.95, 0.05)`, `(0.95, 0.95)`, `(0.05, 0.95)`. Save actual rendered centers and margins, not only ideal layout values. Accuracy outside that sampled area remains unestablished.

At each corner:

- Display the target and give **2 seconds preparation** after its first rendered presentation.
- Collect for **2 seconds**, aiming for at least **20 eligible fresh frames** from both eyes at the observed rate.
- If insufficient, extend the measurement window up to 4 seconds, then offer a retry; never advance indefinitely or invent missing data.
- Summarize each anchor robustly, preserving counts and within-anchor dispersion. Give anchors equal fitting weight regardless of frame count.

The four normal anchor windows take about 16 seconds. A center check with 2 seconds preparation and 1.5 seconds measurement makes the nominal sequence about 20 seconds, excluding warmup, transitions, retries and additional checks.

The center is a separate readiness/check phase and **does not fit the four-corner transform**. Store its error and quality separately. Finite, nondegenerate anchor geometry and sufficient eligible observations are necessary checks. A small fitting error at the corners is not proof of interior accuracy. Select and version numerical conditioning, dispersion and center-error gates using pilot/development data before formal test acquisition; no gaze-accuracy pass threshold has yet been validated.

If anchors fail, repeat affected anchors and refit, then acquire a fresh center check. Persistent poor interior behavior is a reason to compare a nine-point calibration protocol, not silently use center/test labels for fitting. Record failed attempts and the protocol actually used. One center check cannot certify the full screen.

## 4. Collection UI and target protocol

The user looks at a stationary small dot inside a larger visible ring. The ring shows preparation and collection progress at that same location. Use both text/shape and color to distinguish phases; optional sound cues must not be the only cue. Avoid instructions, counters or previews that require looking away during measurement.

Each ordinary target uses **2 seconds preparation followed by 1.5 seconds measurement**. Exclude settling and transition frames from the fitting set. Allow natural blinking; eligibility handling and retries should accommodate it rather than asking the user to suppress blinks.

Provide Pause, Resume, Stop and Repeat last target. Resume restarts the current preparation period and discards its incomplete measurement window from the default fitting set while retaining its incomplete status. Recalibrate when the setup changed during a pause. Stop saves an explicitly incomplete session and releases capture. Reuse the established global pause mechanism only after implementing and checking its collector integration; the existing pointer-probe pause test does not certify collector behavior.

Main collection per session:

- Pass A: 25 positions on a 5x5 grid spanning 5% to 95% of each axis, in a seeded shuffled order.
- Pass B: 25 positions with balanced screen coverage; apply small recorded jitter within the same cells to sample positions between fixed grid points. Keep all centers within the declared area. Use a separate recorded order/seed.
- Offer a short break between passes and quality feedback only during breaks/end, apart from a target-local pause/error cue when collection cannot continue.
- Keep predicted gaze hidden during all labeled collection and scored evaluation. Tracking practice with a predicted dot is a separate phase excluded from the scored dataset.

This produces 50 fixation events and 175 seconds of nominal presentation time. With calibration, setup, breaks and retries, budget approximately 4-6 minutes per session. Optional mouse-following or automatically moving targets are later, separately labeled experiments; they introduce pursuit and timing uncertainty and must not be pooled silently with stationary fixations.

## 5. Conditions and collection scale

| Factor | Initial coverage | Recording rule |
| --- | --- | --- |
| Lighting | Daylight, room/ceiling light at night, desk lamp at night | Record direction, mixed sources, visible glare and screen brightness. |
| Distance | Approximately 65, 70 and 75 cm | Measure or explicitly mark as estimated; do not claim precise depth from the current proxy. |
| Placement | Normal, slightly higher, slightly lower | Record stand/height and lid angle; keep stable within a block. |
| Facing direction | Frontal and small comfortable turns | Record the intended setup and observed numeric pose proxies. |
| Glasses | Same pair throughout | Record reseating and reflections; no need to force identical placement across days. |
| Natural variation | Multiple days and normal small posture changes | Do not deliberately tie one gaze region to one pose or light condition. |

Start with three pilot sessions, one per lighting condition. Inspect timing, calibration consistency, blink/quality exclusions, region coverage and saving throughput. Pilot data can enter training only if it matches the final schema/protocol; otherwise retain it as pilot evidence. Never promote used pilot data into the untouched test set.

The initial dataset target is **15 usable sessions**, five per lighting category, across several days. Vary distance and placement within each lighting category; a full Cartesian product is unnecessary initially. Use 9 training, 3 development and 3 untouched test sessions, with 3/1/1 sessions per lighting category. Reserve entire days/sittings where feasible and keep related segments together.

At 15 FPS, 15 sessions x 50 fixation events x 1.5 seconds yields approximately 16,875 measurement-window frames before exclusions, representing 750 fixation events. Calibration/check frames are additional and separately tagged. At the observed 14.8 FPS, the nominal main-window count is about 16,650. Neither count represents that many independent examples.

After initial model fitting, use learning curves and per-condition errors to decide where further collection is useful. Do not commit to hours of extra frames before diagnosing the limiting factor.

## 6. What the model learns and what calibration learns

See [model architecture](MODEL_ARCHITECTURE.md) for equations, parameter counts and alternatives.

- The pretrained Face Landmarker remains fixed and extracts eye/face geometry.
- A small four-corner transform is fitted afresh for each session/setup using that session's anchor samples only. It is available even before pooled personal training.
- A later personal correction model can learn repeatable residual errors across training sessions after each session's own calibration is applied.
- At test time, fit only the new session's calibration transform from its permitted four corners. Freeze the personal model, preprocessing and all tuning decisions. Score subsequent independent fixations.

The same raw iris features can correspond to different screen positions after a setup change. Recording and consistently using session calibration reduces that ambiguity. It cannot recover an occluded iris or guarantee compensation for arbitrary head movement or lighting. Retain pose range checks and invalid-data handling.

## 7. Records, timing and coordinates

Store a schema-versioned session manifest, presentation events and numeric observations. A proposed directory is a private Linux state location such as `$XDG_STATE_HOME/eyecheck/datasets/` (default `~/.local/state/eyecheck/datasets/`), outside the source repository. Use unique session directories, restrictive permissions and explicit complete/incomplete status.

Manifest fields:

- Protocol/schema versions; session, sitting, day and calibration identifiers; planned train/development/test role.
- Source revision or source hashes, dependency versions, landmark model hash, feature schema and estimator/calibration versions.
- Camera identity, requested/actual resolution and format, requested/observed rate, exposure settings where readable.
- Selected display, settled fullscreen/window geometry, logical dimensions, DPR/scaling metadata, coordinate convention and mirroring policy.
- Conditions from section 5, power source, target seeds, timestamps and completion/error status.

Per-presentation and per-frame fields:

- Presentation/fixation ID, phase (`calibration`, `check`, `collection`, `practice`, `gesture`, `negative_reading`, `gesture_reference`), target center in normalized and actual logical coordinates.
- Intended presentation time and observed paint acknowledgement, preparation/measurement boundaries, frame ID, monotonic read-completion time, and processing-completion time.
- Left/right normalized iris coordinates, eyelid openness and eye width, selected landmark coordinates needed to audit those features, face position/scale/roll proxies, and schema version.
- Detection/geometry status, freshness, eligibility decision and reasons, repeat/incomplete flags and associated calibration ID.

Label frames by their acquisition/read timestamp and the recorded target timeline, never by whichever target is current when inference finishes. Read-completion is not sensor exposure time; UI paint acknowledgement is not measured physical scanout. Record these limits, avoid stale buffered frames, and exclude transition windows. The two-second preparation margin helps static-target collection but does not measure or remove all latency.

Use one explicit screen convention, e.g. normalized target center `u=x/(W-1)`, `v=y/(H-1)` for logical center coordinates in `[0,W-1]` and `[0,H-1]`; preserve the precise rendering convention for subpixel centers. Never multiply normalized labels by DPR and then again by compositor scaling. Keep analysis images unmirrored and preserve any preview transform separately.

## 8. Quality, blinks and storage

The current diagnostic adapter supplies broad geometric sanity checks. It does not establish true fixation, calibrated gaze confidence, reliable open/closed classification, or glare detection. Prompted target windows indicate intended gaze, not independently verified ground truth.

Before the full dataset, review pilot open-eye and comfortable-closure observations to establish a documented provisional eligibility rule. Preserve uncertain/invalid observations with flags, exclude them from ordinary gaze fitting by default, and report excluded fractions per condition/region. Do not silently remove hard conditions from evaluation or use the estimator's own prediction error to decide which test samples count. A feature-only pipeline may miss plausible but incorrect landmarks; document that limitation.

The accepted action design uses left/right/middle toggles, with **SSS reserved for middle toggle** and other assignments deferred. Add the separate workflow in [gesture collection and training](GESTURE_COLLECTION_TRAINING.md): five confirmed trials each of S, SS, SSS, L and SL per session, optional LL exploration, and three minutes of ordinary-reading negatives. Across 15 sessions this gives 375 sequences and 45 minutes of negatives, additional to the gaze dataset. Start with three pilots and revise from evidence.

Retain continuous eyelid traces through closure and distinguish prompted from confirmed actions. Closed-eye frames excluded from gaze regression must remain in the gesture stream. Initially fit personal reference/timing parameters and use a configurable sequence decoder; a separate classifier is conditional. A recognized sequence maps to press or release through controller state, not a separate gaze/blink model class. See [action design](ACTION_GESTURE_DESIGN.md) for lifecycle and prefix rejection.

Gesture/reading blocks add roughly 6-9 minutes, giving about 10-15 minutes combined work per session. Check these estimates in the pilot and allow separate blocks across days while grouping related sittings in one split. The approximately 17,000 gaze frames are not the gesture sample count.

Default collection stores numeric training observations and metadata locally; this is a deliberate change from the earlier aggregate-only diagnostics. Keep raw camera frames and temporary crops in memory. Image/crop retention is not enabled by this plan. An appearance-model branch would require a separate explicit recording choice with visible status, crop transforms, retention rules and appropriate model-specific preprocessing, or later recollection. Numeric features cannot reconstruct eye images for CNN fine-tuning.

## 9. Evaluation without calibration leakage

Split by complete sessions/sittings, preferably days; never randomly split adjacent frames. Within a training fold, fit global normalization, residual weights and tunable processing only on its training portion. Fit every session transform using that session's designated anchors, including held-out sessions under the declared calibrated-use protocol.

Four-corner anchors and the readiness center check are not scored test fixations. Checks cannot secretly update the personal model or affine fit. Recalibration attempts and failed calibration sessions must be reported, not silently excluded to improve results. Separate calibration success/coverage from gaze error conditional on valid observations.

Use development sessions to choose regularization, optional features, quality thresholds and any nonlinear model. Freeze them before the final test. Use fresh test sequences and include both repeated grid locations and interior/jittered positions to assess interpolation. Future uncalibrated-use evaluation is a separate claim and dataset protocol.

Report median and 95th-percentile error in logical pixels and normalized screen distance, stationary dispersion, valid-data fraction, failures and results by region, lighting and setup. Report unsmoothed estimator results and, later, separately tuned filtered/control results. Do not convert to degrees without measured display size and viewing geometry. Do not clamp predictions before error calculation.

## 10. Implementation sequence and completion criteria

1. Implement a collection-specific state machine: setup, prepare anchor, record anchor, fit, check, prepare target, record target, break, paused, complete/error. Keep the existing diagnostic commands and reports unchanged.
2. Implement four-corner fitting, target-local UI, saved geometry after fullscreen settles, timestamp association and versioned local numeric storage. Do not emit desktop pointer/button input from the collector.
3. Add meaningful synthetic tests for anchor-only fitting, coordinate transforms, phase-boundary labeling, retry/pause/stop handling, missing/closed-eye exclusions, data-role separation and profile compatibility.
4. Run three Linux pilots with the same glasses and actual 1080p mode, including separate gesture-reference, sequence and negative-reading blocks. Review throughput, timing, corner separation, label confidence, eyelid observability, comfort and UI usability.
5. Freeze the pilot-adjusted acquisition/label protocol and session split; collect both datasets. Fit/select recognition thresholds only on training/development data.
6. Train/compare gaze models and fit/evaluate gesture recognition independently. Evaluate held-out continuous gesture streams, then stateful mock button scenarios. Implement desktop control later.

The requested four-corner-first flow is part of this plan. The first collection implementation is complete and awaits Linux pilot verification; live recording has not started. The pilot guide is authoritative for implemented behavior; optional drift checks, in-session recalibration and profile reuse remain future work. Remaining pilot choices include numerical eligibility/check gates and whether the richer personal correction improves on the session-only baseline. Image recording and larger neural-model training remain separate decisions.

## References

- [Model architecture and training details](MODEL_ARCHITECTURE.md).
- [Action definitions and button toggles](ACTION_GESTURE_DESIGN.md).
- [Gesture acquisition, fitted thresholds and optional classifier](GESTURE_COLLECTION_TRAINING.md).
- [MediaPipe Face Landmarker](https://developers.google.com/edge/mediapipe/solutions/vision/face_landmarker): pretrained face/landmark model behavior.
- [MPIIGaze collection procedure](https://www.collaborative-ai.org/research/datasets/MPIIGaze/): randomized laptop fixation targets; the timings/counts in this document are project proposals, not copied benchmark guarantees.
- [GroupKFold](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.GroupKFold.html): disjoint grouping for model selection.
