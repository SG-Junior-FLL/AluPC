"""Laserpointer: roter Leuchtpunkt auf Monitor 2, gesteuert mit der Maus auf Monitor 1.

Die Maus auf Monitor 1 wird wie ein Touchpad auf Monitor 2 übertragen (gleiche relative Stelle;
beim Spiegeln genau dort, wo das gespiegelte Bild ist). Steht die Maus selbst auf Monitor 2
(„Erweitern“), leuchtet der Punkt direkt an der Maus.

Der Punkt liegt in einem eigenen, durchsichtigen Fenster über allem, das keine Klicks abfängt.
Im selben Fenster erscheinen auch die Zeichnungen aus „Zeigen & Zeichnen“ (Stift, Textmarker) und der
Laserpunkt, den man dort in der Vorschau steuert. Zeichnungen werden relativ gespeichert (0…1), damit sie
auf jedem Monitor an derselben Stelle liegen.
"""

from __future__ import annotations

import time

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QRadialGradient
from PySide6.QtWidgets import QWidget

from .cursor import tracker
from .sources import fit_rect

TRAIL_SECONDS = 0.28
MARKER_ALPHA = 0.38


def stroke_pen(stroke: dict, height: float) -> QPen:
    color = QColor(stroke.get("color", "#ff2a2a"))
    width = max(1.0, float(stroke.get("width", 0.004)) * height)
    if stroke.get("tool") == "marker":
        color.setAlphaF(MARKER_ALPHA)
        width *= 3.5
    return QPen(color, width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)


def paint_strokes(p: QPainter, strokes: list[dict], area: QRectF) -> None:
    """Zeichnungen (Punkte relativ 0…1) in das Rechteck `area` malen."""
    p.save()
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(Qt.NoBrush)
    for stroke in strokes:
        pts = stroke.get("points") or []
        if not pts:
            continue
        p.setPen(stroke_pen(stroke, area.height()))
        first = QPointF(area.x() + pts[0][0] * area.width(), area.y() + pts[0][1] * area.height())
        if len(pts) == 1:
            p.drawPoint(first)
            continue
        path = QPainterPath(first)
        for x, y in pts[1:]:
            path.lineTo(area.x() + x * area.width(), area.y() + y * area.height())
        p.drawPath(path)
    p.restore()


def paint_dot(p: QPainter, point: QPointF, r: float, color: QColor) -> None:
    """Leuchtender Laserpunkt."""
    p.save()
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    glow = QRadialGradient(point, r * 3)
    g0 = QColor(color)
    g0.setAlphaF(0.55)
    g1 = QColor(color)
    g1.setAlphaF(0.0)
    glow.setColorAt(0, g0)
    glow.setColorAt(1, g1)
    p.setBrush(glow)
    p.drawEllipse(point, r * 3, r * 3)
    p.setBrush(color)
    p.drawEllipse(point, r, r)
    p.setBrush(QColor(255, 255, 255, 200))
    p.drawEllipse(point, r * 0.38, r * 0.38)
    p.restore()


class LaserWindow(QWidget):
    TITLE = "AluPC – Laserpointer"

    def __init__(self, controller):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
                         | Qt.WindowTransparentForInput | Qt.WindowDoesNotAcceptFocus)
        self.controller = controller
        self.setWindowTitle(self.TITLE)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.active = False
        self.point: QPointF | None = None
        self.trail: list[tuple[float, QPointF]] = []
        self._fade = QTimer(self, interval=16)
        self._fade.timeout.connect(self._tick)
        self._kde_done = False
        self.remote = False  # Laserpunkt kommt aus dem Fenster „Zeigen & Zeichnen“
        self.strokes: list[dict] = []
        self.changed_cb = None  # wird nach jeder Änderung der Zeichnungen aufgerufen (Speichern)

    def _changed(self):
        if self.changed_cb is not None:
            self.changed_cb()

    def needed(self) -> bool:
        return self.active or self.remote or bool(self.strokes)

    # ------------------------------------------------------------ an/aus
    def set_active(self, on: bool) -> bool:
        if on == self.active:
            return self.active
        self.active = on
        t = tracker()
        if on:
            t.acquire()
            t.moved.connect(self._moved)
            self.place()
            if t.pos is not None:
                self._moved(t.pos)
        else:
            try:
                t.moved.disconnect(self._moved)
            except (RuntimeError, TypeError):
                pass
            t.release()
            self.point = None
            self.trail.clear()
            self._fade.stop()
            self.update()
            self.place()
        return self.active

    def place(self) -> None:
        screen = self.controller.output_screen()
        if screen is None or not self.needed():
            if self.isVisible():
                self.hide()
            self._kde_done = False
            return
        from .platform.linux_display import is_wayland

        if is_wayland():
            # Wayland: Fenster dürfen sich nicht selbst platzieren → Vollbild auf dem gewünschten Monitor
            self.create()
            handle = self.windowHandle()
            if handle is not None and handle.screen() is not screen:
                handle.setScreen(screen)
            if not self.isVisible() or not self.isFullScreen():
                self.showFullScreen()
        else:
            if self.geometry() != screen.geometry():
                self.setGeometry(screen.geometry())
            if not self.isVisible():
                self.show()
        if not self._kde_done and self.isVisible():
            self._kde_done = True
            self._kde_keep_above()
        self.raise_above()

    def raise_above(self) -> None:
        """Über das Ausgabefenster legen (das sich selbst regelmäßig nach vorne holt)."""
        if not self.isVisible():
            return
        from .platform.window_tools import keep_on_top

        self.raise_()
        keep_on_top(self)

    def _kde_keep_above(self):
        from .platform.window_tools import kde_keep_above
        from .ui.util import run_async

        run_async(lambda: kde_keep_above(self.TITLE), None, lambda _e: None)

    # ------------------------------------------------------------ Position
    def target_for(self, pos: QPoint) -> QPointF | None:
        """Wohin gehört der Punkt auf Monitor 2 (Koordinaten in diesem Fenster)?"""
        out = self.controller.output_screen()
        main = self.controller.main_screen()
        if out is None:
            return None
        og = out.geometry()
        if og.contains(pos):
            return QPointF(pos - og.topLeft())
        if main is None or not main.geometry().contains(pos):
            return None
        mg = main.geometry()
        rx = (pos.x() - mg.x()) / max(1, mg.width())
        ry = (pos.y() - mg.y()) / max(1, mg.height())
        area = self._mirror_area(og) or QRectF(0, 0, og.width(), og.height())
        return QPointF(area.x() + rx * area.width(), area.y() + ry * area.height())

    def _mirror_area(self, og: QRect) -> QRectF | None:
        """Beim Spiegeln: wo genau liegt das Bild von Monitor 1 auf Monitor 2 (evtl. mit Rändern)?"""
        c = self.controller
        src = c.output.content if c.output.isVisible() else None
        if src is None or not (c.content or {}).get("mirror"):
            return None
        img = src.image() if hasattr(src, "image") else None
        if img is None:
            return None
        return fit_rect(img.width(), img.height(), og.width(), og.height(), getattr(src, "fit", "contain"))

    def _moved(self, pos: QPoint):
        target = self.target_for(pos)
        old = self._dirty()
        self.point = target
        if target is not None:
            self.trail.append((time.monotonic(), target))
        self._prune()
        self.update(old.united(self._dirty()))
        if self.trail:
            self._fade.start()

    def _prune(self):
        now = time.monotonic()
        self.trail = [(t, p) for t, p in self.trail if now - t < TRAIL_SECONDS][-40:]

    def _tick(self):
        old = self._dirty()
        self._prune()
        self.update(old.united(self._dirty()))
        if not self.trail:
            self._fade.stop()

    # ------------------------------------------------------------ gesteuert aus „Zeigen & Zeichnen“
    def set_remote(self, on: bool) -> None:
        self.remote = on
        if not on and not self.active:
            self.remote_point(None)
        self.place()

    def remote_point(self, norm: QPointF | None) -> None:
        """Laserpunkt an relativer Stelle (0…1) von Monitor 2 zeigen; None = ausblenden."""
        old = self._dirty()
        if norm is None:
            self.point = None
        else:
            self.point = QPointF(norm.x() * self.width(), norm.y() * self.height())
            self.trail.append((time.monotonic(), self.point))
        self._prune()
        self.update(old.united(self._dirty()))
        if self.trail:
            self._fade.start()

    def begin_stroke(self, tool: str, color: str, width: float, norm: QPointF) -> None:
        self.strokes.append({"tool": tool, "color": color, "width": width, "points": [(norm.x(), norm.y())]})
        self.place()
        self._update_last()

    def extend_stroke(self, norm: QPointF) -> None:
        if not self.strokes:
            return
        pts = self.strokes[-1]["points"]
        if pts and abs(pts[-1][0] - norm.x()) < 0.0005 and abs(pts[-1][1] - norm.y()) < 0.0005:
            return  # kaum bewegt → keinen Punkt speichern
        pts.append((norm.x(), norm.y()))
        self._update_last()

    def _update_last(self):
        """Nur den Bereich des letzten Strichstücks neu zeichnen (schnell, auch bei 4K)."""
        stroke = self.strokes[-1]
        pts = stroke["points"][-2:]
        w, h = self.width(), self.height()
        pad = stroke_pen(stroke, h).widthF() + 4
        xs, ys = [x * w for x, _ in pts], [y * h for _, y in pts]
        self.update(QRectF(min(xs) - pad, min(ys) - pad, max(xs) - min(xs) + 2 * pad,
                           max(ys) - min(ys) + 2 * pad).toAlignedRect())

    def end_stroke(self) -> None:
        """Maustaste losgelassen → Strich fertig → speichern."""
        self._changed()

    def undo(self) -> None:
        if self.strokes:
            self.strokes.pop()
            self.update()
            self.place()
            self._changed()

    def clear_strokes(self) -> None:
        if self.strokes:
            self.strokes = []
            self.update()
            self.place()
            self._changed()

    def erase_at(self, norm: QPointF, radius: float) -> bool:
        """Striche entfernen, die den Radierer (Radius relativ zur Höhe) berühren."""
        aspect = self.width() / max(1, self.height()) if self.height() else 16 / 9
        keep = []
        for stroke in self.strokes:
            hit = any(((x - norm.x()) * aspect) ** 2 + (y - norm.y()) ** 2 <= radius ** 2
                      for x, y in stroke["points"])
            if not hit:
                keep.append(stroke)
        changed = len(keep) != len(self.strokes)
        if changed:
            self.strokes = keep
            self.update()
            self.place()
            self._changed()
        return changed

    # ------------------------------------------------------------ Zeichnen
    def radius(self) -> float:
        size = float(self.controller.config["laser"].get("size", 100)) / 100
        return max(5.0, self.height() / 110 * size)

    def _dirty(self) -> QRect:
        r = self.radius() * 3 + 4
        pts = [p for _t, p in self.trail] + ([self.point] if self.point is not None else [])
        if not pts:
            return QRect()
        xs, ys = [p.x() for p in pts], [p.y() for p in pts]
        return QRectF(min(xs) - r, min(ys) - r, max(xs) - min(xs) + 2 * r,
                      max(ys) - min(ys) + 2 * r).toAlignedRect()

    def paintEvent(self, _event):
        if self.controller.privacy:
            return  # bei „Schwarz“ (Sichtschutz) weder Laser noch Zeichnungen zeigen
        p = QPainter(self)
        if self.strokes:
            paint_strokes(p, self.strokes, QRectF(self.rect()))
        cfg = self.controller.config["laser"]
        # Laser in der gerade gewählten Zeichenfarbe (eigene Laser-Einstellungen gibt es nicht mehr)
        color = QColor(self.controller.config["draw"].get("color", "#ef4444"))
        r = self.radius()
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        now = time.monotonic()
        if cfg.get("trail", True):
            for t, pt in self.trail[:-1]:
                age = (now - t) / TRAIL_SECONDS
                c = QColor(color)
                c.setAlphaF(max(0.0, 0.45 * (1 - age)))
                p.setBrush(c)
                rr = r * (0.9 - 0.5 * age)
                p.drawEllipse(pt, rr, rr)
        if self.point is not None:
            paint_dot(p, self.point, r, color)
        p.end()
