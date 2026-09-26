"""Fingerabdruck: Sensor wählen, Finger anlernen, testen, löschen, Anmeldung einschalten."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from ..platform import IS_WINDOWS
from ..platform.base import FINGERS
from . import icons, theme
from .util import error_box, run_async
from .hand_picker import HandPicker, finger_keys_from
from .widgets import Banner, ProgressRing, button, font


class ScanDialog(QDialog):
    """Zeigt Anweisungen und Fortschritt (Ring), während der Sensor arbeitet."""

    def __init__(self, backend, title: str, parent=None):
        super().__init__(parent)
        self.backend = backend
        self.setWindowTitle(title)
        self.setMinimumWidth(440)
        heading = QLabel(title)
        heading.setObjectName("PageTitle")
        heading.setAlignment(Qt.AlignCenter)
        self.ring = ProgressRing("fingerprint")
        self.ring.set_progress(-1)
        self.label = QLabel("Bitte warten …")
        self.label.setWordWrap(True)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setFont(font(12, QFont.Medium))
        self.label.setMinimumHeight(52)
        self.stage = QLabel("")
        self.stage.setObjectName("Muted")
        self.stage.setAlignment(Qt.AlignCenter)
        self.button = button("Abbrechen", "x")
        self.button.clicked.connect(self._button)
        self.finished_ok = False
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 20)
        lay.setSpacing(12)
        lay.addWidget(heading)
        lay.addWidget(self.ring, 0, Qt.AlignCenter)
        lay.addWidget(self.label)
        lay.addWidget(self.stage)
        lay.addWidget(self.button, 0, Qt.AlignCenter)

    def progress(self, text, stage, total):
        self.label.setText(text)
        if total > 0:
            self.ring.set_progress(stage / total)
            self.stage.setText(f"Schritt {min(stage, total)} von {total}")

    def finish(self, text, ok):
        self.finished_ok = ok
        self.label.setText(text)
        self.ring.set_state("ok" if ok else "error")
        self.button.setText("Schließen")
        self.button.setIcon(icons.icon("check", theme.current().text, 18))

    def _button(self):
        if self.button.text() == "Abbrechen":
            self.backend.cancel()
            self.button.setEnabled(False)
        else:
            self.accept()

    def closeEvent(self, event):
        if self.button.text() == "Abbrechen":
            self.backend.cancel()
        super().closeEvent(event)


class FingerprintPage(QWidget):
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.backend = controller.fingerprint
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        self.status = Banner("Sensoren werden gesucht …", "busy")
        lay.addWidget(self.status)

        auto_box = QGroupBox("Automatisch einrichten")
        al = QHBoxLayout(auto_box)
        auto_text = QLabel("Installieren · Sensor finden · Finger anlernen · Anmeldung an" if not IS_WINDOWS else
                           "Sensor finden · Windows Hello öffnen · Test-Scan")
        auto_text.setWordWrap(True)
        self.auto_btn = button("Automatisch einrichten …", "fingerprint", primary=True)
        self.auto_btn.clicked.connect(self.auto_setup)
        al.addWidget(auto_text, 1)
        al.addWidget(self.auto_btn)
        lay.addWidget(auto_box)

        sensor_box = QGroupBox("Sensor")
        form = QFormLayout(sensor_box)
        self.sensor_combo = QComboBox()
        self.sensor_combo.currentIndexChanged.connect(self.reload_enrolled)
        refresh = button("Neu suchen", "refresh")
        refresh.clicked.connect(self.reload)
        row = QHBoxLayout()
        row.addWidget(self.sensor_combo, 1)
        row.addWidget(refresh)
        form.addRow("Sensor:", row)
        lay.addWidget(sensor_box)

        finger_box = QGroupBox("Finger")
        fl = QVBoxLayout(finger_box)
        hint = QLabel("Finger wählen · grün = angelernt")
        hint.setObjectName("Muted")
        fl.addWidget(hint)
        self.hands = HandPicker()
        self.hands.fingerClicked.connect(self._finger_clicked)
        fl.addWidget(self.hands)
        self.enrolled = QListWidget()
        self.enrolled.setMaximumHeight(96)
        caption = QLabel("Angelernte Finger")
        caption.setObjectName("Muted")
        fl.addWidget(caption)
        fl.addWidget(self.enrolled)

        enroll_row = QHBoxLayout()
        self.finger_combo = QComboBox()
        for key, label in FINGERS:
            self.finger_combo.addItem(label, key)
        self.finger_combo.currentIndexChanged.connect(self._combo_changed)
        self.enroll_btn = button("Finger anlernen …", "fingerprint", primary=True)
        self.enroll_btn.clicked.connect(self.enroll)
        enroll_row.addWidget(self.finger_combo, 1)
        enroll_row.addWidget(self.enroll_btn)
        fl.addLayout(enroll_row)

        act_row = QHBoxLayout()
        self.test_btn = button("Test-Scan", "check")
        self.test_btn.clicked.connect(self.verify)
        self.delete_btn = button("Ausgewählten Finger löschen", "trash", danger=True)
        self.delete_btn.clicked.connect(self.delete_selected)
        self.delete_all_btn = button("Alle löschen", "trash", danger=True)
        self.delete_all_btn.clicked.connect(self.delete_all)
        act_row.addWidget(self.test_btn)
        act_row.addWidget(self.delete_btn)
        act_row.addWidget(self.delete_all_btn)
        act_row.addStretch(1)
        fl.addLayout(act_row)
        self.hello_note = QLabel("Anlernen/Löschen nur über Windows Hello")
        self.hello_note.setWordWrap(True)
        fl.addWidget(self.hello_note)
        lay.addWidget(finger_box)

        self.login_box = QGroupBox("Anmelden mit Fingerabdruck")
        ll = QVBoxLayout(self.login_box)
        self.login_label = QLabel()
        self.login_label.setWordWrap(True)
        self.login_btn = button("", "lock")
        self.login_btn.clicked.connect(self.toggle_login)
        ll.addWidget(self.login_label)
        ll.addWidget(self.login_btn, 0, Qt.AlignLeft)
        lay.addWidget(self.login_box)
        self.win_box = QGroupBox("Anmelden mit Fingerabdruck")
        wl = QVBoxLayout(self.win_box)
        self.win_text = QLabel()
        self.win_text.setWordWrap(True)
        self.win_btn = button("Anmeldeoptionen öffnen", "lock")
        self.win_btn.clicked.connect(self.backend.open_system_settings)
        wl.addWidget(self.win_text)
        wl.addWidget(self.win_btn, 0, Qt.AlignLeft)
        lay.addWidget(self.win_box)
        self._apply_capabilities()
        lay.addStretch(1)
        self._set_enabled(False)
        QTimer.singleShot(0, self.reload)

    # ------------------------------------------------------------ Finger wählen
    def _finger_clicked(self, finger: str):
        i = self.finger_combo.findData(finger)
        if i >= 0:
            self.finger_combo.setCurrentIndex(i)
        # angelernten Finger auch in der Liste markieren (zum Löschen)
        for row in range(self.enrolled.count()):
            item = self.enrolled.item(row)
            if finger in finger_keys_from(self.backend, [item.data(Qt.UserRole)]):
                self.enrolled.setCurrentItem(item)
                break

    def _combo_changed(self, _i):
        finger = self.finger_combo.currentData()
        self.hands.set_selected(finger)
        if self.backend.can_enroll:
            name = self.finger_combo.currentText()
            self.enroll_btn.setText(f"{name} anlernen …")

    # ------------------------------------------------------------ Laden
    def _apply_capabilities(self):
        """Oberfläche an den gefundenen Sensor anpassen (Modul am seriellen Anschluss ↔ System)."""
        b = self.backend
        serial = bool(getattr(b, "is_serial", False))
        self.finger_combo.setVisible(b.can_enroll)
        self.hands.setVisible(b.can_enroll)
        self.enroll_btn.setText(f"{self.finger_combo.currentText()} anlernen …" if b.can_enroll
                                else "Finger anlernen (Windows Hello öffnen) …")
        self.delete_btn.setVisible(b.can_delete)
        self.delete_all_btn.setVisible(b.can_delete)
        self.hello_note.setVisible(IS_WINDOWS and not serial)
        self.login_box.setVisible(bool(b.login_toggle))
        self.win_box.setVisible(IS_WINDOWS)
        if IS_WINDOWS and serial:
            self.win_text.setText("Serielles Modul: nur Anlernen/Prüfen · Windows-Anmeldung braucht Hello-Treiber")
            self.win_btn.hide()
        else:
            self.win_text.setText("An, sobald ein Finger in Windows Hello angelernt ist")
            self.win_btn.show()

    def _set_enabled(self, on):
        for w in (self.enroll_btn, self.test_btn, self.delete_btn, self.delete_all_btn, self.finger_combo):
            w.setEnabled(on)
        if IS_WINDOWS and not self.backend.can_enroll:
            self.enroll_btn.setEnabled(True)  # Einstellungen öffnen geht immer

    def sensor_id(self):
        return self.sensor_combo.currentData()

    def reload(self):
        self.status.set("Sensoren werden gesucht …", "busy")

        def work():
            ok, msg = self.backend.availability()
            sensors = self.backend.list_sensors() if ok else []
            return ok, msg, sensors

        def done(result):
            ok, msg, sensors = result
            self._apply_capabilities()
            self.sensor_combo.blockSignals(True)
            self.sensor_combo.clear()
            for s in sensors:
                self.sensor_combo.addItem(s.name + (f" ({s.detail})" if s.detail else ""), s.id)
            self.sensor_combo.blockSignals(False)
            if ok:
                n = len(sensors)
                self.status.set(f"{n} Sensor{'en' if n != 1 else ''} gefunden – über {self.backend.name}.", "ok")
            else:
                hint = self.backend.install_hint()
                self.status.set(msg + (f"\n{hint}" if hint else ""), "warn")
            self._set_enabled(ok)
            self.reload_enrolled()
            self.reload_login()

        run_async(work, done, lambda e: self.status.set(f"Fehler: {e}", "error"))

    def reload_enrolled(self):
        self.enrolled.clear()
        sid = self.sensor_id()
        if sid is None or not self.backend.can_list_enrolled:
            return

        def done(fingers):
            self.enrolled.clear()
            if not fingers:
                item = QListWidgetItem("(noch keine)")
                item.setFlags(Qt.NoItemFlags)
                self.enrolled.addItem(item)
            for f in fingers:
                item = QListWidgetItem(icons.icon("fingerprint", theme.current().accent, 20), self.backend.finger_label(f))
                item.setData(Qt.UserRole, f)
                self.enrolled.addItem(item)
            self.hands.set_enrolled(finger_keys_from(self.backend, fingers))

        def failed(text):
            self.enrolled.clear()
            item = QListWidgetItem(f"Liste nicht verfügbar: {text}")
            item.setFlags(Qt.NoItemFlags)
            self.enrolled.addItem(item)

        run_async(lambda: self.backend.list_enrolled(sid), done, failed)

    def reload_login(self):
        if not self.backend.login_toggle:
            return
        state = self.backend.login_enabled()
        if state is None:
            self.login_label.setText("Status unbekannt.")
            self.login_btn.setText("Einschalten")
        elif state:
            self.login_label.setText("An: Anmelden · Sperrbildschirm · sudo (Passwort geht weiter)")
            self.login_btn.setText("Ausschalten")
        else:
            self.login_label.setText("Ausgeschaltet: Anmelden nur mit Passwort.")
            self.login_btn.setText("Einschalten")
        self._login_state = state

    # ------------------------------------------------------------ Aktionen
    def auto_setup(self):
        """Erst klären, welcher Sensor-Weg gilt (Modul am Adapter oder System), dann den Assistenten
        passend dazu aufbauen – sonst fehlen z. B. Schritte oder die Finger-Auswahl."""
        from .fingerprint_wizard import FingerprintWizard

        self.auto_btn.setEnabled(False)
        self.status.set("Sensor wird gesucht …", "busy")

        def open_wizard(_result=None):
            self.auto_btn.setEnabled(True)
            self._apply_capabilities()
            wizard = FingerprintWizard(self.backend, self, self.finger_combo.currentData())
            wizard.exec()
            self.reload()

        run_async(self.backend.availability, open_wizard, lambda _e: open_wizard())

    def _scan(self, title, fn, success_text=None, after=None):
        dlg = ScanDialog(self.backend, title, self)

        def done(result):
            if isinstance(result, tuple):
                ok, text = result
            else:
                ok, text = True, success_text or "Fertig."
            dlg.finish(text, ok)
            if after:
                after()

        def failed(text):
            dlg.finish(text, False)
            if after:
                after()

        run_async(fn, done, failed, dlg.progress)
        dlg.exec()

    def enroll(self):
        if not self.backend.can_enroll:
            self.backend.open_system_settings()
            return
        sid, finger = self.sensor_id(), self.finger_combo.currentData()
        if sid is None:
            return
        self._scan(f"{self.finger_combo.currentText()} anlernen",
                   lambda status: self.backend.enroll(sid, finger, status),
                   "Finger erfolgreich angelernt.", self.reload_enrolled)

    def verify(self):
        sid = self.sensor_id()
        if sid is None:
            return
        self._scan("Test-Scan", lambda status: self.backend.verify(sid, status))

    def delete_selected(self):
        item = self.enrolled.currentItem()
        finger = item.data(Qt.UserRole) if item else None
        if not finger:
            QMessageBox.information(self, "Löschen", "Bitte zuerst einen Finger in der Liste auswählen.")
            return
        self._delete(finger, f"{item.text()} wirklich löschen?")

    def delete_all(self):
        self._delete("*", "Wirklich ALLE angelernten Finger auf diesem Sensor löschen?")

    def _delete(self, finger, question):
        if QMessageBox.question(self, "Löschen", question) != QMessageBox.Yes:
            return
        sid = self.sensor_id()
        run_async(lambda: self.backend.delete(sid, finger), lambda _r: self.reload_enrolled(),
                  lambda e: error_box(self, f"Löschen fehlgeschlagen: {e}"))

    def toggle_login(self):
        enable = not bool(getattr(self, "_login_state", False))
        if enable:
            text = ("Anmeldung mit Fingerabdruck einschalten?\n\nDas ändert die PAM-Einstellungen "
                    "des Systems (über pam-auth-update). Du wirst nach deinem Passwort gefragt. "
                    "Das Passwort funktioniert danach weiterhin.")
        else:
            text = "Anmeldung mit Fingerabdruck ausschalten?"
        if QMessageBox.question(self, "Anmeldung", text) != QMessageBox.Yes:
            return
        allow_multi = False
        warning = getattr(self.backend, "multi_user_warning", lambda: "")() if enable else ""
        if warning:
            box = QMessageBox(QMessageBox.Warning, "Mehrere Benutzer", warning, parent=self)
            box.addButton("Trotzdem einschalten", QMessageBox.AcceptRole)
            cancel = box.addButton("Abbrechen", QMessageBox.RejectRole)
            box.setDefaultButton(cancel)
            box.exec()
            if box.clickedButton() is cancel:
                return
            allow_multi = True
        self.login_btn.setEnabled(False)

        def finished(*_):
            self.login_btn.setEnabled(True)
            self.reload_login()

        def failed(e):
            finished()
            error_box(self, f"Konnte nicht geändert werden: {e}")

        if allow_multi:
            run_async(lambda: self.backend.set_login_enabled(enable, allow_multi=True), finished, failed)
        else:
            run_async(lambda: self.backend.set_login_enabled(enable), finished, failed)
