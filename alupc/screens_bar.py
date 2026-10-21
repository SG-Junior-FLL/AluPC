"""Info-Leiste unter einer Vorlage: Uhr, Countdown und Laufschrift – ohne etwas zu verdecken.

Früher lagen Uhr und Countdown als kleine Kästen über der Vorlage und deckten Titel oder Antworten zu. Jetzt rückt
die Vorlage nach oben, und unten steht eine eigene Leiste (wie bei Nachrichtensendern):

    links  Uhrzeit         Mitte  Laufschrift (oder fester Text)         rechts  Countdown mit Restzeit-Balken

Einstellungen an der Vorlage (alle freiwillig): "uhr": True, "countdown": Minuten, "laufschrift": "Text".
"""

from __future__ import annotations

import time

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFontMetricsF, QLinearGradient, QPainter

from . import stage

BAR = 0.11  # Höhe der Leiste (Anteil am Bild)
TICKER_SPEED = 9.0  # Laufschrift: Einheiten (1 % der Breite) pro Sekunde


def extras(cfg: dict) -> dict:
    """Welche Teile die Leiste zeigt – leer: keine Leiste."""
    out = {}
    if cfg.get("uhr"):
        out["uhr"] = True
    try:
        minutes = float(cfg.get("countdown") or 0)
    except (TypeError, ValueError):
        minutes = 0
    if minutes > 0:
        out["countdown"] = minutes
    text = str(cfg.get("laufschrift") or "").strip()
    if text:
        out["laufschrift"] = " ".join(text.split())
    return out


def needs_ticks(cfg: dict) -> int | None:
    """Neu zeichnen alle … ms (Laufschrift flüssig, Uhr/Countdown jede Sekunde) – None: nicht nötig."""
    e = extras(cfg)
    if "laufschrift" in e:
        return 33
    return 500 if e else None


def remaining(cfg: dict, now: float, started: float) -> float:
    return max(0.0, float(cfg.get("countdown") or 0) * 60 - max(0.0, now - (started or now)))


def paint_bar(p: QPainter, w: float, h: float, cfg: dict, now: float, started: float, color: QColor) -> None:
    e = extras(cfg)
    bh = h * BAR
    top = h - bh
    unit = min(w, h / 0.5625) / 100
    r = QRectF(0, top, w, bh)
    p.save()
    p.setRenderHint(QPainter.Antialiasing)
    # dunkle Leiste mit Farbverlauf der Vorlage und Akzentlinie oben
    tint = QColor(color)
    tint.setAlpha(70)
    p.fillRect(r, QColor("#07080d"))
    glow = QLinearGradient(0, top, w, top)
    glow.setColorAt(0, tint)
    glow.setColorAt(0.6, QColor(0, 0, 0, 0))
    p.fillRect(r, glow)
    p.fillRect(QRectF(0, top, w, max(2.0, unit * 0.35)), color)

    pad = unit * 3
    left, right = pad, w - pad
    # links: Uhrzeit
    if "uhr" in e:
        p.setPen(QColor("#ffffff"))
        p.setFont(stage.font(bh * 0.46, 700))
        text = time.strftime("%H:%M", time.localtime(now))
        tw = QFontMetricsF(p.font()).horizontalAdvance(text)
        p.drawText(QRectF(left, top, tw + unit, bh), Qt.AlignLeft | Qt.AlignVCenter, text)
        left += tw + unit * 3
        p.setPen(QColor(255, 255, 255, 40))
        p.drawLine(int(left - unit * 1.5), int(top + bh * 0.25), int(left - unit * 1.5), int(top + bh * 0.75))
    # rechts: Countdown mit Balken
    if "countdown" in e:
        rest = remaining(cfg, now, started)
        total = e["countdown"] * 60
        done = rest <= 0
        label = "Zeit ist um" if done else f"{int(rest // 60)}:{int(rest % 60):02d}"
        p.setFont(stage.font(bh * (0.34 if done else 0.46), 700))
        tw = QFontMetricsF(p.font()).horizontalAdvance(label)
        box = QRectF(right - tw - unit * 4, top + bh * 0.16, tw + unit * 4, bh * 0.68)
        warn = rest <= 60
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#ef4444") if done else QColor(255, 255, 255, 26))
        p.drawRoundedRect(box, box.height() / 2, box.height() / 2)
        if not done:  # Restzeit als Füllung im Kasten
            fill = QColor("#f59e0b" if warn else color)
            fill.setAlpha(150)
            p.setBrush(fill)
            p.setClipRect(QRectF(box.left(), box.top(), box.width() * rest / max(1.0, total), box.height()))
            p.drawRoundedRect(box, box.height() / 2, box.height() / 2)
            p.setClipping(False)
        p.setPen(QColor("#ffffff"))
        p.drawText(box, Qt.AlignCenter, label)
        right = box.left() - unit * 3
        p.setPen(QColor(255, 255, 255, 170))
        p.setFont(stage.font(bh * 0.24, 600))
        word = "" if done else "noch"
        ww = QFontMetricsF(p.font()).horizontalAdvance(word)
        p.drawText(QRectF(right - ww, top, ww, bh), Qt.AlignRight | Qt.AlignVCenter, word)
        right -= ww + unit * 2
    # Mitte: Laufschrift (läuft nur, wenn sie nicht hineinpasst)
    if "laufschrift" in e and right > left:
        area = QRectF(left, top, right - left, bh)
        text = e["laufschrift"]
        p.setFont(stage.font(bh * 0.36, 600))
        p.setPen(QColor(255, 255, 255, 235))
        tw = QFontMetricsF(p.font()).horizontalAdvance(text)
        p.setClipRect(area)
        if tw <= area.width():
            p.drawText(area, Qt.AlignLeft | Qt.AlignVCenter, text)
        else:
            gap = unit * 12
            off = ((now - (started or now)) * TICKER_SPEED * unit) % (tw + gap)
            x = area.left() - off
            while x < area.right():
                p.drawText(QRectF(x, top, tw, bh), Qt.AlignLeft | Qt.AlignVCenter, text)
                x += tw + gap
        p.setClipping(False)
    p.restore()
