"""Töne bei Aktionen: eingebaute Klänge oder eigene, hochgeladene Dateien (WAV, MP3, OGG …)."""

from __future__ import annotations

import math
import shutil
import struct
import wave
from pathlib import Path

from .config import config_dir

# Ereignis → Anzeigename (Reihenfolge = Reihenfolge im Setup)
EVENTS = {
    "inhalt": "Neuer Inhalt auf Monitor 2",
    "szene": "Szene gewechselt",
    "standbild_an": "Standbild an",
    "standbild_aus": "Standbild aus",
    "schwarz_an": "Schwarz (Sichtschutz) an",
    "schwarz_aus": "Schwarz (Sichtschutz) aus",
    "schoner_an": "Bildschirmschoner startet",
    "schoner_aus": "Bildschirmschoner endet",
    "timer_start": "Timer startet",
    "timer_pause": "Timer pausiert",
    "timer_minute": "Timer: noch 1 Minute",
    "timer_ende": "Timer abgelaufen",
    "kachel": "Eigene Kachel (ohne eigenen Ton)",
}

# Eingebaute Klänge werden beim ersten Gebrauch als kleine WAV-Dateien erzeugt
BUILTIN = {
    "ding": "Ding",
    "gong": "Gong",
    "klick": "Klick",
    "piep": "Doppel-Piep",
    "hoch": "Aufsteigend",
    "runter": "Absteigend",
    "alarm": "Alarm",
}

RATE = 22050


def _tone(freqs, duration, decay=6.0, volume=0.6):
    """Einfacher Klang: Summe von Sinustönen mit ausklingender Lautstärke."""
    n = int(RATE * duration)
    out = []
    for i in range(n):
        t = i / RATE
        env = math.exp(-decay * t) * min(1.0, t * 200)  # kurzer Einschwung gegen Knacken
        v = sum(math.sin(2 * math.pi * f * t) * a for f, a in freqs)
        out.append(v * env * volume)
    return out


def _silence(duration):
    return [0.0] * int(RATE * duration)


def _synth(name: str) -> list[float]:
    if name == "ding":
        return _tone([(1318.5, 0.7), (2637, 0.2)], 1.0, 5)
    if name == "gong":
        return _tone([(196, 0.6), (392, 0.3), (587, 0.15)], 2.2, 2.2)
    if name == "klick":
        return _tone([(2000, 0.8), (3500, 0.3)], 0.06, 60)
    if name == "piep":
        return _tone([(1000, 0.7)], 0.12, 8) + _silence(0.08) + _tone([(1000, 0.7)], 0.12, 8)
    if name == "hoch":
        return _tone([(660, 0.6)], 0.14, 10) + _tone([(880, 0.6)], 0.14, 10) + _tone([(1320, 0.6)], 0.3, 8)
    if name == "runter":
        return _tone([(1320, 0.6)], 0.14, 10) + _tone([(880, 0.6)], 0.14, 10) + _tone([(660, 0.6)], 0.3, 8)
    if name == "alarm":
        seq = []
        for _ in range(4):
            seq += _tone([(880, 0.7)], 0.18, 4) + _tone([(660, 0.7)], 0.18, 4)
        return seq
    if name.startswith("spiel-"):
        return _game_sound(name[6:])
    return _tone([(880, 0.6)], 0.3, 8)


SIMON_FREQ = [415.3, 310.0, 252.0, 209.0]  # grün, rot, gelb, blau – die Töne des alten Simon-Spiels


def _noise(duration, decay=18.0, volume=0.6, seed=7):
    import random

    rnd = random.Random(seed)
    n = int(RATE * duration)
    return [rnd.uniform(-1, 1) * math.exp(-decay * i / RATE) * volume for i in range(n)]


def _game_sound(kind: str) -> list[float]:
    """Klänge für die Minispiele (kurz, damit sie bei schnellen Spielen nicht stören)."""
    if kind == "tick":
        return _tone([(880, 0.6)], 0.09, 14)
    if kind == "los":
        return _tone([(1320, 0.6), (2640, 0.15)], 0.35, 6)
    if kind == "blip":
        return _tone([(1568, 0.4)], 0.05, 40)
    if kind == "richtig":
        return _tone([(988, 0.5)], 0.08, 14) + _tone([(1319, 0.55)], 0.22, 9)
    if kind == "falsch":
        return _tone([(196, 0.5), (207.7, 0.4)], 0.35, 5)
    if kind == "raus":
        return _tone([(523, 0.5)], 0.12, 10) + _tone([(392, 0.5)], 0.12, 10) + _tone([(262, 0.55)], 0.35, 6)
    if kind == "plopp":
        return _noise(0.25, 20, 0.8)
    if kind == "treffer":
        return _tone([(660, 0.5), (1320, 0.2)], 0.06, 30)
    if kind == "tor":
        return _noise(0.12, 25, 0.4) + _tone([(784, 0.5)], 0.1, 10) + _tone([(1047, 0.55)], 0.3, 6)
    if kind == "sieg":
        notes = [(523.3, 0.12), (659.3, 0.12), (784.0, 0.12), (1046.5, 0.45)]
        out = []
        for f, d in notes:
            out += _tone([(f, 0.5), (f * 2, 0.12)], d, 3 if d > 0.3 else 8)
        return out
    if kind.startswith("simon") and kind[5:].isdigit():
        return _tone([(SIMON_FREQ[int(kind[5:]) % 4], 0.6), (SIMON_FREQ[int(kind[5:]) % 4] * 2, 0.15)], 0.32, 4)
    return _tone([(880, 0.6)], 0.1, 10)


def sounds_dir() -> Path:
    d = config_dir() / "sounds"
    d.mkdir(parents=True, exist_ok=True)
    return d


def builtin_path(name: str) -> Path:
    path = sounds_dir() / f"eingebaut-{name}.wav"
    if not path.exists():
        samples = _synth(name)
        with wave.open(str(path), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(RATE)
            w.writeframes(b"".join(struct.pack("<h", int(max(-1, min(1, s)) * 32000)) for s in samples))
    return path


def resolve(spec: str) -> Path | None:
    """„builtin:ding“ → Datei, sonst Pfad zu einer (hochgeladenen) Datei."""
    if not spec:
        return None
    if spec.startswith("builtin:"):
        return builtin_path(spec.split(":", 1)[1])
    path = Path(spec)
    return path if path.exists() else None


def upload(source: str) -> str:
    """Tondatei in den AluPC-Ordner kopieren (bleibt, auch wenn das Original gelöscht wird)."""
    src = Path(source)
    target = sounds_dir() / src.name
    i = 2
    while target.exists() and target.resolve() != src.resolve():
        target = sounds_dir() / f"{src.stem}-{i}{src.suffix}"
        i += 1
    if target.resolve() != src.resolve():
        shutil.copy2(src, target)
    return str(target)


def uploaded_files() -> list[Path]:
    return sorted(p for p in sounds_dir().iterdir() if p.is_file() and not p.name.startswith("eingebaut-"))


def describe(spec: str) -> str:
    if not spec:
        return "Kein Ton"
    if spec.startswith("builtin:"):
        return "♪ " + BUILTIN.get(spec.split(":", 1)[1], spec)
    return "♫ " + Path(spec).name


class SoundPlayer:
    """Spielt Töne ab (mehrere gleichzeitig möglich), mit Lautstärke und Ausgabegerät."""

    def __init__(self, config):
        self.config = config
        self._players = []
        self.last_played: str | None = None  # für Tests

    def settings(self) -> dict:
        return self.config["sounds"]

    def play_event(self, event: str, override: str | None = None) -> None:
        cfg = self.settings()
        if not cfg.get("enabled", True):
            return
        spec = override if override else cfg.get("events", {}).get(event, "")
        self.play(spec)

    def play(self, spec: str) -> None:
        path = resolve(spec)
        if path is None:
            return
        self.last_played = spec
        try:
            from PySide6.QtCore import QUrl
            from PySide6.QtMultimedia import QAudioOutput, QMediaDevices, QMediaPlayer
        except ImportError:
            return
        cfg = self.settings()
        player = QMediaPlayer()
        audio = QAudioOutput()
        wanted = cfg.get("device", "")
        if wanted:
            for dev in QMediaDevices.audioOutputs():
                if bytes(dev.id()).decode(errors="replace") == wanted:
                    audio.setDevice(dev)
                    break
        audio.setVolume(max(0, min(100, int(cfg.get("volume", 70)))) / 100)
        player.setAudioOutput(audio)
        player.setSource(QUrl.fromLocalFile(str(path)))
        entry = (player, audio)
        self._players.append(entry)

        def cleanup(*_):
            if entry in self._players and player.playbackState() == QMediaPlayer.StoppedState:
                self._players.remove(entry)
                player.deleteLater()
                audio.deleteLater()

        player.playbackStateChanged.connect(cleanup)
        player.errorOccurred.connect(lambda *_: cleanup())
        # nicht unbegrenzt viele gleichzeitig
        while len(self._players) > 6:
            old_player, old_audio = self._players.pop(0)
            old_player.stop()
            old_player.deleteLater()
            old_audio.deleteLater()
        player.play()
