"""Finger als Schnelltaste: Ein angelernter Finger auf dem Modul (z. B. HLK-ZW101) löst einen Befehl aus –
z. B. rechter Zeigefinger = Schwarz, linker Daumen = nächste Szene.

Läuft nur, solange der Computer entsperrt ist: Beim Sperrbildschirm braucht die Anmeldung das Modul
(Windows lässt nur ein Programm an den COM-Anschluss). AluPC öffnet den Anschluss nur kurz pro Abfrage und
nie, während die Fingerabdruck-Seite gerade anlernt oder testet. Ein Befehl kommt erst, wenn der Finger
neu aufgelegt wird (liegt er noch vom Entsperren drauf, passiert nichts).
"""

from __future__ import annotations

import json
import sys
import threading
import time

from PySide6.QtCore import QObject, Signal

POLL = 0.35  # Sekunden zwischen zwei Abfragen


def shortcut_map(config) -> dict[int, str]:
    raw = (config["finger_shortcuts"].get("map") or {})
    return {int(k): str(v) for k, v in raw.items() if str(k).isdigit() and v}


def own_fingers() -> list[tuple[int, str, str]]:
    """Angelernte Finger im eigenen Konto: (Platz, Person, Finger-Bezeichnung)."""
    from .platform.base import FINGERS
    from .platform.zw_fingerprint import current_user, load_slots

    labels = dict(FINGERS)
    user = current_user()
    out = []
    for key, info in load_slots().items():
        if str(key).isdigit() and info.get("user") == user:
            out.append((int(key), info.get("person") or user, labels.get(info.get("finger", ""), info.get("finger", ""))))
    return sorted(out, key=lambda t: (t[1].lower(), t[0]))


# --------------------------------------------------------------------------- Computer gesperrt?
def session_locked() -> bool:
    if sys.platform.startswith("win"):
        try:
            import ctypes

            u = ctypes.windll.user32
            desk = u.OpenInputDesktop(0, False, 0x0100)  # DESKTOP_SWITCHDESKTOP
            if not desk:
                return True  # Sperrbildschirm (Winlogon-Desktop) → kein Zugriff
            try:
                return not u.SwitchDesktop(desk)
            finally:
                u.CloseDesktop(desk)
        except Exception:  # noqa: BLE001
            return False
    try:
        from .platform import dbus_util

        with dbus_util.connect("SESSION") as conn:
            (active,) = dbus_util.call(conn, "org.freedesktop.ScreenSaver", "/ScreenSaver",
                                       "org.freedesktop.ScreenSaver", "GetActive", timeout=2)
        return bool(active)
    except Exception:  # noqa: BLE001
        return False


def _port_and_baud() -> tuple[str, int]:
    from .platform import zw_fingerprint as zw

    try:
        cached = json.loads(zw._cache_file().read_text(encoding="utf-8"))
        return cached.get("port", ""), int(cached.get("baud", 57600))
    except Exception:  # noqa: BLE001
        ports = zw.candidate_ports()
        return (ports[0] if ports else ""), 57600


class FingerShortcuts(QObject):
    """Wacht im Hintergrund; `triggered(Befehl)` kommt im GUI-Thread an (Qt-Signal über Threads)."""

    triggered = Signal(str)

    def __init__(self, config, parent=None, locked=session_locked, port=_port_and_baud, poll: float = POLL):
        super().__init__(parent)
        self.config = config
        self.locked, self.port, self.poll = locked, port, poll
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self.last_error = ""
        self.last_slot: int | None = None  # für Anzeige/Tests
        self._capacity: dict[str, int] = {}

    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def apply(self) -> None:
        """Nach Änderungen der Einstellung: starten oder stoppen."""
        wanted = bool(self.config["finger_shortcuts"].get("on")) and bool(shortcut_map(self.config))
        from .platform.zw_fingerprint import HAVE_SERIAL

        wanted = wanted and HAVE_SERIAL
        if wanted and not self.running():
            self._stop.clear()
            self._thread = threading.Thread(target=self._run, name="finger-schnelltasten", daemon=True)
            self._thread.start()
        elif not wanted and self.running():
            self.stop()

    def stop(self) -> None:
        self._stop.set()
        thread, self._thread = self._thread, None
        if thread is not None:
            thread.join(timeout=3)

    # ------------------------------------------------------------ Hintergrund
    def _run(self) -> None:
        from .platform import zw_fingerprint as zw

        armed = False  # erst auslösen, nachdem einmal „kein Finger“ gemeldet wurde
        was_locked = False
        while not self._stop.is_set():
            if self.locked():
                was_locked, armed = True, False
                self._stop.wait(1.0)
                continue
            if was_locked:  # gerade entsperrt: der Finger liegt evtl. noch vom Entsperren drauf
                was_locked = False
                self._stop.wait(2.0)
                continue
            port, baud = self.port()
            if not port:
                self._stop.wait(5.0)
                continue
            lock = zw._port_lock(port)
            if not lock.acquire(blocking=False):  # Fingerabdruck-Seite lernt gerade an o. Ä.
                armed = False
                self._stop.wait(0.5)
                continue
            try:
                armed = self._poll_once(zw, port, baud, armed)
                self.last_error = ""
            except Exception as exc:  # noqa: BLE001 - Modul abgesteckt, Anschluss belegt …
                self.last_error = str(exc)
                armed = False
                self._stop.wait(3.0)
            finally:
                lock.release()
            self._stop.wait(self.poll)

    def _poll_once(self, zw, port: str, baud: int, armed: bool) -> bool:
        with zw.ZWSensor(port, baud, timeout=0.5) as s:
            if not s.handshake():
                raise zw.SensorError("Modul antwortet nicht")
            if s.get_image() != zw.OK:
                return True  # kein Finger → ab jetzt scharf
            if not armed:
                return False  # Finger lag schon drauf
            try:
                if port not in self._capacity:
                    self._capacity[port] = s.sys_params()["capacity"]
                hit = s.identify(self._capacity[port])  # unscharfes erstes Bild → gleich nochmal
            except zw.SensorError:
                hit = None
            if hit is not None:
                self.last_slot = hit[0]
                command = shortcut_map(self.config).get(hit[0])
                if command:
                    self.triggered.emit(command)
            # warten, bis der Finger weg ist (höchstens 4 s) – sonst löst er mehrfach aus
            end = time.monotonic() + 4
            while time.monotonic() < end and not self._stop.is_set():
                if s.get_image() != zw.OK:
                    return True
                time.sleep(0.1)
            return False
