"""„Erweitern“ (Monitor 2 = normaler Bildschirm): Handy-Live-Bild, virtuelle Kamera und Live-Ansicht zeigen den echten
Bildschirm – kein Hinweistext mehr. Die Aufnahme selbst ist hier nachgebaut (im Test gibt es keinen echten Monitor)."""

import time

from test_gui import env, pump  # noqa: F401 – gleiche Test-Umgebung wie die GUI-Tests

from PySide6.QtGui import QColor, QImage


class FakeScreen:
    made = []

    def __init__(self, cfg, parent=None):
        self.cfg, self.stopped, self.problem = cfg, False, ""
        FakeScreen.made.append(self)

    def image(self):
        img = QImage(1280, 720, QImage.Format_RGB32)
        img.fill(QColor("#ff0000"))
        return img

    def stop(self):
        self.stopped = True

    def deleteLater(self):
        pass


def _center(img: QImage) -> QColor:
    return QColor(img.pixel(img.width() // 2, img.height() // 2))


def test_extend_shows_real_screen_everywhere(env, monkeypatch):  # noqa: F811
    from alupc import sources

    from PySide6.QtGui import QGuiApplication

    controller, window, _ = env
    FakeScreen.made.clear()
    monkeypatch.setattr(sources, "ScreenSource", FakeScreen)
    monkeypatch.setattr(QGuiApplication, "platformName", staticmethod(lambda: "xcb"))  # wie mit echtem Bildschirm
    controller.extend()
    pump()
    assert not controller.output.isVisible()
    # Handy-Live-Bild
    jpeg = controller._preview_jpeg()
    img = QImage.fromData(jpeg, "JPEG")
    c = _center(img)
    assert c.red() > 200 and c.green() < 60, c.name()
    # virtuelle Kamera
    frame = controller.vcam.frame_image(1280, 720)
    assert _center(frame).red() > 200 and frame.width() == 1280
    # eine gemeinsame Aufnahme für alles, auf Monitor 2
    assert len(FakeScreen.made) == 1 and FakeScreen.made[0].cfg["screen_name"] == controller.output_screen().name()
    # niemand schaut mehr zu → hört von selbst auf
    controller.monitor_feed.used = time.monotonic() - 60
    controller.monitor_feed._check_idle()
    assert FakeScreen.made[0].stopped and not controller.monitor_feed.running()


def test_no_capture_shows_dark_image_with_small_reason(env, monkeypatch):  # noqa: F811
    from alupc import sources

    class Broken(FakeScreen):
        def __init__(self, cfg, parent=None):
            super().__init__(cfg, parent)
            self.problem = "Unter Wayland sieht diese Aufnahme keine Fenster."

        def image(self):
            return None

    from PySide6.QtGui import QGuiApplication

    controller, window, _ = env
    monkeypatch.setattr(sources, "ScreenSource", Broken)
    monkeypatch.setattr(QGuiApplication, "platformName", staticmethod(lambda: "xcb"))
    controller.extend()
    pump()
    img = QImage.fromData(controller._preview_jpeg(), "JPEG")
    assert _center(img).lightness() < 40  # kein großer Hinweistext mehr in der Mitte
    controller.monitor_feed.stop()
