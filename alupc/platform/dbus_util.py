"""Kleine Hilfsfunktionen für D-Bus (über die reine Python-Bibliothek jeepney)."""

from __future__ import annotations

try:
    from jeepney import DBusAddress, MessageFlag, new_method_call
    from jeepney.io.blocking import open_dbus_connection
    from jeepney.wrappers import unwrap_msg

    HAVE_JEEPNEY = True
except ImportError:  # pragma: no cover - nur ohne jeepney
    HAVE_JEEPNEY = False


def call(conn, bus_name: str, path: str, interface: str, method: str,
         signature: str = "", args: tuple = (), timeout: float = 30, interactive: bool = False):
    """Methode aufrufen und den Rückgabe-Body liefern (wirft bei D-Bus-Fehlern)."""
    addr = DBusAddress(path, bus_name=bus_name, interface=interface)
    msg = new_method_call(addr, method, signature or None, args)
    if interactive:
        # Erlaubt eine Passwortabfrage (polkit), z. B. beim Anlernen eines Fingers
        msg.header.flags |= MessageFlag.allow_interactive_authorization
    return unwrap_msg(conn.send_and_get_reply(msg, timeout=timeout))


def get_property(conn, bus_name: str, path: str, interface: str, name: str, timeout: float = 10):
    body = call(conn, bus_name, path, "org.freedesktop.DBus.Properties", "Get",
                "ss", (interface, name), timeout=timeout)
    variant = body[0]
    # jeepney liefert Varianten als (Signatur, Wert)
    return variant[1] if isinstance(variant, tuple) and len(variant) == 2 else variant


def connect(bus: str = "SESSION"):
    if not HAVE_JEEPNEY:
        raise RuntimeError("Python-Paket 'jeepney' fehlt (pip install jeepney)")
    return open_dbus_connection(bus=bus)
