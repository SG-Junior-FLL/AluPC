"""Setup: Monitore (Auflösung, Hz, Anordnung) und Einstellungen von AluPC."""

from __future__ import annotations


from PySide6.QtCore import QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractButton,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QMessageBox,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QScrollArea,
    QSlider,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..config import HOTKEY_LABELS
from ..platform import IS_WINDOWS, autostart, session_info
from ..platform.base import ROTATIONS, clone_outputs, place, side_of
from . import icons, theme
from .util import error_box, run_async
from .hotkey_edit import HotkeyButton
from .reset_page import reset_group
from .sync_page import backup_group, sync_group
from .widgets import button, flow_row, font, rounded

SIDES = [("right", "rechts vom Hauptmonitor"), ("left", "links vom Hauptmonitor"),
         ("above", "über dem Hauptmonitor"), ("below", "unter dem Hauptmonitor"),
         ("mirror", "gespiegelt (gleiche Position)")]


class ConfirmDialog(QDialog):
    """„Einstellungen behalten?“ – ohne Antwort wird nach 15 Sekunden zurückgesetzt."""

    def __init__(self, parent=None, seconds: int = 15):
        super().__init__(parent)
        self.setWindowTitle("Einstellungen behalten?")
        self.remaining = seconds
        self.label = QLabel()
        self.label.setWordWrap(True)
        buttons = QDialogButtonBox()
        keep = buttons.addButton("Behalten", QDialogButtonBox.AcceptRole)
        buttons.addButton("Zurücksetzen", QDialogButtonBox.RejectRole)
        keep.setDefault(True)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay = QVBoxLayout(self)
        lay.addWidget(self.label)
        lay.addWidget(buttons)
        self.timer = QTimer(self, interval=1000)
        self.timer.timeout.connect(self._tick)
        self.timer.start()
        self._update()

    def _update(self):
        self.label.setText(f"Alles richtig? Sonst zurück in {self.remaining} s.")

    def _tick(self):
        self.remaining -= 1
        if self.remaining <= 0:
            self.reject()
        else:
            self._update()


class IdentifyWindow(QLabel):
    def __init__(self, screen, number: int):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setText(f"{number}\n{screen.name()}")
        font = QFont()
        font.setPixelSize(90)
        font.setBold(True)
        self.setFont(font)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet(f"background:{theme.current().accent}; color:white; border-radius:24px;")
        self.resize(360, 260)
        geo = screen.geometry()
        self.move(geo.center().x() - 180, geo.center().y() - 130)
        self.create()
        if self.windowHandle():
            self.windowHandle().setScreen(screen)


class Swatch(QAbstractButton):
    """Runder Farbknopf für die Akzentfarbe."""

    def __init__(self, color: str, tooltip: str, parent=None):
        super().__init__(parent)
        self.color = color
        self.setCheckable(True)
        self.setToolTip(tooltip)
        self.setFixedSize(34, 34)
        self.setCursor(Qt.PointingHandCursor)

    def paintEvent(self, _e):
        t = theme.current()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(3, 3, -3, -3)
        if self.isChecked():
            p.setPen(QPen(QColor(t.text), 2.5))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(QRectF(self.rect()).adjusted(1.5, 1.5, -1.5, -1.5))
            r = r.adjusted(3, 3, -3, -3)
        p.setPen(Qt.NoPen)
        if getattr(self, "brand", False):  # AluPC-Theme: das Logo selbst als Farbknopf
            p.drawPixmap(r.toRect(), icons.app_icon().pixmap(int(r.width()), int(r.width())))
            p.end()
            return
        p.setBrush(QColor(self.color))
        p.drawEllipse(r)
        if getattr(self, "system", False):  # „Wie das System“: kleines Monitor-Symbol in der Systemfarbe
            s = int(r.width() * 0.62)
            icons.icon("monitor", "#ffffff", s).paint(p, int(r.center().x() - s / 2), int(r.center().y() - s / 2), s, s)
        p.end()


class MonitorArrangement(QWidget):
    """Zeichnet die Monitore so, wie sie angeordnet sind; Klick wählt einen Monitor aus."""

    selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.items: list[dict] = []
        self.current = ""
        self.output_name = ""
        self.setMinimumHeight(190)
        self.setCursor(Qt.PointingHandCursor)
        self._rects: dict[str, QRectF] = {}

    def set_items(self, items: list[dict], output_name: str):
        self.items, self.output_name = items, output_name
        self.update()

    def set_current(self, name: str):
        self.current = name
        self.update()

    def mousePressEvent(self, e):
        for name, r in self._rects.items():
            if r.contains(e.position()):
                self.selected.emit(name)
                return

    def paintEvent(self, _e):
        t = theme.current()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        area = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        p.fillPath(rounded(area, 12), QColor(t.surface2))
        self._rects = {}
        if not self.items:
            p.setPen(QColor(t.muted))
            p.drawText(area, Qt.AlignCenter, "Keine Monitore erkannt")
            p.end()
            return
        min_x = min(i["x"] for i in self.items)
        min_y = min(i["y"] for i in self.items)
        max_x = max(i["x"] + i["w"] for i in self.items)
        max_y = max(i["y"] + i["h"] for i in self.items)
        inner = area.adjusted(24, 20, -24, -20)
        scale = min(inner.width() / max(1, max_x - min_x), inner.height() / max(1, max_y - min_y))
        ox = inner.left() + (inner.width() - (max_x - min_x) * scale) / 2
        oy = inner.top() + (inner.height() - (max_y - min_y) * scale) / 2
        for i, item in enumerate(sorted(self.items, key=lambda it: it["name"] == self.current)):
            r = QRectF(ox + (item["x"] - min_x) * scale, oy + (item["y"] - min_y) * scale,
                       item["w"] * scale, item["h"] * scale).adjusted(3, 3, -3, -3)
            self._rects[item["name"]] = r
            is_out = item["name"] == self.output_name
            color = QColor("#f97316") if is_out else QColor(t.accent)
            fill = QColor(color)
            fill.setAlphaF(0.22 if item["name"] == self.current else 0.12)
            p.fillPath(rounded(r, 8), QColor(t.surface))
            p.fillPath(rounded(r, 8), fill)
            p.setPen(QPen(color, 2.5 if item["name"] == self.current else 1.2))
            p.drawPath(rounded(r, 8))
            title = "Monitor 2" if is_out else ("Hauptmonitor" if item.get("primary") else item["name"])
            tf, df = font(10.5, QFont.Bold), font(8.5)
            th, dh = QFontMetrics(tf).height(), QFontMetrics(df).height()
            top = r.center().y() - (th + 2 * dh + 4) / 2
            p.setPen(QColor(t.text))
            p.setFont(tf)
            p.drawText(QRectF(r.left() + 6, top, r.width() - 12, th), Qt.AlignCenter, title)
            p.setPen(QColor(t.muted))
            p.setFont(df)
            p.drawText(QRectF(r.left() + 6, top + th + 4, r.width() - 12, dh), Qt.AlignCenter, item["name"])
            p.drawText(QRectF(r.left() + 6, top + th + 4 + dh, r.width() - 12, dh), Qt.AlignCenter, item["label"])
        p.end()


class SetupPage(QWidget):
    """Setup mit Bereichen: links die Liste, rechts der gewählte Bereich."""

    theme_changed = Signal()
    hotkeys_changed = Signal()

    SECTIONS = [
        ("monitor", "Monitore", "Auflösung · Anordnung"),
        ("pip", "Monitor 2", "Maus · Sichtschutz · PiP"),
        ("palette", "Darstellung", "Design · Farbe"),
        ("moon", "Bildschirmschoner", "Stil · Zeit"),
        ("timer", "Timer", "Dauer · Warnfarben"),
        ("sound", "Töne", "Bei Aktionen"),
        ("keyboard", "Tastenkürzel", "Alles per Tastatur"),
        ("mic", "Sprache", "Sprechen · Stimme · Test"),
        ("sync", "Sichern & Sync", "Export · Dual-Boot"),
        ("fan", "RGB & Lüfter", "OpenRGB · Temperaturen"),
        ("phone", "Handy & Kamera", "Rechte · Kamera"),
        ("sliders", "Allgemein", "Start · Autostart · Hilfe"),
    ]

    def __init__(self, controller, hotkeys, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.config = controller.config
        self.hotkeys = hotkeys
        self.outputs = []
        builders = {
            "Monitore": [self._display_group],
            "Monitor 2": [self._output_group, self._privacy_group, self._pip_group],
            "Darstellung": [self._appearance_group],
            "Bildschirmschoner": [self._screensaver_group],
            "Timer": [self._timer_group],
            "Töne": [self._sound_group],
            "Tastenkürzel": [self._hotkey_group],
            "Sprache": [self._voice_group],
            "Sichern & Sync": [lambda: sync_group(self), lambda: backup_group(self)],
            "RGB & Lüfter": [self._hardware_group],
            "Handy & Kamera": [self._phone_group, self._camera_group],  # AirPlay: ohne Einstellungen
            "Allgemein": [self._app_group, lambda: reset_group(self)],
        }
        self.nav = QListWidget()
        self.nav.setObjectName("SetupNav")
        self.nav.setFixedWidth(230)
        self.nav.setIconSize(QSize(20, 20))
        self.nav.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.stack = QStackedWidget()
        t = theme.current()
        # Bereiche werden erst gebaut, wenn man sie öffnet (das erste Öffnen von „Setup“ war sonst spürbar
        # langsam). Greift Code auf etwas aus einem noch nicht gebauten Bereich zu, baut __getattr__ alle.
        self._areas: list[QScrollArea] = []
        self._pending = {}
        for i, (icon_name, title, sub) in enumerate(self.SECTIONS):
            item = QListWidgetItem(icons.icon(icon_name, t.accent, 20), f"{title}\n{sub}")
            item.setSizeHint(QSize(220, 54))
            self.nav.addItem(item)
            area = QScrollArea()
            area.setWidgetResizable(True)
            area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            self._areas.append(area)
            self._pending[i] = builders[title]
            self.stack.addWidget(area)
        self.nav.currentRowChanged.connect(self._show_row)
        self._build_section(0)
        self.nav.setCurrentRow(0)
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(18)
        root.addWidget(self.nav)
        root.addWidget(self.stack, 1)
        controller.changed.connect(self._update_arrangement)
        QTimer.singleShot(0, self.reload_outputs)

    def _build_section(self, i: int) -> None:
        builders = self.__dict__.get("_pending", {}).pop(i, None)
        if builders is None:
            return
        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(0, 0, 8, 0)
        lay.setSpacing(6)
        for build in builders:
            lay.addWidget(build())
        for combo in inner.findChildren(QComboBox):  # lange Einträge dürfen das Fenster nicht verbreitern
            combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
            combo.setMinimumContentsLength(10)
        lay.addStretch(1)
        self._areas[i].setWidget(inner)

    def build_all(self) -> None:
        for i in list(self.__dict__.get("_pending", {})):
            self._build_section(i)

    def _show_row(self, i: int) -> None:
        self._build_section(i)
        self.stack.setCurrentIndex(i)

    def __getattr__(self, name):
        # Attribut aus einem noch nicht gebauten Bereich (z. B. self.voice_on) → alle Bereiche bauen
        pending = self.__dict__.get("_pending")
        if pending and not name.startswith("__"):
            self.build_all()
            return object.__getattribute__(self, name)
        raise AttributeError(name)

    def set_compact(self, on: bool) -> None:
        """Kleines Fenster: Bereichsliste nur mit Symbolen (Name als Tooltip)."""
        self.nav.setFixedWidth(64 if on else 230)
        for i, (_icon, title, sub) in enumerate(self.SECTIONS):
            item = self.nav.item(i)
            item.setText("" if on else f"{title}\n{sub}")
            item.setToolTip(f"{title} – {sub}")
            item.setSizeHint(QSize(48, 48) if on else QSize(220, 54))
        self.layout().setSpacing(10 if on else 18)

    def show_section(self, title: str) -> None:
        for i, (_icon, name, _sub) in enumerate(self.SECTIONS):
            if name == title:
                self.nav.setCurrentRow(i)

    # ================================================================ Monitore
    def _display_group(self):
        box = QGroupBox("Monitore")
        lay = QVBoxLayout(box)
        backend = self.controller.display
        self.backend_label = QLabel(f"System: {session_info()} – Steuerung über: {backend.name}")
        lay.addWidget(self.backend_label)
        if not backend.available():
            hint = QLabel("Nicht verfügbar – braucht „kscreen-doctor“ (Paket kscreen)")
            hint.setWordWrap(True)
            lay.addWidget(hint)

        self.arrangement = MonitorArrangement()
        self.arrangement.selected.connect(self._select_output)
        lay.addWidget(self.arrangement)

        form = QFormLayout()
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(10)
        self.output_combo = QComboBox()
        self.output_combo.currentIndexChanged.connect(self._show_output)
        self.enabled_check = QCheckBox("Monitor eingeschaltet")
        self.primary_check = QCheckBox("Hauptmonitor")
        self.res_combo = QComboBox()
        self.res_combo.currentIndexChanged.connect(self._fill_rates)
        self.rate_combo = QComboBox()
        self.scale_spin = QDoubleSpinBox()
        self.scale_spin.setRange(0.5, 4.0)
        self.scale_spin.setSingleStep(0.25)
        self.scale_spin.setSuffix(" ×")
        self.scale_spin.setValue(1.0)
        self.rot_combo = QComboBox()
        for key, label in ROTATIONS.items():
            self.rot_combo.addItem(label, key)
        form.addRow("Monitor:", self.output_combo)
        form.addRow("", self.enabled_check)
        form.addRow("", self.primary_check)
        form.addRow("Auflösung:", self.res_combo)
        form.addRow("Bildwiederholrate:", self.rate_combo)
        form.addRow("Skalierung:", self.scale_spin)
        form.addRow("Drehung:", self.rot_combo)
        self.side_combo = QComboBox()
        for key, label in SIDES:
            self.side_combo.addItem(label, key)
        form.addRow("Monitor 2 liegt:", self.side_combo)
        if not backend.supports_scale:
            self.scale_spin.setEnabled(False)
            self.scale_spin.setToolTip("Skalierung stellst du unter Windows/X11 in den Systemeinstellungen ein.")
        lay.addLayout(form)


        row = QHBoxLayout()
        apply_btn = button("Übernehmen", "check", primary=True)
        apply_btn.clicked.connect(self._apply)
        reload_btn = button("Neu laden", "refresh")
        reload_btn.clicked.connect(self.reload_outputs)
        ident_btn = button("Monitore identifizieren", "monitor")
        ident_btn.clicked.connect(self.identify)
        row.addWidget(apply_btn)
        row.addWidget(reload_btn)
        row.addWidget(ident_btn)
        row.addStretch(1)
        lay.addLayout(row)

        row2 = QHBoxLayout()
        mirror_btn = button("System-Spiegeln", "mirror")
        mirror_btn.setToolTip("Das Betriebssystem spiegelt Monitor 1 (ohne AluPC). "
                              "Standbild und Sichtschutz gehen dann nicht.")
        mirror_btn.clicked.connect(self._system_mirror)
        extend_btn = button("System-Erweitern", "extend")
        extend_btn.clicked.connect(self._system_extend)
        row2.addWidget(mirror_btn)
        row2.addWidget(extend_btn)
        open_btn = button("Anzeige-Einstellungen", "sliders")
        open_btn.setToolTip("Bildschirm-Einstellungen des Systems (Windows bzw. KDE/GNOME)")
        open_btn.clicked.connect(self._open_display_settings)
        row2.addWidget(open_btn)
        row2.addStretch(1)
        lay.addLayout(row2)
        for w in (apply_btn, mirror_btn, extend_btn, self.output_combo):
            w.setEnabled(backend.available())
        return box

    def reload_outputs(self):
        if not self.controller.display.available():
            self._update_arrangement()
            return

        def done(outputs):
            self.outputs = outputs
            current = self.output_combo.currentData()
            self.output_combo.blockSignals(True)
            self.output_combo.clear()
            for o in outputs:
                label = o.name + (f" – {o.description}" if o.description else "")
                if o.primary:
                    label += " (Haupt)"
                self.output_combo.addItem(label, o.name)
            self.output_combo.blockSignals(False)
            idx = self.output_combo.findData(current)
            self.output_combo.setCurrentIndex(idx if idx >= 0 else 0)
            self._show_output()
            # Aktuelle Anordnung anzeigen, damit „Übernehmen“ nichts ungewollt verschiebt
            enabled = [o for o in outputs if o.enabled]
            main = next((o for o in enabled if o.primary), enabled[0] if enabled else None)
            other = next((o for o in enabled if o is not main), None)
            if main is not None and other is not None:
                side = side_of(outputs, main.name, other.name)
                self.side_combo.setCurrentIndex(max(0, self.side_combo.findData(side)))
            self._update_arrangement()

        run_async(self.controller.display.list_outputs, done,
                  lambda e: self.backend_label.setText(f"Monitore nicht lesbar: {e}"))

    def _update_arrangement(self):
        out = self.controller.output_screen()
        items = []
        if self.outputs:
            logical = self.controller.display.logical_positions
            for o in self.outputs:
                if not o.enabled:
                    continue
                w, h = o.size()
                if logical and o.scale:
                    w, h = round(w / o.scale), round(h / o.scale)
                m = o.mode()
                label = f"{m.width}×{m.height} · {m.refresh:.0f} Hz" if m else ""
                items.append({"name": o.name, "x": o.x, "y": o.y, "w": max(w, 1), "h": max(h, 1),
                              "primary": o.primary, "label": label})
        else:  # ohne Systemzugriff: Qt-Sicht der Monitore zeigen
            primary = QGuiApplication.primaryScreen()
            for s in QGuiApplication.screens():
                g = s.geometry()
                items.append({"name": s.name(), "x": g.x(), "y": g.y(), "w": g.width(), "h": g.height(),
                              "primary": s is primary,
                              "label": f"{g.width()}×{g.height()} · {s.refreshRate():.0f} Hz"})
        self.arrangement.set_items(items, out.name() if out else "")
        self.arrangement.set_current(self.output_combo.currentData() or "")

    def _select_output(self, name: str):
        idx = self.output_combo.findData(name)
        if idx >= 0:
            self.output_combo.setCurrentIndex(idx)

    def _current_output(self):
        name = self.output_combo.currentData()
        return next((o for o in self.outputs if o.name == name), None)

    def _show_output(self):
        o = self._current_output()
        if o is None:
            return
        self.arrangement.set_current(o.name)
        self.enabled_check.setChecked(o.enabled)
        self.primary_check.setChecked(o.primary)
        self.scale_spin.setValue(o.scale)
        self.rot_combo.setCurrentIndex(max(0, self.rot_combo.findData(o.rotation)))
        self.res_combo.blockSignals(True)
        self.res_combo.clear()
        for w, h in o.resolutions():
            self.res_combo.addItem(f"{w} × {h}", (w, h))
        cur = o.mode()
        if cur:
            self.res_combo.setCurrentIndex(max(0, self.res_combo.findData((cur.width, cur.height))))
        self.res_combo.blockSignals(False)
        self._fill_rates()

    def _fill_rates(self):
        o = self._current_output()
        res = self.res_combo.currentData()
        self.rate_combo.clear()
        if o is None or res is None:
            return
        cur = o.mode()
        for m in o.refresh_rates(*res):
            self.rate_combo.addItem(f"{m.refresh:.2f} Hz".replace(".00 Hz", " Hz"), m.id)
        if cur:
            idx = self.rate_combo.findData(cur.id)
            if idx >= 0:
                self.rate_combo.setCurrentIndex(idx)

    def _collect(self):
        """Neue Einstellungen aus den Feldern in eine Kopie der Monitorliste schreiben."""
        outputs = clone_outputs(self.outputs)
        o = next((x for x in outputs if x.name == self.output_combo.currentData()), None)
        if o is None:
            return None
        o.enabled = self.enabled_check.isChecked()
        if self.rate_combo.currentData():
            o.mode_id = self.rate_combo.currentData()
        o.rotation = self.rot_combo.currentData()
        if self.controller.display.supports_scale:
            o.scale = self.scale_spin.value()
        if self.primary_check.isChecked():
            for x in outputs:
                x.primary = x is o
        enabled = [x for x in outputs if x.enabled]
        if not enabled:
            error_box(self, "Mindestens ein Monitor muss eingeschaltet bleiben.")
            return None
        main = next((x for x in enabled if x.primary), enabled[0])
        side = self.side_combo.currentData()
        for x in enabled:
            if x is main:
                continue
            if side == "mirror":
                x.x, x.y = main.x, main.y
            else:
                place(outputs, main.name, x.name, side, self.controller.display.logical_positions)
        return outputs

    def _apply(self):
        new = self._collect()
        if new is None:
            return
        old = clone_outputs(self.outputs)
        backend = self.controller.display

        def applied(_r):
            dlg = ConfirmDialog(self.window())
            if dlg.exec() == QDialog.Accepted:
                self.reload_outputs()
            else:
                run_async(lambda: backend.apply(old), lambda _r: self.reload_outputs(),
                          lambda e: error_box(self, f"Zurücksetzen fehlgeschlagen: {e}"))

        run_async(lambda: backend.apply(new), applied,
                  lambda e: error_box(self, f"Einstellungen konnten nicht gesetzt werden:\n{e}"))

    def _system_mirror(self):
        pair = self.controller.prepare_system_mirror()
        if pair is None:
            return
        main, out = pair
        run_async(lambda: self.controller.display.mirror(main, out), lambda _r: self._after_mode(),
                  lambda e: error_box(self, f"Spiegeln fehlgeschlagen: {e}"))

    def _system_extend(self):
        main, out = self.controller.main_screen(), self.controller.output_screen()
        if main is None or out is None:
            error_box(self, "Kein zweiter Monitor gefunden.")
            return
        side = self.side_combo.currentData()
        if side == "mirror":
            side = "right"
        run_async(lambda: self.controller.display.extend(main.name(), out.name(), side),
                  lambda _r: self._after_mode(), lambda e: error_box(self, f"Erweitern fehlgeschlagen: {e}"))

    def _after_mode(self):
        QTimer.singleShot(1500, self.reload_outputs)

    def identify(self):
        self._ident = [IdentifyWindow(s, i + 1) for i, s in enumerate(QGuiApplication.screens())]
        for w in self._ident:
            w.show()
        QTimer.singleShot(3000, lambda: [w.close() for w in self._ident])

    # ================================================================ Darstellung
    def _appearance_group(self):
        box = QGroupBox("Darstellung")
        form = QFormLayout(box)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(10)
        a = self.config["appearance"]
        mode = QComboBox()
        for key, label in theme.MODES.items():
            mode.addItem(label, key)
        mode.setCurrentIndex(max(0, mode.findData(a.get("mode", "system"))))
        swatches = QHBoxLayout()
        swatches.setSpacing(8)
        self._swatches = {}
        for key, (label, color) in theme.ACCENTS.items():
            b = Swatch(theme.system_accent() if key == "system" else color, label)
            b.system = key == "system"
            b.brand = key == "alupc"
            b.clicked.connect(lambda _=False, k=key: self._set_accent(k))
            self._swatches[key] = b
            swatches.addWidget(b)
        swatches.addStretch(1)
        self._style_swatches(a.get("accent", "alupc"))
        from ..transitions import TRANSITIONS

        tr = self.config["transition"]
        self.transition_combo = QComboBox()
        # lange Einträge („Zoom (altes Bild …)“) dürfen die Karte nicht breiter machen
        self.transition_combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.transition_combo.setMinimumContentsLength(12)
        for key, label in TRANSITIONS.items():
            self.transition_combo.addItem(label, key)
        current = "schnitt" if not a.get("fade", True) else tr.get("type", "blende")
        self.transition_combo.setCurrentIndex(max(0, self.transition_combo.findData(current)))
        self.transition_ms = QSpinBox()
        self.transition_ms.setRange(50, 5000)
        self.transition_ms.setSingleStep(50)
        self.transition_ms.setSuffix(" ms")
        self.transition_ms.setValue(int(tr.get("ms", 400)))
        try_btn = button("Ausprobieren", "play")
        try_btn.setToolTip("Zeigt den Übergang einmal auf Monitor 2 (der aktuelle Inhalt bleibt)")
        try_btn.clicked.connect(self._try_transition)
        tr_row = QHBoxLayout()
        tr_row.addWidget(self.transition_combo, 1)
        tr_row.addWidget(self.transition_ms)
        tr_row.addWidget(try_btn)

        def save_transition():
            kind = self.transition_combo.currentData()
            self.config["transition"] = {"type": kind, "ms": self.transition_ms.value()}
            self._save_appearance(fade=kind != "schnitt", emit=False)
            self.transition_ms.setEnabled(kind != "schnitt")

        self.transition_combo.currentIndexChanged.connect(save_transition)
        self.transition_ms.valueChanged.connect(save_transition)
        self.transition_ms.setEnabled(current != "schnitt")

        def save_mode():
            self._save_appearance(mode=mode.currentData())

        mode.currentIndexChanged.connect(save_mode)
        form.addRow("Design:", mode)
        form.addRow("Akzentfarbe:", swatches)
        form.addRow("Desktop:", self._desktop_theme_row())
        from .. import perf

        power = QComboBox()
        power.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        power.setMinimumContentsLength(12)
        for key, label in perf.MODES.items():
            power.addItem(label, key)
        power.setCurrentIndex(max(0, power.findData(a.get("performance", "auto"))))
        weak = "schwacher PC erkannt → sparsam" if perf.weak_pc() else "starker PC erkannt → flüssig"
        power.setToolTip(f"Automatisch: {weak}. Sparsam: Animationen mit weniger Bildern, "
                         "keine Übergänge in der App.")

        def save_power():
            self.config["appearance"] = {**self.config["appearance"], "performance": power.currentData()}
            perf.configure(power.currentData())

        power.currentIndexChanged.connect(save_power)
        form.addRow("Leistung:", power)
        form.addRow("Szenenwechsel:", tr_row)
        hint = QLabel("Beim Wechsel auf Monitor 2 · je Szene änderbar")
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        form.addRow("", hint)
        return box

    def _desktop_theme_row(self):
        """AluPC-Farben auch für Windows bzw. KDE übernehmen – mit „Zurück“."""
        from .. import desktop_theme as dt

        row = QHBoxLayout()
        self.desk_apply = button("AluPC-Farben für den Desktop", "palette")
        self.desk_apply.setToolTip("Windows: Akzentfarbe · KDE: Farbschema „AluPC“ – vorherige Farben werden gemerkt")
        self.desk_undo = button("Zurück", "undo")
        self.desk_state = QLabel()
        self.desk_state.setObjectName("Muted")
        ok, why = dt.supported()

        def refresh():
            on = dt.active()
            self.desk_undo.setEnabled(on)
            self.desk_apply.setEnabled(ok)
            self.desk_state.setText(why if not ok else ("an" if on else ""))

        def do(action):
            done, msg = action()
            self.desk_state.setText(msg)
            if not done:
                error_box(self, msg)
            self.desk_undo.setEnabled(dt.active())

        self.desk_apply.clicked.connect(lambda: do(lambda: dt.apply(theme.current().dark)))
        self.desk_undo.clicked.connect(lambda: do(dt.restore))
        row.addWidget(self.desk_apply)
        row.addWidget(self.desk_undo)
        row.addWidget(self.desk_state, 1)
        refresh()
        return row

    def _try_transition(self):
        """Aktuellen Inhalt mit dem eingestellten Übergang neu zeigen."""
        c = self.controller
        if c.mode == "content" and c.content:
            c.show_source(c.content, remember=False, sound=False)
        else:
            error_box(self, "Auf Monitor 2 läuft gerade kein Inhalt von AluPC – zeige zuerst eine Szene "
                            "oder Quelle an.")

    def _style_swatches(self, active: str):
        for key, b in self._swatches.items():
            b.setChecked(key == active)

    def _set_accent(self, key: str):
        self._save_appearance(accent=key)

    def _save_appearance(self, emit: bool = True, **changes):
        a = dict(self.config["appearance"])
        a.update(changes)
        self.config["appearance"] = a
        if emit:
            self.theme_changed.emit()
            self._style_swatches(a.get("accent", "alupc"))

    # ================================================================ AluPC
    def _hardware_group(self):
        from .hardware_page import HardwarePage

        self.hardware = HardwarePage(self.controller, scroll=False)
        return self.hardware

    # ================================================================ Handy & Kamera
    def _phone_group(self):
        box = QGroupBox("Handy-Steuerung – Rechte")
        lay = QVBoxLayout(box)
        allow = {"senden": True, "steuern": True, "live": True, "laser": True,
                 **(self.config["cast"].get("allow") or {})}
        checks = {}
        for key, text in (("senden", "Senden (Fotos, Videos, Links, Text)"),
                          ("steuern", "Fernsteuern"),
                          ("live", "Live-Bild"),
                          ("laser", "Laser && Zeichnen")):
            box_ = QCheckBox(text)
            box_.setChecked(bool(allow.get(key, True)))
            checks[key] = box_
            lay.addWidget(box_)
        auto = QCheckBox("Beim Start mitstarten")
        auto.setChecked(bool(self.config["cast"].get("autostart")))
        lay.addWidget(auto)

        def save(*_):
            self.config["cast"] = {**self.config["cast"], "autostart": auto.isChecked(),
                                   "allow": {k: c.isChecked() for k, c in checks.items()}}
            self.controller._cast_snapshot()

        for w in (*checks.values(), auto):
            w.toggled.connect(save)
        hint = QLabel("Zugang mit dem Code aus dem QR-Code – oder ohne Code: das Handy bittet um Freigabe, "
                      "AluPC fragt hier „Erlauben / Ablehnen“.")
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        lay.addWidget(hint)
        devices = QLabel()
        devices.setWordWrap(True)
        forget = button("Alle Freigaben löschen", "trash")

        def show_devices():
            devs = self.controller.cast.devices()
            devices.setText("Freigegeben: " + ", ".join(f"{d.get('name', 'Handy')} ({d.get('added', '')})"
                                                         for d in devs) if devs else "Noch kein Gerät freigegeben.")
            forget.setEnabled(bool(devs))

        def do_forget():
            self.controller.cast.forget_devices()
            show_devices()

        forget.clicked.connect(do_forget)
        self.controller.access_requested.connect(lambda *_: QTimer.singleShot(500, show_devices))
        show_devices()
        lay.addWidget(devices)
        lay.addWidget(forget, 0, Qt.AlignLeft)
        return box

    def _camera_group(self):
        box = QGroupBox("Kamera")
        form = QFormLayout(box)
        self.camera_combo = QComboBox()
        self.camera_combo.setToolTip("Diese Kamera startet ein Klick auf die Kachel „Kamera“ sofort")
        self._fill_camera_combo()
        self.camera_combo.currentIndexChanged.connect(
            lambda _i: self.config.__setitem__("default_camera", self.camera_combo.currentData() or ""))
        from PySide6.QtMultimedia import QMediaDevices

        self._media_devices = QMediaDevices(self)
        self._media_devices.videoInputsChanged.connect(self._fill_camera_combo)
        fit = QComboBox()
        fit.addItem("Füllen", "cover")
        fit.addItem("Ganzes Bild", "contain")
        fit.setCurrentIndex(max(0, fit.findData(self.config.get("camera_fit", "cover"))))
        fit.currentIndexChanged.connect(lambda _i: self.config.__setitem__("camera_fit", fit.currentData()))
        form.addRow("Standard-Kamera:", self.camera_combo)
        form.addRow("Anzeige:", fit)
        hint = QLabel("Startet per Klick auf „Kamera“ · Pfeil: andere wählen")
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        form.addRow(hint)
        return box

    def _fill_start_combo(self):
        combo = self.start_combo
        combo.blockSignals(True)
        combo.clear()
        for key, label in (("last", "Zuletzt gezeigt"), ("none", "Nichts"),
                           ("mirror", "Spiegeln"), ("camera", "Kamera"), ("airplay", "AirPlay (iPhone/iPad)"),
                           ("cast", "QR-Code")):
            combo.addItem(label, key)
        for name in self.config.scene_names():
            combo.addItem(f"Szene: {name}", f"scene:{name}")
        combo.setCurrentIndex(max(0, combo.findData(self.controller.start_content_setting())))
        combo.blockSignals(False)

    def _start_changed(self, *_):
        value = self.start_combo.currentData() or "last"
        self.config["start_content"] = value
        self.config["restore_last_content"] = value != "none"

    def _fill_camera_combo(self, *_):
        from PySide6.QtMultimedia import QMediaDevices

        from ..sources import camera_id

        combo = self.camera_combo
        combo.blockSignals(True)
        combo.clear()
        devices = QMediaDevices.videoInputs()
        for d in devices:
            combo.addItem(d.description(), camera_id(d))
        if not devices:
            combo.addItem("Keine Kamera gefunden", "")
        combo.setEnabled(bool(devices))
        # vorausgewählt: gespeicherte Kamera, sonst die erste
        combo.setCurrentIndex(max(0, combo.findData(self.config.get("default_camera", ""))))
        combo.blockSignals(False)

    def showEvent(self, e):
        super().showEvent(e)
        if hasattr(self, "start_combo"):
            self._fill_start_combo()  # neue/umbenannte Szenen

    def _app_group(self):
        box = QGroupBox("Allgemein")
        form = QFormLayout(box)
        self.screen_combo = QComboBox()
        self._fill_screen_combo()
        self.screen_combo.currentIndexChanged.connect(self._screen_changed)
        app = QGuiApplication.instance()
        app.screenAdded.connect(lambda _s: self._fill_screen_combo())
        app.screenRemoved.connect(lambda _s: self._fill_screen_combo())

        self.start_combo = QComboBox()
        self.start_combo.setToolTip("Was Monitor 2 zeigt, sobald AluPC startet")
        self._fill_start_combo()
        self.start_combo.currentIndexChanged.connect(self._start_changed)

        auto = QCheckBox("Autostart")
        try:
            auto.setChecked(autostart.is_enabled())
        except Exception:  # noqa: BLE001
            auto.setEnabled(False)
        auto.toggled.connect(self._autostart)
        minimized = QCheckBox("Minimiert starten")
        minimized.setChecked(bool(self.config["start_minimized"]))
        minimized.toggled.connect(lambda v: self.config.__setitem__("start_minimized", v))
        form.addRow("Monitor 2:", self.screen_combo)
        form.addRow("Beim Start zeigen:", self.start_combo)
        form.addRow("", auto)
        form.addRow("", minimized)
        diag = button("Diagnose kopieren", "copy")
        diag.setToolTip("Prüft Monitore, Spiegeln, AirPlay, RGB … und kopiert das Ergebnis – "
                        "zum Weitergeben, wenn etwas nicht geht")
        diag.clicked.connect(self._diagnose)
        report = button("Fehlerbericht …", "alert")
        report.setToolTip("Speichert eine Datei mit Diagnose und Fehlerprotokollen – zum Weiterschicken")
        report.clicked.connect(self._bug_report)
        again = button("Ersteinrichtung starten", "sync")
        again.setToolTip("Prüft Monitore und Spiegeln, installiert Handy-Programme – wie beim ersten Start")
        again.clicked.connect(lambda: self.window().open_first_run())
        form.addRow("Hilfe:", flow_row(diag, report, again))  # bricht im kleinen Fenster um
        return box

    def _bug_report(self):
        from .bug_report_dialog import BugReportDialog

        BugReportDialog(self.controller, self).exec()

    def _diagnose(self):
        from PySide6.QtWidgets import QApplication

        from .. import diagnose

        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            text = diagnose.report(self.controller)
        finally:
            QApplication.restoreOverrideCursor()
        QApplication.clipboard().setText(text)
        box = QMessageBox(self)
        box.setWindowTitle("Diagnose")
        box.setText("Diagnose kopiert – einfach einfügen.")
        box.setDetailedText(text)
        box.exec()

    def _fill_screen_combo(self):
        self.screen_combo.blockSignals(True)
        self.screen_combo.clear()
        self.screen_combo.addItem("Automatisch (nicht der Hauptmonitor)", "")
        for s in QGuiApplication.screens():
            self.screen_combo.addItem(f"{s.name()} – {s.size().width()}×{s.size().height()}", s.name())
        idx = self.screen_combo.findData(self.config["output_screen"])
        self.screen_combo.setCurrentIndex(max(0, idx))
        self.screen_combo.blockSignals(False)

    def _screen_changed(self):
        self.config["output_screen"] = self.screen_combo.currentData() or ""
        self.controller.update_screens()

    def _autostart(self, on):
        try:
            autostart.set_enabled(on)
        except Exception as exc:  # noqa: BLE001
            error_box(self, f"Autostart konnte nicht geändert werden: {exc}")

    # ================================================================ Sichtschutz
    def _privacy_group(self):
        box = QGroupBox("Sichtschutz")
        form = QFormLayout(box)
        p = self.config["privacy"]
        text = QLineEdit(p.get("text", ""))
        text.setPlaceholderText("z. B. „Gleich geht's weiter“ – leer = nur schwarz")
        img_row = QHBoxLayout()
        img = QLineEdit(p.get("image", ""))
        img.setPlaceholderText("optional: Bild/Logo statt Schwarz")
        browse = button("Durchsuchen …", "image")
        img_row.addWidget(img, 1)
        img_row.addWidget(browse)

        def save():
            self.config["privacy"] = {"text": text.text(), "image": img.text()}

        def pick():
            path, _ = QFileDialog.getOpenFileName(self, "Bild wählen", img.text(),
                                                  "Bilder (*.png *.jpg *.jpeg *.bmp *.webp)")
            if path:
                img.setText(path)
                save()

        text.editingFinished.connect(save)
        img.editingFinished.connect(save)
        browse.clicked.connect(pick)
        form.addRow("Text:", text)
        form.addRow("Bild:", img_row)
        return box

    # ================================================================ Bild-in-Bild
    def _pip_group(self):
        box = QGroupBox("Bild-in-Bild")
        form = QFormLayout(box)
        cfg = self.config["pip"]
        width = QSpinBox()
        width.setRange(160, 1920)
        width.setSuffix(" px breit")
        width.setValue(int(cfg.get("width", 480)))
        opacity = QSlider(Qt.Horizontal)
        opacity.setRange(20, 100)
        opacity.setValue(int(float(cfg.get("opacity", 1.0)) * 100))
        fps = QSpinBox()
        fps.setRange(1, 60)
        fps.setSuffix(" Bilder/s")
        fps.setValue(int(cfg.get("fps", 10)))

        def save():
            self.config["pip"] = {"width": width.value(), "opacity": opacity.value() / 100, "fps": fps.value()}
            if self.controller.pip is not None:
                self.controller.pip.apply_settings()

        width.valueChanged.connect(save)
        opacity.valueChanged.connect(save)
        fps.valueChanged.connect(save)
        form.addRow("Größe:", width)
        form.addRow("Deckkraft:", opacity)
        form.addRow("Aktualisierung:", fps)
        return box

    # ================================================================ Bildschirmschoner
    def _screensaver_group(self):
        from .screensaver_settings import ScreensaverSettings

        self.screensaver_box = ScreensaverSettings(self.controller)
        return self.screensaver_box

    # ================================================================ Timer
    def _timer_group(self):
        box = QGroupBox("Timer")
        form = QFormLayout(box)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(10)
        cfg = self.config["timer"]
        mode = QComboBox()
        mode.addItem("Countdown (läuft rückwärts)", "countdown")
        mode.addItem("Stoppuhr (läuft vorwärts)", "stoppuhr")
        mode.setCurrentIndex(max(0, mode.findData(cfg.get("mode", "countdown"))))
        minutes = QSpinBox()
        minutes.setRange(0, 999)
        minutes.setSuffix(" min")
        minutes.setValue(int(cfg.get("minutes", 5)))
        seconds = QSpinBox()
        seconds.setRange(0, 59)
        seconds.setSuffix(" s")
        seconds.setValue(int(cfg.get("seconds", 0)))
        text = QLineEdit(cfg.get("finished_text", "Zeit ist um!"))
        warn = QCheckBox("Warnfarben (orange · rot · blinken)")
        warn.setChecked(bool(cfg.get("warn_colors", True)))
        size = QSpinBox()
        size.setRange(5, 80)
        size.setSuffix(" % der Bildhöhe")
        size.setValue(int(cfg.get("size", 30)))
        dur = QHBoxLayout()
        dur.addWidget(minutes)
        dur.addWidget(seconds)

        def save(*_):
            self.config["timer"] = {"mode": mode.currentData(), "minutes": minutes.value(),
                                    "seconds": seconds.value(), "finished_text": text.text(),
                                    "warn_colors": warn.isChecked(), "size": size.value()}

        for w in (minutes, seconds, size):
            w.valueChanged.connect(save)
        mode.currentIndexChanged.connect(save)
        warn.toggled.connect(save)
        text.editingFinished.connect(save)
        form.addRow("Art:", mode)
        form.addRow("Dauer:", dur)
        form.addRow("Text am Ende:", text)
        form.addRow("Schriftgröße:", size)
        form.addRow("", warn)
        hint = QLabel("Für die Timer-Kachel · Töne unter „Töne“")
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        form.addRow(hint)
        return box

    # ================================================================ Töne
    def _sound_group(self):
        from PySide6.QtMultimedia import QMediaDevices

        from ..sounds import EVENTS
        from .sound_picker import SoundPicker

        box = QGroupBox("Töne")
        form = QFormLayout(box)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(8)
        cfg = self.config["sounds"]
        enabled = QCheckBox("Töne abspielen")
        enabled.setChecked(bool(cfg.get("enabled", True)))
        volume = QSlider(Qt.Horizontal)
        volume.setRange(0, 100)
        volume.setValue(int(cfg.get("volume", 70)))
        device = QComboBox()
        device.addItem("Standard-Ausgabe des Systems", "")
        for dev in QMediaDevices.audioOutputs():
            device.addItem(dev.description(), bytes(dev.id()).decode(errors="replace"))
        idx = device.findData(cfg.get("device", ""))
        device.setCurrentIndex(max(0, idx))

        def save_general(*_):
            new = dict(self.config["sounds"])
            new.update({"enabled": enabled.isChecked(), "volume": volume.value(), "device": device.currentData()})
            self.config["sounds"] = new

        enabled.toggled.connect(save_general)
        volume.sliderReleased.connect(save_general)
        volume.valueChanged.connect(lambda _v: volume.isSliderDown() or save_general())
        device.currentIndexChanged.connect(save_general)
        form.addRow("", enabled)
        form.addRow("Lautstärke:", volume)
        form.addRow("Ausgabe:", device)
        hint = QLabel("Tipp: Ausgabe = Monitor/Beamer (HDMI)")
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        form.addRow(hint)
        self.sound_pickers = {}
        for event, label in EVENTS.items():
            picker = SoundPicker(self.controller.sounds, cfg.get("events", {}).get(event, ""))

            def save_event(spec, e=event):
                new = dict(self.config["sounds"])
                events = dict(new.get("events", {}))
                events[e] = spec
                new["events"] = events
                self.config["sounds"] = new

            picker.changed.connect(save_event)
            form.addRow(label.replace("&", "&&") + ":", picker)
            self.sound_pickers[event] = picker
        more = QLabel("Eigene Töne: WAV, MP3, OGG, FLAC, M4A")
        more.setObjectName("Muted")
        more.setWordWrap(True)
        form.addRow(more)
        return box

    # ================================================================ Sprache
    def _open_voice_test(self):
        from .voice_test import VoiceTestDialog

        VoiceTestDialog(self.controller, self).exec()

    def _voice_group(self):
        from PySide6.QtMultimedia import QMediaDevices
        from PySide6.QtWidgets import QProgressBar

        from .. import voice

        box = QGroupBox("Sprachbefehle")
        lay = QVBoxLayout(box)
        intro = QLabel("Ganz normal sprechen – mit Startwort davor: „Alu PC, mach den Bildschirm schwarz“, „Alu PC, "
                       "Licht auf blau“, „Alu PC, wie spät ist es?“. Läuft komplett auf dem PC (offline), es geht kein "
                       "Ton ins Internet.")
        intro.setWordWrap(True)
        lay.addWidget(intro)
        cfg = self.config["voice"]
        self.voice_on = QCheckBox("Sprachbefehle an")
        self.voice_on.setChecked(bool(cfg.get("on")))
        lay.addWidget(self.voice_on)
        form = QFormLayout()
        mic = QComboBox()
        mic.addItem("Standard-Mikrofon des Systems", "")
        for dev in QMediaDevices.audioInputs():
            mic.addItem(dev.description(), bytes(dev.id()).decode(errors="replace"))
        mic.setCurrentIndex(max(0, mic.findData(cfg.get("device", ""))))
        form.addRow("Mikrofon:", mic)
        wake_row = QHBoxLayout()
        self.wake_boxes = {}
        for key, label in voice.WAKES.items():
            cb = QCheckBox(f"„{label} …“")
            cb.setChecked(key in (cfg.get("wake") or list(voice.WAKES)))
            wake_row.addWidget(cb)
            self.wake_boxes[key] = cb
        wake_row.addStretch(1)
        form.addRow("Startwort:", wake_row)
        lay.addLayout(form)
        self.voice_state = QLabel()
        self.voice_state.setObjectName("Muted")
        self.voice_heard = QLabel()
        self.voice_heard.setObjectName("Muted")
        self.voice_heard.setWordWrap(True)
        state_row = QHBoxLayout()
        state_row.addWidget(self.voice_state, 1)
        test_btn = button("Sprache testen …", "mic", primary=True)
        test_btn.setToolTip("Prüft Schritt für Schritt: Modell, Mikrofon, Pegel, was erkannt wird, Startwort, Befehl")
        test_btn.clicked.connect(self._open_voice_test)
        state_row.addWidget(test_btn)
        lay.addLayout(state_row)
        lay.addWidget(self.voice_heard)
        model_row = QHBoxLayout()
        self.voice_model = QLabel()
        self.voice_model.setWordWrap(True)
        self.voice_dl = button("Herunterladen", "download")
        self.voice_bar = QProgressBar()
        self.voice_bar.setMaximumWidth(220)
        self.voice_bar.hide()
        model_row.addWidget(self.voice_model, 1)
        model_row.addWidget(self.voice_bar)
        model_row.addWidget(self.voice_dl)
        lay.insertLayout(1, model_row)  # Schritt 1 ganz oben: ohne Sprachmodell geht nichts
        # ---- Erkennung, Stimme, Gespräch
        from .. import speech, stt

        talk = QGroupBox("Erkennung && Stimme")
        tf = QFormLayout(talk)
        stt_row = QHBoxLayout()
        stt_box = QComboBox()
        stt_box.addItem("Standard (Vosk, schnell)", "vosk")
        for key, (_repo, label, size) in stt.MODELS.items():
            stt_box.addItem(f"{label} – ca. {size} MB", key)
        stt_box.setCurrentIndex(max(0, stt_box.findData(cfg.get("stt", "vosk"))))
        stt_dl = button("Herunterladen", "download")
        stt_bar = QProgressBar()
        stt_bar.setMaximumWidth(160)
        stt_bar.hide()
        stt_row.addWidget(stt_box, 1)
        stt_row.addWidget(stt_bar)
        stt_row.addWidget(stt_dl)
        tf.addRow("Erkennung:", stt_row)
        stt_note = QLabel()
        stt_note.setObjectName("Muted")
        stt_note.setWordWrap(True)
        tf.addRow("", stt_note)
        tts_row = QHBoxLayout()
        tts_box = QComboBox()
        for key, (_file, label, size) in speech.PIPER_VOICES.items():
            tts_box.addItem(f"{label} – ca. {size} MB", key)
        tts_box.addItem("System-Stimme (Windows / espeak)", "system")
        tts_box.setCurrentIndex(max(0, tts_box.findData(cfg.get("tts", "thorsten"))))
        tts_dl = button("Herunterladen", "download")
        tts_bar = QProgressBar()
        tts_bar.setMaximumWidth(160)
        tts_bar.hide()
        tts_row.addWidget(tts_box, 1)
        tts_row.addWidget(tts_bar)
        tts_row.addWidget(tts_dl)
        tf.addRow("Stimme:", tts_row)
        sys_row = QHBoxLayout()
        speak_voice = QComboBox()
        speak_voice.addItem("Standard-System-Stimme", "")
        for name in self.controller.speaker.voices():
            speak_voice.addItem(name, name)
        speak_voice.setCurrentIndex(max(0, speak_voice.findData(cfg.get("speak_voice", ""))))
        sys_row.addWidget(speak_voice, 1)
        tf.addRow("System-Stimme:", sys_row)
        rate_box = QComboBox()
        for key in speech.RATES:
            rate_box.addItem(key.capitalize(), key)
        rate_box.setCurrentIndex(max(0, rate_box.findData(cfg.get("speak_rate", "normal"))))
        test_say = button("Probehören", "sound")
        rate_row = QHBoxLayout()
        rate_row.addWidget(rate_box)
        rate_row.addStretch(1)
        rate_row.addWidget(test_say)
        tf.addRow("Tempo:", rate_row)
        tts_note = QLabel()
        tts_note.setObjectName("Muted")
        tts_note.setWordWrap(True)
        tf.addRow("", tts_note)
        self.speak_on = QCheckBox("Antworten per Stimme")
        self.speak_on.setChecked(bool(cfg.get("speak", True)))
        tf.addRow("", self.speak_on)
        follow = QCheckBox(f"Nach jeder Antwort {voice.FOLLOW_SECONDS} s ohne Startwort weiterhören")
        follow.setToolTip("Aus (empfohlen): AluPC reagiert nur, wenn ein Satz mit dem Startwort beginnt. Nur das "
                          "Startwort sagen („Computer?“ → „Ja?“) geht immer.")
        follow.setChecked(bool(cfg.get("follow_all", False)))
        tf.addRow("", follow)
        mic_hint = QLabel("Mikrofon-Schalter: Knopf „Zuhören“ links oder Strg+Alt+H – solange an, zählt jeder Satz "
                          "(kein Startwort nötig). Nochmal drücken oder „Hör auf zuzuhören“ = aus.")
        mic_hint.setObjectName("Muted")
        mic_hint.setWordWrap(True)
        tf.addRow("", mic_hint)
        lay.addWidget(talk)

        def refresh_talk():
            key = stt_box.currentData()
            if key == "vosk":
                stt_note.setText("Hört das Startwort und kurze Befehle. Für ganze Sätze lieber Whisper.")
                stt_dl.hide()
            elif not stt.available():
                stt_note.setText("Whisper fehlt in dieser AluPC-Version.")
                stt_dl.hide()
            elif stt.ready(key):
                stt_note.setText("✓ Heruntergeladen. Whisper schreibt jeden Satz an AluPC noch einmal genau mit "
                                 "(offline; braucht pro Satz kurz Rechenzeit).")
                stt_dl.hide()
            else:
                stt_note.setText("Noch nicht heruntergeladen – bis dahin hört AluPC mit Vosk.")
                stt_dl.setVisible(True)
            tkey = tts_box.currentData()
            speak_voice.setEnabled(tkey == "system")
            if tkey == "system":
                tts_note.setText("" if self.controller.speaker.available() else
                                 "Keine System-Stimme gefunden – Linux: sudo apt install speech-dispatcher espeak-ng")
                tts_dl.hide()
            elif not speech.piper_available(quick=True):
                tts_note.setText("Natürliche Stimmen (Piper) fehlen in dieser AluPC-Version – es spricht die "
                                 "System-Stimme.")
                tts_dl.hide()
            elif speech.voice_ready(tkey):
                tts_note.setText("✓ Natürliche Stimme (offline).")
                tts_dl.hide()
            else:
                tts_note.setText("Noch nicht heruntergeladen – bis dahin spricht die System-Stimme.")
                tts_dl.setVisible(True)

        def save_speak(*_):
            self.config["voice"] = {**self.config["voice"], "speak": self.speak_on.isChecked(),
                                    "speak_voice": speak_voice.currentData(), "tts": tts_box.currentData(),
                                    "speak_rate": rate_box.currentData(), "stt": stt_box.currentData(),
                                    "follow_all": follow.isChecked()}
            self.controller.speaker.reload()
            refresh_talk()

        def save_stt(*_):
            save_speak()
            if self.controller.voice.running():  # Whisper im Hintergrund (neu) laden
                import threading

                threading.Thread(target=self.controller.voice.load_stt, daemon=True).start()

        def fetch(bar, btn, work, what):
            btn.setEnabled(False)
            bar.show()
            bar.setRange(0, 0)

            def run(status):
                return work(lambda d, t: status("", d, t))

            def progress(_text, d, t):
                if t:
                    bar.setRange(0, 100)
                    bar.setValue(int(100 * d / t))

            def done(_r):
                bar.hide()
                btn.setEnabled(True)
                save_stt()

            def failed(e):
                bar.hide()
                btn.setEnabled(True)
                error_box(self, f"{what} konnte nicht geladen werden: {e}")

            run_async(run, done, failed, progress)

        stt_dl.clicked.connect(lambda: fetch(stt_bar, stt_dl, lambda p: stt.download(stt_box.currentData(), p),
                                             "Whisper"))
        tts_dl.clicked.connect(lambda: fetch(tts_bar, tts_dl,
                                             lambda p: speech.download_voice(tts_box.currentData(), p), "Die Stimme"))
        self.speak_on.toggled.connect(save_speak)
        speak_voice.currentIndexChanged.connect(save_speak)
        tts_box.currentIndexChanged.connect(save_speak)
        rate_box.currentIndexChanged.connect(save_speak)
        follow.toggled.connect(save_speak)
        stt_box.currentIndexChanged.connect(save_stt)
        test_say.clicked.connect(lambda: self.controller.speaker.say(
            "Alles klar, Monitor 2 ist jetzt schwarz. Sag einfach, was ich tun soll.", force=True))
        refresh_talk()

        # ---- eigene Befehle
        custom_box = QGroupBox("Eigene Befehle")
        cl = QVBoxLayout(custom_box)
        self.custom_list = QListWidget()
        self.custom_list.setMaximumHeight(120)
        cl.addWidget(self.custom_list)
        crow = QHBoxLayout()
        custom_add = button("Befehl hinzufügen …", "plus")
        custom_del = button("Entfernen", "trash")
        crow.addWidget(custom_add)
        crow.addWidget(custom_del)
        crow.addStretch(1)
        cl.addLayout(crow)
        lay.addWidget(custom_box)

        def fill_custom():
            from .voice_custom import describe_action

            self.custom_list.clear()
            for c in self.config["voice"].get("custom") or []:
                item = QListWidgetItem(f"„{c['say']}“  →  {describe_action(self.config, c['do'])}")
                item.setData(Qt.UserRole, c["say"])
                self.custom_list.addItem(item)
            if not self.custom_list.count():
                self.custom_list.addItem("(noch keine – z. B. „Pause machen“ → Szene Pause)")
                self.custom_list.item(0).setFlags(Qt.NoItemFlags)

        def add_custom():
            from .voice_custom import VoiceCustomDialog

            VoiceCustomDialog(self.controller, self).exec()
            fill_custom()

        def del_custom():
            item = self.custom_list.currentItem()
            if item is None or not item.data(Qt.UserRole):
                return
            cfg_v = self.config["voice"]
            self.config["voice"] = {**cfg_v, "custom": [c for c in cfg_v.get("custom") or []
                                                        if c.get("say") != item.data(Qt.UserRole)]}
            fill_custom()

        custom_add.clicked.connect(add_custom)
        custom_del.clicked.connect(del_custom)
        fill_custom()

        # ---- nur bestimmte Stimmen
        voices_box = QGroupBox("Nur auf bestimmte Stimmen hören")
        vl = QVBoxLayout(voices_box)
        self.only_voices = QCheckBox("Befehle nur von angelernten Stimmen annehmen")
        self.only_voices.setChecked(bool(cfg.get("only_voices")))
        vl.addWidget(self.only_voices)
        self.voice_list = QListWidget()
        self.voice_list.setMaximumHeight(110)
        vl.addWidget(self.voice_list)
        vrow = QHBoxLayout()
        self.voice_add = button("Stimme anlernen …", "plus")
        self.voice_del = button("Entfernen", "trash")
        strict = QComboBox()
        for key, label in (("streng", "streng"), ("normal", "normal"), ("locker", "locker")):
            strict.addItem(f"Genauigkeit: {label}", key)
        strict.setCurrentIndex(max(0, strict.findData(cfg.get("strict", "normal"))))
        vrow.addWidget(self.voice_add)
        vrow.addWidget(self.voice_del)
        vrow.addStretch(1)
        vrow.addWidget(strict)
        vl.addLayout(vrow)
        spk_row = QHBoxLayout()
        self.spk_label = QLabel()
        self.spk_label.setWordWrap(True)
        self.spk_dl = button("Herunterladen", "download")
        spk_row.addWidget(self.spk_label, 1)
        spk_row.addWidget(self.spk_dl)
        vl.addLayout(spk_row)
        note = QLabel("Ein Filter gegen Zurufe aus dem Raum – kein Schutz: eine Aufnahme oder eine sehr ähnliche Stimme "
                      "kann ihn täuschen. Hinter „Zuletzt gehört“ steht, wen AluPC erkannt hat und wie sicher "
                      "(kleiner = ähnlicher).")
        note.setObjectName("Muted")
        note.setWordWrap(True)
        vl.addWidget(note)
        lay.addWidget(voices_box)

        cmds = QLabel("<b>Beispiele</b> (Startwort davor, z. B. „Alu PC, …“ – oder Mikrofon-Schalter an):<br>"
                      "„Mach den Bildschirm schwarz“ · „Bild wieder an“ · „Kein Standbild mehr“<br>"
                      "„Zeig die Kamera / das Wetter / den Systemstatus / das Whiteboard“<br>"
                      "„Licht aus“ · „Licht auf blau“ · „Licht wie der Bildschirm“ · „Licht heller“<br>"
                      "„Timer auf fünf Minuten“ · „Timer Pause“ · „Bildschirmschoner an“ · „Overlays aus“<br>"
                      "„Nächste Szene“ · „Szene <i>Name</i>“ · „Lass uns Pong spielen“ · „Nächste Frage“<br>"
                      "„Nächstes Lied“ · „Musik Pause“ · „Dreh das Glücksrad“ · „Computer sperren“<br>"
                      "Fragen: „Wie spät ist es?“ · „Welcher Tag ist heute?“ · „Wie wird das Wetter?“ · "
                      "„Wie warm ist der Prozessor?“ · „Wie geht es dem Computer?“ · „Was kannst du?“ · "
                      "„Erzähl einen Witz“<br>Nur „Alu PC“ sagen → „Ja?“ – dann den Satz ohne Startwort.")
        cmds.setObjectName("Muted")
        cmds.setWordWrap(True)
        lay.addWidget(cmds)
        vc = self.controller.voice

        def fill_voices():
            self.voice_list.clear()
            for v in self.config["voice"].get("voices") or []:
                self.voice_list.addItem(v.get("name", "?"))
            if not self.voice_list.count():
                self.voice_list.addItem("(noch keine Stimme angelernt)")
                self.voice_list.item(0).setFlags(Qt.NoItemFlags)

        def refresh():
            ok = voice.vosk_available(quick=True)
            ready = voice.model_ready()
            spk = voice.spk_ready()
            self.spk_label.setText("Stimmerkennung ✓" if spk else
                                   f"Stimmerkennung fehlt – einmal herunterladen (ca. {voice.SPK_SIZE_MB} MB)")
            self.spk_dl.setVisible(ok and not spk)
            self.voice_add.setEnabled(ok and ready)  # der Dialog lädt Stimmerkennung und startet das Zuhören selbst
            self.voice_add.setToolTip("" if ready else "Erst das Sprachmodell herunterladen")
            if not ok:
                self.voice_model.setText("Spracherkennung (Vosk) fehlt in dieser AluPC-Version.")
            elif ready:
                self.voice_model.setText("Sprachmodell: Deutsch ✓")
            else:
                self.voice_model.setText(f"<b>Schritt 1:</b> Sprachmodell herunterladen (ca. {voice.MODEL_SIZE_MB} MB) – "
                                         "erst dann lassen sich die Sprachbefehle einschalten.")
            t = theme.current()
            self.voice_model.setStyleSheet("" if ready or not ok else f"color: {t.warning};")
            self.voice_dl.setProperty("primary", not ready)
            self.voice_dl.style().unpolish(self.voice_dl)
            self.voice_dl.style().polish(self.voice_dl)
            self.voice_dl.setVisible(ok and not ready)
            self.voice_on.setEnabled(ok and ready)
            self.voice_state.setText(f"Status: {vc.state}")

        def save(*_):
            wakes = [k for k, cb in self.wake_boxes.items() if cb.isChecked()] or ["monitor"]
            self.config["voice"] = {**self.config["voice"], "on": self.voice_on.isChecked(),
                                    "device": mic.currentData(), "wake": wakes}
            vc.stop()
            vc.apply()
            refresh()

        def save_filter(*_):
            self.config["voice"] = {**self.config["voice"], "only_voices": self.only_voices.isChecked(),
                                    "strict": strict.currentData()}

        def enroll():
            from .voice_enroll import VoiceEnrollDialog

            VoiceEnrollDialog(self.controller, self).exec()
            fill_voices()

        def remove_voice():
            item = self.voice_list.currentItem()
            if item is None or not (item.flags() & Qt.ItemIsEnabled):
                return
            cfg = self.config["voice"]
            self.config["voice"] = {**cfg, "voices": [v for v in cfg.get("voices") or []
                                                      if v.get("name") != item.text()]}
            fill_voices()

        def download_spk():
            self.spk_dl.setEnabled(False)

            def done(_p):
                self.spk_dl.setEnabled(True)
                vc.stop()  # neu laden, damit die Stimmerkennung dabei ist
                vc.apply()
                refresh()

            def failed(e):
                self.spk_dl.setEnabled(True)
                error_box(self, f"Stimmerkennung konnte nicht geladen werden: {e}")

            run_async(lambda: voice.download_model(url=voice.SPK_URL, target=voice.spk_dir(), ready=voice.spk_ready),
                      done, failed)

        for cb in self.wake_boxes.values():
            cb.toggled.connect(save)
        self.only_voices.toggled.connect(save_filter)
        strict.currentIndexChanged.connect(save_filter)
        self.voice_add.clicked.connect(enroll)
        self.voice_del.clicked.connect(remove_voice)
        self.spk_dl.clicked.connect(download_spk)
        fill_voices()

        def download():
            self.voice_dl.setEnabled(False)
            self.voice_bar.show()
            self.voice_bar.setRange(0, 0)

            def work(status):
                return voice.download_model(lambda done, total: status(f"{done // 1_000_000} MB", done, total))

            def progress(_text, done, total):
                if total:
                    self.voice_bar.setRange(0, 100)
                    self.voice_bar.setValue(int(100 * done / total))

            def done(_path):
                self.voice_bar.hide()
                self.voice_dl.setEnabled(True)
                refresh()

            def failed(e):
                self.voice_bar.hide()
                self.voice_dl.setEnabled(True)
                error_box(self, f"Sprachmodell konnte nicht geladen werden: {e}")

            run_async(work, done, failed, progress)

        self.voice_on.toggled.connect(save)
        mic.currentIndexChanged.connect(save)
        self.voice_dl.clicked.connect(download)
        vc.state_changed.connect(lambda _s: refresh())
        vc.heard.connect(lambda text: self.voice_heard.setText(f"Zuletzt gehört: {text}"))
        vc.rejected.connect(lambda text, why: self.voice_heard.setText(f"Ignoriert: „{text}“ – {why}"))
        refresh()
        return box

    def _open_display_settings(self):
        from ..platform import open_display_settings

        if not open_display_settings():
            error_box(self, "Anzeige-Einstellungen des Systems nicht gefunden.")

    # ================================================================ Tastenkürzel
    def _hotkey_group(self):
        box = QGroupBox("Tastenkürzel")
        form = QFormLayout(box)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(8)
        self.hotkey_edits = {}
        for action, label in HOTKEY_LABELS.items():
            btn = HotkeyButton(self.config["hotkeys"].get(action, ""), label)
            btn.changed.connect(lambda seq, a=action: self._save_hotkey(a, seq))
            form.addRow(label.replace("&", "&&") + ":", btn)
            self.hotkey_edits[action] = btn
        more = QLabel("Szenen: im Szenen-Editor · Eigene Kacheln: „Startseite anpassen“")
        more.setWordWrap(True)
        form.addRow(more)
        if self.hotkeys is not None and getattr(self.hotkeys, "system_wide", False):
            form.addRow(QLabel("Gelten überall – auch wenn AluPC im Hintergrund ist"))
        else:
            hint = QLabel("Gelten, wenn AluPC aktiv ist · überall: Befehl <tt>alupc --befehl standbild</tt> "
                          "als Kurzbefehl im System eintragen")
            hint.setWordWrap(True)
            hint.setTextFormat(Qt.RichText)
            form.addRow(hint)
        if not IS_WINDOWS:
            kde = button("KDE-Kurzbefehle öffnen", "keyboard")
            kde.clicked.connect(self._open_kde_shortcuts)
            form.addRow("", kde)
        self.hotkey_status = QLabel("")
        self.hotkey_status.setWordWrap(True)
        self.hotkey_status.setStyleSheet(f"color: {theme.current().warning};")
        form.addRow(self.hotkey_status)
        return box

    def refresh_scene_lists(self):
        """Szenenliste im Bildschirmschoner aktualisieren (nach Anlegen/Umbenennen/Löschen)."""
        box = getattr(self, "screensaver_box", None)
        if box is None:
            return
        combo = box.scene_combo
        current = combo.currentText()
        combo.blockSignals(True)
        combo.clear()
        combo.addItems(self.config.scene_names())
        combo.setCurrentText(current)
        combo.blockSignals(False)

    def _open_kde_shortcuts(self):
        import shutil
        import subprocess

        for cmd in (["systemsettings", "kcm_keys"], ["kcmshell6", "kcm_keys"], ["kcmshell5", "kcm_keys"]):
            if shutil.which(cmd[0]):
                subprocess.Popen(cmd)
                return
        error_box(self, "Die KDE-Systemeinstellungen wurden nicht gefunden.")

    def _save_hotkey(self, action, seq: str):
        hotkeys = dict(self.config["hotkeys"])
        hotkeys[action] = seq
        self.config["hotkeys"] = hotkeys
        problems = self.hotkeys.apply(hotkeys)
        self.hotkey_status.setText("\n".join(problems))
        self.hotkeys_changed.emit()

    # ================================================================ Monitor 2
    def _output_group(self):
        box = QGroupBox("Monitor 2")
        lay = QVBoxLayout(box)
        cfg = self.config["output"]
        taskbar = QCheckBox("Taskleiste auf Monitor 2 ausblenden (Windows)")
        taskbar.setChecked(bool(cfg.get("hide_taskbar", True)))
        taskbar.setEnabled(IS_WINDOWS)
        badge = QCheckBox("Standbild-Symbol zeigen")
        badge.setChecked(bool(cfg.get("freeze_badge", True)))
        cursor = QCheckBox("Mauszeiger beim Spiegeln zeigen")
        cursor.setChecked(bool(cfg.get("mirror_cursor", True)))
        confine = QCheckBox("Maus bleibt auf Monitor 1 (außer „Erweitern“)")
        confine.setChecked(bool(cfg.get("confine_cursor", True)))
        guard = self.controller.cursor_guard
        if guard.wayland_gap:
            confine.setToolTip("KDE/Wayland: AluPC rückt Monitor 2 dafür mit Abstand weg – über die Lücke kommt "
                               "die Maus nicht. Bei „Erweitern“ und beim Beenden geht die Lücke wieder zu.")
        elif not guard.supported:
            confine.setEnabled(False)
            confine.setToolTip("KDE erlaubt unter Wayland keinem Programm, die Maus festzuhalten. Beim Anmelden "
                               "die Sitzung „Plasma (X11)“ wählen – dort hält AluPC sie auf Monitor 1.")

        def save(*_):
            self.config["output"] = {**self.config["output"], "hide_taskbar": taskbar.isChecked(),
                                     "freeze_badge": badge.isChecked(), "mirror_cursor": cursor.isChecked(),
                                     "confine_cursor": confine.isChecked()}
            self.controller.apply_output_settings()

        for w in (taskbar, badge, cursor, confine):
            w.toggled.connect(save)
            lay.addWidget(w)
        if not confine.isEnabled():
            note = QLabel("Maus festhalten: unter Wayland nicht möglich · "
                          "mit „Plasma (X11)“ beim Anmelden geht es")
            note.setObjectName("Muted")
            note.setWordWrap(True)
            lay.addWidget(note)

        hint = QLabel("„Computer sperren“ = wie Win+L (auch Monitor 2)")
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        lay.addWidget(hint)
        return box
