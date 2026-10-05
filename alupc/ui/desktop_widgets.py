"""Desktop-Widgets: eigene, schöne „System-Oberflächen“ auf Monitor 1 – Uhr, Systemstatus, Musik, Sprach-Anzeige und
Lautstärke-Anzeige. Halb durchsichtig (Glas-Look), einzeln an/aus, mit der Maus verschiebbar (Rechtsklick = Menü).

Uhr, System und Musik sind kleine Karten, die Sprach- und Lautstärke-Anzeige erscheinen nur kurz, wenn etwas
passiert (wie die Anzeigen vom System) – Klicks gehen durch sie hindurch.

Hinweis Wayland (KDE): Programme dürfen ihre Fenster dort nicht selbst platzieren – KWin legt die Karten hin, und
gemerkte Positionen gelten nur unter X11/Windows. Verschieben mit der Maus geht trotzdem.
"""

from __future__ import annotations

import time

from PySide6.QtCore import QPoint, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QGuiApplication, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import QMenu, QWidget

from . import theme
from .widgets import font, rounded

ITEMS = {"uhr": "Uhr", "system": "Systemstatus", "musik": "Musik", "sprache": "Sprach-Anzeige",
         "lautstaerke": "Lautstärke-Anzeige"}
DEFAULTS = {"on": False, "items": {k: True for k in ITEMS}, "opacity": 0.78, "top": False, "pos": {},
            "style": "glas"}
STYLES = {"glas": "Glas (dunkel)", "hell": "Glas (hell)", "neon": "Neon"}


def settings(config) -> dict:
    cfg = {**DEFAULTS, **(config.get("widgets") or {})}
    cfg["items"] = {**DEFAULTS["items"], **(cfg.get("items") or {})}
    return cfg


class GlassCard(QWidget):
    """Rahmenloses, durchsichtiges Fenster mit Glas-Karte; mit der linken Maustaste verschiebbar."""

    W, H = 260, 120
    HUD = False  # kurz eingeblendete Anzeige (oben drauf, Klicks gehen durch)

    def __init__(self, manager, key: str):
        flags = Qt.FramelessWindowHint | Qt.Tool | Qt.NoDropShadowWindowHint
        cfg = manager.cfg()
        if self.HUD or cfg["top"]:
            flags |= Qt.WindowStaysOnTopHint
        else:
            flags |= Qt.WindowStaysOnBottomHint
        if self.HUD:
            flags |= Qt.WindowTransparentForInput | Qt.WindowDoesNotAcceptFocus
        super().__init__(None, flags)
        self.manager, self.key = manager, key
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setWindowTitle(f"AluPC – {ITEMS.get(key, key)}")
        self.resize(self.W, self.H)
        self._drag: QPoint | None = None

    # ---- Aussehen
    def colors(self) -> tuple[QColor, QColor, QColor]:
        """(Hintergrund, Text, Akzent) für den gewählten Stil und die eingestellte Deckkraft."""
        cfg = self.manager.cfg()
        alpha = max(0.15, min(1.0, float(cfg["opacity"])))
        accent = QColor(theme.current().accent)
        if cfg["style"] == "hell":
            bg, fg = QColor(248, 250, 252), QColor("#0f172a")
        else:
            bg, fg = QColor(10, 14, 28), QColor("#f1f5f9")
        bg.setAlphaF(alpha)
        if cfg["style"] == "neon":
            accent = QColor("#22d3ee")
        return bg, fg, accent

    def paint_card(self, p: QPainter) -> QRectF:
        bg, _fg, accent = self.colors()
        r = QRectF(self.rect()).adjusted(4, 4, -4, -4)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillPath(rounded(r, 18), bg)
        shine = QLinearGradient(r.topLeft(), r.bottomLeft())
        shine.setColorAt(0, QColor(255, 255, 255, 26))
        shine.setColorAt(0.5, QColor(255, 255, 255, 0))
        p.fillPath(rounded(r, 18), shine)
        edge = QColor(accent) if self.manager.cfg()["style"] == "neon" else QColor(255, 255, 255, 40)
        p.setPen(QPen(edge, 1.4))
        p.drawPath(rounded(r.adjusted(0.5, 0.5, -0.5, -0.5), 18))
        return r.adjusted(16, 12, -16, -12)

    # ---- Verschieben / Menü
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            handle = self.windowHandle()
            if handle is not None and QGuiApplication.platformName() == "wayland" and handle.startSystemMove():
                return  # Wayland: der Compositor verschiebt
            self._drag = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
        elif e.button() == Qt.RightButton:
            self.menu(e.globalPosition().toPoint())

    def mouseMoveEvent(self, e):
        if self._drag is not None:
            self.move(e.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, e):
        if self._drag is not None:
            self._drag = None
            self.manager.remember_pos(self.key, self.pos())

    def menu(self, at: QPoint) -> None:
        m = QMenu(self)
        m.addAction(f"„{ITEMS.get(self.key, self.key)}“ ausblenden", lambda: self.manager.set_item(self.key, False))
        m.addAction("Alle Widgets aus", lambda: self.manager.set_on(False))
        m.addSeparator()
        m.addAction("Einstellungen …", self.manager.open_settings)
        m.exec(at)


# --------------------------------------------------------------------------- Uhr
class ClockCard(GlassCard):
    W, H = 280, 132

    def __init__(self, manager, key):
        super().__init__(manager, key)
        self._timer = QTimer(self, interval=1000)
        self._timer.timeout.connect(self.update)
        self._timer.start()

    def paintEvent(self, _e):
        p = QPainter(self)
        r = self.paint_card(p)
        _bg, fg, accent = self.colors()
        now = time.localtime()
        p.setPen(fg)
        p.setFont(font(40, QFont.Bold))
        p.drawText(QRectF(r.x(), r.y(), r.width(), r.height() * 0.62), Qt.AlignLeft | Qt.AlignVCenter,
                   time.strftime("%H:%M", now))
        p.setFont(font(15, QFont.Medium))
        p.setPen(accent)
        p.drawText(QRectF(r.x() + 150, r.y() + 10, r.width() - 150, 30), Qt.AlignRight | Qt.AlignVCenter,
                   time.strftime(":%S", now))
        days = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
        months = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober",
                  "November", "Dezember"]
        p.setPen(fg)
        p.setOpacity(0.75)
        p.setFont(font(11))
        p.drawText(QRectF(r.x(), r.y() + r.height() * 0.64, r.width(), r.height() * 0.36),
                   Qt.AlignLeft | Qt.AlignVCenter, f"{days[now.tm_wday]}, {now.tm_mday}. {months[now.tm_mon - 1]}")
        p.end()


# --------------------------------------------------------------------------- System
class SystemCard(GlassCard):
    W, H = 280, 170

    def __init__(self, manager, key):
        super().__init__(manager, key)
        from .. import sysinfo

        self.mon = sysinfo.monitor()
        self.mon.acquire(self)
        self.mon.updated.connect(self._fit)
        self._fit(self.mon.snapshot)

    def _fit(self, snap) -> None:
        """Höhe passend zu den Zeilen (ohne Grafikkarten-Werte eine Zeile weniger)."""
        rows = 3 if snap is not None and snap.gpu is not None and snap.gpu.load is not None else 2
        h = 64 + rows * 30
        if self.height() != h:
            self.resize(self.W, h)
        self.update()

    def closeEvent(self, e):
        self.mon.release(self)
        super().closeEvent(e)

    def paintEvent(self, _e):
        p = QPainter(self)
        r = self.paint_card(p)
        _bg, fg, accent = self.colors()
        s = self.mon.snapshot
        rows = [("CPU", s.cpu, "#60a5fa"), ("RAM", s.ram, "#a78bfa")]
        if s.gpu is not None and s.gpu.load is not None:
            rows.append(("GPU", s.gpu.load, "#34d399"))
        temp = s.cpu_temp if s.cpu_temp is not None else (s.gpu.temp if s.gpu else None)
        p.setFont(font(10, QFont.DemiBold))
        p.setPen(fg)
        p.drawText(QRectF(r.x(), r.y(), r.width(), 20), Qt.AlignLeft | Qt.AlignVCenter, "SYSTEM")
        if temp is not None:
            p.setPen(QColor("#fbbf24") if temp > 80 else accent)
            p.drawText(QRectF(r.x(), r.y(), r.width(), 20), Qt.AlignRight | Qt.AlignVCenter, f"{temp:.0f} °C")
        y = r.y() + 30
        for label, value, color in rows:
            value = max(0.0, min(100.0, float(value or 0)))
            p.setPen(fg)
            p.setOpacity(0.8)
            p.setFont(font(10))
            p.drawText(QRectF(r.x(), y, 40, 18), Qt.AlignLeft | Qt.AlignVCenter, label)
            p.setOpacity(1.0)
            p.drawText(QRectF(r.right() - 50, y, 50, 18), Qt.AlignRight | Qt.AlignVCenter, f"{value:.0f} %")
            bar = QRectF(r.x() + 42, y + 6, r.width() - 98, 7)
            p.fillPath(rounded(bar, 3.5), QColor(255, 255, 255, 30))
            fill = QColor(color if value < 85 else "#ef4444")
            p.fillPath(rounded(QRectF(bar.x(), bar.y(), max(7.0, bar.width() * value / 100), bar.height()), 3.5),
                       fill)
            y += 30
        p.end()


# --------------------------------------------------------------------------- Musik
class MusicCard(GlassCard):
    W, H = 320, 96

    def __init__(self, manager, key):
        super().__init__(manager, key)
        from ..now_playing_view import feed

        self.feed = feed()
        self.feed.acquire()
        self.feed.changed.connect(lambda _t: self.update())
        self._timer = QTimer(self, interval=1000)
        self._timer.timeout.connect(self.update)
        self._timer.start()

    def closeEvent(self, e):
        self.feed.release()
        super().closeEvent(e)

    def paintEvent(self, _e):
        from ..now_playing import fmt_time

        p = QPainter(self)
        r = self.paint_card(p)
        _bg, fg, accent = self.colors()
        track = self.feed.track
        cover = QRectF(r.x(), r.y(), r.height(), r.height())
        p.fillPath(rounded(cover, 10), QColor(accent.red(), accent.green(), accent.blue(), 90))
        from . import icons

        icons.paint(p, "music", cover.adjusted(14, 14, -14, -14), "#ffffff", 2.0)
        text_x = cover.right() + 12
        width = r.right() - text_x
        p.setPen(fg)
        if track is None or not track.title:
            p.setFont(font(11, QFont.Medium))
            p.setOpacity(0.7)
            p.drawText(QRectF(text_x, r.y(), width, r.height()), Qt.AlignLeft | Qt.AlignVCenter, "Keine Musik")
            p.end()
            return
        p.setFont(font(11.5, QFont.DemiBold))
        title = p.fontMetrics().elidedText(track.title, Qt.ElideRight, int(width))
        p.drawText(QRectF(text_x, r.y(), width, 22), Qt.AlignLeft | Qt.AlignVCenter, title)
        p.setFont(font(10))
        p.setOpacity(0.75)
        artist = p.fontMetrics().elidedText(track.artist or track.player, Qt.ElideRight, int(width))
        p.drawText(QRectF(text_x, r.y() + 22, width, 20), Qt.AlignLeft | Qt.AlignVCenter, artist)
        p.setOpacity(1.0)
        if track.length > 0:
            part = track.position_now() / track.length
            bar = QRectF(text_x, r.bottom() - 10, width - 70, 5)
            p.fillPath(rounded(bar, 2.5), QColor(255, 255, 255, 40))
            p.fillPath(rounded(QRectF(bar.x(), bar.y(), max(5.0, bar.width() * part), 5), 2.5), accent)
            p.setFont(font(9))
            p.drawText(QRectF(bar.right() + 6, bar.y() - 7, 64, 18), Qt.AlignLeft | Qt.AlignVCenter,
                       f"{fmt_time(track.position_now())} {'▶' if track.playing else '❚❚'}")
        p.end()


# --------------------------------------------------------------------------- kurze Anzeigen (HUD)
class HudCard(GlassCard):
    """Erscheint kurz unten in der Mitte, blendet weich aus."""

    HUD = True
    W, H = 460, 86
    SHOW = 3.2

    def __init__(self, manager, key):
        super().__init__(manager, key)
        self.title, self.text, self.value = "", "", None
        self.until = 0.0
        self._timer = QTimer(self, interval=40)
        self._timer.timeout.connect(self._tick)

    def flash(self, title: str, text: str = "", value: float | None = None, seconds: float | None = None) -> None:
        self.title, self.text, self.value = title, text, value
        self.until = time.monotonic() + (seconds or self.SHOW)
        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            g = screen.availableGeometry()
            self.move(g.center().x() - self.width() // 2, g.bottom() - self.height() - 70)
        self.setWindowOpacity(1.0)
        self.show()
        self.raise_()
        self._timer.start()
        self.update()

    def _tick(self):
        left = self.until - time.monotonic()
        if left <= 0:
            self._timer.stop()
            self.hide()
        elif left < 0.4:
            self.setWindowOpacity(left / 0.4)

    def paintEvent(self, _e):
        p = QPainter(self)
        r = self.paint_card(p)
        _bg, fg, accent = self.colors()
        from . import icons

        icon = "sound" if self.key == "lautstaerke" else "mic"
        circle = QRectF(r.x(), r.center().y() - 22, 44, 44)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(accent.red(), accent.green(), accent.blue(), 70))
        pulse = 1 + 0.06 * abs(((time.monotonic() * 2) % 2) - 1) if self.key == "sprache" else 1
        p.drawEllipse(circle.center(), 22 * pulse, 22 * pulse)
        icons.paint(p, icon, circle.adjusted(11, 11, -11, -11), "#ffffff", 2.0)
        x = circle.right() + 14
        width = r.right() - x
        p.setPen(fg)
        p.setFont(font(12.5, QFont.DemiBold))
        title = p.fontMetrics().elidedText(self.title, Qt.ElideRight, int(width))
        p.drawText(QRectF(x, r.y(), width, r.height() / 2), Qt.AlignLeft | Qt.AlignVCenter, title)
        if self.value is not None:
            bar = QRectF(x, r.y() + r.height() * 0.62, width, 8)
            p.fillPath(rounded(bar, 4), QColor(255, 255, 255, 40))
            p.fillPath(rounded(QRectF(bar.x(), bar.y(), max(8.0, bar.width() * self.value / 100), 8), 4), accent)
        elif self.text:
            p.setFont(font(10.5))
            p.setOpacity(0.8)
            text = p.fontMetrics().elidedText(self.text, Qt.ElideRight, int(width))
            p.drawText(QRectF(x, r.center().y(), width, r.height() / 2), Qt.AlignLeft | Qt.AlignVCenter, text)
        p.end()


CLASSES = {"uhr": ClockCard, "system": SystemCard, "musik": MusicCard, "sprache": HudCard, "lautstaerke": HudCard}


class DesktopWidgets:
    """Verwaltet die Karten: an/aus, Positionen, Einstellungen; reagiert auf Sprache und Lautstärke."""

    def __init__(self, controller, open_settings=None):
        self.c = controller
        self.cards: dict[str, GlassCard] = {}
        self._open_settings = open_settings
        vc = controller.voice
        vc.heard.connect(self._heard)
        vc.command.connect(lambda _c, label, _t: self._voice("✓ " + label))
        vc.not_understood.connect(lambda t: self._voice("Nicht verstanden", f"„{t}“"))
        controller.volume_changed.connect(self._volume)

    def cfg(self) -> dict:
        return settings(self.c.config)

    def save(self, **changes) -> None:
        self.c.config["widgets"] = {**self.cfg(), **changes}

    def open_settings(self) -> None:
        if self._open_settings:
            self._open_settings()

    # ---- an/aus
    def set_on(self, on: bool) -> None:
        self.save(on=bool(on))
        self.apply()

    def toggle(self) -> None:
        self.set_on(not self.cfg()["on"])

    def set_item(self, key: str, on: bool) -> None:
        cfg = self.cfg()
        self.save(items={**cfg["items"], key: bool(on)})
        self.apply()

    def remember_pos(self, key: str, pos: QPoint) -> None:
        cfg = self.cfg()
        self.save(pos={**cfg["pos"], key: [pos.x(), pos.y()]})

    def reset_positions(self) -> None:
        self.save(pos={})
        self.apply(rebuild=True)

    def apply(self, rebuild: bool = False) -> None:
        """Karten passend zur Einstellung zeigen/verstecken (rebuild: neu anlegen, z. B. nach „Vorne“)."""
        cfg = self.cfg()
        if rebuild:
            self.close_all()
        for key in ("uhr", "system", "musik"):
            want = cfg["on"] and cfg["items"].get(key, True)
            card = self.cards.get(key)
            if want and card is None:
                card = self.cards[key] = CLASSES[key](self, key)
                self._place(key, card)
                card.show()
            elif not want and card is not None:
                card.close()
                card.deleteLater()
                del self.cards[key]
            elif card is not None:
                card.update()

    def _place(self, key: str, card: GlassCard) -> None:
        pos = self.cfg()["pos"].get(key)
        screen = QGuiApplication.primaryScreen()
        if pos:
            card.move(int(pos[0]), int(pos[1]))
        elif screen is not None:  # Standard: rechts oben untereinander
            g = screen.availableGeometry()
            y = g.top() + 24
            for k in ("uhr", "system", "musik"):
                if k == key:
                    break
                if k in self.cards and k != key:
                    y += self.cards[k].height() + 8
            card.move(g.right() - card.width() - 24, y)

    def close_all(self) -> None:
        for card in list(self.cards.values()):
            card.close()
            card.deleteLater()
        self.cards.clear()

    # ---- kurze Anzeigen
    def _hud(self, key: str) -> HudCard | None:
        cfg = self.cfg()
        if not cfg["on"] or not cfg["items"].get(key, True):
            return None
        card = self.cards.get(key)
        if card is None:
            card = self.cards[key] = HudCard(self, key)
        return card

    def _heard(self, text: str) -> None:
        if self.c.voice.open_ear() or "(genau)" in text:
            self._voice("Gehört", text.strip("„“"))

    def _voice(self, title: str, text: str = "") -> None:
        hud = self._hud("sprache")
        if hud is not None:
            hud.flash(title, text)

    def _volume(self, value: int) -> None:
        hud = self._hud("lautstaerke")
        if hud is not None:
            hud.flash(f"Lautstärke {value} %", value=value, seconds=1.8)


__all__ = ["DesktopWidgets", "ITEMS", "STYLES", "settings"]
