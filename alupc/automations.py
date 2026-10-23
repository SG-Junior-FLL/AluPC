"""Wenn → Dann: Regeln für die Tastenbox.

WENN
  * eine Tastenfolge schnell hintereinander gedrückt wurde (z. B. 7-1-2 = unten links, oben links, oben Mitte;
    je höchstens 0,8 s Abstand – ohne Code-Taste), oder
  * ein Code auf dem Nummerfeld eingegeben wurde (die 9 Tasten als Ziffern 1–9; die Eingabe startet mit einem
    langen Druck auf die Code-Taste, endet nach 1,5 s Pause), und/oder
  * der Regler auf einer Zahl 0–999 steht (Regler-Ziel „Zahl 0–999“; zählt, wenn er 1 s ruhig steht;
    Toleranz ± einige Schritte, weil das Zählwerk eines 10-Gang-Potis nie ganz genau zum Messwert passt)
DANN
  * Programm starten · Webseite am PC öffnen · Webseite auf Bildschirm 2 · Datei/Video auf Bildschirm 2 ·
    eigener Befehl (Kommandozeile) · Klang am PC · Melodie oder MIDI-Datei auf dem Buzzer der Box ·
    AluPC-Befehl (alles, was auch eine Taste kann)

Eine Regel: {"name", "an", "wenn": {"folge": "712" | "", "code": "123" | "", "wert": 0–999 | None, "toleranz": 3},
             "dann": {"art": ACTIONS-Schlüssel, "ziel": Text}}
Regeln stellt nur der Nutzer selbst am PC ein (Konfiguration); ein eigener Befehl läuft wie in seiner Kommandozeile.
"""

from __future__ import annotations

import os
import shlex
import subprocess
import sys

IS_WINDOWS = sys.platform.startswith("win")
ACTIONS = {
    "programm": "Programm starten",
    "webseite": "Webseite am PC öffnen",
    "webseite_m2": "Webseite auf Bildschirm 2",
    "datei": "Video / Bild / Datei auf Bildschirm 2",
    "befehl": "Eigener Befehl (Kommandozeile)",
    "klang": "Klang / Sound am PC abspielen",
    "buzzer": "Melodie auf dem Buzzer der Box",
    "buzzer_midi": "MIDI-Datei auf dem Buzzer der Box",
    "alupc": "AluPC-Befehl",
}
ACTION_HINTS = {
    "programm": "Pfad zum Programm, z. B. C:\\Program Files\\VideoLAN\\VLC\\vlc.exe oder firefox",
    "webseite": "Adresse, z. B. https://example.org",
    "webseite_m2": "Adresse, z. B. https://example.org",
    "datei": "Pfad zur Datei, z. B. D:\\Videos\\intro.mp4",
    "befehl": "Befehl wie in der Kommandozeile, z. B. shutdown /s /t 600",
    "klang": "Tondatei (WAV, MP3, OGG …) – „Auswählen“",
    "buzzer": "",
    "buzzer_midi": "MIDI-Datei (.mid) – „Auswählen“",
    "alupc": "",
}
# Wo die Tasten auf der Box sitzen (für Tastenfolgen: „unten links → oben links → oben Mitte“)
KEY_POS = {1: "oben links", 2: "oben Mitte", 3: "oben rechts", 4: "Mitte links", 5: "Mitte", 6: "Mitte rechts",
           7: "unten links", 8: "unten Mitte", 9: "unten rechts"}
SEQ_GAP_MS = 800  # Tastenfolge: höchstens so viel Zeit zwischen zwei Tasten
CODE_PAUSE_MS = 1500  # so lange Ruhe beendet die Code-Eingabe
CODE_TIMEOUT_MS = 8000
VALUE_SETTLE_MS = 1000  # so lange muss der Regler stehen, bis ein Wert zählt


def clean_rule(rule: dict) -> dict:
    """Regel in die gespeicherte Form bringen (fehlende Felder ergänzen, Werte begrenzen)."""
    wenn, dann = dict(rule.get("wenn") or {}), dict(rule.get("dann") or {})
    code = "".join(ch for ch in str(wenn.get("code") or "") if ch in "123456789")[:12]
    folge = "".join(ch for ch in str(wenn.get("folge") or "") if ch in "123456789")[:12]
    if len(folge) < 2:  # eine einzelne Taste ist keine Folge (dafür: Taste direkt belegen)
        folge = ""
    wert = wenn.get("wert")
    wert = None if wert in (None, "") else max(0, min(999, int(wert)))
    art = dann.get("art") if dann.get("art") in ACTIONS else "alupc"
    return {"name": str(rule.get("name") or "Regel").strip()[:60], "an": bool(rule.get("an", True)),
            "wenn": {"folge": folge, "code": "" if folge else code, "wert": wert,
                     "toleranz": max(0, min(50, int(wenn.get("toleranz", 3) or 0)))},
            "dann": {"art": art, "ziel": str(dann.get("ziel") or "").strip()}}


def is_valid(rule: dict) -> bool:
    w = rule["wenn"]
    return bool(w["folge"] or w["code"] or w["wert"] is not None) and bool(rule["dann"]["ziel"])


def describe_sequence(folge: str) -> str:
    """„712“ → „7-1-2 (unten links → oben links → oben Mitte)“"""
    return "-".join(folge) + " (" + " → ".join(KEY_POS[int(ch)] for ch in folge) + ")"


def describe(rule: dict) -> str:
    """„Code 1-2-3 und Regler 250 ± 3 → Programm starten: vlc“"""
    w, d = rule["wenn"], rule["dann"]
    parts = []
    if w["folge"]:
        parts.append("Tastenfolge " + describe_sequence(w["folge"]))
    if w["code"]:
        parts.append("Code " + "-".join(w["code"]))
    if w["wert"] is not None:
        parts.append(f"Regler {w['wert']:03d}" + (f" ± {w['toleranz']}" if w["toleranz"] else ""))
    return f"{' und '.join(parts) or '–'} → {ACTIONS[d['art']]}: {target_label(d['art'], d['ziel'])}"


def target_label(art: str, ziel: str) -> str:
    if art == "buzzer":
        from .buzzer import SONGS

        return SONGS.get(ziel, (ziel,))[0]
    if art in ("klang", "buzzer_midi"):
        from pathlib import Path

        return Path(ziel.split(":", 1)[1] if ziel.startswith("builtin:") else ziel).name
    return ziel


def value_matches(rule: dict, value: int | None) -> bool:
    w = rule["wenn"]
    return w["wert"] is None or (value is not None and abs(int(value) - w["wert"]) <= w["toleranz"])


def rules_for_code(rules: list[dict], code: str, value: int | None) -> list[dict]:
    """Regeln, die zu einem eingegebenen Code passen (Code gleich, Regler – falls verlangt – im Bereich)."""
    return [r for r in rules if r["an"] and is_valid(r) and r["wenn"]["code"] == code and value_matches(r, value)]


def sequence_rules(rules: list[dict]) -> list[dict]:
    return [r for r in rules if r["an"] and is_valid(r) and r["wenn"]["folge"]]


def rules_for_sequence(rules: list[dict], keys: str, value: int | None) -> list[dict]:
    """Regeln, deren Tastenfolge genau „keys“ ist (Regler – falls verlangt – im Bereich)."""
    return [r for r in sequence_rules(rules) if r["wenn"]["folge"] == keys and value_matches(r, value)]


def rules_for_value(rules: list[dict], value: int) -> list[dict]:
    """Regeln ohne Code, deren Reglerzahl gerade erreicht ist."""
    return [r for r in rules if r["an"] and is_valid(r) and not r["wenn"]["code"] and not r["wenn"]["folge"]
            and r["wenn"]["wert"] is not None and value_matches(r, value)]


def command_line(ziel: str) -> list[str]:
    """Eigener Befehl → Aufruf der System-Kommandozeile (cmd /c bzw. sh -c) mit dem Text als einem Argument."""
    return ["cmd", "/c", ziel] if IS_WINDOWS else ["sh", "-c", ziel]


def run_external(art: str, ziel: str) -> tuple[bool, str]:
    """Programm, eigenen Befehl oder Webseite am PC starten – im Hintergrund, AluPC wartet nicht darauf."""
    detach = {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)} if IS_WINDOWS else {"start_new_session": True}
    quiet = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    try:
        if art == "webseite":
            from PySide6.QtCore import QUrl
            from PySide6.QtGui import QDesktopServices

            return bool(QDesktopServices.openUrl(QUrl.fromUserInput(ziel))), f"Webseite: {ziel}"
        if art == "programm":
            if IS_WINDOWS and os.path.exists(ziel):
                os.startfile(ziel)  # noqa: S606 - vom Nutzer selbst eingestellt
            else:
                subprocess.Popen(shlex.split(ziel, posix=not IS_WINDOWS), **quiet,
                                 **({} if IS_WINDOWS else {"start_new_session": True}))
            return True, f"Gestartet: {ziel}"
        if art == "befehl":
            subprocess.Popen(command_line(ziel), **quiet, **detach)
            return True, f"Befehl: {ziel}"
    except (OSError, ValueError) as exc:
        return False, f"Geht nicht: {exc}"
    return False, "Unbekannte Art"
