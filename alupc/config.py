"""Einstellungen laden und speichern (JSON-Datei im Benutzerprofil)."""

from __future__ import annotations

import copy
import json
import os
import sys
from pathlib import Path

DEFAULT_HOTKEYS = {
    "standbild": "Ctrl+Alt+S",
    "schwarz": "Ctrl+Alt+B",
    "bild_in_bild": "Ctrl+Alt+P",
    "spiegeln": "Ctrl+Alt+M",
    "erweitern": "Ctrl+Alt+E",
    "bildschirmschoner": "Ctrl+Alt+W",
    "naechste_szene": "Ctrl+Alt+PgDown",
    "vorherige_szene": "Ctrl+Alt+PgUp",
    "timer_start_pause": "Ctrl+Alt+T",
    "timer_neustart": "",
    "timer_plus": "",
    "timer_minus": "",
    "laserpointer": "Ctrl+Alt+Z",
}

HOTKEY_LABELS = {
    "standbild": "Standbild an/aus",
    "schwarz": "Sichtschutz (Schwarz) an/aus",
    "bild_in_bild": "Bild-in-Bild an/aus",
    "spiegeln": "Spiegeln",
    "erweitern": "Erweitern",
    "bildschirmschoner": "Bildschirmschoner an/aus",
    "naechste_szene": "Nächste Szene",
    "vorherige_szene": "Vorherige Szene",
    "timer_start_pause": "Timer starten/pausieren",
    "timer_neustart": "Timer neu starten",
    "timer_plus": "Timer +1 Minute",
    "timer_minus": "Timer −1 Minute",
    "laserpointer": "Laserpointer an/aus",
}

DEFAULTS: dict = {
    "version": 1,
    # QScreen-Name des Monitors für andere Leute; leer = automatisch (erster Nicht-Hauptmonitor)
    "output_screen": "",
    # Zuletzt angezeigter Inhalt, wird beim Start wiederhergestellt
    "last_content": None,
    "restore_last_content": True,
    "scenes": [],
    "hotkeys": dict(DEFAULT_HOTKEYS),
    "privacy": {"text": "", "image": ""},
    "pip": {"opacity": 1.0, "width": 480, "fps": 10},
    # Timer (Countdown/Stoppuhr): Voreinstellung für Kachel und Befehle
    "timer": {"minutes": 5, "seconds": 0, "mode": "countdown", "finished_text": "Zeit ist um!",
              "warn_colors": True, "size": 30},
    # Töne bei Aktionen: Ereignis → "builtin:<name>" oder Pfad einer hochgeladenen Datei ("" = still)
    "sounds": {
        "enabled": True,
        "volume": 70,
        "device": "",
        "events": {
            "inhalt": "", "szene": "", "standbild_an": "", "standbild_aus": "", "schwarz_an": "",
            "schwarz_aus": "", "schoner_an": "", "schoner_aus": "", "timer_start": "", "timer_pause": "",
            "timer_minute": "", "timer_ende": "builtin:alarm", "kachel": "",
        },
    },
    # Gespeicherte Websites (Favoriten) für die Kachel „Website“
    "websites": {"favorites": []},
    # Monitor 2: Taskleiste dort ausblenden (Windows), Standbild-Symbol oben rechts
    "output": {"hide_taskbar": True, "freeze_badge": True,
               # Mauszeiger beim Spiegeln ins Bild zeichnen (die Aufnahme enthält ihn nicht)
               "mirror_cursor": True,
               # Maus bleibt auf Monitor 1, außer bei „Erweitern“ (dort ist Monitor 2 ein normaler Bildschirm)
               "confine_cursor": True},
    # Laserpointer auf Monitor 2 (folgt der Maus auf Monitor 1)
    "laser": {"color": "#ff2a2a", "size": 100, "trail": True},
    "start_minimized": False,
    "appearance": {"mode": "system", "accent": "blau", "fade": True},
    # Übergang zwischen Inhalten/Szenen auf Monitor 2 (Art siehe transitions.py); Szenen können
    # einen eigenen Übergang haben
    "transition": {"type": "blende", "ms": 400},
    # Programm-Aufnahme: minimierte Programme im Hintergrund wiederherstellen (nur Windows)
    "program": {"restore_minimized": True},
    "screensaver": {
        "enabled": False,
        "minutes": 10,
        "style": "uhr",
        "when": "desktop",
        "text": "",
        "image": "",
        "folder": "",
        "interval": 8,
        "scene": "",
    },
    # Startseite: tiles = Reihenfolge der sichtbaren Kacheln (None = Standard), custom = eigene Kacheln
    "start_page": {
        "title": "",
        "subtitle": "",
        "show_status": True,
        "show_hint": True,
        "tiles": None,
        "custom": [],
    },
}


def config_dir() -> Path:
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / "AluPC"
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "AluPC"


def _merge(defaults: dict, data: dict) -> dict:
    result = copy.deepcopy(defaults)
    for key, value in data.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = value
    return result


class Config:
    def __init__(self, path: Path | None = None):
        self.path = path or (config_dir() / "config.json")
        self.data = copy.deepcopy(DEFAULTS)
        self.load()

    def load(self) -> None:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                self.data = _merge(DEFAULTS, raw)
        except FileNotFoundError:
            pass
        except (OSError, ValueError):
            # Kaputte Datei nicht überschreiben, sondern sichern
            try:
                self.path.replace(self.path.with_suffix(".defekt.json"))
            except OSError:
                pass

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.path)

    def __getitem__(self, key):
        return self.data[key]

    def __setitem__(self, key, value):
        self.data[key] = value
        self.save()

    # --- Szenen -----------------------------------------------------------
    def scene_names(self) -> list[str]:
        return [s["name"] for s in self.data["scenes"]]

    def get_scene(self, name: str) -> dict | None:
        for scene in self.data["scenes"]:
            if scene["name"] == name:
                return scene
        return None

    def put_scene(self, scene: dict, old_name: str | None = None) -> None:
        scenes = self.data["scenes"]
        key = old_name or scene["name"]
        for i, existing in enumerate(scenes):
            if existing["name"] == key:
                scenes[i] = scene
                break
        else:
            scenes.append(scene)
        if old_name and old_name != scene["name"]:
            _rename_scene_refs(scenes, old_name, scene["name"])
            hotkeys = self.data["hotkeys"]
            if f"szene:{old_name}" in hotkeys:
                hotkeys[f"szene:{scene['name']}"] = hotkeys.pop(f"szene:{old_name}")
            for tile in self.data["start_page"].get("custom", []):
                src = (tile.get("action") or {}).get("source") or {}
                if src.get("type") == "scene" and src.get("scene") == old_name:
                    src["scene"] = scene["name"]
        self.save()

    def delete_scene(self, name: str) -> None:
        self.data["scenes"] = [s for s in self.data["scenes"] if s["name"] != name]
        self.data["hotkeys"].pop(f"szene:{name}", None)
        self.save()


def _rename_scene_refs(scenes: list[dict], old: str, new: str) -> None:
    for scene in scenes:
        for slot in scene.get("slots", []):
            if slot and slot.get("type") == "scene" and slot.get("scene") == old:
                slot["scene"] = new
