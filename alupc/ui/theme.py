"""Farbschema (dunkel/hell, Akzentfarbe) und Stylesheet für die ganze Oberfläche."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication, QPalette

ACCENTS = {
    "blau": ("Blau", "#3b82f6"),
    "violett": ("Violett", "#8b5cf6"),
    "gruen": ("Grün", "#10b981"),
    "orange": ("Orange", "#f59e0b"),
    "rosa": ("Rosa", "#ec4899"),
}
MODES = {"system": "Wie das System", "dunkel": "Dunkel", "hell": "Hell"}


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
    danger: str = "#ef4444"
    warning: str = "#f59e0b"
    success: str = "#22c55e"

    def c(self, name: str) -> QColor:
        return QColor(getattr(self, name))

    def accent_soft(self, alpha: float = 0.16) -> str:
        c = QColor(self.accent)
        return f"rgba({c.red()},{c.green()},{c.blue()},{alpha})"

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
}

_current: Theme | None = None


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
    return app.palette().color(QPalette.Window).lightness() < 128


def make_theme(mode: str = "system", accent: str = "blau") -> Theme:
    dark = system_prefers_dark() if mode == "system" else mode == "dunkel"
    accent_hex = ACCENTS.get(accent, ACCENTS["blau"])[1]
    if dark:
        return Theme(True, accent_hex, bg="#0e1116", surface="#161a22", surface2="#1e2430",
                     border="#2a3140", text="#e8ecf3", muted="#8f99ab")
    return Theme(False, accent_hex, bg="#f3f5f9", surface="#ffffff", surface2="#eef1f6",
                 border="#dce2eb", text="#141a26", muted="#5d6678")


def current() -> Theme:
    global _current
    if _current is None:
        _current = make_theme()
    return _current


def apply(app, mode: str = "system", accent: str = "blau") -> Theme:
    """Farbschema auf die ganze Anwendung anwenden (auch nachträglich)."""
    global _current
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
    app.setStyleSheet(stylesheet(t, _check_image()))
    return t


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


def stylesheet(t: Theme, check_image: str = "") -> str:
    hover = t.mix(t.surface2, t.text, 0.06).name()
    accent_hover = t.mix(t.accent, "#ffffff", 0.12).name()
    return f"""
* {{ outline: none; }}
QWidget {{ color: {t.text}; }}
QMainWindow, QDialog {{ background: {t.bg}; }}
QToolTip {{ background: {t.surface2}; color: {t.text}; border: 1px solid {t.border};
            border-radius: 6px; padding: 6px 8px; }}

#Sidebar {{ background: {t.surface}; border-right: 1px solid {t.border}; }}
#Brand {{ font-size: 15pt; font-weight: 700; }}
#BrandSub, #Muted, QLabel[muted="true"] {{ color: {t.muted}; }}
#PageTitle {{ font-size: 18pt; font-weight: 700; }}
#PageSubtitle {{ color: {t.muted}; font-size: 10.5pt; }}
#SectionTitle {{ font-size: 11pt; font-weight: 700; }}

#Card, QGroupBox {{ background: {t.surface}; border: 1px solid {t.border}; border-radius: 14px; }}
QGroupBox {{ margin-top: 22px; padding: 14px 14px 12px 14px; font-weight: 700; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 14px; top: 2px; padding: 0 4px; color: {t.text}; }}

QPushButton, QToolButton#Plain {{
    background: {t.surface2}; border: 1px solid {t.border}; border-radius: 9px;
    padding: 7px 14px; min-height: 20px; }}
QPushButton:hover, QToolButton#Plain:hover {{ background: {hover}; }}
QPushButton:pressed {{ background: {t.border}; }}
QPushButton:disabled {{ color: {t.muted}; background: {t.surface}; }}
QPushButton[primary="true"] {{ background: {t.accent}; border-color: {t.accent}; color: #ffffff; font-weight: 600; }}
QPushButton[primary="true"]:hover {{ background: {accent_hover}; }}
QPushButton[danger="true"] {{ color: {t.danger}; }}
QPushButton:default {{ border-color: {t.accent}; }}

QLineEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox, QKeySequenceEdit QLineEdit {{
    background: {t.surface2}; border: 1px solid {t.border}; border-radius: 8px; padding: 6px 8px;
    selection-background-color: {t.accent}; }}
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border-color: {t.accent}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{ background: {t.surface}; border: 1px solid {t.border};
    selection-background-color: {t.accent_soft(0.35)}; selection-color: {t.text}; padding: 4px; }}
QSpinBox::up-button, QSpinBox::down-button, QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
    width: 18px; border: none; }}

QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: 5px; border: 1px solid {t.border};
    background: {t.surface2}; }}
QCheckBox::indicator:checked {{ background: {t.accent}; border-color: {t.accent};
    {f'image: url("{check_image}");' if check_image else ''} }}

QListWidget {{ background: {t.surface}; border: 1px solid {t.border}; border-radius: 10px; padding: 4px; }}
QListWidget::item {{ padding: 7px 8px; border-radius: 7px; }}
QListWidget::item:hover {{ background: {hover}; }}
QListWidget::item:selected {{ background: {t.accent_soft(0.28)}; color: {t.text}; }}

QTabWidget::pane {{ border: 1px solid {t.border}; border-radius: 10px; top: -1px; background: {t.surface}; }}
QTabBar::tab {{ background: transparent; padding: 8px 14px; margin-right: 4px; border-radius: 8px; color: {t.muted}; }}
QTabBar::tab:selected {{ background: {t.accent_soft(0.22)}; color: {t.text}; }}

QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {t.border}; border-radius: 4px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {t.muted}; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {t.border}; border-radius: 4px; min-width: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: none; }}

QSlider::groove:horizontal {{ height: 6px; background: {t.surface2}; border-radius: 3px; }}
QSlider::sub-page:horizontal {{ background: {t.accent}; border-radius: 3px; }}
QSlider::handle:horizontal {{ background: #ffffff; border: 2px solid {t.accent}; width: 14px; height: 14px;
    margin: -6px 0; border-radius: 9px; }}

QProgressBar {{ background: {t.surface2}; border: none; border-radius: 5px; height: 10px; text-align: center; }}
QProgressBar::chunk {{ background: {t.accent}; border-radius: 5px; }}

QMenu {{ background: {t.surface}; border: 1px solid {t.border}; border-radius: 10px; padding: 6px; }}
QMenu::item {{ padding: 7px 26px 7px 12px; border-radius: 6px; }}
QMenu::item:selected {{ background: {t.accent_soft(0.25)}; }}
QMenu::item:disabled {{ color: {t.muted}; }}
QMenu::separator {{ height: 1px; background: {t.border}; margin: 5px 8px; }}

QStatusBar {{ background: transparent; color: {t.muted}; }}
QMessageBox, QInputDialog, QColorDialog, QFileDialog {{ background: {t.bg}; }}
"""
