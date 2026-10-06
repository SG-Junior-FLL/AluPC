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
    assert len(games["password"]) == 10  # Linux und Windows gleich: immer mit Passwort
    old = {"games": {"hotspot": {"ssid": "Alt", "password": ""}}}  # früher offen (Linux) → bekommt Passwort
    assert len(hotspot.settings(old, "spiele")["password"]) == 10
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
    assert controller.guest_wifi() is None  # anderes WLAN zählt nicht: nur das AluPC-WLAN hat die Anmeldeseite


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
    # Geschlossen (wie im Hotel): jede Webseite → Anmeldeseite, jede DNS-Frage → AluPC, kein Internet (auch IPv6)
    # – außer den Geräten in <Flagge>.internet (eigene Ketten, alle 2 s neu gebaut)
    assert "-t nat -I PREROUTING -i wlp4s0 -m comment --comment alupc-portal -j alupc-nat" in script
    assert "iptables -t nat -A alupc-nat -p tcp --dport 80 -j REDIRECT --to-ports 8765" in script
    assert "iptables -t nat -A alupc-nat -p udp --dport 53 -j REDIRECT --to-ports 8753" in script
    assert "-I FORWARD -i wlp4s0 -m comment --comment alupc-portal -j alupc-fwd" in script
    assert "iptables -A alupc-fwd -j REJECT" in script and "ip6tables -I FORWARD -i wlp4s0" in script
    assert 'iptables -A alupc-fwd -s "$ip" -j ACCEPT' in script and '-s "$ip" -j RETURN' in script
    assert 'case "$ip" in ""|*[!0-9.]*) continue' in script  # nur IP-Adressen aus der Datei
    assert "kill -0 4242" in script and "-D PREROUTING" in script  # Regeln werden wieder entfernt
    normal = hotspot.portal_script("wlp4s0", 8765, hotspot.Path("/tmp/f"), 1, closed=False)
    assert "--dst-type LOCAL" in normal and "alupc-fwd -j REJECT" not in normal  # offen: Surfen bleibt


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
    flag = tmp_path / "alupc-portal-test"
    flag.write_text("an")
    proc = subprocess.Popen(["sh", "-c", hotspot.portal_script("wlan0", 8765, flag, os.getpid())],
                            env={**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}"})
    assert hotspot._wait_ready(flag, proc, 10)
    lines = log.read_text().splitlines()
    assert len([ln for ln in lines if " -I " in f" {ln} "]) == 5  # Sprünge in die eigenen Ketten + Firewall
    assert len([ln for ln in lines if " -A " in f" {ln} "]) == 4  # DNS ×2, Port 80, sonst REJECT
    # Gerät 10.42.0.7 bekommt Internet → Regeln werden neu gebaut (RETURN + ACCEPT für genau diese Adresse)
    hotspot.Path(f"{flag}.internet").write_text("10.42.0.7\n$(touch /tmp/boese)\n")
    import time

    end = time.time() + 8
    while time.time() < end and "10.42.0.7" not in log.read_text():
        time.sleep(0.2)
    text = log.read_text()
    assert "-t nat -A alupc-nat -s 10.42.0.7 -j RETURN" in text and "-A alupc-fwd -s 10.42.0.7 -j ACCEPT" in text
    assert "boese" not in text and not hotspot.Path("/tmp/boese").exists()  # nur IP-Adressen
    flag.unlink()
    proc.wait(10)
    removed = [ln for ln in log.read_text().splitlines() if " -D " in f" {ln} "]
    assert len(removed) >= 10  # vorher aufgeräumt (falls Reste) + nach dem Ausschalten
    assert "-X alupc-fwd" in log.read_text()


def test_portal_dns_answers_everything_with_the_pc():
    """Eigener DNS der Anmeldeseite: geschlossen → jede Adresse = PC; offen → nur die Prüf-Adressen."""
    import socket
    import struct

    from alupc.portal_dns import PortalDNS, answer

    def query(name, qtype=1):
        q = struct.pack(">HHHHHH", 0x1234, 0x0100, 1, 0, 0, 0)
        q += b"".join(bytes([len(p)]) + p.encode() for p in name.split(".")) + b"\0" + struct.pack(">HH", qtype, 1)
        return q

    dns = PortalDNS(lambda: "10.42.0.1", closed=True, hosts=["captive.apple.com"], port=0)
    out = answer(query("irgendwas.example.org"), dns.ip_for)
    assert out[:2] == b"\x12\x34" and out[6:8] == b"\x00\x01" and out.endswith(socket.inet_aton("10.42.0.1"))
    assert answer(query("x.org", 28), dns.ip_for)[6:8] == b"\x00\x00"  # IPv6: keine Antwort, aber kein Fehler
    open_dns = PortalDNS(lambda: "10.42.0.1", closed=False, hosts=["captive.apple.com"], port=0)
    assert answer(query("captive.apple.com"), open_dns.ip_for).endswith(socket.inet_aton("10.42.0.1"))
    # echter Server über UDP
    srv = PortalDNS(lambda: "10.42.0.7", closed=True, port=18753)
    assert srv.start()
    try:
        c = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        c.settimeout(3)
        c.sendto(query("connectivitycheck.gstatic.com"), ("127.0.0.1", 18753))
        assert c.recv(512).endswith(socket.inet_aton("10.42.0.7"))
    finally:
        srv.stop()


def test_portal_start_order_and_cancel(monkeypatch, tmp_path):
    """Linux: Anmeldeseite VOR dem Hotspot (dnsmasq liest beim Start). Passwort abgebrochen → Hotspot läuft trotzdem."""
    order = []
    monkeypatch.setattr(hotspot, "supported", lambda: (True, ""))
    monkeypatch.setattr(hotspot, "wifi_device", lambda run=None: "wlan0")
    monkeypatch.setattr(hotspot, "portal_flag", lambda: tmp_path / "flag")
    monkeypatch.setattr(hotspot.sys, "platform", "linux")
    monkeypatch.setattr(hotspot, "_linux_start",
                        lambda *a, **k: (order.append("hotspot"), (True, "Hotspot läuft.", "10.42.0.1"))[1])
    monkeypatch.setattr(hotspot, "start_portal",
                        lambda dev, closed=True: (order.append("portal"), (True, "Anmeldeseite an."))[1])
    hs = hotspot.Hotspot()
    ok, msg = hs.start("AluPC-Spiele", "", portal=True)
    assert ok and hs.portal and order == ["portal", "hotspot"] and "Anmeldeseite an" in msg
    monkeypatch.setattr(hotspot, "start_portal",
                        lambda dev, closed=True: (False, "Anmeldeseite aus (Passwort nicht eingegeben)."))
    ok, msg = hotspot.Hotspot().start("AluPC-Spiele", "", portal=True)
    assert ok and "Passwort nicht eingegeben" in msg


def test_windows_portal_script_and_launcher(monkeypatch, tmp_path):
    """Windows wie Linux: Port 53 vom Windows-Hotspot-DNS übernehmen (Dienst kurz anhalten), Firewall inkl.
    Sperr-Regeln für AluPC weg, portproxy 80, geschlossen = kein Weiterleiten. Hotspot erst NACH der Übernahme."""
    script = hotspot.portal_script_windows("192.168.137.1", 8765, tmp_path / "f", 77, program=r"C:\Pro'gramme\AluPC.exe")
    for part in ("portproxy add v4tov4 listenport=80 listenaddress=$ip connectport=8765", "portproxy delete",
                 "firewall add rule name=AluPC-Portal dir=in action=allow protocol=UDP localport=53",
                 'localport="80,53,8765"', "-Forwarding Disabled", "-Forwarding Enabled", "$closed = $true",
                 "Get-Process -Id 77", "Stop-Service SharedAccess", "Start-Service SharedAccess",
                 "Restart-Service SharedAccess", '"$flag.frei"', '"$flag.dns"', '"$flag.bereit"',
                 "$_.Action -eq 'Block'", "Remove-NetFirewallRule", "$prog = 'C:\\Pro''gramme\\AluPC.exe'",
                 'program="$prog"'):
        assert part in script, part
    assert "captive.apple.com" not in script and "drivers\\etc\\hosts" not in script  # keine hosts-Notlösung mehr
    assert script.index("Stop-Service") < script.index('"$flag.frei"') < script.index("Start-Service SharedAccess")
    assert "$closed = $false" in hotspot.portal_script_windows("192.168.137.1", 8765, tmp_path / "f", 77, closed=False)
    monkeypatch.setattr(hotspot, "IS_WINDOWS", True)
    monkeypatch.setattr(hotspot, "portal_flag", lambda: tmp_path / "flag")
    started, order = [], []
    monkeypatch.setattr(hotspot, "start_dns", lambda *a, **k: (started.append(k), order.append("dns"), True)[2])
    monkeypatch.setattr(hotspot, "dns_selftest", lambda ip, port=53: True)

    def files(path, timeout):  # das Administrator-Skript: gibt Port 53 frei, wartet auf AluPC, startet den Dienst
        order.append(path.name.split(".")[-1])
        if path.name.endswith(".bereit"):
            order.append((tmp_path / "flag.dns").read_text())  # AluPC hat Port 53 → meldet „ok“
        return True

    seen = []
    ok, msg = hotspot.start_portal(spawn=lambda cmd: (seen.append(cmd), (0, ""))[1], wait=lambda f, p, t: True,
                                   then=lambda: (order.append("hotspot"), True)[1], wait_file=files)
    assert ok and "-Verb RunAs" in seen[0] and "-EncodedCommand" in seen[0], msg
    assert order == ["frei", "dns", "bereit", "ok", "hotspot"], order
    assert started[-1]["host"] == "0.0.0.0" and started[-1]["port"] == 53 and started[-1]["restrict"]
    assert started[-1]["exclusive"] is False  # exklusiv auf 0.0.0.0 scheitert neben Docker/WSL (172.x:53)
    assert "Owner53" in script and "Get-NetUDPEndpoint -LocalPort 53" in script
    import base64
    sent = base64.b64decode(seen[0].split("'-EncodedCommand','")[1].split("'")[0]).decode("utf-16-le")
    assert "$closed = $true" in sent and "Stop-Service SharedAccess" in sent
    ok, msg = hotspot.start_portal(spawn=lambda cmd: (1, "abgebrochen"), wait=lambda f, p, t: True, wait_file=files)
    assert not ok and "nicht bestätigt" in msg and not (tmp_path / "flag").exists()
    ok, msg = hotspot.start_portal(spawn=lambda cmd: (0, ""), wait=lambda f, p, t: "belegt:System", wait_file=files)
    assert not ok and "Port 80" in msg and "System" in msg and not (tmp_path / "flag").exists()
    ok, msg = hotspot.start_portal(spawn=lambda cmd: (0, ""), wait=lambda f, p, t: True,
                                   wait_file=lambda p, t: False)
    assert not ok and "nicht geantwortet" in msg
    # 0.0.0.0:53 hält ein anderer Dienst → Hotspot-Adresse direkt
    hosts = []
    monkeypatch.setattr(hotspot, "start_dns", lambda *a, **k: (hosts.append(k["host"]), k["host"] != "0.0.0.0")[1])
    ok, msg = hotspot.start_portal(spawn=lambda cmd: (0, ""), wait=lambda f, p, t: True, wait_file=files)
    assert ok and hosts == ["0.0.0.0", "192.168.137.1"], (hosts, msg)
    # nach dem Hotspot-Start kommt nichts an (Adresse neu angelegt) → neu binden, jetzt Hotspot-Adresse zuerst
    hosts.clear()
    tests = iter([False, True])
    monkeypatch.setattr(hotspot, "dns_selftest", lambda ip, port=53: next(tests))
    monkeypatch.setattr(hotspot, "start_dns", lambda *a, **k: (hosts.append((k["host"], k["exclusive"])), True)[1])
    ok, msg = hotspot.start_portal(spawn=lambda cmd: (0, ""), wait=lambda f, p, t: True, wait_file=files)
    assert ok and hosts == [("0.0.0.0", False), ("192.168.137.1", True)], (hosts, msg)
    assert "nach Hotspot-Start neu: 192.168.137.1 exklusiv" in hotspot.DNS_INFO
    monkeypatch.setattr(hotspot, "dns_selftest", lambda ip, port=53: True)

    def frei(path, timeout):
        if path.name.endswith(".frei"):
            path.write_text("belegt:0.0.0.0 svchost hns")
        return True

    monkeypatch.setattr(hotspot, "start_dns", lambda *a, **k: False)
    ok, msg = hotspot.start_portal(spawn=lambda cmd: (0, ""), wait=lambda f, p, t: True, wait_file=frei)
    assert not ok and "Port 53 ist belegt (0.0.0.0 svchost hns)" in msg and (tmp_path / "flag.dns").read_text() == "fehler"
    # Selbsttest scheitert → ehrlich „ging nicht“ (kein stilles „an“ mit Internet für alle)
    monkeypatch.setattr(hotspot, "start_dns", lambda *a, **k: True)
    monkeypatch.setattr(hotspot, "dns_selftest", lambda ip, port=53: False)
    ok, msg = hotspot.start_portal(spawn=lambda cmd: (0, ""), wait=lambda f, p, t: True, wait_file=files)
    assert not ok and "kommen nicht bei AluPC an" in msg


def test_windows_hotspot_starts_after_port53(monkeypatch, tmp_path):
    """Hotspot.start unter Windows: Hotspot erst, wenn Port 53 übernommen ist; ohne „Ja“ trotzdem Hotspot."""
    monkeypatch.setattr(hotspot, "supported", lambda: (True, ""))
    monkeypatch.setattr(hotspot.sys, "platform", "win32")
    monkeypatch.setattr(hotspot, "IS_WINDOWS", True)
    calls = []
    monkeypatch.setattr(hotspot, "_ps", lambda script, env=None, timeout=40: (calls.append(env), (0, "STATUS:Success:"))[1])

    def portal(ip, closed, then):
        calls.append("portal")
        assert then()
        return True, "Anmeldeseite an."

    monkeypatch.setattr(hotspot, "start_portal", portal)
    monkeypatch.setattr(hotspot, "stop_portal", lambda: None)
    hs = hotspot.Hotspot()
    ok, msg = hs.start("AluPC-Spiele", "k7m2p9qa", portal=True, hidden=False)
    assert ok and hs.portal and calls[0] == "portal" and calls[1]["ALUPC_SSID"] == "AluPC-Spiele" and len(calls) == 2
    assert "Anmeldeseite an" in msg and hs.ip == "192.168.137.1"
    calls.clear()
    monkeypatch.setattr(hotspot, "start_portal", lambda ip, closed, then: (False, "Anmeldeseite aus („Ja“ …)."))
    ok, msg = hotspot.Hotspot().start("AluPC-Spiele", "k7m2p9qa", portal=True, hidden=False)
    assert ok and len(calls) == 1 and "Anmeldeseite aus" in msg


def test_windows_arp_any_language(monkeypatch):
    """Geräteliste (Internet pro Gerät): deutsches Windows schreibt „dynamisch“ statt „dynamic“."""
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


def test_dns_selftest_sees_own_server():
    """Selbsttest: Frage an die Adresse kommt bei AluPCs DNS an (wie unter Windows auf 192.168.137.1:53)."""
    assert hotspot.start_dns(lambda: "127.0.0.1", True, host="127.0.0.1", port=18754)
    try:
        assert hotspot.dns_selftest("127.0.0.1", 18754)
    finally:
        hotspot.stop_dns()
    assert not hotspot.dns_selftest("127.0.0.1", 18754, timeout=0.3)


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
    # dasselbe Gerät (gleiche Adresse) später im normalen Browser: gleich erlaubt, ohne neue Frage am PC
    asked.clear()
    status, d1 = call("POST", "/api/freigabe", {"name": "Lenas Handy"})
    assert call("GET", f"/api/freigabe?id={d1['id']}")[1]["state"] == "ok" and asked == []
    # „Geräte vergessen“: wieder fragen – und Ablehnen
    controller.cast.forget_devices()
    assert controller.cast.check("1.2.3.4", st["key"]) is False
    status, d2 = call("POST", "/api/freigabe", {"name": "Fremd"})
    assert call("GET", f"/api/freigabe?id={d2['id']}")[1] == {"state": "wait"}
    controller.cast.answer_access(d2["id"], False)
    assert call("GET", f"/api/freigabe?id={d2['id']}")[1] == {"state": "no"}


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
    assert "Tic-Tac-Toe" in page and f'"/spiel?u={controller.cast.games.token}" + "&name=' in page and "/?frei=" in page
    assert "Abstimmen" not in page
    controller.cast.start()
    controller.start_poll("Pizza?", ["Ja", "Nein"])
    page = portal_page(controller.cast)
    assert "📊 Abstimmen" in page and f"/abstimmung?u={controller.cast.poll.token}" in page and "Pizza?" in page
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
    controller.config["games"] = {**controller.config["games"], "auto_wifi": False, "wifi_only": False}
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


def test_only_alupc_wlan_reaches_alupc(monkeypatch):
    """Einziger Weg für Handys: das AluPC-WLAN (Anmeldeseite). Aus anderen Netzen: 403. Der PC selbst darf."""
    from alupc.cast_server import PUBLIC_PATHS, cast_server, _make_handler

    H = _make_handler(cast_server())
    h = H.__new__(H)
    hs = hotspot.hotspot
    monkeypatch.setattr(hs, "running", True)
    monkeypatch.setattr(hs, "portal", True)
    monkeypatch.setattr(hs, "ip", "10.42.0.1")
    for ip, want in (("127.0.0.1", True), ("::1", True), ("10.42.0.57", True), ("192.168.178.20", False),
                     ("10.43.0.5", False), ("::ffff:10.42.0.9", True), ("fe80::1", False)):
        h.client_address = (ip, 5000)
        assert h._via_wlan() is want, ip
    monkeypatch.setattr(hs, "portal", False)  # ohne Anmeldeseite auch aus dem WLAN nicht
    h.client_address = ("10.42.0.57", 5000)
    assert not h._via_wlan()
    assert "/" not in PUBLIC_PATHS and "/spiel" not in PUBLIC_PATHS and "/api/spiel" not in PUBLIC_PATHS


def test_internet_per_device(env, monkeypatch, tmp_path):  # noqa: F811
    """Hotspot-Fenster: Gerät „Internet“ geben (nach MAC) → seine aktuelle Adresse landet bei DNS und Firewall."""
    controller, _window, _ = env
    monkeypatch.setattr(hotspot, "portal_flag", lambda: tmp_path / "flag")
    hs = hotspot.hotspot
    monkeypatch.setattr(hs, "running", True)
    monkeypatch.setattr(hs, "portal", True)
    monkeypatch.setattr(hs, "ip", "10.42.0.1")
    monkeypatch.setattr(hotspot, "neighbors", lambda dev="", ip="": {"10.42.0.7": "aa:bb:cc:00:00:07",
                                                                   "10.42.0.9": "aa:bb:cc:00:00:09"})
    hotspot.note_name("10.42.0.7", "Lenas iPad")
    devices = controller.wlan_devices()
    assert [d["name"] for d in devices] == ["Lenas iPad", "Gerät"] and not any(d["internet"] for d in devices)
    controller.set_device_internet("AA:BB:CC:00:00:07", "Lenas iPad", True)
    assert (tmp_path / "flag.internet").read_text() == "10.42.0.7\n"
    assert controller.wlan_devices()[0]["internet"] and controller.config["hotspot"]["internet"]
    # neue Adresse (DHCP) → gleiche Freigabe, neue IP
    monkeypatch.setattr(hotspot, "neighbors", lambda dev="", ip="": {"10.42.0.33": "aa:bb:cc:00:00:07"})
    controller.sync_internet()
    assert (tmp_path / "flag.internet").read_text() == "10.42.0.33\n"
    controller.set_device_internet("aa:bb:cc:00:00:07", "Lenas iPad", False)
    assert (tmp_path / "flag.internet").read_text() == ""


def test_portal_dns_real_answers_only_for_allowed_devices():
    from alupc.portal_dns import PortalDNS

    dns = PortalDNS(lambda: "10.42.0.1", closed=True, port=0)
    dns.allowed = {"10.42.0.7"}
    assert dns.ip_for("www.example.com", 1, "10.42.0.9") == ["10.42.0.1"]  # nicht freigeschaltet: Anmeldeseite
    real = dns.ip_for("localhost", 1, "10.42.0.7")  # freigeschaltet: echte Auflösung
    assert real != ["10.42.0.1"] and (real is None or "127.0.0.1" in real)


def test_portal_dns_restricted_to_hotspot_net():
    """Windows lauscht auf allen Adressen – Fragen aus anderen Netzen (LAN) bekommen keine Antwort."""
    from alupc.portal_dns import PortalDNS

    dns = PortalDNS(lambda: "192.168.137.1", closed=True, restrict=True)
    q = bytes.fromhex("41550100000100000000000005616c75706303636f6d0000010001")
    assert dns._reply(q, "192.168.137.50") is not None
    assert dns._reply(q, "127.0.0.1") is not None
    assert dns._reply(q, "192.168.0.20") is None
    assert PortalDNS(lambda: "192.168.137.1", restrict=False)._reply(q, "192.168.0.20") is not None
