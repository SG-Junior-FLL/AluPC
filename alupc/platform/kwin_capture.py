"""Bildschirm aufnehmen unter KDE/Wayland ohne Nachfrage – über KWins D-Bus-Schnittstelle ScreenShot2.

Die normale Wayland-Aufnahme (xdg-desktop-portal) zeigt jedes Mal ein Fenster „Welchen Bildschirm
teilen?“. KWin bietet mit `org.kde.KWin.ScreenShot2` einen direkten Weg, erlaubt ihn aber nur
Programmen, deren Menüeintrag (.desktop) die Zeile
`X-KDE-DBUS-Restricted-Interfaces=org.kde.KWin.ScreenShot2` enthält und dessen `Exec=` auf genau die
laufende Programmdatei zeigt. Das .deb-Paket (und die portable Version beim ersten Start) richtet das
ein. Klappt es nicht, nimmt AluPC wie bisher die normale Aufnahme (mit Nachfrage).

Jedes Bild ist ein eigener Screenshot → etwas langsamer als eine Video-Aufnahme (typisch 10–25 Bilder/s).
"""

from __future__ import annotations

import os
import select
import threading
import time

from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage

from . import dbus_util
from .linux_display import is_wayland

BUS_NAME = "org.kde.KWin"
PATH = "/org/kde/KWin/ScreenShot2"
IFACE = "org.kde.KWin.ScreenShot2"
RESTRICTED_LINE = f"X-KDE-DBUS-Restricted-Interfaces={IFACE}"

_orphans: list = []  # beendete, aber noch nicht fertige Aufnahme-Threads
_state = {"allowed": None, "checked": 0.0, "error": ""}
_lock = threading.Lock()


def is_kde() -> bool:
    return "KDE" in os.environ.get("XDG_CURRENT_DESKTOP", "").upper()


def connect():
    if not dbus_util.HAVE_JEEPNEY:
        raise RuntimeError("Python-Paket 'jeepney' fehlt")
    from jeepney.io.blocking import open_dbus_connection

    return open_dbus_connection(bus="SESSION", enable_fds=True)


def image_from_raw(data: bytes, info: dict) -> QImage:
    """Rohdaten von KWin (Breite/Höhe/Zeilenlänge/QImage-Format) → QImage."""
    def val(key, default=0):
        v = info.get(key, default)
        return v[1] if isinstance(v, tuple) and len(v) == 2 else v

    width, height, stride = int(val("width")), int(val("height")), int(val("stride"))
    fmt = int(val("format", int(QImage.Format_ARGB32_Premultiplied.value)))
    if width <= 0 or height <= 0 or len(data) < stride * height:
        raise RuntimeError("KWin hat ein unvollständiges Bild geliefert")
    return QImage(data, width, height, stride, QImage.Format(fmt)).copy()


def capture_screen(conn, screen_name: str, cursor: bool = True) -> QImage:
    """Ein Bild des Monitors `screen_name` (Wayland-Ausgangsname, z. B. „DP-1“)."""
    from jeepney import DBusAddress, new_method_call
    from jeepney.wrappers import unwrap_msg

    read_fd, write_fd = os.pipe()
    try:
        options = {"include-cursor": ("b", bool(cursor)), "native-resolution": ("b", True)}
        msg = new_method_call(DBusAddress(PATH, bus_name=BUS_NAME, interface=IFACE),
                              "CaptureScreen", "sa{sv}h", (screen_name, options, write_fd))
        reply = conn.send_and_get_reply(msg, timeout=5)
        # KWin antwortet zuerst und schreibt danach die Bilddaten in die Leitung
        os.close(write_fd)
        write_fd = -1
        (info,) = unwrap_msg(reply)
        chunks = []
        while True:
            # nie ewig warten: liefert KWin 5 s lang nichts, abbrechen
            ready, _w, _x = select.select([read_fd], [], [], 5)
            if not ready:
                raise TimeoutError("KWin liefert keine Bilddaten")
            chunk = os.read(read_fd, 4 << 20)
            if not chunk:
                break
            chunks.append(chunk)
        return image_from_raw(b"".join(chunks), info)
    finally:
        if write_fd >= 0:
            os.close(write_fd)
        os.close(read_fd)


def allowed(screen_name: str) -> bool:
    """Darf AluPC KWin-Screenshots machen? (Ergebnis wird gemerkt; „nein“ nur 30 s lang.)"""
    if not (is_wayland() and is_kde() and dbus_util.HAVE_JEEPNEY):
        return False
    with _lock:
        if _state["allowed"] is True:
            return True
        if _state["allowed"] is False and time.monotonic() - _state["checked"] < 30:
            return False
        try:
            with connect() as conn:
                capture_screen(conn, screen_name, cursor=False)
            _state.update(allowed=True, error="")
        except Exception as exc:  # noqa: BLE001
            _state.update(allowed=False, error=str(exc))
        _state["checked"] = time.monotonic()
        return bool(_state["allowed"])


def last_error() -> str:
    return _state["error"]


def grab_once(screen_name: str) -> QImage:
    with connect() as conn:
        return capture_screen(conn, screen_name)


class KWinScreenFeed(QThread):
    """Liefert laufend Bilder eines Monitors (eigener Thread, damit die Oberfläche flüssig bleibt)."""

    frame = Signal(QImage)
    failed = Signal(str)

    def __init__(self, screen_name: str, fps: int = 20, cursor: bool = True, parent=None):
        super().__init__(parent)
        self.screen_name = screen_name
        self.interval = 1.0 / max(1, fps)
        self.cursor = cursor
        self._stop = threading.Event()
        self._busy = threading.Event()  # Oberfläche hat das letzte Bild noch nicht abgeholt

    def stop(self) -> None:
        self._stop.set()
        if not self.wait(3000):
            # Hängt KWin gerade: Thread weiterlaufen lassen, aber vom Besitzer lösen, damit er nicht
            # gelöscht wird, solange er noch läuft (das würde AluPC abstürzen lassen)
            try:
                self.frame.disconnect()
                self.failed.disconnect()
            except (RuntimeError, TypeError):
                pass
            self.setParent(None)
            _orphans.append(self)
            self.finished.connect(lambda: _orphans.remove(self) if self in _orphans else None)

    def frame_taken(self) -> None:
        self._busy.clear()

    def run(self):
        try:
            conn = connect()
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))
            return
        errors = 0
        with conn:
            while not self._stop.is_set():
                start = time.monotonic()
                if not self._busy.is_set():
                    try:
                        image = capture_screen(conn, self.screen_name, self.cursor)
                        errors = 0
                        self._busy.set()
                        self.frame.emit(image)
                    except Exception as exc:  # noqa: BLE001
                        errors += 1
                        if errors >= 5:
                            self.failed.emit(str(exc))
                            return
                rest = self.interval - (time.monotonic() - start)
                if rest > 0:
                    self._stop.wait(rest)
                else:
                    self._stop.wait(0.005)
