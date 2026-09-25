"""Nachgebauter OpenRGB-SDK-Server für Tests (Format nach OpenRGBSDK.md). Merkt sich, was ankommt."""

import socket
import struct
import threading


def s(text: str) -> bytes:
    raw = text.encode() + b"\0"
    return struct.pack("<H", len(raw)) + raw


def mode(name: str, version: int, colors=0) -> bytes:
    out = s(name) + struct.pack("<iIII", 1, 0, 0, 100)
    if version >= 3:
        out += struct.pack("<II", 0, 100)
    out += struct.pack("<III", 0, 1, 50)  # colors_min, colors_max, speed
    if version >= 3:
        out += struct.pack("<I", 100)
    out += struct.pack("<II", 0, 0)  # direction, color_mode
    return out + struct.pack("<H", colors) + b"\x01\x02\x03\x00" * colors


def zone(name: str, leds: int, version: int, matrix=False, segments=0) -> bytes:
    out = s(name) + struct.pack("<iIII", 1, leds, leds, leds)
    if matrix:
        h, w = 2, leds // 2
        data = struct.pack("<II", h, w) + b"".join(struct.pack("<I", i) for i in range(h * w))
        out += struct.pack("<H", len(data)) + data
    else:
        out += struct.pack("<H", 0)
    if version >= 4:
        out += struct.pack("<H", segments)
        for i in range(segments):
            out += s(f"Segment {i}") + struct.pack("<iII", 0, i, 1)
    return out


def device(name: str, dtype: int, zones: list[tuple[str, int, bool, int]], version: int) -> bytes:
    body = struct.pack("<i", dtype) + s(name)
    if version >= 1:
        body += s("Hersteller")
    body += s("Beschreibung") + s("1.0") + s("SN123") + s("I2C: /dev/i2c-1")
    body += struct.pack("<Hi", 3, 0) + mode("Direct", version) + mode("Static", version, 1) + mode("Rainbow", version)
    body += struct.pack("<H", len(zones))
    total = 0
    for zname, leds, matrix, segs in zones:
        body += zone(zname, leds, version, matrix, segs)
        total += leds
    body += struct.pack("<H", total) + b"".join(s(f"LED {i}") + struct.pack("<I", i) for i in range(total))
    body += struct.pack("<H", total) + b"\0\0\0\0" * total
    return struct.pack("<I", 4 + len(body)) + body


class FakeOpenRGB:
    def __init__(self, version: int = 4, silent_version: bool = False):
        self.version = version
        self.silent_version = silent_version  # wie Protokoll 0: keine Antwort auf die Versionsfrage
        self.devices = [("ASUS Mainboard", 0, [("Aura", 4, False, 2), ("Header", 2, False, 0)]),
                        ("Tastatur K70", 5, [("Tasten", 6, True, 0)])]
        self.received: list[tuple[int, int, bytes]] = []
        self.client_name = b""
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(4)
        self.port = self.sock.getsockname()[1]
        self.used_version = None
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self):
        while True:
            try:
                conn, _ = self.sock.accept()
            except OSError:
                return
            threading.Thread(target=self._client, args=(conn,), daemon=True).start()

    def _client(self, conn):
        def read(n):
            buf = b""
            while len(buf) < n:
                chunk = conn.recv(n - len(buf))
                if not chunk:
                    raise ConnectionError
                buf += chunk
            return buf

        def send(dev, pid, body=b""):
            conn.sendall(b"ORGB" + struct.pack("<III", dev, pid, len(body)) + body)

        try:
            while True:
                head = read(16)
                assert head[:4] == b"ORGB"
                dev, pid, size = struct.unpack("<III", head[4:])
                body = read(size) if size else b""
                self.received.append((dev, pid, body))
                if pid == 40 and not self.silent_version:
                    send(0, 40, struct.pack("<I", self.version))
                elif pid == 50:
                    self.client_name = body
                elif pid == 0:
                    send(0, 100)  # dazwischen eine unaufgeforderte Meldung (muss übersprungen werden)
                    send(0, 0, struct.pack("<I", len(self.devices)))
                elif pid == 1:
                    ver = struct.unpack("<I", body)[0] if body else 0
                    self.used_version = ver
                    name, dtype, zones = self.devices[dev]
                    send(dev, 1, device(name, dtype, zones, ver))
        except (ConnectionError, OSError):
            conn.close()

    def leds(self, dev: int) -> list[tuple[int, int, int]]:
        """Zuletzt gesetzte Farben eines Geräts."""
        for d, pid, body in reversed(self.received):
            if d == dev and pid == 1050:
                n = struct.unpack("<H", body[4:6])[0]
                return [tuple(body[6 + 4 * i:9 + 4 * i]) for i in range(n)]
        return []

    def close(self):
        self.sock.close()
