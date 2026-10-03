"""„Sprache testen“: jeden Schritt der Sprachsteuerung live prüfen – und zeigen, wo es hängt.

Programm hat Spracherkennung? → Sprachmodell da? → Zuhören läuft? → welches Mikrofon, kommt Ton an (Pegel)? →
was wird erkannt (live)? → Startwort erkannt? → welcher Befehl würde ausgeführt? Im Test wird nichts ausgeführt.
„Bericht kopieren“ legt alles als Text in die Zwischenablage.
"""

from __future__ import annotations

import sys
import time

from PySide6.QtCore import QRectF, QTimer
from PySide6.QtGui import QColor, QGuiApplication, QPainter
from PySide6.QtWidgets import QDialog, QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from .. import __version__, voice
from . import theme
from .widgets import button, page_header, rounded

STEPS = [
    ("vosk", "Spracherkennung im Programm"),
    ("model", "Sprachmodell heruntergeladen"),
    ("running", "Zuhören läuft"),
    ("mic", "Mikrofon"),
    ("sound", "Ton kommt an"),
    ("heard", "Sprache erkannt"),
    ("wake", "Startwort erkannt"),
    ("command", "Befehl verstanden"),
]


class LevelBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.value = 0.0
        self.peak = 0.0
        self.setFixedHeight(16)

    def set(self, v: float) -> None:
        self.value = max(0.0, min(1.0, v))
        self.peak = max(self.peak * 0.97, self.value)
        self.update()

    def paintEvent(self, _e):
        t = theme.current()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(0, 3, 0, -3)
        p.fillPath(rounded(r, r.height() / 2), QColor(t.surface2))
        w = r.width() * min(1.0, self.value * 2.5)  # leise Sprache sichtbar machen
        color = "#ef4444" if self.value > 0.95 else ("#22c55e" if self.value > 0.02 else "#94a3b8")
        if w > 1:
            p.fillPath(rounded(QRectF(r.x(), r.y(), max(r.height(), w), r.height()), r.height() / 2), QColor(color))
        p.end()


class VoiceTestDialog(QDialog):
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.vc = controller.voice
        self.setWindowTitle("Sprache testen")
        self.setMinimumWidth(560)
        self.status: dict[str, tuple[str, str]] = {k: ("…", "") for k, _ in STEPS}
        self.heard_text = ""
        self.last_partial = ""
        self.max_level = 0.0
        self.started_at = time.monotonic()
        self._started_here = False
        lay = QVBoxLayout(self)
        lay.addWidget(page_header("Sprache testen", "Sag etwas – z. B. „Alu PC, Licht auf blau“. Im Test wird nichts "
                                  "ausgeführt.", "mic"))
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        self.marks, self.texts = {}, {}
        for row, (key, label) in enumerate(STEPS):
            mark = QLabel("…")
            mark.setFixedWidth(22)
            name = QLabel(label)
            text = QLabel("")
            text.setObjectName("Muted")
            text.setWordWrap(True)
            grid.addWidget(mark, row, 0)
            grid.addWidget(name, row, 1)
            grid.addWidget(text, row, 2)
            self.marks[key], self.texts[key] = mark, text
        grid.setColumnStretch(2, 1)
        lay.addLayout(grid)
        self.bar = LevelBar()
        lay.addWidget(self.bar)
        self.live = QLabel("")
        self.live.setWordWrap(True)
        f = self.live.font()
        f.setPointSizeF((f.pointSizeF() if f.pointSizeF() > 0 else 10) * 1.3)
        self.live.setFont(f)
        self.live.setMinimumHeight(48)
        lay.addWidget(self.live)
        self.hint = QLabel("")
        self.hint.setWordWrap(True)
        lay.addWidget(self.hint)
        row = QHBoxLayout()
        self.copy_btn = button("Bericht kopieren", "copy")
        self.copy_btn.clicked.connect(self.copy_report)
        close = button("Schließen", "x", primary=True)
        close.clicked.connect(self.accept)
        row.addWidget(self.copy_btn)
        row.addStretch(1)
        row.addWidget(close)
        lay.addLayout(row)

        vc = self.vc
        vc.dry_run = True
        vc.show_partial = True
        self._conns = [(vc.level, self._level), (vc.partial, self._partial), (vc.heard, self._heard),
                       (vc.dry_command, self._command), (vc.not_understood, self._not_understood),
                       (vc.state_changed, lambda _s: self._refresh())]
        for sig, slot in self._conns:
            sig.connect(slot)
        self._timer = QTimer(self, interval=500)
        self._timer.timeout.connect(self._refresh)
        self._timer.start()
        self._start()
        self._refresh()

    # ------------------------------------------------------------ Ablauf
    def _start(self) -> None:
        vc = self.vc
        if voice.vosk_available() and voice.model_ready() and not vc.running() and vc.state != "lädt":
            self._started_here = not vc.settings().get("on") and not vc.direct
            vc._force_start = True  # Zuhören auch ohne „Sprachbefehle an“ starten (nur für den Test)
            vc.start()

    def _level(self, v: float) -> None:
        self.bar.set(v)
        self.max_level = max(self.max_level, v)

    def _partial(self, text: str) -> None:
        self.last_partial = text
        self.live.setText(f"🎤 {text} …")

    def _heard(self, text: str) -> None:
        self.heard_text = text
        self.live.setText(f"🎤 {text}")
        words = voice.fold(text).split()
        wakes = tuple(self.vc.settings().get("wake") or ("monitor", "alupc"))
        self.status["heard"] = ("✓", text)
        if voice.wake_span(words, wakes) is not None:
            self.status["wake"] = ("✓", "ja")
        elif "(genau)" not in text:
            self.status["wake"] = ("✗", "nicht im Satz – „Alu PC“ oder „Monitor“ an den Anfang (oder Knopf „Zuhören“)")
        self._paint()

    def _command(self, command: str, label: str, _text: str) -> None:
        self.status["command"] = ("✓", f"{label} ({command}) – würde ausgeführt")
        self._paint()

    def _not_understood(self, text: str) -> None:
        self.status["command"] = ("✗", f"„{text}“ nicht verstanden – Beispiele stehen im Setup")
        self._paint()

    # ------------------------------------------------------------ Anzeige
    def _refresh(self) -> None:
        vc = self.vc
        st = self.status
        st["vosk"] = ("✓", "Vosk") if voice.vosk_available() else ("✗", "fehlt in dieser AluPC-Version")
        st["model"] = ("✓", voice.MODEL_NAME) if voice.model_ready() else (
            "✗", "fehlt – im Setup → Sprache „Herunterladen“")
        if vc.state == "hört zu":
            st["running"] = ("✓", "hört zu" + (" (ohne Startwort: Mikrofon-Schalter an)" if vc.direct else ""))
        elif vc.state == "lädt":
            st["running"] = ("…", "lädt das Sprachmodell …")
        else:
            st["running"] = ("✗", vc.state)
        if vc._device_name:
            st["mic"] = ("✓", vc._device_name + f" · {vc._in_format[0]} Hz")
        elif vc.state not in ("hört zu", "lädt"):
            st["mic"] = ("✗", "nicht geöffnet")
        if vc.state == "hört zu":
            waited = time.monotonic() - self.started_at
            if self.max_level > 0.02:
                st["sound"] = ("✓", f"lauteste Stelle {round(self.max_level * 100)} %")
            elif waited > 6:
                st["sound"] = ("✗", "Stille – falsches Mikrofon, stumm geschaltet oder zu leise? "
                                    + ("KDE: Systemeinstellungen → Audio → Eingabegeräte."
                                       if sys.platform.startswith("linux") else "Windows: Einstellungen → System → Sound → Eingabe."))
            else:
                st["sound"] = ("…", "sag etwas")
        cfg = vc.settings()
        hint = ""
        if cfg.get("only_voices") and cfg.get("voices") and not voice.spk_ready():
            hint = ("⚠ „Nur angelernte Stimmen“ ist an, aber die Stimmerkennung fehlt auf diesem PC – dann wird jeder "
                    "Befehl abgelehnt. Im Setup ausschalten oder Stimmerkennung herunterladen.")
        if vc.errors:
            hint += ("\n" if hint else "") + "Fehler: " + vc.errors[-1]
        self.hint.setText(hint)
        self._paint()

    def _paint(self) -> None:
        colors = {"✓": "#22c55e", "✗": "#ef4444", "…": "#94a3b8"}
        for key, _label in STEPS:
            mark, text = self.status[key]
            self.marks[key].setText(mark)
            self.marks[key].setStyleSheet(f"color: {colors.get(mark, '#94a3b8')}; font-weight: bold;")
            self.texts[key].setText(text)

    def report(self) -> str:
        vc = self.vc
        lines = [f"AluPC {__version__} · {sys.platform} · Sprache testen"]
        lines += [f"{mark} {label}: {self.status[key][1]}" for key, label in STEPS for mark in [self.status[key][0]]]
        lines.append(f"Pegel max: {round(self.max_level * 100)} % · Startwörter: {vc.settings().get('wake')}")
        lines.append(f"Erkennung: {vc.settings().get('stt', 'vosk')} · Whisper geladen: {vc.stt is not None}")
        lines.append(f"Mikrofon gewählt: {vc.settings().get('device') or 'Standard'} · neu geöffnet: {vc.mic_restarts}×")
        lines.append(f"Nur angelernte Stimmen: {bool(vc.settings().get('only_voices'))} · Stimmerkennung: "
                     f"{voice.spk_ready()}")
        try:
            from PySide6.QtMultimedia import QMediaDevices

            lines.append("Eingänge: " + " | ".join(d.description() for d in QMediaDevices.audioInputs()))
        except Exception:  # noqa: BLE001
            pass
        if vc.errors:
            lines.append("Fehler: " + " | ".join(vc.errors[-5:]))
        return "\n".join(lines)

    def copy_report(self) -> None:
        QGuiApplication.clipboard().setText(self.report())
        self.copy_btn.setText("Kopiert ✓")

    def done(self, result):
        vc = self.vc
        vc.dry_run = False
        vc.show_partial = False
        vc._force_start = False
        for sig, slot in self._conns:
            try:
                sig.disconnect(slot)
            except (RuntimeError, TypeError):
                pass
        if self._started_here and not vc.settings().get("on") and not vc.direct:
            vc.stop()
        super().done(result)
