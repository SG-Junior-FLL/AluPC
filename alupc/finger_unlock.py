"""Linux: Sperrbildschirm mit dem Finger entsperren – ohne vorher Enter zu drücken (wie unter Windows).

Der KDE-Sperrbildschirm fragt PAM (und damit `alupc --fingerabdruck-pam`) erst, wenn man Enter drückt.
Plasma 5 kennt keinen Weg, der ohne Eingabe startet. Deshalb wacht AluPC selbst, solange der Bildschirm
gesperrt ist: Liegt ein Finger auf dem Modul, der zu DIESEM Benutzer gehört (dieselben Plätze, die auch
PAM erlaubt), bittet AluPC logind, die eigene Sitzung zu entsperren (`loginctl unlock-session`).

Sicherheit: Das darf jedes Programm des angemeldeten Benutzers ohnehin (die eigene Sitzung entsperren) –
AluPC bekommt dadurch keine neuen Rechte. Der Wächter läuft nur, wenn „Anmelden mit Fingerabdruck“ für
diesen Benutzer eingeschaltet ist. Die Anmeldung nach dem Einschalten des PCs (Anmeldebildschirm) geht so
nicht – dort läuft AluPC noch nicht.

Damit sich AluPC und die PAM-Prüfung (z. B. Enter am Sperrbildschirm, sudo) nicht ins Gehege kommen, öffnen
beide den Anschluss exklusiv (siehe ZWSensor.open) und warten kurz aufeinander.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading

from PySide6.QtCore import QObject, Signal

from .finger_shortcuts import _port_and_baud, session_locked

POLL = 0.3


def login_slots(user: str | None = None) -> set[int]:
    """Plätze, mit denen sich dieser Benutzer anmelden darf (wie bei der PAM-Prüfung) – leer = aus."""
    from .platform.linux_serial_login import read_login
    from .platform.zw_fingerprint import current_user, user_slots_from_home

    user = user or current_user()
    allowed = read_login().get("users", {}).get(user)
    if not allowed:
        return set()  # Anmelden mit Fingerabdruck ist für diesen Benutzer aus
    own = user_slots_from_home(user)
    return set(own) if own is not None else {int(s) for s in allowed}


def unlock_session() -> bool:
    """Eigene Sitzung entsperren (logind). KDE (Plasma 5 und 6) reagiert darauf und schließt den Sperrbildschirm."""
    loginctl = shutil.which("loginctl")
    if not loginctl:
        return False
    cmd = [loginctl, "unlock-session"]
    sid = os.environ.get("XDG_SESSION_ID", "")
    if sid.isalnum():
        cmd.append(sid)
    try:
        return subprocess.run(cmd, capture_output=True, timeout=10).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


class FingerUnlock(QObject):
    """Wacht im Hintergrund, solange der Bildschirm gesperrt ist. `unlocked(Platz)` kommt im GUI-Thread an."""

    unlocked = Signal(int)

    def __init__(self, config, parent=None, locked=session_locked, port=_port_and_baud, unlock=unlock_session,
                 slots=login_slots, poll: float = POLL):
        super().__init__(parent)
        self.config = config
        self.locked, self.port, self.unlock, self.slots, self.poll = locked, port, unlock, slots, poll
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self.last_error = ""
        self.last_slot: int | None = None

    @staticmethod
    def supported() -> bool:
        from .platform.zw_fingerprint import HAVE_SERIAL

        return sys.platform.startswith("linux") and HAVE_SERIAL

    def wanted(self) -> bool:
        return self.supported() and bool(self.config["fingerprint"].get("auto_unlock", True))

    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def apply(self) -> None:
        if self.wanted() and not self.running():
            self._stop.clear()
            self._thread = threading.Thread(target=self._run, name="finger-entsperren", daemon=True)
            self._thread.start()
        elif not self.wanted() and self.running():
            self.stop()

    def stop(self) -> None:
        self._stop.set()
        thread, self._thread = self._thread, None
        if thread is not None:
            thread.join(timeout=3)

    # ------------------------------------------------------------ Hintergrund
    def _run(self) -> None:
        from .platform import zw_fingerprint as zw

        armed = False  # erst nach „kein Finger“ prüfen (lag der Finger beim Sperren schon drauf → nichts tun)
        while not self._stop.is_set():
            if not self.locked():
                armed = False
                self._stop.wait(1.0)
                continue
            allowed = self.slots()
            if not allowed:  # Anmelden mit Fingerabdruck aus → nichts tun
                self._stop.wait(5.0)
                continue
            port, baud = self.port()
            if not port:
                self._stop.wait(5.0)
                continue
            lock = zw._port_lock(port)
            if not lock.acquire(blocking=False):
                armed = False
                self._stop.wait(0.5)
                continue
            try:
                armed = self._poll_once(zw, port, baud, armed, allowed)
                self.last_error = ""
            except Exception as exc:  # noqa: BLE001 – Modul abgesteckt, Anschluss gerade von PAM belegt …
                self.last_error = str(exc)
                armed = False
                self._stop.wait(2.0)
            finally:
                lock.release()
            self._stop.wait(self.poll)

    def _poll_once(self, zw, port: str, baud: int, armed: bool, allowed: set[int]) -> bool:
        with zw.ZWSensor(port, baud, timeout=0.5) as s:
            if not s.handshake():
                raise zw.SensorError("Modul antwortet nicht")
            if s.get_image() != zw.OK:
                return True  # kein Finger → ab jetzt scharf
            if not armed:
                return False
            try:
                s.gen_char(1)
                hit = s.search(1, s.sys_params()["capacity"])
            except zw.SensorError:
                hit = None
            if hit is not None and hit[0] in allowed and self.locked():
                self.last_slot = hit[0]
                try:
                    from .welcome import record_login
                    from .platform.zw_fingerprint import current_user

                    record_login(current_user(), hit[0])  # für „Willkommen, Lena!“
                except Exception:  # noqa: BLE001
                    pass
                if self.unlock():
                    self.unlocked.emit(hit[0])
            # erst wieder prüfen, wenn der Finger einmal weg war – den Anschluss aber gleich wieder freigeben
            # (drückt jemand Enter, wartet die PAM-Prüfung sonst unnötig)
            return False
