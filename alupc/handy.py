"""iPhone/iPad → Monitor 2 per AirPlay (über das freie Programm UxPlay).

AirPlay: Das freie Programm UxPlay (GPL) empfängt. Ab UxPlay 1.73 gibt es die Option `-vrtp`: UxPlay
leitet das Bild dann als Videostrom an AluPC weiter und AluPC zeigt es als ganz normale Quelle an
(auch in eigenen Szenen, mit Standbild usw.). Ältere Versionen (z. B. aus Kubuntu 24.04: 1.68)
zeigen das Bild in einem eigenen Fenster – das legt AluPC im Vollbild auf Monitor 2.


UxPlay wird nicht mitgeliefert: Kubuntu installiert es per apt; unter Windows installiert AluPC per winget
„uxplay-windows“ (Community-Paket mit eingebautem UxPlay) und steuert es über dessen arguments.txt.
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
def bundled_uxplay_dir() -> Path | None:
    """Windows-Installer: UxPlay liegt mit seinen GStreamer-Bibliotheken im Programmordner (uxplay/)."""
    base = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent
    folder = base / "uxplay"
    return folder if (folder / "bin" / "uxplay.exe").is_file() else None


def uxplay_environment(uxplay: str) -> dict[str, str]:
    """Umgebung für ein mitgeliefertes UxPlay: eigene DLLs und GStreamer-Plugins statt Systemsuche."""
    folder = bundled_uxplay_dir()
    if folder is None or Path(uxplay).resolve() != (folder / "bin" / "uxplay.exe").resolve():
        return {}
    plugins = str(folder / "lib" / "gstreamer-1.0")
    env = {"PATH": str(folder / "bin") + os.pathsep + os.environ.get("PATH", ""),
           "GST_PLUGIN_PATH": plugins, "GST_PLUGIN_SYSTEM_PATH_1_0": plugins, "GST_PLUGIN_SYSTEM_PATH": plugins,
           "GST_REGISTRY": str(config_dir() / "gst-registry.bin")}
    scanner = folder / "libexec" / "gstreamer-1.0" / "gst-plugin-scanner.exe"
    if scanner.is_file():
        env["GST_PLUGIN_SCANNER"] = str(scanner)
    return env


# „uxplay-windows“ (Community-Paket von leapbtw, winget „leapbtw.uxplay“): Tray-Programm mit eingebautem UxPlay.
# Es liest seine UxPlay-Optionen aus arguments.txt – darüber steuert AluPC Name, Code und Ports.
UXPLAY_WINDOWS_EXE = "uxplay-windows.exe"


def uxplay_windows_candidates() -> list[str]:
    env = os.environ
    bases = [env.get("ProgramFiles", r"C:\Program Files"), env.get("ProgramW6432", ""),
             env.get("ProgramFiles(x86)", ""), os.path.join(env.get("LOCALAPPDATA", ""), "Programs")]
    return [os.path.join(b, "uxplay-windows", UXPLAY_WINDOWS_EXE) for b in bases if b]


def find_uxplay_windows(configured: str = "") -> str | None:
    if configured and configured.lower().endswith(UXPLAY_WINDOWS_EXE) and Path(configured).is_file():
        return configured
    if not IS_WINDOWS:
        return None
    for candidate in uxplay_windows_candidates():
        if Path(candidate).is_file():
            return candidate
    return None


def is_uxplay_windows(path: str | None) -> bool:
    return bool(path) and re.split(r"[\\/]", path)[-1].lower() == UXPLAY_WINDOWS_EXE


def uxplay_windows_arguments_file() -> Path:
    """Die Datei, aus der uxplay-windows seine Optionen liest (Benutzer-Datei unter %APPDATA%)."""
    return Path(os.environ.get("APPDATA", str(Path.home()))) / "leapbtw" / "uxplay-windows" / "arguments.txt"


def uxplay_windows_machine_file() -> Path:
    """Liegt diese Datei vor, hat sie bei uxplay-windows Vorrang (nur mit Adminrechten änderbar)."""
    return Path(os.environ.get("ProgramData", r"C:\ProgramData")) / "uxplay-windows" / "arguments.txt"


def uxplay_windows_command_line(args: list[str]) -> str:
    """Optionen als eine Zeile für arguments.txt (uxplay-windows zerlegt sie wie eine Kommandozeile)."""
    out = []
    for a in args:
        a = a.replace('"', "").replace("%", "")  # %…% würde uxplay-windows als Umgebungsvariable ersetzen
        out.append(f'"{a}"' if (not a or " " in a) else a)
    return " ".join(out)


def uxplay_windows_log_tail(lines: int = 15) -> list[str]:
    """Letzte Zeilen aus dem neuesten Protokoll von uxplay-windows (für verständliche Fehlermeldungen)."""
    folder = Path(os.environ.get("LOCALAPPDATA", "")) / "uxplay-windows" / "logs"
    try:
        logs = sorted(folder.glob("uxplay-*.log"), key=lambda f: f.stat().st_mtime)
        if not logs:
            return []
        text = logs[-1].read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    return [line.strip() for line in text.splitlines() if line.strip()][-lines:]


def kill_uxplay_windows() -> None:
    """Laufendes uxplay-windows (z. B. aus dessen eigenem Autostart) beenden – es darf nur einen AirPlay-Empfänger geben."""
    if not IS_WINDOWS:
        return
    for exe in (UXPLAY_WINDOWS_EXE, "uxplay-bluetooth-beacon.exe"):
        try:
            subprocess.run(["taskkill", "/F", "/T", "/IM", exe], capture_output=True, timeout=10,
                           creationflags=0x08000000)
        except (OSError, subprocess.SubprocessError):
            pass


WINDOWS_UXPLAY = [r"C:\msys64\ucrt64\bin\uxplay.exe", r"C:\msys64\mingw64\bin\uxplay.exe",
                  r"C:\Program Files\UxPlay\uxplay.exe"]
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
    if is_uxplay_windows(uxplay):
        return False  # Tray-Programm: „-h“ würde es starten; zeigt das Bild immer im eigenen Fenster
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
    # -p: feste Ports (TCP 7000, 7001, 7100 / UDP 6000, 6001, 7011) – so lässt sich die Firewall gezielt öffnen
    args = ["-n", name or "AluPC", "-nh", "-p"]
    if pin:
        args += ["-pin", pin] if pin != "zufall" else ["-pin"]
    if port is not None:  # Bild an AluPC weiterleiten statt selbst anzeigen
        args += ["-vrtp", f"config-interval=1 ! udpsink host=127.0.0.1 port={port}"]
    else:  # eigenes Fenster im Vollbild (AluPC schiebt es auf Monitor 2)
        args += ["-fs"]
        if not IS_WINDOWS and window_title:
            args += ["-vs", "ximagesink"]  # X11-Fenster: Titel = Name, lässt sich überall platzieren
    return args


# --------------------------------------------------------------------------- AirPlay-Empfang
class AirPlayServer(QObject):
    """Startet/stoppt UxPlay. Mehrere Quellen können es gleichzeitig benutzen (Zähler)."""

    status = Signal(str)
    log_line = Signal(str)
    failed = Signal(str)  # UxPlay hat sich unerwartet beendet – verständliche Erklärung

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
        bundled = bundled_uxplay_dir() if IS_WINDOWS else None
        extra = ([str(bundled / "bin" / "uxplay.exe")] if bundled else []) + (WINDOWS_UXPLAY if IS_WINDOWS else [])
        configured = self.settings()["uxplay_path"]
        if IS_WINDOWS and bundled and not configured:
            return extra[0]  # mitgeliefertes UxPlay zuerst
        if is_uxplay_windows(configured):
            return find_uxplay_windows(configured)
        return find_program("uxplay", configured, extra) or find_uxplay_windows()

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
        if is_uxplay_windows(uxplay):
            return self._start_uxplay_windows(uxplay, s)
        stream = want_stream and supports_vrtp(uxplay)
        self.port = free_udp_port() if stream else 0
        if stream:
            self.sdp_path().parent.mkdir(parents=True, exist_ok=True)
            self.sdp_path().write_text(sdp_text(self.port), encoding="ascii")
        pin = s.get("pin", "")
        self.pin_code = pin if pin and pin != "zufall" else ""
        args = uxplay_args(s["airplay_name"], pin, self.port if stream else None)
        self.proc = QProcess(self)
        extra_env = uxplay_environment(uxplay)
        if extra_env:  # mitgeliefertes UxPlay (Windows-Installer): eigene GStreamer-Plugins
            from PySide6.QtCore import QProcessEnvironment

            env = QProcessEnvironment.systemEnvironment()
            for key, value in extra_env.items():
                env.insert(key, value)
            self.proc.setProcessEnvironment(env)
        self.proc.setProcessChannelMode(QProcess.MergedChannels)
        self.proc.readyReadStandardOutput.connect(self._read)
        self.proc.finished.connect(self._finished)
        self.proc.start(uxplay, args)
        self.mode = "stream" if stream else "fenster"
        self.status.emit("läuft")
        return self.mode

    def _start_uxplay_windows(self, exe: str, s: dict) -> str:
        """Windows: uxplay-windows mit AluPCs Name/Code starten. Es zeigt das Bild in einem eigenen Fenster."""
        pin = s.get("pin", "")
        if pin == "zufall":  # das Protokoll von uxplay-windows liest AluPC nicht live → Code selbst würfeln
            pin = random_pin()
        self.pin_code = pin
        args = ["-n", s["airplay_name"] or "AluPC", "-nh", "-p"] + (["-pin", pin] if pin else [])
        kill_uxplay_windows()  # evtl. mit anderen Einstellungen schon laufend (eigener Autostart)
        try:
            target = uxplay_windows_arguments_file()
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(uxplay_windows_command_line(args), encoding="utf-8")
        except OSError as exc:
            self.log = (self.log + [f"arguments.txt nicht schreibbar: {exc}"])[-60:]
        if uxplay_windows_machine_file().exists():
            self.log = (self.log + [f"Hinweis: {uxplay_windows_machine_file()} hat Vorrang – Name/Code von AluPC "
                                    "gelten dann nicht"])[-60:]
        self.proc = QProcess(self)
        self.proc.finished.connect(self._finished)
        self.proc.setWorkingDirectory(str(Path(exe).parent))
        self.proc.start(exe, [])
        self.port = 0
        self.mode = "fenster"
        self.status.emit("läuft")
        return self.mode

    def _finished(self, *_):
        self.status.emit("beendet")
        if self.users > 0:  # sollte laufen, ist aber weg → Grund aus den Meldungen ableiten
            log = self.log + (uxplay_windows_log_tail() if is_uxplay_windows(self.binary()) else [])
            self.failed.emit(explain_uxplay_error(log))
            self.proc = None

    def release(self) -> None:
        self.users = max(0, self.users - 1)
        if self.users == 0:
            # kurz warten: beim Szenenwechsel mit AirPlay in beiden Szenen nicht neu starten
            self._stop_timer.start()

    def _really_stop(self):
        if self.users == 0 and self.proc is not None:
            tray_app = IS_WINDOWS and is_uxplay_windows(self.proc.program())
            if not tray_app:
                self.proc.terminate()  # uxplay-windows ist ein Tray-Programm und reagiert darauf nicht
            if tray_app or not self.proc.waitForFinished(2000):
                self.proc.kill()
                self.proc.waitForFinished(2000)
            if tray_app:
                kill_uxplay_windows()  # auch den Bluetooth-Helfer
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


def explain_uxplay_error(log: list[str]) -> str:
    """Letzte UxPlay-Meldungen → verständlicher Grund mit Abhilfe."""
    text = "\n".join(log[-15:])
    if "DNS-SD" in text or "dns_sd" in text.lower():
        if IS_WINDOWS:
            return "Der Apple-Dienst „Bonjour“ fehlt oder läuft nicht – ohne ihn findet das iPhone den PC nicht."
        return ("Der Dienst „avahi-daemon“ läuft nicht – ohne ihn findet das iPhone den PC nicht. "
                "„Automatisch einrichten“ schaltet ihn ein.")
    if "video renderer" in text or "GStreamer" in text:
        return "GStreamer-Pakete fehlen (Videoausgabe) – „Automatisch einrichten“ installiert sie."
    if "Address already in use" in text or "bind" in text.lower():
        return "Die AirPlay-Ports sind belegt – läuft UxPlay schon (z. B. ein zweites AluPC)?"
    if "unknown option" in text:
        return "Diese UxPlay-Version kennt eine Option nicht: " + text.strip().splitlines()[-1]
    last = [line for line in log[-5:] if line.strip()]
    return "UxPlay hat sich beendet" + (f": {last[-1]}" if last else ".")


def random_pin() -> str:
    return f"{random.randint(0, 9999):04d}"


def install_command(program: str) -> list[str]:
    """Kubuntu: Paket per pkexec installieren (Passwortabfrage)."""
    return ["pkexec", "env", "DEBIAN_FRONTEND=noninteractive", "apt-get", "install", "-y", *APT_PACKAGES[program]]


APT_PACKAGES = {"uxplay": ["uxplay", "gstreamer1.0-plugins-good", "gstreamer1.0-plugins-bad", "gstreamer1.0-libav",
                           "avahi-daemon"]}
WINGET_IDS = {"bonjour": "Apple.Bonjour", "uxplay": "leapbtw.uxplay"}


def can_install() -> bool:
    return sys.platform.startswith("linux") and bool(shutil.which("apt-get")) and bool(shutil.which("pkexec"))


def can_winget() -> bool:
    return IS_WINDOWS and bool(shutil.which("winget"))


# --------------------------------------------------------------------------- Automatisch einrichten
AIRPLAY_PORTS = ["7000:7001/tcp", "7100/tcp", "6000:6001/udp", "7011/udp", "5353/udp"]  # zu „uxplay -p“


def missing_packages(packages: list[str]) -> list[str]:
    """Kubuntu: welche dieser Pakete sind (noch) nicht installiert?"""
    if not shutil.which("dpkg-query"):
        return []
    missing = []
    for pkg in packages:
        try:
            out = subprocess.run(["dpkg-query", "-W", "-f=${Status}", pkg], capture_output=True, text=True,
                                 timeout=10).stdout
        except (OSError, subprocess.SubprocessError):
            out = ""
        if "install ok installed" not in out:
            missing.append(pkg)
    return missing


def avahi_running() -> bool:
    """Linux: läuft der Dienst, über den iPhones den PC finden (mDNS/Bonjour)?"""
    if IS_WINDOWS:
        return True
    if shutil.which("systemctl"):
        try:
            if subprocess.run(["systemctl", "is-active", "avahi-daemon"], capture_output=True, text=True,
                              timeout=5).stdout.strip() == "active":
                return True
        except (OSError, subprocess.SubprocessError):
            pass
    try:
        return bool(shutil.which("pgrep")) and subprocess.run(["pgrep", "-x", "avahi-daemon"],
                                                              capture_output=True, timeout=5).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def linux_setup_script(packages: list[str], avahi: bool, firewall_port: int | None) -> str:
    """Ein Skript für EINE Passwortabfrage: Pakete, avahi-Dienst, Firewall (nur feste Werte, keine Eingaben)."""
    lines = ["set -e", "export DEBIAN_FRONTEND=noninteractive"]
    if packages:
        lines.append("apt-get install -y " + " ".join(packages))
    if avahi:
        lines.append("systemctl enable --now avahi-daemon")
    if firewall_port:
        rules = " && ".join(f"ufw allow {r}" for r in AIRPLAY_PORTS + [f"{int(firewall_port)}/tcp"])
        lines.append(f'if command -v ufw >/dev/null && ufw status | grep -q "Status: active"; then {rules}; fi')
    return "\n".join(lines)


def setup_plan(config) -> list[tuple[str, list[str]]]:
    """Was für AirPlay fehlt und automatisch eingerichtet werden kann: [(Beschreibung, Befehl)]."""
    plan = []
    if can_install():
        packages = missing_packages(APT_PACKAGES["uxplay"])
        avahi = not avahi_running()
        firewall = None if config["handy"].get("firewall_done") else int(config["cast"].get("port", 8765))
        if packages or avahi or firewall:
            parts = []
            if packages:
                parts.append("UxPlay installieren" if "uxplay" in packages else "Video-/Netzwerk-Pakete installieren")
            if avahi:
                parts.append("iPhone-Suche (avahi) einschalten")
            if firewall:
                parts.append("Firewall für AirPlay/Handy öffnen")
            plan.append((", ".join(parts), ["pkexec", "sh", "-c", linux_setup_script(packages, avahi, firewall)]))
    elif can_winget():
        if not bonjour_installed():
            plan.append(("Bonjour (damit das iPhone den PC findet) installieren", _winget(WINGET_IDS["bonjour"])))
        if not (find_uxplay_windows() or find_program("uxplay", "", WINDOWS_UXPLAY)):
            plan.append(("AirPlay-Empfänger (UxPlay für Windows) installieren", _winget(WINGET_IDS["uxplay"])))
    return plan


def _winget(package_id: str) -> list[str]:
    return ["winget", "install", "--id", package_id, "-e", "--silent",
            "--accept-source-agreements", "--accept-package-agreements"]


def bonjour_installed() -> bool:
    """Windows: gibt es den Dienst „Bonjour Service“ (Apple-Bonjour oder der von uxplay-windows)?"""
    if not IS_WINDOWS:
        return True
    if os.path.exists(os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "Bonjour",
                                   "mDNSResponder.exe")):
        return True
    try:
        return subprocess.run(["sc", "query", "Bonjour Service"], capture_output=True, timeout=10,
                              creationflags=0x08000000).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


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
