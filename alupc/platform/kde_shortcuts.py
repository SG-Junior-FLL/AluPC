"""Systemweite Tastenkürzel unter Linux (KDE Plasma) – wie RegisterHotKey unter Windows.

Über den KDE-Dienst „kglobalaccel“ (D-Bus): AluPC meldet seine Kürzel an, KDE fängt die Tasten überall ab
(X11 und Wayland) und schickt „globalShortcutPressed“. Die Kürzel stehen dann auch in den Systemeinstellungen unter
Kurzbefehle → „AluPC“. Ohne KDE (z. B. GNOME) gibt es den Dienst nicht – dann gelten die Kürzel nur in AluPC.
"""

from __future__ import annotations

import threading

COMPONENT = "alupc"
FRIENDLY = "AluPC"
_SERVICE = "org.kde.kglobalaccel"
SET_PRESENT, NO_AUTOLOADING = 0x2, 0x4


def _key_code(sequence: str) -> int:
    from PySide6.QtGui import QKeySequence

    seq = QKeySequence(sequence, QKeySequence.PortableText)
    return seq[0].toCombined() if not seq.isEmpty() else 0


class KdeShortcuts:
    def __init__(self, on_pressed):
        self.on_pressed = on_pressed  # wird im Hintergrund-Thread aufgerufen (Qt-Signal benutzen!)
        self.conn = None
        self.registered: set[str] = set()
        self._listener: threading.Thread | None = None
        self._stop = threading.Event()

    # ---------------------------------------------------------------- Verbindung
    def _connect(self):
        if self.conn is not None:
            return self.conn
        from jeepney import DBusAddress, new_method_call
        from jeepney.io.blocking import open_dbus_connection

        conn = open_dbus_connection(bus="SESSION")
        bus = DBusAddress("/org/freedesktop/DBus", bus_name="org.freedesktop.DBus",
                          interface="org.freedesktop.DBus")
        has = conn.send_and_get_reply(new_method_call(bus, "NameHasOwner", "s", (_SERVICE,)), timeout=3).body[0]
        if not has:  # Dienst lässt sich auch per D-Bus-Aktivierung starten
            try:
                conn.send_and_get_reply(new_method_call(bus, "StartServiceByName", "su", (_SERVICE, 0)), timeout=5)
                has = conn.send_and_get_reply(new_method_call(bus, "NameHasOwner", "s", (_SERVICE,)),
                                              timeout=3).body[0]
            except Exception:  # noqa: BLE001 - kein KDE
                has = False
        if not has:
            conn.close()
            raise OSError("kein kglobalaccel")
        self.conn = conn
        return conn

    def available(self) -> bool:
        import sys

        if not sys.platform.startswith("linux"):
            return False
        try:
            self._connect()
            return True
        except Exception:  # noqa: BLE001 - kein D-Bus, kein KDE, jeepney fehlt
            return False

    def _call(self, method: str, signature: str, args: tuple):
        from jeepney import DBusAddress, new_method_call
        from jeepney.low_level import MessageType

        addr = DBusAddress("/kglobalaccel", bus_name=_SERVICE, interface="org.kde.KGlobalAccel")
        reply = self._connect().send_and_get_reply(new_method_call(addr, method, signature, args), timeout=5)
        if reply.header.message_type == MessageType.error:
            raise OSError(f"{method}: {reply.body}")
        return reply.body

    # ---------------------------------------------------------------- Kürzel
    def set(self, shortcuts: dict[str, tuple[str, str]]) -> dict[str, bool]:
        """{Aktion: (Kürzel, Anzeigename)} anmelden; Rückgabe {Aktion: klappt}. Nicht mehr genannte werden frei."""
        result: dict[str, bool] = {}
        for action in list(self.registered - set(shortcuts)):
            self._release(action)
        for action, (seq, label) in shortcuts.items():
            aid = [COMPONENT, action, FRIENDLY, label]
            key = _key_code(seq)
            try:
                self._call("doRegister", "as", (aid,))
                try:
                    got = self._call("setShortcut", "asaiu", (aid, [key], SET_PRESENT | NO_AUTOLOADING))[0]
                except OSError:  # neuere KDE-Versionen: nur noch mit Tastenfolgen
                    got = [k[0] for k in self._call("setShortcutKeys", "asa(ai)u",
                                                    (aid, [([key, 0, 0, 0],)], SET_PRESENT | NO_AUTOLOADING))[0]]
                ok = key in list(got)
            except Exception:  # noqa: BLE001
                ok = False
            if ok:
                self.registered.add(action)
            else:
                self._release(action)
            result[action] = ok
        if self.registered:
            self._listen()
        return result

    def _release(self, action: str) -> None:
        self.registered.discard(action)
        try:
            self._call("unregister", "ss", (COMPONENT, action))
        except Exception:  # noqa: BLE001
            pass

    def clear(self) -> None:
        for action in list(self.registered):
            self._release(action)

    # ---------------------------------------------------------------- Tasten empfangen
    def _listen(self) -> None:
        if self._listener is not None and self._listener.is_alive():
            return
        self._stop.clear()
        self._listener = threading.Thread(target=self._loop, name="alupc-kde-kuerzel", daemon=True)
        self._listener.start()

    def _loop(self) -> None:
        from jeepney import MatchRule, message_bus, new_method_call
        from jeepney.io.blocking import open_dbus_connection

        try:
            conn = open_dbus_connection(bus="SESSION")
            rule = MatchRule(type="signal", interface="org.kde.kglobalaccel.Component",
                             member="globalShortcutPressed", path=f"/component/{COMPONENT}")
            conn.send_and_get_reply(new_method_call(message_bus, "AddMatch", "s", (rule.serialise(),)), timeout=5)
        except Exception:  # noqa: BLE001
            return
        with conn:
            while not self._stop.is_set():
                try:
                    msg = conn.receive(timeout=1)
                except TimeoutError:
                    continue
                except Exception:  # noqa: BLE001 - Verbindung weg
                    return
                body = msg.body or ()
                if len(body) >= 2 and body[0] == COMPONENT and body[1] in self.registered:
                    self.on_pressed(body[1])

    def stop(self) -> None:
        self._stop.set()
        if self.conn is not None:
            try:
                self.conn.close()
            except Exception:  # noqa: BLE001
                pass
            self.conn = None
