"""Vorlagen: gestaltete Seiten (Willkommen, Ablauf, Pause …) und fertige Szenen – eigenen Text eingeben,
sofort auf Monitor 2 zeigen oder als Szene speichern."""

from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QIcon, QImage, QPainter, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..screens import DESIGNS, SCENE_TEMPLATES, TEMPLATE_DEFAULTS, build_template, design_defaults, render_preview
from .widgets import button, page_header, paint_scene_thumb

THUMB = QSize(224, 126)


def _scene_thumb(scene: dict) -> QImage:
    img = QImage(THUMB, QImage.Format_ARGB32_Premultiplied)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    paint_scene_thumb(p, QRectF(0, 0, THUMB.width(), THUMB.height()), scene)
    p.end()
    return img


class TemplatesDialog(QDialog):
    def __init__(self, controller, parent=None, scenes_first: bool = False):
        super().__init__(parent)
        self.controller = controller
        self.config = controller.config
        self.setWindowTitle("Vorlagen")
        self.resize(1080, 700)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 18)
        lay.setSpacing(12)
        lay.addWidget(page_header("Vorlagen", "Fertige Seiten und Szenen – eigenen Text eingeben, zeigen oder "
                                              "als Szene speichern.", "star"))
        body = QHBoxLayout()
        body.setSpacing(18)
        self.list = QListWidget()
        self.list.setViewMode(QListWidget.IconMode)
        self.list.setIconSize(THUMB)
        self.list.setGridSize(QSize(THUMB.width() + 18, THUMB.height() + 44))
        self.list.setResizeMode(QListWidget.Adjust)
        self.list.setMovement(QListWidget.Static)
        self.list.setWordWrap(True)
        self.list.setMinimumWidth(500)
        entries = [("design", k, f"Seite: {v[0]}") for k, v in DESIGNS.items()]
        scenes = [("scene", k, f"Szene: {v[0]}") for k, v in SCENE_TEMPLATES.items()]
        for kind, key, label in (scenes + entries if scenes_first else entries + scenes):
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, (kind, key))
            img = render_preview(design_defaults(key), THUMB.width(), THUMB.height()) if kind == "design" else \
                _scene_thumb(build_template(key, {}))
            item.setIcon(QIcon(QPixmap.fromImage(img)))
            item.setSizeHint(QSize(THUMB.width() + 12, THUMB.height() + 40))
            self.list.addItem(item)
        body.addWidget(self.list, 3)

        side = QWidget()
        side.setObjectName("Card")
        side.setAttribute(Qt.WA_StyledBackground, True)
        side.setMinimumWidth(340)
        col = QVBoxLayout(side)
        col.setContentsMargins(16, 16, 16, 16)
        self.heading = QLabel()
        self.heading.setObjectName("SectionTitle")
        self.desc = QLabel()
        self.desc.setObjectName("Muted")
        self.desc.setWordWrap(True)
        self.preview = QLabel()
        self.preview.setFixedSize(320, 180)
        self.preview.setAlignment(Qt.AlignCenter)
        form = QFormLayout()
        self.name = QLineEdit()
        self.name.setPlaceholderText("Name der Szene")
        self.title = QLineEdit()
        self.text = QPlainTextEdit()
        self.text.setMaximumHeight(110)
        self.minutes = QSpinBox()
        self.minutes.setRange(1, 240)
        self.minutes.setSuffix(" min")
        form.addRow("Name:", self.name)
        form.addRow("Titel:", self.title)
        form.addRow("Text:", self.text)
        form.addRow("Dauer:", self.minutes)
        self.form = form
        self.show_btn = button("Jetzt auf Monitor 2 zeigen", "play", primary=True)
        self.show_btn.clicked.connect(self.show_now)
        self.save_btn = button("Als Szene speichern", "scenes")
        self.save_btn.clicked.connect(self.save_scene)
        col.addWidget(self.heading)
        col.addWidget(self.desc)
        col.addWidget(self.preview, 0, Qt.AlignHCenter)
        col.addLayout(form)
        col.addStretch(1)
        col.addWidget(self.show_btn)
        col.addWidget(self.save_btn)
        body.addWidget(side, 2)
        lay.addLayout(body, 1)

        self._redraw = QTimer(self, singleShot=True, interval=150)
        self._redraw.timeout.connect(self._update_preview)
        for w in (self.title, self.name):
            w.textChanged.connect(lambda *_: self._redraw.start())
        self.text.textChanged.connect(lambda: self._redraw.start())
        self.minutes.valueChanged.connect(lambda *_: self._redraw.start())
        self.list.currentItemChanged.connect(self._selected)
        self.list.setCurrentRow(0)

    # ------------------------------------------------------------ Auswahl
    def current(self) -> tuple[str, str]:
        item = self.list.currentItem()
        return item.data(Qt.UserRole) if item else ("design", "willkommen")

    def _selected(self, *_):
        kind, key = self.current()
        labels = {"wlan": ("WLAN-Name:", "Passwort:"), "zitat": ("Zitat:", "Autor:"),
                  "ablauf": ("Überschrift:", "Punkte:"), "laufschrift": ("Titel:", "Laufschrift:"),
                  "gaeste_wlan": ("WLAN-Name:", "Passwort:"), "ablauf_uhr": ("Überschrift:", "Punkte:"),
                  "kamera_laufschrift": ("Titel:", "Textleiste:")}
        if kind == "design":
            label, desc, title, text, _color = DESIGNS[key]
            fields = ("title", "text") + (("minutes",) if key == "pause" else ())
            values = {"title": title, "text": text, "minutes": 10}
            self.name.setText(label)
        else:
            label, desc, fields, _build = SCENE_TEMPLATES[key]
            values = {"minutes": 5, **TEMPLATE_DEFAULTS.get(key, {})}
            self.name.setText(label)
        self.heading.setText(label)
        self.desc.setText(desc)
        self.title.setText(values.get("title", ""))
        self.text.setPlainText(values.get("text", ""))
        self.minutes.setValue(int(values.get("minutes", 5)))
        a, b = labels.get(key, ("Titel:", "Text:"))
        self.form.labelForField(self.title).setText(a)
        self.form.labelForField(self.text).setText(b)
        self.form.setRowVisible(self.title, "title" in fields)
        self.form.setRowVisible(self.text, "text" in fields)
        self.form.setRowVisible(self.minutes, "minutes" in fields)
        self._update_preview()

    def values(self) -> dict:
        return {"name": self.name.text().strip(), "title": self.title.text(), "text": self.text.toPlainText(),
                "minutes": self.minutes.value()}

    def source(self) -> dict:
        """Was gezeigt wird: eine gestaltete Seite oder eine Szene."""
        kind, key = self.current()
        v = self.values()
        if kind == "design":
            cfg = {**design_defaults(key), "title": v["title"], "text": v["text"]}
            if key == "pause":
                cfg["minutes"] = v["minutes"]
            return cfg
        return build_template(key, v)

    def _update_preview(self):
        kind, _key = self.current()
        src = self.source()
        img = render_preview(src, 320, 180) if kind == "design" else _scene_thumb(src).scaled(
            320, 180, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.preview.setPixmap(QPixmap.fromImage(img))

    # ------------------------------------------------------------ Aktionen
    def _unique_name(self, name: str) -> str:
        existing = set(self.config.scene_names())
        if name not in existing:
            return name
        i = 2
        while f"{name} {i}" in existing:
            i += 1
        return f"{name} {i}"

    def save_scene(self) -> str:
        kind, _key = self.current()
        src = self.source()
        name = self._unique_name(self.name.text().strip() or self.heading.text())
        scene = {**src, "name": name} if kind == "scene" else \
            {"name": name, "layout": "vollbild", "background": "#000000", "slots": [src]}
        self.config.put_scene(scene)
        parent = self.parent()
        if hasattr(parent, "_reload_scenes"):  # Szenen-Seite gleich aktualisieren
            parent._reload_scenes(name)
        self.controller.changed.emit()
        self.controller.message.emit(f"Szene „{name}“ gespeichert – unter „Szenen“.")
        return name

    def show_now(self):
        kind, _key = self.current()
        if kind == "design":
            self.controller.show_source(self.source())
        else:
            name = self.save_scene()
            self.controller.show_source({"type": "scene", "scene": name})
