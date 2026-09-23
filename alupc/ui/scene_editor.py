"""Eigene Szenen bauen: Layout-Vorlage wählen und Felder mit Quellen füllen."""

from __future__ import annotations

import copy

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QListView,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from ..scenes import LAYOUTS, describe_source, layout_slots, new_scene, resize_slots
from .source_picker import SourcePicker
from .util import ColorButton


def layout_icon(layout: str, size: QSize = QSize(96, 54)) -> QIcon:
    """Schematisches Bild einer Layout-Vorlage (keine Live-Vorschau)."""
    pix = QPixmap(size)
    pix.fill(QColor("#202020"))
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    colors = ["#3d7ab8", "#e0913b", "#5aa469", "#b85a9e"]
    for i, (x, y, w, h, _name) in enumerate(layout_slots(layout)):
        rect = QRectF(x * size.width(), y * size.height(), w * size.width(), h * size.height()).adjusted(2, 2, -2, -2)
        p.fillRect(rect, QColor(colors[i % len(colors)]))
        p.setPen(QPen(Qt.white))
        p.drawText(rect, Qt.AlignCenter, str(i + 1))
    p.end()
    return QIcon(pix)


class SceneEditor(QDialog):
    def __init__(self, config, scene: dict | None = None, parent=None):
        super().__init__(parent)
        self.config = config
        self.original_name = scene["name"] if scene else None
        self.scene = copy.deepcopy(scene) if scene else new_scene(self._free_name())
        self.setWindowTitle("Szene bearbeiten" if scene else "Neue Szene")
        self.resize(720, 560)

        self.name_edit = QLineEdit(self.scene["name"])
        self.bg_button = ColorButton(self.scene.get("background", "#000000"))

        self.layout_list = QListWidget()
        self.layout_list.setViewMode(QListView.IconMode)
        self.layout_list.setIconSize(QSize(96, 54))
        self.layout_list.setResizeMode(QListView.Adjust)
        self.layout_list.setMovement(QListView.Static)
        self.layout_list.setGridSize(QSize(170, 100))
        self.layout_list.setWordWrap(True)
        self.layout_list.setFixedHeight(200)
        for key, (label, _slots) in LAYOUTS.items():
            item = QListWidgetItem(layout_icon(key), label)
            item.setData(Qt.UserRole, key)
            self.layout_list.addItem(item)
            if key == self.scene["layout"]:
                self.layout_list.setCurrentItem(item)
        self.layout_list.currentItemChanged.connect(self._layout_changed)

        self.slots_box = QGroupBox("Felder – in jedes Feld eine Quelle legen")
        self.slots_grid = QGridLayout(self.slots_box)

        form = QFormLayout()
        form.addRow("Name:", self.name_edit)
        form.addRow("Hintergrundfarbe:", self.bg_button)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText("Speichern")
        buttons.button(QDialogButtonBox.Cancel).setText("Abbrechen")
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)

        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(QLabel("Layout-Vorlage:"))
        lay.addWidget(self.layout_list)
        lay.addWidget(self.slots_box, 1)
        lay.addWidget(buttons)
        self._rebuild_slots()

    def _free_name(self) -> str:
        names = set(self.config.scene_names())
        i = 1
        while f"Szene {i}" in names:
            i += 1
        return f"Szene {i}"

    def _layout_changed(self, item, _prev):
        if item is not None:
            self.scene = resize_slots(self.scene, item.data(Qt.UserRole))
            self._rebuild_slots()

    def _rebuild_slots(self):
        while self.slots_grid.count():
            w = self.slots_grid.takeAt(0).widget()
            if w:
                w.deleteLater()
        for i, (_x, _y, _w, _h, name) in enumerate(layout_slots(self.scene["layout"])):
            slot = self.scene["slots"][i]
            label = QLabel(f"<b>{i + 1}. {name}</b>")
            desc = QLabel(describe_source(slot))
            desc.setWordWrap(True)
            choose = QPushButton("Quelle wählen …")
            clear = QPushButton("Leeren")
            clear.setEnabled(slot is not None)
            choose.clicked.connect(lambda _=False, idx=i: self._choose(idx))
            clear.clicked.connect(lambda _=False, idx=i: self._clear(idx))
            self.slots_grid.addWidget(label, i, 0)
            self.slots_grid.addWidget(desc, i, 1)
            self.slots_grid.addWidget(choose, i, 2)
            self.slots_grid.addWidget(clear, i, 3)
        self.slots_grid.setColumnStretch(1, 1)
        self.slots_grid.setRowStretch(len(self.scene["slots"]), 1)

    def _choose(self, idx):
        picker = SourcePicker(self.config, self, self.scene["slots"][idx],
                              scene_name=self.original_name or self.name_edit.text())
        if picker.exec() == QDialog.Accepted:
            cfg = picker.result_config()
            if cfg is None:
                QMessageBox.information(self, "Quelle", "Bitte alle nötigen Angaben machen.")
                return
            self.scene["slots"][idx] = cfg
            self._rebuild_slots()

    def _clear(self, idx):
        self.scene["slots"][idx] = None
        self._rebuild_slots()

    def _save(self):
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Szene", "Bitte einen Namen eingeben.")
            return
        if name != self.original_name and name in self.config.scene_names():
            QMessageBox.warning(self, "Szene", f"Eine Szene „{name}“ gibt es schon.")
            return
        if not any(self.scene["slots"]):
            QMessageBox.warning(self, "Szene", "Bitte mindestens ein Feld mit einer Quelle füllen.")
            return
        self.scene["name"] = name
        self.scene["background"] = self.bg_button.color()
        self.config.put_scene(self.scene, self.original_name)
        self.accept()
