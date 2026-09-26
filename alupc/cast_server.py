"""AluCast: Handy → Monitor 2 über den Browser – selbst gebaut, ohne App und ohne Zusatzprogramm.

AluPC startet einen kleinen Webserver im eigenen WLAN. Das Handy scannt den QR-Code (oder tippt die
Adresse und den 6-stelligen Code ein) und kann dann Fotos/Videos senden, Links (z. B. YouTube) und
Text zeigen sowie Monitor 2 fernsteuern. Funktioniert mit iPhone und Android gleich.

Was ein Browser nicht kann: den Handy-Bildschirm übertragen (dafür gibt es AirPlay).
"""

from __future__ import annotations

import hmac
import json
import re
import secrets
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from PySide6.QtCore import QObject, Signal

from .cast_page import PAGE
from .config import config_dir

MAX_UPLOAD = 2 * 1024 ** 3  # 2 GB
KEEP_FILES = 100
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
VIDEO_EXT = {".mp4", ".mov", ".m4v", ".webm", ".mkv", ".3gp", ".avi"}
MIME_EXT = {"image/jpeg": ".jpg", "image/png": ".png", "image/gif": ".gif", "image/webp": ".webp",
            "video/mp4": ".mp4", "video/quicktime": ".mov", "video/webm": ".webm", "video/3gpp": ".3gp"}
# Befehle, die das Handy auslösen darf (dazu „szene:Name“ und „lautstaerke:Zahl“)
ALLOWED_COMMANDS = {"standbild", "schwarz", "spiegeln", "erweitern", "bildschirmschoner", "naechste_szene",
                    "vorherige_szene", "zeichnungen_loeschen", "timer_start_pause", "timer_plus", "timer_minus",
                    "timer_neustart", "timer_zeigen", "video_pause", "video_vor", "video_zurueck",
                    "rgb_farbe", "rgb_monitor2", "rgb_aus", "zeichnung_zurueck", "kamera", "airplay", "qr",
                    "timer_stopp"}
MAX_FAILS = 10
BLOCK_SECONDS = 60


def route_ip() -> str:
    """IP-Adresse, über die dieser PC ins Netz geht (ohne etwas zu senden)."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.connect(("10.254.254.254", 1))
            return s.getsockname()[0]
        except OSError:
            return "127.0.0.1"


# Adapter, die Handys im WLAN nie erreichen: virtuelle Netze von WSL/Hyper-V, VMs, Docker, VPNs
VIRTUAL_HINTS = ("vethernet", "wsl", "hyper-v", "virtualbox", "vmware", "vmnet", "docker", "vbox", "virbr",
                 "br-", "tailscale", "zerotier", "wireguard", "tun", "tap", "vpn", "loopback", "bluetooth")


def score_address(ip: str, name: str, wifi: bool, route: str) -> int:
    """Wie wahrscheinlich erreicht ein Handy im WLAN diesen PC über diese Adresse? (höher = besser)"""
    low = name.lower()
    score = 0
    if ip == route:
        score += 3
    if wifi or any(w in low for w in ("wlan", "wi-fi", "wifi", "wireless", "wlp")):
        score += 3
    if any(v in low for v in VIRTUAL_HINTS):
        score -= 10
    if ip.startswith(("192.168.", "10.")):
        score += 2
    elif ip.startswith("172."):
        score -= 1  # oft virtuelle Netze (WSL, Docker)
    if ip.startswith(("127.", "169.254.")):
        score -= 20
    return score


def network_addresses() -> list[tuple[str, str, int]]:
    """Alle IPv4-Adressen des PCs: [(Adresse, Adaptername, Bewertung)], beste zuerst."""
    route = route_ip()
    found: dict[str, tuple[str, str, int]] = {}
    try:
        from PySide6.QtNetwork import QAbstractSocket, QNetworkInterface

        for iface in QNetworkInterface.allInterfaces():
            flags = iface.flags()
            if not (flags & QNetworkInterface.IsUp and flags & QNetworkInterface.IsRunning) or \
                    flags & QNetworkInterface.IsLoopBack:
                continue
            wifi = iface.type() == QNetworkInterface.Wifi
            name = iface.humanReadableName() or iface.name()
            for entry in iface.addressEntries():
                addr = entry.ip()
                if addr.protocol() != QAbstractSocket.IPv4Protocol:
                    continue
                ip = addr.toString()
                found[ip] = (ip, name, score_address(ip, name, wifi, route))
    except Exception:  # noqa: BLE001 – ohne QtNetwork: nur die Route
        pass
    if route not in found and route != "127.0.0.1":
        found[route] = (route, "", score_address(route, "", False, route))
    return sorted(found.values(), key=lambda a: -a[2])


def local_ip(preferred: str = "") -> str:
    """IP-Adresse dieses PCs im WLAN/LAN: gewählte Adresse (falls noch vorhanden), sonst die beste."""
    addresses = network_addresses()
    if preferred and any(a[0] == preferred for a in addresses):
        return preferred
    return addresses[0][0] if addresses else route_ip()


def new_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def youtube_embed(url: str) -> str:
    """YouTube-Link → Vollbild-Player (ohne Seite drumherum). Andere Links bleiben unverändert."""
    u = urlparse(url)
    host = u.netloc.lower().removeprefix("www.").removeprefix("m.")
    vid = ""
    if host == "youtu.be":
        vid = u.path.strip("/").split("/")[0]
    elif host in ("youtube.com", "music.youtube.com"):
        if u.path == "/watch":
            vid = parse_qs(u.query).get("v", [""])[0]
        elif u.path.startswith(("/shorts/", "/live/", "/embed/")):
            vid = u.path.split("/")[2] if len(u.path.split("/")) > 2 else ""
    if not re.fullmatch(r"[A-Za-z0-9_-]{6,20}", vid or ""):
        return url
    start = parse_qs(u.query).get("t", [""])[0].rstrip("s")
    extra = f"&start={start}" if start.isdigit() else ""
    return f"https://www.youtube-nocookie.com/embed/{vid}?autoplay=1&rel=0{extra}"


def safe_name(name: str, content_type: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9äöüÄÖÜß._-]+", "_", Path(name or "handy").stem)[:60] or "handy"
    ext = Path(name or "").suffix.lower()
    if ext not in IMAGE_EXT | VIDEO_EXT:
        ext = MIME_EXT.get((content_type or "").split(";")[0].strip().lower(), "")
    return f"{time.strftime('%Y%m%d-%H%M%S')}_{stem}{ext}"


def upload_dir() -> Path:
    return config_dir() / "Vom Handy"


def cleanup(folder: Path, keep: int = KEEP_FILES) -> None:
    files = sorted((f for f in folder.glob("*") if f.is_file()), key=lambda f: f.stat().st_mtime, reverse=True)
    for old in files[keep:]:
        try:
            old.unlink()
        except OSError:
            pass


class CastServer(QObject):
    """Webserver in einem eigenen Thread; Anfragen kommen als Signal im Qt-Hauptthread an."""

    request = Signal(dict)
    state_changed = Signal()

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.httpd: ThreadingHTTPServer | None = None
        self.thread: threading.Thread | None = None
        self.port = 0
        self.snapshot = {"now": "", "scenes": [], "volume": 100, "video": False}
        self.preview = b""  # JPEG von Monitor 2 (vom Qt-Hauptthread erneuert, solange ein Handy zuschaut)
        self.preview_wanted = 0.0
        self._fails: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------ Einstellungen
    def settings(self) -> dict:
        return {"port": 8765, "code": "", "autostart": False, **self.config["cast"]}

    def icon_png(self) -> bytes:
        """App-Symbol fürs Handy (Home-Bildschirm, Browser-Tab) – einmal erzeugt."""
        from PySide6.QtCore import QThread
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        if getattr(self, "_icon", None) is None and app is not None and QThread.currentThread() == app.thread():
            try:
                from PySide6.QtCore import QBuffer, QByteArray, QIODevice

                from .ui import icons

                data = QByteArray()
                buf = QBuffer(data)
                buf.open(QIODevice.WriteOnly)
                icons.app_icon().pixmap(192, 192).toImage().save(buf, "PNG")
                buf.close()
                self._icon = bytes(data)
            except Exception:  # noqa: BLE001 – ohne Symbol geht es auch
                self._icon = b""
        return getattr(self, "_icon", None) or b""

    def allowed(self, what: str) -> bool:
        """Darf ein Handy das? („senden“, „steuern“, „live“, „laser“ – im Setup ausschaltbar)"""
        return bool({"senden": True, "steuern": True, "live": True, "laser": True,
                     **(self.settings().get("allow") or {})}.get(what, False))

    def code(self) -> str:
        code = self.settings()["code"]
        if not re.fullmatch(r"\d{6}", code or ""):
            code = new_code()
            self.config["cast"] = {**self.config["cast"], "code": code}
        return code

    def renew_code(self) -> str:
        self.config["cast"] = {**self.config["cast"], "code": new_code()}
        self.state_changed.emit()
        return self.code()

    def url(self, with_code: bool = True) -> str:
        base = f"http://{local_ip(self.settings().get('ip', ''))}:{self.port or self.settings()['port']}/"
        return base + (f"?k={self.code()}" if with_code else "")

    def running(self) -> bool:
        return self.httpd is not None

    # ------------------------------------------------------------ Start/Stopp
    def start(self) -> bool:
        if self.httpd is not None:
            return True
        self._fails.clear()  # neuer Start → alte Sperren vergessen
        self.code()
        self.icon_png()  # im Qt-Hauptthread erzeugen – der Webserver-Thread liefert es nur aus
        first = int(self.settings()["port"])
        handler = _make_handler(self)
        for port in range(first, first + 10):
            try:
                self.httpd = ThreadingHTTPServer(("0.0.0.0", port), handler)
                break
            except OSError:
                continue
        if self.httpd is None:
            return False
        self.httpd.daemon_threads = True
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, name="AluCast", daemon=True)
        self.thread.start()
        self.state_changed.emit()
        return True

    def stop(self) -> None:
        if self.httpd is None:
            return
        self.httpd.shutdown()
        self.httpd.server_close()
        self.httpd = None
        self.port = 0
        self.state_changed.emit()

    # ------------------------------------------------------------ Zugangscode prüfen (mit Sperre)
    def check(self, ip: str, code: str) -> bool | None:
        """True = ok, False = falsch, None = gesperrt (zu viele Fehlversuche)."""
        now = time.monotonic()
        with self._lock:
            fails = [t for t in self._fails.get(ip, []) if now - t < BLOCK_SECONDS]
            self._fails[ip] = fails
            if len(fails) >= MAX_FAILS:
                return None
            if not code:  # ohne Code ist es kein Rateversuch
                return False
            if hmac.compare_digest((code or "").encode(), self.code().encode()):
                return True
            fails.append(now)
            return False


def _make_handler(server: CastServer):
    class Handler(BaseHTTPRequestHandler):
        server_version = "AluCast"
        protocol_version = "HTTP/1.1"
        timeout = 60  # hängende Verbindungen nicht ewig offen halten

        def log_message(self, *_args):  # nichts in die Konsole schreiben
            pass

        def _send(self, status: int, body: bytes, ctype: str = "application/json; charset=utf-8"):
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, status: int, obj):
            self._send(status, json.dumps(obj, ensure_ascii=False).encode())

        def _auth(self) -> bool:
            if not server.running():  # nach „Beenden“ nichts mehr annehmen (auch offene Verbindungen)
                self.close_connection = True
                self._json(503, {"error": "AluCast ist beendet"})
                return False
            ok = server.check(self.client_address[0], self.headers.get("X-AluPC-Code", ""))
            if ok:
                return True
            self.close_connection = True
            if ok is None:
                self._json(429, {"error": "Zu viele falsche Codes – bitte 1 Minute warten"})
            else:
                self._json(403, {"error": "Falscher Code"})
            return False

        def _body_json(self) -> dict:
            n = int(self.headers.get("Content-Length") or 0)
            if n < 0 or n > 100_000:
                raise ValueError("zu groß")
            data = json.loads(self.rfile.read(n) or b"{}")
            if not isinstance(data, dict):
                raise ValueError("ungültig")
            return data

        def do_GET(self):
            path = urlparse(self.path).path
            if path in ("/", "/index.html"):
                self._send(200, PAGE.encode(), "text/html; charset=utf-8")
            elif path == "/api/status":
                if self._auth():
                    self._json(200, server.snapshot)
            elif path == "/api/preview":
                if self._auth() and self._may("live"):
                    server.preview_wanted = time.monotonic()
                    if server.preview:
                        self._send(200, server.preview, "image/jpeg")
                    else:
                        self._send(204, b"", "image/jpeg")
            elif path in ("/icon.png", "/apple-touch-icon.png", "/favicon.ico"):
                self._send(200, server.icon_png(), "image/png")
            elif path == "/manifest.json":  # „Zum Home-Bildschirm“: öffnet wie eine App (ohne Browserleiste)
                self._send(200, json.dumps({"name": "AluPC-Fernbedienung", "short_name": "AluPC",
                                            "start_url": "/", "display": "standalone",
                                            "background_color": "#0b1020", "theme_color": "#0b1020",
                                            "icons": [{"src": "/icon.png", "sizes": "192x192",
                                                       "type": "image/png"}]}).encode(),
                           "application/manifest+json")
            else:
                self._json(404, {"error": "Nicht gefunden"})

        def _may(self, what: str) -> bool:
            if server.allowed(what):
                return True
            self._json(423, {"error": "In AluPC ausgeschaltet (Setup → Handy & Kamera)"})
            return False

        def do_POST(self):
            u = urlparse(self.path)
            if not self._auth():
                return
            need = {"/api/upload": "senden", "/api/link": "senden", "/api/text": "senden",
                    "/api/laser": "laser", "/api/draw": "laser", "/api/cmd": "steuern",
                    "/api/mouse": "steuern"}.get(u.path)
            if need and not self._may(need):
                self.close_connection = True
                return
            try:
                if u.path == "/api/upload":
                    self._upload(parse_qs(u.query).get("name", ["handy"])[0])
                    return
                data = self._body_json()
                if u.path == "/api/link":
                    url = str(data.get("url", "")).strip()
                    if not re.match(r"^(https?://)?[\w.-]+\.[a-z]{2,}", url, re.I):
                        self._json(400, {"error": "Das ist kein Link"})
                        return
                    if not url.lower().startswith(("http://", "https://")):
                        url = "https://" + url
                    server.request.emit({"kind": "link", "url": youtube_embed(url), "original": url})
                elif u.path == "/api/text":
                    text = str(data.get("text", "")).strip()[:2000]
                    if not text:
                        self._json(400, {"error": "Kein Text"})
                        return
                    server.request.emit({"kind": "text", "text": text})
                elif u.path == "/api/laser":
                    if data.get("up"):
                        server.request.emit({"kind": "laser", "x": None, "y": None})
                    else:
                        x, y = float(data.get("x")), float(data.get("y"))
                        if not (0 <= x <= 1 and 0 <= y <= 1):
                            raise ValueError("außerhalb")
                        server.request.emit({"kind": "laser", "x": x, "y": y})
                elif u.path == "/api/draw":  # mit dem Finger auf Monitor 2 zeichnen
                    phase = str(data.get("phase", ""))
                    if phase not in ("down", "move", "up"):
                        raise ValueError("phase")
                    req = {"kind": "draw", "phase": phase}
                    if phase != "up":
                        x, y = float(data.get("x")), float(data.get("y"))
                        if not (0 <= x <= 1 and 0 <= y <= 1):
                            raise ValueError("außerhalb")
                        tool = str(data.get("tool", "stift"))
                        color = str(data.get("color", "#ef4444"))
                        if tool not in ("stift", "marker", "radierer") or not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
                            raise ValueError("Werkzeug")
                        req.update(x=x, y=y, tool=tool, color=color)
                    server.request.emit(req)
                elif u.path == "/api/mouse":  # Handy als Touchpad
                    if "click" in data:
                        button = str(data["click"])
                        if button not in ("links", "rechts"):
                            raise ValueError("Taste")
                        server.request.emit({"kind": "mouse", "click": button})
                    elif "scroll" in data:
                        server.request.emit({"kind": "mouse", "scroll": max(-10, min(10, int(data["scroll"])))})
                    else:
                        dx, dy = float(data.get("dx", 0)), float(data.get("dy", 0))
                        if abs(dx) > 2000 or abs(dy) > 2000:
                            raise ValueError("zu weit")
                        server.request.emit({"kind": "mouse", "dx": dx, "dy": dy})
                elif u.path == "/api/cmd":
                    cmd = str(data.get("cmd", ""))
                    if not (cmd in ALLOWED_COMMANDS or cmd.startswith("szene:")
                            or re.fullmatch(r"lautstaerke:\d{1,3}", cmd) or re.fullmatch(r"timer:\d{1,5}", cmd)
                            or re.fullmatch(r"taste:(weiter|zurueck|rechts|links|start|ende|schwarz|leer)", cmd)):
                        self._json(400, {"error": "Unbekannter Befehl"})
                        return
                    server.request.emit({"kind": "cmd", "cmd": cmd})
                else:
                    self._json(404, {"error": "Nicht gefunden"})
                    return
                self._json(200, {"ok": True})
            except (ValueError, TypeError, json.JSONDecodeError):
                self._json(400, {"error": "Ungültige Anfrage"})

        def _upload(self, name: str):
            try:
                size = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                size = 0
            if size <= 0:
                self.close_connection = True
                self._json(400, {"error": "Leere Datei"})
                return
            if size > MAX_UPLOAD:
                self.close_connection = True
                self._json(413, {"error": "Datei zu groß (höchstens 2 GB)"})
                return
            filename = safe_name(name, self.headers.get("Content-Type", ""))
            ext = Path(filename).suffix
            if ext not in IMAGE_EXT | VIDEO_EXT:
                self.close_connection = True
                self._json(415, {"error": "Nur Fotos und Videos"})
                return
            folder = upload_dir()
            folder.mkdir(parents=True, exist_ok=True)
            target = folder / filename
            left = size
            try:
                with open(target, "wb") as f:
                    while left > 0:
                        chunk = self.rfile.read(min(left, 1 << 20))
                        if not chunk:
                            raise ConnectionError("abgebrochen")
                        f.write(chunk)
                        left -= len(chunk)
            except (OSError, ConnectionError):
                target.unlink(missing_ok=True)
                self.close_connection = True
                return
            cleanup(folder)
            kind = "video" if ext in VIDEO_EXT else "image"
            server.request.emit({"kind": "file", "type": kind, "path": str(target)})
            self._json(200, {"ok": True, "type": kind})

    return Handler


_server: CastServer | None = None


def cast_server(config=None) -> CastServer:
    global _server
    if _server is None:
        if config is None:
            raise RuntimeError("AluCast ist noch nicht eingerichtet")
        _server = CastServer(config)
    elif config is not None:
        _server.config = config
    return _server
