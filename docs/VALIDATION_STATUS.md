# Validation status

Updated: 2026-10-23 (America/Los_Angeles). This record summarizes user-executed Linux tests and synced reports. Windows is the development/review device. The user resumed implementation; guided validation is ready for a Linux run; [NEXT_STEP.md](../NEXT_STEP.md) is the maintained action queue.

## Decision

The one-minute controlled runs at 720p/1080p and ten-minute 720p run support continuing the prototype with the current camera. Select **1280x720 MJPG, approximately 15 observed updates/s**, as the provisional baseline because it provides comparable basic detection coverage with lower processing cost. Retain 1080p for a later accuracy comparison. No new camera purchase is indicated by these measurements.

This is acceptance of capture and basic-landmark stability for development, not full hardware validation, gaze accuracy, blink recognition, or release readiness. The original plan's 20 usable gaze updates/s target remains unmet. The user accepts exploring slower tracking; the FPS investigation is deferred, not resolved.

The original `Linux_Eye_Tracking_Technical_Plan.docx` (19 October 2026, v1.1) remains the historical design reference. This status record documents observed differences from its assumptions: Python 3.13.5 rather than proposed 3.12, a provisional ~15 FPS application baseline, and a still-unverified desktop backend. No later plan milestone is declared complete.

## Observed environment

| Item | Evidence |
| --- | --- |
| Machine | Lenovo XiaoXinPro 14 IMH9; product 83D2 |
| OS / architecture | Reported Ubuntu 24.04.5 LTS, x86_64 |
| Kernel / Python | Reported 7.0.0-38-generic / 3.13.5 |
| Desktop | Ubuntu GNOME, Wayland |
| Qt display | One screen; logical 1648x1030; device-pixel ratio 2; approximately 120 Hz. Physical resolution and native input mapping are not established by these values. |
| RGB camera | `/dev/video0`, Bison USB 5986:2169, `uvcvideo` |
| Advertised relevant modes | MJPG: 1280x720 and 1920x1080 at 30 FPS. YUYV: 720p at 10 FPS, 1080p at 5 FPS. |
| Other nodes | `/dev/video1` and `/dev/video3`: metadata. `/dev/video2`: grayscale capture; not selected. |
| Desktop portals | RemoteDesktop v2 advertises device types 7. GlobalShortcuts interface unavailable. Permission flow, pointer coordinates and pause have not yet been demonstrated. |
| Dependencies | All recorded imports, MediaPipe Tasks import and `pip check` passed. Installed versions retained in reports; no portable hash lock/offline bundle yet. |

Sources: [imports](../reports/01-imports.json), [inventory](../reports/02-inventory.json), [display report](../reports/03-displays.json), [package snapshot](../reports/installed-packages.txt). Reports are local ignored artifacts; sync them separately when needed. Thirty-one unit tests passed on Windows after the guided implementation (synthetic observations and mocked runtime, without camera/model/Qt execution); a target-Linux unit-test result was not supplied for review.

## Controlled camera results

| Run | Captured / processed | Basic geometry | Geometry FPS | Software time median / p95 | Maximum geometry gap |
| --- | --- | --- | --- | --- | --- |
| [720p seated, 60s](../reports/14-seated-720.json) | 890 / 890 | 890 (100%) | 14.80 | 28.71 / 39.59 ms | 76.77 ms |
| [1080p seated, 60s](../reports/15-seated-1080.json) | 890 / 890 | 890 (100%) | 14.80 | 36.68 / 47.44 ms | 86.31 ms |
| [720p seated, 600s](../reports/16-seated-720-ten-minutes.json) | 8,898 / 8,898 | 8,892 (99.9326%) | 14.82 | 28.98 / 39.17 ms | 340.41 ms |

All three runs completed with the requested dimensions and MJPG format, no reported capture errors, no stuck capture thread and no identical consecutive frames. The ten-minute run had six `no_face` observations. Its longest capture-read gap was 77.79 ms; the longer 340.41 ms geometry gap reflects missing observations, rather than a comparably long camera-read stall. The aggregate report does not identify the cause or exact timeline of those six observations.

Software timing is read-completion to processing result; it excludes exposure, sensor/driver buffering and desktop dispatch. It is not end-to-end eye-to-pointer latency. Aggregate timing is comparable to the short runs; per-minute thermal or performance trends cannot be reconstructed from these reports.

Median eye widths were approximately 41/40 pixels at 720p and 57/55 pixels at 1080p in the short runs, and 36/36 pixels in the sustained run. These are predicted corner-to-corner spans, not pupil resolution. The extreme normalized iris positions seen in exploratory reports are absent from these controlled reports. This supports plausibility, not measured landmark or gaze accuracy.

## FPS investigation

1. Initial OpenCV runs delivered approximately 14.8 FPS, with and without inference/preview; processing kept up with captured frames.
2. [Direct V4L2 with dynamic frame rate enabled](../reports/12-v4l2-direct.txt) captured 300 frames in 29.918s, approximately 10 FPS. [Before](../reports/12-controls-before.txt) and [after](../reports/12-controls-after.txt) control snapshots both showed `exposure_dynamic_framerate=1`.
3. [Direct V4L2 with the control set to zero in the same invocation](../reports/13-v4l2-dynamic-off.txt) approached 29.66 FPS and took 10.389s for 300 frames. The camera has therefore demonstrated approximately 30 FPS at 720p MJPG.
4. The application now offers `--disable-dynamic-fps`, applies it after mode setup and verifies zero before capture. Reports 14-16 confirm this readback, but measured capture delivery remains near 14.8 FPS. Readback during streaming is not recorded. Do not attribute the remaining difference to a proven cause.

The option leaves the control applied. Restoring the earlier value is explicit: `v4l2-ctl -d /dev/video0 --set-ctrl=exposure_dynamic_framerate=1`. The verified setting improves the direct V4L2 test; it has not restored 30 FPS in the application.

## Model and interpretation

`--model models/face_landmarker.task` loads pretrained weights. Camera commands always read LIVE `/dev/video0`; absence of `--preview` hides the window, not capture. Frames and temporary crops remain in memory. The task is Face Landmarker, with a Face Mesh V2 landmark model; the preview is ordinary OpenCV crop/resize/drawing, not an image enhancement model. Five displayed markers per eye represent two corners, upper/lower eyelid points and iris center.

Synced model SHA-256 matches the inference reports:

```text
64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff
```

The hash establishes consistency of the tested local bytes, not independent publisher authentication. Model weights are not being trained or personalized in these runs.

The existing `mediapipe478-eye-diagnostic-v1` adapter checks finite, in-frame landmarks and nondegenerate eye width. It can accept implausible iris positions, so `geometry_fraction` is basic geometry availability, not recognition accuracy. It also cannot certify lid tracking during closure. The new `guided` command uses `mediapipe478-eye-diagnostic-v2`: independent eyelid and iris validity, broad outlier rejection, and per-phase summaries. The existing `camera` command retains version 1 measurement semantics. Do not compare these validity counts as identical metrics.

## Guided implementation awaiting Linux validation

The [guided procedure](GUIDED_VALIDATION.md) now runs 106 seconds of prompts after warmup, with an aspect-preserving preview, independent closure observations, and aggregate-only reporting. Unit tests cover geometric checks, phase boundaries, incomplete runs, inference failure and cleanup. Real Qt rendering, audio prompts, model inference and camera integration still require the target Linux run. No new hardware result or gaze/gesture acceptance is claimed. Return the report with [manual notes](GUIDED_RESULTS_TEMPLATE.md).

## Evidence limits and unfinished checks

- Earlier reports 05, 09 and 10 are exploratory: the user moved away or changed setup. They cannot establish comparative resolution performance or sustained detection reliability. Report 10 contains model results despite a pasted command omitting `--model`.
- Earlier screenshots showed strong backlighting. The exact lighting arrangement, measured viewing distance, display brightness/lid angle, power source and thermal observations for the controlled runs are not recorded. Approximately 70 cm is the intended condition, not a verified measurement.
- Eye-only motion response, deliberate closure, ordinary-blink separation, glare challenges and distance tolerance remain unverified.
- The 340 ms observation gap must lead to appropriate freeze/cancellation/disarming in a future controller. That controller behavior is not implemented or tested by these camera probes; loss of tracking must not be interpreted as a blink.
- Native motion, global pause, consent denial/revocation and applicable capture recovery checks remain pending. Portal availability is not proof of functional input. The preferred libei path remains untested.
- Offline startup was designed for local operation, but a reviewed offline smoke test, network-attempt audit and persisted-file inspection have not been provided.
- Personal dataset collection, estimator training, calibration, independent gaze validation, click testing and deployment have not started.

Next work is defined in [NEXT_STEP.md](../NEXT_STEP.md). No further baseline rerun is required unless conditions change or a new diagnostic question justifies it.
