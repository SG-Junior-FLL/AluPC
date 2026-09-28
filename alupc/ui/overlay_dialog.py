"""Overlays bearbeiten: Vorlage wählen, in der Vorschau an die gewünschte Stelle ziehen (rastet in Ecken, an den
Kanten und in der Mitte ein – dazwischen geht auch), Größe, Stil, Farbe und Text einstellen.

Jede Änderung gilt sofort auf Monitor 2."""

from __future__ import annotations

import copy
import time

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QImage, QLinearGradient, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from .. import overlays as ov
from ..now_playing import Track
from . import icons, theme
from .util import ColorButton
from .widgets import button, page_header

THUMB = QSize(224, 126)


def sample_data() -> ov.OverlayData:
    """Beispiel-Titel für Vorschaubilder der Vorlagen."""
    data = ov.OverlayData()
    data.set_track(Track(title="Blinding Lights", artist="The Weeknd", player="Spotify", playing=True,
                         position=84, length=200))
    return data


def _backdrop(p: QPainter, w: float, h: float) -> None:
    grad = QLinearGradient(0, 0, w, h)
    grad.setColorAt(0, QColor("#334155"))
    grad.setColorAt(1, QColor("#0f172a"))
    p.fillRect(QRectF(0, 0, w, h), grad)


def template_thumb(item: dict, data: ov.OverlayData) -> QImage:
    img = QImage(THUMB, QImage.Format_ARGB32_Premultiplied)
    p = QPainter(img)
    _backdrop(p, THUMB.width(), THUMB.height())
    # etwas größer zeichnen, damit man in der kleinen Vorschau etwas erkennt
    ov.paint_all(p, [dict(item, size=float(item.get("size", 1.0)) * 1.5)], THUMB.width(), THUMB.height(), data)
    p.end()
    return img


class TemplatePicker(QDialog):
    """Vorlagen für Overlays, nach Bereichen (Musik, Uhr & Zeit, Text, Bild & Logo, Live)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Overlay hinzufügen")
        self.resize(820, 600)
        self.chosen: dict | None = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 16)
        lay.addWidget(page_header("Overlay hinzufügen", "Vorlage wählen – danach frei anpassen", "layers"))
        self.list = QListWidget()
        self.list.setViewMode(QListWidget.IconMode)
        self.list.setIconSize(THUMB)
        self.list.setGridSize(QSize(THUMB.width() + 18, THUMB.height() + 40))
        self.list.setResizeMode(QListWidget.Adjust)
        self.list.setMovement(QListWidget.Static)
        from .templates_dialog import header_image

        data = sample_data()
        last = None
        for i, (cat, name, desc, item) in enumerate(ov.TEMPLATES):
            if cat != last:  # Überschrift je Bereich (wie bei „Neue Szene“)
                last = cat
                head = QListWidgetItem("")
                head.setFlags(Qt.NoItemFlags)
                pix = QPixmap.fromImage(header_image(cat, sum(1 for t in ov.TEMPLATES if t[0] == cat)))
                icon = QIcon(pix)
                icon.addPixmap(pix, QIcon.Disabled)  # sonst grau, weil nicht wählbar
                head.setIcon(icon)
                self.list.addItem(head)
            entry = QListWidgetItem(QIcon(QPixmap.fromImage(template_thumb({**ov.BASE, **item}, data))), name)
            entry.setToolTip(desc)
            entry.setData(Qt.UserRole, i)
            self.list.addItem(entry)
        self.list.itemDoubleClicked.connect(lambda _it: self._take())
        lay.addWidget(self.list, 1)
        row = QHBoxLayout()
        row.addStretch(1)
        cancel = button("Abbrechen", "x")
        cancel.clicked.connect(self.reject)
        ok = button("Hinzufügen", "plus", primary=True)
        ok.clicked.connect(self._take)
        row.addWidget(cancel)
        row.addWidget(ok)
        lay.addLayout(row)

    def _take(self):
        item = self.list.currentItem()
        if item is None or item.data(Qt.UserRole) is None:
            return
        _cat, name, _desc, tpl = ov.TEMPLATES[int(item.data(Qt.UserRole))]
        self.chosen = ov.from_template(tpl, name)
        self.accept()


class OverlayCanvas(QWidget):
    """Vorschau von Monitor 2 mit allen Overlays. Ziehen verschiebt (mit Einrasten), Mausrad ändert die Größe."""

    selected = Signal(str)
    moved = Signal(str, float, float)
    resized = Signal(str, float)

    def __init__(self, dialog):
        super().__init__()
        self.dialog = dialog
        self.setMinimumSize(420, 240)
        self.setMouseTracking(True)
        self._drag: tuple[str, QPointF, QRectF] | None = None
        self._guides: tuple[float | None, float | None] = (None, None)
        self._bg = QPixmap()
        self._bg_time = 0.0
        self._tick = QTimer(self, interval=1000)
        self._tick.timeout.connect(self.update)
        self._tick.start()

    def area(self) -> QRectF:
        """Fläche in Seitenverhältnis von Monitor 2, mittig."""
        screen = self.dialog.controller.output_screen()
        aspect = 16 / 9
        if screen is not None and screen.geometry().height() > 0:
            aspect = screen.geometry().width() / screen.geometry().height()
        w, h = self.width() - 8, self.height() - 8
        if w / h > aspect:
            w = h * aspect
        else:
            h = w / aspect
        return QRectF((self.width() - w) / 2, (self.height() - h) / 2, w, h)

    def _background(self) -> QPixmap:
        # Was Monitor 2 gerade zeigt (alle 2 s neu), sonst neutraler Hintergrund
        if time.monotonic() - self._bg_time > 2:
            self._bg_time = time.monotonic()
            out = self.dialog.controller.output
            self._bg = out.snapshot() if out.isVisible() else QPixmap()
        return self._bg

    def rects(self) -> list[tuple[dict, QRectF]]:
        a = self.area()
        data = self.dialog.data()
        return [(it, r.translated(a.x(), a.y())) for it, r in ov.layout(self.dialog.items, a.width(), a.height(), data)]

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        a = self.area()
        bg = self._background()
        p.save()
        p.setClipRect(a)
        if not bg.isNull():
            p.drawPixmap(a.toRect(), bg)
        else:
            p.translate(a.topLeft())
            _backdrop(p, a.width(), a.height())
            f = QFont()
            f.setPixelSize(int(a.height() * 0.06))
            p.setFont(f)
            p.setPen(QColor(255, 255, 255, 60))
            p.drawText(QRectF(0, 0, a.width(), a.height()), Qt.AlignCenter, "Monitor 2")
        p.restore()
        p.save()
        p.translate(a.topLeft())
        now = time.monotonic()
        for it, r in ov.layout(self.dialog.items, a.width(), a.height(), self.dialog.data()):
            ov.paint(p, it, r, a.height(), self.dialog.data(), now)
        p.restore()
        # Auswahl + Einrast-Linien
        accent = theme.current().c("accent")
        sel = self.dialog.current_id()
        for it, r in self.rects():
            if it.get("id") == sel:
                p.setPen(QPen(accent, 2, Qt.DashLine))
                p.setBrush(Qt.NoBrush)
                p.drawRoundedRect(r.adjusted(-3, -3, 3, 3), 6, 6)
        gx, gy = self._guides
        if self._drag is not None:
            p.setPen(QPen(QColor(accent.red(), accent.green(), accent.blue(), 150), 1, Qt.DashLine))
            m = ov.margin(a.width(), a.height())
            if gx is not None:
                x = a.x() + m + gx * (a.width() - 2 * m) if gx != 0.5 else a.center().x()
                p.drawLine(QPointF(x, a.top()), QPointF(x, a.bottom()))
            if gy is not None:
                y = a.y() + m + gy * (a.height() - 2 * m) if gy != 0.5 else a.center().y()
                p.drawLine(QPointF(a.left(), y), QPointF(a.right(), y))
        p.setPen(QPen(theme.current().c("border"), 1))
        p.setBrush(Qt.NoBrush)
        p.drawRect(a)

    def _hit(self, pos: QPointF) -> tuple[dict, QRectF] | None:
        for it, r in reversed(self.rects()):  # oben liegendes zuerst
            if r.adjusted(-4, -4, 4, 4).contains(pos):
                return it, r
        return None

    def mousePressEvent(self, event):
        hit = self._hit(event.position())
        if hit is None:
            return
        it, r = hit
        self.selected.emit(it["id"])
        self._drag = (it["id"], event.position() - r.topLeft(), r)
        self.setCursor(Qt.ClosedHandCursor)

    def mouseMoveEvent(self, event):
        if self._drag is None:
            self.setCursor(Qt.OpenHandCursor if self._hit(event.position()) else Qt.ArrowCursor)
            return
        item_id, offset, r = self._drag
        a = self.area()
        top_left = event.position() - offset - a.topLeft()
        x, y = ov.xy_for({}, QRectF(top_left, r.size()), a.width(), a.height())
        sx, sy = ov.snap(x), ov.snap(y)
        if event.modifiers() & Qt.AltModifier:  # Alt gedrückt: nicht einrasten
            sx, sy = x, y
        self._guides = (sx if sx in ov.SNAP else None, sy if sy in ov.SNAP else None)
        self.moved.emit(item_id, sx, sy)

    def mouseReleaseEvent(self, _event):
        self._drag = None
        self._guides = (None, None)
        self.setCursor(Qt.ArrowCursor)
        self.update()

    def wheelEvent(self, event):
        hit = self._hit(event.position())
        if hit is None:
            return
        it, _r = hit
        step = 1.1 if event.angleDelta().y() > 0 else 1 / 1.1
        self.selected.emit(it["id"])
        self.resized.emit(it["id"], max(0.4, min(3.0, float(it.get("size", 1.0)) * step)))


class OverlayDialog(QDialog):
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle("Overlays")
        self.resize(1180, 720)
        cfg = controller.config["overlays"]
        self.items: list[dict] = copy.deepcopy(cfg.get("items", []))
        self._apply_timer = QTimer(self, singleShot=True, interval=150)  # beim Tippen nicht jede Taste speichern
        self._apply_timer.timeout.connect(self._apply)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 18, 22, 16)
        lay.setSpacing(12)
        lay.addWidget(page_header("Overlays", "Über allem, was Monitor 2 zeigt · ziehen = verschieben, "
                                              "Mausrad = Größe", "layers"))
        top = QHBoxLayout()
        self.enabled = QCheckBox("Overlays auf Monitor 2 zeigen")
        self.enabled.setChecked(bool(cfg.get("on")))
        self.enabled.toggled.connect(lambda _on: self._schedule())
        top.addWidget(self.enabled)
        top.addStretch(1)
        lay.addLayout(top)

        body = QHBoxLayout()
        body.setSpacing(14)
        left = QVBoxLayout()
        self.list = QListWidget()
        self.list.setMinimumWidth(220)
        self.list.setMaximumWidth(260)
        self.list.currentRowChanged.connect(self._select_row)
        self.list.itemChanged.connect(self._item_checked)
        left.addWidget(self.list, 1)
        add = button("Vorlage hinzufügen", "plus", primary=True)
        add.clicked.connect(self._add)
        dup = button("Duplizieren", "copy")
        dup.clicked.connect(self._duplicate)
        rm = button("Löschen", "trash")
        rm.clicked.connect(self._remove)
        left.addWidget(add)
        row = QHBoxLayout()
        row.addWidget(dup)
        row.addWidget(rm)
        left.addLayout(row)
        body.addLayout(left)

        self.canvas = OverlayCanvas(self)
        self.canvas.selected.connect(self._select_id)
        self.canvas.moved.connect(self._moved)
        self.canvas.resized.connect(lambda i, s: self._set(i, size=s, refresh_form=True))
        body.addWidget(self.canvas, 1)

        self.form_host = QScrollArea()
        self.form_host.setWidgetResizable(True)
        self.form_host.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.form_host.setFixedWidth(340)
        body.addWidget(self.form_host)
        lay.addLayout(body, 1)

        bottom = QHBoxLayout()
        bottom.addStretch(1)
        close = button("Fertig", "check", primary=True)
        close.clicked.connect(self.accept)
        bottom.addWidget(close)
        lay.addLayout(bottom)

        self._fill_list()
        if self.items:
            self.list.setCurrentRow(0)
        else:
            self._build_form()

    # ---- Daten
    def data(self) -> ov.OverlayData:
        return self.controller.overlay_window.data

    def current_id(self) -> str:
        row = self.list.currentRow()
        return self.items[row]["id"] if 0 <= row < len(self.items) else ""

    def current(self) -> dict | None:
        row = self.list.currentRow()
        return self.items[row] if 0 <= row < len(self.items) else None

    def _schedule(self):
        self.canvas.update()
        self._apply_timer.start()

    def _apply(self):
        self.controller.config["overlays"] = {"on": self.enabled.isChecked(), "items": copy.deepcopy(self.items)}
        self.controller.overlays_changed()

    def done(self, result):
        self._apply_timer.stop()
        self._apply()
        super().done(result)

    def _set(self, item_id: str, refresh_form: bool = False, **changes):
        for it in self.items:
            if it["id"] == item_id:
                it.update(changes)
        if "name" in changes:
            self._fill_list(keep=True)
        if refresh_form:
            self._build_form()
        self._schedule()

    # ---- Liste
    def _fill_list(self, keep: bool = False):
        row = self.list.currentRow()
        self.list.blockSignals(True)
        self.list.clear()
        for it in self.items:
            entry = QListWidgetItem(icons.icon(_icon_for(it), it.get("color", "#888888"), 18),
                                    it.get("name") or ov.TYPES.get(it.get("type"), "Overlay"))
            entry.setFlags(entry.flags() | Qt.ItemIsUserCheckable)
            entry.setCheckState(Qt.Checked if it.get("on", True) else Qt.Unchecked)
            entry.setToolTip(ov.TYPES.get(it.get("type"), ""))
            self.list.addItem(entry)
        self.list.blockSignals(False)
        if keep and 0 <= row < self.list.count():
            self.list.setCurrentRow(row)

    def _item_checked(self, entry: QListWidgetItem):
        row = self.list.row(entry)
        if 0 <= row < len(self.items):
            self.items[row]["on"] = entry.checkState() == Qt.Checked
            self._schedule()

    def _select_row(self, _row: int):
        self._build_form()
        self.canvas.update()

    def _select_id(self, item_id: str):
        for i, it in enumerate(self.items):
            if it["id"] == item_id and self.list.currentRow() != i:
                self.list.setCurrentRow(i)

    def _moved(self, item_id: str, x: float, y: float):
        self._set(item_id, x=x, y=y)
        self._update_position_label()

    def _add(self):
        picker = TemplatePicker(self)
        if picker.exec() and picker.chosen:
            self.items.append(picker.chosen)
            self.enabled.setChecked(True)  # neues Overlay soll man auch sehen
            self._fill_list()
            self.list.setCurrentRow(len(self.items) - 1)
            self._schedule()

    def _duplicate(self):
        it = self.current()
        if it is None:
            return
        new = copy.deepcopy(it)
        new["id"] = ov.from_template({})["id"]
        new["name"] = f"{it.get('name', 'Overlay')} (Kopie)"
        new["x"], new["y"] = 1.0 - float(it.get("x", 1)), float(it.get("y", 1))  # gegenüber, damit man es sieht
        self.items.append(new)
        self._fill_list()
        self.list.setCurrentRow(len(self.items) - 1)
        self._schedule()

    def _remove(self):
        row = self.list.currentRow()
        if 0 <= row < len(self.items):
            del self.items[row]
            self._fill_list()
            self.list.setCurrentRow(min(row, len(self.items) - 1))
            if not self.items:
                self._build_form()
            self._schedule()

    # ---- Einstellungen des gewählten Overlays
    def _update_position_label(self):
        it = self.current()
        if it is not None and getattr(self, "pos_label", None) is not None:
            self.pos_label.setText("Stelle: " + ov.position_name(float(it.get("x", 1)), float(it.get("y", 1))))

    def _build_form(self):
        page = QWidget()
        form = QFormLayout(page)
        form.setContentsMargins(14, 12, 14, 12)
        form.setVerticalSpacing(10)
        it = self.current()
        self.pos_label = None
        if it is None:
            hint = QLabel("Noch kein Overlay. „Vorlage hinzufügen“ – z. B. Musik unten links oder eine Uhr.")
            hint.setWordWrap(True)
            hint.setObjectName("Muted")
            form.addRow(hint)
            self.form_host.setWidget(page)
            return
        iid = it["id"]
        t = it.get("type")
        title = QLabel(ov.TYPES.get(t, "Overlay"))
        title.setObjectName("SectionTitle")
        form.addRow(title)
        name = QLineEdit(it.get("name", ""))
        name.textChanged.connect(lambda v: self._set(iid, name=v))
        form.addRow("Name:", name)

        # Stelle: 3×3 Raster (Ecken, Kanten, Mitte) – frei dazwischen durch Ziehen in der Vorschau
        grid = QGridLayout()
        grid.setSpacing(4)
        arrows = {"oben links": "↖", "oben": "↑", "oben rechts": "↗", "links": "←", "Mitte": "•",
                  "rechts": "→", "unten links": "↙", "unten": "↓", "unten rechts": "↘"}
        for i, (label, (px, py)) in enumerate(ov.POSITIONS.items()):
            b = QPushButton(arrows[label])
            b.setToolTip(label)
            b.setFixedSize(46, 32)
            b.setStyleSheet("padding: 0; min-width: 0;")
            b.clicked.connect(lambda _=False, x=px, y=py: (self._set(iid, x=x, y=y), self._update_position_label()))
            grid.addWidget(b, i // 3, i % 3)
        holder = QWidget()
        holder.setLayout(grid)
        form.addRow("Stelle:", holder)
        self.pos_label = QLabel()
        self.pos_label.setObjectName("Muted")
        form.addRow("", self.pos_label)
        self._update_position_label()

        size = QSlider(Qt.Horizontal)
        size.setRange(40, 300)
        size.setValue(int(float(it.get("size", 1.0)) * 100))
        size.valueChanged.connect(lambda v: self._set(iid, size=v / 100))
        form.addRow("Größe:", size)
        style = QComboBox()
        for key, label in ov.STYLES.items():
            style.addItem(label, key)
        style.setCurrentIndex(max(0, style.findData(it.get("style", "glas"))))
        style.currentIndexChanged.connect(lambda _i: self._set(iid, style=style.currentData()))
        form.addRow("Stil:", style)
        color = ColorButton(it.get("color", "#1db954"))
        color.changed.connect(lambda c: (self._set(iid, color=c), self._fill_list(keep=True)))
        form.addRow("Farbe:", color)

        def text_field(key: str, label: str, placeholder: str = ""):
            edit = QLineEdit(it.get(key, ""))
            edit.setPlaceholderText(placeholder)
            edit.textChanged.connect(lambda v: self._set(iid, **{key: v}))
            form.addRow(label, edit)

        def check(key: str, label: str, default: bool = False):
            box = QCheckBox(label)
            box.setChecked(bool(it.get(key, default)))
            box.toggled.connect(lambda on: self._set(iid, **{key: on}))
            form.addRow("", box)

        if t == "music":
            variant = QComboBox()
            for key, label in ov.MUSIC_VARIANTS.items():
                variant.addItem(label, key)
            variant.setCurrentIndex(max(0, variant.findData(it.get("variant", "kompakt"))))
            variant.currentIndexChanged.connect(lambda _i: self._set(iid, variant=variant.currentData()))
            form.addRow("Form:", variant)
            check("cover", "Cover zeigen", True)
            note = QLabel("Zeigt, was der PC abspielt (Spotify, YouTube, VLC …).")
            note.setWordWrap(True)
            note.setObjectName("Muted")
            form.addRow(note)
        elif t == "clock":
            check("date", "Datum zeigen")
            check("seconds", "Sekunden zeigen")
        elif t == "timer":
            note = QLabel("Zeigt den AluPC-Timer (Kachel „Timer“). Rot in den letzten 10 Sekunden.")
            note.setWordWrap(True)
            note.setObjectName("Muted")
            form.addRow(note)
        elif t == "text":
            text_field("text", "Titel:")
            text_field("sub", "Zeile:", "optional")
        elif t == "ticker":
            text_field("text", "Text:")
            speed = QSlider(Qt.Horizontal)
            speed.setRange(20, 300)
            speed.setValue(int(float(it.get("speed", 1.0)) * 100))
            speed.valueChanged.connect(lambda v: self._set(iid, speed=v / 100))
            form.addRow("Tempo:", speed)
            width = QSlider(Qt.Horizontal)
            width.setRange(30, 100)
            width.setValue(int(float(it.get("width", 1.0)) * 100))
            width.valueChanged.connect(lambda v: self._set(iid, width=v / 100))
            form.addRow("Breite:", width)
        elif t == "image":
            row = QHBoxLayout()
            path = QLineEdit(it.get("path", ""))
            path.textChanged.connect(lambda v: self._set(iid, path=v))
            browse = QPushButton("…")
            browse.setFixedWidth(36)

            def pick():
                f, _ = QFileDialog.getOpenFileName(self, "Bild wählen", path.text(),
                                                   "Bilder (*.png *.jpg *.jpeg *.svg *.webp *.gif *.bmp)")
                if f:
                    path.setText(f)

            browse.clicked.connect(pick)
            row.addWidget(path, 1)
            row.addWidget(browse)
            holder = QWidget()
            holder.setLayout(row)
            form.addRow("Bild:", holder)
            opacity = QSlider(Qt.Horizontal)
            opacity.setRange(10, 100)
            opacity.setValue(int(float(it.get("opacity", 0.85)) * 100))
            opacity.valueChanged.connect(lambda v: self._set(iid, opacity=v / 100))
            form.addRow("Deckkraft:", opacity)
        elif t == "live":
            text_field("text", "Text:", "LIVE")
        elif t == "qr":
            text_field("url", "Link:", "https://…")
            text_field("text", "Beschriftung:", "optional")
        elif t == "badge":
            text_field("text", "Text:")
        self.form_host.setWidget(page)


def _icon_for(item: dict) -> str:
    return {"music": "music", "clock": "clock", "timer": "timer", "text": "text", "ticker": "text",
            "image": "image", "live": "cast", "qr": "qr", "badge": "info"}.get(item.get("type"), "layers")
