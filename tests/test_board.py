"""Whiteboard als Notizbuch (board.py): Seiten, Stift mit Druck, Formen, Radierer, Lasso, Rückgängig, Zoom,
Speichern/Laden, Export – und dass Handy und Monitor 2 dieselbe Tafel benutzen."""

import json

import pytest
from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QColor, QImage, QPainter

from test_gui import env  # noqa: F401


@pytest.fixture()
def qapp():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


@pytest.fixture
def board(qapp, tmp_path, monkeypatch):
    from alupc import board as bm

    monkeypatch.setattr(bm, "boards_dir", lambda: tmp_path / "Tafeln")

    class Cfg:
        def __init__(self):
            self.data = {"whiteboard": {"smooth": 0}}

        def __getitem__(self, k):
            return self.data[k]

        def __setitem__(self, k, v):
            self.data[k] = v

    return bm.Board(Cfg())


def _stroke(b, tool="pen", pts=((100, 100), (200, 120), (300, 160)), pressure=0.5, color="#111827"):
    b.input("down", *pts[0], pressure, tool, color)
    for x, y in pts[1:]:
        b.input("move", x, y, pressure, tool, color)
    b.input("up", *pts[-1], pressure, tool, color)


def test_pen_shapes_eraser_undo(board):
    _stroke(board)
    assert len(board.strokes) == 1 and board.strokes[0]["t"] == "pen" and len(board.strokes[0]["p"]) == 3
    _stroke(board, "rect", ((400, 400), (600, 500)))
    _stroke(board, "arrow", ((50, 800), (500, 800)))
    assert [s["t"] for s in board.strokes] == ["pen", "rect", "arrow"]
    board.input("down", 500, 400, tool="eraser")  # trifft die Rechteck-Kante
    board.input("up", 500, 400, tool="eraser")
    assert [s["t"] for s in board.strokes] == ["pen", "arrow"]
    board.input("down", 1000, 50, tool="eraser")  # trifft nichts → kein leerer Rückgängig-Schritt
    board.input("up", 1000, 50, tool="eraser")
    board.undo()
    assert [s["t"] for s in board.strokes] == ["pen", "rect", "arrow"]
    board.redo()
    assert [s["t"] for s in board.strokes] == ["pen", "arrow"]
    board.add_text(100, 600, "Hallo", "#ef4444")
    assert board.strokes[-1]["text"] == "Hallo"


def test_pressure_and_smoothing(board):
    _stroke(board, pts=((0, 0), (10, 0), (20, 0)), pressure=0.9)
    assert all(pt[2] == 0.9 for pt in board.strokes[0]["p"])
    board.set_settings(pressure=False, smooth=2)
    _stroke(board, pts=((0, 100), (100, 100)), pressure=0.9)
    last = board.strokes[-1]["p"]
    assert last[-1][2] == 0.5 and last[-1][0] < 100  # ohne Druck = mittel, geglättet = hinkt nach


def test_lasso_select_move_delete(board):
    _stroke(board, pts=((100, 100), (150, 120)))
    _stroke(board, pts=((900, 600), (950, 620)))
    for phase, (x, y) in zip(("down", "move", "move", "move", "up"),
                             ((50, 50), (300, 50), (300, 300), (50, 300), (50, 50))):
        board.input(phase, x, y, tool="lasso")
    assert board.sel == [0]
    board.input("down", 120, 110, tool="lasso")  # in die Auswahl → verschieben
    board.input("move", 220, 160, tool="lasso")
    board.input("up", 220, 160, tool="lasso")
    assert board.strokes[0]["p"][0][:2] == [200.0, 150.0]
    board.delete_selection()
    assert len(board.strokes) == 1 and board.strokes[0]["p"][0][:2] == [900, 600]


def test_pages_view_and_coordinates(board):
    board.new_page()
    board.new_page()
    assert len(board.doc["pages"]) == 3 and board.doc["page"] == 2
    board.goto(0)
    board.aspect = 16 / 9
    assert board.to_world(0.5, 0.5) == QPointF(800, 450)
    assert abs(board.to_world(0, 0).x()) < 1e-6 and abs(board.to_world(1, 1).y() - 900) < 1e-6
    anchor = board.to_world(0.25, 0.25)
    board.set_zoom(2.0, anchor)  # Punkt unter dem Finger bleibt an Ort und Stelle
    again = board.to_world(0.25, 0.25)
    assert abs(again.x() - anchor.x()) < 1e-6 and abs(again.y() - anchor.y()) < 1e-6
    board.set_zoom(100)
    assert board.zoom == 8.0
    board.fit()
    assert board.zoom == 1.0 and board.to_world(0.5, 0.5) == QPointF(800, 450)
    board.pan_screen(0.1, 0)
    assert board.to_world(0.5, 0.5).x() < 800  # Inhalt nach rechts → Mitte zeigt weiter links


def test_save_load_export(board, tmp_path):
    _stroke(board)
    board.set_background("kariert")
    board.new_page()
    path = board.save()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert len(data["pages"]) == 2 and data["pages"][0]["bg"] == "kariert"
    board.new_board("Mathe")
    assert board.doc["name"] == "Mathe" and board.strokes == []
    assert board.load("Tafel 1") and len(board.doc["pages"]) == 2 and board.doc["pages"][0]["strokes"]
    png, pdf = tmp_path / "s.png", tmp_path / "t.pdf"
    assert board.export_png(str(png)) and QImage(str(png)).width() == 1920
    assert board.export_pdf(str(pdf)) and pdf.read_bytes()[:4] == b"%PDF"
    assert set(board.boards()) == {"Tafel 1", "Mathe"}


def test_paint_board_shows_strokes_and_zoom(board):
    board.input("down", 700, 450, 0.5, "pen", "#ef4444", 12)
    board.input("move", 800, 450, 0.5, "pen", "#ef4444", 12)
    board.input("up", 800, 450, 0.5, "pen", "#ef4444", 12)
    img = QImage(640, 360, QImage.Format_RGB32)
    from alupc.board import paint_board

    def red_pixels():
        img.fill(QColor("#000000"))
        p = QPainter(img)
        paint_board(p, QRectF(0, 0, 640, 360), board)
        p.end()
        return sum(1 for x in range(640) for y in range(360)
                   if QColor(img.pixel(x, y)).red() > 180 and QColor(img.pixel(x, y)).green() < 110)

    normal = red_pixels()
    board.set_zoom(3.0)
    assert normal > 5 and red_pixels() > normal * 3  # hineingezoomt = Strich viel größer


def test_phone_draws_on_board_and_controls_view(env):  # noqa: F811
    controller, _window, _ = env
    b = controller.board
    controller.show_whiteboard("liniert", draw=False)
    assert controller.whiteboard_active() and b.page["bg"] == "liniert"
    n = len(b.strokes)
    for phase, x in (("down", 0.4), ("move", 0.5), ("move", 0.6), ("up", None)):
        req = {"kind": "draw", "phase": phase, "tool": "stift", "color": "#3b82f6", "pressure": 0.8}
        if x is not None:
            req.update(x=x, y=0.5)
        controller._cast_request(req)
    assert len(b.strokes) == n + 1 and b.strokes[-1]["c"] == "#3b82f6"
    assert not controller.laser.strokes or controller.laser.strokes[-1].get("color") != "#3b82f6"
    controller._cast_request({"kind": "board", "op": "view", "zoom": 2.0, "ax": 0.5, "ay": 0.5})
    assert b.zoom == 2.0
    controller._cast_request({"kind": "board", "op": "seite_neu"})
    assert b.doc["page"] == 1 and controller.board_state()["pages"] >= 2
    controller._cast_request({"kind": "board", "op": "rueckgaengig"})
    controller.run_command("tafel_fit")
    assert b.zoom == 1.0
    controller.extend()


def test_board_window_draw_zoom_pages_settings(env):  # noqa: F811
    """Whiteboard-Fenster: mit der Maus zeichnen (landet auf der Tafel von Monitor 2), Strg+Mausrad zoomt an der
    Mausstelle, Seiten-Leiste, Werkzeuge per Taste, Einstellungen wirken sofort."""
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtGui import QMouseEvent, QWheelEvent
    from PySide6.QtWidgets import QApplication

    controller, window, _ = env
    controller.show_whiteboard()  # öffnet das Fenster (statt „Zeigen & Zeichnen“)
    win = window.board_window
    assert win.isVisible() and controller.whiteboard_active()
    b = controller.board
    b.goto(0)
    b.clear()
    c = win.canvas
    QApplication.processEvents()
    r = c.area()

    def mouse(kind, pos, buttons=Qt.LeftButton):
        ev = QMouseEvent(kind, pos, c.mapToGlobal(pos.toPoint()), Qt.LeftButton, buttons, Qt.NoModifier)
        {QMouseEvent.MouseButtonPress: c.mousePressEvent, QMouseEvent.MouseMove: c.mouseMoveEvent,
         QMouseEvent.MouseButtonRelease: c.mouseReleaseEvent}[kind](ev)

    a, z = r.center() - QPointF(60, 0), r.center() + QPointF(60, 20)
    mouse(QMouseEvent.MouseButtonPress, a)
    for i in range(1, 6):
        mouse(QMouseEvent.MouseMove, a + (z - a) * (i / 5))
    mouse(QMouseEvent.MouseButtonRelease, z, Qt.NoButton)
    assert len(b.strokes) == 1 and b.strokes[0]["t"] == "pen"
    first = b.strokes[0]["p"][0]
    assert abs(first[0] - c.to_world(a).x()) < 2  # Welt-Koordinaten stimmen mit der Stelle überein
    win.set_tool("shape")
    win.shape = "rect"
    mouse(QMouseEvent.MouseButtonPress, r.topLeft() + QPointF(40, 40))
    mouse(QMouseEvent.MouseMove, r.topLeft() + QPointF(140, 120))
    mouse(QMouseEvent.MouseButtonRelease, r.topLeft() + QPointF(140, 120), Qt.NoButton)
    assert b.strokes[-1]["t"] == "rect"
    spot = r.center() + QPointF(100, 50)
    before = c.to_world(spot)
    wheel = QWheelEvent(spot, c.mapToGlobal(spot.toPoint()), QPoint(), QPoint(0, 120), Qt.NoButton,
                        Qt.ControlModifier, Qt.NoScrollPhase, False)
    c.wheelEvent(wheel)
    assert b.zoom > 1.0
    after = c.to_world(spot)
    assert abs(after.x() - before.x()) < 0.5 and abs(after.y() - before.y()) < 0.5  # zoomt an der Maus
    win.board.new_page()
    win._thumbs()
    assert win.pages.count() == len(b.doc["pages"]) and win.page_lab.text().startswith(f"{b.doc['page'] + 1} /")
    from alupc.ui.board_settings import board_settings_widget

    form = board_settings_widget(b)
    form.controls["pencil_only"].setChecked(True)
    form.controls["format"].setCurrentIndex(form.controls["format"].findData("a4"))
    assert b.settings()["pencil_only"] and b.page_size() == (1240.0, 1754.0)
    form.controls["format"].setCurrentIndex(form.controls["format"].findData("16:9"))
    # Papier-Knopf: Menü setzt den Hintergrund der Seite; Leiste wird nie gequetscht, Fenster passt auf 1024 px
    act = next(a for a in win.bg_btn.menu().actions() if a.data() == "liniert")
    act.trigger()
    assert b.page["bg"] == "liniert" and act.isChecked()
    win.resize(1024, 700)
    QApplication.processEvents()
    assert win.width() <= 1024 and win.menu_btn.width() >= win.menu_btn.sizeHint().width()
    win.close()
    controller.extend()
