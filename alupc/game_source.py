"""Monitor 2: Minispiele – Lobby mit QR-Code, Spielfeld, Siegertreppchen (Logik in games.py)."""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import QWidget

from .games import GAMES, RaceGame, ReactionGame, SnakeGame
from .sources import fitted_font, qr_image

MUTED = QColor("#94a3b8")
TEXT = QColor("#f1f5f9")


def _font(px: float, bold: bool = False) -> QFont:
    f = QFont()
    f.setPixelSize(max(8, int(px)))
    f.setBold(bold)
    return f


class GameSource(QWidget):
    def __init__(self, cfg, parent=None):
        super().__init__(parent)
        from .cast_server import cast_server

        self.server = cast_server()
        self.ok = self.server.start()
        self._qr_for, self._qr = "", None
        self.timer = QTimer(self, interval=33)
        self.timer.timeout.connect(self._tick)
        self.timer.start()
        self.setAttribute(Qt.WA_OpaquePaintEvent)

    def stop(self):
        self.timer.stop()

    def _tick(self):
        hub = self.server.games
        if hub is not None:
            hub.tick()
        self.update()

    def qr(self):
        url = self.server.games_url()
        if url != self._qr_for:
            self._qr_for, self._qr = url, qr_image(url)
        return self._qr

    # ------------------------------------------------------------------ Zeichnen
    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        grad = QLinearGradient(0, 0, w, h)
        grad.setColorAt(0, QColor("#0b1020"))
        grad.setColorAt(1, QColor("#1a1033"))
        p.fillRect(self.rect(), grad)
        hub = self.server.games
        if hub is None or not self.ok:
            p.setPen(TEXT)
            text = "Keine Spielrunde" if self.ok else "Minispiele: Netzwerk-Anschluss belegt"
            p.setFont(fitted_font(p, text, int(w * 0.8), max(14, h // 16)))
            p.drawText(self.rect(), Qt.AlignCenter, text)
            p.end()
            return
        with hub.lock:
            now = hub.clock()
            if hub.phase == "lobby":
                self._lobby(p, hub, w, h)
            elif hub.phase == "over":
                self._podium(p, hub, w, h)
            elif isinstance(hub.game, SnakeGame):
                self._snake(p, hub, hub.game, now, w, h)
            elif isinstance(hub.game, ReactionGame):
                self._reaction(p, hub, hub.game, now, w, h)
            elif isinstance(hub.game, RaceGame):
                self._race(p, hub, hub.game, now, w, h)
        p.end()

    def _qr_card(self, p, x, y, side, caption: bool = True):
        pad = side * 0.06
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#ffffff"))
        p.drawRoundedRect(QRectF(x - pad, y - pad, side + 2 * pad, side + 2 * pad), pad * 1.5, pad * 1.5)
        p.setRenderHint(QPainter.SmoothPixmapTransform, False)
        p.drawImage(QRectF(x, y, side, side), self.qr())
        if caption:
            url = self.server.games_url()
            room = min(side * 1.3, 2 * (self.width() - 8 - (x + side / 2)))  # nicht über den Rand
            p.setPen(QColor("#93c5fd"))
            p.setFont(fitted_font(p, url, int(room), max(9, int(side * 0.07))))
            p.drawText(QRectF(x + side / 2 - room / 2, y + side + pad * 2, room, side * 0.12), Qt.AlignCenter, url)

    def _tag(self, p, x, y, w, text, color="#a5b4fc", size=0.03):
        f = _font(self.height() * size, True)
        f.setLetterSpacing(QFont.PercentageSpacing, 115)
        p.setFont(f)
        p.setPen(QColor(color))
        p.drawText(QRectF(x, y, w, self.height() * size * 1.6), Qt.AlignLeft | Qt.AlignVCenter, text)

    def _chip(self, p, rect: QRectF, name: str, color: str, extra: str = ""):
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 16))
        p.drawRoundedRect(rect, rect.height() / 2, rect.height() / 2)
        d = rect.height() * 0.5
        p.setBrush(QColor(color))
        p.drawEllipse(QRectF(rect.x() + rect.height() * 0.25, rect.center().y() - d / 2, d, d))
        inner = rect.adjusted(rect.height() * 0.95, 0, -rect.height() * 0.35, 0)
        p.setPen(TEXT)
        p.setFont(fitted_font(p, name, int(inner.width() * (0.62 if extra else 1)), int(rect.height() * 0.45)))
        p.drawText(inner, Qt.AlignLeft | Qt.AlignVCenter, name)
        if extra:
            p.setFont(_font(rect.height() * 0.45, True))
            p.drawText(inner, Qt.AlignRight | Qt.AlignVCenter, extra)

    def _lobby(self, p, hub, w, h):
        m = max(14, int(min(w, h) * 0.05))
        qr_side = int(min(h * 0.5, w * 0.28))
        left_w = w - 3 * m - qr_side
        self._tag(p, m, m, left_w, "MINISPIELE · HANDY = CONTROLLER")
        title, help_text = GAMES[hub.game_key]
        p.setPen(QColor("#ffffff"))
        p.setFont(fitted_font(p, title, left_w, int(h * 0.1)))
        p.setFont(_font(p.font().pixelSize(), True))
        p.drawText(QRectF(m, m + h * 0.06, left_w, h * 0.13), Qt.AlignLeft | Qt.AlignVCenter, title)
        p.setPen(MUTED)
        p.setFont(_font(h * 0.034))
        p.drawText(QRectF(m, m + h * 0.2, left_w, h * 0.1), Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap, help_text)
        players = list(hub.players.values())
        top = m + h * 0.33
        p.setPen(TEXT)
        p.setFont(_font(h * 0.036, True))
        p.drawText(QRectF(m, top, left_w, h * 0.06), Qt.AlignLeft | Qt.AlignVCenter,
                   f"{len(players)} dabei" if players else "Noch niemand dabei – QR-Code scannen")
        cols = 3 if left_w > 700 else 2
        chip_h = h * 0.07
        gap = m * 0.4
        cw = (left_w - gap * (cols - 1)) / cols
        for i, pl in enumerate(players):
            r, c = divmod(i, cols)
            self._chip(p, QRectF(m + c * (cw + gap), top + h * 0.08 + r * (chip_h + gap), cw, chip_h),
                       pl.name, pl.color)
        p.setPen(MUTED)
        p.setFont(_font(h * 0.03))
        p.drawText(QRectF(m, h - m - h * 0.05, left_w, h * 0.05), Qt.AlignLeft | Qt.AlignVCenter,
                   "Starten: auf einem Handy oder am PC (Kachel „Minispiele“)")
        qx, qy = w - m - qr_side, (h - qr_side) / 2 - h * 0.04
        self._qr_card(p, qx, qy, qr_side)
        p.setPen(TEXT)
        p.setFont(_font(h * 0.034, True))
        p.drawText(QRectF(qx - m, qy - h * 0.1, qr_side + 2 * m, h * 0.06), Qt.AlignCenter, "Scannen & mitspielen")

    def _scoreboard(self, p, hub, rect: QRectF, scores: dict, fmt=str, limit: int = 12):
        rows = sorted(scores.items(), key=lambda kv: -kv[1])[:limit]
        row_h = min(rect.height() / max(1, len(rows)), self.height() * 0.07)
        for i, (pid, score) in enumerate(rows):
            pl = hub.players.get(pid)
            if pl is None:
                continue
            self._chip(p, QRectF(rect.x(), rect.y() + i * row_h, rect.width(), row_h * 0.84), pl.name, pl.color,
                       fmt(score))

    def _snake(self, p, hub, g: SnakeGame, now, w, h):
        m = max(10, int(min(w, h) * 0.03))
        side_w = w * 0.22
        area = QRectF(m, m + h * 0.06, w - 3 * m - side_w, h - 2 * m - h * 0.06)
        cell = min(area.width() / g.W, area.height() / g.H)
        bx = area.x() + (area.width() - cell * g.W) / 2
        by = area.y() + (area.height() - cell * g.H) / 2
        board = QRectF(bx, by, cell * g.W, cell * g.H)
        self._tag(p, m, m, area.width(), "SCHLANGEN-PARTY")
        left = g.remaining(now)
        p.setPen(QColor("#fbbf24") if left < 10 else TEXT)
        p.setFont(_font(h * 0.04, True))
        p.drawText(QRectF(m, m, area.width(), h * 0.05), Qt.AlignRight | Qt.AlignVCenter,
                   f"{int(left) // 60}:{int(left) % 60:02d}")
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 10))
        p.drawRoundedRect(board.adjusted(-4, -4, 4, 4), 10, 10)
        p.setBrush(QColor("#fbbf24"))
        pulse = 0.32 + 0.06 * math.sin(now * 6)
        for fx, fy in g.food:
            p.drawEllipse(QPointF(bx + (fx + 0.5) * cell, by + (fy + 0.5) * cell), cell * pulse, cell * pulse)
        for pid, s in g.snakes.items():
            pl = hub.players.get(pid)
            if not s["alive"] or pl is None:
                continue
            color = QColor(pl.color)
            for k, (x, y) in enumerate(s["body"]):
                c = color.lighter(125) if k == 0 else color
                p.setBrush(c)
                inset = cell * (0.06 if k == 0 else 0.12)
                p.drawRoundedRect(QRectF(bx + x * cell + inset, by + y * cell + inset, cell - 2 * inset,
                                         cell - 2 * inset), cell * 0.3, cell * 0.3)
            hx, hy = s["body"][0]
            label = QRectF(bx + hx * cell - cell * 3, by + hy * cell - cell * 1.05, cell * 7, cell * 0.9)
            p.setFont(fitted_font(p, pl.name, int(cell * 6), int(cell * 0.62)))
            p.setPen(QColor(0, 0, 0, 170))
            p.drawText(label.translated(1, 1), Qt.AlignCenter, pl.name)
            p.setPen(QColor("#ffffff"))
            p.drawText(label, Qt.AlignCenter, pl.name)
            p.setPen(Qt.NoPen)
        side = QRectF(w - m - side_w, m + h * 0.06, side_w, h * 0.62)
        self._scoreboard(p, hub, side, g.scores(), limit=8)
        self._join_corner(p, w, h, m, side_w)

    def _join_corner(self, p, w, h, m, side_w):
        """Kleiner QR-Code: wer zu spät kommt, kann noch einsteigen."""
        q = min(side_w * 0.5, h * 0.18)
        x, y = w - m - side_w / 2 - q / 2, h - m - q - q * 0.06 - h * 0.04
        self._qr_card(p, x, y, q, caption=False)
        p.setPen(MUTED)
        p.setFont(_font(h * 0.022))
        p.drawText(QRectF(w - m - side_w, h - m - h * 0.035, side_w, h * 0.035), Qt.AlignCenter, "Einsteigen")

    def _reaction(self, p, hub, g: ReactionGame, now, w, h):
        m = max(14, int(min(w, h) * 0.04))
        if g.phase in ("warte", "los"):
            p.fillRect(self.rect(), QColor("#16a34a" if g.phase == "los" else "#991b1b"))
        side_w = w * 0.24
        main = QRectF(m, m, w - 3 * m - side_w, h - 2 * m)
        self._tag(p, m, m, main.width(), f"SCHNELLSTER FINGER · RUNDE {g.round} / {g.ROUNDS}", "#ffffff")
        if g.phase == "ergebnis":
            p.setPen(TEXT)
            p.setFont(_font(h * 0.06, True))
            p.drawText(QRectF(main.x(), main.y() + h * 0.08, main.width(), h * 0.1), Qt.AlignLeft | Qt.AlignVCenter,
                       "Am schnellsten:" if g.last else "Keiner war schnell genug!")
            row_h = h * 0.1
            for i, (pid, t) in enumerate(g.last[:5]):
                pl = hub.players.get(pid)
                if pl is None:
                    continue
                pts = f"+{3 - i}  ·  " if i < 3 else ""
                self._chip(p, QRectF(main.x(), main.y() + h * 0.22 + i * row_h, main.width() * 0.9, row_h * 0.8),
                           pl.name, pl.color, f"{pts}{t:.3f} s".replace(".", ","))
        else:
            big = "JETZT!" if g.phase == "los" else "Warte …"
            p.setPen(QColor("#ffffff"))
            p.setFont(fitted_font(p, big, int(main.width() * 0.9), int(h * 0.26)))
            p.setFont(_font(p.font().pixelSize(), True))
            p.drawText(main, Qt.AlignCenter, big)
            p.setFont(_font(h * 0.035))
            hint = "Tippen!" if g.phase == "los" else "Erst bei GRÜN tippen – zu früh = −1"
            p.drawText(QRectF(main.x(), main.center().y() + h * 0.16, main.width(), h * 0.06), Qt.AlignCenter, hint)
        self._scoreboard(p, hub, QRectF(w - m - side_w, m + h * 0.07, side_w, h * 0.8), g.scores())

    def _race(self, p, hub, g: RaceGame, now, w, h):
        m = max(14, int(min(w, h) * 0.04))
        self._tag(p, m, m, w - 2 * m, f"TIPP-RENNEN · {g.GOAL} TIPPS BIS ZUM ZIEL")
        pids = list(g.progress)
        top = m + h * 0.08
        lane_h = min((h - top - m) / max(1, len(pids)), h * 0.14)
        name_w = w * 0.18
        track_x = m + name_w + m * 0.5
        track_w = w - track_x - m - h * 0.06
        for i, pid in enumerate(pids):
            pl = hub.players.get(pid)
            if pl is None:
                continue
            y = top + i * lane_h
            cy = y + lane_h / 2
            p.setPen(TEXT)
            p.setFont(fitted_font(p, pl.name, int(name_w), int(lane_h * 0.32)))
            p.drawText(QRectF(m, y, name_w, lane_h), Qt.AlignRight | Qt.AlignVCenter, pl.name)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255, 255, 255, 16))
            p.drawRoundedRect(QRectF(track_x, cy - lane_h * 0.14, track_w, lane_h * 0.28), lane_h * 0.14,
                              lane_h * 0.14)
            share = min(1.0, g.progress[pid] / g.GOAL)
            color = QColor(pl.color)
            p.setBrush(color.darker(140))
            p.drawRoundedRect(QRectF(track_x, cy - lane_h * 0.14, track_w * share, lane_h * 0.28), lane_h * 0.14,
                              lane_h * 0.14)
            r = lane_h * 0.3
            p.setBrush(color)
            p.drawEllipse(QPointF(track_x + track_w * share, cy), r, r)
            if pid in g.finish:
                p.setPen(QColor("#ffffff"))
                p.setFont(_font(r * 1.1, True))
                p.drawText(QRectF(track_x + track_w * share - r, cy - r, 2 * r, 2 * r), Qt.AlignCenter,
                           str(g.finish.index(pid) + 1))
        # Ziellinie (Schachbrett)
        fx = track_x + track_w + h * 0.02
        sq = h * 0.015
        for k in range(int((h - top - m) / sq)):
            for j in range(2):
                p.fillRect(QRectF(fx + j * sq, top + k * sq, sq, sq),
                           QColor("#ffffff") if (k + j) % 2 else QColor("#111827"))
        if now < g.start:
            n = str(int(g.start - now) + 1)
            p.fillRect(self.rect(), QColor(0, 0, 0, 120))
            p.setPen(QColor("#ffffff"))
            p.setFont(_font(h * 0.4, True))
            p.drawText(self.rect(), Qt.AlignCenter, n)

    def _podium(self, p, hub, w, h):
        m = max(14, int(min(w, h) * 0.05))
        self._tag(p, m, m, w - 2 * m, f"{GAMES[hub.game_key][0].upper()} · ERGEBNIS", "#86efac")
        ranking = [(pid, s) for pid, s in hub.ranking if pid in hub.players]
        race = hub.game_key == "rennen"
        slots = [(0, 0.5, 0.42), (1, 0.22, 0.3), (2, 0.78, 0.22)]  # (Platz-Index, x-Mitte, Höhe)
        base_y = h * 0.78
        col_w = w * 0.22
        medal = ["#fbbf24", "#cbd5e1", "#d97706"]
        for idx, cx, height in slots:
            if idx >= len(ranking):
                continue
            pid, score = ranking[idx]
            pl = hub.players[pid]
            rect = QRectF(w * cx - col_w / 2, base_y - h * height, col_w, h * height)
            g = QLinearGradient(rect.topLeft(), rect.bottomLeft())
            g.setColorAt(0, QColor(pl.color))
            g.setColorAt(1, QColor(pl.color).darker(220))
            p.setPen(Qt.NoPen)
            p.setBrush(g)
            p.drawRoundedRect(rect, 14, 14)
            p.setPen(QPen(QColor(medal[idx]), 1))
            p.setFont(_font(rect.width() * 0.32, True))
            p.drawText(QRectF(rect.x(), rect.y() + h * 0.02, rect.width(), rect.width() * 0.4), Qt.AlignCenter,
                       str(idx + 1))
            p.setPen(QColor("#ffffff"))
            p.setFont(fitted_font(p, pl.name, int(col_w * 1.1), int(h * 0.055)))
            p.setFont(_font(p.font().pixelSize(), True))
            p.drawText(QRectF(rect.x() - col_w * 0.05, rect.y() - h * 0.08, col_w * 1.1, h * 0.07), Qt.AlignCenter,
                       pl.name)
            pts = ("Im Ziel" if score >= 1000 else f"{score} Tipps") if race else f"{score} Punkte"
            p.setFont(_font(h * 0.032))
            p.drawText(QRectF(rect.x(), rect.bottom() - h * 0.07, rect.width(), h * 0.06), Qt.AlignCenter, pts)
        rest = ranking[3:9]
        if rest:
            p.setPen(MUTED)
            p.setFont(_font(h * 0.028))
            text = "   ".join(f"{i + 4}. {hub.players[pid].name}" for i, (pid, _s) in enumerate(rest))
            p.drawText(QRectF(m, base_y + h * 0.03, w - 2 * m, h * 0.05), Qt.AlignCenter, text)
        p.setPen(MUTED)
        p.setFont(_font(h * 0.03))
        p.drawText(QRectF(m, h - m - h * 0.05, w - 2 * m, h * 0.05), Qt.AlignCenter,
                   "Nochmal: „Nochmal“ auf dem Handy oder am PC")
