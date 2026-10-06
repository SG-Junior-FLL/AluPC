"""Minispiele (5): Tetris – alle gleichzeitig, jeder bekommt dieselben Teile in derselben Reihenfolge.

Jeder hat sein eigenes Feld (10 × 20). Die Teile kommen für alle aus derselben Folge (7er-Beutel, ein Zufall pro
Spiel) – niemand hat Glück mit den Teilen. Mit der Zeit fallen sie schneller. Wer oben anstößt, ist raus.
Gewonnen hat, wer am längsten durchhält (bei Gleichstand: mehr Reihen). Allein: so lange, wie es geht.
"""

from __future__ import annotations

from .games_base import Game, clock_text

W, H = 10, 20
# Teile als Liste von Drehungen, jede Drehung = Felder (x, y) im 4×4-Kasten
SHAPES = {
    "I": [[(0, 1), (1, 1), (2, 1), (3, 1)], [(2, 0), (2, 1), (2, 2), (2, 3)],
          [(0, 2), (1, 2), (2, 2), (3, 2)], [(1, 0), (1, 1), (1, 2), (1, 3)]],
    "O": [[(1, 0), (2, 0), (1, 1), (2, 1)]] * 4,
    "T": [[(1, 0), (0, 1), (1, 1), (2, 1)], [(1, 0), (1, 1), (2, 1), (1, 2)],
          [(0, 1), (1, 1), (2, 1), (1, 2)], [(1, 0), (0, 1), (1, 1), (1, 2)]],
    "S": [[(1, 0), (2, 0), (0, 1), (1, 1)], [(1, 0), (1, 1), (2, 1), (2, 2)],
          [(1, 1), (2, 1), (0, 2), (1, 2)], [(0, 0), (0, 1), (1, 1), (1, 2)]],
    "Z": [[(0, 0), (1, 0), (1, 1), (2, 1)], [(2, 0), (1, 1), (2, 1), (1, 2)],
          [(0, 1), (1, 1), (1, 2), (2, 2)], [(1, 0), (0, 1), (1, 1), (0, 2)]],
    "J": [[(0, 0), (0, 1), (1, 1), (2, 1)], [(1, 0), (2, 0), (1, 1), (1, 2)],
          [(0, 1), (1, 1), (2, 1), (2, 2)], [(1, 0), (1, 1), (0, 2), (1, 2)]],
    "L": [[(2, 0), (0, 1), (1, 1), (2, 1)], [(1, 0), (1, 1), (1, 2), (2, 2)],
          [(0, 1), (1, 1), (2, 1), (0, 2)], [(0, 0), (1, 0), (1, 1), (1, 2)]],
}
COLORS = {"I": "#22d3ee", "O": "#facc15", "T": "#a855f7", "S": "#22c55e", "Z": "#ef4444", "J": "#3b82f6",
          "L": "#f97316", "#": "#64748b"}
LINE_POINTS = {1: 1, 2: 3, 3: 5, 4: 8}


class TetrisGame(Game):
    late_join = False  # später Kommende hätten einen Vorteil (weniger Zeit zum Verlieren) → zuschauen
    END_DELAY = 2.5

    def __init__(self, players, now, rng=None, opts=None):
        super().__init__(players, now, rng, opts)
        self.fast = self.opts.get("tempo", "normal") == "schnell"
        self.start = now
        self.sequence: list[str] = []
        self.boards: dict[str, dict] = {pid: self._new_board(now) for pid in self.players}
        self.order_out: list[str] = []  # wer in welcher Reihenfolge raus ist
        self.end_at: float | None = None

    # ---- gemeinsame Teile-Folge (für alle gleich)
    def piece_at(self, index: int) -> str:
        while len(self.sequence) <= index:
            bag = list("IOTSZJL")
            self.rng.shuffle(bag)
            self.sequence += bag
        return self.sequence[index]

    def _new_board(self, now):
        b = {"cells": [[""] * W for _ in range(H)], "index": 0, "alive": True, "lines": 0, "points": 0,
             "out_at": None, "last_fall": now}
        self._spawn(b)
        return b

    def _spawn(self, b) -> bool:
        b["kind"] = self.piece_at(b["index"])
        b["index"] += 1
        b["rot"], b["x"], b["y"] = 0, 3, -1  # oberste Reihe des Teils knapp über dem Feld
        return self._fits(b, b["x"], b["y"], b["rot"])

    @staticmethod
    def cells_of(kind, rot, x, y):
        return [(x + cx, y + cy) for cx, cy in SHAPES[kind][rot % 4]]

    def _fits(self, b, x, y, rot) -> bool:
        for cx, cy in self.cells_of(b["kind"], rot, x, y):
            if cx < 0 or cx >= W or cy >= H:
                return False
            if cy >= 0 and b["cells"][cy][cx]:
                return False
        return True

    # ---- Tempo: alle 20 s eine Stufe schneller
    def level(self, now) -> int:
        return int((now - self.start) // 20) + (3 if self.fast else 0)

    def fall_time(self, now) -> float:
        return max(0.08, 0.75 * (0.85 ** self.level(now)))

    # ---- Eingaben
    def input(self, pid, data, now):
        b = self.boards.get(pid)
        if b is None or not b["alive"] or self.over:
            return
        move = str(data.get("move", ""))
        if move in ("left", "right"):
            dx = -1 if move == "left" else 1
            if self._fits(b, b["x"] + dx, b["y"], b["rot"]):
                b["x"] += dx
        elif move == "rotate":
            for kick in (0, -1, 1, -2, 2):  # an der Wand etwas zur Seite schieben
                if self._fits(b, b["x"] + kick, b["y"], b["rot"] + 1):
                    b["x"] += kick
                    b["rot"] = (b["rot"] + 1) % 4
                    break
        elif move == "down":
            if self._fits(b, b["x"], b["y"] + 1, b["rot"]):
                b["y"] += 1
                b["last_fall"] = now
            else:
                self._lock(pid, b, now)
        elif move == "drop":
            while self._fits(b, b["x"], b["y"] + 1, b["rot"]):
                b["y"] += 1
            self._lock(pid, b, now)

    def _lock(self, pid, b, now):
        for cx, cy in self.cells_of(b["kind"], b["rot"], b["x"], b["y"]):
            if cy < 0:  # ragt oben raus → raus
                self._out(pid, b, now)
                return
            b["cells"][cy][cx] = b["kind"]
        full = [y for y in range(H) if all(b["cells"][y])]
        if full:
            b["cells"] = [[""] * W for _ in full] + [row for y, row in enumerate(b["cells"]) if y not in full]
            b["lines"] += len(full)
            b["points"] += LINE_POINTS.get(len(full), 8)
            self.emit(now, "lines", pid=pid, n=len(full))
            if len(full) >= 2:
                self.emit(now, "correct", pid=pid)
        b["last_fall"] = now
        if not self._spawn(b):
            self._out(pid, b, now)

    def _out(self, pid, b, now):
        b["alive"] = False
        b["out_at"] = now
        self.order_out.append(pid)
        self.emit(now, "out", pid=pid)

    # ---- Ablauf
    def alive(self) -> list[str]:
        return [pid for pid, b in self.boards.items() if b["alive"]]

    def update(self, now):
        if self.over:
            return
        if self.end_at is not None:
            if now >= self.end_at:
                self.over = True
            return
        ft = self.fall_time(now)
        for pid, b in list(self.boards.items()):
            steps = 0
            while b["alive"] and now - b["last_fall"] >= ft and steps < 5:
                steps += 1
                if self._fits(b, b["x"], b["y"] + 1, b["rot"]):
                    b["y"] += 1
                    b["last_fall"] += ft
                else:
                    self._lock(pid, b, now)
        left = self.alive()
        if (len(self.boards) > 1 and len(left) <= 1) or not left:
            if left:
                self.emit(now, "win", pid=left[0])
            self.end_at = now + self.END_DELAY

    def leave(self, pid, now):
        super().leave(pid, now)
        self.boards.pop(pid, None)
        if pid in self.order_out:
            self.order_out.remove(pid)

    def survived(self, pid, now=None) -> float:
        b = self.boards[pid]
        end = b["out_at"] if b["out_at"] is not None else (now if now is not None else
                                                             max([x["out_at"] or 0 for x in self.boards.values()]
                                                                 + [self.start]))
        return max(0.0, end - self.start)

    def scores(self):
        """Wer am längsten durchhält: Sekunden (Überlebende bekommen +1), Reihen entscheiden bei Gleichstand."""
        out = {}
        last = max([b["out_at"] or 0 for b in self.boards.values()] + [self.start])
        for pid, b in self.boards.items():
            secs = (b["out_at"] if b["out_at"] is not None else last + 1) - self.start
            out[pid] = int(secs) + b["lines"] / 1000
        return out

    def info(self, now):
        return f"{len(self.alive())} von {len(self.boards)} im Spiel · Stufe {self.level(now) + 1} · " \
               f"{clock_text(now - self.start)}"

    def phone(self, pid, now):
        b = self.boards.get(pid)
        if b is None:
            return {"ui": "msg", "big": "👀", "status": "Zuschauen – nächste Runde bist du dabei"}
        if not b["alive"]:
            place = len(self.boards) - self.order_out.index(pid) if pid in self.order_out else 1
            return {"ui": "msg", "big": f"Platz {place}", "tone": "bad" if place > 1 else "good",
                    "status": f"Durchgehalten: {clock_text(self.survived(pid))} · {b['lines']} Reihen"}
        if self.end_at is not None:
            return {"ui": "msg", "big": "🏆", "tone": "good", "status": "Du hast am längsten durchgehalten!"}
        return {"ui": "tetris", "status": f"{b['lines']} Reihen · noch {len(self.alive())} im Spiel",
                "next": self.piece_at(b["index"]), "color": COLORS[b["kind"]]}

    # ---- für die Anzeige
    def view(self, pid) -> list[list[str]]:
        """Feld mit dem fallenden Teil und seinem „Schatten“ (Kleinbuchstabe = wo es landen würde)."""
        b = self.boards[pid]
        grid = [row[:] for row in b["cells"]]
        if b["alive"]:
            gy = b["y"]
            while self._fits(b, b["x"], gy + 1, b["rot"]):
                gy += 1
            for cx, cy in self.cells_of(b["kind"], b["rot"], b["x"], gy):
                if 0 <= cy < H and not grid[cy][cx]:
                    grid[cy][cx] = b["kind"].lower()
            for cx, cy in self.cells_of(b["kind"], b["rot"], b["x"], b["y"]):
                if 0 <= cy < H:
                    grid[cy][cx] = b["kind"]
        return grid
