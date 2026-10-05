"""„Wie das System“: Akzentfarbe aus Windows/KDE/GNOME, Hell/Dunkel live mitziehen, Titelleiste."""

import json

import pytest

from test_gui import env, pump  # noqa: F401 – gleiche Test-Umgebung wie die GUI-Tests

from alupc.ui import theme


@pytest.fixture()
def qapp():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_kde_accent_from_kdeglobals(tmp_path):
    f = tmp_path / "kdeglobals"
    f.write_text("[General]\nAccentColor=61,174,233\nColorScheme=BreezeDark\n", encoding="utf-8")
    assert theme._kde_accent(f) == "#3daee9"
    f.write_text("[Colors:Selection]\nBackgroundNormal=233,100,10\n", encoding="utf-8")
    assert theme._kde_accent(f) == "#e9640a"
    f.write_text("[General]\nAccentColor=kaputt\n", encoding="utf-8")
    assert theme._kde_accent(f) == ""
    assert theme._kde_accent(tmp_path / "fehlt") == ""


def test_gnome_accent_from_gsettings():
    assert theme._gnome_accent(lambda cmd: "'purple'\n") == theme.GNOME_ACCENTS["purple"]
    assert theme._gnome_accent(lambda cmd: "'unbekannt'\n") == ""


def test_system_accent_used_and_grey_falls_back(qapp, monkeypatch):
    monkeypatch.setattr(theme, "linux_desktop", lambda: "kde")
    monkeypatch.setattr(theme, "_kde_accent", lambda path=None: "#e9640a")
    monkeypatch.setattr("sys.platform", "linux")
    t = theme.make_theme("dunkel", "system")
    assert t.accent == "#e9640a" and t.accent2 != t.accent
    monkeypatch.setattr(theme, "_kde_accent", lambda path=None: "#808080")  # grau → Blau
    assert theme.make_theme("hell", "system").accent == theme.ACCENTS["blau"][1]


def test_old_default_blue_migrates_to_system(tmp_path):
    from alupc.config import Config

    p = tmp_path / "c.json"
    p.write_text(json.dumps({"appearance": {"mode": "dunkel", "accent": "blau"}}), encoding="utf-8")
    assert Config(p)["appearance"]["accent"] == "system"
    p.write_text(json.dumps({"appearance": {"accent": "blau", "accent_v2": True}}), encoding="utf-8")
    assert Config(p)["appearance"]["accent"] == "blau"  # bewusst gewählt → bleibt
    p.write_text(json.dumps({"appearance": {"accent": "gruen"}}), encoding="utf-8")
    assert Config(p)["appearance"]["accent"] == "gruen"
    assert Config(tmp_path / "neu.json")["appearance"]["accent"] == "system"


def test_title_bar_only_on_windows(qapp):
    from PySide6.QtWidgets import QWidget

    import sys

    w = QWidget()
    assert theme.title_bar(w) is (False if sys.platform != "win32" else theme.title_bar(w))


def test_follows_system_change_live(env, monkeypatch):  # noqa: F811
    controller, window, _ = env
    controller.config["appearance"] = {**controller.config["appearance"], "mode": "system", "accent": "system"}
    state = {"sig": (True, "#3daee9")}
    monkeypatch.setattr(theme, "system_signature", lambda: state["sig"])
    monkeypatch.setattr(theme, "system_accent", lambda: state["sig"][1])
    monkeypatch.setattr(theme, "system_prefers_dark", lambda: state["sig"][0])
    window._sys_timer.timeout.emit()
    window.apply_theme()
    assert theme.current().dark and theme.current().accent == "#3daee9"
    state["sig"] = (False, "#e9640a")  # Nutzer stellt Windows/KDE auf Hell + Orange
    window._sys_timer.timeout.emit()
    pump()
    assert not theme.current().dark and theme.current().accent == "#e9640a"


def test_system_swatch_in_setup(env):  # noqa: F811
    _, window, _ = env
    window.open_setup_section("Darstellung")
    pump()
    sw = window.setup._swatches
    assert list(sw)[0] == "system" and sw["system"].system and sw["system"].isChecked()
