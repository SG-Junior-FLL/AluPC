"""Tastendruck und Mausklicks an den PC senden (Handy als Präsentations-Fernbedienung und Touchpad).

Windows: SendInput/keybd_event (user32). Linux X11: XTest (libXtst). Wayland erlaubt das Programmen aus
Sicherheitsgründen nicht – dann meldet AluPC das ehrlich.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import os
import sys

# Name → (Windows-Tastencode, X11-Keysym)
KEYS = {
    "weiter": (0x22, 0xFF56),     # Bild ab (PowerPoint, LibreOffice, PDF: nächste Folie)
    "zurueck": (0x21, 0xFF55),    # Bild auf
    "rechts": (0x27, 0xFF53),
    "links": (0x25, 0xFF51),
    "start": (0x74, 0xFFC2),      # F5: Präsentation starten
    "ende": (0x1B, 0xFF1B),       # Esc: Präsentation beenden
    "schwarz": (0x42, 0x0062),    # B: Bildschirm schwarz (PowerPoint/Impress)
    "leer": (0x20, 0x0020),
}


# Wayland: Programme dürfen keine Tasten an andere Fenster schicken – außer über ydotool (uinput, braucht den
# Dienst „ydotoold“). Linux-Tastencodes (input-event-codes.h) für ydotool:
EVDEV = {"weiter": 109, "zurueck": 104, "rechts": 106, "links": 105, "start": 63, "ende": 1, "schwarz": 48,
         "leer": 57, "F4": 62, "Tab": 15, "d": 32, "Alt_L": 56, "Super_L": 125}


def _wayland() -> bool:
    return os.environ.get("XDG_SESSION_TYPE") == "wayland" or bool(os.environ.get("WAYLAND_DISPLAY"))


def _ydotool(names: list[str]) -> bool:
    """Tasten (gleichzeitig gedrückt, dann in umgekehrter Reihenfolge los) über ydotool senden."""
    import shutil
    import subprocess

    tool = shutil.which("ydotool")
    codes = [EVDEV.get(n) for n in names]
    if not tool or None in codes:
        return False
    args = [f"{c}:1" for c in codes] + [f"{c}:0" for c in reversed(codes)]
    try:
        return subprocess.run([tool, "key", *args], capture_output=True, timeout=3).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _ydotool_raw(args: list[str]) -> bool:
    import shutil
    import subprocess

    tool = shutil.which("ydotool")
    if not tool:
        return False
    try:
        return subprocess.run([tool, *args], capture_output=True, timeout=3).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def available() -> bool:
    if sys.platform.startswith("win"):
        return True
    if _wayland():
        import shutil

        return shutil.which("ydotool") is not None
    return bool(ctypes.util.find_library("Xtst")) and bool(os.environ.get("DISPLAY"))


def send(name: str) -> bool:
    """Taste drücken und loslassen. False = geht auf diesem System nicht."""
    if name not in KEYS:
        raise ValueError(f"unbekannte Taste: {name}")
    vk, keysym = KEYS[name]
    if sys.platform.startswith("win"):
        user32 = ctypes.windll.user32
        user32.keybd_event(vk, 0, 0, 0)
        user32.keybd_event(vk, 0, 0x0002, 0)  # KEYEVENTF_KEYUP
        return True
    if not available():
        return False
    if _wayland():
        return _ydotool([name])
    x11, xtst = _x11()
    display = x11.XOpenDisplay(None)
    if not display:
        return False
    try:
        code = x11.XKeysymToKeycode(display, keysym)
        if not code:
            return False
        xtst.XTestFakeKeyEvent(display, code, 1, 0)
        xtst.XTestFakeKeyEvent(display, code, 0, 0)
        x11.XFlush(display)
        return True
    finally:
        x11.XCloseDisplay(display)


def combo(key: str, mods: tuple[str, ...] = ()) -> bool:
    """X11: Tastenkombination per Keysym-Namen („F4“ mit („Alt_L“,)). False = geht hier nicht (Wayland …)."""
    if sys.platform.startswith("win") or not available():
        return False
    if _wayland():
        return _ydotool([*mods, key])
    x11, xtst = _x11()
    x11.XStringToKeysym.argtypes = [ctypes.c_char_p]
    x11.XStringToKeysym.restype = ctypes.c_ulong
    display = x11.XOpenDisplay(None)
    if not display:
        return False
    try:
        codes = [x11.XKeysymToKeycode(display, x11.XStringToKeysym(n.encode())) for n in (*mods, key)]
        if not all(codes):
            return False
        for c in codes:
            xtst.XTestFakeKeyEvent(display, c, 1, 0)
        for c in reversed(codes):
            xtst.XTestFakeKeyEvent(display, c, 0, 0)
        x11.XFlush(display)
        return True
    finally:
        x11.XCloseDisplay(display)


def _x11():
    x11 = ctypes.CDLL(ctypes.util.find_library("X11"))
    xtst = ctypes.CDLL(ctypes.util.find_library("Xtst"))
    x11.XOpenDisplay.restype = ctypes.c_void_p
    x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
    x11.XKeysymToKeycode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    x11.XKeysymToKeycode.restype = ctypes.c_ubyte
    x11.XFlush.argtypes = [ctypes.c_void_p]
    x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
    xtst.XTestFakeKeyEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong]
    xtst.XTestFakeButtonEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong]
    return x11, xtst


# Maustaste → (Windows: drücken, loslassen), X11-Knopf
BUTTONS = {"links": ((0x0002, 0x0004), 1), "rechts": ((0x0008, 0x0010), 3), "mitte": ((0x0020, 0x0040), 2)}


def click(button: str = "links") -> bool:
    """Mausklick an der aktuellen Zeigerposition (Handy als Touchpad). False = geht hier nicht."""
    if button not in BUTTONS:
        raise ValueError(f"unbekannte Maustaste: {button}")
    (down, up), xbutton = BUTTONS[button]
    if sys.platform.startswith("win"):
        user32 = ctypes.windll.user32
        user32.mouse_event(down, 0, 0, 0, 0)
        user32.mouse_event(up, 0, 0, 0, 0)
        return True
    if _wayland():  # ydotool: 0xC0 = links drücken+loslassen, 0xC1 rechts, 0xC2 Mitte
        return _ydotool_raw(["click", {1: "0xC0", 3: "0xC1", 2: "0xC2"}[xbutton]])
    return _x11_buttons([xbutton])


def scroll(steps: int) -> bool:
    """Mausrad: positive Zahl = nach oben scrollen."""
    steps = max(-20, min(20, int(steps)))
    if not steps:
        return True
    if sys.platform.startswith("win"):
        ctypes.windll.user32.mouse_event(0x0800, 0, 0, ctypes.c_uint32(120 * steps & 0xFFFFFFFF).value, 0)
        return True
    if _wayland():
        return _ydotool_raw(["mousemove", "--wheel", "-x", "0", "-y", str(steps)])
    return _x11_buttons([4 if steps > 0 else 5] * abs(steps))


def move(dx: int, dy: int) -> bool:
    """Mauszeiger relativ bewegen – nur für Wayland nötig (sonst setzt Qt die Position direkt)."""
    if not _wayland():
        return False
    return _ydotool_raw(["mousemove", "-x", str(int(dx)), "-y", str(int(dy))])


def _x11_buttons(buttons: list[int]) -> bool:
    if not available():
        return False
    x11, xtst = _x11()
    display = x11.XOpenDisplay(None)
    if not display:
        return False
    try:
        for b in buttons:
            xtst.XTestFakeButtonEvent(display, b, 1, 0)
            xtst.XTestFakeButtonEvent(display, b, 0, 0)
        x11.XFlush(display)
        return True
    finally:
        x11.XCloseDisplay(display)
