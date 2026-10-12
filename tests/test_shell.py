"""AluPC-Oberfläche (eigener Desktop): Desktop-Ordner als Symbole (frei verschiebbar, neue Dateien erscheinen),
Taskleiste mit Startmenü (Suche/„Frag AluPC“, Anheften), Widgets, Anpassen, Verlassen, Tastenkürzel."""

import time

from PySide6.QtCore import QPoint

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
    from alupc.ui import shell_desktop

    apps = []
    for name in ("Firefox", "Spotify", "Zoom", "GIMP"):
        f = tmp_path / f"{name}.desktop"
        f.write_text(f"[Desktop Entry]\nType=Application\nName={name}\nExec=true\nIcon=firefox\n")
        apps.append((name, str(f)))
    desk = tmp_path / "Desktop"
    desk.mkdir()
    (desk / "Fotos").mkdir()
    (desk / "Notizen.txt").write_text("hallo")
    (desk / ".versteckt").write_text("x")
    (desk / "desktop.ini").write_text("x")
    (desk / "Spiel.desktop").write_text("[Desktop Entry]\nType=Application\nName=Mein Spiel\nExec=true\n")
    monkeypatch.setattr(shell_desktop, "desktop_dirs", lambda: [desk])
    opened = []
    monkeypatch.setattr(shell_desktop, "open_entry", lambda e: (opened.append(e["name"]), True)[1])
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
    _pump(0.8)
    # Desktop-Ordner: Ordner, Datei, Programm – Verstecktes und desktop.ini nicht
    names = sorted(ic.entry["name"] for ic in sh.area.icons)
    assert names == ["Fotos", "Mein Spiel", "Notizen.txt"]
    kinds = {ic.entry["name"]: ic.entry["kind"] for ic in sh.area.icons}
    assert kinds == {"Fotos": "folder", "Mein Spiel": "app", "Notizen.txt": "file"}
    # frei verschiebbar (am Raster), Position bleibt gespeichert
    icon = next(ic for ic in sh.area.icons if ic.entry["name"] == "Fotos")
    icon.moved.emit(icon.move_key, QPoint(400, 300))
    saved = controller.config["shell"]["pos"][icon.move_key]
    assert 0 < saved[0] < 1 and 0 < saved[1] < 1
    sh.area.reload()
    again = next(ic for ic in sh.area.icons if ic.entry["name"] == "Fotos")
    assert abs(again.x() - icon.x()) <= 2 and abs(again.y() - icon.y()) <= 2
    again.opened.emit(again.entry)  # Doppelklick öffnet
    assert opened == ["Fotos"]
    window.toggle_shell(True)
    # neue Datei auf dem Desktop erscheint von selbst
    (desk / "Neu.pdf").write_text("x")
    _pump(1.2)
    assert any(ic.entry["name"] == "Neu.pdf" for ic in sh.area.icons)
    # Startmenü: Programme, Anheften (auch in der Taskleiste), Suche
    assert [t.app_name for t in sh._tiles] == ["Firefox", "GIMP", "Spotify", "Zoom"]
    assert sh.volume.value() == 40 and "CPU" in sh.status.text() and sh.clock.text()
    sh._pin("Zoom", True)
    assert sh._tiles[0].app_name == "Zoom" and sh._tiles[0].text().startswith("★")
    assert [b.toolTip() for b in sh.pinned_buttons] == ["Zoom"]
    sh.toggle_menu()
    assert sh.menu.isVisible()
    sh.search.setText("spo")
    assert [t.app_name for t in sh._tiles if not t.property("hide")] == ["Spotify"]
    sh._enter()  # genau ein Treffer → starten, Oberfläche geht zur Seite
    assert launched == ["Spotify"] and not sh.isVisible()
    window.toggle_shell(True)
    sh.search.setText("Timer 3 Minuten")  # kein Programm → AluPC versteht den Satz
    sh._enter()
    assert "3 Minuten" in sh.answer.text()
    sh._run("schwarz")
    assert controller.privacy and sh.mon_buttons["schwarz"].isChecked()
    controller.run_command("schwarz")
    # Anpassen: Widgets aus, Taskleiste links, Esc schließt
    from alupc.ui.shell_settings import ShellSettings

    dlg = ShellSettings(sh)
    dlg.wchecks["quick"].setChecked(False)
    dlg.center.setChecked(False)
    assert not sh.quick_w.isVisible() and not sh.bar.lead.isVisible()
    assert controller.config["shell"]["widgets"]["quick"] is False
    sh._escape()  # Esc schließt nur, wenn eingestellt
    assert sh.isVisible()
    dlg.esc.setChecked(True)
    dlg.close()
    sh._escape()
    assert not sh.isVisible() and controller.config["shell"]["open"] is False
    assert controller.config["shell"]["pinned"] == ["Zoom"]


def test_icon_lookup_without_theme(tmp_path, monkeypatch):
    """Linux: Logo aus dem Icon-Ordner, auch wenn Qt kein Icon-Theme kennt (größtes/scalable gewinnt)."""
    from alupc.ui import shell_desktop as sd

    base = tmp_path / "icons"
    for sub in ("hicolor/48x48/apps", "hicolor/256x256/apps", "hicolor/scalable/apps"):
        (base / sub).mkdir(parents=True)
    (base / "hicolor/48x48/apps/meinprog.png").write_bytes(b"x")
    (base / "hicolor/256x256/apps/meinprog.png").write_bytes(b"x")
    (base / "hicolor/256x256/apps/anderes.png").write_bytes(b"x")
    monkeypatch.setattr(sd, "_icon_dirs", lambda: [base])
    sd.icon_index.cache_clear()
    try:
        idx = sd.icon_index()
        assert idx["meinprog"].endswith("256x256/apps/meinprog.png")
        f = tmp_path / "p.desktop"
        f.write_text("[Desktop Entry]\nType=Application\nName=P\nIcon=meinprog\n")
        monkeypatch.setattr(sd, "IS_WINDOWS", False)
        assert sd.icon_file_for(str(f)).endswith("256x256/apps/meinprog.png")
    finally:
        sd.icon_index.cache_clear()
