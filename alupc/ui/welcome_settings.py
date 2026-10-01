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
        # Personen vom Fingerabdruck + von Hand hinzugefügte (z. B. nur für Geburtstage / Ausprobieren)
        persons = self._persons()
        persons += [p for p in list(birthdays) + list(names) if p not in persons]
        head = QLabel("Namen & Geburtstage")
        head.setObjectName("SectionTitle")
        lay.addWidget(head)
        hint = QLabel("Personen vom Fingerabdruck stehen automatisch hier – weitere unten hinzufügen.")
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        lay.addWidget(hint)
        self.names_form = QFormLayout()
        self._names, self._birthdays = names, birthdays
        for person in persons:
            self._add_person_row(person)
        lay.addLayout(self.names_form)
        add_row = QHBoxLayout()
        self.new_person = QLineEdit()
        self.new_person.setPlaceholderText("Neue Person, z. B. Lena")
        self.new_person.setMaxLength(40)
        self.new_person.returnPressed.connect(self._add_person)
        add_btn = button("Hinzufügen", "plus")
        add_btn.clicked.connect(self._add_person)
        add_row.addWidget(self.new_person, 1)
        add_row.addWidget(add_btn)
        lay.addLayout(add_row)

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

    def _add_person_row(self, person: str) -> None:
        edit = QLineEdit(self._names.get(person, ""))
        edit.setPlaceholderText(person)
        edit.setToolTip("Eigener Begrüßungsname (leer = Name der Person)")
        edit.setMaxLength(40)
        self.name_edits[person] = edit
        day = QLineEdit(format_birthday(self._birthdays.get(person, "")))
        day.setPlaceholderText("TT.MM.")
        day.setToolTip("Geburtstag – an dem Tag gibt es Konfetti und „Alles Gute zum Geburtstag!“")
        day.setMaxLength(10)
        day.setFixedWidth(90)
        day.textChanged.connect(lambda _t, d=day: self._check_day(d))
        self.birthday_edits[person] = day
        row = QHBoxLayout()
        row.addWidget(edit, 1)
        row.addWidget(day)
        self.names_form.addRow(person.replace("&", "&&"), row)

    def _add_person(self) -> None:
        name = " ".join(self.new_person.text().split())
        if not name or name in self.name_edits:
            self.new_person.clear()
            return
        self._add_person_row(name)
        if hasattr(self, "try_name") and self.try_name.findText(name) < 0:
            self.try_name.addItem(name)
        self.new_person.clear()
        self.birthday_edits[name].setFocus()

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
        # von Hand hinzugefügte Personen ohne Geburtstag/eigenen Namen bleiben nicht hängen – mit bleiben sie
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
