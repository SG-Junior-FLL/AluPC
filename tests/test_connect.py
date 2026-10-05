"""QR-Codes (scharf, mit Rand), WLAN-QR, Hotspot-Befehle (nachgespielt) und die Lobby mit zwei Codes."""

import sys

import pytest

from test_gui import env  # noqa: F401 – gleiche Test-Umgebung wie die GUI-Tests (QApplication, Controller)

from alupc import hotspot
from alupc.screens import wifi_payload


@pytest.fixture()
def qapp():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_qr_has_quiet_zone_and_snaps_to_whole_pixels(qapp):
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QColor, QImage, QPainter

    from alupc.sources import draw_qr, qr_image

    img = qr_image("http://192.168.1.20:8765/?k=123456")
    n = img.width()
    for i in range(4):  # 4 Module Rand ringsum weiß
        assert img.pixelColor(i, n // 2) == QColor("#ffffff") and img.pixelColor(n // 2, i) == QColor("#ffffff")
    canvas = QImage(500, 500, QImage.Format_RGB32)
    canvas.fill(QColor("#000000"))
    p = QPainter(canvas)
    used = draw_qr(p, QRectF(10.3, 20.7, 333.3, 333.3), img)
    p.end()
    assert used.width() % n == 0 and used.width() <= 333.3 and used.x() == int(used.x())


def test_qr_scannable_with_real_decoder(qapp, tmp_path):
    zx = pytest.importorskip("zxingcpp")
    pil = pytest.importorskip("PIL.Image")
    from alupc.sources import qr_pixmap

    for text in ("http://10.42.0.1:8765/spiel?u=AbC123xy", wifi_payload("AluPC-Spiele", "pass;word:1")):
        pm = qr_pixmap(text, 120)
        path = tmp_path / "q.png"
        pm.save(str(path))
        assert [r.text for r in zx.read_barcodes(pil.open(path))] == [text]


def test_hidden_wifi_qr_readable(qapp, tmp_path):
    zx = pytest.importorskip("zxingcpp")
    pil = pytest.importorskip("PIL.Image")
    from alupc.sources import qr_pixmap

    payload = wifi_payload("AluPC", "k7pm2qa9xr", hidden=True)
    assert payload == "WIFI:T:WPA;S:AluPC;P:k7pm2qa9xr;H:true;;"
    pm = qr_pixmap(payload, 120)
    pm.save(str(tmp_path / "h.png"))
    assert [r.text for r in zx.read_barcodes(pil.open(tmp_path / "h.png"))] == [payload]


def test_wifi_payload_escapes():
    assert wifi_payload('a;b', 'p"w') == r'WIFI:T:WPA;S:a\;b;P:p\"w;;'
    assert wifi_payload("Offen", "") == "WIFI:T:nopass;S:Offen;P:;;"


def test_hotspot_settings_and_linux_commands(monkeypatch):
    cfg = {"games": {}}
    hs = hotspot.settings(cfg, "normal")
    assert hs["ssid"] == "AluPC" and len(hs["password"]) == 10 and cfg["hotspot"] == hs
    assert hotspot.settings(cfg, "normal") == hs  # bleibt gleich
    games = hotspot.settings(cfg, "spiele")
    assert games["ssid"] == "AluPC-Spiele" and cfg["games"]["hotspot"] == games
    if not hotspot.IS_WINDOWS:
        assert games["password"] == ""  # Spiele-WLAN unter Linux: offen
    calls = []

    def run(cmd, timeout=25):
        calls.append(cmd)
        if cmd[:4] == ["nmcli", "-t", "-f", "DEVICE,TYPE"]:
            return 0, "enp3s0:ethernet\nwlp4s0:wifi\nlo:loopback"
        if "hotspot" in cmd:
            return 0, "Device 'wlp4s0' successfully activated"
        if cmd[:2] == ["nmcli", "-g"]:
            return 0, "10.42.0.1/24"
        return 0, ""

    ok, msg, ip = hotspot._linux_start("Party", "geheim123", run, kind="normal")
    assert ok and ip == "10.42.0.1" and "Party" in msg
    add = next(c for c in calls if c[:3] == ["nmcli", "connection", "add"])
    assert "AluPC-Hotspot" in add and "Party" in add and add[add.index("wifi-sec.psk") + 1] == "geheim123"
    assert ["nmcli", "connection", "up", "AluPC-Hotspot"] in calls

    def fail(cmd, timeout=25):
        if cmd[:4] == ["nmcli", "-t", "-f", "DEVICE,TYPE"]:
            return 0, "wlp4s0:wifi"
        return 4, "Error: Connection activation failed: device does not support AP mode"

    ok, msg, ip = hotspot._linux_start("Party", "geheim123", fail, kind="normal")
    assert not ok and "AP mode" in msg and ip == ""


def test_windows_messages():
    assert hotspot.windows_message("STATUS:Success:") == (True, "Mobiler Hotspot läuft.")
    ok, msg = hotspot.windows_message("FEHLER:keine Internetverbindung")
    assert not ok and "Netz" in msg
    ok, msg = hotspot.windows_message("FEHLER:The specified procedure could not be found. (Exception from HRESULT: "
                                      "0x8007007F)")
    assert not ok and "procedure could not be found" in msg and "HRESULT" not in msg and "WLAN" in msg
    ok, msg = hotspot.windows_message("STATUS:WiFiDeviceOff:")
    assert not ok and "WiFiDeviceOff" in msg


def test_server_url_uses_hotspot_ip(env):  # noqa: F811
    controller, _window, _ = env
    controller.cast.start()
    try:
        hs = hotspot.hotspot
        hs.running, hs.ip, hs.kind, hs.ssid, hs.password = True, "10.42.0.1", "spiele", "AluPC-Spiele", ""
        assert controller.cast.games_url().startswith("http://10.42.0.1:")
        assert controller.guest_wifi() == ("AluPC-Spiele", "", False)
    finally:
        hotspot.hotspot.running, hotspot.hotspot.ip, hotspot.hotspot.kind = False, "", ""
    assert controller.guest_wifi() is None
    controller.config["games"] = {**controller.config["games"], "wifi": {"ssid": "Zuhause", "password": "x"}}
    assert controller.guest_wifi() == ("Zuhause", "x", False)


def test_lobby_shows_only_game_code(env, tmp_path):  # noqa: F811
    """WLAN-QR-Code ist raus aus den Minispielen – dafür „WLAN-QR-Code auf Monitor 2“ beim Hotspot."""
    zx = pytest.importorskip("zxingcpp")
    pil = pytest.importorskip("PIL.Image")
    controller, _window, _ = env
    controller.config["games"] = {**controller.config["games"], "wifi": {"ssid": "Zuhause", "password": "geheim99"}}
    controller.start_games("schlangen")
    from alupc.game_source import GameSource

    src = GameSource({})
    src.resize(1280, 720)
    path = tmp_path / "lobby.png"
    src.grab().save(str(path))
    texts = sorted(r.text for r in zx.read_barcodes(pil.open(path)))
    assert texts == [controller.cast.games_url()]
    src.stop()


def test_wifi_qr_on_monitor2(env, tmp_path, monkeypatch):  # noqa: F811
    zx = pytest.importorskip("zxingcpp")
    pil = pytest.importorskip("PIL.Image")
    controller, _window, _ = env
    hs = hotspot.hotspot
    monkeypatch.setattr(hs, "running", False)
    assert controller.show_wifi_qr() is False  # aus → Hinweis statt leerer Seite
    for k, v in (("running", True), ("kind", "normal"), ("ssid", "AluPC"), ("password", "k7pm2qa9xr"),
                 ("hidden", True), ("ip", "10.42.0.1")):
        monkeypatch.setattr(hs, k, v)
    assert controller.show_wifi_qr() and controller.content["type"] == "wlan"
    from alupc.sources import WifiQrSource

    src = WifiQrSource(controller.content)
    src.resize(1280, 720)
    path = tmp_path / "wlan.png"
    src.grab().save(str(path))
    texts = [r.text for r in zx.read_barcodes(pil.open(path))]
    assert texts == [wifi_payload("AluPC", "k7pm2qa9xr", hidden=True)]



@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux")
def test_hotspot_unsupported_without_nmcli(monkeypatch):
    monkeypatch.setattr(hotspot.shutil, "which", lambda _n: None)
    ok, why = hotspot.supported()
    assert not ok and "nmcli" in why


def test_open_games_network_and_portal_script():
    calls = []

    def run(cmd, timeout=25):
        calls.append(cmd)
        if cmd[:4] == ["nmcli", "-t", "-f", "DEVICE,TYPE"]:
            return 0, "wlp4s0:wifi"
        if cmd[:2] == ["nmcli", "-g"]:
            return 0, "10.42.0.1/24"
        return 0, ""

    ok, _msg, ip = hotspot._linux_start("AluPC-Spiele", "", run, kind="spiele")
    assert ok and ip == "10.42.0.1"
    add = next(c for c in calls if c[:3] == ["nmcli", "connection", "add"])
    assert "802-11-wireless.mode" in add and "ap" in add and "shared" in add and "wifi-sec.psk" not in add
    assert add[add.index("802-11-wireless.hidden") + 1] == "yes"  # unsichtbar (Standard)
    assert ["nmcli", "connection", "up", "AluPC-Spiele"] in calls
    script = hotspot.portal_script("wlp4s0", 8765, hotspot.Path("/run/user/1000/alupc-portal-1000"), 4242)
    assert "-I PREROUTING -i wlp4s0 -p tcp --dport 80 -m addrtype --dst-type LOCAL -j REDIRECT --to-ports 8765" \
        in script  # nur Anfragen an den PC – normales Surfen über den Hotspot bleibt unberührt
    assert "kill -0 4242" in script and "-D PREROUTING" in script  # Regel wird wieder entfernt
    assert "interface-name=connectivitycheck.gstatic.com,wlp4s0" in script  # klappt auch ohne Internet


@pytest.mark.skipif(sys.platform.startswith("win"), reason="sh-Skript")
def test_portal_watchdog_really_runs(tmp_path, monkeypatch):
    """Das Root-Skript echt ausführen (iptables als Attrappe): dnsmasq-Eintrag + Regel → „bereit“ → nach dem
    Ausschalten ist alles wieder weg."""
    import os
    import subprocess

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "ipt.log"
    fake = bin_dir / "iptables"
    fake.write_text(f"#!/bin/sh\necho \"$@\" >> {log}\n")
    fake.chmod(0o755)
    conf = tmp_path / "nm" / "alupc-portal.conf"
    monkeypatch.setattr(hotspot, "DNSMASQ_CONF", str(conf))
    flag = tmp_path / "alupc-portal-test"
    flag.write_text("an")
    proc = subprocess.Popen(["sh", "-c", hotspot.portal_script("wlan0", 8765, flag, os.getpid())],
                            env={**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}"})
    assert hotspot._wait_ready(flag, proc, 10)
    text = conf.read_text()
    assert "interface-name=captive.apple.com,wlan0" in text and "interface-name=www.msftconnecttest.com,wlan0" in text
    assert "-I PREROUTING" in log.read_text()
    flag.unlink()
    proc.wait(10)
    assert not conf.exists() and "-D PREROUTING" in log.read_text()


def test_portal_start_order_and_cancel(monkeypatch, tmp_path):
    """Linux: Anmeldeseite VOR dem Hotspot (dnsmasq liest beim Start). Passwort abgebrochen → Hotspot läuft trotzdem."""
    order = []
    monkeypatch.setattr(hotspot, "supported", lambda: (True, ""))
    monkeypatch.setattr(hotspot, "wifi_device", lambda run=None: "wlan0")
    monkeypatch.setattr(hotspot, "portal_flag", lambda: tmp_path / "flag")
    monkeypatch.setattr(hotspot.sys, "platform", "linux")
    monkeypatch.setattr(hotspot, "_linux_start",
                        lambda *a, **k: (order.append("hotspot"), (True, "Hotspot läuft.", "10.42.0.1"))[1])
    monkeypatch.setattr(hotspot, "start_portal", lambda dev: (order.append("portal"), (True, "Anmeldeseite an."))[1])
    hs = hotspot.Hotspot()
    ok, msg = hs.start("AluPC-Spiele", "", portal=True)
    assert ok and hs.portal and order == ["portal", "hotspot"] and "Anmeldeseite an" in msg
    monkeypatch.setattr(hotspot, "start_portal", lambda dev: (False, "Anmeldeseite aus (Passwort nicht eingegeben)."))
    ok, msg = hotspot.Hotspot().start("AluPC-Spiele", "", portal=True)
    assert ok and "Passwort nicht eingegeben" in msg


def test_windows_portal_script_and_launcher(monkeypatch, tmp_path):
    """Windows: Skript enthält hosts/portproxy/Firewall + Aufräumen; Start über „Als Administrator“."""
    script = hotspot.portal_script_windows("192.168.137.1", 8765, tmp_path / "f", 77)
    for part in ("drivers\\etc\\hosts", "portproxy add v4tov4 listenport=80 listenaddress=$ip connectport=8765",
                 "portproxy delete", "firewall add rule name=AluPC-Portal", "finally { Clean }", "Get-Process -Id 77",
                 "'captive.apple.com'"):
        assert part in script, part
    assert "msftconnecttest" not in script  # sonst hielte sich der PC selbst für „im Hotel-WLAN“
    monkeypatch.setattr(hotspot, "IS_WINDOWS", True)
    monkeypatch.setattr(hotspot, "portal_flag", lambda: tmp_path / "flag")
    seen = []
    ok, msg = hotspot.start_portal(spawn=lambda cmd: (seen.append(cmd), (0, ""))[1], wait=lambda f, p, t: True)
    assert ok and "-Verb RunAs" in seen[0] and "-EncodedCommand" in seen[0]
    ok, msg = hotspot.start_portal(spawn=lambda cmd: (1, "abgebrochen"), wait=lambda f, p, t: True)
    assert not ok and "QR-Code" in msg and not (tmp_path / "flag").exists()
    ok, msg = hotspot.start_portal(spawn=lambda cmd: (0, ""), wait=lambda f, p, t: "belegt:System")
    assert not ok and "Port 80" in msg and "System" in msg
    assert "Get-NetTCPConnection -LocalPort 80" in script and "belegt:" in script


def test_portal_redirects_phone_checks_to_game(env, monkeypatch):  # noqa: F811
    """Anmeldeseite: Android/iPhone fragen fremde Adressen ab → Weiterleitung auf die Spielsteuerung."""
    import http.client

    controller, _window, _ = env
    controller.cast.start()
    controller.start_games("ssp")
    hs = hotspot.hotspot
    try:
        hs.running, hs.kind, hs.portal, hs.ip = True, "spiele", True, "127.0.0.1"
        conn = http.client.HTTPConnection("127.0.0.1", controller.cast.port, timeout=5)
        conn.request("GET", "/generate_204", headers={"Host": "connectivitycheck.gstatic.com"})
        r = conn.getresponse()
        assert r.status == 302 and r.getheader("Location").endswith("/anmelden")
        r.read()
        conn.request("GET", "/anmelden", headers={"Host": "127.0.0.1"})
        r = conn.getresponse()
        page = r.read().decode()
        assert r.status == 200 and "/spiel?u=" in page and "Mitspielen" in page
        assert "AluPC steuern" in page and "?k=" not in page  # Steuern nur mit Code – der steht NICHT drin
        conn.request("GET", "/spiel", headers={"Host": "127.0.0.1"})  # eigene Adresse: normal
        r = conn.getresponse()
        assert r.status == 200
        r.read()
        conn.close()
    finally:
        hs.running, hs.kind, hs.portal, hs.ip = False, "", False, ""


def test_games_wifi_stops_with_games(env, monkeypatch):  # noqa: F811
    controller, _window, _ = env
    stopped = []
    monkeypatch.setattr(hotspot.hotspot, "stop", lambda: stopped.append(1) or (True, "aus"))
    hs = hotspot.hotspot
    controller.start_games("ssp")
    try:
        hs.running, hs.kind = True, "normal"
        controller.game_action("aus")  # normaler Hotspot bleibt an
        import time

        time.sleep(0.2)
        assert stopped == []
        controller.start_games("ssp")
        hs.running, hs.kind = True, "spiele"
        controller.game_action("aus")
        end = time.time() + 3
        while not stopped and time.time() < end:
            time.sleep(0.05)
        assert stopped == [1]
    finally:
        hs.running, hs.kind = False, ""


def test_phone_access_by_approval_on_pc(env, monkeypatch):  # noqa: F811
    """Ohne Code: Handy bittet um Freigabe → am PC „Erlauben“ → Gerät steuert ab jetzt ohne Code."""
    import http.client
    import json as _json

    from PySide6.QtWidgets import QApplication, QMessageBox

    controller, window, _ = env
    controller.cast.start()
    asked = []
    controller.access_requested.connect(lambda rid, name, ip: asked.append((rid, name)))
    def call(method, path, body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", controller.cast.port, timeout=5)
        conn.request(method, path, body=_json.dumps(body) if body is not None else None,
                     headers={"Content-Type": "application/json", **(headers or {})})
        r = conn.getresponse()
        out = r.status, _json.loads(r.read() or b"{}")
        conn.close()
        return out

    status, d = call("POST", "/api/freigabe", {"name": "Lenas Handy"})
    assert status == 200 and d["id"]
    for _ in range(50):
        QApplication.processEvents()
        if asked:
            break
    assert asked == [(d["id"], "Lenas Handy")]
    box = window.pending_access
    assert isinstance(box, QMessageBox) and "Lenas Handy" in box.text()
    assert call("GET", f"/api/freigabe?id={d['id']}")[1] == {"state": "wait"}
    assert call("POST", "/api/cmd", {"cmd": "schwarz"})[0] == 403  # ohne Freigabe: nichts
    allow = next(b for b in box.buttons() if b.text() == "Erlauben")
    allow.click()
    QApplication.processEvents()
    st = call("GET", f"/api/freigabe?id={d['id']}")[1]
    assert st["state"] == "ok" and st["key"].startswith("d-")
    assert call("GET", f"/api/freigabe?id={d['id']}")[1] == {"state": "ok"}  # Schlüssel nur einmal
    assert controller.cast.check("1.2.3.4", st["key"]) is True
    assert controller.config["cast"]["devices"][0]["name"] == "Lenas Handy"
    assert st["key"] not in _json.dumps(controller.config["cast"])  # nur die Prüfsumme gespeichert
    # Ablehnen
    status, d2 = call("POST", "/api/freigabe", {"name": "Fremd"})
    controller.cast.answer_access(d2["id"], False)
    assert call("GET", f"/api/freigabe?id={d2['id']}")[1] == {"state": "no"}
    controller.cast.forget_devices()
    assert controller.cast.check("1.2.3.4", st["key"]) is False


def test_normal_hotspot_also_gets_login_page(env, monkeypatch):  # noqa: F811
    """WLAN-QR scannen → Anmeldeseite (Mitspielen / AluPC steuern) – auch beim normalen Hotspot."""
    controller, _window, _ = env
    seen = {}
    monkeypatch.setattr(hotspot.hotspot, "start", lambda *a, **k: (seen.update(k), (True, "läuft"))[1])
    controller.set_hotspot(True, "normal")
    assert seen["portal"] is True and seen["kind"] == "normal"


def test_login_page_has_name_and_both_ways(env):  # noqa: F811
    """WLAN-Anmeldeseite wie im Hotel-WLAN: Name eingeben → Mitspielen (direkt in der Steuerung) oder AluPC steuern."""
    from alupc.cast_server import portal_page

    controller, _window, _ = env
    page = portal_page(controller.cast)
    assert 'id="n"' in page and "Gerade keine Minispiele" in page and "disabled" in page
    controller.start_games("tictactoe")
    page = portal_page(controller.cast)
    assert "Tic-Tac-Toe" in page and controller.cast.games_url() + '" + "&name=' in page and "?frei=" in page
    from alupc.game_page import GAME_PAGE
    from alupc.cast_page import PAGE

    assert 'get("name")' in GAME_PAGE and 'params.get("frei")' in PAGE  # Name kommt mit → gleich dabei
    controller.game_action("aus")


def test_games_start_games_wifi_and_lobby_shows_one_wlan_code(env, tmp_path, monkeypatch):  # noqa: F811
    zx = pytest.importorskip("zxingcpp")
    pil = pytest.importorskip("PIL.Image")
    controller, _window, _ = env
    monkeypatch.delenv("ALUPC_NO_AUTO_WIFI", raising=False)
    monkeypatch.setattr(hotspot, "supported", lambda: (True, ""))
    started = []
    monkeypatch.setattr(controller, "set_hotspot", lambda on, kind="normal": started.append((on, kind)))
    controller.start_games("schlangen")
    for _ in range(50):
        if started:
            break
        import time
        time.sleep(0.02)
    assert started == [(True, "spiele")]  # Minispiele = eigenes WLAN
    controller.game_action("aus")
    controller.config["games"] = {**controller.config["games"], "auto_wifi": False}
    started.clear()
    controller.start_games("schlangen")
    assert started == []
    hs = hotspot.hotspot
    for k, v in (("running", True), ("kind", "spiele"), ("ssid", "AluPC-Spiele"), ("password", ""), ("hidden", True)):
        monkeypatch.setattr(hs, k, v)
    from alupc.game_source import GameSource

    src = GameSource({})
    src.resize(1280, 720)
    path = tmp_path / "lobby-wlan.png"
    src.grab().save(str(path))
    texts = [r.text for r in zx.read_barcodes(pil.open(path))]
    assert texts == [wifi_payload("AluPC-Spiele", "", hidden=True)]  # nur EIN Code: das WLAN
    src.stop()
    controller.game_action("aus")
