"""Bild-in-Bild: kleines Fenster auf Monitor 1, das zeigt, was auf Monitor 2 läuft."""

from __future__ import annotations

import os
import sys

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
        # Linux: kein Qt.Tool – KWin behandelt solche Hilfsfenster unter Wayland anders (nicht zuverlässig oben)
        kind = Qt.Window if sys.platform.startswith("linux") else Qt.Tool
        super().__init__(None, kind | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.controller = controller
        self._pin: str | None = None  # aktives KWin-Skript („immer oben“)
        self._pin_wanted = False
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
        target = None
        if screen is not None:
            geo = screen.availableGeometry()
            target = (geo.right() - self.width() - 24, geo.bottom() - self.height() - 24)
            self.move(*target)
        self.show()
        self.timer.start()
        self.refresh()
        if target is not None:
            self._place_wayland(*target)
        self._stay_on_top()

    def _stay_on_top(self) -> None:
        """Immer vor anderen Fenstern. Qt bittet nur darum – KDE (Wayland) ignoriert das, Windows lässt andere
        „immer oben“-Fenster darüber. Deshalb: KDE per KWin-Skript, Windows regelmäßig nach vorne."""
        from ..platform.window_tools import keep_on_top

        keep_on_top(self)
        if sys.platform.startswith("linux") and not self._pin_wanted:
            from ..platform.window_tools import kde_pin_above
            from .util import run_async

            self._pin_wanted = True

            def started(token):
                if self._pin_wanted and self._pin is None:
                    self._pin = token
                else:  # inzwischen wieder zu
                    self._unpin_token(token)

            caption = self.windowTitle()  # Teil genügt: KWin hängt bei Doppelten „<2>“ an
            run_async(lambda: kde_pin_above(caption), started, lambda _e: None)

    def _unpin(self) -> None:
        self._pin_wanted = False
        token, self._pin = self._pin, None
        self._unpin_token(token)

    def shutdown(self) -> None:
        """Beim Beenden: KWin-Skript sofort entfernen (nicht im Hintergrund – das Programm ist gleich weg)."""
        self._pin_wanted = False
        token, self._pin = self._pin, None
        if token:
            from ..platform.window_tools import kde_unpin

            kde_unpin(token)

    @staticmethod
    def _unpin_token(token) -> None:
        if token:
            from ..platform.window_tools import kde_unpin
            from .util import run_async

            run_async(lambda: kde_unpin(token), lambda _r: None, lambda _e: None)

    def _place_wayland(self, x: int, y: int) -> None:
        """Wayland: Programme dürfen ihr Fenster nicht selbst hinlegen → KDE (KWin) bitten, es unten rechts auf
        Monitor 1 zu platzieren (kurz nach dem Anzeigen, wenn KWin das Fenster kennt)."""
        from ..platform.linux_display import is_wayland

        if not sys.platform.startswith("linux") or not is_wayland() or "KDE" not in \
                os.environ.get("XDG_CURRENT_DESKTOP", "").upper():
            return
        from .util import run_async

        def place():
            from ..platform.linux_windows import kwin_place_window

            return kwin_place_window(self.windowTitle(), x, y, self.width(), self.height())

        QTimer.singleShot(250, lambda: run_async(place, lambda _r: None, lambda _e: None))

    def hideEvent(self, event):
        self.timer.stop()
        self._stop_live()
        self._unpin()
        super().hideEvent(event)

    def _stop_live(self):
        if self.live_capture is not None:
            self.live_capture.stop()
            self.live_capture.deleteLater()
            self.live_capture = None

    def refresh(self):
        if not self.isVisible():
            return
        if sys.platform.startswith("win"):  # Windows: andere „immer oben“-Fenster nicht darüber lassen
            import time

            now = time.monotonic()
            if now - getattr(self, "_top_at", 0.0) > 2:
                self._top_at = now
                from ..platform.window_tools import keep_on_top

                keep_on_top(self)
        out = self.controller.output
        if out.isVisible():
            # AluPC zeigt selbst etwas → einfach das Ausgabefenster abfotografieren
            self._stop_live()
            from ..output_window import grab_scaled

            from ..laser import draw_overlay

            image = grab_scaled(out, self.view.size() * self.view.devicePixelRatioF())
            draw_overlay(self.controller, image)  # Zeichnungen/Laser liegen in einem eigenen Fenster darüber
            self.view.set_image(image)
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
