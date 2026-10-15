"""Schiffe versenken – Fenster für Spieler 1 auf Monitor 1 (Maus) + Tastatur für Spieler 2.

Spieler 1: im linken Feld Schiffe setzen (Klick, Rechtsklick/Mausrad = drehen, gesetztes Schiff anklicken =
aufnehmen und verschieben), im rechten Feld schießen.
Spieler 2 (schaut auf Monitor 2): Pfeiltasten = Feld wählen, Enter/Leertaste = setzen bzw. schießen,
R = drehen, Z = zufällig, B = bereit, Rücktaste = letztes Schiff zurück – oder mit dem Handy.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from .. import duel_draw as dd
from .. import game_draw as gd
from ..duel import SHIPS
from . import theme
from .widgets import button, page_header

P1 = 1
P2 = 2
P2_KEYS = {Qt.Key_Left: (-1, 0), Qt.Key_Right: (1, 0), Qt.Key_Up: (0, -1), Qt.Key_Down: (0, 1)}


class DuelBoards(QWidget):
    """Die zwei Felder von Spieler 1: links die eigene Flotte, rechts das Feld des Gegners."""

    def __init__(self, win):
        super().__init__(win)
        self.win = win
        self.hover: tuple[int, int] | None = None
        self.setMouseTracking(True)
        self.setMinimumSize(640, 340)
        self.setFocusPolicy(Qt.NoFocus)

    def areas(self) -> tuple[QRectF, QRectF]:
        w, h = self.width(), self.height()
        gap = w * 0.04
        side = min((w - gap) / 2, h - 30)
        y = 30 + (h - 30 - side) / 2
        x0 = (w - 2 * side - gap) / 2
        return QRectF(x0, y, side, side), QRectF(x0 + side + gap, y, side, side)

    def paintEvent(self, _e):
        duel = self.win.duel()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), gd.qc("#0b1020"))
        if duel is None:
            p.end()
            return
        view = duel.view(P1)
        own, target = self.areas()
        setting = view["phase"] == "setzen"
        mine = view["turn"] == P1 and view["phase"] == "spielen"
        gd.text(p, QRectF(own.x(), 0, own.width(), 26), "Deine Flotte", 15, "#a5b4fc", True)
        gd.text(p, QRectF(target.x(), 0, target.width(), 26),
                f"Feld von {view['other']} – " + ("hier schießen" if not setting else "nach dem Setzen"),
                15, "#a5b4fc", True)
        ghost, ok = ([], True)
        if setting and self.hover is not None and self.hover[0] == "own":
            ghost, ok = duel.ghost(P1, *self.hover[1])
        dd.own_board(p, own, view, ghost=ghost, ghost_ok=ok, active=setting and not view["ready"], dim=mine)
        cur = self.hover[1] if mine and self.hover is not None and self.hover[0] == "target" else None
        dd.target_board(p, target, view, cursor=cur, active=mine, dim=setting)
        p.end()

    def _cell(self, pos: QPointF):
        own, target = self.areas()
        for name, area in (("own", own), ("target", target)):
            c = dd.cell_at(area, pos)
            if c is not None:
                return name, c
        return None

    def mouseMoveEvent(self, e):
        hit = self._cell(e.position())
        if hit != self.hover:
            self.hover = hit
            self.update()

    def leaveEvent(self, _e):
        self.hover = None
        self.update()

    def mousePressEvent(self, e):
        duel = self.win.duel()
        if duel is None:
            return
        if e.button() == Qt.RightButton:
            duel.rotate(P1)
            self.win.refresh()
            return
        hit = self._cell(e.position())
        if hit is None or e.button() != Qt.LeftButton:
            return
        where, (x, y) = hit
        if where == "own" and duel.phase == "setzen":
            if duel.fleets[P1].ship_at((x, y)) is not None:
                duel.remove(P1, x, y)  # gesetztes Schiff anklicken = aufnehmen, dann woanders hinsetzen
            else:
                duel.place(P1, x, y)
        elif where == "target" and duel.phase == "spielen":
            duel.shoot(P1, x, y)
        self.win.refresh()

    def wheelEvent(self, e):
        duel = self.win.duel()
        if duel is not None and duel.phase == "setzen":
            duel.rotate(P1)
            self.win.refresh()


class DuelWindow(QWidget):
    def __init__(self, controller, parent=None):
        super().__init__(parent, Qt.Window)
        self.controller = controller
        self.setWindowTitle("Schiffe versenken – Spieler 1")
        self.setMinimumSize(760, 520)
        self.resize(1100, 700)
        self._version = -1
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 14, 18, 14)
        head = QHBoxLayout()
        head.addWidget(page_header("Schiffe versenken", "Du = Spieler 1 hier · Spieler 2: Handy als Steuerung, Felder auf dem Bildschirm",
                                   "gamepad"), 1)
        root.addLayout(head)
        self.status = QLabel()
        self.status.setWordWrap(True)
        root.addWidget(self.status)
        self.boards = DuelBoards(self)
        root.addWidget(self.boards, 1)
        self.message = QLabel()
        self.message.setObjectName("Muted")
        self.message.setWordWrap(True)
        root.addWidget(self.message)
        row = QHBoxLayout()
        row.setSpacing(8)
        self.rnd_btn = button("Zufällig", "wheel")
        self.rnd_btn.clicked.connect(lambda: self._act(lambda d: d.randomize(P1)))
        self.rot_btn = button("Drehen", "rotate")
        self.rot_btn.clicked.connect(lambda: self._act(lambda d: d.rotate(P1)))
        self.undo_btn = button("Zurück", "undo")
        self.undo_btn.clicked.connect(lambda: self._act(lambda d: d.undo(P1)))
        self.ready_btn = button("Bereit", "check", primary=True)
        self.ready_btn.clicked.connect(lambda: self._act(lambda d: d.set_ready(P1)))
        self.new_btn = button("Neues Spiel", "refresh")
        self.new_btn.clicked.connect(lambda: self._act(lambda d: d.restart()))
        self.phone_btn = button("Handy abmelden", "phone")
        self.phone_btn.setToolTip("Spieler 2 spielt dann mit der Tastatur oder einem anderen Handy")
        self.phone_btn.clicked.connect(lambda: self._act(lambda d: d.release_phone()))
        self.show_btn = button("Bildschirm zeigen", "extend")
        self.show_btn.clicked.connect(lambda: self.controller.start_duel(open_window=False))
        self.close_btn = button("Beenden", "x")
        self.close_btn.clicked.connect(self.close)
        for b in (self.rnd_btn, self.rot_btn, self.undo_btn, self.ready_btn, self.new_btn, self.phone_btn):
            b.setFocusPolicy(Qt.NoFocus)
            row.addWidget(b)
        row.addStretch(1)
        for b in (self.show_btn, self.close_btn):
            b.setFocusPolicy(Qt.NoFocus)
            row.addWidget(b)
        root.addLayout(row)
        self.keys = QLabel("Gesetztes Schiff anklicken = aufnehmen und verschieben. Ohne Handy: Spieler 2 an der "
                           "Tastatur – Pfeile = Feld · Enter = setzen/schießen (auf einem Schiff: aufnehmen) · "
                           "R = drehen · Z = zufällig · B = bereit · ← Rücktaste = Schiff zurück")
        self.keys.setObjectName("Muted")
        self.keys.setWordWrap(True)
        root.addWidget(self.keys)
        self.setFocusPolicy(Qt.StrongFocus)
        self.timer = QTimer(self, interval=150)  # Handy von Spieler 2 ändert den Stand im Hintergrund
        self.timer.timeout.connect(self._poll)
        self.timer.start()
        self.status.setStyleSheet(f"font-size: 20px; font-weight: 800; color: {theme.current().text};")
        self.refresh()

    def duel(self):
        return self.controller.cast.duel

    def _act(self, fn):
        d = self.duel()
        if d is not None:
            fn(d)
        self.refresh()

    def _poll(self):
        d = self.duel()
        if d is not None and d.version != self._version:
            self.refresh()

    def refresh(self):
        d = self.duel()
        if d is None:
            self.status.setText("Kein Spiel – über die Minispiele neu starten")
            self.boards.update()
            return
        self._version = d.version
        view = d.view(P1)
        big, _color = dd.headline(view)
        setting, ready = view["phase"] == "setzen", view["ready"]
        if view["phase"] == "spielen":
            big += f"  ·  {view['other']} hat noch {view['target']['left']} von {len(SHIPS)} Schiffen"
        self.status.setText(big)
        self.message.setText(view["message"])
        for b in (self.rnd_btn, self.rot_btn, self.undo_btn):
            b.setVisible(setting and not ready)
        self.ready_btn.setVisible(setting and not ready)
        self.ready_btn.setEnabled(view["next"] is None)
        self.rot_btn.setText("Drehen (waagrecht)" if view["horizontal"] else "Drehen (senkrecht)")
        self.new_btn.setVisible(view["phase"] == "ende")
        self.phone_btn.setVisible(d.p2_phone)
        self.boards.update()

    # ---- Tastatur für Spieler 2 (schaut auf Monitor 2)
    def keyPressEvent(self, e):
        d = self.duel()
        if d is None:
            return super().keyPressEvent(e)
        k = e.key()
        if k in P2_KEYS:
            d.move_cursor(*P2_KEYS[k])
        elif k in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            x, y = d.cursor
            if d.phase == "setzen":
                if d.fleets[P2].ship_at((x, y)) is not None:
                    d.remove(P2, x, y)  # auf einem Schiff: aufnehmen (dann woanders mit Enter setzen)
                else:
                    d.place(P2, x, y)
            elif d.phase == "spielen":
                d.shoot(P2, x, y)
        elif k == Qt.Key_R:
            d.rotate(P2)
        elif k == Qt.Key_Z:
            d.randomize(P2)
        elif k == Qt.Key_B:
            d.set_ready(P2)
        elif k == Qt.Key_Backspace:
            d.undo(P2)
        else:
            return super().keyPressEvent(e)
        self.refresh()

    def closeEvent(self, e):
        self.timer.stop()
        self.controller.stop_duel()
        super().closeEvent(e)
