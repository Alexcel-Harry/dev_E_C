"""Explicit motion-only compatibility spike. Never imports camera or sends buttons."""
import asyncio
from functools import partial
import os
import math
from pathlib import Path
import time
import uuid

POINTS = [(0.5, 0.5), (0.1, 0.1), (0.9, 0.1), (0.9, 0.9), (0.1, 0.9), (0.5, 0.5)]


def state_dir():
    root = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp")) / f"eyecheck-{os.getuid()}"
    root.mkdir(mode=0o700, exist_ok=True)
    if root.is_symlink() or root.stat().st_uid != os.getuid() or root.stat().st_mode & 0o077:
        raise RuntimeError("Pointer state directory must be owned by you with mode 0700")
    return root


def pause():
    (state_dir() / "pause").touch(mode=0o600)
    print("Pause requested; an active motion probe stops before its next move")
    return {"schema": 1, "kind": "pause", "status": "recorded",
            "requested_at_unix_ns": time.time_ns(), "meaning": "Request written; active probe acknowledgement is pause_observed."}


async def sequence(move, paused, initial_delay=5, interval=3, sent=None):
    sent = [] if sent is None else sent
    for x, y in POINTS:
        # Five-second countdown first, then three seconds between moves.
        deadline = time.monotonic() + (initial_delay if not sent else interval)
        while time.monotonic() < deadline:
            if paused():
                return sent, True
            await asyncio.sleep(.05)
        if paused():
            return sent, True
        await move(x, y)
        sent.append([x, y])
        print(f"Requested target {x:.0%}, {y:.0%}", flush=True)
    return sent, False


async def x11(paused, progress=None):
    from Xlib import display, X
    from Xlib.ext import xtest
    progress = progress if progress is not None else {}
    progress["backend"] = "X11-XTest"
    progress["stage"] = "connect_x11"
    progress.setdefault("commands_sent", [])
    d = display.Display()
    try:
        if not d.has_extension("XTEST"):
            raise RuntimeError("XTEST extension is unavailable")
        s = d.screen()
        progress["size"] = [s.width_in_pixels, s.height_in_pixels]
        progress["stage"] = "motion"
        async def move(x, y):
            xtest.fake_input(d, X.MotionNotify, x=round(x * (s.width_in_pixels - 1)),
                             y=round(y * (s.height_in_pixels - 1)))
            d.sync()
        sent, stopped = await sequence(move, paused, sent=progress["commands_sent"])
        return {"backend": "X11-XTest", "size": [s.width_in_pixels, s.height_in_pixels],
                "commands_sent": sent, "pause_observed": stopped}
    finally:
        d.close()


def coordinate_size(properties):
    key = "logical_size" if "logical_size" in properties else "size"
    size = properties.get(key)
    if not isinstance(size, (list, tuple)) or len(size) != 2 or any(
        isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 1 for v in size
    ):
        raise RuntimeError("Portal did not advertise a usable coordinate size")
    return size, key


def validate_coordinate_scale(value):
    value = float(value)
    if not math.isfinite(value) or not 0 < value <= 4:
        raise ValueError("Portal coordinate scale must be finite, greater than 0 and at most 4")
    return value


def take_eis_fd(reply):
    """Resolve D-Bus's handle index, retaining one fd and closing any extras."""
    fds = list(getattr(reply, "unix_fds", []))
    selected = None
    try:
        if len(reply.body) != 1 or type(reply.body[0]) is not int or not 0 <= reply.body[0] < len(fds):
            raise RuntimeError("ConnectToEIS returned an invalid Unix file descriptor handle")
        selected = fds[reply.body[0]]
        return selected
    finally:
        for fd in set(fds):
            if fd != selected:
                os.close(fd)


def validate_legacy_positions(size, scale):
    if any(not (0 <= x * (size[0] - 1) * scale < size[0]
                and 0 <= y * (size[1] - 1) * scale < size[1]) for x, y in POINTS):
        raise RuntimeError("Legacy coordinate multiplier would exceed the advertised portal bounds; no moves sent")


async def portal(paused, progress=None, coordinate_scale=1.0, backend="legacy"):
    coordinate_scale = validate_coordinate_scale(coordinate_scale)
    if backend not in ("legacy", "eis") or (backend == "eis" and coordinate_scale != 1):
        raise RuntimeError("EIS uses advertised regions and does not accept a coordinate multiplier")
    from dbus_next.aio import MessageBus
    from dbus_next import Message, MessageType, Variant
    progress = progress if progress is not None else {}
    progress.update(backend="portal-libei" if backend == "eis" else "portal-legacy-NotifyPointerMotionAbsolute", stage="connect_bus",
                    coordinate_scale=coordinate_scale,
                    coordinate_scale_source="explicit_override" if coordinate_scale != 1 else "default",
                    coordinate_formula="normalized * (advertised_size - 1) * coordinate_scale")
    progress.setdefault("commands_sent", [])
    progress.setdefault("motion_calls", [])
    native = None
    if backend == "eis":
        from .ei_native import Sender, load_library
        progress["stage"] = "load_libei"
        native = load_library()
        progress["coordinate_formula"] = "EIS region offset + normalized * (EIS region size - 1)"
    bus = await asyncio.wait_for((MessageBus(negotiate_unix_fd=True) if backend == "eis" else MessageBus()).connect(), 10)
    destination = "org.freedesktop.portal.Desktop"
    path = "/org/freedesktop/portal/desktop"
    remote = "org.freedesktop.portal.RemoteDesktop"
    responses = {}
    closed = False
    session = None
    sender = None
    def receive(msg):
        nonlocal closed
        if msg.message_type == MessageType.SIGNAL:
            if msg.interface == "org.freedesktop.portal.Request" and msg.member == "Response":
                responses[msg.path] = msg.body
            if msg.interface == "org.freedesktop.portal.Session" and msg.member == "Closed" and msg.path == session:
                closed = True
                progress["session_closed"] = True
    bus.add_message_handler(receive)
    async def call(interface, member, signature="", body=None, object_path=path, raw_reply=False):
        reply = await asyncio.wait_for(bus.call(Message(destination=destination, path=object_path,
            interface=interface, member=member, signature=signature, body=body or [])), 10)
        if reply.message_type == MessageType.ERROR:
            raise RuntimeError(f"{member}: {reply.error_name}: {reply.body}")
        return reply if raw_reply else reply.body
    async def request(interface, member, signature, body):
        progress["stage"] = member
        token = "eyecheck_" + uuid.uuid4().hex
        body[-1]["handle_token"] = Variant("s", token)
        reply = await call(interface, member, signature, body)
        handle = reply[0]
        deadline = time.monotonic() + 60
        while handle not in responses:
            if closed or paused() or time.monotonic() > deadline:
                try:
                    await call("org.freedesktop.portal.Request", "Close", object_path=handle)
                finally:
                    raise RuntimeError("Portal consent timed out, session closed, or pause requested")
            await asyncio.sleep(.05)
        code, values = responses.pop(handle)
        if code != 0:
            raise RuntimeError(f"{member}: permission cancelled or denied ({code})")
        return {k: v.value for k, v in values.items()}
    try:
        reply = await asyncio.wait_for(bus.call(Message(destination="org.freedesktop.DBus", path="/org/freedesktop/DBus",
            interface="org.freedesktop.DBus", member="AddMatch", signature="s",
            body=["type='signal',sender='org.freedesktop.portal.Desktop'"])), 10)
        if reply.message_type == MessageType.ERROR:
            raise RuntimeError("Cannot subscribe to portal responses")
        created = await request(remote, "CreateSession", "a{sv}", [{"session_handle_token": Variant("s", "eyecheck_" + uuid.uuid4().hex)}])
        session = created["session_handle"]
        await request(remote, "SelectDevices", "oa{sv}", [session, {"types": Variant("u", 2)}])
        await request("org.freedesktop.portal.ScreenCast", "SelectSources", "oa{sv}",
                      [session, {"types": Variant("u", 1), "multiple": Variant("b", False)}])
        started = await request(remote, "Start", "osa{sv}", [session, "", {}])
        progress["granted_devices"] = started.get("devices", 0)
        if not started.get("devices", 0) & 2:
            raise RuntimeError("Pointer permission was not granted")
        streams = started.get("streams", [])
        if len(streams) != 1:
            raise RuntimeError("Select exactly the laptop display")
        stream, properties = streams[0]
        properties = {k: v.value for k, v in properties.items()}
        size, size_property = coordinate_size(properties)
        progress.update(size=list(size), size_property=size_property,
                        stream_id=stream, stage="motion", session_closed=False)
        if backend == "eis":
            progress["stage"] = "ConnectToEIS"
            reply = await call(remote, "ConnectToEIS", "oa{sv}", [session, {}], raw_reply=True)
            sender = Sender(take_eis_fd(reply), progress, native)
            progress["stage"] = "wait_eis_device"
            mapping_id = properties.get("mapping_id") or None
            progress["portal_mapping_id"] = mapping_id
            if not await sender.wait_ready(lambda: paused() or closed, mapping_id):
                return {"pause_observed": paused(), "session_closed": closed}
            progress["stage"] = "motion"
            print(f"EIS region ready: {progress['eis_selected_region']}. "
                  "First move in five seconds; focus the target chart now.", flush=True)
            def stopped():
                if paused() or closed:
                    return True
                sender.pump()
                return False
            async def move_eis(x, y):
                if paused() or closed:
                    raise RuntimeError("Pause or session closure before EIS dispatch")
                sender.move(x, y)
            sent, was_stopped = await sequence(move_eis, stopped, sent=progress["commands_sent"])
            if not was_stopped:
                await asyncio.sleep(.1)
                stopped()  # Surface immediately queued lifecycle failures after the final submission.
            return {"commands_sent": sent, "pause_observed": (was_stopped or paused()) and not closed,
                    "session_closed": closed,
                    "note": "libei submissions are not cursor-position acknowledgements. No PipeWire frames read."}
        validate_legacy_positions(size, coordinate_scale)
        print(f"Consent granted. Coordinate size: {list(size)} ({size_property}). "
              f"Diagnostic coordinate multiplier: {coordinate_scale:g}. "
              "First move in five seconds; focus the target chart now.", flush=True)
        async def move(x, y):
            if closed:
                raise RuntimeError("Portal session closed")
            unscaled = [float(x * (size[0] - 1)), float(y * (size[1] - 1))]
            # Explicit legacy-backend diagnostic; never infer this from Qt DPR alone.
            absolute = [v * coordinate_scale for v in unscaled]
            entry = {"normalized": [x, y], "unscaled_absolute": unscaled,
                     "absolute": absolute, "state": "attempted"}
            progress["motion_calls"].append(entry)
            await call(remote, "NotifyPointerMotionAbsolute", "oa{sv}udd", [session, {}, stream, *absolute])
            entry["state"] = "acknowledged"
        sent, stopped = await sequence(move, lambda: paused() or closed, sent=progress["commands_sent"])
        return {"backend": "portal-legacy-NotifyPointerMotionAbsolute", "size": list(size),
                "size_property": size_property,
                "commands_sent": sent, "pause_observed": stopped and not closed, "session_closed": closed,
                "note": "Compatibility spike only; libei path remains untested. No PipeWire frames opened or read."}
    finally:
        if sender:
            try:
                sender.close()
            except Exception as exc:
                progress["eis_cleanup_error"] = str(exc)
        if session:
            try:
                await call("org.freedesktop.portal.Session", "Close", object_path=session)
                progress["session_close_acknowledged"] = True
            except Exception as exc:
                progress["session_close_acknowledged"] = False
                progress["cleanup_error"] = str(exc)
        bus.disconnect()


def run(args):
    coordinate_scale = validate_coordinate_scale(getattr(args, "portal_coordinate_scale", 1.0))
    session = os.environ.get("XDG_SESSION_TYPE")
    backend = getattr(args, "backend", "legacy")
    if backend == "eis" and (session != "wayland" or coordinate_scale != 1):
        raise RuntimeError("--backend eis requires Wayland and an unmodified coordinate scale of 1")
    if session != "wayland" and coordinate_scale != 1:
        raise RuntimeError("--portal-coordinate-scale applies only to the Wayland portal probe")
    import fcntl
    root = state_dir()
    with (root / "lock").open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("Another pointer probe is running")
        flag = root / "pause"
        flag.unlink(missing_ok=True)
        if session == "x11":
            operation_factory = x11
        elif session == "wayland" and args.allow_screen_share:
            operation_factory = partial(portal, coordinate_scale=coordinate_scale, backend=backend)
        else:
            raise RuntimeError("Use a local X11 session, or Wayland with --allow-screen-share")
        print("Motion-only probe. Focus a blank window. Pause via your shortcut or Ctrl+C.", flush=True)
        progress = {"commands_sent": [], "pause_observed": False}
        try:
            result = asyncio.run(asyncio.wait_for(operation_factory(flag.exists, progress), 180))
            progress.update(result)
            status, error = "recorded", None
        except Exception as exc:
            status, error = "error", str(exc) or type(exc).__name__
            progress["pause_observed"] = flag.exists()
        return {"schema": 2, "kind": "pointer", "status": status, "error": error, **progress,
                "sequence_complete": len(progress["commands_sent"]) == len(POINTS),
                "manual_coordinate_verification": "REQUIRED", "buttons_tested": False,
                "expected_sequence": POINTS, "initial_delay_seconds": 5, "interval_seconds": 3,
                "limits": ["Acknowledged legacy calls or submitted EIS frames do not establish visible cursor positions.",
                           "An in-flight native call may complete after pause; no later move is scheduled.",
                           "Diagnostic only; clicks and production watchdog are untested."]}
