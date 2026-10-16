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
    end = time.time() + 3
    while time.time() < end:  # schneller Takt (~110 ms) statt alle 0,9 s
        pump()
        time.sleep(0.02)
    assert controller.cast.preview_seq - seq0 >= 15
    assert controller.cast.preview.startswith(b"\xff\xd8")  # JPEG
    from PySide6.QtGui import QImage

    img = QImage.fromData(controller.cast.preview)
    assert img.width() == 960  # beim Zeichnen schärfer
    status, body = _http("POST", base + "/api/draw", json.dumps({"phase": "up"}).encode(), headers=hdr)
    assert status == 200 and json.loads(body)["seq"] == controller.cast.preview_seq
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
