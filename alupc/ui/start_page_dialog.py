"""Startseite anpassen: Kacheln ein-/ausblenden, sortieren, eigene Kacheln anlegen."""

from __future__ import annotations

import copy

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QSpinBox,
    QStackedWidget,
    QWidget,
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
from .hotkey_edit import HotkeyButton
from .setup_page import Swatch
from .source_picker import SourcePicker
from .widgets import button, page_header


ACTION_KINDS = {
    "source": "Etwas auf Monitor 2 anzeigen",
    "screensaver": "Eigenen Bildschirmschoner zeigen (nochmal klicken = beenden)",
    "timer": "Timer mit eigener Dauer starten",
    "command": "Befehl ausführen",
}


class CustomTileDialog(QDialog):
    """Eine eigene Kachel: Name, Symbol, Farbe, Aktion, Ton und Tastenkürzel."""

    def __init__(self, config, tile: dict, hotkey: str = "", parent=None, controller=None):
        super().__init__(parent)
        self.config = config
        self.controller = controller
        self.tile = copy.deepcopy(tile)
        self.setWindowTitle("Eigene Kachel")
        self.setMinimumWidth(640)

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
        kind = action.get("kind") or "source"
        self.kind = QComboBox()
        for key, label in ACTION_KINDS.items():
            if key == "screensaver" and controller is None:
                continue
            self.kind.addItem(label, key)
        self.pages = QStackedWidget()

        # --- Anzeigen
        self.source = action.get("source") if kind == "source" else None
        page = QWidget()
        pl = QHBoxLayout(page)
        pl.setContentsMargins(0, 0, 0, 0)
        self.source_label = QLabel(describe_action({"kind": "source", "source": self.source})
                                   if self.source else "(noch nichts gewählt)")
        self.source_label.setObjectName("Muted")
        pick = button("Quelle wählen …", "plus")
        pick.clicked.connect(self._pick_source)
        pl.addWidget(self.source_label, 1)
        pl.addWidget(pick)
        self.pages.addWidget(page)
        self._page_index = {"source": 0}

        # --- Bildschirmschoner
        self.saver_data = dict(action.get("screensaver") or {"style": "nachricht", "text": self.tile.get("title", "")})
        if controller is not None:
            from .screensaver_settings import ScreensaverSettings

            self.saver = ScreensaverSettings(controller, "", data=self.saver_data, tile_mode=True,
                                             on_change=lambda d: self.saver_data.update(d))
            self._page_index["screensaver"] = self.pages.count()
            self.pages.addWidget(self.saver)

        # --- Timer
        t = action.get("timer") or {}
        page = QWidget()
        tf = QFormLayout(page)
        tf.setContentsMargins(0, 0, 0, 0)
        self.t_mode = QComboBox()
        self.t_mode.addItem("Countdown", "countdown")
        self.t_mode.addItem("Stoppuhr", "stoppuhr")
        self.t_mode.setCurrentIndex(max(0, self.t_mode.findData(t.get("mode", "countdown"))))
        self.t_min = QSpinBox()
        self.t_min.setRange(0, 999)
        self.t_min.setSuffix(" min")
        self.t_min.setValue(int(t.get("minutes", 5)))
        self.t_sec = QSpinBox()
        self.t_sec.setRange(0, 59)
        self.t_sec.setSuffix(" s")
        self.t_sec.setValue(int(t.get("seconds", 0)))
        self.t_text = QLineEdit(t.get("finished_text", "Zeit ist um!"))
        self.t_auto = QCheckBox("Sofort starten")
        self.t_auto.setChecked(bool(t.get("autostart", True)))
        dur = QHBoxLayout()
        dur.addWidget(self.t_min)
        dur.addWidget(self.t_sec)
        tf.addRow("Art:", self.t_mode)
        tf.addRow("Dauer:", dur)
        tf.addRow("Text am Ende:", self.t_text)
        tf.addRow("", self.t_auto)
        self._page_index["timer"] = self.pages.count()
        self.pages.addWidget(page)

        # --- Befehl
        self.command = QComboBox()
        for key, label in COMMANDS.items():
            self.command.addItem(label, key)
        if kind == "command":
            self.command.setCurrentIndex(max(0, self.command.findData(action.get("command"))))
        self._page_index["command"] = self.pages.count()
        self.pages.addWidget(self.command)

        self.kind.currentIndexChanged.connect(
            lambda _i: self.pages.setCurrentIndex(self._page_index[self.kind.currentData()]))
        self.kind.setCurrentIndex(max(0, self.kind.findData(kind)))
        self.pages.setCurrentIndex(self._page_index.get(self.kind.currentData(), 0))

        self.hotkey = HotkeyButton(hotkey, "Tastenkürzel für diese Kachel")
        self.sound = None
        if controller is not None:
            from .sound_picker import SoundPicker

            self.sound = SoundPicker(controller.sounds, self.tile.get("sound", ""))

        form = QFormLayout()
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(10)
        form.addRow("Name:", self.title)
        form.addRow("Untertitel:", self.subtitle)
        form.addRow("Symbol:", self.icon)
        form.addRow("Farbe:", colors)
        form.addRow("Bereich:", self.section)
        form.addRow("Beim Klick:", self.kind)
        form.addRow("", self.pages)
        if self.sound is not None:
            form.addRow("Ton:", self.sound)
        form.addRow("Tastenkürzel:", self.hotkey)

        buttons = QDialogButtonBox()
        buttons.addButton(button("Übernehmen", "check", primary=True), QDialogButtonBox.AcceptRole)
        buttons.addButton(button("Abbrechen"), QDialogButtonBox.RejectRole)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 20, 22, 18)
        lay.setSpacing(12)
        lay.addWidget(page_header("Eigene Kachel", "Anzeigen, eigener Bildschirmschoner, Timer oder Befehl – "
                                                   "mit eigenem Ton und Tastenkürzel."))
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

    def hotkey_text(self) -> str:
        return self.hotkey.sequence()

    def _save(self):
        if not self.title.text().strip():
            QMessageBox.warning(self, "Kachel", "Bitte einen Namen eingeben.")
            return
        kind = self.kind.currentData()
        if kind == "source":
            if not self.source:
                QMessageBox.warning(self, "Kachel", "Bitte eine Quelle wählen.")
                return
            action = {"kind": "source", "source": self.source}
        elif kind == "screensaver":
            action = {"kind": "screensaver", "screensaver": dict(self.saver_data)}
        elif kind == "timer":
            if self.t_mode.currentData() == "countdown" and self.t_min.value() * 60 + self.t_sec.value() <= 0:
                QMessageBox.warning(self, "Kachel", "Bitte eine Dauer größer als 0 wählen.")
                return
            action = {"kind": "timer", "timer": {
                "mode": self.t_mode.currentData(), "minutes": self.t_min.value(), "seconds": self.t_sec.value(),
                "finished_text": self.t_text.text(), "autostart": self.t_auto.isChecked()}}
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
            "sound": self.sound.spec() if self.sound is not None else self.tile.get("sound", ""),
        })
        self.accept()


class StartPageDialog(QDialog):
    def __init__(self, config, parent=None, controller=None):
        super().__init__(parent)
        self.config = config
        self.controller = controller
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
        dlg = CustomTileDialog(self.config, tile, "", self, self.controller)
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
        dlg = CustomTileDialog(self.config, tile, self.hotkeys.get(f"kachel:{tile['id']}", ""), self,
                               self.controller)
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
