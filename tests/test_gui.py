"""Oberflächen-Test mit zwei virtuellen Monitoren (Qt „offscreen“), ohne echte Hardware."""

import os
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
os.environ["QT_QPA_PLATFORM"] = f"offscreen:configfile={HERE / 'offscreen_two_screens.json'}"

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


def test_commands_and_lock(env):
    controller, _window, _ = env
    controller.run_command("standbild")
    pump()
    controller.locked = True
    controller.run_command("schwarz")
    assert not controller.privacy  # gesperrt → nichts passiert
    controller.locked = False


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
