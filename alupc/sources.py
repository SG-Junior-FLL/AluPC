"""Quellen, die auf Monitor 2 angezeigt werden: Kamera, Bildschirm, Programm, Website, …

Jede Quelle ist ein QWidget mit einer Methode `stop()`. Video-Quellen zeichnen ihre
Bilder selbst (über QVideoSink); so funktionieren Standbild und Bild-in-Bild
über ein einfaches `grab()`.
"""

from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import QRectF, Qt, QTimer, QUrl
from PySide6.QtGui import QColor, QFont, QFontMetrics, QGuiApplication, QImage, QImageReader, QPainter, QPixmap
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


class CameraSource(SinkView):
    def __init__(self, cfg, parent=None):
        super().__init__(cfg.get("fit", "contain"), parent)
        self.session = QMediaCaptureSession(self)
        self.camera = None
        dev = find_camera(cfg.get("device_id"))
        if dev is None:
            self.set_message(f"Kamera „{cfg.get('name', '')}“ nicht gefunden.")
            return
        self.camera = QCamera(dev, self)
        self.camera.errorOccurred.connect(lambda _e, text: self.set_message(f"Kamerafehler: {text}"))
        self.session.setCamera(self.camera)
        self.session.setVideoSink(self.sink)
        self.set_message("Kamera startet …")
        self.camera.start()

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
    def __init__(self, cfg, parent=None):
        super().__init__(cfg.get("fit", "contain"), parent)
        self.session = QMediaCaptureSession(self)
        self.capture = QScreenCapture(self)
        screen = find_screen(cfg.get("screen_name")) or QGuiApplication.primaryScreen()
        self.capture.setScreen(screen)
        self.capture.errorOccurred.connect(self._error)
        self.session.setScreenCapture(self.capture)
        self.session.setVideoSink(self.sink)
        self.set_message("Bildschirmaufnahme startet … (evtl. Freigabe bestätigen)")
        self.capture.start()

    def _error(self, _err, text):
        self.set_message(
            f"Bildschirmaufnahme nicht möglich: {text}\n\n"
            "Tipp: Unter Setup → „System-Spiegeln“ kann Kubuntu/Windows den Bildschirm selbst spiegeln."
        )

    def stop(self):
        self.capture.stop()


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


class WindowSource(SinkView):
    """Nimmt ein Programmfenster auf. Verbindet sich neu, wenn das Fenster weg ist, der Titel
    wechselt (z. B. anderer Browser-Tab) oder eine Weile kein Bild mehr kommt."""

    def __init__(self, cfg, parent=None):
        super().__init__(cfg.get("fit", "contain"), parent)
        self.title = cfg.get("title", "")
        self.session = QMediaCaptureSession(self)
        self.capture = QWindowCapture(self)
        self.capture.errorOccurred.connect(self._error)
        self.session.setWindowCapture(self.capture)
        self.session.setVideoSink(self.sink)
        self.sink.videoFrameChanged.connect(self._got_frame)
        self._last_frame = 0.0
        self._started = 0.0
        self._retry = QTimer(self, interval=3000)
        self._retry.timeout.connect(self._attach)
        self._watch = QTimer(self, interval=2000)
        self._watch.timeout.connect(self._check)
        self._attach()

    def _got_frame(self, _frame):
        self._last_frame = time.monotonic()

    def _error(self, _err, text):
        if self._image is None:
            self.set_message(f"Programm-Aufnahme: {text} – versuche es erneut …")
        self.capture.stop()
        self._retry.start()

    def _attach(self):
        match = find_window(capturable_windows(), self.title)
        if match is None:
            if self._image is None:
                self.set_message(f"Programm „{self.title}“ ist nicht geöffnet – warte …")
            self._retry.start()
            return
        self._retry.stop()
        self.title = match.description()
        self.capture.stop()
        self.capture.setWindow(match)
        self._started = time.monotonic()
        self.capture.start()
        self._watch.start()

    def _check(self):
        # 6 s kein neues Bild (Fenster geschlossen, minimiert oder neu erstellt) → neu verbinden
        now = time.monotonic()
        if now - max(self._last_frame, self._started) > 6:
            if self._image is None:
                self.set_message(f"Kein Bild von „{self.title}“ – ist das Programm minimiert?")
            self._watch.stop()
            self._attach()

    def stop(self):
        self._retry.stop()
        self._watch.stop()
        self.capture.stop()


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
        self.view.load(QUrl(url))
        self._timer = None
        seconds = int(cfg.get("reload_seconds", 0) or 0)
        if seconds > 0:
            self._timer = QTimer(self, interval=seconds * 1000)
            self._timer.timeout.connect(self.view.reload)
            self._timer.start()

    def stop(self):
        if self._timer:
            self._timer.stop()
        self.view.stop()
        self.view.setUrl(QUrl("about:blank"))


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
        self.audio.setMuted(bool(cfg.get("muted", False)))
        self.player.setAudioOutput(self.audio)
        self.player.setVideoSink(self.sink)
        self.player.errorOccurred.connect(lambda _e, text: self.set_message(f"Video-Fehler: {text}"))
        if cfg.get("loop", True):
            self.player.setLoops(QMediaPlayer.Infinite)
        self.player.setSource(QUrl.fromLocalFile(cfg.get("path", "")))
        self.player.play()

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
        self.timer = QTimer(self, interval=1000)
        self.timer.timeout.connect(self.update)
        self.timer.start()

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

    def stop(self):
        self.timer.stop()


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
        self.timer = QTimer(self, interval=200)
        self.timer.timeout.connect(self.update)
        self.timer.start()

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
