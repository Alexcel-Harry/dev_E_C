# Gesture collection and recognition training

Updated: 2026-10-25 (America/Los_Angeles). Design revision 2; implementation has not started.

The user accepts held-button toggles, defers detailed action assignments, and selects **triple short (SSS) as the intended middle-button toggle**, subject to pilot reliability. The middle button means physical press/release, not wheel rotation. Keep this capability available even if rarely used; it is not necessary for all document viewing, because scrollbar dragging remains an alternative. Its usefulness depends on the target application.

## 1. Two collection tasks and two kinds of fitting

| Component | Observations and labels | Fitting or programming |
| --- | --- | --- |
| Gaze estimation | Eye/pose features paired with known screen targets | Fit four-corner session transforms and train a shared personal correction if beneficial. |
| Blink recognition | Continuous eyelid/validity traces, confirmed closure events, sequence labels and ordinary-reading negatives | Fit personalized thresholds/timing; run a configurable temporal decoder. Train a separate classifier only if needed. |
| Action controller | Recognized sequence plus current held-button state | Explicit state transitions and configurable bindings; no learned decision to hold or release a button. |

The gaze model does not need separate classes for left down, left up, right down, right up, middle down and middle up. The same recognized gesture can mean press or release depending on state. Record and test both state transitions, but do not duplicate recognition classes simply because a button has two actions.

Changing a binding later does not require recollecting the same blink pattern or retraining gaze estimation. Adding a genuinely new gesture pattern requires new recognition examples and evaluation. Do not attempt to cover every possible blink string: define a bounded vocabulary and reject unsupported/ambiguous sequences.

## 2. Baseline recognizer is personalized rather than a fixed magic threshold

Use the already-fixed MediaPipe front end to obtain per-eye openness and observation validity. For each eye, fit a robust open reference and a comfortably closed reference from designated training/calibration samples. A normalized openness can be expressed as `(observed - closed_reference)/(open_reference - closed_reference)` when the reference separation is adequate. Reject an unreliable reference rather than dividing by a near-zero range.

Then use separate close and reopen thresholds (hysteresis) and timestamped stable-state durations to prevent noisy samples from repeatedly opening/closing an event. Fit deliberate-short and deliberate-long duration bands from confirmed examples. Use rejection bands where distributions overlap instead of forcing every event into a command class. Record left/right agreement; natural blinks, uncertain unilateral closures, poor geometry and missing observations must not automatically become intentional commands.

The nominal 0.5-second S and 1.5-second L are collection cues, not immutable constants. The inter-blink gap, reopening debounce and cooldown are separate configurable values. Fit/select these with training/development data; store their values, source sessions, feature schema and version in a profile. Freeze them before test evaluation. Any per-test-session open/closed reference adjustment must use a separately designated calibration segment and the same predeclared procedure available during ordinary use, never scored sequences or reading negatives.

The decoder contains programmed logic for event timing, sequence completion, rejection and deduplication. The button bindings are configuration. This combination is a fitted rule-based recognizer, not a new deep network and not an arbitrary hardcoded 0.5-second comparison. If natural and intended blinks are observationally indistinguishable, no classifier can infer intent reliably from those same inputs; change the gesture vocabulary or interaction mode.

## 3. Sequence grammar must include triple short

Collect S, SS and SSS as distinct sequence labels. Do not execute S while SS/SSS remains possible, or execute SS while a third S can still start. After the last stable reopening, wait for the inter-blink timeout before committing the sequence. A closure starting before that deadline belongs to the pending sequence even if it ends later.

Use the same grammar while a button is held, so the prefix of a different command cannot accidentally release it. Keep pending pointer position frozen during the entire sequence and recognition wait. Dispatch once per completed sequence ID.

Initial illustrative gap: 0.6 seconds. With S = 0.5 seconds, SSS takes 1.5 seconds of closure plus two actual intervening open intervals, a final completion wait, debounce and processing. If both internal gaps were 0.3 seconds, nominal time to dispatch would be about 2.7 seconds plus debounce/processing. These are planning examples, not measured latency.

In the initial bounded grammar, at most three deliberate closures form one candidate. A fourth closure starting within the completion window invalidates the pending sequence before any command is sent. Unsupported words such as LS, SSL or ambiguous/incomplete timing also reject rather than dispatching a valid prefix. After overflow, timeout, pause or uncertain observations, cancel the sequence and require a fresh stable-open interval. Define separate maximum closure and total-sequence durations from pilot evidence. Cooldown begins after the whole sequence, not after the first blink.

## 4. Acquisition blocks and initial sample budget

Use the same lighting categories, glasses, camera mode and session/day split as the gaze dataset, but save separate sample roles and continuous eyelid traces. Closed-eye frames must remain in gesture data even when excluded from gaze fitting. Gesture blocks may be recorded separately from the gaze blocks to avoid fatigue; related blocks from one sitting/day remain in the same split.

| Sequence | Collection priority | Starting target |
| --- | --- | --- |
| S | Required primitive and single-sequence comparison | 5 confirmed trials per session |
| SS | Required comparison and prefix of SSS | 5 confirmed trials per session |
| SSS | Required proposed middle toggle | 5 confirmed trials per session |
| L | Candidate vocabulary; no action bound yet | 5 confirmed trials per session |
| SL | Candidate vocabulary; no action bound yet | 5 confirmed trials per session |
| LL | Optional exploratory candidate | Up to 2 comfortable trials in each pilot only; no routine quota |

Start with three pilots, one per lighting condition, before committing to the full quota. Omit an uncomfortable exploratory candidate and record the decision. If L or SL is dropped after the pilot, stop its routine collection and update the versioned vocabulary/counts. Keep S and SS comparisons even if unbound, because the recognizer must distinguish them from SSS.

For the initial 15-session plan, five trials of each of the five core sequences yields **375 labeled sequences**, **75 per sequence**. The 9/3/3 session split yields 45/15/15 examples per class for fitting/development/test, assuming complete confirmed trials. This is a starting budget for one user's prototype, not enough evidence by itself for release reliability or a deep sequence model. Do not reduce SSS coverage merely because middle-button use is rare.

Add **3 minutes of ordinary reading with no intentional commands per session**: 45 minutes overall, split 27/9/9 minutes. Record ordinary blinking continuously. Include normal glasses adjustments and head movements if they occur; do not invent confirmed negative actions from unknown windows. Tag interruptions and accidental intended commands rather than calling all unprompted time negative.

The main gaze estimate of about 17,000 measurement frames remains a separate count. Gesture examples are sequences, not frames; negative data are measured in observed time and events. Budget roughly 6-9 additional minutes per gesture/reading block, including preparation and breaks, and revise after the pilot. The combined gaze plus gesture work is roughly 10-15 minutes per session; distribute it across days rather than collecting everything in one sitting.

## 5. Trial presentation and labels

Present the intended pattern at the center, allow the requested two-second preparation time, and use optional audible cues so instructions remain usable during closure. Keep enough open time after each sequence to observe its end and the final completion window. Pilot timing demonstrations can be paced; later trials should include comfortable self-paced execution rather than measuring only obedience to exact beeps.

Store `prompted_pattern`, `confirmed_pattern`, confirmation source, uncertainty, actual timestamps and observed event boundaries separately. Obtain user correction/confirmation after a trial or short block without requiring an eye movement during the event. Do not set `confirmed_pattern` by copying the decoder prediction. Retain failed/incorrectly performed trials with their labels/status; do not count them as successful quota completions or discard them from evaluation without reporting them.

Numeric traces cannot always reveal actual eyelid state if landmarks are wrong. Mark those trials uncertain; image recording remains off by default and would require a separate explicit decision for reliable visual annotation. Do not promise high-confidence ground truth from prompt timing alone.

Save continuous per-frame timestamps, left/right openness, face/eyelid quality, gaze-validity separately, camera gaps, conditions, profile/schema versions, decoder events and sequence decisions. Add trial/sitting/day/split IDs. In later mock controller exercises, save the simulated action binding and held state before/after each command separately from the recognition label.

## 6. Fitting and evaluation sequence

1. Review pilot observability and comfort; establish the supported vocabulary, label process and candidate timing ranges.
2. Collect the initial session-based dataset. Reserve development/test sessions before fitting; reused exploratory pilot data can enter training only if compatible, never untouched test.
3. Fit per-eye reference distributions and candidate event thresholds on training sessions. Tune thresholds, timing, rejection and cooldown on training folds/development sessions with both intentional sequences and reading negatives.
4. Freeze profile and decoder version. Evaluate complete held-out sessions/days using the declared calibration procedure. Do not manually segment test windows from known prompts and then claim continuous recognition performance; also run the decoder over the continuous trace.
5. Inspect per-class confusion including S versus SS versus SSS, missed events, false activations per minute, unknown/rejected rate, valid observation coverage, and dispatch latency. Report results by lighting and session.
6. Run stateful mock scenarios for each supported button's down, move-while-held and up, pause/loss/reconnect handling, duplicate events and prefix rejection. Recognition accuracy does not establish correct button lifecycle.
7. Only after these stages implement and test real desktop button dispatch and the intended applications. Historical pointer-motion validation is not button/gesture validation.

Choose numeric acceptance thresholds using pilot/development evidence before final evaluation. Do not declare a successful recognizer solely because it recognizes prompted demonstrations. Nine minutes of held-out negative reading, even with no false commands, cannot establish rare-error performance over hours; extend negative evaluation substantially before deployment, particularly if the goal requires a low false-command rate.

## 7. When to train a separate classifier

If calibrated rules show unresolved but potentially separable errors, compare a small supervised event/sequence classifier using confirmed samples: closure duration, inter-event gaps, minimum and mean normalized openness, closure/reopening slopes, bilateral agreement and observation quality. A regularized linear classifier or small tree model is a sensible first comparison; keep segmentation, abstention and the explicit button controller.

Train on grouped training sessions, choose models on development data, and score the same untouched test streams as the rule baseline. Do not train a classifier on labels generated by the same thresholds and then treat agreement as independent evidence. Do not use class oversampling to inflate the number of independent trials, or assume 375 sequences justify a large recurrent/transformer network. Expand the dataset based on per-class learning curves and observed failures if a learned classifier is pursued.

Sources for grouped evaluation and confusion reporting: [GroupKFold](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.GroupKFold.html), [confusion matrix](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.confusion_matrix.html). All sample counts and timing examples here are project proposals.

## 8. Binding and stop decisions

SSS is reserved as the intended middle-button toggle. Left/right, ordinary complete-click conveniences, L and SL meanings remain for later assignment. SSS recognition does not imply a default left/right binding for its prefixes. The old L = middle example is superseded.

Because L no longer has a middle-button assignment, the old 1.5-second disarm rule is not automatically in conflict with that mapping; nevertheless its exact threshold and role are not frozen. During gesture acquisition no desktop action, including disarm-on-L, is dispatched. Any future normal L binding must explicitly replace an overlapping stop rule. Independent keyboard pause remains required for later live control.

See [collection plan](DATA_COLLECTION_PLAN.md), [model architecture](MODEL_ARCHITECTURE.md) and [action design](ACTION_GESTURE_DESIGN.md).
