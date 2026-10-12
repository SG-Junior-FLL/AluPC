"""Whiteboard-Fenster auf Monitor 1 – zeichnet direkt auf die Tafel, die Monitor 2 zeigt (gleiche Ansicht).

Bedienung wie in einer Notiz-App: links die Seiten, oben die Werkzeuge. Stift mit Druck (Grafiktablett/Stift),
Mausrad = verschieben, Strg+Mausrad oder zwei Finger = zoomen, mittlere Maustaste oder Leertaste+Ziehen =
verschieben. Tasten: P Stift, M Marker, E Radierer, L Lasso, F Form, T Text, X Laser, Strg+Z/Strg+Y, Entf löscht die
Auswahl, + / − / 0 Zoom, Bild↑/Bild↓ Seiten.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QPointF, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QActionGroup, QColor, QIcon, QInputDevice, QKeySequence, QPainter, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QColorDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..board import SHAPES, paint_board
from ..whiteboard import BACKGROUNDS
from . import icons, theme

TOOL_BUTTONS = [("pen", "edit", "Stift (P)"), ("marker", "highlighter", "Marker (M)"),
                ("eraser", "eraser", "Radierer (E) – löscht ganze Striche"),
                ("lasso", "grid", "Lasso (L) – einkreisen, dann verschieben/löschen/färben"),
                ("shape", "layers", "Form (F): Linie, Pfeil, Rechteck, Kreis"), ("text", "text", "Text (T)"),
                ("laser", "laser", "Laser (X) – nur zeigen, malt nichts")]
SHAPE_NAMES = {"line": "Linie", "arrow": "Pfeil", "rect": "Rechteck", "ellipse": "Kreis"}


def _paper_icon(key: str) -> QPixmap:
    """Kleine Vorschau eines Hintergrunds (abgerundet, mit Rand) für Knopf und Menü."""
    from PySide6.QtGui import QPainterPath, QPen

    from ..whiteboard import paint_background

    pm = QPixmap(60, 40)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    clip = QPainterPath()
    clip.addRoundedRect(QRectF(1, 1, 58, 38), 7, 7)
    p.setClipPath(clip)
    p.scale(1.5, 1.5)  # kleiner malen: Kästchen/Linien bleiben im kleinen Symbol erkennbar
    paint_background(p, QRectF(0, 0, 40, 40 / 1.5), key)
    p.resetTransform()
    p.setClipping(False)
    p.setPen(QPen(QColor(theme.current().border), 2))
    p.setBrush(Qt.NoBrush)
    p.drawPath(clip)
    p.end()
    return pm


def _btn(icon_name: str, tip: str, checkable: bool = False, text: str = "") -> QToolButton:
    t = theme.current()
    b = QToolButton()
    b.setIcon(icons.icon(icon_name, t.text, 20))
    b.setIconSize(QSize(20, 20))
    b.setToolTip(tip)
    b.setCheckable(checkable)
    b.setCursor(Qt.PointingHandCursor)
    if text:
        b.setText(text)
        b.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
    b.setMinimumSize(38, 38)
    b.setStyleSheet(f"QToolButton {{ border: none; border-radius: 10px; padding: 4px 6px; }}"
                    f" QToolButton:hover {{ background: {t.soft(t.text, 0.08)}; }}"
                    f" QToolButton:checked {{ background: {t.soft(t.accent, 0.22)}; }}")
    return b


def _group() -> tuple[QFrame, QHBoxLayout]:
    box = QFrame()
    box.setObjectName("Group")
    t = theme.current()
    box.setStyleSheet(f"#Group {{ background: {t.surface}; border: 1px solid {t.border}; border-radius: 14px; }}")
    lay = QHBoxLayout(box)
    lay.setContentsMargins(6, 3, 6, 3)
    lay.setSpacing(2)
    return box, lay


class BoardCanvas(QWidget):
    """Die Tafel in Monitor-2-Form (gleiche Ansicht wie auf Monitor 2)."""

    def __init__(self, win):
        super().__init__(win)
        self.win = win
        self.board = win.board
        self.setMouseTracking(True)
        self.setAttribute(Qt.WA_AcceptTouchEvents)
        self.grabGesture(Qt.PinchGesture)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMinimumSize(480, 270)
        self._pan_from: QPointF | None = None
        self._space = False
        self._drawing = False
        self._hover: QPointF | None = None
        self.board.changed.connect(self.update)

    def area(self) -> QRectF:
        r = QRectF(self.rect()).adjusted(8, 8, -8, -8)
        a = self.board.aspect or 16 / 9
        w = min(r.width(), r.height() * a)
        h = w / a
        return QRectF(r.center().x() - w / 2, r.center().y() - h / 2, w, h)

    def to_world(self, pos: QPointF) -> QPointF:
        inv, _ok = self.board.transform(self.area()).inverted()
        return inv.map(pos)

    def paintEvent(self, _e):
        t = theme.current()
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(t.bg))
        r = self.area()
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 40))
        p.drawRoundedRect(r.adjusted(-2, 0, 2, 5), 10, 10)
        paint_board(p, r, self.board)
        if self._hover is not None and self.win.tool == "eraser":  # Radierer-Kreis
            rad = float(self.board.settings()["eraser"]) / max(0.4, self.board.zoom)
            scale = self.board.transform(r).m11()
            p.setPen(QColor(t.accent))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(self._hover, rad * scale, rad * scale)
        p.end()

    # ---- Eingabe
    def _is_touch(self, e) -> bool:
        dev = e.pointingDevice() if hasattr(e, "pointingDevice") else None
        return dev is not None and dev.type() == QInputDevice.DeviceType.TouchScreen

    def _input(self, phase: str, pos: QPointF, pressure: float = 0.5) -> None:
        tool = self.win.tool
        if tool == "text":
            if phase == "down":
                self.win.add_text_at(self.to_world(pos))
            return
        if tool == "shape":
            tool = self.win.shape
        w = self.to_world(pos)
        self.board.input(phase, w.x(), w.y(), pressure, tool, self.win.color, self.win.width_for(tool))

    def mousePressEvent(self, e):
        self.setFocus()
        pan = e.button() == Qt.MiddleButton or (e.button() == Qt.LeftButton and self._space) or (
            e.button() == Qt.LeftButton and self._is_touch(e) and self.board.settings()["pencil_only"])
        if pan:
            self._pan_from = e.position()
            self.setCursor(Qt.ClosedHandCursor)
            return
        if e.button() == Qt.RightButton:
            self.win.context_menu(e.globalPosition().toPoint())
            return
        if e.button() == Qt.LeftButton:
            self._drawing = True
            self._input("down", e.position())

    def mouseMoveEvent(self, e):
        self._hover = e.position()
        if self._pan_from is not None:
            d = e.position() - self._pan_from
            self._pan_from = e.position()
            s = self.board.transform(self.area()).m11()
            self.board.pan(d.x() / s, d.y() / s)
            return
        if self._drawing:
            self._input("move", e.position())
        elif self.win.tool == "eraser":
            self.update()

    def mouseReleaseEvent(self, e):
        if self._pan_from is not None:
            self._pan_from = None
            self.unsetCursor()
            self.win.update_cursor()
            return
        if self._drawing:
            self._drawing = False
            self._input("up", e.position())

    def tabletEvent(self, e):
        """Grafiktablett/Stift: mit Druck zeichnen (Maus-Ereignisse danach unterdrückt)."""
        phase = {QEvent.TabletPress: "down", QEvent.TabletMove: "move", QEvent.TabletRelease: "up"}.get(e.type())
        if phase is None:
            return
        if phase == "move" and not self._drawing:
            self._hover = e.position()
            e.accept()
            return
        if phase == "down":
            self._drawing = True
        if phase == "up":
            self._drawing = False
        self._input(phase, e.position(), e.pressure() or 0.5)
        e.accept()

    def wheelEvent(self, e):
        d = e.angleDelta()
        s = self.board.transform(self.area()).m11()
        if e.modifiers() & Qt.ControlModifier:  # zoomen an der Mausstelle
            self.board.zoom_by(1.12 if d.y() > 0 else 1 / 1.12, self.to_world(e.position()))
        elif e.modifiers() & Qt.ShiftModifier:
            self.board.pan(d.y() / 2 / s, 0)
        else:
            self.board.pan(d.x() / 2 / s, d.y() / 2 / s)

    def event(self, e):
        if e.type() == QEvent.Gesture:
            pinch = e.gesture(Qt.PinchGesture)
            if pinch is not None:
                f = pinch.scaleFactor()
                if f and abs(f - 1) > 0.001:
                    self.board.zoom_by(f, self.to_world(self.mapFromGlobal(pinch.centerPoint().toPoint())))
                c, last = pinch.centerPoint(), pinch.lastCenterPoint()
                s = self.board.transform(self.area()).m11()
                self.board.pan((c.x() - last.x()) / s, (c.y() - last.y()) / s)
                return True
        return super().event(e)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Space and not e.isAutoRepeat():
            self._space = True
            self.setCursor(Qt.OpenHandCursor)
            return
        super().keyPressEvent(e)

    def keyReleaseEvent(self, e):
        if e.key() == Qt.Key_Space and not e.isAutoRepeat():
            self._space = False
            self.win.update_cursor()
            return
        super().keyReleaseEvent(e)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.update()


class _SideScroll(QScrollArea):
    def wheelEvent(self, e):
        bar = self.horizontalScrollBar()
        delta = e.angleDelta().y() or e.angleDelta().x()
        if bar.maximum() > 0 and delta:
            bar.setValue(bar.value() - delta)
            e.accept()
            return
        super().wheelEvent(e)


class BoardWindow(QWidget):
    TITLE = "AluPC – Whiteboard"

    def __init__(self, controller, parent=None):
        super().__init__(parent, Qt.Window)
        self.controller = controller
        self.board = controller.board
        self.setWindowTitle(self.TITLE)
        self.resize(1280, 820)
        cfg = self.board.settings()
        self.tool = "pen"
        self.shape = "line"
        self.color = cfg["colors"][0] if self.board.page["bg"] not in ("tafel", "schwarz", "blaupause") else "#ffffff"
        self.widths = {"pen": float(cfg["width"]), "marker": float(cfg["marker_width"])}
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 6)
        root.setSpacing(8)
        root.addWidget(self._toolbar_area())
        body = QHBoxLayout()
        body.setSpacing(8)
        self.pages = QListWidget()
        self.pages.setViewMode(QListWidget.IconMode)
        self.pages.setFlow(QListWidget.TopToBottom)
        self.pages.setMovement(QListWidget.Static)
        self.pages.setIconSize(QSize(150, 90))
        self.pages.setFixedWidth(184)
        self.pages.setSpacing(4)
        self.pages.currentRowChanged.connect(self._page_clicked)
        body.addWidget(self.pages)
        self.canvas = BoardCanvas(self)
        body.addWidget(self.canvas, 1)
        root.addLayout(body, 1)
        self.status = QLabel()
        self.status.setObjectName("Muted")
        self.status.setMinimumWidth(1)  # langer Hinweis darf abgeschnitten werden, statt das Fenster zu verbreitern
        self.status.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        root.addWidget(self.status)
        self._thumbs_soon = QTimer(self, singleShot=True, interval=500)
        self._thumbs_soon.timeout.connect(self._thumbs)
        self.board.changed.connect(self._on_change)
        self._shortcuts()
        self.set_tool("pen")
        self._on_change()
        self._thumbs()

    # ---------------------------------------------------------------- Werkzeugleiste
    def _toolbar_area(self) -> QScrollArea:
        """Leiste in einem waagerecht scrollbaren Bereich: Knöpfe werden nie gequetscht, und das Fenster passt auch
        auf kleine Bildschirme (dann Mausrad über der Leiste = seitlich schieben)."""
        bar = QWidget()
        bar.setLayout(self._toolbar())
        bar.layout().setContentsMargins(0, 0, 0, 0)
        bar.setMinimumWidth(bar.sizeHint().width())
        area = _SideScroll()
        area.setWidget(bar)
        area.setWidgetResizable(True)
        area.setFrameShape(QFrame.NoFrame)
        area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        area.setStyleSheet("QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; }"
                           " QScrollBar:horizontal { height: 6px; }")
        area.setFixedHeight(bar.sizeHint().height() + 8)
        return area

    def _toolbar(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)
        box, lay = _group()
        self.menu_btn = _btn("layers", "Tafel: neu, öffnen, umbenennen, speichern als PNG/PDF", text="Tafel")
        self.menu_btn.setPopupMode(QToolButton.InstantPopup)
        self.menu_btn.setMenu(QMenu(self))
        self.menu_btn.menu().aboutToShow.connect(self._fill_board_menu)
        lay.addWidget(self.menu_btn)
        row.addWidget(box)
        box, lay = _group()
        self.tool_btns: dict[str, QToolButton] = {}
        for key, icon_name, tip in TOOL_BUTTONS:
            b = _btn(icon_name, tip, checkable=True)
            b.clicked.connect(lambda _c=False, k=key: self.set_tool(k))
            if key == "shape":
                m = QMenu(self)
                for skey, label in SHAPE_NAMES.items():
                    m.addAction(label, lambda s=skey: (setattr(self, "shape", s), self.set_tool("shape")))
                b.setMenu(m)
                b.setPopupMode(QToolButton.MenuButtonPopup)
            self.tool_btns[key] = b
            lay.addWidget(b)
        row.addWidget(box)
        box, lay = _group()
        self.color_btns: list[QToolButton] = []
        for i in range(8):
            b = QToolButton()
            b.setFixedSize(26, 26)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _c=False, n=i: self.set_color(self.board.settings()["colors"][n]))
            self.color_btns.append(b)
            lay.addWidget(b)
        more = _btn("palette", "Andere Farbe …")
        more.clicked.connect(self._pick_color)
        lay.addWidget(more)
        row.addWidget(box)
        box, lay = _group()
        self.width_btns = {}
        for label, factor in (("fein", 0.6), ("mittel", 1.0), ("dick", 2.2)):
            b = QToolButton()
            b.setText({"fein": "•", "mittel": "●", "dick": "⬤"}[label])
            b.setToolTip(f"Strich {label}")
            b.setCheckable(True)
            b.setFixedSize(32, 32)
            b.clicked.connect(lambda _c=False, f=factor: self._set_width_factor(f))
            self.width_btns[factor] = b
            lay.addWidget(b)
        row.addWidget(box)
        box, lay = _group()
        self.undo_btn = _btn("undo", "Rückgängig (Strg+Z)")
        self.undo_btn.clicked.connect(self.board.undo)
        self.redo_btn = _btn("refresh", "Wiederholen (Strg+Y)")
        self.redo_btn.clicked.connect(self.board.redo)
        lay.addWidget(self.undo_btn)
        lay.addWidget(self.redo_btn)
        row.addWidget(box)
        row.addStretch(1)
        box, lay = _group()
        out = _btn("zoom_out", "Herauszoomen (−)")
        out.clicked.connect(lambda: self.board.zoom_by(0.8))
        self.zoom_lab = QToolButton()
        self.zoom_lab.setToolTip("Ganze Seite (0)")
        self.zoom_lab.setMinimumWidth(58)
        self.zoom_lab.clicked.connect(self.board.fit)
        zin = _btn("zoom_in", "Hineinzoomen (+)")
        zin.clicked.connect(lambda: self.board.zoom_by(1.25))
        for w in (out, self.zoom_lab, zin):
            lay.addWidget(w)
        row.addWidget(box)
        box, lay = _group()
        prev = _btn("back", "Vorige Seite (Bild↑)")
        prev.clicked.connect(lambda: self.board.goto(self.board.doc["page"] - 1))
        self.page_lab = QLabel()
        self.page_lab.setMinimumWidth(52)
        self.page_lab.setAlignment(Qt.AlignCenter)
        nxt = _btn("forward", "Nächste Seite (Bild↓)")
        nxt.clicked.connect(lambda: self.board.goto(self.board.doc["page"] + 1))
        add = _btn("plus", "Neue Seite")
        add.clicked.connect(self.board.new_page)
        # Papier der Seite: Knopf mit kleiner Vorschau, Menü mit allen Hintergründen (spart Platz in der Leiste)
        self.bg_btn = _btn("grid", "Papier dieser Seite (Kariert, Liniert, Tafel …)")
        self.bg_btn.setIconSize(QSize(30, 20))
        self.bg_btn.setPopupMode(QToolButton.InstantPopup)
        bg_menu = QMenu(self)
        group = QActionGroup(bg_menu)  # genau einer abgehakt – auch wenn man den aktuellen nochmal anklickt
        for key, (label, _d) in BACKGROUNDS.items():
            act = bg_menu.addAction(QIcon(_paper_icon(key)), label, lambda k=key: self.board.set_background(k))
            act.setData(key)
            act.setCheckable(True)
            group.addAction(act)
        self.bg_btn.setMenu(bg_menu)
        for w in (prev, self.page_lab, nxt, add, self.bg_btn):
            lay.addWidget(w)
        row.addWidget(box)
        row.addStretch(1)
        gear = _btn("sliders", "Einstellungen")
        gear.clicked.connect(self.open_settings)
        row.addWidget(gear)
        return row

    def _shortcuts(self) -> None:
        for key, fn in (("P", lambda: self.set_tool("pen")), ("M", lambda: self.set_tool("marker")),
                        ("E", lambda: self.set_tool("eraser")), ("L", lambda: self.set_tool("lasso")),
                        ("F", lambda: self.set_tool("shape")), ("T", lambda: self.set_tool("text")),
                        ("X", lambda: self.set_tool("laser")), ("Ctrl+Z", self.board.undo),
                        ("Ctrl+Y", self.board.redo), ("Ctrl+Shift+Z", self.board.redo),
                        ("Delete", self.board.delete_selection), ("Backspace", self.board.delete_selection),
                        ("+", lambda: self.board.zoom_by(1.25)), ("=", lambda: self.board.zoom_by(1.25)),
                        ("-", lambda: self.board.zoom_by(0.8)), ("0", self.board.fit),
                        ("PgUp", lambda: self.board.goto(self.board.doc["page"] - 1)),
                        ("PgDown", lambda: self.board.goto(self.board.doc["page"] + 1)),
                        ("Ctrl+S", self._save_now)):
            QShortcut(QKeySequence(key), self, activated=fn)

    # ---------------------------------------------------------------- Zustand
    def set_tool(self, tool: str) -> None:
        self.tool = tool
        for k, b in self.tool_btns.items():
            b.setChecked(k == tool)
        b = self.tool_btns["shape"]
        b.setToolTip(f"Form (F): {SHAPE_NAMES[self.shape]} – Pfeil daneben wählt die Form")
        self.update_cursor()
        self._update_width_buttons()
        self._status()

    def update_cursor(self) -> None:
        self.canvas.setCursor({"laser": Qt.PointingHandCursor, "text": Qt.IBeamCursor, "lasso": Qt.CrossCursor,
                               "eraser": Qt.BlankCursor}.get(self.tool, Qt.CrossCursor))

    def set_color(self, color: str) -> None:
        self.color = QColor(color).name()
        if self.tool in ("eraser", "lasso", "laser"):
            if self.tool == "lasso" and self.board.sel:
                self.board.recolor_selection(self.color)  # Auswahl umfärben
            else:
                self.set_tool("pen")
        self._paint_colors()

    def _pick_color(self) -> None:
        c = QColorDialog.getColor(QColor(self.color), self, "Farbe wählen")
        if c.isValid():
            self.set_color(c.name())

    def width_for(self, tool: str) -> float:
        if tool == "marker":
            return self.widths["marker"]
        return self.widths["pen"]

    def _set_width_factor(self, f: float) -> None:
        cfg = self.board.settings()
        key = "marker" if self.tool == "marker" else "pen"
        base = float(cfg["marker_width" if key == "marker" else "width"])
        self.widths[key] = base * f
        self._update_width_buttons()

    def _update_width_buttons(self) -> None:
        cfg = self.board.settings()
        key = "marker" if self.tool == "marker" else "pen"
        base = float(cfg["marker_width" if key == "marker" else "width"])
        for f, b in self.width_btns.items():
            b.setChecked(abs(self.widths[key] - base * f) < 0.01)

    def _paint_colors(self) -> None:
        t = theme.current()
        for b, c in zip(self.color_btns, self.board.settings()["colors"]):
            sel = QColor(c).name() == self.color
            ring = t.accent if sel else t.border
            b.setStyleSheet(f"QToolButton {{ background: {c}; border: {3 if sel else 1}px solid {ring};"
                            f" border-radius: 13px; }}")
            b.setToolTip(c)

    def _on_change(self) -> None:
        b = self.board
        self.zoom_lab.setText(f"{round(b.zoom * 100)} %")
        self.page_lab.setText(f"{b.doc['page'] + 1} / {len(b.doc['pages'])}")
        if getattr(self, "_bg_shown", None) != b.page["bg"]:
            self._bg_shown = b.page["bg"]
            self.bg_btn.setIcon(QIcon(_paper_icon(b.page["bg"])))
            self.bg_btn.setToolTip(f"Papier dieser Seite: {BACKGROUNDS.get(b.page['bg'], ('?',))[0]} – ändern")
            for act in self.bg_btn.menu().actions():
                act.setChecked(act.data() == b.page["bg"])
        self.undo_btn.setEnabled(b.can_undo())
        self.redo_btn.setEnabled(b.can_redo())
        self._paint_colors()
        self._status()
        self._thumbs_soon.start()

    def _status(self) -> None:
        b = self.board
        sel = f" · {len(b.sel)} ausgewählt (Entf löscht, Farbe färbt um, ziehen verschiebt)" if b.sel else ""
        self.status.setText(f"„{b.doc['name']}“ · Seite {b.doc['page'] + 1} von {len(b.doc['pages'])} · "
                            f"Zoom {round(b.zoom * 100)} %{sel}   ·   Strg+Mausrad / zwei Finger: zoomen · "
                            "Mausrad / Leertaste+Ziehen: verschieben · Monitor 2 zeigt genau diese Ansicht")

    def _thumbs(self) -> None:
        b = self.board
        self.pages.blockSignals(True)
        self.pages.clear()
        for i in range(len(b.doc["pages"])):
            img = b.render_page(i, 300)
            item = QListWidgetItem(QIcon(QPixmap.fromImage(img)), f"Seite {i + 1}")
            self.pages.addItem(item)
        self.pages.setCurrentRow(b.doc["page"])
        self.pages.blockSignals(False)

    def _page_clicked(self, row: int) -> None:
        if row >= 0 and row != self.board.doc["page"]:
            self.board.goto(row)

    # ---------------------------------------------------------------- Aktionen
    def add_text_at(self, w: QPointF) -> None:
        text, ok = QInputDialog.getMultiLineText(self, "Text", "Text auf die Tafel schreiben:")
        if ok and text.strip():
            self.board.add_text(w.x(), w.y(), text, self.color)

    def context_menu(self, at) -> None:
        b = self.board
        m = QMenu(self)
        m.addAction("Rückgängig", b.undo).setEnabled(b.can_undo())
        m.addAction("Wiederholen", b.redo).setEnabled(b.can_redo())
        if b.sel:
            m.addSeparator()
            m.addAction(f"Auswahl löschen ({len(b.sel)})", b.delete_selection)
            m.addAction("Auswahl in aktueller Farbe", lambda: b.recolor_selection(self.color))
        m.addSeparator()
        m.addAction("Ganze Seite zeigen", b.fit)
        m.addAction("Neue Seite", b.new_page)
        m.addAction("Seite leeren", lambda: self._confirm("Diese Seite leeren?", b.clear))
        m.addAction("Seite löschen", lambda: self._confirm("Diese Seite löschen?", b.delete_page))
        m.exec(at)

    def _confirm(self, text: str, fn) -> None:
        if QMessageBox.question(self, "Whiteboard", text) == QMessageBox.Yes:
            fn()

    def _fill_board_menu(self) -> None:
        m = self.menu_btn.menu()
        m.clear()
        m.addAction("Neue Tafel", self._new_board)
        opened = m.addMenu("Öffnen")
        for name in self.board.boards()[:30]:
            act = opened.addAction(name, lambda n=name: self.board.load(n))
            act.setCheckable(True)
            act.setChecked(name == self.board.doc["name"])
        m.addAction("Umbenennen …", self._rename)
        m.addSeparator()
        m.addAction("Seite als Bild (PNG) speichern …", self._export_png)
        m.addAction("Ganze Tafel als PDF speichern …", self._export_pdf)
        m.addSeparator()
        m.addAction("Einstellungen …", self.open_settings)

    def _new_board(self) -> None:
        name, ok = QInputDialog.getText(self, "Neue Tafel", "Name:", text="")
        if ok:
            self.board.new_board(name.strip())

    def _rename(self) -> None:
        name, ok = QInputDialog.getText(self, "Umbenennen", "Neuer Name:", text=self.board.doc["name"])
        if ok and name.strip():
            self.board.rename(name)

    def _export_png(self) -> None:
        from ..photowall import default_folder

        default = str(default_folder().parent / f"{self.board.doc['name']} – Seite {self.board.doc['page'] + 1}.png")
        path, _f = QFileDialog.getSaveFileName(self, "Seite speichern", default, "PNG-Bild (*.png)")
        if path:
            ok = self.board.export_png(path)
            self.status.setText(f"Gespeichert: {path}" if ok else "Speichern ging nicht.")

    def _export_pdf(self) -> None:
        from ..photowall import default_folder

        default = str(default_folder().parent / f"{self.board.doc['name']}.pdf")
        path, _f = QFileDialog.getSaveFileName(self, "Tafel als PDF", default, "PDF (*.pdf)")
        if path:
            ok = self.board.export_pdf(path)
            self.status.setText(f"Gespeichert: {path}" if ok else "Speichern ging nicht.")

    def _save_now(self) -> None:
        path = self.board.save()
        self.status.setText(f"Gespeichert: {path}")

    def open_settings(self) -> None:
        from .board_settings import BoardSettingsDialog

        BoardSettingsDialog(self.board, self).exec()
        cfg = self.board.settings()
        self.widths = {"pen": float(cfg["width"]), "marker": float(cfg["marker_width"])}
        self._update_width_buttons()
        self._on_change()

    def showEvent(self, e):
        super().showEvent(e)
        self.canvas.setFocus()

    def closeEvent(self, e):
        if self.board._dirty:
            self.board.save()
        super().closeEvent(e)


__all__ = ["BoardWindow", "SHAPES"]
