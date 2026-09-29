"""Kachel „Programm“: ein Programm auf Monitor 2 bringen."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..sources import capturable_windows
from . import icons, theme
from .widgets import button, page_header


@dataclass
class Program:
    title: str
    app: str = ""
    minimized: bool = False
    window_id: str = ""

    def label(self) -> str:
        extra = [x for x in (self.app, "minimiert" if self.minimized else "") if x]
        return self.title + (f"   ·  {' · '.join(extra)}" if extra else "")


def system_windows(backend) -> list | None:
    """Fensterliste des Systems (Windows: echte Programmfenster, ohne Desktop/Taskleiste) – None,
    wenn das System keine liefert."""
    if not backend.can_list:
        return None
    try:
        return backend.list_windows()
    except Exception:  # noqa: BLE001
        return None


def capture_programs(backend) -> list[Program]:
    """Aufnehmbare Programme. Qt liefert unter Windows auch unsichtbare Systemfenster (z. B.
    „Program Manager“) – die werden mit der Fensterliste des Systems herausgefiltert."""
    from ..sources import kwin_window_mode

    if kwin_window_mode():  # KDE/Wayland: KWin kennt alle Fenster (Qt nur alte X11-Programme)
        from ..platform import kwin_capture

        return [Program(w["title"], w.get("app", ""), bool(w.get("minimized"))) for w in kwin_capture.window_list()
                if w.get("title")]
    known = {w.title: w for w in system_windows(backend) or []}
    result, seen = [], set()
    for w in capturable_windows():
        title = w.description()
        if title in seen:
            continue
        seen.add(title)
        info = known.get(title)
        if known and info is None:
            continue
        result.append(Program(title, info.app if info else "", bool(info and info.minimized)))
    return result


class ProgramList(QWidget):
    """Liste mit Suchfeld; lädt sich alle 3 Sekunden selbst neu und behält die Auswahl."""

    def __init__(self, loader, empty_text: str, parent=None):
        super().__init__(parent)
        self.loader = loader
        self.empty_text = empty_text
        self.search = QLineEdit()
        self.search.setPlaceholderText("Suchen …")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._filter)
        self.list = QListWidget()
        self.list.setUniformItemSizes(True)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        lay.addWidget(self.search)
        lay.addWidget(self.list, 1)
        self.timer = QTimer(self, interval=3000)
        self.timer.timeout.connect(self.reload)
        self._keys: list = []
        self.reload()

    def showEvent(self, e):
        self.timer.start()
        super().showEvent(e)

    def hideEvent(self, e):
        self.timer.stop()
        super().hideEvent(e)

    def reload(self):
        try:
            programs = self.loader()
        except Exception as exc:  # noqa: BLE001
            programs = []
            self.empty_text = f"Fensterliste nicht verfügbar: {exc}"
        keys = [(p.title, p.app, p.minimized, p.window_id) for p in programs]
        if keys == self._keys and self.list.count():
            return  # nichts geändert → Liste nicht neu aufbauen (kein Springen)
        self._keys = keys
        current = self.selected()
        self.list.clear()
        color = theme.current().accent
        for p in programs:
            item = QListWidgetItem(icons.icon("window", theme.current().muted if p.minimized else color, 20),
                                   p.label())
            item.setData(Qt.UserRole, p)
            self.list.addItem(item)
            if current is not None and (p.window_id or p.title) == (current.window_id or current.title):
                self.list.setCurrentItem(item)
        if not programs:
            item = QListWidgetItem(self.empty_text)
            item.setFlags(Qt.NoItemFlags)
            self.list.addItem(item)
        self._filter(self.search.text())

    def _filter(self, text: str):
        text = text.strip().lower()
        for i in range(self.list.count()):
            item = self.list.item(i)
            p = item.data(Qt.UserRole)
            item.setHidden(bool(text) and p is not None and text not in p.label().lower())

    def selected(self) -> Program | None:
        item = self.list.currentItem()
        return item.data(Qt.UserRole) if item is not None and not item.isHidden() else None


class ProgramDialog(QDialog):
    """Programm auf Monitor 2: AluPC zeigt eine Kopie des Fensters (das Programm bleibt, wo es ist)."""

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.backend = controller.windows
        self.setWindowTitle("Programm auf Monitor 2")
        self.resize(680, 580)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 20, 22, 18)
        lay.setSpacing(12)
        lay.addWidget(page_header("Programm auf Monitor 2", "Programm wählen · Anzeigen"))
        lay.addWidget(self._capture_tab(), 1)

    # ------------------------------------------------------------ Aufnahme
    def _capture_tab(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        info = QLabel("Vollbild auf Monitor 2 · Fenster darf hinten liegen")
        info.setWordWrap(True)
        self.capture_list = ProgramList(
            lambda: capture_programs(self.backend),
            "Keine Programmfenster gefunden · Programm öffnen, dann erscheint es hier")
        self.capture_list.list.itemDoubleClicked.connect(lambda _i: self._do_capture())
        settings = self.controller.config["program"]
        self.restore_box = QCheckBox("Minimierte Fenster zurückholen")
        self.restore_box.setChecked(bool(settings.get("restore_minimized", True)))
        self.restore_box.setToolTip("Ein minimiertes Programm liefert kein Bild. AluPC holt es dann zurück, "
                                    "legt es aber ganz nach hinten und aktiviert es nicht.")
        self.restore_box.toggled.connect(self._save_restore)
        if not self.backend.can_restore_background:
            self.restore_box.setEnabled(False)
            self.restore_box.setText("Nicht minimieren (nach hinten reicht)")
        show_btn = button("Anzeigen", "play", primary=True)
        show_btn.setDefault(True)
        show_btn.clicked.connect(self._do_capture)
        row = QHBoxLayout()
        row.addWidget(self.restore_box, 1)
        row.addWidget(show_btn)
        lay.addWidget(info)
        lay.addWidget(self.capture_list, 1)
        lay.addLayout(row)
        return page

    def _save_restore(self, on: bool):
        self.controller.config["program"] = {**self.controller.config["program"], "restore_minimized": on}

    def _do_capture(self):
        program = self.capture_list.selected()
        if program is None:
            return
        if program.minimized and self.restore_box.isChecked() and self.backend.can_restore_background:
            try:
                self.backend.restore_in_background(program.title)
            except Exception:  # noqa: BLE001
                pass
        self.controller.show_source({"type": "window", "title": program.title})
        self.accept()
