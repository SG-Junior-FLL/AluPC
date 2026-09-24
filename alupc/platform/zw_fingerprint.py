"""Fingerabdruckmodule mit eigenem Chip am seriellen Anschluss (z. B. Hi-Link HLK-ZW101/ZW0922,
AS608, R307) – über einen USB-Seriell-Adapter (CH340, CP2102, …) an Windows und Linux.

Solche Module speichern und vergleichen Fingerabdrücke selbst. Sie sprechen das verbreitete
„EF01“-Protokoll (Paketkopf EF 01, Adresse FF FF FF FF). Windows Hello und libfprint kennen sie
nicht – AluPC steuert sie direkt.

Dieses Modul importiert absichtlich kein Qt: Die Anmelde-Prüfung (PAM, siehe `pam_check`) startet
es ohne Oberfläche und soll schnell sein.
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path

from .base import Cancelled, FINGER_NAMES, FingerprintBackend, Sensor

try:
    import serial  # pyserial
    from serial.tools import list_ports

    HAVE_SERIAL = True
except ImportError:  # pragma: no cover - nur ohne pyserial
    HAVE_SERIAL = False

HEADER = b"\xef\x01"
ADDRESS = b"\xff\xff\xff\xff"
PID_COMMAND, PID_DATA, PID_ACK, PID_END = 0x01, 0x02, 0x07, 0x08

CMD_GET_IMAGE = 0x01
CMD_GEN_CHAR = 0x02
CMD_SEARCH = 0x04
CMD_REG_MODEL = 0x05
CMD_STORE = 0x06
CMD_DELETE = 0x0C
CMD_EMPTY = 0x0D
CMD_READ_SYS_PARA = 0x0F
CMD_VERIFY_PASSWORD = 0x13
CMD_TEMPLATE_COUNT = 0x1D
CMD_READ_INDEX_TABLE = 0x1F

OK, NO_FINGER, NOT_FOUND = 0x00, 0x02, 0x09
ERRORS = {
    0x01: "Übertragungsfehler",
    0x02: "Kein Finger auf dem Sensor",
    0x03: "Aufnahme fehlgeschlagen",
    0x06: "Bild zu unscharf – Finger fester und ruhig auflegen",
    0x07: "Zu wenig Merkmale – Finger fester auflegen",
    0x08: "Fingerabdruck passt nicht",
    0x09: "Fingerabdruck nicht gefunden",
    0x0A: "Die Aufnahmen passen nicht zusammen – immer denselben Finger nehmen",
    0x0B: "Speicherplatz außerhalb des Bereichs",
    0x10: "Löschen fehlgeschlagen",
    0x11: "Speicher leeren fehlgeschlagen",
    0x13: "Falsches Modul-Passwort",
    0x15: "Kein gültiges Bild im Speicher",
    0x18: "Fehler beim Schreiben in den Speicher des Moduls",
}

# Übliche USB-Seriell-Chips (werden zuerst probiert): CH340/CH341, CP210x, FTDI, PL2303, CH9102
USB_SERIAL_IDS = {(0x1A86, 0x7523), (0x1A86, 0x5523), (0x1A86, 0x55D4), (0x10C4, 0xEA60), (0x0403, 0x6001),
                  (0x0403, 0x6015), (0x067B, 0x2303)}
BAUDS = (57600, 115200, 9600)  # ZW101 ab Werk: 57600
SCANS_PER_ENROLL = 2
LOGIN_FILE = Path("/etc/alupc/fingerprint-login.json")


class SensorError(RuntimeError):
    pass


def checksum(data: bytes) -> int:
    return sum(data) & 0xFFFF


def build_packet(pid: int, payload: bytes) -> bytes:
    length = len(payload) + 2
    body = bytes([pid]) + length.to_bytes(2, "big") + payload
    return HEADER + ADDRESS + body + checksum(body).to_bytes(2, "big")


def parse_packet(data: bytes) -> tuple[int, bytes]:
    """(PID, Nutzdaten) aus einem kompletten Paket; wirft SensorError bei Unsinn."""
    if len(data) < 12 or data[:2] != HEADER:
        raise SensorError("Ungültige Antwort vom Modul")
    pid = data[6]
    length = int.from_bytes(data[7:9], "big")
    payload = data[9:9 + length - 2]
    got = int.from_bytes(data[9 + length - 2:9 + length], "big")
    if checksum(data[6:9 + length - 2]) != got:
        raise SensorError("Prüfsumme falsch (Kabel/Baudrate?)")
    return pid, payload


class ZWSensor:
    """Verbindung zu einem Modul (EF01-Protokoll)."""

    def __init__(self, port: str, baud: int = 57600, timeout: float = 1.0):
        self.port, self.baud, self.timeout = port, baud, timeout
        self.ser = None

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *_):
        self.close()

    def open(self):
        if not HAVE_SERIAL:
            raise SensorError("Python-Paket „pyserial“ fehlt")
        try:
            self.ser = serial.Serial(self.port, self.baud, timeout=self.timeout, write_timeout=self.timeout)
        except serial.SerialException as exc:
            text = str(exc)
            if "ermission" in text or "Zugriff" in text or "Access" in text:
                raise SensorError(f"Kein Zugriff auf {self.port} – siehe „Automatisch einrichten“") from exc
            raise SensorError(f"{self.port} lässt sich nicht öffnen: {text}") from exc
        self.ser.reset_input_buffer()

    def close(self):
        if self.ser is not None:
            try:
                self.ser.close()
            finally:
                self.ser = None

    def _read_exact(self, n: int) -> bytes:
        data = b""
        deadline = time.monotonic() + self.timeout
        while len(data) < n and time.monotonic() < deadline:
            chunk = self.ser.read(n - len(data))
            if chunk:
                data += chunk
        if len(data) < n:
            raise SensorError("Keine Antwort vom Modul (falscher Anschluss oder Baudrate?)")
        return data

    def _read_packet(self) -> tuple[int, bytes]:
        # bis zum Paketkopf vorlesen (Reste im Puffer überspringen) – mit Gesamtfrist, damit ein Gerät,
        # das ununterbrochen etwas anderes sendet (Arduino, GPS …), nichts ewig blockiert
        deadline = time.monotonic() + self.timeout * 2
        skipped = 0
        first = self._read_exact(1)
        while True:
            second = self._read_exact(1)
            if first + second == HEADER:
                break
            first = second
            skipped += 1
            if skipped > 256 or time.monotonic() > deadline:
                raise SensorError("Kein Fingerabdruckmodul (unerwartete Daten)")
        rest = self._read_exact(7)  # Adresse (4), PID (1), Länge (2)
        length = int.from_bytes(rest[5:7], "big")
        body = self._read_exact(length)
        return parse_packet(HEADER + rest + body)

    def command(self, code: int, params: bytes = b"") -> tuple[int, bytes]:
        """Befehl senden → (Bestätigungscode, Daten)."""
        self.ser.write(build_packet(PID_COMMAND, bytes([code]) + params))
        pid, payload = self._read_packet()
        if pid != PID_ACK or not payload:
            raise SensorError("Unerwartete Antwort vom Modul")
        return payload[0], payload[1:]

    def check(self, code: int, params: bytes = b"") -> bytes:
        confirm, data = self.command(code, params)
        if confirm != OK:
            raise SensorError(ERRORS.get(confirm, f"Fehlercode {confirm:#04x}"))
        return data

    # ---- Befehle
    def handshake(self) -> bool:
        confirm, _ = self.command(CMD_VERIFY_PASSWORD, (0).to_bytes(4, "big"))
        return confirm == OK

    def sys_params(self) -> dict:
        d = self.check(CMD_READ_SYS_PARA)
        return {"capacity": int.from_bytes(d[4:6], "big") or 100, "security": int.from_bytes(d[6:8], "big"),
                "packet": 32 << int.from_bytes(d[12:14], "big"), "baud": int.from_bytes(d[14:16], "big") * 9600}

    def get_image(self) -> int:
        return self.command(CMD_GET_IMAGE)[0]

    def gen_char(self, buffer: int) -> None:
        self.check(CMD_GEN_CHAR, bytes([buffer]))

    def reg_model(self) -> None:
        self.check(CMD_REG_MODEL)

    def store(self, buffer: int, slot: int) -> None:
        self.check(CMD_STORE, bytes([buffer]) + slot.to_bytes(2, "big"))

    def search(self, buffer: int, capacity: int) -> tuple[int, int] | None:
        confirm, d = self.command(CMD_SEARCH, bytes([buffer]) + (0).to_bytes(2, "big") + capacity.to_bytes(2, "big"))
        if confirm == NOT_FOUND:
            return None
        if confirm != OK:
            raise SensorError(ERRORS.get(confirm, f"Fehlercode {confirm:#04x}"))
        return int.from_bytes(d[0:2], "big"), int.from_bytes(d[2:4], "big")

    def delete(self, slot: int, count: int = 1) -> None:
        self.check(CMD_DELETE, slot.to_bytes(2, "big") + count.to_bytes(2, "big"))

    def empty(self) -> None:
        self.check(CMD_EMPTY)

    def used_slots(self, capacity: int) -> set[int]:
        used = set()
        for page in range(max(1, (capacity + 255) // 256)):
            table = self.check(CMD_READ_INDEX_TABLE, bytes([page]))
            for i, byte in enumerate(table[:32]):
                for bit in range(8):
                    if byte & (1 << bit):
                        used.add(page * 256 + i * 8 + bit)
        return {s for s in used if s < capacity}


# --------------------------------------------------------------------------- Suche
def candidate_ports() -> list[str]:
    """Nur USB-Seriell-Adapter mit typischen Chips (CH340, CP210x, FTDI, PL2303) – andere Geräte
    (Arduino mit eigenem USB, Modems …) werden nicht angefasst. Zuletzt gefundener Anschluss zuerst."""
    if not HAVE_SERIAL:
        return []
    ports = [p.device for p in list_ports.comports() if (p.vid, p.pid) in USB_SERIAL_IDS]
    last = _last_port()
    ports.sort(key=lambda d: d != last)
    return ports


def _cache_file() -> Path:
    from ..config import config_dir

    return config_dir() / "fingerprint-module.json"


def _last_port() -> str:
    try:
        return json.loads(_cache_file().read_text(encoding="utf-8")).get("port", "")
    except Exception:  # noqa: BLE001
        return ""


def _remember(port: str, baud: int) -> None:
    try:
        _cache_file().parent.mkdir(parents=True, exist_ok=True)
        _cache_file().write_text(json.dumps({"port": port, "baud": baud}), encoding="utf-8")
    except OSError:
        pass


def probe(port: str) -> tuple[int, dict] | None:
    """Antwortet an `port` ein Modul? → (Baudrate, Parameter)."""
    remembered = None
    try:
        cached = json.loads(_cache_file().read_text(encoding="utf-8"))
        if cached.get("port") == port:
            remembered = int(cached.get("baud", 0))
    except Exception:  # noqa: BLE001
        pass
    for baud in ([remembered] if remembered else []) + [b for b in BAUDS if b != remembered]:
        try:
            with ZWSensor(port, baud, timeout=0.4) as s:
                if s.handshake():
                    return baud, s.sys_params()
        except SensorError as exc:
            if "Kein Zugriff" in str(exc):
                raise
        except Exception:  # noqa: BLE001
            continue
    return None


def usb_serial_present() -> bool:
    """Steckt ein USB-Seriell-Adapter (auch wenn kein Zugriff besteht)?"""
    if not HAVE_SERIAL:
        return False
    return any(p.vid is not None for p in list_ports.comports())


# --------------------------------------------------------------------------- Namen der Plätze
def _slots_file() -> Path:
    from ..config import config_dir

    return config_dir() / "fingerprint-slots.json"


def load_slots() -> dict[str, dict]:
    try:
        return json.loads(_slots_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_slots(slots: dict[str, dict]) -> None:
    path = _slots_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(slots, indent=1), encoding="utf-8")


def current_user() -> str:
    import getpass

    return getpass.getuser()


# --------------------------------------------------------------------------- Backend
class SerialFingerprintBackend(FingerprintBackend):
    name = "Modul am seriellen Anschluss"
    can_enroll = True
    can_delete = True
    can_list_enrolled = True
    login_toggle = sys.platform.startswith("linux")  # Windows-Anmeldung geht nur mit Windows Hello

    def __init__(self):
        self._cancel = threading.Event()
        self._found: dict[str, tuple[int, dict]] = {}

    # ---- Sensoren
    def availability(self):
        if not HAVE_SERIAL:
            return (False, "Python-Paket „pyserial“ fehlt.")
        try:
            sensors = self.list_sensors()
        except SensorError as exc:
            return (False, str(exc))
        if not sensors:
            return (False, "Kein Fingerabdruckmodul am seriellen Anschluss gefunden.")
        return (True, "")

    def list_sensors(self):
        sensors = []
        self._found = {}
        denied = []
        for port in candidate_ports():
            try:
                result = probe(port)
            except SensorError as exc:  # kein Zugriff auf diesen Anschluss → trotzdem die anderen prüfen
                denied.append(str(exc))
                continue
            if result is None:
                continue
            baud, params = result
            self._found[port] = result
            sensors.append(Sensor(id=port, name=f"Fingerabdruckmodul an {port}",
                                  detail=f"{params['capacity']} Plätze, {baud} Baud"))
        if not sensors and denied:
            raise SensorError(denied[0])
        if sensors:
            _remember(sensors[0].id, self._found[sensors[0].id][0])
        return sensors

    def _open(self, port: str) -> tuple[ZWSensor, int]:
        baud, params = self._found.get(port) or probe(port) or (None, None)
        if baud is None:
            raise SensorError(f"Kein Modul an {port}")
        self._found[port] = (baud, params)
        s = ZWSensor(port, baud, timeout=1.0)
        s.open()
        return s, params["capacity"]

    # ---- Finger
    def finger_label(self, key: str) -> str:
        slot = key.split(":", 1)[1] if key.startswith("platz:") else key
        info = load_slots().get(slot, {})
        name = FINGER_NAMES.get(info.get("finger", ""), "Finger")
        who = info.get("user")
        return f"{name} (Platz {slot}" + (f", {who})" if who and who != current_user() else ")")

    def list_enrolled(self, sensor_id):
        s, cap = self._open(sensor_id)
        with s:
            used = s.used_slots(cap)
        slots = load_slots()
        # Plätze, die im Modul gelöscht wurden, auch hier vergessen
        cleaned = {k: v for k, v in slots.items() if int(k) in used}
        if cleaned != slots:
            save_slots(cleaned)
        return [f"platz:{slot}" for slot in sorted(used)]

    def is_enrolled(self, sensor_id, finger) -> bool:
        used = set(self.list_enrolled(sensor_id))
        user = current_user()
        return any(info.get("finger") == finger and info.get("user") == user and f"platz:{slot}" in used
                   for slot, info in load_slots().items())

    def _wait_finger(self, s: ZWSensor, status, text, stage, total, timeout=30.0):
        status(text, stage, total)
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if self._cancel.is_set():
                raise Cancelled()
            code = s.get_image()
            if code == OK:
                return
            if code != NO_FINGER:
                status(ERRORS.get(code, "Bitte noch einmal auflegen."), stage, total)
            time.sleep(0.05)
        raise SensorError("Zeit abgelaufen – kein Finger erkannt")

    def _wait_lift(self, s: ZWSensor, status, stage, total):
        status("Finger kurz abheben …", stage, total)
        end = time.monotonic() + 15
        while time.monotonic() < end:
            if self._cancel.is_set():
                raise Cancelled()
            if s.get_image() == NO_FINGER:
                return
            time.sleep(0.05)

    def enroll(self, sensor_id, finger, status):
        self._cancel.clear()
        user = current_user()
        s, cap = self._open(sensor_id)
        total = SCANS_PER_ENROLL + 1
        with s:
            used = s.used_slots(cap)
            free = next((i for i in range(cap) if i not in used), None)
            if free is None:
                raise SensorError("Der Speicher des Moduls ist voll – bitte erst Finger löschen.")
            for scan in range(1, SCANS_PER_ENROLL + 1):
                for attempt in range(3):
                    self._wait_finger(s, status, f"Finger auflegen ({scan}/{SCANS_PER_ENROLL}) …", scan - 1, total)
                    try:
                        s.gen_char(scan)
                        break
                    except SensorError as exc:
                        status(f"{exc} – noch einmal.", scan - 1, total)
                        self._wait_lift(s, status, scan - 1, total)
                else:
                    raise SensorError("Der Finger wurde nicht gut erkannt – bitte später erneut versuchen.")
                if scan < SCANS_PER_ENROLL:
                    self._wait_lift(s, status, scan, total)
            status("Speichern …", SCANS_PER_ENROLL, total)
            s.reg_model()
            s.store(1, free)
            # derselbe Finger war für diesen Benutzer schon angelernt → alten Platz freigeben
            slots = load_slots()
            for slot, info in list(slots.items()):
                if info.get("finger") == finger and info.get("user") == user and int(slot) != free:
                    try:
                        s.delete(int(slot))
                    except SensorError:
                        pass
                    slots.pop(slot)
            slots[str(free)] = {"finger": finger, "user": user}
            save_slots(slots)
            status("Fertig! Finger gespeichert.", total, total)
        self._sync_login(sensor_id)

    def verify(self, sensor_id, status):
        self._cancel.clear()
        s, cap = self._open(sensor_id)
        with s:
            self._wait_finger(s, status, "Finger auf den Sensor legen …", 0, 0)
            try:
                s.gen_char(1)
            except SensorError as exc:
                return (False, str(exc))
            hit = s.search(1, cap)
        if hit is None:
            return (False, "Nicht erkannt – dieser Finger ist nicht gespeichert.")
        slot, score = hit
        return (True, f"Erkannt: {self.finger_label(f'platz:{slot}')} – Übereinstimmung {score}")

    def delete(self, sensor_id, finger):
        s, cap = self._open(sensor_id)
        with s:
            if finger == "*":
                s.empty()
                save_slots({})
                self._sync_login(sensor_id)
                return
            slot = int(finger.split(":", 1)[1])
            s.delete(slot)
        slots = load_slots()
        slots.pop(str(slot), None)
        save_slots(slots)
        self._sync_login(sensor_id)

    def _sync_login(self, port: str) -> None:
        """Ist die Anmeldung an, muss die Zuordnung Finger → Benutzer in /etc nachgezogen werden."""
        if self.login_enabled():
            from .linux_serial_login import update_login

            try:
                update_login(login_config(port, self._found.get(port, (57600, {}))[0]))
            except Exception as exc:  # noqa: BLE001
                raise SensorError(f"Im Modul erledigt – aber die Anmeldung wurde nicht aktualisiert ({exc}). "
                                  "Bitte unten „Anmelden mit Fingerabdruck“ aus- und wieder einschalten.") from exc

    def cancel(self):
        self._cancel.set()

    def install_hint(self):
        if sys.platform.startswith("win"):
            return ("Modul am USB-Seriell-Adapter einstecken. Fehlt der Treiber (CH340), installiert ihn "
                    "Windows Update meist selbst.")
        return "Modul am USB-Seriell-Adapter einstecken."

    # ---- Anmeldung (Linux, über PAM)
    def login_enabled(self):
        if not self.login_toggle:
            return None
        try:
            return "--fingerabdruck-pam" in Path("/etc/pam.d/common-auth").read_text(encoding="utf-8")
        except OSError:
            return None

    def set_login_enabled(self, enabled):
        from .linux_serial_login import disable_login, enable_login

        if enabled:
            port = next(iter(self._found), "")
            enable_login(login_config(port, self._found.get(port, (57600, {}))[0]))
        else:
            disable_login()


def login_config(port: str, baud: int) -> dict:
    """Was die Anmelde-Prüfung braucht: welche Plätze gehören welchem Benutzer, wo steckt das Modul."""
    users: dict[str, list[int]] = {}
    for slot, info in load_slots().items():
        users.setdefault(info.get("user", ""), []).append(int(slot))
    users.pop("", None)
    return {"users": users, "port": port, "baud": baud, "timeout": 6}


# --------------------------------------------------------------------------- Anmelde-Prüfung (PAM)
def pam_check(env=None, login_file: Path = LOGIN_FILE, out=None) -> int:
    """Wird von pam_exec aufgerufen (Befehl `alupc --fingerabdruck-pam`). 0 = Finger passt zum Benutzer."""
    env = os.environ if env is None else env
    out = out or sys.stdout
    if hasattr(os, "fork") and env is os.environ:  # echter PAM-Aufruf: nie länger als 30 s blockieren
        import signal

        signal.signal(signal.SIGALRM, lambda *_: os._exit(1))
        signal.alarm(30)
    user = env.get("PAM_USER", "")
    try:
        cfg = json.loads(Path(login_file).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return 1
    allowed = set(cfg.get("users", {}).get(user, []))
    if not allowed or not HAVE_SERIAL:
        return 1
    ports = [cfg.get("port")] if cfg.get("port") else []
    ports += [p for p in candidate_ports() if p not in ports]
    timeout = float(cfg.get("timeout", 6))
    for port in ports:
        for baud in [cfg.get("baud")] + [b for b in BAUDS if b != cfg.get("baud")]:
            if not baud:
                continue
            try:
                with ZWSensor(port, int(baud), timeout=0.5) as s:
                    if not s.handshake():
                        continue
                    cap = s.sys_params()["capacity"]
                    print("Finger auf den Sensor legen …", file=out, flush=True)
                    end = time.monotonic() + timeout
                    tries = 0
                    while time.monotonic() < end and tries < 3:
                        if s.get_image() != OK:
                            time.sleep(0.05)
                            continue
                        tries += 1
                        try:
                            s.gen_char(1)
                            hit = s.search(1, cap)
                        except SensorError:
                            hit = None
                        if hit is not None and hit[0] in allowed:
                            return 0
                        print("Nicht erkannt.", file=out, flush=True)
                        time.sleep(0.4)
                    return 1
            except Exception:  # noqa: BLE001
                continue
    return 1
