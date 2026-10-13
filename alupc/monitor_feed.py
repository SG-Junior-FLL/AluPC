"""Echtes Bild von Monitor 2, wenn er ein normaler Bildschirm ist („Erweitern“) – für Handy-Live-Bild, virtuelle Kamera
und Live-Ansicht. Eine gemeinsame Aufnahme (ScreenSource: KDE/Wayland über KWin ohne Nachfrage, sonst Qt), die nur
läuft, solange jemand Bilder holt, und nach kurzer Pause von selbst stoppt.
"""

from __future__ import annotations

import time

from PySide6.QtCore import QObject, QTimer
from PySide6.QtGui import QImage

IDLE_SECONDS = 6.0


class MonitorFeed(QObject):
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.source = None
        self.screen_name = ""
        self.used = 0.0
        self._idle = QTimer(self, interval=2000)
        self._idle.timeout.connect(self._check_idle)

    def image(self) -> QImage | None:
        """Neuestes Bild von Monitor 2 (None = noch keins oder Aufnahme geht hier nicht – siehe problem())."""
        from PySide6.QtGui import QGuiApplication

        if QGuiApplication.platformName() in ("offscreen", "minimal"):
            return None  # kein echter Bildschirm da (Tests, Selbsttest) – nichts aufnehmen
        screen = self.controller.output_screen() if hasattr(self.controller, "output_screen") else None
        if screen is None:
            self.stop()
            return None
        self.used = time.monotonic()
        if self.source is None or self.screen_name != screen.name():
            self.stop()
            from .sources import ScreenSource

            fps = int((self.controller.config.data.get("pip") or {}).get("fps", 20))
            self.source = ScreenSource({"screen_name": screen.name(), "fps": max(10, min(30, fps))})
            self.screen_name = screen.name()
            self._idle.start()
        try:
            img = self.source.image()
        except RuntimeError:  # schon gelöscht
            self.source = None
            return None
        return img if img is not None and not img.isNull() else None

    def problem(self) -> str:
        return getattr(self.source, "problem", "") if self.source is not None else ""

    def running(self) -> bool:
        return self.source is not None

    def stop(self) -> None:
        src, self.source, self.screen_name = self.source, None, ""
        self._idle.stop()
        if src is not None:
            try:
                src.stop()
            except (RuntimeError, AttributeError):
                pass
            src.deleteLater()

    def _check_idle(self) -> None:
        if time.monotonic() - self.used > IDLE_SECONDS:
            self.stop()


def fit_into(img: QImage, w: int, h: int) -> QImage:
    """Bild auf genau w×h (Seitenverhältnis bleibt, schwarzer Rand)."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor, QPainter

    scaled = img.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    if scaled.width() == w and scaled.height() == h:
        return scaled.convertToFormat(QImage.Format_RGB32)
    canvas = QImage(w, h, QImage.Format_RGB32)
    canvas.fill(QColor("#000000"))
    p = QPainter(canvas)
    p.drawImage((w - scaled.width()) // 2, (h - scaled.height()) // 2, scaled)
    p.end()
    return canvas


def waiting_image(w: int, h: int, why: str = "") -> QImage:
    """Solange noch kein Bild da ist (oder die Aufnahme hier nicht geht): dunkles Bild, Grund klein unten."""
    from PySide6.QtCore import QRect, Qt
    from PySide6.QtGui import QColor, QFont, QPainter

    img = QImage(w, h, QImage.Format_RGB32)
    img.fill(QColor("#0b1020"))
    if why:
        p = QPainter(img)
        p.setPen(QColor("#64748b"))
        f = QFont()
        f.setPixelSize(max(10, h // 30))
        p.setFont(f)
        p.drawText(QRect(0, h - h // 8, w, h // 10), Qt.AlignCenter, why)
        p.end()
    return img
