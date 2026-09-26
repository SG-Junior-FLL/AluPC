"""Text anzeigen – wie am Handy: Text eintippen, „Anzeigen“, steht groß auf Monitor 2."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget

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
        hint = QLabel("Strg+Enter = Anzeigen")
        hint.setObjectName("Muted")
        row.addWidget(hint)
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
        self.text.setFocus()

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
        text = self.text.toPlainText().strip()
        if not text:
            self.text.setFocus()
            return
        self.controller.show_text(text)
        self.accept()
