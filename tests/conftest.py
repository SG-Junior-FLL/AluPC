import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("ALUPC_NO_ANIMATION", "1")
os.environ.setdefault("ALUPC_NO_AUTO_WIFI", "1")  # Tests starten kein echtes Spiele-WLAN  # Tests prüfen Zustände, nicht Übergänge (eigener Test dafür)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Chromium (QtWebEngine) verweigert als root den Start mit Sandbox – nur im Test-Container relevant
if hasattr(os, "geteuid") and os.geteuid() == 0:
    os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")


# Auf GitHub: fehlgeschlagene Tests zusätzlich als Anmerkung (::error::) ausgeben – die sind ohne
# Anmeldung sichtbar, die Protokolle nicht.
def pytest_runtest_logreport(report):
    if not os.environ.get("GITHUB_ACTIONS") or not report.failed:
        return
    text = str(report.longrepr).strip().splitlines()
    tail = " | ".join(line.strip() for line in text[-25:] if line.strip())
    tail = tail.replace("%", "%25").replace("\r", "").replace("\n", "%0A")
    sys.__stdout__.write(f"\n::error title={report.nodeid}::{tail[:3500]}\n")
    sys.__stdout__.flush()

# Wie beim echten Start: Videoplayer darf RTP/UDP lesen (AirPlay)
os.environ.setdefault("QT_FFMPEG_PROTOCOL_WHITELIST", "file,crypto,data,udp,rtp,http,https,tcp,tls")


import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _close_fake_servers():
    """Nach jedem Test die OpenRGB-Testserver schließen – sonst hängen Dutzende Threads bis zum Ende in accept()
    (Verdacht beim seltenen Segfault in der Linux-CI)."""
    yield
    try:
        import fake_openrgb
    except ImportError:
        return
    while fake_openrgb.ALIVE:
        fake_openrgb.ALIVE.pop().close()


def pytest_sessionfinish(session, exitstatus):
    """Am Ende alle übrig gebliebenen Fenster löschen, solange Qt (samt QML/WebEngine) noch läuft. Sonst räumt PySide
    sie erst beim Beenden von Python auf – in falscher Reihenfolge; das gab selten einen Segfault nach allen Tests
    (gdb: destroyQCoreApplication → ~QWidget → ~QQmlData → ~QPropertyObserver)."""
    try:
        from PySide6.QtCore import QCoreApplication, QEvent
        from PySide6.QtWidgets import QApplication
    except ImportError:
        return
    app = QApplication.instance()
    if not isinstance(app, QApplication):  # keine oder nur QGuiApplication/QCoreApplication (Windows-Logiktests)
        return
    for widget in app.topLevelWidgets():
        widget.close()
        widget.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()
    import gc

    gc.collect()


@pytest.fixture(autouse=True)
def _hang_guard(request):
    """CI: hängt ein Test (ALUPC_TEST_HANG_EXIT Sekunden), alle Stapel in gui-haenger.txt schreiben und hart beenden –
    statt still bis zum Zeitlimit des Laufs zu warten (der Schritt meldet die Datei dann als Fehler)."""
    seconds = int(os.environ.get("ALUPC_TEST_HANG_EXIT") or 0)
    if not seconds:
        yield
        return
    import faulthandler

    with open("gui-haenger.txt", "w", encoding="utf-8") as f:
        f.write(f"Test hängt: {request.node.nodeid}\n")
        f.flush()
        faulthandler.dump_traceback_later(seconds, exit=True, file=f)
        try:
            yield
        finally:
            faulthandler.cancel_dump_traceback_later()
