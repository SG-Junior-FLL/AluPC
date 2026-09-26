"""CI (Windows): Startet AluPC den AirPlay-Empfänger über uxplay-windows wirklich, und wird er im Netz angekündigt?

Ausgabe als GitHub-Hinweise (::notice), damit das Ergebnis ohne Anmeldung lesbar ist. Ein echtes iPhone gibt es
im CI nicht – geprüft wird: Programm gefunden, läuft, AirPlay-Port offen, per Bonjour mit AluPCs Namen sichtbar.
"""

import os
import subprocess
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, os.getcwd())

from PySide6.QtCore import QCoreApplication  # noqa: E402

from alupc import handy  # noqa: E402
from alupc.config import Config  # noqa: E402


def note(text: str) -> None:
    print(f"::notice title=AirPlay-Probe::{text}", flush=True)


def bonjour_names() -> list[str]:
    try:
        browse = subprocess.run(["dns-sd", "-B", "_airplay._tcp", "local"], capture_output=True, timeout=8)
        found = browse.stdout.decode("utf-8", errors="replace")
    except subprocess.TimeoutExpired as exc:  # dns-sd läuft endlos – nach 8 s abbrechen und Ausgabe lesen
        # dns-sd gibt UTF-8 aus (nicht die Konsolen-Codepage) – sonst wird das geschützte Leerzeichen zu „Â “
        found = exc.stdout.decode("utf-8", errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
    except OSError as exc:
        return [f"(dns-sd nicht ausführbar: {exc})"]
    names = set()
    for line in found.splitlines():
        if " Add " in line and "_airplay._tcp." in line:
            names.add(line.split("_airplay._tcp.", 1)[1].strip().replace("\xa0", " "))  # geschütztes Leerzeichen
    return sorted(names)


def wait(app, seconds, stop=lambda: False):
    end = time.time() + seconds
    while time.time() < end and not stop():
        app.processEvents()
        time.sleep(0.1)


def main():
    app = QCoreApplication([])
    cfg = Config(Path(os.environ.get("RUNNER_TEMP", ".")) / "airplay-probe.json")
    cfg["handy"] = {**cfg["handy"], "airplay_name": "AluPC CI-Test", "pin": "1234"}
    # Wie beim Nutzer: uxplay-windows läuft schon mit EIGENEN Einstellungen (Autostart, Standardname, kein Code)
    autostarts = handy.uxplay_autostarts()
    exe = handy.find_uxplay_windows()
    try:
        handy.uxplay_windows_arguments_file().unlink()
    except OSError:
        pass
    foreign = subprocess.Popen([exe], cwd=str(Path(exe).parent)) if exe else None
    time.sleep(12)
    note(f"FREMD vorher: Autostarts {autostarts} · Bonjour {bonjour_names()} · läuft {foreign and foreign.poll() is None}")
    server = handy.AirPlayServer(cfg)
    failed, notices = [], []
    server.failed.connect(failed.append)
    server.notice.connect(notices.append)
    done, not_done = handy.disable_uxplay_autostarts()
    mode = server.set_background(True)  # wie AluPC beim Start („immer bereit“)
    note(f"Programm: {server.binary()} · Bonjour: {handy.bonjour_installed()} · Modus: {mode} · "
         f"noch einzurichten: {[label for label, _ in handy.setup_plan(cfg)]}")
    wait(app, 20, lambda: bool(failed))
    ports = subprocess.run(["netstat", "-ano", "-p", "tcp"], capture_output=True, text=True).stdout
    listening = sorted({line.split()[1].rsplit(":", 1)[-1] for line in ports.splitlines()
                        if "LISTEN" in line and line.split()[1].rsplit(":", 1)[-1] in ("7000", "7001", "7100")})
    note(f"Start: läuft {server.running()} · Ports {listening or 'keiner'} · "
         f"arguments.txt {handy.uxplay_windows_arguments_file().read_text(encoding='utf-8')!r}"
         + (f" · Fehler: {failed[0]}" if failed else "") + (f" · Hinweis: {notices[0]}" if notices else ""))
    names = bonjour_names()
    note(f"ÜBERNAHME: {'OK' if names == ['AluPC CI-Test'] else 'FEHLER'} · Bonjour {names} · Autostart aus {done} "
         f"· nicht möglich {not_done} · noch da {handy.uxplay_autostarts()}")
    # Umbenennen und Code ändern, WÄHREND es läuft – so wie in Setup oder im Fenster „Handy“
    restarted = server.update_settings(airplay_name="AluPC Umbenannt", pin="4711")
    wait(app, 15, lambda: bool(failed))
    names = bonjour_names()
    ok = "AluPC Umbenannt" in names and "AluPC CI-Test" not in names
    note(f"UMBENENNEN IM BETRIEB: {'OK' if ok else 'FEHLER'} · neu gestartet {restarted} · läuft "
         f"{server.running()} · Bonjour {names} · arguments.txt "
         f"{handy.uxplay_windows_arguments_file().read_text(encoding='utf-8')!r} · läuft als "
         f"{server.running_settings()}" + (f" · Fehler: {failed[-1]}" if failed else "")
         + (f" · Hinweise: {notices}" if notices else ""))
    server.shutdown()


try:
    main()
except BaseException:  # noqa: BLE001 – Fehler als lesbare Hinweise ausgeben
    print("::error title=AirPlay-Probe::" + " | ".join(traceback.format_exc().splitlines()[-8:]), flush=True)
    raise
