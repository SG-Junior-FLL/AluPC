"""Vorschaubilder für die Mediathek – im Hintergrund erzeugt und auf der Festplatte zwischengespeichert.

* Bilder: verkleinert eingelesen (schnell, auch bei großen Fotos)
* Diashow: erstes Bild des Ordners
* Video: ein Bild nach ca. 1 s (über Qt Multimedia); klappt das nicht, bleibt das Symbol
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from PySide6.QtCore import QObject, QSize, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QImage, QImageReader

from ..config import config_dir
from .util import run_async

SIZE = QSize(320, 180)


def cache_path(target: str) -> Path | None:
    try:
        st = os.stat(target)
    except OSError:
        return None
    digest = hashlib.sha1(f"{os.path.abspath(target)}|{st.st_mtime_ns}|{st.st_size}".encode()).hexdigest()
    return config_dir() / "thumbs" / f"{digest}.jpg"


def fit(image: QImage) -> QImage:
    return image.scaled(SIZE, Qt.KeepAspectRatio, Qt.SmoothTransformation)


def load_image_thumb(path: str) -> QImage:
    reader = QImageReader(path)
    reader.setAutoTransform(True)
    size = reader.size()
    if size.isValid() and (size.width() > SIZE.width() * 2 or size.height() > SIZE.height() * 2):
        reader.setScaledSize(size.scaled(SIZE * 2, Qt.KeepAspectRatio))  # nur so groß wie nötig lesen
    image = reader.read()
    return fit(image) if not image.isNull() else QImage()


def first_image(folder: str) -> str | None:
    from ..sources import list_images

    files = list_images(folder)
    return files[0] if files else None


class Thumbnails(QObject):
    """Liefert Vorschaubilder; `ready(schlüssel, bild)` kommt, sobald eins fertig ist."""

    ready = Signal(str, QImage)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.memory: dict[str, QImage] = {}
        self._videos: list[tuple[str, str]] = []
        self._player = None
        self._busy = False

    def request(self, cfg: dict) -> QImage | None:
        """Sofort da (Speicher/Festplatte) → Bild; sonst None und später `ready`."""
        kind = cfg.get("type")
        target = cfg.get("folder") if kind == "slideshow" else cfg.get("path")
        if not target:
            return None
        k = f"{kind}:{target}"
        if k in self.memory:
            return self.memory[k]
        if kind == "slideshow":
            source = first_image(target)
            if source is None:
                return None
            kind, target = "image", source
        cached = cache_path(target)
        if cached is not None and cached.exists():
            image = QImage(str(cached))
            if not image.isNull():
                self.memory[k] = image
                return image
        if cached is None:
            return None
        if kind == "image":
            run_async(lambda: load_image_thumb(target), lambda img: self._done(k, img, cached))
        elif kind == "video":
            self._videos.append((k, target))
            QTimer.singleShot(0, self._next_video)
        return None

    def _done(self, k: str, image: QImage, cached: Path | None):
        if image is None or image.isNull():
            return
        self.memory[k] = image
        if cached is not None:
            try:
                cached.parent.mkdir(parents=True, exist_ok=True)
                image.save(str(cached), "JPG", 85)
            except OSError:
                pass
        self.ready.emit(k, image)

    # Videos nacheinander (ein Player reicht, sonst wird es für viele Videos zu schwer)
    def _next_video(self):
        if self._busy or not self._videos:
            return
        from PySide6.QtMultimedia import QMediaPlayer, QVideoSink

        self._busy = True
        k, path = self._videos.pop(0)
        player = QMediaPlayer(self)
        sink = QVideoSink(self)
        player.setVideoSink(sink)
        state = {"done": False}

        def finish(image: QImage | None):
            if state["done"]:
                return
            state["done"] = True
            player.stop()
            player.deleteLater()
            sink.deleteLater()
            self._busy = False
            if image is not None and not image.isNull():
                self._done(k, fit(image), cache_path(path))
            QTimer.singleShot(0, self._next_video)

        def frame(f):
            if f.isValid() and player.position() >= 800:
                finish(f.toImage())

        sink.videoFrameChanged.connect(frame)
        player.errorOccurred.connect(lambda *_: finish(None))
        player.setSource(QUrl.fromLocalFile(path))
        player.setPosition(1000)
        player.play()
        QTimer.singleShot(6000, lambda: finish(None))  # nie hängen bleiben
