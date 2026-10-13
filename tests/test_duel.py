"""Schiffe versenken: Regeln, Handy von Spieler 2 (Webserver), Monitor 2 (nur Spieler 2), PC-Fenster (Spieler 1 +
Tastatur für Spieler 2)."""

import json
import random

import pytest

from test_gui import env, pump  # noqa: F401 – gleiche Test-Umgebung wie die GUI-Tests
from test_guests import _req

from alupc import hotspot
from alupc.duel import SHIPS, SIZE, Battleship, Fleet, ship_cells


def _fill(game: Battleship, p: int) -> None:
    game.randomize(p)
    assert game.fleets[p].complete()


def test_fleet_rules():
    f = Fleet()
    assert f.place(0, 0, True)  # 5 waagrecht A1–E1
    assert not f.place(0, 1, True)  # direkt darunter: berührt → nicht erlaubt
    assert not f.place(5, 0, True)  # berührt das Ende (F1 neben E1)
    assert not f.place(7, 5, True)  # 4 lang ab H6 → raus aus dem Feld
    assert f.place(0, 2, True)
    f.undo()
    assert len(f.ships) == 1
    for _ in range(20):
        g = Fleet()
        g.randomize(random.Random(_))
        cells = [c for s in g.ships for c in s]
        assert sorted(len(s) for s in g.ships) == sorted(SHIPS) and len(set(cells)) == sum(SHIPS)
        assert all(0 <= x < SIZE and 0 <= y < SIZE for x, y in cells)
        for i, s in enumerate(g.ships):  # kein Schiff berührt ein anderes (auch nicht schräg)
            others = {c for j, o in enumerate(g.ships) if j != i for c in o}
            assert not any((x + dx, y + dy) in others for x, y in s for dx in (-1, 0, 1) for dy in (-1, 0, 1))
    assert ship_cells(2, 3, 3, False) == [(2, 3), (2, 4), (2, 5)]


def test_battle_turns_hits_sunk_win():
    game = Battleship(random.Random(1))
    _fill(game, 1)
    assert not game.set_ready(2)  # Spieler 2 hat noch nichts gesetzt
    assert game.set_ready(1) and game.phase == "setzen"
    assert not game.place(1, 0, 0)  # bereit → nichts mehr ändern
    _fill(game, 2)
    assert game.set_ready(2) and game.phase == "spielen" and game.turn in (1, 2)
    p = game.turn
    q = game.other(p)
    assert game.shoot(q, 0, 0) == ""  # nicht dran
    target = game.fleets[q]
    water = next((x, y) for x in range(SIZE) for y in range(SIZE) if target.ship_at((x, y)) is None)
    assert game.shoot(p, *water) == "wasser" and game.turn == q
    assert game.shoot(q, 0, 0) != "" and True  # q darf jetzt
    # Spieler p versenkt alles (Treffer = nochmal)
    game.turn = p
    results = []
    for ship in target.ships:
        for c in ship:
            results.append(game.shoot(p, *c))
            assert game.turn == p or game.phase == "ende"
    assert results.count("versenkt") == len(SHIPS) - 1 and results[-1] == "sieg"
    assert game.phase == "ende" and game.winner == p
    assert game.shoot(p, *water) == ""
    v = game.view(q)
    assert v["phase"] == "ende" and v["winner"] == p and len(v["own"]["ships"]) == len(SHIPS)
    # Gegner-Ansicht verrät keine Schiffe, nur Schüsse (versenkte werden aufgedeckt)
    v1 = game.view(p)
    assert "ships" not in v1["target"] and len(v1["target"]["sunk"]) == sum(SHIPS) and v1["target"]["left"] == 0
    game.restart()
    assert game.phase == "setzen" and not game.fleets[1].ships and game.winner == 0


def test_view_hides_enemy_ships_while_playing():
    game = Battleship(random.Random(3))
    _fill(game, 1)
    _fill(game, 2)
    game.set_ready(1)
    game.set_ready(2)
    v = game.view(2)
    assert v["target"] == {"hits": [], "misses": [], "sunk": [], "left": len(SHIPS)}
    assert json.dumps(v)  # fürs Handy als JSON
    ghost, ok = game.ghost(2, 0, 0)
    assert ghost == [] and ok is False  # nach dem Setzen keine Vorschau mehr


def test_phone_player_two(env, monkeypatch, tmp_path):  # noqa: F811
    controller, window, _ = env
    hs = hotspot.hotspot
    for k, v in (("running", True), ("ssid", "AluPC"), ("password", "k7pm2qa9xr"),
                 ("hidden", False), ("ip", "10.42.0.1")):
        monkeypatch.setattr(hs, k, v)
    monkeypatch.setattr(controller, "ensure_wlan", lambda: None, raising=False)
    monkeypatch.setenv("ALUPC_NO_AUTO_WIFI", "1")
    controller.cast.duel = None  # (Webserver gibt es nur einmal – nichts aus einem anderen Test übernehmen)
    assert controller.cast.start()
    port = controller.cast.port
    assert _req(port, "/api/schiffe?u=x")[0] == 404  # noch kein Spiel
    controller.run_command("schiffe")
    pump()
    duel = controller.cast.duel
    assert duel is not None and controller.content["type"] == "schiffe"
    win = window.duel_window
    assert win.isVisible()
    assert _req(port, "/schiffe")[0] == 200
    assert _req(port, "/api/schiffe?u=falsch")[0] == 404
    u = f"/api/schiffe?u={duel.token}"
    status, body = _req(port, u, json.dumps({"action": "join", "name": "Mia"}).encode())
    assert status == 200 and json.loads(body)["name"] == "Mia" and duel.p2_phone
    assert duel.phone_action({"action": "random"}, "10.42.0.9") is None  # zweites Handy darf nicht
    status, body = _req(port, u, json.dumps({"action": "place", "x": 0, "y": 0}).encode())
    assert status == 200 and json.loads(body)["ok"] and json.loads(body)["next"] == 4
    _req(port, u, json.dumps({"action": "undo"}).encode())
    _req(port, u, json.dumps({"action": "random"}).encode())
    assert _req(port, u, json.dumps({"action": "ready"}).encode())[0] == 200 and duel.ready[2]
    # Spieler 1 im Fenster: Zufällig + Bereit
    win.rnd_btn.click()
    assert win.ready_btn.isEnabled()
    win.ready_btn.click()
    assert duel.phase == "spielen"
    duel.turn = 2
    v = json.loads(_req(port, u)[1])
    assert v["turn"] == 2 and "ships" not in v["target"]
    target = duel.fleets[1]
    x, y = next((x, y) for x in range(SIZE) for y in range(SIZE) if target.ship_at((x, y)) is None)
    status, body = _req(port, u, json.dumps({"action": "shoot", "x": x, "y": y}).encode())
    assert status == 200 and json.loads(body)["ok"] and duel.turn == 1
    assert not json.loads(_req(port, u, json.dumps({"action": "shoot", "x": x, "y": y}).encode())[1])["ok"]
    # Spieler 1 schießt per Mausklick ins rechte Feld
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtTest import QTest

    from alupc import duel_draw as dd

    win.resize(1100, 700)
    pump()
    _own, tarea = win.boards.areas()
    rect, cell = dd.board_rect(tarea)
    before = len(duel.fleets[2].hits) + len(duel.fleets[2].misses)
    QTest.mouseClick(win.boards, Qt.LeftButton, Qt.NoModifier,
                     QPointF(rect.x() + cell * 2.5, rect.y() + cell * 3.5).toPoint())
    assert len(duel.fleets[2].hits) + len(duel.fleets[2].misses) == before + 1
    assert (2, 3) in duel.fleets[2].hits | duel.fleets[2].misses
    # Monitor 2 verrät die Schiffe von Spieler 2 nicht, solange er am Handy spielt (Zuschauer-Ansicht)
    from PySide6.QtGui import QColor

    from alupc.duel_source import DuelSource

    src = DuelSource({})
    src.resize(1280, 720)
    ship = QColor(dd.SHIP)

    def ship_pixels():
        img = src.grab().toImage()
        return sum(img.pixelColor(x, y) == ship for x in range(0, 1280, 2) for y in range(0, 720, 2))

    spectator = ship_pixels()
    duel.p2_phone = False  # zum Vergleich: Tastatur-Ansicht zeigt die eigene Flotte
    shown = ship_pixels()
    duel.p2_phone = True
    assert shown > 2000 and spectator < 100, (shown, spectator)  # (wenige Pixel: Text in derselben Farbe)
    src.stop()
    # Handy abmelden → Platz wieder frei
    duel.release_phone()
    assert not duel.p2_phone
    win.close()
    pump()
    assert controller.cast.duel is None and _req(port, u)[0] == 404
    assert controller.content is None or controller.content.get("type") != "schiffe"
    controller.cast.stop()


def test_keyboard_player_two_and_monitor2(env, tmp_path, monkeypatch):  # noqa: F811
    zx = pytest.importorskip("zxingcpp")
    pil = pytest.importorskip("PIL.Image")
    controller, window, _ = env
    hs = hotspot.hotspot
    for k, v in (("running", True), ("ssid", "AluPC"), ("password", "k7pm2qa9xr"),
                 ("hidden", False), ("ip", "10.42.0.1")):
        monkeypatch.setattr(hs, k, v)
    monkeypatch.setenv("ALUPC_NO_AUTO_WIFI", "1")
    controller.cast.duel = None
    controller.start_duel()
    pump()
    duel = controller.cast.duel
    win = window.duel_window
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    QTest.keyClick(win, Qt.Key_Right)
    QTest.keyClick(win, Qt.Key_Down)
    assert duel.cursor == (1, 1)
    QTest.keyClick(win, Qt.Key_R)  # senkrecht
    QTest.keyClick(win, Qt.Key_Return)
    assert duel.fleets[2].ships == [[(1, 1), (1, 2), (1, 3), (1, 4), (1, 5)]]
    QTest.keyClick(win, Qt.Key_Backspace)
    assert not duel.fleets[2].ships
    QTest.keyClick(win, Qt.Key_Z)
    QTest.keyClick(win, Qt.Key_B)
    assert duel.ready[2] and not duel.fleets[1].ships  # Spieler 1 bleibt unberührt

    # Monitor 2 zeigt nur Spieler 2 – mit WLAN-Code + Code für die Spielseite
    from alupc.duel_source import DuelSource
    from alupc.screens import wifi_payload

    src = DuelSource({})
    src.resize(1280, 720)
    path = tmp_path / "m2.png"
    src.grab().save(str(path))
    codes = sorted(r.text for r in zx.read_barcodes(pil.open(path)))
    port = controller.cast.port
    assert codes == sorted([wifi_payload("AluPC", "k7pm2qa9xr"), f"http://10.42.0.1:{port}/schiffe?u={duel.token}"])
    _fill(duel, 1)
    duel.set_ready(1)
    duel.turn = 2
    duel.cursor = (0, 0)
    src.grab().save(str(path))  # Spielen: zeichnet ohne Fehler
    QTest.keyClick(win, Qt.Key_Space)
    assert (0, 0) in duel.fleets[1].hits | duel.fleets[1].misses
    src.stop()
    controller.run_command("schiffe_aus")
    assert controller.cast.duel is None
    win.close()
    controller.cast.stop()


def test_intent_and_command_palette():
    from alupc import intents, startpage

    assert "schiffe" in startpage.COMMANDS
    assert intents.understand(["schiffe", "versenken"]) == ("schiffe", "Schiffe versenken")
    assert intents.understand(["minispiele"])[0] == "spiele"  # bleibt wie vorher


def test_free_order_pick_up_and_move():
    """Setzen am Handy/iPad: Länge frei wählbar, gesetztes Schiff aufnehmen und woanders hinsetzen."""
    game = Battleship(random.Random(5))
    assert game.place(2, 0, 0, True, 2)  # zuerst das U-Boot
    assert game.fleets[2].remaining_lengths() == [5, 4, 3, 3] and game.view(2)["left_ships"] == [5, 4, 3, 3]
    assert not game.place(2, 5, 5, True, 2)  # U-Boot gibt es nur einmal
    assert game.place(2, 0, 3, False)  # ohne Länge: das größte fehlende (5) – senkrecht A4–A8
    assert game.fleets[2].ships[-1] == [(0, 3), (0, 4), (0, 5), (0, 6), (0, 7)]
    ship = game.remove(2, 0, 5)  # antippen = aufnehmen
    assert len(ship) == 5 and game.picked[2] == 5 and game.horizontal[2] is False
    ghost, ok = game.ghost(2, 4, 2)
    assert len(ghost) == 5 and ok and ghost[-1] == (4, 6)  # Vorschau mit dem aufgenommenen Schiff
    assert game.place(2, 4, 2) and game.picked[2] is None
    assert game.remove(2, 9, 9) is None  # leeres Feld: nichts
    r = game.phone_action({"action": "join", "name": "Mia"}, "10.42.0.7")
    r = game.phone_action({"action": "remove", "x": 0, "y": 0}, "10.42.0.7")
    assert r["ok"] and r["removed"] == [[0, 0], [1, 0]] and 2 in r["left_ships"]
    r = game.phone_action({"action": "place", "x": 7, "y": 7, "h": False, "len": 3}, "10.42.0.7")
    assert r["ok"] and [7, 9] in r["own"]["ships"][-1]
    assert game.phone_action({"action": "clear"}, "10.42.0.7")["own"]["ships"] == []
    assert game.set_ready(2) is False
    game.fleets[2].randomize(random.Random(1))
    assert game.set_ready(2) and game.remove(2, *game.fleets[2].ships[0][0]) is None  # bereit: nichts mehr ändern


def test_phone_page_has_preview_and_name():
    from alupc.duel import PHONE_PAGE

    for needle in ('id="jname"', 'id="set"', 'id="dock"', 'action: "remove"', "canPlace", "gok", "gbad"):
        assert needle in PHONE_PAGE, needle
    assert "/anmelden" not in PHONE_PAGE
