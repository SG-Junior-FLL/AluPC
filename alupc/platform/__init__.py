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


def _system_fingerprint_backend() -> FingerprintBackend:
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


class AutoFingerprintBackend(FingerprintBackend):
    """Nimmt automatisch den passenden Weg:

    * Fingerabdruckmodul am seriellen Anschluss (z. B. HLK-ZW101) gefunden → das Modul direkt
    * sonst das System (Windows Hello bzw. fprintd unter Linux)
    """

    def __init__(self, system: FingerprintBackend, serial_backend: FingerprintBackend | None):
        self.system = system
        self.serial = serial_backend
        self.active = system

    # Fähigkeiten und Name kommen vom gerade benutzten Weg
    name = property(lambda self: self.active.name)
    can_enroll = property(lambda self: self.active.can_enroll)
    can_delete = property(lambda self: self.active.can_delete)
    can_list_enrolled = property(lambda self: self.active.can_list_enrolled)
    login_toggle = property(lambda self: self.active.login_toggle)
    can_auto_install = property(lambda self: self.system.can_auto_install)

    @property
    def is_serial(self) -> bool:
        return self.active is self.serial and self.serial is not None

    def availability(self):
        serial_msg = ""
        if self.serial is not None:
            try:
                ok, msg = self.serial.availability()
            except Exception as exc:  # noqa: BLE001
                ok, msg = False, str(exc)
            if ok:
                self.active = self.serial
                return ok, msg
            serial_msg = msg
        self.active = self.system
        ok, msg = self.system.availability()
        if not ok and "Kein Zugriff" in serial_msg:
            # kein System-Sensor, aber ein Adapter, der sich nicht öffnen lässt → das ist wohl das Modul
            self.active = self.serial
            return False, serial_msg
        return ok, msg

    def list_sensors(self):
        if self.is_serial and getattr(self.serial, "_found", None):
            from .base import Sensor

            return [Sensor(id=port, name=f"Fingerabdruckmodul an {port}",
                           detail=f"{params.get('capacity', '?')} Plätze, {baud} Baud")
                    for port, (baud, params) in self.serial._found.items()]
        return self.active.list_sensors()

    def finger_label(self, key):
        return self.active.finger_label(key)

    def is_enrolled(self, sensor_id, finger):
        return self.active.is_enrolled(sensor_id, finger)

    # alles andere an den aktiven Weg weitergeben
    def list_enrolled(self, sensor_id):
        return self.active.list_enrolled(sensor_id)

    def enroll(self, sensor_id, finger, status):
        return self.active.enroll(sensor_id, finger, status)

    def verify(self, sensor_id, status):
        return self.active.verify(sensor_id, status)

    def delete(self, sensor_id, finger):
        return self.active.delete(sensor_id, finger)

    def cancel(self):
        self.active.cancel()

    def login_enabled(self):
        return self.active.login_enabled()

    def set_login_enabled(self, enabled, allow_multi: bool = False):
        if self.is_serial:
            return self.serial.set_login_enabled(enabled, allow_multi)
        return self.active.set_login_enabled(enabled)

    def multi_user_warning(self) -> str:
        """Leer, außer: Modul am Adapter + Linux + mehrere Benutzerkonten → Warntext zum Bestätigen."""
        if not (self.is_serial and IS_LINUX):
            return ""
        from .linux_serial_login import MULTI_USER_WARNING, human_accounts

        accounts = human_accounts()
        return MULTI_USER_WARNING.format(accounts=", ".join(accounts)) if len(accounts) > 1 else ""

    def open_system_settings(self):
        return self.system.open_system_settings()

    def install_hint(self):
        return self.active.install_hint()

    def missing_packages(self):
        return [] if self.is_serial else self.system.missing_packages()

    def install_packages(self, packages):
        return self.system.install_packages(packages)

    def detect_hardware(self):
        return self.system.detect_hardware()


def create_fingerprint_backend() -> FingerprintBackend:
    system = _system_fingerprint_backend()
    try:
        from .zw_fingerprint import HAVE_SERIAL, SerialFingerprintBackend

        serial_backend = SerialFingerprintBackend() if HAVE_SERIAL else None
    except Exception:  # noqa: BLE001
        serial_backend = None
    return AutoFingerprintBackend(system, serial_backend)


def session_info() -> str:
    if IS_WINDOWS:
        return "Windows"
    if IS_LINUX:
        from .linux_display import is_wayland

        return "Linux (Wayland)" if is_wayland() else "Linux (X11)"
    return sys.platform
