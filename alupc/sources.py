"""Quellen, die auf Monitor 2 angezeigt werden: Kamera, Bildschirm, Programm, Website, …

Jede Quelle ist ein QWidget mit einer Methode `stop()`. Video-Quellen zeichnen ihre
Bilder selbst (über QVideoSink); so funktionieren Standbild und Bild-in-Bild
über ein einfaches `grab()`.
"""

from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import QRectF, Qt, QTimer, QUrl
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QGuiApplication,
    QImage,
    QImageReader,
    QPainter,
    QPixmap,
    QTransform,
)
from PySide6.QtMultimedia import (
    QAudioOutput,
    QCamera,
    QMediaCaptureSession,
    QMediaDevices,
    QMediaPlayer,
    QScreenCapture,
    QVideoSink,
    QWindowCapture,
)
from PySide6.QtWidgets import QWidget

from .scenes import layout_slots

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".tif", ".tiff"}
MAX_SCENE_DEPTH = 4


class FrameView(QWidget):
    """Zeigt ein Bild (seitenverhältnistreu) oder eine Meldung."""

    def __init__(self, fit: str = "contain", parent=None):
        super().__init__(parent)
        self.fit = fit
        self._image: QImage | None = None
        self._message = ""
        self.setAttribute(Qt.WA_OpaquePaintEvent)

    def set_image(self, image: QImage | QPixmap | None) -> None:
        if isinstance(image, QPixmap):
            image = image.toImage()
        self._image = image if image is not None and not image.isNull() else None
        if self._image is not None:
            self._message = ""
        self.update()

    def image(self) -> QImage | None:
        return self._image

    def set_message(self, text: str) -> None:
        self._message = text
        self.update()

    def stop(self) -> None:
        pass

    def paintEvent(self, _event):
        p = QPainter(self)
        p.fillRect(self.rect(), Qt.black)
        if self._image is not None:
            p.setRenderHint(QPainter.SmoothPixmapTransform)
            p.drawImage(fit_rect(self._image.width(), self._image.height(),
                                 self.width(), self.height(), self.fit), self._image)
        elif self._message:
            p.setPen(QColor("#bbbbbb"))
            font = QFont()
            font.setPixelSize(max(12, min(28, self.height() // 18)))
            p.setFont(font)
            p.drawText(self.rect().adjusted(20, 20, -20, -20), Qt.AlignCenter | Qt.TextWordWrap, self._message)
        p.end()


def fit_rect(iw: int, ih: int, w: int, h: int, fit: str = "contain") -> QRectF:
    if iw <= 0 or ih <= 0 or w <= 0 or h <= 0:
        return QRectF(0, 0, w, h)
    if fit == "stretch":
        return QRectF(0, 0, w, h)
    scale = min(w / iw, h / ih) if fit == "contain" else max(w / iw, h / ih)
    sw, sh = iw * scale, ih * scale
    return QRectF((w - sw) / 2, (h - sh) / 2, sw, sh)


class SinkView(FrameView):
    """FrameView, die Bilder aus einem QVideoSink bekommt.

    Optimierung: Ein Videobild wird erst dann in ein QImage umgewandelt, wenn es wirklich
    gezeichnet (oder für Standbild/Bild-in-Bild abgefragt) wird. Kommen mehr Bilder, als der
    Monitor anzeigen kann, werden die überzähligen gar nicht erst umgewandelt.
    """

    def __init__(self, fit="contain", parent=None):
        super().__init__(fit, parent)
        self.sink = QVideoSink(self)
        self.sink.videoFrameChanged.connect(self._on_frame)
        self._pending = None

    def _on_frame(self, frame):
        if frame.isValid():
            self._pending = frame
            self._message = ""
            if self.isVisible():
                self.update()

    def _convert(self):
        if self._pending is not None:
            image = self._pending.toImage()
            self._pending = None
            if not image.isNull():
                self._image = image

    def image(self):
        self._convert()
        return self._image

    def paintEvent(self, event):
        self._convert()
        super().paintEvent(event)


# --------------------------------------------------------------------------- Kamera
def find_camera(device_id: str | None):
    devices = QMediaDevices.videoInputs()
    for dev in devices:
        if bytes(dev.id()).decode(errors="replace") == device_id:
            return dev
    return devices[0] if devices and not device_id else None


def camera_id(dev) -> str:
    return bytes(dev.id()).decode(errors="replace")


# Einstellungen pro Kamera (Zoom, Ausschnitt, Spiegeln, Drehen, Belichtung) – vom Controller aus
# config["camera"] gesetzt, Schlüssel = Kamera-ID
camera_settings: dict[str, dict] = {}
CAMERA_DEFAULTS = {"zoom": 1.0, "x": 0.5, "y": 0.5, "mirror": False, "rotate": 0, "exposure": 0.0,
                   "quality": "hoch"}
MAX_ZOOM = 5.0


def camera_options(device_id: str) -> dict:
    return {**CAMERA_DEFAULTS, **camera_settings.get(device_id, {})}


def zoom_rect(w: int, h: int, zoom: float, x: float, y: float) -> tuple[int, int, int, int]:
    """Ausschnitt (links, oben, Breite, Höhe) für einen digitalen Zoom um den Punkt (x, y) (0…1)."""
    zoom = max(1.0, min(MAX_ZOOM, float(zoom)))
    cw, ch = max(1, round(w / zoom)), max(1, round(h / zoom))
    left = round(min(max(x * w - cw / 2, 0), w - cw))
    top = round(min(max(y * h - ch / 2, 0), h - ch))
    return left, top, cw, ch


def clamp_center(zoom: float, x: float, y: float) -> tuple[float, float]:
    """Mittelpunkt so begrenzen, dass der Ausschnitt im Bild bleibt."""
    half = 0.5 / max(1.0, zoom)
    return min(max(x, half), 1 - half), min(max(y, half), 1 - half)


def pan_to_source(dx: float, dy: float, rotate: int, mirror: bool) -> tuple[float, float]:
    """Verschieben „wie man es sieht“ (rechts/oben im angezeigten Bild) → Richtung im Kamerabild."""
    for _ in range((-int(rotate) // 90) % 4):  # Drehung zurücknehmen (je 90° im Uhrzeigersinn)
        dx, dy = -dy, dx
    return (-dx if mirror else dx), dy


def best_camera_format(formats, max_pixels: int = 1920 * 1080):
    """Schärfstes Format bis Full HD mit flüssiger Bildrate (≥ 24 Bilder/s) – gut für den Zoom."""
    def size(f):
        r = f.resolution()
        return r.width() * r.height()

    smooth = [f for f in formats if f.maxFrameRate() >= 24 and 0 < size(f) <= max_pixels]
    pool = smooth or [f for f in formats if 0 < size(f) <= max_pixels] or list(formats)
    if not pool:
        return None
    return max(pool, key=lambda f: (size(f), f.maxFrameRate()))


class CameraSource(SinkView):
    def __init__(self, cfg, parent=None):
        super().__init__(cfg.get("fit", "contain"), parent)
        self.session = QMediaCaptureSession(self)
        self.camera = None
        self.device_id = ""
        self.name = cfg.get("name", "") or "Kamera"
        self._raw: QImage | None = None
        self._digital = 1.0
        dev = find_camera(cfg.get("device_id"))
        if dev is None:
            self.set_message(f"Kamera „{cfg.get('name', '')}“ nicht gefunden.")
            return
        self.device_id = camera_id(dev)
        self.name = dev.description()
        self.camera = QCamera(dev, self)
        self.camera.errorOccurred.connect(lambda _e, text: self.set_message(f"Kamerafehler: {text}"))
        if self.options()["quality"] == "hoch":
            fmt = best_camera_format(dev.videoFormats())
            if fmt is not None:
                self.camera.setCameraFormat(fmt)
        self.session.setCamera(self.camera)
        self.session.setVideoSink(self.sink)
        self.set_message("Kamera startet …")
        self.camera.activeChanged.connect(lambda _a: self.apply_options())
        self.camera.start()
        self.apply_options()

    # ------------------------------------------------------------ Optionen
    def options(self) -> dict:
        return camera_options(self.device_id)

    def hardware_zoom_max(self) -> float:
        try:
            return float(self.camera.maximumZoomFactor()) if self.camera else 1.0
        except (AttributeError, RuntimeError):
            return 1.0

    def supports_exposure(self) -> bool:
        try:
            return bool(self.camera and self.camera.supportedFeatures() & QCamera.Feature.ExposureCompensation)
        except (AttributeError, RuntimeError, TypeError):
            return False

    def apply_options(self) -> None:
        """Nach jeder Änderung: Hardware-Zoom/Belichtung setzen, Rest digital, Bild neu berechnen."""
        o = self.options()
        zoom = max(1.0, min(MAX_ZOOM, float(o["zoom"])))
        hw = 1.0
        if self.camera is not None and self.hardware_zoom_max() > 1.01:
            hw = min(zoom, self.hardware_zoom_max())
            self.camera.setZoomFactor(hw)
        self._digital = zoom / hw
        if self.supports_exposure():
            self.camera.setExposureCompensation(float(o["exposure"]))
        if self._raw is not None:
            self._image = self._transform(self._raw)
        self.update()

    def _transform(self, img: QImage) -> QImage:
        o = self.options()
        if self._digital > 1.001:
            img = img.copy(*zoom_rect(img.width(), img.height(), self._digital, o["x"], o["y"]))
        if o["mirror"]:
            img = img.flipped(Qt.Horizontal) if hasattr(img, "flipped") else img.mirrored(True, False)
        rotate = int(o["rotate"]) % 360
        if rotate:
            img = img.transformed(QTransform().rotate(rotate))
        return img

    def _convert(self):
        if self._pending is None:
            return
        frame, self._pending = self._pending, None
        image = frame.toImage()
        if not image.isNull():
            self._raw = image
            self._image = self._transform(image)

    def stop(self):
        if self.camera:
            self.camera.stop()


# --------------------------------------------------------------------------- Bildschirm
def find_screen(name: str | None):
    for screen in QGuiApplication.screens():
        if screen.name() == name:
            return screen
    return None


class ScreenSource(SinkView):
    """Nimmt einen ganzen Monitor auf (z. B. für Spiegeln und Bild-in-Bild).

    KDE/Wayland: wenn erlaubt direkt über KWin – ohne Fenster „Welchen Bildschirm teilen?“.
    Sonst über Qt (Windows, X11 ohne Nachfrage; Wayland mit Nachfrage des Systems).
    """

    def __init__(self, cfg, parent=None):
        super().__init__(cfg.get("fit", "contain"), parent)
        screen = find_screen(cfg.get("screen_name")) or QGuiApplication.primaryScreen()
        self._cursor_on = False
        self.method = "qt"
        self.feed = None
        self.capture = None
        self._screen = screen
        if screen is not None and _kwin_allowed(screen.name()):
            self._start_kwin(screen.name(), int(cfg.get("fps", 30)))
        else:
            self._start_qt(screen)

    def _start_kwin(self, name: str, fps: int):
        from .platform.kwin_capture import KWinScreenFeed

        self.method = "kwin"
        self.feed = KWinScreenFeed(name, fps, cursor=screen_settings["cursor"], parent=self)
        self.feed.frame.connect(self._kwin_frame)
        self.feed.failed.connect(self._kwin_failed)
        self.set_message("Bildschirmaufnahme startet …")
        self.feed.start()

    def _kwin_frame(self, image):
        self._pending = None
        self._image = image
        self._message = ""
        if self.feed is not None:
            self.feed.frame_taken()
        self.update()

    def _kwin_failed(self, text):
        # KWin-Weg geht nicht (mehr) → normale Aufnahme versuchen
        self.feed = None
        self._start_qt(self._screen)

    def _start_qt(self, screen):
        self.method = "qt"
        if screen is None:
            screen = QGuiApplication.primaryScreen()
        self.session = QMediaCaptureSession(self)
        self.capture = QScreenCapture(self)
        self.capture.setScreen(screen)
        self.capture.errorOccurred.connect(self._error)
        self.session.setScreenCapture(self.capture)
        self.session.setVideoSink(self.sink)
        self.set_message("Bildschirmaufnahme startet … (evtl. Freigabe bestätigen)")
        self.capture.start()
        # Die Aufnahme unter Windows/X11 enthält den Mauszeiger nicht → selbst einzeichnen
        from .platform.linux_display import is_wayland

        if not is_wayland() and not self._cursor_on:
            from .cursor import tracker

            self._cursor_on = True
            tracker().acquire()
            tracker().moved.connect(self._cursor_moved)

    def _cursor_moved(self, _pos):
        if self.isVisible() and screen_settings["cursor"]:
            self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if not (self._cursor_on and screen_settings["cursor"]) or self._image is None or self._screen is None:
            return
        from .cursor import map_to_image, paint_cursor, tracker

        pos = tracker().pos
        if pos is None:
            return
        try:
            geo = self._screen.geometry()
            dpr = self._screen.devicePixelRatio()
        except RuntimeError:  # Monitor wurde abgesteckt
            return
        area = fit_rect(self._image.width(), self._image.height(), self.width(), self.height(), self.fit)
        point = map_to_image(pos, geo, area)
        if point is None:
            return
        p = QPainter(self)
        paint_cursor(p, point, area.width() / max(1, geo.width()), dpr)
        p.end()

    def _error(self, _err, text):
        self.set_message(
            f"Bildschirmaufnahme nicht möglich: {text}\n\n"
            "Tipp: Unter Setup → „System-Spiegeln“ kann Kubuntu/Windows den Bildschirm selbst spiegeln."
        )

    def stop(self):
        if self.feed is not None:
            self.feed.stop()
            self.feed = None
        if self.capture is not None:
            self.capture.stop()
        if self._cursor_on:
            from .cursor import tracker

            self._cursor_on = False
            try:
                tracker().moved.disconnect(self._cursor_moved)
            except (RuntimeError, TypeError):
                pass
            tracker().release()


# Einstellungen der Bildschirmaufnahme (setzt der Controller): Mauszeiger einzeichnen?
screen_settings = {"cursor": True}


def _kwin_allowed(screen_name: str) -> bool:
    import sys

    if not sys.platform.startswith("linux"):
        return False
    try:
        from .platform import kwin_capture
    except Exception:  # noqa: BLE001
        return False
    return kwin_capture.allowed(screen_name)


# --------------------------------------------------------------------------- Programmfenster
def capturable_windows():
    """Fenster, die aufgenommen werden können – ohne AluPCs eigene Fenster (sonst Endlos-Spiegel)."""
    try:
        windows = list(QWindowCapture.capturableWindows())
    except Exception:  # noqa: BLE001
        return []
    return [w for w in windows if w.description().strip() and not w.description().startswith("AluPC")]


def _app_part(title: str) -> str:
    """„Dokument – Programmname“ → „Programmname“ (Titel ändern sich oft, der Programmname nicht)."""
    for sep in (" - ", " — ", " – "):
        if sep in title:
            return title.rsplit(sep, 1)[1].strip()
    return ""


def find_window(windows, title: str):
    exact = next((w for w in windows if w.description() == title), None)
    if exact is not None or not title:
        return exact
    part = next((w for w in windows if title in w.description() or w.description() in title), None)
    if part is not None:
        return part
    app = _app_part(title)
    return next((w for w in windows if app and _app_part(w.description()) == app), None)


# Einstellungen der Programm-Aufnahme (setzt der Controller aus der Konfiguration)
window_settings = {"restore_minimized": True}
_window_backend = None


def window_backend():
    """Plattform-Fensterfunktionen (Windows: minimierte Fenster im Hintergrund wiederherstellen)."""
    global _window_backend
    if _window_backend is None:
        from .platform import create_window_backend

        try:
            _window_backend = create_window_backend()
        except Exception:  # noqa: BLE001
            from .platform.base import WindowBackend

            _window_backend = WindowBackend()
    return _window_backend


class WindowSource(SinkView):
    """Nimmt ein Programmfenster auf – auch wenn es hinter anderen Fenstern liegt.

    * Fenster geschlossen → wartet, bis das Programm wieder offen ist, und verbindet sich neu
      (auch wenn sich der Titel ändert, z. B. anderer Browser-Tab).
    * Fenster minimiert → ein minimiertes Fenster zeichnet sich nicht; unter Windows wird es
      (einstellbar) im Hintergrund wiederhergestellt, ohne sich nach vorne zu drängen.
    * Kommen keine neuen Bilder, weil sich im Programm nichts bewegt, bleibt das letzte Bild
      stehen – früher wurde dann alle paar Sekunden neu verbunden (Flackern).
    """

    def __init__(self, cfg, parent=None):
        super().__init__(cfg.get("fit", "contain"), parent)
        self.title = cfg.get("title", "")
        self.restore_minimized = bool(cfg.get("restore_minimized", window_settings["restore_minimized"]))
        self.session = QMediaCaptureSession(self)
        self.capture = QWindowCapture(self)
        self.capture.errorOccurred.connect(self._error)
        self.session.setWindowCapture(self.capture)
        self.session.setVideoSink(self.sink)
        self.sink.videoFrameChanged.connect(self._got_frame)
        self._last_frame = 0.0
        self._started = 0.0
        self._frames = 0
        self.state = "start"
        self._retry = QTimer(self, interval=2000)
        self._retry.timeout.connect(self._attach)
        self._watch = QTimer(self, interval=2000)
        self._watch.timeout.connect(self._check)
        self._attach()

    def _got_frame(self, frame):
        if frame.isValid():
            self._last_frame = time.monotonic()
            self._frames += 1
            self.state = "live"

    def _error(self, _err, text):
        self.state = "fehler"
        if self._image is None:
            self.set_message(f"Programm-Aufnahme: {text} – versuche es erneut …")
        self.capture.stop()
        self._watch.stop()
        self._retry.start()

    def _attach(self):
        match = find_window(capturable_windows(), self.title)
        if match is None:
            self.state = "wartet"
            if self._image is None:
                self.set_message(f"Programm „{self.title}“ ist nicht geöffnet – warte …")
            self._retry.start()
            return
        self._retry.stop()
        self.title = match.description()
        self.capture.stop()
        self.capture.setWindow(match)
        self._started = time.monotonic()
        self._frames = 0
        self._wake_if_minimized()
        self.capture.start()
        self._watch.start()

    def _wake_if_minimized(self) -> bool:
        backend = window_backend()
        try:
            if not backend.is_minimized(self.title):
                return False
            if self.restore_minimized and backend.can_restore_background:
                return backend.restore_in_background(self.title)
        except Exception:  # noqa: BLE001
            return False
        self.state = "minimiert"
        if self._image is None:
            self.set_message(f"„{self.title}“ ist minimiert – ein minimiertes Programm liefert kein Bild. "
                             "Bitte wiederherstellen (es darf hinter anderen Fenstern liegen).")
        return False

    def _check(self):
        window = self.capture.window()
        try:
            gone = not window.isValid()
        except (AttributeError, RuntimeError):
            gone = False
        if gone:  # Fenster geschlossen oder neu erstellt → neu suchen
            self._watch.stop()
            self._attach()
            return
        now = time.monotonic()
        quiet = now - max(self._last_frame, self._started)
        if quiet < 4:
            return
        if self._wake_if_minimized():
            return
        if self._frames == 0 and quiet > 8:
            # Noch nie ein Bild bekommen → Aufnahme neu starten
            self._watch.stop()
            self._attach()

    def stop(self):
        self._retry.stop()
        self._watch.stop()
        self.capture.stop()


# --------------------------------------------------------------------------- Handy (AirPlay)
class AirPlaySource(SinkView):
    """iPhone/iPad per AirPlay: UxPlay empfängt und leitet das Bild als Videostrom hierher weiter."""

    def __init__(self, cfg, parent=None):
        super().__init__(cfg.get("fit", "contain"), parent)
        from .handy import airplay_server

        self.server = airplay_server()
        self.player = None
        self._last_frame = 0.0
        self._started = 0.0
        self._had_frames = False
        self.mode = self.server.acquire(want_stream=True)
        self._watch = QTimer(self, interval=1000)
        self._watch.timeout.connect(self._check)
        if self.mode == "fehlt":
            self.set_message("AirPlay-Empfang: Das Programm UxPlay fehlt.\n\nKachel „Handy“ → „Einrichten …“ "
                             "installiert bzw. findet es.")
            return
        if self.mode == "fenster":
            self.set_message("Diese UxPlay-Version kann das Bild nicht an AluPC weitergeben (erst ab 1.73).\n\n"
                             "Über die Kachel „Handy“ klappt AirPlay trotzdem – im eigenen Vollbild-Fenster.")
            return
        self.sink.videoFrameChanged.connect(self._got_frame)
        self._show_waiting()
        self._start_player()
        self._watch.start()

    def _show_waiting(self):
        s = self.server.settings()
        text = (f"iPhone/iPad: Kontrollzentrum → Bildschirmsynchronisierung → „{s['airplay_name']}“\n"
                "(gleiches WLAN wie dieser PC)")
        if self.server.pin_code:
            text += f"\n\nCode: {self.server.pin_code}"
        self._image = None
        self._pending = None
        self.set_message(text)

    def _start_player(self):
        if self.player is not None:
            self.player.stop()
            self.player.deleteLater()
        self.player = QMediaPlayer(self)
        self.player.setVideoSink(self.sink)
        self.player.setSource(QUrl.fromLocalFile(str(self.server.sdp_path())))
        self.player.play()
        self._started = time.monotonic()

    def _got_frame(self, frame):
        if frame.isValid():
            self._last_frame = time.monotonic()
            self._had_frames = True

    def _check(self):
        now = time.monotonic()
        if self._had_frames and now - self._last_frame > 4:
            # Handy hat aufgehört zu senden → Hinweis zeigen und für die nächste Verbindung neu bereit machen
            self._had_frames = False
            self._show_waiting()
            self._start_player()
        elif not self._had_frames and now - self._started > 30:
            self._start_player()  # vorsorglich neu öffnen, falls der Player hängen geblieben ist
        if self.server.pin_code and self._image is None and "Code:" not in self._message:
            self._show_waiting()

    def stop(self):
        self._watch.stop()
        if self.player is not None:
            self.player.stop()
        if self.mode in ("stream", "fenster"):
            self.server.release()


# --------------------------------------------------------------------------- AluCast (QR-Code)
def qr_image(text: str, border: int = 2) -> QImage:
    """QR-Code als kleines Schwarz-Weiß-Bild (1 Pixel je Modul, zum Hochskalieren ohne Glätten)."""
    import segno

    rows = list(segno.make(text, error="m").matrix_iter(border=border))
    img = QImage(len(rows[0]), len(rows), QImage.Format_RGB32)
    img.fill(QColor("#ffffff"))
    black = QColor("#000000").rgb()
    for y, row in enumerate(rows):
        for x, bit in enumerate(row):
            if bit:
                img.setPixel(x, y, black)
    return img


class CastSource(QWidget):
    """Zeigt QR-Code, Adresse und Code für AluCast – Handy scannt und kann dann senden."""

    def __init__(self, cfg, parent=None):
        super().__init__(parent)
        from .cast_server import cast_server

        self.server = cast_server()
        self.ok = self.server.start()
        self._qr_for = ""
        self._qr: QImage | None = None
        self.server.state_changed.connect(self.update)
        self.setAttribute(Qt.WA_OpaquePaintEvent)

    def qr(self) -> QImage:
        url = self.server.url()
        if url != self._qr_for:
            self._qr_for, self._qr = url, qr_image(url)
        return self._qr

    def paintEvent(self, _e):
        from PySide6.QtGui import QLinearGradient

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        grad = QLinearGradient(0, 0, w, h)
        grad.setColorAt(0, QColor("#0f172a"))
        grad.setColorAt(1, QColor("#1e1b4b"))
        p.fillRect(self.rect(), grad)
        if not self.ok:
            p.setPen(QColor("#e2e8f0"))
            p.setFont(fitted_font(p, "x", w, max(14, h // 24)))
            p.drawText(self.rect().adjusted(20, 20, -20, -20), Qt.AlignCenter | Qt.TextWordWrap,
                       "AluCast konnte nicht starten (Netzwerk-Anschluss belegt).")
            p.end()
            return
        side = int(min(h * 0.62, w * 0.42))
        margin = max(12, h // 30)
        horizontal = w > h * 1.25
        if horizontal:
            qr_rect = QRectF(w * 0.08, (h - side) / 2, side, side)
            text_rect = QRectF(qr_rect.right() + w * 0.05, h * 0.15, w - qr_rect.right() - w * 0.1, h * 0.7)
        else:
            side = int(min(w * 0.7, h * 0.5))
            qr_rect = QRectF((w - side) / 2, h * 0.08, side, side)
            text_rect = QRectF(w * 0.08, qr_rect.bottom() + margin, w * 0.84, h - qr_rect.bottom() - 2 * margin)
        pad = side * 0.05
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#ffffff"))
        p.drawRoundedRect(qr_rect.adjusted(-pad, -pad, pad, pad), pad, pad)
        p.setRenderHint(QPainter.SmoothPixmapTransform, False)
        p.drawImage(qr_rect, self.qr())
        # Text rechts bzw. unten
        code = self.server.code()
        lines = [("Handy → Monitor 2", "#ffffff", 0.11, True),
                 ("QR-Code mit der Kamera-App scannen", "#cbd5e1", 0.055, False),
                 ("Fotos, Videos, Links und Text senden – ohne App", "#94a3b8", 0.045, False),
                 ("", "", 0.03, False),
                 (self.server.url(with_code=False), "#93c5fd", 0.05, False),
                 (f"Code: {code[:3]} {code[3:]}", "#fbbf24", 0.07, True),
                 ("Handy und PC im selben WLAN", "#94a3b8", 0.04, False)]
        y = text_rect.y()
        unit = text_rect.height() if horizontal else text_rect.height() * 1.4
        for text, color, size, bold in lines:
            px = max(10, int(unit * size))
            if text:
                font = fitted_font(p, text, int(text_rect.width()), px)
                font.setBold(bold)
                p.setFont(font)
                p.setPen(QColor(color))
                p.drawText(QRectF(text_rect.x(), y, text_rect.width(), px * 1.5),
                           (Qt.AlignLeft if horizontal else Qt.AlignHCenter) | Qt.AlignVCenter, text)
            y += px * 1.55
        p.end()

    def stop(self):
        pass


# --------------------------------------------------------------------------- Website
class WebsiteSource(QWidget):
    def __init__(self, cfg, parent=None):
        super().__init__(parent)
        from PySide6.QtWebEngineWidgets import QWebEngineView
        from PySide6.QtWidgets import QVBoxLayout

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.view = QWebEngineView(self)
        layout.addWidget(self.view)
        url = normalize_url(cfg.get("url", ""))
        self.view.setZoomFactor(float(cfg.get("zoom", 1.0) or 1.0))
        self.volume = int(cfg.get("volume", 100))
        self.muted = bool(cfg.get("muted", False))
        self._install_volume_script()
        self.view.load(QUrl(url))
        self._timer = None
        seconds = int(cfg.get("reload_seconds", 0) or 0)
        if seconds > 0:
            self._timer = QTimer(self, interval=seconds * 1000)
            self._timer.timeout.connect(self.view.reload)
            self._timer.start()

    def _volume_js(self) -> str:
        return VOLUME_JS % (max(0, min(100, self.volume)) / 100)

    def _install_volume_script(self):
        """Lautstärke für alle <video>/<audio> der Seite – auch für später geladene (z. B. YouTube)."""
        from PySide6.QtWebEngineCore import QWebEngineScript

        page = self.view.page()
        page.setAudioMuted(self.muted)
        scripts = page.scripts()
        for old in scripts.find("alupc-volume"):
            scripts.remove(old)
        script = QWebEngineScript()
        script.setName("alupc-volume")
        script.setSourceCode(self._volume_js())
        script.setInjectionPoint(QWebEngineScript.DocumentReady)
        script.setWorldId(QWebEngineScript.MainWorld)
        script.setRunsOnSubFrames(True)
        scripts.insert(script)

    def set_volume(self, volume: int | None = None, muted: bool | None = None) -> None:
        if volume is not None:
            self.volume = int(volume)
        if muted is not None:
            self.muted = bool(muted)
        self._install_volume_script()
        self.view.page().runJavaScript(self._volume_js())

    def stop(self):
        if self._timer:
            self._timer.stop()
        self.view.stop()
        self.view.setUrl(QUrl("about:blank"))


# Setzt die Lautstärke aller Medien der Seite und merkt sie sich für Medien, die erst später starten
VOLUME_JS = """(function () {
  window.__alupcVolume = %.2f;
  var set = function (m) { try { m.volume = window.__alupcVolume; } catch (e) {} };
  document.querySelectorAll('video, audio').forEach(set);
  if (!window.__alupcVolumeHook) {
    window.__alupcVolumeHook = true;
    document.addEventListener('play', function (e) { set(e.target); }, true);
  }
})();"""


def normalize_url(url: str) -> str:
    """„beispiel.de“ → „https://beispiel.de“; Adressen mit Schema (https:, file:, data: …) bleiben."""
    url = url.strip()
    if url and "://" not in url and not url.startswith(("about:", "file:", "data:", "view-source:")):
        url = "https://" + url
    return url


# --------------------------------------------------------------------------- Bild, Video, Diashow
def load_image(path: str) -> QImage:
    reader = QImageReader(path)
    reader.setAutoTransform(True)
    return reader.read()


class ImageSource(FrameView):
    def __init__(self, cfg, parent=None):
        super().__init__(cfg.get("fit", "contain"), parent)
        image = load_image(cfg.get("path", ""))
        if image.isNull():
            self.set_message(f"Bild nicht gefunden: {cfg.get('path', '')}")
        else:
            self.set_image(image)


class VideoSource(SinkView):
    def __init__(self, cfg, parent=None):
        super().__init__(cfg.get("fit", "contain"), parent)
        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.set_volume(int(cfg.get("volume", 100)), bool(cfg.get("muted", False)))
        self.player.setAudioOutput(self.audio)
        self.player.setVideoSink(self.sink)
        self.player.errorOccurred.connect(lambda _e, text: self.set_message(f"Video-Fehler: {text}"))
        if cfg.get("loop", True):
            self.player.setLoops(QMediaPlayer.Infinite)
        self.title = Path(cfg.get("path", "")).stem or "Video"
        self.player.setSource(QUrl.fromLocalFile(cfg.get("path", "")))
        self.player.play()

    def set_volume(self, volume: int | None = None, muted: bool | None = None) -> None:
        if volume is not None:
            self.audio.setVolume(max(0, min(100, int(volume))) / 100)
        if muted is not None:
            self.audio.setMuted(bool(muted))

    # ---- Steuerung (Mediensteuerung im Hauptfenster)
    def playing(self) -> bool:
        return self.player.playbackState() == QMediaPlayer.PlayingState

    def toggle_play(self) -> None:
        if self.playing():
            self.player.pause()
        else:
            self.player.play()

    def duration(self) -> int:
        return max(0, int(self.player.duration()))

    def position(self) -> int:
        return max(0, int(self.player.position()))

    def seek_to(self, ms: int) -> None:
        d = self.duration()
        self.player.setPosition(max(0, min(int(ms), d - 1 if d else int(ms))))

    def skip(self, ms: int) -> None:
        self.seek_to(self.position() + ms)

    def stop(self):
        self.player.stop()


def list_images(folder: str) -> list[str]:
    try:
        files = sorted(Path(folder).iterdir(), key=lambda p: p.name.lower())
    except OSError:
        return []
    return [str(p) for p in files if p.suffix.lower() in IMAGE_SUFFIXES]


class SlideshowSource(FrameView):
    def __init__(self, cfg, parent=None):
        super().__init__(cfg.get("fit", "contain"), parent)
        self.folder = cfg.get("folder", "")
        self.index = -1
        self.timer = QTimer(self, interval=max(1, int(cfg.get("interval", 5))) * 1000)
        self.timer.timeout.connect(self.next)
        self.next()
        self.timer.start()

    def next(self):
        files = list_images(self.folder)  # neu einlesen: neue Bilder erscheinen automatisch
        if not files:
            self.set_image(None)
            self.set_message(f"Keine Bilder im Ordner: {self.folder}")
            return
        self.index = (self.index + 1) % len(files)
        self.set_image(load_image(files[self.index]))

    def stop(self):
        self.timer.stop()


# --------------------------------------------------------------------------- Text, Uhr, Countdown, Farbe
class TextBase(QWidget):
    """Zeichnet Text; Schriftgröße in Prozent der Feldhöhe, passt also auf jeden Monitor."""

    def __init__(self, cfg, parent=None):
        super().__init__(parent)
        self.size_percent = float(cfg.get("size", 12))
        self.color = QColor(cfg.get("color", "#ffffff"))
        self.background = QColor(cfg.get("background", "#000000"))

    def text(self) -> str:
        return ""

    def fit_text(self, text: str) -> str:
        """Text, nach dem die Schriftgröße bemessen wird (Ziffern → „8“: Größe springt nicht)."""
        return text

    def text_color(self) -> QColor:
        return self.color

    def stop(self):
        pass

    def paintEvent(self, _event):
        p = QPainter(self)
        p.fillRect(self.rect(), self.background)
        margin = int(self.width() * 0.03)
        area = self.rect().adjusted(margin, 0, -margin, 0)
        shown = self.text()
        text = self.fit_text(shown)
        font = QFont()
        size = max(8, int(self.height() * self.size_percent / 100))
        # Schrift verkleinern, bis der Text ins Feld passt
        for _ in range(20):
            font.setPixelSize(size)
            p.setFont(font)
            needed = p.boundingRect(area, Qt.AlignCenter | Qt.TextWordWrap, text)
            fits_lines = all(p.fontMetrics().horizontalAdvance(line) <= area.width() for line in text.split("\n"))
            if (needed.height() <= area.height() and fits_lines) or size <= 8:
                break
            size = max(8, int(size * 0.9))
        p.setPen(self.text_color())
        p.drawText(area, Qt.AlignCenter | Qt.TextWordWrap, shown)
        p.end()


class TextSource(TextBase):
    def __init__(self, cfg, parent=None):
        super().__init__(cfg, parent)
        self._text = cfg.get("text", "")

    def text(self):
        return self._text


class ClockSource(TextBase):
    def __init__(self, cfg, parent=None):
        cfg = {"size": 25, **cfg}
        super().__init__(cfg, parent)
        self.show_date = bool(cfg.get("show_date", True))
        self.show_seconds = bool(cfg.get("show_seconds", True))
        # 4× pro Sekunde nachsehen, aber nur neu zeichnen, wenn sich die Anzeige ändert:
        # die Sekunde springt pünktlich um (max. ¼ s spät) und es wird trotzdem kaum gezeichnet
        self._shown = ""
        self.timer = QTimer(self, interval=250)
        self.timer.setTimerType(Qt.PreciseTimer)
        self.timer.timeout.connect(self._tick)
        self.timer.start()

    def _tick(self):
        text = self.text()
        if text != self._shown:
            self._shown = text
            self.update()

    def stop(self):
        self.timer.stop()

    def text(self):
        fmt = "%H:%M:%S" if self.show_seconds else "%H:%M"
        text = time.strftime(fmt)
        if self.show_date:
            text += "\n" + format_date_de(time.localtime())
        return text

    def fit_text(self, text: str) -> str:
        return "".join("8" if ch.isdigit() else ch for ch in text)

    def paintEvent(self, _event):
        if not self.show_date:
            return super().paintEvent(_event)
        # Uhrzeit groß, Datum kleiner darunter; beides passt sich der Feldbreite an
        p = QPainter(self)
        p.fillRect(self.rect(), self.background)
        p.setPen(self.color)
        margin = int(self.width() * 0.04)
        area = self.rect().adjusted(margin, 0, -margin, 0)
        now = time.localtime()
        clock = time.strftime("%H:%M:%S" if self.show_seconds else "%H:%M", now)
        date = format_date_de(now)
        template = "".join("8" if ch.isdigit() else ch for ch in clock)  # Größe springt nicht
        big = fitted_font(p, template, area.width(), int(self.height() * self.size_percent / 100 * 1.4))
        small = fitted_font(p, date, area.width(), max(8, big.pixelSize() // 3))
        h_big = QFontMetrics(big).height()
        h_small = QFontMetrics(small).height()
        top = area.top() + (area.height() - h_big - h_small) // 2
        p.setFont(big)
        p.drawText(area.left(), top, area.width(), h_big, Qt.AlignCenter, clock)
        p.setFont(small)
        p.drawText(area.left(), top + h_big, area.width(), h_small, Qt.AlignCenter, date)
        p.end()


def fitted_font(painter, text: str, width: int, size: int) -> QFont:
    """Schrift in der Wunschgröße – kleiner, falls der Text sonst nicht in die Breite passt."""
    font = QFont()
    size = max(8, size)
    font.setPixelSize(size)
    advance = QFontMetrics(font).horizontalAdvance(text)
    if advance > width > 0:
        font.setPixelSize(max(8, int(size * width / advance)))
    return font


WEEKDAYS = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
MONTHS = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August",
          "September", "Oktober", "November", "Dezember"]


def format_date_de(t) -> str:
    return f"{WEEKDAYS[t.tm_wday]}, {t.tm_mday}. {MONTHS[t.tm_mon - 1]} {t.tm_year}"


class CountdownSource(TextBase):
    """Zeigt den gemeinsamen Timer (Countdown oder Stoppuhr) – läuft weiter, auch wenn die
    Anzeige neu aufgebaut wird. Farbe: letzte Minute orange, letzte 10 s rot, Ende blinkt."""

    def __init__(self, cfg, parent=None):
        from .timer import clock

        cfg = {"size": 30, **cfg}
        super().__init__(cfg, parent)
        self.clock = clock
        seconds = float(cfg.get("minutes", 5)) * 60 + float(cfg.get("seconds", 0))
        mode = cfg.get("mode", "countdown")
        # Nur neu stellen, wenn der Timer nicht schon läuft (sonst würde er wieder von vorn beginnen).
        # „shared“ = Timer-Kachel: zeigt den Timer so, wie er gerade steht.
        if not cfg.get("shared") and not clock.running and (clock.fresh() or clock.finished() or clock.mode != mode
                                  or abs(clock.duration - seconds) > 0.5):
            clock.set(seconds, mode, cfg.get("finished_text", "Zeit ist um!"))
        if cfg.get("autostart", True) and clock.fresh():
            clock.start()
        self.warn_colors = bool(cfg.get("warn_colors", True))
        self._shown = None
        self.timer = QTimer(self, interval=100)
        self.timer.setTimerType(Qt.PreciseTimer)
        self.timer.timeout.connect(self._tick)
        self.timer.start()

    def _tick(self):
        # nur neu zeichnen, wenn sich Zahl oder Farbe (Warnung/Blinken) ändert
        state = (self.text(), self.text_color().rgba())
        if state != self._shown:
            self._shown = state
            self.update()

    def text(self):
        return self.clock.text()

    def fit_text(self, text: str) -> str:
        return "".join("8" if ch.isdigit() else ch for ch in text)

    def text_color(self) -> QColor:
        if not self.warn_colors:
            return self.color
        state = self.clock.urgency()
        if state == "bald":
            return QColor("#f59e0b")
        if state == "gleich":
            return QColor("#ef4444")
        if state == "ende":
            # blinken: halbe Sekunde rot, halbe Sekunde normal
            return QColor("#ef4444") if int(time.monotonic() * 2) % 2 == 0 else self.color
        return self.color

    def stop(self):
        self.timer.stop()


def format_countdown(seconds: int) -> str:
    h, rest = divmod(seconds, 3600)
    m, s = divmod(rest, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


class ColorSource(QWidget):
    def __init__(self, cfg, parent=None):
        super().__init__(parent)
        self.color = QColor(cfg.get("color", "#000000"))

    def stop(self):
        pass

    def paintEvent(self, _event):
        p = QPainter(self)
        p.fillRect(self.rect(), self.color)
        p.end()


# --------------------------------------------------------------------------- Szene
class SceneSource(QWidget):
    """Setzt mehrere Quellen nach einer Layout-Vorlage zusammen."""

    def __init__(self, cfg, scene_lookup, depth=0, parent=None):
        super().__init__(parent)
        self.children_sources: list[tuple[tuple, QWidget]] = []
        name = cfg.get("scene")
        scene = scene_lookup(name) if name else None
        self.background = QColor((scene or {}).get("background", "#000000"))
        if scene is None:
            self._add((0, 0, 1, 1), ColorSource({"color": "#000000"}, self))
            self._add((0, 0.4, 1, 0.2), TextSource({"text": f"Szene „{name}“ fehlt", "size": 40}, self))
            return
        for rect, slot in zip(layout_slots(scene.get("layout", "vollbild")), scene.get("slots", [])):
            if not slot:
                continue
            widget = create_source(slot, scene_lookup, depth + 1, self)
            self._add(rect[:4], widget)

    def _add(self, rect, widget):
        self.children_sources.append((rect, widget))
        widget.show()

    def resizeEvent(self, _event):
        w, h = self.width(), self.height()
        for (x, y, rw, rh), widget in self.children_sources:
            widget.setGeometry(round(x * w), round(y * h), round(rw * w), round(rh * h))

    def paintEvent(self, _event):
        p = QPainter(self)
        p.fillRect(self.rect(), self.background)
        p.end()

    def stop(self):
        for _rect, widget in self.children_sources:
            widget.stop()


def video_sources(widget) -> list:
    """Alle Videos in einem Inhalt – auch in Feldern eigener Szenen."""
    return [w for w in media_sources(widget) if isinstance(w, VideoSource)]


def camera_sources(widget) -> list:
    """Alle Kameras in einem Inhalt – auch in Feldern eigener Szenen."""
    if widget is None:
        return []
    if isinstance(widget, SceneSource):
        found = []
        for _rect, child in widget.children_sources:
            found += camera_sources(child)
        return found
    return [widget] if isinstance(widget, CameraSource) and widget.camera is not None else []


def media_sources(widget) -> list:
    """Alle Quellen mit Ton (Video, Website) in einem Inhalt – auch in Szenen-Feldern."""
    if widget is None:
        return []
    if isinstance(widget, SceneSource):
        found = []
        for _rect, child in widget.children_sources:
            found += media_sources(child)
        return found
    return [widget] if hasattr(widget, "set_volume") else []


# --------------------------------------------------------------------------- Fabrik
def create_source(cfg: dict, scene_lookup, depth: int = 0, parent=None) -> QWidget:
    t = (cfg or {}).get("type")
    try:
        if t == "scene":
            if depth >= MAX_SCENE_DEPTH:
                return TextSource({"text": "Szenen zu tief verschachtelt", "size": 10}, parent)
            return SceneSource(cfg, scene_lookup, depth, parent)
        factory = {
            "camera": CameraSource,
            "screen": ScreenSource,
            "window": WindowSource,
            "airplay": AirPlaySource,
            "cast": CastSource,
            "website": WebsiteSource,
            "image": ImageSource,
            "video": VideoSource,
            "slideshow": SlideshowSource,
            "text": TextSource,
            "clock": ClockSource,
            "countdown": CountdownSource,
            "color": ColorSource,
        }.get(t)
        if factory is None:
            return TextSource({"text": f"Unbekannte Quelle: {t}", "size": 8}, parent)
        return factory(cfg, parent)
    except Exception as exc:  # noqa: BLE001 - eine kaputte Quelle darf nicht alles stoppen
        return TextSource({"text": f"Fehler in Quelle ({t}): {exc}", "size": 6}, parent)
