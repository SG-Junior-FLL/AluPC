"""Montagsmaler: reihum malen, raten (Umlaute/Großschreibung egal), Punkte, Auflösen, Striche in Stücken."""

import random

from alupc.games import GAMES
from alupc.games_paint import PaintGame, norm


class P:
    def __init__(self, name):
        self.name, self.team = name, 0


def _game(n=3, **opts):
    players = {f"p{i}": P(f"S{i}") for i in range(n)}
    return PaintGame(players, 0.0, random.Random(4), {"runden": 1, "zeit": 60, **opts})


def test_norm_and_registration():
    assert norm("Schlüssel") == norm("schluessel ") == norm("SCHLÜSSEL!") == "schluessel"
    assert GAMES["malen"].cls is PaintGame


def test_round_guessing_and_points():
    g = _game()
    drawer, word = g.drawer, g.word
    assert g.phone(drawer, 1)["ui"] == "draw" and g.phone(drawer, 1)["word"] == word
    guesser = next(pid for pid in g.score if pid != drawer)
    ui = g.phone(guesser, 1)
    assert ui["ui"] == "guess" and word not in ui["hint"] and ui["hint"].count("_") == len(word.replace(" ", ""))
    g.input(guesser, {"guess": "ganz falsch"}, 2)
    assert g.guesses and g.score[guesser] == 0
    g.input(guesser, {"guess": word.upper()}, 5)
    assert g.score[guesser] > 50 and g.score[drawer] == 25 and g.phone(guesser, 6)["big"] == "✅"
    g.input(guesser, {"guess": word}, 6)  # zweimal zählt nicht
    assert g.score[drawer] == 25
    g.input(drawer, {"guess": word}, 6)  # der Maler kann nicht raten
    last = next(pid for pid in g.score if pid not in (drawer, guesser))
    g.input(last, {"guess": word}, 10)
    g.update(10)  # alle haben es → auflösen
    assert g.phase == "aufloesen" and g.phone(last, 10)["big"] == word
    g.update(10 + g.REVEAL)
    assert g.phase == "malen" and g.drawer != drawer and g.word != word and g.strokes == []


def test_strokes_in_pieces_clear_and_timeout():
    g = _game(2)
    d = g.drawer
    g.input(d, {"stroke": {"id": 7, "pts": [[0.1, 0.1], [0.2, 0.2]], "c": "#ef4444", "w": 2}}, 1)
    g.input(d, {"stroke": {"id": 7, "pts": [[0.3, 0.3], [5, -1]]}}, 1)  # Fortsetzung, Werte begrenzt
    assert len(g.strokes) == 1 and g.strokes[0]["pts"][-1] == (1.0, 0.0) and g.strokes[0]["c"] == "#ef4444"
    g.input(d, {"stroke": {"id": 8, "pts": [[0.5, 0.5]], "c": "javascript:", "w": 99}}, 1)
    assert len(g.strokes) == 2 and g.strokes[1]["c"] == "#111827" and g.strokes[1]["w"] == 3
    other = next(pid for pid in g.score if pid != d)
    g.input(other, {"stroke": {"id": 9, "pts": [[0.5, 0.5]]}}, 1)  # nur der Maler malt
    assert len(g.strokes) == 2
    g.input(d, {"clear": 1}, 2)
    assert g.strokes == []
    g.update(61)  # Zeit um
    assert g.phase == "aufloesen"
    g.update(61 + g.REVEAL)
    g.update(200)
    g.update(200 + g.REVEAL)
    assert g.over  # 2 Spieler × 1 Runde


def test_hint_reveals_first_letter_after_half():
    g = _game(2)
    assert not g.hint(1).startswith(g.word[0])
    assert g.hint(31).startswith(g.word[0])


def test_monitor2_draws_paint_game(tmp_path):
    from PySide6.QtWidgets import QApplication

    QApplication.instance() or QApplication([])
    from PySide6.QtGui import QImage, QPainter

    from alupc import game_draw
    from alupc.game_source import GameSource  # noqa: F401  (Modul lädt)

    g = _game(3)
    g.input(g.drawer, {"stroke": {"id": 1, "pts": [[0.1, 0.1], [0.9, 0.9]], "c": "#ef4444", "w": 3}}, 1)
    img = QImage(1280, 720, QImage.Format_RGB32)
    img.fill(0)
    p = QPainter(img)
    from types import SimpleNamespace

    names = {pid: pl.name for pid, pl in g.players.items()}
    c = SimpleNamespace(p=p, w=1280, h=720, now=2.0, fx=SimpleNamespace(born={}),
                        hub=SimpleNamespace(players={pid: SimpleNamespace(name=n, color="#fff", avatar="")
                                                     for pid, n in names.items()}))
    game_draw.DRAW["malen"](c, g, [])
    p.end()
    reds = sum(1 for x in range(0, 1280, 4) for y in range(0, 720, 4) if img.pixelColor(x, y).red() > 200
               and img.pixelColor(x, y).green() < 100)
    assert reds > 50  # der rote Strich ist auf Monitor 2 zu sehen
