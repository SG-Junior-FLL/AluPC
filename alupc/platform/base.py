"""Gemeinsame Datentypen und Schnittstellen der Systemschicht."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field

ROTATIONS = {"normal": "Normal", "left": "90° links", "right": "90° rechts", "inverted": "180°"}


@dataclass
class DisplayMode:
    id: str
    width: int
    height: int
    refresh: float

    @property
    def label(self) -> str:
        return f"{self.width} × {self.height}"


@dataclass
class Output:
    name: str
    description: str = ""
    enabled: bool = True
    primary: bool = False
    x: int = 0
    y: int = 0
    scale: float = 1.0
    rotation: str = "normal"
    mode_id: str = ""
    modes: list[DisplayMode] = field(default_factory=list)

    def mode(self) -> DisplayMode | None:
        for m in self.modes:
            if m.id == self.mode_id:
                return m
        return None

    def size(self) -> tuple[int, int]:
        m = self.mode()
        if not m:
            return (0, 0)
        w, h = m.width, m.height
        if self.rotation in ("left", "right"):
            w, h = h, w
        return (w, h)

    def mode_size(self) -> tuple[int, int]:
        m = self.mode()
        return (m.width, m.height) if m else (0, 0)

    def resolutions(self) -> list[tuple[int, int]]:
        seen: list[tuple[int, int]] = []
        for m in sorted(self.modes, key=lambda m: (m.width * m.height, m.width), reverse=True):
            if (m.width, m.height) not in seen:
                seen.append((m.width, m.height))
        return seen

    def refresh_rates(self, width: int, height: int) -> list[DisplayMode]:
        rates = [m for m in self.modes if m.width == width and m.height == height]
        return sorted(rates, key=lambda m: m.refresh, reverse=True)

    def find_mode(self, width: int, height: int, refresh: float | None = None) -> DisplayMode | None:
        candidates = self.refresh_rates(width, height)
        if not candidates:
            return None
        if refresh is None:
            return candidates[0]
        return min(candidates, key=lambda m: abs(m.refresh - refresh))


class DisplayBackend:
    """Monitor-Einstellungen: Auflösung, Hz, Position, Spiegeln/Erweitern."""

    name = "nicht verfügbar"
    supports_scale = False
    # True: Positionen sind logische Koordinaten (Größe / Skalierung), z. B. KDE unter Wayland
    logical_positions = False

    def available(self) -> bool:
        return False

    def list_outputs(self) -> list[Output]:
        return []

    def apply(self, outputs: list[Output]) -> None:
        raise NotImplementedError

    def mirror(self, main: str, second: str) -> None:
        outputs = self.list_outputs()
        by_name = {o.name: o for o in outputs}
        if main not in by_name or second not in by_name:
            raise RuntimeError("Monitor nicht gefunden")
        m, s = by_name[main], by_name[second]
        s.rotation = m.rotation
        s.scale = m.scale
        mode = s.find_mode(*m.mode_size()) if m.mode() else None
        if mode:
            s.mode_id = mode.id
        s.enabled = True
        s.x, s.y = m.x, m.y
        self.apply(outputs)

    def extend(self, main: str, second: str, side: str = "right") -> None:
        outputs = self.list_outputs()
        by_name = {o.name: o for o in outputs}
        if main not in by_name or second not in by_name:
            raise RuntimeError("Monitor nicht gefunden")
        by_name[second].enabled = True
        place(outputs, main, second, side, self.logical_positions)
        self.apply(outputs)


def logical_size(o: Output, logical: bool) -> tuple[int, int]:
    w, h = o.size()
    if logical and o.scale:
        return (round(w / o.scale), round(h / o.scale))
    return (w, h)


def place(outputs: list[Output], main: str, second: str, side: str, logical: bool) -> None:
    """Zweiten Monitor neben den Hauptmonitor setzen; danach Koordinaten normalisieren."""
    by_name = {o.name: o for o in outputs}
    m, s = by_name[main], by_name[second]
    mw, mh = logical_size(m, logical)
    sw, sh = logical_size(s, logical)
    if side == "left":
        s.x, s.y = m.x - sw, m.y
    elif side == "above":
        s.x, s.y = m.x, m.y - sh
    elif side == "below":
        s.x, s.y = m.x, m.y + mh
    else:
        s.x, s.y = m.x + mw, m.y
    enabled = [o for o in outputs if o.enabled]
    min_x = min(o.x for o in enabled)
    min_y = min(o.y for o in enabled)
    for o in enabled:
        o.x -= min_x
        o.y -= min_y


def side_of(outputs: list[Output], main: str, second: str) -> str:
    by_name = {o.name: o for o in outputs}
    m, s = by_name[main], by_name[second]
    if s.x == m.x and s.y == m.y:
        return "mirror"
    dx, dy = s.x - m.x, s.y - m.y
    if abs(dx) >= abs(dy):
        return "right" if dx > 0 else "left"
    return "below" if dy > 0 else "above"


def clone_outputs(outputs: list[Output]) -> list[Output]:
    return copy.deepcopy(outputs)


@dataclass
class WindowInfo:
    id: str
    title: str
    app: str = ""
    minimized: bool = False


class WindowBackend:
    """Fenster anderer Programme auflisten und auf einen Monitor verschieben."""

    can_list = False
    can_move_active = False

    def list_windows(self) -> list[WindowInfo]:
        return []

    # rect = (x, y, breite, höhe) des Zielmonitors in Qt-Koordinaten
    def move_window(self, window_id: str, output_name: str, rect: tuple[int, int, int, int],
                    fullscreen: bool = False) -> None:
        raise NotImplementedError

    def move_active_window(self, output_name: str, rect: tuple[int, int, int, int],
                           fullscreen: bool = False) -> None:
        raise NotImplementedError

    # Aufnahme im Hintergrund: Ein minimiertes Fenster zeichnet sich nicht, also gibt es kein Bild.
    # Wo möglich wird es wiederhergestellt, aber ganz nach hinten gelegt und nicht aktiviert.
    can_restore_background = False

    def is_minimized(self, title: str) -> bool:
        return False

    def restore_in_background(self, title: str) -> bool:
        return False


@dataclass
class Sensor:
    id: str
    name: str
    detail: str = ""


FINGERS = [
    ("right-index-finger", "Rechter Zeigefinger"),
    ("right-thumb", "Rechter Daumen"),
    ("right-middle-finger", "Rechter Mittelfinger"),
    ("right-ring-finger", "Rechter Ringfinger"),
    ("right-little-finger", "Rechter kleiner Finger"),
    ("left-index-finger", "Linker Zeigefinger"),
    ("left-thumb", "Linker Daumen"),
    ("left-middle-finger", "Linker Mittelfinger"),
    ("left-ring-finger", "Linker Ringfinger"),
    ("left-little-finger", "Linker kleiner Finger"),
]
FINGER_NAMES = dict(FINGERS)


class Cancelled(Exception):
    """Vorgang wurde vom Benutzer abgebrochen."""


class FingerprintBackend:
    """Fingerabdrucksensor: Sensoren, Finger anlernen/prüfen/löschen, Anmeldung.

    Alle Methoden außer `cancel` blockieren und laufen deshalb in einem eigenen Thread.
    `status(text, stage, total)` meldet Fortschritt an die Oberfläche.
    """

    name = "keins"
    can_enroll = False  # False: Anlernen nur über die Systemeinstellungen (Windows Hello)
    can_delete = False
    can_list_enrolled = False
    login_toggle = False  # Anmeldung per Fingerabdruck ein-/ausschaltbar

    def availability(self) -> tuple[bool, str]:
        return (False, "Auf diesem System nicht unterstützt.")

    def list_sensors(self) -> list[Sensor]:
        return []

    def list_enrolled(self, sensor_id: str) -> list[str]:
        return []

    def enroll(self, sensor_id: str, finger: str, status) -> None:
        raise NotImplementedError

    def verify(self, sensor_id: str, status) -> tuple[bool, str]:
        raise NotImplementedError

    def delete(self, sensor_id: str, finger: str) -> None:
        raise NotImplementedError

    def cancel(self) -> None:
        pass

    def login_enabled(self) -> bool | None:
        return None

    def set_login_enabled(self, enabled: bool) -> None:
        raise NotImplementedError

    def open_system_settings(self) -> None:
        pass

    def install_hint(self) -> str:
        return ""
