"""Browser-Steuerung: die Website auf Monitor 2 vom Hauptmonitor aus bedienen.

Adresszeile, Zurück/Vor/Neu laden, Zoom, Scrollen – und eine Live-Vorschau, in die man
klicken, scrollen und tippen kann (Maus/Tastatur werden an die Website weitergegeben).
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QPointF, QSize, Qt, QTimer, QUrl
from PySide6.QtGui import QKeyEvent, QMouseEvent, QWheelEvent
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from ..sources import FrameView, fit_rect, normalize_url
from . import theme
from .widgets import Banner, button


class LivePreview(FrameView):
    """Vorschau der Website; Maus- und Tastatureingaben gehen an die echte Seite."""

    def __init__(self, control, parent=None):
        super().__init__("contain", parent)
        self.control = control
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumSize(480, 270)

    def _map(self, pos: QPointF) -> QPointF | None:
        view = self.control.view
        img = self.image()
        if view is None or img is None:
            return None
        r = fit_rect(img.width(), img.height(), self.width(), self.height(), "contain")
        if not r.contains(pos):
            return None
        return QPointF((pos.x() - r.left()) * view.width() / r.width(),
                       (pos.y() - r.top()) * view.height() / r.height())

    def _target(self):
        view = self.control.view
        return (view.focusProxy() or view) if view is not None else None

    def _send_mouse(self, kind, event):
        pos = self._map(event.position())
        target = self._target()
        if pos is None or target is None:
            return
        glob = QPointF(target.mapToGlobal(pos.toPoint()))
        ev = QMouseEvent(kind, pos, glob, event.button(), event.buttons(), event.modifiers())
        QApplication.sendEvent(target, ev)
        self.control.refresh_soon()

    def mousePressEvent(self, e):
        self.setFocus()
        self._send_mouse(QEvent.MouseButtonPress, e)

    def mouseReleaseEvent(self, e):
        self._send_mouse(QEvent.MouseButtonRelease, e)

    def mouseMoveEvent(self, e):
        self._send_mouse(QEvent.MouseMove, e)

    def mouseDoubleClickEvent(self, e):
        self._send_mouse(QEvent.MouseButtonDblClick, e)

    def wheelEvent(self, e):
        pos = self._map(e.position())
        target = self._target()
        if pos is None or target is None:
            return
        glob = QPointF(target.mapToGlobal(pos.toPoint()))
        ev = QWheelEvent(pos, glob, e.pixelDelta(), e.angleDelta(), e.buttons(), e.modifiers(),
                         e.phase(), e.inverted())
        QApplication.sendEvent(target, ev)
        self.control.refresh_soon()

    def _send_key(self, kind, e):
        target = self._target()
        if target is None:
            return
        ev = QKeyEvent(kind, e.key(), e.modifiers(), e.text(), e.isAutoRepeat(), e.count())
        QApplication.sendEvent(target, ev)
        self.control.refresh_soon()

    def keyPressEvent(self, e):
        self._send_key(QEvent.KeyPress, e)

    def keyReleaseEvent(self, e):
        self._send_key(QEvent.KeyRelease, e)


class BrowserControl(QWidget):
    """Eigenes Fenster (auf dem Hauptmonitor) zum Steuern der Website auf Monitor 2."""

    def __init__(self, controller, save_favorite, parent=None):
        super().__init__(parent, Qt.Window)
        self.controller = controller
        self.save_favorite = save_favorite
        self.view = None
        self.setWindowTitle("AluPC – Browser steuern")
        self.resize(1000, 700)
        t = theme.current()

        def tool(icon_name, tip, slot):
            b = button("", icon_name)
            b.setToolTip(tip)
            b.setIconSize(QSize(18, 18))
            b.clicked.connect(slot)
            return b

        self.url = QLineEdit()
        self.url.setPlaceholderText("Adresse eingeben und Enter drücken")
        self.url.returnPressed.connect(self.go)
        self.back_btn = tool("back", "Zurück", lambda: self._act("back"))
        self.fwd_btn = tool("forward", "Vor", lambda: self._act("forward"))
        self.reload_btn = tool("refresh", "Neu laden", lambda: self._act("reload"))
        self.zoom_label = QLabel("100 %")
        self.zoom_label.setMinimumWidth(52)
        self.zoom_label.setAlignment(Qt.AlignCenter)
        zoom_out = tool("zoom_out", "Verkleinern", lambda: self._zoom(-0.1))
        zoom_in = tool("zoom_in", "Vergrößern", lambda: self._zoom(0.1))
        up = tool("up", "Nach oben scrollen", lambda: self._scroll(-0.8))
        down = tool("down", "Nach unten scrollen", lambda: self._scroll(0.8))
        self.save_btn = button("Unter „Website“ speichern", "bookmark", primary=True)
        self.save_btn.clicked.connect(self._save)
        bar = QHBoxLayout()
        bar.setSpacing(6)
        for w in (self.back_btn, self.fwd_btn, self.reload_btn):
            bar.addWidget(w)
        bar.addWidget(self.url, 1)
        for w in (zoom_out, self.zoom_label, zoom_in, up, down):
            bar.addWidget(w)
        bar.addWidget(self.save_btn)

        self.banner = Banner("", "info")
        self.preview = LivePreview(self)
        hint = QLabel("In die Vorschau klicken, scrollen und tippen – das passiert direkt auf Monitor 2.")
        hint.setObjectName("Muted")
        open_btn = button("Website öffnen …", "globe")
        open_btn.clicked.connect(self._open_website)
        low = QHBoxLayout()
        low.addWidget(hint, 1)
        low.addWidget(open_btn)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(10)
        lay.addLayout(bar)
        lay.addWidget(self.banner)
        lay.addWidget(self.preview, 1)
        lay.addLayout(low)
        self.setStyleSheet(f"BrowserControl {{ background: {t.bg}; }}")

        self.timer = QTimer(self, interval=200)  # 5 Bilder/s
        self.timer.timeout.connect(self.refresh)
        self._soon = QTimer(self, singleShot=True, interval=60)
        self._soon.timeout.connect(self.refresh)
        controller.changed.connect(self.rebind)
        self.rebind()

    # ------------------------------------------------------------ Verbindung zur Website
    def rebind(self):
        view = self.controller.current_web_view()
        if view is self.view:
            return
        if self.view is not None:
            try:
                self.view.urlChanged.disconnect(self._url_changed)
            except (RuntimeError, TypeError):
                pass
        self.view = view
        has = view is not None
        for w in (self.back_btn, self.fwd_btn, self.reload_btn, self.save_btn, self.url):
            w.setEnabled(has)
        if has:
            view.urlChanged.connect(self._url_changed)
            self._url_changed(view.url())
            self.banner.hide()
        else:
            self.preview.set_image(None)
            self.preview.set_message("Auf Monitor 2 läuft gerade keine Website.")
            self.banner.set("Auf Monitor 2 läuft gerade keine Website – öffne eine über „Website öffnen …“ "
                            "oder die Kachel „Website“.", "warn")
            self.banner.show()

    def _url_changed(self, url: QUrl):
        if not self.url.hasFocus():
            self.url.setText(url.toString())
        if self.view is not None:
            self.zoom_label.setText(f"{round(self.view.zoomFactor() * 100)} %")

    def showEvent(self, e):
        self.rebind()
        self.timer.start()
        super().showEvent(e)

    def hideEvent(self, e):
        self.timer.stop()
        super().hideEvent(e)

    def refresh_soon(self):
        self._soon.start()

    def refresh(self):
        view = self.view
        if view is None:
            return
        try:
            self.preview.set_image(self._snapshot(view))
        except RuntimeError:  # Website wurde gerade geschlossen
            self.view = None
            self.rebind()

    def _snapshot(self, view):
        """Bild der Website. Windows/X11: echtes Bildschirmfoto der Stelle auf Monitor 2 (zeigt die
        Seite so, wie die Grafikkarte sie darstellt); Wayland: die Website selbst abfotografieren."""
        from PySide6.QtGui import QGuiApplication

        from ..platform.linux_display import is_wayland

        if not is_wayland() and QGuiApplication.platformName() not in ("offscreen", "minimal") \
                and view.isVisible():
            top_left = view.mapToGlobal(view.rect().topLeft())
            screen = QGuiApplication.screenAt(top_left + view.rect().center())
            if screen is not None:
                g = screen.geometry()
                shot = screen.grabWindow(0, top_left.x() - g.x(), top_left.y() - g.y(), view.width(), view.height())
                if not shot.isNull():
                    return shot
        return view.grab()

    # ------------------------------------------------------------ Aktionen
    def _act(self, what: str):
        if self.view is not None:
            getattr(self.view, what)()
            self.refresh_soon()

    def go(self):
        url = normalize_url(self.url.text())
        if not url:
            return
        if self.view is None:
            self.controller.show_source({"type": "website", "url": url})
            self.rebind()
        else:
            self.view.load(QUrl(url))
        self.url.clearFocus()

    def _zoom(self, delta: float):
        if self.view is not None:
            self.view.setZoomFactor(max(0.25, min(5.0, self.view.zoomFactor() + delta)))
            self.zoom_label.setText(f"{round(self.view.zoomFactor() * 100)} %")
            self.refresh_soon()

    def _scroll(self, pages: float):
        if self.view is not None:
            self.view.page().runJavaScript(f"window.scrollBy(0, window.innerHeight * {pages});")
            self.refresh_soon()

    def _save(self):
        if self.view is None:
            return
        title = self.view.title() or self.view.url().host()
        name, ok = QInputDialog.getText(self, "Website speichern", "Name für die Website:", text=title)
        if ok:
            self.save_favorite(name.strip() or title, self.view.url().toString())

    def _open_website(self):
        parent = self.parent()
        if parent is not None and hasattr(parent, "pick_website"):
            parent.pick_website()
            self.rebind()

