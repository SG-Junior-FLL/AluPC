"""Einstellungen sichern (Export/Import) und bei Dual-Boot automatisch zwischen Windows und Linux abgleichen.

Abgleich: Beide Systeme müssen denselben Ordner erreichen. Linux kann Windows-Laufwerke (NTFS) lesen und
schreiben, Windows aber keine Linux-Laufwerke (ext4) – der Ordner liegt deshalb auf einem Windows-Laufwerk
(z. B. C:\\AluPC-Sync) oder einer gemeinsamen Daten-Partition (NTFS/exFAT). AluPC schreibt dort
`alupc-sync.json`.

Statt Uhrzeiten (bei Dual-Boot gehen Windows und Linux oft um Stunden verschieden!) zählt eine
Revisionsnummer: Wer etwas ändert, schreibt die Datei mit der nächsten Nummer. Beim Start übernimmt
AluPC eine höhere Nummer vom anderen System. Haben beide Seiten geändert (z. B. weil das Laufwerk nicht
eingehängt war), gewinnt die eigene Änderung – die andere Fassung wird als Sicherung daneben gelegt.

Nicht abgeglichen wird, was je System anders ist: Monitor-Namen, Kamera-IDs, Programmpfade,
Fingerabdruck, zuletzt gezeigter Inhalt.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from . import __version__
from .config import DEFAULTS

IS_WINDOWS = sys.platform.startswith("win")
FOLDER_NAME = "AluPC-Sync"
FILE_NAME = "alupc-sync.json"
SHARED_FS = {"ntfs", "ntfs3", "fuseblk", "exfat", "vfat", "msdos", "fat"}

# Bereiche für Export/Import (Name → Einstellungs-Schlüssel)
SECTIONS: dict[str, tuple[str, list[str]]] = {
    "startseite": ("Startseite (Kacheln, Reihenfolge, eigene Kacheln)", ["start_page"]),
    "szenen": ("Szenen", ["scenes"]),
    "favoriten": ("Websites und Mediathek", ["websites", "media"]),
    "tasten": ("Tastenkürzel", ["hotkeys"]),
    "aussehen": ("Darstellung und Übergänge", ["appearance", "transition"]),
    "schoner": ("Bildschirmschoner und Timer", ["screensaver", "timer"]),
    "toene": ("Töne", ["sounds"]),
    "monitor2": ("Monitor 2, Bild-in-Bild, Zeichnen, Kamera-Optionen",
                 ["output", "privacy", "pip", "laser", "draw", "program", "camera"]),
    "handy": ("Handy (Name, Code)", ["handy", "cast"]),
    "rgb": ("RGB-Beleuchtung", ["rgb"]),
}


def all_keys() -> list[str]:
    return [k for _label, keys in SECTIONS.values() for k in keys]


def _portable(key: str, value):
    """Nur das, was auf beiden Systemen gleich gilt (ohne Pfade/Geräte-IDs dieses PCs)."""
    value = copy.deepcopy(value)
    if key == "draw" and isinstance(value, dict):
        value.pop("strokes", None)
        value.pop("strokes_for", None)
    elif key == "handy" and isinstance(value, dict):
        value = {k: v for k, v in value.items() if k in ("airplay_name", "pin")}
    elif key == "cast" and isinstance(value, dict):
        value = {k: v for k, v in value.items() if k in ("code", "port")}
    elif key == "media" and isinstance(value, dict):
        value = {"saved": value.get("saved", [])}
    elif key == "camera":
        value = {}  # Kamera-IDs sind je System verschieden
    elif key == "rgb" and isinstance(value, dict):
        value.pop("openrgb_path", None)
    return value


def payload(config, keys: list[str] | None = None) -> dict:
    return {k: _portable(k, config.data[k]) for k in (keys or all_keys()) if k in config.data}


def payload_hash(data: dict) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


def apply_payload(config, data: dict, keys: list[str] | None = None) -> list[str]:
    """Übernimmt Einstellungen (geprüft, mit Standardwerten ergänzt). Rückgabe: geänderte Schlüssel."""
    changed = []
    for key in keys or all_keys():
        if key not in data or key not in DEFAULTS:
            continue
        value = data[key]
        default = DEFAULTS[key]
        if isinstance(default, dict):
            if not isinstance(value, dict):
                continue
            # Eigene, systemabhängige Teile behalten (z. B. Zeichnungen, Programmpfade)
            local = config.data.get(key, {})
            merged = {**default, **local, **value}
            if key == "media":
                merged["recent"] = local.get("recent", [])
            if key == "camera":
                merged = local
            value = merged
        elif isinstance(default, list) and not isinstance(value, list):
            continue
        if config.data.get(key) != value:
            config.data[key] = value
            changed.append(key)
    if changed:
        config.save()
    return changed


# --------------------------------------------------------------------------- Export / Import
def export_settings(config, sections: list[str]) -> dict:
    keys = [k for s in sections for k in SECTIONS[s][1]]
    return {"app": "AluPC", "version": __version__, "exported": time.strftime("%Y-%m-%d %H:%M"),
            "system": platform.system(), "sections": sections, "data": payload(config, keys)}


def read_export(path: str | Path) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("app") != "AluPC" or not isinstance(data.get("data"), dict):
        raise ValueError("Das ist keine AluPC-Einstellungsdatei.")
    return data


def import_settings(config, exported: dict, sections: list[str]) -> list[str]:
    keys = [k for s in sections for k in SECTIONS[s][1]]
    return apply_payload(config, exported["data"], keys)


def sections_in(exported: dict) -> list[str]:
    data = exported.get("data", {})
    return [name for name, (_label, keys) in SECTIONS.items() if any(k in data for k in keys)]


# --------------------------------------------------------------------------- Dual-Boot-Abgleich
def sync_file(folder: str | Path) -> Path:
    return Path(folder) / FILE_NAME


def _read(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or data.get("app") != "AluPC" or not isinstance(data.get("data"), dict):
        return None
    return data


def _write(path: Path, rev: int, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = {"app": "AluPC", "rev": rev, "system": "Windows" if IS_WINDOWS else "Linux",
           "computer": platform.node(), "written": time.strftime("%Y-%m-%d %H:%M"), "version": __version__,
           "data": data}
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def _set_state(config, **changes) -> None:
    config.data["sync"] = {**config.data["sync"], **changes}
    config.save()


def sync_once(config) -> tuple[str, list[str]]:
    """Einmal abgleichen. Rückgabe: (Meldung, übernommene Schlüssel)."""
    s = config.data["sync"]
    if not s.get("enabled") or not s.get("folder"):
        return "Abgleich ist aus.", []
    folder = Path(s["folder"])
    if not folder.is_dir():
        mount_device(s.get("device", ""), interactive=False)
    if not folder.is_dir():
        msg = "Ordner nicht erreichbar – ist das Windows-Laufwerk eingehängt?" if not IS_WINDOWS else \
            "Ordner nicht erreichbar."
        if s.get("status") != msg:
            _set_state(config, status=msg)
        return msg, []
    path = sync_file(folder)
    remote = _read(path) if path.exists() else None
    remote_rev = int(remote.get("rev", 0)) if remote else 0
    local = payload(config)
    local_hash = payload_hash(local)
    base_rev, dirty = int(s.get("base_rev", 0)), local_hash != s.get("base_hash")
    first = not s.get("base_hash")  # zum ersten Mal verbunden → die vorhandenen Einstellungen übernehmen
    now = time.strftime("%d.%m. %H:%M")
    try:
        if remote and remote_rev > base_rev and (not dirty or first):
            changed = apply_payload(config, remote["data"])
            _set_state(config, base_rev=remote_rev, base_hash=payload_hash(payload(config)), last=now,
                       status=f"Übernommen von {remote.get('system', '?')} ({remote.get('written', '')}).")
            return config.data["sync"]["status"], changed
        if dirty or not remote:
            if remote and remote_rev > base_rev:  # beide Seiten geändert → andere Fassung sichern
                backup = folder / f"alupc-sync-sicherung-{remote_rev}-{remote.get('system', 'x')}.json"
                shutil.copyfile(path, backup)
                note = f" Die Änderungen von {remote.get('system', '?')} liegen als Sicherung daneben."
            else:
                note = ""
            rev = max(remote_rev, base_rev) + 1
            _write(path, rev, local)
            _set_state(config, base_rev=rev, base_hash=local_hash, last=now, status="Gespeichert." + note)
            return config.data["sync"]["status"], []
    except OSError as exc:
        msg = f"Schreiben nicht möglich: {exc.strerror or exc}"
        if not IS_WINDOWS and getattr(exc, "errno", 0) == 30:  # EROFS
            msg = ("Windows-Laufwerk ist nur lesbar – in Windows „Schnellstart“ ausschalten "
                   "(Energieoptionen) und Windows einmal richtig herunterfahren.")
        _set_state(config, status=msg)
        return msg, []
    return "Alles aktuell.", []


# --------------------------------------------------------------------------- Ordner finden
def _mounts() -> list[tuple[str, str]]:
    """Linux: (Einhängepunkt, Dateisystem) der gemeinsam nutzbaren Laufwerke."""
    found = []
    try:
        for line in Path("/proc/mounts").read_text().splitlines():
            parts = line.split()
            if len(parts) >= 3 and parts[2].lower() in SHARED_FS:
                mp = parts[1].replace("\\040", " ")
                if not mp.startswith(("/boot", "/efi")):
                    found.append((mp, parts[2]))
    except OSError:
        pass
    return found


def drives() -> list[str]:
    """Laufwerke, die beide Systeme erreichen können (Windows: Laufwerksbuchstaben)."""
    if IS_WINDOWS:
        return [f"{c}:\\" for c in "CDEFGHIJKLMNOPQRSTUVWXYZ" if os.path.isdir(f"{c}:\\")]
    return [mp for mp, _fs in _mounts()]


def find_existing() -> list[Path]:
    """Schon vorhandene Sync-Ordner (vom anderen System angelegt)."""
    hits = []
    for drive in drives():
        for candidate in (Path(drive) / FOLDER_NAME, Path(drive) / "AluPC" / FOLDER_NAME):
            if sync_file(candidate).is_file():
                hits.append(candidate)
    return hits


def folder_for(choice: str | Path) -> Path:
    """Gewählter Ordner/Laufwerk → Sync-Ordner (legt „AluPC-Sync“ darin an, falls nötig)."""
    p = Path(choice)
    return p if p.name == FOLDER_NAME else p / FOLDER_NAME


def unmounted_partitions() -> list[dict]:
    """Linux: Windows-/Daten-Partitionen, die noch nicht eingehängt sind (für „Einhängen“)."""
    if IS_WINDOWS or not shutil.which("lsblk"):
        return []
    try:
        out = subprocess.run(["lsblk", "-J", "-o", "PATH,FSTYPE,LABEL,MOUNTPOINT,SIZE,UUID"],
                             capture_output=True, text=True, timeout=10).stdout
        devices = json.loads(out).get("blockdevices", [])
    except (OSError, ValueError, subprocess.SubprocessError):
        return []
    result = []

    def walk(items):
        for d in items:
            fs = (d.get("fstype") or "").lower()
            if fs in SHARED_FS and not d.get("mountpoint") and fs not in ("vfat", "msdos", "fat"):
                result.append({"path": d.get("path"), "fstype": fs, "label": d.get("label") or "",
                               "size": d.get("size") or "", "uuid": d.get("uuid") or ""})
            walk(d.get("children") or [])

    walk(devices)
    return result


def device_of(folder: str | Path) -> str:
    """Linux: UUID der Partition eines Ordners (zum automatischen Einhängen beim nächsten Start)."""
    if IS_WINDOWS or not shutil.which("findmnt"):
        return ""
    try:
        return subprocess.run(["findmnt", "-n", "-o", "UUID", "--target", str(folder)],
                              capture_output=True, text=True, timeout=5).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def mount_device(uuid_or_path: str, interactive: bool = True) -> str | None:
    """Linux: Partition über udisks einhängen (wie ein Klick in Dolphin). Rückgabe: Einhängepunkt."""
    if IS_WINDOWS or not uuid_or_path or not shutil.which("udisksctl"):
        return None
    dev = uuid_or_path if uuid_or_path.startswith("/dev/") else f"/dev/disk/by-uuid/{uuid_or_path}"
    if not re.fullmatch(r"/dev/[\w./-]+", dev) or not os.path.exists(dev):
        return None
    args = ["udisksctl", "mount", "-b", dev] + ([] if interactive else ["--no-user-interaction"])
    try:
        out = subprocess.run(args, capture_output=True, text=True, timeout=60 if interactive else 8)
    except (OSError, subprocess.SubprocessError):
        return None
    m = re.search(r" at (.+?)\.?$", out.stdout.strip())
    return m.group(1) if out.returncode == 0 and m else None
