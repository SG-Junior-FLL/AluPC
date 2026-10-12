"""AluPC-Oberfläche als System-Desktop – statt Windows-Explorer bzw. KDE-Plasma (plasmashell), mit Knopf zurück.

Bei jeder Anmeldung startet dann statt des normalen Desktops der **Wächter** (`AluPC --desktop-waechter`). Er startet
AluPC mit der Oberfläche als Desktop (`--desktop`) und wartet. Endet AluPC – Absturz oder „Beenden“ –, startet er
sofort den normalen Desktop: so bleibt der Bildschirm nie schwarz.

* Windows: Benutzer-Eintrag `HKCU\\…\\Winlogon\\Shell` (gilt nur für diesen Benutzer, ohne Administrator). Ohne ihn
  nimmt Windows wieder den Explorer. Den Explorer gibt es weiter: „Normaler Desktop“ startet ihn (den Eintrag dafür
  kurz entfernen, sonst öffnet er nur ein Dateifenster), „AluPC-Desktop“ beendet ihn wieder.
* KDE Plasma mit systemd (Standard seit Plasma 5.25): Zusatz-Datei (Drop-in) für `plasma-plasmashell.service` –
  statt plasmashell läuft der Wächter. Ohne systemd-Start: plasmashell im Autostart ausblenden, Wächter eintragen.
  KWin (Fenster, Alt+Tab) läuft immer weiter.
* GNOME u. a.: geht nicht (dort ist die Oberfläche zugleich der Fenstermanager).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

IS_WINDOWS = sys.platform.startswith("win")
WATCH_ARG = "--desktop-waechter"
CHILD_ARG = "--desktop"
HANDED_OVER = 75  # Kind-Prozess: AluPC lief schon und übernimmt – Wächter macht nichts weiter
WINLOGON = r"Software\Microsoft\Windows NT\CurrentVersion\Winlogon"
UNIT = "plasma-plasmashell.service"
NORMAL_UNIT = "alupc-plasma-normal"
DROPIN = "zz-alupc-desktop.conf"
PLASMA_AUTOSTART = "org.kde.plasmashell.desktop"
OWN_AUTOSTART = "alupc-desktop.desktop"
AUTOSTART_MARK = ".alupc-autostart-war-an"


def _run(cmd: list[str], timeout: float = 15) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def _config_home() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")


def command(arg: str) -> list[str]:
    from .autostart import launch_command

    return launch_command() + [arg]


def _quote(parts: list[str]) -> str:
    return " ".join(f'"{p}"' if " " in p else p for p in parts)


# --------------------------------------------------------------------------- Welches System?
def is_kde() -> bool:
    return "KDE" in os.environ.get("XDG_CURRENT_DESKTOP", "").upper() or shutil.which("plasmashell") is not None


def kde_systemd() -> bool:
    """Startet Plasma über systemd (dann gibt es plasma-plasmashell.service)?"""
    if not shutil.which("systemctl"):
        return False
    try:
        if _run(["systemctl", "--user", "cat", UNIT], 10).returncode != 0:
            return False
    except (OSError, subprocess.SubprocessError):
        return False
    rc = _config_home() / "startkderc"
    try:  # Benutzer kann den systemd-Start abschalten ([General] systemdBoot=false)
        if "systemdboot=false" in rc.read_text(encoding="utf-8").replace(" ", "").lower():
            return False
    except OSError:
        pass
    return True


def kind() -> str:
    """"windows", "kde-systemd", "kde" (ohne systemd) oder "" (nicht möglich)."""
    if IS_WINDOWS:
        return "windows"
    if sys.platform.startswith("linux") and is_kde():
        return "kde-systemd" if kde_systemd() else "kde"
    return ""


# --------------------------------------------------------------------------- Windows: Registry
def _reg_get_shell() -> str:
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, WINLOGON) as key:
            return str(winreg.QueryValueEx(key, "Shell")[0])
    except OSError:
        return ""


def _reg_set_shell(value: str) -> None:
    import winreg

    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, WINLOGON, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, "Shell", 0, winreg.REG_SZ, value)


def _reg_del_shell() -> None:
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, WINLOGON, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, "Shell")
    except OSError:
        pass


# --------------------------------------------------------------------------- KDE: Dateien
def dropin_path() -> Path:
    return _config_home() / "systemd" / "user" / f"{UNIT}.d" / DROPIN


def fallback_line(cmd: list[str]) -> str:
    """Wächter starten – fehlt AluPC (deinstalliert, verschoben) oder geht es nicht, sofort plasmashell."""
    import shlex

    return f"{shlex.join(cmd)} || exec plasmashell --no-respawn"


def dropin_text(cmd: list[str]) -> str:
    # Type=simple: der Wächter meldet sich nicht als org.kde.plasmashell auf dem D-Bus (Type=dbus würde warten
    # und ihn nach 40 s beenden). systemd ersetzt %/$ selbst – darum verdoppeln.
    line = fallback_line(cmd).replace("%", "%%").replace("$", "$$")
    return ("# Von AluPC angelegt: AluPC-Oberfläche statt plasmashell. Löschen = wieder normaler Plasma-Desktop.\n"
            "[Service]\nType=simple\nExecStart=\n"
            f'ExecStart=/bin/sh -c "{line}"\n')


def _autostart_dir() -> Path:
    return _config_home() / "autostart"


def _plasma_hidden_text() -> str:
    return ("[Desktop Entry]\nType=Application\nName=Plasma (von AluPC ausgeblendet)\nExec=plasmashell\n"
            "Hidden=true\n")


def _own_autostart_text(cmd: list[str]) -> str:
    line = fallback_line(cmd).replace("\\", "\\\\").replace('"', '\\"').replace("$", "\\$")
    return ("[Desktop Entry]\nType=Application\nName=AluPC-Desktop\n"
            f'Exec=/bin/sh -c "{line}"\nX-KDE-autostart-phase=0\nOnlyShowIn=KDE;\n')


# --------------------------------------------------------------------------- Status / an / aus
def enabled() -> bool:
    k = kind()
    if k == "windows":
        return WATCH_ARG in _reg_get_shell()
    if k == "kde-systemd":
        return dropin_path().is_file()
    if k == "kde":
        return (_autostart_dir() / OWN_AUTOSTART).is_file()
    return False


def status() -> dict:
    k = kind()
    why = {"windows": "Statt des Windows-Explorers (nur für diesen Benutzer).",
           "kde-systemd": "Statt Plasma (plasmashell) – KWin, Alt+Tab und Programme bleiben.",
           "kde": "Statt Plasma (plasmashell) – KWin, Alt+Tab und Programme bleiben.",
           "": "Geht nur unter Windows und KDE Plasma (GNOME u. a.: Oberfläche und Fenstermanager sind eins)."}[k]
    return {"kind": k, "supported": bool(k), "why": why, "enabled": enabled() if k else False}


def enable() -> tuple[bool, str]:
    """Ab der nächsten Anmeldung: AluPC-Oberfläche statt des normalen Desktops."""
    k = kind()
    cmd = command(WATCH_ARG)
    try:
        if k == "windows":
            _reg_set_shell(_quote(cmd))
            if _reg_get_shell() != _quote(cmd):
                return False, "Der Eintrag ließ sich nicht speichern."
        elif k == "kde-systemd":
            p = dropin_path()
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(dropin_text(cmd), encoding="utf-8")
            _run(["systemctl", "--user", "daemon-reload"])
        elif k == "kde":
            d = _autostart_dir()
            d.mkdir(parents=True, exist_ok=True)
            (d / PLASMA_AUTOSTART).write_text(_plasma_hidden_text(), encoding="utf-8")
            (d / OWN_AUTOSTART).write_text(_own_autostart_text(cmd), encoding="utf-8")
        else:
            return False, status()["why"]
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"Ging nicht: {exc}"
    _pause_own_autostart()
    return True, "Ab der nächsten Anmeldung startet die AluPC-Oberfläche als Desktop."


def refresh() -> bool:
    """Beim Start: ist AluPC als Desktop eingetragen, aber woanders hin verschoben/aktualisiert worden, den Eintrag
    auf den jetzigen Ort setzen (sonst startet bei der Anmeldung ein Programm, das es dort nicht mehr gibt)."""
    k = kind()
    try:
        if k == "windows" and WATCH_ARG in _reg_get_shell() and _reg_get_shell() != _quote(command(WATCH_ARG)):
            _reg_set_shell(_quote(command(WATCH_ARG)))
            return True
        if k == "kde-systemd" and dropin_path().is_file() and \
                dropin_path().read_text(encoding="utf-8") != dropin_text(command(WATCH_ARG)):
            dropin_path().write_text(dropin_text(command(WATCH_ARG)), encoding="utf-8")
            _run(["systemctl", "--user", "daemon-reload"])
            return True
        own = _autostart_dir() / OWN_AUTOSTART
        if k == "kde" and own.is_file() and own.read_text(encoding="utf-8") != _own_autostart_text(command(WATCH_ARG)):
            own.write_text(_own_autostart_text(command(WATCH_ARG)), encoding="utf-8")
            return True
    except (OSError, subprocess.SubprocessError):
        pass
    return False


def disable() -> tuple[bool, str]:
    """Wieder der normale Desktop ab der nächsten Anmeldung (alles von AluPC Angelegte weg)."""
    k = kind()
    try:
        if k == "windows":
            if WATCH_ARG in _reg_get_shell():
                _reg_del_shell()
        elif k in ("kde-systemd", "kde"):
            dropin_path().unlink(missing_ok=True)
            try:
                dropin_path().parent.rmdir()  # nur wenn leer (eigene Zusätze anderer bleiben)
            except OSError:
                pass
            if shutil.which("systemctl"):
                _run(["systemctl", "--user", "daemon-reload"])
            hidden = _autostart_dir() / PLASMA_AUTOSTART
            if hidden.is_file() and "von AluPC" in hidden.read_text(encoding="utf-8", errors="replace"):
                hidden.unlink()
            (_autostart_dir() / OWN_AUTOSTART).unlink(missing_ok=True)
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"Ging nicht: {exc}"
    _restore_own_autostart()
    return True, "Ab der nächsten Anmeldung wieder der normale Desktop."


def _mark() -> Path:
    from ..config import config_dir

    return config_dir() / AUTOSTART_MARK


def _pause_own_autostart() -> None:
    """Der Wächter startet AluPC schon – der normale Autostart käme doppelt (unter Linux gleichzeitig)."""
    from . import autostart

    try:
        if autostart.is_enabled():
            autostart.set_enabled(False)
            _mark().parent.mkdir(parents=True, exist_ok=True)
            _mark().write_text("1", encoding="utf-8")
    except OSError:
        pass


def _restore_own_autostart() -> None:
    from . import autostart

    try:
        if _mark().is_file():
            autostart.set_enabled(True)
            _mark().unlink()
    except OSError:
        pass


# --------------------------------------------------------------------------- Normaler Desktop (in dieser Sitzung)
def in_plasma_unit() -> bool:
    """Läuft dieses AluPC selbst als plasma-plasmashell.service (vom Wächter gestartet)?"""
    try:
        return UNIT in Path("/proc/self/cgroup").read_text()
    except OSError:
        return False


def normal_running() -> bool:
    if IS_WINDOWS:
        return _tray_window() != 0
    try:
        return _run(["pgrep", "-x", "plasmashell"], 5).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _tray_window() -> int:
    import ctypes

    return int(ctypes.windll.user32.FindWindowW("Shell_TrayWnd", None) or 0)


def start_normal(wait: float = 10.0) -> tuple[bool, str]:
    """Normalen Desktop jetzt starten (Explorer bzw. plasmashell). AluPC läuft weiter."""
    k = kind()
    if normal_running():
        return True, "Der normale Desktop läuft schon."
    try:
        if k == "windows":
            return _start_explorer(wait)
        if k == "kde-systemd":
            if dropin_path().is_file() or in_plasma_unit():
                # der Dienst ist gerade AluPC → plasmashell als eigener, kurzlebiger Dienst
                _run(["systemd-run", "--user", f"--unit={NORMAL_UNIT}", "--collect", "plasmashell", "--no-respawn"])
            else:
                _run(["systemctl", "--user", "start", UNIT], 30)
        elif k == "kde":
            subprocess.Popen(["plasmashell"], start_new_session=True, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
        else:
            return False, status()["why"]
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"Normaler Desktop startet nicht: {exc}"
    end = time.monotonic() + wait
    while time.monotonic() < end and not normal_running():
        time.sleep(0.3)
    return (True, "Normaler Desktop läuft.") if normal_running() else \
        (False, "Der normale Desktop hat nicht gestartet.")


def _start_explorer(wait: float) -> tuple[bool, str]:
    # Der Explorer wird nur dann zum Desktop (mit Taskleiste), wenn er sich für die Shell hält – dafür den
    # AluPC-Eintrag kurz entfernen und danach wiederherstellen (sonst öffnet er nur ein Dateifenster)
    saved = _reg_get_shell()
    ours = WATCH_ARG in saved
    if ours:
        _reg_del_shell()
    try:
        windir = os.environ.get("WINDIR", r"C:\Windows")
        subprocess.Popen([os.path.join(windir, "explorer.exe")], cwd=windir)
        end = time.monotonic() + wait
        while time.monotonic() < end and not _tray_window():
            time.sleep(0.3)
        time.sleep(1.0)  # Explorer liest den Eintrag beim Start – erst danach zurück
    finally:
        if ours:
            _reg_set_shell(saved)
    if _tray_window():
        return True, "Normaler Desktop (Explorer) läuft."
    return False, ("Der Explorer kam nur als Dateifenster, nicht als Desktop. Abmelden und neu anmelden – oder "
                   "unter „Anpassen“ den AluPC-Desktop ausschalten.")


def stop_normal() -> tuple[bool, str]:
    """Normalen Desktop beenden (AluPC-Desktop übernimmt wieder)."""
    k = kind()
    try:
        if k == "windows":
            if _tray_window():
                _run(["taskkill", "/f", "/im", "explorer.exe"])
        elif k == "kde-systemd":
            active = _run(["systemctl", "--user", "is-active", f"{NORMAL_UNIT}.service"], 5).stdout.strip()
            if active == "active":
                _run(["systemctl", "--user", "stop", f"{NORMAL_UNIT}.service"], 30)
            elif not dropin_path().is_file() and not in_plasma_unit():
                _run(["systemctl", "--user", "stop", UNIT], 30)
        if not IS_WINDOWS and normal_running():  # ohne systemd oder anders gestartet
            for quit_cmd in (["kquitapp6", "plasmashell"], ["kquitapp5", "plasmashell"], ["pkill", "-x", "plasmashell"]):
                if shutil.which(quit_cmd[0]):
                    _run(quit_cmd, 20)
                    if not normal_running():
                        break
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"Ging nicht: {exc}"
    time.sleep(0.5)
    return (False, "Der normale Desktop läuft noch.") if normal_running() else (True, "AluPC-Desktop ist zurück.")


# --------------------------------------------------------------------------- Wächter
def watchdog(child: list[str] | None = None, start=None) -> int:
    """Läuft statt des normalen Desktops: AluPC starten; endet es (Absturz, „Beenden“), den normalen Desktop
    starten, damit der Bildschirm nie leer bleibt."""
    try:
        code = subprocess.call(child or command(CHILD_ARG))
    except OSError:
        code = -1
    if code == HANDED_OVER:  # AluPC lief schon (z. B. selbst gestartet) und zeigt den Desktop
        return 0
    if start is not None:
        start()
        return 0
    if not IS_WINDOWS and kind():
        try:  # unter systemd: dieser Dienst wird zu plasmashell (gleiches Verhalten wie ohne AluPC)
            os.execvp("plasmashell", ["plasmashell", "--no-respawn"])
        except OSError:
            return 1
    start_normal()
    return 0


# --------------------------------------------------------------------------- Windows: Autostart-Programme
RUN_KEYS = [r"Software\Microsoft\Windows\CurrentVersion\Run",
            r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Run"]
APPROVED = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved"


def _expand(cmd: str) -> str:
    """%ProgramFiles% & Co. ersetzen (wie Windows) – unbekannte bleiben stehen."""
    import re

    return re.sub(r"%([^%]+)%", lambda m: os.environ.get(m.group(1), m.group(0)), cmd)


def startup_entries(run_values: list[tuple[str, str]], folder_items: list[str], disabled: set[str]) -> list[str]:
    """Was der Explorer sonst bei der Anmeldung startet – ohne AluPC selbst und ohne abgeschaltete (Task-Manager →
    Autostart). Rückgabe: Befehlszeilen bzw. Dateien."""
    out = []
    for name, cmd in run_values:
        if name in disabled or "alupc" in (name + cmd).lower():
            continue
        out.append(_expand(cmd))
    for path in folder_items:
        name = path.replace("\\", "/").rsplit("/", 1)[-1]  # Windows-Pfade auch unter Linux (Tests)
        if name in disabled or "alupc" in name.lower() or name.lower() == "desktop.ini":
            continue
        out.append(path)
    return out


def _approved_disabled() -> set[str]:
    import winreg

    off = set()
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for sub in ("Run", "Run32", "StartupFolder"):
            try:
                with winreg.OpenKey(hive, APPROVED + "\\" + sub) as key:
                    i = 0
                    while True:
                        try:
                            name, data, _t = winreg.EnumValue(key, i)
                        except OSError:
                            break
                        if isinstance(data, bytes) and data and data[0] & 1:  # 03 … = im Task-Manager abgeschaltet
                            off.add(name)
                        i += 1
            except OSError:
                continue
    return off


def run_startup_programs() -> list[str]:
    """Windows ohne Explorer: Autostart-Programme selbst starten (sonst tut das der Explorer)."""
    if not IS_WINDOWS:
        return []
    import winreg

    values = []
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for sub in RUN_KEYS:
            try:
                with winreg.OpenKey(hive, sub) as key:
                    i = 0
                    while True:
                        try:
                            name, data, _t = winreg.EnumValue(key, i)
                        except OSError:
                            break
                        if isinstance(data, str) and data.strip():
                            values.append((name, data))
                        i += 1
            except OSError:
                continue
    folders = [Path(os.environ.get("APPDATA", "")) / r"Microsoft\Windows\Start Menu\Programs\Startup",
               Path(os.environ.get("PROGRAMDATA", "")) / r"Microsoft\Windows\Start Menu\Programs\StartUp"]
    items = [str(p) for d in folders if d.is_dir() for p in sorted(d.iterdir()) if p.is_file()]
    started = []
    for entry in startup_entries(values, items, _approved_disabled()):
        try:
            if os.path.isfile(entry):
                os.startfile(entry)  # type: ignore[attr-defined]
            else:
                subprocess.Popen(entry)
            started.append(entry)
        except OSError:
            continue
    return started


def set_work_area(left: int, top: int, right: int, bottom: int) -> bool:
    """Windows: Bereich für maximierte Fenster (ohne Explorer-Taskleiste reserviert sonst niemand Platz)."""
    if not IS_WINDOWS:
        return False
    import ctypes
    from ctypes import wintypes

    rect = wintypes.RECT(left, top, right, bottom)
    return bool(ctypes.windll.user32.SystemParametersInfoW(0x002F, 0, ctypes.byref(rect), 0x02))
