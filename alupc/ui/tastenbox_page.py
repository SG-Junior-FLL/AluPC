"""Seite „Tastenbox“: 9 Tasten (3 × 3, wie auf der Box), Drehregler mit wählbarem Ziel, LED, Anschluss.

Die Tasten der Box sind unbeschriftet – hier sieht man, welche Taste was tut, und eine gedrückte Taste leuchtet kurz
auf. Der Regler hat eine Skala: Wechselt sein Ziel, startet das neue Ziel bei 0, und der Regler greift erst, wenn er
ebenfalls auf 0 gedreht wurde (Anzeige „Auf 0 drehen“).
"""

from __future__ import annotations

import math
from pathlib import Path

from PySide6.QtCore import QEasingCurve, QPointF, QRectF, Qt, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from . import theme
from .voice_custom import action_choices
from .widgets import FlowLayout, button, font, page_header

SKETCH = Path(__file__).resolve().parents[1] / "resources" / "arduino" / "AluPC-Tasten" / "AluPC-Tasten.ino"
LED_MODES = {"live": "Leuchtet, wenn etwas live ist", "an": "Immer an", "aus": "Aus"}
CELL = 132  # 3 × 132 passt auch ins kleinste Fenster (600 px)


class KeyCap(QWidget):
    """Eine Taste der Box: zeigt, was sie tut; leuchtet auf, wenn sie gedrückt wurde."""

    clicked = Signal()

    def __init__(self, number: int, parent=None):
        super().__init__(parent)
        self.number = number
        self.text = ""
        self.long_text = ""  # Befehl bei langem Druck (klein unten)
        self.selected = False
        self.glow = 0.0
        self.setFixedSize(CELL, 92)
        self.setCursor(Qt.PointingHandCursor)
        self._anim = QVariantAnimation(self, startValue=1.0, endValue=0.0, duration=900)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.valueChanged.connect(self._set_glow)

    def _set_glow(self, v) -> None:
        self.glow = float(v)
        self.update()

    def flash(self) -> None:
        self._anim.stop()
        self._anim.start()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton and self.rect().contains(e.position().toPoint()):
            self.clicked.emit()

    def paintEvent(self, _e):
        t = theme.current()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(2, 2, -2, -2)
        rad = {"normal": 14, "holz": 6}.get(t.style, 4) * t.radius_scale
        accent = QColor(t.accent)
        # Tastenkappe: etwas heller oben (wie eine echte Taste), Rand, beim Drücken Leuchten in Akzentfarbe
        base = QColor(t.surface2)
        p.setPen(QPen(QColor(t.border), 1.2))
        p.setBrush(base)
        p.drawRoundedRect(r, rad, rad)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 14 if t.dark else 60))
        p.drawRoundedRect(r.adjusted(4, 4, -4, -r.height() * 0.5), rad * 0.7, rad * 0.7)
        if self.selected:
            p.setPen(QPen(accent, 2))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(r.adjusted(1, 1, -1, -1), rad, rad)
            p.setPen(Qt.NoPen)
        if self.glow > 0:
            g = QColor(accent)
            g.setAlphaF(0.55 * self.glow)
            p.setBrush(g)
            p.drawRoundedRect(r, rad, rad)
            p.setPen(QPen(accent, 2.5))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(r.adjusted(1, 1, -1, -1), rad, rad)
        p.setPen(QColor(t.muted))
        p.setFont(font(8, QFont.DemiBold))
        p.drawText(r.adjusted(10, 6, -10, -6), Qt.AlignLeft | Qt.AlignTop, str(self.number))
        p.setPen(QColor(t.text if self.text else t.muted))
        p.setFont(font(9 if self.long_text else 10, QFont.DemiBold))
        body = r.adjusted(8, 16, -8, -20 if self.long_text else -8)
        p.drawText(body, Qt.AlignCenter | Qt.TextWordWrap, self.text or "– frei –")
        if self.long_text:
            p.setPen(QColor(t.muted))
            p.setFont(font(7.5))
            p.drawText(r.adjusted(8, 0, -8, -6), Qt.AlignHCenter | Qt.AlignBottom,
                       p.fontMetrics().elidedText(f"lang: {self.long_text}", Qt.ElideRight, int(r.width() - 16)))
        p.end()


class KnobDial(QWidget):
    """Der Drehregler als Skala (wie auf der Box): Zeiger = Reglerstellung, darunter das Ziel."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.value: int | None = None
        self.waiting = False
        self.target = ""
        self.setFixedSize(220, 200)

    def set_state(self, value: int | None, waiting: bool, target: str) -> None:
        self.value, self.waiting, self.target = value, waiting, target
        self.update()

    @staticmethod
    def _angle(v: float) -> float:
        return math.radians(225 - 270 * v / 100)  # 0 % links unten, 100 % rechts unten

    def paintEvent(self, _e):
        t = theme.current()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        c = QPointF(self.width() / 2, 96)
        radius = 78
        accent = QColor(t.warning if self.waiting else t.accent)
        # Skala: Striche alle 10 %, lange bei 0/50/100
        for i in range(0, 101, 5):
            a = self._angle(i)
            long = i % 50 == 0
            inner = radius - (12 if long else (8 if i % 10 == 0 else 4))
            p.setPen(QPen(QColor(t.text if long else t.muted), 2 if long else 1))
            p.drawLine(QPointF(c.x() + math.cos(a) * inner, c.y() - math.sin(a) * inner),
                       QPointF(c.x() + math.cos(a) * radius, c.y() - math.sin(a) * radius))
        p.setFont(font(7.5))
        p.setPen(QColor(t.muted))
        for v, align in ((0, Qt.AlignLeft), (100, Qt.AlignRight)):
            a = self._angle(v)
            pt = QPointF(c.x() + math.cos(a) * (radius + 4), c.y() - math.sin(a) * (radius + 4))
            p.drawText(QRectF(pt.x() - 20, pt.y() + 2, 40, 14), Qt.AlignHCenter | align, str(v))
        # Bogen bis zur Stellung
        arc = QRectF(c.x() - radius + 18, c.y() - radius + 18, (radius - 18) * 2, (radius - 18) * 2)
        p.setPen(QPen(QColor(t.border), 6, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(arc, 225 * 16, -270 * 16)
        if self.value is not None:
            p.setPen(QPen(accent, 6, Qt.SolidLine, Qt.RoundCap))
            p.drawArc(arc, 225 * 16, round(-270 * 16 * self.value / 100))
            a = self._angle(self.value)
            p.setPen(QPen(accent, 3, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(c, QPointF(c.x() + math.cos(a) * (radius - 26), c.y() - math.sin(a) * (radius - 26)))
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(t.surface2))
        p.drawEllipse(c, 26, 26)
        p.setPen(QColor(t.text))
        p.setFont(font(13, QFont.Bold))
        p.drawText(QRectF(c.x() - 30, c.y() - 14, 60, 28), Qt.AlignCenter,
                   "–" if self.value is None else f"{self.value}")
        p.setFont(font(9, QFont.DemiBold))
        p.setPen(accent if self.waiting else QColor(t.muted))
        text = "↺ Auf 0 drehen" if self.waiting else (self.target or "")
        p.drawText(QRectF(0, self.height() - 26, self.width(), 22), Qt.AlignCenter, text)
        p.end()


class TastenboxPage(QWidget):
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = c = controller
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(14)
        root.addWidget(page_header("Tastenbox", "9 Tasten und ein Drehregler am USB (Arduino Pro Micro)", "grid"))
        self.status = QLabel()
        self.status.setWordWrap(True)
        root.addWidget(self.status)

        cols = FlowLayout(spacing=14)  # breit: Tasten links, Regler rechts – schmal: untereinander
        holder = QWidget()
        holder.setLayout(cols)
        root.addWidget(holder)

        # ---- Tasten 3 × 3, wie auf der Box
        keys_box = QGroupBox("Tasten")
        kl = QVBoxLayout(keys_box)
        hint = QLabel("Wie auf der Box angeordnet. Taste antippen, unten wählen, was sie tut.")
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        kl.addWidget(hint)
        grid_box = QWidget()
        grid = QGridLayout(grid_box)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(8)
        self.choices = [("", "– nichts –")] + action_choices(c.config)
        self.caps: dict[int, KeyCap] = {}
        for n in range(1, 10):
            cap = KeyCap(n)
            cap.clicked.connect(lambda n=n: self.select(n))
            grid.addWidget(cap, (n - 1) // 3, (n - 1) % 3)
            self.caps[n] = cap
        kl.addWidget(grid_box, 0, Qt.AlignLeft)
        row = QHBoxLayout()
        self.key_label = QLabel()
        self.key_label.setObjectName("Muted")
        self.action = QComboBox()
        self.action.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.action.setMinimumContentsLength(16)
        for key, label in self.choices:
            self.action.addItem(label, key)
        self.action.activated.connect(lambda _i: self._set_key(self.action.currentData() or ""))
        row.addWidget(self.key_label)
        row.addWidget(self.action, 1)
        kl.addLayout(row)
        long_row = QHBoxLayout()
        long_label = QLabel("Lang:")
        long_label.setObjectName("Muted")
        long_label.setToolTip("Taste länger als 0,6 s halten (Arduino-Programm ab Version 2)")
        self.long_action = QComboBox()
        self.long_action.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.long_action.setMinimumContentsLength(16)
        self.long_action.addItem("– wie kurz –", "")
        for key, label in self.choices[1:]:
            self.long_action.addItem(label, key)
        self.long_action.activated.connect(lambda _i: self._set_long(self.long_action.currentData() or ""))
        long_row.addWidget(long_label)
        long_row.addWidget(self.long_action, 1)
        kl.addLayout(long_row)
        cols.addWidget(keys_box)

        # ---- Regler
        knob_box = QGroupBox("Drehregler")
        rl = QVBoxLayout(knob_box)
        self.dial = KnobDial()
        rl.addWidget(self.dial, 0, Qt.AlignHCenter)
        form = QFormLayout()
        self.target = QComboBox()
        self.target.setToolTip("Wechselt das Ziel, startet es bei 0 – den Regler dann auch auf 0 drehen.")
        self._fill_targets()
        self.target.activated.connect(lambda _i: c.set_knob_target(self.target.currentData()))
        form.addRow("Regelt:", self.target)
        self.only = QCheckBox("PC-Ton nur am Regler")
        self.only.setToolTip("Andere Wege (Windows, Tastatur, Handy, Sprache) werden zurückgestellt. "
                             "Programme einzeln (Seite Audio) gehen weiter.")
        self.only.setChecked(bool(c.config["tasten"].get("nur_regler", True)))
        self.only.toggled.connect(lambda v: self._save(nur_regler=v))
        cfg = c.config["tasten"]
        self.invert = QCheckBox("Richtung umkehren")
        self.invert.setChecked(bool(cfg.get("umkehren")))
        self.invert.toggled.connect(lambda v: self._save(umkehren=v))
        self.pickup = QCheckBox("Bei Wechsel erst auf 0")
        self.pickup.setToolTip("Aus: das neue Ziel springt sofort auf die Reglerstellung")
        self.pickup.setChecked(bool(cfg.get("abgleich", True)))
        self.pickup.toggled.connect(lambda v: self._save(abgleich=v))
        self.top = QSpinBox()
        self.top.setRange(10, 100)
        self.top.setSingleStep(5)
        self.top.setSuffix(" %")
        self.top.setToolTip("Ganz aufgedreht = dieser Wert (z. B. nie lauter als 80 %)")
        self.top.setValue(int(cfg.get("max", 100) or 100))
        self.top.valueChanged.connect(lambda v: self._save(max=v))
        form.addRow("Höchstens:", self.top)
        rl.addLayout(form)
        for box in (self.only, self.invert, self.pickup):
            rl.addWidget(box)
        knob_box.setFixedWidth(320)
        cols.addWidget(knob_box)

        # ---- Box: an/aus, LED, Anschluss, Programm
        dev = QGroupBox("Box")
        dl = QVBoxLayout(dev)
        df = QFormLayout()
        on = QCheckBox("Tastenbox suchen und benutzen")
        on.setChecked(bool(c.config["tasten"].get("on", True)))
        on.toggled.connect(lambda v: self._save(on=v))
        df.addRow("", on)
        led = QComboBox()
        for key, label in LED_MODES.items():
            led.addItem(label, key)
        led.setCurrentIndex(max(0, led.findData(c.config["tasten"].get("led", "live"))))
        led.currentIndexChanged.connect(lambda _i: self._save(led=led.currentData()))
        df.addRow("LED:", led)
        bright = QSpinBox()
        bright.setRange(5, 100)
        bright.setSingleStep(5)
        bright.setSuffix(" %")
        bright.setValue(c.box_led_brightness())
        bright.valueChanged.connect(lambda v: self._save(led_hell=v))
        df.addRow("Helligkeit:", bright)
        blink = QCheckBox("LED blitzt bei jedem Tastendruck")
        blink.setChecked(bool(c.config["tasten"].get("led_blink", False)))
        blink.toggled.connect(lambda v: self._save(led_blink=v))
        df.addRow("", blink)
        self.port = QComboBox()
        self.port.addItem("Automatisch", "")
        self._fill_ports()
        self.port.currentIndexChanged.connect(lambda _i: self._save(port=self.port.currentData()))
        df.addRow("Anschluss:", self.port)
        dl.addLayout(df)
        sketch = button("Arduino-Programm speichern …", "download")
        sketch.clicked.connect(self._save_sketch)
        dl.addWidget(sketch, 0, Qt.AlignLeft)
        wiring = QLabel("Tasten an D2–D8, D14, D15 und GND · Regler (10 kΩ) Mitte an A0, außen an VCC und GND · "
                        "LED über 220 Ω an D9 oder LED-Streifen WS2812B an D10.")
        wiring.setObjectName("Muted")
        wiring.setWordWrap(True)
        dl.addWidget(wiring)
        root.addWidget(dev)
        root.addStretch(1)

        bb = c.buttonbox
        bb.state_changed.connect(self.refresh)
        bb.state_changed.connect(self._fill_ports)
        bb.key.connect(self._pressed)
        bb.long_key.connect(self._pressed)
        bb.volume.connect(lambda _v: self.refresh())
        c.changed.connect(self.refresh)
        self.select(1)
        self.refresh()

    # ------------------------------------------------------------ Speichern
    def _save(self, **changes) -> None:
        c = self.controller
        c.config["tasten"] = {**c.config["tasten"], **changes}
        c.apply_buttonbox()

    def _set_key(self, action: str) -> None:
        keys = self.controller.box_keys()
        keys[str(self.selected)] = action
        self._save(keys=keys)
        self.refresh()

    def _set_long(self, action: str) -> None:
        cfg = self.controller.config["tasten"]
        lang = {**(cfg.get("lang") or {}), str(self.selected): action}
        self._save(lang={k: v for k, v in lang.items() if v})
        self.refresh()

    def select(self, n: int) -> None:
        """Taste n bearbeiten (Klick auf die Kappe oder Druck auf die echte Taste)."""
        self.selected = n
        for k, cap in self.caps.items():
            cap.selected = k == n
            cap.update()
        current = self.controller.box_keys().get(str(n), "")
        if current and self.action.findData(current) < 0:
            self.action.addItem(current, current)  # z. B. gelöschte Szene: nicht still verlieren
        self.action.setCurrentIndex(max(0, self.action.findData(current)))
        self.key_label.setText(f"Taste {n}:")
        long = (self.controller.config["tasten"].get("lang") or {}).get(str(n), "")
        if long and self.long_action.findData(long) < 0:
            self.long_action.addItem(long, long)
        self.long_action.setCurrentIndex(max(0, self.long_action.findData(long)))

    def _save_sketch(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Arduino-Programm speichern", str(Path.home() / SKETCH.name),
                                              "Arduino-Sketch (*.ino)")
        if path:
            Path(path).write_text(SKETCH.read_text(encoding="utf-8"), encoding="utf-8")
            self.controller.message.emit("Gespeichert. Mit der Arduino-IDE auf den Pro Micro laden "
                                         "(Board: Arduino Leonardo).")

    # ------------------------------------------------------------ Listen
    def _fill_targets(self) -> None:
        c = self.controller
        current = c.knob_target()
        items = list(c.KNOB_TARGETS.items())
        try:
            from .. import mixer

            apps = sorted({s.get("app", "") for s in mixer.streams("out") if s.get("app")})
        except Exception:  # noqa: BLE001
            apps = []
        if current.startswith("app:") and current[4:] not in apps:
            apps.append(current[4:])  # Programm läuft gerade nicht: Auswahl trotzdem behalten
        items += [(f"app:{a}", f"Programm: {a}") for a in apps]
        self.target.blockSignals(True)
        self.target.clear()
        for key, label in items:
            self.target.addItem(label, key)
        self.target.setCurrentIndex(max(0, self.target.findData(current)))
        self.target.blockSignals(False)

    def showEvent(self, e):
        super().showEvent(e)
        self._fill_targets()  # Programme mit Ton ändern sich

    def _fill_ports(self) -> None:
        from ..tastenbox import candidate_ports

        current = self.controller.config["tasten"].get("port", "")
        ports = candidate_ports()
        self.port.blockSignals(True)
        while self.port.count() > 1:
            self.port.removeItem(1)
        for dev in ports + ([current] if current and current not in ports else []):
            self.port.addItem(dev, dev)
        self.port.setCurrentIndex(max(0, self.port.findData(current)))
        self.port.blockSignals(False)

    # ------------------------------------------------------------ Anzeige
    def _pressed(self, n: int) -> None:
        cap = self.caps.get(n)
        if cap is not None:
            cap.flash()
            self.select(n)  # echte Taste drücken = diese Taste bearbeiten

    def refresh(self) -> None:
        c = self.controller
        bb = c.buttonbox
        if not c.config["tasten"].get("on", True):
            self.status.setText("Aus.")
        elif bb.connected:
            lock = " · PC-Lautstärke nur am Regler" if c.volume_locked() else ""
            self.status.setText(f"✓ Verbunden ({bb.port}){lock}")
        else:
            self.status.setText("Nicht gefunden – Box einstecken, AluPC sucht alle paar Sekunden.")
        labels = dict(self.choices)
        keys = c.box_keys()
        longs = c.config["tasten"].get("lang") or {}
        for n, cap in self.caps.items():
            action = keys.get(str(n), "")
            cap.text = labels.get(action, action)
            long = longs.get(str(n), "")
            cap.long_text = labels.get(long, long) if long else ""
            cap.update()
        self.dial.set_state(bb.knob if bb.connected else None, c.knob_wait, c.knob_target_label())
        self.only.setEnabled(c.knob_target() == "pc")  # Sperre gilt nur, wenn der Regler den PC-Ton regelt
        if self.target.currentData() != c.knob_target():
            self._fill_targets()
