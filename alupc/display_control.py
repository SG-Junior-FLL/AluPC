"""Displays steuern: Helligkeit je Monitor.

Je Monitor der erste Weg, der geht:
* Windows: echte Monitor-Helligkeit über das Monitorkabel (DDC/CI, dxva2) bzw. Laptop-Bildschirm (WMI)
* Linux: DDC/CI über `ddcutil` (externe Monitore), Laptop-Bildschirm über `brightnessctl`
* sonst (z. B. in einer VM): AluPC dunkelt selbst ab – eine durchsichtige, dunkle Ebene über dem Monitor, durch
  die man weiter klicken kann

(Ausschalten gab es in 0.61 – es funktionierte nicht zuverlässig und wurde wieder entfernt.)
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QGuiApplication, QPainter
from PySide6.QtWidgets import QWidget

IS_WINDOWS = sys.platform.startswith("win")
NO_WINDOW = 0x08000000 if IS_WINDOWS else 0


def _run(args: list[str], timeout: float = 6) -> str:
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=timeout,
                              creationflags=NO_WINDOW).stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def _ok(args: list[str], timeout: float = 10) -> bool:
    """Befehl ausführen – True, wenn er geklappt hat (Rückgabewert 0)."""
    try:
        return subprocess.run(args, capture_output=True, timeout=timeout, creationflags=NO_WINDOW).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _norm(name: str) -> str:
    """Anschlussnamen vergleichbar machen: „card1-HDMI-A-1“, „HDMI-A-1“, „HDMI-1“ → „hdmi1“."""
    name = name.lower().split("-", 1)[1] if name.lower().startswith("card") and "-" in name else name.lower()
    name = re.sub(r"-a-", "-", name)
    return re.sub(r"[^a-z0-9]", "", name)


# --------------------------------------------------------------------------- Hardware: Windows
class _WindowsDDC:
    """Echte Helligkeit/Ein-Aus über das Monitorkabel (DDC/CI) – dxva2.dll."""

    def __init__(self):
        import ctypes
        from ctypes import wintypes

        self.ctypes, self.wintypes = ctypes, wintypes
        self.dxva2 = ctypes.windll.dxva2
        self.user32 = ctypes.windll.user32

        class PHYSICAL_MONITOR(ctypes.Structure):
            _fields_ = [("handle", wintypes.HANDLE), ("desc", wintypes.WCHAR * 128)]

        class MONITORINFOEXW(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT), ("rcWork", wintypes.RECT),
                        ("dwFlags", wintypes.DWORD), ("szDevice", wintypes.WCHAR * 32)]

        self.PHYSICAL_MONITOR, self.MONITORINFOEXW = PHYSICAL_MONITOR, MONITORINFOEXW

    def _handles(self) -> dict[str, list]:
        """Gerätename („\\\\.\\DISPLAY1“ = QScreen.name()) → physische Monitor-Handles."""
        ctypes, wintypes = self.ctypes, self.wintypes
        result: dict[str, list] = {}
        proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC, ctypes.POINTER(wintypes.RECT),
                                  wintypes.LPARAM)

        def cb(hmon, _hdc, _rect, _lp):
            info = self.MONITORINFOEXW()
            info.cbSize = ctypes.sizeof(info)
            self.user32.GetMonitorInfoW(hmon, ctypes.byref(info))
            count = wintypes.DWORD()
            if self.dxva2.GetNumberOfPhysicalMonitorsFromHMONITOR(hmon, ctypes.byref(count)) and count.value:
                arr = (self.PHYSICAL_MONITOR * count.value)()
                if self.dxva2.GetPhysicalMonitorsFromHMONITOR(hmon, count.value, arr):
                    result[info.szDevice] = [arr[i].handle for i in range(count.value)]
            return True

        self.user32.EnumDisplayMonitors(None, None, proc(cb), 0)
        return result

    def _with(self, screen_name: str, fn):
        handles = self._handles()
        mine = handles.get(screen_name, [])
        try:
            return fn(mine)
        finally:
            for hs in handles.values():
                for h in hs:
                    self.dxva2.DestroyPhysicalMonitor(h)

    def get(self, screen_name: str) -> int | None:
        ctypes, wintypes = self.ctypes, self.wintypes

        def read(hs):
            for h in hs:
                lo, cur, hi = wintypes.DWORD(), wintypes.DWORD(), wintypes.DWORD()
                if self.dxva2.GetMonitorBrightness(h, ctypes.byref(lo), ctypes.byref(cur), ctypes.byref(hi)):
                    span = max(1, hi.value - lo.value)
                    return round((cur.value - lo.value) * 100 / span)
            return None

        return self._with(screen_name, read)

    def set(self, screen_name: str, percent: int) -> bool:
        ctypes, wintypes = self.ctypes, self.wintypes

        def write(hs):
            ok = False
            for h in hs:
                lo, cur, hi = wintypes.DWORD(), wintypes.DWORD(), wintypes.DWORD()
                if self.dxva2.GetMonitorBrightness(h, ctypes.byref(lo), ctypes.byref(cur), ctypes.byref(hi)):
                    value = lo.value + round((hi.value - lo.value) * percent / 100)
                    ok = bool(self.dxva2.SetMonitorBrightness(h, value)) or ok
            return ok

        return self._with(screen_name, write)

def _windows_wmi_get() -> int | None:
    out = _run(["powershell", "-NoProfile", "-Command",
                "(Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightness -ErrorAction Stop)"
                ".CurrentBrightness"])
    m = re.search(r"\d+", out)
    return int(m.group()) if m else None


def _windows_wmi_set(percent: int) -> bool:
    out = _run(["powershell", "-NoProfile", "-Command",
                "Invoke-CimMethod -InputObject (Get-CimInstance -Namespace root/WMI -ClassName "
                f"WmiMonitorBrightnessMethods -ErrorAction Stop) -MethodName WmiSetBrightness -Arguments "
                f"@{{Timeout=1; Brightness={int(percent)}}} | Out-Null; 'ok'"])
    return "ok" in out


# --------------------------------------------------------------------------- Hardware: Linux
def ddcutil_displays(text: str | None = None) -> dict[str, int]:
    """`ddcutil detect` → {normierter Anschluss: Displaynummer}."""
    if text is None:
        if not shutil.which("ddcutil"):
            return {}
        text = _run(["ddcutil", "detect"], timeout=15)
    result, number = {}, None
    for line in text.splitlines():
        m = re.match(r"\s*Display\s+(\d+)", line)
        if m:
            number = int(m.group(1))
            continue
        m = re.search(r"DRM[_ ]connector:\s*(\S+)", line)
        if m and number is not None:
            result[_norm(m.group(1))] = number
    return result


def parse_ddcutil_brightness(text: str) -> int | None:
    """„VCP 10 C 50 100“ (--brief) → 50 %."""
    m = re.search(r"VCP\s+10\s+C\s+(\d+)\s+(\d+)", text)
    if m:
        cur, hi = int(m.group(1)), max(1, int(m.group(2)))
        return round(cur * 100 / hi)
    return None


def parse_brightnessctl(text: str) -> int | None:
    """`brightnessctl -m`: „intel_backlight,backlight,5000,50%,10000“ → 50."""
    for line in text.splitlines():
        parts = line.split(",")
        if len(parts) >= 4 and parts[1] == "backlight" and parts[3].endswith("%"):
            return int(parts[3][:-1])
    return None


def is_internal(name: str) -> bool:
    return _norm(name).startswith(("edp", "lvds", "dsi"))


# --------------------------------------------------------------------------- Abdunkeln (überall)
class ShadeWindow(QWidget):
    """Halbdurchsichtige dunkle Ebene über einem Monitor – Klicks gehen durch."""

    def __init__(self, screen, alpha: float = 0.0):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
                         | Qt.WindowTransparentForInput | Qt.WindowDoesNotAcceptFocus)
        self.alpha = alpha
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setGeometry(screen.geometry())
        if IS_WINDOWS:
            QTimer.singleShot(0, self._exclude_from_capture)

    def _exclude_from_capture(self):
        """Windows: das Abdunkeln nicht mit aufnehmen (sonst wäre beim Spiegeln auch Monitor 2 dunkel)."""
        try:
            import ctypes

            ctypes.windll.user32.SetWindowDisplayAffinity(int(self.winId()), 0x11)  # WDA_EXCLUDEFROMCAPTURE
        except Exception:  # noqa: BLE001 - ältere Windows-Versionen
            pass

    def set_alpha(self, alpha: float):
        self.alpha = alpha
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        c = QColor(0, 0, 0)
        c.setAlphaF(max(0.0, min(0.9, self.alpha)))
        p.setCompositionMode(QPainter.CompositionMode_Source)
        p.fillRect(self.rect(), c)
        p.end()


# --------------------------------------------------------------------------- Steuerung
class DisplayControl(QObject):
    """Helligkeit aller Monitore."""

    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.shades: dict[str, ShadeWindow] = {}  # abgedunkelt (Software)
        self.software: dict[str, int] = {}  # Helligkeit, die AluPC selbst simuliert
        self._ddc_win = None
        self._ddcutil: dict[str, int] | None = None

    # ---- Monitore
    @staticmethod
    def screens():
        return list(QGuiApplication.screens())

    def screen(self, name: str):
        return next((s for s in self.screens() if s.name() == name), None)

    # ---- Helligkeit
    def method(self, name: str) -> str:
        """Womit sich die Helligkeit dieses Monitors ändern lässt: "ddc", "laptop" oder "abdunkeln"."""
        if IS_WINDOWS:
            if self._win_ddc() is not None and self._win_ddc().get(name) is not None:
                return "ddc"
            if len(self.screens()) == 1 or name == self._primary_name():
                if _windows_wmi_get() is not None:
                    return "laptop"
            return "abdunkeln"
        if _norm(name) in self._ddcutil_map():
            return "ddc"
        if is_internal(name) and shutil.which("brightnessctl") and parse_brightnessctl(_run(["brightnessctl", "-m"])) \
                is not None:
            return "laptop"
        return "abdunkeln"

    def get_brightness(self, name: str, method: str | None = None) -> int:
        method = method or self.method(name)
        value = None
        if method == "ddc":
            if IS_WINDOWS:
                value = self._win_ddc().get(name)
            else:
                num = self._ddcutil_map().get(_norm(name))
                value = parse_ddcutil_brightness(_run(["ddcutil", "--display", str(num), "getvcp", "10", "--brief"]))
        elif method == "laptop":
            value = _windows_wmi_get() if IS_WINDOWS else parse_brightnessctl(_run(["brightnessctl", "-m"]))
        if value is None:
            value = self.software.get(name, 100)
        return max(0, min(100, int(value)))

    def set_brightness(self, name: str, percent: int, method: str | None = None) -> str:
        """Helligkeit setzen. Rückgabe: benutzter Weg ("ddc", "laptop", "abdunkeln")."""
        percent = max(0, min(100, int(percent)))
        method = method or self.method(name)
        if self.set_hardware(name, percent, method):
            self._set_shade(name, 100)
            return method
        self._set_shade(name, percent)
        return "abdunkeln"

    def set_hardware(self, name: str, percent: int, method: str) -> bool:
        """Nur die echte Helligkeit (darf im Hintergrund laufen – keine Fenster). False = geht nicht."""
        ok = False
        if method == "ddc":
            if IS_WINDOWS:
                ok = self._win_ddc().set(name, percent)
            else:
                num = self._ddcutil_map().get(_norm(name))
                ok = num is not None and _ok(["ddcutil", "--display", str(num), "setvcp", "10", str(percent)])
        elif method == "laptop":
            ok = _windows_wmi_set(percent) if IS_WINDOWS else _ok(["brightnessctl", "set", f"{max(1, percent)}%"])
        return bool(ok)

    def apply_result(self, name: str, percent: int, hardware_ok: bool) -> str:
        """Nach `set_hardware` im GUI-Thread: klappte es nicht, dunkelt AluPC selbst ab."""
        self._set_shade(name, 100 if hardware_ok else percent)
        return "hardware" if hardware_ok else "abdunkeln"

    def _set_shade(self, name: str, percent: int) -> None:
        """Software-Helligkeit: 100 % = keine Ebene, 0 % = fast schwarz (nie ganz – man soll noch etwas sehen)."""
        self.software[name] = percent
        shade = self.shades.get(name)
        if percent >= 100:
            if shade is not None:
                shade.close()
                self.shades.pop(name, None)
            self.changed.emit()
            return
        screen = self.screen(name)
        if screen is None:
            return
        alpha = (100 - percent) / 100 * 0.9
        if shade is None:
            shade = ShadeWindow(screen, alpha=alpha)
            self.shades[name] = shade
            shade.show()
        shade.set_alpha(alpha)
        shade.raise_()
        self.changed.emit()

    def step_all(self, delta: int) -> None:
        for s in self.screens():
            self.set_brightness(s.name(), self.get_brightness(s.name()) + delta)

    # ---- Helfer
    def _win_ddc(self):
        if not IS_WINDOWS:
            return None
        if self._ddc_win is None:
            try:
                self._ddc_win = _WindowsDDC()
            except Exception:  # noqa: BLE001
                self._ddc_win = False
        return self._ddc_win or None

    def _ddcutil_map(self) -> dict[str, int]:
        if self._ddcutil is None:
            self._ddcutil = ddcutil_displays()
        return self._ddcutil

    def _primary_name(self) -> str:
        p = QGuiApplication.primaryScreen()
        return p.name() if p else ""

    def shutdown(self) -> None:
        for shade in self.shades.values():
            shade.close()
        self.shades.clear()
