"""Farbschema (dunkel/hell, Akzentfarbe) und Stylesheet für die ganze Oberfläche."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication, QPalette

ACCENTS = {
    "alupc": ("AluPC", "#0a84ff"),  # eigenes Theme (docs/DESIGN.md) – Windows und Linux gleich
    "system": ("Wie das System", "#3b82f6"),  # Farbe kommt aus Windows/KDE (system_accent)
    "blau": ("Blau", "#3b82f6"),
    "violett": ("Violett", "#8b5cf6"),
    "gruen": ("Grün", "#10b981"),
    "orange": ("Orange", "#f59e0b"),
    "rosa": ("Rosa", "#ec4899"),
    "eigen": ("Eigene Farbe", "#5b8cff"),  # Farbe aus appearance["accent_color"]
}
DENSITIES = {"kompakt": ("Kompakt", 0.85), "normal": ("Normal", 1.0), "luftig": ("Luftig", 1.15)}
# Fertige Profile (Setup → Darstellung → Profil); eigene Profile kommen dazu (appearance["profiles"])
BUILTIN_PROFILES = {
    "AluPC Standard": {"style": "normal", "mode": "dunkel", "accent": "alupc", "radius": 100, "font": 100,
                       "density": "normal"},
    "Hell & rund": {"style": "normal", "mode": "hell", "accent": "alupc", "radius": 140, "font": 100,
                    "density": "luftig"},
    "Werkstatt": {"style": "technisch", "mode": "dunkel", "accent": "alupc", "radius": 100, "font": 95,
                  "density": "kompakt"},
    "Wohnzimmer": {"style": "holz", "wood": "nussbaum", "accent": "alupc", "radius": 100, "font": 105,
                   "density": "normal"},
    "Werkbank Eiche": {"style": "holz", "wood": "eiche", "accent": "alupc", "radius": 100, "font": 100,
                       "density": "normal"},
}
PROFILE_KEYS = ("style", "mode", "wood", "accent", "accent_color", "radius", "font", "density")
MODES = {"system": "Wie das System", "dunkel": "Dunkel", "hell": "Hell"}
# Drei Gestaltungen (docs/DESIGN.md), frei umschaltbar unter Setup → Darstellung
STYLES = {"normal": "Normal", "technisch": "Technisch", "holz": "Holz", "matrix": "Matrix"}
STYLE_INFO = {"normal": "Modern, weich und rund",
              "technisch": "Dicht, mit Messwerten",
              "holz": "Echtes Furnier, 7 Holzarten",
              "matrix": "Grüner Code auf Schwarz"}
# Anzeigen auf Monitor 2 (Abstimmung, Glücksrad, Codes …): ruhiger, dunkler Grund
STAGE_BG = "#121315"
STAGE_PANEL = "#1c1d20"


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
    accent2: str = ""  # zweite Farbe für Verläufe (z. B. Begrüßung); leer = wie accent
    danger: str = "#ef4444"
    warning: str = "#f59e0b"
    success: str = "#22c55e"
    live: str = "#e5484d"  # „läuft auf dem Bildschirm“ – nur dafür
    ready: str = "#30a46c"  # bereit / verbunden
    style: str = "normal"  # siehe STYLES
    wood_kind: str = "nussbaum"  # Holzart im Holz-Stil (siehe WOODS)
    radius_scale: float = 1.0  # Rundung: 0 = eckig, 1 = wie der Stil, 2 = doppelt so rund
    font_scale: float = 1.0    # Schriftgröße (0.85–1.3)
    density: float = 1.0       # Abstände: 0.85 kompakt, 1 normal, 1.15 luftig

    def __post_init__(self):
        if not self.accent2:
            self.accent2 = self.accent

    @property
    def technical(self) -> bool:
        """Technisch und Matrix: Pads, Messwerte, Ziffernschrift (Matrix ist eine grüne Spielart davon)."""
        return self.style in ("technisch", "matrix")

    @property
    def matrix(self) -> bool:
        return self.style == "matrix"

    @property
    def kind(self) -> str:
        """Form der Bausteine: normal / technisch / holz (Matrix baut wie Technisch)."""
        return "technisch" if self.technical else self.style

    @property
    def wood(self) -> bool:
        return self.style == "holz"

    @property
    def on_accent(self) -> str:
        """Schrift/Symbol auf Akzentflächen: auf Signalgelb und Messing dunkel, sonst weiß."""
        c = QColor(self.accent)
        lum = 0.2126 * c.redF() + 0.7152 * c.greenF() + 0.0722 * c.blueF()
        return "#16171a" if lum > 0.45 else "#ffffff"

    @property
    def head_font(self) -> str:
        """Schrift für Titel und Kachelnamen: Holz wie Gravur auf Geräten (Barlow), sonst Inter."""
        return WOOD_FONT if self.wood else (MONO_FONT if self.matrix else UI_FONT)

    @property
    def radii(self) -> tuple[int, int, int, int]:
        """Rundung: Karte, Knopf, Eingabefeld, Listenzeile."""
        base = {"technisch": (3, 3, 2, 2), "holz": (6, 5, 4, 4)}.get(self.kind, (20, 17, 12, 10))
        return tuple(max(0, round(r * self.radius_scale)) for r in base)

    def pt(self, size: float) -> float:
        """Schriftgröße mit dem eingestellten Faktor."""
        return round(size * self.font_scale, 2)

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


def from_appearance(a: dict) -> Theme:
    """Theme aus den gespeicherten Einstellungen (appearance) – inkl. eigener Farbe, Rundung, Schrift, Abständen."""
    return make_theme(a.get("mode", "system"), a.get("accent", "alupc"), a.get("style", "normal"),
                      a.get("wood", DEFAULT_WOOD), custom=a)


def make_theme(mode: str = "system", accent: str = "blau", style: str = "normal", wood: str = "nussbaum",
               custom: dict | None = None) -> Theme:
    t = _make_theme(mode, accent, style, wood, custom or {})
    c = custom or {}
    t.radius_scale = max(0.0, min(2.5, float(c.get("radius", 100)) / 100))
    t.font_scale = max(0.8, min(1.4, float(c.get("font", 100)) / 100))
    t.density = DENSITIES.get(c.get("density", "normal"), DENSITIES["normal"])[1]
    return t


def _make_theme(mode: str, accent: str, style: str, wood: str, custom: dict) -> Theme:
    """Drei Gestaltungen (docs/DESIGN.md), jede hell und dunkel:
    normal – ruhiges Grau, runde Ecken; technisch – Mittelgrau, Signalgelb, dichte Zeilen, Messwerte;
    holz – Furnier der gewählten Holzart, Messing als Akzent; ob hell oder dunkel, bestimmt das Holz
    (dunkles Holz → helle Schrift). Rot (live) zeigt in allen dreien, was gerade auf dem Bildschirm läuft."""
    style = style if style in STYLES else "normal"
    wood = wood if wood in WOODS else DEFAULT_WOOD
    dark = WOODS[wood][5] if style == "holz" else (system_prefers_dark() if mode == "system" else mode == "dunkel")
    key = accent if accent in ACCENTS else "alupc"
    own = {"normal": ("#5b8cff", "#2f62e9"), "technisch": ("#f5c400", "#c99a00"),
           "holz": ("#e0b354", "#8a5a12"), "matrix": ("#00ff66", "#00ff66")}[style]
    if style == "matrix":
        dark = True  # Matrix gibt es nur dunkel
    if key == "alupc":
        accent_hex = own[0] if dark else own[1]
    elif key == "system":
        accent_hex = system_accent()
    elif key == "eigen":
        accent_hex = QColor(custom.get("accent_color") or ACCENTS["eigen"][1]).name()
    else:
        accent_hex = ACCENTS[key][1]
    if style == "matrix":  # Phosphorgrün auf Schwarz
        return Theme(True, accent_hex, bg="#010403", surface="#04110a", surface2="#082016", border="#0f3a22",
                     text="#c8ffd8", muted="#6fd394", danger="#ff5c5c", live="#ff3b3b", ready="#00ff66",
                     style=style)
    if style == "technisch":
        if dark:
            return Theme(True, accent_hex, bg="#18191b", surface="#202124", surface2="#292a2e", border="#36383d",
                         text="#e8e8e5", muted="#969a9f", danger="#ff5c4d", live="#ff4433", ready="#3ecf6e",
                         style=style)
        return Theme(False, accent_hex, bg="#e6e6e2", surface="#f7f7f5", surface2="#ededea", border="#c8c9c4",
                     text="#17181a", muted="#5b5e63", danger="#d62f1f", live="#e0291a", ready="#178a3e", style=style)
    if style == "holz":
        bg, panel, panel_hi = wood_color(wood, "bg"), wood_color(wood, "panel"), wood_color(wood, "panel_hi")
        if dark:
            return Theme(True, accent_hex, bg=bg, surface=panel, surface2=panel_hi, border="#120b06",
                         text="#f4ede2", muted="#d3c7b6", danger="#ff6a55", live="#ff3b2f", ready="#57d163",
                         style=style, wood_kind=wood)
        return Theme(False, accent_hex, bg=bg, surface=panel, surface2=panel_hi, border="#5e4026",
                     text="#1c150e", muted="#3f3328", danger="#b3200f", live="#e3261b", ready="#1f7a34",
                     style=style, wood_kind=wood)
    if dark:
        return Theme(True, accent_hex, bg="#131417", surface="#1e2024", surface2="#2a2d33", border="#30333a",
                     text="#f2f3f5", muted="#9aa0aa", danger="#ff5f57", live="#ff4f45", ready="#30d158", style=style)
    return Theme(False, accent_hex, bg="#eceef2", surface="#ffffff", surface2="#f1f2f5", border="#e1e4e9",
                 text="#16181c", muted="#5f6670", danger="#dc3226", live="#e0352b", ready="#248a3d", style=style)


# ------------------------------------------------------------------ Holz: Maserung und Aluminiumplatten
# Holzarten: Name, Grundfarbe, dunkle Fasern, helle Fasern, Maserung, dunkles Holz (→ helle Schrift)
WOODS = {
    "nussbaum": ("Nussbaum", "#5b3b26", "#2c1a0e", "#7d5435", "fluss", True),
    "kirsche": ("Kirsche", "#8e4a2c", "#5c2914", "#ad6542", "flamme", True),
    "wenge": ("Wenge", "#3b2b21", "#120c08", "#5f4838", "streifen", True),
    "raeuchereiche": ("Räuchereiche", "#5c4838", "#30241a", "#7a634e", "poren", True),
    "eiche": ("Eiche", "#bd8f58", "#8a5d30", "#d6ab72", "poren", False),
    "kiefer": ("Kiefer", "#d4a468", "#a46c34", "#e6bf88", "jahresringe", False),
    "ahorn": ("Ahorn", "#dcc29a", "#b8976a", "#efdcbc", "fein", False),
}
DEFAULT_WOOD = "nussbaum"
_wood: dict = {}


def _wood_raw(species: str):
    """Rohes Furnierbild einer Holzart (nahtlos kachelbar, längs gemasert, immer gleich)."""
    key = ("raw", species)
    if key in _wood:
        return _wood[key]
    import math
    import random

    from PySide6.QtCore import QPointF, QRectF
    from PySide6.QtGui import QImage, QPainter, QPainterPath, QPen

    _name, base, deep, light, figure, _dark = WOODS.get(species, WOODS[DEFAULT_WOOD])
    w, h = 720, 480
    img = QImage(w, h, QImage.Format_RGB32)
    img.fill(QColor(base))
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    rnd = random.Random(sum(map(ord, species)) * 31 + 7)
    band_min, band_max, band_alpha = {"streifen": (2, 7, (0.25, 0.5)), "jahresringe": (6, 22, (0.15, 0.35)),
                                      "fein": (8, 34, (0.04, 0.10))}.get(figure, (5, 30, (0.06, 0.2)))
    y = 0.0
    while y < h:  # Jahresringe als Bänder
        band = rnd.uniform(band_min, band_max)
        c = QColor(deep if rnd.random() < 0.55 else light)
        c.setAlphaF(rnd.uniform(*band_alpha))
        p.fillRect(QRectF(0, y, w, band), c)
        y += band
    amp_max = {"flamme": 9.0, "fluss": 5.0, "jahresringe": 3.0, "fein": 1.5, "streifen": 1.2}.get(figure, 3.0)
    count = {"fein": 140, "streifen": 320, "flamme": 220}.get(figure, 260)
    for _ in range(count):  # Fasern: Wellen, die über die Bildbreite genau aufgehen (nahtlos)
        y0 = rnd.uniform(0, h)
        amp = rnd.uniform(0.3, amp_max)
        k = rnd.choice((1, 1, 2, 3))
        phase = rnd.uniform(0, math.tau)
        c = QColor(deep if rnd.random() < 0.7 else light)
        c.setAlphaF(rnd.uniform(0.10, 0.38 if figure != "fein" else 0.22))
        p.setPen(QPen(c, rnd.uniform(0.35, 1.4)))
        for off in (-h, 0, h):
            path = QPainterPath(QPointF(0, y0 + off + amp * math.sin(phase)))
            for x in range(8, w + 8, 8):
                path.lineTo(x, y0 + off + amp * math.sin(math.tau * k * x / w + phase))
            p.drawPath(path)
    if figure == "poren":  # Eiche: kurze, dunkle Porenstriche
        for _ in range(2200):
            x, y_ = rnd.uniform(0, w), rnd.uniform(0, h)
            c = QColor(deep)
            c.setAlphaF(rnd.uniform(0.2, 0.5))
            p.setPen(QPen(c, rnd.uniform(0.6, 1.1)))
            ln = rnd.uniform(2, 11)
            p.drawLine(QPointF(x, y_), QPointF(x + ln, y_))
            if x + ln > w:
                p.drawLine(QPointF(x - w, y_), QPointF(x - w + ln, y_))
    p.end()
    _wood[key] = img
    return img


def _luminance(c: QColor) -> float:
    return 0.2126 * c.redF() + 0.7152 * c.greenF() + 0.0722 * c.blueF()


def _average(img) -> QColor:
    from PySide6.QtCore import Qt as _Qt

    return QColor(img.scaled(1, 1, _Qt.IgnoreAspectRatio, _Qt.SmoothTransformation).pixel(0, 0))


# Helligkeit (Luminanz), die jede Fläche erreicht – so bleibt Schrift auf jeder Holzart lesbar
_WOOD_TARGETS = {True: {"bg": 0.075, "side": 0.05, "panel": 0.13, "panel_hi": 0.16, "panel_lo": 0.095},
                 False: {"bg": 0.64, "side": 0.70, "panel": 0.80, "panel_hi": 0.84, "panel_lo": 0.72}}


def wood_image(species: str = DEFAULT_WOOD, part: str = "bg"):
    """Holzfläche: bg (Fenstergrund), side (Seitenleiste), panel/panel_hi/panel_lo (Furnierplatte normal/
    Maus darüber/gedrückt). Aufgehellt oder abgedunkelt, bis die Fläche die Ziel-Helligkeit hat."""
    species = species if species in WOODS else DEFAULT_WOOD
    key = (species, part)
    if key in _wood:
        return _wood[key]
    from PySide6.QtGui import QPainter

    raw = _wood_raw(species)
    dark = WOODS[species][5]
    target = _WOOD_TARGETS[dark][part]
    lum = _luminance(_average(raw))
    img = raw.copy()
    if abs(lum - target) > 0.005:
        p = QPainter(img)
        if target < lum:
            p.fillRect(img.rect(), QColor(0, 0, 0, int(255 * min(0.92, 1 - target / max(lum, 0.001)))))
        else:
            p.fillRect(img.rect(), QColor(255, 255, 255, int(255 * min(0.9, (target - lum) / max(1 - lum, 0.001)))))
        p.end()
    _wood[key] = img
    return img


def wood_file(species: str = DEFAULT_WOOD, part: str = "bg") -> str:
    """Holzfläche als Datei (für das Stylesheet), im Temp-Ordner zwischengespeichert."""
    import tempfile
    from pathlib import Path

    path = Path(tempfile.gettempdir()) / f"alupc-holz-v4-{species}-{part}.png"
    try:
        if not path.exists():
            wood_image(species, part).save(str(path))
        return path.as_posix()
    except OSError:
        return ""


def wood_jpeg(species: str = DEFAULT_WOOD, part: str = "bg") -> bytes:
    """Holzfläche als JPEG-Bytes (Handy-Seite)."""
    from PySide6.QtCore import QBuffer, QIODevice

    buf = QBuffer()
    buf.open(QIODevice.WriteOnly)
    wood_image(species, part).save(buf, "JPG", 82)
    return bytes(buf.data())


def wood_color(species: str, part: str = "bg") -> str:
    return _average(wood_image(species, part)).name()


def brushed_image():
    """Feine Längsstriche wie gebürstetes Aluminium (halbdurchsichtig, kachelbar) – für Reglerkappen."""
    if "brushed" in _wood:
        return _wood["brushed"]
    import random

    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QImage, QPainter, QPen

    w, h = 240, 80
    img = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
    img.fill(Qt.transparent)
    p = QPainter(img)
    rnd = random.Random(42)
    for _ in range(300):
        y = rnd.uniform(0, h)
        x = rnd.uniform(0, w)
        length = rnd.uniform(30, 200)
        c = QColor(255, 255, 255) if rnd.random() < 0.5 else QColor(0, 0, 0)
        c.setAlphaF(rnd.uniform(0.01, 0.035))
        p.setPen(QPen(c, 0.6))
        for off in (-w, 0):
            p.drawLine(QPointF(x + off, y), QPointF(x + off + length, y))
    p.end()
    _wood["brushed"] = img
    return img


def plate_colors(t: Theme) -> tuple[str, str, str, str]:
    """Aluminiumplatte: oben, unten, Lichtkante oben, Schattenkante unten."""
    if t.dark:
        return "#4a4d52", "#393c40", "#5d6166", "#1c1d1f"
    return "#f1f2f3", "#d9dbdd", "#ffffff", "#8e9195"


def paint_backdrop(p, rect, t: Theme | None = None, part: str = "bg") -> None:
    """Fenstergrund: im Holz-Stil die Maserung (part „side“ = dunklere Seitenleiste), sonst die Grundfarbe."""
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QPixmap

    t = t or current()
    if t.wood:
        p.drawTiledPixmap(rect, QPixmap.fromImage(wood_image(t.wood_kind, part)), QPointF(rect.left(), rect.top()))
    else:
        p.fillRect(rect, QColor(t.bg))


def paint_panel(p, path, rect, t: Theme | None = None, pressed: bool = False, hover: float = 0.0) -> None:
    """Furnierplatte (Holz-Stil): Maserung der Holzart, helle Kante oben, dunkle Fuge rundherum."""
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QPen, QPixmap

    t = t or current()
    part = "panel_lo" if pressed else ("panel_hi" if hover > 0.5 else "panel")
    p.save()
    p.setClipPath(path)
    p.drawTiledPixmap(rect, QPixmap.fromImage(wood_image(t.wood_kind, part)), QPointF(rect.left() * 0.7, rect.top()))
    hi = QColor(255, 255, 255, 46 if t.dark else 120)
    p.setPen(QPen(hi, 1))
    p.drawLine(QPointF(rect.left() + 2, rect.top() + 0.5), QPointF(rect.right() - 2, rect.top() + 0.5))
    p.restore()
    p.setPen(QPen(QColor(0, 0, 0, 150 if t.dark else 90), 1))
    p.setBrush(Qt.NoBrush)
    p.drawPath(path)


def paint_plate(p, path, rect, t: Theme | None = None, pressed: bool = False, hover: float = 0.0) -> None:
    """Gebürstetes Aluminium (Holz-Stil: Reglerkappen): senkrechter Verlauf, helle Kante oben, dunkle unten."""
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QLinearGradient, QPen

    t = t or current()
    top, bottom, hi, lo = plate_colors(t)
    if pressed:
        top, bottom = bottom, top
    g = QLinearGradient(rect.topLeft(), rect.bottomLeft())
    g.setColorAt(0, t.mix(top, "#ffffff", 0.06 * hover))
    g.setColorAt(1, t.mix(bottom, "#ffffff", 0.06 * hover))
    p.fillPath(path, g)
    p.save()
    p.setClipPath(path)
    from PySide6.QtGui import QPixmap

    p.drawTiledPixmap(rect, QPixmap.fromImage(brushed_image()))
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(QColor(hi), 1))
    p.drawLine(QPointF(rect.left() + 2, rect.top() + 0.5), QPointF(rect.right() - 2, rect.top() + 0.5))
    p.restore()
    p.setPen(QPen(QColor(lo), 1))
    p.setBrush(Qt.NoBrush)
    p.drawPath(path)


def current() -> Theme:
    global _current
    if _current is None:
        _current = make_theme()
    return _current


_fonts_loaded = False
UI_FONT = "Inter"
HEAD_FONT = "Inter"  # Anzeigen auf Monitor 2 (Abstimmung, Glücksrad …)
WOOD_FONT = "Barlow Semi Condensed"  # Holz-Stil: Titel und Kachelnamen
MONO_FONT = "JetBrains Mono"  # nur Zahlen/Messwerte im technischen Stil


def load_fonts(app) -> bool:
    """Mitgelieferte Schriften laden (Inter, Barlow, JetBrains Mono) – damit AluPC unter Windows und Linux gleich aussieht.
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


def apply_appearance(app, a: dict) -> Theme:
    """Alle Darstellungs-Einstellungen anwenden (Stil, Farbe, Rundung, Schrift, Abstände)."""
    return apply(app, a.get("mode", "system"), a.get("accent", "alupc"), a.get("style", "normal"),
                 a.get("wood", DEFAULT_WOOD), custom=a)


def apply(app, mode: str = "system", accent: str = "blau", style: str = "normal", wood: str = "nussbaum",
          custom: dict | None = None) -> Theme:
    """Farbschema auf die ganze Anwendung anwenden (auch nachträglich)."""
    global _current, _sys_highlight, _sys_window
    load_fonts(app)
    if not _sys_highlight:
        _sys_highlight = app.palette().color(QPalette.Highlight).name()
        _sys_window = app.palette().color(QPalette.Window).name()
    t = _current = make_theme(mode, accent, style, wood, custom)
    if _fonts_loaded:  # Grundschrift mit Faktor (Schriftgröße)
        from PySide6.QtGui import QFont

        # Grundschrift bleibt Inter (auch Monitor 2 zeichnet damit); Matrix setzt die Ziffernschrift per Stylesheet
        base = QFont(UI_FONT)
        base.setPointSizeF(10 * t.font_scale)
        base.setHintingPreference(QFont.PreferNoHinting)
        app.setFont(base)
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


def stylesheet(t: Theme, check_image: str = "", arrow_image: str = "") -> str:
    """Stylesheet; alle Schriftgrößen mit dem eingestellten Faktor (Setup → Darstellung → Schriftgröße)."""
    import re

    css = _stylesheet(t, check_image, arrow_image)
    if abs(t.font_scale - 1.0) < 0.001:
        return css
    return re.sub(r"font-size:\s*([\d.]+)pt", lambda m: f"font-size: {float(m.group(1)) * t.font_scale:.2f}pt", css)


def _stylesheet(t: Theme, check_image: str = "", arrow_image: str = "") -> str:
    """Stylesheet für alle drei Gestaltungen (docs/DESIGN.md). Gemeinsam: feine Ränder statt Schatten,
    Fokus/Auswahl in der Akzentfarbe. Unterschiede: Rundungen, Flächen (flach / Alu-Platten auf Holz), Schrift."""
    a1 = t.accent
    rc, rb, rf, rs = t.radii
    on_accent = t.on_accent
    head = f'font-family: "{t.head_font}";'
    hover = t.mix(t.surface2, t.text, 0.06).name()
    pressed = t.mix(t.surface2, t.text, 0.12).name()
    line = t.border
    line_hi = t.mix(line, t.text, 0.22).name()
    sel = t.soft(a1, 0.18 if t.dark else 0.12)
    field = t.mix(t.bg, t.surface, 0.5).name() if t.dark else "#ffffff"
    number_font = f'font-family: "{MONO_FONT}";' if t.technical else ""
    title_pt, title_w = {"technisch": (19, 600), "holz": (25, 600)}.get(t.kind, (22, 700))
    group_pt = 13.5 if t.wood else 11.5
    window_bg = t.bg
    side = t.mix(t.bg, "#000000", 0.18).name() if t.dark else t.mix(t.bg, "#ffffff", 0.5).name()
    card = f"background: {t.surface};"
    btn = f"background: {t.surface2};"
    btn_hover = f"background: {hover};"
    btn_down = f"background: {pressed};"
    page_icon = f"background: {a1}; border: none;"
    card_line = line  # Rand von Karten/Gruppen
    btn_line = line   # Rand von Knöpfen
    extra = ""
    rcmd = rf  # Befehlsleiste
    if t.style == "normal":  # modern: weiche Flächen ohne harte Ränder, Knöpfe als Pillen, Seitenleiste schwebt
        card_line = btn_line = "transparent"
        side = t.surface
        hover = t.mix(t.surface2, t.text, 0.08).name()
        pressed = t.mix(t.surface2, t.text, 0.14).name()
        btn_hover = f"background: {hover};"
        btn_down = f"background: {pressed};"
        hero_tint = t.mix(t.surface, a1, 0.16 if t.dark else 0.08).name()
        rcmd = min(23, round(23 * t.radius_scale))
        dialog_top = t.mix(t.bg, a1, 0.10 if t.dark else 0.06).name()
        extra = f"""
#Hero {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {t.surface}, stop:1 {hero_tint}); }}
#Sidebar {{ margin: 12px 0 12px 12px; border-radius: 22px; border: none; }}
QDialog {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {dialog_top}, stop:0.45 {t.bg}); }}
#LiveDock {{ margin: 12px 12px 12px 0; border-radius: 22px; border: none; }}
QPushButton#CommandBar {{ background: {t.surface}; border-color: transparent; }}
QPushButton {{ padding: 7px 16px; }}
QPushButton#Chip {{ border-radius: 16px; padding: 6px 14px; }}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{ background: {t.surface2}; border-color: transparent; }}
QLineEdit:hover, QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover {{ border-color: {line_hi}; }}
QGroupBox {{ padding: 20px 18px 16px 18px; }}
QMenu {{ border-radius: 14px; padding: 6px; }}
QMenu::item {{ border-radius: 9px; }}
QListWidget {{ border-color: transparent; }}
QListWidget#SetupNav {{ border-color: transparent; padding: 6px; }}
QListWidget#SetupNav::item {{ border-left: none; border-radius: 12px; }}
QListWidget#SetupNav::item:selected {{ border-left: none; }}
"""
    matrix_extra = ""
    if t.matrix:
        matrix_extra = f"""
QWidget {{ font-family: "{MONO_FONT}"; }}
#Output, #Output QWidget {{ font-family: "{UI_FONT}"; }}
#PageTitle, #PanelTitle, #Brand {{ color: {a1}; }}
#Sidebar, #LiveDock {{ border-color: {line}; }}
QPushButton[primary="true"] {{ background: {a1}; color: #001a09; }}
QLineEdit, QComboBox, QSpinBox {{ background: #000000; border-color: {line}; }}
QLineEdit:focus, QComboBox:focus {{ border-color: {a1}; }}
"""
    if t.technical:
        side = t.surface
        page_icon = f"background: transparent; border: 1px solid {line_hi};"
        extra = f"""
#Card, QGroupBox, #Hero {{ border-top: 2px solid {a1}; }}
#LiveDock {{ border-top: 2px solid {a1}; }}
QPushButton#Chip {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {t.mix(t.surface2, "#ffffff", 0.06).name()},
    stop:1 {t.mix(t.surface, "#000000", 0.15).name()}); border: 1px solid {line}; border-bottom: 2px solid {t.mix(t.bg, "#000000", 0.4).name()}; }}
QPushButton#Chip:checked {{ background: {a1}; color: {on_accent}; border-color: {a1}; border-bottom-color: {t.mix(a1, "#000000", 0.35).name()}; }}
QPushButton#Chip:pressed {{ border-bottom-width: 1px; padding-top: 6px; }}
{matrix_extra}
QDialog {{ border-top: 2px solid {a1}; }}
#DockTitle {{ font-family: "{MONO_FONT}"; font-weight: 600; border-left: 3px solid {a1}; padding-left: 7px; }}
"""
    if t.wood:
        def img(part: str) -> str:
            f = wood_file(t.wood_kind, part)
            return f'background-image: url("{f}");' if f else ""
        hi = "rgba(255,255,255,0.18)" if t.dark else "rgba(255,255,255,0.55)"
        card = f"background-color: {t.surface}; {img('panel')}"
        btn = card
        btn_hover = f"background-color: {t.surface2}; {img('panel_hi')}"
        btn_down = f"background-color: {t.surface}; {img('panel_lo')}"
        page_icon = f"background-color: {t.surface}; {img('panel')} border: 1px solid {t.border};"
        line, line_hi = t.border, t.mix(t.border, t.text, 0.35).name()
        field = t.mix(t.bg, "#000000", 0.35).name() if t.dark else t.mix(t.surface, "#ffffff", 0.6).name()
        window_bg = f"{t.bg}; {img('bg')}"
        side = f"{t.bg}; {img('side')}"
        brass_hi = t.mix(a1, "#ffffff", 0.25).name()
        brass_lo = t.mix(a1, "#000000", 0.18).name()
        extra = f"""
QPushButton[primary="true"] {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {brass_hi}, stop:1 {a1});
    border: 1px solid {brass_lo}; }}
QPushButton[primary="true"]:pressed {{ background: {brass_lo}; }}
QListWidget, QMenu, QComboBox QAbstractItemView, QComboBoxPrivateContainer {{ background-color: {t.surface}; }}
#Card, QGroupBox, #Hero, QPushButton {{ border-top-color: {hi}; }}
"""
    return f"""
* {{ outline: none; }}
QWidget {{ color: {t.text}; }}
QMainWindow, QDialog {{ background: {window_bg}; }}
QToolTip {{ background: {t.surface2}; color: {t.text}; border: 1px solid {line_hi}; border-radius: {rb}px; padding: 5px 8px; }}

#Sidebar {{ background: {side}; border-right: 1px solid {line}; }}
#Content {{ background: transparent; }}
#PageIcon, #SectionIcon {{ {page_icon} border-radius: {rb}px; }}
#Brand {{ {head} font-size: 13.5pt; font-weight: 700; }}
#BrandSub {{ color: {t.muted}; font-size: 8.5pt; }}
#Muted, QLabel[muted="true"] {{ color: {t.muted}; }}
#PageTitle {{ {head} font-size: {title_pt}pt; font-weight: {title_w}; }}
#PanelTitle {{ {head} font-size: 15pt; font-weight: 700; }}
#PageSubtitle {{ color: {t.muted}; font-size: 9.5pt; }}
#SectionTitle {{ {head} font-size: {group_pt}pt; font-weight: 600; }}
#StartSection {{ font-size: 11pt; font-weight: 600; color: {t.text}; padding: 10px 0 4px 0; border-bottom: 1px solid {line}; }}

#Card, QGroupBox, #Hero {{ {card} border: 1px solid {card_line}; border-radius: {rc}px; }}
QPushButton#Chip {{ border-radius: {rb}px; padding: 5px 11px; {btn} border: 1px solid {line}; font-weight: 600; }}
QPushButton#Chip:hover {{ border-color: {line_hi}; }}
QPushButton#Chip:checked {{ background: {sel}; border-color: {a1}; color: {t.text}; }}
QGroupBox {{ margin-top: 30px; padding: 16px 14px 12px 14px; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 0px; top: 6px; padding: 0 2px; color: {t.text};
                   {head} font-size: {group_pt}pt; font-weight: 600; }}

QPushButton, QToolButton#Plain {{
    {btn} border: 1px solid {btn_line}; border-radius: {rb}px; padding: 6px 13px; min-height: 20px;
    font-weight: 600; }}
QPushButton:hover, QToolButton#Plain:hover {{ {btn_hover} border-color: {line_hi}; }}
QPushButton:pressed {{ {btn_down} }}
QPushButton:disabled {{ color: {t.muted}; background: {t.surface}; }}
QPushButton[primary="true"] {{ background: {a1}; border: 1px solid {a1}; color: {on_accent}; font-weight: 700; }}
QPushButton[primary="true"]:hover {{ background: {t.mix(a1, "#ffffff", 0.12).name()}; }}
QPushButton[primary="true"]:pressed {{ background: {t.mix(a1, "#000000", 0.12).name()}; }}
QPushButton[primary="true"]:disabled {{ background: {t.surface2}; border-color: {line}; color: {t.muted}; }}
QPushButton[danger="true"] {{ color: {t.danger}; }}
QPushButton[danger="true"]:hover {{ border-color: {t.danger}; background: {t.soft(t.danger, 0.10)}; }}
QPushButton:default {{ border-color: {a1}; }}
QPushButton:checked {{ background: {sel}; border-color: {a1}; }}
QPushButton#Segment {{ border-radius: {rb}px; padding: 6px 15px; min-width: 56px; }}
QPushButton#Segment:checked {{ background: {sel}; border-color: {a1}; }}

QLineEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox, QKeySequenceEdit QLineEdit {{
    background: {field}; border: 1px solid {line}; border-radius: {rf}px; padding: 6px 8px;
    selection-background-color: {a1}; selection-color: {on_accent}; }}
QLineEdit:hover, QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover {{ border-color: {line_hi}; }}
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{ border-color: {a1}; }}
QSpinBox, QDoubleSpinBox {{ {number_font} }}
QComboBox {{ padding-right: 30px; combobox-popup: 0; }}
QComboBox::drop-down {{ subcontrol-origin: padding; subcontrol-position: center right; border: none; width: 28px; }}
QComboBox::down-arrow {{ {f'image: url("{arrow_image}");' if arrow_image else ''} width: 14px; height: 14px; }}
QComboBox::down-arrow:on {{ top: 1px; }}
QComboBoxPrivateContainer {{ background: {t.surface}; border: 1px solid {line_hi}; }}
QComboBox QAbstractItemView {{ background: {t.surface}; border: none; padding: 3px; outline: 0;
    selection-background-color: transparent; selection-color: {t.text}; }}
QComboBox QAbstractItemView::item {{ min-height: 28px; padding: 2px 9px; border-radius: {rs}px; margin: 0; }}
QComboBox QAbstractItemView::item:hover {{ background: {hover}; }}
QComboBox QAbstractItemView::item:selected {{ background: {sel}; color: {t.text}; }}
QSpinBox::up-button, QSpinBox::down-button, QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
    width: 18px; border: none; }}

QCheckBox, QRadioButton {{ spacing: 9px; }}
QRadioButton::indicator {{ width: 15px; height: 15px; border-radius: 8px; border: 1px solid {line_hi}; background: {field}; }}
QRadioButton::indicator:checked {{ background: {a1}; border: 4px solid {field}; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: {rs}px; border: 1px solid {line_hi}; background: {field}; }}
QCheckBox::indicator:hover {{ border-color: {a1}; }}
QCheckBox::indicator:checked {{ background: {a1}; border-color: {a1};
    {f'image: url("{check_image}");' if check_image else ''} }}

QListWidget {{ background: {t.surface}; border: 1px solid {line}; border-radius: {rc}px; padding: 3px; }}
QListWidget::item {{ padding: 7px 8px; border-radius: {rs}px; }}
QListWidget::item:hover {{ background: {hover}; }}
QListWidget::item:selected {{ background: {sel}; color: {t.text}; }}
QListWidget::indicator, QTreeWidget::indicator {{ width: 16px; height: 16px; border-radius: {rs}px;
    border: 1px solid {line_hi}; background: {field}; }}
QListWidget::indicator:checked, QTreeWidget::indicator:checked {{ background: {a1}; border-color: {a1};
    {f'image: url("{check_image}");' if check_image else ''} }}
QListWidget#SetupNav {{ background: {t.surface}; border: 1px solid {line}; border-radius: {rc}px; padding: 4px; }}
QListWidget#SetupNav::item {{ padding: 8px 10px; margin: 0; border-radius: {rs}px; border-left: 2px solid transparent; }}
QListWidget#SetupNav::item:selected {{ background: {sel}; border-left: 2px solid {a1}; font-weight: 600; }}

QTabWidget::pane {{ border: 1px solid {line}; border-radius: {rc}px; top: -1px; background: {t.surface}; }}
QTabBar::tab {{ background: transparent; padding: 7px 14px; margin-right: 2px; color: {t.muted}; font-weight: 600;
    border-bottom: 2px solid transparent; }}
QTabBar::tab:hover {{ color: {t.text}; }}
QTabBar::tab:selected {{ color: {t.text}; border-bottom: 2px solid {a1}; }}

QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 8px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {line_hi}; border-radius: {rs}px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {t.muted}; }}
QScrollBar:horizontal {{ background: transparent; height: 8px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {line_hi}; border-radius: {rs}px; min-width: 30px; }}
QScrollBar::handle:horizontal:hover {{ background: {t.muted}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: none; }}

QSlider::groove:horizontal {{ height: 4px; background: {line}; border-radius: 1px; }}
QSlider::sub-page:horizontal {{ background: {a1}; border-radius: 1px; }}
QSlider::handle:horizontal {{ background: {t.surface2}; border: 1px solid {line_hi}; width: 10px; height: 20px;
    margin: -9px 0; border-radius: {rs}px; }}
QSlider::handle:horizontal:hover {{ border-color: {a1}; }}
QSlider::groove:vertical {{ width: 4px; background: {line}; border-radius: 1px; }}
QSlider::add-page:vertical {{ background: {a1}; border-radius: 1px; }}
QSlider::handle:vertical {{ background: {t.surface2}; border: 1px solid {line_hi}; height: 10px; width: 20px;
    margin: 0 -9px; border-radius: {rs}px; }}

QProgressBar {{ background: {line}; border: none; border-radius: 1px; height: 6px; text-align: center; }}
QProgressBar::chunk {{ background: {a1}; border-radius: 1px; }}

QMenu {{ background: {t.surface}; border: 1px solid {line_hi}; border-radius: {rc}px; padding: 4px; min-width: 230px; }}
QMenu::item {{ padding: 8px 28px 8px 10px; border-radius: {rs}px; margin: 0; }}
QMenu::item:selected {{ background: {sel}; color: {t.text}; }}
QMenu::item:disabled {{ color: {t.muted}; }}
QMenu::icon {{ padding-left: 8px; }}
QMenu::indicator {{ width: 15px; height: 15px; margin-left: 8px; border-radius: {rs}px; border: 1px solid {line_hi};
    background: {field}; }}
QMenu::indicator:checked {{ background: {a1}; border-color: {a1};
    {f'image: url("{check_image}");' if check_image else ''} }}
QMenu::separator {{ height: 1px; background: {line}; margin: 4px 6px; }}

QStatusBar {{ background: transparent; color: {t.muted}; }}
QMessageBox, QInputDialog, QColorDialog, QFileDialog {{ background: {window_bg}; }}

#LiveDock {{ background: {side}; border: none; border-left: 1px solid {line}; }}
#DockScroll, #DockInner {{ background: transparent; }}
#DockTitle {{ color: {t.muted}; font-size: 8.5pt; font-weight: 700; }}
#Hero[docked="true"] {{ background: transparent; border: none; }}
QPushButton#CommandBar {{ text-align: left; padding: 10px 16px; background: {field}; border: 1px solid {line};
    border-radius: {rcmd}px; color: {t.muted}; font-weight: 500; font-size: 10.5pt; }}
QPushButton#CommandBar:hover {{ border-color: {a1}; color: {t.text}; }}
QPushButton#CornerButton {{ padding: 0; border-radius: {min(rb, 18)}px; min-height: 0; }}
QLineEdit#SearchField {{ padding: 7px 10px; border-radius: {min(rcmd, 15)}px; }}
QGroupBox[notitle="true"] {{ margin-top: 0px; }}
{extra}"""
