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
        print(f"Moved to {x:.0%}, {y:.0%}", flush=True)
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


async def portal(paused, progress=None, coordinate_scale=1.0):
    coordinate_scale = validate_coordinate_scale(coordinate_scale)
    from dbus_next.aio import MessageBus
    from dbus_next import Message, MessageType, Variant
    progress = progress if progress is not None else {}
    progress.update(backend="portal-legacy-NotifyPointerMotionAbsolute", stage="connect_bus",
                    coordinate_scale=coordinate_scale,
                    coordinate_scale_source="explicit_override" if coordinate_scale != 1 else "default",
                    coordinate_formula="normalized * (advertised_size - 1) * coordinate_scale")
    progress.setdefault("commands_sent", [])
    progress.setdefault("motion_calls", [])
    bus = await asyncio.wait_for(MessageBus().connect(), 10)
    destination = "org.freedesktop.portal.Desktop"
    path = "/org/freedesktop/portal/desktop"
    remote = "org.freedesktop.portal.RemoteDesktop"
    responses = {}
    closed = False
    session = None
    def receive(msg):
        nonlocal closed
        if msg.message_type == MessageType.SIGNAL:
            if msg.interface == "org.freedesktop.portal.Request" and msg.member == "Response":
                responses[msg.path] = msg.body
            if msg.interface == "org.freedesktop.portal.Session" and msg.member == "Closed" and msg.path == session:
                closed = True
                progress["session_closed"] = True
    bus.add_message_handler(receive)
    async def call(interface, member, signature="", body=None, object_path=path):
        reply = await asyncio.wait_for(bus.call(Message(destination=destination, path=object_path,
            interface=interface, member=member, signature=signature, body=body or [])), 10)
        if reply.message_type == MessageType.ERROR:
            raise RuntimeError(f"{member}: {reply.error_name}: {reply.body}")
        return reply.body
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
            operation_factory = partial(portal, coordinate_scale=coordinate_scale)
        else:
            raise RuntimeError("Use a local X11 session, or Wayland with --allow-screen-share for this legacy probe")
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
                "limits": ["Acknowledged calls do not establish visible cursor positions.",
                           "An in-flight native call may complete after pause; no later move is scheduled.",
                           "Legacy portal compatibility only; libei, clicks and production watchdog are untested."]}
