"""Sprachbefehle am PC – offline (Vosk), mit dem Startwort „Monitor“.

Beispiele: „Monitor schwarz“, „Monitor spiegeln“, „Monitor nächste Szene“, „Monitor Szene Pause“,
„Monitor Glücksrad drehen“, „Monitor Spiel starten“, „Monitor Bestenliste“.

Alles bleibt auf dem PC: Das Sprachmodell (Vosk, Deutsch, ca. 45 MB) wird einmal heruntergeladen und dann
lokal benutzt – kein Ton geht ins Internet. Erkannt wird frei (ohne feste Wortliste), danach sucht AluPC nach
„Monitor“ und vergleicht den Rest unscharf mit der Befehlsliste. So stören Wörter, die das kleine Modell
nicht kennt, nicht – und ohne „Monitor“ passiert nie etwas.
"""

from __future__ import annotations

import difflib
import json
import queue
import shutil
import threading
import unicodedata
import zipfile
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from .config import config_dir

MODEL_NAME = "vosk-model-small-de-0.15"
MODEL_URL = f"https://alphacephei.com/vosk/models/{MODEL_NAME}.zip"
MODEL_SIZE_MB = 45
RATE = 16000
WAKE_WORDS = ("monitor", "monitore", "monitors", "monitoren")
MIN_SCORE = 0.72
FILLERS = {"bitte", "mal", "jetzt", "danke", "kurz", "doch", "noch", "aeh", "aehm", "ja", "nun"}

# (gesprochene Varianten, Befehl, Anzeige) – Varianten ohne „Monitor“, Umlaute erlaubt
COMMANDS: list[tuple[tuple[str, ...], str, str]] = [
    (("schwarz", "sichtschutz", "aus", "dunkel"), "schwarz", "Schwarz an/aus"),
    (("standbild", "einfrieren", "stopp bild"), "standbild", "Standbild an/aus"),
    (("spiegeln", "spiegel", "gleich"), "spiegeln", "Spiegeln"),
    (("erweitern", "erweitert", "desktop"), "erweitern", "Erweitern"),
    (("kamera",), "kamera", "Kamera zeigen"),
    (("wetter", "uhr", "wetter und uhr"), "wetter", "Wetter & Uhr"),
    (("whiteboard", "tafel", "weiße tafel"), "whiteboard", "Whiteboard"),
    (("glücksrad", "rad", "zufall"), "gluecksrad", "Glücksrad zeigen"),
    (("drehen", "rad drehen", "glücksrad drehen"), "gluecksrad_drehen", "Glücksrad drehen"),
    (("nächste szene", "nächste", "weiter"), "naechste_szene", "Nächste Szene"),
    (("vorherige szene", "vorherige", "zurück"), "vorherige_szene", "Vorherige Szene"),
    (("timer", "timer start", "timer starten", "timer pause", "timer stopp"), "timer_start_pause",
     "Timer Start/Pause"),
    (("timer zeigen",), "timer_zeigen", "Timer zeigen"),
    (("timer neu", "timer zurücksetzen", "timer neustart"), "timer_neustart", "Timer neu starten"),
    (("musik", "musik zeigen", "was läuft"), "musik_zeigen", "Läuft gerade (Musik)"),
    (("musik pause", "pause", "musik stopp", "musik weiter spielen"), "musik_pause", "Musik Pause/Weiter"),
    (("nächstes lied", "nächster titel", "lied weiter"), "musik_weiter", "Nächstes Lied"),
    (("bildschirmschoner", "schoner"), "bildschirmschoner", "Bildschirmschoner"),
    (("overlays", "einblendungen"), "overlays", "Overlays an/aus"),
    (("zeichnungen löschen", "löschen", "alles löschen"), "zeichnungen_loeschen", "Zeichnungen löschen"),
    (("abstimmung", "umfrage"), "umfrage_zeigen", "Abstimmung zeigen"),
    (("abstimmung beenden", "umfrage beenden", "ergebnis"), "umfrage_ende", "Abstimmung beenden"),
    (("minispiele", "spiele", "spiel"), "spiele", "Minispiele (Lobby)"),
    (("spiel starten", "start", "los"), "spiel_start", "Minispiel starten"),
    (("bestenliste", "rangliste", "punkte"), "spiel_bestenliste", "Bestenliste zeigen"),
    (("airplay", "iphone", "ipad"), "airplay", "AirPlay"),
]


def fold(text: str) -> str:
    """klein, ohne Akzente, Umlaute als ae/oe/ue, nur Buchstaben/Ziffern/Leerzeichen."""
    s = str(text or "").lower()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        s = s.replace(a, b)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c if (c.isascii() and c.isalnum()) else " " for c in s)
    return " ".join(s.split())


def match(text: str, scenes: list[str] | None = None) -> tuple[str, str] | None:
    """Gehörten Satz → (Befehl, Anzeige) oder None. Nur mit „Monitor“ davor."""
    words = fold(text).split()
    idx = max((i for i, w in enumerate(words) if w in WAKE_WORDS), default=None)
    if idx is None:
        return None
    rest = words[idx + 1:]
    if rest and rest[0] in ("zwei", "2"):  # „Monitor zwei schwarz“ geht auch
        rest = rest[1:]
    rest = [w for w in rest if w not in FILLERS]
    if not rest:
        return None
    said = " ".join(rest)
    # Szene per Name: „Monitor Szene Pause“
    if rest[0] in ("szene", "szenen", "seene") and len(rest) > 1 and scenes:
        wanted = " ".join(rest[1:])
        folded = {fold(name): name for name in scenes}
        hit = difflib.get_close_matches(wanted, list(folded), n=1, cutoff=0.6)
        if hit:
            name = folded[hit[0]]
            return f"szene:{name}", f"Szene „{name}“"
        return None
    best, best_score = None, 0.0
    for variants, command, label in COMMANDS:
        for v in variants:
            v = fold(v)
            if len(v) <= 5:  # kurze Wörter nur genau (sonst wird aus „Haus“ schnell „aus“)
                score = 1.0 if said == v else 0.0
            else:
                score = difflib.SequenceMatcher(None, said, v).ratio()
            if score > best_score:
                best, best_score = (command, label), score
    return best if best_score >= MIN_SCORE else None


# --------------------------------------------------------------------------- Sprachmodell
def model_dir() -> Path:
    return config_dir() / "sprache" / MODEL_NAME


def model_ready(path: Path | None = None) -> bool:
    path = path or model_dir()
    return (path / "am" / "final.mdl").exists() and (path / "conf" / "model.conf").exists()


def vosk_available() -> bool:
    try:
        import vosk  # noqa: F401
    except Exception:  # noqa: BLE001 – auch kaputte Bibliothek (DLL) = nicht verfügbar
        return False
    return True


def download_model(progress=None, url: str = MODEL_URL, target: Path | None = None) -> Path:
    """Modell herunterladen und entpacken. progress(fertig_bytes, gesamt_bytes)."""
    import urllib.request

    target = target or model_dir()
    base = target.parent
    base.mkdir(parents=True, exist_ok=True)
    tmp = base / (target.name + ".zip.part")
    with urllib.request.urlopen(url, timeout=30) as resp, open(tmp, "wb") as f:  # noqa: S310 – feste https-URL
        total = int(resp.headers.get("Content-Length") or 0)
        done = 0
        while True:
            chunk = resp.read(256 * 1024)
            if not chunk:
                break
            f.write(chunk)
            done += len(chunk)
            if progress:
                progress(done, total)
    if total and done != total:
        tmp.unlink(missing_ok=True)
        raise RuntimeError("Download unvollständig")
    unpack = base / (target.name + ".neu")
    shutil.rmtree(unpack, ignore_errors=True)
    with zipfile.ZipFile(tmp) as z:
        root = unpack.resolve()
        for member in z.namelist():  # nichts außerhalb des Ordners entpacken
            if not (unpack / member).resolve().is_relative_to(root):
                raise RuntimeError("Ungültige Datei im Modell-Archiv")
        z.extractall(unpack)
    tmp.unlink(missing_ok=True)
    inner = next((p for p in [unpack / target.name, *unpack.iterdir()] if p.is_dir() and model_ready(p)), None)
    if inner is None:
        shutil.rmtree(unpack, ignore_errors=True)
        raise RuntimeError("Archiv enthält kein Sprachmodell")
    shutil.rmtree(target, ignore_errors=True)
    shutil.move(str(inner), str(target))
    shutil.rmtree(unpack, ignore_errors=True)
    return target


# --------------------------------------------------------------------------- Zuhören
class VoiceControl(QObject):
    """Mikrofon → Vosk (im Hintergrund) → Befehl. Signale kommen im GUI-Thread an."""

    command = Signal(str, str, str)  # Befehl, Anzeige, gehörter Text
    heard = Signal(str)  # alles Gehörte (für die Anzeige im Setup)
    state_changed = Signal(str)
    _loaded = Signal(object)

    def __init__(self, config, scenes=None, parent=None, recognizer_factory=None):
        super().__init__(parent)
        self.config = config
        self.scenes = scenes or (lambda: [])
        self.recognizer_factory = recognizer_factory  # für Tests: liefert ein Objekt mit AcceptWaveform/Result
        self.state = "aus"
        self._audio = None
        self._io = None
        self._queue: queue.Queue = queue.Queue(maxsize=200)
        self._worker: threading.Thread | None = None
        self._stop = threading.Event()
        self._loaded.connect(self._start_audio)

    def settings(self) -> dict:
        return self.config["voice"]

    def _set_state(self, state: str) -> None:
        self.state = state
        self.state_changed.emit(state)

    def apply(self) -> None:
        if self.settings().get("on"):
            self.start()
        else:
            self.stop()

    def running(self) -> bool:
        return self._worker is not None and self._worker.is_alive()

    def start(self) -> None:
        if self.running() or self.state == "lädt":
            return
        if self.recognizer_factory is None:
            if not vosk_available():
                self._set_state("Spracherkennung fehlt in dieser AluPC-Version")
                return
            if not model_ready():
                self._set_state("Sprachmodell fehlt – erst herunterladen")
                return
        self._set_state("lädt")

        def load():
            try:
                if self.recognizer_factory is not None:
                    rec = self.recognizer_factory()
                else:
                    import vosk

                    vosk.SetLogLevel(-1)
                    rec = vosk.KaldiRecognizer(vosk.Model(str(model_dir())), RATE)
                self._loaded.emit(rec)
            except Exception as exc:  # noqa: BLE001
                self._loaded.emit(exc)

        threading.Thread(target=load, name="sprache-laden", daemon=True).start()

    def _start_audio(self, rec) -> None:
        if isinstance(rec, Exception):
            self._set_state(f"Fehler: {rec}")
            return
        if not self.settings().get("on") and self.recognizer_factory is None:
            self._set_state("aus")  # in der Zwischenzeit ausgeschaltet
            return
        self._stop.clear()
        self._worker = threading.Thread(target=self._listen, args=(rec,), name="sprache", daemon=True)
        self._worker.start()
        if self.recognizer_factory is None:
            self._open_microphone()
        self._set_state("hört zu")

    def _open_microphone(self) -> None:
        from PySide6.QtMultimedia import QAudioFormat, QAudioSource, QMediaDevices

        fmt = QAudioFormat()
        fmt.setSampleRate(RATE)
        fmt.setChannelCount(1)
        fmt.setSampleFormat(QAudioFormat.Int16)
        device = QMediaDevices.defaultAudioInput()
        wanted = self.settings().get("device", "")
        for dev in QMediaDevices.audioInputs():
            if wanted and bytes(dev.id()).decode(errors="replace") == wanted:
                device = dev
        if device.isNull():
            self._set_state("Kein Mikrofon gefunden")
            return
        self._audio = QAudioSource(device, fmt, self)
        self._io = self._audio.start()
        if self._io is None:
            self._set_state("Mikrofon lässt sich nicht öffnen")
            return
        self._io.readyRead.connect(self._read_audio)

    def _read_audio(self) -> None:
        if self._io is None:
            return
        data = bytes(self._io.readAll())
        if data:
            self.feed(data)

    def feed(self, data: bytes) -> None:
        """Ton (16 kHz, mono, 16 Bit) an die Erkennung geben – vom Mikrofon oder in Tests."""
        try:
            self._queue.put_nowait(data)
        except queue.Full:  # Erkennung kommt nicht hinterher → altes wegwerfen
            try:
                self._queue.get_nowait()
            except queue.Empty:
                pass

    def _listen(self, rec) -> None:
        while not self._stop.is_set():
            try:
                data = self._queue.get(timeout=0.3)
            except queue.Empty:
                continue
            try:
                if rec.AcceptWaveform(data):
                    text = json.loads(rec.Result()).get("text", "")
                    if text:
                        self._handle(text)
            except Exception:  # noqa: BLE001 – ein kaputter Block darf das Zuhören nicht beenden
                continue

    def _handle(self, text: str) -> None:
        self.heard.emit(text)
        try:
            found = match(text, self.scenes())
        except Exception:  # noqa: BLE001
            found = None
        if found:
            self.command.emit(found[0], found[1], text)

    def stop(self) -> None:
        self._stop.set()
        if self._audio is not None:
            try:
                self._audio.stop()
            except RuntimeError:
                pass
            self._audio.deleteLater()
            self._audio = None
            self._io = None
        worker, self._worker = self._worker, None
        if worker is not None:
            worker.join(timeout=2)
        if self.state != "aus":
            self._set_state("aus")
