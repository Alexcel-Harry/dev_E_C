# Remaining validation checks

**Current status: cover/recovery (49), contention/recovery (44-46), and scoped Linux report inspection (47) are reviewed and accepted for prototype progression. File 48 is optional. No repeat is requested; the commands below are reference procedures. Next: collection-protocol design, with current setup recorded before actual collection.**

## Completed camera-cover diagnostic: run 49 (reference)

Reviewed run 49: 157 no-face frames during the dark cover interval, no face/geometry detections in seconds 13-22, geometry recovered from second 23, and normal completion. Source hashes match the reviewed code. Run 43 remains unexplained, but no further cover test is requested. The following paragraphs preserve why this targeted test was prepared.

Run 43 completed for 45.19 s with 668/668 frames marked basic geometry valid and no no-face/rejection counts. The user performed two long eye closures and one camera cover, and explicitly confirms the live preview lost their face for several seconds. The full-cover observation conflicts with uninterrupted reported geometry. Do not accept shutter/occlusion response from this run. Eye closure alone is not expected to invalidate the current geometry adapter; it is not an eye-open or pupil-visibility classifier. Aggregate openness minima cannot establish the timing or success of the two individual closures.

Only run 43 is newly synced; reports 44-48 remain unprovided. Keep its raw file. Prior accepted camera and desktop baselines are unchanged. Before collection, resolve the camera-cover discrepancy with a targeted repeat rather than tuning eyelid thresholds from this mixed run.

Sync `eyecheck/camera.py`, `eyecheck/cli.py`, the new `eyecheck/timeline.py`, and `tests/test_timeline.py`. The new optional `--diagnostic-timeline` records one-second aggregates of sampled grayscale mean/standard deviation/dark fraction, face detections, geometry and eyelid openness, frame-ID ranges and read-to-processing age. Empty bins represent no processed frames, not no-face observations. Samples are from the same input frame sent to the detector. It also records source SHA-256 hashes, run-start timestamp and early-stop reason. No images, video or per-frame landmarks are retained. These image statistics are diagnostic, not a new occlusion classifier. Extra computation makes this unsuitable as a directly comparable performance baseline. Existing runs are unchanged when the flag is absent, except the preview now includes elapsed time.

```bash
python -m eyecheck camera \
  --device /dev/video0 --width 1280 --height 720 \
  --fps 30 --fourcc MJPG --disable-dynamic-fps \
  --model models/face_landmarker.task --seconds 40 --preview \
  --diagnostic-timeline --label cover-only-timeline \
  --out reports/49-cover-only-timeline.json
```

Use the preview's elapsed measurement counter, not time since launching the command:

1. 0-10 s: face visible, eyes naturally open (ordinary blinking is fine).
2. 10-20 s: cover the active camera lens completely with an opaque card without touching the lens. Confirm your face disappears from the preview. Keep looking at the counter/terminal; do not deliberately close your eyes.
3. 20-40 s: uncover and keep your face visible until the run ends automatically.

The terminal emits DIAG lines approximately once per second and the preview shows elapsed time. No automatic cover/uncover cues are implemented; record approximate actual cover/uncover times and any timing deviations. Also record what the covered image looked like and whether CURRENT geometry became unavailable. Return the report. Do not send a video. A controlled cover would normally remove face detections; if geometry persists, the timeline should show whether the processed image changed. A uniform image can trigger the existing exact-duplicate/fresh-frame checks; retain any error rather than repeatedly retrying. Do not equate dark fraction alone with a successful cover or with visible pupils.

All 70 local tests pass with native interfaces mocked, including a simulated visible/covered/visible camera pipeline proving that no-face frames do not reuse previous geometry, empty-bin handling, invalid-geometry distinction and CLI constraints. Actual model response to the user's covered-camera input is still unresolved; this change adds evidence, not a claimed fix. No new package is needed.


Run on the Linux laptop from `~/Desktop/YihaoSun/temp/dev_E_C` with `.venv` active. Estimated active testing time: a few minutes. Camera commands never send pointer input. Keep the current camera, display, glasses and lighting configuration. The run-49 diagnostic requires syncing the timeline changes described above; no new package is needed.

Already accepted: baseline capture/geometry, guided feature feasibility, EIS mapping, Ctrl+Alt+Space pause, denial, revocation, single-instance exclusion, invalid-device handling, fresh-process recovery and offline startup/inference. Do not repeat those baselines. This checklist completes remaining observations; it is not training or gaze calibration.

Use fresh output names. If any filename below already exists, choose a new suffix and record it in the notes; camera reports can overwrite existing files. Start with other camera applications closed.

## 1. Privacy shutter and reopening (43)

If there is a physical privacy shutter, run:

```bash
python -m eyecheck camera \
  --device /dev/video0 --width 1280 --height 720 \
  --fps 30 --fourcc MJPG --disable-dynamic-fps \
  --model models/face_landmarker.task --seconds 45 --preview \
  --label shutter-reopen --out reports/43-shutter-reopen.json
```

After the live preview appears:

1. Leave the shutter open and your face visible for about 10 seconds.
2. Close the shutter for about 10 seconds; note whether the image goes black, changes, freezes, or the program exits.
3. Reopen it and stay visible until the command finishes. Do not close the preview early.

Expected for a purely optical shutter: useful face/eye observations disappear, then recover when reopened. The status line's CURRENT geometry should become unavailable; its total geometry count is cumulative and does not reset. The report should contain missing-face or invalid-geometry observations. This is a manual challenge: aggregate counts cannot prove which frames occurred in each shutter phase. If geometry remains available on a fully blocked image, record that as an issue, not a pass.

Some shutters may stop capture instead. An error report with a released capture thread can be valid device behavior; record what happened and use step 3 for fresh-process recovery. Do not assume automatic reconnect is implemented.

If there is no shutter, write NOT APPLICABLE. Optionally cover only the camera lens with an opaque card held in front of it, without touching it, and label this as a lens-cover substitute rather than a hardware-shutter test. Do not unplug or unbind the integrated camera.

## 2. Camera contention (44/45)

Open two terminals, activate the same `.venv` in both, and use the project directory in both. Finish step 1 first.

In terminal A:

```bash
python -m eyecheck camera \
  --device /dev/video0 --width 1280 --height 720 \
  --fps 30 --fourcc MJPG --disable-dynamic-fps --seconds 60 \
  --label contention-holder --out reports/44-camera-holder.json
```

As soon as terminal A prints a LIVE progress line, start in terminal B:

```bash
python -m eyecheck camera \
  --device /dev/video0 --width 1280 --height 720 \
  --fps 30 --fourcc MJPG --seconds 10 \
  --label contention-second --out reports/45-camera-second.json
```

Both commands are capture-only, so geometry fields are null by design. The second probe intentionally does not change the dynamic-FPS control. Wait for both commands to finish; record whether A continued, failed, or stalled when B started.

Expected possibilities: B fails cleanly because the camera is busy, or the driver supports two readers. Unlike the pointer probe, camera capture has no application-level single-instance lock. Concurrent success is not automatically a failure, and B's error does not by itself prove A was unaffected. Preserve both reports for review. If A had already finished before B started, this was not a contention test; record that instead of claiming a pass.

## 3. Fresh-process recovery after the challenges (46)

After both contention commands finish and the shutter is open:

```bash
python -m eyecheck camera \
  --device /dev/video0 --width 1280 --height 720 \
  --fps 30 --fourcc MJPG --disable-dynamic-fps \
  --model models/face_landmarker.task --seconds 15 --preview \
  --label post-challenge-recovery --out reports/46-camera-recovery.json
```

Expected: preview and live geometry return, no camera error or stuck thread, normal exit after the requested duration. This recovery check follows the new shutter/contention conditions; it is not another sustained baseline. If it fails, retain the error and stop for review rather than restarting the laptop to hide the failure.

## 4. Retained files and Linux permissions (47)

Run these read-only inspections on Linux after the camera commands finish. They list metadata, not file contents. Do not overwrite an existing 47 report.

```bash
umask 077
{
  printf 'Reports directory permissions:\n'
  stat -c '%a %U %n' reports
  printf '\nDirect report files (mode, owner, filename):\n'
  find reports -maxdepth 1 -type f -printf '%m %u %f\n' | sort
  printf '\nSubdirectories and symbolic links, if any:\n'
  find reports -mindepth 1 -type d -print
  find reports -type l -print
} | tee reports/47-retained-files.txt
```

Expected: newly generated camera JSON reports normally have mode 600 (owner read/write only). List any different modes for review; do not blindly chmod the project or existing files. Sync/copy tools may change permissions, and the inspected directory's existing mode is not automatically altered by Eyecheck. Expected outputs are JSON/text aggregates and the notes file below; no video, photos or continuous per-frame landmark traces are saved by these camera probes. Report unexpected files or subdirectories. This checks the reports directory, not all dependency caches or all network activity.

## 5. Setup and manual notes (48)

Optionally copy [CLOSEOUT_RESULTS_TEMPLATE.txt](CLOSEOUT_RESULTS_TEMPLATE.txt) to `reports/48-closeout-notes.txt` and fill it in. Chat observations or collection-session metadata are equally acceptable; file 48 is not required. Preserve any existing file by choosing a new suffix. Include measured distance, actual lighting, glasses, display settings, power/fan observations, actions performed, and any early stops. Mark items NOT TESTED or NOT APPLICABLE when appropriate. Do not invent observations for earlier runs.

Reports 43-47 and 49 have now been reviewed; 43 remains unexplained and 49 supplies controlled cover evidence. File 48 was omitted at the user's preference. Proceed to collection-protocol review; capture current setup notes before actual collection. No additional ten-minute run, native-pointer run, forced device-permission change or physical disconnection of the integrated camera is requested.
