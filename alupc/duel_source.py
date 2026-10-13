"""Monitor 2: Schiffe versenken aus Sicht von Spieler 2 (eigene Flotte + Feld zum Schießen, Tastatur-Auswahl).

Spieler 2 steuert mit dem Handy (QR-Codes rechts, nur übers AluPC-WLAN) oder an der PC-Tastatur (Pfeile + Enter
im Schiffe-Fenster auf Monitor 1). Spieler 1 sieht seine Schiffe nur im PC-Fenster – nie hier.
"""

from __future__ import annotations

import time

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QWidget

from . import duel_draw as dd
from . import game_draw as gd
from .duel import SHIPS
from .sources import draw_qr, qr_image


class DuelSource(QWidget):
    def __init__(self, cfg=None, parent=None):
        super().__init__(parent)
        from .cast_server import cast_server

        self.server = cast_server()
        self.ok = self.server.start()
        self._version = -1
        self._qr: dict[str, tuple[str, object]] = {}
        self.setAttribute(Qt.WA_OpaquePaintEvent)
        self.timer = QTimer(self, interval=100)  # Handy/Tastatur ändern den Stand → neu zeichnen
        self.timer.timeout.connect(self._poll)
        self.timer.start()

    def stop(self):
        self.timer.stop()

    def _poll(self):
        duel = self.server.duel
        version = duel.version if duel is not None else -2
        if version != self._version:
            self._version = version
            self.update()

    def _qr_img(self, key: str, payload: str):
        old = self._qr.get(key)
        if old is None or old[0] != payload:
            self._qr[key] = old = (payload, qr_image(payload or " "))
        return old[1]

    def _phone_codes(self, p, rect: QRectF, duel) -> None:
        """Rechts: WLAN-Code + Code für die Spieler-2-Seite (oder Hinweis, dass das Handy verbunden ist)."""
        from .screens import wifi_payload

        h = rect.height()
        if duel.p2_phone:
            gd.text(p, QRectF(rect.x(), rect.y(), rect.width(), h * 0.1), f"📱 {duel.names[2]} spielt am Handy",
                    h * 0.045, "#86efac", True)
            return
        try:
            provider = getattr(self.server, "wifi_provider", None)
            wifi = provider() if provider else None
        except Exception:  # noqa: BLE001
            wifi = None
        gd.text(p, QRectF(rect.x(), rect.y(), rect.width(), h * 0.07), "Spieler 2 mit dem Handy:", h * 0.04,
                "#e2e8f0", True)
        codes = []
        if wifi:
            codes.append(("1 · WLAN", self._qr_img("wifi", wifi_payload(*wifi)), f"„{wifi[0]}“"))
        codes.append((("2 · " if wifi else "") + "Spielseite", self._qr_img("link", self.server.base() +
                                                                             f"schiffe?u={duel.token}"),
                      "Name eingeben, Schiffe setzen"))
        side = min(rect.width() / len(codes) * 0.78, h * 0.42)
        for i, (label, img, sub) in enumerate(codes):
            cx = rect.x() + rect.width() * (i + 0.5) / len(codes)
            y = rect.y() + h * 0.12
            gd.text(p, QRectF(cx - side, y, 2 * side, h * 0.06), label, h * 0.034, "#a5b4fc", True)
            box = QRectF(cx - side / 2, y + h * 0.07, side, side)
            pad = side * 0.06
            p.setPen(Qt.NoPen)
            p.setBrush(Qt.white)
            p.drawRoundedRect(box.adjusted(-pad, -pad, pad, pad), pad * 1.5, pad * 1.5)
            draw_qr(p, box, img)
            gd.text(p, QRectF(cx - side, box.bottom() + pad * 2, 2 * side, h * 0.05), sub, h * 0.03, "#93c5fd")
        gd.text(p, QRectF(rect.x(), rect.y() + h * 0.12 + side + h * 0.16, rect.width(), h * 0.2),
                "Oder an der PC-Tastatur:\nPfeile = Feld · Enter = setzen/schießen (auf einem Schiff: aufnehmen)\n"
                "R = drehen · Z = zufällig · B = bereit", h * 0.03, gd.MUTED, wrap=True)

    def _spectator(self, p, view, duel, rect: QRectF) -> None:
        """Beide Felder nur mit Schüssen (versenkte Schiffe aufgedeckt) – fair, auch wenn Spieler 1 hinschaut."""
        h = rect.height()
        if view["phase"] == "setzen":
            lines = [f"📱 {duel.names[2]} setzt die Schiffe am Handy",
                     "✅ bereit" if duel.ready[2] else "… setzt noch",
                     f"{duel.names[1]} (PC): " + ("✅ bereit" if duel.ready[1] else "… setzt noch")]
            gd.text(p, QRectF(rect.x(), rect.y() + h * 0.25, rect.width(), h * 0.45), "\n".join(lines), h * 0.06,
                    gd.TEXT, True, wrap=True)
            return
        f1, f2 = duel.fleets[1], duel.fleets[2]
        half = rect.width() / 2
        for i, (fleet, title, active) in enumerate((
                (f1, f"Feld von {duel.names[1]} – {duel.names[2]} schießt", view["turn"] == 2),
                (f2, f"Feld von {duel.names[2]} – {duel.names[1]} schießt", view["turn"] == 1))):
            area = QRectF(rect.x() + i * half + half * 0.04, rect.y() + h * 0.07, half * 0.92, h * 0.86)
            gd.text(p, QRectF(area.x(), rect.y(), area.width(), h * 0.06), title, h * 0.032, "#a5b4fc", True)
            sunk = [c for s in fleet.ships if fleet.sunk(s) for c in s]
            dd.board(p, area, hits=list(fleet.hits), misses=list(fleet.misses), sunk=sunk,
                     active=active and view["phase"] == "spielen")

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        from types import SimpleNamespace

        gd.background(SimpleNamespace(p=p, w=w, h=h, now=time.monotonic()))
        duel = self.server.duel
        if duel is None or not self.ok:
            gd.text(p, QRectF(0, 0, w, h), "Kein Schiffe-versenken-Spiel" if self.ok else
                    "Netzwerk-Anschluss belegt", h / 16, gd.TEXT, True)
            p.end()
            return
        view = duel.view(2)
        cursor = duel.cursor
        m = max(12.0, min(w, h) * 0.035)
        title_h = h * 0.09
        gd.text(p, QRectF(m, m * 0.6, w - 2 * m, title_h), f"🚢 Schiffe versenken · {view['name']}", title_h * 0.55,
                gd.TEXT, True, Qt.AlignLeft | Qt.AlignVCenter)
        big, color = dd.headline(view)
        if duel.p2_phone:  # Monitor 2 ist dann für alle: Namen statt „Du“
            if view["phase"] == "spielen":
                big, color = f"{duel.names[view['turn']]} ist dran", "#86efac"
            elif view["phase"] == "ende":
                big, color = f"🏆 {duel.names[view['winner']]} gewinnt!", "#facc15"
            else:
                big, color = "Schiffe setzen …", "#e2e8f0"
        gd.text(p, QRectF(m, m * 0.6 + title_h, w - 2 * m, h * 0.08), big, h * 0.055, color, True,
                Qt.AlignLeft | Qt.AlignVCenter)
        top = m * 0.6 + title_h + h * 0.09
        area_h = h - top - m * 1.6
        foot = QRectF(m, h - m * 1.5, w - 2 * m, m * 1.2)
        gd.text(p, foot, view["message"], m * 0.75, gd.MUTED, False, Qt.AlignLeft | Qt.AlignVCenter)
        if duel.p2_phone:  # Spieler 2 am Handy: Monitor 2 verrät keine Schiffe (Zuschauer-Ansicht)
            self._spectator(p, view, duel, QRectF(m, top, w - 2 * m, area_h))
            p.end()
            return
        if view["phase"] == "setzen":
            ghost, ok = duel.ghost(2, *cursor) if not duel.p2_phone else ([], True)
            left = QRectF(m, top, w * 0.55, area_h)
            dd.own_board(p, left, view, cursor=None if duel.p2_phone or view["ready"] else cursor,
                         ghost=ghost, ghost_ok=ok)
            self._phone_codes(p, QRectF(w * 0.58, top, w * 0.42 - m, area_h), duel)
        else:
            # Spielen/Ende: groß das Feld zum Schießen, klein die eigene Flotte
            mine = view["turn"] == 2 and view["phase"] == "spielen"
            left = QRectF(m, top + h * 0.05, w * 0.58, area_h - h * 0.05)
            gd.text(p, QRectF(left.x(), top, left.width(), h * 0.05), f"Feld von {view['other']} – hier schießen",
                    h * 0.032, "#a5b4fc", True)
            dd.target_board(p, left, view, cursor=cursor if mine and not duel.p2_phone else None, active=mine)
            right = QRectF(w * 0.62, top + h * 0.05, w * 0.38 - m, area_h * 0.62)
            gd.text(p, QRectF(right.x(), top, right.width(), h * 0.05), "Deine Flotte", h * 0.032, "#a5b4fc", True)
            dd.own_board(p, right, view, dim=mine)
            info = QRectF(right.x(), right.bottom() + h * 0.03, right.width(), h * 0.05)
            gd.text(p, info, f"Gegner hat noch {view['target']['left']} von {len(SHIPS)} Schiffen", h * 0.03,
                    gd.TEXT, False)
            if view["phase"] == "ende":
                gd.text(p, QRectF(right.x(), info.bottom(), right.width(), h * 0.08),
                        "Neues Spiel: am PC im Schiffe-Fenster", h * 0.028, gd.MUTED)
        p.end()
