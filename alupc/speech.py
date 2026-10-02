"""Antwort per Stimme: AluPC sagt kurz, was es gemacht hat („Okay – schwarz“). Offline über die Sprachausgabe des
Systems (Windows: eingebaute Stimmen; Linux: speech-dispatcher, z. B. mit espeak-ng oder RHVoice)."""

from __future__ import annotations


class Speaker:
    def __init__(self, config):
        self.config = config
        self._tts = None
        self.spoken: list[str] = []  # für Tests/Anzeige

    def settings(self) -> dict:
        return self.config["voice"]

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

    def say(self, text: str, force: bool = False) -> None:
        if not text or not (force or self.settings().get("speak", True)):
            return
        self.spoken.append(text)
        del self.spoken[:-20]
        try:
            tts = self._engine()
            tts.setVolume(max(0, min(100, int(self.config["sounds"].get("volume", 70)))) / 100)
            tts.say(text)
        except Exception:  # noqa: BLE001 – ohne Sprachausgabe geht es auch
            pass


def spoken_label(label: str) -> str:
    """„Schwarz an/aus“ → „Schwarz“ – kurz und natürlich zum Vorlesen."""
    for cut in (" an/aus", " Start/Pause", " Pause/Weiter", " zeigen"):
        label = label.replace(cut, "")
    return label.split(" · ")[0].replace("&", "und")
