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
# Zweite Farbe je Akzent: Verläufe (Knöpfe, Navigation, Symbole) laufen von der Akzentfarbe zu dieser
ACCENT_PARTNERS = {"blau": "#8b5cf6", "violett": "#ec4899", "gruen": "#06b6d4", "orange": "#ef4444",
                   "rosa": "#f97316"}
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
    accent2: str = "#8b5cf6"  # Partnerfarbe für Verläufe
    danger: str = "#ef4444"
    warning: str = "#f59e0b"
    success: str = "#22c55e"

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
    "design": "#6366f1",
    "nowplaying": "#1db954",
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
    key = accent if accent in ACCENTS else "blau"
    accent_hex, partner = ACCENTS[key][1], ACCENT_PARTNERS[key]
    if dark:  # tiefes Nachtblau – farbige Verläufe leuchten darauf
        return Theme(True, accent_hex, bg="#070a12", surface="#0f1421", surface2="#171e2e",
                     border="#232c40", text="#f1f4fa", muted="#8d97ab", accent2=partner)
    return Theme(False, accent_hex, bg="#eef1f8", surface="#ffffff", surface2="#f1f4fa",
                 border="#dde3ee", text="#0f172a", muted="#58627a", accent2=partner)


def current() -> Theme:
    global _current
    if _current is None:
        _current = make_theme()
    return _current


_fonts_loaded = False
UI_FONT = "Inter"
MONO_FONT = "JetBrains Mono"


def load_fonts(app) -> bool:
    """Mitgelieferte Schriften laden (Inter, JetBrains Mono) – damit AluPC unter Windows und Linux gleich aussieht.
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
    global _current
    load_fonts(app)
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
    a1, a2 = t.accent, t.accent2
    a1_hi = t.mix(a1, "#ffffff", 0.14).name()
    a2_hi = t.mix(a2, "#ffffff", 0.14).name()
    grad = f"qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {a1}, stop:1 {a2})"
    grad_h = f"qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {a1}, stop:1 {a2})"
    grad_hover = f"qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {a1_hi}, stop:1 {a2_hi})"
    # Glas-Karten: oben einen Hauch heller, feine helle Kante
    card_top = t.mix(t.surface, "#ffffff", 0.035 if t.dark else 0.0).name()
    card_bottom = t.mix(t.surface, t.bg, 0.35 if t.dark else 0.0).name()
    card = f"qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {card_top}, stop:1 {card_bottom})"
    edge = t.mix(t.border, a1, 0.18).name()
    return f"""
* {{ outline: none; }}
QWidget {{ color: {t.text}; }}
QMainWindow, QDialog {{ background: {t.bg}; }}
QToolTip {{ background: {t.surface2}; color: {t.text}; border: 1px solid {edge};
            border-radius: 8px; padding: 6px 9px; }}

#Sidebar {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {t.surface}, stop:0.7 {t.bg},
             stop:1 {t.soft(a2, 0.10)}); border-right: 1px solid {t.border}; }}
#Content {{ background: qradialgradient(cx:0.15, cy:0, radius:0.9, fx:0.15, fy:0, stop:0 {t.soft(a1, 0.16 if t.dark else 0.10)},
             stop:0.45 {t.soft(a2, 0.06 if t.dark else 0.04)}, stop:1 {t.bg}); }}
#PageIcon {{ background: {grad}; border-radius: 14px; }}
#Brand {{ font-size: 15pt; font-weight: 800; }}
#BrandSub, #Muted, QLabel[muted="true"] {{ color: {t.muted}; }}
#PageTitle {{ font-size: 21pt; font-weight: 800; letter-spacing: -0.3px; }}
#PageSubtitle {{ color: {t.muted}; font-size: 10.5pt; }}
#SectionTitle {{ font-size: 11pt; font-weight: 700; }}
#StartSection {{ font-size: 8.5pt; font-weight: 800; letter-spacing: 1.4px; color: {t.muted};
                 padding: 10px 0 2px 2px; border-bottom: 1px solid {t.border}; }}

#Card, QGroupBox {{ background: {card}; border: 1px solid {edge}; border-radius: 18px; }}
#Hero {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {card_top}, stop:0.5 {t.surface},
        stop:0.85 {t.soft(a1, 0.16)}, stop:1 {t.soft(a2, 0.24)}); border: 1px solid {t.soft(a1, 0.35)};
        border-radius: 24px; }}
QPushButton#Chip {{ border-radius: 17px; padding: 7px 14px; background: {t.surface2}; font-weight: 600; }}
QPushButton#Chip:checked {{ background: {grad_h}; border-color: transparent; color: #ffffff; }}
QGroupBox {{ margin-top: 30px; padding: 18px 18px 16px 18px; font-weight: 700; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 8px; top: 4px; padding: 0 4px; color: {t.text};
                   font-size: 11pt; font-weight: 800; }}

QPushButton, QToolButton#Plain {{
    background: {t.surface2}; border: 1px solid {t.border}; border-radius: 11px;
    padding: 7px 15px; min-height: 20px; font-weight: 600; }}
QPushButton:hover, QToolButton#Plain:hover {{ background: {hover}; border-color: {edge}; }}
QPushButton:pressed {{ background: {t.border}; }}
QPushButton:disabled {{ color: {t.muted}; background: {t.surface}; }}
QPushButton[primary="true"] {{ background: {grad}; border: 1px solid {t.soft(a2, 0.6)}; color: #ffffff;
    font-weight: 700; }}
QPushButton[primary="true"]:hover {{ background: {grad_hover}; }}
QPushButton[primary="true"]:disabled {{ background: {t.surface2}; border-color: {t.border}; color: {t.muted}; }}
QPushButton[danger="true"] {{ color: {t.danger}; }}
QPushButton[danger="true"]:hover {{ background: {t.soft(t.danger, 0.14)}; border-color: {t.soft(t.danger, 0.5)}; }}
QPushButton:default {{ border-color: {a1}; }}
QPushButton#Segment {{ border-radius: 17px; padding: 7px 18px; min-width: 56px; }}
QPushButton#Segment:checked {{ background: {grad_h}; border-color: transparent; color: #ffffff; font-weight: 700; }}

QLineEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox, QKeySequenceEdit QLineEdit {{
    background: {t.surface2}; border: 1px solid {t.border}; border-radius: 10px; padding: 6px 9px;
    selection-background-color: {a1}; }}
QLineEdit:hover, QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover {{ border-color: {edge}; }}
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border-color: {a1}; background: {t.mix(t.surface2, a1, 0.05).name()}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{ background: {t.surface}; border: 1px solid {edge}; border-radius: 10px;
    selection-background-color: {t.soft(a1, 0.35)}; selection-color: {t.text}; padding: 4px; }}
QSpinBox::up-button, QSpinBox::down-button, QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
    width: 18px; border: none; }}

QCheckBox, QRadioButton {{ spacing: 9px; }}
QRadioButton::indicator {{ width: 16px; height: 16px; border-radius: 9px; border: 1px solid {t.border};
    background: {t.surface2}; }}
QRadioButton::indicator:checked {{ background: {grad}; border: 4px solid {t.surface2}; }}
QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: 6px; border: 1px solid {t.border};
    background: {t.surface2}; }}
QCheckBox::indicator:hover {{ border-color: {a1}; }}
QCheckBox::indicator:checked {{ background: {grad}; border-color: transparent;
    {f'image: url("{check_image}");' if check_image else ''} }}

QListWidget {{ background: {t.surface}; border: 1px solid {t.border}; border-radius: 12px; padding: 4px; }}
QListWidget::item {{ padding: 7px 8px; border-radius: 8px; }}
QListWidget::item:hover {{ background: {hover}; }}
QListWidget::item:selected {{ background: {t.soft(a1, 0.26)}; color: {t.text}; }}
QListWidget#SetupNav {{ background: {card}; border: 1px solid {edge}; border-radius: 18px; padding: 6px; }}
QListWidget#SetupNav::item {{ padding: 8px 10px; margin: 1px 0; border-radius: 11px; border-left: 3px solid transparent; }}
QListWidget#SetupNav::item:selected {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {t.soft(a1, 0.28)},
    stop:1 {t.soft(a2, 0.10)}); border-left: 3px solid {a2}; font-weight: 700; }}

QTabWidget::pane {{ border: 1px solid {edge}; border-radius: 12px; top: -1px; background: {t.surface}; }}
QTabBar::tab {{ background: transparent; padding: 8px 14px; margin-right: 4px; border-radius: 9px; color: {t.muted}; }}
QTabBar::tab:selected {{ background: {t.soft(a1, 0.22)}; color: {t.text}; border-bottom: 2px solid {a2}; }}

QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 9px; margin: 3px; }}
QScrollBar::handle:vertical {{ background: {t.border}; border-radius: 4px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {a1}; }}
QScrollBar:horizontal {{ background: transparent; height: 9px; margin: 3px; }}
QScrollBar::handle:horizontal {{ background: {t.border}; border-radius: 4px; min-width: 30px; }}
QScrollBar::handle:horizontal:hover {{ background: {a1}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: none; }}

QSlider::groove:horizontal {{ height: 6px; background: {t.surface2}; border-radius: 3px; }}
QSlider::sub-page:horizontal {{ background: {grad_h}; border-radius: 3px; }}
QSlider::handle:horizontal {{ background: #ffffff; border: 2px solid {a2}; width: 14px; height: 14px;
    margin: -6px 0; border-radius: 9px; }}

QProgressBar {{ background: {t.surface2}; border: none; border-radius: 5px; height: 10px; text-align: center; }}
QProgressBar::chunk {{ background: {grad_h}; border-radius: 5px; }}

QMenu {{ background: {t.surface}; border: 1px solid {edge}; border-radius: 12px; padding: 6px; }}
QMenu::item {{ padding: 7px 26px 7px 12px; border-radius: 8px; }}
QMenu::item:selected {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {t.soft(a1, 0.30)},
    stop:1 {t.soft(a2, 0.14)}); }}
QMenu::item:disabled {{ color: {t.muted}; }}
QMenu::separator {{ height: 1px; background: {t.border}; margin: 5px 8px; }}

QStatusBar {{ background: transparent; color: {t.muted}; }}
QMessageBox, QInputDialog, QColorDialog, QFileDialog {{ background: {t.bg}; }}
"""
