"""Whiteboard für Gäste im AluPC-WLAN: aus / alle / nur mit Erlaubnis – Modell, Webserver, Tafel, Anmeldeseite."""

import json

from test_gui import env, pump  # noqa: F401 – gleiche Test-Umgebung wie die GUI-Tests
from test_guests import _req

from alupc import hotspot
from alupc.board_guests import MAX_PER_SECOND, BoardGuests, parse_stroke

GID = "gast_abc12345"


def test_model_states_and_reset():
    g = BoardGuests()
    assert g.state("aus", GID) == "aus" and g.state("alle", GID) == "frei"
    assert g.state("frage", GID) == "fragen"
    assert g.ask(GID, "Mia<script>", "10.42.0.5") and g.names[GID] == "Miascript"
    assert not g.ask(GID, "Mia", "10.42.0.5")  # nicht zweimal am PC fragen
    assert g.state("frage", GID) == "warten"
    assert g.answer(GID, True) and g.state("frage", GID) == "frei"
    assert not g.answer(GID, True)
    assert g.state("alle", GID) == "frei" and g.state("frage", GID) == "fragen"  # Modus gewechselt → vergessen
    g.ask("andere_1234", "Tom", "10.42.0.6")
    g.answer("andere_1234", False)
    assert g.state("frage", "andere_1234") == "nein"
    assert not BoardGuests.valid_id("x") and BoardGuests.valid_id(GID)
    assert not any(g.throttle("1.2.3.4", now=100.0) for _ in range(MAX_PER_SECOND))
    assert g.throttle("1.2.3.4", now=100.1) and not g.throttle("1.2.3.4", now=102.0)


def test_parse_stroke():
    ok = parse_stroke({"tool": "marker", "color": "#22c55e", "size": 9, "pts": [[0.1, 0.2], [0.3, 0.4, 0.9]]})
    assert ok == {"tool": "marker", "color": "#22c55e", "size": 3, "pts": [(0.1, 0.2, 0.5), (0.3, 0.4, 0.9)]}
    assert parse_stroke({"tool": "eraser", "pts": [[0, 0]]}) is None  # Gäste radieren nicht
    assert parse_stroke({"tool": "pen", "color": "red", "pts": [[0, 0]]}) is None
    assert parse_stroke({"tool": "pen", "pts": [[1.5, 0]]}) is None
    assert parse_stroke({"tool": "pen", "pts": [[0, 0]] * 401}) is None
    assert parse_stroke({"tool": "pen", "pts": []}) is None


def test_guests_draw_over_http(env, monkeypatch):  # noqa: F811
    controller, window, _ = env
    hs = hotspot.hotspot
    for k, v in (("running", True), ("portal", True), ("ssid", "AluPC"), ("password", "k7pm2qa9xr"),
                 ("hidden", False), ("ip", "10.42.0.1")):
        monkeypatch.setattr(hs, k, v)
    assert controller.cast.start()
    port = controller.cast.port
    stroke = {"action": "strich", "g": GID, "tool": "pen", "color": "#ef4444", "size": 2,
              "pts": [[0.25, 0.5], [0.5, 0.5], [0.75, 0.5]]}
    post = lambda body: _req(port, "/api/tafel", json.dumps(body).encode())  # noqa: E731
    # aus: kein Knopf, nichts geht
    assert b'id="board"' not in _req(port, "/anmelden")[1]
    assert json.loads(_req(port, f"/api/tafel?g={GID}")[1])["state"] == "aus"
    assert post(stroke)[0] == 404
    assert _req(port, "/tafel")[0] == 200
    # alle: Knopf auf der Anmeldeseite; Tafel noch nicht auf Monitor 2 → 423
    controller.run_command("tafel_gaeste_alle")
    assert controller.board.settings()["guests"] == "alle"
    assert b'id="board"' in _req(port, "/anmelden")[1]
    assert post(stroke)[0] == 423
    controller.show_whiteboard(draw=False)
    pump()
    before = len(controller.board.strokes)
    status, body = post(stroke)
    assert status == 200, body
    pump()
    assert len(controller.board.strokes) == before + 1
    s = controller.board.strokes[-1]
    assert s["t"] == "pen" and s["c"] == "#ef4444" and len(s["p"]) == 3
    left, right = controller.board.to_world(0.25, 0.5), controller.board.to_world(0.75, 0.5)
    assert abs(s["p"][0][0] - left.x()) < 0.2 and abs(s["p"][-1][0] - right.x()) < 0.2
    assert post({**stroke, "tool": "eraser"})[0] == 400
    assert post({**stroke, "g": "x"})[0] == 400
    # nur mit Erlaubnis: erst fragen → PC-Frage → erlauben
    asked = []
    controller.board_guest_requested.connect(lambda gid, name: asked.append((gid, name)))
    controller.run_command("tafel_gaeste_frage")
    assert post(stroke)[0] == 403
    status, body = post({"action": "frage", "g": GID, "name": "Mia"})
    assert status == 200 and json.loads(body)["state"] == "warten"
    pump()
    assert asked == [(GID, "Mia")]
    assert post(stroke)[0] == 403
    controller.answer_board_guest(GID, True)
    assert json.loads(_req(port, f"/api/tafel?g={GID}")[1])["state"] == "frei"
    assert post(stroke)[0] == 200
    pump()
    assert len(controller.board.strokes) == before + 2
    assert controller.board_state()["guests"] == "frage"
    controller.set_board_guests("aus")
    assert post(stroke)[0] == 404 and b'id="board"' not in _req(port, "/anmelden")[1]
    controller.cast.stop()


def test_ipad_heft_settings_and_board_menu(env):  # noqa: F811
    """Heft-Ansicht am iPad: Einstellungen wie im Fenster am PC, Tafel neu/öffnen/umbenennen, Seite wählen."""
    import pytest

    from alupc.cast_server import board_setting

    assert board_setting("width", "50") == 20.0 and board_setting("smooth", 2) == 2
    assert board_setting("pressure", False) is False and board_setting("format", "a4") == "a4"
    for key, bad in (("pressure", "ja"), ("format", "riesig"), ("smooth", 7), ("colors", ["#fff"]), ("geheim", 1)):
        with pytest.raises((ValueError, TypeError)):
            board_setting(key, bad)
    controller, window, _ = env
    controller.show_whiteboard(draw=False)
    pump()
    req = lambda **kw: controller._cast_request({"kind": "board", **kw})  # noqa: E731
    req(op="einstellung", key="width", value=12.0)
    req(op="einstellung", key="pencil_only", value=True)
    assert controller.board.settings()["width"] == 12.0 and controller.board.settings()["pencil_only"] is True
    pages = len(controller.board.doc["pages"])
    req(op="seite_neu", arg="")
    req(op="seite", arg="1")
    assert controller.board.doc["page"] == 0 and len(controller.board.doc["pages"]) == pages + 1
    req(op="tafel_neu", arg="Mathe")
    assert controller.board.doc["name"] == "Mathe"
    req(op="tafel_umbenennen", arg="Mathe 7b")
    req(op="tafel_oeffnen", arg="gibt es nicht")
    assert controller.board.doc["name"] == "Mathe 7b"
    state = controller.board_state()
    assert state["settings"]["width"] == 12.0 and "Mathe 7b" in state["boards"]
    assert ["kariert", "Kariert"] in state["papers"] and state["formats"][0][0] == "16:9"
    controller.cast.thumbs_wanted = __import__("time").monotonic()
    assert controller.cast.start()
    controller._board_thumbs()
    assert len(controller.cast.board_thumbs) == len(controller.board.doc["pages"])
    assert controller.cast.board_thumbs[0][:2] == b"\xff\xd8"
    controller.cast.stop()
