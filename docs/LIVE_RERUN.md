# Live camera rerun

**Completed and reviewed on 2026-10-23.** Both seated 60-second runs returned basic geometry on all 890 processed frames, at ~14.8 FPS. The subsequent ten-minute 720p run returned geometry on 8,892/8,898 frames (99.9326%). See [validation status](VALIDATION_STATUS.md) and [NEXT_STEP.md](../NEXT_STEP.md). This page preserves the procedure; no rerun is currently requested. If a repeat becomes necessary, use new output filenames to preserve existing evidence. The next requested run is [guided eye/closure validation](GUIDED_VALIDATION.md).

The camera command reads your LIVE webcam. `--model models/face_landmarker.task` loads pretrained model weights, not recorded video. Omitting `--preview` only hides the display window; the camera still captures you. Images stay in memory and are not saved.

Sync the updated `eyecheck/cli.py` and `eyecheck/camera.py` to Linux first (or sync the whole source project without overwriting Linux reports/models). The existing editable installation sees these source changes; no package upgrade is required. `python -m eyecheck camera --help` should list `--disable-dynamic-fps`.

Close other camera applications. Adjust lighting before running. Use your usual glasses, sit at a measured comfortable distance (about 70 cm if practical), and keep your entire face in view. Keep lighting, distance, lid angle and posture the same in both runs. Look naturally toward the screen; ordinary blinks are allowed. Do not leave, intentionally close your eyes for extended periods, or move closer/farther during measurement. Record any interruption rather than treating the run as a comparable baseline.

Run from the Linux project root with the virtual environment active. The ten-second warmup after camera setup gives you time to settle. Measurement starts at the `MEASURING LIVE CAMERA` message and lasts 60 seconds. Wait for the final JSON summary/terminal prompt. Terminal progress appears about every ten seconds.

```bash
python -m eyecheck camera \
  --device /dev/video0 --width 1280 --height 720 \
  --fps 30 --fourcc MJPG --disable-dynamic-fps \
  --warmup 10 --seconds 60 \
  --model models/face_landmarker.task \
  --label seated-same-light-720 \
  --out reports/14-seated-720.json
```

After the first run finishes, start the second and settle in the same position:

```bash
python -m eyecheck camera \
  --device /dev/video0 --width 1920 --height 1080 \
  --fps 30 --fourcc MJPG --disable-dynamic-fps \
  --warmup 10 --seconds 60 \
  --model models/face_landmarker.task \
  --label seated-same-light-1080 \
  --out reports/15-seated-1080.json
```

If you want to check framing beforehand, use the same command with `--preview --seconds 20` and a separate output filename. During the two comparison runs, keep preview disabled consistently.

The option applies dynamic frame rate 0 after OpenCV mode setup, verifies the driver's readback before capture, and records it in `dynamic_fps_control`. Failure to set/verify it stops the run. It does not guarantee 30 FPS; measured capture FPS remains the evidence. The option leaves the setting applied. If you want to restore the previous value of 1 after both runs:

```bash
v4l2-ctl -d /dev/video0 --set-ctrl=exposure_dynamic_framerate=1
```

Return both complete JSON files and your approximate distance/lighting description. We will compare actual capture rate, face availability, basic geometry and timing. Basic geometry still has permissive checks; implausible iris positions can be counted, and the rate is not a gaze-accuracy or click-reliability measurement. No training data collection is started by these runs.
