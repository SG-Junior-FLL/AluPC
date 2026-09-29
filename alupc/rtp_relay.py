"""Zwischenstück für das AirPlay-Bild: UxPlay → Relais → AluPCs Player (alles auf 127.0.0.1, RTP/H.264).

Warum: Ein iPhone/iPad schickt beim Bildschirm-Spiegeln das vollständige Bild (Schlüsselbild, IDR) praktisch nur
einmal – beim Verbinden. Danach kommen nur noch Änderungen. War AluPCs Player in diesem Moment nicht bereit
(z. B. weil er nach ~10 s ohne Daten mit „Connection timed out“ aufgegeben hat), bekam er das Schlüsselbild nie
und konnte nichts anzeigen – Ton lief trotzdem (Fehler bis 0.58: „verbunden, Ton ja, Bild nein“).

Das Relais
* leitet jedes Paket sofort weiter,
* merkt sich das letzte Schlüsselbild samt allem danach und spielt es einem neu gestarteten Player vor
  (`replay()`), damit er sofort das aktuelle Bild hat,
* schickt ohne neue Daten alle 2 s das letzte Paket noch einmal (der Player verwirft Doppelte), damit der Player
  nicht wegen „keine Daten“ aufgibt.
"""

from __future__ import annotations

import socket
import threading
import time

MAX_CACHE = 64 * 1024 * 1024  # mehr merkt sich das Relais nicht (dann erst wieder ab dem nächsten Schlüsselbild)
KEEPALIVE = 2.0


def rtp_payload(packet: bytes) -> bytes:
    """Nutzdaten eines RTP-Pakets (ohne Kopf, CSRC-Liste und Erweiterung)."""
    if len(packet) < 12 or packet[0] >> 6 != 2:
        return b""
    offset = 12 + 4 * (packet[0] & 0x0F)
    if packet[0] & 0x10 and len(packet) >= offset + 4:  # Kopf-Erweiterung
        offset += 4 + 4 * int.from_bytes(packet[offset + 2:offset + 4], "big")
    end = len(packet)
    if packet[0] & 0x20 and end > offset:  # Auffüllung
        end -= packet[-1]
    return packet[offset:end]


def sps_of(payload: bytes) -> bytes | None:
    """Die Bildparameter (SPS, NAL-Typ 7) aus einem Paket – einzeln oder im STAP-A."""
    if not payload:
        return None
    kind = payload[0] & 0x1F
    if kind == 7:
        return payload
    if kind == 24:
        i = 1
        while i + 2 < len(payload):
            size = int.from_bytes(payload[i:i + 2], "big")
            if size == 0 or i + 2 + size > len(payload):
                break
            if payload[i + 2] & 0x1F == 7:
                return payload[i + 2:i + 2 + size]
            i += 2 + size
    return None


def nal_types(payload: bytes) -> list[int]:
    """H.264-NAL-Typen in einem RTP-Paket (Einzel-NAL, STAP-A, Anfang eines FU-A)."""
    if not payload:
        return []
    kind = payload[0] & 0x1F
    if 1 <= kind <= 23:
        return [kind]
    if kind == 24:  # STAP-A: mehrere NALs
        types, i = [], 1
        while i + 2 < len(payload):
            size = int.from_bytes(payload[i:i + 2], "big")
            if size == 0 or i + 2 + size > len(payload):
                break
            types.append(payload[i + 2] & 0x1F)
            i += 2 + size
        return types
    if kind == 28 and len(payload) > 1 and payload[1] & 0x80:  # FU-A, erstes Stück
        return [payload[1] & 0x1F]
    return []


class RtpRelay:
    def __init__(self, out_port: int, host: str = "127.0.0.1"):
        self.out = (host, out_port)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 8 * 1024 * 1024)
        self.sock.bind((host, 0))
        self.in_port = self.sock.getsockname()[1]
        self.send = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.cache: list[bytes] = []
        self.cache_bytes = 0
        self.has_keyframe = False
        self.params: dict[int, bytes] = {}  # letzte SPS (7) / PPS (8) als eigene Pakete
        self.last: bytes | None = None
        self.last_time = 0.0
        self.packets = 0
        self._replay = threading.Event()
        self._reset = threading.Event()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="AirPlay-Relais", daemon=True)
        self._thread.start()

    # ---- von außen
    def replay(self) -> None:
        """Neuer Player → aktuellen Stand (Schlüsselbild + alles danach) noch einmal schicken."""
        self._replay.set()

    def reset(self) -> None:
        """Handy getrennt → gemerktes Bild vergessen (beim nächsten Verbinden kommt ein neues)."""
        self._reset.set()

    def _forget(self) -> None:
        self.has_keyframe = False
        self._in_idr = False
        self.cache, self.cache_bytes = [], 0
        self.last = None

    def stop(self) -> None:
        self._stop.set()
        try:
            self.sock.close()
        except OSError:
            pass
        self._thread.join(timeout=2)
        self.send.close()

    # ---- im eigenen Thread
    _in_idr = False  # gerade mitten in einem Schlüsselbild (es kann aus mehreren Teilen/Slices bestehen)
    # Zähler: neue Bildparameter (SPS). AluPCs Player bleibt sonst beim alten Format stehen (Bild friert ein, z. B.
    # nach dem Drehen des iPads) – AluPC startet ihn dann neu, das Relais spielt das neue Schlüsselbild vor.
    generation = 0
    _sps: bytes | None = None

    def _remember(self, packet: bytes) -> None:
        payload = rtp_payload(packet)
        types = nal_types(payload)
        if 7 in types:
            self.params[7] = packet  # SPS (einzeln oder zusammen mit PPS in einem STAP-A)
            sps = sps_of(payload)
            if sps and sps != self._sps:
                if self._sps is not None:  # neue Bildgröße/-art (iPad gedreht, neue Verbindung)
                    self.generation += 1
                self._sps = sps
        elif types == [8]:
            self.params[8] = packet
        if 5 in types and not self._in_idr:
            # neues Schlüsselbild: ab hier merken – mit den Bildparametern davor, falls sie einzeln kamen
            self.cache = [] if 7 in types else [self.params[t] for t in (7, 8) if t in self.params]
            self.cache.append(packet)
            self.cache_bytes = sum(len(p) for p in self.cache)
            self.has_keyframe = True
            self._in_idr = True
            return
        if 1 in types:  # normales Bild → das Schlüsselbild ist vorbei
            self._in_idr = False
        if self.has_keyframe:
            self.cache.append(packet)
            self.cache_bytes += len(packet)
            if self.cache_bytes > MAX_CACHE:  # zu viel – ab dem nächsten Schlüsselbild wieder merken
                self.has_keyframe, self.cache, self.cache_bytes = False, [], 0

    # Eigene Laufnummern/Zeitstempel für alles, was zum Player geht: Der Player ordnet nach Laufnummer und verwirft
    # „alte“ Pakete – nachgereichte Pakete bekämen sonst ihre alten Nummern und würden nie dekodiert.
    _out_seq = 0
    _ts_offset = 0
    _last_out_ts: int | None = None
    _last_in_ts = 0

    def _run(self) -> None:
        self.sock.settimeout(0.25)
        while not self._stop.is_set():
            if self._reset.is_set():
                self._reset.clear()
                self._forget()
            if self._replay.is_set():
                self._replay.clear()
                self._do_replay()
            try:
                packet = self.sock.recv(65536)
            except socket.timeout:
                if self.last is not None and time.monotonic() - self.last_time > KEEPALIVE:
                    self._keepalive()  # Lebenszeichen: Player gibt sonst nach ~10–20 s ohne Daten auf
                    self.last_time = time.monotonic()
                continue
            except OSError:
                break
            if len(packet) < 12:
                continue
            self.packets += 1
            self.last, self.last_time = packet, time.monotonic()
            self._remember(packet)
            ts = int.from_bytes(packet[4:8], "big")
            self._last_in_ts = ts
            self._send(packet, (ts + self._ts_offset) & 0xFFFFFFFF)

    def _do_replay(self) -> None:
        cache = list(self.cache)
        if not cache:
            return
        base = int.from_bytes(cache[0][4:8], "big")
        start = ((self._last_out_ts or base) + 3000) & 0xFFFFFFFF  # kurz nach dem zuletzt Gesendeten
        shift = start - base
        out_ts = start
        for i, packet in enumerate(cache):
            out_ts = (int.from_bytes(packet[4:8], "big") + shift) & 0xFFFFFFFF
            self._send(packet, out_ts)
            if i % 32 == 31:
                time.sleep(0.001)  # Empfangspuffer des Players nicht überlaufen lassen
        # Live-Bilder danach nahtlos anschließen
        self._ts_offset = (out_ts + 3000 - self._last_in_ts) & 0xFFFFFFFF

    def _keepalive(self) -> None:
        """Harmloses Paket (H.264-Trennzeichen „AUD“, vom Decoder ignoriert) mit neuer Laufnummer."""
        head = bytearray(self.last[:12])
        head[0] = 0x80  # ohne CSRC/Erweiterung/Auffüllung
        head[1] &= 0x7F  # ohne Marker
        self._send(bytes(head) + b"\x09\xf0", self._last_out_ts or 0)

    def _send(self, packet: bytes, ts: int) -> None:
        head = bytearray(packet[:12])
        head[2:4] = self._out_seq.to_bytes(2, "big")
        head[4:8] = ts.to_bytes(4, "big")
        self._out_seq = (self._out_seq + 1) & 0xFFFF
        self._last_out_ts = ts
        try:
            self.send.sendto(bytes(head) + packet[12:], self.out)
        except OSError:
            pass
