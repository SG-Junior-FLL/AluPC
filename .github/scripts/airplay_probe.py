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


def main():
    app = QCoreApplication([])
    cfg = Config(Path(os.environ.get("RUNNER_TEMP", ".")) / "airplay-probe.json")
    cfg["handy"] = {**cfg["handy"], "airplay_name": "AluPC CI-Test", "pin": "1234"}
    server = handy.AirPlayServer(cfg)
    note(f"Programm: {server.binary()} · Bonjour: {handy.bonjour_installed()} · "
         f"noch einzurichten: {[label for label, _ in handy.setup_plan(cfg)]}")
    note(f"Modus: {server.acquire(want_stream=False)}")
    failed = []
    server.failed.connect(failed.append)
    end = time.time() + 20
    while time.time() < end and not failed:
        app.processEvents()
        time.sleep(0.1)
    note(f"läuft nach 20 s: {server.running()}" + (f" · Fehler: {failed[0]}" if failed else "")
         + " · Ausgabe: " + " | ".join(line[:120] for line in server.log[-10:]))
    note(f"arguments.txt: {handy.uxplay_windows_arguments_file().read_text(encoding='utf-8')!r}")
    ports = subprocess.run(["netstat", "-ano", "-p", "tcp"], capture_output=True, text=True).stdout
    listening = sorted({line.split()[1].rsplit(":", 1)[-1] for line in ports.splitlines()
                        if "LISTEN" in line and line.split()[1].rsplit(":", 1)[-1] in ("7000", "7001", "7100")})
    note(f"AirPlay-Ports offen: {listening or 'keiner'}")
    try:
        browse = subprocess.run(["dns-sd", "-B", "_airplay._tcp", "local"], capture_output=True, text=True, timeout=8)
        found = browse.stdout
    except subprocess.TimeoutExpired as exc:  # dns-sd läuft endlos – nach 8 s abbrechen und Ausgabe lesen
        found = exc.stdout.decode(errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
    except OSError as exc:
        found = f"(dns-sd nicht ausführbar: {exc})"
    lines = [line.strip() for line in found.splitlines() if "AluPC" in line or "dns-sd" in line]
    note("Bonjour-Suche _airplay._tcp: " + (" | ".join(lines) if lines else "AluPC NICHT gefunden"))
    note("Protokoll: " + " | ".join(line[:160] for line in handy.uxplay_windows_log_tail(8)))  # max. 10 Hinweise/Schritt
    server.shutdown()
    time.sleep(1)
    note(f"nach dem Beenden läuft es noch: {server.running()}")


try:
    main()
except BaseException:  # noqa: BLE001 – Fehler als lesbare Hinweise ausgeben
    print("::error title=AirPlay-Probe::" + " | ".join(traceback.format_exc().splitlines()[-8:]), flush=True)
    raise
