"""„Läuft gerade“ auf Monitor 2: Cover, Titel, Künstler, Fortschritt – vom Player des PCs (Spotify, YouTube …).

`feed()` fragt im Hintergrund-Thread ab (etwa jede Sekunde, nur solange eine Anzeige offen ist) und
führt auch Weiter/Zurück/Pause dort aus – D-Bus bzw. WinRT blockieren so nie die Oberfläche.
"""

from __future__ import annotations

import queue
import threading

from PySide6.QtCore import QObject, QRectF, Qt, QTimer, QVariantAnimation, Signal
from PySide6.QtGui import (QColor, QFont, QFontMetricsF, QImage, QLinearGradient, QPainter, QPainterPath, QPixmap,
                           QRadialGradient)
from PySide6.QtWidgets import QWidget

from . import now_playing
from .now_playing import Track, fmt_time


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
        self.feed = feed()
        self.feed.changed.connect(self._changed)
        self.feed.failed.connect(self._failed)
        self.feed.acquire()
        if self.feed.track is not None:
            self._changed(self.feed.track)

    def stop(self) -> None:
        self._tick.stop()
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
        else:
            self._tick.stop()
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
            small = self._art.scaled(18, 18, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            big = small.scaled(w, h, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            p.drawImage((w - big.width()) // 2, (h - big.height()) // 2, big)
            grad = QLinearGradient(0, 0, w, h)
            grad.setColorAt(0, QColor(0, 0, 0, 150))
            grad.setColorAt(1, QColor(0, 0, 0, 215))
            p.fillRect(0, 0, w, h, grad)
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
        note = QRectF(w / 2 - m * 0.09, h * 0.5 - m * 0.3, m * 0.18, m * 0.18)
        self._paint_note(p, note, QColor(255, 255, 255, 90))
        title = "Gerade läuft nichts" if not self.feed.problem else "„Läuft gerade“ geht hier nicht"
        sub = ("Spotify, YouTube oder eine andere App abspielen – erscheint hier automatisch."
               if not self.feed.problem else self.feed.problem)
        self._text(p, QRectF(w * 0.08, h * 0.52, w * 0.84, m * 0.1), title, m * 0.06, QColor(255, 255, 255, 230),
                   bold=True, align=Qt.AlignCenter)
        self._text(p, QRectF(w * 0.1, h * 0.52 + m * 0.11, w * 0.8, m * 0.12), sub, m * 0.03,
                   QColor(255, 255, 255, 140), align=Qt.AlignHCenter | Qt.AlignTop, wrap=True)

    def _paint_track(self, p: QPainter, w: float, h: float) -> None:
        t = self.track
        landscape = w >= h * 1.15
        if landscape:
            size = min(h * 0.62, w * 0.36)
            cover = QRectF(w * 0.08, (h - size) / 2, size, size)
            tx = cover.right() + w * 0.05
            text = QRectF(tx, cover.top(), w * 0.92 - tx, size)
            align = Qt.AlignLeft
        else:
            size = min(w * 0.62, h * 0.42)
            cover = QRectF((w - size) / 2, h * 0.08, size, size)
            text = QRectF(w * 0.08, cover.bottom() + h * 0.04, w * 0.84, h * 0.92 - cover.bottom() - h * 0.04)
            align = Qt.AlignHCenter
        self._paint_cover(p, cover)
        unit = size if landscape else min(w, h) * 0.9
        # Oben: Player + Zustand
        chip = (t.player.upper() if t.player else "MEDIEN") + ("  ·  LÄUFT" if t.playing else "  ·  PAUSE")
        y = text.top() + (text.height() * 0.08 if landscape else 0)
        chip_h = unit * 0.07
        self._text(p, QRectF(text.left(), y, text.width(), chip_h), chip, unit * 0.045, self._accent, bold=True,
                   align=align | Qt.AlignVCenter, spacing=1.5)
        y += chip_h * 1.25
        title_px = self._fit_px(t.title, unit * 0.14, text.width(), bold=True, minimum=unit * 0.07)
        title_h = title_px * 1.3
        self._text(p, QRectF(text.left(), y, text.width(), title_h), t.title, title_px, QColor("#ffffff"),
                   bold=True, align=align | Qt.AlignVCenter)
        y += title_h
        if t.artist:
            px = unit * 0.07
            self._text(p, QRectF(text.left(), y, text.width(), px * 1.4), t.artist, px, QColor(255, 255, 255, 215),
                       align=align | Qt.AlignVCenter)
            y += px * 1.4
        if t.album:
            px = unit * 0.05
            self._text(p, QRectF(text.left(), y, text.width(), px * 1.4), t.album, px, QColor(255, 255, 255, 140),
                       align=align | Qt.AlignVCenter)
            y += px * 1.4
        if self.show_progress and t.length > 0:
            bar_y = max(y + unit * 0.06, text.bottom() - unit * 0.12) if landscape else y + unit * 0.06
            bar_h = max(3.0, unit * 0.018)
            bar = QRectF(text.left(), bar_y, text.width(), bar_h)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255, 255, 255, 55))
            p.drawRoundedRect(bar, bar_h / 2, bar_h / 2)
            frac = max(0.0, min(1.0, t.position_now() / t.length))
            p.setBrush(self._accent)
            p.drawRoundedRect(QRectF(bar.left(), bar.top(), max(bar_h, bar.width() * frac), bar_h), bar_h / 2,
                              bar_h / 2)
            px = unit * 0.042
            times = QRectF(bar.left(), bar.bottom() + px * 0.5, bar.width(), px * 1.5)
            self._text(p, times, fmt_time(t.position_now()), px, QColor(255, 255, 255, 160),
                       align=Qt.AlignLeft | Qt.AlignVCenter)
            self._text(p, times, fmt_time(t.length), px, QColor(255, 255, 255, 160),
                       align=Qt.AlignRight | Qt.AlignVCenter)

    def _paint_cover(self, p: QPainter, rect: QRectF) -> None:
        radius = rect.width() * 0.05
        shadow = QColor(0, 0, 0, 110)
        p.setPen(Qt.NoPen)
        for i in range(3):  # weicher Schatten (drei Lagen)
            grow = rect.width() * (0.012 + i * 0.012)
            shadow.setAlpha(60 - i * 18)
            p.setBrush(shadow)
            p.drawRoundedRect(rect.adjusted(-grow, -grow * 0.2, grow, grow * 1.8), radius + grow, radius + grow)
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
            grad.setColorAt(0, self._accent.darker(160))
            grad.setColorAt(1, QColor("#111827"))
            p.fillRect(rect, grad)
            s = rect.width() * 0.36
            self._paint_note(p, QRectF(rect.center().x() - s / 2, rect.center().y() - s / 2, s, s),
                             QColor(255, 255, 255, 170))
        p.restore()
        if self.track is not None and not self.track.playing:  # Pause-Zeichen über dem Cover
            p.setBrush(QColor(0, 0, 0, 120))
            p.drawRoundedRect(rect, radius, radius)
            bw, bh = rect.width() * 0.06, rect.height() * 0.24
            c = rect.center()
            p.setBrush(QColor(255, 255, 255, 230))
            p.drawRoundedRect(QRectF(c.x() - bw * 1.6, c.y() - bh / 2, bw, bh), bw * 0.3, bw * 0.3)
            p.drawRoundedRect(QRectF(c.x() + bw * 0.6, c.y() - bh / 2, bw, bh), bw * 0.3, bw * 0.3)

    @staticmethod
    def _paint_note(p: QPainter, r: QRectF, color: QColor) -> None:
        """Einfache Musiknote (zwei Köpfe, Balken)."""
        p.save()
        p.setPen(Qt.NoPen)
        p.setBrush(color)
        head = r.width() * 0.3
        p.drawEllipse(QRectF(r.left(), r.bottom() - head * 0.8, head, head * 0.8))
        p.drawEllipse(QRectF(r.right() - head, r.bottom() - head * 1.05, head, head * 0.8))
        stem = r.width() * 0.08
        p.drawRect(QRectF(r.left() + head - stem, r.top() + r.height() * 0.18, stem, r.height() * 0.72))
        p.drawRect(QRectF(r.right() - stem, r.top(), stem, r.height() * 0.66))
        beam = QPainterPath()
        beam.moveTo(r.left() + head - stem, r.top() + r.height() * 0.18)
        beam.lineTo(r.right(), r.top())
        beam.lineTo(r.right(), r.top() + r.height() * 0.16)
        beam.lineTo(r.left() + head - stem, r.top() + r.height() * 0.34)
        beam.closeSubpath()
        p.drawPath(beam)
        p.restore()

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
