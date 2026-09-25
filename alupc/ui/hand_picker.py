"""Zwei Hände zum Anklicken: Finger wählen, angelernte Finger leuchten."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QTransform
from PySide6.QtWidgets import QWidget

from ..platform.base import FINGER_NAMES
from . import icons, theme

# (Finger, x, Länge, Winkel in Grad) für die rechte Hand, Koordinaten in einer 100×100-Box
RIGHT = [
    ("right-thumb", 22, 26, -48),
    ("right-index-finger", 38, 40, -8),
    ("right-middle-finger", 52, 44, 0),
    ("right-ring-finger", 66, 40, 7),
    ("right-little-finger", 79, 31, 15),
]


class HandPicker(QWidget):
    fingerClicked = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected = "right-index-finger"
        self.enrolled: set[str] = set()
        self.hover = ""
        self.setMouseTracking(True)
        self.setMinimumSize(360, 170)
        self.setCursor(Qt.PointingHandCursor)

    def set_selected(self, finger: str):
        self.selected = finger
        self.update()

    def set_enrolled(self, fingers):
        self.enrolled = set(fingers)
        self.update()

    # ------------------------------------------------------------ Geometrie
    def _hands(self) -> list[tuple[QRectF, bool]]:
        w, h = self.width(), self.height() - 22
        side = min(h, (w - 30) / 2)
        top = 4
        gap = (w - 2 * side) / 3
        return [(QRectF(gap, top, side, side), True), (QRectF(2 * gap + side, top, side, side), False)]

    def _fingers(self):
        """[(Finger, Pfad)] für beide Hände."""
        out = []
        for box, left in self._hands():
            s = box.width() / 100
            for key, x, length, angle in RIGHT:
                if left:
                    key = key.replace("right", "left")
                    x, angle = 100 - x, -angle
                width = 12 if "thumb" not in key else 13
                base = QPointF(box.x() + x * s, box.y() + (62 if "thumb" not in key else 72) * s)
                path = QPainterPath()
                path.addRoundedRect(QRectF(-width * s / 2, -length * s, width * s, length * s + 6 * s),
                                    width * s / 2, width * s / 2)
                t = QTransform()
                t.translate(base.x(), base.y())
                t.rotate(angle)
                out.append((key, t.map(path), t.map(QPointF(0, -length * s + width * s / 2))))
        return out

    def _palm(self, box: QRectF, left: bool) -> QPainterPath:
        s = box.width() / 100
        path = QPainterPath()
        path.addRoundedRect(QRectF(box.x() + 28 * s, box.y() + 56 * s, 58 * s, 40 * s), 16 * s, 16 * s)
        if left:  # linke Hand = gespiegelte rechte
            path = QTransform().translate(2 * box.center().x(), 0).scale(-1, 1).map(path)
        return path

    def finger_at(self, pos: QPointF) -> str:
        for key, path, _tip in self._fingers():
            if path.contains(pos):
                return key
        return ""

    # ------------------------------------------------------------ Maus
    def mouseMoveEvent(self, e):
        hover = self.finger_at(e.position())
        if hover != self.hover:
            self.hover = hover
            self.setToolTip(FINGER_NAMES.get(hover, ""))
            self.update()

    def leaveEvent(self, _e):
        self.hover = ""
        self.update()

    def mousePressEvent(self, e):
        key = self.finger_at(e.position())
        if key and e.button() == Qt.LeftButton:
            self.set_selected(key)
            self.fingerClicked.emit(key)

    # ------------------------------------------------------------ Zeichnen
    def paintEvent(self, _e):
        t = theme.current()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        skin = QColor(t.surface2)
        edge = QColor(t.border)
        accent = QColor(t.accent)
        ok = QColor(t.success)
        for box, left in self._hands():
            p.setPen(QPen(edge, 1.5))
            p.setBrush(skin)
            p.drawPath(self._palm(box, left))
        for key, path, tip in self._fingers():
            done = key in self.enrolled
            fill = QColor(ok if done else skin)
            if done:
                fill.setAlphaF(0.85)
            if key == self.hover and not done:
                fill = QColor(accent)
                fill.setAlphaF(0.35)
            p.setBrush(fill)
            p.setPen(QPen(accent if key == self.selected else edge, 3 if key == self.selected else 1.5))
            p.drawPath(path)
            if done:
                r = 7
                icons.paint(p, "check", QRectF(tip.x() - r, tip.y() - r, 2 * r, 2 * r), "#ffffff", 2.4)
        # Beschriftung unter den Händen
        f = QFont()
        f.setPixelSize(12)
        p.setFont(f)
        p.setPen(QColor(t.muted))
        for box, left in self._hands():
            p.drawText(QRectF(box.x(), self.height() - 20, box.width(), 18), Qt.AlignCenter,
                       "Linke Hand" if left else "Rechte Hand")
        p.end()


def finger_keys_from(backend, keys) -> set[str]:
    """Angelernte Finger als Finger-Namen – auch beim Modul am Adapter (dort sind es Speicherplätze)."""
    result = set()
    for k in keys:
        if k in FINGER_NAMES:
            result.add(k)
        elif str(k).startswith("platz:"):
            try:
                from ..platform.zw_fingerprint import current_user, load_slots

                info = load_slots().get(str(k).split(":", 1)[1], {})
                if info.get("finger") and info.get("user") in (None, current_user()):
                    result.add(info["finger"])
            except Exception:  # noqa: BLE001
                pass
    return result

