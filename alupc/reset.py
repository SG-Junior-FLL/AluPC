"""„Alle Daten löschen“: AluPC auf den Zustand nach der Installation zurücksetzen.

Gelöscht wird alles, was AluPC für diesen Benutzer ablegt: Einstellungen, Szenen, Startseite, Overlays,
Vorschaubilder, vom Handy empfangene Dateien, Namen der Fingerabdrücke, Browser-Daten (Cookies, Anmeldungen
auf Websites) und der Autostart. Das Programm selbst bleibt installiert.

Was Systemrechte braucht (Anmelden mit Fingerabdruck, Fingerabdrücke im Modul), erledigt die Oberfläche vorher
über das Fingerabdruck-Backend – dort fragt das System wie gewohnt nach.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from .config import config_dir


def is_alupc_dir(d: Path) -> bool:
    """Sicherung: nur Ordner, die selbst (oder deren Elternordner) „AluPC“ heißen – nie etwas Fremdes."""
    return any(part.lower() == "alupc" for part in (d.name, d.parent.name))


def data_dirs() -> list[Path]:
    """Ordner, die nur AluPC gehören."""
    dirs = [config_dir()]
    try:
        from PySide6.QtCore import QStandardPaths

        for loc in (QStandardPaths.AppLocalDataLocation, QStandardPaths.AppDataLocation,
                    QStandardPaths.CacheLocation, QStandardPaths.AppConfigLocation):
            path = QStandardPaths.writableLocation(loc)
            if path:
                dirs.append(Path(path))
    except Exception:  # noqa: BLE001 - ohne Qt nur der Einstellungsordner
        pass
    result: list[Path] = []
    for d in dirs:
        if not is_alupc_dir(d) or d in result:
            continue
        if any(parent in result for parent in d.parents):
            continue  # liegt schon in einem anderen Ordner der Liste
        result.append(d)
    return result


def wipe(dirs: list[Path] | None = None) -> list[str]:
    """Löscht Daten und Autostart. Rückgabe: was nicht ging (z. B. eine Datei, die gerade benutzt wird)."""
    problems: list[str] = []
    try:
        from .platform import autostart

        autostart.set_enabled(False)
    except Exception as exc:  # noqa: BLE001
        problems.append(f"Autostart: {exc}")

    def failed(_func, path, exc_info):
        problems.append(f"{path}: {exc_info[1] if isinstance(exc_info, tuple) else exc_info}")

    for d in dirs if dirs is not None else data_dirs():
        if not d.exists():
            continue
        if not is_alupc_dir(d):  # Sicherung gegen falsche Pfade
            problems.append(f"{d}: übersprungen")
            continue
        if sys.version_info >= (3, 12):
            shutil.rmtree(d, onexc=failed)
        else:
            shutil.rmtree(d, onerror=failed)
    return problems


_pending = {"on": False}
LEFTOVER_FILE = "nicht-geloescht.txt"


def pending() -> bool:
    return _pending["on"]


def request(config) -> None:
    """Zurücksetzen anstoßen: nichts mehr speichern, AluPC beenden. Gelöscht wird nach dem Beenden
    (siehe app.main → finish_and_restart), dann startet AluPC neu – mit der Ersteinrichtung."""
    from PySide6.QtWidgets import QApplication

    config.frozen = True
    _pending["on"] = True
    QApplication.quit()


def finish_and_restart() -> None:
    problems = wipe()
    if problems:  # der neue Start zeigt, was nicht ging
        try:
            config_dir().mkdir(parents=True, exist_ok=True)
            (config_dir() / LEFTOVER_FILE).write_text("\n".join(problems), encoding="utf-8")
        except OSError:
            pass
    import subprocess

    from .platform.autostart import launch_command

    flags = 0x00000008 if sys.platform.startswith("win") else 0  # DETACHED_PROCESS
    try:
        # PyInstaller: das neue AluPC soll sich wie ein normaler Start einrichten (nicht die Umgebung erben)
        env = {**os.environ, "PYINSTALLER_RESET_ENVIRONMENT": "1"}
        subprocess.Popen(launch_command(), cwd=os.path.expanduser("~"), creationflags=flags, env=env,
                         start_new_session=not sys.platform.startswith("win"))
    except OSError:
        pass


def report_leftovers(parent) -> None:
    path = config_dir() / LEFTOVER_FILE
    if not path.is_file():
        return
    try:
        text = path.read_text(encoding="utf-8")
        path.unlink()
    except OSError:
        return
    from PySide6.QtWidgets import QMessageBox

    QMessageBox.information(parent, "Daten gelöscht",
                            "AluPC wurde zurückgesetzt. Nicht alles ließ sich löschen:\n\n" + text[:1500])
