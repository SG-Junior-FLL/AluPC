"""Programmfenster unter Linux auf Monitor 2 verschieben.

* KDE (X11 und Wayland): kleines KWin-Skript, das das aktive Fenster verschiebt.
* X11: zusätzlich Fensterliste und Verschieben über `wmctrl`.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import uuid

from . import dbus_util
from .base import WindowBackend, WindowInfo
from .linux_display import is_wayland

KWIN_SCRIPT = r"""
(function () {
    var targetName = %(name)s;
    var rect = %(rect)s;
    var fullscreen = %(fullscreen)s;
    var w = (workspace.activeWindow !== undefined) ? workspace.activeWindow : workspace.activeClient;
    if (!w) { return; }
    if (workspace.screens !== undefined) {
        // Plasma 6: Monitore sind Objekte mit Namen
        for (var i = 0; i < workspace.screens.length; i++) {
            if (workspace.screens[i].name === targetName) {
                workspace.sendClientToScreen(w, workspace.screens[i]);
                break;
            }
        }
    } else {
        // Plasma 5: Monitore sind Nummern, über die Position finden
        for (var j = 0; j < workspace.numScreens; j++) {
            var a = workspace.clientArea(KWin.ScreenArea, j, workspace.currentDesktop);
            if (a.x === rect[0] && a.y === rect[1]) {
                workspace.sendClientToScreen(w, j);
                break;
            }
        }
    }
    if (fullscreen) { w.fullScreen = true; } else { w.setMaximize(true, true); }
})();
"""


def build_kwin_script(output_name: str, rect: tuple[int, int, int, int], fullscreen: bool) -> str:
    return KWIN_SCRIPT % {
        "name": json.dumps(output_name),
        "rect": json.dumps(list(rect)),
        "fullscreen": "true" if fullscreen else "false",
    }


def start_kwin_script(source: str) -> str:
    """KWin-Skript laden und starten; es läuft weiter, bis `stop_kwin_script(name)` es entfernt."""
    plugin = f"alupc_{uuid.uuid4().hex[:8]}"
    fd, path = tempfile.mkstemp(prefix="alupc-", suffix=".js")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(source)
    iface = "org.kde.kwin.Scripting"
    try:
        with dbus_util.connect("SESSION") as conn:
            (script_id,) = dbus_util.call(conn, "org.kde.KWin", "/Scripting", iface,
                                          "loadScript", "ss", (path, plugin))
            if script_id < 0:
                raise RuntimeError("KWin konnte das Skript nicht laden")
            last_error = None
            # Plasma 6 und Plasma 5 benutzen unterschiedliche Objektpfade
            for obj in (f"/Scripting/Script{script_id}", f"/{script_id}"):
                try:
                    dbus_util.call(conn, "org.kde.KWin", obj, "org.kde.kwin.Script", "run")
                    break
                except Exception as exc:  # noqa: BLE001
                    last_error = exc
            else:
                stop_kwin_script(plugin)
                raise RuntimeError(f"KWin-Skript konnte nicht gestartet werden: {last_error}")
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
    return plugin


def stop_kwin_script(plugin: str) -> None:
    try:
        with dbus_util.connect("SESSION") as conn:
            dbus_util.call(conn, "org.kde.KWin", "/Scripting", "org.kde.kwin.Scripting", "unloadScript", "s",
                           (plugin,))
    except Exception:  # noqa: BLE001
        pass


def run_kwin_script(source: str) -> None:
    """KWin-Skript einmal ausführen (und gleich wieder entfernen)."""
    stop_kwin_script(start_kwin_script(source))


def parse_wmctrl(text: str) -> list[WindowInfo]:
    windows = []
    for line in text.splitlines():
        parts = line.split(None, 4)
        if len(parts) < 5:
            continue
        win_id, desktop, wm_class, _host, title = parts
        if desktop == "-1":  # Leisten, Desktop usw.
            continue
        app = wm_class.split(".")[-1]
        windows.append(WindowInfo(id=win_id, title=title, app=app))
    return windows


class LinuxWindowBackend(WindowBackend):
    def __init__(self):
        self.kde = "KDE" in os.environ.get("XDG_CURRENT_DESKTOP", "").upper() \
            or shutil.which("kwin_wayland") is not None or shutil.which("kwin_x11") is not None
        self.wmctrl = shutil.which("wmctrl") is not None and not is_wayland()
        self.can_list = self.wmctrl
        self.can_move_active = self.kde and dbus_util.HAVE_JEEPNEY

    def list_windows(self) -> list[WindowInfo]:
        if not self.wmctrl:
            return []
        out = subprocess.run(["wmctrl", "-lx"], capture_output=True, text=True, timeout=10).stdout
        return parse_wmctrl(out)

    def move_window(self, window_id, output_name, rect, fullscreen=False):
        x, y, w, h = rect
        base = ["wmctrl", "-i", "-r", window_id]
        subprocess.run(base + ["-b", "remove,maximized_vert,maximized_horz,fullscreen"], timeout=10)
        subprocess.run(base + ["-e", f"0,{x + 20},{y + 20},{max(200, w // 2)},{max(150, h // 2)}"], timeout=10)
        state = "fullscreen" if fullscreen else "maximized_vert,maximized_horz"
        subprocess.run(base + ["-b", f"add,{state}"], timeout=10)
        subprocess.run(["wmctrl", "-i", "-a", window_id], timeout=10)

    def move_active_window(self, output_name, rect, fullscreen=False):
        if not self.can_move_active:
            raise RuntimeError("Nur unter KDE Plasma möglich (KWin)")
        run_kwin_script(build_kwin_script(output_name, rect, fullscreen))
