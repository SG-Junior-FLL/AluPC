"""Oberflächen-Test mit zwei virtuellen Monitoren (Qt „offscreen“), ohne echte Hardware."""

import os
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent


def _qpa_path(path: Path) -> str:
    """Pfad ohne Doppelpunkt: Qt trennt Plattform-Optionen am „:“ (Windows: „D:\\…“)."""
    try:
        rel = os.path.relpath(path)
    except ValueError:  # anderes Laufwerk
        rel = str(path)
    rel = rel.replace("\\", "/")
    if ":" in rel:
        rel = rel.split(":", 1)[1]  # Laufwerksbuchstabe weg → gilt für das aktuelle Laufwerk
    return rel


os.environ["QT_QPA_PLATFORM"] = f"offscreen:configfile={_qpa_path(HERE / 'offscreen_two_screens.json')}"

pytest.importorskip("PySide6.QtWidgets")

from PySide6 import QtWebEngineWidgets  # noqa: E402,F401  (vor QApplication laden)
from PySide6.QtCore import QCoreApplication, Qt  # noqa: E402
from PySide6.QtGui import QColor, QImage  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
APP = QApplication.instance() or QApplication([])


def pump(n=5):
    for _ in range(n):
        APP.processEvents()


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    from alupc.config import Config
    from alupc.controller import Controller
    from alupc.hotkeys import HotkeyManager
    from alupc.ui.main_window import MainWindow
    from alupc.ui.pip_window import PipWindow

    config = Config(tmp_path / "config.json")
    config["handy"] = {**config["handy"], "setup_done": True}  # im Test nichts installieren
    controller = Controller(config)
    # Keine echten Monitor-Befehle im Test ausführen
    controller.display.available = lambda: False
    hotkeys = HotkeyManager()
    window = MainWindow(controller, hotkeys)
    hotkeys.attach(window)
    hotkeys.triggered.connect(controller.run_command)
    hotkeys.apply(config["hotkeys"])
    controller.pip = PipWindow(controller)
    window.show()
    pump()
    yield controller, window, tmp_path
    controller.pip.hide()
    controller.shutdown()
    window.tray.hide()
    window.deleteLater()
    pump()


def test_screens(env):
    controller, _window, _ = env
    assert controller.output_screen().name() == "Zweit"
    assert controller.main_screen().name() == "Haupt"
    assert not controller.screens_overlap()


def test_simple_sources_and_freeze(env, tmp_path):
    controller, window, _ = env
    img = QImage(64, 36, QImage.Format_RGB32)
    img.fill(QColor("#ff0000"))
    img_path = str(tmp_path / "rot.png")
    img.save(img_path)
    for cfg in [
        {"type": "text", "text": "Hallo"},
        {"type": "clock"},
        {"type": "countdown", "minutes": 1},
        {"type": "color", "color": "#00ff00"},
        {"type": "image", "path": img_path},
        {"type": "slideshow", "folder": str(tmp_path)},
    ]:
        controller.show_source(cfg)
        pump()
        assert controller.mode == "content"
        assert controller.output.isVisible()
        assert controller.output.geometry().topLeft().x() == 1920  # auf Monitor 2

    controller.show_source({"type": "color", "color": "#00ff00"})
    pump()
    controller.toggle_freeze()
    assert controller.frozen and controller.output.freeze_layer.isVisible()
    frozen = controller.output.freeze_layer.image()
    assert frozen is not None and QColor(frozen.pixel(10, 10)) == QColor("#00ff00")
    # Inhalt wechselt → Standbild bleibt bis zum Ausschalten nicht hängen
    controller.toggle_freeze()
    assert not controller.frozen and not controller.output.freeze_layer.isVisible()
    assert "Farbe" in window.status_card.title.text()


def test_privacy_and_pip(env):
    controller, window, _ = env
    controller.show_source({"type": "text", "text": "Geheim"})
    controller.toggle_privacy()
    pump()
    assert controller.privacy and controller.output.privacy_layer.isVisible()
    assert "SCHWARZ" in window.status_card.pill_texts()
    controller.toggle_pip()
    pump()
    assert controller.pip.isVisible()
    controller.pip.refresh()
    assert controller.pip.view.image() is not None
    controller.toggle_privacy()
    controller.toggle_pip()
    assert not controller.pip.isVisible()


def test_extend_hides_output(env):
    controller, _window, _ = env
    controller.show_source({"type": "text", "text": "x"})
    controller.extend()
    pump()
    assert controller.mode == "desktop"
    assert not controller.output.isVisible()


def test_scene_with_nested_scene(env):
    controller, _window, _ = env
    cfg = controller.config
    cfg.put_scene({"name": "Innen", "layout": "nebeneinander", "background": "#000000",
                   "slots": [{"type": "text", "text": "L"}, {"type": "clock"}]})
    cfg.put_scene({"name": "Außen", "layout": "ecke_unten_rechts", "background": "#101010",
                   "slots": [{"type": "color", "color": "#0000ff"}, {"type": "scene", "scene": "Innen"}]})
    controller.run_command("szene:Außen")
    pump()
    content = controller.output.content
    assert type(content).__name__ == "SceneSource"
    assert len(content.children_sources) == 2
    inner = content.children_sources[1][1]
    assert type(inner).__name__ == "SceneSource"
    # Kleines Feld unten rechts: 26 % von 1280 px Breite
    assert abs(inner.width() - round(0.26 * 1280)) <= 1


def test_scene_cycle_is_limited(env):
    controller, _window, _ = env
    cfg = controller.config
    cfg.put_scene({"name": "A", "layout": "vollbild", "slots": [{"type": "scene", "scene": "A"}]})
    controller.show_source({"type": "scene", "scene": "A"})  # darf nicht endlos rekursiv werden
    pump()
    assert controller.output.content is not None


def test_missing_things_do_not_crash(env):
    controller, _window, _ = env
    for cfg in [
        {"type": "image", "path": "/gibt/es/nicht.png"},
        {"type": "camera", "device_id": "nicht-da", "name": "Weg"},
        {"type": "scene", "scene": "Unbekannt"},
        {"type": "unsinn"},
    ]:
        controller.show_source(cfg)
        pump()
        assert controller.output.content is not None


def test_commands_and_computer_lock(env, monkeypatch):
    controller, _window, _ = env
    controller.run_command("standbild")
    pump()
    assert controller.frozen
    calls = []
    import alupc.platform.window_tools as wt

    monkeypatch.setattr(wt, "lock_computer", lambda: calls.append(1))
    controller.run_command("sperren")
    assert calls == [1]  # „Sperren“ sperrt jetzt den Computer (wie Win+L)
    controller.run_command("schwarz")
    assert controller.privacy  # AluPC selbst bleibt bedienbar
    controller.run_command("schwarz")


def test_dialogs_build(env):
    controller, window, _ = env
    from alupc.ui.program_dialog import ProgramDialog
    from alupc.ui.scene_editor import SceneEditor
    from alupc.ui.source_picker import SOURCE_TYPES, SourcePicker

    picker = SourcePicker(controller.config, window)
    for key, _label in SOURCE_TYPES:
        picker.select_type(key)
        assert picker.current_type() == key
        picker.result_config()  # darf nicht abstürzen, auch wenn Felder leer sind
    picker.select_type("text")
    page = picker.stack.currentWidget()
    from PySide6.QtWidgets import QPlainTextEdit

    page.findChild(QPlainTextEdit).setPlainText("Willkommen")
    assert picker.result_config()["text"] == "Willkommen"

    editor = SceneEditor(controller.config, None, window)
    editor.layout_list.setCurrentRow(6)  # 2 × 2 Raster
    assert len(editor.scene["slots"]) == 4
    editor.scene["slots"][0] = {"type": "text", "text": "x"}
    editor._save()
    assert controller.config.get_scene(editor.scene["name"]) is not None

    ProgramDialog(controller, window)
    for i in range(window.stack.count()):
        window._go(i)
        pump()
    # Szenen-Seite zeigt eine Karte pro Szene
    window._reload_scenes()
    assert len(window.scene_cards) == len(controller.config["scenes"])


def test_theme_switch(env):
    controller, window, _ = env
    from alupc.ui import theme

    for mode, accent in (("hell", "violett"), ("dunkel", "gruen"), ("dunkel", "blau")):
        controller.config["appearance"] = {"mode": mode, "accent": accent, "fade": True}
        window.apply_theme()
        pump()
        assert theme.current().dark == (mode == "dunkel")
        assert theme.current().accent == theme.ACCENTS[accent][1]


def test_crossfade_layer_is_removed(env):
    controller, _window, _ = env
    controller.show_source({"type": "color", "color": "#ff0000"})
    pump()
    controller.show_source({"type": "color", "color": "#0000ff"})
    assert len(controller.output._fades) == 1
    import time

    end = time.time() + 2
    while controller.output._fades and time.time() < end:
        pump()
    assert controller.output._fades == []


def test_website_source(env):
    controller, _window, _ = env
    controller.show_source({"type": "website", "url": "about:blank"})
    pump()
    assert type(controller.output.content).__name__ == "WebsiteSource"


def test_screensaver_styles_and_layers(env, tmp_path):
    controller, window, _ = env
    img = QImage(40, 30, QImage.Format_RGB32)
    img.fill(QColor("#ff8800"))
    img.save(str(tmp_path / "a.png"))
    controller.config.put_scene({"name": "S", "layout": "vollbild", "slots": [{"type": "clock"}]})
    for style in ("uhr", "schweben", "diashow", "farben", "szene"):
        cfg = dict(controller.config["screensaver"])
        cfg.update({"style": style, "folder": str(tmp_path), "scene": "S", "text": "Hallo"})
        controller.config["screensaver"] = cfg
        controller.toggle_screensaver()
        pump()
        assert controller.screensaver.active
        assert controller.output.isVisible() and controller.output.screensaver is not None
        controller.output.screensaver.grab()  # Zeichnen darf nicht abstürzen
        controller.toggle_screensaver()
        pump()
        assert not controller.screensaver.active and controller.output.screensaver is None
    # Sichtschutz liegt immer über dem Bildschirmschoner
    controller.toggle_screensaver()
    controller.toggle_privacy()
    kids = controller.output.children()
    assert kids.index(controller.output.privacy_layer) > kids.index(controller.output.screensaver)
    controller.toggle_privacy()
    # Etwas anzeigen beendet den Bildschirmschoner
    controller.show_source({"type": "clock"})
    assert not controller.screensaver.active


def test_screensaver_auto_start_and_stop(env):
    controller, _window, _ = env
    saver = controller.screensaver
    controller.extend()
    controller.config["screensaver"] = {**controller.config["screensaver"], "enabled": True, "minutes": 1}
    saver.idle_seconds = lambda: 120  # niemand hat seit 2 Minuten etwas gemacht
    saver.check()
    assert saver.active and not saver.manual
    saver.idle_seconds = lambda: 0.5  # Maus bewegt
    saver.check()
    assert not saver.active
    # Modus „nur wenn nichts gezeigt wird“: bei laufendem Inhalt kein Start
    controller.show_source({"type": "clock"})
    saver.idle_seconds = lambda: 999
    saver.check()
    assert not saver.active


def test_custom_tile_and_scene_steps(env):
    controller, window, _ = env
    cfg = controller.config
    cfg.put_scene({"name": "Eins", "layout": "vollbild", "slots": [{"type": "clock"}]})
    cfg.put_scene({"name": "Zwei", "layout": "vollbild", "slots": [{"type": "text", "text": "2"}]})
    controller.run_command("naechste_szene")
    assert controller.content == {"type": "scene", "scene": "Eins"}
    controller.run_command("naechste_szene")
    assert controller.content["scene"] == "Zwei"
    controller.run_command("vorherige_szene")
    assert controller.content["scene"] == "Eins"

    start = dict(cfg["start_page"])
    start["custom"] = [
        {"id": "t1", "title": "Uhr", "icon": "clock", "color": "#10b981", "section": "anzeigen",
         "action": {"kind": "source", "source": {"type": "clock"}}},
        {"id": "t2", "title": "Freeze", "icon": "snowflake", "color": "#0ea5e9", "section": "schnell",
         "action": {"kind": "command", "command": "standbild"}},
    ]
    start["tiles"] = ["camera", "custom:t1", "freeze", "custom:t2"]
    from alupc.startpage import BUILTIN_TILES

    start["seen"] = list(BUILTIN_TILES)  # wie beim Speichern im Dialog: alle anderen bewusst ausgeblendet
    cfg["start_page"] = start
    window.rebuild_start()
    pump()
    assert window.section_grids["anzeigen"].items == [window.tiles["camera"], window.custom_tiles["custom:t1"]]
    assert window.section_grids["schnell"].items == [window.tiles["freeze"], window.custom_tiles["custom:t2"]]
    assert window.tiles["mirror"].isHidden()
    window.custom_tiles["custom:t1"].click()
    assert controller.content == {"type": "clock"}
    assert window.custom_tiles["custom:t1"].active
    controller.run_command("kachel:t2")
    assert controller.frozen
    controller.run_command("kachel:t2")
    assert not controller.frozen


def test_start_page_dialog_roundtrip(env):
    controller, window, _ = env
    from alupc.ui.start_page_dialog import StartPageDialog
    from PySide6.QtCore import Qt as _Qt

    dlg = StartPageDialog(controller.config, window)
    dlg.title.setText("Mein Start")
    dlg.list.item(0).setCheckState(_Qt.Unchecked)  # erste Kachel (Spiegeln) ausblenden
    dlg.list.setCurrentRow(1)
    dlg._move(-1)  # Erweitern nach oben
    dlg._save()
    start = controller.config["start_page"]
    assert start["title"] == "Mein Start"
    assert start["tiles"][0] == "extend" and "mirror" not in start["tiles"]
    window.rebuild_start()
    assert window.start_title.text() == "Mein Start"


def test_duplicate_hotkeys_are_reported(env):
    controller, window, _ = env
    problems = window.hotkeys.apply({"standbild": "Ctrl+Alt+S", "schwarz": "Ctrl+Alt+S"})
    assert any("doppelt" in p for p in problems)
    window.hotkeys.apply(controller.config["hotkeys"])


def test_windows_hotkey_mapping():
    from alupc.hotkeys import MOD_ALT, MOD_CONTROL, MOD_NOREPEAT, MOD_SHIFT, to_windows_hotkey

    assert to_windows_hotkey("Ctrl+Alt+S") == (MOD_NOREPEAT | MOD_CONTROL | MOD_ALT, ord("S"))
    assert to_windows_hotkey("Ctrl+Alt+PgDown") == (MOD_NOREPEAT | MOD_CONTROL | MOD_ALT, 0x22)
    assert to_windows_hotkey("Shift+F5") == (MOD_NOREPEAT | MOD_SHIFT, 0x74)
    assert to_windows_hotkey("Ctrl+Alt+1")[1] == ord("1")
    assert to_windows_hotkey("") is None


def test_timer_keeps_running_when_view_is_rebuilt(env):
    controller, window, _ = env
    from alupc.timer import clock

    clock.set(120)
    controller.config.put_scene({"name": "T", "layout": "vollbild",
                                 "slots": [{"type": "countdown", "minutes": 2}]})
    controller.run_command("szene:T")  # startet den Timer
    assert clock.running
    clock._accumulated = 30  # 30 s sind schon vergangen
    controller.run_command("szene:T")  # Szene neu aufbauen …
    assert clock.running and clock.remaining() <= 90.5  # … Timer läuft weiter statt neu zu beginnen
    controller.timer_action("toggle")
    assert not clock.running
    rem = clock.remaining()
    controller.show_timer()  # Timer-Kachel zeigt den pausierten Timer, ohne ihn zurückzusetzen
    assert abs(clock.remaining() - rem) < 0.5 and not clock.running
    assert controller.timer_visible()
    controller.timer_action("plus")
    assert clock.remaining() > rem + 59
    controller.timer_action("restart")
    assert clock.running and clock.remaining() > 170
    window._update_timer_ui()
    assert window.t_timer.badge.startswith("0")
    clock.reset()


def test_timer_clock_logic():
    from alupc.timer import TimerClock, format_time

    t = TimerClock()
    t.set(65)
    assert t.text() == "01:05" and t.fresh()
    t._accumulated = 64.2
    assert t.text() == "00:01" and t.urgency() == "gleich"
    t._accumulated = 70
    assert t.finished() and t.text() == "Zeit ist um!" and t.urgency() == "ende"
    t.toggle()  # abgelaufen + Start → beginnt neu
    assert t.running and not t.finished()
    t.set(30, "stoppuhr")
    t._accumulated = 75
    assert t.text() == "01:15" and not t.finished()
    assert format_time(3725) == "1:02:05"


def test_freeze_badge_and_watchdog(env):
    controller, _window, _ = env
    controller.show_source({"type": "color", "color": "#00ff00"})
    pump()
    controller.toggle_freeze()
    img = controller.output.freeze_layer.grab().toImage()
    w = img.width()
    # oben rechts ist das hellblaue Standbild-Symbol, links oben die grüne Fläche
    corner = QColor(img.pixel(w - 26, 26))
    assert corner.blue() > 150 and corner != QColor("#00ff00")
    assert QColor(img.pixel(20, 20)) == QColor("#00ff00")
    controller.config["output"] = {"hide_taskbar": True, "freeze_badge": False}
    controller.apply_output_settings()
    img = controller.output.freeze_layer.grab().toImage()
    assert QColor(img.pixel(w - 26, 26)) == QColor("#00ff00")
    controller.toggle_freeze()
    # Wächter: versteckt jemand das Fenster (z. B. Win+D), kommt es zurück
    controller.output.hide()
    controller.output._watch()
    assert controller.output.isVisible()


def test_hotkey_capture_dialog(env):
    controller, window, _ = env
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtCore import QEvent
    from alupc.ui.hotkey_edit import CaptureDialog, pretty

    dlg = CaptureDialog("Test", "")
    ev = QKeyEvent(QEvent.KeyPress, Qt.Key_K, Qt.ControlModifier | Qt.AltModifier)
    dlg.keyPressEvent(ev)
    assert dlg.sequence == "Ctrl+Alt+K"
    ev = QKeyEvent(QEvent.KeyPress, Qt.Key_K, Qt.NoModifier)
    dlg.keyPressEvent(ev)
    assert dlg.sequence == "Ctrl+Alt+K" and dlg.warn.text()  # ohne Zusatztaste nicht erlaubt
    assert pretty("Ctrl+Alt+PgDown") == "Strg+Alt+Bild↓"
    # Pausieren schaltet alle Kürzel ab und wieder an
    window.hotkeys.pause()
    assert all(not sc.isEnabled() for sc in window.hotkeys.shortcuts)
    window.hotkeys.resume()
    assert window.hotkeys.shortcuts and all(sc.isEnabled() for sc in window.hotkeys.shortcuts)


def test_split_tile_menu_and_action(env):
    controller, window, _ = env
    from PySide6.QtCore import QPointF

    tile = window.t_saver
    tile.resize(260, 132)
    hits = []
    tile.activated.connect(lambda: hits.append("action"))
    tile._press_pos = QPointF(40, 100)  # Klick auf die Kachel → Aktion
    tile._show_menu()
    assert hits == ["action"]
    controller.screensaver.stop()
    tile._press_pos = QPointF(250, 30)  # Klick auf den Pfeil → Menü, keine Aktion
    tile._show_menu()
    assert hits == ["action"] and tile.menu.isVisible()
    tile.menu.hide()


def test_program_window_matching():
    from alupc.sources import _app_part, find_window

    class W:
        def __init__(self, d):
            self.d = d

        def description(self):
            return self.d

    wins = [W("Folien.pptx - PowerPoint"), W("Neuer Tab — Mozilla Firefox")]
    assert find_window(wins, "Folien.pptx - PowerPoint").d == "Folien.pptx - PowerPoint"
    # Browser hat den Tab gewechselt → gleiches Programm wird trotzdem gefunden
    assert find_window(wins, "Startseite — Mozilla Firefox").d == "Neuer Tab — Mozilla Firefox"
    assert find_window(wins, "Gibt es nicht") is None
    assert _app_part("a - b - Word") == "Word"


def test_sounds_builtin_and_events(env, tmp_path):
    controller, _window, _ = env
    from alupc import sounds

    for name in sounds.BUILTIN:
        path = sounds.builtin_path(name)
        assert path.exists() and path.stat().st_size > 1000
    src = tmp_path / "mein ton.wav"
    src.write_bytes(sounds.builtin_path("ding").read_bytes())
    stored = sounds.upload(str(src))
    assert stored != str(src) and sounds.resolve(stored) is not None
    src.unlink()  # Original weg – hochgeladene Kopie bleibt
    assert sounds.resolve(stored) is not None
    cfg = controller.config
    events = dict(cfg["sounds"]["events"])
    events.update({"standbild_an": "builtin:ding", "schwarz_an": stored, "inhalt": "builtin:klick"})
    cfg["sounds"] = {**cfg["sounds"], "events": events}
    player = controller.sounds
    player.last_played = None
    controller.show_source({"type": "clock"})
    assert player.last_played == "builtin:klick"
    controller.toggle_freeze()
    assert player.last_played == "builtin:ding"
    controller.toggle_freeze()
    controller.toggle_privacy()
    assert player.last_played == stored
    controller.toggle_privacy()
    cfg["sounds"] = {**cfg["sounds"], "enabled": False}
    player.last_played = None
    controller.toggle_freeze()
    assert player.last_played is None  # Töne aus → still
    controller.toggle_freeze()


def test_timer_end_plays_sound(env):
    controller, _window, _ = env
    from alupc.timer import clock

    controller.config["sounds"] = {**controller.config["sounds"], "enabled": True}
    clock.set(30)
    clock.start()
    controller._watch_timer()
    clock._accumulated = 31  # abgelaufen
    controller.sounds.last_played = None
    controller._watch_timer()
    assert controller.sounds.last_played == "builtin:alarm"
    clock.reset()


def test_tile_with_own_screensaver_and_timer(env):
    controller, window, _ = env
    from alupc.timer import clock

    start = dict(controller.config["start_page"])
    start["custom"] = [
        {"id": "pause", "title": "Pause", "icon": "moon", "color": "#6366f1", "section": "schnell",
         "sound": "builtin:gong",
         "action": {"kind": "screensaver", "screensaver": {"style": "nachricht", "text": "Pause – 10 Minuten"}}},
        {"id": "t10", "title": "10 Minuten", "icon": "timer", "color": "#f43f5e", "section": "schnell",
         "action": {"kind": "timer", "timer": {"minutes": 10, "seconds": 0, "mode": "countdown",
                                               "autostart": True}}},
    ]
    controller.config["start_page"] = start
    window.rebuild_start()
    controller.sounds.last_played = None
    controller.run_tile("pause")
    assert controller.screensaver.active and controller.screensaver.override_id == "pause"
    assert controller.output.screensaver.cfg["text"] == "Pause – 10 Minuten"
    assert controller.sounds.last_played == "builtin:gong"  # eigener Ton der Kachel
    window.refresh()
    assert window.custom_tiles["custom:pause"].active
    controller.run_tile("pause")  # nochmal = beenden
    assert not controller.screensaver.active
    controller.run_tile("t10")
    assert clock.running and 590 < clock.remaining() <= 600
    assert controller.timer_visible()
    clock.reset()


def test_custom_tile_dialog_kinds(env):
    controller, window, _ = env
    from alupc.startpage import new_custom_tile
    from alupc.ui.start_page_dialog import CustomTileDialog

    dlg = CustomTileDialog(controller.config, new_custom_tile(), "", window, controller)
    dlg.title.setText("Meine Pause")
    dlg.kind.setCurrentIndex(dlg.kind.findData("screensaver"))
    dlg.saver.style_combo.setCurrentIndex(dlg.saver.style_combo.findData("uhr"))
    dlg._save()
    assert dlg.tile["action"]["kind"] == "screensaver"
    assert dlg.tile["action"]["screensaver"]["style"] == "uhr"
    dlg2 = CustomTileDialog(controller.config, new_custom_tile(), "", window, controller)
    dlg2.kind.setCurrentIndex(dlg2.kind.findData("timer"))
    dlg2.t_min.setValue(3)
    dlg2._save()
    assert dlg2.tile["action"] == {"kind": "timer", "timer": {"mode": "countdown", "minutes": 3, "seconds": 0,
                                                             "finished_text": "Zeit ist um!", "autostart": True}}


def test_website_favorites_and_browser_control(env):
    controller, window, _ = env
    import time

    html = ("data:text/html,<html><head><title>Start</title></head><body style='margin:0'>"
            "<button id=b style='width:100vw;height:100vh' onclick=\"document.title='Geklickt'\">X</button>"
            "</body></html>")
    controller.show_source({"type": "website", "url": html})
    view = controller.current_web_view()
    assert view is not None
    loaded = []
    view.loadFinished.connect(loaded.append)
    end = time.time() + 20
    while not loaded and time.time() < end:
        pump()
    assert loaded and loaded[0]
    controller.save_website("Testseite", html)
    assert controller.config["websites"]["favorites"][0] == {"title": "Testseite", "url": html}
    controller.save_website("Testseite 2", html)  # gleiche Adresse → ersetzt, nicht doppelt
    assert len(controller.config["websites"]["favorites"]) == 1

    window.open_browser_control()
    bc = window.browser_control
    pump()
    assert bc.view is view and bc.save_btn.isEnabled()
    bc.refresh()
    assert bc.preview.image() is not None
    # Klick in die Vorschau landet auf der Website (Knopf füllt die ganze Seite)
    from PySide6.QtCore import QEvent, QPointF
    from PySide6.QtGui import QMouseEvent

    bc.preview.resize(640, 360)
    center = QPointF(bc.preview.width() / 2, bc.preview.height() / 2)

    def click():
        for kind in (QEvent.MouseButtonPress, QEvent.MouseButtonRelease):
            ev = QMouseEvent(kind, center, center, Qt.LeftButton,
                             Qt.LeftButton if kind == QEvent.MouseButtonPress else Qt.NoButton, Qt.NoModifier)
            (bc.preview.mousePressEvent if kind == QEvent.MouseButtonPress else bc.preview.mouseReleaseEvent)(ev)

    # Chromium nimmt Eingaben erst an, wenn die Seite fertig gezeichnet ist – auf langsamen Rechnern
    # (GitHub) kann das nach „geladen“ noch etwas dauern, darum ggf. erneut klicken
    end = time.time() + 20
    next_click = 0.0
    while view.title() != "Geklickt" and time.time() < end:
        if time.time() >= next_click:
            click()
            next_click = time.time() + 1.5
        pump()
    assert view.title() == "Geklickt"
    bc._zoom(0.1)
    assert abs(view.zoomFactor() - 1.1) < 0.01
    # Keine Website mehr → Fenster zeigt Hinweis
    controller.show_source({"type": "clock"})
    pump()
    assert bc.view is None and not bc.save_btn.isEnabled()
    bc.close()


# ---------------------------------------------------------------- 0.5: Übergänge, Lautstärke, Programm
def test_transitions_all_kinds_finish(env):
    import time

    from alupc.transitions import TRANSITIONS

    controller, _window, _ = env
    for kind in TRANSITIONS:
        controller.config["transition"] = {"type": kind, "ms": 120}
        controller.show_source({"type": "color", "color": "#ff0000"})
        pump()
        controller.show_source({"type": "color", "color": "#00ff00"})
        expected = 0 if kind == "schnitt" else 1
        assert len(controller.output._fades) == expected, kind
        end = time.time() + 2
        while controller.output._fades and time.time() < end:
            pump()
            controller.output.grab()  # Zeichnen jeder Übergangsart muss klappen
        assert controller.output._fades == []


def test_scene_transition_overrides_setup(env):
    controller, _window, _ = env
    controller.config["transition"] = {"type": "blende", "ms": 400}
    controller.config.put_scene({"name": "S", "layout": "vollbild", "slots": [{"type": "color"}],
                                 "transition": {"type": "zoom", "ms": 900}})
    assert controller.transition_for({"type": "scene", "scene": "S"}) == ("zoom", 900)
    assert controller.transition_for({"type": "color"}) == ("blende", 400)
    controller.config["appearance"] = {**controller.config["appearance"], "fade": False}
    assert controller.transition_for({"type": "color"})[0] == "schnitt"  # Setup: harter Schnitt
    assert controller.transition_for({"type": "scene", "scene": "S"}) == ("zoom", 900)  # Szene gilt trotzdem


def test_media_volume_live(env, tmp_path):
    controller, window, _ = env
    controller.show_source({"type": "color"})
    pump()
    assert controller.media_state() is None
    assert window.volume_box.isHidden()
    controller.show_source({"type": "video", "path": str(tmp_path / "fehlt.mp4"), "volume": 40})
    pump()
    assert controller.media_state() == {"volume": 40, "muted": False}
    assert abs(controller.output.content.audio.volume() - 0.4) < 0.01
    controller.set_media_volume(volume=70)
    controller.set_media_volume(muted=True)
    assert controller.content["volume"] == 70 and controller.content["muted"] is True
    assert controller.config["last_content"]["volume"] == 70
    assert controller.output.content.audio.isMuted()
    pump()
    assert not window.volume_box.isHidden()
    assert window.volume_box.mute_btn.isChecked()

    # In einer Szene: gilt für alle Medien darin, auch für Websites
    controller.config.put_scene({"name": "M", "layout": "nebeneinander", "slots": [
        {"type": "website", "url": "about:blank", "volume": 30},
        {"type": "video", "path": str(tmp_path / "fehlt.mp4")}]})
    controller.show_source({"type": "scene", "scene": "M"})
    pump()
    from alupc.sources import media_sources

    assert len(media_sources(controller.output.content)) == 2
    controller.set_media_volume(volume=55)
    web = media_sources(controller.output.content)[0]
    assert web.volume == 55
    assert controller.media_state()["volume"] == 55


def test_capture_programs_filters_system_windows(monkeypatch):
    from alupc.platform.base import WindowBackend, WindowInfo
    from alupc.ui import program_dialog

    class Fake:
        def __init__(self, text):
            self.text = text

        def description(self):
            return self.text

    monkeypatch.setattr(program_dialog, "capturable_windows",
                        lambda: [Fake("Program Manager"), Fake("Editor"), Fake("Editor"), Fake("Film")])

    class Backend(WindowBackend):
        can_list = True

        def list_windows(self):
            return [WindowInfo("1", "Editor", "notepad"), WindowInfo("2", "Film", "vlc", minimized=True)]

    programs = program_dialog.capture_programs(Backend())
    assert [(p.title, p.app, p.minimized) for p in programs] == [("Editor", "notepad", False),
                                                                  ("Film", "vlc", True)]
    assert "minimiert" in programs[1].label()
    # Ohne Fensterliste des Systems: alles zeigen, was Qt aufnehmen kann
    assert len(program_dialog.capture_programs(WindowBackend())) == 3


def test_program_dialog_list_keeps_selection(env, monkeypatch):
    controller, window, _ = env
    from alupc.ui import program_dialog

    progs = [program_dialog.Program("A"), program_dialog.Program("B", "app")]
    monkeypatch.setattr(program_dialog, "capture_programs", lambda _b: list(progs))
    dialog = program_dialog.ProgramDialog(controller, window)
    lst = dialog.capture_list
    assert lst.list.count() == 2
    lst.list.setCurrentRow(1)
    progs.insert(0, program_dialog.Program("Neu"))
    lst.reload()
    assert lst.selected().title == "B"
    lst.search.setText("neu")
    assert lst.selected() is None or lst.selected().title != "B"
    lst.search.setText("")
    lst.list.setCurrentRow(2)
    dialog._do_capture()
    assert controller.content == {"type": "window", "title": "B"}
    dialog.deleteLater()


def test_window_source_wakes_minimized(env, monkeypatch):
    from alupc import sources
    from alupc.platform.base import WindowBackend

    calls = []

    class Backend(WindowBackend):
        can_restore_background = True

        def is_minimized(self, title):
            return True

        def restore_in_background(self, title):
            calls.append(title)
            return True

    monkeypatch.setattr(sources, "_window_backend", Backend())

    class Win:
        def description(self):
            return "Film"

    monkeypatch.setattr(sources, "capturable_windows", lambda: [Win()])
    src = sources.WindowSource.__new__(sources.WindowSource)
    sources.SinkView.__init__(src, "contain")
    src.title = "Film"
    src.restore_minimized = True
    src._image = None
    src.state = "start"
    assert src._wake_if_minimized() is True
    assert calls == ["Film"]
    src.restore_minimized = False
    assert src._wake_if_minimized() is False
    assert src.state == "minimiert"
    assert "minimiert" in src._message


# ---------------------------------------------------------------- 0.6: Linux
class FakeFingerprint:
    name = "fprintd"
    can_enroll = True
    login_toggle = True
    can_auto_install = True

    def __init__(self, missing=("libpam-fprintd",), sensors=True, match=True):
        self.missing = list(missing)
        self.sensors = sensors
        self.match = match
        self.log = []
        self.login = False

    def missing_packages(self):
        return list(self.missing)

    def install_packages(self, pkgs):
        self.log.append(("install", tuple(pkgs)))
        self.missing = []

    def availability(self):
        return (True, "") if self.sensors else (False, "Kein Sensor")

    def list_sensors(self):
        from alupc.platform.base import Sensor

        return [Sensor("/dev/0", "Testsensor")] if self.sensors else []

    def detect_hardware(self):
        return [("Goodix (USB 27c6:538c)", "Zusatztreiber nötig")]

    def list_enrolled(self, _sid):
        return []

    def is_enrolled(self, sid, finger):
        return finger in self.list_enrolled(sid)

    def enroll(self, sid, finger, status):
        for i in range(1, 4):
            status("auflegen", i, 3)
        self.log.append(("enroll", finger))

    def verify(self, sid, status):
        status("auflegen", 0, 0)
        return (self.match, "Erkannt" if self.match else "Passt nicht")

    def login_enabled(self):
        return self.login

    def set_login_enabled(self, on):
        self.login = on
        self.log.append(("login", on))

    def cancel(self):
        self.log.append(("cancel",))

    def open_system_settings(self):
        self.log.append(("hello",))


def _wait(cond, seconds=5):
    import time

    end = time.time() + seconds
    while not cond() and time.time() < end:
        pump()
        time.sleep(0.01)
    return cond()


def test_fingerprint_wizard_runs_all_steps(env):
    from alupc.ui.fingerprint_wizard import FingerprintWizard

    backend = FakeFingerprint()
    wiz = FingerprintWizard(backend, None, "left-thumb")
    wiz.start()
    assert _wait(lambda: not wiz.running)
    assert [s.state for s in wiz.steps.values()] == ["ok"] * 5, [s.detail.text() for s in wiz.steps.values()]
    assert backend.log == [("install", ("libpam-fprintd",)), ("enroll", "left-thumb"), ("login", True)]
    assert "Fertig" in wiz.message.text()
    wiz.deleteLater()


def test_fingerprint_wizard_explains_missing_driver(env):
    from alupc.ui.fingerprint_wizard import FingerprintWizard

    backend = FakeFingerprint(missing=(), sensors=False)
    wiz = FingerprintWizard(backend)
    wiz.start()
    assert _wait(lambda: not wiz.running)
    assert wiz.steps["sensor"].state == "fehler"
    assert "27c6:538c" in wiz.steps["sensor"].detail.text()
    assert wiz.start_btn.isEnabled()
    # Test-Scan passt nicht → anhalten, Anmeldung NICHT einschalten
    backend = FakeFingerprint(missing=(), match=False)
    wiz2 = FingerprintWizard(backend)
    wiz2.start()
    assert _wait(lambda: not wiz2.running)
    assert wiz2.steps["test"].state == "fehler"
    assert ("login", True) not in backend.log
    wiz.deleteLater()
    wiz2.deleteLater()


def test_fingerprint_wizard_windows_flow(env):
    from alupc.ui.fingerprint_wizard import FingerprintWizard

    backend = FakeFingerprint(missing=())
    backend.name, backend.can_enroll, backend.login_toggle = "winbio", False, False
    wiz = FingerprintWizard(backend)
    wiz.start()
    assert _wait(lambda: not wiz.next_btn.isHidden())
    assert ("hello",) in backend.log and "pakete" not in wiz.steps
    wiz.next_btn.click()
    assert _wait(lambda: not wiz.running)
    assert wiz.steps["test"].state == "ok"
    wiz.deleteLater()


def test_screen_source_uses_kwin_without_asking(env, monkeypatch):
    from PySide6.QtCore import QObject, Signal

    from alupc import sources
    from alupc.platform import kwin_capture

    class FakeFeed(QObject):
        frame = Signal(QImage)
        failed = Signal(str)

        def __init__(self, name, fps, cursor=True, parent=None):
            super().__init__(parent)
            self.name = name
            self.cursor = cursor
            self.stopped = False

        def start(self):
            img = QImage(40, 20, QImage.Format_RGB32)
            img.fill(QColor("#00ff00"))
            self.frame.emit(img)

        def frame_taken(self):
            pass

        def stop(self):
            self.stopped = True

    monkeypatch.setattr(sources, "_kwin_allowed", lambda _name: True)
    monkeypatch.setattr(kwin_capture, "KWinScreenFeed", FakeFeed)
    controller, _window, _ = env
    controller.mirror()
    pump()
    src = controller.output.content
    assert src.method == "kwin" and src.feed.name == "Haupt"
    assert src.image().pixelColor(1, 1) == QColor("#00ff00")
    feed = src.feed
    controller.show_source({"type": "color"})
    assert feed.stopped
    # KWin verweigert später → normale Aufnahme
    controller.mirror()
    src = controller.output.content
    src.feed.failed.emit("NoAuthorized")
    assert src.method == "qt" and src.capture is not None


def test_tray_badge_icon_has_all_sizes(env):
    controller, window, _ = env
    from alupc.ui import icons

    ic = icons.app_icon_with_badge("snowflake", "#0ea5e9")
    sizes = {s.width() for s in ic.availableSizes()}
    assert {16, 22, 32, 48, 256} <= sizes
    controller.toggle_privacy()
    pump()
    assert window._tray_key == "eye_off"
    controller.toggle_privacy()


# ---------------------------------------------------------------- 0.7: Maus, Laserpointer
def test_mirror_draws_mouse_pointer(env, monkeypatch):
    from PySide6.QtCore import QPoint

    from alupc import cursor as cursor_mod

    controller, _window, _ = env
    controller.mirror()
    pump()
    src = controller.output.content
    assert src.method == "qt" and src._cursor_on
    img = QImage(1920, 1080, QImage.Format_RGB32)
    img.fill(QColor("#336699"))
    src._pending = None
    src._image = img
    src.resize(960, 540)
    main = controller.main_screen().geometry()
    t = cursor_mod.tracker()
    t._set(QPoint(main.x() + main.width() // 2, main.y() + main.height() // 2))
    shot = src.grab().toImage()
    # Pfeilspitze in der Bildmitte: dort (knapp daneben) ist der Pfeil weiß/schwarz statt blau
    colors = {shot.pixelColor(480 + dx, 270 + dy).name() for dx in range(1, 6) for dy in range(3, 12)}
    assert "#ffffff" in colors or "#000000" in colors, colors
    # Ausschalten im Setup → kein Zeiger mehr
    controller.config["output"] = {**controller.config["output"], "mirror_cursor": False}
    controller.apply_output_settings()
    shot = src.grab().toImage()
    colors = {shot.pixelColor(480 + dx, 270 + dy).name() for dx in range(1, 6) for dy in range(3, 12)}
    assert colors == {"#336699"}
    controller.config["output"] = {**controller.config["output"], "mirror_cursor": True}
    controller.apply_output_settings()
    users = t.users
    controller.show_source({"type": "color"})
    assert t.users == users - 1  # Aufnahme beendet → Abfrage wird freigegeben


def test_cursor_stays_home_except_extend(env):
    from PySide6.QtGui import QCursor

    controller, _window, _ = env
    controller.show_source({"type": "color"})
    pump()
    assert controller.cursor_should_stay_home()
    guard = controller.cursor_guard
    assert guard.active
    out = controller.output_screen().geometry()
    QCursor.setPos(out.center())
    guard._enforce()
    assert controller.main_screen().geometry().contains(QCursor.pos())
    controller.extend()
    pump()
    assert not controller.cursor_should_stay_home() and not guard.active
    controller.show_source({"type": "color"})
    controller.config["output"] = {**controller.config["output"], "confine_cursor": False}
    controller.apply_output_settings()
    assert not guard.active
    controller.config["output"] = {**controller.config["output"], "confine_cursor": True}
    controller.apply_output_settings()




# ---------------------------------------------------------------- 0.8: Zeigen & Zeichnen
def _mouse(widget, kind, pos, button=None):
    from PySide6.QtCore import QEvent, QPointF
    from PySide6.QtGui import QMouseEvent

    button = button if button is not None else Qt.LeftButton
    buttons = Qt.LeftButton if kind in (QEvent.MouseButtonPress, QEvent.MouseMove) and button == Qt.LeftButton \
        else Qt.NoButton
    ev = QMouseEvent(kind, QPointF(pos), QPointF(pos), button if kind != QEvent.MouseMove else Qt.NoButton,
                     buttons, Qt.NoModifier)
    {QEvent.MouseButtonPress: widget.mousePressEvent, QEvent.MouseMove: widget.mouseMoveEvent,
     QEvent.MouseButtonRelease: widget.mouseReleaseEvent}[kind](ev)


def test_presenter_laser_and_drawing(env):
    from PySide6.QtCore import QEvent, QPointF

    controller, window, _ = env
    controller.show_source({"type": "color", "color": "#000000"})
    pump()
    controller.run_command("zeichnen")
    pump()
    win = window.presenter
    laser = controller.laser
    assert win.isVisible() and laser.remote and laser.isVisible()
    assert laser.geometry() == controller.output_screen().geometry()
    canvas = win.canvas
    canvas.resize(800, 450)
    a = canvas.area()
    center = QPointF(a.x() + a.width() / 2, a.y() + a.height() / 2)

    # Laser: Maus in der Mitte der Vorschau → Punkt in der Mitte von Monitor 2
    win.set_tool("laser")
    _mouse(canvas, QEvent.MouseMove, center)
    out = controller.output_screen().geometry()
    assert abs(laser.point.x() - out.width() / 2) < 2 and abs(laser.point.y() - out.height() / 2) < 2
    canvas.leaveEvent(None)
    assert laser.point is None

    # Stift: Strich von links oben zur Mitte
    win.set_tool("pen")
    win.set_color("#22c55e")
    start = QPointF(a.x() + a.width() * 0.25, a.y() + a.height() * 0.25)
    _mouse(canvas, QEvent.MouseButtonPress, start)
    for i in range(1, 11):
        _mouse(canvas, QEvent.MouseMove, start + (center - start) * (i / 10))
    _mouse(canvas, QEvent.MouseButtonRelease, center)
    assert len(laser.strokes) == 1 and laser.strokes[0]["color"] == "#22c55e"
    assert len(laser.strokes[0]["points"]) == 11
    img = laser.grab().toImage()
    mid = QPointF(out.width() * 0.375, out.height() * 0.375).toPoint()
    assert img.pixelColor(mid).green() > 150  # grüner Strich auf Monitor 2
    prev = canvas.grab().toImage()
    pm = QPointF(a.x() + a.width() * 0.375, a.y() + a.height() * 0.375).toPoint()
    assert prev.pixelColor(pm).green() > 150  # … und in der Vorschau

    # Textmarker, Rückgängig, Radierer
    win.set_tool("marker")
    _mouse(canvas, QEvent.MouseButtonPress, center)
    _mouse(canvas, QEvent.MouseMove, center + QPointF(60, 0))
    _mouse(canvas, QEvent.MouseButtonRelease, center + QPointF(60, 0))
    assert laser.strokes[-1]["tool"] == "marker"
    controller.laser.undo()
    assert len(laser.strokes) == 1
    win.set_tool("eraser")
    _mouse(canvas, QEvent.MouseButtonPress, start)
    _mouse(canvas, QEvent.MouseButtonRelease, start)
    assert laser.strokes == []

    # Neuer Inhalt → Zeichnungen weg (Standard)
    laser.begin_stroke("pen", "#ff0000", 0.004, QPointF(0.5, 0.5))
    controller.show_source({"type": "color", "color": "#111111"})
    assert laser.strokes == []
    # Schwarz: nichts vom Laser/Zeichnen zu sehen
    laser.begin_stroke("pen", "#ff0000", 0.02, QPointF(0.5, 0.5))
    laser.extend_stroke(QPointF(0.6, 0.5))
    controller.toggle_privacy()
    img = laser.grab().toImage()
    assert img.pixelColor(QPointF(out.width() * 0.55, out.height() * 0.5).toPoint()).red() < 50
    controller.toggle_privacy()
    # Schließen → Zeichnung bleibt (erst Szenenwechsel/Löschen entfernt sie)
    win.close()
    pump()
    assert laser.strokes and not laser.remote and laser.isVisible()
    controller.laser.clear_strokes()
    assert not laser.isVisible()
    assert controller.config["draw"]["tool"] == "eraser"  # zuletzt gewähltes Werkzeug gemerkt


def test_drawings_stay_until_deleted_or_scene_change(env, tmp_path):
    from PySide6.QtCore import QPointF

    from alupc.config import Config
    from alupc.controller import Controller

    controller, window, _ = env
    controller.show_source({"type": "color", "color": "#123456"})
    window.open_presenter()
    controller.laser.begin_stroke("pen", "#ff0000", 0.004, QPointF(0.2, 0.2))
    controller.laser.extend_stroke(QPointF(0.6, 0.6))
    controller.laser.end_stroke()
    window.presenter.close()
    pump()
    # Fenster zu → Zeichnung bleibt auf Monitor 2 und ist gespeichert
    assert len(controller.laser.strokes) == 1 and controller.laser.isVisible()
    assert len(controller.config["draw"]["strokes"]) == 1
    # Neustart von AluPC (gleicher Inhalt) → Zeichnung ist wieder da
    controller.config.save()
    again = Controller(Config(controller.config.path))
    again.display.available = lambda: False
    again.restore_last()
    assert len(again.laser.strokes) == 1 and again.laser.strokes[0]["points"][0] == (0.2, 0.2)
    again.shutdown()
    # Szenenwechsel → weg (auch aus dem Speicher)
    controller.show_source({"type": "color", "color": "#654321"})
    assert controller.laser.strokes == [] and controller.config["draw"]["strokes"] == []
    # von Hand löschen
    controller.laser.begin_stroke("pen", "#ff0000", 0.004, QPointF(0.5, 0.5))
    controller.laser.end_stroke()
    controller.run_command("zeichnungen_loeschen")
    assert controller.laser.strokes == [] and controller.config["draw"]["strokes"] == []
    # „laserpointer“ (alter Befehl/Tastenkürzel) öffnet jetzt Zeigen & Zeichnen
    window.presenter.close()
    controller.run_command("laserpointer")
    pump()
    assert window.presenter.isVisible()
    window.presenter.close()


def test_preview_frame_rate_selectable(env):

    from PySide6.QtCore import QSize

    from alupc.output_window import grab_scaled

    controller, window, _ = env
    controller.show_source({"type": "color", "color": "#ff0000"})
    pump()
    window.open_presenter()
    win = window.presenter
    assert win.fps() == 30 and win.timer.interval() == 33  # Standard jetzt 30 statt 10
    win.fps_combo.setCurrentIndex(win.fps_combo.findData(60))
    assert win.timer.interval() == 17 and controller.config["draw"]["fps"] == 60
    # Vorschau wird direkt verkleinert gezeichnet – richtiger Inhalt, richtige Größe
    img = grab_scaled(controller.output, QSize(320, 180))
    assert img.width() <= 320 and img.height() <= 180 and img.pixelColor(10, 10).name() == "#ff0000"
    # Es kommen wirklich viele Bilder pro Sekunde an (nicht mehr nur 10)
    from PySide6.QtTest import QTest

    counted = []
    win.timer.timeout.connect(lambda: counted.append(1))  # eigener Zähler (die Anzeige setzt ihren zurück)
    QTest.qWait(1000)
    assert len(counted) >= 15, len(counted)  # großzügig: GitHub-Rechner sind langsam
    win.close()
    pump()


def test_cursor_tracker_cleans_up_failed_kwin(monkeypatch):
    from alupc import cursor as cursor_mod
    from alupc.platform import kwin_cursor

    stopped = []

    class Broken(kwin_cursor.CursorReceiver):
        def start(self, load_script=True):
            raise RuntimeError("KWin-Skript ließ sich nicht laden")

        def stop(self):
            stopped.append(1)

    monkeypatch.setattr(cursor_mod, "is_wayland", lambda: True)
    monkeypatch.setattr(cursor_mod, "wayland_kde", lambda: True)
    monkeypatch.setattr(kwin_cursor, "CursorReceiver", Broken)
    t = cursor_mod.CursorTracker()
    t.acquire()
    assert t.method == "keine" and t._kwin is None and stopped == [1]
    t.release()


# ---------------------------------------------------------------- 0.9: Fingerabdruckmodul am seriellen Anschluss
@pytest.mark.skipif(not __import__("sys").platform.startswith("linux"), reason="virtueller Anschluss nur Linux")
def test_serial_module_page_and_wizard(env, monkeypatch):
    pytest.importorskip("serial")
    import time

    from fake_zw101 import FakeZW101

    from alupc.platform import zw_fingerprint as zw
    from alupc.ui.fingerprint_wizard import FingerprintWizard

    controller, window, tmp = env
    fake = FakeZW101()
    try:
        monkeypatch.setattr(zw, "candidate_ports", lambda: [fake.port])
        backend = controller.fingerprint
        assert backend.availability() == (True, "") and backend.is_serial
        assert backend.can_enroll and backend.can_delete

        # Seite: passt sich an (Finger-Auswahl, Löschen sichtbar, kein Windows-Hello-Hinweis)
        window._go(3)
        page = window.pages[3].findChild(__import__("alupc.ui.fingerprint_page", fromlist=["x"]).FingerprintPage)
        end = time.time() + 5
        while page.sensor_combo.count() == 0 and time.time() < end:
            pump()
        assert fake.port in page.sensor_combo.currentData()
        assert not page.finger_combo.isHidden() and not page.hello_note.isVisible()

        # Assistent: Sensor → anlernen → testen (Anmeldung hier aus: dafür braucht es das .deb)
        fake.finger = "zeigefinger"
        fake.auto_lift = True
        wiz = FingerprintWizard(backend, None, "right-index-finger")
        wiz.login_box.setChecked(False)
        wiz.start()
        end = time.time() + 15
        while wiz.running and time.time() < end:
            pump()
            time.sleep(0.01)
        states = {k: s.state for k, s in wiz.steps.items()}
        assert states["sensor"] == "ok" and states["anlernen"] == "ok" and states["test"] == "ok", \
            {k: s.detail.text() for k, s in wiz.steps.items()}
        assert list(fake.library.values()) == ["zeigefinger"]
        wiz.deleteLater()
    finally:
        fake.close()


# ---------------------------------------------------------------- 0.10: Mediathek
def test_media_library_dialog(env, tmp_path):
    import time

    from alupc import media_library as lib
    from alupc.ui.media_library import MediaLibraryDialog

    controller, window, _ = env
    paths = []
    for name, color in (("rot", "#ff0000"), ("blau", "#0000ff")):
        img = QImage(800, 450, QImage.Format_RGB32)
        img.fill(QColor(color))
        path = tmp_path / f"{name}.png"
        img.save(str(path))
        paths.append(str(path))
    lib.save(controller.config, {"type": "image", "path": paths[0]}, "Rotes Bild")
    lib.save(controller.config, {"type": "video", "path": str(tmp_path / "fehlt.mp4")})
    controller.show_source({"type": "image", "path": paths[1]})  # → automatisch unter „Zuletzt“
    pump()
    dialog = MediaLibraryDialog(controller, window)
    assert dialog.grid.count() == 3
    titles = [dialog.grid.item(i).text() for i in range(3)]
    assert titles == ["fehlt", "Rotes Bild", "blau"]
    # Filter und Suche
    dialog._set_filter("video")
    assert dialog.grid.count() == 1
    dialog._set_filter("all")
    dialog.search.setText("rot")
    assert dialog.grid.count() == 1
    dialog.search.setText("")
    # Vorschaubild wird im Hintergrund erzeugt und zwischengespeichert
    end = time.time() + 5
    while f"image:{paths[0]}" not in dialog.thumbs.memory and time.time() < end:
        pump()
    assert f"image:{paths[0]}" in dialog.thumbs.memory
    # „Zuletzt“ speichern, dann anzeigen
    dialog.grid.item(2).setSelected(True)
    assert dialog.save_btn.isEnabled()
    dialog.save_selected()
    assert lib.is_saved(controller.config, {"type": "image", "path": paths[1]})
    dialog.grid.clearSelection()
    item = next(dialog.grid.item(i) for i in range(dialog.grid.count()) if dialog.grid.item(i).text() == "Rotes Bild")
    item.setSelected(True)
    dialog.show_selected()
    assert controller.content == {"type": "image", "path": paths[0]}
    # fehlende Datei lässt sich nicht zeigen
    dialog = MediaLibraryDialog(controller, window)
    missing = next(dialog.grid.item(i) for i in range(dialog.grid.count()) if dialog.grid.item(i).text() == "fehlt")
    missing.setSelected(True)
    assert not dialog.show_btn.isEnabled()
    # Menü an der Kachel
    window._fill_media_menu(window.media_menu)
    texts = [a.text() for a in window.media_menu.actions()]
    assert "Rotes Bild" in texts and "Mediathek öffnen …" in texts


def test_cursor_rule_depends_on_mode_not_visibility(env):
    controller, _window, _ = env
    controller.show_source({"type": "color"})
    pump()
    controller.output.hide()  # z. B. kurz beim Umschalten des Monitors
    assert controller.cursor_should_stay_home()
    controller.program_moved("Editor")  # Programm direkt auf Monitor 2 = Erweitern → Maus frei
    assert not controller.cursor_should_stay_home()
    controller.toggle_privacy()  # Schwarz über dem Desktop → Maus bleibt auf Monitor 1
    assert controller.cursor_should_stay_home()
    controller.toggle_privacy()
    controller.extend()
    assert not controller.cursor_should_stay_home()


# ---------------------------------------------------------------- 0.10: Mediensteuerung
@pytest.fixture(scope="module")
def test_video(tmp_path_factory):
    import subprocess
    import sys

    path = tmp_path_factory.mktemp("video") / "test.mp4"
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen"}
    proc = subprocess.run([sys.executable, str(HERE / "make_video.py"), str(path)], env=env,
                          capture_output=True, timeout=120)
    if proc.returncode != 0 or not path.exists() or path.stat().st_size < 1000:
        pytest.skip("Testvideo ließ sich hier nicht erzeugen")
    return str(path)


def _until(cond, seconds=8):
    import time

    end = time.time() + seconds
    while not cond() and time.time() < end:
        pump()
        time.sleep(0.02)
    return cond()


def test_media_bar_controls_video(env, test_video):
    controller, window, _ = env
    bar = window.media_bar
    controller.show_source({"type": "color"})
    pump()
    assert bar.isHidden()
    controller.show_source({"type": "video", "path": test_video, "loop": True, "muted": True})
    pump()
    assert not bar.isHidden() and bar.title.text() == "test"
    video = bar.current()
    assert _until(lambda: video.duration() > 0), "Video lädt nicht"
    bar.refresh()
    assert bar.dur_label.text() == "0:04"
    bar._toggle()  # Pause
    assert _until(lambda: not video.playing())
    bar._seek(2500)  # auf der Zeitleiste springen
    assert _until(lambda: abs(video.position() - 2500) < 400), video.position()
    bar._skip(-10_000)  # 10 s zurück → nicht vor den Anfang
    assert _until(lambda: video.position() < 300), video.position()
    bar._toggle()
    assert _until(lambda: video.playing())


def test_media_bar_in_scene_with_two_videos(env, test_video):
    controller, window, _ = env
    controller.config.put_scene({"name": "Zwei Videos", "layout": "nebeneinander", "slots": [
        {"type": "video", "path": test_video, "muted": True},
        {"type": "video", "path": test_video, "muted": True}]})
    controller.show_source({"type": "scene", "scene": "Zwei Videos"})
    pump()
    bar = window.media_bar
    assert not bar.isHidden() and bar.which.count() == 2 and not bar.which.isHidden()
    bar.which.setCurrentIndex(1)
    second = bar.current()
    assert second is bar.videos[1]
    assert _until(lambda: second.duration() > 0)
    bar._toggle()
    assert _until(lambda: not second.playing())
    assert bar.videos[0].playing()  # nur das gewählte Video pausiert


def test_coding_screensavers(env):
    import time

    from alupc.screensaver import ScreensaverView
    from alupc.screensaver_code import SNIPPETS, highlight

    controller, _window, _ = env
    for style in ("matrix", "code", "terminal", "netz", "sterne"):
        view = ScreensaverView({"style": style}, controller.config.get_scene)
        view.resize(640, 360)
        for _ in range(40):  # ~1,5 s Animation
            view._last_tick -= 0.04
            view._tick()
        img = view.grab().toImage()
        colors = {img.pixelColor(x, y).name() for x in range(0, 640, 16) for y in range(0, 360, 12)}
        assert len(colors) > 3, (style, colors)  # es ist wirklich etwas zu sehen
        view.stop()
    # Syntaxfarben: Schlüsselwort, Text, Zeichenkette, Kommentar
    parts = dict((t, c) for t, c in highlight('def zeigen(x):  # "Hallo"', "python"))
    assert parts["def"] == "keyword" and parts["zeigen"] == "function"
    assert highlight('print("Hi")  # Kommentar', "python")[-1] == ("# Kommentar", "comment")
    assert all(len(text) > 100 for _name, _lang, text in SNIPPETS)
    time.sleep(0)


def test_hand_picker(env):
    from PySide6.QtCore import QEvent

    from alupc.ui.hand_picker import HandPicker

    hands = HandPicker()
    hands.resize(420, 200)
    picked = []
    hands.fingerClicked.connect(picked.append)
    fingers = {k: tip for k, _path, tip in hands._fingers()}
    assert len(fingers) == 10
    for key in ("left-thumb", "right-index-finger", "right-little-finger"):
        _mouse(hands, QEvent.MouseButtonPress, fingers[key])
    assert picked == ["left-thumb", "right-index-finger", "right-little-finger"]
    assert hands.selected == "right-little-finger"
    hands.set_enrolled({"right-thumb"})
    img = hands.grab().toImage()
    tip = fingers["right-thumb"].toPoint()
    c = img.pixelColor(tip.x(), tip.y() + 10)
    assert c.green() > c.red()  # angelernter Finger leuchtet grün


# ---------------------------------------------------------------- 0.11: Handy → Monitor 2
FAKE_UXPLAY = '''#!%(python)s
import sys, time
args = sys.argv[1:]
if args == ["-h"]:
    print("UxPlay 1.73 usage: ... %(vrtp)s")
    sys.exit(0)
open(%(log)r, "a").write(" ".join(args) + "\\n")
print("Initialized server socket(s)", flush=True)
if "-pin" in args:
    print("Pin code: 4711", flush=True)
if "-vrtp" in args:
    port = int(args[args.index("-vrtp") + 1].rsplit("port=", 1)[1])
    time.sleep(1.0)
    sys.path.insert(0, %(tests)r)
    import rtp_sender
    rtp_sender.main(port, 6.0)
time.sleep(30)
'''


def _fake_uxplay(tmp_path, vrtp: bool) -> tuple[str, Path]:
    import sys

    log = tmp_path / "uxplay_args.txt"
    script = tmp_path / ("uxplay_neu" if vrtp else "uxplay_alt")
    script.write_text(FAKE_UXPLAY % {"python": sys.executable, "vrtp": "-vrtp pipeline" if vrtp else "",
                                     "log": str(log), "tests": str(HERE)})
    script.chmod(0o755)
    return str(script), log


def test_handy_helpers(tmp_path):
    import sys

    from alupc import handy

    if sys.platform.startswith("win"):
        pytest.skip("Fake-Programm ist ein Shell-Skript")
    new, _ = _fake_uxplay(tmp_path, True)
    old, _ = _fake_uxplay(tmp_path, False)
    assert handy.supports_vrtp(new) and not handy.supports_vrtp(old)
    assert handy.supports_vrtp(str(tmp_path / "gibtsnicht")) is False
    assert handy.find_program("uxplay", new) == new
    assert "m=video 5004 RTP/AVP 96" in handy.sdp_text(5004)
    args = handy.uxplay_args("Klasse 7b", "1234", 5004)
    assert args[:4] == ["-n", "Klasse 7b", "-nh", "-p"] and args[4:6] == ["-pin", "1234"]
    assert args[-1].endswith("udpsink host=127.0.0.1 port=5004")
    assert handy.uxplay_args("", "zufall", None)[4] == "-pin" and "-fs" in handy.uxplay_args("", "", None)
    sc = handy.scrcpy_args((1920, 0, 1280, 720))
    assert sc[sc.index("--window-x") + 1] == "1920" and "--fullscreen" in sc
    assert len(handy.random_pin()) == 4


def test_airplay_source_shows_stream(env, tmp_path):
    """UxPlay ≥ 1.73 (simuliert): Bild kommt per RTP und erscheint als normale Quelle auf Monitor 2."""
    import sys

    if sys.platform.startswith("win"):
        pytest.skip("Fake-Programm ist ein Shell-Skript")
    pytest.importorskip("av")
    controller, window, _ = env
    uxplay, log = _fake_uxplay(tmp_path, True)
    controller.config["handy"] = {**controller.config["handy"], "uxplay_path": uxplay, "pin": "zufall",
                                  "airplay_name": "Beamer"}
    controller.start_airplay()
    pump()
    view = controller.output.content
    assert controller.content == {"type": "airplay"} and view.mode == "stream"
    assert "Beamer" in view._message
    assert _until(log.exists, 5)
    assert "-vrtp" in log.read_text() and "-pin" in log.read_text()
    assert _until(lambda: view._had_frames, 20), "Kein Bild vom (simulierten) iPhone"
    assert _until(lambda: view._image is not None and not view._image.isNull(), 5)
    c = view._image.pixelColor(view._image.width() - 5, view._image.height() // 2)
    assert c.red() > 150 and c.green() < 90, c.name()  # rotes Testbild
    assert controller.airplay.pin_code == "4711"
    pump()
    assert window.t_airplay.active and not window.t_extend.active
    controller.extend()  # etwas anderes → UxPlay wird (verzögert) beendet
    assert _until(lambda: not controller.airplay.running(), 5)


def test_handy_windows_mode(env, tmp_path, monkeypatch):
    """Ältere UxPlay-Version bzw. scrcpy: eigenes Fenster, das auf Monitor 2 geschoben wird."""
    import sys

    if sys.platform.startswith("win"):
        pytest.skip("Fake-Programm ist ein Shell-Skript")
    controller, window, _ = env
    uxplay, log = _fake_uxplay(tmp_path, False)
    scrcpy = tmp_path / "scrcpy"
    scrcpy.write_text(f"#!{sys.executable}\nimport sys, time\nopen({str(tmp_path / 'sc.txt')!r}, 'w')"
                      ".write(' '.join(sys.argv[1:]))\ntime.sleep(30)\n")
    scrcpy.chmod(0o755)
    controller.config["handy"] = {**controller.config["handy"], "uxplay_path": uxplay, "scrcpy_path": str(scrcpy),
                                  "pin": ""}
    from alupc.platform.base import WindowInfo

    moved, open_windows = [], []
    monkeypatch.setattr(controller.windows, "follow_windows", lambda *a: None)  # wie Windows/X11: selbst suchen
    monkeypatch.setattr(controller.windows, "list_windows", lambda: list(open_windows))
    monkeypatch.setattr(controller.windows, "move_window",
                        lambda wid, out, rect, full=False: moved.append((wid, out, rect, full)))
    controller.start_airplay()
    pump()
    assert controller.mode == "desktop" and controller.desktop_note.startswith("iPhone/iPad")
    assert _until(lambda: controller.airplay.running() and log.exists(), 5)
    assert "-fs" in log.read_text() and "-vrtp" not in log.read_text()
    # UxPlay öffnet sein Fenster erst, wenn sich das iPhone verbindet – auch viel später
    controller._follow_timer.timeout.emit()
    assert moved == []
    open_windows.append(WindowInfo(id="0x1", title="AluPC", app="uxplay"))
    controller._follow_timer.timeout.emit()
    assert moved == [("0x1", "Zweit", (1920, 0, 1280, 720), True)]
    controller._follow_timer.timeout.emit()
    assert len(moved) == 1  # nicht dauernd neu schieben
    open_windows[:] = [WindowInfo(id="0x2", title="AluPC", app="uxplay")]  # neue Verbindung → neues Fenster
    controller._follow_timer.timeout.emit()
    assert moved[-1][0] == "0x2"
    open_windows[:] = [WindowInfo(id="0x9", title="AluPC Android", app="scrcpy")]
    assert not controller.cursor_should_stay_home()
    pump()
    assert window.t_airplay.active and not window.t_extend.active and not window.t_program.active
    controller.start_android()
    pump()
    assert controller.desktop_note.startswith("Android")
    assert _until(lambda: (tmp_path / "sc.txt").exists(), 5)
    assert "--window-x 1920" in (tmp_path / "sc.txt").read_text()
    assert _until(lambda: not controller.airplay.running(), 5)  # AirPlay-Fenster beendet
    controller._follow_timer.timeout.emit()
    assert moved[-1][0] == "0x9"
    controller.extend()
    assert controller._scrcpy is None and controller._handy_window == ""


def test_handy_page_airplay_settings(env, tmp_path):
    controller, window, _ = env
    controller.config["handy"] = {**controller.config["handy"], "uxplay_path": "", "scrcpy_path": ""}
    window.open_handy_window()
    pump()
    page = window.handy_page
    page.name.setText("Physikraum")
    page.pin_mode.setCurrentIndex(page.pin_mode.findData("fest"))
    page.pin.setText("2468")
    page._save_airplay()
    assert controller.config["handy"]["airplay_name"] == "Physikraum"
    assert controller.config["handy"]["pin"] == "2468"
    page.pin_mode.setCurrentIndex(page.pin_mode.findData("zufall"))
    assert controller.config["handy"]["pin"] == "zufall" and page.pin.isHidden()
    assert {"airplay", "handy_stream", "handy_remote", "miracast"} <= set(window.tiles)
    controller.start_airplay()  # UxPlay fehlt → nur Hinweis, nichts kaputt
    pump()


# ---------------------------------------------------------------- 0.12: Kamera-Optionen
def _quadrants(w=200, h=100):
    from PySide6.QtGui import QPainter

    img = QImage(w, h, QImage.Format_RGB32)
    p = QPainter(img)
    p.fillRect(0, 0, w // 2, h // 2, QColor("#ff0000"))       # oben links rot
    p.fillRect(w // 2, 0, w // 2, h // 2, QColor("#00ff00"))  # oben rechts grün
    p.fillRect(0, h // 2, w // 2, h // 2, QColor("#0000ff"))  # unten links blau
    p.fillRect(w // 2, h // 2, w // 2, h // 2, QColor("#ffff00"))  # unten rechts gelb
    p.end()
    return img


def test_camera_options_and_bar(env, monkeypatch):
    from PySide6.QtMultimedia import QVideoFrame

    from alupc.sources import CameraSource

    controller, window, _ = env
    cam = CameraSource({"device_id": "gibt-es-nicht", "name": "Test"})
    cam.device_id, cam.name = "testcam", "Testkamera"
    monkeypatch.setattr(controller, "cameras_on_output", lambda: [cam])
    cam.sink.setVideoFrame(QVideoFrame(_quadrants()))
    img = cam.image()
    assert img is not None and img.size().width() == 200

    def color(x, y):
        return cam.image().pixelColor(x, y).name()

    controller.set_camera_option("testcam", zoom=2.0, x=0.0, y=0.0)  # Ausschnitt oben links
    assert cam.image().width() == 100 and color(50, 25) == "#ff0000"
    opts = controller.config["camera"]["testcam"]
    assert opts["x"] == 0.25 and opts["y"] == 0.25  # am Rand begrenzt und gespeichert
    controller.set_camera_option("testcam", zoom=1.0, mirror=True)
    assert color(10, 10) == "#00ff00"  # gespiegelt: grün jetzt links
    controller.set_camera_option("testcam", mirror=False, rotate=90)
    assert cam.image().width() == 100 and cam.image().height() == 200
    assert color(90, 10) == "#ff0000"  # 90° gedreht: oben links wandert nach oben rechts

    # Leiste im Hauptfenster
    controller.reset_camera("testcam")
    bar = window.camera_bar
    bar.sync()
    assert not bar.isHidden() and bar.title.text() == "Testkamera"
    assert not bar.left.isEnabled()  # ohne Zoom nichts zu verschieben
    bar._zoom_by(2.0)
    assert cam.options()["zoom"] == 2.0 and bar.zoom.value() == 200 and bar.zoom_label.text() == "2,0×"
    assert bar.left.isEnabled()
    bar._pan(1, 0)
    assert cam.options()["x"] > 0.5
    bar._flip()
    assert cam.options()["mirror"] and bar.flip.isChecked()
    x = cam.options()["x"]
    bar._pan(1, 0)  # gespiegelt: „rechts“ im Bild ist links in der Kamera
    assert cam.options()["x"] < x
    bar._rotate()
    assert cam.options()["rotate"] == 90
    controller.camera_zoom(1.25)
    assert cam.options()["zoom"] == 2.5
    controller.run_command("kamera_zoom_aus")
    assert cam.options()["zoom"] == 1.0
    bar._reset()
    assert cam.options()["rotate"] == 0 and not cam.options()["mirror"]
    monkeypatch.undo()
    bar.sync()
    assert bar.isHidden()
    cam.deleteLater()


# ---------------------------------------------------------------- 0.12: AluCast (Handy per Browser)
def _free_tcp_port():
    import socket

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _http(method, url, body=None, headers=None, timeout=10):
    """Anfrage in einem Thread schicken und dabei Qt weiterlaufen lassen (Server meldet sich per Signal)."""
    import threading
    import urllib.error
    import urllib.request

    result = {}

    def run():
        req = urllib.request.Request(url, data=body, method=method, headers=headers or {})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                result["status"], result["body"] = r.status, r.read()
        except urllib.error.HTTPError as e:
            result["status"], result["body"] = e.code, e.read()
        except Exception as e:  # noqa: BLE001
            result["status"], result["body"] = 0, str(e).encode()

    t = threading.Thread(target=run)
    t.start()
    assert _until(lambda: not t.is_alive(), timeout + 2)
    pump(10)
    return result["status"], result["body"]


def test_alucast_end_to_end(env, tmp_path):
    import json

    controller, window, _ = env
    port = _free_tcp_port()
    controller.config["cast"] = {**controller.config["cast"], "port": port, "code": "123456"}
    controller.start_cast()
    pump()
    assert controller.cast.running() and controller.content == {"type": "cast"}
    assert controller.config["cast"]["autostart"] is False  # startet nicht ungefragt beim nächsten Mal
    view = controller.output.content
    assert view.qr().width() > 20
    img = view.grab().toImage()
    colors = {img.pixelColor(x, y).name() for x in range(0, img.width(), 8) for y in range(0, img.height(), 8)}
    assert "#ffffff" in colors and "#000000" in colors  # QR-Code ist zu sehen
    pump()
    assert window.t_remote.active and window.t_remote.badge == "LÄUFT"
    base = f"http://127.0.0.1:{port}"
    ok = {"X-AluPC-Code": "123456"}

    status, body = _http("GET", base + "/")
    assert status == 200 and b"AluCast" in body
    assert _http("GET", base + "/api/status")[0] == 403
    status, body = _http("GET", base + "/api/status", headers=ok)
    assert status == 200 and "Handy-Empfang" in json.loads(body)["now"]

    # Foto senden → erscheint auf Monitor 2 und liegt im Ordner „Vom Handy“
    png = tmp_path / "rot.png"
    q = QImage(40, 30, QImage.Format_RGB32)
    q.fill(QColor("#ff0000"))
    q.save(str(png))
    status, body = _http("POST", base + "/api/upload?name=Tafelbild.png", png.read_bytes(),
                         {**ok, "Content-Type": "image/png"})
    assert status == 200, body
    assert _until(lambda: (controller.content or {}).get("type") == "image")
    assert "Vom Handy" in controller.content["path"] and controller.content["path"].endswith("_Tafelbild.png")
    assert _http("POST", base + "/api/upload?name=virus.exe", b"MZ", {**ok, "Content-Type": "x/y"})[0] == 415

    # Text, Befehle
    assert _http("POST", base + "/api/text", json.dumps({"text": "Hallo Klasse"}).encode(), ok)[0] == 200
    assert _until(lambda: (controller.content or {}).get("text") == "Hallo Klasse")
    assert _http("POST", base + "/api/cmd", json.dumps({"cmd": "schwarz"}).encode(), ok)[0] == 200
    assert _until(lambda: controller.privacy)
    assert _http("POST", base + "/api/cmd", json.dumps({"cmd": "sperren"}).encode(), ok)[0] == 400
    assert _http("POST", base + "/api/link", json.dumps({"url": "kein link"}).encode(), ok)[0] == 400

    # Falsche Codes: nach 10 Versuchen 1 Minute gesperrt (auch für den richtigen Code)
    bad = {"X-AluPC-Code": "000000"}
    codes = [_http("GET", base + "/api/status", headers=bad)[0] for _ in range(11)]
    assert codes[:10] == [403] * 10 and codes[10] == 429
    assert _http("GET", base + "/api/status", headers=ok)[0] == 429

    controller.stop_cast()
    assert not controller.cast.running() and controller.config["cast"]["autostart"] is False
    assert _http("GET", base + "/", timeout=2)[0] == 0


def test_handy_page_cards_and_auto_setup(env, tmp_path, monkeypatch):
    import sys

    from alupc import handy
    controller, window, _ = env
    controller.config["cast"] = {**controller.config["cast"], "port": _free_tcp_port()}
    # Pfeil-Menü jeder Handy-Kachel führt zur Handy-Seite
    window._fill_handy_menu(window.handy_menus["airplay"], "airplay")
    window.handy_menus["airplay"].actions()[-1].trigger()
    pump()
    assert window.handy_window.isVisible()  # eigenes Fenster statt eigener Seite
    page = window.handy_page
    assert list(page.cards) == ["cast", "airplay", "android", "miracast"]
    assert page.cards["cast"].pill.text_ == "BEREIT" and page.cast_toggle.text() == "Starten"
    if not sys.platform.startswith("win"):
        assert page.cards["miracast"].pill.text_ == "NUR WINDOWS" and not page.mc_start.isEnabled()
    page._toggle_cast()
    assert controller.cast.running() and page.cards["cast"].pill.text_ == "LÄUFT"
    assert page.qr.pixmap().width() >= 80
    page._toggle_cast()
    assert not controller.cast.running()
    # Android: Handy per USB erkannt (adb-Ausgabe nachgestellt)
    page._android_found(handy.parse_adb_devices(
        "List of devices attached\nR58M123 device usb:1-1 product:beyond model:SM_G973F device:beyond\n"))
    if page._scrcpy():
        assert page.cards["android"].pill.text_ == "VERBUNDEN" and "SM G973F" in page.cards["android"].detail.text()
    # Automatisch einrichten: Plan wird ausgeführt, Name wird eindeutig
    ran = []
    monkeypatch.setattr(handy, "setup_plan", lambda cfg: [("scrcpy (Android) installieren", ["true"])])
    monkeypatch.setattr(handy, "run_plan", lambda plan, status=None: ran.append(plan) or [])
    controller.config["handy"] = {**controller.config["handy"], "airplay_name": "AluPC", "setup_done": False}
    page.run_setup()
    assert _until(lambda: ran and not page._setup_running, 5)
    assert controller.config["handy"]["airplay_name"].startswith("AluPC (")
    assert controller.config["handy"]["setup_done"] is True
    assert page.setup_btn.isVisible()  # Plan (nachgestellt) meldet weiter etwas → Knopf bleibt
    menu = window.handy_menus["handy_remote"]
    window._fill_handy_menu(menu, "handy_remote")
    texts = [a.text() for a in menu.actions()]
    assert texts[0] == "QR-Code auf Monitor 2 zeigen" and texts[-1].startswith("Einrichten und Hilfe")
    controller.start_miracast()  # Linux: nur Hinweis
    pump()


# ---------------------------------------------------------------- 0.12.1: Statuskarte mit Vorschau, Bedienung
def test_status_card_preview_and_stop(env):
    controller, window, _ = env
    window._go(0)
    controller.show_source({"type": "color", "color": "#00ff00"})
    pump()
    assert window.stop_btn.isVisible()
    window._update_preview()
    img = window.status_card.preview.image
    assert img is not None and img.pixelColor(img.width() // 2, img.height() // 2).green() > 200
    window.stop_btn.click()
    pump()
    assert controller.mode == "desktop" and not window.stop_btn.isVisible()
    window._update_preview()
    assert window.status_card.preview.image is None  # Erweitern: Symbol statt Bild
    shown = []
    controller.toggle_pip = lambda: shown.append(True)
    window.status_card.preview.clicked.disconnect()
    window.status_card.preview.clicked.connect(controller.toggle_pip)
    window.status_card.preview.clicked.emit()
    assert shown
    window.t_scenes.activated.emit()  # Kachel „Meine Szenen“ → Szenen-Seite
    assert window.stack.currentIndex() == 1


# ---------------------------------------------------------------- 0.13: Sichern & Sync
def test_sync_setup_and_autosave(env, tmp_path):
    import json

    from alupc import settings_sync as ss

    controller, window, _ = env
    shared = tmp_path / "Windows-C"
    shared.mkdir()
    window._go(2)
    pump()
    controller.config.data["sync"] = {**controller.config.data["sync"], "enabled": True,
                                      "folder": str(ss.folder_for(shared))}
    ss.folder_for(shared).mkdir()
    controller.config["start_page"] = {**controller.config["start_page"], "title": "Hallo Sync"}
    assert controller._sync_timer.isActive()  # Änderung → gleich abgleichen
    controller._sync_timer.stop()
    controller.run_sync()
    data = json.loads(ss.sync_file(ss.folder_for(shared)).read_text())
    assert data["data"]["start_page"]["title"] == "Hallo Sync" and data["rev"] == 1
    # Das „andere System“ schreibt eine neuere Fassung → wird übernommen und die Startseite neu gebaut
    data["rev"] = 5
    data["data"]["start_page"]["title"] = "Von Windows"
    ss.sync_file(ss.folder_for(shared)).write_text(json.dumps(data))
    rebuilt = []
    window.rebuild_start = lambda: rebuilt.append(True)
    controller.run_sync()
    assert controller.config["start_page"]["title"] == "Von Windows" and rebuilt
    assert not controller._sync_timer.isActive()  # Übernehmen löst keinen neuen Abgleich aus


# ---------------------------------------------------------------- 0.13: RGB & Lüfter
def test_hardware_page_rgb_and_fans(env, tmp_path, monkeypatch):
    import sys
    import time

    sys.path.insert(0, str(HERE))
    from fake_openrgb import FakeOpenRGB
    from test_logic import _fake_hwmon

    from alupc.platform import fans

    controller, window, _ = env
    fake = FakeOpenRGB(4)
    hw = _fake_hwmon(tmp_path / "hwmon")
    monkeypatch.setattr(fans, "HWMON", tmp_path / "hwmon")
    controller.config["rgb"] = {**controller.config["rgb"], "port": fake.port, "start_openrgb": False}
    window._go(2)  # RGB & Lüfter steckt jetzt im Setup
    from alupc.ui.setup_page import SetupPage

    setup = window.findChild(SetupPage)
    setup.nav.setCurrentRow([t for _i, t, _s in SetupPage.SECTIONS].index("RGB & Lüfter"))
    pump()
    page = window.findChild(__import__("alupc.ui.hardware_page", fromlist=["HardwarePage"]).HardwarePage)
    assert page is not None
    if sys.platform.startswith("win"):  # Windows: keine Lüfter-Schnittstelle → ehrlicher Hinweis
        assert "FanControl" in page.fan_status.label.text() and not page.pwm_rows
    else:
        assert "nct6798/SYSTIN" in page.temp_bars and page.temp_bars["nct6798/SYSTIN"].value == 41.5
        assert page.fan_labels["nct6798/Lüfter 1"].text() == "812 U/min"
        assert controller.config["fans"]["original"] == {"nct6798/pwm1": 5}  # Automatik-Modus gemerkt
        key, slider, auto = page.pwm_rows["hwmon3/pwm2"]
        slider.setValue(60)
        assert page.fan_request() == "hwmon3/pwm1=auto:5,hwmon3/pwm2=153"
        (hw / "temp1_input").write_text("83000\n")
        page._update_sensors()
        assert page.temp_bars["nct6798/SYSTIN"].value == 83.0
    # RGB: verbinden, Farbe wählen, Gerät abwählen, aus
    controller.rgb.connect_async()
    assert _until(lambda: controller.rgb.connected, 5)
    pump()
    assert "2 Geräte" in page.rgb_status.label.text() and page.devices_box.isVisibleTo(page)
    page._pick_color("#22c55e")
    time.sleep(0.2)
    assert fake.leds(0) == [(0x22, 0xC5, 0x5E)] * 6
    controller.rgb.update_settings(skip=["Tastatur K70"], brightness=50)
    time.sleep(0.2)
    assert fake.leds(0) == [(0x11, 0x62, 0x2F)] * 6 and fake.leds(1) == [(0x22, 0xC5, 0x5E)] * 6
    controller.run_command("rgb_aus")
    time.sleep(0.2)
    assert fake.leds(0) == [(0, 0, 0)] * 6 and page.mode_btns["aus"].isChecked()
    # Farbe folgt Monitor 2
    controller.show_source({"type": "color", "color": "#ff0000"})
    pump()
    controller.rgb.update_settings(mode="monitor2", brightness=100)
    for _ in range(12):
        controller.rgb._ambient_tick()
    time.sleep(0.2)
    r, g, b = fake.leds(0)[0]
    assert r > 200 and g < 40 and b < 40, (r, g, b)
    controller.rgb.shutdown()
    fake.close()


# ---------------------------------------------------------------- 0.14: bessere Handysteuerung
def test_phone_remote_preview_laser_and_flags(env):
    import json

    controller, window, _ = env
    port = _free_tcp_port()
    controller.config["cast"] = {**controller.config["cast"], "port": port, "code": "654321"}
    controller.config.put_scene({"name": "Mathe", "layout": "vollbild", "slots": [{"type": "color", "color": "#00ff00"}]})
    controller.start_cast()
    controller.show_source({"type": "scene", "scene": "Mathe"})
    pump()
    base, ok = f"http://127.0.0.1:{port}", {"X-AluPC-Code": "654321"}
    # Live-Bild: erst nach Abruf erzeugt (sonst keine Rechenzeit verschwenden)
    assert controller.cast.preview == b""
    assert _http("GET", base + "/api/preview", headers=ok)[0] == 204
    def green_preview():  # nach dem Übergang (Einblenden) ist die Szene grün
        controller._cast_tick()
        img = QImage.fromData(controller.cast.preview)
        return not img.isNull() and img.pixelColor(img.width() // 2, img.height() // 2).green() > 200

    assert _until(green_preview, 5)
    status, jpg = _http("GET", base + "/api/preview", headers=ok)
    assert status == 200 and jpg[:2] == b"\xff\xd8"
    assert _http("GET", base + "/api/preview")[0] == 403
    # Status mit aktiver Szene und Zuständen
    s = json.loads(_http("GET", base + "/api/status", headers=ok)[1])
    assert s["scene"] == "Mathe" and s["flags"]["schwarz"] is False and s["timer"]
    assert _http("POST", base + "/api/cmd", json.dumps({"cmd": "schwarz"}).encode(), ok)[0] == 200
    assert _until(lambda: controller.privacy)
    s = json.loads(_http("GET", base + "/api/status", headers=ok)[1])
    assert s["flags"]["schwarz"] is True
    assert _http("POST", base + "/api/cmd", json.dumps({"cmd": "timer_plus"}).encode(), ok)[0] == 200
    # Laserpointer per Finger
    assert _http("POST", base + "/api/laser", json.dumps({"x": 0.25, "y": 0.5}).encode(), ok)[0] == 200
    assert _until(lambda: controller.laser.point is not None and controller.laser.remote)
    assert abs(controller.laser.point.x() - 0.25 * controller.laser.width()) < 2
    assert _http("POST", base + "/api/laser", json.dumps({"up": True}).encode(), ok)[0] == 200
    assert _until(lambda: controller.laser.point is None and not controller.laser.remote)
    assert _http("POST", base + "/api/laser", json.dumps({"x": 3, "y": 0}).encode(), ok)[0] == 400
    sent = []
    import alupc.platform.keys as keys_mod

    orig = keys_mod.send
    keys_mod.send = lambda name: sent.append(name) or True
    try:
        assert _http("POST", base + "/api/cmd", json.dumps({"cmd": "taste:weiter"}).encode(), ok)[0] == 200
        assert _until(lambda: sent == ["weiter"])
        assert _http("POST", base + "/api/cmd", json.dumps({"cmd": "taste:alt+f4"}).encode(), ok)[0] == 400
    finally:
        keys_mod.send = orig
    assert _http("POST", base + "/api/laser", json.dumps({"x": "a"}).encode(), ok)[0] == 400
    controller.stop_cast()


# ---------------------------------------------------------------- 0.14.1: eigene Kacheln je Handy-Weg
def test_handy_tiles_start_each_way(env):
    from alupc.startpage import section_of

    controller, window, _ = env
    controller.config["cast"] = {**controller.config["cast"], "port": _free_tcp_port()}
    controller.config["handy"] = {**controller.config["handy"], "uxplay_path": "", "scrcpy_path": ""}
    assert all(section_of(k, {}) == "handy" for k in ("airplay", "handy_stream", "handy_remote", "miracast"))
    messages = []
    controller.message.connect(messages.append)
    window.t_remote.activated.emit()  # Handy-Steuerung: QR-Code auf Monitor 2
    pump()
    assert controller.cast.running() and controller.content == {"type": "cast"}
    assert window.t_remote.badge == "LÄUFT"
    if not controller.airplay.binary():
        window.t_airplay.activated.emit()
        assert any("UxPlay fehlt" in m for m in messages)
    window.t_miracast.activated.emit()
    pump()
    controller.stop_cast()
    pump()
    assert window.t_remote.badge == ""


# ---------------------------------------------------------------- 0.15: Spiegeln mit Rückfall, Diagnose
def test_mirror_falls_back_to_system_mirror(env, monkeypatch):
    controller, window, _ = env
    calls, msgs = [], []
    controller.message.connect(msgs.append)
    monkeypatch.setattr(controller.display, "available", lambda: True)
    monkeypatch.setattr(controller.display, "mirror", lambda main, out: calls.append((main, out)))
    monkeypatch.setattr(controller, "screens_overlap", lambda: False)
    controller.mirror()
    pump()
    content = controller.output.content
    if content is not None and hasattr(content, "no_signal"):  # Aufnahme läuft (noch) → 4 s ohne Bild nachstellen
        content.frames = 0
        content._no_signal("Die Aufnahme liefert kein Bild.")
    # sonst: Aufnahme ist schon beim Start gescheitert (z. B. Windows im Test) → Rückfall ist schon passiert
    assert _until(lambda: calls, 5)
    assert calls[0] == ("Haupt", "Zweit")
    assert any("spiegelt jetzt über" in m for m in msgs)
    assert controller.mode == "desktop" and controller.desktop_note.startswith("System-Spiegeln")
    controller.mirror()  # kommen Bilder, passiert nichts
    content2 = controller.output.content
    if content2 is not None and hasattr(content2, "no_signal"):
        content2.frames = 3
        content2._no_signal("x")
        assert len(calls) == 1


def test_diagnose_report(env):
    from alupc import diagnose

    controller, window, _ = env
    text = diagnose.report(controller, probe=False)
    for part in ("== Monitore ==", "Monitor 2 = Zweit", "== AirPlay", "== Android ==", "== Miracast ==",
                 "== RGB und Lüfter =="):
        assert part in text, part


# ---------------------------------------------------------------- 0.15: Ersteinrichtung
def test_first_run_wizard(env, monkeypatch):
    from alupc import handy
    from alupc.ui.first_run import FirstRunDialog

    controller, window, _ = env
    ran = []
    monkeypatch.setattr(handy, "setup_plan", lambda cfg: [("UxPlay und scrcpy installieren", ["x"])])
    monkeypatch.setattr(handy, "run_plan", lambda plan, status=None: ran.append(plan) or [])
    monkeypatch.setattr("alupc.diagnose.capture_probe", lambda c, s=3.0: "Methode qt, 0 Bilder in 3 s, KEIN Bild")
    from alupc.platform import autostart

    monkeypatch.setattr(autostart, "set_enabled", lambda on: ran.append(("autostart", on)))
    controller.config["handy"] = {**controller.config["handy"], "airplay_name": "AluPC"}
    controller.config["first_run_done"] = False
    dlg = FirstRunDialog(controller, window)
    dlg.show()
    dlg.start()
    assert _until(lambda: dlg.finished_all, 10)
    states = [row.icon.state for row, _ in dlg.steps]
    assert "run" not in states and "wait" not in states
    assert controller.config["first_run_done"] is True
    # Bildaufnahme liefert nichts → künftig über das Betriebssystem spiegeln
    assert controller.config["output"]["mirror_method"] == "system"
    assert controller.config["handy"]["airplay_name"].startswith("AluPC (")
    assert ran[0] == [("UxPlay und scrcpy installieren", ["x"])] and ("autostart", True) in ran
    assert dlg.go.text() == "Fertig"
    # Spiegeln nutzt jetzt direkt das System-Spiegeln
    calls = []
    monkeypatch.setattr(controller.display, "available", lambda: True)
    monkeypatch.setattr(controller, "system_mirror", lambda: calls.append(True))
    controller.mirror()
    assert calls
    dlg.close()


# ---------------------------------------------------------------- 0.15.2: Zeichnungen in Bild-in-Bild
def test_drawings_visible_in_pip_and_previews(env):
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QImage

    controller, window, _ = env
    controller.show_source({"type": "color", "color": "#00ff00"})
    pump(30)
    laser = controller.laser
    laser.begin_stroke("pen", "#ff0000", 0.05, QPointF(0.1, 0.5))  # dicker roter Strich quer durch die Mitte
    laser.extend_stroke(QPointF(0.9, 0.5))
    laser.end_stroke()
    pump()

    def red_in_middle(img):
        c = img.pixelColor(img.width() // 2, img.height() // 2)
        return c.red() > 180 and c.green() < 120, c.name()

    controller.toggle_pip()
    pump(10)
    controller.pip.refresh()
    ok, col = red_in_middle(controller.pip.view.image())
    assert ok, f"Bild-in-Bild zeigt die Zeichnung nicht ({col})"
    window._go(0)
    window._update_preview()
    ok, col = red_in_middle(window.status_card.preview.image)
    assert ok, f"Vorschau zeigt die Zeichnung nicht ({col})"
    ok, col = red_in_middle(QImage.fromData(controller._preview_jpeg()))
    assert ok, f"Handy-Bild zeigt die Zeichnung nicht ({col})"
    controller.toggle_privacy()  # bei „Schwarz“ keine Zeichnung zeigen
    pump(10)
    controller.pip.refresh()
    assert not red_in_middle(controller.pip.view.image())[0]
    controller.toggle_privacy()
    controller.toggle_pip()
    laser.clear_strokes()
