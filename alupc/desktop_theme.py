"""AluPC-Theme auch für den Desktop (freiwillig, mit „Zurück“).

* Linux/KDE: Farbschema „AluPC“ bzw. „AluPC Dunkel“ nach ~/.local/share/color-schemes und mit
  plasma-apply-colorscheme anwenden (Fenster, Leisten, Markierungen in Logo-Farben).
* Windows: Akzentfarbe (Start, Taskleiste-Akzente, Markierungen, Titelleisten) auf das AluPC-Blau setzen.
Vorher wird gemerkt, was eingestellt war – „Zurück“ stellt genau das wieder her.
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


def kde_scheme(dark: bool) -> str:
    """Inhalt der KDE-Farbschema-Datei aus dem AluPC-Theme."""
    from .ui.theme import make_theme

    t = make_theme("dunkel" if dark else "hell", "alupc")

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


def apply(dark: bool, run=subprocess.run) -> tuple[bool, str]:
    ok, why = supported()
    if not ok:
        return False, why
    state = _state_file()
    previous = json.loads(state.read_text(encoding="utf-8")) if state.is_file() else None
    try:
        if IS_WINDOWS:
            from .ui.theme import make_theme

            if previous is None:
                previous = {"windows": _win_read()}
            _win_write(windows_values(make_theme("dunkel" if dark else "hell", "alupc").accent))
        else:
            if previous is None:
                previous = {"kde": _kde_current_scheme()}
            folder = _schemes_dir()
            folder.mkdir(parents=True, exist_ok=True)
            for d in (False, True):
                (folder / f"{SCHEMES[d]}.colors").write_text(kde_scheme(d), encoding="utf-8")
            r = run(["plasma-apply-colorscheme", SCHEMES[dark]], capture_output=True, text=True, timeout=20)
            if r.returncode != 0:
                return False, "KDE hat das Farbschema nicht übernommen: " + (r.stderr or r.stdout).strip()[:160]
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        return False, f"Ging nicht: {exc}"
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(json.dumps(previous), encoding="utf-8")
    return True, ("Desktop in AluPC-Farben (Akzentfarbe)." if IS_WINDOWS else
                  f"Desktop in AluPC-Farben (KDE-Farbschema „{'AluPC Dunkel' if dark else 'AluPC'}“).")


def restore(run=subprocess.run) -> tuple[bool, str]:
    state = _state_file()
    if not state.is_file():
        return False, "Nichts zurückzustellen."
    previous = json.loads(state.read_text(encoding="utf-8"))
    try:
        if IS_WINDOWS:
            _win_restore(previous.get("windows") or {})
        else:
            scheme = previous.get("kde") or "BreezeLight"
            run(["plasma-apply-colorscheme", scheme], capture_output=True, text=True, timeout=20)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        return False, f"Ging nicht: {exc}"
    state.unlink(missing_ok=True)
    return True, "Desktop-Farben wie vorher."
