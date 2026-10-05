"""Minispiele (3): Schere, Stein, Papier."""

from __future__ import annotations

from .games_base import Game

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

