"""Nachgebautes Fingerabdruckmodul (EF01-Protokoll wie HLK-ZW101/AS608) an einem virtuellen
seriellen Anschluss (pty, nur Linux) – damit lässt sich der Treiber ohne Hardware testen.

Der „Finger“ wird vom Test gesetzt: `fake.finger = "A"` (liegt auf) bzw. `None` (kein Finger).
Mit `auto_lift=True` hebt der Finger nach jeder Merkmal-Erzeugung kurz ab und kommt wieder
(wie ein Mensch beim Anlernen).
"""

from __future__ import annotations

import os
import threading
import time

from alupc.platform.zw_fingerprint import (
    ADDRESS,
    HEADER,
    PID_ACK,
    build_packet,
    parse_packet,
)


class FakeZW101:
    def __init__(self, capacity: int = 50):
        import pty
        import tty

        self.master, slave = pty.openpty()
        tty.setraw(slave)
        self.port = os.ttyname(slave)
        self._slave = slave
        self.capacity = capacity
        self.finger: str | None = None
        self.auto_lift = False
        self._lifted = 0
        self.buffers: dict[int, str | None] = {}
        self.library: dict[int, str] = {}
        self.password_ok = True
        self.commands: list[int] = []
        self._stop = False
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def close(self):
        self._stop = True
        for fd in (self.master, self._slave):
            try:
                os.close(fd)
            except OSError:
                pass

    # ---------------------------------------------------------------- Empfang
    def _read(self, n):
        data = b""
        while len(data) < n and not self._stop:
            try:
                chunk = os.read(self.master, n - len(data))
            except OSError:
                return None
            if not chunk:
                time.sleep(0.005)
            data += chunk
        return data

    def _run(self):
        while not self._stop:
            first = self._read(1)
            if first is None:
                return
            if first != HEADER[:1]:
                continue
            second = self._read(1)
            if second != HEADER[1:]:
                continue
            rest = self._read(7)
            if rest is None:
                return
            length = int.from_bytes(rest[5:7], "big")
            body = self._read(length)
            if body is None:
                return
            _pid, payload = parse_packet(HEADER + rest + body)
            code, params = self._handle(payload[0], payload[1:])
            os.write(self.master, build_packet(PID_ACK, bytes([code]) + params))

    # ---------------------------------------------------------------- Befehle
    def _finger_now(self):
        if self._lifted > 0:
            self._lifted -= 1
            return None
        return self.finger

    def _handle(self, cmd: int, p: bytes) -> tuple[int, bytes]:
        self.commands.append(cmd)
        if cmd == 0x13:  # Passwort prüfen
            return (0x00 if self.password_ok else 0x13), b""
        if cmd == 0x0F:  # Systemparameter
            data = (0).to_bytes(2, "big") + (9).to_bytes(2, "big") + self.capacity.to_bytes(2, "big") + \
                (3).to_bytes(2, "big") + ADDRESS + (1).to_bytes(2, "big") + (6).to_bytes(2, "big")
            return 0x00, data
        if cmd == 0x01:  # Bild aufnehmen
            self._image = self._finger_now()
            return (0x00 if self._image else 0x02), b""
        if cmd == 0x02:  # Merkmale erzeugen
            if not getattr(self, "_image", None):
                return 0x15, b""
            self.buffers[p[0]] = self._image
            if self.auto_lift:
                self._lifted = 2
            return 0x00, b""
        if cmd == 0x05:  # Vorlage aus Puffer 1+2
            if self.buffers.get(1) is None or self.buffers.get(1) != self.buffers.get(2):
                return 0x0A, b""
            return 0x00, b""
        if cmd == 0x06:  # speichern
            slot = int.from_bytes(p[1:3], "big")
            if slot >= self.capacity:
                return 0x0B, b""
            self.library[slot] = self.buffers.get(p[0])
            return 0x00, b""
        if cmd == 0x04:  # suchen
            finger = self.buffers.get(p[0])
            for slot, stored in sorted(self.library.items()):
                if stored == finger:
                    return 0x00, slot.to_bytes(2, "big") + (120).to_bytes(2, "big")
            return 0x09, b"\x00\x00\x00\x00"
        if cmd == 0x0C:  # löschen
            start, count = int.from_bytes(p[0:2], "big"), int.from_bytes(p[2:4], "big")
            for slot in range(start, start + count):
                self.library.pop(slot, None)
            return 0x00, b""
        if cmd == 0x0D:  # alles leeren
            self.library.clear()
            return 0x00, b""
        if cmd == 0x1F:  # Belegungstabelle
            page = p[0]
            table = bytearray(32)
            for slot in self.library:
                if page * 256 <= slot < (page + 1) * 256:
                    i = slot - page * 256
                    table[i // 8] |= 1 << (i % 8)
            return 0x00, bytes(table)
        if cmd == 0x1D:
            return 0x00, len(self.library).to_bytes(2, "big")
        return 0x01, b""
