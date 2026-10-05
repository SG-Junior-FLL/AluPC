"""Seite „System“: Live-Status (Prozessor, Speicher, Grafikkarte, Temperaturen, Lüfter, Laufwerke, Netzwerk,
Akku, Programme), „PC steuern“ (Lautstärke, Musik, Fenster, Bildschirmfoto, Programme öffnen) und Steuerung
(Sperren, Energie sparen, Neustart, Herunterfahren, RGB)."""

from __future__ import annotations

import subprocess
import sys

from PySide6.QtCore import QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .. import sysinfo
from ..sysinfo import POWER_TEXT, fmt_bytes, fmt_rate, fmt_uptime
from ..sysinfo_draw import COLORS, gauge_values, level_color, paint_bar, paint_ring, paint_sparkline
from . import icons, theme
from .util import error_box
from .widgets import button, font, page_header

RGB_COLORS = ["#ef4444", "#f97316", "#22c55e", "#06b6d4", "#3b82f6", "#8b5cf6", "#ec4899", "#ffffff"]


class Card(QWidget):
    """Karte mit eigenem Hintergrund (leichter Farbschimmer oben) – Inhalt zeichnet `draw()`."""

    accent = "#3b82f6"

    def __init__(self, title: str, icon_name: str, parent=None):
        super().__init__(parent)
        self.title, self.icon_name = title, icon_name
        self.setMinimumHeight(150)

    def paintEvent(self, _e):
        t = theme.current()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(r, 16, 16)
        p.fillPath(path, QColor(t.surface))
        sheen = QLinearGradient(r.topLeft(), r.bottomLeft())
        c = QColor(self.accent)
        c.setAlphaF(0.13 if t.dark else 0.08)
        sheen.setColorAt(0, c)
        c.setAlphaF(0.0)
        sheen.setColorAt(0.6, c)
        p.fillPath(path, sheen)
        p.setPen(QPen(QColor(t.border), 1))
        p.drawPath(path)
        icons.paint(p, self.icon_name, QRectF(16, 15, 18, 18), self.accent, 2.0)
        p.setFont(font(10, QFont.DemiBold))
        p.setPen(QColor(t.text))
        p.drawText(QRectF(42, 12, r.width() - 56, 24), Qt.AlignLeft | Qt.AlignVCenter, self.title)
        self.draw(p, t, QRectF(16, 44, r.width() - 32, r.height() - 58))
        p.end()

    def draw(self, p: QPainter, t, r: QRectF) -> None:  # pragma: no cover - überschrieben
        pass


class GaugeCard(Card):
    """Großer Ring mit Prozent, darunter Kurve der letzten 60 Sekunden."""

    def __init__(self, key: str, page, parent=None):
        super().__init__("", "gauge", parent)
        self.key, self.page = key, page
        self.accent = COLORS[key][0]
        self.icon_name = {"cpu": "gauge", "ram": "layers", "gpu": "monitor", "temp": "sun"}[key]
        self.shown = 0.0
        self.target = 0.0
        self.data = ("", None, "–", "")
        self.anim = QTimer(self, interval=16)
        self.anim.timeout.connect(self._step)
        self.setMinimumSize(140, 236)

    def set(self, title: str, frac: float | None, big: str, small: str) -> None:
        self.title = title
        self.data = (title, frac, big, small)
        self.target = frac or 0.0
        if not self.anim.isActive():
            self.anim.start()

    def _step(self):
        d = self.target - self.shown
        if abs(d) < 0.002 or theme_reduced():
            self.shown = self.target
            self.anim.stop()
        else:
            self.shown += d * 0.14
        self.update()

    def draw(self, p, t, r):
        _title, frac, big, small = self.data
        size = min(r.width() * 0.62, r.height() - 66)
        ring = QRectF(r.center().x() - size / 2, r.y() - 2, size, size)
        track = QColor(t.surface2)
        paint_ring(p, ring, self.shown if frac is not None else 0.0, COLORS[self.key], track, max(8.0, size * 0.085))
        p.setPen(QColor(t.text) if frac is not None else QColor(t.muted))
        p.setFont(font(max(12.0, size * 0.15), QFont.Bold))
        p.drawText(ring, Qt.AlignCenter, big)
        p.setFont(font(8.5))
        p.setPen(QColor(t.muted))
        p.drawText(QRectF(r.x(), ring.bottom() + 2, r.width(), 18), Qt.AlignCenter,
                   p.fontMetrics().elidedText(small, Qt.ElideRight, int(r.width())))
        chart = QRectF(r.x(), ring.bottom() + 24, r.width(), r.bottom() - ring.bottom() - 22)
        hist = self.page.mon.history[self.key]
        paint_sparkline(p, chart, hist, COLORS[self.key][1], top=100, width=1.8)


def theme_reduced() -> bool:
    from .widgets import theme_reduced_motion

    return theme_reduced_motion()


class NetCard(Card):
    accent = COLORS["down"][0]

    def __init__(self, page, parent=None):
        super().__init__("Netzwerk", "globe", parent)
        self.page = page
        self.setMinimumHeight(190)

    def draw(self, p, t, r):
        snap, mon = self.page.mon.snapshot, self.page.mon
        p.setFont(font(13, QFont.Bold))
        p.setPen(QColor(COLORS["down"][0]))
        p.drawText(QRectF(r.x(), r.y(), r.width() / 2, 26), Qt.AlignLeft | Qt.AlignVCenter,
                   f"↓ {fmt_rate(snap.net_down)}")
        p.setPen(QColor(COLORS["up"][0]))
        p.drawText(QRectF(r.center().x(), r.y(), r.width() / 2, 26), Qt.AlignRight | Qt.AlignVCenter,
                   f"↑ {fmt_rate(snap.net_up)}")
        p.setFont(font(8.5))
        p.setPen(QColor(t.muted))
        p.drawText(QRectF(r.x(), r.y() + 26, r.width(), 18), Qt.AlignLeft | Qt.AlignVCenter,
                   f"IP {mon.ip}" if mon.ip else "keine Netzwerkverbindung")
        chart = QRectF(r.x(), r.y() + 50, r.width(), r.height() - 50)
        peak = max(max(mon.history["down"]), max(mon.history["up"]), 64 * 1024)
        paint_sparkline(p, chart, mon.history["down"], COLORS["down"][0], top=peak, width=1.8)
        paint_sparkline(p, chart, mon.history["up"], COLORS["up"][0], top=peak, width=1.8)


class CoresCard(Card):
    accent = COLORS["cpu"][1]

    def __init__(self, page, parent=None):
        super().__init__("Prozessorkerne", "gauge", parent)
        self.page = page
        self.setMinimumHeight(190)

    def draw(self, p, t, r):
        snap = self.page.mon.snapshot
        p.setFont(font(8.5))
        p.setPen(QColor(t.muted))
        p.drawText(QRectF(r.x(), r.y(), r.width(), 18), Qt.AlignLeft | Qt.AlignVCenter,
                   p.fontMetrics().elidedText(self.page.mon.cpu_name, Qt.ElideRight, int(r.width())))
        cores = snap.cores or [0.0] * max(1, self.page.mon.cores)
        area = QRectF(r.x(), r.y() + 26, r.width(), r.height() - 26)
        n = len(cores)
        gap = 3 if n > 16 else 5
        bw = max(2.0, (area.width() - gap * (n - 1)) / n)
        for i, v in enumerate(cores):
            col = QRectF(area.x() + i * (bw + gap), area.y(), bw, area.height())
            path = QPainterPath()
            path.addRoundedRect(col, min(4, bw / 2), min(4, bw / 2))
            p.fillPath(path, QColor(t.surface2))
            h = col.height() * max(0.03, min(1.0, v / 100))
            fill = QRectF(col.x(), col.bottom() - h, bw, h)
            g = QLinearGradient(fill.bottomLeft(), col.topLeft())
            g.setColorAt(0, QColor(COLORS["cpu"][0]))
            g.setColorAt(1, level_color(v, 60, 85))
            path = QPainterPath()
            path.addRoundedRect(fill, min(4, bw / 2), min(4, bw / 2))
            p.fillPath(path, g)


class DiskCard(Card):
    accent = "#8b5cf6"

    def __init__(self, page, parent=None):
        super().__init__("Laufwerke", "layers", parent)
        self.page = page
        self.setMinimumHeight(190)

    def draw(self, p, t, r):
        snap = self.page.mon.snapshot
        y = r.y()
        rows = list(snap.disks[:4])
        if snap.battery:
            rows.append(None)
        for d in rows:
            if d is None:
                pct, plugged, left = snap.battery
                name = "Akku" + (" · lädt" if plugged else (f" · noch {fmt_uptime(left)}" if left else ""))
                right, frac = f"{pct:.0f} %", pct / 100
                colors = ("#22c55e", "#84cc16") if pct > 20 else ("#f59e0b", "#ef4444")
            else:
                name, right, frac = d.mount, f"{fmt_bytes(d.total - d.used)} frei von {fmt_bytes(d.total)}", d.percent / 100
                colors = ("#6366f1", "#a855f7") if d.percent < 90 else ("#f59e0b", "#ef4444")
            p.setFont(font(9))
            p.setPen(QColor(t.text))
            p.drawText(QRectF(r.x(), y, r.width() * 0.45, 18), Qt.AlignLeft | Qt.AlignVCenter,
                       p.fontMetrics().elidedText(name, Qt.ElideMiddle, int(r.width() * 0.45)))
            p.setPen(QColor(t.muted))
            p.setFont(font(8.5))
            p.drawText(QRectF(r.x(), y, r.width(), 18), Qt.AlignRight | Qt.AlignVCenter, right)
            paint_bar(p, QRectF(r.x(), y + 21, r.width(), 7), frac, colors, QColor(t.surface2))
            y += 36
        p.setFont(font(8.5))
        p.setPen(QColor(t.muted))
        p.drawText(QRectF(r.x(), r.bottom() - 18, r.width(), 18), Qt.AlignLeft | Qt.AlignVCenter,
                   f"Lesen {fmt_rate(snap.disk_read)}   ·   Schreiben {fmt_rate(snap.disk_write)}")


class SensorCard(Card):
    accent = COLORS["temp"][0]

    def __init__(self, page, parent=None):
        super().__init__("Temperaturen & Lüfter", "fan", parent)
        self.page = page
        self.setMinimumHeight(190)

    def rows(self):
        snap = self.page.mon.snapshot
        out = [("temp", n, v) for n, v in snap.temps[:6]]
        if snap.gpu and snap.gpu.temp is not None and not any(n == snap.gpu.name for _k, n, _v in out):
            out.append(("temp", snap.gpu.name, snap.gpu.temp))
        out += [("fan", n, v) for n, v in snap.fans if v > 0][:6]
        if snap.gpu and snap.gpu.fan is not None:
            out.append(("gpufan", f"{snap.gpu.name} (Lüfter)", snap.gpu.fan))
        return out

    def sizeHint(self):
        return QSize(300, max(190, 70 + 26 * len(self.rows())))

    def draw(self, p, t, r):
        rows = self.rows()
        if not rows:
            p.setFont(font(9))
            p.setPen(QColor(t.muted))
            text = ("Windows meldet ohne Hersteller-Programm keine Temperaturen und Lüfter. "
                    "NVIDIA-Grafikkarten zeigt AluPC trotzdem; für Lüfter z. B. FanControl."
                    if sys.platform == "win32" else "Keine Sensoren gefunden (Paket lm-sensors installieren, "
                    "dann „sudo sensors-detect“).")
            p.drawText(r, Qt.TextWordWrap | Qt.AlignLeft | Qt.AlignTop, text)
            return
        y = r.y()
        for kind, name, value in rows:
            if y + 22 > r.bottom() + 6:
                break
            p.setFont(font(9))
            p.setPen(QColor(t.text))
            p.drawText(QRectF(r.x(), y, r.width() * 0.48, 20), Qt.AlignLeft | Qt.AlignVCenter,
                       p.fontMetrics().elidedText(name, Qt.ElideRight, int(r.width() * 0.48)))
            bar = QRectF(r.x() + r.width() * 0.5, y + 7, r.width() * 0.28, 6)
            if kind == "temp":
                c = level_color(value, 65, 85)
                paint_bar(p, bar, value / 100, (c.name(), c.name()), QColor(t.surface2))
                label = f"{value:.0f} °C"
            elif kind == "fan":
                paint_bar(p, bar, value / 2500, ("#06b6d4", "#3b82f6"), QColor(t.surface2))
                label = f"{value} U/min"
            else:
                paint_bar(p, bar, value / 100, ("#06b6d4", "#3b82f6"), QColor(t.surface2))
                label = f"{value:.0f} %"
            p.setPen(QColor(t.muted))
            p.drawText(QRectF(r.x(), y, r.width(), 20), Qt.AlignRight | Qt.AlignVCenter, label)
            y += 26


class ProcRow(QWidget):
    end_requested = Signal(int, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pid, self.name = 0, ""
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        self.name_label = QLabel()
        self.cpu_label = QLabel()
        self.mem_label = QLabel()
        for lab in (self.cpu_label, self.mem_label):
            lab.setObjectName("Muted")
            lab.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.cpu_label.setFixedWidth(52)
        self.mem_label.setFixedWidth(70)
        self.end = QPushButton()
        self.end.setIcon(icons.icon("x", theme.current().muted, 16))
        self.end.setFixedSize(28, 26)
        self.end.setToolTip("Programm beenden")
        self.end.clicked.connect(lambda: self.end_requested.emit(self.pid, self.name))
        row.addWidget(self.name_label, 1)
        row.addWidget(self.cpu_label)
        row.addWidget(self.mem_label)
        row.addWidget(self.end)

    def set(self, proc) -> None:
        self.pid, self.name = proc.pid, proc.name
        self.name_label.setText(proc.name)
        self.cpu_label.setText(f"{proc.cpu:.0f} %")
        self.mem_label.setText(fmt_bytes(proc.mem))


class SystemPage(QWidget):
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.mon = sysinfo.monitor()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)
        self.header = page_header("System", "Live-Status und Steuerung", "gauge")
        self.subtitle = self.header.findChild(QLabel, "PageSubtitle")
        top = QHBoxLayout()
        top.addWidget(self.header, 1)
        show = button("Auf Monitor 2", "monitor", primary=True)
        show.setToolTip("Großes System-Dashboard auf Monitor 2 zeigen")
        show.clicked.connect(lambda: controller.show_source({"type": "system"}))
        top.addWidget(show, 0, Qt.AlignTop)
        lay.addLayout(top)
        if not self.mon.available:
            warn = QLabel("Systemstatus braucht das Python-Paket „psutil“ (pip install psutil).")
            warn.setObjectName("Muted")
            lay.addWidget(warn)

        self.gauges = {k: GaugeCard(k, self) for k in ("cpu", "ram", "gpu", "temp")}
        self.net, self.cores, self.disks, self.sensors = NetCard(self), CoresCard(self), DiskCard(self), SensorCard(self)
        self.grid = QGridLayout()
        self.grid.setSpacing(14)
        lay.addLayout(self.grid)
        self.pc = self._pc_card()
        self.cards = [*self.gauges.values(), self.pc, self.cores, self.net, self.disks, self.sensors,
                      self._procs_card(), self._control_card()]
        self._cols = 0
        self._relayout(1)  # resizeEvent wählt dann die passende Spaltenzahl
        lay.addStretch(1)
        self.mon.updated.connect(self._update)
        if controller is not None:
            controller.rgb.status.connect(lambda *_: self._refresh_rgb())
        self._update(self.mon.snapshot)

    # ------------------------------------------------------------ Aufbau
    def _procs_card(self) -> QWidget:
        box = QWidget()
        box.setObjectName("Card")
        box.setAttribute(Qt.WA_StyledBackground, True)
        v = QVBoxLayout(box)
        v.setContentsMargins(16, 12, 12, 12)
        v.setSpacing(4)
        head = QHBoxLayout()
        ic = QLabel()
        ic.setPixmap(icons.pixmap("window", "#f97316", 18))
        title = QLabel("Programme (meiste Last)")
        title.setFont(font(10, QFont.DemiBold))
        head.addWidget(ic)
        head.addWidget(title, 1)
        open_btn = QPushButton("Alle …")
        open_btn.setToolTip("Systemüberwachung öffnen")
        open_btn.clicked.connect(self.open_task_manager)
        head.addWidget(open_btn)
        v.addLayout(head)
        self.proc_rows = []
        for _ in range(6):
            row = ProcRow()
            row.end_requested.connect(self.end_process)
            row.hide()
            self.proc_rows.append(row)
            v.addWidget(row)
        v.addStretch(1)
        return box

    def _control_card(self) -> QWidget:
        box = QWidget()
        box.setObjectName("Card")
        box.setAttribute(Qt.WA_StyledBackground, True)
        v = QVBoxLayout(box)
        v.setContentsMargins(16, 12, 16, 14)
        v.setSpacing(8)
        head = QHBoxLayout()
        ic = QLabel()
        ic.setPixmap(icons.pixmap("power", "#ef4444", 18))
        title = QLabel("Steuerung")
        title.setFont(font(10, QFont.DemiBold))
        head.addWidget(ic)
        head.addWidget(title, 1)
        v.addLayout(head)
        grid = QGridLayout()
        grid.setSpacing(8)
        self.power_buttons = {}
        for i, (action, icon_name, danger) in enumerate([("sperren", "lock", False), ("energiesparen", "moon", False),
                                                         ("neustart", "refresh", True), ("aus", "power", True)]):
            b = button(POWER_TEXT[action], icon_name, danger=danger)
            b.clicked.connect(lambda _=False, a=action: self.power(a))
            self.power_buttons[action] = b
            grid.addWidget(b, i // 2, i % 2)
        v.addLayout(grid)
        # RGB schnell
        rgb_row = QHBoxLayout()
        rgb_row.setSpacing(6)
        self.rgb_toggle = button("RGB", "palette")
        self.rgb_toggle.setCheckable(True)
        self.rgb_toggle.setToolTip("RGB-Beleuchtung an/aus (über OpenRGB)")
        self.rgb_toggle.clicked.connect(self._toggle_rgb)
        rgb_row.addWidget(self.rgb_toggle)
        self.rgb_swatches = []
        for color in RGB_COLORS:
            sw = QPushButton()
            sw.setFixedSize(22, 22)
            sw.setCursor(Qt.PointingHandCursor)
            sw.setToolTip(color)
            sw.setStyleSheet(f"QPushButton {{ background: {color}; border-radius: 11px; border: 1px solid "
                             f"{theme.current().border}; padding: 0; min-height: 0; }}")
            sw.clicked.connect(lambda _=False, c=color: self._rgb_color(c))
            self.rgb_swatches.append(sw)
            rgb_row.addWidget(sw)
        rgb_row.addStretch(1)
        v.addLayout(rgb_row)
        more = QHBoxLayout()
        hw = button("RGB && Lüfter …", "fan")
        hw.clicked.connect(self.open_hardware)
        tm = button("Systemüberwachung", "window")
        tm.clicked.connect(self.open_task_manager)
        more.addWidget(hw)
        more.addWidget(tm)
        v.addLayout(more)
        self.rgb_text = QLabel()
        self.rgb_text.setObjectName("Muted")
        self.rgb_text.setWordWrap(True)
        v.addWidget(self.rgb_text)
        v.addStretch(1)
        self._refresh_rgb()
        return box

    def _pc_card(self) -> QWidget:
        """PC steuern wie mit einer Fernbedienung: Lautstärke, Musik, Fenster, Bildschirmfoto, Programme, Ausführen."""
        from PySide6.QtWidgets import QCompleter, QLineEdit, QSlider

        from .. import pc_control
        from .util import run_async
        from .widgets import flow_row

        box = QWidget()
        box.setObjectName("Card")
        box.setAttribute(Qt.WA_StyledBackground, True)
        v = QVBoxLayout(box)
        v.setContentsMargins(16, 12, 16, 14)
        v.setSpacing(10)
        head = QHBoxLayout()
        ic = QLabel()
        ic.setPixmap(icons.pixmap("sliders", "#06b6d4", 18))
        title = QLabel("PC steuern")
        title.setFont(font(10, QFont.DemiBold))
        head.addWidget(ic)
        head.addWidget(title, 1)
        v.addLayout(head)
        # Lautstärke
        vol_row = QHBoxLayout()
        self.mute_btn = button("", "sound")
        self.mute_btn.setToolTip("Stumm an/aus")
        self.mute_btn.setCheckable(True)
        self.vol = QSlider(Qt.Horizontal)
        self.vol.setRange(0, 100)
        self.vol.setSingleStep(5)
        self.vol.setPageStep(10)
        self.vol_label = QLabel("– %")
        self.vol_label.setMinimumWidth(44)
        vol_row.addWidget(self.mute_btn)
        vol_row.addWidget(self.vol, 1)
        vol_row.addWidget(self.vol_label)
        v.addLayout(vol_row)

        def set_volume():
            value = self.vol.value()
            self.vol_label.setText(f"{value} %")
            run_async(lambda: pc_control.set_volume(value), lambda r: None if r[0] else
                      self.controller.message.emit(f"Lautstärke geht nicht: {r[1]}"))

        self.vol.valueChanged.connect(lambda val: self.vol_label.setText(f"{val} %"))
        self.vol.sliderReleased.connect(set_volume)
        self.vol.actionTriggered.connect(lambda _a: QTimer.singleShot(0, set_volume) if not self.vol.isSliderDown()
                                         else None)
        def mute(on):
            self.mute_btn.setIcon(icons.icon("mute" if on else "sound", theme.current().text, 18))
            run_async(lambda: pc_control.set_mute(on))

        self.mute_btn.toggled.connect(mute)

        def cmd(c):
            return lambda: self.controller.run_command(c)

        actions = [("⏮", "musik_zurueck", "Vorheriger Titel"), ("⏯", "musik_pause", "Play/Pause"),
                   ("⏭", "musik_weiter", "Nächster Titel")]
        media = []
        for label, c, tip in actions:
            b = QPushButton(label)
            b.setToolTip(tip)
            b.setMinimumWidth(48)
            b.clicked.connect(cmd(c))
            media.append(b)
        win = []
        for text, icon_name, c in (("Desktop", "window", "pc_desktop"), ("Fenster wechseln", "refresh",
                                                                         "pc_fenster_wechseln"),
                                   ("Bildschirmfoto", "camera", "pc_screenshot")):
            b = button(text, icon_name)
            b.clicked.connect(cmd(c))
            win.append(b)
        v.addWidget(flow_row(*media, *win))
        # Ausführen / Programm öffnen (wie Win+R bzw. KRunner, mit Vorschlägen aus den installierten Programmen)
        run_row = QHBoxLayout()
        self.run_edit = QLineEdit()
        self.run_edit.setPlaceholderText("Programm oder Befehl (wie Win+R) – z. B. Firefox, notepad, https://…")
        completer = QCompleter([], self.run_edit)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        self.run_edit.setCompleter(completer)
        go = button("Öffnen", "play", primary=True)
        run_row.addWidget(self.run_edit, 1)
        run_row.addWidget(go)
        v.addLayout(run_row)

        def fill_apps(names):
            try:
                from PySide6.QtCore import QStringListModel

                completer.setModel(QStringListModel(names, completer))
                self._app_names = set(n.lower() for n in names)
            except RuntimeError:
                pass

        self._app_names: set[str] = set()
        self._load_apps = lambda: run_async(pc_control.app_names, fill_apps)  # erst, wenn die Seite gezeigt wird

        def run_it():
            text = self.run_edit.text().strip()
            if not text:
                return

            def work():
                if text.lower() in self._app_names:
                    return pc_control.launch_installed(text)
                return pc_control.run_line(text)

            def done(result):
                ok, why = result
                self.controller.message.emit(f"Geöffnet: {text}" if ok else f"Ging nicht: {why}")
                if ok:
                    self.run_edit.clear()

            run_async(work, done)

        self.run_edit.returnPressed.connect(run_it)
        go.clicked.connect(run_it)
        return box

    def _read_volume(self) -> None:
        from .. import pc_control
        from .util import run_async

        def show(value):
            try:
                if value is None:
                    self.vol_label.setText("– %")
                    self.vol.setToolTip("Lautstärke lässt sich hier nicht ablesen")
                    return
                self.vol.blockSignals(True)
                self.vol.setValue(int(value))
                self.vol.blockSignals(False)
                self.vol_label.setText(f"{int(value)} %")
            except RuntimeError:
                pass

        run_async(pc_control.get_volume, show)

    def _relayout(self, cols: int) -> None:
        if cols == self._cols:
            return
        self._cols = cols
        for card in self.cards:
            self.grid.removeWidget(card)
        gauges = list(self.gauges.values())
        g_cols = cols if cols >= 2 else 1
        for i, card in enumerate(gauges):
            self.grid.addWidget(card, i // g_cols, i % g_cols)
        row = (len(gauges) + g_cols - 1) // g_cols
        rest = self.cards[len(gauges):]
        if cols >= 4:  # breit: „PC steuern“ über die ganze Breite, untere Karten paarweise
            self.grid.addWidget(self.pc, row, 0, 1, 4)
            row += 1
            layout = [(self.cores, 0, 2), (self.net, 2, 2), (self.disks, 0, 2), (self.sensors, 2, 2),
                      (rest[-2], 0, 2), (rest[-1], 2, 2)]
            for k, (card, col, span) in enumerate(layout):
                self.grid.addWidget(card, row + k // 2, col, 1, span)
        else:
            for k, card in enumerate(rest):
                self.grid.addWidget(card, row + k, 0, 1, g_cols)
        for c in range(4):
            self.grid.setColumnStretch(c, 1 if c < g_cols else 0)

    def resizeEvent(self, e):
        w = self.width()
        self._relayout(4 if w >= 700 else (2 if w >= 330 else 1))
        super().resizeEvent(e)

    def showEvent(self, e):
        self.mon.acquire(self)
        if hasattr(self, "vol"):
            self._read_volume()  # Lautstärke kann sich außerhalb von AluPC geändert haben
            if not self._app_names and getattr(self, "_load_apps", None):
                load, self._load_apps = self._load_apps, None
                load()
        super().showEvent(e)

    def hideEvent(self, e):
        self.mon.release(self)
        super().hideEvent(e)

    # ------------------------------------------------------------ Werte
    def _update(self, snap) -> None:
        for key, title, frac, big, small in gauge_values(self.mon, snap):
            self.gauges[key].set(title, frac, big, small)
        note = snap.gpu.note if snap.gpu is not None else ""
        self.gauges["gpu"].setToolTip(note)
        parts = [self.mon.host, self.mon.os]
        if snap.uptime:
            parts.append(f"läuft seit {fmt_uptime(snap.uptime)}")
        if self.subtitle:
            self.subtitle.setText("  ·  ".join(parts))
        for card in (self.net, self.cores, self.disks, self.sensors):
            card.update()
        self.sensors.updateGeometry()
        for row, proc in zip(self.proc_rows, snap.procs + [None] * 6):
            row.setVisible(proc is not None)
            if proc is not None:
                row.set(proc)

    # ------------------------------------------------------------ Steuerung
    def power(self, action: str) -> None:
        if action == "sperren":
            self.controller.lock_computer()
            return
        text = POWER_TEXT[action]
        question = {"energiesparen": "Computer in den Energiesparmodus schicken?",
                    "neustart": "Computer jetzt neu starten? Nicht gespeicherte Arbeit geht verloren.",
                    "aus": "Computer jetzt herunterfahren? Nicht gespeicherte Arbeit geht verloren."}[action]
        if QMessageBox.question(self, text, question) != QMessageBox.Yes:
            return
        try:
            sysinfo.power_action(action)
        except Exception as exc:  # noqa: BLE001
            error_box(self, str(exc))

    def end_process(self, pid: int, name: str) -> None:
        if QMessageBox.question(self, "Programm beenden", f"„{name}“ beenden? Nicht gespeicherte Daten gehen "
                                "verloren.") != QMessageBox.Yes:
            return
        try:
            sysinfo.end_process(pid)
        except Exception as exc:  # noqa: BLE001
            error_box(self, str(exc))

    def open_task_manager(self) -> None:
        cmd = sysinfo.task_manager_command()
        if not cmd:
            error_box(self, "Keine Systemüberwachung gefunden (z. B. „plasma-systemmonitor“ installieren).")
            return
        try:
            subprocess.Popen(cmd, creationflags=sysinfo.NO_WINDOW)
        except OSError as exc:
            error_box(self, f"Systemüberwachung ließ sich nicht öffnen: {exc}")

    def open_hardware(self) -> None:
        from .hardware_page import HardwarePage

        dlg = QDialog(self)
        dlg.setWindowTitle("RGB & Lüfter")
        dlg.resize(760, 640)
        v = QVBoxLayout(dlg)
        v.addWidget(HardwarePage(self.controller, scroll=True))
        dlg.exec()

    def _refresh_rgb(self) -> None:
        rgb = self.controller.rgb
        s = rgb.settings()
        on = s["mode"] != "aus"
        self.rgb_toggle.setChecked(on)
        self.rgb_toggle.setText("RGB an" if on else "RGB aus")
        self.rgb_text.setText("" if rgb.connected else f"RGB: {rgb.text}")

    def _toggle_rgb(self) -> None:
        rgb = self.controller.rgb
        mode = rgb.settings()["mode"]
        rgb.set_mode("farbe" if mode == "aus" else "aus")
        self._refresh_rgb()

    def _rgb_color(self, color: str) -> None:
        rgb = self.controller.rgb
        rgb.update_settings(color=color, mode="farbe")
        if not rgb.connected:
            rgb.connect_async(start_if_needed=True)
        self._refresh_rgb()
