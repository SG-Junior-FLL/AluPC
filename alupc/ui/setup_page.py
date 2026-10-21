"""Setup: Monitore (Auflösung, Hz, Anordnung) und Einstellungen von AluPC."""

from __future__ import annotations


from PySide6.QtCore import QEvent, QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QGuiApplication, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QMessageBox,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QScrollArea,
    QSlider,
    QSpinBox,
    QStackedWidget,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QVBoxLayout,
    QWidget,
)

from ..config import HOTKEY_LABELS
from ..platform import IS_WINDOWS, autostart, session_info
from ..platform.base import ROTATIONS, clone_outputs, place, side_of
from . import icons, theme
from .util import error_box, run_async
from .hotkey_edit import HotkeyButton
from .reset_page import reset_group
from .sync_page import backup_group, sync_group
from .widgets import FlowLayout, button, flow_row, font, rounded

SIDES = [("right", "rechts vom Hauptmonitor"), ("left", "links vom Hauptmonitor"),
         ("above", "über dem Hauptmonitor"), ("below", "unter dem Hauptmonitor"),
         ("mirror", "gespiegelt (gleiche Position)")]


class ConfirmDialog(QDialog):
    """„Einstellungen behalten?“ – ohne Antwort wird nach 15 Sekunden zurückgesetzt."""

    def __init__(self, parent=None, seconds: int = 15):
        super().__init__(parent)
        self.setWindowTitle("Einstellungen behalten?")
        self.remaining = seconds
        self.label = QLabel()
        self.label.setWordWrap(True)
        buttons = QDialogButtonBox()
        keep = buttons.addButton("Behalten", QDialogButtonBox.AcceptRole)
        buttons.addButton("Zurücksetzen", QDialogButtonBox.RejectRole)
        keep.setDefault(True)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay = QVBoxLayout(self)
        lay.addWidget(self.label)
        lay.addWidget(buttons)
        self.timer = QTimer(self, interval=1000)
        self.timer.timeout.connect(self._tick)
        self.timer.start()
        self._update()

    def _update(self):
        self.label.setText(f"Alles richtig? Sonst zurück in {self.remaining} s.")

    def _tick(self):
        self.remaining -= 1
        if self.remaining <= 0:
            self.reject()
        else:
            self._update()


class IdentifyWindow(QLabel):
    def __init__(self, screen, number: int):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setText(f"{number}\n{screen.name()}")
        font = QFont()
        font.setPixelSize(90)
        font.setBold(True)
        self.setFont(font)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet(f"background:{theme.current().accent}; color:white; border-radius:10px;")
        self.resize(360, 260)
        geo = screen.geometry()
        self.move(geo.center().x() - 180, geo.center().y() - 130)
        self.create()
        if self.windowHandle():
            self.windowHandle().setScreen(screen)


class Swatch(QAbstractButton):
    """Runder Farbknopf für die Akzentfarbe."""

    def __init__(self, color: str, tooltip: str, parent=None):
        super().__init__(parent)
        self.color = color
        self.setCheckable(True)
        self.setToolTip(tooltip)
        self.setFixedSize(34, 34)
        self.setCursor(Qt.PointingHandCursor)

    def paintEvent(self, _e):
        t = theme.current()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(3, 3, -3, -3)
        if self.isChecked():
            p.setPen(QPen(QColor(t.text), 2.5))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(QRectF(self.rect()).adjusted(1.5, 1.5, -1.5, -1.5))
            r = r.adjusted(3, 3, -3, -3)
        p.setPen(Qt.NoPen)
        if getattr(self, "brand", False):  # AluPC-Theme: das Logo selbst als Farbknopf
            p.drawPixmap(r.toRect(), icons.app_icon().pixmap(int(r.width()), int(r.width())))
            p.end()
            return
        p.setBrush(QColor(self.color))
        p.drawEllipse(r)
        if getattr(self, "system", False):  # „Wie das System“: kleines Monitor-Symbol in der Systemfarbe
            s = int(r.width() * 0.62)
            icons.icon("monitor", "#ffffff", s).paint(p, int(r.center().x() - s / 2), int(r.center().y() - s / 2), s, s)
        p.end()


class StyleCard(QAbstractButton):
    """Auswahl des Stils (Normal / Technisch / Holz): kleine Skizze der Startseite im jeweiligen Stil."""

    def __init__(self, style: str, config, parent=None):
        super().__init__(parent)
        self.style_key = style
        self.config = config
        self.setCheckable(True)
        self.setAutoExclusive(True)
        self.setFixedSize(200, 168)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(theme.STYLE_INFO[style])
        self.setAccessibleName(f"Stil {theme.STYLES[style]}")

    def paintEvent(self, _e):
        from .widgets import paint_led

        cur = theme.current()
        accent = self.config["appearance"].get("accent", "alupc")
        a = self.config["appearance"]
        t = theme.make_theme("dunkel" if cur.dark else "hell", accent, self.style_key,
                             a.get("wood", theme.DEFAULT_WOOD), custom={**a, "font": 100})
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        outer = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        p.setPen(QPen(QColor(cur.accent) if self.isChecked() else QColor(cur.border), 2 if self.isChecked() else 1))
        p.setBrush(QColor(cur.surface))
        p.drawRoundedRect(outer, 8, 8)
        win = QRectF(outer.left() + 9, outer.top() + 9, outer.width() - 18, 100)
        p.save()
        clip = QPainterPath()
        clip.addRoundedRect(win, 4, 4)
        p.setClipPath(clip)
        theme.paint_backdrop(p, win, t)
        # Seitenleiste
        side = QRectF(win.left(), win.top(), 26, win.height())
        if t.wood:
            p.fillRect(side, QColor(0, 0, 0, 70))
        else:
            p.fillRect(side, QColor(t.surface if t.technical else t.mix(t.bg, "#000000", 0.18 if t.dark else 0.04)))
        mark = QRectF(side.left() + 4, side.top() + 14, 18, 10)
        if t.wood:
            theme.paint_panel(p, _round(mark, 2), mark, t)
        else:
            tint = QColor(t.accent)
            tint.setAlphaF(0.35)
            p.fillPath(_round(mark, t.radii[1] / 3), tint)
        # Bild von Monitor 2 und zwei Regler
        prev = QRectF(win.left() + 34, win.top() + 8, 70, 40)
        if t.wood:
            p.fillPath(_round(prev, 3), QColor("#1a1a1b"))
            prev = prev.adjusted(3, 3, -3, -3)
        p.fillPath(_round(prev, t.radii[0] / 3), QColor("#000000"))
        p.setPen(QPen(QColor(t.live), 1.4))
        p.setBrush(Qt.NoBrush)
        p.drawPath(_round(prev, t.radii[0] / 3))
        for i in range(2):
            fx = win.right() - 30 + i * 13
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#151515" if t.wood else t.surface2))
            p.drawRect(QRectF(fx, win.top() + 10, 3, 38))
            p.setBrush(QColor(t.accent))
            if t.wood:
                cap = QRectF(fx - 5, win.top() + 22 + i * 8, 13, 7)
                theme.paint_plate(p, _round(cap, 1.5), cap, t)
            else:
                p.drawRect(QRectF(fx, win.top() + 26 + i * 8, 3, 22 - i * 8))
        # drei Kacheln, die mittlere läuft
        colors = ["#e5484d", "#30a46c", "#f5a623"]
        for i, col in enumerate(colors):
            r = QRectF(win.left() + 34 + i * 49, win.top() + (60 if not t.technical else 62), 44,
                       32 if not t.technical else 26)
            on = i == 1
            path = _round(r, t.radii[0] / 3)
            if t.wood:
                theme.paint_panel(p, path, r, t)
                paint_led(p, QPointF(r.left() + 7, r.top() + 7), on, t.live, 2.6)
            else:
                p.fillPath(path, QColor(t.surface))
                p.setPen(QPen(QColor(t.live) if on else QColor(t.border), 1.2 if on else 1))
                p.setBrush(Qt.NoBrush)
                p.drawPath(path)
                if t.technical and on:
                    p.fillRect(QRectF(r.left(), r.top(), 2, r.height()), QColor(t.live))
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(col))
            if t.technical:
                p.drawRect(QRectF(r.left() + 6, r.center().y() - 3, 6, 6))
            elif t.wood:
                p.drawRect(QRectF(r.left() + 14, r.top() + 4, 6, 6))
            else:
                p.drawEllipse(QRectF(r.left() + 5, r.top() + 5, 10, 10))
            p.setBrush(QColor(t.text))
            tx = r.left() + (16 if t.technical else 6)
            ty = r.center().y() - 2 if t.technical else r.bottom() - 10
            p.drawRect(QRectF(tx, ty, 20, 2.5))
            p.setBrush(QColor(t.live if on else t.muted))
            p.drawRect(QRectF(tx, ty + 5, 12, 2))
        p.restore()
        p.setPen(QPen(QColor(cur.border), 1))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(win, 4, 4)
        p.setPen(QColor(cur.text))
        p.setFont(font(10.5, QFont.DemiBold))
        p.drawText(QRectF(outer.left() + 12, win.bottom() + 10, outer.width() - 24, 18), Qt.AlignLeft | Qt.AlignVCenter,
                   theme.STYLES[self.style_key])
        p.setPen(QColor(cur.muted))
        p.setFont(font(8.8))
        p.drawText(QRectF(outer.left() + 12, win.bottom() + 28, outer.width() - 24, 16), Qt.AlignLeft | Qt.AlignVCenter,
                   QFontMetrics(font(8.8)).elidedText(theme.STYLE_INFO[self.style_key], Qt.ElideRight,
                                                     int(outer.width() - 24)))
        p.end()


class WoodSwatch(QAbstractButton):
    """Holzart zum Anklicken: echtes Stück Furnier mit Namen darunter."""

    def __init__(self, key: str, parent=None):
        super().__init__(parent)
        self.key = key
        self.setCheckable(True)
        self.setAutoExclusive(True)
        self.setFixedSize(96, 78)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(theme.WOODS[key][0])
        self.setAccessibleName(f"Holzart {theme.WOODS[key][0]}")

    def paintEvent(self, _e):
        from PySide6.QtGui import QPixmap

        cur = theme.current()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(3, 3, self.width() - 6, 50)
        path = _round(r, 6)
        p.save()
        p.setClipPath(path)
        offset = QPointF(sum(map(ord, self.key)) % 300, 40)
        p.drawTiledPixmap(r, QPixmap.fromImage(theme.wood_image(self.key, "panel")), offset)
        p.restore()
        p.setBrush(Qt.NoBrush)
        if self.isChecked():
            p.setPen(QPen(QColor(cur.accent), 2.5))
            p.drawRoundedRect(QRectF(1.5, 1.5, self.width() - 3, 53), 7, 7)
        else:
            p.setPen(QPen(QColor(0, 0, 0, 120), 1))
            p.drawPath(path)
        p.setPen(QColor(cur.text if self.isChecked() else cur.muted))
        p.setFont(font(9, QFont.DemiBold if self.isChecked() else QFont.Normal))
        p.drawText(QRectF(0, 56, self.width(), 20), Qt.AlignCenter, theme.WOODS[self.key][0])
        p.end()


def _round(rect: QRectF, radius: float):
    path = QPainterPath()
    path.addRoundedRect(rect, radius, radius)
    return path


GROUP_HEAD = 30  # Höhe der Gruppenüberschrift in der Setup-Liste


class NavDelegate(QStyledItemDelegate):
    """Setup-Liste: Bereichsname in Textfarbe, darunter kleiner und leiser, was drin ist."""

    def paint(self, p, option, index):
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        text = index.data(Qt.DisplayRole) or ""
        opt.text = ""
        group = index.data(Qt.UserRole + 1) if text else None
        t = theme.current()
        if group:  # Überschrift der Gruppe („Bildschirm“, „Werkzeuge“ …) über dem ersten Bereich
            head = QRectF(opt.rect.left() + 12, opt.rect.top() + 6, opt.rect.width() - 20, GROUP_HEAD - 8)
            p.save()
            p.setFont(font(8.2, QFont.Bold))
            p.setPen(QColor(t.muted))
            p.drawText(head, Qt.AlignLeft | Qt.AlignVCenter, group)
            p.restore()
            opt.rect = opt.rect.adjusted(0, GROUP_HEAD, 0, 0)
        style = opt.widget.style() if opt.widget else QApplication.style()
        style.drawControl(QStyle.CE_ItemViewItem, opt, p, opt.widget)
        if not text:
            return
        title, _, sub = text.partition("\n")
        r = QRectF(opt.rect).adjusted(opt.decorationSize.width() + 22, 0, -8, 0)
        p.save()
        f = font(10, QFont.DemiBold if opt.state & QStyle.State_Selected else QFont.Medium)
        p.setFont(f)
        p.setPen(QColor(t.text))
        mid = r.center().y()
        p.drawText(QRectF(r.left(), mid - 18, r.width(), 18), Qt.AlignLeft | Qt.AlignBottom,
                   QFontMetrics(f).elidedText(title, Qt.ElideRight, int(r.width())))
        f2 = font(8.5)
        p.setFont(f2)
        p.setPen(QColor(t.muted))
        p.drawText(QRectF(r.left(), mid + 1, r.width(), 16), Qt.AlignLeft | Qt.AlignTop,
                   QFontMetrics(f2).elidedText(sub, Qt.ElideRight, int(r.width())))
        p.restore()


class MonitorArrangement(QWidget):
    """Zeichnet die Monitore so, wie sie angeordnet sind; Klick wählt einen Monitor aus."""

    selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.items: list[dict] = []
        self.current = ""
        self.output_name = ""
        self.setMinimumHeight(190)
        self.setCursor(Qt.PointingHandCursor)
        self._rects: dict[str, QRectF] = {}

    def set_items(self, items: list[dict], output_name: str):
        self.items, self.output_name = items, output_name
        self.update()

    def set_current(self, name: str):
        self.current = name
        self.update()

    def mousePressEvent(self, e):
        for name, r in self._rects.items():
            if r.contains(e.position()):
                self.selected.emit(name)
                return

    def paintEvent(self, _e):
        t = theme.current()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        area = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        p.fillPath(rounded(area, 12), QColor(t.surface2))
        self._rects = {}
        if not self.items:
            p.setPen(QColor(t.muted))
            p.drawText(area, Qt.AlignCenter, "Keine Monitore erkannt")
            p.end()
            return
        min_x = min(i["x"] for i in self.items)
        min_y = min(i["y"] for i in self.items)
        max_x = max(i["x"] + i["w"] for i in self.items)
        max_y = max(i["y"] + i["h"] for i in self.items)
        inner = area.adjusted(24, 20, -24, -20)
        scale = min(inner.width() / max(1, max_x - min_x), inner.height() / max(1, max_y - min_y))
        ox = inner.left() + (inner.width() - (max_x - min_x) * scale) / 2
        oy = inner.top() + (inner.height() - (max_y - min_y) * scale) / 2
        for i, item in enumerate(sorted(self.items, key=lambda it: it["name"] == self.current)):
            r = QRectF(ox + (item["x"] - min_x) * scale, oy + (item["y"] - min_y) * scale,
                       item["w"] * scale, item["h"] * scale).adjusted(3, 3, -3, -3)
            self._rects[item["name"]] = r
            is_out = item["name"] == self.output_name
            color = QColor("#f97316") if is_out else QColor(t.accent)
            fill = QColor(color)
            fill.setAlphaF(0.22 if item["name"] == self.current else 0.12)
            p.fillPath(rounded(r, 8), QColor(t.surface))
            p.fillPath(rounded(r, 8), fill)
            p.setPen(QPen(color, 2.5 if item["name"] == self.current else 1.2))
            p.drawPath(rounded(r, 8))
            title = "Bildschirm" if is_out else ("Hauptmonitor" if item.get("primary") else item["name"])
            tf, df = font(10.5, QFont.Bold), font(8.5)
            th, dh = QFontMetrics(tf).height(), QFontMetrics(df).height()
            top = r.center().y() - (th + 2 * dh + 4) / 2
            p.setPen(QColor(t.text))
            p.setFont(tf)
            p.drawText(QRectF(r.left() + 6, top, r.width() - 12, th), Qt.AlignCenter, title)
            p.setPen(QColor(t.muted))
            p.setFont(df)
            p.drawText(QRectF(r.left() + 6, top + th + 4, r.width() - 12, dh), Qt.AlignCenter, item["name"])
            p.drawText(QRectF(r.left() + 6, top + th + 4 + dh, r.width() - 12, dh), Qt.AlignCenter, item["label"])
        p.end()


class SetupPage(QWidget):
    """Setup mit Bereichen: links die Liste, rechts der gewählte Bereich."""

    theme_changed = Signal()
    hotkeys_changed = Signal()

    SECTIONS = [
        ("monitor", "Monitore", "Auflösung und Anordnung"),
        ("pip", "Bildschirm", "Maus, Sichtschutz, Bild im Bild"),
        ("palette", "Darstellung", "Stil, Farbe, Übergänge"),
        ("moon", "Bildschirmschoner", "Wann und wie"),
        ("timer", "Timer", "Dauer und Warnfarben"),
        ("board", "Whiteboard", "Stift, Seiten, Farben"),
        ("sound", "Töne", "Klänge bei Aktionen"),
        ("keyboard", "Tastenkürzel", "Alles per Tastatur"),
        ("mic", "Sprache", "Sprachbefehle und Stimme"),
        ("phone", "Handy & Kamera", "Was das Handy darf"),
        ("sync", "Sichern & Sync", "Sichern, Windows/Linux"),
        ("fan", "RGB & Lüfter", "Licht und Temperaturen"),
        ("sliders", "Allgemein", "Start, Autostart, Hilfe"),
    ]
    # Gruppen in der Liste: erster Bereich → Überschrift
    GROUPS = {"Monitore": "Bildschirm", "Timer": "Werkzeuge", "Tastenkürzel": "Bedienung",
              "Sichern & Sync": "System"}

    def __init__(self, controller, hotkeys, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.config = controller.config
        self.hotkeys = hotkeys
        self.outputs = []
        builders = {
            "Monitore": [self._display_group],
            "Bildschirm": [self._output_group, self._privacy_group, self._pip_group],
            "Darstellung": [self._appearance_group],
            "Bildschirmschoner": [self._screensaver_group],
            "Timer": [self._timer_group],
            "Whiteboard": [self._board_group],
            "Töne": [self._sound_group],
            "Tastenkürzel": [self._hotkey_group],
            "Sprache": [self._voice_group],
            "Sichern & Sync": [lambda: sync_group(self), lambda: backup_group(self)],
            "RGB & Lüfter": [self._hardware_group],
            "Handy & Kamera": [self._phone_group, self._camera_group],  # AirPlay: ohne Einstellungen
            "Allgemein": [self._app_group, lambda: reset_group(self)],
        }
        self.nav = QListWidget()
        self.nav.setObjectName("SetupNav")
        self.nav.setItemDelegate(NavDelegate(self.nav))
        self.nav.setFixedWidth(230)
        self.nav.setIconSize(QSize(20, 20))
        self.nav.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.stack = QStackedWidget()
        t = theme.current()
        # Bereiche werden erst gebaut, wenn man sie öffnet (das erste Öffnen von „Setup“ war sonst spürbar
        # langsam). Greift Code auf etwas aus einem noch nicht gebauten Bereich zu, baut __getattr__ alle.
        self._areas: list[QScrollArea] = []
        self._pending = {}
        for i, (icon_name, title, sub) in enumerate(self.SECTIONS):
            item = QListWidgetItem(icons.icon(icon_name, t.accent, 20), f"{title}\n{sub}")
            item.setData(Qt.UserRole + 1, self.GROUPS.get(title))
            item.setSizeHint(self._item_size(title, False))
            self.nav.addItem(item)
            area = QScrollArea()
            area.setWidgetResizable(True)
            area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            self._areas.append(area)
            self._pending[i] = builders[title]
            self.stack.addWidget(area)
        self.nav.currentRowChanged.connect(self._show_row)
        self._build_section(0)
        self.nav.setCurrentRow(0)
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(18)
        side = QVBoxLayout()
        side.setSpacing(10)
        self.search = QLineEdit()
        self.search.setObjectName("SearchField")
        self.search.setPlaceholderText("Einstellung suchen …")
        self.search.setClearButtonEnabled(True)
        self.search.addAction(icons.icon("search", t.muted, 16), QLineEdit.LeadingPosition)
        self.search.setFixedWidth(230)
        self.search.textChanged.connect(self._filter)
        side.addWidget(self.search)
        side.addWidget(self.nav, 1)
        root.addLayout(side)
        right = QVBoxLayout()
        right.setSpacing(12)
        head = QHBoxLayout()
        head.setSpacing(12)
        self.section_icon = QLabel()
        self.section_icon.setObjectName("SectionIcon")
        self.section_icon.setFixedSize(38, 38)
        self.section_icon.setAlignment(Qt.AlignCenter)
        col = QVBoxLayout()
        col.setSpacing(0)
        self.section_title = QLabel()
        self.section_title.setObjectName("PanelTitle")
        self.section_sub = QLabel()
        self.section_sub.setObjectName("Muted")
        col.addWidget(self.section_title)
        col.addWidget(self.section_sub)
        head.addWidget(self.section_icon)
        head.addLayout(col, 1)
        self.no_match = QLabel("Keine Einstellung gefunden")
        self.no_match.setObjectName("Muted")
        self.no_match.hide()
        right.addLayout(head)
        right.addWidget(self.no_match)
        right.addWidget(self.stack, 1)
        root.addLayout(right, 1)
        self._update_head(0)
        controller.changed.connect(self._update_arrangement)
        QTimer.singleShot(0, self.reload_outputs)

    def _build_section(self, i: int) -> None:
        builders = self.__dict__.get("_pending", {}).pop(i, None)
        if builders is None:
            return
        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(0, 0, 8, 0)
        lay.setSpacing(6)
        for build in builders:
            box = build()
            if isinstance(box, QGroupBox) and box.title() == self.SECTIONS[i][1]:
                box.setTitle("")  # steht schon groß im Kopf darüber
                box.setProperty("notitle", True)
            lay.addWidget(box)
        for combo in inner.findChildren(QComboBox):  # lange Einträge dürfen das Fenster nicht verbreitern
            combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
            combo.setMinimumContentsLength(8)
        lay.addStretch(1)
        self._areas[i].setWidget(inner)
        self.__dict__.setdefault("_area_of", {})[inner] = self._areas[i]
        inner.installEventFilter(self)
        self._fit_forms()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._fit_forms()

    def _fit_forms(self) -> None:
        """Schmales Fenster: Beschriftung über das Feld statt daneben – sonst wird rechts abgeschnitten."""
        policy = QFormLayout.WrapAllRows if self.stack.width() < 620 else QFormLayout.DontWrapRows
        for area in self._areas:
            inner = area.widget()
            if inner is None:
                continue
            for form in inner.findChildren(QFormLayout):
                if form.rowWrapPolicy() != policy:
                    form.setRowWrapPolicy(policy)

    def eventFilter(self, obj, event):
        # Inhalt wurde schmaler (Beschriftungen umgebrochen o. Ä.): QScrollArea passt ihn von selbst erst bei der
        # nächsten Größenänderung an – bis dahin bliebe er rechts abgeschnitten. Darum hier neu einpassen.
        if event.type() == QEvent.LayoutRequest:
            area = self.__dict__.get("_area_of", {}).get(obj)  # nicht über __getattr__ (baut sonst alle Bereiche)
            if area is not None:
                area.setWidgetResizable(True)
        return super().eventFilter(obj, event)

    def build_all(self) -> None:
        for i in list(self.__dict__.get("_pending", {})):
            self._build_section(i)

    def _show_row(self, i: int) -> None:
        if i < 0:
            return
        self._build_section(i)
        self.stack.setCurrentIndex(i)
        self._update_head(i)

    def _item_size(self, title: str, compact: bool) -> QSize:
        if compact:
            return QSize(48, 48)
        searching = bool(self.__dict__.get("search") and self.search.text().strip())
        return QSize(220, 54 + (GROUP_HEAD if title in self.GROUPS and not searching else 0))

    def _update_head(self, i: int) -> None:
        """Kopf über dem Bereich: Symbol, Name und was drin ist."""
        if "section_title" not in self.__dict__:
            return
        icon_name, title, sub = self.SECTIONS[i]
        t = theme.current()
        color = t.accent if t.technical else (t.text if t.wood else t.on_accent)
        self.section_icon.setPixmap(icons.pixmap(icon_name, color, 20))
        self.section_title.setText(title)
        self.section_sub.setText(sub)

    def _section_text(self, i: int) -> str:
        """Alle Beschriftungen eines Bereichs (für die Suche)."""
        from PySide6.QtWidgets import QAbstractButton, QGroupBox

        self._build_section(i)
        inner = self._areas[i].widget()
        parts = [" ".join(self.SECTIONS[i][1:])]
        for w in inner.findChildren(QWidget) if inner is not None else []:
            if isinstance(w, (QLabel, QAbstractButton)):
                parts.append(w.text())
            elif isinstance(w, QGroupBox):
                parts.append(w.title())
            elif isinstance(w, QComboBox):
                parts.extend(w.itemText(k) for k in range(w.count()))
        return " ".join(parts).lower()

    def _filter(self, text: str) -> None:
        """Suche: nur Bereiche zeigen, in denen das Wort vorkommt (Name, Beschriftungen, Auswahllisten)."""
        query = text.strip().lower()
        compact = self.nav.width() < 100
        first = None
        for i, (_icon, title, _sub) in enumerate(self.SECTIONS):
            match = not query or query in self._section_text(i)
            self.nav.setRowHidden(i, not match)
            self.nav.item(i).setSizeHint(self._item_size(title, compact))
            if match and first is None:
                first = i
        if first is not None and self.nav.isRowHidden(self.nav.currentRow()):
            self.nav.setCurrentRow(first)
        self.no_match.setVisible(first is None)
        self.stack.setVisible(first is not None)
        self.nav.doItemsLayout()

    def __getattr__(self, name):
        # Attribut aus einem noch nicht gebauten Bereich (z. B. self.voice_on) → alle Bereiche bauen
        pending = self.__dict__.get("_pending")
        if pending and not name.startswith("__"):
            self.build_all()
            return object.__getattribute__(self, name)
        raise AttributeError(name)

    def set_compact(self, on: bool) -> None:
        """Kleines Fenster: Bereichsliste nur mit Symbolen (Name als Tooltip)."""
        self.nav.setFixedWidth(64 if on else 230)
        self.search.setVisible(not on)
        for i, (_icon, title, sub) in enumerate(self.SECTIONS):
            item = self.nav.item(i)
            item.setText("" if on else f"{title}\n{sub}")
            item.setToolTip(f"{title} – {sub}")
            item.setSizeHint(self._item_size(title, on))
        self.layout().setSpacing(10 if on else 18)

    def show_section(self, title: str) -> None:
        for i, (_icon, name, _sub) in enumerate(self.SECTIONS):
            if name == title:
                self.nav.setCurrentRow(i)

    # ================================================================ Whiteboard
    def _board_group(self):
        from .board_settings import board_settings_widget

        box = QGroupBox("Whiteboard")
        lay = QVBoxLayout(box)
        note = QLabel("Wie ein Notizbuch: Seiten, Zoomen, Stift mit Druck, Lasso, Formen, Text. Öffnen über die "
                      "Kachel „Whiteboard“ (am PC) oder „Tafel“ auf dem Handy.")
        note.setWordWrap(True)
        note.setObjectName("Muted")
        lay.addWidget(note)
        open_btn = button("Whiteboard öffnen", "board", primary=True)
        open_btn.clicked.connect(lambda: self.controller.show_whiteboard())
        lay.addWidget(open_btn, 0, Qt.AlignLeft)
        self.board_form = board_settings_widget(self.controller.board)
        lay.addWidget(self.board_form)
        return box

    # ================================================================ Monitore
    def _display_group(self):
        box = QGroupBox("Monitore")
        lay = QVBoxLayout(box)
        backend = self.controller.display
        self.backend_label = QLabel(f"System: {session_info()} – Steuerung über: {backend.name}")
        self.backend_label.setWordWrap(True)
        lay.addWidget(self.backend_label)
        if not backend.available():
            hint = QLabel("Nicht verfügbar – braucht „kscreen-doctor“ (Paket kscreen)")
            hint.setWordWrap(True)
            lay.addWidget(hint)

        self.arrangement = MonitorArrangement()
        self.arrangement.selected.connect(self._select_output)
        lay.addWidget(self.arrangement)

        form = QFormLayout()
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(10)
        self.output_combo = QComboBox()
        self.output_combo.currentIndexChanged.connect(self._show_output)
        self.enabled_check = QCheckBox("Monitor eingeschaltet")
        self.primary_check = QCheckBox("Hauptmonitor")
        self.res_combo = QComboBox()
        self.res_combo.currentIndexChanged.connect(self._fill_rates)
        self.rate_combo = QComboBox()
        self.scale_spin = QDoubleSpinBox()
        self.scale_spin.setRange(0.5, 4.0)
        self.scale_spin.setSingleStep(0.25)
        self.scale_spin.setSuffix(" ×")
        self.scale_spin.setValue(1.0)
        self.rot_combo = QComboBox()
        for key, label in ROTATIONS.items():
            self.rot_combo.addItem(label, key)
        form.addRow("Monitor:", self.output_combo)
        form.addRow("", self.enabled_check)
        form.addRow("", self.primary_check)
        form.addRow("Auflösung:", self.res_combo)
        form.addRow("Bildwiederholrate:", self.rate_combo)
        form.addRow("Skalierung:", self.scale_spin)
        form.addRow("Drehung:", self.rot_combo)
        self.side_combo = QComboBox()
        for key, label in SIDES:
            self.side_combo.addItem(label, key)
        form.addRow("Der Bildschirm liegt:", self.side_combo)
        if not backend.supports_scale:
            self.scale_spin.setEnabled(False)
            self.scale_spin.setToolTip("Skalierung stellst du unter Windows/X11 in den Systemeinstellungen ein.")
        lay.addLayout(form)


        apply_btn = button("Übernehmen", "check", primary=True)
        apply_btn.clicked.connect(self._apply)
        reload_btn = button("Neu laden", "refresh")
        reload_btn.clicked.connect(self.reload_outputs)
        ident_btn = button("Monitore identifizieren", "monitor")
        ident_btn.clicked.connect(self.identify)
        lay.addWidget(flow_row(apply_btn, reload_btn, ident_btn))  # bricht im kleinen Fenster um

        mirror_btn = button("System-Spiegeln", "mirror")
        mirror_btn.setToolTip("Das Betriebssystem spiegelt Monitor 1 (ohne AluPC). "
                              "Standbild und Sichtschutz gehen dann nicht.")
        mirror_btn.clicked.connect(self._system_mirror)
        extend_btn = button("System-Erweitern", "extend")
        extend_btn.clicked.connect(self._system_extend)
        open_btn = button("Anzeige-Einstellungen", "sliders")
        open_btn.setToolTip("Bildschirm-Einstellungen des Systems (Windows bzw. KDE/GNOME)")
        open_btn.clicked.connect(self._open_display_settings)
        lay.addWidget(flow_row(mirror_btn, extend_btn, open_btn))
        for w in (apply_btn, mirror_btn, extend_btn, self.output_combo):
            w.setEnabled(backend.available())
        return box

    def reload_outputs(self):
        if not self.controller.display.available():
            self._update_arrangement()
            return

        def done(outputs):
            self.outputs = outputs
            current = self.output_combo.currentData()
            self.output_combo.blockSignals(True)
            self.output_combo.clear()
            for o in outputs:
                label = o.name + (f" – {o.description}" if o.description else "")
                if o.primary:
                    label += " (Haupt)"
                self.output_combo.addItem(label, o.name)
            self.output_combo.blockSignals(False)
            idx = self.output_combo.findData(current)
            self.output_combo.setCurrentIndex(idx if idx >= 0 else 0)
            self._show_output()
            # Aktuelle Anordnung anzeigen, damit „Übernehmen“ nichts ungewollt verschiebt
            enabled = [o for o in outputs if o.enabled]
            main = next((o for o in enabled if o.primary), enabled[0] if enabled else None)
            other = next((o for o in enabled if o is not main), None)
            if main is not None and other is not None:
                side = side_of(outputs, main.name, other.name)
                self.side_combo.setCurrentIndex(max(0, self.side_combo.findData(side)))
            self._update_arrangement()

        run_async(self.controller.display.list_outputs, done,
                  lambda e: self.backend_label.setText(f"Monitore nicht lesbar: {e}"))

    def _update_arrangement(self):
        out = self.controller.output_screen()
        items = []
        if self.outputs:
            logical = self.controller.display.logical_positions
            for o in self.outputs:
                if not o.enabled:
                    continue
                w, h = o.size()
                if logical and o.scale:
                    w, h = round(w / o.scale), round(h / o.scale)
                m = o.mode()
                label = f"{m.width}×{m.height}, {m.refresh:.0f} Hz" if m else ""
                items.append({"name": o.name, "x": o.x, "y": o.y, "w": max(w, 1), "h": max(h, 1),
                              "primary": o.primary, "label": label})
        else:  # ohne Systemzugriff: Qt-Sicht der Monitore zeigen
            primary = QGuiApplication.primaryScreen()
            for s in QGuiApplication.screens():
                g = s.geometry()
                items.append({"name": s.name(), "x": g.x(), "y": g.y(), "w": g.width(), "h": g.height(),
                              "primary": s is primary,
                              "label": f"{g.width()}×{g.height()}, {s.refreshRate():.0f} Hz"})
        self.arrangement.set_items(items, out.name() if out else "")
        self.arrangement.set_current(self.output_combo.currentData() or "")

    def _select_output(self, name: str):
        idx = self.output_combo.findData(name)
        if idx >= 0:
            self.output_combo.setCurrentIndex(idx)

    def _current_output(self):
        name = self.output_combo.currentData()
        return next((o for o in self.outputs if o.name == name), None)

    def _show_output(self):
        o = self._current_output()
        if o is None:
            return
        self.arrangement.set_current(o.name)
        self.enabled_check.setChecked(o.enabled)
        self.primary_check.setChecked(o.primary)
        self.scale_spin.setValue(o.scale)
        self.rot_combo.setCurrentIndex(max(0, self.rot_combo.findData(o.rotation)))
        self.res_combo.blockSignals(True)
        self.res_combo.clear()
        for w, h in o.resolutions():
            self.res_combo.addItem(f"{w} × {h}", (w, h))
        cur = o.mode()
        if cur:
            self.res_combo.setCurrentIndex(max(0, self.res_combo.findData((cur.width, cur.height))))
        self.res_combo.blockSignals(False)
        self._fill_rates()

    def _fill_rates(self):
        o = self._current_output()
        res = self.res_combo.currentData()
        self.rate_combo.clear()
        if o is None or res is None:
            return
        cur = o.mode()
        for m in o.refresh_rates(*res):
            self.rate_combo.addItem(f"{m.refresh:.2f} Hz".replace(".00 Hz", " Hz"), m.id)
        if cur:
            idx = self.rate_combo.findData(cur.id)
            if idx >= 0:
                self.rate_combo.setCurrentIndex(idx)

    def _collect(self):
        """Neue Einstellungen aus den Feldern in eine Kopie der Monitorliste schreiben."""
        outputs = clone_outputs(self.outputs)
        o = next((x for x in outputs if x.name == self.output_combo.currentData()), None)
        if o is None:
            return None
        o.enabled = self.enabled_check.isChecked()
        if self.rate_combo.currentData():
            o.mode_id = self.rate_combo.currentData()
        o.rotation = self.rot_combo.currentData()
        if self.controller.display.supports_scale:
            o.scale = self.scale_spin.value()
        if self.primary_check.isChecked():
            for x in outputs:
                x.primary = x is o
        enabled = [x for x in outputs if x.enabled]
        if not enabled:
            error_box(self, "Mindestens ein Monitor muss eingeschaltet bleiben.")
            return None
        main = next((x for x in enabled if x.primary), enabled[0])
        side = self.side_combo.currentData()
        for x in enabled:
            if x is main:
                continue
            if side == "mirror":
                x.x, x.y = main.x, main.y
            else:
                place(outputs, main.name, x.name, side, self.controller.display.logical_positions)
        return outputs

    def _apply(self):
        new = self._collect()
        if new is None:
            return
        old = clone_outputs(self.outputs)
        backend = self.controller.display

        def applied(_r):
            dlg = ConfirmDialog(self.window())
            if dlg.exec() == QDialog.Accepted:
                self.reload_outputs()
            else:
                run_async(lambda: backend.apply(old), lambda _r: self.reload_outputs(),
                          lambda e: error_box(self, f"Zurücksetzen fehlgeschlagen: {e}"))

        run_async(lambda: backend.apply(new), applied,
                  lambda e: error_box(self, f"Einstellungen konnten nicht gesetzt werden:\n{e}"))

    def _system_mirror(self):
        pair = self.controller.prepare_system_mirror()
        if pair is None:
            return
        main, out = pair
        run_async(lambda: self.controller.display.mirror(main, out), lambda _r: self._after_mode(),
                  lambda e: error_box(self, f"Spiegeln fehlgeschlagen: {e}"))

    def _system_extend(self):
        main, out = self.controller.main_screen(), self.controller.output_screen()
        if main is None or out is None:
            error_box(self, "Kein Bildschirm gefunden.")
            return
        side = self.side_combo.currentData()
        if side == "mirror":
            side = "right"
        run_async(lambda: self.controller.display.extend(main.name(), out.name(), side),
                  lambda _r: self._after_mode(), lambda e: error_box(self, f"Erweitern fehlgeschlagen: {e}"))

    def _after_mode(self):
        QTimer.singleShot(1500, self.reload_outputs)

    def identify(self):
        self._ident = [IdentifyWindow(s, i + 1) for i, s in enumerate(QGuiApplication.screens())]
        for w in self._ident:
            w.show()
        QTimer.singleShot(3000, lambda: [w.close() for w in self._ident])

    # ================================================================ Darstellung
    def _appearance_group(self):
        box = QGroupBox("Darstellung")
        form = QFormLayout(box)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(10)
        a = self.config["appearance"]
        mode = QComboBox()
        for key, label in theme.MODES.items():
            mode.addItem(label, key)
        mode.setCurrentIndex(max(0, mode.findData(a.get("mode", "system"))))
        swatches = FlowLayout(spacing=8)  # bricht im kleinen Fenster um
        self._swatches = {}
        for key, (label, color) in theme.ACCENTS.items():
            if key == "eigen":
                color = a.get("accent_color") or color
            b = Swatch(theme.system_accent() if key == "system" else color, label)
            b.system = key == "system"
            b.brand = key == "alupc"
            b.clicked.connect(lambda _=False, k=key: self._set_accent(k))
            self._swatches[key] = b
            swatches.addWidget(b)
        pick = button("Farbe wählen …", "palette")
        pick.setToolTip("Eigene Akzentfarbe aussuchen")
        pick.clicked.connect(self._pick_accent)
        swatches.addWidget(pick)
        self._style_swatches(a.get("accent", "alupc"))
        from ..transitions import TRANSITIONS

        tr = self.config["transition"]
        self.transition_combo = QComboBox()
        # lange Einträge („Zoom (altes Bild …)“) dürfen die Karte nicht breiter machen
        self.transition_combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.transition_combo.setMinimumContentsLength(10)
        for key, label in TRANSITIONS.items():
            self.transition_combo.addItem(label, key)
        current = "schnitt" if not a.get("fade", True) else tr.get("type", "blende")
        self.transition_combo.setCurrentIndex(max(0, self.transition_combo.findData(current)))
        self.transition_ms = QSpinBox()
        self.transition_ms.setRange(50, 5000)
        self.transition_ms.setSingleStep(50)
        self.transition_ms.setSuffix(" ms")
        self.transition_ms.setValue(int(tr.get("ms", 400)))
        try_btn = button("Ausprobieren", "play")
        try_btn.setToolTip("Zeigt den Übergang einmal auf dem Bildschirm (der aktuelle Inhalt bleibt)")
        try_btn.clicked.connect(self._try_transition)
        tr_row = FlowLayout()  # bricht im kleinen Fenster um
        tr_row.addWidget(self.transition_combo)
        tr_row.addWidget(self.transition_ms)
        tr_row.addWidget(try_btn)

        def save_transition():
            kind = self.transition_combo.currentData()
            self.config["transition"] = {"type": kind, "ms": self.transition_ms.value()}
            self._save_appearance(fade=kind != "schnitt", emit=False)
            self.transition_ms.setEnabled(kind != "schnitt")

        self.transition_combo.currentIndexChanged.connect(save_transition)
        self.transition_ms.valueChanged.connect(save_transition)
        self.transition_ms.setEnabled(current != "schnitt")

        def save_mode():
            self._save_appearance(mode=mode.currentData())

        mode.currentIndexChanged.connect(save_mode)
        styles = FlowLayout(spacing=12)  # bricht im kleinen Fenster um
        self._style_cards = {}
        for key in theme.STYLES:
            card = StyleCard(key, self.config)
            card.setChecked(a.get("style", "normal") == key)
            card.clicked.connect(lambda _=False, k=key: self._save_appearance(style=k))
            self._style_cards[key] = card
            styles.addWidget(card)
        form.addRow("Profil:", self._profile_row())
        form.addRow("Stil:", styles)
        woods = FlowLayout(spacing=8)
        self._wood_swatches = {}
        for key in theme.WOODS:
            sw = WoodSwatch(key)
            sw.setChecked(a.get("wood", theme.DEFAULT_WOOD) == key)
            sw.clicked.connect(lambda _=False, k=key: self._save_appearance(wood=k))
            self._wood_swatches[key] = sw
            woods.addWidget(sw)
        self._wood_row = QWidget()
        self._wood_row.setLayout(woods)
        self._mode_combo = mode
        self._appearance_form = form
        form.addRow("Holzart:", self._wood_row)
        form.addRow("Hell/Dunkel:", mode)
        form.addRow("Akzentfarbe:", swatches)
        self._fine_controls(form, a)
        self.quick_switch = QCheckBox("Knopf unten links zeigen")
        self.quick_switch.setToolTip("Stil, Hell/Dunkel und Profil mit einem Klick")
        self.quick_switch.setChecked(bool(a.get("quick_switch", True)))
        self.quick_switch.toggled.connect(lambda on: self._save_appearance(quick_switch=on))
        form.addRow("Schnellwahl:", self.quick_switch)
        form.addRow("Desktop:", self._desktop_theme_row())
        self._sync_style_rows()
        from .. import perf

        power = QComboBox()
        power.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        power.setMinimumContentsLength(12)
        for key, label in perf.MODES.items():
            power.addItem(label, key)
        power.setCurrentIndex(max(0, power.findData(a.get("performance", "auto"))))
        weak = "schwacher PC erkannt → sparsam" if perf.weak_pc() else "starker PC erkannt → flüssig"
        power.setToolTip(f"Automatisch: {weak}. Sparsam: Animationen mit weniger Bildern, "
                         "keine Übergänge in der App.")

        def save_power():
            self.config["appearance"] = {**self.config["appearance"], "performance": power.currentData()}
            perf.configure(power.currentData())

        power.currentIndexChanged.connect(save_power)
        form.addRow("Leistung:", power)
        form.addRow("Szenenwechsel:", tr_row)
        hint = QLabel("Gilt beim Wechsel auf dem Bildschirm. Jede Szene kann einen eigenen haben.")
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        form.addRow("", hint)
        return box

    def _desktop_theme_row(self):
        """AluPC-Design aufs System: Farben, Hell/Dunkel, Hintergrundbild – mit „Zurück“. Zieht mit, wenn man in
        AluPC Akzentfarbe oder Design ändert."""
        from PySide6.QtWidgets import QCheckBox

        from .. import desktop_theme as dt

        holder = QWidget()
        col = QVBoxLayout(holder)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(6)
        row = QHBoxLayout()
        self.desk_apply = button("AluPC-Design aufs System", "palette")
        self.desk_apply.setToolTip("Windows: Akzentfarbe, Hell/Dunkel, Hintergrundbild · KDE: Farbschema, Plasma-Stil, "
                                   "Hintergrundbild · GNOME: Hell/Dunkel, Akzentfarbe, Hintergrundbild – der alte "
                                   "Stand wird gemerkt")
        self.desk_undo = button("Zurück", "undo")
        self.desk_state = QLabel()
        self.desk_state.setObjectName("Muted")
        self.desk_state.setWordWrap(True)
        row.addWidget(self.desk_apply)
        row.addWidget(self.desk_undo)
        row.addStretch(1)
        col.addLayout(row)
        opts = QHBoxLayout()
        parts = {"colors": True, "mode": True, "wallpaper": True, **(self.config["appearance"].get("desktop") or {})}
        self.desk_parts = {}
        for key, label in (("colors", "Farben"), ("mode", "Hell/Dunkel"), ("wallpaper", "Hintergrundbild")):
            box = QCheckBox(label)
            box.setChecked(bool(parts.get(key, True)))
            box.toggled.connect(lambda on, k=key: self._save_appearance(
                emit=False, desktop={**(self.config["appearance"].get("desktop") or {}), k: bool(on)}))
            self.desk_parts[key] = box
            opts.addWidget(box)
        opts.addStretch(1)
        col.addLayout(opts)
        col.addWidget(self.desk_state)
        ok, why = dt.supported()

        def refresh():
            self.desk_undo.setEnabled(dt.active())
            self.desk_apply.setEnabled(ok)
            if not ok:
                self.desk_state.setText(why)
            elif dt.active() and not self.desk_state.text():
                self.desk_state.setText("an – zieht mit, wenn du Akzentfarbe oder Design änderst")

        def do(action):
            done, msg = action()
            self.desk_state.setText(msg)
            if not done:
                error_box(self, msg)
            refresh()

        self.desk_apply.clicked.connect(lambda: do(self._apply_desktop_design))
        self.desk_undo.clicked.connect(lambda: do(dt.restore))
        refresh()
        return holder

    def _apply_desktop_design(self) -> tuple[bool, str]:
        from .. import desktop_theme as dt

        a = self.config["appearance"]
        parts = {"colors": True, "mode": True, "wallpaper": True, **(a.get("desktop") or {})}
        return dt.apply(theme.current().dark, accent=a.get("accent", "alupc"), colors=parts["colors"],
                        mode=parts["mode"], wallpaper=parts["wallpaper"])

    def _try_transition(self):
        """Aktuellen Inhalt mit dem eingestellten Übergang neu zeigen."""
        c = self.controller
        if c.mode == "content" and c.content:
            c.show_source(c.content, remember=False, sound=False)
        else:
            error_box(self, "Auf dem Bildschirm läuft gerade kein Inhalt von AluPC – zeige zuerst eine Szene "
                            "oder Quelle an.")

    def _style_swatches(self, active: str):
        for key, b in self._swatches.items():
            b.setChecked(key == active)

    def _set_accent(self, key: str):
        if key == "eigen" and not self.config["appearance"].get("accent_color"):
            self._pick_accent()  # noch keine eigene Farbe → erst aussuchen
            return
        self._save_appearance(accent=key)

    def _pick_accent(self) -> None:
        """Eigene Akzentfarbe (nicht-blockierender Farbdialog)."""
        from PySide6.QtWidgets import QColorDialog

        a = self.config["appearance"]
        dlg = QColorDialog(QColor(a.get("accent_color") or theme.current().accent), self)
        dlg.setWindowTitle("Akzentfarbe wählen")

        def chosen(color):
            if color.isValid():
                self._swatches["eigen"].color = color.name()
                self._save_appearance(accent="eigen", accent_color=color.name())

        dlg.colorSelected.connect(chosen)
        dlg.open()
        self._color_dialog = dlg

    # ---------------------------------------------------------------- Profile und Feinheiten
    def _profiles(self) -> dict:
        return {**theme.BUILTIN_PROFILES, **self.config["appearance"].get("profiles", {})}

    def _profile_row(self) -> QWidget:
        self._profile_combo = QComboBox()
        self._profile_combo.setMinimumContentsLength(22)
        self._profile_combo.currentIndexChanged.connect(self._apply_profile)
        save = button("Speichern als …", "plus")
        save.setToolTip("Die jetzige Darstellung (Stil, Farbe, Rundung, Schrift, Abstände) als Profil speichern")
        save.clicked.connect(self._save_profile)
        self._profile_delete = button("Löschen", "trash")
        self._profile_delete.setToolTip("Eigenes Profil löschen (fertige Profile bleiben)")
        self._profile_delete.clicked.connect(self._delete_profile)
        self._profile_undo: dict | None = None
        self._fill_profiles()
        return flow_row(self._profile_combo, save, self._profile_delete)

    def _fill_profiles(self) -> None:
        combo = self._profile_combo
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("Aktuelle Einstellungen", None)
        own = self.config["appearance"].get("profiles", {})
        for name in theme.BUILTIN_PROFILES:
            combo.addItem(name, name)
        for name in own:
            if name not in theme.BUILTIN_PROFILES:
                combo.addItem(f"{name} (eigenes)", name)
        current = self.config["appearance"].get("profile") or None
        combo.setCurrentIndex(max(0, combo.findData(current)) if current else 0)
        combo.blockSignals(False)
        self._profile_delete.setEnabled(bool(current) and current in own)

    def _apply_profile(self, index: int) -> None:
        name = self._profile_combo.itemData(index)
        a = self.config["appearance"]
        if name is None:  # „Aktuelle Einstellungen“: zurück zu dem, was vor dem Profil eingestellt war
            if self._profile_undo is not None:
                values, self._profile_undo = self._profile_undo, None
                self._save_appearance(**values, profile="")
            else:
                self._save_appearance(profile="")
        else:
            if self._profile_undo is None:  # Stand vor dem ersten Profil merken („Aktuelle Einstellungen“)
                self._profile_undo = {k: a[k] for k in theme.PROFILE_KEYS if k in a}
            values = {k: v for k, v in self._profiles()[name].items() if k in theme.PROFILE_KEYS}
            self._save_appearance(**values, profile=name)
        self._sync_appearance_controls()

    def _save_profile(self) -> None:
        from PySide6.QtWidgets import QInputDialog

        name, ok = QInputDialog.getText(self, "Profil speichern", "Name des Profils:",
                                        text=self.config["appearance"].get("profile") or "Mein Design")
        name = name.strip()
        if not ok or not name:
            return
        if name in theme.BUILTIN_PROFILES:
            name += " (eigenes)"
        a = self.config["appearance"]
        own = dict(a.get("profiles", {}))
        own[name] = {k: a[k] for k in theme.PROFILE_KEYS if k in a}
        self._profile_undo = None
        self._save_appearance(emit=False, profiles=own, profile=name)
        self._fill_profiles()

    def _delete_profile(self) -> None:
        a = self.config["appearance"]
        name = a.get("profile")
        own = dict(a.get("profiles", {}))
        if name in own:
            del own[name]
            self._save_appearance(emit=False, profiles=own, profile="")
            self._fill_profiles()

    def _fine_controls(self, form, a: dict) -> None:
        """Rundung, Schriftgröße, Abstände – gelten für jeden Stil."""
        def slider(lo, hi, value, suffix, key, step=5):
            row = QWidget()
            lay = QHBoxLayout(row)
            lay.setContentsMargins(0, 0, 0, 0)
            sl = QSlider(Qt.Horizontal)
            sl.setRange(lo, hi)
            sl.setSingleStep(step)
            sl.setPageStep(step * 2)
            sl.setValue(int(value))
            label = QLabel(f"{int(value)} %")
            label.setMinimumWidth(48)
            sl.value_label = label
            timer = QTimer(row, singleShot=True, interval=250)

            def save():
                timer.stop()
                if int(self.config["appearance"].get(key, 100)) != sl.value():
                    self._save_appearance(**{key: sl.value()})

            sl.valueChanged.connect(lambda v: (label.setText(f"{v} %"), None if sl.isSliderDown() else timer.start()))
            sl.sliderReleased.connect(save)
            timer.timeout.connect(save)
            lay.addWidget(sl, 1)
            lay.addWidget(label)
            return row, sl

        row, self._radius_slider = slider(0, 200, a.get("radius", 100), "%", "radius", 10)
        self._radius_slider.setToolTip("0 % = eckig, 100 % = wie der Stil, 200 % = sehr rund")
        form.addRow("Rundung:", row)
        row, self._font_slider = slider(85, 130, a.get("font", 100), "%", "font", 5)
        self._font_slider.setToolTip("Größe aller Schriften in AluPC")
        form.addRow("Schriftgröße:", row)
        self._density_combo = QComboBox()
        for key, (label, _f) in theme.DENSITIES.items():
            self._density_combo.addItem(label, key)
        self._density_combo.setCurrentIndex(max(0, self._density_combo.findData(a.get("density", "normal"))))
        self._density_combo.currentIndexChanged.connect(
            lambda _i: self._save_appearance(density=self._density_combo.currentData()))
        form.addRow("Abstände:", self._density_combo)

    def _sync_appearance_controls(self) -> None:
        """Bedienelemente auf den gespeicherten Stand bringen (nach einem Profilwechsel) – ohne neu zu speichern."""
        a = self.config["appearance"]
        for key, card in getattr(self, "_style_cards", {}).items():
            card.setChecked(a.get("style", "normal") == key)
        for key, sw in getattr(self, "_wood_swatches", {}).items():
            sw.setChecked(a.get("wood", theme.DEFAULT_WOOD) == key)
        if "eigen" in getattr(self, "_swatches", {}) and a.get("accent_color"):
            self._swatches["eigen"].color = a["accent_color"]
        self._style_swatches(a.get("accent", "alupc"))
        qs = self.__dict__.get("quick_switch")
        if qs is not None:
            qs.blockSignals(True)
            qs.setChecked(bool(a.get("quick_switch", True)))
            qs.blockSignals(False)
        for widget, value in ((self.__dict__.get("_radius_slider"), a.get("radius", 100)),
                              (self.__dict__.get("_font_slider"), a.get("font", 100)),
                              (self.__dict__.get("_mode_combo"), None),
                              (self.__dict__.get("_density_combo"), None)):
            if widget is None:
                continue
            widget.blockSignals(True)
            if isinstance(widget, QSlider):
                widget.setValue(int(value))
                widget.value_label.setText(f"{int(value)} %")
            elif widget is self.__dict__.get("_mode_combo"):
                widget.setCurrentIndex(max(0, widget.findData(a.get("mode", "system"))))
            else:
                widget.setCurrentIndex(max(0, widget.findData(a.get("density", "normal"))))
            widget.blockSignals(False)
        self._sync_style_rows()

    def _sync_style_rows(self) -> None:
        """Holzart nur im Holz-Stil zeigen; dort bestimmt das Holz hell/dunkel (Auswahl gesperrt)."""
        form = self.__dict__.get("_appearance_form")
        if form is None:
            return
        style = self.config["appearance"].get("style")
        wood = style == "holz"
        form.setRowVisible(self._wood_row, wood)
        self._mode_combo.setEnabled(style not in ("holz", "matrix", "regie"))
        self._mode_combo.setToolTip("Im Holz-Stil bestimmt die Holzart, ob hell oder dunkel" if wood else
                                    (f"{theme.STYLES[style]} ist immer dunkel" if style in ("matrix", "regie") else ""))

    def _save_appearance(self, emit: bool = True, **changes):
        a = dict(self.config["appearance"])
        if "profile" not in changes and set(changes) & set(theme.PROFILE_KEYS) and a.get("profile"):
            # von Hand geändert → kein Profil mehr aktiv (Auswahl zeigt „Aktuelle Einstellungen“)
            changes["profile"] = ""
            self._profile_undo = None
            combo = self.__dict__.get("_profile_combo")
            if combo is not None:
                combo.blockSignals(True)
                combo.setCurrentIndex(0)
                combo.blockSignals(False)
                self._profile_delete.setEnabled(False)
        a.update(changes)
        self.config["appearance"] = a
        if emit:
            self.theme_changed.emit()
            self._style_swatches(a.get("accent", "alupc"))
            for card in getattr(self, "_style_cards", {}).values():
                card.update()
            self._sync_style_rows()
            from .. import desktop_theme as dt

            if dt.active() and ({"accent", "mode"} & set(changes)):  # Desktop-Design zieht mit
                QTimer.singleShot(150, lambda: run_async(self._apply_desktop_design,
                                                         lambda r: self.desk_state.setText(r[1])))

    # ================================================================ AluPC
    def _hardware_group(self):
        from .hardware_page import HardwarePage

        self.hardware = HardwarePage(self.controller, scroll=False)
        return self.hardware

    # ================================================================ Handy & Kamera
    def _phone_group(self):
        box = QGroupBox("Handy-Steuerung – Rechte")
        lay = QVBoxLayout(box)
        allow = {"senden": True, "steuern": True, "live": True, "laser": True,
                 **(self.config["cast"].get("allow") or {})}
        checks = {}
        for key, text in (("senden", "Senden (Fotos, Videos, Links, Text)"),
                          ("steuern", "Fernsteuern"),
                          ("live", "Live-Bild"),
                          ("laser", "Laser && Zeichnen")):
            box_ = QCheckBox(text)
            box_.setChecked(bool(allow.get(key, True)))
            checks[key] = box_
            lay.addWidget(box_)
        auto = QCheckBox("Beim Start mitstarten")
        auto.setChecked(bool(self.config["cast"].get("autostart")))
        lay.addWidget(auto)

        def save(*_):
            self.config["cast"] = {**self.config["cast"], "autostart": auto.isChecked(),
                                   "allow": {k: c.isChecked() for k, c in checks.items()}}
            self.controller._cast_snapshot()

        for w in (*checks.values(), auto):
            w.toggled.connect(save)
        hint = QLabel("Zugang mit dem Code aus dem QR-Code – oder ohne Code: das Handy bittet um Freigabe, "
                      "AluPC fragt hier „Erlauben / Ablehnen“.")
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        lay.addWidget(hint)
        devices = QLabel()
        devices.setWordWrap(True)
        forget = button("Alle Freigaben löschen", "trash")

        def show_devices():
            devs = self.controller.cast.devices()
            devices.setText("Freigegeben: " + ", ".join(f"{d.get('name', 'Handy')} ({d.get('added', '')})"
                                                         for d in devs) if devs else "Noch kein Gerät freigegeben.")
            forget.setEnabled(bool(devs))

        def do_forget():
            self.controller.cast.forget_devices()
            show_devices()

        forget.clicked.connect(do_forget)
        self.controller.access_requested.connect(lambda *_: QTimer.singleShot(500, show_devices))
        show_devices()
        lay.addWidget(devices)
        lay.addWidget(forget, 0, Qt.AlignLeft)
        return box

    def _camera_group(self):
        box = QGroupBox("Kamera")
        form = QFormLayout(box)
        self.camera_combo = QComboBox()
        self.camera_combo.setToolTip("Diese Kamera startet ein Klick auf die Kachel „Kamera“ sofort")
        self._fill_camera_combo()
        self.camera_combo.currentIndexChanged.connect(
            lambda _i: self.config.__setitem__("default_camera", self.camera_combo.currentData() or ""))
        from PySide6.QtMultimedia import QMediaDevices

        self._media_devices = QMediaDevices(self)
        self._media_devices.videoInputsChanged.connect(self._fill_camera_combo)
        fit = QComboBox()
        fit.addItem("Füllen", "cover")
        fit.addItem("Ganzes Bild", "contain")
        fit.setCurrentIndex(max(0, fit.findData(self.config.get("camera_fit", "cover"))))
        fit.currentIndexChanged.connect(lambda _i: self.config.__setitem__("camera_fit", fit.currentData()))
        form.addRow("Standard-Kamera:", self.camera_combo)
        form.addRow("Anzeige:", fit)
        hint = QLabel("Startet per Klick auf „Kamera“. Über den Pfeil wählst du eine andere.")
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        form.addRow(hint)
        return box

    def _fill_start_combo(self):
        combo = self.start_combo
        combo.blockSignals(True)
        combo.clear()
        for key, label in (("last", "Zuletzt gezeigt"), ("none", "Nichts"),
                           ("mirror", "Spiegeln"), ("camera", "Kamera"), ("airplay", "AirPlay (iPhone/iPad)"),
                           ("cast", "QR-Code")):
            combo.addItem(label, key)
        for name in self.config.scene_names():
            combo.addItem(f"Szene: {name}", f"scene:{name}")
        combo.setCurrentIndex(max(0, combo.findData(self.controller.start_content_setting())))
        combo.blockSignals(False)

    def _start_changed(self, *_):
        value = self.start_combo.currentData() or "last"
        self.config["start_content"] = value
        self.config["restore_last_content"] = value != "none"

    def _fill_camera_combo(self, *_):
        from PySide6.QtMultimedia import QMediaDevices

        from ..sources import camera_id

        combo = self.camera_combo
        combo.blockSignals(True)
        combo.clear()
        devices = QMediaDevices.videoInputs()
        for d in devices:
            combo.addItem(d.description(), camera_id(d))
        if not devices:
            combo.addItem("Keine Kamera gefunden", "")
        combo.setEnabled(bool(devices))
        # vorausgewählt: gespeicherte Kamera, sonst die erste
        combo.setCurrentIndex(max(0, combo.findData(self.config.get("default_camera", ""))))
        combo.blockSignals(False)

    def showEvent(self, e):
        super().showEvent(e)
        if hasattr(self, "start_combo"):
            self._fill_start_combo()  # neue/umbenannte Szenen

    def _app_group(self):
        box = QGroupBox("Allgemein")
        form = QFormLayout(box)
        self.screen_combo = QComboBox()
        self._fill_screen_combo()
        self.screen_combo.currentIndexChanged.connect(self._screen_changed)
        app = QGuiApplication.instance()
        app.screenAdded.connect(lambda _s: self._fill_screen_combo())
        app.screenRemoved.connect(lambda _s: self._fill_screen_combo())

        self.start_combo = QComboBox()
        self.start_combo.setToolTip("Was der Bildschirm zeigt, sobald AluPC startet")
        self._fill_start_combo()
        self.start_combo.currentIndexChanged.connect(self._start_changed)

        auto = QCheckBox("Autostart")
        try:
            auto.setChecked(autostart.is_enabled())
        except Exception:  # noqa: BLE001
            auto.setEnabled(False)
        auto.toggled.connect(self._autostart)
        minimized = QCheckBox("Minimiert starten")
        minimized.setChecked(bool(self.config["start_minimized"]))
        minimized.toggled.connect(lambda v: self.config.__setitem__("start_minimized", v))
        form.addRow("Bildschirm:", self.screen_combo)
        form.addRow("Beim Start zeigen:", self.start_combo)
        integ = QCheckBox("Ins System einbinden (Rechtsklick, Links)")
        integ.setToolTip("Rechtsklick auf Bild, Video, PDF oder Ordner im Dateimanager → Bildschirm.\n"
                         "Links wie alupc://standbild oder alupc://szene/Pause steuern AluPC.")
        integ.setChecked(bool(self.config["system_integration"]))
        integ.toggled.connect(self._integration)
        form.addRow("", auto)
        form.addRow("", minimized)
        form.addRow("", integ)
        diag = button("Diagnose kopieren", "copy")
        diag.setToolTip("Prüft Monitore, Spiegeln, AirPlay, RGB … und kopiert das Ergebnis – "
                        "zum Weitergeben, wenn etwas nicht geht")
        diag.clicked.connect(self._diagnose)
        report = button("Fehlerbericht …", "alert")
        report.setToolTip("Speichert eine Datei mit Diagnose und Fehlerprotokollen – zum Weiterschicken")
        report.clicked.connect(self._bug_report)
        again = button("Ersteinrichtung starten", "sync")
        again.setToolTip("Prüft Monitore und Spiegeln, installiert Handy-Programme – wie beim ersten Start")
        again.clicked.connect(lambda: self.window().open_first_run())
        form.addRow("Hilfe:", flow_row(diag, report, again))  # bricht im kleinen Fenster um
        return box

    def _bug_report(self):
        from .bug_report_dialog import BugReportDialog

        BugReportDialog(self.controller, self).exec()

    def _diagnose(self):
        from PySide6.QtWidgets import QApplication

        from .. import diagnose

        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            text = diagnose.report(self.controller)
        finally:
            QApplication.restoreOverrideCursor()
        QApplication.clipboard().setText(text)
        box = QMessageBox(self)
        box.setWindowTitle("Diagnose")
        box.setText("Diagnose kopiert – einfach einfügen.")
        box.setDetailedText(text)
        box.exec()

    def _fill_screen_combo(self):
        self.screen_combo.blockSignals(True)
        self.screen_combo.clear()
        self.screen_combo.addItem("Automatisch (nicht der Hauptmonitor)", "")
        for s in QGuiApplication.screens():
            self.screen_combo.addItem(f"{s.name()} – {s.size().width()}×{s.size().height()}", s.name())
        idx = self.screen_combo.findData(self.config["output_screen"])
        self.screen_combo.setCurrentIndex(max(0, idx))
        self.screen_combo.blockSignals(False)

    def _screen_changed(self):
        self.config["output_screen"] = self.screen_combo.currentData() or ""
        self.controller.update_screens()

    def _autostart(self, on):
        try:
            autostart.set_enabled(on)
        except Exception as exc:  # noqa: BLE001
            error_box(self, f"Autostart konnte nicht geändert werden: {exc}")

    def _integration(self, on):
        from ..platform import system_integration

        self.config["system_integration"] = on
        ok, msg = system_integration.set_enabled(on)
        if ok:
            self.controller.message.emit(msg)
        else:
            error_box(self, msg)

    # ================================================================ Sichtschutz
    def _privacy_group(self):
        box = QGroupBox("Sichtschutz")
        form = QFormLayout(box)
        p = self.config["privacy"]
        text = QLineEdit(p.get("text", ""))
        text.setPlaceholderText("z. B. „Gleich geht's weiter“ – leer = nur schwarz")
        img_row = QHBoxLayout()
        img = QLineEdit(p.get("image", ""))
        img.setPlaceholderText("optional: Bild/Logo statt Schwarz")
        browse = button("Durchsuchen …", "image")
        img_row.addWidget(img, 1)
        img_row.addWidget(browse)

        def save():
            self.config["privacy"] = {"text": text.text(), "image": img.text()}

        def pick():
            path, _ = QFileDialog.getOpenFileName(self, "Bild wählen", img.text(),
                                                  "Bilder (*.png *.jpg *.jpeg *.bmp *.webp)")
            if path:
                img.setText(path)
                save()

        text.editingFinished.connect(save)
        img.editingFinished.connect(save)
        browse.clicked.connect(pick)
        form.addRow("Text:", text)
        form.addRow("Bild:", img_row)
        return box

    # ================================================================ Bild-in-Bild
    def _pip_group(self):
        box = QGroupBox("Bild-in-Bild")
        form = QFormLayout(box)
        cfg = self.config["pip"]
        width = QSpinBox()
        width.setRange(160, 1920)
        width.setSuffix(" px breit")
        width.setValue(int(cfg.get("width", 480)))
        opacity = QSlider(Qt.Horizontal)
        opacity.setRange(20, 100)
        opacity.setValue(int(float(cfg.get("opacity", 1.0)) * 100))
        fps = QSpinBox()
        fps.setRange(1, 60)
        fps.setSuffix(" Bilder/s")
        fps.setValue(int(cfg.get("fps", 10)))

        def save():
            self.config["pip"] = {"width": width.value(), "opacity": opacity.value() / 100, "fps": fps.value()}
            if self.controller.pip is not None:
                self.controller.pip.apply_settings()

        width.valueChanged.connect(save)
        opacity.valueChanged.connect(save)
        fps.valueChanged.connect(save)
        form.addRow("Größe:", width)
        form.addRow("Deckkraft:", opacity)
        form.addRow("Aktualisierung:", fps)
        return box

    # ================================================================ Bildschirmschoner
    def _screensaver_group(self):
        from .screensaver_settings import ScreensaverSettings

        self.screensaver_box = ScreensaverSettings(self.controller)
        return self.screensaver_box

    # ================================================================ Timer
    def _timer_group(self):
        box = QGroupBox("Timer")
        form = QFormLayout(box)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(10)
        cfg = self.config["timer"]
        mode = QComboBox()
        mode.addItem("Countdown (läuft rückwärts)", "countdown")
        mode.addItem("Stoppuhr (läuft vorwärts)", "stoppuhr")
        mode.setCurrentIndex(max(0, mode.findData(cfg.get("mode", "countdown"))))
        minutes = QSpinBox()
        minutes.setRange(0, 999)
        minutes.setSuffix(" min")
        minutes.setValue(int(cfg.get("minutes", 5)))
        seconds = QSpinBox()
        seconds.setRange(0, 59)
        seconds.setSuffix(" s")
        seconds.setValue(int(cfg.get("seconds", 0)))
        text = QLineEdit(cfg.get("finished_text", "Zeit ist um!"))
        warn = QCheckBox("Warnfarben (erst orange, dann rot, am Ende blinken)")
        warn.setChecked(bool(cfg.get("warn_colors", True)))
        size = QSpinBox()
        size.setRange(5, 80)
        size.setSuffix(" % der Bildhöhe")
        size.setValue(int(cfg.get("size", 30)))
        dur = QHBoxLayout()
        dur.addWidget(minutes)
        dur.addWidget(seconds)

        def save(*_):
            self.config["timer"] = {"mode": mode.currentData(), "minutes": minutes.value(),
                                    "seconds": seconds.value(), "finished_text": text.text(),
                                    "warn_colors": warn.isChecked(), "size": size.value()}

        for w in (minutes, seconds, size):
            w.valueChanged.connect(save)
        mode.currentIndexChanged.connect(save)
        warn.toggled.connect(save)
        text.editingFinished.connect(save)
        form.addRow("Art:", mode)
        form.addRow("Dauer:", dur)
        form.addRow("Text am Ende:", text)
        form.addRow("Schriftgröße:", size)
        form.addRow("", warn)
        hint = QLabel("Für die Timer-Kachel. Die Töne stellst du unter „Töne“ ein.")
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        form.addRow(hint)
        return box

    # ================================================================ Töne
    def _sound_group(self):
        from PySide6.QtMultimedia import QMediaDevices

        from ..sounds import EVENTS
        from .sound_picker import SoundPicker

        box = QGroupBox("Töne")
        form = QFormLayout(box)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(8)
        cfg = self.config["sounds"]
        enabled = QCheckBox("Töne abspielen")
        enabled.setChecked(bool(cfg.get("enabled", True)))
        volume = QSlider(Qt.Horizontal)
        volume.setRange(0, 100)
        volume.setValue(int(cfg.get("volume", 70)))
        device = QComboBox()
        device.addItem("Standard-Ausgabe des Systems", "")
        for dev in QMediaDevices.audioOutputs():
            device.addItem(dev.description(), bytes(dev.id()).decode(errors="replace"))
        idx = device.findData(cfg.get("device", ""))
        device.setCurrentIndex(max(0, idx))

        def save_general(*_):
            new = dict(self.config["sounds"])
            new.update({"enabled": enabled.isChecked(), "volume": volume.value(), "device": device.currentData()})
            self.config["sounds"] = new

        enabled.toggled.connect(save_general)
        volume.sliderReleased.connect(save_general)
        volume.valueChanged.connect(lambda _v: volume.isSliderDown() or save_general())
        device.currentIndexChanged.connect(save_general)
        form.addRow("", enabled)
        form.addRow("Lautstärke:", volume)
        form.addRow("Ausgabe:", device)
        hint = QLabel("Tipp: Ausgabe = Monitor/Beamer (HDMI)")
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        form.addRow(hint)
        self.sound_pickers = {}
        for event, label in EVENTS.items():
            picker = SoundPicker(self.controller.sounds, cfg.get("events", {}).get(event, ""))

            def save_event(spec, e=event):
                new = dict(self.config["sounds"])
                events = dict(new.get("events", {}))
                events[e] = spec
                new["events"] = events
                self.config["sounds"] = new

            picker.changed.connect(save_event)
            form.addRow(label.replace("&", "&&") + ":", picker)
            self.sound_pickers[event] = picker
        more = QLabel("Eigene Töne: WAV, MP3, OGG, FLAC, M4A")
        more.setObjectName("Muted")
        more.setWordWrap(True)
        form.addRow(more)
        return box

    # ================================================================ Sprache
    def _open_voice_test(self):
        from .voice_test import VoiceTestDialog

        VoiceTestDialog(self.controller, self).exec()

    def _voice_group(self):
        from PySide6.QtMultimedia import QMediaDevices
        from PySide6.QtWidgets import QProgressBar

        from .. import voice

        box = QGroupBox("Sprachbefehle")
        lay = QVBoxLayout(box)
        intro = QLabel("Ganz normal sprechen – mit Startwort davor: „Alu PC, mach den Bildschirm schwarz“, „Alu PC, "
                       "Licht auf blau“, „Alu PC, wie spät ist es?“. Läuft komplett auf dem PC (offline), es geht kein "
                       "Ton ins Internet.")
        intro.setWordWrap(True)
        lay.addWidget(intro)
        cfg = self.config["voice"]
        self.voice_on = QCheckBox("Sprachbefehle an")
        self.voice_on.setChecked(bool(cfg.get("on")))
        lay.addWidget(self.voice_on)
        form = QFormLayout()
        mic = QComboBox()
        mic.addItem("Standard-Mikrofon des Systems", "")
        for dev in QMediaDevices.audioInputs():
            mic.addItem(dev.description(), bytes(dev.id()).decode(errors="replace"))
        mic.setCurrentIndex(max(0, mic.findData(cfg.get("device", ""))))
        form.addRow("Mikrofon:", mic)
        wake_row = FlowLayout(spacing=12)  # bricht im kleinen Fenster um
        self.wake_boxes = {}
        for key, label in voice.WAKES.items():
            cb = QCheckBox(f"„{label} …“")
            cb.setChecked(key in (cfg.get("wake") or list(voice.WAKES)))
            wake_row.addWidget(cb)
            self.wake_boxes[key] = cb
        form.addRow("Startwort:", wake_row)
        lay.addLayout(form)
        self.voice_state = QLabel()
        self.voice_state.setObjectName("Muted")
        self.voice_heard = QLabel()
        self.voice_heard.setObjectName("Muted")
        self.voice_heard.setWordWrap(True)
        state_row = QHBoxLayout()
        state_row.addWidget(self.voice_state, 1)
        test_btn = button("Sprache testen …", "mic", primary=True)
        test_btn.setToolTip("Prüft Schritt für Schritt: Modell, Mikrofon, Pegel, was erkannt wird, Startwort, Befehl")
        test_btn.clicked.connect(self._open_voice_test)
        state_row.addWidget(test_btn)
        lay.addLayout(state_row)
        lay.addWidget(self.voice_heard)
        model_row = QHBoxLayout()
        self.voice_model = QLabel()
        self.voice_model.setWordWrap(True)
        self.voice_dl = button("Herunterladen", "download")
        self.voice_bar = QProgressBar()
        self.voice_bar.setMaximumWidth(220)
        self.voice_bar.hide()
        model_row.addWidget(self.voice_model, 1)
        model_row.addWidget(self.voice_bar)
        model_row.addWidget(self.voice_dl)
        lay.insertLayout(1, model_row)  # Schritt 1 ganz oben: ohne Sprachmodell geht nichts
        # ---- Erkennung, Stimme, Gespräch
        from .. import speech, stt

        talk = QGroupBox("Erkennung && Stimme")
        tf = QFormLayout(talk)
        stt_row = FlowLayout()  # bricht im kleinen Fenster um
        stt_box = QComboBox()
        stt_box.addItem("Standard (Vosk, schnell)", "vosk")
        for key, (_repo, label, size) in stt.MODELS.items():
            stt_box.addItem(f"{label} – ca. {size} MB", key)
        stt_box.setCurrentIndex(max(0, stt_box.findData(cfg.get("stt", "vosk"))))
        stt_dl = button("Herunterladen", "download")
        stt_bar = QProgressBar()
        stt_bar.setMaximumWidth(160)
        stt_bar.hide()
        stt_row.addWidget(stt_box)
        stt_row.addWidget(stt_bar)
        stt_row.addWidget(stt_dl)
        tf.addRow("Erkennung:", stt_row)
        stt_note = QLabel()
        stt_note.setObjectName("Muted")
        stt_note.setWordWrap(True)
        tf.addRow("", stt_note)
        tts_row = FlowLayout()  # bricht im kleinen Fenster um
        tts_box = QComboBox()
        for key, (_file, label, size) in speech.PIPER_VOICES.items():
            tts_box.addItem(f"{label} – ca. {size} MB", key)
        tts_box.addItem("System-Stimme (Windows / espeak)", "system")
        tts_box.setCurrentIndex(max(0, tts_box.findData(cfg.get("tts", "thorsten"))))
        tts_dl = button("Herunterladen", "download")
        tts_bar = QProgressBar()
        tts_bar.setMaximumWidth(160)
        tts_bar.hide()
        tts_row.addWidget(tts_box)
        tts_row.addWidget(tts_bar)
        tts_row.addWidget(tts_dl)
        tf.addRow("Stimme:", tts_row)
        sys_row = QHBoxLayout()
        speak_voice = QComboBox()
        speak_voice.addItem("Standard-System-Stimme", "")
        for name in self.controller.speaker.voices():
            speak_voice.addItem(name, name)
        speak_voice.setCurrentIndex(max(0, speak_voice.findData(cfg.get("speak_voice", ""))))
        sys_row.addWidget(speak_voice, 1)
        tf.addRow("System-Stimme:", sys_row)
        rate_box = QComboBox()
        for key in speech.RATES:
            rate_box.addItem(key.capitalize(), key)
        rate_box.setCurrentIndex(max(0, rate_box.findData(cfg.get("speak_rate", "normal"))))
        test_say = button("Probehören", "sound")
        rate_row = FlowLayout()  # bricht im kleinen Fenster um
        rate_row.addWidget(rate_box)
        rate_row.addWidget(test_say)
        tf.addRow("Tempo:", rate_row)
        tts_note = QLabel()
        tts_note.setObjectName("Muted")
        tts_note.setWordWrap(True)
        tf.addRow("", tts_note)
        self.speak_on = QCheckBox("Antworten per Stimme")
        self.speak_on.setChecked(bool(cfg.get("speak", True)))
        tf.addRow("", self.speak_on)
        follow = QCheckBox(f"Nach Antwort {voice.FOLLOW_SECONDS} s weiterhören")
        follow.setToolTip(f"Nach jeder Antwort {voice.FOLLOW_SECONDS} s ohne Startwort weiterhören.\n"
                          "Aus (empfohlen): AluPC reagiert nur, wenn ein Satz mit dem Startwort beginnt. Nur das "
                          "Startwort sagen („Computer?“ → „Ja?“) geht immer.")
        follow.setChecked(bool(cfg.get("follow_all", False)))
        tf.addRow("", follow)
        mic_hint = QLabel("Mikrofon-Schalter: Knopf „Zuhören“ links oder Strg+Alt+H – solange an, zählt jeder Satz "
                          "(kein Startwort nötig). Nochmal drücken oder „Hör auf zuzuhören“ = aus.")
        mic_hint.setObjectName("Muted")
        mic_hint.setWordWrap(True)
        tf.addRow("", mic_hint)
        lay.addWidget(talk)

        def refresh_talk():
            key = stt_box.currentData()
            if key == "vosk":
                stt_note.setText("Hört das Startwort und kurze Befehle. Für ganze Sätze lieber Whisper.")
                stt_dl.hide()
            elif not stt.available():
                stt_note.setText("Whisper fehlt in dieser AluPC-Version.")
                stt_dl.hide()
            elif stt.ready(key):
                stt_note.setText("✓ Heruntergeladen. Whisper schreibt jeden Satz an AluPC noch einmal genau mit "
                                 "(offline; braucht pro Satz kurz Rechenzeit).")
                stt_dl.hide()
            else:
                stt_note.setText("Noch nicht heruntergeladen – bis dahin hört AluPC mit Vosk.")
                stt_dl.setVisible(True)
            tkey = tts_box.currentData()
            speak_voice.setEnabled(tkey == "system")
            if tkey == "system":
                tts_note.setText("" if self.controller.speaker.available() else
                                 "Keine System-Stimme gefunden – Linux: sudo apt install speech-dispatcher espeak-ng")
                tts_dl.hide()
            elif not speech.piper_available(quick=True):
                tts_note.setText("Natürliche Stimmen (Piper) fehlen in dieser AluPC-Version – es spricht die "
                                 "System-Stimme.")
                tts_dl.hide()
            elif speech.voice_ready(tkey):
                tts_note.setText("✓ Natürliche Stimme (offline).")
                tts_dl.hide()
            else:
                tts_note.setText("Noch nicht heruntergeladen – bis dahin spricht die System-Stimme.")
                tts_dl.setVisible(True)

        def save_speak(*_):
            self.config["voice"] = {**self.config["voice"], "speak": self.speak_on.isChecked(),
                                    "speak_voice": speak_voice.currentData(), "tts": tts_box.currentData(),
                                    "speak_rate": rate_box.currentData(), "stt": stt_box.currentData(),
                                    "follow_all": follow.isChecked()}
            self.controller.speaker.reload()
            refresh_talk()

        def save_stt(*_):
            save_speak()
            if self.controller.voice.running():  # Whisper im Hintergrund (neu) laden
                import threading

                threading.Thread(target=self.controller.voice.load_stt, daemon=True).start()

        def fetch(bar, btn, work, what):
            btn.setEnabled(False)
            bar.show()
            bar.setRange(0, 0)

            def run(status):
                return work(lambda d, t: status("", d, t))

            def progress(_text, d, t):
                if t:
                    bar.setRange(0, 100)
                    bar.setValue(int(100 * d / t))

            def done(_r):
                bar.hide()
                btn.setEnabled(True)
                save_stt()

            def failed(e):
                bar.hide()
                btn.setEnabled(True)
                error_box(self, f"{what} konnte nicht geladen werden: {e}")

            run_async(run, done, failed, progress)

        stt_dl.clicked.connect(lambda: fetch(stt_bar, stt_dl, lambda p: stt.download(stt_box.currentData(), p),
                                             "Whisper"))
        tts_dl.clicked.connect(lambda: fetch(tts_bar, tts_dl,
                                             lambda p: speech.download_voice(tts_box.currentData(), p), "Die Stimme"))
        self.speak_on.toggled.connect(save_speak)
        speak_voice.currentIndexChanged.connect(save_speak)
        tts_box.currentIndexChanged.connect(save_speak)
        rate_box.currentIndexChanged.connect(save_speak)
        follow.toggled.connect(save_speak)
        stt_box.currentIndexChanged.connect(save_stt)
        test_say.clicked.connect(lambda: self.controller.speaker.say(
            "Alles klar, der Bildschirm ist jetzt schwarz. Sag einfach, was ich tun soll.", force=True))
        refresh_talk()

        # ---- eigene Befehle
        custom_box = QGroupBox("Eigene Befehle")
        cl = QVBoxLayout(custom_box)
        self.custom_list = QListWidget()
        self.custom_list.setMaximumHeight(120)
        cl.addWidget(self.custom_list)
        crow = FlowLayout()
        custom_add = button("Befehl hinzufügen …", "plus")
        custom_del = button("Entfernen", "trash")
        crow.addWidget(custom_add)
        crow.addWidget(custom_del)
        cl.addLayout(crow)
        lay.addWidget(custom_box)

        def fill_custom():
            from .voice_custom import describe_action

            self.custom_list.clear()
            for c in self.config["voice"].get("custom") or []:
                item = QListWidgetItem(f"„{c['say']}“  →  {describe_action(self.config, c['do'])}")
                item.setData(Qt.UserRole, c["say"])
                self.custom_list.addItem(item)
            if not self.custom_list.count():
                self.custom_list.addItem("(noch keine – z. B. „Pause machen“ → Szene Pause)")
                self.custom_list.item(0).setFlags(Qt.NoItemFlags)

        def add_custom():
            from .voice_custom import VoiceCustomDialog

            VoiceCustomDialog(self.controller, self).exec()
            fill_custom()

        def del_custom():
            item = self.custom_list.currentItem()
            if item is None or not item.data(Qt.UserRole):
                return
            cfg_v = self.config["voice"]
            self.config["voice"] = {**cfg_v, "custom": [c for c in cfg_v.get("custom") or []
                                                        if c.get("say") != item.data(Qt.UserRole)]}
            fill_custom()

        custom_add.clicked.connect(add_custom)
        custom_del.clicked.connect(del_custom)
        fill_custom()

        # ---- nur bestimmte Stimmen
        voices_box = QGroupBox("Nur auf bestimmte Stimmen hören")
        vl = QVBoxLayout(voices_box)
        self.only_voices = QCheckBox("Nur angelernte Stimmen annehmen")
        self.only_voices.setChecked(bool(cfg.get("only_voices")))
        vl.addWidget(self.only_voices)
        self.voice_list = QListWidget()
        self.voice_list.setMaximumHeight(110)
        vl.addWidget(self.voice_list)
        vrow = FlowLayout()  # bricht im kleinen Fenster um
        self.voice_add = button("Stimme anlernen …", "plus")
        self.voice_del = button("Entfernen", "trash")
        strict = QComboBox()
        for key, label in (("streng", "streng"), ("normal", "normal"), ("locker", "locker")):
            strict.addItem(f"Genauigkeit: {label}", key)
        strict.setCurrentIndex(max(0, strict.findData(cfg.get("strict", "normal"))))
        vrow.addWidget(self.voice_add)
        vrow.addWidget(self.voice_del)
        vrow.addWidget(strict)
        vl.addLayout(vrow)
        spk_row = QHBoxLayout()
        self.spk_label = QLabel()
        self.spk_label.setWordWrap(True)
        self.spk_dl = button("Herunterladen", "download")
        spk_row.addWidget(self.spk_label, 1)
        spk_row.addWidget(self.spk_dl)
        vl.addLayout(spk_row)
        note = QLabel("Ein Filter gegen Zurufe aus dem Raum – kein Schutz: eine Aufnahme oder eine sehr ähnliche Stimme "
                      "kann ihn täuschen. Hinter „Zuletzt gehört“ steht, wen AluPC erkannt hat und wie sicher "
                      "(kleiner = ähnlicher).")
        note.setObjectName("Muted")
        note.setWordWrap(True)
        vl.addWidget(note)
        lay.addWidget(voices_box)

        cmds = QLabel("<b>Beispiele</b> (Startwort davor, z. B. „Alu PC, …“ – oder Mikrofon-Schalter an):<br>"
                      "„Mach den Bildschirm schwarz“ · „Bild wieder an“ · „Kein Standbild mehr“<br>"
                      "„Zeig die Kamera / das Wetter / den Systemstatus / das Whiteboard“<br>"
                      "„Licht aus“ · „Licht auf blau“ · „Licht wie der Bildschirm“ · „Licht heller“<br>"
                      "„Timer auf fünf Minuten“ · „Timer Pause“ · „Bildschirmschoner an“ · „Overlays aus“<br>"
                      "„Nächste Szene“ · „Szene <i>Name</i>“ · „Lass uns Pong spielen“ · „Nächste Frage“<br>"
                      "„Nächstes Lied“ · „Musik Pause“ · „Dreh das Glücksrad“ · „Computer sperren“<br>"
                      "Fragen: „Wie spät ist es?“ · „Welcher Tag ist heute?“ · „Wie wird das Wetter?“ · "
                      "„Wie warm ist der Prozessor?“ · „Wie geht es dem Computer?“ · „Was kannst du?“ · "
                      "„Erzähl einen Witz“<br>Nur „Alu PC“ sagen → „Ja?“ – dann den Satz ohne Startwort.")
        cmds.setObjectName("Muted")
        cmds.setWordWrap(True)
        lay.addWidget(cmds)
        vc = self.controller.voice

        def fill_voices():
            self.voice_list.clear()
            for v in self.config["voice"].get("voices") or []:
                self.voice_list.addItem(v.get("name", "?"))
            if not self.voice_list.count():
                self.voice_list.addItem("(noch keine Stimme angelernt)")
                self.voice_list.item(0).setFlags(Qt.NoItemFlags)

        def refresh():
            ok = voice.vosk_available(quick=True)
            ready = voice.model_ready()
            spk = voice.spk_ready()
            self.spk_label.setText("Stimmerkennung ✓" if spk else
                                   f"Stimmerkennung fehlt – einmal herunterladen (ca. {voice.SPK_SIZE_MB} MB)")
            self.spk_dl.setVisible(ok and not spk)
            self.voice_add.setEnabled(ok and ready)  # der Dialog lädt Stimmerkennung und startet das Zuhören selbst
            self.voice_add.setToolTip("" if ready else "Erst das Sprachmodell herunterladen")
            if not ok:
                self.voice_model.setText("Spracherkennung (Vosk) fehlt in dieser AluPC-Version.")
            elif ready:
                self.voice_model.setText("Sprachmodell: Deutsch ✓")
            else:
                self.voice_model.setText(f"<b>Schritt 1:</b> Sprachmodell herunterladen (ca. {voice.MODEL_SIZE_MB} MB) – "
                                         "erst dann lassen sich die Sprachbefehle einschalten.")
            t = theme.current()
            self.voice_model.setStyleSheet("" if ready or not ok else f"color: {t.warning};")
            self.voice_dl.setProperty("primary", not ready)
            self.voice_dl.style().unpolish(self.voice_dl)
            self.voice_dl.style().polish(self.voice_dl)
            self.voice_dl.setVisible(ok and not ready)
            self.voice_on.setEnabled(ok and ready)
            self.voice_state.setText(f"Status: {vc.state}")

        def save(*_):
            wakes = [k for k, cb in self.wake_boxes.items() if cb.isChecked()] or ["monitor"]
            self.config["voice"] = {**self.config["voice"], "on": self.voice_on.isChecked(),
                                    "device": mic.currentData(), "wake": wakes}
            vc.stop()
            vc.apply()
            refresh()

        def save_filter(*_):
            self.config["voice"] = {**self.config["voice"], "only_voices": self.only_voices.isChecked(),
                                    "strict": strict.currentData()}

        def enroll():
            from .voice_enroll import VoiceEnrollDialog

            VoiceEnrollDialog(self.controller, self).exec()
            fill_voices()

        def remove_voice():
            item = self.voice_list.currentItem()
            if item is None or not (item.flags() & Qt.ItemIsEnabled):
                return
            cfg = self.config["voice"]
            self.config["voice"] = {**cfg, "voices": [v for v in cfg.get("voices") or []
                                                      if v.get("name") != item.text()]}
            fill_voices()

        def download_spk():
            self.spk_dl.setEnabled(False)

            def done(_p):
                self.spk_dl.setEnabled(True)
                vc.stop()  # neu laden, damit die Stimmerkennung dabei ist
                vc.apply()
                refresh()

            def failed(e):
                self.spk_dl.setEnabled(True)
                error_box(self, f"Stimmerkennung konnte nicht geladen werden: {e}")

            run_async(lambda: voice.download_model(url=voice.SPK_URL, target=voice.spk_dir(), ready=voice.spk_ready),
                      done, failed)

        for cb in self.wake_boxes.values():
            cb.toggled.connect(save)
        self.only_voices.toggled.connect(save_filter)
        strict.currentIndexChanged.connect(save_filter)
        self.voice_add.clicked.connect(enroll)
        self.voice_del.clicked.connect(remove_voice)
        self.spk_dl.clicked.connect(download_spk)
        fill_voices()

        def download():
            self.voice_dl.setEnabled(False)
            self.voice_bar.show()
            self.voice_bar.setRange(0, 0)

            def work(status):
                return voice.download_model(lambda done, total: status(f"{done // 1_000_000} MB", done, total))

            def progress(_text, done, total):
                if total:
                    self.voice_bar.setRange(0, 100)
                    self.voice_bar.setValue(int(100 * done / total))

            def done(_path):
                self.voice_bar.hide()
                self.voice_dl.setEnabled(True)
                refresh()

            def failed(e):
                self.voice_bar.hide()
                self.voice_dl.setEnabled(True)
                error_box(self, f"Sprachmodell konnte nicht geladen werden: {e}")

            run_async(work, done, failed, progress)

        self.voice_on.toggled.connect(save)
        mic.currentIndexChanged.connect(save)
        self.voice_dl.clicked.connect(download)
        vc.state_changed.connect(lambda _s: refresh())
        vc.heard.connect(lambda text: self.voice_heard.setText(f"Zuletzt gehört: {text}"))
        vc.rejected.connect(lambda text, why: self.voice_heard.setText(f"Ignoriert: „{text}“ – {why}"))
        refresh()
        return box

    def _open_display_settings(self):
        from ..platform import open_display_settings

        if not open_display_settings():
            error_box(self, "Anzeige-Einstellungen des Systems nicht gefunden.")

    # ================================================================ Tastenkürzel
    def _hotkey_group(self):
        box = QGroupBox("Tastenkürzel")
        form = QFormLayout(box)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(8)
        self.hotkey_edits = {}
        for action, label in HOTKEY_LABELS.items():
            btn = HotkeyButton(self.config["hotkeys"].get(action, ""), label)
            btn.changed.connect(lambda seq, a=action: self._save_hotkey(a, seq))
            form.addRow(label.replace("&", "&&") + ":", btn)
            self.hotkey_edits[action] = btn
        more = QLabel("Kürzel für Szenen setzt du im Szenen-Editor, für eigene Kacheln unter „Startseite anpassen“.")
        more.setWordWrap(True)
        form.addRow(more)
        if self.hotkeys is not None and getattr(self.hotkeys, "system_wide", False):
            form.addRow(QLabel("Gelten überall – auch wenn AluPC im Hintergrund ist"))
        else:
            hint = QLabel("Gelten, wenn AluPC aktiv ist · überall: Befehl <tt>alupc --befehl standbild</tt> "
                          "als Kurzbefehl im System eintragen")
            hint.setWordWrap(True)
            hint.setTextFormat(Qt.RichText)
            form.addRow(hint)
        if not IS_WINDOWS:
            kde = button("KDE-Kurzbefehle öffnen", "keyboard")
            kde.clicked.connect(self._open_kde_shortcuts)
            form.addRow("", kde)
        self.hotkey_status = QLabel("")
        self.hotkey_status.setWordWrap(True)
        self.hotkey_status.setStyleSheet(f"color: {theme.current().warning};")
        form.addRow(self.hotkey_status)
        return box

    def refresh_scene_lists(self):
        """Szenenliste im Bildschirmschoner aktualisieren (nach Anlegen/Umbenennen/Löschen)."""
        box = getattr(self, "screensaver_box", None)
        if box is None:
            return
        combo = box.scene_combo
        current = combo.currentText()
        combo.blockSignals(True)
        combo.clear()
        combo.addItems(self.config.scene_names())
        combo.setCurrentText(current)
        combo.blockSignals(False)

    def _open_kde_shortcuts(self):
        import shutil
        import subprocess

        for cmd in (["systemsettings", "kcm_keys"], ["kcmshell6", "kcm_keys"], ["kcmshell5", "kcm_keys"]):
            if shutil.which(cmd[0]):
                subprocess.Popen(cmd)
                return
        error_box(self, "Die KDE-Systemeinstellungen wurden nicht gefunden.")

    def _save_hotkey(self, action, seq: str):
        hotkeys = dict(self.config["hotkeys"])
        hotkeys[action] = seq
        self.config["hotkeys"] = hotkeys
        problems = self.hotkeys.apply(hotkeys)
        self.hotkey_status.setText("\n".join(problems))
        self.hotkeys_changed.emit()

    # ================================================================ Monitor 2
    def _output_group(self):
        box = QGroupBox("Bildschirm")
        lay = QVBoxLayout(box)
        cfg = self.config["output"]
        taskbar = QCheckBox("Taskleiste dort ausblenden (Windows)")
        taskbar.setToolTip("Windows-Taskleiste auf dem Bildschirm (Monitor 2) ausblenden")
        taskbar.setChecked(bool(cfg.get("hide_taskbar", True)))
        taskbar.setEnabled(IS_WINDOWS)
        badge = QCheckBox("Standbild-Symbol zeigen")
        badge.setChecked(bool(cfg.get("freeze_badge", True)))
        cursor = QCheckBox("Mauszeiger beim Spiegeln zeigen")
        cursor.setChecked(bool(cfg.get("mirror_cursor", True)))
        confine = QCheckBox("Maus bleibt auf Monitor 1 (außer „Erweitern“)")
        confine.setChecked(bool(cfg.get("confine_cursor", True)))
        guard = self.controller.cursor_guard
        if guard.wayland_gap:
            confine.setToolTip("KDE/Wayland: AluPC rückt den Bildschirm dafür mit Abstand weg – über die Lücke kommt "
                               "die Maus nicht. Bei „Erweitern“ und beim Beenden geht die Lücke wieder zu.")
        elif not guard.supported:
            confine.setEnabled(False)
            confine.setToolTip("KDE erlaubt unter Wayland keinem Programm, die Maus festzuhalten. Beim Anmelden "
                               "die Sitzung „Plasma (X11)“ wählen – dort hält AluPC sie auf Monitor 1.")

        def save(*_):
            self.config["output"] = {**self.config["output"], "hide_taskbar": taskbar.isChecked(),
                                     "freeze_badge": badge.isChecked(), "mirror_cursor": cursor.isChecked(),
                                     "confine_cursor": confine.isChecked()}
            self.controller.apply_output_settings()

        for w in (taskbar, badge, cursor, confine):
            w.toggled.connect(save)
            lay.addWidget(w)
        if not confine.isEnabled():
            note = QLabel("Maus festhalten: unter Wayland nicht möglich · "
                          "mit „Plasma (X11)“ beim Anmelden geht es")
            note.setObjectName("Muted")
            note.setWordWrap(True)
            lay.addWidget(note)

        from .. import stage

        look = QComboBox()
        for key, label in stage.LOOKS.items():
            look.addItem(label, key)
        look.setCurrentIndex(max(0, look.findData(cfg.get("stage", "buehne"))))
        look.setToolTip("Hintergrund aller Anzeigen für das Publikum (Abstimmung, Glücksrad, Uhr, Text, QR …) – "
                        "gleich, egal welches Design die AluPC-App hat")

        def save_look(_i):
            self.config["output"] = {**self.config["output"], "stage": look.currentData()}
            self.controller.apply_output_settings()

        look.currentIndexChanged.connect(save_look)
        look_row = QHBoxLayout()
        look_row.addWidget(QLabel("Publikum sieht:"))
        look_row.addWidget(look, 1)
        lay.addLayout(look_row)

        hint = QLabel("„Computer sperren“ = wie Win+L (gilt auch für den Bildschirm)")
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        lay.addWidget(hint)
        return box
