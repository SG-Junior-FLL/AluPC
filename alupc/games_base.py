"""Gemeinsame Grundlage aller Minispiele (ohne Qt).

Jedes Spiel bekommt die Spieler (pid → Player), die Startzeit, einen Zufallsgenerator und die Einstellungen aus dem
Steuerfenster. Es kennt nur Zeitpunkte, die man ihm gibt – dadurch lässt es sich mit einer festen Uhr testen.
"""

from __future__ import annotations

import random

TEAM_COLORS = ["#ef4444", "#3b82f6"]
TEAM_NAMES = ["Team Rot", "Team Blau"]


class Game:
    teams = False  # Mannschaftsspiel (Player.team = 0 oder 1)
    late_join = True  # dürfen Neue mitten im Spiel einsteigen?

    def __init__(self, players: dict, now: float, rng: random.Random | None = None, opts: dict | None = None):
        self.rng = rng or random.Random()
        self.opts = dict(opts or {})
        self.players = dict(players)
        self.over = False
        self.events: list[tuple[int, float, str, dict]] = []  # für Effekte auf Monitor 2
        self.event_n = 0

    # ---- Ereignisse (Monitor 2 zeigt dazu Effekte)
    def emit(self, now: float, kind: str, **data) -> None:
        self.event_n += 1
        self.events.append((self.event_n, now, kind, data))
        if len(self.events) > 120:
            del self.events[:40]

    # ---- Spieler kommen und gehen
    def join(self, pid: str, player, now: float) -> bool:
        if not self.late_join:
            return False
        self.players[pid] = player
        return True

    def leave(self, pid: str, now: float) -> None:
        self.players.pop(pid, None)

    def plays(self, pid: str) -> bool:
        return pid in self.players

    # ---- Ablauf
    def input(self, pid: str, data: dict, now: float) -> None:
        pass

    def update(self, now: float) -> None:
        pass

    def skip(self, now: float) -> bool:
        """„Weiter“ im Steuerfenster (nächste Frage, nächstes Wort …). False = gibt es hier nicht."""
        return False

    def scores(self) -> dict[str, float]:
        return {pid: 0 for pid in self.players}

    def info(self, now: float) -> str:
        """Kurzer Stand fürs Steuerfenster."""
        return ""

    def phone(self, pid: str, now: float) -> dict:
        return {"ui": "msg", "big": "", "status": ""}

    def team_of(self, pid: str) -> int:
        return int(getattr(self.players.get(pid), "team", 0) or 0)


def clock_text(seconds: float) -> str:
    seconds = max(0, int(seconds + 0.999))
    return f"{seconds // 60}:{seconds % 60:02d}"
