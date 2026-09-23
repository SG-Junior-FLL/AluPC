"""Kleine Helfer für die Oberfläche."""

from __future__ import annotations

import traceback

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QColorDialog, QMessageBox, QPushButton

_running: set = set()


class _Signals(QObject):
    done = Signal(object)
    failed = Signal(str)
    progress = Signal(str, int, int)


class _Task(QRunnable):
    def __init__(self, fn, signals, with_progress):
        super().__init__()
        self.fn, self.signals, self.with_progress = fn, signals, with_progress

    def run(self):
        try:
            if self.with_progress:
                result = self.fn(lambda text, stage, total: self.signals.progress.emit(text, stage, total))
            else:
                result = self.fn()
            self.signals.done.emit(result)
        except Exception as exc:  # noqa: BLE001
            name = type(exc).__name__
            text = str(exc) or name
            if name == "Cancelled":
                text = "Abgebrochen."
            elif not isinstance(exc, RuntimeError):
                traceback.print_exc()
            self.signals.failed.emit(text)


def run_async(fn, on_done=None, on_error=None, on_progress=None):
    """`fn` im Hintergrund ausführen; Rückmeldungen kommen im GUI-Thread an.

    Mit `on_progress` bekommt `fn` eine Funktion status(text, stufe, gesamt) übergeben.
    """
    signals = _Signals()
    _running.add(signals)

    def finish(*_):
        _running.discard(signals)

    if on_done:
        signals.done.connect(on_done)
    if on_error:
        signals.failed.connect(on_error)
    if on_progress:
        signals.progress.connect(on_progress)
    signals.done.connect(finish)
    signals.failed.connect(finish)
    QThreadPool.globalInstance().start(_Task(fn, signals, on_progress is not None))
    return signals


def error_box(parent, text: str, title: str = "AluPC") -> None:
    QMessageBox.warning(parent, title, text)


class ColorButton(QPushButton):
    def __init__(self, color: str = "#000000", parent=None):
        super().__init__(parent)
        self.clicked.connect(self._pick)
        self.set_color(color)

    def set_color(self, color: str) -> None:
        self._color = QColor(color).name()
        fg = "#000000" if QColor(self._color).lightness() > 128 else "#ffffff"
        self.setText(self._color)
        self.setStyleSheet(f"background:{self._color}; color:{fg};")

    def color(self) -> str:
        return self._color

    def _pick(self):
        c = QColorDialog.getColor(QColor(self._color), self, "Farbe wählen")
        if c.isValid():
            self.set_color(c.name())
