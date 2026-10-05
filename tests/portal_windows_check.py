"""Windows-CI (Runner hat Administratorrechte): das Anmeldeseiten-Skript ECHT ausführen.

Geprüft wird: hosts-Einträge greifen (Prüf-Adresse → PC), Port 80 → AluPC-Port über portproxy, eine Handy-Prüfung
(GET http://connectivitycheck.gstatic.com/generate_204) kommt bei AluPC an – und nach dem Ausschalten ist alles
wieder weg. Statt der Hotspot-Adresse wird 127.0.0.1 genommen (der Runner hat kein WLAN).
Nicht prüfbar hier: die „Ja“-Abfrage (UAC) und ob der Mobile Hotspot die hosts-Datei an Handys weitergibt.
"""

import base64
import http.client
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from alupc import hotspot  # noqa: E402

PORT = 18765
seen = []


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        seen.append(self.headers.get("Host"))
        self.send_response(302)
        self.send_header("Location", f"http://127.0.0.1:{PORT}/anmelden")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, *a):
        pass


def fail(msg):
    print(f"::error title=Anmeldeseite (Windows)::{msg}")
    sys.exit(1)


def listener_on_80():
    out = subprocess.run(["powershell", "-NoProfile", "-Command",
                          "Get-NetTCPConnection -LocalPort 80 -State Listen -ErrorAction SilentlyContinue | "
                          "ForEach-Object { $_.LocalAddress + ' ' + $_.OwningProcess + ' ' + "
                          "(Get-Process -Id $_.OwningProcess).ProcessName }"], capture_output=True, text=True)
    return out.stdout.strip()


def main():
    busy = listener_on_80()
    if busy:  # Runner: oft IIS/http.sys – wie auf einem normalen PC ohne Webserver: anhalten
        print(f"::notice title=Port 80 vorher belegt::{busy}")
        subprocess.run(["powershell", "-NoProfile", "-Command",
                        "Stop-Service W3SVC,WAS -Force -ErrorAction SilentlyContinue; "
                        "netsh http show servicestate view=requestq | Select-String 'URL' | Select-Object -First 5"])
        busy = listener_on_80()
        print(f"::notice title=Port 80 danach::{busy or 'frei'}")
    httpd = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    flag = Path(tempfile.gettempdir()) / "alupc-portal-ci"
    flag.write_text("an")
    script = hotspot.portal_script_windows("127.0.0.1", PORT, flag, os.getpid())
    enc = base64.b64encode(script.encode("utf-16-le")).decode()
    proc = subprocess.Popen(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-EncodedCommand", enc])
    state = hotspot._wait_ready(flag, proc, 60)
    if not state:
        fail(f"Skript meldet nicht „bereit“ (Rückgabe {proc.poll()})")
    if state.startswith("belegt"):
        flag.unlink()
        proc.wait(20)
        if busy:  # Port war wirklich schon belegt → richtig erkannt, mehr lässt sich hier nicht prüfen
            print(f"::warning title=Anmeldeseite (Windows)::Port 80 belegt, Wächter meldet es richtig ({state})")
            return
        fail(f"Wächter meldet belegt, obwohl Port 80 frei war ({state})")
    hosts = Path(os.environ["SystemRoot"]) / "System32" / "drivers" / "etc" / "hosts"
    if "alupc-portal" not in hosts.read_text(errors="replace"):
        fail("hosts-Einträge fehlen")
    ip = socket.gethostbyname("connectivitycheck.gstatic.com")
    if ip != "127.0.0.1":
        fail(f"connectivitycheck.gstatic.com → {ip} (hosts greift nicht)")
    status = 0
    for _ in range(10):  # portproxy braucht manchmal einen Moment
        try:
            c = http.client.HTTPConnection("connectivitycheck.gstatic.com", 80, timeout=5)
            c.request("GET", "/generate_204")
            status = c.getresponse().status
            break
        except OSError:
            time.sleep(1)
    if status != 302 or "connectivitycheck.gstatic.com" not in seen:
        fail(f"Handy-Prüfung kam nicht bei AluPC an (Status {status}, gesehen {seen})")
    flag.unlink()
    try:
        proc.wait(20)
    except subprocess.TimeoutExpired:
        fail("Wächter beendet sich nicht")
    if "alupc-portal" in hosts.read_text(errors="replace"):
        fail("hosts-Einträge nach dem Ausschalten noch da")
    proxies = subprocess.run(["netsh", "interface", "portproxy", "show", "v4tov4"], capture_output=True,
                             text=True).stdout
    if str(PORT) in proxies:
        fail("portproxy nach dem Ausschalten noch da")
    print("::notice title=Anmeldeseite (Windows)::hosts + portproxy + Weiterleitung ok, danach sauber aufgeräumt")
    httpd.shutdown()


if __name__ == "__main__":
    main()
