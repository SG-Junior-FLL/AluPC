"""Text anzeigen – wie am Handy: Text eintippen, „Anzeigen“, steht groß auf Monitor 2."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (QCheckBox, QDialog, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout,
                               QWidget)

from .widgets import button, page_header


class TextDialog(QDialog):
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle("Text anzeigen")
        self.resize(520, 380)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 20, 22, 18)
        lay.setSpacing(12)
        lay.addWidget(page_header("Text anzeigen", "Eintippen · Anzeigen · steht groß auf Monitor 2", "text"))
        self.text = QPlainTextEdit()
        self.text.setPlaceholderText("Text für Monitor 2")
        current = controller.content or {}
        if current.get("type") == "text" and controller.mode == "content":
            self.text.setPlainText(current.get("text", ""))  # läuft gerade → zum Ändern vorbefüllt
            self.text.selectAll()
        lay.addWidget(self.text, 1)
        self.recent_box = QWidget()
        self.recent = QHBoxLayout(self.recent_box)
        self.recent.setContentsMargins(0, 0, 0, 0)
        self.recent.setSpacing(6)
        self._fill_recent()
        lay.addWidget(self.recent_box)
        row = QHBoxLayout()
        self.live = QCheckBox("Live – sofort auf Monitor 2")
        self.live.setChecked(bool(controller.config.get("text_live", False)))
        self.live.setStyleSheet("QCheckBox { font-weight: 600; }")
        self.live.toggled.connect(self._live_toggled)
        row.addWidget(self.live)
        row.addStretch(1)
        close = button("Schließen")
        close.clicked.connect(self.reject)
        self.show_btn = button("Anzeigen", "text", primary=True)
        self.show_btn.clicked.connect(self.show_text)
        row.addWidget(close)
        row.addWidget(self.show_btn)
        lay.addLayout(row)
        for keys in ("Ctrl+Return", "Ctrl+Enter"):
            QShortcut(QKeySequence(keys), self, activated=self.show_text)
        self.show_btn.setToolTip("Strg+Enter")
        self._live_timer = QTimer(self, singleShot=True, interval=60)  # beim schnellen Tippen kurz bündeln
        self._live_timer.timeout.connect(self._send_live)
        self.text.textChanged.connect(self._text_changed)
        self._sync_live_ui()
        self.text.setFocus()

    # ------------------------------------------------------------ Live
    def _sync_live_ui(self):
        on = self.live.isChecked()
        self.show_btn.setText("Fertig" if on else "Anzeigen")
        self.text.setPlaceholderText("Tippen – erscheint sofort auf Monitor 2" if on else "Text für Monitor 2")

    def _live_toggled(self, on: bool):
        self.controller.config["text_live"] = on
        self._sync_live_ui()
        if on:
            self._send_live()

    def _text_changed(self):
        if self.live.isChecked():
            self._live_timer.start()

    def _send_live(self):
        self.controller.live_text(self.text.toPlainText())

    def done(self, result):
        if self.live.isChecked():  # Live-Text am Ende in „Zuletzt“ merken
            self._live_timer.stop()
            text = self.text.toPlainText().strip()
            if text:
                self._send_live()
                recent = [t for t in self.controller.config.get("recent_texts", []) if t != text]
                self.controller.config["recent_texts"] = [text] + recent[:7]
        super().done(result)

    def _fill_recent(self):
        while self.recent.count():
            item = self.recent.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        texts = self.controller.config.get("recent_texts", [])[:5]
        self.recent_box.setVisible(bool(texts))
        if texts:
            label = QLabel("Zuletzt:")
            label.setObjectName("Muted")
            self.recent.addWidget(label)
        for t in texts:
            short = t.replace("\n", " ")
            chip = QPushButton(short if len(short) <= 22 else short[:21] + "…")
            chip.setObjectName("Chip")
            chip.setToolTip(t)
            chip.setCursor(Qt.PointingHandCursor)
            chip.clicked.connect(lambda _=False, v=t: self.text.setPlainText(v))
            self.recent.addWidget(chip)
        self.recent.addStretch(1)

    def show_text(self):
        if self.live.isChecked():  # läuft schon live – „Fertig“ schließt nur
            self.accept()
            return
        text = self.text.toPlainText().strip()
        if not text:
            self.text.setFocus()
            return
        self.controller.show_text(text)
        self.accept()
