"""Setup: Monitore (Auflösung, Hz, Anordnung) und Einstellungen von AluPC."""

from __future__ import annotations

import hashlib
import secrets

from PySide6.QtCore import QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QGuiApplication, QKeySequence, QPainter, QPen
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
    QInputDialog,
    QKeySequenceEdit,
    QLabel,
    QLineEdit,
    QMessageBox,
    QScrollArea,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..config import HOTKEY_LABELS
from ..platform import IS_WINDOWS, autostart, session_info
from ..platform.base import ROTATIONS, clone_outputs, place, side_of
from . import theme
from .util import error_box, run_async
from .widgets import button, font, rounded

SIDES = [("right", "rechts vom Hauptmonitor"), ("left", "links vom Hauptmonitor"),
         ("above", "über dem Hauptmonitor"), ("below", "unter dem Hauptmonitor"),
         ("mirror", "gespiegelt (gleiche Position)")]


def hash_pin(pin: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", pin.encode(), salt.encode(), 200_000).hex()


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


class SetupPage(QScrollArea):
    theme_changed = Signal()
    hotkeys_changed = Signal()

    def __init__(self, controller, hotkeys, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.config = controller.config
        self.hotkeys = hotkeys
        self.outputs = []
        self.setWidgetResizable(True)
        inner = QWidget()
        self.setWidget(inner)
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(0, 0, 8, 0)
        lay.setSpacing(6)
        lay.addWidget(self._display_group())
        lay.addWidget(self._appearance_group())
        lay.addWidget(self._app_group())
        lay.addWidget(self._privacy_group())
        lay.addWidget(self._pip_group())
        lay.addWidget(self._screensaver_group())
        lay.addWidget(self._hotkey_group())
        lay.addWidget(self._lock_group())
        lay.addStretch(1)
        controller.changed.connect(self._update_arrangement)
        QTimer.singleShot(0, self.reload_outputs)

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
        fade = QCheckBox("Weich überblenden, wenn der Inhalt auf Monitor 2 wechselt")
        fade.setChecked(bool(a.get("fade", True)))

        def save_mode():
            self._save_appearance(mode=mode.currentData())

        mode.currentIndexChanged.connect(save_mode)
        fade.toggled.connect(lambda v: self._save_appearance(fade=v, emit=False))
        form.addRow("Design:", mode)
        form.addRow("Akzentfarbe:", swatches)
        form.addRow("", fade)
        return box

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
        fps.setRange(1, 30)
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
        from ..screensaver import STYLES, WHEN

        box = QGroupBox("Bildschirmschoner (Monitor 2)")
        form = QFormLayout(box)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(10)
        cfg = self.config["screensaver"]
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
        scene.addItems(self.config.scene_names())
        scene.setCurrentText(cfg.get("scene", ""))
        test = button("Jetzt starten / beenden", "moon", primary=True)
        test.clicked.connect(self.controller.toggle_screensaver)
        info = QLabel(self.controller.screensaver.idle.describe())
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
            self.config["screensaver"] = {
                "enabled": enabled.isChecked(), "minutes": minutes.value(), "when": when.currentData(),
                "style": style.currentData(), "text": text.text(), "image": image.text(),
                "folder": folder.text(), "interval": interval.value(), "scene": scene.currentText(),
            }
            update_rows()

        def pick_image():
            path, _ = QFileDialog.getOpenFileName(self, "Logo wählen", image.text(),
                                                  "Bilder (*.png *.jpg *.jpeg *.bmp *.webp *.svg)")
            if path:
                image.setText(path)
                save()

        def pick_folder():
            path = QFileDialog.getExistingDirectory(self, "Bilderordner wählen", folder.text())
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
        self._screensaver_scene_combo = scene
        update_rows()
        return box

    # ================================================================ Tastenkürzel
    def _hotkey_group(self):
        box = QGroupBox("Tastenkürzel")
        form = QFormLayout(box)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(8)
        self.hotkey_edits = {}
        for action, label in HOTKEY_LABELS.items():
            edit = QKeySequenceEdit(QKeySequence(self.config["hotkeys"].get(action, ""), QKeySequence.PortableText))
            edit.setMaximumSequenceLength(1)
            edit.editingFinished.connect(lambda a=action, e=edit: self._save_hotkey(a, e))
            clear = button("", "x")
            clear.setToolTip("Tastenkürzel entfernen")
            clear.clicked.connect(lambda _=False, a=action, e=edit: (e.clear(), self._save_hotkey(a, e)))
            row = QHBoxLayout()
            row.addWidget(edit, 1)
            row.addWidget(clear)
            form.addRow(label + ":", row)
            self.hotkey_edits[action] = edit
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
        combo = getattr(self, "_screensaver_scene_combo", None)
        if combo is None:
            return
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

    def _save_hotkey(self, action, edit):
        hotkeys = dict(self.config["hotkeys"])
        hotkeys[action] = edit.keySequence().toString(QKeySequence.PortableText)
        self.config["hotkeys"] = hotkeys
        problems = self.hotkeys.apply(hotkeys)
        self.hotkey_status.setText("\n".join(problems))
        self.hotkeys_changed.emit()

    # ================================================================ Sperre
    def _lock_group(self):
        box = QGroupBox("AluPC sperren")
        lay = QVBoxLayout(box)
        lock = self.config["lock"]
        self.lock_check = QCheckBox("Beim Start und über „Sperren“ nur mit Fingerabdruck (oder PIN) bedienbar")
        self.lock_check.setChecked(bool(lock.get("enabled")))
        self.lock_check.toggled.connect(self._lock_toggled)
        pin_btn = button("Ersatz-PIN festlegen …", "lock")
        pin_btn.clicked.connect(self._set_pin)
        hint = QLabel("Die PIN brauchst du, falls der Sensor mal nicht geht. Die Sperre schützt nur die "
                      "Bedienung von AluPC, nicht den ganzen Computer.")
        hint.setWordWrap(True)
        lay.addWidget(self.lock_check)
        lay.addWidget(pin_btn, 0, Qt.AlignLeft)
        lay.addWidget(hint)
        return box

    def _lock_toggled(self, on):
        lock = dict(self.config["lock"])
        if on and not lock.get("pin_hash"):
            if not self._set_pin():
                self.lock_check.setChecked(False)
                return
            lock = dict(self.config["lock"])
        lock["enabled"] = on
        self.config["lock"] = lock

    def _set_pin(self) -> bool:
        pin, ok = QInputDialog.getText(self, "Ersatz-PIN", "Neue PIN (mindestens 4 Zeichen):", QLineEdit.Password)
        if not ok:
            return False
        if len(pin) < 4:
            QMessageBox.warning(self, "PIN", "Die PIN muss mindestens 4 Zeichen haben.")
            return False
        salt = secrets.token_hex(16)
        lock = dict(self.config["lock"])
        lock.update({"pin_salt": salt, "pin_hash": hash_pin(pin, salt)})
        self.config["lock"] = lock
        QMessageBox.information(self, "PIN", "PIN gespeichert.")
        return True

