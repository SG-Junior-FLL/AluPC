"""Handy → Monitor 2: iPhone/iPad per AirPlay (über UxPlay) und Android (über scrcpy).

AirPlay: Das freie Programm UxPlay (GPL) empfängt. Ab UxPlay 1.73 gibt es die Option `-vrtp`: UxPlay
leitet das Bild dann als Videostrom an AluPC weiter und AluPC zeigt es als ganz normale Quelle an
(auch in eigenen Szenen, mit Standbild usw.). Ältere Versionen (z. B. aus Kubuntu 24.04: 1.68)
zeigen das Bild in einem eigenen Fenster – das legt AluPC im Vollbild auf Monitor 2.

Android: Einen Chromecast-Empfänger kann ein PC nicht spielen (Google lässt nur zertifizierte Geräte
zu). Das freie scrcpy zeigt den Handy-Bildschirm über USB oder WLAN (USB-Debugging nötig).

Beide Programme werden nicht mitgeliefert; AluPC findet sie (bzw. installiert sie unter Kubuntu nach
Rückfrage mit apt).
"""

from __future__ import annotations

import os
import random
import re
import shutil
import socket
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, QTimer, Signal

from .config import config_dir

IS_WINDOWS = sys.platform.startswith("win")
WINDOWS_UXPLAY = [r"C:\msys64\ucrt64\bin\uxplay.exe", r"C:\msys64\mingw64\bin\uxplay.exe",
                  r"C:\Program Files\UxPlay\uxplay.exe"]
WINDOW_TITLE_ANDROID = "AluPC Android"
# winget legt Programme hier als Verknüpfung ab (der PATH von AluPC kennt das nach der Installation noch nicht)
WINGET_LINKS = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "WinGet", "Links")


def find_program(name: str, configured: str = "", extra: list[str] | None = None) -> str | None:
    """Programm suchen: eigener Pfad aus dem Setup, dann PATH, dann bekannte Orte."""
    for candidate in [configured] if configured else []:
        if Path(candidate).is_file():
            return candidate
    found = shutil.which(name)
    if found:
        return found
    if IS_WINDOWS:
        linked = shutil.which(name, path=WINGET_LINKS)
        if linked:
            return linked
    for candidate in extra or []:
        if Path(candidate).is_file():
            return candidate
    return None


_vrtp_cache: dict[str, bool] = {}


def supports_vrtp(uxplay: str) -> bool:
    """Kann diese UxPlay-Version das Bild an AluPC weiterleiten (-vrtp, ab 1.73)?"""
    if uxplay not in _vrtp_cache:
        try:
            out = subprocess.run([uxplay, "-h"], capture_output=True, text=True, timeout=8)
            _vrtp_cache[uxplay] = "-vrtp" in (out.stdout + out.stderr)
        except (OSError, subprocess.SubprocessError):
            _vrtp_cache[uxplay] = False
    return _vrtp_cache[uxplay]


def free_udp_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def sdp_text(port: int) -> str:
    """Beschreibung des Videostroms von UxPlay (H.264 über RTP, Payload 96) für den Videoplayer."""
    return ("v=0\no=- 0 0 IN IP4 127.0.0.1\ns=AluPC AirPlay\nc=IN IP4 127.0.0.1\nt=0 0\n"
            f"m=video {port} RTP/AVP 96\na=rtpmap:96 H264/90000\n")


def uxplay_args(name: str, pin: str, port: int | None, window_title: bool = True) -> list[str]:
    args = ["-n", name or "AluPC", "-nh"]
    if pin:
        args += ["-pin", pin] if pin != "zufall" else ["-pin"]
    if port is not None:  # Bild an AluPC weiterleiten statt selbst anzeigen
        args += ["-vrtp", f"config-interval=1 ! udpsink host=127.0.0.1 port={port}"]
    else:  # eigenes Fenster im Vollbild (AluPC schiebt es auf Monitor 2)
        args += ["-fs"]
        if not IS_WINDOWS and window_title:
            args += ["-vs", "ximagesink"]  # X11-Fenster: Titel = Name, lässt sich überall platzieren
    return args


def scrcpy_args(rect: tuple[int, int, int, int]) -> list[str]:
    x, y, w, h = rect
    return ["--window-title", WINDOW_TITLE_ANDROID, "--window-x", str(x), "--window-y", str(y),
            "--window-width", str(w), "--window-height", str(h), "--window-borderless", "--fullscreen",
            "--stay-awake"]


# --------------------------------------------------------------------------- AirPlay-Empfang
class AirPlayServer(QObject):
    """Startet/stoppt UxPlay. Mehrere Quellen können es gleichzeitig benutzen (Zähler)."""

    status = Signal(str)
    log_line = Signal(str)

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.proc: QProcess | None = None
        self.users = 0
        self.mode = ""  # "stream" (an AluPC) oder "fenster" (eigenes Fenster)
        self.port = 0
        self.log: list[str] = []
        self.pin_code = ""
        self._stop_timer = QTimer(self, singleShot=True, interval=1500)
        self._stop_timer.timeout.connect(self._really_stop)

    def settings(self) -> dict:
        return {"airplay_name": "AluPC", "pin": "", "uxplay_path": "", **self.config["handy"]}

    def binary(self) -> str | None:
        return find_program("uxplay", self.settings()["uxplay_path"], WINDOWS_UXPLAY if IS_WINDOWS else [])

    def sdp_path(self) -> Path:
        return config_dir() / "airplay.sdp"

    def running(self) -> bool:
        return self.proc is not None and self.proc.state() != QProcess.NotRunning

    def acquire(self, want_stream: bool = True) -> str:
        """UxPlay starten (falls nötig). Rückgabe: Modus „stream“/„fenster“ oder Fehlertext."""
        self._stop_timer.stop()
        self.users += 1
        if self.running():
            return self.mode
        uxplay = self.binary()
        if not uxplay:
            self.users -= 1
            return "fehlt"
        s = self.settings()
        stream = want_stream and supports_vrtp(uxplay)
        self.port = free_udp_port() if stream else 0
        if stream:
            self.sdp_path().parent.mkdir(parents=True, exist_ok=True)
            self.sdp_path().write_text(sdp_text(self.port), encoding="ascii")
        pin = s.get("pin", "")
        self.pin_code = pin if pin and pin != "zufall" else ""
        args = uxplay_args(s["airplay_name"], pin, self.port if stream else None)
        self.proc = QProcess(self)
        self.proc.setProcessChannelMode(QProcess.MergedChannels)
        self.proc.readyReadStandardOutput.connect(self._read)
        self.proc.finished.connect(lambda *_: self.status.emit("beendet"))
        self.proc.start(uxplay, args)
        self.mode = "stream" if stream else "fenster"
        self.status.emit("läuft")
        return self.mode

    def release(self) -> None:
        self.users = max(0, self.users - 1)
        if self.users == 0:
            # kurz warten: beim Szenenwechsel mit AirPlay in beiden Szenen nicht neu starten
            self._stop_timer.start()

    def _really_stop(self):
        if self.users == 0 and self.proc is not None:
            self.proc.terminate()
            if not self.proc.waitForFinished(2000):
                self.proc.kill()
            self.proc = None
            self.status.emit("gestoppt")

    def _read(self):
        text = bytes(self.proc.readAllStandardOutput()).decode(errors="replace")
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            self.log = (self.log + [line])[-60:]
            self.log_line.emit(line)
            low = line.lower()
            if "pin" in low and any(ch.isdigit() for ch in line):  # „-pin“ ohne feste Zahl: Code steht im Log
                digits = "".join(ch for ch in line.split(":")[-1] if ch.isdigit())
                if len(digits) == 4:
                    self.pin_code = digits
                    self.status.emit("pin")

    def shutdown(self):
        self.users = 0
        self._really_stop()


_server: AirPlayServer | None = None


def airplay_server(config=None) -> AirPlayServer:
    global _server
    if _server is None:
        if config is None:
            raise RuntimeError("AirPlay-Empfang ist noch nicht eingerichtet")
        _server = AirPlayServer(config)
    elif config is not None:
        _server.config = config
    return _server


def random_pin() -> str:
    return f"{random.randint(0, 9999):04d}"


def install_command(program: str) -> list[str]:
    """Kubuntu: Paket per pkexec installieren (Passwortabfrage)."""
    return ["pkexec", "env", "DEBIAN_FRONTEND=noninteractive", "apt-get", "install", "-y", *APT_PACKAGES[program]]


APT_PACKAGES = {"uxplay": ["uxplay", "gstreamer1.0-plugins-good", "gstreamer1.0-plugins-bad", "gstreamer1.0-libav"],
                "scrcpy": ["scrcpy"]}
WINGET_IDS = {"scrcpy": "Genymobile.scrcpy", "bonjour": "Apple.Bonjour"}


def can_install() -> bool:
    return sys.platform.startswith("linux") and bool(shutil.which("apt-get")) and bool(shutil.which("pkexec"))


def can_winget() -> bool:
    return IS_WINDOWS and bool(shutil.which("winget"))


# --------------------------------------------------------------------------- Automatisch einrichten
def setup_plan(config) -> list[tuple[str, list[str]]]:
    """Was fehlt und automatisch installiert werden kann: [(Beschreibung, Befehl)] – ein Passwort/UAC je Schritt."""
    s = {"uxplay_path": "", "scrcpy_path": "", **config["handy"]}
    missing = [p for p in ("uxplay", "scrcpy") if not find_program(p, s[f"{p}_path"],
                                                                     WINDOWS_UXPLAY if p == "uxplay" and IS_WINDOWS else [])]
    plan = []
    if can_install() and missing:
        packages = [pkg for p in missing for pkg in APT_PACKAGES[p]]
        names = " und ".join({"uxplay": "UxPlay (iPhone)", "scrcpy": "scrcpy (Android)"}[p] for p in missing)
        plan.append((f"{names} installieren",
                     ["pkexec", "env", "DEBIAN_FRONTEND=noninteractive", "apt-get", "install", "-y", *packages]))
    elif can_winget():
        if "scrcpy" in missing:
            plan.append(("scrcpy (Android) installieren", _winget(WINGET_IDS["scrcpy"])))
        if "uxplay" in missing and not bonjour_installed():
            plan.append(("Bonjour (für AirPlay) installieren", _winget(WINGET_IDS["bonjour"])))
    return plan


def _winget(package_id: str) -> list[str]:
    return ["winget", "install", "--id", package_id, "-e", "--silent",
            "--accept-source-agreements", "--accept-package-agreements"]


def bonjour_installed() -> bool:
    if not IS_WINDOWS:
        return True
    return os.path.exists(os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "Bonjour",
                                       "mDNSResponder.exe"))


def run_plan(plan: list[tuple[str, list[str]]], status=None) -> list[str]:
    """Schritte nacheinander ausführen. Rückgabe: Fehlermeldungen (leer = alles gut)."""
    errors = []
    for i, (label, cmd) in enumerate(plan):
        if status:
            status(f"{label} …", i, len(plan))
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=1800,
                                  creationflags=0x08000000 if IS_WINDOWS else 0)
        except (OSError, subprocess.SubprocessError) as exc:
            errors.append(f"{label}: {exc}")
            continue
        if proc.returncode in (126, 127) and cmd[0] == "pkexec":
            errors.append(f"{label}: abgebrochen (kein Passwort)")
        elif proc.returncode != 0:
            last = (proc.stderr or proc.stdout or "fehlgeschlagen").strip().splitlines()
            errors.append(f"{label}: {last[-1] if last else 'fehlgeschlagen'}")
    _vrtp_cache.clear()
    return errors


def default_airplay_name() -> str:
    """Name, unter dem der PC am iPhone erscheint: „AluPC (Rechnername)“."""
    host = re.sub(r"[^\w .-]", "", socket.gethostname().split(".")[0])[:24]
    return f"AluPC ({host})" if host else "AluPC"


# --------------------------------------------------------------------------- Android per USB erkennen
def adb_path(scrcpy: str | None) -> str | None:
    found = find_program("adb")
    if found:
        return found
    if scrcpy:  # Windows-ZIP von scrcpy bringt adb.exe mit
        candidate = Path(scrcpy).with_name("adb.exe" if IS_WINDOWS else "adb")
        if candidate.is_file():
            return str(candidate)
    return None


def parse_adb_devices(output: str) -> list[dict]:
    """Ausgabe von „adb devices -l“ → [{serial, state, model}] (state: device / unauthorized / offline)."""
    devices = []
    for line in output.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 2 or parts[0].startswith("*"):
            continue
        info = dict(p.split(":", 1) for p in parts[2:] if ":" in p)
        devices.append({"serial": parts[0], "state": parts[1],
                        "model": info.get("model", "").replace("_", " ") or parts[0]})
    return devices


def android_devices(adb: str | None) -> list[dict]:
    if not adb:
        return []
    try:
        out = subprocess.run([adb, "devices", "-l"], capture_output=True, text=True, timeout=6,
                             creationflags=0x08000000 if IS_WINDOWS else 0).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    return parse_adb_devices(out)
