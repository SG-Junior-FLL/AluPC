"""AluPC-Oberfläche – Vollbild auf Monitor 1 statt des Desktops: große Uhr, Suche („Frag AluPC“), alle Programme
(angeheftete zuerst, auch im Dock), Monitor 2 (Live-Bild + Schalter), AluPC-Aktionen, Lautstärke, offene Fenster.

Aussehen: das AluPC-Hintergrundbild („Aurora“, gleiche Grafik wie fürs System – desktop_theme.paint_wallpaper) in
der Akzentfarbe, darauf Glas-Karten und ein schwebendes Dock. Selbst gezeichnet, darum auf Windows und Linux gleich.

Wie ein eigener Desktop: Ein Programm starten → die Oberfläche geht zur Seite, das Programm ist vorne. Zurück mit
Strg+Alt+O, dem Knopf „Oberfläche“ in AluPC oder dem Symbol im Infobereich. Esc oder „Zum Desktop“ verlässt sie.
Startmenü/Taskleiste des Systems bleiben darunter erhalten (nichts wird ersetzt oder verstellt).
"""

from __future__ import annotations

import sys
import time
import zlib

from PySide6.QtCore import QEasingCurve, QFileInfo, QPropertyAnimation, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QGuiApplication, QIcon, QKeySequence, QLinearGradient, QPainter, QPixmap, \
    QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
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
    QSizePolicy,
    QSlider,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from . import icons, theme
from .util import run_async

IS_WINDOWS = sys.platform.startswith("win")
# Monitor 2 (oben in der Karte, leuchten, wenn an) und AluPC-Aktionen (bunte Knöpfe)
MONITOR = [("spiegeln", "mirror", "Spiegeln"), ("erweitern", "extend", "Erweitern"), ("schwarz", "eye_off", "Schwarz"),
           ("standbild", "snowflake", "Standbild")]
QUICK = [("kamera", "camera", "Kamera", "#0ea5e9"), ("spiele", "gamepad", "Minispiele", "#f97316"),
         ("chat", "chat", "Chat", "#3b82f6"), ("fotowand", "photos", "Foto-Wand", "#ec4899"),
         ("vcam", "webcam", "Virt. Kamera", "#14b8a6"), ("bildschirmschoner", "moon", "Schoner", "#8b5cf6"),
         ("whiteboard", "board", "Tafel", "#22c55e"), ("timer_zeigen", "timer", "Timer", "#eab308")]
TEXT = "#f8fafc"
MUTED = "rgba(226,232,240,0.72)"
GLASS = ("background: rgba(15,18,36,0.46); border: 1px solid rgba(255,255,255,0.13); border-radius: 22px;")
SCROLL_STYLE = ("QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; }"
                "QScrollBar:vertical { background: transparent; width: 8px; }"
                "QScrollBar::handle:vertical { background: rgba(255,255,255,0.25); border-radius: 4px; min-height: 40px; }"
                "QScrollBar::add-line, QScrollBar::sub-line { height: 0; }")


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


def letter_icon(name: str, size: int = 96) -> QIcon:
    """Programm ohne eigenes Symbol: farbiges Quadrat mit Anfangsbuchstaben (Farbe fest je Name)."""
    hue = zlib.crc32(name.encode("utf-8")) % 360
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    g = QLinearGradient(0, 0, size, size)
    g.setColorAt(0, QColor.fromHsv(hue, 150, 250))
    g.setColorAt(1, QColor.fromHsv((hue + 35) % 360, 200, 190))
    p.setPen(Qt.NoPen)
    p.setBrush(g)
    p.drawRoundedRect(QRectF(size * 0.04, size * 0.04, size * 0.92, size * 0.92), size * 0.24, size * 0.24)
    f = QFont()
    f.setPixelSize(int(size * 0.46))
    f.setBold(True)
    p.setFont(f)
    p.setPen(QColor("#ffffff"))
    letter = next((ch for ch in name if ch.isalnum()), "?").upper()
    p.drawText(QRectF(0, 0, size, size * 0.98), int(Qt.AlignCenter), letter)
    p.end()
    return QIcon(pm)


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


def _label(text: str = "", size: float = 14, weight: int = 400, color: str = TEXT) -> QLabel:
    lab = QLabel(text)
    lab.setStyleSheet(f"color:{color}; font-size:{size}px; font-weight:{weight}; background:transparent;")
    return lab


class Glass(QFrame):
    """Halbdurchsichtige Karte auf dem Hintergrundbild."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Glass")
        self.setStyleSheet(f"#Glass {{ {GLASS} }} QLabel {{ background: transparent; }}")


class AppTile(QToolButton):
    def __init__(self, name: str, icon: QIcon, parent=None):
        super().__init__(parent)
        self.app_name = name
        self.setIcon(icon if not icon.isNull() else letter_icon(name))
        self.setIconSize(QSize(52, 52))
        self.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self.setFixedSize(124, 112)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(name)
        self.setStyleSheet("QToolButton { color:#f1f5f9; background:transparent; border-radius:18px; padding:8px 4px;"
                           " font-size:12.5px; } QToolButton:hover { background: rgba(255,255,255,0.13); }"
                           " QToolButton:pressed { background: rgba(255,255,255,0.22); }")

    def setText(self, text: str) -> None:  # noqa: N802 – Qt-Name; zu lange Namen mit „…“
        super().setText(self.fontMetrics().elidedText(text, Qt.ElideRight, 112))


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
        self._bg: tuple[tuple, QPixmap] | None = None
        root = QVBoxLayout(self)
        root.setContentsMargins(44, 26, 44, 22)
        root.setSpacing(18)
        root.addLayout(self._top_bar())
        root.addLayout(self._hero())
        body = QHBoxLayout()
        body.setSpacing(20)
        left = QVBoxLayout()
        left.setSpacing(14)
        left.addWidget(self._apps_panel(), 1)
        windows = self._windows_card()
        windows.setMaximumHeight(190)
        left.addWidget(windows)
        body.addLayout(left, 3)
        side = QWidget()
        side.setStyleSheet("background: transparent;")
        right = QVBoxLayout(side)
        right.setContentsMargins(0, 0, 4, 0)
        right.setSpacing(14)
        right.addWidget(self._monitor_card())
        right.addWidget(self._quick_card())
        right.addWidget(self._sound_card())
        right.addStretch(1)
        side_scroll = QScrollArea()  # kleiner Bildschirm: rechte Spalte scrollt statt sich zu quetschen
        side_scroll.setWidget(side)
        side_scroll.setWidgetResizable(True)
        side_scroll.setFrameShape(QFrame.NoFrame)
        side_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        side_scroll.setStyleSheet(SCROLL_STYLE)
        body.addWidget(side_scroll, 2)
        root.addLayout(body, 1)
        root.addLayout(self._dock_row())
        QShortcut(QKeySequence(Qt.Key_Escape), self, activated=self.leave)
        self._clock = QTimer(self, interval=1000)
        self._clock.timeout.connect(self._tick)
        self._slow = QTimer(self, interval=3000)
        self._slow.timeout.connect(self._refresh_slow)
        self._fade = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade.setDuration(260)
        self._fade.setEasingCurve(QEasingCurve.OutCubic)

    # ---------------------------------------------------------------- Aufbau
    def _top_bar(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(10)
        logo = QLabel()
        logo.setPixmap(icons.icon("monitor", "#ffffff", 22).pixmap(22, 22))
        logo.setFixedSize(40, 40)
        logo.setAlignment(Qt.AlignCenter)
        logo.setStyleSheet("background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #6366f1, stop:1 #ec4899);"
                           " border-radius: 12px;")
        row.addWidget(logo)
        name = QVBoxLayout()
        name.setSpacing(0)
        name.addWidget(_label("AluPC", 16, 800))
        name.addWidget(_label("Oberfläche", 12, 500, MUTED))
        row.addLayout(name)
        row.addStretch(1)
        self.status = QLabel()  # CPU · RAM · Akku · WLAN als Pillen
        self.status.setTextFormat(Qt.RichText)
        self.status.setStyleSheet("color:#e2e8f0; font-size:13px; background: rgba(15,18,36,0.42);"
                                  " border: 1px solid rgba(255,255,255,0.12); border-radius: 15px; padding: 6px 14px;")
        row.addWidget(self.status)
        return row

    def _hero(self) -> QVBoxLayout:
        col = QVBoxLayout()
        col.setSpacing(4)
        self.clock = QLabel()
        self.clock.setAlignment(Qt.AlignCenter)
        col.addWidget(self.clock)
        line = QHBoxLayout()
        line.addStretch(1)
        self.hello = _label("", 20, 650)
        line.addWidget(self.hello)
        line.addWidget(_label("·", 20, 400, MUTED))
        self.date = _label("", 16, 400, MUTED)
        line.addWidget(self.date)
        line.addStretch(1)
        col.addLayout(line)
        col.addSpacing(10)
        holder = QFrame()
        holder.setObjectName("Search")
        holder.setFixedSize(760, 60)
        holder.setStyleSheet("#Search { background: rgba(255,255,255,0.14); border: 1px solid rgba(255,255,255,0.26);"
                             " border-radius: 30px; }")
        h = QHBoxLayout(holder)
        h.setContentsMargins(22, 0, 18, 0)
        h.setSpacing(12)
        glass = QLabel()
        glass.setPixmap(icons.icon("search", "#e0e7ff", 22).pixmap(22, 22))
        glass.setStyleSheet("background:transparent;")
        h.addWidget(glass)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Programm suchen oder AluPC fragen („Timer 5 Minuten“, „Licht blau“) …")
        self.search.setStyleSheet("QLineEdit { background: transparent; color:#fff; border: none; font-size:17px; }")
        self.search.textChanged.connect(self._filter)
        self.search.returnPressed.connect(self._enter)
        h.addWidget(self.search, 1)
        col.addWidget(holder, 0, Qt.AlignHCenter)
        self.answer = _label("", 14.5, 500, "#e0e7ff")
        self.answer.setAlignment(Qt.AlignCenter)
        self.answer.setMinimumHeight(22)
        col.addWidget(self.answer)
        return col

    def _head(self, lay, text: str, icon_name: str) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)
        ic = QLabel()
        ic.setPixmap(icons.icon(icon_name, "#c7d2fe", 18).pixmap(18, 18))
        row.addWidget(ic)
        row.addWidget(_label(text, 15, 700, "#e0e7ff"))
        row.addStretch(1)
        lay.addLayout(row)
        return row

    def _apps_panel(self) -> QWidget:
        panel = Glass()
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(22, 18, 22, 14)
        lay.setSpacing(8)
        head = self._head(lay, "Programme", "apps")
        self.app_count = _label("", 12.5, 500, MUTED)
        head.addWidget(self.app_count)
        self.grid_holder = QWidget()
        self.grid_holder.setStyleSheet("background: transparent;")
        self.grid = QGridLayout(self.grid_holder)
        self.grid.setContentsMargins(0, 4, 0, 4)
        self.grid.setHorizontalSpacing(6)
        self.grid.setVerticalSpacing(6)
        self.grid.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        scroll = QScrollArea()
        scroll.setWidget(self.grid_holder)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet(SCROLL_STYLE)
        self.apps_scroll = scroll
        lay.addWidget(scroll, 1)
        hint = _label("Rechtsklick auf ein Programm: anheften (oben und im Dock)", 12, 400, MUTED)
        lay.addWidget(hint)
        return panel

    def _monitor_card(self) -> QWidget:
        card = Glass()
        lay = QVBoxLayout(card)
        lay.setContentsMargins(18, 14, 18, 16)
        lay.setSpacing(10)
        head = self._head(lay, "Monitor 2", "monitor")
        self.mon_state = QLabel()
        self.mon_state.setStyleSheet("color:#bbf7d0; font-size:12px; font-weight:700; background: rgba(34,197,94,0.18);"
                                     " border-radius: 10px; padding: 3px 10px;")
        head.addWidget(self.mon_state)
        self.preview = QLabel()
        self.preview.setFixedHeight(168)
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setStyleSheet("background: rgba(0,0,0,0.42); border-radius: 14px;")
        lay.addWidget(self.preview)
        row = QHBoxLayout()
        row.setSpacing(8)
        self.mon_buttons: dict[str, QToolButton] = {}
        for cmd, icon_name, label in MONITOR:
            b = QToolButton()
            b.setText(label)
            b.setIcon(icons.icon(icon_name, "#ffffff", 18))
            b.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setMinimumHeight(38)
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            b.setStyleSheet("QToolButton { color:#f1f5f9; background: rgba(255,255,255,0.10); border-radius: 12px;"
                            " padding: 0 10px; font-size: 13px; font-weight: 600; }"
                            " QToolButton:hover { background: rgba(255,255,255,0.20); }"
                            " QToolButton:checked { background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #6366f1,"
                            " stop:1 #8b5cf6); }")
            b.clicked.connect(lambda _c=False, c=cmd: self._run(c))
            self.mon_buttons[cmd] = b
            row.addWidget(b, 1)
        lay.addLayout(row)
        return card

    def _quick_card(self) -> QWidget:
        card = Glass()
        lay = QVBoxLayout(card)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(8)
        self._head(lay, "AluPC", "star")
        grid = QGridLayout()
        grid.setSpacing(6)
        for i, (cmd, icon_name, label, color) in enumerate(QUICK):
            b = QToolButton()
            b.setText(label)
            b.setIcon(icons.icon(icon_name, "#ffffff", 22))
            b.setIconSize(QSize(22, 22))
            b.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
            b.setMinimumSize(78, 66)
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            b.setCursor(Qt.PointingHandCursor)
            c = QColor(color)
            b.setStyleSheet(f"QToolButton {{ color:#ffffff; border-radius: 16px; font-size: 11.5px; font-weight: 600;"
                            f" background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 {c.lighter(115).name()},"
                            f" stop:1 {c.darker(135).name()}); padding: 6px 2px; }}"
                            f" QToolButton:hover {{ background: {c.lighter(130).name()}; }}")
            b.clicked.connect(lambda _c=False, cm=cmd: self._run(cm))
            grid.addWidget(b, i // 4, i % 4)
        lay.addLayout(grid)
        return card

    def _sound_card(self) -> QWidget:
        card = Glass()
        lay = QVBoxLayout(card)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(8)
        head = self._head(lay, "Lautstärke", "sound")
        mixer_btn = QToolButton()
        mixer_btn.setText("Mischpult")
        mixer_btn.setIcon(icons.icon("mixer", "#e0e7ff", 16))
        mixer_btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        mixer_btn.setCursor(Qt.PointingHandCursor)
        mixer_btn.setStyleSheet("QToolButton { color:#e0e7ff; background: rgba(255,255,255,0.10); border-radius:11px;"
                                " padding:5px 12px; font-size: 12.5px; } QToolButton:hover { background:"
                                " rgba(255,255,255,0.2); }")
        mixer_btn.clicked.connect(lambda: self._open_page(6))
        head.addWidget(mixer_btn)
        row = QHBoxLayout()
        self.mute = QToolButton()
        self.mute.setCheckable(True)
        self.mute.setAutoRaise(True)
        self.mute.setIconSize(QSize(22, 22))
        self.mute.setStyleSheet("QToolButton { background: rgba(255,255,255,0.10); border-radius: 12px; padding: 6px; }"
                                " QToolButton:checked { background: rgba(239,68,68,0.35); }")
        self.mute.toggled.connect(self._set_mute)
        row.addWidget(self.mute)
        self.volume = QSlider(Qt.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.setStyleSheet(
            "QSlider::groove:horizontal { height: 8px; border-radius: 4px; background: rgba(255,255,255,0.18); }"
            "QSlider::sub-page:horizontal { border-radius: 4px; background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            " stop:0 #6366f1, stop:1 #ec4899); }"
            "QSlider::handle:horizontal { background: #ffffff; width: 20px; height: 20px; margin: -6px 0;"
            " border-radius: 10px; }")
        self.volume.valueChanged.connect(self._volume_changed)
        row.addWidget(self.volume, 1)
        self.vol_label = _label("", 14, 700)
        self.vol_label.setMinimumWidth(48)
        self.vol_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        row.addWidget(self.vol_label)
        lay.addLayout(row)
        self._vol_send = QTimer(self, singleShot=True, interval=120)
        self._vol_send.timeout.connect(self._apply_volume)
        return card

    def _windows_card(self) -> QWidget:
        card = Glass()
        lay = QVBoxLayout(card)
        lay.setContentsMargins(18, 14, 18, 12)
        lay.setSpacing(6)
        self._head(lay, "Offene Fenster", "window")
        self.windows = QListWidget()
        self.windows.setStyleSheet("QListWidget { background: transparent; border: none; color:#f1f5f9; font-size:13px;"
                                   " outline: none; } QListWidget::item { padding:7px 8px; border-radius:10px; }"
                                   "QListWidget::item:hover { background: rgba(255,255,255,0.12); }"
                                   "QListWidget::item:selected { background: rgba(99,102,241,0.45); }")
        self.windows.itemClicked.connect(self._activate)
        lay.addWidget(self.windows, 1)
        return card

    def _dock_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addStretch(1)
        self.dock = QFrame()
        self.dock.setObjectName("Dock")
        self.dock.setStyleSheet("#Dock { background: rgba(15,18,36,0.55); border: 1px solid rgba(255,255,255,0.18);"
                                " border-radius: 26px; }")
        self.dock_lay = QHBoxLayout(self.dock)
        self.dock_lay.setContentsMargins(12, 8, 12, 8)
        self.dock_lay.setSpacing(8)
        row.addWidget(self.dock)
        row.addStretch(1)
        self.autostart = QCheckBox("Beim Start zeigen")
        self.autostart.setStyleSheet("QCheckBox { color:#cbd5e1; background: transparent; font-size: 12.5px; }")
        self.autostart.setChecked(bool(self.cfg()["autostart"]))
        self.autostart.toggled.connect(lambda on: self.controller.config.__setitem__(
            "shell", {**self.cfg(), "autostart": bool(on)}))
        row.addWidget(self.autostart, 0, Qt.AlignBottom)
        self._build_dock()
        return row

    def _dock_button(self, icon: QIcon, tip: str, fn, accent: bool = False) -> QToolButton:
        b = QToolButton()
        b.setIcon(icon)
        b.setIconSize(QSize(28, 28))
        b.setFixedSize(52, 52)
        b.setToolTip(tip)
        b.setCursor(Qt.PointingHandCursor)
        bg = ("qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #6366f1, stop:1 #ec4899)" if accent
              else "rgba(255,255,255,0.10)")
        b.setStyleSheet(f"QToolButton {{ background: {bg}; border-radius: 16px; }}"
                        " QToolButton:hover { background: rgba(255,255,255,0.26); }")
        b.clicked.connect(fn)
        self.dock_lay.addWidget(b)
        return b

    def _build_dock(self) -> None:
        while self.dock_lay.count():
            w = self.dock_lay.takeAt(0).widget()
            if w is not None:
                w.deleteLater()
        self._dock_button(icons.icon("home", "#ffffff", 28), "AluPC öffnen", self._open_alupc, accent=True)
        for text, icon_name, fn in (("Gäste (Chat, Foto-Wand)", "users", lambda: self._open_page(5)),
                                    ("Audio & Kamera", "mixer", lambda: self._open_page(6)),
                                    ("Einstellungen", "sliders", lambda: self._open_page(2))):
            self._dock_button(icons.icon(icon_name, "#f1f5f9", 26), text, fn)
        pinned = [p for p in self.cfg()["pinned"] if any(n == p for n, _path in self._apps)][:8]
        if pinned:
            self.dock_lay.addWidget(self._dock_sep())
            for name in pinned:
                path = next(path for n, path in self._apps if n == name)
                self._dock_button(self._app_icon(name, path), name, lambda _c=False, n=name: self._launch(n))
        self.dock_lay.addWidget(self._dock_sep())
        self._dock_button(icons.icon("lock", "#f1f5f9", 26), "Sperren", self._lock)
        self.power_button = self._dock_button(icons.icon("power", "#fca5a5", 26), "Energie", self._power_menu)
        self._dock_button(icons.icon("x", "#f1f5f9", 26), "Zum Desktop (Esc)", self.leave)

    @staticmethod
    def _dock_sep() -> QFrame:
        sep = QFrame()
        sep.setFixedSize(1, 34)
        sep.setStyleSheet("background: rgba(255,255,255,0.22);")
        return sep

    # ---------------------------------------------------------------- Zeichnen
    def paintEvent(self, _e):
        from ..desktop_theme import paint_wallpaper

        t = theme.current()
        key = (self.width(), self.height(), t.accent, t.accent2)
        if self._bg is None or self._bg[0] != key:  # einmal je Größe/Farbe malen, dann nur noch kopieren
            pm = QPixmap(max(1, self.width()), max(1, self.height()))
            q = QPainter(pm)
            paint_wallpaper(q, pm.width(), pm.height(), True, colors=(t.accent, t.accent2))
            q.fillRect(pm.rect(), QColor(5, 7, 16, 60))  # etwas dunkler – Schrift bleibt gut lesbar
            q.end()
            self._bg = (key, pm)
        p = QPainter(self)
        p.drawPixmap(0, 0, self._bg[1])

    # ---------------------------------------------------------------- Zeigen / Verlassen
    def show_shell(self) -> None:
        screen = QGuiApplication.primaryScreen()
        out = self.controller.output_screen()
        if screen is out:  # nie auf Monitor 2
            screen = next((s for s in QGuiApplication.screens() if s is not out), screen)
        self.setGeometry(screen.geometry())
        big = screen.geometry().height() >= 1000  # kleiner Bildschirm (z. B. 1366×768): Uhr kleiner
        self.clock.setStyleSheet(f"color:#ffffff; font-size:{88 if big else 60}px; font-weight:200;"
                                 " background:transparent; letter-spacing: 2px;")
        self.preview.setFixedHeight(160 if big else 120)
        self.setWindowOpacity(0.0)
        self.showFullScreen()
        self.raise_()
        self.activateWindow()
        self._fade.stop()
        self._fade.setStartValue(0.0)
        self._fade.setEndValue(1.0)
        self._fade.start()
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
        self.status.setText("  <span style='color:rgba(255,255,255,0.35)'>|</span>  ".join(parts))
        c = self.controller
        self.mon_state.setText((c.describe()[:34] if hasattr(c, "describe") else "") or "bereit")
        flags = {"schwarz": bool(getattr(c, "privacy", False)), "standbild": bool(getattr(c, "frozen", False)),
                 "spiegeln": bool(getattr(c, "mode", "") == "content" and (getattr(c, "content", None) or {})
                                  .get("mirror")),
                 "erweitern": bool(getattr(c, "mode", "") == "desktop"
                                   and str(getattr(c, "desktop_note", "")).startswith("Erweitert"))}
        for cmd, b in self.mon_buttons.items():
            b.setChecked(flags.get(cmd, False))
        try:
            pm = QPixmap()
            pm.loadFromData(c._preview_jpeg())
            self.preview.setPixmap(pm.scaled(self.preview.width() - 10, self.preview.height() - 10, Qt.KeepAspectRatio,
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

        run_async(pc_control.get_volume, got_volume, owner=self)
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
            self._build_dock()

        run_async(pc_control.installed_apps, done, owner=self)

    def _app_icon(self, name: str, path: str) -> QIcon:
        icon = self._icons.get(path)
        if icon is None:
            icon = app_icon_for(path)
            if icon.isNull() or not icon.availableSizes() and icon.pixmap(48, 48).isNull():
                icon = letter_icon(name)
            self._icons[path] = icon
        return icon

    def _build_tiles(self) -> None:
        for tile in self._tiles:
            tile.deleteLater()
        self._tiles = []
        pinned = self.cfg()["pinned"]
        order = sorted(self._apps, key=lambda a: (a[0] not in pinned, pinned.index(a[0]) if a[0] in pinned else 0,
                                                  a[0].lower()))
        for name, path in order[:400]:
            tile = AppTile(name, self._app_icon(name, path))
            tile.setText(("★ " if name in pinned else "") + name)
            tile.clicked.connect(lambda _c=False, n=name: self._launch(n))
            tile.setContextMenuPolicy(Qt.CustomContextMenu)
            tile.customContextMenuRequested.connect(lambda _p, n=name, tl=tile: self._tile_menu(n, tl))
            self._tiles.append(tile)
        self.app_count.setText(f"{len(self._apps)} Programme" if self._apps else "")
        self._relayout()

    def _relayout(self) -> None:
        cols = max(3, (self.apps_scroll.viewport().width() - 10) // 130)
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
            QTimer.singleShot(0, self, self._relayout)

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
            menu.addAction("Lösen (nicht mehr oben/im Dock)", lambda: self._pin(name, False))
        else:
            menu.addAction("Anheften (oben und im Dock)", lambda: self._pin(name, True))
        menu.exec(tile.mapToGlobal(tile.rect().bottomLeft()))

    def _pin(self, name: str, on: bool) -> None:
        pinned = [p for p in self.cfg()["pinned"] if p != name] + ([name] if on else [])
        self.controller.config["shell"] = {**self.cfg(), "pinned": pinned}
        self._build_tiles()
        self._build_dock()

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
