"""Studio-Modus (wie in OBS): links die Vorschau, rechts was gerade live auf dem Bildschirm ist.

Solange das Fenster offen ist, landen Kacheln, Szenen und Befehle erst in der Vorschau. Dort kann man in Ruhe
prüfen, dann schaltet „Übergang“ (oder die Leertaste) die Vorschau live – mit dem gewählten Übergang. Der vorige
Inhalt wandert in die Vorschau, so kann man mit einem zweiten Klick zurückwechseln.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QKeySequence, QPainter, QPen, QShortcut
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..scenes import describe_source
from . import icons, theme
from .widgets import button, font, page_header, paint_live_pill, paint_scene_thumb

# Quellen, die es nur einmal gibt (Kamera, Bildschirm-/Fensteraufnahme, AirPlay …): in der Vorschau nur als
# Schema – sonst würde die Vorschau sie dem Live-Bild wegnehmen
EXCLUSIVE = {"camera", "window", "screen", "airplay", "cast", "spiel", "schiffe", "umfrage"}


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


class Screen(QFrame):
    """16:9-Fläche mit Rahmen und Etikett („Vorschau“ / „Live“)."""

    def __init__(self, label: str, live: bool, parent=None):
        super().__init__(parent)
        self.label, self.live = label, live
        self.image = None  # Live: Abbild von Monitor 2
        self.placeholder: dict | None = None  # Vorschau ohne echtes Bild (Kamera …): Schema + Text
        self.empty_text = ""
        self.setMinimumSize(320, 180)
        self.setAttribute(Qt.WA_OpaquePaintEvent, False)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, w):
        return round(w * 9 / 16)

    def sizeHint(self):
        return QSize(560, 315)

    def content_rect(self) -> QRectF:
        w = self.width()
        h = min(self.height(), w * 9 / 16)
        w = h * 16 / 9
        return QRectF((self.width() - w) / 2, (self.height() - h) / 2, w, h)

    def paintEvent(self, _e):
        t = theme.current()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = self.content_rect()
        if self.image is not None and not self.image.isNull():
            p.drawImage(r, self.image)
        elif self.placeholder is not None:
            paint_scene_thumb(p, r.adjusted(8, 8, -8, -8), self.placeholder.get("scene"),
                              self.placeholder.get("layout"))
            p.setPen(QColor("#ffffff"))
            p.setFont(font(10, QFont.DemiBold))
            p.drawText(r.adjusted(16, 0, -16, -14), Qt.AlignHCenter | Qt.AlignBottom | Qt.TextWordWrap,
                       self.placeholder.get("text", ""))
        elif self.empty_text:
            p.fillRect(r, QColor(t.mix(t.bg, "#000000", 0.4)))
            p.setPen(QColor(t.muted))
            p.setFont(font(10))
            p.drawText(r.adjusted(20, 20, -20, -20), Qt.AlignCenter | Qt.TextWordWrap, self.empty_text)
        color = QColor(t.live if self.live else "#2fd27a")
        p.setPen(QPen(color, 3))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(r.adjusted(1.5, 1.5, -1.5, -1.5), 6, 6)
        if self.live:
            paint_live_pill(p, QRectF(r.left() + 12, r.top() + 12, 52, 22))
        p.end()


class StudioWindow(QWidget):
    """Eigenes Fenster: Vorschau | Übergang | Live."""

    def __init__(self, controller, parent=None):
        super().__init__(parent, Qt.Window)
        self.controller = controller
        self.setWindowTitle("Studio-Modus – AluPC")
        self.setObjectName("StudioWindow")
        self.resize(1320, 640)
        self._preview_cfg = None
        self._preview_widget: QWidget | None = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 18, 22, 18)
        lay.setSpacing(14)
        lay.addWidget(page_header("Studio-Modus", "Links vorbereiten, mit „Übergang“ live schalten – wie in OBS",
                                  "scenes"))

        screens = QHBoxLayout()
        screens.setSpacing(16)
        left = QVBoxLayout()
        head = QLabel("●  Vorschau – wird vorbereitet")
        head.setStyleSheet("color: #2fd27a; font-weight: 700;")
        left.addWidget(head)
        self.preview = Screen("Vorschau", False)
        self.preview_host = QWidget(self.preview)  # echte Quelle (Text, Uhr, Vorlage …) in Vorschau-Größe
        self.preview_host.hide()
        self.preview_caption = QLabel()
        self.preview_caption.setObjectName("Muted")
        left.addWidget(self.preview, 1)
        left.addWidget(self.preview_caption)
        right = QVBoxLayout()
        head = QLabel("●  Live – das sehen alle")
        head.setStyleSheet(f"color: {theme.current().live}; font-weight: 700;")
        right.addWidget(head)
        self.live = Screen("Live", True)
        self.live_caption = QLabel()
        self.live_caption.setObjectName("Muted")
        right.addWidget(self.live, 1)
        right.addWidget(self.live_caption)

        middle = QVBoxLayout()
        middle.setSpacing(10)
        middle.addStretch(1)
        self.take_button = button("Übergang", "forward", primary=True)
        self.take_button.setMinimumHeight(56)
        self.take_button.setToolTip("Vorschau live schalten (Leertaste)")
        self.take_button.clicked.connect(self.take)
        from ..transitions import TRANSITIONS

        self.kind = QComboBox()
        for key, label in TRANSITIONS.items():
            self.kind.addItem(label.split(" (")[0], key)
        tr = self.controller.config.data.get("transition") or {}
        self.kind.setCurrentIndex(max(0, self.kind.findData(tr.get("type", "blende"))))
        self.ms = QSpinBox()
        self.ms.setRange(0, 5000)
        self.ms.setSingleStep(100)
        self.ms.setSuffix(" ms")
        self.ms.setValue(int(tr.get("ms", 400) or 400))
        self.cut = button("Schnitt", "x")
        self.cut.setToolTip("Sofort live schalten, ohne Übergang")
        self.cut.clicked.connect(lambda: self.take(("schnitt", 0)))
        clear = button("Vorschau leeren", "trash")
        clear.clicked.connect(self.controller.clear_preview)
        for w in (self.take_button, self.kind, self.ms, self.cut, clear):
            w.setFixedWidth(170)
            middle.addWidget(w, 0, Qt.AlignHCenter)
        middle.addStretch(1)

        screens.addLayout(left, 1)
        screens.addLayout(middle)
        screens.addLayout(right, 1)
        lay.addLayout(screens, 1)

        # Szenen direkt in die Vorschau legen
        bar = QHBoxLayout()
        bar.setSpacing(8)
        hint = QLabel("Szenen:")
        hint.setObjectName("Muted")
        bar.addWidget(hint)
        self.scene_bar = bar
        self._scene_buttons: list[QPushButton] = []
        bar.addStretch(1)
        lay.addLayout(bar)
        tip = QLabel("Solange dieses Fenster offen ist, gehen Kacheln, Szenen und Befehle erst in die Vorschau. "
                     "Kamera, Bildschirm-Aufnahme und AirPlay zeigt die Vorschau nur als Schema (es gibt sie nur "
                     "einmal).")
        tip.setObjectName("Muted")
        tip.setWordWrap(True)
        lay.addWidget(tip)

        QShortcut(QKeySequence(Qt.Key_Space), self, activated=self.take)
        self._timer = QTimer(self, interval=500)
        self._timer.timeout.connect(self._update_live)
        controller.studio_changed.connect(self._update_preview)
        controller.changed.connect(self._update_captions)

    # ------------------------------------------------------------ öffnen/schließen
    def showEvent(self, e):
        super().showEvent(e)
        self.controller.set_studio(True)
        self._fill_scenes()
        self._update_preview()
        self._update_live()
        self._timer.start()

    def closeEvent(self, e):
        self._timer.stop()
        self._drop_preview_widget()
        self.controller.set_studio(False)
        super().closeEvent(e)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._place_host()

    # ------------------------------------------------------------ Aktionen
    def take(self, transition: tuple[str, int] | None = None) -> None:
        if transition is None or isinstance(transition, bool):
            transition = (self.kind.currentData(), self.ms.value())
        if not self.controller.take(transition):
            self.controller.message.emit("Vorschau ist leer – erst eine Kachel oder Szene wählen.")

    def _fill_scenes(self) -> None:
        for b in self._scene_buttons:
            b.deleteLater()
        self._scene_buttons = []
        for scene in self.controller.config["scenes"][:12]:
            b = QPushButton(scene["name"])
            b.setIcon(icons.icon("scenes", theme.current().text, 16))
            b.clicked.connect(lambda _=False, n=scene["name"]: self.controller.show_source(
                {"type": "scene", "scene": n}))
            self.scene_bar.insertWidget(self.scene_bar.count() - 1, b)
            self._scene_buttons.append(b)

    # ------------------------------------------------------------ Anzeige
    def _drop_preview_widget(self) -> None:
        w = self._preview_widget
        self._preview_widget = None
        if w is not None:
            if hasattr(w, "stop"):
                try:
                    w.stop()
                except RuntimeError:
                    pass
            w.hide()
            w.deleteLater()

    def _place_host(self) -> None:
        r = self.preview.content_rect().adjusted(3, 3, -3, -3).toRect()
        self.preview_host.setGeometry(r)
        if self._preview_widget is not None:
            self._preview_widget.setGeometry(0, 0, r.width(), r.height())

    def _update_preview(self) -> None:
        c = self.controller
        cfg = c.preview
        self._update_captions()
        if cfg == self._preview_cfg and (cfg is None or self._preview_widget or self.preview.placeholder):
            return
        self._preview_cfg = dict(cfg) if cfg else None
        self._drop_preview_widget()
        self.preview.placeholder = None
        self.preview.empty_text = "" if cfg else "Leer – Kachel oder Szene wählen, sie erscheint hier"
        self.preview_host.hide()
        if cfg is not None:
            if uses_exclusive(cfg, c.config.get_scene):
                scene = c.config.get_scene(cfg.get("scene", "")) if cfg.get("type") == "scene" else None
                self.preview.placeholder = {"scene": scene, "text": f"{describe_source(cfg)} – live sichtbar "
                                                                    "nach dem Übergang"}
            else:
                from ..sources import create_source, media_sources

                widget = create_source(cfg, c.config.get_scene, parent=self.preview_host)
                for src in media_sources(widget):  # Vorschau ist stumm
                    src.set_volume(None, True)
                self._preview_widget = widget
                self._place_host()
                widget.show()
                self.preview_host.show()
        self.preview.update()

    def _update_captions(self) -> None:
        c = self.controller
        self.preview_caption.setText(describe_source(c.preview) if c.preview else "Vorschau leer")
        self.live_caption.setText(c.describe())
        self.take_button.setEnabled(c.preview is not None)

    def _update_live(self) -> None:
        from ..output_window import grab_scaled

        c = self.controller
        out = c.output
        if out.isVisible() and c.mode == "content":
            r = self.live.content_rect()
            self.live.image = grab_scaled(out, QSize(int(r.width()), int(r.height())))
            self.live.empty_text = ""
        else:
            self.live.image = None
            self.live.empty_text = "Bildschirm zeigt den erweiterten Desktop"
        self.live.update()
