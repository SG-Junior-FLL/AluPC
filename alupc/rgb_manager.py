"""RGB im Programm: Verbindung zu OpenRGB halten, Farbe setzen, „Farbe folgt Monitor 2“."""

from __future__ import annotations

from PySide6.QtCore import QObject, QSize, QTimer, Signal

from .rgb import OpenRGB, RGBError, find_openrgb, hex_to_rgb, start_openrgb, vivid

RGB_DEFAULTS = {"enabled": False, "port": 6742, "mode": "farbe", "color": "#3b82f6", "brightness": 100,
                "skip": [], "openrgb_path": "", "start_openrgb": True}
MODES = {"farbe": "Farbe", "monitor2": "Farbe folgt Monitor 2", "aus": "Aus"}


class RgbManager(QObject):
    status = Signal(str, bool)  # Text, verbunden?

    def __init__(self, controller):
        super().__init__(controller)
        self.controller = controller
        self.client: OpenRGB | None = None
        self.text = "Nicht verbunden."
        self._busy = False
        self._current = None  # zuletzt gesendete Farbe (Monitor-2-Modus: geglättet)
        self._ambient = QTimer(self, interval=120)
        self._ambient.timeout.connect(self._ambient_tick)
        if self.settings()["enabled"]:
            QTimer.singleShot(1500, lambda: self.connect_async(start_if_needed=True))

    def settings(self) -> dict:
        return {**RGB_DEFAULTS, **self.controller.config["rgb"]}

    def update_settings(self, **changes) -> None:
        self.controller.config["rgb"] = {**self.controller.config["rgb"], **changes}
        self.apply()
        self.status.emit(self.text, self.connected)  # Oberfläche auffrischen (auch bei Befehlen/Tasten)

    @property
    def connected(self) -> bool:
        return self.client is not None and self.client.sock is not None

    @property
    def devices(self):
        return self.client.devices if self.connected else []

    def _set_status(self, text: str):
        self.text = text
        self.status.emit(text, self.connected)

    # ------------------------------------------------------------ Verbinden
    def connect_async(self, start_if_needed: bool = False) -> None:
        from .ui.util import run_async

        if self._busy:
            return
        self._busy = True
        s = self.settings()
        self._set_status("Verbinde mit OpenRGB …")
        client = OpenRGB(port=int(s["port"]))

        def work():
            try:
                client.connect()
                return client
            except RGBError:
                path = find_openrgb(s["openrgb_path"])
                if not (start_if_needed and s["start_openrgb"] and path):
                    raise
                start_openrgb(path)  # OpenRGB mit SDK-Server starten und etwas warten
                import time

                for _ in range(20):
                    time.sleep(1)
                    try:
                        client.connect()
                        return client
                    except RGBError:
                        continue
                raise

        def done(c):
            self._busy = False
            self.disconnect()
            self.client = c
            n = len(c.devices)
            self._set_status(f"Verbunden mit OpenRGB – {n} Gerät{'e' if n != 1 else ''}.")
            self.apply()

        def failed(text):
            self._busy = False
            self._set_status(text)

        run_async(work, done, failed)

    def disconnect(self) -> None:
        self._ambient.stop()
        if self.client is not None:
            self.client.close()
        self.client = None

    # ------------------------------------------------------------ Farben
    def targets(self) -> list[int]:
        skip = set(self.settings()["skip"])
        return [d.index for d in self.devices if d.name not in skip]

    def send(self, rgb) -> bool:
        if not self.connected:
            return False
        try:
            self.client.set_color(tuple(rgb), self.targets())
            self._current = tuple(rgb)
            return True
        except RGBError as exc:
            self.disconnect()
            self._set_status(str(exc))
            return False

    def apply(self) -> None:
        s = self.settings()
        self._ambient.stop()
        if not self.connected:
            return
        if s["mode"] == "aus":
            self.send((0, 0, 0))
        elif s["mode"] == "monitor2":
            self._ambient.start()
            self._ambient_tick()
        else:
            self.send(hex_to_rgb(s["color"], int(s["brightness"])))

    def _ambient_tick(self) -> None:
        """Durchschnittsfarbe von Monitor 2 → LEDs (weich übergeblendet)."""
        from .output_window import grab_scaled

        c = self.controller
        out = c.output
        s = self.settings()
        if out.isVisible() and (c.mode == "content" or c.privacy or c.frozen):
            img = grab_scaled(out, QSize(32, 18))
            if img.isNull():
                return
            total = [0, 0, 0]
            count = 0
            for y in range(img.height()):
                for x in range(img.width()):
                    col = img.pixelColor(x, y)
                    total[0] += col.red()
                    total[1] += col.green()
                    total[2] += col.blue()
                    count += 1
            target = vivid(tuple(v / max(1, count) for v in total))
        else:  # normaler Desktop auf Monitor 2 → gewählte Farbe
            target = hex_to_rgb(s["color"], 100)
        f = int(s["brightness"]) / 100
        target = tuple(v * f for v in target)
        cur = self._current or target
        smooth = tuple(round(a + (b - a) * 0.35) for a, b in zip(cur, target))
        if self._current is None or max(abs(a - b) for a, b in zip(smooth, self._current)) >= 3:
            self.send(smooth)

    def set_mode(self, mode: str) -> None:
        if mode in MODES:
            self.update_settings(mode=mode)
            if not self.connected:
                self.connect_async(start_if_needed=True)

    def shutdown(self) -> None:
        self.disconnect()
