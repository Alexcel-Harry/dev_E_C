# Linux validation results

Reusable template for future checks. Completed results are in [VALIDATION_STATUS.md](VALIDATION_STATUS.md); remaining actions are in [NEXT_STEP.md](../NEXT_STEP.md). Leave unperformed items as NOT TESTED rather than inferring a pass. Work is paused until the user resumes.

Date:
Source revision or date copied:
Ubuntu / kernel / Python:
Desktop / X11 or Wayland:
Display resolution / scaling / Qt logical geometry:
Power source:
Measured eye-to-camera/screen distance (state which):
Lighting / screen brightness / lid angle:
Any time out of frame or setup change during the run:

## Setup

- Imports and pip check:
- Unit tests (state Windows or target Linux):
- Missing packages or errors:
- Inventory report:
- Selected RGB node, driver, USB vendor/product IDs (omit serial):
- Available relevant modes (format, dimensions, FPS):

## Camera and eyes

| Run/report | Actual dimensions/format | Capture FPS | Processed FPS | Geometry FPS/fraction | Software latency median/p95 | Eye detail and glare |
| --- | --- | --- | --- | --- | --- | --- |
| 720p baseline | | | | | | |
| 1080p baseline | | | | | | |
| 10 minutes | | | | | | |
| Lighting challenges | | | | | | |
| 65/75 cm | | | | | | |

- Glasses, distance, lighting, screen brightness, lid angle:
- Eye-only movement visible:
- Natural/long closure observation (not recognition accuracy):
- Selected candidate mode and reason:
- CPU, temperature/fan observations and maximum gaps:
- Any actual-mode substitution or freezing:
- Dynamic frame-rate readback and whether checked before/during streaming:
- Maximum geometry-observation gap:
- Implausible iris coordinates or other validity concerns:

Geometry availability is not gaze or blink-recognition accuracy. Software timing excludes camera exposure and buffering.

## Failure behavior

Use PASS / FAIL / NOT TESTED and explain actual behavior.

- Invalid node:
- Early close and reopen:
- Contention:
- Shutter:
- Face loss:
- Physical disconnect (skip integrated camera):
- Permission denial (do not modify device permissions):
- Subsequent recovery:

## Desktop integration

- Native backend tested:
- Six positions visually correct:
- Global pause from another focused application:
- Pause report has pause_observed true:
- Wayland consent denial:
- Wayland session revocation:
- Single-instance lock:
- Any coordinate offset/scaling problem:
- libei preferred path: NOT TESTED by this toolkit
- Clicks, lock/suspend and production watchdog: NOT TESTED by this toolkit

## Offline and decision

- Offline preview result:
- Unexpected persisted files:
- Report privacy review complete:
- Blocking issues:
- Unresolved/manual checks:
- Proposed next action (resolve problems before collecting training data):
