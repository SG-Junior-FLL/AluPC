"""Diagnose: Was geht auf diesem PC, was nicht – und warum? (Text zum Kopieren und Weitergeben)

Prüft echt statt zu raten: Monitore, eine kurze Probe-Aufnahme für das Spiegeln, AirPlay (UxPlay, avahi/
Bonjour), RGB (OpenRGB), Lüfter, Handy-Steuerung.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import time

from . import __version__


def _run(cmd: list[str], timeout: float = 8) -> str:
    try:
        flags = 0x08000000 if sys.platform.startswith("win") else 0
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, creationflags=flags)
        return (out.stdout + out.stderr).strip()
    except (OSError, subprocess.SubprocessError) as exc:
        return f"(nicht ausführbar: {exc})"


def capture_probe(controller, seconds: float = 3.0) -> str:
    """Kurze echte Aufnahme des Hauptmonitors: kommen Bilder an? (läuft im Qt-Hauptthread)"""
    from PySide6.QtCore import QCoreApplication

    from .sources import ScreenSource

    main = controller.main_screen()
    if main is None:
        return "kein Hauptmonitor gefunden"
    src = ScreenSource({"screen_name": main.name(), "fps": 30})
    errors = []
    src.no_signal.connect(errors.append)
    end = time.monotonic() + seconds
    while time.monotonic() < end and not errors:
        QCoreApplication.processEvents()
        time.sleep(0.02)
    img = src.image()
    result = (f"Methode {src.method}, {src.frames} Bilder in {seconds:.0f} s"
              + (f", Bild {img.width()}×{img.height()}" if img is not None and not img.isNull() else ", KEIN Bild")
              + (f", Fehler: {errors[0]}" if errors else ""))
    src.stop()
    src.deleteLater()
    return result


def audio_check() -> str:
    """Linux: Kann UxPlay Ton ausgeben? (AAC-Decoder + Ausgabe für GStreamer, laufender Ton-Server)"""
    if not shutil.which("gst-inspect-1.0"):
        parts = ["gst-inspect-1.0 fehlt (Paket gstreamer1.0-tools) – Ton-Teile nicht prüfbar"]
    else:
        def has(element: str) -> bool:
            try:
                return subprocess.run(["gst-inspect-1.0", "--exists", element], timeout=10).returncode == 0
            except (OSError, subprocess.SubprocessError):
                return False

        sinks = [e for e in ("pulsesink", "pipewiresink", "alsasink") if has(e)]
        parts = [f"AAC-Decoder: {'ja' if has('avdec_aac') else 'FEHLT (gstreamer1.0-libav)'}",
                 f"Ausgabe: {', '.join(sinks) if sinks else 'KEINE (gstreamer1.0-plugins-good)'}"]
    info = _run(["pactl", "info"]) if shutil.which("pactl") else ""
    if info.startswith("(") or "Connection" in info or "Verbindung" in info:
        info = ""
    sink = next((x.split(":", 1)[1].strip() for x in info.splitlines() if x.startswith(("Default Sink", "Standard-Ziel"))),
                "")
    parts.append(f"Ton-Server: {'Ausgang ' + sink if sink else ('läuft' if info else 'nicht gefunden')}")
    return " · ".join(parts)


def report(controller, probe: bool = True) -> str:
    from PySide6 import __version__ as pyside_version
    from PySide6.QtGui import QGuiApplication

    from . import handy
    from .platform import fans
    from .rgb import OpenRGB, RGBError, find_openrgb

    lines = [f"AluPC {__version__} · {'Programm' if getattr(sys, 'frozen', False) else 'Quellcode'}"
             f" · {sys.executable}",
             f"System: {platform.platform()} · Python {platform.python_version()} · PySide6 {pyside_version}"]
    if sys.platform.startswith("linux"):
        lines.append(f"Sitzung: {os.environ.get('XDG_SESSION_TYPE', '?')} · Desktop: "
                     f"{os.environ.get('XDG_CURRENT_DESKTOP', '?')}")
    from PySide6.QtWidgets import QApplication

    lines.append(f"Schrift: {QApplication.font().family()} {QApplication.font().pointSizeF():.0f} pt · Stil: "
                 f"{QApplication.style().name()}")
    lines.append("")
    lines.append("== Monitore ==")
    for s in QGuiApplication.screens():
        g = s.geometry()
        lines.append(f"  {s.name()}: {g.width()}×{g.height()} bei {g.x()},{g.y()} · Skalierung {s.devicePixelRatio()}"
                     + (" · HAUPTMONITOR" if s == QGuiApplication.primaryScreen() else ""))
    out, main = controller.output_screen(), controller.main_screen()
    lines.append(f"  AluPC: Monitor 1 = {main.name() if main else '–'}, Monitor 2 = {out.name() if out else '–'}"
                 f" · Hauptmonitor laut System: {controller.display.main_name() or '–'}"
                 f" · Monitor 2 fest gewählt: {controller.config['output_screen'] or 'nein'}")
    lines.append(f"  Monitor-Steuerung: {controller.display.name} · verfügbar: "
                 f"{'ja' if controller.display.available() else 'nein'}")
    lines.append(f"  Gerade: {controller.describe()}")
    if probe:
        lines.append(f"  Probe-Aufnahme (Spiegeln): {capture_probe(controller)}")
    if getattr(controller, "last_mirror_problem", ""):
        lines.append(f"  Letztes Spiegel-Problem: {controller.last_mirror_problem}")
    saver = getattr(controller, "screensaver", None)
    if saver is not None:
        idle = saver.idle
        unit = {None: "Einheit noch unbekannt", 1.0: "Sekunden", 0.001: "Millisekunden"}.get(idle.scale, "?") \
            if idle.method == "freedesktop" else ""
        lines.append(f"  Bildschirmschoner: Leerlauf über {idle.method}{f' ({unit})' if unit else ''} · jetzt "
                     f"{saver.idle_seconds():.0f} s · {saver.keep_awake.describe()}")

    lines.append("")
    lines.append("== WLAN / Anmeldeseite ==")
    from . import hotspot as hs

    h = hs.hotspot
    lines.append(f"  Hotspot: {'an' if h.running else 'aus'} ({h.kind or '–'}) · {h.ssid or '–'} · {h.ip or '–'}"
                 f" · Anmeldeseite: {'an' if h.portal else 'aus'}")
    if h.message:
        lines.append(f"  Meldung: {h.message}")
    if hs.DNS_INFO:
        lines.append(f"  {hs.DNS_INFO}")
    if hs._dns is not None:
        lines.append(f"  AluPC-DNS: {hs._dns.host}:{hs._dns.port} · Fragen bisher: {hs._dns.queries}"
                     f" · Internet frei für: {', '.join(sorted(hs._dns.allowed)) or 'niemand'}")
    if h.running:
        nb = hs.neighbors()
        lines.append("  Geräte im WLAN: " + (", ".join(
            f"{k} ({v}, DNS {hs.client_status(k)[0]}, Prüfung {'ja' if hs.client_status(k)[1] else 'nein'})"
            for k, v in nb.items()) or "keine gefunden"))
        if hs._dns is not None and hs._dns.clients:
            lines.append(f"  Namensfragen je Gerät: {hs._dns.clients}")

    lines.append("")
    lines.append("== AirPlay (iPhone) ==")
    ux = controller.airplay.binary()
    if handy.is_uxplay_windows(ux):
        lines.append(f"  UxPlay: {ux} (uxplay-windows, Community-Paket, Bild im eigenen Fenster)")
        lines.append(f"  Optionen-Datei: {handy.uxplay_windows_arguments_file()}"
                     + (" · ACHTUNG: Maschinen-Datei hat Vorrang" if handy.uxplay_windows_machine_file().exists()
                        else ""))
        tail = handy.uxplay_windows_log_tail(6)
        if tail:
            lines.append("  Protokoll: " + " | ".join(tail))
    else:
        version = _run([ux, "-v"]) if ux else ""
        lines.append(f"  UxPlay: {ux or 'NICHT installiert'}"
                     + (f" · {version.splitlines()[0]}" if version else ""))
    if ux:
        way = "ja (-vrtp)" if handy.supports_vrtp(ux) else \
            "ja (über -vd/-vc/-vs, RTP)" if handy.supports_rtp_pipeline(ux) else "nein, eigenes Fenster"
        lines.append(f"  Bild direkt in AluPC: {way} · jetzt: {controller.airplay.mode or '–'}")
    if sys.platform.startswith("win"):
        lines.append(f"  Bonjour: {'installiert' if handy.bonjour_installed() else 'FEHLT'}")
    else:
        lines.append(f"  avahi-daemon läuft: {'ja' if handy.avahi_running() else 'NEIN (iPhone findet den PC nicht)'}")
    lines.append(f"  Name: {controller.airplay.settings()['airplay_name']} · läuft: "
                 f"{'ja' if controller.airplay.running() else 'nein'}")
    if sys.platform.startswith("linux"):
        lines.append("  Ton: " + audio_check())
        if handy.in_virtual_machine():
            opts = " ".join(handy.vm_options(handy.uxplay_help(ux))) if ux else ""
            lines.append(f"  Virtuelle Maschine: ja · UxPlay-Zusatz: {opts or 'keiner (Version kennt ihn nicht)'}")
    if controller.airplay.log:
        lines.append("  Letzte Meldungen: " + " | ".join(controller.airplay.log[-5:]))
        audio = [x for x in controller.airplay.log if "audio" in x.lower() or "aac" in x.lower()]
        if audio:
            lines.append("  Ton-Meldungen: " + " | ".join(audio[-4:]))
    try:  # Wird das Bild-Fenster gefunden? (AluPC legt es auf Monitor 2)
        wins = [f"„{w.title}“ ({w.app})" for w in controller.windows.list_windows()
                if "uxplay" in (w.app or "").lower() or "uxplay" in w.title.lower()]
        lines.append("  AirPlay-Fenster: " + (", ".join(wins) if wins else "keins offen (erst bei Verbindung)"))
    except Exception:  # noqa: BLE001
        pass

    lines.append("")
    lines.append("== Handy-Steuerung (QR) ==")
    cast = controller.cast
    lines.append(f"  läuft: {'ja, ' + cast.url(False) if cast.running() else 'nein'}")

    lines.append("")
    lines.append("== RGB und Lüfter ==")
    orgb = find_openrgb(controller.config["rgb"].get("openrgb_path", ""))
    lines.append(f"  OpenRGB: {orgb or 'NICHT installiert'}")
    try:
        client = OpenRGB(port=int(controller.config["rgb"].get("port", 6742)), timeout=1.5)
        devices = client.connect()
        lines.append(f"  OpenRGB-SDK-Server: verbunden, {len(devices)} Geräte: " + ", ".join(d.name for d in devices))
        client.close()
    except RGBError as exc:
        lines.append(f"  OpenRGB-SDK-Server: {exc}")
    chips = fans.read_sensors()
    lines.append(f"  Sensoren: {len(chips)} Chips, {sum(len(c.temps) for c in chips)} Temperaturen, "
                 f"{sum(len(c.fans) for c in chips)} Lüfter, {sum(len(c.pwms) for c in chips)} steuerbar"
                 + ("" if sys.platform.startswith("linux") else " (unter Windows nicht möglich)"))

    recent = getattr(controller, "recent_messages", [])
    if recent:
        lines.append("")
        lines.append("== Letzte Meldungen ==")
        lines += [f"  {m}" for m in recent[-10:]]
    tools = [t for t in ("kscreen-doctor", "xrandr", "wmctrl", "pkexec", "apt-get", "winget") if shutil.which(t)]
    lines.append("")
    lines.append("Werkzeuge vorhanden: " + (", ".join(tools) or "–"))
    return "\n".join(lines)
