"""KDE-Bildschirmaufnahme ohne Nachfrage (KWin ScreenShot2) gegen einen nachgebauten KWin-Dienst."""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent


@pytest.mark.skipif(not sys.platform.startswith("linux") or not shutil.which("dbus-run-session"),
                    reason="nur Linux mit dbus-run-session")
def test_kwin_capture_with_fake_kwin():
    pytest.importorskip("jeepney")
    proc = subprocess.run(["dbus-run-session", "--", sys.executable, str(HERE / "kwin_check.py")],
                          capture_output=True, text=True, timeout=120)
    assert "KWIN-OK" in proc.stdout and "CURSOR-OK" in proc.stdout, proc.stdout + proc.stderr


@pytest.mark.skipif(not sys.platform.startswith("linux") or not shutil.which("dbus-run-session"),
                    reason="nur Linux mit dbus-run-session")
def test_now_playing_with_fake_spotify():
    """„Läuft gerade“: nachgebauter Spotify-Player (MPRIS) – Titel/Cover/Zeit auslesen, Weiter/Pause, Anzeige."""
    pytest.importorskip("jeepney")
    proc = subprocess.run(["dbus-run-session", "--", sys.executable, str(HERE / "mpris_check.py")],
                          capture_output=True, text=True, timeout=120)
    assert "MPRIS-OK" in proc.stdout and "VIEW-OK" in proc.stdout, proc.stdout + proc.stderr
