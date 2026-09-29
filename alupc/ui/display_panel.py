"""Fenster „Displays“: Helligkeit je Monitor, einzelne oder alle Monitore ausschalten."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QDialog, QGridLayout, QHBoxLayout, QLabel, QSlider, QVBoxLayout

from .util import run_async
from .widgets import button, page_header

METHODS = {"ddc": "Monitor", "laptop": "Laptop", "abdunkeln": "per AluPC"}
METHOD_TIPS = {
    "ddc": "Echte Helligkeit des Monitors (über das Monitorkabel, DDC/CI)",
    "laptop": "Helligkeit des Laptop-Bildschirms",
    "abdunkeln": "Der Monitor lässt sich nicht direkt steuern – AluPC dunkelt das Bild ab (Klicks gehen durch)",
}


class DisplayPanel(QDialog):
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.displays = controller.displays
        self.setWindowTitle("Displays")
        self.setMinimumWidth(520)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 20, 22, 18)
        lay.setSpacing(12)
        lay.addWidget(page_header("Displays", "Helligkeit · Ausschalten", "sun"))
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)
        self.rows = {}
        out = controller.output_screen()
        for row, screen in enumerate(self.displays.screens()):
            name = screen.name()
            label = QLabel(f"<b>{'Monitor 2' if out is not None and name == out.name() else 'Monitor 1' if row == 0 else f'Monitor {row + 1}'}</b>"
                           f"<br><span style='font-size:8.5pt'>{screen.model() or name}</span>")
            slider = QSlider(Qt.Horizontal)
            slider.setRange(0, 100)
            slider.setValue(self.displays.software.get(name, 100))
            slider.setEnabled(False)  # erst nach dem Nachfragen (kann bei DDC/CI ~1 s dauern)
            value = QLabel("…")
            value.setMinimumWidth(96)
            value.setObjectName("Muted")
            off = button("Aus", "power")
            off.setToolTip("Nur diesen Monitor ausschalten – Taste oder Maus schaltet ihn wieder ein")
            off.clicked.connect(lambda _=False, n=name: self._off(n))
            grid.addWidget(label, row, 0)
            grid.addWidget(slider, row, 1)
            grid.addWidget(value, row, 2)
            grid.addWidget(off, row, 3)
            grid.setColumnStretch(1, 1)
            timer = QTimer(self, singleShot=True, interval=250)  # beim Ziehen nicht jeden Schritt senden
            self.rows[name] = {"slider": slider, "value": value, "timer": timer, "method": None}
            timer.timeout.connect(lambda n=name: self._apply(n))
            slider.valueChanged.connect(lambda v, n=name: self._moved(n, v))
            self._load(name)
        lay.addLayout(grid)
        hint = QLabel("Ausgeschaltet? Eine Taste drücken oder die Maus bewegen – dann geht alles wieder an.")
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        lay.addWidget(hint)
        row = QHBoxLayout()
        all_off = button("Alle Displays aus", "power", primary=True)
        all_off.clicked.connect(self._all_off)
        close = button("Schließen", "check")
        close.clicked.connect(self.accept)
        row.addWidget(all_off)
        row.addStretch(1)
        row.addWidget(close)
        lay.addLayout(row)

    def _load(self, name: str) -> None:
        def work():
            method = self.displays.method(name)
            return method, self.displays.get_brightness(name, method)

        def done(result):
            method, value = result
            r = self.rows[name]
            r["method"] = method
            r["slider"].blockSignals(True)
            r["slider"].setValue(value)
            r["slider"].blockSignals(False)
            r["slider"].setEnabled(True)
            self._show_value(name, value)

        run_async(work, done, lambda _e: done(("abdunkeln", self.displays.software.get(name, 100))))

    def _show_value(self, name: str, value: int) -> None:
        r = self.rows[name]
        r["value"].setText(f"{value} % · {METHODS.get(r['method'], '')}")
        r["value"].setToolTip(METHOD_TIPS.get(r["method"], ""))

    def _moved(self, name: str, value: int) -> None:
        self._show_value(name, value)
        if self.rows[name]["method"] == "abdunkeln":
            self._apply(name)  # Abdunkeln ist sofort – gleich mitziehen
        else:
            self.rows[name]["timer"].start()

    def _apply(self, name: str) -> None:
        r = self.rows[name]
        value, method = r["slider"].value(), r["method"]
        if method == "abdunkeln":
            self.displays.set_brightness(name, value, method)
            return

        def done(ok):
            self.displays.apply_result(name, value, ok)
            if not ok:  # Monitor hat nicht reagiert → ab jetzt abdunkeln
                r["method"] = "abdunkeln"
                self._show_value(name, value)

        # echte Helligkeit im Hintergrund (DDC/CI braucht ~1 s), Abdunkel-Ebene danach im GUI-Thread
        run_async(lambda: self.displays.set_hardware(name, value, method), done, lambda _e: done(False))

    def _off(self, name: str) -> None:
        self.displays.off(name)

    def _all_off(self) -> None:
        self.accept()
        self.controller.displays_off()
