"""Monitor 2 als virtuelle Kamera („AluPC Monitor 2“): Zoom, Teams, Discord, OBS, Browser sehen genau das Bild von
Monitor 2 – mit Overlays (Chat, Uhr …) und Zeichnungen.

* Bild: AluPCs Ausgabe von Monitor 2 in Kamera-Größe gezeichnet (wie Bild-in-Bild/Live-Vorschau). Bei „Erweitern“
  (Monitor 2 ist ein normaler Bildschirm) wird der Bildschirm aufgenommen – unter Wayland geht das nicht, dann
  kommt ein Hinweisbild.
* Ausgabe: pyvirtualcam – Linux v4l2loopback (/dev/video42), Windows die virtuelle Kamera von OBS Studio.
  Die Treiber richtet drivers.py ein (Installer oder „Einrichten“).
* Das Bild wird im Qt-Hauptthread geholt, das Senden läuft in einem eigenen Thread (immer nur das neueste Bild).
"""

from __future__ import annotations

import threading
import time

from PySide6.QtCore import QObject, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QImage, QPainter

from .drivers import IS_WINDOWS, v4l2_device, vcam_installed

SIZES = {"720p": (1280, 720), "1080p": (1920, 1080), "540p": (960, 540)}


class VirtualCam(QObject):
    changed = Signal()

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.cam = None
        self.error = ""
        self.device = ""
        self._frame = None
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._thread: threading.Thread | None = None
        self._running = False
        self.sent = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._grab)

    # ---- Einstellungen
    def cfg(self) -> dict:
        return {"size": "720p", "fps": 20, "mirror": False, **(self.controller.config.data.get("vcam") or {})}

    @property
    def running(self) -> bool:
        return self._running

    def status(self) -> tuple[bool, str]:
        """(Treiber da?, Hinweis)"""
        try:
            import pyvirtualcam  # noqa: F401
        except ImportError:
            return False, "pyvirtualcam fehlt in dieser AluPC-Version."
        return vcam_installed()

    # ---- an/aus
    def start(self) -> tuple[bool, str]:
        if self._running:
            return True, ""
        ok, why = self.status()
        if not ok:
            self.error = why
            self.changed.emit()
            return False, why
        cfg = self.cfg()
        w, h = SIZES.get(cfg["size"], SIZES["720p"])
        fps = max(5, min(60, int(cfg["fps"])))
        try:
            import pyvirtualcam

            kwargs = {"width": w, "height": h, "fps": fps, "fmt": pyvirtualcam.PixelFormat.RGB}
            if IS_WINDOWS:
                kwargs["backend"] = "obs"
            else:
                self.device = v4l2_device()
                kwargs["device"] = self.device or None
            self.cam = pyvirtualcam.Camera(**kwargs)
            self.device = getattr(self.cam, "device", self.device) or self.device
        except Exception as exc:  # noqa: BLE001 – Treiber/Gerät belegt/fehlt
            self.cam = None
            self.error = f"Virtuelle Kamera ging nicht: {exc}"
            self.changed.emit()
            return False, self.error
        self.error = ""
        self._running = True
        self.sent = 0
        self._thread = threading.Thread(target=self._send_loop, name="alupc-vcam", daemon=True)
        self._thread.start()
        self._timer.start(int(1000 / fps))
        self.controller.config["vcam"] = {**self.cfg(), "on": True}
        self.changed.emit()
        return True, ""

    def stop(self, remember: bool = True) -> None:
        if not self._running:
            return
        self._running = False
        self._timer.stop()
        self._wake.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
        try:
            if self.cam is not None:
                self.cam.close()
        except Exception:  # noqa: BLE001
            pass
        self.cam = None
        if remember:
            self.controller.config["vcam"] = {**self.cfg(), "on": False}
        self.changed.emit()

    def toggle(self) -> tuple[bool, str]:
        if self._running:
            self.stop()
            return True, ""
        return self.start()

    # ---- Bild
    def frame_image(self, w: int, h: int) -> QImage:
        """Was Monitor 2 gerade zeigt, in Kamera-Größe (RGB888)."""
        c = self.controller
        img = QImage()
        out = getattr(c, "output", None)
        if out is not None and out.isVisible() and out.width() > 0:
            from .laser import draw_overlay
            from .output_window import grab_scaled

            img = grab_scaled(out, QSize(w, h))
            draw_overlay(c, img)
        else:
            screen = c.output_screen() if hasattr(c, "output_screen") else None
            if screen is not None:
                pm = screen.grabWindow(0)
                if not pm.isNull():
                    img = pm.toImage().scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            if img.isNull() or _mostly_black(img):
                img = _hint_image(w, h, "Monitor 2: normaler Bildschirm")
        if img.width() != w or img.height() != h:  # mit schwarzem Rand auf genau w×h
            canvas = QImage(w, h, QImage.Format_RGB32)
            canvas.fill(QColor("#000000"))
            p = QPainter(canvas)
            p.drawImage((w - img.width()) // 2, (h - img.height()) // 2, img)
            p.end()
            img = canvas
        if self.cfg().get("mirror"):
            img = img.mirrored(True, False)
        return img.convertToFormat(QImage.Format_RGB888)

    def _grab(self) -> None:
        if not self._running:
            return
        w, h = SIZES.get(self.cfg()["size"], SIZES["720p"])
        img = self.frame_image(w, h)
        data = bytes(img.constBits())[: img.bytesPerLine() * h]
        with self._lock:
            self._frame = (data, img.bytesPerLine(), w, h)
        self._wake.set()

    def _send_loop(self) -> None:
        import numpy as np

        while self._running:
            self._wake.wait(1.0)
            self._wake.clear()
            with self._lock:
                frame, self._frame = self._frame, None
            if frame is None or self.cam is None:
                continue
            data, bpl, w, h = frame
            arr = np.frombuffer(data, dtype=np.uint8).reshape(h, bpl)[:, : w * 3].reshape(h, w, 3)
            try:
                self.cam.send(arr)
                self.sent += 1
            except Exception as exc:  # noqa: BLE001
                self.error = f"Senden ging nicht: {exc}"
                time.sleep(0.5)

    def restore(self) -> None:
        if self.cfg().get("on"):
            self.start()


def _mostly_black(img: QImage) -> bool:
    small = img.scaled(16, 9)
    return all(QColor(small.pixel(x, y)).lightness() < 6 for x in range(16) for y in range(9))


def _hint_image(w: int, h: int, text: str) -> QImage:
    img = QImage(w, h, QImage.Format_RGB32)
    img.fill(QColor("#0f172a"))
    p = QPainter(img)
    p.setPen(QColor("#cbd5e1"))
    f = QFont()
    f.setPixelSize(max(12, h // 18))
    p.setFont(f)
    p.drawText(img.rect(), Qt.AlignCenter, text)
    p.end()
    return img
