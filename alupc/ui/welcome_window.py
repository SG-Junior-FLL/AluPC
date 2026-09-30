"""„Willkommen, Lena!“ – Vollbild-Animation auf Monitor 1 nach der Anmeldung mit dem Finger.

Stile: Aurora (weiche Farbwolken, Buchstaben schweben ein), Konfetti (Explosion, Name springt auf),
Scan (Fingerabdruck wird abgetastet, Name wird getippt). Klick oder Taste schließt sofort.
"""

from __future__ import annotations

import math
import random
import time

from PySide6.QtCore import QElapsedTimer, QObject, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (QColor, QFont, QFontMetricsF, QPainter, QPainterPath, QPen, QRadialGradient,
                           QTransform)
from PySide6.QtWidgets import QWidget

from ..welcome import STYLES, display_name, last_login, person_for_slot
from . import theme

DURATION = 4.6  # Sekunden
CONFETTI = ["#f43f5e", "#f59e0b", "#22c55e", "#38bdf8", "#a855f7", "#ec4899", "#facc15"]


def greeting(hour: int | None = None) -> str:
    hour = time.localtime().tm_hour if hour is None else hour
    if 5 <= hour < 11:
        return "Guten Morgen"
    if 11 <= hour < 17:
        return "Hallo"
    if 17 <= hour < 23:
        return "Guten Abend"
    return "Noch wach?"


def _clamp(v: float) -> float:
    return 0.0 if v < 0 else 1.0 if v > 1 else v


def _ease_out(v: float) -> float:
    v = _clamp(v)
    return 1 - (1 - v) ** 3


def _ease_back(v: float) -> float:
    v = _clamp(v)
    c = 1.9
    return 1 + (c + 1) * (v - 1) ** 3 + c * (v - 1) ** 2


class WelcomeWindow(QWidget):
    TITLE = "AluPC – Willkommen"
    finished = Signal()

    def __init__(self, name: str, style: str = "aurora", text: str = "", sound: bool = False, controller=None,
                 birthday: bool = False):
        super().__init__(None, Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setWindowTitle(self.TITLE)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setCursor(Qt.BlankCursor)
        if style not in STYLES or style == "zufall":
            style = random.choice([k for k in STYLES if k != "zufall"])
        self.style, self.name = style, " ".join(name.split())[:40]
        self.birthday = birthday
        self.headline = "Alles Gute zum Geburtstag!" if birthday else (text.strip() or greeting())
        self.controller, self.sound = controller, sound
        self.t = 0.0  # Sekunden seit Start (Tests setzen das direkt)
        rng = random.Random(len(self.name) * 7919 + 17)
        # Konfetti: Startwinkel, Tempo, Drehung, Farbe, Größe
        self.parts = [(rng.uniform(-math.pi * 0.95, -math.pi * 0.05), rng.uniform(0.55, 1.35), rng.uniform(-9, 9),
                       rng.choice(CONFETTI), rng.uniform(0.6, 1.4), rng.uniform(0, 6.28)) for _ in range(170)]
        self.clock = QElapsedTimer()
        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.PreciseTimer)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self._tick)
        self._done = False

    # ------------------------------------------------------------ Anzeigen
    def play(self, screen=None) -> None:
        if screen is None and self.controller is not None:
            screen = self.controller.main_screen()
        if screen is not None:
            self.setGeometry(screen.geometry())
            self.create()
            if self.windowHandle() is not None:
                self.windowHandle().setScreen(screen)
        self.showFullScreen()
        self.raise_()
        self.activateWindow()
        from ..platform.window_tools import kde_keep_above, keep_on_top

        keep_on_top(self)
        import sys

        if sys.platform.startswith("linux"):
            from .util import run_async

            run_async(lambda: kde_keep_above(self.TITLE, True, True), None, lambda _e: None)
        if self.sound and self.controller is not None:
            sounds = self.controller.sounds
            if sounds.settings().get("enabled", True):
                sounds.play("builtin:hoch")
        self.clock.start()
        self.timer.start()

    def _tick(self) -> None:
        self.t = self.clock.elapsed() / 1000.0
        if self.t >= DURATION:
            self.finish()
            return
        self.update()

    def finish(self) -> None:
        if self._done:
            return
        self._done = True
        self.timer.stop()
        self.finished.emit()
        self.close()

    def mousePressEvent(self, _event):
        self.finish()

    def keyPressEvent(self, _event):
        self.finish()

    # ------------------------------------------------------------ Zeichnen
    def fade(self) -> float:
        return _clamp(self.t / 0.35) * _clamp((DURATION - self.t) / 0.6)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        p.setOpacity(self.fade())
        th = theme.current()
        w, h = self.width(), self.height()
        p.fillRect(self.rect(), QColor(6, 8, 16, 236))
        getattr(self, f"_paint_{self.style}")(p, th, w, h)
        p.end()

    def _blob(self, p, x, y, r, color, alpha):
        g = QRadialGradient(QPointF(x, y), r)
        c = QColor(color)
        c.setAlphaF(alpha)
        g.setColorAt(0, c)
        c.setAlphaF(0)
        g.setColorAt(1, c)
        p.setPen(Qt.NoPen)
        p.setBrush(g)
        p.drawEllipse(QPointF(x, y), r, r)

    def _name_font(self, h: float, w: float, text: str) -> QFont:
        f = QFont()
        f.setWeight(QFont.Black)
        f.setPixelSize(max(24, int(h * 0.13)))
        while f.pixelSize() > 24 and QFontMetricsF(f).horizontalAdvance(text) > w * 0.86:
            f.setPixelSize(int(f.pixelSize() * 0.9))
        return f

    def _headline(self, p, th, w, y, start, size):
        f = QFont()
        f.setWeight(QFont.DemiBold)
        f.setPixelSize(max(14, int(size)))
        f.setLetterSpacing(QFont.PercentageSpacing, 108)
        a = _ease_out((self.t - start) / 0.6)
        p.save()
        p.setOpacity(p.opacity() * a)
        p.setFont(f)
        p.setPen(QColor(255, 255, 255, 240))
        p.drawText(QRectF(0, y + 24 * (1 - a), w, size * 1.6), Qt.AlignHCenter | Qt.AlignTop, self.headline)
        p.restore()

    def _letters(self, p, th, text, font, cx, baseline, start, step, mode):
        """Name Buchstabe für Buchstabe (mit Farbverlauf). mode: "float" (einschweben) oder "pop"."""
        fm = QFontMetricsF(font)
        total = fm.horizontalAdvance(text)
        x = cx - total / 2
        rect = QRectF(x, baseline - fm.ascent(), total, fm.height())
        brush = th.gradient(rect, diagonal=False)
        for i, ch in enumerate(text):
            adv = fm.horizontalAdvance(ch)
            v = (self.t - start - i * step) / 0.55
            if v > 0 and ch.strip():
                path = QPainterPath()
                path.addText(0, 0, font, ch)
                if mode == "pop":
                    s = max(0.01, _ease_back(v))
                    dy = 0.0
                else:
                    s = 0.55 + 0.45 * _ease_back(v)
                    dy = 46 * (1 - _ease_out(v))
                tr = QTransform()
                tr.translate(x + adv / 2, baseline + dy - fm.ascent() * 0.35)
                tr.scale(s, s)
                tr.translate(-adv / 2, fm.ascent() * 0.35)
                p.save()
                p.setOpacity(p.opacity() * _clamp(v * 1.6))
                p.setPen(Qt.NoPen)
                shape = tr.map(path)
                p.setBrush(QColor(0, 0, 0, 120))  # Schatten: lesbar auch über hellen Farbwolken
                p.drawPath(shape.translated(0, max(2.0, fm.height() * 0.035)))
                p.setBrush(brush)
                p.drawPath(shape)
                p.restore()
            x += adv
        return rect

    def _check(self, p, th, cx, cy, r, start):
        """Kreis zeichnet sich, dann Haken – „erkannt“."""
        a = _ease_out((self.t - start) / 0.55)
        b = _ease_out((self.t - start - 0.4) / 0.35)
        if a <= 0:
            return
        pen = QPen(QColor(th.success), max(3.0, r * 0.12), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawArc(QRectF(cx - r, cy - r, 2 * r, 2 * r), 90 * 16, int(-360 * 16 * a))
        if b > 0:
            pts = [QPointF(cx - r * 0.42, cy + r * 0.02), QPointF(cx - r * 0.1, cy + r * 0.34),
                   QPointF(cx + r * 0.45, cy - r * 0.3)]
            path = QPainterPath(pts[0])
            first = min(1.0, b * 2)
            path.lineTo(pts[0] + (pts[1] - pts[0]) * first)
            if b > 0.5:
                path.lineTo(pts[1] + (pts[2] - pts[1]) * ((b - 0.5) * 2))
            p.drawPath(path)

    def _main_text(self, p, th, w, h, cy, start, step, mode):
        text = self.name or "Willkommen!"
        font = self._name_font(h, w, text)
        fm = QFontMetricsF(font)
        self._headline(p, th, w, cy - fm.height() * 1.05, start - 0.25, h * 0.05)
        rect = self._letters(p, th, text, font, w / 2, cy + fm.ascent() * 0.55, start, step, mode)
        # Linie wischt unter dem Namen durch
        end = start + len(text) * step + 0.35
        u = _ease_out((self.t - end) / 0.6)
        if u > 0:
            lw = rect.width() * 0.6 * u
            line = QRectF(w / 2 - lw / 2, rect.bottom() + h * 0.025, lw, max(4, h * 0.007))
            p.setPen(Qt.NoPen)
            p.setBrush(th.gradient(line, diagonal=False))
            p.drawRoundedRect(line, line.height() / 2, line.height() / 2)
        return rect

    # --- Aurora
    def _paint_aurora(self, p, th, w, h):
        t, m = self.t, min(w, h)
        for i, (color, speed, phase) in enumerate(((th.accent, 0.35, 0.0), (th.accent2, 0.27, 2.1),
                                                   ("#38bdf8", 0.21, 4.0))):
            x = w / 2 + math.cos(t * speed * 2 + phase) * w * 0.22
            y = h / 2 + math.sin(t * speed * 3 + phase) * h * 0.16
            self._blob(p, x, y, m * (0.55 + 0.05 * i), color, 0.42)
        # feine Sterne
        rng = random.Random(3)
        for _ in range(70):
            sx, sy, tw = rng.random() * w, rng.random() * h, rng.random() * 6.28
            a = 0.25 + 0.35 * (0.5 + 0.5 * math.sin(t * 2.2 + tw))
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255, 255, 255, int(255 * a)))
            p.drawEllipse(QPointF(sx, sy), 1.4, 1.4)
        self._check(p, th, w / 2, h * 0.24, m * 0.045, 0.2)
        self._main_text(p, th, w, h, h * 0.52, 0.75, 0.065, "float")

    # --- Konfetti
    def _paint_konfetti(self, p, th, w, h):
        t, m = self.t, min(w, h)
        self._blob(p, w / 2, h * 0.55, m * 0.7, th.accent, 0.35 * _ease_out(t / 0.5))
        # Konfetti fliegt aus der Mitte, fällt dann (Schwerkraft), flattert (Breite schwankt)
        ct = max(0.0, t - 0.15)
        for ang, speed, spin, color, size, flip in self.parts:
            v = speed * m * 1.25
            x = w / 2 + math.cos(ang) * v * ct * 0.75
            y = h * 0.55 + math.sin(ang) * v * ct + 0.5 * m * 1.1 * ct * ct
            if y > h + 30 or ct <= 0:
                continue
            p.save()
            p.translate(x, y)
            p.rotate(math.degrees(spin * ct))
            sw = m * 0.016 * size * abs(math.cos(ct * 7 + flip))
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(color))
            p.drawRect(QRectF(-sw / 2, -m * 0.006 * size, sw + 1, m * 0.012 * size))
            p.restore()
        self._main_text(p, th, w, h, h * 0.47, 0.3, 0.035, "pop")

    # --- Scan
    def _paint_scan(self, p, th, w, h):
        t, m = self.t, min(w, h)
        cx, cy, r = w / 2, h * 0.27, m * 0.11
        scan = _clamp((t - 0.15) / 1.0)  # 0 → 1: Linie fährt von oben nach unten
        done = t > 1.2
        # Fingerabdruck aus Bögen
        for i in range(9):
            rr = r * (0.18 + i * 0.1)
            gap = 30 + (i * 37) % 70
            top = cy - rr
            lit = done or (top < cy - r + 2 * r * scan)
            color = QColor(th.success if done else (th.accent if lit else "#334155"))
            if done:
                color.setAlphaF(0.55 + 0.45 * _clamp(1 - (t - 1.2) / 0.5))
            p.setPen(QPen(color, max(2.0, m * 0.006), Qt.SolidLine, Qt.RoundCap))
            p.setBrush(Qt.NoBrush)
            p.drawArc(QRectF(cx - rr * 0.8, cy - rr, rr * 1.6, rr * 2.1), (90 + gap // 2) * 16, (360 - gap) * 16)
        if not done:
            y = cy - r * 1.05 + 2.2 * r * scan
            grad_rect = QRectF(cx - r * 1.3, y - 2, r * 2.6, 4)
            p.setPen(Qt.NoPen)
            p.setBrush(th.gradient(grad_rect, diagonal=False))
            p.drawRoundedRect(grad_rect, 2, 2)
            self._blob(p, cx, y, r * 0.9, th.accent, 0.25)
        else:
            ring = _ease_out((t - 1.2) / 0.7)
            c = QColor(th.success)
            c.setAlphaF(0.6 * (1 - ring))
            p.setPen(QPen(c, 3))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(QPointF(cx, cy + r * 0.05), r * (1.2 + ring), r * (1.2 + ring))
        # Name wird getippt
        text = self.name or "Willkommen!"
        font = self._name_font(h, w, text + "_")
        fm = QFontMetricsF(font)
        start = 1.35
        n = max(0, min(len(text), int((t - start) / 0.075) + 1)) if t >= start else 0
        base = h * 0.7
        self._headline(p, th, w, base - fm.height() * 1.3, 1.15, h * 0.05)
        shown = text[:n]
        total = fm.horizontalAdvance(text)
        x = w / 2 - total / 2
        p.setFont(font)
        rect = QRectF(x, base - fm.ascent(), total, fm.height())
        path = QPainterPath()
        path.addText(x, base, font, shown)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 120))
        p.drawPath(path.translated(0, max(2.0, fm.height() * 0.035)))
        p.setBrush(th.gradient(rect, diagonal=False))
        p.drawPath(path)
        if t >= start - 0.2 and (n < len(text) or int(t * 2.5) % 2 == 0):  # Cursor
            cx2 = x + fm.horizontalAdvance(shown) + 6
            p.setBrush(QColor(255, 255, 255, 220))
            p.drawRect(QRectF(cx2, base - fm.ascent() * 0.8, max(3, fm.height() * 0.06), fm.ascent() * 0.9))


class WelcomeWatcher(QObject):
    """Meldet eine neue Anmeldung mit dem Finger: `greet(Anzeigename)`."""

    greet = Signal(str, str)  # Anzeigename, Person (für Geburtstage)
    FRESH = 90.0  # so alt darf ein Eintrag höchstens sein (Sekunden)

    def __init__(self, config, reader=last_login, parent=None, interval: int = 2000):
        super().__init__(parent)
        self.config = config
        self.reader = reader
        record = self._read()
        self.seen = record[1] if record else 0.0
        # gerade eben mit dem Finger angemeldet und AluPC startet automatisch → auch begrüßen
        self.startup = record if record and 0 <= time.time() - record[1] < self.FRESH else None
        self.timer = QTimer(self)
        self.timer.setInterval(interval)
        self.timer.timeout.connect(self.poll)
        self.timer.start()

    def _read(self):
        try:
            return self.reader()
        except Exception:  # noqa: BLE001
            return None

    def greet_startup(self) -> None:
        if self.startup is not None:
            record, self.startup = self.startup, None
            self._greet(record[0])

    def poll(self) -> None:
        record = self._read()
        if record is None or record[1] <= self.seen:
            return
        self.seen = record[1]
        if time.time() - record[1] < self.FRESH:
            self._greet(record[0])

    def _greet(self, slot: int) -> None:
        if not self.config["welcome"].get("on", True):
            return
        try:
            person = person_for_slot(slot)
        except Exception:  # noqa: BLE001
            person = ""
        self.greet.emit(display_name(self.config, person), person)
