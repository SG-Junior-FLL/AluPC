"""Seite „Gäste“: alles, was Handys übers AluPC-WLAN machen – Chat (direkt als Overlay auf Monitor 2) und
Foto-Wand verwalten: an/aus, auf Monitor 2 zeigen, Nachrichten/Fotos löschen, Handys sperren, Wortfilter."""

from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QIcon, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from . import icons, theme
from .widgets import button, font, page_header

CHAT_POSITIONS = {"unten links": (0.0, 1.0), "unten rechts": (1.0, 1.0), "oben links": (0.0, 0.0),
                  "oben rechts": (1.0, 0.0), "links Mitte": (0.0, 0.5), "rechts Mitte": (1.0, 0.5)}


def _card(title: str, icon_name: str, color: str) -> tuple[QFrame, QVBoxLayout, QHBoxLayout]:
    card = QFrame()
    card.setObjectName("Card")
    lay = QVBoxLayout(card)
    lay.setContentsMargins(18, 16, 18, 16)
    lay.setSpacing(10)
    head = QHBoxLayout()
    ic = QLabel()
    ic.setPixmap(icons.pixmap(icon_name, color, 22))
    head.addWidget(ic)
    lab = QLabel(f"<b>{title}</b>")
    lab.setFont(font(12.5))
    head.addWidget(lab)
    head.addStretch(1)
    lay.addLayout(head)
    return card, lay, head


def _pill(label: QLabel, on: bool, text_on: str = "● AN", text_off: str = "○ AUS") -> None:
    t = theme.current()
    color = t.success if on else t.muted
    label.setText(text_on if on else text_off)
    label.setStyleSheet(f"color:{color}; background:{t.soft(color, 0.14)}; border-radius:11px; padding:3px 12px;"
                        "font-weight:700;")


class GuestsPage(QWidget):
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self._chat_version = -1
        self._wall_version = -1
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(14)
        root.addWidget(page_header("Gäste", "Chat und Foto-Wand übers AluPC-WLAN – erscheint direkt auf dem Bildschirm",
                                   "users"))
        root.addWidget(self._wlan_card())
        grid = QGridLayout()
        grid.setSpacing(14)
        self.chat_card, self.wall_card = self._chat_card(), self._wall_card()
        grid.addWidget(self.chat_card, 0, 0)
        grid.addWidget(self.wall_card, 0, 1)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        self.grid = grid
        self._wide = True
        root.addLayout(grid, 1)
        controller.guests_changed.connect(self.refresh)
        controller.hotspot_changed.connect(self.refresh)
        self._timer = QTimer(self, interval=1500)  # neue Nachrichten/Fotos auch ohne Signal (z. B. Handy-Seite)
        self._timer.timeout.connect(self.refresh)
        self._timer.start()
        self.refresh()

    # ---------------------------------------------------------------- WLAN
    def _wlan_card(self) -> QFrame:
        card, lay, head = _card("AluPC-WLAN", "wifi", theme.current().accent)
        self.wlan_pill = QLabel()
        head.addWidget(self.wlan_pill)
        self.wlan_text = QLabel()
        self.wlan_text.setObjectName("Muted")
        self.wlan_text.setWordWrap(True)
        lay.addWidget(self.wlan_text)
        row = QHBoxLayout()
        self.wlan_btn = button("WLAN starten", "play", primary=True)
        self.wlan_btn.clicked.connect(self.controller.ensure_wlan)
        codes = button("Codes auf dem Bildschirm", "qr")
        codes.setToolTip("WLAN-Code + Seiten-Code groß auf dem Bildschirm")
        codes.clicked.connect(lambda: self.controller.run_command("qr"))
        window = button("Hotspot-Fenster", "sliders")
        window.clicked.connect(self._open_hotspot)
        for b in (self.wlan_btn, codes, window):
            row.addWidget(b)
        row.addStretch(1)
        lay.addLayout(row)
        return card

    def _open_hotspot(self) -> None:
        win = self.window()
        if hasattr(win, "open_hotspot_dialog"):
            win.open_hotspot_dialog()

    # ---------------------------------------------------------------- Chat
    def _chat_card(self) -> QFrame:
        card, lay, head = _card("Chat", "chat", "#3b82f6")
        self.chat_pill = QLabel()
        head.addWidget(self.chat_pill)
        self.chat_toggle = button("Chat starten", "play", primary=True)
        self.chat_toggle.clicked.connect(self._toggle_chat)
        head.addWidget(self.chat_toggle)
        row = QHBoxLayout()
        self.chat_overlay = QCheckBox("Als Overlay auf dem Bildschirm")
        self.chat_overlay.setToolTip("Nachrichten erscheinen direkt über allem, was der Bildschirm zeigt")
        self.chat_overlay.toggled.connect(lambda on: self.controller.set_chat_overlay(on))
        row.addWidget(self.chat_overlay)
        row.addStretch(1)
        wall = button("Chat-Wand", "monitor")
        wall.setToolTip("Chat groß auf dem Bildschirm (mit den Codes zum Mitschreiben)")
        wall.clicked.connect(lambda: self.controller.run_command("chat_wand"))
        row.addWidget(wall)
        lay.addLayout(row)
        self.chat_list = QListWidget()
        self.chat_list.setMinimumHeight(170)
        self.chat_list.setWordWrap(True)
        self.chat_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.chat_list.customContextMenuRequested.connect(self._chat_menu)
        self.chat_list.setToolTip("Rechtsklick: Nachricht löschen oder das Handy sperren")
        lay.addWidget(self.chat_list, 1)
        say = QHBoxLayout()
        self.chat_say = QLineEdit()
        self.chat_say.setPlaceholderText("Als AluPC schreiben (hervorgehoben) …")
        self.chat_say.returnPressed.connect(self._say)
        send = button("", "forward")
        send.setToolTip("Senden")
        send.clicked.connect(self._say)
        say.addWidget(self.chat_say, 1)
        say.addWidget(send)
        lay.addLayout(say)
        tools = QHBoxLayout()
        delete = button("Löschen", "trash")
        delete.setToolTip("Markierte Nachricht löschen")
        delete.clicked.connect(self._delete_selected)
        block = button("Handy sperren", "lock")
        block.setToolTip("Das Handy der markierten Nachricht darf nicht mehr schreiben (Nachrichten verschwinden)")
        block.clicked.connect(self._block_selected)
        clear = button("Leeren", "x")
        clear.clicked.connect(self._clear_chat)
        self.unblock = button("Sperren aufheben", "refresh")
        self.unblock.clicked.connect(lambda: self.controller.cast.chat and self.controller.cast.chat.unblock_all())
        for b in (delete, block, clear, self.unblock):
            tools.addWidget(b)
        tools.addStretch(1)
        lay.addLayout(tools)
        # Einstellungen
        cfg = self.controller.config["chat"]
        opts = QGridLayout()
        opts.setHorizontalSpacing(10)
        opts.addWidget(QLabel("Overlay:"), 0, 0)
        self.chat_pos = QComboBox()
        for name, xy in CHAT_POSITIONS.items():
            self.chat_pos.addItem(name, xy)
        current = (cfg.get("x", 0.0), cfg.get("y", 1.0))
        self.chat_pos.setCurrentIndex(max(0, next((i for i, xy in enumerate(CHAT_POSITIONS.values())
                                                   if xy == current), 0)))
        self.chat_pos.currentIndexChanged.connect(
            lambda _i: self.controller.update_chat_settings(x=self.chat_pos.currentData()[0],
                                                            y=self.chat_pos.currentData()[1]))
        opts.addWidget(self.chat_pos, 0, 1)
        opts.addWidget(QLabel("Anzeige:"), 1, 0)
        self.chat_mode = QComboBox()
        self.chat_mode.addItem("Liste (mit QR-Code)", "liste")
        self.chat_mode.addItem("Pop-up (kurz, ohne QR)", "popup")
        self.chat_mode.setToolTip("Pop-up: jede neue Nachricht ploppt kurz auf und verschwindet wieder")
        self.chat_mode.setCurrentIndex(1 if cfg.get("mode") == "popup" else 0)
        self.chat_mode.currentIndexChanged.connect(self._chat_mode)
        opts.addWidget(self.chat_mode, 1, 1)
        self.chat_count = QSpinBox()
        self.chat_count.setRange(1, 12)
        self.chat_count.setSuffix(" Nachrichten")
        self.chat_count.setValue(int(cfg.get("count", 5)))
        self.chat_count.valueChanged.connect(lambda v: self.controller.update_chat_settings(count=v))
        opts.addWidget(self.chat_count, 2, 1)
        self.chat_secs = QSpinBox()
        self.chat_secs.setRange(0, 600)
        self.chat_secs.setSuffix(" s sichtbar")
        self.chat_secs.setSpecialValueText("bleiben stehen")
        self.chat_secs.setValue(int(cfg.get("seconds", 0)))
        self.chat_secs.valueChanged.connect(lambda v: self.controller.update_chat_settings(seconds=v))
        opts.addWidget(self.chat_secs, 2, 2)
        self.chat_qr = QCheckBox("QR-Code im Overlay")
        self.chat_qr.setChecked(bool(cfg.get("qr", True)))
        self.chat_qr.toggled.connect(lambda on: self.controller.update_chat_settings(qr=on))
        opts.addWidget(self.chat_qr, 0, 2)
        self._chat_mode_ui()
        self.chat_links = QCheckBox("Links ausblenden")
        self.chat_links.setChecked(bool(cfg.get("hide_links", True)))
        self.chat_links.toggled.connect(lambda on: self.controller.update_chat_settings(hide_links=on))
        opts.addWidget(self.chat_links, 3, 1)
        self.chat_builtin = QCheckBox("Schimpfwörter-Filter")
        self.chat_builtin.setChecked(bool(cfg.get("builtin", True)))
        self.chat_builtin.toggled.connect(lambda on: self.controller.update_chat_settings(builtin=on))
        opts.addWidget(self.chat_builtin, 3, 2)
        opts.addWidget(QLabel("Eigene Wörter:"), 4, 0)
        self.chat_words = QLineEdit(", ".join(cfg.get("words") or []))
        self.chat_words.setPlaceholderText("werden zu *** (mit Komma trennen)")
        self.chat_words.editingFinished.connect(
            lambda: self.controller.update_chat_settings(
                words=[w.strip() for w in self.chat_words.text().split(",") if w.strip()]))
        opts.addWidget(self.chat_words, 4, 1, 1, 2)
        lay.addLayout(opts)
        return card

    def _chat_mode(self, _i: int) -> None:
        self.controller.update_chat_settings(mode=self.chat_mode.currentData())
        self._chat_mode_ui()

    def _chat_mode_ui(self) -> None:
        popup = self.chat_mode.currentData() == "popup"
        self.chat_qr.setEnabled(not popup)  # Pop-up zeigt nie einen QR-Code
        self.chat_secs.setSpecialValueText("8 s (Standard)" if popup else "bleiben stehen")

    def _toggle_chat(self) -> None:
        if self.controller.cast.chat is None:
            self.controller.start_chat()
        else:
            self.controller.stop_chat()

    def _say(self) -> None:
        text = self.chat_say.text().strip()
        if text and self.controller.chat_say(text):
            self.chat_say.clear()

    def _selected_message(self) -> dict | None:
        item = self.chat_list.currentItem()
        return item.data(Qt.UserRole) if item is not None else None

    def _delete_selected(self) -> None:
        msg, chat = self._selected_message(), self.controller.cast.chat
        if msg and chat is not None and chat.delete(msg["id"]):
            self.controller.overlay_window.chat_changed()
            self.refresh(force=True)

    def _block_selected(self) -> None:
        msg, chat = self._selected_message(), self.controller.cast.chat
        if not msg or chat is None or not msg.get("ip"):
            return
        removed = chat.block(msg["ip"])
        self.controller.overlay_window.chat_changed()
        self.controller.message.emit(f"„{msg['name']}“ ist im Chat gesperrt ({removed} Nachrichten entfernt).")
        self.refresh(force=True)

    def _clear_chat(self) -> None:
        chat = self.controller.cast.chat
        if chat is not None:
            chat.clear()
            self.controller.overlay_window.chat_changed()
            self.refresh(force=True)

    def _chat_menu(self, pos) -> None:
        if self._selected_message() is None:
            return
        menu = QMenu(self)
        menu.addAction(icons.icon("trash", theme.current().text, 16), "Nachricht löschen", self._delete_selected)
        menu.addAction(icons.icon("lock", theme.current().text, 16), "Handy sperren", self._block_selected)
        menu.exec(self.chat_list.viewport().mapToGlobal(pos))

    # ---------------------------------------------------------------- Foto-Wand
    def _wall_card(self) -> QFrame:
        card, lay, head = _card("Foto-Wand", "photos", "#ec4899")
        self.wall_pill = QLabel()
        head.addWidget(self.wall_pill)
        self.wall_toggle = button("Foto-Wand starten", "play", primary=True)
        self.wall_toggle.clicked.connect(self._toggle_wall)
        head.addWidget(self.wall_toggle)
        cfg = self.controller.config["photowall"]
        row = QHBoxLayout()
        self.wall_mode = QComboBox()
        self.wall_mode.addItem("Collage", "collage")
        self.wall_mode.addItem("Diashow", "diashow")
        self.wall_mode.setCurrentIndex(max(0, self.wall_mode.findData(cfg.get("mode", "collage"))))
        self.wall_mode.currentIndexChanged.connect(lambda _i: self._wall_set(mode=self.wall_mode.currentData()))
        row.addWidget(self.wall_mode)
        self.wall_interval = QSpinBox()
        self.wall_interval.setRange(3, 60)
        self.wall_interval.setSuffix(" s je Foto")
        self.wall_interval.setValue(int(cfg.get("interval", 7)))
        self.wall_interval.valueChanged.connect(lambda v: self._wall_set(interval=v))
        row.addWidget(self.wall_interval)
        self.wall_codes = QCheckBox("Codes zeigen")
        self.wall_codes.setChecked(bool(cfg.get("codes", True)))
        self.wall_codes.toggled.connect(lambda on: self._wall_set(codes=on))
        row.addWidget(self.wall_codes)
        row.addStretch(1)
        show = button("Auf dem Bildschirm", "monitor")
        show.clicked.connect(lambda: self.controller.start_wall(show=True))
        row.addWidget(show)
        lay.addLayout(row)
        self.wall_list = QListWidget()
        self.wall_list.setViewMode(QListWidget.IconMode)
        self.wall_list.setIconSize(QSize(96, 96))
        self.wall_list.setResizeMode(QListWidget.Adjust)
        self.wall_list.setMovement(QListWidget.Static)
        self.wall_list.setSpacing(6)
        self.wall_list.setMinimumHeight(170)
        self.wall_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.wall_list.customContextMenuRequested.connect(self._wall_menu)
        self.wall_list.setToolTip("Rechtsklick: Foto entfernen oder das Handy sperren · Doppelklick: öffnen")
        self.wall_list.itemDoubleClicked.connect(
            lambda it: QDesktopServices.openUrl(QUrl.fromLocalFile(it.data(Qt.UserRole)["path"])))
        lay.addWidget(self.wall_list, 1)
        tools = QHBoxLayout()
        delete = button("Entfernen", "trash")
        delete.setToolTip("Markiertes Foto von der Wand nehmen und die Datei löschen")
        delete.clicked.connect(self._delete_photo)
        block = button("Handy sperren", "lock")
        block.clicked.connect(self._block_photo)
        clear = button("Wand leeren", "x")
        clear.setToolTip("Alle Fotos von der Wand nehmen – die Dateien bleiben im Ordner")
        clear.clicked.connect(lambda: self.controller.cast.wall and self.controller.cast.wall.clear())
        folder = button("Ordner", "image")
        folder.setToolTip("Ordner mit allen Fotos öffnen · Rechtsklick: anderen Ordner wählen")
        folder.clicked.connect(self._open_folder)
        folder.setContextMenuPolicy(Qt.CustomContextMenu)
        folder.customContextMenuRequested.connect(lambda _p: self._pick_folder())
        for b in (delete, block, clear, folder):
            tools.addWidget(b)
        tools.addStretch(1)
        lay.addLayout(tools)
        self.wall_folder = QLabel()
        self.wall_folder.setObjectName("Muted")
        self.wall_folder.setWordWrap(True)
        self.wall_folder.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lay.addWidget(self.wall_folder)
        return card

    def _wall_set(self, **values) -> None:
        self.controller.config["photowall"] = {**self.controller.config["photowall"], **values}
        self.controller.guests_changed.emit()

    def _toggle_wall(self) -> None:
        if self.controller.cast.wall is None:
            self.controller.start_wall(show=True)
        else:
            self.controller.stop_wall()

    def _folder(self) -> Path:
        from ..photowall import default_folder

        wall = self.controller.cast.wall
        cfg = self.controller.config["photowall"]
        return wall.folder if wall is not None else (Path(cfg["folder"]) if cfg.get("folder") else default_folder())

    def _open_folder(self) -> None:
        folder = self._folder()
        folder.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def _pick_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Ordner für die Foto-Wand", str(self._folder()))
        if folder:
            self._wall_set(folder=folder)
            if self.controller.cast.wall is not None:
                self.controller.start_wall(show=False)
            self.refresh(force=True)

    def _selected_photo(self) -> dict | None:
        item = self.wall_list.currentItem()
        return item.data(Qt.UserRole) if item is not None else None

    def _delete_photo(self) -> None:
        photo, wall = self._selected_photo(), self.controller.cast.wall
        if photo and wall is not None:
            wall.remove(photo["id"])
            self.refresh(force=True)

    def _block_photo(self) -> None:
        photo, wall = self._selected_photo(), self.controller.cast.wall
        if photo and wall is not None and photo.get("ip"):
            removed = wall.block(photo["ip"])
            self.controller.message.emit(f"„{photo['name']}“ ist für die Foto-Wand gesperrt ({removed} Fotos entfernt).")
            self.refresh(force=True)

    def _wall_menu(self, pos) -> None:
        if self._selected_photo() is None:
            return
        menu = QMenu(self)
        menu.addAction(icons.icon("trash", theme.current().text, 16), "Foto entfernen (Datei löschen)",
                       self._delete_photo)
        menu.addAction(icons.icon("lock", theme.current().text, 16), "Handy sperren", self._block_photo)
        menu.exec(self.wall_list.viewport().mapToGlobal(pos))

    # ---------------------------------------------------------------- Stand
    def refresh(self, force: bool = False) -> None:
        if not self.isVisible() and not force:
            return
        from ..hotspot import hotspot

        c = self.controller
        on = hotspot.running
        _pill(self.wlan_pill, on)
        self.wlan_btn.setVisible(not on)
        self.wlan_text.setText(f"„{hotspot.ssid}“ · Handys: WLAN-Code scannen, dann den Seiten-Code auf dem "
                               "Bildschirm." if on else
                               (hotspot.message or "Aus – Chat und Foto-Wand starten das WLAN automatisch."))
        chat = c.cast.chat
        _pill(self.chat_pill, chat is not None)
        self.chat_toggle.setText("Chat beenden" if chat is not None else "Chat starten")
        self.chat_toggle.setIcon(icons.icon("x" if chat is not None else "play", theme.current().text, 18))
        self.chat_overlay.blockSignals(True)
        self.chat_overlay.setChecked("chat" in c.live_overlays)
        self.chat_overlay.blockSignals(False)
        self.unblock.setVisible(bool(chat is not None and chat.blocked))
        version = (chat.version, len(chat.messages)) if chat is not None else -1
        if version != self._chat_version or force:
            self._chat_version = version
            at_end = self.chat_list.verticalScrollBar().value() >= self.chat_list.verticalScrollBar().maximum() - 4
            selected = (self._selected_message() or {}).get("id")
            self.chat_list.clear()
            for msg in (chat.latest(200) if chat is not None else []):
                when = time.strftime("%H:%M", time.localtime(msg["t"]))
                prefix = "📢 " if msg.get("host") else (msg.get("avatar", "") + " " if msg.get("avatar") else "")
                item = QListWidgetItem(f"{when}  {prefix}{msg['name']}: {msg['text']}" +
                                       ("  (gefiltert)" if msg.get("filtered") else ""))
                item.setData(Qt.UserRole, msg)
                item.setToolTip(f"Handy: {msg.get('ip') or 'PC'}")
                self.chat_list.addItem(item)
                if msg["id"] == selected:
                    self.chat_list.setCurrentItem(item)
            if not self.chat_list.count():
                self.chat_list.addItem("Noch keine Nachrichten." if chat is not None else
                                       "Chat ist aus – „Chat starten“: Handys schreiben über den Chat-Code auf dem Bildschirm.")
            if at_end:
                self.chat_list.scrollToBottom()
        wall = c.cast.wall
        _pill(self.wall_pill, wall is not None)
        self.wall_toggle.setText("Foto-Wand beenden" if wall is not None else "Foto-Wand starten")
        self.wall_toggle.setIcon(icons.icon("x" if wall is not None else "play", theme.current().text, 18))
        version = (wall.version, len(wall.photos)) if wall is not None else -1
        if version != self._wall_version or force:
            self._wall_version = version
            self.wall_list.clear()
            for photo in reversed(wall.latest(120) if wall is not None else []):
                pix = QPixmap(photo.get("thumb") or photo["path"])
                if not pix.isNull():
                    pix = pix.scaled(96, 96, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                item = QListWidgetItem(QIcon(pix), photo["name"])
                item.setData(Qt.UserRole, photo)
                item.setToolTip(f"{photo['name']} · {time.strftime('%H:%M', time.localtime(photo['t']))}")
                self.wall_list.addItem(item)
            n = len(wall.photos) if wall is not None else 0
            self.wall_folder.setText(f"{n} Fotos auf der Wand · Ordner: {self._folder()}")

    def showEvent(self, e):
        super().showEvent(e)
        self.refresh(force=True)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        wide = self.width() >= 1000  # schmal: Chat und Foto-Wand untereinander
        if wide != self._wide:
            self._wide = wide
            self.grid.removeWidget(self.wall_card)
            self.grid.addWidget(self.wall_card, 0 if wide else 1, 1 if wide else 0)
            self.grid.setColumnStretch(1, 1 if wide else 0)

    def minimumSizeHint(self):
        hint = super().minimumSizeHint()
        hint.setWidth(min(hint.width(), max(self.chat_card.minimumSizeHint().width(),
                                            self.wall_card.minimumSizeHint().width())))
        return hint
