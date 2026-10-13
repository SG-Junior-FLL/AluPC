"""AluPC-Oberfläche – ein eigener Desktop im Vollbild auf Monitor 1:

* Hintergrund: das AluPC-Hintergrundbild („Aurora“ in der Akzentfarbe) oder ein eigenes Bild.
* Desktop: Symbole aus dem Desktop-Ordner (Dateien, Ordner, Verknüpfungen – mit echten Logos), frei verschiebbar,
  neue Dateien erscheinen von selbst; dazu Widgets (Uhr, Monitor 2, AluPC-Aktionen), ebenfalls frei verschiebbar.
* Eigene Taskleiste: Start (Startmenü mit Suche, „Frag AluPC“ und allen Programmen), angeheftete Programme, offene
  Fenster; rechts Monitor 2, WLAN, Lautstärke, Akku, Uhr und „Anpassen“.
* Anpassen (Knopf rechts in der Taskleiste oder Rechtsklick auf den Desktop): Hintergrund, Symbolgröße, Raster,
  Taskleiste mittig/links, Uhr mit Sekunden, Widgets, Start mit AluPC, Esc schließt.

Ein Programm starten → die Oberfläche geht zur Seite, das Programm ist vorne. Zurück mit Strg+Alt+O (oder Knopf
„Oberfläche“ in AluPC / Infobereich). Selbst gezeichnet, darum auf Windows und Linux gleich.
"""

from __future__ import annotations

import sys
import time

from PySide6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QGuiApplication, QIcon, QKeySequence, QPainter, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
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
from .shell_desktop import DesktopArea, Movable, app_icon_for, icon_index, icon_index_ready, letter_icon, usable
from .util import run_async

IS_WINDOWS = sys.platform.startswith("win")
MONITOR = [("spiegeln", "mirror", "Spiegeln"), ("erweitern", "extend", "Erweitern"), ("schwarz", "eye_off", "Schwarz"),
           ("standbild", "snowflake", "Standbild")]
QUICK = [("kamera", "camera", "Kamera", "#0ea5e9"), ("spiele", "gamepad", "Minispiele", "#f97316"),
         ("chat", "chat", "Chat", "#3b82f6"), ("fotowand", "photos", "Foto-Wand", "#ec4899"),
         ("vcam", "webcam", "Virt. Kamera", "#14b8a6"), ("bildschirmschoner", "moon", "Schoner", "#8b5cf6"),
         ("whiteboard", "board", "Tafel", "#22c55e"), ("timer_zeigen", "timer", "Timer", "#eab308")]
DEFAULTS = {"autostart": False, "pinned": [], "open": False, "wallpaper": "", "desktop_icons": True,
            "icon_size": 56, "snap": True, "pos": {}, "taskbar_center": True, "clock_seconds": False,
            "widgets": {"clock": True, "monitor": True, "quick": True}, "esc_closes": False}
MUTED = "rgba(226,232,240,0.72)"
GLASS = "background: rgba(14,17,34,0.55); border: 1px solid rgba(255,255,255,0.14); border-radius: 22px;"
SCROLL_STYLE = ("QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; }"
                "QScrollBar:vertical { background: transparent; width: 8px; }"
                "QScrollBar::handle:vertical { background: rgba(255,255,255,0.25); border-radius: 4px; min-height: 40px; }"
                "QScrollBar::add-line, QScrollBar::sub-line { height: 0; }")


def greeting(hour: int) -> str:
    return "Gute Nacht" if hour < 5 else "Guten Morgen" if hour < 11 else "Hallo" if hour < 17 else "Guten Abend"


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

        from ..platform.linux_display import is_wayland

        if is_wayland():  # wmctrl geht dort nicht – KWin holt das Fenster nach vorne
            from ..platform.linux_windows import kwin_activate

            return kwin_activate(win_id)
        if shutil.which("wmctrl"):
            return subprocess.run(["wmctrl", "-i", "-a", win_id], timeout=5).returncode == 0
    except (OSError, ValueError):
        pass
    return False


def _label(text: str = "", size: float = 14, weight: int = 400, color: str = "#f8fafc") -> QLabel:
    lab = QLabel(text)
    lab.setStyleSheet(f"color:{color}; font-size:{size}px; font-weight:{weight}; background:transparent; border:none;")
    return lab


def _round_button(icon: QIcon, tip: str, size: int = 44, icon_px: int = 26, bg: str = "transparent") -> QToolButton:
    b = QToolButton()
    b.setIcon(icon)
    b.setIconSize(QSize(icon_px, icon_px))
    b.setFixedSize(size, size)
    b.setToolTip(tip)
    b.setCursor(Qt.PointingHandCursor)
    b.setStyleSheet(f"QToolButton {{ background: {bg}; border: none; border-radius: {size // 3}px; }}"
                    " QToolButton:hover { background: rgba(255,255,255,0.16); }"
                    " QToolButton:pressed { background: rgba(255,255,255,0.26); }")
    return b


# --------------------------------------------------------------------------- Widgets (frei verschiebbar)
class DeskWidget(Movable, QFrame):
    moved = Signal(str, QPoint)

    def __init__(self, key: str, title: str = "", icon_name: str = "", width: int = 340):
        super().__init__()
        self._init_move(key)
        self.setObjectName("DeskWidget")
        self.setStyleSheet(f"#DeskWidget {{ {GLASS} }}")
        self.setFixedWidth(width)
        self.setCursor(Qt.OpenHandCursor)
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(18, 14, 18, 16)
        self.lay.setSpacing(10)
        if title:
            row = QHBoxLayout()
            ic = QLabel()
            ic.setPixmap(icons.icon(icon_name, "#c7d2fe", 18).pixmap(18, 18))
            ic.setStyleSheet("background:transparent; border:none;")
            row.addWidget(ic)
            row.addWidget(_label(title, 15, 700, "#e0e7ff"))
            row.addStretch(1)
            self.head = row
            self.lay.addLayout(row)

    def mousePressEvent(self, e):
        self._press(e)

    def mouseMoveEvent(self, e):
        self._drag(e)

    def mouseReleaseEvent(self, _e):
        self._release()


class ClockWidget(DeskWidget):
    def __init__(self):
        super().__init__("widget:clock", width=340)
        self.lay.setSpacing(2)
        self.time = _label("", 64, 200, "#ffffff")
        self.lay.addWidget(self.time)
        self.date = _label("", 15, 600)
        self.lay.addWidget(self.date)
        self.status = _label("", 12.5, 500, MUTED)
        self.lay.addWidget(self.status)


class MonitorWidget(DeskWidget):
    def __init__(self, run):
        super().__init__("widget:monitor", "Monitor 2", "monitor", 340)
        self.state = QLabel()
        self.state.setStyleSheet("color:#bbf7d0; font-size:12px; font-weight:700; background: rgba(34,197,94,0.18);"
                                 " border:none; border-radius: 10px; padding: 3px 10px;")
        self.head.addWidget(self.state)
        self.preview = QLabel()
        self.preview.setFixedSize(304, 171)
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setStyleSheet("background: rgba(0,0,0,0.45); border:none; border-radius: 14px;")
        self.lay.addWidget(self.preview)
        grid = QGridLayout()
        grid.setSpacing(8)
        self.buttons: dict[str, QToolButton] = {}
        for i, (cmd, icon_name, label) in enumerate(MONITOR):
            b = QToolButton()
            b.setText(label)
            b.setIcon(icons.icon(icon_name, "#ffffff", 18))
            b.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setMinimumHeight(38)
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            b.setStyleSheet("QToolButton { color:#f1f5f9; background: rgba(255,255,255,0.10); border:none;"
                            " border-radius: 12px; padding: 0 10px; font-size: 13px; font-weight: 600; }"
                            " QToolButton:hover { background: rgba(255,255,255,0.2); }"
                            " QToolButton:checked { background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #6366f1,"
                            " stop:1 #8b5cf6); }")
            b.clicked.connect(lambda _c=False, c=cmd: run(c))
            self.buttons[cmd] = b
            grid.addWidget(b, i // 2, i % 2)
        self.lay.addLayout(grid)


class QuickWidget(DeskWidget):
    def __init__(self, run):
        super().__init__("widget:quick", "AluPC", "star", 340)
        grid = QGridLayout()
        grid.setSpacing(6)
        for i, (cmd, icon_name, label, color) in enumerate(QUICK):
            b = QToolButton()
            b.setText(label)
            b.setIcon(icons.icon(icon_name, "#ffffff", 22))
            b.setIconSize(QSize(22, 22))
            b.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
            b.setMinimumSize(70, 64)
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            b.setCursor(Qt.PointingHandCursor)
            c = QColor(color)
            b.setStyleSheet(f"QToolButton {{ color:#ffffff; border:none; border-radius: 16px; font-size: 11px;"
                            f" font-weight: 600; padding: 6px 2px; background: qlineargradient(x1:0,y1:0,x2:1,y2:1,"
                            f" stop:0 {c.lighter(115).name()}, stop:1 {c.darker(135).name()}); }}"
                            f" QToolButton:hover {{ background: {c.lighter(130).name()}; }}")
            b.clicked.connect(lambda _c=False, cm=cmd: run(cm))
            grid.addWidget(b, i // 4, i % 4)
        self.lay.addLayout(grid)


# --------------------------------------------------------------------------- Startmenü
class AppTile(QToolButton):
    def __init__(self, name: str, icon: QIcon, parent=None):
        super().__init__(parent)
        self.app_name = name
        self.setIcon(icon if usable(icon) else letter_icon(name))
        self.setIconSize(QSize(44, 44))
        self.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self.setFixedSize(116, 96)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(name)
        self.setStyleSheet("QToolButton { color:#f1f5f9; background:transparent; border:none; border-radius:16px;"
                           " padding:6px 4px; font-size:12px; } QToolButton:hover { background: rgba(255,255,255,0.13); }"
                           " QToolButton:pressed { background: rgba(255,255,255,0.22); }")

    def setText(self, text: str) -> None:  # noqa: N802 – Qt-Name; zu lange Namen mit „…“
        super().setText(self.fontMetrics().elidedText(text, Qt.ElideRight, 106))


class StartMenu(QFrame):
    """Startmenü: Suche („Frag AluPC“), alle Programme (angeheftete zuerst), unten AluPC, Anpassen, Sperren, Energie."""

    def __init__(self, shell):
        super().__init__(shell, Qt.Popup | Qt.FramelessWindowHint)
        self.shell = shell
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(700, 620)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        card = QFrame()
        card.setObjectName("StartCard")
        card.setStyleSheet("#StartCard { background: rgba(16,18,36,0.96); border: 1px solid rgba(255,255,255,0.16);"
                           " border-radius: 24px; } QLabel { background: transparent; border: none; }")
        outer.addWidget(card)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(22, 20, 22, 16)
        lay.setSpacing(10)
        holder = QFrame()
        holder.setObjectName("Search")
        holder.setFixedHeight(48)
        holder.setStyleSheet("#Search { background: rgba(255,255,255,0.10); border: 1px solid rgba(255,255,255,0.22);"
                             " border-radius: 24px; }")
        h = QHBoxLayout(holder)
        h.setContentsMargins(18, 0, 14, 0)
        glass = QLabel()
        glass.setPixmap(icons.icon("search", "#e0e7ff", 20).pixmap(20, 20))
        h.addWidget(glass)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Programm suchen oder AluPC fragen („Timer 5 Minuten“, „Licht blau“) …")
        self.search.setStyleSheet("QLineEdit { background: transparent; color:#fff; border: none; font-size:15px; }")
        h.addWidget(self.search, 1)
        lay.addWidget(holder)
        self.answer = _label("", 13.5, 500, "#e0e7ff")
        self.answer.setWordWrap(True)
        lay.addWidget(self.answer)
        head = QHBoxLayout()
        head.addWidget(_label("Programme", 14, 700, "#e0e7ff"))
        head.addStretch(1)
        self.count = _label("", 12, 500, MUTED)
        head.addWidget(self.count)
        lay.addLayout(head)
        self.grid_holder = QWidget()
        self.grid_holder.setStyleSheet("background: transparent;")
        self.grid = QGridLayout(self.grid_holder)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(4)
        self.grid.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        scroll = QScrollArea()
        scroll.setWidget(self.grid_holder)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(SCROLL_STYLE)
        lay.addWidget(scroll, 1)
        lay.addWidget(_label("Rechtsklick auf ein Programm: an die Taskleiste anheften", 11.5, 400, MUTED))
        foot = QHBoxLayout()
        foot.setSpacing(8)
        self.hello = _label("", 14, 700)
        foot.addWidget(self.hello)
        self.status = _label("", 12, 500, MUTED)
        foot.addWidget(self.status)
        foot.addStretch(1)
        for icon_name, tip, fn in (("home", "AluPC öffnen", shell._open_alupc),
                                   ("palette", "Oberfläche anpassen", shell.customize),
                                   ("lock", "Sperren", shell._lock)):
            b = _round_button(icons.icon(icon_name, "#f1f5f9", 20), tip, 40, 20, "rgba(255,255,255,0.08)")
            b.clicked.connect(fn)
            foot.addWidget(b)
        self.power = _round_button(icons.icon("power", "#fca5a5", 20), "Energie", 40, 20, "rgba(255,255,255,0.08)")
        self.power.clicked.connect(lambda: shell._power_menu(self.power))
        foot.addWidget(self.power)
        lay.addLayout(foot)


class VolumePopup(QFrame):
    def __init__(self, shell):
        super().__init__(shell, Qt.Popup | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(360, 110)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        card = QFrame()
        card.setObjectName("VolCard")
        card.setStyleSheet("#VolCard { background: rgba(16,18,36,0.96); border: 1px solid rgba(255,255,255,0.16);"
                           " border-radius: 20px; } QLabel { background: transparent; border: none; }")
        outer.addWidget(card)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 12, 16, 12)
        head = QHBoxLayout()
        head.addWidget(_label("Lautstärke", 14, 700, "#e0e7ff"))
        head.addStretch(1)
        self.mixer = QToolButton()
        self.mixer.setText("Mischpult")
        self.mixer.setIcon(icons.icon("mixer", "#e0e7ff", 16))
        self.mixer.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.mixer.setStyleSheet("QToolButton { color:#e0e7ff; background: rgba(255,255,255,0.10); border:none;"
                                 " border-radius:11px; padding:4px 10px; font-size: 12px; }")
        head.addWidget(self.mixer)
        lay.addLayout(head)
        row = QHBoxLayout()
        self.mute = QToolButton()
        self.mute.setCheckable(True)
        self.mute.setIconSize(QSize(20, 20))
        self.mute.setStyleSheet("QToolButton { background: rgba(255,255,255,0.10); border:none; border-radius: 11px;"
                                " padding: 5px; } QToolButton:checked { background: rgba(239,68,68,0.35); }")
        row.addWidget(self.mute)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.setStyleSheet(
            "QSlider::groove:horizontal { height: 8px; border-radius: 4px; background: rgba(255,255,255,0.18); }"
            "QSlider::sub-page:horizontal { border-radius: 4px; background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            " stop:0 #6366f1, stop:1 #ec4899); }"
            "QSlider::handle:horizontal { background: #ffffff; width: 18px; height: 18px; margin: -5px 0;"
            " border-radius: 9px; }")
        row.addWidget(self.slider, 1)
        self.label = _label("", 13.5, 700)
        self.label.setMinimumWidth(44)
        row.addWidget(self.label)
        lay.addLayout(row)


# --------------------------------------------------------------------------- Taskleiste
class Taskbar(QFrame):
    def __init__(self, shell):
        super().__init__()
        self.shell = shell
        self.setObjectName("Taskbar")
        self.setFixedHeight(62)
        self.setStyleSheet("#Taskbar { background: rgba(10,12,26,0.72); border-top: 1px solid rgba(255,255,255,0.14); }"
                           " QLabel { background: transparent; border: none; }")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 6, 14, 6)
        lay.setSpacing(6)
        self.lead = QWidget()  # Abstand links (bei „mittig“ dehnbar)
        self.lead.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        lay.addWidget(self.lead)
        self.start = _round_button(icons.icon("grid", "#ffffff", 24), "Start (Programme, Suche)", 46, 24,
                                   "qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #6366f1, stop:1 #ec4899)")
        lay.addWidget(self.start)
        # AluPC selbst – immer direkt erreichbar (als System-Desktop gibt es kein Infobereich-Symbol)
        self.alupc = _round_button(icons.app_icon(), "AluPC öffnen (Hauptfenster)", 46, 30)
        lay.addWidget(self.alupc)
        self.apps = QHBoxLayout()
        self.apps.setSpacing(4)
        lay.addLayout(self.apps)
        self.trail = QWidget()
        self.trail.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        lay.addWidget(self.trail)
        tray = QHBoxLayout()
        tray.setSpacing(4)
        self.mon = QToolButton()
        self.mon.setIcon(icons.icon("monitor", "#e0e7ff", 18))
        self.mon.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.mon.setCursor(Qt.PointingHandCursor)
        self.mon.setStyleSheet("QToolButton { color:#e0e7ff; background: rgba(255,255,255,0.08); border:none;"
                               " border-radius: 12px; padding: 6px 10px; font-size: 12.5px; font-weight: 600; }"
                               " QToolButton:hover { background: rgba(255,255,255,0.18); }")
        tray.addWidget(self.mon)
        self.wifi = _round_button(icons.icon("wifi", "#e0e7ff", 20), "AluPC-WLAN", 40, 20)
        tray.addWidget(self.wifi)
        self.sound = _round_button(icons.icon("sound", "#e0e7ff", 20), "Lautstärke", 40, 20)
        tray.addWidget(self.sound)
        self.battery = _label("", 12.5, 600, "#e2e8f0")
        tray.addWidget(self.battery)
        clock = QVBoxLayout()
        clock.setSpacing(0)
        self.clock = _label("", 15, 700)
        self.clock.setAlignment(Qt.AlignRight)
        self.date = _label("", 11.5, 500, MUTED)
        self.date.setAlignment(Qt.AlignRight)
        clock.addWidget(self.clock)
        clock.addWidget(self.date)
        tray.addSpacing(6)
        tray.addLayout(clock)
        tray.addSpacing(6)
        self.gear = _round_button(icons.icon("sliders", "#e0e7ff", 20), "Oberfläche anpassen", 40, 20)
        tray.addWidget(self.gear)
        # nur als System-Desktop: zurück zum normalen Desktop (Explorer bzw. Plasma)
        self.normal = QToolButton()
        self.normal.setText("Normaler Desktop")
        self.normal.setIcon(icons.icon("window", "#e0e7ff", 18))
        self.normal.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.normal.setCursor(Qt.PointingHandCursor)
        self.normal.setToolTip("Zum normalen Desktop wechseln (Explorer bzw. Plasma) – AluPC läuft weiter")
        self.normal.setStyleSheet(self.mon.styleSheet())
        self.normal.setVisible(False)
        tray.addWidget(self.normal)
        lay.addLayout(tray)

    def set_centered(self, on: bool) -> None:
        self.lead.setVisible(on)


# --------------------------------------------------------------------------- Fenster
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
        self._windows: list = []
        self._win_key = None
        self._listing = False
        self.system = False  # als echter System-Desktop (statt Explorer/Plasma)
        self.bar_win: QWidget | None = None
        self._bg: tuple[tuple, QPixmap] | None = None
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.area = DesktopArea(self)
        root.addWidget(self.area, 1)
        self.bar = Taskbar(self)
        root.addWidget(self.bar)
        # Widgets auf dem Desktop
        self.clock_w = ClockWidget()
        self.monitor_w = MonitorWidget(self._run)
        self.quick_w = QuickWidget(self._run)
        for w in (self.clock_w, self.monitor_w, self.quick_w):
            self.area.add_widget(w.move_key, w)
        self.preview = self.monitor_w.preview
        self.mon_buttons = self.monitor_w.buttons
        # Startmenü / Lautstärke
        self.menu = StartMenu(self)
        self.search, self.answer, self.status = self.menu.search, self.menu.answer, self.menu.status
        self.search.textChanged.connect(self._filter)
        self.search.returnPressed.connect(self._enter)
        self.vol = VolumePopup(self)
        self.volume, self.mute, self.vol_label = self.vol.slider, self.vol.mute, self.vol.label
        self.volume.valueChanged.connect(self._volume_changed)
        self.mute.toggled.connect(self._set_mute)
        self.vol.mixer.clicked.connect(lambda: (self.vol.hide(), self._open_page(6)))
        self._vol_send = QTimer(self, singleShot=True, interval=120)
        self._vol_send.timeout.connect(self._apply_volume)
        self.clock = self.bar.clock
        self.bar.start.clicked.connect(self.toggle_menu)
        self.bar.sound.clicked.connect(lambda: self._popup(self.vol, self.bar.sound))
        self.bar.gear.clicked.connect(self.customize)
        self.bar.mon.clicked.connect(self._monitor_menu)
        self.bar.wifi.clicked.connect(lambda: self._open_page(5))
        self.bar.normal.clicked.connect(lambda: self.main_window.system_desktop(False))
        self.bar.alupc.clicked.connect(self._open_alupc)
        QShortcut(QKeySequence(Qt.Key_Escape), self, activated=self._escape)
        self._clock = QTimer(self, interval=1000)
        self._clock.timeout.connect(self._tick)
        self._slow = QTimer(self, interval=3000)
        self._slow.timeout.connect(self._refresh_slow)
        self._fade = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade.setDuration(260)
        self._fade.setEasingCurve(QEasingCurve.OutCubic)
        self.apply_settings()

    # ---------------------------------------------------------------- Einstellungen
    def cfg(self) -> dict:
        raw = dict(self.controller.config.data.get("shell") or {})
        cfg = {**DEFAULTS, **raw}
        cfg["widgets"] = {**DEFAULTS["widgets"], **(raw.get("widgets") or {})}
        cfg["pos"] = dict(raw.get("pos") or {})
        return cfg

    def save(self, **values) -> None:
        self.controller.config["shell"] = {**self.cfg(), **values}

    def apply_settings(self) -> None:
        """Nach „Anpassen“: Taskleiste, Symbole, Widgets, Hintergrund neu."""
        self.bar.set_centered(bool(self.cfg()["taskbar_center"]))
        self._bg = None
        self._build_taskbar_apps()
        if self.isVisible():
            self.area.reload()
            self._tick()
        self.update()

    def customize(self) -> None:
        from .shell_settings import ShellSettings

        self.menu.hide()
        ShellSettings(self).exec()

    # ---------------------------------------------------------------- Zeichnen
    def paintEvent(self, _e):
        t = theme.current()
        wall = self.cfg()["wallpaper"]
        key = (self.width(), self.height(), t.accent, t.accent2, wall)
        if self._bg is None or self._bg[0] != key:  # einmal je Größe/Farbe/Bild malen, dann nur noch kopieren
            pm = QPixmap(max(1, self.width()), max(1, self.height()))
            q = QPainter(pm)
            img = QPixmap(wall) if wall else QPixmap()
            if not img.isNull():  # eigenes Bild: füllend, mittig beschnitten
                scaled = img.scaled(pm.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                q.drawPixmap(-(scaled.width() - pm.width()) // 2, -(scaled.height() - pm.height()) // 2, scaled)
                q.fillRect(pm.rect(), QColor(0, 0, 0, 40))
            else:
                from ..desktop_theme import paint_wallpaper

                paint_wallpaper(q, pm.width(), pm.height(), True, colors=(t.accent, t.accent2))
            q.end()
            self._bg = (key, pm)
        p = QPainter(self)
        p.drawPixmap(0, 0, self._bg[1])

    # ---------------------------------------------------------------- Zeigen / Verlassen
    def _screen(self):
        screen = QGuiApplication.primaryScreen()
        out = self.controller.output_screen()
        if screen is out:  # nie auf Monitor 2
            screen = next((s for s in QGuiApplication.screens() if s is not out), screen)
        return screen

    def show_shell(self) -> None:
        screen = self._screen()
        self.setGeometry(screen.geometry())
        if self.system:
            self._show_as_desktop(screen)
        else:
            self.setWindowOpacity(0.0)
            self.showFullScreen()
            self.raise_()
            self.activateWindow()
            self._fade.stop()
            self._fade.setStartValue(0.0)
            self._fade.setEndValue(1.0)
            self._fade.start()
        self.area.reload()
        self._tick()
        self._refresh_slow()
        self._load_apps()
        self._clock.start()
        self._slow.start()
        self.save(open=True)

    def leave(self) -> None:
        self._clock.stop()
        self._slow.stop()
        self.menu.hide()
        self.vol.hide()
        self.hide()
        if self.bar_win is not None:
            self.bar_win.hide()
        self.save(open=False)

    def step_aside(self) -> None:
        """Programm wurde gestartet/vorgeholt: Oberfläche weg, das Programm ist vorne. Als System-Desktop bleibt sie
        (ganz unten, hinter dem Programm) – nur Startmenü/Lautstärke gehen zu."""
        self.menu.hide()
        self.vol.hide()
        if self.system:
            return
        self._clock.stop()
        self._slow.stop()
        self.hide()

    def _escape(self) -> None:
        if self.menu.isVisible():
            self.menu.hide()
        elif self.cfg()["esc_closes"] and not self.system:
            self.leave()

    # ---------------------------------------------------------------- Als System-Desktop
    BAR_TITLE = "AluPC – Taskleiste"

    def set_system(self, on: bool) -> None:
        """An: dieses Fenster ist der Desktop (immer ganz unten, hinter allen Programmen), die Taskleiste eine eigene
        Leiste (immer oben, Platz dafür reserviert). Aus: wieder ein Vollbild mit Taskleiste darin."""
        if bool(on) == self.system:
            return
        was = self.isVisible()
        self.hide()
        root = self.layout()
        if on:
            self.bar_win = QWidget(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
                                   | Qt.WindowDoesNotAcceptFocus)
            self.bar_win.setWindowTitle(self.BAR_TITLE)
            self.bar_win.setObjectName("TaskbarWindow")  # eigenes Fenster: kein Desktop dahinter → fester Grund
            self.bar_win.setAttribute(Qt.WA_StyledBackground, True)
            self.bar_win.setStyleSheet("#TaskbarWindow { background: #0d1022; }")
            self.bar_win.setAttribute(Qt.WA_X11NetWmWindowTypeDock, True)
            lay = QVBoxLayout(self.bar_win)
            lay.setContentsMargins(0, 0, 0, 0)
            root.removeWidget(self.bar)
            lay.addWidget(self.bar)
            root.setContentsMargins(0, 0, 0, self.bar.height())  # Symbole nicht unter die Taskleiste legen
            self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnBottomHint
                                | Qt.WindowDoesNotAcceptFocus)
            self.setAttribute(Qt.WA_X11NetWmWindowTypeDesktop, True)
        else:
            root.setContentsMargins(0, 0, 0, 0)
            root.addWidget(self.bar)
            if self.bar_win is not None:
                self.bar_win.hide()
                self.bar_win.deleteLater()
                self.bar_win = None
            self.setAttribute(Qt.WA_X11NetWmWindowTypeDesktop, False)
            self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.system = bool(on)
        self.bar.normal.setVisible(self.system)
        self._win_key = None
        if was:
            self.show_shell()

    def _show_as_desktop(self, screen) -> None:
        geo = screen.geometry()
        h = self.bar.height()
        self.setWindowOpacity(1.0)
        self.show()
        self.lower()
        bar = (geo.left(), geo.bottom() + 1 - h, geo.width(), h)
        self.bar_win.setGeometry(*bar)
        self.bar_win.show()
        self.bar_win.raise_()
        if IS_WINDOWS:  # ohne Explorer reserviert niemand Platz für die Taskleiste
            from ..platform.desktop_shell import set_work_area

            set_work_area(geo.left(), geo.top(), geo.right() + 1, geo.bottom() + 1 - h)
            return
        from ..platform import linux_windows
        from ..platform.linux_display import is_wayland

        if is_wayland():  # Wayland: KWin legt die Fenster hin (Programme dürfen das dort nicht selbst)
            desk = (geo.x(), geo.y(), geo.width(), geo.height())

            def pin():
                if self.system and self.isVisible():
                    linux_windows.kwin_window_props(self.TITLE, below=True, geo=desk)
                    linux_windows.kwin_window_props(self.BAR_TITLE, above=True, geo=bar)

            pin()
            # Das KWin-Skript findet ein Fenster erst, wenn KWin es kennt (kurz nach show) – darum nachfassen,
            # sonst bleibt es ein normales Fenster (in der Taskleiste, verschiebbar, falsche Größe)
            for ms in (250, 1000, 3000):
                QTimer.singleShot(ms, self, pin)
        elif QGuiApplication.platformName() == "xcb":  # nur echtes X11 (nicht offscreen/Tests)
            virt = screen.virtualGeometry()
            linux_windows.set_x11_strut(int(self.bar_win.winId()), virt.bottom() - geo.bottom() + h, geo.left(),
                                        geo.right())

    # ---------------------------------------------------------------- Startmenü / Popups
    def toggle_menu(self) -> None:
        if self.menu.isVisible():
            self.menu.hide()
            return
        g = self.bar.start.mapToGlobal(QPoint(0, 0))
        x = g.x() - 8 if not self.cfg()["taskbar_center"] else self.geometry().center().x() - self.menu.width() // 2
        self.menu.move(max(self.geometry().left() + 8, x), g.y() - self.menu.height() - 14)
        self.menu.show()
        self.search.setFocus()
        self.search.selectAll()

    def _popup(self, popup: QWidget, anchor: QWidget) -> None:
        g = anchor.mapToGlobal(QPoint(anchor.width(), 0))
        popup.move(min(g.x() - popup.width(), self.geometry().right() - popup.width() - 8), g.y() - popup.height() - 12)
        popup.show()

    # ---------------------------------------------------------------- Inhalte
    def _tick(self) -> None:
        from ..sources import format_date_de

        now = time.localtime()
        secs = self.cfg()["clock_seconds"]
        self.bar.clock.setText(time.strftime("%H:%M:%S" if secs else "%H:%M", now))
        self.bar.date.setText(time.strftime("%d.%m.%Y", now))
        self.clock_w.time.setText(time.strftime("%H:%M", now))
        self.clock_w.date.setText(f"{greeting(now.tm_hour)} · {format_date_de(now)}")
        self.menu.hello.setText(greeting(now.tm_hour))

    def _refresh_slow(self) -> None:
        import psutil

        parts = [f"CPU {psutil.cpu_percent():.0f} %", f"RAM {psutil.virtual_memory().percent:.0f} %"]
        try:
            bat = psutil.sensors_battery()
        except (AttributeError, OSError, NotImplementedError):
            bat = None
        self.bar.battery.setText(f"{bat.percent:.0f} %" + (" ⚡" if bat.power_plugged else "") if bat else "")
        self.bar.battery.setVisible(bat is not None)
        from ..hotspot import hotspot

        self.bar.wifi.setToolTip(f"AluPC-WLAN „{hotspot.ssid}“ an" if hotspot.running else "AluPC-WLAN aus (Gäste)")
        self.bar.wifi.setIcon(icons.icon("wifi", "#86efac" if hotspot.running else "#94a3b8", 20))
        self.status.setText("  ·  ".join(parts))
        self.clock_w.status.setText("  ·  ".join(parts))
        c = self.controller
        state = (c.describe() if hasattr(c, "describe") else "") or "bereit"
        self.monitor_w.state.setText(state[:28])
        self.bar.mon.setText("Monitor 2: " + state.split(" (")[0][:22])
        flags = {"schwarz": bool(getattr(c, "privacy", False)), "standbild": bool(getattr(c, "frozen", False)),
                 "spiegeln": bool(getattr(c, "mode", "") == "content" and (getattr(c, "content", None) or {})
                                  .get("mirror")),
                 "erweitern": bool(getattr(c, "mode", "") == "desktop"
                                   and str(getattr(c, "desktop_note", "")).startswith("Erweitert"))}
        for cmd, b in self.mon_buttons.items():
            b.setChecked(flags.get(cmd, False))
        if self.monitor_w.isVisible():
            try:
                pm = QPixmap()
                pm.loadFromData(c._preview_jpeg())
                self.preview.setPixmap(pm.scaled(self.preview.width() - 8, self.preview.height() - 8,
                                                 Qt.KeepAspectRatio, Qt.SmoothTransformation))
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

    def _app_icon(self, name: str, path: str) -> QIcon:
        icon = self._icons.get(path)
        if icon is None:
            icon = app_icon_for(path)
            if not usable(icon):
                icon = letter_icon(name)
            self._icons[path] = icon
        return icon

    def _icon_for_window(self, app: str, title: str) -> QIcon:
        """Logo eines offenen Fensters: passendes installiertes Programm (nach Programmname), sonst Fenster-Symbol."""
        low = (app or "").lower()
        for name, path in self._apps:
            n = name.lower()
            if low and (low == n or low == n.replace(" ", "") or n.split()[0] == low):
                return self._app_icon(name, path)
        for name, path in self._apps:
            if len(name) > 3 and name.lower() in title.lower():
                return self._app_icon(name, path)
        return icons.icon("window", "#e2e8f0", 24)

    def _skip_window(self, title: str) -> bool:
        # als Desktop gehört das AluPC-Fenster in die Taskleiste (es gibt dann kein Infobereich-Symbol)
        return title in (self.TITLE, self.BAR_TITLE) if self.system else title.startswith("AluPC")

    def _fill_windows(self) -> None:
        from ..sources import window_backend

        backend = window_backend()
        if not getattr(backend, "can_list", False) and not IS_WINDOWS:
            from ..platform.linux_display import is_wayland

            if is_wayland() and not self._listing:  # KDE/Wayland: KWin fragen (dauert etwas → im Hintergrund)
                from ..platform.base import WindowInfo
                from ..platform.kwin_capture import window_list

                self._listing = True

                def got(items):
                    self._listing = False
                    self._set_windows([WindowInfo(str(w["id"]), str(w.get("title", "")), str(w.get("app", "")),
                                                  bool(w.get("minimized"))) for w in items or []])

                run_async(lambda: window_list(skip=self._skip_window), got,
                          lambda _e: setattr(self, "_listing", False), owner=self)
            return
        try:
            wins = [w for w in backend.list_windows() if not self._skip_window(w.title)] \
                if getattr(backend, "can_list", False) else []
        except Exception:  # noqa: BLE001
            wins = []
        self._set_windows(wins)

    def _set_windows(self, wins: list) -> None:
        key = tuple((w.id, w.title) for w in wins)
        if key == self._win_key:
            return
        self._win_key = key
        self._windows = wins
        self._build_taskbar_apps()

    def _build_taskbar_apps(self) -> None:
        lay = self.bar.apps
        while lay.count():
            w = lay.takeAt(0).widget()
            if w is not None:
                w.deleteLater()
        known = {n for n, _p in self._apps}
        self.pinned_buttons = []
        for name in [p for p in self.cfg()["pinned"] if p in known][:10]:
            path = next(p for n, p in self._apps if n == name)
            b = _round_button(self._app_icon(name, path), name, 46, 28)
            b.clicked.connect(lambda _c=False, n=name: self._launch(n))
            b.setContextMenuPolicy(Qt.CustomContextMenu)
            b.customContextMenuRequested.connect(lambda _p, n=name, bb=b: self._tile_menu(n, bb))
            lay.addWidget(b)
            self.pinned_buttons.append(b)
        if self._windows:
            sep = QFrame()
            sep.setFixedSize(1, 30)
            sep.setStyleSheet("background: rgba(255,255,255,0.22);")
            lay.addWidget(sep)
        for w in self._windows[:12]:
            b = QToolButton()
            b.setIcon(self._icon_for_window(w.app, w.title))
            b.setIconSize(QSize(24, 24))
            b.setText(b.fontMetrics().elidedText(w.title, Qt.ElideRight, 130))
            b.setToolTip(w.title + ("  (minimiert)" if w.minimized else ""))
            b.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            b.setFixedHeight(46)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet("QToolButton { color:#f1f5f9; background: rgba(255,255,255,0.07); border:none;"
                            " border-radius: 14px; padding: 0 12px; font-size: 12.5px; }"
                            " QToolButton:hover { background: rgba(255,255,255,0.18); }")
            b.clicked.connect(lambda _c=False, wid=w.id: self._activate_id(wid))
            lay.addWidget(b)

    def _load_apps(self) -> None:
        if self._apps:
            return
        from .. import pc_control

        def done(apps):
            self._apps = apps or []
            self._build_tiles()
            self._build_taskbar_apps()
            if not IS_WINDOWS and not icon_index_ready():  # Logos im Hintergrund suchen, dann nachtragen
                run_async(icon_index, lambda _i: self._icons_found(), owner=self)

        run_async(pc_control.installed_apps, done, owner=self)

    def _icons_found(self) -> None:
        self._icons.clear()
        self._build_tiles()
        self._build_taskbar_apps()

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
        self.menu.count.setText(f"{len(self._apps)} Programme" if self._apps else "")
        self._relayout()

    def _relayout(self) -> None:
        grid = self.menu.grid
        for tl in self._tiles:
            grid.removeWidget(tl)
        i = 0
        for tl in self._tiles:
            if tl.property("hide"):
                tl.hide()
                continue
            tl.show()
            grid.addWidget(tl, i // 5, i % 5)
            i += 1

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

    def _tile_menu(self, name: str, anchor) -> None:
        menu = QMenu(self)
        if name in self.cfg()["pinned"]:
            menu.addAction("Von der Taskleiste lösen", lambda: self._pin(name, False))
        else:
            menu.addAction("An die Taskleiste anheften", lambda: self._pin(name, True))
        menu.exec(anchor.mapToGlobal(anchor.rect().bottomLeft()))

    def _pin(self, name: str, on: bool) -> None:
        pinned = [p for p in self.cfg()["pinned"] if p != name] + ([name] if on else [])
        self.save(pinned=pinned)
        self._build_tiles()
        self._build_taskbar_apps()

    # ---------------------------------------------------------------- Aktionen
    def _launch(self, name: str) -> None:
        from .. import pc_control

        ok, why = pc_control.launch_installed(name)
        if ok:
            self.step_aside()
        else:
            self.answer.setText(f"„{name}“: {why}")

    def _activate_id(self, win_id: str) -> None:
        if activate_window(str(win_id)):
            self.step_aside()

    def _run(self, cmd: str) -> None:
        self.controller.run_command(cmd)
        self._refresh_slow()

    def _monitor_menu(self) -> None:
        menu = QMenu(self)
        for cmd, icon_name, label in MONITOR:
            menu.addAction(icons.icon(icon_name, "#e0e7ff", 16), label, lambda c=cmd: self._run(c))
        menu.addSeparator()
        menu.addAction("AluPC öffnen", self._open_alupc)
        menu.exec(self.bar.mon.mapToGlobal(QPoint(0, -menu.sizeHint().height() - 6)))

    def _open_alupc(self) -> None:
        self.step_aside()
        self.main_window.show_normal_front()

    def _open_page(self, index: int) -> None:
        self._open_alupc()
        self.main_window._go(index)

    def _lock(self) -> None:
        self.controller.lock_computer()

    def _power_menu(self, anchor=None) -> None:
        from .. import pc_control

        anchor = anchor or self.menu.power
        menu = QMenu(self)
        for label, cmd in (("Energie sparen", "pc_schlafen"), ("Abmelden", "pc_abmelden"),
                           ("Neu starten", "pc_neustart"), ("Herunterfahren", "pc_herunterfahren")):
            def go(c=cmd, lab=label):
                if c != "pc_schlafen" and QMessageBox.question(self, "AluPC", f"Wirklich {lab.lower()}?") \
                        != QMessageBox.Yes:
                    return
                pc_control.power(c)

            menu.addAction(label, go)
        menu.exec(anchor.mapToGlobal(QPoint(0, -menu.sizeHint().height() - 6)))

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
        self.mute.setIcon(icons.icon("mute" if on else "sound", "#fca5a5" if on else "#f1f5f9", 20))
        self.bar.sound.setIcon(icons.icon("mute" if on else "sound", "#fca5a5" if on else "#e0e7ff", 20))
