"""Handy-Einrichtung: iPhone/iPad per AirPlay und jedes Handy per Browser (QR-Code) – mit Status und
automatischer Einrichtung."""

from __future__ import annotations

import sys

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .. import handy
from . import icons, theme
from .util import run_async
from .widgets import Pill, button, font, rounded

IS_WINDOWS = sys.platform.startswith("win")
PIN_MODES = [("", "Kein Code"), ("fest", "Fester Code"), ("zufall", "Neuer Code je Gerät")]
READY, SETUP, OFF, LIVE = "#22c55e", "#f59e0b", "#94a3b8", "#3b82f6"


class ChipIcon(QWidget):
    """Großes Symbol im farbigen Verlaufs-Quadrat (Kopf jeder Karte)."""

    def __init__(self, icon_name: str, color: str, parent=None):
        super().__init__(parent)
        self.icon_name, self.color = icon_name, color
        self.setFixedSize(52, 52)

    def paintEvent(self, _e):
        from PySide6.QtGui import QLinearGradient

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        c = QColor(self.color)
        grad = QLinearGradient(r.topLeft(), r.bottomRight())
        grad.setColorAt(0, c.lighter(122))
        grad.setColorAt(1, c.darker(108))
        p.fillPath(rounded(r, 15), grad)
        icons.paint(p, self.icon_name, r.adjusted(13, 13, -13, -13), "#ffffff", 2.0)
        p.end()


class MethodCard(QWidget):
    """Eine Karte je Weg: Kopf (Symbol, Titel, für wen, Status), Schritte, Optionen, Knöpfe."""

    def __init__(self, icon_name: str, color: str, title: str, audience: str, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(10)
        head = QHBoxLayout()
        head.setSpacing(12)
        head.addWidget(ChipIcon(icon_name, color))
        names = QVBoxLayout()
        names.setSpacing(0)
        t = QLabel(title)
        t.setFont(font(13, QFont.Bold))
        a = QLabel(audience)
        a.setObjectName("Muted")
        names.addWidget(t)
        names.addWidget(a)
        head.addLayout(names, 1)
        self.pill = Pill("…", OFF)
        head.addWidget(self.pill, 0, Qt.AlignTop)
        lay.addLayout(head)
        self.detail = QLabel()
        self.detail.setWordWrap(True)
        self.detail.setTextFormat(Qt.RichText)
        lay.addWidget(self.detail)
        self.body = QVBoxLayout()
        self.body.setSpacing(8)
        lay.addLayout(self.body)
        lay.addStretch(1)
        self.buttons = QHBoxLayout()
        self.buttons.setSpacing(8)
        lay.addLayout(self.buttons)

    def set_status(self, text: str, color: str, detail: str = ""):
        self.pill.set(text, color)
        self.detail.setText(detail)
        self.detail.setVisible(bool(detail))


def link_button(text: str, slot):
    """Unauffälliger Text-Knopf (wie ein Link) für Nebensachen."""
    from PySide6.QtWidgets import QPushButton

    b = QPushButton(text)
    b.setFlat(True)
    b.setCursor(Qt.PointingHandCursor)
    b.setStyleSheet(f"QPushButton {{ border: none; background: transparent; color: {theme.current().accent}; "
                    "padding: 0; text-align: left; } QPushButton:hover { text-decoration: underline; }")
    b.clicked.connect(slot)
    return b


def steps_label(*lines: str) -> QLabel:
    label = QLabel(steps(*lines))
    label.setWordWrap(True)
    return label


def steps(*lines: str) -> str:
    return "".join(f"<div style='margin:2px 0'><b>{i}.</b> {line}</div>" for i, line in enumerate(lines, 1))


class HandyPage(QWidget):
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.config = controller.config
        self._setup_running = False
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(0, 0, 8, 0)
        lay.setSpacing(14)
        lay.addWidget(self._setup_card())
        grid = QGridLayout()
        grid.setSpacing(14)
        self.cards = {
            "cast": self._cast_card(),
            "airplay": self._airplay_card(),
        }
        for i, card in enumerate(self.cards.values()):
            grid.addWidget(card, i // 2, i % 2)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        lay.addLayout(grid)
        lay.addStretch(1)
        area.setWidget(inner)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(area)

        controller.cast.state_changed.connect(self.refresh)
        controller.changed.connect(self.refresh)
        controller.airplay.status.connect(lambda _s: self.refresh())  # läuft / neu gestartet / beendet
        controller.airplay.log_line.connect(self._log)
        self._first = True
        self.refresh()

    # ================================================================ Einrichtung
    def _setup_card(self) -> QWidget:
        card = QWidget()
        card.setObjectName("Card")
        card.setAttribute(Qt.WA_StyledBackground, True)
        lay = QHBoxLayout(card)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(14)
        lay.addWidget(ChipIcon("sync", theme.current().accent))
        col = QVBoxLayout()
        col.setSpacing(2)
        self.setup_title = QLabel()
        self.setup_title.setFont(font(12, QFont.Bold))
        self.setup_text = QLabel()
        self.setup_text.setObjectName("Muted")
        self.setup_text.setWordWrap(True)
        col.addWidget(self.setup_title)
        col.addWidget(self.setup_text)
        lay.addLayout(col, 1)
        self.setup_btn = button("Automatisch einrichten", "sync", primary=True)
        self.setup_btn.clicked.connect(self.run_setup)
        lay.addWidget(self.setup_btn, 0, Qt.AlignVCenter)
        return card

    def _refresh_setup(self, plan):
        ready = sum(1 for key in ("cast", "airplay") if self._state(key) in ("ready", "live"))
        total = 2
        if self._setup_running:
            return
        if plan:
            self.setup_title.setText(f"{ready} von {total} bereit")
            self.setup_text.setText("Fehlt: " + " · ".join(label for label, _cmd in plan))
            self.setup_btn.show()
        else:
            missing_here = ready < total and not (handy.can_install() or handy.can_winget())
            self.setup_title.setText(f"{ready} von {total} bereit" if ready < total else
                                     f"Alles bereit ({ready}/{total})")
            left = []
            if missing_here:
                left.append("Automatisch nicht möglich – bitte selbst installieren")
            if IS_WINDOWS and not self.controller.airplay.binary():
                left.append("AirPlay: „uxplay-windows“ selbst installieren")
            self.setup_text.setText(" · ".join(left) or "Eingerichtet")
            self.setup_btn.hide()

    def run_setup(self):
        """Fehlende Programme installieren, Name/Code festlegen – alles, was automatisch geht."""
        if self._setup_running:
            return
        self.controller.airplay.ensure_unique_name()  # eindeutiger Name in der iPhone-Liste
        self.controller.cast.code()  # Zugangscode für AluCast anlegen
        plan = handy.setup_plan(self.config)
        self.config["handy"] = {**self.config["handy"], "setup_done": True}
        if not plan:
            self.refresh()
            return
        self._setup_running = True
        self.setup_btn.setEnabled(False)
        self.setup_title.setText("Wird eingerichtet …")

        def progress(text, _step, _total):
            self.setup_text.setText(text)

        def done(errors):
            self._setup_running = False
            self.setup_btn.setEnabled(True)
            handy._vrtp_cache.clear()
            self.refresh()
            if errors:
                self.setup_text.setText("Nicht alles hat geklappt: " + " · ".join(errors))
            else:
                self.config["handy"] = {**self.config["handy"], "firewall_done": True}
                self.refresh()
                self.controller.message.emit("Handy-Empfang eingerichtet.")

        def failed(text):
            done([text])

        run_async(lambda status: handy.run_plan(plan, status), done, failed, on_progress=progress)

    # ================================================================ AluCast
    def _cast_card(self) -> MethodCard:
        card = MethodCard("qr", "#8b5cf6", "Jedes Handy", "Browser + QR-Code · ohne App")
        card.body.addWidget(steps_label("QR-Code zeigen", "Mit dem Handy scannen", "Steuern · Zeichnen · Senden"))
        row = QHBoxLayout()
        self.qr = QLabel()
        self.qr.setFixedSize(92, 92)
        self.qr.setAlignment(Qt.AlignCenter)
        self.qr.setStyleSheet("background:#ffffff; border:1px solid #cbd5e1; border-radius:10px;")
        row.addWidget(self.qr)
        info = QVBoxLayout()
        self.cast_url = QLabel()
        self.cast_url.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.cast_auto = QCheckBox("Beim Start von AluPC mitstarten")
        self.cast_auto.toggled.connect(lambda on: self.config.__setitem__(
            "cast", {**self.config["cast"], "autostart": bool(on)}))
        info.addWidget(self.cast_url)
        ip_row = QHBoxLayout()
        ip_row.addWidget(QLabel("Adresse:"))
        self.cast_ip = QComboBox()
        self.cast_ip.setToolTip("Über diese Adresse erreichen Handys den PC. „Automatisch“ nimmt das WLAN/LAN "
                                "und lässt virtuelle Netze (WSL, VPN, VirtualBox …) weg.")
        self._fill_ip_box()
        self.cast_ip.currentIndexChanged.connect(self._save_ip)
        ip_row.addWidget(self.cast_ip, 1)
        info.addLayout(ip_row)
        info.addWidget(self.cast_auto)
        info.addStretch(1)
        row.addLayout(info, 1)
        card.body.addLayout(row)
        show = button("QR-Code zeigen", "qr", primary=True)
        show.clicked.connect(self.controller.start_cast)
        self.cast_toggle = button("Beenden", "x")
        self.cast_toggle.clicked.connect(self._toggle_cast)
        renew = button("Neuer Code", "refresh")
        renew.setToolTip("Alter QR-Code gilt dann nicht mehr")
        renew.clicked.connect(lambda: (self.controller.cast.renew_code(), self.refresh()))
        for b in (show, self.cast_toggle, renew):
            card.buttons.addWidget(b)
        card.buttons.addStretch(1)
        return card

    def _fill_ip_box(self):
        from ..cast_server import network_addresses

        chosen = self.config["cast"].get("ip", "")
        self.cast_ip.blockSignals(True)
        self.cast_ip.clear()
        addresses = network_addresses()
        best = addresses[0][0] if addresses else "?"
        self.cast_ip.addItem(f"Automatisch ({best})", "")
        for ip, name, _score in addresses:
            self.cast_ip.addItem(f"{ip} – {name}" if name else ip, ip)
        index = self.cast_ip.findData(chosen)
        self.cast_ip.setCurrentIndex(max(0, index))
        self.cast_ip.blockSignals(False)

    def _save_ip(self, *_):
        self.config["cast"] = {**self.config["cast"], "ip": self.cast_ip.currentData() or ""}
        self.controller.cast.state_changed.emit()  # QR-Code auf Monitor 2 neu zeichnen
        self.refresh()

    def _toggle_cast(self):
        if self.controller.cast.running():
            self.controller.stop_cast()
        else:
            self.controller.cast.start()
        self.refresh()

    # ================================================================ AirPlay
    def _airplay_card(self) -> MethodCard:
        card = MethodCard("phone", "#0ea5e9", "iPhone & iPad", "AirPlay · im selben WLAN")
        s = {"airplay_name": "AluPC", "pin": "", **self.config["handy"]}
        form = QGridLayout()
        form.setHorizontalSpacing(10)
        form.addWidget(QLabel("Name:"), 0, 0)
        self.name = QLineEdit(s["airplay_name"])
        self._name_loaded = s["airplay_name"]  # zuletzt gespeicherter Stand – Abweichung = noch nicht gespeichert
        self.name.editingFinished.connect(self._save_name)
        form.addWidget(self.name, 0, 1)
        form.addWidget(QLabel("Code:"), 1, 0)
        pin_row = QHBoxLayout()
        self.pin_mode = QComboBox()
        for key, label in PIN_MODES:
            self.pin_mode.addItem(label, key)
        pin = s.get("pin", "")
        self.pin_mode.setCurrentIndex(max(0, self.pin_mode.findData("fest" if pin.isdigit() else pin)))
        self.pin = QLineEdit(pin if pin.isdigit() else handy.random_pin())
        self.pin.setInputMask("9999")
        self._pin_loaded = self.pin.text()
        self.pin.setMaximumWidth(70)
        self.pin_mode.currentIndexChanged.connect(self._save_pin)
        self.pin.editingFinished.connect(self._save_pin)
        self.controller.airplay.settings_changed.connect(self._sync_airplay)
        pin_row.addWidget(self.pin_mode, 1)
        pin_row.addWidget(self.pin)
        form.addLayout(pin_row, 1, 1)
        card.body.addLayout(form)
        self.airplay_steps = QLabel()
        self.airplay_steps.setWordWrap(True)
        card.body.addWidget(self.airplay_steps)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(90)
        self.log.setPlaceholderText("Meldungen von UxPlay")
        self.log.setPlainText("\n".join(self.controller.airplay.log[-20:]))
        self.log.hide()
        card.body.addWidget(self.log)
        start = button("Auf Monitor 2 zeigen", "phone", primary=True)
        start.clicked.connect(self.controller.start_airplay)
        self.air_start = start
        details = button("Meldungen", "text")
        details.setCheckable(True)
        details.toggled.connect(self.log.setVisible)
        self.ux_pick = link_button("Schon installiert? Programm wählen …", lambda: self._pick("uxplay"))
        card.body.insertWidget(0, self.ux_pick)
        for b in (start, details):
            card.buttons.addWidget(b)
        card.buttons.addStretch(1)
        return card

    def _save_name(self):
        self._apply(airplay_name=self.name.text())
        self._name_loaded = self.name.text()

    def _save_pin(self, *_):
        mode = self.pin_mode.currentData()
        pin = self.pin.text() if mode == "fest" and len(self.pin.text()) == 4 else ("zufall" if mode == "zufall" else "")
        self._pin_loaded = self.pin.text()
        self._apply(pin=pin)

    def _apply(self, **values):
        if self.controller.airplay.update_settings(**values):  # läuft gerade → sofort mit neuen Werten
            self.controller.message.emit("AirPlay neu gestartet")
        self.refresh()

    def _sync_airplay(self):
        """Anderswo geändert (Setup, Einrichtung) → Felder hier nachziehen, sonst schreiben sie Altes zurück."""
        try:
            s = self.controller.airplay.settings()
            if self.name.text() == self._name_loaded:  # nichts Ungespeichertes überschreiben
                self.name.setText(s["airplay_name"])
            self._name_loaded = s["airplay_name"]
            pin = s.get("pin", "")
            self.pin_mode.blockSignals(True)
            self.pin_mode.setCurrentIndex(max(0, self.pin_mode.findData("fest" if pin.isdigit() else pin)))
            self.pin_mode.blockSignals(False)
            if pin.isdigit() and self.pin.text() == self._pin_loaded:
                self.pin.setText(pin)
                self._pin_loaded = pin
            self.refresh()
        except RuntimeError:  # Fenster schon zu
            pass

    def _log(self, line: str):
        try:
            self.log.appendPlainText(line)
        except RuntimeError:
            pass

    # ================================================================ Programme wählen
    def _pick(self, program: str):
        from PySide6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getOpenFileName(self, f"{program} wählen", "", "Programme (*.exe)" if IS_WINDOWS else "")
        if path:
            self.config["handy"] = {**self.config["handy"], f"{program}_path": path}
            handy._vrtp_cache.pop(path, None)
            self.controller.airplay.restart_if_changed()
            self.refresh()

    # ================================================================ Zustand
    def _state(self, key: str) -> str:
        c = self.controller
        if key == "cast":
            return "live" if c.cast.running() else "ready"
        if key == "airplay":
            return "ready" if c.airplay.binary() else "setup"
        return "off"

    def showEvent(self, e):
        super().showEvent(e)
        if self._first:
            self._first = False
            # Beim ersten Öffnen der Seite richtet sich alles selbst ein (einmal Passwort für fehlende Programme)
            if not self.config["handy"].get("setup_done"):
                QTimer.singleShot(400, self.run_setup)

    def refresh(self, *_):
        c = self.controller
        try:
            self._refresh_cards(c)
            self._refresh_setup(handy.setup_plan(self.config))
        except RuntimeError:  # Seite wird gerade geschlossen
            pass

    def _refresh_cards(self, c):
        from ..sources import qr_image

        # --- Jedes Handy (AluCast)
        cast = self.cards["cast"]
        on = c.cast.running()
        code = c.cast.code()
        if on:
            url = c.cast.url()
            if getattr(self, "_qr_for", "") != url:  # QR-Code nur neu berechnen, wenn sich die Adresse ändert
                self._qr_for = url
                img = qr_image(url)
                self.qr.setPixmap(QPixmap.fromImage(img.scaled(84, 84, Qt.KeepAspectRatio, Qt.FastTransformation)))
            cast.set_status("LÄUFT", LIVE, f"Adresse: <b>{c.cast.url(with_code=False)}</b> · Code <b>{code[:3]} "
                                           f"{code[3:]}</b>")
        else:
            cast.set_status("BEREIT", READY, "Sofort nutzbar")
            if getattr(self, "_qr_for", None) != "":
                self._qr_for = ""
                self.qr.setPixmap(icons.pixmap("qr", "#94a3b8", 40))
        self.cast_url.setText("Gleiches WLAN" if not on else "Code = Zugang")
        self.cast_toggle.setText("Beenden" if on else "Starten")
        self.cast_toggle.setIcon(icons.icon("x" if on else "play", theme.current().text, 18))
        self.cast_auto.blockSignals(True)
        self.cast_auto.setChecked(bool(c.cast.settings().get("autostart")))
        self.cast_auto.blockSignals(False)

        # --- iPhone (AirPlay)
        air = self.cards["airplay"]
        ux = c.airplay.binary()
        name = c.airplay.settings()["airplay_name"]
        self.airplay_steps.setText(steps("Auf Monitor 2 zeigen", "iPhone: Bildschirmsynchronisierung",
                                         f"„{name}“ wählen"))
        running = c.airplay.running_settings()
        if running:  # zeigt, womit UxPlay WIRKLICH läuft – so sieht man, ob eine Änderung angekommen ist
            code = f" · Code <b>{running['pin']}</b>" if running.get("pin") and running["pin"] != "zufall" else ""
            air.set_status("LÄUFT", LIVE, f"Läuft als <b>„{running['airplay_name']}“</b>{code}")
        elif ux and handy.supports_vrtp(ux):
            air.set_status("BEREIT", READY, "Bild direkt in AluPC")
        elif ux and handy.is_uxplay_windows(ux):
            air.set_status("BEREIT", READY, "Über uxplay-windows")
        elif ux:
            air.set_status("BEREIT", READY, "Eigenes Fenster im Vollbild")
        elif IS_WINDOWS:
            air.set_status("EINRICHTEN", SETUP, "Empfänger fehlt · oben einrichten")
        else:
            air.set_status("EINRICHTEN", SETUP, "UxPlay fehlt · oben einrichten")
        self.air_start.setEnabled(bool(ux))
        self.ux_pick.setVisible(not ux)
        self.pin.setVisible(self.pin_mode.currentData() == "fest")
