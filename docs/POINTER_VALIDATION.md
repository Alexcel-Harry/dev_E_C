# Native Wayland motion and global pause validation

This is the next Linux stage after reviewed camera/eye run 18. It tests the desktop input path independently of the camera and gaze model. The probe sends only six absolute pointer moves; no buttons, clicks, scroll or keyboard input. No new packages are needed. Sync `eyecheck/`, `tests/`, `docs/`, `README.md` and `NEXT_STEP.md`, preserving Linux `.venv/`, models and reports.

Use the local GNOME Wayland session, the laptop screen only, and the same display scale throughout. Do not run through SSH, as root, or switch display configuration during a trial. Use two terminals in the project root with the virtual environment active. Run `python -m unittest discover -s tests -v`; keep the output. Windows automated tests use simulated native interfaces; actual Linux results are still required.

Current reviewed progress (2026-10-24): run 20 retry obtained pointer permission and completed six calls, but the user reports incorrect positions confined to the left half. **Visual mapping failed.** Run the focused diagnostic below before continuing to active pause validation. Sections 1-6 retain the original procedure and filenames; do not overwrite existing reports.

## Current diagnostic: suspected 2x coordinate mismatch

Sync the updated code first. Keep the same laptop display and 200% scaling; keep the pause shortcut available (section 1). This tests an explicit multiplier, not automatic scale detection. Run the unit tests from the Linux project root before the motion test:

```bash
cd ~/Desktop/YihaoSun/temp/dev_E_C
python -m unittest discover -s tests -v
```

In terminal A, open a new chart and leave it open:

```bash
python -m eyecheck pointer-targets --out reports/27-pointer-targets-scale2.json
```

In terminal B, also in the project root with the virtual environment active:

```bash
python -m eyecheck pointer --enable-motion --allow-screen-share \
  --portal-coordinate-scale 2 \
  --out reports/28-wayland-motion-scale2.json
```

Select the laptop monitor and enable **Allow Remote Interaction**. Manual movement during consent is expected. Focus the chart during the five-second countdown, then keep hands off. Watch the arrow tip at center → upper-left → upper-right → lower-right → lower-left → center. Compare it to the crosses, not the text labels. Check vertical alignment as well as reaching the right half. If movement is wrong, use the pause shortcut or Escape while the chart is focused, and report the positions you did see; do not try successive arbitrary multipliers.

After the sequence, close the chart with Escape to save report 27. Record desktop versions once:

```bash
{
  gnome-shell --version
  dpkg-query -W -f='${binary:Package} ${Version}\n' \
    gnome-shell mutter-common xdg-desktop-portal xdg-desktop-portal-gnome
} 2>&1 | tee reports/29-desktop-versions.txt
```

Expected report 28: `coordinate_scale: 2`, `coordinate_scale_source: explicit_override`, advertised `size: [1648, 1030]`, first `unscaled_absolute: [823.5, 514.5]`, first sent `absolute: [1647, 1029]`, six acknowledged calls and a clean session close. These numbers are diagnostic inputs, not measured cursor positions. The pass condition is the observed arrow tip near every cross, without a systematic offset, compression or clipping. `manual_coordinate_verification` remains REQUIRED even when calls succeed.

Return reports 27-29, Linux unit-test output, and your observations for all targets. Stop here for review. If this works, the multiplier is a tested workaround for this display/backend configuration only. Subsequent motion/pause/revocation trials on this setup must use the validated multiplier explicitly; the default remains 1. Revalidate after any display/backend change. Do not change GNOME scaling to hide the issue.

## 1. Configure and verify the global pause shortcut

In the Linux project root, print the exact shortcut command:

```bash
python - <<'PY'
from pathlib import Path
import shlex, sys
print(shlex.join([sys.executable, '-m', 'eyecheck', 'pause', '--out',
                  str(Path('reports/21-shortcut.json').resolve())]))
PY
```

Paste that printed command into a GNOME custom shortcut named **Eyecheck pause**, for example Ctrl+Alt+P if unused. Use Settings → Keyboard → View and Customize Shortcuts → Custom Shortcuts. The absolute virtual-environment interpreter and editable install let it run outside the project directory. Do not use `~`, `source`, or the Windows project path in the shortcut command. [GNOME's shortcut instructions](https://help.gnome.org/gnome-help/keyboard-shortcuts-set.html) describe this configuration.

Focus Text Editor or another ordinary application and press the shortcut. Then inspect:

```bash
cat reports/21-shortcut.json
```

Expected: `kind: pause`, `status: recorded` and a current `requested_at_unix_ns`. This proves the command ran, not that an active pointer probe stopped. The later pause trial supplies that acknowledgement. This one report is intentionally overwritten on each shortcut invocation. If the file is not created/updated, fix the shortcut before moving the pointer.

The fallback terminal command is `python -m eyecheck pause`. A new explicitly started pointer run clears the old pause request after acquiring the single-instance lock. Pause ends the current diagnostic; it is not a persistent production disable switch.

## 2. Open the coordinate chart (terminal A)

```bash
python -m eyecheck pointer-targets --out reports/19-pointer-targets.json
```

A static fullscreen chart displays five crosses labelled 1/6 center, 2 upper-left, 3 upper-right, 4 lower-right, 5 lower-left. This process sends no pointer input. Keep it open while using terminal B for the trials. Alt+Tab switches back to it. Escape while the chart is focused requests pause and closes it; its JSON is saved on normal close, with final window/screen geometry. Escape is not a global shortcut when another app is focused.

## 3. Verify coordinates (terminal B)

```bash
python -m eyecheck pointer --enable-motion --allow-screen-share \
  --out reports/20-wayland-motion.json
```

In the portal dialog, enable **Allow Remote Interaction** (wording may vary), select the laptop monitor, then click Share. Selecting a screen alone can authorize sharing without pointer control. Manual mouse movement to complete this dialog is expected; hands off starts only after consent/setup. GNOME implements the interaction switch separately from screen selection: [upstream dialog source](https://raw.githubusercontent.com/GNOME/xdg-desktop-portal-gnome/main/src/remotedesktopdialog.c). After consent, the terminal prints the coordinate size and gives five seconds before the first move. Switch to the chart. Keep hands off the mouse/touchpad during the sequence.

Expected order: **center → upper-left → upper-right → lower-right → lower-left → center**, spaced three seconds apart (about 20 seconds after permission/setup). Look at the cursor's hotspot, normally its arrow tip, relative to each cross. The chart uses 10%, 50%, 90% positions. Record whether all six moves land near their crosses, or describe systematic offsets/scaling/clipping. API success alone does not establish mapping. Different reported stream and Qt sizes need interpretation; do not multiply coordinates by the display pixel ratio yourself.

Expected JSON: `status: recorded`, `sequence_complete: true`, six `commands_sent`, six acknowledged `motion_calls`, `pause_observed: false`, and no unexpected `session_closed`. `manual_coordinate_verification: REQUIRED` remains until your observations are reviewed. If it errors or positions are wrong, stop here and return the report plus what you saw.

### If the report says pointer permission was not granted

A completed consent response with `granted_devices: 0` means the probe received no input-device grant (or no devices field). It stops before sending motion. This is consistent with sharing the screen while leaving the remote-interaction switch off; it does not by itself prove that was the cause. Retry from the project root with a fresh report filename, explicitly enabling the interaction switch:

```bash
cd ~/Desktop/YihaoSun/temp/dev_E_C
python -m eyecheck pointer --enable-motion --allow-screen-share \
  --out reports/20-wayland-motion-retry1.json
```

Keep the chart open and the pause shortcut ready. If the switch is absent, already enabled, or the retry still returns zero, return the new JSON and a screenshot of the consent dialog. Do not change system remote-login settings or bypass portal consent. There is no code change required for this retry. Relative output paths resolve from the shell working directory, not the installed package directory.

## 4. Verify pause while another application is focused

```bash
python -m eyecheck pointer --enable-motion --allow-screen-share \
  --out reports/22-wayland-pause.json
```

Grant consent, focus an ordinary Text Editor window, observe the first scheduled move, then promptly press the configured global shortcut before the next three-second interval. Do not use the terminal fallback or chart Escape for this trial: they would not verify the global shortcut. Wait for the process to finish.

Expected: `pause_observed: true`, `sequence_complete: false`, usually one completed command, and no subsequent scheduled moves. The timestamp in `21-shortcut.json` should update. Polling is approximately every 50 ms while waiting, but shortcut launch, OS scheduling and in-flight native calls prevent a guaranteed response latency. An already dispatched move may complete; the probe must not schedule another afterward. Record exactly what you saw.

## 5. Verify permission denial

```bash
python -m eyecheck pointer --enable-motion --allow-screen-share \
  --out reports/23-wayland-denied.json
```

Cancel/deny the consent dialog. Expected: nonzero exit, `status: error`, a denial/cancellation explanation and no completed or attempted motion calls. If the desktop does not show a consent dialog, pause immediately and record denial as NOT TESTED; do not assume permission handling passed.

## 6. Session revocation and single-instance check

If GNOME exposes a stop-sharing/remote-control control, start a separate run to `reports/24-wayland-revoked.json`, allow consent, then use that desktop control during the sequence. Expected: no later scheduled moves, with `session_closed: true` or an error from a revoked native call. The report preserves completed commands and attempted/acknowledged calls. Revocation is separate from `pause_observed`. Record NOT TESTED if that control is unavailable.

For the lock check, keep a first pointer run open at its consent dialog:

```bash
python -m eyecheck pointer --enable-motion --allow-screen-share \
  --out reports/25-lock-holder.json
```

While that dialog remains open, start a second command from the other terminal (Alt+Tab away from the chart if necessary). If the dialog blocks application switching, grant consent and start the second command during the first probe's countdown or motion sequence:

```bash
python -m eyecheck pointer --enable-motion --allow-screen-share \
  --out reports/26-second-instance.json
```

Expected: the second process exits with an error containing `Another pointer probe is running` and sends no input. Return to the first dialog and cancel it, or use the pause shortcut if its motion sequence has already started. The second probe must not clear the first probe's pause state. Each command needs a distinct output file; existing pointer/target outputs are refused to preserve evidence.

After these tests, close the chart with Escape to write report 19. Do not use Ctrl+C to close the chart if you want its geometry report. Ctrl+C in the pointer-command terminal remains an interruption fallback; outer worker termination may produce a generic error without partial history. A native hang is bounded by the 195-second outer deadline, not instantaneous termination.

## Return evidence

Sync reports 19–26 that you executed, the Linux test output and [manual observations](POINTER_RESULTS_TEMPLATE.md). Missing optional trials should be labelled NOT TESTED. No screenshot or video is required initially. We will review coordinates, global pause and consent/session behavior before moving to the remaining environment checks or data collection.

## Scope and interpretation

The existing compatibility backend uses RemoteDesktop `NotifyPointerMotionAbsolute`, whose coordinates are stream-relative. It reads portal stream metadata, preferring `logical_size` when provided and otherwise `size`; it does not open PipeWire frames or capture screen images. The portal's `size` is compositor coordinate space and need not be video pixel dimensions. A legacy backend can still transform the submitted coordinates differently; equal chart/portal sizes alone are insufficient. The diagnostic multiplier preserves the metadata and applies `normalized * (size - 1) * coordinate_scale` to each axis; it is never selected automatically from Qt DPR. See [RemoteDesktop](https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.RemoteDesktop.html#org-freedesktop-portal-remotedesktop-notifypointermotionabsolute) and [ScreenCast](https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.ScreenCast.html) references checked for this implementation.

Success establishes only this compatibility path at the tested configuration. The preferred EIS/libei route, production clicking, button-release lifecycle, tracking watchdog, suspend/lock recovery and accurate eye-to-pointer control are not implemented or certified here. No input backend is driven by the camera in these tests.
