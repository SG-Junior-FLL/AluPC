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
