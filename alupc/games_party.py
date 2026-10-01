"""Minispiele (2): Schätzen, Farb-Chaos, Simon sagt, Tauziehen, Malen & Raten, Pong, Ballon."""

from __future__ import annotations

import math
import re
import unicodedata

from .games_base import TEAM_COLORS, TEAM_NAMES, Game, clock_text


# --------------------------------------------------------------------------- Hilfen
YEAR_UNITS = ("Jahr", "v. Chr.")


def parse_number(text) -> float | None:
    """„1.234,5“, „1234.5“, „2,5“, „12 000“ → Zahl. Deutsche Schreibweise hat Vorrang."""
    if isinstance(text, (int, float)) and not isinstance(text, bool):
        value = float(text)
    else:
        s = str(text or "").strip().replace(" ", "").replace(" ", "").replace("'", "")
        if not s or len(s) > 24:
            return None
        if "," in s:
            s = s.replace(".", "").replace(",", ".")
        elif re.fullmatch(r"\d{1,3}(\.\d{3})+", s):
            s = s.replace(".", "")
        if not re.fullmatch(r"\d+(\.\d+)?|\.\d+", s):
            return None
        value = float(s)
    if not math.isfinite(value) or value < 0 or value > 1e15:
        return None
    return value


def format_number(value: float, unit: str = "") -> str:
    """Zahl auf Deutsch (1.234,5) – Jahreszahlen ohne Punkt."""
    if unit in YEAR_UNITS:
        return f"{int(round(value))} v. Chr." if unit == "v. Chr." else str(int(round(value)))
    if abs(value - round(value)) < 1e-9 or abs(value) >= 1000:
        text = f"{round(value):,}".replace(",", ".")
    else:
        text = f"{value:,.2f}".rstrip("0").rstrip(".").replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{text} {unit}".strip()


def normalize_word(text: str) -> str:
    s = str(text or "").lower().strip()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        s = s.replace(a, b)
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if c.isalnum() and c.isascii())


def _distance(a: str, b: str) -> int:
    """Levenshtein-Abstand (für „knapp daneben“)."""
    if abs(len(a) - len(b)) > 2:
        return 3
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _pick(rng, items: list, memory: set | None, key=lambda x: x, count: int = 1) -> list:
    """Zufällig auswählen – zuerst, was in dieser Sitzung noch nicht dran war."""
    memory = memory if memory is not None else set()
    fresh = [x for x in items if key(x) not in memory]
    if len(fresh) < count:  # alles schon gehabt → von vorn
        for x in items:
            memory.discard(key(x))
        fresh = list(items)
    chosen = rng.sample(fresh, min(count, len(fresh)))
    for x in chosen:
        memory.add(key(x))
    return chosen


# --------------------------------------------------------------------------- Schätzen
class EstimateGame(Game):
    ASK = 25.0
    REVEAL = 8.0
    POINTS = [5, 3, 2]

    def __init__(self, players, now, rng=None, opts=None):
        super().__init__(players, now, rng, opts)
        from .game_data import QUESTIONS

        count = int(self.opts.get("fragen", 8))
        cat = self.opts.get("kategorie", "alle")
        pool = [q for q in QUESTIONS if cat in ("alle", q[0])] or list(QUESTIONS)
        self.questions = _pick(self.rng, pool, self.opts.get("_mem"), key=lambda q: q[1], count=count)
        self.score = {pid: 0 for pid in self.players}
        self.index = -1
        self._next(now)

    def join(self, pid, player, now):
        super().join(pid, player, now)
        self.score.setdefault(pid, 0)
        return True

    def leave(self, pid, now):
        super().leave(pid, now)
        self.score.pop(pid, None)
        self.guesses.pop(pid, None)

    @property
    def question(self):
        return self.questions[min(self.index, len(self.questions) - 1)]

    def _next(self, now):
        self.index += 1
        if self.index >= len(self.questions):
            self.over = True
            return
        self.phase = "frage"
        self.started = now
        self.until = now + self.ASK
        self.guesses: dict[str, tuple[float, float]] = {}
        self.gained: dict[str, int] = {}
        self.emit(now, "question", index=self.index)

    def input(self, pid, data, now):
        if self.phase != "frage" or pid not in self.score or pid in self.guesses or "num" not in data:
            return
        value = parse_number(data.get("num"))
        if value is None:
            return
        self.guesses[pid] = (value, now)
        self.emit(now, "guess", pid=pid)

    def _reveal(self, now):
        answer = self.question[2]
        errors = {pid: abs(v - answer) for pid, (v, _t) in self.guesses.items()}
        for pid, err in errors.items():
            better = sum(1 for e in errors.values() if e < err)
            pts = self.POINTS[better] if better < len(self.POINTS) else 1
            exact = err < 0.5 if self.question[3] in YEAR_UNITS else err <= abs(answer) * 0.01
            if exact:
                pts += 3  # Volltreffer (Jahreszahl genau, sonst höchstens 1 % daneben)
            self.gained[pid] = pts
            self.score[pid] += pts
        self.phase = "aufloesung"
        self.until = now + self.REVEAL
        self.revealed = now
        self.emit(now, "reveal")

    def update(self, now):
        if self.over:
            return
        if self.phase == "frage" and (now >= self.until or (self.score and len(self.guesses) >= len(self.score))):
            self._reveal(now)
        elif self.phase == "aufloesung" and now >= self.until:
            self._next(now)

    def skip(self, now):
        if self.phase == "frage":
            self._reveal(now)
        else:
            self._next(now)
        return True

    def scores(self):
        return dict(self.score)

    def info(self, now):
        return f"Frage {self.index + 1} / {len(self.questions)}"

    def phone(self, pid, now):
        if pid not in self.score:
            return {"ui": "msg", "big": "👀", "status": "Zuschauen"}
        _cat, text, answer, unit = self.question
        if self.phase == "frage":
            mine = self.guesses.get(pid)
            return {"ui": "number", "question": text, "unit": unit, "qid": self.index,
                    "done": format_number(mine[0], unit) if mine else "",
                    "status": f"Frage {self.index + 1} / {len(self.questions)} · {clock_text(self.until - now)}"}
        mine = self.guesses.get(pid)
        pts = self.gained.get(pid, 0)
        return {"ui": "msg", "big": f"+{pts}" if pts else "0", "status":
                f"Richtig: {format_number(answer, unit)}" +
                (f" · Du: {format_number(mine[0], unit)}" if mine else " · keine Schätzung")}


# --------------------------------------------------------------------------- Farb-Chaos (Stroop)
STROOP_COLORS = [("ROT", "#ef4444"), ("BLAU", "#3b82f6"), ("GRÜN", "#22c55e"), ("GELB", "#facc15"),
                 ("LILA", "#a855f7"), ("ORANGE", "#f97316")]


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


class StroopGame(EliminationGame):
    PAUSE = 1.3

    def __init__(self, players, now, rng=None, opts=None):
        super().__init__(players, now, rng, opts)
        self.base = 3.0 if self.opts.get("tempo", "normal") == "normal" else 2.2
        self._next(now)

    def _next(self, now):
        self.round += 1
        k = 4 if self.round <= 8 else 6
        cols = STROOP_COLORS[:k]
        word = self.rng.choice(cols)
        ink = word if self.rng.random() < 0.12 else self.rng.choice([c for c in cols if c != word])
        self.rule = "farbe" if self.round <= 5 or self.rng.random() < 0.65 else "wort"
        self.word, self.ink = word, ink
        self.target = (ink if self.rule == "farbe" else word)[0]
        self.choices = [c[0] for c in self.rng.sample(cols, k)]  # Reihenfolge auf dem Handy wechselt
        self.window = max(1.0, self.base * 0.94 ** (self.round - 1))
        self.phase = "zeigen"
        self.shown = now
        self.until = now + self.window
        self.answers: dict[str, tuple[str, float]] = {}
        self.emit(now, "word")

    def input(self, pid, data, now):
        if self.phase != "zeigen" or pid not in self.alive or pid in self.answers:
            return
        choice = str(data.get("btn", ""))
        if choice in self.choices:
            self.answers[pid] = (choice, now - self.shown)

    def update(self, now):
        if self.over:
            return
        if self.phase == "zeigen" and (now >= self.until or self.alive <= set(self.answers)):
            failed = {pid for pid in self.alive if self.answers.get(pid, ("",))[0] != self.target}
            self._eliminate(failed, len(self.answers), now)
            self.phase = "pause"
            self.until = now + self.PAUSE
        elif self.phase == "pause" and now >= self.until:
            if self._finished():
                self.over = True
            else:
                self._next(now)

    def info(self, now):
        return f"Runde {self.round} · {len(self.alive)} im Spiel"

    def phone(self, pid, now):
        if pid not in self.players:
            return {"ui": "msg", "big": "👀", "status": "Zuschauen"}
        if pid not in self.alive:
            return self._out_msg(pid)
        ask = "Welche FARBE hat das Wort?" if self.rule == "farbe" else "Was STEHT da?"
        if self.phase == "zeigen":
            done = pid in self.answers
            return {"ui": "buttons", "layout": "list", "rid": self.round, "enabled": not done,
                    "buttons": [{"id": c, "label": c} for c in self.choices],
                    "status": "✓ gewählt" if done else ask}
        ok = pid not in self.last_out
        return {"ui": "msg", "big": "✓" if ok else "RAUS", "tone": "good" if ok else "bad",
                "status": "Alle falsch – keiner fliegt raus!" if self.all_failed else f"noch {len(self.alive)} im Spiel"}


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


# --------------------------------------------------------------------------- Tauziehen
class TugGame(Game):
    teams = True
    GAP = 0.05
    PULL = 0.03  # Seil-Weg je Zug (geteilt durch Teamgröße – große Teams sind nicht im Vorteil)

    def __init__(self, players, now, rng=None, opts=None):
        super().__init__(players, now, rng, opts)
        self.duration = float(self.opts.get("dauer", 45))
        self.start = now
        self.pos = 0.0  # −1 = Team Rot gewinnt, +1 = Team Blau
        self.taps = {pid: 0 for pid in self.players}
        self.last_tap = {pid: -1.0 for pid in self.players}
        self.winner: int | None = None

    def join(self, pid, player, now):
        super().join(pid, player, now)
        self.taps.setdefault(pid, 0)
        self.last_tap.setdefault(pid, -1.0)
        return True

    def leave(self, pid, now):
        super().leave(pid, now)
        self.taps.pop(pid, None)

    def team_size(self, team):
        return max(1, sum(1 for p in self.players if self.team_of(p) == team))

    def input(self, pid, data, now):
        if self.over or pid not in self.taps or not data.get("tap") or now - self.last_tap[pid] < self.GAP:
            return
        self.last_tap[pid] = now
        self.taps[pid] += 1
        team = self.team_of(pid)
        step = self.PULL / self.team_size(team)
        self.pos += -step if team == 0 else step

    def update(self, now):
        if self.over:
            return
        if abs(self.pos) >= 1.0 or now - self.start >= self.duration:
            self.pos = max(-1.0, min(1.0, self.pos))
            self.winner = None if abs(self.pos) < 0.02 else (0 if self.pos < 0 else 1)
            self.over = True
            self.emit(now, "win", team=self.winner)

    def remaining(self, now):
        return max(0.0, self.duration - (now - self.start))

    def scores(self):
        return {pid: (1000 if self.winner == self.team_of(pid) else 0) + n for pid, n in self.taps.items()}

    def info(self, now):
        return f"noch {clock_text(self.remaining(now))}"

    def phone(self, pid, now):
        if pid not in self.taps:
            return {"ui": "msg", "big": "👀", "status": "Zuschauen"}
        team = self.team_of(pid)
        return {"ui": "tap", "label": "ZIEH!", "color": TEAM_COLORS[team],
                "status": f"{TEAM_NAMES[team]} · {self.taps[pid]} Züge"}


# --------------------------------------------------------------------------- Malen & Raten
class DrawGame(Game):
    REVEAL = 4.5
    MAX_POINTS = 6000
    GUESS_POINTS = [10, 8, 6, 5, 4]

    def __init__(self, players, now, rng=None, opts=None):
        super().__init__(players, now, rng, opts)
        from .game_data import WORDS

        self.turn_time = float(self.opts.get("zeit", 80))
        order = list(self.players)
        self.rng.shuffle(order)
        self.order = (order * int(self.opts.get("runden", 1)))[:16]
        self.words = _pick(self.rng, WORDS, self.opts.get("_mem"), count=len(self.order))
        self.score = {pid: 0 for pid in self.players}
        self.turn = -1
        self.feed: list[tuple[float, str, str, str]] = []  # (Zeit, pid, Text, Art)
        self._next(now)

    def join(self, pid, player, now):
        super().join(pid, player, now)
        self.score.setdefault(pid, 0)
        return True

    def leave(self, pid, now):
        super().leave(pid, now)
        self.score.pop(pid, None)
        if self.phase == "malen" and pid == self.drawer:
            self._reveal(now)

    def _next(self, now):
        while True:
            self.turn += 1
            if self.turn >= len(self.order):
                self.over = True
                return
            if self.order[self.turn] in self.players:
                break
        self.drawer = self.order[self.turn]
        self.word = self.words[self.turn % len(self.words)]
        self.strokes: list[dict] = []
        self.points_total = 0
        self.guessed: dict[str, float] = {}
        self.close: dict[str, float] = {}
        self.gained: dict[str, int] = {}
        self.phase = "malen"
        self.start = now
        self.until = now + self.turn_time
        letters = [i for i, c in enumerate(self.word) if c.isalpha()]
        self.reveal_order = self.rng.sample(letters, len(letters))
        self.emit(now, "turn", drawer=self.drawer)

    def guessers(self):
        return [p for p in self.players if p != self.drawer]

    def hint(self, now) -> str:
        """„E _ _ _ _ _ _“ – mit der Zeit kommen Buchstaben dazu."""
        part = (now - self.start) / max(1.0, self.turn_time)
        show = 0 if part < 0.4 else 1 if part < 0.65 else 2 if part < 0.85 else 3
        show = min(show, max(0, len(self.reveal_order) - 2))
        visible = set(self.reveal_order[:show])
        return " ".join(c if (i in visible or not c.isalpha()) else "_" for i, c in enumerate(self.word))

    def input(self, pid, data, now):
        if self.phase != "malen" or pid not in self.players:
            return
        if pid == self.drawer:
            self._draw(data)
            return
        text = str(data.get("guess", "")).strip()[:40]
        if not text or pid in self.guessed:
            return
        guess, word = normalize_word(text), normalize_word(self.word)
        if guess == word:
            pts = self.GUESS_POINTS[len(self.guessed)] if len(self.guessed) < len(self.GUESS_POINTS) else 3
            self.guessed[pid] = now
            self.gained[pid] = pts
            self.score[pid] += pts
            self.feed.append((now, pid, "hat's erraten!", "ok"))
            self.emit(now, "correct", pid=pid)
        elif len(word) >= 4 and _distance(guess, word) <= 1:
            self.close[pid] = now
            self.feed.append((now, pid, "ist ganz nah dran …", "close"))
        else:
            self.feed.append((now, pid, text, "guess"))
        del self.feed[:-12]

    def _draw(self, data):
        if "clear" in data:
            self.strokes = []
            self.points_total = 0
            return
        if "undo" in data:
            if self.strokes:
                self.points_total -= len(self.strokes.pop()["pts"])
            return
        stroke = data.get("stroke")
        if isinstance(stroke, dict):
            color = str(stroke.get("c", "#111827"))
            if not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
                color = "#111827"
            width = max(1.0, min(40.0, float(stroke.get("w", 6) or 6)))
            self.strokes.append({"c": color, "w": width, "pts": []})
            self._points([stroke.get("p")])
        if "pts" in data and isinstance(data["pts"], list):
            self._points(data["pts"][:200])

    def _points(self, pts):
        if not self.strokes:
            return
        target = self.strokes[-1]["pts"]
        for pt in pts:
            if self.points_total >= self.MAX_POINTS:
                return
            try:
                x, y = float(pt[0]), float(pt[1])
            except (TypeError, ValueError, IndexError):
                continue
            if math.isfinite(x) and math.isfinite(y):
                target.append((max(0.0, min(1.0, x)), max(0.0, min(1.0, y))))
                self.points_total += 1

    def _reveal(self, now):
        if self.guessed and self.drawer in self.score:
            pts = min(12, 3 * len(self.guessed))
            self.gained[self.drawer] = pts
            self.score[self.drawer] += pts
        self.phase = "wort"
        self.until = now + self.REVEAL
        self.emit(now, "reveal")

    def update(self, now):
        if self.over:
            return
        if self.phase == "malen":
            everyone = self.guessers() and all(p in self.guessed for p in self.guessers())
            if now >= self.until or everyone:
                self._reveal(now)
        elif self.phase == "wort" and now >= self.until:
            self._next(now)

    def skip(self, now):
        if self.phase == "malen":
            self._reveal(now)
        else:
            self._next(now)
        return True

    def scores(self):
        return dict(self.score)

    def info(self, now):
        name = getattr(self.players.get(self.drawer), "name", "?")
        return f"Bild {self.turn + 1} / {len(self.order)} · {name} malt „{self.word}“"

    def phone(self, pid, now):
        if pid not in self.score:
            return {"ui": "msg", "big": "👀", "status": "Zuschauen"}
        if self.phase == "wort":
            pts = self.gained.get(pid, 0)
            return {"ui": "msg", "big": self.word, "status": f"+{pts} Punkte" if pts else "Das Wort war …"}
        left = clock_text(self.until - now)
        if pid == self.drawer:
            return {"ui": "draw", "word": self.word, "tid": self.turn,
                    "status": f"Male: {self.word} · {left} · {len(self.guessed)} erraten"}
        if pid in self.guessed:
            return {"ui": "msg", "big": "✓", "tone": "good", "status": f"Richtig! +{self.gained.get(pid, 0)} · {left}"}
        close = now - self.close.get(pid, -99) < 3
        return {"ui": "text", "tid": self.turn, "hint": self.hint(now), "feedback": "Ganz knapp!" if close else "",
                "status": f"Was wird gemalt? · {left}"}


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
