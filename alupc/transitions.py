"""Übergänge zwischen Inhalten/Szenen auf Monitor 2.

Das alte Bild wird als Foto über den neuen Inhalt gelegt und auf verschiedene Arten
weggenommen – der neue Inhalt läuft darunter schon live.
"""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QRectF, Qt, QVariantAnimation
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import QWidget

# Schlüssel → Anzeigename
TRANSITIONS = {
    "blende": "Überblenden",
    "schwarz": "Über Schwarz blenden",
    "schieben": "Wegschieben (nach links)",
    "wischen": "Wischen (von links nach rechts)",
    "zoom": "Zoom (altes Bild wird größer und verschwindet)",
    "schnitt": "Harter Schnitt (sofort)",
}
DEFAULT = {"type": "blende", "ms": 400}


def resolve(global_cfg: dict | None, scene_cfg: dict | None = None) -> tuple[str, int]:
    """Welcher Übergang gilt? Szene überschreibt die allgemeine Einstellung (wenn gesetzt)."""
    kind, ms = DEFAULT["type"], DEFAULT["ms"]
    for cfg in (global_cfg, scene_cfg):
        if not cfg:
            continue
        if cfg.get("type") in TRANSITIONS:
            kind = cfg["type"]
        if cfg.get("ms"):
            ms = int(cfg["ms"])
    return kind, max(50, min(5000, ms))


class TransitionLayer(QWidget):
    """Zeichnet das alte Bild abhängig vom Fortschritt 0 → 1."""

    def __init__(self, old: QPixmap, kind: str, parent=None):
        super().__init__(parent)
        self.old = old
        self.kind = kind
        self.progress = 0.0
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.anim = QVariantAnimation(self)
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(1.0)
        self.anim.setEasingCurve(QEasingCurve.InOutCubic if kind != "blende" else QEasingCurve.InOutQuad)
        self.anim.valueChanged.connect(self._step)

    def start(self, ms: int) -> None:
        self.anim.setDuration(ms)
        self.anim.start()

    def _step(self, value):
        self.progress = float(value)
        self.update()

    def paintEvent(self, _event):
        t = self.progress
        w, h = self.width(), self.height()
        full = QRectF(0, 0, w, h)
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        if self.kind == "blende":
            p.setOpacity(1.0 - t)
            p.drawPixmap(full, self.old, QRectF(self.old.rect()))
        elif self.kind == "schwarz":
            if t < 0.5:  # erst altes Bild abdunkeln …
                p.drawPixmap(full, self.old, QRectF(self.old.rect()))
                p.fillRect(full, QColor(0, 0, 0, round(255 * t * 2)))
            else:  # … dann aus Schwarz das neue aufblenden
                p.fillRect(full, QColor(0, 0, 0, round(255 * (1 - t) * 2)))
        elif self.kind == "schieben":
            p.drawPixmap(QRectF(-t * w, 0, w, h), self.old, QRectF(self.old.rect()))
        elif self.kind == "wischen":
            src = QRectF(self.old.rect())
            p.drawPixmap(QRectF(t * w, 0, w * (1 - t), h),
                         self.old, QRectF(src.width() * t, 0, src.width() * (1 - t), src.height()))
        elif self.kind == "zoom":
            scale = 1 + 0.25 * t
            p.setOpacity(1.0 - t)
            p.drawPixmap(QRectF(w * (1 - scale) / 2, h * (1 - scale) / 2, w * scale, h * scale),
                         self.old, QRectF(self.old.rect()))
        p.end()
