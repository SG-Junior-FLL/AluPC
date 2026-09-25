"""Programmstart."""

from __future__ import annotations

import argparse
import os
import sys

from . import APP_NAME, __version__

COMMANDS_HELP = ("standbild, schwarz, bild-in-bild, bildschirmschoner, zeichnen, spiegeln, erweitern, "
                 "naechste_szene, "
                 "vorherige_szene, sperren (Computer), zeigen, szene:NAME")


def parse_args(argv):
    parser = argparse.ArgumentParser(prog="alupc", description=f"{APP_NAME} – Monitor 2 steuern")
    parser.add_argument("--befehl", metavar="BEFEHL", help=f"An laufendes AluPC senden: {COMMANDS_HELP}")
    parser.add_argument("--minimiert", action="store_true", help="Nur als Symbol in der Taskleiste starten")
    parser.add_argument("--version", action="version", version=f"{APP_NAME} {__version__}")
    # Für den automatischen Test des fertigen Programms (baut alles auf, zeigt nichts, beendet sich)
    parser.add_argument("--selbsttest", metavar="LOGDATEI", help=argparse.SUPPRESS)
    # Anmelde-Prüfung für PAM (Fingerabdruckmodul am seriellen Anschluss) – ohne Oberfläche
    parser.add_argument("--fingerabdruck-pam", action="store_true", help=argparse.SUPPRESS)
    return parser.parse_args(argv)


def needs_chromium_sandbox_off() -> bool:
    """Muss die Sandbox der Website-Engine (Chromium) aus sein, damit Websites überhaupt laufen?

    * als root startet Chromium nur ohne Sandbox;
    * Ubuntu/Kubuntu ab 24.04 sperrt „User Namespaces“ für Programme ohne AppArmor-Profil.
      Das .deb-Paket bringt ein Profil mit (dann bleibt die Sandbox an); bei install.sh oder
      Start aus dem Quellcode gibt es keins – dann wird sie ausgeschaltet.
    """
    if not sys.platform.startswith("linux"):
        return False
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        return True
    try:
        with open("/proc/sys/kernel/apparmor_restrict_unprivileged_userns", encoding="ascii") as f:
            restricted = f.read().strip() == "1"
    except OSError:
        restricted = False
    has_profile = os.path.exists("/etc/apparmor.d/alupc") and sys.executable.startswith("/opt/alupc/")
    return restricted and not has_profile


def _media_env() -> None:
    """Videoplayer darf lokale Datenströme lesen (AirPlay-Bild von UxPlay kommt per RTP/UDP)."""
    os.environ.setdefault("QT_FFMPEG_PROTOCOL_WHITELIST", "file,crypto,data,udp,rtp,http,https,tcp,tls")


def main(argv=None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.fingerabdruck_pam:
        from .platform.zw_fingerprint import pam_check

        return pam_check()
    if args.selbsttest:
        return self_test(args.selbsttest)

    if needs_chromium_sandbox_off():
        os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
    _media_env()
    # QtWebEngine muss vor der QApplication geladen werden
    try:
        from PySide6 import QtWebEngineWidgets  # noqa: F401
    except ImportError:
        pass
    from PySide6.QtCore import QCoreApplication, Qt
    from PySide6.QtWidgets import QApplication

    from .ipc import send_to_running

    QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
    app = QApplication(sys.argv[:1])
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setDesktopFileName("alupc")
    app.setQuitOnLastWindowClosed(False)

    # Läuft AluPC schon? Dann nur den Befehl weitergeben.
    if send_to_running(args.befehl or "zeigen"):
        return 0
    if args.befehl and args.befehl != "zeigen":
        print("AluPC läuft nicht – Befehl wird nach dem Start ausgeführt.", file=sys.stderr)

    from .config import Config
    from .controller import Controller
    from .hotkeys import HotkeyManager
    from .ipc import SingleInstance
    from .ui.main_window import MainWindow, app_icon
    from .ui.pip_window import PipWindow

    from .ui import theme

    config = Config()
    appearance = config["appearance"]
    theme.apply(app, appearance.get("mode", "system"), appearance.get("accent", "blau"))
    app.setWindowIcon(app_icon())
    controller = Controller(config)
    hotkeys = HotkeyManager()
    window = MainWindow(controller, hotkeys)
    hotkeys.attach(window)
    hotkeys.triggered.connect(controller.run_command)
    from .ui import hotkey_edit

    hotkey_edit.manager = hotkeys
    problems = hotkeys.apply(config["hotkeys"])
    for p in problems:
        controller.message.emit(p)

    controller.pip = PipWindow(controller)

    instance = SingleInstance(app)

    def on_command(cmd):
        if cmd == "zeigen":
            window.show_normal_front()
        else:
            controller.run_command(cmd)

    instance.command.connect(on_command)
    app.aboutToQuit.connect(controller.shutdown)

    if sys.platform.startswith("linux"):
        # Portable Version: Menüeintrag und Logo für KDE/Wayland anlegen (einmalig, danach nur bei Änderung)
        from .platform.linux_desktop import ensure_user_entry

        ensure_user_entry()

    controller.restore_last()
    if args.befehl and args.befehl != "zeigen":
        on_command(args.befehl)
    if not (args.minimiert or config["start_minimized"]) or not window.tray.isVisible():
        window.show()
    return app.exec()



def self_test(log_path: str) -> int:
    """Startet alle Teile ohne Fenster und schreibt das Ergebnis in eine Datei.

    Wird vom Build auf GitHub mit der fertigen AluPC.exe ausgeführt, damit ein kaputter
    Build (z. B. fehlende Module) auffällt, bevor ihn jemand herunterlädt.
    """
    import tempfile
    import traceback

    lines = []
    try:
        tmp = tempfile.mkdtemp(prefix="alupc-test-")
        os.environ["APPDATA"] = tmp  # eigene Einstellungen nicht anfassen
        os.environ["XDG_CONFIG_HOME"] = tmp
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        _media_env()
        if needs_chromium_sandbox_off():
            os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
        from PySide6 import QtWebEngineWidgets  # noqa: F401
        from PySide6.QtCore import QCoreApplication, Qt
        from PySide6.QtWidgets import QApplication

        QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
        app = QApplication(sys.argv[:1])

        from .config import Config
        from .controller import Controller
        from .hotkeys import HotkeyManager
        from .ui import theme
        from .ui.main_window import MainWindow
        from .ui.pip_window import PipWindow

        config = Config()
        theme.apply(app, "dunkel", "blau")
        controller = Controller(config)
        lines.append(f"Monitore: {controller.display.name}, Fenster: {type(controller.windows).__name__}, "
                     f"Fingerabdruck: {controller.fingerprint.name}")
        hotkeys = HotkeyManager()
        window = MainWindow(controller, hotkeys)
        hotkeys.attach(window)
        controller.pip = PipWindow(controller)
        controller.show_source({"type": "text", "text": "Selbsttest"})
        controller.show_source({"type": "clock"})
        controller.show_source({"type": "website", "url": "about:blank"})
        controller.toggle_screensaver()
        controller.toggle_screensaver()
        lines.append(f"Leerlaufzeit: {controller.screensaver.idle.method}")
        from .platform.zw_fingerprint import HAVE_SERIAL, candidate_ports

        lines.append(f"Serielle Fingerabdruckmodule: pyserial {'da' if HAVE_SERIAL else 'FEHLT'}, "
                     f"Anschlüsse: {len(candidate_ports())}")
        if sys.platform.startswith("linux"):
            missing = controller.fingerprint.missing_packages()
            lines.append("Fingerabdruck-Pakete: " + ("vollständig" if not missing else "fehlen: " + ", ".join(missing))
                         + f" · automatisch installierbar: {'ja' if controller.fingerprint.can_auto_install else 'nein'}")
        controller.sounds.play("builtin:ding")  # Ton-Wiedergabe (FFmpeg/Multimedia im Paket vorhanden?)
        window.open_browser_control()
        window.browser_control.close()
        controller.run_command("timer_start_pause")
        controller.run_command("timer_start_pause")
        if controller.windows.can_list:  # Fensterliste (Windows: Win32-Aufrufe) einmal wirklich ausführen
            wins = controller.windows.list_windows()
            controller.windows.is_minimized("AluPC-Selbsttest-gibt-es-nicht")
            lines.append(f"Fenster: {len(wins)}")
        controller.config["transition"] = {"type": "zoom", "ms": 100}
        controller.show_source({"type": "text", "text": "Übergang"})
        controller.set_media_volume(volume=50)
        controller.mirror()  # Aufnahme + Mauszeiger (Windows: echtes Zeigerbild über Win32)
        from .platform.cursor_native import cursor_image

        cursor_image()
        controller.update_cursor_guard()
        for page in range(len(window.pages)):  # auch die erst beim Öffnen gebauten Seiten prüfen
            window._go(page)
        window.open_presenter()  # Zeigen & Zeichnen: Vorschau, Strich, Laser
        from PySide6.QtCore import QPointF

        controller.laser.begin_stroke("pen", "#ff0000", 0.004, QPointF(0.1, 0.1))
        controller.laser.extend_stroke(QPointF(0.5, 0.5))
        controller.laser.remote_point(QPointF(0.5, 0.5))
        app.processEvents()
        window.presenter.close()
        app.processEvents()
        from . import handy
        from .ui.handy_dialog import HandyDialog

        ux = controller.airplay.binary()
        sc = handy.find_program("scrcpy", "")
        lines.append(f"Handy: UxPlay {ux or 'nicht installiert'}"
                     + (f" (Bild an AluPC: {'ja' if handy.supports_vrtp(ux) else 'nein, eigenes Fenster'})" if ux else "")
                     + f", scrcpy {sc or 'nicht installiert'}")
        dlg = HandyDialog(controller, window)
        dlg.show()
        app.processEvents()
        dlg.close()
        if not ux:  # ohne UxPlay nur Hinweis auf Monitor 2
            controller.show_source({"type": "airplay"})
            app.processEvents()
        controller.shutdown()
        lines.append("OK")
        code = 0
    except Exception:  # noqa: BLE001
        lines.append(traceback.format_exc())
        code = 1
    with open(log_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return code
