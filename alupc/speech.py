"""Antwort per Stimme – offline.

Zwei Wege:
- **Natürliche Stimme (Piper):** neuronale Sprachausgabe, klingt fast wie ein Mensch. Die Stimme (eine .onnx-Datei,
  20–115 MB) wird einmal von Hugging Face (rhasspy/piper-voices) heruntergeladen und läuft dann lokal.
- **System-Stimme:** Windows-Stimmen bzw. unter Linux speech-dispatcher (espeak-ng klingt roboterhaft).
Ohne heruntergeladene Piper-Stimme nimmt AluPC automatisch die System-Stimme.
"""

from __future__ import annotations

import io
import queue
import sys
import threading
import wave
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from .config import config_dir

VOICES_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/main"
# Schlüssel → (Dateiname, Anzeige, ungefähre Größe in MB)
PIPER_VOICES = {
    "thorsten": ("de_DE-thorsten-medium", "Thorsten – männlich (empfohlen)", 63),
    "thorsten_hoch": ("de_DE-thorsten-high", "Thorsten – männlich, beste Qualität", 109),
    "kerstin": ("de_DE-kerstin-low", "Kerstin – weiblich", 63),
    "ramona": ("de_DE-ramona-low", "Ramona – weiblich", 63),
    "eva": ("de_DE-eva_k-x_low", "Eva – weiblich (klein, schnell)", 20),
}
RATES = {"langsam": 1.2, "normal": 1.0, "schnell": 0.85}


def piper_available(quick: bool = False) -> bool:
    """Ist Piper da? quick=True: nur nachsehen (für die Oberfläche, spart ~0,15 s Laden)."""
    if quick and "piper" not in sys.modules:
        import importlib.util

        return importlib.util.find_spec("piper") is not None
    try:
        import piper  # noqa: F401
    except Exception:  # noqa: BLE001
        return False
    return True


def voices_dir() -> Path:
    return config_dir() / "sprache" / "stimmen"


def voice_path(key: str) -> Path:
    return voices_dir() / f"{PIPER_VOICES[key][0]}.onnx"


def voice_ready(key: str) -> bool:
    if key not in PIPER_VOICES:
        return False
    p = voice_path(key)
    return p.is_file() and p.with_suffix(".onnx.json").is_file() and p.stat().st_size > 1_000_000


def voice_url(key: str) -> str:
    name = PIPER_VOICES[key][0]
    lang, speaker, quality = name.split("-")
    return f"{VOICES_URL}/{lang.split('_')[0]}/{lang}/{speaker}/{quality}/{name}.onnx"


def download_voice(key: str, progress=None) -> Path:
    import urllib.request

    target = voice_path(key)
    target.parent.mkdir(parents=True, exist_ok=True)
    for url, dest in ((voice_url(key) + ".json", target.with_suffix(".onnx.json")), (voice_url(key), target)):
        tmp = dest.with_suffix(dest.suffix + ".part")
        with urllib.request.urlopen(url, timeout=30) as resp, open(tmp, "wb") as out:  # noqa: S310 – feste https-URL
            total = int(resp.headers.get("Content-Length") or 0)
            got = 0
            while True:
                chunk = resp.read(256 * 1024)
                if not chunk:
                    break
                out.write(chunk)
                got += len(chunk)
                if progress and dest == target:
                    progress(got, total)
        if total and got != total:
            tmp.unlink(missing_ok=True)
            raise RuntimeError("Download unvollständig")
        tmp.replace(dest)
    if not voice_ready(key):
        raise RuntimeError("Stimme unvollständig")
    return target


def synthesize(voice, text: str, rate: float = 1.0) -> bytes:
    """Text → WAV-Datei (Bytes) mit einer geladenen PiperVoice."""
    from piper import SynthesisConfig

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        voice.synthesize_wav(text, wav, syn_config=SynthesisConfig(length_scale=rate))
    return buf.getvalue()


def wav_seconds(data: bytes) -> float:
    try:
        with wave.open(io.BytesIO(data)) as w:
            return w.getnframes() / float(w.getframerate() or 1)
    except (wave.Error, EOFError):
        return 0.0


class Speaker(QObject):
    """Spricht Antworten. `speaking(Sekunden)` meldet, wie lange gerade gesprochen wird (für die Echo-Sperre:
    AluPC soll seine eigene Stimme nicht als Befehl hören)."""

    speaking = Signal(float)
    _ready = Signal(bytes, str)

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self._tts = None
        self._piper = None  # (Schlüssel, PiperVoice)
        self._jobs: queue.Queue = queue.Queue()
        self._worker: threading.Thread | None = None
        self._player = None
        self._n = 0
        self.spoken: list[str] = []  # für Tests/Anzeige
        self.last_engine = ""
        self._ready.connect(self._play_wav)

    def settings(self) -> dict:
        return self.config["voice"]

    # ------------------------------------------------------------ System-Stimme
    def _engine(self):
        if self._tts is None:
            from PySide6.QtCore import QLocale
            from PySide6.QtTextToSpeech import QTextToSpeech

            self._tts = QTextToSpeech()
            german = [loc for loc in self._tts.availableLocales() if loc.language() == QLocale.German]
            if german:
                self._tts.setLocale(german[0])
            wanted = self.settings().get("speak_voice", "")
            for v in self._tts.availableVoices():
                if wanted and v.name() == wanted:
                    self._tts.setVoice(v)
        return self._tts

    def available(self) -> bool:
        if self.piper_key():
            return True
        try:
            from PySide6.QtTextToSpeech import QTextToSpeech

            return bool(QTextToSpeech.availableEngines())
        except Exception:  # noqa: BLE001
            return False

    def voices(self) -> list[str]:
        try:
            return [v.name() for v in self._engine().availableVoices()]
        except Exception:  # noqa: BLE001
            return []

    def reload(self) -> None:
        self._tts = None
        self._piper = None

    # ------------------------------------------------------------ Piper
    def piper_key(self) -> str:
        """Gewählte und heruntergeladene Piper-Stimme – oder "" (dann System-Stimme)."""
        key = self.settings().get("tts", "thorsten")
        if key in PIPER_VOICES and piper_available() and voice_ready(key):
            return key
        return ""

    def _work(self) -> None:
        while True:
            key, text, rate = self._jobs.get()
            if key is None:
                return
            try:
                if self._piper is None or self._piper[0] != key:
                    from piper import PiperVoice

                    self._piper = (key, PiperVoice.load(str(voice_path(key))))
                data = synthesize(self._piper[1], text, rate)
                self._ready.emit(data, text)
            except Exception:  # noqa: BLE001 – dann eben mit der System-Stimme
                self._ready.emit(b"", text)

    def _play_wav(self, data: bytes, text: str) -> None:
        if not data:
            self._say_system(text)
            return
        from PySide6.QtCore import QUrl
        from PySide6.QtMultimedia import QAudioOutput, QMediaDevices, QMediaPlayer

        self._n = (self._n + 1) % 4
        path = config_dir() / "sprache" / f"antwort-{self._n}.wav"
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        except OSError:
            self._say_system(text)
            return
        if self._player is None:
            self._player = QMediaPlayer(self)
            self._audio = QAudioOutput(self)
            self._player.setAudioOutput(self._audio)
        cfg = self.config["sounds"]
        wanted = cfg.get("device", "")
        for dev in QMediaDevices.audioOutputs():
            if wanted and bytes(dev.id()).decode(errors="replace") == wanted:
                self._audio.setDevice(dev)
        self._audio.setVolume(max(0, min(100, int(cfg.get("volume", 70)))) / 100)
        self._player.stop()
        self._player.setSource(QUrl.fromLocalFile(str(path)))
        self.speaking.emit(wav_seconds(data))
        self._player.play()
        self.last_engine = "piper"

    def _say_system(self, text: str) -> None:
        try:
            tts = self._engine()
            tts.setVolume(max(0, min(100, int(self.config["sounds"].get("volume", 70)))) / 100)
            rate = RATES.get(self.settings().get("speak_rate", "normal"), 1.0)
            tts.setRate(max(-1.0, min(1.0, (1.0 - rate) * 2)))
            self.speaking.emit(0.6 + len(text) * 0.075 * rate)
            tts.say(text)
            self.last_engine = "system"
        except Exception:  # noqa: BLE001 – ohne Sprachausgabe geht es auch
            pass

    # ------------------------------------------------------------ sprechen
    def say(self, text: str, force: bool = False) -> None:
        if not text or not (force or self.settings().get("speak", True)):
            return
        self.spoken.append(text)
        del self.spoken[:-20]
        key = self.piper_key()
        if not key:
            self._say_system(text)
            return
        while not self._jobs.empty():  # Neues ersetzt, was noch nicht gesprochen wurde
            try:
                self._jobs.get_nowait()
            except queue.Empty:
                break
        self._jobs.put((key, text, RATES.get(self.settings().get("speak_rate", "normal"), 1.0)))
        if self._worker is None or not self._worker.is_alive():
            self._worker = threading.Thread(target=self._work, name="stimme", daemon=True)
            self._worker.start()
        self.speaking.emit(1.5)  # Echo-Sperre schon während des Berechnens

    def shutdown(self) -> None:
        if self._worker is not None and self._worker.is_alive():
            self._jobs.put((None, "", 1.0))
        if self._player is not None:
            self._player.stop()


def spoken_label(label: str) -> str:
    """„Schwarz an/aus“ → „Schwarz“ – kurz und natürlich zum Vorlesen."""
    for cut in (" an/aus", " Start/Pause", " Pause/Weiter", " zeigen"):
        label = label.replace(cut, "")
    return label.split(" · ")[0].replace("&", "und")

