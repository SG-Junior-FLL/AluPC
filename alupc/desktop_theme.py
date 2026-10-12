"""AluPC-Design auch für das System (freiwillig, mit „Zurück“) – Farben, Hell/Dunkel und Hintergrundbild.

* Farben – Linux/KDE: Farbschema „AluPC“ bzw. „AluPC Dunkel“ (aus der gewählten Akzentfarbe) nach
  ~/.local/share/color-schemes und mit plasma-apply-colorscheme anwenden. Windows: Akzentfarbe (Start, Taskleiste,
  Markierungen, Titelleisten).
* Hell/Dunkel – Windows: Apps und System hell oder dunkel. KDE: steckt im Farbschema, dazu der Plasma-Stil
  (Breeze bzw. Breeze Dunkel), falls plasma-apply-desktoptheme da ist.
* Hintergrundbild – AluPC malt eins in den Design-Farben (Bildschirmgröße) und setzt es (Windows:
  SystemParametersInfo, KDE: plasma-apply-wallpaperimage, GNOME: gsettings).
* Linux ohne KDE (GNOME, Ubuntu-Standard): über gsettings – Hell/Dunkel (color-scheme), Akzentfarbe (accent-color,
  ab GNOME 47 – die nächste der GNOME-Farben) und Hintergrundbild (hell + dunkel).
Vorher wird gemerkt, was eingestellt war – „Zurück“ stellt genau das wieder her. Ändert man in AluPC Akzentfarbe
oder Hell/Dunkel, zieht der Desktop mit (solange das Desktop-Design an ist).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

IS_WINDOWS = sys.platform.startswith("win")
SCHEMES = {False: "AluPC", True: "AluPCDunkel"}


def _state_file() -> Path:
    from .config import config_dir

    return config_dir() / "desktop-theme.json"


def _rgb(color: str) -> str:
    c = color.lstrip("#")
    return ",".join(str(int(c[i:i + 2], 16)) for i in (0, 2, 4))


def kde_scheme(dark: bool, accent: str = "alupc") -> str:
    """Inhalt der KDE-Farbschema-Datei aus dem AluPC-Theme (mit der gewählten Akzentfarbe)."""
    from .ui.theme import make_theme

    t = make_theme("dunkel" if dark else "hell", accent)

    def colors(bg, alt, fg):
        return {"BackgroundNormal": bg, "BackgroundAlternate": alt, "ForegroundNormal": fg,
                "ForegroundInactive": t.muted, "ForegroundActive": t.accent, "ForegroundLink": t.accent,
                "ForegroundVisited": t.accent2, "ForegroundNegative": t.danger, "ForegroundNeutral": t.warning,
                "ForegroundPositive": t.success, "DecorationFocus": t.accent, "DecorationHover": t.accent}

    sections = {
        "Colors:Window": colors(t.bg, t.surface2, t.text),
        "Colors:View": colors(t.surface, t.surface2, t.text),
        "Colors:Button": colors(t.surface2, t.surface, t.text),
        "Colors:Header": colors(t.bg, t.surface2, t.text),
        "Colors:Tooltip": colors(t.surface2, t.surface, t.text),
        "Colors:Complementary": colors("#0b0c1a", "#131429", "#eef0ff"),
        "Colors:Selection": {**colors(t.accent, t.accent2, "#ffffff"), "ForegroundInactive": "#e6e9ff"},
    }
    lines = []
    for name, values in sections.items():
        lines.append(f"[{name}]")
        lines += [f"{k}={_rgb(v)}" for k, v in values.items()]
        lines.append("")
    name = SCHEMES[dark]
    lines += ["[General]", f"ColorScheme={name}", f"Name={'AluPC Dunkel' if dark else 'AluPC'}", "shadeSortColumn=true",
              "", "[KDE]", "contrast=4", "",
              "[WM]", f"activeBackground={_rgb(t.bg)}", f"activeForeground={_rgb(t.text)}",
              f"inactiveBackground={_rgb(t.surface2)}", f"inactiveForeground={_rgb(t.muted)}",
              f"activeBlend={_rgb(t.accent)}", f"inactiveBlend={_rgb(t.surface2)}", ""]
    return "\n".join(lines)


def _kdeglobals() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "kdeglobals"


def _kde_current_scheme() -> str:
    import configparser

    cp = configparser.ConfigParser(interpolation=None, strict=False)
    try:
        cp.read(_kdeglobals(), encoding="utf-8")
        return cp.get("General", "ColorScheme", fallback="")
    except (OSError, configparser.Error):
        return ""


def _schemes_dir() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "color-schemes"


# ------------------------------------------------------------------ Windows
_ACCENT_KEYS = [(r"Software\Microsoft\Windows\DWM", "AccentColor"),
                (r"Software\Microsoft\Windows\DWM", "ColorizationColor"),
                (r"Software\Microsoft\Windows\CurrentVersion\Explorer\Accent", "AccentColorMenu"),
                (r"Software\Microsoft\Windows\CurrentVersion\Explorer\Accent", "StartColorMenu"),
                (r"Software\Microsoft\Windows\CurrentVersion\Explorer\Accent", "AccentPalette"),
                (r"Control Panel\Desktop", "AutoColorization")]


def _abgr(color: str) -> int:
    c = color.lstrip("#")
    r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
    return 0xFF000000 | (b << 16) | (g << 8) | r


def accent_palette(color: str) -> bytes:
    """Windows-AccentPalette: 8 Farben (hell → dunkel), je R,G,B,0."""
    from PySide6.QtGui import QColor

    base = QColor(color)
    out = b""
    for f in (150, 130, 112, 100, 88, 72, 58, 100):
        c = base.lighter(f) if f > 100 else base.darker(int(10000 / f)) if f < 100 else base
        out += bytes((c.red(), c.green(), c.blue(), 0))
    return out


def windows_values(color: str) -> dict:
    return {"AccentColor": _abgr(color), "ColorizationColor": 0xC4000000 | (int(color[1:], 16) & 0xFFFFFF),
            "AccentColorMenu": _abgr(color), "StartColorMenu": _abgr(color), "AccentPalette": accent_palette(color),
            "AutoColorization": "0"}


def _win_read() -> dict:
    import winreg

    saved = {}
    for path, name in _ACCENT_KEYS:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as key:
                value, kind = winreg.QueryValueEx(key, name)
                saved[f"{path}|{name}"] = [value.hex() if isinstance(value, bytes) else value, kind]
        except OSError:
            saved[f"{path}|{name}"] = None
    return saved


def _win_write(values: dict) -> None:
    import winreg

    for path, name in _ACCENT_KEYS:
        if name not in values:
            continue
        v = values[name]
        kind = winreg.REG_BINARY if isinstance(v, bytes) else winreg.REG_SZ if isinstance(v, str) else winreg.REG_DWORD
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, path) as key:
            winreg.SetValueEx(key, name, 0, kind, v)
    _win_broadcast()


def _win_restore(saved: dict) -> None:
    import winreg

    for full, entry in saved.items():
        path, name = full.split("|", 1)
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, path) as key:
            if entry is None:
                try:
                    winreg.DeleteValue(key, name)
                except OSError:
                    pass
                continue
            value, kind = entry
            winreg.SetValueEx(key, name, 0, kind, bytes.fromhex(value) if kind == winreg.REG_BINARY else value)
    _win_broadcast()


def _win_broadcast() -> None:
    """Windows sagen, dass sich die Farben geändert haben (wie die Einstellungen-App)."""
    import ctypes

    HWND_BROADCAST, WM_SETTINGCHANGE, SMTO_ABORTIFHUNG = 0xFFFF, 0x1A, 0x2
    res = ctypes.c_ulong()
    for param in ("ImmersiveColorSet", "WindowsThemeElement"):
        ctypes.windll.user32.SendMessageTimeoutW(HWND_BROADCAST, WM_SETTINGCHANGE, 0, param, SMTO_ABORTIFHUNG,
                                                 2000, ctypes.byref(res))


# ------------------------------------------------------------------ gemeinsam
GNOME_KEYS = (("org.gnome.desktop.interface", "color-scheme"), ("org.gnome.desktop.interface", "accent-color"),
              ("org.gnome.desktop.background", "picture-uri"), ("org.gnome.desktop.background", "picture-uri-dark"),
              ("org.gnome.desktop.background", "picture-options"))



def _linux_desktop(run=subprocess.run) -> str:
    """"kde" (Plasma), "gnome" (gsettings mit GNOME-Schemas) oder ""."""
    if shutil.which("plasma-apply-colorscheme"):
        return "kde"
    if shutil.which("gsettings"):
        try:
            r = run(["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"], capture_output=True,
                    text=True, timeout=10)
            if r.returncode == 0:
                return "gnome"
        except (OSError, subprocess.SubprocessError):
            pass
    return ""


GNOME_FOR_ACCENT = {"alupc": "blue", "blau": "blue", "violett": "purple", "gruen": "green", "orange": "orange",
                    "rosa": "pink"}


def gnome_accent(color: str) -> str:
    """GNOME-Akzentfarbe (GNOME kennt nur feste Farben, siehe theme.GNOME_ACCENTS): AluPC-Farben nach Namen
    („Grün“ → green), eigene Farben nach dem nächsten Farbton – kaum gesättigt → „slate“."""
    from PySide6.QtGui import QColor

    from .ui.theme import ACCENTS, GNOME_ACCENTS

    if color in GNOME_FOR_ACCENT:
        return GNOME_FOR_ACCENT[color]
    named = next((k for k, v in ACCENTS.items() if v[1].lower() == str(color).lower()), "")
    if named in GNOME_FOR_ACCENT:
        return GNOME_FOR_ACCENT[named]
    h, s, _v, _a = QColor(color).getHsv()
    if h < 0 or s < 40:
        return "slate"
    order = ("blue", "green", "teal", "yellow", "orange", "red", "pink", "purple")

    def dist(name):
        gh = QColor(GNOME_ACCENTS[name]).hue()
        d = abs(gh - h) % 360
        return min(d, 360 - d)

    return min(order, key=dist)


def supported(run=subprocess.run) -> tuple[bool, str]:
    if IS_WINDOWS:
        return True, ""
    if _linux_desktop(run):
        return True, ""
    return False, "Geht unter Linux mit KDE Plasma oder GNOME (weder plasma-apply-colorscheme noch gsettings gefunden)."


def active() -> bool:
    return _state_file().is_file()


_MODE_KEY = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"


def _win_mode_read() -> dict:
    import winreg

    out = {}
    for name in ("AppsUseLightTheme", "SystemUsesLightTheme"):
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _MODE_KEY) as key:
                out[name] = winreg.QueryValueEx(key, name)[0]
        except OSError:
            out[name] = None
    return out


def _win_mode_write(values: dict) -> None:
    import winreg

    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _MODE_KEY) as key:
        for name, v in values.items():
            if v is None:
                try:
                    winreg.DeleteValue(key, name)
                except OSError:
                    pass
            else:
                winreg.SetValueEx(key, name, 0, winreg.REG_DWORD, int(v))
    _win_broadcast()


def _win_wallpaper_read() -> str:
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Desktop") as key:
            return str(winreg.QueryValueEx(key, "Wallpaper")[0])
    except OSError:
        return ""


def _win_wallpaper_set(path: str) -> bool:
    import ctypes

    SPI_SETDESKWALLPAPER, SPIF = 20, 0x01 | 0x02  # UPDATEINIFILE | SENDCHANGE
    return bool(ctypes.windll.user32.SystemParametersInfoW(SPI_SETDESKWALLPAPER, 0, path, SPIF))


def _kde_wallpaper_read() -> str:
    """Erstes Bild der Plasma-Arbeitsfläche (für „Zurück“)."""
    cfg = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "plasma-org.kde.plasma.desktop-appletsrc"
    try:
        for line in cfg.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("Image="):
                return line.split("=", 1)[1].replace("file://", "")
    except OSError:
        pass
    return ""


def _kde_plasma_theme() -> str:
    import configparser

    cp = configparser.ConfigParser(interpolation=None, strict=False)
    try:
        cp.read(Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "plasmarc", encoding="utf-8")
        return cp.get("Theme", "name", fallback="")
    except (OSError, configparser.Error):
        return ""


def wallpaper_path() -> Path:
    from .config import config_dir

    return config_dir() / "desktop-hintergrund.png"


def _hue(color, deg: int):
    from PySide6.QtGui import QColor

    c = QColor(color)
    h, sat, v, _a = c.getHsv()
    return QColor.fromHsv(((h if h >= 0 else 230) + deg) % 360, max(sat, 120), v)


def paint_wallpaper(p, w: float, h: float, dark: bool, accent: str = "alupc", seed: int = 7,
                    colors: tuple[str, str] | None = None) -> None:
    """Das AluPC-Hintergrundbild malen („Aurora“): tiefe Grundfarbe, große weiche Farbwolken in Akzent- und
    Partnerfarbe, leuchtende Bänder, feines Korn und ein dunkler Rand. Gleiche Grafik für das System-Hintergrundbild
    (Windows/KDE/GNOME) und die AluPC-Oberfläche – darum hier als Funktion."""
    import random

    from PySide6.QtCore import QPointF, QRectF, Qt
    from PySide6.QtGui import QColor, QImage, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap, QRadialGradient

    from .ui.theme import make_theme

    if colors is None:
        t = make_theme("dunkel" if dark else "hell", accent)
        colors = (t.accent, t.accent2)
    a1, a2 = QColor(colors[0]), QColor(colors[1])
    a3, a4 = _hue(colors[0], 48), _hue(colors[0], -70)
    full = QRectF(0, 0, w, h)
    p.save()
    p.setRenderHint(QPainter.Antialiasing)
    base = QLinearGradient(0, 0, w * 0.4, h)
    if dark:
        base.setColorAt(0, QColor(a1).darker(560))
        base.setColorAt(0.6, QColor("#070a16"))
        base.setColorAt(1, QColor(a2).darker(620))
    else:
        base.setColorAt(0, QColor(a1).lighter(190))
        base.setColorAt(0.6, QColor("#f3f5fc"))
        base.setColorAt(1, QColor(a2).lighter(185))
    p.fillRect(full, base)
    big = max(w, h)
    blobs = ((0.84, 0.16, 0.62, a1, 175), (0.10, 0.92, 0.58, a2, 150), (0.52, 0.62, 0.42, a3, 80),
             (0.04, 0.06, 0.40, a4, 75), (0.98, 0.98, 0.35, a3, 70))
    for cx, cy, r, col, alpha in blobs:  # weiche Farbwolken
        glow = QRadialGradient(QPointF(w * cx, h * cy), big * r)
        c = QColor(col) if dark else QColor(col).lighter(118)
        for stop, k in ((0, 1.0), (0.35, 0.55), (0.7, 0.16), (1, 0.0)):
            c.setAlpha(int((alpha if dark else alpha * 0.8) * k))
            glow.setColorAt(stop, c)
        p.fillRect(full, glow)
    rng = random.Random(seed)
    p.setCompositionMode(QPainter.CompositionMode_Screen if dark else QPainter.CompositionMode_SourceOver)
    p.setBrush(Qt.NoBrush)
    import math

    for y0, amp, thick, col, alpha in ((0.60, 0.17, 0.22, a1, 34), (0.70, 0.13, 0.15, a2, 30),
                                       (0.50, 0.21, 0.10, a3, 26)):  # seidige Bänder (Aurora) aus vielen Linien
        k1, k2, wob = rng.uniform(0.2, 0.4), rng.uniform(0.55, 0.8), rng.uniform(0.6, 1.4)
        n = 30
        for j in range(n):
            f = j / (n - 1)
            off = thick * f
            sway = 0.02 * math.sin(f * math.pi * wob)
            path = QPainterPath(QPointF(-w * 0.05, h * (y0 + amp * 0.3 + off)))
            path.cubicTo(QPointF(w * (k1 + sway), h * (y0 - amp + off * 0.6)),
                         QPointF(w * (k2 - sway), h * (y0 + amp + off * 1.3)),
                         QPointF(w * 1.05, h * (y0 - amp * 0.4 + off)))
            c = QColor(col) if dark else QColor(col).lighter(140)
            c.setAlpha(int(alpha * math.sin(math.pi * f) ** 1.5 * (1.0 if dark else 1.6)))
            p.setPen(QPen(c, h * thick / n * 3.0))
            p.drawPath(path)
        top = QPainterPath(QPointF(-w * 0.05, h * (y0 + amp * 0.3)))
        top.cubicTo(QPointF(w * k1, h * (y0 - amp)), QPointF(w * k2, h * (y0 + amp)), QPointF(w * 1.05, h * (y0 - amp * 0.4)))
        p.setPen(QPen(QColor(255, 255, 255, 34 if dark else 110), max(1.0, w / 1600)))  # feine Lichtkante
        p.drawPath(top)
    p.setCompositionMode(QPainter.CompositionMode_SourceOver)
    vig = QRadialGradient(QPointF(w * 0.5, h * 0.45), big * 0.75)  # Rand dunkler (bzw. heller)
    edge = QColor(0, 0, 0) if dark else QColor(255, 255, 255)
    edge.setAlpha(0)
    vig.setColorAt(0.55, edge)
    edge.setAlpha(150 if dark else 70)
    vig.setColorAt(1, edge)
    p.fillRect(full, vig)
    tile = QImage(128, 128, QImage.Format_ARGB32)  # feines Korn gegen Streifen im Verlauf
    for y in range(128):
        for x in range(128):
            v = rng.randint(0, 255)
            tile.setPixelColor(x, y, QColor(v, v, v, 7 if dark else 5))
    p.drawTiledPixmap(full, QPixmap.fromImage(tile))
    p.restore()


def render_wallpaper(dark: bool, accent: str, size: tuple[int, int] = (2560, 1440), path: Path | None = None) -> Path:
    """Hintergrundbild in den Design-Farben (siehe paint_wallpaper) als PNG speichern."""
    from PySide6.QtGui import QImage, QPainter

    w, h = size
    img = QImage(w, h, QImage.Format_RGB32)
    p = QPainter(img)
    paint_wallpaper(p, w, h, dark, accent)
    p.end()
    target = wallpaper_path() if path is None else path
    target.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(target), "PNG")
    return target


def _screen_size() -> tuple[int, int]:
    try:
        from PySide6.QtGui import QGuiApplication

        s = QGuiApplication.primaryScreen()
        if s is not None:
            g, dpr = s.geometry(), s.devicePixelRatio()
            return max(1280, int(g.width() * dpr)), max(720, int(g.height() * dpr))
    except Exception:  # noqa: BLE001
        pass
    return 2560, 1440


def apply(dark: bool, run=subprocess.run, accent: str = "alupc", colors: bool = True, mode: bool = True,
          wallpaper: bool = True) -> tuple[bool, str]:
    """AluPC-Design aufs System: Farben (Akzent/Farbschema), Hell/Dunkel, Hintergrundbild. Mehrfach aufrufbar – das
    erste Mal wird der alte Stand gemerkt, später nur noch angepasst."""
    ok, why = supported(run)
    if not ok:
        return False, why
    from .ui.theme import make_theme

    accent = accent if accent and accent != "system" else "alupc"
    state = _state_file()
    previous = json.loads(state.read_text(encoding="utf-8")) if state.is_file() else {}
    done = []
    try:
        if IS_WINDOWS:
            if colors:
                previous.setdefault("windows", _win_read())
                _win_write(windows_values(make_theme("dunkel" if dark else "hell", accent).accent))
                done.append("Akzentfarbe")
            if mode:
                previous.setdefault("windows_mode", _win_mode_read())
                light = 0 if dark else 1
                _win_mode_write({"AppsUseLightTheme": light, "SystemUsesLightTheme": light})
                done.append("dunkel" if dark else "hell")
            if wallpaper:
                previous.setdefault("windows_wallpaper", _win_wallpaper_read())
                if _win_wallpaper_set(str(render_wallpaper(dark, accent, _screen_size()))):
                    done.append("Hintergrundbild")
        elif _linux_desktop(run) == "gnome":
            def gget(schema, key):
                r = run(["gsettings", "get", schema, key], capture_output=True, text=True, timeout=10)
                return r.stdout.strip() if r.returncode == 0 else None

            def gset(schema, key, value):
                return run(["gsettings", "set", schema, key, value], capture_output=True, text=True,
                           timeout=10).returncode == 0

            previous.setdefault("gnome", {f"{s} {k}": gget(s, k) for s, k in GNOME_KEYS})
            if mode and gset("org.gnome.desktop.interface", "color-scheme", "prefer-dark" if dark else "default"):
                done.append("dunkel" if dark else "hell")
            if colors and previous["gnome"].get("org.gnome.desktop.interface accent-color") is not None and gset(
                    "org.gnome.desktop.interface", "accent-color",
                    gnome_accent(accent if accent in GNOME_FOR_ACCENT else
                                 make_theme("dunkel" if dark else "hell", accent).accent)):
                done.append("Akzentfarbe")
            if wallpaper:
                uri = render_wallpaper(dark, accent, _screen_size()).resolve().as_uri()
                if gset("org.gnome.desktop.background", "picture-uri", uri) and \
                        gset("org.gnome.desktop.background", "picture-uri-dark", uri):
                    gset("org.gnome.desktop.background", "picture-options", "zoom")
                    done.append("Hintergrundbild")
        else:
            if colors or mode:
                previous.setdefault("kde", _kde_current_scheme())
                folder = _schemes_dir()
                folder.mkdir(parents=True, exist_ok=True)
                for d in (False, True):
                    (folder / f"{SCHEMES[d]}.colors").write_text(kde_scheme(d, accent), encoding="utf-8")
                r = run(["plasma-apply-colorscheme", SCHEMES[dark]], capture_output=True, text=True, timeout=20)
                if r.returncode != 0 and "already" not in (r.stdout + r.stderr).lower():
                    return False, "KDE hat das Farbschema nicht übernommen: " + (r.stderr or r.stdout).strip()[:160]
                done.append(f"Farbschema „{'AluPC Dunkel' if dark else 'AluPC'}“")
            if mode and shutil.which("plasma-apply-desktoptheme"):
                previous.setdefault("kde_plasma", _kde_plasma_theme())
                run(["plasma-apply-desktoptheme", "breeze-dark" if dark else "breeze-light"], capture_output=True,
                    text=True, timeout=20)
                done.append("Plasma-Stil")
            if wallpaper and shutil.which("plasma-apply-wallpaperimage"):
                previous.setdefault("kde_wallpaper", _kde_wallpaper_read())
                img = render_wallpaper(dark, accent, _screen_size())
                r = run(["plasma-apply-wallpaperimage", str(img)], capture_output=True, text=True, timeout=20)
                if r.returncode == 0:
                    done.append("Hintergrundbild")
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        return False, f"Ging nicht: {exc}"
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(json.dumps(previous), encoding="utf-8")
    return True, "Desktop im AluPC-Design: " + (", ".join(done) or "nichts geändert") + "."


def restore(run=subprocess.run) -> tuple[bool, str]:
    state = _state_file()
    if not state.is_file():
        return False, "Nichts zurückzustellen."
    previous = json.loads(state.read_text(encoding="utf-8"))
    try:
        if IS_WINDOWS:
            if "windows" in previous:
                _win_restore(previous.get("windows") or {})
            if "windows_mode" in previous:
                _win_mode_write(previous["windows_mode"])
            if previous.get("windows_wallpaper") is not None and "windows_wallpaper" in previous:
                _win_wallpaper_set(previous["windows_wallpaper"])
        elif "gnome" in previous:
            for sk, value in (previous.get("gnome") or {}).items():
                if value is not None:
                    schema, key = sk.split(" ", 1)
                    run(["gsettings", "set", schema, key, value], capture_output=True, text=True, timeout=10)
        else:
            if "kde" in previous:
                run(["plasma-apply-colorscheme", previous.get("kde") or "BreezeLight"], capture_output=True,
                    text=True, timeout=20)
            if previous.get("kde_plasma") and shutil.which("plasma-apply-desktoptheme"):
                run(["plasma-apply-desktoptheme", previous["kde_plasma"]], capture_output=True, text=True, timeout=20)
            if previous.get("kde_wallpaper") and shutil.which("plasma-apply-wallpaperimage"):
                run(["plasma-apply-wallpaperimage", previous["kde_wallpaper"]], capture_output=True, text=True,
                    timeout=20)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        return False, f"Ging nicht: {exc}"
    state.unlink(missing_ok=True)
    return True, "Desktop wie vorher (Farben, Hell/Dunkel, Hintergrundbild)."
