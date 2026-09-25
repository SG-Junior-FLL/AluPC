"""Mediensteuerung im Hauptfenster: Läuft auf Monitor 2 ein Video (auch in einer eigenen Szene),
erscheint eine Leiste mit Pause/Weiter, ±10 Sekunden und einer Zeitleiste zum Springen."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QSlider, QToolButton, QWidget

from ..sources import video_sources
from . import icons, theme

SKIP_MS = 10_000


def fmt(ms: int) -> str:
    s = max(0, int(ms)) // 1000
    h, rest = divmod(s, 3600)
    m, s = divmod(rest, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


class MediaBar(QWidget):
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.setObjectName("Card")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.videos = []

        def tool(icon_name, tip, slot, text=""):
            b = QToolButton()
            b.setAutoRaise(True)
            b.setIconSize(QSize(20, 20))
            b.setToolTip(tip)
            b.setProperty("icon_name", icon_name)
            if text:
                b.setText(text)
                b.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            b.clicked.connect(slot)
            return b

        self.back_btn = tool("rewind", "10 Sekunden zurück", lambda: self._skip(-SKIP_MS), "10 s")
        self.play_btn = tool("pause", "Pause / Weiter", self._toggle)
        self.play_btn.setIconSize(QSize(26, 26))
        self.fwd_btn = tool("fastforward", "10 Sekunden vor", lambda: self._skip(SKIP_MS), "10 s")
        self.fwd_btn.setLayoutDirection(Qt.RightToLeft)
        self.pos_label = QLabel("0:00")
        self.pos_label.setMinimumWidth(52)
        self.pos_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 0)
        self.slider.setToolTip("Ziehen oder klicken, um im Video zu springen")
        self.slider.sliderReleased.connect(lambda: self._seek(self.slider.value()))
        self.slider.actionTriggered.connect(self._slider_action)
        self.dur_label = QLabel("0:00")
        self.dur_label.setMinimumWidth(52)
        self.which = QComboBox()
        self.which.setToolTip("Welches Video steuern? (Szene mit mehreren Videos)")
        self.which.currentIndexChanged.connect(lambda _i: self.refresh())
        self.title = QLabel()
        self.title.setObjectName("Muted")
        self.title.setMaximumWidth(220)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 8, 16, 8)
        lay.setSpacing(8)
        for w in (self.back_btn, self.play_btn, self.fwd_btn, self.pos_label):
            lay.addWidget(w)
        lay.addWidget(self.slider, 1)
        lay.addWidget(self.dur_label)
        lay.addWidget(self.which)
        lay.addWidget(self.title)

        self.timer = QTimer(self, interval=250)
        self.timer.timeout.connect(self.refresh)
        self.timer.start()
        self.apply_theme()
        self.sync()

    def apply_theme(self):
        t = theme.current()
        for b in (self.back_btn, self.play_btn, self.fwd_btn):
            b.setIcon(icons.icon(b.property("icon_name"), t.text, 26))

    # ------------------------------------------------------------ Welche Videos laufen?
    def sync(self):
        """Nach jedem Inhaltswechsel: Videos auf Monitor 2 suchen, Leiste zeigen/verstecken."""
        c = self.controller
        self.videos = video_sources(c.output.content) if c.mode == "content" else []
        self.setVisible(bool(self.videos))
        self.which.blockSignals(True)
        self.which.clear()
        for i, v in enumerate(self.videos, 1):
            self.which.addItem(f"Video {i}: {v.title}")
        self.which.blockSignals(False)
        self.which.setVisible(len(self.videos) > 1)
        self.title.setVisible(len(self.videos) == 1)
        if len(self.videos) == 1:
            self.title.setText(self.videos[0].title)
        self.refresh()

    def current(self):
        i = max(0, self.which.currentIndex())
        return self.videos[i] if i < len(self.videos) else None

    def refresh(self):
        video = self.current()
        if video is None or not self.isVisible():
            return
        try:
            dur, pos = video.duration(), video.position()
            playing = video.playing()
        except RuntimeError:  # Video wurde gerade beendet
            self.sync()
            return
        if not self.slider.isSliderDown():
            self.slider.setRange(0, dur)
            self.slider.setValue(pos)
        self.pos_label.setText(fmt(self.slider.value() if self.slider.isSliderDown() else pos))
        self.dur_label.setText(fmt(dur))
        name = "pause" if playing else "play"
        if self.play_btn.property("icon_name") != name:
            self.play_btn.setProperty("icon_name", name)
            self.play_btn.setIcon(icons.icon(name, theme.current().text, 26))

    # ------------------------------------------------------------ Bedienung
    def _toggle(self):
        video = self.current()
        if video is not None:
            video.toggle_play()
            self.refresh()

    def _skip(self, ms: int):
        video = self.current()
        if video is not None:
            video.skip(ms)
            self.refresh()

    def _seek(self, ms: int):
        video = self.current()
        if video is not None:
            video.seek_to(ms)
            self.refresh()

    def _slider_action(self, action):
        # Klick neben den Regler (Seite vor/zurück) → sofort springen
        if action in (QSlider.SliderPageStepAdd, QSlider.SliderPageStepSub,
                      QSlider.SliderSingleStepAdd, QSlider.SliderSingleStepSub):
            QTimer.singleShot(0, lambda: self._seek(self.slider.value()))
