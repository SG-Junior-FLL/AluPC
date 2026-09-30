"""Fenster „Finger als Schnelltaste“: jedem angelernten Finger einen Befehl geben."""

from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QComboBox, QDialog, QFormLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from ..finger_shortcuts import own_fingers, shortcut_map
from .widgets import button, page_header


def command_choices(config) -> list[tuple[str, str]]:
    from ..startpage import COMMANDS

    items = [("", "– nichts –"), ("sperren", "Computer sperren")] + list(COMMANDS.items())
    items += [(f"szene:{s['name']}", f"Szene: {s['name']}") for s in config["scenes"] if s.get("name")]
    return items


class FingerShortcutsDialog(QDialog):
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle("Finger als Schnelltaste")
        self.setMinimumWidth(480)
        lay = QVBoxLayout(self)
        lay.addWidget(page_header("Finger als Schnelltaste", "Finger auflegen = Befehl ausführen", "fingerprint"))
        cfg = controller.config["finger_shortcuts"]
        self.on = QCheckBox("Eingeschaltet")
        self.on.setChecked(bool(cfg.get("on")))
        lay.addWidget(self.on)
        hint = QLabel("Nur wenn der PC entsperrt ist. Anmelden mit dem Finger geht weiterhin.")
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        lay.addWidget(hint)
        current = shortcut_map(controller.config)
        choices = command_choices(controller.config)
        self.combos: dict[int, QComboBox] = {}
        body = QWidget()
        form = QFormLayout(body)
        fingers = own_fingers()
        for slot, person, finger in fingers:
            combo = QComboBox()
            for key, label in choices:
                combo.addItem(label, key)
            if current.get(slot) and combo.findData(current[slot]) < 0:
                combo.addItem(current[slot], current[slot])  # z. B. gelöschte Szene: nicht still verlieren
            combo.setCurrentIndex(max(0, combo.findData(current.get(slot, ""))))
            self.combos[slot] = combo
            form.addRow(f"{person} · {finger}", combo)
        if not fingers:
            empty = QLabel("Noch keine Finger angelernt (Seite Fingerabdruck → Finger anlernen).")
            empty.setWordWrap(True)
            form.addRow(empty)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(body)
        scroll.setFrameShape(QScrollArea.NoFrame)
        lay.addWidget(scroll, 1)
        done = button("Fertig", "check", primary=True)
        done.clicked.connect(self.accept)
        lay.addWidget(done)
        self.finished.connect(lambda _r: self.save())

    def save(self) -> None:
        mapping = {str(slot): combo.currentData() for slot, combo in self.combos.items() if combo.currentData()}
        self.controller.config["finger_shortcuts"] = {"on": self.on.isChecked(), "map": mapping}
        self.controller.config.save()
        self.controller.finger_shortcuts.apply()
