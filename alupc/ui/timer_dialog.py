"""Timer einstellen: Dauer, Countdown oder Stoppuhr, Text am Ende."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
)

from ..timer import clock
from .widgets import button, page_header


class TimerDialog(QDialog):
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle("Timer")
        self.setMinimumWidth(460)
        cfg = controller.config["timer"]
        self.mode = QComboBox()
        self.mode.addItem("Countdown (läuft rückwärts)", "countdown")
        self.mode.addItem("Stoppuhr (läuft vorwärts)", "stoppuhr")
        self.mode.setCurrentIndex(max(0, self.mode.findData(cfg.get("mode", "countdown"))))
        self.minutes = QSpinBox()
        self.minutes.setRange(0, 999)
        self.minutes.setSuffix(" min")
        self.minutes.setValue(int(cfg.get("minutes", 5)))
        self.seconds = QSpinBox()
        self.seconds.setRange(0, 59)
        self.seconds.setSuffix(" s")
        self.seconds.setValue(int(cfg.get("seconds", 0)))
        self.finished = QLineEdit(cfg.get("finished_text", "Zeit ist um!"))
        self.warn = QCheckBox("Warnfarben (orange · rot · blinken)")
        self.warn.setChecked(bool(cfg.get("warn_colors", True)))
        self.start_now = QCheckBox("Sofort starten")
        self.start_now.setChecked(True)
        dur = QHBoxLayout()
        dur.addWidget(self.minutes)
        dur.addWidget(self.seconds)
        form = QFormLayout()
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(10)
        form.addRow("Art:", self.mode)
        form.addRow("Dauer:", dur)
        form.addRow("Text am Ende:", self.finished)
        form.addRow("", self.warn)
        form.addRow("", self.start_now)
        buttons = QDialogButtonBox()
        buttons.addButton(button("Auf Monitor 2 zeigen", "play", primary=True), QDialogButtonBox.AcceptRole)
        buttons.addButton(button("Abbrechen"), QDialogButtonBox.RejectRole)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 20, 22, 18)
        lay.setSpacing(12)
        lay.addWidget(page_header("Timer", f"Aktuell: {clock.status()}"))
        lay.addLayout(form)
        lay.addWidget(buttons)

    def _save(self):
        total = self.minutes.value() * 60 + self.seconds.value()
        if self.mode.currentData() == "countdown" and total <= 0:
            self.minutes.setValue(1)
            total = 60
        cfg = dict(self.controller.config["timer"])
        cfg.update({"mode": self.mode.currentData(), "minutes": self.minutes.value(),
                    "seconds": self.seconds.value(), "finished_text": self.finished.text(),
                    "warn_colors": self.warn.isChecked()})
        self.controller.config["timer"] = cfg
        clock.set(max(1, total), cfg["mode"], cfg["finished_text"])
        if self.start_now.isChecked():
            clock.start()
        self.controller.show_source(self.controller.timer_source())
        self.accept()
