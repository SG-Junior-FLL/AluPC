"""„Zeigen & Zeichnen“: Fenster auf Monitor 1 mit Live-Bild von Monitor 2.

In der Vorschau zeigt man mit dem Laserpointer oder kritzelt mit Stift/Textmarker – alles erscheint
sofort auf Monitor 2 (im durchsichtigen Fenster über allem, siehe laser.py).
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QKeySequence, QPainter, QPen, QShortcut
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QSlider,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..laser import paint_dot, paint_strokes
from ..sources import ScreenSource, fit_rect
from . import icons, theme
from .util import ColorButton
from .widgets import button

COLORS = ["#ef4444", "#f59e0b", "#facc15", "#22c55e", "#3b82f6", "#a855f7", "#ffffff", "#111827"]
TOOLS = [("laser", "laser", "Laserpointer (L)"), ("pen", "edit", "Stift (S)"),
         ("marker", "highlighter", "Textmarker (M)"), ("eraser", "eraser", "Radierer (R)")]
ERASER_RADIUS = 0.03  # relativ zur Höhe von Monitor 2


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
            paint_dot(p, pt, r, QColor(c.config["laser"].get("color", "#ff2a2a")))
        if self.eraser_pos is not None:
            p.setRenderHint(QPainter.Antialiasing)
            p.setPen(QPen(QColor(t.text), 1.5, Qt.DashLine))
            p.setBrush(Qt.NoBrush)
            r = ERASER_RADIUS * a.height()
            p.drawEllipse(self.eraser_pos, r, r)
        p.setPen(QPen(QColor(t.accent), 2))
        p.setBrush(Qt.NoBrush)
        p.drawRect(a.adjusted(-1, -1, 1, 1))
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
        bar.setSpacing(6)
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
            bar.addWidget(b)
        bar.addSpacing(12)

        # Farben
        self.swatches = {}
        for color in COLORS:
            s = QToolButton()
            s.setCheckable(True)
            s.setFixedSize(28, 28)
            s.setToolTip(color)
            s.clicked.connect(lambda _=False, col=color: self.set_color(col))
            self.swatches[color] = s
            bar.addWidget(s)
        self.custom_color = ColorButton(self.color)
        self.custom_color.setToolTip("Eigene Farbe")
        self.custom_color.changed.connect(self.set_color)
        bar.addWidget(self.custom_color)
        bar.addSpacing(12)
        bar.addWidget(QLabel("Stärke:"))
        self.width_slider = QSlider(Qt.Horizontal)
        self.width_slider.setRange(1, 20)
        self.width_slider.setValue(int(controller.config["draw"].get("width", 4)))
        self.width_slider.setFixedWidth(110)
        self.width_slider.valueChanged.connect(self._save)
        bar.addWidget(self.width_slider)
        bar.addStretch(1)
        undo = button("Rückgängig", "undo")
        undo.setToolTip("Letzten Strich entfernen (Strg+Z)")
        undo.clicked.connect(controller.laser.undo)
        clear = button("Alles löschen", "trash", danger=True)
        clear.setToolTip("Alle Zeichnungen auf Monitor 2 entfernen (Entf)")
        clear.clicked.connect(controller.laser.clear_strokes)
        bar.addWidget(undo)
        bar.addWidget(clear)

        self.canvas = PresenterCanvas(self)
        self.clear_on_change = QCheckBox("Zeichnungen löschen, wenn auf Monitor 2 etwas anderes kommt")
        self.clear_on_change.setChecked(bool(controller.config["draw"].get("clear_on_change", True)))
        self.clear_on_change.toggled.connect(self._save)
        self.clear_on_close = QCheckBox("… und beim Schließen dieses Fensters")
        self.clear_on_close.setChecked(bool(controller.config["draw"].get("clear_on_close", True)))
        self.clear_on_close.toggled.connect(self._save)
        hint = QLabel("Zeichnen: Maustaste gedrückt halten · Tasten L S M R: Werkzeug · Strg+Z: zurück")
        hint.setObjectName("Muted")
        low = QHBoxLayout()
        low.addWidget(self.clear_on_change)
        low.addWidget(self.clear_on_close)
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
            f"QToolButton#ToolBtn {{ padding: 6px 10px; border-radius: 8px; border: 1px solid {t.border}; }}"
            f"QToolButton#ToolBtn:checked {{ background: {t.accent}; color: #ffffff; border-color: {t.accent}; }}")

        for keys, slot in (("Ctrl+Z", controller.laser.undo), ("Del", controller.laser.clear_strokes),
                           ("L", lambda: self.set_tool("laser")), ("S", lambda: self.set_tool("pen")),
                           ("M", lambda: self.set_tool("marker")), ("R", lambda: self.set_tool("eraser")),
                           ("Esc", self.close)):
            QShortcut(QKeySequence(keys), self, activated=slot)

        self.timer = QTimer(self, interval=100)  # Vorschau 10 Bilder/s
        self.timer.timeout.connect(self.refresh)
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
        for col, s in self.swatches.items():
            border = theme.current().accent if col == color else theme.current().border
            s.setChecked(col == color)
            s.setStyleSheet(f"QToolButton {{ background: {col}; border: 3px solid {border}; border-radius: 14px; }}")
        self._save()

    def width_value(self) -> float:
        return self.width_slider.value() / 1000  # relativ zur Höhe von Monitor 2

    def _save(self, *_):
        if not hasattr(self, "clear_on_close"):
            return
        self.controller.config["draw"] = {
            "tool": self.tool, "color": self.color, "width": self.width_slider.value(),
            "clear_on_change": self.clear_on_change.isChecked(), "clear_on_close": self.clear_on_close.isChecked()}

    # ------------------------------------------------------------ Vorschau
    def showEvent(self, e):
        self.controller.laser.set_remote(True)
        self.timer.start()
        self.refresh()
        super().showEvent(e)

    def hideEvent(self, e):
        self.timer.stop()
        self._stop_live()
        self.controller.laser.remote_point(None)
        if self.clear_on_close.isChecked():
            self.controller.laser.clear_strokes()
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
            self.canvas.image = out.grab().toImage()
        else:
            screen = c.output_screen()
            if screen is None:
                self._stop_live()
                self.canvas.image = None
            else:
                # „Erweitern“: Monitor 2 live aufnehmen
                if self.live_capture is None:
                    self.live_capture = ScreenSource({"screen_name": screen.name()})
                self.canvas.image = self.live_capture.image()
        self.canvas.update()
