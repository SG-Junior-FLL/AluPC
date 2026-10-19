"""„Handy verbinden“: QR-Codes zum Scannen – erst das AluPC-WLAN, dann die Seite (Mitspielen) oder, privat nur im
Fenster am PC, AluPC steuern (Adresse mit Code). Kein Abtippen."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
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
    qr.setStyleSheet("background:#ffffff; border-radius:8px; padding:10px;")
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


def control_code(cast) -> tuple[str, list[str]] | None:
    """Privater Steuer-Zugang (Adresse + Code im QR) – NUR im Fenster am PC zeigen, nie auf Monitor 2.
    None = Webserver aus."""
    if not cast.running():
        return None
    return cast.url(True), [f"Adresse: <b>{cast.base().split('://', 1)[-1].rstrip('/')}</b> · Code: "
                            f"<b>{cast.code()}</b>", "Privat – nur hier am PC, nicht auf dem Bildschirm"]


class ConnectDialog(QDialog):
    """QR-Codes zum Scannen: 1. das AluPC-WLAN, dann (codes) z. B. 2. die Seite zum Mitspielen oder – privat, nur
    hier am PC – AluPC steuern. wifi: (Name, Passwort[, unsichtbar]); codes: [(Titel, Inhalt, Zeilen), …]."""

    def __init__(self, title: str, wifi: tuple | None, hint: str = "", on_monitor=None, parent=None,
                 codes: list | tuple = ()):
        super().__init__(parent)
        self.setWindowTitle(title)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 18, 22, 18)
        lay.setSpacing(14)
        lay.addWidget(page_header(title, hint or "Erst den WLAN-Code scannen, dann den Code der Seite", "qr"))
        self.wifi_card = None
        self.cards = []
        if wifi and wifi[0]:
            ssid, password = wifi[0], wifi[1]
            hidden = bool(wifi[2]) if len(wifi) > 2 else False
            row = QHBoxLayout()
            row.setSpacing(14)
            self.wifi_card = _qr_card("1" if codes else "", "AluPC-WLAN", wifi_payload(ssid, password, hidden),
                                      [f"WLAN: <b>{ssid}</b>", f"Passwort: <b>{password}</b>"])
            row.addWidget(self.wifi_card)
            for i, (code_title, payload, lines) in enumerate(codes):
                card = _qr_card(str(i + 2), code_title, payload, lines)
                self.cards.append(card)
                row.addWidget(card)
            lay.addLayout(row)
        else:
            msg = QLabel("Das AluPC-WLAN läuft noch nicht – erst starten (Kachel „Hotspot“ oder Minispiele → „WLAN …“).")
            msg.setWordWrap(True)
            lay.addWidget(msg)
        buttons = QHBoxLayout()
        if on_monitor is not None:
            mon = button("Auf dem Bildschirm zeigen", "monitor")
            mon.setToolTip("Zeigt WLAN-Code und Seiten-Code auf dem Bildschirm – den privaten Steuer-Code nicht")
            mon.clicked.connect(on_monitor)
            buttons.addWidget(mon)
        buttons.addStretch(1)
        close = button("Schließen", "x", primary=True)
        close.clicked.connect(self.accept)
        buttons.addWidget(close)
        lay.addLayout(buttons)


class HotspotDialog(QDialog):
    """Das AluPC-WLAN einstellen und an/aus – EIN WLAN für alles (Hotspot-Kachel, Minispiele, Abstimmen, Steuern).
    kind ist nur noch aus Kompatibilität da; „Mit den Minispielen automatisch starten“ steht immer dabei."""

    def __init__(self, controller, kind: str = "normal", parent=None):
        from PySide6.QtWidgets import QCheckBox, QFormLayout, QLineEdit

        from ..hotspot import hotspot, settings, supported

        super().__init__(parent)
        self.controller, self.kind = controller, "normal"
        title = "AluPC-WLAN"
        self.setWindowTitle(title)
        self.setMinimumWidth(540)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 18, 22, 18)
        lay.setSpacing(12)
        lay.addWidget(page_header(title, "Ein WLAN für alles: Minispiele, Abstimmen, Chat, Whiteboard, Steuern", "wifi"))
        hs = settings(controller.config)
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
        for edit in (self.ssid, self.pw):
            edit.setMinimumHeight(34)
        form.addRow("Name:", self.ssid)
        form.addRow("Passwort:", self.pw)
        from ..hotspot import IS_WINDOWS

        self.hidden = QCheckBox("Unsichtbar (nur per QR-Code)")
        self.hidden.setChecked(bool(hs.get("hidden", True)) and not IS_WINDOWS)
        self.hidden.setEnabled(not IS_WINDOWS)
        if IS_WINDOWS:
            self.hidden.setText("Unsichtbar – geht unter Windows nicht")
        form.addRow("", self.hidden)
        self.auto = QCheckBox("Mit den Minispielen automatisch starten (bleibt danach an)")
        self.auto.setChecked(bool(controller.config["games"].get("auto_wifi", True)))
        form.addRow("", self.auto)
        bl.addLayout(form)
        row = QHBoxLayout()
        self.toggle = button("", "play", primary=True)
        self.toggle.setEnabled(ok)
        self.toggle.clicked.connect(self._toggle)
        row.addWidget(self.toggle)
        self.show_qr = button("QR auf dem Bildschirm", "monitor")
        self.show_qr.setToolTip("WLAN-QR-Code groß auf dem Bildschirm zeigen – Handys scannen ihn von dort")
        self.show_qr.clicked.connect(controller.show_wifi_qr)
        row.addWidget(self.show_qr)
        row.addStretch(1)
        self.pill = QLabel()  # Status als Pille: grün „AN“ / grau „AUS“
        self.pill.setAlignment(Qt.AlignCenter)
        row.addWidget(self.pill)
        bl.addLayout(row)
        self.state = QLabel(why or hotspot.message)
        self.state.setObjectName("Muted")
        self.state.setWordWrap(True)
        bl.addWidget(self.state)
        hint = QLabel("Handy: WLAN-Code scannen, dann den zweiten Code der jeweiligen Seite auf dem Bildschirm (Spiel, "
                      "Chat, Abstimmung …). Steuern: der Steuer-Code unten – privat, nur hier am PC. Hat der PC "
                      "Internet, haben es die Handys im WLAN auch. Das normale WLAN des PCs kann dabei getrennt "
                      "werden (viele WLAN-Karten können nicht beides).")
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        bl.addWidget(hint)
        stay = button("Handy fliegt aus dem WLAN? – Anleitung", "info")
        stay.setToolTip("Ohne Internet am PC verlassen Android und iPhone/iPad das WLAN manchmal – so bleibt es verbunden")
        stay.clicked.connect(self.show_stay_help)
        bl.addWidget(stay, 0, Qt.AlignLeft)
        lay.addWidget(box)
        # Geräte im WLAN (Name, falls beim Mitmachen eingegeben)
        from PySide6.QtWidgets import QListWidget

        dev_box = QFrame()
        dev_box.setObjectName("Card")
        dl = QVBoxLayout(dev_box)
        dl.addWidget(QLabel("<b>Geräte im WLAN</b>"))
        self.devices = QListWidget()
        self.devices.setMinimumHeight(90)
        dl.addWidget(self.devices)
        lay.addWidget(dev_box)
        self._dev_timer = QTimer(self)
        self._dev_timer.timeout.connect(self._fill_devices)
        self._dev_timer.start(2000)
        qr_row = QHBoxLayout()  # 1. WLAN · 2. AluPC steuern (privat – nur hier am PC, nie auf Monitor 2)
        qr_row.addStretch(1)
        self.qr, self.ctl_qr, self.qr_labels = QLabel(), QLabel(), []
        for qr, caption in ((self.qr, "1 · WLAN"), (self.ctl_qr, "2 · AluPC steuern – privat, nur hier am PC")):
            col = QVBoxLayout()
            qr.setAlignment(Qt.AlignCenter)
            qr.setStyleSheet("background:#ffffff; border-radius:8px; padding:10px;")
            col.addWidget(qr, 0, Qt.AlignCenter)
            lab = QLabel(caption)
            lab.setObjectName("Muted")
            lab.setAlignment(Qt.AlignCenter)
            lab.setWordWrap(True)
            lab.setTextInteractionFlags(Qt.TextSelectableByMouse)
            col.addWidget(lab)
            self.qr_labels.append(lab)
            qr_row.addLayout(col)
        qr_row.addStretch(1)
        lay.addLayout(qr_row)
        bottom = QHBoxLayout()
        bottom.addStretch(1)
        close = button("Fertig", "check")
        close.clicked.connect(self.accept)
        bottom.addWidget(close)
        lay.addLayout(bottom)
        controller.hotspot_changed.connect(self._refresh)
        self._refresh()
        self._fill_devices()

    def _mine(self) -> bool:
        from ..hotspot import hotspot

        return hotspot.running

    def _fill_devices(self) -> None:
        from PySide6.QtWidgets import QListWidgetItem

        try:
            devices = self.controller.wlan_devices() if self._mine() else []
            key = [(d["ip"], d["mac"], d["name"]) for d in devices]
            if key == getattr(self, "_dev_key", None):
                return
            self._dev_key = key
            self.devices.blockSignals(True)
            self.devices.clear()
            for d in devices:
                item = QListWidgetItem(f"{d['name']}   ·   {d['ip']}")
                item.setToolTip(d["mac"])
                item.setFlags(Qt.ItemIsEnabled)
                self.devices.addItem(item)
            if not devices:
                item = QListWidgetItem("Noch kein Gerät verbunden" if self._mine() else "WLAN ist aus")
                item.setFlags(Qt.NoItemFlags)
                self.devices.addItem(item)
            self.devices.blockSignals(False)
        except RuntimeError:  # Dialog schon zu
            pass

    def show_stay_help(self) -> None:
        from PySide6.QtWidgets import QMessageBox

        from ..hotspot import stay_help_html

        box = QMessageBox(self)
        box.setWindowTitle("Handy bleibt im AluPC-WLAN")
        box.setTextFormat(Qt.RichText)
        box.setText(stay_help_html())
        show = box.addButton("Auf dem Bildschirm zeigen", QMessageBox.ActionRole)
        box.addButton("Schließen", QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() is show:
            self.controller.show_wifi_help()

    def _refresh(self) -> None:
        from ..hotspot import hotspot

        try:
            on = self._mine()
            self.toggle.setText("WLAN beenden" if on else "WLAN starten")
            self.toggle.setIcon(icons.icon("x" if on else "play", theme.current().text, 18))
            t = theme.current()
            color = t.success if on else t.muted
            self.pill.setText(("● AN" + (" · unsichtbar" if hotspot.hidden else "")) if on else "○ AUS")
            self.pill.setStyleSheet(f"color:{color}; background:{t.soft(color, 0.14)}; border-radius:11px;"
                                    "padding:3px 12px; font-weight:700;")
            ctl = control_code(self.controller.cast) if on else None
            self.qr.setVisible(on)
            self.ctl_qr.setVisible(ctl is not None)
            self.qr_labels[0].setVisible(on)
            self.qr_labels[1].setVisible(ctl is not None)
            self.show_qr.setEnabled(on)
            if on:
                dpr = self.devicePixelRatioF()
                self.qr.setPixmap(qr_pixmap(wifi_payload(hotspot.ssid, hotspot.password, hotspot.hidden), 170, dpr))
            if ctl is not None:
                self.ctl_qr.setPixmap(qr_pixmap(ctl[0], 170, self.devicePixelRatioF()))
                self.qr_labels[1].setText("2 · AluPC steuern<br>" + "<br>".join(ctl[1]))
        except RuntimeError:  # Dialog schon zu
            pass

    def _save(self) -> None:
        from ..hotspot import new_password

        cfg = self.controller.config
        pw = self.pw.text().strip()
        if len(pw) < 8:  # WPA braucht mindestens 8 Zeichen (Linux und Windows gleich)
            pw = new_password()
            self.pw.setText(pw)
        hs = {"ssid": self.ssid.text().strip() or "AluPC", "password": pw, "hidden": self.hidden.isChecked()}
        cfg["hotspot"] = {**(cfg.get("hotspot") or {}), **hs}  # Internet-Freigaben behalten
        games = {k: v for k, v in cfg["games"].items() if k not in ("wifi", "wifi_only")}
        if bool(games.get("auto_wifi", True)) != self.auto.isChecked():
            cfg["games"] = {**games, "auto_wifi": self.auto.isChecked()}

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

        run_async(lambda: self.controller.set_hotspot(on), done, lambda t: done((False, t)))

    def accept(self) -> None:
        self._save()
        self.controller.games_changed.emit()
        super().accept()


WifiDialog = HotspotDialog  # (alter Name)
