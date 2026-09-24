"""Tests der reinen Logik (ohne Bildschirm, ohne Hardware)."""

import ctypes
import json

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
