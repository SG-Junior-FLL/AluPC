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
    from alupc.startpage import DEFAULT_ORDER, all_keys, custom_key, ordered_keys, section_of

    cfg = {"tiles": None, "custom": [{"id": "a1", "title": "X", "section": "schnell"}]}
    assert ordered_keys(cfg) == DEFAULT_ORDER + ["custom:a1"]
    cfg["tiles"] = ["camera", "gibts-nicht", "mirror"]
    cfg["seen"] = list(DEFAULT_ORDER)
    keys = ordered_keys(cfg)
    assert keys == ["camera", "mirror", "custom:a1"]  # unbekannte weg, neue eigene hinten dran
    full = all_keys(cfg)
    assert full[:3] == keys and set(full) == set(DEFAULT_ORDER) | {"custom:a1"}
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
    from alupc.startpage import ordered_keys

    old_saved = {"tiles": ["timer", "mirror"], "custom": []}  # Einstellungen von vor dem Update
    assert ordered_keys(old_saved) == ["timer", "mirror", "handy", "draw"]
    from alupc.startpage import DEFAULT_ORDER

    hidden_on_purpose = {"tiles": ["timer", "mirror"], "custom": [], "seen": list(DEFAULT_ORDER)}
    assert ordered_keys(hidden_on_purpose) == ["timer", "mirror"]
    assert "draw" in ordered_keys({"tiles": None})


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


# ---------------------------------------------------------------- 0.12: AluCast, Miracast
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


def test_miracast_parse():
    from alupc.platform.miracast import CAPABILITY, install_command, parse_app

    assert parse_app('{"Name":"Drahtlose Anzeige","AppID":"Microsoft.WirelessDisplay_8wekyb3d8bbwe!App"}') == {
        "name": "Drahtlose Anzeige", "app_id": "Microsoft.WirelessDisplay_8wekyb3d8bbwe!App"}
    assert parse_app("") is None and parse_app("kaputt") is None and parse_app('{"Name":"x"}') is None
    assert parse_app('[{"Name":"Connect","AppID":"a!b"}]')["name"] == "Connect"
    assert CAPABILITY in " ".join(install_command()) and "RunAs" in " ".join(install_command())


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
    # Ordner fehlt → verständliche Meldung, nichts kaputt
    lin.data["sync"]["folder"] = str(tmp_path / "gibtsnicht")
    assert "nicht erreichbar" in ss.sync_once(lin)[0]


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
