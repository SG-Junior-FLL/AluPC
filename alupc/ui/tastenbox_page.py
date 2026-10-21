"""Setup → Tastenbox: Status, Belegung der 9 Tasten (3 × 3), Lautstärke nur am Regler, LED."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from .voice_custom import action_choices
from .widgets import FlowLayout, button

SKETCH = Path(__file__).resolve().parents[1] / "resources" / "arduino" / "AluPC-Tasten" / "AluPC-Tasten.ino"
LED_MODES = {"live": "Leuchtet, wenn etwas live ist", "an": "Immer an", "aus": "Aus"}


def tastenbox_group(setup) -> QGroupBox:
    c = setup.controller
    box = QGroupBox("Tastenbox")
    lay = QVBoxLayout(box)
    lay.setSpacing(10)
    status = QLabel()
    status.setWordWrap(True)
    lay.addWidget(status)
    cfg = c.config["tasten"]

    def save(**changes):
        c.config["tasten"] = {**c.config["tasten"], **changes}
        c.apply_buttonbox()

    form = QFormLayout()
    on = QCheckBox("Tastenbox suchen und benutzen")
    on.setChecked(bool(cfg.get("on", True)))
    on.toggled.connect(lambda v: save(on=v))
    form.addRow("", on)
    only = QCheckBox("Lautstärke nur am Regler")
    only.setToolTip("Andere Wege (Windows, Tastatur, Handy, Sprache) werden zurückgestellt. "
                    "Programme einzeln (Seite Audio) gehen weiter.")
    only.setChecked(bool(cfg.get("nur_regler", True)))
    only.toggled.connect(lambda v: save(nur_regler=v))
    form.addRow("Regler:", only)
    led = QComboBox()
    for key, label in LED_MODES.items():
        led.addItem(label, key)
    led.setCurrentIndex(max(0, led.findData(cfg.get("led", "live"))))
    led.currentIndexChanged.connect(lambda _i: save(led=led.currentData()))
    form.addRow("LED:", led)
    port = QComboBox()
    port.addItem("Automatisch", "")

    def fill_ports():
        from ..tastenbox import candidate_ports

        current = c.config["tasten"].get("port", "")
        port.blockSignals(True)
        while port.count() > 1:
            port.removeItem(1)
        for dev in candidate_ports() + ([current] if current and current not in candidate_ports() else []):
            port.addItem(dev, dev)
        port.setCurrentIndex(max(0, port.findData(current)))
        port.blockSignals(False)

    fill_ports()
    port.currentIndexChanged.connect(lambda _i: save(port=port.currentData()))
    form.addRow("Anschluss:", port)
    lay.addLayout(form)

    # Belegung wie die Tasten auf der Box: 3 × 3
    grid_box = QWidget()
    grid = FlowLayout(grid_box, spacing=8)  # breit: 3 × 3 wie auf der Box, schmal: bricht um
    grid_box.setMaximumWidth(3 * 170 + 2 * 8)
    choices = [("", "– nichts –")] + action_choices(c.config)
    keys = c.box_keys()
    combos: dict[int, QComboBox] = {}
    labels: dict[int, QLabel] = {}
    for n in range(1, 10):
        cell = QWidget()
        cl = QVBoxLayout(cell)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(3)
        title = QLabel(f"Taste {n}")
        title.setObjectName("Muted")
        combo = QComboBox()
        combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        combo.setMinimumContentsLength(10)
        for key, label in choices:
            combo.addItem(label, key)
        current = keys.get(str(n), "")
        if current and combo.findData(current) < 0:
            combo.addItem(current, current)  # z. B. gelöschte Szene: nicht still verlieren
        combo.setCurrentIndex(max(0, combo.findData(current)))
        combo.currentIndexChanged.connect(lambda _i, k=n: save_keys())
        cl.addWidget(title)
        cl.addWidget(combo)
        cell.setFixedWidth(170)
        grid.addWidget(cell)
        combos[n] = combo
        labels[n] = title

    def save_keys():
        save(keys={str(n): combo.currentData() or "" for n, combo in combos.items()})

    lay.addWidget(grid_box)

    def save_sketch():
        path, _ = QFileDialog.getSaveFileName(box, "Arduino-Programm speichern", str(Path.home() / SKETCH.name),
                                              "Arduino-Sketch (*.ino)")
        if path:
            Path(path).write_text(SKETCH.read_text(encoding="utf-8"), encoding="utf-8")
            c.message.emit("Gespeichert. Mit der Arduino-IDE auf den Pro Micro laden (Board: Arduino Leonardo).")

    sketch = button("Arduino-Programm speichern …", "download")
    sketch.clicked.connect(save_sketch)
    lay.addWidget(sketch)
    wiring = QLabel("Anschluss: Tasten an D2–D8, D14, D15 und GND · Regler (10 kΩ) Mitte an A0, außen an VCC und "
                    "GND · LED über 220 Ω an D9 oder LED-Streifen WS2812B an D10.")
    wiring.setObjectName("Muted")
    wiring.setWordWrap(True)
    lay.addWidget(wiring)

    def refresh():
        bb = c.buttonbox
        if not c.config["tasten"].get("on", True):
            status.setText("Aus.")
        elif bb.connected:
            knob = f", Regler {bb.knob} %" if bb.knob is not None else ""
            lock = " · Lautstärke nur am Regler" if c.volume_locked() else ""
            status.setText(f"✓ Verbunden ({bb.port}{knob}){lock}")
        else:
            status.setText("Nicht gefunden – Box einstecken, AluPC sucht alle paar Sekunden.")
        for n, title in labels.items():
            title.setText(f"Taste {n}" + ("  ●" if n == bb.last_key and bb.connected else ""))

    c.buttonbox.state_changed.connect(refresh)
    c.buttonbox.key.connect(lambda _n: refresh())
    c.buttonbox.volume.connect(lambda _v: refresh())
    c.buttonbox.state_changed.connect(fill_ports)
    refresh()
    box.tastenbox_refresh = refresh  # für Tests
    return box
