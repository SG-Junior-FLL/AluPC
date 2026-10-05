"""Zeichnen der Minispiele auf Monitor 2 (mit Animationen). Jede Funktion bekommt einen Zeichen-Kontext `c`."""

from __future__ import annotations

import math
import random
from types import SimpleNamespace

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient

from .games_base import TEAM_COLORS, TEAM_NAMES, clock_text

TEXT = "#f1f5f9"
MUTED = "#94a3b8"
CARD = QColor(255, 255, 255, 14)
_rnd = random.Random()


# =========================================================================== Hilfen
def qc(color, alpha: float | None = None) -> QColor:
    c = QColor(color)
    if alpha is not None:
        c.setAlphaF(max(0.0, min(1.0, alpha)))
    return c


def font(px: float, bold: bool = False) -> QFont:
    f = QFont()
    f.setPixelSize(max(8, int(px)))
    f.setBold(bold)
    return f


def ease_out(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def ease_back(t: float) -> float:
    t = max(0.0, min(1.0, t))
    s = 1.70158
    return 1 + (s + 1) * (t - 1) ** 3 + s * (t - 1) ** 2


def text(p: QPainter, rect: QRectF, txt: str, px: float, color=TEXT, bold=False, align=Qt.AlignCenter,
         wrap=False) -> None:
    """Text, der in das Rechteck passt (wird notfalls kleiner)."""
    f = font(px, bold)
    if wrap:
        flags = int(align) | int(Qt.TextWordWrap)
        while f.pixelSize() > 10:
            br = QFontMetrics(f).boundingRect(rect.toRect(), flags, txt)
            if br.height() <= rect.height() and br.width() <= rect.width():
                break
            f.setPixelSize(int(f.pixelSize() * 0.92))
        p.setFont(f)
        p.setPen(qc(color))
        p.drawText(rect, flags, txt)
        return
    adv = QFontMetrics(f).horizontalAdvance(txt)
    if adv > rect.width() > 0:
        f.setPixelSize(max(8, int(f.pixelSize() * rect.width() / adv)))
    p.setFont(f)
    p.setPen(qc(color))
    p.drawText(rect, align, txt)


def tag(c, x, y, w, label: str, color="#a5b4fc") -> None:
    f = font(c.h * 0.028, True)
    f.setLetterSpacing(QFont.PercentageSpacing, 115)
    c.p.setFont(f)
    c.p.setPen(qc(color))
    c.p.drawText(QRectF(x, y, w, c.h * 0.045), Qt.AlignLeft | Qt.AlignVCenter, label)


def chip(p, rect: QRectF, name: str, color: str, extra: str = "", dim: float = 1.0, mark: str = "",
         avatar: str = "") -> None:
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(255, 255, 255, int(18 * dim)))
    r = rect.height() / 2
    p.drawRoundedRect(rect, r, r)
    d = rect.height() * (0.82 if avatar else 0.5)
    dot = QRectF(rect.x() + rect.height() * (0.1 if avatar else 0.25), rect.center().y() - d / 2, d, d)
    p.setBrush(qc(color, dim * (0.55 if avatar else 1)))
    p.drawEllipse(dot)
    if avatar:  # Emoji im farbigen Kreis
        p.setOpacity(dim)
        text(p, dot, avatar, d * 0.74)
        p.setOpacity(1.0)
    inner = rect.adjusted(rect.height() * 0.95, 0, -rect.height() * 0.35, 0)
    tail = extra or mark
    tail_w = 0.0
    if tail:  # rechts der Wert, der Name bekommt den Rest (überlappt nie)
        tail_w = min(inner.width() * 0.42, QFontMetrics(font(rect.height() * 0.45, True)).horizontalAdvance(tail) + 2)
        text(p, QRectF(inner.right() - tail_w, inner.y(), tail_w, inner.height()), tail, rect.height() * 0.45,
             qc(TEXT, dim), True, Qt.AlignRight | Qt.AlignVCenter)
    name_w = inner.width() - tail_w - (rect.height() * 0.25 if tail else 0)
    text(p, QRectF(inner.x(), inner.y(), name_w, inner.height()), name, rect.height() * 0.45,
         qc(TEXT, dim), align=Qt.AlignLeft | Qt.AlignVCenter)


def scoreboard(c, rect: QRectF, scores: dict, fmt=str, limit: int = 10, marks: dict | None = None) -> None:
    rows = sorted(scores.items(), key=lambda kv: -kv[1])[:limit]
    if not rows:
        return
    row_h = min(rect.height() / len(rows), c.h * 0.065)
    for i, (pid, score) in enumerate(rows):
        pl = c.hub.players.get(pid)
        if pl is None:
            continue
        # sanft an die neue Position gleiten
        key = ("row", pid)
        y_target = rect.y() + i * row_h
        y = c.fx.vals.get(key, y_target)
        y += (y_target - y) * 0.25
        c.fx.vals[key] = y
        chip(c.p, QRectF(rect.x(), y, rect.width(), row_h * 0.84), pl.name, pl.color, fmt(score),
             mark=(marks or {}).get(pid, ""), avatar=pl.avatar)


def time_bar(c, rect: QRectF, part: float) -> None:
    """Zeitbalken (part = 1 … 0), wird gegen Ende gelb/rot."""
    part = max(0.0, min(1.0, part))
    p = c.p
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(255, 255, 255, 22))
    r = rect.height() / 2
    p.drawRoundedRect(rect, r, r)
    color = "#22c55e" if part > 0.5 else "#f59e0b" if part > 0.2 else "#ef4444"
    p.setBrush(qc(color))
    p.drawRoundedRect(QRectF(rect.x(), rect.y(), max(rect.height(), rect.width() * part), rect.height()), r, r)


def ring(c, center: QPointF, radius: float, part: float, label: str = "") -> None:
    p = c.p
    pen = QPen(QColor(255, 255, 255, 30), radius * 0.18)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    p.drawEllipse(center, radius, radius)
    part = max(0.0, min(1.0, part))
    color = "#22c55e" if part > 0.5 else "#f59e0b" if part > 0.2 else "#ef4444"
    pen = QPen(qc(color), radius * 0.18)
    pen.setCapStyle(Qt.RoundCap)
    p.setPen(pen)
    p.drawArc(QRectF(center.x() - radius, center.y() - radius, 2 * radius, 2 * radius), 90 * 16, int(-360 * 16 * part))
    if label:
        text(p, QRectF(center.x() - radius, center.y() - radius, 2 * radius, 2 * radius), label, radius * 0.7,
             TEXT, True)


# ---- Teilchen (Konfetti, Funken, Platzen)
def new_fx():
    return SimpleNamespace(parts=[], vals={}, ev=0, born={}, toasts=[])


def burst(fx, x, y, color, now, n=18, speed=320.0, size=6.0, gravity=500.0, life=0.9):
    for _ in range(n):
        a = _rnd.uniform(0, 2 * math.pi)
        v = speed * _rnd.uniform(0.35, 1.0)
        fx.parts.append([x, y, math.cos(a) * v, math.sin(a) * v - speed * 0.25, color, now,
                         life * _rnd.uniform(0.6, 1.0), size * _rnd.uniform(0.6, 1.3), gravity, _rnd.random() * 6])
    del fx.parts[:-900]


def confetti(fx, w, h, now, n=160, colors=None):
    colors = colors or ["#ef4444", "#3b82f6", "#22c55e", "#facc15", "#a855f7", "#ec4899", "#06b6d4", "#f97316"]
    for _ in range(n):
        x = _rnd.uniform(0, w)
        fx.parts.append([x, -_rnd.uniform(0, h * 0.4), _rnd.uniform(-60, 60), _rnd.uniform(60, 220),
                         _rnd.choice(colors), now, _rnd.uniform(2.5, 4.5), _rnd.uniform(6, 12) * h / 900, 120.0,
                         _rnd.random() * 6])
    del fx.parts[:-900]


def draw_particles(c) -> None:
    p, now = c.p, c.now
    keep = []
    p.setPen(Qt.NoPen)
    for part in c.fx.parts:
        x0, y0, vx, vy, color, born, life, size, g, spin = part
        t = now - born
        if t < 0 or t > life:
            if t < 0:
                keep.append(part)
            continue
        keep.append(part)
        x = x0 + vx * t
        y = y0 + vy * t + 0.5 * g * t * t
        alpha = 1.0 if t < life * 0.7 else (life - t) / (life * 0.3)
        p.setBrush(qc(color, alpha))
        p.save()
        p.translate(x, y)
        p.rotate((spin + t * 6) * 57.3)
        p.drawRect(QRectF(-size / 2, -size / 4, size, size / 2) if g < 200 else QRectF(-size / 2, -size / 2, size,
                                                                                         size))
        p.restore()
    c.fx.parts = keep


def float_text(c, x, y, label, color, born, life=1.2, px=None):
    """Kurz aufsteigender Text (+5, TOR!, PENG!)."""
    t = c.now - born
    if t < 0 or t > life:
        return
    a = 1 - max(0.0, (t - life * 0.6) / (life * 0.4))
    scale = ease_back(min(1.0, t / 0.25))
    px = (px or c.h * 0.05) * scale
    text(c.p, QRectF(x - c.w * 0.2, y - t * c.h * 0.06 - px, c.w * 0.4, px * 2), label, px, qc(color, a), True)


_BG_CACHE: dict = {}
BG_SCALE = 8  # Hintergrund in 1/8 Größe rechnen – weiche Verläufe sehen hochskaliert gleich aus
BG_EVERY = 0.12  # Sekunden: die Flecken wandern so langsam, dass öfter neu rechnen nichts bringt


def _paint_background(p: QPainter, w: float, h: float, now: float) -> None:
    grad = QLinearGradient(0, 0, w, h)
    grad.setColorAt(0, QColor("#0b1020"))
    grad.setColorAt(1, QColor("#1a1033"))
    p.fillRect(QRectF(0, 0, w, h), grad)
    # langsam wandernde, weiche Farbflecken
    for i, color in enumerate(("#6366f1", "#ec4899", "#06b6d4")):
        cx = w * (0.5 + 0.38 * math.sin(now * 0.07 + i * 2.1))
        cy = h * (0.5 + 0.35 * math.cos(now * 0.05 + i * 1.7))
        r = max(w, h) * 0.45
        g = QRadialGradient(QPointF(cx, cy), r)
        g.setColorAt(0, qc(color, 0.10))
        g.setColorAt(1, qc(color, 0.0))
        p.fillRect(QRectF(0, 0, w, h), g)


def background(c) -> None:
    """Hintergrund aller Spiele. Früher 4 Verläufe über den ganzen Bildschirm in JEDEM Bild (Full HD: ~10 ms) –
    jetzt klein gerechnet, zwischengespeichert und nur alle 0,12 s neu."""
    from PySide6.QtGui import QImage

    p, w, h, now = c.p, c.w, c.h, c.now
    sw, sh = max(8, int(w) // BG_SCALE), max(8, int(h) // BG_SCALE)
    key = (sw, sh)
    entry = _BG_CACHE.get(key)
    if entry is None or abs(now - entry[0]) >= BG_EVERY:
        img = QImage(sw, sh, QImage.Format_RGB32)
        q = QPainter(img)
        _paint_background(q, sw, sh, now)
        q.end()
        _BG_CACHE.clear()
        _BG_CACHE[key] = entry = (now, img)
    p.save()
    p.setRenderHint(QPainter.SmoothPixmapTransform, True)
    p.drawImage(QRectF(0, 0, w, h), entry[1])
    p.restore()


def qr_card(c, x, y, side, caption=True, image=None):
    p = c.p
    pad = side * 0.06
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#ffffff"))
    p.drawRoundedRect(QRectF(x - pad, y - pad, side + 2 * pad, side + 2 * pad), pad * 1.5, pad * 1.5)
    from .sources import draw_qr

    draw_qr(p, QRectF(x, y, side, side), image if image is not None else c.qr())
    if caption:
        url = c.url()
        room = min(side * 1.3, 2 * (c.w - 8 - (x + side / 2)))
        text(p, QRectF(x + side / 2 - room / 2, y + side + pad * 2, room, side * 0.12), url, side * 0.07, "#93c5fd")


def name_of(c, pid) -> str:
    pl = c.hub.players.get(pid)
    return pl.name if pl else "?"


def color_of(c, pid) -> str:
    pl = c.hub.players.get(pid)
    return pl.color if pl else "#64748b"


def avatar_of(c, pid) -> str:
    pl = c.hub.players.get(pid)
    return pl.avatar if pl else ""


# =========================================================================== Lobby, 3-2-1, Ergebnis
def lobby(c) -> None:
    p, w, h, hub = c.p, c.w, c.h, c.hub
    m = max(14, int(min(w, h) * 0.05))
    qr_side = int(min(h * 0.46, w * 0.26))
    left_w = w - 3 * m - qr_side
    tag(c, m, m, left_w, "MINISPIELE · HANDY = CONTROLLER")
    spec = hub.spec
    t = c.now - c.fx.born.setdefault(("lobby", hub.game_key), c.now)
    slide = ease_out(t / 0.6)
    text(p, QRectF(m - (1 - slide) * 60, m + h * 0.06, left_w, h * 0.13), spec.title, h * 0.1, qc("#ffffff", slide),
         True, Qt.AlignLeft | Qt.AlignVCenter)
    text(p, QRectF(m, m + h * 0.2, left_w, h * 0.09), spec.help, h * 0.032, MUTED, align=Qt.AlignLeft | Qt.AlignTop,
         wrap=True)
    players = sorted(hub.players.values(), key=lambda pl: pl.joined)
    top = m + h * 0.32
    text(p, QRectF(m, top, left_w, h * 0.055), f"{len(players)} dabei" if players else
         "Noch niemand dabei – QR-Code scannen", h * 0.036, TEXT, True, Qt.AlignLeft | Qt.AlignVCenter)
    chip_h = h * 0.064
    gap = m * 0.35
    if spec.cls.teams:
        col_w = (left_w - gap) / 2
        for team in (0, 1):
            x = m + team * (col_w + gap)
            text(p, QRectF(x, top + h * 0.065, col_w, h * 0.05), TEAM_NAMES[team], h * 0.03, TEAM_COLORS[team], True,
                 Qt.AlignLeft | Qt.AlignVCenter)
            members = [pl for pl in players if pl.team == team]
            for i, pl in enumerate(members[:8]):
                _lobby_chip(c, QRectF(x, top + h * 0.12 + i * (chip_h + gap * 0.6), col_w, chip_h), pl)
    else:
        cols = 3 if left_w > 700 else 2
        cw = (left_w - gap * (cols - 1)) / cols
        for i, pl in enumerate(players):
            r, col = divmod(i, cols)
            _lobby_chip(c, QRectF(m + col * (cw + gap), top + h * 0.075 + r * (chip_h + gap), cw, chip_h), pl)
    text(p, QRectF(m, h - m - h * 0.05, left_w, h * 0.05), "Gestartet wird am PC", h * 0.028, MUTED,
         align=Qt.AlignLeft | Qt.AlignVCenter)
    line = board_line(hub)
    if line:
        text(p, QRectF(m, h - m - h * 0.1, left_w, h * 0.05), line, h * 0.03, "#fbbf24", True,
             Qt.AlignLeft | Qt.AlignVCenter)
    wifi = getattr(c, "wifi", None)
    if wifi:  # Spiele-WLAN: EIN Code – Handy ist im WLAN, die Anmeldeseite (Name → mitspielen) öffnet sich selbst
        qx, qy = w - m - qr_side, (h - qr_side) / 2 - h * 0.02
        text(p, QRectF(qx - m, qy - h * 0.11, qr_side + 2 * m, h * 0.06), "WLAN scannen", h * 0.04, TEXT, True)
        qr_card(c, qx, qy, qr_side, caption=False, image=c.wifi_qr())
        text(p, QRectF(qx - m * 2, qy + qr_side + h * 0.03, qr_side + 4 * m, h * 0.045),
             f"„{wifi[0]}“ · Anmeldung öffnet sich", h * 0.026, "#67e8f9", True)
        text(p, QRectF(qx - m * 2, qy + qr_side + h * 0.075, qr_side + 4 * m, h * 0.04),
             "Name eingeben → mitspielen", h * 0.024, MUTED)
        return
    # Der Code steht still (auch kein „Wippen“): bewegte Codes lesen manche Handy-Kameras schlecht
    qx, qy = w - m - qr_side, (h - qr_side) / 2 - h * 0.03
    qr_card(c, qx, qy, qr_side)
    text(p, QRectF(qx - m, qy - h * 0.1, qr_side + 2 * m, h * 0.06), "Scannen & mitspielen", h * 0.034, TEXT, True)


def _lobby_chip(c, rect, pl):
    t = c.now - pl.joined
    s = ease_back(t / 0.45)
    if s <= 0.01:
        return
    c.p.save()
    c.p.translate(rect.center())
    c.p.scale(s, s)
    c.p.translate(-rect.center())
    chip(c.p, rect.translated(0, math.sin(c.now * 2 + pl.joined) * c.h * 0.003), pl.name, pl.color,
         avatar=pl.avatar)
    c.p.restore()


def intro(c) -> None:
    """3 – 2 – 1 vor dem Spiel: Titel, Erklärung, große Zahl."""
    p, w, h, hub = c.p, c.w, c.h, c.hub
    left = hub.intro_until - c.now
    n = max(1, math.ceil(left))
    frac = left - (n - 1)  # 1 → 0 innerhalb jeder Sekunde
    spec = hub.spec
    t = hub.INTRO - left
    slide = ease_out(t / 0.5)
    text(p, QRectF(0, h * 0.1 - (1 - slide) * 40, w, h * 0.12), spec.title, h * 0.09, qc("#ffffff", slide), True)
    text(p, QRectF(w * 0.12, h * 0.23, w * 0.76, h * 0.1), spec.help, h * 0.035, qc(MUTED, slide), wrap=True)
    scale = 0.6 + 0.6 * ease_back(1 - frac) if frac > 0.15 else 1.2 + (0.15 - frac) * 4
    alpha = min(1.0, frac / 0.15) if frac < 0.15 else 1.0
    center = QPointF(w / 2, h * 0.62)
    ring(c, center, h * 0.2, frac)
    p.save()
    p.translate(center)
    p.scale(scale, scale)
    text(p, QRectF(-h * 0.2, -h * 0.2, h * 0.4, h * 0.4), str(n), h * 0.22, qc("#ffffff", alpha), True)
    p.restore()


def podium(c) -> None:
    p, w, h, hub = c.p, c.w, c.h, c.hub
    m = max(14, int(min(w, h) * 0.05))
    if not c.fx.born.get("confetti"):
        c.fx.born["confetti"] = c.now
        confetti(c.fx, w, h, c.now)
    t = c.now - hub.over_at
    tag(c, m, m, w - 2 * m, f"{hub.spec.title.upper()} · ERGEBNIS", "#86efac")
    if hub.spec.cls.teams:
        _team_result(c, m, t)
        return
    ranking = [(pid, s) for pid, s in hub.ranking if pid in hub.players]
    places = [hub.place_of(pid) for pid, _ in ranking]
    slots = [(0, 0.5, 0.42), (1, 0.22, 0.3), (2, 0.78, 0.22)]  # (Index, x-Mitte, Höhe)
    base_y = h * 0.78
    col_w = w * 0.22
    medal = {1: "#fbbf24", 2: "#cbd5e1", 3: "#d97706"}
    key = hub.game_key
    for idx, cx, height in slots:
        if idx >= len(ranking):
            continue
        pid, score = ranking[idx]
        pl = hub.players[pid]
        grow = ease_out((t - 0.25 * (2 - idx)) / 0.7)
        hh = h * height * grow
        rect = QRectF(w * cx - col_w / 2, base_y - hh, col_w, hh)
        g = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        g.setColorAt(0, QColor(pl.color))
        g.setColorAt(1, QColor(pl.color).darker(220))
        p.setPen(Qt.NoPen)
        p.setBrush(g)
        p.drawRoundedRect(rect, 14, 14)
        if grow < 0.98:
            continue
        place = places[idx] or idx + 1
        text(p, QRectF(rect.x(), rect.y() + h * 0.02, rect.width(), rect.width() * 0.4), str(place),
             rect.width() * 0.32, medal.get(place, TEXT), True)
        text(p, QRectF(rect.x() - col_w * 0.05, rect.y() - h * 0.08, col_w * 1.1, h * 0.07), pl.name, h * 0.055,
             "#ffffff", True)
        if pl.avatar:  # Avatar über dem Namen, hüpft ein bisschen
            hop = abs(math.sin((c.now - hub.over_at) * 4 + idx)) * h * 0.012
            text(p, QRectF(rect.x(), rect.y() - h * 0.17 - hop, rect.width(), h * 0.09), pl.avatar, h * 0.07)
        text(p, QRectF(rect.x(), rect.bottom() - h * 0.07, rect.width(), h * 0.06), score_label(key, score),
             h * 0.032, "#ffffff")
        gain = hub.last_award.get(pl.name)
        if gain:
            a = ease_out((c.now - hub.over_at - 1.2) / 0.5)
            text(p, QRectF(rect.x(), rect.y() + h * 0.15, rect.width(), h * 0.05), f"+{gain} gesamt", h * 0.03,
                 qc("#fbbf24", a), True)
    rest = ranking[3:10]
    if rest:
        line = "   ".join(f"{places[i + 3]}. {hub.players[pid].name}" for i, (pid, _s) in enumerate(rest))
        text(p, QRectF(m, base_y + h * 0.03, w - 2 * m, h * 0.05), line, h * 0.028, MUTED)
    _board_footer(c, m)


def board_line(hub, top: int = 3) -> str:
    rows = hub.board_ranking()[:top]
    if not rows:
        return ""
    return "Bestenliste: " + "  ·  ".join(f"{place}. {name} {pts}" for name, pts, place in rows)


def _board_footer(c, m):
    p, w, h = c.p, c.w, c.h
    line = board_line(c.hub)
    if line:
        text(p, QRectF(m, h - m - h * 0.1, w - 2 * m, h * 0.05), line, h * 0.03, "#fbbf24", True)
    text(p, QRectF(m, h - m - h * 0.05, w - 2 * m, h * 0.05), "Das nächste Spiel startet am PC", h * 0.028, MUTED)


def board(c) -> None:
    """Bestenliste über den ganzen Abend: Balken wachsen nacheinander, die ersten drei mit Medaille."""
    p, w, h, hub = c.p, c.w, c.h, c.hub
    m = max(14, int(min(w, h) * 0.05))
    t = c.now - hub.board_at
    if not c.fx.born.get("confetti") and hub.board:
        c.fx.born["confetti"] = c.now
        confetti(c.fx, w, h, c.now, n=120)
    tag(c, m, m, w - 2 * m, "BESTENLISTE DES ABENDS", "#fbbf24")
    games = hub.board_games
    s = ease_back(t / 0.5)
    p.save()
    p.translate(w / 2, m + h * 0.1)
    p.scale(s, s)
    text(p, QRectF(-w * 0.45, -h * 0.05, w * 0.9, h * 0.1),
         f"nach {games} {'Spiel' if games == 1 else 'Spielen'}" if games else "Noch keine Punkte", h * 0.06,
         "#ffffff", True)
    p.restore()
    rows = hub.board_ranking()[:16]
    if not rows:
        text(p, QRectF(0, h * 0.4, w, h * 0.1), "Erst ein Spiel spielen – dann gibt es hier Punkte", h * 0.04, MUTED)
        return
    cols = 1 if len(rows) <= 8 else 2
    per_col = math.ceil(len(rows) / cols)
    top = m + h * 0.2
    row_h = min(h * 0.085, (h - top - m) / per_col)
    col_w = (w - 2 * m - (cols - 1) * m) / cols
    best = max(pts for _n, pts, _pl in rows) or 1
    medal = {1: "#fbbf24", 2: "#cbd5e1", 3: "#d97706"}
    # von unten nach oben aufbauen: Platz 1 kommt zuletzt (Spannung)
    for i, (name, pts, place) in enumerate(rows):
        col, r = divmod(i, per_col)
        x = m + col * (col_w + m)
        y = top + r * row_h
        delay = (len(rows) - 1 - i) * 0.18
        k = ease_out((t - 0.4 - delay) / 0.6)
        if k <= 0:
            continue
        circle = row_h * 0.7
        p.setPen(Qt.NoPen)
        p.setBrush(qc(medal.get(place, "#334155"), k))
        p.drawEllipse(QRectF(x, y + (row_h - circle) / 2, circle, circle))
        text(p, QRectF(x, y + (row_h - circle) / 2, circle, circle), str(place), circle * 0.5,
             qc("#0b1020" if place in medal else TEXT, k), True)
        bar_x = x + circle + row_h * 0.25
        bar_w = (col_w - circle - row_h * 0.25) * (0.35 + 0.65 * pts / best) * k
        bar = QRectF(bar_x, y + row_h * 0.14, bar_w, row_h * 0.72)
        color = QColor(hub.color_of_name(name))
        g = QLinearGradient(bar.topLeft(), bar.topRight())
        g.setColorAt(0, qc(color.darker(150).name(), 0.9 * k))
        g.setColorAt(1, qc(color.name(), 0.9 * k))
        p.setBrush(g)
        p.drawRoundedRect(bar, bar.height() / 2, bar.height() / 2)
        inner = bar.adjusted(row_h * 0.3, 0, -row_h * 0.3, 0)
        avatar = hub.avatar_of_name(name)
        text(p, inner, f"{avatar}  {name}" if avatar else name, row_h * 0.4, qc("#ffffff", k), True,
             Qt.AlignLeft | Qt.AlignVCenter)
        text(p, inner, str(int(pts * k)), row_h * 0.42, qc("#ffffff", k), True, Qt.AlignRight | Qt.AlignVCenter)
        if place == 1 and k >= 1 and ("crown", name) not in c.fx.born:
            c.fx.born[("crown", name)] = c.now
            burst(c.fx, bar.right(), bar.center().y(), "#fbbf24", c.now, n=40, speed=380)


def score_label(key: str, score) -> str:
    if key == "rennen":
        return "Im Ziel" if score >= 1000 else f"{int(score)} Tipps"
    if key == "simon":
        return f"Runde {int(score)}"
    if key == "ballon":
        return f"{int(score)} gepumpt"
    return f"{int(score)} Punkte"


def _team_result(c, m, t):
    p, w, h, hub = c.p, c.w, c.h, c.hub
    win = hub.team_result()
    s = ease_back(t / 0.6)
    title = "Unentschieden!" if win is None else f"{TEAM_NAMES[win]} gewinnt!"
    color = "#ffffff" if win is None else TEAM_COLORS[win]
    p.save()
    p.translate(w / 2, h * 0.24)
    p.scale(s, s)
    text(p, QRectF(-w * 0.45, -h * 0.08, w * 0.9, h * 0.16), title, h * 0.1, color, True)
    p.restore()
    game = hub.game
    extra = ""
    if hasattr(game, "goals"):
        extra = f"{game.goals[0]} : {game.goals[1]}"
    if extra:
        text(p, QRectF(0, h * 0.33, w, h * 0.07), extra, h * 0.06, TEXT, True)
    col_w = w * 0.36
    scores = dict(hub.ranking)
    for team in (0, 1):
        x = w / 2 - col_w - m / 2 if team == 0 else w / 2 + m / 2
        y0 = h * 0.43
        text(p, QRectF(x, y0, col_w, h * 0.05), TEAM_NAMES[team], h * 0.036, TEAM_COLORS[team], True,
             Qt.AlignLeft | Qt.AlignVCenter)
        members = sorted((pid for pid, pl in hub.players.items() if pl.team == team and pid in scores),
                         key=lambda pid: -scores[pid])
        unit = getattr(game, "unit", "Treffer" if hasattr(game, "goals") else "Züge")
        for i, pid in enumerate(members[:7]):
            appear = ease_out((t - 0.4 - i * 0.08) / 0.4)
            if appear <= 0:
                continue
            chip(p, QRectF(x - (1 - appear) * 30, y0 + h * 0.065 + i * h * 0.062, col_w, h * 0.054),
                 hub.players[pid].name, hub.players[pid].color, f"{int(scores[pid] % 1000)} {unit}", dim=appear)
    _board_footer(c, m)


# =========================================================================== Ausscheiden (Simon)
def _alive_strip(c, g, top, m, answered=None, progress=None, seq_len=0) -> None:
    """Spieler-Kacheln unten: wer ist noch drin, wer ist raus (mit Wackeln und rotem Blitz)."""
    p, w, h, now = c.p, c.w, c.h, c.now
    pids = sorted(g.players, key=lambda pid: (pid not in g.alive, -g.out_round.get(pid, 0), name_of(c, pid)))
    cols = min(6, max(1, len(pids)))
    rows = max(1, math.ceil(len(pids) / cols))
    gap = m * 0.4
    cw = (w - 2 * m - gap * (cols - 1)) / cols
    ch = min(h * 0.07, (h - top - m) / rows - gap)
    for i, pid in enumerate(pids):
        r, col = divmod(i, cols)
        rect = QRectF(m + col * (cw + gap), top + r * (ch + gap), cw, ch)
        out = pid not in g.alive
        born = c.fx.born.get(("out", pid))
        shake = 0.0
        if born is not None:
            age = now - born
            if age < 0.6:
                shake = math.sin(age * 60) * h * 0.008 * (1 - age / 0.6)
                if ("outfx", pid) not in c.fx.born:
                    c.fx.born[("outfx", pid)] = now
                    burst(c.fx, rect.center().x(), rect.center().y(), "#ef4444", now, n=22, speed=260)
        mark = "RAUS" if out else ""
        if not out and answered is not None and pid in answered:
            mark = "✓"
        if not out and progress is not None:
            mark = "✓" if pid in getattr(g, "done", ()) else ("✗" if pid in getattr(g, "failed", ()) else
                                                               f"{progress.get(pid, 0)}/{seq_len}")
        chip(p, rect.translated(shake, 0), name_of(c, pid), color_of(c, pid), avatar=avatar_of(c, pid), mark=mark, dim=0.35 if out else 1.0)


# =========================================================================== Simon sagt
def simon(c, g, events) -> None:
    from .games_party import SIMON_PADS

    p, w, h, now = c.p, c.w, c.h, c.now
    m = max(14, int(min(w, h) * 0.045))
    for _n, t, kind, data in events:
        if kind == "out":
            c.fx.born[("out", data["pid"])] = t
        elif kind == "go":
            c.fx.born["go"] = t
    tag(c, m, m, w * 0.6, f"SIMON SAGT · RUNDE {g.round} · {len(g.seq)} FARBEN · NOCH {len(g.alive)} IM SPIEL")
    size = min(h * 0.56, w * 0.42)
    center = QPointF(w * 0.3, h * 0.45)
    lit = g.lit(now)
    outer, inner = size / 2, size * 0.2
    for i, (_name, color) in enumerate(SIMON_PADS):
        start = [90, 0, 180, 270][i]  # grün oben links, rot oben rechts, gelb unten links, blau unten rechts
        path = QPainterPath()
        path.arcMoveTo(QRectF(center.x() - outer, center.y() - outer, 2 * outer, 2 * outer), start + 2)
        path.arcTo(QRectF(center.x() - outer, center.y() - outer, 2 * outer, 2 * outer), start + 2, 86)
        path.arcTo(QRectF(center.x() - inner, center.y() - inner, 2 * inner, 2 * inner), start + 88, -86)
        path.closeSubpath()
        on = lit == i
        col = QColor(color)
        if on:
            glow = QRadialGradient(center, outer * 1.3)
            glow.setColorAt(0.5, qc(color, 0.55))
            glow.setColorAt(1, qc(color, 0.0))
            p.setPen(Qt.NoPen)
            p.setBrush(glow)
            p.drawEllipse(center, outer * 1.3, outer * 1.3)
        p.setPen(Qt.NoPen)
        p.setBrush(col.lighter(135) if on else col.darker(260))
        p.drawPath(path)
    p.setBrush(QColor("#0f172a"))
    p.drawEllipse(center, inner * 0.92, inner * 0.92)
    label = {"zeigen": "Merken!", "eingabe": "Jetzt ihr!", "pause": "…"}[g.phase]
    text(p, QRectF(center.x() - inner, center.y() - inner * 0.6, 2 * inner, inner * 0.7), label, inner * 0.32,
         "#ffffff", True)
    if g.phase == "eingabe":
        part = (g.until - now) / (3.0 + 0.9 * len(g.seq))
        ring(c, QPointF(center.x(), center.y() + inner * 0.35), inner * 0.32, part)
    elif g.phase == "pause" and g.all_failed:
        text(p, QRectF(center.x() - outer, center.y() + outer + h * 0.01, 2 * outer, h * 0.05),
             "Alle falsch – keiner fliegt raus!", h * 0.035, "#fbbf24", True)
    # Folge als Punkte (beim Eingeben)
    if g.phase != "zeigen":
        dot = min(h * 0.022, (outer * 2) / max(1, len(g.seq)) / 2.6)
        total = len(g.seq) * dot * 2.6
        p.setPen(Qt.NoPen)
        for k, pad in enumerate(g.seq):
            # beim Eingeben nur graue Punkte (sonst könnte man die Folge ablesen)
            p.setBrush(qc(SIMON_PADS[pad][1], 0.85) if g.phase == "pause" else QColor(255, 255, 255, 50))
            p.drawEllipse(QPointF(center.x() - total / 2 + dot * 1.3 + k * dot * 2.6, center.y() + outer + h * 0.06),
                          dot, dot)
    # Spieler rechts
    side = QRectF(w * 0.6, h * 0.12, w * 0.4 - m, h * 0.8)
    pids = sorted(g.players, key=lambda pid: (pid not in g.alive, name_of(c, pid)))
    row_h = min(side.height() / max(1, len(pids)), h * 0.07)
    for i, pid in enumerate(pids):
        rect = QRectF(side.x(), side.y() + i * row_h, side.width(), row_h * 0.84)
        out = pid not in g.alive
        born = c.fx.born.get(("out", pid))
        shake = 0.0
        if born is not None and now - born < 0.6:
            shake = math.sin((now - born) * 60) * h * 0.008
            if ("outfx", pid) not in c.fx.born:
                c.fx.born[("outfx", pid)] = now
                burst(c.fx, rect.center().x(), rect.center().y(), "#ef4444", now, n=22, speed=260)
        if out:
            mark = "RAUS"
        elif g.phase == "eingabe":
            mark = "✓" if pid in g.done else "✗" if pid in g.failed else f"{g.progress.get(pid, 0)}/{len(g.seq)}"
        else:
            mark = ""
        chip(p, rect.translated(shake, 0), name_of(c, pid), color_of(c, pid), avatar=avatar_of(c, pid), mark=mark, dim=0.35 if out else 1)
        if g.phase == "eingabe" and not out and pid not in g.done:  # Fortschritt
            part = g.progress.get(pid, 0) / max(1, len(g.seq))
            p.setPen(Qt.NoPen)
            p.setBrush(qc(color_of(c, pid), 0.35))
            p.drawRoundedRect(QRectF(rect.x(), rect.bottom() - 4, rect.width() * part, 4), 2, 2)


# =========================================================================== Pong
def pong(c, g, events) -> None:
    p, w, h, now = c.p, c.w, c.h, c.now
    m = max(10, int(min(w, h) * 0.03))
    top = m + h * 0.1
    scale = min((w - 2 * m) / g.W, (h - top - m) / g.H)
    fw, fh = g.W * scale, g.H * scale
    fx0, fy0 = (w - fw) / 2, top + (h - top - m - fh) / 2
    field = QRectF(fx0, fy0, fw, fh)

    def pt(x, y):
        return QPointF(fx0 + x * scale, fy0 + y * scale)

    for _n, t, kind, data in events:
        if kind == "hit":
            q = pt(data["x"], data["y"])
            burst(c.fx, q.x(), q.y(), color_of(c, data["pid"]), now, n=14, speed=260, size=5, gravity=0)
        elif kind == "goal":
            c.fx.born["goal"] = t
            c.fx.vals["goal_team"] = data["team"]
            q = pt(0 if data["team"] == 1 else g.W, g.H / 2)
            burst(c.fx, q.x(), q.y(), TEAM_COLORS[data["team"]], now, n=50, speed=420)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(255, 255, 255, 10))
    p.drawRoundedRect(field.adjusted(-6, -6, 6, 6), 16, 16)
    for team, rect in ((0, QRectF(fx0, fy0, fw / 2, fh)), (1, QRectF(fx0 + fw / 2, fy0, fw / 2, fh))):
        grad = QLinearGradient(rect.topLeft() if team == 0 else rect.topRight(), rect.center())
        grad.setColorAt(0, qc(TEAM_COLORS[team], 0.16))
        grad.setColorAt(1, qc(TEAM_COLORS[team], 0.0))
        p.fillRect(rect, grad)
    goal_born = c.fx.born.get("goal")
    if goal_born is not None and now - goal_born < 0.8:
        a = 1 - (now - goal_born) / 0.8
        team = c.fx.vals.get("goal_team", 0)
        p.fillRect(QRectF(fx0 + (0 if team == 1 else fw / 2), fy0, fw / 2, fh), qc(TEAM_COLORS[team], 0.3 * a))
    pen = QPen(QColor(255, 255, 255, 50), max(2, scale * 0.06), Qt.DashLine)
    p.setPen(pen)
    p.drawLine(pt(g.W / 2, 0), pt(g.W / 2, g.H))
    p.setBrush(Qt.NoBrush)
    p.drawEllipse(pt(g.W / 2, g.H / 2), scale * 1.2, scale * 1.2)
    # Stand
    pop = 1.0
    if goal_born is not None and now - goal_born < 0.5:
        pop = 1 + 0.4 * (1 - (now - goal_born) / 0.5)
    p.save()
    p.translate(w / 2, m + h * 0.045)
    p.scale(pop, pop)
    text(p, QRectF(-w * 0.1, -h * 0.045, w * 0.2, h * 0.09), f"{g.goals[0]} : {g.goals[1]}", h * 0.07, TEXT, True)
    p.restore()
    text(p, QRectF(m, m, w * 0.35, h * 0.08), TEAM_NAMES[0], h * 0.04, TEAM_COLORS[0], True,
         Qt.AlignLeft | Qt.AlignVCenter)
    text(p, QRectF(w - m - w * 0.35, m, w * 0.35, h * 0.08), TEAM_NAMES[1], h * 0.04, TEAM_COLORS[1], True,
         Qt.AlignRight | Qt.AlignVCenter)
    text(p, QRectF(w * 0.6, m + h * 0.05, w * 0.4 - m, h * 0.04), f"bis {g.to_win}", h * 0.024, MUTED,
         align=Qt.AlignLeft | Qt.AlignVCenter)
    # Schläger
    for pid, pad in g.paddles.items():
        center = pt(pad["x"], pad["y"])
        rect = QRectF(center.x() - g.PW * scale / 2, center.y() - g.PH * scale / 2, g.PW * scale, g.PH * scale)
        glow = QRadialGradient(center, g.PH * scale * 0.7)
        glow.setColorAt(0, qc(TEAM_COLORS[pad["team"]], 0.35))
        glow.setColorAt(1, qc(TEAM_COLORS[pad["team"]], 0.0))
        p.setPen(Qt.NoPen)
        p.setBrush(glow)
        p.drawEllipse(center, g.PH * scale * 0.7, g.PH * scale * 0.7)
        p.setBrush(qc(color_of(c, pid)))
        p.drawRoundedRect(rect, rect.width() / 2, rect.width() / 2)
        lx = rect.right() + 6 if pad["team"] == 0 else rect.left() - 6 - w * 0.1
        text(p, QRectF(lx, rect.center().y() - h * 0.016, w * 0.1, h * 0.032), name_of(c, pid), h * 0.022,
             qc(TEXT, 0.8), align=(Qt.AlignLeft if pad["team"] == 0 else Qt.AlignRight) | Qt.AlignVCenter)
    # Ball mit Schweif
    for i, (x, y) in enumerate(g.trail):
        a = (i + 1) / max(1, len(g.trail)) * 0.35
        p.setBrush(qc("#ffffff", a))
        p.drawEllipse(pt(x, y), g.R * scale * (0.4 + 0.6 * a / 0.35), g.R * scale * (0.4 + 0.6 * a / 0.35))
    waiting = now < g.serve_at
    if not waiting or int(now * 6) % 2 == 0:
        p.setBrush(QColor("#ffffff"))
        p.drawEllipse(pt(g.bx, g.by), g.R * scale, g.R * scale)
    if goal_born is not None and now - goal_born < 1.1:
        float_text(c, w / 2, h * 0.45, "TOR!", TEAM_COLORS[c.fx.vals.get("goal_team", 0)], goal_born, 1.1, h * 0.12)


# =========================================================================== Ballon
def ballon(c, g, events) -> None:
    p, w, h, now = c.p, c.w, c.h, c.now
    m = max(14, int(min(w, h) * 0.04))
    for _n, t, kind, data in events:
        if kind in ("burst", "bank"):
            c.fx.born[(kind, data["pid"], g.round)] = t
        elif kind == "round":
            c.fx.born["round"] = t
    tag(c, m, m, w * 0.7, f"BALLON · RUNDE {g.round} / {g.rounds} · ALLE PLATZEN BEI DERSELBEN ZAHL")
    if g.phase == "pumpen":
        text(p, QRectF(w - m - w * 0.2, m, w * 0.2, h * 0.05), clock_text(g.until - now), h * 0.04, TEXT, True,
             Qt.AlignRight | Qt.AlignVCenter)
    else:
        t = now - (g.until - g.REVEAL)
        s = ease_back(t / 0.4)
        p.save()
        p.translate(w / 2, h * 0.11)
        p.scale(s, s)
        text(p, QRectF(-w * 0.4, -h * 0.05, w * 0.8, h * 0.1), f"Geplatzt wäre er bei {g.limit}", h * 0.06,
             "#fbbf24", True)
        p.restore()
    pids = list(g.state)
    n = max(1, len(pids))
    cols = min(n, 8)
    rows = math.ceil(n / cols)
    cell_w = (w - 2 * m) / cols
    cell_h = (h - m - h * 0.18) / rows
    for i, pid in enumerate(pids):
        st = g.state[pid]
        r, col = divmod(i, cols)
        cx = m + (col + 0.5) * cell_w
        base = h * 0.18 + (r + 1) * cell_h - h * 0.07
        key = ("size", pid)
        target = 0.3 + 0.7 * min(1.0, math.sqrt(st["pumps"] / 45))
        size = c.fx.vals.get(key, 0.3)
        size += (target - size) * 0.3
        c.fx.vals[key] = size
        if g.phase == "pumpen" and st["pumps"] == 0:
            c.fx.vals[key] = size = 0.3
        rad = min(cell_w * 0.42, cell_h * 0.36) * size
        color = color_of(c, pid)
        burst_t = c.fx.born.get(("burst", pid, g.round))
        bank_t = c.fx.born.get(("bank", pid, g.round))
        cy = base - h * 0.06 - rad
        if st["st"] == "banked" and bank_t is not None:
            cy -= min(1.0, (now - bank_t) / 0.6) * h * 0.02
        text(p, QRectF(cx - cell_w / 2, base, cell_w, h * 0.04), name_of(c, pid), h * 0.028, TEXT, True)
        label = {"pump": str(st["pumps"]), "banked": f"✓ {st['pumps']}", "burst": "0"}[st["st"]]
        text(p, QRectF(cx - cell_w / 2, base + h * 0.035, cell_w, h * 0.035), label, h * 0.026,
             "#4ade80" if st["st"] == "banked" else "#f87171" if st["st"] == "burst" else MUTED, True)
        if st["st"] == "burst":
            if burst_t is not None and ("burstfx", pid, g.round) not in c.fx.born:
                c.fx.born[("burstfx", pid, g.round)] = now
                burst(c.fx, cx, cy, color, now, n=40, speed=520, size=9)
            if burst_t is not None:
                float_text(c, cx, cy, "PENG!", "#f87171", burst_t, 1.2, h * 0.06)
            p.setPen(QPen(QColor(255, 255, 255, 80), 2))
            p.drawLine(QPointF(cx, base - h * 0.01), QPointF(cx, base - h * 0.06))
            continue
        wob = math.sin(now * 3 + i) * rad * 0.04
        # Schnur
        p.setPen(QPen(QColor(255, 255, 255, 110), 2))
        path = QPainterPath(QPointF(cx, cy + rad * 1.1))
        path.cubicTo(QPointF(cx + rad * 0.2, cy + rad * 1.4), QPointF(cx - rad * 0.2, base - h * 0.04),
                     QPointF(cx, base - h * 0.01))
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)
        # Ballon
        grad = QRadialGradient(QPointF(cx - rad * 0.35, cy - rad * 0.4), rad * 1.4)
        grad.setColorAt(0, QColor(color).lighter(170))
        grad.setColorAt(1, QColor(color))
        p.setPen(Qt.NoPen)
        p.setBrush(grad)
        p.drawEllipse(QRectF(cx - rad + wob, cy - rad * 1.1, rad * 2 - 2 * wob, rad * 2.2))
        knot = QPainterPath(QPointF(cx - rad * 0.1, cy + rad * 1.1))
        knot.lineTo(QPointF(cx + rad * 0.1, cy + rad * 1.1))
        knot.lineTo(QPointF(cx, cy + rad * 1.0))
        p.setBrush(QColor(color).darker(130))
        p.drawPath(knot)
        if st["st"] == "banked" and bank_t is not None:
            float_text(c, cx, cy - rad, f"+{st['pumps']}", "#4ade80", bank_t, 1.4, h * 0.045)


# =========================================================================== Snake, Tipp-Rennen
def schlangen(c, g, events) -> None:
    p, w, h, now = c.p, c.w, c.h, c.now
    m = max(10, int(min(w, h) * 0.03))
    side_w = w * 0.22
    area = QRectF(m, m + h * 0.06, w - 3 * m - side_w, h - 2 * m - h * 0.06)
    cell = min(area.width() / g.W, area.height() / g.H)
    bx = area.x() + (area.width() - cell * g.W) / 2
    by = area.y() + (area.height() - cell * g.H) / 2
    board = QRectF(bx, by, cell * g.W, cell * g.H)
    for _n, t, kind, data in events:
        x, y = data["cell"]
        q = (bx + (x + 0.5) * cell, by + (y + 0.5) * cell)
        if kind == "eat":
            burst(c.fx, q[0], q[1], "#fbbf24", now, n=10, speed=160, size=4, gravity=0, life=0.5)
        elif kind == "crash":
            burst(c.fx, q[0], q[1], color_of(c, data["pid"]), now, n=30, speed=300, size=6)
            if data.get("wall"):
                c.fx.born["wall"] = t
    tag(c, m, m, area.width(), "SNAKE")
    left = g.remaining(now)
    text(p, QRectF(m, m, area.width(), h * 0.05), clock_text(left), h * 0.04, "#fbbf24" if left < 10 else TEXT, True,
         Qt.AlignRight | Qt.AlignVCenter)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(255, 255, 255, 10))
    p.drawRoundedRect(board.adjusted(-4, -4, 4, 4), 10, 10)
    # Wand: der Rand ist tödlich – rot leuchtend (blitzt kurz auf, wenn jemand dagegen fährt)
    hit = c.fx.born.get("wall")
    flash = 1 - (now - hit) / 0.5 if hit is not None and now - hit < 0.5 else 0.0
    wall = max(3.0, cell * 0.22)
    p.setPen(QPen(qc("#ef4444", 0.55 + 0.45 * flash), wall))
    p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(board.adjusted(-wall / 2 - 2, -wall / 2 - 2, wall / 2 + 2, wall / 2 + 2), 10, 10)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#fbbf24"))
    pulse = 0.32 + 0.06 * math.sin(now * 6)
    for fx_, fy in g.food:
        p.drawEllipse(QPointF(bx + (fx_ + 0.5) * cell, by + (fy + 0.5) * cell), cell * pulse, cell * pulse)
    for pid, s in g.snakes.items():
        if not s["alive"]:
            continue
        color = QColor(color_of(c, pid))
        for k, (x, y) in enumerate(s["body"]):
            p.setBrush(color.lighter(125) if k == 0 else color)
            inset = cell * (0.06 if k == 0 else 0.12)
            p.drawRoundedRect(QRectF(bx + x * cell + inset, by + y * cell + inset, cell - 2 * inset,
                                     cell - 2 * inset), cell * 0.3, cell * 0.3)
        hx, hy = s["body"][0]
        label = QRectF(bx + hx * cell - cell * 3, by + hy * cell - cell * 1.05, cell * 7, cell * 0.9)
        text(p, label.translated(1, 1), name_of(c, pid), cell * 0.62, qc("#000000", 0.6))
        text(p, label, name_of(c, pid), cell * 0.62, "#ffffff")
        p.setPen(Qt.NoPen)
    scoreboard(c, QRectF(w - m - side_w, m + h * 0.06, side_w, h * 0.62), g.scores(), limit=8)
    q = min(side_w * 0.5, h * 0.18)
    x, y = w - m - side_w / 2 - q / 2, h - m - q - q * 0.06 - h * 0.04
    qr_card(c, x, y, q, caption=False)
    text(p, QRectF(w - m - side_w, h - m - h * 0.035, side_w, h * 0.035), "Einsteigen", h * 0.022, MUTED)


def rennen(c, g, events) -> None:
    p, w, h, now = c.p, c.w, c.h, c.now
    m = max(14, int(min(w, h) * 0.04))
    tag(c, m, m, w - 2 * m, f"TIPP-RENNEN · {g.goal} TIPPS BIS ZUM ZIEL")
    pids = list(g.progress)
    top = m + h * 0.08
    lane_h = min((h - top - m) / max(1, len(pids)), h * 0.14)
    name_w = w * 0.18
    track_x = m + name_w + m * 0.5
    track_w = w - track_x - m - h * 0.06
    for _n, t, kind, data in events:
        if kind == "finish" and data["pid"] in pids:
            i = pids.index(data["pid"])
            burst(c.fx, track_x + track_w, top + i * lane_h + lane_h / 2, color_of(c, data["pid"]), now, n=40)
    for i, pid in enumerate(pids):
        y = top + i * lane_h
        cy = y + lane_h / 2
        text(p, QRectF(m, y, name_w, lane_h), name_of(c, pid), lane_h * 0.32, TEXT, align=Qt.AlignRight |
             Qt.AlignVCenter)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 16))
        p.drawRoundedRect(QRectF(track_x, cy - lane_h * 0.14, track_w, lane_h * 0.28), lane_h * 0.14, lane_h * 0.14)
        key = ("share", pid)
        target = min(1.0, g.progress[pid] / g.goal)
        share = c.fx.vals.get(key, 0.0)
        share += (target - share) * 0.35
        c.fx.vals[key] = share
        color = QColor(color_of(c, pid))
        p.setBrush(color.darker(140))
        p.drawRoundedRect(QRectF(track_x, cy - lane_h * 0.14, track_w * share, lane_h * 0.28), lane_h * 0.14,
                          lane_h * 0.14)
        r = lane_h * 0.3
        recent = now - g.last_tap.get(pid, -9) < 0.12
        p.setBrush(color.lighter(130) if recent else color)
        p.drawEllipse(QPointF(track_x + track_w * share, cy), r * (1.1 if recent else 1), r * (1.1 if recent else 1))
        if pid in g.finish:
            text(p, QRectF(track_x + track_w * share - r, cy - r, 2 * r, 2 * r), str(g.finish.index(pid) + 1), r * 1.1,
                 "#ffffff", True)
    fx = track_x + track_w + h * 0.02
    sq = h * 0.015
    for k in range(int((h - top - m) / sq)):
        for j in range(2):
            p.fillRect(QRectF(fx + j * sq, top + k * sq, sq, sq), QColor("#ffffff") if (k + j) % 2 else
                       QColor("#111827"))


# =========================================================================== Schere, Stein, Papier
def ssp(c, g, events) -> None:
    from .games_retro import RPS

    p, w, h, now = c.p, c.w, c.h, c.now
    m = max(14, int(min(w, h) * 0.045))
    for _n, t, kind, data in events:
        if kind == "reveal":
            c.fx.born["rps_reveal"] = t
        elif kind == "pick":
            c.fx.born[("pick", data["pid"])] = t
    side_w = w * 0.24
    main = QRectF(m, m, w - 3 * m - side_w, h - 2 * m)
    tag(c, m, m, main.width(), f"SCHERE · STEIN · PAPIER · RUNDE {g.round} / {g.rounds}", "#fda4af")
    col_w = main.width() / 3
    if g.phase == "waehlen":
        text(p, QRectF(main.x(), main.y() + h * 0.08, main.width(), h * 0.09), "Geheim wählen!", h * 0.07, TEXT, True)
        time_bar(c, QRectF(main.x() + main.width() * 0.2, main.y() + h * 0.19, main.width() * 0.6, h * 0.018),
                 (g.until - now) / g.CHOOSE)
        for i, (_k, label, emoji) in enumerate(RPS):  # die drei Zeichen wippen im Takt
            cx = main.x() + col_w * (i + 0.5)
            bob = math.sin(now * 5 + i) * h * 0.02
            text(p, QRectF(cx - col_w / 2, main.y() + h * 0.27 + bob, col_w, h * 0.22), emoji, h * 0.16)
            text(p, QRectF(cx - col_w / 2, main.y() + h * 0.5, col_w, h * 0.06), label, h * 0.04, MUTED, True)
        players = [pid for pid in g.score]
        chip_w = min(main.width() / 4, w * 0.16)
        for i, pid in enumerate(players[:16]):
            r_, col = divmod(i, 4)
            rect = QRectF(main.x() + col * (chip_w + m * 0.3), main.y() + h * 0.62 + r_ * h * 0.075, chip_w, h * 0.06)
            done = pid in g.picks
            chip(p, rect, name_of(c, pid), color_of(c, pid), "✓" if done else "…", dim=1.0 if done else 0.5,
                 avatar=avatar_of(c, pid))
    else:
        t = now - c.fx.born.get("rps_reveal", now)
        counts = g.counts()
        for i, (key, label, emoji) in enumerate(RPS):
            k = ease_back(min(1.0, max(0.0, (t - i * 0.15) / 0.4)))
            cx = main.x() + col_w * (i + 0.5)
            p.save()
            p.translate(cx, main.y() + h * 0.24)
            p.scale(k, k)
            text(p, QRectF(-col_w / 2, -h * 0.11, col_w, h * 0.22), emoji, h * 0.15)
            p.restore()
            text(p, QRectF(cx - col_w / 2, main.y() + h * 0.37, col_w, h * 0.06), f"{label} · {counts[key]}×",
                 h * 0.038, TEXT, True)
            pids = [pid for pid, v in g.picks.items() if v == key]
            for j, pid in enumerate(pids[:7]):
                gained = g.gained.get(pid, 0)
                chip(p, QRectF(cx - col_w * 0.45, main.y() + h * 0.45 + j * h * 0.068, col_w * 0.9, h * 0.058),
                     name_of(c, pid), color_of(c, pid), f"+{gained}" if gained else "0", dim=k,
                     avatar=avatar_of(c, pid))
    scoreboard(c, QRectF(w - m - side_w, m + h * 0.07, side_w, h * 0.8), g.scores())


# =========================================================================== Tic-Tac-Toe
def _mark(p, rect: QRectF, mark: str, grow: float = 1.0, alpha: float = 1.0) -> None:
    r = rect.adjusted(rect.width() * 0.2, rect.height() * 0.2, -rect.width() * 0.2, -rect.height() * 0.2)
    if grow < 1:
        k = (1 - grow) * r.width() / 2
        r = r.adjusted(k, k, -k, -k)
    color = TEAM_COLORS[0] if mark == "X" else TEAM_COLORS[1]
    pen = QPen(qc(color, alpha), max(4.0, rect.width() * 0.11))
    pen.setCapStyle(Qt.RoundCap)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    if mark == "X":
        p.drawLine(r.topLeft(), r.bottomRight())
        p.drawLine(r.topRight(), r.bottomLeft())
    else:
        p.drawEllipse(r)


def tictactoe(c, g, events) -> None:
    p, w, h, now = c.p, c.w, c.h, c.now
    m = max(10, int(min(w, h) * 0.03))
    for _n, t, kind, data in events:
        if kind == "place":
            c.fx.born[f"ttt{data['cell']}"] = t
        elif kind == "line":
            c.fx.born["tttline"] = t
            confetti(c.fx, w, h, now, n=90, colors=[TEAM_COLORS[data["team"]], "#ffffff"])
    side = min(h * 0.72, w * 0.5)
    board = QRectF((w - side) / 2, h * 0.17, side, side)
    cs = side / 3
    # Kopf: Teams, Stand, wer dran ist
    text(p, QRectF(m, m, w * 0.3, h * 0.07), f"✕  {TEAM_NAMES[0]}", h * 0.042, TEAM_COLORS[0], True,
         Qt.AlignLeft | Qt.AlignVCenter)
    text(p, QRectF(w - m - w * 0.3, m, w * 0.3, h * 0.07), f"{TEAM_NAMES[1]}  ◯", h * 0.042, TEAM_COLORS[1], True,
         Qt.AlignRight | Qt.AlignVCenter)
    text(p, QRectF(w * 0.35, m, w * 0.3, h * 0.07), f"{g.wins[0]} : {g.wins[1]}", h * 0.06, TEXT, True)
    text(p, QRectF(w * 0.35, m + h * 0.065, w * 0.3, h * 0.04), f"Runde {g.round} / {g.rounds}", h * 0.026, MUTED)
    if g.result == "draw":
        status, color = "Unentschieden!", TEXT
    elif g.result:
        team = 0 if g.result == "X" else 1
        status, color = f"{TEAM_NAMES[team]} gewinnt die Runde!", TEAM_COLORS[team]
    else:
        status, color = f"{TEAM_NAMES[g.turn]} ist dran", TEAM_COLORS[g.turn]
    text(p, QRectF(0, board.bottom() + h * 0.02, w, h * 0.06), status, h * 0.045, color, True)
    if not g.result:  # Bedenkzeit
        part = g.time_left(now) / max(0.1, g.think)
        time_bar(c, QRectF(board.x(), board.bottom() + h * 0.085, board.width(), h * 0.012), part)
        # leuchtender Rand in der Farbe des Teams, das dran ist
        glow = 0.25 + 0.15 * math.sin(now * 4)
        p.setPen(QPen(qc(TEAM_COLORS[g.turn], glow), max(4, side * 0.02)))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(board.adjusted(-side * 0.03, -side * 0.03, side * 0.03, side * 0.03), 18, 18)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(255, 255, 255, 12))
    p.drawRoundedRect(board, 16, 16)
    grid = QPen(QColor(255, 255, 255, 70), max(3, side * 0.012))
    grid.setCapStyle(Qt.RoundCap)
    p.setPen(grid)
    for k in (1, 2):
        p.drawLine(QPointF(board.x() + k * cs, board.y() + cs * 0.12), QPointF(board.x() + k * cs, board.bottom() - cs * 0.12))
        p.drawLine(QPointF(board.x() + cs * 0.12, board.y() + k * cs), QPointF(board.right() - cs * 0.12, board.y() + k * cs))
    # Stimmen des Teams, das gerade dran ist (kleine Punkte im Feld)
    counts: dict[int, list] = {}
    for pid, cell in g.votes.items():
        counts.setdefault(cell, []).append(pid)
    for i in range(9):
        cell = QRectF(board.x() + (i % 3) * cs, board.y() + (i // 3) * cs, cs, cs)
        mark = g.cells[i]
        if mark:
            born = c.fx.born.get(f"ttt{i}")
            grow = ease_back((now - born) / 0.35) if born is not None and now - born < 0.35 else 1.0
            _mark(p, cell, mark, max(0.05, grow))
        elif i in counts and not g.result:
            for k, pid in enumerate(counts[i][:6]):
                p.setPen(Qt.NoPen)
                p.setBrush(qc(color_of(c, pid)))
                r = cs * 0.07
                p.drawEllipse(QPointF(cell.x() + cs * 0.2 + k * r * 2.6, cell.bottom() - cs * 0.16), r, r)
            _mark(p, cell, "X" if g.turn == 0 else "O", 0.6, 0.18 + 0.1 * len(counts[i]))
    if g.line:  # Gewinnlinie
        born = c.fx.born.get("tttline", now)
        part = min(1.0, (now - born) / 0.4)
        a, b = g.line[0], g.line[2]

        def center(i):
            return QPointF(board.x() + (i % 3 + 0.5) * cs, board.y() + (i // 3 + 0.5) * cs)

        pa, pb = center(a), center(b)
        end = QPointF(pa.x() + (pb.x() - pa.x()) * part, pa.y() + (pb.y() - pa.y()) * part)
        pen = QPen(QColor("#ffffff"), max(6, side * 0.03))
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        p.drawLine(pa, end)
    # Teams am Rand
    for team in (0, 1):
        members = [pid for pid in g.players if g.team_of(pid) == team]
        x = m if team == 0 else w - m - w * 0.2
        for k, pid in enumerate(members[:8]):
            voted = pid in g.votes and g.turn == team and not g.result
            chip(p, QRectF(x, h * 0.2 + k * h * 0.07, w * 0.2, h * 0.058), name_of(c, pid), color_of(c, pid),
                 "✓" if voted else "")
        if not members:
            text(p, QRectF(x, h * 0.2, w * 0.2, h * 0.06), "PC spielt", h * 0.03, MUTED)


DRAW = {"simon": simon, "pong": pong, "ballon": ballon, "schlangen": schlangen, "rennen": rennen, "ssp": ssp,
        "tictactoe": tictactoe}
