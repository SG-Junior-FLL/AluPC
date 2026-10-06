"""Windows-CI (Administrator): WLAN-Anmeldeseite ECHT durchspielen – wie unter Linux, mit einem „Handy“.

Aufbau (tests/windows/hotspot_sim.ps1): Windows-Internetfreigabe (ICS – derselbe Dienst wie der Mobile Hotspot)
auf einem Loopback-Adapter, PC = 192.168.137.1, Windows-DNS lauscht auf 0.0.0.0:53. Das Handy ist ein
Windows-Container (192.168.137.50, DNS/Gateway 192.168.137.1) – wie ein Handy im Hotspot. Auf dem PC laufen das
echte AluPC (Controller, Webserver, Minispiele, eigener DNS) und das echte Administrator-Skript (über „Als
Administrator“ gestartet, wie in der App).

Spiele-WLAN (geschlossen):
  1. AluPC-DNS übernimmt 192.168.137.1:53 (Selbsttest) – jede Adresse zeigt auf den PC
  2. Android-/iPhone-Prüfung → 302 zur Anmeldeseite (über Port 80 → AluPC)
  3. Anmeldeseite mit Namensfeld → Spielseite → Beitreten → Spieler ist im Spiel
  4. Kein Weg vorbei: fremder DNS (8.8.8.8) und Internet per IP (1.1.1.1:443) gesperrt
  5. Ausschalten → portproxy, Firewall, Sperre weg, Port 53 frei
Normaler Hotspot (offen): Prüf-Adressen → PC, alles andere normal, Internet geht.

Nicht prüfbar hier: echte WLAN-Karte, ob das Handy-Betriebssystem das Anmeldefenster selbst öffnet, die UAC-Abfrage
(Runner ist schon Administrator).
"""

from __future__ import annotations

import base64
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
IP, PHONE_IP = "192.168.137.1", "192.168.137.50"
results: list[tuple[bool, str]] = []


def ok(cond, text: str) -> bool:
    results.append((bool(cond), text))
    print(("  OK   " if cond else "  FEHL ") + text, flush=True)
    return bool(cond)


def ps(cmd: str, timeout: float = 120) -> str:
    r = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True,
                       timeout=timeout)
    return (r.stdout + r.stderr).strip()


PHONE = r"""
$ErrorActionPreference = 'Continue'
$ProgressPreference = 'SilentlyContinue'
function Get-Url($u) {
  $r = [Net.HttpWebRequest]::Create($u); $r.AllowAutoRedirect = $false; $r.Timeout = 8000; $r.Proxy = $null
  try { $x = $r.GetResponse() } catch [Net.WebException] { $x = $_.Exception.Response }
  if (-not $x) { return @{ s = 0; l = ''; b = '' } }
  $b = (New-Object IO.StreamReader($x.GetResponseStream())).ReadToEnd()
  $o = @{ s = [int]$x.StatusCode; l = '' + $x.Headers['Location']; b = $b }; $x.Close(); return $o
}
function Resolve($n, $server) {
  try {
    $a = if ($server) { Resolve-DnsName $n -Server $server -Type A -DnsOnly -QuickTimeout -ErrorAction Stop }
         else { Resolve-DnsName $n -Type A -DnsOnly -QuickTimeout -ErrorAction Stop }
    return (($a | Where-Object Type -eq 'A' | ForEach-Object IPAddress) -join ',')
  } catch { return 'FEHLER' }
}
$o = [ordered]@{}
$o.dns_check = Resolve 'connectivitycheck.gstatic.com' $null
$o.dns_any = Resolve 'www.example.com' $null
$o.dns_8888 = Resolve 'example.org' '8.8.8.8'
$c = New-Object Net.Sockets.TcpClient
try { $o.inet_1111 = $c.ConnectAsync('1.1.1.1', 443).Wait(5000) -and $c.Connected } catch { $o.inet_1111 = $false }
$c.Close()
$a = Get-Url 'http://connectivitycheck.gstatic.com/generate_204'; $o.android = "$($a.s) $($a.l)"
$i = Get-Url 'http://captive.apple.com/hotspot-detect.html'; $o.iphone = "$($i.s) $($i.l)"
if ($MODE -eq 'spiele' -and $a.l) {
  $p = Get-Url $a.l
  $o.portal = $p.s; $o.portal_name = ($p.b -match 'id="n"') -and ($p.b -match 'Mitspielen')
  $m = [regex]::Match($p.b, 'location.href = "([^"]+)" \+ "&name="')
  $game = $m.Groups[1].Value.Replace('&amp;', '&'); $o.game_url = $game
  $token = [regex]::Match($game, '[?&]u=([^&]+)').Groups[1].Value
  $o.game_page = (Get-Url ($game + '&name=Lena')).s
  $base = ([Uri]$game).GetLeftPart('Authority')
  try {
    $j = Invoke-RestMethod -Uri "$base/api/spiel" -Method Post -ContentType 'application/json' -UseBasicParsing `
      -Body (@{ u = [Uri]::UnescapeDataString($token); action = 'join'; name = 'Lena' } | ConvertTo-Json)
    $o.join = 200
  } catch { $o.join = [int]$_.Exception.Response.StatusCode }
}
'JSON:' + ($o | ConvertTo-Json -Compress)
"""


def phone(mode: str, image: str, pump) -> dict:
    script = f"$MODE = '{mode}'\n" + PHONE
    enc = base64.b64encode(script.encode("utf-16-le")).decode()
    cmd = ["docker", "run", "--rm", "--network", "hotspot", "--ip", PHONE_IP, "--dns", IP, image,
           "powershell", "-NoProfile", "-EncodedCommand", enc]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    end = time.time() + 400
    while proc.poll() is None and time.time() < end:
        pump(0.05)
    out = proc.communicate()[0] if proc.poll() is not None else (proc.kill() or "Zeitüberschreitung")
    for line in out.splitlines():
        if line.startswith("JSON:"):
            return json.loads(line[5:])
    print(out[-1500:])
    return {}


def forwarding(alias: str) -> str:
    return ps(f"(Get-NetIPInterface -InterfaceAlias '{alias}' -AddressFamily IPv4).Forwarding")


def main() -> int:
    image = sys.argv[1] if len(sys.argv) > 1 else "mcr.microsoft.com/windows/servercore:ltsc2022"
    tmp = Path(tempfile.mkdtemp(prefix="alupc-portal-"))
    os.environ.update(QT_QPA_PLATFORM="offscreen", ALUPC_NO_AUTO_WIFI="1", APPDATA=str(tmp),
                      LOCALAPPDATA=str(tmp))
    busy = ps("Get-NetTCPConnection -LocalPort 80 -State Listen -EA 0 | % { $_.LocalAddress }")
    if busy:  # Runner: IIS/http.sys – wie auf einem normalen PC ohne Webserver: anhalten
        ps("Stop-Service W3SVC,WAS -Force -EA 0")
    from PySide6.QtWidgets import QApplication

    app = QApplication([])

    def pump(sec: float) -> None:
        end = time.time() + sec
        while time.time() < end:
            app.processEvents()
            time.sleep(0.01)

    from alupc import hotspot as hs_mod
    from alupc.config import Config
    from alupc.controller import Controller

    cfg = Config(tmp / "config.json")
    cfg["cast"] = {**cfg["cast"], "port": hs_mod.PORTAL_PORT}
    controller = Controller(cfg)
    controller.display.available = lambda: False
    controller.cast.start()
    controller.start_games("tictactoe")
    hub = controller.cast.games
    alias = ps(f"(Get-NetIPAddress -IPAddress {IP}).InterfaceAlias")
    hs = hs_mod.hotspot
    target = f"http://{IP}:{hs_mod.PORTAL_PORT}/anmelden"

    # ================= Spiele-WLAN: geschlossen
    hs.running, hs.kind, hs.ssid, hs.password, hs.ip = True, "spiele", "AluPC-Spiele", "x", IP
    good, msg = hs_mod.start_portal(ip=IP, closed=True)  # echter Weg: „Als Administrator“ + Wächter
    ok(good and "eingeschränkt" not in msg, f"Anmeldeseite an (eigener DNS, Administrator-Skript): {msg}")
    hs.portal = good
    ok(hs_mod.dns_selftest(IP), "AluPC-DNS beantwortet 192.168.137.1:53 (statt Windows-DNS)")
    ok(f"{IP}" in ps("netsh interface portproxy show v4tov4"), "Port 80 → AluPC (portproxy)")
    ok("AluPC-Portal" in ps("netsh advfirewall firewall show rule name=AluPC-Portal"), "Firewall offen (80, 53)")
    ok(forwarding(alias) == "Disabled", f"Hotspot leitet nichts ins Internet weiter ({forwarding(alias)})")
    r = phone("spiele", image, pump)
    ok(r.get("dns_check") == IP, f"Handy-DNS: connectivitycheck.gstatic.com → {r.get('dns_check')}")
    ok(r.get("dns_any") == IP, f"Handy-DNS: jede andere Adresse → {r.get('dns_any')}")
    ok(r.get("android") == f"302 {target}", f"Android-Prüfung → {r.get('android')}")
    ok(r.get("iphone") == f"302 {target}", f"iPhone-Prüfung → {r.get('iphone')}")
    ok(r.get("portal") == 200 and r.get("portal_name"), "Anmeldeseite mit Namensfeld und „Mitspielen“")
    ok(r.get("game_page") == 200, f"Spielseite aus der Anmeldeseite öffnet ({r.get('game_page')})")
    ok(r.get("join") == 200, f"Beitreten aus dem Spiele-WLAN → {r.get('join')}")
    pump(0.3)
    ok(any(p.name == "Lena" for p in hub.players.values()), "„Lena“ ist im Spiel")
    ok(r.get("dns_8888") == "FEHLER", f"Fremder DNS-Server (8.8.8.8) gesperrt → {r.get('dns_8888')}")
    ok(r.get("inet_1111") is False, f"Internet per IP (1.1.1.1:443) gesperrt → {r.get('inet_1111')}")

    hs_mod.stop_portal()
    clean = False
    for _ in range(30):  # Wächter räumt in ≤ 2 s auf
        pump(0.5)
        if IP not in ps("netsh interface portproxy show v4tov4") and forwarding(alias) == "Enabled":
            clean = True
            break
    ok(clean, "Nach dem Ausschalten: portproxy weg, Weiterleitung wieder an")
    ok("AluPC-Portal" not in ps("netsh advfirewall firewall show rule name=AluPC-Portal"), "Firewall-Regeln weg")
    free = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        free.bind((IP, 53))
        released = True
    except OSError:
        released = False
    free.close()
    ok(released, "Port 53 wieder frei")

    # ================= normaler Hotspot: offen (Internet geht, Prüf-Adressen → Anmeldeseite)
    hs.kind = "normal"
    good, msg = hs_mod.start_portal(ip=IP, closed=False)
    ok(good and forwarding(alias) == "Enabled", f"Normaler Hotspot: Anmeldeseite an, Internet bleibt ({msg})")
    r = phone("normal", image, pump)
    ok(r.get("dns_check") == IP, f"Normal: Prüf-Adresse → {r.get('dns_check')}")
    ok(r.get("dns_any") not in ("", IP, "FEHLER", None), f"Normal: andere Adressen echt → {r.get('dns_any')}")
    ok(r.get("android") == f"302 {target}", f"Normal: Android-Prüfung → {r.get('android')}")
    ok(r.get("inet_1111") is True, f"Normal: Internet geht → {r.get('inet_1111')}")
    hs_mod.stop_portal()
    pump(4)
    controller.shutdown()
    failed = [t for good, t in results if not good]
    print(f"\n{len(results) - len(failed)}/{len(results)} Prüfungen bestanden")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
