"""Lüfter und Temperaturen.

Linux: Der Kernel zeigt Sensoren unter /sys/class/hwmon (Temperaturen, Lüfter-Drehzahlen, PWM-Regler).
Lesen darf jeder; Lüfter STEUERN braucht Administratorrechte – AluPC ruft sich dafür per pkexec selbst
auf (`--luefter hwmon2/pwm1=128,…`), prüft dabei jeden Wert streng und lässt nie weniger als 30 % zu.
„Automatisch“ gibt die Steuerung zurück an Mainboard/BIOS. Nach einem Neustart regelt ohnehin wieder
das BIOS.

Windows: Es gibt keine allgemeine Schnittstelle für Lüfter/Temperaturen. Dafür braucht es
Hersteller-Programme oder z. B. „FanControl“ – AluPC kann das dort nicht.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

HWMON = Path("/sys/class/hwmon")
MIN_PERCENT = 30
PWM_RE = re.compile(r"^hwmon(\d{1,3})/pwm(\d{1,2})$")


@dataclass
class Pwm:
    id: str  # "hwmon2/pwm1"
    label: str
    value: int  # 0–255
    mode: int  # pwmN_enable: 0 = volle Kraft, 1 = manuell, ≥2 = automatisch (je nach Chip)

    @property
    def percent(self) -> int:
        return round(self.value * 100 / 255)

    @property
    def automatic(self) -> bool:
        return self.mode >= 2


@dataclass
class Chip:
    name: str
    raw: str = ""  # Name des Sensor-Chips im Kernel (bleibt über Neustarts gleich, hwmonN nicht)
    temps: list[tuple[str, float]] = field(default_factory=list)
    fans: list[tuple[str, int]] = field(default_factory=list)
    pwms: list[Pwm] = field(default_factory=list)


def _read(path: Path) -> str | None:
    try:
        return path.read_text().strip()
    except OSError:
        return None


def _num(path: Path) -> int | None:
    text = _read(path)
    try:
        return int(text) if text is not None else None
    except ValueError:
        return None


CHIP_NAMES = {"k10temp": "AMD-Prozessor", "coretemp": "Intel-Prozessor", "amdgpu": "AMD-Grafikkarte",
              "nvme": "SSD (NVMe)", "acpitz": "Mainboard (ACPI)", "iwlwifi_1": "WLAN", "thinkpad": "ThinkPad",
              "dell_smm": "Dell", "asus": "ASUS", "nouveau": "NVIDIA-Grafikkarte"}


def chip_title(name: str) -> str:
    if name.startswith(("nct", "it8", "f71", "w83")):
        return f"Mainboard ({name})"
    return CHIP_NAMES.get(name, name)


def read_sensors(root: Path | None = None) -> list[Chip]:
    root = root or HWMON
    chips = []
    if not root.is_dir():
        return chips
    for hw in sorted(root.glob("hwmon*"), key=lambda p: int(re.sub(r"\D", "", p.name) or 0)):
        raw = _read(hw / "name") or hw.name
        chip = Chip(name=chip_title(raw), raw=raw)
        for f in sorted(hw.glob("temp*_input")):
            n = f.name.split("_")[0]
            v = _num(f)
            if v is not None and -40_000 < v < 150_000:
                chip.temps.append((_read(hw / f"{n}_label") or f"Temperatur {n[4:]}", v / 1000))
        for f in sorted(hw.glob("fan*_input")):
            n = f.name.split("_")[0]
            v = _num(f)
            if v is not None:
                chip.fans.append((_read(hw / f"{n}_label") or f"Lüfter {n[3:]}", v))
        for f in sorted(hw.glob("pwm[0-9]*")):
            if not re.fullmatch(r"pwm\d+", f.name):
                continue
            value, mode = _num(f), _num(hw / f"{f.name}_enable")
            if value is None:
                continue
            chip.pwms.append(Pwm(f"{hw.name}/{f.name}", f"Regler {f.name[3:]}", value, mode if mode is not None else 2))
        if chip.temps or chip.fans or chip.pwms:
            chips.append(chip)
    return chips


# --------------------------------------------------------------------------- Steuern (mit Adminrechten)
def parse_request(text: str) -> list[tuple[str, str]]:
    """„hwmon2/pwm1=128,hwmon2/pwm2=auto:5“ → geprüfte Liste. Alles Unerwartete → ValueError."""
    out = []
    for part in text.split(","):
        pwm, _, value = part.strip().partition("=")
        if not PWM_RE.fullmatch(pwm):
            raise ValueError(f"ungültiger Regler: {pwm!r}")
        if value.startswith("auto"):
            mode = value.partition(":")[2] or "2"
            if not re.fullmatch(r"[2-9]", mode):
                raise ValueError(f"ungültiger Modus: {value!r}")
            out.append((pwm, f"auto:{mode}"))
        else:
            if not re.fullmatch(r"\d{1,3}", value) or not 0 <= int(value) <= 255:
                raise ValueError(f"ungültiger Wert: {value!r}")
            out.append((pwm, str(max(int(value), -(-255 * MIN_PERCENT // 100)))))  # aufrunden: ≥ 30 %
    if not out or len(out) > 32:
        raise ValueError("keine oder zu viele Regler")
    return out


def apply_request(text: str, root: Path = HWMON) -> int:
    """Läuft als Administrator (pkexec). Rückgabe: Exit-Code."""
    try:
        items = parse_request(text)
    except ValueError as exc:
        print(f"AluPC: {exc}", file=sys.stderr)
        return 2
    errors = 0
    for pwm, value in items:
        hw, name = pwm.split("/")
        base = root / hw
        target = (base / name).resolve()
        if not (base / name).exists() or not str(target).startswith("/sys/") and root == HWMON:
            errors += 1
            continue
        try:
            if value.startswith("auto:"):
                (base / f"{name}_enable").write_text(value.split(":")[1])
            else:
                (base / f"{name}_enable").write_text("1")
                (base / name).write_text(value)
        except OSError as exc:
            print(f"AluPC: {pwm}: {exc}", file=sys.stderr)
            errors += 1
    return 1 if errors else 0


def helper_command(request: str) -> list[str]:
    """pkexec-Aufruf von AluPC selbst (fertiges Programm oder aus dem Quellcode)."""
    if getattr(sys, "frozen", False):
        return ["pkexec", sys.executable, "--luefter", request]
    return ["pkexec", sys.executable, "-m", "alupc", "--luefter", request]


def set_fans(request: str) -> None:
    proc = subprocess.run(helper_command(request), capture_output=True, text=True, timeout=120)
    if proc.returncode == 126 or proc.returncode == 127:
        raise RuntimeError("Abgebrochen (kein Administrator-Passwort).")
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or "Lüfter konnten nicht gesetzt werden").strip().splitlines()[-1])


def supported() -> bool:
    return sys.platform.startswith("linux") and HWMON.is_dir() and os.path.exists("/usr/bin/pkexec")
