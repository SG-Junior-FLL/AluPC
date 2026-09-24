"""Selbst gezeichnete Linien-Symbole – überall gleich scharf, egal ob Kubuntu oder Windows."""

from __future__ import annotations

import math
from functools import lru_cache

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap


def _monitor(p, x, y, w, h):
    p.drawRoundedRect(QRectF(x, y, w, h), 1.6, 1.6)


def _arrow(p, x1, y1, x2, y2, head=2.6, both=False):
    p.drawLine(QPointF(x1, y1), QPointF(x2, y2))
    ends = [(x1, y1, x2, y2)] + ([(x2, y2, x1, y1)] if both else [])
    for ax, ay, bx, by in ends:
        ang = math.atan2(by - ay, bx - ax)
        for side in (1, -1):
            a2 = ang + math.pi - side * math.radians(38)
            p.drawLine(QPointF(bx, by), QPointF(bx + head * math.cos(a2), by + head * math.sin(a2)))


def _draw(name: str, p: QPainter, color: QColor):
    """Zeichnet in einem 24×24-Raster (Stil ähnlich „Lucide“)."""
    fill = QColor(color)
    if name == "monitor":
        _monitor(p, 3, 4, 18, 12)
        p.drawLine(QPointF(12, 16), QPointF(12, 20))
        p.drawLine(QPointF(8, 20), QPointF(16, 20))
    elif name == "mirror":
        _monitor(p, 1.5, 4, 9, 7)
        _monitor(p, 13.5, 4, 9, 7)
        p.drawLine(QPointF(6, 11), QPointF(6, 13))
        p.drawLine(QPointF(18, 11), QPointF(18, 13))
        _arrow(p, 7, 18, 17, 18, both=True)
    elif name == "extend":
        _monitor(p, 1.5, 5, 11, 9)
        pen = p.pen()
        dashed = QPen(pen)
        dashed.setDashPattern([2, 1.6])
        p.setPen(dashed)
        _monitor(p, 13.5, 5, 9, 9)
        p.setPen(pen)
        p.drawLine(QPointF(7, 14), QPointF(7, 18))
        p.drawLine(QPointF(4, 18.5), QPointF(10, 18.5))
        _arrow(p, 15, 9.5, 20.5, 9.5, head=2.2)
    elif name == "camera":
        p.drawRoundedRect(QRectF(2, 6.5, 13.5, 11), 2.5, 2.5)
        path = QPainterPath(QPointF(15.5, 10.5))
        path.lineTo(21.5, 7)
        path.lineTo(21.5, 17)
        path.lineTo(15.5, 13.5)
        p.drawPath(path)
    elif name == "window":
        p.drawRoundedRect(QRectF(3, 4, 18, 16), 2.5, 2.5)
        p.drawLine(QPointF(3, 9), QPointF(21, 9))
        p.setBrush(fill)
        for x in (6, 8.8):
            p.drawEllipse(QPointF(x, 6.5), 0.6, 0.6)
        p.setBrush(Qt.NoBrush)
    elif name == "globe":
        p.drawEllipse(QPointF(12, 12), 9, 9)
        p.drawEllipse(QPointF(12, 12), 4, 9)
        p.drawLine(QPointF(3, 12), QPointF(21, 12))
    elif name == "image":
        p.drawRoundedRect(QRectF(3, 3, 18, 18), 2.5, 2.5)
        p.drawEllipse(QPointF(9, 9), 1.8, 1.8)
        path = QPainterPath(QPointF(21, 15))
        path.lineTo(16, 10)
        path.lineTo(5, 21)
        p.drawPath(path)
    elif name == "scenes":
        p.drawRoundedRect(QRectF(3, 3, 18, 18), 2.5, 2.5)
        p.drawLine(QPointF(12, 3), QPointF(12, 21))
        p.drawLine(QPointF(12, 12), QPointF(21, 12))
    elif name == "eye_off":
        path = QPainterPath(QPointF(2.5, 12))
        path.quadTo(12, 2.5, 21.5, 12)
        path.quadTo(12, 21.5, 2.5, 12)
        p.drawPath(path)
        p.drawEllipse(QPointF(12, 12), 3, 3)
        p.drawLine(QPointF(4, 3.5), QPointF(20, 20.5))
    elif name == "snowflake":
        for i in range(6):
            a = math.radians(90 + i * 60)
            dx, dy = math.cos(a), -math.sin(a)
            p.drawLine(QPointF(12, 12), QPointF(12 + 9.5 * dx, 12 + 9.5 * dy))
            bx, by = 12 + 6.3 * dx, 12 + 6.3 * dy
            for side in (-1, 1):
                b = a + side * math.radians(40)
                p.drawLine(QPointF(bx, by), QPointF(bx + 3 * math.cos(b), by - 3 * math.sin(b)))
    elif name == "pip":
        p.drawRoundedRect(QRectF(2, 4, 20, 16), 2.5, 2.5)
        p.setBrush(fill)
        p.drawRoundedRect(QRectF(12, 11, 7, 6), 1.2, 1.2)
        p.setBrush(Qt.NoBrush)
    elif name == "home":
        path = QPainterPath(QPointF(3, 10.5))
        path.lineTo(12, 3)
        path.lineTo(21, 10.5)
        p.drawPath(path)
        path = QPainterPath(QPointF(5.5, 9))
        path.lineTo(5.5, 20.5)
        path.lineTo(18.5, 20.5)
        path.lineTo(18.5, 9)
        p.drawPath(path)
        p.drawLine(QPointF(10, 20.5), QPointF(10, 14.5))
        p.drawLine(QPointF(14, 14.5), QPointF(14, 20.5))
        p.drawLine(QPointF(10, 14.5), QPointF(14, 14.5))
    elif name == "sliders":
        for y, x in ((6, 9), (12, 15.5), (18, 7)):
            p.drawLine(QPointF(3.5, y), QPointF(x - 2.2, y))
            p.drawLine(QPointF(x + 2.2, y), QPointF(20.5, y))
            p.drawEllipse(QPointF(x, y), 2.2, 2.2)
    elif name == "fingerprint":
        # Nach unten offene Bögen wie Papillarlinien
        def arc_path(r, start, span, extend_left=0.0, extend_right=0.0):
            rect = QRectF(12 - r, 12 - r, 2 * r, 2 * r)
            path = QPainterPath()
            path.arcMoveTo(rect, start)
            if extend_right:
                pt = path.currentPosition()
                path.moveTo(pt.x(), pt.y() + extend_right)
                path.lineTo(pt)
            path.arcTo(rect, start, span)
            if extend_left:
                pt = path.currentPosition()
                path.lineTo(pt.x(), pt.y() + extend_left)
            p.drawPath(path)

        arc_path(9.5, 20, 140)
        arc_path(6.5, 0, 180, extend_left=6.5, extend_right=3)
        arc_path(3.5, 0, 180, extend_left=4, extend_right=7.5)
        p.drawLine(QPointF(12, 12), QPointF(12, 21))
    elif name == "lock":
        p.drawRoundedRect(QRectF(5, 10.5, 14, 10.5), 2.5, 2.5)
        path = QPainterPath(QPointF(8, 10.5))
        path.lineTo(8, 7.5)
        path.arcTo(QRectF(8, 3, 8, 9), 180, -180)
        path.lineTo(16, 10.5)
        p.drawPath(path)
        p.drawLine(QPointF(12, 14.5), QPointF(12, 17))
    elif name == "plus":
        p.drawLine(QPointF(12, 5), QPointF(12, 19))
        p.drawLine(QPointF(5, 12), QPointF(19, 12))
    elif name == "edit":
        path = QPainterPath(QPointF(4, 20))
        path.lineTo(4.8, 16)
        path.lineTo(15.5, 5.3)
        path.lineTo(18.7, 8.5)
        path.lineTo(8, 19.2)
        path.closeSubpath()
        p.drawPath(path)
        p.drawLine(QPointF(13.5, 7.3), QPointF(16.7, 10.5))
    elif name == "copy":
        p.drawRoundedRect(QRectF(8, 8, 13, 13), 2, 2)
        path = QPainterPath(QPointF(16, 8))
        path.lineTo(16, 5)
        path.quadTo(16, 3, 14, 3)
        path.lineTo(5, 3)
        path.quadTo(3, 3, 3, 5)
        path.lineTo(3, 14)
        path.quadTo(3, 16, 5, 16)
        path.lineTo(8, 16)
        p.drawPath(path)
    elif name == "trash":
        p.drawLine(QPointF(3.5, 6.5), QPointF(20.5, 6.5))
        p.drawLine(QPointF(9.5, 6.5), QPointF(10, 3.5))
        p.drawLine(QPointF(10, 3.5), QPointF(14, 3.5))
        p.drawLine(QPointF(14, 3.5), QPointF(14.5, 6.5))
        path = QPainterPath(QPointF(5.5, 6.5))
        path.lineTo(6.5, 20.5)
        path.lineTo(17.5, 20.5)
        path.lineTo(18.5, 6.5)
        p.drawPath(path)
    elif name == "play":
        path = QPainterPath(QPointF(7, 4.5))
        path.lineTo(19, 12)
        path.lineTo(7, 19.5)
        path.closeSubpath()
        p.setBrush(fill)
        p.drawPath(path)
        p.setBrush(Qt.NoBrush)
    elif name == "refresh":
        p.drawArc(QRectF(4, 4, 16, 16), 30 * 16, 290 * 16)
        path = QPainterPath(QPointF(19.5, 3.5))
        path.lineTo(19.3, 8.3)
        path.lineTo(14.6, 8)
        p.drawPath(path)
    elif name == "check":
        path = QPainterPath(QPointF(4.5, 12.5))
        path.lineTo(9.5, 17.5)
        path.lineTo(19.5, 6.5)
        p.drawPath(path)
    elif name == "x":
        p.drawLine(QPointF(6, 6), QPointF(18, 18))
        p.drawLine(QPointF(18, 6), QPointF(6, 18))
    elif name == "text":
        p.drawLine(QPointF(5, 5), QPointF(19, 5))
        p.drawLine(QPointF(12, 5), QPointF(12, 19.5))
        p.drawLine(QPointF(9, 19.5), QPointF(15, 19.5))
    elif name == "clock":
        p.drawEllipse(QPointF(12, 12), 9, 9)
        p.drawLine(QPointF(12, 12), QPointF(12, 7))
        p.drawLine(QPointF(12, 12), QPointF(15.5, 14))
    elif name == "timer":
        p.drawEllipse(QPointF(12, 13.5), 7.5, 7.5)
        p.drawLine(QPointF(12, 13.5), QPointF(12, 9.5))
        p.drawLine(QPointF(10, 3), QPointF(14, 3))
        p.drawLine(QPointF(12, 3), QPointF(12, 6))
    elif name == "palette":
        p.drawEllipse(QPointF(12, 12), 9, 9)
        p.setBrush(fill)
        for x, y in ((8, 9.5), (12, 7), (16, 9.5)):
            p.drawEllipse(QPointF(x, y), 1.1, 1.1)
        p.setBrush(Qt.NoBrush)
    elif name == "video":
        p.drawRoundedRect(QRectF(3, 5, 18, 14), 2.5, 2.5)
        path = QPainterPath(QPointF(10, 9))
        path.lineTo(15, 12)
        path.lineTo(10, 15)
        path.closeSubpath()
        p.setBrush(fill)
        p.drawPath(path)
        p.setBrush(Qt.NoBrush)
    elif name == "slides":
        p.drawRoundedRect(QRectF(6, 6, 15, 12), 2, 2)
        p.drawLine(QPointF(3, 8.5), QPointF(3, 15.5))
        p.drawEllipse(QPointF(11, 10.5), 1.4, 1.4)
        path = QPainterPath(QPointF(21, 15))
        path.lineTo(17, 12)
        path.lineTo(9.5, 18)
        p.drawPath(path)
    elif name == "power":
        p.drawArc(QRectF(4, 5, 16, 16), 125 * 16, 290 * 16)
        p.drawLine(QPointF(12, 3), QPointF(12, 11))
    elif name == "sun":
        p.drawEllipse(QPointF(12, 12), 4, 4)
        for i in range(8):
            a = math.radians(i * 45)
            p.drawLine(QPointF(12 + 7 * math.cos(a), 12 + 7 * math.sin(a)),
                       QPointF(12 + 9.5 * math.cos(a), 12 + 9.5 * math.sin(a)))
    elif name == "moon":
        path = QPainterPath()
        path.addEllipse(QPointF(12, 12), 8.5, 8.5)
        cut = QPainterPath()
        cut.addEllipse(QPointF(16.5, 8.5), 7, 7)
        p.drawPath(path.subtracted(cut))
        p.setBrush(fill)
        p.drawEllipse(QPointF(19, 16), 0.9, 0.9)
        p.drawEllipse(QPointF(15.5, 19.5), 0.6, 0.6)
        p.setBrush(Qt.NoBrush)
    elif name == "star":
        path = QPainterPath()
        for i in range(10):
            r = 9.5 if i % 2 == 0 else 4
            a = math.radians(-90 + i * 36)
            pt = QPointF(12 + r * math.cos(a), 12.5 + r * math.sin(a))
            if i == 0:
                path.moveTo(pt)
            else:
                path.lineTo(pt)
        path.closeSubpath()
        p.drawPath(path)
    elif name == "keyboard":
        p.drawRoundedRect(QRectF(2, 6, 20, 12), 2.5, 2.5)
        p.setBrush(fill)
        for y in (9.5, 12.5):
            for x in (6, 10, 14, 18):
                p.drawEllipse(QPointF(x, y), 0.45, 0.45)
        p.setBrush(Qt.NoBrush)
        p.drawLine(QPointF(8, 15.3), QPointF(16, 15.3))
    elif name == "grid":
        for x, y in ((3, 3), (13, 3), (3, 13), (13, 13)):
            p.drawRoundedRect(QRectF(x, y, 8, 8), 1.8, 1.8)
    elif name == "up":
        p.drawLine(QPointF(12, 19), QPointF(12, 5))
        p.drawLine(QPointF(12, 5), QPointF(6.5, 10.5))
        p.drawLine(QPointF(12, 5), QPointF(17.5, 10.5))
    elif name == "down":
        p.drawLine(QPointF(12, 5), QPointF(12, 19))
        p.drawLine(QPointF(12, 19), QPointF(6.5, 13.5))
        p.drawLine(QPointF(12, 19), QPointF(17.5, 13.5))
    elif name == "sound":
        path = QPainterPath(QPointF(3.5, 9.5))
        path.lineTo(7.5, 9.5)
        path.lineTo(12, 5)
        path.lineTo(12, 19)
        path.lineTo(7.5, 14.5)
        path.lineTo(3.5, 14.5)
        path.closeSubpath()
        p.drawPath(path)
        p.drawArc(QRectF(10, 8, 7, 8), -60 * 16, 120 * 16)
        p.drawArc(QRectF(9, 4.5, 12, 15), -60 * 16, 120 * 16)
    elif name == "back":
        p.drawLine(QPointF(19, 12), QPointF(5, 12))
        p.drawLine(QPointF(5, 12), QPointF(10.5, 6.5))
        p.drawLine(QPointF(5, 12), QPointF(10.5, 17.5))
    elif name == "forward":
        p.drawLine(QPointF(5, 12), QPointF(19, 12))
        p.drawLine(QPointF(19, 12), QPointF(13.5, 6.5))
        p.drawLine(QPointF(19, 12), QPointF(13.5, 17.5))
    elif name == "zoom_in" or name == "zoom_out":
        p.drawEllipse(QPointF(10.5, 10.5), 6.5, 6.5)
        p.drawLine(QPointF(15.5, 15.5), QPointF(20.5, 20.5))
        p.drawLine(QPointF(7.5, 10.5), QPointF(13.5, 10.5))
        if name == "zoom_in":
            p.drawLine(QPointF(10.5, 7.5), QPointF(10.5, 13.5))
    elif name == "bookmark":
        path = QPainterPath(QPointF(6, 3.5))
        path.lineTo(18, 3.5)
        path.lineTo(18, 20.5)
        path.lineTo(12, 16)
        path.lineTo(6, 20.5)
        path.closeSubpath()
        p.drawPath(path)
    else:  # unbekannt → Kreis
        p.drawEllipse(QPointF(12, 12), 8, 8)


def pixmap(name: str, color: str | QColor, size: int = 24, stroke: float = 1.9, dpr: float = 2.0) -> QPixmap:
    px = QPixmap(int(size * dpr), int(size * dpr))
    px.setDevicePixelRatio(dpr)
    px.fill(Qt.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.Antialiasing)
    p.scale(size / 24, size / 24)
    col = QColor(color)
    p.setPen(QPen(col, stroke, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(Qt.NoBrush)
    _draw(name, p, col)
    p.end()
    return px


@lru_cache(maxsize=256)
def _icon_cached(name: str, color: str, size: int) -> QIcon:
    return QIcon(pixmap(name, color, size))


def icon(name: str, color: str | QColor, size: int = 24) -> QIcon:
    return _icon_cached(name, QColor(color).name(QColor.HexArgb), size)


def paint(p: QPainter, name: str, rect: QRectF, color: str | QColor, stroke: float = 1.9) -> None:
    """Symbol direkt in einen vorhandenen Painter zeichnen (skaliert auf `rect`)."""
    p.save()
    p.setRenderHint(QPainter.Antialiasing)
    side = min(rect.width(), rect.height())
    p.translate(rect.center().x() - side / 2, rect.center().y() - side / 2)
    p.scale(side / 24, side / 24)
    col = QColor(color)
    p.setPen(QPen(col, stroke, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(Qt.NoBrush)
    _draw(name, p, col)
    p.restore()


SOURCE_ICONS = {
    "camera": "camera", "window": "window", "screen": "monitor", "website": "globe", "image": "image",
    "video": "video", "slideshow": "slides", "text": "text", "clock": "clock", "countdown": "timer",
    "color": "palette", "scene": "scenes",
}


def app_icon() -> QIcon:
    """Programmsymbol: zwei Monitore auf blauem Verlauf."""
    from PySide6.QtGui import QLinearGradient

    ic = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        px = QPixmap(size, size)
        px.fill(Qt.transparent)
        p = QPainter(px)
        p.setRenderHint(QPainter.Antialiasing)
        s = size / 64
        grad = QLinearGradient(0, 0, size, size)
        grad.setColorAt(0, QColor("#4f8df9"))
        grad.setColorAt(1, QColor("#6d4ce8"))
        p.setPen(Qt.NoPen)
        p.setBrush(grad)
        p.drawRoundedRect(QRectF(2 * s, 2 * s, 60 * s, 60 * s), 15 * s, 15 * s)
        # hinterer Monitor (Monitor 2) halbtransparent, vorderer weiß
        p.setBrush(QColor(255, 255, 255, 110))
        p.drawRoundedRect(QRectF(24 * s, 13 * s, 28 * s, 20 * s), 3.5 * s, 3.5 * s)
        p.setBrush(QColor("#ffffff"))
        p.drawRoundedRect(QRectF(12 * s, 22 * s, 30 * s, 21 * s), 3.5 * s, 3.5 * s)
        p.drawRoundedRect(QRectF(22 * s, 43 * s, 10 * s, 6 * s), 1 * s, 1 * s)
        p.drawRoundedRect(QRectF(17 * s, 48 * s, 20 * s, 3.5 * s), 1.7 * s, 1.7 * s)
        p.setBrush(QColor("#5b76f2"))
        p.drawRoundedRect(QRectF(15 * s, 25 * s, 24 * s, 15 * s), 2 * s, 2 * s)
        p.end()
        ic.addPixmap(px)
    return ic
