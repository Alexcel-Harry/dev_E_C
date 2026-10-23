# Linux validation checklist

Run on the Lenovo laptop in its local graphical login session. Do not use SSH, WSL, a container, or this Windows machine for hardware conclusions. Keep keyboard/touchpad access. Use only the laptop display for the initial tests; disconnect external displays. The probe is limited to one intended user.

Do these sections in order. Stop at a blocking failure and send its report; no need to complete later sections first. `recorded` is not an automatic pass. This stage collects diagnostic aggregates only; do not begin the gaze training dataset yet.

## 1. Copy and install

- [ ] Copy this project folder manually to the Linux laptop, excluding `.venv`, caches, reports from unrelated runs, and Windows generated packaging artifacts. Keep the plan with the source.
- [ ] Open a terminal in the Linux project root. The commands below are Bash commands.

```bash
sudo apt update
sudo apt install python3-venv python3-dev curl v4l-utils usbutils libglib2.0-bin libgl1 libegl1 libxkbcommon-x11-0 libxcb-cursor0
python3 --version
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
mkdir -p reports models
chmod 700 reports models
python -m eyecheck imports --out reports/01-imports.json
python -m unittest discover -s tests -v
```

Expected: Python 3.12 on the planned Ubuntu 24.04; all imports and `pip check` succeed, all unit tests pass. A different Python/OS is evidence to review, not a reason to replace system Python. If pip cannot resolve a wheel, stop and return its terminal error plus `python3 --version` and `uname -m`. Do not run the application as root. The `validation` extra is a candidate dependency set; target compatibility has not yet been tested.

After successful imports:

```bash
python -m pip freeze > reports/installed-packages.txt
```

This is an environment snapshot, not a portable hash lock. Inspect the editable install line for your local path before sharing it.

## 2. Inventory and desktop geometry

```bash
python -m eyecheck inventory --out reports/02-inventory.json
python -m eyecheck displays --out reports/03-displays.json
```

- [ ] Confirm expected machine/platform, architecture, OS, kernel and desktop session.
- [ ] In Ubuntu Settings > Displays, note resolution and scaling in the results template. Compare with Qt's logical geometry and device-pixel ratio. Record any mismatch.
- [ ] Identify candidate RGB capture nodes from `cameras` and their listed formats/intervals. Metadata and IR nodes must not be selected just because their number is small.
- [ ] Check each command's status. Missing tools, permission errors and portal errors are unresolved evidence, not a pass.

Expected: a camera node with Video Capture capability and usable color modes. Portal availability is only discovery. A missing RemoteDesktop interface blocks the supplied Wayland motion probe, but does not prove the camera is unusable. Do not change desktop sessions or permission rules before returning unexpected findings.

## 3. Capture and camera identity

Close browsers and other camera applications. Open the privacy shutter. Choose the verified candidate node below; `/dev/video0` is only an example. Confirm the advertised pixel format as well. Do not blindly use MJPG if it was not listed.

```bash
CAM=/dev/video0
python -m eyecheck camera --device "$CAM" --width 1280 --height 720 --fps 30 --fourcc MJPG --seconds 30 --preview --out reports/04-capture-720.json
```

- [ ] Preview is a normal RGB view of you, not an IR image or unrelated camera.
- [ ] Actual `frame_dimensions` match the request. Note `driver_reported.fourcc` and FPS; setting a mode is only a request.
- [ ] No prolonged freezing or read errors. Watch a small head movement to make frame freshness visible.
- [ ] Close the preview early once in a separate run: expect `incomplete` and exit code 2; a subsequent run must reopen the camera.

If 720p is unsupported, use an advertised mode, with 640x480 as a diagnostic fallback if available. If 1080p is listed, repeat with width 1920, height 1080 and `reports/04-capture-1080.json`. Do not count a silently substituted mode as the requested mode passing.

## 4. Local model setup and glasses preview

Download the Face Landmarker model during setup only. This command names the version-1 float16 model explicitly. The runtime never downloads it.

```bash
curl --fail --location --output models/face_landmarker.task https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task
sha256sum models/face_landmarker.task > reports/model-sha256.txt
```

If curl is missing, install it or use the model link in the official [Face Landmarker guide](https://ai.google.dev/edge/mediapipe/solutions/vision/face_landmarker/python). Keep the source URL, model version and associated license information. The generated SHA-256 records the exact local bytes; it does not independently authenticate the publisher.

```bash
python -m eyecheck camera --device "$CAM" --width 1280 --height 720 --fps 30 --fourcc MJPG --model models/face_landmarker.task --seconds 60 --preview --label glasses-70cm-diffuse-720 --out reports/05-eyes-720.json
python -m eyecheck camera --device "$CAM" --width 1920 --height 1080 --fps 30 --fourcc MJPG --model models/face_landmarker.task --seconds 60 --preview --label glasses-70cm-diffuse-1080 --out reports/05-eyes-1080.json
```

Run only advertised modes, changing FOURCC/FPS as needed. Use your usual glasses at approximately 70 cm, repeatable diffuse lighting, and the same lid angle/screen brightness.

- [ ] Pupils and lids are visible in both enlarged eye crops; enlarging a crop does not create more optical detail.
- [ ] With head still, look left/right/up/down. Landmarks move plausibly with the eyes.
- [ ] Observe natural blinks and several comfortable longer closures. Record whether lids remain trackable. No blink recognition or intentional-click score is claimed.
- [ ] Try light and dark screen content, a dimmer room and stronger side lighting in separate labeled runs. Record glare covering the pupils and unstable landmarks.
- [ ] Briefly leave the frame and return. Preview resumes; the report counts `no_face`. The pointer must never move during any camera run.
- [ ] Try 65 cm, 75 cm and glasses reseating as separate short challenges. These measure visibility/geometry only, not calibration accuracy.

Expected: repeatable eye geometry and visible pupils in baseline lighting. Choose a candidate mode jointly from optical detail, geometry rate, failures and processing time. No fixed minimum eye-width threshold is asserted. If no mode is clear enough, stop and adjust lighting/camera setup before any data collection.

## 5. Ten minute baseline

Use the selected mode. Keep eyes naturally open, including ordinary blinks; avoid deliberate long closures and face-loss challenges in this run. Preview is disabled to measure processing without display overhead.

```bash
python -m eyecheck camera --device "$CAM" --width 1280 --height 720 --fps 30 --fourcc MJPG --model models/face_landmarker.task --seconds 600 --label baseline-70cm-ten-minutes --out reports/06-sustained.json
```

- [ ] Run completes for approximately 600 measured seconds and has no error/stuck capture thread.
- [ ] Record capture reads/s, processed frames/s, geometry fraction/rate, exact duplicates, gap percentiles, inference/dequeue-to-result percentiles and CPU percentage.
- [ ] Record fan/heat behavior and whether the laptop was plugged in or on battery. CPU percent uses one CPU core as 100% and can exceed 100%.

The plan's initial goal is at least 20 usable gaze updates/s. Geometry at or above 20/s is only a preliminary feasibility screen; it does not certify usable gaze. A lower geometry rate needs investigation before continuing. These timestamps omit exposure and sensor/driver buffering and must never be labeled end-to-end gaze latency. This tool does not measure gaze accuracy or automatically exclude deliberate closures.

## 6. Failure and recovery checks

Use separate 30-second runs and distinct `--out` names.

- [ ] Invalid device: use `--device /dev/video9999`. Expect nonzero exit and an error report, with no movement or click.
- [ ] Camera contention: try opening a second camera probe while one runs. A second open may fail, or the driver may allow it. Record actual behavior; do not require failure if concurrent capture is supported.
- [ ] Privacy shutter: close it during a vision run. Some shutters produce black frames rather than a read failure. Expect loss of useful eye observations, not necessarily a device error. Record what occurs.
- [ ] Face loss: leave the camera view briefly. Expect no-face counts and no input.
- [ ] Disconnect: only if the camera is physically removable, unplug it during capture. Expect failure or bounded termination and an error report. Do not unbind the integrated camera driver for this test; mark it not tested.
- [ ] Permission failure: if ordinary user access already fails, preserve that report. Do not change `/dev` permissions or run as root to fabricate/pass this test. Otherwise mark forced permission revocation not tested.
- [ ] After each recoverable condition, start a new process and confirm preview works. There is no automatic reconnect.

## 7. Native motion and global pause

This is the only command that moves the pointer. It never clicks. First configure an Ubuntu custom keyboard shortcut, for example Ctrl+Alt+P, with the following command using the **actual absolute Linux project path**:

```text
/absolute/path/to/dev_E_C/.venv/bin/python -m eyecheck pause
```

The editable install makes this work without the shortcut's working directory being the project root. Test it once; a terminal invocation of `python -m eyecheck pause` is also available. This pause command only controls this diagnostic probe.

Open a blank window. Keep one monitor connected. Do not change display layout, scale, lock or suspend during the coordinate test.

For X11:

```bash
python -m eyecheck pointer --enable-motion --out reports/07-motion.json
```

For Wayland:

```bash
python -m eyecheck pointer --enable-motion --allow-screen-share --out reports/07-motion.json
```

The Wayland fallback requests pointer and monitor-sharing permission. Choose the laptop display. It uses stream metadata for coordinates; it does not open/read PipeWire video or save screenshots. It does not connect EIS/libei. If consent is denied, expect an error and no movement.

- [ ] After consent/setup, expect five seconds before the first move. Then center, upper-left, upper-right, lower-right, lower-left and center, at 10/50/90% coordinates and three-second spacing. Verify visually at the actual display scaling.
- [ ] Repeat to `reports/07-pause.json`, focus another application's window, and press the configured pause shortcut after the first move. Expect no further scheduled moves and `pause_observed: true`.
- [ ] On Wayland, repeat with `reports/07-denied.json` and deny consent. Expect nonzero exit and no move.
- [ ] On Wayland, if the desktop exposes a sharing stop control, revoke the session during a separate run. Expect motion to stop; record report/error. A call succeeding is not proof of an on-screen movement.
- [ ] Confirm a second concurrently started probe fails its single-instance lock.

If coordinates or pause fail, mark the backend unresolved. Return the evidence before implementing a helper or changing compositor settings. The portal fallback's success does not prove libei support. Lock/suspend, clicks, button release, vision watchdog and gesture cancellation are not implemented or certified by this motion-only probe.

## 8. Offline and retained files

- [ ] After setup, turn off Wi-Fi/unplug Ethernet and repeat a 30-second local-model preview. Expected: startup, inference and shutdown work without internet. Keep the desktop D-Bus session available.
- [ ] Inspect `reports/`: JSON/text aggregates only, no video, images or continuous landmark traces. Dependencies may create ordinary caches; list unexpected files in the results template.
- [ ] Verify report file permissions are private (`ls -l reports`). The tool uses mode 0600 for newly written reports; existing parent directories are not chmodded automatically.

Disconnecting networking is an offline smoke test, not a monitored proof of zero attempted network requests by every dependency. Network-denied auditing remains a release check.

## 9. Return evidence and decide the next stage

Fill in [RESULTS_TEMPLATE.md](RESULTS_TEMPLATE.md). Review reports before sharing: routine serial fields are redacted, but free-form driver/package errors may still expose paths or identifiers. Share the reports, filled template and installation errors. No photos or video are needed.

Decision to review together: correct RGB camera and actual mode; acceptable eye visibility in the chosen conditions; complete sustained run; import compatibility; known display geometry; demonstrated native motion and global pause, or a clearly unresolved backend. Do not equate this with T1 gaze accuracy, full T0 preferred-backend certification, or release readiness. Hold dataset collection until blocking issues are resolved and we agree on the collection protocol.
