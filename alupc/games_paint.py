"""Minispiele (Montagsmaler): einer malt am Handy, Monitor 2 zeigt das Bild live, alle anderen raten am Handy.

Reihum malt jeder (Runden aus dem Steuerfenster). Wer das Wort richtig tippt, bekommt Punkte – je schneller, desto
mehr; der Maler bekommt für jeden, der es errät, auch Punkte. Groß-/Kleinschreibung, Umlaute (ä = ae) und Leerzeichen
sind beim Raten egal. Das Bild gibt es nur auf Monitor 2 – die Handys der Ratenden zeigen nur das Eingabefeld.
"""

from __future__ import annotations

import re

from .games_base import Game

WORDS = [
    "Apfel", "Banane", "Haus", "Auto", "Fahrrad", "Hund", "Katze", "Sonne", "Mond", "Baum", "Blume", "Fisch",
    "Schiff", "Flugzeug", "Zug", "Brille", "Schuh", "Hut", "Regenschirm", "Schneemann", "Eis", "Pizza", "Kuchen",
    "Burg", "Krone", "Schlüssel", "Uhr", "Telefon", "Computer", "Gitarre", "Trommel", "Ball", "Tor", "Rakete",
    "Stern", "Wolke", "Regenbogen", "Blitz", "Berg", "Insel", "Brücke", "Leuchtturm", "Zelt", "Feuer", "Kerze",
    "Geschenk", "Ballon", "Drache", "Einhorn", "Pinguin", "Elefant", "Giraffe", "Schlange", "Spinne", "Biene",
    "Schmetterling", "Schnecke", "Igel", "Eule", "Hai", "Krake", "Dinosaurier", "Roboter", "Gespenst", "Pirat",
    "Ritter", "Zauberer", "Hexe", "König", "Brot", "Erdbeere", "Karotte", "Kirsche", "Popcorn", "Tasse",
    "Gabel", "Löffel", "Bett", "Lampe", "Fenster", "Treppe", "Leiter", "Hammer", "Schere", "Buch", "Brief",
    "Kamera", "Fernseher", "Kopfhörer", "Rucksack", "Sonnenbrille", "Tannenbaum", "Osterei", "Kürbis",
    "Handschuh", "Socke", "Herz", "Anker", "Fallschirm", "Hubschrauber", "Traktor", "Skateboard", "Schaukel",
]
COLORS = ["#111827", "#ef4444", "#f59e0b", "#22c55e", "#3b82f6", "#a855f7", "#ec4899", "#8b5a2b"]
MAX_STROKES = 800
MAX_POINTS = 400


def norm(text: str) -> str:
    """Zum Vergleichen: klein, ä→ae …, nur Buchstaben und Ziffern."""
    text = str(text or "").strip().lower()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        text = text.replace(a, b)
    return re.sub(r"[^a-z0-9]", "", text)


class PaintGame(Game):
    REVEAL = 5.0

    def __init__(self, players, now, rng=None, opts=None):
        super().__init__(players, now, rng, opts)
        self.per_player = int(self.opts.get("runden", 1))
        self.seconds = float(self.opts.get("zeit", 80))
        self.order = list(self.players)
        self.rng.shuffle(self.order)
        self.total = max(1, len(self.order) * self.per_player)
        self.score = {pid: 0 for pid in self.players}
        self.used: set[str] = set()
        self.round = 0
        self.version = 0
        self.guesses: list[tuple[str, str]] = []  # (pid, falscher Tipp) – die letzten auf Monitor 2
        self._next(now)

    # ---- Spieler
    def join(self, pid, player, now):
        super().join(pid, player, now)
        self.score.setdefault(pid, 0)
        if pid not in self.order:
            self.order.append(pid)
        return True

    def leave(self, pid, now):
        super().leave(pid, now)
        self.score.pop(pid, None)
        self.guessed.pop(pid, None)
        if pid == self.drawer and self.phase == "malen":
            self._reveal(now)  # Maler weg → Wort auflösen, weiter mit dem Nächsten

    # ---- Ablauf
    def _next(self, now):
        self.round += 1
        if self.round > self.total or not self.score:
            self.over = True
            self.phase = "ende"
            return
        alive = [pid for pid in self.order if pid in self.score]
        self.drawer = alive[(self.round - 1) % len(alive)]
        choices = [w for w in WORDS if w not in self.used] or WORDS
        self.word = self.rng.choice(choices)
        self.used.add(self.word)
        self.strokes: list[dict] = []
        self.guessed: dict[str, float] = {}
        self.guesses = []
        self.phase = "malen"
        self.started = now
        self.until = now + self.seconds
        self.version += 1
        self.emit(now, "round", drawer=self.drawer)

    def _reveal(self, now):
        self.phase = "aufloesen"
        self.until = now + self.REVEAL
        self.version += 1
        self.emit(now, "reveal", word=self.word)

    def guessers(self) -> list[str]:
        return [pid for pid in self.score if pid != self.drawer]

    def update(self, now):
        if self.over:
            return
        if self.phase == "malen":
            others = self.guessers()
            if now >= self.until or (others and all(pid in self.guessed for pid in others)):
                self._reveal(now)
        elif self.phase == "aufloesen" and now >= self.until:
            self._next(now)

    def skip(self, now):
        if self.phase == "malen":
            self._reveal(now)
            return True
        if self.phase == "aufloesen":
            self.until = now
            return True
        return False

    def input(self, pid, data, now):
        if self.phase != "malen" or pid not in self.score:
            return
        if pid == self.drawer:
            self._draw_input(data)
            return
        guess = str(data.get("guess", ""))[:40]
        if not guess or pid in self.guessed:
            return
        if norm(guess) == norm(self.word):
            self.guessed[pid] = now
            left = max(0.0, self.until - now) / self.seconds
            self.score[pid] += 50 + int(50 * left) + (20 if len(self.guessed) == 1 else 0)
            self.score[self.drawer] = self.score.get(self.drawer, 0) + 25
            self.emit(now, "correct", pid=pid)
        else:
            self.guesses = (self.guesses + [(pid, guess.strip()[:24])])[-8:]
            self.emit(now, "guess", pid=pid)
        self.version += 1

    def _draw_input(self, data):
        if data.get("clear"):
            self.strokes = []
            self.version += 1
            return
        stroke = data.get("stroke")
        if not isinstance(stroke, dict):
            return
        pts = []
        for p in (stroke.get("pts") or [])[:MAX_POINTS]:
            try:
                x, y = float(p[0]), float(p[1])
            except (TypeError, ValueError, IndexError):
                return
            pts.append((min(1.0, max(0.0, x)), min(1.0, max(0.0, y))))
        if not pts:
            return
        color = stroke.get("c") if stroke.get("c") in COLORS else COLORS[0]
        erase = bool(stroke.get("erase"))
        try:
            width = max(1, min(3, int(stroke.get("w", 2))))
            sid = int(stroke.get("id", 0))
        except (TypeError, ValueError):
            return
        last = self.strokes[-1] if self.strokes else None
        if last is not None and last["id"] == sid:  # Fortsetzung desselben Strichs (kommt in Stücken)
            last["pts"].extend(pts)
            del last["pts"][:-MAX_POINTS * 4]
        else:
            self.strokes.append({"id": sid, "pts": pts, "c": color, "w": width, "erase": erase})
            del self.strokes[:-MAX_STROKES]
        self.version += 1

    # ---- Anzeigen
    def hint(self, now) -> str:
        """Lücken fürs Wort; nach der Hälfte der Zeit kommt der erste Buchstabe dazu."""
        show_first = now - self.started > self.seconds / 2
        out = []
        for i, ch in enumerate(self.word):
            out.append(ch if ch == " " or (show_first and i == 0) else "_")
        return " ".join(out)

    def scores(self):
        return dict(self.score)

    def info(self, now):
        if self.phase == "malen":
            return f"Runde {self.round} / {self.total} · Wort: {self.word} · {len(self.guessed)} / " \
                   f"{len(self.guessers())} erraten"
        return f"Runde {self.round} / {self.total}"

    def phone(self, pid, now):
        if pid not in self.score:
            return {"ui": "msg", "big": "👀", "status": "Zuschauen"}
        if self.phase == "aufloesen":
            got = pid in self.guessed or (pid == self.drawer and self.guessed)
            return {"ui": "msg", "big": self.word, "tone": "good" if got else "",
                    "status": f"{self.score[pid]} Punkte"}
        if self.phase != "malen":
            return {"ui": "msg", "big": "🎨", "status": ""}
        if pid == self.drawer:
            return {"ui": "draw", "rid": self.round, "word": self.word, "colors": COLORS,
                    "status": "Du malst – keine Buchstaben! Alle sehen es auf Monitor 2"}
        if pid in self.guessed:
            return {"ui": "msg", "big": "✅", "tone": "good", "status": f"Richtig! {self.score[pid]} Punkte"}
        return {"ui": "guess", "rid": self.round, "hint": self.hint(now),
                "status": "Was wird gemalt? Schau auf Monitor 2 und tippe es ein"}
