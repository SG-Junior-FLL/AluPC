"""Windows-CI (Administrator): WLAN-Anmeldeseite ECHT durchspielen – wie unter Linux, mit einem „Handy“.

Aufbau (tests/windows/hotspot_sim.ps1): Windows-Internetfreigabe (ICS – derselbe Dienst wie der Mobile Hotspot)
auf einem Loopback-Adapter, PC = 192.168.137.1, Windows-DNS lauscht auf 0.0.0.0:53. Das Handy ist ein
Windows-Container (192.168.137.50, DNS/Gateway 192.168.137.1) – wie ein Handy im Hotspot. Auf dem PC laufen das
echte AluPC (Controller, Webserver, Minispiele, eigener DNS) und das echte Administrator-Skript (über „Als
Administrator“ gestartet, wie in der App).

Spiele-WLAN (geschlossen):
  1. AluPC-DNS auf 192.168.137.1:53 (genauer als der Windows-DNS auf 0.0.0.0) – jede Adresse zeigt auf den PC;
     eine Firewall-Sperre für AluPC (weggeklickte Windows-Frage) wird entfernt
  0. Monitor 2 zeigt genau EINEN QR-Code: den WLAN-Code (echter Decoder)
  2. Android-/iPhone-Prüfung → 302 zur Anmeldeseite (über Port 80 → AluPC)
  3. Anmeldeseite mit Namensfeld → Spielseite → Beitreten → Spieler ist im Spiel
  4. Kein Weg vorbei: fremder DNS (8.8.8.8) und Internet per IP (1.1.1.1:443) gesperrt; ein Handy aus einem
     anderen Netz (Docker-NAT) bekommt überall 403 – auch nicht „AluPC steuern“
  5. Ausschalten → portproxy, Firewall, Sperre weg, Port 53 wieder beim Windows-Dienst
Normaler Hotspot (offen): Prüf-Adressen → PC, alles andere normal, Internet geht.

Nicht prüfbar hier: echte WLAN-Karte, ob das Handy-Betriebssystem das Anmeldefenster selbst öffnet, die UAC-Abfrage
(Runner ist schon Administrator).
"""

from __future__ import annotations

import base64
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
IP, PHONE_IP = "192.168.137.1", "192.168.137.50"
CAST = {"port": 8765}  # Port von AluPCs Webserver (weicht aus, wenn 8765 belegt ist)
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
$sw = [Diagnostics.Stopwatch]::StartNew()
try { $tc = New-Object Net.Sockets.TcpClient; $tc.Connect('192.168.137.1', 443); $ns = $tc.GetStream(); $ns.ReadTimeout = 8000
      $ns.Write([byte[]](22, 3, 1), 0, 3); $buf = New-Object byte[] 8; $null = $ns.Read($buf, 0, 8) } catch {}
$o.https_ms = $sw.ElapsedMilliseconds
$pr = Get-Url 'http://192.168.137.1/'; $o.pc_root = "$($pr.s) $(($pr.b -match 'id="n"') -and ($pr.b -match 'Mitspielen'))"
$base0 = "http://192.168.137.1:$PORT"
$o.remote_page = (Get-Url "$base0/").s
try { Invoke-RestMethod -Uri "$base0/api/freigabe" -Method Post -ContentType 'application/json' -Body '{"name":"Handy"}' -UseBasicParsing | Out-Null; $o.ask_access = 200 }
catch { $o.ask_access = [int]$_.Exception.Response.StatusCode }
if ($MODE -eq 'spiele' -and $a.l) {
  $p = Get-Url $a.l
  $o.portal = $p.s; $o.portal_name = ($p.b -match 'id="n"') -and ($p.b -match 'Mitspielen')
  $m = [regex]::Match($p.b, 'location.href = "([^"]+)" \+ "&name="')
  $game = $base0 + $m.Groups[1].Value.Replace('&amp;', '&'); $o.game_url = $game
  $token = [regex]::Match($game, '[?&]u=([^&]+)').Groups[1].Value
  $o.game_page = (Get-Url ($game + '&name=Lena')).s
  $base = ([Uri]$game).GetLeftPart('Authority')
  try {
    $j = Invoke-RestMethod -Uri "$base/api/spiel" -Method Post -ContentType 'application/json' -UseBasicParsing `
      -Body (@{ u = [Uri]::UnescapeDataString($token); action = 'join'; name = 'Lena' } | ConvertTo-Json)
    $o.join = 200
  } catch { $o.join = [int]$_.Exception.Response.StatusCode }
  $pm = [regex]::Match($p.b, '"(/abstimmung\?u=[^"]+)"')
  $o.poll_button = $pm.Success -and ($p.b -match 'Abstimmen')
  if ($pm.Success) {
    $o.poll_page = (Get-Url ($base0 + $pm.Groups[1].Value)).s
    $pt = $pm.Groups[1].Value.Split('=')[1]
    try {
      Invoke-RestMethod -Uri "$base0/api/umfrage" -Method Post -ContentType 'application/json' -UseBasicParsing `
        -Body (@{ u = $pt; v = 'lena-handy'; c = 0 } | ConvertTo-Json) | Out-Null
      $o.vote = 200
    } catch { $o.vote = [int]$_.Exception.Response.StatusCode }
  }
}
'JSON:' + ($o | ConvertTo-Json -Compress)
"""


def phone(mode: str, image: str, pump) -> dict:
    script = f"$MODE = '{mode}'\n$PORT = {CAST['port']}\n" + PHONE
    enc = base64.b64encode(script.encode("utf-16-le")).decode()
    cmd = ["docker", "run", "--rm", "--network", "hotspot", "--ip", PHONE_IP, "--mac-address", "00:15:5d:00:00:50",
           "--dns", IP, image,
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


PROBE = r"""
$r = [Net.HttpWebRequest]::Create('http://connectivitycheck.gstatic.com/generate_204'); $r.AllowAutoRedirect = $false
$r.Timeout = 6000; $r.Proxy = $null
try { $x = $r.GetResponse() } catch [Net.WebException] { $x = $_.Exception.Response }
'JSON:' + (@{ android = $(if ($x) { [int]$x.StatusCode } else { 0 }) } | ConvertTo-Json -Compress)
"""


def phone_probe(image: str, pump) -> int:
    """Nur die Android-Prüfung (Status-Code, 0 = keine Antwort)."""
    enc = base64.b64encode(PROBE.encode("utf-16-le")).decode()
    proc = subprocess.Popen(["docker", "run", "--rm", "--network", "hotspot", "--ip", PHONE_IP, "--mac-address",
                             "00:15:5d:00:00:50", "--dns", IP, image, "powershell", "-NoProfile", "-EncodedCommand",
                             enc], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    end = time.time() + 300
    while proc.poll() is None and time.time() < end:
        pump(0.05)
    out = proc.communicate()[0] if proc.poll() is not None else (proc.kill() or "")
    for line in out.splitlines():
        if line.startswith("JSON:"):
            return int(json.loads(line[5:]).get("android", 0))
    print(out[-1500:])
    return -1


OUTSIDER = r"""
$ProgressPreference = 'SilentlyContinue'
function Code($u, $body) {
  $r = [Net.HttpWebRequest]::Create($u); $r.AllowAutoRedirect = $false; $r.Timeout = 8000; $r.Proxy = $null
  if ($body) { $r.Method = 'POST'; $r.ContentType = 'application/json'; $b = [Text.Encoding]::UTF8.GetBytes($body)
               $s = $r.GetRequestStream(); $s.Write($b, 0, $b.Length); $s.Close() }
  try { $x = $r.GetResponse(); $c = [int]$x.StatusCode; $x.Close(); return $c }
  catch [Net.WebException] { if ($_.Exception.Response) { return [int]$_.Exception.Response.StatusCode } return 0 }
}
$o = [ordered]@{}
$o.root = Code "$BASE/" $null
$o.spiel = Code "$BASE/spiel?u=$TOKEN" $null
$o.anmelden = Code "$BASE/anmelden" $null
$o.join = Code "$BASE/api/spiel" ('{"u":"' + $TOKEN + '","action":"join","name":"Fremd"}')
$o.status = Code "$BASE/api/status" $null
$o.freigabe = Code "$BASE/api/freigabe" '{"name":"x"}'
$o.abstimmung = Code "$BASE/abstimmung" $null
$o.umfrage = Code "$BASE/api/umfrage" '{"u":"x","v":"y","c":0}'
'JSON:' + ($o | ConvertTo-Json -Compress)
"""


def outsider(image: str, base: str, token: str, pump) -> dict:
    """Handy in einem ANDEREN Netz (Docker-NAT statt AluPC-WLAN) – darf nichts."""
    script = f"$BASE = '{base}'\n$TOKEN = '{token}'\n" + OUTSIDER
    enc = base64.b64encode(script.encode("utf-16-le")).decode()
    proc = subprocess.Popen(["docker", "run", "--rm", image, "powershell", "-NoProfile", "-EncodedCommand", enc],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    end = time.time() + 400
    while proc.poll() is None and time.time() < end:
        pump(0.05)
    out = proc.communicate()[0] if proc.poll() is not None else ""
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
    # wie nach der Installation: AluPC darf in der Firewall Verbindungen annehmen (sonst kommt NICHTS an –
    # dann wäre „abgelehnt“ von außen nicht prüfbar)
    ps(f"New-NetFirewallRule -DisplayName AluPC-Test -Direction Inbound -Action Allow -Program '{sys.executable}'")
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
    # Port 8765 belegt (anderes Programm) → AluPC weicht aus; Firewall, Weiterleitung und Anmeldeseite folgen
    blocker = socket.socket()
    blocker.bind(("0.0.0.0", hs_mod.PORTAL_PORT))
    blocker.listen(1)
    controller.cast.start()
    from alupc.cast_server import active_port

    CAST["port"] = active_port()
    ok(CAST["port"] and CAST["port"] != hs_mod.PORTAL_PORT,
       f"Port {hs_mod.PORTAL_PORT} belegt → AluPC nimmt Port {CAST['port']}")
    controller.start_games("tictactoe")
    hub = controller.cast.games
    alias = ps(f"(Get-NetIPAddress -IPAddress {IP}).InterfaceAlias")
    hs = hs_mod.hotspot
    target = f"http://{IP}:{CAST['port']}/anmelden"

    # ================= Spiele-WLAN: geschlossen
    hs.running, hs.kind, hs.ssid, hs.password, hs.ip = True, "spiele", "AluPC-Spiele", "k7m2p9qa", IP
    # Monitor 2: genau EIN QR-Code – der WLAN-Code dieses WLANs (echter Decoder liest ihn)
    import zxingcpp
    from PIL import Image

    from alupc.game_source import GameSource

    src = GameSource({})
    src.resize(1280, 720)
    pump(0.3)
    src.grab().save(str(tmp / "lobby.png"))
    codes = [c.text for c in zxingcpp.read_barcodes(Image.open(tmp / "lobby.png"))]
    ok(codes == [f"WIFI:T:WPA;S:{hs.ssid};P:{hs.password};;"], f"Monitor 2 (Lobby): genau 1 QR-Code = WLAN → {codes}")
    src.stop()
    controller.start_poll("Pizza oder Pasta?", ["Pizza", "Pasta"])  # Abstimmen: auch nur übers WLAN
    # Wie nach einer weggeklickten Windows-Firewall-Frage: Sperr-Regel für AluPC (hier: python.exe)
    ps(f"New-NetFirewallRule -DisplayName 'AluPC Testsperre' -Direction Inbound -Action Block "
       f"-Program '{sys.executable}' | Out-Null")
    before53 = ps("(Get-NetUDPEndpoint -LocalPort 53 -ErrorAction SilentlyContinue | "
                  "Where-Object LocalAddress -eq '0.0.0.0').OwningProcess")
    print("::notice title=Port 53 vorher::" + ps(
        "Get-NetUDPEndpoint -LocalPort 53 -ErrorAction SilentlyContinue | ForEach-Object { $p = $_.OwningProcess; "
        "\"$($_.LocalAddress) $p $((Get-Process -Id $p).ProcessName) \" + "
        "((Get-CimInstance Win32_Service -Filter \"ProcessId=$p\" | ForEach-Object Name) -join ',') }").replace("\n", " | "),
        flush=True)
    good, msg = hs_mod.start_portal(ip=IP, closed=True)  # echter Weg: Administrator + Wächter
    ok(good, f"Anmeldeseite an (Port 53 übernommen, Administrator-Skript): {msg}")
    print("::notice title=Port 53 (AluPC)::" + hs_mod.DNS_INFO, flush=True)
    owner = ps(f"(Get-NetUDPEndpoint -LocalPort 53 -ErrorAction SilentlyContinue | "
               f"Where-Object {{ $_.LocalAddress -in @('0.0.0.0', '{IP}') -and $_.OwningProcess -eq {os.getpid()} }}"
               f").LocalAddress")
    ok(owner.strip() != "", f"Port 53 gehört AluPC (vorher Prozess {before53 or '–'} auf 0.0.0.0, AluPC jetzt {owner})")
    ok(not ps("Get-NetFirewallRule -DisplayName 'AluPC Testsperre' -ErrorAction SilentlyContinue"),
       "Firewall-Sperre für AluPC entfernt")
    ok(ps("(Get-Service SharedAccess).Status") == "Running", "Windows-Hotspot-Dienst läuft weiter (nie angehalten)")
    hs.portal = good
    ok(hs_mod.dns_selftest(IP), "AluPC-DNS beantwortet 192.168.137.1:53 (statt Windows-DNS)")
    own80 = ps(f"Get-NetTCPConnection -LocalPort 80 -State Listen -ErrorAction SilentlyContinue | "
               f"Where-Object {{ $_.LocalAddress -eq '{IP}' -and $_.OwningProcess -eq {os.getpid()} }}")
    ok(own80 or f"{IP}" in ps("netsh interface portproxy show v4tov4"),
       f"Port 80 → AluPC ({'direkt' if own80 else 'Weiterleitung'})")
    ok("AluPC-Portal" in ps("netsh advfirewall firewall show rule name=AluPC-Portal"), "Firewall offen (80, 53)")
    hs_mod.portal_status()  # Selbsttest läuft im Hintergrund an
    for _ in range(20):
        pump(0.3)
        line = hs_mod.portal_status()
        if "Anmeldeseite am PC: antwortet nicht" not in line:
            break
    ok(line.startswith(f"Port 80 → AluPC-Seite (Port {CAST['port']})") and "Anmeldeseite am PC: " in line and "antwortet nicht" not in line,
       f"Hotspot-Fenster (gleich auf Windows und Linux): {line}")
    ok(forwarding(alias) == "Disabled", f"Hotspot leitet nichts ins Internet weiter ({forwarding(alias)})")
    r = phone("spiele", image, pump)
    ok(r.get("dns_check") == IP, f"Handy-DNS: connectivitycheck.gstatic.com → {r.get('dns_check')}")
    ok(r.get("dns_any") == IP, f"Handy-DNS: jede andere Adresse → {r.get('dns_any')}")
    ok(r.get("android") == f"302 {target}", f"Android-Prüfung → {r.get('android')}")
    ok(r.get("iphone") == f"302 {target}", f"iPhone-Prüfung → {r.get('iphone')}")
    ok(isinstance(r.get("https_ms"), int) and r["https_ms"] < 2000,
       f"HTTPS (443) wird sofort abgelehnt – Browser nehmen gleich HTTP ({r.get('https_ms')} ms)")
    ok(r.get("pc_root") == "200 True", f"Hotspot-Adresse im Browser ({IP}) → Anmeldeseite ({r.get('pc_root')})")
    ok(r.get("portal") == 200 and r.get("portal_name"), "Anmeldeseite mit Namensfeld und „Mitspielen“")
    ok(r.get("game_page") == 200, f"Spielseite aus der Anmeldeseite öffnet ({r.get('game_page')})")
    ok(r.get("join") == 200, f"Beitreten aus dem Spiele-WLAN → {r.get('join')}")
    ok(r.get("remote_page") == 200 and r.get("ask_access") == 200,
       f"„AluPC steuern“ aus dem WLAN: Seite {r.get('remote_page')}, am PC um Erlaubnis fragen {r.get('ask_access')}")
    ok(r.get("poll_button") and r.get("poll_page") == 200 and r.get("vote") == 200,
       f"Anmeldeseite → „Abstimmen“ → abgestimmt ({r.get('poll_page')}, {r.get('vote')})")
    pump(0.3)
    ok(controller.cast.poll is not None and sum(controller.cast.poll.counts()) == 1, "Stimme ist am PC angekommen")
    ok(any(p.name == "Lena" for p in hub.players.values()), "„Lena“ ist im Spiel")
    dns_n, probed = hs_mod.client_status(PHONE_IP)
    ok(dns_n > 0 and probed, f"Hotspot-Fenster zeigt beim Handy: DNS ✓ ({dns_n} Fragen), Anmeldeseite ✓ ({probed})")
    ok(r.get("dns_8888") == "FEHLER", f"Fremder DNS-Server (8.8.8.8) gesperrt → {r.get('dns_8888')}")
    ok(r.get("inet_1111") is False, f"Internet per IP (1.1.1.1:443) gesperrt → {r.get('inet_1111')}")

    # Internet pro Gerät: im Hotspot-Fenster freischalten → dieses Gerät kommt raus
    devices = controller.wlan_devices()
    me = next((d for d in devices if d["ip"] == PHONE_IP), None)
    ok(me is not None and not me["internet"], f"Hotspot-Fenster: Gerät gelistet, ohne Internet → {me} / {devices}")
    if me:
        controller.set_device_internet(me["mac"], me["name"], True)
        for _ in range(20):
            pump(0.5)
            if forwarding(alias) == "Enabled":
                break
        ok(forwarding(alias) == "Enabled", f"Freigeschaltet: Weiterleitung an ({forwarding(alias)})")
        r2 = phone("spiele", image, pump)
        ok(r2.get("dns_any") not in ("", IP, "FEHLER", None) and r2.get("inet_1111") is True,
           f"…das Gerät hat Internet: DNS echt ({r2.get('dns_any')}), 1.1.1.1:443 → {r2.get('inet_1111')}")
        controller.set_device_internet(me["mac"], me["name"], False)
        for _ in range(20):
            pump(0.5)
            if forwarding(alias) == "Disabled":
                break
        ok(forwarding(alias) == "Disabled", f"Haken weg: Weiterleitung wieder aus ({forwarding(alias)})")

    nat_ip = ps("(Get-NetIPAddress -InterfaceAlias 'vEthernet (nat)' -AddressFamily IPv4).IPAddress").strip()
    o = outsider(image, f"http://{nat_ip}:{CAST['port']}", hub.token, pump)
    ok(o and all(v == 403 for v in o.values()),
       f"Handy aus anderem Netz ({nat_ip}): Steuern, Spielen, Abstimmen, Status, Erlaubnis → überall 403 {o}")
    ok(not any(p.name == "Fremd" for p in hub.players.values()), "„Fremd“ ist NICHT im Spiel")

    # Firewall sperrt Port 80 (eigene Regel, wie auf manchen PCs): AluPC erkennt sie, zeigt sie, „Beheben“ hebt sie
    # nur bis zum Ende auf
    rule = "AluPC Testsperre Port 80"
    ps(f"New-NetFirewallRule -DisplayName '{rule}' -Direction Inbound -Action Block -Protocol TCP -LocalPort 80 | Out-Null")
    ok(hs_mod.audit_active(), "Wächter: Firewall-Überwachung an (sieht Sperren)")
    code = phone_probe(image, pump)
    ok(code != 302, f"Mit Sperr-Regel kommt das Handy nicht durch ({code})")
    drops = []
    for _ in range(30):
        pump(0.5)
        drops = hs_mod.drop_info(PHONE_IP)
        if drops:
            break
    print("::notice title=Firewall-Sperre erkannt::" + repr(drops[-3:]), flush=True)
    ok(any(d["name"] == rule and d["kind"] == "regel" for d in drops), f"Sperre erkannt: Regel „{rule}“ → {drops[-2:]}")
    for _ in range(30):  # ohne Knopf: der Wächter schaltet die Sperre selbst aus
        pump(0.5)
        if rule in hs_mod.fix_result():
            break
    ok(rule in hs_mod.fix_result(), f"Automatisch freigemacht: {hs_mod.fix_result()}")
    hint = hs_mod.check_hint(PHONE_IP)
    ok("automatisch aufgehoben" in hint, f"Hotspot-Fenster beim Handy: {hint}")
    ok(ps(f"(Get-NetFirewallRule -DisplayName '{rule}').Enabled") == "False", "Sperr-Regel vorübergehend aus")
    code = phone_probe(image, pump)
    ok(code == 302, f"Danach kommt das Handy durch → Android-Prüfung {code}")

    hs_mod.stop_portal()
    clean = False
    for _ in range(30):  # Wächter räumt in ≤ 2 s auf
        pump(0.5)
        if IP not in ps("netsh interface portproxy show v4tov4") and forwarding(alias) == "Enabled":
            clean = True
            break
    ok(clean, "Nach dem Ausschalten: portproxy weg, Weiterleitung wieder an")
    ok("AluPC-Portal" not in ps("netsh advfirewall firewall show rule name=AluPC-Portal"), "Firewall-Regeln weg")
    bak = os.path.join(os.environ.get("ProgramData", "C:/ProgramData"), "AluPC", "audit-vorher.csv")
    for _ in range(20):  # Wächter stellt nach dem Aufräumen zurück
        if ps(f"(Get-NetFirewallRule -DisplayName '{rule}').Enabled") == "True" and not os.path.exists(bak):
            break
        pump(0.5)
    ok(ps(f"(Get-NetFirewallRule -DisplayName '{rule}').Enabled") == "True", "Sperr-Regel des PCs wieder an")
    ok(not os.path.exists(os.path.join(os.environ.get("ProgramData", "C:/ProgramData"), "AluPC", "audit-vorher.csv")),
       "Firewall-Überwachung wieder wie vorher")
    ps(f"Remove-NetFirewallRule -DisplayName '{rule}'")
    free = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        free.bind((IP, 53))
        released = True
    except OSError:
        released = False
    free.close()
    ok(released, "Port 53 wieder frei")
    mine = "x"
    for _ in range(30):  # Wächter gibt Port 53 frei und startet den Windows-Dienst neu
        pump(0.5)
        mine = ps(f"Get-NetUDPEndpoint -LocalPort 53 -ErrorAction SilentlyContinue | "
                  f"Where-Object OwningProcess -eq {os.getpid()}")
        if not mine and ps("(Get-Service SharedAccess).Status") == "Running":
            break
    ok(not mine and ps("(Get-Service SharedAccess).Status") == "Running",
       "Port 53 von AluPC freigegeben, Windows-Hotspot-Dienst läuft")

    # ================= normaler Hotspot: offen (Internet geht, Prüf-Adressen → Anmeldeseite)
    hs.kind = "normal"
    good, msg = hs_mod.start_portal(ip=IP, closed=False)
    ok(good and forwarding(alias) == "Enabled", f"Offene Variante (nicht mehr Standard): Anmeldeseite an, Internet bleibt ({msg})")
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
