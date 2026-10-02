"""Systemstatus live: Prozessor, Arbeitsspeicher, Grafikkarte, Temperaturen, Lüfter, Laufwerke, Netzwerk, Akku.

Gemessen wird mit psutil in einem Hintergrund-Thread (einmal pro Sekunde, nur solange jemand zuschaut –
Seite „System“ offen oder Systemanzeige auf Monitor 2). Dazu:
- Temperaturen/Lüfter unter Linux aus /sys/class/hwmon (platform/fans.py).
- Grafikkarte: NVIDIA über `nvidia-smi` (Linux und Windows), AMD unter Linux über sysfs.
Windows meldet ohne Hersteller-Programme keine Prozessor-Temperaturen und keine Lüfter – das zeigt
AluPC dann ehrlich als „keine Daten“ an.
"""

from __future__ import annotations

import os
import platform
import shutil
import socket
import subprocess
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal

try:
    import psutil
except ImportError:  # pragma: no cover - psutil ist Abhängigkeit, fehlt höchstens im Quellcode-Start
    psutil = None

HISTORY = 60  # Sekunden Verlauf für die Kurven
SKIP_FS = {"squashfs", "tmpfs", "devtmpfs", "overlay", "proc", "sysfs", "iso9660", "udf", ""}
NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


@dataclass
class Gpu:
    name: str
    load: float | None = None  # %
    temp: float | None = None  # °C
    mem_used: float | None = None  # MiB
    mem_total: float | None = None
    fan: float | None = None  # %
    power: float | None = None  # W


@dataclass
class Disk:
    mount: str
    used: int
    total: int

    @property
    def percent(self) -> float:
        return self.used * 100 / self.total if self.total else 0.0


@dataclass
class Proc:
    pid: int
    name: str
    cpu: float  # % der ganzen CPU
    mem: int  # Bytes


@dataclass
class Snapshot:
    time: float = 0.0
    cpu: float = 0.0
    cores: list[float] = field(default_factory=list)
    freq: float | None = None  # MHz
    ram_used: int = 0
    ram_total: int = 0
    swap_used: int = 0
    swap_total: int = 0
    disks: list[Disk] = field(default_factory=list)
    disk_read: float = 0.0  # Bytes/s
    disk_write: float = 0.0
    net_up: float = 0.0  # Bytes/s
    net_down: float = 0.0
    battery: tuple[float, bool, int | None] | None = None  # (%, am Netz, Restsekunden)
    cpu_temp: float | None = None
    temps: list[tuple[str, float]] = field(default_factory=list)
    fans: list[tuple[str, int]] = field(default_factory=list)
    gpu: Gpu | None = None
    procs: list[Proc] = field(default_factory=list)
    uptime: float = 0.0

    @property
    def ram(self) -> float:
        return self.ram_used * 100 / self.ram_total if self.ram_total else 0.0


# --------------------------------------------------------------------------- Formatieren
def fmt_bytes(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit in ("B", "KB") or n >= 100 else f"{n:.1f} {unit}".replace(".", ",")
        n /= 1024
    return f"{n:.1f} TB"


def fmt_rate(n: float) -> str:
    return fmt_bytes(n) + "/s"


def fmt_uptime(seconds: float) -> str:
    m = int(seconds // 60)
    d, m = divmod(m, 1440)
    h, m = divmod(m, 60)
    if d:
        return f"{d} T. {h} Std."
    if h:
        return f"{h} Std. {m} Min."
    return f"{m} Min."


# --------------------------------------------------------------------------- feste Angaben
def cpu_model() -> str:
    try:
        if sys.platform.startswith("linux"):
            for line in Path("/proc/cpuinfo").read_text().splitlines():
                if line.startswith("model name"):
                    return clean_cpu_name(line.partition(":")[2])
        elif sys.platform == "win32":
            import winreg

            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as k:
                return clean_cpu_name(winreg.QueryValueEx(k, "ProcessorNameString")[0])
    except Exception:  # noqa: BLE001
        pass
    return clean_cpu_name(platform.processor()) or "Prozessor"


def clean_cpu_name(name: str) -> str:
    for junk in ("(R)", "(TM)", "(tm)", "CPU ", " Processor", "with Radeon Graphics"):
        name = name.replace(junk, " " if junk == "CPU " else "")
    name = name.split("@")[0]
    for suffix in ("-Core", "Core"):  # „8-Core“ am Ende weglassen
        parts = name.split()
        if parts and parts[-1].endswith(suffix) and parts[-1][0].isdigit():
            name = " ".join(parts[:-1])
    return " ".join(name.split())


def os_name() -> str:
    if sys.platform == "win32":
        try:
            build = sys.getwindowsversion().build
            return f"Windows {'11' if build >= 22000 else '10'}"
        except AttributeError:
            return "Windows"
    try:
        for line in Path("/etc/os-release").read_text().splitlines():
            if line.startswith("PRETTY_NAME="):
                return line.partition("=")[2].strip('"')
    except OSError:
        pass
    return platform.system()


def local_ip() -> str:
    """Adresse im Heimnetz (UDP-„Verbindung“ schickt kein Paket, wählt nur die Netzwerkkarte)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        return ""
    finally:
        s.close()


# --------------------------------------------------------------------------- Grafikkarte
NVIDIA_QUERY = "name,utilization.gpu,temperature.gpu,memory.used,memory.total,fan.speed,power.draw"


def _float(text: str) -> float | None:
    try:
        return float(text.strip())
    except ValueError:  # „[N/A]“, „[Not Supported]“
        return None


def parse_nvidia(text: str) -> Gpu | None:
    line = text.strip().splitlines()[0] if text.strip() else ""
    parts = [x.strip() for x in line.split(",")]
    if len(parts) < 5:
        return None
    vals = [_float(x) for x in parts[1:]] + [None] * 7
    return Gpu(parts[0].replace("NVIDIA ", ""), vals[0], vals[1], vals[2], vals[3], vals[4], vals[5])


def amd_gpu(drm: Path = Path("/sys/class/drm")) -> Gpu | None:
    for card in sorted(drm.glob("card[0-9]")):
        dev = card / "device"
        busy = dev / "gpu_busy_percent"
        if not busy.exists():
            continue
        try:
            gpu = Gpu("AMD-Grafikkarte", load=float(busy.read_text()))
            used, total = dev / "mem_info_vram_used", dev / "mem_info_vram_total"
            if used.exists() and total.exists():
                gpu.mem_used = int(used.read_text()) / 2**20
                gpu.mem_total = int(total.read_text()) / 2**20
            for hw in (dev / "hwmon").glob("hwmon*"):
                temp = hw / "temp1_input"
                if temp.exists():
                    gpu.temp = int(temp.read_text()) / 1000
                power = hw / "power1_average"
                if power.exists():
                    gpu.power = int(power.read_text()) / 1e6
            return gpu
        except (OSError, ValueError):
            continue
    return None


CPU_CHIPS = ("k10temp", "coretemp", "zenpower", "cpu_thermal", "acpitz")
CPU_LABELS = ("tctl", "tdie", "package id 0", "cpu")


def pick_cpu_temp(chips) -> float | None:
    """Prozessor-Temperatur aus den hwmon-Chips (bevorzugt k10temp/coretemp, deren Haupt-Sensor)."""
    for raw in CPU_CHIPS:
        for chip in chips:
            if chip.raw == raw and chip.temps:
                for want in CPU_LABELS:
                    for label, value in chip.temps:
                        if label.lower().startswith(want):
                            return value
                return max(v for _l, v in chip.temps)
    return None


# --------------------------------------------------------------------------- Messen
class Sampler:
    """Liest den Systemzustand; Raten (Netz, Laufwerke) aus dem Abstand zur letzten Messung."""

    def __init__(self):
        self._last_net = self._last_io = None
        self._last_t = 0.0
        self._procs: dict[int, object] = {}
        self._procs_at = 0.0
        self._disks: list[Disk] = []
        self._disks_at = 0.0
        self._nvidia = shutil.which("nvidia-smi")
        self._nvidia_off_until = 0.0
        self.top: list[Proc] = []
        if psutil:
            psutil.cpu_percent(None, percpu=True)  # erster Aufruf liefert 0 – Startpunkt setzen
            psutil.cpu_percent(None)

    def sample(self) -> Snapshot:
        now = time.monotonic()
        s = Snapshot(time=now)
        if psutil is None:
            return s
        s.cpu = psutil.cpu_percent(None)
        s.cores = psutil.cpu_percent(None, percpu=True)
        try:
            f = psutil.cpu_freq()
            s.freq = f.current if f else None
        except Exception:  # noqa: BLE001 - manche VMs/Kerne melden keinen Takt
            s.freq = None
        vm = psutil.virtual_memory()
        s.ram_used, s.ram_total = vm.total - vm.available, vm.total
        sw = psutil.swap_memory()
        s.swap_used, s.swap_total = sw.used, sw.total
        s.uptime = time.time() - psutil.boot_time()
        dt = now - self._last_t if self._last_t else 0
        net = psutil.net_io_counters()
        try:
            io = psutil.disk_io_counters()
        except Exception:  # noqa: BLE001
            io = None
        if dt > 0 and self._last_net and net:
            s.net_up = max(0.0, (net.bytes_sent - self._last_net.bytes_sent) / dt)
            s.net_down = max(0.0, (net.bytes_recv - self._last_net.bytes_recv) / dt)
        if dt > 0 and self._last_io and io:
            s.disk_read = max(0.0, (io.read_bytes - self._last_io.read_bytes) / dt)
            s.disk_write = max(0.0, (io.write_bytes - self._last_io.write_bytes) / dt)
        self._last_net, self._last_io, self._last_t = net, io, now
        if now - self._disks_at > 10 or not self._disks:
            self._disks, self._disks_at = self.read_disks(), now
        s.disks = self._disks
        try:
            b = psutil.sensors_battery()
            if b is not None:
                left = b.secsleft if isinstance(b.secsleft, int) and b.secsleft >= 0 else None
                s.battery = (b.percent, bool(b.power_plugged), left)
        except Exception:  # noqa: BLE001
            pass
        if sys.platform.startswith("linux"):
            from .platform import fans

            chips = fans.read_sensors()
            s.cpu_temp = pick_cpu_temp(chips)
            for chip in chips:
                if chip.temps:
                    s.temps.append((chip.name, max(v for _l, v in chip.temps)))
                s.fans += [(label, rpm) for label, rpm in chip.fans]
        s.gpu = self.read_gpu(now)
        if s.gpu and s.gpu.temp is not None and s.gpu.name and not any(n == s.gpu.name for n, _ in s.temps):
            if sys.platform == "win32":
                s.temps.append((s.gpu.name, s.gpu.temp))
        if now - self._procs_at >= 2:
            self.top, self._procs_at = self.read_procs(), now
        s.procs = self.top
        return s

    @staticmethod
    def read_disks() -> list[Disk]:
        out, seen = [], set()
        for part in psutil.disk_partitions(all=False):
            if part.fstype.lower() in SKIP_FS or "cdrom" in part.opts or part.device in seen:
                continue
            if part.mountpoint.startswith(("/snap", "/boot", "/var/snap", "/run")):
                continue
            try:
                u = psutil.disk_usage(part.mountpoint)
            except (OSError, PermissionError):
                continue
            if u.total < 1 << 30:  # kleine Hilfs-Partitionen (< 1 GB) weglassen
                continue
            seen.add(part.device)
            out.append(Disk(part.mountpoint, u.used, u.total))
        return out[:6]

    def read_gpu(self, now: float) -> Gpu | None:
        if self._nvidia and now >= self._nvidia_off_until:
            try:
                r = subprocess.run([self._nvidia, f"--query-gpu={NVIDIA_QUERY}", "--format=csv,noheader,nounits"],
                                   capture_output=True, text=True, timeout=2, creationflags=NO_WINDOW)
                gpu = parse_nvidia(r.stdout) if r.returncode == 0 else None
                if gpu:
                    return gpu
            except (OSError, subprocess.SubprocessError):
                pass
            self._nvidia_off_until = now + 30  # Treiber gerade weg? Später nochmal versuchen
        if sys.platform.startswith("linux"):
            return amd_gpu()
        return None

    def read_procs(self, count: int = 6) -> list[Proc]:
        cores = psutil.cpu_count() or 1
        alive, rows = {}, []
        own = os.getpid()
        for p in psutil.process_iter(["name"]):
            proc = self._procs.get(p.pid, p)
            alive[p.pid] = proc
            try:
                cpu = proc.cpu_percent(None) / cores
                if p.pid in (0, own) or not p.info.get("name") or p.info["name"] in ("System Idle Process", "Idle"):
                    continue
                rows.append(Proc(p.pid, p.info["name"], cpu, proc.memory_info().rss))
            except (psutil.Error, OSError):
                continue
        self._procs = alive
        rows.sort(key=lambda r: (r.cpu, r.mem), reverse=True)
        return rows[:count]


class SystemMonitor(QObject):
    """Misst einmal pro Sekunde im Hintergrund, solange mindestens ein Nutzer angemeldet ist."""

    updated = Signal(object)
    _arrived = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.snapshot = Snapshot()
        self.history = {k: deque([0.0] * HISTORY, maxlen=HISTORY)
                        for k in ("cpu", "ram", "gpu", "temp", "up", "down")}
        self.cpu_name = cpu_model()
        self.os = os_name()
        self.host = socket.gethostname()
        self.cores = (psutil.cpu_count() or 0) if psutil else 0
        self.ip = ""
        self._ip_at = 0.0
        self._users: set[int] = set()
        self._busy = False
        self._sampler: Sampler | None = None
        self._timer = QTimer(self, interval=1000)
        self._timer.timeout.connect(self._tick)
        self._arrived.connect(self._store)

    @property
    def available(self) -> bool:
        return psutil is not None

    def acquire(self, user) -> None:
        self._users.add(id(user))
        if not self._timer.isActive():
            self._timer.start()
            self._tick()

    def release(self, user) -> None:
        self._users.discard(user if isinstance(user, int) else id(user))
        if not self._users:
            self._timer.stop()

    @property
    def running(self) -> bool:
        return self._timer.isActive()

    def _tick(self) -> None:
        if self._busy or psutil is None:
            return
        self._busy = True
        threading.Thread(target=self._work, name="systemstatus", daemon=True).start()

    def _work(self) -> None:
        try:
            if self._sampler is None:
                self._sampler = Sampler()
            snap = self._sampler.sample()
            if time.monotonic() - self._ip_at > 30:
                self.ip, self._ip_at = local_ip(), time.monotonic()
        except Exception:  # noqa: BLE001 - Messfehler dürfen die App nicht stören
            snap = None
        self._arrived.emit(snap)

    def _store(self, snap) -> None:
        self._busy = False
        if snap is None:
            return
        self.snapshot = snap
        h = self.history
        h["cpu"].append(snap.cpu)
        h["ram"].append(snap.ram)
        h["gpu"].append(snap.gpu.load if snap.gpu and snap.gpu.load is not None else 0.0)
        h["temp"].append(snap.cpu_temp if snap.cpu_temp is not None else
                         (snap.gpu.temp if snap.gpu and snap.gpu.temp is not None else 0.0))
        h["up"].append(snap.net_up)
        h["down"].append(snap.net_down)
        self.updated.emit(snap)


_monitor: SystemMonitor | None = None


def monitor() -> SystemMonitor:
    global _monitor
    if _monitor is None:
        _monitor = SystemMonitor()
    return _monitor


# --------------------------------------------------------------------------- Steuern
POWER_TEXT = {"sperren": "Sperren", "energiesparen": "Energie sparen", "neustart": "Neu starten",
              "aus": "Herunterfahren", "abmelden": "Abmelden"}


def power_command(action: str, plat: str | None = None) -> list[str] | None:
    plat = plat or sys.platform
    if plat == "win32":
        return {"energiesparen": ["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"],
                "neustart": ["shutdown", "/r", "/t", "0"],
                "aus": ["shutdown", "/s", "/t", "0"],
                "abmelden": ["shutdown", "/l"]}.get(action)
    return {"energiesparen": ["systemctl", "suspend"],
            "neustart": ["systemctl", "reboot"],
            "aus": ["systemctl", "poweroff"],
            "abmelden": ["qdbus", "org.kde.Shutdown", "/Shutdown", "org.kde.Shutdown.logout"]}.get(action)


def power_action(action: str) -> None:
    cmd = power_command(action)
    if cmd is None:
        raise ValueError(f"unbekannte Aktion: {action}")
    try:
        subprocess.Popen(cmd, creationflags=NO_WINDOW, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError as exc:
        raise RuntimeError(f"{POWER_TEXT.get(action, action)} ging nicht: {exc}") from exc


def task_manager_command() -> list[str] | None:
    if sys.platform == "win32":
        return ["taskmgr.exe"]
    for prog in ("plasma-systemmonitor", "ksysguard", "gnome-system-monitor", "xfce4-taskmanager"):
        path = shutil.which(prog)
        if path:
            return [path]
    return None


def end_process(pid: int) -> None:
    if psutil is None:
        raise RuntimeError("psutil fehlt")
    try:
        psutil.Process(pid).terminate()
    except psutil.AccessDenied as exc:
        raise RuntimeError("Keine Berechtigung – das Programm gehört einem anderen Benutzer oder dem System.") from exc
    except psutil.NoSuchProcess:
        pass
