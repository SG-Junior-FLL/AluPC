"""Lautstärke der Medien auf Monitor 2 live einstellen (Video, Website – auch in Szenen)."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSlider, QToolButton, QWidget

from . import icons, theme


class VolumeBox(QWidget):
    """Stumm-Knopf + Regler; nur sichtbar, wenn auf Monitor 2 etwas mit Ton läuft."""

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.mute_btn = QToolButton()
        self.mute_btn.setCheckable(True)
        self.mute_btn.setAutoRaise(True)
        self.mute_btn.setIconSize(QSize(20, 20))
        self.mute_btn.setToolTip("Ton der Medien auf Monitor 2 aus/an")
        self.mute_btn.toggled.connect(lambda on: self.controller.set_media_volume(muted=on))
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.setFixedWidth(120)
        self.slider.setToolTip("Lautstärke der Medien auf Monitor 2")
        self.label = QLabel()
        self.label.setObjectName("Muted")
        self.label.setMinimumWidth(40)
        # Beim Ziehen nicht bei jedem Schritt alles neu setzen
        self._apply = QTimer(self, singleShot=True, interval=80)
        self._apply.timeout.connect(lambda: self.controller.set_media_volume(volume=self.slider.value()))
        self.slider.valueChanged.connect(self._moved)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        lay.addWidget(self.mute_btn)
        lay.addWidget(self.slider)
        lay.addWidget(self.label)
        self.sync()

    def _moved(self, value):
        self.label.setText(f"{value} %")
        self._apply.start()

    def sync(self):
        state = self.controller.media_state()
        self.setVisible(state is not None)
        if state is None:
            return
        for w in (self.slider, self.mute_btn):
            w.blockSignals(True)
        if not self.slider.isSliderDown() and not self._apply.isActive():
            self.slider.setValue(state["volume"])
        self.mute_btn.setChecked(state["muted"])
        for w in (self.slider, self.mute_btn):
            w.blockSignals(False)
        self.label.setText(f"{self.slider.value()} %")
        self.slider.setEnabled(not state["muted"])
        t = theme.current()
        self.mute_btn.setIcon(icons.icon("mute" if state["muted"] else "sound",
                                         t.danger if state["muted"] else t.text, 20))
