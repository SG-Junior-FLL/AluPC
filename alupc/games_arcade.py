"""Minispiele (6): Retro – Space Invaders, Flappy Bird, Vier gewinnt.

* Space Invaders: alle zusammen gegen die Aliens. Jeder hat ein Raumschiff unten (Finger ziehen) und schießt
  (FEUER). Wer getroffen wird, verliert ein Leben; ohne Leben ist man raus. Welle geschafft → die nächste ist
  schneller. Erreichen die Aliens den Boden, ist das Spiel für alle vorbei.
* Flappy Bird: jeder ist ein Vogel, Tippen = flattern. Alle fliegen durch dieselben Röhren – wer am längsten
  durchhält (die meisten Röhren), gewinnt.
* Vier gewinnt: Team Rot gegen Team Blau wie Tic-Tac-Toe – Spalte antippen, die meistgewählte Spalte zählt.
"""

from __future__ import annotations

import math

from .games_base import TEAM_NAMES, Game, clock_text
from .games_board import MARKS, TicTacToeGame


def _num(value, default=None):
    try:
        v = float(value)
    except (TypeError, ValueError):
        return default
    return v if math.isfinite(v) else default


# --------------------------------------------------------------------------- Space Invaders
class InvadersGame(Game):
    W, H = 16.0, 12.0
    SHIP_Y, SHIP_W = 11.2, 0.9
    SHIP_SPEED = 16.0
    SHOT_SPEED, ALIEN_SHOT_SPEED = 15.0, 6.5
    COOLDOWN = 0.32
    ROWS, COLS = 4, 9
    LIVES = 3
    SAFE = 2.0  # nach einem Treffer: so lange unverwundbar
    ROW_POINTS = (30, 20, 20, 10)

    def __init__(self, players, now, rng=None, opts=None):
        super().__init__(players, now, rng, opts)
        self.duration = float(self.opts.get("dauer", 180))
        self.start = self.last = now
        self.ships: dict[str, dict] = {}
        self.shots: list[dict] = []  # Schüsse der Spieler {pid, x, y}
        self.bombs: list[dict] = []  # Schüsse der Aliens {x, y}
        self.wave = 0
        self.lost = False  # Aliens unten angekommen
        for i, pid in enumerate(self.players):
            self._new_ship(pid, i, now)
        self._new_wave(now)

    def _new_ship(self, pid, index, now):
        x = self.W / 2 + ((index % 7) - 3) * 1.4
        self.ships[pid] = {"x": x, "target": x, "lives": self.LIVES, "score": 0, "safe_until": now + 1.0,
                           "cool": now, "hits": 0}

    def _new_wave(self, now):
        self.wave += 1
        self.aliens = [{"x": 2.0 + c * 1.25, "y": 1.6 + r * 0.95, "row": r, "alive": True}
                       for r in range(self.ROWS) for c in range(self.COLS)]
        self.dir = 1.0
        self.wave_at = now
        self.next_bomb = now + 1.5
        self.bombs = []
        if self.wave > 1:
            self.emit(now, "go")

    def join(self, pid, player, now):
        super().join(pid, player, now)
        self._new_ship(pid, len(self.ships), now)
        return True

    def leave(self, pid, now):
        super().leave(pid, now)
        self.ships.pop(pid, None)

    def alive_ships(self):
        return {pid: s for pid, s in self.ships.items() if s["lives"] > 0}

    def remaining(self, now):
        return max(0.0, self.duration - (now - self.start))

    def input(self, pid, data, now):
        s = self.ships.get(pid)
        if s is None or s["lives"] <= 0:
            return
        x = _num(data.get("x"))
        if x is not None:
            half = self.SHIP_W / 2
            s["target"] = half + max(0.0, min(1.0, x)) * (self.W - 2 * half)
        if data.get("fire") and now >= s["cool"] and not any(sh["pid"] == pid for sh in self.shots):
            s["cool"] = now + self.COOLDOWN
            self.shots.append({"pid": pid, "x": s["x"], "y": self.SHIP_Y - 0.4})
            self.emit(now, "shot", pid=pid)

    def _alien_speed(self) -> float:
        left = sum(1 for a in self.aliens if a["alive"]) or 1
        return (0.9 + 0.25 * (self.wave - 1)) * (1 + 2.2 * (1 - left / (self.ROWS * self.COLS)))

    def update(self, now):
        if self.over:
            return
        dt_total = min(0.1, max(0.0, now - self.last))
        self.last = now
        steps = max(1, int(dt_total / 0.01) + 1)
        dt = dt_total / steps
        for _ in range(steps):
            self._step(dt, now)
            if self.over:
                return
        if self.remaining(now) <= 0 or not self.alive_ships():
            self.over = True

    def _step(self, dt, now):
        for s in self.ships.values():
            diff = s["target"] - s["x"]
            s["x"] += max(-self.SHIP_SPEED * dt, min(self.SHIP_SPEED * dt, diff))
        # Aliens: hin und her, am Rand eine Reihe tiefer
        alive = [a for a in self.aliens if a["alive"]]
        if not alive:
            self._new_wave(now)
            return
        dx = self.dir * self._alien_speed() * dt
        if any(a["x"] + dx < 0.6 or a["x"] + dx > self.W - 0.6 for a in alive):
            self.dir = -self.dir
            for a in alive:
                a["y"] += 0.45
        else:
            for a in alive:
                a["x"] += dx
        if max(a["y"] for a in alive) >= self.SHIP_Y - 0.6:
            self.lost = True
            self.over = True
            self.emit(now, "crash")
            return
        # Aliens werfen Bomben (aus der untersten Reihe einer Spalte)
        if now >= self.next_bomb:
            lowest: dict[int, dict] = {}
            for a in alive:
                col = round((a["x"] - alive[0]["x"]) / 1.25)
                if col not in lowest or a["y"] > lowest[col]["y"]:
                    lowest[col] = a
            a = self.rng.choice(list(lowest.values()))
            self.bombs.append({"x": a["x"], "y": a["y"] + 0.4})
            players = max(1, len(self.alive_ships()))
            self.next_bomb = now + max(0.25, (1.3 - 0.1 * self.wave) / (1 + 0.25 * (players - 1)))
        # Schüsse der Spieler
        for sh in list(self.shots):
            sh["y"] -= self.SHOT_SPEED * dt
            if sh["y"] < 0:
                self.shots.remove(sh)
                continue
            for a in alive:
                if a["alive"] and abs(a["x"] - sh["x"]) < 0.5 and abs(a["y"] - sh["y"]) < 0.4:
                    a["alive"] = False
                    self.shots.remove(sh)
                    s = self.ships.get(sh["pid"])
                    if s is not None:
                        s["score"] += self.ROW_POINTS[a["row"]]
                        s["hits"] += 1
                    self.emit(now, "hit", pid=sh["pid"], x=a["x"], y=a["y"])
                    break
        # Bomben der Aliens
        for b in list(self.bombs):
            b["y"] += self.ALIEN_SHOT_SPEED * dt
            if b["y"] > self.H:
                self.bombs.remove(b)
                continue
            for pid, s in self.alive_ships().items():
                if now >= s["safe_until"] and abs(s["x"] - b["x"]) < self.SHIP_W / 2 + 0.1 and \
                        abs(self.SHIP_Y - b["y"]) < 0.35:
                    s["lives"] -= 1
                    s["safe_until"] = now + self.SAFE
                    self.bombs.remove(b)
                    self.emit(now, "crash", pid=pid, x=s["x"], y=self.SHIP_Y)
                    if s["lives"] <= 0:
                        self.emit(now, "out", pid=pid)
                    break

    def scores(self):
        return {pid: self.ships.get(pid, {}).get("score", 0) for pid in self.players}

    def info(self, now):
        left = sum(1 for a in self.aliens if a["alive"])
        return (f"Welle {self.wave} · {left} Aliens · {len(self.alive_ships())} Schiffe · "
                f"noch {clock_text(self.remaining(now))}")

    def phone(self, pid, now):
        s = self.ships.get(pid)
        if s is None:
            return {"ui": "msg", "big": "👀", "status": "Zuschauen"}
        if s["lives"] <= 0:
            return {"ui": "msg", "big": "RAUS", "tone": "bad", "status": f"{s['score']} Punkte – die anderen kämpfen weiter"}
        return {"ui": "shooter", "rid": self.wave, "x": (s["x"] - self.SHIP_W / 2) / (self.W - self.SHIP_W),
                "status": f"{'♥' * s['lives']}  ·  {s['score']} Punkte  ·  Welle {self.wave}"}


# --------------------------------------------------------------------------- Flappy Bird
class FlappyGame(Game):
    late_join = False  # später Kommende hätten einen Vorteil → zuschauen
    W, H = 16.0, 9.0
    BIRD_X, R = 4.0, 0.32
    GRAVITY, FLAP = 24.0, -8.0
    PIPE_W, SPACING = 1.3, 4.6
    LEAD = 2.0  # erst schweben, dann geht es los
    END_DELAY = 2.0

    def __init__(self, players, now, rng=None, opts=None):
        super().__init__(players, now, rng, opts)
        self.gap = 2.6 if self.opts.get("roehren", "normal") == "eng" else 3.2
        self.start = self.last = now
        self.go_at = now + self.LEAD
        self.dist = 0.0  # wie weit die Welt schon gescrollt ist
        self.pipes: list[dict] = []  # {x (Welt), gap_y (Mitte)}
        self.birds = {pid: {"y": self.H / 2, "vy": 0.0, "alive": True, "passed": 0, "out_at": None}
                      for pid in self.players}
        self.end_at: float | None = None
        while len(self.pipes) < 6:
            self._add_pipe()

    def _add_pipe(self):
        x = (self.pipes[-1]["x"] + self.SPACING) if self.pipes else self.W + 2.0
        last = self.pipes[-1]["gap_y"] if self.pipes else self.H / 2
        margin = self.gap / 2 + 0.6
        y = max(margin, min(self.H - margin, last + self.rng.uniform(-2.2, 2.2)))
        self.pipes.append({"x": x, "gap_y": y})

    def speed(self, now) -> float:
        return 3.6 + min(2.4, max(0.0, now - self.go_at) * 0.03)

    def input(self, pid, data, now):
        b = self.birds.get(pid)
        if b is None or not b["alive"] or not data.get("tap"):
            return
        b["vy"] = self.FLAP
        self.emit(now, "flap", pid=pid)

    def update(self, now):
        if self.over:
            return
        dt_total = min(0.1, max(0.0, now - self.last))
        self.last = now
        if self.end_at is not None:
            if now >= self.end_at:
                self.over = True
            return
        if now < self.go_at:  # schweben
            for b in self.birds.values():
                b["y"] = self.H / 2 + math.sin((now - self.start) * 4) * 0.25
            return
        steps = max(1, int(dt_total / 0.01) + 1)
        dt = dt_total / steps
        for _ in range(steps):
            self._step(dt, now)
        if not any(b["alive"] for b in self.birds.values()):
            self.end_at = now + self.END_DELAY

    def _step(self, dt, now):
        self.dist += self.speed(now) * dt
        while self.pipes and self.pipes[0]["x"] - self.dist < -self.PIPE_W:
            self.pipes.pop(0)
        while len(self.pipes) < 6:
            self._add_pipe()
        for pid, b in self.birds.items():
            if not b["alive"]:
                continue
            b["vy"] = min(14.0, b["vy"] + self.GRAVITY * dt)
            b["y"] += b["vy"] * dt
            if b["y"] < self.R:
                b["y"], b["vy"] = self.R, 0.0
            dead = b["y"] > self.H - self.R
            for pipe in self.pipes:
                px = pipe["x"] - self.dist
                if abs(px - self.BIRD_X) < self.PIPE_W / 2 + self.R and \
                        abs(b["y"] - pipe["gap_y"]) > self.gap / 2 - self.R:
                    dead = True
            total = self._passed_total()
            if total > b["passed"]:
                b["passed"] = total
                self.emit(now, "score", pid=pid)
            if dead:
                b["alive"] = False
                b["out_at"] = now
                self.emit(now, "crash", pid=pid, y=b["y"])

    def _passed_total(self) -> int:
        """Röhren, deren rechte Kante schon links vom Vogel ist (für alle gleich – alle fliegen dieselbe Strecke)."""
        x_bird = self.dist + self.BIRD_X - self.R
        first = self.W + 2.0
        return max(0, int(math.floor((x_bird - self.PIPE_W / 2 - first) / self.SPACING)) + 1)

    def survived(self, pid, now) -> float:
        b = self.birds.get(pid)
        if b is None:
            return 0.0
        end = b["out_at"] if b["out_at"] is not None else now
        return max(0.0, end - self.go_at)

    def scores(self):
        return {pid: self.birds.get(pid, {}).get("passed", 0) for pid in self.players}

    def info(self, now):
        alive = sum(1 for b in self.birds.values() if b["alive"])
        best = max((b["passed"] for b in self.birds.values()), default=0)
        return f"{alive} fliegen noch · Rekord {best} Röhren"

    def phone(self, pid, now):
        b = self.birds.get(pid)
        if b is None:
            return {"ui": "msg", "big": "👀", "status": "Zuschauen – nächste Runde bist du dabei"}
        if not b["alive"]:
            return {"ui": "msg", "big": f"{b['passed']}", "tone": "bad",
                    "status": f"Abgestürzt – {b['passed']} Röhren"}
        if now < self.go_at:
            return {"ui": "tap", "label": "FLATTERN", "tone": "wait", "status": "Gleich geht's los – dann tippen!"}
        return {"ui": "tap", "label": "FLATTERN", "tone": "go", "status": f"{b['passed']} Röhren"}


# --------------------------------------------------------------------------- Vier gewinnt
COLS4, ROWS4 = 7, 6


def winner4(cells: list[str]) -> tuple[str, tuple] | None:
    for r in range(ROWS4):
        for c in range(COLS4):
            mark = cells[r * COLS4 + c]
            if not mark:
                continue
            for dr, dc in ((0, 1), (1, 0), (1, 1), (1, -1)):
                line = []
                for k in range(4):
                    rr, cc = r + dr * k, c + dc * k
                    if not (0 <= rr < ROWS4 and 0 <= cc < COLS4) or cells[rr * COLS4 + cc] != mark:
                        break
                    line.append(rr * COLS4 + cc)
                if len(line) == 4:
                    return mark, tuple(line)
    return None


def drop_row(cells: list[str], col: int) -> int | None:
    """Unterste freie Reihe in einer Spalte (None = voll)."""
    for r in range(ROWS4 - 1, -1, -1):
        if not cells[r * COLS4 + col]:
            return r
    return None


def best_column(cells: list[str], me: str, rng) -> int:
    """Einfacher PC-Gegner: gewinnen, sonst verhindern, keine Vorlage geben, sonst eher Mitte."""
    other = "O" if me == "X" else "X"
    free = [c for c in range(COLS4) if drop_row(cells, c) is not None]

    def after(col, mark):
        test = list(cells)
        test[drop_row(cells, col) * COLS4 + col] = mark
        return test

    for mark in (me, other):
        for col in free:
            if winner4(after(col, mark)):
                return col
    safe = []
    for col in free:
        test = after(col, me)
        if not any(winner4(after_c) for after_c in
                   (_with(test, c2, other) for c2 in range(COLS4) if drop_row(test, c2) is not None)):
            safe.append(col)
    pool = safe or free
    weights = [4 - abs(3 - c) for c in pool]
    return rng.choices(pool, weights=weights)[0]


def _with(cells, col, mark):
    test = list(cells)
    test[drop_row(cells, col) * COLS4 + col] = mark
    return test


class ConnectFourGame(TicTacToeGame):
    PAUSE = 3.5

    def _new_round(self, now):
        super()._new_round(now)
        self.cells = [""] * (COLS4 * ROWS4)

    def input(self, pid, data, now):
        if self.result or pid not in self.players or self.team_of(pid) != self.turn:
            return
        col = _num(data.get("col"))
        if col is None:
            return
        col = int(col)
        if 0 <= col < COLS4 and drop_row(self.cells, col) is not None:
            self.votes[pid] = col
            self.emit(now, "vote", pid=pid, cell=col)

    def _pc_move(self) -> int:
        return best_column(self.cells, MARKS[self.turn], self.rng)

    def _chosen(self) -> int:
        counts: dict[int, int] = {}
        for col in self.votes.values():
            if drop_row(self.cells, col) is not None:
                counts[col] = counts.get(col, 0) + 1
        if counts:
            top = max(counts.values())
            return self.rng.choice(sorted(c for c, n in counts.items() if n == top))
        return self.rng.choice([c for c in range(COLS4) if drop_row(self.cells, c) is not None])

    def _place(self, col: int, now):
        row = drop_row(self.cells, col)
        if row is None:
            return
        cell = row * COLS4 + col
        mark = MARKS[self.turn]
        self.cells[cell] = mark
        self.emit(now, "place", cell=cell, team=self.turn)
        won = winner4(self.cells)
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

    def phone(self, pid, now):
        team = self.team_of(pid)
        mine = self.turn == team and not self.result
        if self.result == "draw":
            status = "Unentschieden"
        elif self.result:
            status = "Gewonnen! 🎉" if self.result == MARKS[team] else "Verloren"
        elif mine:
            status = f"Ihr seid dran · noch {int(self.time_left(now) + 0.99)} s"
        else:
            status = f"{TEAM_NAMES[self.turn]} ist dran …"
        full = [drop_row(self.cells, c) is None for c in range(COLS4)]
        return {"ui": "connect4", "cells": list(self.cells), "enabled": mine, "vote": self.votes.get(pid, -1),
                "mark": MARKS[team], "line": list(self.line or []), "full": full, "status": status,
                "rid": self.round}
