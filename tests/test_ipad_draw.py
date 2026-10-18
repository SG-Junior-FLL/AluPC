"""iPad zeichnet: schnelles Live-Bild mit Bildnummer, Antworten mit Bildnummer (für die lokale Tinte/Zoom-Vorschau)."""

from __future__ import annotations

import json
import time

from test_gui import _free_tcp_port, _http, env, pump  # noqa: F401


def test_fast_preview_and_frame_numbers(env):  # noqa: F811
    controller, window, _ = env
    port = _free_tcp_port()
    controller.config["cast"] = {**controller.config["cast"], "port": port, "code": "123456"}
    controller.cast.start()
    controller.show_whiteboard("weiss", draw=False)
    pump()
    base = f"http://127.0.0.1:{controller.cast.port}"
    hdr = {"X-AluPC-Code": "123456"}
    status, _ = _http("GET", base + "/api/preview?fast=1", headers=hdr)
    seq0 = controller.cast.preview_seq
    end, ask = time.time() + 3, time.time() + 0.5
    while time.time() < end:  # schneller Takt (~110 ms) statt alle 0,9 s – das iPad fragt dabei laufend nach
        pump()
        time.sleep(0.02)
        if time.time() > ask:
            controller.cast.preview_fast, ask = time.monotonic(), time.time() + 0.5
    assert controller.cast.preview_seq - seq0 >= 15
    assert controller.cast.preview.startswith(b"\xff\xd8")  # JPEG
    from PySide6.QtGui import QImage

    img = QImage.fromData(controller.cast.preview)
    assert img.width() == 960  # beim Zeichnen schärfer
    status, body = _http("POST", base + "/api/draw", json.dumps({"phase": "up"}).encode(), headers=hdr)
    n = json.loads(body)["seq"]  # Nummer der Eingabe …
    assert status == 200 and n == controller.cast.live_no
    controller.cast.preview_fast = time.monotonic()
    end = time.time() + 2
    while time.time() < end and controller.cast.preview_applied < n:
        pump()
        time.sleep(0.01)
    assert controller.cast.preview_applied >= n  # … das nächste Live-Bild enthält sie
    st = controller.board_state()
    assert st["page_h"] > 0 and st["zoom_f"] == 1.0
    # ohne „fast“ wieder nur langsam
    controller.cast.preview_fast = 0.0
    seq1 = controller.cast.preview_seq
    end = time.time() + 1
    while time.time() < end:
        pump()
        time.sleep(0.02)
    assert controller.cast.preview_seq - seq1 <= 2


def test_page_has_local_ink_and_view():
    from alupc.cast_page import PAGE

    for part in ("function frameArrived", "X-AluPC-Frame", "?fast=1", "function gestureMove", "mergeView",
                 "getCoalescedEvents", "#heft.max .hpages, #heft.max .hstatus { display:none; }"):
        assert part in PAGE, part
    assert "#heft.max .hbar" not in PAGE  # Vergrößern: Werkzeuge bleiben


def test_live_websocket_frames_and_inputs(env):  # noqa: F811
    """WebSocket /ws/live: Bilder kommen ohne Nachfragen, Striche gehen darüber und werden mit Nummer bestätigt."""
    import base64
    import os
    import socket
    import struct
    import threading

    from alupc import ws

    controller, window, _ = env
    port = _free_tcp_port()
    controller.config["cast"] = {**controller.config["cast"], "port": port, "code": "123456"}
    controller.cast.start()
    controller.show_whiteboard("weiss", draw=False)
    pump()
    out = {"frames": [], "acks": []}

    def client():
        s = socket.create_connection(("127.0.0.1", controller.cast.port), timeout=10)
        key = base64.b64encode(os.urandom(16)).decode()
        s.sendall((f"GET /ws/live?c=123456 HTTP/1.1\r\nHost: x\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                   f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode())
        f = s.makefile("rb")
        while f.readline() not in (b"\r\n", b""):
            pass

        def send_text(obj):
            data = json.dumps(obj).encode()
            mask = os.urandom(4)
            s.sendall(bytes([0x81, 0x80 | len(data)]) + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))

        send_text({"p": "draw", "b": {"phase": "down", "x": 0.2, "y": 0.5, "tool": "pen", "color": "#ef4444"}})
        send_text({"p": "draw", "b": {"phase": "move", "x": 0.6, "y": 0.5, "tool": "pen", "color": "#ef4444"}})
        send_text({"p": "draw", "b": {"phase": "up"}, "id": 7})
        end = time.time() + 6
        while time.time() < end and (len(out["frames"]) < 3 or not out["acks"]):
            got = ws.read_frame(f)
            if got is None:
                break
            op, data = got
            if op == 0x2:
                out["frames"].append(struct.unpack(">I", data[:4])[0])
                assert data[4:6] == b"\xff\xd8"
            elif op == 0x1:
                out["acks"].append(json.loads(data))
        s.close()

    t = threading.Thread(target=client)
    t.start()
    end = time.time() + 8
    while t.is_alive() and time.time() < end:
        pump()
        time.sleep(0.01)
    t.join(1)
    assert out["acks"] and out["acks"][0]["ack"] == 7
    n = out["acks"][0]["seq"]
    assert max(out["frames"]) >= n  # ein Bild mit dem Strich kam an
    assert controller.board.strokes and controller.board.strokes[-1]["c"] == "#ef4444"


def test_live_websocket_needs_code(env):  # noqa: F811
    controller, window, _ = env
    port = _free_tcp_port()
    controller.config["cast"] = {**controller.config["cast"], "port": port, "code": "123456"}
    controller.cast.start()
    status, _ = _http("GET", f"http://127.0.0.1:{controller.cast.port}/ws/live?c=000000",
                      headers={"Upgrade": "websocket", "Connection": "Upgrade", "Sec-WebSocket-Key": "abc"})
    assert status == 403
