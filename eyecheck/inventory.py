import glob
import json
import os
from pathlib import Path
import platform
import sys

from .common import command


def inventory():
    report = {"schema": 1, "kind": "inventory", "platform": platform.system(),
              "kernel": platform.release(), "architecture": platform.machine(),
              "python": platform.python_version(), "session": {
                  k: os.environ.get(k) for k in ("XDG_SESSION_TYPE", "XDG_CURRENT_DESKTOP", "WAYLAND_DISPLAY", "DISPLAY")},
              "native_absolute_input": "NOT_TESTED", "global_pause": "NOT_TESTED"}
    if platform.system() != "Linux":
        report.update(status="blocked", reason="Run inventory on the target Linux desktop")
        return report
    os_release = Path("/etc/os-release")
    report["os_release"] = os_release.read_text() if os_release.exists() else "unavailable"
    report["machine"] = {}
    for name in ("sys_vendor", "product_name", "product_version"):
        p = Path("/sys/class/dmi/id") / name
        try:
            report["machine"][name] = p.read_text().strip()
        except OSError:
            report["machine"][name] = "unavailable"
    commands = {
        "usb": ["lsusb"], "video_devices": ["v4l2-ctl", "--list-devices"],
        "portal_properties": ["gdbus", "call", "--session", "--dest", "org.freedesktop.portal.Desktop",
                              "--object-path", "/org/freedesktop/portal/desktop", "--method",
                              "org.freedesktop.DBus.Properties.GetAll", "org.freedesktop.portal.RemoteDesktop"],
        "shortcut_properties": ["gdbus", "call", "--session", "--dest", "org.freedesktop.portal.Desktop",
                                "--object-path", "/org/freedesktop/portal/desktop", "--method",
                                "org.freedesktop.DBus.Properties.GetAll", "org.freedesktop.portal.GlobalShortcuts"],
        "system_packages": ["dpkg-query", "-W", "-f=${Package} ${Version}\n", "v4l-utils", "usbutils",
                            "xdg-desktop-portal*", "libei*", "pipewire*"],
    }
    report["commands"] = {name: command(argv) for name, argv in commands.items()}
    report["cameras"] = {}
    for node in sorted(glob.glob("/dev/video[0-9]*")):
        report["cameras"][node] = {"read_write_access": os.access(node, os.R_OK | os.W_OK),
                                  "details": command(["v4l2-ctl", f"--device={node}", "--all", "--list-formats-ext"]),
                                  "controls": command(["v4l2-ctl", f"--device={node}", "--list-ctrls"])}
    # by-id names may contain serial numbers: only report whether such links exist.
    report["stable_camera_links_available"] = bool(glob.glob("/dev/v4l/by-id/*"))
    report["status"] = "recorded" if report["cameras"] else "blocked"
    report["note"] = "Device enumeration and portal properties do not prove RGB capture or input functionality."
    return report


def imports():
    checks = {}
    for module in ("numpy", "cv2", "mediapipe", "sklearn", "PySide6", "dbus_next", "Xlib"):
        checks[module] = command([sys.executable, "-c",
            f"import {module}; print(getattr({module}, '__version__', 'import OK'))"], timeout=45)
    checks["mediapipe_tasks"] = command([sys.executable, "-c",
        "from mediapipe.tasks.python.vision import FaceLandmarker, FaceLandmarkerOptions, RunningMode; print('Tasks API OK')"])
    return {"schema": 1, "kind": "imports", "python": platform.python_version(),
            "status": "ok" if all(c["status"] == "ok" for c in checks.values()) else "blocked",
            "checks": checks, "packages": command([sys.executable, "-m", "pip", "freeze"]),
            "dependency_consistency": command([sys.executable, "-m", "pip", "check"])}


def displays():
    from PySide6.QtGui import QGuiApplication
    app = QGuiApplication.instance() or QGuiApplication([])
    result = []
    for index, screen in enumerate(app.screens()):
        g = screen.geometry()
        result.append({"index": index, "logical_geometry": [g.x(), g.y(), g.width(), g.height()],
                       "device_pixel_ratio": screen.devicePixelRatio(), "refresh_hz": screen.refreshRate()})
    print(json.dumps({"schema": 1, "kind": "displays", "status": "recorded", "screens": result,
                      "qt_platform": app.platformName(), "note": "Qt geometry is not proof of native input coordinate mapping."}))
