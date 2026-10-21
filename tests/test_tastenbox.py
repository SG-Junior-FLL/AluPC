"""Tastenbox (Arduino Pro Micro): Zeilen der Box, Tasten → Befehle, Lautstärke nur am Regler, LED, Setup."""

from test_gui import _until, env, pump  # noqa: F401  (Fixture + Hilfen der Oberflächen-Tests)

from alupc import tastenbox
from alupc.tastenbox import parse_line


def test_parse_lines():
    assert parse_line("HALLO ALUPC-TASTEN 1\r\n") == ("hallo", "1")
    assert parse_line("TASTE 3") == ("taste", 3)
    assert parse_line("taste 9") == ("taste", 9)
    assert parse_line("TASTE 10") is None and parse_line("TASTE 0") is None
    assert parse_line("LAUT 57") == ("laut", 57)
    assert parse_line("LAUT 250") == ("laut", 100)
    assert parse_line("STUMM") == ("stumm", None)
    assert parse_line("") is None and parse_line("Müll") is None and parse_line("LAUT x") is None


def test_only_arduino_ports_are_asked(monkeypatch):
    """Fremde Geräte (Drucker, Modems, Fingerabdruck-Modul) bekommen nie „WER?“ geschickt."""
    from types import SimpleNamespace

    from serial.tools import list_ports

    ports = [SimpleNamespace(device="COM3", vid=0x2341, description="Arduino Leonardo", manufacturer="", product=""),
             SimpleNamespace(device="COM4", vid=0x1A86, description="USB-SERIAL CH340", manufacturer="", product=""),
             SimpleNamespace(device="COM5", vid=0x1B4F, description="SparkFun Pro Micro", manufacturer="", product=""),
             SimpleNamespace(device="COM6", vid=None, description="Bluetooth", manufacturer="", product="")]
    monkeypatch.setattr(list_ports, "comports", lambda: ports)
    assert tastenbox.candidate_ports() == ["COM3", "COM5"]
    assert tastenbox.candidate_ports({"COM3"}) == ["COM5"]


def test_keys_run_commands_and_volume_only_at_knob(env, monkeypatch):  # noqa: F811
    controller, window, _ = env
    from alupc import pc_control

    calls = []
    monkeypatch.setattr(pc_control, "set_volume", lambda percent=None, step=0: calls.append(("set", percent)) or (True, ""))
    monkeypatch.setattr(pc_control, "set_mute", lambda on: calls.append(("mute", on)) or (True, ""))
    monkeypatch.setattr(pc_control, "get_volume", lambda: 30)
    box = controller.buttonbox
    box.port = "COM9"  # wie verbunden (ohne echte Box)
    sent = []
    monkeypatch.setattr(box, "send", lambda line: sent.append(line) or True)

    # Taste → Befehl (Standardbelegung: 1 = Schwarz)
    assert not controller.privacy
    box.feed("TASTE 1")
    pump()
    assert controller.privacy
    controller.config["tasten"] = {**controller.config["tasten"], "keys": {"2": "szene:Gibt es nicht"}}
    box.feed("TASTE 2")
    pump()
    controller.toggle_privacy()

    # Regler meldet sich → Lautstärke folgt ihm; andere Wege sind gesperrt
    assert not controller.volume_locked()
    box.feed("LAUT 40")
    pump(30)
    assert controller.volume_locked() and ("set", 40) in calls
    messages = []
    controller.message.connect(messages.append)
    controller.run_command("pc_lauter")
    controller.run_command("ton_laut:90")
    pump()
    assert messages.count("Lautstärke geht nur am Regler.") == 2
    assert not any(c == ("set", 90) for c in calls)

    # Jemand dreht in Windows/KDE (30 % statt 40 %) → zurück auf den Regler
    keeper = controller.volume_keeper
    assert _until(lambda: not keeper._busy)
    calls.clear()
    keeper._ignore_until = 0
    keeper._check()
    assert _until(lambda: ("set", 40) in calls, 5)

    # Regler-Sperre aus → Befehle gehen wieder
    controller.config["tasten"] = {**controller.config["tasten"], "nur_regler": False}
    assert not controller.volume_locked()

    # LED „live“: leuchtet, solange etwas auf Bildschirm 2 läuft
    controller.config["tasten"] = {**controller.config["tasten"], "led": "live"}
    controller._led_level = None
    controller.show_source({"type": "clock"})
    pump()
    assert sent and sent[-1] == "LED 100"
    controller.extend()
    pump()
    assert sent[-1] == "LED 0"
    box.port = ""
    box.knob = None
    keeper.set_target(None)


def test_setup_section(env):  # noqa: F811
    controller, window, _ = env
    window.open_setup_section("Tastenbox")
    pump()
    from PySide6.QtWidgets import QComboBox, QGroupBox

    group = next(g for g in window.setup.findChildren(QGroupBox) if hasattr(g, "tastenbox_refresh"))  # Titel steht im Kopf
    group.tastenbox_refresh()

    combos = [c for c in group.findChildren(QComboBox) if c.findData("schwarz") >= 0]
    assert len(combos) == 9 and combos[0].currentData() == "schwarz"
    combos[4].setCurrentIndex(combos[4].findData("standbild"))
    pump()
    assert controller.box_keys()["5"] == "standbild"
    assert tastenbox_sketch_exists()
    window._go(0)


def tastenbox_sketch_exists() -> bool:
    from alupc.ui.tastenbox_page import SKETCH

    text = SKETCH.read_text(encoding="utf-8")
    return "HALLO ALUPC-TASTEN 1" in text and "LAUT" in text and "TASTE" in text
