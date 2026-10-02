"""Genaue Erkennung mit Whisper (faster-whisper, offline, optional).

Vosk hört die ganze Zeit mit (schnell, wenig Rechenleistung) und erkennt das Startwort. Ist ein Satz für AluPC
gemeint (Startwort gehört, Mikrofon-Schalter an oder kurz nach einer Antwort), schreibt Whisper genau diesen Satz
noch einmal sauber mit – das versteht deutlich mehr Wörter und ganze Sätze. Das Modell wird einmal von Hugging Face
heruntergeladen (Systran/faster-whisper-…) und läuft dann lokal auf dem Prozessor; kein Ton geht ins Internet.
"""

from __future__ import annotations

import os
from pathlib import Path

from .config import config_dir

# Schlüssel → (Repository, Anzeige, ungefähre Größe in MB)
MODELS = {
    "base": ("Systran/faster-whisper-base", "Genau (Whisper Base)", 145),
    "small": ("Systran/faster-whisper-small", "Sehr genau (Whisper Small)", 485),
}
FILES = ("config.json", "tokenizer.json", "vocabulary.txt", "model.bin")
# Wörter, die AluPC oft hört – hilft Whisper bei Namen und Fachwörtern
PROMPT = ("Alu PC, Monitor, Bildschirm schwarz, Standbild, Bildschirmschoner, Kamera, Glücksrad, Whiteboard, "
          "RGB-Licht, Timer, Overlays, Minispiele, Szene, Wetter, AirPlay.")


def available() -> bool:
    try:
        import faster_whisper  # noqa: F401
    except Exception:  # noqa: BLE001 – auch kaputte Bibliothek = nicht verfügbar
        return False
    return True


def model_dir(name: str) -> Path:
    return config_dir() / "sprache" / f"whisper-{name}"


def ready(name: str, path: Path | None = None) -> bool:
    if name not in MODELS:
        return False
    path = path or model_dir(name)
    return all((path / f).is_file() and (path / f).stat().st_size > 0 for f in FILES)


def download(name: str, progress=None, base_url: str = "https://huggingface.co") -> Path:
    """Alle Dateien des Modells laden. progress(fertig_bytes, gesamt_bytes) – gesamt ist geschätzt."""
    import urllib.request

    repo, _label, size_mb = MODELS[name]
    target = model_dir(name)
    target.mkdir(parents=True, exist_ok=True)
    total_guess = size_mb * 1024 * 1024
    done_before = 0
    for f in FILES:
        dest = target / f
        if dest.is_file() and dest.stat().st_size > 0:
            done_before += dest.stat().st_size
            continue
        tmp = dest.with_suffix(dest.suffix + ".part")
        url = f"{base_url}/{repo}/resolve/main/{f}"
        with urllib.request.urlopen(url, timeout=30) as resp, open(tmp, "wb") as out:  # noqa: S310 – feste https-URL
            length = int(resp.headers.get("Content-Length") or 0)
            got = 0
            while True:
                chunk = resp.read(512 * 1024)
                if not chunk:
                    break
                out.write(chunk)
                got += len(chunk)
                if progress:
                    progress(done_before + got, max(total_guess, done_before + got))
        if length and got != length:
            tmp.unlink(missing_ok=True)
            raise RuntimeError("Download unvollständig")
        tmp.replace(dest)
        done_before += got
    if not ready(name):
        raise RuntimeError("Whisper-Modell unvollständig")
    return target


class WhisperSTT:
    """Ein geladenes Whisper-Modell. transcribe() ist langsam (≈ 0,3–2 s) – nur im Hintergrund-Thread aufrufen."""

    def __init__(self, name: str, path: Path | None = None):
        from faster_whisper import WhisperModel

        threads = max(1, min(4, (os.cpu_count() or 2) - 1))
        self.name = name
        self.model = WhisperModel(str(path or model_dir(name)), device="cpu", compute_type="int8",
                                  cpu_threads=threads)

    def transcribe(self, pcm16: bytes, rate: int = 16000) -> str:
        import numpy as np

        audio = np.frombuffer(pcm16, dtype=np.int16).astype(np.float32) / 32768.0
        if rate != 16000:
            audio = resample(audio, rate, 16000)
        if audio.size < 16000 * 0.3:
            return ""
        segments, _info = self.model.transcribe(audio, language="de", beam_size=3, vad_filter=False,
                                                condition_on_previous_text=False, without_timestamps=True,
                                                initial_prompt=PROMPT)
        parts = []
        for seg in segments:
            if getattr(seg, "no_speech_prob", 0) > 0.7:
                continue
            parts.append(seg.text)
        return " ".join(p.strip() for p in parts).strip()


def resample(audio, src: int, dst: int):
    """Einfaches lineares Umrechnen der Abtastrate (für Sprache gut genug)."""
    import numpy as np

    if src == dst or audio.size == 0:
        return audio
    n = int(round(audio.size * dst / src))
    x_old = np.linspace(0, 1, audio.size, endpoint=False)
    x_new = np.linspace(0, 1, n, endpoint=False)
    return np.interp(x_new, x_old, audio).astype(np.float32)
