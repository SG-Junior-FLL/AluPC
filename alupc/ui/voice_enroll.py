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
        self.heard = QLabel()  # was AluPC gerade hört – zeigt, dass das Mikrofon geht
        self.heard.setObjectName("Muted")
        self.heard.setWordWrap(True)
        lay.addWidget(self.heard)
        self.dl_btn = button("Stimmerkennung herunterladen (ca. 13 MB)", "download", primary=True)
        self.dl_btn.clicked.connect(self._download)
        self.dl_btn.hide()
        lay.addWidget(self.dl_btn)
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
        self.voice.state_changed.connect(self._state)
        self.voice.heard.connect(self._heard)
        self.voice.enrolling = True
        self._started_here = False
        self._prepare()
        self._update()

    # ------------------------------------------------------------ vorbereiten: Stimmerkennung + Zuhören
    def _prepare(self):
        """Alles Nötige selbst erledigen: Stimmerkennung fehlt → Download anbieten; Zuhören aus → kurz starten;
        Stimmerkennung erst nach dem Start geladen → neu starten."""
        from ..voice import spk_ready

        if self.voice.has_spk and self.voice.state == "hört zu":
            return  # läuft schon mit Stimmerkennung
        if not spk_ready():
            self.dl_btn.show()
            return
        self.dl_btn.hide()
        v = self.voice
        if v.running() and not v.has_spk:
            v.stop()
        if not v.running() and v.state != "lädt":
            self._started_here = not v.settings().get("on") and not v.direct
            v.start()

    def _download(self):
        from .. import voice
        from .util import error_box, run_async

        self.dl_btn.setEnabled(False)
        self.dl_btn.setText("Lädt …")

        def done(_p):
            self.dl_btn.setEnabled(True)
            self._prepare()
            self._update()

        def failed(e):
            self.dl_btn.setEnabled(True)
            self.dl_btn.setText("Stimmerkennung herunterladen (ca. 13 MB)")
            error_box(self, f"Stimmerkennung konnte nicht geladen werden: {e}")

        run_async(lambda: voice.download_model(url=voice.SPK_URL, target=voice.spk_dir(), ready=voice.spk_ready),
                  done, failed)

    def _state(self, _state):
        self._update()

    def _heard(self, text: str):
        self.heard.setText(f"Gehört: {text}")

    def _update(self):
        n = len(self.vectors)
        self.bar.setValue(n)
        from ..voice import spk_ready

        ready = self.voice.state == "hört zu" and self.voice.has_spk
        if not ready and not spk_ready():
            self.sentence.setText("Einmal die Stimmerkennung herunterladen – dann geht's los")
        elif not ready:
            state = self.voice.state
            self.sentence.setText("Einen Moment – AluPC startet das Zuhören …" if state in ("lädt", "aus", "hört zu")
                                  else f"Problem: {state}")
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
        v = self.voice
        v.enrolling = False
        for sig, slot in ((v.sample, self._sample), (v.state_changed, self._state), (v.heard, self._heard)):
            try:
                sig.disconnect(slot)
            except (RuntimeError, TypeError):
                pass
        if self._started_here and not v.settings().get("on") and not v.direct:
            v.stop()  # nur fürs Anlernen gestartet
        super().done(result)
