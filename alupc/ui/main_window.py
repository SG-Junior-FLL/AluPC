"""Hauptfenster: große Kacheln – ein Klick, fertig."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QAction, QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtMultimedia import QMediaDevices
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSystemTrayIcon,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .. import APP_NAME
from ..scenes import describe_source
from ..sources import camera_id, normalize_url
from .fingerprint_page import FingerprintPage
from .lock_dialog import LockDialog
from .program_dialog import ProgramDialog
from .scene_editor import SceneEditor
from .setup_page import SetupPage
from .source_picker import IMAGE_FILTER, VIDEO_FILTER

TILE_STYLE = """
QToolButton#tile {
    font-size: 15px; font-weight: 600; padding: 10px;
    border: 2px solid palette(mid); border-radius: 12px; background: palette(button);
}
QToolButton#tile:hover { border-color: palette(highlight); }
QToolButton#tile[active="true"] { border-color: #1d6fb8; background: rgba(29,111,184,0.18); }
QToolButton#tile[alert="true"] { border-color: #c0392b; background: rgba(192,57,43,0.18); }
"""


def app_icon() -> QIcon:
    """Symbol: zwei Monitore (wird ohne Bilddatei gezeichnet)."""
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        pix = QPixmap(size, size)
        pix.fill(Qt.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.Antialiasing)
        s = size / 64
        p.setBrush(QColor("#1d6fb8"))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(2 * s, 10 * s, 36 * s, 26 * s, 4 * s, 4 * s)
        p.setBrush(QColor("#e0913b"))
        p.drawRoundedRect(26 * s, 24 * s, 36 * s, 26 * s, 4 * s, 4 * s)
        p.setBrush(QColor("#555555"))
        p.drawRect(40 * s, 50 * s, 8 * s, 6 * s)
        p.drawRoundedRect(34 * s, 55 * s, 20 * s, 4 * s, 2 * s, 2 * s)
        p.end()
        icon.addPixmap(pix)
    return icon


def symbol_icon(symbol: str, size: int = 88) -> QIcon:
    """Emoji/Zeichen als großes Symbol (Kubuntu: Noto Color Emoji, Windows: Segoe UI Emoji)."""
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    font = QFont()
    font.setFamilies(["Noto Color Emoji", "Segoe UI Emoji", "Apple Color Emoji", font.family()])
    font.setPixelSize(int(size * 0.72))
    p.setFont(font)
    p.drawText(pix.rect(), Qt.AlignCenter, symbol)
    p.end()
    return QIcon(pix)


class Tile(QToolButton):
    def __init__(self, symbol: str, text: str, tooltip: str = ""):
        super().__init__()
        self.setObjectName("tile")
        self.setText(text)
        self.setIcon(symbol_icon(symbol))
        self.setIconSize(QSize(44, 44))
        self.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self.setToolTip(tooltip)
        self.setMinimumSize(QSize(150, 96))
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setPopupMode(QToolButton.InstantPopup)

    def set_state(self, active: bool = False, alert: bool = False):
        self.setProperty("active", active)
        self.setProperty("alert", alert)
        self.style().unpolish(self)
        self.style().polish(self)


class WebsiteDialog(QDialog):
    def __init__(self, recent: list[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Website anzeigen")
        self.setMinimumWidth(480)
        self.combo = QComboBox()
        self.combo.setEditable(True)
        self.combo.addItems(recent)
        self.combo.setCurrentText(recent[0] if recent else "")
        self.combo.lineEdit().setPlaceholderText("z. B. www.beispiel.de")
        form = QFormLayout()
        form.addRow("Adresse:", self.combo)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Anzeigen")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(buttons)

    def url(self) -> str:
        return normalize_url(self.combo.currentText())


class MainWindow(QMainWindow):
    def __init__(self, controller, hotkeys):
        super().__init__()
        self.controller = controller
        self.config = controller.config
        self.hotkeys = hotkeys
        self.setWindowTitle(f"{APP_NAME} – Monitor 2 steuern")
        self.setWindowIcon(app_icon())
        self.resize(900, 640)
        self.setStyleSheet(TILE_STYLE)

        central = QWidget()
        lay = QVBoxLayout(central)
        self.status_label = QLabel()
        font = QFont()
        font.setPointSize(font.pointSize() + 2)
        self.status_label.setFont(font)
        self.status_label.setWordWrap(True)
        lay.addWidget(self.status_label)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._start_tab(), "Start")
        self.tabs.addTab(self._scenes_tab(), "Szenen")
        self.tabs.addTab(SetupPage(controller, hotkeys), "Setup")
        self.tabs.addTab(FingerprintPage(controller), "Fingerabdruck")
        lay.addWidget(self.tabs, 1)
        self.setCentralWidget(central)

        self._build_tray()
        controller.changed.connect(self.refresh)
        controller.message.connect(self.show_message)
        self.refresh()

    # ================================================================ Start
    def _start_tab(self):
        page = QWidget()
        grid = QGridLayout(page)
        grid.setSpacing(12)
        self.t_mirror = Tile("🪞", "Spiegeln", "Monitor 2 zeigt dasselbe wie Monitor 1")
        self.t_extend = Tile("🖥️", "Erweitern", "Monitor 2 ist ein normaler zweiter Bildschirm")
        self.t_camera = Tile("📷", "Kamera", "Eine Kamera auf Monitor 2 zeigen")
        self.t_program = Tile("🗔", "Programm", "Ein Programm auf Monitor 2 zeigen")
        self.t_web = Tile("🌐", "Website", "Eine Website im Vollbild auf Monitor 2")
        self.t_media = Tile("🖼️", "Bild / Video", "Bild, Video oder Diashow zeigen")
        self.t_scenes = Tile("🎬", "Meine Szenen", "Eine eigene Szene zeigen")
        self.t_black = Tile("⬛", "Schwarz", "Sichtschutz an/aus")
        self.t_freeze = Tile("❄️", "Standbild", "Bild auf Monitor 2 einfrieren / weiterlaufen lassen")
        self.t_pip = Tile("🔲", "Bild-in-Bild", "Monitor 2 klein auf Monitor 1 anzeigen")

        c = self.controller
        self.t_mirror.clicked.connect(c.mirror)
        self.t_extend.clicked.connect(c.extend)
        self.t_program.clicked.connect(lambda: ProgramDialog(c, self).exec())
        self.t_web.clicked.connect(self.pick_website)
        self.t_black.clicked.connect(c.toggle_privacy)
        self.t_freeze.clicked.connect(c.toggle_freeze)
        self.t_pip.clicked.connect(c.toggle_pip)

        self.camera_menu = QMenu(self)
        self.t_camera.clicked.connect(self._camera_clicked)
        media_menu = QMenu(self)
        media_menu.addAction("Bild …", self.pick_image)
        media_menu.addAction("Video …", self.pick_video)
        media_menu.addAction("Diashow aus Ordner …", self.pick_slideshow)
        self.t_media.setMenu(media_menu)
        self.scene_menu = QMenu(self)
        self.scene_menu.aboutToShow.connect(lambda: self._fill_scene_menu(self.scene_menu))
        self.t_scenes.setMenu(self.scene_menu)

        tiles = [self.t_mirror, self.t_extend, self.t_camera, self.t_program, self.t_web,
                 self.t_media, self.t_scenes, self.t_black, self.t_freeze, self.t_pip]
        for i, tile in enumerate(tiles):
            grid.addWidget(tile, i // 5, i % 5)
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
            self.camera_menu.addAction(cfg["name"], lambda c=cfg: self.controller.show_source(c))
        self.camera_menu.popup(self.t_camera.mapToGlobal(self.t_camera.rect().bottomLeft()))

    def _fill_scene_menu(self, menu):
        menu.clear()
        names = self.config.scene_names()
        if not names:
            act = menu.addAction("Noch keine Szene – im Tab „Szenen“ anlegen")
            act.setEnabled(False)
        for name in names:
            menu.addAction(name, lambda n=name: self.controller.show_source({"type": "scene", "scene": n}))
        menu.addSeparator()
        menu.addAction("Neue Szene …", self.new_scene)

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
    def _scenes_tab(self):
        page = QWidget()
        lay = QHBoxLayout(page)
        self.scene_list = QListWidget()
        self.scene_list.itemDoubleClicked.connect(lambda _i: self.show_scene())
        self.scene_detail = QLabel()
        self.scene_detail.setWordWrap(True)
        self.scene_detail.setAlignment(Qt.AlignTop)
        self.scene_list.currentTextChanged.connect(self._scene_selected)
        left = QVBoxLayout()
        left.addWidget(QLabel("Deine Szenen (nur selbst erstellte):"))
        left.addWidget(self.scene_list, 1)
        left.addWidget(self.scene_detail)
        buttons = QVBoxLayout()
        for text, slot in [("▶ Anzeigen", self.show_scene), ("Neu …", self.new_scene),
                           ("Bearbeiten …", self.edit_scene), ("Duplizieren", self.duplicate_scene),
                           ("Löschen", self.delete_scene)]:
            b = QPushButton(text)
            b.clicked.connect(slot)
            buttons.addWidget(b)
        buttons.addStretch(1)
        lay.addLayout(left, 1)
        lay.addLayout(buttons)
        self._reload_scenes()
        return page

    def _reload_scenes(self, select: str | None = None):
        current = select or (self.scene_list.currentItem().text() if self.scene_list.currentItem() else None)
        self.scene_list.clear()
        self.scene_list.addItems(self.config.scene_names())
        items = self.scene_list.findItems(current or "", Qt.MatchExactly)
        if items:
            self.scene_list.setCurrentItem(items[0])
        elif self.scene_list.count():
            self.scene_list.setCurrentRow(0)
        self._scene_selected(self.scene_list.currentItem().text() if self.scene_list.currentItem() else "")
        self._fill_tray_scenes()

    def _scene_selected(self, name):
        scene = self.config.get_scene(name) if name else None
        if not scene:
            self.scene_detail.setText("Lege mit „Neu …“ deine erste Szene an.")
            return
        from ..scenes import LAYOUTS, layout_slots

        lines = [f"<b>{name}</b> – {LAYOUTS.get(scene['layout'], ('?',))[0]}"]
        for (_x, _y, _w, _h, slot_name), slot in zip(layout_slots(scene["layout"]), scene["slots"]):
            lines.append(f"{slot_name}: {describe_source(slot)}")
        self.scene_detail.setText("<br>".join(lines))

    def _selected_scene(self):
        item = self.scene_list.currentItem()
        return self.config.get_scene(item.text()) if item else None

    def show_scene(self):
        scene = self._selected_scene()
        if scene:
            self.controller.show_source({"type": "scene", "scene": scene["name"]})

    def new_scene(self):
        dlg = SceneEditor(self.config, None, self)
        if dlg.exec() == QDialog.Accepted:
            self._reload_scenes(dlg.scene["name"])

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
        import copy

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
        out = c.output_screen()
        where = out.name() if out else "nicht angeschlossen"
        badges = []
        if c.frozen:
            badges.append("<span style='color:#c0392b'><b>STANDBILD</b></span>")
        if c.privacy:
            badges.append("<b>SCHWARZ</b>")
        if c.pip and c.pip.isVisible():
            badges.append("Bild-in-Bild an")
        extra = ("  ·  " + "  ·  ".join(badges)) if badges else ""
        self.status_label.setText(f"Monitor 2 ({where}): <b>{c.describe()}</b>{extra}")
        t = c.content.get("type") if c.mode == "content" and c.content else None
        self.t_mirror.set_state(bool(c.content and c.content.get("mirror")))
        self.t_extend.set_state(c.mode == "desktop")
        self.t_camera.set_state(t == "camera")
        self.t_program.set_state(t == "window" or c.desktop_note.startswith("Programm") and c.mode == "desktop")
        self.t_web.set_state(t == "website")
        self.t_media.set_state(t in ("image", "video", "slideshow"))
        self.t_scenes.set_state(t == "scene")
        self.t_black.set_state(alert=c.privacy)
        self.t_freeze.set_state(alert=c.frozen)
        self.t_pip.set_state(bool(c.pip and c.pip.isVisible()))
        self.a_freeze.setChecked(c.frozen)
        self.a_black.setChecked(c.privacy)
        self.a_pip.setChecked(bool(c.pip and c.pip.isVisible()))

    def show_message(self, text):
        self.statusBar().showMessage(text, 8000)
        if not self.isVisible() and self.tray.isVisible():
            self.tray.showMessage(APP_NAME, text, QSystemTrayIcon.Information, 4000)

    # ================================================================ Sperre
    def lock(self):
        if not self.config["lock"].get("enabled"):
            QMessageBox.information(self, "Sperren", "Die Sperre ist aus. Einschalten unter Setup → „AluPC sperren“.")
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

