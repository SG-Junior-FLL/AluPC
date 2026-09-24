"""Mausposition unter KDE/Wayland über ein kleines KWin-Skript.

Unter Wayland erfahren Programme die Mausposition nur über ihren eigenen Fenstern. Für den
Laserpointer (Maus auf Monitor 1 → Punkt auf Monitor 2) meldet ein KWin-Skript jede Bewegung per
D-Bus direkt an AluPC.
"""

from __future__ import annotations

import threading

from PySide6.QtCore import QObject, QPoint, Signal

from . import dbus_util

IFACE = "de.alupc.Cursor"
OBJ_PATH = "/de/alupc/Cursor"

SCRIPT = r"""
(function () {
    var service = %(service)s;
    var last = "";
    function send() {
        var p = workspace.cursorPos;
        if (!p) { return; }
        var key = p.x + "," + p.y;
        if (key === last) { return; }
        last = key;
        callDBus(service, %(path)s, %(iface)s, "Pos", Math.round(p.x), Math.round(p.y));
    }
    if (workspace.cursorPosChanged !== undefined) {
        workspace.cursorPosChanged.connect(send);
    } else {
        var timer = new QTimer();
        timer.interval = 16;
        timer.timeout.connect(send);
        timer.start();
    }
    send();
})();
"""


def build_script(service: str) -> str:
    import json

    return SCRIPT % {"service": json.dumps(service), "path": json.dumps(OBJ_PATH), "iface": json.dumps(IFACE)}


class CursorReceiver(QObject):
    """Nimmt die Meldungen des KWin-Skripts an (eigener Thread) und gibt sie als Qt-Signal weiter."""

    moved = Signal(QPoint)
    failed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._stop = threading.Event()
        self._thread = None
        self.conn = None
        self.plugin = ""

    @property
    def service(self) -> str:
        return self.conn.unique_name if self.conn else ""

    def start(self, load_script: bool = True) -> None:
        self.conn = dbus_util.connect("SESSION")
        self._thread = threading.Thread(target=self._loop, name="alupc-kwin-cursor", daemon=True)
        self._thread.start()
        if load_script:
            from .linux_windows import start_kwin_script

            self.plugin = start_kwin_script(build_script(self.service))

    def stop(self) -> None:
        self._stop.set()
        if self.plugin:
            from .linux_windows import stop_kwin_script

            stop_kwin_script(self.plugin)
            self.plugin = ""
        if self._thread is not None:
            self._thread.join(2)
        if self.conn is not None:
            try:
                self.conn.close()
            except Exception:  # noqa: BLE001
                pass
            self.conn = None

    def _loop(self):
        from jeepney import HeaderFields, MessageType, new_method_return

        conn = self.conn
        while not self._stop.is_set():
            try:
                msg = conn.receive(timeout=0.3)
            except TimeoutError:
                continue
            except Exception as exc:  # noqa: BLE001
                if not self._stop.is_set():
                    self.failed.emit(str(exc))
                return
            hdr = msg.header
            if hdr.message_type != MessageType.method_call:
                continue
            if hdr.fields.get(HeaderFields.member) == "Pos" and len(msg.body) >= 2:
                try:
                    x, y = (v[1] if isinstance(v, tuple) else v for v in msg.body[:2])  # evtl. als Variant
                    self.moved.emit(QPoint(int(x), int(y)))
                except (TypeError, ValueError):
                    pass
            try:
                conn.send(new_method_return(msg))
            except Exception:  # noqa: BLE001
                pass
