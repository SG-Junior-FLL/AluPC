"""Zeichen-Bausteine für den Systemstatus: Ring-Anzeige, Verlaufskurve, Balken – und die Systemanzeige
für Monitor 2 (Quelle „system“)."""

from __future__ import annotations

import math
import time

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QConicalGradient, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from .sysinfo import fmt_bytes, fmt_rate, fmt_uptime, monitor

# Farben je Messwert (Anfang → Ende des Verlaufs)
COLORS = {
    "cpu": ("#06b6d4", "#3b82f6"),
    "ram": ("#a855f7", "#ec4899"),
    "gpu": ("#22c55e", "#10b981"),
    "temp": ("#f59e0b", "#ef4444"),
    "up": ("#f472b6", "#f472b6"),
    "down": ("#38bdf8", "#38bdf8"),
}


def level_color(value: float, warn: float = 70, hot: float = 90) -> QColor:
    return QColor("#22c55e" if value < warn else ("#f59e0b" if value < hot else "#ef4444"))


def _font(px: float, bold: bool = False) -> QFont:
    f = QFont()
    f.setPixelSize(max(1, int(px)))
    if bold:
        f.setWeight(QFont.Bold)
    return f


def paint_ring(p: QPainter, rect: QRectF, fraction: float, colors: tuple[str, str], track: QColor,
               width: float, glow: bool = True) -> None:
    """Ring-Anzeige von oben im Uhrzeigersinn, mit Farbverlauf und leichtem Leuchten."""
    fraction = max(0.0, min(1.0, fraction))
    r = rect.adjusted(width / 2, width / 2, -width / 2, -width / 2)
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(track, width, Qt.SolidLine, Qt.RoundCap))
    p.drawEllipse(r)
    if fraction <= 0.002:
        return
    g = QConicalGradient(r.center(), 90)
    # Kegel-Verlauf läuft gegen den Uhrzeigersinn: Anfang des Bogens = 1.0, Ende = 1 − Anteil
    g.setColorAt(0.0, QColor(colors[1]))
    g.setColorAt(max(0.0, 1.0 - fraction), QColor(colors[1]))
    g.setColorAt(1.0, QColor(colors[0]))
    span = -int(360 * 16 * fraction)
    if glow:
        halo = QColor(colors[1])
        halo.setAlphaF(0.18)
        p.setPen(QPen(halo, width * 2.0, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(r, 90 * 16, span)
    p.setPen(QPen(g, width, Qt.SolidLine, Qt.RoundCap))
    p.drawArc(r, 90 * 16, span)
    # leuchtender Punkt am Ende
    a = math.radians(90 - 360 * fraction)
    end = QPointF(r.center().x() + math.cos(a) * r.width() / 2, r.center().y() - math.sin(a) * r.height() / 2)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#ffffff"))
    p.drawEllipse(end, width * 0.22, width * 0.22)


def paint_sparkline(p: QPainter, rect: QRectF, values, color: str, top: float | None = None,
                    fill: bool = True, width: float = 2.0) -> None:
    vals = list(values)
    if len(vals) < 2 or rect.width() <= 0:
        return
    top = top or max(max(vals), 1e-9)
    step = rect.width() / (len(vals) - 1)
    path = QPainterPath()
    for i, v in enumerate(vals):
        pt = QPointF(rect.x() + i * step, rect.bottom() - rect.height() * max(0.0, min(1.0, v / top)))
        if i == 0:
            path.moveTo(pt)
        else:  # weich: Mittelpunkt-Kurven
            prev = path.currentPosition()
            mid = QPointF((prev.x() + pt.x()) / 2, (prev.y() + pt.y()) / 2)
            path.quadTo(prev, mid)
    path.lineTo(rect.right(), rect.bottom() - rect.height() * max(0.0, min(1.0, vals[-1] / top)))
    if fill:
        area = QPainterPath(path)
        area.lineTo(rect.bottomRight())
        area.lineTo(rect.bottomLeft())
        area.closeSubpath()
        g = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        c = QColor(color)
        c.setAlphaF(0.38)
        g.setColorAt(0, c)
        c.setAlphaF(0.0)
        g.setColorAt(1, c)
        p.fillPath(area, g)
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(QColor(color), width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.drawPath(path)


def paint_bar(p: QPainter, rect: QRectF, fraction: float, colors: tuple[str, str], track: QColor) -> None:
    rad = rect.height() / 2
    path = QPainterPath()
    path.addRoundedRect(rect, rad, rad)
    p.fillPath(path, track)
    fraction = max(0.0, min(1.0, fraction))
    if fraction <= 0:
        return
    fill = QRectF(rect.x(), rect.y(), max(rect.height(), rect.width() * fraction), rect.height())
    g = QLinearGradient(fill.topLeft(), fill.topRight())
    g.setColorAt(0, QColor(colors[0]))
    g.setColorAt(1, QColor(colors[1]))
    path = QPainterPath()
    path.addRoundedRect(fill, rad, rad)
    p.fillPath(path, g)


def gauge_values(mon, snap) -> list[tuple[str, str, float | None, str, str]]:
    """(Schlüssel, Titel, Anteil 0..1 oder None, großer Text, kleiner Text) für die vier Ringe."""
    gpu = snap.gpu
    temp = snap.cpu_temp if snap.cpu_temp is not None else (gpu.temp if gpu else None)
    freq = f" · {snap.freq / 1000:.1f} GHz".replace(".", ",") if snap.freq else ""
    out = [
        ("cpu", "Prozessor", snap.cpu / 100, f"{snap.cpu:.0f}%", f"{mon.cores} Kerne{freq}"),
        ("ram", "Arbeitsspeicher", snap.ram / 100, f"{snap.ram:.0f}%",
         f"{fmt_bytes(snap.ram_used)} von {fmt_bytes(snap.ram_total)}"),
    ]
    if gpu and gpu.load is not None:
        sub = gpu.name
        if gpu.mem_total:
            sub = f"{fmt_bytes(gpu.mem_used * 2**20)} von {fmt_bytes(gpu.mem_total * 2**20)}"
        out.append(("gpu", "Grafikkarte", gpu.load / 100, f"{gpu.load:.0f}%", sub))
    else:
        out.append(("gpu", "Grafikkarte", None, "–", "keine Daten"))
    if temp is not None:
        where = "Prozessor" if snap.cpu_temp is not None else "Grafikkarte"
        out.append(("temp", "Temperatur", temp / 100, f"{temp:.0f}°", where))
    else:
        out.append(("temp", "Temperatur", None, "–", "keine Daten"))
    return out


class SystemSource(QWidget):
    """Monitor 2: großes Systemstatus-Dashboard (Ringe, Kurven, Laufwerke, Netzwerk)."""

    def __init__(self, cfg=None, parent=None):
        super().__init__(parent)
        self.mon = monitor()
        self.mon.updated.connect(self._on_update)
        self.mon.acquire(self)
        key = id(self)
        self.destroyed.connect(lambda *_: monitor().release(key))  # falls stop() nie kam
        self.shown = {}  # sanfte Übergänge der Ringe
        self.anim = QTimer(self, interval=33)
        self.anim.timeout.connect(self._animate)
        self.setAttribute(Qt.WA_OpaquePaintEvent)

    def stop(self):
        self.anim.stop()
        self.mon.release(self)

    def closeEvent(self, e):
        self.stop()
        super().closeEvent(e)

    def _on_update(self, _snap):
        if not self.anim.isActive():
            self.anim.start()

    def _animate(self):
        moving = False
        for key, _t, frac, _b, _s in gauge_values(self.mon, self.mon.snapshot):
            target = frac or 0.0
            cur = self.shown.get(key, 0.0)
            nxt = cur + (target - cur) * 0.18
            if abs(target - nxt) < 0.002:
                nxt = target
            else:
                moving = True
            self.shown[key] = nxt
        self.update()
        if not moving:
            self.anim.stop()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        bg = QLinearGradient(0, 0, w, h)
        bg.setColorAt(0, QColor("#070b16"))
        bg.setColorAt(1, QColor("#151034"))
        p.fillRect(self.rect(), bg)
        mon, snap = self.mon, self.mon.snapshot
        u = min(w / 16, h / 9)  # Grundmaß (16:9)
        m = u * 0.6
        # Kopfzeile
        p.setPen(QColor("#eef1f6"))
        p.setFont(_font(u * 0.55, True))
        p.drawText(QRectF(m, m * 0.6, w - 2 * m, u * 0.8), Qt.AlignLeft | Qt.AlignVCenter, mon.host)
        p.setPen(QColor("#94a3b8"))
        p.setFont(_font(u * 0.28))
        sub = f"{mon.os}  ·  {mon.cpu_name}  ·  läuft seit {fmt_uptime(snap.uptime)}" if snap.uptime else mon.os
        p.drawText(QRectF(m, m * 0.6 + u * 0.8, w - 2 * m, u * 0.45), Qt.AlignLeft | Qt.AlignVCenter, sub)
        p.setPen(QColor("#eef1f6"))
        p.setFont(_font(u * 0.62, True))
        p.drawText(QRectF(m, m * 0.6, w - 2 * m, u * 0.8), Qt.AlignRight | Qt.AlignVCenter, time.strftime("%H:%M"))
        if not mon.available:
            p.setFont(_font(u * 0.4))
            p.drawText(self.rect(), Qt.AlignCenter, "Systemstatus nicht verfügbar (psutil fehlt)")
            p.end()
            return
        # vier Ringe
        top = m + u * 1.55
        ring_h = h * 0.37
        cell = (w - 2 * m) / 4
        track = QColor(255, 255, 255, 22)
        for i, (key, title, frac, big, small) in enumerate(gauge_values(mon, snap)):
            cx = m + cell * i
            card = QRectF(cx + m * 0.25, top, cell - m * 0.5, ring_h)
            path = QPainterPath()
            path.addRoundedRect(card, u * 0.3, u * 0.3)
            p.fillPath(path, QColor(255, 255, 255, 12))
            size = min(card.width() * 0.62, card.height() * 0.62)
            rr = QRectF(card.center().x() - size / 2, card.y() + card.height() * 0.08, size, size)
            shown = self.shown.get(key, 0.0) if frac is not None else 0.0
            paint_ring(p, rr, shown, COLORS[key], track, size * 0.09)
            p.setPen(QColor("#ffffff"))
            p.setFont(_font(size * 0.24, True))
            p.drawText(rr, Qt.AlignCenter, big)
            p.setFont(_font(u * 0.32, True))
            p.setPen(QColor("#eef1f6"))
            p.drawText(QRectF(card.x(), rr.bottom() + u * 0.12, card.width(), u * 0.45), Qt.AlignCenter, title)
            p.setFont(_font(u * 0.24))
            p.setPen(QColor("#94a3b8"))
            p.drawText(QRectF(card.x() + 6, rr.bottom() + u * 0.55, card.width() - 12, u * 0.4),
                       Qt.AlignCenter, small)
        # unten: Verlauf (CPU/RAM), Netzwerk, Laufwerke
        y = top + ring_h + m * 0.6
        bh = h - y - m
        col = (w - 2 * m) / 3
        boxes = [QRectF(m + col * i + m * 0.25, y, col - m * 0.5, bh) for i in range(3)]
        for b in boxes:
            path = QPainterPath()
            path.addRoundedRect(b, u * 0.3, u * 0.3)
            p.fillPath(path, QColor(255, 255, 255, 12))
        pad = u * 0.3
        hd = u * 0.34
        # 1) Verlauf
        b = boxes[0]
        p.setFont(_font(hd * 0.85, True))
        p.setPen(QColor("#eef1f6"))
        p.drawText(QRectF(b.x() + pad, b.y() + pad * 0.6, b.width(), hd * 1.2), Qt.AlignLeft | Qt.AlignVCenter,
                   "Auslastung – 60 s")
        chart = b.adjusted(pad, pad + hd * 1.5, -pad, -pad)
        paint_sparkline(p, chart, mon.history["ram"], COLORS["ram"][1], top=100)
        paint_sparkline(p, chart, mon.history["cpu"], COLORS["cpu"][0], top=100)
        # 2) Netzwerk
        b = boxes[1]
        p.setPen(QColor("#eef1f6"))
        p.setFont(_font(hd * 0.85, True))
        p.drawText(QRectF(b.x() + pad, b.y() + pad * 0.6, b.width(), hd * 1.2), Qt.AlignLeft | Qt.AlignVCenter,
                   "Netzwerk" + (f"  ·  {mon.ip}" if mon.ip else ""))
        p.setFont(_font(hd * 0.8, True))
        p.setPen(QColor(COLORS["down"][0]))
        p.drawText(QRectF(b.x() + pad, b.y() + pad + hd * 1.3, b.width() / 2, hd * 1.2),
                   Qt.AlignLeft | Qt.AlignVCenter, f"↓ {fmt_rate(snap.net_down)}")
        p.setPen(QColor(COLORS["up"][0]))
        p.drawText(QRectF(b.center().x(), b.y() + pad + hd * 1.3, b.width() / 2 - pad, hd * 1.2),
                   Qt.AlignRight | Qt.AlignVCenter, f"↑ {fmt_rate(snap.net_up)}")
        chart = b.adjusted(pad, pad + hd * 2.9, -pad, -pad)
        peak = max(max(mon.history["down"]), max(mon.history["up"]), 64 * 1024)
        paint_sparkline(p, chart, mon.history["down"], COLORS["down"][0], top=peak)
        paint_sparkline(p, chart, mon.history["up"], COLORS["up"][0], top=peak)
        # 3) Laufwerke (+ Akku)
        b = boxes[2]
        p.setPen(QColor("#eef1f6"))
        p.setFont(_font(hd * 0.85, True))
        p.drawText(QRectF(b.x() + pad, b.y() + pad * 0.6, b.width(), hd * 1.2), Qt.AlignLeft | Qt.AlignVCenter,
                   "Laufwerke")
        rows = list(snap.disks[:4])
        yy = b.y() + pad + hd * 1.4
        row_h = min(u * 0.75, (b.bottom() - pad - yy) / max(1, len(rows) + (1 if snap.battery else 0)))
        fs = max(u * 0.2, min(u * 0.26, row_h * 0.42))
        for d in rows:
            p.setFont(_font(fs))
            p.setPen(QColor("#cbd5e1"))
            p.drawText(QRectF(b.x() + pad, yy, b.width() - 2 * pad, row_h * 0.55), Qt.AlignLeft | Qt.AlignVCenter,
                       d.mount)
            p.drawText(QRectF(b.x() + pad, yy, b.width() - 2 * pad, row_h * 0.55), Qt.AlignRight | Qt.AlignVCenter,
                       f"{fmt_bytes(d.total - d.used)} frei")
            paint_bar(p, QRectF(b.x() + pad, yy + row_h * 0.6, b.width() - 2 * pad, max(3.0, row_h * 0.14)), d.percent / 100,
                      ("#6366f1", "#a855f7") if d.percent < 90 else ("#f59e0b", "#ef4444"), QColor(255, 255, 255, 25))
            yy += row_h
        if snap.battery:
            pct, plugged, _left = snap.battery
            p.setFont(_font(fs))
            p.setPen(QColor("#cbd5e1"))
            p.drawText(QRectF(b.x() + pad, yy, b.width() - 2 * pad, row_h * 0.55), Qt.AlignLeft | Qt.AlignVCenter,
                       "Akku" + (" (lädt)" if plugged else ""))
            p.drawText(QRectF(b.x() + pad, yy, b.width() - 2 * pad, row_h * 0.55), Qt.AlignRight | Qt.AlignVCenter,
                       f"{pct:.0f} %")
            paint_bar(p, QRectF(b.x() + pad, yy + row_h * 0.6, b.width() - 2 * pad, max(3.0, row_h * 0.14)), pct / 100,
                      ("#22c55e", "#84cc16") if pct > 20 else ("#f59e0b", "#ef4444"), QColor(255, 255, 255, 25))
        p.end()
