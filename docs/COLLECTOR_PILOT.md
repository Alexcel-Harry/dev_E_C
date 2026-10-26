# Run the combined collection pilot

Implemented 2026-10-25. `collect` gathers gaze, blink-sequence and ordinary-reading data in separate blocks within one session. It fits only the session's four-corner affine mapping. Personalized gaze training, blink decoding, button toggles and live pointer control are not implemented. SSS remains reserved for the future middle-button toggle.

## On the Linux laptop

Sync the updated `eyecheck/` and `tests/` directories and these documents into the existing checkout. Use the existing tested environment and local model; no new dependency or download is required. From `~/Desktop/YihaoSun/temp/dev_E_C` with `.venv` active:

```bash
python -m unittest discover -s tests -v
python -m eyecheck collect --plan --seed 42
```

The plan command prints the schedule without accessing the camera, GUI or dataset directory. A default session has 83 items: 4 anchors, 1 center check, 50 gaze targets, 2 references, 25 gesture trials and 1 reading block. Timed intervals total about 10 minutes, plus confirmations, breaks and retries. Allow about 15 minutes, longer if needed. The default overall recording bound is 30 minutes, including breaks; `--max-minutes 45` extends it explicitly, up to 60.

First run a short **pilot smoke session**. Replace the lighting, sitting ID, distance and setup notes with the actual conditions. `/dev/video0` is the previously tested RGB device; use the verified device if it has changed.

```bash
python -m eyecheck collect \
  --device /dev/video0 --width 1920 --height 1080 \
  --fps 30 --fourcc MJPG --disable-dynamic-fps \
  --model models/face_landmarker.task \
  --lighting "daylight" --distance-cm 70 \
  --notes "usual glasses; laptop on desk; facing straight; record power and light details here" \
  --sitting-id pilot-daylight-01 --split pilot \
  --trials-per-pattern 1 --reading-seconds 30
```

This retains all four anchors and 50 gaze targets, but uses one trial per pattern and 30 seconds reading. It is a prototype smoke run, not the full dataset budget. After checking the UI and saved records, omit `--trials-per-pattern` and `--reading-seconds` for each of the three full pilots (daylight, room light at night, desk lamp at night). `--include-ll` adds two optional LL trials in a pilot only. Let the collector choose a fresh random seed for normal sessions; fixed seeds are useful for debugging.

The requested 30 FPS is not a throughput claim: earlier runs delivered about 14.8 FPS. Actual frame dimensions must match the explicit request; a mismatch stops the run. Requested/driver modes, observed intervals, processed intervals and inference latency are retained. Do not silently substitute 720p; choose it explicitly only for a documented comparison.

## What happens on screen

1. Fullscreen setup shows the camera preview and the CLI metadata. Start becomes available after ten consecutive fresh frames with both-eye iris geometry. Inspect the image yourself; geometry sanity checks do not prove pupil visibility. Space starts.
2. Look at the small dot, clockwise: top-left, top-right, bottom-right, bottom-left. Each has two seconds preparation, then at least two seconds recording. An anchor extends to at most four seconds if fewer than 20 eligible frames are available. Insufficient coverage offers a retry. Degenerate fitting stops the session with an error.
3. The separate center check displays its median normalized error. It does not update calibration. Space explicitly accepts proceeding with this pilot; R repeats the check; Escape stops so you can adjust the setup and recalibrate in a new session. No calibrated accuracy threshold is claimed.
4. Follow 25 shuffled grid targets, take a break, then follow 25 stratified random targets. Every target has two seconds preparation and 1.5 seconds measurement. Fewer than ten eligible frames requires a retry. Predicted gaze and camera preview are hidden; the cursor is hidden locally during recording.
5. Record an open-eye reference (three seconds) and a comfortable closed-eye reference (two seconds), each after two seconds preparation. Confirm what you actually did. These are reference windows, not scored gesture events or automatically inferred closure boundaries.
6. Complete S, SS, SSS, L and SL prompts in shuffled order. S means approximately 0.5 seconds closed, L approximately 1.5 seconds; these are practice cues, not learned recognition thresholds. Wait for RECORD, perform the sequence with comfortable reopening gaps, and finish eyes open. Recording windows are 5/6/7/6/8 seconds respectively; optional LL is 9 seconds. A beep accompanies record/review transitions when the desktop supports it; use the visual cue for the start.
7. After every reference/trial, select what you actually performed, or uncertain/failed, and continue. Nothing is preconfirmed. To correct and retry, select the actual result first and press R; the old label and invalidated attempt remain in the record.
8. Read the supplied text naturally for three minutes, with ordinary blinking and no intentional commands. Left/right arrows change pages. Confirm `no command`, `commands present`, or `uncertain` afterwards. The window closes and the terminal reports the saved session. Completion is not a claim that quotas or quality criteria passed; inspect the manifest summary.

P pauses an active item; Space restarts it with a fresh two-second preparation interval. The interrupted attempt is invalidated. Losing window focus also pauses. The existing Ctrl+Alt+Space shortcut (`python -m eyecheck pause`) is observed through the shared pause file; stale signals are ignored at startup and the collector never deletes that flag. Pause responsiveness is bounded by pending inference/UI work, not a certified watchdog latency.

R repeats a review/retry item. During gaze measurement it restarts that target; during the next target's preparation it repeats the preceding target within the same pass. At a pass break it repeats the last target. Old attempts remain saved. Other active gesture/reading items can be restarted with P then Space. Escape/window close saves an incomplete session. Ctrl+C or a worker timeout may force interruption; retain partial evidence.

A changed distance, lighting, laptop angle, glasses position or display setup requires **stopping and launching a fresh session**. This first implementation uses one calibration ID per session; it does not silently reuse calibration or offer in-place recalibration. Keep the same sitting ID for all runs from the same sitting. A detected display/camera geometry change stops recording. Physical head/setup changes still require your judgement.

## Records and interpretation

The terminal prints the fresh session directory. Default: `~/.local/state/eyecheck/datasets/<timestamp-and-random-id>/`; an absolute `XDG_STATE_HOME` is honored. Keep this private data outside the repository. Linux session directories use 0700 and files 0600; an existing dataset directory with broader permissions is rejected, not silently chmodded. Existing session data is never overwritten.

| File | Contents |
| --- | --- |
| `manifest.json` | Protocol/schema versions; settings, sitting/split and calibration IDs; shuffled schedule/seeds; model/source hashes and package versions; actual mode/display/timing summaries; affine coefficients and exact anchor input timestamps; attempt status, confirmation counts, quota flags; final status and trace hashes. |
| `events.jsonl` | State transitions, actual paint acknowledgements and target coordinates, calibration fit, retries/invalidations, explicit confirmations, reading-page changes. |
| `observations.jsonl` | Numeric eye/pose measurements and validity/rejection flags, frame IDs and read/inference times, phase/role/attempt IDs, nominal targets where applicable, eligibility flags and optional unclamped session predictions. |

No images, eye crops, video, audio recordings or desktop input are saved/emitted. The local pretrained model processes live frames in memory. Unlike older aggregate diagnostics, this collector deliberately saves per-frame numeric traces, including missing-face and closed-eye observations. The existing latest-frame capture may skip frames when inference is slower than the camera and ignores exact duplicate images; frame IDs, gaps and capture statistics expose these limits.

`schema` is `eyecheck-numeric-session-v1`; protocol is `eyecheck-collection-pilot-v1`. Roles are `calibration_anchor`, `calibration_check`, `gaze_target`, `gesture_reference`, `gesture_trial`, `negative_reading` (plus setup context). Preparation, review and uncovered timing gaps are unscored for gaze. Read-completion time selects the phase, independently of when inference finishes. A capture read is not a sensor exposure timestamp, and a Qt paint callback is not physical scanout. Timing alignment needs pilot review.

The broad existing landmark checks and 250ms read-to-result gate are provisional. A low-openness iris rejection is not an intentional-blink classifier. Gesture observations remain available even when iris coordinates are unusable. Sequence windows have user-reported pattern labels, not verified event onset/offset annotations. Review/prepare gaps stay in the continuous trace with context but are not scored gesture windows. There is no automatic blink decoder supplying labels.

For future training, join rows to the final attempt ledger. Exclude invalidated/interrupted/insufficient attempts, preparation and review intervals from gaze fitting. Row-level `gaze_eligible` alone is insufficient. Calibration inputs, center checks and main gaze targets have separate roles; only designated anchors fit the affine map. The fit stores its exact input timestamps so a late result cannot silently change the recorded fit. For gesture evaluation, preserve failed/corrected trials and report them; do not silently discard errors. A matching prompted and confirmed sequence counts toward quota; a corrected different sequence does not fill that prompt's quota.

`recorded`/exit 0 means the scheduled flow completed. `incomplete`/exit 2 means user interruption; errors return 1. A forced parent termination marks the manifest incomplete and may leave a partial last JSONL line; it is evidence to diagnose, not training-ready data. Keep whole sessions/sittings/days together across splits. Test data must not tune thresholds; begin with pilots before freezing the full collection protocol.

## Return from the first pilot

Send the manifest and a brief note about preview/target readability, the four-corner order, preparation timing, center-check result, blink prompt comfort, confirmations and pause/repeat behavior. Retain the numeric traces locally for detailed review if needed. Do not send a video. Report the actual directory/status, observed FPS, eligible counts, corrected/uncertain trials and any error. Do not begin fifteen-session production collection until the pilot workload and labels have been reviewed.

Offline tests cover protocol chronology, fitting and data-role separation, retries and invalidation, confirmation independence, numeric storage, parent timeout recovery, worker cleanup and display-change stopping. Qt painting, V4L2, MediaPipe runtime behavior, sounds, desktop focus/global shortcut behavior and Linux permissions still require this user-run Linux pilot; Windows mocks do not certify them.
