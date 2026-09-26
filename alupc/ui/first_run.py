"""Ersteinrichtung: Beim ersten Start richtet AluPC mit einem Klick alles ein.

Schritte: Monitore erkennen → Spiegeln testen (klappt die Bildaufnahme nicht, spiegelt AluPC künftig
über Windows/KDE) → Handy-Programme installieren (eine Passwortabfrage) → iPhone-Name und Handy-Code →
Autostart.
"""

from __future__ import annotations

import sys

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import QCheckBox, QDialog, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from .. import handy
from . import icons, theme
from .util import run_async
from .widgets import button, font

IS_WINDOWS = sys.platform.startswith("win")


class StepIcon(QWidget):
    """Kreis mit Zustand: wartet (grau), läuft (dreht sich), ok (grün), Hinweis (orange), übersprungen."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.state = "wait"
        self.angle = 0
        self.setFixedSize(30, 30)
        self._spin = QTimer(self, interval=40)
        self._spin.timeout.connect(self._tick)

    def set(self, state: str):
        self.state = state
        if state == "run":
            self._spin.start()
        else:
            self._spin.stop()
        self.update()

    def _tick(self):
        self.angle = (self.angle + 18) % 360
        self.update()

    def paintEvent(self, _e):
        t = theme.current()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(2, 2, -2, -2)
        colors = {"ok": t.success, "warn": t.warning, "skip": t.muted}
        if self.state == "run":
            p.setPen(Qt.NoPen)
            ring = QColor(t.accent)
            ring.setAlphaF(0.2)
            p.setBrush(ring)
            p.drawEllipse(r)
            from PySide6.QtGui import QPen

            p.setPen(QPen(QColor(t.accent), 3, Qt.SolidLine, Qt.RoundCap))
            p.setBrush(Qt.NoBrush)
            p.drawArc(r.adjusted(2, 2, -2, -2), -self.angle * 16, 100 * 16)
        elif self.state in colors:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(colors[self.state]))
            p.drawEllipse(r)
            icons.paint(p, {"ok": "check", "warn": "alert", "skip": "x"}[self.state], r.adjusted(6, 6, -6, -6),
                        "#ffffff", 2.4)
        else:
            from PySide6.QtGui import QPen

            p.setPen(QPen(QColor(t.border), 2))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(r.adjusted(1, 1, -1, -1))
        p.end()


class StepRow(QWidget):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 4, 0, 4)
        lay.setSpacing(12)
        self.icon = StepIcon()
        lay.addWidget(self.icon, 0, Qt.AlignTop)
        col = QVBoxLayout()
        col.setSpacing(1)
        self.title = QLabel(title)
        self.title.setFont(font(11, QFont.DemiBold))
        self.detail = QLabel()
        self.detail.setObjectName("Muted")
        self.detail.setWordWrap(True)
        col.addWidget(self.title)
        col.addWidget(self.detail)
        lay.addLayout(col, 1)

    def set(self, state: str, detail: str = ""):
        self.icon.set(state)
        self.detail.setText(detail)


class FirstRunDialog(QDialog):
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.config = controller.config
        self.setWindowTitle("AluPC einrichten")
        self.setMinimumWidth(640)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 22)
        lay.setSpacing(10)
        head = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(icons.app_icon().pixmap(64, 64))
        head.addWidget(logo)
        names = QVBoxLayout()
        title = QLabel("Willkommen bei AluPC")
        title.setFont(font(18, QFont.Bold))
        sub = QLabel("Ein Klick – alles wird eingerichtet")
        sub.setObjectName("Muted")
        names.addWidget(title)
        names.addWidget(sub)
        head.addSpacing(8)
        head.addLayout(names, 1)
        lay.addLayout(head)
        lay.addSpacing(8)

        self.steps: list[tuple[StepRow, callable]] = []
        self._add("Monitore erkennen", self._step_monitors)
        self._add("Spiegeln testen", self._step_mirror)
        self._add("AirPlay einrichten (iPhone/iPad)", self._step_install)
        self._add("iPhone-Name und Handy-Code festlegen", self._step_names)
        self._add("Mit dem Computer starten", self._step_autostart)
        for row, _fn in self.steps:
            lay.addWidget(row)
        self.autostart = QCheckBox("AluPC beim Anmelden automatisch starten")
        self.autostart.setChecked(True)
        lay.addWidget(self.autostart)
        lay.addStretch(1)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.later = button("Später", "x")
        self.later.clicked.connect(self._later)
        self.go = button("Alles einrichten", "sync", primary=True)
        self.go.clicked.connect(self.start)
        buttons.addWidget(self.later)
        buttons.addWidget(self.go)
        lay.addLayout(buttons)
        self._index = -1
        self.finished_all = False

    def _add(self, title, fn):
        self.steps.append((StepRow(title), fn))

    # ------------------------------------------------------------ Ablauf
    def start(self):
        if self.finished_all:
            self.accept()
            return
        self.go.setEnabled(False)
        self.later.setEnabled(False)
        self.autostart.setEnabled(False)
        self._index = -1
        self._next()

    def _next(self, state: str | None = None, detail: str = ""):
        if state is not None and 0 <= self._index < len(self.steps):
            self.steps[self._index][0].set(state, detail)
        self._index += 1
        if self._index >= len(self.steps):
            self._done()
            return
        row, fn = self.steps[self._index]
        row.set("run", "läuft …")
        QTimer.singleShot(50, fn)

    def _done(self):
        self.finished_all = True
        self.config["first_run_done"] = True
        self.go.setEnabled(True)
        self.go.setText("Fertig")
        self.later.hide()
        self.controller.message.emit("AluPC ist eingerichtet.")

    def _later(self):
        self.config["first_run_done"] = True  # nicht jedes Mal fragen – Setup → Allgemein startet sie erneut
        self.reject()

    # ------------------------------------------------------------ Schritte
    def _step_monitors(self):
        out = self.controller.output_screen()
        if out is None:
            self._next("warn", "Kein Monitor 2 – wird später erkannt")
        else:
            g = out.geometry()
            self._next("ok", f"Monitor 2: {out.name()} ({g.width()} × {g.height()})")

    def _step_mirror(self):
        from ..platform.linux_display import is_wayland
        from ..sources import _kwin_allowed

        main = self.controller.main_screen()
        if main is not None and is_wayland() and not _kwin_allowed(main.name()):
            self._next("skip", "Wayland: wird beim ersten Spiegeln geprüft")
            return
        from ..diagnose import capture_probe

        result = capture_probe(self.controller, 3.0)
        ok = "KEIN Bild" not in result and " 0 Bilder" not in result
        output = dict(self.config["output"])
        if ok:
            output["mirror_method"] = "auto"
            self.config["output"] = output
            self._next("ok", "Spiegeln über AluPC")
        else:
            output["mirror_method"] = "system"
            self.config["output"] = output
            self._next("warn", f"Kein Bild · spiegelt über {self.controller.display.name}")

    def _step_install(self):
        plan = handy.setup_plan(self.config)
        if not plan:
            missing = [] if self.controller.airplay.binary() else ["UxPlay"]
            if missing and not (handy.can_install() or handy.can_winget()):
                self._next("warn", "Automatisch installieren geht hier nicht – fehlt: " + ", ".join(missing))
            else:
                self._next("ok", "Alles schon da.")
            return
        row = self.steps[self._index][0]

        def progress(text, _i, _n):
            row.set("run", text)

        def done(errors):
            if errors:
                self._next("warn", "Nicht alles hat geklappt: " + " · ".join(errors))
            else:
                self.config["handy"] = {**self.config["handy"], "firewall_done": True, "setup_done": True}
                self._next("ok", " · ".join(label for label, _ in plan))

        run_async(lambda status: handy.run_plan(plan, status), done, lambda t: done([t]), on_progress=progress)

    def _step_names(self):
        s = self.config["handy"]
        if s.get("airplay_name", "AluPC") == "AluPC":
            self.config["handy"] = {**s, "airplay_name": handy.default_airplay_name()}
        code = self.controller.cast.code()
        self._next("ok", f"iPhone sieht „{self.config['handy']['airplay_name']}“ · Handy-Code {code[:3]} {code[3:]}")

    def _step_autostart(self):
        from ..platform import autostart

        try:
            autostart.set_enabled(self.autostart.isChecked())
            self._next("ok" if self.autostart.isChecked() else "skip",
                       "Startet beim Anmelden." if self.autostart.isChecked() else "Kein Autostart.")
        except Exception as exc:  # noqa: BLE001
            self._next("warn", f"Autostart ging nicht: {exc}")
