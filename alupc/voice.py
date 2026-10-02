"""Sprachbefehle am PC – offline (Vosk), mit Startwort „Monitor“ oder „Alu PC“.

Beispiele: „Monitor schwarz“, „Alu PC, Bildschirm schwarz“, „Monitor nächste Szene“, „Alu PC, Szene Pause“,
„Monitor Glücksrad drehen“, „Alu PC, Spiel starten“, „Monitor Bestenliste“.

Nur bestimmte Stimmen: Mit dem Sprecher-Modell von Vosk (ca. 13 MB) bekommt jede Äußerung einen
„Stimmabdruck“ (x-Vektor). Angelernte Stimmen sind der Mittelwert aus ein paar vorgelesenen Sätzen; ein Befehl
zählt nur, wenn der Abdruck nah genug an einer davon liegt (Kosinus-Abstand). Das ist ein Komfort-Filter gegen
Zurufe aus dem Raum – KEIN Schutz: eine Aufnahme der Stimme oder eine ähnliche Stimme kann ihn täuschen.

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
SPK_NAME = "vosk-model-spk-0.4"
SPK_URL = f"https://alphacephei.com/vosk/models/{SPK_NAME}.zip"
SPK_SIZE_MB = 13
RATE = 16000
WAKE_WORDS = ("monitor", "monitore", "monitors", "monitoren")
# Startwörter: Schlüssel → Anzeige
WAKES = {"monitor": "Monitor", "alupc": "Alu PC"}
# „Alu PC“ hört das Modell je nach Aussprache als „alu pc“, „alu p c“, „alu pe ze“ … – zusammengeschrieben vergleichen
ALUPC_FORMS = ("alupc", "alupeze", "alupezeh", "alupehzeh", "alupetse", "alupeetse", "alupece", "alupeceh")
TARGET_WORDS = {"bildschirm", "monitor", "monitore", "zwei", "2"}  # „Alu PC, Bildschirm schwarz“
STRICTNESS = {"streng": 0.40, "normal": 0.55, "locker": 0.70}  # höchster Kosinus-Abstand zur angelernten Stimme
MIN_SPK_FRAMES = 30  # kürzere Äußerungen haben einen zu ungenauen Stimmabdruck
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
    (("system", "systemstatus", "status", "computer status"), "system", "Systemstatus"),
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
    # Minispiele (dazu „Spiel Pong“, „Spiel Schätzen“ … zum Auswählen)
    (("spiel weiter", "nächste frage", "nächste runde", "nächstes bild"), "spiel_weiter", "Minispiel: weiter"),
    (("ergebnis zeigen", "spiel ende", "spiel beenden", "spielende"), "spiel_ende", "Minispiel: Ergebnis"),
    (("lobby", "zur lobby", "zurück zur lobby"), "spiel_lobby", "Minispiele: Lobby"),
    (("teams mischen", "neue teams"), "spiel_teams", "Teams mischen"),
    (("töne an", "töne aus", "spiel töne"), "spiel_toene", "Spiel-Töne an/aus"),
]

# „Spiel Pong“ → Spiel auswählen (gesprochene Namen der Spiele)
GAME_NAMES = {
    "schaetzen": ("schätzen", "schätz spiel"), "malen": ("malen", "malen und raten", "zeichnen"),
    "stroop": ("farb chaos", "farbchaos", "farben"), "simon": ("simon", "simon sagt"),
    "tauziehen": ("tauziehen", "tau ziehen"), "pong": ("pong", "ping pong"), "ballon": ("ballon", "luftballon"),
    "schlangen": ("schlangen", "schlange", "snake"), "reaktion": ("schnellster finger", "reaktion"),
    "rennen": ("tipp rennen", "rennen", "wettrennen"),
}


def fold(text: str) -> str:
    """klein, ohne Akzente, Umlaute als ae/oe/ue, nur Buchstaben/Ziffern/Leerzeichen."""
    s = str(text or "").lower()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        s = s.replace(a, b)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c if (c.isascii() and c.isalnum()) else " " for c in s)
    return " ".join(s.split())


def _is_alupc(joined: str) -> bool:
    if not joined.startswith(("alu", "hal", "allu", "aloo")):
        return False
    return max(difflib.SequenceMatcher(None, joined, form).ratio() for form in ALUPC_FORMS) >= 0.82


def wake_end(words: list[str], wakes=("monitor", "alupc")) -> int | None:
    """Position direkt nach dem LETZTEN Startwort im Satz (oder None, wenn keins vorkommt)."""
    end = None
    for i, w in enumerate(words):
        if "monitor" in wakes and w in WAKE_WORDS:
            end = i + 1
        if "alupc" in wakes:
            for k in (3, 2, 1):  # „alu pe ze“, „alu pc“, „alupc“
                if i + k <= len(words) and _is_alupc("".join(words[i:i + k])):
                    end = max(end or 0, i + k)
                    break
    return end


def _similar(said: str, phrase: str) -> float:
    phrase = fold(phrase)
    if len(phrase) <= 5:  # kurze Wörter nur genau (sonst wird aus „Haus“ schnell „aus“)
        return 1.0 if said == phrase else 0.0
    return difflib.SequenceMatcher(None, said, phrase).ratio()


def match(text: str, scenes: list[str] | None = None, wakes=("monitor", "alupc"),
          custom: list[dict] | None = None) -> tuple[str, str] | None:
    """Gehörten Satz → (Befehl, Anzeige) oder None. Nur mit einem Startwort davor."""
    words = fold(text).split()
    idx = wake_end(words, wakes)
    if idx is None:
        return None
    rest = words[idx:]
    while rest and rest[0] in TARGET_WORDS:  # „Monitor zwei schwarz“, „Alu PC, Bildschirm schwarz“
        rest = rest[1:]
    rest = [w for w in rest if w not in FILLERS]
    if not rest:
        return None
    said = " ".join(rest)
    # eigene Sätze zuerst (die dürfen auch eingebaute überschreiben)
    best_custom = max(((_similar(said, c.get("say", "")), c) for c in custom or [] if c.get("say") and c.get("do")),
                      key=lambda t: t[0], default=(0.0, None))
    if best_custom[0] >= 0.8:
        return best_custom[1]["do"], f"„{best_custom[1]['say']}“"
    # Minispiel per Name: „Alu PC, Spiel Pong“
    if rest[0] in ("spiel", "spielen") and len(rest) > 1 and rest[1] not in ("starten", "start", "weiter", "ende",
                                                                          "beenden", "toene"):
        wanted = " ".join(rest[1:])
        scores = [(max(difflib.SequenceMatcher(None, wanted, fold(n)).ratio() for n in names), key)
                  for key, names in GAME_NAMES.items()]
        score, key = max(scores)
        if score >= 0.7:
            from .games import GAMES

            return f"spiel:{key}", f"Minispiel: {GAMES[key].title}"
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
            score = _similar(said, v)
            if score > best_score:
                best, best_score = (command, label), score
    return best if best_score >= MIN_SCORE else None


# --------------------------------------------------------------------------- Sprachmodell
def model_dir() -> Path:
    return config_dir() / "sprache" / MODEL_NAME


def model_ready(path: Path | None = None) -> bool:
    path = path or model_dir()
    return (path / "am" / "final.mdl").exists() and (path / "conf" / "model.conf").exists()


def spk_dir() -> Path:
    return config_dir() / "sprache" / SPK_NAME


def spk_ready(path: Path | None = None) -> bool:
    path = path or spk_dir()
    return all((path / f).exists() for f in ("mfcc.conf", "final.ext.raw", "mean.vec", "transform.mat"))


def cosine_dist(a, b) -> float:
    """0 = gleiche Richtung (gleiche Stimme), 1 = nichts gemeinsam, bis 2 = entgegengesetzt."""
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    if not na or not nb:
        return 2.0
    return 1 - dot / (na * nb)


def average_voice(vectors: list[list[float]]) -> list[float]:
    """Stimmabdrücke mehrerer Sätze zu einem zusammenfassen (jeder vorher auf Länge 1 gebracht)."""
    norm = []
    for v in vectors:
        n = sum(x * x for x in v) ** 0.5 or 1.0
        norm.append([x / n for x in v])
    return [round(sum(col) / len(norm), 6) for col in zip(*norm)]


def who_speaks(vector, voices: list[dict]) -> tuple[str, float]:
    """(Name der ähnlichsten angelernten Stimme, Abstand)."""
    best = ("", 2.0)
    for v in voices:
        d = cosine_dist(vector, v.get("vec") or [])
        if d < best[1]:
            best = (str(v.get("name", "")), d)
    return best


def vosk_available() -> bool:
    try:
        import vosk  # noqa: F401
    except Exception:  # noqa: BLE001 – auch kaputte Bibliothek (DLL) = nicht verfügbar
        return False
    return True


def download_model(progress=None, url: str = MODEL_URL, target: Path | None = None, ready=model_ready) -> Path:
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
    inner = next((p for p in [unpack / target.name, *unpack.iterdir()] if p.is_dir() and ready(p)), None)
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
    heard = Signal(str)  # alles Gehörte (für die Anzeige im Setup), mit erkannter Stimme
    rejected = Signal(str, str)  # Befehl kam von einer fremden Stimme: (gehörter Text, Grund)
    sample = Signal(object, int, str)  # beim Anlernen: Stimmabdruck, Länge (Frames), gehörter Text
    state_changed = Signal(str)
    _loaded = Signal(object)

    def __init__(self, config, scenes=None, parent=None, recognizer_factory=None):
        super().__init__(parent)
        self.config = config
        self.scenes = scenes or (lambda: [])
        self.recognizer_factory = recognizer_factory  # für Tests: liefert ein Objekt mit AcceptWaveform/Result
        self.state = "aus"
        self.enrolling = False  # Stimme anlernen: Sätze liefern nur Stimmabdrücke, keine Befehle
        self.has_spk = False  # Sprecher-Modell geladen?
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
                    self.has_spk = bool(getattr(rec, "speaker", False))
                else:
                    import vosk

                    vosk.SetLogLevel(-1)
                    rec = vosk.KaldiRecognizer(vosk.Model(str(model_dir())), RATE)
                    self.has_spk = False
                    if spk_ready():  # Stimmen unterscheiden (nur wenn heruntergeladen)
                        rec.SetSpkModel(vosk.SpkModel(str(spk_dir())))
                        self.has_spk = True
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
                    res = json.loads(rec.Result())
                    text = res.get("text", "")
                    if text:
                        self._handle(text, res.get("spk"), int(res.get("spk_frames", 0) or 0))
            except Exception:  # noqa: BLE001 – ein kaputter Block darf das Zuhören nicht beenden
                continue

    def _handle(self, text: str, spk=None, frames: int = 0) -> None:
        if self.enrolling:
            if spk:
                self.sample.emit(list(spk), frames, text)
            return
        cfg = self.settings()
        voices = [v for v in cfg.get("voices") or [] if v.get("vec")]
        who = ""
        if spk and voices and frames >= MIN_SPK_FRAMES:
            name, dist = who_speaks(spk, voices)
            limit = STRICTNESS.get(cfg.get("strict", "normal"), STRICTNESS["normal"])
            who = f"{name} ({dist:.2f})".replace(".", ",") if dist <= limit else f"fremde Stimme ({dist:.2f})".replace(".", ",")
        self.heard.emit(f"„{text}“" + (f" – {who}" if who else ""))
        try:
            found = match(text, self.scenes(), tuple(cfg.get("wake") or ("monitor", "alupc")), cfg.get("custom") or [])
        except Exception:  # noqa: BLE001
            found = None
        if not found:
            return
        if cfg.get("only_voices") and voices:
            if not spk or frames < MIN_SPK_FRAMES:
                self.rejected.emit(text, "Stimme nicht erkannt (zu kurz oder Stimmerkennung fehlt)")
                return
            name, dist = who_speaks(spk, voices)
            limit = STRICTNESS.get(cfg.get("strict", "normal"), STRICTNESS["normal"])
            if dist > limit:
                self.rejected.emit(text, f"fremde Stimme (Abstand {dist:.2f})".replace(".", ","))
                return
            self.command.emit(found[0], f"{found[1]} · {name}", text)
            return
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
