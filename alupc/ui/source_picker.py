"""Dialog zum Auswählen einer Quelle (für Szenen-Felder)."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtMultimedia import QMediaDevices
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QSlider,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..scenes import creates_cycle
from ..sources import camera_id, capturable_windows
from . import icons, theme
from .util import ColorButton
from .widgets import button, page_header

SOURCE_TYPES = [
    ("camera", "Kamera"),
    ("window", "Programm (Aufnahme)"),
    ("airplay", "iPhone/iPad (AirPlay)"),
    ("cast", "Handy-Empfang (QR-Code)"),
    ("screen", "Bildschirm"),
    ("website", "Website"),
    ("image", "Bild"),
    ("video", "Video"),
    ("slideshow", "Diashow (Ordner)"),
    ("design", "Gestaltete Seite (Willkommen, Ablauf, Pause …)"),
    ("text", "Text"),
    ("clock", "Uhr"),
    ("countdown", "Countdown"),
    ("color", "Farbfläche"),
    ("scene", "Andere Szene"),
]

FITS = [("contain", "Einpassen (ganzes Bild sichtbar)"), ("cover", "Ausfüllen (Ränder abschneiden)"),
        ("stretch", "Strecken")]

IMAGE_FILTER = "Bilder (*.png *.jpg *.jpeg *.bmp *.gif *.webp *.tif *.tiff)"
VIDEO_FILTER = "Videos (*.mp4 *.mkv *.webm *.mov *.avi *.m4v *.mpg *.mpeg *.wmv)"


def _path_row(filter_text: str | None, folder: bool = False):
    row = QWidget()
    lay = QHBoxLayout(row)
    lay.setContentsMargins(0, 0, 0, 0)
    edit = QLineEdit()
    btn = button("Durchsuchen …", "image" if not folder else "slides")
    lay.addWidget(edit, 1)
    lay.addWidget(btn)

    def browse():
        if folder:
            path = QFileDialog.getExistingDirectory(row, "Ordner wählen", edit.text())
        else:
            path, _ = QFileDialog.getOpenFileName(row, "Datei wählen", edit.text(), filter_text or "")
        if path:
            edit.setText(path)

    btn.clicked.connect(browse)
    return row, edit


def volume_row(init: dict):
    """Lautstärke-Regler + „Ton aus“ für eine einzelne Quelle (Video, Website)."""
    row = QWidget()
    lay = QHBoxLayout(row)
    lay.setContentsMargins(0, 0, 0, 0)
    slider = QSlider(Qt.Horizontal)
    slider.setRange(0, 100)
    slider.setValue(int(init.get("volume", 100)))
    value = QLabel()
    value.setMinimumWidth(44)
    muted = QCheckBox("Ton aus")
    muted.setChecked(bool(init.get("muted", False)))

    def update():
        value.setText(f"{slider.value()} %")
        slider.setEnabled(not muted.isChecked())

    slider.valueChanged.connect(update)
    muted.toggled.connect(update)
    update()
    lay.addWidget(slider, 1)
    lay.addWidget(value)
    lay.addWidget(muted)
    row.slider, row.muted = slider, muted
    return row, lambda: {"volume": slider.value(), "muted": muted.isChecked()}


def _fit_combo(value: str = "contain") -> QComboBox:
    combo = QComboBox()
    for key, label in FITS:
        combo.addItem(label, key)
    combo.setCurrentIndex(max(0, combo.findData(value)))
    return combo


class SourcePicker(QDialog):
    def __init__(self, config, parent=None, initial: dict | None = None, scene_name: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Quelle wählen")
        self.config = config
        self.scene_name = scene_name
        self.resize(760, 480)
        initial = initial or {}

        # Links: Arten mit Symbol · rechts: Einstellungen der gewählten Art
        self.type_list = QListWidget()
        self.type_list.setFixedWidth(236)
        self.type_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.type_list.setIconSize(QSize(22, 22))
        for key, label in SOURCE_TYPES:
            item = QListWidgetItem(icons.icon(icons.SOURCE_ICONS[key], theme.SOURCE_COLORS[key], 22), label)
            item.setData(Qt.UserRole, key)
            self.type_list.addItem(item)
        self.stack = QStackedWidget()
        self.pages: dict[str, tuple[QWidget, callable]] = {}
        for key, _label in SOURCE_TYPES:
            page, getter = getattr(self, f"_page_{key}")(initial if initial.get("type") == key else {})
            self.pages[key] = (page, getter)
            self.stack.addWidget(page)
        self.type_list.currentRowChanged.connect(self._type_changed)
        self.page_title = QLabel()
        self.page_title.setObjectName("SectionTitle")
        self.type_list.setCurrentRow(0)
        if initial.get("type"):
            self.select_type(initial["type"])

        buttons = QDialogButtonBox()
        ok = button("Übernehmen", "check", primary=True)
        buttons.addButton(ok, QDialogButtonBox.AcceptRole)
        buttons.addButton(button("Abbrechen"), QDialogButtonBox.RejectRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        right = QVBoxLayout()
        right.setSpacing(10)
        right.addWidget(self.page_title)
        right.addWidget(self.stack, 1)
        body = QHBoxLayout()
        body.setSpacing(18)
        body.addWidget(self.type_list)
        body.addLayout(right, 1)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 20, 22, 18)
        lay.setSpacing(14)
        lay.addWidget(page_header("Quelle wählen", "Was soll in diesem Feld zu sehen sein?"))
        lay.addLayout(body, 1)
        lay.addWidget(buttons)

    def _type_changed(self, row: int):
        self.stack.setCurrentIndex(row)
        if 0 <= row < len(SOURCE_TYPES):
            self.page_title.setText(SOURCE_TYPES[row][1])

    def select_type(self, key: str) -> None:
        for i in range(self.type_list.count()):
            if self.type_list.item(i).data(Qt.UserRole) == key:
                self.type_list.setCurrentRow(i)
                return

    def current_type(self) -> str:
        item = self.type_list.currentItem()
        return item.data(Qt.UserRole) if item else SOURCE_TYPES[0][0]

    def result_config(self) -> dict | None:
        key = self.current_type()
        cfg = self.pages[key][1]()
        if cfg is None:
            return None
        return {"type": key, **cfg}

    # ------------------------------------------------------------ Seiten
    def _form(self):
        page = QWidget()
        form = QFormLayout(page)
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(10)
        return page, form

    def _page_camera(self, init):
        page, form = self._form()
        combo = QComboBox()
        for dev in QMediaDevices.videoInputs():
            combo.addItem(dev.description(), camera_id(dev))
        if combo.count() == 0:
            form.addRow(QLabel("Keine Kamera gefunden."))
        # vorausgewählt: diese Quelle, sonst die Standard-Kamera aus dem Setup, sonst die erste
        idx = combo.findData(init.get("device_id") or getattr(self, "config", {}).get("default_camera", ""))
        if idx >= 0:
            combo.setCurrentIndex(idx)
        fit = _fit_combo(init.get("fit", "cover"))
        form.addRow("Kamera:", combo)
        form.addRow("Anzeige:", fit)
        hint = QLabel("Zoom, Ausschnitt, Spiegeln, Drehen und Helligkeit: in der Kamera-Leiste im "
                      "Hauptfenster, sobald die Kamera läuft (gilt dann für diese Kamera überall).")
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        form.addRow(hint)
        return page, lambda: None if combo.count() == 0 else {
            "device_id": combo.currentData(), "name": combo.currentText(), "fit": fit.currentData()}

    def _page_window(self, init):
        page, form = self._form()
        combo = QComboBox()
        combo.setEditable(True)
        for w in capturable_windows():
            combo.addItem(w.description())
        if init.get("title"):
            combo.setCurrentText(init["title"])
        refresh = button("Liste neu laden", "refresh")

        def reload():
            current = combo.currentText()
            combo.clear()
            for w in capturable_windows():
                combo.addItem(w.description())
            combo.setCurrentText(current)

        refresh.clicked.connect(reload)
        form.addRow("Programmfenster:", combo)
        form.addRow("", refresh)
        hint = QLabel("Das Programm muss geöffnet sein. Unter Wayland (KDE) kann Qt einzelne Fenster "
                      "nicht aufnehmen – dann bleibt die Liste leer. Nutze dort die Kachel "
                      "„Programm“ → „Fenster verschieben“.")
        hint.setWordWrap(True)
        form.addRow(hint)
        fit = _fit_combo(init.get("fit", "contain"))
        form.addRow("Anzeige:", fit)
        return page, lambda: {"title": combo.currentText(), "fit": fit.currentData()} if combo.currentText() else None

    def _page_airplay(self, init):
        page, form = self._form()
        hint = QLabel("Zeigt, was ein iPhone oder iPad per AirPlay („Bildschirmsynchronisierung“) sendet.\n\n"
                      "Braucht das freie Programm UxPlay ab Version 1.73 (Seite „Handy“ → „Automatisch einrichten“). "
                      "Ältere Versionen gehen nur über die Kachel „Handy“ (eigenes Vollbild-Fenster), nicht in Szenen.")
        hint.setWordWrap(True)
        form.addRow(hint)
        fit = _fit_combo(init.get("fit", "contain"))
        form.addRow("Anzeige:", fit)
        return page, lambda: {"fit": fit.currentData()}

    def _page_cast(self, init):
        page, form = self._form()
        hint = QLabel("Zeigt einen QR-Code: Wer ihn mit dem Handy scannt, kann Fotos, Videos, Links und Text auf "
                      "Monitor 2 senden und ihn fernsteuern – iPhone und Android, ohne App (AluCast).\n\n"
                      "Der Code im QR-Code ist der Zugang: Jeder, der ihn sieht, kann senden. Neuer Code: "
                      "Seite „Handy“.")
        hint.setWordWrap(True)
        form.addRow(hint)
        return page, lambda: {}

    def _page_screen(self, init):
        page, form = self._form()
        combo = QComboBox()
        for s in QGuiApplication.screens():
            combo.addItem(f"{s.name()} ({s.size().width()}×{s.size().height()})", s.name())
        idx = combo.findData(init.get("screen_name"))
        if idx >= 0:
            combo.setCurrentIndex(idx)
        form.addRow("Bildschirm:", combo)
        return page, lambda: {"screen_name": combo.currentData()}

    def _page_website(self, init):
        page, form = self._form()
        url = QLineEdit(init.get("url", ""))
        url.setPlaceholderText("z. B. www.beispiel.de")
        reload_s = QSpinBox()
        reload_s.setRange(0, 86400)
        reload_s.setSuffix(" s")
        reload_s.setSpecialValueText("nie")
        reload_s.setValue(int(init.get("reload_seconds", 0)))
        zoom = QDoubleSpinBox()
        zoom.setRange(0.25, 5.0)
        zoom.setSingleStep(0.1)
        zoom.setValue(float(init.get("zoom", 1.0)))
        vol, vol_get = volume_row(init)
        form.addRow("Adresse:", url)
        form.addRow("Automatisch neu laden:", reload_s)
        form.addRow("Zoom:", zoom)
        form.addRow("Lautstärke:", vol)
        return page, lambda: {"url": url.text().strip(), "reload_seconds": reload_s.value(),
                              "zoom": zoom.value(), **vol_get()} if url.text().strip() else None

    def _page_image(self, init):
        page, form = self._form()
        row, edit = _path_row(IMAGE_FILTER)
        edit.setText(init.get("path", ""))
        fit = _fit_combo(init.get("fit", "contain"))
        form.addRow("Bilddatei:", row)
        form.addRow("Anzeige:", fit)
        return page, lambda: {"path": edit.text(), "fit": fit.currentData()} if edit.text() else None

    def _page_video(self, init):
        page, form = self._form()
        row, edit = _path_row(VIDEO_FILTER)
        edit.setText(init.get("path", ""))
        loop = QCheckBox("Endlos wiederholen")
        loop.setChecked(bool(init.get("loop", True)))
        vol, vol_get = volume_row(init)
        fit = _fit_combo(init.get("fit", "contain"))
        form.addRow("Videodatei:", row)
        form.addRow("", loop)
        form.addRow("Lautstärke:", vol)
        form.addRow("Anzeige:", fit)
        return page, lambda: {"path": edit.text(), "loop": loop.isChecked(), **vol_get(),
                              "fit": fit.currentData()} if edit.text() else None

    def _page_slideshow(self, init):
        page, form = self._form()
        row, edit = _path_row(None, folder=True)
        edit.setText(init.get("folder", ""))
        interval = QSpinBox()
        interval.setRange(1, 3600)
        interval.setSuffix(" s")
        interval.setValue(int(init.get("interval", 5)))
        fit = _fit_combo(init.get("fit", "contain"))
        form.addRow("Bilderordner:", row)
        form.addRow("Wechsel alle:", interval)
        form.addRow("Anzeige:", fit)
        return page, lambda: {"folder": edit.text(), "interval": interval.value(),
                              "fit": fit.currentData()} if edit.text() else None

    def _text_style(self, form, init, default_size):
        size = QSpinBox()
        size.setRange(2, 90)
        size.setSuffix(" % der Feldhöhe")
        size.setValue(int(init.get("size", default_size)))
        color = ColorButton(init.get("color", "#ffffff"))
        bg = ColorButton(init.get("background", "#000000"))
        form.addRow("Schriftgröße:", size)
        form.addRow("Schriftfarbe:", color)
        form.addRow("Hintergrund:", bg)
        return lambda: {"size": size.value(), "color": color.color(), "background": bg.color()}

    def _page_design(self, init):
        from ..screens import DESIGNS, design_defaults

        page, form = self._form()
        design = QComboBox()
        for key, (label, desc, *_rest) in DESIGNS.items():
            design.addItem(f"{label} – {desc}", key)
        design.setCurrentIndex(max(0, design.findData(init.get("design", "willkommen"))))
        title = QLineEdit()
        text = QPlainTextEdit()
        text.setMaximumHeight(120)
        color = ColorButton(init.get("color") or DESIGNS[design.currentData()][4])
        minutes = QSpinBox()
        minutes.setRange(1, 240)
        minutes.setSuffix(" min")
        current = QSpinBox()
        current.setRange(1, 30)
        labels = {"wlan": ("WLAN-Name:", "Passwort:"), "zitat": ("Zitat:", "Autor:"),
                  "ablauf": ("Überschrift:", "Punkte (je Zeile einer):"), "laufschrift": ("Titel:", "Laufschrift:")}
        form.addRow("Design:", design)
        form.addRow("Titel:", title)
        form.addRow("Text:", text)
        form.addRow("Farbe:", color)
        form.addRow("Dauer:", minutes)
        form.addRow("Aktueller Punkt:", current)
        filled = {"key": None}

        def apply_design(*_):
            key = design.currentData()
            base = {**design_defaults(key), **(init if init.get("design") == key else {})}
            if filled["key"] is not None:  # beim Umschalten nur leere Felder mit Beispieltext füllen
                base = {**base, **({"title": title.text()} if title.text() else {}),
                        **({"text": text.toPlainText()} if text.toPlainText() else {})}
            filled["key"] = key
            title.setText(base.get("title", ""))
            text.setPlainText(base.get("text", ""))
            color.set_color(base.get("color", "#6366f1"))
            minutes.setValue(int(base.get("minutes", 10)))
            current.setValue(int(base.get("current", 1)))
            a, b = labels.get(key, ("Titel:", "Text:"))
            form.labelForField(title).setText(a)
            form.labelForField(text).setText(b)
            form.setRowVisible(minutes, key == "pause")
            form.setRowVisible(current, key == "ablauf")

        design.currentIndexChanged.connect(apply_design)
        apply_design()
        hint = QLabel("Alles wird passend zur Monitorgröße gezeichnet. Pause: der Countdown startet, sobald die "
                      "Seite gezeigt wird.")
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        form.addRow(hint)
        return page, lambda: {"design": design.currentData(), "title": title.text(), "text": text.toPlainText(),
                              "color": color.color(), "minutes": minutes.value(), "current": current.value()}

    def _page_text(self, init):
        page, form = self._form()
        text = QPlainTextEdit(init.get("text", ""))
        form.addRow("Text:", text)
        style = self._text_style(form, init, 12)
        return page, lambda: {"text": text.toPlainText(), **style()} if text.toPlainText().strip() else None

    def _page_clock(self, init):
        page, form = self._form()
        date = QCheckBox("Datum anzeigen")
        date.setChecked(bool(init.get("show_date", True)))
        secs = QCheckBox("Sekunden anzeigen")
        secs.setChecked(bool(init.get("show_seconds", True)))
        form.addRow("", date)
        form.addRow("", secs)
        style = self._text_style(form, init, 25)
        return page, lambda: {"show_date": date.isChecked(), "show_seconds": secs.isChecked(), **style()}

    def _page_countdown(self, init):
        page, form = self._form()
        minutes = QDoubleSpinBox()
        minutes.setRange(0.1, 1440)
        minutes.setSuffix(" min")
        minutes.setValue(float(init.get("minutes", 5)))
        finished = QLineEdit(init.get("finished_text", "Zeit ist um!"))
        form.addRow("Dauer:", minutes)
        form.addRow("Text am Ende:", finished)
        hint = QLabel("Der Countdown startet, sobald die Szene angezeigt wird.")
        form.addRow(hint)
        style = self._text_style(form, init, 30)
        return page, lambda: {"minutes": minutes.value(), "finished_text": finished.text(), **style()}

    def _page_color(self, init):
        page, form = self._form()
        color = ColorButton(init.get("color", "#000000"))
        form.addRow("Farbe:", color)
        return page, lambda: {"color": color.color()}

    def _page_scene(self, init):
        page, form = self._form()
        combo = QComboBox()
        scenes = self.config["scenes"]
        for name in self.config.scene_names():
            if name == self.scene_name or (self.scene_name and creates_cycle(scenes, self.scene_name, name)):
                continue  # keine Szene in sich selbst
            combo.addItem(name)
        if init.get("scene"):
            combo.setCurrentText(init["scene"])
        if combo.count() == 0:
            form.addRow(QLabel("Es gibt noch keine andere Szene."))
        form.addRow("Szene:", combo)
        return page, lambda: {"scene": combo.currentText()} if combo.count() else None
