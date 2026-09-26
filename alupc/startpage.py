"""Startseite: welche Kacheln in welcher Reihenfolge (ohne Qt, testbar)."""

from __future__ import annotations

import uuid

# id: (Symbol, Titel, Untertitel, Farbe oder None = Akzentfarbe, Bereich)
BUILTIN_TILES: dict[str, tuple[str, str, str, str | None, str]] = {
    "mirror": ("mirror", "Spiegeln", "Gleiches Bild", "#3b82f6", "anzeigen"),
    "extend": ("extend", "Erweitern", "Eigener Desktop", "#6366f1", "anzeigen"),
    "camera": ("camera", "Kamera", "Vollbild", "#ef4444", "anzeigen"),
    "program": ("window", "Programm", "Fenster zeigen", "#a855f7", "anzeigen"),
    "website": ("globe", "Website", "Seite öffnen", "#06b6d4", "anzeigen"),
    "media": ("image", "Bild / Video", "Mediathek", "#10b981", "anzeigen"),
    "scenes": ("scenes", "Meine Szenen", "Eigene Szenen", "#ec4899", "anzeigen"),
    # Handy → Monitor 2: jeder Weg mit eigener Kachel
    "airplay": ("phone", "AirPlay", "iPhone & iPad", "#0ea5e9", "handy"),
    "handy_remote": ("qr", "Handy-Steuerung", "Per QR-Code", "#8b5cf6", "handy"),
    "freeze": ("snowflake", "Standbild", "Bild einfrieren", "#0ea5e9", "schnell"),
    "black": ("eye_off", "Schwarz", "Sichtschutz", "#64748b", "schnell"),
    "pip": ("pip", "Bild-in-Bild", "Mini-Vorschau", "#8b5cf6", "schnell"),
    "screensaver": ("moon", "Bildschirmschoner", "An / aus", "#6366f1", "schnell"),
    "timer": ("timer", "Timer", "Start / Pause", "#f43f5e", "schnell"),
    "draw": ("edit", "Zeigen & Zeichnen", "Laser, Stift, Marker", "#f97316", "schnell"),
}
# Schwarz, Standbild, Bild-in-Bild sind jetzt Schalter oben beim Live-Bild – als Kachel nur noch auf Wunsch
HIDDEN_BY_DEFAULT = {"freeze", "black", "pip", "draw"}
DEFAULT_ORDER = [k for k in BUILTIN_TILES if k not in HIDDEN_BY_DEFAULT]
# Kacheln, die es schon vor dem Merken von „seen“ gab (für ältere Einstellungen)
LEGACY_TILES = ["mirror", "extend", "camera", "program", "website", "media", "scenes", "freeze", "black",
                "pip", "screensaver", "timer"]

SECTIONS = {"anzeigen": "Anzeigen", "handy": "Handy", "schnell": "Werkzeuge"}

# Befehle, die eine eigene Kachel ausführen kann
COMMANDS = {
    "standbild": "Standbild an/aus",
    "schwarz": "Schwarz (Sichtschutz) an/aus",
    "bild-in-bild": "Bild-in-Bild an/aus",
    "bildschirmschoner": "Bildschirmschoner an/aus",
    "spiegeln": "Spiegeln",
    "erweitern": "Erweitern",
    "naechste_szene": "Nächste Szene",
    "ablauf_weiter": "Weiter (nächster Punkt)",
    "ablauf_zurueck": "Zurück (vorheriger Punkt)",
    "vorherige_szene": "Vorherige Szene",
    "timer_zeigen": "Timer auf Monitor 2 zeigen",
    "timer_start_pause": "Timer starten/pausieren",
    "timer_neustart": "Timer neu starten",
    "timer_plus": "Timer +1 Minute",
    "timer_minus": "Timer −1 Minute",
    "zeichnen": "Zeigen & Zeichnen (Fenster öffnen)",
    "kamera_zoom_plus": "Kamera hineinzoomen",
    "kamera_zoom_minus": "Kamera herauszoomen",
    "kamera_zoom_aus": "Kamera-Zoom zurück auf 1×",
    "rgb_farbe": "RGB: gewählte Farbe",
    "rgb_monitor2": "RGB: Farbe folgt Monitor 2",
    "rgb_aus": "RGB aus",
}

# Symbole, die man für eigene Kacheln wählen kann
TILE_ICONS = {
    "star": "Stern", "monitor": "Monitor", "camera": "Kamera", "window": "Programm", "globe": "Website",
    "image": "Bild", "video": "Video", "slides": "Diashow", "scenes": "Szene", "text": "Text", "clock": "Uhr",
    "timer": "Countdown", "palette": "Farbe", "play": "Abspielen", "snowflake": "Standbild",
    "eye_off": "Sichtschutz", "moon": "Bildschirmschoner", "mirror": "Spiegeln", "extend": "Erweitern",
    "pip": "Bild-in-Bild", "home": "Haus", "lock": "Schloss", "power": "Ein/Aus", "sun": "Sonne",
}

TILE_COLORS = ["#3b82f6", "#8b5cf6", "#10b981", "#f59e0b", "#ef4444", "#ec4899", "#06b6d4", "#64748b"]


def custom_key(tile: dict) -> str:
    return f"custom:{tile['id']}"


def new_custom_tile() -> dict:
    return {
        "id": uuid.uuid4().hex[:10],
        "title": "Meine Kachel",
        "subtitle": "",
        "icon": "star",
        "color": TILE_COLORS[0],
        "section": "anzeigen",
        "action": None,
    }


def ordered_keys(start_cfg: dict) -> list[str]:
    """Sichtbare Kacheln in Reihenfolge: Standard-IDs und „custom:<id>“."""
    custom = {custom_key(t) for t in start_cfg.get("custom", [])}
    saved = start_cfg.get("tiles")
    if saved is None:
        return DEFAULT_ORDER + [custom_key(t) for t in start_cfg.get("custom", [])]
    keys = [k for k in saved if k in BUILTIN_TILES or k in custom]
    # Neue Standard-Kacheln (nach einem Update) erscheinen, auch wenn die Reihenfolge schon angepasst wurde
    seen = set(start_cfg.get("seen") or LEGACY_TILES)
    keys += [k for k in DEFAULT_ORDER if k not in seen and k not in keys]
    # Neu angelegte eigene Kacheln, die noch nicht in der Liste stehen, hinten anhängen
    listed = set(saved)
    keys += [custom_key(t) for t in start_cfg.get("custom", []) if custom_key(t) not in listed]
    return keys


def all_keys(start_cfg: dict) -> list[str]:
    """Alle Kacheln (auch ausgeblendete): erst die sichtbaren in Reihenfolge, dann der Rest."""
    visible = ordered_keys(start_cfg)
    rest = [k for k in BUILTIN_TILES if k not in visible]  # auch standardmäßig ausgeblendete
    rest += [custom_key(t) for t in start_cfg.get("custom", []) if custom_key(t) not in visible]
    return visible + rest


def section_of(key: str, start_cfg: dict) -> str:
    if key in BUILTIN_TILES:
        return BUILTIN_TILES[key][4]
    tile = find_custom(start_cfg, key)
    return (tile or {}).get("section", "anzeigen")


def find_custom(start_cfg: dict, key: str) -> dict | None:
    tile_id = key.split(":", 1)[1] if key.startswith("custom:") else key
    return next((t for t in start_cfg.get("custom", []) if t.get("id") == tile_id), None)


def describe_action(action: dict | None) -> str:
    from .scenes import describe_source

    if not action:
        return "(noch keine Aktion)"
    if action.get("kind") == "command":
        return "Befehl: " + COMMANDS.get(action.get("command", ""), action.get("command", ""))
    if action.get("kind") == "source":
        return describe_source(action.get("source"))
    if action.get("kind") == "screensaver":
        return "Eigener Bildschirmschoner"
    if action.get("kind") == "timer":
        t = action.get("timer") or {}
        return f"Timer {int(t.get('minutes', 0))}:{int(t.get('seconds', 0)):02d}"
    return "(unbekannt)"
