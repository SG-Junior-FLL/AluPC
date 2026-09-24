"""Menüeintrag (.desktop) und Programmsymbole unter Linux einrichten.

* Das .deb installiert beides systemweit (packaging/linux/build_deb.sh ruft `install_files` auf).
* Die portable Version (tar.gz) trägt sich beim Start selbst für den Benutzer ein. Ohne Eintrag zeigt
  KDE unter Wayland statt des Logos ein Standardsymbol, und die KWin-Aufnahme ohne Nachfrage
  (Spiegeln) wäre nicht erlaubt.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

RESOURCES = Path(__file__).resolve().parent.parent / "resources"
ICON_SIZES = (16, 22, 24, 32, 48, 64, 128, 256, 512)


def desktop_entry(exec_path: str) -> str:
    """Inhalt der .desktop-Datei; `exec_path` ersetzt „alupc“ in allen Exec-Zeilen."""
    text = (RESOURCES / "alupc.desktop").read_text(encoding="utf-8")
    quoted = f'"{exec_path}"' if " " in exec_path else exec_path
    return re.sub(r"^Exec=alupc\b", lambda _m: f"Exec={quoted}", text, flags=re.M)


def install_files(prefix: Path, exec_path: str) -> list[Path]:
    """Schreibt .desktop und Symbole unter `prefix` (z. B. /usr/share oder ~/.local/share).
    Gibt die geänderten Dateien zurück (leer = war schon aktuell)."""
    changed = []

    def put(target: Path, data: bytes):
        try:
            if target.read_bytes() == data:
                return
        except OSError:
            pass
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        changed.append(target)

    put(prefix / "applications" / "alupc.desktop", desktop_entry(exec_path).encode("utf-8"))
    icons = prefix / "icons" / "hicolor"
    for size in ICON_SIZES:
        src = RESOURCES / "icons" / f"alupc-{size}.png"
        if src.exists():
            put(icons / f"{size}x{size}" / "apps" / "alupc.png", src.read_bytes())
    svg = RESOURCES / "icons" / "alupc.svg"
    if svg.exists():
        put(icons / "scalable" / "apps" / "alupc.svg", svg.read_bytes())
    return changed


def refresh_caches(prefix: Path) -> None:
    """Menü- und Symbol-Zwischenspeicher auffrischen (KDE liest Berechtigungen aus KSycoca)."""
    commands = [
        ["update-desktop-database", "-q", str(prefix / "applications")],
        ["gtk-update-icon-cache", "-q", "-t", str(prefix / "icons" / "hicolor")],
        ["kbuildsycoca6"], ["kbuildsycoca5"],
    ]
    for cmd in commands:
        if shutil.which(cmd[0]):
            try:
                subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except OSError:
                pass
            if cmd[0].startswith("kbuildsycoca"):
                break  # eins reicht


def system_installed() -> bool:
    """Läuft das .deb (Menüeintrag liegt systemweit und zeigt auf dieses Programm)?"""
    entry = Path("/usr/share/applications/alupc.desktop")
    try:
        return f"Exec={os.path.realpath(sys.executable)}" in entry.read_text(encoding="utf-8")
    except OSError:
        return False


def ensure_user_entry() -> bool:
    """Portable Version: Menüeintrag + Symbole für den Benutzer anlegen bzw. aktualisieren.
    Nur für die fertige Programmdatei (nicht beim Start aus dem Quellcode)."""
    if not sys.platform.startswith("linux") or not getattr(sys, "frozen", False):
        return False
    base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    if system_installed():
        # Ein alter Eintrag der portablen Version würde den des .deb verdecken (gleicher Name) –
        # dann gälte die KWin-Erlaubnis nicht für das installierte Programm.
        stale = base / "applications" / "alupc.desktop"
        try:
            text = stale.read_text(encoding="utf-8")
        except OSError:
            return False
        if "X-KDE-DBUS-Restricted-Interfaces" in text and f"Exec={os.path.realpath(sys.executable)}" not in text:
            stale.unlink()
            refresh_caches(base)
            return True
        return False
    try:
        changed = install_files(base, os.path.realpath(sys.executable))
    except OSError:
        return False
    if changed:
        refresh_caches(base)
    return bool(changed)


def main(argv=None) -> int:
    """Für build_deb.sh: python -m alupc.platform.linux_desktop ZIEL-PREFIX EXEC-PFAD"""
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 2:
        print("Aufruf: linux_desktop.py PREFIX EXEC", file=sys.stderr)
        return 2
    for path in install_files(Path(args[0]), args[1]):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
