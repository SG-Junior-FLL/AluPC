"""Mauszeiger: Position verfolgen, beim Spiegeln ins Bild zeichnen, auf Monitor 1 festhalten.

* `CursorTracker` meldet die Mausposition (Windows/X11: abfragen; KDE/Wayland: KWin-Skript).
* `paint_cursor` zeichnet den echten Zeiger (Windows/X11) oder einen Standardpfeil.
* `CursorGuard` hält die Maus auf Monitor 1, solange Monitor 2 nicht „Erweitern“ ist.
"""

from __future__ import annotations

import sys

from PySide6.QtCore import QObject, QPoint, QPointF, QRect, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QCursor, QGuiApplication, QPainter, QPainterPath, QPen

from .platform.linux_display import is_wayland

IS_WINDOWS = sys.platform.startswith("win")


def wayland_kde() -> bool:
    import os

    return sys.platform.startswith("linux") and is_wayland() and \
        "KDE" in os.environ.get("XDG_CURRENT_DESKTOP", "").upper()


# =========================================================================== Position
class CursorTracker(QObject):
    """Meldet Mausbewegungen, solange jemand zuhört (`acquire`/`release`)."""

    moved = Signal(QPoint)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pos: QPoint | None = None
        self.users = 0
        self.method = "keine"
        self._timer = QTimer(self, interval=16)  # ~60 Abfragen/s
        self._timer.timeout.connect(self._poll)
        self._kwin = None

    def acquire(self) -> None:
        self.users += 1
        if self.users == 1:
            self._start()

    def release(self) -> None:
        self.users = max(0, self.users - 1)
        if self.users == 0:
            self._stop()

    def _start(self):
        if is_wayland():
            # Unter Wayland liefert QCursor.pos() nur über eigenen Fenstern etwas Brauchbares
            if wayland_kde():
                try:
                    from .platform.kwin_cursor import CursorReceiver

                    self._kwin = CursorReceiver(self)
                    self._kwin.moved.connect(self._set)
                    self._kwin.start()
                    self.method = "kwin"
                    return
                except Exception:  # noqa: BLE001
                    if self._kwin is not None:
                        self._kwin.stop()  # D-Bus-Verbindung und Thread nicht liegen lassen
                    self._kwin = None
            self.method = "keine"
            return
        self.method = "abfragen"
        self._timer.start()
        self._poll()

    def _stop(self):
        self._timer.stop()
        if self._kwin is not None:
            self._kwin.stop()
            self._kwin = None
        self.method = "keine"

    def _poll(self):
        self._set(QCursor.pos())

    def _set(self, pos: QPoint):
        if pos != self.pos:
            self.pos = QPoint(pos)
            self.moved.emit(self.pos)

    def available(self) -> bool:
        return self.method != "keine"

    def shutdown(self):
        self.users = 0
        self._stop()


_tracker: CursorTracker | None = None


def tracker() -> CursorTracker:
    global _tracker
    if _tracker is None:
        _tracker = CursorTracker()
    return _tracker


# =========================================================================== Zeichnen
ARROW = [(0, 0), (0, 17), (4.2, 13.2), (7, 19.5), (9.6, 18.4), (6.9, 12.2), (12.3, 12.2)]


def paint_arrow(p: QPainter, tip: QPointF, scale: float) -> None:
    """Standard-Mauspfeil (weiß mit schwarzem Rand), Spitze bei `tip`."""
    path = QPainterPath(QPointF(tip.x() + ARROW[0][0] * scale, tip.y() + ARROW[0][1] * scale))
    for x, y in ARROW[1:]:
        path.lineTo(tip.x() + x * scale, tip.y() + y * scale)
    path.closeSubpath()
    p.save()
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(QPen(QColor(0, 0, 0), max(1.0, 1.1 * scale), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(QColor(255, 255, 255))
    p.drawPath(path)
    p.restore()


def paint_cursor(p: QPainter, pos: QPointF, scale: float, device_ratio: float = 1.0) -> None:
    """Echten Mauszeiger (falls abfragbar) oder Pfeil zeichnen. `pos` = Zeigerspitze im Bild,
    `scale` = Vergrößerung Monitor → Bild, `device_ratio` = Bildpunkte je Monitor-Einheit."""
    from .platform.cursor_native import cursor_image

    shape = cursor_image()
    if shape is None:
        paint_arrow(p, pos, scale)
        return
    image, (hx, hy), _key = shape
    k = scale / max(0.1, device_ratio)
    target = QRectF(pos.x() - hx * k, pos.y() - hy * k, image.width() * k, image.height() * k)
    p.save()
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.drawImage(target, image)
    p.restore()


def map_to_image(pos: QPoint, screen_rect: QRect, image_rect: QRectF) -> QPointF | None:
    """Mausposition auf dem Monitor → Punkt im (eingepassten) Bild dieses Monitors."""
    if not screen_rect.contains(pos) or screen_rect.width() <= 0 or screen_rect.height() <= 0:
        return None
    rx = (pos.x() - screen_rect.x()) / screen_rect.width()
    ry = (pos.y() - screen_rect.y()) / screen_rect.height()
    return QPointF(image_rect.x() + rx * image_rect.width(), image_rect.y() + ry * image_rect.height())


# =========================================================================== Festhalten
class CursorGuard(QObject):
    """Hält die Maus auf Monitor 1 (Windows: ClipCursor, X11: unsichtbare Wände + Nachkorrektur).
    Unter Wayland dürfen Programme das nicht – dort bleibt die Maus frei (`supported` = False)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.active = False
        self.main_rect: QRect | None = None
        self.out_rect: QRect | None = None
        self.main_name = ""
        self._barriers = None
        self.supported = IS_WINDOWS or (sys.platform.startswith("linux") and not is_wayland())
        # Windows setzt die Begrenzung bei vielen Gelegenheiten zurück (Fensterwechsel, Strg+Alt+Entf …)
        self._timer = QTimer(self, interval=250)
        self._timer.timeout.connect(self._enforce)

    def set_active(self, on: bool, main_screen=None, out_screen=None) -> None:
        on = bool(on and self.supported and main_screen is not None and out_screen is not None
                  and main_screen is not out_screen
                  and not main_screen.geometry().intersects(out_screen.geometry()))  # System-Spiegeln
        if on:
            self.main_rect = main_screen.geometry()
            self.out_rect = out_screen.geometry()
            self.main_name = main_screen.name()
            self._dpr = out_screen.devicePixelRatio()
        if on == self.active and not on:
            return
        self.active = on
        if on:
            self._move_home()
            self._apply()
            self._timer.start()
        else:
            self._timer.stop()
            self._release()

    def _move_home(self):
        """Steht die Maus gerade auf Monitor 2, zurück in die Mitte von Monitor 1."""
        pos = QCursor.pos()
        if self.out_rect is not None and self.out_rect.contains(pos) and self.main_rect is not None:
            QCursor.setPos(self.main_rect.center())

    def _native_out_rect(self):
        r, dpr = self.out_rect, getattr(self, "_dpr", 1.0) or 1.0
        # Qt verschiebt den Ursprung eines Monitors nicht, nur die Größe wird skaliert
        return (r.x(), r.y(), round(r.width() * dpr), round(r.height() * dpr))

    def _apply(self):
        try:
            if IS_WINDOWS:
                from .platform.cursor_native import clip_cursor
                from .platform.windows_display import monitor_rect

                rect = monitor_rect(self.main_name)
                if rect:
                    clip_cursor(rect)
            else:
                from .platform.cursor_native import X11Barriers, is_x11

                if not is_x11():
                    return

                if self._barriers is None:
                    self._barriers = X11Barriers()
                self._barriers.set(self._native_out_rect())
        except Exception:  # noqa: BLE001
            pass

    def _enforce(self):
        if not self.active:
            return
        if IS_WINDOWS:
            self._apply()
        # Sicherheitsnetz für alle Systeme: Maus doch auf Monitor 2 (z. B. per Tastatur verschoben)?
        pos = QCursor.pos()
        if self.out_rect is not None and self.out_rect.contains(pos) and self.main_rect is not None:
            m = self.main_rect
            QCursor.setPos(QPoint(min(max(pos.x(), m.left()), m.right()), min(max(pos.y(), m.top()), m.bottom())))

    def _release(self):
        try:
            if IS_WINDOWS:
                from .platform.cursor_native import clip_cursor

                clip_cursor(None)
            elif self._barriers is not None:
                self._barriers.clear()
        except Exception:  # noqa: BLE001
            pass

    def shutdown(self):
        self._timer.stop()
        if self.active:
            self.active = False
            self._release()


def screen_at(pos: QPoint):
    for s in QGuiApplication.screens():
        if s.geometry().contains(pos):
            return s
    return None
