"""Design-Karten für Monitor 2: auffällig gestaltet, für alles nutzbar (Party, Stream, Präsentation, Gaming …).

Neon-Schild, Glitch, Synthwave, Poster, Minimal, Spotlight, Now Playing, LIVE, Versus, Link-Karte (QR-Code),
Coming soon, Glas-Karte. Alles gezeichnet und animiert – ohne Bilddateien, passend zu jeder Monitorgröße.
"""

from __future__ import annotations

import math
import random
import time

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetricsF,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
)

CARD_DESIGNS: dict[str, tuple[str, str, str, str, str]] = {
    "neon": ("Neon-Schild", "Leuchtende Neonschrift mit Flackern", "OPEN", "Late Night Session", "#ff2bd6"),
    "glitch": ("Glitch", "Cyberpunk-Titel mit Farbverschiebung", "SYSTEM ONLINE", "Willkommen im Netz", "#22d3ee"),
    "synthwave": ("Synthwave", "80er-Sonnenuntergang mit Raster", "RETRO NIGHT", "Press start to continue",
                  "#f472b6"),
    "poster": ("Poster", "Riesige Wörter, harte Kontraste", "BIG NEWS TODAY", "Alle Infos gleich hier", "#facc15"),
    "minimal": ("Minimal", "Viel Weißraum, eine klare Aussage", "Weniger ist mehr.", "— Kapitel 1", "#e5e7eb"),
    "spotlight": ("Spotlight", "Wandernder Scheinwerfer auf dem Titel", "Bühne frei", "für den nächsten Act",
                  "#fde68a"),
    "nowplaying": ("Now Playing", "Musik-Karte mit Cover und Equalizer", "Midnight City", "M83", "#8b5cf6"),
    "live": ("LIVE", "Stream-Overlay mit Uhr und Titel", "Wir sind live!", "Gleich geht's los", "#ef4444"),
    "versus": ("Versus", "Duell-Bildschirm: links gegen rechts", "Team Nova", "Team Blaze", "#3b82f6"),
    "linkkarte": ("Link-Karte", "Titel und Link mit QR-Code zum Scannen", "Schau vorbei",
                  "https://example.com", "#10b981"),
    "comingsoon": ("Coming soon", "Ankündigung mit pulsierenden Punkten", "Bald verfügbar", "Stay tuned",
                   "#f97316"),
    "glas": ("Glas-Karte", "Milchglas-Karte über fließenden Farben", "Hallo zusammen", "Schön, dass du da bist",
             "#6366f1"),
}
CARD_TIMED = {"neon": 50, "glitch": 50, "synthwave": 33, "spotlight": 33, "nowplaying": 50, "live": 500,
              "versus": 50, "comingsoon": 50, "glas": 33, "poster": 1000, "minimal": 1000, "linkkarte": 1000}
CARD_LABELS = {"nowplaying": ("Song:", "Künstler:"), "versus": ("Links:", "Rechts:"),
               "linkkarte": ("Titel:", "Link (wird zum QR-Code):"), "poster": ("Wörter:", "Text unten:")}


def _font(px: float, bold: bool = True, family: str | None = None, italic: bool = False) -> QFont:
    f = QFont(family) if family else QFont()
    f.setPixelSize(max(6, int(px)))
    f.setBold(bold)
    f.setItalic(italic)
    return f


def _fit(text: str, rect: QRectF, px: float, bold=True, flags=Qt.AlignCenter | Qt.TextWordWrap, family=None,
         spacing: float = 0.0) -> QFont:
    while px > 8:
        f = _font(px, bold, family)
        if spacing:
            f.setLetterSpacing(QFont.PercentageSpacing, 100 + spacing)
        r = QFontMetricsF(f).boundingRect(rect, int(flags), text)
        if r.height() <= rect.height() and r.width() <= rect.width() + 1:
            return f
        px *= 0.93
    return _font(8, bold, family)


def _draw(p: QPainter, rect: QRectF, text: str, font: QFont, color: QColor, flags=Qt.AlignCenter | Qt.TextWordWrap):
    p.setFont(font)
    p.setPen(color)
    p.drawText(rect, int(flags), text)


def _glow_text(p, rect, text, font, color: QColor, layers=6, spread=1.0, flags=Qt.AlignCenter | Qt.TextWordWrap):
    """Leuchtschrift: mehrere verschobene, halbdurchsichtige Kopien, dann der helle Kern."""
    for i in range(layers, 0, -1):
        c = QColor(color)
        c.setAlphaF(0.06 * (layers - i + 1) / layers + 0.02)
        d = i * spread
        for dx, dy in ((d, 0), (-d, 0), (0, d), (0, -d)):
            _draw(p, rect.translated(dx, dy), text, font, c, flags)
    _draw(p, rect, text, font, color.lighter(150), flags)


# =========================================================================== Karten
def c_neon(p, w, h, cfg, t, color, u):
    p.fillRect(0, 0, w, h, QColor("#07030d"))
    # Ziegelwand angedeutet
    p.setPen(QPen(QColor(255, 255, 255, 10), max(1.0, u * 0.1)))
    bh = h / 14
    for row in range(15):
        y = row * bh
        p.drawLine(QPointF(0, y), QPointF(w, y))
        off = (row % 2) * bh
        x = off
        while x < w:
            p.drawLine(QPointF(x, y), QPointF(x, y + bh))
            x += bh * 2
    rng = random.Random(int(t * 12))
    flicker = 0.35 if rng.random() < 0.04 else 1.0  # ab und zu kurz flackern
    col = QColor(color)
    col.setAlphaF(flicker)
    rect = QRectF(w * 0.08, h * 0.2, w * 0.84, h * 0.4)
    font = _fit(cfg["title"], rect, u * 14, family="Sans Serif")
    halo = QRadialGradient(QPointF(w / 2, h * 0.4), w * 0.5)
    hc = QColor(color)
    hc.setAlpha(int(50 * flicker))
    halo.setColorAt(0, hc)
    halo.setColorAt(1, QColor(0, 0, 0, 0))
    p.fillRect(0, 0, w, h, halo)
    _glow_text(p, rect, cfg["title"], font, col, 8, u * 0.25)
    sub = QColor("#67e8f9")
    _glow_text(p, QRectF(w * 0.1, h * 0.64, w * 0.8, h * 0.14), cfg["text"],
               _fit(cfg["text"], QRectF(w * 0.1, h * 0.64, w * 0.8, h * 0.14), u * 4.5, bold=False), sub, 5, u * 0.15)


def c_glitch(p, w, h, cfg, t, color, u):
    p.fillRect(0, 0, w, h, QColor("#030712"))
    # Scanlines
    p.setPen(QPen(QColor(255, 255, 255, 12), 1))
    y = 0.0
    while y < h:
        p.drawLine(QPointF(0, y), QPointF(w, y))
        y += max(2.0, u * 0.35)
    rect = QRectF(w * 0.06, h * 0.26, w * 0.88, h * 0.34)
    font = _fit(cfg["title"], rect, u * 12, family="Monospace", spacing=6)
    rng = random.Random(int(t * 8))
    burst = rng.random() < 0.18
    shift = u * (1.2 if burst else 0.4) * math.sin(t * 7)
    p.setCompositionMode(QPainter.CompositionMode_Plus)
    _draw(p, rect.translated(-shift, 0), cfg["title"], font, QColor(255, 0, 80, 200))
    _draw(p, rect.translated(shift, 0), cfg["title"], font, QColor(0, 220, 255, 200))
    p.setCompositionMode(QPainter.CompositionMode_SourceOver)
    _draw(p, rect, cfg["title"], font, QColor("#f8fafc"))
    if burst:  # Bildstörung: verschobene Streifen
        for _ in range(4):
            sy = rng.uniform(rect.top(), rect.bottom())
            sh = rng.uniform(u * 0.5, u * 2)
            strip = QRectF(0, sy, w, sh)
            p.save()
            p.setClipRect(strip)
            _draw(p, rect.translated(rng.uniform(-u * 4, u * 4), 0), cfg["title"], font, QColor(color))
            p.restore()
    _draw(p, QRectF(w * 0.1, h * 0.66, w * 0.8, h * 0.1), "> " + cfg["text"] + ("_" if int(t * 2) % 2 else " "),
          _font(u * 3, False, "Monospace"), QColor(color))


def c_synthwave(p, w, h, cfg, t, color, u):
    sky = QLinearGradient(0, 0, 0, h * 0.6)
    sky.setColorAt(0, QColor("#12002b"))
    sky.setColorAt(1, QColor("#5b1070"))
    p.fillRect(QRectF(0, 0, w, h * 0.6), sky)
    # Sonne mit Streifen
    c = QPointF(w / 2, h * 0.5)
    r = h * 0.28
    sun = QLinearGradient(0, c.y() - r, 0, c.y() + r)
    sun.setColorAt(0, QColor("#ffd319"))
    sun.setColorAt(1, QColor("#ff2975"))
    p.save()
    clip = QPainterPath()
    clip.addRect(QRectF(0, 0, w, h * 0.6))
    p.setClipPath(clip)
    p.setPen(Qt.NoPen)
    p.setBrush(sun)
    p.drawEllipse(c, r, r)
    p.setBrush(QColor("#2a0a4a"))
    for i in range(6):
        y = c.y() + r * (0.05 + i * 0.16)
        p.drawRect(QRectF(c.x() - r, y, 2 * r, r * 0.02 * (i + 1)))
    p.restore()
    # Boden mit Raster, das auf einen zukommt
    p.fillRect(QRectF(0, h * 0.6, w, h * 0.4), QColor("#0b0014"))
    p.setPen(QPen(QColor(color), max(1.0, u * 0.18)))
    horizon = h * 0.6
    for i in range(-14, 15):
        p.drawLine(QPointF(w / 2 + i * u * 1.5, horizon), QPointF(w / 2 + i * u * 14, h))
    phase = (t * 0.5) % 1.0
    for i in range(12):
        z = (i + phase) / 12
        y = horizon + (h - horizon) * (z ** 2.2)
        p.drawLine(QPointF(0, y), QPointF(w, y))
    title_rect = QRectF(w * 0.05, h * 0.05, w * 0.9, h * 0.2)
    one_line = Qt.AlignCenter  # immer eine Zeile – wird kleiner statt umzubrechen
    font = _fit(cfg["title"], title_rect, u * 11, flags=one_line, spacing=4)
    font.setItalic(True)
    grad = QLinearGradient(0, title_rect.top(), 0, title_rect.bottom())
    grad.setColorAt(0, QColor("#fef08a"))
    grad.setColorAt(1, QColor("#fb7185"))
    _glow_text(p, title_rect, cfg["title"], font, QColor("#ff2975"), 5, u * 0.2, one_line)
    p.setPen(QPen(grad, 1))
    p.setFont(font)
    p.drawText(title_rect, int(one_line), cfg["title"])
    _draw(p, QRectF(0, h * 0.25, w, h * 0.06), cfg["text"].upper(), _font(u * 2.2, True), QColor("#67e8f9"))


def c_poster(p, w, h, cfg, t, color, u):
    p.fillRect(0, 0, w, h, QColor("#0a0a0a"))
    words = cfg["title"].split() or [" "]  # jedes Wort eine Zeile
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(color))
    p.drawRect(QRectF(w * 0.62, 0, w * 0.38, h))
    row = h * 0.8 / max(1, len(words))
    for i, word in enumerate(words):
        rect = QRectF(w * 0.05, h * 0.06 + i * row, w * 0.9, row)
        f = _fit(word.upper(), rect, row * 1.1, flags=Qt.AlignLeft | Qt.AlignVCenter)
        # Wort über die Farbfläche: dort schwarz, sonst weiß
        p.save()
        p.setClipRect(QRectF(0, 0, w * 0.62, h))
        _draw(p, rect, word.upper(), f, QColor("#fafafa"), Qt.AlignLeft | Qt.AlignVCenter)
        p.restore()
        p.save()
        p.setClipRect(QRectF(w * 0.62, 0, w * 0.38, h))
        _draw(p, rect, word.upper(), f, QColor("#0a0a0a"), Qt.AlignLeft | Qt.AlignVCenter)
        p.restore()
    _draw(p, QRectF(w * 0.05, h * 0.88, w * 0.55, h * 0.08), cfg["text"], _font(u * 2.4, False), QColor("#a3a3a3"),
          Qt.AlignLeft | Qt.AlignVCenter)
    _draw(p, QRectF(w * 0.64, h * 0.88, w * 0.32, h * 0.08), time.strftime("%d.%m.%Y"), _font(u * 2.4, True),
          QColor("#0a0a0a"), Qt.AlignRight | Qt.AlignVCenter)


def c_minimal(p, w, h, cfg, t, color, u):
    p.fillRect(0, 0, w, h, QColor("#f5f5f4"))
    ink = QColor("#1c1917")
    p.setPen(QPen(ink, max(1.0, u * 0.12)))
    p.drawLine(QPointF(w * 0.08, h * 0.12), QPointF(w * 0.92, h * 0.12))
    p.drawLine(QPointF(w * 0.08, h * 0.88), QPointF(w * 0.92, h * 0.88))
    _draw(p, QRectF(w * 0.08, h * 0.04, w * 0.84, h * 0.07), time.strftime("%H:%M"), _font(u * 1.6, False), ink,
          Qt.AlignRight | Qt.AlignVCenter)
    rect = QRectF(w * 0.08, h * 0.2, w * 0.84, h * 0.55)
    _draw(p, rect, cfg["title"], _fit(cfg["title"], rect, u * 9, flags=Qt.AlignLeft | Qt.AlignVCenter | Qt.TextWordWrap),
          ink, Qt.AlignLeft | Qt.AlignVCenter | Qt.TextWordWrap)
    _draw(p, QRectF(w * 0.08, h * 0.89, w * 0.84, h * 0.07), cfg["text"], _font(u * 1.8, False), QColor("#78716c"),
          Qt.AlignLeft | Qt.AlignVCenter)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(color) if QColor(color).lightness() < 200 else QColor("#ef4444"))
    p.drawEllipse(QPointF(w * 0.9, h * 0.8), u * 0.8, u * 0.8)


def c_spotlight(p, w, h, cfg, t, color, u):
    p.fillRect(0, 0, w, h, QColor("#050505"))
    x = w * (0.5 + 0.3 * math.sin(t * 0.6))
    y = h * (0.45 + 0.08 * math.sin(t * 0.9))
    beam = QPainterPath(QPointF(w * 0.5, -h * 0.1))
    beam.lineTo(x - w * 0.2, y + h * 0.3)
    beam.lineTo(x + w * 0.2, y + h * 0.3)
    beam.closeSubpath()
    bg = QLinearGradient(w * 0.5, 0, x, y)
    bc = QColor(color)
    bc.setAlpha(10)
    bg.setColorAt(0, bc)
    bc2 = QColor(color)
    bc2.setAlpha(45)
    bg.setColorAt(1, bc2)
    p.fillPath(beam, bg)
    spot = QRadialGradient(QPointF(x, y), w * 0.28)
    sc = QColor(color)
    sc.setAlpha(140)
    spot.setColorAt(0, sc)
    spot.setColorAt(1, QColor(0, 0, 0, 0))
    p.fillRect(0, 0, w, h, spot)
    rect = QRectF(w * 0.08, h * 0.3, w * 0.84, h * 0.3)
    font = _fit(cfg["title"], rect, u * 11)
    # Text nur dort hell, wo das Licht ist
    p.save()
    _draw(p, rect, cfg["title"], font, QColor(255, 255, 255, 40))
    clip = QPainterPath()
    clip.addEllipse(QPointF(x, y), w * 0.24, w * 0.24)
    p.setClipPath(clip)
    _draw(p, rect, cfg["title"], font, QColor("#ffffff"))
    p.restore()
    _draw(p, QRectF(w * 0.1, h * 0.66, w * 0.8, h * 0.1), cfg["text"], _font(u * 3, False), QColor(255, 255, 255, 170))


def c_nowplaying(p, w, h, cfg, t, color, u):
    base = QColor(color)
    bg = QLinearGradient(0, 0, w, h)
    bg.setColorAt(0, base.darker(260))
    bg.setColorAt(1, QColor("#050508"))
    p.fillRect(0, 0, w, h, bg)
    side = min(h * 0.56, w * 0.34)
    cover = QRectF(w * 0.1, (h - side) / 2 - h * 0.04, side, side)
    g = QLinearGradient(cover.topLeft(), cover.bottomRight())
    g.setColorAt(0, base.lighter(140))
    g.setColorAt(1, QColor.fromHsvF((base.hsvHueF() + 0.15) % 1.0, 0.8, 0.6))
    p.setPen(Qt.NoPen)
    p.setBrush(g)
    p.drawRoundedRect(cover, u * 2, u * 2)
    p.setBrush(QColor(0, 0, 0, 60))  # Schallplatte angedeutet
    p.drawEllipse(cover.center(), side * 0.3, side * 0.3)
    p.setBrush(QColor(255, 255, 255, 200))
    p.drawEllipse(cover.center(), side * 0.04, side * 0.04)
    left = cover.right() + w * 0.05
    width = w * 0.9 - left
    _draw(p, QRectF(left, cover.top(), width, h * 0.07), "NOW PLAYING", _font(u * 1.8, True), QColor(base.lighter(160)),
          Qt.AlignLeft | Qt.AlignVCenter)
    title_r = QRectF(left, cover.top() + h * 0.08, width, h * 0.2)
    _draw(p, title_r, cfg["title"], _fit(cfg["title"], title_r, u * 6.5, flags=Qt.AlignLeft | Qt.AlignVCenter | Qt.TextWordWrap),
          QColor("#ffffff"), Qt.AlignLeft | Qt.AlignVCenter | Qt.TextWordWrap)
    _draw(p, QRectF(left, title_r.bottom(), width, h * 0.08), cfg["text"], _font(u * 3, False), QColor(255, 255, 255, 170),
          Qt.AlignLeft | Qt.AlignVCenter)
    # Equalizer
    bars = 24
    bw = width / bars
    eq_bottom = cover.bottom() - h * 0.1
    for i in range(bars):
        level = 0.25 + 0.75 * abs(math.sin(t * (2.2 + i * 0.37) + i * 1.3)) * (0.6 + 0.4 * math.sin(t * 1.1 + i))
        bh = h * 0.12 * max(0.1, level)
        p.setBrush(base.lighter(130))
        p.drawRoundedRect(QRectF(left + i * bw, eq_bottom - bh, bw * 0.6, bh), bw * 0.2, bw * 0.2)
    # Fortschritt
    length = 214.0
    pos = (t % length)
    bar = QRectF(left, cover.bottom() - h * 0.04, width, u * 0.6)
    p.setBrush(QColor(255, 255, 255, 50))
    p.drawRoundedRect(bar, bar.height() / 2, bar.height() / 2)
    p.setBrush(QColor("#ffffff"))
    p.drawRoundedRect(QRectF(bar.left(), bar.top(), bar.width() * pos / length, bar.height()), bar.height() / 2,
                      bar.height() / 2)
    fmt = lambda s: f"{int(s) // 60}:{int(s) % 60:02d}"  # noqa: E731
    small = _font(u * 1.6, False)
    _draw(p, QRectF(left, bar.bottom() + u * 0.5, width, u * 3), fmt(pos), small, QColor(255, 255, 255, 150),
          Qt.AlignLeft | Qt.AlignVCenter)
    _draw(p, QRectF(left, bar.bottom() + u * 0.5, width, u * 3), fmt(length), small, QColor(255, 255, 255, 150),
          Qt.AlignRight | Qt.AlignVCenter)


def c_live(p, w, h, cfg, t, color, u):
    bg = QLinearGradient(0, 0, w, h)
    bg.setColorAt(0, QColor("#0f172a"))
    bg.setColorAt(1, QColor("#020617"))
    p.fillRect(0, 0, w, h, bg)
    pill = QRectF(w * 0.05, h * 0.07, u * 12, u * 4.2)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(color))
    p.drawRoundedRect(pill, pill.height() / 2, pill.height() / 2)
    blink = int(t * 2) % 2 == 0
    p.setBrush(QColor("#ffffff") if blink else QColor(255, 255, 255, 90))
    p.drawEllipse(QPointF(pill.left() + u * 2.2, pill.center().y()), u * 0.8, u * 0.8)
    _draw(p, pill.adjusted(u * 3.5, 0, 0, 0), "LIVE", _font(u * 2.3, True), QColor("#ffffff"),
          Qt.AlignLeft | Qt.AlignVCenter)
    _draw(p, QRectF(w * 0.6, h * 0.07, w * 0.35, pill.height()), time.strftime("%H:%M"), _font(u * 2.6, True),
          QColor(255, 255, 255, 200), Qt.AlignRight | Qt.AlignVCenter)
    rect = QRectF(w * 0.05, h * 0.62, w * 0.9, h * 0.16)
    _draw(p, rect, cfg["title"], _fit(cfg["title"], rect, u * 7, flags=Qt.AlignLeft | Qt.AlignVCenter),
          QColor("#ffffff"), Qt.AlignLeft | Qt.AlignVCenter)
    p.setBrush(QColor(color))
    p.drawRect(QRectF(w * 0.05, h * 0.79, u * 8, u * 0.5))
    _draw(p, QRectF(w * 0.05, h * 0.81, w * 0.9, h * 0.08), cfg["text"], _font(u * 3, False), QColor(255, 255, 255, 170),
          Qt.AlignLeft | Qt.AlignVCenter)


def c_versus(p, w, h, cfg, t, color, u):
    left_c, right_c = QColor(color), QColor("#ef4444")
    shake = u * 0.3 * math.sin(t * 20) if (t % 3) < 0.25 else 0
    lp = QPainterPath(QPointF(0, 0))
    lp.lineTo(w * 0.56, 0)
    lp.lineTo(w * 0.44, h)
    lp.lineTo(0, h)
    lp.closeSubpath()
    rp = QPainterPath(QPointF(w * 0.56, 0))
    rp.lineTo(w, 0)
    rp.lineTo(w, h)
    rp.lineTo(w * 0.44, h)
    rp.closeSubpath()
    for path, col in ((lp, left_c), (rp, right_c)):
        g = QLinearGradient(0, 0, w, h)
        g.setColorAt(0, col.darker(170))
        g.setColorAt(1, col.darker(300))
        p.fillPath(path, g)
    p.setPen(QPen(QColor("#ffffff"), u * 0.6))
    p.drawLine(QPointF(w * 0.56, 0), QPointF(w * 0.44, h))
    lr = QRectF(w * 0.03, h * 0.35, w * 0.42, h * 0.3)
    rr = QRectF(w * 0.55, h * 0.35, w * 0.42, h * 0.3)
    _draw(p, lr, cfg["title"], _fit(cfg["title"], lr, u * 7), QColor("#ffffff"))
    _draw(p, rr, cfg["text"], _fit(cfg["text"], rr, u * 7), QColor("#ffffff"))
    vs = QRectF(w / 2 - u * 9 + shake, h / 2 - u * 7, u * 18, u * 14)
    _glow_text(p, vs, "VS", _font(u * 11, True), QColor("#facc15"), 6, u * 0.3, Qt.AlignCenter)


def c_linkkarte(p, w, h, cfg, t, color, u):
    from .sources import qr_image

    base = QColor(color)
    bg = QLinearGradient(0, 0, w, h)
    bg.setColorAt(0, base.darker(280))
    bg.setColorAt(1, QColor("#030712"))
    p.fillRect(0, 0, w, h, bg)
    side = min(h * 0.6, w * 0.34)
    qr_rect = QRectF(w * 0.58, (h - side) / 2, side, side)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#ffffff"))
    p.drawRoundedRect(qr_rect.adjusted(-u * 1.5, -u * 1.5, u * 1.5, u * 1.5), u * 2, u * 2)
    link = cfg["text"].strip() or " "
    p.setRenderHint(QPainter.SmoothPixmapTransform, False)
    p.drawImage(qr_rect, qr_image(link, border=1))
    p.setRenderHint(QPainter.SmoothPixmapTransform, True)
    left = QRectF(w * 0.07, h * 0.24, w * 0.46, h * 0.52)
    _draw(p, QRectF(left.left(), left.top(), left.width(), h * 0.3), cfg["title"],
          _fit(cfg["title"], QRectF(left.left(), left.top(), left.width(), h * 0.3), u * 7,
               flags=Qt.AlignLeft | Qt.AlignBottom | Qt.TextWordWrap), QColor("#ffffff"),
          Qt.AlignLeft | Qt.AlignBottom | Qt.TextWordWrap)
    shown = link.replace("https://", "").replace("http://", "").rstrip("/")
    lr = QRectF(left.left(), left.top() + h * 0.33, left.width(), h * 0.09)
    _draw(p, lr, shown, _fit(shown, lr, u * 3.2, flags=Qt.AlignLeft | Qt.AlignVCenter), base.lighter(150),
          Qt.AlignLeft | Qt.AlignVCenter)
    _draw(p, QRectF(left.left(), left.top() + h * 0.44, left.width(), h * 0.08), "QR-Code mit der Handy-Kamera scannen",
          _font(u * 1.8, False), QColor(255, 255, 255, 140), Qt.AlignLeft | Qt.AlignVCenter)


def c_comingsoon(p, w, h, cfg, t, color, u):
    p.fillRect(0, 0, w, h, QColor("#09090b"))
    base = QColor(color)
    for i in range(3):  # weiche Farbflecken
        g = QRadialGradient(QPointF(w * (0.2 + 0.3 * i + 0.05 * math.sin(t * 0.4 + i)), h * (0.3 + 0.2 * (i % 2))),
                            w * 0.35)
        c = QColor.fromHsvF((base.hsvHueF() + i * 0.08) % 1.0, 0.8, 0.9)
        c.setAlpha(45)
        g.setColorAt(0, c)
        g.setColorAt(1, QColor(0, 0, 0, 0))
        p.fillRect(0, 0, w, h, g)
    rect = QRectF(w * 0.08, h * 0.28, w * 0.84, h * 0.28)
    _draw(p, rect, cfg["title"], _fit(cfg["title"], rect, u * 10), QColor("#fafafa"))
    for i in range(3):
        a = 0.3 + 0.7 * max(0.0, math.sin(t * 4 - i * 0.8))
        c = QColor(base)
        c.setAlphaF(a)
        p.setPen(Qt.NoPen)
        p.setBrush(c)
        p.drawEllipse(QPointF(w / 2 + (i - 1) * u * 4, h * 0.64), u * 1.1, u * 1.1)
    _draw(p, QRectF(0, h * 0.72, w, h * 0.08), cfg["text"].upper(), _font(u * 2.2, True), QColor(255, 255, 255, 150))


def c_glas(p, w, h, cfg, t, color, u):
    base = QColor(color)
    p.fillRect(0, 0, w, h, QColor("#0b0b14"))
    for i in range(4):
        cx = w * (0.5 + 0.35 * math.sin(t * 0.3 + i * 1.7))
        cy = h * (0.5 + 0.35 * math.cos(t * 0.25 + i * 2.1))
        g = QRadialGradient(QPointF(cx, cy), w * 0.3)
        c = QColor.fromHsvF((base.hsvHueF() + i * 0.12) % 1.0, 0.75, 1.0)
        c.setAlpha(170)
        g.setColorAt(0, c)
        g.setColorAt(1, QColor(0, 0, 0, 0))
        p.fillRect(0, 0, w, h, g)
    card = QRectF(w * 0.14, h * 0.2, w * 0.72, h * 0.6)
    p.setPen(QPen(QColor(255, 255, 255, 90), max(1.0, u * 0.15)))
    p.setBrush(QColor(255, 255, 255, 38))
    p.drawRoundedRect(card, u * 3, u * 3)
    shine = QLinearGradient(card.topLeft(), card.bottomLeft())
    shine.setColorAt(0, QColor(255, 255, 255, 40))
    shine.setColorAt(0.5, QColor(255, 255, 255, 0))
    p.setPen(Qt.NoPen)
    p.setBrush(shine)
    p.drawRoundedRect(card, u * 3, u * 3)
    tr = QRectF(card.left() + u * 4, card.top() + card.height() * 0.18, card.width() - u * 8, card.height() * 0.42)
    _draw(p, tr, cfg["title"], _fit(cfg["title"], tr, u * 8), QColor("#ffffff"))
    sr = QRectF(card.left() + u * 4, card.top() + card.height() * 0.64, card.width() - u * 8, card.height() * 0.2)
    _draw(p, sr, cfg["text"], _fit(cfg["text"], sr, u * 3.2, bold=False), QColor(255, 255, 255, 210))


CARD_PAINTERS = {
    "neon": c_neon, "glitch": c_glitch, "synthwave": c_synthwave, "poster": c_poster, "minimal": c_minimal,
    "spotlight": c_spotlight, "nowplaying": c_nowplaying, "live": c_live, "versus": c_versus,
    "linkkarte": c_linkkarte, "comingsoon": c_comingsoon, "glas": c_glas,
}


def paint_card(p: QPainter, w: int, h: int, cfg: dict, now: float, started: float, color: QColor, unit: float) -> None:
    t = now - (started or now) + (started % 97 if started else 0)  # Animationszeit
    CARD_PAINTERS[cfg["design"]](p, w, h, {"title": cfg.get("title", ""), "text": cfg.get("text", "")}, t, color, unit)
