"""Töne der Minispiele (am PC): 3-2-1, Los, richtig/falsch, raus, Plopp, Treffer, Tor, Sieger-Fanfare, Simon-Töne.

Die Klänge werden einmal erzeugt (sounds.py) und mit QSoundEffect abgespielt – das ist schnell genug für Pong.
An/aus im Steuerfenster („Töne“); Lautstärke und Ausgabegerät wie bei den anderen AluPC-Tönen (Setup → Töne).
"""

from __future__ import annotations

import math
import time

# Ereignis eines Spiels → Ton
EVENT_SOUNDS = {
    "guess": "blip", "reveal": "richtig", "correct": "richtig", "out": "raus", "allfail": "falsch",
    "wrong": "falsch", "go": "los", "early": "falsch", "hit": "treffer", "goal": "tor", "burst": "plopp",
    "bank": "richtig", "eat": "blip", "crash": "falsch", "finish": "richtig", "word": "tick", "score": "blip",
}


class GameSounds:
    def __init__(self, config, player=None):
        self.config = config
        self.player = player  # sounds.SoundPlayer (für Lautstärke/Gerät)
        self._effects = {}
        self._last_played: dict[str, float] = {}
        self.played: list[str] = []  # für Tests
        self._game_id = None
        self._event_n = 0
        self._phase = None
        self._intro_n = None
        self._players = 0
        self._lit = None

    def enabled(self) -> bool:
        return bool(self.config["games"].get("sound", True))

    # ------------------------------------------------------------ Abspielen
    def play(self, kind: str, now: float | None = None) -> None:
        now = time.monotonic() if now is None else now
        if now - self._last_played.get(kind, -9) < 0.06:  # nicht 10× im selben Augenblick
            return
        self._last_played[kind] = now
        self.played.append(kind)
        del self.played[:-50]
        if not self.enabled():
            return
        try:
            effect = self._effects.get(kind)
            if effect is None:
                from PySide6.QtCore import QUrl
                from PySide6.QtMultimedia import QMediaDevices, QSoundEffect

                from .sounds import builtin_path

                effect = QSoundEffect()
                effect.setSource(QUrl.fromLocalFile(str(builtin_path(f"spiel-{kind}"))))
                cfg = self.config["sounds"]
                wanted = cfg.get("device", "")
                if wanted:
                    for dev in QMediaDevices.audioOutputs():
                        if bytes(dev.id()).decode(errors="replace") == wanted:
                            effect.setAudioDevice(dev)
                            break
                self._effects[kind] = effect
            effect.setVolume(max(0, min(100, int(self.config["sounds"].get("volume", 70)))) / 100)
            effect.play()
        except Exception:  # noqa: BLE001 – ohne Ton geht das Spiel trotzdem
            pass

    # ------------------------------------------------------------ Was ist passiert?
    def update(self, hub) -> None:
        """Wird mit der Spiel-Uhr aufgerufen (≈30× pro Sekunde) und spielt passende Töne."""
        with hub.lock:
            now = hub.clock()
            phase = hub.phase
            if phase == "lobby" and len(hub.players) > self._players:
                self.play("blip", now)
            self._players = len(hub.players)
            if phase != self._phase:
                if phase in ("over", "board") and self._phase is not None:
                    self.play("sieg", now)
                self._phase = phase
            game = hub.game
            if game is None or phase != "running":
                self._game_id = None
                return
            if id(game) != self._game_id:
                self._game_id, self._event_n, self._intro_n, self._lit = id(game), game.event_n, None, None
            if now < hub.intro_until:  # 3 – 2 – 1
                n = max(1, math.ceil(hub.intro_until - now))
                if n != self._intro_n:
                    self._intro_n = n
                    self.play("tick", now)
                return
            if self._intro_n is not None:  # gerade losgegangen
                self._intro_n = None
                self.play("los", now)
            for n, _t, kind, _data in game.events:
                if n > self._event_n and kind in EVENT_SOUNDS:
                    self.play(EVENT_SOUNDS[kind], now)
            self._event_n = game.event_n
            lit = game.lit(now) if hasattr(game, "lit") else None  # Simon: Ton zur leuchtenden Farbe
            if lit is not None and lit != self._lit:
                self.play(f"simon{lit}", now)
            self._lit = lit
