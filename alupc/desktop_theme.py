"""AluPC-Design auch für das System (freiwillig, mit „Zurück“) – Farben, Hell/Dunkel und Hintergrundbild.

* Farben – Linux/KDE: Farbschema „AluPC“ bzw. „AluPC Dunkel“ (aus der gewählten Akzentfarbe) nach
  ~/.local/share/color-schemes und mit plasma-apply-colorscheme anwenden. Windows: Akzentfarbe (Start, Taskleiste,
  Markierungen, Titelleisten).
* Hell/Dunkel – Windows: Apps und System hell oder dunkel. KDE: steckt im Farbschema, dazu der Plasma-Stil
  (Breeze bzw. Breeze Dunkel), falls plasma-apply-desktoptheme da ist.
* Hintergrundbild – AluPC malt eins in den Design-Farben (Bildschirmgröße) und setzt es (Windows:
  SystemParametersInfo, KDE: plasma-apply-wallpaperimage).
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
def supported() -> tuple[bool, str]:
    if IS_WINDOWS:
        return True, ""
    if shutil.which("plasma-apply-colorscheme"):
        return True, ""
    return False, "Geht unter Linux nur mit KDE Plasma (plasma-apply-colorscheme fehlt)."


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


def render_wallpaper(dark: bool, accent: str, size: tuple[int, int] = (2560, 1440), path: Path | None = None) -> Path:
    """Hintergrundbild in den Design-Farben: Verlauf, weiches Leuchten in Akzentfarbe, dezentes Wellenmuster."""
    from PySide6.QtCore import QPointF, QRectF
    from PySide6.QtGui import QColor, QImage, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient

    from .ui.theme import make_theme

    t = make_theme("dunkel" if dark else "hell", accent)
    w, h = size
    img = QImage(w, h, QImage.Format_RGB32)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    base = QLinearGradient(0, 0, w, h)
    base.setColorAt(0, QColor(t.bg).darker(130) if dark else QColor(t.bg).lighter(103))
    base.setColorAt(1, QColor(t.accent).darker(330) if dark else QColor(t.accent).lighter(185))
    p.fillRect(QRectF(0, 0, w, h), base)
    for cx, cy, r, col, alpha in ((0.78, 0.22, 0.55, t.accent, 95), (0.18, 0.85, 0.45, t.accent2, 70)):
        glow = QRadialGradient(QPointF(w * cx, h * cy), w * r)
        c = QColor(col)
        c.setAlpha(alpha if dark else alpha // 2)
        glow.setColorAt(0, c)
        c.setAlpha(0)
        glow.setColorAt(1, c)
        p.fillRect(QRectF(0, 0, w, h), glow)
    for i in range(7):  # Wellenlinien
        wave = QPainterPath(QPointF(0, h * (0.55 + i * 0.045)))
        wave.cubicTo(QPointF(w * 0.3, h * (0.35 + i * 0.05)), QPointF(w * 0.65, h * (0.85 + i * 0.03)),
                     QPointF(w, h * (0.5 + i * 0.05)))
        c = QColor(255, 255, 255, 14) if dark else QColor(0, 0, 0, 10)
        p.setPen(QPen(c, max(1.0, w / 1400)))
        p.drawPath(wave)
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
    ok, why = supported()
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
