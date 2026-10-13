"""Aufräumen: Die AluPC-Oberfläche (eigener Desktop) gibt es nicht mehr.

Ältere Versionen konnten sich als System-Desktop eintragen – statt Windows-Explorer bzw. KDE-Plasma. Dieses Modul
nimmt das wieder zurück, damit nach dem Update immer der normale Desktop kommt:

* Windows: Benutzer-Eintrag `HKCU\\…\\Winlogon\\Shell` löschen – aber nur, wenn er auf AluPCs Wächter zeigt.
* KDE Plasma: Zusatzdatei (Drop-in) für `plasma-plasmashell.service`, ausgeblendeter Plasma-Autostart und AluPCs
  eigener Desktop-Autostart weg; den normalen Autostart von AluPC (falls er dafür pausiert war) wieder an.

Meldet sich jemand noch mit dem alten Eintrag an (`AluPC --desktop-waechter`), startet sofort der normale Desktop.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

IS_WINDOWS = sys.platform.startswith("win")
WATCH_ARG = "--desktop-waechter"
WINLOGON = r"Software\Microsoft\Windows NT\CurrentVersion\Winlogon"
UNIT = "plasma-plasmashell.service"
DROPIN = "zz-alupc-desktop.conf"
PLASMA_AUTOSTART = "org.kde.plasmashell.desktop"
OWN_AUTOSTART = "alupc-desktop.desktop"
AUTOSTART_MARK = ".alupc-autostart-war-an"


def _run(cmd: list[str], timeout: float = 15) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def _config_home() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")


# --------------------------------------------------------------------------- Windows: Registry
def _reg_get_shell() -> str:
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, WINLOGON) as key:
            return str(winreg.QueryValueEx(key, "Shell")[0])
    except OSError:
        return ""


def _reg_set_shell(value: str) -> None:  # nur für Tests (alten Zustand nachstellen)
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


def _autostart_dir() -> Path:
    return _config_home() / "autostart"


def _plasma_hidden_by_us() -> bool:
    hidden = _autostart_dir() / PLASMA_AUTOSTART
    try:
        return hidden.is_file() and "von AluPC" in hidden.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False


# --------------------------------------------------------------------------- Status / zurücknehmen
def enabled() -> bool:
    """Ist noch ein Eintrag einer älteren Version da (AluPC statt des normalen Desktops)?"""
    if IS_WINDOWS:
        return WATCH_ARG in _reg_get_shell()
    if not sys.platform.startswith("linux"):
        return False
    return dropin_path().is_file() or (_autostart_dir() / OWN_AUTOSTART).is_file() or _plasma_hidden_by_us()


def disable() -> tuple[bool, str]:
    """Alles zurücknehmen – ab der nächsten Anmeldung wieder der normale Desktop."""
    try:
        if IS_WINDOWS:
            if WATCH_ARG in _reg_get_shell():
                _reg_del_shell()
        elif sys.platform.startswith("linux"):
            if dropin_path().is_file():
                dropin_path().unlink()
                try:
                    dropin_path().parent.rmdir()  # nur wenn leer (eigene Zusätze anderer bleiben)
                except OSError:
                    pass
                if shutil.which("systemctl"):
                    _run(["systemctl", "--user", "daemon-reload"])
            if _plasma_hidden_by_us():
                (_autostart_dir() / PLASMA_AUTOSTART).unlink()
            (_autostart_dir() / OWN_AUTOSTART).unlink(missing_ok=True)
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"Ging nicht: {exc}"
    _restore_own_autostart()
    return True, "Wieder der normale Desktop."


def cleanup() -> bool:
    """Beim Start von AluPC: alte Desktop-Einträge entfernen. True = es war etwas da."""
    try:
        if enabled():
            return disable()[0]
    except Exception:  # noqa: BLE001 - darf den Start nie verhindern
        pass
    return False


def _mark() -> Path:
    from ..config import config_dir

    return config_dir() / AUTOSTART_MARK


def _restore_own_autostart() -> None:
    """Der normale Autostart von AluPC war für den Desktop-Modus pausiert – wieder einschalten."""
    from . import autostart

    try:
        if _mark().is_file():
            autostart.set_enabled(True)
            _mark().unlink()
    except OSError:
        pass


# --------------------------------------------------------------------------- Anmeldung mit altem Eintrag
def legacy_login(spawn=None, exec_plasma=None) -> int:
    """`AluPC --desktop-waechter` (alter Eintrag statt Explorer/Plasma): Eintrag entfernen, AluPC normal im
    Hintergrund starten und sofort den normalen Desktop – der Bildschirm bleibt nie leer."""
    cleanup()
    from .autostart import launch_command

    spawn = spawn or (lambda cmd: subprocess.Popen(cmd, start_new_session=not IS_WINDOWS))
    try:
        spawn(launch_command() + ["--minimiert"])
    except OSError:
        pass
    if IS_WINDOWS:  # ohne den Eintrag wird der Explorer wieder zur vollständigen Shell (mit Taskleiste)
        windir = os.environ.get("WINDIR", r"C:\Windows")
        try:
            spawn([os.path.join(windir, "explorer.exe")])
        except OSError:
            return 1
        return 0
    if shutil.which("plasmashell"):  # unter systemd: dieser Dienst wird wieder zu plasmashell
        try:
            (exec_plasma or (lambda: os.execvp("plasmashell", ["plasmashell", "--no-respawn"])))()
        except OSError:
            return 1
    return 0
