"""Bild-in-Bild: kleines Fenster auf Monitor 1, das zeigt, was auf Monitor 2 läuft."""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QSizeGrip, QWidget

from ..sources import FrameView, ScreenSource
from . import theme


class PipView(FrameView):
    def __init__(self, controller, parent=None):
        super().__init__("contain", parent)
        self.controller = controller

    def paintEvent(self, event):
        super().paintEvent(event)
        t = theme.current()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        c = self.controller
        badges = [("MONITOR 2", t.accent)]
        if c.privacy:
            badges.append(("SCHWARZ", "#64748b"))
        if c.frozen:
            badges.append(("STANDBILD", "#0ea5e9"))
        font = QFont()
        font.setBold(True)
        font.setPixelSize(max(10, min(13, self.height() // 16)))
        p.setFont(font)
        x = 10
        for text, color in badges:
            w = p.fontMetrics().horizontalAdvance(text) + 18
            h = p.fontMetrics().height() + 8
            bg = QColor(color)
            bg.setAlphaF(0.92)
            p.setPen(Qt.NoPen)
            p.setBrush(bg)
            p.drawRoundedRect(QRectF(x, 10, w, h), h / 2, h / 2)
            p.setPen(Qt.white)
            p.drawText(QRectF(x, 10, w, h), Qt.AlignCenter, text)
            x += w + 6
        # Rahmen in Akzentfarbe (Standbild: hellblau)
        border = QColor("#0ea5e9" if c.frozen else t.accent)
        p.setPen(QPen(border, 3))
        p.setBrush(Qt.NoBrush)
        p.drawRect(QRectF(self.rect()).adjusted(1.5, 1.5, -1.5, -1.5))
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
        self.timer.setTimerType(Qt.PreciseTimer)
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
            from ..output_window import grab_scaled

            self.view.set_image(grab_scaled(out, self.view.size() * self.view.devicePixelRatioF()))
            return
        screen = self.controller.output_screen()
        if screen is None:
            self._stop_live()
            self.view.set_image(None)
            self.view.set_message("Kein zweiter Monitor")
            return
        # Normaler Desktop auf Monitor 2 → Monitor 2 live aufnehmen
        if self.live_capture is None:
            fps = int(self.controller.config["pip"].get("fps", 20))
            self.live_capture = ScreenSource({"screen_name": screen.name(), "fps": fps})
        image = self.live_capture.image()  # nur so oft umwandeln, wie Bild-in-Bild aktualisiert
        if image is not None:
            self.view.set_image(image)
        else:
            self.view.update()

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
