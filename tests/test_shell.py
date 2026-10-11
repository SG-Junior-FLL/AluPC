"""AluPC-Oberfläche (Vollbild statt Desktop): Programme, Suche/„Frag AluPC“, Anheften, Verlassen, Tastenkürzel."""

import time

from test_gui import env  # noqa: F401


def _pump(sec=0.3):
    from PySide6.QtWidgets import QApplication

    t = time.monotonic()
    while time.monotonic() - t < sec:
        QApplication.processEvents()
        time.sleep(0.01)


def test_shell(env, monkeypatch, tmp_path):  # noqa: F811
    controller, window, _ = env
    import alupc.pc_control as pc

    apps = []
    for name in ("Firefox", "Spotify", "Zoom", "GIMP"):
        f = tmp_path / f"{name}.desktop"
        f.write_text(f"[Desktop Entry]\nType=Application\nName={name}\nExec=true\nIcon=firefox\n")
        apps.append((name, str(f)))
    launched = []
    monkeypatch.setattr(pc, "installed_apps", lambda: apps)
    monkeypatch.setattr(pc, "get_volume", lambda: 40)
    monkeypatch.setattr(pc, "launch_installed", lambda n: (launched.append(n), (True, ""))[1])
    from alupc.config import DEFAULT_HOTKEYS
    from alupc.startpage import COMMANDS

    assert DEFAULT_HOTKEYS["oberflaeche"] == "Ctrl+Alt+O" and "oberflaeche" in COMMANDS
    controller.run_command("oberflaeche")  # Befehl/Tastenkürzel → Oberfläche auf
    sh = window.shell
    assert sh is not None and sh.isVisible()
    _pump(0.6)
    assert [t.app_name for t in sh._tiles] == ["Firefox", "GIMP", "Spotify", "Zoom"]
    assert sh.volume.value() == 40 and "CPU" in sh.status.text() and sh.clock.text()
    sh._pin("Zoom", True)  # angeheftet → nach vorne
    assert sh._tiles[0].app_name == "Zoom" and sh._tiles[0].text().startswith("★")
    sh.search.setText("spo")
    assert [t.app_name for t in sh._tiles if not t.property("hide")] == ["Spotify"]
    sh._enter()  # genau ein Treffer → starten, Oberfläche geht zur Seite
    assert launched == ["Spotify"] and not sh.isVisible()
    window.toggle_shell(True)
    sh.search.setText("Timer 3 Minuten")  # kein Programm → AluPC versteht den Satz
    sh._enter()
    assert "3 Minuten" in sh.answer.text()
    sh._run("schwarz")
    assert controller.privacy
    controller.run_command("schwarz")
    sh.leave()
    assert not sh.isVisible() and controller.config["shell"]["open"] is False
    assert controller.config["shell"]["pinned"] == ["Zoom"]
