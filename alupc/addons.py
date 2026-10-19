"""Zusatzprogramme, die AluPC unter Windows selbst installiert (AirPlay, RGB, Lüfter, virtuelles Mikro/Kamera) –
merken und bei der Deinstallation auf Wunsch wieder entfernen.

Gemerkt wird nur, was VORHER fehlte und NACHHER da ist: Hatte man ein Programm schon, bleibt es beim
Deinstallieren. Merkzettel: eine Datei je Programm in %ProgramData%\\AluPC\\zusatz (das Deinstallationsprogramm
liest denselben Ordner). Linux: Pakete, die AluPC nachinstalliert, werden als „automatisch“ markiert –
`sudo apt autoremove` entfernt sie nach AluPC mit (siehe `apt_install_script`).
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

IS_WINDOWS = sys.platform.startswith("win")
# Schlüssel → (Name für Menschen, winget-Id; None = kein winget-Paket)
ADDONS = {
    "bonjour": ("Bonjour (iPhone findet den PC)", "Apple.Bonjour"),
    "uxplay": ("uxplay-windows (AirPlay-Empfang)", "leapbtw.uxplay"),
    "openrgb": ("OpenRGB (RGB-Beleuchtung)", "OpenRGB.OpenRGB"),
    "fancontrol": ("FanControl (Lüfter)", "Rem0o.FanControl"),
    "obs": ("OBS Studio (virtuelle Kamera)", "OBSProject.OBSStudio"),
    "vbcable": ("VB-CABLE (virtuelles Mikro)", None),
}
VBCABLE_INF = re.compile(r"vbMmeCable", re.I)  # Treiber-INF von VB-CABLE (Original-Name in pnputil)
_FLAGS = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _run(cmd: list[str], timeout: int = 900) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, creationflags=_FLAGS,
                          encoding="utf-8", errors="replace")


# --------------------------------------------------------------------------- Merkzettel
def record_dirs() -> list[Path]:
    """Wo gemerkt wird: zuerst %ProgramData% (für alle Benutzer, liest auch das Deinstallationsprogramm),
    ersatzweise der eigene Einstellungsordner (falls ProgramData nicht beschreibbar ist)."""
    from .config import config_dir

    dirs = []
    if IS_WINDOWS:
        dirs.append(Path(os.environ.get("ProgramData", r"C:\ProgramData")) / "AluPC" / "zusatz")
    dirs.append(config_dir() / "zusatz")
    return dirs


def mark(key: str) -> bool:
    for folder in record_dirs():
        try:
            folder.mkdir(parents=True, exist_ok=True)
            (folder / f"{key}.txt").write_text(ADDONS[key][0], encoding="utf-8")
            return True
        except OSError:
            continue
    return False


def recorded() -> list[str]:
    """Von AluPC installierte Zusatzprogramme (Schlüssel, ohne doppelte)."""
    keys = []
    for folder in record_dirs():
        try:
            keys += [f.stem for f in sorted(folder.glob("*.txt")) if f.stem in ADDONS]
        except OSError:
            pass
    return list(dict.fromkeys(keys))


def forget(key: str) -> None:
    for folder in record_dirs():
        try:
            (folder / f"{key}.txt").unlink(missing_ok=True)
        except OSError:
            pass


# --------------------------------------------------------------------------- Da oder nicht?
def _vbcable_infs(run=_run) -> list[str]:
    """Veröffentlichte INF-Namen (oemNN.inf) des VB-CABLE-Treibers – sprachunabhängig aus `pnputil /enum-drivers`
    (Blöcke durch Leerzeilen getrennt; im selben Block stehen oemNN.inf und der Original-Name)."""
    try:
        out = run(["pnputil", "/enum-drivers"], timeout=60).stdout or ""
    except (OSError, subprocess.SubprocessError):
        return []
    infs = []
    for block in re.split(r"\n\s*\n", out):
        oem = re.search(r"\boem\d+\.inf\b", block, re.I)
        if oem and VBCABLE_INF.search(block):
            infs.append(oem.group(0))
    return list(dict.fromkeys(infs))


def present(key: str, run=_run) -> bool:
    """Ist das Zusatzprogramm installiert? (winget-Liste bzw. Treiberliste)"""
    if not IS_WINDOWS:
        return False
    if key == "vbcable":
        return bool(_vbcable_infs(run))
    package = ADDONS[key][1]
    if not package or not shutil.which("winget"):
        return False
    try:
        r = run(["winget", "list", "--id", package, "-e", "--accept-source-agreements",
                 "--disable-interactivity"], timeout=120)
    except (OSError, subprocess.SubprocessError):
        return False
    return r.returncode == 0 and package.lower() in (r.stdout or "").lower()


def track(keys: list[str], action, check=present):
    """`action()` ausführen und merken, welche der `keys` dadurch NEU installiert wurden."""
    keys = [k for k in keys if k in ADDONS]
    before = {k: check(k) for k in keys} if IS_WINDOWS else {}
    try:
        return action()
    finally:
        for k in keys if IS_WINDOWS else []:
            if not before[k] and check(k):
                mark(k)


# --------------------------------------------------------------------------- Installieren / Entfernen
def winget_install(key: str, run=_run) -> bool:
    package = ADDONS[key][1]
    if not package or not shutil.which("winget"):
        return False
    r = run(["winget", "install", "--id", package, "-e", "--silent", "--accept-source-agreements",
             "--accept-package-agreements", "--disable-interactivity"])
    return r.returncode == 0


def remove(key: str, run=_run) -> tuple[bool, str]:
    """Ein (von AluPC installiertes) Zusatzprogramm entfernen."""
    name = ADDONS[key][0]
    try:
        if key == "vbcable":
            infs = _vbcable_infs(run)
            for inf in infs:
                run(["pnputil", "/delete-driver", inf, "/uninstall", "/force"], timeout=300)
            ok = not _vbcable_infs(run)
        else:
            if key == "obs":  # virtuelle Kamera vorher abmelden (sonst bleibt der Eintrag stehen)
                dll = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "obs-studio" / "data" / \
                    "obs-plugins" / "win-dshow" / "obs-virtualcam-module64.dll"
                if dll.is_file():
                    run(["regsvr32", "/s", "/u", str(dll)], timeout=60)
            run(["winget", "uninstall", "--id", ADDONS[key][1], "-e", "--silent", "--accept-source-agreements",
                 "--disable-interactivity"])
            ok = not present(key, run)
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"{name}: ging nicht ({exc})"
    return ok, f"{name}: {'entfernt' if ok else 'ließ sich nicht entfernen'}"


def remove_recorded(run=_run) -> list[str]:
    """Alles entfernen, was AluPC installiert hat. Was schon weg ist, wird nur vergessen."""
    lines = []
    for key in recorded():
        if present(key, run):
            ok, msg = remove(key, run)
            lines.append(msg)
            if ok:
                forget(key)
        else:
            forget(key)
    return lines


def main(arg: str) -> int:
    """`AluPC --zusatz installieren=bonjour,uxplay` (Installer) bzw. `--zusatz entfernen` (Deinstallation)."""
    if arg == "entfernen":
        lines = remove_recorded()
        print("\n".join(lines) or "Keine von AluPC installierten Zusatzprogramme gefunden.")
        return 0 if all("entfernt" in ln for ln in lines) else 1
    if arg.startswith("installieren="):
        keys = [k.strip() for k in arg.split("=", 1)[1].split(",") if k.strip() in ADDONS]
        ok = True
        for key in keys:
            ok = bool(track([key], lambda k=key: winget_install(k))) and ok
        return 0 if ok else 1
    print("Unbekannt: --zusatz installieren=… | entfernen")
    return 2


def self_command(*args: str) -> list[str]:
    """Befehl, der AluPC selbst ohne Oberfläche startet (gebautes Programm bzw. `python -m alupc`)."""
    if getattr(sys, "frozen", False):
        return [sys.executable, *args]
    return [sys.executable, "-m", "alupc", *args]


# --------------------------------------------------------------------------- Linux
def apt_install_script(packages: list[str]) -> str:
    """Shell-Zeilen: Pakete installieren und die NEU installierten als „automatisch“ markieren – so entfernt
    `apt autoremove` sie, wenn AluPC weg ist. Schon vorhandene Pakete bleiben unverändert."""
    names = " ".join(packages)
    return (f'new=""; for p in {names}; do dpkg -s "$p" >/dev/null 2>&1 || new="$new $p"; done\n'
            f"DEBIAN_FRONTEND=noninteractive apt-get -o DPkg::Lock::Timeout=600 install -y {names}\n"
            'if [ -n "$new" ]; then apt-mark auto $new >/dev/null 2>&1 || true; fi')
