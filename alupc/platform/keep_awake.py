"""Dem System sagen: Bildschirm nicht abdunkeln, nicht ausschalten, nicht sperren – solange AluPC Monitor 2
braucht (Bildschirmschoner eingeschaltet, Inhalt auf Monitor 2). So machen es auch Videoplayer.

* Linux (KDE, GNOME …): org.freedesktop.ScreenSaver.Inhibit – gilt, solange die D-Bus-Verbindung offen ist
  (stürzt AluPC ab, hebt das System die Sperre von selbst auf). Dazu PowerManagement.Inhibit gegen Ruhezustand.
* Windows: SetThreadExecutionState(ES_CONTINUOUS | ES_DISPLAY_REQUIRED | ES_SYSTEM_REQUIRED).
"""

from __future__ import annotations

import sys

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002


class KeepAwake:
    def __init__(self):
        self.active = False
        self.method = ""
        self.error = ""
        self._conn = None
        self._cookies: list[tuple[str, str, str, int]] = []

    def set(self, on: bool, reason: str = "AluPC zeigt etwas auf Monitor 2") -> bool:
        """Ein-/ausschalten (mehrfach aufrufen ist harmlos). Rückgabe: jetzt aktiv?"""
        if on == self.active:
            return self.active
        try:
            if sys.platform.startswith("win"):
                self._windows(on)
            elif sys.platform.startswith("linux"):
                self._linux(on, reason)
            else:
                return False
            self.active = on
            self.error = ""
        except Exception as exc:  # noqa: BLE001 - nie AluPC stören
            self.error = str(exc)
            if not on:
                self.active = False
        return self.active

    # ---- Windows
    def _windows(self, on: bool) -> None:
        import ctypes

        flags = ES_CONTINUOUS | (ES_DISPLAY_REQUIRED | ES_SYSTEM_REQUIRED if on else 0)
        if not ctypes.windll.kernel32.SetThreadExecutionState(flags):  # type: ignore[attr-defined]
            raise OSError("SetThreadExecutionState fehlgeschlagen")
        self.method = "Windows (Anzeige bleibt an)"

    # ---- Linux
    SERVICES = (
        ("org.freedesktop.ScreenSaver", "/org/freedesktop/ScreenSaver", "org.freedesktop.ScreenSaver"),
        ("org.freedesktop.PowerManagement", "/org/freedesktop/PowerManagement/Inhibit",
         "org.freedesktop.PowerManagement.Inhibit"),
    )

    def _linux(self, on: bool, reason: str) -> None:
        from . import dbus_util

        if on:
            if self._conn is None:
                self._conn = dbus_util.connect("SESSION")
            done = []
            for name, path, iface in self.SERVICES:
                try:
                    (cookie,) = dbus_util.call(self._conn, name, path, iface, "Inhibit", "ss", ("AluPC", reason),
                                               timeout=3)
                    self._cookies.append((name, path, iface, int(cookie)))
                    done.append(name.rsplit(".", 1)[-1])
                except Exception:  # noqa: BLE001 - nicht jeder Desktop hat beide Dienste
                    continue
            if not done:
                raise RuntimeError("Der Desktop bietet kein „Nicht abdunkeln“ an")
            self.method = " + ".join(done)
            return
        for name, path, iface, cookie in self._cookies:
            try:
                dbus_util.call(self._conn, name, path, iface, "UnInhibit", "u", (cookie,), timeout=3)
            except Exception:  # noqa: BLE001
                pass
        self._cookies = []
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:  # noqa: BLE001
                pass
            self._conn = None

    def describe(self) -> str:
        if self.active:
            return f"System dunkelt nicht ab ({self.method})"
        return f"System darf abdunkeln{f' – Fehler: {self.error}' if self.error else ''}"
