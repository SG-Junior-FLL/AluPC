"""CI (Windows, Admin): Legt AluPC die AirPlay-Firewall-Freigabe richtig an? – für alle Netzwerktypen, und von
Windows angelegte Sperr-Regeln für UxPlay werden ersetzt (sonst: iPhone sieht „AluPC“, Verbinden lädt endlos)."""

import os
import re
import subprocess
import sys

sys.path.insert(0, os.getcwd())

from alupc import handy  # noqa: E402


def note(text: str) -> None:
    print(f"::notice title=Firewall AirPlay::{text}", flush=True)


def netsh(*args: str) -> str:
    return subprocess.run(["netsh", "advfirewall", "firewall", *args], capture_output=True, text=True,
                          errors="replace").stdout


programs = handy.uxplay_programs()
for exe in programs:  # wie nach dem Wegklicken von Windows' Nachfrage: Sperr-Regel für das Programm
    netsh("add", "rule", "name=uxplay-windows", "dir=in", "action=block", f"program={exe}", "profile=public")
cmd = handy.windows_firewall_command("x", 8765)[-1]
script = re.search(r"'/c (.*)'", cmd, re.S).group(1).replace("''", "'")
subprocess.run(["cmd.exe", "/c", script], capture_output=True)  # CI läuft schon als Admin
air = netsh("show", "rule", "name=AluPC AirPlay")
profiles = sorted({line.split(":", 1)[1].strip() for line in air.splitlines() if line.strip().startswith("Profile")})
blocks = [block for block in netsh("show", "rule", "name=all", "dir=in", "verbose").split("\n\n")
          if "uxplay" in block.lower() and re.search(r"Action:\s*Block", block)]
ok = bool(profiles) and all("Public" in p for p in profiles) and not blocks
note(f"{'OK' if ok else 'FEHLER'} · Programme {programs} · AirPlay-Profile {profiles} · Sperr-Regeln übrig "
     f"{len(blocks)}")
sys.exit(0 if ok else 1)
