"""Windows (CI): nachgebautes Fingerabdruckmodul an einer Named Pipe – für den Test des Anmeldebausteins.

Aufruf: python fake_zw101_pipe.py <pipe> <platz>  – Platz <platz> ist mit Finger „A“ belegt; der Finger liegt
nach zwei Abfragen auf (erst „kein Finger“, wie im echten Leben). Beendet sich, wenn der Baustein trennt.
"""

import ctypes
import sys
from ctypes import wintypes
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from alupc.platform.zw_fingerprint import HEADER, PID_ACK, build_packet, parse_packet  # noqa: E402
from fake_zw101 import FakeZW101  # noqa: E402

k32 = ctypes.windll.kernel32
k32.CreateNamedPipeW.restype = wintypes.HANDLE


class PipeFake(FakeZW101):
    def __init__(self, slot: int):  # ohne pty: nur die Befehlslogik von FakeZW101
        self.capacity = 50
        self.finger = "A"
        self.auto_lift = False
        self._lifted = 2  # die ersten beiden Bildaufnahmen: kein Finger
        self.buffers = {}
        self.library = {slot: "A"}
        self.password_ok = True
        self.commands = []


def read(h, n):
    buf = ctypes.create_string_buffer(n)
    data = b""
    while len(data) < n:
        got = wintypes.DWORD()
        if not k32.ReadFile(h, ctypes.byref(buf, 0), n - len(data), ctypes.byref(got), None) or not got.value:
            return None
        data += buf.raw[:got.value]
    return data


def main(pipe: str, slot: int):
    fake = PipeFake(slot)
    h = k32.CreateNamedPipeW(pipe, 3, 0, 1, 4096, 4096, 0, None)  # DUPLEX, Byte-Modus, blockierend
    print("bereit", flush=True)
    k32.ConnectNamedPipe(h, None)
    while True:
        head = read(h, 9)
        if head is None or head[:2] != HEADER:
            break
        length = int.from_bytes(head[7:9], "big")
        body = read(h, length)
        if body is None:
            break
        _pid, payload = parse_packet(head + body)
        code, params = fake._handle(payload[0], payload[1:])
        out = build_packet(PID_ACK, bytes([code]) + params)
        written = wintypes.DWORD()
        k32.WriteFile(h, out, len(out), ctypes.byref(written), None)
    print("befehle", " ".join(f"{c:02x}" for c in fake.commands), flush=True)


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]))
