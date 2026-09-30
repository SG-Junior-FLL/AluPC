"""Kleine Fenster für Abstimmung, Glücksrad und Wetter-Ort."""

from __future__ import annotations

from PySide6.QtWidgets import (QCheckBox, QDialog, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QVBoxLayout)

from ..polls import MAX_OPTIONS
from .widgets import button, page_header


class PollDialog(QDialog):
    """Neue Abstimmung: Frage + 2–6 Antworten."""

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle("Abstimmung")
        self.setMinimumWidth(460)
        last = controller.config["poll"]
        lay = QVBoxLayout(self)
        lay.addWidget(page_header("Abstimmung", "Alle stimmen per Handy ab – ohne App", "poll"))
        self.question = QLineEdit(last.get("question", ""))
        self.question.setPlaceholderText("Frage, z. B. „Welche Mission zuerst?“")
        self.question.setMaxLength(160)
        lay.addWidget(self.question)
        self.options: list[QLineEdit] = []
        previous = list(last.get("options") or []) or ["Ja", "Nein"]
        for i in range(MAX_OPTIONS):
            edit = QLineEdit(previous[i] if i < len(previous) else "")
            edit.setPlaceholderText(f"Antwort {i + 1}" + ("" if i < 2 else " (optional)"))
            edit.setMaxLength(80)
            edit.textChanged.connect(self._check)
            self.options.append(edit)
            lay.addWidget(edit)
        self.hint = QLabel()
        self.hint.setObjectName("Muted")
        lay.addWidget(self.hint)
        row = QHBoxLayout()
        cancel = button("Abbrechen", "x")
        cancel.clicked.connect(self.reject)
        self.start = button("Starten", "play", primary=True)
        self.start.clicked.connect(self._start)
        row.addStretch(1)
        row.addWidget(cancel)
        row.addWidget(self.start)
        lay.addLayout(row)
        self.question.textChanged.connect(self._check)
        self._check()

    def answers(self) -> list[str]:
        return [e.text().strip() for e in self.options if e.text().strip()]

    def _check(self):
        ok = bool(self.question.text().strip()) and len(self.answers()) >= 2
        self.start.setEnabled(ok)
        self.hint.setText("QR-Code erscheint auf Monitor 2 · Ergebnis live" if ok else
                          "Frage und mindestens zwei Antworten eingeben")

    def _start(self):
        self.controller.start_poll(self.question.text(), self.answers())
        self.accept()


class WheelDialog(QDialog):
    """Namen fürs Glücksrad (eine Zeile pro Name)."""

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle("Glücksrad")
        self.setMinimumWidth(400)
        cfg = controller.config["wheel"]
        lay = QVBoxLayout(self)
        lay.addWidget(page_header("Glücksrad", "Ein Name pro Zeile", "wheel"))
        self.names = QPlainTextEdit("\n".join(cfg.get("names") or []))
        self.names.setPlaceholderText("leer = Personen vom Fingerabdruck\n\nLena\nNoah\nMia …")
        self.names.setMinimumHeight(200)
        lay.addWidget(self.names)
        self.remove = QCheckBox("Gezogene herausnehmen (jeder kommt einmal dran)")
        self.remove.setChecked(bool(cfg.get("remove_picked")))
        lay.addWidget(self.remove)
        row = QHBoxLayout()
        save = button("Speichern", "check")
        save.clicked.connect(self.accept)
        spin = button("Speichern && zeigen", "monitor", primary=True)
        spin.clicked.connect(self._spin)
        row.addStretch(1)
        row.addWidget(save)
        row.addWidget(spin)
        lay.addLayout(row)
        self.accepted.connect(self.save)

    def save(self):
        from ..wheel import clean_names

        self.controller.config["wheel"] = {"names": clean_names(self.names.toPlainText()),
                                           "remove_picked": self.remove.isChecked()}
        self.controller.wheel_left = None

    def _spin(self):
        self.accept()
        self.controller.show_wheel()  # gedreht wird erst mit „Drehen“


def ask_weather_place(controller, parent=None) -> None:
    """Ort fürs Wetter suchen (im Hintergrund) und speichern."""
    from PySide6.QtWidgets import QInputDialog

    from ..weather import geocode
    from .util import error_box, run_async

    current = controller.config["weather"].get("name", "")
    name, ok = QInputDialog.getText(parent, "Wetter", "Ort oder Postleitzahl (z. B. Berlin oder 80331):", text=current)
    if not ok or not name.strip():
        return

    def done(place):
        if place is None:
            error_box(parent, f"„{name.strip()}“ nicht gefunden.", "Wetter")
            return
        controller.config["weather"] = place
        controller.weather.data = None
        controller.weather.refresh(force=True)
        controller.message.emit(f"Wetter für {place['label']}.")
        controller.changed.emit()

    run_async(lambda: geocode(name), done,
              lambda e: error_box(parent, f"Ort nicht gefunden – keine Verbindung? ({e})", "Wetter"))
