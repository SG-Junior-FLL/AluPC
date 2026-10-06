"""Linux: systemweite Tastenkürzel ECHT prüfen – mit dem KDE-Dienst kglobalaccel (wie in Plasma).

Aufruf (CI): dbus-run-session -- sh -c 'Xvfb :55 & kglobalaccel5 & python tests/kde_hotkeys_check.py'
Ablauf: AluPC meldet seine Kürzel an → xdotool drückt sie (Fenster von AluPC ist NICHT aktiv) → AluPC
bekommt die Aktion. Dazu: doppelt belegte Taste wird gemeldet, „Pause“ (beim Aufnehmen) gibt die Tasten frei.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
results: list[tuple[bool, str]] = []


def ok(cond, text):
    results.append((bool(cond), text))
    print(("  ✓ " if cond else "  ✗ ") + text, flush=True)


def main() -> int:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")  # Tasten kommen über KDE, nicht über Qt
    from PySide6.QtWidgets import QApplication, QWidget

    app = QApplication([])

    def pump(sec):
        end = time.time() + sec
        while time.time() < end:
            app.processEvents()
            time.sleep(0.01)

    from alupc.hotkeys import HotkeyManager
    from alupc.platform.kde_shortcuts import COMPONENT, KdeShortcuts

    for _ in range(50):  # Dienst braucht einen Moment
        if KdeShortcuts(lambda a: None).available():
            break
        time.sleep(0.2)
    win = QWidget()
    mgr = HotkeyManager()
    mgr.attach(win)
    ok(mgr.kde is not None and mgr.system_wide, "KDE-Dienst erkannt → Kürzel gelten systemweit")
    got: list[str] = []
    mgr.triggered.connect(got.append)
    problems = mgr.apply({"standbild": "Ctrl+Alt+S", "sichtschutz": "Ctrl+Alt+P", "monitor2_aus": ""})
    ok(not problems and mgr.kde_ids == {"standbild", "sichtschutz"}, f"2 Kürzel angemeldet ({sorted(mgr.kde_ids)})")
    pump(0.5)
    subprocess.run(["xdotool", "key", "ctrl+alt+s"], check=False)
    pump(1.5)
    ok(got == ["standbild"], f"Strg+Alt+S gedrückt (AluPC nicht aktiv) → {got}")
    subprocess.run(["xdotool", "key", "ctrl+alt+p"], check=False)
    pump(1.5)
    ok(got[-1:] == ["sichtschutz"], f"Strg+Alt+P → {got[-1:]}")

    # anderes Programm hat die Taste schon
    other = KdeShortcuts(lambda a: None)
    from jeepney import DBusAddress, new_method_call

    addr = DBusAddress("/kglobalaccel", bus_name="org.kde.kglobalaccel", interface="org.kde.KGlobalAccel")
    aid = ["anderes", "aktion", "Anderes Programm", "Aktion"]
    other._connect().send_and_get_reply(new_method_call(addr, "doRegister", "as", (aid,)))
    from alupc.platform.kde_shortcuts import _key_code

    other._connect().send_and_get_reply(new_method_call(addr, "setShortcut", "asaiu",
                                                        (aid, [_key_code("Ctrl+Alt+K")], 6)))
    problems = mgr.apply({"standbild": "Ctrl+Alt+S", "sichtschutz": "Ctrl+Alt+K"})
    ok(any("Ctrl+Alt+K" in p and "belegt" in p for p in problems), f"Belegte Taste gemeldet: {problems}")
    ok("sichtschutz" not in mgr.kde_ids and len(mgr.shortcuts) == 1, "… und gilt dann nur in AluPC")

    mgr.pause()
    got.clear()
    subprocess.run(["xdotool", "key", "ctrl+alt+s"], check=False)
    pump(1.2)
    ok(got == [], f"Pause (Kürzel aufnehmen): Tasten frei → {got}")
    mgr.resume()
    pump(0.5)
    subprocess.run(["xdotool", "key", "ctrl+alt+s"], check=False)
    pump(1.5)
    ok(got == ["standbild"], f"Nach der Pause wieder aktiv → {got}")
    ok(COMPONENT == "alupc", "In KDE unter Kurzbefehle → „AluPC“ sichtbar")
    mgr.kde.stop()
    failed = [t for good, t in results if not good]
    print(f"\n{len(results) - len(failed)}/{len(results)} Prüfungen bestanden")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
