"""Tastenbox: Arduino Pro Micro (ATmega32U4) mit 9 Tasten (3 × 3) und einem Lautstärke-Drehregler (Poti).

Die Box meldet sich am USB als serieller Anschluss (115200 Baud) und schickt kurze Textzeilen:

    HALLO ALUPC-TASTEN 1     Antwort auf „WER?“ (so erkennt AluPC die Box unter allen COM-Anschlüssen)
    TASTE 3                  Taste 3 gedrückt (1–9; ab Programm 2 beim Loslassen, wenn kurz gedrückt)
    LANG 3                   Taste 3 lange gedrückt (ab Programm 2, nach 0,6 s)
    LAUT 57                  Drehregler steht auf 57 % (0–100; nur bei Änderung, und auf „LAUT?“)
    STUMM                    optional: Druck auf den Drehregler (falls er einen Taster hat)

AluPC schickt: „WER?“ (Wer bist du?), „LAUT?“ (Wo steht der Regler?) und „LED 0–100“ (Helligkeit der LED bzw.
des LED-Streifens; 0 = aus).

Anschluss am Pro Micro: Tasten D2–D8, D14, D15 gegen GND · Poti 10 kΩ: Mitte an A0, außen VCC/GND ·
LED an D9 (über 220 Ω) oder LED-Streifen WS2812B an D10. Programm für den Arduino: resources/arduino/.

Was der Regler regelt, ist wählbar (Seite „Tastenbox“): PC-Ton, Ton auf Bildschirm 2, Mikrofon oder ein Programm.
Der Regler hat eine Skala – beim Wechsel startet das neue Ziel bei 0 und folgt erst, wenn der Regler auch auf 0 steht.

Lautstärke nur am Regler (Einstellung, Standard: an; nur wenn er den PC-Ton regelt): Solange die Box angeschlossen ist, bestimmt allein der
Regler die PC-Lautstärke. Ändert sie jemand anders (Windows-/KDE-Lautstärke, Medientasten, Handy, Sprache), stellt
AluPC sie innerhalb einer Sekunde zurück. Die Lautstärke einzelner Programme bleibt frei (Seite Audio).
"""

from __future__ import annotations

import threading
import time

from PySide6.QtCore import QObject, QTimer, Signal

BAUD = 115200
HELLO = "HALLO ALUPC-TASTEN"
KEYS = 9
# Arduino/SparkFun/Adafruit-Kennungen (Pro Micro und Nachbauten melden sich meist so)
VIDS = {0x2341, 0x2A03, 0x1B4F, 0x239A, 0x1D50}
DEFAULT_KEYS = {"1": "schwarz", "2": "standbild", "3": "studio_uebergang", "4": "vorherige_szene",
                "5": "naechste_szene", "6": "bild-in-bild", "7": "timer_start_pause", "8": "spiegeln",
                "9": "erweitern"}


def parse_line(line: str) -> tuple[str, int | str | None] | None:
    """Eine Zeile der Box → ("taste", 3) / ("laut", 57) / ("stumm", None) / ("hallo", "1") – sonst None."""
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
    return None


def candidate_ports(exclude: set[str] | None = None) -> list[str]:
    """Serielle Anschlüsse, an denen die Box sein könnte – Arduino-Kennungen zuerst, Fingerabdruck-Modul nie."""
    try:
        from serial.tools import list_ports
    except ImportError:
        return []
    exclude = exclude or set()
    found = []
    for info in list_ports.comports():
        if info.device in exclude:
            continue
        text = f"{info.description} {info.manufacturer or ''} {info.product or ''}".lower()
        # nur Arduino-artige Geräte fragen – fremde Geräte (Drucker, Modems …) bekommen nie „WER?“ geschickt
        if (info.vid in VIDS) or any(w in text for w in ("arduino", "pro micro", "leonardo", "sparkfun")):
            found.append(info.device)
    return found


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
    _line = Signal(str)
    _connected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.port = ""          # verbundener Anschluss ("" = nicht verbunden)
        self.wanted_port = ""   # aus den Einstellungen; "" = automatisch suchen
        self.knob: int | None = None  # letzte Reglerstellung
        self.last_key = 0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._serial = None
        self._line.connect(self._handle)
        self._connected.connect(self._set_port)

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
            return True
        except Exception:  # noqa: BLE001 - abgezogen: der Lesefaden merkt es und sucht neu
            return False

    def set_led(self, level: int) -> bool:
        return self.send(f"LED {max(0, min(100, int(level)))}")

    # ------------------------------------------------------------ Hintergrund
    def _open(self, device: str):
        import serial

        ser = serial.Serial(device, BAUD, timeout=0.3, write_timeout=0.5)
        ser.dtr = True  # Pro Micro (USB-CDC) schickt erst, wenn DTR gesetzt ist
        deadline = time.monotonic() + 2.5
        ser.reset_input_buffer()
        ser.write(b"WER?\n")
        while time.monotonic() < deadline and not self._stop.is_set():
            raw = ser.readline()
            parsed = parse_line(raw.decode("ascii", "ignore")) if raw else None
            if parsed and parsed[0] == "hallo":
                return ser
            if not raw:
                ser.write(b"WER?\n")
        ser.close()
        return None

    def _run(self) -> None:
        while not self._stop.is_set():
            ser = None
            ports = [self.wanted_port] if self.wanted_port else candidate_ports(_fingerprint_port())
            for device in ports:
                if self._stop.is_set():
                    return
                try:
                    ser = self._open(device)
                except Exception:  # noqa: BLE001 - belegt, keine Rechte, falsches Gerät …
                    ser = None
                if ser is not None:
                    self._serial = ser
                    self._connected.emit(device)
                    break
            if ser is None:
                self._stop.wait(3.0)  # in 3 s wieder suchen (Box später eingesteckt)
                continue
            try:
                ser.write(b"LAUT?\n")
                while not self._stop.is_set():
                    raw = ser.readline()
                    if raw:
                        self._line.emit(raw.decode("ascii", "ignore"))
            except Exception:  # noqa: BLE001 - Box abgezogen
                pass
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
        if not device:
            self.knob = None
        self.state_changed.emit()

    def _handle(self, line: str) -> None:
        self.feed(line)

    def feed(self, line: str) -> None:
        """Eine Zeile auswerten (auch für Tests ohne Box)."""
        parsed = parse_line(line)
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
