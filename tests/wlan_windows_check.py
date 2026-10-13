"""Windows-CI (Administrator): AluPC-WLAN ECHT durchspielen – wie unter Linux, mit einem „Handy“.

Aufbau (tests/windows/hotspot_sim.ps1): Windows-Internetfreigabe (ICS – derselbe Dienst wie der Mobile Hotspot)
auf einem Loopback-Adapter, PC = 192.168.137.1. Das Handy ist ein Windows-Container (192.168.137.50) – wie ein
Handy im Hotspot. Auf dem PC läuft das echte AluPC (Controller, Webserver, Minispiele, Abstimmung).

  1. Firewall: AluPC legt die Freigabe „AluPC WLAN“ (Port 8765–8774) selbst an – OHNE eigene Testregel für Python
  2. Monitor 2: Lobby und Abstimmung zeigen je 2 QR-Codes (echter Decoder): WLAN + direkte Seite
  3. Das Handy öffnet genau diese Seiten-Links: Spiel beitreten, abstimmen, Steuerseite + am PC fragen
  4. Handy aus einem anderen Netz (Docker-NAT) → überall 403
  5. Alte Adresse /anmelden → Weiterleitung zur Steuerseite

Nicht prüfbar hier: echte WLAN-Karte, die UAC-Abfrage (Runner ist schon Administrator).
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
function Post($u, $body) {
  try { Invoke-RestMethod -Uri $u -Method Post -ContentType 'application/json' -UseBasicParsing -Body $body | Out-Null; return 200 }
  catch { if ($_.Exception.Response) { return [int]$_.Exception.Response.StatusCode } return 0 }
}
$o = [ordered]@{}
$g = Get-Url $GAME; $o.game_page = "$($g.s) $($g.b -match 'id="name"')"
$token = [regex]::Match($GAME, '[?&]u=([^&]+)').Groups[1].Value
$o.join = Post "$BASE/api/spiel" (@{ u = $token; action = 'join'; name = 'Lena' } | ConvertTo-Json)
$o.poll_page = (Get-Url $POLL).s
$pt = [regex]::Match($POLL, '[?&]u=([^&]+)').Groups[1].Value
$o.vote = Post "$BASE/api/umfrage" (@{ u = $pt; v = 'lena-handy'; c = 0 } | ConvertTo-Json)
$o.remote_page = (Get-Url "$BASE/").s
$o.ask_access = Post "$BASE/api/freigabe" '{"name":"Handy"}'
$a = Get-Url "$BASE/anmelden"; $o.old_portal = "$($a.s) $($a.l)"
'JSON:' + ($o | ConvertTo-Json -Compress)
"""

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
$o.join = Code "$BASE/api/spiel" ('{"u":"' + $TOKEN + '","action":"join","name":"Fremd"}')
$o.status = Code "$BASE/api/status" $null
$o.freigabe = Code "$BASE/api/freigabe" '{"name":"x"}'
$o.abstimmung = Code "$BASE/abstimmung" $null
$o.tafel = Code "$BASE/tafel" $null
'JSON:' + ($o | ConvertTo-Json -Compress)
"""


def container(args: list[str], script: str, pump) -> dict:
    enc = base64.b64encode(script.encode("utf-16-le")).decode()
    proc = subprocess.Popen(["docker", "run", "--rm", *args, "powershell", "-NoProfile", "-EncodedCommand", enc],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    end = time.time() + 400
    while proc.poll() is None and time.time() < end:
        pump(0.05)
    out = proc.communicate()[0] if proc.poll() is not None else (proc.kill() or "Zeitüberschreitung")
    for line in out.splitlines():
        if line.startswith("JSON:"):
            return json.loads(line[5:])
    print(out[-1500:])
    return {}


def main() -> int:
    image = sys.argv[1] if len(sys.argv) > 1 else "mcr.microsoft.com/windows/servercore:ltsc2022"
    tmp = Path(tempfile.mkdtemp(prefix="alupc-wlan-"))
    os.environ.update(QT_QPA_PLATFORM="offscreen", ALUPC_NO_AUTO_WIFI="1", APPDATA=str(tmp),
                      LOCALAPPDATA=str(tmp))
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

    # 1. Firewall-Freigabe: wie bei der ZIP-Version ohne Installer – AluPC legt sie selbst an (Runner = Admin)
    ps(f"netsh advfirewall firewall delete rule name=\"{hs_mod.FIREWALL_RULE}\"")
    ok(not hs_mod.firewall_rule_ok(), "Vorher: keine Freigabe „AluPC WLAN“")
    note = hs_mod.ensure_firewall_rule()
    ok(hs_mod.firewall_rule_ok() and not note, f"AluPC legt die Freigabe an (Port 8765–8774, alle Netze) {note}")
    ok(hs_mod.ensure_firewall_rule() == "", "Zweiter Aufruf: schon da, nichts zu tun")

    cfg = Config(tmp / "config.json")
    controller = Controller(cfg)
    controller.display.available = lambda: False
    blocker = socket.socket()  # Port 8765 belegt → AluPC weicht aus (bleibt in der Freigabe 8765–8774)
    blocker.bind(("0.0.0.0", 8765))
    blocker.listen(1)
    controller.cast.start()
    from alupc.cast_server import active_port

    port = active_port()
    ok(port and port != 8765, f"Port 8765 belegt → AluPC nimmt Port {port}")
    controller.start_games("tictactoe")
    hub = controller.cast.games
    hs = hs_mod.hotspot
    hs.running, hs.kind, hs.ssid, hs.password, hs.ip = True, "normal", "AluPC", "k7m2p9qa", IP
    controller.start_poll("Pizza oder Pasta?", ["Pizza", "Pasta"])
    base = f"http://{IP}:{port}"
    game_url = f"{base}/spiel?u={hub.token}"
    poll_url = f"{base}/abstimmung?u={controller.cast.poll.token}"

    # 2. Monitor 2: je 2 QR-Codes
    import zxingcpp
    from PIL import Image

    from alupc.game_source import GameSource
    from alupc.poll_source import PollSource

    want_wifi = f"WIFI:T:WPA;S:{hs.ssid};P:{hs.password};;"
    for name, cls, link in (("Lobby", GameSource, game_url), ("Abstimmung", PollSource, poll_url)):
        src = cls({})
        src.resize(1280, 720)
        pump(0.3)
        shot = tmp / f"{name}.png"
        src.grab().save(str(shot))
        codes = sorted(c.text for c in zxingcpp.read_barcodes(Image.open(shot)))
        ok(codes == sorted([want_wifi, link]), f"Monitor 2 ({name}): WLAN-Code + direkte Seite → {codes}")
        src.stop()

    # 3. Handy im Hotspot-Netz
    script = f"$GAME = '{game_url}'\n$POLL = '{poll_url}'\n$BASE = '{base}'\n" + PHONE
    r = container(["--network", "hotspot", "--ip", PHONE_IP, "--mac-address", "00:15:5d:00:00:50", "--dns", IP, image],
                  script, pump)
    ok(r.get("game_page") == "200 True", f"Spiel-Code → Spielseite mit Namensfeld ({r.get('game_page')})")
    ok(r.get("join") == 200, f"Beitreten aus dem AluPC-WLAN → {r.get('join')}")
    ok(r.get("poll_page") == 200 and r.get("vote") == 200, f"Abstimmungs-Code → abgestimmt ({r.get('vote')})")
    pump(0.3)
    ok(sum(controller.cast.poll.counts()) == 1, "Stimme ist am PC angekommen")
    ok(any(p.name == "Lena" for p in hub.players.values()), "„Lena“ ist im Spiel")
    ok(r.get("remote_page") == 200 and r.get("ask_access") == 200,
       f"Steuerseite aus dem WLAN: Seite {r.get('remote_page')}, am PC fragen {r.get('ask_access')}")
    ok(r.get("old_portal") == "302 /", f"Alte Adresse /anmelden → Steuerseite ({r.get('old_portal')})")

    # 4. Handy aus einem anderen Netz
    nat_ip = ps("(Get-NetIPAddress -InterfaceAlias 'vEthernet (nat)' -AddressFamily IPv4).IPAddress").strip()
    o = container([image], f"$BASE = 'http://{nat_ip}:{port}'\n$TOKEN = '{hub.token}'\n" + OUTSIDER, pump)
    ok(o and all(v == 403 for v in o.values()), f"Handy aus anderem Netz ({nat_ip}): überall 403 {o}")
    ok(not any(p.name == "Fremd" for p in hub.players.values()), "„Fremd“ ist NICHT im Spiel")

    hs.running = False
    controller.shutdown()
    ps(f"netsh advfirewall firewall delete rule name=\"{hs_mod.FIREWALL_RULE}\"")
    failed = [t for good, t in results if not good]
    print(f"\n{len(results) - len(failed)}/{len(results)} Prüfungen bestanden")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
