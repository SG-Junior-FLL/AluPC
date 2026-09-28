"""Overlays über Monitor 2: Stelle (Ecken, Kanten, frei), Vorlagen, Fenster, Kachel, Editor mit Ziehen."""

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt
from PySide6.QtGui import QImage, QMouseEvent, QWheelEvent

from test_gui import _until, env, pump  # noqa: F401  (Fixture + Hilfen der Oberflächen-Tests)

from alupc import overlays as ov
from alupc.now_playing import Track


def _data():
    data = ov.OverlayData()
    data.set_track(Track(title="Blinding Lights", artist="The Weeknd", player="Spotify", playing=True,
                         position=84, length=200))
    return data


def test_overlay_positions_and_templates():
    """x/y 0…1: Ecken, Kanten-Mitten, Mitte und alles dazwischen; immer ganz auf dem Bildschirm; Einrasten."""
    W, H = 1920, 1080
    data = _data()
    m = ov.margin(W, H)
    for _cat, name, _desc, tpl in ov.TEMPLATES:
        item = ov.from_template(tpl, name)
        assert item["id"] and item["name"] == name and item["on"]
        size = ov.measure(item, W, H, data)
        assert size.width() > 10 and size.height() > 10, name
        for x in (0.0, 0.25, 0.5, 1.0):
            for y in (0.0, 0.7, 1.0):
                r = ov.place(dict(item, x=x, y=y), W, H, size)
                assert r.left() >= m - 0.5 and r.top() >= m - 0.5, (name, x, y)
                assert r.right() <= W - m + 0.5 and r.bottom() <= H - m + 0.5, (name, x, y)
                back = ov.xy_for(item, r, W, H)
                if r.width() < W - 2 * m - 1:  # sonst gibt es waagerecht keinen Spielraum
                    assert abs(back[0] - x) < 0.01, (name, x, back)
                assert abs(back[1] - y) < 0.01, (name, y, back)
        # zeichnen klappt in jeder Größe (klein = Vorschau, groß = 4K)
        for w, h in ((224, 126), (1280, 720), (3840, 2160)):
            img = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
            img.fill(Qt.black)
            from PySide6.QtGui import QPainter

            p = QPainter(img)
            ov.paint_all(p, [item], w, h, data)
            p.end()
    item = {"x": 1.0, "y": 1.0}
    r = ov.place(item, W, H, ov.measure({"type": "clock"}, W, H, data))
    assert abs(r.right() - (W - m)) < 1 and abs(r.bottom() - (H - m)) < 1  # unten rechts in der Ecke
    assert ov.snap(0.03) == 0.0 and ov.snap(0.52) == 0.5 and ov.snap(0.97) == 1.0 and ov.snap(0.3) == 0.3
    assert ov.position_name(0.0, 1.0) == "unten links" and ov.position_name(0.3, 0.5) == "frei"


def test_overlay_window_follows_settings(env):
    """Overlays an → eigenes Fenster über Monitor 2 (auch über fremden Fenstern); Schwarz/aus → weg.
    Vorschau-Bilder (Bild-in-Bild, Live-Bild, Handy) enthalten sie."""
    controller, window, _ = env
    win = controller.overlay_window
    assert not win.isVisible()
    item = ov.from_template({"type": "badge", "text": "Hallo", "x": 0.0, "y": 0.0, "style": "farbe",
                             "color": "#ff0000"}, "Hinweis")
    controller.config["overlays"] = {"on": False, "items": [item]}
    controller.overlays_changed()
    assert not win.isVisible() and not window.t_overlays.active
    window.t_overlays.activated.emit()  # Kachel: an
    pump()
    assert controller.config["overlays"]["on"] and win.isVisible() and window.t_overlays.active
    out = controller.output_screen().geometry()
    assert win.geometry() == out
    # Vorschau: Overlay oben links ins Bild gemalt
    img = QImage(640, 360, QImage.Format_ARGB32_Premultiplied)
    img.fill(Qt.black)
    from alupc.laser import draw_overlay

    draw_overlay(controller, img)
    m = ov.margin(640, 360)
    c = img.pixelColor(int(m + 3), int(m + 3.6 * 6 / 2))  # linker Rand des Kastens (vor dem Text), halbe Höhe
    assert c.red() > 150 and c.green() < 80, c.name()
    controller.toggle_privacy()  # Schwarz: keine Overlays
    pump()
    assert not win.isVisible()
    controller.toggle_privacy()
    pump()
    assert win.isVisible()
    controller.toggle_overlay_item(item["id"])  # einzelnes aus → keins mehr an → Fenster weg
    pump()
    assert not win.isVisible()
    controller.toggle_overlay_item(item["id"])
    controller.run_command("overlays")  # Befehl (Tastenkürzel, eigene Kachel, Handy): umschalten
    pump()
    assert not controller.config["overlays"]["on"] and not win.isVisible()
    from alupc.cast_server import ALLOWED_COMMANDS

    assert "overlays" in ALLOWED_COMMANDS


def test_overlay_music_uses_now_playing(env, monkeypatch):
    """Musik-Overlay: holt sich den Titel von „Läuft gerade“ (nur solange es an ist)."""
    controller, _window, _ = env
    from alupc.now_playing_view import feed

    f = feed()
    started = []
    monkeypatch.setattr(f, "acquire", lambda: started.append("an"))
    monkeypatch.setattr(f, "release", lambda: started.append("aus"))
    item = ov.from_template({"type": "music", "variant": "kompakt", "x": 0.0, "y": 1.0}, "Musik")
    controller.config["overlays"] = {"on": True, "items": [item]}
    controller.overlays_changed()
    assert started == ["an"]
    f.changed.emit(Track(title="Levitating", artist="Dua Lipa", player="Spotify", playing=True, length=200))
    assert controller.overlay_window.data.track.title == "Levitating"
    controller.set_overlays(False)
    assert started == ["an", "aus"]


def test_overlay_tiles_on_start_page(env):
    """Wie Bildschirmschoner-Kacheln: beliebig viele Overlay-Kacheln auf der Startseite, jede mit eigenem
    Overlay. Klick = einblenden, nochmal = aus – unabhängig von den Overlays aus dem Editor."""
    controller, window, _ = env
    from alupc.startpage import custom_key
    from alupc.ui.start_page_dialog import CustomTileDialog, StartPageDialog

    dlg = StartPageDialog(controller.config, window, controller)
    music = next(i for i, t in enumerate(ov.TEMPLATES) if t[1] == "Musik – kompakt")
    live = next(i for i, t in enumerate(ov.TEMPLATES) if t[1] == "LIVE")
    dlg.add_overlay(music)
    dlg.add_overlay(live)
    tiles = [t for t in dlg.cfg["custom"] if (t.get("action") or {}).get("kind") == "overlay"]
    assert [t["title"] for t in tiles] == ["Musik – kompakt", "LIVE"]
    assert all(custom_key(t) in dlg.cfg["tiles"] for t in tiles)
    # Kachel-Dialog: Aktion „Overlay“ bearbeitbar und wird gespeichert
    edit = CustomTileDialog(controller.config, tiles[1], "", dlg, controller)
    assert edit.kind.currentData() == "overlay"
    edit.overlay_data = dict(edit.overlay_data, text="AUF SENDUNG", x=0.5, y=0.0)
    edit._save()
    assert edit.tile["action"]["overlay"]["text"] == "AUF SENDUNG"
    tiles[1].update(edit.tile)
    dlg.accept()
    pump()
    controller.config["start_page"] = dlg.cfg
    controller.config["overlays"] = {"on": False, "items": []}
    controller.overlays_changed()
    win = controller.overlay_window
    live_id = tiles[1]["id"]
    controller.run_tile(live_id)
    pump()
    assert live_id in controller.tile_overlays and win.isVisible()
    assert [it["text"] for it in win.items()] == ["AUF SENDUNG"]
    controller.run_tile(tiles[0]["id"])  # zweite Kachel dazu
    assert len(win.items()) == 2
    controller.run_tile(live_id)  # nochmal klicken = aus
    assert live_id not in controller.tile_overlays and len(win.items()) == 1
    # Startseite gespeichert, Kachel gelöscht → ihr Overlay verschwindet
    controller.config["start_page"] = {**controller.config["start_page"],
                                       "custom": [t for t in controller.config["start_page"]["custom"]
                                                  if t["id"] != tiles[0]["id"]]}
    controller.refresh_tile_overlays()
    pump()
    assert not controller.tile_overlays and not win.isVisible()


def test_overlay_quick_add(env):
    """Schnellwahl unter der Vorschau: ein Klick legt die Vorlage an, schaltet Overlays ein und wählt sie aus."""
    controller, window, _ = env
    from alupc.ui.overlay_dialog import OverlayDialog

    dlg = OverlayDialog(controller, window)
    dlg.show()
    pump()
    buttons = [b for b in dlg.quick_row.findChildren(type(dlg.findChild(type(dlg.quick_row.children()[1]))))]
    assert [b.text() for b in buttons] == ["Musik", "Uhr", "Bauchbinde", "Laufschrift", "LIVE"]
    buttons[1].click()
    assert [it["type"] for it in dlg.items] == ["clock"] and dlg.enabled.isChecked()
    assert dlg.list.currentRow() == 0
    dlg.accept()
    pump()
    assert controller.config["overlays"]["items"][0]["type"] == "clock" and controller.overlay_window.isVisible()


def test_start_page_fits_window(env):
    """Startseite ragt nie rechts über den Rand: die Statuskarte zeigt je nach Platz Schalter mit Namen, nur
    Symbole oder alles untereinander."""
    controller, window, _ = env
    from PySide6.QtWidgets import QScrollArea

    controller.show_source({"type": "clock"})
    card = window.status_card
    for width, mode in ((1500, "voll"), (950, "mittel")):
        window.resize(width, 820)
        pump(30)
        card._recheck()
        pump(5)
        area = window.pages[0] if isinstance(window.pages[0], QScrollArea) else window.pages[0].findChild(QScrollArea)
        assert area.widget().width() <= area.viewport().width(), width  # nichts ragt rechts heraus
        assert card._mode == mode, (width, card._mode, card.width(), card._full_width())
        chips = list(card._chips())
        if mode == "voll":  # Namen ganz lesbar, kein Schalter gequetscht
            assert all(c.text() and c.width() >= c.sizeHint().width() - 1 for c in chips)
        else:
            assert not any(c.text() for c in chips) and all(c.toolTip() for c in chips)
    controller.extend()


def _mouse(widget, kind, pos: QPointF, buttons=Qt.LeftButton):
    ev = QMouseEvent(kind, pos, QPointF(widget.mapToGlobal(pos.toPoint())), Qt.LeftButton, buttons, Qt.NoModifier)
    {QMouseEvent.MouseButtonPress: widget.mousePressEvent, QMouseEvent.MouseMove: widget.mouseMoveEvent,
     QMouseEvent.MouseButtonRelease: widget.mouseReleaseEvent}[kind](ev)


def test_overlay_editor_drag_snap_and_forms(env):
    """Editor: jede Vorlage lässt sich einstellen; Ziehen verschiebt frei und rastet an Ecken/Mitte ein;
    Mausrad ändert die Größe; alles gilt sofort auf Monitor 2."""
    controller, window, _ = env
    from alupc.ui.overlay_dialog import OverlayDialog, TemplatePicker

    picker = TemplatePicker(window)
    assert sum(1 for i in range(picker.list.count()) if picker.list.item(i).data(Qt.UserRole) is not None) \
        == len(ov.TEMPLATES)
    picker.close()

    dlg = OverlayDialog(controller, window)
    dlg.resize(1180, 720)
    dlg.show()
    pump()
    for _cat, name, _d, tpl in ov.TEMPLATES:  # alle Arten: Einstellungen bauen sich ohne Fehler
        dlg.items.append(ov.from_template(tpl, name))
    dlg._fill_list()
    for row in range(len(dlg.items)):
        dlg.list.setCurrentRow(row)
        pump(1)
    # nur ein Overlay (Uhr) zum Ziehen
    dlg.items[:] = [ov.from_template({"type": "clock", "x": 1.0, "y": 1.0}, "Uhr")]
    dlg._fill_list()
    dlg.list.setCurrentRow(0)
    dlg.enabled.setChecked(True)
    pump()
    canvas = dlg.canvas
    (_it, r), = canvas.rects()
    area = canvas.area()
    start = r.center()
    _mouse(canvas, QMouseEvent.MouseButtonPress, start)
    # fast ganz nach oben links → rastet genau in der Ecke ein
    _mouse(canvas, QMouseEvent.MouseMove, start - QPointF(r.left() - area.left() - 3, r.top() - area.top() - 2))
    assert (dlg.items[0]["x"], dlg.items[0]["y"]) == (0.0, 0.0)
    # irgendwo dazwischen → bleibt dort (frei)
    target = QPointF(area.left() + area.width() * 0.3, area.top() + area.height() * 0.7)
    _mouse(canvas, QMouseEvent.MouseMove, target)
    x, y = dlg.items[0]["x"], dlg.items[0]["y"]
    assert 0.1 < x < 0.45 and 0.5 < y < 0.9 and ov.position_name(x, y) == "frei"
    _mouse(canvas, QMouseEvent.MouseButtonRelease, target, Qt.NoButton)
    (_it, r2), = canvas.rects()
    wheel = QWheelEvent(r2.center(), QPointF(canvas.mapToGlobal(r2.center().toPoint())), QPoint(0, 0), QPoint(0, 120),
                        Qt.NoButton, Qt.NoModifier, Qt.NoScrollPhase, False)
    canvas.wheelEvent(wheel)
    assert dlg.items[0]["size"] > 1.05
    dlg.accept()
    pump()
    saved = controller.config["overlays"]
    assert saved["on"] and saved["items"][0]["x"] == x and saved["items"][0]["size"] > 1.05
    assert controller.overlay_window.isVisible()
    rect = QRectF(controller.overlay_window._rects[0][1])
    assert rect.width() > 10
