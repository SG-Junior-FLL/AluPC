"""Design-Schnellwahl (Knopf unten links): ein grafisches Auswahlfeld statt einer Textliste – Vorschaukarten je Stil,
Hell/Dunkel bzw. Holzart, Akzentfarbe und Profile. Jede Wahl wirkt sofort (wie Setup → Darstellung)."""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractButton,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from . import theme
from .widgets import FlowLayout, font

CARD_W, CARD_H = 132, 96


class StyleCard(QAbstractButton):
    """Kleine Vorschau eines Stils: Hintergrund, Karte, Akzentknopf, Schrift – so sieht AluPC damit aus."""

    def __init__(self, key: str, preview: theme.Theme, current: bool, parent=None):
        super().__init__(parent)
        self.key, self.preview, self.current = key, preview, current
        self.setFixedSize(CARD_W, CARD_H)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(theme.STYLE_INFO.get(key, ""))

    def sizeHint(self):
        return QSize(CARD_W, CARD_H)

    def paintEvent(self, _e):
        t, ui = self.preview, theme.current()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        frame = QRectF(self.rect()).adjusted(1.5, 1.5, -1.5, -1.5)
        r = 10.0
        shot = QRectF(frame.x() + 6, frame.y() + 6, frame.width() - 12, 56)
        # Rahmen der Karte (in der Farbe der aktuellen Oberfläche)
        p.setPen(QPen(QColor(ui.accent), 2.5) if self.current else QPen(QColor(ui.border), 1))
        p.setBrush(QColor(ui.surface2) if self.underMouse() else QColor(ui.surface))
        p.drawRoundedRect(frame, r, r)
        # Mini-Vorschau im Stil
        rad = max(2.0, 6 * t.radius_scale if t.style == "normal" else 3)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(t.bg))
        p.drawRoundedRect(shot, 6, 6)
        p.setBrush(QColor(t.surface))
        card = QRectF(shot.x() + 8, shot.y() + 8, shot.width() * 0.62, shot.height() - 16)
        p.setPen(QPen(QColor(t.border), 1))
        p.drawRoundedRect(card, rad, rad)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(t.muted))
        p.drawRoundedRect(QRectF(card.x() + 6, card.y() + 7, card.width() * 0.6, 4), 2, 2)
        p.setBrush(QColor(t.text))
        p.drawRoundedRect(QRectF(card.x() + 6, card.y() + 15, card.width() * 0.75, 5), 2, 2)
        p.setBrush(QColor(t.accent))
        p.drawRoundedRect(QRectF(card.x() + 6, card.bottom() - 13, 30, 8), min(4, rad), min(4, rad))
        p.setBrush(QColor(t.accent))
        dot = QRectF(shot.right() - 22, shot.y() + 10, 12, 12)
        p.drawEllipse(dot)
        p.setBrush(QColor(t.surface2))
        p.drawRoundedRect(QRectF(shot.right() - 26, dot.bottom() + 6, 20, 14), 3, 3)
        # Name
        p.setPen(QColor(ui.text))
        p.setFont(font(9.5, QFont.Bold if self.current else QFont.DemiBold))
        p.drawText(QRectF(frame.x() + 8, shot.bottom() + 4, frame.width() - 16, 22), Qt.AlignLeft | Qt.AlignVCenter,
                   theme.STYLES.get(self.key, self.key) + ("  ✓" if self.current else ""))
        p.end()

    def enterEvent(self, e):
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.update()
        super().leaveEvent(e)


class Swatch(QAbstractButton):
    """Runder Farbtupfer (Akzentfarbe, Holzart)."""

    def __init__(self, color: str, tip: str, current: bool, parent=None):
        super().__init__(parent)
        self.color, self.current = color, current
        self.setToolTip(tip)
        self.setFixedSize(30, 30)
        self.setCursor(Qt.PointingHandCursor)

    def paintEvent(self, _e):
        ui = theme.current()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        if self.current:
            p.setPen(QPen(QColor(ui.text), 2))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(QRectF(self.rect()).adjusted(1.5, 1.5, -1.5, -1.5))
        p.setPen(QPen(QColor(ui.border), 1))
        p.setBrush(QColor(self.color))
        p.drawEllipse(QRectF(self.rect()).adjusted(5, 5, -5, -5))
        p.end()


class StylePopover(QFrame):
    """Das Auswahlfeld. `apply(**changes)` und `profile(name)` kommen vom Hauptfenster."""

    def __init__(self, window):
        super().__init__(window, Qt.Popup | Qt.FramelessWindowHint)
        self.window_ = window
        self.setObjectName("StylePopover")
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(14, 12, 14, 12)
        self.lay.setSpacing(8)
        self._build()

    def _section(self, text: str) -> None:
        label = QLabel(text.upper())
        label.setObjectName("Muted")
        label.setFont(font(8, QFont.Bold))
        self.lay.addWidget(label)

    def _build(self) -> None:
        a = self.window_.config["appearance"]
        ui = theme.current()
        self.setStyleSheet(f"#StylePopover {{ background: {ui.surface}; border: 1px solid {ui.border}; "
                           "border-radius: 14px; }")
        head = QHBoxLayout()
        title = QLabel("Design")
        title.setFont(font(13, QFont.Bold))
        head.addWidget(title, 1)
        more = QPushButton("Mehr einstellen …")
        more.setFlat(True)
        more.clicked.connect(lambda: (self.close(), self.window_.open_setup_section("Darstellung")))
        head.addWidget(more)
        self.lay.addLayout(head)

        self._section("Stil")
        grid = QGridLayout()
        grid.setSpacing(8)
        mode, accent, wood = a.get("mode", "dunkel"), a.get("accent", "alupc"), a.get("wood", theme.DEFAULT_WOOD)
        for i, key in enumerate(theme.STYLES):
            preview = theme.make_theme(mode, accent, key, wood, custom={**a, "style": key})
            card = StyleCard(key, preview, a.get("style", "normal") == key)
            card.clicked.connect(lambda _c=False, k=key: self._set(style=k))
            grid.addWidget(card, i // 3, i % 3)
        self.lay.addLayout(grid)

        if a.get("style") == "holz":
            self._section("Holzart")
            row = FlowLayout(spacing=4)
            for key, info in theme.WOODS.items():
                sw = Swatch(info[1], info[0], wood == key)
                sw.clicked.connect(lambda _c=False, k=key: self._set(wood=k))
                row.addWidget(sw)
            self.lay.addLayout(row)
        else:
            self._section("Helligkeit")
            row = QHBoxLayout()
            row.setSpacing(6)
            for key, label in (("dunkel", "Dunkel"), ("hell", "Hell"), ("system", "Wie das System")):
                b = QPushButton(label)
                b.setObjectName("Segment")
                b.setCheckable(True)
                b.setChecked(mode == key)
                b.clicked.connect(lambda _c=False, k=key: self._set(mode=k))
                row.addWidget(b)
            self.lay.addLayout(row)

        self._section("Farbe")
        row = FlowLayout(spacing=4)
        for key, (label, color) in theme.ACCENTS.items():
            if key == "eigen":
                color = a.get("accent_color") or color
            sw = Swatch(theme.system_accent() if key == "system" else color, label, accent == key)
            sw.clicked.connect(lambda _c=False, k=key: self._set(accent=k))
            row.addWidget(sw)
        self.lay.addLayout(row)

        profiles = {**theme.BUILTIN_PROFILES, **(a.get("profiles") or {})}
        if profiles:
            self._section("Profil")
            row = FlowLayout(spacing=6)
            for name in profiles:
                b = QPushButton(name.replace("&", "&&"))  # „&“ wäre sonst ein Tastenkürzel-Zeichen
                b.setObjectName("Chip")
                b.setCheckable(True)
                b.setChecked(a.get("profile") == name)
                b.clicked.connect(lambda _c=False, n=name: self._profile(n))
                row.addWidget(b)
            self.lay.addLayout(row)

        hide = QPushButton("Diesen Knopf ausblenden")
        hide.setFlat(True)
        hide.setObjectName("Muted")
        hide.clicked.connect(lambda: (self.close(), self.window_.quick_appearance(quick_switch=False)))
        self.lay.addWidget(hide, 0, Qt.AlignLeft)

    def _rebuild(self) -> None:
        while self.lay.count():
            item = self.lay.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)  # sofort weg (deleteLater allein ließe sie bis zur nächsten Runde stehen)
                w.deleteLater()
            elif item.layout() is not None:
                _clear(item.layout())
        self._build()
        self.adjustSize()

    def _set(self, **changes) -> None:
        self.window_.quick_appearance(**changes)
        self._rebuild()

    def _profile(self, name: str) -> None:
        self.window_.quick_profile(name)
        self._rebuild()

    def popup_at(self, anchor) -> None:
        """Rechts neben dem Knopf, nach oben aufgehend (der Knopf sitzt unten links)."""
        self.adjustSize()
        pos = anchor.mapToGlobal(QPoint(anchor.width() + 8, anchor.height() - self.height()))
        screen = anchor.screen().availableGeometry() if anchor.screen() else None
        if screen is not None:
            pos.setY(max(screen.top() + 8, min(pos.y(), screen.bottom() - self.height() - 8)))
            pos.setX(min(pos.x(), screen.right() - self.width() - 8))
        self.move(pos)
        self.show()


def _clear(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        if item.widget() is not None:
            item.widget().setParent(None)
            item.widget().deleteLater()
        elif item.layout() is not None:
            _clear(item.layout())
