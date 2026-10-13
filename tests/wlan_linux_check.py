"""Linux, als root (CI: sudo): AluPC-WLAN ECHT durchspielen – mit einem „Handy“ im eigenen Netz.

Aufbau: Netz-Namensraum „alupc-handy“ mit Schnittstelle handy0 (10.42.0.50), verbunden über ein veth-Paar mit
alupc-wlan0 (10.42.0.1) – wie ein Handy im Hotspot des PCs. Ein zweites „Handy“ steckt in einem ANDEREN Netz
(wie Router-WLAN/LAN). Auf dem PC laufen das echte AluPC (Controller, Webserver, Minispiele, Abstimmung).

  1. Monitor 2: Lobby und Abstimmung zeigen je 2 QR-Codes (echter Decoder): WLAN + direkte Seite
  2. Das Handy öffnet genau diese Seiten-Links: Spiel beitreten, abstimmen, „AluPC steuern“ (am PC fragen)
  3. Mit Chromium (falls Playwright da ist): Spiel-Code öffnen, Name tippen, „Mitspielen“ → Steuerung erscheint;
     Steuerseite → am PC erlaubt → Foto senden
  4. Handy aus einem anderen Netz → überall 403
  5. Alte Adresse /anmelden → Weiterleitung zur Steuerseite (die Anmeldeseite gibt es nicht mehr)

Nicht prüfbar ohne echte Hardware: die WLAN-Karte selbst und die Kamera-App des Handys.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
NS, PC_IF, PHONE_IF, PC_IP, PHONE_IP = "alupc-handy", "alupc-wlan0", "handy0", "10.42.0.1", "10.42.0.50"
NS2, OUT_IF, OUT_PHONE_IF, OUT_PC_IP, OUT_PHONE_IP = "alupc-fremd", "alupc-lan0", "fremd0", "10.99.0.1", "10.99.0.50"
results: list[tuple[bool, str]] = []


def sh(cmd: str, check: bool = True) -> str:
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"{cmd}: {r.stderr.strip()}")
    return r.stdout.strip()


def ok(cond: bool, text: str) -> bool:
    results.append((bool(cond), text))
    print(("  ✓ " if cond else "  ✗ ") + text, flush=True)
    return bool(cond)


def setup_net() -> None:
    teardown_net()
    for ns, pc_if, ph_if, pc_ip, ph_ip in ((NS, PC_IF, PHONE_IF, PC_IP, PHONE_IP),
                                           (NS2, OUT_IF, OUT_PHONE_IF, OUT_PC_IP, OUT_PHONE_IP)):
        sh(f"ip netns add {ns}")
        sh(f"ip link add {pc_if} type veth peer name {ph_if}")
        sh(f"ip link set {ph_if} netns {ns}")
        sh(f"ip addr add {pc_ip}/24 dev {pc_if} && ip link set {pc_if} up")
        sh(f"ip netns exec {ns} ip addr add {ph_ip}/24 dev {ph_if}")
        sh(f"ip netns exec {ns} ip link set {ph_if} up && ip netns exec {ns} ip link set lo up")


def teardown_net() -> None:
    for ns, pc_if in ((NS, PC_IF), (NS2, OUT_IF)):
        sh(f"ip netns del {ns}", check=False)
        sh(f"ip link del {pc_if}", check=False)


PHONE_ENV = "env -u HTTP_PROXY -u HTTPS_PROXY -u http_proxy -u https_proxy -u ALL_PROXY -u NO_PROXY -u no_proxy"

PHONE_HTTP = r'''
import json, sys, urllib.request, urllib.parse
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k): return None
opener = urllib.request.build_opener(NoRedirect)
def get(url):
    try:
        r = opener.open(url, timeout=10); return r.status, r.headers.get("Location", ""), r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Location", ""), e.read().decode("utf-8", "replace")
def post(url, body):
    req = urllib.request.Request(url, method="POST", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        r = urllib.request.urlopen(req, timeout=10); return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, ""
game, poll, base = sys.argv[1], sys.argv[2], sys.argv[3]
out = {}
st, _, page = get(game)
out["game_page"] = [st, 'id="name"' in page]
token = urllib.parse.parse_qs(urllib.parse.urlparse(game).query)["u"][0]
st, body = post(urllib.parse.urljoin(game, "/api/spiel"), {"u": token, "action": "join", "name": "Lena"})
out["join"] = st
st, _, page = get(poll)
out["poll_page"] = st
ptoken = urllib.parse.parse_qs(urllib.parse.urlparse(poll).query)["u"][0]
out["vote"] = post(urllib.parse.urljoin(poll, "/api/umfrage"), {"u": ptoken, "v": "lena-handy", "c": 0})[0]
out["remote_page"] = get(base + "/")[0]
out["ask_access"] = post(base + "/api/freigabe", {"name": "Handy"})[0]
st, loc, _ = get(base + "/anmelden")
out["old_portal"] = [st, loc]
print(json.dumps(out))
'''

OUTSIDER = r'''
import json, sys, urllib.request
ip, port, token = sys.argv[1], sys.argv[2], sys.argv[3]
base = "http://%s:%s" % (ip, port)
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k): return None
opener = urllib.request.build_opener(NoRedirect)
def code(url, data=None):
    req = urllib.request.Request(base + url, data=data, method="POST" if data else "GET",
                                 headers={"Content-Type": "application/json"})
    try:
        return opener.open(req, timeout=10).status
    except urllib.error.HTTPError as e:
        return e.code
out = {"/": code("/"), "/spiel": code("/spiel?u=" + token), "/anmelden": code("/anmelden"),
       "join": code("/api/spiel", json.dumps({"u": token, "action": "join", "name": "Fremd"}).encode()),
       "/api/status": code("/api/status"), "freigabe": code("/api/freigabe", b'{"name":"x"}'),
       "/abstimmung": code("/abstimmung"), "umfrage": code("/api/umfrage", b'{"u":"x","v":"y","c":0}'),
       "/tafel": code("/tafel"), "/chat": code("/chat")}
print(json.dumps(out))
'''

PHONE_BROWSER = r'''
const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch({ executablePath: process.env.CHROMIUM || undefined, args: ['--no-sandbox', '--no-proxy-server'] });
  const ctx = await b.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
  const p = await ctx.newPage();
  await p.goto(process.argv[2]);  // = Inhalt des Spiel-QR-Codes
  await p.fill('#name', 'Mia');
  await p.click('#joinbtn');
  await p.waitForFunction(() => document.getElementById('who').textContent === 'Mia', null, { timeout: 15000 });
  const joined = await p.evaluate(() => document.getElementById('who').textContent);
  await p.screenshot({ path: process.argv[3] });
  // Steuerseite: ohne Code am PC um Erlaubnis fragen → Foto senden
  const q = await ctx.newPage();
  await q.goto(process.argv[4]);
  await q.fill('#devname', 'Mia');
  await q.click('text=Am PC freigeben lassen');
  await q.waitForFunction(() => typeof code !== 'undefined' && !!code, null, { timeout: 30000 });
  await q.setInputFiles('#gal', process.argv[5]);
  await q.waitForTimeout(2500);
  console.log(JSON.stringify({ joined, photo: true }));
  await b.close();
})().catch(e => { console.log(JSON.stringify({ error: String(e) })); process.exit(1); });
'''


def run_in(ns: str, cmd: str, pump) -> str:
    proc = subprocess.Popen(f"ip netns exec {ns} {PHONE_ENV} {cmd}", shell=True, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True)
    while proc.poll() is None:
        pump(0.05)
    out, err = proc.communicate()
    return (out.strip().splitlines() or [""])[-1] if out.strip() else "ERR " + err[-400:]


def main() -> int:
    if os.geteuid() != 0:
        print("Bitte als root ausführen (sudo).")
        return 2
    tmp = Path(tempfile.mkdtemp(prefix="alupc-wlan-"))
    os.environ.update(QT_QPA_PLATFORM="offscreen", XDG_CONFIG_HOME=str(tmp), XDG_RUNTIME_DIR=str(tmp),
                      ALUPC_NO_AUTO_WIFI="1")
    setup_net()
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
    controller = Controller(cfg)
    controller.display.available = lambda: False
    # Port 8765 belegt (anderes Programm) → AluPC weicht auf den nächsten freien aus; die QR-Codes folgen
    import socket

    blocker = socket.socket()
    blocker.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    blocker.bind(("0.0.0.0", 8765))
    blocker.listen(1)
    controller.cast.start()
    from alupc.cast_server import active_port, wlan_url

    port = active_port()
    ok(port and port != 8765, f"Port 8765 belegt → AluPC nimmt Port {port}")
    controller.start_games("tictactoe")
    hub = controller.cast.games
    hs = hs_mod.hotspot
    hs.running, hs.kind, hs.ssid, hs.password, hs.hidden, hs.ip = True, "normal", "AluPC", "k7m2p9qa", False, PC_IP
    controller.start_poll("Pizza oder Pasta?", ["Pizza", "Pasta"])
    game_url = f"http://{PC_IP}:{port}/spiel?u={hub.token}"
    poll_url = f"http://{PC_IP}:{port}/abstimmung?u={controller.cast.poll.token}"
    want_wifi = f"WIFI:T:WPA;S:{hs.ssid};P:{hs.password};;"

    # ---- Monitor 2: 2 QR-Codes je Seite (echter Decoder)
    try:
        import zxingcpp
        from PIL import Image

        from alupc.game_source import GameSource
        from alupc.poll_source import PollSource

        for name, cls, link in (("Lobby", GameSource, game_url), ("Abstimmung", PollSource, poll_url)):
            src = cls({})
            src.resize(1280, 720)
            pump(0.3)
            shot = tmp / f"{name}.png"
            src.grab().save(str(shot))
            codes = sorted(c.text for c in zxingcpp.read_barcodes(Image.open(shot)))
            ok(codes == sorted([want_wifi, link]) and not any("k=" in c for c in codes),
               f"Monitor 2 ({name}): WLAN-Code + direkte Seite (ohne Steuer-Code) → {codes}")
            src.stop()
    except ImportError:
        print("  · QR-Prüfung übersprungen (zxing-cpp/Pillow fehlen)")
    ok(wlan_url("/chat") == f"http://{PC_IP}:{port}/chat", f"Chat-Code: {wlan_url('/chat')}")

    # ---- Handy im AluPC-WLAN öffnet genau diese Links
    script = tmp / "phone_http.py"
    script.write_text(PHONE_HTTP)
    line = run_in(NS, f"{sys.executable} {script} '{game_url}' '{poll_url}' http://{PC_IP}:{port}", pump)
    try:
        r = json.loads(line)
    except ValueError:
        ok(False, f"Handy-Prüfung lief nicht: {line}")
        r = {}
    ok(r.get("game_page") == [200, True], f"Spiel-Code → Spielseite mit Namensfeld {r.get('game_page')}")
    ok(r.get("join") == 200, f"Beitreten aus dem AluPC-WLAN → {r.get('join')}")
    ok(r.get("poll_page") == 200 and r.get("vote") == 200, f"Abstimmungs-Code → abgestimmt ({r.get('vote')})")
    pump(0.3)
    ok(sum(controller.cast.poll.counts()) == 1, "Stimme ist am PC angekommen")
    ok(any(p.name == "Lena" for p in hub.players.values()), "„Lena“ ist im Spiel")
    ok(r.get("remote_page") == 200 and r.get("ask_access") == 200,
       f"Steuerseite aus dem WLAN: Seite {r.get('remote_page')}, am PC um Erlaubnis fragen {r.get('ask_access')}")
    ok(r.get("old_portal") == [302, "/"], f"Alte Adresse /anmelden → Steuerseite {r.get('old_portal')}")

    # ---- Handy mit echtem Browser
    node = shutil.which("node")
    if node and os.environ.get("NODE_PATH"):
        js = tmp / "phone.js"
        js.write_text(PHONE_BROWSER)
        shot = Path(os.environ.get("ALUPC_WLAN_SHOT", tmp / "handy.png"))
        from PIL import Image

        photo = tmp / "urlaub.jpg"
        Image.new("RGB", (320, 200), (220, 30, 30)).save(photo)
        asks = []
        controller.cast.request.connect(lambda req: asks.append(req) if req.get("kind") == "freigabe" else None)
        cmd = (f"ip netns exec {NS} {PHONE_ENV} NODE_PATH={os.environ['NODE_PATH']} "
               f"CHROMIUM={os.environ.get('CHROMIUM', '')} {node} {js} '{game_url}' {shot} "
               f"http://{PC_IP}:{port}/ {photo}")
        proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        while proc.poll() is None:
            pump(0.05)
            while asks:  # am PC „Erlauben“
                controller.cast.answer_access(asks.pop(0)["id"], True)
        out, err = proc.communicate()
        try:
            b = json.loads(out.strip().splitlines()[-1])
        except (ValueError, IndexError):
            b = {"error": err[-400:]}
        ok(b.get("joined") == "Mia", f"Browser: Spiel-Code → Name „Mia“ → Mitspielen ({b.get('joined') or b.get('error')})")
        pump(0.3)
        ok(any(p.name == "Mia" for p in hub.players.values()), "„Mia“ ist im Spiel")
        content = controller.content or {}
        ok(b.get("photo") and content.get("type") == "image" and "urlaub" in str(content.get("path")),
           f"Steuerseite → am PC erlaubt → Foto gesendet → Monitor 2 zeigt es ({content.get('type')})")
    else:
        print("  · Browser-Teil übersprungen (kein node/Playwright)")

    devices = controller.wlan_devices()
    me = next((d for d in devices if d["ip"] == PHONE_IP), None)
    ok(me is not None and me["name"] in ("Lena", "Mia", "Handy"), f"Hotspot-Fenster listet das Handy mit Namen → {me}")

    # ---- Handy in einem ANDEREN Netz: alles abgelehnt
    outsider = tmp / "outsider.py"
    outsider.write_text(OUTSIDER)
    line = run_in(NS2, f"{sys.executable} {outsider} {OUT_PC_IP} {port} {hub.token}", pump)
    try:
        o = json.loads(line)
    except ValueError:
        o = {"error": line}
    ok(o and all(v == 403 for v in o.values()), f"Handy aus anderem Netz: überall 403 {o}")
    ok(not any(p.name == "Fremd" for p in hub.players.values()), "„Fremd“ ist NICHT im Spiel")
    hs.running = False
    controller.shutdown()
    teardown_net()
    failed = [t for good, t in results if not good]
    print(f"\n{len(results) - len(failed)}/{len(results)} Prüfungen bestanden")
    return 1 if failed else 0


if __name__ == "__main__":
    try:
        code = main()
    finally:
        teardown_net()
    sys.exit(code)
