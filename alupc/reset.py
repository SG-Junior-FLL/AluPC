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


_pending = {"on": False, "sync_folder": ""}
LEFTOVER_FILE = "nicht-geloescht.txt"
RETRY_FILE = "alupc-reset-rest.txt"  # im Temp-Ordner: was der Neustart noch löschen soll


def _retry_path() -> Path:
    import tempfile

    return Path(tempfile.gettempdir()) / RETRY_FILE


def clear_sync_folder(folder: str | Path) -> list[str]:
    """Abgeglichene Einstellungen im Sync-Ordner löschen – sonst holt AluPC sie nach dem Neustart vom anderen
    System zurück (dann wirkt „Alle Daten löschen“, als hätte es nichts getan)."""
    problems = []
    folder = Path(folder)
    if not folder.is_dir():
        return problems
    for item in list(folder.glob("alupc-sync*.json")) + [folder / "Dateien"]:
        try:
            if item.is_dir():
                shutil.rmtree(item)
            elif item.exists():
                item.unlink()
        except OSError as exc:
            problems.append(f"{item}: {exc}")
    return problems


def pending() -> bool:
    return _pending["on"]


KEEP_KEYS = ["scenes", "start_page", "media", "websites", "overlays"]  # „Szenen & Startseite behalten“


def backup_dir() -> Path:
    """Sicherungen vor dem Zurücksetzen: Dokumente/AluPC-Sicherungen (liegt NICHT in den gelöschten Ordnern)."""
    try:
        from PySide6.QtCore import QStandardPaths

        docs = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation)
    except Exception:  # noqa: BLE001
        docs = ""
    return Path(docs or Path.home()) / "AluPC-Sicherungen"


def save_backup(config) -> Path | None:
    """Alle Einstellungen als Datei sichern (wie „Exportieren“) – lässt sich unter Sichern & Sync wieder laden."""
    import json
    import time

    from .settings_sync import SECTIONS, export_settings

    try:
        folder = backup_dir()
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"AluPC-Sicherung-{time.strftime('%Y-%m-%d_%H%M%S')}.json"
        data = export_settings(config, list(SECTIONS))
        path.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
        return path
    except (OSError, ValueError, TypeError):
        return None


def request(config, clear_sync: bool = False, keep: bool = False, backup: Path | None = None) -> None:
    """Zurücksetzen anstoßen: nichts mehr speichern, AluPC beenden. Gelöscht wird nach dem Beenden
    (siehe app.main → finish_and_restart), dann startet AluPC neu – mit der Ersteinrichtung.
    clear_sync: auch die abgeglichenen Einstellungen im Dual-Boot-Ordner löschen und den Abgleich auslassen."""
    from PySide6.QtWidgets import QApplication

    sync = config.data.get("sync") or {}
    _pending["sync_folder"] = str(sync.get("folder") or "") if clear_sync else ""
    _pending["clear_sync"] = clear_sync
    _pending["keep"] = {k: config.data[k] for k in KEEP_KEYS if k in config.data} if keep else {}
    _pending["backup"] = str(backup or "")
    config.frozen = True
    _pending["on"] = True
    QApplication.quit()


def finish_and_restart(attempts: int = 6, pause: float = 0.5) -> None:
    import time

    try:  # eigene offene Dateien zuerst schließen (sonst: „wird von einem anderen Prozess verwendet“)
        from .bug_report import close_crash_log

        close_crash_log()
    except Exception:  # noqa: BLE001
        pass
    problems = wipe()
    for _ in range(attempts - 1):  # Browser-Hilfsprozesse halten Dateien oft noch kurz offen → nochmal
        if not problems:
            break
        time.sleep(pause)
        problems = wipe()
    fresh: dict = dict(_pending.get("keep") or {})  # behaltene Bereiche (Szenen, Startseite …)
    if _pending.get("clear_sync"):
        if _pending.get("sync_folder"):
            problems += clear_sync_folder(_pending["sync_folder"])
        fresh["sync"] = {"declined": True}  # Abgleich bleibt aus, bis man ihn wieder einschaltet
    if _pending.get("backup"):
        fresh["reset_info"] = {"backup": _pending["backup"]}  # der Neustart sagt, wo die Sicherung liegt
    if fresh:
        import json

        try:
            config_dir().mkdir(parents=True, exist_ok=True)
            (config_dir() / "config.json").write_text(json.dumps(fresh, ensure_ascii=False), encoding="utf-8")
        except OSError as exc:
            problems.append(f"Einstellungen: {exc}")
    if problems:  # was jetzt noch klemmt, löscht der Neustart als Allererstes (bevor er Dateien öffnet)
        try:
            _retry_path().write_text("\n".join(str(d) for d in data_dirs()), encoding="utf-8")
        except OSError:
            pass
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


def cleanup_pending() -> None:
    """Beim Start (noch bevor AluPC Protokolle öffnet): Reste vom letzten „Alle Daten löschen“ entfernen."""
    path = _retry_path()
    if not path.is_file():
        return
    try:
        dirs = [Path(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        path.unlink()
    except OSError:
        return
    keep = None
    cfg = config_dir() / "config.json"
    try:  # die frisch geschriebenen Einstellungen (Abgleich aus, behaltene Szenen) behalten
        keep = cfg.read_text(encoding="utf-8") if cfg.is_file() else None
    except OSError:
        keep = None
    problems = [p for p in wipe([d for d in dirs if is_alupc_dir(d)]) if not p.startswith("Autostart")]
    if keep is not None:
        try:
            config_dir().mkdir(parents=True, exist_ok=True)
            cfg.write_text(keep, encoding="utf-8")
        except OSError:
            pass
    leftover = config_dir() / LEFTOVER_FILE
    try:
        if problems:
            config_dir().mkdir(parents=True, exist_ok=True)
            leftover.write_text("\n".join(problems), encoding="utf-8")
        elif leftover.exists():
            leftover.unlink()  # beim zweiten Versuch ging alles → keine Fehlermeldung zeigen
    except OSError:
        pass


def report_leftovers(parent, config=None) -> None:
    """Nach dem Neustart: sagen, wo die Sicherung liegt – und was sich nicht löschen ließ."""
    info = (config.data.pop("reset_info", None) if config is not None else None) or {}
    lines = []
    if info.get("backup"):
        lines.append(f"Sicherung: {info['backup']}\nZurückholen: Setup → Sichern & Sync → „Importieren …“.")
        config.save()
    path = config_dir() / LEFTOVER_FILE
    if path.is_file():
        try:
            lines.append("Nicht alles ließ sich löschen:\n" + path.read_text(encoding="utf-8")[:1500])
            path.unlink()
        except OSError:
            pass
    if not lines:
        return
    from PySide6.QtWidgets import QMessageBox

    QMessageBox.information(parent, "AluPC zurückgesetzt", "AluPC wurde zurückgesetzt.\n\n" + "\n\n".join(lines))
