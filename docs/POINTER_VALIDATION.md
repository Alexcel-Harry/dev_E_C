# Native EIS motion and global pause validation

**Current result: visual EIS coordinate mapping and active global pause accepted.** Reviewed chart 33, motion 34, and the user's confirmation of accurate alignment. All six targets were submitted once, with no error and clean EIS/portal cleanup. No additional coordinate run is needed for the unchanged laptop/display configuration. The earlier legacy backend remains unsuitable for this setup; use `--backend eis` explicitly.

Synced run 36-eis-pause-retry1 confirms one center move, pause observed, an incomplete sequence, no error and clean EIS/portal cleanup. The user manually confirms stopping with Ctrl+Alt+Space. Keep this existing working binding; Ctrl+Alt+P failed during troubleshooting for an unconfirmed reason. Sections 1-2 are retained as reference procedures, not requested reruns. **Consent denial also passed in pasted report 37. Proceed to section 3: available revocation, then single-instance checks.** This remains environment validation; no camera, gaze inference, clicks, scroll or keyboard injection is involved.

Use the local GNOME Wayland session and active virtual environment in `~/Desktop/YihaoSun/temp/dev_E_C`. Sync the cleanup fix in `eyecheck/pointer.py` and its tests before the next run. No new package or display-setting change is required.

## 1. Verify the global pause shortcut

If the shortcut is already configured with the acknowledgement output below, test it; do not create a duplicate. Otherwise print its exact command from the Linux project root:

```bash
python - <<'PY'
from pathlib import Path
import shlex, sys
print(shlex.join([sys.executable, '-m', 'eyecheck', 'pause', '--out',
                  str(Path('reports/21-shortcut.json').resolve())]))
PY
```

Use that printed command in a GNOME custom keyboard shortcut named Eyecheck pause, using the verified Ctrl+Alt+Space binding. Configure it through Settings → Keyboard → View and Customize Shortcuts → Custom Shortcuts. Use the absolute virtual-environment interpreter and report path printed above; do not put shell activation commands or `~` in the shortcut. See [GNOME's shortcut instructions](https://help.gnome.org/gnome-help/keyboard-shortcuts-set.html).

The current working Command entry uses this shell wrapper; keep it rather than replacing it during the remaining checks:

```text
/bin/sh -c '/home/yihaosun/Desktop/YihaoSun/temp/dev_E_C/.venv/bin/python -m eyecheck pause --out /home/yihaosun/Desktop/YihaoSun/temp/dev_E_C/reports/21-shortcut.json > /home/yihaosun/eyecheck-shortcut.log 2>&1'
```

Focus Text Editor, press the shortcut, then inspect:

```bash
cat reports/21-shortcut.json
```

Expected: `kind: pause`, `status: recorded` and a current `requested_at_unix_ns`. This proves the shortcut ran while another application was focused, not that it stopped active movement. This acknowledgement file is intentionally updated on each shortcut invocation. If it does not update, fix the shortcut before continuing.

## 2. Stop an active EIS sequence

Leave an ordinary blank Text Editor window available. No target chart is needed; mapping is already verified. Start:

```bash
python -m eyecheck pointer --backend eis \
  --enable-motion --allow-screen-share \
  --out reports/36-eis-pause-retry1.json
```

Select the laptop monitor and enable Allow Remote Interaction. Manual mouse use during consent is normal. When EIS is ready, focus Text Editor during the five-second countdown. After the first scheduled cursor move, promptly press the configured global shortcut before the next three-second interval. Observe whether movement stops and wait for the probe to finish.

For this trial, use the global shortcut rather than the terminal pause command or chart Escape. If the shortcut fails, `python -m eyecheck pause` from a terminal or Ctrl+C in the probe terminal remains a fallback; record the trial as a failed shortcut test and state which fallback you used.

Expected fresh pause report:

- `backend: portal-libei`, `status: recorded`, no error.
- `pause_observed: true`, `sequence_complete: false`, usually one target submitted.
- `eis_context_released: true`, `session_close_acknowledged: true`.
- No later scheduled moves observed; report 21's timestamp updates.

An already dispatched move can finish, so this is not a guaranteed stopping-latency test. Zero moves only verifies pause before motion; all six means the active-stop condition was not demonstrated. If more than one move occurs, describe when you pressed the shortcut so the report can be interpreted.

**Completed and reviewed: report 21 and 36-eis-pause-retry1.json, plus manual confirmation of stopping. No repeat is requested.** Keep existing reports; use a new suffix if retrying. The probe refuses existing pointer output filenames. A new explicitly started probe clears the previous pause request after acquiring its lock; pause ends the current diagnostic rather than permanently disabling future runs.

## 3. Subsequent EIS permission and lifecycle checks

Active pause and consent denial are accepted; revocation and single-instance behavior are the next Linux checks. Use fresh output filenames and keep Ctrl+Alt+Space ready. Return reports 37-40 with manual observations for review before proceeding to data collection.

Consent denial is completed (pasted report 37); retain this command as reference, not a requested rerun:

```bash
python -m eyecheck pointer --backend eis \
  --enable-motion --allow-screen-share --out reports/37-eis-denied.json
```

Cancel the consent dialog. Expect an error identifying cancellation/denial, with no submitted or attempted motion. If consent is not presented, pause and record NOT TESTED rather than assuming denial passed.

Next, for revocation, if GNOME offers a stop-sharing/remote-control control:

```bash
python -m eyecheck pointer --backend eis \
  --enable-motion --allow-screen-share --out reports/38-eis-revoked.json
```

Grant consent and use that desktop control during movement. Expect no later scheduled moves, with a portal closure or EIS device/seat/disconnect error. Manual mouse use to revoke consent is expected here. Revocation is distinct from `pause_observed`. Keep Ctrl+Alt+Space as fallback and report if it was used; a shortcut stop alone does not pass revocation. Record NOT TESTED if no such control is available. With the cleanup fix, an observed portal Closed signal yields `session_cleanup: already_closed_by_portal` and `session_close_acknowledged: null`; this means no redundant Close call was needed. If the portal has not reported closure, explicit Close is still attempted and failures remain visible.

For the single-instance check, start the first probe and leave its consent dialog open:

```bash
python -m eyecheck pointer --backend eis \
  --enable-motion --allow-screen-share --out reports/39-eis-lock-holder.json
```

From another terminal, while the first probe is still active:

```bash
python -m eyecheck pointer --backend eis \
  --enable-motion --allow-screen-share --out reports/40-eis-second-instance.json
```

Expect the second probe to reject with `Another pointer probe is running`, without clearing the first probe's pause flag or sending input. Cancel the first consent dialog afterward. If the dialog prevents switching applications, grant consent and launch the second probe during the first countdown, then stop the first with the shortcut. Preserve both reports and your observations.

## Evidence and limits

Run 34 used EIS logical coordinates in a 1648x1030 region at origin (0,0). Physical scale ~1.74757 and Qt DPR 2 are metadata, not target multipliers. The two equivalent region advertisements share a mapping ID and identical geometry. The implementation retains one device and submits each move once; conflicting geometry or loss of the selected device stops the probe.

The [RemoteDesktop portal](https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.RemoteDesktop.html) supplies the consented EIS connection. The backend uses [libei region coordinates](https://libinput.pages.freedesktop.org/libei/api/group__libei-region.html) and binds only absolute motion. It does not read PipeWire frames or fall back to legacy input. Submitted frames do not acknowledge visible cursor arrival; the user's observation completes the qualitative alignment check. Raw reports retain their original manual-verification field.

Sixty-six local tests passed with native interfaces mocked after the confirmed-closure cleanup fix. The user previously reported Linux tests passed; logs 32/35 were not synced at this review. Retain an existing log if available; the cleanup fix has not yet been exercised on Linux; preserve any Linux test output when available. The 195-second worker deadline bounds hangs, not instantaneous stopping; outer termination can produce a generic report without partial history.

Visual mapping is accepted only for the tested configuration. Revalidate after display changes. Active pause, denial/revocation and lock behavior are separate checks. Clicking, button-release handling, production watchdogs, suspend/lock recovery and eye-to-pointer calibration remain unimplemented or unverified.
