"""Kleines Fenster: Video weiterschauen oder von vorn? Schließt sich, sobald entschieden ist (auch per Handy)."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QVBoxLayout

from .widgets import button


def clock(ms: int) -> str:
    s = max(0, int(ms) // 1000)
    return f"{s // 3600}:{s // 60 % 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"


class VideoResumeDialog(QDialog):
    def __init__(self, controller, title: str, pos_ms: int, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle("Video")
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setModal(False)
        lay = QVBoxLayout(self)
        head = QLabel(f"<b>{title}</b><br>Schon mal geschaut bis <b>{clock(pos_ms)}</b>")
        head.setTextFormat(Qt.RichText)
        head.setWordWrap(True)
        lay.addWidget(head)
        self.left = QLabel()
        self.left.setObjectName("Muted")
        lay.addWidget(self.left)
        row = QHBoxLayout()
        self.restart = button("Von vorn", "rewind")
        self.resume = button(f"Weiterschauen ab {clock(pos_ms)}", "play", primary=True)
        self.restart.clicked.connect(lambda: self._choose("neu"))
        self.resume.clicked.connect(lambda: self._choose("weiter"))
        row.addWidget(self.restart)
        row.addWidget(self.resume)
        lay.addLayout(row)
        self._seconds = controller.RESUME_WAIT // 1000
        self._tick()
        self.timer = QTimer(self, interval=1000)
        self.timer.timeout.connect(self._tick)
        self.timer.start()
        controller.changed.connect(self._check_open)

    def _tick(self):
        if self.controller.resume_offer is None:
            self.close()
            return
        self.left.setText(f"Geht in {self._seconds} s von selbst weiter")
        self._seconds = max(0, self._seconds - 1)

    def _check_open(self):
        if self.controller.resume_offer is None:  # am Handy oder per Zeit entschieden
            self.close()

    def _choose(self, choice: str):
        self.controller.video_resume_choice(choice)
        self.close()

    def closeEvent(self, e):
        self.timer.stop()
        try:
            self.controller.changed.disconnect(self._check_open)
        except (RuntimeError, TypeError):
            pass
        super().closeEvent(e)
