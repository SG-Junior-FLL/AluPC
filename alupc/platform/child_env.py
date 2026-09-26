"""Umgebung für fremde Programme (UxPlay, kscreen-doctor, wmctrl, apt …).

Die fertige Linux-Version (PyInstaller) setzt LD_LIBRARY_PATH auf ihren eigenen Bibliotheksordner – dort liegt
u. a. eine ältere GLib. Jedes Programm, das AluPC startet, erbt das und lädt dann diese statt der des Systems:
UxPlay bricht so mit „symbol lookup error … g_once_init_leave_pointer“ ab (Exit-Code 127).

AluPC selbst braucht die Variable nach dem Start nicht mehr (der Lader liest sie nur einmal beim Programmstart,
AluPCs Hilfsprogramme wie QtWebEngineProcess finden ihre Bibliotheken über ihren eingebauten Suchpfad). Deshalb
wird sie früh auf den Wert vor PyInstaller zurückgesetzt – dann bekommen alle gestarteten Programme die Umgebung
des Systems."""

from __future__ import annotations

import os
import sys

# PyInstaller merkt sich die ursprünglichen Werte unter NAME_ORIG
_VARS = ("LD_LIBRARY_PATH", "GST_PLUGIN_PATH", "GST_PLUGIN_SYSTEM_PATH", "GST_PLUGIN_SCANNER", "GIO_MODULE_DIR",
         "GDK_PIXBUF_MODULE_FILE", "GTK_PATH")


def restore_system_env(environ=None, frozen: bool | None = None, platform: str | None = None) -> list[str]:
    """Nur in der fertigen Linux-Version: Pfade, die PyInstaller gesetzt hat, auf die Systemwerte zurück.
    Rückgabe: geänderte Variablen."""
    environ = os.environ if environ is None else environ
    frozen = getattr(sys, "frozen", False) if frozen is None else frozen
    platform = sys.platform if platform is None else platform
    if not frozen or not platform.startswith("linux"):
        return []
    changed = []
    for name in _VARS:
        orig = environ.get(name + "_ORIG")
        if orig is not None:
            if environ.get(name) != orig:
                environ[name] = orig
                changed.append(name)
        elif name == "LD_LIBRARY_PATH" and name in environ:
            base = getattr(sys, "_MEIPASS", "") or os.path.dirname(sys.executable)
            # Nur AluPCs eigene Ordner entfernen, fremde Einträge (falls vorher gesetzt) behalten
            kept = [p for p in environ[name].split(os.pathsep) if p and not p.startswith(base)]
            if kept:
                environ[name] = os.pathsep.join(kept)
            else:
                del environ[name]
            changed.append(name)
    return changed
