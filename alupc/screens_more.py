"""Weitere gestaltete Seiten für Monitor 2 (Ergänzung zu screens.py).

Jede Seite: Eintrag in MORE_DESIGNS (Name, Beschreibung, Beispiel-Titel, Beispiel-Text, Farbe), Kategorie und eine
Zeichenfunktion `paint(ctx)`. Listen und Tabellen: je Zeile ein Eintrag, Spalten mit „|“ trennen.
"""

from __future__ import annotations

import math
import random
import re
import time
from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPainterPath, QPen, QRadialGradient

MORE_DESIGNS: dict[str, tuple[str, str, str, str, str]] = {
    "event_countdown": ("Countdown bis …", "Restzeit bis zu einer Uhrzeit oder einem Datum", "Es geht los in",
                        "18:00", "#ec4899"),
    "geburtstag": ("Geburtstag", "Glückwunsch mit Konfetti", "Alles Gute, Lea!",
                   "Wir wünschen dir einen tollen Tag!", "#f59e0b"),
    "tabelle": ("Tabelle / Stundenplan", "Zeilen, Spalten mit | trennen", "Stundenplan Montag",
                "08:00 | Mathe\n08:45 | Deutsch\n09:45 | Pause\n10:05 | Englisch\n10:50 | Sport", "#0ea5e9"),
    "abstimmung": ("Abstimmung / Quiz", "Frage und bis zu 6 Antworten A, B, C …", "Was ist die Hauptstadt von Australien?",
                   "Sydney\nCanberra\nMelbourne\nPerth", "#8b5cf6"),
    "aufgabe": ("Arbeitsauftrag", "Aufgabe in Schritten, mit Zeitangabe", "Arbeitsauftrag",
                "Lies den Text auf S. 42.\nMarkiere wichtige Stellen.\nBeantworte die Fragen 1–3.", "#22c55e"),
    "regeln": ("Regeln / Hinweise", "Liste mit Häkchen", "Unsere Regeln",
               "Wir lassen einander ausreden.\nHandys bleiben in der Tasche.\nWir helfen uns gegenseitig.", "#14b8a6"),
    "gruppen": ("Gruppeneinteilung", "Je Zeile: Gruppe: Mitglieder", "Gruppen",
                "Gruppe 1: Anna, Ben, Chris\nGruppe 2: Dana, Emil, Finn\nGruppe 3: Greta, Hanna, Ida\n"
                "Gruppe 4: Jonas, Kim, Lena", "#f97316"),
    "ruhe": ("Stillarbeit / Ruhe", "Ruhige Seite mit sanfter Animation", "Stillarbeit", "Bitte leise arbeiten.",
             "#38bdf8"),
    "danke": ("Danke / Ende", "Abschluss einer Stunde oder Veranstaltung", "Danke!", "Bis zum nächsten Mal.",
              "#6366f1"),
    "hausaufgaben": ("Hausaufgaben", "Aufgabe | bis wann, je Zeile", "Hausaufgaben",
                     "S. 42 Nr. 3 | Mittwoch\nVokabeln Unit 4 | Freitag\nReferat vorbereiten | nächste Woche",
                     "#eab308"),
    "schlagzeile": ("Schlagzeile", "Nachrichten-Stil mit Eilmeldung", "Schulfest am Freitag!",
                    "Ab 14 Uhr auf dem Schulhof – alle sind eingeladen.", "#dc2626"),
    "kennzahl": ("Große Zahl", "Eine Zahl mit Beschriftung", "1.250 €", "gesammelt für den guten Zweck", "#10b981"),
    "termine": ("Termine", "Datum | Termin, je Zeile", "Nächste Termine",
                "12.10. | Elternabend\n24.10. | Wandertag\n03.11. | Projektwoche", "#a855f7"),
    "tuerschild": ("Türschild", "Raum, Klasse, Hinweis", "Raum 204", "Klasse 7b · Mathematik\nBitte nicht stören",
                   "#64748b"),
    "speiseplan": ("Speiseplan", "Tag | Gericht, je Zeile", "Mensa diese Woche",
                   "Mo | Spaghetti Bolognese\nDi | Gemüsecurry\nMi | Fischstäbchen\nDo | Pizza\nFr | Kartoffelsuppe",
                   "#84cc16"),
    "sieger": ("Siegerehrung", "Plätze 1–3 mit Podest", "Siegerehrung", "Team Blau\nTeam Rot\nTeam Grün", "#eab308"),
    "stimmung": ("Stimmungsbarometer", "Wie geht's euch? Fünf Gesichter", "Wie geht es euch heute?",
                 "Zeigt mit den Fingern: 1 bis 5", "#22c55e"),
    "zweispaltig": ("Pro & Contra", "Zwei Spalten gegenüberstellen (Zeilen: links | rechts)", "Pro & Contra",
                    "Spart Zeit | Kostet Geld\nMacht Spaß | Braucht Übung\nGut fürs Team | Mehr Absprachen", "#0ea5e9"),
    "begriff": ("Begriff / Definition", "Wort groß, Erklärung darunter", "Photosynthese",
                "Pflanzen bilden mit Licht aus Wasser und CO₂ Zucker und Sauerstoff.", "#16a34a"),
    "willkommen_gast": ("Willkommen Gäste", "Begrüßung für Besucher mit Namen", "Herzlich willkommen",
                        "Familie Müller\nTeam Schulentwicklung\nGäste aus Partnerschule", "#f97316"),
}

MORE_CATEGORIES = {
    "event_countdown": "Veranstaltung", "geburtstag": "Spaß", "tabelle": "Unterricht", "abstimmung": "Unterricht",
    "aufgabe": "Unterricht", "regeln": "Info", "gruppen": "Unterricht", "ruhe": "Pause & Zeit",
    "danke": "Veranstaltung", "hausaufgaben": "Unterricht", "schlagzeile": "Info", "kennzahl": "Info",
    "termine": "Info", "tuerschild": "Info", "speiseplan": "Info", "sieger": "Spaß", "stimmung": "Unterricht",
    "zweispaltig": "Unterricht", "begriff": "Unterricht", "willkommen_gast": "Veranstaltung",
}
MORE_TIMED = {"event_countdown": 500, "geburtstag": 33, "ruhe": 50, "sieger": 40, "schlagzeile": 1000}
MORE_LABELS = {
    "event_countdown": ("Text oben:", "Uhrzeit/Datum (z. B. 18:00 oder 24.12.2026 18:00):"),
    "tabelle": ("Überschrift:", "Zeilen (Spalten mit | trennen):"),
    "abstimmung": ("Frage:", "Antworten (je Zeile eine):"),
    "aufgabe": ("Überschrift:", "Schritte (je Zeile einer):"),
    "regeln": ("Überschrift:", "Regeln (je Zeile eine):"),
    "gruppen": ("Überschrift:", "Gruppen (Name: Mitglieder):"),
    "hausaufgaben": ("Überschrift:", "Aufgabe | bis wann:"),
    "termine": ("Überschrift:", "Datum | Termin:"),
    "speiseplan": ("Überschrift:", "Tag | Gericht:"),
    "sieger": ("Überschrift:", "Platz 1, 2, 3 (je Zeile):"),
    "kennzahl": ("Zahl:", "Beschriftung:"),
    "zweispaltig": ("Überschrift:", "Zeilen: links | rechts"),
    "begriff": ("Begriff:", "Erklärung:"),
    "tuerschild": ("Raum:", "Zeilen darunter:"),
    "willkommen_gast": ("Titel:", "Namen (je Zeile):"),
}


@dataclass
class Ctx:
    p: QPainter
    w: int
    h: int
    cfg: dict
    now: float
    started: float
    color: QColor
    unit: float

    @property
    def title(self) -> str:
        return self.cfg.get("title", "")

    @property
    def text(self) -> str:
        return self.cfg.get("text", "")

    def lines(self) -> list[str]:
        return [line.strip() for line in self.text.splitlines() if line.strip()]


WHITE = QColor("#f8fafc")
MUTED = QColor(255, 255, 255, 170)


def _font(px: float, bold: bool = False) -> QFont:
    f = QFont()
    f.setPixelSize(max(6, int(px)))
    f.setBold(bold)
    return f


def _fit(text: str, rect: QRectF, start_px: float, bold: bool = True, flags=Qt.AlignCenter | Qt.TextWordWrap) -> QFont:
    px = start_px
    while px > 8:
        f = _font(px, bold)
        r = QFontMetricsF(f).boundingRect(rect, int(flags), text)
        if r.height() <= rect.height() and r.width() <= rect.width() + 1:
            return f
        px *= 0.92
    return _font(8, bold)


def _text(c: Ctx, rect: QRectF, text: str, px: float, bold=True, color=WHITE, flags=Qt.AlignCenter | Qt.TextWordWrap):
    c.p.setPen(color)
    c.p.setFont(_fit(text, rect, px, bold, flags))
    c.p.drawText(rect, int(flags), text)


def _heading(c: Ctx, y: float = 0.07) -> float:
    """Überschrift links oben mit Akzentstrich; gibt die Y-Position darunter zurück."""
    u = c.unit
    _text(c, QRectF(c.w * 0.07, c.h * y, c.w * 0.86, c.h * 0.11), c.title, u * 5,
          flags=Qt.AlignLeft | Qt.AlignVCenter)
    c.p.setPen(Qt.NoPen)
    c.p.setBrush(c.color)
    c.p.drawRoundedRect(QRectF(c.w * 0.07, c.h * (y + 0.125), u * 10, u * 0.6), u * 0.3, u * 0.3)
    return c.h * (y + 0.18)


def _confetti(c: Ctx, count: int = 120) -> None:
    rng = random.Random(7)
    t = c.now - (c.started or c.now)
    colors = ["#ef4444", "#f59e0b", "#22c55e", "#3b82f6", "#a855f7", "#ec4899", "#facc15"]
    for i in range(count):
        x = rng.random()
        speed = rng.uniform(0.05, 0.14)
        y = (rng.random() + t * speed) % 1.1 - 0.05
        size = rng.uniform(0.5, 1.2) * c.unit
        angle = t * rng.uniform(1, 4) + i
        c.p.save()
        c.p.translate(x * c.w + math.sin(t + i) * c.unit * 2, y * c.h)
        c.p.rotate(math.degrees(angle))
        c.p.setPen(Qt.NoPen)
        col = QColor(colors[i % len(colors)])
        col.setAlpha(170)  # etwas durchsichtig – Text bleibt gut lesbar
        c.p.setBrush(col)
        c.p.drawRect(QRectF(-size, -size * 0.4, size * 2, size * 0.8))
        c.p.restore()


def _rows(c: Ctx, top: float, rows: list[tuple[str, str]], left_pill: bool = True) -> None:
    """Tabelle: linke Spalte als farbige Marke, rechte als Text – Zeilen wechselnd leicht hinterlegt."""
    if not rows:
        return
    u = c.unit
    avail = c.h * 0.9 - top
    row_h = min(c.h * 0.13, avail / len(rows))
    left_w = c.w * 0.2 if any(a for a, _b in rows) else 0
    for i, (a, b) in enumerate(rows):
        y = top + i * row_h
        band = QRectF(c.w * 0.07, y + row_h * 0.08, c.w * 0.86, row_h * 0.84)
        c.p.setPen(Qt.NoPen)
        c.p.setBrush(QColor(255, 255, 255, 18 if i % 2 == 0 else 8))
        c.p.drawRoundedRect(band, row_h * 0.18, row_h * 0.18)
        if left_w:
            pill = QRectF(band.left() + u, band.top() + row_h * 0.14, left_w - u * 2, band.height() - row_h * 0.28)
            if left_pill:
                c.p.setBrush(c.color)
                c.p.drawRoundedRect(pill, pill.height() / 2, pill.height() / 2)
            _text(c, pill.adjusted(u * 0.6, 0, -u * 0.6, 0), a, row_h * 0.34, True, WHITE,
                  Qt.AlignCenter)
        right = QRectF(band.left() + left_w + u * 1.5, band.top(), band.width() - left_w - u * 3, band.height())
        _text(c, right, b, row_h * 0.38, False, WHITE, Qt.AlignLeft | Qt.AlignVCenter)


def _split(line: str, sep: str = "|") -> tuple[str, str]:
    if sep in line:
        a, b = line.split(sep, 1)
        return a.strip(), b.strip()
    return "", line.strip()


def _parse_target(text: str, now: float) -> float | None:
    """„18:00“ (heute bzw. morgen) oder „24.12.2026 18:00“ / „24.12. 18:00“ → Zeitpunkt."""
    text = text.strip()
    m = re.fullmatch(r"(?:(\d{1,2})\.(\d{1,2})\.(\d{4})?\s*)?(\d{1,2})[:.](\d{2})", text)
    if not m:
        return None
    day, month, year, hour, minute = m.groups()
    lt = time.localtime(now)
    y = int(year) if year else lt.tm_year
    mo = int(month) if month else lt.tm_mon
    d = int(day) if day else lt.tm_mday
    try:
        target = time.mktime((y, mo, d, int(hour), int(minute), 0, 0, 0, -1))
    except (OverflowError, ValueError):
        return None
    if not day and target < now - 60:  # nur Uhrzeit, schon vorbei → morgen
        target += 86400
    return target


# =========================================================================== Zeichenfunktionen
def p_event_countdown(c: Ctx):
    target = _parse_target(c.text, c.now)
    _text(c, QRectF(c.w * 0.1, c.h * 0.14, c.w * 0.8, c.h * 0.14), c.title, c.unit * 5, color=MUTED)
    if target is None:
        _text(c, QRectF(c.w * 0.1, c.h * 0.35, c.w * 0.8, c.h * 0.3), "Uhrzeit angeben, z. B. 18:00", c.unit * 5)
        return
    left = max(0, int(target - c.now))
    d, rest = divmod(left, 86400)
    hh, rest = divmod(rest, 3600)
    mm, ss = divmod(rest, 60)
    parts = ([(str(d), "Tage")] if d else []) + [(f"{hh:02d}", "Std"), (f"{mm:02d}", "Min"), (f"{ss:02d}", "Sek")]
    box_w = min(c.w * 0.8 / len(parts), c.h * 0.36)
    x = (c.w - box_w * len(parts)) / 2
    for value, label in parts:
        r = QRectF(x + box_w * 0.06, c.h * 0.33, box_w * 0.88, box_w * 0.88)
        c.p.setPen(Qt.NoPen)
        c.p.setBrush(QColor(255, 255, 255, 20))
        c.p.drawRoundedRect(r, r.width() * 0.12, r.width() * 0.12)
        _text(c, r.adjusted(0, 0, 0, -r.height() * 0.25), value, r.height() * 0.5)
        _text(c, QRectF(r.left(), r.bottom() - r.height() * 0.3, r.width(), r.height() * 0.25), label,
              r.height() * 0.13, False, MUTED)
        x += box_w
    when = time.strftime("%d.%m.%Y, %H:%M Uhr", time.localtime(target))
    _text(c, QRectF(0, c.h * 0.8, c.w, c.h * 0.08), "Jetzt!" if left == 0 else when, c.unit * 2.8, False, c.color)


def p_geburtstag(c: Ctx):
    _confetti(c, 60)
    _text(c, QRectF(c.w * 0.08, c.h * 0.24, c.w * 0.84, c.h * 0.32), c.title, c.unit * 9)
    _text(c, QRectF(c.w * 0.12, c.h * 0.6, c.w * 0.76, c.h * 0.16), c.text, c.unit * 3.6, False, MUTED)
    # Torte
    u = c.unit
    cx, base = c.w / 2, c.h * 0.2
    c.p.setPen(Qt.NoPen)
    c.p.setBrush(c.color)
    c.p.drawRoundedRect(QRectF(cx - u * 5, base - u * 2.5, u * 10, u * 3), u, u)
    for i in range(3):
        x = cx - u * 3 + i * u * 3
        c.p.setBrush(QColor("#f8fafc"))
        c.p.drawRect(QRectF(x - u * 0.3, base - u * 5, u * 0.6, u * 2.5))
        flame = 0.3 * math.sin((c.now - c.started) * 8 + i)
        c.p.setBrush(QColor("#fbbf24"))
        c.p.drawEllipse(QPointF(x, base - u * 5.6), u * (0.5 + flame * 0.2), u * (0.8 + flame * 0.2))


def p_tabelle(c: Ctx):
    top = _heading(c)
    _rows(c, top, [_split(line) for line in c.lines()])


def p_hausaufgaben(c: Ctx):
    top = _heading(c)
    rows = [_split(line) for line in c.lines()]
    _rows(c, top, [(b, a) if a else ("", b) for a, b in rows])  # „bis wann“ als Marke links


def p_termine(c: Ctx):
    top = _heading(c)
    _rows(c, top, [_split(line) for line in c.lines()])


def p_speiseplan(c: Ctx):
    top = _heading(c)
    _rows(c, top, [_split(line) for line in c.lines()])


def p_abstimmung(c: Ctx):
    _text(c, QRectF(c.w * 0.07, c.h * 0.06, c.w * 0.86, c.h * 0.22), c.title, c.unit * 5)
    answers = c.lines()[:6]
    if not answers:
        return
    solved = int(c.cfg.get("current", 0) or 0)
    cols = 2 if len(answers) > 2 else 1
    rows = math.ceil(len(answers) / cols)
    gap = c.unit * 1.5
    area = QRectF(c.w * 0.07, c.h * 0.32, c.w * 0.86, c.h * 0.6)
    cw = (area.width() - gap * (cols - 1)) / cols
    ch = (area.height() - gap * (rows - 1)) / rows
    palette = ["#ef4444", "#3b82f6", "#eab308", "#22c55e", "#a855f7", "#f97316"]
    for i, ans in enumerate(answers):
        r = QRectF(area.left() + (i % cols) * (cw + gap), area.top() + (i // cols) * (ch + gap), cw, ch)
        col = QColor(palette[i])
        if solved and i + 1 != solved:
            col.setAlpha(70)
        c.p.setPen(QPen(QColor("#ffffff"), c.unit * 0.5) if solved == i + 1 else Qt.NoPen)
        c.p.setBrush(col)
        c.p.drawRoundedRect(r, c.unit * 1.5, c.unit * 1.5)
        letter = QRectF(r.left() + c.unit, r.top(), ch * 0.8, r.height())
        _text(c, letter, "ABCDEF"[i], ch * 0.42)
        _text(c, QRectF(letter.right(), r.top(), r.width() - letter.width() - c.unit * 2, r.height()),
              ans + ("  ✓" if solved == i + 1 else ""), ch * 0.3, True, WHITE, Qt.AlignLeft | Qt.AlignVCenter)


def p_aufgabe(c: Ctx):
    top = _heading(c)
    steps = c.lines()
    minutes = c.cfg.get("minutes")
    if minutes:
        badge = QRectF(c.w * 0.73, c.h * 0.075, c.w * 0.2, c.h * 0.09)
        c.p.setPen(Qt.NoPen)
        c.p.setBrush(c.color)
        c.p.drawRoundedRect(badge, badge.height() / 2, badge.height() / 2)
        _text(c, badge, f"⏱ {int(minutes)} min", badge.height() * 0.45)
    if not steps:
        return
    row_h = min(c.h * 0.15, (c.h * 0.9 - top) / len(steps))
    for i, step in enumerate(steps, start=1):
        y = top + (i - 1) * row_h
        circle = QRectF(c.w * 0.08, y + row_h * 0.18, row_h * 0.64, row_h * 0.64)
        c.p.setPen(QPen(c.color, c.unit * 0.35))
        c.p.setBrush(QColor(255, 255, 255, 10))
        c.p.drawEllipse(circle)
        _text(c, circle, str(i), row_h * 0.3)
        _text(c, QRectF(circle.right() + c.unit * 2, y, c.w * 0.8, row_h), step, row_h * 0.36, False, WHITE,
              Qt.AlignLeft | Qt.AlignVCenter | Qt.TextWordWrap)


def p_regeln(c: Ctx):
    top = _heading(c)
    items = c.lines()
    if not items:
        return
    row_h = min(c.h * 0.14, (c.h * 0.9 - top) / len(items))
    for i, item in enumerate(items):
        y = top + i * row_h
        tick = QRectF(c.w * 0.08, y + row_h * 0.2, row_h * 0.6, row_h * 0.6)
        c.p.setPen(Qt.NoPen)
        c.p.setBrush(c.color)
        c.p.drawRoundedRect(tick, tick.width() * 0.25, tick.width() * 0.25)
        c.p.setPen(QPen(QColor("#ffffff"), row_h * 0.07, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        path = QPainterPath(QPointF(tick.left() + tick.width() * 0.25, tick.center().y()))
        path.lineTo(tick.left() + tick.width() * 0.43, tick.bottom() - tick.height() * 0.27)
        path.lineTo(tick.right() - tick.width() * 0.22, tick.top() + tick.height() * 0.28)
        c.p.setBrush(Qt.NoBrush)
        c.p.drawPath(path)
        _text(c, QRectF(tick.right() + c.unit * 2, y, c.w * 0.8, row_h), item, row_h * 0.38, False, WHITE,
              Qt.AlignLeft | Qt.AlignVCenter | Qt.TextWordWrap)


def p_gruppen(c: Ctx):
    top = _heading(c)
    groups = [_split(line, ":") for line in c.lines()]
    if not groups:
        return
    cols = 2 if len(groups) > 3 else len(groups)
    cols = max(1, min(cols, 3))
    rows = math.ceil(len(groups) / cols)
    gap = c.unit * 1.5
    area = QRectF(c.w * 0.07, top, c.w * 0.86, c.h * 0.92 - top)
    cw = (area.width() - gap * (cols - 1)) / cols
    ch = (area.height() - gap * (rows - 1)) / rows
    for i, (name, members) in enumerate(groups):
        r = QRectF(area.left() + (i % cols) * (cw + gap), area.top() + (i // cols) * (ch + gap), cw, ch)
        c.p.setPen(QPen(c.color, c.unit * 0.3))
        c.p.setBrush(QColor(255, 255, 255, 14))
        c.p.drawRoundedRect(r, c.unit * 1.5, c.unit * 1.5)
        _text(c, QRectF(r.left() + c.unit * 1.5, r.top() + c.unit, r.width() - c.unit * 3, r.height() * 0.35),
              name or f"Gruppe {i + 1}", min(ch * 0.2, c.unit * 3.5), True, c.color.lighter(140),
              Qt.AlignLeft | Qt.AlignVCenter)
        _text(c, QRectF(r.left() + c.unit * 1.5, r.top() + r.height() * 0.38, r.width() - c.unit * 3,
                        r.height() * 0.56), members, min(ch * 0.17, c.unit * 3), False, WHITE,
              Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap)


def p_ruhe(c: Ctx):
    t = c.now - (c.started or c.now)
    center = QPointF(c.w / 2, c.h * 0.42)
    for i in range(4):  # langsam atmende Kreise
        phase = (t * 0.25 + i / 4) % 1.0
        r = min(c.w, c.h) * (0.08 + 0.32 * phase)
        col = QColor(c.color)
        col.setAlphaF(0.35 * (1 - phase))
        c.p.setPen(QPen(col, c.unit * 0.4))
        c.p.setBrush(Qt.NoBrush)
        c.p.drawEllipse(center, r, r)
    c.p.setPen(Qt.NoPen)
    c.p.setBrush(c.color)
    breathe = 1 + 0.08 * math.sin(t * 1.3)
    c.p.drawEllipse(center, min(c.w, c.h) * 0.07 * breathe, min(c.w, c.h) * 0.07 * breathe)
    _text(c, QRectF(c.w * 0.1, c.h * 0.66, c.w * 0.8, c.h * 0.13), c.title, c.unit * 6)
    _text(c, QRectF(c.w * 0.1, c.h * 0.8, c.w * 0.8, c.h * 0.1), c.text, c.unit * 3, False, MUTED)


def p_danke(c: Ctx):
    glow = QRadialGradient(QPointF(c.w / 2, c.h * 0.42), min(c.w, c.h) * 0.5)
    col = QColor(c.color)
    col.setAlpha(90)
    glow.setColorAt(0, col)
    glow.setColorAt(1, QColor(0, 0, 0, 0))
    c.p.fillRect(0, 0, c.w, c.h, glow)
    _text(c, QRectF(c.w * 0.1, c.h * 0.22, c.w * 0.8, c.h * 0.36), c.title, c.unit * 14)
    _text(c, QRectF(c.w * 0.1, c.h * 0.62, c.w * 0.8, c.h * 0.14), c.text, c.unit * 4, False, MUTED)


def p_schlagzeile(c: Ctx):
    u = c.unit
    tag = QRectF(c.w * 0.07, c.h * 0.16, u * 18, u * 4.5)
    c.p.setPen(Qt.NoPen)
    c.p.setBrush(c.color)
    c.p.drawRect(tag)
    _text(c, tag, "AKTUELL", tag.height() * 0.5)
    _text(c, QRectF(c.w * 0.07, c.h * 0.28, c.w * 0.86, c.h * 0.34), c.title, u * 8, True, WHITE,
          Qt.AlignLeft | Qt.AlignVCenter | Qt.TextWordWrap)
    c.p.setPen(QPen(QColor(255, 255, 255, 60), u * 0.2))
    c.p.drawLine(QPointF(c.w * 0.07, c.h * 0.65), QPointF(c.w * 0.93, c.h * 0.65))
    _text(c, QRectF(c.w * 0.07, c.h * 0.68, c.w * 0.86, c.h * 0.16), c.text, u * 3.6, False, MUTED,
          Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap)
    _text(c, QRectF(c.w * 0.07, c.h * 0.88, c.w * 0.86, c.h * 0.06), time.strftime("%H:%M Uhr", time.localtime(c.now)),
          u * 2, True, c.color, Qt.AlignRight | Qt.AlignVCenter)


def p_kennzahl(c: Ctx):
    _text(c, QRectF(c.w * 0.05, c.h * 0.18, c.w * 0.9, c.h * 0.42), c.title, c.unit * 20, True, c.color.lighter(130))
    _text(c, QRectF(c.w * 0.1, c.h * 0.62, c.w * 0.8, c.h * 0.16), c.text, c.unit * 4, False, WHITE)


def p_tuerschild(c: Ctx):
    u = c.unit
    card = QRectF(c.w * 0.08, c.h * 0.12, c.w * 0.84, c.h * 0.76)
    c.p.setPen(Qt.NoPen)
    c.p.setBrush(QColor("#f8fafc"))
    c.p.drawRoundedRect(card, u * 2, u * 2)
    c.p.setBrush(c.color)
    c.p.drawRoundedRect(QRectF(card.left(), card.top(), u * 2, card.height()), u, u)
    _text(c, QRectF(card.left() + u * 5, card.top() + u * 3, card.width() - u * 8, card.height() * 0.42), c.title,
          u * 12, True, QColor("#0f172a"), Qt.AlignLeft | Qt.AlignVCenter)
    _text(c, QRectF(card.left() + u * 5, card.top() + card.height() * 0.5, card.width() - u * 8,
                    card.height() * 0.42), c.text, u * 4.5, False, QColor("#334155"),
          Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap)


def p_sieger(c: Ctx):
    _confetti(c, 80)
    _heading(c)
    names = (c.lines() + ["", "", ""])[:3]
    u = c.unit
    base = c.h * 0.9
    width = c.w * 0.22
    order = [(0, 0.39, 0.42, "#eab308"), (1, 0.15, 0.3, "#94a3b8"), (2, 0.63, 0.22, "#b45309")]  # Mitte = Platz 1
    for idx, x, height, col in order:
        r = QRectF(c.w * x, base - c.h * height, width, c.h * height)
        c.p.setPen(Qt.NoPen)
        c.p.setBrush(QColor(col))
        c.p.drawRoundedRect(r, u, u)
        _text(c, QRectF(r.left(), r.top() + u, r.width(), r.height() * 0.5), str(idx + 1),
              min(r.height() * 0.45, u * 12))
        _text(c, QRectF(r.left() - u * 2, r.top() - c.h * 0.13, r.width() + u * 4, c.h * 0.12), names[idx],
              u * 3.2, True, WHITE)


def p_stimmung(c: Ctx):
    _text(c, QRectF(c.w * 0.07, c.h * 0.08, c.w * 0.86, c.h * 0.18), c.title, c.unit * 5.5)
    colors = ["#ef4444", "#f97316", "#eab308", "#84cc16", "#22c55e"]
    size = min(c.w * 0.14, c.h * 0.3)
    gap = (c.w * 0.86 - size * 5) / 4
    for i, col in enumerate(colors):
        center = QPointF(c.w * 0.07 + size / 2 + i * (size + gap), c.h * 0.52)
        c.p.setPen(Qt.NoPen)
        c.p.setBrush(QColor(col))
        c.p.drawEllipse(center, size / 2, size / 2)
        c.p.setBrush(QColor("#111827"))
        for dx in (-0.16, 0.16):
            c.p.drawEllipse(QPointF(center.x() + dx * size, center.y() - size * 0.1), size * 0.05, size * 0.06)
        curve = (i - 2) / 2  # -1 traurig … +1 fröhlich
        path = QPainterPath(QPointF(center.x() - size * 0.2, center.y() + size * 0.16))
        path.quadTo(QPointF(center.x(), center.y() + size * (0.16 + 0.18 * curve)),
                    QPointF(center.x() + size * 0.2, center.y() + size * 0.16))
        c.p.setPen(QPen(QColor("#111827"), size * 0.045, Qt.SolidLine, Qt.RoundCap))
        c.p.setBrush(Qt.NoBrush)
        c.p.drawPath(path)
        _text(c, QRectF(center.x() - size / 2, center.y() + size * 0.55, size, size * 0.3), str(i + 1), size * 0.2)
    _text(c, QRectF(c.w * 0.1, c.h * 0.86, c.w * 0.8, c.h * 0.08), c.text, c.unit * 2.6, False, MUTED)


def p_zweispaltig(c: Ctx):
    top = _heading(c)
    left_head, right_head = "Pro", "Contra"
    pairs = [_split(line) for line in c.lines()]
    if pairs and pairs[0][0].endswith(":") and pairs[0][1].endswith(":"):
        left_head, right_head = pairs[0][0][:-1], pairs[0][1][:-1]
        pairs = pairs[1:]
    gap = c.unit * 2
    col_w = (c.w * 0.86 - gap) / 2
    for side, (head, col) in enumerate(((left_head, "#22c55e"), (right_head, "#ef4444"))):
        x = c.w * 0.07 + side * (col_w + gap)
        box = QRectF(x, top, col_w, c.h * 0.9 - top)
        c.p.setPen(QPen(QColor(col), c.unit * 0.3))
        c.p.setBrush(QColor(255, 255, 255, 12))
        c.p.drawRoundedRect(box, c.unit * 1.5, c.unit * 1.5)
        _text(c, QRectF(x, top + c.unit, col_w, c.h * 0.09), head, c.unit * 3.6, True, QColor(col))
        items = [b if side else a for a, b in pairs]
        items = [i for i in items if i]
        if items:
            row_h = min(c.h * 0.11, (box.height() - c.h * 0.12) / len(items))
            for j, item in enumerate(items):
                _text(c, QRectF(x + c.unit * 2, top + c.h * 0.11 + j * row_h, col_w - c.unit * 4, row_h),
                      "•  " + item, row_h * 0.4, False, WHITE, Qt.AlignLeft | Qt.AlignVCenter | Qt.TextWordWrap)


def p_begriff(c: Ctx):
    _text(c, QRectF(c.w * 0.08, c.h * 0.2, c.w * 0.84, c.h * 0.28), c.title, c.unit * 11, True, c.color.lighter(135))
    c.p.setPen(Qt.NoPen)
    c.p.setBrush(c.color)
    c.p.drawRoundedRect(QRectF(c.w / 2 - c.unit * 6, c.h * 0.51, c.unit * 12, c.unit * 0.6), c.unit * 0.3,
                        c.unit * 0.3)
    _text(c, QRectF(c.w * 0.12, c.h * 0.56, c.w * 0.76, c.h * 0.3), c.text, c.unit * 4.2, False, WHITE)


def p_willkommen_gast(c: Ctx):
    _text(c, QRectF(c.w * 0.08, c.h * 0.1, c.w * 0.84, c.h * 0.2), c.title, c.unit * 7)
    names = c.lines()
    if not names:
        return
    row_h = min(c.h * 0.12, c.h * 0.56 / len(names))
    for i, name in enumerate(names):
        _text(c, QRectF(c.w * 0.1, c.h * 0.36 + i * row_h, c.w * 0.8, row_h), name, row_h * 0.55, i == 0,
              WHITE if i == 0 else MUTED)


PAINTERS = {
    "event_countdown": p_event_countdown, "geburtstag": p_geburtstag, "tabelle": p_tabelle,
    "abstimmung": p_abstimmung, "aufgabe": p_aufgabe, "regeln": p_regeln, "gruppen": p_gruppen, "ruhe": p_ruhe,
    "danke": p_danke, "hausaufgaben": p_hausaufgaben, "schlagzeile": p_schlagzeile, "kennzahl": p_kennzahl,
    "termine": p_termine, "tuerschild": p_tuerschild, "speiseplan": p_speiseplan, "sieger": p_sieger,
    "stimmung": p_stimmung, "zweispaltig": p_zweispaltig, "begriff": p_begriff, "willkommen_gast": p_willkommen_gast,
}
