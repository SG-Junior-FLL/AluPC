"""Minispiele: Spiel-Logik ohne Qt (feste Uhr, fester Zufall)."""

import random

from alupc.games import MAX_PLAYERS, GameHub, RaceGame, ReactionGame, SnakeGame


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def test_snake_moves_eats_and_crashes():
    g = SnakeGame({"a": 1, "b": 1}, 0.0, random.Random(1))
    a = g.snakes["a"]
    a["body"].clear()
    a["body"].extend([(10, 5), (9, 5), (8, 5)])
    a["dir"] = a["next"] = (1, 0)
    g.snakes["b"]["body"].clear()
    g.snakes["b"]["body"].extend([(30, 15), (29, 15), (28, 15)])
    g.snakes["b"]["dir"] = g.snakes["b"]["next"] = (1, 0)
    g.food = {(11, 5)}
    g.input("a", {"dir": "left"}, 0.0)  # umdrehen geht nicht
    assert a["next"] == (1, 0)
    g.update(g.STEP + 0.001)
    assert a["body"][0] == (11, 5) and len(a["body"]) == 4 and a["score"] == 1
    g.input("a", {"dir": "down"}, 0.2)
    g.update(2 * g.STEP + 0.001)
    assert a["body"][0] == (11, 6)
    # Rand: auf der anderen Seite wieder rein
    a["body"].clear()
    a["body"].extend([(g.W - 1, 0), (g.W - 2, 0)])
    a["dir"] = a["next"] = (1, 0)
    g.food = {(5, 20)}
    g.update(3 * g.STEP + 0.001)
    assert a["body"][0] == (0, 0)
    # in eine andere Schlange → Crash, wird Futter, kommt nach RESPAWN wieder
    b = g.snakes["b"]
    b["body"].clear()
    b["body"].extend([(1, 1), (1, 0), (1, 19)])
    b["dir"] = b["next"] = (0, 1)
    t = 4 * g.STEP + 0.001
    g.update(t)
    assert not a["alive"] and b["alive"] and a["score"] == 1
    assert "Crash" in g.status("a", t)
    for k in range(1, 24):  # wie im Betrieb: regelmäßig
        g.update(t + k * 0.1)
    assert a["alive"] and len(a["body"]) >= 3
    g.update(g.DURATION + 1)
    assert g.over


def test_reaction_scoring():
    g = ReactionGame({"a": 1, "b": 1, "c": 1}, 0.0, random.Random(2))
    go = g.go_at
    g.input("c", {"tap": 1}, go - 0.5)  # zu früh
    g.input("c", {"tap": 1}, go - 0.4)  # nur einmal Minuspunkt
    assert g.score["c"] == -1 and "Zu früh" in g.status("c", go - 0.3)
    g.update(go)
    assert g.phase == "los"
    g.input("b", {"tap": 1}, go + 0.2)
    g.input("a", {"tap": 1}, go + 0.3)
    g.input("b", {"tap": 1}, go + 0.35)  # doppelt zählt nicht
    g.input("c", {"tap": 1}, go + 0.4)  # war zu früh → diese Runde raus
    g.update(go + 0.5)  # alle haben getippt → Ergebnis
    assert g.phase == "ergebnis" and g.score == {"a": 2, "b": 3, "c": -1}
    assert [p for p, _ in g.last] == ["b", "a"] and g.status("b", go + 0.6) == "Platz 1"
    t = go + 0.5
    for _ in range(g.ROUNDS - 1):
        t += g.RESULT + 0.01
        g.update(t)
        assert g.phase == "warte"
        t = g.go_at
        g.update(t)
        t += g.GO_WINDOW + 0.01
        g.update(t)  # keiner tippt → nach GO_WINDOW Ergebnis
        assert g.phase == "ergebnis" and g.last == []
    g.update(t + g.RESULT + 0.01)
    assert g.over and g.round == g.ROUNDS


def test_race_finish_and_rate_limit():
    g = RaceGame({"a": 1, "b": 1}, 0.0)
    g.input("a", {"tap": 1}, 1.0)  # Countdown läuft noch
    assert g.progress["a"] == 0 and "Gleich" in g.status("a", 1.0)
    t = g.start
    for i in range(g.GOAL):
        g.input("a", {"tap": 1}, t + i * 0.05)
        g.input("a", {"tap": 1}, t + i * 0.05 + 0.01)  # zu schnell → zählt nicht
    assert g.progress["a"] == g.GOAL and g.finish == ["a"]
    g.input("b", {"tap": 1}, t + 0.5)
    assert g.scores()["a"] > g.scores()["b"] == 1
    g.update(g.end_at - 0.1)
    assert not g.over
    g.update(g.end_at)
    assert g.over and g.status("a", g.end_at) == "Im Ziel! Platz 1"


def test_hub_join_lobby_and_rounds():
    clock = Clock()
    hub = GameHub("reaktion", clock, random.Random(3))
    lena = hub.join("  Lena<script> ")
    lena2 = hub.join("Lena")
    assert lena.name == "Lenascript" and lena2.name == "Lena" and lena.color != lena2.color
    again = hub.join("Lena")
    assert again.name == "Lena 2"
    assert hub.join("").name == "Spieler"
    assert not hub.input("unbekannt", {"tap": 1})
    state = hub.state_for(lena.pid)
    assert state["joined"] and state["phase"] == "lobby" and state["title"] == "Schnellster Finger"
    assert not hub.state_for("x")["joined"]
    # wer sich lange nicht meldet, fliegt aus der Lobby
    clock.t += hub.LOBBY_TIMEOUT + 1
    hub.seen(lena.pid)
    hub.tick()
    assert list(hub.players) == [lena.pid]
    assert hub.start() and hub.phase == "running"
    assert not hub.start()  # zweites Handy startet nicht doppelt
    late = hub.join("Mia")  # steigt in die laufende Runde ein
    assert late.pid in hub.game.score
    assert hub.state_for(lena.pid)["signal"] == "warte"
    hub.game.over = True
    hub.tick()
    assert hub.phase == "over" and hub.state_for(lena.pid)["status"].startswith("Platz")
    hub.set_game("schlangen")
    assert hub.phase == "lobby" and hub.game_key == "schlangen"
    hub.set_game("gibtsnicht")
    assert hub.game_key == "schlangen"
    assert hub.start(restart=True) and isinstance(hub.game, SnakeGame)
    hub.input(late.pid, {"dir": "up"})
    hub.to_lobby()
    assert hub.phase == "lobby" and hub.game is None


def test_hub_full_and_empty():
    hub = GameHub(clock=Clock())
    assert not hub.start()  # niemand dabei
    for i in range(MAX_PLAYERS):
        assert hub.join(f"P{i}") is not None
    assert hub.join("zu viel") is None
