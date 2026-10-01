"""Zufallsauswahl: Glücksrad auf Monitor 2 – mit Namen, Aufgaben, Zahlen oder was auch immer.

Das Ergebnis wird vorher fair gezogen (secrets), das Rad dreht sich dann genau dorthin – langsam auslaufend.
Auf Wunsch fliegt ein gezogener Eintrag bis zum Neustart raus (jeder Eintrag kommt einmal dran).
"""

from __future__ import annotations

import math
import secrets

from PySide6.QtCore import QElapsedTimer, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPolygonF, QRadialGradient
from PySide6.QtWidgets import QWidget

from .sources import fitted_font

COLORS = ["#6366f1", "#06b6d4", "#f59e0b", "#ec4899", "#22c55e", "#f43f5e", "#8b5cf6", "#14b8a6", "#eab308",
          "#3b82f6"]
SPIN_SECONDS = 5.0


def default_names() -> list[str]:
    try:
        from .platform.zw_fingerprint import persons

        names = persons()
    except Exception:  # noqa: BLE001
        names = []
    return names if len(names) >= 2 else ["1", "2", "3", "4", "5", "6"]


def clean_names(text_or_list) -> list[str]:
    items = text_or_list.splitlines() if isinstance(text_or_list, str) else list(text_or_list)
    out = []
    for item in items:
        name = " ".join(str(item).split())[:40]
        if name:
            out.append(name)
    return out[:40]


def _ease_out(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 4


class WheelSource(QWidget):
    finished = Signal(str)

    def __init__(self, cfg, parent=None):
        super().__init__(parent)
        self.names = clean_names(cfg.get("names") or []) or default_names()
        self.angle = 0.0  # Drehung in Grad (Segment 0 beginnt bei 0°)
        self.start_angle = self.end_angle = 0.0
        self.winner: int | None = None
        self.spinning = False
        self.clock = QElapsedTimer()
        self.timer = QTimer(self, interval=16)
        self.timer.setTimerType(Qt.PreciseTimer)
        self.timer.timeout.connect(self._tick)
        self.progress = 1.0  # 0…1 während des Drehens (Tests setzen es direkt)
        self.setAttribute(Qt.WA_OpaquePaintEvent)

    def stop(self):
        self.timer.stop()

    def set_names(self, names: list[str]) -> None:
        self.names = clean_names(names) or default_names()
        self.winner = None
        self.update()

    # ------------------------------------------------------------ Drehen
    def segment_angle(self) -> float:
        return 360.0 / max(1, len(self.names))

    def pointer_index(self, angle: float | None = None) -> int:
        """Welches Segment zeigt auf den Zeiger (rechts, 0°)?"""
        a = (-(self.angle if angle is None else angle)) % 360
        return int(a // self.segment_angle()) % len(self.names)

    def spin(self, winner: int | None = None) -> int:
        if not self.names:
            return -1
        n = len(self.names)
        self.winner = secrets.randbelow(n) if winner is None else winner % n
        seg = self.segment_angle()
        inside = seg * (0.2 + 0.6 * secrets.randbelow(1000) / 1000)  # nicht genau auf der Kante
        target = -(self.winner * seg + inside)  # Segment `winner` unter dem Zeiger
        turns = 5 + secrets.randbelow(3)
        self.start_angle = self.angle
        base = self.angle - (self.angle % 360)
        self.end_angle = base + target - 360 * turns
        while self.end_angle > self.start_angle - 360 * 4:
            self.end_angle -= 360
        self.progress = 0.0
        self.spinning = True
        self.clock.start()
        self.timer.start()
        return self.winner

    def _tick(self):
        self.progress = min(1.0, self.clock.elapsed() / 1000 / SPIN_SECONDS)
        self.angle = self.start_angle + (self.end_angle - self.start_angle) * _ease_out(self.progress)
        if self.progress >= 1.0:
            self.timer.stop()
            self.spinning = False
            self.angle = self.end_angle % 360
            if self.winner is not None:
                self.finished.emit(self.names[self.winner])
        self.update()

    # ------------------------------------------------------------ Zeichnen
    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        bg = QRadialGradient(QPointF(w * 0.4, h * 0.5), max(w, h) * 0.8)
        bg.setColorAt(0, QColor("#1e1b4b"))
        bg.setColorAt(1, QColor("#050816"))
        p.fillRect(self.rect(), bg)
        wide = w > h * 1.2
        r = min(h * 0.43, w * (0.3 if wide else 0.42))
        cx = w * 0.36 if wide else w / 2
        cy = h / 2 if wide else h * 0.42
        n = len(self.names)
        seg = self.segment_angle()
        # Schatten
        shadow = QRadialGradient(QPointF(cx, cy + r * 0.06), r * 1.12)
        shadow.setColorAt(0.85, QColor(0, 0, 0, 120))
        shadow.setColorAt(1, QColor(0, 0, 0, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(shadow)
        p.drawEllipse(QPointF(cx, cy + r * 0.06), r * 1.12, r * 1.12)
        rect = QRectF(cx - r, cy - r, 2 * r, 2 * r)
        done = not self.spinning and self.winner is not None
        for i, name in enumerate(self.names):
            color = QColor(COLORS[i % len(COLORS)])
            if n % len(COLORS) == 1 and i == n - 1:  # letzte und erste Farbe nicht gleich nebeneinander
                color = QColor(COLORS[(i + 3) % len(COLORS)])
            if done and i != self.winner:
                color = color.darker(170)
            start = self.angle + i * seg  # Qt: Winkel gegen den Uhrzeigersinn
            path = QPainterPath(QPointF(cx, cy))
            path.arcTo(rect, -start, -seg)
            path.closeSubpath()
            p.setBrush(color)
            p.setPen(QPen(QColor(255, 255, 255, 60), max(1.0, r * 0.006)))
            p.drawPath(path)
            # Name entlang der Segmentmitte
            mid = math.radians(start + seg / 2)
            p.save()
            p.translate(cx, cy)
            deg = math.degrees(mid) % 360
            text_w = r * 0.72
            f = fitted_font(p, name, int(text_w), max(10, int(min(r * 0.12, r * math.radians(seg) * 0.5))))
            f.setBold(True)
            p.setFont(f)
            p.setPen(QColor("#ffffff"))
            if 90 < deg < 270:  # linke Hälfte: Schrift umdrehen, damit sie nicht auf dem Kopf steht
                p.rotate(deg + 180)
                p.drawText(QRectF(-r * 0.94, -r * 0.1, text_w, r * 0.2), Qt.AlignLeft | Qt.AlignVCenter, name)
            else:
                p.rotate(deg)
                p.drawText(QRectF(r * 0.22, -r * 0.1, text_w, r * 0.2), Qt.AlignRight | Qt.AlignVCenter, name)
            p.restore()
        # Rand + Mitte
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor("#f8fafc"), max(3.0, r * 0.025)))
        p.drawEllipse(rect)
        hub = QRadialGradient(QPointF(cx, cy), r * 0.14)
        hub.setColorAt(0, QColor("#ffffff"))
        hub.setColorAt(1, QColor("#cbd5e1"))
        p.setPen(Qt.NoPen)
        p.setBrush(hub)
        p.drawEllipse(QPointF(cx, cy), r * 0.12, r * 0.12)
        # Zeiger rechts
        tip = QPointF(cx + r * 0.94, cy)
        pointer = QPolygonF([tip, QPointF(cx + r * 1.16, cy - r * 0.09), QPointF(cx + r * 1.16, cy + r * 0.09)])
        p.setBrush(QColor("#f8fafc"))
        p.setPen(QPen(QColor("#0f172a"), max(1.5, r * 0.01)))
        p.drawPolygon(pointer)
        # Ergebnis
        if wide:
            area = QRectF(cx + r * 1.3, h * 0.2, w - (cx + r * 1.3) - w * 0.04, h * 0.6)
        else:
            area = QRectF(w * 0.06, cy + r * 1.08, w * 0.88, h - (cy + r * 1.08) - h * 0.02)
        p.setPen(QColor("#a5b4fc"))
        tag = QFont()
        tag.setBold(True)
        tag.setPixelSize(max(10, int(h * 0.035)))
        tag.setLetterSpacing(QFont.PercentageSpacing, 115)
        p.setFont(tag)
        label = "AUSGEWÄHLT" if done else ("DREHT …" if self.spinning else "GLÜCKSRAD")
        p.drawText(QRectF(area.x(), area.y(), area.width(), area.height() * 0.2), Qt.AlignCenter, label)
        if done:
            text = self.names[self.winner]
        elif self.spinning:
            text = self.names[self.pointer_index()]
        else:
            text = ""  # vor dem Drehen nur „GLÜCKSRAD“ – keine Anzahl
        big = fitted_font(p, text, int(area.width()), max(14, int(h * (0.13 if done else 0.08))))
        big.setBold(True)
        p.setFont(big)
        p.setPen(QColor("#ffffff" if done else "#cbd5e1"))
        p.drawText(QRectF(area.x(), area.y() + area.height() * 0.2, area.width(), area.height() * 0.5),
                   Qt.AlignCenter, text)
        p.end()
