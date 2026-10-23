"""Live-Anzeige der Tastenbox unten links am Hauptmonitor: welche Taste (mit Lage auf der Box), was sie tut,
laufende Tastenfolge, Code-Eingabe, ausgelöste Wenn → Dann-Regel, auf Wunsch der Regler. Blendet sich nach kurzer
Zeit aus. Klicks gehen durch die Anzeige hindurch; sie nimmt nie den Fokus.

Einstellung: Seite Tastenbox → „Eingaben unten links am Monitor anzeigen“ (tasten.anzeige, tasten.anzeige_regler).
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, QTimer, QVariantAnimation
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget

from ..automations import KEY_POS
from . import theme
from .widgets import font

TITLE = "AluPC Tastenbox-Anzeige"
SHOW_MS = 1800  # so lange bleibt die Anzeige nach der letzten Eingabe
W, H, MARGIN = 380, 96, 24


def describe_event(event: dict, labels: dict[str, str]) -> tuple[str, str, int | None]:
    """Ereignis → (Überschrift, Zeile darunter, Taste für das kleine 3 × 3-Feld oder None)."""
    art = event.get("art")
    if art == "taste":
        n = int(event["n"])
        title = f"Taste {n} · {KEY_POS.get(n, '')}" + (" · lang" if event.get("lang") else "")
        if event.get("folge"):
            return title, "Folge " + "-".join(event["folge"]) + " …", n
        action = event.get("aktion") or ""
        return title, labels.get(action, action) if action else "– nicht belegt –", n
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
        self.trail = ""  # Tasten der laufenden Folge (leuchten schwächer mit)
        self.alpha = 0.0
        self._anim = QVariantAnimation(self, duration=220)
        self._anim.valueChanged.connect(self._set_alpha)
        self._timer = QTimer(self, singleShot=True, timeout=lambda: self._fade(0.0))
        self._placed = None
        self._labels: dict[str, str] | None = None
        controller.box_input.connect(self.show_event)
        controller.changed.connect(lambda: setattr(self, "_labels", None))  # neue Szenen/Regeln → Namen neu

    def enabled(self) -> bool:
        return bool(self.controller.config["tasten"].get("anzeige", False))

    def labels(self) -> dict[str, str]:
        if self._labels is None:
            from .voice_custom import action_choices

            self._labels = dict(action_choices(self.controller.config))
        return self._labels

    def show_event(self, event: dict) -> None:
        if not self.enabled():
            if self.isVisible():
                self.hide()
            return
        if event.get("art") == "regler" and not self.controller.config["tasten"].get("anzeige_regler", True):
            return
        title, detail, key = describe_event(event, self.labels())
        if not title:
            return
        self.title, self.detail, self.key = title, detail, key
        self.trail = event.get("folge", "") if event.get("art") == "taste" else ""
        self._place()
        self._fade(1.0)
        self._timer.start(SHOW_MS)
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
        bg.setAlpha(235)
        p.setPen(QPen(QColor(t.border), 1))
        p.setBrush(bg)
        p.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 14, 14)
        accent = QColor(t.accent)
        p.setPen(Qt.NoPen)
        p.setBrush(accent)
        p.drawRoundedRect(QRectF(0, 14, 5, H - 28), 2.5, 2.5)
        # kleines 3 × 3-Feld: die gedrückte Taste leuchtet (zeigt die Lage auf der Box)
        cell, gap, x0, y0 = 18, 4, 18, (H - 3 * 18 - 2 * 4) / 2
        for n in range(1, 10):
            r, c = (n - 1) // 3, (n - 1) % 3
            if n == self.key:
                p.setBrush(accent)
            elif str(n) in self.trail:
                soft = QColor(accent)
                soft.setAlpha(110)
                p.setBrush(soft)
            else:
                p.setBrush(QColor(t.border))
            p.drawRoundedRect(QRectF(x0 + c * (cell + gap), y0 + r * (cell + gap), cell, cell), 4, 4)
        tx = x0 + 3 * cell + 2 * gap + 16
        p.setPen(QColor(t.muted))
        p.setFont(font(9.5, QFont.DemiBold))
        p.drawText(QRectF(tx, 16, W - tx - 14, 22), Qt.AlignLeft | Qt.AlignVCenter, self.title)
        p.setPen(QColor(t.text))
        p.setFont(font(14, QFont.Bold))
        text = p.fontMetrics().elidedText(self.detail, Qt.ElideRight, int(W - tx - 14))
        p.drawText(QRectF(tx, 40, W - tx - 14, 40), Qt.AlignLeft | Qt.AlignVCenter, text)
        p.end()
