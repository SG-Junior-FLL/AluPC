"""Monitor 2: laufende Abstimmung – Frage, Balken (bewegen sich weich mit), QR-Code zum Mitmachen."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter
from PySide6.QtWidgets import QWidget

from .sources import draw_qr, fitted_font, qr_image

BAR_COLORS = ["#6366f1", "#06b6d4", "#f59e0b", "#ec4899", "#22c55e", "#f43f5e"]


class PollSource(QWidget):
    def __init__(self, cfg, parent=None):
        super().__init__(parent)
        from .cast_server import cast_server

        self.server = cast_server()
        self.ok = self.server.start()
        self.shown: list[float] = []  # angezeigte Balkenlänge 0…1 (läuft dem Ergebnis weich hinterher)
        self._qr_for, self._qr = "", None
        self._version = -1
        self.timer = QTimer(self, interval=33)
        self.timer.timeout.connect(self._tick)
        self.timer.start()
        self.setAttribute(Qt.WA_OpaquePaintEvent)

    def stop(self):
        self.timer.stop()

    def _targets(self) -> list[float]:
        poll = self.server.poll
        if poll is None:
            return []
        counts = poll.counts()
        total = sum(counts)
        return [c / total if total else 0.0 for c in counts]

    def _tick(self):
        poll = self.server.poll
        target = self._targets()
        if len(self.shown) != len(target):
            self.shown = [0.0] * len(target)
        moving = any(abs(a - b) > 0.002 for a, b in zip(self.shown, target))
        self.shown = [a + (b - a) * 0.18 for a, b in zip(self.shown, target)]
        version = poll.version if poll else -2
        if moving or version != self._version:
            self._version = version
            self.update()

    def qr(self):
        url = self.server.poll_url()
        if url != self._qr_for:
            self._qr_for, self._qr = url, qr_image(url)
        return self._qr

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        grad = QLinearGradient(0, 0, w, h)
        grad.setColorAt(0, QColor("#0b1020"))
        grad.setColorAt(1, QColor("#1e1b4b"))
        p.fillRect(self.rect(), grad)
        poll = self.server.poll
        if poll is None or not self.ok:
            p.setPen(QColor("#e2e8f0"))
            p.setFont(fitted_font(p, "Keine laufende Abstimmung", int(w * 0.8), max(14, h // 16)))
            p.drawText(self.rect(), Qt.AlignCenter,
                       "Keine laufende Abstimmung" if self.ok else "Abstimmung: Netzwerk-Anschluss belegt")
            p.end()
            return
        m = max(12, int(min(w, h) * 0.05))
        show_qr = poll.open
        qr_side = int(min(h * 0.46, w * 0.26)) if show_qr else 0
        left = QRectF(m, m, w - 2 * m - (qr_side + m * 2 if show_qr else 0), h - 2 * m)
        # Überschrift
        tag = "ABSTIMMUNG" if poll.open else "ERGEBNIS"
        f = QFont()
        f.setBold(True)
        f.setPixelSize(max(10, int(h * 0.03)))
        f.setLetterSpacing(QFont.PercentageSpacing, 115)
        p.setFont(f)
        p.setPen(QColor("#a5b4fc" if poll.open else "#86efac"))
        p.drawText(QRectF(left.x(), left.y(), left.width(), h * 0.05), Qt.AlignLeft | Qt.AlignVCenter, tag)
        qf = QFont()
        qf.setBold(True)
        qf.setPixelSize(max(14, int(h * 0.075)))
        p.setFont(qf)
        p.setPen(QColor("#ffffff"))
        q_rect = QRectF(left.x(), left.y() + h * 0.055, left.width(), h * 0.2)
        needed = p.boundingRect(q_rect, Qt.TextWordWrap, poll.question)
        while needed.height() > q_rect.height() and qf.pixelSize() > 14:
            qf.setPixelSize(int(qf.pixelSize() * 0.9))
            p.setFont(qf)
            needed = p.boundingRect(q_rect, Qt.TextWordWrap, poll.question)
        p.drawText(q_rect, Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap, poll.question)
        # Balken
        counts = poll.counts()
        total = sum(counts)
        best = max(counts) if total else -1
        n = len(poll.options)
        top = q_rect.bottom() + h * 0.03
        avail = left.bottom() - top - h * 0.06
        row = avail / n
        bar_h = min(row * 0.72, h * 0.11)
        for i, text in enumerate(poll.options):
            y = top + i * row + (row - bar_h) / 2
            track = QRectF(left.x(), y, left.width(), bar_h)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255, 255, 255, 18))
            p.drawRoundedRect(track, bar_h * 0.28, bar_h * 0.28)
            share = self.shown[i] if i < len(self.shown) else 0.0
            if share > 0.001:
                color = QColor(BAR_COLORS[i % len(BAR_COLORS)])
                if not poll.open and counts[i] != best:
                    color.setAlphaF(0.45)
                fill = QRectF(track.x(), track.y(), max(bar_h * 0.56, track.width() * share), bar_h)
                g = QLinearGradient(fill.topLeft(), fill.topRight())
                g.setColorAt(0, color.darker(115))
                g.setColorAt(1, color)
                p.setBrush(g)
                p.drawRoundedRect(fill, bar_h * 0.28, bar_h * 0.28)
            pct = f"{round(100 * counts[i] / total)} %" if total else "0 %"
            label_font = fitted_font(p, text, int(track.width() * 0.7), max(10, int(bar_h * 0.42)))
            label_font.setBold(True)
            p.setFont(label_font)
            p.setPen(QColor("#ffffff"))
            inner = track.adjusted(bar_h * 0.35, 0, -bar_h * 0.35, 0)
            p.drawText(inner, Qt.AlignLeft | Qt.AlignVCenter, text)
            p.drawText(inner, Qt.AlignRight | Qt.AlignVCenter, f"{pct}  ·  {counts[i]}")
        sf = QFont()
        sf.setPixelSize(max(10, int(h * 0.032)))
        p.setFont(sf)
        p.setPen(QColor("#94a3b8"))
        p.drawText(QRectF(left.x(), left.bottom() - h * 0.05, left.width(), h * 0.05), Qt.AlignLeft | Qt.AlignVCenter,
                   f"{total} {'Stimme' if total == 1 else 'Stimmen'}")
        # QR-Code zum Mitmachen
        if show_qr:
            qx = w - m - qr_side
            qy = (h - qr_side) / 2 - h * 0.04
            pad = qr_side * 0.06
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#ffffff"))
            p.drawRoundedRect(QRectF(qx - pad, qy - pad, qr_side + 2 * pad, qr_side + 2 * pad), pad, pad)
            draw_qr(p, QRectF(qx, qy, qr_side, qr_side), self.qr())
            cf = QFont()
            cf.setBold(True)
            cf.setPixelSize(max(10, int(h * 0.034)))
            p.setFont(cf)
            p.setPen(QColor("#e2e8f0"))
            p.drawText(QRectF(qx - m, qy + qr_side + pad * 2, qr_side + 2 * m, h * 0.05), Qt.AlignCenter,
                       "Scannen & abstimmen")
            uf = fitted_font(p, self.server.poll_url(), int(qr_side + 2 * m), max(9, int(h * 0.022)))
            p.setFont(uf)
            p.setPen(QColor("#93c5fd"))
            p.drawText(QRectF(qx - m, qy + qr_side + pad * 2 + h * 0.05, qr_side + 2 * m, h * 0.04), Qt.AlignCenter,
                       self.server.poll_url())
        p.end()
