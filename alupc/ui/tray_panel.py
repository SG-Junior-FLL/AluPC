"""Schnellfenster der Taskleiste: Klick aufs AluPC-Symbol öffnet eine kleine Steuerzentrale –
Live-Bild von Monitor 2, Schalter, Modi, Szenen, Timer, Ton, Weiterschalten.

(Rechtsklick zeigt weiter das normale Menü – unter KDE zeichnet Plasma dieses selbst.)"""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPainterPath
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSlider,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from . import icons, theme

WIDTH = 372


def is_wayland() -> bool:
    return QGuiApplication.platformName().startswith("wayland")


class Preview(QLabel):
    """Kleines Live-Bild von Monitor 2 mit abgerundeten Ecken."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.image = None
        self.icon_name = "monitor"
        self.setFixedSize(132, 74)

    def set(self, image, icon_name: str):
        self.image = image if image is not None and not image.isNull() else None
        self.icon_name = icon_name
        self.update()

    def paintEvent(self, _e):
        t = theme.current()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        path = QPainterPath()
        path.addRoundedRect(self.rect().adjusted(0, 0, -1, -1), 10, 10)
        p.fillPath(path, QColor("#000000" if self.image is not None else t.surface2))
        if self.image is not None:
            p.setClipPath(path)
            img = self.image.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            p.drawImage((self.width() - img.width()) // 2, (self.height() - img.height()) // 2, img)
        else:
            icons.paint(p, self.icon_name, self.rect().adjusted(46, 17, -46, -17), t.accent, 1.8)
        p.end()


class TrayPanel(QFrame):
    def __init__(self, window):
        flags = Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        super().__init__(None, flags)
        self.window = window
        self.controller = window.controller
        self.setObjectName("TrayPanel")
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedWidth(WIDTH)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        self.card = QFrame()
        self.card.setObjectName("TrayCard")
        outer.addWidget(self.card)
        lay = QVBoxLayout(self.card)
        lay.setContentsMargins(14, 14, 14, 12)
        lay.setSpacing(10)

        # --- Kopf: Live-Bild, Zustand, schließen
        head = QHBoxLayout()
        head.setSpacing(12)
        self.preview = Preview()
        head.addWidget(self.preview)
        info = QVBoxLayout()
        info.setSpacing(2)
        self.where = QLabel()
        self.where.setObjectName("TrayMuted")
        self.title = QLabel()
        self.title.setObjectName("TrayTitle")
        self.pill = QLabel()
        self.pill.setObjectName("TrayPill")
        info.addWidget(self.where)
        info.addWidget(self.title)
        info.addWidget(self.pill, 0, Qt.AlignLeft)
        info.addStretch(1)
        head.addLayout(info, 1)
        close = QToolButton()
        close.setObjectName("TrayClose")
        close.setToolTip("Schließen (Esc)")
        close.clicked.connect(self.hide)
        self.close_btn = close
        head.addWidget(close, 0, Qt.AlignTop)
        lay.addLayout(head)

        # --- Schalter
        c = self.controller
        self.toggles: dict[str, QToolButton] = {}
        grid = QGridLayout()
        grid.setSpacing(6)
        for i, (key, icon_name, text, slot) in enumerate([
            ("freeze", "snowflake", "Standbild", c.toggle_freeze),
            ("black", "eye_off", "Schwarz", c.toggle_privacy),
            ("saver", "moon", "Schoner", c.toggle_screensaver),
            ("pip", "pip", "Mini-Bild", c.toggle_pip),
        ]):
            b = self._tile(icon_name, text, checkable=True)
            b.clicked.connect(lambda _=False, s=slot: self._run(s, keep=True))
            self.toggles[key] = b
            grid.addWidget(b, 0, i)
        lay.addLayout(grid)

        # --- Zeigen
        lay.addWidget(self._section("Zeigen"))
        modes = QGridLayout()
        modes.setSpacing(6)
        w = self.window
        self.modes: dict[str, QToolButton] = {}
        for i, (key, icon_name, text, slot) in enumerate([
            ("mirror", "mirror", "Spiegeln", c.mirror),
            ("extend", "extend", "Erweitern", c.extend),
            ("camera", "camera", "Kamera", c.start_camera),
            ("text", "text", "Text", w.open_text_dialog),
            ("airplay", "phone", "iPhone", c.start_airplay),
            ("cast", "qr", "Handy", c.start_cast),
            ("timer", "timer", "Timer", w._timer_clicked),
            ("draw", "edit", "Zeichnen", w.open_presenter),
        ]):
            b = self._tile(icon_name, text)
            b.clicked.connect(lambda _=False, s=slot, k=key: self._run(s, keep=k in ("timer",)))
            self.modes[key] = b
            modes.addWidget(b, i // 4, i % 4)
        lay.addLayout(modes)

        # --- Weiterschalten (Ablauf, Quiz …) – nur wenn es etwas gibt
        self.step_box = QWidget()
        step = QHBoxLayout(self.step_box)
        step.setContentsMargins(0, 0, 0, 0)
        step.setSpacing(6)
        self.step_prev = self._small("back", "Zurück")
        self.step_prev.clicked.connect(lambda: c.step_page(-1))
        self.step_label = QLabel()
        self.step_label.setObjectName("TrayMuted")
        self.step_label.setAlignment(Qt.AlignCenter)
        self.step_next = self._small("forward", "Weiter", primary=True)
        self.step_next.clicked.connect(lambda: c.step_page(1))
        step.addWidget(self.step_prev)
        step.addWidget(self.step_label, 1)
        step.addWidget(self.step_next)
        lay.addWidget(self.step_box)

        # --- Szenen
        self.scene_head = self._section("Szenen")
        lay.addWidget(self.scene_head)
        self.scene_box = QWidget()
        self.scene_grid = QGridLayout(self.scene_box)
        self.scene_grid.setContentsMargins(0, 0, 0, 0)
        self.scene_grid.setSpacing(6)
        lay.addWidget(self.scene_box)

        # --- Ton (nur wenn gerade etwas mit Ton läuft)
        self.volume_box = QWidget()
        vol = QHBoxLayout(self.volume_box)
        vol.setContentsMargins(0, 0, 0, 0)
        vol.setSpacing(8)
        self.mute = self._small("sound", "")
        self.mute.setCheckable(True)
        self.mute.setToolTip("Ton aus/an")
        self.mute.clicked.connect(lambda on: c.set_media_volume(muted=on))
        self.volume = QSlider(Qt.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.sliderReleased.connect(lambda: c.set_media_volume(volume=self.volume.value(), muted=False))
        self.volume_label = QLabel()
        self.volume_label.setObjectName("TrayMuted")
        self.volume_label.setFixedWidth(40)
        self.volume.valueChanged.connect(lambda v: self.volume_label.setText(f"{v} %"))
        vol.addWidget(self.mute)
        vol.addWidget(self.volume, 1)
        vol.addWidget(self.volume_label)
        lay.addWidget(self.volume_box)

        # --- Fuß
        line = QFrame()
        line.setObjectName("TrayLine")
        line.setFixedHeight(1)
        lay.addWidget(line)
        foot = QHBoxLayout()
        foot.setSpacing(6)
        for icon_name, text, slot, primary in [
            ("home", "AluPC öffnen", window.show_normal_front, True),
            ("lock", "Sperren", window.lock, False),
            ("power", "Beenden", QApplication.instance().quit, False),
        ]:
            b = self._small(icon_name, text, primary=primary)
            b.clicked.connect(lambda _=False, s=slot: self._run(s))
            foot.addWidget(b, 1 if primary else 0)
        lay.addLayout(foot)

        self._preview_timer = QTimer(self, interval=1000)
        self._preview_timer.timeout.connect(self._update_preview)
        self.controller.changed.connect(self.sync)
        self.apply_style()

    # ------------------------------------------------------------ Bausteine
    def _tile(self, icon_name: str, text: str, checkable: bool = False) -> QToolButton:
        """Kachel: Symbol über kurzem Text."""
        b = QToolButton()
        b.setText(text)
        b.setObjectName("TrayTile")
        b.setProperty("iconName", icon_name)
        b.setCheckable(checkable)
        b.setCursor(Qt.PointingHandCursor)
        b.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        b.setIconSize(QSize(22, 22))
        b.setMinimumHeight(62)
        b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        b.setToolTip(text)
        return b

    def _small(self, icon_name: str, text: str, primary: bool = False) -> QPushButton:
        b = QPushButton(text)
        b.setObjectName("TrayPrimary" if primary else "TraySmall")
        b.setProperty("iconName", icon_name)
        b.setCursor(Qt.PointingHandCursor)
        b.setIconSize(QSize(16, 16))
        return b

    def _section(self, text: str) -> QLabel:
        label = QLabel(text.upper())
        label.setObjectName("TraySection")
        return label

    def _run(self, slot, keep: bool = False):
        slot()
        if not keep:
            self.hide()

    # ------------------------------------------------------------ Aussehen
    def apply_style(self):
        t = theme.current()
        soft = QColor(t.accent)
        accent_soft = f"rgba({soft.red()},{soft.green()},{soft.blue()},0.18)"
        accent_line = f"rgba({soft.red()},{soft.green()},{soft.blue()},0.55)"
        self.setStyleSheet(f"""
#TrayCard {{ background: {t.surface}; border: 1px solid {t.border}; border-radius: 18px; }}
#TrayTitle {{ font-size: 11pt; font-weight: 700; color: {t.text}; }}
#TrayMuted {{ color: {t.muted}; font-size: 8.5pt; }}
#TraySection {{ color: {t.muted}; font-size: 7.5pt; font-weight: 800; letter-spacing: 1px; padding-top: 2px; }}
#TrayPill {{ border-radius: 8px; padding: 2px 8px; font-size: 7.5pt; font-weight: 800; }}
#TrayLine {{ background: {t.border}; }}
QToolButton#TrayTile {{ background: {t.surface2}; border: 1px solid transparent; border-radius: 12px;
    padding: 7px 2px 6px 2px; font-size: 8pt; font-weight: 600; color: {t.text}; }}
QToolButton#TrayTile:hover {{ border-color: {accent_line}; }}
QToolButton#TrayTile:checked {{ background: {accent_soft}; border-color: {t.accent}; color: {t.accent}; }}
QPushButton#TraySmall {{ background: {t.surface2}; border: none; border-radius: 10px; padding: 7px 10px;
    font-weight: 600; color: {t.text}; }}
QPushButton#TraySmall:hover {{ background: {accent_soft}; }}
QPushButton#TraySmall:checked {{ background: {accent_soft}; color: {t.accent}; }}
QPushButton#TrayPrimary {{ background: {t.accent}; border: none; border-radius: 10px; padding: 7px 12px;
    font-weight: 700; color: #ffffff; }}
QPushButton#TrayScene {{ background: {t.surface2}; border: 1px solid transparent; border-radius: 10px;
    padding: 7px 8px; font-weight: 600; color: {t.text}; text-align: left; }}
QPushButton#TrayScene:hover {{ border-color: {accent_line}; }}
QPushButton#TrayScene:checked {{ background: {accent_soft}; border-color: {t.accent}; color: {t.accent}; }}
QToolButton#TrayClose {{ border: none; border-radius: 8px; padding: 4px; }}
QToolButton#TrayClose:hover {{ background: {t.surface2}; }}
QSlider::groove:horizontal {{ height: 4px; background: {t.border}; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {t.accent}; border-radius: 2px; }}
QSlider::handle:horizontal {{ width: 14px; margin: -5px 0; border-radius: 7px; background: {t.accent}; }}
""")
        self.close_btn.setIcon(icons.icon("x", t.muted, 16))
        for b in self.findChildren(QPushButton) + self.findChildren(QToolButton):
            name = b.property("iconName")
            if name:
                color = "#ffffff" if b.objectName() == "TrayPrimary" else t.text
                b.setIcon(icons.icon(name, color, b.iconSize().width()))

    # ------------------------------------------------------------ Zustand
    def sync(self, *_):
        if not self.isVisible():
            return
        c = self.controller
        t = theme.current()
        out = c.output_screen()
        self.where.setText(f"MONITOR 2 · {out.name()}" if out else "KEIN MONITOR 2")
        from PySide6.QtGui import QFontMetrics

        full = c.describe() if out else "Nicht angeschlossen"
        self.title.setToolTip(full)
        self.title.setText(QFontMetrics(self.title.font()).elidedText(full, Qt.ElideRight, WIDTH - 228))
        state = ("SCHWARZ", "#64748b") if c.privacy else ("STANDBILD", "#0ea5e9") if c.frozen else \
            ("SCHONER", "#6366f1") if c.screensaver.active else ("LIVE", t.success) if c.mode == "content" else \
            ("DESKTOP", t.muted)
        if out is None:
            state = ("FEHLT", t.danger)
        col = QColor(state[1])
        self.pill.setText(f"● {state[0]}")
        self.pill.setStyleSheet(f"background: rgba({col.red()},{col.green()},{col.blue()},0.16); color: {state[1]};")
        pip_on = bool(c.pip and c.pip.isVisible())
        for key, on in (("freeze", c.frozen), ("black", c.privacy), ("saver", c.screensaver.active),
                        ("pip", pip_on)):
            self.toggles[key].setChecked(on)
        typ = c.content.get("type") if c.mode == "content" and c.content else None
        mirror = bool(c.content and c.content.get("mirror")) and c.mode == "content"
        active = {"mirror": mirror, "extend": c.mode == "desktop", "camera": typ == "camera", "text": typ == "text",
                  "airplay": typ == "airplay", "cast": typ == "cast", "timer": typ == "countdown"}
        for key, b in self.modes.items():
            b.setProperty("on", active.get(key, False))
            b.setCheckable(True)
            b.setChecked(active.get(key, False))
        for b in list(self.toggles.values()) + list(self.modes.values()):  # aktives Symbol in Akzentfarbe
            b.setIcon(icons.icon(b.property("iconName"), t.accent if b.isChecked() else t.text, 22))
        label = c.step_label()
        self.step_box.setVisible(bool(label))
        self.step_label.setText(label)
        self._fill_scenes(typ)
        state_media = c.media_state()
        self.volume_box.setVisible(state_media is not None)
        if state_media is not None:
            self.volume.blockSignals(True)
            self.volume.setValue(int(state_media["volume"]))
            self.volume.blockSignals(False)
            self.volume_label.setText(f"{int(state_media['volume'])} %")
            self.mute.setChecked(state_media["muted"])
            self.mute.setIcon(icons.icon("mute" if state_media["muted"] else "sound", t.text, 16))
        self._update_preview()
        self.adjustSize()

    def _fill_scenes(self, typ):
        while self.scene_grid.count():
            item = self.scene_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        c = self.controller
        names = c.config.scene_names()[:6]
        current = c.content.get("scene", "") if typ == "scene" else ""
        self.scene_head.setVisible(bool(names))
        self.scene_box.setVisible(bool(names))
        t = theme.current()
        for i, name in enumerate(names):
            b = QPushButton(name)
            b.setObjectName("TrayScene")
            b.setCheckable(True)
            b.setChecked(name == current)
            b.setCursor(Qt.PointingHandCursor)
            b.setIcon(icons.icon("scenes", t.accent if name == current else t.muted, 16))
            b.setToolTip(name)
            b.clicked.connect(lambda _=False, n=name: self._run(lambda: c.show_source({"type": "scene", "scene": n})))
            self.scene_grid.addWidget(b, i // 2, i % 2)

    def _update_preview(self):
        from ..output_window import grab_scaled

        c = self.controller
        out = c.output
        image = None
        if out.isVisible() and (c.mode == "content" or c.privacy or c.frozen or c.screensaver.active):
            dpr = self.preview.devicePixelRatioF()
            image = grab_scaled(out, QSize(int(132 * dpr), int(74 * dpr)))
        self.preview.set(image, "extend" if c.mode == "desktop" else "monitor")

    # ------------------------------------------------------------ Öffnen / Schließen
    def popup_near(self, tray_rect: QRect | None, cursor: QPoint | None) -> None:
        """Neben dem Taskleisten-Symbol öffnen (Windows: über dem Symbol; Linux X11: am Mauszeiger;
        Wayland erlaubt keine eigene Position – dort entscheidet KWin)."""
        self.apply_style()
        self.show()
        self.sync()
        self.adjustSize()
        anchor = tray_rect.center() if tray_rect is not None and tray_rect.isValid() and not tray_rect.isEmpty() \
            else cursor
        screen = QGuiApplication.screenAt(anchor) if anchor is not None else None
        screen = screen or QGuiApplication.primaryScreen()
        area = screen.availableGeometry()
        size = self.sizeHint()
        if anchor is None or is_wayland():
            x, y = area.right() - size.width() - 8, area.bottom() - size.height() - 8
        else:
            x = anchor.x() - size.width() // 2
            # Taskleiste unten → darüber, oben → darunter
            y = anchor.y() - size.height() - 8 if anchor.y() > area.center().y() else anchor.y() + 16
        x = max(area.left() + 4, min(x, area.right() - size.width() - 4))
        y = max(area.top() + 4, min(y, area.bottom() - size.height() - 4))
        self.move(x, y)
        self.raise_()
        self.activateWindow()
        self._preview_timer.start()

    def hideEvent(self, e):
        self._preview_timer.stop()
        super().hideEvent(e)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.hide()
            return
        super().keyPressEvent(e)

    def changeEvent(self, e):
        # Klick daneben (Fenster verliert den Fokus) → zu, wie ein Menü
        from PySide6.QtCore import QEvent

        if e.type() == QEvent.ActivationChange and not self.isActiveWindow() and self.isVisible():
            QTimer.singleShot(150, self._hide_if_inactive)
        super().changeEvent(e)

    def _hide_if_inactive(self):
        if not self.isActiveWindow() and not QApplication.activePopupWidget() \
                and not (QApplication.activeModalWidget()):
            self.hide()

