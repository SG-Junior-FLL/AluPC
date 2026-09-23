"""Sperrbildschirm für AluPC: entsperren per Fingerabdruck oder Ersatz-PIN."""

from __future__ import annotations

import hmac

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout

from .setup_page import hash_pin
from .util import run_async


class LockDialog(QDialog):
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.backend = controller.fingerprint
        self.setWindowTitle("AluPC ist gesperrt")
        self.setMinimumWidth(420)
        self.setWindowFlag(Qt.WindowCloseButtonHint, False)
        title = QLabel("🔒 AluPC ist gesperrt")
        font = title.font()
        font.setPointSize(font.pointSize() + 6)
        title.setFont(font)
        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.scan_btn = QPushButton("Mit Fingerabdruck entsperren")
        self.scan_btn.clicked.connect(self.scan)
        self.pin = QLineEdit()
        self.pin.setEchoMode(QLineEdit.Password)
        self.pin.setPlaceholderText("Ersatz-PIN")
        self.pin.returnPressed.connect(self.check_pin)
        pin_btn = QPushButton("OK")
        pin_btn.clicked.connect(self.check_pin)
        row = QHBoxLayout()
        row.addWidget(self.pin, 1)
        row.addWidget(pin_btn)
        lay = QVBoxLayout(self)
        lay.addWidget(title)
        lay.addWidget(self.status)
        lay.addWidget(self.scan_btn)
        lay.addLayout(row)
        self._scanning = False
        QTimer.singleShot(200, self.scan)

    def scan(self):
        if self._scanning:
            return
        self._scanning = True
        self.scan_btn.setEnabled(False)

        def work(status):
            ok, msg = self.backend.availability()
            if not ok:
                return (False, msg)
            sensors = self.backend.list_sensors()
            return self.backend.verify(sensors[0].id, status)

        def done(result):
            self._scanning = False
            self.scan_btn.setEnabled(True)
            ok, text = result
            if ok:
                self.accept()
            else:
                self.status.setText(text)

        def failed(text):
            self._scanning = False
            self.scan_btn.setEnabled(True)
            self.status.setText(text)

        run_async(work, done, failed, lambda text, *_: self.status.setText(text))

    def check_pin(self):
        lock = self.controller.config["lock"]
        if lock.get("pin_hash") and hmac.compare_digest(hash_pin(self.pin.text(), lock.get("pin_salt", "")),
                                                        lock["pin_hash"]):
            self.accept()
        else:
            self.status.setText("PIN falsch.")
            self.pin.clear()

    def done(self, result):
        self.backend.cancel()
        super().done(result)

    def reject(self):
        pass  # Escape schließt die Sperre nicht
