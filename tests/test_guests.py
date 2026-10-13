"""Gäste: Chat (übers AluPC-WLAN, direkt als Overlay) und Foto-Wand – Modell, Webserver, Monitor 2, Seite „Gäste“."""

import json
import time
import urllib.error
import urllib.request

import pytest

from test_gui import env  # noqa: F401 – gleiche Test-Umgebung wie die GUI-Tests

from alupc import hotspot
from alupc.chat import Chat, WordFilter


def _jpeg(w=640, h=480, color="#ff0000") -> bytes:
    from PySide6.QtCore import QBuffer, QByteArray, QIODevice
    from PySide6.QtGui import QColor, QImage

    img = QImage(w, h, QImage.Format_RGB32)
    img.fill(QColor(color))
    data = QByteArray()
    buf = QBuffer(data)
    buf.open(QIODevice.WriteOnly)
    img.save(buf, "JPEG", 90)
    return bytes(data)


def _req(port, path, data=None, ctype="application/json"):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=data, method="POST" if data is not None else "GET",
                                 headers={"Content-Type": ctype, "Host": f"10.42.0.1:{port}"})  # wie ein Handy
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # direkt, nie über einen Proxy
    try:
        with opener.open(req, timeout=10) as r:
            body = r.read()
            return r.status, body
    except urllib.error.HTTPError as e:
        return e.code, e.read()


# --------------------------------------------------------------------------- Modell
def test_word_filter_and_links():
    f = WordFilter(["Pausenbrot"])
    text, changed = f.apply("Du Arschloch, mein Pausenbrot! Klassenarbeit www.example.de und https://x.y/z")
    assert changed and "Arschloch" not in text and "Pausenbrot" not in text
    assert "Klassenarbeit" in text  # „arsch“ mitten im Wort bleibt
    assert "example" not in text and "x.y" not in text and text.count("[Link]") == 2
    assert WordFilter([], builtin=False, hide_links=False).apply("Arsch www.a.de") == ("Arsch www.a.de", False)


def test_chat_rate_block_delete_clear():
    c = Chat()
    t = time.time()
    assert c.post("Max", "Hallo", "10.42.0.5", now=t)[0]
    assert c.post("Max", "nochmal", "10.42.0.5", now=t + 0.2) == (None, "Nicht so schnell – kurz warten")
    for i in range(3):
        assert c.post("Max", f"m{i}", "10.42.0.5", now=t + 1 + i)[0]
    assert c.post("Max", "zu viel", "10.42.0.5", now=t + 5)[1] == "Nicht so schnell – kurz warten"  # 4 in 10 s
    assert c.post("Mia", "   ", "10.42.0.6", now=t)[1] == "Leere Nachricht"
    assert c.post("Mia", "x" * 500, "10.42.0.6", now=t)[0]["text"] == "x" * 200
    assert c.block("10.42.0.5") == 4 and all(m["ip"] != "10.42.0.5" for m in c.messages)
    assert c.post("Max", "hi", "10.42.0.5", now=t + 60)[1] == "Du bist im Chat gesperrt"
    host, _ = c.post("", "Willkommen!", host=True)
    assert host["host"] and host["name"] == "AluPC"
    assert c.delete(host["id"]) and not c.delete(9999)
    c.set_open(False)
    assert c.post("Mia", "zu", "10.42.0.6", now=t + 60)[1] == "Der Chat ist gerade geschlossen"
    c.clear()
    assert c.since(0) == {"open": False, "messages": [], "last": 0}
    assert "ip" not in Chat.public({"id": 1, "name": "a", "avatar": "", "text": "b", "t": 0, "host": False, "ip": "x"})


def test_photowall_model(tmp_path):
    from alupc.photowall import PhotoWall

    wall = PhotoWall(tmp_path / "wand")
    t = time.time()
    photo, why = wall.add(_jpeg(3000, 2000), "Lena", "10.42.0.7", now=t)
    assert photo and not why
    from PySide6.QtGui import QImage

    img = QImage(photo["path"])
    assert max(img.width(), img.height()) == 2048 and (tmp_path / "wand" / ".vorschau").is_dir()
    assert wall.add(b"kein bild", "Lena", "10.42.0.8", now=t)[1].startswith("Das ist kein Foto")
    assert wall.add(_jpeg(), "Lena", "10.42.0.7", now=t + 0.5)[1] == "Nicht so schnell – kurz warten"
    second, _ = wall.add(_jpeg(color="#00ff00"), "Tom", "10.42.0.9", now=t)
    assert [p["id"] for p in wall.latest()] == [photo["id"], second["id"]]
    assert wall.remove(second["id"]) and not (tmp_path / "wand" / second["path"]).exists()
    assert wall.block("10.42.0.7") == 1 and not wall.photos
    assert wall.add(_jpeg(), "Lena", "10.42.0.7", now=t + 120)[1] == "Du bist für die Foto-Wand gesperrt"
    pc, _ = wall.add(_jpeg(), "PC")  # vom PC: ohne Sperren/Tempo
    wall.clear()
    assert not wall.photos and (tmp_path / "wand").exists() and wall.public()["photos"] == []
    assert pc is not None


# --------------------------------------------------------------------------- Webserver + Monitor 2
def test_chat_and_wall_over_http_and_monitor2(env, tmp_path, monkeypatch):  # noqa: F811
    zx = pytest.importorskip("zxingcpp")
    pil = pytest.importorskip("PIL.Image")
    controller, window, _ = env
    hs = hotspot.hotspot
    for k, v in (("running", True), ("ssid", "AluPC"), ("password", "k7pm2qa9xr"),
                 ("hidden", False), ("ip", "10.42.0.1")):
        monkeypatch.setattr(hs, k, v)
    monkeypatch.setattr(controller, "ensure_wlan", lambda: None)
    controller.config["photowall"] = {**controller.config["photowall"], "folder": str(tmp_path / "wand")}
    port = None
    # aus: Seiten da, aber Chat/Foto-Wand antworten „aus“
    assert controller.cast.start()
    port = controller.cast.port
    assert _req(port, "/api/chat")[0] == 404 and _req(port, "/api/fotowand")[0] == 404
    controller.start_chat()
    controller.start_wall(show=False)
    from alupc.cast_server import wlan_url

    assert wlan_url("/chat") == f"http://10.42.0.1:{port}/chat"  # Code auf Monitor 2: direkt die Seite
    assert _req(port, "/chat")[0] == 200 and _req(port, "/fotos")[0] == 200
    assert "chat" in controller.live_overlays  # Chat startet direkt mit Overlay
    status, body = _req(port, "/api/chat", json.dumps({"name": "Lena", "text": "Hallo Arschloch", "avatar": "🦊"}).encode())
    assert status == 200 and json.loads(body)["filtered"]
    status, body = _req(port, "/api/chat", json.dumps({"name": "Lena", "text": "gleich nochmal"}).encode())
    assert status == 429
    data = json.loads(_req(port, "/api/chat?after=0")[1])
    assert data["open"] and [m["text"] for m in data["messages"]] == ["Hallo ******"]
    assert data["messages"][0]["avatar"] == "🦊" and "ip" not in data["messages"][0]
    status, body = _req(port, "/api/fotowand?name=Tom", _jpeg(), "image/jpeg")
    assert status == 200
    pid = json.loads(body)["id"]
    assert _req(port, "/api/fotowand?name=Tom", b"x" * 100, "image/jpeg")[0] in (415, 429)
    assert json.loads(_req(port, "/api/fotowand")[1])["photos"][0]["name"] == "Tom"
    status, img = _req(port, f"/api/fotowand/bild?klein=1&id={pid}")
    assert status == 200 and img[:2] == b"\xff\xd8"
    from alupc.cast_server import _make_handler

    H = _make_handler(controller.cast)  # aus einem anderen Netz: alles gesperrt
    h = H.__new__(H)
    h.client_address = ("192.168.178.20", 5000)
    assert not h._via_wlan()

    # Chat-Overlay zeichnet Nachricht + QR-Code (/chat)
    from PySide6.QtGui import QImage, QPainter

    from alupc import overlays as ov

    item = controller.chat_overlay_item()
    data_ = ov.OverlayData()
    data_.chat = lambda: controller.cast.chat
    canvas = QImage(1280, 720, QImage.Format_ARGB32)
    canvas.fill(0xFF202020)
    p = QPainter(canvas)
    ov.paint_all(p, [item], 1280, 720, data_)
    p.end()
    path = tmp_path / "overlay.png"
    canvas.save(str(path))
    codes = [r.text for r in zx.read_barcodes(pil.open(path))]
    assert codes == [f"http://10.42.0.1:{port}/chat"]
    r = ov.place(item, 1280, 720, ov.measure(item, 1280, 720, data_))
    assert r.x() < 60 and r.bottom() > 680  # unten links

    # Monitor 2: Chat-Wand und Foto-Wand mit beiden Codes (WLAN + Seite)
    from alupc.guest_sources import ChatWallSource, PhotoWallSource
    from alupc.screens import wifi_payload

    for cls, page in ((ChatWallSource, "/chat"), (PhotoWallSource, "/fotos")):
        src = cls({})
        src.resize(1280, 720)
        src._tick()
        src.grab().save(str(path))
        codes = sorted(r.text for r in zx.read_barcodes(pil.open(path)))
        assert codes == sorted([wifi_payload("AluPC", "k7pm2qa9xr"), f"http://10.42.0.1:{port}{page}"]), cls
        src.stop()
    controller.run_command("fotowand")
    assert controller.content["type"] == "fotowand"
    controller.run_command("chat_wand")
    assert controller.content["type"] == "chatwand"

    # Seite „Gäste“: Liste, löschen, sperren
    from alupc.ui.guests_page import GuestsPage

    page_w = GuestsPage(controller)
    page_w.refresh(force=True)
    assert "Lena" in page_w.chat_list.item(0).text() and page_w.wall_list.count() == 1
    page_w.chat_list.setCurrentRow(0)
    page_w._block_selected()
    assert not controller.cast.chat.messages and "127.0.0.1" in controller.cast.chat.blocked
    assert _req(port, "/api/chat", json.dumps({"name": "Lena", "text": "wieder da"}).encode())[0] == 403
    page_w.wall_list.setCurrentRow(0)
    page_w._delete_photo()
    assert not controller.cast.wall.photos
    assert controller.chat_say("Pause bis 10:30")
    controller.set_chat_overlay(False)
    assert "chat" not in controller.live_overlays and controller.config["chat"]["overlay"] is False
    controller.stop_chat()
    controller.stop_wall()
    assert _req(port, "/api/chat")[0] == 404 and _req(port, "/api/fotowand")[0] == 404
    page_w.close()
    controller.cast.stop()


def test_overlay_template_and_icons():
    from alupc import overlays as ov
    from alupc.ui import icons

    assert any(t[3]["type"] == "chat" for t in ov.TEMPLATES) and "chat" in ov.TYPES
    for name in ("chat", "users", "mixer", "apps", "photos", "webcam"):
        assert not icons.pixmap(name, "#ffffff", 24).isNull()


def test_chat_popup_mode(env):  # noqa: F811
    """Chat als Pop-up: nur neue Nachrichten (8 s), kein QR-Code, ohne Nachricht unsichtbar; Befehl schaltet um."""
    from PySide6.QtCore import QSizeF

    from alupc import overlays

    controller, _window, _ = env
    chat = Chat([], True, True)
    data = overlays.OverlayData()
    data.chat = lambda: chat
    item = {"type": "chat", "mode": "popup", "count": 5, "seconds": 0, "qr": True, "x": 1.0, "y": 1.0}
    assert overlays.measure(item, 1280, 720, data) == QSizeF(overlays.measure(item, 1280, 720, data).width(), 0)
    chat.post("Tom", "alt", ip="a")
    chat.post("Mia", "neu", ip="b")
    chat.messages[0]["t"] -= 20  # älter als 8 s → weg
    assert [m["text"] for m in data.chat_messages(item)] == ["neu"]
    assert overlays._chat_head(item, 10, data) == 0  # nie ein QR-Code
    liste = {**item, "mode": "liste"}
    assert [m["text"] for m in data.chat_messages(liste)] == ["alt", "neu"]
    controller.config["chat"] = {**controller.config["chat"], "mode": "liste"}
    controller.run_command("chat_popup")
    assert controller.config["chat"]["mode"] == "popup" and controller.live_overlays["chat"]["mode"] == "popup"
    controller.run_command("chat_popup")
    assert controller.config["chat"]["mode"] == "liste"
    controller.stop_chat()
