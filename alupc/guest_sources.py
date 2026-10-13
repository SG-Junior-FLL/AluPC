"""Monitor 2 für Gäste: Chat-Wand und Foto-Wand – jeweils mit den zwei Codes zum Mitmachen (1. AluPC-WLAN,
2. die Seite im Browser). Beide zeichnen nur neu, wenn sich etwas tut (neue Nachricht/neues Foto, Animation)."""

from __future__ import annotations

import math
import time

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QImage, QLinearGradient, QPainter, QPainterPath
from PySide6.QtWidgets import QWidget

from .sources import draw_qr, fitted_font, qr_image


def _font(px: float, bold: bool = False) -> QFont:
    f = QFont()
    f.setPixelSize(max(8, int(px)))
    f.setBold(bold)
    return f


def _ease(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


class JoinCodes:
    """Die zwei Codes zum Mitmachen: WLAN + Seite (z. B. /chat, /fotos). Bilder werden nur bei Änderung neu gebaut."""

    def __init__(self, path: str, title: str = "Seite öffnen"):
        self.path = path
        self.title = title
        self._wifi = ("", None)
        self._link = ("", None)

    def link(self) -> str:
        from .cast_server import wlan_url

        return wlan_url(self.path)

    def codes(self) -> list[tuple[str, QImage, str]]:
        from .hotspot import hotspot
        from .screens import wifi_payload

        payload = wifi_payload(hotspot.ssid, hotspot.password, hotspot.hidden) if hotspot.running else ""
        if payload != self._wifi[0]:
            self._wifi = (payload, qr_image(payload) if payload else None)
        link = self.link()
        if link != self._link[0]:
            self._link = (link, qr_image(link) if link else None)
        out = []
        if self._wifi[1] is not None:
            out.append(("1 · WLAN", self._wifi[1], hotspot.ssid))
        if self._link[1] is not None:
            out.append((f"2 · {self.title}", self._link[1], "öffnet im Browser"))
        return out

    def paint(self, p: QPainter, rect: QRectF, vertical: bool = True) -> None:
        """Codes in rect (untereinander oder nebeneinander), mit Überschrift und Zeile."""
        codes = self.codes()
        if not codes:
            p.setPen(QColor("#cbd5e1"))
            p.setFont(_font(min(rect.width(), rect.height()) * 0.07, True))
            p.drawText(rect, Qt.AlignCenter | Qt.TextWordWrap, "AluPC-WLAN startet …")
            return
        n = len(codes)
        if vertical:
            cell_h = rect.height() / n
            cells = [QRectF(rect.x(), rect.y() + i * cell_h, rect.width(), cell_h) for i in range(n)]
        else:
            cell_w = rect.width() / n
            cells = [QRectF(rect.x() + i * cell_w, rect.y(), cell_w, rect.height()) for i in range(n)]
        for (title, img, line), cell in zip(codes, cells):
            label = min(cell.height() * 0.12, cell.width() * 0.13)
            # Überschrift + Code (mit weißem Rand) + Zeile darunter + Abstand zur nächsten Zelle
            side = min(cell.width() * 0.8, (cell.height() - label * 2.6) / 1.12)
            head = QRectF(cell.x(), cell.y(), cell.width(), label)
            p.setPen(QColor("#ffffff"))
            p.setFont(fitted_font(p, title, int(cell.width()), int(label * 0.8)))
            f = p.font()
            f.setBold(True)
            p.setFont(f)
            p.drawText(head, Qt.AlignCenter, title)
            pad = side * 0.06
            q = QRectF(cell.center().x() - side / 2, head.bottom() + pad + label * 0.12, side, side)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#ffffff"))
            p.drawRoundedRect(q.adjusted(-pad, -pad, pad, pad), pad, pad)
            draw_qr(p, q, img)
            p.setPen(QColor("#93c5fd"))
            p.setFont(fitted_font(p, line, int(cell.width()), int(label * 0.6)))
            p.drawText(QRectF(cell.x(), q.bottom() + pad + label * 0.1, cell.width(), label), Qt.AlignCenter, line)


# =========================================================================== Chat-Wand
class ChatWallSource(QWidget):
    """Großer Chat auf Monitor 2: Sprechblasen (neueste unten), rechts die Codes zum Mitschreiben."""

    def __init__(self, cfg, parent=None):
        super().__init__(parent)
        from .cast_server import cast_server

        self.server = cast_server()
        self.codes = JoinCodes("/chat")
        self._version = -1
        self.timer = QTimer(self, interval=33)
        self.timer.timeout.connect(self._tick)
        self.timer.start()
        self.setAttribute(Qt.WA_OpaquePaintEvent)

    def stop(self):
        self.timer.stop()

    def _tick(self):
        chat = self.server.chat
        version = chat.version if chat is not None else -2
        fresh = chat is not None and bool(chat.latest(1)) and time.time() - chat.latest(1)[0]["t"] < 0.6
        if version != self._version or fresh or int(time.monotonic()) % 2 == 0 and self._version == -2:
            self._version = version
            self.update()

    def paintEvent(self, _e):
        from .chat import name_color

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        grad = QLinearGradient(0, 0, w, h)
        grad.setColorAt(0, QColor("#0b1020"))
        grad.setColorAt(1, QColor("#172554"))
        p.fillRect(self.rect(), grad)
        m = min(w, h) * 0.05
        portrait = h > w * 1.1
        codes_rect = QRectF(m, h - m - h * 0.26, w - 2 * m, h * 0.26) if portrait else \
            QRectF(w - m - w * 0.22, m, w * 0.22, h - 2 * m)
        self.codes.paint(p, codes_rect, vertical=not portrait)
        area = QRectF(m, m, w - 2 * m, codes_rect.y() - 2 * m) if portrait else \
            QRectF(m, m, codes_rect.x() - 2 * m, h - 2 * m)
        p.setPen(QColor("#ffffff"))
        title_px = min(h, w) * 0.07
        p.setFont(_font(title_px, True))
        p.drawText(QRectF(area.x(), area.y(), area.width(), title_px * 1.4), Qt.AlignLeft | Qt.AlignVCenter, "💬 Chat")
        chat = self.server.chat
        top = area.y() + title_px * 1.7
        if chat is None or not chat.messages:
            p.setPen(QColor("#94a3b8"))
            p.setFont(_font(title_px * 0.5))
            p.drawText(QRectF(area.x(), top, area.width(), area.bottom() - top), Qt.AlignCenter | Qt.TextWordWrap,
                       "Der Chat ist aus" if chat is None else
                       "Noch keine Nachrichten – Codes scannen und die erste schreiben!")
            p.end()
            return
        px = min(h, w) * 0.034
        name_f, text_f = _font(px * 0.85, True), _font(px)
        fm = QFontMetricsF(text_f)
        y = area.bottom()
        now = time.time()
        bubble_w = area.width() * 0.82
        for msg in reversed(chat.latest(40)):  # von unten nach oben, bis kein Platz mehr ist
            text_h = fm.boundingRect(QRectF(0, 0, bubble_w - px * 1.6, 10_000), int(Qt.TextWordWrap),
                                     msg["text"]).height()
            hh = px * 0.7 + px * 1.2 + text_h + px * 0.8
            if y - hh < top:
                break
            y -= hh
            appear = _ease((now - msg["t"]) / 0.4)
            box = QRectF(area.x() + (1 - appear) * px * 4, y, bubble_w, hh - px * 0.4)
            p.save()
            p.setOpacity(0.25 + 0.75 * appear)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(245, 158, 11, 70) if msg.get("host") else QColor(255, 255, 255, 22))
            p.drawRoundedRect(box, px * 0.7, px * 0.7)
            name = (msg.get("avatar", "") + " " if msg.get("avatar") else "") + msg["name"]
            p.setFont(name_f)
            p.setPen(QColor("#fbbf24" if msg.get("host") else name_color(msg["name"])))
            p.drawText(QRectF(box.x() + px * 0.8, box.y() + px * 0.35, box.width() - px * 1.6, px * 1.2),
                       Qt.AlignLeft | Qt.AlignVCenter, name)
            p.setFont(text_f)
            p.setPen(QColor("#f1f5f9"))
            p.drawText(QRectF(box.x() + px * 0.8, box.y() + px * 1.6, box.width() - px * 1.6, text_h + 2),
                       int(Qt.TextWordWrap | Qt.AlignLeft | Qt.AlignTop), msg["text"])
            p.restore()
            y -= px * 0.1
        p.end()


# =========================================================================== Foto-Wand
class PhotoWallSource(QWidget):
    """Foto-Wand auf Monitor 2: Collage (Polaroids) oder Diashow; neue Fotos erst groß, dann in die Collage."""

    SPOT = 4.5  # Sekunden groß für ein neues Foto

    def __init__(self, cfg, parent=None):
        super().__init__(parent)
        from .cast_server import cast_server

        self.server = cast_server()
        self.cfg_override = dict(cfg or {})
        self.codes = JoinCodes("/fotos")
        self._cache: dict[tuple[int, int], QImage] = {}
        self._seen = -1  # höchste schon gezeigte Foto-ID
        self._queue: list[int] = []
        self._spot: tuple[int, float] | None = None  # (Foto-ID, Start)
        self._slide = (0, time.monotonic())
        self._version = -1
        self.timer = QTimer(self, interval=33)
        self.timer.timeout.connect(self._tick)
        self.timer.start()
        self.setAttribute(Qt.WA_OpaquePaintEvent)

    def stop(self):
        self.timer.stop()

    def settings(self) -> dict:
        try:
            base = dict(self.server.config["photowall"])
        except (KeyError, TypeError, AttributeError):
            base = {}
        return {"mode": "collage", "codes": True, "interval": 7, **base,
                **{k: v for k, v in self.cfg_override.items() if k in ("mode", "codes", "interval")}}

    def _image(self, photo: dict, side: int) -> QImage:
        key = (photo["id"], side)
        img = self._cache.get(key)
        if img is None:
            from .sources import load_image

            src = load_image(photo["path"])
            img = src.scaled(side, side, Qt.KeepAspectRatio, Qt.SmoothTransformation) if not src.isNull() else src
            if len(self._cache) > 60:
                self._cache.clear()
            self._cache[key] = img
        return img

    def _tick(self):
        wall = self.server.wall
        now = time.monotonic()
        busy = False
        if wall is not None and wall.version != self._version:
            self._version = wall.version
            ids = [p["id"] for p in wall.latest(60)]
            if self._seen < 0:
                self._seen = max(ids, default=0)  # beim Öffnen: vorhandene Fotos nicht alle einzeln groß zeigen
            new = [i for i in ids if i > self._seen]
            if new:
                self._queue += new
                self._seen = max(new)
            self._queue = [i for i in self._queue if wall.get(i) is not None]
            busy = True
        if self._spot is not None and now - self._spot[1] > self.SPOT:
            self._spot = None
            busy = True
        if self._spot is None and self._queue and self.settings().get("mode") != "diashow":
            self._spot = (self._queue.pop(0), now)
        if self._spot is not None or self.settings().get("mode") == "diashow":
            busy = True
        if busy:
            self.update()

    # ---- Zeichnen
    def _background(self, p: QPainter, w: int, h: int) -> None:
        grad = QLinearGradient(0, 0, w, h)
        grad.setColorAt(0, QColor("#1a0b1e"))
        grad.setColorAt(1, QColor("#0b1020"))
        p.fillRect(QRectF(0, 0, w, h), grad)

    def _polaroid(self, p: QPainter, photo: dict, center: QPointF, size: float, angle: float, caption: bool,
                  scale: float = 1.0) -> None:
        img = self._image(photo, int(size))
        if img.isNull():
            return
        iw, ih = img.width(), img.height()
        f = size / max(iw, ih)
        pw, ph = iw * f, ih * f
        border = size * 0.04
        cap = size * 0.12 if caption else border
        p.save()
        p.translate(center)
        p.rotate(angle)
        p.scale(scale, scale)
        frame = QRectF(-pw / 2 - border, -ph / 2 - border, pw + 2 * border, ph + border + cap)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 90))
        p.drawRoundedRect(frame.translated(size * 0.012, size * 0.02), border * 0.6, border * 0.6)
        p.setBrush(QColor("#fdfdfb"))
        p.drawRoundedRect(frame, border * 0.6, border * 0.6)
        p.drawImage(QRectF(-pw / 2, -ph / 2, pw, ph), img)
        if caption:
            p.setPen(QColor("#334155"))
            p.setFont(_font(cap * 0.5, True))
            p.drawText(QRectF(frame.x(), ph / 2, frame.width(), cap), Qt.AlignCenter, "📷 " + photo["name"])
        p.restore()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        w, h = self.width(), self.height()
        self._background(p, w, h)
        wall = self.server.wall
        cfg = self.settings()
        m = min(w, h) * 0.04
        show_codes = cfg.get("codes", True)
        photos = wall.latest(60) if wall is not None else []
        if wall is None or not photos:
            title = "📷 Foto-Wand" if wall is not None else "Die Foto-Wand ist aus"
            p.setPen(QColor("#ffffff"))
            p.setFont(_font(min(w, h) * 0.08, True))
            p.drawText(QRectF(0, m, w, h * 0.14), Qt.AlignCenter, title)
            if wall is not None:
                p.setPen(QColor("#f9a8d4"))
                p.setFont(_font(min(w, h) * 0.035))
                p.drawText(QRectF(0, m + h * 0.13, w, h * 0.06), Qt.AlignCenter,
                           "Codes scannen und das erste Foto schicken!")
                self.codes.paint(p, QRectF(w * 0.15, h * 0.28, w * 0.7, h * 0.66), vertical=False)
            p.end()
            return
        codes_rect = QRectF(w - m - min(w * 0.2, h * 0.32), h - m - min(h * 0.62, w * 0.36),
                            min(w * 0.2, h * 0.32), min(h * 0.62, w * 0.36)) if show_codes else None
        if cfg.get("mode") == "diashow":
            self._paint_slideshow(p, photos, w, h, cfg)
        else:
            self._paint_collage(p, photos, QRectF(m, m, (codes_rect.x() - 2 * m) if codes_rect else w - 2 * m,
                                                  h - 2 * m))
        if codes_rect is not None:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(11, 16, 32, 210))
            p.drawRoundedRect(codes_rect.adjusted(-m * 0.4, -m * 0.4, m * 0.4, m * 0.4), m * 0.5, m * 0.5)
            self.codes.paint(p, codes_rect, vertical=True)
        if self._spot is not None and wall is not None:
            photo = wall.get(self._spot[0])
            if photo is not None:
                t = time.monotonic() - self._spot[1]
                fade = _ease(t / 0.35) * (1 - _ease((t - self.SPOT + 0.5) / 0.5))
                p.fillRect(QRectF(0, 0, w, h), QColor(0, 0, 0, int(170 * fade)))
                self._polaroid(p, photo, QPointF(w / 2, h / 2), min(w, h) * 0.78, -2.0, True,
                               scale=0.6 + 0.4 * _ease(t / 0.45) if fade > 0.02 else 0.0001)
        p.end()

    def _paint_collage(self, p: QPainter, photos: list[dict], area: QRectF) -> None:
        spot = self._spot[0] if self._spot else None
        shown = [ph for ph in photos if ph["id"] != spot and ph["id"] not in self._queue][-12:]
        n = len(shown)
        if not n:
            return
        cols = max(1, math.ceil(math.sqrt(n * area.width() / max(1.0, area.height()))))
        rows = math.ceil(n / cols)
        cw, ch = area.width() / cols, area.height() / rows
        size = min(cw, ch) * 0.86
        for i, photo in enumerate(reversed(shown)):  # neuestes oben links
            r, c = divmod(i, cols)
            center = QPointF(area.x() + cw * (c + 0.5), area.y() + ch * (r + 0.5))
            angle = ((photo["id"] * 37) % 11) - 5  # fest je Foto: leicht schräg wie aufgehängt
            self._polaroid(p, photo, center, size, angle, True)

    def _paint_slideshow(self, p: QPainter, photos: list[dict], w: int, h: int, cfg: dict) -> None:
        interval = max(3.0, float(cfg.get("interval", 7) or 7))
        idx, start = self._slide
        now = time.monotonic()
        if now - start > interval:
            idx, start = idx + 1, now
            self._slide = (idx, start)
        photo = photos[-1 - (idx % len(photos))]  # neueste zuerst
        img = self._image(photo, int(max(w, h)))
        if img.isNull():
            return
        t = (now - start) / interval
        zoom = 1.0 + 0.06 * t  # langsames Heranzoomen
        f = min(w / img.width(), h / img.height()) * zoom
        dw, dh = img.width() * f, img.height() * f
        p.setOpacity(_ease((now - start) / 0.6))
        p.drawImage(QRectF((w - dw) / 2, (h - dh) / 2, dw, dh), img)
        p.setOpacity(1.0)
        path = QPainterPath()
        label = f"📷 {photo['name']}"
        px = min(w, h) * 0.04
        p.setFont(_font(px, True))
        tw = QFontMetricsF(p.font()).horizontalAdvance(label)
        box = QRectF(px, h - px * 2.6, tw + px * 1.4, px * 1.8)
        path.addRoundedRect(box, px * 0.5, px * 0.5)
        p.fillPath(path, QColor(0, 0, 0, 150))
        p.setPen(QColor("#ffffff"))
        p.drawText(box, Qt.AlignCenter, label)
