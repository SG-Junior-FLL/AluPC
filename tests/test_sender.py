"""Bildschirm an Fernseher senden: HLS-Stream, Webserver-Freigabe nur mit Schlüssel, Chromecast und AirPlay (mit
nachgebauten Geräten, die den Stream wirklich abholen und ein Bild dekodieren)."""

from __future__ import annotations

import time
import urllib.error
import urllib.request

import pytest

from test_gui import env, pump  # noqa: F401

pytest.importorskip("av")


def _wait(cond, sec=30.0):
    end = time.time() + sec
    while time.time() < end and not cond():
        pump(2)
        time.sleep(0.03)
    return cond()


def _show_red(controller):
    """Bildschirm zeigt eine rote Fläche (wie ein Inhalt) – im Stream muss Rot ankommen."""
    from PySide6.QtGui import QColor, QImage

    def red(w, h):
        img = QImage(w, h, QImage.Format_RGB888)
        img.fill(QColor("#e01010"))
        return img

    controller.vcam.frame_image = red


def _is_red(frame) -> bool:
    if frame is None:
        return False
    r, g, b = (int(v) for v in frame[frame.shape[0] // 2, frame.shape[1] // 2])
    return r > 180 and g < 70 and b < 70


def test_stream_only_with_key(env):  # noqa: F811
    controller, _w, _ = env
    from alupc.cast_server import active_port
    from alupc.sender import HlsStream

    controller.cast.start()
    stream = HlsStream(320, 180, 10)
    controller.cast.screen_stream = stream
    stream.start()
    try:
        assert _wait(stream.ready, 10)
        base = f"http://127.0.0.1:{active_port()}/bildschirm"
        r = urllib.request.urlopen(f"{base}/{stream.token}/stream.m3u8", timeout=5)
        assert r.status == 200 and r.headers["Access-Control-Allow-Origin"] == "*"
        assert b"#EXTM3U" in r.read()
        for bad in (f"{base}/falsch/stream.m3u8", f"{base}/{stream.token}/../config.json",
                    f"{base}/{stream.token}/geheim.txt"):
            with pytest.raises(urllib.error.HTTPError) as e:
                urllib.request.urlopen(bad, timeout=5)
            assert e.value.code == 404
    finally:
        controller.cast.screen_stream = None
        stream.stop()
    assert not stream.dir.exists()  # Stücke werden weggeräumt


def test_chromecast_gets_live_picture(env):  # noqa: F811
    pytest.importorskip("pychromecast")
    from fake_receivers import FakeChromecast

    from alupc.sender import CHROMECAST, Device

    controller, _w, _ = env
    _show_red(controller)
    cc = FakeChromecast()
    sender = controller.sender
    try:
        dev = Device(CHROMECAST, "Wohnzimmer", "127.0.0.1", cc.port, "8d2d2b6e-1f5a-4c7e-9a43-6c1b0c1d2e3f", "Chromecast")
        ok, why = sender.start(dev)
        assert ok, why
        assert _wait(lambda: sender.state != "verbinde", 60), sender.describe()
        assert sender.state == "läuft", sender.error
        assert sender.describe() == "Sendet an Wohnzimmer"
        media = cc.loaded[-1]
        assert media["contentType"] == "application/x-mpegURL" and media["streamType"] == "LIVE"
        assert "/bildschirm/" in media["contentId"] and media["contentId"].endswith("/stream.m3u8")
        assert _wait(cc.got_frame.is_set, 30)
        assert _is_red(cc.frame), "Chromecast hat nicht das Bild vom Bildschirm bekommen"
        assert controller.config["senden"]["last"] == dev.key
        sender.stop()
        assert _wait(cc.stopped.is_set, 10)  # Chromecast bekommt „Stopp“
        assert sender.state == "aus" and controller.cast.screen_stream is None
    finally:
        sender.stop()
        cc.close()


def test_airplay_gets_live_picture_and_stop(env):  # noqa: F811
    pytest.importorskip("pyatv")
    from fake_receivers import FakeAirPlay

    from alupc.sender import AIRPLAY, Device

    controller, _w, _ = env
    _show_red(controller)
    ap = FakeAirPlay()
    sender = controller.sender
    try:
        dev = Device(AIRPLAY, "Fernseher", "127.0.0.1", ap.port, "AA:BB:CC:DD:EE:FF", "AppleTV3,2",
                     {"features": "0x5A7FFFF7,0x1E", "model": "AppleTV3,2"})
        ok, why = sender.start(dev)
        assert ok, why
        assert _wait(lambda: sender.state != "verbinde", 60), sender.describe()
        assert sender.state == "läuft", sender.error
        assert ap.plays and ap.plays[-1]["Content-Location"].endswith("/stream.m3u8")
        assert _wait(ap.got_frame.is_set, 30)
        assert _is_red(ap.frame), "AirPlay-Empfänger hat nicht das Bild vom Bildschirm bekommen"
        sender.stop()
        assert _wait(lambda: ap.stops >= 1, 10)
    finally:
        sender.stop()
        ap.close()


def test_airplay_asks_for_pin(env, monkeypatch):  # noqa: F811
    pytest.importorskip("pyatv")
    from fake_receivers import FakeAirPlay

    from alupc import sender as sender_mod
    from alupc.sender import AIRPLAY, Device

    controller, _w, _ = env
    ap = FakeAirPlay(need_pin=True)
    sender = controller.sender
    asked = []
    from PySide6.QtWidgets import QInputDialog

    # hier tippt der Test die PIN, nicht das Fenster (dessen Abfrage schließt sofort, ohne abzubrechen)
    monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: ("", False)))
    monkeypatch.setattr(sender, "cancel_pin", lambda: None)
    sender.pin_needed.connect(asked.append)

    class Handler:  # Kopplung wie bei pyatv: begin → PIN → finish → credentials
        has_paired = False

        def __init__(self):
            self.service = type("S", (), {"credentials": ""})()

        def pin(self, pin):
            self._pin = pin

        async def finish(self):
            if self._pin == "1234":
                self.has_paired, self.service.credentials = True, "geheim:1"

        async def close(self):
            pass

    async def fake_begin(_dev, _loop):
        return Handler()

    monkeypatch.setattr(sender_mod, "_pair_begin", fake_begin)
    try:
        dev = Device(AIRPLAY, "Apple TV", "127.0.0.1", ap.port, "11:22:33:44:55:66", "AppleTV11,1",
                     {"features": "0x5A7FFFF7,0x1E"})
        sender.start(dev)
        assert _wait(lambda: asked, 60), sender.describe()
        assert asked == ["Apple TV"] and "PIN" in sender.error
        ok, why = sender.submit_pin("9999")
        assert not ok and "PIN" in why
        sender._begin_pairing(dev)
        assert _wait(lambda: sender._pairing is not None, 10)
        ap.need_pin = False  # nach der Kopplung nimmt der Fernseher an
        ok, why = sender.submit_pin("1234")
        assert ok, why
        assert controller.config["senden"]["airplay"][dev.key] == "geheim:1"
        assert sender._target.credentials == "geheim:1"  # neuer Versuch gleich mit der Kopplung
        # (die echte Prüfung der Kopplung macht pyatv mit dem Gerät – das kann der nachgebaute Empfänger nicht)
    finally:
        sender.stop()
        ap.close()


def test_discovery_parses_both_kinds():
    from alupc.sender import AIRPLAY, CHROMECAST, device_from_info

    class Info:
        def __init__(self, name, port, props, addr="192.168.1.50"):
            self.name, self.port, self.properties, self._a = name, port, props, addr

        def parsed_addresses(self):
            return ["fe80::1", self._a]

    cc = device_from_info(CHROMECAST, Info("Chromecast-abc._googlecast._tcp.local.", 8009,
                                          {b"fn": b"Wohnzimmer", b"id": b"abc", b"md": b"Chromecast"}))
    assert (cc.name, cc.host, cc.port, cc.ident, cc.model) == ("Wohnzimmer", "192.168.1.50", 8009, "abc", "Chromecast")
    ap = device_from_info(AIRPLAY, Info("Küche._airplay._tcp.local.", 7000,
                                       {b"deviceid": b"AA:BB", b"model": b"AppleTV5,3", b"x": None}))
    assert (ap.name, ap.ident, ap.props["x"]) == ("Küche", "AA:BB", "")
    assert device_from_info(AIRPLAY, Info("x._airplay._tcp.local.", 7000, {}, addr="fe80::2")) is None


def test_manual_device_and_command(env):  # noqa: F811
    controller, window, _ = env
    sender = controller.sender
    dev = sender.add_manual("airplay", " 192.168.1.77 ", "Beamer")
    assert (dev.host, dev.port, dev.name) == ("192.168.1.77", 7000, "Beamer")
    assert any(d.key == dev.key for d in sender.manual_devices())
    opened = []
    controller.sender_requested.connect(lambda: opened.append(1))
    controller.run_command("senden")
    assert opened == [1]


def test_window_pin_prompt_and_tile(env, monkeypatch):  # noqa: F811
    controller, window, _ = env
    from PySide6.QtWidgets import QInputDialog

    got = []
    monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: ("4711", True)))
    monkeypatch.setattr(controller.sender, "submit_pin", lambda pin: got.append(pin) or (True, ""))
    controller.sender.pin_needed.emit("Apple TV")
    assert got == ["4711"]
    monkeypatch.setattr(controller.sender, "scan", lambda: None)
    window.t_send.activated.emit()
    pump(5)
    dlg = window.sender_dialog
    assert dlg.isVisible() and dlg.windowTitle() == "An Fernseher senden"
    controller.sender.add_manual("chromecast", "10.0.0.9", "Küche")
    assert any(dlg.list.item(i).text().startswith("Küche (Chromecast") for i in range(dlg.list.count()))
    dlg.hide()


def test_discovery_real_mdns():
    """Echte mDNS-Suche: ein angemeldeter „Chromecast“ und „Apple TV“ werden gefunden."""
    pytest.importorskip("zeroconf")
    import socket

    from zeroconf import ServiceInfo, Zeroconf

    from alupc.sender import discover

    zc = Zeroconf()
    ip = socket.inet_aton("192.0.2.10")
    infos = [ServiceInfo("_googlecast._tcp.local.", "Chromecast-t1._googlecast._tcp.local.", addresses=[ip], port=8009,
                         properties={"fn": "Testzimmer", "id": "t1", "md": "Chromecast"}, server="cc-t1.local."),
             ServiceInfo("_airplay._tcp.local.", "TestTV._airplay._tcp.local.", addresses=[ip], port=7000,
                         properties={"deviceid": "AA:BB:CC:00:11:22", "model": "AppleTV5,3"}, server="tv-t1.local.")]
    try:
        for info in infos:
            zc.register_service(info)
        found = {(d.kind, d.name, d.host, d.port) for d in discover(3.0)}
    finally:
        zc.unregister_all_services()
        zc.close()
    if not found:
        pytest.skip("mDNS (Multicast) geht in dieser Umgebung nicht")
    assert ("chromecast", "Testzimmer", "192.0.2.10", 8009) in found
    assert ("airplay", "TestTV", "192.0.2.10", 7000) in found
