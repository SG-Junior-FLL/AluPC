"""Eigener Sprachbefehl: Satz (ohne Startwort) → Aktion (Befehl, Szene oder eigene Kachel)."""

from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QVBoxLayout

from .widgets import button, page_header


def action_choices(config) -> list[tuple[str, str]]:
    """(Aktion, Anzeige) – eingebaute Befehle, Szenen, eigene Kacheln."""
    from ..startpage import COMMANDS

    out = [(key, label) for key, label in COMMANDS.items()]
    out += [(f"szene:{name}", f"Szene: {name}") for name in config.scene_names()]
    for tile in config["start_page"].get("custom", []) or []:
        out.append((f"kachel:{tile.get('id')}", f"Eigene Kachel: {tile.get('title', '?')}"))
    return out


def describe_action(config, action: str) -> str:
    return dict(action_choices(config)).get(action, action)


class VoiceCustomDialog(QDialog):
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle("Eigener Sprachbefehl")
        self.setMinimumWidth(460)
        lay = QVBoxLayout(self)
        lay.addWidget(page_header("Eigener Sprachbefehl", "Was du sagst → was AluPC macht", "mic"))
        form = QFormLayout()
        self.say = QLineEdit()
        self.say.setPlaceholderText("z. B. Pause machen")
        self.say.setMaxLength(60)
        self.action = QComboBox()
        for key, label in action_choices(controller.config):
            self.action.addItem(label.replace("&", "&&"), key)
        form.addRow("Satz:", self.say)
        form.addRow("Aktion:", self.action)
        lay.addLayout(form)
        self.example = QLabel()
        self.example.setObjectName("Muted")
        self.example.setWordWrap(True)
        lay.addWidget(self.example)
        row = QHBoxLayout()
        cancel = button("Abbrechen", "x")
        cancel.clicked.connect(self.reject)
        self.ok = button("Speichern", "check", primary=True)
        self.ok.clicked.connect(self.save)
        row.addStretch(1)
        row.addWidget(cancel)
        row.addWidget(self.ok)
        lay.addLayout(row)
        self.say.textChanged.connect(self._check)
        self._check()

    def _check(self):
        text = self.say.text().strip()
        self.ok.setEnabled(bool(text))
        self.example.setText(f"Sagen: „Alu PC, {text}“ oder „Monitor {text}“" if text else
                             "Der Satz ohne Startwort – AluPC hört auch auf leicht andere Aussprache.")

    def save(self):
        say = " ".join(self.say.text().split())
        if not say:
            return
        cfg = self.controller.config["voice"]
        custom = [c for c in cfg.get("custom") or [] if c.get("say", "").lower() != say.lower()]
        custom.append({"say": say, "do": self.action.currentData()})
        self.controller.config["voice"] = {**cfg, "custom": custom}
        self.accept()
