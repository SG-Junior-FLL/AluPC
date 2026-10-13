"""Whiteboard-Einstellungen – dasselbe Formular im Whiteboard-Fenster (Zahnrad) und in Setup → „Whiteboard“."""

from __future__ import annotations

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from ..board import FORMATS, PALETTE, boards_dir
from ..whiteboard import BACKGROUNDS
from .util import ColorButton
from .widgets import button


def _slider(lo: int, hi: int, value: float, on_change, suffix: str = "") -> QWidget:
    holder = QWidget()
    row = QHBoxLayout(holder)
    row.setContentsMargins(0, 0, 0, 0)
    s = QSlider(Qt.Horizontal)
    s.setRange(lo, hi)
    s.setValue(int(round(value)))
    lab = QLabel(f"{int(round(value))}{suffix}")
    lab.setMinimumWidth(48)
    s.valueChanged.connect(lambda v: (lab.setText(f"{v}{suffix}"), on_change(v)))
    row.addWidget(s, 1)
    row.addWidget(lab)
    holder.slider = s
    return holder


def board_settings_widget(board) -> QWidget:
    """Alle Whiteboard-Einstellungen; jede Änderung gilt sofort (board.set_settings)."""
    cfg = board.settings()
    root = QWidget()
    lay = QVBoxLayout(root)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(10)
    root.controls = {}

    page = QGroupBox("Seiten")
    f = QFormLayout(page)
    fmt = QComboBox()
    for key, (label, _w, _h) in FORMATS.items():
        fmt.addItem(label, key)
    fmt.setCurrentIndex(max(0, fmt.findData(cfg["format"])))
    fmt.currentIndexChanged.connect(lambda _i: (board.set_settings(format=fmt.currentData()), board.fit()))
    f.addRow("Format:", fmt)
    bg = QComboBox()
    for key, (label, _dark) in BACKGROUNDS.items():
        bg.addItem(label, key)
    bg.setCurrentIndex(max(0, bg.findData(cfg["background"])))
    bg.currentIndexChanged.connect(lambda _i: board.set_settings(background=bg.currentData()))
    f.addRow("Hintergrund für neue Seiten:", bg)
    root.controls.update(format=fmt, background=bg)
    lay.addWidget(page)

    pen = QGroupBox("Stift")
    f = QFormLayout(pen)
    root.controls["width"] = _slider(1, 20, cfg["width"], lambda v: board.set_settings(width=float(v)))
    f.addRow("Stift-Stärke:", root.controls["width"])
    root.controls["marker_width"] = _slider(6, 60, cfg["marker_width"],
                                            lambda v: board.set_settings(marker_width=float(v)))
    f.addRow("Marker-Stärke:", root.controls["marker_width"])
    smooth = QComboBox()
    for label, v in (("Aus (genau wie gezeichnet)", 0), ("Leicht", 1), ("Stark (sehr ruhige Linien)", 2)):
        smooth.addItem(label, v)
    smooth.setCurrentIndex(max(0, smooth.findData(int(cfg["smooth"]))))
    smooth.currentIndexChanged.connect(lambda _i: board.set_settings(smooth=smooth.currentData()))
    f.addRow("Glätten:", smooth)
    pressure = QCheckBox("Druckempfindlich (Apple Pencil, Grafiktablett, Stift)")
    pressure.setChecked(bool(cfg["pressure"]))
    pressure.toggled.connect(lambda on: board.set_settings(pressure=on))
    f.addRow(pressure)
    pencil = QCheckBox("Nur der Stift zeichnet – Finger verschieben und zoomen (Handballen-Schutz)")
    pencil.setChecked(bool(cfg["pencil_only"]))
    pencil.toggled.connect(lambda on: board.set_settings(pencil_only=on))
    f.addRow(pencil)
    root.controls["eraser"] = _slider(6, 80, cfg["eraser"], lambda v: board.set_settings(eraser=float(v)))
    f.addRow("Radierer-Größe:", root.controls["eraser"])
    root.controls["text_size"] = _slider(14, 120, cfg["text_size"], lambda v: board.set_settings(text_size=float(v)))
    f.addRow("Textgröße:", root.controls["text_size"])
    root.controls.update(smooth=smooth, pressure=pressure, pencil_only=pencil)
    lay.addWidget(pen)

    colors = QGroupBox("Eigene Farben (Werkzeugleiste und Handy)")
    g = QGridLayout(colors)
    buttons = []

    def save_colors(*_):
        board.set_settings(colors=[b.color() for b in buttons])

    for i, c in enumerate(cfg["colors"]):
        b = ColorButton(c)
        b.setMinimumHeight(30)
        b.changed.connect(save_colors)
        buttons.append(b)
        g.addWidget(b, i // 4, i % 4)
    reset = button("Standardfarben", "refresh")
    reset.clicked.connect(lambda: ([b.set_color(c) for b, c in zip(buttons, PALETTE)], save_colors()))
    g.addWidget(reset, 2, 0, 1, 4)
    root.controls["colors"] = buttons
    lay.addWidget(colors)

    guests = QGroupBox("Gäste im AluPC-WLAN")
    g = QFormLayout(guests)
    from ..board_guests import MODES

    mode = QComboBox()
    for key, label in MODES.items():
        mode.addItem(label, key)
    mode.setCurrentIndex(max(0, mode.findData(cfg["guests"])))
    mode.currentIndexChanged.connect(lambda _i: board.set_settings(guests=mode.currentData()))
    g.addRow("Mitschreiben:", mode)
    note = QLabel("Auf der Anmeldeseite erscheint dann „Whiteboard“. Gäste schreiben nur, solange die Tafel auf "
                  "Monitor 2 zu sehen ist – radieren und Seiten wechseln bleibt beim PC.")
    note.setWordWrap(True)
    note.setObjectName("Muted")
    g.addRow(note)
    root.controls["guests"] = mode
    lay.addWidget(guests)

    other = QGroupBox("Speichern")
    f = QFormLayout(other)
    auto = QCheckBox("Automatisch speichern (jede Änderung)")
    auto.setChecked(bool(cfg["autosave"]))
    auto.toggled.connect(lambda on: board.set_settings(autosave=on))
    f.addRow(auto)
    folder = button("Ordner mit den Tafeln öffnen", "image")
    folder.clicked.connect(lambda: (boards_dir().mkdir(parents=True, exist_ok=True),
                                    QDesktopServices.openUrl(QUrl.fromLocalFile(str(boards_dir())))))
    f.addRow(folder)
    root.controls["autosave"] = auto
    lay.addWidget(other)
    return root


class BoardSettingsDialog(QDialog):
    def __init__(self, board, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Whiteboard – Einstellungen")
        self.setMinimumWidth(560)
        lay = QVBoxLayout(self)
        self.form = board_settings_widget(board)
        lay.addWidget(self.form)
        done = button("Fertig", "check", primary=True)
        done.clicked.connect(self.accept)
        lay.addWidget(done, 0, Qt.AlignRight)
