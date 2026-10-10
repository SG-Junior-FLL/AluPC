"""Rundgang durch AluPC: öffnet jede Seite, jeden Setup-Bereich, die Fenster und die Anzeigen auf Monitor 2,
löst dabei die Kernfunktionen aus und macht von allem ein Bildschirmfoto.

    python tools/screens_tour.py <Ausgabeordner> [hell|dunkel]

Schreibt <Ausgabeordner>/screens.json (Titel, Bereich, Funktion, Datei, Fehler) und die PNG-Bilder. Läuft ohne
Bildschirm (Qt „offscreen“ mit zwei virtuellen Monitoren). Fehler (Ausnahmen, Qt-Warnungen) landen in
screens.json → „errors“ – der Rundgang bricht dabei nicht ab.
"""

from __future__ import annotations

import json
import os
import random
import sys
import tempfile
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "screens").resolve()
MODE = sys.argv[2] if len(sys.argv) > 2 else "dunkel"
OUT.mkdir(parents=True, exist_ok=True)
TMP = Path(tempfile.mkdtemp(prefix="alupc-tour-"))
os.environ["QT_QPA_PLATFORM"] = f"offscreen:configfile={ROOT / 'tests' / 'offscreen_two_screens.json'}"
os.environ["XDG_CONFIG_HOME"] = str(TMP / "cfg")
os.environ["APPDATA"] = str(TMP / "cfg")
os.environ["ALUPC_NO_AUTO_WIFI"] = "1"
os.environ["ALUPC_NO_ANIMATION"] = "1"
if hasattr(os, "geteuid") and os.geteuid() == 0:
    os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")

from PySide6 import QtWebEngineWidgets  # noqa: E402,F401
from PySide6.QtCore import QCoreApplication, Qt, QtMsgType, qInstallMessageHandler  # noqa: E402

QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
from PySide6.QtWidgets import QApplication, QDialog, QWidget  # noqa: E402

app = QApplication([])
from alupc.ui import theme  # noqa: E402

theme.apply(app, MODE, "alupc")

screens: list[dict] = []
errors: list[str] = []


def on_qt_message(kind, _ctx, msg):
    if (kind in (QtMsgType.QtCriticalMsg, QtMsgType.QtFatalMsg) or "Traceback" in msg) and "speechd" not in msg:
        errors.append(f"Qt: {msg}")


qInstallMessageHandler(on_qt_message)
_old_hook = sys.excepthook


def hook(t, v, tb):
    text = "".join(traceback.format_exception(t, v, tb))
    errors.append(text[-1500:])
    print(text, file=sys.stderr)


sys.excepthook = hook


def pump(seconds: float = 0.4) -> None:
    end = time.time() + seconds
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def visible_texts(widget) -> list[str]:
    """Alle sichtbaren Beschriftungen (für den Vergleich Linux ↔ Windows)."""
    from PySide6.QtWidgets import QAbstractButton, QComboBox, QGroupBox, QLabel, QLineEdit

    out = []
    for w in [widget, *widget.findChildren(QWidget)]:
        try:
            if not w.isVisibleTo(widget) and w is not widget:
                continue
            if isinstance(w, QLabel):
                t = w.text()
            elif isinstance(w, QAbstractButton):
                t = w.text()
            elif isinstance(w, QGroupBox):
                t = w.title()
            elif isinstance(w, QLineEdit):
                t = w.placeholderText()
            elif isinstance(w, QComboBox):
                t = w.currentText()
            else:
                continue
        except RuntimeError:
            continue
        t = " ".join(str(t).split())
        if t and len(t) < 400:
            out.append(t)
    return sorted(set(out))


def save(widget, key: str, title: str, area: str, text: str) -> None:
    pump(0.35)
    path = OUT / f"{len(screens) + 1:02d}-{key}.png"
    widget.grab().save(str(path))
    try:
        texts = visible_texts(widget)
    except Exception:  # noqa: BLE001 - nur für den Vergleich
        texts = []
    screens.append({"key": key, "title": title, "area": area, "text": text, "file": path.name, "ui_text": texts})
    print(f"  ✓ {title}")


def step(fn, label: str) -> None:
    try:
        fn()
    except Exception:  # noqa: BLE001 - Rundgang läuft weiter, Fehler wird gemeldet
        errors.append(f"{label}: {traceback.format_exc()[-1500:]}")
        print(f"  ✗ {label}")


# ---- modale Fenster abfangen: zeigen, fotografieren, schließen
pending: list[tuple[str, str, str, str]] = []


def fake_exec(self):
    self.show()
    pump(0.5)
    if pending:
        key, title, area, text = pending.pop(0)
        save(self, key, title, area, text)
    self.reject()
    return 0


QDialog.exec = fake_exec
QDialog.exec_ = fake_exec


def dialog(key, title, area, text, opener) -> None:
    pending.append((key, title, area, text))

    def run():
        opener()
        pump(0.3)
        if pending and pending[0][0] == key:  # nicht modal geöffnet → oberstes Fenster nehmen
            pending.pop(0)
            win = next((w for w in reversed(QApplication.topLevelWidgets())
                        if w.isVisible() and w is not window and w.windowTitle()), None)
            if win is not None:
                save(win, key, title, area, text)
                win.close()
    step(run, title)


# ---- App mit Beispiel-Daten
from alupc.config import Config  # noqa: E402
from alupc.controller import Controller  # noqa: E402
from alupc.hotkeys import HotkeyManager  # noqa: E402
from alupc.ui.main_window import MainWindow  # noqa: E402

config = Config(TMP / "cfg" / "AluPC" / "config.json")
config["handy"] = {**config["handy"], "setup_done": True}
config["first_run_done"] = True
config["cast"] = {**config["cast"], "port": 18760 + random.randint(0, 200), "code": "482913"}
config.put_scene({"name": "Begrüßung", "layout": "vollbild", "background": "#000000",
                  "slots": [{"type": "design", "design": "willkommen"}]})
config.put_scene({"name": "Kamera + Uhr", "layout": "ecke_unten_rechts", "background": "#000000",
                  "slots": [{"type": "clock"}, {"type": "design", "design": "neon"}]})
config["wheel"] = {**config["wheel"], "names": ["Lena", "Noah", "Mia", "Ben", "Emma", "Paul"]}
controller = Controller(config)
controller.display.available = lambda: False
window = MainWindow(controller, HotkeyManager())
window.resize(1440, 900)
window.show()
pump(1.0)
out = controller.output


def monitor2(key, title, text):
    pump(0.6)
    widget = out.content if getattr(out, "content", None) is not None else out
    save(widget, key, title, "Monitor 2", text)


print("App")
save(window, "start", "Startseite", "App",
     "Kacheln antippen – läuft sofort auf Monitor 2. Oben: was Monitor 2 gerade zeigt (Vorschau, Sichtschutz, "
     "Standbild, Bild-in-Bild, Zeichnen). Pfeil an einer Kachel = mehr Möglichkeiten.")
step(lambda: (window._go(1), save(window, "szenen", "Szenen", "App",
                                  "Eigene Szenen: mehrere Quellen (Kamera, Bild, Text, Uhr …) auf Monitor 2 – anlegen "
                                  "aus Vorlagen, bearbeiten, mit einem Klick zeigen.")), "Szenen")
step(lambda: (window._go(4), save(window, "system", "System – PC steuern", "App",
                                  "Live-Status (Prozessor, Speicher, Grafik, Temperaturen, Laufwerke, Netzwerk). "
                                  "„PC steuern“: Lautstärke, Musik, Fenster, Bildschirmfoto, Programm öffnen (wie "
                                  "Win+R). Sperren, Energie sparen, Neustart, Herunterfahren, RGB.")), "System")
step(lambda: (window._go(3), save(window, "fingerabdruck", "Fingerabdruck", "App",
                                  "ZW101-Fingerabdruckmodul: Personen und Finger anlernen, Windows-/Linux-Anmeldung "
                                  "mit dem Finger, Finger als Schnelltaste.")), "Fingerabdruck")
setup_texts = {
    "Monitore": "Auflösung, Anordnung, Drehung und Helligkeit der Monitore; Monitor 2 auswählen.",
    "Monitor 2": "Mauszeiger, Sichtschutz, Bild-in-Bild und was beim Start auf Monitor 2 läuft.",
    "Darstellung": "Hell/Dunkel/wie das System, Akzentfarbe (auch die von Windows/KDE), Übergänge, Leistung.",
    "Bildschirmschoner": "Stil und Wartezeit des Bildschirmschoners auf Monitor 2.",
    "Timer": "Countdown/Stoppuhr: Dauer, Warnfarben, Text am Ende.",
    "Töne": "Töne bei Aktionen, Lautstärke, Ausgabegerät.",
    "Tastenkürzel": "Jede Funktion auf eine Taste – auch global, wenn AluPC im Hintergrund ist.",
    "Sprache": "Sprachbefehle mit Startwort („Alu PC“, „Computer“), Stimme, eigene Befehle, Test.",
    "Sichern & Sync": "Dual-Boot-Abgleich Windows ↔ Linux (Status, Bereiche, Prüfen, Verlauf, Sicherungen) und "
                      "Einstellungen exportieren/importieren.",
    "RGB & Lüfter": "RGB-Beleuchtung über OpenRGB, Temperaturen und Lüfter.",
    "Handy & Kamera": "Was das Handy darf, freigegebene Geräte, Kamera-Einstellungen.",
    "Allgemein": "Start, Autostart, Hilfe, Fehlerbericht und „Alle Daten löschen“.",
}
config.data["sync"] = {**config.data["sync"], "enabled": True, "folder": str(TMP / "C" / "AluPC-Sync")}
(TMP / "C" / "AluPC-Sync").mkdir(parents=True)
step(lambda: controller.run_sync(), "Sync")
for name, text in setup_texts.items():
    def show_section(n=name, t=text):
        window.open_setup_section(n)
        slug = n.lower().replace(" ", "-").replace("&", "und")
        for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
            slug = slug.replace(a, b)
        save(window, "setup-" + slug, f"Setup – {n}", "App", t)
    step(show_section, f"Setup {name}")

print("Fenster")
window._go(0)
pump()
dialog("befehlssuche", "Befehlssuche (Strg+K)", "Fenster",
       "Tippen, was passieren soll („Licht blau“, „Timer 5 Minuten“, „Szene Pause“) oder Funktionen suchen.",
       window.open_command_palette)
dialog("startseite-anpassen", "Startseite anpassen", "Fenster",
       "Kacheln ein-/ausblenden, sortieren, eigene Kacheln anlegen (Szene, Website, Programm, Ausführen wie Win+R …).",
       window.customize_start)
dialog("neue-szene", "Neue Szene – Vorlagen", "Fenster",
       "Leer oder aus Vorlagen (Design-Karten, Szenen-Vorlagen) mit Kategorien und Suche.", window.new_scene)


def edit_first_scene():
    window._go(1)
    pump()
    buttons = window.scene_group.buttons() if hasattr(window, "scene_group") else []
    if buttons:
        buttons[0].setChecked(True)
    window.edit_scene()


dialog("szenen-editor", "Szenen-Editor", "Fenster",
       "Quellen einer Szene anordnen (Größe, Lage, Ebenen), Texte und Farben ändern, Vorschau.", edit_first_scene)
window._go(0)
dialog("text", "Text zeigen", "Fenster", "Schnell einen Text groß auf Monitor 2 zeigen.", window.open_text_dialog)
dialog("timer", "Timer einstellen", "Fenster", "Countdown oder Stoppuhr mit Warnfarben.", window.edit_timer)
dialog("abstimmung", "Abstimmung", "Fenster", "Frage und Antworten – abgestimmt wird per Handy (QR-Code).",
       window.open_poll_dialog)
dialog("gluecksrad", "Glücksrad", "Fenster", "Namen eintragen und auf Monitor 2 drehen.", window.open_wheel_dialog)
dialog("overlays", "Overlays", "Fenster", "Einblendungen über Monitor 2 (Uhr, Logo, Laufschrift …), frei verschiebbar.",
       window.open_overlays)
dialog("mediathek", "Mediathek", "Fenster", "Bilder und Videos sammeln und mit einem Klick zeigen.",
       window.open_media_library)
dialog("programm", "Programm zeigen", "Fenster", "Ein Programmfenster auf Monitor 2 zeigen.",
       window.open_program_dialog)
dialog("hotspot", "Hotspot", "Fenster",
       "Der PC macht ein eigenes WLAN – der einzige Weg fürs Handy. Handys bekommen die Anmeldeseite: Mitspielen "
       "oder AluPC steuern.", lambda: window.open_hotspot_dialog("normal"))
def fake_wlan(on: bool):  # kein echtes WLAN im Rundgang: so tun, als liefe das AluPC-WLAN
    from alupc import hotspot as hs_mod

    hs = hs_mod.hotspot
    hs.running, hs.kind, hs.ssid, hs.password, hs.hidden = on, "normal", "AluPC", "k7pm2qa9xr", False


def connect_dialog():
    from alupc.ui.connect_dialog import ConnectDialog

    controller.cast.start()
    fake_wlan(True)
    ConnectDialog("Handy verbinden", controller.guest_wifi(),
                  "WLAN-Code scannen → Anmeldeseite → „AluPC steuern“ → am PC erlauben",
                  on_monitor=lambda: None, parent=window).exec()
    fake_wlan(False)


dialog("handy-verbinden", "Handy verbinden", "Fenster",
       "EIN QR-Code: das AluPC-WLAN. Scannen → die Anmeldeseite öffnet sich → „AluPC steuern“ (am PC erlauben) "
       "oder mitspielen. Einen anderen Weg gibt es nicht.", connect_dialog)
dialog("handy-fenster", "Handy auf Monitor 2", "Fenster",
       "AirPlay (iPhone), Miracast/Spiegeln (Android), AluCast im Browser – Status und Einrichtung.",
       window.open_handy_window)
dialog("ersteinrichtung", "Ersteinrichtung", "Fenster", "Beim ersten Start: Monitore, Handy, Autostart – geführt.",
       window.open_first_run)


def reset_dialog():
    from alupc.ui.reset_page import ResetDialog

    ResetDialog(True, False, window, sync_on=True).exec()


dialog("zuruecksetzen", "Alle Daten löschen", "Fenster",
       "AluPC wie frisch installiert – mit Sicherung vorher, auf Wunsch Szenen/Startseite behalten und den "
       "Dual-Boot-Abgleich mit zurücksetzen.", reset_dialog)


def bug_dialog():
    from alupc.ui.bug_report_dialog import BugReportDialog

    BugReportDialog(controller, window).exec()


dialog("fehlerbericht", "Fehlerbericht", "Fenster", "Diagnose und Protokolle mit einem Klick als Datei speichern.",
       bug_dialog)

print("Monitor 2")
step(lambda: (controller.show_source({"type": "clock"}), monitor2("uhr", "Uhr", "Große Uhr mit Datum.")), "Uhr")
step(lambda: (controller.show_source({"type": "system"}),
              monitor2("system-m2", "System-Dashboard", "Live-Werte des PCs groß auf Monitor 2.")), "System M2")
def wlan_qr():
    fake_wlan(True)
    controller.start_cast()  # Handy-Steuerung = WLAN-Code des AluPC-WLANs
    pump(1.2)
    monitor2("wlan-qr", "Handy-Steuerung: WLAN-QR-Code",
             "Der einzige Weg fürs Handy: WLAN-Code scannen → die Anmeldeseite öffnet sich → mitspielen oder "
             "„AluPC steuern“ (am PC erlauben).")
    fake_wlan(False)


step(wlan_qr, "WLAN-QR")
step(lambda: (controller.show_source({"type": "text", "text": "Gleich geht's los!", "size": 12}),
              monitor2("text-m2", "Text", "Schnelltext groß auf Monitor 2.")), "Text M2")
step(lambda: (controller.run_command("timer_zeigen"), controller.run_command("timer_start_pause"),
              monitor2("timer-m2", "Timer", "Countdown mit Warnfarben.")), "Timer M2")
step(lambda: (controller.show_whiteboard(), monitor2("whiteboard", "Whiteboard",
                                                     "Zeichnen auf Monitor 2 – am PC oder vom Handy.")), "Whiteboard")
step(lambda: (controller.start_poll("Pizza oder Pasta?", ["Pizza", "Pasta", "Beides"]),
              monitor2("abstimmung-m2", "Abstimmung", "Live-Ergebnis, Handys stimmen per QR-Code ab.")), "Umfrage")
step(lambda: (controller.show_wheel(), monitor2("gluecksrad-m2", "Glücksrad", "Dreht auf Klick, zeigt den Gewinner.")),
     "Rad")
step(lambda: (controller.show_now_playing(), monitor2("musik", "Läuft gerade",
                                                      "Titel, Künstler und Cover der Musik am PC.")), "Musik")
for design, title in (("willkommen", "Design-Seite: Willkommen"), ("neon", "Design-Seite: Neon"),
                      ("ablauf", "Design-Seite: Ablauf")):
    step(lambda d=design, t=title: (controller.show_source({"type": "design", "design": d}),
                                    monitor2(f"design-{d}", t, "Eine von 32 gestalteten Karten – Text eintragen, "
                                                               "fertig.")), title)

print("Minispiele")


def games():
    from alupc.games import GAMES

    window.open_games_window()
    pump(0.6)
    hub = controller.cast.games
    players = [hub.join(n, a) for n, a in (("Lena", "🦊"), ("Noah", "🐼"), ("Mia", "🐸"), ("Ben", "🦁"))]
    save(window.games_window, "spiele-fenster", "Minispiele – Steuerfenster", "Fenster",
         "Spiel wählen (1–7), Einstellungen, Spieler, Teams; Start/Weiter/Ergebnis per Taste. Zeigt, ob das "
         "Spiele-WLAN läuft.")
    monitor2("spiele-lobby", "Minispiele – Lobby", "Wer dabei ist, QR-Code zum Mitmachen, Bestenliste des Abends.")
    for key in GAMES:
        controller.start_games(key)
        controller.game_action("start")
        hub.intro_until = hub.clock()
        for _ in range(40):
            hub.tick()
            pump(0.03)
        g = hub.game
        if key == "tictactoe":
            g.cells = ["X", "O", "", "", "X", "", "O", "", ""]
            for p in players:
                if g.team_of(p.pid) == g.turn:
                    g.votes[p.pid] = 8
        if key == "tetris":  # ein paar Teile stapeln, einer ist schon raus
            moves = [["left"] * 4, ["right"] * 3, [], ["rotate", "left", "left"], ["right"] * 5, ["rotate"]]
            for k, p in enumerate(players):
                for j in range(30 if k == 3 else 5 + k * 2):
                    for m in moves[(j + k) % len(moves)]:
                        g.input(p.pid, {"move": m}, hub.clock())
                    g.input(p.pid, {"move": "drop"}, hub.clock())
            hub.tick()
        monitor2(f"spiel-{key}", f"Spiel: {GAMES[key].title}", GAMES[key].help)
        controller.game_action("ende")
        pump(0.3)
    monitor2("spiele-ergebnis", "Minispiele – Siegertreppchen", "Platz 1–3 mit Animation, danach nächstes Spiel.")
    return players


game_players = []
step(lambda: game_players.extend(games()), "Minispiele")


def phone_lobby():  # für die Handy-Bilder: Tic-Tac-Toe in der Lobby
    hub = controller.cast.games
    hub.to_lobby()
    hub.set_game("tictactoe")


step(phone_lobby, "Lobby fürs Handy")

print("Handy (Browser)")
phone_urls = {"base": controller.cast.base() if controller.cast.running() else "",
              "code": config["cast"].get("code", ""),
              "game": controller.cast.games_url() if controller.cast.games else ""}
(OUT / "phone.json").write_text(json.dumps(phone_urls), encoding="utf-8")

(OUT / "screens.json").write_text(json.dumps({"mode": MODE, "screens": screens, "errors": errors}, indent=1,
                                             ensure_ascii=False), encoding="utf-8")
print(f"{len(screens)} Bilder, {len(errors)} Fehler")
for e in errors:
    print("FEHLER:", e[:600])
if os.environ.get("ALUPC_TOUR_KEEP_SERVER"):  # für Handy-Bilder: Server weiterlaufen lassen
    print("SERVER", phone_urls["base"], flush=True)
    end = time.time() + float(os.environ["ALUPC_TOUR_KEEP_SERVER"])
    started = False
    while time.time() < end:
        app.processEvents()
        time.sleep(0.02)
        hub = controller.cast.games
        if not started and hub is not None and any(p.name == "Sophie" for p in hub.players.values()):
            # Handy ist beigetreten → Spiel starten (Tic-Tac-Toe-Feld auf dem Handy)
            started = True
            controller.game_action("start")
            hub.intro_until = hub.clock()
controller.shutdown()
sys.exit(1 if errors else 0)
