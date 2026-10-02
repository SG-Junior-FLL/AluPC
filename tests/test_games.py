"""Minispiele: Spiel-Logik ohne Qt (feste Uhr, fester Zufall)."""

import random

from alupc.games import GAMES, MAX_PLAYERS, GameHub, Player
from alupc.games_classic import RaceGame, ReactionGame, SnakeGame
from alupc.games_party import (BalloonGame, DrawGame, EstimateGame, PongGame, SimonGame, StroopGame, TugGame,
                               format_number, normalize_word, parse_number)


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def players(*names, teams=None):
    out = {}
    for i, n in enumerate(names):
        p = Player(n.lower(), n, "#ef4444", 0.0)
        p.team = (teams[i] if teams else i % 2)
        out[p.pid] = p
    return out


# --------------------------------------------------------------------------- Hilfen
def test_numbers():
    assert parse_number("1.234,5") == 1234.5
    assert parse_number("1.234") == 1234
    assert parse_number("1.5") == 1.5
    assert parse_number("2,5") == 2.5
    assert parse_number("12 000") == 12000
    assert parse_number(42) == 42
    for bad in ("", "abc", "-5", "1e999", "1,2,3", True, None, "9" * 30):
        assert parse_number(bad) is None, bad
    assert format_number(8849, "m") == "8.849 m"
    assert format_number(1969, "Jahr") == "1969"
    assert format_number(753, "v. Chr.") == "753 v. Chr."
    assert format_number(42.195, "km") == "42,2 km" or format_number(42.195, "km") == "42,19 km"
    assert format_number(0.44, "km²") == "0,44 km²"
    assert normalize_word(" Schildkröte! ") == "schildkroete"


def test_question_data_is_sane():
    from alupc.game_data import CATEGORIES, QUESTIONS, WORDS

    assert len(QUESTIONS) >= 250 and len(WORDS) >= 200
    texts = [q[1] for q in QUESTIONS]
    assert len(texts) == len(set(texts))
    for cat, text, answer, unit in QUESTIONS:
        assert cat in CATEGORIES and text.endswith("?") and isinstance(answer, (int, float)) and answer > 0, text
        assert parse_number(str(answer).replace(".", ",")) == answer
    assert len(WORDS) == len(set(WORDS))


# --------------------------------------------------------------------------- Klassiker
def test_snake_moves_eats_and_crashes():
    g = SnakeGame(players("A", "B"), 0.0, random.Random(1))
    a, b = g.snakes["a"], g.snakes["b"]
    a["body"].clear()
    a["body"].extend([(10, 5), (9, 5), (8, 5)])
    a["dir"] = a["next"] = (1, 0)
    b["body"].clear()
    b["body"].extend([(30, 15), (29, 15), (28, 15)])
    b["dir"] = b["next"] = (1, 0)
    g.food = {(11, 5)}
    g.input("a", {"dir": "left"}, 0.0)  # umdrehen geht nicht
    assert a["next"] == (1, 0)
    g.update(g.STEP + 0.001)
    assert a["body"][0] == (11, 5) and len(a["body"]) == 4 and a["score"] == 1
    assert any(e[2] == "eat" for e in g.events)
    b["body"].clear()
    b["body"].extend([(12, 4), (12, 3), (12, 2)])
    b["dir"] = b["next"] = (0, 1)
    g.update(2 * g.STEP + 0.001)  # beide wollen auf (12, 5) → beide crashen
    assert not a["alive"] and not b["alive"] and "Crash" in g.phone("a", 1.0)["status"]
    for k in range(1, 24):
        g.update(2 * g.STEP + k * 0.1)
    assert a["alive"]
    g.update(g.duration + 1)
    assert g.over


def test_reaction_scoring():
    g = ReactionGame(players("A", "B", "C"), 0.0, random.Random(2), {"runden": 2})
    go = g.go_at
    g.input("c", {"tap": 1}, go - 0.5)
    g.input("c", {"tap": 1}, go - 0.4)
    assert g.score["c"] == -1 and g.phone("c", go - 0.3)["status"] == "Zu früh! −1"
    g.update(go)
    assert g.phase == "los" and g.phone("a", go)["tone"] == "go"
    g.input("b", {"tap": 1}, go + 0.2)
    g.input("a", {"tap": 1}, go + 0.3)
    g.update(go + 0.5)
    assert g.phase == "ergebnis" and g.score == {"a": 2, "b": 3, "c": -1}
    assert g.skip(go + 0.6)
    g.update(go + 0.6)
    assert g.round == 2
    g.update(g.go_at)
    g.update(g.go_at + g.GO_WINDOW + 0.01)
    g.update(g.go_at + g.GO_WINDOW + g.RESULT + 0.1)
    assert g.over


def test_race_finish_and_rate_limit():
    g = RaceGame(players("A", "B"), 0.0, opts={"ziel": 20})
    for i in range(20):
        g.input("a", {"tap": 1}, 1 + i * 0.05)
        g.input("a", {"tap": 1}, 1 + i * 0.05 + 0.01)  # zu schnell → zählt nicht
    assert g.progress["a"] == 20 and g.finish == ["a"]
    g.input("b", {"tap": 1}, 2.0)
    assert g.scores()["a"] > g.scores()["b"] == 1
    g.update(g.end_at)
    assert g.over and g.phone("a", 9)["big"] == "Platz 1"


# --------------------------------------------------------------------------- Schätzen
def test_estimate_rounds_and_points():
    mem = set()
    g = EstimateGame(players("A", "B", "C", "D"), 0.0, random.Random(3), {"fragen": 3, "_mem": mem})
    assert len(g.questions) == 3 and len(mem) == 3
    g.questions[0] = ("welt", "Wie hoch ist der Mount Everest?", 8849, "m")
    assert g.phone("a", 0)["ui"] == "number"
    g.input("a", {"num": "8.850"}, 1)  # 1 daneben → Volltreffer
    g.input("a", {"num": "1"}, 2)  # nur die erste Zahl zählt
    g.input("b", {"num": "9000"}, 2)
    g.input("c", {"num": "9000"}, 3)  # gleich weit → gleicher Platz
    g.input("d", {"num": "kaputt"}, 3)
    assert set(g.guesses) == {"a", "b", "c"}
    g.update(g.ASK + 0.1)
    assert g.phase == "aufloesung"
    assert g.gained == {"a": 5 + 3, "b": 3, "c": 3}
    assert g.phone("a", 30)["big"] == "+8" and "8.849 m" in g.phone("a", 30)["status"]
    assert g.phone("d", 30)["big"] == "0"
    g.update(g.ASK + g.REVEAL + 0.2)
    assert g.phase == "frage" and g.index == 1
    g.questions[1] = ("geschichte", "Mondlandung?", 1969, "Jahr")
    g.input("a", {"num": "1970"}, 40)  # bei Jahreszahlen nur genau = Volltreffer
    g.input("b", {"num": "1969"}, 40)
    g.input("c", {"num": "1900"}, 40)
    g.input("d", {"num": "2000"}, 40)
    g.update(41)  # alle haben geschätzt → sofort Auflösung
    assert g.gained == {"b": 8, "a": 3, "d": 2, "c": 1}
    assert g.skip(42) and g.index == 2
    g.skip(43)
    g.skip(44)
    assert g.over
    # zweites Spiel derselben Sitzung: andere Fragen
    g2 = EstimateGame(players("A"), 0.0, random.Random(3), {"fragen": 3, "_mem": mem})
    assert not {q[1] for q in g2.questions} & {q[1] for q in g.questions[2:]}


# --------------------------------------------------------------------------- Farb-Chaos / Simon
def test_stroop_elimination():
    g = StroopGame(players("A", "B", "C"), 0.0, random.Random(5))
    target = g.target
    wrong = next(c for c in g.choices if c != target)
    ph = g.phone("a", 0.1)
    assert ph["ui"] == "buttons" and {b["id"] for b in ph["buttons"]} == set(g.choices)
    g.input("a", {"btn": target}, 0.5)
    g.input("b", {"btn": wrong}, 0.6)
    g.input("b", {"btn": target}, 0.7)  # nur die erste Antwort zählt
    g.update(g.until)  # C hat nicht geantwortet → auch raus
    assert g.alive == {"a"} and g.out_round == {"b": 1, "c": 1}
    assert g.phone("b", 3)["big"] == "RAUS"
    g.update(g.until + 0.01)
    assert g.over and g.scores()["a"] > g.scores()["b"]
    # alle falsch → keiner fliegt
    g = StroopGame(players("A", "B"), 0.0, random.Random(6))
    wrong = next(c for c in g.choices if c != g.target)
    g.input("a", {"btn": wrong}, 0.2)
    g.input("b", {"btn": wrong}, 0.2)
    g.update(0.3)
    assert g.alive == {"a", "b"} and g.all_failed
    assert g.phone("a", 0.4)["status"].startswith("Alle falsch")
    # Zeitfenster wird kürzer
    first = g.window
    g.update(g.until + 0.01)
    assert g.round == 2 and g.window < first


def test_simon_sequence_and_elimination():
    g = SimonGame(players("A", "B", "C"), 0.0, random.Random(7))
    assert len(g.seq) == 3 and g.phase == "zeigen"
    on, gap = g._timing()
    assert g.lit(g.show_start + 0.01) == g.seq[0] and g.lit(g.show_start + on + gap / 2) is None
    assert not g.phone("a", 0.1)["enabled"]
    g.input("a", {"btn": g.seq[0]}, 0.1)  # beim Vorzeigen zählt nichts
    g.update(g.until)
    assert g.phase == "eingabe" and g.phone("a", g.until)["enabled"]
    for x in g.seq:
        g.input("a", {"btn": x}, g.until + 0.1)
    g.input("b", {"btn": (g.seq[0] + 1) % 4}, g.until + 0.1)
    assert "a" in g.done and "b" in g.failed
    g.update(g.until + 99)  # C zu langsam
    assert g.alive == {"a"} and g.phase == "pause"
    g.update(g.until + 0.01)
    assert g.over


def test_simon_all_fail_keeps_everyone_and_sequence():
    g = SimonGame(players("A", "B"), 0.0, random.Random(8))
    seq = list(g.seq)
    g.update(g.until)
    g.update(g.until + 99)  # keiner tippt
    assert g.alive == {"a", "b"} and g.all_failed
    g.update(g.until + 0.01)
    assert g.seq == seq and g.round == 2  # gleiche Folge nochmal
    for _ in range(3):  # wer gar nichts tippt, beendet das Spiel irgendwann
        if g.over:
            break
        g.update(g.until)
        g.update(g.until + 99)
        g.update(g.until + 0.01)
    assert g.over


# --------------------------------------------------------------------------- Tauziehen / Pong / Ballon
def test_tug_teams():
    g = TugGame(players("A", "B", "C", teams=[0, 1, 1]), 0.0, opts={"dauer": 30})
    g.input("a", {"tap": 1}, 0.1)
    g.input("a", {"tap": 1}, 0.12)  # zu schnell
    assert g.pos < 0 and g.taps["a"] == 1
    before = g.pos
    g.input("b", {"tap": 1}, 0.2)
    assert abs((g.pos - before) - g.PULL / 2) < 1e-9  # großes Team: weniger pro Zug
    t = 1.0
    while not g.over:
        g.input("a", {"tap": 1}, t)
        g.update(t)
        t += 0.06
    assert g.winner == 0 and g.scores()["a"] > 1000 > g.scores()["b"]
    assert g.phone("c", t)["color"] == "#3b82f6"


def test_pong_hits_goals_and_win():
    g = PongGame(players("A", "B", "C", teams=[0, 1, 0]), 0.0, random.Random(9), {"punkte": 2})
    assert g.paddles["a"]["slot"] == 0 and g.paddles["c"]["slot"] == 1
    g.input("a", {"y": 0.0}, 0.1)
    g.update(0.5)
    assert g.paddles["a"]["y"] < g.H / 2
    # Ball genau auf Schläger A zufliegen lassen
    pa = g.paddles["a"]
    pa["y"] = pa["target"] = 4.5
    g.paddles["c"]["y"] = g.paddles["c"]["target"] = 1.0  # aus dem Weg
    g.serve_at = 0
    g.bx, g.by, g.vx, g.vy = 3.0, 4.5, -8.0, 0.0
    g.last = 1.0
    for k in range(1, 6):
        g.update(1.0 + k * 0.05)
    assert g.vx > 0 and g.hits["a"] == 1 and any(e[2] == "hit" for e in g.events)
    # Tor für Team Blau
    pa["y"] = pa["target"] = 8.0
    g.bx, g.by, g.vx, g.vy = 1.0, 2.0, -10.0, 0.0
    g.last = 2.0
    for k in range(1, 5):
        g.update(2.0 + k * 0.05)
    assert g.goals == [0, 1]
    g.serve_at = 0
    g.bx, g.by, g.vx, g.vy = 1.0, 2.0, -10.0, 0.0
    g.last = 3.0
    for k in range(1, 5):
        g.update(3.0 + k * 0.05)
    assert g.over and g.winner == 1 and g.scores()["b"] >= 1000


def test_balloon_pump_bank_burst():
    g = BalloonGame(players("A", "B", "C"), 0.0, random.Random(10), {"runden": 1})
    g.limit = 5
    for i in range(3):
        g.input("a", {"pump": 1}, 1 + i * 0.1)
    g.input("a", {"pump": 1}, 1.25)  # zu schnell
    g.input("a", {"stop": 1}, 2)
    assert g.state["a"] == {"pumps": 3, "st": "banked", "last": 1.2} and g.total["a"] == 3
    for i in range(6):
        g.input("b", {"pump": 1}, 1 + i * 0.1)
    assert g.state["b"]["st"] == "burst" and g.state["b"]["pumps"] == 5
    g.input("c", {"pump": 1}, 1)
    g.update(g.until)  # Zeit um → C sichert automatisch
    assert g.total == {"a": 3, "b": 0, "c": 1} and g.phase == "zeigen"
    assert g.phone("b", g.until)["big"] == "+0"
    g.update(g.until + 0.01)
    assert g.over


# --------------------------------------------------------------------------- Malen & Raten
def test_draw_guess_and_strokes():
    g = DrawGame(players("A", "B", "C"), 0.0, random.Random(11), {"zeit": 60})
    drawer = g.drawer
    guessers = g.guessers()
    g.word = "Schildkröte"
    g.reveal_order = list(range(len(g.word)))
    assert g.phone(drawer, 1)["ui"] == "draw" and g.phone(drawer, 1)["word"] == "Schildkröte"
    assert g.phone(guessers[0], 1)["ui"] == "text"
    assert g.hint(1) == "_ _ _ _ _ _ _ _ _ _ _" and g.hint(50).startswith("S c")
    g.input(drawer, {"stroke": {"c": "#ff0000", "w": 8, "p": [0.1, 0.2]}}, 1)
    g.input(drawer, {"pts": [[0.2, 0.3], [5, -1], ["x", 1]]}, 1)
    assert g.strokes[0]["pts"] == [(0.1, 0.2), (0.2, 0.3), (1.0, 0.0)]
    g.input(drawer, {"stroke": {"c": "javascript:alert(1)", "w": 9999, "p": [0.5, 0.5]}}, 1)
    assert g.strokes[1]["c"] == "#111827" and g.strokes[1]["w"] == 40
    g.input(drawer, {"undo": 1}, 1)
    assert len(g.strokes) == 1
    g.input(guessers[0], {"guess": "Schildkrote"}, 2)  # ein Buchstabe falsch → knapp
    assert g.phone(guessers[0], 3)["feedback"] == "Ganz knapp!" and not g.guessed
    g.input(guessers[0], {"guess": "schildkroete"}, 4)
    assert g.guessed == {guessers[0]: 4} and g.score[guessers[0]] == 10
    g.input(guessers[1], {"guess": "Haus"}, 5)
    assert g.feed[-1][2] == "Haus"
    g.input(guessers[1], {"guess": "Schildkröte"}, 6)
    g.update(6)  # alle haben es → Auflösung
    assert g.phase == "wort" and g.score[guessers[1]] == 8 and g.score[drawer] == 6
    g.input(drawer, {"clear": 1}, 7)  # nach der Runde zählt nichts mehr
    assert g.strokes
    g.update(6 + g.REVEAL)
    assert g.turn == 1 and g.drawer != drawer and not g.strokes
    g.leave(g.drawer, 20)  # wer malt, geht → Auflösung
    assert g.phase == "wort"


# --------------------------------------------------------------------------- Spielrunde (Hub)
def test_hub_lobby_start_and_rounds():
    clock = Clock()
    hub = GameHub("reaktion", clock, random.Random(3))
    lena = hub.join("  Lena<script> ")
    lena2 = hub.join("Lena")
    assert lena.name == "Lenascript" and lena2.name == "Lena" and lena.color != lena2.color
    assert hub.join("Lena").name == "Lena 2" and hub.join("").name == "Spieler"
    assert {p.team for p in hub.players.values()} == {0, 1}  # Teams werden gleich aufgefüllt
    state = hub.state_for(lena.pid)
    assert state["joined"] and state["ui"]["status"].startswith("Warte auf den Start am PC")
    assert not hub.state_for("x")["joined"]
    clock.t += hub.LOBBY_TIMEOUT + 1
    hub.seen(lena.pid)
    hub.tick()
    assert list(hub.players) == [lena.pid]
    assert hub.start() and hub.phase == "running"
    assert hub.state_for(lena.pid)["ui"]["big"] == "3"  # 3-2-1
    assert not hub.start()
    hub.input(lena.pid, {"tap": 1})  # während 3-2-1 zählt nichts
    assert hub.game.score[lena.pid] == 0
    clock.t = hub.intro_until
    hub.tick()
    late = hub.join("Mia")
    assert late.pid in hub.game.score
    assert hub.state_for(lena.pid)["ui"]["ui"] == "tap"
    hub.finish()
    assert hub.phase == "over" and hub.state_for(lena.pid)["ui"]["big"].startswith("Platz")
    hub.set_game("gibtsnicht")
    assert hub.game_key == "reaktion" and hub.phase == "lobby"


def test_hub_options_kick_teams_next():
    clock = Clock()
    hub = GameHub("schaetzen", clock, random.Random(4))
    ps = [hub.join(n) for n in ("A", "B", "C", "D")]
    hub.set_option("fragen", 5)
    hub.set_option("fragen", 999)  # nicht erlaubt → bleibt
    hub.set_option("kategorie", "sport")
    assert hub.options["schaetzen"] == {"fragen": 5, "kategorie": "sport"}
    assert hub.start()
    clock.t = hub.intro_until
    hub.tick()
    assert len(hub.game.questions) == 5 and all(q[0] == "sport" for q in hub.game.questions)
    assert hub.next() and hub.game.phase == "aufloesung"
    assert hub.kick(ps[0].pid) and ps[0].pid not in hub.game.score and not hub.kick("x")
    assert not hub.state_for(ps[0].pid)["joined"]
    hub.to_lobby()
    hub.set_game("tauziehen")
    hub.set_team(ps[1].pid, 0)
    hub.set_team(ps[2].pid, 0)
    hub.set_team(ps[3].pid, 0)
    assert hub.start()  # Teams werden vor dem Start ausgeglichen
    teams = [p.team for p in hub.players.values()]
    assert abs(teams.count(0) - teams.count(1)) <= 1
    assert hub.state_for(ps[1].pid)["color"] in ("#ef4444", "#3b82f6")
    hub.finish()
    assert hub.state_for(ps[1].pid)["ui"]["big"] in ("Gewonnen!", "Verloren", "Unentschieden")


def test_hub_full_and_every_game_runs():
    hub = GameHub(clock=Clock())
    assert not hub.start()  # niemand dabei
    for i in range(MAX_PLAYERS):
        assert hub.join(f"P{i}") is not None
    assert hub.join("zu viel") is None
    for key in GAMES:  # jedes Spiel startet und liefert ein Handy-Bedienfeld
        clock = Clock()
        hub = GameHub(key, clock, random.Random(1))
        ps = [hub.join(n) for n in ("A", "B", "C")]
        assert hub.start()
        clock.t = hub.intro_until + 0.5
        hub.tick()
        for p in ps:
            ui = hub.state_for(p.pid)["ui"]
            assert ui["ui"] in ("msg", "tap", "pad", "buttons", "number", "text", "draw", "paddle", "balloon"), key
        hub.finish()
        assert hub.phase == "over" and len(hub.ranking) == 3, key


# --------------------------------------------------------------------------- Bestenliste / Töne
def test_board_over_the_evening():
    clock = Clock()
    hub = GameHub("reaktion", clock, random.Random(1))
    a, b, c = (hub.join(n) for n in ("Lena", "Noah", "Mia"))
    assert hub.board_ranking() == [] and hub.board_games == 0
    hub.start()
    clock.t = hub.intro_until
    hub.tick()
    hub.game.score = {a.pid: 5, b.pid: 5, c.pid: 1}  # Gleichstand auf Platz 1
    hub.finish()
    assert hub.last_award == {"Lena": 10, "Noah": 10, "Mia": 5} and hub.board_games == 1
    # Team-Spiel: Sieger 6, Verlierer 2
    hub.set_game("tauziehen")
    a.team, b.team, c.team = 0, 1, 0
    hub.start()
    clock.t = hub.intro_until
    hub.tick()
    hub.game.pos = -1.0
    hub.tick()
    assert hub.phase == "over" and hub.last_award == {"Lena": 6, "Noah": 2, "Mia": 6}
    assert hub.board == {"Lena": 16, "Noah": 12, "Mia": 11} and hub.board_games == 2
    assert hub.board_ranking() == [("Lena", 16, 1), ("Noah", 12, 2), ("Mia", 11, 3)]
    assert "Gesamt: Platz 2 · 12 Punkte" in hub.state_for(b.pid)["ui"]["status"]
    hub.show_board()
    assert hub.phase == "board" and hub.state_for(a.pid)["ui"]["big"] == "Platz 1"
    assert "nach 2 Spielen" in hub.state_for(a.pid)["ui"]["status"]
    hub.start()
    assert hub.phase == "running"
    hub.show_board()  # läuft ein Spiel, bleibt es beim Spiel
    assert hub.phase == "running"
    hub.reset_board()
    assert hub.board == {} and hub.board_games == 0


def test_game_sounds_follow_the_game():
    from alupc.game_sounds import GameSounds

    clock = Clock()
    hub = GameHub("simon", clock, random.Random(2))
    config = {"games": {"sound": False}, "sounds": {"volume": 50}}  # aus: nichts abspielen, aber mitzählen
    gs = GameSounds(config)
    gs.update(hub)
    p1 = hub.join("Lena")
    hub.join("Noah")
    gs.update(hub)
    assert gs.played[-1] == "blip"  # jemand ist beigetreten
    hub.start()
    for k in range(30):  # 3-2-1 → drei Ticks, dann „los“
        clock.t += 0.1
        gs.update(hub)
    assert gs.played.count("tick") == 3 and gs.played[-1] == "los"
    g = hub.game
    clock.t = g.show_start + 0.01
    hub.tick()
    gs.update(hub)
    assert gs.played[-1] == f"simon{g.seq[0]}"  # Simon: Ton zur leuchtenden Farbe
    clock.t = g.until + 0.01
    hub.tick()
    hub.input(p1.pid, {"btn": (g.seq[0] + 1) % 4})
    gs.update(hub)
    assert "falsch" in gs.played[-2:]
    hub.finish()
    gs.update(hub)
    assert gs.played[-1] == "sieg"


def test_game_sound_files_are_generated(tmp_path, monkeypatch):
    import wave

    from alupc import sounds

    monkeypatch.setattr(sounds, "sounds_dir", lambda: tmp_path)
    for kind in ("tick", "los", "blip", "richtig", "falsch", "raus", "plopp", "treffer", "tor", "sieg", "simon0",
                 "simon3"):
        path = sounds.builtin_path(f"spiel-{kind}")
        with wave.open(str(path)) as w:
            assert w.getframerate() == sounds.RATE and 0.03 < w.getnframes() / w.getframerate() < 2.5, kind
