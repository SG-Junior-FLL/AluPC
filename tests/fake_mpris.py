"""Nachgebauter Medienplayer mit MPRIS-Schnittstelle (wie Spotify unter Linux) für Tests.

Aufruf: python fake_mpris.py <cover.png> – läuft, bis der Bus endet. Weiter/Zurück/Pause ändern den Zustand.
"""

import sys

from jeepney import HeaderFields, MessageType, new_error, new_method_return
from jeepney.bus_messages import message_bus
from jeepney.io.blocking import open_dbus_connection

SONGS = [("Blinding Lights", ["The Weeknd"], "After Hours", 200), ("Levitating", ["Dua Lipa"], "Future Nostalgia", 203)]


def main():
    cover = sys.argv[1] if len(sys.argv) > 1 else ""
    conn = open_dbus_connection(bus="SESSION")
    conn.send_and_get_reply(message_bus.RequestName("org.mpris.MediaPlayer2.spotify"))
    state = {"song": 0, "status": "Playing"}
    print("bereit", flush=True)
    while True:
        msg = conn.receive()
        if msg.header.message_type != MessageType.method_call:
            continue
        member = msg.header.fields.get(HeaderFields.member)
        iface = msg.header.fields.get(HeaderFields.interface)
        title, artist, album, length = SONGS[state["song"]]
        meta = {"xesam:title": ("s", title), "xesam:artist": ("as", artist), "xesam:album": ("s", album),
                "mpris:length": ("x", length * 1_000_000), "mpris:trackid": ("o", f"/track/{state['song']}")}
        if cover:
            meta["mpris:artUrl"] = ("s", "file://" + cover)
        player = {"PlaybackStatus": ("s", state["status"]), "Metadata": ("a{sv}", meta),
                  "Position": ("x", 42_000_000)}
        if iface == "org.freedesktop.DBus.Properties" and member == "GetAll":
            body = player if msg.body[0] == "org.mpris.MediaPlayer2.Player" else {"Identity": ("s", "Spotify")}
            conn.send(new_method_return(msg, "a{sv}", (body,)))
        elif iface == "org.freedesktop.DBus.Properties" and member == "Get":
            if msg.body[1] == "Identity":
                conn.send(new_method_return(msg, "v", (("s", "Spotify"),)))
            else:
                conn.send(new_method_return(msg, "v", (player.get(msg.body[1], ("s", "")),)))
        elif member in ("Next", "Previous"):
            state["song"] = (state["song"] + (1 if member == "Next" else -1)) % len(SONGS)
            conn.send(new_method_return(msg))
        elif member == "PlayPause":
            state["status"] = "Paused" if state["status"] == "Playing" else "Playing"
            conn.send(new_method_return(msg))
        else:
            conn.send(new_error(msg, "org.freedesktop.DBus.Error.UnknownMethod", "s", (str(member),)))


if __name__ == "__main__":
    main()
