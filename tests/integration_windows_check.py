"""Windows-CI: Einbindung ins System ECHT prüfen (Registry des Benutzers).

1. Einschalten → Rechtsklick-Einträge + alupc://-Protokoll stehen in HKCU.
2. Der eingetragene Rechtsklick-Befehl (so wie der Explorer ihn mit „%1“ startet) erreicht das laufende AluPC.
3. `start alupc://standbild` (wie ein Klick auf den Link) → Windows startet AluPC → Befehl kommt an.
4. Ausschalten → alles wieder weg.
"""

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main() -> int:
    from PySide6.QtGui import QImage
    from PySide6.QtWidgets import QApplication

    app = QApplication([])
    from alupc.ipc import SingleInstance
    from alupc.platform import system_integration as si

    errors: list[str] = []

    def ok(cond, text):
        print(("✓ " if cond else "✗ ") + text, flush=True)
        if not cond:
            errors.append(text)

    got: list[str] = []
    inst = SingleInstance(app)
    inst.command.connect(got.append)

    def wait_for(n, seconds=60):
        end = time.time() + seconds
        while len(got) < n and time.time() < end:
            app.processEvents()
            time.sleep(0.05)

    ok(si.set_enabled(True)[0], "einschalten")
    ok(si.is_active(), "Registry-Einträge vollständig")
    cmd = si._win_read(r"SystemFileAssociations\image\shell\AluPC.Monitor2\command", "")
    print("Befehl:", cmd)
    tmp = Path(tempfile.mkdtemp()) / "Bild mit Leerzeichen.png"
    QImage(8, 8, QImage.Format_RGB32).save(str(tmp))
    p = subprocess.Popen(cmd.replace("%1", str(tmp)), cwd=str(Path(__file__).resolve().parents[1]))
    wait_for(1)
    p.wait(30)
    ok(got[:1] == ["datei:" + str(tmp)], f"Rechtsklick-Befehl kommt an → {got[:1]}")

    os.system('start "" "alupc://standbild"')  # wie ein Klick auf den Link
    wait_for(2)
    ok(got[1:2] == ["standbild"], f"alupc://standbild über Windows → {got[1:2]}")

    ok(si.set_enabled(False)[0], "ausschalten")
    ok(not si.is_active() and si._win_read("alupc", "") is None
       and si._win_read(r"Directory\shell\AluPC.Monitor2", "MUIVerb") is None, "alles entfernt")
    print(f"{'OK' if not errors else 'FEHLER'}: {6 - len(errors)}/6", flush=True)
    for e in errors:
        print(f"::error title=Einbindung (Windows)::{e}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
