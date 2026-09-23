"""Kachel „Programm“: ein Programm auf Monitor 2 bringen."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
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


class ProgramDialog(QDialog):
    """Zwei Wege: Programm aufnehmen (AluPC zeigt es) oder Fenster wirklich verschieben."""

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle("Programm auf Monitor 2")
        self.resize(640, 540)
        tabs = QTabWidget()
        tabs.setDocumentMode(True)
        tabs.addTab(self._capture_tab(), "Anzeigen (Aufnahme)")
        tabs.addTab(self._move_tab(), "Fenster verschieben")
        if not capturable_windows():
            tabs.setCurrentIndex(1)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 20, 22, 18)
        lay.setSpacing(12)
        lay.addWidget(page_header("Programm auf Monitor 2", "Aufnehmen oder das echte Fenster verschieben."))
        lay.addWidget(tabs)

    # ------------------------------------------------------------ Aufnahme
    def _capture_tab(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        info = QLabel("AluPC nimmt das Programm auf und zeigt es im Vollbild auf Monitor 2. "
                      "Das Programm bleibt auf deinem Monitor – Standbild und Bild-in-Bild funktionieren.")
        info.setWordWrap(True)
        self.capture_list = QListWidget()
        self.capture_list.itemDoubleClicked.connect(lambda _i: self._do_capture())
        reload_btn = button("Neu laden", "refresh")
        reload_btn.clicked.connect(self._fill_capture)
        show_btn = button("Anzeigen", "play", primary=True)
        show_btn.setDefault(True)
        show_btn.clicked.connect(self._do_capture)
        row = QHBoxLayout()
        row.addWidget(reload_btn)
        row.addStretch(1)
        row.addWidget(show_btn)
        lay.addWidget(info)
        lay.addWidget(self.capture_list, 1)
        lay.addLayout(row)
        self._fill_capture()
        return page

    def _fill_capture(self):
        self.capture_list.clear()
        windows = capturable_windows()
        for w in windows:
            if w.description():
                self.capture_list.addItem(QListWidgetItem(icons.icon("window", theme.current().accent, 20),
                                                          w.description()))
        if not windows:
            item = QListWidgetItem("Auf diesem System kann Qt keine einzelnen Fenster aufnehmen "
                                   "(z. B. KDE unter Wayland). Nutze „Fenster verschieben“.")
            item.setFlags(Qt.NoItemFlags)
            self.capture_list.addItem(item)

    def _do_capture(self):
        item = self.capture_list.currentItem()
        if item is None or not item.flags() & Qt.ItemIsEnabled:
            return
        self.controller.show_source({"type": "window", "title": item.text()})
        self.accept()

    # ------------------------------------------------------------ Verschieben
    def _move_tab(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        wb = self.controller.windows
        info = QLabel("Das echte Programmfenster wird auf Monitor 2 geschoben und maximiert. "
                      "Du kannst es dort weiter bedienen.")
        info.setWordWrap(True)
        lay.addWidget(info)
        self.fullscreen = QCheckBox("Vollbild statt maximiert (nur Linux/KDE)")
        lay.addWidget(self.fullscreen)

        self.move_list = QListWidget()
        if wb.can_list:
            self.move_list.itemDoubleClicked.connect(lambda _i: self._do_move())
            lay.addWidget(self.move_list, 1)
            row = QHBoxLayout()
            reload_btn = button("Neu laden", "refresh")
            reload_btn.clicked.connect(self._fill_move)
            move_btn = button("Verschieben", "extend", primary=True)
            move_btn.clicked.connect(self._do_move)
            row.addWidget(reload_btn)
            row.addStretch(1)
            row.addWidget(move_btn)
            lay.addLayout(row)
            self._fill_move()

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
        lay.addStretch(1)
        return page

    def _fill_move(self):
        self.move_list.clear()
        try:
            windows = self.controller.windows.list_windows()
        except Exception as exc:  # noqa: BLE001
            error_box(self, f"Fensterliste nicht verfügbar: {exc}")
            return
        for w in windows:
            item = QListWidgetItem(icons.icon("window", theme.current().accent, 20),
                                   f"{w.title}" + (f"  ({w.app})" if w.app else ""))
            item.setData(Qt.UserRole, w.id)
            item.setData(Qt.UserRole + 1, w.title)
            self.move_list.addItem(item)

    def _target(self):
        screen = self.controller.output_screen()
        if screen is None:
            error_box(self, "Kein zweiter Monitor gefunden.")
            return None
        g = screen.geometry()
        return screen.name(), (g.x(), g.y(), g.width(), g.height())

    def _do_move(self):
        item = self.move_list.currentItem()
        target = self._target()
        if item is None or target is None:
            return
        self.controller.ensure_extended()
        name, rect = target
        try:
            self.controller.windows.move_window(item.data(Qt.UserRole), name, rect, self.fullscreen.isChecked())
        except Exception as exc:  # noqa: BLE001
            error_box(self, f"Verschieben fehlgeschlagen: {exc}")
            return
        self.controller.program_moved(item.data(Qt.UserRole + 1))
        self.accept()

    def _start_countdown(self):
        target = self._target()
        if target is None:
            return
        self.controller.ensure_extended()
        self._remaining = 4
        self.countdown_btn.setEnabled(False)
        # AluPC-Fenster aus dem Weg räumen, damit man das Programm anklicken kann
        main = self.parent().window() if self.parent() else None
        self.hide()
        if main is not None:
            main.showMinimized()
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

        def done(_r):
            self.controller.program_moved("per Anklicken gewählt")
            if main is not None:
                main.showNormal()
            self.accept()

        def failed(text):
            if main is not None:
                main.showNormal()
            error_box(main, f"Verschieben fehlgeschlagen: {text}")
            self.reject()

        run_async(lambda: self.controller.windows.move_active_window(name, rect, fullscreen), done, failed)
