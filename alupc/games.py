"""Minispiele: Handys sind die Controller, Monitor 2 ist das Spielfeld, gestartet wird nur am PC.

Ablauf: Kachel „Minispiele“ → Steuerfenster am PC + Lobby mit QR-Code auf Monitor 2 → jeder scannt, gibt einen
Namen ein und ist dabei → Start im Steuerfenster → 3-2-1 → Spiel → Siegertreppchen → nächstes Spiel.

Zum Mitspielen braucht das Handy nur das Stichwort der Spielrunde im QR-Code – NICHT den Code der Handy-Steuerung.
Handys können nichts starten oder umstellen. Hier steht nur die Logik (ohne Qt); gezeichnet wird in
game_source.py/game_draw.py, das Handy-Bedienfeld steht in game_page.py.
"""

from __future__ import annotations

import math
import random
import re
import secrets
import threading
import time
from typing import NamedTuple

from .games_base import TEAM_COLORS, TEAM_NAMES, Game
from .games_classic import RaceGame, ReactionGame, SnakeGame
from .games_retro import QuizGame, RpsGame, TronGame
from .games_party import (BalloonGame, DrawGame, EstimateGame, PongGame, SimonGame, StroopGame, TugGame,
                          format_number)


class GameSpec(NamedTuple):
    title: str
    short: str  # eine Zeile fürs Steuerfenster
    help: str  # Erklärung auf Monitor 2 und dem Handy
    cls: type
    opts: dict  # Name → (Beschriftung, [(Wert, Text), …], Standard)


def _category_choices():
    from .game_data import CATEGORIES

    return [(k, v) for k, v in CATEGORIES.items()]


GAMES: dict[str, GameSpec] = {
    "schaetzen": GameSpec("Schätzen", "Wer schätzt am besten?",
                          "Zahl eintippen – wer am nächsten dran ist, bekommt die meisten Punkte",
                          EstimateGame, {"fragen": ("Fragen", [(5, "5"), (8, "8"), (12, "12"), (20, "20")], 8),
                                         "kategorie": ("Thema", None, "alle")}),
    "malen": GameSpec("Malen & Raten", "Einer malt, alle raten",
                      "Wer dran ist, malt auf dem Handy – alle anderen tippen ihren Tipp ein",
                      DrawGame, {"runden": ("Runden", [(1, "1× malen"), (2, "2× malen")], 1),
                                 "zeit": ("Zeit", [(60, "60 s"), (80, "80 s"), (100, "100 s")], 80)}),
    "stroop": GameSpec("Farb-Chaos", "Farbe oder Wort? Wer falsch tippt, ist raus",
                       "Tippe die FARBE des Wortes (oder was dasteht, wenn „WORT“ angesagt wird) – falsch = raus",
                       StroopGame, {"tempo": ("Tempo", [("normal", "normal"), ("schnell", "schnell")], "normal")}),
    "simon": GameSpec("Simon sagt", "Farbfolge merken – alle gleichzeitig",
                      "Merk dir die Farben auf dem Bildschirm und tippe sie nach – ein Fehler und du bist raus",
                      SimonGame, {"tempo": ("Tempo", [("normal", "normal"), ("schnell", "schnell")], "normal")}),
    "tauziehen": GameSpec("Tauziehen", "Team Rot gegen Team Blau",
                          "So schnell tippen wie möglich – zieht das Seil auf eure Seite",
                          TugGame, {"dauer": ("Dauer", [(30, "30 s"), (45, "45 s"), (60, "60 s")], 45)}),
    "pong": GameSpec("Pong", "Teams mit bis zu 3 Schlägern",
                     "Finger hoch und runter ziehen – lass den Ball nicht durch",
                     PongGame, {"punkte": ("Bis", [(5, "5 Tore"), (7, "7 Tore"), (11, "11 Tore")], 7)}),
    "ballon": GameSpec("Ballon", "Aufpumpen – aber nicht zu weit",
                       "Pumpen bringt Punkte – „Sichern“, bevor er platzt! Alle Ballons platzen an der gleichen Stelle",
                       BalloonGame, {"runden": ("Runden", [(3, "3"), (5, "5")], 3)}),
    "schlangen": GameSpec("Schlangen-Party", "Snake für alle",
                          "Steuerkreuz oder wischen · Punkte fressen · nicht anstoßen",
                          SnakeGame, {"dauer": ("Dauer", [(60, "60 s"), (90, "90 s"), (120, "120 s")], 90)}),
    "reaktion": GameSpec("Schnellster Finger", "Bei Grün zuerst tippen",
                         "Erst rot, dann GRÜN: sofort tippen · zu früh = Minuspunkt",
                         ReactionGame, {"runden": ("Runden", [(3, "3"), (5, "5"), (8, "8")], 5)}),
    "rennen": GameSpec("Tipp-Rennen", "Wer zuerst im Ziel ist",
                       "So schnell tippen wie möglich · wer zuerst im Ziel ist, gewinnt",
                       RaceGame, {"ziel": ("Ziel", [(40, "40 Tipps"), (60, "60 Tipps"), (100, "100 Tipps")], 60)}),
    "quiz": GameSpec("Quiz", "Vier Antworten – wer weiß es zuerst?",
                     "Frage lesen, A/B/C/D tippen · richtig = Punkte, schneller = mehr",
                     QuizGame, {"fragen": ("Fragen", [(5, "5"), (10, "10"), (15, "15")], 10)}),
    "lichtrenner": GameSpec("Lichtrenner", "Leuchtspuren – wer fährt am längsten?",
                            "Steuerkreuz oder wischen · nicht gegen Spuren oder den Rand fahren",
                            TronGame, {"runden": ("Runden", [(3, "3"), (5, "5"), (7, "7")], 3)}),
    "ssp": GameSpec("Schere, Stein, Papier", "Alle gegen alle, gleichzeitig",
                    "Geheim wählen · jeder geschlagene Gegner = 1 Punkt",
                    RpsGame, {"runden": ("Runden", [(3, "3"), (5, "5"), (8, "8")], 5)}),
}

COLORS = ["#ef4444", "#3b82f6", "#22c55e", "#f59e0b", "#a855f7", "#ec4899", "#06b6d4", "#f97316", "#84cc16",
          "#eab308", "#14b8a6", "#e11d48", "#6366f1", "#10b981", "#f43f5e", "#0ea5e9"]
MAX_PLAYERS = len(COLORS)
AVATARS = ["🦊", "🐼", "🐸", "🐯", "🦁", "🐨", "🐷", "🐵", "🐙", "🦄", "🐲", "🐧", "🦉", "🐝", "🐢", "🐬",
           "🦖", "🐱", "🐶", "🐰", "🦀", "🦋", "🐻", "🐮", "🤖", "👾", "🚀", "⚽"]
# Vibration aufs Handy (Muster in ms: an, aus, an …) – nur Android-Browser können das, iPhones nicht
BUZZ = {"out": [200, 100, 200], "wrong": [150], "crash": [150], "early": [150], "hit": [30],
        "correct": [40, 60, 40], "bank": [40, 60, 40], "finish": [40, 60, 40], "burst": [300],
        "goal": [60, 40, 60], "win": [100, 60, 100, 60, 300], "go": [60]}
NAME_RE = re.compile(r"[^\w .\-!?äöüÄÖÜß]", re.UNICODE)


def option_choices(key: str, opt: str) -> list[tuple]:
    choices = GAMES[key].opts[opt][1]
    return _category_choices() if choices is None else choices


class Player:
    def __init__(self, pid: str, name: str, color: str, now: float):
        self.pid, self.name, self.color = pid, name, color
        self.seen = now
        self.joined = now
        self.team = 0
        self.avatar = ""
        self.buzz: tuple[int, list[int]] | None = None  # (Nummer, Muster) – das Handy vibriert bei neuer Nummer

    def public(self) -> dict:
        return {"name": self.name, "color": self.color}


class GameHub:
    """Spieler, Lobby und das laufende Spiel. Wird vom Webserver-Thread und vom Qt-Thread benutzt (Lock)."""

    LOBBY_TIMEOUT = 25.0  # so lange ohne Lebenszeichen → aus der Lobby
    INTRO = 3.0  # 3-2-1 vor jedem Spiel

    def __init__(self, game: str = "schaetzen", clock=time.monotonic, rng: random.Random | None = None):
        self.game_key = game if game in GAMES else "schaetzen"
        self.clock = clock
        self.rng = rng or random.Random()
        self.token = secrets.token_urlsafe(6)
        self.players: dict[str, Player] = {}
        self.phase = "lobby"  # lobby | running | over | board (Bestenliste)
        self.game: Game | None = None
        self.ranking: list[tuple[str, float]] = []
        self.intro_until = 0.0
        self.over_at = 0.0
        self.options = {k: {o: spec[2] for o, spec in g.opts.items()} for k, g in GAMES.items()}
        self.memory: dict[str, set] = {}  # pro Spiel: was in dieser Sitzung schon dran war (Fragen, Wörter)
        self.lock = threading.RLock()
        self.version = 0  # zählt bei Änderungen (Steuerfenster aktualisiert sich dann)
        # Bestenliste über den ganzen Abend: Name → Punkte (Name, weil Handys auch mal neu beitreten)
        self.board: dict[str, int] = {}
        self.board_games = 0
        self.last_award: dict[str, int] = {}
        self.board_at = 0.0
        self._buzz_n = 0
        self._buzz_seen: tuple[int, int] = (0, 0)  # (Spiel-ID, letzte Ereignisnummer)

    @property
    def spec(self) -> GameSpec:
        return GAMES[self.game_key]

    def _changed(self):
        self.version += 1

    # ---- Spieler
    def join(self, name: str, avatar: str = "") -> Player | None:
        name = NAME_RE.sub("", " ".join(str(name).split()))[:16].strip() or "Spieler"
        with self.lock:
            now = self.clock()
            if len(self.players) >= MAX_PLAYERS:
                return None
            taken = {p.name for p in self.players.values()}
            base, n = name, 2
            while name in taken:
                name = f"{base[:13]} {n}"
                n += 1
            used = {p.color for p in self.players.values()}
            color = next(c for c in COLORS if c not in used)
            player = Player(secrets.token_urlsafe(8), name, color, now)
            player.avatar = avatar if avatar in AVATARS else ""
            player.team = self._smaller_team()
            self.players[player.pid] = player
            if self.phase == "running" and self.game is not None:
                self.game.join(player.pid, player, now)
            self._changed()
            return player

    def _smaller_team(self) -> int:
        sizes = [sum(1 for p in self.players.values() if p.team == t) for t in (0, 1)]
        return 0 if sizes[0] <= sizes[1] else 1

    def kick(self, pid: str) -> bool:
        with self.lock:
            if self.players.pop(pid, None) is None:
                return False
            if self.game is not None:
                self.game.leave(pid, self.clock())
            self._changed()
            return True

    def set_team(self, pid: str, team: int) -> None:
        with self.lock:
            if pid in self.players and self.phase != "running":
                self.players[pid].team = 1 if team else 0
                self._changed()

    def shuffle_teams(self) -> None:
        with self.lock:
            pids = list(self.players)
            self.rng.shuffle(pids)
            for i, pid in enumerate(pids):
                self.players[pid].team = i % 2
            self._changed()

    def seen(self, pid: str) -> Player | None:
        with self.lock:
            p = self.players.get(pid)
            if p is not None:
                p.seen = self.clock()
            return p

    def _prune(self, now: float) -> None:
        if self.phase == "running":
            return
        gone = [pid for pid, p in self.players.items() if now - p.seen > self.LOBBY_TIMEOUT]
        for pid in gone:
            del self.players[pid]
        if gone:
            self._changed()

    # ---- Ablauf (nur vom PC aus)
    def set_game(self, key: str) -> None:
        with self.lock:
            if key in GAMES:
                self.game_key = key
            self.phase, self.game = "lobby", None
            self._changed()

    def set_option(self, opt: str, value, key: str | None = None) -> None:
        with self.lock:
            key = key or self.game_key
            if opt in GAMES[key].opts and value in [v for v, _ in option_choices(key, opt)]:
                self.options[key][opt] = value
                self._changed()

    def start(self, restart: bool = False) -> bool:
        """Spiel starten (3-2-1, dann los). Läuft schon eins, nur mit restart=True."""
        with self.lock:
            if self.phase == "running" and not restart:
                return False
            now = self.clock()
            self._prune(now)
            if not self.players:
                return False
            if self.spec.cls.teams:  # Teams ausgleichen, falls jemand gegangen ist
                sizes = [sum(1 for p in self.players.values() if p.team == t) for t in (0, 1)]
                while abs(sizes[0] - sizes[1]) > 1:
                    big = 0 if sizes[0] > sizes[1] else 1
                    mover = max((p for p in self.players.values() if p.team == big), key=lambda p: p.joined)
                    mover.team = 1 - big
                    sizes[big] -= 1
                    sizes[1 - big] += 1
            self.intro_until = now + self.INTRO
            opts = dict(self.options[self.game_key])
            opts["_mem"] = self.memory.setdefault(self.game_key, set())
            self.game = self.spec.cls(dict(self.players), self.intro_until, self.rng, opts)
            self.phase = "running"
            self.ranking = []
            self._changed()
            return True

    def next(self) -> bool:
        """„Weiter“: nächste Frage, nächstes Bild, nächste Runde."""
        with self.lock:
            now = self.clock()
            if self.phase != "running" or self.game is None or now < self.intro_until:
                return False
            ok = self.game.skip(now)
            self._changed()
            return ok

    def finish(self) -> None:
        """Spiel sofort beenden und Ergebnis zeigen."""
        with self.lock:
            if self.phase == "running" and self.game is not None:
                self.game.over = True
                self.intro_until = min(self.intro_until, self.clock())
                self.tick()

    def to_lobby(self) -> None:
        with self.lock:
            self.phase, self.game = "lobby", None
            self._changed()

    def input(self, pid: str, data: dict) -> bool:
        with self.lock:
            if pid not in self.players:
                return False
            now = self.clock()
            self.players[pid].seen = now
            if self.phase == "running" and self.game is not None and now >= self.intro_until:
                self.game.input(pid, data, now)
            return True

    def tick(self) -> None:
        with self.lock:
            now = self.clock()
            self._prune(now)
            if self.phase == "running" and self.game is not None and now >= self.intro_until:
                self.game.update(now)
                self._buzz_events()
                if self.game.over:
                    scores = self.game.scores()
                    self.ranking = sorted(scores.items(), key=lambda kv: -kv[1])
                    self.phase = "over"
                    self.over_at = now
                    self._award()
                    self._buzz_winners()
                    self._changed()

    # ---- Vibration
    def buzz(self, pid: str, kind: str) -> None:
        pl = self.players.get(pid)
        if pl is not None and kind in BUZZ:
            self._buzz_n += 1
            pl.buzz = (self._buzz_n, BUZZ[kind])

    def _buzz_events(self) -> None:
        game = self.game
        gid, last = self._buzz_seen
        if gid != id(game):
            last = 0
        for n, _t, kind, data in game.events:
            if n <= last:
                continue
            if "pid" in data:
                self.buzz(data["pid"], kind)
            elif kind == "goal":  # Tor: das Team, das getroffen hat
                for pid, pl in self.players.items():
                    if pl.team == data.get("team"):
                        self.buzz(pid, "goal")
            elif kind == "go":  # Reaktion: GRÜN
                for pid in self.players:
                    self.buzz(pid, "go")
        self._buzz_seen = (id(game), game.event_n)

    def _buzz_winners(self) -> None:
        if self.spec.cls.teams:
            win = self.team_result()
            winners = [pid for pid, pl in self.players.items() if win is not None and pl.team == win]
        else:
            winners = [pid for pid, _s in self.ranking if self.place_of(pid) == 1]
        for pid in winners:
            self.buzz(pid, "win")

    # ---- Bestenliste über den Abend
    PLACE_POINTS = [10, 7, 5, 4, 3, 2]  # ab Platz 7: 1 Punkt fürs Mitmachen
    TEAM_POINTS = {"win": 6, "lose": 2, "tie": 4}

    def award_for(self) -> dict[str, int]:
        """Punkte für die Bestenliste aus dem gerade beendeten Spiel (Name → Punkte)."""
        out: dict[str, int] = {}
        if self.spec.cls.teams:
            win = self.team_result()
            for pid, _score in self.ranking:
                pl = self.players.get(pid)
                if pl is None:
                    continue
                kind = "tie" if win is None else ("win" if pl.team == win else "lose")
                out[pl.name] = self.TEAM_POINTS[kind]
            return out
        for pid, _score in self.ranking:
            pl = self.players.get(pid)
            place = self.place_of(pid)
            if pl is None or place is None:
                continue
            out[pl.name] = self.PLACE_POINTS[place - 1] if place <= len(self.PLACE_POINTS) else 1
        return out

    def _award(self) -> None:
        self.last_award = self.award_for()
        for name, pts in self.last_award.items():
            self.board[name] = self.board.get(name, 0) + pts
        if self.last_award:
            self.board_games += 1

    def board_ranking(self) -> list[tuple[str, int, int]]:
        """[(Name, Punkte, Platz)] – gleiche Punkte = gleicher Platz."""
        rows = sorted(self.board.items(), key=lambda kv: (-kv[1], kv[0].lower()))
        return [(name, pts, 1 + sum(1 for v in self.board.values() if v > pts)) for name, pts in rows]

    def show_board(self) -> None:
        """Bestenliste auf Monitor 2 (bricht ein laufendes Spiel nicht ab – erst „Ergebnis“ oder „Lobby“)."""
        with self.lock:
            if self.phase == "running":
                return
            self.phase, self.game = "board", None
            self.board_at = self.clock()
            self._changed()

    def reset_board(self) -> None:
        with self.lock:
            self.board, self.board_games, self.last_award = {}, 0, {}
            self._changed()

    def color_of_name(self, name: str) -> str:
        return next((p.color for p in self.players.values() if p.name == name), "#64748b")

    def avatar_of_name(self, name: str) -> str:
        return next((p.avatar for p in self.players.values() if p.name == name), "")

    def place_of(self, pid: str) -> int | None:
        """Platz 1, 2, … (Gleichstand = gleicher Platz)."""
        scores = dict(self.ranking)
        if pid not in scores:
            return None
        return 1 + sum(1 for s in scores.values() if s > scores[pid])

    def team_result(self) -> int | None:
        return getattr(self.game, "winner", None)

    # ---- Anzeige auf dem Handy
    def state_for(self, pid: str) -> dict:
        with self.lock:
            now = self.clock()
            p = self.players.get(pid)
            spec = self.spec
            data = {"game": self.game_key, "title": spec.title, "help": spec.help, "phase": self.phase,
                    "players": len(self.players), "joined": p is not None}
            if p is None:
                return data
            color = p.color
            if spec.cls.teams and self.phase != "lobby":
                color = TEAM_COLORS[p.team]
            data.update(name=p.name, color=color, avatar=p.avatar, buzz=list(p.buzz) if p.buzz else None)
            board_line = ""
            if self.board.get(p.name):
                place = next((pl for n, _pts, pl in self.board_ranking() if n == p.name), None)
                board_line = f"Gesamt: Platz {place} · {self.board[p.name]} Punkte"
            if self.phase == "board":
                place = next((pl for n, _pts, pl in self.board_ranking() if n == p.name), None)
                data["ui"] = {"ui": "msg", "big": f"Platz {place}" if place else "–",
                              "tone": "good" if place == 1 else "",
                              "status": f"Bestenliste · {self.board.get(p.name, 0)} Punkte nach {self.board_games} "
                                        f"{'Spiel' if self.board_games == 1 else 'Spielen'}"}
            elif self.phase == "lobby":
                team = f" · {TEAM_NAMES[p.team]}" if spec.cls.teams else ""
                data["ui"] = {"ui": "msg", "big": "Du bist dabei!", "status": f"Warte auf den Start am PC{team}"}
            elif self.phase == "running" and now < self.intro_until:
                data["ui"] = {"ui": "msg", "big": str(max(1, math.ceil(self.intro_until - now))), "status": spec.title}
            elif self.phase == "running" and self.game is not None:
                if not self.game.plays(pid):
                    data["ui"] = {"ui": "msg", "big": "👀", "status": "Zuschauen – nächstes Spiel bist du dabei"}
                else:
                    data["ui"] = self.game.phone(pid, now)
            else:
                place = self.place_of(pid)
                if spec.cls.teams:
                    win = self.team_result()
                    big = "Unentschieden" if win is None else ("Gewonnen!" if win == p.team else "Verloren")
                    data["ui"] = {"ui": "msg", "big": big, "tone": "good" if win == p.team else "",
                                  "status": TEAM_NAMES[p.team] + (f" · {board_line}" if board_line else "")}
                else:
                    data["ui"] = {"ui": "msg", "big": f"Platz {place}" if place else "–",
                                  "tone": "good" if place == 1 else "",
                                  "status": f"von {len(self.ranking)}" + (f" · {board_line}" if board_line else "")}
            return data


__all__ = ["AVATARS", "GAMES", "GameHub", "Player", "MAX_PLAYERS", "COLORS", "TEAM_COLORS", "TEAM_NAMES", "format_number",
           "option_choices", "SnakeGame", "ReactionGame", "RaceGame", "EstimateGame", "DrawGame", "StroopGame",
           "SimonGame", "TugGame", "PongGame", "BalloonGame"]
