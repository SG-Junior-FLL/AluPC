"""Linux: Anmelden mit einem Fingerabdruckmodul am seriellen Anschluss (z. B. HLK-ZW101).

* PAM: Ein Profil für pam-auth-update ruft beim Anmelden, Entsperren und bei sudo
  `alupc --fingerabdruck-pam` auf (über pam_exec). Passt der Finger zum Benutzer, ist man drin –
  sonst geht es wie gewohnt mit dem Passwort weiter.
* udev: Angemeldete Benutzer bekommen Zugriff auf USB-Seriell-Adapter (sonst dürfte der
  Sperrbildschirm das Modul nicht lesen). Der Dienst „brltty“ (Braillezeilen) schnappt sich
  CH340-Adapter unter Ubuntu – er kann auf Wunsch entfernt werden.

Alles, was Systemdateien ändert, läuft über pkexec (Passwortabfrage).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

PAM_PROFILE = "alupc-fingerprint"
UDEV_RULE_PATH = "/etc/udev/rules.d/70-alupc-serial.rules"
UDEV_RULE = """# AluPC: angemeldete Benutzer dürfen USB-Seriell-Adapter benutzen (Fingerabdruckmodule wie HLK-ZW101)
SUBSYSTEM=="tty", ATTRS{idVendor}=="1a86", TAG+="uaccess"
SUBSYSTEM=="tty", ATTRS{idVendor}=="10c4", ATTRS{idProduct}=="ea60", TAG+="uaccess"
SUBSYSTEM=="tty", ATTRS{idVendor}=="0403", TAG+="uaccess"
SUBSYSTEM=="tty", ATTRS{idVendor}=="067b", ATTRS{idProduct}=="2303", TAG+="uaccess"
"""


def helper_command() -> str:
    """Befehl, den PAM aufruft (absoluter Pfad – PAM kennt kein PATH)."""
    if getattr(sys, "frozen", False):
        return f"{os.path.realpath(sys.executable)} --fingerabdruck-pam"
    return f"{os.path.realpath(sys.executable)} -m alupc --fingerabdruck-pam"


def pam_profile(command: str) -> str:
    return (
        "Name: AluPC Fingerabdruck (Modul am seriellen Anschluss, z. B. HLK-ZW101)\n"
        "Default: no\n"
        "Priority: 259\n"
        "Auth-Type: Primary\n"
        "Auth:\n"
        f"\t[success=end default=ignore]\tpam_exec.so quiet stdout {command}\n"
    )


def valid_config(cfg: dict) -> dict:
    """Nur erwartete Werte übernehmen (Benutzernamen, Platznummern, Anschluss) – landet in /etc."""
    users = {u: sorted({int(s) for s in slots}) for u, slots in cfg.get("users", {}).items()
             if re.fullmatch(r"[a-z_][a-z0-9_.-]{0,31}\$?", u)}
    port = str(cfg.get("port", ""))
    if port and not re.fullmatch(r"/dev/tty[A-Za-z0-9]+", port):
        port = ""
    return {"users": users, "port": port, "baud": int(cfg.get("baud", 57600)),
            "timeout": max(2, min(30, int(cfg.get("timeout", 6))))}


def _pkexec(script: str, *args: str, timeout: int = 600) -> None:
    if not shutil.which("pkexec"):
        raise RuntimeError("pkexec fehlt (sudo apt install pkexec).")
    # Daten als Parameter übergeben (nie in den Skripttext einsetzen)
    proc = subprocess.run(["pkexec", "sh", "-c", script, "alupc", *args],
                          capture_output=True, text=True, timeout=timeout)
    if proc.returncode in (126, 127):
        raise RuntimeError("Abgebrochen (Passwort nicht bestätigt).")
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "Fehlgeschlagen").strip().splitlines()[-1])


ENABLE_SCRIPT = r"""set -e
mkdir -p /etc/alupc
printf '%s\n' "$1" > /etc/alupc/fingerprint-login.json
chmod 644 /etc/alupc/fingerprint-login.json
printf '%s' "$2" > /usr/share/pam-configs/alupc-fingerprint
if [ ! -f /etc/udev/rules.d/70-alupc-serial.rules ]; then
    printf '%s' "$3" > /etc/udev/rules.d/70-alupc-serial.rules
    udevadm control --reload-rules || true
    udevadm trigger --subsystem-match=tty || true
fi
DEBIAN_FRONTEND=noninteractive pam-auth-update --enable alupc-fingerprint
"""

UPDATE_SCRIPT = r"""set -e
mkdir -p /etc/alupc
printf '%s\n' "$1" > /etc/alupc/fingerprint-login.json
chmod 644 /etc/alupc/fingerprint-login.json
"""

DISABLE_SCRIPT = r"""set -e
DEBIAN_FRONTEND=noninteractive pam-auth-update --remove alupc-fingerprint
rm -f /usr/share/pam-configs/alupc-fingerprint /etc/alupc/fingerprint-login.json
"""

ACCESS_SCRIPT = r"""set -e
printf '%s' "$1" > /etc/udev/rules.d/70-alupc-serial.rules
udevadm control --reload-rules || true
udevadm trigger --subsystem-match=tty || true
if [ "$2" = "brltty" ] && dpkg -s brltty >/dev/null 2>&1; then
    DEBIAN_FRONTEND=noninteractive apt-get remove -y brltty
fi
"""


def helper_is_safe(path: str | None = None) -> bool:
    """PAM startet das Prüfprogramm als root (z. B. bei sudo). Es darf also nur eine Datei sein, die
    root gehört und die kein normaler Benutzer ändern kann – sonst könnte man sich root-Rechte holen."""
    path = os.path.realpath(path or sys.executable)
    if not getattr(sys, "frozen", False) and path == os.path.realpath(sys.executable):
        return False  # Start aus dem Quellcode/venv: Python + Module liegen oft im Home-Ordner
    p = Path(path)
    for item in [p, *p.parents]:
        try:
            st = item.stat()
        except OSError:
            return False
        if st.st_uid != 0 or st.st_mode & 0o022:
            return False
        if item == Path("/"):
            break
    return True


def human_accounts(passwd: str = "/etc/passwd") -> list[str]:
    """Benutzerkonten von Menschen (UID 1000–59999 mit Anmelde-Shell)."""
    names = []
    try:
        lines = Path(passwd).read_text(encoding="utf-8").splitlines()
    except OSError:
        return names
    for line in lines:
        parts = line.split(":")
        if len(parts) < 7:
            continue
        try:
            uid = int(parts[2])
        except ValueError:
            continue
        if 1000 <= uid < 60000 and not parts[6].endswith(("nologin", "false")):
            names.append(parts[0])
    return names


def enable_login(cfg: dict) -> None:
    accounts = human_accounts()
    if len(accounts) > 1:
        # Das Modul hat keinen Zugriffsschutz: Wer den Adapter öffnen darf, kann Finger in beliebige
        # Plätze schreiben – bei mehreren Konten könnte sich jemand so als ein anderer Benutzer anmelden.
        raise RuntimeError("Anmelden mit diesem Modul ist nur auf PCs mit genau einem Benutzerkonto erlaubt "
                           f"(gefunden: {', '.join(accounts)}). Grund: Das Modul hat keinen Zugriffsschutz – "
                           "ein anderer Benutzer könnte sonst seinen Finger für dein Konto eintragen.")
    if not helper_is_safe():
        raise RuntimeError("Anmelden mit dem Modul geht nur mit dem installierten .deb-Paket von AluPC "
                           "(aus Sicherheitsgründen – das Prüfprogramm läuft beim Anmelden als root).")
    if not shutil.which("pam-auth-update"):
        raise RuntimeError("pam-auth-update nicht gefunden (kein Ubuntu/Kubuntu?).")
    cfg = valid_config(cfg)
    if not any(cfg["users"].values()):
        raise RuntimeError("Erst einen Finger anlernen.")
    _pkexec(ENABLE_SCRIPT, json.dumps(cfg), pam_profile(helper_command()), UDEV_RULE)


def update_login(cfg: dict) -> None:
    """Nach Anlernen/Löschen: Zuordnung Finger → Benutzer für die Anmeldung aktualisieren."""
    _pkexec(UPDATE_SCRIPT, json.dumps(valid_config(cfg)))


def disable_login() -> None:
    _pkexec(DISABLE_SCRIPT)


def brltty_installed() -> bool:
    return Path("/usr/bin/brltty").exists() or Path("/bin/brltty").exists()


def access_problem() -> str:
    """Warum sieht AluPC keinen Adapter bzw. darf ihn nicht öffnen? Leer = kein Problem erkannt."""
    ch340 = False
    try:
        for dev in Path("/sys/bus/usb/devices").iterdir():
            try:
                if (dev / "idVendor").read_text().strip() == "1a86":
                    ch340 = True
            except OSError:
                continue
    except OSError:
        pass
    ttys = list(Path("/dev").glob("ttyUSB*")) + list(Path("/dev").glob("ttyACM*"))
    if ch340 and not ttys and brltty_installed():
        return "brltty"  # bekanntes Ubuntu-Problem: brltty übernimmt CH340-Adapter
    if any(not os.access(t, os.R_OK | os.W_OK) for t in ttys):
        return "zugriff"
    return ""


def fix_access(remove_brltty: bool) -> None:
    _pkexec(ACCESS_SCRIPT, UDEV_RULE, "brltty" if remove_brltty else "", timeout=900)
