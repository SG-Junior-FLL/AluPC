"""Fingerabdruck automatisch einrichten: ein Klick, AluPC erledigt die Schritte nacheinander.

Linux:   Pakete prüfen/installieren → Sensor suchen → Finger anlernen → Test-Scan → Anmeldung einschalten
Windows: Sensor suchen → Windows Hello zum Anlernen öffnen → Test-Scan
"""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from ..platform.base import FINGERS
from . import icons, theme
from .util import run_async
from .widgets import ProgressRing, button, font, page_header

STATE_ICONS = {"wartet": ("dot", "muted"), "läuft": ("refresh", "accent"), "ok": ("check", "success"),
               "übersprungen": ("check", "muted"), "fehler": ("x", "danger")}


def _dot(color: str):
    from PySide6.QtGui import QColor, QPainter, QPen, QPixmap

    px = QPixmap(40, 40)
    px.setDevicePixelRatio(2)
    px.fill(Qt.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(QPen(QColor(color), 1.8))
    p.drawEllipse(4, 4, 12, 12)
    p.end()
    return px


class StepRow:
    def __init__(self, grid: QGridLayout, row: int, title: str):
        self.icon = QLabel()
        self.icon.setFixedSize(22, 22)
        self.title = QLabel(title)
        self.title.setFont(font(10.5, QFont.DemiBold))
        self.detail = QLabel("")
        self.detail.setObjectName("Muted")
        self.detail.setWordWrap(True)
        self.detail.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse)
        self.detail.setOpenExternalLinks(True)
        box = QVBoxLayout()
        box.setSpacing(0)
        box.addWidget(self.title)
        box.addWidget(self.detail)
        grid.addWidget(self.icon, row, 0, Qt.AlignTop)
        grid.addLayout(box, row, 1)
        self.set("wartet")

    def set(self, state: str, detail: str | None = None):
        name, role = STATE_ICONS[state]
        t = theme.current()
        color = {"muted": t.muted, "accent": t.accent, "success": t.success, "danger": t.danger}[role]
        if name == "dot":
            self.icon.setPixmap(_dot(color))
        else:
            self.icon.setPixmap(icons.pixmap(name, color, 20))
        if detail is not None:
            self.detail.setText(detail)
            self.detail.setVisible(bool(detail))
        self.state = state
        dialog = self.icon.window()
        if hasattr(dialog, "grow"):
            dialog.grow()


class FingerprintWizard(QDialog):
    def __init__(self, backend, parent=None, finger: str = "right-index-finger"):
        super().__init__(parent)
        self.backend = backend
        self.setWindowTitle("Fingerabdruck automatisch einrichten")
        self.setMinimumWidth(640)
        self.sensor_id = None
        self.running = False
        self.linux = backend.name == "fprintd"
        self._access_fixed = False

        self.finger_combo = QComboBox()
        for key, label in FINGERS:
            self.finger_combo.addItem(label, key)
        self.finger_combo.setCurrentIndex(max(0, self.finger_combo.findData(finger)))
        self.login_box = QCheckBox("Danach Anmelden per Fingerabdruck einschalten")
        self.login_box.setChecked(True)
        form = QFormLayout()
        if backend.can_enroll:
            form.addRow("Finger:", self.finger_combo)
        if backend.login_toggle:
            form.addRow("", self.login_box)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)
        grid.setColumnStretch(1, 1)
        titles = []
        if self.linux:
            titles.append(("pakete", "Sensor-Programme prüfen und installieren (fprintd)"))
        titles.append(("sensor", "Fingerabdrucksensor suchen"))
        titles.append(("anlernen", "Finger anlernen" if backend.can_enroll else "Finger in Windows Hello anlernen"))
        titles.append(("test", "Test-Scan"))
        if backend.login_toggle:
            titles.append(("anmeldung", "Anmelden mit Fingerabdruck einschalten"))
        self.steps = {key: StepRow(grid, i, text) for i, (key, text) in enumerate(titles)}

        self.ring = ProgressRing("fingerprint")
        self.ring.set_progress(0)
        self.ring.hide()
        self.message = QLabel("Klick auf „Einrichtung starten“ – AluPC erledigt den Rest und sagt dir, "
                              "wann du den Finger auflegen musst.")
        self.message.setWordWrap(True)
        self.message.setAlignment(Qt.AlignCenter)
        self.message.setFont(font(11, QFont.Medium))

        self.start_btn = button("Einrichtung starten", "play", primary=True)
        self.start_btn.clicked.connect(self.start)
        self.next_btn = button("Ich habe den Finger angelernt – weiter", "check", primary=True)
        self.next_btn.clicked.connect(self._after_hello)
        self.next_btn.hide()
        self.close_btn = button("Schließen", "x")
        self.close_btn.clicked.connect(self._close)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(self.close_btn)
        buttons.addWidget(self.next_btn)
        buttons.addWidget(self.start_btn)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 18)
        lay.setSpacing(12)
        lay.addWidget(page_header("Fingerabdruck einrichten", "Alles automatisch – Schritt für Schritt."))
        lay.addLayout(form)
        steps = QWidget()
        steps.setLayout(grid)
        lay.addWidget(steps)
        lay.addWidget(self.ring, 0, Qt.AlignCenter)
        lay.addWidget(self.message)
        lay.addLayout(buttons)

    def grow(self):
        """Fenster wächst mit, wenn Texte länger werden (nichts wird abgeschnitten oder gequetscht)."""
        layout = self.layout()
        if layout is None:
            return
        layout.activate()
        need = layout.totalHeightForWidth(self.width()) if layout.hasHeightForWidth() else self.sizeHint().height()
        if need > self.height():
            self.resize(self.width(), need)

    # ------------------------------------------------------------ Ablauf
    def say(self, text: str):
        self.message.setText(text)
        self.grow()

    def start(self):
        self.running = True
        self.start_btn.setEnabled(False)
        self.finger_combo.setEnabled(False)
        self.login_box.setEnabled(False)
        for step in self.steps.values():
            step.set("wartet", "")
        self.ring.restart()
        if self.linux:
            self._step_packages()
        else:
            self._step_sensor()

    def _fail(self, key: str, text: str):
        self.running = False
        self.steps[key].set("fehler", text)
        self.say("Einrichtung angehalten – siehe oben. Du kannst es nach dem Beheben erneut starten.")
        self.ring.hide()
        self.start_btn.setEnabled(True)
        self.start_btn.setText("Erneut versuchen")
        self.finger_combo.setEnabled(True)
        self.login_box.setEnabled(True)

    def _step_packages(self):
        step = self.steps["pakete"]
        step.set("läuft", "Prüfe …")

        def check():
            return self.backend.missing_packages()

        def checked(missing):
            if not missing:
                step.set("ok", "fprintd und libpam-fprintd sind installiert.")
                self._step_sensor()
                return
            if not self.backend.can_auto_install:
                self._fail("pakete", "Fehlt: " + ", ".join(missing) + " – bitte installieren: sudo apt install "
                           + " ".join(missing))
                return
            step.set("läuft", "Installiere " + ", ".join(missing) + " … (Passwort bestätigen; braucht Internet)")
            self.say("Das System fragt jetzt nach deinem Passwort, um die Pakete zu installieren.")
            run_async(lambda: self.backend.install_packages(missing),
                      lambda _r: (step.set("ok", "Installiert: " + ", ".join(missing)), self._step_sensor()),
                      lambda e: self._fail("pakete", str(e)))

        run_async(check, checked, lambda e: self._fail("pakete", str(e)))

    def _step_sensor(self):
        step = self.steps["sensor"]
        step.set("läuft", "Suche …")

        def work():
            ok, msg = self.backend.availability()
            sensors = self.backend.list_sensors() if ok else []
            hardware = self.backend.detect_hardware() if not sensors else []
            problem = ""
            if not sensors and not hardware and sys.platform.startswith("linux"):
                from ..platform.linux_serial_login import access_problem

                problem = access_problem()
            return ok, msg, sensors, hardware, problem

        def done(result):
            ok, msg, sensors, hardware, problem = result
            if not sensors and problem and not self._access_fixed:
                self._offer_access_fix(problem)
                return
            if sensors:
                self.sensor_id = sensors[0].id
                more = f" (+{len(sensors) - 1} weitere)" if len(sensors) > 1 else ""
                step.set("ok", f"{sensors[0].name}{more}")
                self._step_enroll()
                return
            text = msg or "Kein Sensor gefunden."
            if hardware:
                names = "; ".join(name for name, _hint in hardware)
                hints = " ".join(h for _n, h in hardware if h)
                text = (f"Das Gerät ist da ({names}), aber es gibt dafür keinen passenden Treiber. {hints} "
                        "Liste der unterstützten Sensoren: "
                        "<a href='https://fprint.freedesktop.org/supported-devices.html'>fprint.freedesktop.org</a>")
            self._fail("sensor", text)

        run_async(work, done, lambda e: self._fail("sensor", str(e)))

    def _offer_access_fix(self, problem: str):
        """Linux: USB-Seriell-Adapter (Fingerabdruckmodul) ist da, aber nicht nutzbar → reparieren?"""
        from PySide6.QtWidgets import QMessageBox

        from ..platform.linux_serial_login import fix_access

        step = self.steps["sensor"]
        if problem == "brltty":
            text = ("Ein USB-Seriell-Adapter (CH340) steckt, wird aber vom Dienst „brltty“ (für Braillezeilen) "
                    "blockiert – ein bekanntes Ubuntu-Problem.\n\nSoll AluPC brltty entfernen und angemeldeten "
                    "Benutzern Zugriff auf USB-Seriell-Adapter geben? (Passwort nötig. Wer eine Braillezeile "
                    "benutzt, sollte „Nein“ wählen.)")
        else:
            text = ("Ein USB-Seriell-Adapter steckt, aber AluPC darf ihn nicht öffnen.\n\nSoll AluPC angemeldeten "
                    "Benutzern Zugriff auf USB-Seriell-Adapter geben (udev-Regel)? Passwort nötig.")
        if QMessageBox.question(self, "Zugriff auf den Adapter", text) != QMessageBox.Yes:
            self._fail("sensor", "Kein Zugriff auf den USB-Seriell-Adapter.")
            return
        self._access_fixed = True
        step.set("läuft", "Zugriff wird eingerichtet … (Adapter danach einmal aus- und wieder einstecken)")
        run_async(lambda: fix_access(problem == "brltty"),
                  lambda _r: QTimer.singleShot(2500, self._step_sensor),
                  lambda e: self._fail("sensor", str(e)))

    def _step_enroll(self):
        step = self.steps["anlernen"]
        if self.backend.can_enroll:
            step.title.setText("Finger anlernen")
        if not self.backend.can_enroll:
            # Windows: Anlernen geht nur über Windows Hello
            step.set("läuft", "Windows Hello ist geöffnet – dort „Fingerabdruck einrichten“ durchklicken.")
            self.say("Lerne den Finger in Windows Hello an und klicke dann hier auf „weiter“.")
            self.backend.open_system_settings()
            self.next_btn.show()
            return
        finger = self.finger_combo.currentData()
        label = self.finger_combo.currentText()
        step.set("läuft", f"{label} …")

        def work(status):
            if self.backend.is_enrolled(self.sensor_id, finger):
                return "schon da"
            self.backend.enroll(self.sensor_id, finger, status)
            return "neu"

        def done(result):
            self.ring.hide()
            step.set("ok" if result == "neu" else "übersprungen",
                     f"{label} angelernt." if result == "neu" else f"{label} war schon angelernt.")
            self._step_test()

        def failed(text):
            self.ring.hide()
            self._fail("anlernen", text)

        self.ring.restart()
        self.ring.set_progress(-1)
        self.ring.show()
        self.grow()
        self.say("Gleich: Finger auf den Sensor legen (evtl. vorher Passwort bestätigen).")
        run_async(work, done, failed, self._progress)

    def _progress(self, text, stage, total):
        self.say(text)
        if total > 0:
            self.ring.set_progress(stage / total)

    def _after_hello(self):
        self.next_btn.hide()
        self.steps["anlernen"].set("ok", "In Windows Hello angelernt.")
        self._step_test()

    def _step_test(self):
        step = self.steps["test"]
        step.set("läuft", "Finger auflegen …")
        self.ring.restart()
        self.ring.set_progress(-1)
        self.ring.show()
        self.grow()
        self.say("Test: Lege den Finger noch einmal auf den Sensor.")

        def done(result):
            self.ring.hide()
            ok, text = result
            if not ok:
                self._fail("test", text + " – nochmal versuchen oder einen anderen Finger anlernen.")
                return
            step.set("ok", text)
            self._step_login()

        def failed(text):
            self.ring.hide()
            self._fail("test", text)

        run_async(lambda status: self.backend.verify(self.sensor_id, status), done, failed, self._progress)

    def _step_login(self):
        if "anmeldung" not in self.steps:
            self._finish()
            return
        step = self.steps["anmeldung"]
        if not self.login_box.isChecked():
            step.set("übersprungen", "Nicht gewünscht.")
            self._finish()
            return
        if self.backend.login_enabled():
            step.set("ok", "War schon eingeschaltet.")
            self._finish()
            return
        step.set("läuft", "Passwort bestätigen …")
        self.say("Das System fragt nach deinem Passwort, um die Anmeldung umzustellen.")
        run_async(lambda: self.backend.set_login_enabled(True),
                  lambda _r: (step.set("ok", "Eingeschaltet – das Passwort geht weiterhin."), self._finish()),
                  lambda e: self._fail("anmeldung", str(e)))

    def _finish(self):
        self.running = False
        self.ring.set_progress(1)
        self.ring.show()
        self.grow()
        self.ring.set_state("ok")
        text = "Fertig! Der Fingerabdruck ist eingerichtet."
        if self.linux and "anmeldung" in self.steps and self.steps["anmeldung"].state == "ok":
            text += (" Am Sperrbildschirm einfach den Finger auflegen. Beim Anmeldebildschirm musst du je "
                     "nach Version erst Enter drücken (leeres Passwort) und dann den Finger auflegen.")
        self.say(text)
        self.start_btn.hide()
        self.close_btn.setText("Fertig")

    def _close(self):
        if self.running:
            self.backend.cancel()
        self.accept()

    def closeEvent(self, event):
        if self.running:
            self.backend.cancel()
        super().closeEvent(event)

