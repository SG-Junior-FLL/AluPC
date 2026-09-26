"""Einstellungen des Bildschirmschoners – im Setup und direkt an der Kachel."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
)

from .util import ColorButton
from .widgets import button, page_header


class ScreensaverSettings(QGroupBox):
    """Einstellungen eines Bildschirmschoners.

    Normal: die allgemeinen Einstellungen (config["screensaver"]).
    tile_mode: eigener Bildschirmschoner einer Kachel – nur Aussehen, gespeichert in `data`.
    """

    def __init__(self, controller, title: str = "Bildschirmschoner (Monitor 2)", parent=None,
                 data: dict | None = None, tile_mode: bool = False, on_change=None):
        super().__init__(parent)
        from ..screensaver import STYLES, WHEN

        self.controller = controller
        self.tile_mode = tile_mode
        self.on_change = on_change
        self.data = dict(data if data is not None else controller.config["screensaver"])
        cfg = self.data
        box = self
        self.setTitle(title)
        form = QFormLayout(box)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(10)
        enabled = QCheckBox("Automatisch starten, wenn niemand den PC benutzt")
        enabled.setChecked(bool(cfg.get("enabled")))
        minutes = QSpinBox()
        minutes.setRange(1, 240)
        minutes.setSuffix(" Minuten")
        minutes.setValue(int(cfg.get("minutes", 10)))
        when = QComboBox()
        for key, label in WHEN.items():
            when.addItem(label, key)
        when.setCurrentIndex(max(0, when.findData(cfg.get("when", "desktop"))))
        style = QComboBox()
        for key, label in STYLES.items():
            style.addItem(label, key)
        style.setCurrentIndex(max(0, style.findData(cfg.get("style", "uhr"))))
        text = QLineEdit(cfg.get("text", ""))
        text.setPlaceholderText("z. B. „Gleich geht's weiter“ (leer = Uhrzeit)")
        color = ColorButton(cfg.get("color", "#e8ecf3"))
        image = QLineEdit(cfg.get("image", ""))
        image.setPlaceholderText("optional: Logo bzw. Hintergrundbild")
        img_btn = button("…", "image")
        folder = QLineEdit(cfg.get("folder", ""))
        folder_btn = button("…", "slides")
        interval = QSpinBox()
        interval.setRange(3, 600)
        interval.setSuffix(" s")
        interval.setValue(int(cfg.get("interval", 8)))
        scene = QComboBox()
        scene.addItems(controller.config.scene_names())
        scene.setCurrentText(cfg.get("scene", ""))
        test = button("Vorschau auf Monitor 2" if tile_mode else "Jetzt starten / beenden", "moon", primary=True)
        test.clicked.connect(self._test)
        info = QLabel(controller.screensaver.idle.describe())
        info.setObjectName("Muted")
        info.setWordWrap(True)

        def row(*widgets):
            r = QHBoxLayout()
            for w in widgets:
                r.addWidget(w, 1 if isinstance(w, QLineEdit) else 0)
            return r

        img_row = row(image, img_btn)
        folder_row = row(folder, folder_btn)
        rows = {
            "schweben": [("Text:", text), ("Bild/Logo:", img_row), ("Farbe:", color)],
            "nachricht": [("Text:", text), ("Bild/Logo:", img_row), ("Farbe:", color)],
            "uhr": [("Farbe:", color)],
            "diashow": [("Ordner:", folder_row), ("Wechsel alle:", interval)],
            "szene": [("Szene:", scene)],
            "sprueche": [("Sprüche:", text), ("Farbe:", color)],
            "schnee": [("Text:", text)],
            "analog": [("Zeigerfarbe:", color)],
            "flipuhr": [("Ziffernfarbe:", color)],
            "lava": [("Grundfarbe:", color)],
            "bokeh": [("Grundfarbe:", color)],
            "wellen": [("Meeresfarbe:", color)],
            "matrix": [("Farbe:", color)],
            "netz": [("Farbe:", color)],
        }
        if not tile_mode:
            form.addRow("", enabled)
            form.addRow("Nach:", minutes)
            form.addRow("Wann:", when)
        form.addRow("Stil:", style)
        added = set()
        for items in rows.values():
            for label, field in items:
                if id(field) not in added:
                    form.addRow(label, field)
                    added.add(id(field))
        test_row = QHBoxLayout()
        test_row.addWidget(test)
        test_row.addStretch(1)
        form.addRow("", test_row)
        if not tile_mode:
            form.addRow(info)

        def update_rows():
            current = style.currentData()
            visible = {id(f) for _l, f in rows.get(current, [])}
            for items in rows.values():
                for _label, field in items:
                    form.setRowVisible(field, id(field) in visible)

        def save(*_):
            self.data.update({
                "style": style.currentData(), "text": text.text(), "image": image.text(),
                "folder": folder.text(), "interval": interval.value(), "scene": scene.currentText(),
                "color": color.color(),
            })
            if not tile_mode:
                self.data.update({"enabled": enabled.isChecked(), "minutes": minutes.value(),
                                  "when": when.currentData()})
                controller.config["screensaver"] = dict(self.data)
            if self.on_change:
                self.on_change(dict(self.data))
            update_rows()

        def pick_image():
            path, _ = QFileDialog.getOpenFileName(box, "Bild wählen", image.text(),
                                                  "Bilder (*.png *.jpg *.jpeg *.bmp *.webp *.svg)")
            if path:
                image.setText(path)
                save()

        def pick_folder():
            path = QFileDialog.getExistingDirectory(box, "Bilderordner wählen", folder.text())
            if path:
                folder.setText(path)
                save()

        img_btn.clicked.connect(pick_image)
        folder_btn.clicked.connect(pick_folder)
        enabled.toggled.connect(save)
        color.changed.connect(save)
        for w in (minutes, interval):
            w.valueChanged.connect(save)
        for w in (when, style, scene):
            w.currentIndexChanged.connect(save)
        for w in (text, image, folder):
            w.editingFinished.connect(save)
        self.scene_combo = scene
        self.style_combo = style
        update_rows()

    def _test(self):
        saver = self.controller.screensaver
        if self.tile_mode:
            if saver.active:
                saver.stop()
            else:
                saver.start(manual=True, override=dict(self.data))
        else:
            self.controller.toggle_screensaver()


class ScreensaverDialog(QDialog):
    """Einstellungen, die man direkt über den Pfeil der Bildschirmschoner-Kachel öffnet."""

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Bildschirmschoner")
        self.setMinimumWidth(560)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 20, 22, 18)
        lay.setSpacing(12)
        lay.addWidget(page_header("Bildschirmschoner", "Speichert sofort"))
        lay.addWidget(ScreensaverSettings(controller, ""))
        buttons = QDialogButtonBox()
        close = button("Fertig", "check", primary=True)
        buttons.addButton(close, QDialogButtonBox.AcceptRole)
        buttons.accepted.connect(self.accept)
        lay.addWidget(buttons)
