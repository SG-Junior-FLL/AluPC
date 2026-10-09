"""Linux, als root (CI: sudo): WLAN-Anmeldeseite ECHT durchspielen – mit einem „Handy“ im eigenen Netz.

Aufbau: Netz-Namensraum „alupc-handy“ mit Schnittstelle handy0 (10.42.0.50), verbunden über ein veth-Paar mit
alupc-wlan0 (10.42.0.1) – wie ein Handy im Hotspot des PCs. Auf dem PC laufen das echte AluPC (Controller,
Webserver, Minispiele, eigener DNS) und das echte Root-Skript (iptables). Das Handy macht dann, was Android und
iPhone beim Verbinden tun, und spielt mit:

  1. DNS: jede Adresse zeigt auf den PC (auch über fremde DNS-Server)
  2. Android-Prüfung  http://connectivitycheck.gstatic.com/generate_204  → 302 zur Anmeldeseite
  3. iPhone-Prüfung   http://captive.apple.com/hotspot-detect.html       → 302 zur Anmeldeseite
  4. beliebige Webseite per IP (http)                                     → 302 zur Anmeldeseite
  5. Anmeldeseite: Name eingeben → „Mitspielen“ → Spielseite → beigetreten (Spieler ist im Spiel)
  6. Mit Chromium (falls Playwright da ist): dasselbe wie ein Mensch – Seite öffnet, Name tippen, tippen auf
     „Mitspielen“, die Spielsteuerung erscheint
  7. Mitspielen von außerhalb des Spiele-WLANs (ohne Anmeldeseite) → abgelehnt
  8. Ausschalten → alle Regeln wieder weg

Nicht prüfbar ohne echte Hardware: die WLAN-Karte, ob das Handy-Betriebssystem das Anmeldefenster selbst öffnet.
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
# zweites Handy in einem ANDEREN Netz (wie Router-WLAN/LAN) – darf nichts
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
    sh(f"ip netns add {NS}")
    sh(f"ip link add {PC_IF} type veth peer name {PHONE_IF}")
    sh(f"ip link set {PHONE_IF} netns {NS}")
    sh(f"ip addr add {PC_IP}/24 dev {PC_IF} && ip link set {PC_IF} up")
    sh(f"ip netns exec {NS} ip addr add {PHONE_IP}/24 dev {PHONE_IF}")
    sh(f"ip netns exec {NS} ip link set {PHONE_IF} up && ip netns exec {NS} ip link set lo up")
    sh(f"ip netns exec {NS} ip route add default via {PC_IP}")
    sh(f"ip netns add {NS2}")
    sh(f"ip link add {OUT_IF} type veth peer name {OUT_PHONE_IF}")
    sh(f"ip link set {OUT_PHONE_IF} netns {NS2}")
    sh(f"ip addr add {OUT_PC_IP}/24 dev {OUT_IF} && ip link set {OUT_IF} up")
    sh(f"ip netns exec {NS2} ip addr add {OUT_PHONE_IP}/24 dev {OUT_PHONE_IF}")
    sh(f"ip netns exec {NS2} ip link set {OUT_PHONE_IF} up && ip netns exec {NS2} ip link set lo up")
    Path(f"/etc/netns/{NS}").mkdir(parents=True, exist_ok=True)
    Path(f"/etc/netns/{NS}/resolv.conf").write_text(f"nameserver {PC_IP}\n")  # wie per DHCP vom Hotspot


def teardown_net() -> None:
    sh(f"ip netns del {NS}", check=False)
    sh(f"ip link del {PC_IF}", check=False)
    sh(f"ip netns del {NS2}", check=False)
    sh(f"ip link del {OUT_IF}", check=False)
    shutil.rmtree(f"/etc/netns/{NS}", ignore_errors=True)


PHONE_ENV = "env -u HTTP_PROXY -u HTTPS_PROXY -u http_proxy -u https_proxy -u ALL_PROXY -u NO_PROXY -u no_proxy"


def phone(cmd: str) -> subprocess.CompletedProcess:
    return subprocess.run(f"ip netns exec {NS} {PHONE_ENV} {cmd}", shell=True, capture_output=True, text=True,
                          timeout=40)


PHONE_HTTP = r'''
import json, re, sys, urllib.request, urllib.parse, socket
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k): return None
opener = urllib.request.build_opener(NoRedirect)
def get(url):
    try:
        r = opener.open(url, timeout=10); return r.status, r.headers.get("Location", ""), r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Location", ""), e.read().decode("utf-8", "replace")
out = {}
out["dns_check"] = socket.gethostbyname("connectivitycheck.gstatic.com")
base = "http://%s:%s" % (sys.argv[1], sys.argv[2])
out["remote_page"] = get(base + "/")[0]
req = urllib.request.Request(base + "/api/freigabe", method="POST", data=b'{"name":"Handy"}',
                             headers={"Content-Type": "application/json"})
try:
    out["ask_access"] = urllib.request.urlopen(req, timeout=10).status
except urllib.error.HTTPError as e:
    out["ask_access"] = e.code
out["dns_any"] = socket.gethostbyname("www.beispiel-irgendwas.de")
out["android"] = get("http://connectivitycheck.gstatic.com/generate_204")[:2]
out["iphone"] = get("http://captive.apple.com/hotspot-detect.html")[:2]
out["raw_ip"] = get("http://93.184.216.34/")[:2]
st, _, pc_page = get("http://%s/" % sys.argv[1])  # Hotspot-Adresse im Browser (ohne Port) → Anmeldeseite
out["pc_root"] = [st, 'id="n"' in pc_page and "Mitspielen" in pc_page]
status, _, page = get(out["android"][1])
out["portal_status"] = status
out["portal_has_name"] = 'id="n"' in page and "Mitspielen" in page
m = re.search(r'location.href = "([^"]+)" \+ "&name="', page)
game = urllib.parse.urljoin(out["android"][1], m.group(1).replace("&amp;", "&")) if m else ""
out["game_url"] = game
token = urllib.parse.parse_qs(urllib.parse.urlparse(game).query).get("u", [""])[0]
st, _, gp = get(game + "&name=Lena")
out["game_page"] = st
req = urllib.request.Request(urllib.parse.urljoin(game, "/api/spiel"), method="POST",
      data=json.dumps({"u": token, "action": "join", "name": "Lena"}).encode(), headers={"Content-Type": "application/json"})
try:
    r = urllib.request.urlopen(req, timeout=10); out["join"] = r.status; out["pid"] = json.loads(r.read())["p"]
except urllib.error.HTTPError as e:
    out["join"] = e.code
m = re.search(r'"(/abstimmung\?u=[^"]+)"', page)
out["poll_button"] = bool(m) and "Abstimmen" in page
if m:
    out["poll_page"] = get(base + m.group(1))[0]
    ptoken = m.group(1).split("u=")[1]
    req = urllib.request.Request(base + "/api/umfrage", method="POST", headers={"Content-Type": "application/json"},
                                 data=json.dumps({"u": ptoken, "v": "lena-handy", "c": 0}).encode())
    try:
        out["vote"] = urllib.request.urlopen(req, timeout=10).status
    except urllib.error.HTTPError as e:
        out["vote"] = e.code
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
       "/abstimmung": code("/abstimmung"), "umfrage": code("/api/umfrage", b'{"u":"x","v":"y","c":0}')}
print(json.dumps(out))
'''

PHONE_BROWSER = r'''
const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch({ executablePath: process.env.CHROMIUM || undefined, args: ['--no-sandbox', '--no-proxy-server'] });
  const ctx = await b.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
  const p = await ctx.newPage();
  // wie das Anmeldefenster des Handys: die Prüf-Adresse aufrufen und der Weiterleitung folgen
  await p.goto('http://connectivitycheck.gstatic.com/generate_204');
  const portal = p.url();
  await p.fill('#n', 'Mia');
  await p.click('#play');
  await p.waitForSelector('#play:not(.hidden)', { timeout: 15000 });
  const joined = await p.evaluate(() => document.getElementById('who').textContent);
  await p.screenshot({ path: process.argv[2] });
  // „AluPC steuern“ → am PC erlauben → Foto senden (wie im Browser des Handys)
  const q = await ctx.newPage();
  await q.goto('http://captive.apple.com/hotspot-detect.html');
  await q.fill('#n', 'Mia');
  await q.click('#ctl');
  await q.waitForFunction(() => typeof code !== 'undefined' && !!code, null, { timeout: 30000 });
  await q.setInputFiles('#gal', process.argv[3]);
  await q.waitForTimeout(2500);
  console.log(JSON.stringify({ portal, joined, url: p.url(), photo: true }));
  await b.close();
})().catch(e => { console.log(JSON.stringify({ error: String(e) })); process.exit(1); });
'''


def main() -> int:
    if os.geteuid() != 0:
        print("Bitte als root ausführen (sudo).")
        return 2
    tmp = Path(tempfile.mkdtemp(prefix="alupc-portal-"))
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
    cfg["cast"] = {**cfg["cast"], "port": hs_mod.PORTAL_PORT}
    controller = Controller(cfg)
    controller.display.available = lambda: False
    # Port 8765 belegt (anderes Programm) → AluPC weicht auf den nächsten freien aus; Umleitung von Port 80 folgt
    import socket

    blocker = socket.socket()
    blocker.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    blocker.bind(("0.0.0.0", hs_mod.PORTAL_PORT))
    blocker.listen(1)
    controller.cast.start()
    from alupc.cast_server import active_port

    PORT = active_port()
    ok(PORT and PORT != hs_mod.PORTAL_PORT, f"Port {hs_mod.PORTAL_PORT} belegt → AluPC nimmt Port {PORT}")
    controller.start_games("tictactoe")
    hs = hs_mod.hotspot
    hs.running, hs.kind, hs.ssid, hs.password, hs.hidden, hs.ip = True, "spiele", "AluPC-Spiele", "k7m2p9qa", False, PC_IP
    flag = hs_mod.portal_flag()
    flag.write_text("an")
    if not hs_mod.start_dns(lambda: hs.ip, closed=True):
        ok(False, "AluPC-DNS startet")
        return 1
    script = hs_mod.portal_script(PC_IF, PORT, flag, os.getpid(), closed=True)
    watcher = subprocess.Popen(["sh", "-c", script])
    ok(bool(hs_mod._wait_ready(flag, watcher, 20)), "Root-Skript setzt die Regeln (iptables) und meldet „bereit“")
    hs.portal = True
    rules = sh("iptables-save", check=False)
    want_rules = ["-j alupc-nat", "-j alupc-fwd", "-A alupc-fwd -j REJECT", "--dport 53 -j REDIRECT --to-ports 8753",
                  f"--dport 80 -j REDIRECT --to-ports {PORT}"]
    ok(all(w in rules for w in want_rules), f"Regeln aktiv: DNS → AluPC, Port 80 → Anmeldeseite (Port {PORT}), kein Internet")
    ok(hs_mod.forwarding_state() == "Disabled", f"Internet-Sperre gemeldet ({hs_mod.forwarding_state()!r})")
    hs_mod.portal_status()  # Selbsttest läuft im Hintergrund an
    for _ in range(20):
        pump(0.3)
        line = hs_mod.portal_status()
        if "Anmeldeseite am PC: antwortet nicht" not in line:
            break
    ok(line.startswith(f"Port 80 → AluPC-Seite (Port {PORT})") and "Anmeldeseite am PC: " in line and "antwortet nicht" not in line,
       f"Hotspot-Fenster (gleich auf Windows und Linux): {line}")
    ok("alupc-portal" in sh("ip6tables-save 2>/dev/null", check=False) or not shutil.which("ip6tables"),
       "IPv6: auch gesperrt (kein Weg an der Anmeldeseite vorbei)")
    controller.cast.start()
    controller.start_poll("Pizza oder Pasta?", ["Pizza", "Pasta"])  # Abstimmen: auch nur übers WLAN

    # ---- Monitor 2: genau EIN QR-Code – der WLAN-Code dieses WLANs (echter Decoder liest ihn)
    try:
        import zxingcpp
        from PIL import Image

        from alupc.game_source import GameSource

        src = GameSource({})
        src.resize(1280, 720)
        shot = tmp / "lobby.png"
        pump(0.3)
        src.grab().save(str(shot))
        codes = [c.text for c in zxingcpp.read_barcodes(Image.open(shot))]
        want = f"WIFI:T:WPA;S:{hs.ssid};P:{hs.password};;"
        ok(codes == [want], f"Monitor 2 (Lobby): genau 1 QR-Code = WLAN „{hs.ssid}“ → {codes}")
        src.stop()
        from alupc.poll_source import PollSource

        psrc = PollSource({})
        psrc.resize(1280, 720)
        pump(0.3)
        psrc.grab().save(str(tmp / "umfrage.png"))
        codes = [c.text for c in zxingcpp.read_barcodes(Image.open(tmp / "umfrage.png"))]
        ok(codes == [want], f"Monitor 2 (Abstimmung): genau 1 QR-Code = WLAN → {codes}")
    except ImportError:
        print("  · QR-Prüfung übersprungen (zxing-cpp/Pillow fehlen)")

    # ---- Handy: Prüfungen wie Android/iPhone + Anmeldeseite + Beitreten (HTTP)
    phone_py = tmp / "phone_http.py"
    phone_py.write_text(PHONE_HTTP)
    proc = subprocess.Popen(f"ip netns exec {NS} {PHONE_ENV} {sys.executable} {phone_py} {PC_IP} {PORT}",
                            shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    while proc.poll() is None:
        pump(0.05)
    out, err = proc.communicate()
    try:
        r = json.loads(out.strip().splitlines()[-1])
    except (ValueError, IndexError):
        ok(False, f"Handy-Prüfung lief nicht: {err[-400:]}")
        r = {}
    target = f"http://{PC_IP}:{PORT}/anmelden"
    ok(r.get("dns_check") == PC_IP, f"DNS: connectivitycheck.gstatic.com → {r.get('dns_check')}")
    ok(r.get("dns_any") == PC_IP, f"DNS: jede andere Adresse → {r.get('dns_any')} (geschlossenes WLAN)")
    ok(r.get("android") == [302, target], f"Android-Prüfung → {r.get('android')}")
    ok(r.get("iphone") == [302, target], f"iPhone-Prüfung → {r.get('iphone')}")
    ok(r.get("raw_ip") == [302, target], f"Webseite per IP → {r.get('raw_ip')}")
    ok(r.get("pc_root") == [200, True], f"Hotspot-Adresse im Browser ({PC_IP}) → Anmeldeseite {r.get('pc_root')}")
    ok(r.get("portal_status") == 200 and r.get("portal_has_name"), "Anmeldeseite mit Namensfeld und „Mitspielen“")
    ok(r.get("game_page") == 200, "Spielseite aus der Anmeldeseite öffnet")
    ok(r.get("join") == 200, f"Beitreten aus dem Spiele-WLAN → {r.get('join')}")
    ok(r.get("poll_button") and r.get("poll_page") == 200 and r.get("vote") == 200,
       f"Anmeldeseite → „Abstimmen“ → abgestimmt ({r.get('poll_page')}, {r.get('vote')})")
    ok(controller.cast.poll is not None and sum(controller.cast.poll.counts()) == 1, "Stimme ist am PC angekommen")
    ok(r.get("remote_page") == 200 and r.get("ask_access") == 200,
       f"„AluPC steuern“ aus dem WLAN: Seite {r.get('remote_page')}, am PC um Erlaubnis fragen {r.get('ask_access')}")
    pump(0.3)
    hub = controller.cast.games
    ok(any(p.name == "Lena" for p in hub.players.values()), "„Lena“ ist im Spiel")
    dig = phone("dig +short +time=3 +tries=1 @8.8.8.8 example.org")
    ok(dig.stdout.strip() == PC_IP, f"Fremder DNS-Server (8.8.8.8) wird auch abgefangen → {dig.stdout.strip()!r}")

    # ---- Handy mit echtem Browser (wie das Anmeldefenster)
    node = shutil.which("node")
    if node and os.environ.get("NODE_PATH"):
        js = tmp / "phone.js"
        js.write_text(PHONE_BROWSER)
        shot = Path(os.environ.get("ALUPC_PORTAL_SHOT", tmp / "handy.png"))
        from PIL import Image

        photo = tmp / "urlaub.jpg"
        Image.new("RGB", (320, 200), (220, 30, 30)).save(photo)
        cmd = (f"ip netns exec {NS} {PHONE_ENV} NODE_PATH={os.environ['NODE_PATH']} "
               f"CHROMIUM={os.environ.get('CHROMIUM', '')} {node} {js} {shot} {photo}")
        asks = []
        controller.cast.request.connect(lambda req: asks.append(req) if req.get("kind") == "freigabe" else None)
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
        ok(b.get("portal") == target, f"Browser landet auf der Anmeldeseite → {b.get('portal') or b.get('error')}")
        ok(b.get("joined") == "Mia", f"Browser: Name „Mia“ → Mitspielen → Spielsteuerung ({b.get('joined')})")
        pump(0.3)
        ok(any(p.name == "Mia" for p in hub.players.values()), "„Mia“ ist im Spiel")
        content = controller.content or {}
        ok(b.get("photo") and content.get("type") == "image" and "urlaub" in str(content.get("path")),
           f"„AluPC steuern“ → am PC erlaubt → Foto gesendet → Monitor 2 zeigt es ({content.get('type')})")
    else:
        print("  · Browser-Teil übersprungen (kein node/Playwright)")

    # ---- Internet pro Gerät: im Hotspot-Fenster freischalten (nach MAC) → nur dieses Gerät kommt raus
    devices = controller.wlan_devices()
    me = next((d for d in devices if d["ip"] == PHONE_IP), None)
    ok(me is not None and me["name"] in ("Lena", "Mia") and not me["internet"],
       f"Hotspot-Fenster: Gerät mit Name und ohne Internet gelistet → {me}")
    if me:
        controller.set_device_internet(me["mac"], me["name"], True)
        end = time.time() + 8
        while time.time() < end and f"-s {PHONE_IP}/32 -j ACCEPT" not in sh("iptables-save", check=False):
            pump(0.2)
        rules = sh("iptables-save", check=False)
        ok(f"-A alupc-fwd -s {PHONE_IP}/32 -j ACCEPT" in rules and f"-A alupc-nat -s {PHONE_IP}/32 -j RETURN" in rules,
           "Freigeschaltet: Weiterleitung ins Internet für genau dieses Gerät")
        free = phone(f"{sys.executable} -c \"import socket; print(socket.gethostbyname('www.example.com'))\"")
        ok(free.stdout.strip() != PC_IP, f"…und echte Namensauflösung statt Anmeldeseite → {free.stdout.strip() or 'kein Eintrag'}")
        controller.set_device_internet(me["mac"], me["name"], False)
        end = time.time() + 8
        while time.time() < end and f"-s {PHONE_IP}/32" in sh("iptables-save", check=False):
            pump(0.2)
        again = phone(f"{sys.executable} -c \"import socket; print(socket.gethostbyname('www.example.com'))\"")
        ok(f"-s {PHONE_IP}/32" not in sh("iptables-save", check=False) and again.stdout.strip() == PC_IP,
           "Haken weg: wieder kein Internet, nur AluPC")

    # ---- Handy in einem ANDEREN Netz (Router-WLAN/LAN, Link abgetippt): alles abgelehnt
    outsider = tmp / "outsider.py"
    outsider.write_text(OUTSIDER)
    proc = subprocess.Popen(f"ip netns exec {NS2} {PHONE_ENV} {sys.executable} {outsider} {OUT_PC_IP} "
                            f"{PORT} {hub.token}", shell=True, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True)
    while proc.poll() is None:
        pump(0.05)
    out, err = proc.communicate()
    try:
        o = json.loads(out.strip().splitlines()[-1])
    except (ValueError, IndexError):
        o = {"error": err[-300:]}
    ok(o and all(v == 403 for v in o.values()),
       f"Handy aus anderem Netz: Steuern, Spielen, Abstimmen, Status, Erlaubnis → überall 403 {o}")
    ok(not any(p.name == "Fremd" for p in hub.players.values()), "„Fremd“ ist NICHT im Spiel")

    # ---- Ausschalten: Regeln weg
    hs_mod.stop_portal()
    try:
        watcher.wait(15)
    except subprocess.TimeoutExpired:
        watcher.kill()
    ok("alupc-portal" not in sh("iptables-save", check=False), "Nach dem Ausschalten sind alle Regeln weg")
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
