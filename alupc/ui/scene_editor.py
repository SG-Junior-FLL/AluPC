"""Eigene Szenen bauen: Layout-Vorlage wählen und Felder mit Quellen füllen."""

from __future__ import annotations

import copy

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QSpinBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QListView,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QHBoxLayout,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..scenes import LAYOUTS, describe_source, layout_slots, new_scene, resize_slots
from .hotkey_edit import HotkeyButton
from .source_picker import SourcePicker
from . import icons, theme
from .util import ColorButton
from .widgets import button, page_header, paint_scene_thumb


def layout_icon(layout: str, size: QSize = QSize(112, 63)) -> QIcon:
    """Schematisches Bild einer Layout-Vorlage (keine Live-Vorschau)."""
    dpr = 2
    pix = QPixmap(size.width() * dpr, size.height() * dpr)
    pix.setDevicePixelRatio(dpr)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    paint_scene_thumb(p, QRectF(0, 0, size.width(), size.height()), None, layout, numbers=True)
    p.end()
    return QIcon(pix)


class ScenePreview(QWidget):
    """Schema der Szene, wie sie gerade im Editor eingestellt ist (Quellen als farbige Felder)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = None
        self.setMinimumSize(240, 135)

    def set_scene(self, scene):
        self.scene = scene
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        w = self.width()
        h = min(self.height(), w * 9 / 16)
        w = h * 16 / 9
        paint_scene_thumb(p, QRectF((self.width() - w) / 2, 0, w, h), self.scene)
        p.end()


class SceneEditor(QDialog):
    def __init__(self, config, scene: dict | None = None, parent=None, template: dict | None = None):
        super().__init__(parent)
        self.config = config
        self.original_name = scene["name"] if scene else None
        if template is not None:  # neue Szene aus einer Vorlage: vorausgefüllt, noch nicht gespeichert
            self.scene = copy.deepcopy(template)
            self.scene["name"] = self._free_name(template.get("name") or "Szene")
        else:
            self.scene = copy.deepcopy(scene) if scene else new_scene(self._free_name())
        self.setWindowTitle("Szene bearbeiten" if scene else ("Neue Szene aus Vorlage" if template else "Neue Szene"))
        self.resize(1060, 720)

        self.name_edit = QLineEdit(self.scene["name"])
        self.bg_button = ColorButton(self.scene.get("background", "#000000"))

        self.layout_list = QListWidget()
        self.layout_list.setViewMode(QListView.IconMode)
        self.layout_list.setIconSize(QSize(112, 63))
        self.layout_list.setResizeMode(QListView.Adjust)
        self.layout_list.setMovement(QListView.Static)
        self.layout_list.setGridSize(QSize(164, 126))
        self.layout_list.setWordWrap(True)
        self.layout_list.setTextElideMode(Qt.ElideNone)
        self.layout_list.setFixedHeight(276)
        self.layout_list.setSpacing(4)
        for key, (label, _slots) in LAYOUTS.items():
            item = QListWidgetItem(layout_icon(key), label)
            item.setData(Qt.UserRole, key)
            item.setToolTip(label)
            item.setSizeHint(QSize(156, 118))
            self.layout_list.addItem(item)
            if key == self.scene["layout"]:
                self.layout_list.setCurrentItem(item)
        self.layout_list.currentItemChanged.connect(self._layout_changed)

        self.slots_box = QGroupBox("Felder")
        self.slots_grid = QGridLayout(self.slots_box)

        form = QFormLayout()
        form.addRow("Name:", self.name_edit)
        form.addRow("Hintergrundfarbe:", self.bg_button)
        self.hotkey_edit = HotkeyButton(
            config["hotkeys"].get(f"szene:{self.original_name}", "") if self.original_name else "",
            "Tastenkürzel für diese Szene")
        form.addRow("Tastenkürzel:", self.hotkey_edit)
        from ..transitions import TRANSITIONS

        tr = self.scene.get("transition") or {}
        self.transition_combo = QComboBox()
        self.transition_combo.addItem("Standard (wie im Setup eingestellt)", "")
        for key, label in TRANSITIONS.items():
            self.transition_combo.addItem(label, key)
        self.transition_combo.setCurrentIndex(max(0, self.transition_combo.findData(tr.get("type", ""))))
        self.transition_ms = QSpinBox()
        self.transition_ms.setRange(0, 5000)
        self.transition_ms.setSingleStep(50)
        self.transition_ms.setSuffix(" ms")
        self.transition_ms.setSpecialValueText("Standard-Dauer")
        self.transition_ms.setValue(int(tr.get("ms", 0) or 0))
        self.transition_combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.transition_combo.setMinimumContentsLength(10)
        tr_row = QHBoxLayout()
        tr_row.addWidget(self.transition_combo, 1)
        tr_row.addWidget(self.transition_ms)
        form.addRow("Übergang:", tr_row)

        buttons = QDialogButtonBox()
        buttons.addButton(button("Speichern", "check", primary=True), QDialogButtonBox.AcceptRole)
        buttons.addButton(button("Abbrechen"), QDialogButtonBox.RejectRole)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)

        # Studio-Aufbau: links die Schritte (Allgemein → Layout → Felder), rechts Vorschau + Speichern
        self.preview = ScenePreview()
        self.preview.setFixedSize(292, 164)
        general = QGroupBox("Allgemein")
        general.setLayout(form)
        layout_box = QGroupBox("Layout")
        QVBoxLayout(layout_box).addWidget(self.layout_list)
        steps = QWidget()
        sl = QVBoxLayout(steps)
        sl.setContentsMargins(0, 0, 8, 0)
        sl.setSpacing(6)
        sl.addWidget(general)
        sl.addWidget(layout_box)
        sl.addWidget(self.slots_box)
        sl.addStretch(1)
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        area.setWidget(steps)

        side = QFrame()
        side.setObjectName("Card")
        side.setAttribute(Qt.WA_StyledBackground, True)
        side.setFixedWidth(328)
        side_lay = QVBoxLayout(side)
        side_lay.setContentsMargins(18, 18, 18, 18)
        side_lay.setSpacing(10)
        side_lay.addWidget(self.preview)
        self.preview_note = QLabel()
        self.preview_note.setObjectName("Muted")
        self.preview_note.setWordWrap(True)
        side_lay.addWidget(self.preview_note)
        side_lay.addStretch(1)
        buttons.setOrientation(Qt.Vertical)
        for b in buttons.buttons():
            b.setMinimumWidth(290)
        side_lay.addWidget(buttons)

        body = QHBoxLayout()
        body.setSpacing(18)
        body.addWidget(area, 1)
        body.addWidget(side)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 20, 22, 18)
        lay.setSpacing(14)
        lay.addWidget(page_header("Szene bearbeiten" if scene else "Neue Szene",
                                  "Layout, Felder, fertig"))
        lay.addLayout(body, 1)
        self._rebuild_slots()

    def _free_name(self, base: str = "Szene") -> str:
        names = set(self.config.scene_names())
        if base != "Szene" and base not in names:
            return base
        i = 1 if base == "Szene" else 2
        while f"{base} {i}" in names:
            i += 1
        return f"{base} {i}"

    def _layout_changed(self, item, _prev):
        if item is not None:
            self.scene = resize_slots(self.scene, item.data(Qt.UserRole))
            self._rebuild_slots()

    def _rebuild_slots(self):
        while self.slots_grid.count():
            w = self.slots_grid.takeAt(0).widget()
            if w:
                w.deleteLater()
        t = theme.current()
        for i, (_x, _y, _w, _h, name) in enumerate(layout_slots(self.scene["layout"])):
            slot = self.scene["slots"][i]
            ic = QLabel()
            typ = slot.get("type") if slot else None
            ic.setPixmap(icons.pixmap(icons.SOURCE_ICONS.get(typ, "plus"),
                                      theme.SOURCE_COLORS.get(typ, t.muted), 22))
            label = QLabel(f"<b>{i + 1}. {name}</b>")
            desc = QLabel(describe_source(slot) if slot else "Noch leer – Quelle wählen")
            desc.setObjectName("" if slot else "Muted")
            desc.setWordWrap(True)
            choose = button("Quelle wählen …", "plus" if not slot else "edit", primary=not slot)
            clear = button("Leeren", "x")
            clear.setEnabled(slot is not None)
            choose.clicked.connect(lambda _=False, idx=i: self._choose(idx))
            clear.clicked.connect(lambda _=False, idx=i: self._clear(idx))
            self.slots_grid.addWidget(ic, i, 0)
            self.slots_grid.addWidget(label, i, 1)
            self.slots_grid.addWidget(desc, i, 2)
            self.slots_grid.addWidget(choose, i, 3)
            self.slots_grid.addWidget(clear, i, 4)
        self.slots_grid.setColumnStretch(2, 1)
        self.slots_grid.setHorizontalSpacing(12)
        self.slots_grid.setVerticalSpacing(8)
        self.preview.set_scene(self.scene)
        filled = sum(1 for x in self.scene["slots"] if x)
        total = len(self.scene["slots"])
        self.preview_note.setText(f"{LAYOUTS.get(self.scene['layout'], ('?',))[0]} · {filled} von {total} "
                                  f"Feld{'' if total == 1 else 'ern'} gefüllt")
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
        kind, ms = self.transition_combo.currentData(), self.transition_ms.value()
        if kind or ms:
            self.scene["transition"] = {"type": kind, "ms": ms}
        else:
            self.scene.pop("transition", None)
        self.config.put_scene(self.scene, self.original_name)
        seq = self.hotkey_edit.sequence()
        hotkeys = dict(self.config["hotkeys"])
        if seq:
            hotkeys[f"szene:{name}"] = seq
        else:
            hotkeys.pop(f"szene:{name}", None)
        self.config["hotkeys"] = hotkeys
        self.accept()
