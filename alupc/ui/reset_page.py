"""Setup → Allgemein: „Alle Daten löschen“ (AluPC zurücksetzen wie nach der Installation)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QDialog, QDialogButtonBox, QGroupBox, QLabel, QMessageBox, \
    QVBoxLayout

from .. import reset
from .util import error_box, run_async
from .widgets import button, page_header

WHAT = ("Einstellungen, Szenen, Startseite, Overlays, Tastenkürzel · vom Handy empfangene Dateien · "
        "Namen der Fingerabdrücke · Browser-Daten (Anmeldungen auf Websites) · Autostart")


class ResetDialog(QDialog):
    def __init__(self, fingerprint_module: bool, login_on: bool, parent=None, sync_on: bool = False):
        super().__init__(parent)
        self.setWindowTitle("Alle Daten löschen")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 20, 22, 18)
        lay.addWidget(page_header("Alle Daten löschen", "AluPC wird wie frisch installiert."))
        what = QLabel("Gelöscht wird: " + WHAT + ".\n\nDas Programm selbst bleibt installiert. "
                      "Danach startet AluPC neu mit der Ersteinrichtung.")
        what.setWordWrap(True)
        lay.addWidget(what)
        self.module = QCheckBox("Fingerabdrücke im Modul löschen")
        self.module.setChecked(True)
        self.module.setVisible(fingerprint_module)
        lay.addWidget(self.module)
        self.login = QCheckBox("Anmelden mit Fingerabdruck ausschalten (fragt nach Rechten)")
        self.login.setChecked(True)
        self.login.setVisible(login_on)
        lay.addWidget(self.login)
        self.sync = QCheckBox("Dual-Boot-Abgleich auch zurücksetzen (sonst holt AluPC die Einstellungen vom "
                              "anderen System zurück)")
        self.sync.setChecked(True)
        self.sync.setVisible(sync_on)
        lay.addWidget(self.sync)
        hint = QLabel("Tipp: Vorher unter „Sichern & Sync“ exportieren, wenn du etwas behalten willst.")
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        lay.addWidget(hint)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Alles löschen")
        buttons.button(QDialogButtonBox.Ok).setObjectName("Danger")
        buttons.button(QDialogButtonBox.Cancel).setText("Abbrechen")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)


def _fingerprint_state(backend):
    """(Modul am Adapter gefunden?, Anmeldung an?) – aus der letzten Suche der Fingerabdruck-Seite, ohne neu
    zu suchen (das würde die Oberfläche kurz einfrieren)."""
    try:
        serial = bool(getattr(backend, "is_serial", False) and getattr(backend.serial, "_found", None))
        login = serial and backend.login_toggle and backend.login_enabled() is not False
        return serial, bool(login)
    except Exception:  # noqa: BLE001
        return False, False


def reset_all(page) -> None:
    controller = page.controller
    backend = controller.fingerprint
    serial, login_on = _fingerprint_state(backend)
    sync = controller.config["sync"]
    dlg = ResetDialog(serial, login_on, page, sync_on=bool(sync.get("enabled") or sync.get("folder")))
    if dlg.exec() != QDialog.Accepted:
        return
    if QMessageBox.warning(page, "Alle Daten löschen", "Wirklich alles löschen? Das lässt sich nicht "
                           "rückgängig machen.", QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
        return
    clear_module = serial and dlg.module.isChecked()
    login_off = login_on and dlg.login.isChecked()

    def work():
        problems = []
        if login_off:
            try:
                backend.set_login_enabled(False)
            except Exception as exc:  # noqa: BLE001
                problems.append(f"Anmeldung: {exc}")
        if clear_module:
            try:
                for sensor in backend.list_sensors():
                    backend.delete(sensor.id, "*")
            except Exception as exc:  # noqa: BLE001
                problems.append(f"Modul: {exc}")
        return problems

    def done(problems):
        if problems and QMessageBox.question(
                page, "Alle Daten löschen", "Nicht alles hat geklappt:\n\n" + "\n".join(problems)
                + "\n\nTrotzdem die Daten von AluPC löschen?") != QMessageBox.Yes:
            return
        reset.request(controller.config, clear_sync=not dlg.sync.isHidden() and dlg.sync.isChecked())

    if login_off or clear_module:
        controller.message.emit("Fingerabdruck wird zurückgesetzt …")
        run_async(work, done, lambda e: error_box(page, f"Fehlgeschlagen: {e}"))
    else:
        done([])


def reset_group(page) -> QGroupBox:
    box = QGroupBox("Zurücksetzen")
    lay = QVBoxLayout(box)  # untereinander: im kleinen Fenster wurde der Knopf rechts abgeschnitten
    text = QLabel("Alle Daten von AluPC löschen – wie frisch installiert")
    text.setWordWrap(True)
    btn = button("Alle Daten löschen …", "trash", danger=True)
    btn.clicked.connect(lambda: reset_all(page))
    lay.addWidget(text)
    lay.addWidget(btn, 0, Qt.AlignLeft)
    return box
