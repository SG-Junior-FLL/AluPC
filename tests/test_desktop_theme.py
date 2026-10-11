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

    (tmp_path / "cfg" / "plasmarc").write_text("[Theme]\nname=default\n")
    (tmp_path / "cfg" / "plasma-org.kde.plasma.desktop-appletsrc").write_text(
        "[Containments][1][Wallpaper][org.kde.image][General]\nImage=file:///usr/share/wallpapers/Next/x.png\n")
    monkeypatch.setattr(dt, "wallpaper_path", lambda: tmp_path / "bg.png")
    run = lambda cmd, **k: (calls.append(cmd), R())[1]  # noqa: E731
    ok, msg = dt.apply(True, run=run, accent="gruen")
    assert ok and dt.active() and "Hintergrundbild" in msg
    assert ["plasma-apply-colorscheme", "AluPCDunkel"] in calls
    assert ["plasma-apply-desktoptheme", "breeze-dark"] in calls
    assert ["plasma-apply-wallpaperimage", str(tmp_path / "bg.png")] in calls and (tmp_path / "bg.png").is_file()
    green = (tmp_path / "data" / "color-schemes" / "AluPCDunkel.colors").read_text()
    assert "DecorationFocus=16,185,129" in green  # gewählte Akzentfarbe (Grün) statt AluPC-Blau
    assert (tmp_path / "data" / "color-schemes" / "AluPC.colors").is_file()
    ok, _ = dt.apply(False, run=run)  # zweimal anwenden: der ursprüngliche Stand bleibt gemerkt
    calls.clear()
    ok, msg = dt.restore(run=run)
    assert ok and not dt.active()
    assert calls == [["plasma-apply-colorscheme", "BreezeDark"], ["plasma-apply-desktoptheme", "default"],
                     ["plasma-apply-wallpaperimage", "/usr/share/wallpapers/Next/x.png"]]
    assert dt.restore(run=run)[0] is False
    calls.clear()  # nur Hintergrundbild
    assert dt.apply(False, run=run, colors=False, mode=False)[0]
    assert [c[0] for c in calls] == ["plasma-apply-wallpaperimage"]
    dt.restore(run=run)


def test_wallpaper_in_design_colors(qapp, tmp_path):
    from PySide6.QtGui import QColor, QImage

    for dark in (True, False):
        path = dt.render_wallpaper(dark, "rosa", (640, 360), tmp_path / f"w{dark}.png")
        img = QImage(str(path))
        assert (img.width(), img.height()) == (640, 360)
        light = sum(QColor(img.pixel(x, y)).lightness() for x in range(0, 640, 64) for y in range(0, 360, 60)) / 60
        assert (light < 110) == dark  # dunkles Design → dunkles Bild


def test_not_supported_without_plasma(monkeypatch):
    monkeypatch.setattr(dt, "IS_WINDOWS", False)
    monkeypatch.setattr(dt.shutil, "which", lambda name: None)
    ok, why = dt.apply(False)
    assert not ok and "KDE" in why


def test_windows_values(qapp):
    v = dt.windows_values("#4f6bef")
    assert v["AccentColor"] == 0xFFEF6B4F and v["AccentColorMenu"] == v["AccentColor"]
    assert len(v["AccentPalette"]) == 32 and v["AutoColorization"] == "0"
