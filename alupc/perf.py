"""Leistung: flüssig auf starken PCs, sparsam auf schwachen.

„Automatisch“ (Standard) erkennt schwache PCs (≤ 4 Prozessorkerne) und begrenzt dann die Bildrate von
Animationen. Zusätzlich misst jede Animation, wie lange ein Bild zum Zeichnen braucht, und zeichnet von selbst
seltener, wenn der PC nicht hinterherkommt – so bleibt AluPC bedienbar und der Lüfter ruhig."""

from __future__ import annotations

import os
import time

MODES = {"auto": "Automatisch", "fluessig": "Flüssig (starker PC)", "sparsam": "Sparsam (schwacher PC)"}
_mode = "auto"


def configure(mode: str | None) -> None:
    global _mode
    _mode = mode if mode in MODES else "auto"


def weak_pc() -> bool:
    return (os.cpu_count() or 2) <= 4


def saving() -> bool:
    """Sparsam zeichnen? (Einstellung oder automatisch erkannter schwacher PC)"""
    if os.environ.get("ALUPC_SPARSAM") == "1":
        return True
    return _mode == "sparsam" or (_mode == "auto" and weak_pc())


def max_fps() -> int:
    return 15 if saving() else 30


def interval(requested_ms: int) -> int:
    """Timer-Abstand für eine Animation – nie schneller als die erlaubte Bildrate."""
    return max(int(requested_ms), int(1000 / max_fps()))


class FrameGovernor:
    """Misst die Zeichenzeit und macht den Timer langsamer, wenn ein Bild zu lange dauert
    (mehr als 40 % der Zeit zwischen zwei Bildern) – bis höchstens 8 Bilder pro Sekunde."""

    SLOWEST_MS = 125

    def __init__(self, timer):
        self.timer = timer
        self._t0 = 0.0
        self._sum = 0.0
        self._n = 0

    def begin(self) -> None:
        self._t0 = time.perf_counter()

    def end(self) -> None:
        if not self._t0:
            return
        self._sum += time.perf_counter() - self._t0
        self._n += 1
        if self._n >= 20:
            avg_ms = self._sum / self._n * 1000
            iv = self.timer.interval()
            if avg_ms > 0.4 * iv and iv < self.SLOWEST_MS:
                self.timer.setInterval(min(self.SLOWEST_MS, int(iv * 1.5)))
            self._sum, self._n = 0.0, 0
