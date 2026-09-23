"""Autostart beim Anmelden ein- und ausschalten."""

from __future__ import annotations

import os
import sys
from pathlib import Path

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "AluPC"


def launch_command() -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable]
    exe = sys.executable
    if sys.platform.startswith("win") and exe.lower().endswith("python.exe"):
        pythonw = exe[:-10] + "pythonw.exe"
        if os.path.exists(pythonw):
            exe = pythonw  # ohne schwarzes Konsolenfenster
    return [exe, "-m", "alupc"]


def _quote(parts: list[str]) -> str:
    return " ".join(f'"{p}"' if " " in p else p for p in parts)


def _desktop_file() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "autostart" / "alupc.desktop"


def is_enabled() -> bool:
    if sys.platform.startswith("win"):
        import winreg

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
                winreg.QueryValueEx(key, VALUE_NAME)
                return True
        except OSError:
            return False
    return _desktop_file().exists()


def set_enabled(enabled: bool) -> None:
    command = _quote(launch_command() + ["--minimiert"])
    if sys.platform.startswith("win"):
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            if enabled:
                winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, command)
            else:
                try:
                    winreg.DeleteValue(key, VALUE_NAME)
                except OSError:
                    pass
        return
    path = _desktop_file()
    if enabled:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "[Desktop Entry]\nType=Application\nName=AluPC\n"
            f"Exec={command}\nIcon=video-display\nX-GNOME-Autostart-enabled=true\n",
            encoding="utf-8",
        )
    elif path.exists():
        path.unlink()
