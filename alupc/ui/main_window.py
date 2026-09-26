"""Hauptfenster: Seitenleiste, Statuskarte und große Kacheln – ein Klick, fertig."""

from __future__ import annotations

import copy
import sys

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QAction
from PySide6.QtMultimedia import QMediaDevices
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from .. import APP_NAME, __version__
from ..controller import HANDY_NOTES
from ..scenes import describe_source
from ..sources import camera_id, normalize_url
from . import icons, theme
from .fingerprint_page import FingerprintPage
from .icons import app_icon
from .program_dialog import ProgramDialog
from .camera_bar import CameraBar
from .media_bar import MediaBar
from .volume_box import VolumeBox
from .scene_editor import SceneEditor
from .setup_page import SetupPage
from .source_picker import IMAGE_FILTER, VIDEO_FILTER
from ..startpage import BUILTIN_TILES, SECTIONS, custom_key, find_custom, ordered_keys, section_of
from .start_page_dialog import StartPageDialog
from .widgets import EmptyState, NavButton, SceneCard, StatusCard, Tile, Toast, button, font, page_header

__all__ = ["MainWindow", "app_icon"]

# Farben der Schnell-Kacheln (Zustand „an“)
FREEZE_COLOR = "#0ea5e9"
PRIVACY_COLOR = "#64748b"
PIP_COLOR = "#8b5cf6"


class FlowGrid(QWidget):
    """Legt Kacheln in so vielen Spalten an, wie die Fensterbreite hergibt."""

    def __init__(self, min_width: int = 170, max_cols: int = 4, spacing: int = 14, fixed=False, parent=None):
        super().__init__(parent)
        self.items: list[QWidget] = []
        self.min_width, self.max_cols, self.fixed = min_width, max_cols, fixed
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(spacing)
        self._cols = 0

    def set_items(self, items):
        for w in self.items:
            self.grid.removeWidget(w)
        self.items = list(items)
        self._cols = 0
        self._relayout()

    def _relayout(self):
        spacing = self.grid.spacing()
        cols = max(1, min(self.max_cols, (self.width() + spacing) // (self.min_width + spacing)))
        if cols == self._cols:
            return
        self._cols = cols
        for w in self.items:
            self.grid.removeWidget(w)
        for i, w in enumerate(self.items):
            align = Qt.AlignLeft | Qt.AlignTop if self.fixed else Qt.Alignment()
            self.grid.addWidget(w, i // cols, i % cols, align)
        for c in range(self.max_cols):
            self.grid.setColumnStretch(c, 0 if self.fixed else (1 if c < cols else 0))
        if self.fixed:
            self.grid.setColumnStretch(cols, 1)

    def resizeEvent(self, e):
        self._relayout()
        super().resizeEvent(e)


class WebsiteDialog(QDialog):
    """Website öffnen: gespeicherte Websites (Favoriten) oder eine neue Adresse."""

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Website anzeigen")
        self.setMinimumSize(560, 480)
        recent = list(config.data.get("recent_urls", []))
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 20, 22, 18)
        lay.setSpacing(12)
        lay.addWidget(page_header("Website anzeigen", "Die Seite erscheint im Vollbild auf Monitor 2."))
        caption = QLabel("Gespeicherte Websites")
        caption.setObjectName("SectionTitle")
        lay.addWidget(caption)
        self.favs = QListWidget()
        self.favs.itemDoubleClicked.connect(lambda _i: self._use_favorite())
        self.favs.currentItemChanged.connect(lambda item, _p: item and self.combo.setCurrentText(
            item.data(Qt.UserRole)))
        lay.addWidget(self.favs, 1)
        fav_row = QHBoxLayout()
        remove = button("Entfernen", "trash", danger=True)
        remove.clicked.connect(self._remove)
        rename = button("Umbenennen …", "edit")
        rename.clicked.connect(self._rename)
        fav_row.addWidget(rename)
        fav_row.addWidget(remove)
        fav_row.addStretch(1)
        lay.addLayout(fav_row)
        self.combo = QComboBox()
        self.combo.setEditable(True)
        self.combo.addItems(recent)
        self.combo.setCurrentText(recent[0] if recent else "")
        self.combo.lineEdit().setPlaceholderText("z. B. www.beispiel.de")
        self.combo.setMinimumHeight(38)
        self.save_it = QCheckBox("Unter „Website“ speichern")
        self.control_it = QCheckBox("Danach das Fenster „Browser steuern“ öffnen")
        form = QFormLayout()
        form.addRow("Adresse:", self.combo)
        form.addRow("", self.save_it)
        form.addRow("", self.control_it)
        lay.addLayout(form)
        buttons = QDialogButtonBox()
        ok = button("Anzeigen", "play", primary=True)
        cancel = button("Abbrechen")
        buttons.addButton(ok, QDialogButtonBox.AcceptRole)
        buttons.addButton(cancel, QDialogButtonBox.RejectRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)
        self._fill()

    def _fill(self):
        self.favs.clear()
        t = theme.current()
        for fav in self.config["websites"].get("favorites", []):
            item = QListWidgetItem(icons.icon("globe", t.accent, 20), f"{fav.get('title')}   —   {fav.get('url')}")
            item.setData(Qt.UserRole, fav.get("url"))
            item.setData(Qt.UserRole + 1, fav.get("title"))
            self.favs.addItem(item)
        if not self.favs.count():
            item = QListWidgetItem("Noch keine gespeicherten Websites – unten eine Adresse eingeben und "
                                   "„Unter Website speichern“ anhaken.")
            item.setFlags(Qt.NoItemFlags)
            self.favs.addItem(item)

    def _use_favorite(self):
        item = self.favs.currentItem()
        if item is not None and item.data(Qt.UserRole):
            self.combo.setCurrentText(item.data(Qt.UserRole))
            self.accept()

    def _selected(self):
        item = self.favs.currentItem()
        return item.data(Qt.UserRole) if item is not None else None

    def _remove(self):
        url = self._selected()
        if url:
            favs = [f for f in self.config["websites"].get("favorites", []) if f.get("url") != url]
            self.config["websites"] = {**self.config["websites"], "favorites": favs}
            self._fill()

    def _rename(self):
        url = self._selected()
        if not url:
            return
        from PySide6.QtWidgets import QInputDialog

        old = self.favs.currentItem().data(Qt.UserRole + 1)
        name, ok = QInputDialog.getText(self, "Umbenennen", "Name:", text=old)
        if ok and name.strip():
            favs = [dict(f, title=name.strip()) if f.get("url") == url else f
                    for f in self.config["websites"].get("favorites", [])]
            self.config["websites"] = {**self.config["websites"], "favorites": favs}
            self._fill()

    def url(self) -> str:
        return normalize_url(self.combo.currentText())


def _padded(widget: QWidget, scroll: bool = False) -> QWidget:
    wrap = QWidget()
    lay = QVBoxLayout(wrap)
    lay.setContentsMargins(28, 24, 28, 20)
    lay.setSpacing(16)
    lay.addWidget(widget)
    if not scroll:
        return wrap
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setWidget(wrap)
    return area


class LazyPage(QWidget):
    """Seite, die erst beim ersten Anzeigen gebaut wird – AluPC startet dadurch schneller."""

    def __init__(self, builder, parent=None):
        super().__init__(parent)
        self.builder = builder
        self.built = False
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(0, 0, 0, 0)

    def ensure(self) -> None:
        if not self.built:
            self.built = True
            self._lay.addWidget(self.builder())

    def showEvent(self, e):
        self.ensure()
        super().showEvent(e)


class MainWindow(QMainWindow):
    def __init__(self, controller, hotkeys):
        super().__init__()
        self.controller = controller
        self.config = controller.config
        self.hotkeys = hotkeys
        self.setWindowTitle(f"{APP_NAME} – Monitor 2 steuern")
        self.setWindowIcon(app_icon())
        self.resize(1080, 720)
        self.setMinimumSize(760, 560)

        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._sidebar())
        self.stack = QStackedWidget()
        root.addWidget(self.stack, 1)
        self.setCentralWidget(central)

        self.setup = None
        self.pages = [
            _padded(self._start_page(), scroll=True),
            _padded(self._scenes_page()),
            # Setup und Fingerabdruck erst beim ersten Öffnen bauen (spart ~40 % der Startzeit)
            LazyPage(lambda: _padded(self._setup_page())),
            LazyPage(lambda: _padded(self._finger_page(), scroll=True)),
        ]
        for page in self.pages:
            self.stack.addWidget(page)
        self.nav_group.buttons()[0].setChecked(True)

        self.toast = Toast(self)
        self._build_tray()
        controller.changed.connect(self.refresh)
        controller.message.connect(self.show_message)
        controller.presenter_requested.connect(self.open_presenter)
        controller.settings_imported.connect(self._settings_imported)
        controller.cast.state_changed.connect(self.refresh)  # Kachel „Handy-Steuerung“: LÄUFT an/aus
        self.refresh()

    # ================================================================ Seitenleiste
    def _sidebar(self):
        side = QWidget()
        side.setObjectName("Sidebar")
        side.setAttribute(Qt.WA_StyledBackground, True)
        side.setFixedWidth(224)
        lay = QVBoxLayout(side)
        lay.setContentsMargins(8, 20, 8, 16)
        lay.setSpacing(4)

        brand = QHBoxLayout()
        brand.setContentsMargins(14, 0, 8, 18)
        logo = QLabel()
        logo.setPixmap(app_icon().pixmap(38, 38))
        names = QVBoxLayout()
        names.setSpacing(0)
        title = QLabel(APP_NAME)
        title.setObjectName("Brand")
        sub = QLabel("Monitor 2 steuern")
        sub.setObjectName("BrandSub")
        names.addWidget(title)
        names.addWidget(sub)
        brand.addWidget(logo)
        brand.addSpacing(8)
        brand.addLayout(names, 1)
        lay.addLayout(brand)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        # (Seiten-Nummer, Symbol, Text) – Reihenfolge in der Leiste, Nummer = Seite im Stapel
        for i, icon_name, text in [(0, "home", "Start"), (1, "scenes", "Szenen"), (2, "sliders", "Setup"),
                                   (3, "fingerprint", "Fingerabdruck")]:
            b = NavButton(icon_name, text)
            self.nav_group.addButton(b, i)
            lay.addWidget(b)
        self.nav_group.idClicked.connect(self._go)
        lay.addStretch(1)

        self.side_monitor = QLabel()
        self.side_monitor.setObjectName("Muted")
        self.side_monitor.setWordWrap(True)
        self.side_monitor.setContentsMargins(14, 0, 8, 8)
        lay.addWidget(self.side_monitor)
        lock = NavButton("lock", "Computer sperren")
        lock.setToolTip("Wie Win+L – Monitor 2 zeigt weiter, was gerade läuft")
        lock.setCheckable(False)
        lock.clicked.connect(self.lock)
        lay.addWidget(lock)
        version = QLabel(f"Version {__version__}")
        version.setObjectName("Muted")
        version.setContentsMargins(14, 6, 0, 0)
        version.setFont(font(8.5))
        lay.addWidget(version)
        return side

    def _go(self, index: int):
        page = self.pages[index]
        if isinstance(page, LazyPage):
            page.ensure()
        self.stack.setCurrentIndex(index)
        self.nav_group.button(index).setChecked(True)

    # ================================================================ Start
    def _start_page(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(16)
        top = QHBoxLayout()
        self.start_header = QWidget()
        head = QVBoxLayout(self.start_header)
        head.setContentsMargins(0, 0, 0, 6)
        head.setSpacing(2)
        self.start_title = QLabel()
        self.start_title.setObjectName("PageTitle")
        self.start_subtitle = QLabel()
        self.start_subtitle.setObjectName("PageSubtitle")
        self.start_subtitle.setWordWrap(True)
        head.addWidget(self.start_title)
        head.addWidget(self.start_subtitle)
        top.addWidget(self.start_header, 1)
        customize = button("Startseite anpassen", "edit")
        customize.clicked.connect(self.customize_start)
        top.addWidget(customize, 0, Qt.AlignTop)
        lay.addLayout(top)
        self.status_card = StatusCard()
        self.status_card.preview.clicked.connect(self.controller.toggle_pip)
        self.stop_btn = button("Beenden", "x")
        self.stop_btn.setToolTip("AluPC-Anzeige beenden – Monitor 2 wird wieder ein normaler Bildschirm (Erweitern)")
        self.stop_btn.clicked.connect(self.controller.extend)
        self.status_card.actions.addWidget(self.stop_btn, 0, Qt.AlignRight)
        # Schnellschalter direkt beim Live-Bild (statt eigener Kacheln)
        self.chips = {}
        for key, icon_name, text, slot, tip in [
            ("black", "eye_off", "Schwarz", self.controller.toggle_privacy, "Sichtschutz an/aus (Strg+Alt+B)"),
            ("freeze", "snowflake", "Standbild", self.controller.toggle_freeze, "Bild einfrieren (Strg+Alt+S)"),
            ("pip", "pip", "Bild-in-Bild", self.controller.toggle_pip, "Monitor 2 klein auf Monitor 1"),
            ("draw", "edit", "Zeichnen", self.open_presenter, "Zeigen & Zeichnen (Strg+Alt+K)"),
        ]:
            chip = QPushButton(text)
            chip.setObjectName("Chip")
            chip.setCheckable(True)
            chip.setCursor(Qt.PointingHandCursor)
            chip.setToolTip(tip)
            chip.setProperty("iconName", icon_name)
            chip.setIcon(icons.icon(icon_name, theme.current().text, 16))
            chip.clicked.connect(slot)
            self.chips[key] = chip
            self.status_card.chips.addWidget(chip)
        # Live-Vorschau von Monitor 2 in der Statuskarte (nur wenn die Startseite zu sehen ist)
        self._preview_timer = QTimer(self, interval=1000)
        self._preview_timer.timeout.connect(self._update_preview)
        self._preview_timer.start()
        self.volume_box = VolumeBox(self.controller)
        self.status_card.actions.addStretch(1)
        self.status_card.actions.addWidget(self.volume_box)
        lay.addWidget(self.status_card)
        self.media_bar = MediaBar(self.controller)
        lay.addWidget(self.media_bar)
        self.camera_bar = CameraBar(self.controller)
        lay.addWidget(self.camera_bar)

        c = self.controller
        # Standard-Kacheln (einmal angelegt, je nach Einstellung angezeigt)
        self.tiles: dict[str, Tile] = {}
        for key, (icon_name, title, subtitle, color, _section) in BUILTIN_TILES.items():
            self.tiles[key] = Tile(icon_name, title, subtitle, color)
        self.t_mirror, self.t_extend = self.tiles["mirror"], self.tiles["extend"]
        self.t_camera, self.t_program = self.tiles["camera"], self.tiles["program"]
        self.t_web, self.t_media, self.t_scenes = self.tiles["website"], self.tiles["media"], self.tiles["scenes"]
        self.t_freeze, self.t_black, self.t_pip = self.tiles["freeze"], self.tiles["black"], self.tiles["pip"]
        self.t_saver = self.tiles["screensaver"]
        self.t_draw = self.tiles["draw"]
        self.t_draw.activated.connect(self.open_presenter)
        draw_menu = QMenu(self)
        draw_menu.addAction(icons.icon("edit", theme.current().text, 18), "Zeigen & Zeichnen öffnen …",
                            self.open_presenter)
        draw_menu.addAction(icons.icon("trash", theme.current().text, 18), "Zeichnungen auf Monitor 2 löschen",
                            c.laser.clear_strokes)
        self.t_draw.set_menu(draw_menu, split=True)
        # Handy: eigene Kachel je Weg – Klick startet, Pfeil zeigt Optionen und die Handy-Seite
        self.t_airplay, self.t_remote = self.tiles["airplay"], self.tiles["handy_remote"]
        self.handy_menus = {}
        for key, tile, start in [("airplay", self.t_airplay, c.start_airplay),
                                 ("handy_remote", self.t_remote, c.start_cast)]:
            tile.activated.connect(start)
            menu = QMenu(self)
            menu.aboutToShow.connect(lambda m=menu, k=key: self._fill_handy_menu(m, k))
            tile.set_menu(menu, split=True)
            self.handy_menus[key] = menu

        self.t_mirror.clicked.connect(c.mirror)
        self.t_extend.clicked.connect(c.extend)
        self.t_camera.activated.connect(self._camera_clicked)
        self.t_program.clicked.connect(self.open_program_dialog)
        self.t_web.activated.connect(self.pick_website)
        self.website_menu = QMenu(self)
        self.website_menu.aboutToShow.connect(lambda: self._fill_website_menu(self.website_menu))
        self.t_web.set_menu(self.website_menu, split=True)
        self.t_black.clicked.connect(c.toggle_privacy)
        self.t_freeze.clicked.connect(c.toggle_freeze)
        self.t_pip.clicked.connect(c.toggle_pip)
        self.t_saver.activated.connect(c.toggle_screensaver)
        saver_menu = QMenu(self)
        saver_menu.addAction(icons.icon("moon", theme.current().text, 18), "Jetzt starten / beenden",
                             c.toggle_screensaver)
        saver_menu.addAction(icons.icon("sliders", theme.current().text, 18), "Einstellungen …",
                             self.edit_screensaver)
        self.t_saver.set_menu(saver_menu, split=True)
        self.t_timer = self.tiles["timer"]
        self.t_timer.activated.connect(self._timer_clicked)
        timer_menu = QMenu(self)
        self._fill_timer_menu(timer_menu)
        self.t_timer.set_menu(timer_menu, split=True)
        # Timer-Anzeige auf Kachel/Statuskarte jede Sekunde aktualisieren
        self._timer_tick = QTimer(self, interval=500)
        self._timer_tick.timeout.connect(self._update_timer_ui)
        self._timer_tick.start()
        self.camera_menu = QMenu(self)
        self.camera_menu.aboutToShow.connect(lambda: self._fill_camera_menu(self.camera_menu))
        self.t_camera.set_menu(self.camera_menu, split=True)
        self.media_menu = QMenu(self)
        self.media_menu.aboutToShow.connect(lambda: self._fill_media_menu(self.media_menu))
        self.t_media.set_menu(self.media_menu, split=True)
        self.t_media.activated.connect(self.open_media_library)
        self.scene_menu = QMenu(self)
        self.scene_menu.aboutToShow.connect(lambda: self._fill_scene_menu(self.scene_menu))
        self.t_scenes.set_menu(self.scene_menu, split=True)
        self.t_scenes.activated.connect(lambda: self._go(1))  # Klick: Szenen-Seite, Pfeil: Szene starten
        self.custom_tiles: dict[str, Tile] = {}

        self.section_labels = {}
        self.section_grids = {}
        for key, label in SECTIONS.items():
            title = QLabel(label)
            title.setObjectName("SectionTitle")
            grid = FlowGrid(min_width=270, max_cols=4, spacing=12)
            self.section_labels[key] = title
            self.section_grids[key] = grid
            lay.addWidget(title)
            lay.addWidget(grid)
        self.start_empty = QLabel("Alle Kacheln sind ausgeblendet – über „Startseite anpassen“ wieder einblenden.")
        self.start_empty.setObjectName("Muted")
        lay.addWidget(self.start_empty)
        hint = QLabel()
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        self.shortcut_hint = hint
        lay.addWidget(hint)
        lay.addStretch(1)
        self.rebuild_start()
        return page

    def rebuild_start(self):
        """Startseite nach den Einstellungen neu zusammensetzen."""
        cfg = self.config["start_page"]
        self.start_title.setText(cfg.get("title") or "Was sollen die anderen sehen?")
        self.start_subtitle.setText(cfg.get("subtitle") or "Ein Klick auf eine Kachel – und Monitor 2 zeigt es sofort.")
        self.status_card.setVisible(bool(cfg.get("show_status", True)))
        self.shortcut_hint.setVisible(bool(cfg.get("show_hint", True)))
        # eigene Kacheln neu anlegen
        for tile in self.custom_tiles.values():
            tile.deleteLater()
        self.custom_tiles = {}
        for tile_cfg in cfg.get("custom", []):
            tile = Tile(tile_cfg.get("icon", "star"), tile_cfg.get("title", ""), tile_cfg.get("subtitle", ""),
                        tile_cfg.get("color"))
            tile.clicked.connect(lambda _=False, i=tile_cfg["id"]: self.controller.run_tile(i))
            self.custom_tiles[custom_key(tile_cfg)] = tile
        per_section = {key: [] for key in SECTIONS}
        keys = ordered_keys(cfg)
        for key in keys:
            widget = self.tiles.get(key) or self.custom_tiles.get(key)
            if widget is not None:
                per_section.setdefault(section_of(key, cfg), []).append(widget)
        shown = set()
        for key, grid in self.section_grids.items():
            items = per_section.get(key, [])
            grid.set_items(items)
            shown.update(items)
            grid.setVisible(bool(items))
            self.section_labels[key].setVisible(bool(items))
        for widget in list(self.tiles.values()) + list(self.custom_tiles.values()):
            widget.setVisible(widget in shown)
        self.start_empty.setVisible(not shown)
        if hasattr(self, "a_freeze"):
            self.refresh()

    def _apply_hotkeys(self):
        problems = self.hotkeys.apply(self.config["hotkeys"])
        for text in problems:
            self.show_message(text, "warn")

    def _timer_clicked(self):
        c = self.controller
        if not c.timer_visible():
            c.show_timer()  # erst anzeigen …
            from ..timer import clock

            if clock.fresh():
                c.timer_action("toggle")  # … und beim ersten Mal gleich starten
        else:
            c.timer_action("toggle")

    def _update_timer_ui(self):
        from ..timer import clock

        if clock.fresh():
            badge = ""
        elif clock.finished():
            badge = "ENDE"
        else:
            badge = clock.text() + ("" if clock.running else " ⏸")
        self.t_timer.set_state(clock.running or clock.finished(), badge=badge)
        c = self.controller
        if c.content and c.content.get("type") == "countdown" and c.mode == "content":
            self.status_card.title.setText(c.describe())
        self.tray_timer.setTitle(f"Timer  {badge}".rstrip())

    def customize_start(self):
        dlg = StartPageDialog(self.config, self, self.controller)
        if dlg.exec() == QDialog.Accepted:
            self.rebuild_start()
            self.show_message("Startseite gespeichert.", "ok")
            self._apply_hotkeys()

    def _camera_clicked(self):
        """Klick: Standard-Kamera sofort zeigen (vorausgewählt: gewählte oder erste). Pfeil: andere wählen."""
        self.controller.start_camera()

    def _fill_camera_menu(self, menu):
        menu.clear()
        col = theme.current().text
        devices = QMediaDevices.videoInputs()
        if not devices:
            act = menu.addAction("Keine Kamera gefunden")
            act.setEnabled(False)
            return
        current = (self.controller.default_camera() or {}).get("device_id")
        for d in devices:
            cfg = {"type": "camera", "device_id": camera_id(d), "name": d.description(),
                   "fit": self.config.get("camera_fit", "cover") or "cover"}
            act = menu.addAction(icons.icon("camera", col, 18), d.description(),
                                 lambda c=cfg: self._use_camera(c))
            act.setCheckable(True)
            act.setChecked(cfg["device_id"] == current)

    def _use_camera(self, cfg: dict):
        """Kamera aus dem Pfeil-Menü: zeigen und als Standard merken (nächster Klick nimmt sie wieder)."""
        self.config["default_camera"] = cfg["device_id"]
        self.controller.start_camera(cfg)

    def _fill_scene_menu(self, menu):
        menu.clear()
        names = self.config.scene_names()
        if not names:
            act = menu.addAction("Noch keine Szene angelegt")
            act.setEnabled(False)
        for name in names:
            menu.addAction(icons.icon("scenes", theme.current().text, 18), name,
                           lambda n=name: self.controller.show_source({"type": "scene", "scene": n}))
        menu.addSeparator()
        menu.addAction(icons.icon("plus", theme.current().text, 18), "Neue Szene …", self.new_scene)

    def open_program_dialog(self):
        dialog = ProgramDialog(self.controller, self)
        dialog.setAttribute(Qt.WA_DeleteOnClose)  # nicht bei jedem Öffnen ein Fenster übrig lassen
        dialog.exec()

    def pick_website(self):
        dlg = WebsiteDialog(self.config, self)
        if dlg.exec() != QDialog.Accepted or not dlg.url():
            return
        url = dlg.url()
        recent = list(self.config.data.get("recent_urls", []))
        self.config["recent_urls"] = [url] + [u for u in recent if u != url][:9]
        self.controller.show_source({"type": "website", "url": url})
        if dlg.save_it.isChecked():
            self._save_current_later(url)
        if dlg.control_it.isChecked():
            self.open_browser_control()

    def _save_current_later(self, url: str):
        """Name der Seite abwarten (Titel kommt erst nach dem Laden), dann speichern."""
        view = self.controller.current_web_view()

        def save(ok=True):
            title = (view.title() if view is not None else "") or QUrl(url).host() or url
            self.controller.save_website(title, url)

        if view is None:
            save()
            return
        done = {"x": False}

        def once(ok):
            if not done["x"]:
                done["x"] = True
                save(ok)

        view.loadFinished.connect(once)
        QTimer.singleShot(8000, lambda: once(False))

    def save_current_website(self):
        view = self.controller.current_web_view()
        if view is None:
            self.show_message("Auf Monitor 2 läuft gerade keine Website.", "warn")
            return
        from PySide6.QtWidgets import QInputDialog

        title = view.title() or view.url().host()
        name, ok = QInputDialog.getText(self, "Website speichern", "Name für die Website:", text=title)
        if ok:
            self.controller.save_website(name.strip() or title, view.url().toString())

    def _fill_handy_menu(self, menu, key: str):
        """Pfeil-Menü einer Handy-Kachel."""
        c = self.controller
        col = theme.current().text
        menu.clear()
        page = ("sliders", "Einrichten und Hilfe …", self.open_handy_window)
        items = {
            "airplay": [("phone", "Auf Monitor 2 zeigen", c.start_airplay)],
            "handy_remote": [("qr", "QR-Code auf Monitor 2 zeigen", c.start_cast)]
            + ([("x", "Handy-Steuerung beenden", c.stop_cast)] if c.cast.running() else [])
            + [("refresh", "Neuer Code (alter QR-Code ungültig)", c.cast.renew_code)],
        }[key]
        for icon_name, text, slot in items:
            menu.addAction(icons.icon(icon_name, col, 18), text, slot)
        menu.addSeparator()
        menu.addAction(icons.icon(page[0], col, 18), page[1], page[2])

    def open_presenter(self):
        """Fenster „Zeigen & Zeichnen“ auf Monitor 1 öffnen (bzw. nach vorne holen)."""
        from .presenter_window import PresenterWindow

        if getattr(self, "presenter", None) is None:
            self.presenter = PresenterWindow(self.controller, self)
        win = self.presenter
        screen = self.controller.main_screen()
        if screen is not None and not win.isVisible():
            g = screen.availableGeometry()
            win.resize(min(win.width(), g.width() - 40), min(win.height(), g.height() - 40))
            win.move(g.x() + (g.width() - win.width()) // 2, g.y() + (g.height() - win.height()) // 2)
        win.show()
        win.raise_()
        win.activateWindow()

    def open_browser_control(self):
        from .browser_control import BrowserControl

        if getattr(self, "browser_control", None) is None:
            self.browser_control = BrowserControl(self.controller, self.controller.save_website, self)
        win = self.browser_control
        screen = self.controller.main_screen()
        if screen is not None and not win.isVisible():
            g = screen.availableGeometry()
            win.move(g.x() + (g.width() - win.width()) // 2, g.y() + (g.height() - win.height()) // 2)
        win.show()
        win.raise_()
        win.activateWindow()

    def _fill_website_menu(self, menu):
        t = theme.current()
        menu.clear()
        favs = self.config["websites"].get("favorites", [])
        for fav in favs[:15]:
            menu.addAction(icons.icon("globe", t.text, 18), fav.get("title") or fav.get("url"),
                           lambda u=fav.get("url"): self.controller.show_source({"type": "website", "url": u}))
        if not favs:
            act = menu.addAction("Noch keine gespeicherten Websites")
            act.setEnabled(False)
        menu.addSeparator()
        menu.addAction(icons.icon("sliders", t.text, 18), "Browser steuern …", self.open_browser_control)
        save = menu.addAction(icons.icon("bookmark", t.text, 18), "Aktuelle Website speichern …",
                              self.save_current_website)
        save.setEnabled(self.controller.current_web_view() is not None)
        menu.addAction(icons.icon("plus", t.text, 18), "Website öffnen / verwalten …", self.pick_website)

    def open_media_library(self):
        from .media_library import MediaLibraryDialog

        dialog = MediaLibraryDialog(self.controller, self)
        dialog.setAttribute(Qt.WA_DeleteOnClose)
        dialog.exec()

    def _fill_media_menu(self, menu):
        from .. import media_library as lib

        t = theme.current()
        menu.clear()
        kinds = {"image": "image", "video": "video", "slideshow": "slides"}
        items = lib.saved(self.config)[:10]
        for item in items:
            cfg = {k: v for k, v in item.items() if k != "title"}
            act = menu.addAction(icons.icon(kinds.get(item.get("type"), "image"), t.text, 18), item.get("title", ""),
                                 lambda c=cfg: self.controller.show_source(c))
            act.setEnabled(lib.exists(item))
        if not items:
            act = menu.addAction("Noch nichts in der Mediathek gespeichert")
            act.setEnabled(False)
        recent = lib.recent(self.config)[:5]
        if recent:
            sub = menu.addMenu(icons.icon("clock", t.text, 18), "Zuletzt gezeigt")
            for item in recent:
                cfg = {k: v for k, v in item.items() if k != "title"}
                act = sub.addAction(icons.icon(kinds.get(item.get("type"), "image"), t.text, 18),
                                    item.get("title", ""), lambda c=cfg: self.controller.show_source(c))
                act.setEnabled(lib.exists(item))
        menu.addSeparator()
        menu.addAction(icons.icon("image", t.text, 18), "Bild öffnen …", self.pick_image)
        menu.addAction(icons.icon("video", t.text, 18), "Video öffnen …", self.pick_video)
        menu.addAction(icons.icon("slides", t.text, 18), "Diashow aus Ordner …", self.pick_slideshow)
        current = self.controller.current_media()
        save = menu.addAction(icons.icon("bookmark", t.text, 18), "Aktuelles in der Mediathek speichern",
                              lambda: self.controller.save_media(current))
        save.setEnabled(current is not None and not lib.is_saved(self.config, current))
        menu.addAction(icons.icon("grid", t.text, 18), "Mediathek öffnen …", self.open_media_library)

    def pick_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "Bild wählen", "", IMAGE_FILTER)
        if path:
            self.controller.show_source({"type": "image", "path": path})

    def pick_video(self):
        path, _ = QFileDialog.getOpenFileName(self, "Video wählen", "", VIDEO_FILTER)
        if path:
            self.controller.show_source({"type": "video", "path": path, "loop": True})

    def pick_slideshow(self):
        folder = QFileDialog.getExistingDirectory(self, "Ordner mit Bildern wählen")
        if folder:
            self.controller.show_source({"type": "slideshow", "folder": folder, "interval": 5})

    # ================================================================ Szenen
    def _scenes_page(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)
        top = QHBoxLayout()
        top.addWidget(page_header("Meine Szenen", "Eigene Zusammenstellungen – nur von dir erstellt."), 1)
        new = button("Neue Szene", "plus", primary=True)
        new.clicked.connect(self.new_scene)
        top.addWidget(new, 0, Qt.AlignTop)
        lay.addLayout(top)

        self.scene_actions = QHBoxLayout()
        self.scene_actions.setSpacing(8)
        for text, icon_name, slot, kwargs in [
            ("Anzeigen", "play", self.show_scene, {}),
            ("Bearbeiten", "edit", self.edit_scene, {}),
            ("Duplizieren", "copy", self.duplicate_scene, {}),
            ("Löschen", "trash", self.delete_scene, {"danger": True}),
        ]:
            b = button(text, icon_name, **kwargs)
            b.clicked.connect(slot)
            self.scene_actions.addWidget(b)
        self.scene_actions.addStretch(1)
        self.scene_detail = QLabel()
        self.scene_detail.setObjectName("Muted")
        self.scene_detail.setWordWrap(True)
        lay.addLayout(self.scene_actions)
        lay.addWidget(self.scene_detail)

        self.scene_stack = QStackedWidget()
        empty_btn = button("Erste Szene anlegen", "plus", primary=True)
        empty_btn.clicked.connect(self.new_scene)
        self.scene_stack.addWidget(EmptyState(
            "scenes", "Noch keine Szene",
            "Wähle eine Layout-Vorlage und lege in jedes Feld eine Quelle:\n"
            "Kamera, Programm, Website, Bild, Text, Uhr …", empty_btn))
        area = QScrollArea()
        area.setWidgetResizable(True)
        self.scene_grid = FlowGrid(min_width=236, max_cols=6, fixed=True)
        holder = QWidget()
        hl = QVBoxLayout(holder)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.addWidget(self.scene_grid)
        hl.addStretch(1)
        area.setWidget(holder)
        self.scene_stack.addWidget(area)
        lay.addWidget(self.scene_stack, 1)
        self.scene_group = QButtonGroup(self)
        self.scene_cards: list[SceneCard] = []
        self._reload_scenes()
        return page

    def _reload_scenes(self, select: str | None = None):
        current = select or (self._selected_scene() or {}).get("name")
        for card in self.scene_cards:
            self.scene_group.removeButton(card)
            card.deleteLater()
        self.scene_cards = []
        for scene in self.config["scenes"]:
            card = SceneCard(scene)
            card.double_clicked.connect(self.show_scene)
            card.toggled.connect(lambda on, s=scene: on and self._scene_selected(s))
            self.scene_group.addButton(card)
            self.scene_cards.append(card)
        self.scene_grid.set_items(self.scene_cards)
        has = bool(self.scene_cards)
        self.scene_stack.setCurrentIndex(1 if has else 0)
        for i in range(self.scene_actions.count()):
            w = self.scene_actions.itemAt(i).widget()
            if w:
                w.setVisible(has)
        self.scene_detail.setVisible(has)
        target = next((c for c in self.scene_cards if c.scene["name"] == current), None)
        target = target or (self.scene_cards[0] if self.scene_cards else None)
        if target:
            target.setChecked(True)
            self._scene_selected(target.scene)
        self._fill_tray_scenes()
        self._mark_live_scene()
        if getattr(self, "setup", None) is not None:
            self.setup.refresh_scene_lists()
        if hasattr(self, "a_freeze"):
            self._apply_hotkeys()

    def _scene_selected(self, scene):
        from ..scenes import LAYOUTS, layout_slots

        parts = [f"<b>{scene['name']}</b> · {LAYOUTS.get(scene['layout'], ('?',))[0]}"]
        for (_x, _y, _w, _h, slot_name), slot in zip(layout_slots(scene["layout"]), scene["slots"]):
            parts.append(f"{slot_name}: {describe_source(slot)}")
        self.scene_detail.setText("  ·  ".join(parts))

    def _selected_scene(self):
        card = self.scene_group.checkedButton() if hasattr(self, "scene_group") else None
        return self.config.get_scene(card.scene["name"]) if card else None

    def _mark_live_scene(self):
        c = self.controller
        live = c.content.get("scene") if c.mode == "content" and c.content and c.content.get("type") == "scene" \
            else None
        for card in getattr(self, "scene_cards", []):
            card.live = card.scene["name"] == live
            card.update()

    def show_scene(self):
        scene = self._selected_scene()
        if scene:
            self.controller.show_source({"type": "scene", "scene": scene["name"]})

    def new_scene(self):
        dlg = SceneEditor(self.config, None, self)
        if dlg.exec() == QDialog.Accepted:
            self._reload_scenes(dlg.scene["name"])
            self.show_message(f"Szene „{dlg.scene['name']}“ gespeichert.", "ok")

    def edit_scene(self):
        scene = self._selected_scene()
        if not scene:
            return
        dlg = SceneEditor(self.config, scene, self)
        if dlg.exec() == QDialog.Accepted:
            self._reload_scenes(dlg.scene["name"])
            c = self.controller
            if c.content and c.content.get("type") == "scene" and c.content.get("scene") in (scene["name"],
                                                                                              dlg.scene["name"]):
                c.show_source({"type": "scene", "scene": dlg.scene["name"]})  # geänderte Szene neu laden

    def duplicate_scene(self):
        scene = self._selected_scene()
        if not scene:
            return
        new = copy.deepcopy(scene)
        names = set(self.config.scene_names())
        i = 2
        while f"{scene['name']} ({i})" in names:
            i += 1
        new["name"] = f"{scene['name']} ({i})"
        self.config.put_scene(new)
        self._reload_scenes(new["name"])

    def delete_scene(self):
        scene = self._selected_scene()
        if scene and QMessageBox.question(self, "Löschen", f"Szene „{scene['name']}“ löschen?") == QMessageBox.Yes:
            self.config.delete_scene(scene["name"])
            self._reload_scenes()

    # ================================================================ Setup / Fingerabdruck
    def _setup_page(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(page_header("Setup", "Alle Einstellungen – links den Bereich wählen."))
        self.setup = SetupPage(self.controller, self.hotkeys)
        self.setup.theme_changed.connect(self.apply_theme)
        self.setup.hotkeys_changed.connect(self.refresh)
        lay.addWidget(self.setup, 1)
        return page

    def _finger_page(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(page_header("Fingerabdruck", "Sensor wählen, Finger anlernen und damit anmelden."))
        lay.addWidget(FingerprintPage(self.controller), 1)
        return page

    def open_first_run(self):
        from .first_run import FirstRunDialog

        dlg = FirstRunDialog(self.controller, self)
        dlg.setAttribute(Qt.WA_DeleteOnClose)
        dlg.open()
        return dlg

    def open_handy_window(self):
        """Handy einrichten (Status, automatische Einrichtung, Hilfe) – als eigenes Fenster statt eigener Seite."""
        from PySide6.QtWidgets import QDialog

        from .handy_page import HandyPage

        if getattr(self, "handy_window", None) is None:
            dlg = QDialog(self)
            dlg.setWindowTitle("Handy auf Monitor 2")
            dlg.resize(1060, 820)
            lay = QVBoxLayout(dlg)
            lay.setContentsMargins(22, 18, 22, 18)
            lay.addWidget(page_header("Handy auf Monitor 2", "Vier Wege – die Einrichtung läuft automatisch."))
            self.handy_page = HandyPage(self.controller)
            lay.addWidget(self.handy_page, 1)
            self.handy_window = dlg
        self.handy_window.show()
        self.handy_window.raise_()
        self.handy_window.activateWindow()

    def _settings_imported(self, keys: list):
        """Einstellungen geladen (Import oder vom anderen System) → Oberfläche auffrischen."""
        if not keys:
            return
        if "start_page" in keys:
            self.rebuild_start()
        if "scenes" in keys:
            self._reload_scenes()
        if "hotkeys" in keys:
            self._apply_hotkeys()
        if "appearance" in keys:
            self.apply_theme()
        self.refresh()

    def apply_theme(self):
        a = self.config["appearance"]
        theme.apply(QApplication.instance(), a.get("mode", "system"), a.get("accent", "blau"))
        # Symbole in Knöpfen neu einfärben
        for b in self.findChildren(QPushButton):
            name = b.property("iconName")
            if name:
                t = theme.current()
                color = "#ffffff" if b.property("primary") else (t.danger if b.property("danger") else t.text)
                b.setIcon(icons.icon(name, color, 18))
        self.media_bar.apply_theme()
        self.camera_bar.apply_theme()
        self.refresh()
        for w in self.findChildren(QWidget):
            w.update()

    # ================================================================ Tray
    def _build_tray(self):
        """Symbol in der Taskleiste: Klick öffnet ein Schnellmenü, das Symbol zeigt den Zustand."""
        self.tray = QSystemTrayIcon(app_icon(), self)
        self.tray.setToolTip(APP_NAME)
        c = self.controller
        t = theme.current()
        ic = lambda name: icons.icon(name, t.text, 18)  # noqa: E731
        menu = QMenu()
        self.a_status = menu.addAction("")
        self.a_status.setEnabled(False)
        menu.addSeparator()
        self.a_freeze = QAction(ic("snowflake"), "Standbild", menu, checkable=True)
        self.a_freeze.triggered.connect(lambda _=False: c.toggle_freeze())
        self.a_black = QAction(ic("eye_off"), "Schwarz (Sichtschutz)", menu, checkable=True)
        self.a_black.triggered.connect(lambda _=False: c.toggle_privacy())
        self.a_saver = QAction(ic("moon"), "Bildschirmschoner", menu, checkable=True)
        self.a_saver.triggered.connect(lambda _=False: c.toggle_screensaver())
        self.a_pip = QAction(ic("pip"), "Bild-in-Bild", menu, checkable=True)
        self.a_pip.triggered.connect(lambda _=False: c.toggle_pip())
        self.a_draw = QAction(ic("edit"), "Zeigen & Zeichnen …", menu)
        self.a_draw.triggered.connect(self.open_presenter)
        for act in (self.a_freeze, self.a_black, self.a_saver, self.a_pip, self.a_draw):
            menu.addAction(act)
        self.tray_timer = menu.addMenu(ic("timer"), "Timer")
        self._fill_timer_menu(self.tray_timer)
        self.tray_volume = menu.addMenu(ic("sound"), "Ton auf Monitor 2")
        self.a_mute = QAction(ic("mute"), "Ton aus", menu, checkable=True)
        self.a_mute.triggered.connect(lambda on: c.set_media_volume(muted=on))
        self.tray_volume.addAction(self.a_mute)
        self.tray_volume.addSeparator()
        self.a_levels = []
        for level in (100, 75, 50, 25, 10):
            act = QAction(f"{level} %", menu, checkable=True)
            act.triggered.connect(lambda _=False, v=level: c.set_media_volume(volume=v, muted=False))
            self.tray_volume.addAction(act)
            self.a_levels.append((level, act))
        menu.addSeparator()
        menu.addAction(ic("mirror"), "Spiegeln", c.mirror)
        menu.addAction(ic("extend"), "Erweitern", c.extend)
        menu.addAction(ic("qr"), "Handy (QR-Code)", c.start_cast)
        self.tray_scenes = menu.addMenu(ic("scenes"), "Szenen")
        menu.addAction(ic("down"), "Nächste Szene", lambda: c.step_scene(1))
        menu.addSeparator()
        menu.addAction(ic("home"), "AluPC öffnen", self.show_normal_front)
        menu.addAction(ic("lock"), "Computer sperren", self.lock)
        menu.addAction(ic("power"), "Beenden", QApplication.instance().quit)
        self.tray_menu = menu
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._tray_activated)
        self._fill_tray_scenes()
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.show()
            if sys.platform.startswith("win"):
                # Windows 11 legt das Symbol erst später in seine Liste → dann direkt sichtbar schalten
                QTimer.singleShot(4000, self._promote_tray)
                QTimer.singleShot(20000, self._promote_tray)

    def _promote_tray(self):
        """Einmal pro Programmpfad: AluPC-Symbol direkt in der Taskleiste statt hinter dem Pfeil."""
        import os

        from ..platform.windows_tray import promote

        exe = os.path.realpath(sys.executable)
        done = self.config["tray"].get("promoted_for", "")
        if done == exe or not getattr(sys, "frozen", False):
            return
        try:
            if promote(exe):
                self.config["tray"] = {**self.config["tray"], "promoted_for": exe}
                # neu anmelden, damit Explorer die Einstellung sofort übernimmt
                self.tray.hide()
                self.tray.show()
        except Exception:  # noqa: BLE001
            pass

    def _fill_timer_menu(self, menu):
        c = self.controller
        menu.clear()
        menu.addAction("Auf Monitor 2 zeigen", c.show_timer)
        menu.addAction("Start / Pause", lambda: c.timer_action("toggle"))
        menu.addAction("Neu starten", lambda: c.timer_action("restart"))
        menu.addAction("+1 Minute", lambda: c.timer_action("plus"))
        menu.addAction("−1 Minute", lambda: c.timer_action("minus"))
        menu.addSeparator()
        menu.addAction("Timer einstellen …", self.edit_timer)

    def edit_timer(self):
        from .timer_dialog import TimerDialog

        self.show_normal_front()
        TimerDialog(self.controller, self).exec()

    def edit_screensaver(self):
        from .screensaver_settings import ScreensaverDialog

        ScreensaverDialog(self.controller, self).exec()

    def _tray_icon(self):
        """Programmsymbol mit kleinem Zustands-Punkt (Standbild, Schwarz, Bildschirmschoner)."""

        c = self.controller
        state = ("eye_off", PRIVACY_COLOR) if c.privacy else ("snowflake", FREEZE_COLOR) if c.frozen \
            else ("moon", "#6366f1") if c.screensaver.active else None
        key = state[0] if state else ""
        if getattr(self, "_tray_key", None) == key:
            return None
        self._tray_key = key
        if state is None:
            return app_icon()
        return icons.app_icon_with_badge(state[0], state[1])

    def _fill_tray_scenes(self):
        if hasattr(self, "tray_scenes"):
            self._fill_scene_menu(self.tray_scenes)

    def _tray_activated(self, reason):
        # Einfacher Klick: Schnellmenü zum Steuern · Doppelklick: Fenster öffnen
        if reason == QSystemTrayIcon.DoubleClick:
            self.tray_menu.hide()
            self.show_normal_front()
        elif reason == QSystemTrayIcon.Trigger:
            from PySide6.QtGui import QCursor

            self.tray_menu.popup(QCursor.pos())

    def show_normal_front(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    # ================================================================ Status
    def _sync_tray_volume(self):
        if not hasattr(self, "tray_volume"):
            return
        state = self.controller.media_state()
        self.tray_volume.menuAction().setVisible(state is not None)
        if state is None:
            return
        self.a_mute.setChecked(state["muted"])
        for level, act in self.a_levels:
            act.setChecked(not state["muted"] and state["volume"] == level)

    def _update_preview(self):
        from PySide6.QtCore import QSize

        from ..output_window import grab_scaled

        c = self.controller
        card = self.status_card
        if not self.isVisible() or self.isMinimized() or self.stack.currentIndex() != 0:
            return
        out = c.output
        image = None
        if out.isVisible() and (c.mode == "content" or c.privacy or c.frozen or c.screensaver.active):
            dpr = card.preview.devicePixelRatioF()
            pw, ph = card.preview.width(), card.preview.height()
            image = grab_scaled(out, QSize(int(pw * dpr), int(ph * dpr)))
            from ..laser import draw_overlay

            draw_overlay(c, image)
        card.preview.set(image, card.preview.icon_name)

    def refresh(self):
        c = self.controller
        t = theme.current()
        out = c.output_screen()
        pip_on = bool(c.pip and c.pip.isVisible())
        if out is not None:
            size = out.size()
            where = f"Monitor 2 · {out.name()} · {size.width()} × {size.height()}"
            hz = out.refreshRate()
            if hz:
                where += f" · {hz:.0f} Hz"
        else:
            where = "Monitor 2 · nicht angeschlossen"
        typ = c.content.get("type") if c.mode == "content" and c.content else None
        is_mirror = bool(c.content and c.content.get("mirror"))
        icon_name = "mirror" if is_mirror else icons.SOURCE_ICONS.get(typ, "extend" if c.mode == "desktop" else "monitor")
        if c.mode == "desktop" and c.desktop_note.startswith("Programm"):
            icon_name = "window"
        elif c.mode == "desktop" and c.desktop_note.startswith(HANDY_NOTES):
            icon_name = "phone"
        pills = []
        if out is None:
            pills.append(("KEIN MONITOR", t.danger))
        elif c.privacy:
            pills.append(("SCHWARZ", PRIVACY_COLOR))
        elif c.screensaver.active:
            pills.append(("BILDSCHIRMSCHONER", "#6366f1"))
        elif c.frozen:
            pills.append(("STANDBILD", FREEZE_COLOR))
        else:
            pills.append(("LIVE", t.success))
        if pip_on:
            pills.append(("BILD-IN-BILD", PIP_COLOR))
        if c.laser.strokes:
            pills.append(("ZEICHNUNG", "#f97316"))
        self.status_card.set(icon_name, where, c.describe(), pills)
        self.stop_btn.setVisible(c.mode == "content")
        QTimer.singleShot(150, self._update_preview)  # Vorschau gleich nach dem Wechsel auffrischen
        self.volume_box.sync()
        self.media_bar.sync()
        self.camera_bar.sync()
        self._sync_tray_volume()
        dot = theme.current().success if out else theme.current().danger
        self.side_monitor.setText(f'<span style="color:{dot}">●</span> ' + (
            f"Monitor 2: <b>{out.name()}</b><br>&nbsp;&nbsp;&nbsp;&nbsp;{out.size().width()} × {out.size().height()}" if out
            else "Kein Monitor 2 angeschlossen"))

        self.t_mirror.set_state(is_mirror, badge="AKTIV" if is_mirror else "")
        handy_desktop = c.mode == "desktop" and c.desktop_note.startswith(HANDY_NOTES)
        desktop = c.mode == "desktop" and not c.desktop_note.startswith("Programm") and not handy_desktop
        self.t_extend.set_state(desktop, badge="AKTIV" if desktop else "")
        for tile, on in [
            (self.t_camera, typ == "camera"),
            (self.t_program, typ == "window" or (c.mode == "desktop" and c.desktop_note.startswith("Programm"))),
            (self.t_web, typ == "website"),
            (self.t_media, typ in ("image", "video", "slideshow")),
            (self.t_scenes, typ == "scene"),
            (self.t_airplay, typ == "airplay" or (c.mode == "desktop" and c.desktop_note.startswith("iPhone"))),
        ]:
            tile.set_state(on, badge="AKTIV" if on else "")
        remote_on = c.cast.running()  # Handy-Steuerung: „LÄUFT“, solange Handys verbinden können
        self.t_remote.set_state(remote_on or typ == "cast", badge="LÄUFT" if remote_on else "")
        saver_on = c.screensaver.active
        self.t_saver.set_state(saver_on, badge="AN" if saver_on else "")
        drawing = bool(getattr(self, "presenter", None) and self.presenter.isVisible())
        self.t_draw.set_state(drawing, badge="OFFEN" if drawing else "")
        for key, tile in self.custom_tiles.items():
            tcfg = find_custom(self.config["start_page"], key) or {}
            action = tcfg.get("action") or {}
            on = (action.get("kind") == "source" and c.mode == "content" and c.content == action.get("source")) \
                or (action.get("kind") == "screensaver" and c.screensaver.active
                    and c.screensaver.override_id == tcfg.get("id"))
            tile.set_state(on, badge="AKTIV" if on else "")
        self.t_freeze.set_state(c.frozen, badge="AN" if c.frozen else "")
        self.t_black.set_state(c.privacy, badge="AN" if c.privacy else "")
        self.t_pip.set_state(pip_on, badge="AN" if pip_on else "")
        drawing_now = bool(getattr(self, "presenter", None) and self.presenter.isVisible())
        for key, on in (("black", c.privacy), ("freeze", c.frozen), ("pip", pip_on), ("draw", drawing_now)):
            chip = self.chips[key]
            if chip.isChecked() != bool(on):
                chip.setChecked(bool(on))
            color = "#ffffff" if on else theme.current().text
            chip.setIcon(icons.icon(chip.property("iconName"), color, 16))
        self.a_freeze.setChecked(c.frozen)
        self.a_black.setChecked(c.privacy)
        self.a_pip.setChecked(pip_on)
        self.a_saver.setChecked(c.screensaver.active)
        self.a_status.setText(f"Monitor 2: {c.describe()}"[:70])
        self.tray.setToolTip(f"{APP_NAME} – Monitor 2: {c.describe()}")
        icon = self._tray_icon()
        if icon is not None:
            self.tray.setIcon(icon)
        hk = self.config["hotkeys"]
        parts = [(hk.get(k), label) for k, label in (("standbild", "Standbild"), ("schwarz", "Schwarz"),
                                                        ("bild_in_bild", "Bild-in-Bild"),
                                                        ("bildschirmschoner", "Bildschirmschoner"),
                                                        ("naechste_szene", "Nächste Szene"))]
        self.shortcut_hint.setText("Tastenkürzel: " + " · ".join(
            f"{seq} {label}" for seq, label in parts if seq).replace("Ctrl", "Strg").replace("PgDown", "Bild↓"))
        self._mark_live_scene()

    def show_message(self, text, kind: str = ""):
        if not kind:
            low = text.lower()
            kind = "warn" if any(w in low for w in ("nicht", "fehl", "kein", "gesperrt", "unbekannt")) else "info"
        self.toast.show_text(text, kind)
        if not self.isVisible() and self.tray.isVisible():
            self.tray.showMessage(APP_NAME, text, QSystemTrayIcon.Information, 4000)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if hasattr(self, "toast") and self.toast.isVisible():
            self.toast.reposition()

    # ================================================================ Sperre
    def lock(self):
        """Computer sperren – wie Win+L (Linux: Bildschirmsperre)."""
        self.controller.lock_computer()

    def closeEvent(self, event):
        # Schließen = nur ausblenden; Monitor 2 läuft weiter. Beenden über das Tray-Menü.
        if self.tray.isVisible():
            event.ignore()
            self.hide()
            if not self.config.data.get("tray_hint_shown"):
                self.tray.showMessage(APP_NAME, "AluPC läuft im Hintergrund weiter (Symbol in der Taskleiste).",
                                      QSystemTrayIcon.Information, 4000)
                self.config["tray_hint_shown"] = True
        else:
            event.accept()
            QApplication.instance().quit()

