"""Publikumsansicht (Monitor 2): EIN Aussehen für alle Info-Anzeigen – Abstimmung, Glücksrad, WLAN/QR, System,
Musik, Spiele, AirPlay-Warten, Text/Uhr/Timer (mit Standard-Hintergrund). Unabhängig vom Design der PC-App
(Normal/Technisch/Holz), damit das Publikum immer dasselbe sieht.

„Bühne“ (Standard): dunkler, leicht blauer Verlauf mit sanftem Leuchten oben. „Schwarz“: reines Schwarz
(z. B. für Beamer mit wenig Kontrast). Einstellung: Setup → Bildschirm → Publikum.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QRadialGradient

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
    """Hintergrund der Publikumsansicht."""
    rect = QRectF(rect)
    if settings["look"] == "schwarz":
        p.fillRect(rect, QColor("#000000"))
        return
    grad = QLinearGradient(rect.topLeft(), rect.bottomLeft())
    grad.setColorAt(0, QColor(BG_TOP))
    grad.setColorAt(1, QColor(BG_BOTTOM))
    p.fillRect(rect, grad)
    glow = QRadialGradient(QPointF(rect.center().x(), rect.top()), max(rect.width(), rect.height()) * 0.7)
    c0, c1 = QColor(ACCENT), QColor(ACCENT)
    c0.setAlphaF(0.10)
    c1.setAlphaF(0.0)
    glow.setColorAt(0, c0)
    glow.setColorAt(1, c1)
    p.fillRect(rect, glow)


def margin(w: float, h: float) -> float:
    """Gleicher Rand für alle Anzeigen (6 % der kürzeren Seite)."""
    return min(w, h) * 0.06


def is_default_black(color: QColor) -> bool:
    """Standard-Hintergrund von Text/Uhr/Timer (Schwarz) → stattdessen die Bühne zeigen."""
    return QColor(color).rgb() == QColor("#000000").rgb()
