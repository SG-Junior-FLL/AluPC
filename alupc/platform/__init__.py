"""Systemschicht: wählt passend zum Betriebssystem die richtigen Umsetzungen aus."""

from __future__ import annotations

import sys

from .base import DisplayBackend, FingerprintBackend, WindowBackend

IS_WINDOWS = sys.platform.startswith("win")
IS_LINUX = sys.platform.startswith("linux")


def create_display_backend() -> DisplayBackend:
    if IS_WINDOWS:
        from .windows_display import WindowsDisplayBackend

        return WindowsDisplayBackend()
    if IS_LINUX:
        from .linux_display import create_display_backend as linux_backend

        return linux_backend()
    return DisplayBackend()


def create_window_backend() -> WindowBackend:
    try:
        if IS_WINDOWS:
            from .windows_windows import WindowsWindowBackend

            return WindowsWindowBackend()
        if IS_LINUX:
            from .linux_windows import LinuxWindowBackend

            return LinuxWindowBackend()
    except Exception:  # noqa: BLE001
        pass
    return WindowBackend()


def create_fingerprint_backend() -> FingerprintBackend:
    try:
        if IS_WINDOWS:
            from .windows_fingerprint import WinBioBackend

            return WinBioBackend()
        if IS_LINUX:
            from .linux_fingerprint import FprintdBackend

            return FprintdBackend()
    except Exception:  # noqa: BLE001
        pass
    return FingerprintBackend()


def session_info() -> str:
    if IS_WINDOWS:
        return "Windows"
    if IS_LINUX:
        from .linux_display import is_wayland

        return "Linux (Wayland)" if is_wayland() else "Linux (X11)"
    return sys.platform
