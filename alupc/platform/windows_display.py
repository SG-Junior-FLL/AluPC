"""Monitor-Einstellungen unter Windows 11 (Win32: ChangeDisplaySettingsEx, DisplaySwitch)."""

from __future__ import annotations

import ctypes
import subprocess
import sys
import time

from .base import DisplayBackend, DisplayMode, Output, place

ENUM_CURRENT_SETTINGS = 0xFFFFFFFF
DM_POSITION = 0x00000020
DM_DISPLAYORIENTATION = 0x00000080
DM_BITSPERPEL = 0x00040000
DM_PELSWIDTH = 0x00080000
DM_PELSHEIGHT = 0x00100000
DM_DISPLAYFREQUENCY = 0x00400000
CDS_UPDATEREGISTRY = 0x00000001
CDS_SET_PRIMARY = 0x00000010
CDS_NORESET = 0x10000000
DISPLAY_DEVICE_ATTACHED_TO_DESKTOP = 0x00000001
DISPLAY_DEVICE_PRIMARY_DEVICE = 0x00000004
DISPLAY_DEVICE_MIRRORING_DRIVER = 0x00000008

ORIENTATION_TO_NAME = {0: "normal", 1: "left", 2: "inverted", 3: "right"}
NAME_TO_ORIENTATION = {v: k for k, v in ORIENTATION_TO_NAME.items()}

DISP_ERRORS = {
    1: "Neustart erforderlich",
    -1: "Der Grafiktreiber hat den Modus abgelehnt",
    -2: "Dieser Modus wird nicht unterstützt",
    -3: "Einstellungen konnten nicht gespeichert werden",
    -4: "Ungültige Parameter",
    -5: "Ungültige Parameter",
    -6: "Grafikkarte unterstützt das nicht",
}

WCHAR = ctypes.c_wchar
WORD = ctypes.c_uint16
DWORD = ctypes.c_uint32
LONG = ctypes.c_int32
SHORT = ctypes.c_int16


class DEVMODEW(ctypes.Structure):
    # Anzeige-Variante der DEVMODEW-Struktur (220 Bytes)
    _fields_ = [
        ("dmDeviceName", WCHAR * 32),
        ("dmSpecVersion", WORD),
        ("dmDriverVersion", WORD),
        ("dmSize", WORD),
        ("dmDriverExtra", WORD),
        ("dmFields", DWORD),
        ("dmPositionX", LONG),
        ("dmPositionY", LONG),
        ("dmDisplayOrientation", DWORD),
        ("dmDisplayFixedOutput", DWORD),
        ("dmColor", SHORT),
        ("dmDuplex", SHORT),
        ("dmYResolution", SHORT),
        ("dmTTOption", SHORT),
        ("dmCollate", SHORT),
        ("dmFormName", WCHAR * 32),
        ("dmLogPixels", WORD),
        ("dmBitsPerPel", DWORD),
        ("dmPelsWidth", DWORD),
        ("dmPelsHeight", DWORD),
        ("dmDisplayFlags", DWORD),
        ("dmDisplayFrequency", DWORD),
        ("dmICMMethod", DWORD),
        ("dmICMIntent", DWORD),
        ("dmMediaType", DWORD),
        ("dmDitherType", DWORD),
        ("dmReserved1", DWORD),
        ("dmReserved2", DWORD),
        ("dmPanningWidth", DWORD),
        ("dmPanningHeight", DWORD),
    ]


class DISPLAY_DEVICEW(ctypes.Structure):
    _fields_ = [
        ("cb", DWORD),
        ("DeviceName", WCHAR * 32),
        ("DeviceString", WCHAR * 128),
        ("StateFlags", DWORD),
        ("DeviceID", WCHAR * 128),
        ("DeviceKey", WCHAR * 128),
    ]


_USER32 = None


def _user32():
    global _USER32
    if _USER32 is None:
        from ctypes import wintypes

        u = ctypes.windll.user32  # type: ignore[attr-defined]
        u.EnumDisplaySettingsW.argtypes = [wintypes.LPCWSTR, DWORD, ctypes.POINTER(DEVMODEW)]
        u.EnumDisplaySettingsW.restype = wintypes.BOOL
        u.EnumDisplayDevicesW.argtypes = [wintypes.LPCWSTR, DWORD, ctypes.POINTER(DISPLAY_DEVICEW), DWORD]
        u.EnumDisplayDevicesW.restype = wintypes.BOOL
        u.ChangeDisplaySettingsExW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(DEVMODEW),
                                               wintypes.HWND, DWORD, ctypes.c_void_p]
        u.ChangeDisplaySettingsExW.restype = LONG
        _USER32 = u
    return _USER32


def _devmode() -> DEVMODEW:
    dm = DEVMODEW()
    dm.dmSize = ctypes.sizeof(DEVMODEW)
    return dm


def current_settings(device: str) -> DEVMODEW | None:
    dm = _devmode()
    if _user32().EnumDisplaySettingsW(device, ENUM_CURRENT_SETTINGS, ctypes.byref(dm)):
        return dm
    return None


def monitor_rect(device: str) -> tuple[int, int, int, int] | None:
    """Physische Position und Größe eines Monitors (für SetWindowPos)."""
    dm = current_settings(device)
    if not dm:
        return None
    return (dm.dmPositionX, dm.dmPositionY, dm.dmPelsWidth, dm.dmPelsHeight)


def _monitor_name(device: str) -> str:
    mon = DISPLAY_DEVICEW()
    mon.cb = ctypes.sizeof(DISPLAY_DEVICEW)
    if _user32().EnumDisplayDevicesW(device, 0, ctypes.byref(mon), 0):
        return mon.DeviceString
    return ""


def _modes(device: str) -> list[DisplayMode]:
    modes: dict[tuple[int, int, int], DisplayMode] = {}
    i = 0
    dm = _devmode()
    while _user32().EnumDisplaySettingsW(device, i, ctypes.byref(dm)):
        i += 1
        if dm.dmBitsPerPel < 24:
            continue
        key = (dm.dmPelsWidth, dm.dmPelsHeight, dm.dmDisplayFrequency)
        if key not in modes:
            modes[key] = DisplayMode(f"{key[0]}x{key[1]}@{key[2]}", key[0], key[1], float(key[2]))
    return list(modes.values())


class WindowsDisplayBackend(DisplayBackend):
    name = "Windows"

    def available(self) -> bool:
        return sys.platform.startswith("win")

    def list_outputs(self) -> list[Output]:
        outputs = []
        i = 0
        dd = DISPLAY_DEVICEW()
        dd.cb = ctypes.sizeof(DISPLAY_DEVICEW)
        while _user32().EnumDisplayDevicesW(None, i, ctypes.byref(dd), 0):
            i += 1
            if dd.StateFlags & DISPLAY_DEVICE_MIRRORING_DRIVER:
                continue
            if not dd.StateFlags & DISPLAY_DEVICE_ATTACHED_TO_DESKTOP:
                continue
            name = dd.DeviceName
            dm = current_settings(name)
            if not dm:
                continue
            rotation = ORIENTATION_TO_NAME.get(dm.dmDisplayOrientation, "normal")
            w, h = dm.dmPelsWidth, dm.dmPelsHeight
            if rotation in ("left", "right"):
                w, h = h, w  # Modi werden unrotiert gespeichert
            outputs.append(
                Output(
                    name=name,
                    description=_monitor_name(name) or dd.DeviceString,
                    enabled=True,
                    primary=bool(dd.StateFlags & DISPLAY_DEVICE_PRIMARY_DEVICE),
                    x=dm.dmPositionX,
                    y=dm.dmPositionY,
                    rotation=rotation,
                    mode_id=f"{w}x{h}@{dm.dmDisplayFrequency}",
                    modes=_modes(name),
                )
            )
        return outputs

    def apply(self, outputs: list[Output]) -> None:
        primary = next((o for o in outputs if o.primary and o.enabled), None)
        ox, oy = (primary.x, primary.y) if primary else (0, 0)
        user32 = _user32()
        for o in outputs:
            dm = current_settings(o.name) or _devmode()
            flags = CDS_UPDATEREGISTRY | CDS_NORESET
            if not o.enabled:
                dm.dmPelsWidth = dm.dmPelsHeight = 0
                dm.dmFields = DM_POSITION | DM_PELSWIDTH | DM_PELSHEIGHT
            else:
                mode = o.mode()
                if mode:
                    w, h = mode.width, mode.height
                    if o.rotation in ("left", "right"):
                        w, h = h, w
                    dm.dmPelsWidth, dm.dmPelsHeight = w, h
                    dm.dmDisplayFrequency = int(round(mode.refresh))
                dm.dmPositionX, dm.dmPositionY = o.x - ox, o.y - oy  # Hauptmonitor muss bei 0,0 liegen
                dm.dmDisplayOrientation = NAME_TO_ORIENTATION.get(o.rotation, 0)
                dm.dmFields = (DM_POSITION | DM_PELSWIDTH | DM_PELSHEIGHT
                               | DM_DISPLAYFREQUENCY | DM_DISPLAYORIENTATION)
                if o is primary:
                    flags |= CDS_SET_PRIMARY
            res = user32.ChangeDisplaySettingsExW(o.name, ctypes.byref(dm), None, flags, None)
            if res != 0:
                raise RuntimeError(f"{o.description or o.name}: {DISP_ERRORS.get(res, f'Fehler {res}')}")
        res = user32.ChangeDisplaySettingsExW(None, None, None, 0, None)
        if res != 0:
            raise RuntimeError(DISP_ERRORS.get(res, f"Fehler {res}"))

    def mirror(self, main: str, second: str) -> None:
        # Windows spiegelt über den offiziellen Weg (wie Win+P → Duplizieren)
        subprocess.run(["DisplaySwitch.exe", "/clone"], timeout=20)

    def extend(self, main: str, second: str, side: str = "right") -> None:
        subprocess.run(["DisplaySwitch.exe", "/extend"], timeout=20)
        # Windows braucht einen Moment, bis der zweite Monitor wieder aktiv ist
        for _ in range(10):
            time.sleep(0.5)
            outputs = self.list_outputs()
            names = {o.name for o in outputs}
            if main in names and second in names:
                place(outputs, main, second, side, False)
                self.apply(outputs)
                return
