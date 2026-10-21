"""Studio-Modus auf der Startseite (wie OBS): Über dem Live-Bild klappt eine Vorschau auf.

Kacheln, Szenen und Befehle landen dann erst in der Vorschau; „Übergang“ schaltet sie live. Der vorige Inhalt
wandert in die Vorschau – ein zweiter Klick wechselt zurück. Beim Einschalten teilt sich das Bild: oben erscheint
die Vorschau, das Live-Bild rutscht nach unten, dann kommen die Knöpfe.
"""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QRectF, Qt, QVariantAnimation
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QGraphicsOpacityEffect, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ..scenes import describe_source
from . import theme
from .widgets import button, font, paint_scene_thumb

# Quellen, die es nur einmal gibt (Kamera, Aufnahme, AirPlay …): Vorschau zeigt nur ein Schema,
# sonst nähme sie dem Live-Bild die Kamera weg
EXCLUSIVE = {"camera", "window", "screen", "airplay", "cast", "spiel", "schiffe", "umfrage"}
CUE = "#2fd27a"  # Grün = Vorschau (Rot bleibt „läuft“)


def uses_exclusive(cfg: dict | None, lookup) -> bool:
    if not cfg:
        return False
    kind = cfg.get("type")
    if kind in EXCLUSIVE or cfg.get("mirror"):
        return True
    if kind == "scene":
        scene = lookup(cfg.get("scene", "")) or {}
        return any(uses_exclusive(slot, lookup) for slot in scene.get("slots", []) if slot)
    return False


class CueScreen(QWidget):
    """Vorschau-Bild mit grünem Rahmen; echte Quelle als Kind (`host`) oder ein Schema."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.placeholder: dict | None = None
        self.empty = True
        self.host = QWidget(self)
        self.host.hide()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.host.setGeometry(self.rect().adjusted(3, 3, -3, -3))
        for child in self.host.findChildren(QWidget, options=Qt.FindDirectChildrenOnly):
            child.setGeometry(0, 0, self.host.width(), self.host.height())

    def paintEvent(self, _e):
        t = theme.current()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        rad = {"normal": 12, "holz": 4}.get(t.style, 3)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#0b0c10"))
        p.drawRoundedRect(r, rad, rad)
        if self.placeholder is not None:
            paint_scene_thumb(p, r.adjusted(8, 8, -8, -8), self.placeholder.get("scene"))
            p.setPen(QColor("#ffffff"))
            p.setFont(font(9, QFont.DemiBold))
            p.drawText(r.adjusted(10, 0, -10, -8), Qt.AlignHCenter | Qt.AlignBottom | Qt.TextWordWrap,
                       self.placeholder.get("text", ""))
        elif self.empty:
            p.setPen(QColor(t.muted))
            p.setFont(font(9.5))
            p.drawText(r, Qt.AlignCenter, "Kachel antippen")
        p.setPen(QPen(QColor(CUE), 2.5))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(r.adjusted(0.5, 0.5, -0.5, -0.5), rad, rad)
        p.end()


class StudioPanel(QWidget):
    """Vorschau + Knöpfe, steht in der Statuskarte direkt über dem Live-Bild."""

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self._cfg = None
        self._widget: QWidget | None = None
        self._progress = 0.0
        self._width = 320
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        self.caption = QLabel()
        self.caption.setStyleSheet(f"color: {CUE}; font-weight: 700;")
        lay.addWidget(self.caption)
        self.screen = CueScreen()
        lay.addWidget(self.screen)
        self.buttons = QWidget()
        row = QHBoxLayout(self.buttons)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        self.take_button = button("Übergang", "forward", primary=True)
        self.take_button.setToolTip("Vorschau live schalten (Strg+Enter)")
        self.take_button.clicked.connect(lambda: self.controller.take())
        self.cut_button = button("Schnitt")
        self.cut_button.setToolTip("Sofort live, ohne Überblenden")
        self.cut_button.clicked.connect(lambda: self.controller.take(("schnitt", 0)))
        self.clear_button = button("", "x")
        self.clear_button.setToolTip("Vorschau leeren")
        self.clear_button.clicked.connect(self.controller.clear_preview)
        row.addWidget(self.take_button, 1)
        row.addWidget(self.cut_button)
        row.addWidget(self.clear_button)
        lay.addWidget(self.buttons)
        self._fx = QGraphicsOpacityEffect(self.buttons)
        self._fx.setOpacity(0.0)
        self.buttons.setGraphicsEffect(self._fx)
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(520)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.valueChanged.connect(self._apply)
        self._anim.finished.connect(self._finished)
        self.setFixedHeight(0)
        self.hide()
        controller.studio_changed.connect(self.sync)

    # ------------------------------------------------------------ Größe/Animation
    def set_width(self, width: int) -> None:
        """Breite wie das Live-Bild darunter (die Vorschau ist gleich groß)."""
        self._width = width
        self.screen.setFixedSize(width, round(width * 9 / 16))
        self.setFixedWidth(width)
        self._apply(self._progress)

    def _full_height(self) -> int:
        return self.caption.sizeHint().height() + self.screen.height() + self.buttons.sizeHint().height() + 16

    def _apply(self, value) -> None:
        self._progress = float(value)
        self.setFixedHeight(round(self._full_height() * self._progress))
        self._fx.setOpacity(max(0.0, (self._progress - 0.6) / 0.4))  # Knöpfe kommen zum Schluss

    def _finished(self) -> None:
        if self._progress <= 0.001:
            self.hide()

    def open(self, on: bool, animate: bool = True) -> None:
        target = 1.0 if on else 0.0
        if on:
            self.show()
        self._anim.stop()
        if not animate or not self.isVisible():
            self._apply(target)
            self._finished()
            return
        self._anim.setStartValue(self._progress)
        self._anim.setEndValue(target)
        self._anim.start()

    # ------------------------------------------------------------ Inhalt
    def sync(self) -> None:
        c = self.controller
        want = c.studio
        if want != (self._anim.endValue() == 1.0 if self._anim.state() == self._anim.State.Running
                    else self._progress > 0.5):
            from .widgets import theme_reduced_motion

            self.open(want, animate=not theme_reduced_motion())
        cfg = c.preview if want else None
        self.caption.setText("Vorschau" + (f" · {describe_source(cfg)}" if cfg else ""))
        self.take_button.setEnabled(cfg is not None)
        self.cut_button.setEnabled(cfg is not None)
        if cfg == self._cfg and (cfg is None or self._widget is not None or self.screen.placeholder):
            return
        self._cfg = dict(cfg) if cfg else None
        self._drop()
        self.screen.placeholder = None
        self.screen.empty = cfg is None
        if cfg is not None:
            if uses_exclusive(cfg, c.config.get_scene):
                scene = c.config.get_scene(cfg.get("scene", "")) if cfg.get("type") == "scene" else None
                self.screen.placeholder = {"scene": scene, "text": "Bild erst live"}
            else:
                from ..sources import create_source, media_sources

                widget = create_source(cfg, c.config.get_scene, parent=self.screen.host)
                for src in media_sources(widget):  # Vorschau ist stumm
                    src.set_volume(None, True)
                widget.setGeometry(0, 0, self.screen.host.width(), self.screen.host.height())
                self._widget = widget
                widget.show()
                self.screen.host.show()
        self.screen.update()

    def _drop(self) -> None:
        w, self._widget = self._widget, None
        self.screen.host.hide()
        if w is not None:
            if hasattr(w, "stop"):
                try:
                    w.stop()
                except RuntimeError:
                    pass
            w.hide()
            w.deleteLater()

    @property
    def preview_widget(self) -> QWidget | None:
        return self._widget
