"""AluPC ins System einbinden (pro Benutzer, ohne Adminrechte, abschaltbar).

* Rechtsklick auf Bild, Video oder PDF → „Auf Monitor 2 zeigen“; auf einen Ordner → „Als Diashow auf Monitor 2“
  (Windows: Explorer-Kontextmenü – unter Windows 11 bei „Weitere Optionen anzeigen“; KDE: Dolphin-Dienstmenü).
* Links „alupc://…“ (z. B. alupc://standbild, alupc://szene/Pause) – aus Browser, Verknüpfungen, Stream Deck …
  Nur harmlose Befehle; nichts, was Programme startet oder den PC ausschaltet.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

from .autostart import _quote, launch_command

IS_WINDOWS = sys.platform.startswith("win")
SCHEME = "alupc"
MENU_ID = "AluPC.Monitor2"
SHOW_LABEL = "Auf Monitor 2 zeigen"
SLIDES_LABEL = "Als Diashow auf Monitor 2"

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".tif", ".tiff"}
VIDEO_EXT = {".mp4", ".mkv", ".webm", ".mov", ".avi", ".m4v", ".mpg", ".mpeg", ".wmv"}
PAGE_EXT = {".pdf", ".html", ".htm", ".svg"}

# alupc://… darf nur das hier (Webseiten könnten solche Links auslösen)
URL_COMMANDS = {"zeigen", "standbild", "schwarz", "sichtschutz", "bild-in-bild", "bildschirmschoner", "spiegeln",
                "erweitern", "naechste_szene", "vorherige_szene", "timer_zeigen", "timer_start_pause",
                "timer_neustart", "timer_plus", "timer_minus", "musik_zeigen", "musik_pause", "musik_weiter",
                "musik_zurueck", "overlays"}


def url_command(url: str) -> str | None:
    """alupc://standbild → „standbild“, alupc://szene/Pause → „szene:Pause“; sonst None."""
    parts = urlsplit(url.strip())
    if parts.scheme.lower() != SCHEME:
        return None
    words = [unquote(p) for p in (parts.netloc + "/" + parts.path).split("/") if p]
    if not words:
        return "zeigen"
    head = words[0].lower()
    if head not in URL_COMMANDS:
        head = head.replace("-", "_")
    if head == "szene" and len(words) >= 2:
        return "szene:" + "/".join(words[1:])
    return head if head in URL_COMMANDS else None


def file_source(path: str) -> dict | None:
    """Welche Quelle zu einer Datei/einem Ordner passt (None = geht nicht)."""
    p = Path(path)
    if p.is_dir():
        return {"type": "slideshow", "folder": str(p), "interval": 5}
    ext = p.suffix.lower()
    if not p.is_file():
        return None
    if ext in IMAGE_EXT:
        return {"type": "image", "path": str(p)}
    if ext in VIDEO_EXT:
        return {"type": "video", "path": str(p), "loop": True}
    if ext in PAGE_EXT:
        return {"type": "website", "url": p.resolve().as_uri()}
    return None


# ------------------------------------------------------------------ Linux (KDE)
def _data_home() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")


def _config_home() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")


def _linux_files() -> dict[Path, str]:
    cmd = _quote(launch_command())
    mimes = ";".join(["image/*", "video/*", "application/pdf", "text/html", "image/svg+xml"]) + ";"

    def menu(kf5: bool) -> str:
        extra = "X-KDE-ServiceTypes=KonqPopupMenu/Plugin\n" if kf5 else ""
        return ("[Desktop Entry]\nType=Service\n" + extra +
                f"MimeType={mimes}inode/directory;\nActions=alupcZeigen;alupcDiashow;\nX-KDE-Priority=TopLevel\n\n"
                f"[Desktop Action alupcZeigen]\nName={SHOW_LABEL}\nIcon=alupc\nExec={cmd} --zeigen %f\n"
                f"MimeType={mimes}\n\n"
                f"[Desktop Action alupcDiashow]\nName={SLIDES_LABEL}\nIcon=alupc\nExec={cmd} --zeigen %f\n"
                "MimeType=inode/directory;\n")

    link = ("[Desktop Entry]\nType=Application\nName=AluPC (Links)\nNoDisplay=true\nIcon=alupc\n"
            f"Exec={cmd} %u\nMimeType=x-scheme-handler/{SCHEME};\n")
    data = _data_home()
    return {data / "kio" / "servicemenus" / "alupc-monitor2.desktop": menu(False),
            data / "kservices5" / "ServiceMenus" / "alupc-monitor2.desktop": menu(True),
            data / "applications" / "alupc-link.desktop": link}


def _mimeapps_set(on: bool) -> None:
    """x-scheme-handler/alupc in ~/.config/mimeapps.list eintragen/entfernen (Rest der Datei bleibt)."""
    path = _config_home() / "mimeapps.list"
    key = f"x-scheme-handler/{SCHEME}="
    lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    lines = [ln for ln in lines if not ln.startswith(key)]
    if on:
        if "[Default Applications]" not in lines:
            lines += ([""] if lines else []) + ["[Default Applications]"]
        lines.insert(lines.index("[Default Applications]") + 1, key + "alupc-link.desktop")
    if lines or path.is_file():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _linux_apply(on: bool) -> None:
    for path, text in _linux_files().items():
        if on:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            path.chmod(0o755)  # KDE nimmt Dienstmenüs im Benutzerordner nur, wenn sie ausführbar sind
        elif path.exists():
            path.unlink()
    _mimeapps_set(on)


def _linux_active() -> bool:
    return all(p.is_file() for p in _linux_files())


# ------------------------------------------------------------------ Windows
_CLASSES = r"Software\Classes"
_MENU_PARENTS = [r"SystemFileAssociations\image", r"SystemFileAssociations\video"] + \
                [rf"SystemFileAssociations\{e}" for e in sorted(PAGE_EXT)]


def windows_entries() -> dict[str, dict[str, str]]:
    """Registry-Schlüssel (unter HKCU\\Software\\Classes) → Werte ("" = Standardwert)."""
    parts = launch_command()
    cmd = _quote(parts)
    icon = parts[0] if getattr(sys, "frozen", False) else ""
    out: dict[str, dict[str, str]] = {}
    for parent, label in [(p, SHOW_LABEL) for p in _MENU_PARENTS] + [("Directory", SLIDES_LABEL)]:
        base = rf"{parent}\shell\{MENU_ID}"
        out[base] = {"MUIVerb": label, **({"Icon": icon} if icon else {})}
        out[base + r"\command"] = {"": f'{cmd} --zeigen "%1"'}
    out[SCHEME] = {"": "URL:AluPC", "URL Protocol": ""}
    if icon:
        out[SCHEME + r"\DefaultIcon"] = {"": f"{icon},0"}
    out[SCHEME + r"\shell\open\command"] = {"": f'{cmd} "%1"'}
    return out


def _win_delete_tree(root, path: str) -> None:
    import winreg

    try:
        with winreg.OpenKey(root, path, 0, winreg.KEY_ALL_ACCESS) as key:
            while True:
                try:
                    child = winreg.EnumKey(key, 0)
                except OSError:
                    break
                _win_delete_tree(root, path + "\\" + child)
        winreg.DeleteKey(root, path)
    except OSError:
        pass


def _win_apply(on: bool) -> None:
    import winreg

    root = winreg.HKEY_CURRENT_USER
    entries = windows_entries()
    if on:
        for sub, values in entries.items():
            with winreg.CreateKeyEx(root, rf"{_CLASSES}\{sub}", 0, winreg.KEY_SET_VALUE) as key:
                for name, value in values.items():
                    winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)
    else:
        for parent in _MENU_PARENTS + ["Directory"]:
            _win_delete_tree(root, rf"{_CLASSES}\{parent}\shell\{MENU_ID}")
        _win_delete_tree(root, rf"{_CLASSES}\{SCHEME}")
    try:  # Explorer neu einlesen lassen
        import ctypes

        ctypes.windll.shell32.SHChangeNotify(0x08000000, 0, None, None)
    except Exception:  # noqa: BLE001
        pass


def _win_read(sub: str, name: str) -> str | None:
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, rf"{_CLASSES}\{sub}") as key:
            return winreg.QueryValueEx(key, name)[0]
    except OSError:
        return None


def _win_active() -> bool:
    return all(_win_read(sub, name) == value for sub, values in windows_entries().items()
               for name, value in values.items())


# ------------------------------------------------------------------ gemeinsam
def is_active() -> bool:
    try:
        return _win_active() if IS_WINDOWS else _linux_active()
    except OSError:
        return False


def set_enabled(on: bool) -> tuple[bool, str]:
    try:
        _win_apply(on) if IS_WINDOWS else _linux_apply(on)
    except OSError as exc:
        return False, f"Ging nicht: {exc}"
    if not on:
        return True, "Aus dem System entfernt."
    where = "Explorer (Win 11: „Weitere Optionen anzeigen“)" if IS_WINDOWS else "Dolphin"
    return True, f"Rechtsklick → „{SHOW_LABEL}“ in {where}; Links alupc://…"


def sync(config) -> None:
    """Beim Start: Einstellung umsetzen (auch neuer Programmpfad nach Update/Umzug)."""
    want = bool(config["system_integration"])
    if want and is_active():
        return
    if want or is_active():
        set_enabled(want)
