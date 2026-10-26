# Button actions and blink gesture proposal

Updated: 2026-10-25 (America/Los_Angeles).

Status: the user accepts button toggles, reserves triple short (SSS) for middle-button toggle, and defers other detailed bindings. The [pilot collector](COLLECTOR_PILOT.md) records gesture observations and explicit labels; action decoding and button-controller implementation have not started. The user requests left/right press and release, dragging through gaze movement while held, and has clarified that the wheel-related action means **physical middle-button press/release**. The original five candidates plus SSS are retained for collection; optional LL may be dropped if uncomfortable. This extends the original single-complete-left-click scope; it does not change existing diagnostic code or enable desktop input.

## 1. Actions and triggers are separate

The controller should represent `left_down`, `left_up`, `right_down`, `right_up`, `middle_down`, `middle_up`, and `release_all`. Middle-button press/release must not be implemented by sending scroll deltas. Rotating a wheel is a separate action, outside the currently requested bindings. The target Linux applications must be tested; physically pressing the wheel does not universally activate document autoscroll. [libinput scrolling documentation](https://wayland.freedesktop.org/libinput/doc/latest/scrolling)

An optional complete-click command sends a controlled down/up pair at one frozen target. It can reduce the effort and accidental dragging involved in two separate blink commands, but it is not a replacement for the explicitly requested held-button capability. Gesture bindings and any normal-click versus drag mode remain configurable design choices.

The backend interface will need separate button down/up capabilities for all three buttons rather than only the original `click_left` operation. The successful EIS pointer-motion tests do not validate these additional operations.

## 2. Share a trigger between down and up

Recommend a stateful toggle per supported held button:

| Controller state | Recognized trigger | Command and new state |
| --- | --- | --- |
| No button held | Left toggle | Left down; LEFT_HELD |
| LEFT_HELD | Left toggle | Left up; no button held |
| No button held | Right toggle | Right down; RIGHT_HELD |
| RIGHT_HELD | Right toggle | Right up; no button held |
| No button held | Middle toggle | Middle down; MIDDLE_HELD |
| MIDDLE_HELD | Middle toggle | Middle up; no button held |
| Any active state | Explicit stop/pause/failure handling | Cancel pending gestures, request release of held buttons; disarm |

Initially allow only one held button at a time. While a button is held, requests to toggle either other button are rejected with feedback. Do not queue rejected commands to execute later. The corresponding release trigger and independent pause remain available. Preserve the same decoder grammar while held; do not reinterpret the S or SS prefix of an intended SSS as an immediate release merely because the left button is held.

Always display the state near the pointer or in a persistent status indicator, e.g. `Left held - repeat to release`, with optional audible confirmation on successful local dispatch. State comes from the controller's command lifecycle, not from guessing what the application did. Toggle recognition must dispatch once per unique gesture ID, not once per frame.

For a scrollbar drag: aim at the thumb, toggle left down, move gaze while open to pull it, then toggle left up at the final pointer position. For a single click using two toggles, the pointer must remain within the intended control between down and up; gaze drift can otherwise initiate a drag. A separate complete-click command/profile may be preferable for frequent ordinary clicks.

## 3. Gesture vocabulary and initial mapping candidate

`S` means a deliberate short closure, nominally about 0.5 seconds. `L` means a deliberate long closure, nominally about 1.5 seconds. These are the user's candidate targets, not universal physiological thresholds. Actual accepted duration bands, reopening debounce, timing gaps and ambiguous regions must be personalized from examples and frozen before evaluation.

| Candidate | Nominal total closed time, excluding gaps | Initial assessment |
| --- | --- | --- |
| S | 0.5 s | Lowest effort; must distinguish from natural or prolonged incidental blinks. |
| L | 1.5 s | Clear timing contrast if observable; more time without visual feedback. Conflicts with the old 1.5 s disarm proposal. |
| SS | 1.0 s | Required comparison and prefix of SSS. |
| SSS | 1.5 s | Intended middle toggle; requires two open intervals and a final completion wait. |
| LL | 3.0 s | Slow and potentially tiring; low-priority candidate, not an initial routine command. |
| SL | 2.0 s | Possible extra command; higher latency and a shared prefix with S and SS. |

The current binding decision is **SSS = middle-button toggle**: first complete sequence presses, the next complete sequence releases. This intended binding still requires recognition/application testing. Left/right toggles and complete-click shortcuts remain unassigned. The earlier L = middle example is superseded; L, SL and optional LL have no device actions assigned.

A middle-button capability is useful for application compatibility but is not necessary for all document viewing: scrollbar dragging remains an alternative. Its rarity can justify a slower trigger, not weaker recognition or release testing.

## 4. Single double and triple ambiguity

S is a prefix of SS and SSS; SS is a prefix of SSS. Wait after stable reopening for the next-closure timeout before committing a shorter sequence. Never send an action speculatively and try to undo it when another blink arrives. Use the same grammar while a button is held.

An illustrative pilot inter-blink gap is 0.6 seconds. Three 0.5-second closures with two 0.3-second internal gaps and a 0.6-second final wait take approximately 2.7 seconds, before debounce and processing. Fit actual duration bands, gap and cooldown from confirmed training/development examples; these numbers are not measured response times.

Allow up to three deliberate closures in the initial bounded grammar and wait after the third as well. A fourth closure starting inside the completion window invalidates the pending sequence without dispatching SSS first. Unsupported/ambiguous words, missing observations, pause or sequence timeout cancel the whole pending gesture. Unbound recognized patterns produce no command. Require fresh stable-open observations after cancellation.

Cooldown starts after the completed sequence, never after the first blink. Preserve unique sequence IDs to prevent duplicate dispatch. See [gesture collection and training](GESTURE_COLLECTION_TRAINING.md) for timing, personalization and evaluation details.

## 5. Gaze movement while recognizing gestures

Freeze the pointer at the last stable pre-closure position when a command sequence begins. Keep it frozen through the recognition window, including inter-blink gaps, so reopening movement cannot redirect a pending command. After successful down and fresh stable-open gaze, resume gaze movement with that button held. After an up, resume ordinary movement without a held button.

For release, latch the position immediately before the release gesture, not the original drag-start location. Otherwise ending a drag would jump back. Ignore closed-eye iris estimates for pointer motion. A brief ordinary blink during a drag freezes motion and preserves the hold if face/eyelid observations remain valid; it is not automatically a release or a camera failure.

Gesture decoding and held-button state are separate state machines. Suggested decoder states are OPEN, CLOSED, WAIT_NEXT, COMMIT, COOLDOWN and CANCELLED. Suggested controller states are DISARMED, READY, LEFT_HELD, RIGHT_HELD and MIDDLE_HELD.

## 6. Middle button and application behavior

The user explicitly means pressing/releasing the middle button, not rotating the wheel. The middle toggle therefore sends middle down on first activation and middle up on the next. Gaze movement between these actions produces pointer movement while middle is held, subject to the same validity and freeze rules as left/right holds.

Some applications implement panning while held; others may activate autoscroll only after a complete middle click, use the middle button for another function, or ignore it. Middle-button down alone must not be promised to start scrolling. Test the actual browser/PDF viewer and its settings. A controlled complete middle click (down then up) is a separate optional convenience command, not the same thing as a persistent hold.

Releasing the button is also not guaranteed to exit an application's latched autoscroll mode. Distinguish controller-held-button state from application-owned modes. Verify how to end the latter in the target applications; do not claim the controller's release-all command cancels every application behavior. A dedicated wheel-scroll mode is a possible later extension if requested, not part of this binding proposal. [Mozilla discussion of held-button versus latched autoscroll](https://bugzilla.mozilla.org/show_bug.cgi?id=1675155)

## 7. Resolve the old long-closure rule before implementation

The original v1.1 technical plan used a valid approximately 1.5-second closure to disarm. It cannot simultaneously mean a normal L command. SSS now owns the intended middle binding, so L has no normal action assigned. If a normal L action is assigned later, revise the old disarm rule first. Its stop threshold is not frozen, and gesture acquisition does not dispatch an L stop action.

Keep the established keyboard pause shortcut as an independent stop path and test release behavior when buttons are held. A separately defined overlong-closure cancel/disarm rule can be considered only with a non-overlapping, pilot-tested threshold; no replacement duration is selected here. Pause must cancel pending commands before they dispatch.

Valid intentional closure may make iris coordinates unusable while face/eyelid observations remain available. Do not use loss of an iris during L as the same signal as stale capture or face loss. Conversely, missing/invalid eyelid measurements cannot be labeled a deliberate blink.

Pause, stop, capture/face loss beyond the defined tolerance, display/session change and backend failure must stop pointer commands, clear pending commands and attempt to release held buttons through a still-valid channel. Track release outcomes honestly: a dead or revoked connection may prevent release delivery. Enter an unknown/disarmed state in that case; never claim release succeeded or automatically resume a held state after reconnection. Later backend lifecycle and watchdog tests must cover these cases and process failure.

## 8. Gesture collection and fitting

Follow [GESTURE_COLLECTION_TRAINING.md](GESTURE_COLLECTION_TRAINING.md). Collect S, SS, SSS, L and SL with continuous numeric eyelid traces, optional LL pilot examples, and ordinary-reading negatives. The starting target is five confirmed trials per core sequence per session across 15 sessions: 375 sequences, 75 per class, plus 45 minutes of negative reading. Review the three pilots before committing to the full quota. Counts do not guarantee reliability.

Fit per-eye reference values, hysteresis thresholds, duration bands and sequence timing using training/development data. The decoder and button state transitions are explicit logic with versioned configuration. A learned classifier is conditional on demonstrated shortcomings. Gaze regression is separate and does not need a class for every button event.

Test recognition independently of action bindings. Later mock controller exercises cover down, movement while held and up for all three buttons, duplicates, prefix rejection, pause and loss. Press and release use the same recognition class plus state. Evaluate continuous held-out streams, confusion, false activations per minute, rejection, coverage and latency; extend negative evaluation before deployment.

## 9. Remaining decisions

- Preserve SSS as the intended middle toggle; assign left/right and complete-click conveniences later.
- Select timing and quality bands from the pilot; decide whether L, SL or optional LL merits a binding.
- Define non-conflicting stop behavior and test keyboard pause and release handling.
- Verify middle-button behavior in the actual applications.
- Keep gesture, negative-reading, gaze and four-corner samples in distinct roles with session/day splits.

See [collection plan](DATA_COLLECTION_PLAN.md), [gaze architecture](MODEL_ARCHITECTURE.md) and [gesture fitting specification](GESTURE_COLLECTION_TRAINING.md). No camera recording or desktop input is performed by this documentation update.
