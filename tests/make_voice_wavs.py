"""Für den Sprachtest der fertigen Version: Vosk-Modell laden und Sätze mit Piper als WAV sprechen.
Aufruf: python tests/make_voice_wavs.py ZIELORDNER   (XDG_CONFIG_HOME bestimmt, wohin das Modell kommt)"""

import io
import sys
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from alupc import speech, voice  # noqa: E402

SENTENCES = ["Alu PC, mach bitte den Bildschirm schwarz.", "Alu PC, Licht auf blau.",
             "Alu PC, wie spät ist es?", "Alu PC, stell einen Timer auf fünf Minuten."]


def main(target: str) -> None:
    from piper import PiperVoice

    out = Path(target)
    out.mkdir(parents=True, exist_ok=True)
    voice.download_model()
    speech.download_voice("thorsten")
    pv = PiperVoice.load(str(speech.voice_path("thorsten")))
    for i, sentence in enumerate(SENTENCES, 1):
        with wave.open(io.BytesIO(speech.synthesize(pv, sentence))) as w:
            params, frames = w.getparams(), w.readframes(w.getnframes())
        with wave.open(str(out / f"satz{i}.wav"), "wb") as f:  # 1,5 s Stille danach: Satzende für Vosk
            f.setparams(params)
            f.writeframes(frames + b"\0" * int(params.sampwidth * params.nchannels * params.framerate * 1.5))
        print(out / f"satz{i}.wav", sentence)


if __name__ == "__main__":
    main(sys.argv[1])
