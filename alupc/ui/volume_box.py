"""Regler-Pult auf der Startseite: Lautstärke des PCs und der Medien auf Monitor 2 als Mischpult-Fader."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtWidgets import QHBoxLayout, QLabel, QToolButton, QVBoxLayout, QWidget

from . import icons, theme
from .widgets import Fader


class VolumeBox(QWidget):
    """Kanal „Medien“: Fader + Stumm-Knopf; nur sichtbar, wenn auf Monitor 2 etwas mit Ton läuft."""

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.mute_btn = QToolButton()
        self.mute_btn.setCheckable(True)
        self.mute_btn.setAutoRaise(True)
        self.mute_btn.setIconSize(QSize(20, 20))
        self.mute_btn.setToolTip("Ton der Medien auf dem Bildschirm aus/an")
        self.mute_btn.toggled.connect(lambda on: self.controller.set_media_volume(muted=on))
        self.slider = Fader("Medien")
        self.slider.setToolTip("Lautstärke der Medien auf dem Bildschirm")
        self.label = QLabel()  # Wert steht im Fader selbst; bleibt für Bedienhilfen
        self.label.hide()
        # Beim Ziehen nicht bei jedem Schritt alles neu setzen
        self._apply = QTimer(self, singleShot=True, interval=80)
        self._apply.timeout.connect(lambda: self.controller.set_media_volume(volume=self.slider.value()))
        self.slider.valueChanged.connect(self._moved)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        lay.addWidget(self.slider, 0, Qt.AlignHCenter)
        lay.addWidget(self.mute_btn, 0, Qt.AlignHCenter)
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


class PcVolumeFader(QWidget):
    """Kanal „PC“: Gesamtlautstärke des Computers (wie der Lautstärkeregler des Systems)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.fader = Fader("PC")
        self.fader.setToolTip("Lautstärke des Computers")
        self.fader.setEnabled(False)  # bis der Wert gelesen ist
        self._apply = QTimer(self, singleShot=True, interval=120)
        self._apply.timeout.connect(self._set)
        self.fader.valueChanged.connect(lambda _v: self._apply.start())
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        lay.addWidget(self.fader, 0, Qt.AlignHCenter)
        lay.addSpacing(28)  # gleiche Höhe wie der Medien-Kanal mit Stumm-Knopf
        self.refresh()

    def refresh(self) -> None:
        """Wert vom System lesen (im Hintergrund – das Abfragen kann kurz dauern); höchstens alle 3 s."""
        import time

        from .. import pc_control
        from .util import run_async

        now = time.monotonic()
        if now - getattr(self, "_read_at", -10.0) < 3:
            return
        self._read_at = now

        def show(value):
            try:
                if value is None:
                    self.fader.setEnabled(False)
                    self.fader.setToolTip("Lautstärke des Computers lässt sich hier nicht ablesen")
                    return
                if not self.fader.isSliderDown() and not self._apply.isActive():
                    self.fader.blockSignals(True)
                    self.fader.setValue(int(value))
                    self.fader.blockSignals(False)
                    self.fader.update()
                self.fader.setEnabled(True)
            except RuntimeError:  # Fenster schon zu
                pass

        run_async(pc_control.get_volume, show, owner=self)

    def _set(self) -> None:
        from .. import pc_control
        from .util import run_async

        run_async(lambda v=self.fader.value(): pc_control.set_volume(v), owner=self)


class FaderPanel(QWidget):
    """Kleines Regler-Pult neben dem Programmbild: PC und Medien."""

    def __init__(self, volume_box: VolumeBox, parent=None):
        super().__init__(parent)
        self.pc = PcVolumeFader()
        self.setObjectName("FaderPanel")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.apply_theme()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(6, 4, 6, 0)
        lay.setSpacing(6)
        lay.addWidget(self.pc)
        lay.addWidget(volume_box)

    def apply_theme(self) -> None:
        """Eingelassener, dunkler Pultteil (wie die Fader-Sektion eines Mischpults)."""
        t = theme.current()
        inset = t.mix(t.bg, "#000000", 0.25).name() if t.dark else t.mix(t.bg, "#000000", 0.04).name()
        self.setStyleSheet(f"#FaderPanel {{ background: {inset}; border: 1px solid {t.border}; border-radius: 8px; }}")
