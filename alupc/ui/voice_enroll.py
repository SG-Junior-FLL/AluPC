"""Stimme anlernen: ein paar Sätze vorlesen → aus den Stimmabdrücken wird ein Mittelwert gespeichert."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QLineEdit, QProgressBar, QVBoxLayout

from .widgets import button, page_header

SENTENCES = [
    "Alu PC, Bildschirm schwarz.",
    "Monitor, nächste Szene.",
    "Heute ist ein schöner Tag für eine Präsentation.",
    "Ich lese diesen Satz ganz normal laut vor.",
    "Alu PC, Glücksrad drehen.",
    "Unser Roboter fährt jetzt die nächste Mission.",
]


class VoiceEnrollDialog(QDialog):
    def __init__(self, controller, parent=None, name: str = ""):
        super().__init__(parent)
        self.controller = controller
        self.voice = controller.voice
        self.vectors: list[list[float]] = []
        self.setWindowTitle("Stimme anlernen")
        self.setMinimumWidth(480)
        lay = QVBoxLayout(self)
        lay.addWidget(page_header("Stimme anlernen", "Sätze in normaler Lautstärke vorlesen – so wie später", "mic"))
        row = QHBoxLayout()
        row.addWidget(QLabel("Name:"))
        self.name = QLineEdit(name)
        self.name.setPlaceholderText("z. B. Lena")
        self.name.setMaxLength(24)
        row.addWidget(self.name, 1)
        lay.addLayout(row)
        self.sentence = QLabel()
        self.sentence.setWordWrap(True)
        self.sentence.setAlignment(Qt.AlignCenter)
        f = self.sentence.font()
        f.setPointSizeF((f.pointSizeF() if f.pointSizeF() > 0 else 10) * 1.6)
        f.setBold(True)
        self.sentence.setFont(f)
        self.sentence.setMinimumHeight(90)
        lay.addWidget(self.sentence)
        self.bar = QProgressBar()
        self.bar.setRange(0, len(SENTENCES))
        lay.addWidget(self.bar)
        self.hint = QLabel()
        self.hint.setObjectName("Muted")
        self.hint.setWordWrap(True)
        lay.addWidget(self.hint)
        buttons = QHBoxLayout()
        cancel = button("Abbrechen", "x")
        cancel.clicked.connect(self.reject)
        self.save_btn = button("Speichern", "check", primary=True)
        self.save_btn.clicked.connect(self.save)
        buttons.addStretch(1)
        buttons.addWidget(cancel)
        buttons.addWidget(self.save_btn)
        lay.addLayout(buttons)
        self.name.textChanged.connect(lambda _t: self.save_btn.setEnabled(len(self.vectors) >= 3
                                                                          and bool(self.name.text().strip())))
        self.voice.sample.connect(self._sample)
        self.voice.enrolling = True
        self._update()

    def _update(self):
        n = len(self.vectors)
        self.bar.setValue(n)
        ready = self.voice.state == "hört zu" and self.voice.has_spk
        if not ready:
            self.sentence.setText("Erst Sprachbefehle einschalten und die Stimmerkennung herunterladen")
        elif n < len(SENTENCES):
            self.sentence.setText(f"„{SENTENCES[n]}“")
        else:
            self.sentence.setText("Fertig! ✓")
        self.hint.setText(f"Satz {min(n + 1, len(SENTENCES))} von {len(SENTENCES)} – nach jedem Satz kurz Pause. "
                          "Gezählt wird, sobald AluPC den Satz gehört hat." if n < len(SENTENCES) else
                          "Jetzt einen Namen eingeben und speichern.")
        self.save_btn.setEnabled(n >= 3 and bool(self.name.text().strip()))

    def _sample(self, vector, frames: int, text: str):
        from ..voice import MIN_SPK_FRAMES

        if len(self.vectors) >= len(SENTENCES):
            return
        if frames < MIN_SPK_FRAMES:
            self.hint.setText(f"„{text}“ war zu kurz – den ganzen Satz bitte nochmal")
            return
        self.vectors.append(list(vector))
        self._update()

    def save(self):
        from ..voice import average_voice

        name = self.name.text().strip()
        if len(self.vectors) < 3 or not name:
            return
        cfg = self.controller.config["voice"]
        voices = [v for v in cfg.get("voices") or [] if v.get("name") != name]
        voices.append({"name": name, "vec": average_voice(self.vectors)})
        self.controller.config["voice"] = {**cfg, "voices": voices}
        self.accept()

    def done(self, result):
        self.voice.enrolling = False
        try:
            self.voice.sample.disconnect(self._sample)
        except (RuntimeError, TypeError):
            pass
        super().done(result)
