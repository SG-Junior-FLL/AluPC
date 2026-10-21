"""PC prüfen: Welche Updates (System, Programme) und Treiber/Firmware stehen an – Windows und Linux gleich.

Nur nachsehen, nichts installieren. Installiert wird mit den Werkzeugen des Systems („Aktualisieren öffnen“):
Windows Update bzw. winget, unter Linux die Software-Verwaltung (Discover, GNOME Software …).

Quellen
    Windows: Windows Update (System + Treiber, über die Update-Schnittstelle von Windows), winget (Programme),
             Geräte mit Problem (Geräte-Manager: Treiber fehlt/defekt)
    Linux:   apt / dnf / pacman (System), Flatpak, Snap, fwupd (Firmware), ubuntu-drivers (empfohlene Treiber),
             PCI-Geräte ohne Treiber (lspci -k)

Ergebnis von scan(): {"updates": [Eintrag], "drivers": [Eintrag], "checked": [Quelle], "errors": [Text]}
Eintrag: {"name", "current", "new", "source", "note"} – nicht jedes Feld ist überall gefüllt.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys

IS_WINDOWS = sys.platform.startswith("win")
_FLAGS = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _run(cmd: list[str], timeout: float = 120) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, timeout=timeout, creationflags=_FLAGS,
                           stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError) as exc:
        return -1, str(exc)
    out = p.stdout or b""
    for enc in ("utf-8", "cp850", "latin-1"):
        try:
            return p.returncode, out.decode(enc)
        except UnicodeDecodeError:
            continue
    return p.returncode, out.decode("utf-8", "replace")


def _ps(script: str, timeout: float = 300) -> tuple[int, str]:
    return _run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command",
                 "[Console]::OutputEncoding=[Text.Encoding]::UTF8; " + script], timeout)


def _item(name, current="", new="", source="", note="") -> dict:
    return {"name": str(name).strip(), "current": str(current or "").strip(), "new": str(new or "").strip(),
            "source": source, "note": str(note or "").strip()}


def _json_list(text: str) -> list:
    text = text.strip()
    if not text:
        return []
    data = json.loads(text)
    return data if isinstance(data, list) else [data]


# =========================================================================== Windows
def parse_winget(text: str) -> list[dict]:
    """Tabelle von „winget upgrade“ (Spalten je nach Sprache: Name Id Version Verfügbar Quelle)."""
    lines = [ln.rstrip() for ln in text.replace("\r", "\n").split("\n")]
    sep = next((i for i, ln in enumerate(lines) if ln and set(ln.strip()) == {"-"} and len(ln.strip()) > 10), None)
    if sep is None or sep == 0:
        return []
    header = lines[sep - 1]
    starts = [m.start() for m in re.finditer(r"\S+", header)]
    if len(starts) < 4:
        return []
    out = []
    for ln in lines[sep + 1:]:
        if not ln.strip() or len(ln) < starts[3]:
            break  # Ende der Tabelle („3 Aktualisierungen verfügbar.“)
        cols = [ln[a:b].strip() for a, b in zip(starts, starts[1:] + [None])]
        name, ident, cur, new = cols[0], cols[1], cols[2], cols[3]
        if not ident or not new:
            continue
        out.append(_item(name, cur, new, "winget", ident))
    return out


def _win_updates() -> tuple[list, list]:
    """Windows Update: ausstehende System-Updates und Treiber (Type 2)."""
    code, out = _ps(
        "$s = New-Object -ComObject Microsoft.Update.Session; "
        "$r = $s.CreateUpdateSearcher().Search('IsInstalled=0 and IsHidden=0'); "
        "@($r.Updates | ForEach-Object { [pscustomobject]@{ T = $_.Title; K = [int]$_.Type; "
        "D = ($_.DriverVerDate -as [string]) } }) | ConvertTo-Json -Compress", timeout=400)
    if code != 0:
        raise RuntimeError("Windows Update: " + (out.strip().splitlines() or ["keine Antwort"])[-1][:160])
    updates, drivers = [], []
    for u in _json_list(out):
        (drivers if u.get("K") == 2 else updates).append(_item(u.get("T", "?"), source="Windows Update"))
    return updates, drivers


def _win_problem_devices() -> list[dict]:
    code, out = _ps("@(Get-CimInstance Win32_PnPEntity | Where-Object { $_.ConfigManagerErrorCode -ne 0 } | "
                    "Select-Object Name, ConfigManagerErrorCode, PNPClass) | ConvertTo-Json -Compress", timeout=60)
    if code != 0:
        raise RuntimeError("Geräte-Manager: keine Antwort")
    texts = {1: "nicht richtig eingerichtet", 10: "startet nicht", 22: "deaktiviert", 28: "kein Treiber installiert",
             31: "Treiber lädt nicht", 43: "meldet einen Fehler", 45: "nicht angeschlossen"}
    out_list = []
    for d in _json_list(out):
        code_ = int(d.get("ConfigManagerErrorCode") or 0)
        if code_ in (22, 45):  # absichtlich aus bzw. gerade nicht eingesteckt – kein Treiberproblem
            continue
        out_list.append(_item(d.get("Name") or "Unbekanntes Gerät", source="Geräte-Manager",
                              note=texts.get(code_, f"Fehlercode {code_}")))
    return out_list


def _scan_windows(result: dict, progress) -> None:
    progress("Windows Update wird gefragt (kann 1–2 Minuten dauern) …")
    try:
        u, d = _win_updates()
        result["updates"] += u
        result["drivers"] += d
        result["checked"].append("Windows Update")
    except Exception as exc:  # noqa: BLE001
        result["errors"].append(str(exc))
    progress("Programme (winget) …")
    if shutil.which("winget"):
        code, out = _run(["winget", "upgrade", "--include-unknown", "--accept-source-agreements",
                          "--disable-interactivity"], timeout=180)
        if code == -1:
            result["errors"].append("winget: " + out[:160])
        else:
            result["updates"] += parse_winget(out)
            result["checked"].append("winget")
    else:
        result["errors"].append("winget fehlt (App „App-Installer“ aus dem Microsoft Store) – Programme nicht geprüft.")
    progress("Geräte und Treiber …")
    try:
        result["drivers"] += _win_problem_devices()
        result["checked"].append("Geräte-Manager")
    except Exception as exc:  # noqa: BLE001
        result["errors"].append(str(exc))


# =========================================================================== Linux
def parse_apt(text: str) -> list[dict]:
    """„apt list --upgradable“: name/suite neu arch [upgradable from: alt]"""
    out = []
    for ln in text.splitlines():
        m = re.match(r"^([^/\s]+)/\S+\s+(\S+)\s+\S+\s+\[[^:\]]*:\s*([^\]]+)\]", ln.strip())
        if m:
            out.append(_item(m.group(1), m.group(3), m.group(2), "apt"))
    return out


def parse_dnf(text: str) -> list[dict]:
    """„dnf check-update -q“: name.arch  version  repo"""
    out = []
    for ln in text.splitlines():
        parts = ln.split()
        if len(parts) == 3 and "." in parts[0] and not ln.startswith(" ") and parts[0][0].isalnum():
            if parts[0].lower().startswith(("obsoleting", "security")):
                continue
            out.append(_item(parts[0].rsplit(".", 1)[0], "", parts[1], "dnf"))
    return out


def parse_pacman(text: str) -> list[dict]:
    """„checkupdates“: name alt -> neu"""
    out = []
    for ln in text.splitlines():
        m = re.match(r"^(\S+)\s+(\S+)\s+->\s+(\S+)", ln.strip())
        if m:
            out.append(_item(m.group(1), m.group(2), m.group(3), "pacman"))
    return out


def parse_flatpak(text: str) -> list[dict]:
    """„flatpak remote-ls --updates --columns=name,application,version“ (Tabulator getrennt)"""
    out = []
    for ln in text.splitlines():
        parts = [p.strip() for p in ln.split("\t")]
        if len(parts) >= 2 and parts[1] and "." in parts[1]:
            out.append(_item(parts[0] or parts[1], "", parts[2] if len(parts) > 2 else "", "Flatpak", parts[1]))
    return out


def parse_snap(text: str) -> list[dict]:
    """„snap refresh --list“: Name Version Rev Publisher Notes (erste Zeile Kopf)"""
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines or not lines[0].lower().startswith("name"):
        return []
    return [_item(ln.split()[0], "", ln.split()[1], "Snap") for ln in lines[1:] if len(ln.split()) >= 2]


def parse_fwupd(text: str) -> list[dict]:
    """„fwupdmgr get-updates --json“: Geräte mit neuerer Firmware"""
    try:
        data = json.loads(text)
    except ValueError:
        return []
    out = []
    for dev in data.get("Devices", []) or []:
        rel = (dev.get("Releases") or [{}])[0]
        if rel.get("Version"):
            out.append(_item(dev.get("Name", "Gerät"), dev.get("Version", ""), rel.get("Version"), "Firmware (fwupd)"))
    return out


def parse_ubuntu_drivers(text: str) -> list[dict]:
    """„ubuntu-drivers list“: empfohlene (meist herstellereigene) Treiber, z. B. nvidia-driver-550"""
    out = []
    for ln in text.splitlines():
        name = ln.split(",")[0].strip()
        if name and re.match(r"^[a-z0-9][a-z0-9.+-]+$", name):
            out.append(_item(name, source="ubuntu-drivers", note="Empfohlener Treiber, noch nicht installiert"))
    return out


def parse_lspci(text: str) -> list[dict]:
    """„lspci -k“: wichtige Geräte (Grafik, Netzwerk, WLAN, Ton) ohne geladenen Treiber"""
    out, dev, has_driver = [], None, False
    important = ("vga", "3d controller", "display", "network", "ethernet", "wireless", "audio", "bluetooth")

    def flush():
        if dev and not has_driver and any(w in dev.lower() for w in important):
            out.append(_item(dev.split(": ", 1)[-1], source="lspci", note="Kein Treiber geladen"))

    for ln in text.splitlines():
        if ln and not ln[0].isspace():
            flush()
            dev, has_driver = ln.split(" ", 1)[-1], False
        elif "kernel driver in use" in ln.lower():
            has_driver = True
    flush()
    return out


LINUX_SOURCES = [
    # (Name, Programm, Befehl, Auswertung, Liste, Zeitlimit)
    ("apt", "apt", ["apt", "list", "--upgradable"], parse_apt, "updates", 60),
    ("dnf", "dnf", ["dnf", "check-update", "-q"], parse_dnf, "updates", 180),
    ("pacman", "checkupdates", ["checkupdates"], parse_pacman, "updates", 120),
    ("Flatpak", "flatpak", ["flatpak", "remote-ls", "--updates", "--columns=name,application,version"],
     parse_flatpak, "updates", 120),
    ("Snap", "snap", ["snap", "refresh", "--list"], parse_snap, "updates", 60),
    ("Firmware", "fwupdmgr", ["fwupdmgr", "get-updates", "--json"], parse_fwupd, "drivers", 120),
    ("Treiber", "ubuntu-drivers", ["ubuntu-drivers", "list"], parse_ubuntu_drivers, "drivers", 60),
    ("Geräte", "lspci", ["lspci", "-k"], parse_lspci, "drivers", 20),
]


def _scan_linux(result: dict, progress, run=_run, which=shutil.which) -> None:
    for label, prog, cmd, parse, key, timeout in LINUX_SOURCES:
        if not which(prog):
            continue
        progress(f"{label} …")
        code, out = run(cmd, timeout)
        if code == -1:
            result["errors"].append(f"{label}: {out[:160]}")
            continue
        result[key] += parse(out)
        result["checked"].append(label)
    if not any(s in result["checked"] for s in ("apt", "dnf", "pacman")):
        result["errors"].append("Keine bekannte Paketverwaltung (apt, dnf, pacman) gefunden – System nicht geprüft.")


# =========================================================================== gemeinsam
def scan(progress=None) -> dict:
    """Alles prüfen (dauert je nach System 10 s bis 2 min). progress(text) meldet den Schritt."""
    progress = progress or (lambda _t: None)
    result: dict = {"updates": [], "drivers": [], "checked": [], "errors": []}
    if IS_WINDOWS:
        _scan_windows(result, progress)
    else:
        _scan_linux(result, progress)
    return result


def open_updater(kind: str = "updates") -> tuple[bool, str]:
    """Aktualisieren mit den Werkzeugen des Systems öffnen. kind: updates | drivers | programme"""
    if IS_WINDOWS:
        if kind == "programme" and shutil.which("winget"):
            # sichtbares Fenster: man sieht, was passiert, und kann abbrechen
            subprocess.Popen(["cmd", "/c", "start", "AluPC – Programme aktualisieren", "cmd", "/k",
                              "winget upgrade --all --include-unknown --accept-source-agreements"])
            return True, "winget aktualisiert die Programme im neuen Fenster."
        target = "ms-settings:windowsupdate-optionalupdates" if kind == "drivers" else "ms-settings:windowsupdate"
        import os

        os.startfile(target)  # noqa: S606 - Windows-Einstellungen öffnen
        return True, "Windows Update geöffnet."
    for cmd in (["plasma-discover", "--mode", "update"], ["gnome-software", "--mode=updates"], ["update-manager"],
                ["mintupdate"], ["pamac-manager", "--updates"]):
        if shutil.which(cmd[0]):
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            return True, "Software-Aktualisierung geöffnet."
    return False, "Keine Software-Verwaltung gefunden – im Terminal z. B. „sudo apt upgrade“."
