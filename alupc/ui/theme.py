"""Farbschema (dunkel/hell, Akzentfarbe) und Stylesheet für die ganze Oberfläche."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication, QPalette

ACCENTS = {
    "alupc": ("AluPC", "#5b8def"),  # eigenes Theme „Regiepult“ (docs/DESIGN.md) – Windows und Linux gleich
    "system": ("Wie das System", "#3b82f6"),  # Farbe kommt aus Windows/KDE (system_accent)
    "blau": ("Blau", "#3b82f6"),
    "violett": ("Violett", "#8b5cf6"),
    "gruen": ("Grün", "#10b981"),
    "orange": ("Orange", "#f59e0b"),
    "rosa": ("Rosa", "#ec4899"),
}
MODES = {"system": "Wie das System", "dunkel": "Dunkel", "hell": "Hell"}
# Anzeigen auf Monitor 2 (Abstimmung, Glücksrad, Codes …): ruhiger Graphit-Grund wie im Regiepult
STAGE_BG = "#0e1013"
STAGE_PANEL = "#191c20"


@dataclass
class Theme:
    dark: bool
    accent: str
    bg: str
    surface: str
    surface2: str
    border: str
    text: str
    muted: str
    accent2: str = "#8b5cf6"  # Partnerfarbe für Verläufe
    danger: str = "#ef4444"
    warning: str = "#f59e0b"
    success: str = "#22c55e"
    live: str = "#e5484d"  # Sendung: „läuft auf dem Bildschirm“ (Tally-Leuchte) – nur dafür
    ready: str = "#30a46c"  # bereit / verbunden

    def c(self, name: str) -> QColor:
        return QColor(getattr(self, name))

    def accent_soft(self, alpha: float = 0.16) -> str:
        c = QColor(self.accent)
        return f"rgba({c.red()},{c.green()},{c.blue()},{alpha})"

    def soft(self, color: str, alpha: float) -> str:
        c = QColor(color)
        return f"rgba({c.red()},{c.green()},{c.blue()},{alpha})"

    def gradient(self, rect, alpha: float = 1.0, diagonal: bool = True):
        """QLinearGradient Akzent → Partnerfarbe über `rect` (für selbst gezeichnete Teile)."""
        from PySide6.QtGui import QLinearGradient

        g = QLinearGradient(rect.topLeft(), rect.bottomRight() if diagonal else rect.topRight())
        a, b = QColor(self.accent), QColor(self.accent2)
        a.setAlphaF(alpha)
        b.setAlphaF(alpha)
        g.setColorAt(0, a)
        g.setColorAt(1, b)
        return g

    def mix(self, a: str, b: str, t: float) -> QColor:
        ca, cb = QColor(a), QColor(b)
        return QColor(round(ca.red() + (cb.red() - ca.red()) * t),
                      round(ca.green() + (cb.green() - ca.green()) * t),
                      round(ca.blue() + (cb.blue() - ca.blue()) * t))


# Farben für Quellen-Arten (Szenen-Vorschau, Symbole)
SOURCE_COLORS = {
    "camera": "#ef4444", "window": "#8b5cf6", "screen": "#3b82f6", "website": "#06b6d4",
    "image": "#10b981", "video": "#f97316", "slideshow": "#84cc16", "text": "#eab308",
    "clock": "#f59e0b", "countdown": "#f43f5e", "color": "#64748b", "scene": "#ec4899",
    "airplay": "#0ea5e9",
    "cast": "#8b5cf6",
    "wlan": "#0891b2",
    "design": "#6366f1",
    "nowplaying": "#1db954",
    "system": "#06b6d4",
}

_current: Theme | None = None
_sys_highlight: str = ""  # Markierungs- und Fensterfarbe des Systems, bevor AluPC die Palette überschreibt
_sys_window: str = ""


def system_prefers_dark() -> bool:
    app = QGuiApplication.instance()
    if app is None:
        return True
    try:
        scheme = app.styleHints().colorScheme()
        if scheme == Qt.ColorScheme.Dark:
            return True
        if scheme == Qt.ColorScheme.Light:
            return False
    except AttributeError:
        pass
    if _sys_window:  # AluPC hat die Palette schon überschrieben → die des Systems vom Start nehmen
        return QColor(_sys_window).lightness() < 128
    return app.palette().color(QPalette.Window).lightness() < 128




def _windows_accent() -> str:
    """Akzentfarbe aus Windows (Einstellungen → Personalisierung → Farben)."""
    import winreg

    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\DWM") as key:
        for name, abgr in (("AccentColor", True), ("ColorizationColor", False)):
            try:
                v = int(winreg.QueryValueEx(key, name)[0]) & 0xFFFFFFFF
            except OSError:
                continue
            r, g, b = (v & 0xFF, (v >> 8) & 0xFF, (v >> 16) & 0xFF) if abgr else \
                ((v >> 16) & 0xFF, (v >> 8) & 0xFF, v & 0xFF)
            return f"#{r:02x}{g:02x}{b:02x}"
    return ""


def _kde_accent(path=None) -> str:
    """Akzentfarbe aus KDE Plasma (~/.config/kdeglobals, [General] AccentColor=r,g,b)."""
    import configparser
    import os
    from pathlib import Path

    path = path or Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "kdeglobals"
    cp = configparser.ConfigParser(interpolation=None, strict=False)
    try:
        cp.read(path, encoding="utf-8")
        for section, key in (("General", "AccentColor"), ("Colors:Selection", "BackgroundNormal")):
            raw = cp.get(section, key, fallback="").strip()
            parts = [int(x) for x in raw.split(",")[:3]] if raw else []
            if len(parts) == 3:
                return "#{:02x}{:02x}{:02x}".format(*parts)
    except (OSError, ValueError, configparser.Error):
        pass
    return ""


# GNOME 47+: Einstellungen → Darstellung → Akzentfarbe (Namen aus gsettings, Farben wie in libadwaita)
GNOME_ACCENTS = {"blue": "#3584e4", "teal": "#2190a4", "green": "#3a944a", "yellow": "#c88800",
                 "orange": "#ed5b00", "red": "#e62d42", "pink": "#d56199", "purple": "#9141ac", "slate": "#6f8396"}


def _gnome_accent(run=None) -> str:
    import subprocess

    def default_run(cmd):
        return subprocess.run(cmd, capture_output=True, text=True, timeout=2).stdout

    try:
        out = (run or default_run)(["gsettings", "get", "org.gnome.desktop.interface", "accent-color"])
    except (OSError, subprocess.SubprocessError):
        return ""
    return GNOME_ACCENTS.get(out.strip().strip("'\""), "")


def linux_desktop() -> str:
    import os

    d = (os.environ.get("XDG_CURRENT_DESKTOP") or os.environ.get("DESKTOP_SESSION") or "").lower()
    return "kde" if "kde" in d or "plasma" in d else "gnome" if "gnome" in d or "unity" in d else d


def system_accent() -> str:
    """Akzentfarbe des Betriebssystems – Windows-Registry, KDE, GNOME oder Qt-Palette; sonst Blau."""
    import sys

    color = ""
    try:
        if sys.platform == "win32":
            color = _windows_accent()
        else:
            desk = linux_desktop()
            color = _gnome_accent() if desk == "gnome" else _kde_accent()
    except Exception:  # noqa: BLE001 - nur Farbe, Fehler egal
        color = ""
    if not color:
        color = _sys_highlight
        app = QGuiApplication.instance()
        if not color and app is not None:
            color = app.palette().color(QPalette.Highlight).name()
    c = QColor(color)
    if not c.isValid() or c.hslSaturation() < 40:  # grau/kaputt → kein brauchbarer Akzent
        return ACCENTS["blau"][1]
    return c.name()


def make_theme(mode: str = "system", accent: str = "blau") -> Theme:
    """Regiepult (docs/DESIGN.md): Graphit (dunkel) bzw. Alu (hell), neutrale Flächen; der Akzent ist die
    Bedienfarbe, Rot (live) zeigt nur, was gerade auf dem Bildschirm läuft."""
    dark = system_prefers_dark() if mode == "system" else mode == "dunkel"
    key = accent if accent in ACCENTS else "alupc"
    if key == "alupc":
        accent_hex = "#5b8def" if dark else "#2f6fdb"
    elif key == "system":
        accent_hex = system_accent()
    else:
        accent_hex = ACCENTS[key][1]
    if dark:
        return Theme(True, accent_hex, bg="#111316", surface="#191c20", surface2="#23272c", border="#30353c",
                     text="#eceef1", muted="#979ea9", accent2=accent_hex, danger="#f2555a", live="#e5484d",
                     ready="#30a46c")
    return Theme(False, accent_hex, bg="#e6e8eb", surface="#f6f7f8", surface2="#ffffff", border="#c9ced5",
                 text="#15181c", muted="#59616c", accent2=accent_hex, danger="#d93a40", live="#d93a40",
                 ready="#218358")


def current() -> Theme:
    global _current
    if _current is None:
        _current = make_theme()
    return _current


_fonts_loaded = False
UI_FONT = "Inter"
HEAD_FONT = "Barlow Semi Condensed"  # Titel, Kacheln, Tasten – schmal und technisch wie Pultbeschriftung
MONO_FONT = "JetBrains Mono"


def load_fonts(app) -> bool:
    """Mitgelieferte Schriften laden (Inter, Barlow Semi Condensed, JetBrains Mono) – damit AluPC unter Windows und Linux gleich aussieht.
    False = Schriftdateien fehlen (dann nimmt Qt die Systemschrift)."""
    global _fonts_loaded
    if _fonts_loaded:
        return True
    from pathlib import Path

    from PySide6.QtGui import QFont, QFontDatabase

    folder = Path(__file__).resolve().parent.parent / "assets" / "fonts"
    ok = False
    for file in sorted(folder.glob("*.ttf")):
        if QFontDatabase.addApplicationFont(str(file)) >= 0:
            ok = True
    if ok:
        font = QFont(UI_FONT)
        font.setPointSizeF(10)
        font.setHintingPreference(QFont.PreferNoHinting)  # gleiche Buchstabenbreiten auf allen Systemen
        app.setFont(font)
        for generic in ("Monospace", "monospace", "Consolas", "DejaVu Sans Mono"):
            QFont.insertSubstitution(generic, MONO_FONT)
    _fonts_loaded = ok
    return ok


def apply(app, mode: str = "system", accent: str = "blau") -> Theme:
    """Farbschema auf die ganze Anwendung anwenden (auch nachträglich)."""
    global _current, _sys_highlight, _sys_window
    load_fonts(app)
    if not _sys_highlight:
        _sys_highlight = app.palette().color(QPalette.Highlight).name()
        _sys_window = app.palette().color(QPalette.Window).name()
    t = _current = make_theme(mode, accent)
    if app.style().name().lower() != "fusion":
        app.setStyle("Fusion")
    pal = QPalette()
    for role, color in [
        (QPalette.Window, t.bg), (QPalette.Base, t.surface), (QPalette.AlternateBase, t.surface2),
        (QPalette.Button, t.surface2), (QPalette.Text, t.text), (QPalette.WindowText, t.text),
        (QPalette.ButtonText, t.text), (QPalette.ToolTipBase, t.surface2), (QPalette.ToolTipText, t.text),
        (QPalette.Highlight, t.accent), (QPalette.HighlightedText, "#ffffff"), (QPalette.Link, t.accent),
        (QPalette.PlaceholderText, t.muted), (QPalette.Mid, t.border),
    ]:
        pal.setColor(role, QColor(color))
    for role in (QPalette.Text, QPalette.WindowText, QPalette.ButtonText):
        pal.setColor(QPalette.Disabled, role, QColor(t.muted))
    app.setPalette(pal)
    app.setStyleSheet(stylesheet(t, _check_image(), _arrow_image(t)))
    _install_title_bars(app, t)
    return t


_sig_cache: tuple = (0.0, None)


def system_signature() -> tuple:
    """Was „Wie das System“ gerade bedeutet (hell/dunkel + Farbe) – ändert es sich, wird neu eingefärbt.
    Höchstens alle 3 s wirklich nachsehen (mehrere Fenster teilen sich das Ergebnis)."""
    import time

    global _sig_cache
    now = time.monotonic()
    if _sig_cache[1] is None or now - _sig_cache[0] > 3:
        _sig_cache = (now, (system_prefers_dark(), system_accent()))
    return _sig_cache[1]


# ------------------------------------------------------------------ Windows: Titelleiste passend zur App
def title_bar(widget, t: Theme | None = None) -> bool:
    """Windows 10/11: dunkle bzw. helle Titelleiste, Windows 11 zusätzlich in der App-Hintergrundfarbe."""
    import sys

    if sys.platform != "win32":
        return False
    try:
        import ctypes

        t = t or current()
        hwnd = int(widget.winId())
        dwm = ctypes.windll.dwmapi

        def setattr_(attr: int, value: int) -> bool:
            v = ctypes.c_int(value)
            return dwm.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(v), ctypes.sizeof(v)) == 0

        def colorref(color: str) -> int:
            c = QColor(color)
            return c.red() | (c.green() << 8) | (c.blue() << 16)

        ok = setattr_(20, int(t.dark)) or setattr_(19, int(t.dark))  # DWMWA_USE_IMMERSIVE_DARK_MODE (19: alte Win10)
        setattr_(35, colorref(t.bg))    # DWMWA_CAPTION_COLOR (nur Windows 11)
        setattr_(36, colorref(t.text))  # DWMWA_TEXT_COLOR
        setattr_(34, colorref(t.border))  # DWMWA_BORDER_COLOR
        return ok
    except Exception:  # noqa: BLE001 - nur Optik
        return False


_title_filter = None


def _install_title_bars(app, t: Theme) -> None:
    import sys

    if sys.platform != "win32":
        return
    from PySide6.QtCore import QEvent, QObject

    global _title_filter
    if _title_filter is None:
        class _Filter(QObject):
            def eventFilter(self, obj, event):  # noqa: N802 - Qt
                if event.type() == QEvent.Show and getattr(obj, "isWindow", None) and obj.isWindow() \
                        and not obj.property("alupc_titlebar"):
                    obj.setProperty("alupc_titlebar", True)
                    title_bar(obj)
                return False

        _title_filter = _Filter(app)
        app.installEventFilter(_title_filter)
    for w in app.topLevelWidgets():  # schon offene Fenster nach Design-Wechsel nachziehen
        if w.isVisible():
            title_bar(w, t)


def round_popup(menu) -> None:
    """Menü mit echten runden Ecken (durchsichtiger Fensterhintergrund, kein eckiger Systemschatten).
    Einzeln am Menü gesetzt – ein programmweiter Ereignisfilter bringt den Browser-Baustein zum Absturz."""
    if menu is None or menu.testAttribute(Qt.WA_TranslucentBackground) or menu.isVisible():
        return
    menu.setWindowFlag(Qt.FramelessWindowHint, True)
    menu.setWindowFlag(Qt.NoDropShadowWindowHint, True)
    menu.setAttribute(Qt.WA_TranslucentBackground, True)


def _arrow_image(t) -> str:
    """Pfeil nach unten für Auswahllisten (Farbe passend zum Design)."""
    import tempfile
    from pathlib import Path


    path = Path(tempfile.gettempdir()) / f"alupc-chevron-{QColor(t.muted).name()[1:]}.png"
    try:
        if not path.exists():
            from PySide6.QtCore import QPointF
            from PySide6.QtGui import QPainter, QPen, QPixmap

            px = QPixmap(28, 28)  # doppelt so groß gezeichnet → scharf auf hochauflösenden Bildschirmen
            px.fill(Qt.transparent)
            p = QPainter(px)
            p.setRenderHint(QPainter.Antialiasing)
            p.setPen(QPen(QColor(t.muted), 3.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.drawPolyline([QPointF(7, 11), QPointF(14, 18), QPointF(21, 11)])
            p.end()
            px.save(str(path))
        return path.as_posix()
    except OSError:
        return ""


def _check_image() -> str:
    """Weißer Haken als Bilddatei für angekreuzte Kästchen (QSS braucht eine Datei)."""
    import tempfile
    from pathlib import Path

    from . import icons

    path = Path(tempfile.gettempdir()) / "alupc-check.png"
    try:
        if not path.exists():
            icons.pixmap("check", "#ffffff", 14, stroke=3.0, dpr=1).save(str(path))
        return path.as_posix()
    except OSError:
        return ""


def _fader_image(t: Theme) -> str:
    """Griffrille der Fader-Kappe (waagerechter Strich) als kleines Bild für das Stylesheet."""
    import tempfile
    from pathlib import Path

    from PySide6.QtGui import QImage, QPainter, QPen

    path = Path(tempfile.gettempdir()) / f"alupc-fader-{'d' if t.dark else 'h'}.png"
    try:
        if not path.exists():
            img = QImage(28, 44, QImage.Format_ARGB32)
            img.fill(Qt.transparent)
            p = QPainter(img)
            p.setRenderHint(QPainter.Antialiasing)
            p.setPen(QPen(QColor(t.text), 3))
            p.drawLine(5, 22, 23, 22)
            p.end()
            img.setDevicePixelRatio(2)
            img.save(str(path))
        return path.as_posix()
    except OSError:
        return ""


def stylesheet(t: Theme, check_image: str = "", arrow_image: str = "") -> str:
    """Regiepult (docs/DESIGN.md): flache Flächen, Fugen statt Schatten, Rundung nach Rang (Pult 10, Taste 6),
    Tasten mit hellerer Oberkante. Keine Verläufe, kein Glas."""
    a1 = t.accent
    head = HEAD_FONT
    hover = t.mix(t.surface2, t.text, 0.06).name()
    pressed = t.mix(t.surface2, t.text, 0.12).name()
    # Taste: Oberkante heller (dunkel) bzw. Unterkante dunkler (hell) – wie eine echte Pulttaste
    key_top = t.mix(t.border, "#ffffff", 0.14).name() if t.dark else t.border
    key_bottom = t.border if t.dark else t.mix(t.border, "#000000", 0.12).name()
    a1_hover = t.mix(a1, "#ffffff", 0.10).name()
    a1_down = t.mix(a1, "#000000", 0.12).name()
    sel = t.soft(a1, 0.20 if t.dark else 0.13)
    side = t.mix(t.bg, "#000000", 0.18).name() if t.dark else t.surface
    field = t.mix(t.bg, t.surface, 0.5).name() if t.dark else "#ffffff"
    slot = "#08090b" if t.dark else "#aab1ba"  # Schlitz im Pult
    cap = t.mix(t.surface2, "#ffffff", 0.16).name() if t.dark else "#ffffff"  # Fader-Kappe
    fader_image = _fader_image(t)
    return f"""
* {{ outline: none; }}
QWidget {{ color: {t.text}; }}
QMainWindow, QDialog {{ background: {t.bg}; }}
QToolTip {{ background: {t.surface2}; color: {t.text}; border: 1px solid {t.border}; border-radius: 6px; padding: 6px 9px; }}

#Sidebar {{ background: {side}; border-right: 1px solid {t.border}; }}
#Content {{ background: transparent; }}
#PageIcon {{ background: {t.surface2}; border: 1px solid {t.border}; border-radius: 8px; }}
#Brand {{ font-family: "{head}"; font-size: 16pt; font-weight: 700; }}
#BrandSub, #Muted, QLabel[muted="true"] {{ color: {t.muted}; }}
#PageTitle {{ font-family: "{head}"; font-size: 22pt; font-weight: 700; }}
#PageSubtitle {{ color: {t.muted}; font-size: 10pt; }}
#SectionTitle {{ font-family: "{head}"; font-size: 12.5pt; font-weight: 600; }}
#StartSection {{ font-family: "{head}"; font-size: 12pt; font-weight: 600; color: {t.text};
                 padding: 10px 0 4px 0; border-bottom: 1px solid {t.border}; }}

#Card, QGroupBox {{ background: {t.surface}; border: 1px solid {t.border}; border-radius: 10px; }}
#Hero {{ background: {t.surface}; border: 1px solid {t.border}; border-radius: 10px; }}
QPushButton#Chip {{ border-radius: 13px; padding: 5px 12px; background: {t.surface2}; font-weight: 600; }}
QPushButton#Chip:checked {{ background: {a1}; border-color: {a1}; color: #ffffff; }}
QGroupBox {{ margin-top: 30px; padding: 18px 16px 14px 16px; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 2px; top: 4px; padding: 0 2px; color: {t.text};
                   font-family: "{head}"; font-size: 12.5pt; font-weight: 600; }}

QPushButton, QToolButton#Plain {{
    background: {t.surface2}; border: 1px solid {t.border}; border-top-color: {key_top};
    border-bottom-color: {key_bottom}; border-radius: 6px; padding: 6px 14px; min-height: 20px;
    font-family: "{head}"; font-size: 11pt; font-weight: 600; }}
QPushButton:hover, QToolButton#Plain:hover {{ background: {hover}; }}
QPushButton:pressed {{ background: {pressed}; border-top-color: {key_bottom}; }}
QPushButton:disabled {{ color: {t.muted}; background: {t.surface}; border-color: {t.border}; }}
QPushButton[primary="true"] {{ background: {a1}; border: 1px solid {a1_down}; border-top-color: {a1_hover};
    color: #ffffff; }}
QPushButton[primary="true"]:hover {{ background: {a1_hover}; }}
QPushButton[primary="true"]:pressed {{ background: {a1_down}; }}
QPushButton[primary="true"]:disabled {{ background: {t.surface2}; border-color: {t.border}; color: {t.muted}; }}
QPushButton[danger="true"] {{ color: {t.danger}; }}
QPushButton[danger="true"]:hover {{ background: {t.soft(t.danger, 0.12)}; border-color: {t.soft(t.danger, 0.5)}; }}
QPushButton:default {{ border-color: {a1}; }}
QPushButton#Segment {{ border-radius: 6px; padding: 6px 16px; min-width: 56px; }}
QPushButton#Segment:checked {{ background: {a1}; border-color: {a1_down}; color: #ffffff; }}

QLineEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox, QKeySequenceEdit QLineEdit {{
    background: {field}; border: 1px solid {t.border}; border-radius: 6px; padding: 6px 9px;
    selection-background-color: {a1}; }}
QLineEdit:hover, QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover {{ border-color: {t.mix(t.border, t.text, 0.25).name()}; }}
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{ border-color: {a1}; }}
QComboBox {{ padding-right: 30px; combobox-popup: 0; }}
QComboBox::drop-down {{ subcontrol-origin: padding; subcontrol-position: center right; border: none; width: 28px; }}
QComboBox::down-arrow {{ {f'image: url("{arrow_image}");' if arrow_image else ''} width: 14px; height: 14px; }}
QComboBox::down-arrow:on {{ top: 1px; }}
QComboBoxPrivateContainer {{ background: {t.surface}; border: 1px solid {t.border}; }}
QComboBox QAbstractItemView {{ background: {t.surface}; border: none; padding: 4px; outline: 0;
    selection-background-color: transparent; selection-color: {t.text}; }}
QComboBox QAbstractItemView::item {{ min-height: 30px; padding: 2px 10px; border-radius: 4px; margin: 1px 0; }}
QComboBox QAbstractItemView::item:hover {{ background: {hover}; }}
QComboBox QAbstractItemView::item:selected {{ background: {sel}; color: {t.text}; }}
QSpinBox::up-button, QSpinBox::down-button, QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
    width: 18px; border: none; }}

QCheckBox, QRadioButton {{ spacing: 9px; }}
QRadioButton::indicator {{ width: 16px; height: 16px; border-radius: 9px; border: 1px solid {t.border};
    background: {field}; }}
QRadioButton::indicator:checked {{ background: {a1}; border: 4px solid {field}; }}
QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: 4px; border: 1px solid {t.border};
    background: {field}; }}
QCheckBox::indicator:hover {{ border-color: {a1}; }}
QCheckBox::indicator:checked {{ background: {a1}; border-color: {a1};
    {f'image: url("{check_image}");' if check_image else ''} }}

QListWidget {{ background: {t.surface}; border: 1px solid {t.border}; border-radius: 8px; padding: 4px; }}
QListWidget::item {{ padding: 7px 8px; border-radius: 4px; }}
QListWidget::item:hover {{ background: {hover}; }}
QListWidget::item:selected {{ background: {sel}; color: {t.text}; }}
QListWidget::indicator, QTreeWidget::indicator {{ width: 17px; height: 17px; border-radius: 4px;
    border: 1px solid {t.border}; background: {field}; }}
QListWidget::indicator:checked, QTreeWidget::indicator:checked {{ background: {a1}; border-color: {a1};
    {f'image: url("{check_image}");' if check_image else ''} }}
QListWidget#SetupNav {{ background: {t.surface}; border: 1px solid {t.border}; border-radius: 10px; padding: 6px; }}
QListWidget#SetupNav::item {{ padding: 8px 10px; margin: 1px 0; border-radius: 4px; border-left: 3px solid transparent; }}
QListWidget#SetupNav::item:selected {{ background: {t.surface2}; border-left: 3px solid {a1}; font-weight: 600; }}

QTabWidget::pane {{ border: 1px solid {t.border}; border-radius: 8px; top: -1px; background: {t.surface}; }}
QTabBar::tab {{ background: transparent; padding: 8px 14px; margin-right: 2px; color: {t.muted};
    font-family: "{head}"; font-size: 11pt; font-weight: 600; border-bottom: 2px solid transparent; }}
QTabBar::tab:hover {{ color: {t.text}; }}
QTabBar::tab:selected {{ color: {t.text}; border-bottom: 2px solid {a1}; }}

QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 9px; margin: 3px; }}
QScrollBar::handle:vertical {{ background: {t.border}; border-radius: 3px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {t.muted}; }}
QScrollBar:horizontal {{ background: transparent; height: 9px; margin: 3px; }}
QScrollBar::handle:horizontal {{ background: {t.border}; border-radius: 3px; min-width: 30px; }}
QScrollBar::handle:horizontal:hover {{ background: {t.muted}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: none; }}

QSlider::groove:horizontal {{ height: 6px; background: {slot}; border: 1px solid {t.border}; border-radius: 3px; }}
QSlider::sub-page:horizontal {{ background: {a1}; border: 1px solid {t.border}; border-radius: 3px; }}
QSlider::handle:horizontal {{ background: {cap}; border: 1px solid {t.mix(t.border, t.text, 0.35).name()};
    width: 14px; height: 22px; margin: -9px 0; border-radius: 3px;
    {f'image: url("{fader_image}");' if fader_image else ''} }}
QSlider::handle:horizontal:hover {{ border-color: {a1}; }}
QSlider::groove:vertical {{ width: 6px; background: {slot}; border: 1px solid {t.border}; border-radius: 3px; }}
QSlider::add-page:vertical {{ background: {a1}; border: 1px solid {t.border}; border-radius: 3px; }}
QSlider::handle:vertical {{ background: {cap}; border: 1px solid {t.mix(t.border, t.text, 0.35).name()};
    height: 14px; width: 26px; margin: 0 -11px; border-radius: 3px; }}

QProgressBar {{ background: {t.border}; border: none; border-radius: 3px; height: 8px; text-align: center; }}
QProgressBar::chunk {{ background: {a1}; border-radius: 3px; }}

QMenu {{ background: {t.surface}; border: 1px solid {t.border}; border-radius: 8px; padding: 6px; min-width: 230px; }}
QMenu::item {{ padding: 8px 30px 8px 12px; border-radius: 4px; margin: 1px 0; }}
QMenu::item:selected {{ background: {sel}; color: {t.text}; }}
QMenu::item:disabled {{ color: {t.muted}; }}
QMenu::icon {{ padding-left: 10px; }}
QMenu::indicator {{ width: 16px; height: 16px; margin-left: 10px; border-radius: 4px; border: 1px solid {t.border};
    background: {field}; }}
QMenu::indicator:checked {{ background: {a1}; border-color: {a1};
    {f'image: url("{check_image}");' if check_image else ''} }}
QMenu::separator {{ height: 1px; background: {t.border}; margin: 5px 8px; }}

QStatusBar {{ background: transparent; color: {t.muted}; }}
QMessageBox, QInputDialog, QColorDialog, QFileDialog {{ background: {t.bg}; }}
"""
