"""Live-Anzeige der Tastenbox unten links am Hauptmonitor – sieht aus wie das Tastenfeld: 3 × 3 Tasten mit ihren
Funktionen, die gedrückte Taste leuchtet. Wartet eine Taste, weil eine Tastenfolge weitergehen könnte, läuft ein
Wartebalken und die möglichen nächsten Tasten sind umrandet; Code-Eingabe, ausgelöste Wenn → Dann-Regel und auf
Wunsch der Regler stehen in der Kopfzeile. Blendet sich nach kurzer Zeit aus, Klicks gehen hindurch, nimmt nie den
Fokus. Zeichnen ist billig (alles vorberechnet) – die Anzeige darf beim schnellen Tippen nicht bremsen.

Einstellung: Seite Tastenbox → „Eingaben unten links am Monitor anzeigen“ (tasten.anzeige, tasten.anzeige_regler).
"""

from __future__ import annotations

import time

from PySide6.QtCore import QElapsedTimer, QRectF, Qt, QTimer, QVariantAnimation
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QWidget

from ..automations import KEY_POS
from . import theme
from .widgets import font

TITLE = "AluPC Tastenbox-Anzeige"
SHOW_MS = 2000  # so lange bleibt die Anzeige nach der letzten Eingabe
CELL_W, CELL_H, GAP, PAD, HEAD = 116, 54, 6, 12, 50
W = PAD * 2 + CELL_W * 3 + GAP * 2
H = HEAD + PAD + CELL_H * 3 + GAP * 2 + 16
MARGIN = 24
LABEL_W, LABEL_H = CELL_W - 12, CELL_H - 17  # Platz für den Funktionsnamen in einer Taste


def fit_label(text: str) -> tuple[QFont, str]:
    """Funktionsname passend für eine Taste: erst kleinere Schrift, sonst nach 3 Zeilen mit „…“ kürzen."""
    flags = Qt.AlignCenter | Qt.TextWordWrap
    for size in (8.5, 7.8, 7.2):
        f = font(size, QFont.DemiBold)
        if QFontMetrics(f).boundingRect(0, 0, LABEL_W, 1000, flags, text).height() <= LABEL_H:
            return f, text
    f = font(7.2, QFont.DemiBold)
    fm = QFontMetrics(f)
    words, lines, cur = text.split(), [], ""
    for word in words:
        test = (cur + " " + word).strip()
        if fm.horizontalAdvance(test) <= LABEL_W or not cur:
            cur = test
        else:
            lines.append(cur)
            cur = word
    lines.append(cur)
    max_lines = max(1, LABEL_H // fm.height())
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = fm.elidedText(lines[-1] + " …", Qt.ElideRight, LABEL_W)
    return f, "\n".join(lines)


def describe_event(event: dict, labels: dict[str, str]) -> tuple[str, str, int | None]:
    """Ereignis → (Überschrift, Zeile darunter, gedrückte Taste oder None)."""
    art = event.get("art")
    if art == "taste":
        n = int(event["n"])
        title = f"Taste {n} · {KEY_POS.get(n, '')}" + (" · lang" if event.get("lang") else "")
        if event.get("folge"):
            more = event.get("weiter") or ""
            return title, "Folge " + "-".join(event["folge"]) + (" … weiter mit " + " / ".join(more) if more else
                                                                  " … kurz warten"), n
        action = event.get("aktion") or ""
        return title, labels.get(action, action) if action else "– nicht belegt –", n
    if art == "freigabe":
        keys = event.get("tasten") or ""
        return "Keine Folge", "Ausgeführt: Taste " + ", ".join(keys), int(keys[-1]) if keys else None
    if art == "code":
        code = event.get("code") or ""
        if event.get("fertig"):
            return "Code-Eingabe", ("Code " + "-".join(code)) if code else "abgebrochen", None
        return "Code-Eingabe", ("-".join(code) + " …") if code else "Ziffern tippen, dann kurz warten …", None
    if art == "regel":
        return "Wenn → Dann", str(event.get("name", "")), None
    if art == "regler":
        return "Regler", f"{event.get('ziel', '')}: {event.get('wert')} %", None
    if art == "zahl":
        value = event.get("wert")
        return "Regler-Zahl", "–" if value is None else f"{int(value):03d}", None
    return "", "", None


class BoxOsd(QWidget):
    def __init__(self, controller):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
                         | Qt.WindowTransparentForInput | Qt.WindowDoesNotAcceptFocus)
        self.controller = controller
        self.setWindowTitle(TITLE)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.resize(W, H)
        self.title = self.detail = ""
        self.key: int | None = None
        self.trail = ""  # Tasten der laufenden Folge
        self.next_keys = ""  # damit kann die Folge weitergehen
        self.code_mode = False
        self.caps: dict[int, str] = {}  # Taste → Funktion (Text auf der Taste)
        self._fitted: dict[int, tuple[QFont, str]] = {}
        self.alpha = 0.0
        self._wait_ms = 0
        self._wait_clock = QElapsedTimer()
        self._wait_tick = QTimer(self, interval=33, timeout=self._tick)  # nur während des Wartens
        self._anim = QVariantAnimation(self, duration=200)
        self._anim.valueChanged.connect(self._set_alpha)
        self._timer = QTimer(self, singleShot=True, timeout=lambda: self._fade(0.0))
        self._placed = None
        self._labels: dict[str, str] | None = None
        self._labels_at = 0.0
        controller.box_input.connect(self.show_event)

    def enabled(self) -> bool:
        return bool(self.controller.config["tasten"].get("anzeige", False))

    def labels(self) -> dict[str, str]:
        # Namen (Szenen, Regeln, Klänge …) höchstens alle 5 s neu lesen – nicht bei jedem Tastendruck
        if self._labels is None or time.monotonic() - self._labels_at > 5:
            from .voice_custom import action_choices

            self._labels = dict(action_choices(self.controller.config))
            self._labels_at = time.monotonic()
        return self._labels

    def show_event(self, event: dict) -> None:
        if not self.enabled():
            if self.isVisible():
                self.hide()
            return
        art = event.get("art")
        if art == "regler" and not self.controller.config["tasten"].get("anzeige_regler", True):
            return
        labels = self.labels()
        title, detail, key = describe_event(event, labels)
        if not title:
            return
        keys = self.controller.box_keys()
        caps = {n: labels.get(keys.get(str(n), ""), keys.get(str(n), "")) for n in range(1, 10)}
        if caps != self.caps:  # Schrift/Kürzung nur neu ausrechnen, wenn sich die Belegung geändert hat
            self.caps = caps
            self._fitted = {n: fit_label(text or "–") for n, text in caps.items()}
        self.title, self.detail, self.key = title, detail, key
        self.trail = event.get("folge", "") if art == "taste" else ""
        self.next_keys = event.get("weiter", "") if art == "taste" else ""
        self.code_mode = art == "code" and not event.get("fertig")
        self._wait_ms = int(event.get("warten_ms") or 0) if art == "taste" else 0
        if self._wait_ms > 0:
            self._wait_clock.start()
            self._wait_tick.start()
        else:
            self._wait_tick.stop()
        self._place()
        self._fade(1.0)
        self._timer.start(SHOW_MS + self._wait_ms)
        self.update()

    def _tick(self) -> None:
        if self._wait_clock.elapsed() >= self._wait_ms:
            self._wait_tick.stop()
        self.update()

    def _place(self) -> None:
        screen = self.controller.main_screen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        rect = (geo.x() + MARGIN, geo.y() + geo.height() - H - MARGIN, W, H)
        from ..platform.linux_display import is_wayland

        if is_wayland():
            # Wayland: Programme dürfen ihr Fenster nicht selbst setzen – KWin legt es hin (einmal je Monitor-Lage);
            # die Anzeige bleibt dafür sichtbar und wird nur durchsichtig gezeichnet
            if not self.isVisible():
                self.show()
            if self._placed != rect:
                self._placed = rect
                from ..platform import linux_windows
                from .util import run_async

                run_async(lambda: linux_windows.kwin_window_props(TITLE, above=True, geo=rect), None,
                          lambda _e: None)
        else:
            if self.geometry().getRect() != rect:
                self.setGeometry(*rect)
            if not self.isVisible():
                self.show()
                from ..platform.window_tools import keep_on_top

                keep_on_top(self)

    def _fade(self, to: float) -> None:
        self._anim.stop()
        self._anim.setStartValue(self.alpha)
        self._anim.setEndValue(to)
        self._anim.start()

    def _set_alpha(self, value) -> None:
        self.alpha = float(value)
        self.update()
        from ..platform.linux_display import is_wayland

        if self.alpha <= 0.001 and self._anim.endValue() == 0.0 and not is_wayland() and self.isVisible():
            self.hide()  # unter Wayland sichtbar lassen (sonst landet sie beim nächsten Mal woanders)

    def paintEvent(self, _e):
        if self.alpha <= 0.001:
            return
        t = theme.current()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setOpacity(self.alpha)
        bg = QColor(t.surface)
        bg.setAlpha(240)
        p.setPen(QPen(QColor(t.border), 1))
        p.setBrush(bg)
        p.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 14, 14)
        accent = QColor(t.accent)
        # Kopfzeile
        p.setPen(QColor(t.muted))
        p.setFont(font(9, QFont.DemiBold))
        p.drawText(QRectF(PAD + 2, 8, W - 2 * PAD, 16), Qt.AlignLeft | Qt.AlignVCenter, self.title)
        p.setPen(QColor(t.text))
        p.setFont(font(12.5, QFont.Bold))
        text = p.fontMetrics().elidedText(self.detail, Qt.ElideRight, W - 2 * PAD - 4)
        p.drawText(QRectF(PAD + 2, 24, W - 2 * PAD, 22), Qt.AlignLeft | Qt.AlignVCenter, text)
        # Tastenfeld wie auf der Box
        number = font(8, QFont.Bold)
        for n in range(1, 10):
            r, c = (n - 1) // 3, (n - 1) % 3
            cell = QRectF(PAD + c * (CELL_W + GAP), HEAD + r * (CELL_H + GAP), CELL_W, CELL_H)
            pressed, in_trail, nxt = n == self.key, str(n) in self.trail, str(n) in self.next_keys
            fill = QColor(accent) if pressed else QColor(t.surface2)
            if in_trail and not pressed:
                fill = QColor(accent)
                fill.setAlpha(90)
            p.setBrush(fill)
            p.setPen(QPen(accent, 2) if nxt else QPen(QColor(t.border), 1))
            p.drawRoundedRect(cell, 8, 8)
            p.setPen(QColor("#ffffff") if pressed else QColor(t.muted))
            p.setFont(number)
            p.drawText(cell.adjusted(7, 4, -6, 0), Qt.AlignLeft | Qt.AlignTop, str(n))
            p.setPen(QColor("#ffffff") if pressed else QColor(t.text))
            f, label = (font(8.5, QFont.DemiBold), f"Ziffer {n}") if self.code_mode else \
                self._fitted.get(n, (font(8.5, QFont.DemiBold), "–"))
            p.setFont(f)
            p.drawText(QRectF(cell.x() + 6, cell.y() + 14, LABEL_W, LABEL_H), Qt.AlignCenter | Qt.TextWordWrap, label)
        # Wartebalken: Taste könnte eine Folge beginnen – ihre eigene Aktion kommt erst danach
        if self._wait_ms > 0:
            left = max(0.0, 1 - self._wait_clock.elapsed() / self._wait_ms)
            p.setPen(Qt.NoPen)
            p.setBrush(accent)
            p.drawRoundedRect(QRectF(PAD, H - 12, (W - 2 * PAD) * left, 4), 2, 2)
        p.end()
