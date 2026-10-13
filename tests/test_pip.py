"""Live-Ansicht von Monitor 2 auf Monitor 1 (Bild-in-Bild): Fenster verschieben/vergrößern, Vollbild auf Monitor 1,
„immer oben“ an/aus, Knöpfe im Fenster."""

from PySide6.QtCore import Qt

from test_gui import env, pump  # noqa: F401


def test_live_view_window_fullscreen_and_on_top(env):  # noqa: F811
    controller, window, _ = env
    pip = controller.pip
    pip.show_on_main()
    pump()
    assert pip.isVisible() and not pip.isFullScreen()
    small = pip.geometry()
    pip.enterEvent(None)  # Maus drin → Knöpfe
    assert pip.bar.isVisible() and pip.full_btn.text() == "Vollbild"
    pip.full_btn.click()  # Vollbild auf Monitor 1
    pump()
    assert pip.isFullScreen() and pip.full_btn.text() == "Fenster"
    assert pip.geometry() == controller.main_screen().geometry()
    pip.refresh()
    assert pip.view.image() is not None or pip.view._message  # zeigt Monitor 2 (oder „kein zweiter Monitor“)
    pip.toggle_fullscreen(False)  # Esc / „Fenster“
    pump()
    assert not pip.isFullScreen() and pip.geometry().size() == small.size()
    pip.top_btn.setChecked(False)  # nicht mehr immer oben
    pump()
    assert pip.isVisible() and not (pip.windowFlags() & Qt.WindowStaysOnTopHint)
    pip.top_btn.setChecked(True)
    pump()
    assert pip.windowFlags() & Qt.WindowStaysOnTopHint
    pip.mouseDoubleClickEvent(None)  # Doppelklick = Vollbild (früher: schließen)
    pump()
    assert pip.isFullScreen()
    pip.close_btn.click()
    pump()
    assert not pip.isVisible() and not pip.isFullScreen()
