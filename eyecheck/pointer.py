"""Explicit motion-only compatibility spike. Never imports camera or sends buttons."""
import asyncio
import os
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


async def sequence(move, paused, initial_delay=5, interval=3):
    sent = []
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


async def x11(paused):
    from Xlib import display, X
    from Xlib.ext import xtest
    d = display.Display()
    try:
        if not d.has_extension("XTEST"):
            raise RuntimeError("XTEST extension is unavailable")
        s = d.screen()
        async def move(x, y):
            xtest.fake_input(d, X.MotionNotify, x=round(x * (s.width_in_pixels - 1)),
                             y=round(y * (s.height_in_pixels - 1)))
            d.sync()
        sent, stopped = await sequence(move, paused)
        return {"backend": "X11-XTest", "size": [s.width_in_pixels, s.height_in_pixels],
                "commands_sent": sent, "pause_observed": stopped}
    finally:
        d.close()


async def portal(paused):
    from dbus_next.aio import MessageBus
    from dbus_next import Message, MessageType, Variant
    bus = await MessageBus().connect()
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
    bus.add_message_handler(receive)
    async def call(interface, member, signature="", body=None, object_path=path):
        reply = await asyncio.wait_for(bus.call(Message(destination=destination, path=object_path,
            interface=interface, member=member, signature=signature, body=body or [])), 10)
        if reply.message_type == MessageType.ERROR:
            raise RuntimeError(f"{member}: {reply.error_name}: {reply.body}")
        return reply.body
    async def request(interface, member, signature, body):
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
        reply = await bus.call(Message(destination="org.freedesktop.DBus", path="/org/freedesktop/DBus",
            interface="org.freedesktop.DBus", member="AddMatch", signature="s",
            body=["type='signal',sender='org.freedesktop.portal.Desktop'"]))
        if reply.message_type == MessageType.ERROR:
            raise RuntimeError("Cannot subscribe to portal responses")
        created = await request(remote, "CreateSession", "a{sv}", [{"session_handle_token": Variant("s", "eyecheck_" + uuid.uuid4().hex)}])
        session = created["session_handle"]
        await request(remote, "SelectDevices", "oa{sv}", [session, {"types": Variant("u", 2)}])
        await request("org.freedesktop.portal.ScreenCast", "SelectSources", "oa{sv}",
                      [session, {"types": Variant("u", 1), "multiple": Variant("b", False)}])
        started = await request(remote, "Start", "osa{sv}", [session, "", {}])
        if not started.get("devices", 0) & 2:
            raise RuntimeError("Pointer permission was not granted")
        streams = started.get("streams", [])
        if len(streams) != 1:
            raise RuntimeError("Select exactly the laptop display")
        stream, properties = streams[0]
        properties = {k: v.value for k, v in properties.items()}
        size = properties.get("logical_size", properties.get("size"))
        if not size or len(size) != 2 or min(size) <= 0:
            raise RuntimeError("Portal did not advertise a usable coordinate size")
        async def move(x, y):
            if closed:
                raise RuntimeError("Portal session closed")
            await call(remote, "NotifyPointerMotionAbsolute", "oa{sv}udd",
                       [session, {}, stream, float(x * (size[0] - 1)), float(y * (size[1] - 1))])
        sent, stopped = await sequence(move, lambda: paused() or closed)
        return {"backend": "portal-legacy-NotifyPointerMotionAbsolute", "size": list(size),
                "size_property": "logical_size" if "logical_size" in properties else "size",
                "commands_sent": sent, "pause_observed": stopped and not closed, "session_closed": closed,
                "note": "Compatibility spike only; libei path remains untested. No PipeWire frames opened or read."}
    finally:
        if session:
            try:
                await call("org.freedesktop.portal.Session", "Close", object_path=session)
            except Exception:
                pass
        bus.disconnect()


def run(args):
    import fcntl
    root = state_dir()
    with (root / "lock").open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("Another pointer probe is running")
        flag = root / "pause"
        flag.unlink(missing_ok=True)
        session = os.environ.get("XDG_SESSION_TYPE")
        if session == "x11":
            operation = x11(flag.exists)
        elif session == "wayland" and args.allow_screen_share:
            operation = portal(flag.exists)
        else:
            raise RuntimeError("Use a local X11 session, or Wayland with --allow-screen-share for this legacy probe")
        print("Motion-only probe. Focus a blank window. Pause via your shortcut or Ctrl+C.", flush=True)
        result = asyncio.run(asyncio.wait_for(operation, 180))
        return {"schema": 1, "kind": "pointer", "status": "recorded", **result,
                "manual_coordinate_verification": "REQUIRED", "buttons_tested": False}
