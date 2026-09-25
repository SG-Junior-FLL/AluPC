"""Kamera-Leiste im Hauptfenster: Zeigt Monitor 2 eine Kamera (auch in einer eigenen Szene), erscheint
eine Leiste mit Zoom, Ausschnitt verschieben, Spiegeln, Drehen und Helligkeit."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QSlider, QToolButton, QWidget

from ..sources import MAX_ZOOM, pan_to_source
from . import icons, theme

PAN_STEP = 0.25  # Anteil des sichtbaren Ausschnitts pro Klick


class CameraBar(QWidget):
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.setObjectName("Card")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.cameras = []
        self.buttons: list[QToolButton] = []

        def tool(icon_name, tip, slot, text="", checkable=False):
            b = QToolButton()
            b.setAutoRaise(True)
            b.setIconSize(QSize(20, 20))
            b.setToolTip(tip)
            b.setProperty("icon_name", icon_name)
            b.setCheckable(checkable)
            if text:
                b.setText(text)
                b.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            b.clicked.connect(slot)
            self.buttons.append(b)
            return b

        self.icon_label = QLabel()
        self.zoom_out = tool("zoom_out", "Herauszoomen", lambda: self._zoom_by(0.8))
        self.zoom = QSlider(Qt.Horizontal)
        self.zoom.setRange(100, int(MAX_ZOOM * 100))
        self.zoom.setSingleStep(10)
        self.zoom.setPageStep(50)
        self.zoom.setMinimumWidth(120)
        self.zoom.setToolTip("Zoom (1× bis 5×)")
        self.zoom.valueChanged.connect(lambda v: self._set(zoom=v / 100))
        self.zoom_in = tool("zoom_in", "Hineinzoomen", lambda: self._zoom_by(1.25))
        self.zoom_label = QLabel("1,0×")
        self.zoom_label.setMinimumWidth(40)
        self.left = tool("back", "Ausschnitt nach links", lambda: self._pan(-1, 0))
        self.up = tool("up", "Ausschnitt nach oben", lambda: self._pan(0, -1))
        self.down = tool("down", "Ausschnitt nach unten", lambda: self._pan(0, 1))
        self.right = tool("forward", "Ausschnitt nach rechts", lambda: self._pan(1, 0))
        self.flip = tool("flip", "Spiegeln (links ↔ rechts)", self._flip, checkable=True)
        self.rotate = tool("rotate", "Um 90° drehen", self._rotate)
        self.light_icon = QLabel()
        self.light = QSlider(Qt.Horizontal)
        self.light.setRange(-20, 20)
        self.light.setMaximumWidth(90)
        self.light.setToolTip("Helligkeit (Belichtung der Kamera)")
        self.light.valueChanged.connect(lambda v: self._set(exposure=v / 10))
        self.reset = tool("refresh", "Zoom, Ausschnitt, Spiegeln, Drehen und Helligkeit zurücksetzen",
                          self._reset, "Zurücksetzen")
        self.which = QComboBox()
        self.which.setToolTip("Welche Kamera einstellen? (Szene mit mehreren Kameras)")
        self.which.currentIndexChanged.connect(lambda _i: self.refresh())
        self.title = QLabel()
        self.title.setObjectName("Muted")
        self.title.setMaximumWidth(200)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 6, 16, 6)
        lay.setSpacing(6)
        lay.addWidget(self.icon_label)
        for w in (self.zoom_out, self.zoom, self.zoom_in, self.zoom_label):
            lay.addWidget(w)
        lay.addSpacing(8)
        for w in (self.left, self.up, self.down, self.right):
            lay.addWidget(w)
        lay.addSpacing(8)
        for w in (self.flip, self.rotate, self.light_icon, self.light, self.reset):
            lay.addWidget(w)
        lay.addStretch(1)
        lay.addWidget(self.which)
        lay.addWidget(self.title)
        self.apply_theme()
        self.sync()

    def apply_theme(self):
        t = theme.current()
        for b in self.buttons:
            b.setIcon(icons.icon(b.property("icon_name"), t.text, 22))
        self.icon_label.setPixmap(icons.pixmap("camera", t.accent, 20))
        self.light_icon.setPixmap(icons.pixmap("sun", t.muted, 18))

    # ------------------------------------------------------------ Welche Kameras laufen?
    def sync(self):
        self.cameras = self.controller.cameras_on_output()
        self.setVisible(bool(self.cameras))
        self.which.blockSignals(True)
        self.which.clear()
        for i, cam in enumerate(self.cameras, 1):
            self.which.addItem(f"Kamera {i}: {cam.name}")
        self.which.blockSignals(False)
        self.which.setVisible(len(self.cameras) > 1)
        self.title.setVisible(len(self.cameras) == 1)
        if len(self.cameras) == 1:
            self.title.setText(self.cameras[0].name)
        self.refresh()

    def current(self):
        i = max(0, self.which.currentIndex())
        return self.cameras[i] if i < len(self.cameras) else None

    def refresh(self):
        cam = self.current()
        if cam is None:
            return
        try:
            o = cam.options()
            exposure = cam.supports_exposure()
            hw = cam.hardware_zoom_max()
        except RuntimeError:  # Kamera wurde gerade beendet
            return
        for w, value in ((self.zoom, round(o["zoom"] * 100)), (self.light, round(o["exposure"] * 10))):
            w.blockSignals(True)
            w.setValue(value)
            w.blockSignals(False)
        self.zoom_label.setText(f"{o['zoom']:.1f}×".replace(".", ","))
        self.zoom_label.setToolTip("Optischer Zoom der Kamera bis {:.1f}×, darüber digital".format(hw)
                                   if hw > 1.01 else "Digitaler Zoom (Ausschnitt des Kamerabilds)")
        zoomed = o["zoom"] > 1.001
        for b in (self.left, self.up, self.down, self.right):
            b.setEnabled(zoomed)
        self.flip.setChecked(bool(o["mirror"]))
        self.light.setVisible(exposure)
        self.light_icon.setVisible(exposure)

    # ------------------------------------------------------------ Bedienung
    def _set(self, **changes):
        cam = self.current()
        if cam is not None:
            self.controller.set_camera_option(cam.device_id, **changes)
            self.refresh()

    def _zoom_by(self, factor: float):
        cam = self.current()
        if cam is not None:
            self._set(zoom=cam.options()["zoom"] * factor)

    def _pan(self, dx: int, dy: int):
        cam = self.current()
        if cam is None:
            return
        o = cam.options()
        sx, sy = pan_to_source(dx, dy, o["rotate"], o["mirror"])
        step = PAN_STEP / o["zoom"]
        self._set(x=o["x"] + sx * step, y=o["y"] + sy * step)

    def _flip(self):
        cam = self.current()
        if cam is not None:
            self._set(mirror=not cam.options()["mirror"])

    def _rotate(self):
        cam = self.current()
        if cam is not None:
            self._set(rotate=(int(cam.options()["rotate"]) + 90) % 360)

    def _reset(self):
        cam = self.current()
        if cam is not None:
            self.controller.reset_camera(cam.device_id)
            self.refresh()
