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


def test_shell_as_system_desktop(env, monkeypatch, tmp_path):  # noqa: F811
    """Als System-Desktop: Oberfläche ganz unten (hinter Programmen), Taskleiste als eigene Leiste oben, Programm
    starten lässt den Desktop stehen, Knopf „Normaler Desktop“ startet Explorer/Plasma und erst DANN verschwindet
    die Oberfläche (nie schwarzer Bildschirm). Ging der normale Desktop nicht, bleibt AluPC sichtbar."""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QMessageBox

    import alupc.pc_control as pc
    from alupc.platform import desktop_shell as ds
    from alupc.ui import shell_desktop

    controller, window, _ = env
    monkeypatch.setattr(shell_desktop, "desktop_dirs", lambda: [tmp_path])
    monkeypatch.setattr(pc, "installed_apps", lambda: [])
    monkeypatch.setattr(pc, "get_volume", lambda: 40)
    monkeypatch.setattr(pc, "launch_installed", lambda n: (True, ""))
    calls = []
    normal = {"ok": True}
    monkeypatch.setattr(ds, "stop_normal", lambda: calls.append("stop") or (True, "AluPC-Desktop ist zurück."))
    monkeypatch.setattr(ds, "start_normal", lambda: calls.append("start") or
                        ((True, "Normaler Desktop läuft.") if normal["ok"] else (False, "ging nicht")))
    monkeypatch.setattr(ds, "set_work_area", lambda *a: calls.append(("area", a)))
    monkeypatch.setattr(ds, "normal_running", lambda: False)
    monkeypatch.setattr(ds, "run_startup_programs", lambda: calls.append("autostart") or [])

    def wait_for(cond, sec=3):
        end = time.monotonic() + sec
        while time.monotonic() < end and not cond():
            _pump(0.05)
        return cond()

    window.system_desktop(True)
    sh = window.shell
    assert wait_for(lambda: "stop" in calls)
    assert sh.system and sh.isVisible() and sh.windowFlags() & Qt.WindowStaysOnBottomHint
    bar = sh.bar_win
    assert bar is not None and bar.isVisible() and bar.windowFlags() & Qt.WindowStaysOnTopHint
    assert sh.bar.parentWidget() is bar and sh.bar.normal.isVisible()
    assert abs(bar.geometry().bottom() - sh.geometry().bottom()) <= 1 and bar.height() == sh.bar.height()
    sh._launch("Firefox")  # Programm starten: Desktop bleibt (liegt ja hinten)
    assert sh.isVisible() and not sh.menu.isVisible()
    window.hide()
    sh.bar.alupc.click()  # AluPC-Knopf in der Taskleiste: Hauptfenster vorne, Desktop bleibt dahinter
    assert window.isVisible() and sh.isVisible() and sh.bar.alupc.isVisible()
    window.hide()
    from alupc.config import DEFAULT_HOTKEYS

    assert DEFAULT_HOTKEYS["alupc_oeffnen"] == "Ctrl+Alt+A"
    controller.run_command("alupc_oeffnen")  # Tastenkürzel Strg+Alt+A: ebenso
    assert window.isVisible() and sh.isVisible()
    window.hide()
    window.toggle_shell()  # Strg+Alt+O schaltet den System-Desktop nicht weg
    assert sh.isVisible()
    assert sh._skip_window(sh.TITLE) and not sh._skip_window("AluPC")  # Hauptfenster gehört in die Taskleiste
    # Zurück zum normalen Desktop – klappt nicht: AluPC bleibt sichtbar (sonst schwarz)
    normal["ok"] = False
    sh.bar.normal.click()
    assert wait_for(lambda: "start" in calls) and _pump(0.2) is None
    assert sh.system and sh.isVisible()
    normal["ok"] = True
    calls.clear()
    sh.bar.normal.click()
    assert wait_for(lambda: not sh.isVisible())
    assert calls == ["start"] and not sh.system and sh.bar_win is None and sh.bar.parentWidget() is sh
    assert not sh.bar.normal.isVisible()
    # Anpassen: Abschnitt „Als System-Desktop“ – einschalten fragt nach und ruft enable()
    from alupc.ui.shell_settings import ShellSettings

    monkeypatch.setattr(ds, "status", lambda: {"kind": "kde-systemd", "supported": True, "why": "Statt Plasma.",
                                               "enabled": False})
    monkeypatch.setattr(ds, "enable", lambda: calls.append("enable") or (True, "Ab der nächsten Anmeldung …"))
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.Yes)
    dlg = ShellSettings(sh)
    dlg.system_login.setChecked(True)
    assert "enable" in calls and "nächsten Anmeldung" in dlg.system_msg.text()
    assert dlg.system_now.text() == "Jetzt ausprobieren"
    dlg.close()
    # Start als System-Desktop (Wächter): Oberfläche sofort, unter Windows Autostart-Programme
    calls.clear()
    monkeypatch.setattr(ds, "IS_WINDOWS", True)
    window.system_desktop(True, startup=True)
    assert wait_for(lambda: "autostart" in calls) and sh.system and sh.isVisible() and "stop" not in calls
    window.system_desktop(False)
    wait_for(lambda: not sh.isVisible())


def test_desktop_rubber_band_and_group_move(env, monkeypatch, tmp_path):  # noqa: F811
    """Auswahlrahmen wie auf dem Windows-/KDE-Desktop: auf freier Fläche ziehen markiert mehrere Symbole, die
    sich dann zusammen verschieben lassen; Klick ins Leere hebt die Auswahl auf."""
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from alupc.ui import shell_desktop

    controller, window, _ = env
    desk = tmp_path / "Desktop"
    desk.mkdir()
    for n in ("A.txt", "B.txt", "C.txt"):
        (desk / n).write_text("x")
    monkeypatch.setattr(shell_desktop, "desktop_dirs", lambda: [desk])
    controller.run_command("oberflaeche")
    sh = window.shell
    _pump(0.6)
    area = sh.area
    icons = {ic.entry["name"]: ic for ic in area.icons}
    a, b, c = icons["A.txt"], icons["B.txt"], icons["C.txt"]
    # Rahmen um A und B ziehen (beginnt rechts neben den Symbolen auf freier Fläche)
    start = QPoint(a.geometry().right() + 30, a.geometry().top() - 4)
    end = QPoint(a.geometry().left() + 10, b.geometry().center().y())
    QTest.mousePress(area, Qt.LeftButton, Qt.NoModifier, start)
    for i in range(1, 6):
        QTest.mouseMove(area, start + (end - start) * i / 5)
    _pump(0.05)
    assert a.selected and b.selected and not c.selected
    assert area._band is not None and area._band.isVisible()
    QTest.mouseRelease(area, Qt.LeftButton, Qt.NoModifier, end)
    assert not area._band.isVisible()
    # A ziehen: B zieht mit, C bleibt
    pa, pb, pc_ = a.pos(), b.pos(), c.pos()
    QTest.mousePress(a, Qt.LeftButton, Qt.NoModifier, QPoint(10, 10))
    for i in range(1, 8):
        QTest.mouseMove(a, QPoint(10 + 20 * i, 10 + 6 * i))
    QTest.mouseRelease(a, Qt.LeftButton, Qt.NoModifier, a.mapFromGlobal(a.mapToGlobal(QPoint(10, 10))))
    _pump(0.1)
    assert a.pos() != pa and b.pos() != pb and c.pos() == pc_
    saved = controller.config["shell"]["pos"]
    assert a.move_key in saved and b.move_key in saved  # beide Positionen gemerkt
    # Klick ins Leere: Auswahl weg
    QTest.mouseClick(area, Qt.LeftButton, Qt.NoModifier, QPoint(area.width() // 2, area.height() - 20))
    assert not any(ic.selected for ic in area.icons)
