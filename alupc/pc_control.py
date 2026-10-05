"""Den ganzen PC steuern – per Sprache, Befehlssuche oder Handy: Lautstärke, Programme und Webseiten öffnen, im
Internet suchen, Fenster schließen/minimieren, Desktop zeigen, Bildschirmfoto, Herunterfahren (nur mit Rückfrage).

Befehle heißen „pc_…“ (siehe `pc_intent`). `run(Befehl)` führt aus und gibt eine kurze Antwort zurück; ging es nicht,
steht der Grund darin (z. B. „unter Wayland nicht möglich“) – nie eine Ausnahme.

Linux: PipeWire/PulseAudio (wpctl/pactl), KDE-Kurzbefehle über D-Bus (kglobalaccel, geht auch unter Wayland),
sonst X11-Tasten (XTest). Programme: .desktop-Dateien. Windows: Medientasten/Tastenkürzel (user32), Programme:
Startmenü-Verknüpfungen.
"""

from __future__ import annotations

import difflib
import os
import shutil
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

from .voice import fold

# Webseiten, die man beim Namen nennt
SITES = {
    "youtube": "https://www.youtube.com", "google": "https://www.google.com", "netflix": "https://www.netflix.com",
    "wikipedia": "https://de.wikipedia.org", "amazon": "https://www.amazon.de", "twitch": "https://www.twitch.tv",
    "github": "https://github.com", "gmail": "https://mail.google.com", "maps": "https://maps.google.com",
    "google maps": "https://maps.google.com", "instagram": "https://www.instagram.com",
    "tiktok": "https://www.tiktok.com", "reddit": "https://www.reddit.com", "ebay": "https://www.ebay.de",
    "wetter": "https://www.wetter.com", "chatgpt": "https://chatgpt.com", "claude": "https://claude.ai",
    "disney": "https://www.disneyplus.com", "disney plus": "https://www.disneyplus.com",
    "prime video": "https://www.primevideo.com", "whatsapp": "https://web.whatsapp.com",
}
# gesprochener Name → Programm (Linux-Befehle in Reihenfolge, Windows-Befehl/URI)
APPS = {
    "firefox": (["firefox"], "firefox"),
    "chrome": (["google-chrome", "chromium", "chromium-browser"], "chrome"),
    "browser": (["xdg-open https://"], "https://"),
    "spotify": (["spotify"], "spotify:"),
    "discord": (["discord"], "discord:"),
    "steam": (["steam"], "steam:"),
    "taschenrechner": (["kcalc", "gnome-calculator", "galculator"], "calc"),
    "rechner app": (["kcalc", "gnome-calculator"], "calc"),
    "explorer": (["dolphin", "nautilus", "thunar", "nemo"], "explorer"),
    "dateien": (["dolphin", "nautilus", "thunar", "nemo"], "explorer"),
    "dateimanager": (["dolphin", "nautilus", "thunar", "nemo"], "explorer"),
    "terminal": (["konsole", "gnome-terminal", "xterm"], "wt"),
    "konsole": (["konsole", "gnome-terminal", "xterm"], "wt"),
    "einstellungen": (["systemsettings", "gnome-control-center"], "ms-settings:"),
    "systemeinstellungen": (["systemsettings", "gnome-control-center"], "ms-settings:"),
    "editor": (["kate", "kwrite", "gedit", "gnome-text-editor"], "notepad"),
    "texteditor": (["kate", "kwrite", "gedit", "gnome-text-editor"], "notepad"),
    "vlc": (["vlc"], "vlc"),
    "obs": (["obs"], "obs64"),
    "code": (["code"], "code"),
    "visual studio code": (["code"], "code"),
    "word": (["libreoffice --writer"], "winword"),
    "excel": (["libreoffice --calc"], "excel"),
    "powerpoint": (["libreoffice --impress"], "powerpoint"),
    "libreoffice": (["libreoffice"], "soffice"),
    "thunderbird": (["thunderbird"], "thunderbird"),
    "minecraft": (["minecraft-launcher"], "minecraft:"),
}
POWER = {"pc_herunterfahren": "herunterfahren", "pc_neustart": "neu starten", "pc_schlafen": "schlafen legen",
         "pc_abmelden": "abmelden"}
OPEN_VERBS = ("oeffne", "oeffnen", "starte", "starten", "start", "open", "geh", "gehe", "lade", "aufmachen",
              "oeffnest", "starten")
_FILL = {"bitte", "mal", "doch", "jetzt", "den", "die", "das", "dem", "der", "mir", "mich", "auf", "zu", "app",
         "programm", "seite", "webseite", "website", "im", "in", "kurz", "kannst", "du", "ein", "eine", "einen", "mach"}


# =========================================================================== Verstehen
def pc_intent(words: list[str], alupc_words: set[str] | None = None) -> tuple[str, str] | None:
    """Gefaltete Wörter → (pc_…-Befehl, Anzeige) oder None. `alupc_words`: Themen von AluPC selbst („Kamera“,
    „Timer“ …) – „öffne die Kamera“ bleibt dann AluPCs Kamera."""
    said = " ".join(words)
    ws = set(words)
    pc = bool(ws & {"computer", "pc", "rechner", "laptop"})
    # --- Ein/Aus
    if pc and ws & {"herunterfahren", "runterfahren", "ausschalten", "abschalten", "ausmachen", "aus", "shutdown"} \
            and not ws & {"sperren", "sperre", "neu"}:
        return "pc_herunterfahren", "PC herunterfahren"
    if pc and ws & {"herunter", "runter"} and ws & {"fahr", "fahre", "fahren"}:  # „fahr den PC herunter“
        return "pc_herunterfahren", "PC herunterfahren"
    if (pc and ws & {"neustarten", "neustart", "neu"}) or "neu starten" in said and pc:
        return "pc_neustart", "PC neu starten"
    if ws & {"ruhezustand", "standby", "energiesparmodus"} or (pc and ws & {"schlafen", "einschlafen"}) or \
            "energie sparen" in said:
        return "pc_schlafen", "PC schlafen legen"
    if ws & {"abmelden", "ausloggen"} and (pc or len(words) <= 2):
        return "pc_abmelden", "Abmelden"
    # --- Lautstärke
    if ws & {"stumm", "stummschalten", "mute", "lautlos"} or said in ("ton aus", "sound aus"):
        return ("pc_stumm_aus", "Ton an") if ws & {"aufheben", "wieder"} or "stumm aus" in said else \
            ("pc_stumm_an", "Stumm")
    if said in ("ton an", "sound an", "ton wieder an"):
        return "pc_stumm_aus", "Ton an"
    if ws & {"lautstaerke", "volume", "laut", "lauter", "leiser"}:
        from .intents import to_number

        for i, w in enumerate(words):
            n, _used = to_number(words, i)
            if n is not None and 0 <= n <= 100:
                return f"pc_lautstaerke:{n}", f"Lautstärke {n} %"
        if ws & {"lauter", "erhoehen", "hoeher", "rauf", "hoch"}:
            return "pc_lauter", "Lauter"
        if ws & {"leiser", "runter", "verringern", "niedriger"}:
            return "pc_leiser", "Leiser"
        if ws & {"lautstaerke", "laut"} and ws & {"wie", "welche", "wieviel"}:
            return "pc_lautstaerke_frage", "Lautstärke?"
    # --- Fenster
    if ws & {"fenster", "programm", "app"} or said in ("schliessen", "minimieren", "maximieren"):
        if ws & {"schliessen", "schliesse", "zumachen", "zu", "beenden", "beende", "weg"}:
            return "pc_fenster_zu", "Fenster schließen"
        if ws & {"minimieren", "minimiere", "verkleinern", "runter"}:
            return "pc_minimieren", "Fenster minimieren"
        if ws & {"maximieren", "maximiere", "vergroessern", "gross", "vollbild"}:
            return "pc_maximieren", "Fenster maximieren"
        if ws & {"wechseln", "wechsle", "naechstes", "naechste", "anderes"}:
            return "pc_fenster_wechseln", "Fenster wechseln"
    if "desktop" in ws or "alle fenster weg" in said or "alles minimieren" in said:
        return "pc_desktop", "Desktop zeigen"
    # --- Bildschirmfoto
    if ws & {"screenshot", "bildschirmfoto", "screenshots"} or ("foto" in ws and ws & {"bildschirm", "monitor"}):
        return "pc_screenshot", "Bildschirmfoto"
    # --- Suchen
    for key in ("suche nach ", "such nach ", "google nach ", "suche im internet nach ", "such im internet nach ",
                "google ", "suche ", "such "):
        if said.startswith(key) and len(said) > len(key):
            q = said[len(key):].strip()
            return f"pc_suche:{q}", f"Suche: {q}"
    if "youtube" in ws and ws & {"suche", "such", "spiel", "spiele", "zeig"} and len(words) > 2:
        q = " ".join(w for w in words if w not in {"youtube", "auf", "bei", "in", "suche", "such", "spiel", "spiele",
                                                   "zeig", "mir", "nach", "bitte", "mal"})
        if q:
            return f"pc_youtube:{q}", f"YouTube: {q}"
    # --- Öffnen (Webseite oder Programm)
    if ws & set(OPEN_VERBS):
        target = [w for w in words if w not in OPEN_VERBS and w not in _FILL]
        name = " ".join(target)
        if not name:
            return None
        tlds = ("de", "com", "org", "net", "io", "at", "ch", "eu", "tv")
        if len(target) >= 2 and target[-1] in tlds:  # „heise.de“ (gefaltet „heise de“) oder „heise punkt de“
            domain = ".".join(w for w in target if w != "punkt")
            return f"pc_web:{domain}", f"{domain} öffnen"
        if name in SITES:
            return f"pc_web:{name}", f"{name.title()} öffnen"
        if alupc_words and set(target) & alupc_words:
            return None  # „öffne die Kamera“, „starte den Timer“ – das macht AluPC selbst
        return f"pc_app:{name}", f"{name.title()} öffnen"
    return None


# =========================================================================== Ausführen
def _run(cmd: list[str], timeout: float = 8) -> tuple[int, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return r.returncode, (r.stdout + r.stderr).strip()
    except (OSError, subprocess.SubprocessError) as exc:
        return 1, str(exc)


def _spawn(cmd: list[str]) -> bool:
    try:
        subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=not sys.platform.startswith("win"),
                         creationflags=getattr(subprocess, "DETACHED_PROCESS", 0))
        return True
    except OSError:
        return False


def _open_url(url: str) -> bool:
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QDesktopServices

    return QDesktopServices.openUrl(QUrl(url))


# ---- Lautstärke (Systemlautstärke, nicht nur AluPC)
def get_volume() -> int | None:
    if sys.platform.startswith("linux"):
        if shutil.which("wpctl"):
            code, out = _run(["wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"])
            if code == 0 and out.startswith("Volume:"):
                try:
                    return round(float(out.split()[1]) * 100)
                except (IndexError, ValueError):
                    return None
        if shutil.which("pactl"):
            code, out = _run(["pactl", "get-sink-volume", "@DEFAULT_SINK@"])
            for part in out.split("/"):
                if part.strip().endswith("%"):
                    try:
                        return int(part.strip().rstrip("%"))
                    except ValueError:
                        return None
    return None


def set_volume(percent: int | None = None, step: int = 0) -> tuple[bool, str]:
    percent = None if percent is None else max(0, min(100, int(percent)))
    if sys.platform.startswith("linux"):
        if shutil.which("wpctl"):
            arg = f"{percent / 100:.2f}" if percent is not None else f"{abs(step) / 100:.2f}{'+' if step > 0 else '-'}"
            code, out = _run(["wpctl", "set-volume", "-l", "1.0", "@DEFAULT_AUDIO_SINK@", arg])
            if code == 0:
                _run(["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "0"])
                return True, ""
        if shutil.which("pactl"):
            arg = f"{percent}%" if percent is not None else f"{'+' if step > 0 else '-'}{abs(step)}%"
            code, out = _run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", arg])
            if code == 0:
                _run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "0"])
                return True, ""
            return False, out
        return False, "kein wpctl/pactl gefunden"
    if sys.platform.startswith("win"):
        # Medientasten: jeder Druck = 2 %. Für „auf 30 %“ erst ganz runter, dann hoch
        if percent is not None:
            _vk(0xAE, 50)
            _vk(0xAF, round(percent / 2))
        else:
            _vk(0xAF if step > 0 else 0xAE, max(1, abs(step) // 2))
        return True, ""
    return False, "nicht unterstützt"


def set_mute(on: bool) -> tuple[bool, str]:
    if sys.platform.startswith("linux"):
        if shutil.which("wpctl"):
            return _run(["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "1" if on else "0"])[0] == 0, ""
        if shutil.which("pactl"):
            return _run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "1" if on else "0"])[0] == 0, ""
        return False, "kein wpctl/pactl gefunden"
    if sys.platform.startswith("win"):
        _vk(0xAD)  # Windows kennt nur „umschalten“
        return True, ""
    return False, "nicht unterstützt"


def _vk(code: int, times: int = 1, modifiers: tuple[int, ...] = ()) -> None:
    import ctypes

    user32 = ctypes.windll.user32
    for _ in range(times):
        for m in modifiers:
            user32.keybd_event(m, 0, 0, 0)
        user32.keybd_event(code, 0, 0, 0)
        user32.keybd_event(code, 0, 2, 0)
        for m in reversed(modifiers):
            user32.keybd_event(m, 0, 2, 0)


# ---- Fenster (KDE-Kurzbefehle über D-Bus, sonst Tasten)
KDE_ACTIONS = {"pc_fenster_zu": "Window Close", "pc_minimieren": "Window Minimize",
               "pc_maximieren": "Window Maximize", "pc_desktop": "Show Desktop",
               "pc_fenster_wechseln": "Walk Through Windows"}
WIN_KEYS = {"pc_fenster_zu": (0x73, (0x12,)),  # Alt+F4
            "pc_minimieren": (0x28, (0x5B,)),  # Win+↓
            "pc_maximieren": (0x26, (0x5B,)),  # Win+↑
            "pc_desktop": (0x44, (0x5B,)),  # Win+D
            "pc_fenster_wechseln": (0x09, (0x12,))}  # Alt+Tab
X11_KEYS = {"pc_fenster_zu": ("F4", ("Alt_L",)), "pc_fenster_wechseln": ("Tab", ("Alt_L",)),
            "pc_desktop": ("d", ("Super_L",))}


def _kde_shortcut(name: str) -> bool:
    for tool in ("qdbus6", "qdbus", "qdbus-qt5"):
        if shutil.which(tool):
            code, _out = _run([tool, "org.kde.kglobalaccel", "/component/kwin", "invokeShortcut", name], 5)
            return code == 0
    return False


def window_action(cmd: str) -> tuple[bool, str]:
    if sys.platform.startswith("win"):
        vk, mods = WIN_KEYS[cmd]
        _vk(vk, 1, mods)
        return True, ""
    if os.environ.get("XDG_CURRENT_DESKTOP", "").upper().find("KDE") >= 0 and _kde_shortcut(KDE_ACTIONS[cmd]):
        return True, ""
    if cmd in X11_KEYS:
        from .platform import keys

        if keys.combo(*X11_KEYS[cmd]):
            return True, ""
    return False, "geht hier nur unter KDE oder X11"


# ---- Programme suchen und starten
def _desktop_entries() -> dict[str, str]:
    """Linux: Anzeigename (gefaltet) → .desktop-Datei."""
    found: dict[str, str] = {}
    dirs = [Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "applications"]
    dirs += [Path(d) / "applications" for d in os.environ.get("XDG_DATA_DIRS", "/usr/local/share:/usr/share").split(":")]
    dirs += [Path("/var/lib/flatpak/exports/share/applications"),
             Path.home() / ".local/share/flatpak/exports/share/applications"]
    for d in dirs:
        try:
            files = list(d.glob("*.desktop"))
        except OSError:
            continue
        for f in files:
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if "NoDisplay=true" in text:
                continue
            for line in text.splitlines():
                if line.startswith(("Name=", "Name[de]=")):
                    found.setdefault(fold(line.split("=", 1)[1]), str(f))
            found.setdefault(fold(f.stem.split(".")[-1]), str(f))
    return found


def _start_menu() -> dict[str, str]:
    """Windows: Name der Startmenü-Verknüpfung (gefaltet) → Pfad."""
    found: dict[str, str] = {}
    roots = [Path(os.environ.get("ProgramData", r"C:\ProgramData")) / r"Microsoft\Windows\Start Menu\Programs",
             Path(os.environ.get("APPDATA", "")) / r"Microsoft\Windows\Start Menu\Programs"]
    for root in roots:
        try:
            for f in root.rglob("*.lnk"):
                found.setdefault(fold(f.stem), str(f))
        except OSError:
            continue
    return found


def find_app(name: str, entries: dict[str, str]) -> str | None:
    key = fold(name)
    if key in entries:
        return entries[key]
    starts = [k for k in entries if k.startswith(key) or key in k.split()]
    if starts:
        return entries[min(starts, key=len)]
    close = difflib.get_close_matches(key, list(entries), n=1, cutoff=0.75)
    return entries[close[0]] if close else None


def open_app(name: str) -> tuple[bool, str]:
    key = fold(name)
    linux_cmds, win_cmd = APPS.get(key, ([], ""))
    if sys.platform.startswith("win"):
        lnk = find_app(name, _start_menu())
        try:
            os.startfile(lnk or win_cmd or name)  # noqa: S606 – Startmenü-Verknüpfung oder bekannter Befehl
            return True, ""
        except OSError:
            return False, f"„{name}“ nicht gefunden"
    entry = find_app(name, _desktop_entries())
    if entry:
        for tool in (["gtk-launch", Path(entry).stem], ["kioclient", "exec", entry], ["gio", "launch", entry]):
            if shutil.which(tool[0]) and _spawn(tool):
                return True, ""
    for cmd in linux_cmds:
        parts = cmd.split()
        if shutil.which(parts[0]) and _spawn(parts):
            return True, ""
    return False, f"„{name}“ nicht gefunden"


# ---- Bildschirmfoto
def screenshot(folder: Path | None = None) -> tuple[bool, str]:
    from PySide6.QtGui import QGuiApplication

    folder = folder or Path.home() / ("Bilder" if (Path.home() / "Bilder").is_dir() else "Pictures") / "AluPC"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / time.strftime("Bildschirmfoto %Y-%m-%d %H-%M-%S.png")
    wayland = bool(os.environ.get("WAYLAND_DISPLAY"))
    if wayland and shutil.which("spectacle"):  # unter Wayland darf nur der Desktop selbst fotografieren
        ok = _run(["spectacle", "-b", "-n", "-f", "-o", str(path)], 15)[0] == 0
        return ok, str(path) if ok else "Spectacle konnte kein Foto machen"
    screen = QGuiApplication.primaryScreen()
    if screen is None:
        return False, "kein Bildschirm"
    pix = screen.grabWindow(0)
    if pix.isNull() or not pix.save(str(path)):
        return False, "Foto ging nicht"
    return True, str(path)


# ---- Ein/Aus
def power(cmd: str) -> tuple[bool, str]:
    if sys.platform.startswith("win"):
        table = {"pc_herunterfahren": ["shutdown", "/s", "/t", "5"], "pc_neustart": ["shutdown", "/r", "/t", "5"],
                 "pc_abmelden": ["shutdown", "/l"],
                 "pc_schlafen": ["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"]}
    else:
        table = {"pc_herunterfahren": ["systemctl", "poweroff"], "pc_neustart": ["systemctl", "reboot"],
                 "pc_schlafen": ["systemctl", "suspend"],
                 "pc_abmelden": ["loginctl", "terminate-session", os.environ.get("XDG_SESSION_ID", "")]}
    return (_spawn(table[cmd]), "")


# ---- Verteiler
def run(cmd: str) -> str:
    """Befehl ausführen → kurze Antwort (für Sprache/Handy)."""
    try:
        if cmd.startswith("pc_lautstaerke:"):
            n = int(cmd.split(":", 1)[1])
            ok, why = set_volume(n)
            return f"Lautstärke {n} Prozent." if ok else f"Lautstärke geht nicht: {why}"
        if cmd == "pc_lautstaerke_frage":
            v = get_volume()
            return f"Die Lautstärke ist auf {v} Prozent." if v is not None else "Das kann ich hier nicht ablesen."
        if cmd in ("pc_lauter", "pc_leiser"):
            ok, why = set_volume(step=10 if cmd == "pc_lauter" else -10)
            v = get_volume()
            word = "Lauter" if cmd == "pc_lauter" else "Leiser"
            return (f"{word} – jetzt {v} Prozent." if v is not None else f"{word}.") if ok else \
                f"Lautstärke geht nicht: {why}"
        if cmd in ("pc_stumm_an", "pc_stumm_aus"):
            ok, why = set_mute(cmd == "pc_stumm_an")
            return ("Stumm." if cmd == "pc_stumm_an" else "Ton ist wieder an.") if ok else f"Geht nicht: {why}"
        if cmd in KDE_ACTIONS:
            ok, why = window_action(cmd)
            return "Okay." if ok else f"Das geht nicht: {why}."
        if cmd == "pc_screenshot":
            ok, where = screenshot()
            return f"Bildschirmfoto gespeichert: {Path(where).name}" if ok else f"Bildschirmfoto ging nicht: {where}"
        if cmd.startswith("pc_web:"):
            name = cmd.split(":", 1)[1]
            url = SITES.get(name) or ("https://" + name)
            return f"Ich öffne {name}." if _open_url(url) else f"{name} ließ sich nicht öffnen."
        if cmd.startswith("pc_suche:"):
            q = cmd.split(":", 1)[1]
            ok = _open_url("https://www.google.com/search?q=" + urllib.parse.quote_plus(q))
            return f"Ich suche nach {q}." if ok else "Der Browser ließ sich nicht öffnen."
        if cmd.startswith("pc_youtube:"):
            q = cmd.split(":", 1)[1]
            ok = _open_url("https://www.youtube.com/results?search_query=" + urllib.parse.quote_plus(q))
            return f"YouTube: {q}." if ok else "Der Browser ließ sich nicht öffnen."
        if cmd.startswith("pc_app:"):
            name = cmd.split(":", 1)[1]
            ok, why = open_app(name)
            return f"Ich öffne {name}." if ok else f"Das ging nicht: {why}."
        if cmd in POWER:
            ok, _why = power(cmd)
            return f"Okay, ich {'fahre den PC herunter' if cmd == 'pc_herunterfahren' else POWER[cmd]}." if ok \
                else "Das ging nicht."
    except Exception as exc:  # noqa: BLE001
        return f"Das ging nicht: {exc}"
    return "Den PC-Befehl kenne ich nicht."
