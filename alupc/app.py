"""Programmstart."""

from __future__ import annotations

import argparse
import os
import sys

from . import APP_NAME, __version__

COMMANDS_HELP = ("standbild, schwarz, bild-in-bild, bildschirmschoner, spiegeln, erweitern, naechste_szene, "
                 "vorherige_szene, sperren (Computer), zeigen, szene:NAME")


def parse_args(argv):
    parser = argparse.ArgumentParser(prog="alupc", description=f"{APP_NAME} – Monitor 2 steuern")
    parser.add_argument("--befehl", metavar="BEFEHL", help=f"An laufendes AluPC senden: {COMMANDS_HELP}")
    parser.add_argument("--minimiert", action="store_true", help="Nur als Symbol in der Taskleiste starten")
    parser.add_argument("--version", action="version", version=f"{APP_NAME} {__version__}")
    # Für den automatischen Test des fertigen Programms (baut alles auf, zeigt nichts, beendet sich)
    parser.add_argument("--selbsttest", metavar="LOGDATEI", help=argparse.SUPPRESS)
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


def main(argv=None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.selbsttest:
        return self_test(args.selbsttest)

    if needs_chromium_sandbox_off():
        os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
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
