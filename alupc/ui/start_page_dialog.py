"""Startseite anpassen: Kacheln ein-/ausblenden, sortieren, eigene Kacheln anlegen."""

from __future__ import annotations

import copy

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QKeySequenceEdit,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QRadioButton,
    QVBoxLayout,
)

from ..startpage import (
    BUILTIN_TILES,
    COMMANDS,
    SECTIONS,
    TILE_COLORS,
    TILE_ICONS,
    all_keys,
    custom_key,
    describe_action,
    find_custom,
    new_custom_tile,
    ordered_keys,
)
from . import icons, theme
from .setup_page import Swatch
from .source_picker import SourcePicker
from .widgets import button, page_header


class CustomTileDialog(QDialog):
    """Eine eigene Kachel: Name, Symbol, Farbe, Aktion und Tastenkürzel."""

    def __init__(self, config, tile: dict, hotkey: str = "", parent=None):
        super().__init__(parent)
        self.config = config
        self.tile = copy.deepcopy(tile)
        self.setWindowTitle("Eigene Kachel")
        self.setMinimumWidth(560)

        self.title = QLineEdit(self.tile.get("title", ""))
        self.subtitle = QLineEdit(self.tile.get("subtitle", ""))
        self.subtitle.setPlaceholderText("optional, kleine Zeile unter dem Namen")
        self.icon = QComboBox()
        self.icon.setIconSize(QSize(20, 20))
        for key, label in TILE_ICONS.items():
            self.icon.addItem(icons.icon(key, theme.current().text, 20), label, key)
        self.icon.setCurrentIndex(max(0, self.icon.findData(self.tile.get("icon", "star"))))

        colors = QHBoxLayout()
        colors.setSpacing(6)
        self.color_group = QButtonGroup(self)
        self.color_group.setExclusive(True)
        for color in TILE_COLORS:
            sw = Swatch(color, color)
            sw.setChecked(color == self.tile.get("color"))
            self.color_group.addButton(sw)
            colors.addWidget(sw)
        colors.addStretch(1)

        self.section = QComboBox()
        for key, label in SECTIONS.items():
            self.section.addItem(label, key)
        self.section.setCurrentIndex(max(0, self.section.findData(self.tile.get("section", "anzeigen"))))

        action = self.tile.get("action") or {}
        self.source = action.get("source") if action.get("kind") == "source" else None
        self.show_radio = QRadioButton("Etwas auf Monitor 2 anzeigen")
        self.cmd_radio = QRadioButton("Befehl ausführen")
        self.source_label = QLabel(describe_action({"kind": "source", "source": self.source})
                                   if self.source else "(noch nichts gewählt)")
        self.source_label.setObjectName("Muted")
        pick = button("Quelle wählen …", "plus")
        pick.clicked.connect(self._pick_source)
        self.command = QComboBox()
        for key, label in COMMANDS.items():
            self.command.addItem(label, key)
        if action.get("kind") == "command":
            self.cmd_radio.setChecked(True)
            self.command.setCurrentIndex(max(0, self.command.findData(action.get("command"))))
        else:
            self.show_radio.setChecked(True)

        self.hotkey = QKeySequenceEdit(QKeySequence(hotkey, QKeySequence.PortableText))
        self.hotkey.setMaximumSequenceLength(1)
        clear = button("Leeren", "x")
        clear.clicked.connect(self.hotkey.clear)

        form = QFormLayout()
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(10)
        form.addRow("Name:", self.title)
        form.addRow("Untertitel:", self.subtitle)
        form.addRow("Symbol:", self.icon)
        form.addRow("Farbe:", colors)
        form.addRow("Bereich:", self.section)
        form.addRow(self.show_radio)
        row = QHBoxLayout()
        row.addWidget(self.source_label, 1)
        row.addWidget(pick)
        form.addRow("", row)
        form.addRow(self.cmd_radio)
        form.addRow("", self.command)
        hk = QHBoxLayout()
        hk.addWidget(self.hotkey, 1)
        hk.addWidget(clear)
        form.addRow("Tastenkürzel:", hk)

        buttons = QDialogButtonBox()
        buttons.addButton(button("Übernehmen", "check", primary=True), QDialogButtonBox.AcceptRole)
        buttons.addButton(button("Abbrechen"), QDialogButtonBox.RejectRole)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 20, 22, 18)
        lay.setSpacing(12)
        lay.addWidget(page_header("Eigene Kachel", "Ein Klick darauf zeigt etwas an oder führt einen Befehl aus."))
        lay.addLayout(form)
        lay.addWidget(buttons)

    def _pick_source(self):
        picker = SourcePicker(self.config, self, self.source)
        if picker.exec() == QDialog.Accepted:
            cfg = picker.result_config()
            if cfg is None:
                QMessageBox.information(self, "Quelle", "Bitte alle nötigen Angaben machen.")
                return
            self.source = cfg
            self.source_label.setText(describe_action({"kind": "source", "source": cfg}))
            self.show_radio.setChecked(True)

    def hotkey_text(self) -> str:
        return self.hotkey.keySequence().toString(QKeySequence.PortableText)

    def _save(self):
        if not self.title.text().strip():
            QMessageBox.warning(self, "Kachel", "Bitte einen Namen eingeben.")
            return
        if self.show_radio.isChecked():
            if not self.source:
                QMessageBox.warning(self, "Kachel", "Bitte eine Quelle wählen.")
                return
            action = {"kind": "source", "source": self.source}
        else:
            action = {"kind": "command", "command": self.command.currentData()}
        checked = self.color_group.checkedButton()
        self.tile.update({
            "title": self.title.text().strip(),
            "subtitle": self.subtitle.text().strip(),
            "icon": self.icon.currentData(),
            "color": checked.color if checked else TILE_COLORS[0],
            "section": self.section.currentData(),
            "action": action,
        })
        self.accept()


class StartPageDialog(QDialog):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.cfg = copy.deepcopy(config["start_page"])
        self.hotkeys = dict(config["hotkeys"])
        self.setWindowTitle("Startseite anpassen")
        self.resize(720, 620)

        self.title = QLineEdit(self.cfg.get("title", ""))
        self.title.setPlaceholderText("Was sollen die anderen sehen?")
        self.subtitle = QLineEdit(self.cfg.get("subtitle", ""))
        self.subtitle.setPlaceholderText("Ein Klick auf eine Kachel – und Monitor 2 zeigt es sofort.")
        self.show_status = QCheckBox("Statuskarte anzeigen (was läuft gerade auf Monitor 2)")
        self.show_status.setChecked(bool(self.cfg.get("show_status", True)))
        self.show_hint = QCheckBox("Hinweis mit Tastenkürzeln anzeigen")
        self.show_hint.setChecked(bool(self.cfg.get("show_hint", True)))

        self.list = QListWidget()
        self.list.setIconSize(QSize(22, 22))
        self.list.setDragDropMode(QAbstractItemView.InternalMove)
        self.list.setDefaultDropAction(Qt.MoveAction)
        self.list.itemDoubleClicked.connect(lambda _i: self._edit())
        self._fill()

        side = QVBoxLayout()
        side.setSpacing(8)
        for text, icon_name, slot, kw in [
            ("Nach oben", "up", lambda: self._move(-1), {}),
            ("Nach unten", "down", lambda: self._move(1), {}),
            ("Eigene Kachel …", "plus", self._add, {"primary": True}),
            ("Bearbeiten …", "edit", self._edit, {}),
            ("Löschen", "trash", self._delete, {"danger": True}),
            ("Standard", "refresh", self._reset, {}),
        ]:
            b = button(text, icon_name, **kw)
            b.clicked.connect(slot)
            side.addWidget(b)
        side.addStretch(1)

        form = QFormLayout()
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(8)
        form.addRow("Überschrift:", self.title)
        form.addRow("Untertitel:", self.subtitle)
        form.addRow("", self.show_status)
        form.addRow("", self.show_hint)

        body = QHBoxLayout()
        body.addWidget(self.list, 1)
        body.addLayout(side)
        hint = QLabel("Haken = Kachel wird angezeigt. Reihenfolge per Ziehen oder mit den Pfeilen ändern.")
        hint.setObjectName("Muted")
        hint.setWordWrap(True)

        buttons = QDialogButtonBox()
        buttons.addButton(button("Speichern", "check", primary=True), QDialogButtonBox.AcceptRole)
        buttons.addButton(button("Abbrechen"), QDialogButtonBox.RejectRole)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 20, 22, 18)
        lay.setSpacing(12)
        lay.addWidget(page_header("Startseite anpassen", "Deine Startseite – so, wie du sie brauchst."))
        lay.addLayout(form)
        lay.addWidget(hint)
        lay.addLayout(body, 1)
        lay.addWidget(buttons)

    # ------------------------------------------------------------ Liste
    def _item(self, key: str, checked: bool) -> QListWidgetItem:
        t = theme.current()
        if key in BUILTIN_TILES:
            icon_name, title, _sub, color, section = BUILTIN_TILES[key]
            extra = ""
        else:
            tile = find_custom(self.cfg, key) or {}
            icon_name, title, color = tile.get("icon", "star"), tile.get("title", "?"), tile.get("color")
            section = tile.get("section", "anzeigen")
            extra = " · eigene Kachel"
        item = QListWidgetItem(icons.icon(icon_name, color or t.accent, 22),
                               f"{title}   —   {SECTIONS.get(section, section)}{extra}")
        item.setData(Qt.UserRole, key)
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsDragEnabled)
        item.setFlags(item.flags() & ~Qt.ItemIsDropEnabled)
        item.setCheckState(Qt.Checked if checked else Qt.Unchecked)
        return item

    def _fill(self, select: str | None = None):
        visible = set(ordered_keys(self.cfg))
        self.list.clear()
        for key in all_keys(self.cfg):
            self.list.addItem(self._item(key, key in visible))
        for i in range(self.list.count()):
            if self.list.item(i).data(Qt.UserRole) == select:
                self.list.setCurrentRow(i)

    def _current_keys(self) -> tuple[list[str], list[str]]:
        order, visible = [], []
        for i in range(self.list.count()):
            item = self.list.item(i)
            key = item.data(Qt.UserRole)
            order.append(key)
            if item.checkState() == Qt.Checked:
                visible.append(key)
        return order, visible

    def _sync(self):
        """Haken und Reihenfolge der Liste in die Arbeitskopie übernehmen."""
        _order, visible = self._current_keys()
        self.cfg["tiles"] = visible

    def _move(self, step: int):
        row = self.list.currentRow()
        target = row + step
        if row < 0 or not 0 <= target < self.list.count():
            return
        item = self.list.takeItem(row)
        self.list.insertItem(target, item)
        self.list.setCurrentRow(target)

    def _add(self):
        self._sync()
        tile = new_custom_tile()
        dlg = CustomTileDialog(self.config, tile, "", self)
        if dlg.exec() == QDialog.Accepted:
            self.cfg.setdefault("custom", []).append(dlg.tile)
            self.cfg["tiles"] = self.cfg["tiles"] + [custom_key(dlg.tile)]
            self._set_hotkey(dlg.tile["id"], dlg.hotkey_text())
            self._fill(custom_key(dlg.tile))

    def _edit(self):
        item = self.list.currentItem()
        if item is None:
            return
        key = item.data(Qt.UserRole)
        if key in BUILTIN_TILES:
            QMessageBox.information(self, "Kachel", "Standard-Kacheln kann man nur ein-/ausblenden und "
                                                    "verschieben. Für eigene Aktionen: „Eigene Kachel …“.")
            return
        self._sync()
        tile = find_custom(self.cfg, key)
        dlg = CustomTileDialog(self.config, tile, self.hotkeys.get(f"kachel:{tile['id']}", ""), self)
        if dlg.exec() == QDialog.Accepted:
            tile.update(dlg.tile)
            self._set_hotkey(tile["id"], dlg.hotkey_text())
            self._fill(key)

    def _delete(self):
        item = self.list.currentItem()
        if item is None:
            return
        key = item.data(Qt.UserRole)
        if key in BUILTIN_TILES:
            item.setCheckState(Qt.Unchecked)  # Standard-Kacheln nur ausblenden
            return
        tile = find_custom(self.cfg, key)
        if QMessageBox.question(self, "Löschen", f"Kachel „{tile.get('title')}“ löschen?") != QMessageBox.Yes:
            return
        self._sync()
        self.cfg["custom"] = [t for t in self.cfg["custom"] if t["id"] != tile["id"]]
        self.cfg["tiles"] = [k for k in self.cfg["tiles"] if k != key]
        self.hotkeys.pop(f"kachel:{tile['id']}", None)
        self._fill()

    def _reset(self):
        if QMessageBox.question(self, "Standard", "Reihenfolge und Sichtbarkeit auf Standard zurücksetzen? "
                                "Eigene Kacheln bleiben erhalten.") == QMessageBox.Yes:
            self.cfg["tiles"] = None
            self._fill()

    def _set_hotkey(self, tile_id: str, seq: str):
        if seq:
            self.hotkeys[f"kachel:{tile_id}"] = seq
        else:
            self.hotkeys.pop(f"kachel:{tile_id}", None)

    def _save(self):
        self._sync()
        self.cfg.update({
            "title": self.title.text().strip(),
            "subtitle": self.subtitle.text().strip(),
            "show_status": self.show_status.isChecked(),
            "show_hint": self.show_hint.isChecked(),
        })
        self.config.data["hotkeys"] = self.hotkeys
        self.config["start_page"] = self.cfg
        self.accept()
