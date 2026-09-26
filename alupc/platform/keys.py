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


def available() -> bool:
    if sys.platform.startswith("win"):
        return True
    if os.environ.get("XDG_SESSION_TYPE") == "wayland" or os.environ.get("WAYLAND_DISPLAY"):
        return False
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
    return _x11_buttons([xbutton])


def scroll(steps: int) -> bool:
    """Mausrad: positive Zahl = nach oben scrollen."""
    steps = max(-20, min(20, int(steps)))
    if not steps:
        return True
    if sys.platform.startswith("win"):
        ctypes.windll.user32.mouse_event(0x0800, 0, 0, ctypes.c_uint32(120 * steps & 0xFFFFFFFF).value, 0)
        return True
    return _x11_buttons([4 if steps > 0 else 5] * abs(steps))


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
