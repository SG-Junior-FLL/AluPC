"""Gestaltete Seiten für Monitor 2 („Screens“) und fertige Szenen-Vorlagen – jeweils mit eigenem Text.

Eine gestaltete Seite ist die Quelle `{"type": "design", "design": "<name>", "title": …, "text": …}`:
Willkommen, Ablauf, Pause (mit Countdown), Laufschrift, Zitat, Ankündigung, Fragen, WLAN-Zugang (mit QR-Code).
Alles wird gezeichnet (keine Bilddateien) und passt sich jeder Monitorgröße an.
"""

from __future__ import annotations

import math
import time

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QImage, QLinearGradient, QPainter, QPen, QRadialGradient
from PySide6.QtWidgets import QWidget

# name → (Anzeige-Name, Beschreibung, Standard-Titel, Standard-Text, Standardfarbe)
DESIGNS: dict[str, tuple[str, str, str, str, str]] = {
    "willkommen": ("Willkommen", "Großer Titel, Untertitel, Uhrzeit", "Herzlich willkommen!",
                   "Schön, dass ihr da seid.", "#6366f1"),
    "ablauf": ("Ablauf / Agenda", "Punkte untereinander, der aktuelle ist markiert", "Heute",
               "Intro\nDas Wichtigste\nLive-Demo\nFragen\nAusklang", "#0ea5e9"),
    "pause": ("Pause", "Pause mit Restzeit und „weiter um …“", "Pause", "Gleich geht's weiter.", "#22c55e"),
    "laufschrift": ("Laufschrift", "Titel und laufende Textzeile unten", "Aktuelles",
                    "Hier kann eine Nachricht durchlaufen – einfach eigenen Text eingeben.", "#f97316"),
    "zitat": ("Zitat", "Zitat mit Autor", "Nicht, weil es schwer ist, wagen wir es nicht, sondern weil wir es "
              "nicht wagen, ist es schwer.", "Seneca", "#a855f7"),
    "ankuendigung": ("Ankündigung", "Wichtiger Hinweis, gut sichtbar", "Hinweis",
                     "Bitte Handys auf lautlos stellen.", "#ef4444"),
    "frage": ("Fragen?", "Fragerunde / Diskussion", "Fragen?", "Jetzt ist Zeit für eure Fragen.", "#eab308"),
    "wlan": ("WLAN-Zugang", "WLAN-Name und Passwort mit QR-Code zum Scannen", "Gäste-WLAN", "Passwort", "#14b8a6"),
}
TIMED = {"willkommen": 1000, "pause": 500, "laufschrift": 33, "frage": 50}

# Weitere Seiten (screens_more.py) dazunehmen
from .screens_more import (MORE_CATEGORIES, MORE_DESIGNS, MORE_LABELS, MORE_TIMED, PAINTERS, Ctx,  # noqa: E402
                           changed, intro)

from .screens_cards import CARD_DESIGNS, CARD_LABELS, CARD_PAINTERS, CARD_TIMED, paint_card  # noqa: E402

DESIGNS.update(MORE_DESIGNS)
DESIGNS.update(CARD_DESIGNS)
TIMED.update(MORE_TIMED)
TIMED.update(CARD_TIMED)
CATEGORY_NAMES = ["Style", "Party & Event", "Präsentation", "Info", "Zeit"]
ANIMATED_NAME = "Animiert"  # Extra-Filter: alles, was sich dauerhaft bewegt (zusätzlich zur Kategorie)
CATEGORIES = {"willkommen": "Party & Event", "ablauf": "Präsentation", "pause": "Zeit", "laufschrift": "Info",
              "zitat": "Style", "ankuendigung": "Info", "frage": "Präsentation", "wlan": "Info",
              **MORE_CATEGORIES, **{k: "Style" for k in CARD_DESIGNS},
              "nowplaying": "Party & Event", "live": "Party & Event", "versus": "Party & Event",
              "linkkarte": "Info", "comingsoon": "Info"}
# Beschriftung der Eingabefelder je Seite (Titel, Text)
FIELD_LABELS = {"wlan": ("WLAN-Name:", "Passwort:"), "zitat": ("Zitat:", "Autor:"),
                "ablauf": ("Überschrift:", "Punkte (je Zeile einer):"), "laufschrift": ("Titel:", "Laufschrift:"),
                **MORE_LABELS, **CARD_LABELS}


def animated_designs() -> set[str]:
    """Seiten mit dauerhafter Bewegung (Laufschrift, Konfetti, Neon-Flackern, Equalizer …) –
    nicht die, die nur die Uhrzeit weiterzählen."""
    return {k for k, interval in TIMED.items() if interval <= 100}


def is_animated_template(kind: str, key: str) -> bool:
    if kind == "design":
        return key in animated_designs()
    if kind == "scene":
        return any((slot or {}).get("design") in animated_designs() for slot in build_template(key, {})["slots"])
    return False


def design_defaults(design: str) -> dict:
    _label, _desc, title, text, color = DESIGNS.get(design, DESIGNS["willkommen"])
    cfg = {"type": "design", "design": design, "title": title, "text": text, "color": color}
    if design == "pause":
        cfg["minutes"] = 10
    if design == "ablauf":
        cfg["current"] = 1
    if design == "abstimmung":
        cfg["current"] = 0  # 0 = noch nicht aufgelöst, sonst Nummer der richtigen Antwort
    return cfg


def describe_design(cfg: dict) -> str:
    label = DESIGNS.get(cfg.get("design", ""), ("Seite",))[0]
    title = (cfg.get("title") or "").replace("\n", " ")
    return f"{label}: {title[:36]}" if title else label


def wifi_payload(ssid: str, password: str, hidden: bool = False) -> str:
    """Inhalt für den WLAN-QR-Code (Handys verbinden sich damit direkt). hidden: unsichtbares WLAN (H:true) –
    das Handy sucht dann gezielt nach dem Namen."""
    def esc(s: str) -> str:
        return "".join("\\" + ch if ch in "\\;,:\"" else ch for ch in s)
    kind = "WPA" if password else "nopass"
    return f"WIFI:T:{kind};S:{esc(ssid)};P:{esc(password)};{'H:true;' if hidden else ''};"


def _font(px: float, bold: bool = False, weight: QFont.Weight | None = None) -> QFont:
    from . import stage

    return stage.font(px, int(weight) if weight is not None else (700 if bold else 400))


def _fit(text: str, rect: QRectF, start_px: float, bold: bool = True, flags=Qt.AlignCenter | Qt.TextWordWrap) -> QFont:
    """Größte Schrift, bei der der Text ins Rechteck passt."""
    px = start_px
    while px > 8:
        f = _font(px, bold)
        r = QFontMetricsF(f).boundingRect(rect, int(flags), text)
        if r.height() <= rect.height() and r.width() <= rect.width() + 1:
            return f
        px *= 0.92
    return _font(8, bold)


def _background(p: QPainter, w: int, h: int, color: QColor) -> None:
    """Gemeinsamer Hintergrund aller Vorlagen (stage.paint_aurora): dunkler Grund in der Farbe, zwei Lichtflecken."""
    from . import stage

    stage.paint_aurora(p, QRectF(0, 0, w, h), color)


def paint_design(p: QPainter, w: int, h: int, cfg: dict, now: float | None = None, started: float = 0.0) -> None:
    now = time.time() if now is None else now
    design = cfg.get("design", "willkommen")
    color = QColor(cfg.get("color") or DESIGNS.get(design, DESIGNS["willkommen"])[4])
    title = cfg.get("title", "")
    text = cfg.get("text", "")
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.TextAntialiasing)
    _background(p, w, h, color)
    white = QColor("#f8fafc")
    muted = QColor(255, 255, 255, 170)
    unit = min(w, h / 0.5625) / 100  # 1 % der Breite eines 16:9-Bilds

    if design in CARD_PAINTERS:  # Design-Karten zeichnen ihren eigenen Hintergrund
        paint_card(p, w, h, cfg, now, started, color, unit)
        return
    if design in PAINTERS:
        PAINTERS[design](Ctx(p, w, h, cfg, now, started, color, unit))
        return
    if design not in DESIGNS:  # z. B. entfernte Vorlage in einer alten Szene: Titel und Text schlicht zeigen
        design = "willkommen"

    from . import stage

    m = unit * 6  # Rand links/rechts – gleich auf allen Vorlagen

    def label(text):
        stage.eyebrow(p, m, unit * 4, text, color, unit)

    if design == "willkommen":
        label("Willkommen")
        stage.clock_corner(p, w, unit, now)
        area = QRectF(m, h * 0.2, w - 2 * m, h * 0.4)
        a = intro(cfg, now, dur=0.8)
        p.save()
        p.setOpacity(a)
        p.translate(0, (1 - a) * unit * 5)
        p.setPen(white)
        p.setFont(_fit(title, area, unit * 12))
        p.drawText(area, Qt.AlignCenter | Qt.TextWordWrap, title)
        p.restore()
        bar = unit * 16 * intro(cfg, now, 3)
        g = QLinearGradient(w / 2 - bar / 2, 0, w / 2 + bar / 2, 0)
        g.setColorAt(0, QColor(color.red(), color.green(), color.blue(), 0))
        g.setColorAt(0.5, color.lighter(130))
        g.setColorAt(1, QColor(color.red(), color.green(), color.blue(), 0))
        p.setPen(Qt.NoPen)
        p.setBrush(g)
        p.drawRoundedRect(QRectF(w / 2 - bar / 2, h * 0.64, bar, unit * 0.5), unit * 0.25, unit * 0.25)
        sub = QRectF(m * 1.5, h * 0.68, w - 3 * m, h * 0.16)
        p.save()
        p.setOpacity(intro(cfg, now, 5))
        p.setPen(muted)
        p.setFont(_fit(text, sub, unit * 4, bold=False))
        p.drawText(sub, Qt.AlignCenter | Qt.TextWordWrap, text)
        p.restore()
    elif design == "ablauf":
        label("Ablauf")
        stage.clock_corner(p, w, unit, now)
        items = [line.strip() for line in text.splitlines() if line.strip()]
        current = int(cfg.get("current", 1))
        a = intro(cfg, now)
        p.save()
        p.setOpacity(a)
        p.translate(-(1 - a) * w * 0.03, 0)
        p.setPen(white)
        head = QRectF(m, unit * 10, w - 2 * m, h * 0.14)
        p.setFont(_fit(title, head, unit * 7.5, flags=Qt.AlignLeft | Qt.AlignVCenter))
        p.drawText(head, Qt.AlignLeft | Qt.AlignVCenter, title)
        p.restore()
        if items:
            top = unit * 10 + h * 0.17
            row_h = min(h * 0.15, (h - top - unit * 4) / len(items))
            badge_d = row_h * 0.6
            line_x = m + badge_d / 2

            def row_box(i):
                return QRectF(m - unit * 1.2, top + (i - 1) * row_h + row_h * 0.08, w - 2 * m + unit * 2.4,
                              row_h * 0.84)

            # Zeitleiste: senkrechte Linie durch alle Punkte, bis zum aktuellen in der Farbe
            p.setPen(QPen(QColor(255, 255, 255, 40), unit * 0.35))
            p.drawLine(QPointF(line_x, top + row_h / 2), QPointF(line_x, top + (len(items) - 0.5) * row_h))
            if current > 1:
                done_to = top + (min(current, len(items)) - 0.5) * row_h
                p.setPen(QPen(color, unit * 0.35))
                p.drawLine(QPointF(line_x, top + row_h / 2), QPointF(line_x, done_to))
            if 1 <= current <= len(items):  # Markierung gleitet vom alten zum neuen Punkt
                box = row_box(current)
                prev = int(cfg.get("_prev") or 0)
                t = changed(cfg, now)
                if 1 <= prev <= len(items):
                    box.moveTop(row_box(prev).top() + (box.top() - row_box(prev).top()) * t)
                bg = QColor(color)
                bg.setAlpha(55)
                p.save()
                p.setOpacity(intro(cfg, now, current))
                p.setPen(Qt.NoPen)
                p.setBrush(bg)
                p.drawRoundedRect(box, row_h * 0.22, row_h * 0.22)
                p.setBrush(color)
                p.drawRoundedRect(QRectF(box.right() - unit * 0.8, box.top() + row_h * 0.2, unit * 0.5,
                                         box.height() - row_h * 0.4), unit * 0.25, unit * 0.25)
                p.restore()
            for i, item in enumerate(items, start=1):
                active, done = i == current, i < current
                box = row_box(i)
                a = intro(cfg, now, i)
                p.save()
                p.setOpacity(a)
                p.translate(-(1 - a) * w * 0.05, 0)
                badge = QRectF(m, box.center().y() - badge_d / 2, badge_d, badge_d)
                p.setPen(QPen(color, unit * 0.3) if not (active or done) else Qt.NoPen)
                p.setBrush(color if (active or done) else QColor(10, 12, 20, 230))
                p.drawEllipse(badge)
                p.setPen(white)
                p.setFont(_font(badge_d * 0.45, True))
                p.drawText(badge, Qt.AlignCenter, "✓" if done else str(i))
                p.setPen(white if not done else QColor(255, 255, 255, 120))
                f = _font(row_h * (0.5 if active else 0.44), active)
                p.setFont(f)
                tx = QRectF(badge.right() + unit * 3, box.top(), box.right() - badge.right() - unit * 5, box.height())
                p.drawText(tx, Qt.AlignLeft | Qt.AlignVCenter,
                           QFontMetricsF(f).elidedText(item, Qt.ElideRight, tx.width()))
                p.restore()
    elif design == "pause":
        label("Pause")
        stage.clock_corner(p, w, unit, now)
        total = max(1.0, float(cfg.get("minutes", 10)) * 60)
        left = max(0.0, total - (now - (started or now)))
        c = QPointF(w / 2, h * 0.45)
        r = min(w, h) * 0.27
        glow = QRadialGradient(c, r * 1.5)
        glow.setColorAt(0, QColor(color.red(), color.green(), color.blue(), 60))
        glow.setColorAt(1, QColor(0, 0, 0, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(glow)
        p.drawEllipse(c, r * 1.5, r * 1.5)
        ring = QRectF(c.x() - r, c.y() - r, 2 * r, 2 * r)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(255, 255, 255, 26), r * 0.07))
        p.drawEllipse(c, r, r)
        # Restzeit als Ring aus Strichen (wie eine Uhr), dazu der durchgehende Bogen
        ticks = 60
        lit = int(ticks * left / total + 0.999)
        for i in range(ticks):
            ang = math.radians(90 - i * 6)
            r0, r1 = r * 1.12, r * (1.18 if i % 5 == 0 else 1.15)
            p.setPen(QPen(color if i < lit else QColor(255, 255, 255, 30), r * 0.012 * (1.6 if i % 5 == 0 else 1)))
            p.drawLine(QPointF(c.x() + r0 * math.cos(ang), c.y() - r0 * math.sin(ang)),
                       QPointF(c.x() + r1 * math.cos(ang), c.y() - r1 * math.sin(ang)))
        p.setPen(QPen(color, r * 0.07, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(ring, 90 * 16, int(360 * 16 * left / total))
        p.setPen(white)
        mm, ss = divmod(int(math.ceil(left)), 60)
        p.setFont(_font(r * 0.5, True))
        p.drawText(QRectF(c.x() - r, c.y() - r * 0.42, 2 * r, r * 0.62), Qt.AlignCenter, f"{mm}:{ss:02d}")
        p.setFont(_font(r * 0.13, True))
        p.setPen(muted)
        p.drawText(QRectF(c.x() - r, c.y() + r * 0.22, 2 * r, r * 0.25), Qt.AlignCenter, title)
        until = time.strftime("%H:%M", time.localtime((started or now) + total))
        line = QRectF(m, h * 0.84, w - 2 * m, h * 0.08)
        msg = f"{text}  ·  weiter um {until}" if text else f"Weiter um {until}"
        p.setPen(white)
        p.setFont(_fit(msg, line, unit * 3.4, False))
        p.drawText(line, Qt.AlignCenter, msg)
    elif design == "laufschrift":
        label("Aktuell")
        stage.clock_corner(p, w, unit, now)
        area = QRectF(m, h * 0.18, w - 2 * m, h * 0.46)
        p.setPen(white)
        p.setFont(_fit(title, area, unit * 12))
        p.drawText(area, Qt.AlignCenter | Qt.TextWordWrap, title)
        band = QRectF(0, h * 0.8, w, h * 0.12)
        p.setPen(Qt.NoPen)
        g = QLinearGradient(band.topLeft(), band.bottomLeft())
        g.setColorAt(0, color.lighter(115))
        g.setColorAt(1, color.darker(125))
        p.setBrush(g)
        p.drawRect(band)
        tag = QRectF(0, band.top(), unit * 16, band.height())
        p.setBrush(QColor(10, 12, 20))
        p.drawRect(tag)
        f = _font(band.height() * 0.46, True)
        p.save()
        p.setClipRect(QRectF(tag.right(), band.top(), w - tag.right(), band.height()))
        p.setFont(f)
        msg = (text or " ").replace("\n", "   ·   ") + "      •      "
        width = QFontMetricsF(f).horizontalAdvance(msg)
        speed = unit * 12  # Pixel pro Sekunde
        offset = ((now - (started or now)) * speed) % max(1.0, width)
        p.setPen(QColor("#ffffff"))
        x = tag.right() - offset
        while x < w:
            p.drawText(QRectF(x, band.top(), width, band.height()), Qt.AlignVCenter | Qt.AlignLeft, msg)
            x += width
        p.restore()
        p.setPen(QColor("#ffffff"))
        p.setFont(_font(band.height() * 0.4, True))
        p.drawText(tag, Qt.AlignCenter, time.strftime("%H:%M", time.localtime(now)))
    elif design == "zitat":
        p.setPen(QColor(color.red(), color.green(), color.blue(), 110))
        p.setFont(_font(unit * 30, True))
        p.drawText(QRectF(m - unit * 2, -unit * 4, w * 0.3, h * 0.5), Qt.AlignLeft | Qt.AlignTop, "“")
        area = QRectF(m * 1.6, h * 0.18, w - 3.2 * m, h * 0.5)
        p.save()
        a = intro(cfg, now, dur=1.2)
        p.setOpacity(a)
        p.translate(0, (1 - a) * unit * 3)
        p.setPen(white)
        f = _fit(title, area, unit * 7)
        f.setItalic(True)
        p.setFont(f)
        p.drawText(area, Qt.AlignCenter | Qt.TextWordWrap, title)
        p.restore()
        p.setOpacity(intro(cfg, now, 10))
        if text:
            p.setPen(Qt.NoPen)
            p.setBrush(color)
            p.drawRoundedRect(QRectF(w / 2 - unit * 5, h * 0.74, unit * 10, unit * 0.5), unit * 0.25, unit * 0.25)
            p.setPen(white)
            p.setFont(_font(unit * 3.4, True))
            p.drawText(QRectF(0, h * 0.77, w, h * 0.1), Qt.AlignCenter, text)
    elif design == "ankuendigung":
        a = intro(cfg, now, dur=0.5)
        p.setOpacity(a)
        p.translate(w / 2, h / 2)
        p.scale(0.94 + 0.06 * a, 0.94 + 0.06 * a)
        p.translate(-w / 2, -h / 2)
        stage.eyebrow(p, m, unit * 4, "Wichtig", color, unit)
        stage.clock_corner(p, w, unit, now)
        # großes Warnzeichen links, Text rechts – gut lesbar aus der letzten Reihe
        side = min(h * 0.42, w * 0.26)
        tri_c = QPointF(m + side / 2, h * 0.52)
        glow = QRadialGradient(tri_c, side)
        glow.setColorAt(0, QColor(color.red(), color.green(), color.blue(), 90))
        glow.setColorAt(1, QColor(0, 0, 0, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(glow)
        p.drawEllipse(tri_c, side, side)
        from PySide6.QtGui import QPainterPath, QPolygonF

        tri = QPolygonF([QPointF(tri_c.x(), tri_c.y() - side * 0.48), QPointF(tri_c.x() + side * 0.52, tri_c.y() + side * 0.42),
                         QPointF(tri_c.x() - side * 0.52, tri_c.y() + side * 0.42)])
        path = QPainterPath()
        path.addPolygon(tri)
        path.closeSubpath()
        p.setPen(QPen(color, unit * 0.9, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(color)
        p.drawPath(path)
        p.setPen(QColor("#0b0c10"))
        p.setFont(_font(side * 0.5, True))
        p.drawText(QRectF(tri_c.x() - side / 2, tri_c.y() - side * 0.28, side, side * 0.66), Qt.AlignCenter, "!")
        col_x = m + side + unit * 6
        head = QRectF(col_x, h * 0.24, w - col_x - m, h * 0.24)
        p.setPen(white)
        p.setFont(_fit(title, head, unit * 8.5, flags=Qt.AlignLeft | Qt.AlignBottom | Qt.TextWordWrap))
        p.drawText(head, Qt.AlignLeft | Qt.AlignBottom | Qt.TextWordWrap, title)
        p.setPen(Qt.NoPen)
        p.setBrush(color)
        p.drawRoundedRect(QRectF(col_x, h * 0.51, unit * 10, unit * 0.5), unit * 0.25, unit * 0.25)
        body = QRectF(col_x, h * 0.55, w - col_x - m, h * 0.3)
        p.setPen(QColor(255, 255, 255, 225))
        p.setFont(_fit(text, body, unit * 4.6, bold=False, flags=Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap))
        p.drawText(body, Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap, text)
    elif design == "frage":
        label("Fragerunde")
        pulse = 1 + 0.04 * math.sin((now - (started or now)) * 2.2)
        c = QPointF(w / 2, h * 0.37)
        r = min(w, h) * 0.19 * pulse
        for k, alpha in ((2.2, 30), (1.6, 60)):
            g = QRadialGradient(c, r * k)
            g.setColorAt(0, QColor(color.red(), color.green(), color.blue(), alpha))
            g.setColorAt(1, QColor(0, 0, 0, 0))
            p.setPen(Qt.NoPen)
            p.setBrush(g)
            p.drawEllipse(c, r * k, r * k)
        p.setPen(QPen(QColor(255, 255, 255, 60), unit * 0.3))
        p.setBrush(color)
        p.drawEllipse(c, r, r)
        p.setPen(QColor("#0b0c10"))
        p.setFont(_font(r * 1.25, True))
        p.drawText(QRectF(c.x() - r, c.y() - r * 1.05, 2 * r, 2 * r), Qt.AlignCenter, "?")
        area = QRectF(m, h * 0.62, w - 2 * m, h * 0.15)
        p.setPen(white)
        p.setFont(_fit(title, area, unit * 8))
        p.drawText(area, Qt.AlignCenter, title)
        sub = QRectF(m, h * 0.78, w - 2 * m, h * 0.12)
        p.setPen(muted)
        p.setFont(_fit(text, sub, unit * 3.6, bold=False))
        p.drawText(sub, Qt.AlignCenter | Qt.TextWordWrap, text)
    elif design == "wlan":
        from .sources import qr_image

        label("WLAN")
        stage.clock_corner(p, w, unit, now)
        side = min(h * 0.6, w * 0.34)
        qr_rect = QRectF(w - m - side, (h - side) / 2 + unit * 2, side, side)
        card = qr_rect.adjusted(-unit * 2, -unit * 2, unit * 2, unit * 2)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 90))
        p.drawRoundedRect(card.translated(0, unit), unit * 3, unit * 3)
        p.setBrush(QColor("#ffffff"))
        p.drawRoundedRect(card, unit * 3, unit * 3)
        img = qr_image(wifi_payload(title, text), border=1)
        p.setRenderHint(QPainter.SmoothPixmapTransform, False)
        p.drawImage(qr_rect, img)
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)
        left = QRectF(m, h * 0.24, card.left() - m - unit * 6, h * 0.6)

        def field(y, caption, value, px, col):
            p.setPen(muted)
            p.setFont(_font(unit * 2.2, True))
            p.drawText(QRectF(left.left(), y, left.width(), unit * 3.5), Qt.AlignLeft | Qt.AlignVCenter, caption)
            box = QRectF(left.left(), y + unit * 4, left.width(), unit * 9)
            p.setBrush(QColor(255, 255, 255, 16))
            p.setPen(QPen(QColor(255, 255, 255, 30), unit * 0.15))
            p.drawRoundedRect(box, unit * 2, unit * 2)
            p.setPen(col)
            inner = box.adjusted(unit * 2.5, 0, -unit * 2, 0)
            p.setFont(_fit(value, inner, px, flags=Qt.AlignLeft | Qt.AlignVCenter))
            p.drawText(inner, Qt.AlignLeft | Qt.AlignVCenter, value)
            return box.bottom()

        y = field(left.top(), "Netzwerk", title, unit * 5.5, white)
        y = field(y + unit * 3, "Passwort", text or "(ohne Passwort)", unit * 5, color.lighter(140))
        p.setPen(QColor(255, 255, 255, 160))
        p.setFont(_font(unit * 2.3))
        p.drawText(QRectF(left.left(), y + unit * 3, left.width(), unit * 8), Qt.AlignLeft | Qt.TextWordWrap,
                   "Handy-Kamera auf den Code richten – das Handy verbindet sich von selbst.")


# --------------------------------------------------------------------------- Weiterschalten
# Seiten mit mehreren Punkten: design → (Art, kleinster Wert, Standard). „mark“ = aktueller Punkt ist markiert,
# „reveal“ = so viele sind aufgedeckt (Standard None = alle).
STEPS = {
    "ablauf": ("mark", 1, 1),
    "tabelle": ("mark", 0, 0),
    "termine": ("mark", 0, 0),
    "willkommen_gast": ("mark", 1, 1),
    "abstimmung": ("mark", 0, 0),
    "sieger": ("reveal", 0, None),
    "zweispaltig": ("reveal", 0, None),
}


def step_range(cfg: dict) -> tuple[int, int] | None:
    """(kleinster, größter) Wert fürs Weiterschalten – None, wenn die Seite nichts zum Weiterschalten hat."""
    design = cfg.get("design")
    if design not in STEPS:
        return None
    lines = [line for line in cfg.get("text", "").splitlines() if line.strip()]
    n = len(lines)
    if design == "ablauf":
        n += 1  # nach dem letzten Punkt: alles erledigt
    elif design == "abstimmung":
        n = min(n, 6)
    elif design == "sieger":
        n = 3
    elif design == "zweispaltig":
        from .screens_more import zweispaltig_pairs

        n = len(zweispaltig_pairs(cfg)[1])
    lo = STEPS[design][1]
    return (lo, max(lo, n))


def step_value(cfg: dict) -> int:
    rng = step_range(cfg)
    if rng is None:
        return 0
    value = cfg.get("current")
    if value is None or value == "":
        value = STEPS[cfg["design"]][2]
    if value is None:
        value = rng[1]  # „reveal“: standardmäßig alles zu sehen
    return max(rng[0], min(rng[1], int(value)))


def step_design(cfg: dict, delta: int) -> bool:
    """Eine Seite weiterschalten (delta ±1). Merkt sich den alten Wert und die Zeit für die Animation."""
    rng = step_range(cfg)
    if rng is None:
        return False
    old = step_value(cfg)
    new = max(rng[0], min(rng[1], old + delta))
    if new == old:
        return False
    cfg["_prev"], cfg["current"], cfg["_changed"] = old, new, time.time()
    return True


def step_label(cfg: dict) -> str:
    """Kurz für Handy und Seitenleiste, z. B. „Punkt 2/5“, „3/3 aufgedeckt“."""
    rng = step_range(cfg)
    if rng is None:
        return ""
    value, hi = step_value(cfg), rng[1]
    if cfg["design"] == "ablauf":
        return "alles erledigt" if value >= hi else f"Punkt {value}/{hi - 1}"
    if cfg["design"] == "abstimmung":
        return f"Lösung: {'ABCDEF'[value - 1]}" if value else "Lösung offen"
    if STEPS[cfg["design"]][0] == "reveal":
        return f"{value}/{hi} aufgedeckt"
    return f"Punkt {value}/{hi}" if value else "nichts markiert"


ANIM_SECONDS = 2.0  # so lange nach Start/Weiterschalten flüssig neu zeichnen


class DesignSource(QWidget):
    """Quelle „Gestaltete Seite“ für Monitor 2 und Szenen."""

    def __init__(self, cfg: dict, parent=None):
        super().__init__(parent)
        self.cfg = {**design_defaults(cfg.get("design", "willkommen")), **cfg}
        self.started = time.time()
        self.cfg["_intro"] = self.started  # Einblend-Animation
        self.setAttribute(Qt.WA_OpaquePaintEvent)
        from . import perf

        interval = TIMED.get(self.cfg["design"])
        self.timer = QTimer(self, interval=perf.interval(interval) if interval else 1000)
        self.timer.timeout.connect(self.update)
        if interval:
            self.timer.start()
        self.governor = perf.FrameGovernor(self.timer)
        self.anim = QTimer(self, interval=perf.interval(16))
        self.anim.timeout.connect(self._anim_tick)
        self.anim.start()

    def _anim_tick(self):
        self.update()
        last = max(self.cfg.get("_intro") or 0, self.cfg.get("_changed") or 0)
        if time.time() - last > ANIM_SECONDS:
            self.anim.stop()

    def step(self, delta: int) -> bool:
        if not step_design(self.cfg, delta):
            return False
        self.anim.start()
        self.update()
        return True

    def stop(self):
        self.timer.stop()
        self.anim.stop()

    def paintEvent(self, _e):
        self.governor.begin()
        p = QPainter(self)
        paint_design(p, self.width(), self.height(), self.cfg, started=self.started)
        p.end()
        self.governor.end()


def render_preview(cfg: dict, w: int = 320, h: int = 180) -> QImage:
    """Kleines Vorschaubild (für die Vorlagen-Auswahl)."""
    img = QImage(w, h, QImage.Format_RGB32)
    p = QPainter(img)
    if cfg.get("type") == "design":
        paint_design(p, w, h, cfg, started=time.time())
    p.end()
    return img


# --------------------------------------------------------------------------- Szenen-Vorlagen
# key → (Name, Beschreibung, Felder, Baufunktion). Felder: "title", "text", "minutes"
def _scene(name, layout, slots, background="#000000"):
    return {"name": name, "layout": layout, "background": background, "slots": slots}


def _clock():
    return {"type": "clock", "show_date": False, "show_seconds": False, "color": "#ffffff", "size": 30}


SCENE_TEMPLATES = {
    "begruessung": ("Begrüßung mit Uhr", "Willkommen-Seite, Uhr klein unten rechts", ("title", "text"),
                    lambda v: _scene(v["name"], "ecke_unten_rechts",
                                     [{**design_defaults("willkommen"), "title": v["title"], "text": v["text"]},
                                      _clock()])),
    "ablauf_uhr": ("Ablauf + Uhr + Hinweis", "Agenda groß, Uhr und Hinweis daneben", ("title", "text"),
                   lambda v: _scene(v["name"], "gross_zwei_klein",
                                    [{**design_defaults("ablauf"), "title": v["title"], "text": v["text"]},
                                     _clock(),
                                     {**design_defaults("ankuendigung"), "title": "Tipp",
                                      "text": "Fragen gerne am Ende."}])),
    "pause": ("Pause mit Countdown", "Pause-Seite mit Restzeit", ("title", "text", "minutes"),
              lambda v: _scene(v["name"], "vollbild",
                               [{**design_defaults("pause"), "title": v["title"], "text": v["text"],
                                 "minutes": v["minutes"]}])),
    "kamera_laufschrift": ("Kamera + Laufschrift", "Kamera im Vollbild, Textleiste unten", ("text",),
                           lambda v: _scene(v["name"], "bauchbinde",
                                            [{"type": "camera", "fit": "cover"},
                                             {"type": "text", "text": v["text"], "color": "#ffffff",
                                              "background": "#111827", "size": 45}])),
    "fragerunde": ("Fragerunde", "Fragen-Seite, Uhr klein oben rechts", ("title", "text"),
                   lambda v: _scene(v["name"], "ecke_oben_rechts",
                                    [{**design_defaults("frage"), "title": v["title"], "text": v["text"]},
                                     _clock()])),
    "gaeste_wlan": ("WLAN für Gäste", "WLAN-Name und Passwort mit QR-Code", ("title", "text"),
                    lambda v: _scene(v["name"], "vollbild",
                                     [{**design_defaults("wlan"), "title": v["title"], "text": v["text"]}])),
    "countdown_start": ("Countdown bis zum Start", "Willkommen-Seite und Countdown", ("title", "minutes"),
                        lambda v: _scene(v["name"], "uebereinander",
                                         [{**design_defaults("willkommen"), "title": v["title"],
                                           "text": "Es geht gleich los"},
                                          {"type": "countdown", "minutes": v["minutes"],
                                           "finished_text": "Los geht's!", "color": "#ffffff", "size": 40}])),
}
def _design(key: str, **values) -> dict:
    return {**design_defaults(key), **{k: v for k, v in values.items() if v not in (None, "")}}


def _countdown(minutes: float) -> dict:
    return {"type": "countdown", "minutes": minutes, "finished_text": "Zeit ist um!", "color": "#ffffff", "size": 40}


def _qr() -> dict:
    return {"type": "cast"}


SCENE_TEMPLATES.update({
    "quiz": ("Quiz mit Zeit", "Frage mit Antworten, Countdown klein", ("title", "text", "minutes"),
             lambda v: _scene(v["name"], "ecke_oben_rechts",
                              [_design("abstimmung", title=v["title"], text=v["text"]), _countdown(v["minutes"])])),
    "abstimmung_handy": ("Abstimmung per Handy", "Frage und QR-Code: Handys scannen und senden", ("title", "text"),
                         lambda v: _scene(v["name"], "ecke_unten_rechts",
                                          [_design("abstimmung", title=v["title"], text=v["text"]), _qr()])),
    "termine_uhr": ("Termine + Uhr", "Nächste Termine, Uhr klein", ("title", "text"),
                    lambda v: _scene(v["name"], "ecke_oben_rechts",
                                     [_design("termine", title=v["title"], text=v["text"]), _clock()])),
    "geburtstag": ("Geburtstag", "Glückwunsch mit Konfetti", ("title", "text"),
                   lambda v: _scene(v["name"], "vollbild", [_design("geburtstag", title=v["title"], text=v["text"])])),
    "siegerehrung": ("Siegerehrung", "Podest mit Konfetti", ("title", "text"),
                     lambda v: _scene(v["name"], "vollbild", [_design("sieger", title=v["title"], text=v["text"])])),
    "event_countdown": ("Countdown zum Event", "Restzeit bis zur Uhrzeit, Laufschrift unten", ("title", "text"),
                        lambda v: _scene(v["name"], "bauchbinde",
                                         [_design("event_countdown", title=v["title"], text=v["text"]),
                                          {"type": "text", "text": "Wir freuen uns auf euch!", "color": "#ffffff",
                                           "background": "#831843", "size": 45}])),
    "nachrichten": ("Nachrichten", "Schlagzeile groß mit Laufschrift", ("title", "text"),
                    lambda v: _scene(v["name"], "bauchbinde",
                                     [_design("schlagzeile", title=v["title"], text=v["text"]),
                                      {"type": "text", "text": v["text"], "color": "#ffffff", "background": "#991b1b",
                                       "size": 45}])),
    "handy_willkommen": ("Willkommen + Handy-QR", "Begrüßung und QR-Code zum Mitmachen", ("title", "text"),
                         lambda v: _scene(v["name"], "nebeneinander",
                                          [_design("willkommen", title=v["title"], text=v["text"]), _qr()])),
})
def _card(key: str, v: dict, **extra) -> dict:
    return _design(key, title=v.get("title"), text=v.get("text"), **extra)


SCENE_TEMPLATES.update({
    "stream": ("Stream-Overlay", "LIVE-Karte groß, Kamera klein unten rechts", ("title", "text"),
               lambda v: _scene(v["name"], "ecke_unten_rechts", [_card("live", v), {"type": "camera", "fit": "cover"}])),
    "stream_start": ("Stream startet gleich", "Coming soon mit Countdown", ("title", "minutes"),
                     lambda v: _scene(v["name"], "uebereinander",
                                      [_design("comingsoon", title=v["title"], text="Stay tuned"),
                                       _countdown(v["minutes"])])),
    "partynacht": ("Partynacht", "Neon-Schild mit Musik-Karte klein", ("title", "text"),
                   lambda v: _scene(v["name"], "ecke_unten_rechts",
                                    [_card("neon", v), _design("nowplaying")])),
    "musik": ("Musik läuft", "Now Playing im Vollbild", ("title", "text"),
              lambda v: _scene(v["name"], "vollbild", [_card("nowplaying", v)])),
    "gaming": ("Gaming-Duell", "Versus-Bildschirm mit Countdown", ("title", "text", "minutes"),
               lambda v: _scene(v["name"], "bauchbinde",
                                [_card("versus", v), _countdown(v["minutes"])])),
    "retro": ("Retro-Abend", "Synthwave mit Uhr", ("title", "text"),
              lambda v: _scene(v["name"], "ecke_oben_rechts", [_card("synthwave", v), _clock()])),
    "link_teilen": ("Link teilen", "Link-Karte mit QR-Code im Vollbild", ("title", "text"),
                    lambda v: _scene(v["name"], "vollbild", [_card("linkkarte", v)])),
    "praesentation_start": ("Präsentation startet", "Glas-Karte und Countdown", ("title", "text", "minutes"),
                            lambda v: _scene(v["name"], "uebereinander",
                                             [_card("glas", v), _countdown(v["minutes"])])),
    "kamera_neon": ("Kamera + Neon-Titel", "Kamera groß, Neon-Schrift als Leiste unten", ("title", "text"),
                    lambda v: _scene(v["name"], "bauchbinde",
                                     [{"type": "camera", "fit": "cover"}, _card("neon", v)])),
})

TEMPLATE_CATEGORIES = {
    "stream": "Party & Event", "stream_start": "Party & Event", "partynacht": "Party & Event", "musik": "Party & Event",
    "gaming": "Party & Event", "retro": "Style", "link_teilen": "Info", "praesentation_start": "Präsentation",
    "kamera_neon": "Style",
    "begruessung": "Party & Event", "ablauf_uhr": "Präsentation", "pause": "Zeit",
    "kamera_laufschrift": "Info", "fragerunde": "Präsentation", "gaeste_wlan": "Info",
    "countdown_start": "Party & Event", "quiz": "Präsentation", "abstimmung_handy": "Präsentation", "termine_uhr": "Info", "geburtstag": "Party & Event", "siegerehrung": "Party & Event", "event_countdown": "Party & Event",
    "nachrichten": "Info", "handy_willkommen": "Party & Event",
}
TEMPLATE_LABELS = {"gaming": ("Links:", "Rechts:"), "musik": ("Song:", "Künstler:"), "link_teilen": ("Titel:", "Link:"),
                   "partynacht": ("Neon-Text:", "Zeile darunter:"),"gaeste_wlan": ("WLAN-Name:", "Passwort:"), "ablauf_uhr": ("Überschrift:", "Punkte:"),
                   "kamera_laufschrift": ("Titel:", "Textleiste:"), "quiz": ("Frage:", "Antworten:"),
                   "abstimmung_handy": ("Frage:", "Antworten:"),
                   "termine_uhr": ("Überschrift:", "Datum | Termin:"), "siegerehrung": ("Überschrift:", "Platz 1, 2, 3:"),
                   "event_countdown": ("Text oben:", "Uhrzeit/Datum:"), "begriff_kamera": ("Begriff:", "Erklärung:")}

TEMPLATE_DEFAULTS = {
    "begruessung": {"title": "Herzlich willkommen!", "text": "Schön, dass ihr da seid."},
    "ablauf_uhr": {"title": "Heute", "text": DESIGNS["ablauf"][3]},
    "pause": {"title": "Pause", "text": "Gleich geht's weiter.", "minutes": 10},
    "kamera_laufschrift": {"text": "Live dabei – schön, dass du zuschaust"},
    "fragerunde": {"title": "Fragen?", "text": "Jetzt ist Zeit für eure Fragen."},
    "gaeste_wlan": {"title": "Gäste-WLAN", "text": ""},  # Passwort bitte selbst eintragen
    "countdown_start": {"title": "Herzlich willkommen!", "minutes": 5},
    **{key: {"title": DESIGNS[d][2], "text": DESIGNS[d][3], "minutes": m} for key, d, m in (
        ("quiz", "abstimmung", 1), ("abstimmung_handy", "abstimmung", 5), ("termine_uhr", "termine", 5), ("geburtstag", "geburtstag", 5), ("siegerehrung", "sieger", 5),
        ("event_countdown", "event_countdown", 5), ("nachrichten", "schlagzeile", 5),
        ("handy_willkommen", "willkommen", 5),
        ("stream", "live", 5), ("stream_start", "comingsoon", 5), ("partynacht", "neon", 5), ("musik", "nowplaying", 5),
        ("gaming", "versus", 3), ("retro", "synthwave", 5), ("link_teilen", "linkkarte", 5),
        ("praesentation_start", "glas", 5), ("kamera_neon", "neon", 5))},
}
TEMPLATE_DEFAULTS["stream_start"]["title"] = "Stream startet gleich"
TEMPLATE_DEFAULTS["praesentation_start"].update(title="Gleich geht's los", text="Schnapp dir einen Platz")
TEMPLATE_DEFAULTS["kamera_neon"].update(title="ON AIR", text="")



def build_template(key: str, values: dict) -> dict:
    """Szene aus einer Vorlage bauen (values: name, title, text, minutes)."""
    name, _desc, _fields, build = SCENE_TEMPLATES[key]
    v = {"name": values.get("name") or name, **TEMPLATE_DEFAULTS.get(key, {}),
         **{k: val for k, val in values.items() if val not in (None, "")}}
    v["minutes"] = float(v.get("minutes", 5) or 5)
    v.setdefault("title", "")
    v.setdefault("text", "")
    return build(v)


def render_scene_preview(scene: dict, w: int = 320, h: int = 180) -> QImage:
    """Vorschau einer Szene mit echtem Inhalt der Felder (Karten, Uhr, Countdown, Kamera, Text …)."""
    from .scenes import layout_slots
    from .ui import icons

    img = QImage(w, h, QImage.Format_RGB32)
    img.fill(QColor(scene.get("background", "#000000")))
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    now = time.time()
    if not any(scene.get("slots", [])):  # leere Szene: freundliches Plus statt schwarzer Fläche
        g = QLinearGradient(0, 0, w, h)
        g.setColorAt(0, QColor("#1e293b"))
        g.setColorAt(1, QColor("#0f172a"))
        p.fillRect(0, 0, w, h, g)
        p.setPen(QPen(QColor(255, 255, 255, 60), max(1.0, w / 160), Qt.DashLine))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(QRectF(w * 0.06, h * 0.1, w * 0.88, h * 0.8), w * 0.03, w * 0.03)
        icons.paint(p, "plus", QRectF(w / 2 - h * 0.14, h / 2 - h * 0.14, h * 0.28, h * 0.28), "#94a3b8", 2.0)
        p.end()
        return img
    for (x, y, sw, sh, _name), slot in zip(layout_slots(scene.get("layout", "vollbild")), scene.get("slots", [])):
        if not slot:
            continue
        r = QRectF(x * w, y * h, sw * w, sh * h)
        p.save()
        p.setClipRect(r)
        p.translate(r.topLeft())
        t = slot.get("type")
        rw, rh = int(r.width()), int(r.height())
        if t == "design":
            paint_design(p, rw, rh, slot, now=now, started=now)
        else:
            p.fillRect(QRectF(0, 0, rw, rh), QColor(slot.get("background", "#0b0f19")))
            label = {"clock": time.strftime("%H:%M"), "countdown": f"{int(float(slot.get('minutes', 5)))}:00",
                     "text": slot.get("text", "")}.get(t)
            if label:
                p.setPen(QColor(slot.get("color", "#ffffff")))
                p.setFont(_fit(label, QRectF(0, 0, rw, rh), rh * 0.5))
                p.drawText(QRectF(0, 0, rw, rh), int(Qt.AlignCenter | Qt.TextWordWrap), label)
            else:
                icon = {"camera": "camera", "cast": "qr", "airplay": "phone", "website": "globe"}.get(t, "image")
                s = min(rw, rh) * 0.35
                icons.paint(p, icon, QRectF((rw - s) / 2, (rh - s) / 2, s, s), "#94a3b8", 1.8)
        p.restore()
        if len(scene.get("slots", [])) > 1:  # Feldgrenzen andeuten
            p.setPen(QPen(QColor(255, 255, 255, 60), 1))
            p.setBrush(Qt.NoBrush)
            p.drawRect(r.adjusted(0.5, 0.5, -0.5, -0.5))
    p.end()
    return img
