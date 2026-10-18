"""Bildschirm an andere Geräte senden: Chromecast und AirPlay (Apple TV, AirPlay-Fernseher).

Weg: AluPC kodiert das Bild von Monitor 2 live als HLS-Video (H.264 mit PyAV/libx264) und stellt es über den
eigenen Webserver bereit – unter /bildschirm/<Zufallsschlüssel>/… (ohne Schlüssel: 404). Das Zielgerät holt den
Stream selbst ab:
* Chromecast: Standard-Mediaplayer von Google (pychromecast), als LIVE-Stream.
* AirPlay: „AirPlay-Video“ (pyatv play_url) – so, wie ein iPhone ein Video an den Fernseher schickt. Apple TV
  verlangt einmal eine Kopplung mit PIN (steht auf dem Fernseher). Echte Bildschirm-Spiegelung (wie vom Mac) geht
  nicht: dafür braucht es Apples Verschlüsselung.
Grenzen: einige Sekunden Verzögerung (HLS), kein Ton.
"""

from __future__ import annotations

import asyncio
import fractions
import secrets
import shutil
import socket
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal

SIZES = {"720p": (1280, 720), "1080p": (1920, 1080), "540p": (960, 540)}
CHROMECAST, AIRPLAY = "chromecast", "airplay"
SERVICE_TYPES = {"_googlecast._tcp.local.": CHROMECAST, "_airplay._tcp.local.": AIRPLAY}
DEFAULT_PORTS = {CHROMECAST: 8009, AIRPLAY: 7000}
LABEL = {CHROMECAST: "Chromecast", AIRPLAY: "AirPlay"}


@dataclass
class Device:
    kind: str  # CHROMECAST / AIRPLAY
    name: str
    host: str
    port: int
    ident: str = ""
    model: str = ""
    props: dict = field(default_factory=dict)

    @property
    def key(self) -> str:
        return f"{self.kind}:{self.ident or self.host}"

    def label(self) -> str:
        extra = f" · {self.model}" if self.model and self.model != LABEL[self.kind] else ""
        return f"{self.name} ({LABEL[self.kind]}{extra})"


# --------------------------------------------------------------------------- Suche
def _own_addresses() -> set[str]:
    from .cast_server import network_addresses

    try:
        return {a[0] for a in network_addresses()} | {"127.0.0.1"}
    except Exception:  # noqa: BLE001
        return {"127.0.0.1"}


def device_from_info(kind: str, info) -> Device | None:
    """zeroconf.ServiceInfo → Device ("" bei unbrauchbaren Einträgen)."""
    addresses = [a for a in info.parsed_addresses() if ":" not in a]  # nur IPv4
    if not addresses or not info.port:
        return None
    props = {}
    for k, v in (info.properties or {}).items():
        try:
            props[k.decode()] = v.decode() if isinstance(v, bytes) else ("" if v is None else str(v))
        except UnicodeDecodeError:
            continue
    service = info.name.split("._", 1)[0]
    if kind == CHROMECAST:
        name, ident, model = props.get("fn") or service, props.get("id", ""), props.get("md", "")
    else:
        name, ident, model = service, props.get("deviceid") or props.get("pk", "")[:16], props.get("model", "")
    return Device(kind, name, addresses[0], int(info.port), ident, model, props)


def discover(timeout: float = 4.0, zc=None, skip_own: bool = True) -> list[Device]:
    """Chromecasts und AirPlay-Empfänger im Netz suchen (mDNS). AluPCs eigener AirPlay-Empfang fällt raus."""
    from zeroconf import ServiceBrowser, Zeroconf

    own = _own_addresses() if skip_own else set()
    zconf = zc or Zeroconf()
    names: list[tuple[str, str]] = []

    class Listener:
        def add_service(self, _zc, type_, name):
            if (type_, name) not in names:
                names.append((type_, name))

        def update_service(self, *_a):
            pass

        def remove_service(self, *_a):
            pass

    browsers = [ServiceBrowser(zconf, t, Listener()) for t in SERVICE_TYPES]
    try:
        time.sleep(timeout)
        found: dict[str, Device] = {}
        for type_, name in list(names):
            info = zconf.get_service_info(type_, name, timeout=2000)
            dev = device_from_info(SERVICE_TYPES[type_], info) if info else None
            if dev is None or (dev.kind == AIRPLAY and dev.host in own):
                continue
            found.setdefault(dev.key, dev)
        return sorted(found.values(), key=lambda d: (d.kind, d.name.lower()))
    finally:
        for b in browsers:
            b.cancel()
        if zc is None:
            zconf.close()


def route_ip(host: str) -> str:
    """Eigene Adresse, über die `host` erreichbar ist (für die Stream-Adresse)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect((host, 9))
        return s.getsockname()[0]
    except OSError:
        from .cast_server import local_ip

        return local_ip()
    finally:
        s.close()


# --------------------------------------------------------------------------- HLS
class HlsStream:
    """Kodiert das jeweils neueste Bild in festem Takt als HLS (0,5-s-Stücke) in einen Ordner."""

    def __init__(self, width: int, height: int, fps: int):
        self.width, self.height, self.fps = width, height, max(5, min(30, fps))
        self.token = secrets.token_urlsafe(16)
        self.dir = Path(tempfile.mkdtemp(prefix="alupc-senden-"))
        self.error = ""
        self.frames = 0
        self._frame: bytes | None = None
        self._lock = threading.Lock()
        self._running = False
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._loop, name="alupc-senden-hls", daemon=True)
        self._thread.start()

    def push(self, rgb: bytes) -> None:
        """Ein Bild (RGB888, genau width×height×3 Bytes)."""
        with self._lock:
            self._frame = rgb

    def ready(self) -> bool:
        return (self.dir / "stream.m3u8").is_file()

    def file(self, name: str) -> tuple[bytes, str] | None:
        """Datei für den Webserver (nur stream.m3u8 und die .ts-Stücke)."""
        if name == "stream.m3u8":
            ctype = "application/vnd.apple.mpegurl"
        elif name.startswith("stream") and name.endswith(".ts") and name[6:-3].isdigit():
            ctype = "video/mp2t"
        else:
            return None
        try:
            return (self.dir / name).read_bytes(), ctype
        except OSError:
            return None

    def stop(self) -> None:
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=5)
        shutil.rmtree(self.dir, ignore_errors=True)

    def _loop(self) -> None:
        import av
        import numpy as np

        try:
            out = av.open(str(self.dir / "stream.m3u8"), "w", format="hls", options={
                "hls_time": "0.5", "hls_list_size": "4", "hls_segment_type": "mpegts",  # kurze Stücke = wenig Verzögerung
                "hls_flags": "delete_segments+independent_segments+omit_endlist+temp_file"})
            st = out.add_stream("libx264", rate=self.fps)
            st.width, st.height, st.pix_fmt = self.width, self.height, "yuv420p"
            st.options = {"preset": "veryfast", "tune": "zerolatency", "profile": "main", "crf": "23",
                          "g": str(max(1, self.fps // 2)), "keyint_min": str(max(1, self.fps // 2)), "sc_threshold": "0"}
        except Exception as exc:  # noqa: BLE001 – PyAV/libx264 fehlt
            self.error = f"Video-Kodierer ging nicht: {exc}"
            self._running = False
            return
        black = np.zeros((self.height, self.width, 3), np.uint8)
        arr, step, nxt, pts = black, 1.0 / self.fps, time.monotonic(), 0
        try:
            while self._running:
                with self._lock:
                    data, self._frame = self._frame, None
                if data is not None and len(data) == self.width * self.height * 3:
                    arr = np.frombuffer(data, np.uint8).reshape(self.height, self.width, 3)
                frame = av.VideoFrame.from_ndarray(arr, format="rgb24")
                frame.pts, frame.time_base = pts, fractions.Fraction(1, self.fps)
                for packet in st.encode(frame):
                    out.mux(packet)
                pts += 1
                self.frames += 1
                nxt += step
                wait = nxt - time.monotonic()
                if wait > 0:
                    time.sleep(wait)
                elif wait < -1:  # zu langsam → Takt neu ansetzen statt nachzuholen
                    nxt = time.monotonic()
        except Exception as exc:  # noqa: BLE001
            self.error = f"Kodieren ging nicht: {exc}"
        finally:
            try:
                for packet in st.encode():
                    out.mux(packet)
                out.close()
            except Exception:  # noqa: BLE001
                pass


# --------------------------------------------------------------------------- Ziele
DEFAULT_MEDIA_RECEIVER = "CC1AD845"


class ChromecastTarget:
    def __init__(self, dev: Device):
        self.dev = dev
        self.cast = None

    def prepare(self, stop: threading.Event, phase=lambda _t: None) -> None:
        """Verbinden und den Mediaplayer auf dem Fernseher starten – läuft parallel zum Anlaufen des Streams."""
        import uuid

        import pychromecast

        try:
            ident = uuid.UUID(self.dev.ident) if self.dev.ident else uuid.uuid4()
        except ValueError:
            ident = uuid.uuid4()
        self.cast = pychromecast.get_chromecast_from_host(
            (self.dev.host, self.dev.port, ident, self.dev.model or None, self.dev.name), tries=2, timeout=10)
        self.cast.wait(timeout=15)
        if stop.is_set():
            return
        phase("Starte Player auf dem Fernseher …")
        self.cast.start_app(DEFAULT_MEDIA_RECEIVER, timeout=20)

    def play(self, url: str, stop: threading.Event) -> str:
        if self.cast is None:
            self.prepare(stop)
        mc = self.cast.media_controller
        mc.play_media(url, "application/x-mpegURL", title="AluPC – Bildschirm", stream_type="LIVE")
        mc.block_until_active(timeout=20)
        if not mc.is_active:
            return "Chromecast hat den Stream nicht angenommen."
        return ""

    def alive(self) -> str:
        """"" = läuft; sonst Grund, warum nicht mehr."""
        mc = self.cast.media_controller if self.cast else None
        st = mc.status if mc else None
        if st is not None and st.player_state == "IDLE" and st.idle_reason in ("ERROR", "INTERRUPTED"):
            return "Chromecast: Wiedergabe abgebrochen" + (" (anderes Gerät hat übernommen)"
                                                           if st.idle_reason == "INTERRUPTED" else "")
        return ""

    def close(self) -> None:
        if self.cast is None:
            return
        try:
            self.cast.media_controller.stop()
            self.cast.quit_app()
        except Exception:  # noqa: BLE001
            pass
        try:
            self.cast.disconnect(timeout=3)
        except Exception:  # noqa: BLE001
            pass
        self.cast = None


class AirPlayTarget:
    """AirPlay-Video über pyatv in einer eigenen asyncio-Schleife (eigener Thread)."""

    def __init__(self, dev: Device, credentials: str = ""):
        self.dev = dev
        self.credentials = credentials
        self.loop: asyncio.AbstractEventLoop | None = None
        self.atv = None
        self.task = None
        self.ended = ""

    def _conf(self):
        import pyatv
        from pyatv.const import Protocol

        conf = pyatv.conf.AppleTV(self.dev.host, self.dev.name)
        conf.add_service(pyatv.conf.ManualService(self.dev.ident or self.dev.host, Protocol.AirPlay, self.dev.port,
                                                  dict(self.dev.props), credentials=self.credentials or None))
        return conf

    def play(self, url: str, stop: threading.Event) -> str:
        import pyatv

        self.loop = asyncio.new_event_loop()
        ready = threading.Event()
        result = {"why": ""}

        async def run():
            try:
                self.atv = await pyatv.connect(self._conf(), self.loop)
                self.task = asyncio.ensure_future(self.atv.stream.play_url(url))
                await asyncio.sleep(2.0)  # Gerät nimmt an oder lehnt sofort ab
                if self.task.done() and self.task.exception() is not None:
                    raise self.task.exception()
            except Exception as exc:  # noqa: BLE001
                result["why"] = _airplay_error(exc)
            ready.set()
            if result["why"]:
                return
            try:
                await self.task
                self.ended = "AirPlay: Wiedergabe beendet (am Fernseher gestoppt?)"
            except asyncio.CancelledError:
                pass
            except Exception as exc:  # noqa: BLE001
                self.ended = _airplay_error(exc)

        async def main():
            try:
                await run()
            finally:
                if self.atv is not None:
                    await asyncio.gather(*self.atv.close(), return_exceptions=True)

        def thread():
            asyncio.set_event_loop(self.loop)
            self.loop.run_until_complete(main())
            self.loop.close()

        threading.Thread(target=thread, name="alupc-senden-airplay", daemon=True).start()
        ready.wait(40)
        return result["why"]

    def alive(self) -> str:
        return self.ended

    def close(self) -> None:
        loop = self.loop
        if loop is not None and self.task is not None and not loop.is_closed():
            try:
                loop.call_soon_threadsafe(self.task.cancel)
            except RuntimeError:
                pass
        _http_stop(self.dev)


def _http_stop(dev: Device) -> None:
    """AirPlay-Video beenden (POST /stop) – klappt bei Geräten ohne Kopplung, sonst endet es mit der Verbindung."""
    try:
        with socket.create_connection((dev.host, dev.port), timeout=2) as s:
            s.sendall(f"POST /stop HTTP/1.1\r\nHost: {dev.host}:{dev.port}\r\nContent-Length: 0\r\n\r\n".encode())
            s.recv(256)
    except OSError:
        pass


def _airplay_error(exc: Exception) -> str:
    name = type(exc).__name__
    text = str(exc) or name
    if "Auth" in name or "auth" in text.lower() or "403" in text or "401" in text or "470" in text:
        return "PIN"
    return f"AirPlay ging nicht: {text}"


async def _pair_begin(dev: Device, loop):
    import pyatv
    from pyatv.const import Protocol

    conf = pyatv.conf.AppleTV(dev.host, dev.name)
    conf.add_service(pyatv.conf.ManualService(dev.ident or dev.host, Protocol.AirPlay, dev.port, dict(dev.props)))
    handler = await pyatv.pair(conf, Protocol.AirPlay, loop)
    await handler.begin()
    return handler


# --------------------------------------------------------------------------- Steuerung
class ScreenSender(QObject):
    """Senden an ein Gerät. Signale kommen im Qt-Hauptthread an."""

    changed = Signal()
    devices_found = Signal(list)
    pin_needed = Signal(str)  # Gerätename – PIN steht auf dem Fernseher
    _done = Signal(str, str)  # (Gerät-Schlüssel, Fehler)
    _found = Signal(list)
    _pair_failed = Signal(str)
    _phase = Signal(str, str)  # Gerät, Schritt beim Verbinden

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.devices: list[Device] = []
        self.target_dev: Device | None = None
        self.state = "aus"  # aus / suche / verbinde / läuft / fehler
        self.error = ""
        self.stream: HlsStream | None = None
        self._target = None
        self._stop = threading.Event()
        self._pairing = None  # (Gerät, Handler, Schleife)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._grab)
        self._watch = QTimer(self)
        self._watch.setInterval(2000)
        self._watch.timeout.connect(self._check)
        self._done.connect(self._connected)
        self._phase.connect(self._on_phase)
        self.phase = ""
        self._found.connect(self._on_found)
        self._pair_failed.connect(self._fail)

    def cfg(self) -> dict:
        return {"size": "720p", "fps": 20, "airplay": {}, "manual": [], **(self.controller.config.data.get("senden") or {})}

    def _save(self, **kw) -> None:
        self.controller.config["senden"] = {**self.cfg(), **kw}

    @property
    def running(self) -> bool:
        return self.state in ("verbinde", "läuft")

    def describe(self) -> str:
        if self.state == "läuft" and self.target_dev:
            return f"Sendet an {self.target_dev.name}"
        if self.state == "verbinde" and self.target_dev:
            return f"{self.target_dev.name}: {self.phase}" if self.phase else f"Verbinde mit {self.target_dev.name} …"
        if self.state == "suche":
            return "Suche Geräte …"
        return self.error or "Aus"

    # ---- Geräte
    def manual_devices(self) -> list[Device]:
        out = []
        for m in self.cfg().get("manual") or []:
            kind = m.get("kind") if m.get("kind") in DEFAULT_PORTS else CHROMECAST
            out.append(Device(kind, m.get("name") or m.get("host", "?"), m.get("host", ""),
                              int(m.get("port") or DEFAULT_PORTS[kind]), m.get("host", "")))
        return [d for d in out if d.host]

    def add_manual(self, kind: str, host: str, name: str = "") -> Device:
        host = host.strip()
        manual = [m for m in self.cfg().get("manual") or [] if m.get("host") != host]
        manual.append({"kind": kind, "host": host, "name": name.strip() or host, "port": DEFAULT_PORTS[kind]})
        self._save(manual=manual[-10:])
        dev = Device(kind, name.strip() or host, host, DEFAULT_PORTS[kind], host)
        self.devices = [d for d in self.devices if d.key != dev.key] + [dev]
        self.devices_found.emit(list(self.devices))
        return dev

    def scan(self) -> None:
        if self.state == "suche":
            return
        prev = self.state
        self.state = "suche"
        self.changed.emit()

        def work():
            try:
                found = discover()
            except Exception:  # noqa: BLE001 – kein Netz/mDNS blockiert
                found = []
            self._found.emit([prev, found])

        threading.Thread(target=work, name="alupc-senden-suche", daemon=True).start()

    def _on_found(self, data: list) -> None:
        prev, found = data
        if self.state == "suche":
            self.state = prev if prev != "suche" else "aus"
        keys = {d.key for d in found}
        self.devices = found + [d for d in self.manual_devices() if d.key not in keys]
        self.devices_found.emit(list(self.devices))
        self.changed.emit()

    # ---- an/aus
    def start(self, dev: Device) -> tuple[bool, str]:
        if self.running:
            self.stop()
        try:
            import av  # noqa: F401

            if dev.kind == CHROMECAST:
                import pychromecast  # noqa: F401
            else:
                import pyatv  # noqa: F401
        except ImportError as exc:
            return self._fail(f"Fehlt in dieser AluPC-Version: {exc.name}")
        c = self.controller
        if not c.cast.start():
            return self._fail("AluPCs Webserver startet nicht – Port belegt?")
        cfg = self.cfg()
        w, h = SIZES.get(cfg["size"], SIZES["720p"])
        self.stream = HlsStream(w, h, int(cfg["fps"]))
        c.cast.screen_stream = self.stream
        self.stream.start()
        self._timer.start(int(1000 / self.stream.fps))
        self._grab()  # gleich ein Bild, nicht erst schwarz
        self.target_dev, self.error, self.state, self.phase = dev, "", "verbinde", ""
        self._stop.clear()
        self.changed.emit()
        from .cast_server import active_port

        url = f"http://{route_ip(dev.host)}:{active_port()}/bildschirm/{self.stream.token}/stream.m3u8"
        creds = (cfg.get("airplay") or {}).get(dev.key, "")
        target = ChromecastTarget(dev) if dev.kind == CHROMECAST else AirPlayTarget(dev, creds)
        self._target = target

        def work():
            from .hotspot import ensure_firewall_rule

            # Firewall, Verbindung + Player-Start und das erste Stück des Streams laufen gleichzeitig an
            fw: dict = {}
            fw_thread = threading.Thread(target=lambda: fw.update(note=ensure_firewall_rule()),
                                         name="alupc-senden-firewall", daemon=True)
            fw_thread.start()
            try:
                prepare = getattr(target, "prepare", None)
                if prepare is not None:
                    prepare(self._stop, lambda text: self._phase.emit(dev.key, text))
                end = time.monotonic() + 8
                if not self.stream.ready():
                    self._phase.emit(dev.key, "Warte auf das erste Bild …")
                while not self.stream.ready() and time.monotonic() < end and not self._stop.is_set():
                    time.sleep(0.05)
                fw_thread.join(timeout=200)  # Windows: der Fernseher braucht die Freigabe, bevor er den Stream holt
                if self._stop.is_set():
                    return
                if self.stream.error:
                    why = self.stream.error
                else:
                    self._phase.emit(dev.key, "Fernseher puffert …")
                    why = target.play(url, self._stop)
            except Exception as exc:  # noqa: BLE001
                why = f"{LABEL[dev.kind]} ging nicht: {exc}"
            note = fw.get("note", "")
            if why and note:
                why += " · " + note
            self._done.emit(dev.key, why)

        threading.Thread(target=work, name="alupc-senden", daemon=True).start()
        return True, ""

    def _on_phase(self, key: str, text: str) -> None:
        if self.state == "verbinde" and self.target_dev is not None and self.target_dev.key == key:
            self.phase = text
            self.changed.emit()

    def _connected(self, key: str, why: str) -> None:
        if self.target_dev is None or self.target_dev.key != key or self.state != "verbinde":
            return
        if why == "PIN":
            dev = self.target_dev
            self.stop()
            self.error = f"{dev.name} möchte eine PIN – sie steht gleich auf dem Fernseher."
            self.changed.emit()
            self._begin_pairing(dev)
            return
        if why:
            self.stop()
            self._fail(why)
            return
        self.state = "läuft"
        self._save(last=key)
        self._watch.start()
        self.changed.emit()
        self.controller.message.emit(f"Bildschirm wird an {self.target_dev.name} gesendet (kurz verzögert).")

    def _check(self) -> None:
        if self.state != "läuft":
            return
        why = (self.stream.error if self.stream else "") or (self._target.alive() if self._target else "")
        if why:
            self.stop()
            self._fail(why)

    def _fail(self, why: str) -> tuple[bool, str]:
        self.state, self.error = "fehler", why
        self.changed.emit()
        self.controller.message.emit(why)
        return False, why

    def stop(self) -> None:
        self._stop.set()
        self._timer.stop()
        self._watch.stop()
        target, self._target = self._target, None
        if target is not None:
            threading.Thread(target=target.close, name="alupc-senden-stop", daemon=True).start()
        if self.stream is not None:
            if getattr(self.controller.cast, "screen_stream", None) is self.stream:
                self.controller.cast.screen_stream = None
            stream, self.stream = self.stream, None
            threading.Thread(target=stream.stop, name="alupc-senden-hls-stop", daemon=True).start()
        if self.state != "fehler":
            self.state = "aus"
        self.changed.emit()

    def _grab(self) -> None:
        if self.stream is None:
            return
        img = self.controller.vcam.frame_image(self.stream.width, self.stream.height)
        bpl, w, h = img.bytesPerLine(), self.stream.width, self.stream.height
        raw = bytes(img.constBits())[: bpl * h]
        if bpl != w * 3:
            raw = b"".join(raw[y * bpl: y * bpl + w * 3] for y in range(h))
        self.stream.push(raw)

    # ---- AirPlay-Kopplung (Apple TV: PIN auf dem Fernseher)
    def _begin_pairing(self, dev: Device) -> None:
        loop = asyncio.new_event_loop()
        threading.Thread(target=loop.run_forever, name="alupc-senden-pin", daemon=True).start()
        fut = asyncio.run_coroutine_threadsafe(_pair_begin(dev, loop), loop)

        def started(f):
            try:
                self._pairing = (dev, f.result(), loop)
                self.pin_needed.emit(dev.name)
            except Exception as exc:  # noqa: BLE001
                loop.call_soon_threadsafe(loop.stop)
                self._pair_failed.emit(f"Kopplung mit {dev.name} ging nicht: {exc}")
        fut.add_done_callback(started)

    def submit_pin(self, pin: str) -> tuple[bool, str]:
        if self._pairing is None:
            return False, "Keine Kopplung offen."
        dev, handler, loop = self._pairing
        self._pairing = None

        async def finish():
            handler.pin(pin.strip())
            await handler.finish()
            creds = handler.service.credentials if handler.has_paired else ""
            await handler.close()
            return creds

        try:
            creds = asyncio.run_coroutine_threadsafe(finish(), loop).result(30)
        except Exception as exc:  # noqa: BLE001
            creds, why = "", f"PIN falsch oder abgelaufen ({exc})"
        else:
            why = "" if creds else "PIN falsch oder abgelaufen"
        loop.call_soon_threadsafe(loop.stop)
        if not creds:
            return self._fail(why)
        self._save(airplay={**(self.cfg().get("airplay") or {}), dev.key: creds})
        return self.start(dev)

    def cancel_pin(self) -> None:
        if self._pairing is not None:
            _dev, handler, loop = self._pairing
            self._pairing = None
            asyncio.run_coroutine_threadsafe(handler.close(), loop)
            loop.call_soon_threadsafe(loop.stop)
