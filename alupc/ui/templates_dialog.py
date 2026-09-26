"""Neue Szene: Vorlage wählen (oder leer beginnen), Text eintragen, dann im Szenen-Editor fertig machen.

Vorlagen gibt es nur hier – sie werden erst zur Szene, wenn man sie im Editor speichert."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QIcon, QImage, QPainter, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..scenes import new_scene
from ..screens import (
    ANIMATED_NAME,
    CATEGORIES,
    CATEGORY_NAMES,
    DESIGNS,
    FIELD_LABELS,
    SCENE_TEMPLATES,
    TEMPLATE_CATEGORIES,
    TEMPLATE_DEFAULTS,
    TEMPLATE_LABELS,
    build_template,
    design_defaults,
    is_animated_template,
    render_preview,
    render_scene_preview,
)
from . import theme
from .widgets import button, page_header

THUMB = QSize(224, 126)
EMPTY = ("leer", "")
HEADER = ("kategorie", "")


def badge_image(img: QImage) -> None:
    """Kleines „✦ ANIMIERT“-Schild oben links aufs Vorschaubild."""
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    font = QFont()
    font.setPixelSize(10)
    font.setBold(True)
    p.setFont(font)
    text = "✦ ANIMIERT"
    w = p.fontMetrics().horizontalAdvance(text) + 12
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(0, 0, 0, 170))
    p.drawRoundedRect(6, 6, w, 18, 9, 9)
    p.setPen(QColor("#fde68a"))
    p.drawText(6, 6, w, 18, Qt.AlignCenter, text)
    p.end()


def header_image(title: str, count: int) -> QImage:
    """Kachel für eine Kategorie-Überschrift in der Liste."""
    t = theme.current()
    accent = t.c("accent")
    img = QImage(THUMB, QImage.Format_ARGB32_Premultiplied)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    fill = QColor(accent)
    fill.setAlpha(40)
    p.setPen(Qt.NoPen)
    p.setBrush(fill)
    p.drawRoundedRect(img.rect().adjusted(2, 2, -2, -2), 14, 14)
    p.setBrush(accent)
    p.drawRoundedRect(18, THUMB.height() // 2 - 26, 6, 52, 3, 3)
    font = QFont()
    font.setPixelSize(24)
    font.setBold(True)
    p.setFont(font)
    p.setPen(t.c("text"))
    p.drawText(img.rect().adjusted(36, 0, -12, -18), Qt.AlignVCenter | Qt.AlignLeft, title)
    font.setPixelSize(13)
    font.setBold(False)
    p.setFont(font)
    p.setPen(t.c("muted"))
    p.drawText(img.rect().adjusted(36, 34, -12, 0), Qt.AlignVCenter | Qt.AlignLeft, f"{count} Vorlagen")
    p.end()
    return img


class TemplatesDialog(QDialog):
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.config = controller.config
        self.setWindowTitle("Neue Szene")
        self.resize(1080, 700)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 18)
        lay.setSpacing(12)
        lay.addWidget(page_header("Neue Szene", "Vorlage wählen · Text eintragen · anpassen", "scenes"))

        filters = QHBoxLayout()
        filters.setSpacing(6)
        self.cat_group = QButtonGroup(self)
        for i, label in enumerate(["Alle", *CATEGORY_NAMES, "✦ " + ANIMATED_NAME]):
            b = QPushButton(label.replace("&", "&&"))  # „&“ sonst als Tastenkürzel-Unterstrich
            b.setObjectName("Segment")
            b.setCheckable(True)
            b.setChecked(i == 0)
            self.cat_group.addButton(b, i)
            filters.addWidget(b)
        self.cat_group.idClicked.connect(lambda _i: self._filter())
        filters.addSpacing(10)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Suchen …")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._filter)
        filters.addWidget(self.search, 1)
        lay.addLayout(filters)

        body = QHBoxLayout()
        body.setSpacing(18)
        self.list = QListWidget()
        self.list.setViewMode(QListWidget.IconMode)
        self.list.setIconSize(THUMB)
        self.list.setGridSize(QSize(THUMB.width() + 18, THUMB.height() + 40))
        self.list.setResizeMode(QListWidget.Adjust)
        self.list.setMovement(QListWidget.Static)
        self.list.setMinimumWidth(260)
        blank = QListWidgetItem("Leer")
        blank.setData(Qt.UserRole, EMPTY)
        blank.setData(Qt.UserRole + 1, "")
        blank.setData(Qt.UserRole + 2, "leer")
        blank.setIcon(QIcon(QPixmap.fromImage(render_scene_preview(new_scene("Leer"), THUMB.width(), THUMB.height()))))
        self.list.addItem(blank)
        entries = [("scene", k, v[0], v[1], TEMPLATE_CATEGORIES.get(k, "")) for k, v in SCENE_TEMPLATES.items()]
        entries += [("design", k, v[0], v[1], CATEGORIES.get(k, "")) for k, v in DESIGNS.items()]
        # nach Kategorie sortiert, je Kategorie eine Überschrift (nur bei „Alle“ ohne Suche sichtbar)
        order = {c: i for i, c in enumerate(CATEGORY_NAMES)}
        entries.sort(key=lambda e: order.get(e[4], len(order)))
        last_cat = None
        for kind, key, label, desc, cat in entries:
            if cat != last_cat:
                last_cat = cat
                head = QListWidgetItem("")
                head.setData(Qt.UserRole, HEADER)
                head.setData(Qt.UserRole + 1, cat)
                head.setData(Qt.UserRole + 2, "")
                head.setFlags(Qt.NoItemFlags)
                count = sum(1 for e in entries if e[4] == cat)
                pix = QPixmap.fromImage(header_image(cat or "Weitere", count))
                icon = QIcon(pix)
                icon.addPixmap(pix, QIcon.Disabled)  # sonst grau, weil nicht wählbar
                head.setIcon(icon)
                self.list.addItem(head)
            item = QListWidgetItem(label)
            animated = is_animated_template(kind, key)
            item.setData(Qt.UserRole, (kind, key))
            item.setData(Qt.UserRole + 1, cat)
            item.setData(Qt.UserRole + 2, f"{label} {desc} {'animiert bewegt' if animated else ''}".lower())
            item.setData(Qt.UserRole + 3, animated)
            item.setToolTip(desc + (" · animiert" if animated else ""))
            img = render_preview(design_defaults(key), THUMB.width(), THUMB.height()) if kind == "design" else \
                render_scene_preview(build_template(key, {}), THUMB.width(), THUMB.height())
            if animated:
                badge_image(img)
            item.setIcon(QIcon(QPixmap.fromImage(img)))
            self.list.addItem(item)
        body.addWidget(self.list, 3)

        side = QWidget()
        side.setObjectName("Card")
        side.setAttribute(Qt.WA_StyledBackground, True)
        side.setMinimumWidth(320)
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
        self.next_btn = button("Weiter", "edit", primary=True)
        self.next_btn.setToolTip("Szenen-Editor öffnen")
        self.next_btn.clicked.connect(self.save_scene)
        col.addWidget(self.heading)
        col.addWidget(self.desc)
        col.addWidget(self.preview, 0, Qt.AlignHCenter)
        col.addLayout(form)
        col.addStretch(1)
        col.addWidget(self.next_btn)
        body.addWidget(side, 2)
        lay.addLayout(body, 1)

        self._redraw = QTimer(self, singleShot=True, interval=150)
        self._redraw.timeout.connect(self._update_preview)
        for w in (self.title, self.name):
            w.textChanged.connect(lambda *_: self._redraw.start())
        self.text.textChanged.connect(lambda: self._redraw.start())
        self.minutes.valueChanged.connect(lambda *_: self._redraw.start())
        self.list.currentItemChanged.connect(self._selected)
        self.list.itemDoubleClicked.connect(lambda _i: self.save_scene())
        self._filter()
        self.list.setCurrentRow(0)

    def _filter(self, *_):
        cat_id = self.cat_group.checkedId()
        cat = None if cat_id <= 0 else ([*CATEGORY_NAMES, ANIMATED_NAME])[cat_id - 1]
        words = self.search.text().lower().split()
        for i in range(self.list.count()):
            item = self.list.item(i)
            is_blank = item.data(Qt.UserRole) == EMPTY
            if item.data(Qt.UserRole) == HEADER:
                ok = cat is None and not words
            else:
                in_cat = item.data(Qt.UserRole + 3) if cat == ANIMATED_NAME else item.data(Qt.UserRole + 1) == cat
                ok = (cat is None or in_cat or is_blank) and all(w in item.data(Qt.UserRole + 2) for w in words)
            item.setHidden(not ok)
        current = self.list.currentItem()
        if current is None or current.isHidden():
            first = next((self.list.item(i) for i in range(self.list.count())
                          if not self.list.item(i).isHidden() and self.list.item(i).data(Qt.UserRole) != HEADER),
                         None)
            if first is not None:
                self.list.setCurrentItem(first)

    # ------------------------------------------------------------ Auswahl
    def current(self) -> tuple[str, str]:
        item = self.list.currentItem()
        data = item.data(Qt.UserRole) if item else EMPTY
        return EMPTY if data == HEADER else data

    def _selected(self, *_):
        kind, key = self.current()
        if kind == "leer":
            label, desc, fields, values, a, b = "Leer", "Layout und Felder selbst wählen", (), {}, "Titel:", "Text:"
        elif kind == "design":
            label, desc, title, text, _color = DESIGNS[key]
            fields = ("title", "text") + (("minutes",) if key == "pause" else ())
            values = {"title": title, "text": text, "minutes": design_defaults(key).get("minutes", 10)}
            a, b = FIELD_LABELS.get(key, ("Titel:", "Text:"))
        else:
            label, desc, fields, _build = SCENE_TEMPLATES[key]
            values = {"minutes": 5, **TEMPLATE_DEFAULTS.get(key, {})}
            a, b = TEMPLATE_LABELS.get(key, ("Titel:", "Text:"))
        self.name.setText(label if kind != "leer" else "")
        self.name.setPlaceholderText("Name der Szene")
        self.heading.setText(label)
        self.desc.setText(desc)
        self.title.setText(values.get("title", ""))
        self.text.setPlainText(values.get("text", ""))
        self.minutes.setValue(int(values.get("minutes", 5)))
        self.form.labelForField(self.title).setText(a)
        self.form.labelForField(self.text).setText(b)
        self.form.setRowVisible(self.title, "title" in fields)
        self.form.setRowVisible(self.text, "text" in fields)
        self.form.setRowVisible(self.minutes, "minutes" in fields)
        self._update_preview()

    def values(self) -> dict:
        return {"name": self.name.text().strip(), "title": self.title.text(), "text": self.text.toPlainText(),
                "minutes": self.minutes.value()}

    def template_scene(self) -> dict:
        """Die gewählte Vorlage als (noch nicht gespeicherte) Szene."""
        kind, key = self.current()
        v = self.values()
        name = v["name"] or self.heading.text()
        if kind == "leer":
            return new_scene(v["name"] or "Szene")
        if kind == "scene":
            return {**build_template(key, v), "name": name}
        cfg = {**design_defaults(key), "title": v["title"], "text": v["text"]}
        if key == "pause":
            cfg["minutes"] = v["minutes"]
        return {"name": name, "layout": "vollbild", "background": "#000000", "slots": [cfg]}

    def _update_preview(self):
        self.preview.setPixmap(QPixmap.fromImage(render_scene_preview(self.template_scene(), 320, 180)))

    # ------------------------------------------------------------ Weiter → Editor
    def save_scene(self):
        """Szenen-Editor mit der Vorlage öffnen – erst dort wird gespeichert."""
        from .scene_editor import SceneEditor

        blank = self.current() == EMPTY
        editor = SceneEditor(self.config, None, self, template=None if blank else self.template_scene())
        editor.setAttribute(Qt.WA_DeleteOnClose)
        self.editor = editor

        def saved():
            name = editor.scene["name"]
            parent = self.parent()
            if hasattr(parent, "_reload_scenes"):
                parent._reload_scenes(name)
            self.controller.changed.emit()
            self.controller.message.emit(f"Szene „{name}“ gespeichert")
            self.accept()

        editor.accepted.connect(saved)
        editor.open()
        return editor
