"""Sperrbildschirm für AluPC: entsperren per Fingerabdruck oder Ersatz-PIN."""

from __future__ import annotations

import hmac

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QLineEdit, QVBoxLayout

from .setup_page import hash_pin
from .util import run_async
from .widgets import ProgressRing, button


class LockDialog(QDialog):
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.backend = controller.fingerprint
        self.setWindowTitle("AluPC ist gesperrt")
        self.setMinimumWidth(440)
        self.setWindowFlag(Qt.WindowCloseButtonHint, False)
        self.ring = ProgressRing("lock")
        self.ring.set_progress(0)
        title = QLabel("AluPC ist gesperrt")
        title.setObjectName("PageTitle")
        title.setAlignment(Qt.AlignCenter)
        self.status = QLabel("Finger auf den Sensor legen – oder die Ersatz-PIN eingeben.")
        self.status.setObjectName("Muted")
        self.status.setAlignment(Qt.AlignCenter)
        self.status.setWordWrap(True)
        self.status.setMinimumHeight(40)
        self.scan_btn = button("Mit Fingerabdruck entsperren", "fingerprint", primary=True)
        self.scan_btn.clicked.connect(self.scan)
        self.pin = QLineEdit()
        self.pin.setEchoMode(QLineEdit.Password)
        self.pin.setPlaceholderText("Ersatz-PIN")
        self.pin.setMinimumHeight(36)
        self.pin.returnPressed.connect(self.check_pin)
        pin_btn = button("Entsperren", "lock")
        pin_btn.clicked.connect(self.check_pin)
        row = QHBoxLayout()
        row.addWidget(self.pin, 1)
        row.addWidget(pin_btn)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(30, 26, 30, 24)
        lay.setSpacing(14)
        lay.addWidget(self.ring, 0, Qt.AlignCenter)
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
        self.ring.restart()

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
                self.ring.set_state("ok")
                QTimer.singleShot(350, self.accept)
            else:
                self.ring.set_state("error")
                self.status.setText(text)

        def failed(text):
            self._scanning = False
            self.scan_btn.setEnabled(True)
            self.ring.set_state("error")
            self.status.setText(text)

        run_async(work, done, failed, lambda text, *_: self.status.setText(text))

    def check_pin(self):
        lock = self.controller.config["lock"]
        if lock.get("pin_hash") and hmac.compare_digest(hash_pin(self.pin.text(), lock.get("pin_salt", "")),
                                                        lock["pin_hash"]):
            self.accept()
        else:
            self.ring.set_state("error")
            self.status.setText("PIN falsch.")
            self.pin.clear()

    def done(self, result):
        self.backend.cancel()
        super().done(result)

    def reject(self):
        pass  # Escape schließt die Sperre nicht
