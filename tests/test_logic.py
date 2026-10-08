"""Tests der reinen Logik (ohne Bildschirm, ohne Hardware)."""

import ctypes
import json
import sys

import pytest

from alupc.config import Config
from alupc.platform.base import DisplayMode, Output, place, side_of
from alupc.platform.linux_display import kscreen_args, parse_kscreen_json, parse_xrandr, xrandr_args
from alupc.platform.linux_windows import build_kwin_script, parse_wmctrl
from alupc.scenes import LAYOUTS, creates_cycle, describe_source, layout_slots, new_scene, resize_slots

KSCREEN_JSON = {
    "outputs": [
        {
            "id": 1, "name": "eDP-1", "connected": True, "enabled": True, "priority": 1,
            "currentModeId": "2", "pos": {"x": 0, "y": 0}, "rotation": 1, "scale": 1.25,
            "modes": [
                {"id": "1", "name": "1920x1080@60", "refreshRate": 60.0, "size": {"width": 1920, "height": 1080}},
                {"id": "2", "name": "1920x1080@144", "refreshRate": 144.0, "size": {"width": 1920, "height": 1080}},
            ],
        },
        {
            "id": 2, "name": "HDMI-A-1", "connected": True, "enabled": True, "priority": 2,
            "currentModeId": "5", "pos": {"x": 1536, "y": 0}, "rotation": 8, "scale": 1,
            "modes": [
                {"id": "5", "name": "2560x1440@59.95", "refreshRate": 59.951, "size": {"width": 2560, "height": 1440}},
            ],
        },
        {"id": 3, "name": "DP-1", "connected": False, "enabled": False, "modes": []},
    ]
}

XRANDR = """Screen 0: minimum 320 x 200, current 3840 x 1080, maximum 16384 x 16384
HDMI-1 connected primary 1920x1080+0+0 (normal left inverted right x axis y axis) 527mm x 296mm
   1920x1080     60.00*+  50.00    59.94
   1280x720      60.00    50.00
DP-1 connected 1080x1920+1920+0 left (normal left inverted right x axis y axis) 527mm x 296mm
   1920x1080     74.97 +  60.00*
DP-2 disconnected (normal left inverted right x axis y axis)
HDMI-2 connected (normal left inverted right x axis y axis)
   1024x768      60.00 +
"""


def test_parse_kscreen():
    outs = parse_kscreen_json("kscreen.doctor: noise\n" + json.dumps(KSCREEN_JSON))
    assert [o.name for o in outs] == ["eDP-1", "HDMI-A-1"]
    edp, hdmi = outs
    assert edp.primary and not hdmi.primary
    assert edp.mode().refresh == 144.0
    assert hdmi.rotation == "right"
    assert hdmi.size() == (1440, 2560)
    assert edp.resolutions() == [(1920, 1080)]
    assert [m.refresh for m in edp.refresh_rates(1920, 1080)] == [144.0, 60.0]


def test_kscreen_args():
    outs = parse_kscreen_json(json.dumps(KSCREEN_JSON))
    args = kscreen_args(outs)
    assert "output.eDP-1.mode.2" in args
    assert "output.HDMI-A-1.position.1536,0" in args
    assert "output.eDP-1.scale.1.25" in args
    assert "output.HDMI-A-1.rotation.right" in args
    assert args[-1] == "output.eDP-1.primary"
    outs[1].enabled = False
    assert "output.HDMI-A-1.disable" in kscreen_args(outs)


def test_parse_xrandr_and_args():
    outs = parse_xrandr(XRANDR)
    assert [o.name for o in outs] == ["HDMI-1", "DP-1", "HDMI-2"]
    hdmi, dp, hdmi2 = outs
    assert hdmi.primary and hdmi.mode_id == "1920x1080@60.00"
    assert dp.rotation == "left" and dp.x == 1920 and dp.mode_id == "1920x1080@60.00"
    assert not hdmi2.enabled
    args = xrandr_args(outs)
    i = args.index("DP-1")
    assert args[i + 1:i + 9] == ["--mode", "1920x1080", "--rate", "60.00", "--pos", "1920x0", "--rotate", "left"]
    assert args[-2:] == ["HDMI-2", "--off"]


def _out(name, w, h, x=0, y=0, scale=1.0, primary=False):
    return Output(name=name, x=x, y=y, scale=scale, primary=primary, mode_id="m",
                  modes=[DisplayMode("m", w, h, 60.0)])


def test_place_sides():
    for side, expected in [("right", (1920, 0)), ("below", (0, 1080))]:
        outs = [_out("A", 1920, 1080, primary=True), _out("B", 1280, 720)]
        place(outs, "A", "B", side, False)
        assert (outs[1].x, outs[1].y) == expected
        assert side_of(outs, "A", "B") == side
    outs = [_out("A", 1920, 1080, primary=True), _out("B", 1280, 720)]
    place(outs, "A", "B", "left", False)
    # normalisiert: niemand hat negative Koordinaten
    assert (outs[1].x, outs[0].x) == (0, 1280)
    assert side_of(outs, "A", "B") == "left"


def test_place_logical_scale():
    outs = [_out("A", 1920, 1080, scale=1.5, primary=True), _out("B", 1920, 1080)]
    place(outs, "A", "B", "right", True)
    assert outs[1].x == 1280


def test_scenes_layouts():
    for key in LAYOUTS:
        for x, y, w, h, _name in layout_slots(key):
            assert 0 <= x < 1 and 0 <= y < 1 and 0 < w <= 1 and 0 < h <= 1
            assert x + w <= 1.0001 and y + h <= 1.0001
    scene = new_scene("A", "raster_2x2")
    assert len(scene["slots"]) == 4
    scene["slots"][0] = {"type": "text", "text": "x"}
    smaller = resize_slots(scene, "nebeneinander")
    assert len(smaller["slots"]) == 2 and smaller["slots"][0]["text"] == "x"


def test_scene_cycles():
    scenes = [
        {"name": "A", "slots": [{"type": "scene", "scene": "B"}]},
        {"name": "B", "slots": [{"type": "scene", "scene": "C"}]},
        {"name": "C", "slots": [None]},
    ]
    assert creates_cycle(scenes, "C", "A")  # A enthält (über B) C
    assert not creates_cycle(scenes, "A", "C")


def test_describe_source():
    assert describe_source(None) == "(leer)"
    assert describe_source({"type": "website", "url": "x.de"}) == "Website: x.de"


def test_config_roundtrip_and_rename(tmp_path):
    path = tmp_path / "config.json"
    cfg = Config(path)
    cfg.put_scene({"name": "Innen", "layout": "vollbild", "slots": [{"type": "text", "text": "t"}]})
    cfg.put_scene({"name": "Außen", "layout": "vollbild", "slots": [{"type": "scene", "scene": "Innen"}]})
    cfg.put_scene({"name": "Neu", "layout": "vollbild", "slots": [{"type": "text", "text": "t"}]}, old_name="Innen")
    again = Config(path)
    assert again.scene_names() == ["Neu", "Außen"]
    assert again.get_scene("Außen")["slots"][0]["scene"] == "Neu"
    assert again["hotkeys"]["standbild"] == "Ctrl+Alt+S"


def test_config_corrupt_file(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{kaputt", encoding="utf-8")
    cfg = Config(path)
    assert cfg["scenes"] == []
    assert (tmp_path / "config.defekt.json").exists()


def test_wmctrl_and_kwin():
    text = ("0x03a00003  0 firefox.Firefox  host Meine Seite - Firefox\n"
            "0x01000007 -1 plasmashell.plasmashell  host Desktop\n")
    wins = parse_wmctrl(text)
    assert len(wins) == 1 and wins[0].title == "Meine Seite - Firefox" and wins[0].app == "Firefox"
    script = build_kwin_script('HDMI-"1', (1920, 0, 1920, 1080), True)
    assert 'var targetName = "HDMI-\\"1";' in script
    assert "var fullscreen = true;" in script


@pytest.mark.skipif(ctypes.sizeof(ctypes.c_wchar) != 2, reason="nur mit 2-Byte-WCHAR (Windows) sinnvoll")
def test_windows_structs_have_correct_size():
    from alupc.platform.windows_display import DEVMODEW, DISPLAY_DEVICEW
    from alupc.platform.windows_fingerprint import WINBIO_IDENTITY, WINBIO_UNIT_SCHEMA

    assert ctypes.sizeof(DEVMODEW) == 220
    assert ctypes.sizeof(DISPLAY_DEVICEW) == 840
    assert ctypes.sizeof(WINBIO_IDENTITY) == 76
    assert ctypes.sizeof(WINBIO_UNIT_SCHEMA) == 5 * 4 + 5 * 512 + 8


def test_startpage_order():
    from alupc.startpage import BUILTIN_TILES, DEFAULT_ORDER, all_keys, custom_key, ordered_keys, section_of

    cfg = {"tiles": None, "custom": [{"id": "a1", "title": "X", "section": "schnell"}]}
    assert ordered_keys(cfg) == DEFAULT_ORDER + ["custom:a1"]
    cfg["tiles"] = ["camera", "gibts-nicht", "mirror"]
    cfg["seen"] = list(DEFAULT_ORDER)
    keys = ordered_keys(cfg)
    assert keys == ["camera", "mirror", "custom:a1"]  # unbekannte weg, neue eigene hinten dran
    full = all_keys(cfg)
    assert full[:3] == keys and set(full) == set(BUILTIN_TILES) | {"custom:a1"}  # auch ausgeblendete wählbar
    assert "freeze" not in DEFAULT_ORDER  # Schwarz/Standbild/PiP sind Schalter beim Live-Bild
    assert section_of("freeze", cfg) == "schnell"
    assert section_of(custom_key(cfg["custom"][0]), cfg) == "schnell"


def test_scene_rename_moves_hotkey_and_tiles(tmp_path):
    cfg = Config(tmp_path / "c.json")
    cfg.put_scene({"name": "Alt", "layout": "vollbild", "slots": [{"type": "clock"}]})
    cfg.data["hotkeys"]["szene:Alt"] = "Ctrl+Alt+1"
    cfg.data["start_page"]["custom"] = [{"id": "k", "action": {"kind": "source",
                                                               "source": {"type": "scene", "scene": "Alt"}}}]
    cfg.put_scene({"name": "Neu", "layout": "vollbild", "slots": [{"type": "clock"}]}, old_name="Alt")
    assert cfg["hotkeys"].get("szene:Neu") == "Ctrl+Alt+1" and "szene:Alt" not in cfg["hotkeys"]
    assert cfg["start_page"]["custom"][0]["action"]["source"]["scene"] == "Neu"
    cfg.delete_scene("Neu")
    assert "szene:Neu" not in cfg["hotkeys"]


def test_new_default_hotkeys_merge_into_old_config(tmp_path):
    path = tmp_path / "c.json"
    path.write_text(json.dumps({"hotkeys": {"standbild": "Ctrl+Alt+X"}}), encoding="utf-8")
    cfg = Config(path)
    assert cfg["hotkeys"]["standbild"] == "Ctrl+Alt+X"  # eigene Einstellung bleibt
    assert cfg["hotkeys"]["bildschirmschoner"] == "Ctrl+Alt+W"  # neue Standardwerte kommen dazu
    assert cfg["screensaver"]["style"] == "uhr"


def test_normalize_url():
    from alupc.sources import normalize_url

    assert normalize_url(" beispiel.de ") == "https://beispiel.de"
    assert normalize_url("http://x.de") == "http://x.de"
    assert normalize_url("data:text/html,<b>x</b>") == "data:text/html,<b>x</b>"
    assert normalize_url("about:blank") == "about:blank"
    assert normalize_url("") == ""


# ---------------------------------------------------------------- 0.6: Linux-Einrichtung
def _usb(root, name, vendor, product, label=""):
    d = root / name
    d.mkdir(parents=True)
    (d / "idVendor").write_text(vendor + "\n")
    (d / "idProduct").write_text(product + "\n")
    if label:
        (d / "product").write_text(label + "\n")


def test_detect_usb_fingerprint_sensors(tmp_path):
    from alupc.platform.linux_fingerprint import detect_usb_sensors

    _usb(tmp_path, "1-1", "27c6", "538c", "Goodix USB2.0 MISC")
    _usb(tmp_path, "1-2", "046d", "c52b", "USB Receiver")  # Maus-Empfänger
    _usb(tmp_path, "1-3", "04f3", "0c4b")  # Elan-Fingerabdruck
    _usb(tmp_path, "1-4", "04f3", "2a1c", "Touchscreen")  # Elan-Touchscreen → nein
    _usb(tmp_path, "1-5", "abcd", "0001", "Fingerprint Reader")
    found = detect_usb_sensors(tmp_path)
    labels = [f[0] for f in found]
    assert len(found) == 3
    assert "27c6:538c" in labels[0] and "Goodix" in labels[0]
    assert "libfprint-2-tod1-goodix" in found[0][1]
    assert any("04f3:0c4b" in x for x in labels)
    assert not any("2a1c" in x or "c52b" in x for x in labels)
    assert detect_usb_sensors(tmp_path / "gibtsnicht") == []


def test_desktop_entry_and_icons(tmp_path):
    from alupc.platform import linux_desktop

    text = linux_desktop.desktop_entry("/opt/alupc/AluPC")
    assert "Exec=/opt/alupc/AluPC\n" in text
    assert "Exec=/opt/alupc/AluPC --befehl standbild" in text
    assert "X-KDE-DBUS-Restricted-Interfaces=org.kde.KWin.ScreenShot2" in text
    assert "StartupWMClass=AluPC" in text
    assert 'Exec="/mein pfad/AluPC"' in linux_desktop.desktop_entry("/mein pfad/AluPC")
    changed = linux_desktop.install_files(tmp_path, "/x/AluPC")
    assert (tmp_path / "applications" / "alupc.desktop").exists()
    for size in linux_desktop.ICON_SIZES:
        assert (tmp_path / "icons" / "hicolor" / f"{size}x{size}" / "apps" / "alupc.png").exists()
    assert (tmp_path / "icons" / "hicolor" / "scalable" / "apps" / "alupc.svg").exists()
    assert len(changed) == len(linux_desktop.ICON_SIZES) + 2
    assert linux_desktop.install_files(tmp_path, "/x/AluPC") == []  # zweites Mal: nichts zu tun


def test_portable_registers_itself(tmp_path, monkeypatch):
    import sys

    from alupc.platform import linux_desktop

    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    monkeypatch.setattr(linux_desktop, "refresh_caches", lambda _p: None)
    monkeypatch.setattr(linux_desktop, "system_installed", lambda: False)
    monkeypatch.delattr(sys, "frozen", raising=False)
    assert linux_desktop.ensure_user_entry() is False  # Quellcode: nichts eintragen
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert linux_desktop.ensure_user_entry() is True
    entry = (tmp_path / "applications" / "alupc.desktop").read_text()
    assert f"Exec={__import__('os').path.realpath(sys.executable)}" in entry
    assert linux_desktop.ensure_user_entry() is False
    # .deb installiert → alten Eintrag der portablen Version entfernen (würde den des .deb verdecken)
    monkeypatch.setattr(linux_desktop, "system_installed", lambda: True)
    (tmp_path / "applications" / "alupc.desktop").write_text(entry.replace("Exec=", "Exec=/alt"))
    assert linux_desktop.ensure_user_entry() is True
    assert not (tmp_path / "applications" / "alupc.desktop").exists()


# ---------------------------------------------------------------- 0.7: Maus, Laserpointer
def test_new_builtin_tiles_appear_after_update():
    from alupc.startpage import all_keys, ordered_keys

    old_saved = {"tiles": ["timer", "mirror"], "custom": []}  # Einstellungen von vor dem Update
    import sys

    # neu: „text“ 0.30, „nowplaying“ 0.46, „overlays“ 0.47, „whiteboard“ 0.61, „wetter“/„umfrage“/„zufall“ 0.68, „spiele“ 0.76, „system“ 0.82, „hotspot“ 0.97
    expected = ["timer", "mirror", "text", "nowplaying", "airplay", "handy_remote", "overlays", "whiteboard",
                "wetter", "system", "umfrage", "zufall", "spiele", "hotspot"]
    assert ordered_keys(old_saved) == expected, sys.platform
    from alupc.startpage import DEFAULT_ORDER

    hidden_on_purpose = {"tiles": ["timer", "mirror"], "custom": [], "seen": list(DEFAULT_ORDER)}
    assert ordered_keys(hidden_on_purpose) == ["timer", "mirror"]
    assert "draw" in all_keys({"tiles": None})  # ausgeblendet, aber wählbar (Zeichnen ist ein Schalter oben)


def test_barrier_lines():
    from alupc.platform.cursor_native import barrier_lines

    assert barrier_lines((1920, 0, 1280, 720)) == [
        (1920, 0, 1920, 720), (3200, 0, 3200, 720), (1920, 0, 3200, 0), (1920, 720, 3200, 720)]


def test_draw_hotkey_and_no_separate_laser():
    from alupc.config import DEFAULT_HOTKEYS, HOTKEY_LABELS
    from alupc.startpage import BUILTIN_TILES, COMMANDS

    assert "laserpointer" not in DEFAULT_HOTKEYS and "laser" not in BUILTIN_TILES  # Laser nur in „Zeigen & Zeichnen“
    assert DEFAULT_HOTKEYS["zeichnen"] == "Ctrl+Alt+K" and "zeichnen" in HOTKEY_LABELS and "zeichnen" in COMMANDS
    values = [v for v in DEFAULT_HOTKEYS.values() if v]
    assert len(values) == len(set(values))  # keine doppelten Standard-Kürzel


_KEEP: list = []


@pytest.mark.skipif(not sys.platform.startswith("win"), reason="nur Windows")
def test_windows_cursor_image_and_clip():
    from PySide6.QtGui import QGuiApplication

    if QGuiApplication.instance() is None:
        _KEEP.append(QGuiApplication([]))  # Qt-Anwendung am Leben halten
    from alupc.platform import cursor_native

    shape = cursor_native.cursor_image()  # darf None sein (z. B. Zeiger versteckt), aber nicht abstürzen
    if shape is not None:
        image, (hx, hy), _key = shape
        assert image.width() == 128 and 0 <= hx < 128 and 0 <= hy < 128
    assert cursor_native.clip_cursor(None) in (True, False)


def test_cheap_usb_sensors_are_named():
    import tempfile
    from pathlib import Path

    from alupc.platform.linux_fingerprint import detect_usb_sensors

    with tempfile.TemporaryDirectory() as tmp:
        _usb(Path(tmp), "3-1", "2541", "0236")  # Chipsailing CS9711 (günstige USB-Leser)
        found = detect_usb_sensors(Path(tmp))
    assert len(found) == 1 and "Chipsailing" in found[0][0] and "2541:0236" in found[0][0]
    assert "nicht unterstützt" in found[0][1] and "Windows" in found[0][1]


# ---------------------------------------------------------------- 0.10: Mediathek
def test_media_library(tmp_path):
    from alupc import media_library as lib

    cfg = Config(tmp_path / "c.json")
    a = {"type": "image", "path": str(tmp_path / "a.png")}
    v = {"type": "video", "path": str(tmp_path / "Urlaub.mp4"), "loop": True, "volume": 40}
    lib.remember(cfg, a)
    lib.remember(cfg, v)
    assert [i["title"] for i in lib.recent(cfg)] == ["Urlaub", "a"]  # neuestes zuerst, Titel = Dateiname
    lib.remember(cfg, a)  # erneut gezeigt → nach oben, nicht doppelt
    assert [i["title"] for i in lib.recent(cfg)] == ["a", "Urlaub"]
    lib.save(cfg, v, "Sommerfilm")
    assert lib.saved(cfg)[0]["title"] == "Sommerfilm" and lib.saved(cfg)[0]["volume"] == 40
    assert [i["title"] for i in lib.recent(cfg)] == ["a"]  # gespeichert → nicht mehr unter „Zuletzt“
    assert lib.is_saved(cfg, {"type": "video", "path": v["path"]})
    lib.save(cfg, {**v, "volume": 80})  # erneut speichern = aktualisieren, kein Duplikat
    assert len(lib.saved(cfg)) == 1 and lib.saved(cfg)[0]["volume"] == 80
    lib.rename(cfg, v, "Film")
    assert lib.saved(cfg)[0]["title"] == "Film"
    for i in range(20):
        lib.remember(cfg, {"type": "image", "path": str(tmp_path / f"{i}.png")})
    assert len(cfg["media"]["recent"]) == lib.RECENT_MAX
    lib.remove(cfg, v)
    assert lib.saved(cfg) == []
    assert lib.file_type("x.JPG") == "image" and lib.file_type("x.mkv") == "video" and lib.file_type("x.txt") is None
    lib.remember(cfg, {"type": "text", "text": "hallo"})  # keine Medien → nicht merken
    assert all(i["type"] == "image" for i in lib.recent(cfg))
    assert not lib.exists({"type": "image", "path": str(tmp_path / "fehlt.png")})


@pytest.mark.skipif(not sys.platform.startswith("win"), reason="nur Windows")
def test_windows_mouse_block_hook():
    from alupc.platform.cursor_native import MouseBlock

    block = MouseBlock()
    assert block.install((10000, 0, 1920, 1080), (0, 0, 1920, 1080))  # Hook lässt sich einhängen
    assert block.install((10000, 0, 1920, 1080), (0, 0, 1920, 1080))  # und erneut (Auffrischen)
    block.uninstall()
    assert block.hook is None and block.block is None


def test_tray_path_matching():
    from alupc.platform.windows_tray import _matches

    exe = r"C:\Program Files\AluPC\AluPC.exe"
    assert _matches(r"{6D809377-6AF0-444B-8957-A3773F02200E}\AluPC\AluPC.exe", exe)  # Ordner-GUID statt Pfad
    assert _matches(r"C:\PROGRAM FILES\ALUPC\ALUPC.EXE", exe)
    assert not _matches(r"C:\Python312\python.exe", exe)
    assert not _matches("", exe)


@pytest.mark.skipif(not sys.platform.startswith("win"), reason="nur Windows")
def test_tray_promote_runs():
    from alupc.platform.windows_tray import promote

    assert promote(r"C:\gibt\es\nicht\AluPC.exe") is False  # kein Eintrag → nichts ändern, kein Absturz


# ---------------------------------------------------------------- 0.12: Kamera-Optionen
def test_camera_zoom_math():
    from alupc.sources import clamp_center, pan_to_source, zoom_rect

    assert zoom_rect(1920, 1080, 1.0, 0.5, 0.5) == (0, 0, 1920, 1080)
    assert zoom_rect(1920, 1080, 2.0, 0.5, 0.5) == (480, 270, 960, 540)
    assert zoom_rect(1920, 1080, 2.0, 1.0, 0.0) == (960, 0, 960, 540)  # am Rand begrenzt
    assert zoom_rect(100, 100, 99, 0.5, 0.5)[2] == 20  # höchstens 5×
    assert clamp_center(2.0, 0.9, 0.1) == (0.75, 0.25)
    assert clamp_center(1.0, 0.9, 0.1) == (0.5, 0.5)
    assert pan_to_source(1, 0, 0, False) == (1, 0)
    assert pan_to_source(1, 0, 0, True) == (-1, 0)
    # 90° im Uhrzeigersinn gedreht: „rechts“ im Bild ist „oben“ in der Kamera
    assert pan_to_source(1, 0, 90, False) == (0, -1)
    assert pan_to_source(0, 1, 180, False) == (0, -1)
    assert pan_to_source(1, 0, 270, False) == (0, 1)


def test_best_camera_format():
    from alupc.sources import best_camera_format

    class F:
        def __init__(self, w, h, fps):
            self.w, self.h, self.fps = w, h, fps

        def resolution(self):
            from PySide6.QtCore import QSize

            return QSize(self.w, self.h)

        def maxFrameRate(self):
            return self.fps

    formats = [F(640, 480, 30), F(1920, 1080, 5), F(1280, 720, 30), F(3840, 2160, 30)]
    best = best_camera_format(formats)
    assert (best.w, best.h) == (1280, 720)  # Full HD nur mit 5 Bildern/s, 4K zu groß
    assert best_camera_format([F(1920, 1080, 5)]).w == 1920
    assert best_camera_format([]) is None


# ---------------------------------------------------------------- 0.12: AluCast
def test_alucast_helpers():
    from alupc.cast_server import new_code, safe_name, youtube_embed

    emb = "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ?autoplay=1&rel=0"
    assert youtube_embed("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == emb
    assert youtube_embed("https://youtu.be/dQw4w9WgXcQ?si=abc") == emb
    assert youtube_embed("https://m.youtube.com/watch?v=dQw4w9WgXcQ&t=42s") == emb + "&start=42"
    assert youtube_embed("https://youtube.com/shorts/dQw4w9WgXcQ") == emb
    assert youtube_embed("https://example.org/watch?v=x") == "https://example.org/watch?v=x"
    assert youtube_embed("https://www.youtube.com/watch?v=<script>") == "https://www.youtube.com/watch?v=<script>"
    name = safe_name("../../böse Datei.JPG", "image/jpeg")
    assert name.endswith("_böse_Datei.jpg") and "/" not in name
    assert safe_name("", "video/quicktime").endswith("_handy.mov")
    assert safe_name("x.exe", "application/x-msdownload").endswith("_x")  # keine Endung → wird abgelehnt
    assert len(new_code()) == 6 and new_code().isdigit()


# ---------------------------------------------------------------- 0.13: Sichern, Dual-Boot-Abgleich
def test_export_import_startpage(tmp_path):
    from alupc import settings_sync as ss
    from alupc.config import Config

    a = Config(tmp_path / "a.json")
    a["start_page"] = {**a["start_page"], "title": "Klasse 7b", "tiles": ["timer", "mirror"]}
    a.put_scene({"name": "Mathe", "layout": "vollbild", "slots": [None]})
    exported = ss.export_settings(a, ["startseite"])
    assert list(exported["data"]) == ["start_page"] and ss.sections_in(exported) == ["startseite"]
    path = tmp_path / "export.json"
    import json

    path.write_text(json.dumps(exported))
    b = Config(tmp_path / "b.json")
    changed = ss.import_settings(b, ss.read_export(path), ["startseite"])
    assert changed == ["start_page"] and b["start_page"]["title"] == "Klasse 7b"
    assert b.scene_names() == []  # nur die Startseite
    (tmp_path / "kaputt.json").write_text('{"app": "etwas anderes"}')
    try:
        ss.read_export(tmp_path / "kaputt.json")
        raise AssertionError("hätte abgelehnt werden müssen")
    except ValueError:
        pass


def test_dual_boot_sync(tmp_path):
    from alupc import settings_sync as ss
    from alupc.config import Config

    shared = tmp_path / "C" / ss.FOLDER_NAME
    win, lin = Config(tmp_path / "win.json"), Config(tmp_path / "lin.json")
    win["draw"] = {**win["draw"], "strokes": [{"points": [[0, 0]]}]}
    lin["draw"] = {**lin["draw"], "strokes": [], "strokes_for": "x"}
    lin["handy"] = {**lin["handy"], "uxplay_path": "/usr/bin/uxplay"}
    for cfg in (win, lin):
        cfg.data["sync"] = {**cfg.data["sync"], "enabled": True, "folder": str(shared)}
    shared.mkdir(parents=True)

    # Windows richtet ein und schreibt
    win["start_page"] = {**win["start_page"], "title": "Von Windows"}
    msg, _ = ss.sync_once(win)
    assert "Gespeichert" in msg and ss.sync_file(shared).is_file()
    # Linux verbindet sich zum ersten Mal → übernimmt (trotz eigener Standardwerte)
    msg, changed = ss.sync_once(lin)
    assert "Übernommen von" in msg and "start_page" in changed
    assert lin["start_page"]["title"] == "Von Windows"
    assert lin["handy"]["uxplay_path"] == "/usr/bin/uxplay"  # eigene Pfade bleiben
    assert lin["draw"]["strokes_for"] == "x"  # Zeichnungen sind nicht Teil des Abgleichs
    assert ss.sync_once(lin)[0] == "Alles aktuell."
    # Linux ändert → schreibt; Windows übernimmt beim nächsten Start
    lin["appearance"] = {**lin["appearance"], "accent": "gruen"}
    assert "Gespeichert" in ss.sync_once(lin)[0]
    msg, changed = ss.sync_once(win)
    assert changed == ["appearance"] and win["appearance"]["accent"] == "gruen"
    assert win["draw"]["strokes"] == [{"points": [[0, 0]]}]
    # Beide ändern (Laufwerk war nicht erreichbar) → eigene Änderung gewinnt, andere wird gesichert
    win["timer"] = {**win["timer"], "minutes": 7}
    ss.sync_once(win)
    lin["timer"] = {**lin["timer"], "minutes": 9}
    msg, _ = ss.sync_once(lin)
    assert "Sicherung" in msg and list(shared.glob("alupc-sync-sicherung-*.json"))
    assert ss.sync_once(win)[1] == ["timer"] and win["timer"]["minutes"] == 9
    # Beide ändern VERSCHIEDENES → zusammenführen, nichts geht verloren
    win["timer"] = {**win["timer"], "size": 40}
    ss.sync_once(win)
    lin["appearance"] = {**lin["appearance"], "accent": "rot"}
    msg, changed = ss.sync_once(lin)
    assert "Zusammengeführt" in msg and changed == ["timer"] and lin["timer"]["size"] == 40
    assert lin["appearance"]["accent"] == "rot"
    assert ss.sync_once(win)[1] == ["appearance"] and win["appearance"]["accent"] == "rot"
    assert win["timer"]["size"] == 40
    # Ordner woanders eingehängt (Linux: anderer Pfad) → vorhandenen Sync-Ordner wiederfinden
    moved = tmp_path / "D" / ss.FOLDER_NAME
    moved.parent.mkdir()
    shared.rename(moved)
    lin.data["sync"]["folder"] = str(tmp_path / "gibtsnicht")
    import alupc.settings_sync as mod

    old = mod.drives
    mod.drives = lambda: [str(tmp_path / "D")]
    try:
        assert "nicht erreichbar" not in ss.sync_once(lin)[0] and lin["sync"]["folder"] == str(moved)
        # Ordner wirklich weg → verständliche Meldung, nichts kaputt
        mod.drives = lambda: []
        lin.data["sync"]["folder"] = str(tmp_path / "gibtsnicht")
        assert "nicht erreichbar" in ss.sync_once(lin)[0]
    finally:
        mod.drives = old


def test_sync_auto_setup(tmp_path, monkeypatch):
    """Das andere System hat schon einen Sync-Ordner → beim Start ohne Klicken verbinden (außer selbst abgeschaltet)."""
    from alupc import settings_sync as ss
    from alupc.config import Config

    shared = tmp_path / "C" / ss.FOLDER_NAME
    win = Config(tmp_path / "win.json")
    win.data["sync"] = {**win.data["sync"], "enabled": True, "folder": str(shared)}
    shared.mkdir(parents=True)
    win["timer"] = {**win["timer"], "minutes": 12}
    ss.sync_once(win)
    monkeypatch.setattr(ss, "drives", lambda: [str(tmp_path / "C")])
    lin = Config(tmp_path / "lin.json")
    assert ss.auto_setup(lin) == shared and lin["sync"]["enabled"]
    assert "start_page" not in ss.sync_once(lin)[1] and lin["timer"]["minutes"] == 12
    other = Config(tmp_path / "other.json")
    other.data["sync"] = {**other.data["sync"], "declined": True}
    assert ss.auto_setup(other) is None and not other["sync"]["enabled"]


def test_sync_ignores_clock_and_status_changes(tmp_path):
    """Nur echte Änderungen zählen – z. B. nicht die gespeicherte Statusmeldung selbst (keine Endlosschleife)."""
    from alupc import settings_sync as ss
    from alupc.config import Config

    shared = tmp_path / ss.FOLDER_NAME
    cfg = Config(tmp_path / "c.json")
    cfg.data["sync"] = {**cfg.data["sync"], "enabled": True, "folder": str(shared)}
    shared.mkdir()
    ss.sync_once(cfg)
    rev = cfg["sync"]["base_rev"]
    cfg["last_content"] = {"type": "clock"}  # nicht abgeglichen
    cfg["output_screen"] = "DP-2"
    assert ss.sync_once(cfg)[0] == "Alles aktuell." and cfg["sync"]["base_rev"] == rev
    assert ss.folder_for(tmp_path) == tmp_path / ss.FOLDER_NAME and ss.folder_for(shared) == shared


# ---------------------------------------------------------------- 0.13: RGB (OpenRGB-SDK)
def test_openrgb_client_all_versions():
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).parent))
    from fake_openrgb import FakeOpenRGB

    from alupc.rgb import OpenRGB, hex_to_rgb, vivid

    for server_version, silent in ((4, False), (6, False), (3, False), (2, False), (0, True)):
        fake = FakeOpenRGB(server_version, silent_version=silent)
        client = OpenRGB(port=fake.port, timeout=2)
        devices = client.connect()
        assert client.version == min(4, server_version), server_version
        assert fake.used_version == (client.version if client.version >= 1 else 0)
        assert [d.name for d in devices] == ["ASUS Mainboard", "Tastatur K70"]
        assert [d.num_leds for d in devices] == [6, 6] and devices[1].kind == "Tastatur"
        assert devices[0].zones == [("Aura", 4), ("Header", 2)] and devices[0].modes[0] == "Direct"
        assert (devices[0].vendor == "Hersteller") == (client.version >= 1)
        assert fake.client_name == b"AluPC\0"
        client.set_color((255, 0, 128))
        client.set_color((0, 255, 0), devices=[1])
        import time

        time.sleep(0.2)
        assert fake.leds(0) == [(255, 0, 128)] * 6 and fake.leds(1) == [(0, 255, 0)] * 6
        assert sum(1 for d, pid, _ in fake.received if pid == 1100) == 2  # je Gerät einmal „Direkt“
        client.close()
        fake.close()
    assert hex_to_rgb("#ff8000", 50) == (128, 64, 0)
    assert vivid((200, 100, 100))[0] == 255 and vivid((3, 3, 3)) == (0, 0, 0)
    assert vivid((120, 118, 121)) == (121, 121, 121)


def test_openrgb_not_running():
    from alupc.rgb import OpenRGB, RGBError

    import socket

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    try:
        OpenRGB(port=port, timeout=1).connect()
        raise AssertionError("müsste fehlschlagen")
    except RGBError as exc:
        assert "SDK-Server" in str(exc)


# ---------------------------------------------------------------- 0.13: Lüfter (Linux hwmon)
def _fake_hwmon(root):
    hw = root / "hwmon3"
    hw.mkdir(parents=True)
    for name, value in {"name": "nct6798", "temp1_input": "41500", "temp1_label": "SYSTIN", "temp2_input": "55000",
                        "fan1_input": "812", "fan2_input": "0", "pwm1": "128", "pwm1_enable": "5",
                        "pwm2": "255", "pwm2_enable": "1"}.items():
        (hw / name).write_text(value + "\n")
    (root / "hwmon0").mkdir()
    (root / "hwmon0" / "name").write_text("k10temp\n")
    (root / "hwmon0" / "temp1_input").write_text("62125\n")
    return hw


def test_fans_read_and_set(tmp_path):
    from alupc.platform import fans

    hw = _fake_hwmon(tmp_path)
    chips = fans.read_sensors(tmp_path)
    assert [c.name for c in chips] == ["AMD-Prozessor", "Mainboard (nct6798)"]
    board = chips[1]
    assert board.temps == [("SYSTIN", 41.5), ("Temperatur 2", 55.0)]
    assert board.fans == [("Lüfter 1", 812), ("Lüfter 2", 0)]
    assert [(p.id, p.percent, p.automatic) for p in board.pwms] == [("hwmon3/pwm1", 50, True),
                                                                     ("hwmon3/pwm2", 100, False)]
    # Setzen: nie unter 30 %, „auto“ stellt den gemerkten Modus wieder her
    assert fans.apply_request("hwmon3/pwm1=10,hwmon3/pwm2=auto:5", tmp_path) == 0
    assert (hw / "pwm1").read_text() == "77" and (hw / "pwm1_enable").read_text() == "1"
    assert (hw / "pwm2_enable").read_text() == "5"
    # Alles Unerwartete wird abgelehnt (läuft als Administrator!)
    for bad in ("../../etc/passwd=1", "hwmon3/pwm1=999", "hwmon3/pwm1=-1", "hwmon3/pwm1=auto:1",
                "hwmon3/temp1_input=5", "hwmon3/pwm1=12;rm", ""):
        assert fans.apply_request(bad, tmp_path) == 2, bad
    assert fans.apply_request("hwmon9/pwm1=200", tmp_path) == 1  # gibt es nicht
    cmd = fans.helper_command("hwmon3/pwm1=100")
    assert cmd[0] == "pkexec" and cmd[-2:] == ["--luefter", "hwmon3/pwm1=100"]


# ---------------------------------------------------------------- 0.14: Handy automatisch einrichten
def test_handy_setup_plan(monkeypatch, tmp_path):
    from alupc import handy
    from alupc.config import Config

    cfg = Config(tmp_path / "c.json")
    monkeypatch.setattr(handy, "find_program", lambda name, configured="", extra=None: None)
    monkeypatch.setattr(handy, "can_install", lambda: True)
    monkeypatch.setattr(handy, "missing_packages", lambda pkgs: list(pkgs))
    monkeypatch.setattr(handy, "avahi_running", lambda: False)
    monkeypatch.setattr(handy, "windows_firewall_ok", lambda: True)  # Windows-CI: Freigabe nicht mitprüfen
    cfg["handy"] = {**cfg["handy"], "firewall_version": handy.FIREWALL_VERSION}  # Windows-Firewall schon erledigt
    plan = handy.setup_plan(cfg)
    assert len(plan) == 1, plan  # alles in EINEM Schritt → nur eine Passwortabfrage
    label, cmd = plan[0]
    assert "UxPlay installieren" in label and "avahi" in label and "Firewall" in label
    assert cmd[:3] == ["pkexec", "sh", "-c"]
    assert "uxplay" in cmd[3] and "scrcpy" not in cmd[3] and "gstreamer1.0-libav" in cmd[3] and "avahi-daemon" in cmd[3]
    # Alles da und eingerichtet → nichts zu tun
    monkeypatch.setattr(handy, "missing_packages", lambda pkgs: [])
    monkeypatch.setattr(handy, "avahi_running", lambda: True)
    cfg["handy"] = {**cfg["handy"], "firewall_done": True, "firewall_version": handy.FIREWALL_VERSION}
    assert handy.setup_plan(cfg) == []
    monkeypatch.setattr(handy, "can_install", lambda: False)
    monkeypatch.setattr(handy, "can_winget", lambda: True)
    monkeypatch.setattr(handy, "bonjour_installed", lambda: False)
    monkeypatch.setattr(handy, "find_uxplay_windows", lambda configured="": None)
    plan = handy.setup_plan(cfg)
    assert [p[1][3] for p in plan] == ["Apple.Bonjour", "leapbtw.uxplay"]
    monkeypatch.setattr(handy, "find_uxplay_windows", lambda configured="": r"C:\x\uxplay-windows.exe")
    monkeypatch.setattr(handy, "bonjour_installed", lambda: True)
    assert handy.setup_plan(cfg) == []
    import sys

    errors = handy.run_plan([("Test ok", [sys.executable, "-c", "pass"]),
                             ("Test kaputt", [sys.executable, "-c", "raise SystemExit(1)"])])
    assert errors == ["Test kaputt: fehlgeschlagen"]
    assert handy.default_airplay_name().startswith("AluPC")


# ---------------------------------------------------------------- 0.15: AirPlay wirklich zum Laufen bringen
def test_airplay_setup_script_and_errors():
    from alupc import handy
    from alupc.platform.linux_windows import build_follow_script

    script = handy.linux_setup_script(["uxplay", "gstreamer1.0-libav"], True, 8765)
    assert "apt-get -o DPkg::Lock::Timeout=600 install -y uxplay gstreamer1.0-libav" in script
    assert "systemctl enable --now avahi-daemon" in script
    assert "ufw allow 7000:7001/tcp" in script and "ufw allow 8765/tcp" in script and "ufw allow 5353/udp" in script
    assert handy.linux_setup_script([], False, None) == "set -e\nexport DEBIAN_FRONTEND=noninteractive"
    import sys

    expected = "Bonjour" if sys.platform.startswith("win") else "avahi"
    assert expected in handy.explain_uxplay_error(["*** ERROR: No DNS-SD Server found"])
    assert "GStreamer" in handy.explain_uxplay_error(["*** ERROR: Failed to initialize GStreamer video renderer"])
    assert "unknown option" in handy.explain_uxplay_error(['unknown option -x, stopping'])
    assert "-p" in handy.uxplay_args("A", "", None)  # feste Ports für die Firewall
    js = build_follow_script(["AluPC (PC)", "UxPlay"], "HDMI-A-1", (1920, 0, 1280, 720))
    assert '["AluPC (PC)", "UxPlay"]' in js and "windowAdded" in js and "captionChanged" in js


def test_uxplay_windows_control(monkeypatch, tmp_path):
    """Windows-AirPlay über „uxplay-windows“: AluPC schreibt Name/Code in dessen arguments.txt und startet es."""
    import os
    import stat
    import sys

    from alupc import handy
    from alupc.config import Config

    line = handy.uxplay_windows_command_line(["-n", "AluPC (Mein PC)", "-nh", "-p", "-pin", "1234"])
    assert line == '-n AluPC\u00a0(Mein\u00a0PC) -nh -p -pin 1234' and len(line.split(" ")) == 6
    assert "%" not in handy.uxplay_windows_command_line(["-n", "%USERNAME%"])
    assert handy.is_uxplay_windows(r"C:\Program Files\uxplay-windows\uxplay-windows.exe")
    assert not handy.is_uxplay_windows("/usr/bin/uxplay")
    assert handy.supports_vrtp(r"C:\nicht\da\uxplay-windows.exe") is False  # „-h“ würde das Tray-Programm starten
    monkeypatch.setenv("APPDATA", str(tmp_path / "roaming"))
    assert handy.uxplay_windows_arguments_file() == tmp_path / "roaming" / "leapbtw" / "uxplay-windows" / "arguments.txt"
    if sys.platform.startswith("win"):
        return  # der Start eines Ersatzprogramms (Shell-Skript) geht nur unter Linux
    fake = tmp_path / "uxplay-windows" / "uxplay-windows.exe"
    fake.parent.mkdir()
    fake.write_text("#!/bin/sh\nsleep 30\n")
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    cfg = Config(tmp_path / "c.json")
    cfg["handy"] = {**cfg["handy"], "uxplay_path": str(fake), "airplay_name": "AluPC (Test)", "pin": "zufall"}
    server = handy.AirPlayServer(cfg)
    assert server.binary() == str(fake)
    assert server.acquire(want_stream=True) == "fenster"  # uxplay-windows zeigt immer ein eigenes Fenster
    assert server.proc.waitForStarted(5000) and server.running()
    text = handy.uxplay_windows_arguments_file().read_text(encoding="utf-8")
    assert text.startswith('-n AluPC\u00a0(Test) -nh -p -pin ') and len(server.pin_code) == 4
    assert text.endswith(server.pin_code)  # zufälliger Code, den AluPC anzeigen kann
    server.shutdown()
    assert not server.running()
    assert os.path.exists(fake)


def test_presentation_keys():
    from alupc.platform import keys

    assert set(keys.KEYS) >= {"weiter", "zurueck", "start", "ende", "schwarz"}
    try:
        keys.send("rm -rf")
        raise AssertionError("unbekannte Taste muss abgelehnt werden")
    except ValueError:
        pass


def test_cast_address_choice(monkeypatch):
    """QR-Code: WLAN-Adresse statt virtueller Netze (WSL/Hyper-V/VPN), die ein Handy nie erreicht."""
    from alupc import cast_server, handy

    route = "172.22.0.1"
    wsl = cast_server.score_address("172.22.0.1", "vEthernet (WSL)", False, route)
    wlan = cast_server.score_address("192.168.178.20", "WLAN", True, route)
    vpn = cast_server.score_address("10.8.0.2", "Tailscale", False, route)
    assert wlan > wsl and wlan > vpn
    assert cast_server.score_address("169.254.1.2", "Ethernet", False, route) < 0
    monkeypatch.setattr(cast_server, "network_addresses",
                        lambda: [("192.168.178.20", "WLAN", 8), ("172.22.0.1", "vEthernet (WSL)", -8)])
    assert cast_server.local_ip() == "192.168.178.20"
    assert cast_server.local_ip("172.22.0.1") == "172.22.0.1"  # von Hand gewählt
    assert cast_server.local_ip("10.0.0.99") == "192.168.178.20"  # gewählte Adresse gibt es nicht mehr
    cmd = handy.windows_firewall_command(r"C:\AluPC\AluPC.exe", 8765)
    assert cmd[0] == "powershell" and "-Verb RunAs" in cmd[-1]
    assert "localport=8765-8774" in cmd[-1] and "localport=7000,7001,7100" in cmd[-1]
    # Handy-Steuerung nur privat; AirPlay für alle Netzwerktypen (Windows nennt WLANs oft „öffentlich“)
    assert "localport=8765-8774 profile=private,domain" in cmd[-1] and "7100 profile=any" in cmd[-1]
    monkeypatch.setattr(handy, "uxplay_programs", lambda: [r"C:\Program Files\uxplay-windows\uxplay-windows.exe"])
    cmd = handy.windows_firewall_command(r"C:\AluPC\AluPC.exe", 8765)
    assert 'delete rule name=all program="C:\\Program Files\\uxplay-windows\\uxplay-windows.exe"' in cmd[-1]
    assert 'name="AluPC AirPlay (UxPlay)" dir=in action=allow program=' in cmd[-1]


def test_iphone_window_not_browser():
    """Nur UxPlays Fenster ist das iPhone-Bild – kein Browser-Tab mit „AluPC“ oder „UxPlay“ im Titel."""
    from alupc.handy import is_iphone_window

    titles = ["AluPC", "AluPC", "UxPlay", "AirPlay Video"]
    # darf NICHT auf Monitor 2 wandern
    for title, app in [("AluCast – AluPC-Fernbedienung — Mozilla Firefox", "firefox"),
                       ("GitHub - SG-Junior-FLL/AluPC", "msedge.exe"),
                       ("AluPC", "chrome"),  # auch bei genau passendem Titel: Browser nie
                       ("UxPlay – Wikipedia", "Navigator"),
                       ("Releases · AluPC", ""),
                       ("uxplay-windows", "uxplay-windows"),  # dessen Einstellungsfenster
                       ("uxplay-windows log", "uxplay-windows"),
                       ("AluPC", "alupc")]:  # AluPCs eigene Fenster
        assert not is_iphone_window(title, app, titles), (title, app)
    # das echte iPhone-Fenster
    for title, app in [("AluPC", ""), ("AluPC", "uxplay"), ("AluPC\u00a0", "gst"),
                       ("Direct3D11 renderer", "uxplay-windows"), ("UxPlay", "")]:
        assert is_iphone_window(title, app, titles), (title, app)


def test_kwin_follow_script_exact_match():
    from alupc.platform.linux_windows import build_follow_script

    js = build_follow_script(["AluPC", "UxPlay"], "HDMI-1", (1920, 0, 1280, 720))
    assert "indexOf(titles[t])" not in js and "cap === " in js and "resourceClass" in js


def test_child_env_restores_system_libraries():
    """Fertige Linux-Version: UxPlay & Co. dürfen nicht AluPCs eigene (ältere) Bibliotheken erben (Exit-Code 127)."""
    from alupc.platform.child_env import restore_system_env

    env = {"LD_LIBRARY_PATH": "/opt/alupc/_internal", "LD_LIBRARY_PATH_ORIG": "/usr/local/lib", "PATH": "/usr/bin"}
    assert restore_system_env(env, frozen=True, platform="linux") == ["LD_LIBRARY_PATH"]
    assert env["LD_LIBRARY_PATH"] == "/usr/local/lib"
    env = {"LD_LIBRARY_PATH": "/opt/alupc/_internal"}  # vorher nicht gesetzt → ganz weg
    import sys as _sys

    old = getattr(_sys, "_MEIPASS", None)
    _sys._MEIPASS = "/opt/alupc/_internal"
    try:
        restore_system_env(env, frozen=True, platform="linux")
    finally:
        if old is None:
            del _sys._MEIPASS
        else:
            _sys._MEIPASS = old
    assert "LD_LIBRARY_PATH" not in env
    env = {"LD_LIBRARY_PATH": "/x"}
    assert restore_system_env(env, frozen=False, platform="linux") == [] and env["LD_LIBRARY_PATH"] == "/x"
    assert restore_system_env({"LD_LIBRARY_PATH": "/x"}, frozen=True, platform="win32") == []


def test_kwin_place_script():
    from alupc.platform.linux_windows import build_place_script

    js = build_place_script("AluPC – Bild-in-Bild", 1500, 700, 400, 225)
    assert '"AluPC \\u2013 Bild-in-Bild"' in js or "AluPC – Bild-in-Bild" in js
    assert "frameGeometry = {x: 1500, y: 700, width: 400, height: 225}" in js and "keepAbove = true" in js


def test_kde_mirror_direction(monkeypatch):
    """KDE: Spiegeln legt ausdrücklich fest „Monitor 2 ist Kopie von Monitor 1“ (nicht umgekehrt);
    kennt KDE das nicht, bleibt der alte Weg über die Position."""
    import json

    from alupc.platform import linux_display

    calls = []
    state = {"src": 0, "mirror_ok": True}

    def fake_run(cmd, timeout=20):
        calls.append(cmd[1:])
        if cmd[1] == "-j":
            return json.dumps({"outputs": [
                {"id": 1, "name": "eDP-1", "connected": True, "enabled": True, "pos": {"x": 0, "y": 0},
                 "currentModeId": "1", "modes": [{"id": "1", "size": {"width": 1920, "height": 1080}}],
                 "replicationSource": 0},
                {"id": 2, "name": "HDMI-A-1", "connected": True, "enabled": True, "pos": {"x": 1920, "y": 0},
                 "currentModeId": "1", "modes": [{"id": "1", "size": {"width": 1920, "height": 1080}}],
                 "replicationSource": state["src"]}]})
        if "mirror" in cmd[1]:
            if not state["mirror_ok"]:
                raise RuntimeError("unbekannt")
            state["src"] = 1 if cmd[1].endswith(".eDP-1") else 0
        return ""

    monkeypatch.setattr(linux_display, "_run", fake_run)
    backend = linux_display.KScreenBackend()
    backend.mirror("eDP-1", "HDMI-A-1")
    assert calls[0] == ["output.HDMI-A-1.mirror.eDP-1"]  # Monitor 2 = Kopie von Monitor 1
    assert not any("position" in " ".join(c) for c in calls)  # kein Positions-Trick nötig
    # alte KDE-Version: Befehl unbekannt → Positions-Weg, und dabei wird nur Monitor 2 verschoben
    calls.clear()
    state.update(src=0, mirror_ok=False)
    applied = []
    monkeypatch.setattr(backend, "apply", lambda outs: applied.append({o.name: (o.x, o.y) for o in outs}))
    backend.mirror("eDP-1", "HDMI-A-1")
    assert applied and applied[-1]["eDP-1"] == (0, 0) and applied[-1]["HDMI-A-1"] == (0, 0)


def test_kde_main_monitor_from_priority():
    """KDE/Wayland: Monitor 1 = Priorität 1 in KDE – auch wenn Qt den anderen Monitor zuerst meldet."""
    import json

    from alupc.platform.linux_display import main_output_name

    def out(i, name, prio):
        return {"id": i, "name": name, "connected": True, "enabled": True, "priority": prio, "pos": {"x": 0, "y": 0}}

    assert main_output_name(json.dumps({"outputs": [out(1, "Virtual-2", 2), out(2, "Virtual-1", 1)]})) == "Virtual-1"
    assert main_output_name(json.dumps({"outputs": [out(1, "A", 0), out(2, "B", 0)]})) is None


def test_dual_boot_media_paths(tmp_path):
    """Szene unter Windows angelegt (C:\\…\\Video.MP4) → unter Linux auf dem eingehängten Windows-Laufwerk finden,
    auch bei anderer Groß-/Kleinschreibung; umgekehrt Linux-Pfad auf einem Windows-Laufwerk."""
    import os

    from alupc.platform import shared_paths as sp

    win = tmp_path / "Windows"
    video = win / "Users" / "Noah" / "Videos" / "Film.mp4"
    video.parent.mkdir(parents=True)
    video.write_bytes(b"x")
    other = tmp_path / "Daten"
    other.mkdir()
    roots = [str(other), str(win)]
    assert os.path.samefile(sp.resolve(r"C:\Users\Noah\Videos\Film.mp4", roots), video)
    assert os.path.samefile(sp.resolve(r"C:\users\noah\videos\FILM.MP4", roots), video)
    assert os.path.samefile(sp.resolve("/media/noah/OS/Users/Noah/Videos/Film.mp4", roots), video)
    assert sp.resolve(r"C:\Fehlt\x.mp4", roots) == r"C:\Fehlt\x.mp4"  # nicht da → unverändert
    assert sp.resolve("/home/noah/x.mp4", roots) == "/home/noah/x.mp4"  # Linux-Laufwerk: nicht erreichbar
    assert sp.resolve(str(video), []) == str(video)


def test_wayland_gap_keeps_mouse_home(monkeypatch):
    """KDE/Wayland: Maus auf Monitor 1 → Monitor 2 mit Lücke wegrücken; „Erweitern“ oder Maus auf Monitor 2
    → Lücke zu. Beim Anordnen bleibt Monitor 2 auf seiner Seite."""
    from PySide6.QtCore import QPoint, QRect

    from alupc import cursor
    from alupc.platform.base import DisplayBackend, DisplayMode, Output

    assert cursor.gap_between(QRect(0, 0, 1920, 1080), QRect(1920, 0, 1920, 1080)) == 0
    assert cursor.gap_between(QRect(0, 0, 1920, 1080), QRect(3920, 0, 1920, 1080)) == 2000

    class Fake(DisplayBackend):
        def __init__(self):
            mode = [DisplayMode("1", 1920, 1080, 60)]
            self.outs = [Output("A", x=1920, mode_id="1", modes=mode), Output("B", x=0, mode_id="1", modes=mode)]

        def available(self):
            return True

        def list_outputs(self):
            return [Output(o.name, x=o.x, y=o.y, mode_id="1", modes=o.modes) for o in self.outs]

        def apply(self, outputs):
            self.outs = outputs

    fake = Fake()
    fake.separate("A", "B", 2000)  # B lag links von A → bleibt links, mit Lücke
    pos = {o.name: o.x for o in fake.outs}
    assert pos["A"] - (pos["B"] + 1920) == 2000
    fake.join("A", "B")
    pos = {o.name: o.x for o in fake.outs}
    assert pos["A"] - (pos["B"] + 1920) == 0

    calls = []
    monkeypatch.setattr(cursor, "wayland_kde", lambda: True)
    import alupc.ui.util as util

    monkeypatch.setattr(util, "run_async", lambda fn, done=None, err=None: (calls.append(fn), fn(), done and done()))
    guard = cursor.CursorGuard()
    guard.display = fake
    guard.active = True
    guard.main_name, guard.out_name = "A", "B"
    guard.main_rect, guard.out_rect = QRect(1920, 0, 1920, 1080), QRect(0, 0, 1920, 1080)
    guard._wayland_pos(QPoint(2500, 500))  # Maus auf Monitor 1 → Lücke auf
    assert len(calls) == 1 and gap_ok(fake)
    guard.main_rect, guard.out_rect = QRect(3920, 0, 1920, 1080), QRect(0, 0, 1920, 1080)
    guard._wayland_pos(QPoint(100, 100))  # doch auf Monitor 2 (Tablett) → Lücke zu, damit sie zurück kann
    assert len(calls) == 2 and not gap_ok(fake)


def gap_ok(fake):
    pos = {o.name: o.x for o in fake.outs}
    return pos["A"] - (pos["B"] + 1920) >= 100



def test_uxplay_vm_options_and_disconnect():
    """VM: Software-Decoder + ohne Zeitstempel-Abgleich (sonst Ton ohne Bild) – aber nur Optionen, die die
    UxPlay-Version kennt. Trennen wird aus UxPlays Meldungen erkannt."""
    from alupc import handy
    from alupc.platform.linux_windows import build_follow_script

    new = "-avdec    Force software h264\n-vsync [x]Mirror mode\n"
    assert handy.vm_options(new) == ["-avdec", "-vsync", "no"]
    assert handy.vm_options("-avdec    Force software h264\n") == ["-avdec"]  # alte Version ohne -vsync
    assert handy.vm_options("") == []
    args = handy.uxplay_args("AluPC", "", None, extra=handy.vm_options(new))
    assert args[:4] == ["-n", "AluPC", "-nh", "-p"] and "-avdec" in args and args[args.index("-vsync") + 1] == "no"
    assert any("open connections: 0" in h for h in handy.DISCONNECT_HINTS)
    assert "activeWindow = w" in build_follow_script(["AluPC"], "HDMI-A-1", (1920, 0, 1920, 1080))


def test_now_playing_parsing():
    """„Läuft gerade“: Player-Namen, MPRIS-Daten (wie Spotify/Firefox sie liefern), Zeit weiterzählen."""
    import time

    from alupc import now_playing as np

    assert np.player_name("org.mpris.MediaPlayer2.spotify") == "Spotify"
    assert np.player_name("org.mpris.MediaPlayer2.firefox.instance_1_84") == "Firefox"
    assert np.player_name("Spotify.exe") == "Spotify"
    assert np.player_name("SpotifyAB.SpotifyMusic_zpdnekdrzrea0!Spotify") == "Spotify"
    assert np.player_name("MSEdge") == "Edge"
    assert np.fmt_time(65) == "1:05" and np.fmt_time(3725) == "1:02:05"
    props = {"PlaybackStatus": ("s", "Paused"), "Position": ("x", 5_000_000),
             "Metadata": ("a{sv}", {"xesam:title": ("s", "Song"), "xesam:artist": ("as", ["A", "B"]),
                                    "mpris:length": ("t", 90_000_000)})}
    t = np.track_from_mpris("org.mpris.MediaPlayer2.vlc", props)
    assert (t.title, t.artist, t.player, t.playing, t.length) == ("Song", "A, B", "VLC", False, 90)
    assert t.position_now() == 5  # pausiert → bleibt stehen
    # Titel fehlt, aber Datei-URL da (z. B. Video im Player) → Dateiname
    t2 = np.track_from_mpris("x", {"Metadata": {"xesam:url": ("s", "file:///m/Mein%20Film.mp4")}})
    assert t2.title == "Mein Film.mp4"
    assert np.track_from_mpris("x", {"Metadata": {}}) is None
    playing = np.Track(title="x", playing=True, position=10, length=12, stamp=time.monotonic() - 5)
    assert playing.position_now() == 12  # nie über das Ende hinaus


def test_reset_wipes_only_alupc_data(tmp_path, monkeypatch):
    """„Alle Daten löschen“: nur Ordner von AluPC, Autostart aus, Einstellungen werden danach nicht neu geschrieben."""
    from alupc import reset

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "cfg"))
    data = tmp_path / "cfg" / "AluPC"
    (data / "Vom Handy").mkdir(parents=True)
    (data / "config.json").write_text("{}")
    (data / "Vom Handy" / "foto.jpg").write_bytes(b"x")
    fremd = tmp_path / "fremd"
    fremd.mkdir()
    (fremd / "wichtig.txt").write_text("bleibt")
    autostart_calls = []
    monkeypatch.setattr("alupc.platform.autostart.set_enabled", lambda on: autostart_calls.append(on))
    assert all(reset.is_alupc_dir(d) for d in reset.data_dirs())
    problems = reset.wipe([data, fremd])
    assert not data.exists() and (fremd / "wichtig.txt").exists()
    assert autostart_calls == [False] and problems == [f"{fremd}: übersprungen"]

    config = Config(tmp_path / "cfg" / "AluPC" / "config.json")
    config.frozen = True  # nach dem Zurücksetzen bis zum Neustart nichts mehr schreiben
    config["start_minimized"] = True
    config.save()
    assert not (tmp_path / "cfg" / "AluPC" / "config.json").exists()

    # Nach dem Beenden: löschen, Reste melden, neu starten
    started = []
    tries = []
    monkeypatch.setattr(reset, "wipe", lambda: tries.append(1) or ["gesperrt.log: benutzt"])
    monkeypatch.setattr("subprocess.Popen",
                        lambda cmd, **kw: started.append(cmd))
    reset.finish_and_restart(pause=0)
    assert started and (data / reset.LEFTOVER_FILE).read_text(encoding="utf-8") == "gesperrt.log: benutzt"
    assert len(tries) == 6  # mehrmals versucht (Browser-Hilfsprozesse geben Dateien erst kurz danach frei)


def test_reset_closes_own_crash_log_first(tmp_path, monkeypatch):
    """Windows-Fehler: „absturz.log wird von einem anderen Prozess verwendet“ – AluPC hielt die Datei selbst offen."""
    import faulthandler

    from alupc import bug_report, reset

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "cfg"))
    was_on = faulthandler.is_enabled()
    log = tmp_path / "cfg" / "AluPC" / "absturz.log"
    log.parent.mkdir(parents=True)
    monkeypatch.setattr(bug_report, "_crash_file", open(log, "a", encoding="utf-8"))  # noqa: SIM115
    seen = []
    monkeypatch.setattr(reset, "wipe", lambda: seen.append(bug_report._crash_file) or [])
    monkeypatch.setattr("subprocess.Popen", lambda cmd, **kw: None)
    reset.finish_and_restart(pause=0)
    assert seen == [None]  # beim Löschen ist die Datei schon zu
    log.unlink()  # unter Windows ginge das nur mit geschlossener Datei
    if was_on:
        faulthandler.enable()


def test_rtp_relay_remembers_keyframe():
    """AirPlay-Relais: erkennt Schlüsselbilder (auch STAP-A, FU-A, mehrere Teile) und merkt sich alles ab dort."""
    import socket
    import time

    from alupc.rtp_relay import RtpRelay, nal_types, rtp_payload

    def pkt(seq, payload):
        return bytes([0x80, 96]) + seq.to_bytes(2, "big") + bytes(8) + payload

    sps, pps = pkt(1, b"\x67abc"), pkt(2, b"\x68de")
    idr_a = pkt(3, bytes([0x7C, 0x85]) + b"x" * 50)  # FU-A, Anfang, Typ 5
    idr_mid = pkt(4, bytes([0x7C, 0x05]) + b"y" * 50)  # FU-A, Fortsetzung
    idr_b = pkt(5, bytes([0x65]) + b"z")  # zweiter Teil (Slice) desselben Schlüsselbilds
    p1 = pkt(6, bytes([0x41]) + b"p")  # normales Bild
    stap = pkt(7, bytes([24]) + (4).to_bytes(2, "big") + b"\x67sps" + (3).to_bytes(2, "big") + b"\x68pp"
               + (2).to_bytes(2, "big") + b"\x65i")
    assert nal_types(rtp_payload(idr_a)) == [5] and nal_types(rtp_payload(idr_mid)) == []
    assert nal_types(rtp_payload(stap)) == [7, 8, 5] and nal_types(rtp_payload(p1)) == [1]

    out = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    out.bind(("127.0.0.1", 0))
    out.settimeout(1)
    relay = RtpRelay(out.getsockname()[1])
    send = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        for p in (sps, pps, idr_a, idr_mid, idr_b, p1):
            send.sendto(p, ("127.0.0.1", relay.in_port))
        def body(p):
            return p[12:]

        got = [out.recv(2000) for _ in range(6)]
        assert [body(p) for p in got] == [body(p) for p in (sps, pps, idr_a, idr_mid, idr_b, p1)]  # sofort weiter
        seqs = [int.from_bytes(p[2:4], "big") for p in got]
        deadline = time.time() + 2
        while relay.cache != [sps, pps, idr_a, idr_mid, idr_b, p1] and time.time() < deadline:
            time.sleep(0.01)
        assert relay.cache == [sps, pps, idr_a, idr_mid, idr_b, p1]  # zweiter Slice startet KEIN neues Bild
        relay.replay()  # neuer Player → alles ab dem Schlüsselbild noch einmal
        again = [out.recv(2000) for _ in range(6)]
        assert [body(p) for p in again] == [body(p) for p in (sps, pps, idr_a, idr_mid, idr_b, p1)]
        # mit NEUEN, fortlaufenden Laufnummern – sonst verwirft der Player sie als „alt“
        assert [int.from_bytes(p[2:4], "big") for p in again] == list(range(seqs[-1] + 1, seqs[-1] + 7))
        send.sendto(stap, ("127.0.0.1", relay.in_port))  # neues Schlüsselbild (mit SPS/PPS im STAP-A)
        out.recv(2000)
        deadline = time.time() + 2
        while relay.cache != [stap] and time.time() < deadline:
            time.sleep(0.01)
        assert relay.cache == [stap]
        relay.reset()
        deadline = time.time() + 2
        while relay.has_keyframe and time.time() < deadline:
            time.sleep(0.01)
        assert not relay.has_keyframe and relay.cache == []
    finally:
        relay.stop()
        send.close()
        out.close()


def test_idle_clock_detects_kde_milliseconds(monkeypatch):
    """KDE meldet die Leerlaufzeit teils in Millisekunden (statt Sekunden) oder immer 0. AluPC misst die Einheit,
    statt ihr zu glauben – sonst startet der Schoner bei jeder kurzen Pause und geht nicht mehr weg."""
    from alupc import screensaver as ss

    clock = ss.IdleClock()
    clock.method = "freedesktop"
    now = [1000.0]
    monkeypatch.setattr(ss.time, "monotonic", lambda: now[0])
    raw = [0.0]
    monkeypatch.setattr(clock, "_freedesktop", lambda: raw[0])

    def step(seconds, per_second):
        now[0] += seconds
        raw[0] += seconds * per_second
        return clock.seconds()

    raw[0] = 5000.0
    assert clock.seconds() is None  # Einheit noch unbekannt → nicht verwenden
    assert abs(step(2, 1000) - 7.0) < 0.01 and clock.scale == 0.001  # Millisekunden erkannt

    clock2 = ss.IdleClock()
    clock2.method = "freedesktop"
    monkeypatch.setattr(clock2, "_freedesktop", lambda: raw[0])
    raw[0] = 30.0
    clock = clock2
    assert clock.seconds() is None
    assert abs(step(2, 1) - 32.0) < 0.01 and clock.scale == 1.0  # Sekunden

    clock3 = ss.IdleClock()
    clock3.method = "freedesktop"
    monkeypatch.setattr(clock3, "_freedesktop", lambda: 0)  # Wayland ohne Unterstützung: immer 0
    for _ in range(5):
        now[0] += 2
        assert clock3.seconds() is None  # nie „0 s Leerlauf“ glauben


def test_keep_awake_linux_inhibits_and_releases(monkeypatch):
    from alupc.platform import dbus_util, keep_awake

    monkeypatch.setattr(keep_awake.sys, "platform", "linux")
    calls = []

    class Conn:
        def close(self):
            calls.append(("close",))

    monkeypatch.setattr(dbus_util, "connect", lambda bus="SESSION": Conn())

    def call(conn, name, path, iface, method, sig="", args=(), timeout=0):
        calls.append((name, method, args))
        return (41,) if method == "Inhibit" else ()

    monkeypatch.setattr(dbus_util, "call", call)
    ka = keep_awake.KeepAwake()
    assert ka.set(True) and ka.active
    assert ("org.freedesktop.ScreenSaver", "Inhibit", ("AluPC", "AluPC zeigt etwas auf Monitor 2")) in calls
    n = len(calls)
    assert ka.set(True) and len(calls) == n  # zweimal einschalten: nichts Doppeltes
    assert not ka.set(False)
    assert ("org.freedesktop.ScreenSaver", "UnInhibit", (41,)) in calls and ("close",) in calls
    assert "abdunkeln" in ka.describe()


def test_uxplay_gets_monitor_2_size():
    """Das iPhone bekommt die Größe von Monitor 2 (weniger Pixel = flüssiger), höchstens 1920×1080."""
    from alupc.handy import screen_size_option

    helptext = "-s wxh[@r]  Set display resolution"
    assert screen_size_option(helptext, (1280, 720)) == ["-s", "1280x720"]
    assert screen_size_option(helptext, (3840, 2160)) == ["-s", "1920x1080"]
    assert screen_size_option(helptext, (2560, 1600)) == ["-s", "1728x1080"]
    assert screen_size_option("", (1280, 720)) == []  # Version ohne -s
    assert screen_size_option(helptext, None) == []


# ---------------------------------------------------------------- 0.82: Systemstatus
def test_sysinfo_helpers(tmp_path):
    from alupc import sysinfo
    from alupc.platform.fans import Chip

    assert sysinfo.fmt_bytes(512) == "512 B"
    assert sysinfo.fmt_bytes(1536 * 2**20) == "1,5 GB"
    assert sysinfo.fmt_bytes(500 * 2**30) == "500 GB"
    assert sysinfo.fmt_uptime(3 * 86400 + 7200) == "3 T. 2 Std."
    assert sysinfo.fmt_uptime(125 * 60) == "2 Std. 5 Min."
    assert sysinfo.clean_cpu_name("AMD Ryzen 7 5800X 8-Core Processor") == "AMD Ryzen 7 5800X"
    assert sysinfo.clean_cpu_name("Intel(R) Core(TM) i7-9700K CPU @ 3.60GHz") == "Intel Core i7-9700K"
    gpu = sysinfo.parse_nvidia("NVIDIA GeForce RTX 3070, 37, 61, 2048, 8192, 45, 120.5\n")
    assert gpu.name == "GeForce RTX 3070" and gpu.load == 37 and gpu.temp == 61 and gpu.mem_total == 8192
    assert gpu.fan == 45 and gpu.power == 120.5
    gpu = sysinfo.parse_nvidia("NVIDIA GeForce GTX 1050, 5, 40, 100, 2048, [N/A], [N/A]")
    assert gpu.fan is None and gpu.power is None
    assert sysinfo.parse_nvidia("") is None
    chips = [Chip("Mainboard (nct6798)", "nct6798", temps=[("SYSTIN", 30.0)]),
             Chip("AMD-Prozessor", "k10temp", temps=[("Tccd1", 50.0), ("Tctl", 55.5)])]
    assert sysinfo.pick_cpu_temp(chips) == 55.5
    assert sysinfo.pick_cpu_temp([Chip("x", "nvme", temps=[("Composite", 40.0)])]) is None
    # AMD-Grafikkarte aus sysfs
    dev = tmp_path / "card0" / "device"
    (dev / "hwmon" / "hwmon3").mkdir(parents=True)
    (dev / "gpu_busy_percent").write_text("42\n")
    (dev / "mem_info_vram_used").write_text(str(2 * 2**30))
    (dev / "mem_info_vram_total").write_text(str(8 * 2**30))
    (dev / "hwmon" / "hwmon3" / "temp1_input").write_text("63000")
    gpu = sysinfo.amd_gpu(tmp_path)
    assert gpu.load == 42 and gpu.mem_total == 8192 and gpu.temp == 63
    # Ein-/Ausschalten: feste Befehle je System
    assert sysinfo.power_command("aus", "linux") == ["systemctl", "poweroff"]
    assert sysinfo.power_command("neustart", "win32") == ["shutdown", "/r", "/t", "0"]
    assert sysinfo.power_command("energiesparen", "win32")[0] == "rundll32.exe"
    assert sysinfo.power_command("quatsch", "linux") is None


def test_system_voice_command():
    from alupc.voice import match

    assert match("monitor system", [])[0] == "system"
    assert match("monitor systemstatus", [])[0] == "system"


# ---------------------------------------------------------------- 0.84: Leistung richtig messen
def test_cpu_usage_and_device_filters():
    from collections import namedtuple

    from alupc import sysinfo
    from alupc.platform.win_pdh import engine_load

    T = namedtuple("T", "user nice system idle iowait irq softirq steal guest guest_nice")
    a = T(100, 0, 50, 800, 50, 0, 0, 0, 10, 0)
    b = T(160, 0, 70, 850, 70, 0, 0, 0, 30, 0)  # +80 belegt (guest steckt in user), +70 Leerlauf/Warten
    assert round(sysinfo.cpu_usage(a, b), 1) == round(80 * 100 / 150, 1)
    assert sysinfo.cpu_usage(a, a) == 0.0
    for nic in ("eth0", "enp3s0", "wlp2s0", "Ethernet", "WLAN"):
        assert sysinfo.real_nic(nic), nic
    for nic in ("lo", "docker0", "veth12ab", "virbr0", "tun0", "wg0", "ifb0", "tailscale0",
                "Loopback Pseudo-Interface 1", "vEthernet (Default Switch)"):
        assert not sysinfo.real_nic(nic), nic
    for disk in ("sda", "nvme0n1", "vda", "mmcblk0", "PhysicalDrive0"):
        assert sysinfo.physical_disk(disk), disk
    for disk in ("sda1", "nvme0n1p2", "loop3", "dm-0", "zram0", "mmcblk0p1", "sr0"):
        assert not sysinfo.physical_disk(disk), disk
    rows = [("pid_1_luid_0x1_phys_0_eng_0_engtype_3D", 30.0), ("pid_2_luid_0x1_phys_0_eng_0_engtype_3D", 25.0),
            ("pid_2_luid_0x1_phys_0_eng_3_engtype_VideoDecode", 40.0), ("pid_3_x_engtype_Copy", 5.0)]
    assert engine_load(rows) == 55.0  # wie der Task-Manager: stärkste Engine-Art, über Programme summiert
    assert engine_load([("a_engtype_3D", 80.0), ("b_engtype_3D", 70.0)]) == 100.0


@pytest.mark.skipif(sys.platform != "win32", reason="Leistungsindikatoren gibt es nur unter Windows")
def test_windows_pdh_counters_real():
    import time

    from alupc.platform import win_pdh

    pdh = win_pdh.Pdh()
    assert "cpu" in pdh.counters, "Prozessor-Zähler fehlt"
    time.sleep(1)
    pdh.collect()
    total, cores = pdh.cpu()
    assert total is not None and 0 <= total <= 100
    assert len(cores) >= 1 and all(0 <= c <= 100 for c in cores)
    load, _vram = pdh.gpu()  # CI-VM hat oft keine GPU-Zähler – dann None, aber kein Fehler
    assert load is None or 0 <= load <= 100
    print("PDH", total, len(cores), load, win_pdh.gpu_name_and_memory())
    pdh.close()


# ---------------------------------------------------------------- 0.87: Mainboard-RGB (ASUS Aura USB)
def test_openrgb_resizable_zones_and_late_devices():
    """ASUS-AM5-Mainboards: ARGB-Anschlüsse stehen in OpenRGB oft auf 0 LEDs; das Mainboard taucht erst nach
    Maus/Tastatur auf. AluPC muss beides können."""
    from fake_openrgb import FakeOpenRGB

    from alupc.rgb import OpenRGB

    fake = FakeOpenRGB(4)
    fake.devices = [("Logitech Maus", 6, [("Logo", 1, False, 0)])]
    try:
        client = OpenRGB(port=fake.port)
        assert [d.name for d in client.connect()] == ["Logitech Maus"]
        # Mainboard kommt später (OpenRGB-Erkennung über USB dauert)
        fake.devices.append(("ASUS TUF GAMING B650-PLUS WIFI", 0,
                             [("Aura Mainboard", 1, False, 0), ("Aura Addressable 1", 0, False, 0, 120)]))
        devs = client.refresh()
        board = devs[1]
        assert board.type == 0 and board.num_leds == 1
        z = board.zone_info[1]
        assert z.resizable and z.count == 0 and z.leds_max == 120
        assert not board.zone_info[0].resizable
        client.resize_zone(1, 1, 30)
        board = client.refresh()[1]
        assert board.zone_info[1].count == 30 and board.num_leds == 31
        client.set_color((0, 0, 255))
        import time

        time.sleep(0.2)
        assert fake.leds(1) == [(0, 0, 255)] * 31
        assert (1, 1100, b"") in fake.received  # vorher auf „Direkt“ geschaltet
        client.close()
    finally:
        fake.close()


def test_linux_gpu_scan_with_reasons(tmp_path):
    """Linux: jede Karte zählt – mit Auslastung (amdgpu) oder mit Grund, warum sie fehlt (nouveau, Intel …)."""
    import os
    import shutil

    from alupc import sysinfo
    from alupc.sysinfo_draw import gauge_values

    def card(name, vendor, driver, busy=None, vram_total=None, temp=None):
        dev = tmp_path / "drm" / name / "device"
        (dev / "hwmon" / "hwmon1").mkdir(parents=True)
        (dev / "vendor").write_text(vendor + "\n")
        drv = tmp_path / "drivers" / driver
        drv.mkdir(parents=True, exist_ok=True)
        os.symlink(drv, dev / "driver")
        if busy is not None:
            (dev / "gpu_busy_percent").write_text(f"{busy}\n")
            (dev / "mem_info_vram_used").write_text(str(512 * 2**20))
            (dev / "mem_info_vram_total").write_text(str(vram_total * 2**20))
        if temp is not None:
            (dev / "hwmon" / "hwmon1" / "temp1_input").write_text(str(temp * 1000))
        (tmp_path / "drm" / f"{name}-HDMI-A-1").mkdir()

    card("card0", "0x1002", "amdgpu", busy=3, vram_total=512, temp=40)  # Ryzen-Grafik im Prozessor
    card("card1", "0x1002", "amdgpu", busy=71, vram_total=16384, temp=63)  # Radeon-Grafikkarte
    gpus = sysinfo.linux_gpus(tmp_path / "drm")
    assert len(gpus) == 2
    best = sysinfo.pick_gpu(gpus)
    assert best.load == 71 and best.mem_total == 16384 and best.name == "AMD-Grafikkarte" and best.temp == 63
    shutil.rmtree(tmp_path / "drm")
    card("card0", "0x10de", "nouveau", temp=45)  # nur NVIDIA mit nouveau: Grund statt „keine Daten“
    (gpu,) = sysinfo.linux_gpus(tmp_path / "drm")
    assert gpu.load is None and gpu.name == "NVIDIA-Grafikkarte" and "nouveau" in gpu.note and gpu.temp == 45

    class Mon:
        cores = 8

    row = next(r for r in gauge_values(Mon(), sysinfo.Snapshot(gpu=gpu, ram_total=1)) if r[0] == "gpu")
    assert row[2] is None and "NVIDIA-Grafikkarte" in row[4] and "45 °C" in row[4]


@pytest.mark.skipif(sys.platform == "win32", reason="Ersatz-Programm ist ein Shell-Skript")
def test_nvidia_stream_reads_continuous_output(tmp_path):
    """nvidia-smi läuft dauerhaft (-lms) statt jede Sekunde neu – hier mit einem Ersatz-Programm."""
    import time

    from alupc import sysinfo

    fake = tmp_path / "nvidia-smi"
    fake.write_text("#!/bin/sh\n"
                    "while true; do echo 'NVIDIA GeForce RTX 4070, 42, 55, 3000, 12282, 30, 95.5'; sleep 0.2; done\n")
    fake.chmod(0o755)
    stream = sysinfo.NvidiaStream(str(fake))
    end = time.time() + 3
    gpu = None
    while gpu is None and time.time() < end:
        gpu = stream.get()
        time.sleep(0.05)
    stream.stop()
    assert gpu is not None and gpu.name == "GeForce RTX 4070" and gpu.load == 42 and gpu.temp == 55


def test_sync_merges_entries_not_whole_sections():
    """Beide Systeme ändern Verschiedenes im selben Bereich → beides bleibt (früher: eine Seite verlor)."""
    from alupc.settings_sync import merge_payload, merge_value

    base = {"scenes": [{"name": "A", "x": 1}], "timer": {"minutes": 5, "size": 30}, "voice": {"wake": ["monitor"]}}
    local = {"scenes": [{"name": "A", "x": 2}, {"name": "Linux-Szene"}], "timer": {"minutes": 9, "size": 30},
             "voice": {"wake": ["monitor", "computer"]}}
    remote = {"scenes": [{"name": "A", "x": 1}, {"name": "Windows-Szene"}], "timer": {"minutes": 5, "size": 40},
              "voice": {"wake": ["monitor", "alupc"]}}
    merged, conflicts = merge_payload(base, local, remote)
    names = [s["name"] for s in merged["scenes"]]
    assert names[0] == "A" and sorted(names[1:]) == ["Linux-Szene", "Windows-Szene"]
    assert merged["scenes"][0]["x"] == 2 and merged["timer"] == {"minutes": 9, "size": 40}
    assert merged["voice"]["wake"] == ["monitor", "computer", "alupc"] and conflicts == []
    # gelöscht auf einer Seite, unverändert auf der anderen → bleibt gelöscht
    v, c = merge_value([{"name": "A"}, {"name": "B"}], [{"name": "A"}], [{"name": "A"}, {"name": "B"}, {"name": "C"}])
    assert [x["name"] for x in v] == ["A", "C"] and not c
    # nur umsortiert auf der anderen Seite → deren Reihenfolge
    v, _ = merge_value([{"id": 1}, {"id": 2}], [{"id": 1}, {"id": 2}, {"id": 3}], [{"id": 2}, {"id": 1}])
    assert [x["id"] for x in v] == [2, 1, 3]
    # wirklich dieselbe Stelle verschieden geändert → Konflikt, eigene gewinnt
    v, c = merge_value({"minutes": 5}, {"minutes": 7}, {"minutes": 9})
    assert v == {"minutes": 7} and c


def test_sync_media_paths_work_on_both_systems(tmp_path, monkeypatch):
    """Bilder/Videos: C:\\Bilder ↔ /media/…/Bilder; Dateien nur im Linux-Home werden in den Sync-Ordner kopiert."""
    import os
    from pathlib import Path

    from alupc import settings_sync as ss
    from alupc.config import Config

    win_root = tmp_path / "C"  # Windows sieht das Laufwerk als C:\
    (win_root / "Bilder").mkdir(parents=True)
    (win_root / "Bilder" / "a.jpg").write_bytes(b"jpg")
    lin_root = tmp_path / "media-win"  # Linux hat dasselbe Laufwerk woanders eingehängt
    try:
        os.symlink(win_root, lin_root, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Verknüpfungen hier nicht erlaubt")
    home = tmp_path / "home"
    home.mkdir()
    (home / "b.png").write_bytes(b"png-nur-linux")
    win, lin = Config(tmp_path / "win.json"), Config(tmp_path / "lin.json")
    win.data["sync"] = {**win.data["sync"], "enabled": True, "folder": str(win_root / ss.FOLDER_NAME)}
    lin.data["sync"] = {**lin.data["sync"], "enabled": True, "folder": str(lin_root / ss.FOLDER_NAME)}
    (win_root / ss.FOLDER_NAME).mkdir()

    def on(system):
        root = win_root if system is win else lin_root
        monkeypatch.setattr(ss, "drive_root", lambda folder: root)
        return system

    win["media"] = {**win["media"], "saved": [str(win_root / "Bilder" / "a.jpg")]}
    ss.sync_once(on(win))
    raw = ss.sync_file(win_root / ss.FOLDER_NAME).read_text(encoding="utf-8")
    assert "alupc-laufwerk:Bilder/a.jpg" in raw and str(win_root) not in raw  # laufwerksneutral gespeichert
    ss.sync_once(on(lin))
    assert lin["media"]["saved"] == [str(lin_root / "Bilder" / "a.jpg")]
    # Linux legt eine Szene mit einem Bild aus dem Home an → wird kopiert, Windows findet es
    lin["scenes"] = [{"name": "Urlaub", "sources": [{"type": "image", "path": str(home / "b.png")}]}]
    assert "Gespeichert" in ss.sync_once(on(lin))[0]
    ss.copy_thread.join(10)
    copies = list((win_root / ss.FOLDER_NAME / ss.COPY_DIR).glob("*-b.png"))
    assert len(copies) == 1 and copies[0].read_bytes() == b"png-nur-linux"
    _msg, changed = ss.sync_once(on(win))
    path = win["scenes"][0]["sources"][0]["path"]
    assert "scenes" in changed and Path(path) == copies[0] and Path(path).is_file()
    # Windows bleibt danach stabil (kein Hin-und-Her durch Pfad-Übersetzung)
    assert ss.sync_once(on(win))[0] == "Alles aktuell." and ss.sync_once(on(lin))[0] == "Alles aktuell."


def test_sync_covers_voice_games_extras(tmp_path):
    from alupc import settings_sync as ss
    from alupc.config import Config

    cfg = Config(tmp_path / "c.json")
    cfg["voice"] = {**cfg["voice"], "device": "alsa:hw:1", "custom": [{"say": "licht an", "do": "x"}]}
    data = ss.payload(cfg)
    for key in ("voice", "games", "hotspot", "welcome", "wheel", "start_content", "finger_shortcuts"):
        assert key in data, key
    assert "device" not in data["voice"] and data["voice"]["custom"][0]["say"] == "licht an"


def test_reset_also_clears_dual_boot_sync(tmp_path, monkeypatch):
    """„Alle Daten löschen“ wirkte wie wirkungslos: nach dem Neustart holte der Abgleich alles vom anderen System
    zurück. Jetzt: Sync-Dateien weg, Abgleich bleibt aus (bis man ihn wieder einschaltet)."""
    import json

    from alupc import reset, settings_sync as ss
    from alupc.config import Config

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "cfg"))
    monkeypatch.setattr("alupc.platform.autostart.set_enabled", lambda on: None)
    monkeypatch.setattr("tempfile.gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(reset, "data_dirs", lambda: [tmp_path / "cfg" / "AluPC"])  # nie echte Ordner löschen
    shared = tmp_path / "C" / ss.FOLDER_NAME
    shared.mkdir(parents=True)
    other = Config(tmp_path / "anderes.json")  # das andere System hat schon abgeglichen
    other.data["sync"] = {**other.data["sync"], "enabled": True, "folder": str(shared)}
    other["timer"] = {**other["timer"], "minutes": 42}
    ss.sync_once(other)
    (shared / "Dateien").mkdir()
    cfg = Config(tmp_path / "cfg" / "AluPC" / "config.json")
    cfg.data["sync"] = {**cfg.data["sync"], "enabled": True, "folder": str(shared)}
    reset._pending.update(on=True, clear_sync=True, sync_folder=str(shared))
    with monkeypatch.context() as mp:
        mp.setattr("subprocess.Popen", lambda cmd, **kw: None)  # kein echter Neustart
        try:
            reset.finish_and_restart(pause=0)
        finally:
            reset._pending.update(on=False, clear_sync=False, sync_folder="")
    assert not list(shared.glob("alupc-sync*.json")) and not (shared / "Dateien").exists()
    fresh = Config(tmp_path / "cfg" / "AluPC" / "config.json")
    assert fresh["sync"]["declined"] and not fresh["sync"]["enabled"]
    monkeypatch.setattr(ss, "drives", lambda: [str(tmp_path / "C")])
    ss.sync_once(other)  # anderes System schreibt wieder …
    assert ss.auto_setup(fresh) is None and fresh["timer"]["minutes"] != 42  # … aber hier kommt nichts zurück
    assert json.loads((tmp_path / "cfg" / "AluPC" / "config.json").read_text())["sync"]["declined"]


def test_reset_retries_locked_leftovers_on_next_start(tmp_path, monkeypatch):
    from alupc import reset

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "cfg"))
    monkeypatch.setattr("alupc.platform.autostart.set_enabled", lambda on: None)
    monkeypatch.setattr("tempfile.gettempdir", lambda: str(tmp_path))
    data = tmp_path / "cfg" / "AluPC"
    data.mkdir(parents=True)
    (data / "absturz.log").write_text("x")
    (data / reset.LEFTOVER_FILE).write_text("absturz.log: benutzt")
    reset._retry_path().write_text(str(data))
    reset.cleanup_pending()  # Neustart: Datei ist jetzt frei → weg, keine Fehlermeldung
    assert not (data / "absturz.log").exists() and not (data / reset.LEFTOVER_FILE).exists()
    assert not reset._retry_path().exists()


def test_sync_sections_can_be_switched_off(tmp_path):
    """Setup → Sichern & Sync: Bereiche abwählen – die werden weder geschickt noch übernommen, und die des anderen
    Systems bleiben in der Sync-Datei erhalten. Verlauf zeigt, was passiert ist."""
    from alupc import settings_sync as ss
    from alupc.config import Config

    shared = tmp_path / ss.FOLDER_NAME
    shared.mkdir()
    win, lin = Config(tmp_path / "win.json"), Config(tmp_path / "lin.json")
    for cfg in (win, lin):
        cfg.data["sync"] = {**cfg.data["sync"], "enabled": True, "folder": str(shared)}
    win["scenes"] = [{"name": "Windows-Szene"}]
    win["timer"] = {**win["timer"], "minutes": 9}
    ss.sync_once(win)
    lin.data["sync"] = {**lin.data["sync"], "skip": ["szenen"]}
    _msg, changed = ss.sync_once(lin)
    assert "scenes" not in changed and lin["scenes"] == [] and lin["timer"]["minutes"] == 9
    lin["timer"] = {**lin["timer"], "minutes": 3}
    ss.sync_once(lin)
    data = ss._read(ss.sync_file(shared))["data"]
    assert data["scenes"] == [{"name": "Windows-Szene"}] and data["timer"]["minutes"] == 3  # Szenen von Windows bleiben
    assert any("übernommen" in h for h in lin["sync"]["history"]) and "gespeichert" in lin["sync"]["history"][-1]


def test_reset_keeps_scenes_and_reports_backup(tmp_path, monkeypatch):
    """„Szenen & Startseite behalten“: nur Einstellungen weg; Sicherung wird nach dem Neustart genannt und lässt sich
    importieren."""
    from alupc import reset
    from alupc import settings_sync as ss
    from alupc.config import Config

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "cfg"))
    monkeypatch.setattr("alupc.platform.autostart.set_enabled", lambda on: None)
    monkeypatch.setattr("tempfile.gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(reset, "data_dirs", lambda: [tmp_path / "cfg" / "AluPC"])
    monkeypatch.setattr(reset, "backup_dir", lambda: tmp_path / "Sicherungen")
    cfg = Config(tmp_path / "cfg" / "AluPC" / "config.json")
    cfg["scenes"] = [{"name": "Party"}]
    cfg["timer"] = {**cfg["timer"], "minutes": 33}
    backup = reset.save_backup(cfg)
    assert backup and backup.is_file()
    reset._pending.update(on=True, clear_sync=False, sync_folder="", keep={"scenes": cfg["scenes"]},
                          backup=str(backup))
    with monkeypatch.context() as mp:
        mp.setattr("subprocess.Popen", lambda cmd, **kw: None)
        try:
            reset.finish_and_restart(pause=0)
        finally:
            reset._pending.update(on=False, keep={}, backup="")
    fresh = Config(tmp_path / "cfg" / "AluPC" / "config.json")
    assert [sc["name"] for sc in fresh["scenes"]] == ["Party"] and fresh["timer"]["minutes"] != 33
    shown = []
    monkeypatch.setattr("PySide6.QtWidgets.QMessageBox.information", lambda *a: shown.append(a[2]))
    reset.report_leftovers(None, fresh)
    assert shown and str(backup) in shown[0] and "reset_info" not in fresh.data
    changed = ss.import_settings(fresh, ss.read_export(backup), list(ss.SECTIONS))  # alles wieder da
    assert "timer" in changed and fresh["timer"]["minutes"] == 33


def test_sync_check_info_and_restore_conflict_backup(tmp_path):
    """Sync-Seite: „Prüfen“, Stand des anderen Systems, Konflikt-Sicherung zurückholen."""
    from alupc import settings_sync as ss
    from alupc.config import Config

    shared = tmp_path / ss.FOLDER_NAME
    shared.mkdir()
    win, lin = Config(tmp_path / "win.json"), Config(tmp_path / "lin.json")
    for cfg in (win, lin):
        cfg.data["sync"] = {**cfg.data["sync"], "enabled": True, "folder": str(shared)}
    result = ss.check(lin)
    assert any(not ok and "Sync-Datei" in t for ok, t in result)  # noch nie abgeglichen
    ss.sync_once(win)
    ss.sync_once(lin)
    assert ss.remote_info(lin)["rev"] >= 1
    assert all(ok for ok, _t in ss.check(lin))
    # Konflikt: beide ändern dieselbe Stelle → Sicherung der anderen Fassung
    win["timer"] = {**win["timer"], "minutes": 11}
    ss.sync_once(win)
    lin["timer"] = {**lin["timer"], "minutes": 22}
    ss.sync_once(lin)
    backups = ss.conflict_backups(lin)
    assert backups and lin["timer"]["minutes"] == 22
    changed = ss.restore_backup(lin, backups[0])  # doch lieber die andere Fassung
    assert "timer" in changed and lin["timer"]["minutes"] == 11
    assert "Sicherung übernommen" in lin["sync"]["history"][-1]


def test_broken_scenes_are_repaired(tmp_path):
    """Gefunden beim Rundgang: Szene ohne „layout“ (alte Sicherung, Abgleich) ließ die App beim Start abstürzen."""
    import json

    from alupc.config import Config
    from alupc.scenes import LAYOUTS, layout_slots

    p = tmp_path / "c.json"
    p.write_text(json.dumps({"scenes": [{"name": "Alt"}, {"name": "X", "layout": "gibtsnicht", "slots": [None] * 9},
                                        "kaputt"]}), encoding="utf-8")
    cfg = Config(p)
    assert [s["name"] for s in cfg["scenes"]] == ["Alt", "X"]
    for sc in cfg["scenes"]:
        assert sc["layout"] in LAYOUTS and len(sc["slots"]) == len(layout_slots(sc["layout"]))
    cfg.put_scene({"name": "Neu"})
    assert cfg.get_scene("Neu")["layout"] == "vollbild"


@pytest.mark.skipif(not sys.platform.startswith("win"), reason="Windows-Registry")
def test_tray_promote_after_update_windows():
    """Nach einem Update legt Windows einen neuen, versteckten Eintrag an → AluPC zeigt das Symbol wieder."""
    import winreg

    from alupc.platform.windows_tray import KEY, promote

    exe = r"C:\AluPC-Test\AluPC.exe"
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, KEY + r"\AluPCTestEintrag") as k:
        winreg.SetValueEx(k, "ExecutablePath", 0, winreg.REG_SZ, exe)
        winreg.SetValueEx(k, "IsPromoted", 0, winreg.REG_DWORD, 0)
    try:
        assert promote(exe) is True
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, KEY + r"\AluPCTestEintrag") as k:
            assert winreg.QueryValueEx(k, "IsPromoted")[0] == 1
        assert promote(exe) is False  # schon sichtbar → nichts zu tun (kein Flackern)
    finally:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, KEY + r"\AluPCTestEintrag")


def test_audio_pactl_parsing():
    """Linux-Ton: Geräte aus pactl (JSON und alt), Monitor-Quellen weg, Pegel und Stumm lesen."""
    import json

    from alupc import audio

    sinks = [{"name": "alsa_output.pci.analog", "description": "Eingebaut"},
             {"name": "bluez_output.kopfhoerer", "description": "Kopfhörer"}]
    sources = [{"name": "alsa_output.pci.analog.monitor", "description": "Monitor of Eingebaut",
                "monitor_of_sink": "alsa_output.pci.analog"},
               {"name": "alsa_input.pci.mic", "description": "Mikrofon", "monitor_of_sink": "n/a"}]

    def run(cmd, timeout=6):
        joined = " ".join(cmd)
        if "get-default-sink" in joined:
            return 0, "bluez_output.kopfhoerer\n"
        if "get-default-source" in joined:
            return 0, "alsa_input.pci.mic\n"
        if "-f json list sinks" in joined:
            return 0, json.dumps(sinks)
        if "-f json list sources" in joined:
            return 0, json.dumps(sources)
        if "get-sink-volume" in joined:
            return 0, "Volume: front-left: 26214 /  40% / -23.88 dB,   front-right: 26214 /  40% / -23.88 dB"
        if "get-sink-mute" in joined:
            return 0, "Mute: yes"
        return 1, ""

    outs = audio._pa_devices("out", run=run)
    assert outs == [{"id": "alsa_output.pci.analog", "name": "Eingebaut", "default": False},
                    {"id": "bluez_output.kopfhoerer", "name": "Kopfhörer", "default": True}]
    assert audio._pa_devices("in", run=run) == [{"id": "alsa_input.pci.mic", "name": "Mikrofon", "default": True}]
    assert audio._pa_level("out", run=run) == (40, True)

    def old(cmd, timeout=6):  # pactl ohne JSON
        joined = " ".join(cmd)
        if "-f json" in joined:
            return 1, "Unbekannte Option"
        if "list short sources" in joined:
            return 0, "0\talsa_output.x.monitor\tmodule\ts16le\tIDLE\n1\talsa_input.mic\tmodule\ts16le\tRUNNING\n"
        if "get-default-source" in joined:
            return 0, "alsa_input.mic"
        return 1, ""

    assert audio._pa_devices("in", run=old) == [{"id": "alsa_input.mic", "name": "alsa_input.mic", "default": True}]
    assert audio.run("ton_quatsch:1") == "Unbekannter Ton-Befehl."


@pytest.mark.skipif(not sys.platform.startswith("win"), reason="Windows Core Audio")
def test_audio_core_audio_windows():
    """Windows: Core-Audio-Schnittstellen lassen sich anlegen; Geräte lesen stürzt nicht ab (CI hat evtl. keine)."""
    from alupc import audio

    assert audio.available()
    st = audio.state(max_age=0)
    assert st is not None and set(st) == {"out", "in"}
    for kind in ("out", "in"):
        for d in st[kind]["devices"]:
            assert d["id"] and d["name"]
    print("Windows-Ton:", {k: (v["vol"], v["muted"], [d["name"] for d in v["devices"]]) for k, v in st.items()})
