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


def test_run_line_like_win_r(monkeypatch, tmp_path):
    if not sys.platform.startswith("linux"):
        pytest.skip("Linux-Pfad")
    spawned = []
    monkeypatch.setattr(pc_control, "_spawn", lambda cmd: spawned.append(cmd) or True)
    monkeypatch.setattr(pc_control.shutil, "which", lambda n: f"/usr/bin/{n}" if n in ("xdg-open", "kate") else None)
    assert pc_control.run_line("https://example.org") == (True, "")
    assert spawned[-1] == ["xdg-open", "https://example.org"]
    assert pc_control.run_line("ms-settings:")[0] and spawned[-1] == ["xdg-open", "ms-settings:"]
    f = tmp_path / "liste.txt"
    f.write_text("x")
    pc_control.run_line(str(f))
    assert spawned[-1] == ["xdg-open", str(f)]
    pc_control.run_line("kate ~/notiz.txt")  # Programm mit Argument, ~ aufgelöst
    assert spawned[-1][0] == "kate" and spawned[-1][1].endswith("/notiz.txt") and "~" not in spawned[-1][1]
    pc_control.run_line("echo hallo | tee /tmp/x")  # Shell
    assert spawned[-1][:2] == ["sh", "-c"]
    assert pc_control.run_line("   ") == (False, "kein Befehl eingetragen")


def test_run_tile_uses_command_for_this_system(env, monkeypatch):  # noqa: F811
    controller, _window, _ = env
    ran, msgs = [], []
    monkeypatch.setattr(pc_control, "run_line", lambda line: (ran.append(line) or True, ""))
    controller.message.connect(msgs.append)
    tile = {"id": "t1", "title": "Notizen", "action": {"kind": "run", "command": "editor", "windows": "notepad",
                                                       "linux": ""}}
    controller.config["start_page"] = {**controller.config["start_page"], "custom": [tile]}
    controller.run_tile("t1")
    assert ran == ["notepad" if sys.platform.startswith("win") else "editor"] and msgs[-1] == "▶ Notizen"
    from alupc.startpage import describe_action

    assert describe_action(tile["action"]).startswith("Ausführen: ")


def test_wayland_keys_and_mouse_via_ydotool(monkeypatch):
    if not sys.platform.startswith("linux"):
        pytest.skip("Linux")
    import subprocess

    from alupc.platform import keys

    calls = []
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
    monkeypatch.setattr("shutil.which", lambda n: "/usr/bin/ydotool" if n == "ydotool" else None)
    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: calls.append(cmd) or
                        subprocess.CompletedProcess(cmd, 0, b"", b""))
    assert keys.available() and keys.send("weiter")
    assert calls[-1] == ["/usr/bin/ydotool", "key", "109:1", "109:0"]  # Bild ab
    assert keys.combo("F4", ("Alt_L",))
    assert calls[-1] == ["/usr/bin/ydotool", "key", "56:1", "62:1", "62:0", "56:0"]  # Alt+F4
    assert keys.click("rechts") and calls[-1] == ["/usr/bin/ydotool", "click", "0xC1"]
    assert keys.scroll(-3) and calls[-1][-1] == "-3"
    assert keys.move(5, -2) and calls[-1] == ["/usr/bin/ydotool", "mousemove", "-x", "5", "-y", "-2"]
    monkeypatch.setattr("shutil.which", lambda n: None)
    assert not keys.available()  # ohne ydotool ehrlich „geht nicht“


def test_installed_apps_and_program_tiles(monkeypatch, tmp_path):
    if not sys.platform.startswith("linux"):
        pytest.skip("Linux-.desktop")
    apps = tmp_path / "share" / "applications"
    apps.mkdir(parents=True)
    (apps / "org.kde.kate.desktop").write_text("[Desktop Entry]\nType=Application\nName=Kate\nName[de]=Kate Editor\n"
                                               "Exec=kate %U\n")
    (apps / "hidden.desktop").write_text("[Desktop Entry]\nType=Application\nName=Versteckt\nNoDisplay=true\n")
    monkeypatch.setenv("XDG_DATA_DIRS", str(tmp_path / "share"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "leer"))
    found = pc_control.installed_apps()
    assert [n for n, _ in found] == ["Kate Editor"] and found[0][1].endswith("org.kde.kate.desktop")
    spawned = []
    monkeypatch.setattr(pc_control, "_spawn", lambda cmd: spawned.append(cmd) or True)
    monkeypatch.setattr(pc_control.shutil, "which", lambda n: "/usr/bin/" + n if n == "gtk-launch" else None)
    assert pc_control.run_line(found[0][1]) == (True, "") and spawned[-1] == ["gtk-launch", "org.kde.kate"]
    from alupc.startpage import custom_key, ordered_keys, section_of, sections
    from alupc.ui.start_page_dialog import add_programs

    cfg = {"custom": [], "tiles": None}
    tiles = add_programs(cfg, found, windows=False)
    sec = next(s for s in sections(cfg) if s["name"] == "Programme")
    assert section_of(custom_key(tiles[0]), cfg) == sec["id"] and custom_key(tiles[0]) in ordered_keys(cfg)
    assert tiles[0]["action"] == {"kind": "run", "command": "", "windows": "", "linux": found[0][1]}
    add_programs(cfg, [("Zwei", "x")], windows=True)
    assert [s["name"] for s in sections(cfg)].count("Programme") == 1  # Bereich nur einmal


def test_hotspot_tile_on_start_page(env, monkeypatch):  # noqa: F811
    from alupc import hotspot

    controller, window, _ = env
    assert "hotspot" in window.tiles
    calls = []
    monkeypatch.setattr(controller, "set_hotspot", lambda on, kind="normal": calls.append((on, kind)) or (True, ""))
    window.toggle_hotspot()
    from PySide6.QtCore import QThreadPool

    QThreadPool.globalInstance().waitForDone(3000)
    assert calls == [(True, "normal")]
    hs = hotspot.hotspot
    try:
        hs.running, hs.kind = True, "normal"
        window.refresh()
        assert window.t_hotspot.badge == "AN" and window.t_hotspot.active
    finally:
        hs.running, hs.kind = False, ""
