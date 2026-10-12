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
        self.setMinimumWidth(520)
        cfg = shell.cfg()
        lay = QVBoxLayout(self)
        lay.setSpacing(12)

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

        foot = QHBoxLayout()
        close_shell = button("Oberfläche schließen", "x")
        close_shell.clicked.connect(lambda: (self.accept(), self.shell.leave()))
        foot.addWidget(close_shell)
        foot.addStretch(1)
        done = button("Fertig", "check", primary=True)
        done.clicked.connect(self.accept)
        foot.addWidget(done)
        lay.addLayout(foot)

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
