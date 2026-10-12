"""Seite „Audio & Kamera“ – ein Mischpult für den ganzen PC: Kanalzüge für jeden Ausgang, jedes Mikro und jedes
Programm mit Ton (Schieberegler, Pegel, Stumm, Standardgerät), virtuelle Geräte hinzufügen/entfernen, Ton
weiterleiten (Mikro → virtuelles Mikro, Mithören) und Monitor 2 als virtuelle Kamera. Gleich unter Linux und Windows."""

from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMenu,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .. import mixer
from ..audio import IS_WINDOWS
from ..mixer_route import SPEAKER
from . import icons, theme
from .util import run_async
from .widgets import button, font, page_header

STRIP_W = 112
ROW_H = 26  # Höhe eines Weiterleitungs-Knopfs


def short_name(name: str) -> str:
    """„AluPC Virtuelles Mikro“ → „Virtuelles Mikro“ (im schmalen Kanalzug)."""
    return name[6:] if name.startswith("AluPC ") else name
COLORS = {"out": "#3b82f6", "in": "#22c55e", "virtual": "#a855f7", "app": "#f59e0b"}


class Meter(QWidget):
    """Senkrechter Pegel (grün → gelb → rot) mit Spitzenwert, fällt weich ab."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.level = 0.0
        self.hold = 0.0
        self.setFixedWidth(10)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)

    def set_level(self, v: float) -> None:
        v = max(0.0, min(1.0, v))
        new = v if v > self.level else self.level * 0.78 + v * 0.22
        hold = max(new, self.hold - 0.012)
        if abs(new - self.level) > 0.004 or abs(hold - self.hold) > 0.004:
            self.level, self.hold = new, hold
            self.update()

    def paintEvent(self, _e):
        t = theme.current()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(t.surface2))
        p.drawRoundedRect(r, 4, 4)
        if self.level > 0.003:
            grad = QLinearGradient(r.bottomLeft(), r.topLeft())
            grad.setColorAt(0.0, QColor(t.success))
            grad.setColorAt(0.68, QColor(t.success))
            grad.setColorAt(0.82, QColor(t.warning))
            grad.setColorAt(1.0, QColor(t.danger))
            fill = QRectF(r.x(), r.bottom() - r.height() * self.level, r.width(), r.height() * self.level)
            path = QPainterPath()
            path.addRoundedRect(r, 4, 4)
            p.setClipPath(path)
            p.fillRect(fill, grad)
            p.setClipping(False)
        if self.hold > 0.01:
            y = r.bottom() - r.height() * self.hold
            p.setPen(QPen(QColor(t.text), 1.6))
            p.drawLine(r.left() + 1, y, r.right() - 1, y)


class Strip(QFrame):
    """Ein Kanalzug: Farbstreifen, Symbol, Name, Pegel + Schieberegler, %, Stumm, Standard, Weiterleitungen."""

    def __init__(self, page, kind: str, item: dict, stream: bool = False):
        super().__init__()
        self.page, self.kind, self.item, self.stream = page, kind, item, stream
        self.key = ("app:" if stream else f"{kind}:") + str(item["id"])
        t = theme.current()
        self.color = COLORS["app"] if stream else (COLORS["virtual"] if item.get("virtual") else COLORS[kind])
        self.setObjectName("Strip")
        self.setFixedWidth(STRIP_W)
        self.setStyleSheet(f"#Strip {{ background:{t.surface}; border:1px solid {t.border}; border-radius:14px;"
                           f" border-top:4px solid {self.color}; }}")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 10, 8, 10)
        lay.setSpacing(6)
        ic = QLabel()
        icon_name = "window" if stream else ("mic" if kind == "in" else "sound")
        ic.setPixmap(icons.pixmap(icon_name, self.color, 22))
        ic.setAlignment(Qt.AlignCenter)
        lay.addWidget(ic)
        title = item.get("app") if stream else short_name(item["name"])
        self.name = QLabel(title)
        self.name.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        self.name.setWordWrap(True)
        self.name.setFont(font(9, QFont.Bold))
        self.name.setFixedHeight(34)
        self.name.setToolTip(((item.get("title") or "") + "\n" + item.get("device", "")).strip() if stream
                             else item["id"])
        lay.addWidget(self.name)
        sub = QLabel("virtuell" if item.get("virtual") and not stream else
                     ((item.get("title") or "Programm")[:18] if stream else ("Ausgang" if kind == "out" else "Eingang")))
        sub.setAlignment(Qt.AlignCenter)
        sub.setStyleSheet(f"color:{self.color if item.get('virtual') else t.muted}; font-size:10.5px;")
        lay.addWidget(sub)
        mid = QHBoxLayout()
        mid.setSpacing(6)
        mid.addStretch(1)
        self.meter = Meter()
        mid.addWidget(self.meter)
        self.slider = QSlider(Qt.Vertical)
        self.slider.setRange(0, 100)
        self.slider.setMinimumHeight(150)
        self.slider.valueChanged.connect(self._slide)
        mid.addWidget(self.slider)
        mid.addStretch(1)
        lay.addLayout(mid, 1)
        self.pct = QLabel()
        self.pct.setAlignment(Qt.AlignCenter)
        self.pct.setFont(font(9.5, QFont.Bold))
        lay.addWidget(self.pct)
        row = QHBoxLayout()
        row.setSpacing(4)
        row.addStretch(1)
        self.mute = QToolButton()
        self.mute.setCheckable(True)
        self.mute.setAutoRaise(True)
        self.mute.setIconSize(QSize(18, 18))
        self.mute.toggled.connect(self._mute)
        row.addWidget(self.mute)
        self.default = None
        if not stream:
            self.default = QToolButton()
            self.default.setAutoRaise(True)
            self.default.setIconSize(QSize(18, 18))
            self.default.clicked.connect(self._default)
            row.addWidget(self.default)
        row.addStretch(1)
        lay.addLayout(row)
        self.extra = QWidget()  # Weiterleitungen / Ziel-Gerät – feste Höhe, damit alle Regler gleich lang sind
        self.routes_box = QVBoxLayout(self.extra)
        self.routes_box.setContentsMargins(0, 0, 0, 0)
        self.routes_box.setSpacing(3)
        self.routes_box.setAlignment(Qt.AlignTop)
        lay.addWidget(self.extra)
        self.target = None
        if stream and mixer.can_move_streams():
            self.target = QComboBox()
            self.target.setToolTip("Auf welchem Gerät dieses Programm läuft")
            self.target.currentIndexChanged.connect(self._move)
            self.routes_box.addWidget(self.target)
        self._send = QTimer(self, singleShot=True, interval=120)
        self._send.timeout.connect(self._apply_volume)
        self.update_values(item)

    # ---- Werte
    def update_values(self, item: dict) -> None:
        self.item = item
        if not self.slider.isSliderDown():
            self.slider.blockSignals(True)
            self.slider.setValue(min(100, int(item.get("volume", 0))))
            self.slider.blockSignals(False)
        self.mute.blockSignals(True)
        self.mute.setChecked(bool(item.get("muted")))
        self.mute.blockSignals(False)
        self.pct.setText(f"{self.slider.value()} %")
        self._icons()

    def set_targets(self, outs: list[dict]) -> None:
        if self.target is None:
            return
        self.target.blockSignals(True)
        self.target.clear()
        for d in outs:
            self.target.addItem(d["name"], d["id"])
        self.target.setCurrentIndex(max(0, self.target.findData(self.item.get("device", ""))))
        self.target.blockSignals(False)

    def set_routes(self, options: list[tuple[str, str, bool]]) -> None:
        """Weiterleitungs-Knöpfe: (Ziel-ID, Beschriftung, an?)."""
        t = theme.current()
        for dst, label, on in options:
            b = QToolButton()
            b.setCheckable(True)
            b.setChecked(on)
            b.setText(label)
            b.setToolTip("Mithören: auf dem Lautsprecher hören" if dst == SPEAKER else
                         f"Ton auch ins virtuelle Mikro „{label[2:]}“")
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            col = COLORS["virtual"]
            b.setStyleSheet(f"QToolButton {{ font-size:10.5px; padding:2px 4px; border-radius:7px;"
                            f" border:1px solid {t.border}; color:{t.muted}; }}"
                            f"QToolButton:checked {{ background:{t.soft(col, 0.22)}; color:{t.text};"
                            f" border-color:{col}; }}")
            b.toggled.connect(lambda checked, d=dst: self.page.toggle_route(self.item["id"], d, checked))
            self.routes_box.addWidget(b)

    def _icons(self):
        t = theme.current()
        on = self.mute.isChecked()
        name = ("mic_off" if self.kind == "in" else "mute") if on else ("mic" if self.kind == "in" else "sound")
        self.mute.setIcon(icons.icon(name, t.danger if on else t.text, 18))
        self.mute.setToolTip("Stumm – Klick: wieder an" if on else "Stumm schalten")
        if self.default is not None:
            is_def = bool(self.item.get("default"))
            self.default.setIcon(icons.icon("star", t.warning if is_def else t.muted, 18))
            self.default.setToolTip("Standardgerät" if is_def else "Als Standardgerät nehmen")

    def _slide(self, v: int) -> None:
        self.pct.setText(f"{v} %")
        self._send.start()

    def _apply_volume(self) -> None:
        v, sid, kind = self.slider.value(), self.item["id"], self.kind
        if self.stream:
            run_async(lambda: mixer.set_stream(kind, sid, volume=v))
        else:
            run_async(lambda: mixer.set_device(kind, sid, volume=v))

    def _mute(self, on: bool) -> None:
        self._icons()
        sid, kind = self.item["id"], self.kind
        if self.stream:
            run_async(lambda: mixer.set_stream(kind, sid, muted=on))
        else:
            run_async(lambda: mixer.set_device(kind, sid, muted=on))

    def _default(self) -> None:
        dev, kind = self.item["id"], self.kind
        run_async(lambda: mixer.set_default(kind, dev), lambda _r: self.page.reload(), owner=self.page)

    def _move(self, _i: int) -> None:
        dev, sid, kind = self.target.currentData(), self.item["id"], self.kind
        run_async(lambda: mixer.move_stream(kind, sid, dev), lambda r: self.page.show_result(r), owner=self.page)


class AudioPage(QWidget):
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        from ..mixer_meters import Meters

        self.controller = controller
        self.routing = controller.audio_routing
        self.meters = Meters()
        self.destroyed.connect(lambda *_, m=self.meters: m.stop())  # Fenster weg ohne „hide“: Messung trotzdem beenden
        self._snap: dict = {}
        self._signature = None
        self._strips: dict[str, Strip] = {}
        self._busy = False
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(14)
        root.addWidget(page_header("Audio & Kamera", "Mischpult für den ganzen PC: Geräte, Programme, virtuelle "
                                                     "Mikros und Monitor 2 als Kamera", "mixer"))
        self.note = QLabel()
        self.note.setWordWrap(True)
        self.note.setObjectName("Muted")
        self.note.hide()
        root.addWidget(self.note)
        top = QHBoxLayout()
        top.setSpacing(14)
        top.addWidget(self._virtual_card(), 3)
        top.addWidget(self._cam_card(), 2)
        root.addLayout(top)
        root.addWidget(self._desk_card(), 1)
        self.routing.changed.connect(self._fill_virtual)
        controller.vcam.changed.connect(self._fill_cam)
        self._timer = QTimer(self, interval=2000)
        self._timer.timeout.connect(self.reload)
        self._meter_timer = QTimer(self, interval=50)
        self._meter_timer.timeout.connect(self._read_meters)
        self._cam_timer = QTimer(self, interval=1000)
        self._cam_timer.timeout.connect(self._fill_cam)

    # ---------------------------------------------------------------- Karten
    def _card(self, title: str, icon_name: str, sub: str = "") -> tuple[QFrame, QVBoxLayout]:
        card = QFrame()
        card.setObjectName("Card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(8)
        head = QHBoxLayout()
        ic = QLabel()
        ic.setPixmap(icons.pixmap(icon_name, theme.current().accent, 20))
        head.addWidget(ic)
        lab = QLabel(f"<b>{title}</b>")
        lab.setFont(font(12))
        head.addWidget(lab)
        head.addStretch(1)
        lay.addLayout(head)
        if sub:
            s = QLabel(sub)
            s.setObjectName("Muted")
            s.setWordWrap(True)
            lay.addWidget(s)
        card.head = head
        return card, lay

    def _desk_card(self) -> QFrame:
        card, lay = self._card("Mischpult", "sliders", "Jeder Kanal: Lautstärke, Pegel, Stumm, ★ = Standardgerät. "
                                                       "Lila Knöpfe leiten Ton weiter (→ virtuelles Mikro, Mithören)." +
                               ("" if mixer.can_move_streams() else
                                " Programme auf ein anderes Gerät legen: Windows-Einstellungen."))
        if IS_WINDOWS:
            win = button("Windows: Gerät je Programm", "sliders")
            win.setToolTip("„App-Lautstärke und Geräteeinstellungen“ öffnen")
            win.clicked.connect(mixer.open_app_settings)
            card.head.addWidget(win)
        self.desk = QHBoxLayout()
        self.desk.setSpacing(10)
        self.desk.setContentsMargins(2, 4, 2, 8)
        holder = QWidget()
        holder.setLayout(self.desk)
        scroll = QScrollArea()
        scroll.setWidget(holder)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setMinimumHeight(440)
        scroll.setStyleSheet("QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; }")
        lay.addWidget(scroll, 1)
        return card

    def _virtual_card(self) -> QFrame:
        card, lay = self._card("Virtuelle Geräte", "mixer")
        self.v_pill = QLabel()
        card.head.addWidget(self.v_pill)
        self.v_toggle = button("", "play", primary=True)
        self.v_toggle.clicked.connect(self._toggle_virtual)
        card.head.addWidget(self.v_toggle)
        self.v_text = QLabel()
        self.v_text.setWordWrap(True)
        self.v_text.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lay.addWidget(self.v_text)
        self.v_list = QHBoxLayout()
        self.v_list.setSpacing(6)
        self.v_list.setContentsMargins(0, 0, 0, 0)
        holder = QWidget()
        holder.setLayout(self.v_list)
        lay.addWidget(holder)
        row = QHBoxLayout()
        self.add_out = button("Ausgang", "plus")
        self.add_out.setToolTip("Neuen virtuellen Ausgang anlegen (z. B. „Musik“) – Programme dort hinein spielen")
        self.add_out.clicked.connect(lambda: self._add_device("out"))
        self.add_mic = button("Mikro", "plus")
        self.add_mic.setToolTip("Neues virtuelles Mikro anlegen (z. B. „Discord“) – Ton per Knopf hineinleiten")
        self.add_mic.clicked.connect(lambda: self._add_device("mic"))
        row.addWidget(self.add_out)
        row.addWidget(self.add_mic)
        row.addStretch(1)
        lay.addLayout(row)
        self.v_error = QLabel()
        self.v_error.setWordWrap(True)
        self.v_error.setStyleSheet(f"color:{theme.current().danger}")
        lay.addWidget(self.v_error)
        return card

    def _cam_card(self) -> QFrame:
        from PySide6.QtWidgets import QSpinBox

        from ..vcam import SIZES

        card, lay = self._card("Virtuelle Kamera", "webcam")
        self.c_pill = QLabel()
        card.head.addWidget(self.c_pill)
        self.c_toggle = button("", "play", primary=True)
        self.c_toggle.clicked.connect(self._toggle_cam)
        card.head.addWidget(self.c_toggle)
        self.c_text = QLabel()
        self.c_text.setWordWrap(True)
        self.c_text.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lay.addWidget(self.c_text)
        self.c_preview = QLabel()
        self.c_preview.setFixedSize(224, 126)
        self.c_preview.setStyleSheet("background:#000; border-radius:8px;")
        self.c_preview.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.c_preview, 0, Qt.AlignLeft)
        row = QHBoxLayout()
        cfg = self.controller.vcam.cfg()
        self.c_size = QComboBox()
        for key, (w, h) in SIZES.items():
            self.c_size.addItem(f"{w} × {h}", key)
        self.c_size.setCurrentIndex(max(0, self.c_size.findData(cfg["size"])))
        self.c_size.currentIndexChanged.connect(lambda _i: self._cam_set(size=self.c_size.currentData()))
        row.addWidget(self.c_size)
        self.c_fps = QSpinBox()
        self.c_fps.setRange(5, 60)
        self.c_fps.setSuffix(" Bilder/s")
        self.c_fps.setValue(int(cfg["fps"]))
        self.c_fps.valueChanged.connect(lambda v: self._cam_set(fps=v))
        row.addWidget(self.c_fps)
        self.c_mirror = QCheckBox("Spiegeln")
        self.c_mirror.setToolTip("Manche Programme zeigen das eigene Bild gespiegelt – hier ausgleichen")
        self.c_mirror.setChecked(bool(cfg["mirror"]))
        self.c_mirror.toggled.connect(lambda on: self._cam_set(mirror=on))
        row.addWidget(self.c_mirror)
        row.addStretch(1)
        lay.addLayout(row)
        return card

    # ---------------------------------------------------------------- Kamera
    def _cam_set(self, **values) -> None:
        cam = self.controller.vcam
        self.controller.config["vcam"] = {**cam.cfg(), **values}
        if cam.running and ({"size", "fps"} & set(values)):  # neue Größe/Bildrate → neu starten
            cam.stop(remember=False)
            cam.start()
        self._fill_cam()

    def _toggle_cam(self) -> None:
        cam = self.controller.vcam
        ok, _why = cam.status()
        if not ok and not cam.running:
            from .. import drivers

            drivers.install_async(self, "kamera", done=self._fill_cam)
            return
        self.controller.run_command("vcam")
        self._fill_cam()

    def _fill_cam(self) -> None:
        from PySide6.QtGui import QPixmap

        cam = self.controller.vcam
        t = theme.current()
        installed, why = cam.status()
        on = cam.running
        color = t.success if on else t.muted
        self.c_pill.setText("● LIVE" if on else "○ AUS")
        self.c_pill.setStyleSheet(f"color:{color}; background:{t.soft(color, 0.14)}; border-radius:11px;"
                                  "padding:3px 12px; font-weight:700;")
        self.c_toggle.setText("Ausschalten" if on else ("Einschalten" if installed else "Einrichten"))
        self.c_toggle.setIcon(icons.icon("x" if on else ("play" if installed else "download"), t.text, 18))
        name = "„OBS Virtual Camera“" if IS_WINDOWS else "„AluPC Monitor 2“"
        if on:
            text = f"Läuft – in Zoom, Teams, Discord oder OBS die Kamera <b>{name}</b> wählen." + \
                (f" ({cam.device})" if cam.device and not IS_WINDOWS else "")
        else:
            text = (f"Monitor 2 (mit Overlays und Zeichnungen) als Webcam {name}." if installed else why)
        if cam.error:
            text += f"<br><span style='color:{t.danger}'>{cam.error}</span>"
        self.c_text.setText(text)
        if self.isVisible():
            self.c_preview.setPixmap(QPixmap.fromImage(cam.frame_image(224, 126)))

    # ---------------------------------------------------------------- virtuelle Geräte
    def _toggle_virtual(self) -> None:
        st = self._snap.get("virtual") or {}
        if IS_WINDOWS and not (st.get("out") and st.get("mic")):
            from .. import drivers

            drivers.install_async(self, "vbcable", done=self.reload)
            return
        self._route(lambda: self.routing.set_virtual(not self.routing.cfg()["virtual"]))

    def _add_device(self, kind: str) -> None:
        what = "den virtuellen Ausgang" if kind == "out" else "das virtuelle Mikro"
        name, ok = QInputDialog.getText(self, "Neues Gerät", f"Name für {what}:",
                                        text="Discord" if kind == "mic" else "Musik")
        if ok and name.strip():
            self._route(lambda: self.routing.add_device(kind, name))

    def _remove_device(self, dev_id: str) -> None:
        self._route(lambda: self.routing.remove_device(dev_id))

    def _route(self, fn) -> None:
        ok, why = fn()
        self.show_result((ok, why))
        self._signature = None  # Kanäle neu aufbauen (Geräte/Weiterleitungen geändert)
        self.reload()

    def toggle_route(self, src: str, dst: str, on: bool) -> None:
        self.show_result(self.routing.set_route(src, dst, on))

    def show_result(self, result) -> None:
        ok, why = result if isinstance(result, tuple) else (True, "")
        self.v_error.setText("" if ok else why)

    def _fill_virtual(self) -> None:
        st = self._snap.get("virtual") or {}
        cfg = self.routing.cfg()
        t = theme.current()
        on = bool(cfg["virtual"] and st.get("mic"))
        color = t.success if on else t.muted
        self.v_pill.setText("● AN" if on else "○ AUS")
        self.v_pill.setStyleSheet(f"color:{color}; background:{t.soft(color, 0.14)}; border-radius:11px;"
                                  "padding:3px 12px; font-weight:700;")
        missing = IS_WINDOWS and not (st.get("out") and st.get("mic"))
        self.v_toggle.setText("VB-CABLE installieren" if missing else ("Ausschalten" if on else "Einschalten"))
        self.v_toggle.setIcon(icons.icon("download" if missing else ("x" if on else "play"), t.text, 18))
        if IS_WINDOWS:
            self.v_text.setText("Von VB-CABLE: <b>„CABLE Input“</b> = virtueller Ausgang, <b>„CABLE Output“</b> = "
                                "virtuelles Mikro – in Zoom, Teams, Discord oder OBS als Mikrofon wählen." +
                                (f"<br>{st.get('why')}" if missing else ""))
        else:
            self.v_text.setText("Virtuelle Ausgänge (Programme hineinspielen) und virtuelle Mikros (in Zoom, Teams, "
                                "Discord, OBS als Mikrofon wählen). Ton leitet man im Mischpult mit den lila Knöpfen "
                                "weiter.")
        for b in (self.add_out, self.add_mic):
            b.setVisible(not IS_WINDOWS)
            b.setEnabled(on)
        while self.v_list.count():
            w = self.v_list.takeAt(0).widget()
            if w is not None:
                w.deleteLater()
        for d in self.routing.devices() if on else []:
            chip = QToolButton()
            chip.setText(("🔊 " if d["kind"] == "out" else "🎙 ") + d["name"])
            chip.setToolTip(("Virtueller Ausgang" if d["kind"] == "out" else "Virtuelles Mikro") +
                            ("" if d["present"] else " – fehlt gerade") +
                            (" · Klick: entfernen" if d["removable"] else ""))
            chip.setStyleSheet(f"QToolButton {{ background:{t.soft(COLORS['virtual'], 0.16)}; color:{t.text};"
                               f" border-radius:9px; padding:3px 10px;"
                               f" border:1px solid {t.soft(COLORS['virtual'], 0.4)}; }}")
            if d["removable"]:
                chip.clicked.connect(lambda _c=False, dev=d, c=chip: self._chip_menu(dev, c))
            self.v_list.addWidget(chip)
        self.v_list.addStretch(1)
        if self.routing.last_error:
            self.v_error.setText(self.routing.last_error)

    def _chip_menu(self, dev: dict, chip) -> None:
        menu = QMenu(self)
        menu.addAction(icons.icon("trash", theme.current().text, 16), f"„{dev['name']}“ entfernen",
                       lambda: self._remove_device(dev["id"]))
        menu.exec(chip.mapToGlobal(chip.rect().bottomLeft()))

    # ---------------------------------------------------------------- Mischpult
    def reload(self) -> None:
        if self._busy:
            return
        self._busy = True

        def done(snap):
            self._busy = False
            self._snap = snap or {}
            self._fill()

        def failed(_e):
            self._busy = False

        run_async(mixer.snapshot, done, failed, owner=self)

    def _routes_for(self, item_id: str, kind: str, virtual_out: bool) -> list[tuple[str, str, bool]]:
        """Weiterleitungs-Knöpfe eines Kanals: Mikros und virtuelle Ausgänge → jedes virtuelle Mikro (+ Mithören)."""
        cfg = self.routing.cfg()
        if not cfg["virtual"]:
            return []
        devs = self.routing.devices()
        own = next((d for d in devs if d["id"] == item_id), None)
        if kind == "in" and own is not None:
            return []  # ein virtuelles Mikro leitet man nicht weiter
        if kind == "out" and not virtual_out:
            return []
        opts = [(d["id"], "→ " + ("Mikro" if d["id"] == mixer.MIC_NAME else short_name(d["name"])),
                 [item_id, d["id"]] in cfg["routes"])
                for d in devs if d["kind"] == "mic" and d["present"] and
                not (IS_WINDOWS and own is not None and own["sink"] == d["sink"])]
        if virtual_out:
            opts.append((SPEAKER, "🔊 Mithören", [item_id, SPEAKER] in cfg["routes"]))
        return opts

    def _fill(self) -> None:
        snap = self._snap
        ok, why = snap.get("ok", (True, ""))
        self.note.setVisible(not ok)
        self.note.setText(why)
        cfg = self.routing.cfg()
        if cfg["virtual"] and not IS_WINDOWS and not (snap.get("virtual") or {}).get("mic") and \
                not getattr(self, "_reapplied", False):
            self._reapplied = True  # eingeschaltet, aber weg (Audio-Dienst neu gestartet) → neu anlegen
            self.routing.apply()
            QTimer.singleShot(300, self, self.reload)
        outs, ins, apps = snap.get("out", []), snap.get("in", []), snap.get("apps", [])
        vdevs = {d["id"] for d in self.routing.devices() if d["kind"] == "out"} if self.routing.cfg()["virtual"] \
            else set()
        signature = (tuple(d["id"] for d in outs), tuple(d["id"] for d in ins), tuple(a["id"] for a in apps),
                     tuple(map(tuple, self.routing.cfg()["routes"])), tuple(sorted(vdevs)),
                     self.routing.cfg()["virtual"])
        if signature != self._signature:
            self._signature = signature
            self._build(outs, ins, apps, vdevs)
        else:
            for prefix, items in (("out", outs), ("in", ins), ("app", apps)):
                for d in items:
                    strip = self._strips.get(f"{prefix}:{d['id']}")
                    if strip is not None:
                        strip.update_values(d)
        self._fill_virtual()

    def _section(self, title: str, color: str) -> QLabel:
        t = theme.current()
        lab = QLabel("<br>".join(title))  # senkrecht
        lab.setToolTip(title)
        lab.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        lab.setFixedWidth(22)
        lab.setStyleSheet(f"color:{color}; font-weight:800; font-size:10.5px; background:{t.soft(color, 0.10)};"
                          "border-radius:8px; padding-top:10px;")
        return lab

    def _build(self, outs: list[dict], ins: list[dict], apps: list[dict], vdevs: set[str]) -> None:
        while self.desk.count():
            w = self.desk.takeAt(0).widget()
            if w is not None:
                w.deleteLater()
        self._strips = {}
        specs = []
        groups = [("AUSGÄNGE", COLORS["out"], "out", outs, False), ("EINGÄNGE", COLORS["in"], "in", ins, False),
                  ("PROGRAMME", COLORS["app"], "out", apps, True)]
        for title, color, kind, items, stream in groups:
            self.desk.addWidget(self._section(title, color))
            if not items:
                empty = QLabel("Gerade spielt kein\nProgramm Ton ab." if stream else "Keine Geräte")
                empty.setObjectName("Muted")
                empty.setAlignment(Qt.AlignCenter)
                empty.setFixedWidth(STRIP_W + 20)
                self.desk.addWidget(empty)
            for it in items:
                strip = Strip(self, kind, it, stream)
                if stream:
                    strip.set_targets(outs)
                else:
                    strip.set_routes(self._routes_for(it["id"], kind, kind == "out" and it["id"] in vdevs))
                self._strips[strip.key] = strip
                self.desk.addWidget(strip)
                sink = next((o["id"] for o in outs if it.get("device") in (o["id"], o["name"])), "") if stream else ""
                specs.append({"key": strip.key, "kind": kind, "dev": "" if stream else it["id"],
                              "stream": it["id"] if stream else None, "sink": sink})
            self.desk.addSpacing(8)
        self.desk.addStretch(1)
        rows = max([s.routes_box.count() for s in self._strips.values()] + [0])
        for s in self._strips.values():
            s.extra.setFixedHeight(rows * ROW_H)
        if self.isVisible():
            self.meters.set_channels(specs)
            self._meter_timer.start()

    def _read_meters(self) -> None:
        import math

        for key, strip in self._strips.items():
            peak = self.meters.peak(key)
            # dB-Skala wie am Mischpult: −60 dB … 0 dB
            strip.meter.set_level(max(0.0, (20 * math.log10(peak) + 60) / 60) if peak > 0.001 else 0.0)

    def showEvent(self, e):
        super().showEvent(e)
        self._signature = None
        self.reload()
        self._timer.start()
        self._cam_timer.start()
        self._fill_cam()

    def hideEvent(self, e):
        super().hideEvent(e)
        self._timer.stop()
        self._cam_timer.stop()
        self._meter_timer.stop()
        self.meters.stop()
