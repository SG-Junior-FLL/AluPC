"""Kachel „Programm“: ein Programm auf Monitor 2 bringen."""

from __future__ import annotations

import sys
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
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..sources import capturable_windows
from . import icons, theme
from .util import error_box, run_async
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
    """Zwei Wege: Programm aufnehmen (AluPC zeigt es) oder Fenster wirklich verschieben."""

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.backend = controller.windows
        self.setWindowTitle("Programm auf Monitor 2")
        self.resize(680, 580)
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.addTab(self._capture_tab(), "Anzeigen (Aufnahme)")
        self.tabs.addTab(self._move_tab(), "Fenster verschieben")
        if not self.capture_list._keys:  # Aufnahme hier nicht möglich → gleich „Verschieben“ zeigen
            self.tabs.setCurrentIndex(1)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 20, 22, 18)
        lay.setSpacing(12)
        lay.addWidget(page_header("Programm auf Monitor 2", "Aufnehmen oder das echte Fenster verschieben."))
        lay.addWidget(self.tabs)

    # ------------------------------------------------------------ Aufnahme
    def _capture_tab(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        info = QLabel("AluPC nimmt das Programm auf und zeigt es im Vollbild auf Monitor 2. Das Programm "
                      "bleibt auf deinem Monitor und darf <b>hinter anderen Fenstern</b> liegen – du kannst "
                      "währenddessen normal weiterarbeiten.")
        info.setWordWrap(True)
        self.capture_list = ProgramList(
            lambda: capture_programs(self.backend),
            "Auf diesem System kann Qt keine einzelnen Fenster aufnehmen (z. B. KDE unter Wayland). "
            "Nutze „Fenster verschieben“.")
        self.capture_list.list.itemDoubleClicked.connect(lambda _i: self._do_capture())
        settings = self.controller.config["program"]
        self.restore_box = QCheckBox("Minimierte Programme automatisch im Hintergrund wiederherstellen")
        self.restore_box.setChecked(bool(settings.get("restore_minimized", True)))
        self.restore_box.setToolTip("Ein minimiertes Programm liefert kein Bild. AluPC holt es dann zurück, "
                                    "legt es aber ganz nach hinten und aktiviert es nicht.")
        self.restore_box.toggled.connect(self._save_restore)
        if not self.backend.can_restore_background:
            self.restore_box.setEnabled(False)
            self.restore_box.setText("Minimierte Programme liefern kein Bild – bitte nicht minimieren "
                                     "(nach hinten legen reicht)")
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

    # ------------------------------------------------------------ Verschieben
    def _move_tab(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        wb = self.backend
        info = QLabel("Das echte Programmfenster wird auf Monitor 2 geschoben und maximiert. "
                      "Du kannst es dort weiter bedienen.")
        info.setWordWrap(True)
        lay.addWidget(info)
        self.fullscreen = QCheckBox("Vollbild statt maximiert (nur Linux)")
        self.fullscreen.setVisible(not sys.platform.startswith("win"))
        lay.addWidget(self.fullscreen)

        self.move_list = None
        if wb.can_list:
            self.move_list = ProgramList(self._move_programs, "Keine Programmfenster gefunden.")
            self.move_list.list.itemDoubleClicked.connect(lambda _i: self._do_move())
            lay.addWidget(self.move_list, 1)
            row = QHBoxLayout()
            row.addStretch(1)
            move_btn = button("Verschieben", "extend", primary=True)
            move_btn.clicked.connect(self._do_move)
            row.addWidget(move_btn)
            lay.addLayout(row)

        if wb.can_move_active:
            box = QLabel("<b>Oder:</b> Klick auf „Anklicken“, dann hast du 4 Sekunden Zeit, "
                         "das gewünschte Programm anzuklicken.")
            box.setWordWrap(True)
            lay.addWidget(box)
            self.countdown_btn = button("Anklicken (4 Sekunden)", "timer")
            self.countdown_btn.clicked.connect(self._start_countdown)
            lay.addWidget(self.countdown_btn)
        if not wb.can_list and not wb.can_move_active:
            lay.addWidget(QLabel("Fenster verschieben ist auf diesem System nicht möglich."))
        if not wb.can_list:
            lay.addStretch(1)
        return page

    def _move_programs(self) -> list[Program]:
        return [Program(w.title, w.app, w.minimized, w.id) for w in self.backend.list_windows()]

    def _target(self):
        screen = self.controller.output_screen()
        if screen is None:
            error_box(self, "Kein zweiter Monitor gefunden.")
            return None
        g = screen.geometry()
        return screen.name(), (g.x(), g.y(), g.width(), g.height())

    def _do_move(self):
        program = self.move_list.selected() if self.move_list else None
        if program is None:
            return
        target = self._target()
        if target is None:
            return
        self.controller.ensure_extended()
        name, rect = target
        try:
            self.backend.move_window(program.window_id, name, rect, self.fullscreen.isChecked())
        except Exception as exc:  # noqa: BLE001
            error_box(self, f"Verschieben fehlgeschlagen: {exc}")
            return
        self.controller.program_moved(program.title)
        self.accept()

    def _start_countdown(self):
        target = self._target()
        if target is None:
            return
        self.controller.ensure_extended()
        self._remaining = 4
        self.countdown_btn.setEnabled(False)
        # AluPC-Fenster aus dem Weg räumen, damit man das Programm anklicken kann. Der Dialog wird nur
        # durchsichtig (nicht versteckt) – sonst würde er sich schließen, bevor der Countdown fertig ist.
        main = self.parent().window() if self.parent() else None
        self.setWindowOpacity(0.0)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        if main is not None:
            main.showMinimized()
        self.lower()
        self._timer = QTimer(self, interval=1000)
        self._timer.timeout.connect(lambda: self._tick(target, main))
        self._timer.start()

    def _tick(self, target, main):
        self._remaining -= 1
        if self._remaining > 0:
            return
        self._timer.stop()
        name, rect = target
        fullscreen = self.fullscreen.isChecked()

        def restore():
            if main is not None:
                main.showNormal()
            self.setWindowOpacity(1.0)
            self.setAttribute(Qt.WA_TransparentForMouseEvents, False)

        def done(_r):
            restore()
            self.controller.program_moved("per Anklicken gewählt")
            self.accept()

        def failed(text):
            restore()
            self.countdown_btn.setEnabled(True)
            error_box(self, f"Verschieben fehlgeschlagen: {text}")

        run_async(lambda: self.backend.move_active_window(name, rect, fullscreen), done, failed)
