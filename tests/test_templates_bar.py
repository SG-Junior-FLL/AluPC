"""Vorlagen: Uhr, Countdown und Laufschrift stehen in einer Leiste unter der Seite – nichts liegt mehr darüber."""

from PySide6.QtGui import QImage, QPainter
from test_gui import env  # noqa: F401  (Fixture: Qt-App + Fenster)

from alupc import screens, screens_bar
from alupc.scenes import layout_slots

CORNERS = {"ecke_oben_rechts", "ecke_unten_links"}


def test_extras_parsing():
    assert screens_bar.extras({}) == {}
    assert screens_bar.extras({"uhr": True, "countdown": "2", "laufschrift": "  a   b "}) == \
        {"uhr": True, "countdown": 2.0, "laufschrift": "a b"}
    assert screens_bar.extras({"countdown": "x"}) == {}
    assert screens_bar.needs_ticks({"laufschrift": "x"}) == 33 and screens_bar.needs_ticks({}) is None
    assert screens_bar.remaining({"countdown": 1}, now=130, started=100) == 30


def test_templates_do_not_cover_content():
    """Keine Vorlage legt Uhr/Countdown als Kasten über eine gestaltete Seite."""
    for key in screens.SCENE_TEMPLATES:
        scene = screens.build_template(key, {})
        slots = scene["slots"]
        assert scene["layout"] not in CORNERS, key
        if scene["layout"] == "ecke_unten_rechts":  # nur noch Kamera klein über der LIVE-Karte
            assert slots[1]["type"] == "camera", key
        assert not any(s.get("type") in ("clock", "countdown") for s in slots), key
        assert len(slots) == len(layout_slots(scene["layout"])), key


def test_bar_paints_and_hides_corner_clock(env, monkeypatch):  # noqa: F811
    from alupc import stage

    calls = []
    real = stage.clock_corner
    monkeypatch.setattr(stage, "clock_corner", lambda *a, **k: calls.append(stage.HIDE_CLOCK) or real(*a, **k))
    img = QImage(640, 360, QImage.Format_RGB32)
    p = QPainter(img)
    cfg = {**screens.design_defaults("willkommen"), "uhr": True, "countdown": 5, "laufschrift": "Hallo " * 40}
    screens.paint_design(p, 640, 360, cfg, now=1000.0, started=990.0)
    p.end()
    assert calls and all(calls)  # die kleine Uhr oben rechts bleibt weg, die Leiste zeigt sie
    assert stage.HIDE_CLOCK is False
    bar = img.pixelColor(320, 359)
    assert bar.value() < 60  # dunkle Leiste ganz unten


def test_old_template_scenes_are_replaced(tmp_path):
    """Gespeicherte Szenen aus alten Vorlagen bekommen beim Laden einmal den neuen Aufbau; alte Fassung gesichert."""
    import json

    from alupc.config import Config
    from alupc.scenes import upgrade_scene

    clock = {"type": "clock", "show_date": False}
    old = [
        {"name": "Begrüßung", "layout": "ecke_unten_rechts", "background": "#000000",
         "slots": [{"type": "design", "design": "willkommen", "title": "Hallo"}, clock]},
        {"name": "Quiz", "layout": "ecke_oben_rechts", "background": "#000000",
         "slots": [{"type": "design", "design": "abstimmung"}, {"type": "countdown", "minutes": 2}]},
        {"name": "Ablauf", "layout": "gross_zwei_klein", "background": "#000000",
         "slots": [{"type": "design", "design": "ablauf"}, clock,
                   {"type": "design", "design": "ankuendigung", "text": "Fragen am Ende"}]},
        {"name": "News", "layout": "bauchbinde", "background": "#000000",
         "slots": [{"type": "design", "design": "schlagzeile"}, {"type": "text", "text": "Ticker"}]},
        {"name": "QR", "layout": "nebeneinander", "background": "#000000",
         "slots": [{"type": "design", "design": "willkommen"}, {"type": "cast"}]},
        {"name": "Eigene", "layout": "nebeneinander", "background": "#000000",
         "slots": [{"type": "camera"}, clock]},  # keine alte Vorlage: bleibt
    ]
    new = [upgrade_scene(json.loads(json.dumps(s))) for s in old]
    assert new[0]["layout"] == "vollbild" and new[0]["slots"][0] == {**old[0]["slots"][0], "uhr": True}
    assert new[1]["slots"][0]["countdown"] == 2
    assert new[2]["slots"][0]["uhr"] and new[2]["slots"][0]["laufschrift"] == "Fragen am Ende"
    assert new[3]["slots"][0]["laufschrift"] == "Ticker"
    assert new[4]["layout"] == "haupt_seite" and len(new[4]["slots"]) == 2
    assert new[5] == old[5]
    assert all(n["name"] == o["name"] for n, o in zip(new, old))

    path = tmp_path / "config.json"
    path.write_text(json.dumps({"scenes": old}), encoding="utf-8")
    cfg = Config(path)
    assert cfg.get_scene("Begrüßung")["layout"] == "vollbild"
    assert json.loads((tmp_path / "config.vorlagen-alt.json").read_text(encoding="utf-8")) == old
    assert json.loads(path.read_text(encoding="utf-8"))["vorlagen_v2"] is True  # gespeichert, nur einmal
    cfg2 = Config(path)
    assert cfg2.data["scenes"] == cfg.data["scenes"]
