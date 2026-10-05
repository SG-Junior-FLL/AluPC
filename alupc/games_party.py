"""Minispiele (2): Simon sagt, Pong, Ballon."""

from __future__ import annotations

import math

from .games_base import TEAM_COLORS, TEAM_NAMES, Game, clock_text


# --------------------------------------------------------------------------- Ausscheiden (Grundlage für Simon)
class EliminationGame(Game):
    """Alle spielen gleichzeitig – wer einen Fehler macht, ist raus. Machen ALLE Übrigen einen Fehler, fliegt
    keiner (sonst gäbe es keinen Sieger). Wer raus ist, bleibt raus."""

    late_join = False
    MAX_ROUNDS = 80

    def __init__(self, players, now, rng=None, opts=None):
        super().__init__(players, now, rng, opts)
        self.alive = set(self.players)
        self.started_with = len(self.alive)
        self.out_round: dict[str, int] = {}
        self.round = 0
        self.idle_rounds = 0
        self.last_out: set[str] = set()
        self.all_failed = False

    def leave(self, pid, now):
        super().leave(pid, now)
        self.alive.discard(pid)
        self.out_round.pop(pid, None)

    def _eliminate(self, failed: set, answered: int, now: float) -> None:
        self.idle_rounds = 0 if answered else self.idle_rounds + 1
        self.all_failed = bool(failed) and failed >= self.alive and len(self.alive) > 1
        if self.all_failed:
            self.last_out = set()
            self.emit(now, "allfail")
        else:
            self.last_out = failed & self.alive
            for pid in self.last_out:
                self.out_round[pid] = self.round
                self.emit(now, "out", pid=pid)
            self.alive -= failed

    def _finished(self) -> bool:
        if not self.alive or self.round >= self.MAX_ROUNDS or self.idle_rounds >= 3:
            return True
        return self.started_with > 1 and len(self.alive) <= 1

    def scores(self):
        return {pid: (self.round + 1 if pid in self.alive else self.out_round.get(pid, 0)) for pid in self.players}

    def _out_msg(self, pid):
        return {"ui": "msg", "big": "RAUS", "tone": "bad",
                "status": f"Runde {self.out_round.get(pid, 0)} – noch {len(self.alive)} im Spiel"}


# --------------------------------------------------------------------------- Simon sagt
SIMON_PADS = [("grün", "#22c55e"), ("rot", "#ef4444"), ("gelb", "#facc15"), ("blau", "#3b82f6")]


class SimonGame(EliminationGame):
    LEAD = 1.0
    PAUSE = 1.6

    def __init__(self, players, now, rng=None, opts=None):
        super().__init__(players, now, rng, opts)
        self.fast = self.opts.get("tempo", "normal") != "normal"
        self.seq = [self.rng.randrange(4) for _ in range(2)]
        self._next(now, grow=True)

    def _timing(self):
        on = max(0.22, (0.42 if self.fast else 0.55) * 0.97 ** self.round)
        return on, on * 0.35

    def _next(self, now, grow):
        self.round += 1
        if grow:
            self.seq.append(self.rng.randrange(4))
        on, gap = self._timing()
        self.phase = "zeigen"
        self.show_start = now + self.LEAD
        self.until = self.show_start + len(self.seq) * (on + gap)
        self.progress = {pid: 0 for pid in self.alive}
        self.done: set[str] = set()
        self.failed: set[str] = set()
        self.emit(now, "show")

    def lit(self, now) -> int | None:
        """Welches Feld leuchtet gerade (beim Vorzeigen)?"""
        if self.phase != "zeigen" or now < self.show_start:
            return None
        on, gap = self._timing()
        t = now - self.show_start
        k = int(t // (on + gap))
        if k < len(self.seq) and t - k * (on + gap) < on:
            return self.seq[k]
        return None

    def input(self, pid, data, now):
        if self.phase != "eingabe" or pid not in self.alive or pid in self.done or pid in self.failed:
            return
        try:
            pad = int(data.get("btn"))
        except (TypeError, ValueError):
            return
        if pad == self.seq[self.progress[pid]]:
            self.progress[pid] += 1
            if self.progress[pid] >= len(self.seq):
                self.done.add(pid)
        else:
            self.failed.add(pid)
            self.emit(now, "wrong", pid=pid)

    def update(self, now):
        if self.over:
            return
        if self.phase == "zeigen" and now >= self.until:
            self.phase = "eingabe"
            self.until = now + 3.0 + 0.9 * len(self.seq)
            self.emit(now, "go")
        elif self.phase == "eingabe" and (now >= self.until or self.alive <= self.done | self.failed):
            failed = self.alive - self.done
            answered = sum(1 for p in self.alive if self.progress.get(p, 0) or p in self.failed)
            self._eliminate(failed, answered, now)
            self.phase = "pause"
            self.until = now + self.PAUSE
        elif self.phase == "pause" and now >= self.until:
            if self._finished():
                self.over = True
            else:
                self._next(now, grow=not self.all_failed)

    def info(self, now):
        return f"Runde {self.round} · {len(self.seq)} Farben · {len(self.alive)} im Spiel"

    def phone(self, pid, now):
        if pid not in self.players:
            return {"ui": "msg", "big": "👀", "status": "Zuschauen"}
        if pid not in self.alive:
            return self._out_msg(pid)
        pads = [{"id": str(i), "label": "", "color": c} for i, (_n, c) in enumerate(SIMON_PADS)]
        if self.phase == "zeigen":
            return {"ui": "buttons", "layout": "simon", "rid": self.round, "enabled": False, "buttons": pads,
                    "status": "Schau auf den Bildschirm!"}
        if self.phase == "eingabe":
            if pid in self.done:
                return {"ui": "msg", "big": "✓", "tone": "good", "status": "Geschafft – warte auf die anderen"}
            if pid in self.failed:
                return {"ui": "msg", "big": "✗", "tone": "bad", "status": "Falsch …"}
            return {"ui": "buttons", "layout": "simon", "rid": self.round, "enabled": True, "buttons": pads,
                    "status": f"Nachtippen! {self.progress.get(pid, 0)} / {len(self.seq)}"}
        ok = pid not in self.last_out
        return {"ui": "msg", "big": "✓" if ok else "RAUS", "tone": "good" if ok else "bad",
                "status": "Alle falsch – keiner fliegt raus!" if self.all_failed else f"noch {len(self.alive)} im Spiel"}


# --------------------------------------------------------------------------- Pong
class PongGame(Game):
    teams = True
    W, H = 16.0, 9.0
    PH, PW, R = 2.0, 0.32, 0.22  # Schläger-Höhe/-Breite, Ball-Radius
    PER_TEAM = 3
    SPEED, MAX_SPEED = 8.0, 20.0

    def __init__(self, players, now, rng=None, opts=None):
        super().__init__(players, now, rng, opts)
        self.to_win = int(self.opts.get("punkte", 7))
        self.goals = [0, 0]
        self.paddles: dict[str, dict] = {}
        self.hits = {pid: 0 for pid in self.players}
        for pid in self.players:
            self._place(pid)
        self.start = self.last = now
        self.trail: list[tuple[float, float]] = []
        self.winner: int | None = None
        self._serve(now, self.rng.choice((-1, 1)))

    def _place(self, pid):
        team = self.team_of(pid)
        used = {p["slot"] for p in self.paddles.values() if p["team"] == team}
        slot = next((s for s in range(self.PER_TEAM) if s not in used), None)
        if slot is None:
            return  # Team voll → zuschauen
        x = 0.7 + slot * 2.4
        self.paddles[pid] = {"team": team, "slot": slot, "x": x if team == 0 else self.W - x,
                             "y": self.H / 2, "target": self.H / 2}

    def join(self, pid, player, now):
        super().join(pid, player, now)
        self.hits.setdefault(pid, 0)
        self._place(pid)
        return True

    def leave(self, pid, now):
        super().leave(pid, now)
        self.paddles.pop(pid, None)

    def _serve(self, now, direction):
        self.bx, self.by = self.W / 2, self.H / 2
        self.vx = self.vy = 0.0
        self.serve_at = now + 1.2
        self.serve_dir = direction
        self.speed = self.SPEED
        self.trail = []

    def input(self, pid, data, now):
        p = self.paddles.get(pid)
        if p is None or "y" not in data:
            return
        try:
            y = float(data["y"])
        except (TypeError, ValueError):
            return
        if math.isfinite(y):
            half = self.PH / 2
            p["target"] = half + max(0.0, min(1.0, y)) * (self.H - 2 * half)

    def update(self, now):
        if self.over:
            return
        dt_total = min(0.1, max(0.0, now - self.last))
        self.last = now
        steps = max(1, int(dt_total / 0.008) + 1)
        dt = dt_total / steps
        for _ in range(steps):
            for p in self.paddles.values():
                diff = p["target"] - p["y"]
                p["y"] += max(-40 * dt, min(40 * dt, diff))
            if now < self.serve_at:
                continue
            if self.vx == 0 and self.vy == 0:
                angle = self.rng.uniform(-0.5, 0.5)
                self.vx = self.serve_dir * self.speed * math.cos(angle)
                self.vy = self.speed * math.sin(angle)
            self._move(dt, now)
            if self.over:
                return
        self.trail.append((self.bx, self.by))
        del self.trail[:-14]
        if now - self.start > 240:  # nach 4 Minuten ist Schluss
            self._finish(now)

    def _move(self, dt, now):
        px, nx = self.bx, self.bx + self.vx * dt
        ny = self.by + self.vy * dt
        if ny - self.R < 0:
            ny, self.vy = self.R, abs(self.vy)
        elif ny + self.R > self.H:
            ny, self.vy = self.H - self.R, -abs(self.vy)
        for pid, p in self.paddles.items():
            if p["team"] == 0 and self.vx < 0:
                face = p["x"] + self.PW / 2
                crossed = px - self.R >= face - 0.001 and nx - self.R <= face
            elif p["team"] == 1 and self.vx > 0:
                face = p["x"] - self.PW / 2
                crossed = px + self.R <= face + 0.001 and nx + self.R >= face
            else:
                continue
            if crossed and abs(ny - p["y"]) <= self.PH / 2 + self.R:
                offset = max(-1.0, min(1.0, (ny - p["y"]) / (self.PH / 2 + self.R)))
                self.speed = min(self.MAX_SPEED, self.speed * 1.06)
                angle = offset * 1.0
                direction = 1 if p["team"] == 0 else -1
                self.vx = direction * self.speed * math.cos(angle)
                self.vy = self.speed * math.sin(angle)
                nx = face + direction * self.R
                self.hits[pid] = self.hits.get(pid, 0) + 1
                self.emit(now, "hit", pid=pid, x=nx, y=ny)
                break
        self.bx, self.by = nx, ny
        if self.bx < -self.R or self.bx > self.W + self.R:
            team = 1 if self.bx < 0 else 0
            self.goals[team] += 1
            self.emit(now, "goal", team=team)
            if self.goals[team] >= self.to_win:
                self._finish(now)
            else:
                self._serve(now, -1 if team == 1 else 1)

    def _finish(self, now):
        a, b = self.goals
        self.winner = None if a == b else (0 if a > b else 1)
        self.over = True
        self.emit(now, "win", team=self.winner)

    def scores(self):
        return {pid: (1000 if self.winner == self.team_of(pid) else 0) + self.hits.get(pid, 0)
                for pid in self.players}

    def info(self, now):
        return f"{TEAM_NAMES[0]} {self.goals[0]} : {self.goals[1]} {TEAM_NAMES[1]} · bis {self.to_win}"

    def phone(self, pid, now):
        p = self.paddles.get(pid)
        if p is None:
            return {"ui": "msg", "big": "👀", "status": f"Zuschauen (höchstens {self.PER_TEAM} pro Team)"}
        team = p["team"]
        return {"ui": "paddle", "color": TEAM_COLORS[team],
                "status": f"{TEAM_NAMES[team]} · {self.goals[team]} : {self.goals[1 - team]}"}


# --------------------------------------------------------------------------- Ballon
class BalloonGame(Game):
    GAP = 0.09
    ROUND_TIME = 25.0
    REVEAL = 4.0

    def __init__(self, players, now, rng=None, opts=None):
        super().__init__(players, now, rng, opts)
        self.rounds = int(self.opts.get("runden", 3))
        self.total = {pid: 0 for pid in self.players}
        self.round = 0
        self._next(now)

    def join(self, pid, player, now):
        super().join(pid, player, now)
        self.total.setdefault(pid, 0)
        if self.phase == "pumpen":
            self.state[pid] = {"pumps": 0, "st": "pump", "last": -1.0}
        return True

    def leave(self, pid, now):
        super().leave(pid, now)
        self.total.pop(pid, None)
        self.state.pop(pid, None)

    def _next(self, now):
        self.round += 1
        self.limit = self.rng.randint(8, 45)  # für alle gleich – wer traut sich am meisten?
        self.state = {pid: {"pumps": 0, "st": "pump", "last": -1.0} for pid in self.total}
        self.phase = "pumpen"
        self.until = now + self.ROUND_TIME
        self.emit(now, "round")

    def input(self, pid, data, now):
        s = self.state.get(pid)
        if self.phase != "pumpen" or s is None or s["st"] != "pump":
            return
        if data.get("stop"):
            if s["pumps"]:
                s["st"] = "banked"
                self.total[pid] += s["pumps"]
                self.emit(now, "bank", pid=pid)
            return
        if not data.get("pump") or now - s["last"] < self.GAP:
            return
        s["last"] = now
        s["pumps"] += 1
        if s["pumps"] >= self.limit:
            s["st"] = "burst"
            self.emit(now, "burst", pid=pid)

    def update(self, now):
        if self.over:
            return
        if self.phase == "pumpen":
            if now >= self.until or all(s["st"] != "pump" for s in self.state.values()):
                for pid, s in self.state.items():  # Zeit um: was aufgepumpt ist, zählt
                    if s["st"] == "pump":
                        s["st"] = "banked"
                        self.total[pid] += s["pumps"]
                self.phase = "zeigen"
                self.until = now + self.REVEAL
                self.emit(now, "reveal")
        elif self.phase == "zeigen" and now >= self.until:
            if self.round >= self.rounds:
                self.over = True
            else:
                self._next(now)

    def skip(self, now):
        self.until = now
        return True

    def scores(self):
        return dict(self.total)

    def info(self, now):
        return f"Runde {self.round} / {self.rounds} · platzt bei {self.limit}"

    def phone(self, pid, now):
        s = self.state.get(pid)
        if s is None:
            return {"ui": "msg", "big": "👀", "status": "Zuschauen"}
        if self.phase == "zeigen":
            got = s["pumps"] if s["st"] == "banked" else 0
            return {"ui": "msg", "big": f"+{got}", "tone": "good" if got else "bad",
                    "status": f"Geplatzt wäre er bei {self.limit} · gesamt {self.total[pid]}"}
        return {"ui": "balloon", "pumps": s["pumps"], "state": s["st"], "rid": self.round,
                "status": {"pump": f"Runde {self.round} / {self.rounds} · {clock_text(self.until - now)}",
                           "banked": f"Gesichert: {s['pumps']} Punkte", "burst": "PENG! Diese Runde 0"}[s["st"]]}
