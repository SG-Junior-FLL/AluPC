"""Dual-Boot: Dateipfade vom anderen System finden (Szene/Mediathek unter Windows angelegt → unter Linux zeigen).

Windows „C:\\Users\\Noah\\Videos\\a.mp4“ gibt es unter Linux nicht – dort ist das Windows-Laufwerk z. B. unter
„/media/noah/Windows“ eingehängt. Laufwerksbuchstaben kennt Linux nicht, darum wird der Rest des Pfads
(„Users/Noah/Videos/a.mp4“) auf jedem eingehängten Windows-Laufwerk gesucht. Umgekehrt (Linux-Pfad auf einem
Windows-Laufwerk, z. B. „/media/noah/Daten/Filme/a.mp4“) wird „Filme/a.mp4“ auf C:, D:, … gesucht.
Linux-Laufwerke (ext4) kann Windows nicht lesen – solche Pfade bleiben, wie sie sind.
"""

from __future__ import annotations

import os
import re
import sys

IS_WINDOWS = sys.platform.startswith("win")
_WIN_PATH = re.compile(r"^[A-Za-z]:[\\/](.*)$")
_LINUX_MOUNT = re.compile(r"^/(?:run/media/[^/]+/[^/]+|media/[^/]+/[^/]+|mnt/[^/]+)/(.+)$")
_mount_tried = False


def relative_part(path: str) -> str | None:
    """Teil des Pfads ohne Laufwerk/Einhängepunkt – oder None, wenn der Pfad nicht vom anderen System ist."""
    m = _WIN_PATH.match(path)
    if m:
        return m.group(1).replace("\\", "/").strip("/") or None
    m = _LINUX_MOUNT.match(path.replace("\\", "/"))
    return m.group(1).strip("/") if m else None


def _find_case_insensitive(root: str, rel: str) -> str | None:
    """Windows kennt keine Groß-/Kleinschreibung – Linux schon. Darum Stück für Stück passend suchen."""
    current = root
    for part in [p for p in rel.split("/") if p]:
        exact = os.path.join(current, part)
        if os.path.exists(exact):
            current = exact
            continue
        try:
            names = os.listdir(current)
        except OSError:
            return None
        match = next((n for n in names if n.lower() == part.lower()), None)
        if match is None:
            return None
        current = os.path.join(current, match)
    return current


def candidates_roots() -> list[str]:
    """Wo das andere System liegen kann: Windows = Laufwerksbuchstaben, Linux = eingehängte NTFS/exFAT."""
    from ..settings_sync import drives

    return drives()


def resolve(path: str, roots: list[str] | None = None, mount: bool = True) -> str:
    """Pfad, der auf diesem System wirklich existiert – sonst unverändert zurück."""
    global _mount_tried
    if not path or os.path.exists(path):
        return path
    rel = relative_part(path)
    if not rel:
        return path
    for attempt in range(2):
        for root in (roots if roots is not None else candidates_roots()):
            hit = _find_case_insensitive(root, rel)
            if hit:
                return hit
        # Linux: Windows-Laufwerk ist noch nicht eingehängt → einmal versuchen (ohne Passwort-Abfrage)
        if attempt or roots is not None or IS_WINDOWS or not mount or _mount_tried:
            break
        _mount_tried = True
        if not _mount_windows_drives():
            break
    return path


def _mount_windows_drives() -> bool:
    from ..settings_sync import mount_device, unmounted_partitions

    mounted = False
    for part in unmounted_partitions():
        if mount_device(part.get("uuid") or part.get("path", ""), interactive=False):
            mounted = True
    return mounted


def resolve_cfg(cfg: dict) -> dict:
    """Quellen-Einstellung (Bild/Video/Diashow) mit passendem Pfad für dieses System."""
    key = "folder" if cfg.get("type") == "slideshow" else "path"
    value = cfg.get(key)
    if not isinstance(value, str) or not value:
        return cfg
    found = resolve(value)
    return cfg if found == value else {**cfg, key: found}
