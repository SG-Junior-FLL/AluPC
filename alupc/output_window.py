"""Vollbild-Fenster auf Monitor 2 mit Standbild- und Sichtschutz-Ebene."""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QObject, QPropertyAnimation, Qt, QTimer, Signal
from PySide6.QtGui import QGuiApplication, QImage, QPixmap
from PySide6.QtMultimedia import QMediaCaptureSession, QScreenCapture, QVideoSink
from PySide6.QtWidgets import QGraphicsOpacityEffect, QWidget

from .platform.linux_display import is_wayland
from .sources import FrameView, TextSource, load_image


class PrivacyLayer(QWidget):
    """Schwarzes Bild, optional mit eigenem Bild oder Text."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAutoFillBackground(True)
        pal = self.palette()
        pal.setColor(self.backgroundRole(), Qt.black)
        self.setPalette(pal)
        self._child: QWidget | None = None

    def configure(self, image_path: str, text: str) -> None:
        if self._child is not None:
            self._child.deleteLater()
            self._child = None
        if image_path:
            view = FrameView(parent=self)
            view.set_image(load_image(image_path))
            self._child = view
        elif text:
            self._child = TextSource({"text": text, "size": 8}, self)
        if self._child is not None:
            self._child.setGeometry(self.rect())
            self._child.show()

    def resizeEvent(self, _event):
        if self._child is not None:
            self._child.setGeometry(self.rect())


class OutputWindow(QWidget):
    def __init__(self):
        super().__init__(None, Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
                         | Qt.WindowDoesNotAcceptFocus)
        self.setWindowTitle("AluPC – Monitor 2")
        self.setCursor(Qt.BlankCursor)
        self.setAutoFillBackground(True)
        pal = self.palette()
        pal.setColor(self.backgroundRole(), Qt.black)
        self.setPalette(pal)
        self.content: QWidget | None = None
        self.freeze_layer = FrameView(parent=self)
        self.freeze_layer.hide()
        self.privacy_layer = PrivacyLayer(self)
        self.privacy_layer.hide()
        self.content_active = False
        self.screen_name = ""
        self.fade_enabled = True
        self._fades: list[QWidget] = []

    # ------------------------------------------------------------ Inhalt
    def set_content(self, widget: QWidget | None) -> None:
        if self.fade_enabled and self.isVisible() and self.content is not None and widget is not None:
            self._crossfade(self.content.grab())
        if self.content is not None:
            try:
                self.content.stop()
            except Exception:  # noqa: BLE001
                pass
            self.content.hide()
            self.content.deleteLater()
        self.content = widget
        self.content_active = widget is not None
        if widget is not None:
            widget.setParent(self)
            widget.setGeometry(self.rect())
            widget.show()
            widget.lower()
        self.update_visibility()

    def _crossfade(self, old: QPixmap) -> None:
        """Altes Bild kurz über das neue legen und ausblenden (weicher Wechsel)."""
        if old.isNull():
            return
        layer = FrameView("stretch", self)
        layer.set_image(old)
        layer.setGeometry(self.rect())
        effect = QGraphicsOpacityEffect(layer)
        layer.setGraphicsEffect(effect)
        layer.show()
        layer.raise_()
        for top in (self.freeze_layer, self.privacy_layer):
            if top.isVisible():
                top.raise_()
        anim = QPropertyAnimation(effect, b"opacity", layer)
        anim.setDuration(350)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.setEasingCurve(QEasingCurve.InOutQuad)
        anim.finished.connect(layer.deleteLater)
        anim.finished.connect(lambda: self._fades.remove(layer) if layer in self._fades else None)
        self._fades.append(layer)
        anim.start()

    def snapshot(self) -> QPixmap:
        if self.content is not None:
            return self.content.grab()
        return QPixmap()

    # ------------------------------------------------------------ Ebenen
    def set_frozen(self, image: QImage | QPixmap | None) -> None:
        if image is None:
            self.freeze_layer.hide()
            self.freeze_layer.set_image(None)
        else:
            self.freeze_layer.set_image(image)
            self.freeze_layer.setGeometry(self.rect())
            self.freeze_layer.show()
            self.freeze_layer.raise_()
            self.privacy_layer.raise_()
        self.update_visibility()

    def set_privacy(self, on: bool, image_path: str = "", text: str = "") -> None:
        if on:
            self.privacy_layer.configure(image_path, text)
            self.privacy_layer.setGeometry(self.rect())
            self.privacy_layer.show()
            self.privacy_layer.raise_()
        else:
            self.privacy_layer.hide()
        self.update_visibility()

    def needed(self) -> bool:
        return self.content_active or self.freeze_layer.isVisible() or self.privacy_layer.isVisible()

    # ------------------------------------------------------------ Monitor
    def place_on(self, screen) -> None:
        self.screen_name = screen.name() if screen else ""
        if screen is None:
            self.hide()
            return
        was_visible = self.isVisible()
        if was_visible:
            self.hide()
        self.setGeometry(screen.geometry())
        self.create()
        handle = self.windowHandle()
        if handle is not None:
            handle.setScreen(screen)
        self.update_visibility()

    def update_visibility(self) -> None:
        if self.needed() and self.screen_name:
            if not self.isVisible():
                self.showFullScreen()
        elif self.isVisible():
            self.hide()

    def resizeEvent(self, _event):
        for w in (self.content, self.freeze_layer, self.privacy_layer, *self._fades):
            if w is not None:
                w.setGeometry(self.rect())


class ScreenGrabber(QObject):
    """Einmaliges Bildschirmfoto eines Monitors – auch unter Wayland (über Aufnahme)."""

    done = Signal(QImage)
    failed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._capture = None

    def grab(self, screen) -> None:
        if screen is None:
            self.failed.emit("Monitor nicht gefunden")
            return
        if not is_wayland():
            pixmap = screen.grabWindow(0)
            if not pixmap.isNull():
                QTimer.singleShot(0, lambda: self.done.emit(pixmap.toImage()))
                return
        self._start_capture(screen)

    def _start_capture(self, screen) -> None:
        self.session = QMediaCaptureSession(self)
        self.sink = QVideoSink(self)
        self._capture = QScreenCapture(self)
        self._capture.setScreen(screen)
        self._capture.errorOccurred.connect(lambda _e, text: self._finish(None, text))
        self.session.setScreenCapture(self._capture)
        self.session.setVideoSink(self.sink)
        self.sink.videoFrameChanged.connect(self._frame)
        QTimer.singleShot(20000, lambda: self._finish(None, "Zeitüberschreitung"))
        self._capture.start()

    def _frame(self, frame) -> None:
        if frame.isValid():
            image = frame.toImage()
            if not image.isNull():
                self._finish(image, "")

    def _finish(self, image, error) -> None:
        if self._capture is None:
            return
        self._capture.stop()
        self._capture.deleteLater()
        self._capture = None
        if image is not None:
            self.done.emit(image)
        else:
            self.failed.emit(error or "Unbekannter Fehler")


def screen_by_name(name: str):
    for s in QGuiApplication.screens():
        if s.name() == name:
            return s
    return None
