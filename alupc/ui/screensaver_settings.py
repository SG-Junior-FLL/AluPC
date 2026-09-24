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

from .widgets import button, page_header


class ScreensaverSettings(QGroupBox):
    def __init__(self, controller, title: str = "Bildschirmschoner (Monitor 2)", parent=None):
        super().__init__(parent)
        from ..screensaver import STYLES, WHEN

        box = self
        self.setTitle(title)
        form = QFormLayout(box)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(10)
        cfg = controller.config["screensaver"]
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
        text.setPlaceholderText("leer = Uhrzeit")
        image = QLineEdit(cfg.get("image", ""))
        image.setPlaceholderText("optional: Logo statt Text")
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
        test = button("Jetzt starten / beenden", "moon", primary=True)
        test.clicked.connect(controller.toggle_screensaver)
        info = QLabel(controller.screensaver.idle.describe())
        info.setObjectName("Muted")
        info.setWordWrap(True)

        def row(*widgets):
            r = QHBoxLayout()
            for w in widgets:
                r.addWidget(w, 1 if isinstance(w, QLineEdit) else 0)
            return r

        rows = {
            "schweben": [("Text:", text), ("Logo:", row(image, img_btn))],
            "diashow": [("Ordner:", row(folder, folder_btn)), ("Wechsel alle:", interval)],
            "szene": [("Szene:", scene)],
        }
        form.addRow("", enabled)
        form.addRow("Nach:", minutes)
        form.addRow("Wann:", when)
        form.addRow("Stil:", style)
        for items in rows.values():
            for label, field in items:
                form.addRow(label, field)
        test_row = QHBoxLayout()
        test_row.addWidget(test)
        test_row.addStretch(1)
        form.addRow("", test_row)
        form.addRow(info)

        def update_rows():
            current = style.currentData()
            for key, items in rows.items():
                for _label, field in items:
                    form.setRowVisible(field, key == current)

        def save(*_):
            controller.config["screensaver"] = {
                "enabled": enabled.isChecked(), "minutes": minutes.value(), "when": when.currentData(),
                "style": style.currentData(), "text": text.text(), "image": image.text(),
                "folder": folder.text(), "interval": interval.value(), "scene": scene.currentText(),
            }
            update_rows()

        def pick_image():
            path, _ = QFileDialog.getOpenFileName(box, "Logo wählen", image.text(),
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
        for w in (enabled,):
            w.toggled.connect(save)
        for w in (minutes, interval):
            w.valueChanged.connect(save)
        for w in (when, style, scene):
            w.currentIndexChanged.connect(save)
        for w in (text, image, folder):
            w.editingFinished.connect(save)
        self.scene_combo = scene
        update_rows()



class ScreensaverDialog(QDialog):
    """Einstellungen, die man direkt über den Pfeil der Bildschirmschoner-Kachel öffnet."""

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Bildschirmschoner")
        self.setMinimumWidth(560)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 20, 22, 18)
        lay.setSpacing(12)
        lay.addWidget(page_header("Bildschirmschoner", "Wird sofort gespeichert."))
        lay.addWidget(ScreensaverSettings(controller, ""))
        buttons = QDialogButtonBox()
        close = button("Fertig", "check", primary=True)
        buttons.addButton(close, QDialogButtonBox.AcceptRole)
        buttons.accepted.connect(self.accept)
        lay.addWidget(buttons)
