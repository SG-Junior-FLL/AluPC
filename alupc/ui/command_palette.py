"""Befehlssuche (Strg+K): eintippen, was passieren soll – „licht blau“, „szene pause“, „timer 5 minuten“, „setup
sprache“. Oben steht, was AluPC aus dem Satz versteht (wie bei der Sprachsteuerung), darunter passende Befehle,
Szenen und Seiten. Pfeiltasten wählen, Enter führt aus, Esc schließt."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem, QVBoxLayout

from .. import startpage
from ..voice import fold
from . import icons, theme
from .widgets import font

# Seiten der Seitenleiste: Text → Seiten-Nummer im Stapel
PAGES = [("Start", 0, "home"), ("Szenen", 1, "scenes"), ("System", 4, "gauge"), ("Setup", 2, "sliders"),
         ("Fingerabdruck", 3, "fingerprint")]


def entries(controller) -> list[tuple[str, str, str, str]]:
    """(Anzeige, Suchtext, Symbol, Aktion) – Aktion: „cmd:…“, „page:N“, „setup:Titel“."""
    out = []
    for label, index, icon in PAGES:
        out.append((f"Seite: {label}", label, icon, f"page:{index}"))
    try:
        from .setup_page import SetupPage

        for icon, title, sub in SetupPage.SECTIONS:
            out.append((f"Setup → {title}", f"setup einstellungen {title} {sub}", icon, f"setup:{title}"))
    except Exception:  # noqa: BLE001
        pass
    for name in controller.config.scene_names():
        out.append((f"Szene zeigen: {name}", f"szene {name}", "scenes", f"cmd:szene:{name}"))
    seen = set()
    for cmd, label in {**startpage.COMMANDS, "kamera": "Kamera zeigen", "system": "Systemstatus zeigen",
                       "airplay": "AirPlay (iPhone) zeigen", "qr": "Handy-Steuerung (QR-Code)",
                       "sperren": "Computer sperren"}.items():
        if cmd in seen:
            continue
        seen.add(cmd)
        out.append((label, f"{label} {cmd.replace('_', ' ')}", "play", f"cmd:{cmd}"))
    return out


def matches(query: str, items):
    """Alle Wörter der Suche müssen vorkommen; Treffer am Wortanfang zuerst."""
    q = fold(query).split()
    if not q:
        return list(items)
    scored = []
    for item in items:
        hay = fold(item[0] + " " + item[1])
        words = hay.split()
        if all(any(w.startswith(t) for w in words) or t in hay for t in q):
            starts = sum(1 for t in q if any(w.startswith(t) for w in words))
            scored.append((-starts, len(item[0]), item))
    scored.sort(key=lambda x: (x[0], x[1]))
    return [s[2] for s in scored]


class CommandPalette(QDialog):
    def __init__(self, window, parent=None):
        super().__init__(parent or window)
        self.window_ = window
        self.controller = window.controller
        self.setWindowTitle("Befehlssuche")
        self.setModal(True)
        self.setMinimumWidth(560)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(8)
        self.edit = QLineEdit()
        self.edit.setPlaceholderText("Was soll AluPC tun?  z. B. Licht blau · Szene Pause · Timer 5 Minuten · Setup Sprache")
        self.edit.setFont(font(12))
        self.edit.setMinimumHeight(44)
        self.edit.setClearButtonEnabled(True)
        lay.addWidget(self.edit)
        self.list = QListWidget()
        self.list.setIconSize(QSize(18, 18))
        self.list.setMinimumHeight(320)
        self.list.setUniformItemSizes(True)
        lay.addWidget(self.list)
        self.status = QLabel("↑↓ wählen · Enter ausführen · Esc schließen")
        self.status.setObjectName("Muted")
        self.status.setWordWrap(True)
        lay.addWidget(self.status)
        self.items = entries(self.controller)
        self.edit.textChanged.connect(self._fill)
        self.edit.returnPressed.connect(self.run_selected)
        self.list.itemActivated.connect(lambda _it: self.run_selected())
        self._fill("")

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key_Down, Qt.Key_Up) and self.list.count():
            row = self.list.currentRow() + (1 if e.key() == Qt.Key_Down else -1)
            self.list.setCurrentRow(max(0, min(self.list.count() - 1, row)))
            return
        super().keyPressEvent(e)

    def _fill(self, text: str) -> None:
        t = theme.current()
        self.list.clear()
        text = text.strip()
        if text:  # 1) was die Sprachsteuerung aus dem Satz macht
            from ..intents import understand
            from ..voice import wake_span

            words = fold(text).split()
            span = wake_span(words)
            if span:
                words = words[:span[0]] + words[span[1]:]
            try:
                hit = understand(words, self.controller.config.scene_names(),
                                 self.controller.config["voice"].get("custom") or []) if words else None
            except Exception:  # noqa: BLE001
                hit = None
            if hit:
                item = QListWidgetItem(icons.icon("mic", t.accent, 18), f"„{text}“  →  {hit[1]}")
                item.setData(Qt.UserRole, f"ask:{text}")
                f = font(10.5)
                f.setBold(True)
                item.setFont(f)
                item.setForeground(QColor(t.accent))
                self.list.addItem(item)
        for label, _hay, icon, action in matches(text, self.items)[:40]:
            item = QListWidgetItem(icons.icon(icon, t.muted, 18), label)
            item.setData(Qt.UserRole, action)
            self.list.addItem(item)
        if self.list.count():
            self.list.setCurrentRow(0)
        elif text:
            self.status.setText("Nichts gefunden – anders formulieren, z. B. „Kamera zeigen“")

    def run_selected(self) -> None:
        item = self.list.currentItem()
        if item is None:
            return
        action = item.data(Qt.UserRole)
        w, c = self.window_, self.controller
        if action.startswith("ask:"):
            result = c.ask(action[4:])
            c.message.emit(result["reply"] or result["label"])
        elif action.startswith("page:"):
            w._go(int(action[5:]))
        elif action.startswith("setup:"):
            w.open_setup_section(action[6:])
        elif action.startswith("cmd:"):
            c.run_command(action[4:])
        self.accept()
