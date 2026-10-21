"""Publikumsansicht (Monitor 2): EIN Aussehen für alle Info-Anzeigen – Abstimmung, Glücksrad, WLAN/QR, System,
Musik, Spiele, AirPlay-Warten, Text/Uhr/Timer (mit Standard-Hintergrund). Unabhängig vom Design der PC-App
(Normal/Technisch/Holz), damit das Publikum immer dasselbe sieht.

„Bühne“ (Standard): dunkler, leicht blauer Verlauf mit sanftem Leuchten oben. „Schwarz“: reines Schwarz
(z. B. für Beamer mit wenig Kontrast). Einstellung: Setup → Bildschirm → Publikum.
"""

from __future__ import annotations

import time

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QLinearGradient, QPainter, QRadialGradient

LOOKS = {"buehne": "Bühne (dunkler Verlauf)", "schwarz": "Reines Schwarz"}
BG_TOP = "#16181e"
BG_BOTTOM = "#0b0c0f"
PANEL = "#1d2027"      # Flächen (Balken, Karten) auf der Bühne
LINE = "#2b2f38"
TEXT = "#f3f4f6"
MUTED = "#9ca3af"
ACCENT = "#5b8cff"     # AluPC-Blau – immer gleich, egal welches PC-Design
LIVE = "#ff4f45"

settings = {"look": "buehne"}  # setzt der Controller aus config["output"]["stage"]


def configure(look: str | None) -> None:
    settings["look"] = look if look in LOOKS else "buehne"


def base_color() -> QColor:
    """Eine Farbe für Stellen, die keinen Verlauf malen können."""
    return QColor("#000000" if settings["look"] == "schwarz" else BG_BOTTOM)


def paint_background(p: QPainter, rect: QRectF) -> None:
    """Hintergrund der Publikumsansicht: dunkle „Aurora“ in AluPC-Blau und Violett (oder reines Schwarz)."""
    rect = QRectF(rect)
    if settings["look"] == "schwarz":
        p.fillRect(rect, QColor("#000000"))
        return
    paint_aurora(p, rect, QColor(ACCENT), strength=0.4)  # ruhiger als die Vorlagen: Publikum sieht vor allem Inhalt


def _blob(p: QPainter, rect: QRectF, center: QPointF, radius: float, color: QColor, alpha: float) -> None:
    g = QRadialGradient(center, radius)
    c0, c1, c2 = QColor(color), QColor(color), QColor(color)
    c0.setAlphaF(alpha)
    c1.setAlphaF(alpha * 0.35)
    c2.setAlphaF(0.0)
    g.setColorAt(0, c0)
    g.setColorAt(0.45, c1)
    g.setColorAt(1, c2)
    p.fillRect(rect, g)


_AURORA_CACHE: dict = {}


def paint_aurora(p: QPainter, rect: QRectF, color: QColor, now: float = 0.0, strength: float = 1.0) -> None:
    """Wie `_paint_aurora`, aber einmal je Größe/Farbe gerechnet und danach nur kopiert (Animationen: 30 Bilder/s)."""
    from PySide6.QtGui import QImage

    rect = QRectF(rect)
    dpr = p.device().devicePixelRatioF() if p.device() else 1.0
    key = (QColor(color).rgb(), round(rect.width()), round(rect.height()), round(strength, 2), dpr)
    img = _AURORA_CACHE.get(key)
    if img is None:
        img = QImage(max(1, int(rect.width() * dpr)), max(1, int(rect.height() * dpr)), QImage.Format_RGB32)
        img.setDevicePixelRatio(dpr)
        q = QPainter(img)
        _paint_aurora(q, QRectF(0, 0, rect.width(), rect.height()), QColor(color), strength)
        q.end()
        if len(_AURORA_CACHE) > 16:
            _AURORA_CACHE.clear()
        _AURORA_CACHE[key] = img
    p.drawImage(rect.topLeft(), img)


def _paint_aurora(p: QPainter, rect: QRectF, color: QColor, strength: float = 1.0) -> None:
    """Gemeinsamer Hintergrund aller Vorlagen auf Monitor 2: sehr dunkler Grund in der Farbe der Vorlage, zwei
    weiche Lichtflecken (Farbe + Nachbarfarbe), die langsam wandern, dunkler Rand. Passt zu jeder Größe."""
    rect = QRectF(rect)
    w, h = rect.width(), rect.height()
    hue = color.hsvHueF() if color.hsvHueF() >= 0 else 0.62
    base = QLinearGradient(rect.topLeft(), rect.bottomRight())
    base.setColorAt(0, QColor.fromHsvF(hue, 0.55, 0.13))
    base.setColorAt(1, QColor.fromHsvF((hue + 0.04) % 1.0, 0.6, 0.045))
    p.fillRect(rect, base)
    drift = 0.0
    big = max(w, h)
    _blob(p, rect, QPointF(rect.left() + w * (0.18 + drift), rect.top() + h * 0.05), big * 0.75, color, 0.42 * strength)
    other = QColor.fromHsvF((hue + 0.09) % 1.0, min(1.0, max(0.5, color.hsvSaturationF())), 0.95)
    _blob(p, rect, QPointF(rect.left() + w * (0.92 - drift), rect.top() + h * 1.02), big * 0.65, other,
          0.30 * strength)
    vignette = QRadialGradient(rect.center(), big * 0.72)
    vignette.setColorAt(0.55, QColor(0, 0, 0, 0))
    vignette.setColorAt(1, QColor(0, 0, 0, 150))
    p.fillRect(rect, vignette)


def font(px: float, weight: int = 700) -> QFont:
    """Schrift für Monitor 2: Inter, große Titel etwas enger gesetzt."""
    f = QFont("Inter")
    f.setPixelSize(max(6, int(px)))
    f.setWeight(QFont.Weight(weight))
    if px >= 40:
        f.setLetterSpacing(QFont.PercentageSpacing, 98)
    return f


def eyebrow(p: QPainter, x: float, y: float, text: str, color: QColor, unit: float) -> QRectF:
    """Kleines Etikett oben links (Punkt in der Farbe + Wort), wie bei Sendungen. Gibt sein Rechteck zurück."""
    f = font(unit * 1.9, 700)
    f.setLetterSpacing(QFont.PercentageSpacing, 104)
    tw = QFontMetricsF(f).horizontalAdvance(text)
    r = QRectF(x, y, tw + unit * 5.2, unit * 4)
    p.save()
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(255, 255, 255, 22))
    p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
    p.setBrush(color)
    p.drawEllipse(QPointF(r.left() + unit * 2, r.center().y()), unit * 0.75, unit * 0.75)
    p.setPen(QColor(255, 255, 255, 225))
    p.setFont(f)
    p.drawText(r.adjusted(unit * 3.4, 0, 0, 0), Qt.AlignLeft | Qt.AlignVCenter, text)
    p.restore()
    return r


HIDE_CLOCK = False  # Info-Leiste zeigt schon die Uhr (screens_bar) → oben rechts keine zweite


def clock_corner(p: QPainter, w: float, unit: float, now: float, y: float | None = None) -> None:
    """Uhrzeit oben rechts (gleiche Stelle auf allen Vorlagen)."""
    if HIDE_CLOCK:
        return
    p.save()
    p.setPen(QColor(255, 255, 255, 190))
    p.setFont(font(unit * 2.4, 600))
    top = unit * 3.5 if y is None else y
    p.drawText(QRectF(w * 0.5, top, w * 0.5 - unit * 4.5, unit * 4), Qt.AlignRight | Qt.AlignVCenter,
               time.strftime("%H:%M", time.localtime(now)))
    p.restore()


def margin(w: float, h: float) -> float:
    """Gleicher Rand für alle Anzeigen (6 % der kürzeren Seite)."""
    return min(w, h) * 0.06


def is_default_black(color: QColor) -> bool:
    """Standard-Hintergrund von Text/Uhr/Timer (Schwarz) → stattdessen die Bühne zeigen."""
    return QColor(color).rgb() == QColor("#000000").rgb()
