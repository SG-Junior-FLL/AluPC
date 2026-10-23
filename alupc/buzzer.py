"""Buzzer der Tastenbox: eingebaute Lieder und Signaltöne, MIDI-Dateien – alles als Folge (Hz, ms).

Die Box (Programm ab Version 7, Buzzer an A2) kann nur „TON f ms“: einen Ton spielen. Melodien spielt AluPC
Note für Note ab (BuzzerPlayer). Ein Buzzer kann nur EINEN Ton gleichzeitig – aus MIDI-Dateien wird deshalb immer
der höchste gerade klingende Ton genommen (meist die Melodie); das Schlagzeug (Kanal 10) bleibt weg.
"""

from __future__ import annotations

import shutil
import struct
from pathlib import Path

from .config import config_dir

MIN_VERSION = 7  # ab diesem Box-Programm gibt es „TON“

# Name → (Anzeige, Tempo in Vierteln pro Minute, Noten „E5/4 B4/8 R/4 A4/8.“ – R = Pause, „.“ = punktiert)
SONGS = {
    "piep": ("Signal: Piep", 120, "A5/16"),
    "doppelpiep": ("Signal: Doppel-Piep", 120, "A5/16 R/32 A5/16"),
    "erfolg": ("Signal: Erfolg", 140, "C5/16 E5/16 G5/16 C6/8"),
    "fehler": ("Signal: Fehler", 120, "G4/8 C4/4"),
    "start": ("Signal: Start", 160, "C5/16 E5/16 G5/16 C6/16"),
    "alarm": ("Signal: Alarm", 150, "A5/8 E5/8 A5/8 E5/8 A5/8 E5/8"),
    "tetris": ("Lied: Tetris", 144,
               "E5/4 B4/8 C5/8 D5/4 C5/8 B4/8 A4/4 A4/8 C5/8 E5/4 D5/8 C5/8 B4/4. C5/8 D5/4 E5/4 C5/4 A4/4 A4/4 "
               "R/4 R/8 D5/4 F5/8 A5/4 G5/8 F5/8 E5/4. C5/8 E5/4 D5/8 C5/8 B4/4 B4/8 C5/8 D5/4 E5/4 C5/4 A4/4 A4/4"),
    "freude": ("Lied: Ode an die Freude", 120,
               "E5/4 E5/4 F5/4 G5/4 G5/4 F5/4 E5/4 D5/4 C5/4 C5/4 D5/4 E5/4 E5/4. D5/8 D5/2 E5/4 E5/4 F5/4 G5/4 "
               "G5/4 F5/4 E5/4 D5/4 C5/4 C5/4 D5/4 E5/4 D5/4. C5/8 C5/2"),
    "elise": ("Lied: Für Elise", 80,
              "E5/16 DS5/16 E5/16 DS5/16 E5/16 B4/16 D5/16 C5/16 A4/8. C4/16 E4/16 A4/16 B4/8. E4/16 GS4/16 B4/16 "
              "C5/8. E4/16 E5/16 DS5/16 E5/16 DS5/16 E5/16 B4/16 D5/16 C5/16 A4/8. C4/16 E4/16 A4/16 B4/8. E4/16 "
              "C5/16 B4/16 A4/2"),
    "geburtstag": ("Lied: Happy Birthday", 110,
                   "G4/8. G4/16 A4/4 G4/4 C5/4 B4/2 G4/8. G4/16 A4/4 G4/4 D5/4 C5/2 G4/8. G4/16 G5/4 E5/4 C5/4 B4/4 "
                   "A4/4 F5/8. F5/16 E5/4 C5/4 D5/4 C5/2"),
    "jingle": ("Lied: Jingle Bells", 170,
               "E5/4 E5/4 E5/2 E5/4 E5/4 E5/2 E5/4 G5/4 C5/4. D5/8 E5/1 F5/4 F5/4 F5/4. F5/8 F5/4 E5/4 E5/4 E5/8 "
               "E5/8 E5/4 D5/4 D5/4 E5/4 D5/2 G5/2"),
    "entchen": ("Lied: Alle meine Entchen", 130,
                "C5/8 D5/8 E5/8 F5/8 G5/4 G5/4 A5/8 A5/8 A5/8 A5/8 G5/2 A5/8 A5/8 A5/8 A5/8 G5/2 F5/8 F5/8 F5/8 "
                "F5/8 E5/4 E5/4 D5/8 D5/8 D5/8 D5/8 C5/2"),
    "jakob": ("Lied: Bruder Jakob", 130,
              "C5/4 D5/4 E5/4 C5/4 C5/4 D5/4 E5/4 C5/4 E5/4 F5/4 G5/2 E5/4 F5/4 G5/2 G5/8 A5/8 G5/8 F5/8 E5/4 "
              "C5/4 G5/8 A5/8 G5/8 F5/8 E5/4 C5/4 C5/4 G4/4 C5/2 C5/4 G4/4 C5/2"),
    "bergkoenig": ("Lied: In der Halle des Bergkönigs", 140,
                   "A4/8 B4/8 C5/8 D5/8 E5/8 C5/8 E5/4 DS5/8 B4/8 DS5/4 D5/8 AS4/8 D5/4 A4/8 B4/8 C5/8 D5/8 E5/8 "
                   "C5/8 E5/8 A5/8 G5/8 E5/8 C5/8 E5/8 G5/2"),
    "stern": ("Lied: Twinkle Twinkle Little Star", 120,
              "C5/4 C5/4 G5/4 G5/4 A5/4 A5/4 G5/2 F5/4 F5/4 E5/4 E5/4 D5/4 D5/4 C5/2 G5/4 G5/4 F5/4 F5/4 E5/4 "
              "E5/4 D5/2 G5/4 G5/4 F5/4 F5/4 E5/4 E5/4 D5/2 C5/4 C5/4 G5/4 G5/4 A5/4 A5/4 G5/2 F5/4 F5/4 E5/4 "
              "E5/4 D5/4 D5/4 C5/2"),
}
CLICK = (2400, 12)  # kurzer Klick als Rückmeldung bei Tastendruck

_STEPS = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def note_freq(name: str) -> int:
    """„A4“ → 440, „DS5“ (Dis) → 622; „R“ → 0 (Pause)."""
    name = name.upper()
    if name == "R":
        return 0
    sharp = name[1:2] == "S"
    midi = 12 * (int(name[2:] if sharp else name[1:]) + 1) + _STEPS[name[0]] + sharp
    return midi_freq(midi)


def midi_freq(note: int) -> int:
    return round(440 * 2 ** ((note - 69) / 12))


def parse_melody(text: str, tempo: int) -> list[tuple[int, int]]:
    whole = 240000 / max(20, tempo)  # ms einer ganzen Note
    out = []
    for tok in text.split():
        name, length = tok.split("/")
        ms = whole / int(length.rstrip("."))
        if length.endswith("."):
            ms *= 1.5
        out.append((note_freq(name), round(ms)))
    return out


def song_notes(name: str) -> list[tuple[int, int]]:
    _label, tempo, text = SONGS[name]
    return parse_melody(text, tempo)


# --------------------------------------------------------------------------- MIDI
def _vlq(data: bytes, i: int) -> tuple[int, int]:
    value = 0
    while True:
        b = data[i]
        i += 1
        value = (value << 7) | (b & 0x7F)
        if not b & 0x80:
            return value, i


def midi_notes(path: str | Path, max_ms: int = 10 * 60 * 1000) -> list[tuple[int, int]]:
    """MIDI-Datei (Typ 0/1) → [(Hz, ms)] für einen Buzzer: je Moment der höchste klingende Ton, Pausen = 0 Hz.
    Fehlerhafte Dateien → ValueError."""
    data = Path(path).read_bytes()
    if data[:4] != b"MThd" or len(data) < 14:
        raise ValueError("keine MIDI-Datei")
    hlen = struct.unpack(">I", data[4:8])[0]
    _fmt, ntracks, division = struct.unpack(">HHH", data[8:14])
    pos = 8 + hlen
    events: list[tuple[int, int, int]] = []  # (Tick, +1/-1, Note)
    tempos: list[tuple[int, int]] = [(0, 500000)]  # (Tick, µs je Viertel)
    try:
        for _ in range(ntracks):
            while data[pos:pos + 4] != b"MTrk":  # unbekannte Blöcke überspringen
                if pos + 8 > len(data):
                    raise ValueError("Spur fehlt")
                pos += 8 + struct.unpack(">I", data[pos + 4:pos + 8])[0]
            length = struct.unpack(">I", data[pos + 4:pos + 8])[0]
            i, end, tick, status = pos + 8, pos + 8 + length, 0, 0
            pos = end
            while i < end:
                delta, i = _vlq(data, i)
                tick += delta
                b = data[i]
                if b == 0xFF:  # Meta
                    kind = data[i + 1]
                    n, i = _vlq(data, i + 2)
                    if kind == 0x51 and n == 3:
                        tempos.append((tick, int.from_bytes(data[i:i + 3], "big")))
                    i += n
                    if kind == 0x2F:
                        break
                    continue
                if b in (0xF0, 0xF7):  # SysEx
                    n, i = _vlq(data, i + 1)
                    i += n
                    continue
                if b & 0x80:
                    status = b
                    i += 1
                elif not status:
                    raise ValueError("kaputte Spur")
                kind, chan = status & 0xF0, status & 0x0F
                if kind in (0xC0, 0xD0):
                    i += 1
                    continue
                note, vel = data[i], data[i + 1]
                i += 2
                if chan == 9 or kind not in (0x80, 0x90):  # Schlagzeug / anderes
                    continue
                events.append((tick, 1 if kind == 0x90 and vel > 0 else -1, note))
    except (IndexError, struct.error) as exc:
        raise ValueError("kaputte MIDI-Datei") from exc
    if not events:
        raise ValueError("keine Noten in der Datei")

    tempos.sort()

    def to_ms(t: int) -> float:
        if division & 0x8000:  # SMPTE: Bilder/s × Ticks je Bild
            fps = 256 - (division >> 8)
            return t * 1000 / (fps * (division & 0xFF))
        ms, last_tick, last_tempo = 0.0, 0, 500000
        for at, tempo in tempos:
            if at >= t:
                break
            ms += (at - last_tick) * last_tempo / division / 1000
            last_tick, last_tempo = at, tempo
        return ms + (t - last_tick) * last_tempo / division / 1000

    events.sort(key=lambda e: (e[0], e[1]))  # gleicher Zeitpunkt: erst aus, dann an
    sounding: dict[int, int] = {}
    out: list[list[int]] = []
    prev_ms, cur = 0.0, 0
    for tick, change, note in events:
        now = to_ms(tick)
        if now > prev_ms:
            seg = round(now - prev_ms)
            if out and out[-1][0] == cur:
                out[-1][1] += seg
            elif seg > 0 and (out or cur):  # Stille am Anfang weglassen
                out.append([cur, seg])
            prev_ms = now
        if change > 0:
            sounding[note] = sounding.get(note, 0) + 1
        elif sounding.get(note):
            sounding[note] -= 1
            if not sounding[note]:
                del sounding[note]
        cur = midi_freq(max(sounding)) if sounding else 0
        if now > max_ms:
            break
    merged: list[tuple[int, int]] = []
    for f, ms in out:  # Schnipsel unter 15 ms (Akkord-Anschläge) an den vorigen Ton hängen
        if merged and ms < 15:
            merged[-1] = (merged[-1][0], merged[-1][1] + ms)
        else:
            merged.append((f, ms))
    while merged and merged[-1][0] == 0:
        merged.pop()
    return merged


def midi_dir() -> Path:
    d = config_dir() / "midi"
    d.mkdir(parents=True, exist_ok=True)
    return d


def upload_midi(source: str) -> str:
    """MIDI-Datei in den AluPC-Ordner kopieren (bleibt, auch wenn das Original weg ist)."""
    src = Path(source)
    target = midi_dir() / src.name
    i = 2
    while target.exists() and target.resolve() != src.resolve():
        target = midi_dir() / f"{src.stem}-{i}{src.suffix}"
        i += 1
    if target.resolve() != src.resolve():
        shutil.copy2(src, target)
    return str(target)


def midi_files() -> list[Path]:
    return sorted(p for p in midi_dir().iterdir() if p.suffix.lower() in (".mid", ".midi"))


class BuzzerPlayer:
    """Spielt [(Hz, ms)] Note für Note: schickt „TON f ms“ an die Box und wartet die Länge ab (Qt-Timer, kein
    Blockieren). Eine neue Melodie ersetzt die laufende."""

    def __init__(self, send, parent=None):
        from PySide6.QtCore import QElapsedTimer, Qt, QTimer

        self._send = send  # send("TON 440 200") → bool
        self._timer = QTimer(parent, singleShot=True)
        self._timer.setTimerType(Qt.PreciseTimer)
        self._timer.timeout.connect(self._step)
        self._clock = QElapsedTimer()
        self._notes: list[tuple[int, int]] = []
        self._i = 0
        self._due = 0
        self.name = ""

    @property
    def playing(self) -> bool:
        return self._timer.isActive()

    def play(self, notes: list[tuple[int, int]], name: str = "") -> None:
        self.stop(quiet=True)
        self._notes, self._i, self._due, self.name = list(notes), 0, 0, name
        self._clock.start()
        self._step()

    def stop(self, quiet: bool = False) -> None:
        was = self._timer.isActive()
        self._timer.stop()
        self._notes, self.name = [], ""
        if was and not quiet:
            self._send("TON 0 0")

    def _step(self) -> None:
        if self._i >= len(self._notes):
            self._notes, self.name = [], ""
            return
        freq, ms = self._notes[self._i]
        self._i += 1
        if freq:  # 10 % Lücke, damit gleiche Töne hintereinander getrennt klingen
            self._send(f"TON {freq} {max(10, ms - min(25, ms // 10))}")
        self._due += ms
        self._timer.start(max(0, self._due - self._clock.elapsed()))  # Zeit nachholen statt aufzusummieren
