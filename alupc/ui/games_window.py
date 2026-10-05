"""Steuerfenster für die Minispiele (am PC): Spiel wählen, Einstellungen, Start, Weiter, Spieler verwalten.

Schnell bedienbar mit Tasten: Leertaste = Start, N = Weiter, E = Ergebnis, L = Lobby, T = Teams mischen,
M = Monitor 2 zeigen, Entf = Spieler entfernen, 1 … 0 = Spiel wählen.
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QColor, QKeySequence, QShortcut
from PySide6.QtWidgets import (QComboBox, QGridLayout, QHBoxLayout, QLabel, QListWidget,
                               QListWidgetItem, QPushButton, QVBoxLayout, QWidget)

from . import icons, theme
from .widgets import button, page_header

KEYS = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"]


class GamesWindow(QWidget):
    def __init__(self, controller, parent=None):
        super().__init__(parent, Qt.Window)
        self.controller = controller
        self.setWindowTitle("Minispiele – Steuerung")
        self.setMinimumSize(860, 560)
        self.resize(1040, 660)
        self._version = -1
        t = theme.current()
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        head = QHBoxLayout()
        head.addWidget(page_header("Minispiele", "Handys scannen den QR-Code auf Monitor 2 – gestartet wird nur hier",
                                   "gamepad"), 1)
        self.pill = QLabel()
        self.pill.setAlignment(Qt.AlignCenter)
        self.pill.setMinimumWidth(110)
        head.addWidget(self.pill, 0, Qt.AlignTop)
        root.addLayout(head)
        body = QHBoxLayout()
        body.setSpacing(18)
        root.addLayout(body, 1)
        # ---- links: Spiele + Einstellungen
        left = QVBoxLayout()
        body.addLayout(left, 3)
        grid = QGridLayout()
        grid.setSpacing(8)
        self.cards: dict[str, QPushButton] = {}
        from ..games import GAMES

        for i, (key, spec) in enumerate(GAMES.items()):
            b = QPushButton(f"{spec.title.replace('&', '&&')}\n{spec.short.replace('&', '&&')}")
            b.setCheckable(True)
            b.setFocusPolicy(Qt.NoFocus)
            b.setCursor(Qt.PointingHandCursor)
            b.setMinimumHeight(64)
            b.setToolTip(f"Taste {KEYS[i]}" if i < len(KEYS) else "")
            b.setStyleSheet(self._card_css(t))
            b.clicked.connect(lambda _=False, k=key: self.choose(k))
            cols = 3 if len(GAMES) > 10 else 2
            grid.addWidget(b, i // cols, i % cols)
            self.cards[key] = b
        left.addLayout(grid)
        self.opts_row = QHBoxLayout()
        self.opts_row.setSpacing(10)
        left.addLayout(self.opts_row)
        self.help = QLabel()
        self.help.setObjectName("Muted")
        self.help.setWordWrap(True)
        left.addWidget(self.help)
        left.addStretch(1)
        # ---- rechts: Steuerung + Spieler
        right = QVBoxLayout()
        body.addLayout(right, 2)
        self.info = QLabel()
        self.info.setWordWrap(True)
        f = self.info.font()
        f.setPointSizeF(f.pointSizeF() * 1.25 if f.pointSizeF() > 0 else 12)
        f.setBold(True)
        self.info.setFont(f)
        right.addWidget(self.info)
        controls = QGridLayout()
        controls.setSpacing(8)
        self.b_start = button("Start  (Leertaste)", "play", primary=True)
        self.b_next = button("Weiter   N", "forward")
        self.b_end = button("Ergebnis   E", "check")
        self.b_lobby = button("Lobby   L", "home")
        self.b_teams = button("Teams mischen   T", "refresh")
        self.b_show = button("Monitor 2   M", "monitor")
        self.b_board = button("Bestenliste   B", "star")
        self.b_sound = button("Töne an   S", "sound")
        for i, b in enumerate((self.b_start, self.b_next, self.b_end, self.b_lobby, self.b_teams, self.b_show,
                               self.b_board, self.b_sound)):
            b.setFocusPolicy(Qt.NoFocus)
            b.setMinimumHeight(44 if i else 54)
            if i == 0:
                controls.addWidget(b, 0, 0, 1, 2)
            else:
                controls.addWidget(b, 1 + (i - 1) // 2, (i - 1) % 2)
        right.addLayout(controls)
        self.b_start.clicked.connect(self.start)
        self.b_next.clicked.connect(lambda: self.controller.game_action("weiter"))
        self.b_end.clicked.connect(lambda: self.controller.game_action("ende"))
        self.b_lobby.clicked.connect(lambda: self.controller.game_action("lobby"))
        self.b_teams.clicked.connect(self.shuffle_teams)
        self.b_show.clicked.connect(lambda: self.controller.start_games())
        self.b_board.clicked.connect(lambda: self.controller.game_action("bestenliste"))
        self.b_sound.clicked.connect(self.toggle_sound)
        self.players_label = QLabel()
        self.players_label.setObjectName("SectionLabel")
        right.addWidget(self.players_label)
        self.players = QListWidget()
        self.players.setFocusPolicy(Qt.ClickFocus)
        self.players.setIconSize(QSize(14, 14))
        right.addWidget(self.players, 1)
        prow = QHBoxLayout()
        self.b_team = button("Team wechseln", "refresh")
        self.b_kick = button("Entfernen   Entf", "x")
        for b in (self.b_team, self.b_kick):
            b.setFocusPolicy(Qt.NoFocus)
            prow.addWidget(b)
        right.addLayout(prow)
        self.b_team.clicked.connect(self.switch_team)
        self.b_kick.clicked.connect(self.kick)
        self.url = QLabel()
        self.url.setObjectName("Muted")
        self.url.setTextInteractionFlags(Qt.TextSelectableByMouse)
        right.addWidget(self.url)
        bottom = QHBoxLayout()
        copy = button("QR groß", "qr")
        copy.setToolTip("Großer QR-Code zum Scannen (mit WLAN-Code, falls eingerichtet) – Link kopieren")
        copy.setFocusPolicy(Qt.NoFocus)
        copy.clicked.connect(self.show_connect)
        wifi = button("WLAN / Hotspot …", "phone")
        wifi.setToolTip("Eigenes WLAN für die Handys starten oder vorhandenes WLAN eintragen → WLAN-QR-Code in der Lobby")
        wifi.setFocusPolicy(Qt.NoFocus)
        wifi.clicked.connect(self.open_wifi)
        stop = button("Minispiele beenden", "x", danger=True)
        stop.setFocusPolicy(Qt.NoFocus)
        stop.clicked.connect(self.stop_games)
        reset = button("Bestenliste zurücksetzen", "trash")
        reset.setFocusPolicy(Qt.NoFocus)
        reset.clicked.connect(self.reset_board)
        bottom.addWidget(copy)
        bottom.addWidget(wifi)
        bottom.addWidget(reset)
        bottom.addStretch(1)
        bottom.addWidget(stop)
        root.addLayout(bottom)
        # ---- Tasten
        for seq, fn in ((Qt.Key_Space, self.start), (Qt.Key_N, lambda: self.controller.game_action("weiter")),
                        (Qt.Key_E, lambda: self.controller.game_action("ende")),
                        (Qt.Key_L, lambda: self.controller.game_action("lobby")), (Qt.Key_T, self.shuffle_teams),
                        (Qt.Key_M, lambda: self.controller.start_games()), (Qt.Key_Delete, self.kick),
                        (Qt.Key_B, lambda: self.controller.game_action("bestenliste")), (Qt.Key_S, self.toggle_sound)):
            QShortcut(QKeySequence(seq), self, activated=fn)
        for i, key in enumerate(list(self.cards)[:len(KEYS)]):
            QShortcut(QKeySequence(KEYS[i]), self, activated=lambda k=key: self.choose(k))
        QShortcut(QKeySequence.Close, self, activated=self.close)
        controller.games_changed.connect(self.refresh)
        self.timer = QTimer(self, interval=400)  # Stand („Frage 3 / 8“) läuft mit
        self.timer.timeout.connect(self._tick)
        self.timer.start()
        self.refresh()

    @staticmethod
    def _card_css(t) -> str:
        return (f"QPushButton {{ text-align: left; padding: 10px 14px; border-radius: 12px; background: {t.surface2};"
                f" border: 2px solid {t.border}; color: {t.text}; }}"
                f"QPushButton:hover {{ border-color: {t.muted}; }}"
                f"QPushButton:checked {{ border-color: {t.accent}; background: rgba({QColor(t.accent).red()},"
                f" {QColor(t.accent).green()}, {QColor(t.accent).blue()}, 40); }}")

    # ------------------------------------------------------------ Aktionen
    def show_connect(self) -> None:
        from .connect_dialog import ConnectDialog

        c = self.controller
        if c.cast.games is None:
            c.start_games()
        ConnectDialog("Mitspielen", c.cast.games_url(), c.guest_wifi(), "Handy-Kamera auf den Code halten",
                      parent=self).exec()

    def open_wifi(self) -> None:
        from .connect_dialog import WifiDialog

        WifiDialog(self.controller, self).exec()

    def hub(self):
        return self.controller.cast.games

    def choose(self, key: str) -> None:
        hub = self.hub()
        if hub is not None and hub.phase == "running":  # laufendes Spiel nicht aus Versehen abbrechen
            self.controller.message.emit("Erst „Lobby“ oder „Ergebnis“ – dann ein anderes Spiel wählen.")
            self.refresh(force=True)
            return
        self.controller.start_games(key)
        self.refresh(force=True)

    def start(self) -> None:
        self.controller.game_action("start")
        self.refresh(force=True)

    def shuffle_teams(self) -> None:
        hub = self.hub()
        if hub is not None and hub.phase != "running":
            hub.shuffle_teams()
            self.controller.games_changed.emit()

    def selected_pid(self) -> str:
        item = self.players.currentItem()
        return item.data(Qt.UserRole) if item is not None else ""

    def kick(self) -> None:
        hub, pid = self.hub(), self.selected_pid()
        if hub is not None and pid:
            hub.kick(pid)
            self.controller.games_changed.emit()

    def switch_team(self) -> None:
        hub, pid = self.hub(), self.selected_pid()
        if hub is not None and pid in hub.players:
            hub.set_team(pid, 1 - hub.players[pid].team)
            self.controller.games_changed.emit()

    def toggle_sound(self) -> None:
        cfg = self.controller.config["games"]
        self.controller.config["games"] = {**cfg, "sound": not cfg.get("sound", True)}
        self.refresh(force=True)

    def reset_board(self) -> None:
        from PySide6.QtWidgets import QMessageBox

        hub = self.hub()
        if hub is None or not hub.board:
            return
        if QMessageBox.question(self, "Bestenliste", "Bestenliste des Abends löschen?") == QMessageBox.Yes:
            self.controller.game_action("bestenliste_neu")

    def stop_games(self) -> None:
        self.controller.game_action("aus")
        self.close()

    def _set_option(self, opt, combo) -> None:
        hub = self.hub()
        if hub is not None:
            hub.set_option(opt, combo.currentData())
            self.controller.save_game_options()
        self.setFocus()

    # ------------------------------------------------------------ Anzeige
    def _tick(self):
        hub = self.hub()
        if hub is not None and hub.phase == "running":
            self._update_info(hub)

    def _update_info(self, hub) -> None:
        with hub.lock:
            now = hub.clock()
            if hub.phase == "lobby":
                n = len(hub.players)
                text = f"Lobby · {n} dabei" if n else "Lobby · noch niemand dabei"
            elif hub.phase == "over":
                text = "Ergebnis auf Monitor 2"
            elif hub.phase == "board":
                text = f"Bestenliste auf Monitor 2 · {hub.board_games} Spiele"
            elif now < hub.intro_until:
                text = f"{hub.spec.title} startet …"
            else:
                text = f"{hub.spec.title}: {hub.game.info(now) if hub.game else ''}"
        self.info.setText(text)

    def refresh(self, force: bool = False) -> None:
        from ..games import GAMES, TEAM_NAMES, option_choices

        hub = self.hub()
        t = theme.current()
        if hub is None:
            self.info.setText("Minispiele sind aus")
            self.pill.setText("AUS")
            for b in (self.b_start, self.b_next, self.b_end, self.b_lobby, self.b_teams, self.b_team, self.b_kick):
                b.setEnabled(False)
            self.players.clear()
            return
        if hub.version == self._version and not force:
            return
        self._version = hub.version
        for key, b in self.cards.items():
            b.setChecked(key == hub.game_key)
        spec = GAMES[hub.game_key]
        self.help.setText(spec.help)
        # Einstellungen des gewählten Spiels
        while self.opts_row.count():
            item = self.opts_row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for opt, (label, _choices, _default) in spec.opts.items():
            lab = QLabel(label)
            lab.setObjectName("Muted")
            combo = QComboBox()
            combo.setFocusPolicy(Qt.ClickFocus)
            for value, text in option_choices(hub.game_key, opt):
                combo.addItem(text, value)
            idx = combo.findData(hub.options[hub.game_key].get(opt))
            combo.setCurrentIndex(max(0, idx))
            combo.setEnabled(hub.phase != "running")
            combo.activated.connect(lambda _i, o=opt, cb=combo: self._set_option(o, cb))
            self.opts_row.addWidget(lab)
            self.opts_row.addWidget(combo)
        self.opts_row.addStretch(1)
        running = hub.phase == "running"
        pill = {"lobby": ("LOBBY", t.accent), "running": ("LÄUFT", t.success), "over": ("ERGEBNIS", t.warning),
                "board": ("BESTENLISTE", t.warning)}
        label, color = pill[hub.phase]
        self.pill.setText(label)
        self.pill.setStyleSheet(f"background: {color}; color: white; border-radius: 12px; padding: 6px 12px;"
                                f" font-weight: 700;")
        self.b_start.setText("Neu starten  (Leertaste)" if running else "Start  (Leertaste)")
        self.b_start.setEnabled(bool(hub.players))
        self.b_next.setEnabled(running)
        self.b_end.setEnabled(running)
        self.b_lobby.setEnabled(hub.phase != "lobby")
        self.b_board.setEnabled(not running)
        sound_on = bool(self.controller.config["games"].get("sound", True))
        self.b_sound.setText("Töne an   S" if sound_on else "Töne aus   S")
        teams = spec.cls.teams
        self.b_teams.setEnabled(teams and not running)
        self.b_team.setEnabled(teams and not running)
        self.b_kick.setEnabled(bool(hub.players))
        # Spieler
        selected = self.selected_pid()
        scores = dict(hub.ranking)
        if running and hub.game is not None:
            try:
                scores = hub.game.scores()
            except Exception:  # noqa: BLE001 – Anzeige darf das Spiel nie stören
                scores = {}
        self.players.clear()
        for pl in sorted(hub.players.values(), key=lambda p: p.joined):
            parts = [pl.name]
            if teams:
                parts.append(TEAM_NAMES[pl.team])
            if pl.pid in scores and hub.phase not in ("lobby", "board"):
                parts.append(f"{int(scores[pl.pid]) % 1000 if teams else int(scores[pl.pid])}")
            if hub.board.get(pl.name):
                parts.append(f"gesamt {hub.board[pl.name]}")
            item = QListWidgetItem(icons.dot_icon(pl.color), "   ·   ".join(parts))
            item.setData(Qt.UserRole, pl.pid)
            self.players.addItem(item)
            if pl.pid == selected:
                self.players.setCurrentItem(item)
        self.players_label.setText(f"SPIELER ({len(hub.players)})")
        self.url.setText(self.controller.cast.games_url())
        self._update_info(hub)

    def closeEvent(self, e):
        self.timer.stop()
        super().closeEvent(e)

    def showEvent(self, e):
        self.timer.start()
        self.refresh(force=True)
        super().showEvent(e)
