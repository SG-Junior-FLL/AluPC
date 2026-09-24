"""Bildschirmschoner für Monitor 2: Stile, Leerlauf-Erkennung und Steuerung."""

from __future__ import annotations

import math
import random
import shutil
import subprocess
import sys
import time

from PySide6.QtCore import QObject, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QLinearGradient, QPainter, QRadialGradient
from PySide6.QtWidgets import QWidget

from .sources import create_source, format_date_de, list_images, load_image

STYLES = {
    "uhr": "Uhr (wandert langsam – schont den Bildschirm)",
    "nachricht": "Nachricht (großer Text, kleine Uhr, optional Hintergrundbild)",
    "schweben": "Schwebender Text oder Logo",
    "diashow": "Diashow aus einem Ordner",
    "farben": "Farbverlauf (ruhige Animation)",
    "szene": "Eine eigene Szene",
}
WHEN = {
    "desktop": "Nur wenn AluPC gerade nichts zeigt (Modus Erweitern)",
    "immer": "Immer – auch über laufenden Inhalten",
}


# --------------------------------------------------------------------------- Leerlaufzeit
class IdleClock:
    """Wie lange hat niemand Maus oder Tastatur benutzt? (Sekunden oder None)"""

    def __init__(self):
        self.method = "keine"
        self._conn = None
        if sys.platform.startswith("win"):
            self.method = "windows"
        elif sys.platform.startswith("linux"):
            self.method = self._detect_linux()

    def _detect_linux(self) -> str:
        from .platform import dbus_util

        if dbus_util.HAVE_JEEPNEY:
            for name, probe in (("freedesktop", self._freedesktop), ("gnome", self._gnome)):
                try:
                    if probe() is not None:
                        return name
                except Exception:  # noqa: BLE001
                    self._close()
        if shutil.which("xprintidle"):
            return "xprintidle"
        return "keine"

    def _connection(self):
        from .platform import dbus_util

        if self._conn is None:
            self._conn = dbus_util.connect("SESSION")
        return self._conn

    def _close(self):
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:  # noqa: BLE001
                pass
            self._conn = None

    def _freedesktop(self):
        # KDE Plasma (X11 und Wayland) liefert die Leerlaufzeit in Sekunden
        from .platform import dbus_util

        (secs,) = dbus_util.call(self._connection(), "org.freedesktop.ScreenSaver", "/org/freedesktop/ScreenSaver",
                                 "org.freedesktop.ScreenSaver", "GetSessionIdleTime", timeout=2)
        return float(secs)

    def _gnome(self):
        from .platform import dbus_util

        (ms,) = dbus_util.call(self._connection(), "org.gnome.Mutter.IdleMonitor",
                               "/org/gnome/Mutter/IdleMonitor/Core", "org.gnome.Mutter.IdleMonitor",
                               "GetIdletime", timeout=2)
        return ms / 1000.0

    def _windows(self):
        import ctypes

        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint32)]

        info = LASTINPUTINFO()
        info.cbSize = ctypes.sizeof(info)
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):  # type: ignore[attr-defined]
            return None
        ctypes.windll.kernel32.GetTickCount.restype = ctypes.c_uint32  # type: ignore[attr-defined]
        now = ctypes.windll.kernel32.GetTickCount()  # type: ignore[attr-defined]
        return ((now - info.dwTime) & 0xFFFFFFFF) / 1000.0

    def _xprintidle(self):
        out = subprocess.run(["xprintidle"], capture_output=True, text=True, timeout=2).stdout
        return int(out.strip()) / 1000.0

    def seconds(self) -> float | None:
        fn = {"windows": self._windows, "freedesktop": self._freedesktop, "gnome": self._gnome,
              "xprintidle": self._xprintidle}.get(self.method)
        if fn is None:
            return None
        try:
            return fn()
        except Exception:  # noqa: BLE001
            self._close()
            return None

    def describe(self) -> str:
        return {
            "windows": "Windows meldet, wann zuletzt Maus/Tastatur benutzt wurden.",
            "freedesktop": "KDE meldet, wann zuletzt Maus/Tastatur benutzt wurden.",
            "gnome": "GNOME meldet, wann zuletzt Maus/Tastatur benutzt wurden.",
            "xprintidle": "Leerlaufzeit über xprintidle (X11).",
        }.get(self.method, "Das System meldet keine Leerlaufzeit – gezählt wird nur die Bedienung von AluPC.")


# --------------------------------------------------------------------------- Stile
class ScreensaverView(QWidget):
    """Der eigentliche Bildschirmschoner (wird über Monitor 2 gelegt)."""

    def __init__(self, cfg: dict, scene_lookup, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.style_ = cfg.get("style", "uhr")
        self.t0 = time.monotonic()
        self.child = None
        self.setAttribute(Qt.WA_OpaquePaintEvent)
        self.rng = random.Random()
        # schwebend
        self.pos = QPointF(80, 60)
        self.vel = QPointF(1.6, 1.2)
        self.logo = load_image(cfg["image"]) if cfg.get("image") else None
        if self.logo is not None and self.logo.isNull():
            self.logo = None
        # Diashow
        self.images: list[str] = []
        self.index = -1
        self.current = None
        self.previous = None
        self.switched = 0.0
        if self.style_ == "diashow":
            self.images = list_images(cfg.get("folder", ""))
            self.rng.shuffle(self.images)
            self._next_image()
        if self.style_ == "szene" and cfg.get("scene"):
            self.child = create_source({"type": "scene", "scene": cfg["scene"]}, scene_lookup, 0, self)
            self.child.show()
        self.text_color = QColor(cfg.get("color") or "#e8ecf3")
        fps = {"uhr": 2, "nachricht": 2, "diashow": 30, "schweben": 50, "farben": 25}.get(self.style_, 0)
        self.timer = QTimer(self, interval=int(1000 / fps) if fps else 1000)
        self.timer.timeout.connect(self._tick)
        if fps:
            self.timer.start()

    def stop(self):
        self.timer.stop()
        if self.child is not None:
            self.child.stop()

    def resizeEvent(self, _e):
        if self.child is not None:
            self.child.setGeometry(self.rect())

    def _next_image(self):
        if not self.images:
            return
        self.index = (self.index + 1) % len(self.images)
        self.previous = self.current
        self.current = load_image(self.images[self.index])
        self.switched = time.monotonic()

    def _tick(self):
        if self.style_ == "diashow" and time.monotonic() - self.switched > max(3, int(self.cfg.get("interval", 8))):
            self._next_image()
        if self.style_ == "schweben":
            self._move()
        self.update()

    def _move(self):
        w, h = self._float_size()
        x, y = self.pos.x() + self.vel.x(), self.pos.y() + self.vel.y()
        if x < 0 or x + w > self.width():
            self.vel.setX(-self.vel.x())
            x = min(max(0, x), max(0, self.width() - w))
        if y < 0 or y + h > self.height():
            self.vel.setY(-self.vel.y())
            y = min(max(0, y), max(0, self.height() - h))
        self.pos = QPointF(x, y)

    def _float_font(self) -> QFont:
        f = QFont()
        f.setPixelSize(max(24, self.height() // 9))
        f.setBold(True)
        return f

    def _float_size(self):
        if self.logo is not None:
            side = self.height() / 4
            ratio = self.logo.width() / max(1, self.logo.height())
            return side * ratio, side
        fm = QFontMetrics(self._float_font())
        return fm.horizontalAdvance(self._float_text()) + 20, fm.height() + 10

    def _float_text(self) -> str:
        return self.cfg.get("text") or time.strftime("%H:%M")

    # ------------------------------------------------------------ Zeichnen
    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.fillRect(self.rect(), Qt.black)
        t = time.monotonic() - self.t0
        {"uhr": self._paint_clock, "schweben": self._paint_float, "diashow": self._paint_slides,
         "farben": self._paint_colors, "nachricht": self._paint_message}.get(self.style_, lambda *_: None)(p, t)
        p.end()

    def _paint_clock(self, p: QPainter, t: float):
        w, h = self.width(), self.height()
        g = QRadialGradient(QPointF(w * 0.5, h * 0.35), max(w, h) * 0.8)
        g.setColorAt(0, QColor("#141c2e"))
        g.setColorAt(1, QColor("#05070c"))
        p.fillRect(self.rect(), g)
        # langsames Wandern: jede Minute ein anderer Platz (Einbrennschutz)
        minute = int(time.time() // 60)
        rng = random.Random(minute)
        big = QFont()
        big.setPixelSize(max(40, h // 5))
        big.setWeight(QFont.Light)
        small = QFont()
        small.setPixelSize(max(16, h // 22))
        clock = time.strftime("%H:%M")
        date = format_date_de(time.localtime())
        bw = QFontMetrics(big).horizontalAdvance(clock)
        bh = QFontMetrics(big).height()
        sh = QFontMetrics(small).height()
        block_w = max(bw, QFontMetrics(small).horizontalAdvance(date))
        x = rng.uniform(w * 0.05, max(w * 0.05, w * 0.95 - block_w))
        y = rng.uniform(h * 0.08, max(h * 0.08, h * 0.92 - bh - sh))
        p.setFont(big)
        p.setPen(self.text_color)
        p.drawText(QRectF(x, y, block_w, bh), Qt.AlignHCenter | Qt.AlignVCenter, clock)
        p.setFont(small)
        p.setPen(QColor("#8f99ab"))
        p.drawText(QRectF(x, y + bh, block_w, sh), Qt.AlignHCenter | Qt.AlignVCenter, date)

    def _paint_float(self, p: QPainter, t: float):
        w, h = self._float_size()
        rect = QRectF(self.pos.x(), self.pos.y(), w, h)
        if self.logo is not None:
            p.drawImage(rect, self.logo)
            return
        p.setFont(self._float_font())
        if self.cfg.get("color"):
            p.setPen(self.text_color)
        else:
            p.setPen(QColor.fromHsv(int(t * 20) % 360, 150, 255))
        p.drawText(rect, Qt.AlignCenter, self._float_text())

    def _paint_message(self, p: QPainter, t: float):
        w, h = self.width(), self.height()
        if self.logo is not None:
            self._draw_kenburns(p, self.logo, 0, 1.0)
            p.fillRect(self.rect(), QColor(0, 0, 0, 120))  # abdunkeln, damit der Text lesbar bleibt
        else:
            g = QLinearGradient(0, 0, w, h)
            g.setColorAt(0, QColor("#111827"))
            g.setColorAt(1, QColor("#1e1b4b"))
            p.fillRect(self.rect(), g)
        # Text wandert pro Minute ein kleines Stück (Einbrennschutz)
        rng = random.Random(int(time.time() // 60))
        dx, dy = rng.uniform(-0.04, 0.04) * w, rng.uniform(-0.04, 0.04) * h
        text = self.cfg.get("text") or "Gleich geht's weiter"
        f = QFont()
        f.setBold(True)
        f.setPixelSize(max(24, h // 8))
        while f.pixelSize() > 16 and QFontMetrics(f).boundingRect(
                0, 0, int(w * 0.85), h, Qt.TextWordWrap, text).height() > h * 0.6:
            f.setPixelSize(int(f.pixelSize() * 0.9))
        p.setFont(f)
        p.setPen(self.text_color)
        p.drawText(QRectF(w * 0.075 + dx, h * 0.2 + dy, w * 0.85, h * 0.6), Qt.AlignCenter | Qt.TextWordWrap, text)
        small = QFont()
        small.setPixelSize(max(14, h // 20))
        p.setFont(small)
        c = QColor(self.text_color)
        c.setAlpha(170)
        p.setPen(c)
        p.drawText(QRectF(0, h * 0.86, w * 0.96, h * 0.1), Qt.AlignRight | Qt.AlignVCenter, time.strftime("%H:%M"))

    def _paint_slides(self, p: QPainter, t: float):
        if self.current is None or self.current.isNull():
            p.setPen(QColor("#8f99ab"))
            p.drawText(self.rect(), Qt.AlignCenter, "Keine Bilder im Ordner gefunden")
            return
        since = time.monotonic() - self.switched
        fade = min(1.0, since / 1.2)
        if self.previous is not None and fade < 1:
            self._draw_kenburns(p, self.previous, since + 8, 1.0)
        self._draw_kenburns(p, self.current, since, fade)

    def _draw_kenburns(self, p: QPainter, img, since: float, opacity: float):
        # langsames Hineinzoomen (Ken-Burns-Effekt)
        zoom = 1.0 + min(since, 20) * 0.006
        w, h = self.width(), self.height()
        scale = max(w / img.width(), h / img.height()) * zoom
        iw, ih = img.width() * scale, img.height() * scale
        p.setOpacity(opacity)
        p.drawImage(QRectF((w - iw) / 2, (h - ih) / 2, iw, ih), img)
        p.setOpacity(1.0)

    def _paint_colors(self, p: QPainter, t: float):
        w, h = self.width(), self.height()
        base = QLinearGradient(0, 0, w, h)
        base.setColorAt(0, QColor.fromHsv(int(t * 6) % 360, 160, 60))
        base.setColorAt(1, QColor.fromHsv(int(t * 6 + 120) % 360, 160, 40))
        p.fillRect(self.rect(), base)
        for i in range(3):
            cx = w * (0.5 + 0.35 * math.sin(t * 0.07 * (i + 1) + i * 2))
            cy = h * (0.5 + 0.35 * math.cos(t * 0.05 * (i + 2) + i))
            g = QRadialGradient(QPointF(cx, cy), max(w, h) * 0.45)
            c = QColor.fromHsv(int(t * 8 + i * 110) % 360, 200, 230)
            c.setAlpha(110)
            g.setColorAt(0, c)
            c2 = QColor(c)
            c2.setAlpha(0)
            g.setColorAt(1, c2)
            p.fillRect(self.rect(), g)


# --------------------------------------------------------------------------- Steuerung
class ScreensaverManager(QObject):
    """Startet den Bildschirmschoner nach Leerlauf und beendet ihn bei Aktivität."""

    changed = Signal()

    def __init__(self, controller):
        super().__init__(controller)
        self.controller = controller
        self.idle = IdleClock()
        self.active = False
        self.manual = False
        self.override_id = None
        self.last_activity = time.monotonic()  # Ersatz, wenn das System keine Leerlaufzeit meldet
        self.timer = QTimer(self, interval=2000)
        self.timer.timeout.connect(self.check)
        self.timer.start()

    def settings(self) -> dict:
        return self.controller.config["screensaver"]

    def activity(self):
        """AluPC wurde bedient (Kachel, Tastenkürzel …)."""
        self.last_activity = time.monotonic()

    def idle_seconds(self) -> float:
        secs = self.idle.seconds()
        own = time.monotonic() - self.last_activity
        return own if secs is None else min(secs, own)

    def allowed(self) -> bool:
        c = self.controller
        if c.output_screen() is None or c.screens_overlap() or c.privacy:
            return False
        if self.settings().get("when", "desktop") == "desktop":
            return c.mode == "desktop"
        return True

    def check(self):
        cfg = self.settings()
        idle = self.idle_seconds()
        if self.active:
            if not self.manual and idle < 3:
                self.stop()  # jemand hat Maus/Tastatur benutzt
            elif not self.allowed() and not self.manual:
                self.stop()
            return
        if cfg.get("enabled") and idle >= max(1, float(cfg.get("minutes", 10))) * 60 and self.allowed():
            self.start(manual=False)

    def start(self, manual: bool = True, override: dict | None = None):
        """Bildschirmschoner zeigen – mit den Einstellungen aus dem Setup oder (Kachel) eigenen."""
        c = self.controller
        if c.output_screen() is None:
            c.message.emit("Kein zweiter Monitor gefunden.")
            return
        if c.screens_overlap():
            c.message.emit("Bildschirmschoner geht nicht bei System-Spiegeln – nutze „Spiegeln“ in AluPC.")
            return
        self.active, self.manual = True, manual
        self.override_id = (override or {}).get("_id")
        cfg = {**self.settings(), **(override or {})}
        c.output.set_screensaver(ScreensaverView(cfg, c.config.get_scene))
        c.sounds.play_event("schoner_an")
        self.changed.emit()

    def stop(self):
        if not self.active:
            return
        self.active = self.manual = False
        self.override_id = None
        self.controller.output.set_screensaver(None)
        self.controller.sounds.play_event("schoner_aus")
        self.changed.emit()

    def toggle(self):
        if self.active:
            self.stop()
        else:
            self.start(manual=True)
