"""Fenster „Fehlerbericht“: kurz beschreiben, was passiert ist → ZIP auf dem Desktop."""

from __future__ import annotations

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication, QCheckBox, QDialog, QHBoxLayout, QLabel, QMessageBox, QPlainTextEdit, \
    QVBoxLayout

from .widgets import button, page_header


class BugReportDialog(QDialog):
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.path = None
        self.setWindowTitle("Fehlerbericht")
        self.setMinimumWidth(480)
        lay = QVBoxLayout(self)
        lay.addWidget(page_header("Fehlerbericht", "Eine Datei mit allem, was zum Helfen nötig ist", "alert"))
        self.text = QPlainTextEdit()
        self.text.setPlaceholderText("Was ist passiert? Was hast du davor gemacht?\n"
                                     "z. B. „AirPlay: Ton ja, Bild nein – seit dem Update“")
        self.text.setMinimumHeight(120)
        lay.addWidget(self.text)
        self.shot = QCheckBox("Bild vom AluPC-Fenster mitschicken")
        self.shot.setChecked(True)
        lay.addWidget(self.shot)
        info = QLabel("Enthält: Diagnose, Einstellungen (Codes und PINs geschwärzt), Fehlerprotokolle. "
                      "Kein Bild vom Bildschirm, keine Passwörter.")
        info.setObjectName("Muted")
        info.setWordWrap(True)
        lay.addWidget(info)
        row = QHBoxLayout()
        cancel = button("Abbrechen", "x")
        cancel.clicked.connect(self.reject)
        self.create = button("Bericht erstellen", "download", primary=True)
        self.create.clicked.connect(self.make)
        row.addStretch(1)
        row.addWidget(cancel)
        row.addWidget(self.create)
        lay.addLayout(row)

    def make(self, folder=None, ask: bool = True):
        from .. import bug_report

        window = self.parent().window() if self.parent() is not None else None
        shot = window.grab().toImage() if (self.shot.isChecked() and window is not None) else None
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            self.path = bug_report.build(self.controller, self.text.toPlainText(), shot, folder)
        except Exception as exc:  # noqa: BLE001
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(self, "Fehlerbericht", f"Konnte den Bericht nicht speichern: {exc}")
            return
        QApplication.restoreOverrideCursor()
        QApplication.clipboard().setText(str(self.path))
        self.accept()
        if not ask:
            return
        box = QMessageBox(self.parent())
        box.setWindowTitle("Fehlerbericht")
        box.setText(f"Gespeichert:\n{self.path}\n\nPfad ist kopiert – die Datei einfach weiterschicken.")
        open_btn = box.addButton("Ordner öffnen", QMessageBox.ActionRole)
        box.addButton(QMessageBox.Ok)
        box.exec()
        if box.clickedButton() is open_btn:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.path.parent)))
