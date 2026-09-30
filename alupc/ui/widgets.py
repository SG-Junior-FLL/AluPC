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
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetrics, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QAbstractButton,
    QBoxLayout,
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


# Symbol je Seitenkopf (automatisch nach Titel – so bekommen alle Dialoge ein einheitliches Aussehen)
PAGE_ICONS = {"Setup": "sliders", "Meine Szenen": "scenes", "Fingerabdruck": "fingerprint", "Mediathek": "image",
              "Handy auf Monitor 2": "phone", "Website anzeigen": "globe", "Programm auf Monitor 2": "window",
              "Bildschirmschoner": "moon", "Quelle wählen": "plus", "Startseite anpassen": "edit",
              "Eigene Kachel": "plus", "Fingerabdruck einrichten": "fingerprint", "Neue Szene": "scenes",
              "Szene bearbeiten": "scenes"}


def menu_header(menu, text: str) -> None:
    """Kleine Überschrift in einem Menü (z. B. „HINTERGRUND“) – gliedert längere Menüs.
    Ein normaler, ausgegrauter Eintrag (kein eingebettetes Widget: das vertragen Taskleisten-Menüs nicht)."""
    action = menu.addAction(text.upper())
    action.setEnabled(False)
    action.setData("header")
    f = action.font()
    f.setPointSizeF(max(7.0, f.pointSizeF() * 0.8 if f.pointSizeF() > 0 else 8.0))
    f.setBold(True)
    f.setLetterSpacing(QFont.PercentageSpacing, 108)
    action.setFont(f)


def mark_current(action, on: bool) -> None:
    """Aktuelle Auswahl in einem Menü: fett und mit Haken am Ende (auch bei Einträgen mit Symbol sichtbar)."""
    f = action.font()
    f.setBold(bool(on))
    action.setFont(f)
    text = action.text().removesuffix("  ✓")
    action.setText(text + "  ✓" if on else text)


def page_header(title: str, subtitle: str = "", icon_name: str | None = None) -> QWidget:
    w = QWidget()
    row = QHBoxLayout(w)
    row.setContentsMargins(0, 0, 0, 8)
    row.setSpacing(14)
    icon_name = icon_name or PAGE_ICONS.get(title)
    if icon_name:
        chip = QLabel()
        chip.setObjectName("PageIcon")
        chip.setFixedSize(46, 46)
        chip.setAlignment(Qt.AlignCenter)
        chip.setPixmap(icons.pixmap(icon_name, "#ffffff", 24))
        row.addWidget(chip, 0, Qt.AlignTop)
    col = QVBoxLayout()
    col.setSpacing(2)
    t = QLabel(title)
    t.setObjectName("PageTitle")
    col.addWidget(t)
    if subtitle:
        s = QLabel(subtitle)
        s.setObjectName("PageSubtitle")
        s.setWordWrap(True)
        col.addWidget(s)
    row.addLayout(col, 1)
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
def _partner(color: QColor) -> QColor:
    """Nachbarfarbe für zweifarbige Verläufe (Farbton ~28° weiter, etwas dunkler)."""
    h, s, v, a = color.getHsv()
    if h < 0:  # Grau
        return color.darker(115)
    return QColor.fromHsv((h + 28) % 360, min(255, s + 10), max(0, int(v * 0.9)), a)


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
        self.setMinimumSize(QSize(160, 118))
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setToolTip(subtitle)
        self._init_hover()
        self.clicked.connect(self._show_menu)

    hover = Property(float, HoverMixin._get_hover, HoverMixin._set_hover)

    def set_menu(self, menu, split: bool = False):
        theme.round_popup(menu)
        self.menu = menu
        self.split = split
        self.update()

    def menu_zone(self) -> QRectF:
        """Pfeil oben rechts (großzügige Klickfläche)."""
        return QRectF(self.width() - 50, 0, 50, 50)

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
        return QSize(190, 118)

    def paintEvent(self, _e):
        """Schnellzugriff-Karte: Symbol oben links, Pfeil oben rechts, Titel unten.
        Aktiv: ganze Karte in der Kachelfarbe (weiße Schrift) – auf einen Blick zu sehen, was läuft."""
        t = theme.current()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(2, 2, -2, -3)
        radius = 18
        accent = QColor(t.danger if self.alert else (self.color or t.accent))
        on = self.active or self.alert
        if not t.dark:  # hell: ganz leichter Schatten, damit die Karte sich abhebt
            shade = QColor(15, 23, 42, int(9 + 14 * self._hover))
            p.fillPath(rounded(r.adjusted(0, 2, 0, 2), radius), shade)
        if on:
            fill = QLinearGradient(r.topLeft(), r.bottomRight())
            fill.setColorAt(0, accent.lighter(108 + int(6 * self._hover)))
            fill.setColorAt(1, accent.darker(108))
            p.fillPath(rounded(r, radius), fill)
        else:
            p.fillPath(rounded(r, radius), t.mix(t.surface, t.surface2, 0.6 * self._hover))
            p.setPen(QPen(t.mix(t.border, accent.name(), 0.4 * self._hover), 1.0))
            p.setBrush(Qt.NoBrush)
            p.drawPath(rounded(r.adjusted(0.5, 0.5, -0.5, -0.5), radius))
        if self.isDown():
            p.fillPath(rounded(r, radius), QColor(0, 0, 0, 26))

        pad = 14
        text_col = QColor("#ffffff") if on else QColor(t.text)
        sub_col = QColor(255, 255, 255, 200) if on else QColor(t.muted)
        # Symbol oben links
        chip = QRectF(r.left() + pad, r.top() + pad, 38, 38)
        p.setPen(Qt.NoPen)
        if on:
            p.setBrush(QColor(255, 255, 255, 46))
            icon_col = "#ffffff"
        else:
            soft = QColor(accent)
            soft.setAlphaF((0.17 if t.dark else 0.12) + 0.06 * self._hover)
            p.setBrush(soft)
            icon_col = (t.mix(accent.name(), "#ffffff", 0.25) if t.dark else accent.darker(112)).name()
        p.drawRoundedRect(chip, 11, 11)
        icons.paint(p, self.icon_name, chip.adjusted(9, 9, -9, -9), icon_col, 2.0)

        # Pfeil oben rechts (öffnet das Menü); dahinter beim Drüberfahren eine ruhige Fläche
        top_right = r.right() - pad + 4
        if self.menu is not None:
            cx, cy = r.right() - 24, chip.center().y()
            if self.split:
                ring = QColor(255, 255, 255, 40) if on else QColor(t.text)
                if not on:
                    ring.setAlphaF(0.05 + 0.06 * self._hover)
                p.setPen(Qt.NoPen)
                p.setBrush(ring)
                p.drawEllipse(QPointF(cx, cy), 14, 14)
            p.setPen(QPen(text_col if on else QColor(t.mix(t.muted, t.text, self._hover)), 1.8, Qt.SolidLine,
                          Qt.RoundCap, Qt.RoundJoin))
            p.drawPolyline([QPointF(cx - 4, cy - 2), QPointF(cx, cy + 2), QPointF(cx + 4, cy - 2)])
            top_right = cx - 20
        # Zustand (z. B. AKTIV, LÄUFT) als kleines Etikett neben dem Pfeil
        if self.badge:
            f = font(7, QFont.Bold)
            p.setFont(f)
            bw = QFontMetrics(f).horizontalAdvance(self.badge) + 14
            badge = QRectF(top_right - bw, chip.center().y() - 9, bw, 18)
            if badge.left() > chip.right() + 6:
                p.setPen(Qt.NoPen)
                if on:
                    p.setBrush(QColor(255, 255, 255, 56))
                else:
                    tint = QColor(accent)
                    tint.setAlphaF(0.16)
                    p.setBrush(tint)
                p.drawRoundedRect(badge, 9, 9)
                p.setPen(QColor("#ffffff") if on else
                         QColor(t.mix(accent.name(), "#ffffff", 0.3) if t.dark else accent.darker(125)))
                p.drawText(badge, Qt.AlignCenter, self.badge)

        # Titel und Untertitel unten links
        width = r.width() - 2 * pad
        tf = font(11.2, QFont.DemiBold)
        p.setFont(tf)
        p.setPen(text_col)
        has_sub = bool(self.subtitle)
        title_y = r.bottom() - pad - (38 if has_sub else 22)
        title = QFontMetrics(tf).elidedText(self.title, Qt.ElideRight, int(width))
        p.drawText(QRectF(r.left() + pad, title_y, width, 22), Qt.AlignLeft | Qt.AlignVCenter, title)
        if has_sub:
            sf = font(8.8)
            p.setFont(sf)
            p.setPen(sub_col)
            sub = QFontMetrics(sf).elidedText(self.subtitle, Qt.ElideRight, int(width))
            p.drawText(QRectF(r.left() + pad, title_y + 20, width, 18), Qt.AlignLeft | Qt.AlignVCenter, sub)
        p.end()


# --------------------------------------------------------------------------- Navigation
class NavButton(HoverMixin, QAbstractButton):
    def __init__(self, icon_name: str, text: str, parent=None):
        super().__init__(parent)
        self.icon_name, self.text_ = icon_name, text
        self.compact = False
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(42)
        self._init_hover()

    hover = Property(float, HoverMixin._get_hover, HoverMixin._set_hover)

    def set_compact(self, on: bool) -> None:
        self.compact = on
        self.update()

    def paintEvent(self, _e):
        t = theme.current()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(8, 2, -8, -2)
        if self.compact:  # nur Symbol, mittig
            r = QRectF(self.rect().center().x() - 22, 2, 44, self.height() - 4)
        if self.isChecked():  # ruhig: zart getönte Fläche, Symbol und Text in der Akzentfarbe
            tint = QColor(t.accent)
            tint.setAlphaF(0.16 if t.dark else 0.11)
            p.fillPath(rounded(r, 12), tint)
            if not self.compact:  # kleiner Balken links als Markierung
                p.fillPath(rounded(QRectF(r.left() + 1, r.center().y() - 9, 3, 18), 1.5), QColor(t.accent))
        elif self._hover > 0:
            h = QColor(t.text)
            h.setAlphaF(0.06 * self._hover)
            p.fillPath(rounded(r, 12), h)
        sel = (t.mix(t.accent, "#ffffff", 0.25) if t.dark else QColor(t.accent).darker(110)).name()
        col = sel if self.isChecked() else t.muted
        if self.compact:
            icons.paint(p, self.icon_name, QRectF(r.center().x() - 10, r.center().y() - 10, 20, 20), col, 2.0)
            p.end()
            return
        icons.paint(p, self.icon_name, QRectF(r.left() + 14, r.center().y() - 10, 20, 20), col, 2.0)
        p.setPen(QColor(sel if self.isChecked() else t.text))
        p.setFont(font(10.5, QFont.DemiBold if self.isChecked() else QFont.Medium))
        p.drawText(r.adjusted(46, 0, 0, 0), Qt.AlignLeft | Qt.AlignVCenter, self.text_)
        p.end()


class MonitorCard(QWidget):
    """Seitenleiste unten: Monitor 2 als kleines Live-Bild mit Name und Zustand – auf jeder Seite sichtbar."""

    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.image = None
        self.name = ""
        self.detail = ""
        self.state = ("", "#22c55e")
        self.icon_name = "monitor"
        self.compact = False
        self.setFixedHeight(166)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Monitor 2 – Klick: zur Startseite")

    def set_compact(self, on: bool) -> None:
        """Schmale Seitenleiste: nur kleines Bild mit Zustandspunkt."""
        self.compact = on
        self.setFixedHeight(64 if on else 166)
        self.update()

    def set(self, name: str, detail: str, state: tuple[str, str], icon_name: str):
        self.name, self.detail, self.state, self.icon_name = name, detail, state, icon_name
        self.update()

    def set_image(self, image):
        self.image = image if image is not None and not image.isNull() else None
        self.update()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.clicked.emit()

    def paintEvent(self, _e):
        t = theme.current()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        r = QRectF(self.rect()).adjusted(8, 0, -8, -1)
        if self.compact:
            thumb = QRectF(r.left(), r.top() + 6, r.width(), r.width() * 9 / 16)
            path = rounded(thumb, 7)
            p.fillPath(path, QColor("#000000" if self.image is not None else t.surface2))
            if self.image is not None:
                p.save()
                p.setClipPath(path)
                p.drawImage(thumb, self.image)
                p.restore()
            else:  # ohne Live-Bild: Symbol des Inhalts statt leerer Fläche
                s_ = min(18.0, thumb.height() - 8)
                icons.paint(p, self.icon_name, QRectF(thumb.center().x() - s_ / 2, thumb.center().y() - s_ / 2,
                                                      s_, s_), t.muted, 1.6)
            p.setPen(QPen(QBrush(t.gradient(thumb, alpha=0.45)), 1.0))
            p.setBrush(Qt.NoBrush)
            p.drawPath(path)
            p.setPen(QPen(QColor(t.surface), 1.5))
            p.setBrush(QColor(self.state[1]))
            p.drawEllipse(QPointF(thumb.right() - 4, thumb.top() + 4), 4, 4)
            p.end()
            return
        # schlichte Karte mit feinem Rand
        p.fillPath(rounded(r, 16), QColor(t.surface))
        p.setPen(QPen(QColor(t.border), 1.0))
        p.drawPath(rounded(r.adjusted(0.5, 0.5, -0.5, -0.5), 16))
        thumb = QRectF(r.left() + 8, r.top() + 8, r.width() - 16, (r.width() - 16) * 9 / 16)
        path = rounded(thumb, 9)
        p.fillPath(path, QColor("#000000" if self.image is not None else t.bg))
        if self.image is not None:
            p.save()
            p.setClipPath(path)
            iw, ih = self.image.width(), self.image.height()
            scale = min(thumb.width() / iw, thumb.height() / ih)
            target = QRectF(0, 0, iw * scale, ih * scale)
            target.moveCenter(thumb.center())
            p.drawImage(target, self.image)
            p.restore()
        else:
            s_ = 30
            icons.paint(p, self.icon_name, QRectF(thumb.center().x() - s_ / 2, thumb.center().y() - s_ / 2, s_, s_),
                        t.muted, 1.8)
        label, color = self.state
        if label:  # Zustand als kleines Etikett oben links im Bild
            f = font(7, QFont.Bold)
            p.setFont(f)
            bw = QFontMetrics(f).horizontalAdvance(label) + 20
            badge = QRectF(thumb.left() + 6, thumb.top() + 6, bw, 16)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(0, 0, 0, 150))
            p.drawRoundedRect(badge, 8, 8)
            p.setBrush(QColor(color))
            p.drawEllipse(QPointF(badge.left() + 8, badge.center().y()), 3, 3)
            p.setPen(QColor("#ffffff"))
            p.drawText(badge.adjusted(14, 0, 0, 0), Qt.AlignLeft | Qt.AlignVCenter, label)
        y = thumb.bottom() + 6
        p.setPen(QColor(t.text))
        tf = font(9.5, QFont.DemiBold)
        p.setFont(tf)
        p.drawText(QRectF(r.left() + 10, y, r.width() - 20, 18), Qt.AlignLeft | Qt.AlignVCenter,
                   QFontMetrics(tf).elidedText(self.name, Qt.ElideRight, int(r.width() - 20)))
        p.setPen(QColor(t.muted))
        sf = font(8)
        p.setFont(sf)
        p.drawText(QRectF(r.left() + 10, y + 17, r.width() - 20, 16), Qt.AlignLeft | Qt.AlignVCenter,
                   QFontMetrics(sf).elidedText(self.detail, Qt.ElideRight, int(r.width() - 20)))
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
        self._lay = lay
        self._narrow = False  # vom Hauptfenster: sehr schmales Fenster
        self._mode = ""

    def set_compact(self, on: bool) -> None:
        """Sehr schmales Fenster: Vorschau oben, Text darunter. Sonst wählt die Karte ihre Form selbst."""
        self._narrow = on
        self._auto()

    def minimumSizeHint(self):
        # Nie breiter verlangen als die schmale Form – sonst ragt die Startseite rechts über den Rand,
        # bevor die Karte auf „nur Symbole“ umschalten kann
        hint = super().minimumSizeHint()
        return QSize(min(hint.width(), 300), hint.height())

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._auto()

    def showEvent(self, e):
        super().showEvent(e)
        self._recheck()
        QTimer.singleShot(0, self._recheck)  # nach dem ersten Layout (Stylesheet angewendet) nochmal

    def _recheck(self):
        self._mode = ""
        self._auto()

    def _chips(self):
        for i in range(self.chips.count()):
            chip = self.chips.itemAt(i).widget()
            if chip is not None:
                if chip.property("full_text") is None:
                    chip.setProperty("full_text", chip.text())
                full = _chip_width(chip)
                old = int(chip.property("full_w") or 0)
                if full > old:
                    chip.setProperty("full_w", full)
                    if old:  # breiter als gedacht → gleich nochmal entscheiden
                        QTimer.singleShot(0, self._recheck)
                yield chip

    def _full_width(self) -> int:
        """So breit wäre die Karte nebeneinander mit beschrifteten Schnellschaltern."""
        chips = list(self._chips())
        chip_w = sum(int(c.property("full_w") or 0) or
                     QFontMetrics(c.font()).horizontalAdvance(c.property("full_text") or "") + 64 for c in chips)
        chip_w += self.chips.spacing() * max(0, len(chips) - 1)
        actions = max((self.actions.itemAt(i).widget().sizeHint().width() for i in range(self.actions.count())
                       if self.actions.itemAt(i).widget() is not None
                       and not self.actions.itemAt(i).widget().isHidden()), default=0)
        m = self._lay.contentsMargins()
        return m.left() + m.right() + 272 + self._lay.spacing() * 2 + chip_w + actions + 24  # etwas Luft

    def _auto(self) -> None:
        """Breit: nebeneinander, Schalter mit Namen · mittel: nebeneinander, Schalter nur Symbol ·
        schmal: Vorschau oben, Text darunter."""
        need = max(self._full_width(), getattr(self, "_full_min", 0))
        mode = "schmal" if self._narrow else ("voll" if self.width() >= need else "mittel")
        if mode == self._mode:
            return
        self._mode = mode
        narrow = mode == "schmal"
        self._lay.setDirection(QBoxLayout.TopToBottom if narrow else QBoxLayout.LeftToRight)
        self._lay.setAlignment(self.preview, Qt.AlignHCenter if narrow else Qt.Alignment())
        self.preview.setFixedSize(QSize(240, 135) if narrow else QSize(272, 153))
        self.title.setFont(font(14 if narrow else 17, QFont.Bold))
        for chip in self._chips():  # Schnellschalter: knapp nur Symbol (Name als Tooltip)
            chip.setText(chip.property("full_text") if mode == "voll" else "")
            chip.setToolTip(chip.property("full_text"))
            # selbst gerechnete Mindestbreite: Qt vergisst mit Stylesheet den Abstand Symbol–Text
            chip.setMinimumWidth(int(chip.property("full_w")) if mode == "voll" else 0)
        if mode == "voll":
            QTimer.singleShot(0, self._verify_fit)

    def _verify_fit(self) -> None:
        """Nachmessen: Passen die Schalter mit Namen wirklich? Sonst wurden sie abgeschnitten („Bild-in-Bil…“) –
        dann nur Symbole, bis die Karte breiter ist als jetzt."""
        if self._mode != "voll" or not self.isVisible():
            return
        chips = [c for c in self._chips() if c.isVisible()]
        squeezed = any(c.width() < int(c.property("full_w") or 0) - 1 for c in chips)
        touching = any(a.geometry().right() + 4 > b.geometry().left() for a, b in zip(chips, chips[1:]))
        if squeezed or touching:
            self._full_min = self.width() + 1
            self._mode = ""
            self._auto()

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


def _chip_width(chip) -> int:
    """Breite eines Schnellschalters mit Namen: Text (halbfett) + Symbol + Abstand + Innenrand + Rand."""
    f = QFont(chip.font())
    f.setWeight(QFont.DemiBold)
    text = QFontMetrics(f).horizontalAdvance(chip.property("full_text") or chip.text())
    return text + chip.iconSize().width() + 8 + 2 * 14 + 2 + 6  # +6 Luft (Schriftglättung je System)


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
        self._timer = QTimer(self, interval=33)  # dreht nur, solange sichtbar und „busy“ (siehe show/hide)
        self._timer.timeout.connect(self._tick)
        self.setFixedSize(150, 150)

    def showEvent(self, e):
        if self.value < 0 and self.state == "busy":
            self._timer.start()
        super().showEvent(e)

    def hideEvent(self, e):
        self._timer.stop()
        super().hideEvent(e)

    def _tick(self):
        self._spin = (self._spin + 8) % 360
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


class SectionHeader(QWidget):
    """Überschrift eines Startseiten-Bereichs: Pfeil, Name, Anzahl, Linie – Klick klappt ein/aus."""

    toggled = Signal(bool)  # True = eingeklappt

    def __init__(self, name: str, count: int = 0, collapsed: bool = False, tiles=None, parent=None):
        super().__init__(parent)
        self.name, self.count, self.collapsed = name, count, collapsed
        self.tiles = list(tiles or [])  # (Symbol, Farbe) – eingeklappt als Mini-Symbole zu sehen
        self._hover = False
        self.setFixedHeight(34)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Klick: ein-/ausklappen")
        self.setAttribute(Qt.WA_Hover, True)

    def set(self, name: str, count: int, collapsed: bool) -> None:
        self.name, self.count, self.collapsed = name, count, collapsed
        self.update()

    def enterEvent(self, e):
        self._hover = True
        self.update()

    def leaveEvent(self, e):
        self._hover = False
        self.update()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.collapsed = not self.collapsed
            self.update()
            self.toggled.emit(self.collapsed)

    def paintEvent(self, _e):
        t = theme.current()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        h = self.height()
        if self._hover:
            p.fillPath(rounded(QRectF(self.rect()).adjusted(0, 2, 0, -2), 9), QColor(t.surface2))
        # Pfeil: ▾ offen, ▸ eingeklappt
        cx, cy, s = 14.0, h / 2, 4.5
        pen = QPen(QColor(t.accent if self._hover else t.muted), 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        p.setPen(pen)
        if self.collapsed:
            p.drawPolyline([QPointF(cx - s / 2, cy - s), QPointF(cx + s / 2, cy), QPointF(cx - s / 2, cy + s)])
        else:
            p.drawPolyline([QPointF(cx - s, cy - s / 2), QPointF(cx, cy + s / 2), QPointF(cx + s, cy - s / 2)])
        f = font(8.8, QFont.Bold)
        f.setLetterSpacing(QFont.PercentageSpacing, 110)
        p.setFont(f)
        p.setPen(QColor(t.text if self._hover else t.muted))
        x = 30
        label = self.name.upper()
        width = QFontMetrics(f).horizontalAdvance(label)
        p.drawText(QRectF(x, 0, width + 2, h), Qt.AlignVCenter | Qt.AlignLeft, label)
        x += width + 8
        cf = font(8.5)
        p.setFont(cf)
        p.setPen(QColor(t.muted))
        count = str(self.count)
        cw = QFontMetrics(cf).horizontalAdvance(count)
        p.drawText(QRectF(x, 0, cw + 2, h), Qt.AlignVCenter | Qt.AlignLeft, count)
        pill = QRectF(x, h / 2 - 9, cw, 18)
        x = pill.right() + 12
        # eingeklappt: die Kacheln als kleine farbige Symbole (bis 10)
        if self.collapsed and self.tiles:
            size = 22
            for icon_name, color in self.tiles[:10]:
                if x + size > self.width() - 40:
                    break
                bg = QColor(color or t.accent)
                bg.setAlphaF(0.2)
                p.setPen(Qt.NoPen)
                p.setBrush(bg)
                p.drawRoundedRect(QRectF(x, h / 2 - size / 2, size, size), 7, 7)
                icons.paint(p, icon_name, QRectF(x + 4, h / 2 - size / 2 + 4, size - 8, size - 8), color or t.accent,
                            1.8)
                x += size + 5
            x += 7
        p.end()


def fade_in(widget, ms: int = 220, delay: int = 0, dy: int = 0) -> None:
    """Weiches Einblenden (optional leicht von unten hochgleitend). Der Effekt wird danach wieder entfernt –
    Grafikeffekte kosten sonst dauerhaft Leistung (und vertragen sich nicht mit Web-Ansichten)."""
    from PySide6.QtCore import QParallelAnimationGroup, QPoint, QSequentialAnimationGroup

    if widget is None or not widget.isVisible() or theme_reduced_motion():
        return
    effect = QGraphicsOpacityEffect(widget)
    effect.setOpacity(0.0)
    widget.setGraphicsEffect(effect)
    fade = QPropertyAnimation(effect, b"opacity", widget)
    fade.setDuration(ms)
    fade.setStartValue(0.0)
    fade.setEndValue(1.0)
    fade.setEasingCurve(QEasingCurve.OutCubic)
    group = QParallelAnimationGroup(widget)
    group.addAnimation(fade)
    if dy and widget.parentWidget() is not None and widget.parentWidget().layout() is None:
        end = widget.pos()
        slide = QPropertyAnimation(widget, b"pos", widget)
        slide.setDuration(ms + 60)
        slide.setStartValue(end + QPoint(0, dy))
        slide.setEndValue(end)
        slide.setEasingCurve(QEasingCurve.OutBack)
        group.addAnimation(slide)
    seq = QSequentialAnimationGroup(widget)
    if delay:
        seq.addPause(delay)
    seq.addAnimation(group)

    def done():
        try:
            if widget.graphicsEffect() is effect:
                widget.setGraphicsEffect(None)
        except RuntimeError:
            pass

    seq.finished.connect(done)
    seq.start(QPropertyAnimation.DeleteWhenStopped)


def theme_reduced_motion() -> bool:
    """Animationen aus (Einstellung „Animationen“ oder Test-/Offscreen-Umgebung ohne echten Bildschirm)."""
    import os

    from .. import perf

    return os.environ.get("ALUPC_NO_ANIMATION") == "1" or perf._mode == "sparsam"


def animate_height(widget, show: bool, ms: int = 240) -> None:
    """Ein-/Ausklappen mit Animation (maximale Höhe gleitet)."""
    if theme_reduced_motion():
        widget.setVisible(show)
        return
    start = widget.height() if widget.isVisible() else 0
    target = widget.sizeHint().height() if show else 0
    widget.setMaximumHeight(start)
    widget.setVisible(True)
    anim = QPropertyAnimation(widget, b"maximumHeight", widget)
    anim.setDuration(ms)
    anim.setStartValue(start)
    anim.setEndValue(max(target, 1) if show else 0)
    anim.setEasingCurve(QEasingCurve.OutCubic if show else QEasingCurve.InCubic)

    def done():
        try:
            widget.setMaximumHeight(16777215)
            widget.setVisible(show)
        except RuntimeError:
            pass

    anim.finished.connect(done)
    anim.start(QPropertyAnimation.DeleteWhenStopped)
