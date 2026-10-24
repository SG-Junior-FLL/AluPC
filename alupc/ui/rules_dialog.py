"""Wenn → Dann: eine Regel für die Tastenbox bearbeiten (Tastenfolge, Code und/oder Reglerzahl → Aktion).
Siehe automations."""

from __future__ import annotations

from PySide6.QtCore import QRegularExpression
from PySide6.QtGui import QRegularExpressionValidator
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..automations import (
    ACTION_HINTS,
    ACTIONS,
    KEY_POS,
    actions_of,
    clean_rule,
    describe,
    describe_sequence,
    is_valid,
    target_label,
)
from .voice_custom import action_choices
from .widgets import button, page_header, searchable

TRIGGERS = {
    "folge": "Tastenfolge – Tasten schnell hintereinander drücken",
    "code": "Code – Code-Taste lang drücken, dann Ziffern tippen",
    "wert": "Nur Reglerzahl – Regler auf eine Zahl drehen",
}


class RuleDialog(QDialog):
    def __init__(self, controller, rule: dict | None = None, taken: set[str] | None = None, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.taken = taken or set()  # Namen anderer Regeln (Name ist der Schlüssel für „regel:Name“)
        rule = clean_rule(rule or {"name": "", "wenn": {}, "dann": {"art": "programm"}})
        self.setWindowTitle("Wenn → Dann")
        self.setMinimumWidth(560)
        lay = QVBoxLayout(self)
        lay.addWidget(page_header("Wenn → Dann", "Wenn das an der Box passiert → dann macht AluPC das", "keyboard"))
        self._form = form = QFormLayout()
        self.name = QLineEdit(rule["name"])
        self.name.setPlaceholderText("z. B. Intro-Video")
        self.name.setMaxLength(60)
        form.addRow("Name:", self.name)

        # ---- WENN
        self.trigger = QComboBox()
        for key, label in TRIGGERS.items():
            self.trigger.addItem(label, key)
        w = rule["wenn"]
        start = "folge" if w["folge"] else ("code" if w["code"] else ("wert" if w["wert"] is not None else "folge"))
        self.trigger.setCurrentIndex(self.trigger.findData(start))
        form.addRow("Wenn:", self.trigger)

        self.seq_box = QWidget()  # Tastenfolge: 3 × 3 wie auf der Box antippen
        sl = QHBoxLayout(self.seq_box)
        sl.setContentsMargins(0, 0, 0, 0)
        pad = QGridLayout()
        pad.setSpacing(4)
        for n in range(1, 10):
            b = QPushButton(str(n))
            b.setFixedSize(44, 36)
            b.setToolTip(KEY_POS[n])
            b.clicked.connect(lambda _c=False, n=n: self.seq.setText((self.seq.text() + str(n))[:12]))
            pad.addWidget(b, (n - 1) // 3, (n - 1) % 3)
        sl.addLayout(pad)
        side = QVBoxLayout()
        self.seq = QLineEdit(w["folge"])
        self.seq.setPlaceholderText("z. B. 712")
        self.seq.setValidator(QRegularExpressionValidator(QRegularExpression("[1-9]{0,12}"), self))
        clear = button("Neu anfangen", "x")
        clear.clicked.connect(self.seq.clear)
        self.seq_text = QLabel()
        self.seq_text.setObjectName("Muted")
        self.seq_text.setWordWrap(True)
        for x in (self.seq, clear, self.seq_text):
            side.addWidget(x)
        side.addStretch(1)
        sl.addLayout(side, 1)
        form.addRow("Folge:", self.seq_box)

        self.code = QLineEdit(w["code"])
        self.code.setPlaceholderText("z. B. 123")
        self.code.setValidator(QRegularExpressionValidator(QRegularExpression("[1-9]{0,12}"), self))
        self.code.setToolTip(f"Taste {controller.code_key()} lang drücken, dann den Code tippen, 1,5 s warten")
        form.addRow("Code:", self.code)

        row = QHBoxLayout()
        self.use_value = QCheckBox("Regler steht auf")
        self.use_value.setChecked(w["wert"] is not None)
        self.value = QSpinBox()
        self.value.setRange(0, 999)
        self.value.setValue(w["wert"] or 0)
        here = button("Jetzt", "sliders")
        here.setToolTip("Aktuelle Reglerzahl übernehmen")
        here.clicked.connect(self._take_value)
        self.tol = QSpinBox()
        self.tol.setRange(0, 50)
        self.tol.setPrefix("± ")
        self.tol.setValue(w["toleranz"])
        self.tol.setToolTip("Zählwerk und Messwert weichen etwas ab – ± 2 bis 5 ist gut")
        for x in (self.use_value, self.value, self.tol, here):
            row.addWidget(x)
        row.addStretch(1)
        self.value_label = QLabel("und:")
        form.addRow(self.value_label, row)

        # ---- DANN
        self.art = QComboBox()
        for key, label in ACTIONS.items():
            self.art.addItem(label, key)
        self.art.setCurrentIndex(max(0, self.art.findData(rule["dann"]["art"])))
        form.addRow("Dann:", self.art)
        self.stack = QStackedWidget()
        text_row = QHBoxLayout()
        art, ziel = rule["dann"]["art"], rule["dann"]["ziel"]
        self.ziel = QLineEdit(ziel if art not in ("alupc", "buzzer") else "")
        self.pick = button("Auswählen", "download")
        self.pick.clicked.connect(self._pick_file)
        self.play_btn = button("Probe", "play")
        self.play_btn.setToolTip("Jetzt einmal abspielen")
        self.play_btn.clicked.connect(self._try)
        text_row.addWidget(self.ziel, 1)
        text_row.addWidget(self.pick)
        text_row.addWidget(self.play_btn)
        holder = QWidget()
        holder.setLayout(text_row)
        text_row.setContentsMargins(0, 0, 0, 0)
        self.stack.addWidget(holder)
        self.command = searchable(QComboBox())
        for key, label in action_choices(controller.config):
            self.command.addItem(label, key)
        if art == "alupc":
            self.command.setCurrentIndex(max(0, self.command.findData(ziel)))
        self.stack.addWidget(self.command)
        song_row = QHBoxLayout()
        song_row.setContentsMargins(0, 0, 0, 0)
        from ..buzzer import SONGS

        self.song = searchable(QComboBox())
        for key, (label, _t, _n) in SONGS.items():
            self.song.addItem(label, key)
        if art == "buzzer":
            self.song.setCurrentIndex(max(0, self.song.findData(ziel)))
        song_try = button("Probe", "play")
        song_try.setToolTip("Jetzt auf dem Buzzer der Box abspielen")
        song_try.clicked.connect(self._try)
        song_row.addWidget(self.song, 1)
        song_row.addWidget(song_try)
        song_holder = QWidget()
        song_holder.setLayout(song_row)
        self.stack.addWidget(song_holder)
        form.addRow("", self.stack)
        # Mehrere Aktionen: Liste der Schritte – der ausgewählte Schritt wird oben bearbeitet
        self.actions = [dict(a) for a in actions_of(rule)]
        self.cur = 0
        steps = QWidget()
        sl2 = QVBoxLayout(steps)
        sl2.setContentsMargins(0, 0, 0, 0)
        self.steps = QListWidget()
        self.steps.setMaximumHeight(96)
        self.steps.setToolTip("Alle Aktionen laufen nacheinander. Eine anklicken = oben bearbeiten.")
        self.steps.currentRowChanged.connect(self._pick_step)
        step_row = QHBoxLayout()
        add = button("Weitere Aktion", "plus")
        add.clicked.connect(self._add_step)
        self.del_step = button("Entfernen", "trash")
        self.del_step.clicked.connect(self._remove_step)
        step_row.addWidget(add)
        step_row.addWidget(self.del_step)
        step_row.addStretch(1)
        sl2.addWidget(self.steps)
        sl2.addLayout(step_row)
        form.addRow("Schritte:", steps)
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

        for sig in (self.name.textChanged, self.code.textChanged, self.ziel.textChanged, self.seq.textChanged):
            sig.connect(self._check)
        for sig in (self.value.valueChanged, self.tol.valueChanged):
            sig.connect(self._check)
        self.use_value.toggled.connect(self._check)
        for combo in (self.trigger, self.art, self.command, self.song):
            combo.currentIndexChanged.connect(self._check)
        self._check()

    def _editor_action(self) -> dict:
        art = self.art.currentData()
        ziel = {"alupc": self.command.currentData(), "buzzer": self.song.currentData()}.get(art, self.ziel.text())
        return {"art": art, "ziel": ziel or ""}

    def _load_action(self, action: dict) -> None:
        widgets = (self.art, self.ziel, self.command, self.song)
        for w in widgets:
            w.blockSignals(True)
        self.art.setCurrentIndex(max(0, self.art.findData(action.get("art", "alupc"))))
        ziel = action.get("ziel", "")
        self.ziel.setText(ziel if action.get("art") not in ("alupc", "buzzer") else "")
        if action.get("art") == "alupc":
            self.command.setCurrentIndex(max(0, self.command.findData(ziel)))
        if action.get("art") == "buzzer":
            self.song.setCurrentIndex(max(0, self.song.findData(ziel)))
        for w in widgets:
            w.blockSignals(False)

    def _fill_steps(self) -> None:
        self.steps.blockSignals(True)
        if self.steps.count() != len(self.actions):
            self.steps.clear()
            self.steps.addItems(["" for _ in self.actions])
        for i, a in enumerate(self.actions):
            label = f"{i + 1}. {ACTIONS.get(a['art'], a['art'])}: {target_label(a['art'], a['ziel']) or '…'}"
            if a["art"] == "alupc":
                label = f"{i + 1}. {self.command.itemText(max(0, self.command.findData(a['ziel'])))}"
            self.steps.item(i).setText(label)
        self.steps.setCurrentRow(self.cur)
        self.steps.blockSignals(False)
        self.del_step.setEnabled(len(self.actions) > 1)

    def _pick_step(self, row: int) -> None:
        if 0 <= row < len(self.actions):
            self.cur = row
            self._load_action(self.actions[row])
            self._check()

    def _add_step(self) -> None:
        self.actions.append({"art": "alupc", "ziel": ""})
        self.cur = len(self.actions) - 1
        self._load_action(self.actions[self.cur])
        self._check()

    def _remove_step(self) -> None:
        if len(self.actions) > 1:
            self.actions.pop(self.cur)
            self.cur = max(0, self.cur - 1)
            self._load_action(self.actions[self.cur])
            self._check()

    def rule(self) -> dict:
        trig = self.trigger.currentData()
        if hasattr(self, "actions"):
            self.actions[self.cur] = self._editor_action()
        actions = [a for a in getattr(self, "actions", [self._editor_action()]) if a["ziel"]] or [self._editor_action()]
        use_value = self.use_value.isChecked() or trig == "wert"
        return clean_rule({"name": self.name.text(), "an": True,
                           "wenn": {"folge": self.seq.text() if trig == "folge" else "",
                                    "code": self.code.text() if trig == "code" else "",
                                    "toleranz": self.tol.value(),
                                    "wert": self.value.value() if use_value else None},
                           "dann": actions[0], "weitere": actions[1:]})

    def _check(self) -> None:
        art, trig = self.art.currentData(), self.trigger.currentData()
        if hasattr(self, "actions"):
            self.actions[self.cur] = self._editor_action()
            self._fill_steps()
        self.stack.setCurrentIndex({"alupc": 1, "buzzer": 2}.get(art, 0))
        self.ziel.setPlaceholderText(ACTION_HINTS.get(art, ""))
        self.pick.setVisible(art in ("programm", "datei", "klang", "buzzer_midi"))
        self.play_btn.setVisible(art in ("klang", "buzzer_midi"))
        self._form.setRowVisible(self.seq_box, trig == "folge")
        self._form.setRowVisible(self.code, trig == "code")
        self.use_value.setVisible(trig != "wert")
        self.value_label.setText("Bei Zahl:" if trig == "wert" else "und:")
        on = self.use_value.isChecked() or trig == "wert"
        self.value.setEnabled(on)
        self.tol.setEnabled(on)
        folge = self.seq.text()
        self.seq_text.setText(describe_sequence(folge) if len(folge) >= 2 else
                              "Tasten oben antippen (mindestens 2). Zahlen = Tasten wie auf der Box: 1 oben links … "
                              "9 unten rechts.")
        rule = self.rule()
        name = self.name.text().strip()
        problem = ""
        if not name:
            problem = "Name fehlt."
        elif name in self.taken:
            problem = "Diesen Namen gibt es schon."
        elif trig == "folge" and len(folge) < 2:
            problem = "Tastenfolge: mindestens 2 Tasten."
        elif trig == "code" and not self.code.text():
            problem = "Code fehlt."
        elif not is_valid(rule):
            problem = "Ziel eintragen bzw. auswählen."
        self.ok.setEnabled(not problem)
        hint = ""
        if trig == "folge":
            gap = self.controller.seq_gap_ms() / 1000
            hint += (f" Die Tasten schnell hintereinander drücken (je höchstens {gap:.1f} s Pause). Tasten machen "
                     f"ihre eigene Funktion erst nach {gap:.1f} s – falls keine Folge daraus wird (Einstellung "
                     "„Jede Taste wartet kurz“ auf der Seite Tastenbox).")
        if trig == "code":
            hint += f" Taste {self.controller.code_key()} lang drücken (LEDs blinken), Code tippen, 1,5 s warten."
        if rule["wenn"]["wert"] is not None and self.controller.knob_target() != "wert":
            hint += " Reglerzahl zählt nur, wenn der Regler auf „Zahl 0–999“ steht."
        if art == "befehl":
            hint += " Läuft wie in deiner Kommandozeile – nur eigene Befehle eintragen."
        if art in ("buzzer", "buzzer_midi"):
            hint += " Braucht einen Buzzer an A2 und das Tastenbox-Programm ab Version 7."
        self.preview.setText(problem or (describe(rule) + "\n" + hint.strip()).strip())

    def _take_value(self) -> None:
        value = self.controller.box_number()
        if value is None:
            self.controller.message.emit("Keine Box verbunden.")
            return
        self.use_value.setChecked(True)
        self.value.setValue(value)

    def _pick_file(self) -> None:
        art = self.art.currentData()
        title, filt = {"programm": ("Programm wählen", ""), "klang": ("Klang wählen", "Töne (*.wav *.mp3 *.ogg *.flac *.m4a)"),
                       "buzzer_midi": ("MIDI-Datei wählen", "MIDI (*.mid *.midi)")}.get(art, ("Datei wählen", ""))
        path, _ = QFileDialog.getOpenFileName(self, title, "", filt)
        if not path:
            return
        if art == "klang":
            from .. import sounds

            path = sounds.upload(path)
        elif art == "buzzer_midi":
            from .. import buzzer

            try:
                buzzer.midi_notes(path)
            except (OSError, ValueError) as exc:
                self.preview.setText(f"Diese MIDI-Datei geht nicht: {exc}")
                return
            path = buzzer.upload_midi(path)
        self.ziel.setText(f'"{path}"' if art == "programm" and " " in path else path)

    def _try(self) -> None:
        art = self.art.currentData()
        if art == "buzzer":
            self.controller.play_buzzer_song(self.song.currentData())
        elif art == "buzzer_midi":
            self.controller.play_buzzer_midi(self.ziel.text())
        elif art == "klang":
            self.controller.sounds.play(self.ziel.text())
