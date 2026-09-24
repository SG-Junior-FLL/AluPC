"""Vollbild-Fenster auf Monitor 2 mit Standbild- und Sichtschutz-Ebene."""

from __future__ import annotations

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QGuiApplication, QImage, QPixmap
from PySide6.QtMultimedia import QMediaCaptureSession, QScreenCapture, QVideoSink
from PySide6.QtWidgets import QWidget

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


class FreezeLayer(FrameView):
    """Eingefrorenes Bild – optional mit kleinem Schneeflocken-Symbol oben rechts."""

    def __init__(self, parent=None):
        super().__init__("stretch", parent)
        self.badge = True

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self.badge or self.image() is None:
            return
        from PySide6.QtCore import QRectF
        from PySide6.QtGui import QColor, QPainter

        from .ui import icons

        side = max(28, min(56, self.height() // 22))
        margin = side // 2
        rect = QRectF(self.width() - side - margin, margin, side, side)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(14, 165, 233, 215))
        p.drawEllipse(rect)
        icons.paint(p, "snowflake", rect.adjusted(side * 0.2, side * 0.2, -side * 0.2, -side * 0.2),
                    "#ffffff", 2.2)
        p.end()


class OutputWindow(QWidget):
    # Titel wird auch von KWin-Skripten benutzt, um dieses Fenster zu finden
    TITLE = "AluPC – Monitor 2"

    def __init__(self):
        super().__init__(None, Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
                         | Qt.WindowDoesNotAcceptFocus)
        self.setWindowTitle(self.TITLE)
        self.setAutoFillBackground(True)
        pal = self.palette()
        pal.setColor(self.backgroundRole(), Qt.black)
        self.setPalette(pal)
        self.content: QWidget | None = None
        self.freeze_layer = FreezeLayer(self)
        self.freeze_layer.hide()
        self.privacy_layer = PrivacyLayer(self)
        self.privacy_layer.hide()
        self.content_active = False
        self.screen_name = ""
        self.fade_enabled = True
        self._fades: list[QWidget] = []
        self.screensaver: QWidget | None = None
        self.hide_taskbar = True
        self._placed_on: tuple | None = None
        self._kde_done = False
        self.after_raise: list = []  # z. B. Laserpointer: muss über diesem Fenster bleiben
        from .platform.window_tools import SecondaryTaskbar

        self.taskbar = SecondaryTaskbar()
        # Wächter: holt das Fenster zurück, falls es verdeckt, minimiert (Win+D) oder versteckt wurde
        self.watchdog = QTimer(self, interval=1000)
        self.watchdog.timeout.connect(self._watch)
        self.watchdog.start()

    # ------------------------------------------------------------ Inhalt
    def set_content(self, widget: QWidget | None, transition: tuple[str, int] | None = None) -> None:
        """Neuen Inhalt zeigen. `transition` = (Art, Millisekunden), siehe transitions.py."""
        kind, ms = transition or (("blende", 350) if self.fade_enabled else ("schnitt", 0))
        if kind != "schnitt" and self.isVisible() and self.content is not None and widget is not None:
            self._transition(self.content.grab(), kind, ms)
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

    def _transition(self, old: QPixmap, kind: str, ms: int) -> None:
        """Altes Bild über das neue legen und je nach Art wegnehmen (weicher Wechsel)."""
        from .transitions import TransitionLayer

        if old.isNull():
            return
        for layer in list(self._fades):  # laufenden Übergang sofort beenden
            layer.anim.stop()
            layer.hide()
            layer.deleteLater()
        self._fades.clear()
        layer = TransitionLayer(old, kind, self)
        layer.setGeometry(self.rect())
        layer.show()
        layer.raise_()
        for top in (self.freeze_layer, self.screensaver, self.privacy_layer):
            if top is not None and top.isVisible():
                top.raise_()

        def finished():
            if layer in self._fades:
                self._fades.remove(layer)
            layer.deleteLater()

        layer.anim.finished.connect(finished)
        self._fades.append(layer)
        layer.start(ms)

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
            if self.screensaver is not None:
                self.screensaver.raise_()
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

    def set_screensaver(self, widget: QWidget | None) -> None:
        """Bildschirmschoner über Inhalt und Standbild legen (Sichtschutz bleibt ganz oben)."""
        if self.screensaver is not None:
            self.screensaver.stop()
            self.screensaver.hide()
            self.screensaver.deleteLater()
        self.screensaver = widget
        if widget is not None:
            widget.setParent(self)
            widget.setGeometry(self.rect())
            widget.show()
            widget.raise_()
            if self.privacy_layer.isVisible():
                self.privacy_layer.raise_()
        self.update_visibility()

    def needed(self) -> bool:
        return (self.content_active or self.freeze_layer.isVisible() or self.privacy_layer.isVisible()
                or self.screensaver is not None)

    # ------------------------------------------------------------ Monitor
    def place_on(self, screen) -> None:
        self.screen_name = screen.name() if screen else ""
        if screen is None:
            self._placed_on = None
            self.hide()
            self.taskbar.restore()
            return
        key = (screen.name(), screen.geometry().getRect())
        if key == self._placed_on and self.windowHandle() is not None:
            self.update_visibility()  # gleicher Monitor, gleiche Größe → nichts neu aufbauen
            return
        self._placed_on = key
        if self.isVisible():
            self.hide()
        self.setGeometry(screen.geometry())
        self.create()
        handle = self.windowHandle()
        if handle is not None:
            handle.setScreen(screen)
        self.update_visibility()

    def update_visibility(self) -> None:
        if self.needed() and self.screen_name:
            self.bring_to_front()
        else:
            if self.isVisible():
                self.hide()
            self.taskbar.restore()

    def bring_to_front(self) -> None:
        """Sicher sichtbar machen: Vollbild, ganz oben, auch über der Taskleiste."""
        from .platform.window_tools import keep_on_top

        first = not self.isVisible()
        if first or self.isMinimized() or not self.isFullScreen():
            self.showFullScreen()
        self.raise_()
        keep_on_top(self)
        if self.hide_taskbar:
            self.taskbar.hide_on(self)
        if not self._kde_done:
            self._kde_done = True
            self._kde_keep_above()
        for callback in self.after_raise:
            callback()

    def _kde_keep_above(self) -> None:
        from .platform.window_tools import kde_keep_above
        from .ui.util import run_async

        run_async(lambda: kde_keep_above(self.TITLE), None, lambda _e: None)

    def _watch(self) -> None:
        if self.needed() and self.screen_name:
            if not self.isVisible() or self.isMinimized() or not self.isFullScreen():
                self._kde_done = False
            self.bring_to_front()

    def hideEvent(self, event):
        self._kde_done = False
        super().hideEvent(event)

    def shutdown(self) -> None:
        self.watchdog.stop()
        self.taskbar.restore()

    def resizeEvent(self, _event):
        for w in (self.content, self.freeze_layer, self.privacy_layer, self.screensaver, *self._fades):
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
        from .sources import _kwin_allowed

        if _kwin_allowed(screen.name()):
            # KDE/Wayland: direkt über KWin, ohne Nachfrage
            from .platform.kwin_capture import grab_once
            from .ui.util import run_async

            name = screen.name()
            run_async(lambda: grab_once(name), self.done.emit, lambda _e: self._start_capture(screen))
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
