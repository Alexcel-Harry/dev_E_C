import asyncio
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

from eyecheck import pointer
from eyecheck.cli import main
from eyecheck.pointer_targets import markers


class Variant:
    def __init__(self, signature, value):
        self.value = value


class PortalTests(unittest.TestCase):
    def execute(self, denied=False, revoke=False, fail_second=False, pause_after_first=False):
        kind = types.SimpleNamespace(SIGNAL=1, ERROR=2, METHOD_RETURN=3)
        class Bus:
            def __init__(self):
                self.calls, self.moves = [], []
                self.disconnected = False
            async def connect(self): return self
            def add_message_handler(self, handler): self.handler = handler
            def disconnect(self): self.disconnected = True
            async def call(self, msg):
                self.calls.append(msg)
                if msg.member in ("CreateSession", "SelectDevices", "SelectSources", "Start"):
                    values = {}
                    if msg.member == "CreateSession":
                        values = {"session_handle": Variant("o", "/session/test")}
                    if msg.member == "Start":
                        values = {"devices": Variant("u", 2),
                                  "streams": Variant("a(ua{sv})", [(17, {"size": Variant("(ii)", [1648, 1030])})])}
                    handle = "/request/" + msg.member
                    self.handler(types.SimpleNamespace(message_type=kind.SIGNAL,
                        interface="org.freedesktop.portal.Request", member="Response", path=handle,
                        body=[1 if denied and msg.member == "Start" else 0, values]))
                    return types.SimpleNamespace(message_type=kind.METHOD_RETURN, body=[handle])
                if msg.member == "NotifyPointerMotionAbsolute":
                    self.moves.append(msg.body[-2:])
                    if fail_second and len(self.moves) == 2:
                        return types.SimpleNamespace(message_type=kind.ERROR, error_name="test.Revoked", body=[])
                    if revoke:
                        self.handler(types.SimpleNamespace(message_type=kind.SIGNAL,
                            interface="org.freedesktop.portal.Session", member="Closed", path="/session/test"))
                return types.SimpleNamespace(message_type=kind.METHOD_RETURN, body=[])
        bus = Bus()
        module = types.ModuleType("dbus_next")
        module.Message = lambda **kwargs: types.SimpleNamespace(**kwargs)
        module.MessageType, module.Variant = kind, Variant
        aio = types.ModuleType("dbus_next.aio")
        aio.MessageBus = lambda: bus
        original_sequence = pointer.sequence
        async def fast_sequence(move, paused, sent):
            return await original_sequence(move, paused, initial_delay=0, interval=0, sent=sent)
        progress, result, error = {}, None, None
        with patch.dict(sys.modules, {"dbus_next": module, "dbus_next.aio": aio}), \
             patch.object(pointer, "sequence", fast_sequence):
            try:
                result = asyncio.run(pointer.portal(lambda: pause_after_first and bool(bus.moves), progress))
            except RuntimeError as exc:
                error = str(exc)
        self.assertTrue(bus.disconnected)
        self.assertTrue(any(c.member == "Close" and c.interface == "org.freedesktop.portal.Session" for c in bus.calls))
        self.assertFalse(any("Button" in c.member or "Keyboard" in c.member or "OpenPipeWire" in c.member for c in bus.calls))
        return bus, progress, result, error

    def test_complete_sequence_uses_stream_coordinate_size(self):
        bus, progress, result, error = self.execute()
        self.assertIsNone(error)
        self.assertEqual(len(result["commands_sent"]), 6)
        self.assertEqual(bus.moves[0], [823.5, 514.5])
        self.assertAlmostEqual(bus.moves[1][0], 164.7)
        self.assertAlmostEqual(bus.moves[1][1], 102.9)
        self.assertTrue(all(c["state"] == "acknowledged" for c in progress["motion_calls"]))
        self.assertTrue(progress["session_close_acknowledged"])

    def test_denial_never_sends_motion(self):
        bus, progress, _, error = self.execute(denied=True)
        self.assertIn("cancelled or denied", error)
        self.assertEqual(bus.moves, [])
        self.assertEqual(progress["commands_sent"], [])
        self.assertEqual(progress["stage"], "Start")

    def test_pause_stops_before_second_move(self):
        bus, _, result, error = self.execute(pause_after_first=True)
        self.assertIsNone(error)
        self.assertEqual(len(bus.moves), 1)
        self.assertTrue(result["pause_observed"])

    def test_revocation_stops_without_claiming_pause(self):
        bus, _, result, error = self.execute(revoke=True)
        self.assertIsNone(error)
        self.assertEqual(len(bus.moves), 1)
        self.assertTrue(result["session_closed"])
        self.assertFalse(result["pause_observed"])

    def test_call_failure_preserves_attempt_and_completed_moves(self):
        _, progress, _, error = self.execute(fail_second=True)
        self.assertIn("test.Revoked", error)
        self.assertEqual(progress["commands_sent"], [[.5, .5]])
        self.assertEqual([c["state"] for c in progress["motion_calls"]], ["acknowledged", "attempted"])


class PointerSupportTests(unittest.TestCase):
    def test_runner_retains_partial_commands_on_error(self):
        fake_fcntl = types.SimpleNamespace(LOCK_EX=1, LOCK_NB=2, flock=lambda *a: None)
        async def fails(paused, progress):
            progress.update(stage="motion", commands_sent=[[.5, .5]])
            raise RuntimeError("synthetic backend failure")
        with tempfile.TemporaryDirectory() as folder, patch.object(pointer, "state_dir", return_value=Path(folder)), \
             patch.dict(sys.modules, {"fcntl": fake_fcntl}), patch.dict("os.environ", {"XDG_SESSION_TYPE": "wayland"}), \
             patch.object(pointer, "portal", fails):
            result = pointer.run(types.SimpleNamespace(allow_screen_share=True))
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["commands_sent"], [[.5, .5]])
        self.assertFalse(result["sequence_complete"])

    def test_second_instance_cannot_clear_first_instances_pause(self):
        def locked(*args): raise BlockingIOError()
        fake_fcntl = types.SimpleNamespace(LOCK_EX=1, LOCK_NB=2, flock=locked)
        with tempfile.TemporaryDirectory() as folder, patch.object(pointer, "state_dir", return_value=Path(folder)), \
             patch.dict(sys.modules, {"fcntl": fake_fcntl}):
            flag = Path(folder)/"pause"
            flag.touch()
            with self.assertRaisesRegex(RuntimeError, "Another pointer probe"):
                pointer.run(types.SimpleNamespace(allow_screen_share=True))
            self.assertTrue(flag.exists())

    def test_coordinate_size_validation_and_preference(self):
        self.assertEqual(pointer.coordinate_size({"size": [3296, 2060], "logical_size": [1648, 1030]}),
                         ([1648, 1030], "logical_size"))
        for size in (None, [1, 10], [0, 10], [True, 10], [float("nan"), 10], ["10", 10], [10]):
            with self.subTest(size=size), self.assertRaises(RuntimeError):
                pointer.coordinate_size({"size": size})

    def test_target_chart_coordinates_match_normalized_sequence(self):
        chart = markers(1648, 1030)
        self.assertEqual(chart[0]["logical_xy"], [824, 514])
        self.assertEqual(chart[1]["logical_xy"], [165, 103])
        self.assertEqual(chart[3]["normalized"], [.9, .9])

    def test_shortcut_can_save_pause_acknowledgement(self):
        with tempfile.TemporaryDirectory() as folder, patch("eyecheck.cli.platform.system", return_value="Linux"), \
             patch.object(pointer, "state_dir", return_value=Path(folder)):
            out = Path(folder)/"pause.json"
            self.assertEqual(main(["pause", "--out", str(out)]), 0)
            self.assertTrue((Path(folder)/"pause").exists())
            self.assertEqual(json.loads(out.read_text())["kind"], "pause")

    def test_pointer_reports_are_not_overwritten(self):
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stderr(io.StringIO()):
            out = Path(folder)/"existing.json"
            out.write_text("KEEP")
            for command in ("pointer", "pointer-targets"):
                with self.assertRaises(SystemExit):
                    main([command, "--out", str(out)])
                self.assertEqual(out.read_text(), "KEEP")


if __name__ == "__main__":
    unittest.main()
