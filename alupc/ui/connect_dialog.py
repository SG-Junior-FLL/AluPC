"""„Handy verbinden“: großer, scharfer QR-Code zum Scannen – und, wenn ein WLAN bekannt ist (eigener Hotspot oder
im Setup eingetragenes Gäste-WLAN), davor ein WLAN-QR-Code: Handy scannt → ist im WLAN → scannt den zweiten Code
→ Seite ist offen. Kein Abtippen."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QDialog, QFrame, QHBoxLayout, QLabel, QVBoxLayout

from ..screens import wifi_payload
from ..sources import qr_pixmap
from . import icons, theme
from .widgets import button, font, page_header

QR_PX = 260


def _qr_card(step: str, title: str, payload: str, lines: list[str]) -> QFrame:
    card = QFrame()
    card.setObjectName("Card")
    lay = QVBoxLayout(card)
    lay.setContentsMargins(18, 16, 18, 16)
    lay.setSpacing(8)
    head = QLabel(f"<span style='opacity:.6'>{step}</span>  <b>{title}</b>")
    head.setFont(font(12))
    lay.addWidget(head)
    qr = QLabel()
    qr.setObjectName("QrBox")
    qr.setAlignment(Qt.AlignCenter)
    qr.setStyleSheet("background:#ffffff; border-radius:14px; padding:10px;")
    dpr = QGuiApplication.primaryScreen().devicePixelRatio() if QGuiApplication.primaryScreen() else 1.0
    qr.setPixmap(qr_pixmap(payload, QR_PX, dpr))
    lay.addWidget(qr, 0, Qt.AlignCenter)
    for text in lines:
        lab = QLabel(text)
        lab.setWordWrap(True)
        lab.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lab.setAlignment(Qt.AlignCenter)
        lay.addWidget(lab)
    return card


class ConnectDialog(QDialog):
    """url: Seite fürs Handy · wifi: (Name, Passwort) oder None · on_monitor: Knopf „Auf Monitor 2 zeigen“."""

    def __init__(self, title: str, url: str, wifi: tuple[str, str] | None = None, hint: str = "",
                 on_monitor=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.url = url
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 18, 22, 18)
        lay.setSpacing(14)
        lay.addWidget(page_header(title, hint or "Mit der Kamera-App des Handys scannen", "qr"))
        row = QHBoxLayout()
        row.setSpacing(14)
        self.wifi_card = None
        if wifi and wifi[0]:
            ssid, password = wifi
            self.wifi_card = _qr_card("1", "WLAN verbinden", wifi_payload(ssid, password),
                                      [f"WLAN: <b>{ssid}</b>", f"Passwort: <b>{password}</b>" if password else
                                       "ohne Passwort"])
            row.addWidget(self.wifi_card)
        self.link_card = _qr_card("2" if self.wifi_card else "", "Seite öffnen", url,
                                  [f"<span style='color:#60a5fa'>{url.split('?')[0]}</span>"])
        row.addWidget(self.link_card)
        lay.addLayout(row)
        buttons = QHBoxLayout()
        copy = button("Link kopieren", "copy")
        copy.clicked.connect(lambda: (QGuiApplication.clipboard().setText(self.url), copy.setText("Kopiert ✓")))
        buttons.addWidget(copy)
        if on_monitor is not None:
            mon = button("Auf Monitor 2 zeigen", "monitor")
            mon.clicked.connect(on_monitor)
            buttons.addWidget(mon)
        buttons.addStretch(1)
        close = button("Schließen", "x", primary=True)
        close.clicked.connect(self.accept)
        buttons.addWidget(close)
        lay.addLayout(buttons)


class HotspotDialog(QDialog):
    """Hotspot einstellen und an/aus. kind „normal“ (Hotspot-Kachel) oder „spiele“ (Spiele-WLAN aus dem
    Minispiele-Fenster: offen, mit Anmeldeseite, geht mit den Spielen aus – dazu „vorhandenes WLAN“ für den QR-Code)."""

    def __init__(self, controller, kind: str = "normal", parent=None):
        from PySide6.QtWidgets import QCheckBox, QFormLayout, QLineEdit

        from ..hotspot import IS_WINDOWS, hotspot, settings, supported

        super().__init__(parent)
        self.controller, self.kind = controller, kind
        games = kind == "spiele"
        title = "Spiele-WLAN" if games else "Hotspot"
        self.setWindowTitle(title)
        self.setMinimumWidth(540)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 18, 22, 18)
        lay.setSpacing(12)
        lay.addWidget(page_header(title, "Handys verbinden sich, gehen automatisch auf die Spielsteuerung · aus, wenn "
                                         "die Spiele enden" if games else "Der PC macht ein eigenes WLAN auf", "wifi"))
        hs = settings(controller.config, kind)
        ok, why = supported()
        box = QFrame()
        box.setObjectName("Card")
        bl = QVBoxLayout(box)
        form = QFormLayout()
        self.ssid = QLineEdit(hs["ssid"])
        self.ssid.setMaxLength(32)
        self.pw = QLineEdit(hs["password"])
        self.pw.setMaxLength(63)
        self.pw.setPlaceholderText("mindestens 8 Zeichen")
        form.addRow("Name:", self.ssid)
        form.addRow("Passwort:", self.pw)
        self.open_net = None
        if games and not IS_WINDOWS:  # offenes WLAN: ein Tippen, dann kommt die Anmeldeseite von selbst
            self.open_net = QCheckBox("Offen (ohne Passwort) – empfohlen für Spiele")
            self.open_net.setChecked(not hs["password"])
            self.open_net.toggled.connect(lambda on: self.pw.setEnabled(not on))
            self.pw.setEnabled(not self.open_net.isChecked())
            form.addRow("", self.open_net)
        bl.addLayout(form)
        row = QHBoxLayout()
        self.toggle = button("", "play", primary=True)
        self.toggle.setEnabled(ok)
        self.toggle.clicked.connect(self._toggle)
        row.addWidget(self.toggle)
        row.addStretch(1)
        bl.addLayout(row)
        self.state = QLabel(why or hotspot.message)
        self.state.setObjectName("Muted")
        self.state.setWordWrap(True)
        bl.addWidget(self.state)
        hint = QLabel(("Anmeldeseite (Linux): beim Start einmal das Passwort des PCs (für die Weiterleitung). "
                       "Windows: Handys nehmen den QR-Code. " if games else "")
                      + "Viele WLAN-Karten trennen dabei das normale WLAN – der PC hat dann (außer per Kabel) "
                        "kein Internet.")
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        bl.addWidget(hint)
        lay.addWidget(box)
        self.qr = QLabel()
        self.qr.setAlignment(Qt.AlignCenter)
        self.qr.setStyleSheet("background:#ffffff; border-radius:14px; padding:10px;")
        lay.addWidget(self.qr, 0, Qt.AlignCenter)
        self.r_ssid = self.r_pw = None
        if games:  # Alternative ohne Hotspot: vorhandenes WLAN nur für den WLAN-QR-Code
            box2 = QFrame()
            box2.setObjectName("Card")
            b2 = QVBoxLayout(box2)
            b2.addWidget(QLabel("<b>Oder vorhandenes WLAN</b> – nur für den WLAN-QR-Code in der Lobby"))
            form2 = QFormLayout()
            wifi = controller.config["games"].get("wifi") or {}
            self.r_ssid = QLineEdit(wifi.get("ssid", ""))
            self.r_pw = QLineEdit(wifi.get("password", ""))
            self.r_pw.setEchoMode(QLineEdit.PasswordEchoOnEdit)
            form2.addRow("Name:", self.r_ssid)
            form2.addRow("Passwort:", self.r_pw)
            b2.addLayout(form2)
            lay.addWidget(box2)
        bottom = QHBoxLayout()
        bottom.addStretch(1)
        close = button("Fertig", "check")
        close.clicked.connect(self.accept)
        bottom.addWidget(close)
        lay.addLayout(bottom)
        controller.hotspot_changed.connect(self._refresh)
        self._refresh()

    def _mine(self) -> bool:
        from ..hotspot import hotspot

        return hotspot.running and hotspot.kind == self.kind

    def _refresh(self) -> None:
        from ..hotspot import hotspot

        try:
            on = self._mine()
            self.toggle.setText(("Spiele-WLAN" if self.kind == "spiele" else "Hotspot") +
                                (" beenden" if on else " starten"))
            self.toggle.setIcon(icons.icon("x" if on else "play", theme.current().text, 18))
            self.qr.setVisible(on)
            if on:
                dpr = self.devicePixelRatioF()
                self.qr.setPixmap(qr_pixmap(wifi_payload(hotspot.ssid, hotspot.password), 220, dpr))
        except RuntimeError:  # Dialog schon zu
            pass

    def _save(self) -> None:
        from ..hotspot import IS_WINDOWS, new_password

        cfg = self.controller.config
        pw = "" if self.open_net is not None and self.open_net.isChecked() else self.pw.text().strip()
        if (pw or IS_WINDOWS or self.kind == "normal") and len(pw) < 8:  # WPA braucht mindestens 8 Zeichen
            pw = new_password()
            self.pw.setText(pw)
        default = "AluPC-Spiele" if self.kind == "spiele" else "AluPC"
        hs = {"ssid": self.ssid.text().strip() or default, "password": pw}
        if self.kind == "spiele":
            games = {**cfg["games"], "hotspot": hs}
            ssid = self.r_ssid.text().strip()
            games["wifi"] = {"ssid": ssid, "password": self.r_pw.text()} if ssid else {}
            cfg["games"] = games
        else:
            cfg["hotspot"] = hs

    def _toggle(self) -> None:
        from .util import run_async

        self._save()
        on = not self._mine()
        self.toggle.setEnabled(False)
        self.state.setText("Startet …" if on else "Wird beendet …")

        def done(result):
            try:
                self.state.setText(result[1])
                self.toggle.setEnabled(True)
            except RuntimeError:
                pass
            self._refresh()
            self.controller.games_changed.emit()

        run_async(lambda: self.controller.set_hotspot(on, self.kind), done, lambda t: done((False, t)))

    def accept(self) -> None:
        self._save()
        self.controller.games_changed.emit()
        super().accept()


WifiDialog = HotspotDialog  # (alter Name)
