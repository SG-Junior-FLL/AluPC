"""Windows 11: AluPC-Symbol direkt in der Taskleiste zeigen (nicht versteckt hinter dem Pfeil „^“).

Windows merkt sich pro Programm unter HKCU\\Control Panel\\NotifyIconSettings, ob sein Symbol sichtbar
(„IsPromoted“ = 1) oder im Überlauf ist. Der Eintrag entsteht erst, wenn das Symbol das erste Mal
angezeigt wurde. AluPC setzt ihn einmal auf „sichtbar“ – ändert man es danach selbst, bleibt das so.
Windows 10 kennt diese Einstellung nicht (dort passiert nichts).
"""

from __future__ import annotations

import ntpath
import os
import sys

KEY = r"Control Panel\NotifyIconSettings"


def _matches(registered: str, exe: str) -> bool:
    """Windows speichert Pfade teils mit Ordner-GUID statt „C:\\Program Files“ – deshalb die letzten
    zwei Teile (Ordner + Datei) vergleichen."""
    def tail(path: str) -> tuple[str, ...]:
        parts = [p for p in ntpath.normcase(path).replace("/", "\\").split("\\") if p]
        return tuple(parts[-2:])

    return bool(registered) and tail(registered) == tail(exe)


def promote(exe: str | None = None) -> bool:
    """Symbol dieses Programms sichtbar schalten. True = Eintrag gefunden (und gesetzt)."""
    if not sys.platform.startswith("win") or not getattr(sys, "frozen", False) and exe is None:
        return False  # Start aus dem Quellcode: das wäre python.exe – nicht anfassen
    import winreg

    exe = exe or os.path.realpath(sys.executable)
    try:
        root = winreg.OpenKey(winreg.HKEY_CURRENT_USER, KEY)
    except OSError:
        return False
    found = False
    with root:
        i = 0
        while True:
            try:
                sub = winreg.EnumKey(root, i)
            except OSError:
                break
            i += 1
            try:
                with winreg.OpenKey(root, sub, 0, winreg.KEY_READ | winreg.KEY_SET_VALUE) as k:
                    path, _ = winreg.QueryValueEx(k, "ExecutablePath")
                    if _matches(str(path), exe):
                        winreg.SetValueEx(k, "IsPromoted", 0, winreg.REG_DWORD, 1)
                        found = True
            except OSError:
                continue
    return found
