"""Tastenbox: Arduino Pro Micro (ATmega32U4) oder Nano mit 9 Tasten (3 × 3) und einem Lautstärke-Drehregler (Poti).

Die Box meldet sich am USB als serieller Anschluss (115200 Baud) und schickt kurze Textzeilen:

    HALLO ALUPC-TASTEN 3 NANO  Antwort auf „WER?“ (so erkennt AluPC die Box unter allen COM-Anschlüssen);
                             Programmversion und (ab 3) Board
    TASTE 3                  Taste 3 gedrückt (1–9; ab Programm 2 beim Loslassen, wenn kurz gedrückt)
    LANG 3                   Taste 3 lange gedrückt (ab Programm 2, nach 0,6 s)
    LAUT 57                  Drehregler steht auf 57 % (0–100; nur bei Änderung, und auf „LAUT?“)
    STUMM                    optional: Druck auf den Drehregler (falls er einen Taster hat)
    ROH 010000000 512        ab Programm 3, nur nach „DEBUG 1“: Tasten (1 = unten) und Regler roh (0–1023)

AluPC schickt: „WER?“ (Wer bist du?), „LAUT?“ (Wo steht der Regler?), „LED 0–100“ (Helligkeit der LEDs bzw.
des LED-Streifens; 0 = aus), ab Programm 3 auch „EFFEKT 0|1|2“ (ruhig/atmen/blinken), „FARBE r g b“ (Streifen)
und „DEBUG 0|1“ (Rohwerte für die Fehlersuche).

Anschluss Pro Micro: Tasten D2–D8, D14, D15 gegen GND · Poti 10 kΩ: Mitte an A0, außen VCC/GND ·
LEDs an D9 (je LED 1 kΩ) oder LED-Streifen WS2812B an D10.
Anschluss Nano: Tasten D2–D10 · Poti an A0 · LEDs an D11 · Streifen an D12. Programm: resources/arduino/.

Was der Regler regelt, ist wählbar (Seite „Tastenbox“): PC-Ton, Ton auf Bildschirm 2, Mikrofon oder ein Programm.
Der Regler hat eine Skala – beim Wechsel startet das neue Ziel bei 0 und folgt erst, wenn der Regler auch auf 0 steht.

Lautstärke nur am Regler (Einstellung, Standard: an; nur wenn er den PC-Ton regelt): Solange die Box angeschlossen ist, bestimmt allein der
Regler die PC-Lautstärke. Ändert sie jemand anders (Windows-/KDE-Lautstärke, Medientasten, Handy, Sprache), stellt
AluPC sie innerhalb einer Sekunde zurück. Die Lautstärke einzelner Programme bleibt frei (Seite Audio).
"""

from __future__ import annotations

import collections
import threading
import time

from PySide6.QtCore import QObject, QTimer, Signal

BAUD = 115200
HELLO = "HALLO ALUPC-TASTEN"
KEYS = 9
# Arduino/SparkFun/Adafruit-Kennungen (Pro Micro und Nachbauten melden sich meist so)
VIDS = {0x2341, 0x2A03, 0x1B4F, 0x239A, 0x1D50}
# USB-Seriell-Chips (Nano-Nachbauten: CH340, FTDI, CP210x) – stecken auch in anderen Geräten, deshalb fragt AluPC
# jeden solchen Anschluss nur einmal je Einstecken (antwortet er nicht, bleibt er in Ruhe)
SERIAL_CHIP_VIDS = {0x1A86, 0x0403, 0x10C4}
LED_EFFECTS = {"ruhig": 0, "atmen": 1, "blinken": 2, "regenbogen": 3}
# Farbschemata für RGB-LEDs (Programm 4): Reihenfolge der Kette 0–3 = Ecken (vorne links, hinten links,
# hinten rechts, vorne rechts), ab 4 die Lichtleiste
LED_SCHEMES = {"einfarbig": "Eine Farbe", "ecken": "Jede Ecke eigene Farbe", "zustand": "Zeigt den Zustand",
               "regenbogen": "Regenbogen (läuft)"}
CORNER_COLORS = ["#57c1ff", "#ff6161", "#59d499", "#ffc533"]
DEFAULT_KEYS = {"1": "schwarz", "2": "standbild", "3": "studio_uebergang", "4": "vorherige_szene",
                "5": "naechste_szene", "6": "bild-in-bild", "7": "timer_start_pause", "8": "spiegeln",
                "9": "erweitern"}


def parse_line(line: str) -> tuple[str, int | str | None] | None:
    """Eine Zeile der Box → ("taste", 3) / ("laut", 57) / ("stumm", None) / ("hallo", "3 NANO") /
    ("roh", ("010000000", 512)) – sonst None."""
    text = line.strip().upper()
    if not text:
        return None
    if text.startswith(HELLO):
        return "hallo", text[len(HELLO):].strip() or "1"
    parts = text.split()
    if parts[0] in ("TASTE", "LANG") and len(parts) == 2 and parts[1].isdigit() and 1 <= int(parts[1]) <= KEYS:
        return ("taste" if parts[0] == "TASTE" else "lang"), int(parts[1])
    if parts[0] == "LAUT" and len(parts) == 2 and parts[1].isdigit():
        return "laut", max(0, min(100, int(parts[1])))
    if parts[0] == "STUMM" and len(parts) == 1:
        return "stumm", None
    if (parts[0] == "ROH" and len(parts) == 3 and len(parts[1]) == KEYS and set(parts[1]) <= {"0", "1"}
            and parts[2].isdigit()):
        return "roh", (parts[1], min(1023, int(parts[2])))
    return None


def hello_info(value: str) -> tuple[int, str]:
    """„3 NANO“ → (3, "Nano"); alte Programme „2“ → (2, "")."""
    parts = (value or "1").split()
    version = int(parts[0]) if parts and parts[0].isdigit() else 1
    board = {"NANO": "Nano", "PROMICRO": "Pro Micro"}.get(parts[1], parts[1].title()) if len(parts) > 1 else ""
    return version, board


def candidate_ports(exclude: set[str] | None = None, chips: bool = True) -> list[str]:
    """Serielle Anschlüsse, an denen die Box sein könnte – Arduino-Kennungen zuerst, dann USB-Seriell-Chips
    (Nano-Nachbauten; mit chips=False nicht), Fingerabdruck-Modul nie."""
    try:
        from serial.tools import list_ports
    except ImportError:
        return []
    exclude = exclude or set()
    found, chip = [], []
    for info in list_ports.comports():
        if info.device in exclude:
            continue
        text = f"{info.description} {info.manufacturer or ''} {info.product or ''}".lower()
        # nur Arduino-artige Geräte fragen – fremde Geräte (Drucker, Modems …) bekommen nie „WER?“ geschickt
        if (info.vid in VIDS) or any(w in text for w in ("arduino", "pro micro", "leonardo", "sparkfun", "nano")):
            found.append(info.device)
        elif chips and (info.vid in SERIAL_CHIP_VIDS or any(w in text for w in ("ch340", "ch341", "ft232", "cp210"))):
            chip.append(info.device)
    return found + chip


def _fingerprint_port() -> set[str]:
    try:
        import json

        from .platform import zw_fingerprint as zw

        port = json.loads(zw._cache_file().read_text(encoding="utf-8")).get("port", "")
        return {port} if port else set()
    except Exception:  # noqa: BLE001
        return set()


class ButtonBox(QObject):
    """Liest die Box im Hintergrund; Signale kommen im GUI-Thread an."""

    key = Signal(int)          # Taste 1–9
    long_key = Signal(int)     # Taste 1–9 lange gedrückt (Arduino-Programm ab Version 2)
    volume = Signal(int)       # Reglerstellung 0–100
    mute = Signal()            # Druck auf den Regler (optional)
    state_changed = Signal()   # verbunden/getrennt
    raw = Signal(str, int)     # Fehlersuche: Tasten "010000000" und Regler roh 0–1023
    log_line = Signal(str)     # Fehlersuche: jede Zeile hin und zurück, Suche, Fehler
    _line = Signal(str)
    _connected = Signal(str)
    _log = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.port = ""          # verbundener Anschluss ("" = nicht verbunden)
        self.wanted_port = ""   # aus den Einstellungen; "" = automatisch suchen
        self.knob: int | None = None  # letzte Reglerstellung
        self.last_key = 0
        self.version = 0        # Programmversion der Box (aus „HALLO …“)
        self.board = ""
        self.raw_keys = ""      # nur mit Fehlersuche (DEBUG 1)
        self.raw_knob: int | None = None
        self.debug = False
        self.log: collections.deque[str] = collections.deque(maxlen=300)
        self._silent: set[str] = set()  # USB-Seriell-Anschlüsse ohne Antwort (bis sie abgezogen werden)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._serial = None
        self._line.connect(self._handle)
        self._connected.connect(self._set_port)
        self._log.connect(self._add_log)

    # ------------------------------------------------------------ Start/Stopp
    def start(self, port: str = "") -> None:
        self.stop()
        self.wanted_port = port
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="alupc-tastenbox", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        ser = self._serial
        if ser is not None:
            try:
                ser.close()
            except Exception:  # noqa: BLE001
                pass
        if self._thread is not None:
            self._thread.join(timeout=2)
        self._thread = None
        if self.port:
            self._set_port("")

    @property
    def connected(self) -> bool:
        return bool(self.port)

    def send(self, line: str) -> bool:
        """Zeile an die Box schicken (z. B. „LED 100“). False, wenn keine Box verbunden ist."""
        ser = self._serial
        if ser is None:
            return False
        try:
            ser.write((line.strip() + "\n").encode("ascii"))
            self._log.emit("→ " + line.strip())
            return True
        except Exception:  # noqa: BLE001 - abgezogen: der Lesefaden merkt es und sucht neu
            return False

    def set_led(self, level: int) -> bool:
        return self.send(f"LED {max(0, min(100, int(level)))}")

    def set_effect(self, name: str) -> bool:
        """LED-Effekt in der Box: ruhig, atmen, blinken (ab Programm 3), Regenbogen (ab 4; sonst ruhig)."""
        code = LED_EFFECTS.get(name, 0)
        if code == 3 and self.version < 4:
            code = 0
        return self.version >= 3 and self.send(f"EFFEKT {code}")

    def set_pixel(self, index: int, color: str) -> bool:
        """Eine RGB-LED der Kette einfärben (ab Programm 4)."""
        c = color.lstrip("#")
        if len(c) != 6 or self.version < 4:
            return False
        try:
            r, g, b = (int(c[i:i + 2], 16) for i in (0, 2, 4))
        except ValueError:
            return False
        return self.send(f"PIXEL {int(index)} {r} {g} {b}")

    def set_color(self, color: str) -> bool:
        """Farbe des LED-Streifens („#00ffa0“, ab Programm 3; einfarbige LEDs ignorieren sie)."""
        c = color.lstrip("#")
        if len(c) != 6 or self.version < 3:
            return False
        try:
            r, g, b = (int(c[i:i + 2], 16) for i in (0, 2, 4))
        except ValueError:
            return False
        return self.send(f"FARBE {r} {g} {b}")

    def set_debug(self, on: bool) -> None:
        """Fehlersuche: Box schickt alle 0,1 s die Rohwerte (Tasten, Regler)."""
        self.debug = bool(on)
        if not on:
            self.raw_keys, self.raw_knob = "", None
        if self.connected:
            self.send(f"DEBUG {1 if on else 0}")

    def _add_log(self, text: str) -> None:
        self.log.append(time.strftime("%H:%M:%S ") + text)
        self.log_line.emit(self.log[-1])

    # ------------------------------------------------------------ Hintergrund
    def _open(self, device: str):
        import serial

        self._log.emit(f"Suche: {device} …")
        ser = serial.Serial(device, BAUD, timeout=0.3, write_timeout=0.5)
        ser.dtr = True  # Pro Micro (USB-CDC) schickt erst, wenn DTR gesetzt ist; der Nano startet dabei neu
        deadline = time.monotonic() + 4.0  # Nano: ~1–2 s Neustart (Bootloader), dann meldet er sich selbst
        ser.reset_input_buffer()
        ser.write(b"WER?\n")
        while time.monotonic() < deadline and not self._stop.is_set():
            raw = ser.readline()
            parsed = parse_line(raw.decode("ascii", "ignore")) if raw else None
            if parsed and parsed[0] == "hallo":
                self._log.emit("← " + raw.decode("ascii", "ignore").strip())
                self._hello = str(parsed[1])
                return ser
            if not raw:
                ser.write(b"WER?\n")
        ser.close()
        self._log.emit(f"{device}: keine Antwort")
        return None

    def _run(self) -> None:
        while not self._stop.is_set():
            ser = None
            if self.wanted_port:
                ports = [self.wanted_port]
            else:
                ports = candidate_ports(_fingerprint_port())
                self._silent &= set(ports)  # abgezogen → beim nächsten Einstecken wieder fragen
                ports = [p for p in ports if p not in self._silent]
            for device in ports:
                if self._stop.is_set():
                    return
                try:
                    ser = self._open(device)
                except Exception as exc:  # noqa: BLE001 - belegt, keine Rechte, falsches Gerät …
                    self._log.emit(f"{device}: {exc}")
                    ser = None
                if ser is not None:
                    self._serial = ser
                    self._connected.emit(device)
                    break
                if not self.wanted_port and device not in candidate_ports(chips=False):
                    self._silent.add(device)
            if ser is None:
                self._stop.wait(3.0)  # in 3 s wieder suchen (Box später eingesteckt)
                continue
            try:
                ser.write(b"LAUT?\n")
                if self.debug:
                    ser.write(b"DEBUG 1\n")
                while not self._stop.is_set():
                    raw = ser.readline()
                    if raw:
                        self._line.emit(raw.decode("ascii", "ignore"))
            except Exception as exc:  # noqa: BLE001 - Box abgezogen
                self._log.emit(f"Getrennt: {exc}")
            finally:
                try:
                    ser.close()
                except Exception:  # noqa: BLE001
                    pass
                self._serial = None
                self._connected.emit("")

    # ------------------------------------------------------------ GUI-Thread
    def _set_port(self, device: str) -> None:
        self.port = device
        if device:
            self.version, self.board = hello_info(getattr(self, "_hello", ""))
        else:
            self.knob = None
            self.version, self.board, self.raw_keys, self.raw_knob = 0, "", "", None
        self.state_changed.emit()

    def _handle(self, line: str) -> None:
        self.feed(line)

    def feed(self, line: str) -> None:
        """Eine Zeile auswerten (auch für Tests ohne Box)."""
        parsed = parse_line(line)
        if parsed is None or parsed[0] != "roh":
            if line.strip():
                self._add_log("← " + line.strip())
        if parsed is None:
            return
        kind, value = parsed
        if kind in ("taste", "lang"):
            self.last_key = int(value)
            (self.key if kind == "taste" else self.long_key).emit(int(value))
        elif kind == "laut":
            self.knob = int(value)
            self.volume.emit(int(value))
        elif kind == "stumm":
            self.mute.emit()
        elif kind == "roh":
            self.raw_keys, self.raw_knob = value
            self.raw.emit(*value)
        elif kind == "hallo":  # Nano nach Neustart (z. B. Reset-Knopf): Version merken
            self.version, self.board = hello_info(str(value))
            self.state_changed.emit()


class VolumeKeeper(QObject):
    """Setzt die PC-Lautstärke auf die Reglerstellung – gebündelt (Drehen erzeugt viele Werte) und im Hintergrund –
    und stellt sie zurück, wenn sie jemand anders geändert hat."""

    overridden = Signal()  # jemand hat außerhalb des Reglers gedreht → zurückgestellt

    def __init__(self, parent=None):
        super().__init__(parent)
        self.target: int | None = None
        self.muted = False
        self._busy = False
        self._pending = False
        self._ignore_until = 0.0
        self._watch = QTimer(self, interval=1000)
        self._watch.timeout.connect(self._check)

    def set_target(self, value: int | None) -> None:
        self.target = value
        if value is None:
            self._watch.stop()
            return
        self._watch.start()
        self._apply()

    def toggle_mute(self) -> None:
        self.muted = not self.muted
        self._apply()

    def _apply(self) -> None:
        if self._busy:  # läuft gerade: danach mit dem neuesten Wert noch einmal
            self._pending = True
            return
        if self.target is None:
            return
        self._busy = True
        target, muted = self.target, self.muted
        self._ignore_until = time.monotonic() + 1.5

        def work():
            from . import pc_control

            pc_control.set_volume(0 if muted else target)
            if muted:
                pc_control.set_mute(True)

        from .ui.util import run_async

        run_async(work, lambda _r: self._done(), lambda _e: self._done())

    def _done(self) -> None:
        self._busy = False
        if self._pending:
            self._pending = False
            self._apply()

    def _check(self) -> None:
        if self.target is None or self._busy or time.monotonic() < self._ignore_until:
            return
        from . import pc_control
        from .ui.util import run_async

        want = 0 if self.muted else self.target

        def got(level):
            if level is not None and abs(int(level) - want) > 2 and self.target is not None:
                self.overridden.emit()
                self._apply()

        run_async(pc_control.get_volume, got, lambda _e: None)
