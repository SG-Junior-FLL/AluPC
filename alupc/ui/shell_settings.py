"""„Oberfläche anpassen“ – Hintergrund, Desktop-Symbole, Taskleiste, Widgets, Verhalten. Jede Änderung gilt sofort."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
)

from .widgets import button

SIZES = [("Klein", 44), ("Mittel", 56), ("Groß", 72)]


class ShellSettings(QDialog):
    def __init__(self, shell):
        super().__init__(shell)
        self.shell = shell
        self.setWindowTitle("Oberfläche anpassen")
        self.setMinimumWidth(980)
        cfg = shell.cfg()
        outer = QVBoxLayout(self)
        outer.setSpacing(12)
        cols = QHBoxLayout()  # zwei Spalten: passt auch auf Bildschirme mit 900 px Höhe
        cols.setSpacing(14)
        left, right = QVBoxLayout(), QVBoxLayout()
        left.setSpacing(12)
        right.setSpacing(12)
        cols.addLayout(left, 1)
        cols.addLayout(right, 1)
        outer.addLayout(cols)
        lay = left

        bg = QGroupBox("Hintergrund")
        f = QFormLayout(bg)
        self.wall = QComboBox()
        self.wall.addItem("Aurora (in der Akzentfarbe)", "")
        self.wall.addItem("Eigenes Bild …", "bild")
        self.wall.setCurrentIndex(1 if cfg["wallpaper"] else 0)
        self.wall.activated.connect(self._wall)
        f.addRow("Bild:", self.wall)
        self.wall_path = QLabel(cfg["wallpaper"] or "")
        self.wall_path.setObjectName("Muted")
        self.wall_path.setWordWrap(True)
        f.addRow("", self.wall_path)
        lay.addWidget(bg)

        desk = QGroupBox("Desktop-Symbole (aus dem Desktop-Ordner)")
        f = QFormLayout(desk)
        self.icons = QCheckBox("Dateien, Ordner und Verknüpfungen vom Desktop zeigen")
        self.icons.setChecked(bool(cfg["desktop_icons"]))
        self.icons.toggled.connect(lambda on: self._set(desktop_icons=on))
        f.addRow(self.icons)
        self.size = QComboBox()
        for label, px in SIZES:
            self.size.addItem(label, px)
        self.size.setCurrentIndex(min(range(len(SIZES)), key=lambda i: abs(SIZES[i][1] - int(cfg["icon_size"]))))
        self.size.currentIndexChanged.connect(lambda _i: self._set(icon_size=self.size.currentData()))
        f.addRow("Größe:", self.size)
        self.snap = QCheckBox("Am Raster einrasten (sonst ganz frei)")
        self.snap.setChecked(bool(cfg["snap"]))
        self.snap.toggled.connect(lambda on: self._set(snap=on))
        f.addRow(self.snap)
        arrange = button("Symbole automatisch anordnen", "grid")
        arrange.clicked.connect(self.shell.area.arrange)
        f.addRow(arrange)
        lay.addWidget(desk)

        bar = QGroupBox("Taskleiste")
        f = QFormLayout(bar)
        self.center = QCheckBox("Start und Programme in der Mitte (sonst links)")
        self.center.setChecked(bool(cfg["taskbar_center"]))
        self.center.toggled.connect(lambda on: self._set(taskbar_center=on))
        f.addRow(self.center)
        self.secs = QCheckBox("Uhr mit Sekunden")
        self.secs.setChecked(bool(cfg["clock_seconds"]))
        self.secs.toggled.connect(lambda on: self._set(clock_seconds=on))
        f.addRow(self.secs)
        f.addRow(QLabel("Programme anheften: im Startmenü Rechtsklick → „An die Taskleiste anheften“."))
        lay.addWidget(bar)
        lay.addStretch(1)
        lay = right

        wid = QGroupBox("Widgets (frei verschiebbar – einfach ziehen)")
        row = QHBoxLayout(wid)
        self.wchecks = {}
        for key, label in (("clock", "Uhr"), ("monitor", "Monitor 2"), ("quick", "AluPC-Aktionen")):
            c = QCheckBox(label)
            c.setChecked(bool(cfg["widgets"].get(key, True)))
            c.toggled.connect(lambda on, k=key: self._set(widgets={**self.shell.cfg()["widgets"], k: on}))
            self.wchecks[key] = c
            row.addWidget(c)
        reset = button("An den Standardplatz", "refresh")
        reset.clicked.connect(self.shell.area.reset_widgets)
        row.addWidget(reset)
        lay.addWidget(wid)

        beh = QGroupBox("Verhalten")
        f = QFormLayout(beh)
        self.auto = QCheckBox("Beim Start von AluPC gleich die Oberfläche zeigen")
        self.auto.setChecked(bool(cfg["autostart"]))
        self.auto.toggled.connect(lambda on: self._set(autostart=on))
        f.addRow(self.auto)
        self.esc = QCheckBox("Esc schließt die Oberfläche")
        self.esc.setChecked(bool(cfg["esc_closes"]))
        self.esc.toggled.connect(lambda on: self._set(esc_closes=on))
        f.addRow(self.esc)
        f.addRow(QLabel("Wieder öffnen oder schließen: Strg+Alt+O."))
        lay.addWidget(beh)

        lay.addWidget(self._system_group())
        lay.addStretch(1)
        lay = outer

        foot = QHBoxLayout()
        if self.shell.system:
            close_shell = button("Zum normalen Desktop", "window")
            close_shell.clicked.connect(lambda: (self.accept(), self.shell.main_window.system_desktop(False)))
        else:
            close_shell = button("Oberfläche schließen", "x")
            close_shell.clicked.connect(lambda: (self.accept(), self.shell.leave()))
        foot.addWidget(close_shell)
        foot.addStretch(1)
        done = button("Fertig", "check", primary=True)
        done.clicked.connect(self.accept)
        foot.addWidget(done)
        lay.addLayout(foot)

    def _system_group(self) -> QGroupBox:
        """Als echter Desktop statt Explorer (Windows) bzw. Plasma (KDE) – mit Wächter und Knopf zurück."""
        from ..platform import desktop_shell as ds

        box = QGroupBox("Als System-Desktop (statt Explorer bzw. Plasma)")
        f = QVBoxLayout(box)
        st = ds.status()
        info = QLabel(st["why"] + (" Stürzt AluPC ab oder wird beendet, startet sofort der normale Desktop."
                                   if st["supported"] else ""))
        info.setWordWrap(True)
        info.setObjectName("Muted")
        f.addWidget(info)
        self.system_login = QCheckBox("Bei jeder Anmeldung die AluPC-Oberfläche als Desktop starten")
        self.system_login.setChecked(bool(st["enabled"]))
        self.system_login.setEnabled(st["supported"])
        self.system_login.toggled.connect(self._system_login)
        f.addWidget(self.system_login)
        row = QHBoxLayout()
        self.system_now = button("Zum normalen Desktop" if self.shell.system else "Jetzt ausprobieren", "window")
        self.system_now.setEnabled(st["supported"])
        self.system_now.clicked.connect(self._system_now)
        row.addWidget(self.system_now)
        row.addStretch(1)
        f.addLayout(row)
        self.system_msg = QLabel(("Ohne Explorer" if ds.IS_WINDOWS else "Ohne Plasma") + " fehlen: Symbole anderer "
                                 "Programme im Infobereich, "
                                 "Benachrichtigungen anderer Programme" + (", Windows-Startmenü (Win-Taste) und "
                                 "Info-Center. Notfall: Strg+Alt+Entf → Task-Manager → „Neuen Task ausführen“ → "
                                 "explorer." if ds.IS_WINDOWS else ", Plasma-Widgets und -Leisten. Fenster, Alt+Tab und "
                                 "Tastenkürzel (KWin) bleiben."))
        self.system_msg.setWordWrap(True)
        self.system_msg.setObjectName("Muted")
        f.addWidget(self.system_msg)
        return box

    def _system_login(self, on: bool) -> None:
        from PySide6.QtWidgets import QMessageBox

        from ..platform import desktop_shell as ds

        if on and QMessageBox.question(
                self, "AluPC als Desktop",
                "Ab der nächsten Anmeldung startet die AluPC-Oberfläche statt des normalen Desktops.\n\n"
                "Zurück jederzeit über den Knopf „Normaler Desktop“ in der Taskleiste. Stürzt AluPC ab oder wird es "
                "beendet, startet der normale Desktop von selbst.\n\nEinschalten?") != QMessageBox.Yes:
            self.system_login.blockSignals(True)
            self.system_login.setChecked(False)
            self.system_login.blockSignals(False)
            return
        ok, msg = ds.enable() if on else ds.disable()
        self.system_msg.setText(msg)
        if not ok:
            self.system_login.blockSignals(True)
            self.system_login.setChecked(ds.enabled())
            self.system_login.blockSignals(False)

    def _system_now(self) -> None:
        self.accept()
        self.shell.main_window.system_desktop(not self.shell.system)

    def _set(self, **values) -> None:
        self.shell.save(**values)
        self.shell.apply_settings()

    def _wall(self, _i: int) -> None:
        if self.wall.currentData() != "bild":
            self.wall_path.setText("")
            self._set(wallpaper="")
            return
        path, _f = QFileDialog.getOpenFileName(self, "Hintergrundbild wählen", "",
                                               "Bilder (*.png *.jpg *.jpeg *.webp *.bmp)")
        if path:
            self.wall_path.setText(path)
            self._set(wallpaper=path)
        elif not self.shell.cfg()["wallpaper"]:
            self.wall.setCurrentIndex(0)
