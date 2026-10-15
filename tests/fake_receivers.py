"""Nachgebaute Empfänger für die Tests: ein Chromecast (Cast-Protokoll über TLS, wie ein echtes Gerät) und ein
AirPlay-Empfänger (AirPlay-Video: POST /play, GET /playback-info). Beide holen den angebotenen HLS-Stream wirklich
ab und dekodieren ein Bild daraus – so prüfen die Tests den ganzen Weg bis zum Bild."""

from __future__ import annotations

import json
import plistlib
import socket
import ssl
import struct
import tempfile
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def fetch_frame(url: str, tries: int = 40):
    """HLS-Playlist laden, ein .ts-Stück holen, erstes Bild als RGB-Array (oder None)."""
    import time

    import av

    for _ in range(tries):
        try:
            pl = urllib.request.urlopen(url, timeout=5).read().decode()
            segs = [ln for ln in pl.splitlines() if ln and not ln.startswith("#")]
            if segs:
                seg = urllib.request.urlopen(url.rsplit("/", 1)[0] + "/" + segs[-1], timeout=5).read()
                path = Path(tempfile.mkdtemp()) / "s.ts"
                path.write_bytes(seg)
                with av.open(str(path)) as c:
                    for frame in c.decode(video=0):
                        arr = frame.to_ndarray(format="rgb24")
                        if arr.max() > 40:  # die ersten Stücke sind schwarz, bis das erste Bild da ist
                            return arr
                        break
        except Exception:  # noqa: BLE001 – Stream noch nicht da
            pass
        time.sleep(0.25)
    return None


# --------------------------------------------------------------------------- Chromecast
def _self_signed(tmp: Path) -> tuple[str, str]:
    """Selbst signiertes Zertifikat (wie ein Chromecast, dessen Zertifikat pychromecast nicht prüft)."""
    import datetime

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "fake-cast")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now - datetime.timedelta(minutes=5))
            .not_valid_after(now + datetime.timedelta(days=1)).sign(key, hashes.SHA256()))
    crt, k = tmp / "c.pem", tmp / "k.pem"
    crt.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    k.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL,
                                    serialization.NoEncryption()))
    return str(crt), str(k)


class FakeChromecast:
    """Antwortet auf CONNECT/GET_STATUS/LAUNCH/LOAD/STOP wie ein Chromecast mit Standard-Mediaplayer."""

    def __init__(self):
        from pychromecast.generated import cast_channel_pb2

        self.pb = cast_channel_pb2
        tmp = Path(tempfile.mkdtemp())
        self.ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self.ctx.load_cert_chain(*_self_signed(tmp))
        self.sock = socket.socket()
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(4)
        self.port = self.sock.getsockname()[1]
        self.loaded: list[dict] = []
        self.frame = None  # erstes Bild aus dem geladenen Stream
        self.app_running = False
        self.stopped = threading.Event()
        self.got_frame = threading.Event()
        self._closing = False
        threading.Thread(target=self._accept, daemon=True).start()

    def close(self):
        self._closing = True
        self.sock.close()

    def _accept(self):
        while not self._closing:
            try:
                conn, _ = self.sock.accept()
            except OSError:
                return
            threading.Thread(target=self._serve, args=(self.ctx.wrap_socket(conn, server_side=True),),
                             daemon=True).start()

    def _send(self, conn, src, dst, ns, payload):
        m = self.pb.CastMessage()
        m.protocol_version = m.CASTV2_1_0
        m.source_id, m.destination_id, m.namespace = src, dst, ns
        m.payload_type = m.STRING
        m.payload_utf8 = json.dumps(payload)
        data = m.SerializeToString()
        conn.sendall(struct.pack(">I", len(data)) + data)

    def _receiver_status(self, rid):
        apps = [{"appId": "CC1AD845", "sessionId": "s1", "transportId": "web-5", "displayName": "Default Media Receiver",
                 "statusText": "", "namespaces": [{"name": "urn:x-cast:com.google.cast.media"}]}] if self.app_running else []
        return {"type": "RECEIVER_STATUS", "requestId": rid,
                "status": {"applications": apps, "volume": {"level": 1.0, "muted": False}, "isActiveInput": True}}

    def _media_status(self, rid, state="PLAYING"):
        st = [] if not self.loaded else [{"mediaSessionId": 1, "playerState": state, "currentTime": 0,
                                          "supportedMediaCommands": 15, "volume": {"level": 1, "muted": False},
                                          "media": {**self.loaded[-1], "streamType": "LIVE"}}]
        return {"type": "MEDIA_STATUS", "requestId": rid, "status": st}

    def _serve(self, conn):
        buf = b""
        try:
            while True:
                while len(buf) < 4:
                    chunk = conn.recv(65536)
                    if not chunk:
                        return
                    buf += chunk
                n = struct.unpack(">I", buf[:4])[0]
                while len(buf) < 4 + n:
                    chunk = conn.recv(65536)
                    if not chunk:
                        return
                    buf += chunk
                m = self.pb.CastMessage()
                m.ParseFromString(buf[4:4 + n])
                buf = buf[4 + n:]
                data = json.loads(m.payload_utf8 or "{}")
                kind, rid = data.get("type"), data.get("requestId", 0)
                me, you, ns = m.destination_id, m.source_id, m.namespace
                if kind == "PING":
                    self._send(conn, me, you, ns, {"type": "PONG"})
                elif ns.endswith(".receiver") and kind == "GET_STATUS":
                    self._send(conn, me, you, ns, self._receiver_status(rid))
                elif kind == "LAUNCH":
                    self.app_running = True
                    self._send(conn, me, you, ns, self._receiver_status(rid))
                elif ns.endswith(".receiver") and kind == "STOP":
                    self.app_running = False
                    self.stopped.set()
                    self._send(conn, me, you, ns, self._receiver_status(rid))
                elif ns.endswith(".media") and kind == "GET_STATUS":
                    self._send(conn, me, you, ns, self._media_status(rid))
                elif kind == "LOAD":
                    self.loaded.append(data.get("media") or {})
                    self._send(conn, me, you, ns, self._media_status(rid))
                    threading.Thread(target=self._watch, args=(self.loaded[-1].get("contentId", ""),),
                                     daemon=True).start()
                elif ns.endswith(".media") and kind == "STOP":
                    self.stopped.set()
                    self._send(conn, me, you, ns, self._media_status(rid, "IDLE"))
        except (OSError, ssl.SSLError):
            return

    def _watch(self, url):
        self.frame = fetch_frame(url)
        self.got_frame.set()


# --------------------------------------------------------------------------- AirPlay
class FakeAirPlay:
    """AirPlay-Video-Empfänger: nimmt /play an, meldet „spielt“, holt den Stream. need_pin=True → 470 wie Apple TV."""

    def __init__(self, need_pin: bool = False):
        self.plays: list[dict] = []
        self.stops = 0
        self.frame = None
        self.got_frame = threading.Event()
        self.need_pin = need_pin
        outer = self

        class H(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *_a):
                pass

            def _r(self, code=200, body=b"", ctype="text/plain"):
                self.send_response(code)
                self.send_header("Content-Length", str(len(body)))
                if body:
                    self.send_header("Content-Type", ctype)
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self):
                n = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(n) if n else b""
                if outer.need_pin:
                    self._r(470)
                    return
                if self.path == "/play":
                    info = plistlib.loads(body) if body.startswith(b"bplist") else {}
                    outer.plays.append(info)
                    threading.Thread(target=outer._watch, args=(info.get("Content-Location", ""),),
                                     daemon=True).start()
                elif self.path == "/stop":
                    outer.stops += 1
                self._r(200)

            def do_GET(self):
                if self.path.startswith("/playback-info"):
                    self._r(200, plistlib.dumps({"duration": 0.0, "position": 1.0, "rate": 1.0, "readyToPlay": True}),
                            "text/x-apple-plist+xml")
                else:
                    self._r(200)

            do_PUT = do_POST

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def _watch(self, url):
        self.frame = fetch_frame(url)
        self.got_frame.set()

    def close(self):
        self.httpd.shutdown()
