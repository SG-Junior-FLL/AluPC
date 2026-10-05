"""Minispiele (3) – Klassiker: Lichtrenner (wie „Tron“), Schere-Stein-Papier, Quiz (A/B/C/D)."""

from __future__ import annotations

from .games_base import Game, clock_text

DIRS = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}


# --------------------------------------------------------------------------- Lichtrenner
class TronGame(Game):
    """Jeder fährt eine Leuchtspur, die stehen bleibt. Wer gegen eine Spur oder den Rand fährt, ist für diese Runde
    raus. Wer am längsten fährt, gewinnt die Runde. Punkte je Runde: so viele, wie Gegner vorher ausgeschieden sind."""

    W, H = 64, 36
    STEP = 0.085
    READY = 2.0  # 3-2-1 vor jeder Runde
    RESULT = 3.0

    def __init__(self, players, now, rng=None, opts=None):
        super().__init__(players, now, rng, opts)
        self.rounds = int(self.opts.get("runden", 3))
        self.score = {pid: 0 for pid in self.players}
        self.round = 0
        self.winner: str | None = None
        self.gained: dict[str, int] = {}
        self._new_round(now)

    def join(self, pid, player, now):
        super().join(pid, player, now)
        self.score.setdefault(pid, 0)  # fährt ab der nächsten Runde mit
        return True

    def leave(self, pid, now):
        super().leave(pid, now)
        self.score.pop(pid, None)
        self.riders.pop(pid, None)

    def _starts(self, n: int) -> list[tuple[tuple[int, int], tuple[int, int]]]:
        """Startplätze gleichmäßig am Rand verteilt, Blick zur Mitte."""
        spots = []
        for i in range(n):
            side = i % 4
            k = i // 4 + 1
            slots = (n + 3) // 4 + 1
            if side == 0:
                spots.append(((4, self.H * k // slots), DIRS["right"]))
            elif side == 1:
                spots.append(((self.W - 5, self.H * k // slots), DIRS["left"]))
            elif side == 2:
                spots.append(((self.W * k // slots, 3), DIRS["down"]))
            else:
                spots.append(((self.W * k // slots, self.H - 4), DIRS["up"]))
        return spots

    def _new_round(self, now):
        self.round += 1
        self.phase = "bereit"
        self.until = now + self.READY
        self.last_step = self.until
        self.trail: dict[tuple[int, int], str] = {}
        self.riders: dict[str, dict] = {}
        self.order_out: list[str] = []
        self.out_points: dict[str, int] = {}
        pids = list(self.score)
        self.rng.shuffle(pids)
        for pid, (pos, d) in zip(pids, self._starts(len(pids))):
            self.riders[pid] = {"pos": pos, "dir": d, "next": d, "alive": True}
            self.trail[pos] = pid

    def alive(self) -> list[str]:
        return [pid for pid, r in self.riders.items() if r["alive"]]

    def input(self, pid, data, now):
        r = self.riders.get(pid)
        d = DIRS.get(str(data.get("dir", "")))
        if r is None or d is None or not r["alive"]:
            return
        if (d[0] + r["dir"][0], d[1] + r["dir"][1]) != (0, 0):  # nicht umdrehen
            r["next"] = d

    def update(self, now):
        if self.over:
            return
        if self.phase == "bereit" and now >= self.until:
            self.phase = "fahren"
            self.last_step = now
            self.emit(now, "go")
        elif self.phase == "fahren":
            steps = 0
            while now - self.last_step >= self.STEP and steps < 10 and self.phase == "fahren":
                self.last_step += self.STEP
                steps += 1
                self._step(self.last_step)
        elif self.phase == "ergebnis" and now >= self.until:
            if self.round >= self.rounds:
                self.over = True
            else:
                self._new_round(now)

    def _step(self, now):
        heads = {}
        for pid, r in self.riders.items():
            if not r["alive"]:
                continue
            r["dir"] = r["next"]
            heads[pid] = (r["pos"][0] + r["dir"][0], r["pos"][1] + r["dir"][1])
        crashed = set()
        for pid, (x, y) in heads.items():
            if not (0 <= x < self.W and 0 <= y < self.H) or (x, y) in self.trail:
                crashed.add(pid)
            elif any(h == (x, y) for p, h in heads.items() if p != pid):  # Kopf an Kopf
                crashed.add(pid)
        before = len(self.order_out)  # gleichzeitig Gecrashte bekommen gleich viele Punkte
        for pid, head in heads.items():
            r = self.riders[pid]
            if pid in crashed:
                r["alive"] = False
                self.order_out.append(pid)
                self.out_points[pid] = before
                self.emit(now, "crash", pid=pid, cell=r["pos"])
            else:
                r["pos"] = head
                self.trail[head] = pid
        left = self.alive()
        if len(left) <= (0 if len(self.riders) == 1 else 1):
            self._finish_round(now, left)

    def _finish_round(self, now, left):
        self.gained = {}
        for pid in self.riders:
            if pid in self.score:
                self.gained[pid] = len(self.riders) - 1 if pid in left else self.out_points.get(pid, 0)
                self.score[pid] += self.gained[pid]
        self.winner = left[0] if len(left) == 1 else None
        if self.winner:
            self.emit(now, "win", pid=self.winner)
        self.phase = "ergebnis"
        self.until = now + self.RESULT

    def skip(self, now):
        if self.phase == "ergebnis":
            self.until = now
            return True
        return False

    def scores(self):
        return dict(self.score)

    def info(self, now):
        return f"Runde {self.round} / {self.rounds} · {len(self.alive())} fahren"

    def phone(self, pid, now):
        r = self.riders.get(pid)
        if pid not in self.score:
            return {"ui": "msg", "big": "👀", "status": "Zuschauen"}
        if r is None:
            return {"ui": "msg", "big": "⏳", "status": "Nächste Runde bist du dabei"}
        if self.phase == "bereit":
            return {"ui": "pad", "status": f"Gleich geht's los – Runde {self.round}"}
        if self.phase == "fahren":
            return {"ui": "pad", "status": "Fahr! Nicht gegen Spuren oder Rand" if r["alive"] else "Crash – raus"}
        won = self.winner == pid
        return {"ui": "msg", "big": "🏆" if won else "✓", "tone": "good" if won else "",
                "status": f"{self.score[pid]} Punkte"}


# --------------------------------------------------------------------------- Schere, Stein, Papier
RPS = [("stein", "Stein", "✊"), ("papier", "Papier", "✋"), ("schere", "Schere", "✌️")]
BEATS = {"stein": "schere", "schere": "papier", "papier": "stein"}


class RpsGame(Game):
    """Alle gegen alle, gleichzeitig: jeder wählt geheim. Pro geschlagenem Gegner 1 Punkt."""

    CHOOSE = 8.0
    SHOW = 4.0

    def __init__(self, players, now, rng=None, opts=None):
        super().__init__(players, now, rng, opts)
        self.rounds = int(self.opts.get("runden", 5))
        self.score = {pid: 0 for pid in self.players}
        self.round = 0
        self.gained: dict[str, int] = {}
        self._next(now)

    def join(self, pid, player, now):
        super().join(pid, player, now)
        self.score.setdefault(pid, 0)
        return True

    def leave(self, pid, now):
        super().leave(pid, now)
        self.score.pop(pid, None)
        self.picks.pop(pid, None)

    def _next(self, now):
        self.round += 1
        self.phase = "waehlen"
        self.until = now + self.CHOOSE
        self.picks: dict[str, str] = {}

    def input(self, pid, data, now):
        if self.phase == "waehlen" and pid in self.score and data.get("btn") in BEATS and pid not in self.picks:
            self.picks[pid] = data["btn"]
            self.emit(now, "pick", pid=pid)

    def update(self, now):
        if self.over:
            return
        if self.phase == "waehlen" and (now >= self.until or (self.score and len(self.picks) >= len(self.score))):
            self._reveal(now)
        elif self.phase == "zeigen" and now >= self.until:
            if self.round >= self.rounds:
                self.over = True
            else:
                self._next(now)

    def _reveal(self, now):
        self.gained = {}
        for pid, mine in self.picks.items():
            self.gained[pid] = sum(1 for other, theirs in self.picks.items() if other != pid and BEATS[mine] == theirs)
            self.score[pid] = self.score.get(pid, 0) + self.gained[pid]
        self.phase = "zeigen"
        self.until = now + self.SHOW
        self.emit(now, "reveal")

    def counts(self) -> dict[str, int]:
        return {k: sum(1 for v in self.picks.values() if v == k) for k, _l, _e in RPS}

    def skip(self, now):
        if self.phase == "zeigen":
            self.until = now
            return True
        if self.phase == "waehlen":
            self._reveal(now)
            return True
        return False

    def scores(self):
        return dict(self.score)

    def info(self, now):
        return f"Runde {self.round} / {self.rounds} · {len(self.picks)} / {len(self.score)} gewählt"

    def phone(self, pid, now):
        if pid not in self.score:
            return {"ui": "msg", "big": "👀", "status": "Zuschauen"}
        if self.phase == "waehlen":
            chosen = self.picks.get(pid)
            if chosen:
                emoji = next(e for k, _l, e in RPS if k == chosen)
                return {"ui": "msg", "big": emoji, "status": "Gewählt – warte auf die anderen"}
            return {"ui": "buttons", "layout": "column", "rid": self.round, "enabled": True,
                    "buttons": [{"id": k, "label": f"{e}  {label}"} for k, label, e in RPS],
                    "status": f"Runde {self.round}: geheim wählen!"}
        g = self.gained.get(pid)
        return {"ui": "msg", "big": f"+{g}" if g is not None else "–", "tone": "good" if g else "",
                "status": f"{self.score[pid]} Punkte" if g is not None else "Zu spät gewählt"}


# --------------------------------------------------------------------------- Quiz
QUIZ = [
    ("Wie heißt die Hauptstadt von Australien?", "Canberra", ["Sydney", "Melbourne", "Perth"]),
    ("Wie viele Beine hat eine Spinne?", "8", ["6", "10", "12"]),
    ("Welcher Planet ist der Sonne am nächsten?", "Merkur", ["Venus", "Mars", "Erde"]),
    ("Welches ist das größte Tier der Erde?", "Blauwal", ["Afrikanischer Elefant", "Giraffe", "Pottwal"]),
    ("Wie viele Minuten hat ein Tag?", "1440", ["1240", "1640", "1200"]),
    ("Welches chemische Zeichen hat Gold?", "Au", ["Ag", "Go", "Gd"]),
    ("Wer hat die Mona Lisa gemalt?", "Leonardo da Vinci", ["Michelangelo", "Raffael", "Rembrandt"]),
    ("Wie viele Spieler einer Fußballmannschaft stehen auf dem Feld?", "11", ["10", "9", "12"]),
    ("Wie heißt der höchste Berg Deutschlands?", "Zugspitze", ["Watzmann", "Feldberg", "Brocken"]),
    ("Welches Tier ist an Land am schnellsten?", "Gepard", ["Löwe", "Pferd", "Strauß"]),
    ("In welchem Jahr fiel die Berliner Mauer?", "1989", ["1990", "1987", "1991"]),
    ("Wie heißt die Hauptstadt von Kanada?", "Ottawa", ["Toronto", "Vancouver", "Montreal"]),
    ("Welche Farbe entsteht aus Blau und Gelb?", "Grün", ["Lila", "Orange", "Braun"]),
    ("Wie viele Tasten hat ein normales Klavier?", "88", ["76", "96", "72"]),
    ("Welches Gas nehmen Pflanzen für die Fotosynthese auf?", "Kohlendioxid", ["Sauerstoff", "Stickstoff",
                                                                              "Helium"]),
    ("Was ist die Wurzel aus 144?", "12", ["14", "11", "16"]),
    ("Welche Sprache spricht man in Brasilien?", "Portugiesisch", ["Spanisch", "Englisch", "Französisch"]),
    ("Wie viele Herzen hat ein Oktopus?", "3", ["1", "2", "8"]),
    ("Wer hat „Faust“ geschrieben?", "Goethe", ["Schiller", "Lessing", "Kafka"]),
    ("Welcher Ozean ist der größte?", "Pazifik", ["Atlantik", "Indischer Ozean", "Arktischer Ozean"]),
    ("Wie viele Bundesländer hat Deutschland?", "16", ["15", "14", "17"]),
    ("Wofür steht das chemische Zeichen O?", "Sauerstoff", ["Gold", "Osmium", "Ozon"]),
    ("Wie viele Ecken hat ein Sechseck?", "6", ["5", "7", "8"]),
    ("Welches Land nennt man „Land der aufgehenden Sonne“?", "Japan", ["China", "Südkorea", "Thailand"]),
    ("Wie viel ist 7 × 8?", "56", ["54", "63", "48"]),
    ("Welcher Planet heißt „der rote Planet“?", "Mars", ["Jupiter", "Venus", "Saturn"]),
    ("In welcher Stadt steht der Eiffelturm?", "Paris", ["Lyon", "Brüssel", "Marseille"]),
    ("Welches ist das größte Organ des Menschen?", "Haut", ["Leber", "Lunge", "Gehirn"]),
    ("Wie viele Zähne hat ein Erwachsener mit Weisheitszähnen?", "32", ["28", "30", "36"]),
    ("In welcher Einheit misst man elektrische Spannung?", "Volt", ["Ampere", "Watt", "Ohm"]),
    ("Wer betrat als erster Mensch den Mond?", "Neil Armstrong", ["Buzz Aldrin", "Juri Gagarin",
                                                                  "Michael Collins"]),
    ("Wie viele Stunden hat eine Woche?", "168", ["144", "172", "160"]),
    ("Welches Instrument hat normalerweise sechs Saiten?", "Gitarre", ["Geige", "Cello", "Kontrabass"]),
    ("Was ist H₂O?", "Wasser", ["Wasserstoff", "Salz", "Sauerstoff"]),
    ("Wie heißt die Hauptstadt von Spanien?", "Madrid", ["Barcelona", "Sevilla", "Valencia"]),
    ("Wie viel Grad hat ein rechter Winkel?", "90", ["180", "45", "60"]),
    ("Welches Säugetier legt Eier?", "Schnabeltier", ["Delfin", "Fledermaus", "Känguru"]),
    ("Wie viele Tage hat ein Schaltjahr?", "366", ["365", "364", "367"]),
    ("Welcher Kontinent ist der größte?", "Asien", ["Afrika", "Nordamerika", "Europa"]),
    ("Wie viele Farben hat ein Regenbogen (übliche Zählung)?", "7", ["5", "6", "8"]),
]
LETTERS = "ABCD"
ANSWER_COLORS = ["#ef4444", "#3b82f6", "#f59e0b", "#22c55e"]


class QuizGame(Game):
    """Frage + 4 Antworten auf Monitor 2, Handys tippen A/B/C/D. Richtig = 500 Punkte + bis zu 500 für Tempo."""

    ASK = 15.0
    SHOW = 4.5

    def __init__(self, players, now, rng=None, opts=None):
        super().__init__(players, now, rng, opts)
        count = int(self.opts.get("fragen", 10))
        self.questions = self.rng.sample(QUIZ, min(count, len(QUIZ)))
        self.score = {pid: 0 for pid in self.players}
        self.index = -1
        self.gained: dict[str, int] = {}
        self._next(now)

    def join(self, pid, player, now):
        super().join(pid, player, now)
        self.score.setdefault(pid, 0)
        return True

    def leave(self, pid, now):
        super().leave(pid, now)
        self.score.pop(pid, None)

    def _next(self, now):
        self.index += 1
        q, right, wrong = self.questions[self.index]
        answers = [right, *wrong]
        self.rng.shuffle(answers)
        self.question, self.answers, self.right = q, answers, answers.index(right)
        self.phase = "frage"
        self.asked = now
        self.until = now + self.ASK
        self.picks: dict[str, tuple[int, float]] = {}
        self.emit(now, "question")

    def input(self, pid, data, now):
        if self.phase != "frage" or pid not in self.score or pid in self.picks:
            return
        try:
            choice = int(data.get("btn"))
        except (TypeError, ValueError):
            return
        if 0 <= choice < 4:
            self.picks[pid] = (choice, now - self.asked)
            self.emit(now, "pick", pid=pid)

    def update(self, now):
        if self.over:
            return
        if self.phase == "frage" and (now >= self.until or (self.score and len(self.picks) >= len(self.score))):
            self._reveal(now)
        elif self.phase == "aufloesung" and now >= self.until:
            if self.index + 1 >= len(self.questions):
                self.over = True
            else:
                self._next(now)

    def _reveal(self, now):
        self.gained = {}
        for pid, (choice, t) in self.picks.items():
            if choice == self.right:
                pts = 500 + int(500 * max(0.0, 1 - t / self.ASK))
                self.gained[pid] = pts
                self.score[pid] = self.score.get(pid, 0) + pts
        self.phase = "aufloesung"
        self.until = now + self.SHOW
        self.emit(now, "reveal")

    def skip(self, now):
        if self.phase == "frage":
            self._reveal(now)
            return True
        if self.phase == "aufloesung":
            self.until = now
            return True
        return False

    def scores(self):
        return dict(self.score)

    def info(self, now):
        left = clock_text(self.until - now) if self.phase == "frage" else "Auflösung"
        return f"Frage {self.index + 1} / {len(self.questions)} · {left}"

    def phone(self, pid, now):
        if pid not in self.score:
            return {"ui": "msg", "big": "👀", "status": "Zuschauen"}
        if self.phase == "frage":
            if pid in self.picks:
                return {"ui": "msg", "big": LETTERS[self.picks[pid][0]], "status": "Eingeloggt – warte …"}
            return {"ui": "buttons", "layout": "quiz", "rid": self.index, "enabled": True,
                    "buttons": [{"id": str(i), "label": f"{LETTERS[i]}  {a}", "color": ANSWER_COLORS[i]}
                                for i, a in enumerate(self.answers)],
                    "status": self.question}
        pts = self.gained.get(pid)
        return {"ui": "msg", "big": f"+{pts}" if pts else "✗", "tone": "good" if pts else "bad",
                "status": f"Richtig: {LETTERS[self.right]} {self.answers[self.right]} · {self.score[pid]} Punkte"}
