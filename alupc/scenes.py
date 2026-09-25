"""Layout-Vorlagen und Hilfsfunktionen für eigene Szenen (ohne Qt, testbar)."""

from __future__ import annotations

# Jede Vorlage: (Anzeigename, [(x, y, breite, höhe, Feldname), ...]) in Anteilen 0..1
LAYOUTS: dict[str, tuple[str, list[tuple[float, float, float, float, str]]]] = {
    "vollbild": ("Vollbild", [(0, 0, 1, 1, "Ganzer Bildschirm")]),
    "nebeneinander": (
        "2 nebeneinander",
        [(0, 0, 0.5, 1, "Links"), (0.5, 0, 0.5, 1, "Rechts")],
    ),
    "uebereinander": (
        "2 übereinander",
        [(0, 0, 1, 0.5, "Oben"), (0, 0.5, 1, 0.5, "Unten")],
    ),
    "ecke_unten_rechts": (
        "Groß + klein unten rechts",
        [(0, 0, 1, 1, "Groß (Hintergrund)"), (0.72, 0.70, 0.26, 0.26, "Klein unten rechts")],
    ),
    "ecke_unten_links": (
        "Groß + klein unten links",
        [(0, 0, 1, 1, "Groß (Hintergrund)"), (0.02, 0.70, 0.26, 0.26, "Klein unten links")],
    ),
    "ecke_oben_rechts": (
        "Groß + klein oben rechts",
        [(0, 0, 1, 1, "Groß (Hintergrund)"), (0.72, 0.04, 0.26, 0.26, "Klein oben rechts")],
    ),
    "raster_2x2": (
        "2 × 2 Raster",
        [
            (0, 0, 0.5, 0.5, "Oben links"),
            (0.5, 0, 0.5, 0.5, "Oben rechts"),
            (0, 0.5, 0.5, 0.5, "Unten links"),
            (0.5, 0.5, 0.5, 0.5, "Unten rechts"),
        ],
    ),
    "gross_zwei_klein": (
        "1 groß + 2 klein",
        [
            (0, 0, 2 / 3, 1, "Groß links"),
            (2 / 3, 0, 1 / 3, 0.5, "Klein oben rechts"),
            (2 / 3, 0.5, 1 / 3, 0.5, "Klein unten rechts"),
        ],
    ),
    "bauchbinde": (
        "Vollbild + Textleiste unten",
        [(0, 0, 1, 1, "Hintergrund"), (0, 0.84, 1, 0.16, "Leiste unten")],
    ),
}


def layout_slots(layout: str) -> list[tuple[float, float, float, float, str]]:
    return LAYOUTS.get(layout, LAYOUTS["vollbild"])[1]


def new_scene(name: str, layout: str = "vollbild") -> dict:
    return {
        "name": name,
        "layout": layout,
        "background": "#000000",
        "slots": [None] * len(layout_slots(layout)),
    }


def resize_slots(scene: dict, layout: str) -> dict:
    """Layout wechseln und vorhandene Quellen so weit wie möglich behalten."""
    count = len(layout_slots(layout))
    slots = list(scene.get("slots", []))[:count]
    slots += [None] * (count - len(slots))
    scene = dict(scene)
    scene["layout"] = layout
    scene["slots"] = slots
    return scene


def scene_refs(scene: dict) -> list[str]:
    return [s["scene"] for s in scene.get("slots", []) if s and s.get("type") == "scene"]


def creates_cycle(scenes: list[dict], scene_name: str, candidate: str) -> bool:
    """True, wenn Szene `candidate` (direkt oder indirekt) `scene_name` enthält."""
    by_name = {s["name"]: s for s in scenes}
    stack, seen = [candidate], set()
    while stack:
        current = stack.pop()
        if current == scene_name:
            return True
        if current in seen or current not in by_name:
            continue
        seen.add(current)
        stack.extend(scene_refs(by_name[current]))
    return False


def _short(cfg: dict, key: str) -> str:
    import ntpath
    import posixpath

    value = str(cfg.get(key) or "")
    return cfg.get("title") or posixpath.basename(ntpath.basename(value.rstrip("/\\"))) or value


def describe_source(cfg: dict | None) -> str:
    """Kurze, lesbare Beschreibung einer Quelle."""
    if not cfg:
        return "(leer)"
    t = cfg.get("type")
    if t == "camera":
        return f"Kamera: {cfg.get('name') or cfg.get('device_id')}"
    if t == "screen":
        return f"Bildschirm: {cfg.get('screen_name')}"
    if t == "window":
        return f"Programm: {cfg.get('title')}"
    if t == "airplay":
        return "iPhone/iPad (AirPlay)"
    if t == "website":
        return f"Website: {cfg.get('url')}"
    # Nur den Namen zeigen (Titel aus der Mediathek oder Dateiname) – der ganze Pfad ist zu lang
    if t == "image":
        return f"Bild: {_short(cfg, 'path')}"
    if t == "video":
        return f"Video: {_short(cfg, 'path')}"
    if t == "slideshow":
        return f"Diashow: {_short(cfg, 'folder')}"
    if t == "text":
        text = (cfg.get("text") or "").replace("\n", " ")
        return f"Text: {text[:40]}"
    if t == "clock":
        return "Uhr"
    if t == "countdown":
        return f"Countdown: {cfg.get('minutes')} min"
    if t == "color":
        return f"Farbe: {cfg.get('color')}"
    if t == "scene":
        return f"Szene: {cfg.get('scene')}"
    return str(t)
