"""Systemnahe Helfer für das Fenster auf Monitor 2 und das Sperren des Computers."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

IS_WINDOWS = sys.platform.startswith("win")

HWND_TOPMOST = -1
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040
SW_HIDE = 0
SW_SHOWNA = 8
MONITOR_DEFAULTTONEAREST = 2


def _user32():
    import ctypes
    from ctypes import wintypes

    u = ctypes.windll.user32  # type: ignore[attr-defined]
    u.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                               ctypes.c_int, wintypes.UINT]
    u.FindWindowExW.argtypes = [wintypes.HWND, wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR]
    u.FindWindowExW.restype = wintypes.HWND
    u.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
    u.MonitorFromWindow.restype = wintypes.HANDLE
    u.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    u.IsWindowVisible.argtypes = [wintypes.HWND]
    return u


# --------------------------------------------------------------------------- ganz vorne halten
def keep_on_top(widget) -> None:
    """Fenster über alles (auch über die Taskleiste) legen, ohne ihm den Fokus zu geben."""
    if not IS_WINDOWS:
        return
    try:
        _user32().SetWindowPos(int(widget.winId()), HWND_TOPMOST, 0, 0, 0, 0,
                               SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW)
    except Exception:  # noqa: BLE001
        pass


def not_on_top(widget) -> None:
    """Windows: „immer oben“ wieder abgeben (andere Fenster dürfen darüber)."""
    if not IS_WINDOWS:
        return
    try:
        _user32().SetWindowPos(int(widget.winId()), -2, 0, 0, 0, 0,  # HWND_NOTOPMOST
                               SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)
    except Exception:  # noqa: BLE001
        pass


# --------------------------------------------------------------------------- Taskleiste auf Monitor 2
class SecondaryTaskbar:
    """Windows: die Taskleiste auf Monitor 2 ausblenden, solange AluPC dort etwas zeigt."""

    def __init__(self):
        self.hidden: list[int] = []

    def hide_on(self, widget) -> None:
        if not IS_WINDOWS:
            return
        try:
            u = _user32()
            target = u.MonitorFromWindow(int(widget.winId()), MONITOR_DEFAULTTONEAREST)
            hwnd = None
            while True:
                hwnd = u.FindWindowExW(None, hwnd, "Shell_SecondaryTrayWnd", None)
                if not hwnd:
                    break
                if u.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST) == target and u.IsWindowVisible(hwnd):
                    u.ShowWindow(hwnd, SW_HIDE)
                    if int(hwnd) not in self.hidden:
                        self.hidden.append(int(hwnd))
        except Exception:  # noqa: BLE001
            pass

    def restore(self) -> None:
        if not IS_WINDOWS or not self.hidden:
            return
        try:
            u = _user32()
            for hwnd in self.hidden:
                u.ShowWindow(hwnd, SW_SHOWNA)
        except Exception:  # noqa: BLE001
            pass
        self.hidden = []


# --------------------------------------------------------------------------- KDE: „Immer im Vordergrund“
KWIN_KEEP_ABOVE = r"""
(function () {
    var list = (workspace.windowList !== undefined) ? workspace.windowList() : workspace.clientList();
    for (var i = 0; i < list.length; i++) {
        if (list[i].caption === %s) {
            list[i].keepAbove = %s;
            if (%s) { list[i].fullScreen = true; }
        }
    }
})();
"""


def kde_keep_above(caption: str, above: bool = True) -> None:
    """KDE (vor allem Wayland): Fenster über Leisten/Panels legen – Qt kann das dort nicht selbst.
    above=False: „immer oben“ wieder abgeben."""
    if IS_WINDOWS or "KDE" not in os.environ.get("XDG_CURRENT_DESKTOP", "").upper():
        return
    import json

    from .linux_windows import run_kwin_script

    flag = "true" if above else "false"
    run_kwin_script(KWIN_KEEP_ABOVE % (json.dumps(caption), flag, flag))


# --------------------------------------------------------------------------- Computer sperren
def lock_computer() -> None:
    """Wie Win+L: den ganzen Computer sperren (Windows bzw. Bildschirmsperre unter Linux)."""
    if IS_WINDOWS:
        import ctypes

        if not ctypes.windll.user32.LockWorkStation():  # type: ignore[attr-defined]
            raise RuntimeError("Windows hat das Sperren abgelehnt")
        return
    errors = []
    if shutil.which("loginctl"):
        proc = subprocess.run(["loginctl", "lock-session"], capture_output=True, text=True, timeout=10)
        if proc.returncode == 0:
            return
        errors.append(proc.stderr.strip())
    try:
        from . import dbus_util

        with dbus_util.connect("SESSION") as conn:
            dbus_util.call(conn, "org.freedesktop.ScreenSaver", "/org/freedesktop/ScreenSaver",
                           "org.freedesktop.ScreenSaver", "Lock", timeout=5)
        return
    except Exception as exc:  # noqa: BLE001
        errors.append(str(exc))
    for cmd in (["xdg-screensaver", "lock"], ["dm-tool", "lock"]):
        if shutil.which(cmd[0]) and subprocess.run(cmd, capture_output=True, timeout=10).returncode == 0:
            return
    raise RuntimeError("Sperren nicht möglich: " + "; ".join(e for e in errors if e))
