"""Läuft in einem eigenen D-Bus (dbus-run-session): „Läuft gerade“ gegen einen nachgebauten Spotify-Player.
Gibt „MPRIS-OK“ und „VIEW-OK“ aus, wenn Auslesen, Steuern und Anzeigen klappen."""

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("ALUPC_NO_ANIMATION", "1")

from PySide6.QtGui import QColor, QImage  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication([])
cover = Path(tempfile.mkdtemp()) / "cover.png"
img = QImage(64, 64, QImage.Format_RGB32)
img.fill(QColor("#e11d48"))
img.save(str(cover))
fake = subprocess.Popen([sys.executable, str(HERE / "fake_mpris.py"), str(cover)], stdout=subprocess.PIPE, text=True)
assert fake.stdout.readline().strip() == "bereit"
try:
    from alupc import now_playing

    r = now_playing.reader()
    t = r.read()
    assert (t.title, t.artist, t.album, t.player, t.playing) == \
        ("Blinding Lights", "The Weeknd", "After Hours", "Spotify", True), t
    assert t.length == 200 and 41 <= t.position_now() <= 44 and t.art.startswith(b"\x89PNG"), t
    assert r.control("next") and r.read().title == "Levitating"
    assert r.control("play_pause") and not r.read().playing
    assert r.control("play_pause") and r.control("previous") and r.read().title == "Blinding Lights"
    r.close()
    print("MPRIS-OK", flush=True)

    from alupc.now_playing_view import NowPlayingSource, feed

    view = NowPlayingSource({})
    view.resize(640, 360)
    view.show()
    end = time.time() + 8
    while (view.track is None or view.track.title != "Blinding Lights") and time.time() < end:
        app.processEvents()
        time.sleep(0.02)
    assert view.track is not None and view.track.title == "Blinding Lights", view.track
    shot = view.grab().toImage()
    # Hintergrund = abgedunkeltes Cover (rötlich), Cover selbst links groß und kräftig rot
    c = shot.pixelColor(int(640 * 0.08 + 40), 180)
    assert c.red() > 180 and c.green() < 80, c.name()
    feed().control("next")  # über die Hintergrund-Abfrage (so steuern Kachel und Handy)
    end = time.time() + 8
    while view.track.title != "Levitating" and time.time() < end:
        app.processEvents()
        time.sleep(0.02)
    assert view.track.title == "Levitating", view.track
    view.stop()
    print("VIEW-OK", flush=True)
finally:
    fake.terminate()
    fake.wait()
