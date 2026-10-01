"""Kleiner WebSocket-Teil (RFC 6455) für die Minispiele – ohne zusätzliche Bibliothek.

Pro Handy eine Verbindung: Eingaben kommen sofort an (kein neuer HTTP-Aufruf je Tipp), und der Stand wird dem Handy
geschickt, sobald er sich ändert (statt dass das Handy ständig nachfragt).
"""

from __future__ import annotations

import base64
import hashlib
import json
import socket
import struct
import threading
import time

GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
MAX_FRAME = 64 * 1024
PUSH_EVERY = 0.04  # Sekunden – so oft wird geschaut, ob sich der Stand geändert hat
READ_TIMEOUT = 30.0  # das Handy schickt alle 4 s ein Lebenszeichen


def accept_key(key: str) -> str:
    return base64.b64encode(hashlib.sha1((key.strip() + GUID).encode()).digest()).decode()


def read_frame(rfile) -> tuple[int, bytes] | None:
    head = rfile.read(2)
    if len(head) < 2:
        return None
    op, masked, n = head[0] & 0x0F, head[1] & 0x80, head[1] & 0x7F
    if n == 126:
        n = struct.unpack(">H", rfile.read(2))[0]
    elif n == 127:
        n = struct.unpack(">Q", rfile.read(8))[0]
    if n > MAX_FRAME:
        return None
    mask = rfile.read(4) if masked else b""
    data = rfile.read(n)
    if len(data) < n:
        return None
    if masked:
        data = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
    return op, data


def frame(op: int, payload: bytes) -> bytes:
    n = len(payload)
    if n < 126:
        head = struct.pack(">BB", 0x80 | op, n)
    elif n < 65536:
        head = struct.pack(">BBH", 0x80 | op, 126, n)
    else:
        head = struct.pack(">BBQ", 0x80 | op, 127, n)
    return head + payload


def serve_game(sock, rfile, hub, pid: str, alive) -> None:
    """Läuft im Webserver-Thread, bis das Handy geht oder die Runde endet. `alive()` → False beendet."""
    try:
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    except OSError:
        pass
    sock.settimeout(READ_TIMEOUT)
    send_lock = threading.Lock()
    stop = threading.Event()

    def send(op, payload):
        with send_lock:
            sock.sendall(frame(op, payload))

    def push():
        last, last_t = None, 0.0
        try:
            while not stop.is_set() and alive():
                hub.seen(pid)
                text = json.dumps(hub.state_for(pid), ensure_ascii=False)
                now = time.monotonic()
                if text != last or now - last_t > 2.0:
                    send(0x1, text.encode())
                    last, last_t = text, now
                stop.wait(PUSH_EVERY)
        except OSError:
            pass
        finally:
            stop.set()
            try:  # Lesen im anderen Thread beenden
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

    pusher = threading.Thread(target=push, name="AluCast-Spiel", daemon=True)
    pusher.start()
    try:
        while not stop.is_set():
            got = read_frame(rfile)
            if got is None:
                break
            op, data = got
            if op == 0x8:  # Schließen
                try:
                    send(0x8, data[:2])
                except OSError:
                    pass
                break
            if op == 0x9:  # Ping
                send(0xA, data)
            elif op == 0x1:
                try:
                    msg = json.loads(data.decode("utf-8"))
                except (ValueError, UnicodeDecodeError):
                    continue
                if isinstance(msg, dict) and not msg.get("ping"):
                    hub.input(pid, msg)
    except (OSError, ValueError, struct.error):
        pass
    finally:
        stop.set()
        pusher.join(1.0)
