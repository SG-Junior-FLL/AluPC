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
from .widgets import button, font, rounded

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
        self.label.setText(f"Siehst du alles richtig? Ohne Bestätigung werden die alten Einstellungen "
                           f"in {self.remaining} Sekunden wiederhergestellt.")

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
        p.setBrush(QColor(self.color))
        p.drawEllipse(r)
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
        ("monitor", "Monitore", "Auflösung, Hz, Anordnung"),
        ("pip", "Monitor 2", "Maus, Standbild, Sichtschutz, Bild-in-Bild"),
        ("palette", "Darstellung", "Design und Akzentfarbe"),
        ("moon", "Bildschirmschoner", "Stil, Zeit, Verhalten"),
        ("timer", "Timer", "Dauer, Art, Warnfarben"),
        ("sound", "Töne", "Ton bei Aktionen, eigene Töne"),
        ("keyboard", "Tastenkürzel", "Alles per Tastatur"),
        ("sliders", "Allgemein", "Autostart, Monitor-Wahl"),
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
            "Allgemein": [self._app_group],
        }
        self.nav = QListWidget()
        self.nav.setObjectName("SetupNav")
        self.nav.setFixedWidth(230)
        self.nav.setIconSize(QSize(20, 20))
        self.stack = QStackedWidget()
        t = theme.current()
        for icon_name, title, sub in self.SECTIONS:
            item = QListWidgetItem(icons.icon(icon_name, t.accent, 20), f"{title}\n{sub}")
            item.setSizeHint(QSize(220, 54))
            self.nav.addItem(item)
            area = QScrollArea()
            area.setWidgetResizable(True)
            area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            inner = QWidget()
            lay = QVBoxLayout(inner)
            lay.setContentsMargins(0, 0, 8, 0)
            lay.setSpacing(6)
            for build in builders[title]:
                lay.addWidget(build())
            lay.addStretch(1)
            area.setWidget(inner)
            self.stack.addWidget(area)
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav.setCurrentRow(0)
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(18)
        root.addWidget(self.nav)
        root.addWidget(self.stack, 1)
        controller.changed.connect(self._update_arrangement)
        QTimer.singleShot(0, self.reload_outputs)

    def show_section(self, title: str) -> None:
        for i, (_icon, name, _sub) in enumerate(self.SECTIONS):
            if name == title:
                self.nav.setCurrentRow(i)

    # ================================================================ Monitore
    def _display_group(self):
        box = QGroupBox("Monitore (Einstellungen des Systems)")
        lay = QVBoxLayout(box)
        backend = self.controller.display
        self.backend_label = QLabel(f"System: {session_info()} – Steuerung über: {backend.name}")
        lay.addWidget(self.backend_label)
        if not backend.available():
            hint = QLabel("Monitor-Einstellungen sind hier nicht verfügbar. Unter Kubuntu wird "
                          "„kscreen-doctor“ (Paket libkf5screen-bin bzw. kscreen) benötigt.")
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
        if IS_WINDOWS:
            open_btn = button("Windows-Anzeigeeinstellungen", "sliders")
            open_btn.clicked.connect(lambda: __import__("os").startfile("ms-settings:display"))
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
                  lambda e: self.backend_label.setText(f"Monitore konnten nicht gelesen werden: {e}"))

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
            b = Swatch(color, label)
            b.clicked.connect(lambda _=False, k=key: self._set_accent(k))
            self._swatches[key] = b
            swatches.addWidget(b)
        swatches.addStretch(1)
        self._style_swatches(a.get("accent", "blau"))
        from ..transitions import TRANSITIONS

        tr = self.config["transition"]
        self.transition_combo = QComboBox()
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
        form.addRow("Szenenwechsel:", tr_row)
        hint = QLabel("Übergang, wenn auf Monitor 2 eine andere Szene oder ein anderer Inhalt erscheint. "
                      "Jede Szene kann im Szenen-Editor einen eigenen Übergang bekommen.")
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        form.addRow("", hint)
        return box

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
            self._style_swatches(a.get("accent", "blau"))

    # ================================================================ AluPC
    def _app_group(self):
        box = QGroupBox("AluPC")
        form = QFormLayout(box)
        self.screen_combo = QComboBox()
        self._fill_screen_combo()
        self.screen_combo.currentIndexChanged.connect(self._screen_changed)
        app = QGuiApplication.instance()
        app.screenAdded.connect(lambda _s: self._fill_screen_combo())
        app.screenRemoved.connect(lambda _s: self._fill_screen_combo())

        restore = QCheckBox("Beim Start den letzten Inhalt wieder anzeigen")
        restore.setChecked(bool(self.config["restore_last_content"]))
        restore.toggled.connect(lambda v: self.config.__setitem__("restore_last_content", v))
        auto = QCheckBox("Beim Anmelden automatisch starten")
        try:
            auto.setChecked(autostart.is_enabled())
        except Exception:  # noqa: BLE001
            auto.setEnabled(False)
        auto.toggled.connect(self._autostart)
        minimized = QCheckBox("Beim Start nur als Symbol in der Taskleiste")
        minimized.setChecked(bool(self.config["start_minimized"]))
        minimized.toggled.connect(lambda v: self.config.__setitem__("start_minimized", v))
        form.addRow("Monitor für andere Leute:", self.screen_combo)
        form.addRow("", restore)
        form.addRow("", auto)
        form.addRow("", minimized)
        return box

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
        box = QGroupBox("Sichtschutz (Kachel „Schwarz“)")
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
        box = QGroupBox("Timer (Kachel „Timer“ und Tastenkürzel)")
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
        warn = QCheckBox("Letzte Minute orange, letzte 10 Sekunden rot, am Ende blinken")
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
        hint = QLabel("Gilt für die Timer-Kachel. Eigene Kacheln können einen Timer mit eigener Dauer haben. "
                      "Töne bei Start/Ende stellst du unter „Töne“ ein.")
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        form.addRow(hint)
        return box

    # ================================================================ Töne
    def _sound_group(self):
        from PySide6.QtMultimedia import QMediaDevices

        from ..sounds import EVENTS
        from .sound_picker import SoundPicker

        box = QGroupBox("Töne bei Aktionen")
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
        hint = QLabel("Tipp: Als Ausgabe den Monitor/Beamer (HDMI) wählen, dann hören die anderen den Ton.")
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
            form.addRow(label + ":", picker)
            self.sound_pickers[event] = picker
        more = QLabel("„Eigene Datei hochladen …“ kopiert den Ton in den AluPC-Ordner – er bleibt also, auch wenn "
                      "die Originaldatei gelöscht wird. Erlaubt: WAV, MP3, OGG, FLAC, M4A …")
        more.setObjectName("Muted")
        more.setWordWrap(True)
        form.addRow(more)
        return box

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
            form.addRow(label + ":", btn)
            self.hotkey_edits[action] = btn
        more = QLabel("Eigene Tastenkürzel für <b>Szenen</b> legst du im Szenen-Editor fest, für "
                      "<b>eigene Kacheln</b> unter Start → „Startseite anpassen“.")
        more.setWordWrap(True)
        form.addRow(more)
        if IS_WINDOWS:
            text = "Die Tastenkürzel funktionieren überall in Windows, auch wenn AluPC im Hintergrund ist."
            form.addRow(QLabel(text))
        else:
            text = ("In AluPC funktionieren die Tastenkürzel immer. <b>Überall in KDE</b>: Systemeinstellungen "
                    "→ Tastatur → Kurzbefehle → „AluPC“ – dort stehen Standbild, Schwarz, Bild-in-Bild, "
                    "Bildschirmschoner, Spiegeln, Erweitern und die Szenenwechsel schon bereit (nach der "
                    "Installation mit dem .deb-Paket oder install.sh). Oder: „Neu hinzufügen“ → „Befehl“ mit "
                    "<tt>alupc --befehl standbild</tt> bzw. <tt>alupc --befehl szene:Name</tt>.")
            hint = QLabel(text)
            hint.setWordWrap(True)
            hint.setTextFormat(Qt.RichText)
            form.addRow(hint)
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
        from ..cursor import CursorGuard

        box = QGroupBox("Monitor 2")
        lay = QVBoxLayout(box)
        cfg = self.config["output"]
        taskbar = QCheckBox("Taskleiste auf Monitor 2 ausblenden, solange AluPC dort etwas zeigt (Windows)")
        taskbar.setChecked(bool(cfg.get("hide_taskbar", True)))
        taskbar.setEnabled(IS_WINDOWS)
        badge = QCheckBox("Beim Standbild ein kleines Schneeflocken-Symbol oben rechts auf Monitor 2 zeigen")
        badge.setChecked(bool(cfg.get("freeze_badge", True)))
        cursor = QCheckBox("Mauszeiger beim Spiegeln auf Monitor 2 zeigen")
        cursor.setChecked(bool(cfg.get("mirror_cursor", True)))
        confine = QCheckBox("Maus bleibt auf Monitor 1 – nur bei „Erweitern“ darf sie auf Monitor 2")
        confine.setChecked(bool(cfg.get("confine_cursor", True)))
        if not CursorGuard().supported:
            confine.setEnabled(False)
            confine.setToolTip("Unter Wayland dürfen Programme die Maus nicht festhalten.")

        def save(*_):
            self.config["output"] = {**self.config["output"], "hide_taskbar": taskbar.isChecked(),
                                     "freeze_badge": badge.isChecked(), "mirror_cursor": cursor.isChecked(),
                                     "confine_cursor": confine.isChecked()}
            self.controller.apply_output_settings()

        for w in (taskbar, badge, cursor, confine):
            w.toggled.connect(save)
            lay.addWidget(w)
        if not confine.isEnabled():
            note = QLabel("Maus festhalten geht unter Wayland nicht (das System erlaubt es Programmen nicht).")
            note.setObjectName("Muted")
            note.setWordWrap(True)
            lay.addWidget(note)

        hint = QLabel("„Computer sperren“ (Seitenleiste, Taskleisten-Symbol, Befehl „sperren“) sperrt den "
                      "ganzen Computer wie Win+L. Der Sperrbildschirm des Systems liegt dann über allen "
                      "Monitoren – auch Monitor 2 zeigt so lange nichts von AluPC.")
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        lay.addWidget(hint)
        return box
