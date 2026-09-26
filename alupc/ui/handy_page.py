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
            self.setup_title.setText(f"{ready} von {total} Wegen bereit")
            self.setup_text.setText("Fehlt noch: " + ", ".join(label for label, _cmd in plan) + ". "
                                    + ("Ein Klick installiert alles (einmal Passwort)." if not IS_WINDOWS else
                                       "Ein Klick installiert es über winget."))
            self.setup_btn.show()
        else:
            missing_here = ready < total and not (handy.can_install() or handy.can_winget())
            self.setup_title.setText(f"{ready} von {total} Wegen bereit" if ready < total else
                                     f"Alles eingerichtet – {ready} von {total} Wegen bereit")
            left = []
            if missing_here:
                left.append("Automatisch installieren geht auf diesem System nicht (kein apt/pkexec bzw. winget) – "
                            "fehlende Programme bitte selbst installieren")
            if IS_WINDOWS and not self.controller.airplay.binary():
                left.append("AirPlay unter Windows braucht UxPlay (von Hand, siehe Karte)")
            self.setup_text.setText(" · ".join(left) or "Alles, was automatisch geht, ist eingerichtet.")
            self.setup_btn.hide()

    def run_setup(self):
        """Fehlende Programme installieren, Name/Code festlegen – alles, was automatisch geht."""
        if self._setup_running:
            return
        s = self.config["handy"]
        if s.get("airplay_name", "AluPC") == "AluPC":  # eindeutiger Name in der iPhone-Liste
            self.config["handy"] = {**s, "airplay_name": handy.default_airplay_name()}
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
        card.body.addWidget(steps_label("„QR-Code zeigen“ klicken",
                                         "Mit der Handy-Kamera scannen",
                                         "Fotos, Videos, Links, Text senden – oder fernsteuern"))
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
        self.name.editingFinished.connect(self._save_airplay)
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
        self.pin.setMaximumWidth(70)
        self.pin_mode.currentIndexChanged.connect(self._save_airplay)
        self.pin.editingFinished.connect(self._save_airplay)
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

    def _save_airplay(self, *_):
        mode = self.pin_mode.currentData()
        pin = self.pin.text() if mode == "fest" and len(self.pin.text()) == 4 else ("zufall" if mode == "zufall" else "")
        self.config["handy"] = {**self.config["handy"], "airplay_name": self.name.text().strip() or "AluPC",
                                "pin": pin}
        self.refresh()

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
            cast.set_status("BEREIT", READY, "Funktioniert sofort – nichts zu installieren.")
            if getattr(self, "_qr_for", None) != "":
                self._qr_for = ""
                self.qr.setPixmap(icons.pixmap("qr", "#94a3b8", 40))
        self.cast_url.setText("Handy und PC im selben WLAN." if not on else "Wer den Code sieht, kann senden.")
        self.cast_toggle.setText("Beenden" if on else "Starten")
        self.cast_toggle.setIcon(icons.icon("x" if on else "play", theme.current().text, 18))
        self.cast_auto.blockSignals(True)
        self.cast_auto.setChecked(bool(c.cast.settings().get("autostart")))
        self.cast_auto.blockSignals(False)

        # --- iPhone (AirPlay)
        air = self.cards["airplay"]
        ux = c.airplay.binary()
        name = c.airplay.settings()["airplay_name"]
        self.airplay_steps.setText(steps("„Auf Monitor 2 zeigen“ klicken",
                                         "iPhone: Kontrollzentrum → Bildschirmsynchronisierung",
                                         f"„{name}“ wählen"))
        if ux and handy.supports_vrtp(ux):
            air.set_status("BEREIT", READY, "Das iPhone-Bild erscheint direkt in AluPC (auch in Szenen).")
        elif ux:
            air.set_status("BEREIT", READY, "Ältere UxPlay-Version: Bild im eigenen Vollbild-Fenster auf Monitor 2.")
        elif IS_WINDOWS:
            air.set_status("VON HAND", SETUP, "Braucht UxPlay (MSYS2-Build, github.com/FDH2/UxPlay) und Apple "
                                              "„Bonjour“ – danach „UxPlay wählen …“.")
        else:
            air.set_status("EINRICHTEN", SETUP, "UxPlay fehlt – „Automatisch einrichten“ oben installiert es.")
        self.air_start.setEnabled(bool(ux))
        self.ux_pick.setVisible(not ux)
        self.pin.setVisible(self.pin_mode.currentData() == "fest")
