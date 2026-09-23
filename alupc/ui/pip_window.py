"""Bild-in-Bild: kleines Fenster auf Monitor 1, das zeigt, was auf Monitor 2 läuft."""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import QSizeGrip, QWidget

from ..sources import FrameView, ScreenSource


class PipView(FrameView):
    def __init__(self, controller, parent=None):
        super().__init__("contain", parent)
        self.controller = controller

    def paintEvent(self, event):
        super().paintEvent(event)
        badges = []
        if self.controller.privacy:
            badges.append(("SCHWARZ", "#444444"))
        if self.controller.frozen:
            badges.append(("EINGEFROREN", "#c0392b"))
        if not badges:
            return
        p = QPainter(self)
        font = QFont()
        font.setBold(True)
        font.setPixelSize(max(11, self.height() // 14))
        p.setFont(font)
        x = 8
        for text, color in badges:
            w = p.fontMetrics().horizontalAdvance(text) + 14
            h = p.fontMetrics().height() + 6
            p.fillRect(x, 8, w, h, QColor(color))
            p.setPen(Qt.white)
            p.drawText(x, 8, w, h, Qt.AlignCenter, text)
            x += w + 6
        p.end()


class PipWindow(QWidget):
    def __init__(self, controller):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.controller = controller
        self.setWindowTitle("AluPC – Bild-in-Bild")
        self.view = PipView(controller, self)
        self.grip = QSizeGrip(self)
        self.grip.resize(16, 16)
        self.live_capture: ScreenSource | None = None
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self._drag: QPoint | None = None
        self.setToolTip("Ziehen zum Verschieben, Ecke unten rechts zum Vergrößern, Doppelklick schließt")
        self.apply_settings()
        controller.changed.connect(self.refresh)

    def apply_settings(self):
        cfg = self.controller.config["pip"]
        width = int(cfg.get("width", 480))
        self.resize(width, int(width * 9 / 16))
        self.setWindowOpacity(float(cfg.get("opacity", 1.0)))
        self.timer.setInterval(int(1000 / max(1, int(cfg.get("fps", 10)))))

    def toggle(self):
        if self.isVisible():
            self.hide()
        else:
            self.show_on_main()

    def show_on_main(self):
        screen = self.controller.main_screen()
        if screen is not None:
            geo = screen.availableGeometry()
            self.move(geo.right() - self.width() - 24, geo.bottom() - self.height() - 24)
        self.show()
        self.timer.start()
        self.refresh()

    def hideEvent(self, event):
        self.timer.stop()
        self._stop_live()
        super().hideEvent(event)

    def _stop_live(self):
        if self.live_capture is not None:
            self.live_capture.stop()
            self.live_capture.deleteLater()
            self.live_capture = None

    def refresh(self):
        if not self.isVisible():
            return
        out = self.controller.output
        if out.isVisible():
            # AluPC zeigt selbst etwas → einfach das Ausgabefenster abfotografieren
            self._stop_live()
            self.view.set_image(out.grab())
            return
        screen = self.controller.output_screen()
        if screen is None:
            self._stop_live()
            self.view.set_image(None)
            self.view.set_message("Kein zweiter Monitor")
            return
        # Normaler Desktop auf Monitor 2 → Monitor 2 live aufnehmen
        if self.live_capture is None:
            self.live_capture = ScreenSource({"screen_name": screen.name()})
            self.live_capture.sink.videoFrameChanged.connect(self._live_frame)
        self.view.update()

    def _live_frame(self, frame):
        if frame.isValid() and not self.controller.output.isVisible():
            self.view.set_image(frame.toImage())

    # ------------------------------------------------------------ Maus
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            handle = self.windowHandle()
            # Unter Wayland darf nur der Fenstermanager verschieben
            if handle is not None and handle.startSystemMove():
                return
            self._drag = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._drag is not None:
            self.move(event.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, _event):
        self._drag = None

    def mouseDoubleClickEvent(self, _event):
        self.hide()
        self.controller.changed.emit()

    def resizeEvent(self, _event):
        self.view.setGeometry(self.rect())
        self.grip.move(self.width() - self.grip.width(), self.height() - self.grip.height())
        self.grip.raise_()
