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
from .screens_more import MORE_CATEGORIES, MORE_DESIGNS, MORE_LABELS, MORE_TIMED, PAINTERS, Ctx  # noqa: E402

from .screens_cards import CARD_DESIGNS, CARD_LABELS, CARD_PAINTERS, CARD_TIMED, paint_card  # noqa: E402

DESIGNS.update(MORE_DESIGNS)
DESIGNS.update(CARD_DESIGNS)
TIMED.update(MORE_TIMED)
TIMED.update(CARD_TIMED)
CATEGORY_NAMES = ["Style", "Party & Event", "Präsentation", "Info", "Zeit"]
CATEGORIES = {"willkommen": "Party & Event", "ablauf": "Präsentation", "pause": "Zeit", "laufschrift": "Info",
              "zitat": "Style", "ankuendigung": "Info", "frage": "Präsentation", "wlan": "Info",
              **MORE_CATEGORIES, **{k: "Style" for k in CARD_DESIGNS},
              "nowplaying": "Party & Event", "live": "Party & Event", "versus": "Party & Event",
              "linkkarte": "Info", "comingsoon": "Info"}
# Beschriftung der Eingabefelder je Seite (Titel, Text)
FIELD_LABELS = {"wlan": ("WLAN-Name:", "Passwort:"), "zitat": ("Zitat:", "Autor:"),
                "ablauf": ("Überschrift:", "Punkte (je Zeile einer):"), "laufschrift": ("Titel:", "Laufschrift:"),
                **MORE_LABELS, **CARD_LABELS}


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


def wifi_payload(ssid: str, password: str) -> str:
    """Inhalt für den WLAN-QR-Code (Handys verbinden sich damit direkt)."""
    def esc(s: str) -> str:
        return "".join("\\" + ch if ch in "\\;,:\"" else ch for ch in s)
    kind = "WPA" if password else "nopass"
    return f"WIFI:T:{kind};S:{esc(ssid)};P:{esc(password)};;"


def _font(px: float, bold: bool = False, weight: QFont.Weight | None = None) -> QFont:
    f = QFont()
    f.setPixelSize(max(6, int(px)))
    if weight is not None:
        f.setWeight(weight)
    else:
        f.setBold(bold)
    return f


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
    g = QLinearGradient(0, 0, w, h)
    g.setColorAt(0, QColor.fromHsvF(color.hsvHueF() % 1.0 if color.hsvHueF() >= 0 else 0.6, 0.55, 0.16))
    g.setColorAt(1, QColor("#05070d"))
    p.fillRect(0, 0, w, h, g)
    glow = QRadialGradient(QPointF(w * 0.85, h * 0.1), max(w, h) * 0.6)
    c = QColor(color)
    c.setAlpha(70)
    glow.setColorAt(0, c)
    glow.setColorAt(1, QColor(0, 0, 0, 0))
    p.fillRect(0, 0, w, h, glow)


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

    def accent_bar(x, y, length):
        p.setPen(Qt.NoPen)
        p.setBrush(color)
        p.drawRoundedRect(QRectF(x, y, length, unit * 0.6), unit * 0.3, unit * 0.3)

    if design == "willkommen":
        area = QRectF(w * 0.1, h * 0.22, w * 0.8, h * 0.34)
        p.setPen(white)
        p.setFont(_fit(title, area, unit * 9))
        p.drawText(area, Qt.AlignCenter | Qt.TextWordWrap, title)
        accent_bar(w / 2 - unit * 6, h * 0.6, unit * 12)
        sub = QRectF(w * 0.12, h * 0.64, w * 0.76, h * 0.16)
        p.setPen(muted)
        p.setFont(_fit(text, sub, unit * 3.6, bold=False))
        p.drawText(sub, Qt.AlignCenter | Qt.TextWordWrap, text)
        p.setFont(_font(unit * 2.4, True))
        p.setPen(QColor(255, 255, 255, 140))
        p.drawText(QRectF(0, h * 0.86, w, h * 0.08), Qt.AlignCenter, time.strftime("%H:%M", time.localtime(now)))
    elif design == "ablauf":
        items = [line.strip() for line in text.splitlines() if line.strip()]
        current = int(cfg.get("current", 1))
        p.setPen(white)
        p.setFont(_font(unit * 5, True))
        p.drawText(QRectF(w * 0.08, h * 0.07, w * 0.84, h * 0.12), Qt.AlignLeft | Qt.AlignVCenter, title)
        accent_bar(w * 0.08, h * 0.2, unit * 10)
        if items:
            row_h = min(h * 0.13, h * 0.68 / len(items))
            for i, item in enumerate(items, start=1):
                y = h * 0.25 + (i - 1) * row_h
                active, done = i == current, i < current
                box = QRectF(w * 0.08, y + row_h * 0.1, w * 0.84, row_h * 0.8)
                if active:
                    bg = QColor(color)
                    bg.setAlpha(60)
                    p.setPen(QPen(color, max(1.0, unit * 0.25)))
                    p.setBrush(bg)
                    p.drawRoundedRect(box, row_h * 0.2, row_h * 0.2)
                badge = QRectF(box.left() + row_h * 0.15, box.center().y() - row_h * 0.26, row_h * 0.52, row_h * 0.52)
                p.setPen(Qt.NoPen)
                p.setBrush(color if (active or done) else QColor(255, 255, 255, 40))
                p.drawEllipse(badge)
                p.setPen(white)
                p.setFont(_font(row_h * 0.26, True))
                p.drawText(badge, Qt.AlignCenter, "✓" if done else str(i))
                p.setPen(white if not done else QColor(255, 255, 255, 120))
                p.setFont(_font(row_h * 0.36, active))
                p.drawText(box.adjusted(row_h * 0.9, 0, -unit, 0), Qt.AlignLeft | Qt.AlignVCenter,
                           QFontMetricsF(_font(row_h * 0.36, active)).elidedText(item, Qt.ElideRight,
                                                                                box.width() - row_h * 1.2))
    elif design == "pause":
        total = max(1.0, float(cfg.get("minutes", 10)) * 60)
        left = max(0.0, total - (now - (started or now)))
        c = QPointF(w / 2, h * 0.43)
        r = min(w, h) * 0.26
        p.setPen(QPen(QColor(255, 255, 255, 30), r * 0.08))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(c, r, r)
        p.setPen(QPen(color, r * 0.08, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(QRectF(c.x() - r, c.y() - r, 2 * r, 2 * r), 90 * 16, int(360 * 16 * left / total))
        p.setPen(white)
        p.setFont(_font(r * 0.46, True))
        m, s = divmod(int(math.ceil(left)), 60)
        p.drawText(QRectF(c.x() - r, c.y() - r * 0.45, 2 * r, r * 0.6), Qt.AlignCenter, f"{m}:{s:02d}")
        p.setFont(_font(r * 0.18, True))
        p.setPen(muted)
        p.drawText(QRectF(c.x() - r, c.y() + r * 0.15, 2 * r, r * 0.3), Qt.AlignCenter, title.upper())
        until = time.strftime("%H:%M", time.localtime((started or now) + total))
        p.setPen(white)
        line = QRectF(w * 0.1, h * 0.78, w * 0.8, h * 0.09)
        p.setFont(_fit(f"{text}  ·  weiter um {until}" if text else f"Weiter um {until}", line, unit * 3.4, False))
        p.drawText(line, Qt.AlignCenter, f"{text}  ·  weiter um {until}" if text else f"Weiter um {until}")
    elif design == "laufschrift":
        area = QRectF(w * 0.08, h * 0.2, w * 0.84, h * 0.4)
        p.setPen(white)
        p.setFont(_fit(title, area, unit * 10))
        p.drawText(area, Qt.AlignCenter | Qt.TextWordWrap, title)
        band = QRectF(0, h * 0.78, w, h * 0.14)
        p.setPen(Qt.NoPen)
        p.setBrush(color)
        p.drawRect(band)
        f = _font(band.height() * 0.5, True)
        p.setFont(f)
        msg = (text or " ").replace("\n", "   ·   ") + "      •      "
        width = QFontMetricsF(f).horizontalAdvance(msg)
        speed = unit * 12  # Pixel pro Sekunde
        offset = ((now - (started or now)) * speed) % max(1.0, width)
        p.setPen(QColor("#ffffff"))
        x = -offset
        while x < w:
            p.drawText(QRectF(x, band.top(), width, band.height()), Qt.AlignVCenter | Qt.AlignLeft, msg)
            x += width
    elif design == "zitat":
        p.setPen(QColor(color.red(), color.green(), color.blue(), 90))
        p.setFont(_font(unit * 22, True))
        p.drawText(QRectF(w * 0.05, h * 0.02, w * 0.3, h * 0.4), Qt.AlignLeft | Qt.AlignTop, "“")
        area = QRectF(w * 0.12, h * 0.2, w * 0.76, h * 0.48)
        p.setPen(white)
        p.setFont(_fit(title, area, unit * 6))
        p.drawText(area, Qt.AlignCenter | Qt.TextWordWrap, title)
        if text:
            accent_bar(w / 2 - unit * 4, h * 0.73, unit * 8)
            p.setPen(muted)
            p.setFont(_font(unit * 3, True))
            p.drawText(QRectF(0, h * 0.76, w, h * 0.1), Qt.AlignCenter, f"— {text}")
    elif design == "ankuendigung":
        card = QRectF(w * 0.1, h * 0.18, w * 0.8, h * 0.64)
        p.setPen(QPen(color, unit * 0.4))
        p.setBrush(QColor(255, 255, 255, 14))
        p.drawRoundedRect(card, unit * 3, unit * 3)
        badge = QRectF(card.left() + unit * 3, card.top() + unit * 3, unit * 9, unit * 9)
        p.setPen(Qt.NoPen)
        p.setBrush(color)
        p.drawEllipse(badge)
        p.setPen(white)
        p.setFont(_font(unit * 6, True))
        p.drawText(badge, Qt.AlignCenter, "!")
        head = QRectF(badge.right() + unit * 3, badge.top(), card.right() - badge.right() - unit * 6, badge.height())
        p.setFont(_fit(title, head, unit * 5.5, flags=Qt.AlignLeft | Qt.AlignVCenter | Qt.TextWordWrap))
        p.drawText(head, Qt.AlignLeft | Qt.AlignVCenter | Qt.TextWordWrap, title)
        body = QRectF(card.left() + unit * 3, badge.bottom() + unit * 3, card.width() - unit * 6,
                      card.bottom() - badge.bottom() - unit * 6)
        p.setPen(QColor(255, 255, 255, 220))
        p.setFont(_fit(text, body, unit * 4.5, bold=False, flags=Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap))
        p.drawText(body, Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap, text)
    elif design == "frage":
        pulse = 1 + 0.04 * math.sin((now - (started or now)) * 2.2)
        c = QPointF(w / 2, h * 0.36)
        r = min(w, h) * 0.2 * pulse
        g = QRadialGradient(c, r * 1.6)
        g.setColorAt(0, QColor(color.red(), color.green(), color.blue(), 120))
        g.setColorAt(1, QColor(0, 0, 0, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(g)
        p.drawEllipse(c, r * 1.6, r * 1.6)
        p.setBrush(color)
        p.drawEllipse(c, r, r)
        p.setPen(QColor("#111827"))
        p.setFont(_font(r * 1.3, True))
        p.drawText(QRectF(c.x() - r, c.y() - r, 2 * r, 2 * r), Qt.AlignCenter, "?")
        area = QRectF(w * 0.1, h * 0.62, w * 0.8, h * 0.14)
        p.setPen(white)
        p.setFont(_fit(title, area, unit * 7))
        p.drawText(area, Qt.AlignCenter, title)
        sub = QRectF(w * 0.1, h * 0.77, w * 0.8, h * 0.12)
        p.setPen(muted)
        p.setFont(_fit(text, sub, unit * 3.2, bold=False))
        p.drawText(sub, Qt.AlignCenter | Qt.TextWordWrap, text)
    elif design == "wlan":
        from .sources import qr_image

        side = min(h * 0.62, w * 0.36)
        qr_rect = QRectF(w * 0.58, (h - side) / 2, side, side)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#ffffff"))
        p.drawRoundedRect(qr_rect.adjusted(-unit, -unit, unit, unit), unit * 1.5, unit * 1.5)
        img = qr_image(wifi_payload(title, text), border=1)
        p.setRenderHint(QPainter.SmoothPixmapTransform, False)
        p.drawImage(qr_rect, img)
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)
        left = QRectF(w * 0.07, h * 0.2, w * 0.46, h * 0.6)
        p.setPen(muted)
        p.setFont(_font(unit * 2.6, True))
        p.drawText(QRectF(left.left(), left.top(), left.width(), unit * 4), Qt.AlignLeft, "WLAN")
        p.setPen(white)
        name_r = QRectF(left.left(), left.top() + unit * 4.5, left.width(), unit * 9)
        p.setFont(_fit(title, name_r, unit * 6, flags=Qt.AlignLeft | Qt.AlignVCenter))
        p.drawText(name_r, Qt.AlignLeft | Qt.AlignVCenter, title)
        p.setPen(muted)
        p.setFont(_font(unit * 2.6, True))
        p.drawText(QRectF(left.left(), name_r.bottom() + unit * 3, left.width(), unit * 4), Qt.AlignLeft, "PASSWORT")
        pw_r = QRectF(left.left(), name_r.bottom() + unit * 7.5, left.width(), unit * 8)
        p.setPen(color.lighter(130))
        p.setFont(_fit(text or "(ohne Passwort)", pw_r, unit * 5, flags=Qt.AlignLeft | Qt.AlignVCenter))
        p.drawText(pw_r, Qt.AlignLeft | Qt.AlignVCenter, text or "(ohne Passwort)")
        p.setPen(QColor(255, 255, 255, 150))
        p.setFont(_font(unit * 2.2))
        p.drawText(QRectF(left.left(), pw_r.bottom() + unit * 4, left.width(), unit * 8),
                   Qt.AlignLeft | Qt.TextWordWrap, "Mit der Handy-Kamera den QR-Code scannen – das Handy verbindet sich.")


class DesignSource(QWidget):
    """Quelle „Gestaltete Seite“ für Monitor 2 und Szenen."""

    def __init__(self, cfg: dict, parent=None):
        super().__init__(parent)
        self.cfg = {**design_defaults(cfg.get("design", "willkommen")), **cfg}
        self.started = time.time()
        self.setAttribute(Qt.WA_OpaquePaintEvent)
        interval = TIMED.get(self.cfg["design"])
        self.timer = QTimer(self, interval=interval or 1000)
        self.timer.timeout.connect(self.update)
        if interval:
            self.timer.start()

    def stop(self):
        self.timer.stop()

    def paintEvent(self, _e):
        p = QPainter(self)
        paint_design(p, self.width(), self.height(), self.cfg, started=self.started)
        p.end()


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
