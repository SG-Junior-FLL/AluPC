"""Minispiele: Spiel-Logik ohne Qt (feste Uhr, fester Zufall)."""

import random

from alupc.games import GAMES, MAX_PLAYERS, GameHub, Player
from alupc.games_board import TicTacToeGame, best_move, winner_of
from alupc.games_classic import RaceGame, SnakeGame
from alupc.games_party import PongGame, SimonGame
from alupc.games_tetris import TetrisGame


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
# --------------------------------------------------------------------------- Farb-Chaos / Simon
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


# --------------------------------------------------------------------------- Pong / Tetris
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


def test_tetris_same_pieces_for_everyone():
    g = TetrisGame(players("A", "B", "C"), 0.0, random.Random(4))
    seq = [g.piece_at(i) for i in range(14)]
    assert sorted(seq[:7]) == sorted("IOTSZJL") and sorted(seq[7:14]) == sorted("IOTSZJL")  # 7er-Beutel
    assert {b["kind"] for b in g.boards.values()} == {seq[0]}  # alle starten mit demselben Teil
    g.input("a", {"move": "drop"}, 1.0)
    g.input("a", {"move": "drop"}, 1.1)
    g.input("b", {"move": "drop"}, 1.2)
    assert g.boards["a"]["kind"] == seq[2] and g.boards["b"]["kind"] == seq[1]  # jeder in seinem Tempo, gleiche Folge
    assert g.phone("a", 1.2)["next"] == seq[3] and g.phone("c", 1.2)["next"] == seq[1]


def test_tetris_moves_rotate_walls_and_lines():
    g = TetrisGame(players("A"), 0.0, random.Random(1))
    b = g.boards["a"]
    b["kind"], b["rot"], b["x"], b["y"] = "I", 0, 3, 5
    for _ in range(10):
        g.input("a", {"move": "left"}, 0.1)
    assert b["x"] == 0  # bleibt an der Wand
    g.input("a", {"move": "rotate"}, 0.1)
    assert b["rot"] == 1 and g._fits(b, b["x"], b["y"], b["rot"])
    # unterste Reihe bis auf 4 Felder voll → waagrechtes I rein → Reihe weg
    b["cells"][19] = ["#"] * 6 + [""] * 4
    b["kind"], b["rot"], b["x"], b["y"] = "I", 0, 6, 10
    g.input("a", {"move": "drop"}, 0.2)
    assert b["lines"] == 1 and b["cells"][19] == [""] * 10 and b["points"] == 1
    assert any(kind == "lines" for _n, _t, kind, _d in g.events)


def test_tetris_last_one_standing_wins_and_gravity():
    g = TetrisGame(players("A", "B"), 0.0, random.Random(2))
    y0 = g.boards["b"]["y"]
    g.update(g.fall_time(0.0) * 2 + 0.01)
    assert g.boards["b"]["y"] == y0 + 2  # Teile fallen von allein
    assert g.fall_time(100) < g.fall_time(0)  # wird schneller
    t = 1.0
    while g.boards["a"]["alive"]:  # A stapelt bis oben
        g.input("a", {"move": "drop"}, t)
        t += 0.01
    assert g.order_out == ["a"] and g.phone("a", t)["big"] == "Platz 2"
    g.update(t)
    assert g.end_at is not None and not g.over
    g.update(t + g.END_DELAY)
    assert g.over
    sc = g.scores()
    assert sc["b"] > sc["a"]  # wer länger durchhält, gewinnt
    grid = g.view("b")
    assert any(v and v.islower() for row in grid for v in row)  # Schatten: wo das Teil landen würde


def test_tetris_alone_plays_until_out():
    g = TetrisGame(players("A"), 0.0, random.Random(2))
    g.update(30.0)
    assert not g.over and g.boards["a"]["alive"]
    t = 30.0
    while g.boards["a"]["alive"]:
        g.input("a", {"move": "drop"}, t)
        t += 0.01
    g.update(t)
    g.update(t + g.END_DELAY)
    assert g.over


# --------------------------------------------------------------------------- Malen & Raten
# --------------------------------------------------------------------------- Spielrunde (Hub)
def test_hub_lobby_start_and_rounds():
    clock = Clock()
    hub = GameHub("schlangen", clock, random.Random(3))
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
    before = hub.game.snakes[lena.pid]["next"]
    hub.input(lena.pid, {"dir": "up" if before[1] == 0 else "left"})  # während 3-2-1 zählt nichts
    assert hub.game.snakes[lena.pid]["next"] == before
    clock.t = hub.intro_until
    hub.tick()
    late = hub.join("Mia")
    assert late.pid in hub.game.snakes
    assert hub.state_for(lena.pid)["ui"]["ui"] == "pad"
    hub.finish()
    assert hub.phase == "over" and hub.state_for(lena.pid)["ui"]["big"].startswith("Platz")
    hub.set_game("gibtsnicht")
    assert hub.game_key == "schlangen" and hub.phase == "lobby"


def test_hub_options_kick_teams_next():
    clock = Clock()
    hub = GameHub("tictactoe", clock, random.Random(4))
    ps = [hub.join(n) for n in ("A", "B", "C", "D")]
    hub.set_option("runden", 5)
    hub.set_option("runden", 999)  # nicht erlaubt → bleibt
    hub.set_option("zeit", 6)
    assert hub.options["tictactoe"] == {"runden": 5, "zeit": 6}
    assert hub.start()
    clock.t = hub.intro_until
    hub.tick()
    assert hub.game.rounds == 5 and hub.game.think == 6
    assert hub.kick(ps[0].pid) and ps[0].pid not in hub.game.players and not hub.kick("x")
    assert not hub.state_for(ps[0].pid)["joined"]
    hub.to_lobby()
    hub.set_game("pong")
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
            assert ui["ui"] in ("msg", "tap", "pad", "buttons", "board", "paddle", "tetris"), key
        hub.finish()
        assert hub.phase == "over" and len(hub.ranking) == 3, key


# --------------------------------------------------------------------------- Bestenliste / Töne
def test_board_over_the_evening():
    clock = Clock()
    hub = GameHub("rennen", clock, random.Random(1))
    a, b, c = (hub.join(n) for n in ("Lena", "Noah", "Mia"))
    assert hub.board_ranking() == [] and hub.board_games == 0
    hub.start()
    clock.t = hub.intro_until
    hub.tick()
    hub.game.progress = {a.pid: 5, b.pid: 5, c.pid: 1}  # Gleichstand auf Platz 1
    hub.finish()
    assert hub.last_award == {"Lena": 10, "Noah": 10, "Mia": 5} and hub.board_games == 1
    # Team-Spiel: Sieger 6, Verlierer 2
    hub.set_game("tictactoe")
    a.team, b.team, c.team = 0, 1, 0
    hub.start()
    clock.t = hub.intro_until
    hub.tick()
    hub.game.wins = [2, 0]
    hub.game._finish()
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


def test_avatars_and_vibration():
    from alupc.games import AVATARS

    clock = Clock()
    hub = GameHub("tetris", clock, random.Random(3))
    a = hub.join("Lena", "🦊")
    b = hub.join("Noah", "<script>")  # nur Avatare aus der Liste
    assert a.avatar == "🦊" and AVATARS[0] == "🦊" and b.avatar == ""
    assert hub.state_for(a.pid)["avatar"] == "🦊" and hub.state_for(a.pid)["buzz"] is None
    hub.start()
    clock.t = hub.intro_until
    hub.tick()
    for _ in range(40):  # Noah stapelt bis oben → raus → nur Noahs Handy vibriert
        hub.input(b.pid, {"move": "drop"})
    hub.tick()
    nb = hub.state_for(b.pid)["buzz"]
    la = hub.state_for(a.pid)["buzz"]
    assert nb[1] == [200, 100, 200]  # Noah raus
    assert la[1] == [100, 60, 100, 60, 300]  # Lena bleibt als Letzte übrig → Sieg
    first = la[0]
    hub.finish()  # Ende: Sieger (Lena) bekommt die lange Vibration (wieder)
    assert hub.state_for(a.pid)["buzz"][0] >= first and hub.state_for(a.pid)["buzz"][1][-1] == 300


# --------------------------------------------------------------------------- Klassiker
def test_rps_all_against_all():
    from alupc.games_retro import RpsGame

    g = RpsGame(players("A", "B", "C", "D"), 0.0, random.Random(1), {"runden": 2})
    ui = g.phone("a", 0.0)
    assert ui["ui"] == "buttons" and [b["id"] for b in ui["buttons"]] == ["stein", "papier", "schere"]
    g.input("a", {"btn": "stein"}, 1.0)
    g.input("a", {"btn": "papier"}, 1.1)  # nur die erste Wahl zählt
    g.input("b", {"btn": "schere"}, 1.2)
    g.input("c", {"btn": "schere"}, 1.3)
    g.input("x", {"btn": "stein"}, 1.3)  # kein Mitspieler
    g.update(2.0)
    assert g.phase == "waehlen"  # D fehlt noch
    g.update(g.CHOOSE + 0.1)  # Zeit um: D hat nicht gewählt
    assert g.phase == "zeigen" and g.score == {"a": 2, "b": 0, "c": 0, "d": 0}
    assert g.counts() == {"stein": 1, "papier": 0, "schere": 2}
    assert g.phone("d", 9)["status"] == "Zu spät gewählt"
    g.update(g.CHOOSE + g.SHOW + 0.2)
    assert g.round == 2 and g.phase == "waehlen"
    for pid, pick in (("a", "papier"), ("b", "papier"), ("c", "stein"), ("d", "schere")):
        g.input(pid, {"btn": pick}, 20.0)
    g.update(20.0)  # alle gewählt → sofort auflösen
    assert g.phase == "zeigen" and g.gained == {"a": 1, "b": 1, "c": 1, "d": 2}
    g.update(40.0)
    assert g.over


# --------------------------------------------------------------------------- Snake: Wände sind tödlich
def test_snake_wall_kills():
    g = SnakeGame(players("A"), 0.0, random.Random(5))
    a = g.snakes["a"]
    a["body"].clear()
    a["body"].extend([(g.W - 1, 5), (g.W - 2, 5), (g.W - 3, 5)])
    a["dir"] = a["next"] = (1, 0)
    a["score"] = 6
    g.food = set()
    g.update(g.STEP + 0.001)
    assert not a["alive"] and a["score"] == 3  # gegen die Wand → Crash, halbe Punkte
    crash = [e for e in g.events if e[2] == "crash"][-1]
    assert crash[3]["wall"] and crash[3]["cell"] == (g.W - 1, 5)
    for k in range(1, 30):  # kommt wieder – innerhalb des Felds
        g.update(g.STEP + k * 0.1)
    assert a["alive"] and all(0 <= x < g.W and 0 <= y < g.H for x, y in a["body"])


# --------------------------------------------------------------------------- Tic-Tac-Toe
def test_tictactoe_team_votes_and_win():
    ps = players("A", "B", "C", "D", teams=[0, 0, 1, 1])
    g = TicTacToeGame(ps, 0.0, random.Random(1), {"runden": 1, "zeit": 10})
    assert g.turn == 0 and g.phone("a", 0.0)["enabled"] and not g.phone("c", 0.0)["enabled"]
    g.input("c", {"cell": 4}, 0.1)  # nicht dran → zählt nicht
    assert g.votes == {}
    g.input("a", {"cell": 4}, 0.2)
    g.update(0.3)
    assert g.cells[4] == ""  # B hat noch nicht abgestimmt
    g.input("b", {"cell": 4}, 0.4)
    g.update(0.5)
    assert g.cells[4] == "X" and g.turn == 1
    # Team Blau lässt die Zeit ablaufen → Zufallsfeld
    g.update(0.5 + 10.1)
    assert g.cells.count("O") == 1 and g.turn == 0
    # Rot gewinnt über die Diagonale 0-4-8 bzw. eine freie Linie
    free_line = next(line for line in ((0, 4, 8), (2, 4, 6), (1, 4, 7), (3, 4, 5))
                     if all(g.cells[i] in ("", "X") for i in line))
    t = 11.0
    for cell in [i for i in free_line if not g.cells[i]]:
        for pid in ("a", "b"):
            g.input(pid, {"cell": cell}, t)
        g.update(t)
        t += 0.1
        if g.result:
            break
        o_free = [i for i, v in enumerate(g.cells) if not v and i not in free_line]
        for pid in ("c", "d"):
            g.input(pid, {"cell": o_free[0]}, t)
        g.update(t)
        t += 0.1
    assert g.result == "X" and g.wins == [1, 0] and g.line is not None
    assert g.phone("a", t)["status"].startswith("Gewonnen") and g.phone("c", t)["status"] == "Verloren"
    g.update(t + g.PAUSE + 0.1)
    assert g.over and g.winner == 0 and g.scores() == {"a": 1, "b": 1, "c": 0, "d": 0}


def test_tictactoe_pc_plays_empty_team_and_draws():
    g = TicTacToeGame(players("A", teams=[0]), 0.0, random.Random(2), {"runden": 2, "zeit": 6})
    t = 0.0
    while not g.over and t < 200:
        if g.turn == 0 and not g.result:
            free = [i for i, v in enumerate(g.cells) if not v]
            g.input("a", {"cell": free[0]}, t)
        t += 0.5
        g.update(t)
    assert g.over and g.round == 2 and sum(g.wins) <= 2
    assert winner_of(["X", "X", "X", "", "", "", "", "", ""])[0] == "X"
    assert best_move(["O", "O", "", "X", "X", "", "", "", ""], "X", random.Random(0)) == 5  # gewinnen
    assert best_move(["O", "O", "", "X", "", "", "", "", ""], "X", random.Random(0)) == 2  # verhindern

