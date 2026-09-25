"""Handy einrichten: AluCast (Browser/QR-Code), AirPlay (UxPlay), Android (scrcpy), Miracast (Windows)."""

from __future__ import annotations

import subprocess
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .. import handy
from .util import error_box, run_async
from . import icons, theme
from .widgets import Banner, button, page_header

IS_WINDOWS = sys.platform.startswith("win")
PIN_MODES = [("", "Kein Code (jeder im WLAN kann senden)"), ("fest", "Fester 4-stelliger Code"),
             ("zufall", "Neuer Code bei jedem neuen Gerät")]


def _wrap(group: QGroupBox) -> QWidget:
    page = QWidget()
    lay = QVBoxLayout(page)
    lay.addWidget(group)
    lay.addStretch(1)
    return page


class HandyDialog(QDialog):
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.config = controller.config
        self.setWindowTitle("Handy auf Monitor 2")
        self.resize(780, 680)
        s = {**{"airplay_name": "AluPC", "pin": "", "uxplay_path": "", "scrcpy_path": ""}, **self.config["handy"]}

        # ---------------------------------------------------------------- AirPlay
        air = QGroupBox("iPhone / iPad – AirPlay")
        af = QFormLayout(air)
        self.ux_status = Banner("", "info")
        af.addRow(self.ux_status)
        ux_row = QHBoxLayout()
        self.ux_install = button("UxPlay installieren", "plus", primary=True)
        self.ux_install.clicked.connect(lambda: self._install("uxplay"))
        self.ux_pick = button("UxPlay-Programm wählen …", "window")
        self.ux_pick.clicked.connect(lambda: self._pick("uxplay"))
        ux_row.addWidget(self.ux_install)
        ux_row.addWidget(self.ux_pick)
        ux_row.addStretch(1)
        af.addRow(ux_row)
        self.name = QLineEdit(s["airplay_name"])
        self.name.setPlaceholderText("AluPC")
        self.name.editingFinished.connect(self._save)
        af.addRow("Name am iPhone:", self.name)
        self.pin_mode = QComboBox()
        for key, label in PIN_MODES:
            self.pin_mode.addItem(label, key)
        pin = s.get("pin", "")
        self.pin_mode.setCurrentIndex(max(0, self.pin_mode.findData("fest" if pin.isdigit() else pin)))
        self.pin = QLineEdit(pin if pin.isdigit() else handy.random_pin())
        self.pin.setInputMask("9999")
        self.pin.setMaximumWidth(80)
        self.pin_mode.currentIndexChanged.connect(self._save)
        self.pin.editingFinished.connect(self._save)
        pin_row = QHBoxLayout()
        pin_row.addWidget(self.pin_mode, 1)
        pin_row.addWidget(self.pin)
        af.addRow("Code:", pin_row)
        how = QLabel("Am iPhone/iPad: <b>Kontrollzentrum → Bildschirmsynchronisierung → Name wählen</b>. "
                     "iPhone und PC müssen im selben WLAN sein.")
        how.setWordWrap(True)
        af.addRow(how)

        # ---------------------------------------------------------------- Android
        andr = QGroupBox("Android – scrcpy (USB oder WLAN)")
        nf = QFormLayout(andr)
        self.sc_status = Banner("", "info")
        nf.addRow(self.sc_status)
        sc_row = QHBoxLayout()
        self.sc_install = button("scrcpy installieren", "plus", primary=True)
        self.sc_install.clicked.connect(lambda: self._install("scrcpy"))
        self.sc_pick = button("scrcpy-Programm wählen …", "window")
        self.sc_pick.clicked.connect(lambda: self._pick("scrcpy"))
        sc_row.addWidget(self.sc_install)
        sc_row.addWidget(self.sc_pick)
        sc_row.addStretch(1)
        nf.addRow(sc_row)
        steps = QLabel("Einmalig am Handy: <b>Einstellungen → Über das Telefon → 7× auf „Build-Nummer“</b> tippen, "
                       "dann unter <b>Entwickleroptionen → USB-Debugging</b> einschalten. Per USB-Kabel verbinden "
                       "und am Handy „Zulassen“ tippen.<br>Chromecast-Empfang ist auf einem PC nicht möglich "
                       "(Google lässt nur zertifizierte Geräte zu).")
        steps.setWordWrap(True)
        nf.addRow(steps)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(110)
        self.log.setPlaceholderText("Meldungen von UxPlay erscheinen hier, sobald AirPlay läuft.")
        self.log.setPlainText("\n".join(controller.airplay.log[-30:]))
        controller.airplay.log_line.connect(self._log)

        start_air = button("iPhone/iPad anzeigen", "phone", primary=True)
        start_air.clicked.connect(lambda: (self.controller.start_airplay(), self.accept()))
        af.addRow(self.log)
        af.addRow(start_air)
        start_andr = button("Android anzeigen", "phone", primary=True)
        start_andr.clicked.connect(lambda: (self.controller.start_android(), self.accept()))
        nf.addRow(start_andr)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._cast_tab(), icons.icon("qr", theme.current().text, 18), "Browser (QR-Code)")
        self.tabs.addTab(_wrap(air), icons.icon("phone", theme.current().text, 18), "iPhone (AirPlay)")
        self.tabs.addTab(_wrap(andr), icons.icon("phone", theme.current().text, 18), "Android")
        self.tabs.addTab(self._miracast_tab(), icons.icon("cast", theme.current().text, 18), "Miracast")
        close = button("Schließen", "x")
        close.clicked.connect(self.accept)
        bottom = QHBoxLayout()
        bottom.addStretch(1)
        bottom.addWidget(close)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 20, 22, 18)
        lay.setSpacing(12)
        lay.addWidget(page_header("Handy auf Monitor 2",
                                  "Ohne App per Browser, iPhone per AirPlay, Android per scrcpy, Miracast (Windows)."))
        lay.addWidget(self.tabs, 1)
        lay.addLayout(bottom)
        self.controller.cast.state_changed.connect(self.refresh_cast)
        self.refresh()
        self.refresh_cast()

    # ------------------------------------------------------------ AluCast
    def _cast_tab(self) -> QWidget:
        page = QWidget()
        row = QHBoxLayout(page)
        row.setSpacing(18)
        self.qr = QLabel()
        self.qr.setFixedSize(220, 220)
        self.qr.setAlignment(Qt.AlignCenter)
        self.qr.setStyleSheet("background:#ffffff; border:1px solid #cbd5e1; border-radius:12px;")
        row.addWidget(self.qr, 0, Qt.AlignTop)
        col = QVBoxLayout()
        col.setSpacing(8)
        intro = QLabel("<b>AluCast</b> – selbst gebaut, ohne App: QR-Code mit der Kamera-App scannen, dann "
                       "<b>Fotos, Videos, Links (z. B. YouTube) und Text</b> auf Monitor 2 senden und Monitor 2 "
                       "fernsteuern. Geht mit iPhone und Android.")
        intro.setWordWrap(True)
        col.addWidget(intro)
        self.cast_status = Banner("", "info")
        col.addWidget(self.cast_status)
        self.cast_url = QLabel()
        self.cast_url.setTextInteractionFlags(Qt.TextSelectableByMouse)
        col.addWidget(self.cast_url)
        buttons = QHBoxLayout()
        self.cast_show = button("QR-Code auf Monitor 2", "qr", primary=True)
        self.cast_show.clicked.connect(lambda: (self.controller.start_cast(), self.refresh_cast()))
        self.cast_toggle = button("Beenden", "x")
        self.cast_toggle.clicked.connect(self._toggle_cast)
        renew = button("Neuer Code", "refresh")
        renew.setToolTip("Alter Code (und alter QR-Code) gilt dann nicht mehr")
        renew.clicked.connect(lambda: (self.controller.cast.renew_code(), self.refresh_cast()))
        for b in (self.cast_show, self.cast_toggle, renew):
            buttons.addWidget(b)
        buttons.addStretch(1)
        col.addLayout(buttons)
        self.cast_auto = QCheckBox("Beim Start von AluPC mitstarten")
        self.cast_auto.toggled.connect(lambda on: self.controller.config.__setitem__(
            "cast", {**self.controller.config["cast"], "autostart": bool(on)}))
        col.addWidget(self.cast_auto)
        note = QLabel("Handy und PC müssen im selben WLAN sein. Wer den QR-Code oder Code sieht, kann senden – "
                      "bei Bedarf „Neuer Code“. Den Handy-Bildschirm selbst kann ein Browser nicht übertragen "
                      "(dafür AirPlay, Android oder Miracast)." + (" Windows fragt beim ersten Start, ob AluPC "
                      "im Netzwerk erreichbar sein darf: „Privates Netzwerk“ erlauben." if IS_WINDOWS else ""))
        note.setObjectName("Muted")
        note.setWordWrap(True)
        col.addWidget(note)
        col.addStretch(1)
        row.addLayout(col, 1)
        return page

    def refresh_cast(self):
        from ..sources import qr_image

        server = self.controller.cast
        try:
            on = server.running()
        except RuntimeError:
            return
        if on:
            self.cast_status.set(f"Läuft – Code: {server.code()[:3]} {server.code()[3:]}", "ok")
            self.cast_url.setText(f"Adresse zum Eintippen: <b>{server.url(with_code=False)}</b>")
            img = qr_image(server.url())
            self.qr.setPixmap(QPixmap.fromImage(img.scaled(204, 204, Qt.KeepAspectRatio, Qt.FastTransformation)))
        else:
            self.cast_status.set("Aus – „QR-Code auf Monitor 2“ startet AluCast.", "info")
            self.cast_url.setText("")
            self.qr.setPixmap(icons.pixmap("qr", "#94a3b8", 64))
        self.cast_toggle.setText("Beenden" if on else "Starten")
        self.cast_toggle.setIcon(icons.icon("x" if on else "play", theme.current().text, 18))
        self.cast_auto.blockSignals(True)
        self.cast_auto.setChecked(bool(server.settings().get("autostart")))
        self.cast_auto.blockSignals(False)

    def _toggle_cast(self):
        if self.controller.cast.running():
            self.controller.stop_cast()
        else:
            self.controller.cast.start()
        self.refresh_cast()

    # ------------------------------------------------------------ Miracast
    def _miracast_tab(self) -> QWidget:
        from ..platform import miracast

        page = QWidget()
        form = QFormLayout(page)
        self.mc_status = Banner("", "info")
        form.addRow(self.mc_status)
        if not miracast.IS_WINDOWS:
            self.mc_status.set("Miracast-Empfang geht nur unter Windows: Linux hat keinen brauchbaren Empfänger "
                               "(bräuchte „Wi-Fi Direct“, das unter Kubuntu mit dem Netzwerk-Manager kollidiert). "
                               "Unter Linux: QR-Code (AluCast), AirPlay oder Android per scrcpy.", "warn")
            return page
        how = QLabel("Windows hat einen eigenen Miracast-Empfänger („Drahtlose Anzeige“). AluPC startet ihn und "
                     "legt ihn im Vollbild auf Monitor 2.<br><b>Am Handy:</b> Samsung „Smart View“, Xiaomi "
                     "„Übertragen“, andere „Bildschirm übertragen/Screen Mirroring“ → diesen PC wählen. "
                     "Laptops: <b>Windows-Taste + K</b>.<br>iPhones können kein Miracast (dafür AirPlay), "
                     "Google-Pixel-Handys auch nicht mehr.")
        how.setWordWrap(True)
        form.addRow(how)
        row = QHBoxLayout()
        self.mc_install = button("Drahtlose Anzeige installieren", "plus", primary=True)
        self.mc_install.clicked.connect(self._install_miracast)
        self.mc_install.hide()
        settings = button("„Projizieren auf diesen PC“ einstellen", "sliders")
        settings.setToolTip("Dort „Überall verfügbar“ (bzw. „Überall in sicheren Netzwerken“) wählen")
        settings.clicked.connect(miracast.open_settings)
        start = button("Miracast starten", "cast", primary=True)
        start.clicked.connect(lambda: (self.controller.start_miracast(), self.accept()))
        for b in (self.mc_install, settings, start):
            row.addWidget(b)
        row.addStretch(1)
        form.addRow(row)
        self.mc_status.set("Suche die App „Drahtlose Anzeige“ …", "info")
        run_async(miracast.find_app, self._miracast_found, lambda t: self.mc_status.set(t, "warn"))
        return page

    def _miracast_found(self, app):
        try:
            if app:
                self.mc_status.set(f"Gefunden: {app['name']}. Unter „Projizieren auf diesen PC“ einmal "
                                   "„Überall verfügbar“ einstellen.", "ok")
                self.mc_install.hide()
            else:
                self.mc_status.set("Die Windows-App „Drahtlose Anzeige“ fehlt. „Installieren“ lädt sie von Windows "
                                   "Update (Administrator-Abfrage, dauert einige Minuten).", "warn")
                self.mc_install.show()
        except RuntimeError:  # Fenster schon zu
            pass

    def _install_miracast(self):
        from ..platform import miracast

        self.mc_install.setEnabled(False)
        self.mc_install.setText("Wird installiert …")

        def done(_r):
            self.mc_install.setEnabled(True)
            self.mc_install.setText("Drahtlose Anzeige installieren")
            run_async(miracast.find_app, self._miracast_found)

        def failed(text):
            self.mc_install.setEnabled(True)
            self.mc_install.setText("Drahtlose Anzeige installieren")
            error_box(self, f"Installation fehlgeschlagen: {text}")

        run_async(miracast.install, done, failed)

    # ------------------------------------------------------------ Zustand
    def refresh(self):
        server = self.controller.airplay
        ux = server.binary()
        if ux:
            stream = handy.supports_vrtp(ux)
            self.ux_status.set(f"UxPlay gefunden: {ux}\n" + (
                "Das iPhone-Bild erscheint direkt in AluPC (auch in eigenen Szenen)." if stream else
                "Ältere Version (vor 1.73): Das Bild erscheint in einem eigenen Vollbild-Fenster auf Monitor 2."),
                "ok")
        elif IS_WINDOWS:
            self.ux_status.set("UxPlay nicht gefunden. Für Windows gibt es UxPlay als MSYS2-Build (braucht außerdem "
                               "„Bonjour“ von Apple) – Anleitung: github.com/FDH2/UxPlay. Danach hier das "
                               "Programm wählen.", "warn")
        else:
            self.ux_status.set("UxPlay nicht gefunden – „UxPlay installieren“ (Kubuntu, Passwort nötig).", "warn")
        sc = handy.find_program("scrcpy", self.config["handy"].get("scrcpy_path", ""))
        if sc:
            self.sc_status.set(f"scrcpy gefunden: {sc}", "ok")
        elif IS_WINDOWS:
            self.sc_status.set("scrcpy nicht gefunden – von github.com/Genymobile/scrcpy (Windows-ZIP) laden, "
                               "entpacken und hier „scrcpy.exe“ wählen.", "warn")
        else:
            self.sc_status.set("scrcpy nicht gefunden – „scrcpy installieren“ (Kubuntu, Passwort nötig).", "warn")
        can = handy.can_install()
        self.ux_install.setVisible(can and not ux)
        self.sc_install.setVisible(can and not sc)
        self.pin.setVisible(self.pin_mode.currentData() == "fest")

    def _save(self, *_):
        mode = self.pin_mode.currentData()
        pin = self.pin.text() if mode == "fest" and len(self.pin.text()) == 4 else ("zufall" if mode == "zufall" else "")
        self.config["handy"] = {**self.config["handy"], "airplay_name": self.name.text().strip() or "AluPC",
                                "pin": pin}
        self.refresh()

    def _log(self, line: str):
        try:
            self.log.appendPlainText(line)
        except RuntimeError:  # Fenster schon zu
            pass

    def _pick(self, program: str):
        path, _ = QFileDialog.getOpenFileName(self, f"{program} wählen", "",
                                              "Programme (*.exe)" if IS_WINDOWS else "")
        if path:
            self.config["handy"] = {**self.config["handy"], f"{program}_path": path}
            handy._vrtp_cache.pop(path, None)
            self.refresh()

    def _install(self, program: str):
        btn = self.ux_install if program == "uxplay" else self.sc_install
        btn.setEnabled(False)
        btn.setText("Wird installiert …")

        def work():
            proc = subprocess.run(handy.install_command(program), capture_output=True, text=True, timeout=900)
            if proc.returncode != 0:
                raise RuntimeError((proc.stderr or proc.stdout or "abgebrochen").strip().splitlines()[-1])

        def done(_r):
            btn.setEnabled(True)
            self.refresh()

        def failed(text):
            btn.setEnabled(True)
            btn.setText(f"{program} installieren")
            error_box(self, f"Installation fehlgeschlagen: {text}")

        run_async(work, done, failed)

