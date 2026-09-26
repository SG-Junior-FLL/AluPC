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
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QSpinBox,
    QStackedWidget,
    QTabWidget,
    QWidget,
    QVBoxLayout,
)

from ..startpage import (
    BUILTIN_TILES,
    COMMANDS,
    TILE_COLORS,
    TILE_ICONS,
    all_keys,
    custom_key,
    delete_section,
    describe_action,
    find_custom,
    move_to_section,
    new_custom_tile,
    new_section,
    ordered_keys,
    section_name,
    section_of,
    sections,
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
        start_cfg = getattr(parent, "cfg", None) or config["start_page"]  # Arbeitskopie des Startseiten-Dialogs
        for sec in sections(start_cfg):
            self.section.addItem(sec["name"], sec["id"])
        current = section_of(custom_key(self.tile), start_cfg) if find_custom(start_cfg, custom_key(self.tile)) \
            else self.tile.get("section", "anzeigen")
        self.section.setCurrentIndex(max(0, self.section.findData(current)))

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
        lay.addWidget(page_header("Eigene Kachel", "Anzeigen · Schoner · Timer · Befehl"))
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
        self.resize(760, 640)

        self.title = QLineEdit(self.cfg.get("title", ""))
        self.title.setPlaceholderText("Was sollen die anderen sehen?")
        self.subtitle = QLineEdit(self.cfg.get("subtitle", ""))
        self.subtitle.setPlaceholderText("Kachel antippen – läuft sofort auf Monitor 2")
        self.show_status = QCheckBox("Statuskarte zeigen")
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
            ("Bildschirmschoner", "moon", self._add_saver_menu, {}),
            ("Bearbeiten …", "edit", self._edit, {}),
            ("Löschen", "trash", self._delete, {"danger": True}),
            ("Standard", "refresh", self._reset, {}),
        ]:
            b = button(text, icon_name, **kw)
            b.clicked.connect(slot)
            side.addWidget(b)
        side.addStretch(1)

        # ausgewählte Kachel in einen anderen Bereich verschieben
        self.move_combo = QComboBox()
        self.move_combo.activated.connect(self._move_selected)
        self.list.currentItemChanged.connect(lambda *_: self._sync_move_combo())

        # Bereiche verwalten
        self.sec_list = QListWidget()
        self.sec_list.setSpacing(3)
        self.sec_list.itemDoubleClicked.connect(lambda _i: self._rename_section())
        sec_box = QWidget()
        sec_lay = QHBoxLayout(sec_box)
        sec_lay.setContentsMargins(0, 12, 0, 0)
        sec_lay.addWidget(self.sec_list, 1)
        sec_side = QVBoxLayout()
        sec_side.setSpacing(6)
        for text, icon_name, slot, kw in [
            ("Neu …", "plus", self._add_section, {"primary": True}),
            ("Umbenennen …", "edit", self._rename_section, {}),
            ("Nach oben", "up", lambda: self._move_section(-1), {}),
            ("Nach unten", "down", lambda: self._move_section(1), {}),
            ("Löschen", "trash", self._delete_section, {"danger": True}),
        ]:
            b = button(text, icon_name, **kw)
            b.clicked.connect(slot)
            sec_side.addWidget(b)
        sec_side.addStretch(1)
        sec_lay.addLayout(sec_side)
        self._fill_sections()

        form = QFormLayout()
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(8)
        form.addRow("Überschrift:", self.title)
        form.addRow("Untertitel:", self.subtitle)
        form.addRow("", self.show_status)
        form.addRow("", self.show_hint)

        body = QHBoxLayout()
        left = QVBoxLayout()
        left.addWidget(self.list, 1)
        move_row = QHBoxLayout()
        move_row.addWidget(QLabel("Bereich der Kachel:"))
        move_row.addWidget(self.move_combo, 1)
        left.addLayout(move_row)
        body.addLayout(left, 1)
        body.addLayout(side)
        hint = QLabel("Haken = sichtbar · Ziehen = Reihenfolge · Bereich unten wählen")
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
        lay.addWidget(page_header("Startseite anpassen", "Kacheln · Bereiche · Texte"))
        tabs = QTabWidget()
        tiles_page = QWidget()
        tiles_lay = QVBoxLayout(tiles_page)
        tiles_lay.setContentsMargins(14, 14, 14, 14)
        tiles_lay.addWidget(hint)
        tiles_lay.addLayout(body, 1)
        texts_page = QWidget()
        texts_lay = QVBoxLayout(texts_page)
        texts_lay.setContentsMargins(14, 14, 14, 14)
        texts_lay.addLayout(form)
        texts_lay.addStretch(1)
        sec_hint = QLabel("Doppelklick = umbenennen · Auf der Startseite: Klick auf Überschrift = einklappen")
        sec_hint.setObjectName("Muted")
        sec_hint.setWordWrap(True)
        sec_page = QWidget()
        sec_page_lay = QVBoxLayout(sec_page)
        sec_page_lay.setContentsMargins(14, 2, 14, 14)
        sec_page_lay.addWidget(sec_box, 1)
        sec_page_lay.addWidget(sec_hint)
        tabs.addTab(tiles_page, icons.icon("grid", theme.current().text, 18), "Kacheln")
        tabs.addTab(sec_page, icons.icon("scenes", theme.current().text, 18), "Bereiche")
        tabs.addTab(texts_page, icons.icon("text", theme.current().text, 18), "Texte")
        self.tabs = tabs
        lay.addWidget(tabs, 1)
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
        section = section_of(key, self.cfg)
        item = QListWidgetItem(icons.icon(icon_name, color or t.accent, 22),
                               f"{title}   —   {section_name(self.cfg, section)}{extra}")
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
        self.cfg["seen"] = list(BUILTIN_TILES)

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
            move_to_section(self.cfg, custom_key(dlg.tile), dlg.tile["section"])
            self.cfg["tiles"] = self.cfg["tiles"] + [custom_key(dlg.tile)]
            self._set_hotkey(dlg.tile["id"], dlg.hotkey_text())
            self._fill(custom_key(dlg.tile))

    # ------------------------------------------------------------ Bereiche
    def _fill_sections(self, select: str | None = None):
        self.sec_list.clear()
        counts = {}
        for key in all_keys(self.cfg):
            sid = section_of(key, self.cfg)
            counts[sid] = counts.get(sid, 0) + 1
        for sec in sections(self.cfg):
            item = QListWidgetItem(f"{sec['name']}   ·   {counts.get(sec['id'], 0)} Kacheln")
            item.setData(Qt.UserRole, sec["id"])
            self.sec_list.addItem(item)
            if sec["id"] == select:
                self.sec_list.setCurrentItem(item)
        self.move_combo.blockSignals(True)
        self.move_combo.clear()
        for sec in sections(self.cfg):
            self.move_combo.addItem(sec["name"], sec["id"])
        self.move_combo.blockSignals(False)
        self._sync_move_combo()

    def _sync_move_combo(self):
        item = self.list.currentItem()
        self.move_combo.setEnabled(item is not None)
        if item is not None:
            self.move_combo.setCurrentIndex(max(0, self.move_combo.findData(section_of(item.data(Qt.UserRole),
                                                                                       self.cfg))))

    def _current_section(self) -> str | None:
        item = self.sec_list.currentItem()
        return item.data(Qt.UserRole) if item else None

    def _refresh_all(self, tile: str | None = None, section: str | None = None):
        self._sync()
        self._fill(tile)
        self._fill_sections(section)

    def move_tile(self, key: str, section_id: str) -> None:
        self._sync()
        move_to_section(self.cfg, key, section_id)
        self._refresh_all(key, self._current_section())

    def _move_selected(self, *_):
        item = self.list.currentItem()
        if item is not None:
            self.move_tile(item.data(Qt.UserRole), self.move_combo.currentData())

    def add_section(self, name: str) -> str:
        self._sync()
        sec = new_section(name)
        self.cfg["sections"] = sections(self.cfg) + [sec]
        self._fill_sections(sec["id"])
        return sec["id"]

    def _add_section(self):
        name, ok = QInputDialog.getText(self, "Neuer Bereich", "Name:")
        if ok and name.strip():
            sid = self.add_section(name)
            item = self.list.currentItem()
            if item is not None and QMessageBox.question(
                    self, "Neuer Bereich", f"Ausgewählte Kachel gleich nach „{name.strip()}“ verschieben?") \
                    == QMessageBox.Yes:
                self.move_tile(item.data(Qt.UserRole), sid)

    def rename_section(self, section_id: str, name: str) -> None:
        self.cfg["sections"] = [{**s, "name": name.strip() or s["name"]} if s["id"] == section_id else s
                                for s in sections(self.cfg)]
        self._refresh_all(None, section_id)

    def _rename_section(self):
        sid = self._current_section()
        if sid is None:
            return
        name, ok = QInputDialog.getText(self, "Bereich umbenennen", "Name:", text=section_name(self.cfg, sid))
        if ok and name.strip():
            self.rename_section(sid, name)

    def _move_section(self, step: int):
        sid = self._current_section()
        secs = sections(self.cfg)
        i = next((n for n, s in enumerate(secs) if s["id"] == sid), -1)
        if i < 0 or not 0 <= i + step < len(secs):
            return
        secs[i], secs[i + step] = secs[i + step], secs[i]
        self.cfg["sections"] = secs
        self._refresh_all(None, sid)

    def _delete_section(self):
        sid = self._current_section()
        secs = sections(self.cfg)
        if sid is None:
            return
        if len(secs) == 1:
            QMessageBox.information(self, "Bereich", "Mindestens ein Bereich muss bleiben.")
            return
        rest = next(s["name"] for s in secs if s["id"] != sid)
        if QMessageBox.question(self, "Bereich löschen", f"„{section_name(self.cfg, sid)}“ löschen? Die Kacheln "
                                f"kommen nach „{rest}“.") != QMessageBox.Yes:
            return
        self._sync()
        delete_section(self.cfg, sid)
        self._refresh_all()

    def _add_saver_menu(self):
        """Menü: Bildschirmschoner als eigene Kachel – beliebig viele, jeder mit eigenem Stil."""
        from PySide6.QtGui import QCursor
        from PySide6.QtWidgets import QMenu

        from ..screensaver import STYLE_GROUPS, STYLES

        menu = QMenu(self)
        for group, keys in STYLE_GROUPS.items():
            menu.addSection(group)
            for key in keys:
                menu.addAction(STYLES[key], lambda k=key: self.add_saver(k))
        menu.exec(QCursor.pos())

    def add_saver(self, style: str) -> None:
        from ..screensaver import STYLES

        self._sync()
        tile = new_custom_tile()
        n = len(self.cfg.get("custom", []))
        tile.update({"title": STYLES[style], "subtitle": "Bildschirmschoner", "icon": "moon",
                     "color": TILE_COLORS[n % len(TILE_COLORS)],
                     "action": {"kind": "screensaver", "screensaver": {"style": style, "text": ""}}})
        if style in ("diashow", "szene"):  # braucht Ordner bzw. Szene → erst einstellen
            dlg = CustomTileDialog(self.config, tile, "", self, self.controller)
            if dlg.exec() != QDialog.Accepted:
                return
            tile = dlg.tile
            self._set_hotkey(tile["id"], dlg.hotkey_text())
        self.cfg.setdefault("custom", []).append(tile)
        self.cfg["tiles"] = self.cfg["tiles"] + [custom_key(tile)]
        self._fill(custom_key(tile))

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
            move_to_section(self.cfg, key, dlg.tile["section"])
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
