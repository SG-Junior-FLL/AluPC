"""Eigene, selbst gezeichnete Bausteine: Kacheln, Navigation, Statuskarte, Hinweise, Ring …"""

from __future__ import annotations

from PySide6.QtCore import (
    Property,
    QEasingCurve,
    QPointF,
    QPropertyAnimation,
    QRectF,
    QSize,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import QColor, QFont, QFontMetrics, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QAbstractButton,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..scenes import layout_slots
from . import icons, theme


def font(size_pt: float | None = None, weight: QFont.Weight = QFont.Normal) -> QFont:
    f = QFont()
    if size_pt:
        f.setPointSizeF(size_pt)
    f.setWeight(weight)
    return f


def button(text: str, icon_name: str | None = None, primary: bool = False, danger: bool = False) -> QPushButton:
    b = QPushButton(text)
    if primary:
        b.setProperty("primary", True)
    if danger:
        b.setProperty("danger", True)
    if icon_name:
        b.setProperty("iconName", icon_name)  # zum Neu-Einfärben beim Wechsel des Designs
        t = theme.current()
        color = "#ffffff" if primary else (t.danger if danger else t.text)
        b.setIcon(icons.icon(icon_name, color, 18))
        b.setIconSize(QSize(18, 18))
    b.setCursor(Qt.PointingHandCursor)
    return b


def page_header(title: str, subtitle: str = "") -> QWidget:
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 6)
    lay.setSpacing(2)
    t = QLabel(title)
    t.setObjectName("PageTitle")
    lay.addWidget(t)
    if subtitle:
        s = QLabel(subtitle)
        s.setObjectName("PageSubtitle")
        s.setWordWrap(True)
        lay.addWidget(s)
    return w


def rounded(rect: QRectF, radius: float) -> QPainterPath:
    path = QPainterPath()
    path.addRoundedRect(rect, radius, radius)
    return path


class HoverMixin:
    """Weiche Hover-Animation (0 → 1) für selbst gezeichnete Knöpfe."""

    def _init_hover(self):
        self._hover = 0.0
        self._anim = QPropertyAnimation(self, b"hover", self)
        self._anim.setDuration(140)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)

    def _get_hover(self):
        return self._hover

    def _set_hover(self, v):
        self._hover = v
        self.update()

    def _animate_hover(self, target):
        self._anim.stop()
        self._anim.setStartValue(self._hover)
        self._anim.setEndValue(target)
        self._anim.start()

    def enterEvent(self, e):
        self._animate_hover(1.0)
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._animate_hover(0.0)
        super().leaveEvent(e)


# --------------------------------------------------------------------------- Kachel
class Tile(HoverMixin, QAbstractButton):
    """Große Kachel: Symbol im farbigen Kreis, Titel, Untertitel, Zustand (aktiv/Warnung).

    Mit `set_menu(menu, split=True)` öffnet nur der Pfeil oben rechts das Menü; ein Klick auf
    den Rest der Kachel löst `activated` aus.
    """

    activated = Signal()

    def __init__(self, icon_name: str, title: str, subtitle: str = "", color: str | None = None, parent=None):
        super().__init__(parent)
        self.icon_name, self.title, self.subtitle = icon_name, title, subtitle
        self.color = color
        self.active = False
        self.alert = False
        self.badge = ""
        self.menu = None
        self.split = False
        self._press_pos = None
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumSize(QSize(200, 78))
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setToolTip(subtitle)
        self._init_hover()
        self.clicked.connect(self._show_menu)

    hover = Property(float, HoverMixin._get_hover, HoverMixin._set_hover)

    def set_menu(self, menu, split: bool = False):
        self.menu = menu
        self.split = split
        self.update()

    def menu_zone(self) -> QRectF:
        return QRectF(self.width() - 54, 0, 54, self.height())

    def mousePressEvent(self, e):
        self._press_pos = e.position()
        super().mousePressEvent(e)

    def _show_menu(self):
        in_zone = self._press_pos is not None and self.menu_zone().contains(self._press_pos)
        self._press_pos = None
        if self.menu is not None and (not self.split or in_zone):
            self.menu.popup(self.mapToGlobal(self.rect().bottomLeft()))
        else:
            self.activated.emit()

    def set_state(self, active: bool = False, alert: bool = False, badge: str = ""):
        if (active, alert, badge) != (self.active, self.alert, self.badge):
            self.active, self.alert, self.badge = active, alert, badge
            self.update()

    def sizeHint(self):
        return QSize(240, 82)

    def paintEvent(self, _e):
        t = theme.current()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        lift = 1.5 * self._hover if not self.isDown() else 0.0
        r = QRectF(self.rect()).adjusted(2.5, 1.5 - lift, -2.5, -4.5 - lift)
        accent = QColor(t.danger if self.alert else (self.color or t.accent))
        # weicher Schatten unter der Kachel (stärker beim Drüberfahren)
        p.setPen(Qt.NoPen)
        for i, alpha in enumerate((0.05, 0.035, 0.02)):
            shade = QColor(0, 0, 0)
            shade.setAlphaF((alpha * (1.6 if t.dark else 1.0)) * (1 + 1.2 * self._hover))
            p.fillPath(rounded(r.adjusted(-i * 0.5, 1.5 + i * 1.2, i * 0.5, 1.5 + i * 1.6), 16 + i), shade)
        base = QColor(t.surface)
        hover_bg = t.mix(t.surface, t.surface2, 0.9)
        bg = t.mix(base.name(), hover_bg.name(), self._hover)
        if self.active or self.alert:
            soft = QColor(accent)
            soft.setAlphaF(0.14 if t.dark else 0.10)
            p.fillPath(rounded(r, 16), bg)
            p.fillPath(rounded(r, 16), soft)
        else:
            p.fillPath(rounded(r, 16), bg)
        border = QColor(accent) if (self.active or self.alert) else t.mix(t.border, t.muted, 0.35 * self._hover)
        p.setPen(QPen(border, 2 if (self.active or self.alert) else 1))
        p.drawPath(rounded(r, 16))
        if self.isDown():
            p.fillPath(rounded(r, 16), QColor(0, 0, 0, 30))

        # Symbol links im Quadrat
        pad = 14
        chip = QRectF(r.left() + pad, r.center().y() - 22, 44, 44)
        p.setPen(Qt.NoPen)
        if self.active or self.alert:  # aktiv: kräftiger Verlauf
            grad = QLinearGradient(chip.topLeft(), chip.bottomRight())
            grad.setColorAt(0, accent.lighter(118))
            grad.setColorAt(1, accent.darker(108))
            p.setBrush(grad)
        else:
            chip_col = QColor(accent)
            chip_col.setAlphaF((0.18 if t.dark else 0.12) + 0.08 * self._hover)
            p.setBrush(chip_col)
        p.drawRoundedRect(chip, 12, 12)
        icon_col = "#ffffff" if (self.active or self.alert) else accent.name()
        icons.paint(p, self.icon_name, chip.adjusted(11, 11, -11, -11), icon_col, 2.0)

        right = r.right() - pad
        # Menü-Pfeil rechts mittig
        if self.menu is not None:
            cx, cy = right - 10, r.center().y()
            if self.split:
                ring = QColor(t.muted)
                ring.setAlphaF(0.16 + 0.3 * self._hover)
                p.setPen(Qt.NoPen)
                p.setBrush(ring)
                p.drawEllipse(QRectF(cx - 13, cy - 13, 26, 26))
            p.setPen(QPen(QColor(t.text if self.split else t.muted), 1.8, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(QPointF(cx - 4, cy - 2), QPointF(cx, cy + 2))
            p.drawLine(QPointF(cx, cy + 2), QPointF(cx + 4, cy - 2))
            right -= 34
        # Zustand (z. B. AKTIV) klein oben rechts
        if self.badge:
            f = font(7.5, QFont.Bold)
            p.setFont(f)
            bw = QFontMetrics(f).horizontalAdvance(self.badge) + 14
            badge = QRectF(r.right() - pad - bw, r.top() + 7, bw, 18)
            p.setPen(Qt.NoPen)
            p.setBrush(accent)
            p.drawRoundedRect(badge, 9, 9)
            p.setPen(QColor("#ffffff"))
            p.drawText(badge, Qt.AlignCenter, self.badge)

        # Texte rechts vom Symbol
        left = chip.right() + 12
        width = max(20.0, right - left - 4)
        tf = font(11.5, QFont.DemiBold)
        p.setFont(tf)
        p.setPen(QColor(t.text))
        title = QFontMetrics(tf).elidedText(self.title, Qt.ElideRight, int(width))
        has_sub = bool(self.subtitle)
        p.drawText(QRectF(left, r.center().y() - (21 if has_sub else 11), width, 22), Qt.AlignLeft | Qt.AlignVCenter,
                   title)
        if has_sub:
            p.setPen(QColor(t.muted))
            sf = font(8.8)
            p.setFont(sf)
            sub = QFontMetrics(sf).elidedText(self.subtitle, Qt.ElideRight, int(width))
            p.drawText(QRectF(left, r.center().y() + 1, width, 20), Qt.AlignLeft | Qt.AlignVCenter, sub)
        p.end()


# --------------------------------------------------------------------------- Navigation
class NavButton(HoverMixin, QAbstractButton):
    def __init__(self, icon_name: str, text: str, parent=None):
        super().__init__(parent)
        self.icon_name, self.text_ = icon_name, text
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(42)
        self._init_hover()

    hover = Property(float, HoverMixin._get_hover, HoverMixin._set_hover)

    def paintEvent(self, _e):
        t = theme.current()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(8, 2, -8, -2)
        if self.isChecked():
            soft = QColor(t.accent)
            soft.setAlphaF(0.18)
            p.fillPath(rounded(r, 10), soft)
            p.fillPath(rounded(QRectF(r.left(), r.top() + 10, 3.5, r.height() - 20), 1.75), QColor(t.accent))
        elif self._hover > 0:
            h = QColor(t.text)
            h.setAlphaF(0.06 * self._hover)
            p.fillPath(rounded(r, 10), h)
        col = t.accent if self.isChecked() else t.muted
        icons.paint(p, self.icon_name, QRectF(r.left() + 14, r.center().y() - 10, 20, 20), col, 2.0)
        p.setPen(QColor(t.text if self.isChecked() else t.muted))
        p.setFont(font(10.5, QFont.DemiBold if self.isChecked() else QFont.Medium))
        p.drawText(r.adjusted(46, 0, 0, 0), Qt.AlignLeft | Qt.AlignVCenter, self.text_)
        p.end()


# --------------------------------------------------------------------------- Pill / Status
class Pill(QWidget):
    """Kleines farbiges Etikett, z. B. „LIVE“ oder „STANDBILD“."""

    def __init__(self, text: str = "", color: str = "#22c55e", dot: bool = True, parent=None):
        super().__init__(parent)
        self.text_, self.color, self.dot = text, color, dot
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

    def set(self, text: str, color: str):
        self.text_, self.color = text, color
        self.updateGeometry()
        self.update()

    def sizeHint(self):
        fm = QFontMetrics(font(8.5, QFont.Bold))
        return QSize(fm.horizontalAdvance(self.text_) + (30 if self.dot else 18), 24)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        c = QColor(self.color)
        bg = QColor(c)
        bg.setAlphaF(0.16)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.fillPath(rounded(r, r.height() / 2), bg)
        x = 9
        if self.dot:
            p.setPen(Qt.NoPen)
            p.setBrush(c)
            p.drawEllipse(QPointF(x + 3, r.center().y()), 3.5, 3.5)
            x += 12
        p.setPen(c)
        p.setFont(font(8.5, QFont.Bold))
        p.drawText(r.adjusted(x, 0, 0, 0), Qt.AlignLeft | Qt.AlignVCenter, self.text_)
        p.end()


class PreviewThumb(QWidget):
    """Kleines Live-Bild von Monitor 2 (abgerundet, mit Rahmen) – oder ein Symbol, wenn nichts läuft."""

    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.image = None
        self.icon_name = "monitor"
        self.setFixedSize(272, 153)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Live-Vorschau von Monitor 2 – Klick öffnet Bild-in-Bild")

    def set(self, image, icon_name: str):
        self.image = image if image is not None and not image.isNull() else None
        self.icon_name = icon_name
        self.update()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton and self.rect().contains(e.position().toPoint()):
            self.clicked.emit()

    def paintEvent(self, _e):
        t = theme.current()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = rounded(r, 14)
        if self.image is not None:
            p.fillPath(path, QColor("#000000"))
            p.save()
            p.setClipPath(path)
            iw, ih = self.image.width(), self.image.height()
            scale = min(r.width() / iw, r.height() / ih)
            target = QRectF(0, 0, iw * scale, ih * scale)
            target.moveCenter(r.center())
            p.drawImage(target, self.image)
            p.restore()
        else:
            soft = QColor(t.accent)
            soft.setAlphaF(0.14 if t.dark else 0.10)
            p.fillPath(path, QColor(t.surface2))
            p.fillPath(path, soft)
            s = 46
            icons.paint(p, self.icon_name, QRectF(r.center().x() - s / 2, r.center().y() - s / 2, s, s), t.accent, 1.9)
        p.setPen(QPen(QColor(t.border), 1))
        p.drawPath(path)
        p.end()


class StatusCard(QWidget):
    """Oben im Hauptfenster: Monitor 2 groß – Live-Bild, was läuft, Schnellschalter (Schwarz, Standbild …)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Hero")
        self.setAttribute(Qt.WA_StyledBackground, True)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 16, 20, 16)
        lay.setSpacing(20)
        self.preview = PreviewThumb()
        text = QVBoxLayout()
        text.setSpacing(4)
        self.caption = QLabel()
        self.caption.setObjectName("Muted")
        self.caption.setFont(font(8.5, QFont.DemiBold))
        self.title = QLabel()
        self.title.setFont(font(17, QFont.Bold))
        self.title.setWordWrap(True)
        self.pills = QHBoxLayout()
        self.pills.setSpacing(6)
        pill_row = QHBoxLayout()
        pill_row.setSpacing(0)
        pill_row.addLayout(self.pills)
        pill_row.addStretch(1)
        self.chips = QHBoxLayout()  # Schnellschalter (werden vom Hauptfenster eingesetzt)
        self.chips.setSpacing(8)
        chip_row = QHBoxLayout()
        chip_row.addLayout(self.chips)
        chip_row.addStretch(1)
        text.addStretch(1)
        text.addWidget(self.caption)
        text.addWidget(self.title)
        text.addLayout(pill_row)
        text.addSpacing(8)
        text.addLayout(chip_row)
        text.addStretch(1)
        self.actions = QVBoxLayout()
        self.actions.setSpacing(8)
        lay.addWidget(self.preview)
        lay.addLayout(text, 1)
        lay.addLayout(self.actions)

    def set(self, icon_name: str, caption: str, title: str, pills: list[tuple[str, str]]):
        self.preview.icon_name = icon_name
        if self.preview.image is None:
            self.preview.update()
        self.caption.setText(caption.upper())
        self.title.setText(title)
        # Etiketten wiederverwenden statt neu anlegen (kein Flackern, keine Reste)
        while self.pills.count() < len(pills):
            self.pills.addWidget(Pill())
        for i in range(self.pills.count()):
            pill = self.pills.itemAt(i).widget()
            if i < len(pills):
                pill.set(*pills[i])
                pill.show()
            else:
                pill.hide()

    def pill_texts(self) -> list[str]:
        pills = (self.pills.itemAt(i).widget() for i in range(self.pills.count()))
        return [p.text_ for p in pills if not p.isHidden()]


def _chip_pixmap(icon_name: str, color: str, size: int):
    from PySide6.QtGui import QPixmap

    dpr = 2
    px = QPixmap(size * dpr, size * dpr)
    px.setDevicePixelRatio(dpr)
    px.fill(Qt.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.Antialiasing)
    c = QColor(color)
    p.setPen(Qt.NoPen)
    p.setBrush(c)
    p.drawRoundedRect(QRectF(0, 0, size, size), size * 0.28, size * 0.28)
    icons.paint(p, icon_name, QRectF(size * 0.24, size * 0.24, size * 0.52, size * 0.52), "#ffffff", 2.0)
    p.end()
    return px


# --------------------------------------------------------------------------- Hinweis (Toast)
class Toast(QWidget):
    """Kurzer Hinweis unten im Fenster, blendet sich selbst aus."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.text_ = ""
        self.kind = "info"
        self.effect = QGraphicsOpacityEffect(self)
        self.effect.setOpacity(0)
        self.setGraphicsEffect(self.effect)
        self.anim = QPropertyAnimation(self.effect, b"opacity", self)
        self.anim.setDuration(220)
        self.timer = QTimer(self, singleShot=True)
        self.timer.timeout.connect(lambda: self._fade(0))
        self.hide()

    def show_text(self, text: str, kind: str = "info", ms: int = 4200):
        self.text_, self.kind = text, kind
        f = font(10, QFont.Medium)
        fm = QFontMetrics(f)
        width = min(self.parent().width() - 60, fm.horizontalAdvance(text) + 70)
        lines = max(1, fm.boundingRect(0, 0, width - 60, 1000, Qt.TextWordWrap, text).height() // fm.height())
        self.resize(width, 24 + lines * fm.height())
        self.reposition()
        self.show()
        self.raise_()
        self._fade(1)
        self.timer.start(ms)

    def reposition(self):
        par = self.parent()
        self.move((par.width() - self.width()) // 2, par.height() - self.height() - 26)

    def _fade(self, target):
        self.anim.stop()
        self.anim.setStartValue(self.effect.opacity())
        self.anim.setEndValue(target)
        if target == 0:
            self.anim.finished.connect(self._hide_once)
        self.anim.start()

    def _hide_once(self):
        self.anim.finished.disconnect(self._hide_once)
        if self.effect.opacity() == 0:
            self.hide()

    def paintEvent(self, _e):
        t = theme.current()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        p.fillPath(rounded(r, 12), QColor("#1f2633" if t.dark else "#1b2230"))
        color = {"info": t.accent, "warn": t.warning, "error": t.danger, "ok": t.success}.get(self.kind, t.accent)
        p.fillPath(rounded(QRectF(r.left() + 12, r.center().y() - 5, 10, 10), 5), QColor(color))
        p.setPen(QColor("#f3f5f9"))
        p.setFont(font(10, QFont.Medium))
        p.drawText(r.adjusted(34, 0, -14, 0), Qt.AlignVCenter | Qt.TextWordWrap, self.text_)
        p.end()


# --------------------------------------------------------------------------- Fortschrittsring
class ProgressRing(QWidget):
    """Ring mit Fingerabdruck in der Mitte; Farbe zeigt Erfolg/Fehler."""

    def __init__(self, icon_name: str = "fingerprint", parent=None):
        super().__init__(parent)
        self.icon_name = icon_name
        self.value = 0.0  # 0..1; <0 = unbestimmt (dreht sich)
        self.state = "busy"  # busy | ok | error
        self._spin = 0
        self._timer = QTimer(self, interval=16)
        self._timer.timeout.connect(self._tick)
        self._timer.start()
        self.setFixedSize(150, 150)

    def _tick(self):
        self._spin = (self._spin + 4) % 360
        if self.value < 0 and self.state == "busy":
            self.update()

    def set_progress(self, value: float):
        self.value = value
        if value < 0 and self.state == "busy":
            self._timer.start()
        else:
            self._timer.stop()
        self.update()

    def restart(self):
        """Zurück auf „arbeitet …“ (drehender Ring)."""
        self.state = "busy"
        self.set_progress(-1)

    def set_state(self, state: str):
        self.state = state
        if state != "busy":
            self._timer.stop()
        self.update()

    def paintEvent(self, _e):
        t = theme.current()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(9, 9, -9, -9)
        p.setPen(QPen(QColor(t.surface2), 9, Qt.SolidLine, Qt.RoundCap))
        p.drawEllipse(r)
        color = {"ok": t.success, "error": t.danger}.get(self.state, t.accent)
        p.setPen(QPen(QColor(color), 9, Qt.SolidLine, Qt.RoundCap))
        if self.state != "busy":
            p.drawEllipse(r)
        elif self.value < 0:
            p.drawArc(r, int((90 - self._spin) * 16), int(-90 * 16))
        elif self.value > 0:
            p.drawArc(r, 90 * 16, int(-360 * 16 * min(1.0, self.value)))
        name = {"ok": "check", "error": "x"}.get(self.state, self.icon_name)
        icons.paint(p, name, r.adjusted(34, 34, -34, -34), color, 1.8)
        p.end()


# --------------------------------------------------------------------------- Szenen-Vorschau
def paint_scene_thumb(p: QPainter, rect: QRectF, scene: dict | None, layout: str | None = None,
                      numbers: bool = False):
    """Schematische Vorschau einer Szene: Felder in der Farbe ihrer Quelle, mit Symbol."""
    t = theme.current()
    p.save()
    p.setRenderHint(QPainter.Antialiasing)
    bg = QColor((scene or {}).get("background", "#000000")) if scene else QColor(t.surface2)
    if scene is None:
        bg = t.mix(t.surface2, t.border, 0.5)
    p.fillPath(rounded(rect, 8), bg)
    slots = (scene or {}).get("slots", [])
    lay = layout or (scene or {}).get("layout", "vollbild")
    for i, (x, y, w, h, _name) in enumerate(layout_slots(lay)):
        cell = QRectF(rect.left() + x * rect.width(), rect.top() + y * rect.height(),
                      w * rect.width(), h * rect.height()).adjusted(2, 2, -2, -2)
        slot = slots[i] if i < len(slots) else None
        if slot:
            color = QColor(theme.SOURCE_COLORS.get(slot.get("type"), t.muted))
            fill = QColor(color)
            fill.setAlphaF(0.85)
            p.fillPath(rounded(cell, 5), fill)
            side = min(cell.width(), cell.height()) * 0.45
            if side >= 8:
                icons.paint(p, icons.SOURCE_ICONS.get(slot.get("type"), "monitor"),
                            QRectF(cell.center().x() - side / 2, cell.center().y() - side / 2, side, side),
                            "#ffffff", 2.2)
        else:
            palette = ["#3b82f6", "#f59e0b", "#10b981", "#ec4899"]
            color = QColor(palette[i % 4]) if numbers else QColor(t.muted)
            fill = QColor(color)
            fill.setAlphaF(0.85 if numbers else 0.18)
            p.fillPath(rounded(cell, 5), fill)
            if numbers and min(cell.width(), cell.height()) > 12:
                p.setPen(QColor("#ffffff"))
                p.setFont(font(9, QFont.Bold))
                p.drawText(cell, Qt.AlignCenter, str(i + 1))
            elif not numbers:
                pen = QPen(QColor(t.muted), 1, Qt.DashLine)
                p.setPen(pen)
                p.drawPath(rounded(cell, 5))
    p.restore()


class SceneCard(HoverMixin, QAbstractButton):
    double_clicked = Signal()

    def __init__(self, scene: dict, parent=None):
        super().__init__(parent)
        self.scene = scene
        self.live = False
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(236, 200)
        self._init_hover()

    hover = Property(float, HoverMixin._get_hover, HoverMixin._set_hover)

    def mouseDoubleClickEvent(self, e):
        self.double_clicked.emit()
        super().mouseDoubleClickEvent(e)

    def paintEvent(self, _e):
        t = theme.current()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(1.5, 1.5, -1.5, -1.5)
        p.fillPath(rounded(r, 14), t.mix(t.surface, t.surface2, 0.9 * self._hover))
        border = QColor(t.accent) if self.isChecked() else QColor(t.border)
        p.setPen(QPen(border, 2 if self.isChecked() else 1))
        p.drawPath(rounded(r, 14))
        thumb = QRectF(r.left() + 12, r.top() + 12, r.width() - 24, (r.width() - 24) * 9 / 16)
        paint_scene_thumb(p, thumb, self.scene)
        p.setPen(QColor(t.text))
        p.setFont(font(11, QFont.DemiBold))
        fm = QFontMetrics(p.font())
        name = fm.elidedText(self.scene["name"], Qt.ElideRight, int(r.width() - 24))
        p.drawText(QRectF(r.left() + 12, thumb.bottom() + 8, r.width() - 24, 22), Qt.AlignLeft | Qt.AlignVCenter,
                   name)
        filled = sum(1 for s in self.scene.get("slots", []) if s)
        p.setPen(QColor(t.muted))
        p.setFont(font(9))
        p.drawText(QRectF(r.left() + 12, thumb.bottom() + 30, r.width() - 24, 18), Qt.AlignLeft | Qt.AlignVCenter,
                   f"{filled} Quelle{'n' if filled != 1 else ''}")
        if self.live:
            pill = QRectF(thumb.right() - 58, thumb.top() + 8, 50, 20)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(t.success))
            p.drawRoundedRect(pill, 10, 10)
            p.setPen(QColor("#ffffff"))
            p.setFont(font(8, QFont.Bold))
            p.drawText(pill, Qt.AlignCenter, "LIVE")
        p.end()


class EmptyState(QWidget):
    """Hinweis, wenn eine Liste leer ist (z. B. noch keine Szene)."""

    def __init__(self, icon_name: str, title: str, text: str, action: QPushButton | None = None, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignCenter)
        lay.setSpacing(8)
        ic = QLabel()
        ic.setPixmap(_chip_pixmap(icon_name, theme.current().accent, 64))
        ic.setAlignment(Qt.AlignCenter)
        tl = QLabel(title)
        tl.setFont(font(14, QFont.Bold))
        tl.setAlignment(Qt.AlignCenter)
        tx = QLabel(text)
        tx.setObjectName("Muted")
        tx.setAlignment(Qt.AlignCenter)
        tx.setWordWrap(True)
        lay.addWidget(ic)
        lay.addWidget(tl)
        lay.addWidget(tx)
        if action is not None:
            row = QHBoxLayout()
            row.addStretch(1)
            row.addWidget(action)
            row.addStretch(1)
            lay.addLayout(row)


class Banner(QWidget):
    """Hinweiszeile mit farbigem Symbol (ok / warn / info / busy)."""

    def __init__(self, text: str = "", kind: str = "info", parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.setAttribute(Qt.WA_StyledBackground, True)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(12)
        self.icon = QLabel()
        self.icon.setFixedSize(36, 36)
        self.label = QLabel()
        self.label.setWordWrap(True)
        self.label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lay.addWidget(self.icon, 0, Qt.AlignTop)
        lay.addWidget(self.label, 1)
        self.set(text, kind)

    def set(self, text: str, kind: str = "info"):
        t = theme.current()
        color, name = {"ok": (t.success, "check"), "warn": (t.warning, "alert"), "error": (t.danger, "x"),
                       "busy": (t.accent, "refresh")}.get(kind, (t.accent, "info"))
        self.icon.setPixmap(_chip_pixmap(name, color, 36))
        self.label.setText(text)
