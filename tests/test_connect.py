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
    assert ["nmcli", "device", "wifi", "hotspot", "ifname", "wlp4s0", "con-name", "AluPC-Hotspot", "ssid", "Party",
            "password", "geheim123"] in calls

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
        assert controller.guest_wifi() == ("AluPC-Spiele", "")
    finally:
        hotspot.hotspot.running, hotspot.hotspot.ip, hotspot.hotspot.kind = False, "", ""
    assert controller.guest_wifi() is None
    controller.config["games"] = {**controller.config["games"], "wifi": {"ssid": "Zuhause", "password": "x"}}
    assert controller.guest_wifi() == ("Zuhause", "x")


def test_lobby_shows_two_readable_codes(env, tmp_path):  # noqa: F811
    zx = pytest.importorskip("zxingcpp")
    pil = pytest.importorskip("PIL.Image")
    controller, _window, _ = env
    controller.config["games"] = {**controller.config["games"], "wifi": {"ssid": "Zuhause", "password": "geheim99"}}
    controller.start_games("schaetzen")
    from alupc.game_source import GameSource

    src = GameSource({})
    src.resize(1280, 720)
    path = tmp_path / "lobby.png"
    src.grab().save(str(path))
    texts = sorted(r.text for r in zx.read_barcodes(pil.open(path)))
    assert texts == sorted([controller.cast.games_url(), wifi_payload("Zuhause", "geheim99")])
    src.stop()


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
    assert "802-11-wireless.mode" in add and "ap" in add and "shared" in add and "password" not in add
    assert ["nmcli", "connection", "up", "AluPC-Spiele"] in calls
    script = hotspot.portal_script("wlp4s0", 8765, hotspot.Path("/run/user/1000/alupc-portal-1000"), 4242)
    assert "-I PREROUTING -i wlp4s0 -p tcp --dport 80 -j REDIRECT --to-ports 8765" in script
    assert "kill -0 4242" in script and script.rstrip().endswith("--comment alupc-portal")
    assert "-D PREROUTING" in script  # Regel wird wieder entfernt


def test_portal_redirects_phone_checks_to_game(env, monkeypatch):  # noqa: F811
    """Anmeldeseite: Android/iPhone fragen fremde Adressen ab → Weiterleitung auf die Spielsteuerung."""
    import http.client

    controller, _window, _ = env
    controller.cast.start()
    controller.start_games("quiz")
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
    controller.start_games("quiz")
    try:
        hs.running, hs.kind = True, "normal"
        controller.game_action("aus")  # normaler Hotspot bleibt an
        import time

        time.sleep(0.2)
        assert stopped == []
        controller.start_games("quiz")
        hs.running, hs.kind = True, "spiele"
        controller.game_action("aus")
        end = time.time() + 3
        while not stopped and time.time() < end:
            time.sleep(0.05)
        assert stopped == [1]
    finally:
        hs.running, hs.kind = False, ""
