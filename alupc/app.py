"""Programmstart."""

from __future__ import annotations

import argparse
import os
import sys

from . import APP_NAME, __version__

COMMANDS_HELP = "standbild, schwarz, bild-in-bild, spiegeln, erweitern, zeigen, sperren, szene:NAME"


def parse_args(argv):
    parser = argparse.ArgumentParser(prog="alupc", description=f"{APP_NAME} – Monitor 2 steuern")
    parser.add_argument("--befehl", metavar="BEFEHL", help=f"An laufendes AluPC senden: {COMMANDS_HELP}")
    parser.add_argument("--minimiert", action="store_true", help="Nur als Symbol in der Taskleiste starten")
    parser.add_argument("--version", action="version", version=f"{APP_NAME} {__version__}")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)

    if hasattr(os, "geteuid") and os.geteuid() == 0:
        # Chromium (Websites) startet als root nur ohne Sandbox – normal läuft AluPC als Benutzer
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
    problems = hotkeys.apply(config["hotkeys"])
    for p in problems:
        controller.message.emit(p)

    controller.pip = PipWindow(controller)

    instance = SingleInstance(app)

    def on_command(cmd):
        if cmd == "zeigen":
            window.show_normal_front()
        elif cmd == "sperren":
            window.lock()
        else:
            controller.run_command(cmd)

    instance.command.connect(on_command)
    app.aboutToQuit.connect(controller.shutdown)

    locked_start = bool(config["lock"].get("enabled"))
    if locked_start:
        from .ui.lock_dialog import LockDialog

        controller.locked = True
        LockDialog(controller).exec()
        controller.locked = False

    controller.restore_last()
    if args.befehl and args.befehl != "zeigen":
        on_command(args.befehl)
    if not (args.minimiert or config["start_minimized"]) or not window.tray.isVisible():
        window.show()
    return app.exec()

