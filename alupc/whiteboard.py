"""Whiteboard für Monitor 2: Hintergrund zum Draufzeichnen (Stift, Marker, Radierer aus „Zeigen & Zeichnen“)."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QRadialGradient
from PySide6.QtWidgets import QWidget

# Schlüssel: (Name, dunkel?) – dunkel = helle Stiftfarbe passt besser
BACKGROUNDS: dict[str, tuple[str, bool]] = {
    "weiss": ("Weiß", False),
    "kariert": ("Kariert", False),
    "liniert": ("Liniert", False),
    "punkte": ("Punkteraster", False),
    "millimeter": ("Millimeterpapier", False),
    "koordinaten": ("Koordinatensystem", False),
    "noten": ("Notenlinien", False),
    "tafel": ("Tafel (grün)", True),
    "schwarz": ("Tafel (schwarz)", True),
    "blaupause": ("Blaupause", True),
}
DEFAULT = "weiss"


def is_dark(key: str) -> bool:
    return BACKGROUNDS.get(key, BACKGROUNDS[DEFAULT])[1]


def pen_color_for(key: str, current: str) -> str:
    """Passende Stiftfarbe: auf dunklen Tafeln Weiß statt Schwarz (und umgekehrt), sonst die gewählte."""
    c = QColor(current)
    if is_dark(key) and c.lightness() < 90:
        return "#ffffff"
    if not is_dark(key) and c.lightness() > 200:
        return "#111827"
    return current


def paint_background(p: QPainter, rect: QRectF, key: str) -> None:
    """Hintergrund zeichnen (auch für kleine Vorschauen). Rastergröße wächst mit der Höhe."""
    w, h = rect.width(), rect.height()
    unit = max(4.0, h / 24)  # Kästchen: 24 Reihen auf der Höhe
    paper = QColor("#fdfdfb")
    if key == "tafel":
        g = QRadialGradient(rect.center(), max(w, h) * 0.75)
        g.setColorAt(0, QColor("#2f5e46"))
        g.setColorAt(1, QColor("#1d3b2c"))
        p.fillRect(rect, g)
        return
    if key == "schwarz":
        g = QRadialGradient(rect.center(), max(w, h) * 0.75)
        g.setColorAt(0, QColor("#2a2d33"))
        g.setColorAt(1, QColor("#15171b"))
        p.fillRect(rect, g)
        return
    if key == "blaupause":
        p.fillRect(rect, QColor("#123a73"))
        _grid(p, rect, unit / 2, QColor(255, 255, 255, 26), 1)
        _grid(p, rect, unit * 2, QColor(255, 255, 255, 60), 1.2)
        return
    p.fillRect(rect, paper)
    if key == "kariert":
        _grid(p, rect, unit, QColor("#b9c6dc"), 1)
    elif key == "millimeter":
        _grid(p, rect, unit / 5, QColor(229, 120, 60, 45), 0.6)
        _grid(p, rect, unit, QColor(229, 120, 60, 110), 0.9)
        _grid(p, rect, unit * 5, QColor(229, 120, 60, 170), 1.3)
    elif key == "liniert":
        pen = QPen(QColor("#a9c1e6"), max(1.0, h / 900))
        p.setPen(pen)
        y = rect.top() + unit * 2.2
        while y < rect.bottom():
            p.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
            y += unit * 1.25
        p.setPen(QPen(QColor("#e8a0a0"), max(1.2, h / 700)))  # Rand links
        x = rect.left() + w * 0.08
        p.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))
    elif key == "punkte":
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#9aa7bd"))
        r = max(0.8, unit / 16)
        y = rect.top() + unit
        while y < rect.bottom():
            x = rect.left() + unit
            while x < rect.right():
                p.drawEllipse(QPointF(x, y), r, r)
                x += unit
            y += unit
    elif key == "koordinaten":
        _grid(p, rect, unit, QColor("#d3dbe8"), 1)
        axis = QPen(QColor("#1f2937"), max(1.5, h / 500))
        p.setPen(axis)
        cx = rect.left() + round(w / 2 / unit) * unit
        cy = rect.top() + round(h / 2 / unit) * unit
        p.drawLine(QPointF(rect.left(), cy), QPointF(rect.right(), cy))
        p.drawLine(QPointF(cx, rect.top()), QPointF(cx, rect.bottom()))
        a = unit * 0.45  # Pfeilspitzen
        p.drawLine(QPointF(rect.right() - 2, cy), QPointF(rect.right() - 2 - a, cy - a * 0.6))
        p.drawLine(QPointF(rect.right() - 2, cy), QPointF(rect.right() - 2 - a, cy + a * 0.6))
        p.drawLine(QPointF(cx, rect.top() + 2), QPointF(cx - a * 0.6, rect.top() + 2 + a))
        p.drawLine(QPointF(cx, rect.top() + 2), QPointF(cx + a * 0.6, rect.top() + 2 + a))
        if unit >= 14:  # Zahlen nur, wenn groß genug
            f = QFont()
            f.setPixelSize(int(unit * 0.42))
            p.setFont(f)
            p.setPen(QColor("#4b5563"))
            for i in range(-12, 13):
                if i == 0 or i % 2:
                    continue
                x = cx + i * unit
                if rect.left() < x < rect.right() - unit:
                    p.drawText(QRectF(x - unit, cy + 2, unit * 2, unit * 0.7), Qt.AlignHCenter | Qt.AlignTop, str(i))
                y = cy - i * unit
                if rect.top() + unit < y < rect.bottom():
                    p.drawText(QRectF(cx + 4, y - unit * 0.35, unit * 1.5, unit * 0.7), Qt.AlignLeft | Qt.AlignVCenter,
                               str(i))
    elif key == "noten":
        pen = QPen(QColor("#6b7280"), max(1.0, h / 800))
        p.setPen(pen)
        gap = unit * 0.55
        top = rect.top() + unit * 2
        while top + gap * 4 < rect.bottom() - unit:
            for i in range(5):
                y = top + i * gap
                p.drawLine(QPointF(rect.left() + w * 0.05, y), QPointF(rect.right() - w * 0.05, y))
            top += gap * 4 + unit * 1.6


def _grid(p: QPainter, rect: QRectF, step: float, color: QColor, width: float) -> None:
    if step < 2:
        return
    p.setPen(QPen(color, width))
    x = rect.left() + step
    while x < rect.right():
        p.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))
        x += step
    y = rect.top() + step
    while y < rect.bottom():
        p.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
        y += step


class WhiteboardSource(QWidget):
    """Quelle „whiteboard“ – nur der Hintergrund; gezeichnet wird darüber (Zeichen-Ebene von Monitor 2)."""

    def __init__(self, cfg: dict, parent=None):
        super().__init__(parent)
        self.background = cfg.get("background", DEFAULT) if cfg.get("background") in BACKGROUNDS else DEFAULT
        self.setAttribute(Qt.WA_OpaquePaintEvent)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        paint_background(p, QRectF(self.rect()), self.background)
        p.end()

    def stop(self):
        pass
