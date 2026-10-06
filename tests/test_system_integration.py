"""Einbindung ins System: Rechtsklick „Auf Monitor 2 zeigen“ und alupc://-Links."""

import os
import sys

import pytest

from alupc.app import parse_args, startup_command
from alupc.platform import system_integration as si


def test_url_commands_only_harmless():
    assert si.url_command("alupc://standbild") == "standbild"
    assert si.url_command("alupc://Standbild/") == "standbild"
    assert si.url_command("alupc:schwarz") == "schwarz"
    assert si.url_command("alupc://naechste-szene") == "naechste_szene"
    assert si.url_command("alupc://bild-in-bild") == "bild-in-bild"
    assert si.url_command("alupc://szene/Pause%20mit%20Musik") == "szene:Pause mit Musik"
    assert si.url_command("alupc://") == "zeigen"
    for bad in ("alupc://pc_herunterfahren", "alupc://kachel/cmd", "alupc://datei/etc/passwd",
                "alupc://sperren", "alupc://pc_lauter", "http://standbild"):
        assert si.url_command(bad) is None, bad


def test_file_source(tmp_path):
    (tmp_path / "a.JPG").write_bytes(b"x")
    (tmp_path / "b.mkv").write_bytes(b"x")
    (tmp_path / "c.pdf").write_bytes(b"x")
    (tmp_path / "d.txt").write_bytes(b"x")
    assert si.file_source(str(tmp_path / "a.JPG"))["type"] == "image"
    assert si.file_source(str(tmp_path / "b.mkv")) == {"type": "video", "path": str(tmp_path / "b.mkv"), "loop": True}
    assert si.file_source(str(tmp_path / "c.pdf"))["url"].startswith("file:")
    assert si.file_source(str(tmp_path))["type"] == "slideshow"
    assert si.file_source(str(tmp_path / "d.txt")) is None
    assert si.file_source(str(tmp_path / "fehlt.png")) is None


def test_startup_command(tmp_path):
    def cmd(*argv):
        return startup_command(parse_args(list(argv)))

    assert cmd() is None
    assert cmd("--befehl", "schwarz") == "schwarz"
    assert cmd("--zeigen", str(tmp_path / "a b.png")) == "datei:" + str(tmp_path / "a b.png")
    assert cmd("alupc://standbild") == "standbild"
    assert cmd("alupc://pc_herunterfahren").startswith("link_unbekannt:")
    assert cmd(str(tmp_path / "x.mp4")) == "datei:" + str(tmp_path / "x.mp4")


@pytest.mark.skipif(sys.platform.startswith("win"), reason="Linux-Dateien")
def test_linux_files_on_off(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    mimeapps = tmp_path / "cfg" / "mimeapps.list"
    mimeapps.parent.mkdir(parents=True)
    mimeapps.write_text("[Default Applications]\ntext/html=firefox.desktop\n\n[Added Associations]\nx=y.desktop\n")
    assert not si.is_active()
    ok, msg = si.set_enabled(True)
    assert ok and si.is_active() and "Dolphin" in msg
    menu = tmp_path / "data" / "kio" / "servicemenus" / "alupc-monitor2.desktop"
    text = menu.read_text()
    assert "Name=Auf Monitor 2 zeigen" in text and "--zeigen %f" in text and "MimeType=inode/directory;" in text
    assert os.access(menu, os.X_OK)
    assert (tmp_path / "data" / "kservices5" / "ServiceMenus" / "alupc-monitor2.desktop").is_file()
    link = (tmp_path / "data" / "applications" / "alupc-link.desktop").read_text()
    assert "MimeType=x-scheme-handler/alupc;" in link and " %u" in link
    lines = mimeapps.read_text().splitlines()
    assert "x-scheme-handler/alupc=alupc-link.desktop" in lines and "text/html=firefox.desktop" in lines
    si.set_enabled(True)  # zweimal → kein doppelter Eintrag
    assert mimeapps.read_text().count("x-scheme-handler/alupc=") == 1
    # Desktop-Dateien sind gültig (wenn das Prüfprogramm da ist)
    import shutil
    import subprocess

    if shutil.which("desktop-file-validate"):
        r = subprocess.run(["desktop-file-validate", str(tmp_path / "data" / "applications" / "alupc-link.desktop")],
                           capture_output=True, text=True)
        assert "error" not in r.stdout.lower(), r.stdout
    ok, _ = si.set_enabled(False)
    assert ok and not si.is_active() and not menu.exists()
    assert "alupc" not in mimeapps.read_text() and "text/html=firefox.desktop" in mimeapps.read_text()


def test_sync_follows_setting(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    calls = []
    monkeypatch.setattr(si, "set_enabled", lambda on: calls.append(on) or (True, ""))
    monkeypatch.setattr(si, "is_active", lambda: False)
    si.sync({"system_integration": True})
    si.sync({"system_integration": False})
    assert calls == [True]


def test_windows_entries():
    e = si.windows_entries()
    assert e[r"SystemFileAssociations\image\shell\AluPC.Monitor2"]["MUIVerb"] == "Auf Monitor 2 zeigen"
    assert e[r"Directory\shell\AluPC.Monitor2"]["MUIVerb"] == "Als Diashow auf Monitor 2"
    assert e[r"SystemFileAssociations\.pdf\shell\AluPC.Monitor2\command"][""].endswith('--zeigen "%1"')
    assert e["alupc"]["URL Protocol"] == "" and e[r"alupc\shell\open\command"][""].endswith('"%1"')
