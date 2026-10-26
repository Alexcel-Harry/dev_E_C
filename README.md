# Eye tracking validation and collection

The `collect` command now implements a combined numeric-data pilot: four-corner calibration, gaze targets, blink references/trials and ordinary reading. Follow [COLLECTOR_PILOT.md](docs/COLLECTOR_PILOT.md). `Linux_Eye_Tracking_Technical_Plan.docx` remains the design reference (25 October 2026, v1.2); personal model training, blink recognition and gesture control are future work. Development targets the Lenovo Linux laptop; its supplied reports show Ubuntu 24.04.5, Python 3.13.5 and GNOME Wayland. Use the usual glasses at a recorded comfortable distance; about 70 cm remains the nominal plan. Windows is the development/review machine only.

Read [NEXT_STEP.md](NEXT_STEP.md) for the maintained action queue and [the validation status](docs/VALIDATION_STATUS.md) for reviewed evidence. **Run 18 demonstrates basic directional and closure feature response; run 34 verifies visual EIS pointer mapping. Run 36 retry1 verifies active global pause using Ctrl+Alt+Space. Consent denial (37), portal revocation (38), and single-instance exclusion (39/40) passed. Invalid-device handling and fresh-process recovery passed in 41/42; offline startup/inference is accepted with user confirmation that networking was off. Controlled camera-cover response passed in run 49; run 43 remains unexplained historical evidence. Contention/recovery and scoped file inspection (44-47) are accepted. The collection plan now specifies four-corner calibration before each setup's target collection; setup notes belong in session metadata instead of optional file 48. See NEXT_STEP.md.** Record remaining [manual observations](docs/GUIDED_RESULTS_TEMPLATE.md); [the guided procedure](docs/GUIDED_VALIDATION.md) remains the protocol reference. The seated 720p/1080p runs and ten-minute 720p stability run are complete; do not repeat them by default. Use [the Linux checklist](docs/LINUX_CHECKLIST.md) for remaining checks and [the results template](docs/RESULTS_TEMPLATE.md) for new observations.

Current decision: basic capture/landmark stability is satisfactory for continuing at a provisional ~15 FPS, with 720p MJPG selected. The ten-minute run returned basic geometry for 8,892/8,898 frames (99.9326%). This is not gaze accuracy or a full validation pass. The 30 FPS application discrepancy, reliable gaze/blink classification remain unresolved. Camera recovery and offline startup are accepted for prototype progression, with scoped evidence limits documented. Active diagnostic pause passed with Ctrl+Alt+Space. EIS native coordinate mapping is visually verified for the tested setup. Basic eye-motion/closure response is provisionally demonstrated in run 18.

## Data collection pilot

Read the [data collection plan](docs/DATA_COLLECTION_PLAN.md) and [model architecture](docs/MODEL_ARCHITECTURE.md). The proposed flow is setup, four corners in clockwise order, an independent center check, then labeled target collection. Each target has a two-second preparation interval. The plan proposes a 1080p pilot, separate calibration and evaluation samples, and a small personal correction model. The combined pilot collector and per-session affine fit are implemented; the shared personal correction model is not. Live Linux collection and UI validation remain to be performed. The [pilot guide](docs/COLLECTOR_PILOT.md) specifies the actual CLI, labels, storage and provisional gates.

The user accepts held-button toggles and reserves **SSS for middle-button press/release**, with other detailed bindings deferred. Read the [action design](docs/ACTION_GESTURE_DESIGN.md) and [gesture collection/training specification](docs/GESTURE_COLLECTION_TRAINING.md). Gaze fitting and gesture recognition have separate labels and evaluations. Gesture recognition initially fits personalized thresholds and runs configurable sequence logic; a learned classifier is conditional. S/SS cannot dispatch while an SSS continuation remains possible.

The Word plan describes the design; current implementation status and pilot commands are maintained in the Markdown pilot guide. Historical validation procedures/results describe existing commands and evidence; they do not certify the planned gesture/controller behavior.

Included:

- Fullscreen `collect` workflow with two-second preparation, per-eye affine calibration, two gaze passes, explicit gesture confirmations, reading negatives, pause/repeat controls and private numeric traces.

- Read-only Linux, camera mode, package, portal and display inventory.
- Bounded V4L2 capture, requested versus actual mode, aggregate timing and CPU measurements.
- Optional local MediaPipe Face Landmarker diagnostics and an aspect-preserving Qt preview with enlarged eye crops.
- A 116-second `guided` live sequence with target-local instructions and excluded one-second transition buffers for eye movements, natural blinks, deliberate closures and face loss; independent eyelid/iris summaries for each phase.
- Explicit motion-only X11 or Wayland portal probes (legacy or EIS/libei), static fullscreen coordinate chart, and a separate pause command with optional acknowledgement report.
- Unit tests with synthetic observations and mocked runtime dependencies for diagnostic math, report handling, capture failure and pointer cancellation logic.

The camera path never emits input. `--model` loads pretrained weights; inference uses the LIVE webcam even without `--preview`. The .task file is not an input video. Frames and eye crops stay in memory. Validation reports contain aggregate diagnostic values. The separate `collect` command deliberately saves per-frame numeric observations, calibration inputs/coefficients and user-confirmed trial labels to a private XDG state directory; it saves no images or trained recognition model. The runtime does not download anything. Setup requires explicit dependency and model downloads; downloaded packages/models carry their own licenses.

Next: run the short Linux collection smoke session, review three full pilots, freeze the collection protocol/splits, collect both datasets, fit/evaluate gaze and blink components independently, then test the controller. The downloaded Face Landmarker is a diagnostic dependency, not a personally trained gaze model.

## Development checks

```bash
python -m unittest discover -s tests -v
python -m compileall -q eyecheck tests
python -m eyecheck --help
```

These checks do not open a camera or move a pointer. Windows tests cannot validate V4L2, Qt desktop integration, installed Linux wheels, portal consent, or XTest behavior.

## Reports and exit codes

The collector creates a unique private session directory and has no `--out` option; see its pilot guide for manifest/JSONL formats and incomplete-session handling. Each validation command accepting `--out` produces JSON. `recorded` means evidence was collected, not that hardware passed. Exit 0 means a completed probe, 1 means an error/blocked probe, and 2 means a camera run closed early or invalid command arguments. Each run should use a distinct output filename. A failed inventory command is preserved in its individual result, even when overall inventory is `recorded`.

The camera worker has an outer deadline of requested duration plus warmup plus 45 seconds. A stalled driver may therefore take that long to be terminated. Native calls run in a separate pointer worker with a 195-second outer deadline. Neither tool automatically restarts or reconnects. No production watchdog or gaze controller is claimed.

## Design limits

The legacy `camera` geometry adapter (version 1) checks finite in-frame coordinates and nondegenerate eye width. The new `guided` adapter (version 2) additionally rejects gross geometric outliers and measures eyelid plausibility independently of iris validity. Its engineering limits are not calibrated accuracy thresholds. It does not detect glare, prove iris visibility, classify intentional blinks, or validate gaze accuracy. Read the eye crops yourself. Reported geometry FPS is a screening measure, not the plan's final usable-gaze-update metric. Natural blinks remain in its denominator.

The pointer probe never sends buttons or keyboard events. On Wayland it explicitly requests one monitor plus pointer consent, then uses the explicitly selected transport without consuming screen frames. `--backend eis` uses compositor-advertised EIS regions via the installed libei1 library; the default legacy API remains available for historical diagnostics. EIS motion and visual mapping passed on Linux in run 34; active global pause passed in run 36 retry1 using Ctrl+Alt+Space; consent denial and portal revocation passed in reports 37/38; single-instance exclusion also passed in reports 39/40. Screen metadata and successful calls require visual coordinate verification, especially at fractional scaling. Production pause/watchdog, button release, suspend/lock handling, and permissions revoked during gestures belong to later controller tests.

Dependencies are intentionally not advertised as locked. Resolve and import them on the target Python first, retain the resulting package snapshot, and use that evidence to create a tested lock and offline bundle later. The supplied Linux import and dependency-consistency checks passed; this does not establish all runtime paths or a reproducible offline install. No Linux compatibility is inferred from Windows-only unit tests.

Use `--disable-dynamic-fps` for the current camera baseline. It sets and verifies `exposure_dynamic_framerate=0` after OpenCV mode setup and leaves that setting applied. Current application reports still measure ~14.8 FPS; it must not be described as a guaranteed 30 FPS fix. [The completed rerun procedure](docs/LIVE_RERUN.md) documents the commands and restoration option.

Primary API references checked during implementation:

- [MediaPipe Face Landmarker Python](https://ai.google.dev/edge/mediapipe/solutions/vision/face_landmarker/python)
- [RemoteDesktop portal](https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.RemoteDesktop.html)
- [ScreenCast portal](https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.ScreenCast.html)
