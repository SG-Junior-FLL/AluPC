"""Hauptfenster: Seitenleiste, Statuskarte und große Kacheln – ein Klick, fertig."""

from __future__ import annotations

import copy

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtMultimedia import QMediaDevices
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
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
from ..scenes import describe_source
from ..sources import camera_id, normalize_url
from . import icons, theme
from .fingerprint_page import FingerprintPage
from .icons import app_icon
from .lock_dialog import LockDialog
from .program_dialog import ProgramDialog
from .scene_editor import SceneEditor
from .setup_page import SetupPage
from .source_picker import IMAGE_FILTER, VIDEO_FILTER
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
    def __init__(self, recent: list[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Website anzeigen")
        self.setMinimumWidth(520)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 20, 22, 18)
        lay.setSpacing(14)
        lay.addWidget(page_header("Website anzeigen", "Die Seite erscheint im Vollbild auf Monitor 2."))
        self.combo = QComboBox()
        self.combo.setEditable(True)
        self.combo.addItems(recent)
        self.combo.setCurrentText(recent[0] if recent else "")
        self.combo.lineEdit().setPlaceholderText("z. B. www.beispiel.de")
        self.combo.setMinimumHeight(38)
        form = QFormLayout()
        form.addRow("Adresse:", self.combo)
        lay.addLayout(form)
        buttons = QDialogButtonBox()
        ok = button("Anzeigen", "play", primary=True)
        cancel = button("Abbrechen")
        buttons.addButton(ok, QDialogButtonBox.AcceptRole)
        buttons.addButton(cancel, QDialogButtonBox.RejectRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)

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

        self.pages = [
            _padded(self._start_page(), scroll=True),
            _padded(self._scenes_page()),
            _padded(self._setup_page()),
            _padded(self._finger_page(), scroll=True),
        ]
        for page in self.pages:
            self.stack.addWidget(page)
        self.nav_group.buttons()[0].setChecked(True)

        self.toast = Toast(self)
        self._build_tray()
        controller.changed.connect(self.refresh)
        controller.message.connect(self.show_message)
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
        for i, (icon_name, text) in enumerate([("home", "Start"), ("scenes", "Szenen"),
                                               ("sliders", "Setup"), ("fingerprint", "Fingerabdruck")]):
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
        lock = NavButton("lock", "Sperren")
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
        self.stack.setCurrentIndex(index)
        self.nav_group.button(index).setChecked(True)

    # ================================================================ Start
    def _start_page(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(16)
        lay.addWidget(page_header("Was sollen die anderen sehen?",
                                  "Ein Klick auf eine Kachel – und Monitor 2 zeigt es sofort."))
        self.status_card = StatusCard()
        lay.addWidget(self.status_card)

        c = self.controller
        self.t_mirror = Tile("mirror", "Spiegeln", "Zeigt dasselbe wie Monitor 1")
        self.t_extend = Tile("extend", "Erweitern", "Normaler zweiter Bildschirm")
        self.t_camera = Tile("camera", "Kamera", "Kamera im Vollbild")
        self.t_program = Tile("window", "Programm", "Ein Programm zeigen")
        self.t_web = Tile("globe", "Website", "Website im Vollbild")
        self.t_media = Tile("image", "Bild / Video", "Bild, Video oder Diashow")
        self.t_scenes = Tile("scenes", "Meine Szenen", "Eigene Zusammenstellungen")
        self.t_freeze = Tile("snowflake", "Standbild", "Bild einfrieren", FREEZE_COLOR)
        self.t_black = Tile("eye_off", "Schwarz", "Sichtschutz", PRIVACY_COLOR)
        self.t_pip = Tile("pip", "Bild-in-Bild", "Monitor 2 klein anzeigen", PIP_COLOR)

        self.t_mirror.clicked.connect(c.mirror)
        self.t_extend.clicked.connect(c.extend)
        self.t_camera.clicked.connect(self._camera_clicked)
        self.t_program.clicked.connect(lambda: ProgramDialog(c, self).exec())
        self.t_web.clicked.connect(self.pick_website)
        self.t_black.clicked.connect(c.toggle_privacy)
        self.t_freeze.clicked.connect(c.toggle_freeze)
        self.t_pip.clicked.connect(c.toggle_pip)
        self.camera_menu = QMenu(self)
        media_menu = QMenu(self)
        media_menu.addAction(icons.icon("image", theme.current().text, 18), "Bild …", self.pick_image)
        media_menu.addAction(icons.icon("video", theme.current().text, 18), "Video …", self.pick_video)
        media_menu.addAction(icons.icon("slides", theme.current().text, 18), "Diashow aus Ordner …",
                             self.pick_slideshow)
        self.t_media.set_menu(media_menu)
        self.scene_menu = QMenu(self)
        self.scene_menu.aboutToShow.connect(lambda: self._fill_scene_menu(self.scene_menu))
        self.t_scenes.set_menu(self.scene_menu)

        section = QLabel("Anzeigen")
        section.setObjectName("SectionTitle")
        lay.addWidget(section)
        grid = FlowGrid(min_width=170, max_cols=4)
        grid.set_items([self.t_mirror, self.t_extend, self.t_camera, self.t_program,
                        self.t_web, self.t_media, self.t_scenes])
        lay.addWidget(grid)

        section2 = QLabel("Schnell umschalten")
        section2.setObjectName("SectionTitle")
        lay.addWidget(section2)
        quick = FlowGrid(min_width=170, max_cols=3)
        quick.set_items([self.t_freeze, self.t_black, self.t_pip])
        lay.addWidget(quick)
        hint = QLabel("Tipp: Strg+Alt+S = Standbild · Strg+Alt+B = Schwarz · Strg+Alt+P = Bild-in-Bild")
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        self.shortcut_hint = hint
        lay.addWidget(hint)
        lay.addStretch(1)
        return page

    def _camera_clicked(self):
        devices = QMediaDevices.videoInputs()
        configs = [{"type": "camera", "device_id": camera_id(d), "name": d.description(), "fit": "cover"}
                   for d in devices]
        if len(configs) == 1:  # nur eine Kamera → sofort zeigen
            self.controller.show_source(configs[0])
            return
        self.camera_menu.clear()
        if not configs:
            act = self.camera_menu.addAction("Keine Kamera gefunden")
            act.setEnabled(False)
        for cfg in configs:
            self.camera_menu.addAction(icons.icon("camera", theme.current().text, 18), cfg["name"],
                                       lambda c=cfg: self.controller.show_source(c))
        self.camera_menu.popup(self.t_camera.mapToGlobal(self.t_camera.rect().bottomLeft()))

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

    def pick_website(self):
        recent = list(self.config.data.get("recent_urls", []))
        dlg = WebsiteDialog(recent, self)
        if dlg.exec() != QDialog.Accepted or not dlg.url():
            return
        url = dlg.url()
        self.config["recent_urls"] = [url] + [u for u in recent if u != url][:9]
        self.controller.show_source({"type": "website", "url": url})

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
        lay.addWidget(page_header("Setup", "Monitore, Darstellung, Tastenkürzel und Sperre."))
        self.setup = SetupPage(self.controller, self.hotkeys)
        self.setup.theme_changed.connect(self.apply_theme)
        lay.addWidget(self.setup, 1)
        return page

    def _finger_page(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(page_header("Fingerabdruck", "Sensor wählen, Finger anlernen und damit anmelden."))
        lay.addWidget(FingerprintPage(self.controller), 1)
        return page

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
        self.refresh()
        for w in self.findChildren(QWidget):
            w.update()

    # ================================================================ Tray
    def _build_tray(self):
        self.tray = QSystemTrayIcon(app_icon(), self)
        self.tray.setToolTip(APP_NAME)
        menu = QMenu()
        menu.addAction("AluPC öffnen", self.show_normal_front)
        menu.addSeparator()
        c = self.controller
        self.a_freeze = QAction("Standbild", menu, checkable=True)
        self.a_freeze.triggered.connect(lambda _=False: c.toggle_freeze())
        self.a_black = QAction("Schwarz (Sichtschutz)", menu, checkable=True)
        self.a_black.triggered.connect(lambda _=False: c.toggle_privacy())
        self.a_pip = QAction("Bild-in-Bild", menu, checkable=True)
        self.a_pip.triggered.connect(lambda _=False: c.toggle_pip())
        menu.addAction(self.a_freeze)
        menu.addAction(self.a_black)
        menu.addAction(self.a_pip)
        menu.addSeparator()
        menu.addAction("Spiegeln", c.mirror)
        menu.addAction("Erweitern", c.extend)
        self.tray_scenes = menu.addMenu("Szenen")
        menu.addSeparator()
        menu.addAction("Sperren", self.lock)
        menu.addAction("Beenden", QApplication.instance().quit)
        self.tray_menu = menu
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._tray_activated)
        self._fill_tray_scenes()
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.show()

    def _fill_tray_scenes(self):
        if hasattr(self, "tray_scenes"):
            self._fill_scene_menu(self.tray_scenes)

    def _tray_activated(self, reason):
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            if self.isVisible() and not self.isMinimized():
                self.hide()
            else:
                self.show_normal_front()

    def show_normal_front(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    # ================================================================ Status
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
        pills = []
        if out is None:
            pills.append(("KEIN MONITOR", t.danger))
        elif c.privacy:
            pills.append(("SCHWARZ", PRIVACY_COLOR))
        elif c.frozen:
            pills.append(("STANDBILD", FREEZE_COLOR))
        else:
            pills.append(("LIVE", t.success))
        if pip_on:
            pills.append(("BILD-IN-BILD", PIP_COLOR))
        self.status_card.set(icon_name, where, c.describe(), pills)
        self.side_monitor.setText(("● " if out else "○ ") + (out.name() if out else "Kein Monitor 2"))

        self.t_mirror.set_state(is_mirror, badge="AKTIV" if is_mirror else "")
        desktop = c.mode == "desktop" and not c.desktop_note.startswith("Programm")
        self.t_extend.set_state(desktop, badge="AKTIV" if desktop else "")
        for tile, on in [
            (self.t_camera, typ == "camera"),
            (self.t_program, typ == "window" or (c.mode == "desktop" and c.desktop_note.startswith("Programm"))),
            (self.t_web, typ == "website"),
            (self.t_media, typ in ("image", "video", "slideshow")),
            (self.t_scenes, typ == "scene"),
        ]:
            tile.set_state(on, badge="AKTIV" if on else "")
        self.t_freeze.set_state(c.frozen, badge="AN" if c.frozen else "")
        self.t_black.set_state(c.privacy, badge="AN" if c.privacy else "")
        self.t_pip.set_state(pip_on, badge="AN" if pip_on else "")
        self.a_freeze.setChecked(c.frozen)
        self.a_black.setChecked(c.privacy)
        self.a_pip.setChecked(pip_on)
        hk = self.config["hotkeys"]
        self.shortcut_hint.setText(
            f"Tastenkürzel: {hk.get('standbild') or '–'} Standbild · {hk.get('schwarz') or '–'} Schwarz · "
            f"{hk.get('bild_in_bild') or '–'} Bild-in-Bild".replace("Ctrl", "Strg"))
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
        if not self.config["lock"].get("enabled"):
            self.show_message("Die Sperre ist aus – einschalten unter Setup → „AluPC sperren“.", "warn")
            return
        self.controller.locked = True
        self.hide()
        dlg = LockDialog(self.controller)
        dlg.setWindowIcon(app_icon())
        dlg.exec()
        self.controller.locked = False
        self.show_normal_front()

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

