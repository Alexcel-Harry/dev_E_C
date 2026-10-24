import asyncio
from collections import deque
import os
import types
import unittest
from unittest.mock import patch

from eyecheck.ei_native import Sender, region_point
from eyecheck import pointer


class Native:
    """A protocol lifecycle fixture, with deliberate nonzero region offsets."""
    def __init__(self, regions=None, resume=True, setup_result=0):
        self.regions = regions or [dict(x=200, y=100, width=1648, height=1030,
                                       physical_scale=2.0, mapping_id=b"display-A")]
        self.events = deque([(1, None), (3, None), (5, 41)] + ([(8, 41)] if resume else []))
        self.motion, self.frames, self.refs, self.unrefs, self.events_released = [], [], [], [], []
        self.motion_devices = []
        self.setup_result, self.fd, self.released = setup_result, None, False
        self.starts, self.stops, self.caps = [], [], []
    def ei_new_sender(self, data): return 1
    def ei_configure_name(self, ctx, name): pass
    def ei_setup_backend_fd(self, ctx, fd):
        self.fd = fd
        return self.setup_result
    def ei_unref(self, ctx):
        self.released = True
        os.close(self.fd)
    def ei_dispatch(self, ctx): pass
    def ei_get_event(self, ctx): return self.events.popleft() if self.events else None
    def ei_event_get_type(self, event): return event[0]
    def ei_event_get_device(self, event): return event[1]
    def ei_event_get_seat(self, event): return 5
    def ei_event_unref(self, event): self.events_released.append(event)
    def ei_seat_has_capability(self, seat, cap): return cap == 2
    def ei_seat_bind_capabilities(self, seat, cap, sentinel): self.caps.append((cap.value, sentinel.value))
    def ei_device_has_capability(self, device, cap): return cap == 2
    def ei_device_get_type(self, device): return 1
    def ei_device_ref(self, device):
        self.refs.append(device)
        return device
    def ei_device_unref(self, device): self.unrefs.append(device)
    def ei_device_get_region(self, device, index): return index + 1 if index < len(self.regions) else None
    def __getattr__(self, name):
        prefix = "ei_region_get_"
        if name.startswith(prefix):
            return lambda region: self.regions[region - 1][name[len(prefix):]]
        raise AttributeError(name)
    def ei_device_start_emulating(self, device, seq): self.starts.append(seq)
    def ei_device_stop_emulating(self, device): self.stops.append(device)
    def ei_device_pointer_motion_absolute(self, device, x, y):
        self.motion.append([x, y])
        self.motion_devices.append(device)
    def ei_device_frame(self, device, timestamp): self.frames.append(timestamp)
    def ei_now(self, ctx): return 100000


class EISTests(unittest.TestCase):
    def make_sender(self, native):
        fd = os.open(os.devnull, os.O_RDONLY)
        return Sender(fd, {"motion_calls": []}, native)

    def test_region_coordinates_include_offset_without_physical_multiplier(self):
        lib = Native()
        sender = self.make_sender(lib)
        try:
            self.assertTrue(asyncio.run(sender.wait_ready(lambda: False, "display-A")))
            for x, y in pointer.POINTS:
                sender.move(x, y)
            self.assertEqual(lib.motion[0], [1023.5, 614.5])
            self.assertAlmostEqual(lib.motion[2][0], 1682.3)
            self.assertEqual(lib.starts, [1])
            self.assertEqual(lib.caps, [(2, None)])
            self.assertEqual(len(lib.frames), 6)
            self.assertTrue(all(e["state"] == "submitted" for e in sender.progress["motion_calls"]))
        finally:
            sender.close()
        self.assertTrue(lib.released)
        self.assertEqual(lib.refs, lib.unrefs)
        self.assertEqual(lib.stops, [41])
        self.assertEqual(len(lib.events_released), 4)
        sender.close()  # Idempotent cleanup.

    def test_mapping_id_selects_correct_region_and_ambiguity_blocks(self):
        regions = [dict(x=0, y=0, width=100, height=80, physical_scale=1, mapping_id=b"A"),
                   dict(x=100, y=0, width=200, height=80, physical_scale=2, mapping_id=b"B")]
        for mapping in (None, "B", "absent"):
            lib = Native(regions=regions)
            sender = self.make_sender(lib)
            try:
                if mapping == "B":
                    asyncio.run(sender.wait_ready(lambda: False, mapping))
                    sender.move(.5, .5)
                    self.assertEqual(lib.motion, [[199.5, 39.5]])
                else:
                    with self.assertRaises(RuntimeError):
                        asyncio.run(sender.wait_ready(lambda: False, mapping, timeout=.02))
                    self.assertEqual(lib.motion, [])
            finally:
                sender.close()

    def test_lifecycle_loss_after_one_move_never_sends_second(self):
        for kind in (2, 4, 6, 7):
            with self.subTest(event=kind):
                lib = Native()
                sender = self.make_sender(lib)
                try:
                    asyncio.run(sender.wait_ready(lambda: False))
                    sender.move(.5, .5)
                    lib.events.append((kind, 41))
                    with self.assertRaises(RuntimeError):
                        sender.move(.9, .9)
                    self.assertEqual(len(lib.motion), 1)
                    self.assertEqual(lib.events_released[-1], (kind, 41))
                finally:
                    sender.close()
                self.assertTrue(lib.released)
                self.assertEqual(lib.refs, lib.unrefs)

    def test_equivalent_device_arrives_before_or_after_selection(self):
        # Reproduce run 31: CONNECT, SEAT_ADDED, ADDED/RESUMED twice.
        for late in (False, True):
            for mapping in (None, "display-A"):
                with self.subTest(late=late, mapping=mapping):
                    lib = Native()
                    sender = self.make_sender(lib)
                    try:
                        if not late:
                            lib.events.extend([(5, 42), (8, 42)])
                        asyncio.run(sender.wait_ready(lambda: False, mapping))
                        if late:
                            lib.events.extend([(5, 42), (8, 42)])
                        for x, y in pointer.POINTS:
                            sender.move(x, y)
                        self.assertEqual(len(lib.motion), 6)
                        self.assertEqual(lib.motion_devices, [41] * 6)
                        self.assertEqual(sender.progress["eis_events"], [1, 3, 5, 8, 5, 8])
                        self.assertEqual(sender.progress["eis_equivalent_region_count"], 2)
                    finally:
                        sender.close()
                    self.assertEqual(lib.refs, lib.unrefs)

    def test_duplicate_selection_uses_resumed_device_without_switching_later(self):
        lib = Native(resume=False)
        lib.events.extend([(5, 42), (8, 42)])
        sender = self.make_sender(lib)
        try:
            asyncio.run(sender.wait_ready(lambda: False, "display-A"))
            sender.move(.5, .5)
            lib.events.append((8, 41))
            sender.move(.1, .1)
            self.assertEqual(lib.motion_devices, [42, 42])
        finally:
            sender.close()

    def test_conflicting_or_unidentified_duplicates_block_initial_and_late_selection(self):
        base = dict(x=0, y=0, width=1648, height=1030, physical_scale=1.75, mapping_id=b"A")
        cases = [({**base, "mapping_id": None}, {**base, "mapping_id": None}),
                 (base, {**base, "width": 1800}), (base, {**base, "x": 10}),
                 (base, {**base, "physical_scale": 2}), (base, {**base, "mapping_id": b"B"})]
        for first, second in cases:
            for late in (False, True):
                lib = Native(regions=[first])
                sender = self.make_sender(lib)
                try:
                    if late:
                        asyncio.run(sender.wait_ready(lambda: False))
                    lib.regions = [first, second]
                    lib.events.extend([(5, 42), (8, 42)])
                    with self.assertRaisesRegex(RuntimeError, "Conflicting or ambiguous"):
                        if late:
                            sender.move(.5, .5)
                        else:
                            asyncio.run(sender.wait_ready(lambda: False))
                    self.assertEqual(lib.motion, [])
                finally:
                    sender.close()

    def test_selected_device_loss_does_not_fail_over_to_equivalent_device(self):
        for kind in (6, 7):
            lib = Native()
            lib.events.extend([(5, 42), (8, 42)])
            sender = self.make_sender(lib)
            try:
                asyncio.run(sender.wait_ready(lambda: False, "display-A"))
                sender.move(.5, .5)
                lib.events.append((kind, 41))
                with self.assertRaisesRegex(RuntimeError, "paused or removed"):
                    sender.move(.9, .9)
                self.assertEqual(lib.motion_devices, [41])
            finally:
                sender.close()

    def test_wait_requires_resumed_device_and_honors_pause(self):
        for pause in (False, True):
            lib = Native(resume=False)
            sender = self.make_sender(lib)
            try:
                if pause:
                    self.assertFalse(asyncio.run(sender.wait_ready(lambda: True)))
                else:
                    with self.assertRaisesRegex(RuntimeError, "No resumed"):
                        asyncio.run(sender.wait_ready(lambda: False, timeout=.02))
                self.assertEqual(lib.motion, [])
            finally:
                sender.close()

    def test_global_pause_after_first_submission_stops_sequence(self):
        lib = Native()
        sender = self.make_sender(lib)
        async def run():
            await sender.wait_ready(lambda: False)
            async def move(x, y): sender.move(x, y)
            return await pointer.sequence(move, lambda: bool(lib.motion), initial_delay=0, interval=0)
        try:
            sent, stopped = asyncio.run(run())
            self.assertEqual(sent, [[.5, .5]])
            self.assertTrue(stopped)
        finally:
            sender.close()

    def test_setup_failure_releases_context_and_fd(self):
        lib = Native(setup_result=-1)
        fd = os.open(os.devnull, os.O_RDONLY)
        with self.assertRaisesRegex(RuntimeError, "backend setup failed"):
            Sender(fd, {}, lib)
        self.assertTrue(lib.released)
        with self.assertRaises(OSError): os.fstat(fd)

    def test_fd_handle_index_and_invalid_reply_cleanup(self):
        for handle in (1, 2, -1, True):
            fds = [os.open(os.devnull, os.O_RDONLY) for _ in range(2)]
            reply = types.SimpleNamespace(body=[handle], unix_fds=fds)
            if handle == 1 and type(handle) is int:
                chosen = pointer.take_eis_fd(reply)
                self.assertEqual(chosen, fds[1])
                os.fstat(chosen)
                os.close(chosen)
            else:
                with self.assertRaisesRegex(RuntimeError, "invalid Unix"):
                    pointer.take_eis_fd(reply)
            for fd in fds:
                with self.assertRaises(OSError): os.fstat(fd)

    def test_invalid_region_and_coordinate_rejected(self):
        base = dict(x=0, y=0, width=1648, height=1030)
        for value in (-.1, 1.1, float("nan")):
            with self.assertRaises(RuntimeError): region_point(base, value, .5)
        for width in (0, 1, float("nan")):
            with self.assertRaises(RuntimeError): region_point({**base, "width": width}, .5, .5)

    def test_eis_rejects_scale_and_non_wayland_before_session(self):
        for session, scale in (("wayland", 2), ("x11", 1)):
            with patch.dict("os.environ", {"XDG_SESSION_TYPE": session}):
                with self.assertRaisesRegex(RuntimeError, "requires Wayland"):
                    pointer.run(types.SimpleNamespace(backend="eis", portal_coordinate_scale=scale))


if __name__ == "__main__":
    unittest.main()
