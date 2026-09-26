"""Mediathek: gespeicherte und zuletzt gezeigte Bilder, Videos und Diashows – mit Vorschaubildern."""

from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QImage, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListView,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)

from .. import media_library as lib
from . import icons, theme
from .source_picker import IMAGE_FILTER, VIDEO_FILTER
from .thumbnails import Thumbnails
from .widgets import button, page_header

CARD = QSize(240, 135)
TYPE_ICON = {"image": "image", "video": "video", "slideshow": "slides"}
TYPE_NAME = {"image": "Bild", "video": "Video", "slideshow": "Diashow"}
TYPE_COLOR = {"image": "#10b981", "video": "#f43f5e", "slideshow": "#f59e0b"}


def card_icon(cfg: dict, image: QImage | None, recent: bool = False) -> QIcon:
    """Vorschau-Karte: Bild (oder Symbol), Art-Abzeichen, ggf. „Datei fehlt“."""
    t = theme.current()
    dpr = 2
    pix = QPixmap(CARD.width() * dpr, CARD.height() * dpr)
    pix.setDevicePixelRatio(dpr)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    rect = QRectF(0, 0, CARD.width(), CARD.height())
    clip = QPainterPath()
    clip.addRoundedRect(rect, 12, 12)
    p.setClipPath(clip)
    p.fillRect(rect, QColor(t.surface2))
    kind = cfg.get("type", "image")
    if image is not None and not image.isNull():
        # „Ausfüllen“: Vorschau füllt die Karte, Ränder werden abgeschnitten
        scale = max(rect.width() / image.width(), rect.height() / image.height())
        w, h = image.width() * scale, image.height() * scale
        p.drawImage(QRectF((rect.width() - w) / 2, (rect.height() - h) / 2, w, h), image)
    else:
        icons.paint(p, TYPE_ICON.get(kind, "image"), QRectF(rect.center().x() - 24, rect.center().y() - 24, 48, 48),
                    t.muted, 1.6)
    if kind == "video":  # Abspiel-Symbol mittig
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 120))
        p.drawEllipse(rect.center(), 22, 22)
        icons.paint(p, "play", QRectF(rect.center().x() - 12, rect.center().y() - 12, 24, 24), "#ffffff", 2.2)
    # Abzeichen unten links: Art
    f = QFont()
    f.setPixelSize(11)
    f.setBold(True)
    p.setFont(f)
    label = TYPE_NAME.get(kind, "")
    w = p.fontMetrics().horizontalAdvance(label) + 16
    badge = QRectF(8, rect.height() - 28, w, 20)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(TYPE_COLOR.get(kind, t.accent)))
    p.drawRoundedRect(badge, 10, 10)
    p.setPen(QColor("#ffffff"))
    p.drawText(badge, Qt.AlignCenter, label)
    if recent:
        tag = QRectF(rect.width() - 76, 8, 68, 20)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 150))
        p.drawRoundedRect(tag, 10, 10)
        p.setPen(QColor("#ffffff"))
        p.drawText(tag, Qt.AlignCenter, "ZULETZT")
    if not lib.exists(cfg):
        p.fillRect(rect, QColor(0, 0, 0, 150))
        p.setPen(QColor("#fca5a5"))
        p.drawText(rect, Qt.AlignCenter, "Datei fehlt")
    p.end()
    return QIcon(pix)


class MediaLibraryDialog(QDialog):
    FILTERS = [("all", "Alle"), ("image", "Bilder"), ("video", "Videos"), ("slideshow", "Diashows")]

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.config = controller.config
        self.setWindowTitle("Mediathek")
        self.resize(1040, 700)
        self.thumbs = Thumbnails(self)
        self.thumbs.ready.connect(self._thumb_ready)
        self.filter = "all"

        # Filter als Knöpfe (Chips) + Suche
        chips = QHBoxLayout()
        chips.setSpacing(6)
        self.chip_group = QButtonGroup(self)
        for key, label in self.FILTERS:
            b = QPushButton(label)
            b.setObjectName("Chip")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, k=key: self._set_filter(k))
            self.chip_group.addButton(b)
            chips.addWidget(b)
            if key == "all":
                b.setChecked(True)
        chips.addStretch(1)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Suchen …")
        self.search.setClearButtonEnabled(True)
        self.search.setFixedWidth(240)
        self.search.textChanged.connect(self.reload)
        chips.addWidget(self.search)

        self.grid = QListWidget()
        self.grid.setViewMode(QListView.IconMode)
        self.grid.setIconSize(CARD)
        self.grid.setGridSize(QSize(CARD.width() + 20, CARD.height() + 52))
        self.grid.setResizeMode(QListView.Adjust)
        self.grid.setMovement(QListView.Static)
        self.grid.setWordWrap(True)
        self.grid.setSpacing(6)
        self.grid.setSelectionMode(QListWidget.ExtendedSelection)
        self.grid.setUniformItemSizes(True)
        self.grid.itemDoubleClicked.connect(lambda _i: self.show_selected())
        self.grid.itemSelectionChanged.connect(self._update_buttons)
        self.empty = QLabel("Noch leer · „Dateien hinzufügen …“")
        self.empty.setAlignment(Qt.AlignCenter)
        self.empty.setObjectName("Muted")
        self.empty.setWordWrap(True)

        add = button("Dateien hinzufügen …", "plus")
        add.clicked.connect(self.add_files)
        add_folder = button("Ordner als Diashow …", "slides")
        add_folder.clicked.connect(self.add_folder)
        self.save_btn = button("Speichern", "bookmark")
        self.save_btn.setToolTip("„Zuletzt gezeigt“ dauerhaft in der Mediathek behalten")
        self.save_btn.clicked.connect(self.save_selected)
        self.rename_btn = button("Umbenennen", "edit")
        self.rename_btn.clicked.connect(self.rename_selected)
        self.remove_btn = button("Entfernen", "trash", danger=True)
        self.remove_btn.clicked.connect(self.remove_selected)
        self.show_btn = button("Auf Monitor 2 zeigen", "play", primary=True)
        self.show_btn.clicked.connect(self.show_selected)
        actions = QHBoxLayout()
        actions.setSpacing(8)
        for w in (add, add_folder):
            actions.addWidget(w)
        actions.addStretch(1)
        for w in (self.save_btn, self.rename_btn, self.remove_btn, self.show_btn):
            actions.addWidget(w)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 20, 22, 18)
        lay.setSpacing(12)
        lay.addWidget(page_header("Mediathek", "Bilder · Videos · Diashows – Doppelklick zeigt"))
        lay.addLayout(chips)
        lay.addWidget(self.grid, 1)
        lay.addWidget(self.empty, 1)
        lay.addLayout(actions)
        t = theme.current()
        self.setStyleSheet(
            f"QPushButton#Chip {{ padding: 6px 14px; border-radius: 15px; border: 1px solid {t.border}; "
            f"background: {t.surface}; }}"
            f"QPushButton#Chip:checked {{ background: {t.accent}; color: #ffffff; border-color: {t.accent}; }}"
            f"QListWidget {{ background: transparent; border: none; }}"
            f"QListWidget::item {{ border-radius: 14px; padding: 6px; }}"
            f"QListWidget::item:selected {{ background: {t.accent_soft(0.22)}; color: {t.text}; }}"
            f"QListWidget::item:hover {{ background: {t.surface}; }}")
        self.reload()

    # ------------------------------------------------------------ Liste
    def _set_filter(self, key: str):
        self.filter = key
        self.reload()

    def entries(self) -> list[tuple[dict, bool]]:
        """(Eintrag, zuletzt?) – gespeicherte zuerst, dann zuletzt gezeigte; gefiltert."""
        rows = [(i, False) for i in lib.saved(self.config)] + [(i, True) for i in lib.recent(self.config)]
        text = self.search.text().strip().lower()
        return [(i, r) for i, r in rows
                if (self.filter == "all" or i.get("type") == self.filter)
                and (not text or text in (i.get("title", "") + " " + (i.get("path") or i.get("folder") or "")).lower())]

    def reload(self, *_):
        selected = {lib.key(i) for i in self.selected()}
        self.grid.clear()
        self._items: dict[str, list[QListWidgetItem]] = {}
        for cfg, recent in self.entries():
            image = self.thumbs.request(cfg)
            item = QListWidgetItem(card_icon(cfg, image, recent), cfg.get("title") or lib.default_title(cfg))
            item.setData(Qt.UserRole, cfg)
            item.setData(Qt.UserRole + 1, recent)
            item.setToolTip(cfg.get("path") or cfg.get("folder") or "")
            self.grid.addItem(item)
            target = cfg.get("folder") if cfg.get("type") == "slideshow" else cfg.get("path")
            self._items.setdefault(f"{cfg.get('type')}:{target}", []).append(item)
            if lib.key(cfg) in selected:
                item.setSelected(True)
        has = self.grid.count() > 0
        self.grid.setVisible(has)
        self.empty.setVisible(not has)
        self._update_buttons()

    def _thumb_ready(self, k: str, image: QImage):
        for item in self._items.get(k, []):
            try:
                item.setIcon(card_icon(item.data(Qt.UserRole), image, bool(item.data(Qt.UserRole + 1))))
            except RuntimeError:  # Liste wurde inzwischen neu aufgebaut
                pass

    def selected(self) -> list[dict]:
        return [i.data(Qt.UserRole) for i in self.grid.selectedItems()] if hasattr(self, "grid") else []

    def _update_buttons(self):
        items = self.grid.selectedItems()
        one = len(items) == 1
        self.show_btn.setEnabled(one and lib.exists(items[0].data(Qt.UserRole)))
        self.rename_btn.setEnabled(one and not items[0].data(Qt.UserRole + 1))
        self.save_btn.setEnabled(any(i.data(Qt.UserRole + 1) for i in items))
        self.remove_btn.setEnabled(bool(items))

    # ------------------------------------------------------------ Aktionen
    def add_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Bilder und Videos hinzufügen", "",
            f"Bilder und Videos ({IMAGE_FILTER.split('(')[1][:-1]} {VIDEO_FILTER.split('(')[1][:-1]});;"
            f"{IMAGE_FILTER};;{VIDEO_FILTER}")
        cfgs = []
        for path in paths:
            kind = lib.file_type(path)
            if kind == "image":
                cfgs.append({"type": "image", "path": path})
            elif kind == "video":
                cfgs.append({"type": "video", "path": path, "loop": True})
        if cfgs:
            lib.save_many(self.config, cfgs)
            self.reload()

    def add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Ordner mit Bildern wählen")
        if folder:
            lib.save(self.config, {"type": "slideshow", "folder": folder, "interval": 5})
            self.reload()

    def save_selected(self):
        for cfg in self.selected():
            lib.save(self.config, cfg)
        self.reload()

    def rename_selected(self):
        items = self.selected()
        if len(items) != 1:
            return
        cfg = items[0]
        title, ok = QInputDialog.getText(self, "Umbenennen", "Name:", text=cfg.get("title", ""))
        if ok:
            lib.rename(self.config, cfg, title)
            self.reload()

    def remove_selected(self):
        for cfg in self.selected():
            lib.remove(self.config, cfg)
        self.reload()

    def show_selected(self):
        items = self.selected()
        if len(items) == 1 and lib.exists(items[0]):
            cfg = {k: v for k, v in items[0].items() if k != "title"}
            self.controller.show_source(cfg)
            self.accept()
