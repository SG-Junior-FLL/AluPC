"""AluPC-Farben für den Desktop: KDE-Farbschema und Windows-Akzentfarbe, mit Zurück."""

import configparser
import sys

import pytest

from alupc import desktop_theme as dt


@pytest.fixture()
def qapp():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_kde_scheme_is_valid_and_branded(qapp):
    for dark in (False, True):
        cp = configparser.ConfigParser(interpolation=None)
        cp.optionxform = str
        cp.read_string(dt.kde_scheme(dark))
        for section in ("Colors:Window", "Colors:View", "Colors:Button", "Colors:Selection", "Colors:Tooltip",
                        "Colors:Header", "Colors:Complementary", "General", "WM"):
            assert section in cp, section
        for section in [s for s in cp.sections() if s.startswith("Colors:")]:
            for key in ("BackgroundNormal", "ForegroundNormal", "DecorationFocus"):
                parts = [int(x) for x in cp[section][key].split(",")]
                assert len(parts) == 3 and all(0 <= x <= 255 for x in parts)
        assert cp["General"]["ColorScheme"] == dt.SCHEMES[dark]
        r, g, b = (int(x) for x in cp["Colors:Selection"]["BackgroundNormal"].split(","))
        assert b > r and b > g  # Logo-Blau
        win = [int(x) for x in cp["Colors:Window"]["BackgroundNormal"].split(",")]
        assert (sum(win) < 120) == dark


@pytest.mark.skipif(sys.platform.startswith("win"), reason="KDE-Weg")
def test_kde_apply_and_restore(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    (tmp_path / "cfg").mkdir()
    (tmp_path / "cfg" / "kdeglobals").write_text("[General]\nColorScheme=BreezeDark\n")
    monkeypatch.setattr(dt, "_state_file", lambda: tmp_path / "state.json")
    monkeypatch.setattr(dt.shutil, "which", lambda name: "/usr/bin/" + name)
    calls = []

    class R:
        returncode, stdout, stderr = 0, "", ""

    run = lambda cmd, **k: (calls.append(cmd), R())[1]  # noqa: E731
    ok, msg = dt.apply(True, run=run)
    assert ok and calls[-1] == ["plasma-apply-colorscheme", "AluPCDunkel"] and dt.active()
    assert (tmp_path / "data" / "color-schemes" / "AluPC.colors").is_file()
    assert (tmp_path / "data" / "color-schemes" / "AluPCDunkel.colors").is_file()
    ok, _ = dt.apply(False, run=run)  # zweimal anwenden: das ursprüngliche Schema bleibt gemerkt
    ok, msg = dt.restore(run=run)
    assert ok and calls[-1] == ["plasma-apply-colorscheme", "BreezeDark"] and not dt.active()
    assert dt.restore(run=run)[0] is False


def test_not_supported_without_plasma(monkeypatch):
    monkeypatch.setattr(dt, "IS_WINDOWS", False)
    monkeypatch.setattr(dt.shutil, "which", lambda name: None)
    ok, why = dt.apply(False)
    assert not ok and "KDE" in why


def test_windows_values(qapp):
    v = dt.windows_values("#4f6bef")
    assert v["AccentColor"] == 0xFFEF6B4F and v["AccentColorMenu"] == v["AccentColor"]
    assert len(v["AccentPalette"]) == 32 and v["AutoColorization"] == "0"
