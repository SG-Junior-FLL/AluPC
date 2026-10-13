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
    # nur noch EIN AluPC-WLAN: auch die Minispiele bekommen dasselbe (kein eigenes Spiele-WLAN mehr)
    assert hotspot.settings(cfg, "spiele") == hs and "hotspot" not in cfg["games"]
    old = {"games": {}, "hotspot": {"ssid": "Alt", "password": ""}}  # früher offen (Linux) → bekommt Passwort
    assert len(hotspot.settings(old)["password"]) == 10 and old["hotspot"]["ssid"] == "Alt"
    calls = []

    def run(cmd, timeout=25):
        calls.append(cmd)
        if cmd[:4] == ["nmcli", "-t", "-f", "DEVICE,TYPE"]:
            return 0, "enp3s0:ethernet\nwlp4s0:wifi\nlo:loopback"
        if "hotspot" in cmd:
            return 0, "Device 'wlp4s0' successfully activated"
        if cmd[:3] == ["nmcli", "-g", "WIFI-PROPERTIES.AP"]:
            return 0, "yes"
        if cmd[:3] == ["nmcli", "-g", "GENERAL.CONNECTION"]:
            return 0, next((c[-1] for c in calls if c[:3] == ["nmcli", "connection", "up"]), "")
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
    assert not ok and "WiFiDeviceOff" in msg and "WLAN ist ausgeschaltet" in msg
    ok, msg = hotspot.windows_message("KANN:DisabledByGroupPolicy")
    assert not ok and "Gruppenrichtlinie" in msg
    ok, msg = hotspot.windows_message("KANN:Neu123")
    assert not ok and "Neu123" in msg
    assert "GetConnectionProfiles" in hotspot._PS_HEAD  # ohne Internet: andere Verbindung versuchen


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
    assert controller.guest_wifi() is None  # anderes WLAN zählt nicht: nur das AluPC-WLAN


def test_lobby_without_games_wifi_shows_no_link(env, tmp_path):  # noqa: F811
    """Mitspielen nur über das Spiele-WLAN: läuft es nicht, zeigt die Lobby KEINEN Code (nur den Grund) – auch
    nicht mit einem eingetragenen anderen WLAN oder der alten Einstellung „nur über WLAN: aus“."""
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
    assert texts == []  # kein anderer Weg als über das WLAN
    controller.config["games"] = {**controller.config["games"], "wifi_only": False}
    src.grab().save(str(path))
    assert sorted(r.text for r in zx.read_barcodes(pil.open(path))) == []
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
    # auch mit laufendem Webserver nur der WLAN-Code (jede Seite zeigt ihren eigenen zweiten Code)
    assert controller.cast.start()
    src._follow()
    for size in ((1280, 720), (1080, 1920)):
        src.resize(*size)
        src.grab().save(str(path))
        texts = sorted(r.text for r in zx.read_barcodes(pil.open(path)))
        assert texts == [wifi_payload("AluPC", "k7pm2qa9xr", hidden=True)], size
    controller.cast.stop()



@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux")
def test_hotspot_unsupported_without_nmcli(monkeypatch):
    monkeypatch.setattr(hotspot.shutil, "which", lambda _n: None)
    ok, why = hotspot.supported()
    assert not ok and "nmcli" in why


def test_open_games_network_linux_commands():
    calls = []

    def run(cmd, timeout=25):
        calls.append(cmd)
        if cmd[:4] == ["nmcli", "-t", "-f", "DEVICE,TYPE"]:
            return 0, "wlp4s0:wifi"
        if cmd[:3] == ["nmcli", "-g", "WIFI-PROPERTIES.AP"]:
            return 0, "yes"
        if cmd[:3] == ["nmcli", "-g", "GENERAL.CONNECTION"]:
            return 0, next((c[-1] for c in calls if c[:3] == ["nmcli", "connection", "up"]), "")
        if cmd[:2] == ["nmcli", "-g"]:
            return 0, "10.42.0.1/24"
        return 0, ""

    ok, _msg, ip = hotspot._linux_start("AluPC-Spiele", "", run, kind="spiele")
    assert ok and ip == "10.42.0.1"
    add = next(c for c in calls if c[:3] == ["nmcli", "connection", "add"])
    assert "802-11-wireless.mode" in add and "ap" in add and "shared" in add and "wifi-sec.psk" not in add
    assert add[add.index("802-11-wireless.hidden") + 1] == "yes"  # unsichtbar (Standard)
    assert ["nmcli", "connection", "up", "AluPC-Spiele"] in calls


def test_windows_hotspot_start_and_firewall(monkeypatch):
    """Hotspot.start unter Windows: Mobiler Hotspot, danach Firewall-Freigabe (fehlt sie: einmal Administrator)."""
    monkeypatch.setattr(hotspot, "supported", lambda: (True, ""))
    monkeypatch.setattr(hotspot.sys, "platform", "win32")
    monkeypatch.setattr(hotspot, "IS_WINDOWS", True)
    monkeypatch.setattr(hotspot, "note_windows_try", lambda out: None)
    calls, rule = [], {"there": False}
    monkeypatch.setattr(hotspot, "_ps", lambda script, extra=None, timeout=40: (
        calls.append(extra or ("runas" if "RunAs" in script else "state")),
        rule.update(there=rule["there"] or "RunAs" in script), (0, "STATUS:Success:"))[2])
    monkeypatch.setattr(hotspot, "_run", lambda cmd, timeout=25: (
        (0, "Regelname: AluPC WLAN") if rule["there"] else (1, "Keine Regeln")))
    hs = hotspot.Hotspot()
    ok, msg = hs.start("AluPC", "k7m2p9qa", hidden=False)
    assert ok and calls[0]["ALUPC_SSID"] == "AluPC" and calls[1:] == ["runas"] and hs.ip == "192.168.137.1"
    assert "Firewall" not in msg
    calls.clear()
    assert hotspot.Hotspot().start("AluPC", "k7m2p9qa", hidden=False)[0] and calls[1:] == []  # Regel schon da
    rule["there"] = False
    monkeypatch.setattr(hotspot, "_ps", lambda script, extra=None, timeout=40: (0, "STATUS:Success:"))  # „Nein“
    ok, msg = hotspot.Hotspot().start("AluPC", "k7m2p9qa", hidden=False)
    assert ok and "Firewall-Freigabe fehlt" in msg  # WLAN läuft trotzdem, ehrlicher Hinweis


def test_windows_arp_any_language(monkeypatch):
    """Geräteliste im Hotspot-Fenster: deutsches Windows schreibt „dynamisch“ statt „dynamic“."""
    text = """
Schnittstelle: 192.168.137.1 --- 0x12
  Internetadresse       Physische Adresse     Typ
  192.168.137.45        a2-11-22-33-44-55     dynamisch
  192.168.137.80        3c-22-fb-01-02-03     dynamic
  192.168.137.255       ff-ff-ff-ff-ff-ff     statisch
  224.0.0.22            01-00-5e-00-00-16     statisch

Schnittstelle: 192.168.0.20 --- 0x7
  192.168.0.1           11-22-33-44-55-66     dynamisch
"""
    monkeypatch.setattr(hotspot.sys, "platform", "win32")
    monkeypatch.setattr(hotspot, "IS_WINDOWS", True)
    monkeypatch.setattr(hotspot, "_run", lambda cmd, timeout=10: (0, text))
    assert hotspot.neighbors(ip="192.168.137.1") == {"192.168.137.45": "a2:11:22:33:44:55",
                                                       "192.168.137.80": "3c:22:fb:01:02:03"}


def test_wlan_stays_on_when_games_end(env, monkeypatch):  # noqa: F811
    """EIN AluPC-WLAN: Minispiele beenden schaltet es NICHT aus (sonst flögen die Handys raus)."""
    controller, _window, _ = env
    stopped = []
    monkeypatch.setattr(hotspot.hotspot, "stop", lambda: stopped.append(1) or (True, "aus"))
    hs = hotspot.hotspot
    try:
        for kind in ("normal", "spiele"):  # auch ein (alter) Spiele-Hotspot bleibt an
            controller.start_games("ssp")
            hs.running, hs.kind = True, kind
            controller.game_action("aus")
            import time

            time.sleep(0.3)
            assert stopped == []
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
    # dasselbe Gerät (gleiche Adresse) fragt nochmal: wieder am PC bestätigen (im WLAN wechseln Adressen)
    asked.clear()
    status, d1 = call("POST", "/api/freigabe", {"name": "Lenas Handy"})
    QApplication.processEvents()
    assert call("GET", f"/api/freigabe?id={d1['id']}")[1] == {"state": "wait"} and len(asked) == 1
    # „Geräte vergessen“: wieder fragen – und Ablehnen
    controller.cast.forget_devices()
    assert controller.cast.check("1.2.3.4", st["key"]) is False
    status, d2 = call("POST", "/api/freigabe", {"name": "Fremd"})
    assert call("GET", f"/api/freigabe?id={d2['id']}")[1] == {"state": "wait"}
    controller.cast.answer_access(d2["id"], False)
    assert call("GET", f"/api/freigabe?id={d2['id']}")[1] == {"state": "no"}


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
    assert started == [(True, "normal")]  # Minispiele starten das (eine) AluPC-WLAN, falls es noch aus ist
    controller.game_action("aus")
    controller.config["games"] = {**controller.config["games"], "auto_wifi": False, "wifi_only": False}
    started.clear()
    controller.start_games("schlangen")
    assert started == []
    hs = hotspot.hotspot
    for k, v in (("running", True), ("kind", "normal"), ("ssid", "AluPC"), ("password", ""), ("hidden", True)):
        monkeypatch.setattr(hs, k, v)
    from alupc.game_source import GameSource

    src = GameSource({})
    src.resize(1280, 720)
    path = tmp_path / "lobby-wlan.png"
    src.grab().save(str(path))
    texts = [r.text for r in zx.read_barcodes(pil.open(path))]
    assert texts == [wifi_payload("AluPC", "", hidden=True)]  # ohne Adresse im WLAN nur EIN Code: das WLAN
    monkeypatch.setattr(hs, "ip", "10.42.0.1")
    for size in ((1280, 720), (1920, 1080)):
        src.resize(*size)
        src.grab().save(str(path))
        texts = sorted(r.text for r in zx.read_barcodes(pil.open(path)))
        assert texts == sorted([wifi_payload("AluPC", "", hidden=True),
                                f"http://10.42.0.1:{controller.cast.port}/spiel?u={controller.cast.games.token}"]), size
    src.stop()
    controller.game_action("aus")


def test_only_alupc_wlan_reaches_alupc(monkeypatch):
    """Einziger Weg für Handys: das AluPC-WLAN. Aus anderen Netzen: 403. Der PC selbst darf."""
    from alupc.cast_server import PUBLIC_PATHS, cast_server, _make_handler

    H = _make_handler(cast_server())
    h = H.__new__(H)
    hs = hotspot.hotspot
    monkeypatch.setattr(hs, "running", True)
    monkeypatch.setattr(hs, "ip", "10.42.0.1")
    for ip, want in (("127.0.0.1", True), ("::1", True), ("10.42.0.57", True), ("192.168.178.20", False),
                     ("10.43.0.5", False), ("::ffff:10.42.0.9", True), ("fe80::1", False)):
        h.client_address = (ip, 5000)
        assert h._via_wlan() is want, ip
    monkeypatch.setattr(hs, "running", False)  # WLAN aus → auch die alte WLAN-Adresse nicht mehr
    h.client_address = ("10.42.0.57", 5000)
    assert not h._via_wlan()
    assert "/" not in PUBLIC_PATHS and "/spiel" not in PUBLIC_PATHS and "/api/spiel" not in PUBLIC_PATHS


def test_windows_hotspot_ip_default():
    assert hotspot.windows_hotspot_ip() == "192.168.137.1"  # ohne Windows-Registry: Standard


def test_hotspot_start_always_starts_webserver(monkeypatch, env):  # noqa: F811 – Fixture
    """Hotspot-Kachel: AluPCs Webserver läuft danach immer (sonst ginge Port 80 ins Leere: „DNS ✓, Anmeldeseite nicht“)."""
    controller = env[0]
    controller.cast.stop()
    seen = {}

    def fake_start(ssid, password, kind="normal", portal=False, hidden=True):
        from alupc import cast_server

        seen["port"] = cast_server.active_port()
        return True, "an"

    monkeypatch.setattr(hotspot.hotspot, "start", fake_start)
    ok, _msg = controller.set_hotspot(True, "normal")
    assert ok and controller.cast.running() and seen["port"] == controller.cast.port > 0
    controller.cast.stop()


def test_wlan_never_started_twice(env, monkeypatch):  # noqa: F811
    """Läuft das AluPC-WLAN schon, startet es nicht neu; ein zweiter Start mittendrin wird abgelehnt (sonst
    flögen alle Handys raus und die Anmeldeseite wäre kurz weg)."""
    import threading
    import time

    controller = env[0]
    calls = []
    gate = threading.Event()

    def slow_start(*a, **k):
        calls.append(1)
        gate.wait(3)
        return True, "an"

    monkeypatch.setattr(hotspot.hotspot, "start", slow_start)
    first = threading.Thread(target=lambda: controller.set_hotspot(True))
    first.start()
    time.sleep(0.2)
    ok, msg = controller.set_hotspot(True)  # z. B. Minispiele starten, während die Kachel das WLAN hochfährt
    assert not ok and "gerade schon" in msg and calls == [1]
    gate.set()
    first.join(5)
    monkeypatch.setattr(hotspot.hotspot, "running", True)
    ok, msg = controller.set_hotspot(True)
    assert ok and "läuft schon" in msg and calls == [1]  # kein Neustart
    controller.cast.stop()


def test_control_qr_only_on_pc(env, tmp_path, monkeypatch):  # noqa: F811
    """Steuer-Code (Adresse + Code) nur im Fenster am PC: Hotspot-Fenster und „Handy verbinden“ zeigen ihn als QR,
    Monitor 2 („qr“-Befehl) zeigt nur WLAN + Seite."""
    zx = pytest.importorskip("zxingcpp")
    pil = pytest.importorskip("PIL.Image")
    controller, window, _ = env
    hs = hotspot.hotspot
    for k, v in (("running", True), ("ssid", "AluPC"), ("password", "k7pm2qa9xr"),
                 ("hidden", False), ("ip", "10.42.0.1")):
        monkeypatch.setattr(hs, k, v)
    assert controller.cast.start()
    ctl = f"http://10.42.0.1:{controller.cast.port}/?k={controller.cast.code()}"
    from alupc.ui.connect_dialog import HotspotDialog, control_code

    assert control_code(controller.cast)[0] == ctl
    dlg = HotspotDialog(controller, parent=window)
    dlg._refresh()
    assert dlg.ctl_qr.isVisibleTo(dlg) and controller.cast.code() in dlg.qr_labels[1].text()
    path = tmp_path / "ctl.png"
    dlg.ctl_qr.pixmap().save(str(path))
    assert [r.text for r in zx.read_barcodes(pil.open(path))] == [ctl]
    dlg.close()
    controller.run_command("qr")  # Monitor 2: nur WLAN, NICHT der Steuer-Code
    from alupc.sources import WifiQrSource

    src = WifiQrSource(controller.content)
    src.resize(1280, 720)
    src.grab().save(str(path))
    texts = sorted(r.text for r in zx.read_barcodes(pil.open(path)))
    assert texts == [wifi_payload("AluPC", "k7pm2qa9xr")]
    assert ctl not in texts
    controller.cast.stop()


def test_cast_page_tablet_layout_and_ids():
    """Handy-Seite: jede per $("…") genutzte ID gibt es im HTML; iPad-Layout (Leiste links, 2 Spalten) vorhanden."""
    import re

    from alupc.cast_page import PAGE

    html, script = PAGE.split("<script>", 1)
    ids = set(re.findall(r'id="([\w-]+)"', html))
    used = set(re.findall(r'\$\("([\w-]+)"\)', script))
    created = {"nav-pill", "fullclose"}  # legt das Skript selbst an
    assert used - ids - created == set()
    assert "@media (min-width: 740px)" in PAGE and "@media (min-width: 1060px) and (min-aspect-ratio: 1/1)" in PAGE
    assert 'id="side"' in html and 'id="c-mon2"' in html and '$("c-mon2").classList.toggle("hide", !allow.steuern)' in script
    assert "pill.style.top" in script  # Leuchtpunkt gleitet auch in der senkrechten Leiste


def test_linux_hotspot_checks_ap_mode_and_result():
    """Linux-Hotspot robuster: WLAN-Karte ohne AP-Modus → klare Meldung; unsichtbar geht nicht → sichtbar;
    NetworkManager verbindet sich stattdessen mit einem WLAN → Fehler statt „läuft“."""
    def fake(ap="yes", hidden_fails=False, connected=None):
        calls = []

        def run(cmd, timeout=25):
            calls.append(cmd)
            if cmd[:4] == ["nmcli", "-t", "-f", "DEVICE,TYPE"]:
                return 0, "wlp4s0:wifi"
            if cmd[:3] == ["nmcli", "-g", "WIFI-PROPERTIES.AP"]:
                return 0, ap
            if cmd[:3] == ["nmcli", "-g", "GENERAL.CONNECTION"]:
                return 0, connected or "AluPC-Hotspot"
            if cmd[:2] == ["nmcli", "-g"]:
                return 0, "10.42.0.1/24"
            if cmd[:3] == ["nmcli", "connection", "up"] and hidden_fails and \
                    not any(c[:3] == ["nmcli", "connection", "modify"] for c in calls):
                return 4, "Error: Connection activation failed: 802.1X supplicant failed"
            return 0, ""
        return run, calls

    run, calls = fake(ap="no")
    ok, msg, _ip = hotspot._linux_start("AluPC", "geheim123", run, kind="normal")
    assert not ok and "AP-Modus" in msg and not any(c[:3] == ["nmcli", "connection", "add"] for c in calls)
    run, calls = fake(hidden_fails=True)
    ok, msg, ip = hotspot._linux_start("AluPC", "geheim123", run, kind="normal")
    assert ok and ip == "10.42.0.1" and hotspot.VISIBLE_NOTE in msg
    assert ["nmcli", "connection", "modify", "AluPC-Hotspot", "802-11-wireless.hidden", "no"] in calls
    run, calls = fake(connected="FRITZ!Box 7590")
    ok, msg, _ip = hotspot._linux_start("AluPC", "geheim123", run, kind="normal")
    assert not ok and "FRITZ!Box 7590" in msg and ["nmcli", "connection", "down", "AluPC-Hotspot"] in calls


def test_hotspot_needs_dnsmasq(monkeypatch):
    """Ohne dnsmasq kann NetworkManager keinen Hotspot verteilen – das sagt AluPC vorher (statt dass sich die Karte
    still wieder mit dem normalen WLAN verbindet). Das .deb hängt jetzt davon ab."""
    if not sys.platform.startswith("linux"):
        return
    monkeypatch.setattr(hotspot.shutil, "which", lambda n: "/usr/bin/nmcli" if n == "nmcli" else None)
    monkeypatch.setattr(hotspot, "Path", lambda p: type("P", (), {"exists": lambda self: False})())
    ok, why = hotspot.supported()
    assert not ok and "dnsmasq-base" in why
