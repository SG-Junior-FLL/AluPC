"""„Handy verbinden“: großer, scharfer QR-Code zum Scannen – und, wenn ein WLAN bekannt ist (eigener Hotspot oder
im Setup eingetragenes Gäste-WLAN), davor ein WLAN-QR-Code: Handy scannt → ist im WLAN → scannt den zweiten Code
→ Seite ist offen. Kein Abtippen."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QDialog, QFrame, QHBoxLayout, QLabel, QVBoxLayout

from ..screens import wifi_payload
from ..sources import qr_pixmap
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


class WifiDialog(QDialog):
    """Spiele-Fenster → „WLAN für Handys“: eigenen Hotspot starten ODER das vorhandene WLAN eintragen (dann zeigt
    die Lobby einen WLAN-QR-Code – praktisch für Gäste, die das Passwort nicht kennen)."""

    def __init__(self, controller, parent=None):
        from PySide6.QtWidgets import QFormLayout, QLineEdit

        from ..hotspot import hotspot, settings, supported

        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle("WLAN für Handys")
        self.setMinimumWidth(520)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 18, 22, 18)
        lay.setSpacing(12)
        lay.addWidget(page_header("WLAN für Handys", "Handys scannen erst den WLAN-Code, dann den Spiel-Code", "phone"))
        # --- eigener Hotspot
        hs = settings(controller.config)
        ok, why = supported()
        box = QFrame()
        box.setObjectName("Card")
        bl = QVBoxLayout(box)
        bl.addWidget(QLabel("<b>Eigenes WLAN (Hotspot)</b> – der PC macht selbst ein WLAN auf"))
        form = QFormLayout()
        self.ssid = QLineEdit(hs["ssid"])
        self.ssid.setMaxLength(32)
        self.pw = QLineEdit(hs["password"])
        self.pw.setMaxLength(63)
        form.addRow("Name:", self.ssid)
        form.addRow("Passwort:", self.pw)
        bl.addLayout(form)
        row = QHBoxLayout()
        self.toggle = button("Hotspot starten" if not hotspot.running else "Hotspot beenden", "play" if not
                             hotspot.running else "x", primary=not hotspot.running)
        self.toggle.setEnabled(ok)
        self.toggle.clicked.connect(self._toggle)
        row.addWidget(self.toggle)
        row.addStretch(1)
        bl.addLayout(row)
        self.state = QLabel(why or hotspot.message or "Hinweis: Viele WLAN-Karten trennen dabei das normale WLAN – "
                            "der PC hat dann (außer per Kabel) kein Internet.")
        self.state.setObjectName("Muted")
        self.state.setWordWrap(True)
        bl.addWidget(self.state)
        lay.addWidget(box)
        # --- vorhandenes WLAN eintragen
        box2 = QFrame()
        box2.setObjectName("Card")
        b2 = QVBoxLayout(box2)
        b2.addWidget(QLabel("<b>Vorhandenes WLAN</b> – nur für den WLAN-QR-Code (leer = keiner)"))
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
        close = button("Fertig", "check", primary=True)
        close.clicked.connect(self.accept)
        bottom.addWidget(close)
        lay.addLayout(bottom)

    def _save(self) -> None:
        cfg = self.controller.config
        hs = {"ssid": self.ssid.text().strip() or "AluPC-Spiele", "password": self.pw.text().strip()}
        if len(hs["password"]) < 8:  # WPA braucht mindestens 8 Zeichen
            from ..hotspot import new_password

            hs["password"] = new_password()
            self.pw.setText(hs["password"])
        ssid = self.r_ssid.text().strip()
        cfg["games"] = {**cfg["games"], "hotspot": hs,
                        "wifi": {"ssid": ssid, "password": self.r_pw.text()} if ssid else {}}

    def _toggle(self) -> None:
        from ..hotspot import hotspot
        from .util import run_async

        self._save()
        on = not hotspot.running
        self.toggle.setEnabled(False)
        self.state.setText("Hotspot startet …" if on else "Hotspot wird beendet …")

        def done(result):
            ok, msg = result
            self.state.setText(msg)
            self.toggle.setEnabled(True)
            self.toggle.setText("Hotspot beenden" if hotspot.running else "Hotspot starten")
            self.controller.games_changed.emit()

        run_async(lambda: self.controller.set_hotspot(on), done, lambda t: done((False, t)))

    def accept(self) -> None:
        self._save()
        self.controller.games_changed.emit()
        super().accept()
