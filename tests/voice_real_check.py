"""Echte Sprach-Kette in der CI (braucht Internet für die Modelle):

Piper spricht Sätze → Vosk (Startwort, wie im Betrieb) → Whisper (genau) → AluPC versteht → Befehl.
Ohne Mikrofon: der Ton geht direkt in dieselbe Auswertung (VoiceControl._handle), die auch das Mikrofon nutzt.
Aufruf: python tests/voice_real_check.py   (Ergebnis als ::notice-Zeilen, Fehler → Exit 1)
"""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import time
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
tmp = tempfile.mkdtemp(prefix="alupc-voice-")
os.environ["XDG_CONFIG_HOME"] = tmp
os.environ["APPDATA"] = tmp

import numpy as np  # noqa: E402
from PySide6.QtCore import QCoreApplication  # noqa: E402

from alupc import speech, stt, voice  # noqa: E402
from alupc.config import Config  # noqa: E402

app = QCoreApplication([])
for stream in (sys.stdout, sys.stderr):  # Windows-Konsole: sonst scheitern „“ und Umlaute
    try:
        stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
SENTENCES = [
    ("Alu PC, mach bitte den Bildschirm schwarz.", "schwarz_an"),
    ("Alu PC, Licht auf blau.", "rgb_farbe:#0000ff"),
    ("Alu PC, wie spät ist es?", "frage:uhrzeit"),
    ("Alu PC, stell einen Timer auf fünf Minuten.", "timer_set:300"),
    ("Alu PC, zeig mir die Kamera.", "kamera"),
    ("Alu PC, schalte den Bildschirmschoner aus.", "bildschirmschoner_aus"),
]


def note(text: str) -> None:
    print(f"::notice title=Sprache echt::{text}", flush=True)


def to_16k(wav_bytes: bytes) -> bytes:
    with wave.open(io.BytesIO(wav_bytes)) as w:
        rate = w.getframerate()
        pcm = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    pcm = stt.resample(pcm, rate, 16000)
    pcm = np.concatenate([np.zeros(8000, np.float32), pcm, np.zeros(16000, np.float32)])  # Pausen davor/danach
    return (np.clip(pcm, -1, 1) * 32767).astype(np.int16).tobytes()


def vosk_text(rec, pcm: bytes) -> str:
    texts = []
    for i in range(0, len(pcm), 4000):
        if rec.AcceptWaveform(pcm[i:i + 4000]):
            texts.append(json.loads(rec.Result()).get("text", ""))
    texts.append(json.loads(rec.FinalResult()).get("text", ""))
    return " ".join(t for t in texts if t)


def main() -> int:
    t0 = time.time()
    speech.download_voice("thorsten")
    note(f"Piper-Stimme Thorsten geladen ({time.time() - t0:.0f} s)")
    voice.download_model()
    stt.download("base")
    note(f"Vosk-Modell und Whisper Base geladen ({time.time() - t0:.0f} s)")
    from piper import PiperVoice

    piper_voice = PiperVoice.load(str(speech.voice_path("thorsten")))
    import vosk

    vosk.SetLogLevel(-1)
    model = vosk.Model(str(voice.model_dir()))
    config = Config(Path(tmp) / "c.json")
    config["voice"] = {**config["voice"], "stt": "base"}
    vc = voice.VoiceControl(config)
    vc.load_stt()
    assert vc.stt is not None, f"Whisper nicht geladen: {vc.stt_error}"
    got: list[str] = []
    vc.command.connect(lambda c, _l, _t: got.append(c))
    vc.not_understood.connect(lambda t: got.append(f"?{t}"))
    heard: list[str] = []
    vc.heard.connect(heard.append)
    ok_whisper = ok_vosk = ok_wake = 0
    for sentence, expected in SENTENCES:
        t1 = time.time()
        wav = speech.synthesize(piper_voice, sentence)
        tts_s = time.time() - t1
        pcm = to_16k(wav)
        text = vosk_text(vosk.KaldiRecognizer(model, 16000), pcm)
        wake = voice.wake_span(voice.fold(text).split()) is not None
        ok_wake += wake
        # nur Vosk (Standard-Erkennung)
        stt_saved, vc.stt = vc.stt, None
        got.clear()
        vc._handle(text, None, 0, pcm)
        vosk_cmd = got[-1] if got else "-"
        ok_vosk += vosk_cmd == expected
        # mit Whisper (Mikrofon-Schalter an, damit nur das Verstehen zählt – das Startwort prüft „wake“)
        vc.stt = stt_saved
        vc.direct = True
        got.clear()
        heard.clear()
        t2 = time.time()
        vc._handle(text or "?", None, 0, pcm)
        whisper_s = time.time() - t2
        vc.direct = False
        whisper_cmd = got[-1] if got else "-"
        ok_whisper += whisper_cmd == expected
        exact = next((h for h in heard if "(genau)" in h), "")
        note(f"„{sentence}“ → Vosk: „{text}“ (Startwort {'ja' if wake else 'NEIN'}) = {vosk_cmd} · Whisper: {exact} = {whisper_cmd} "
             f"(erwartet {expected}; Stimme {tts_s:.1f} s, Whisper {whisper_s:.1f} s)")
    n = len(SENTENCES)
    note(f"Richtig verstanden: mit Whisper {ok_whisper}/{n}, nur Vosk {ok_vosk}/{n} · Startwort von Vosk gehört {ok_wake}/{n}")
    if ok_whisper < len(SENTENCES) - 1:
        print(f"::error title=Sprache echt::Whisper hat nur {ok_whisper}/{len(SENTENCES)} richtig", flush=True)
        return 1
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # noqa: BLE001 – Grund als Hinweis im CI-Lauf sichtbar machen
        import traceback

        for line in traceback.format_exc().strip().splitlines()[-12:]:
            print(f"::error title=Sprache echt::{line.strip()}", flush=True)
        sys.exit(1)
