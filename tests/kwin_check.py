"""Läuft in einer eigenen D-Bus-Sitzung (dbus-run-session) gegen fake_kwin.py."""

import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
os.environ.update(XDG_SESSION_TYPE="wayland", XDG_CURRENT_DESKTOP="KDE", QT_QPA_PLATFORM="offscreen")


def start(mode):
    proc = subprocess.Popen([sys.executable, str(HERE / "fake_kwin.py"), mode], stdout=subprocess.PIPE, text=True)
    assert proc.stdout.readline().strip() == "bereit"
    return proc


from PySide6.QtGui import QColor, QGuiApplication  # noqa: E402

app = QGuiApplication([])
from alupc.platform import kwin_capture  # noqa: E402

fake = start("verboten")
assert kwin_capture.allowed("DP-1") is False, "verboten muss abgelehnt werden"
assert "NoAuthorized" in kwin_capture.last_error()
fake.kill()
fake.wait()

fake = start("erlaubt")
kwin_capture._state.update(allowed=None, checked=0.0)
assert kwin_capture.allowed("DP-1") is True, kwin_capture.last_error()
img = kwin_capture.grab_once("DP-1")
assert (img.width(), img.height()) == (64, 32)
assert img.pixelColor(3, 3) == QColor("#ff0000"), img.pixelColor(3, 3).name()
assert img.pixelColor(3, 31) == QColor("#00ff00")

# Laufende Aufnahme im Thread
feed = kwin_capture.KWinScreenFeed("DP-1", fps=30)
frames = []
feed.frame.connect(lambda im: (frames.append(im), feed.frame_taken()))
feed.start()
end = time.time() + 5
while len(frames) < 5 and time.time() < end:
    app.processEvents()
    time.sleep(0.01)
feed.stop()
assert len(frames) >= 5, len(frames)
fake.kill()
print("KWIN-OK")
