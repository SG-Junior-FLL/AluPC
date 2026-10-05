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
    # Sprachtest des fertigen Programms: echtes Mikrofon → Vosk → Verstehen, Ergebnis in LOGDATEI
    parser.add_argument("--sprachtest", metavar="LOGDATEI", help=argparse.SUPPRESS)
    # Nur das Mikrofon: kommt Ton an? (Gerät, Format, Pegel) – ohne Sprachmodell
    parser.add_argument("--mikrofontest", metavar="LOGDATEI", help=argparse.SUPPRESS)
    # Anmelde-Prüfung für PAM (Fingerabdruckmodul am seriellen Anschluss) – ohne Oberfläche
    parser.add_argument("--fingerabdruck-pam", action="store_true", help=argparse.SUPPRESS)
    # Windows: Anmeldung mit Modul einrichten (mit Administratorrechten gestartet, siehe windows_serial_login)
    parser.add_argument("--fingerabdruck-windows", metavar="AUFTRAG", help=argparse.SUPPRESS)
    # Lüfter setzen (läuft per pkexec als Administrator, ohne Oberfläche)
    parser.add_argument("--luefter", metavar="REGLER=WERT,…", help=argparse.SUPPRESS)
    return parser.parse_args(argv)


def voice_test(log_path: str, seconds: float = 150.0) -> int:
    """Wie im Betrieb zuhören (Mikrofon über Qt, Vosk, Verstehen) und alles mitschreiben. Ende nach
    ALUPC_SPRACHTEST_ANZAHL Befehlen (Standard 4) oder nach `seconds`. Exit 0, wenn alle Befehle kamen."""
    import time

    from PySide6.QtCore import QCoreApplication

    from .config import Config
    from .voice import VoiceControl

    app = QCoreApplication.instance() or QCoreApplication([])
    want = int(os.environ.get("ALUPC_SPRACHTEST_ANZAHL", "4"))
    need = int(os.environ.get("ALUPC_SPRACHTEST_MIN", str(want)))
    log = open(log_path, "w", encoding="utf-8")  # noqa: SIM115

    def write(text):
        log.write(text + "\n")
        log.flush()

    config = Config()
    config["voice"] = {**config["voice"], "on": True, "stt": "vosk", "only_voices": False}
    vc = VoiceControl(config)
    commands = []
    vc.state_changed.connect(lambda st: write(f"ZUSTAND {st}"))
    vc.heard.connect(lambda t: write(f"GEHÖRT {t}"))
    vc.command.connect(lambda c, label, t: (commands.append(c), write(f"BEFEHL {c} ({label})")))
    vc.not_understood.connect(lambda t: write(f"NICHT VERSTANDEN {t}"))
    from PySide6.QtMultimedia import QMediaDevices

    write("MIKROFONE " + " | ".join(d.description() for d in QMediaDevices.audioInputs()))
    vc.start()
    end = time.monotonic() + seconds
    while time.monotonic() < end and len(commands) < want:  # (bei weniger Befehlen: bis zum Zeitende warten)
        app.processEvents()
        time.sleep(0.01)
    write(f"FEHLER {' | '.join(vc.errors) or '-'} · Mikrofon neu geöffnet: {vc.mic_restarts}")
    write(f"ENDE {len(commands)}/{want}")
    vc.stop()
    log.close()
    return 0 if len(commands) >= need else 1


def mic_test(log_path: str, seconds: float = 5.0) -> int:
    """Mikrofon öffnen wie im Betrieb und `seconds` lang messen. Exit 0, wenn Ton ankam."""
    from PySide6.QtCore import QCoreApplication

    from .config import Config
    from .voice import VoiceControl

    app = QCoreApplication.instance() or QCoreApplication([])
    report = VoiceControl(Config()).probe_microphone(seconds, app.processEvents)
    with open(log_path, "w", encoding="utf-8") as f:
        for key, value in report.items():
            f.write(f"{key}: {value}\n")
    return 0 if report.get("sekunden_ton", 0) > seconds * 0.3 else 1


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
    from .platform.child_env import restore_system_env

    restore_system_env()  # fertige Linux-Version: gestartete Programme (UxPlay …) bekommen die System-Bibliotheken
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.fingerabdruck_pam:
        from .platform.zw_fingerprint import pam_check

        return pam_check()
    if args.fingerabdruck_windows:
        from .platform.windows_serial_login import run_request_file

        return run_request_file(args.fingerabdruck_windows)
    if args.luefter:
        from .platform.fans import apply_request

        return apply_request(args.luefter)
    if args.selbsttest:
        return self_test(args.selbsttest)
    if args.sprachtest:
        return voice_test(args.sprachtest)
    if args.mikrofontest:
        return mic_test(args.mikrofontest)

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

    from . import bug_report, reset

    reset.cleanup_pending()  # Reste von „Alle Daten löschen“ – bevor Protokolle wieder Dateien öffnen
    bug_report.install()  # Programmfehler/Abstürze mitschreiben (für „Fehlerbericht“)
    from .config import Config
    from .controller import Controller
    from .hotkeys import HotkeyManager
    from .ipc import SingleInstance
    from .ui.main_window import MainWindow, app_icon
    from .ui.pip_window import PipWindow

    from .ui import theme

    config = Config()
    try:  # Dual-Boot: Einstellungen vom anderen System übernehmen, bevor die Oberfläche entsteht
        from .settings_sync import auto_setup, sync_once

        auto_setup(config)  # anderes System hat schon einen Sync-Ordner → ohne Klicken verbinden
        sync_once(config)
    except Exception:  # noqa: BLE001 - Abgleich darf den Start nie verhindern
        pass
    appearance = config["appearance"]
    theme.apply(app, appearance.get("mode", "system"), appearance.get("accent", "system"))
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
    # Anmeldung mit dem Finger → „Willkommen, Lena!“ (auch direkt nach dem Start, wenn AluPC automatisch startet)
    from .ui.welcome_window import WelcomeWatcher

    controller.welcome_watcher = WelcomeWatcher(config, parent=controller)
    controller.welcome_watcher.greet.connect(controller.show_welcome)

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
    # AirPlay „immer bereit“: UxPlay mit AluPCs Name/Code im Hintergrund (übernimmt fremde Autostarts)
    from PySide6.QtCore import QTimer

    QTimer.singleShot(2500, controller.airplay_background)
    if args.befehl and args.befehl != "zeigen":
        on_command(args.befehl)
    if not (args.minimiert or config["start_minimized"]) or not window.tray.isVisible():
        window.show()
    if not config["first_run_done"]:  # erster Start: alles mit einem Klick einrichten
        from PySide6.QtCore import QTimer

        QTimer.singleShot(700, lambda: (window.show(), window.open_first_run()))
    from . import reset

    QTimer.singleShot(900, lambda: reset.report_leftovers(window, config))  # nach „Alle Daten löschen“
    QTimer.singleShot(1200, controller.welcome_watcher.greet_startup)
    code = app.exec()
    if reset.pending():
        # erst jetzt löschen: AirPlay, Protokolle usw. sind beendet und halten keine Dateien mehr offen
        instance.server.close()
        reset.finish_and_restart()
    return code



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
        # Im Selbsttest nichts installieren (die Handy-Seite richtet sich sonst beim ersten Öffnen selbst ein)
        config["handy"] = {**config["handy"], "setup_done": True}
        theme.apply(app, "dunkel", "blau")
        controller = Controller(config)
        lines.append(f"Monitore: {controller.display.name}, Fenster: {type(controller.windows).__name__}, "
                     f"Fingerabdruck: {controller.fingerprint.name}")
        hotkeys = HotkeyManager()
        window = MainWindow(controller, hotkeys)
        hotkeys.attach(window)
        controller.pip = PipWindow(controller)
        controller.show_welcome("Selbsttest", style="konfetti")  # Begrüßung
        controller._welcome.finish()
        for typ in ("zufall", "wetter", "umfrage", "spiel", "system"):  # neue Seiten im fertigen Paket vorhanden?
            controller.show_source({"type": typ}, remember=False)
            kind = type(controller.output.content).__name__
            lines.append(f"Seite {typ}: {kind}")
            if kind == "TextSource":  # = Fehlermeldung statt Seite (Modul fehlt im Paket?)
                raise RuntimeError(f"Seite {typ} fehlt im Paket")
        controller.show_source({"type": "text", "text": "Selbsttest"})
        controller.show_source({"type": "clock"})
        controller.show_source({"type": "website", "url": "about:blank"})
        controller.toggle_screensaver()
        controller.toggle_screensaver()
        lines.append(f"Leerlaufzeit: {controller.screensaver.idle.method}")
        from .voice import vosk_available

        if not vosk_available():  # Sprachbefehle: Vosk samt Bibliothek (libvosk) im Paket?
            raise RuntimeError("Spracherkennung (vosk) fehlt im Paket")
        import vosk

        lines.append(f"Spracherkennung: vosk {getattr(vosk, '__version__', '')} ok")
        # Natürliche Stimme (Piper samt espeak-ng-Daten) und genaue Erkennung (Whisper) im Paket?
        from piper.phonemize_espeak import EspeakPhonemizer

        phonemes = EspeakPhonemizer().phonemize("de", "Alles klar.")
        if not phonemes or not phonemes[0]:
            raise RuntimeError("Piper/espeak-ng liefert keine Lautschrift")
        from faster_whisper import WhisperModel  # noqa: F401  (lädt ctranslate2, tokenizers, av)

        lines.append(f"Stimme (Piper) und Whisper: ok · Lautschrift „{''.join(phonemes[0])[:20]}“")
        from .game_sounds import GameSounds

        GameSounds(config).play("tick")  # Spiel-Töne lassen sich erzeugen
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

        ux = controller.airplay.binary()
        lines.append(f"AirPlay: UxPlay {ux or 'nicht installiert'}"
                     + (" (Bild an AluPC: " + ("ja, -vrtp" if handy.supports_vrtp(ux) else "ja, RTP über -vd/-vc/-vs"
                                               if handy.supports_rtp_pipeline(ux) else "nein, eigenes Fenster") + ")"
                        if ux else ""))
        lines.append("Handy-Einrichtung: " + (", ".join(label for label, _ in handy.setup_plan(config))
                                                 or "nichts zu installieren"))
        from .ui.first_run import FirstRunDialog

        first = FirstRunDialog(controller, window)
        first.show()
        app.processEvents()
        first._step_monitors()  # nur die harmlosen Schritte (nichts installieren)
        first.close()
        window.open_handy_window()
        window.handy_page.refresh()
        window.handy_window.close()
        if not ux:  # ohne UxPlay nur Hinweis auf Monitor 2
            controller.show_source({"type": "airplay"})
            app.processEvents()
        # AluCast: Webserver starten, Seite abrufen, QR-Code zeichnen (segno im Paket?)
        import urllib.request

        controller.config["cast"] = {**controller.config["cast"], "port": 18765}
        controller.start_cast()
        app.processEvents()
        with urllib.request.urlopen(f"http://127.0.0.1:{controller.cast.port}/", timeout=10) as r:
            page_ok = r.status == 200 and b"AluCast" in r.read()
        controller.output.content.grab()
        lines.append(f"AluCast: Seite {'ok' if page_ok else 'FEHLER'}, Adresse {controller.cast.url(False)}")
        controller.stop_cast()
        from . import settings_sync
        from .platform import fans

        exported = settings_sync.export_settings(config, list(settings_sync.SECTIONS))
        chips = fans.read_sensors()
        lines.append(f"Einstellungen: {len(exported['data'])} Gruppen exportierbar, Laufwerke für Dual-Boot: "
                     f"{len(settings_sync.drives())}; Sensoren: {sum(len(c.temps) for c in chips)} Temperaturen, "
                     f"{sum(len(c.pwms) for c in chips)} Lüfter-Regler")
        # „Läuft gerade“: Baustein da (Windows: WinRT mitgeliefert?) und echte Abfrage beim System
        from . import now_playing

        ok, why = now_playing.available()
        if not ok:
            raise RuntimeError(f"Läuft gerade: {why}")
        try:
            reader = now_playing.reader()
            track = reader.read()
            reader.close()
            result = f"{track.player}: {track.title}" if track else "nichts läuft"
        except Exception as exc:  # noqa: BLE001 - ohne Player/Session ist das kein Fehler von AluPC
            result = f"Abfrage nicht möglich: {type(exc).__name__}: {exc}"
        lines.append(f"Läuft gerade: {result}")
        lines.append(f"DIAG Läuft gerade: {result}")
        # Leistung: zwei echte Messungen im fertigen Programm (Windows: Task-Manager-Zähler)
        import time

        from . import sysinfo

        sampler = sysinfo.Sampler()
        time.sleep(1.0)
        snap = sampler.sample()
        time.sleep(1.0)
        snap = sampler.sample()
        gpu = snap.gpu
        perf = (f"CPU {snap.cpu:.0f} % ({len(snap.cores)} Kerne, Takt {snap.freq or 0:.0f} MHz, "
                f"Quelle {'Task-Manager-Zähler' if sampler._pdh else 'psutil'}) · RAM {snap.ram:.0f} % · "
                f"GPU {(f'{gpu.name} {gpu.load:.0f} %') if gpu and gpu.load is not None else 'keine Daten'} · "
                f"Netz ↓{sysinfo.fmt_rate(snap.net_down)} ↑{sysinfo.fmt_rate(snap.net_up)} · "
                f"Laufwerke {len(snap.disks)} · Temperatur {snap.cpu_temp if snap.cpu_temp is not None else '–'}")
        lines.append(f"Leistung: {perf}")
        lines.append(f"DIAG Leistung: {perf}")
        if not (0 <= snap.cpu <= 100 and snap.ram_total > 0 and snap.cores):
            raise RuntimeError(f"Leistung falsch gemessen: {perf}")
        controller.show_source({"type": "nowplaying"})
        app.processEvents()
        # Overlays: alle Vorlagen einmal im eigenen Fenster über Monitor 2 zeichnen
        from . import overlays

        saved_overlays = controller.config["overlays"]
        controller.config["overlays"] = {"on": True, "items": [overlays.from_template(t, n)
                                                               for _c, n, _d, t in overlays.TEMPLATES]}
        controller.overlays_changed()
        app.processEvents()
        ow = controller.overlay_window
        if ow.needed():
            ow.repaint()
        lines.append(f"Overlays: {len(ow.items())} Vorlagen, Fenster "
                     f"{'sichtbar' if ow.isVisible() else 'aus (kein Monitor 2)'}")
        controller.config["overlays"] = saved_overlays
        controller.overlays_changed()
        from . import diagnose

        # Echte Probe-Aufnahme (Spiegeln) + Gesamtbild – steht dann im Protokoll (CI zeigt es an)
        for line in diagnose.report(controller).splitlines():
            if line.strip():
                lines.append("DIAG " + line.strip())
        controller.show_source({"type": "camera", "device_id": "selbsttest"})  # Kamera-Leiste/Optionen
        window.camera_bar.sync()
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
