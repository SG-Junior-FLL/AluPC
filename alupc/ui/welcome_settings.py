"""Fenster „Begrüßung“ (Seite Fingerabdruck): Animation nach der Anmeldung mit dem Finger, eigene Namen und
Geburtstage je Person – und „Ausprobieren“ ohne Sensor."""

from __future__ import annotations

from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
                               QVBoxLayout)

from ..welcome import STYLES, format_birthday, parse_birthday
from .widgets import button, page_header


class WelcomeSettings(QDialog):
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle("Begrüßung")
        self.setMinimumWidth(460)
        cfg = controller.config["welcome"]
        lay = QVBoxLayout(self)
        lay.addWidget(page_header("Begrüßung", "Nach der Anmeldung mit dem Finger", "star"))

        form = QFormLayout()
        self.on = QCheckBox("Nach Fingerabdruck begrüßen")
        self.on.setChecked(bool(cfg.get("on", True)))
        form.addRow(self.on)
        self.style = QComboBox()
        for key, label in STYLES.items():
            self.style.addItem(label, key)
        self.style.setCurrentIndex(max(0, self.style.findData(cfg.get("style", "aurora"))))
        form.addRow("Animation", self.style)
        self.text = QLineEdit(cfg.get("text", ""))
        self.text.setPlaceholderText("automatisch (z. B. „Guten Morgen“)")
        self.text.setMaxLength(60)
        form.addRow("Überschrift", self.text)
        self.sound = QCheckBox("Mit Ton")
        self.sound.setChecked(bool(cfg.get("sound", True)))
        form.addRow(self.sound)
        lay.addLayout(form)

        # Eigene Namen und Geburtstage je Person (z. B. „Noah“ → „Chef“, 24.12.)
        names = cfg.get("names") or {}
        birthdays = cfg.get("birthdays") or {}
        self.name_edits: dict[str, QLineEdit] = {}
        self.birthday_edits: dict[str, QLineEdit] = {}
        persons = self._persons()
        head = QLabel("Namen & Geburtstage" if persons else "Noch keine Personen mit Fingerabdruck angelernt.")
        head.setObjectName("SectionTitle" if persons else "Muted")
        lay.addWidget(head)
        names_form = QFormLayout()
        for person in persons:
            edit = QLineEdit(names.get(person, ""))
            edit.setPlaceholderText(person)
            edit.setMaxLength(40)
            self.name_edits[person] = edit
            day = QLineEdit(format_birthday(birthdays.get(person, "")))
            day.setPlaceholderText("TT.MM.")
            day.setToolTip("Geburtstag – an dem Tag gibt es Konfetti und „Alles Gute zum Geburtstag!“")
            day.setMaxLength(10)
            day.setFixedWidth(90)
            day.textChanged.connect(lambda _t, d=day: self._check_day(d))
            self.birthday_edits[person] = day
            row = QHBoxLayout()
            row.addWidget(edit, 1)
            row.addWidget(day)
            names_form.addRow(person, row)
        lay.addLayout(names_form)

        # Ausprobieren (ohne Sensor): Animation mit gewähltem Namen jetzt zeigen
        lay.addSpacing(6)
        row = QHBoxLayout()
        self.try_name = QComboBox()
        self.try_name.setEditable(True)
        self.try_name.addItems(persons or ["Noah"])
        self.try_name.setToolTip("Name zum Ausprobieren")
        row.addWidget(self.try_name, 1)
        self.try_button = button("Ausprobieren", "play")
        self.try_button.clicked.connect(self.try_it)
        row.addWidget(self.try_button)
        lay.addLayout(row)
        close = button("Fertig", "check", primary=True)
        close.clicked.connect(self.accept)
        lay.addWidget(close)
        self.finished.connect(lambda _r: self.save())

    @staticmethod
    def _persons() -> list[str]:
        try:
            from ..platform.zw_fingerprint import persons

            return persons()
        except Exception:  # noqa: BLE001
            return []

    @staticmethod
    def _check_day(edit: QLineEdit) -> None:
        edit.setStyleSheet("" if parse_birthday(edit.text()) is not None else "border: 2px solid #ef4444;")

    def save(self) -> None:
        names = {p: e.text().strip() for p, e in self.name_edits.items() if e.text().strip()}
        birthdays = {p: parse_birthday(e.text()) for p, e in self.birthday_edits.items()}
        self.controller.config["welcome"] = {
            **self.controller.config["welcome"],
            "on": self.on.isChecked(), "style": self.style.currentData(), "text": self.text.text().strip(),
            "sound": self.sound.isChecked(), "names": names,
            "birthdays": {p: v for p, v in birthdays.items() if v},
        }
        self.controller.config.save()

    def try_it(self) -> None:
        self.save()
        from ..welcome import display_name

        typed = self.try_name.currentText().strip()
        person = typed if typed in self.name_edits else ""
        self.controller.show_welcome(display_name(self.controller.config, typed), person)
