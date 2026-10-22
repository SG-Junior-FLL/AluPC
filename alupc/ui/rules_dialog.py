"""Wenn → Dann: eine Regel für die Tastenbox bearbeiten (Code und/oder Reglerzahl → Aktion). Siehe automations."""

from __future__ import annotations

from PySide6.QtCore import QRegularExpression
from PySide6.QtGui import QRegularExpressionValidator
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..automations import ACTION_HINTS, ACTIONS, clean_rule, describe, is_valid
from .voice_custom import action_choices
from .widgets import button, page_header


class RuleDialog(QDialog):
    def __init__(self, controller, rule: dict | None = None, taken: set[str] | None = None, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.taken = taken or set()  # Namen anderer Regeln (Name ist der Schlüssel für „regel:Name“)
        rule = clean_rule(rule or {"name": "", "wenn": {}, "dann": {"art": "programm"}})
        self.setWindowTitle("Wenn → Dann")
        self.setMinimumWidth(520)
        lay = QVBoxLayout(self)
        lay.addWidget(page_header("Wenn → Dann", "Code auf den Tasten und/oder Reglerzahl → Aktion", "keyboard"))
        form = QFormLayout()
        self.name = QLineEdit(rule["name"])
        self.name.setPlaceholderText("z. B. Intro-Video")
        self.name.setMaxLength(60)
        form.addRow("Name:", self.name)

        self.code = QLineEdit(rule["wenn"]["code"])
        self.code.setPlaceholderText("leer = ohne Code · z. B. 123")
        self.code.setValidator(QRegularExpressionValidator(QRegularExpression("[1-9]{0,12}"), self))
        self.code.setToolTip(f"Taste {controller.code_key()} lang drücken, dann den Code tippen, 1,5 s warten")
        form.addRow("Wenn Code:", self.code)

        row = QHBoxLayout()
        self.use_value = QCheckBox("Regler steht auf")
        self.use_value.setChecked(rule["wenn"]["wert"] is not None)
        self.value = QSpinBox()
        self.value.setRange(0, 999)
        self.value.setValue(rule["wenn"]["wert"] or 0)
        here = button("Jetzt", "sliders")
        here.setToolTip("Aktuelle Reglerzahl übernehmen")
        here.clicked.connect(self._take_value)
        self.tol = QSpinBox()
        self.tol.setRange(0, 50)
        self.tol.setPrefix("± ")
        self.tol.setValue(rule["wenn"]["toleranz"])
        self.tol.setToolTip("Zählwerk und Messwert weichen etwas ab – ± 2 bis 5 ist gut")
        for w in (self.use_value, self.value, self.tol, here):
            row.addWidget(w)
        row.addStretch(1)
        form.addRow("und/oder:", row)

        self.art = QComboBox()
        for key, label in ACTIONS.items():
            self.art.addItem(label, key)
        self.art.setCurrentIndex(max(0, self.art.findData(rule["dann"]["art"])))
        form.addRow("Dann:", self.art)
        self.stack = QStackedWidget()
        text_row = QHBoxLayout()
        self.ziel = QLineEdit(rule["dann"]["ziel"] if rule["dann"]["art"] != "alupc" else "")
        self.pick = button("Auswählen", "download")
        self.pick.clicked.connect(self._pick_file)
        text_row.addWidget(self.ziel, 1)
        text_row.addWidget(self.pick)
        holder = QWidget()
        holder.setLayout(text_row)
        text_row.setContentsMargins(0, 0, 0, 0)
        self.stack.addWidget(holder)
        self.command = QComboBox()
        for key, label in action_choices(controller.config):
            self.command.addItem(label.replace("&", "&&"), key)
        if rule["dann"]["art"] == "alupc":
            self.command.setCurrentIndex(max(0, self.command.findData(rule["dann"]["ziel"])))
        self.stack.addWidget(self.command)
        form.addRow("", self.stack)
        lay.addLayout(form)

        self.preview = QLabel()
        self.preview.setObjectName("Muted")
        self.preview.setWordWrap(True)
        lay.addWidget(self.preview)
        row = QHBoxLayout()
        cancel = button("Abbrechen", "x")
        cancel.clicked.connect(self.reject)
        self.ok = button("Speichern", "check", primary=True)
        self.ok.clicked.connect(self.accept)
        row.addStretch(1)
        row.addWidget(cancel)
        row.addWidget(self.ok)
        lay.addLayout(row)

        for sig in (self.name.textChanged, self.code.textChanged, self.ziel.textChanged):
            sig.connect(self._check)
        for sig in (self.value.valueChanged, self.tol.valueChanged):
            sig.connect(self._check)
        self.use_value.toggled.connect(self._check)
        self.art.currentIndexChanged.connect(self._check)
        self.command.currentIndexChanged.connect(self._check)
        self._check()

    def rule(self) -> dict:
        art = self.art.currentData()
        ziel = self.command.currentData() if art == "alupc" else self.ziel.text()
        return clean_rule({"name": self.name.text(), "an": True,
                           "wenn": {"code": self.code.text(), "toleranz": self.tol.value(),
                                    "wert": self.value.value() if self.use_value.isChecked() else None},
                           "dann": {"art": art, "ziel": ziel}})

    def _check(self) -> None:
        art = self.art.currentData()
        self.stack.setCurrentIndex(1 if art == "alupc" else 0)
        self.ziel.setPlaceholderText(ACTION_HINTS.get(art, ""))
        self.pick.setVisible(art in ("programm", "datei"))
        self.value.setEnabled(self.use_value.isChecked())
        self.tol.setEnabled(self.use_value.isChecked())
        rule = self.rule()
        name = self.name.text().strip()
        problem = ""
        if not name:
            problem = "Name fehlt."
        elif name in self.taken:
            problem = "Diesen Namen gibt es schon."
        elif not is_valid(rule):
            problem = "Code oder Reglerzahl wählen und ein Ziel eintragen."
        self.ok.setEnabled(not problem)
        hint = ""
        if rule["wenn"]["code"]:
            hint += f" Taste {self.controller.code_key()} lang drücken, Code tippen, kurz warten."
        if rule["wenn"]["wert"] is not None and self.controller.knob_target() != "wert":
            hint += " Reglerzahl zählt nur, wenn der Regler auf „Zahl 0–999“ steht."
        if art == "befehl":
            hint += " Läuft wie in deiner Kommandozeile – nur eigene Befehle eintragen."
        self.preview.setText(problem or (describe(rule) + "\n" + hint.strip()).strip())

    def _take_value(self) -> None:
        value = self.controller.box_number()
        if value is None:
            self.controller.message.emit("Keine Box verbunden.")
            return
        self.use_value.setChecked(True)
        self.value.setValue(value)

    def _pick_file(self) -> None:
        title = "Programm wählen" if self.art.currentData() == "programm" else "Datei wählen"
        path, _ = QFileDialog.getOpenFileName(self, title)
        if path:
            self.ziel.setText(f'"{path}"' if self.art.currentData() == "programm" and " " in path else path)
