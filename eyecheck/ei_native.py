"""libei sender for a consented, single-display motion diagnostic.

Only absolute motion is bound. EIS region coordinates are used directly;
physical_scale is metadata, never a multiplier. See the pointer guide for API sources.
"""
import asyncio
import ctypes as C
import math
import os
import time

ABSOLUTE = 2
CONNECT, DISCONNECT, SEAT_ADDED, SEAT_REMOVED = 1, 2, 3, 4
DEVICE_ADDED, DEVICE_REMOVED, DEVICE_PAUSED, DEVICE_RESUMED = 5, 6, 7, 8


def load_library():
    try:
        lib = C.CDLL("libei.so.1")
    except OSError as exc:
        raise RuntimeError("Cannot load libei.so.1; check the Linux libei1 package") from exc
    ptr, integer, uint = C.c_void_p, C.c_int, C.c_uint32
    signatures = {
        "ei_new_sender": (ptr, [ptr]), "ei_unref": (ptr, [ptr]),
        "ei_configure_name": (None, [ptr, C.c_char_p]),
        "ei_setup_backend_fd": (integer, [ptr, integer]),
        "ei_dispatch": (None, [ptr]), "ei_get_event": (ptr, [ptr]),
        "ei_event_unref": (ptr, [ptr]), "ei_event_get_type": (integer, [ptr]),
        "ei_event_get_seat": (ptr, [ptr]), "ei_event_get_device": (ptr, [ptr]),
        "ei_seat_has_capability": (C.c_bool, [ptr, integer]),
        # Variadic capability and NULL sentinel are explicitly typed at the call site.
        "ei_seat_bind_capabilities": (None, [ptr]),
        "ei_device_ref": (ptr, [ptr]), "ei_device_unref": (ptr, [ptr]),
        "ei_device_has_capability": (C.c_bool, [ptr, integer]),
        "ei_device_get_type": (integer, [ptr]),
        "ei_device_get_region": (ptr, [ptr, C.c_size_t]),
        "ei_region_get_x": (uint, [ptr]), "ei_region_get_y": (uint, [ptr]),
        "ei_region_get_width": (uint, [ptr]), "ei_region_get_height": (uint, [ptr]),
        "ei_region_get_mapping_id": (C.c_char_p, [ptr]),
        "ei_region_get_physical_scale": (C.c_double, [ptr]),
        "ei_device_start_emulating": (None, [ptr, uint]),
        "ei_device_stop_emulating": (None, [ptr]),
        "ei_device_pointer_motion_absolute": (None, [ptr, C.c_double, C.c_double]),
        "ei_device_frame": (None, [ptr, C.c_uint64]), "ei_now": (C.c_uint64, [ptr]),
    }
    for name, (result, args) in signatures.items():
        fn = getattr(lib, name)
        fn.restype, fn.argtypes = result, args
    return lib


def region_point(region, x, y):
    if any(not math.isfinite(v) or not 0 <= v <= 1 for v in (x, y)):
        raise RuntimeError("Normalized EIS position is outside [0, 1]")
    if any(not math.isfinite(region[k]) for k in ("x", "y", "width", "height")) or min(
        region["width"], region["height"]
    ) <= 1:
        raise RuntimeError("EIS region has invalid dimensions")
    return [region["x"] + x * (region["width"] - 1),
            region["y"] + y * (region["height"] - 1)]


class Sender:
    """Own the supplied fd, context and retained device refs until close()."""
    def __init__(self, fd, progress, lib):
        self.lib, self.progress = lib, progress
        self.context, self.devices, self.selected = None, {}, None
        self.emulating, self.failed = False, False
        self.progress["eis_events"] = []
        self.progress["eis_regions"] = []
        owned_fd = fd
        try:
            self.context = lib.ei_new_sender(None)
            if not self.context:
                raise RuntimeError("libei could not create a sender")
            lib.ei_configure_name(self.context, b"eyecheck-motion-diagnostic")
            # libei takes ownership, including on backend-setup failure.
            owned_fd = None
            result = lib.ei_setup_backend_fd(self.context, fd)
            if result < 0:
                raise RuntimeError(f"libei backend setup failed: {result}")
        except BaseException:
            if owned_fd is not None:
                os.close(owned_fd)
            self.close()
            raise

    def pump(self):
        self.lib.ei_dispatch(self.context)
        # Bound event processing so pause remains responsive.
        for _ in range(512):
            event = self.lib.ei_get_event(self.context)
            if not event:
                return
            try:
                kind = self.lib.ei_event_get_type(event)
                if len(self.progress["eis_events"]) < 128:
                    self.progress["eis_events"].append(kind)
                if kind in (DISCONNECT, SEAT_REMOVED):
                    self.failed = True
                    raise RuntimeError("EIS disconnected or removed its seat; no automatic reconnect")
                if kind == SEAT_ADDED:
                    seat = self.lib.ei_event_get_seat(event)
                    if self.lib.ei_seat_has_capability(seat, ABSOLUTE):
                        self.lib.ei_seat_bind_capabilities(seat, C.c_int(ABSOLUTE), C.c_void_p())
                elif kind in (DEVICE_ADDED, DEVICE_REMOVED, DEVICE_PAUSED, DEVICE_RESUMED):
                    device = self.lib.ei_event_get_device(event)
                    if kind == DEVICE_ADDED:
                        if self.lib.ei_device_has_capability(device, ABSOLUTE):
                            if self.lib.ei_device_get_type(device) != 1:
                                raise RuntimeError("EIS absolute device is not a virtual region device")
                            regions = []
                            for index in range(32):
                                region = self.lib.ei_device_get_region(device, index)
                                if not region:
                                    break
                                metadata = {k: getattr(self.lib, "ei_region_get_" + k)(region)
                                            for k in ("x", "y", "width", "height", "physical_scale")}
                                mapping = self.lib.ei_region_get_mapping_id(region)
                                metadata["mapping_id"] = mapping.decode("utf-8", "replace") if mapping else None
                                region_point(metadata, .5, .5)
                                if not math.isfinite(metadata["physical_scale"]) or metadata["physical_scale"] <= 0:
                                    raise RuntimeError("EIS advertised an invalid physical scale")
                                regions.append(metadata)
                            else:
                                raise RuntimeError("Too many EIS regions for this diagnostic")
                            if device in self.devices:
                                raise RuntimeError("Duplicate EIS device announcement")
                            self.devices[device] = {"ref": self.lib.ei_device_ref(device),
                                                    "resumed": False, "regions": regions}
                            self.progress["eis_regions"].extend(regions)
                    elif device in self.devices:
                        if kind in (DEVICE_PAUSED, DEVICE_REMOVED) and self.selected and device == self.selected[0]:
                            self.devices[device]["resumed"] = False
                            self.failed = True
                            raise RuntimeError("Selected EIS device paused or removed; motion stopped")
                        if kind == DEVICE_REMOVED:
                            self.lib.ei_device_unref(self.devices.pop(device)["ref"])
                        else:
                            self.devices[device]["resumed"] = kind == DEVICE_RESUMED
            finally:
                self.lib.ei_event_unref(event)
        raise RuntimeError("EIS event queue exceeded diagnostic limit")

    async def wait_ready(self, paused, mapping_id=None, timeout=10):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if paused():
                return False
            self.pump()
            candidates = [(device, region) for device, info in self.devices.items()
                          for region in info["regions"]
                          if mapping_id is None or region["mapping_id"] == mapping_id]
            if len(candidates) > 1:
                raise RuntimeError("Ambiguous EIS regions; use only the laptop display")
            if candidates and self.devices[candidates[0][0]]["resumed"]:
                self.selected = candidates[0]
                self.progress["eis_selected_region"] = dict(self.selected[1])
                self.progress["eis_region_selection"] = "mapping_id" if mapping_id else "only_region"
                return True
            await asyncio.sleep(.01)
        raise RuntimeError("No resumed EIS absolute region matching the selected screen before timeout")

    def move(self, x, y):
        self.pump()
        if self.failed or not self.selected or not self.devices[self.selected[0]]["resumed"]:
            raise RuntimeError("EIS device is not ready")
        device, region = self.selected
        matching = [(d, r) for d, info in self.devices.items() for r in info["regions"]
                    if self.progress["eis_region_selection"] == "only_region"
                    or r["mapping_id"] == region["mapping_id"]]
        if len(matching) != 1:
            raise RuntimeError("EIS display configuration changed; repeat validation")
        absolute = region_point(region, x, y)
        entry = {"normalized": [x, y], "absolute": absolute, "state": "attempted"}
        self.progress["motion_calls"].append(entry)
        if not self.emulating:
            self.lib.ei_device_start_emulating(device, 1)
            self.emulating = True
        self.lib.ei_device_pointer_motion_absolute(device, *absolute)
        self.lib.ei_device_frame(device, self.lib.ei_now(self.context))
        self.lib.ei_dispatch(self.context)
        entry["state"] = "submitted"  # No acknowledgement of the visible cursor position.

    def close(self):
        if not self.context:
            return
        try:
            if self.emulating and not self.failed:
                self.lib.ei_device_stop_emulating(self.selected[0])
                self.lib.ei_dispatch(self.context)
        finally:
            for info in self.devices.values():
                self.lib.ei_device_unref(info["ref"])
            self.devices.clear()
            self.lib.ei_unref(self.context)
            self.context = None
            self.progress["eis_context_released"] = True
