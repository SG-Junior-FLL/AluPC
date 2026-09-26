"""Weitere Bildschirmschoner: Polarlicht, Lavalampe, Lichtkugeln, Meereswellen, Feuerwerk, Analoguhr,
Klappuhr, Schneefall und wechselnde Sprüche.

Gleiche Schnittstelle wie in screensaver_code: `tick(dt, w, h)` rechnet weiter, `paint(p, w, h)` zeichnet.
Alles wird mit einfachen Formen und Verläufen gezeichnet – ohne Bilder, flüssig auch auf großen Monitoren.
"""

from __future__ import annotations

import math
import random
import time

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient

FPS = {"aurora": 30, "lava": 30, "bokeh": 30, "wellen": 30, "feuerwerk": 40, "analog": 10, "flipuhr": 10,
       "schnee": 30, "sprueche": 20}
WEEKDAYS = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
MONTHS = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober",
          "November", "Dezember"]


def _font(px: float, bold: bool = False) -> QFont:
    f = QFont()
    f.setPixelSize(max(8, int(px)))
    f.setBold(bold)
    return f


def _date_text() -> str:
    now = time.localtime()
    return f"{WEEKDAYS[now.tm_wday]}, {now.tm_mday}. {MONTHS[now.tm_mon - 1]}"


def _accent(cfg: dict, default: str) -> QColor:
    c = QColor(cfg.get("color") or "")
    # „#e8ecf3“ ist die Standard-Textfarbe – dann lieber die typische Farbe des Stils
    return c if c.isValid() and c.name() != "#e8ecf3" else QColor(default)


# =========================================================================== Polarlicht
class Aurora:
    def __init__(self, rng: random.Random, cfg: dict):
        self.t = rng.uniform(0, 100)
        self.stars = [(rng.random(), rng.random() * 0.7, rng.uniform(0.3, 1.0)) for _ in range(160)]

    def tick(self, dt, w, h):
        self.t += dt

    def paint(self, p: QPainter, w: int, h: int):
        sky = QLinearGradient(0, 0, 0, h)
        sky.setColorAt(0, QColor("#020617"))
        sky.setColorAt(1, QColor("#0b1a2e"))
        p.fillRect(0, 0, w, h, sky)
        p.setPen(Qt.NoPen)
        for x, y, b in self.stars:
            c = QColor(255, 255, 255, int(120 * b * (0.7 + 0.3 * math.sin(self.t * 2 + x * 40))))
            p.setBrush(c)
            p.drawEllipse(QPointF(x * w, y * h), 1.2, 1.2)
        p.setCompositionMode(QPainter.CompositionMode_Plus)
        for band, (col, off, amp) in enumerate(((QColor(34, 197, 94), 0.0, 0.10), (QColor(20, 184, 166), 1.7, 0.08),
                                                 (QColor(168, 85, 247), 3.1, 0.06))):
            path = QPainterPath()
            steps = 60
            base = h * (0.35 + band * 0.07)
            top = []
            for i in range(steps + 1):
                x = w * i / steps
                y = base + h * amp * math.sin(i * 0.23 + self.t * 0.35 + off) \
                    + h * 0.03 * math.sin(i * 0.61 - self.t * 0.8 + off)
                top.append(QPointF(x, y))
            path.moveTo(top[0])
            for pt in top[1:]:
                path.lineTo(pt)
            path.lineTo(w, base + h * 0.35)
            path.lineTo(0, base + h * 0.35)
            path.closeSubpath()
            g = QLinearGradient(0, base - h * amp, 0, base + h * 0.35)
            c1, c2 = QColor(col), QColor(col)
            c1.setAlpha(0)
            c2.setAlpha(0)
            mid = QColor(col)
            mid.setAlpha(int(90 + 40 * math.sin(self.t * 0.5 + off)))
            g.setColorAt(0, c1)
            g.setColorAt(0.25, mid)
            g.setColorAt(1, c2)
            p.fillPath(path, g)
        p.setCompositionMode(QPainter.CompositionMode_SourceOver)


# =========================================================================== Lavalampe
class Lava:
    def __init__(self, rng: random.Random, cfg: dict):
        base = _accent(cfg, "#f97316")
        self.blobs = []
        for i in range(9):
            col = QColor.fromHsvF((base.hsvHueF() + rng.uniform(-0.08, 0.08)) % 1.0, 0.85, 1.0)
            self.blobs.append([rng.random(), rng.random(), rng.uniform(0.12, 0.24), rng.uniform(0.02, 0.06),
                               rng.uniform(0, 6.28), col])
        self.t = 0.0

    def tick(self, dt, w, h):
        self.t += dt
        for b in self.blobs:
            b[1] -= b[3] * dt * math.sin(self.t * 0.3 + b[4])
            b[0] += 0.01 * dt * math.cos(self.t * 0.2 + b[4])
            b[1] = min(1.1, max(-0.1, b[1]))

    def paint(self, p: QPainter, w: int, h: int):
        bg = QLinearGradient(0, 0, 0, h)
        bg.setColorAt(0, QColor("#12051f"))
        bg.setColorAt(1, QColor("#2a0a12"))
        p.fillRect(0, 0, w, h, bg)
        p.setPen(Qt.NoPen)
        p.setCompositionMode(QPainter.CompositionMode_Plus)
        for x, y, r, _s, _o, col in self.blobs:
            radius = r * min(w, h) * (1 + 0.08 * math.sin(self.t + x * 10))
            g = QRadialGradient(QPointF(x * w, y * h), radius)
            c0, c1 = QColor(col), QColor(col)
            c0.setAlpha(170)
            c1.setAlpha(0)
            g.setColorAt(0, c0)
            g.setColorAt(0.55, QColor(col.red(), col.green(), col.blue(), 90))
            g.setColorAt(1, c1)
            p.setBrush(g)
            p.drawEllipse(QPointF(x * w, y * h), radius, radius)
        p.setCompositionMode(QPainter.CompositionMode_SourceOver)


# =========================================================================== Lichtkugeln (Bokeh)
class Bokeh:
    def __init__(self, rng: random.Random, cfg: dict):
        self.rng = rng
        self.base = _accent(cfg, "#60a5fa")
        self.dots = [self._new(fresh=True) for _ in range(46)]

    def _new(self, fresh=False):
        hue = (self.base.hsvHueF() + self.rng.uniform(-0.12, 0.12)) % 1.0
        return [self.rng.random(), self.rng.random() if fresh else 1.1, self.rng.uniform(0.02, 0.09),
                self.rng.uniform(0.01, 0.04), QColor.fromHsvF(hue, 0.55, 1.0), self.rng.uniform(0, 6.28)]

    def tick(self, dt, w, h):
        for i, d in enumerate(self.dots):
            d[1] -= d[3] * dt
            d[5] += dt
            if d[1] < -0.15:
                self.dots[i] = self._new()

    def paint(self, p: QPainter, w: int, h: int):
        bg = QRadialGradient(QPointF(w / 2, h), max(w, h))
        bg.setColorAt(0, QColor("#111a33"))
        bg.setColorAt(1, QColor("#03050d"))
        p.fillRect(0, 0, w, h, bg)
        p.setPen(Qt.NoPen)
        for x, y, r, _s, col, ph in self.dots:
            radius = r * min(w, h)
            cx = x * w + math.sin(ph * 0.5) * w * 0.01
            g = QRadialGradient(QPointF(cx, y * h), radius)
            a = int(110 + 50 * math.sin(ph))
            g.setColorAt(0, QColor(col.red(), col.green(), col.blue(), a))
            g.setColorAt(0.8, QColor(col.red(), col.green(), col.blue(), a // 2))
            g.setColorAt(1, QColor(col.red(), col.green(), col.blue(), 0))
            p.setBrush(g)
            p.drawEllipse(QPointF(cx, y * h), radius, radius)


# =========================================================================== Meereswellen
class Waves:
    def __init__(self, rng: random.Random, cfg: dict):
        self.t = rng.uniform(0, 10)
        self.base = _accent(cfg, "#0ea5e9")

    def tick(self, dt, w, h):
        self.t += dt

    def paint(self, p: QPainter, w: int, h: int):
        sky = QLinearGradient(0, 0, 0, h)
        sky.setColorAt(0, QColor("#fde68a"))
        sky.setColorAt(0.35, QColor("#fb923c"))
        sky.setColorAt(0.6, QColor("#1e3a5f"))
        sky.setColorAt(1, QColor("#0b1a2e"))
        p.fillRect(0, 0, w, h, sky)
        p.setPen(Qt.NoPen)
        sun = QRadialGradient(QPointF(w * 0.5, h * 0.42), h * 0.18)
        sun.setColorAt(0, QColor(255, 247, 200, 255))
        sun.setColorAt(1, QColor(255, 200, 120, 0))
        p.setBrush(sun)
        p.drawEllipse(QPointF(w * 0.5, h * 0.42), h * 0.18, h * 0.18)
        for layer in range(5):
            depth = layer / 4
            y0 = h * (0.48 + depth * 0.1)
            amp = h * (0.012 + depth * 0.02)
            path = QPainterPath(QPointF(0, h))
            steps = 80
            for i in range(steps + 1):
                x = w * i / steps
                y = y0 + amp * math.sin(i * 0.18 * (1.3 - depth) + self.t * (0.6 + depth)) \
                    + amp * 0.5 * math.sin(i * 0.41 - self.t * 1.1)
                path.lineTo(x, y)
            path.lineTo(w, h)
            path.closeSubpath()
            c = QColor(self.base).darker(int(120 + depth * 160))  # vorne dunkler, hinten heller
            c.setAlpha(int(200 + depth * 55))
            p.fillPath(path, c)


# =========================================================================== Feuerwerk
class Fireworks:
    def __init__(self, rng: random.Random, cfg: dict):
        self.rng = rng
        self.rockets: list[list] = []
        self.sparks: list[list] = []
        self.next = 0.2
        self._burst(0.5, 0.35, QColor.fromHsvF(rng.random(), 0.8, 1.0))  # nicht mit leerem Bild beginnen

    def _burst(self, x: float, y: float, color: QColor):
        for _ in range(110):
            a, v = self.rng.uniform(0, 6.283), self.rng.uniform(0.05, 0.28)
            self.sparks.append([x, y, math.cos(a) * v, math.sin(a) * v, 1.0, color])

    def tick(self, dt, w, h):
        self.next -= dt
        if self.next <= 0:
            self.next = self.rng.uniform(0.4, 1.2)
            self.rockets.append([self.rng.uniform(0.15, 0.85), 1.0, self.rng.uniform(0.25, 0.5),
                                 QColor.fromHsvF(self.rng.random(), 0.8, 1.0)])
        for r in list(self.rockets):
            r[1] -= dt * 0.7
            if r[1] <= r[2]:
                self.rockets.remove(r)
                self._burst(r[0], r[1], r[3])
        for s in self.sparks:
            s[0] += s[2] * dt
            s[1] += s[3] * dt
            s[3] += 0.12 * dt  # Schwerkraft
            s[4] -= dt * 0.6
        self.sparks = [s for s in self.sparks if s[4] > 0]

    def paint(self, p: QPainter, w: int, h: int):
        p.fillRect(0, 0, w, h, QColor("#03040a"))
        scale = min(w, h)
        p.setCompositionMode(QPainter.CompositionMode_Plus)
        for x, y, _t, col in self.rockets:
            p.setPen(QPen(QColor(255, 220, 160, 200), max(2.0, scale / 300)))
            p.drawLine(QPointF(x * w, y * h), QPointF(x * w, (y + 0.03) * h))
        for x, y, vx, vy, life, col in self.sparks:
            c = QColor(col)
            c.setAlphaF(max(0.0, min(1.0, life)))
            p.setPen(QPen(c, max(1.5, scale / 400), Qt.SolidLine, Qt.RoundCap))
            p.drawLine(QPointF(x * w, y * h), QPointF((x - vx * 0.08) * w, (y - vy * 0.08) * h))
        p.setCompositionMode(QPainter.CompositionMode_SourceOver)


# =========================================================================== Analoguhr
class AnalogClock:
    def __init__(self, rng: random.Random, cfg: dict):
        self.accent = _accent(cfg, "#f97316")

    def tick(self, dt, w, h):
        pass

    def paint(self, p: QPainter, w: int, h: int):
        bg = QRadialGradient(QPointF(w / 2, h / 2), max(w, h) * 0.7)
        bg.setColorAt(0, QColor("#1c2333"))
        bg.setColorAt(1, QColor("#05070c"))
        p.fillRect(0, 0, w, h, bg)
        r = min(w, h) * 0.36
        c = QPointF(w / 2, h * 0.46)
        p.setPen(QPen(QColor(255, 255, 255, 40), r * 0.02))
        p.setBrush(QColor(255, 255, 255, 12))
        p.drawEllipse(c, r, r)
        for i in range(60):
            a = i * math.pi / 30
            inner = r * (0.86 if i % 5 == 0 else 0.92)
            p.setPen(QPen(QColor(255, 255, 255, 220 if i % 5 == 0 else 90), r * (0.022 if i % 5 == 0 else 0.008),
                          Qt.SolidLine, Qt.RoundCap))
            p.drawLine(QPointF(c.x() + math.sin(a) * inner, c.y() - math.cos(a) * inner),
                       QPointF(c.x() + math.sin(a) * r * 0.97, c.y() - math.cos(a) * r * 0.97))
        now = time.time()
        lt = time.localtime(now)
        sec = lt.tm_sec + (now % 1)
        minute = lt.tm_min + sec / 60
        hour = (lt.tm_hour % 12) + minute / 60
        for angle, length, width, col in ((hour * 30, 0.5, 0.05, "#ffffff"), (minute * 6, 0.78, 0.032, "#ffffff"),
                                           (sec * 6, 0.86, 0.012, self.accent.name())):
            a = math.radians(angle)
            p.setPen(QPen(QColor(col), r * width, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(QPointF(c.x() - math.sin(a) * r * 0.1, c.y() + math.cos(a) * r * 0.1),
                       QPointF(c.x() + math.sin(a) * r * length, c.y() - math.cos(a) * r * length))
        p.setPen(Qt.NoPen)
        p.setBrush(self.accent)
        p.drawEllipse(c, r * 0.035, r * 0.035)
        p.setPen(QColor(255, 255, 255, 200))
        p.setFont(_font(h * 0.045))
        p.drawText(QRectF(0, c.y() + r + h * 0.03, w, h * 0.08), Qt.AlignCenter, _date_text())


# =========================================================================== Klappuhr
class FlipClock:
    def __init__(self, rng: random.Random, cfg: dict):
        self.color = _accent(cfg, "#f8fafc")
        self.shown = ""
        self.flip_at = 0.0

    def tick(self, dt, w, h):
        text = time.strftime("%H%M")
        if text != self.shown:
            self.shown = text
            self.flip_at = time.monotonic()

    def paint(self, p: QPainter, w: int, h: int):
        p.fillRect(0, 0, w, h, QColor("#050608"))
        digits = time.strftime("%H%M")
        card_w, card_h = min(w * 0.19, h * 0.34), min(w * 0.19, h * 0.34) * 1.35
        gap = card_w * 0.08
        total = card_w * 4 + gap * 3 + card_w * 0.3
        x = (w - total) / 2
        y = h * 0.42 - card_h / 2
        font = _font(card_h * 0.78, bold=True)
        p.setFont(font)
        flip = max(0.0, 1 - (time.monotonic() - self.flip_at) / 0.35)
        for i, d in enumerate(digits):
            if i == 2:
                x += card_w * 0.3
            rect = QRectF(x, y, card_w, card_h)
            g = QLinearGradient(rect.topLeft(), rect.bottomLeft())
            g.setColorAt(0, QColor("#2a2d34"))
            g.setColorAt(0.5, QColor("#1b1d22"))
            g.setColorAt(0.5001, QColor("#16181c"))
            g.setColorAt(1, QColor("#101114"))
            p.setPen(Qt.NoPen)
            p.setBrush(g)
            p.drawRoundedRect(rect, card_w * 0.08, card_w * 0.08)
            p.setPen(self.color)
            squash = rect.adjusted(0, card_h * 0.5 * flip * 0.3, 0, -card_h * 0.5 * flip * 0.3)
            p.drawText(squash, Qt.AlignCenter, d)
            p.setPen(QPen(QColor("#050608"), max(2.0, card_h * 0.012)))
            p.drawLine(QPointF(rect.left(), rect.center().y()), QPointF(rect.right(), rect.center().y()))
            x += card_w + gap
        p.setPen(QColor(255, 255, 255, 170))
        p.setFont(_font(h * 0.045))
        p.drawText(QRectF(0, y + card_h + h * 0.05, w, h * 0.08), Qt.AlignCenter, _date_text())


# =========================================================================== Schneefall
class Snow:
    def __init__(self, rng: random.Random, cfg: dict):
        self.rng = rng
        self.flakes = [[rng.random(), rng.random(), rng.uniform(0.3, 1.0), rng.uniform(0, 6.28)] for _ in range(260)]
        self.text = cfg.get("text", "")

    def tick(self, dt, w, h):
        for f in self.flakes:
            f[1] += dt * 0.05 * (0.4 + f[2])
            f[3] += dt
            if f[1] > 1.02:
                f[0], f[1] = self.rng.random(), -0.02

    def paint(self, p: QPainter, w: int, h: int):
        bg = QLinearGradient(0, 0, 0, h)
        bg.setColorAt(0, QColor("#0b1730"))
        bg.setColorAt(1, QColor("#1c3358"))
        p.fillRect(0, 0, w, h, bg)
        p.setPen(Qt.NoPen)
        # Schneehügel
        hill = QPainterPath(QPointF(0, h))
        for i in range(41):
            hill.lineTo(w * i / 40, h * (0.9 - 0.03 * math.sin(i * 0.35)))
        hill.lineTo(w, h)
        p.fillPath(hill, QColor("#e2e8f0"))
        for x, y, depth, ph in self.flakes:
            p.setBrush(QColor(255, 255, 255, int(120 + 135 * depth)))
            r = max(1.0, depth * min(w, h) / 260)
            p.drawEllipse(QPointF(x * w + math.sin(ph) * w * 0.01 * depth, y * h), r, r)
        if self.text:
            p.setPen(QColor(255, 255, 255, 230))
            p.setFont(_font(h * 0.08, bold=True))
            p.drawText(QRectF(0, h * 0.35, w, h * 0.2), Qt.AlignCenter, self.text)


# =========================================================================== Sprüche / Zitate
DEFAULT_SAYINGS = [
    "Gleich geht's weiter.",
    "Kleine Schritte sind auch Schritte.",
    "Fehler sind Beweise, dass du es versuchst.",
    "Erst denken, dann klicken.",
    "Heute ist ein guter Tag, um etwas Neues zu lernen.",
]


class Sayings:
    """Wechselnde Sprüche/Zitate mit Überblendung. Eigene: im Feld „Text“ mit | trennen."""

    SHOW = 12.0

    def __init__(self, rng: random.Random, cfg: dict):
        own = [s.strip() for s in (cfg.get("text") or "").split("|") if s.strip()]
        self.items = own or DEFAULT_SAYINGS
        self.index = rng.randrange(len(self.items)) if not own else 0
        self.t = 0.0
        self.color = _accent(cfg, "#f8fafc")

    def tick(self, dt, w, h):
        self.t += dt
        if self.t >= self.SHOW:
            self.t = 0.0
            self.index = (self.index + 1) % len(self.items)

    def paint(self, p: QPainter, w: int, h: int):
        hue = (self.index * 0.13) % 1.0
        bg = QLinearGradient(0, 0, w, h)
        bg.setColorAt(0, QColor.fromHsvF(hue, 0.55, 0.22))
        bg.setColorAt(1, QColor.fromHsvF((hue + 0.12) % 1.0, 0.6, 0.08))
        p.fillRect(0, 0, w, h, bg)
        fade = min(1.0, self.t / 1.0, (self.SHOW - self.t) / 1.0)
        c = QColor(self.color)
        c.setAlphaF(max(0.0, fade))
        text = self.items[self.index]
        size = h * 0.085
        rect = QRectF(w * 0.1, h * 0.2, w * 0.8, h * 0.55)
        f = _font(size, bold=True)
        while size > 14 and QFontMetricsF(f).boundingRect(rect, Qt.TextWordWrap | Qt.AlignCenter, text).height() \
                > rect.height():
            size *= 0.9
            f = _font(size, bold=True)
        p.setFont(f)
        p.setPen(c)
        p.drawText(rect, Qt.AlignCenter | Qt.TextWordWrap, f"„{text}“")
        clock = QColor(255, 255, 255, int(150 * max(0.0, fade)))
        p.setPen(clock)
        p.setFont(_font(h * 0.04))
        p.drawText(QRectF(0, h * 0.84, w, h * 0.08), Qt.AlignCenter, time.strftime("%H:%M"))


CLASSES = {"aurora": Aurora, "lava": Lava, "bokeh": Bokeh, "wellen": Waves, "feuerwerk": Fireworks,
           "analog": AnalogClock, "flipuhr": FlipClock, "schnee": Snow, "sprueche": Sayings}


def create(style: str, rng: random.Random, cfg: dict):
    cls = CLASSES.get(style)
    return cls(rng, cfg) if cls else None
