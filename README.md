# Eye tracking validation

This is the first validation stage of `Linux_Eye_Tracking_Technical_Plan.docx` (19 October 2026, v1.1). Target: the Lenovo Linux laptop, expected Ubuntu 24.04, Python 3.12, usual glasses at about 70 cm. Windows is the development machine only.

Start with [the Linux execution checklist](docs/LINUX_CHECKLIST.md). Return the JSON reports and the completed [results template](docs/RESULTS_TEMPLATE.md). No target hardware result is assumed or certified by this code.

Included:

- Read-only Linux, camera mode, package, portal and display inventory.
- Bounded V4L2 capture, requested versus actual mode, aggregate timing and CPU measurements.
- Optional local MediaPipe Face Landmarker diagnostics and a Qt preview with enlarged eye crops.
- Explicit motion-only X11 or experimental Wayland portal compatibility probe and a separate pause command.
- Dependency-free unit tests for diagnostic math, report handling, capture failure and pointer cancellation logic.

The camera path never emits input. Frames and eye crops stay in memory. Reports contain aggregate diagnostic values, not images, per-frame traces, calibration samples, or trained models. The runtime does not download anything. Setup requires explicit dependency and model downloads; downloaded packages/models carry their own licenses.

Next stages, after review of the Linux results: resolve hardware/runtime issues, design data collection, train the personal estimator, calibrate and independently evaluate it, then implement deployment. The downloaded Face Landmarker is a diagnostic dependency, not a personally trained gaze model.

## Development checks

```bash
python -m unittest discover -s tests -v
python -m compileall -q eyecheck tests
python -m eyecheck --help
```

These checks do not open a camera or move a pointer. Windows tests cannot validate V4L2, Qt desktop integration, installed Linux wheels, portal consent, or XTest behavior.

## Reports and exit codes

Each command accepting `--out` produces JSON. `recorded` means evidence was collected, not that hardware passed. Exit 0 means a completed probe, 1 means an error/blocked probe, and 2 means a camera run closed early or invalid command arguments. Each run should use a distinct output filename. A failed inventory command is preserved in its individual result, even when overall inventory is `recorded`.

The camera worker has an outer deadline of requested duration plus warmup plus 45 seconds. A stalled driver may therefore take that long to be terminated. Native calls run in a separate pointer worker with a 195-second outer deadline. Neither tool automatically restarts or reconnects. No production watchdog or gaze controller is claimed.

## Design limits

The geometry adapter checks finite in-frame coordinates and nondegenerate eye width. It does not detect glare, prove iris visibility, classify intentional blinks, or validate gaze accuracy. Read the eye crops yourself. Reported geometry FPS is a screening measure, not the plan's final usable-gaze-update metric. Natural blinks remain in its denominator.

The pointer probe never sends buttons or keyboard events. On Wayland it explicitly requests one monitor plus pointer consent, then uses the legacy portal absolute-motion API without consuming screen frames. This tests a possible fallback only; the preferred libei route is still pending. Screen metadata and successful calls require visual coordinate verification, especially at fractional scaling. Production pause/watchdog, button release, suspend/lock handling, and permissions revoked during gestures belong to later controller tests.

Dependencies are intentionally not advertised as locked. Resolve and import them on the target Python first, retain the resulting package snapshot, and use that evidence to create a tested lock and offline bundle later. No dependency compatibility is inferred from this Windows environment.

Primary API references checked during implementation:

- [MediaPipe Face Landmarker Python](https://ai.google.dev/edge/mediapipe/solutions/vision/face_landmarker/python)
- [RemoteDesktop portal](https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.RemoteDesktop.html)
- [ScreenCast portal](https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.ScreenCast.html)
