"""Handy einrichten: AirPlay (UxPlay) und Android (scrcpy) – finden, installieren, Name und Code."""

from __future__ import annotations

import subprocess
import sys

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QVBoxLayout,
)

from .. import handy
from .util import error_box, run_async
from .widgets import Banner, button, page_header

IS_WINDOWS = sys.platform.startswith("win")
PIN_MODES = [("", "Kein Code (jeder im WLAN kann senden)"), ("fest", "Fester 4-stelliger Code"),
             ("zufall", "Neuer Code bei jedem neuen Gerät")]


class HandyDialog(QDialog):
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.config = controller.config
        self.setWindowTitle("Handy auf Monitor 2")
        self.resize(760, 640)
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
        if IS_WINDOWS:
            project = button("Windows: „Projizieren auf diesen PC“ öffnen (Miracast/Smart View)", "extend")
            project.clicked.connect(lambda: subprocess.Popen(["cmd", "/c", "start", "", "ms-settings:project"]))
            nf.addRow(project)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(110)
        self.log.setPlaceholderText("Meldungen von UxPlay erscheinen hier, sobald AirPlay läuft.")
        self.log.setPlainText("\n".join(controller.airplay.log[-30:]))
        controller.airplay.log_line.connect(self._log)

        start_air = button("iPhone/iPad anzeigen", "phone", primary=True)
        start_air.clicked.connect(lambda: (self.controller.start_airplay(), self.accept()))
        start_andr = button("Android anzeigen", "phone")
        start_andr.clicked.connect(lambda: (self.controller.start_android(), self.accept()))
        close = button("Schließen", "x")
        close.clicked.connect(self.accept)
        bottom = QHBoxLayout()
        bottom.addStretch(1)
        for w in (close, start_andr, start_air):
            bottom.addWidget(w)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 20, 22, 18)
        lay.setSpacing(12)
        lay.addWidget(page_header("Handy auf Monitor 2", "iPhone/iPad per AirPlay, Android per scrcpy."))
        lay.addWidget(air)
        lay.addWidget(andr)
        lay.addWidget(self.log)
        lay.addLayout(bottom)
        self.refresh()

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

