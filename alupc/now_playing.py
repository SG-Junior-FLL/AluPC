"""„Läuft gerade“: was der PC gerade abspielt – Spotify, Browser (YouTube …), VLC, Musik-Apps.

* Linux: MPRIS über D-Bus (jeder Player, der im Plasma-Medienwidget erscheint, meldet sich dort).
* Windows: „Globale Mediensteuerung“ (dieselbe Quelle wie das Medien-Popup bei den Lautstärketasten).

Ohne Qt, im Hintergrund-Thread aufrufbar: `reader()` liefert ein Objekt mit `read()` → `Track | None` und
`control("play_pause" | "next" | "previous")`. Das Cover kommt als Bytes (PNG/JPEG).
"""

from __future__ import annotations

import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

IS_WINDOWS = sys.platform.startswith("win")
ACTIONS = ("play_pause", "next", "previous")


@dataclass
class Track:
    title: str = ""
    artist: str = ""
    album: str = ""
    player: str = ""
    playing: bool = False
    position: float = 0.0  # Sekunden, Stand `stamp`
    length: float = 0.0  # Sekunden (0 = unbekannt, z. B. Livestream)
    art: bytes = b""
    art_key: str = ""  # ändert sich, wenn ein anderes Cover kommt
    stamp: float = field(default_factory=time.monotonic)

    def position_now(self) -> float:
        pos = self.position + (time.monotonic() - self.stamp if self.playing else 0.0)
        return min(pos, self.length) if self.length > 0 else max(0.0, pos)

    def same_song(self, other: Track | None) -> bool:
        return other is not None and (self.title, self.artist, self.player) == (other.title, other.artist,
                                                                                other.player)


def fmt_time(seconds: float) -> str:
    seconds = max(0, int(seconds))
    h, rest = divmod(seconds, 3600)
    m, s = divmod(rest, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def player_name(raw: str) -> str:
    """„org.mpris.MediaPlayer2.spotify“, „Spotify.exe“, „SpotifyAB.SpotifyMusic_zpdnekdrzrea0!Spotify“,
    „org.mpris.MediaPlayer2.firefox.instance_1_23“ → „Spotify“ / „Firefox“."""
    name = raw or ""
    if name.startswith("org.mpris.MediaPlayer2."):
        name = name[len("org.mpris.MediaPlayer2."):].split(".instance")[0].split(".")[0]
    name = name.split("!")[-1]
    if name.lower().endswith(".exe"):
        name = name[:-4]
    name = name.split("\\")[-1]
    known = {"msedge": "Edge", "chrome": "Chrome", "chromium": "Chromium", "firefox": "Firefox",
             "spotify": "Spotify", "vlc": "VLC", "brave": "Brave", "opera": "Opera", "elisa": "Elisa",
             "microsoft.zunemusic": "Media Player", "microsoft.media.player": "Media Player",
             "plasma-browser-integration": "Browser", "kdeconnect": "KDE Connect"}
    low = name.lower()
    for key, label in known.items():
        if low.startswith(key):
            return label
    return name[:1].upper() + name[1:] if name else ""


# --------------------------------------------------------------------------- Cover laden (mit kleinem Speicher)
_ART_CACHE: dict[str, bytes] = {}


def load_art(url: str) -> bytes:
    """Cover von „file://…“ oder „https://…“ (Spotify liefert eine Web-Adresse) – gemerkt, nicht jede Sekunde neu."""
    if not url:
        return b""
    if url in _ART_CACHE:
        return _ART_CACHE[url]
    data = b""
    try:
        if url.startswith("file://"):
            with open(urllib.parse.unquote(urllib.parse.urlparse(url).path), "rb") as f:
                data = f.read(8_000_000)
        elif url.startswith(("https://", "http://")):
            with urllib.request.urlopen(url, timeout=5) as resp:  # noqa: S310 - Adresse vom Player
                data = resp.read(8_000_000)
    except (OSError, ValueError):
        data = b""
    if len(_ART_CACHE) > 12:
        _ART_CACHE.clear()
    _ART_CACHE[url] = data
    return data


# --------------------------------------------------------------------------- Linux: MPRIS
MPRIS_PREFIX = "org.mpris.MediaPlayer2."
MPRIS_PATH = "/org/mpris/MediaPlayer2"
PLAYER_IFACE = "org.mpris.MediaPlayer2.Player"


def _unvariant(value):
    return value[1] if isinstance(value, tuple) and len(value) == 2 and isinstance(value[0], str) else value


def track_from_mpris(bus_name: str, props: dict, identity: str = "") -> Track | None:
    """Eigenschaften von org.mpris.MediaPlayer2.Player (GetAll) → Track."""
    props = {k: _unvariant(v) for k, v in (props or {}).items()}
    meta = {k: _unvariant(v) for k, v in (props.get("Metadata") or {}).items()}
    title = str(meta.get("xesam:title") or "").strip()
    if not title:
        url = str(meta.get("xesam:url") or "")
        title = urllib.parse.unquote(url.rsplit("/", 1)[-1]) if url else ""
    if not title:
        return None
    artist = meta.get("xesam:artist") or []
    if isinstance(artist, str):
        artist = [artist]
    length = meta.get("mpris:length") or 0
    try:
        length_s = max(0.0, float(length) / 1_000_000)
    except (TypeError, ValueError):
        length_s = 0.0
    try:
        position = max(0.0, float(props.get("Position") or 0) / 1_000_000)
    except (TypeError, ValueError):
        position = 0.0
    return Track(title=title, artist=", ".join(str(a) for a in artist if a), album=str(meta.get("xesam:album") or ""),
                 player=identity or player_name(bus_name), playing=props.get("PlaybackStatus") == "Playing",
                 position=position, length=length_s, art_key=str(meta.get("mpris:artUrl") or ""))


class MprisReader:
    def __init__(self):
        self.conn = None
        self.current = ""  # D-Bus-Name des gezeigten Players (für Weiter/Pause)
        self._last_playing = ""

    def _connection(self):
        from .platform import dbus_util

        if self.conn is None:
            self.conn = dbus_util.connect("SESSION")
        return self.conn

    def _call(self, *args, **kw):
        from .platform import dbus_util

        try:
            return dbus_util.call(self._connection(), *args, **kw)
        except (ConnectionError, OSError):
            self.close()
            raise

    def players(self) -> list[str]:
        (names,) = self._call("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus",
                              "ListNames", timeout=3)
        return sorted(n for n in names if n.startswith(MPRIS_PREFIX))

    def read(self) -> Track | None:
        found: list[tuple[str, Track]] = []
        for name in self.players():
            try:
                (props,) = self._call(name, MPRIS_PATH, "org.freedesktop.DBus.Properties", "GetAll", "s",
                                      (PLAYER_IFACE,), timeout=2)
            except Exception:  # noqa: BLE001 - ein hängender Player darf die anderen nicht stören
                continue
            identity = ""
            try:
                (ident,) = self._call(name, MPRIS_PATH, "org.freedesktop.DBus.Properties", "Get", "ss",
                                      ("org.mpris.MediaPlayer2", "Identity"), timeout=2)
                identity = str(_unvariant(ident) or "")
            except Exception:  # noqa: BLE001
                pass
            track = track_from_mpris(name, props, player_name(identity) if identity else "")
            if track is not None:
                found.append((name, track))
        if not found:
            self.current = ""
            return None
        # Was gerade spielt, zuerst – sonst der zuletzt spielende (pausiert) – sonst irgendeiner
        playing = [f for f in found if f[1].playing]
        pick = next((f for f in playing if f[0] == self._last_playing), None) or (playing[0] if playing else None)
        pick = pick or next((f for f in found if f[0] == self._last_playing), None) or found[0]
        self.current = pick[0]
        if pick[1].playing:
            self._last_playing = pick[0]
        pick[1].art = load_art(pick[1].art_key)
        return pick[1]

    def control(self, action: str) -> bool:
        if action not in ACTIONS:
            return False
        if not self.current:
            self.read()
        if not self.current:
            return False
        method = {"play_pause": "PlayPause", "next": "Next", "previous": "Previous"}[action]
        self._call(self.current, MPRIS_PATH, PLAYER_IFACE, method, timeout=3)
        return True

    def close(self):
        if self.conn is not None:
            try:
                self.conn.close()
            except Exception:  # noqa: BLE001
                pass
        self.conn = None


# --------------------------------------------------------------------------- Windows: globale Mediensteuerung
class WindowsReader:
    """Über WinRT (Paket „winrt-Windows.Media.Control“)."""

    def __init__(self):
        import asyncio

        self.loop = asyncio.new_event_loop()
        self.manager = None
        self._art_for = ""
        self._art = b""

    def _run(self, coro):
        return self.loop.run_until_complete(coro)

    async def _session(self):
        from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionManager as Manager

        if self.manager is None:
            self.manager = await Manager.request_async()
        return self.manager.get_current_session()

    def read(self) -> Track | None:
        return self._run(self._read())

    async def _read(self) -> Track | None:
        session = await self._session()
        if session is None:
            return None
        props = await session.try_get_media_properties_async()
        title = (props.title or "").strip() if props else ""
        if not title:
            return None
        info = session.get_playback_info()
        playing = int(info.playback_status) == 4 if info is not None else False  # 4 = Playing
        position = length = 0.0
        try:
            tl = session.get_timeline_properties()
            position = _seconds(tl.position) - _seconds(tl.start_time)
            length = max(0.0, _seconds(tl.end_time) - _seconds(tl.start_time))
            if playing:  # Stand von „last_updated_time“ bis jetzt weiterrechnen
                import datetime

                updated = tl.last_updated_time
                if isinstance(updated, datetime.datetime) and updated.year > 2000:
                    now = datetime.datetime.now(updated.tzinfo or datetime.timezone.utc)
                    position += max(0.0, (now - updated).total_seconds())
        except Exception:  # noqa: BLE001 - manche Apps melden keine Zeitleiste
            pass
        track = Track(title=title, artist=props.artist or props.album_artist or "", album=props.album_title or "",
                      player=player_name(session.source_app_user_model_id or ""), playing=playing,
                      position=max(0.0, position), length=length)
        key = f"{track.player}|{track.title}|{track.artist}"
        if key != self._art_for:
            self._art_for, self._art = key, await _thumbnail(props)
        track.art, track.art_key = self._art, key if self._art else ""
        return track

    def control(self, action: str) -> bool:
        if action not in ACTIONS:
            return False
        return bool(self._run(self._control(action)))

    async def _control(self, action: str):
        session = await self._session()
        if session is None:
            return False
        call = {"play_pause": session.try_toggle_play_pause_async, "next": session.try_skip_next_async,
                "previous": session.try_skip_previous_async}[action]
        return await call()

    def close(self):
        try:
            self.loop.close()
        except Exception:  # noqa: BLE001
            pass


def _seconds(value) -> float:
    if value is None:
        return 0.0
    if hasattr(value, "total_seconds"):
        return float(value.total_seconds())
    if hasattr(value, "duration"):  # ältere WinRT-Bindungen: TimeSpan in 100-ns-Schritten
        return float(value.duration) / 10_000_000
    return float(value) / 10_000_000


async def _thumbnail(props) -> bytes:
    ref = getattr(props, "thumbnail", None)
    if ref is None:
        return b""
    try:
        from winrt.windows.storage.streams import Buffer, DataReader, InputStreamOptions

        stream = await ref.open_read_async()
        size = int(stream.size)
        if size <= 0 or size > 8_000_000:
            return b""
        buf = Buffer(size)
        await stream.read_async(buf, size, InputStreamOptions.READ_AHEAD)
        try:
            return bytes(memoryview(buf)[: buf.length])
        except TypeError:
            reader = DataReader.from_buffer(buf)
            data = bytearray(buf.length)
            reader.read_bytes(data)
            return bytes(data)
    except Exception:  # noqa: BLE001 - ohne Cover geht es auch
        return b""


# --------------------------------------------------------------------------- Auswahl
def available() -> tuple[bool, str]:
    """Geht „Läuft gerade“ auf diesem System? (ja/nein, Grund)"""
    if IS_WINDOWS:
        try:
            import winrt.windows.media.control  # noqa: F401
        except ImportError:
            return False, "Windows-Baustein fehlt (winrt-Windows.Media.Control)"
        return True, ""
    from .platform import dbus_util

    if not dbus_util.HAVE_JEEPNEY:
        return False, "Python-Paket jeepney fehlt"
    return True, ""


def reader():
    return WindowsReader() if IS_WINDOWS else MprisReader()
