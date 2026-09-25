"""„Zeigen & Zeichnen“: Fenster auf Monitor 1 mit Live-Bild von Monitor 2.

In der Vorschau zeigt man mit dem Laserpointer oder kritzelt mit Stift/Textmarker – alles erscheint
sofort auf Monitor 2 (im durchsichtigen Fenster über allem, siehe laser.py).
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QKeySequence, QPainter, QPainterPath, QPen, QShortcut
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QSlider,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..laser import paint_dot, paint_strokes
from ..output_window import grab_scaled
from ..sources import ScreenSource, fit_rect
from . import icons, theme
from .widgets import button

COLORS = ["#ef4444", "#f59e0b", "#facc15", "#22c55e", "#3b82f6", "#a855f7", "#ffffff", "#111827"]
TOOLS = [("laser", "laser", "Laser (L)"), ("pen", "edit", "Stift (S)"),
         ("marker", "highlighter", "Marker (M)"), ("eraser", "eraser", "Radierer (R)")]
FPS_CHOICES = [10, 15, 20, 30, 45, 60]
ERASER_RADIUS = 0.03  # relativ zur Höhe von Monitor 2


def _group():
    """Abgerundete Gruppe in der Werkzeugleiste."""
    box = QFrame()
    box.setObjectName("Group")
    lay = QHBoxLayout(box)
    lay.setContentsMargins(6, 4, 6, 4)
    lay.setSpacing(4)
    return box, lay


def _ring(color: str):
    """Leuchtender Ring um die gewählte Farbe."""
    from PySide6.QtWidgets import QGraphicsDropShadowEffect

    effect = QGraphicsDropShadowEffect()
    effect.setColor(QColor(color))
    effect.setBlurRadius(10)
    effect.setOffset(0, 0)
    return effect


class PresenterCanvas(QWidget):
    """Vorschau von Monitor 2 – Maus hier = Laser/Stift auf Monitor 2."""

    def __init__(self, window):
        super().__init__(window)
        self.win = window
        self.image = None
        self.setMouseTracking(True)
        self.setMinimumSize(480, 270)
        self.setCursor(Qt.CrossCursor)
        self._drawing = False
        self.eraser_pos: QPointF | None = None

    # Seitenverhältnis wie Monitor 2, mittig im Fenster
    def area(self) -> QRectF:
        screen = self.win.controller.output_screen()
        if screen is not None:
            w, h = screen.geometry().width(), screen.geometry().height()
        elif self.image is not None:
            w, h = self.image.width(), self.image.height()
        else:
            w, h = 16, 9
        return fit_rect(w, h, self.width(), self.height(), "contain")

    def to_norm(self, pos: QPointF) -> QPointF | None:
        a = self.area()
        if a.width() <= 0 or a.height() <= 0:
            return None
        x, y = (pos.x() - a.x()) / a.width(), (pos.y() - a.y()) / a.height()
        if not (0 <= x <= 1 and 0 <= y <= 1):
            return None
        return QPointF(x, y)

    # ------------------------------------------------------------ Maus
    def mousePressEvent(self, e):
        norm = self.to_norm(e.position())
        if e.button() != Qt.LeftButton or norm is None:
            return
        tool = self.win.tool
        laser = self.win.controller.laser
        if tool in ("pen", "marker"):
            self._drawing = True
            laser.begin_stroke(tool, self.win.color, self.win.width_value(), norm)
        elif tool == "eraser":
            self._drawing = True
            laser.erase_at(norm, ERASER_RADIUS)
        self.update()

    def mouseMoveEvent(self, e):
        norm = self.to_norm(e.position())
        tool = self.win.tool
        laser = self.win.controller.laser
        self.eraser_pos = e.position() if tool == "eraser" else None
        if tool == "laser":
            laser.remote_point(norm)
        elif self._drawing and norm is not None:
            if tool == "eraser":
                laser.erase_at(norm, ERASER_RADIUS)
            else:
                laser.extend_stroke(norm)
        self.update()

    def mouseReleaseEvent(self, _e):
        if self._drawing and self.win.tool in ("pen", "marker"):
            self.win.controller.laser.end_stroke()
        self._drawing = False

    def leaveEvent(self, _e):
        self.eraser_pos = None
        if self.win.tool == "laser":
            self.win.controller.laser.remote_point(None)
        self.update()

    # ------------------------------------------------------------ Zeichnen
    def paintEvent(self, _e):
        t = theme.current()
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(t.bg))
        a = self.area()
        c = self.win.controller
        p.setRenderHint(QPainter.Antialiasing)
        # weicher Schatten unter der Vorschau
        for i, alpha in ((10, 18), (6, 30), (3, 45)):
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(0, 0, 0, alpha))
            p.drawRoundedRect(a.adjusted(-i, -i + 3, i, i + 3), 14 + i, 14 + i)
        clip = QPainterPath()
        clip.addRoundedRect(a, 12, 12)
        p.setClipPath(clip)
        p.fillRect(a, Qt.black)
        if self.image is not None and not self.image.isNull():
            p.setRenderHint(QPainter.SmoothPixmapTransform)
            p.drawImage(a, self.image)
        laser = c.laser
        if laser.strokes:
            paint_strokes(p, laser.strokes, a)
        if laser.point is not None and laser.width() > 0 and laser.height() > 0:
            pt = QPointF(a.x() + laser.point.x() / laser.width() * a.width(),
                         a.y() + laser.point.y() / laser.height() * a.height())
            r = max(4.0, laser.radius() * a.height() / max(1, laser.height()))
            paint_dot(p, pt, r, QColor(self.win.color))
        if self.eraser_pos is not None:
            p.setRenderHint(QPainter.Antialiasing)
            p.setPen(QPen(QColor(t.text), 1.5, Qt.DashLine))
            p.setBrush(Qt.NoBrush)
            r = ERASER_RADIUS * a.height()
            p.drawEllipse(self.eraser_pos, r, r)
        p.setClipping(False)
        p.setPen(QPen(QColor(t.accent), 2))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(a.adjusted(-1, -1, 1, 1), 13, 13)
        # Etikett „LIVE · MONITOR 2“ (Standbild/Schwarz sichtbar machen)
        label, color = ("LIVE · MONITOR 2", t.success)
        if c.privacy:
            label, color = ("SCHWARZ", "#64748b")
        elif c.frozen:
            label, color = ("STANDBILD", "#0ea5e9")
        f = p.font()
        f.setBold(True)
        f.setPixelSize(12)
        p.setFont(f)
        w = p.fontMetrics().horizontalAdvance(label) + 26
        pill = QRectF(a.x() + 12, a.y() + 12, w, 24)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 150))
        p.drawRoundedRect(pill, 12, 12)
        p.setBrush(QColor(color))
        p.drawEllipse(QPointF(pill.x() + 11, pill.center().y()), 4, 4)
        p.setPen(QColor("#ffffff"))
        p.drawText(pill.adjusted(18, 0, 0, 0), Qt.AlignVCenter | Qt.AlignLeft, label)
        if c.privacy:
            p.setPen(QColor("#ffffff"))
            p.drawText(a, Qt.AlignCenter, "SCHWARZ ist an – auf Monitor 2 ist gerade nichts zu sehen")
        p.end()


class PresenterWindow(QWidget):
    TITLE = "AluPC – Zeigen & Zeichnen"

    def __init__(self, controller, parent=None):
        super().__init__(parent, Qt.Window)
        self.controller = controller
        self.setWindowTitle(self.TITLE)
        self.resize(1180, 760)
        self.tool = "laser"
        self.color = controller.config["draw"].get("color", COLORS[0])
        self.live_capture: ScreenSource | None = None
        t = theme.current()

        # Werkzeuge
        self.tool_group = QButtonGroup(self)
        self.tool_group.setExclusive(True)
        self.tool_buttons = {}
        bar = QHBoxLayout()
        bar.setSpacing(10)
        tools_box, tools = _group()
        colors_box, colors = _group()
        size_box, size = _group()
        actions_box, actions = _group()
        for key, icon_name, tip in TOOLS:
            b = QToolButton()
            b.setObjectName("ToolBtn")
            b.setCheckable(True)
            b.setToolTip(tip)
            b.setIcon(icons.icon(icon_name, t.text, 22))
            b.setIconSize(QSize(22, 22))
            b.setText(tip.split(" (")[0])
            b.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            b.clicked.connect(lambda _=False, k=key: self.set_tool(k))
            self.tool_group.addButton(b)
            self.tool_buttons[key] = b
            tools.addWidget(b)

        # Farben
        self.swatches = {}
        for color in COLORS:
            s = QToolButton()
            s.setCheckable(True)
            s.setFixedSize(26, 26)
            s.setToolTip(color)
            s.clicked.connect(lambda _=False, col=color: self.set_color(col))
            self.swatches[color] = s
            colors.addWidget(s)
        self.custom_color = QToolButton()
        self.custom_color.setObjectName("ToolBtn")
        self.custom_color.setCheckable(True)
        self.custom_color.setIcon(icons.icon("palette", t.text, 20))
        self.custom_color.setToolTip("Eigene Farbe wählen …")
        self.custom_color.clicked.connect(self._pick_color)
        colors.addWidget(self.custom_color)
        size.addWidget(QLabel("Stärke"))
        self.width_slider = QSlider(Qt.Horizontal)
        self.width_slider.setRange(1, 20)
        self.width_slider.setValue(int(controller.config["draw"].get("width", 4)))
        self.width_slider.setFixedWidth(90)
        self.width_slider.valueChanged.connect(self._save)
        size.addWidget(self.width_slider)
        size.addSpacing(6)
        self.fps_combo = QComboBox()
        for fps in FPS_CHOICES:
            self.fps_combo.addItem(f"{fps} fps", fps)
        self.fps_combo.setToolTip("Wie oft die Vorschau hier aktualisiert wird (Monitor 2 selbst läuft immer "
                                  "flüssig). Mehr Bilder/s = flüssiger, braucht aber mehr Rechenleistung.")
        wanted = int(controller.config["draw"].get("fps", 30))
        self.fps_combo.setCurrentIndex(max(0, self.fps_combo.findData(wanted)))
        self.fps_combo.currentIndexChanged.connect(self._fps_changed)
        self.fps_label = QLabel("")
        self.fps_label.setObjectName("Muted")
        self.fps_label.setMinimumWidth(30)
        size.addWidget(self.fps_combo)
        size.addWidget(self.fps_label)
        undo = button("", "undo")
        undo.setToolTip("Letzten Strich entfernen (Strg+Z)")
        undo.clicked.connect(controller.laser.undo)
        clear = button("Alles löschen", "trash", danger=True)
        self.clear_btn = clear
        clear.setToolTip("Alle Zeichnungen auf Monitor 2 entfernen (Entf)")
        clear.clicked.connect(controller.laser.clear_strokes)
        actions.addWidget(undo)
        actions.addWidget(clear)
        for box in (tools_box, colors_box, size_box):
            bar.addWidget(box)
        bar.addStretch(1)
        bar.addWidget(actions_box)

        self.canvas = PresenterCanvas(self)
        hint = QLabel("L S M R: Werkzeug · Strg+Z: zurück · Entf: alles weg")
        hint.setObjectName("Muted")
        low = QHBoxLayout()
        keep = QLabel("Zeichnungen bleiben stehen, bis du sie löschst oder die Szene wechselt.")
        keep.setObjectName("Muted")
        low.addWidget(keep)
        low.addStretch(1)
        low.addWidget(hint)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(10)
        lay.addLayout(bar)
        lay.addWidget(self.canvas, 1)
        lay.addLayout(low)
        self.setStyleSheet(
            f"PresenterWindow {{ background: {t.bg}; }}"
            f"QFrame#Group {{ background: {t.surface}; border: 1px solid {t.border}; border-radius: 12px; }}"
            f"QFrame#Group QLabel {{ background: transparent; color: {t.muted}; }}"
            f"QToolButton#ToolBtn {{ padding: 6px 12px; border-radius: 8px; border: none; background: transparent; }}"
            f"QToolButton#ToolBtn:hover {{ background: {t.surface2}; }}"
            f"QToolButton#ToolBtn:checked {{ background: {t.accent}; color: #ffffff; }}")

        for keys, slot in (("Ctrl+Z", controller.laser.undo), ("Del", controller.laser.clear_strokes),
                           ("L", lambda: self.set_tool("laser")), ("S", lambda: self.set_tool("pen")),
                           ("M", lambda: self.set_tool("marker")), ("R", lambda: self.set_tool("eraser")),
                           ("Esc", self.close)):
            QShortcut(QKeySequence(keys), self, activated=slot)

        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.PreciseTimer)
        self.timer.timeout.connect(self.refresh)
        self._frames = 0
        self._measure = QTimer(self, interval=1000)
        self._measure.timeout.connect(self._show_rate)
        self._apply_fps()
        # Schmales Fenster (z. B. Laptop): Werkzeuge nur als Symbole – passt sich beim Ziehen an
        self._bar = bar
        self._full_width = None
        self._compact = False
        lay.setSizeConstraint(QLayout.SetNoConstraint)
        self.setMinimumSize(760, 480)
        self.set_tool(controller.config["draw"].get("tool", "laser"))
        self.set_color(self.color)

    # ------------------------------------------------------------ Werkzeug/Farbe
    def set_tool(self, tool: str) -> None:
        if tool not in self.tool_buttons:
            tool = "laser"
        if self.tool == "laser" and tool != "laser":
            self.controller.laser.remote_point(None)
        self.tool = tool
        self.tool_buttons[tool].setChecked(True)
        for key, b in self.tool_buttons.items():  # Symbol weiß auf dem gewählten Knopf
            icon_name = next(i for k, i, _t in TOOLS if k == key)
            b.setIcon(icons.icon(icon_name, "#ffffff" if key == tool else theme.current().text, 22))
        self.canvas.setCursor(Qt.BlankCursor if tool == "laser" else Qt.CrossCursor)
        self._save()

    def set_color(self, color: str) -> None:
        self.color = color
        custom = color not in COLORS
        self.custom_color.setIcon(icons.icon("palette", color if custom else theme.current().text, 20))
        self.custom_color.setChecked(custom)
        for col, s in self.swatches.items():
            t = theme.current()
            s.setChecked(col == color)
            if col == color:  # gewählt: heller Innenring + Akzent-Außenring
                s.setStyleSheet(f"QToolButton {{ background: {col}; border: 3px solid {t.text}; "
                                f"border-radius: 13px; }}")
                s.setGraphicsEffect(_ring(t.accent))
            else:
                s.setStyleSheet(f"QToolButton {{ background: {col}; border: 1px solid {t.border}; "
                                f"border-radius: 13px; }} QToolButton:hover {{ border: 2px solid {t.text}; }}")
                s.setGraphicsEffect(None)
        self._save()

    def fps(self) -> int:
        return int(self.fps_combo.currentData() or 30)

    def _apply_fps(self):
        self.timer.setInterval(max(1, round(1000 / self.fps())))

    def _fps_changed(self, *_):
        self._apply_fps()
        self._stop_live()  # Aufnahme mit neuer Rate neu starten
        self._save()

    def _show_rate(self):
        # ehrlich anzeigen, was wirklich erreicht wird (langsamer Rechner → weniger als eingestellt)
        self.fps_label.setText(f"≈{self._frames}")
        self.fps_label.setToolTip(f"Erreicht: {self._frames} Bilder/s (eingestellt: {self.fps()})")
        self._frames = 0

    def resizeEvent(self, e):
        if self._full_width is None:
            self.set_compact(False)
            self._full_width = self._bar.sizeHint().width() + 28
        compact = self.width() < self._full_width
        if compact != self._compact:
            self.set_compact(compact)
        super().resizeEvent(e)

    def set_compact(self, compact: bool) -> None:
        self._compact = compact
        style = Qt.ToolButtonIconOnly if compact else Qt.ToolButtonTextBesideIcon
        for b in self.tool_buttons.values():
            b.setToolButtonStyle(style)
        self.clear_btn.setText("" if compact else "Alles löschen")

    def _pick_color(self):
        from PySide6.QtWidgets import QColorDialog

        color = QColorDialog.getColor(QColor(self.color), self, "Eigene Farbe")
        self.set_color(color.name() if color.isValid() else self.color)

    def width_value(self) -> float:
        return self.width_slider.value() / 1000  # relativ zur Höhe von Monitor 2

    def _save(self, *_):
        if not hasattr(self, "fps_combo"):
            return
        self.controller.config["draw"] = {**self.controller.config["draw"],  # gespeicherte Zeichnungen behalten
            "tool": self.tool, "color": self.color, "width": self.width_slider.value(),
            "fps": self.fps()}

    # ------------------------------------------------------------ Vorschau
    def showEvent(self, e):
        self.controller.laser.set_remote(True)
        self.timer.start()
        self._frames = 0
        self._measure.start()
        self.refresh()
        super().showEvent(e)

    def hideEvent(self, e):
        self.timer.stop()
        self._measure.stop()
        self._stop_live()
        self.controller.laser.remote_point(None)
        self.controller.laser.set_remote(False)
        super().hideEvent(e)

    def _stop_live(self):
        if self.live_capture is not None:
            self.live_capture.stop()
            self.live_capture.deleteLater()
            self.live_capture = None

    def refresh(self):
        c = self.controller
        out = c.output
        if out.isVisible():
            # AluPC zeigt selbst etwas → Ausgabefenster abfotografieren (ohne Aufnahme-Freigabe)
            self._stop_live()
            # direkt in Vorschaugröße zeichnen (schneller als volle Auflösung abfotografieren)
            area = self.canvas.area()
            dpr = self.canvas.devicePixelRatioF()
            self.canvas.image = grab_scaled(out, area.size() * dpr)
        else:
            screen = c.output_screen()
            if screen is None:
                self._stop_live()
                self.canvas.image = None
            else:
                # „Erweitern“: Monitor 2 live aufnehmen
                if self.live_capture is None:
                    self.live_capture = ScreenSource({"screen_name": screen.name(), "fps": self.fps()})
                self.canvas.image = self.live_capture.image()
        self._frames += 1
        self.canvas.update()
