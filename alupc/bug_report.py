"""Fehlerbericht per Knopf: eine ZIP-Datei mit allem, was man zum Helfen braucht – ohne Geheimnisse.

Inhalt: Beschreibung (was ist passiert?), Diagnose (Monitore, Spiegeln, AirPlay …), Einstellungen (Codes,
PINs, Passwörter geschwärzt), AluPCs Fehlerprotokoll (Programmfehler mit Stelle im Code), Absturzprotokoll,
das letzte AirPlay-Protokoll und auf Wunsch ein Bild vom AluPC-Fenster (nur das Fenster, nicht der Bildschirm).
"""

from __future__ import annotations

import json
import os
import sys
import time
import traceback
import zipfile
from pathlib import Path

from . import __version__
from .config import config_dir

SECRET_KEYS = ("pin", "code", "password", "passwort", "secret", "token", "key")
MAX_LOG = 300_000  # Bytes je Protokoll im Bericht


def error_log() -> Path:
    return config_dir() / "fehler.log"


def crash_log() -> Path:
    return config_dir() / "absturz.log"


def redact(value, key: str = ""):
    """Einstellungen ohne Geheimnisse (Handy-Code, AirPlay-PIN …)."""
    if isinstance(value, dict):
        return {k: redact(v, k) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v, key) for v in value]
    low = key.lower()
    if isinstance(value, str) and value and any(low == s or low.endswith("_" + s) for s in SECRET_KEYS):
        return "•••"
    return value


def _tail(path: Path, limit: int = MAX_LOG) -> bytes:
    try:
        size = path.stat().st_size
        with open(path, "rb") as f:
            if size > limit:
                f.seek(size - limit)
            return f.read()
    except OSError:
        return b""


# --------------------------------------------------------------------------- Fehler mitschreiben
def log_exception(exc_type, exc, tb) -> None:
    """Unbehandelte Programmfehler ins Fehlerprotokoll (Datei bleibt klein: ältere Hälfte fliegt raus)."""
    try:
        path = error_log()
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.stat().st_size > 2 * MAX_LOG:
            keep = _tail(path, MAX_LOG)
            path.write_bytes(keep)
        text = "".join(traceback.format_exception(exc_type, exc, tb))
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"\n=== {time.strftime('%Y-%m-%d %H:%M:%S')} · AluPC {__version__} ===\n{text}")
    except Exception:  # noqa: BLE001 - Protokollieren darf nie selbst abstürzen
        pass


def install() -> None:
    """Beim Start: Programmfehler mitschreiben (weiter wie bisher anzeigen) und harte Abstürze festhalten."""
    previous = sys.excepthook

    def hook(exc_type, exc, tb):
        log_exception(exc_type, exc, tb)
        previous(exc_type, exc, tb)

    sys.excepthook = hook
    try:
        import faulthandler

        crash_log().parent.mkdir(parents=True, exist_ok=True)
        global _crash_file
        _crash_file = open(crash_log(), "a", encoding="utf-8")  # noqa: SIM115 - bleibt offen bis zum Ende
        _crash_file.write(f"\n=== Start {time.strftime('%Y-%m-%d %H:%M:%S')} · AluPC {__version__} ===\n")
        _crash_file.flush()
        faulthandler.enable(_crash_file)
    except Exception:  # noqa: BLE001
        pass


_crash_file = None


# --------------------------------------------------------------------------- Bericht bauen
def default_folder() -> Path:
    from PySide6.QtCore import QStandardPaths

    for kind in (QStandardPaths.DesktopLocation, QStandardPaths.DownloadLocation, QStandardPaths.HomeLocation):
        folder = QStandardPaths.writableLocation(kind)
        if folder and Path(folder).is_dir():
            return Path(folder)
    return Path.home()


def _airplay_log() -> tuple[str, bytes] | None:
    candidates = []
    local = os.environ.get("LOCALAPPDATA")
    if local:
        candidates += list((Path(local) / "uxplay-windows" / "logs").glob("uxplay-*.log"))
    candidates += list(config_dir().glob("uxplay*.log"))
    try:
        newest = max(candidates, key=lambda f: f.stat().st_mtime)
    except ValueError:
        return None
    return newest.name, _tail(newest)


def build(controller, description: str = "", screenshot=None, folder: Path | None = None,
          diagnosis: str | None = None) -> Path:
    """ZIP erstellen und den Pfad liefern. `screenshot`: QImage vom AluPC-Fenster (oder None)."""
    folder = folder or default_folder()
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"AluPC-Fehlerbericht-{time.strftime('%Y%m%d-%H%M%S')}.zip"
    if diagnosis is None:
        from . import diagnose

        try:
            diagnosis = diagnose.report(controller)
        except Exception as exc:  # noqa: BLE001
            diagnosis = f"Diagnose fehlgeschlagen: {exc}\n{traceback.format_exc()}"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("beschreibung.txt", (description.strip() or "(keine Beschreibung)") +
                   f"\n\nAluPC {__version__} · {time.strftime('%Y-%m-%d %H:%M:%S')} · {sys.platform}\n")
        z.writestr("diagnose.txt", diagnosis)
        z.writestr("einstellungen.json", json.dumps(redact(controller.config.data), indent=1, ensure_ascii=False))
        for name, log in (("fehler.log", error_log()), ("absturz.log", crash_log())):
            data = _tail(log)
            if data:
                z.writestr(name, data)
        airplay = _airplay_log()
        if airplay:
            z.writestr(f"airplay-{airplay[0]}", airplay[1])
        if screenshot is not None and not screenshot.isNull():
            from PySide6.QtCore import QBuffer, QByteArray, QIODevice

            data = QByteArray()
            buf = QBuffer(data)
            buf.open(QIODevice.WriteOnly)
            screenshot.save(buf, "PNG")
            buf.close()
            z.writestr("alupc-fenster.png", bytes(data))
    return path
