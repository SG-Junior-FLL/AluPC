"""Willkommen nach dem Fingerabdruck: Wer sich mit dem Finger anmeldet (oder entsperrt), wird mit Namen begrüßt.

Woher AluPC weiß, wer es war:
* Linux: Die PAM-Prüfung (`alupc --fingerabdruck-pam`) merkt sich den erkannten Platz – als root in
  /run/alupc/finger-<Benutzer>.json (nur root darf dort schreiben), beim Entsperren (läuft als der Benutzer
  selbst) in ~/.cache/alupc/last-finger.json.
* Windows: Der Anmeldebaustein schreibt „Platz;Zeit“ in die Registry (HKLM\\SOFTWARE\\AluPC\\Fingerprint,
  Wert = Benutzername). Normale Benutzer dürfen dort nur lesen.
AluPC schaut alle 2 s nach, ob ein neuer Eintrag da ist, und ordnet den Platz über die Namen aus der
Fingerabdruck-Seite einer Person zu.
"""

from __future__ import annotations

import json
import os
import stat
import sys
import time
from pathlib import Path

RUN_DIR = Path("/run/alupc")
REG_KEY = r"SOFTWARE\AluPC\Fingerprint"
STYLES = {"aurora": "Aurora", "konfetti": "Konfetti", "scan": "Scan", "zufall": "Zufällig"}


def _safe(user: str) -> str:
    return "".join(c if (c.isascii() and c.isalnum()) or c in "._-" else "_" for c in user) or "x"


# --------------------------------------------------------------------------- merken (Linux, PAM)
def record_login(user: str, slot: int, now: float | None = None, run_dir: Path = RUN_DIR,
                 euid: int | None = None, home: str | None = None) -> Path | None:
    """Erkannten Platz merken. Nie eine Ausnahme – die Anmeldung darf daran nicht scheitern."""
    try:
        euid = os.geteuid() if euid is None else euid
        if euid == 0:
            run_dir.mkdir(mode=0o755, exist_ok=True)
            st = os.lstat(run_dir)
            if not stat.S_ISDIR(st.st_mode) or st.st_uid != 0 or st.st_mode & 0o022:
                return None  # fremder oder beschreibbarer Ordner → lieber nichts schreiben
            path = run_dir / f"finger-{_safe(user)}.json"
        else:
            if home is None:
                import pwd

                pw = pwd.getpwnam(user)
                if pw.pw_uid != euid:
                    return None
                home = pw.pw_dir
            path = Path(home) / ".cache" / "alupc" / "last-finger.json"
            path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o644)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump({"slot": int(slot), "time": time.time() if now is None else now}, f)
        os.replace(tmp, path)
        return path
    except Exception:  # noqa: BLE001
        return None


# --------------------------------------------------------------------------- lesen (AluPC)
def _read_json(path: Path) -> tuple[int, float] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return int(data["slot"]), float(data["time"])
    except (OSError, ValueError, KeyError, TypeError):
        return None


def _read_registry(users: list[str]) -> tuple[int, float] | None:
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, REG_KEY) as key:
            for user in users:
                try:
                    value, _ = winreg.QueryValueEx(key, user)
                except OSError:
                    continue
                slot, when = str(value).split(";", 1)
                return int(slot), float(when)
    except (OSError, ValueError, ImportError):
        return None
    return None


def last_login(user: str | None = None, run_dir: Path = RUN_DIR, home: str | None = None) -> tuple[int, float] | None:
    """(Platz, Zeit) der letzten Anmeldung mit dem Finger für diesen Benutzer – oder None."""
    import getpass

    user = user or getpass.getuser()
    if sys.platform.startswith("win"):
        names = [user]
        account = os.environ.get("USERNAME", "")
        if account and account != user:
            names.append(account)
        return _read_registry(names)
    home = home or os.path.expanduser("~")
    found = [r for r in (_read_json(run_dir / f"finger-{_safe(user)}.json"),
                         _read_json(Path(home) / ".cache" / "alupc" / "last-finger.json")) if r]
    return max(found, key=lambda r: r[1]) if found else None


def person_for_slot(slot: int) -> str:
    from .platform.zw_fingerprint import my_names

    return my_names().get(int(slot), "")


def display_name(config, person: str) -> str:
    """Eigener Begrüßungsname (Fenster „Begrüßung“) – sonst der Name der Person."""
    names = config["welcome"].get("names") or {}
    return str(names.get(person) or person or "").strip()


# --------------------------------------------------------------------------- Geburtstage
def parse_birthday(text: str) -> str | None:
    """„24.12.“, „24.12“ oder „24.12.2010“ → „12-24“. Leer → "". Ungültig → None."""
    import re

    text = (text or "").strip()
    if not text:
        return ""
    m = re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.?(\d{2,4})?", text)
    if not m:
        return None
    day, month = int(m.group(1)), int(m.group(2))
    days = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    if not (1 <= month <= 12 and 1 <= day <= days[month - 1]):
        return None
    return f"{month:02d}-{day:02d}"


def format_birthday(value: str) -> str:
    """„12-24“ → „24.12.“"""
    try:
        month, day = value.split("-")
        return f"{int(day):02d}.{int(month):02d}."
    except (ValueError, AttributeError):
        return ""


def is_birthday(config, person: str, today=None) -> bool:
    import datetime

    value = (config["welcome"].get("birthdays") or {}).get(person or "", "")
    if not value:
        return False
    today = today or datetime.date.today()
    if value == "02-29" and today.month == 2 and today.day == 28:  # kein Schaltjahr → am 28. feiern
        try:
            datetime.date(today.year, 2, 29)
        except ValueError:
            return True
    return value == f"{today.month:02d}-{today.day:02d}"
