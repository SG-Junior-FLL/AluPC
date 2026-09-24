"""Nachgebauter KWin-Dienst „ScreenShot2“ für Tests (antwortet wie KWin: erst Antwort, dann Bilddaten).

Aufruf: python fake_kwin.py [erlaubt|verboten]  – läuft, bis der Bus endet.
"""

import os
import sys
import threading

from jeepney import HeaderFields, MessageType, new_error, new_method_return
from jeepney.bus_messages import message_bus
from jeepney.io.blocking import open_dbus_connection

WIDTH, HEIGHT = 64, 32
FORMAT_ARGB32_PREMULTIPLIED = 6


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "erlaubt"
    conn = open_dbus_connection(bus="SESSION", enable_fds=True)
    conn.send_and_get_reply(message_bus.RequestName("org.kde.KWin"))
    print("bereit", flush=True)
    while True:
        msg = conn.receive()
        if msg.header.message_type != MessageType.method_call:
            continue
        if msg.header.fields.get(HeaderFields.member) != "CaptureScreen":
            continue
        name, _options, fd = msg.body
        raw = fd.to_raw_fd()
        if mode == "verboten":
            conn.send(new_error(msg, "org.kde.KWin.ScreenShot2.Error.NoAuthorized", "s", ("nicht erlaubt",)))
            os.close(raw)
            continue
        stride = WIDTH * 4
        # BGRA im Speicher = ARGB32 → rot, letzte Zeile grün (prüft Zeilenreihenfolge)
        data = bytearray(b"\x00\x00\xff\xff" * WIDTH * (HEIGHT - 1) + b"\x00\xff\x00\xff" * WIDTH)
        conn.send(new_method_return(msg, "a{sv}", ({
            "type": ("s", "raw"), "width": ("u", WIDTH), "height": ("u", HEIGHT),
            "stride": ("u", stride), "format": ("u", FORMAT_ARGB32_PREMULTIPLIED), "scale": ("d", 1.0),
            "screen": ("s", name)},)))

        def write(raw=raw, data=bytes(data)):
            with os.fdopen(raw, "wb") as f:
                f.write(data)

        threading.Thread(target=write, daemon=True).start()


if __name__ == "__main__":
    main()
