"""RGB-Beleuchtung über OpenRGB (Windows und Linux).

OpenRGB (freies Programm, openrgb.org) kennt Hunderte Mainboards, RAM, Grafikkarten, Lüfter, Tastaturen …
und bietet einen „SDK-Server“ (TCP, Anschluss 6742). AluPC spricht dieses Protokoll selbst (nach der
offiziellen Beschreibung „OpenRGBSDK.md“, Protokoll-Version bis 4) – AluPC bringt also keinen fremden
Code mit, braucht aber ein laufendes OpenRGB mit eingeschaltetem SDK-Server.
"""

from __future__ import annotations

import shutil
import socket
import struct
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

MAGIC = b"ORGB"
CLIENT_PROTOCOL = 4  # höchste Version, deren Format AluPC kennt
REQUEST_CONTROLLER_COUNT = 0
REQUEST_CONTROLLER_DATA = 1
REQUEST_PROTOCOL_VERSION = 40
SET_CLIENT_NAME = 50
DEVICE_LIST_UPDATED = 100
UPDATE_LEDS = 1050
SET_CUSTOM_MODE = 1100

DEVICE_TYPES = {0: "Mainboard", 1: "Arbeitsspeicher", 2: "Grafikkarte", 3: "Kühler", 4: "LED-Streifen",
                5: "Tastatur", 6: "Maus", 7: "Mauspad", 8: "Headset", 9: "Headset-Ständer", 10: "Gamepad",
                11: "Licht", 12: "Lautsprecher", 13: "Virtuell", 14: "Speicher", 15: "Gehäuse",
                16: "Mikrofon", 17: "Zubehör", 18: "Tastenfeld"}


class RGBError(Exception):
    pass


@dataclass
class Device:
    index: int
    name: str
    type: int
    vendor: str = ""
    num_leds: int = 0
    zones: list[tuple[str, int]] = field(default_factory=list)
    modes: list[str] = field(default_factory=list)

    @property
    def kind(self) -> str:
        return DEVICE_TYPES.get(self.type, "Gerät")


# --------------------------------------------------------------------------- Pakete
def header(dev: int, pkt_id: int, size: int) -> bytes:
    return MAGIC + struct.pack("<III", dev, pkt_id, size)


def color_bytes(rgb: tuple[int, int, int]) -> bytes:
    r, g, b = (max(0, min(255, int(c))) for c in rgb)
    return bytes((r, g, b, 0))  # RGBColor: 0x00BBGGRR (little endian)


def update_leds_packet(dev: int, colors: list[tuple[int, int, int]]) -> bytes:
    body = struct.pack("<H", len(colors)) + b"".join(color_bytes(c) for c in colors)
    data = struct.pack("<I", 4 + len(body)) + body
    return header(dev, UPDATE_LEDS, len(data)) + data


class _Reader:
    def __init__(self, data: bytes):
        self.data, self.pos = data, 0

    def take(self, n: int) -> bytes:
        if self.pos + n > len(self.data):
            raise RGBError("Gerätedaten unvollständig")
        chunk = self.data[self.pos:self.pos + n]
        self.pos += n
        return chunk

    def u16(self) -> int:
        return struct.unpack("<H", self.take(2))[0]

    def u32(self) -> int:
        return struct.unpack("<I", self.take(4))[0]

    def i32(self) -> int:
        return struct.unpack("<i", self.take(4))[0]

    def string(self) -> str:
        return self.take(self.u16()).rstrip(b"\0").decode("utf-8", "replace")


def parse_device(index: int, data: bytes, version: int) -> Device:
    """Antwort auf REQUEST_CONTROLLER_DATA (Format laut OpenRGBSDK.md, Version 0–4)."""
    r = _Reader(data)
    r.u32()  # data_size
    dev = Device(index=index, name="", type=r.i32())
    dev.name = r.string()
    if version >= 1:
        dev.vendor = r.string()
    for _ in range(4):  # description, version, serial, location
        r.string()
    num_modes = r.u16()
    r.i32()  # active_mode
    for _ in range(num_modes):
        dev.modes.append(r.string())
        r.take(4 * (5 if version < 3 else 7))  # value, flags, speed_min/max, (brightness_min/max), colors_min
        r.take(4 * (4 if version < 3 else 5))  # colors_max, speed, (brightness), direction, color_mode
        r.take(4 * r.u16())  # Farben des Modus
    for _ in range(r.u16()):  # Zonen
        name = r.string()
        r.i32()  # type
        r.u32()  # leds_min
        r.u32()  # leds_max
        count = r.u32()
        r.take(r.u16())  # Matrix (Höhe, Breite, Daten) – brauchen wir nicht
        if version >= 4:
            for _ in range(r.u16()):  # Segmente
                r.string()
                r.take(12)
        dev.zones.append((name, count))
    num_leds = r.u16()
    for _ in range(num_leds):
        r.string()
        r.u32()  # led_value
    dev.num_leds = r.u16()  # Anzahl Farben = Anzahl LEDs
    return dev


# --------------------------------------------------------------------------- Verbindung
class OpenRGB:
    def __init__(self, host: str = "127.0.0.1", port: int = 6742, timeout: float = 2.0):
        self.host, self.port, self.timeout = host, port, timeout
        self.sock: socket.socket | None = None
        self.version = 0
        self.devices: list[Device] = []
        self._custom: set[int] = set()
        self.list_changed = False

    # ---- Grundlagen
    def connect(self) -> list[Device]:
        try:
            self.sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        except OSError as exc:
            raise RGBError("OpenRGB antwortet nicht – läuft OpenRGB mit eingeschaltetem SDK-Server?") from exc
        self.sock.settimeout(self.timeout)
        self._send(header(0, REQUEST_PROTOCOL_VERSION, 4) + struct.pack("<I", CLIENT_PROTOCOL))
        try:
            server = struct.unpack("<I", self._recv(REQUEST_PROTOCOL_VERSION, timeout=1.0))[0]
        except (RGBError, struct.error):
            server = 0  # ganz alte Server antworten nicht
        self.version = min(CLIENT_PROTOCOL, server)
        name = b"AluPC\0"
        self._send(header(0, SET_CLIENT_NAME, len(name)) + name)
        return self.refresh()

    def refresh(self) -> list[Device]:
        self._send(header(0, REQUEST_CONTROLLER_COUNT, 0))
        count = struct.unpack("<I", self._recv(REQUEST_CONTROLLER_COUNT)[:4])[0]
        devices = []
        for i in range(count):
            body = struct.pack("<I", self.version) if self.version >= 1 else b""
            self._send(header(i, REQUEST_CONTROLLER_DATA, len(body)) + body)
            devices.append(parse_device(i, self._recv(REQUEST_CONTROLLER_DATA), self.version))
        self.devices = devices
        self._custom.clear()
        self.list_changed = False
        return devices

    def close(self) -> None:
        if self.sock is not None:
            try:
                self.sock.close()
            except OSError:
                pass
        self.sock = None

    def _send(self, data: bytes) -> None:
        if self.sock is None:
            raise RGBError("Nicht verbunden")
        try:
            self.sock.sendall(data)
        except OSError as exc:
            self.close()
            raise RGBError("Verbindung zu OpenRGB verloren") from exc

    def _read_exact(self, n: int) -> bytes:
        buf = b""
        while len(buf) < n:
            chunk = self.sock.recv(n - len(buf))
            if not chunk:
                raise RGBError("Verbindung zu OpenRGB verloren")
            buf += chunk
        return buf

    def _recv(self, expected: int, timeout: float | None = None) -> bytes:
        """Auf die Antwort mit dieser Paket-ID warten (andere Meldungen des Servers überspringen)."""
        if self.sock is None:
            raise RGBError("Nicht verbunden")
        self.sock.settimeout(timeout or self.timeout)
        try:
            while True:
                head = self._read_exact(16)
                if head[:4] != MAGIC:
                    raise RGBError("Unerwartete Antwort – ist das wirklich OpenRGB?")
                _dev, pkt_id, size = struct.unpack("<III", head[4:])
                if size > 16 * 1024 * 1024:
                    raise RGBError("Antwort zu groß")
                body = self._read_exact(size) if size else b""
                if pkt_id == expected:
                    return body
                if pkt_id == DEVICE_LIST_UPDATED:
                    self.list_changed = True
        except socket.timeout as exc:
            raise RGBError("OpenRGB antwortet nicht rechtzeitig") from exc
        finally:
            if self.sock is not None:
                self.sock.settimeout(self.timeout)

    # ---- Farben
    def set_color(self, rgb: tuple[int, int, int], devices: list[int] | None = None) -> None:
        for dev in self.devices:
            if devices is not None and dev.index not in devices or dev.num_leds == 0:
                continue
            if dev.index not in self._custom:  # einmal auf „Direkt“ schalten, sonst übernimmt das Gerät nichts
                self._send(header(dev.index, SET_CUSTOM_MODE, 0))
                self._custom.add(dev.index)
            self._send(update_leds_packet(dev.index, [rgb] * dev.num_leds))


def hex_to_rgb(color: str, brightness: int = 100) -> tuple[int, int, int]:
    c = color.lstrip("#")
    if len(c) != 6:
        c = "ffffff"
    f = max(0, min(100, brightness)) / 100
    return tuple(round(int(c[i:i + 2], 16) * f) for i in (0, 2, 4))


def vivid(rgb: tuple[float, float, float]) -> tuple[int, int, int]:
    """Mittelwert eines Bildes → kräftigere Farbe (graue Mischfarben wirken auf LEDs sonst weiß)."""
    r, g, b = rgb
    top, low = max(r, g, b), min(r, g, b)
    if top < 8:
        return (0, 0, 0)
    boost = 255 / top
    sat = 1.6
    mean = (r + g + b) / 3
    out = [max(0.0, min(255.0, (mean + (c - mean) * sat) * boost)) for c in (r, g, b)]
    if top - low < 12:  # fast grau → einfach weiß/grau in der Helligkeit
        out = [top] * 3
    return tuple(int(v) for v in out)


# --------------------------------------------------------------------------- OpenRGB finden/starten
WINDOWS_PATHS = [r"C:\Program Files\OpenRGB\OpenRGB.exe", r"C:\Program Files (x86)\OpenRGB\OpenRGB.exe"]


def find_openrgb(configured: str = "") -> str | None:
    if configured and Path(configured).is_file():
        return configured
    found = shutil.which("openrgb") or shutil.which("OpenRGB")
    if found:
        return found
    if sys.platform.startswith("win"):
        return next((p for p in WINDOWS_PATHS if Path(p).is_file()), None)
    return None


def start_openrgb(path: str) -> None:
    """OpenRGB im Hintergrund mit SDK-Server starten."""
    flags = 0x08000000 if sys.platform.startswith("win") else 0
    subprocess.Popen([path, "--server", "--startminimized"], creationflags=flags,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=not flags)
