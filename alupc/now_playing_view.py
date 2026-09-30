"""„Läuft gerade“ auf Monitor 2: Cover, Titel, Künstler, Fortschritt – vom Player des PCs (Spotify, YouTube …).

`feed()` fragt im Hintergrund-Thread ab (etwa jede Sekunde, nur solange eine Anzeige offen ist) und
führt auch Weiter/Zurück/Pause dort aus – D-Bus bzw. WinRT blockieren so nie die Oberfläche.
"""

from __future__ import annotations

import queue
import threading

from PySide6.QtCore import QObject, QPointF, QRectF, Qt, QTimer, QVariantAnimation, Signal
from PySide6.QtGui import (QColor, QFont, QFontMetricsF, QImage, QLinearGradient, QPainter, QPainterPath, QPixmap,
                           QPen, QRadialGradient)
from PySide6.QtWidgets import QWidget

from . import now_playing
from .now_playing import Track, fmt_time
from .ui.icons import draw_note


class NowPlayingFeed(QObject):
    changed = Signal(object)  # Track oder None
    failed = Signal(str)

    def __init__(self):
        super().__init__()
        self.track: Track | None = None
        self.problem = ""
        self.users = 0
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._commands: queue.Queue[str] = queue.Queue()
        self._thread: threading.Thread | None = None

    def acquire(self) -> None:
        self.users += 1
        if self._thread is None or not self._thread.is_alive():
            self._stop.clear()
            self._thread = threading.Thread(target=self._run, name="alupc-now-playing", daemon=True)
            self._thread.start()

    def release(self) -> None:
        self.users = max(0, self.users - 1)
        if self.users == 0:
            self._stop.set()
            self._wake.set()

    def control(self, action: str) -> None:
        """Pause/Weiter/Zurück beim Player (auch ohne offene Anzeige)."""
        self._commands.put(action)
        if self._thread is None or not self._thread.is_alive():
            self._stop.clear()
            self._thread = threading.Thread(target=self._run, name="alupc-now-playing", daemon=True)
            self._thread.start()
        self._wake.set()

    def _run(self) -> None:
        ok, why = now_playing.available()
        if not ok:
            self.problem = why
            self.failed.emit(why)
            return
        try:
            reader = now_playing.reader()
        except Exception as exc:  # noqa: BLE001
            self.problem = str(exc)
            self.failed.emit(self.problem)
            return
        last_key = None
        try:
            while True:
                while not self._commands.empty():
                    try:
                        reader.control(self._commands.get_nowait())
                    except Exception:  # noqa: BLE001 - Player weg oder kann das nicht
                        pass
                if self._stop.is_set() and self.users == 0:
                    break
                try:
                    track = reader.read()
                    self.problem = ""
                except Exception as exc:  # noqa: BLE001
                    track = None
                    self.problem = str(exc) or type(exc).__name__
                key = None if track is None else (track.title, track.artist, track.player, track.playing,
                                                  round(track.position), track.length, track.art_key)
                if key != last_key:  # nur melden, wenn sich etwas geändert hat
                    last_key = key
                    self.track = track
                    self.changed.emit(track)
                # spielt etwas: jede Sekunde nachsehen, sonst seltener (spart Rechenzeit auf schwachen PCs)
                self._wake.wait(1.0 if track is not None and track.playing else 2.5)
                self._wake.clear()
                if self.users == 0 and self._commands.empty():
                    break
        finally:
            try:
                reader.close()
            except Exception:  # noqa: BLE001
                pass


_feed: NowPlayingFeed | None = None


def feed() -> NowPlayingFeed:
    global _feed
    if _feed is None:
        _feed = NowPlayingFeed()
    return _feed


# --------------------------------------------------------------------------- Anzeige
def _average_color(image: QImage) -> QColor:
    if image.isNull():
        return QColor("#1db954")
    c = image.scaled(1, 1, Qt.IgnoreAspectRatio, Qt.SmoothTransformation).pixelColor(0, 0)
    h, s, v, _a = c.getHsvF()
    # als Akzent gut sichtbar auf dunklem Grund: kräftig und hell genug
    return QColor.fromHsvF(max(0.0, h), min(1.0, max(0.45, s)), max(0.75, v))


class NowPlayingSource(QWidget):
    """Was der PC gerade abspielt – groß, ruhig, mit Cover als Hintergrund."""

    def __init__(self, cfg: dict | None = None, parent=None):
        super().__init__(parent)
        cfg = cfg or {}
        self.show_progress = bool(cfg.get("progress", True))
        self.track: Track | None = None
        self._art = QImage()
        self._accent = QColor("#1db954")
        self._bg_cache: tuple | None = None
        self._bg = QPixmap()
        self._fade = 1.0
        self._anim = None
        self.setAttribute(Qt.WA_OpaquePaintEvent)
        self._tick = QTimer(self, interval=1000)  # Fortschritt weiterzählen (nur beim Abspielen)
        self._tick.timeout.connect(self.update)
        self._eq_rect = None  # Equalizer-Balken: nur diese kleine Fläche oft neu zeichnen
        self._eq_timer = QTimer(self, interval=110)
        self._eq_timer.timeout.connect(lambda: self.update(self._eq_rect) if self._eq_rect is not None else None)
        self.feed = feed()
        self.feed.changed.connect(self._changed)
        self.feed.failed.connect(self._failed)
        self.feed.acquire()
        if self.feed.track is not None:
            self._changed(self.feed.track)

    def stop(self) -> None:
        self._tick.stop()
        self._eq_timer.stop()
        try:
            self.feed.changed.disconnect(self._changed)
            self.feed.failed.disconnect(self._failed)
        except (RuntimeError, TypeError):
            pass
        self.feed.release()

    def _failed(self, _text: str) -> None:
        self.update()

    def _changed(self, track) -> None:
        new_song = track is None or not track.same_song(self.track)
        old_art = self.track.art_key if self.track else None
        self.track = track
        if track is not None and track.art_key != old_art:
            img = QImage()
            if track.art:
                img.loadFromData(track.art)
            self._art = img
            self._accent = _average_color(img)
            self._bg_cache = None
        elif track is None:
            self._art = QImage()
            self._accent = QColor("#1db954")
            self._bg_cache = None
        if track is not None and track.playing:
            self._tick.start()
            self._eq_timer.start()
        else:
            self._tick.stop()
            self._eq_timer.stop()
        if new_song:
            self._start_fade()
        self.update()

    def _start_fade(self) -> None:
        from .ui.widgets import theme_reduced_motion

        if theme_reduced_motion() or not self.isVisible():
            self._fade = 1.0
            return
        anim = QVariantAnimation(self)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setDuration(450)
        anim.valueChanged.connect(self._set_fade)
        anim.start(QVariantAnimation.DeleteWhenStopped)
        self._anim = anim

    def _set_fade(self, value) -> None:
        self._fade = float(value)
        self.update()

    # ---- Zeichnen
    def _background(self) -> QPixmap:
        key = (self.width(), self.height(), self.track.art_key if self.track else None)
        if key == self._bg_cache and not self._bg.isNull():
            return self._bg
        w, h = max(1, self.width()), max(1, self.height())
        pm = QPixmap(w, h)
        p = QPainter(pm)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        if not self._art.isNull():
            # stark verkleinert und wieder vergrößert = weicher, unscharfer Hintergrund (ohne teuren Filter)
            # zweimal stark verkleinern = sehr weicher Farbverlauf ohne erkennbare Schrift/Formen vom Cover
            small = self._art.scaled(24, 24, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            small = small.scaled(5, 5, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            big = small.scaled(w, h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            p.drawImage(0, 0, big)
            grad = QLinearGradient(0, 0, w, h)
            grad.setColorAt(0, QColor(0, 0, 0, 120))
            grad.setColorAt(1, QColor(0, 0, 0, 200))
            p.fillRect(0, 0, w, h, grad)
            vignette = QRadialGradient(w / 2, h / 2, max(w, h) * 0.75)
            vignette.setColorAt(0.55, QColor(0, 0, 0, 0))
            vignette.setColorAt(1, QColor(0, 0, 0, 150))
            p.fillRect(0, 0, w, h, vignette)
        else:
            grad = QLinearGradient(0, 0, w, h)
            grad.setColorAt(0, QColor("#0f172a"))
            grad.setColorAt(1, QColor("#020617"))
            p.fillRect(0, 0, w, h, grad)
            # weiches Leuchten hinter der Mitte
            r = min(w, h) * 0.55
            glow = QRadialGradient(w / 2, h * 0.42, r)
            c = QColor(self._accent)
            c.setAlpha(55)
            glow.setColorAt(0, c)
            c.setAlpha(0)
            glow.setColorAt(1, c)
            p.fillRect(0, 0, w, h, glow)
        p.end()
        self._bg, self._bg_cache = pm, key
        return pm

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing | QPainter.SmoothPixmapTransform)
        p.drawPixmap(0, 0, self._background())
        w, h = float(self.width()), float(self.height())
        if w < 40 or h < 30:
            return
        p.setOpacity(self._fade)
        if self.track is None:
            self._paint_idle(p, w, h)
        else:
            self._paint_track(p, w, h)

    def _paint_idle(self, p: QPainter, w: float, h: float) -> None:
        m = min(w, h)
        # Note in einem weichen Kreis, darunter Text
        c = QPointF(w / 2, h * 0.4)
        r = m * 0.15
        ring = QRadialGradient(c, r * 1.6)
        glow = QColor(self._accent)
        glow.setAlpha(60)
        ring.setColorAt(0, glow)
        glow.setAlpha(0)
        ring.setColorAt(1, glow)
        p.setPen(Qt.NoPen)
        p.setBrush(ring)
        p.drawEllipse(c, r * 1.6, r * 1.6)
        p.setBrush(QColor(255, 255, 255, 18))
        p.setPen(QPen(QColor(255, 255, 255, 40), max(1.5, m * 0.003)))
        p.drawEllipse(c, r, r)
        draw_note(p, QRectF(c.x() - r * 0.55, c.y() - r * 0.55, r * 1.1, r * 1.1), QColor(255, 255, 255, 200))
        title = "Gerade läuft nichts" if not self.feed.problem else "„Läuft gerade“ geht hier nicht"
        sub = ("Spotify, YouTube oder eine andere App abspielen – erscheint hier automatisch."
               if not self.feed.problem else self.feed.problem)
        top = c.y() + r * 1.35
        self._text(p, QRectF(w * 0.08, top, w * 0.84, m * 0.1), title, m * 0.06, QColor(255, 255, 255, 235),
                   bold=True, align=Qt.AlignCenter)
        self._text(p, QRectF(w * 0.12, top + m * 0.11, w * 0.76, m * 0.12), sub, m * 0.032,
                   QColor(255, 255, 255, 150), align=Qt.AlignHCenter | Qt.AlignTop, wrap=True)

    def _paint_track(self, p: QPainter, w: float, h: float) -> None:
        t = self.track
        landscape = w >= h * 1.15
        if landscape:
            size = min(h * 0.64, w * 0.38)
            cover = QRectF(w * 0.08, (h - size) / 2, size, size)
            tx = cover.right() + w * 0.055
            area = QRectF(tx, cover.top(), w * 0.93 - tx, size)
            align = Qt.AlignLeft
            unit = size
        else:
            size = min(w * 0.64, h * 0.42)
            cover = QRectF((w - size) / 2, h * 0.07, size, size)
            area = QRectF(w * 0.08, cover.bottom() + h * 0.04, w * 0.84, h * 0.93 - cover.bottom() - h * 0.04)
            align = Qt.AlignHCenter
            unit = min(w, h) * 0.9
        self._paint_cover(p, cover)
        # Titel darf zwei Zeilen haben; Größe so, dass er hineinpasst
        title_px = self._fit_px(t.title, unit * 0.13, area.width() * 1.9, bold=True, minimum=unit * 0.07)
        title_font = self._font(title_px, True)
        lines = self._wrap(t.title, title_font, area.width(), 2)
        chip_h = unit * 0.075
        blocks = [chip_h * 1.35, title_px * 1.22 * len(lines)]
        if t.artist:
            blocks.append(unit * 0.075 * 1.45)
        if t.album:
            blocks.append(unit * 0.052 * 1.5)
        progress = self.show_progress and t.length > 0
        if progress:
            blocks.append(unit * 0.16)
        total = sum(blocks)
        y = area.top() + max(0.0, (area.height() - total) / 2) if landscape else area.top()
        # Zeile oben: Equalizer + Player + Zustand
        eq = QRectF(area.left(), y + chip_h * 0.15, chip_h * 0.9, chip_h * 0.7)
        if align == Qt.AlignHCenter:
            chip_text = (t.player.upper() if t.player else "MEDIEN") + ("  ·  LÄUFT" if t.playing else "  ·  PAUSE")
            cw = QFontMetricsF(self._font(unit * 0.045, True, 1.5)).horizontalAdvance(chip_text)
            eq.moveLeft(area.center().x() - (cw + eq.width() * 1.4) / 2)
        self._paint_eq(p, eq, t.playing)
        self._eq_rect = eq.adjusted(-2, -2, 2, 2).toAlignedRect()
        chip = (t.player.upper() if t.player else "MEDIEN") + ("  ·  LÄUFT" if t.playing else "  ·  PAUSE")
        chip_rect = QRectF(eq.right() + eq.width() * 0.4, y, area.right() - eq.right(), chip_h)
        self._text(p, chip_rect, chip, unit * 0.045, self._accent, bold=True, align=Qt.AlignLeft | Qt.AlignVCenter,
                   spacing=1.5)
        y += chip_h * 1.35
        for line in lines:
            self._text(p, QRectF(area.left(), y, area.width(), title_px * 1.22), line, title_px, QColor("#ffffff"),
                       bold=True, align=align | Qt.AlignVCenter)
            y += title_px * 1.22
        if t.artist:
            px = unit * 0.075
            self._text(p, QRectF(area.left(), y, area.width(), px * 1.45), t.artist, px, QColor(255, 255, 255, 220),
                       align=align | Qt.AlignVCenter)
            y += px * 1.45
        if t.album:
            px = unit * 0.052
            self._text(p, QRectF(area.left(), y, area.width(), px * 1.5), t.album, px, QColor(255, 255, 255, 140),
                       align=align | Qt.AlignVCenter)
            y += px * 1.5
        if progress:
            y += unit * 0.05
            bar_h = max(4.0, unit * 0.022)
            bar = QRectF(area.left(), y, area.width(), bar_h)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255, 255, 255, 50))
            p.drawRoundedRect(bar, bar_h / 2, bar_h / 2)
            frac = max(0.0, min(1.0, t.position_now() / t.length))
            done = QRectF(bar.left(), bar.top(), max(bar_h, bar.width() * frac), bar_h)
            grad = QLinearGradient(done.topLeft(), done.topRight())
            grad.setColorAt(0, self._accent.darker(125))
            grad.setColorAt(1, self._accent)
            p.setBrush(grad)
            p.drawRoundedRect(done, bar_h / 2, bar_h / 2)
            p.setBrush(QColor("#ffffff"))  # Knopf am Ende
            p.drawEllipse(QPointF(done.right(), done.center().y()), bar_h * 1.1, bar_h * 1.1)
            px = unit * 0.042
            times = QRectF(bar.left(), bar.bottom() + px * 0.6, bar.width(), px * 1.5)
            self._text(p, times, fmt_time(t.position_now()), px, QColor(255, 255, 255, 170),
                       align=Qt.AlignLeft | Qt.AlignVCenter)
            self._text(p, times, "−" + fmt_time(max(0.0, t.length - t.position_now())), px,
                       QColor(255, 255, 255, 170), align=Qt.AlignRight | Qt.AlignVCenter)

    def _paint_eq(self, p: QPainter, rect: QRectF, playing: bool) -> None:
        """Drei hüpfende Balken, solange Musik läuft (in Pause: flach)."""
        import math
        import time as _time

        bw = rect.width() / 5
        now = _time.monotonic()
        p.save()
        p.setPen(Qt.NoPen)
        p.setBrush(self._accent)
        for i in range(3):
            level = 0.25
            if playing:
                level = 0.35 + 0.65 * abs(math.sin(now * (3.1 + i * 1.7) + i * 1.3))
            bh = max(bw, rect.height() * level)
            p.drawRoundedRect(QRectF(rect.left() + i * bw * 2, rect.bottom() - bh, bw, bh), bw / 2, bw / 2)
        p.restore()

    def _wrap(self, text: str, font: QFont, width: float, max_lines: int) -> list[str]:
        fm = QFontMetricsF(font)
        if fm.horizontalAdvance(text) <= width:
            return [text]
        words, lines, cur = text.split(), [], ""
        for word in words:
            probe = f"{cur} {word}".strip()
            if fm.horizontalAdvance(probe) <= width or not cur:
                cur = probe
            else:
                lines.append(cur)
                cur = word
                if len(lines) == max_lines - 1:
                    break
        rest = " ".join(words[len(" ".join(lines).split()):]) if len(lines) == max_lines - 1 else cur
        lines.append(fm.elidedText(rest, Qt.ElideRight, width))
        return lines[:max_lines]

    def _paint_cover(self, p: QPainter, rect: QRectF) -> None:
        radius = rect.width() * 0.045
        p.setPen(Qt.NoPen)
        for i in range(4):  # weicher Schatten (mehrere Lagen)
            grow = rect.width() * (0.01 + i * 0.014)
            p.setBrush(QColor(0, 0, 0, 55 - i * 12))
            p.drawRoundedRect(rect.adjusted(-grow, -grow * 0.1, grow, grow * 2.0), radius + grow, radius + grow)
        path = QPainterPath()
        path.addRoundedRect(rect, radius, radius)
        p.save()
        p.setClipPath(path)
        if not self._art.isNull():
            img = self._art.scaled(int(rect.width()), int(rect.height()), Qt.KeepAspectRatioByExpanding,
                                   Qt.SmoothTransformation)
            p.drawImage(QRectF(rect.left() - (img.width() - rect.width()) / 2,
                               rect.top() - (img.height() - rect.height()) / 2, img.width(), img.height()), img)
        else:
            grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
            grad.setColorAt(0, self._accent.darker(140))
            grad.setColorAt(1, QColor("#0b1020"))
            p.fillRect(rect, grad)
            if self.track is None or self.track.playing:  # in Pause steht dort der Pause-Knopf
                s = rect.width() * 0.42
                draw_note(p, QRectF(rect.center().x() - s / 2, rect.center().y() - s / 2, s, s),
                          QColor(255, 255, 255, 190))
        p.restore()
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(255, 255, 255, 30), 1.2))
        p.drawRoundedRect(rect, radius, radius)
        if self.track is not None and not self.track.playing:  # Pause-Zeichen im runden Knopf über dem Cover
            c = rect.center()
            r = rect.width() * 0.14
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(0, 0, 0, 150))
            p.drawEllipse(c, r, r)
            bw, bh = r * 0.22, r * 0.8
            p.setBrush(QColor(255, 255, 255, 235))
            p.drawRoundedRect(QRectF(c.x() - bw * 1.5, c.y() - bh / 2, bw, bh), bw * 0.35, bw * 0.35)
            p.drawRoundedRect(QRectF(c.x() + bw * 0.5, c.y() - bh / 2, bw, bh), bw * 0.35, bw * 0.35)

    @staticmethod
    def _font(px: float, bold: bool = False, spacing: float = 0.0) -> QFont:
        f = QFont()
        f.setPixelSize(max(6, int(px)))
        f.setWeight(QFont.Bold if bold else QFont.Normal)
        if spacing:
            f.setLetterSpacing(QFont.AbsoluteSpacing, spacing)
        return f

    def _fit_px(self, text: str, start: float, width: float, bold: bool, minimum: float) -> float:
        px = start
        while px > minimum and QFontMetricsF(self._font(px, bold)).horizontalAdvance(text) > width:
            px *= 0.9
        return max(minimum, px)

    def _text(self, p: QPainter, rect: QRectF, text: str, px: float, color: QColor, bold: bool = False,
              align=Qt.AlignLeft, wrap: bool = False, spacing: float = 0.0) -> None:
        font = self._font(px, bold, spacing)
        p.setFont(font)
        p.setPen(color)
        if wrap:
            p.drawText(rect, int(align) | Qt.TextWordWrap, text)
            return
        text = QFontMetricsF(font).elidedText(text, Qt.ElideRight, rect.width())
        p.drawText(rect, int(align), text)
