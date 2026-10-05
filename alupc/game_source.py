"""Monitor 2: Minispiele – Lobby mit QR-Code, 3-2-1, Spielfeld, Siegertreppchen (gezeichnet in game_draw.py).

Die Spiel-Uhr läuft im Controller (auch wenn Monitor 2 gerade etwas anderes zeigt); diese Anzeige zeichnet nur.
"""

from __future__ import annotations

from types import SimpleNamespace

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QWidget

from . import game_draw as gd
from .sources import qr_image


class GameSource(QWidget):
    def __init__(self, cfg, parent=None):
        super().__init__(parent)
        from .cast_server import cast_server

        self.server = cast_server()
        self.ok = self.server.start()
        self._qr_for, self._qr = "", None
        self._fx_for = None
        self.fx = gd.new_fx()
        self.timer = QTimer(self, interval=16)
        self.timer.timeout.connect(self.update)
        self.timer.start()
        self.setAttribute(Qt.WA_OpaquePaintEvent)

    def stop(self):
        self.timer.stop()

    def qr(self):
        url = self.server.games_url()
        if url != self._qr_for:
            self._qr_for, self._qr = url, qr_image(url)
        return self._qr

    def wifi(self):
        """(Name, Passwort) des WLANs für die Handys – vom Controller (Hotspot oder eingetragenes WLAN)."""
        try:
            provider = getattr(self.server, "wifi_provider", None)
            return provider() if provider else None
        except Exception:  # noqa: BLE001
            return None

    def wifi_qr(self):
        from .screens import wifi_payload

        wifi = self.wifi()
        payload = wifi_payload(*wifi) if wifi else ""
        if payload != getattr(self, "_wifi_for", None):
            self._wifi_for, self._wifi_img = payload, qr_image(payload or " ")
        return self._wifi_img

    def _fx_key(self, hub):
        return (id(hub), hub.phase if hub.phase != "running" else "running", id(hub.game))

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        hub = self.server.games
        c = SimpleNamespace(p=p, w=self.width(), h=self.height(), now=0.0, hub=hub, fx=self.fx, qr=self.qr,
                            url=self.server.games_url, wifi=self.wifi(), wifi_qr=self.wifi_qr)
        if hub is None or not self.ok:
            import time

            c.now = time.monotonic()
            gd.background(c)
            msg = "Keine Spielrunde" if self.ok else "Minispiele: Netzwerk-Anschluss belegt"
            gd.text(p, QRectF(0, 0, c.w, c.h), msg, c.h / 16, gd.TEXT, True)
            p.end()
            return
        with hub.lock:
            c.now = hub.clock()
            key = self._fx_key(hub)
            if key != self._fx_for:  # neues Spiel / neue Phase → Effekte neu
                keep = self.fx.parts if hub.phase in ("over", "board") else []
                self.fx = c.fx = gd.new_fx()
                self.fx.parts = keep
                self.fx.ev = hub.game.event_n if hub.game is not None and hub.phase == "over" else 0
                self._fx_for = key
            gd.background(c)
            if hub.phase == "lobby":
                gd.lobby(c)
            elif hub.phase == "over":
                gd.podium(c)
            elif hub.phase == "board":
                gd.board(c)
            elif hub.game is not None and c.now < hub.intro_until:
                gd.intro(c)
            elif hub.game is not None:
                game = hub.game
                events = [e for e in game.events if e[0] > self.fx.ev]
                self.fx.ev = game.event_n
                gd.DRAW[hub.game_key](c, game, events)
            gd.draw_particles(c)
            # Spielen: 60 Bilder/s (Pong, Snake …). Lobby/Ergebnis/Bestenliste bewegen sich langsam → 30 Bilder/s
            # (halbe Rechenzeit; mit Konfetti weiter flüssig genug)
            want = 16 if hub.phase == "running" or c.fx.parts else 33
            if self.timer.interval() != want:
                self.timer.setInterval(want)
        p.end()
