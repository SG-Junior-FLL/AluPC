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
    assert controller.transition_for({"type": "scene", "scene": "S"})[0] == "schnitt"


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


def test_laser_pointer(env):
    import time

    from PySide6.QtCore import QPoint

    controller, window, _ = env
    controller.show_source({"type": "color", "color": "#000000"})
    pump()
    controller.run_command("laserpointer")
    pump()
    laser = controller.laser
    assert laser.active and laser.isVisible()
    assert laser.geometry() == controller.output_screen().geometry()
    window.refresh()
    assert window.a_laser.isChecked()
    main, out = controller.main_screen().geometry(), controller.output_screen().geometry()
    # Maus in der Mitte von Monitor 1 → Punkt in der Mitte von Monitor 2
    target = laser.target_for(main.center())
    assert abs(target.x() - out.width() / 2) < 2 and abs(target.y() - out.height() / 2) < 2
    # Maus direkt auf Monitor 2 („Erweitern“) → Punkt genau dort
    assert laser.target_for(out.topLeft() + QPoint(10, 20)).toPoint() == QPoint(10, 20)
    from alupc.cursor import tracker

    tracker()._set(main.topLeft() + QPoint(main.width() // 4, main.height() // 4))
    laser._moved(tracker().pos)
    assert laser.point is not None and laser.trail
    img = laser.grab().toImage()
    p = laser.point.toPoint()
    assert img.pixelColor(p).red() > 200
    end = time.time() + 1
    while laser.trail and time.time() < end:
        pump()
    assert not laser.trail  # Leuchtspur verblasst
    from alupc.sources import screen_settings

    assert screen_settings["cursor"] is False  # Laser an → kein zusätzlicher Mauszeiger im Spiegelbild
    controller.run_command("laserpointer")
    assert not laser.active and not laser.isVisible()
    assert screen_settings["cursor"] is True


def test_laser_follows_mirrored_image_area(env):
    controller, _window, _ = env
    controller.mirror()
    pump()
    src = controller.output.content
    img = QImage(400, 400, QImage.Format_RGB32)  # quadratisch → links/rechts schwarze Ränder
    img.fill(QColor("#ffffff"))
    src._pending = None
    src._image = img
    controller.run_command("laserpointer")
    laser = controller.laser
    main, out = controller.main_screen().geometry(), controller.output_screen().geometry()
    left = laser.target_for(main.topLeft())
    assert abs(left.x() - (out.width() - out.height()) / 2) < 2  # linker Rand des Bildes, nicht des Monitors
    controller.run_command("laserpointer")
