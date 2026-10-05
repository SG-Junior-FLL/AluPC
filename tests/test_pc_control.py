"""PC steuern: Sätze → Befehle, Lautstärke/Programme (nachgespielt), Herunterfahren nur nach „Ja“."""

import sys

import pytest
from test_gui import env  # noqa: F401

from alupc import pc_control
from alupc.intents import understand
from alupc.voice import fold


def u(text):
    return understand(fold(text).split(), [], [])


@pytest.mark.parametrize("text, command", [
    ("öffne Firefox", "pc_app:firefox"), ("starte Spotify", "pc_app:spotify"), ("öffne YouTube", "pc_web:youtube"),
    ("öffne wikipedia", "pc_web:wikipedia"), ("geh auf heise.de", "pc_web:heise.de"),
    ("mach lauter", "pc_lauter"), ("leiser bitte", "pc_leiser"), ("Lautstärke auf dreißig", "pc_lautstaerke:30"),
    ("Lautstärke auf 75 Prozent", "pc_lautstaerke:75"), ("stumm", "pc_stumm_an"), ("Ton an", "pc_stumm_aus"),
    ("wie laut ist es", "pc_lautstaerke_frage"), ("Fenster schließen", "pc_fenster_zu"),
    ("Fenster minimieren", "pc_minimieren"), ("zeig den Desktop", "pc_desktop"),
    ("mach einen Screenshot", "pc_screenshot"), ("suche nach Pizza Rezept", "pc_suche:pizza rezept"),
    ("spiel Queen auf YouTube", "pc_youtube:queen"), ("fahr den Computer herunter", "pc_herunterfahren"),
    ("schalte den PC aus", "pc_herunterfahren"), ("starte den PC neu", "pc_neustart"),
    ("Ruhezustand", "pc_schlafen"), ("ja", "bestaetigen"), ("nein", "abbrechen"),
])
def test_pc_sentences(text, command):
    assert u(text)[0] == command


@pytest.mark.parametrize("text, command", [  # AluPC-eigene Dinge bleiben AluPC
    ("öffne die Kamera", "kamera"), ("starte den Timer", "timer_start"), ("öffne das Whiteboard", "whiteboard"),
    ("spiel Pong", "spiel:pong"), ("Licht aus", "rgb_aus"), ("Computer sperren", "sperren"),
    ("mach den Bildschirm schwarz", "schwarz_an"), ("nächstes Lied", "musik_weiter"),
])
def test_alupc_things_stay_alupc(text, command):
    assert u(text)[0] == command


def test_volume_linux_commands(monkeypatch):
    if not sys.platform.startswith("linux"):
        pytest.skip("Linux")
    calls = []
    monkeypatch.setattr(pc_control.shutil, "which", lambda n: "/usr/bin/" + n if n == "wpctl" else None)

    def run(cmd, timeout=8):
        calls.append(cmd)
        return (0, "Volume: 0.42") if cmd[1] == "get-volume" else (0, "")

    monkeypatch.setattr(pc_control, "_run", run)
    assert pc_control.run("pc_lautstaerke:30") == "Lautstärke 30 Prozent."
    assert ["wpctl", "set-volume", "-l", "1.0", "@DEFAULT_AUDIO_SINK@", "0.30"] in calls
    assert pc_control.run("pc_lauter") == "Lauter – jetzt 42 Prozent."
    assert ["wpctl", "set-volume", "-l", "1.0", "@DEFAULT_AUDIO_SINK@", "0.10+"] in calls
    assert pc_control.run("pc_stumm_an") == "Stumm."
    assert ["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "1"] in calls


def test_find_app_and_unknown(monkeypatch, tmp_path):
    entries = {"firefox webbrowser": "/a/firefox.desktop", "spotify": "/a/spotify.desktop",
               "visual studio code": "/a/code.desktop"}
    assert pc_control.find_app("Firefox", entries) == "/a/firefox.desktop"
    assert pc_control.find_app("spotifi", entries) == "/a/spotify.desktop"
    assert pc_control.find_app("gibtsnicht", entries) is None
    monkeypatch.setattr(pc_control, "_desktop_entries", lambda: {})
    monkeypatch.setattr(pc_control, "_start_menu", lambda: {})
    monkeypatch.setattr(pc_control.shutil, "which", lambda n: None)
    if sys.platform.startswith("linux"):
        assert pc_control.run("pc_app:gibtsnicht") == "Das ging nicht: „gibtsnicht“ nicht gefunden."


def test_shutdown_needs_yes(env, monkeypatch):  # noqa: F811
    controller, _window, _ = env
    done = []
    monkeypatch.setattr(pc_control, "power", lambda cmd: (done.append(cmd) or True, ""))
    a = controller.assistant
    reply = a.handle("pc_herunterfahren", "PC herunterfahren", voice=False)
    assert "wirklich herunterfahren" in reply and done == []
    assert a.handle("abbrechen", "Nein", voice=False) == "Okay, abgebrochen." and done == []
    assert a.handle("bestaetigen", "Ja", voice=False) == "Es gibt gerade nichts zu bestätigen."
    a.handle("pc_neustart", "PC neu starten", voice=False)
    # Sprache: nur „ja“ im Nachfrage-Fenster genügt
    hit, _empty = controller.voice._interpret(["ja"], None)
    assert hit == ("bestaetigen", "Ja")
    assert "neu starten" in a.handle("bestaetigen", "Ja", voice=False) and done == ["pc_neustart"]
    hit, empty = controller.voice._interpret(["ja"], None)
    assert hit is None and empty  # danach ist „ja“ wieder nur ein Füllwort
    # vom Handy: Ein/Aus geht nicht
    assert "nur direkt am PC" in controller.ask("PC herunterfahren", source="handy")["reply"]


def test_screenshot_saves_file(env, tmp_path, monkeypatch):  # noqa: F811
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    ok, path = pc_control.screenshot(tmp_path)
    assert ok and path.endswith(".png") and (tmp_path / path.split("/")[-1]).exists()
