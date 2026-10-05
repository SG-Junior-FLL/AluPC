"""Minispiele (1): Snake (Wände sind tödlich), Tipp-Rennen."""

from __future__ import annotations

from collections import deque

from .games_base import Game, clock_text

DIRS = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}


# --------------------------------------------------------------------------- Snake
class SnakeGame(Game):
    W, H = 40, 22
    STEP = 0.12  # Sekunden pro Feld
    RESPAWN = 2.0

    def __init__(self, players, now, rng=None, opts=None):
        super().__init__(players, now, rng, opts)
        self.duration = float(self.opts.get("dauer", 90))
        self.start, self.last_step = now, now
        self.snakes: dict[str, dict] = {}
        self.food: set[tuple[int, int]] = set()
        for pid in self.players:
            self._new(pid, now)
            self._spawn(pid)
        self._fill_food()

    def _new(self, pid, now):
        self.snakes[pid] = {"body": deque(), "dir": (1, 0), "next": (1, 0), "alive": False, "respawn": now,
                            "score": 0}

    def join(self, pid, player, now):
        super().join(pid, player, now)
        self._new(pid, now)
        return True

    def leave(self, pid, now):
        super().leave(pid, now)
        self.snakes.pop(pid, None)

    def remaining(self, now):
        return max(0.0, self.duration - (now - self.start))

    def _occupied(self):
        return {c for s in self.snakes.values() if s["alive"] for c in s["body"]}

    def _spawn(self, pid):
        s = self.snakes[pid]
        busy = self._occupied() | self.food
        for _ in range(200):
            x, y = self.rng.randrange(4, self.W - 4), self.rng.randrange(2, self.H - 2)
            d = (1, 0) if x < self.W / 2 else (-1, 0)  # Wände sind tödlich: immer Richtung Feldmitte starten
            cells = [(x - d[0] * k, y) for k in range(3)]
            if not busy & set(cells):
                break
        s["body"] = deque(cells)
        s["dir"] = s["next"] = d
        s["alive"] = True

    def _fill_food(self):
        want = max(3, len(self.snakes) + 2)
        busy = self._occupied()
        tries = 0
        while len(self.food) < want and tries < 500:
            tries += 1
            c = (self.rng.randrange(self.W), self.rng.randrange(self.H))
            if c not in busy:
                self.food.add(c)

    def input(self, pid, data, now):
        s = self.snakes.get(pid)
        d = DIRS.get(str(data.get("dir", "")))
        if s is None or d is None:
            return
        if (d[0] + s["dir"][0], d[1] + s["dir"][1]) != (0, 0):  # nicht in sich selbst umdrehen
            s["next"] = d

    def update(self, now):
        if self.over:
            return
        if now - self.start >= self.duration:
            self.over = True
            return
        steps = 0
        while now - self.last_step >= self.STEP and steps < 10:
            self.last_step += self.STEP
            steps += 1
            self._step(self.last_step)

    def _step(self, now):
        for pid, s in self.snakes.items():
            if not s["alive"] and now >= s["respawn"]:
                self._spawn(pid)
        heads = {}
        for pid, s in self.snakes.items():
            if not s["alive"]:
                continue
            s["dir"] = s["next"]
            hx, hy = s["body"][0]
            heads[pid] = (hx + s["dir"][0], hy + s["dir"][1])
        bodies = {c for s in self.snakes.values() if s["alive"] for c in list(s["body"])[:-1]}
        crashed = set()
        for pid, head in heads.items():
            others = [p for p, h in heads.items() if h == head and p != pid]
            wall = not (0 <= head[0] < self.W and 0 <= head[1] < self.H)  # Rand = Wand: tödlich
            if wall or head in bodies or others:
                crashed.add(pid)
        for pid, head in heads.items():
            s = self.snakes[pid]
            if pid in crashed:
                s["alive"] = False
                s["respawn"] = now + self.RESPAWN
                self.food |= set(list(s["body"])[::3])  # was übrig bleibt, wird Futter
                s["score"] = s["score"] // 2  # Crash kostet die Hälfte der Punkte
                cell = (min(self.W - 1, max(0, head[0])), min(self.H - 1, max(0, head[1])))
                self.emit(now, "crash", pid=pid, cell=cell, wall=cell != head)
                continue
            s["body"].appendleft(head)
            if head in self.food:
                self.food.discard(head)
                s["score"] += 1
                self.emit(now, "eat", pid=pid, cell=head)
            else:
                s["body"].pop()
        self._fill_food()

    def scores(self):
        return {pid: s["score"] for pid, s in self.snakes.items()}

    def info(self, now):
        return f"noch {clock_text(self.remaining(now))}"

    def phone(self, pid, now):
        s = self.snakes.get(pid)
        if s is None:
            return {"ui": "msg", "big": "👀", "status": "Zuschauen"}
        status = f"{s['score']} Punkte" if s["alive"] else f"Crash! Gleich wieder da · {s['score']} Punkte"
        return {"ui": "pad", "status": status}


# --------------------------------------------------------------------------- Tipp-Rennen
class RaceGame(Game):
    MIN_GAP = 0.045  # schneller als ~22 Tipps/s zählt nicht (gegen Tricks)
    END_DELAY = 4.0
    late_join = False

    def __init__(self, players, now, rng=None, opts=None):
        super().__init__(players, now, rng, opts)
        self.goal = int(self.opts.get("ziel", 60))
        self.progress = {pid: 0 for pid in self.players}
        self.last_tap = {pid: -1.0 for pid in self.players}
        self.finish: list[str] = []
        self.start = now
        self.end_at = None

    def leave(self, pid, now):
        super().leave(pid, now)
        self.progress.pop(pid, None)
        if pid in self.finish:
            self.finish.remove(pid)

    def input(self, pid, data, now):
        if pid not in self.progress or not data.get("tap") or pid in self.finish:
            return
        if now - self.last_tap[pid] < self.MIN_GAP:
            return
        self.last_tap[pid] = now
        self.progress[pid] += 1
        if self.progress[pid] >= self.goal:
            self.finish.append(pid)
            self.emit(now, "finish", pid=pid, place=len(self.finish))
            if self.end_at is None:
                self.end_at = now + self.END_DELAY

    def update(self, now):
        if self.over:
            return
        if self.end_at is not None and (now >= self.end_at or len(self.finish) == len(self.progress)):
            self.over = True
        elif now - self.start > 120:  # niemand tippt mehr
            self.over = True

    def scores(self):
        # Ziel zuerst erreicht zählt mehr als Fortschritt
        bonus = {pid: (len(self.progress) - i) * 1000 for i, pid in enumerate(self.finish)}
        return {pid: p + bonus.get(pid, 0) for pid, p in self.progress.items()}

    def info(self, now):
        return f"{len(self.finish)} im Ziel"

    def phone(self, pid, now):
        if pid not in self.progress:
            return {"ui": "msg", "big": "👀", "status": "Zuschauen – nächste Runde bist du dabei"}
        if pid in self.finish:
            return {"ui": "msg", "big": f"Platz {self.finish.index(pid) + 1}", "status": "Im Ziel!"}
        return {"ui": "tap", "label": "TIPP!", "status": f"{self.progress[pid]} / {self.goal}"}
