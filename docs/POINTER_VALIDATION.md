# Native Wayland motion and global pause validation

This is the next Linux stage after reviewed camera/eye run 18. It tests the desktop input path independently of the camera and gaze model. The probe sends only six absolute pointer moves; no buttons, clicks, scroll or keyboard input. No new packages are needed. Sync `eyecheck/`, `tests/`, `docs/`, `README.md` and `NEXT_STEP.md`, preserving Linux `.venv/`, models and reports.

Use the local GNOME Wayland session, the laptop screen only, and the same display scale throughout. Do not run through SSH, as root, or switch display configuration during a trial. Use two terminals in the project root with the virtual environment active. Run `python -m unittest discover -s tests -v`; keep the output. Windows automated tests use simulated native interfaces; actual Linux results are still required.

Current reviewed progress: the user reports all prior Linux tests passed. Run 31 connected to EIS but sent no motion: a second device advertised the same region, and our guard incorrectly classified it as a display change. That guard is corrected. **Use fresh reports 33-35 below after syncing the fix.** Preserve run 31. The older legacy commands in sections 2-6 are historical reference; do not execute them for this validation.

## Current diagnostic: EIS motion at unchanged display scale

Your inventory already contains `libei1 1.2.1-1`; this implementation loads `libei.so.1` through Python's standard-library ctypes. No new pip package, compiler or desktop upgrade is requested. Sync the code and documents first. Keep only the laptop screen enabled, at the current scale, and use the virtual environment in both terminals. Verify the pause shortcut as described in section 1 before starting motion.

Run the tests on Linux and retain their output (64 tests expected):

```bash
cd ~/Desktop/YihaoSun/temp/dev_E_C
set -o pipefail
python -m unittest discover -s tests -v 2>&1 | tee reports/35-eis-retry-tests.txt
```

If tests fail, return the output before moving the pointer. In terminal A:

```bash
python -m eyecheck pointer-targets --out reports/33-pointer-targets-eis-retry1.json
```

In terminal B, also from the project root with the virtual environment active:

```bash
python -m eyecheck pointer --backend eis \
  --enable-motion --allow-screen-share \
  --out reports/34-wayland-eis-motion-retry1.json
```

Do not supply `--portal-coordinate-scale 2`; EIS rejects a scale override. Complete consent by selecting the laptop monitor and enabling **Allow Remote Interaction**. Manual mouse use during consent is normal. When `EIS region ready` appears, focus the chart within the five-second countdown, then keep hands off. Watch center → upper-left → upper-right → lower-right → lower-left → center, three seconds apart. The arrow tip should land near each cross on both axes, without a consistent offset, compression or clipping. If behavior is wrong, use the configured pause shortcut (or Escape while the chart is focused) and report what happened.

Close the chart with Escape after the sequence to save report 33. Expected report 34: backend `portal-libei`, a selected EIS region, six commands and six `motion_calls` with state `submitted`, `sequence_complete: true`, no error, `eis_context_released: true` and `session_close_acknowledged: true`. `pause_observed: false` is normal for an uninterrupted run. Inspect the recorded EIS region and resulting positions rather than assuming they equal the portal's stream dimensions. Physical scale is recorded, not applied as a multiplier. Equivalent region announcements are retained in `eis_regions`; `eis_equivalent_region_count` may be 2 while only one motion is submitted per target. `submitted` means libei API calls returned; it does not acknowledge cursor arrival. Visual verification is still REQUIRED.

If library loading, ConnectToEIS, region selection or device readiness fails, the report preserves the stage/error; there is no silent legacy fallback. Return the report without retrying arbitrary multipliers or changing display settings. The handshake is bounded to 10 seconds after the portal connection; existing consent/worker deadlines remain in effect. Device pause/removal, seat loss or disconnect stops the diagnostic, with no automatic reactivation.

Sync reports 33-35 and report the arrow-tip alignment at all five crosses, including the final return to center. Stop for review. Active global pause, permission denial, revocation and single-instance behavior must subsequently be validated using `--backend eis`; an EIS movement success alone does not complete them.

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

## 2. Historical legacy procedure: coordinate chart (terminal A)

```bash
python -m eyecheck pointer-targets --out reports/19-pointer-targets.json
```

A static fullscreen chart displays five crosses labelled 1/6 center, 2 upper-left, 3 upper-right, 4 lower-right, 5 lower-left. This process sends no pointer input. Keep it open while using terminal B for the trials. Alt+Tab switches back to it. Escape while the chart is focused requests pause and closes it; its JSON is saved on normal close, with final window/screen geometry. Escape is not a global shortcut when another app is focused.

## 3. Historical legacy procedure: coordinates (terminal B)

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

The EIS path uses [ConnectToEIS](https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.RemoteDesktop.html#org-freedesktop-portal-remotedesktop-connecttoeis), then exclusively libei input calls. It selects a matching mapping ID when present. Multiple candidates are accepted only if their nonempty mapping ID and all region metadata agree; otherwise they remain ambiguous. It selects one resumed device and never sends the same move to both or switches devices after selection. [EIS regions](https://libinput.pages.freedesktop.org/libei/api/group__libei-region.html) define their own coordinate space; their physical scale is not a multiplier for these normalized absolute targets. The ctypes binding uses the [libei sender API](https://libinput.pages.freedesktop.org/libei/api/group__libei-sender.html), retains device references, and releases the EIS context and its owned socket on completion/failure. Only the absolute-pointer capability is bound; no button or keyboard entry points are bound.

Sixty-four Windows tests pass with simulated native interfaces. They cannot validate the actual Linux library or compositor. Successful visual EIS mapping would establish only this motion path at the tested configuration. Production clicking, button-release lifecycle, tracking watchdog, suspend/lock recovery and accurate eye-to-pointer control remain unimplemented/unverified. No input backend is driven by the camera in these tests.
