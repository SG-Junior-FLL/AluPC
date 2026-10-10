"""Minispiele (4): Tic-Tac-Toe – Team Rot (✕) gegen Team Blau (◯).

Alle im Team haben dasselbe Zeichen. Ist das Team dran, tippt jeder auf seinem Handy ein Feld an; sobald alle
getippt haben (oder die Zeit um ist), wird das Feld mit den meisten Stimmen gesetzt. Hat ein Team niemanden,
spielt der PC für dieses Team. Mehrere Runden, die Startseite wechselt jede Runde.
"""

from __future__ import annotations

from .games_base import TEAM_NAMES, Game

LINES = [(0, 1, 2), (3, 4, 5), (6, 7, 8), (0, 3, 6), (1, 4, 7), (2, 5, 8), (0, 4, 8), (2, 4, 6)]
MARKS = ["X", "O"]


def winner_of(cells: list[str]) -> tuple[str, tuple] | None:
    for line in LINES:
        a, b, c = (cells[i] for i in line)
        if a and a == b == c:
            return a, line
    return None


def best_move(cells: list[str], me: str, rng) -> int:
    """Einfacher PC-Gegner: gewinnen, sonst verhindern, sonst Mitte/Ecke/Rest (mit etwas Zufall)."""
    other = "O" if me == "X" else "X"
    free = [i for i, v in enumerate(cells) if not v]
    for mark in (me, other):
        for i in free:
            test = list(cells)
            test[i] = mark
            if winner_of(test):
                return i
    if 4 in free:
        return 4
    corners = [i for i in (0, 2, 6, 8) if i in free]
    return rng.choice(corners or free)


class TicTacToeGame(Game):
    teams = True
    PAUSE = 3.0  # nach einer Runde: Ergebnis zeigen

    def __init__(self, players, now, rng=None, opts=None):
        super().__init__(players, now, rng, opts)
        self.rounds = int(self.opts.get("runden", 3))
        self.think = float(self.opts.get("zeit", 10))
        self.round = 0
        self.wins = [0, 0]
        self.goals = self.wins  # für die Ergebnis-Anzeige („2 : 1“)
        self.unit = "Siege"
        self.winner: int | None = None
        self.points: dict[str, int] = {pid: 0 for pid in self.players}
        self._new_round(now)

    # ---- Runden
    def _new_round(self, now):
        self.round += 1
        self.cells = [""] * 9
        self.turn = (self.round - 1) % 2  # Startseite wechselt
        self.votes: dict[str, int] = {}
        self.turn_start = now
        self.result: str | None = None  # "X", "O" oder "draw"
        self.line: tuple | None = None
        self.result_at = 0.0

    def members(self, team: int) -> list[str]:
        return [pid for pid in self.players if self.team_of(pid) == team]

    def join(self, pid, player, now):
        super().join(pid, player, now)
        self.points.setdefault(pid, 0)
        return True

    def leave(self, pid, now):
        super().leave(pid, now)
        self.votes.pop(pid, None)

    def input(self, pid, data, now):
        if self.result or pid not in self.players or self.team_of(pid) != self.turn:
            return
        try:
            cell = int(data.get("cell", -1))
        except (TypeError, ValueError):
            return
        if 0 <= cell < 9 and not self.cells[cell]:
            self.votes[pid] = cell
            self.emit(now, "vote", pid=pid, cell=cell)

    def time_left(self, now) -> float:
        return max(0.0, self.think - (now - self.turn_start))

    def update(self, now):
        if self.over:
            return
        if self.result:
            if now - self.result_at >= self.PAUSE:
                if self.round >= self.rounds:
                    self._finish()
                else:
                    self._new_round(now)
            return
        team = self.members(self.turn)
        if not team:  # niemand im Team → der PC zieht (kurz „überlegen“)
            if now - self.turn_start >= 1.0:
                self._place(self._pc_move(), now)
            return
        if all(pid in self.votes for pid in team) or self.time_left(now) <= 0:
            self._place(self._chosen(), now)

    def _pc_move(self) -> int:
        return best_move(self.cells, MARKS[self.turn], self.rng)

    def _chosen(self) -> int:
        counts: dict[int, int] = {}
        for cell in self.votes.values():
            if not self.cells[cell]:
                counts[cell] = counts.get(cell, 0) + 1
        if counts:
            top = max(counts.values())
            return self.rng.choice(sorted(c for c, n in counts.items() if n == top))
        return self.rng.choice([i for i, v in enumerate(self.cells) if not v])  # niemand getippt → Zufall

    def _place(self, cell: int, now):
        mark = MARKS[self.turn]
        self.cells[cell] = mark
        self.emit(now, "place", cell=cell, team=self.turn)
        won = winner_of(self.cells)
        if won:
            self.result, self.line = won[0], won[1]
            self.wins[self.turn] += 1
            for pid in self.members(self.turn):
                self.points[pid] = self.points.get(pid, 0) + 1
            self.result_at = now
            self.emit(now, "line", team=self.turn)
            for pid in self.members(self.turn):
                self.emit(now, "correct", pid=pid)
        elif all(self.cells):
            self.result, self.result_at = "draw", now
            self.emit(now, "draw")
        else:
            self.turn = 1 - self.turn
            self.votes = {}
            self.turn_start = now

    def _finish(self):
        self.over = True
        a, b = self.wins
        self.winner = None if a == b else (0 if a > b else 1)

    def skip(self, now) -> bool:
        if self.result:
            self.result_at = now - self.PAUSE
            return True
        return False

    # ---- Anzeige
    def scores(self):
        return {pid: self.wins[self.team_of(pid)] for pid in self.players}

    def info(self, now):
        return (f"Runde {self.round}/{self.rounds} · {TEAM_NAMES[0]} {self.wins[0]} : {self.wins[1]} "
                f"{TEAM_NAMES[1]}")

    def phone(self, pid, now):
        team = self.team_of(pid)
        mine = self.turn == team and not self.result
        if self.result == "draw":
            status = "Unentschieden"
        elif self.result:
            status = "Gewonnen! 🎉" if self.result == MARKS[team] else "Verloren"
        elif mine:
            status = f"Ihr seid dran ({MARKS[team]}) · noch {int(self.time_left(now) + 0.99)} s"
        else:
            status = "Die anderen sind dran …"
        return {"ui": "board", "cells": list(self.cells), "enabled": mine, "vote": self.votes.get(pid, -1),
                "mark": MARKS[team], "line": list(self.line or []), "status": status,
                "rid": self.round}
