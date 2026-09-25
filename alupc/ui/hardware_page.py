"""Seite „RGB & Lüfter“: RGB-Beleuchtung über OpenRGB, Temperaturen und Lüfter (Linux)."""

from __future__ import annotations

import sys

from PySide6.QtCore import QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QRadialGradient
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from ..platform import fans
from ..rgb import find_openrgb, hex_to_rgb, start_openrgb
from ..rgb_manager import MODES
from . import theme
from .util import ColorButton, error_box, run_async
from .widgets import Banner, button, font, rounded

PRESETS = ["#ef4444", "#f97316", "#facc15", "#22c55e", "#06b6d4", "#3b82f6", "#8b5cf6", "#ec4899", "#ffffff"]


class ColorOrb(QWidget):
    """Leuchtende Kugel in der aktuellen RGB-Farbe (Vorschau)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.color = QColor("#3b82f6")
        self.mode = "farbe"
        self.setFixedSize(132, 132)

    def set(self, color: str, mode: str, brightness: int):
        c = QColor(color)
        if mode == "aus":
            c = QColor("#1f2937")
        else:
            c = QColor(*hex_to_rgb(color, max(15, brightness)))
        self.color, self.mode = c, mode
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(6, 6, -6, -6)
        glow = QRadialGradient(r.center(), r.width() / 2)
        c = QColor(self.color)
        glow.setColorAt(0.0, c.lighter(150))
        glow.setColorAt(0.55, c)
        edge = QColor(c)
        edge.setAlphaF(0.0)
        glow.setColorAt(1.0, edge)
        p.setPen(Qt.NoPen)
        p.setBrush(glow)
        p.drawEllipse(r)
        core = r.adjusted(26, 26, -26, -26)
        p.setBrush(c)
        p.drawEllipse(core)
        if self.mode == "monitor2":  # kleines Monitor-Symbol: Farbe kommt vom Bildschirm
            from . import icons

            icons.paint(p, "monitor", core.adjusted(16, 16, -16, -16), "#ffffff", 2.2)
        p.end()


class Swatch(QPushButton):
    def __init__(self, color: str, parent=None):
        super().__init__(parent)
        self.color = color
        self.selected = False
        self.setFixedSize(34, 34)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(color)

    def paintEvent(self, _e):
        t = theme.current()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(3, 3, -3, -3)
        if self.selected:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(t.accent))
            p.drawEllipse(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5))
            r = r.adjusted(2, 2, -2, -2)
        p.setBrush(QColor(self.color))
        p.setPen(QColor(t.border))
        p.drawEllipse(r)
        p.end()


class TempBar(QWidget):
    """Temperatur als farbiger Balken (grün → orange → rot)."""

    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        self.label, self.value = label, 0.0
        self.setMinimumHeight(30)

    def set(self, value: float):
        self.value = value
        self.update()

    def paintEvent(self, _e):
        t = theme.current()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        p.setFont(font(9))
        p.setPen(QColor(t.text))
        p.drawText(QRectF(0, 0, w * 0.45, h), Qt.AlignVCenter | Qt.AlignLeft, self.label)
        color = "#22c55e" if self.value < 60 else ("#f59e0b" if self.value < 80 else "#ef4444")
        bar = QRectF(w * 0.47, h / 2 - 4, w * 0.36, 8)
        p.fillPath(rounded(bar, 4), QColor(t.surface2))
        fill = QRectF(bar.x(), bar.y(), bar.width() * max(0.02, min(1.0, self.value / 100)), bar.height())
        p.fillPath(rounded(fill, 4), QColor(color))
        p.setFont(font(9.5))
        p.drawText(QRectF(w * 0.85, 0, w * 0.15, h), Qt.AlignVCenter | Qt.AlignRight, f"{self.value:.0f} °C")
        p.end()


class HardwarePage(QWidget):
    def __init__(self, controller, parent=None, scroll: bool = True):
        super().__init__(parent)
        self.controller = controller
        self.config = controller.config
        self.rgb = controller.rgb
        inner = QWidget()
        self.lay = QVBoxLayout(inner)
        self.lay.setContentsMargins(0, 0, 8 if scroll else 0, 0)
        self.lay.setSpacing(14)
        self.lay.addWidget(self._rgb_box())
        self.lay.addWidget(self._fan_box())
        self.lay.addStretch(1)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        if scroll:
            area = QScrollArea()
            area.setWidgetResizable(True)
            area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            area.setWidget(inner)
            root.addWidget(area)
        else:  # z. B. im Setup, das schon selbst scrollt
            root.addWidget(inner)
        self.rgb.status.connect(lambda *_: self.refresh_rgb())
        self.refresh_rgb()

    # ================================================================ RGB
    def _rgb_box(self) -> QGroupBox:
        box = QGroupBox("RGB-Beleuchtung")
        outer = QHBoxLayout(box)
        outer.setSpacing(22)
        self.orb = ColorOrb()
        outer.addWidget(self.orb, 0, Qt.AlignTop)
        col = QVBoxLayout()
        col.setSpacing(10)
        self.rgb_status = Banner("", "info")
        col.addWidget(self.rgb_status)
        row = QHBoxLayout()
        self.connect_btn = button("Verbinden", "refresh", primary=True)
        self.connect_btn.clicked.connect(lambda: self.rgb.connect_async(start_if_needed=True))
        self.start_btn = button("OpenRGB starten", "play")
        self.start_btn.clicked.connect(self._start_openrgb)
        self.auto = QCheckBox("Beim Start von AluPC verbinden")
        self.auto.toggled.connect(lambda on: self.config.__setitem__("rgb", {**self.config["rgb"], "enabled": on}))
        row.addWidget(self.connect_btn)
        row.addWidget(self.start_btn)
        row.addWidget(self.auto)
        row.addStretch(1)
        col.addLayout(row)

        # Modus als Umschalter
        mode_row = QHBoxLayout()
        mode_row.setSpacing(6)
        self.mode_group = QButtonGroup(self)
        self.mode_btns = {}
        for key, label in MODES.items():
            b = QPushButton(label)
            b.setCheckable(True)
            b.setObjectName("Segment")
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, k=key: self.rgb.set_mode(k))
            self.mode_group.addButton(b)
            self.mode_btns[key] = b
            mode_row.addWidget(b)
        mode_row.addStretch(1)
        col.addLayout(mode_row)

        # Farbfelder + eigene Farbe + Helligkeit
        sw_row = QHBoxLayout()
        sw_row.setSpacing(6)
        self.swatches = []
        for c in PRESETS:
            s = Swatch(c)
            s.clicked.connect(lambda _=False, c=c: self._pick_color(c))
            self.swatches.append(s)
            sw_row.addWidget(s)
        self.custom = ColorButton(self.rgb.settings()["color"])
        self.custom.setToolTip("Eigene Farbe wählen")
        self.custom.changed.connect(self._pick_color)
        sw_row.addSpacing(8)
        sw_row.addWidget(self.custom)
        sw_row.addStretch(1)
        col.addLayout(sw_row)
        bright_row = QHBoxLayout()
        bright_row.addWidget(QLabel("Helligkeit"))
        self.bright = QSlider(Qt.Horizontal)
        self.bright.setRange(5, 100)
        self.bright.setMaximumWidth(260)
        self.bright.sliderReleased.connect(lambda: self.rgb.update_settings(brightness=self.bright.value()))
        self.bright.valueChanged.connect(lambda v: self.bright_label.setText(f"{v} %"))
        self.bright_label = QLabel()
        self.bright_label.setMinimumWidth(44)
        bright_row.addWidget(self.bright)
        bright_row.addWidget(self.bright_label)
        bright_row.addStretch(1)
        col.addLayout(bright_row)

        self.devices_box = QWidget()
        self.devices_lay = QGridLayout(self.devices_box)
        self.devices_lay.setContentsMargins(0, 4, 0, 0)
        col.addWidget(self.devices_box)
        help_text = QLabel(
            "Braucht das kostenlose <b>OpenRGB</b> (openrgb.org) – es kennt Mainboards, RAM, Grafikkarten, "
            "Lüfter-LEDs, Tastaturen … von fast allen Herstellern. In OpenRGB einmal unter <b>„SDK-Server“ → "
            "„Server starten“</b> (AluPC startet OpenRGB sonst selbst mit Server). Hersteller-Programme wie "
            "iCUE/Armoury Crate vorher beenden – sonst streiten sie sich um die LEDs.")
        help_text.setWordWrap(True)
        help_text.setObjectName("Muted")
        col.addWidget(help_text)
        outer.addLayout(col, 1)
        return box

    def _pick_color(self, color: str):
        self.custom.set_color(color)
        mode = self.rgb.settings()["mode"]
        self.rgb.update_settings(color=color, mode="farbe" if mode == "aus" else mode)
        if not self.rgb.connected:
            self.rgb.connect_async(start_if_needed=True)
        self.refresh_rgb()

    def _start_openrgb(self):
        path = find_openrgb(self.rgb.settings()["openrgb_path"])
        if not path:
            error_box(self, "OpenRGB wurde nicht gefunden. Bitte von openrgb.org installieren.")
            return
        start_openrgb(path)
        QTimer.singleShot(4000, lambda: self.rgb.connect_async())

    def refresh_rgb(self):
        s = self.rgb.settings()
        connected = self.rgb.connected
        text = self.rgb.text
        if not connected and "Verbinde" not in text and not find_openrgb(s["openrgb_path"]):
            text += "\nOpenRGB ist auf diesem PC nicht installiert."
        self.rgb_status.set(text, "ok" if connected else ("busy" if "Verbinde" in text else "info"))
        self.start_btn.setVisible(not connected and bool(find_openrgb(s["openrgb_path"])))
        self.connect_btn.setText("Neu verbinden" if connected else "Verbinden")
        self.auto.blockSignals(True)
        self.auto.setChecked(bool(s["enabled"]))
        self.auto.blockSignals(False)
        for key, b in self.mode_btns.items():
            b.setChecked(s["mode"] == key)
        for sw in self.swatches:
            sw.selected = sw.color.lower() == s["color"].lower()
            sw.update()
        self.bright.blockSignals(True)
        self.bright.setValue(int(s["brightness"]))
        self.bright.blockSignals(False)
        self.bright_label.setText(f"{int(s['brightness'])} %")
        self.orb.set(s["color"], s["mode"], int(s["brightness"]))
        # Geräte (Häkchen = wird mitgesteuert)
        while self.devices_lay.count():
            w = self.devices_lay.takeAt(0).widget()
            if w:
                w.deleteLater()
        skip = set(s["skip"])
        for i, dev in enumerate(self.rgb.devices):
            cb = QCheckBox(f"{dev.name}  ·  {dev.kind}, {dev.num_leds} LEDs")
            cb.setChecked(dev.name not in skip)
            cb.toggled.connect(lambda on, n=dev.name: self._toggle_device(n, on))
            self.devices_lay.addWidget(cb, i // 2, i % 2)
        self.devices_box.setVisible(bool(self.rgb.devices))

    def _toggle_device(self, name: str, on: bool):
        skip = [n for n in self.rgb.settings()["skip"] if n != name] + ([] if on else [name])
        self.rgb.update_settings(skip=skip)

    # ================================================================ Lüfter
    def _fan_box(self) -> QGroupBox:
        box = QGroupBox("Temperaturen und Lüfter")
        self.fan_lay = QVBoxLayout(box)
        self.fan_status = Banner("", "info")
        self.fan_lay.addWidget(self.fan_status)
        self.sensor_grid = QGridLayout()
        self.sensor_grid.setHorizontalSpacing(18)
        self.sensor_grid.setVerticalSpacing(10)
        self.fan_lay.addLayout(self.sensor_grid)
        self.pwm_box = QWidget()
        self.pwm_lay = QGridLayout(self.pwm_box)
        self.pwm_lay.setContentsMargins(0, 6, 0, 0)
        self.fan_lay.addWidget(self.pwm_box)
        self.apply_btn = button("Lüfter übernehmen", "check", primary=True)
        self.apply_btn.clicked.connect(self._apply_fans)
        apply_row = QHBoxLayout()
        apply_row.addWidget(self.apply_btn)
        apply_row.addStretch(1)
        self.fan_lay.addLayout(apply_row)
        self.temp_bars: dict[str, TempBar] = {}
        self.fan_labels: dict[str, QLabel] = {}
        self.pwm_rows: dict[str, tuple] = {}
        if sys.platform.startswith("win"):
            self.fan_status.set("Unter Windows gibt es keine allgemeine Schnittstelle für Lüfter und Temperaturen – "
                                "dafür braucht es das Programm des Mainboard-Herstellers oder z. B. „FanControl“. "
                                "Unter Linux zeigt und steuert AluPC sie hier.", "warn")
            self.pwm_box.hide()
            self.apply_btn.hide()
            return box
        self._build_sensors()
        self._fan_timer = QTimer(self, interval=2000)
        self._fan_timer.timeout.connect(self._update_sensors)
        self._fan_timer.start()
        return box

    def _build_sensors(self):
        chips = fans.read_sensors()
        if not chips:
            self.fan_status.set("Keine Sensoren gefunden. Tipp: Paket „lm-sensors“ installieren und im Terminal "
                                "„sudo sensors-detect“ ausführen.", "warn")
        row = 0
        for chip in chips:
            if not (chip.temps or chip.fans):
                continue
            title = QLabel(chip.name)
            title.setFont(font(10, QFont.DemiBold))
            self.sensor_grid.addWidget(title, row, 0, 1, 2)
            row += 1
            for label, value in chip.temps:
                bar = TempBar(label)
                bar.set(value)
                self.temp_bars[f"{chip.raw}/{label}"] = bar
                self.sensor_grid.addWidget(bar, row, 0, 1, 2)
                row += 1
            for label, rpm in chip.fans:
                name = QLabel(label)
                val = QLabel(f"{rpm} U/min" if rpm else "steht / nicht angeschlossen")
                val.setObjectName("Muted" if not rpm else "")
                self.fan_labels[f"{chip.raw}/{label}"] = val
                self.sensor_grid.addWidget(name, row, 0)
                self.sensor_grid.addWidget(val, row, 1)
                row += 1
        # Regler
        pwms = [(chip, pwm) for chip in chips for pwm in chip.pwms]
        original = dict(self.config["fans"].get("original", {}))
        for i, (chip, pwm) in enumerate(pwms):
            key = f"{chip.raw}/{pwm.id.split('/')[1]}"
            if pwm.automatic and key not in original:
                original[key] = pwm.mode  # Automatik-Modus des Mainboards merken (zum Zurückstellen)
            label = QLabel(f"{chip.name} – {pwm.label}")
            slider = QSlider(Qt.Horizontal)
            slider.setRange(fans.MIN_PERCENT, 100)
            slider.setValue(max(fans.MIN_PERCENT, pwm.percent))
            value = QLabel(f"{slider.value()} %")
            value.setMinimumWidth(44)
            auto = QCheckBox("Automatisch")
            auto.setChecked(pwm.automatic)
            slider.setEnabled(not pwm.automatic)
            slider.valueChanged.connect(lambda v, lab=value: lab.setText(f"{v} %"))
            auto.toggled.connect(lambda on, s=slider: s.setEnabled(not on))
            self.pwm_rows[pwm.id] = (key, slider, auto)
            for c, w in enumerate((label, slider, value, auto)):
                self.pwm_lay.addWidget(w, i, c)
        if original != self.config["fans"].get("original", {}):
            self.config["fans"] = {**self.config["fans"], "original": original}
        if not pwms:
            self.pwm_box.hide()
            self.apply_btn.hide()
            if chips:
                self.fan_status.set("Temperaturen und Drehzahlen werden angezeigt. Steuerbare Lüfter meldet dieser PC "
                                    "nicht (bei vielen Mainboards hilft das Paket „lm-sensors“ bzw. der Kernel-Treiber "
                                    "„nct6775“ / „it87“).", "info")
        else:
            self.fan_status.set("Lüfter-Steuerung: nie unter 30 %. „Automatisch“ gibt die Regelung zurück ans "
                                "Mainboard. Übernehmen fragt nach dem Administrator-Passwort; nach einem Neustart "
                                "regelt wieder das Mainboard.", "info")

    def _update_sensors(self):
        if not self.isVisible():
            return
        for chip in fans.read_sensors():
            for label, value in chip.temps:
                bar = self.temp_bars.get(f"{chip.raw}/{label}")
                if bar:
                    bar.set(value)
            for label, rpm in chip.fans:
                lab = self.fan_labels.get(f"{chip.raw}/{label}")
                if lab:
                    lab.setText(f"{rpm} U/min" if rpm else "steht / nicht angeschlossen")

    def fan_request(self) -> str:
        original = self.config["fans"].get("original", {})
        parts = []
        for pwm_id, (key, slider, auto) in self.pwm_rows.items():
            if auto.isChecked():
                parts.append(f"{pwm_id}=auto:{original.get(key, 2)}")
            else:
                parts.append(f"{pwm_id}={round(slider.value() * 255 / 100)}")
        return ",".join(parts)

    def _apply_fans(self):
        request = self.fan_request()
        if not request:
            return
        self.apply_btn.setEnabled(False)

        def done(_r):
            self.apply_btn.setEnabled(True)
            self.controller.message.emit("Lüfter eingestellt.")

        def failed(text):
            self.apply_btn.setEnabled(True)
            error_box(self, f"Lüfter: {text}")

        run_async(lambda: fans.set_fans(request), done, failed)

    def sizeHint(self):
        return QSize(900, 700)
