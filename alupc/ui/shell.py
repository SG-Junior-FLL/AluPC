"""AluPC-Oberfläche – Vollbild auf Monitor 1 statt des Desktops: Uhr, Suche („Frag AluPC“), alle Programme
(angeheftete zuerst), offene Fenster, Lautstärke, Monitor 2 (Live-Bild + Schalter), Gäste, Energie.

Wie ein eigener Desktop: Ein Programm starten → die Oberfläche geht zur Seite, das Programm ist vorne. Zurück mit
Strg+Alt+O, dem Knopf „Oberfläche“ in AluPC oder dem Symbol im Infobereich. Esc oder „Zum Desktop“ verlässt sie.
Startmenü/Taskleiste des Systems bleiben darunter erhalten (nichts wird ersetzt oder verstellt).
"""

from __future__ import annotations

import sys
import time

from PySide6.QtCore import QFileInfo, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QGuiApplication, QIcon, QKeySequence, QLinearGradient, QPainter, QPixmap, \
    QRadialGradient, QShortcut
from PySide6.QtWidgets import (
    QFileIconProvider,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QScrollArea,
    QSlider,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from . import icons, theme
from .util import run_async

IS_WINDOWS = sys.platform.startswith("win")
QUICK = [("spiegeln", "mirror", "Spiegeln"), ("erweitern", "extend", "Erweitern"), ("schwarz", "eye_off", "Schwarz"),
         ("standbild", "snowflake", "Standbild"), ("kamera", "camera", "Kamera"), ("spiele", "gamepad", "Minispiele"),
         ("chat", "chat", "Chat"), ("fotowand", "photos", "Foto-Wand"), ("vcam", "webcam", "Virt. Kamera"),
         ("bildschirmschoner", "moon", "Schoner")]


def greeting(hour: int) -> str:
    return "Gute Nacht" if hour < 5 else "Guten Morgen" if hour < 11 else "Hallo" if hour < 17 else "Guten Abend"


def app_icon_for(path: str) -> QIcon:
    """Symbol eines installierten Programms (Windows: Verknüpfung, Linux: Icon= der .desktop-Datei)."""
    if IS_WINDOWS:
        return QFileIconProvider().icon(QFileInfo(path))
    try:
        text = open(path, encoding="utf-8", errors="replace").read()  # noqa: SIM115
    except OSError:
        return QIcon()
    name = next((ln.split("=", 1)[1].strip() for ln in text.splitlines() if ln.startswith("Icon=")), "")
    if not name:
        return QIcon()
    if name.startswith("/"):
        return QIcon(name)
    return QIcon.fromTheme(name)


def activate_window(win_id: str) -> bool:
    """Offenes Fenster nach vorne holen (Windows: Fenster-Handle, Linux/X11: wmctrl)."""
    try:
        if IS_WINDOWS:
            import ctypes

            hwnd = int(win_id)
            user32 = ctypes.windll.user32
            if user32.IsIconic(hwnd):
                user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            return bool(user32.SetForegroundWindow(hwnd))
        import shutil
        import subprocess

        if shutil.which("wmctrl"):
            return subprocess.run(["wmctrl", "-i", "-a", win_id], timeout=5).returncode == 0
    except (OSError, ValueError):
        pass
    return False


class Glass(QFrame):
    """Halbdurchsichtige Karte auf dem Hintergrund."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Glass")
        self.setStyleSheet("#Glass { background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.12);"
                           " border-radius: 18px; } QLabel { color: #f1f5f9; background: transparent; }")


class AppTile(QToolButton):
    def __init__(self, name: str, icon: QIcon, parent=None):
        super().__init__(parent)
        self.app_name = name
        self.setText(name)
        self.setIcon(icon if not icon.isNull() else icons.icon("window", "#e2e8f0", 40))
        self.setIconSize(QSize(44, 44))
        self.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self.setFixedSize(112, 100)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(name)
        self.setStyleSheet("QToolButton { color:#f1f5f9; background:transparent; border-radius:14px; padding:6px;"
                           " font-size:12px; } QToolButton:hover { background: rgba(255,255,255,0.14); }")


class ShellWindow(QWidget):
    TITLE = "AluPC – Oberfläche"

    def __init__(self, main_window, controller):
        super().__init__(None, Qt.Window | Qt.FramelessWindowHint)
        self.main_window, self.controller = main_window, controller
        self.setWindowTitle(self.TITLE)
        self.setAttribute(Qt.WA_StyledBackground, False)
        self._apps: list[tuple[str, str]] = []
        self._icons: dict[str, QIcon] = {}
        self._tiles: list[AppTile] = []
        root = QVBoxLayout(self)
        root.setContentsMargins(48, 32, 48, 28)
        root.setSpacing(22)
        root.addLayout(self._top_bar())
        self.search = QLineEdit()
        self.search.setPlaceholderText("Programm suchen oder AluPC fragen („Timer 5 Minuten“, „Licht blau“) …")
        self.search.setMinimumHeight(52)
        self.search.setMinimumWidth(620)
        self.search.setMaximumWidth(820)
        self.search.setStyleSheet("QLineEdit { background: rgba(255,255,255,0.12); color:#fff; border:1px solid "
                                  "rgba(255,255,255,0.2); border-radius:26px; padding:0 24px; font-size:17px; }"
                                  "QLineEdit:focus { border-color: rgba(255,255,255,0.55); }")
        self.search.textChanged.connect(self._filter)
        self.search.returnPressed.connect(self._enter)
        root.addWidget(self.search, 0, Qt.AlignHCenter)
        self.answer = QLabel()
        self.answer.setStyleSheet("color:#e0e7ff; font-size:14px;")
        self.answer.setAlignment(Qt.AlignCenter)
        root.addWidget(self.answer)
        body = QHBoxLayout()
        body.setSpacing(22)
        body.addWidget(self._apps_panel(), 3)
        right = QVBoxLayout()
        right.setSpacing(16)
        right.addWidget(self._monitor_card())
        right.addWidget(self._sound_card())
        right.addWidget(self._windows_card(), 1)
        body.addLayout(right, 2)
        root.addLayout(body, 1)
        root.addLayout(self._dock())
        QShortcut(QKeySequence(Qt.Key_Escape), self, activated=self.leave)
        self._clock = QTimer(self, interval=1000)
        self._clock.timeout.connect(self._tick)
        self._slow = QTimer(self, interval=3000)
        self._slow.timeout.connect(self._refresh_slow)

    # ---------------------------------------------------------------- Aufbau
    def _top_bar(self) -> QHBoxLayout:
        row = QHBoxLayout()
        left = QVBoxLayout()
        self.hello = QLabel()
        self.hello.setStyleSheet("color:#f8fafc; font-size:26px; font-weight:700;")
        self.date = QLabel()
        self.date.setStyleSheet("color:#cbd5e1; font-size:15px;")
        left.addWidget(self.hello)
        left.addWidget(self.date)
        row.addLayout(left)
        row.addStretch(1)
        self.clock = QLabel()
        self.clock.setStyleSheet("color:#ffffff; font-size:64px; font-weight:300;")
        row.addWidget(self.clock)
        row.addStretch(1)
        self.status = QLabel()
        self.status.setStyleSheet("color:#e2e8f0; font-size:13.5px;")
        self.status.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        row.addWidget(self.status)
        return row

    def _apps_panel(self) -> QWidget:
        panel = Glass()
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(10)
        head = QLabel("AluPC")
        head.setStyleSheet("font-size:15px; font-weight:700; color:#c7d2fe;")
        lay.addWidget(head)
        self.quick = QHBoxLayout()
        self.quick.setSpacing(6)
        for cmd, icon_name, label in QUICK:
            b = QToolButton()
            b.setText(label)
            b.setIcon(icons.icon(icon_name, "#e0e7ff", 26))
            b.setIconSize(QSize(26, 26))
            b.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
            b.setFixedSize(84, 70)
            b.setStyleSheet("QToolButton { color:#e0e7ff; background: rgba(99,102,241,0.25); border-radius:14px;"
                            " font-size:11.5px; } QToolButton:hover { background: rgba(99,102,241,0.45); }")
            b.clicked.connect(lambda _c=False, c=cmd: self._run(c))
            self.quick.addWidget(b)
        self.quick.addStretch(1)
        quick_holder = QWidget()
        quick_holder.setLayout(self.quick)
        qs = QScrollArea()
        qs.setWidget(quick_holder)
        qs.setWidgetResizable(True)
        qs.setFixedHeight(88)
        qs.setFrameShape(QFrame.NoFrame)
        qs.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        qs.setStyleSheet("QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; }")
        lay.addWidget(qs)
        head2 = QLabel("Programme")
        head2.setStyleSheet("font-size:15px; font-weight:700; color:#c7d2fe;")
        lay.addWidget(head2)
        self.grid_holder = QWidget()
        self.grid = QGridLayout(self.grid_holder)
        self.grid.setSpacing(6)
        self.grid.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        scroll = QScrollArea()
        scroll.setWidget(self.grid_holder)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; }")
        self.apps_scroll = scroll
        lay.addWidget(scroll, 1)
        return panel

    def _monitor_card(self) -> QWidget:
        card = Glass()
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 14, 16, 14)
        head = QHBoxLayout()
        t = QLabel("Monitor 2")
        t.setStyleSheet("font-size:15px; font-weight:700; color:#c7d2fe;")
        head.addWidget(t)
        head.addStretch(1)
        self.mon_state = QLabel()
        self.mon_state.setStyleSheet("color:#cbd5e1;")
        head.addWidget(self.mon_state)
        lay.addLayout(head)
        self.preview = QLabel()
        self.preview.setFixedHeight(170)
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setStyleSheet("background: rgba(0,0,0,0.35); border-radius: 12px;")
        lay.addWidget(self.preview)
        return card

    def _sound_card(self) -> QWidget:
        card = Glass()
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 14, 16, 14)
        head = QHBoxLayout()
        t = QLabel("Lautstärke")
        t.setStyleSheet("font-size:15px; font-weight:700; color:#c7d2fe;")
        head.addWidget(t)
        head.addStretch(1)
        mixer_btn = QToolButton()
        mixer_btn.setText("Mischpult")
        mixer_btn.setIcon(icons.icon("mixer", "#e0e7ff", 18))
        mixer_btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        mixer_btn.setStyleSheet("QToolButton { color:#e0e7ff; background: rgba(255,255,255,0.1); border-radius:10px;"
                                " padding:4px 10px; }")
        mixer_btn.clicked.connect(lambda: self._open_page(6))
        head.addWidget(mixer_btn)
        lay.addLayout(head)
        row = QHBoxLayout()
        self.mute = QToolButton()
        self.mute.setCheckable(True)
        self.mute.setAutoRaise(True)
        self.mute.setIconSize(QSize(22, 22))
        self.mute.toggled.connect(self._set_mute)
        row.addWidget(self.mute)
        self.volume = QSlider(Qt.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.valueChanged.connect(self._volume_changed)
        row.addWidget(self.volume, 1)
        self.vol_label = QLabel()
        self.vol_label.setMinimumWidth(44)
        row.addWidget(self.vol_label)
        lay.addLayout(row)
        self._vol_send = QTimer(self, singleShot=True, interval=120)
        self._vol_send.timeout.connect(self._apply_volume)
        return card

    def _windows_card(self) -> QWidget:
        card = Glass()
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 14, 16, 14)
        t = QLabel("Offene Fenster")
        t.setStyleSheet("font-size:15px; font-weight:700; color:#c7d2fe;")
        lay.addWidget(t)
        self.windows = QListWidget()
        self.windows.setStyleSheet("QListWidget { background: transparent; border: none; color:#f1f5f9; font-size:13px; }"
                                   "QListWidget::item { padding:6px; border-radius:8px; }"
                                   "QListWidget::item:hover { background: rgba(255,255,255,0.12); }")
        self.windows.itemClicked.connect(self._activate)
        lay.addWidget(self.windows, 1)
        return card

    def _dock(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addStretch(1)
        style = ("QToolButton { color:#f1f5f9; background: rgba(255,255,255,0.12); border-radius:16px;"
                 " padding:8px 16px; font-size:13px; } QToolButton:hover { background: rgba(255,255,255,0.24); }")
        for text, icon_name, fn in (("AluPC", "home", self._open_alupc), ("Gäste", "users", lambda: self._open_page(5)),
                                    ("Einstellungen", "sliders", lambda: self._open_page(2)),
                                    ("Sperren", "lock", self._lock), ("Energie", "power", self._power_menu),
                                    ("Zum Desktop", "x", self.leave)):
            b = QToolButton()
            b.setText(text)
            b.setIcon(icons.icon(icon_name, "#f1f5f9", 18))
            b.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            b.setStyleSheet(style)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(fn)
            if text == "Energie":
                self.power_button = b
            row.addWidget(b)
        row.addStretch(1)
        from PySide6.QtWidgets import QCheckBox

        self.autostart = QCheckBox("Beim Start von AluPC zeigen")
        self.autostart.setStyleSheet("QCheckBox { color:#cbd5e1; }")
        self.autostart.setChecked(bool(self.cfg()["autostart"]))
        self.autostart.toggled.connect(lambda on: self.controller.config.__setitem__(
            "shell", {**self.cfg(), "autostart": bool(on)}))
        row.addWidget(self.autostart)
        return row

    # ---------------------------------------------------------------- Zeichnen
    def paintEvent(self, _e):
        t = theme.current()
        p = QPainter(self)
        r = QRectF(self.rect())
        grad = QLinearGradient(r.topLeft(), r.bottomRight())
        base = QColor(t.accent)
        grad.setColorAt(0, QColor("#0b1020"))
        grad.setColorAt(0.55, QColor(base).darker(260))
        grad.setColorAt(1, QColor(t.accent2 if hasattr(t, "accent2") else t.accent).darker(200))
        p.fillRect(r, grad)
        glow = QRadialGradient(r.width() * 0.8, r.height() * 0.15, r.width() * 0.5)
        c = QColor(base)
        c.setAlpha(70)
        glow.setColorAt(0, c)
        c.setAlpha(0)
        glow.setColorAt(1, c)
        p.fillRect(r, glow)

    # ---------------------------------------------------------------- Zeigen / Verlassen
    def show_shell(self) -> None:
        screen = QGuiApplication.primaryScreen()
        out = self.controller.output_screen()
        if screen is out:  # nie auf Monitor 2
            screen = next((s for s in QGuiApplication.screens() if s is not out), screen)
        self.setGeometry(screen.geometry())
        self.showFullScreen()
        self.raise_()
        self.activateWindow()
        self.search.setFocus()
        self._tick()
        self._refresh_slow()
        self._load_apps()
        self._clock.start()
        self._slow.start()
        self.controller.config["shell"] = {**self.cfg(), "open": True}

    def cfg(self) -> dict:
        return {"autostart": False, "pinned": [], **(self.controller.config.data.get("shell") or {})}

    def leave(self) -> None:
        self._clock.stop()
        self._slow.stop()
        self.hide()
        self.controller.config["shell"] = {**self.cfg(), "open": False}

    def step_aside(self) -> None:
        """Programm wurde gestartet/vorgeholt: Oberfläche weg, das Programm ist vorne."""
        self._clock.stop()
        self._slow.stop()
        self.hide()

    # ---------------------------------------------------------------- Inhalte
    def _tick(self) -> None:
        from ..sources import format_date_de

        now = time.localtime()
        self.clock.setText(time.strftime("%H:%M", now))
        self.date.setText(format_date_de(now))
        self.hello.setText(greeting(now.tm_hour))

    def _refresh_slow(self) -> None:
        import psutil

        parts = [f"CPU {psutil.cpu_percent():.0f} %", f"RAM {psutil.virtual_memory().percent:.0f} %"]
        try:
            bat = psutil.sensors_battery()
        except (AttributeError, OSError, NotImplementedError):
            bat = None
        if bat is not None:
            parts.append(f"Akku {bat.percent:.0f} %" + (" ⚡" if bat.power_plugged else ""))
        from ..hotspot import hotspot

        if hotspot.running:
            parts.append(f"WLAN „{hotspot.ssid}“")
        self.status.setText("   ·   ".join(parts))
        c = self.controller
        self.mon_state.setText(c.describe()[:40] if hasattr(c, "describe") else "")
        try:
            pm = QPixmap()
            pm.loadFromData(c._preview_jpeg())
            self.preview.setPixmap(pm.scaled(self.preview.width() - 8, self.preview.height() - 8, Qt.KeepAspectRatio,
                                             Qt.SmoothTransformation))
        except Exception:  # noqa: BLE001 – Vorschau ist nur Zierde
            pass
        from .. import pc_control

        def got_volume(v):
            if v is not None and not self.volume.isSliderDown():
                self.volume.blockSignals(True)
                self.volume.setValue(int(v))
                self.volume.blockSignals(False)
                self.vol_label.setText(f"{int(v)} %")
            self._mute_icon()

        run_async(pc_control.get_volume, got_volume)
        self._fill_windows()

    def _fill_windows(self) -> None:
        from ..sources import window_backend

        backend = window_backend()
        self.windows.clear()
        if not getattr(backend, "can_list", False):
            item = QListWidgetItem("Fensterliste gibt es hier nicht (Wayland) – Alt+Tab wechselt Fenster.")
            item.setFlags(Qt.NoItemFlags)
            self.windows.addItem(item)
            return
        try:
            wins = backend.list_windows()
        except Exception:  # noqa: BLE001
            wins = []
        for w in wins:
            if w.title.startswith("AluPC"):
                continue
            item = QListWidgetItem(icons.icon("window", "#e2e8f0", 16), (w.title[:70] + ("  (minimiert)"
                                                                                       if w.minimized else "")))
            item.setData(Qt.UserRole, w.id)
            self.windows.addItem(item)
        if not self.windows.count():
            item = QListWidgetItem("Keine offenen Fenster")
            item.setFlags(Qt.NoItemFlags)
            self.windows.addItem(item)

    def _load_apps(self) -> None:
        if self._apps:
            return
        from .. import pc_control

        def done(apps):
            self._apps = apps or []
            self._build_tiles()

        run_async(pc_control.installed_apps, done)

    def _build_tiles(self) -> None:
        for tile in self._tiles:
            tile.deleteLater()
        self._tiles = []
        pinned = self.cfg()["pinned"]
        order = sorted(self._apps, key=lambda a: (a[0] not in pinned, pinned.index(a[0]) if a[0] in pinned else 0,
                                                  a[0].lower()))
        for name, path in order[:400]:
            icon = self._icons.get(path)
            if icon is None:
                icon = self._icons[path] = app_icon_for(path)
            tile = AppTile(("★ " if name in pinned else "") + name, icon)
            tile.app_name = name
            tile.clicked.connect(lambda _c=False, n=name: self._launch(n))
            tile.setContextMenuPolicy(Qt.CustomContextMenu)
            tile.customContextMenuRequested.connect(lambda _p, n=name, tl=tile: self._tile_menu(n, tl))
            self._tiles.append(tile)
        self._relayout()

    def _relayout(self) -> None:
        cols = max(3, (self.apps_scroll.viewport().width() - 10) // 118)
        for tl in self._tiles:
            self.grid.removeWidget(tl)
        i = 0
        for tl in self._tiles:
            if tl.property("hide"):
                tl.hide()
                continue
            tl.show()
            self.grid.addWidget(tl, i // cols, i % cols)
            i += 1

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self._tiles:
            QTimer.singleShot(0, self._relayout)

    def _filter(self, text: str) -> None:
        needle = text.strip().lower()
        for tl in self._tiles:
            tl.setProperty("hide", bool(needle) and needle not in tl.app_name.lower())
        self.answer.setText("")
        self._relayout()

    def _enter(self) -> None:
        text = self.search.text().strip()
        if not text:
            return
        hits = [tl for tl in self._tiles if not tl.property("hide")]
        if hits and text.lower() in hits[0].app_name.lower():
            self._launch(hits[0].app_name)
            return
        result = self.controller.ask(text, source="pc")  # „Timer 5 Minuten“, „Licht blau“, „Spiegeln“ …
        self.answer.setText(result.get("reply") or result.get("label") or "Nicht verstanden.")

    def _tile_menu(self, name: str, tile) -> None:
        pinned = list(self.cfg()["pinned"])
        menu = QMenu(self)
        if name in pinned:
            menu.addAction("Lösen (nicht mehr oben)", lambda: self._pin(name, False))
        else:
            menu.addAction("Anheften (oben zeigen)", lambda: self._pin(name, True))
        menu.exec(tile.mapToGlobal(tile.rect().bottomLeft()))

    def _pin(self, name: str, on: bool) -> None:
        pinned = [p for p in self.cfg()["pinned"] if p != name] + ([name] if on else [])
        self.controller.config["shell"] = {**self.cfg(), "pinned": pinned}
        self._build_tiles()

    # ---------------------------------------------------------------- Aktionen
    def _launch(self, name: str) -> None:
        from .. import pc_control

        ok, why = pc_control.launch_installed(name)
        if ok:
            self.step_aside()
        else:
            self.answer.setText(f"„{name}“: {why}")

    def _activate(self, item) -> None:
        win_id = item.data(Qt.UserRole)
        if win_id and activate_window(str(win_id)):
            self.step_aside()

    def _run(self, cmd: str) -> None:
        self.controller.run_command(cmd)
        self._refresh_slow()

    def _open_alupc(self) -> None:
        self.step_aside()
        self.main_window.show_normal_front()

    def _open_page(self, index: int) -> None:
        self._open_alupc()
        self.main_window._go(index)

    def _lock(self) -> None:
        self.controller.lock_computer()

    def _power_menu(self) -> None:
        from .. import pc_control

        menu = QMenu(self)
        for label, cmd in (("Energie sparen", "pc_schlafen"), ("Abmelden", "pc_abmelden"),
                           ("Neu starten", "pc_neustart"), ("Herunterfahren", "pc_herunterfahren")):
            def go(c=cmd, lab=label):
                if c != "pc_schlafen" and QMessageBox.question(self, "AluPC", f"Wirklich {lab.lower()}?") \
                        != QMessageBox.Yes:
                    return
                pc_control.power(c)

            menu.addAction(label, go)
        menu.exec(self.power_button.mapToGlobal(self.power_button.rect().topLeft()))

    def _volume_changed(self, v: int) -> None:
        self.vol_label.setText(f"{v} %")
        self._vol_send.start()

    def _apply_volume(self) -> None:
        from .. import pc_control

        v = self.volume.value()
        run_async(lambda: pc_control.set_volume(v))

    def _set_mute(self, on: bool) -> None:
        from .. import pc_control

        self._mute_icon()
        run_async(lambda: pc_control.set_mute(on))

    def _mute_icon(self) -> None:
        on = self.mute.isChecked()
        self.mute.setIcon(icons.icon("mute" if on else "sound", "#fca5a5" if on else "#f1f5f9", 22))

