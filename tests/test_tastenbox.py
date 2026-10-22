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


def test_parse_v3_lines():
    """Programm 3: Board in der Begrüßung, Rohwerte für die Fehlersuche."""
    assert parse_line("HALLO ALUPC-TASTEN 3 NANO") == ("hallo", "3 NANO")
    assert tastenbox.hello_info("3 NANO") == (3, "Nano") and tastenbox.hello_info("3 PROMICRO") == (3, "Pro Micro")
    assert tastenbox.hello_info("2") == (2, "") and tastenbox.hello_info("") == (1, "")
    assert parse_line("ROH 010000001 512") == ("roh", ("010000001", 512))
    assert parse_line("ROH 0100 512") is None and parse_line("ROH 01000000x 5") is None


def test_only_arduino_ports_are_asked(monkeypatch):
    """Fremde Geräte (Drucker, Modems, Fingerabdruck-Modul) bekommen nie „WER?“ geschickt."""
    from types import SimpleNamespace

    from serial.tools import list_ports

    ports = [SimpleNamespace(device="COM3", vid=0x2341, description="Arduino Leonardo", manufacturer="", product=""),
             SimpleNamespace(device="COM4", vid=0x1A86, description="USB-SERIAL CH340", manufacturer="", product=""),
             SimpleNamespace(device="COM5", vid=0x1B4F, description="SparkFun Pro Micro", manufacturer="", product=""),
             SimpleNamespace(device="COM6", vid=None, description="Bluetooth", manufacturer="", product="")]
    monkeypatch.setattr(list_ports, "comports", lambda: ports)
    # USB-Seriell-Chip (Nano-Nachbau) erst nach den Arduino-Kennungen – und nur einmal je Einstecken (siehe _silent)
    assert tastenbox.candidate_ports() == ["COM3", "COM5", "COM4"]
    assert tastenbox.candidate_ports(chips=False) == ["COM3", "COM5"]
    assert tastenbox.candidate_ports({"COM3", "COM4"}) == ["COM5"]


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


def test_tastenbox_page(env):  # noqa: F811
    """Eigene Seite: Tasten 3 × 3 (Taste leuchtet beim Drücken), Belegung, Regler-Anzeige; Setup-Link führt hin."""
    controller, window, _ = env
    window.open_setup_section("Tastenbox")
    pump()
    from alupc.ui.tastenbox_page import TastenboxPage

    page = window.findChild(TastenboxPage)
    assert page is not None and window.stack.currentIndex() == 7
    assert len(page.caps) == 9 and page.action.currentData() == "schwarz"
    assert page.caps[1].text  # zeigt, was die Taste tut (auf der Box steht nichts)
    page.select(5)
    page.action.setCurrentIndex(page.action.findData("standbild"))
    page.action.activated.emit(page.action.currentIndex())
    pump()
    assert controller.box_keys()["5"] == "standbild" and page.caps[5].text == "Standbild an/aus"
    controller.buttonbox.key.emit(3)  # echte Taste gedrückt → leuchtet und wird ausgewählt
    assert page.caps[3]._anim.state() == page.caps[3]._anim.State.Running
    assert page.selected == 3 and page.key_label.text() == "Taste 3:"
    assert page.target.findData("medien") >= 0 and page.target.findData("mikro") >= 0
    assert tastenbox_sketch_exists()
    window._go(0)


def test_knob_target_waits_for_zero(env, monkeypatch):  # noqa: F811
    """Ziel wechseln → neues Ziel auf 0, Regler greift erst, wenn er auch auf 0 steht (Skala am Regler)."""
    controller, _window, _ = env
    from alupc import audio, pc_control

    calls = []
    monkeypatch.setattr(pc_control, "set_volume", lambda percent=None, step=0: calls.append(("pc", percent)) or (True, ""))
    monkeypatch.setattr(pc_control, "set_mute", lambda on: (True, ""))
    monkeypatch.setattr(pc_control, "get_volume", lambda: None)
    monkeypatch.setattr(audio, "set_level", lambda kind, v: calls.append((kind, v)) or (True, ""))
    box = controller.buttonbox
    box.port = "COM9"
    monkeypatch.setattr(box, "send", lambda line: True)
    box.feed("LAUT 60")
    pump(30)
    assert controller.volume_locked()

    controller.set_knob_target("mikro")
    assert _until(lambda: ("in", 0) in calls)
    assert controller.knob_wait and not controller.volume_locked()  # PC-Ton ist wieder frei
    calls.clear()
    box.feed("LAUT 55")  # noch nicht auf 0 → nichts passiert
    pump(30)
    assert not any(k == "in" for k, _v in calls)
    box.feed("LAUT 1")   # auf 0 gedreht → Regler greift
    box.feed("LAUT 30")
    assert _until(lambda: ("in", 30) in calls)
    assert not controller.knob_wait

    controller.set_knob_target("pc")  # zurück: PC-Ton auf 0, wartet wieder
    assert controller.knob_wait and controller.volume_keeper.target == 0
    box.feed("LAUT 0")
    box.feed("LAUT 25")
    pump(30)
    assert controller.volume_keeper.target == 25
    box.port = ""
    box.knob = None
    controller.volume_keeper.set_target(None)


def tastenbox_sketch_exists() -> bool:
    from alupc.ui.tastenbox_page import SKETCH

    text = SKETCH.read_text(encoding="utf-8")
    return all(w in text for w in ("HALLO ALUPC-TASTEN 5", "LAUT", "WERT", "TASTE", "LANG", "EFFEKT", "FARBE", "DEBUG", "ROH", "PIXEL",
                                   "ARDUINO_AVR_LEONARDO"))


def test_audio_default_output_locked(env, monkeypatch):  # noqa: F811
    """Audio-Seite: Standard-Lautsprecher ausgegraut, solange der Regler gilt; Programme bleiben frei."""
    from types import SimpleNamespace

    from alupc.ui.audio_page import Strip

    controller, _window, _ = env
    page = SimpleNamespace(controller=controller)
    monkeypatch.setattr(controller, "volume_locked", lambda: True)
    speaker = Strip(page, "out", {"id": "spk", "name": "Lautsprecher", "volume": 40, "default": True})
    other = Strip(page, "out", {"id": "hdmi", "name": "HDMI", "volume": 40, "default": False})
    app = Strip(page, "out", {"id": "7", "app": "Spotify", "volume": 40, "default": True}, stream=True)
    assert not speaker.slider.isEnabled() and not speaker.mute.isEnabled()
    assert other.slider.isEnabled() and app.slider.isEnabled()



def test_long_press_and_knob_options(env, monkeypatch):  # noqa: F811
    """Lang drücken = eigener Befehl; Regler umkehren, Höchstwert, ohne Null-Abgleich; LED-Helligkeit und Blitz."""
    controller, _window, _ = env
    from alupc import audio, pc_control

    assert parse_line("LANG 4") == ("lang", 4) and parse_line("LANG 0") is None
    ran = []
    monkeypatch.setattr(controller, "run_command", lambda a: ran.append(a))
    box = controller.buttonbox
    sent = []
    monkeypatch.setattr(box, "send", lambda line: sent.append(line) or True)
    box.port = "COM9"
    base = dict(controller.config["tasten"])
    controller.config["tasten"] = {**base, "lang": {"4": "standbild"}, "led_blink": True, "led_hell": 40,
                                   "led": "an", "nur_regler": False}
    box.feed("LANG 4")
    box.feed("LANG 5")  # ohne eigenen Befehl: wie kurz (5 = nächste Szene)
    assert ran == ["standbild", "naechste_szene"]
    assert any(line in ("LED 0", "LED 40") for line in sent)  # Blitz
    controller._led_level = None
    controller.update_box_led()
    assert sent[-1] == "LED 40"

    # Regler: umgekehrt und höchstens 80 %
    controller.config["tasten"] = {**controller.config["tasten"], "umkehren": True, "max": 80}
    assert controller.knob_value(0) == 80 and controller.knob_value(100) == 0 and controller.knob_value(None) is None

    # ohne Null-Abgleich folgt ein neues Ziel sofort der Reglerstellung
    levels = []
    monkeypatch.setattr(audio, "set_level", lambda kind, v: levels.append((kind, v)) or (True, ""))
    monkeypatch.setattr(pc_control, "set_volume", lambda percent=None, step=0: (True, ""))
    controller.config["tasten"] = {**controller.config["tasten"], "umkehren": False, "max": 100, "abgleich": False}
    box.knob = 30
    controller.set_knob_target("mikro")
    assert not controller.knob_wait and _until(lambda: ("in", 30) in levels)
    controller.config["tasten"] = {**base}
    controller.knob_wait = False
    box.port = ""
    box.knob = None
    controller.volume_keeper.set_target(None)


def test_led_effect_color_and_debug_panel(env, monkeypatch):  # noqa: F811
    """LEDs über die Software: Effekt + Farbe gehen an die Box (ab Programm 3); Fehlersuche zeigt Protokoll,
    Rohwerte (Taste leuchtet, solange sie unten ist) und schaltet DEBUG an der Box an/aus."""
    controller, window, _ = env
    box = controller.buttonbox
    sent = []
    monkeypatch.setattr(box, "send", lambda line: sent.append(line) or True)
    box.port, box.version, box.board = "COM9", 3, "Nano"
    base = dict(controller.config["tasten"])
    controller.config["tasten"] = {**base, "led": "an", "led_effekt": "atmen", "led_farbe": "#ff0010", "led_hell": 60}
    controller._led_level = controller._led_extra = None
    controller.update_box_led()
    assert sent[-3:] == ["EFFEKT 1", "FARBE 255 0 16", "LED 60"]
    sent.clear()
    controller.update_box_led()
    assert sent == []  # nichts doppelt schicken
    box.version = 2  # altes Programm: kennt EFFEKT/FARBE nicht → nicht schicken
    controller._led_level = controller._led_extra = None
    controller.update_box_led()
    assert sent == ["LED 60"]

    box.version = 3
    window.open_setup_section("Tastenbox")
    pump()
    from alupc.ui.tastenbox_page import TastenboxPage

    page = window.findChild(TastenboxPage)
    page.debug_toggle.setChecked(True)
    page.debug_raw.setChecked(True)
    assert sent[-1] == "DEBUG 1" and box.debug
    box.feed("ROH 001000000 1023")
    assert page.caps[3].down and not page.caps[1].down and "3" in page.raw_label.text()
    box.feed("TASTE 3")
    assert "← TASTE 3" in page.log_view.toPlainText()
    page._debug_info()
    assert "Programm 3" in page.debug_summary.text() and "Nano" in page.debug_summary.text()
    page.debug_raw.setChecked(False)
    assert sent[-1] == "DEBUG 0" and not page.caps[3].down
    page.debug_toggle.setChecked(False)
    controller.config["tasten"] = {**base}
    box.port, box.version, box.board = "", 0, ""
    window._go(0)


def test_led_commands_and_color_schemes(env, monkeypatch):  # noqa: F811
    """LEDs vom Handy (box_*-Befehle) und Farbschemata für RGB-LEDs (Programm 4: PIXEL, Regenbogen)."""
    controller, _window, _ = env
    box = controller.buttonbox
    sent = []
    monkeypatch.setattr(box, "send", lambda line: sent.append(line) or True)
    box.port, box.version = "COM9", 4
    base = dict(controller.config["tasten"])
    controller.config["tasten"] = {**base, "led": "an", "led_hell": 80}
    controller.run_command("box_schema:ecken")
    assert controller.config["tasten"]["led_schema"] == "ecken"
    assert [line for line in sent if line.startswith("PIXEL")] == [
        "PIXEL 0 87 193 255", "PIXEL 1 255 97 97", "PIXEL 2 89 212 153", "PIXEL 3 255 197 51"]
    sent.clear()
    controller.run_command("box_schema:regenbogen")
    assert "EFFEKT 3" in sent
    sent.clear()
    controller.run_command("box_schema:zustand")
    controller.privacy = True
    controller._led_extra = None
    controller.update_box_led()
    assert "PIXEL 0 255 176 0" in sent  # Schwarz/Standbild → Gelb
    controller.privacy = False
    for cmd, key, value in (("box_led:aus", "led", "aus"), ("box_effekt:atmen", "led_effekt", "atmen"),
                            ("box_farbe:#FF0000", "led_farbe", "#ff0000"), ("box_hell:300", "led_hell", 100)):
        controller.run_command(cmd)
        assert controller.config["tasten"][key] == value
    assert not controller.box_led_command("box_led:quatsch")
    snap = controller.cast.snapshot if hasattr(controller, "cast") else {}
    controller._cast_snapshot()
    assert controller.cast.snapshot["boxled"]["led_schema"] == "zustand" and controller.cast.snapshot["boxled"]["on"]
    box.version = 3  # altes Programm: kein PIXEL, Regenbogen wird ruhig
    sent.clear()
    assert not box.set_pixel(0, "#ffffff") and box.set_effect("regenbogen") and sent == ["EFFEKT 0"]
    controller.config["tasten"] = {**base}
    box.port, box.version = "", 0
    del snap


def test_automation_rules_model(monkeypatch):
    """Wenn → Dann: Regeln säubern, Code/Reglerzahl vergleichen, eigener Befehl ohne Shell-Zeichenkette."""
    from alupc import automations as a

    r = a.clean_rule({"name": " Intro ", "wenn": {"code": "1a20 3", "wert": "1200", "toleranz": 99},
                      "dann": {"art": "quatsch", "ziel": " standbild "}})
    assert r == {"name": "Intro", "an": True, "wenn": {"code": "123", "wert": 999, "toleranz": 50},
                 "dann": {"art": "alupc", "ziel": "standbild"}}
    assert not a.is_valid(a.clean_rule({"wenn": {}, "dann": {"art": "alupc", "ziel": "x"}}))
    code = a.clean_rule({"name": "c", "wenn": {"code": "12"}, "dann": {"art": "alupc", "ziel": "x"}})
    both = a.clean_rule({"name": "b", "wenn": {"code": "12", "wert": 250}, "dann": {"art": "alupc", "ziel": "y"}})
    val = a.clean_rule({"name": "v", "wenn": {"wert": 500, "toleranz": 3}, "dann": {"art": "alupc", "ziel": "z"}})
    off = {**val, "an": False}
    rules = [code, both, val, off]
    assert a.rules_for_code(rules, "12", None) == [code]
    assert a.rules_for_code(rules, "12", 252) == [code, both]
    assert a.rules_for_code(rules, "21", 250) == []
    assert a.rules_for_value(rules, 503) == [val] and a.rules_for_value(rules, 504) == []
    assert "Code 1-2 und Regler 250 ± 3" in a.describe(both)
    assert a.command_line("echo hi && dir")[-1] == "echo hi && dir"
    started = []
    monkeypatch.setattr(a.subprocess, "Popen", lambda args, **kw: started.append(args))
    assert a.run_external("befehl", "echo hi")[0] and started[-1] == a.command_line("echo hi")
    assert a.run_external("programm", "prog --x 1")[0] and started[-1][-2:] == ["--x", "1"]


def _wait(seconds: float) -> None:
    import time

    end = time.time() + seconds
    while time.time() < end:
        pump()
        time.sleep(0.01)


def test_code_entry_and_value_rules(env, monkeypatch):  # noqa: F811
    """Code-Taste lang → Tasten sind Ziffern, nach der Pause passende Regel; Reglerzahl löst einmal aus."""
    controller, window, _ = env
    from alupc import automations

    assert parse_line("WERT 250") == ("wert", 250) and parse_line("WERT 1500") == ("wert", 999)
    monkeypatch.setattr(automations, "CODE_PAUSE_MS", 50)
    monkeypatch.setattr(automations, "VALUE_SETTLE_MS", 50)
    ran, ext = [], []
    real_run = controller.run_command
    monkeypatch.setattr(controller, "run_command",
                        lambda a: real_run(a) if a.startswith("regel:") else ran.append(a))
    monkeypatch.setattr(automations, "run_external", lambda art, ziel: ext.append((art, ziel)) or (True, "ok"))
    box = controller.buttonbox
    monkeypatch.setattr(box, "send", lambda line: True)
    box.port, box.version = "COM9", 5
    base = dict(controller.config["tasten"])
    rules = [{"name": "Video", "wenn": {"code": "123"}, "dann": {"art": "alupc", "ziel": "standbild"}},
             {"name": "Web", "wenn": {"code": "12", "wert": 250}, "dann": {"art": "webseite", "ziel": "example.org"}},
             {"name": "Prog", "wenn": {"wert": 700, "toleranz": 2}, "dann": {"art": "befehl", "ziel": "echo 7"}}]
    controller.config["tasten"] = {**base, "regeln": rules, "regler": "pc", "lang": {"9": "schwarz"}}

    # Code 1-2-3: Ziffern lösen ihre normalen Aktionen nicht aus
    box.feed("LANG 9")
    assert controller.box_code == ""
    for n in (1, 2, 3):
        box.feed(f"TASTE {n}")
    assert ran == [] and controller.box_code == "123"
    assert _until(lambda: ran == ["standbild"]) and controller.box_code is None
    # Code 1-2 mit Reglerzahl: nur wenn der Regler auf „Zahl“ steht und im Bereich
    controller.set_knob_target("wert")
    assert not controller.knob_wait
    box.feed("WERT 251")
    box.feed("LANG 9")
    box.feed("TASTE 1")
    box.feed("TASTE 2")
    assert _until(lambda: ext == [("webseite", "example.org")])
    # Reglerzahl allein: erst nach Ruhe, nur einmal, wieder nach Verlassen des Bereichs
    _wait(0.15)  # erster ruhiger Wert nach dem Wechsel löst nichts aus
    box.feed("WERT 699")
    assert _until(lambda: ("befehl", "echo 7") in ext)
    box.feed("WERT 701")
    _wait(0.15)
    assert ext.count(("befehl", "echo 7")) == 1
    box.feed("WERT 400")
    _wait(0.15)
    box.feed("WERT 700")
    assert _until(lambda: ext.count(("befehl", "echo 7")) == 2)
    # ohne Code-Regeln: lange Taste 9 macht wieder ihren Befehl; regel:Name von einer Taste
    controller.config["tasten"] = {**controller.config["tasten"], "regeln": rules[2:]}
    box.feed("LANG 9")
    assert controller.box_code is None and ran[-1] == "schwarz"
    controller.run_command("regel:Prog")
    assert ext.count(("befehl", "echo 7")) == 3
    # Seite: Liste + Livewert
    window.open_setup_section("Tastenbox")
    pump()
    from alupc.ui.tastenbox_page import TastenboxPage

    page = window.findChild(TastenboxPage)
    page._fill_rules()
    assert page.rules_list.count() == 1 and "700" in page.rules_live.text()
    controller.config["tasten"] = {**base}
    box.port, box.version, box.fine_value = "", 0, None
    controller._value_hits = None


def test_rule_dialog(env):  # noqa: F811
    controller, window, _ = env
    from alupc.ui.rules_dialog import RuleDialog

    dlg = RuleDialog(controller, None, {"Alt"}, window)
    assert not dlg.ok.isEnabled()
    dlg.name.setText("Alt")
    dlg.code.setText("42")
    dlg.ziel.setText("vlc")
    assert not dlg.ok.isEnabled()  # Name schon vergeben
    dlg.name.setText("Neu")
    assert dlg.ok.isEnabled()
    dlg.art.setCurrentIndex(dlg.art.findData("alupc"))
    assert dlg.rule()["dann"]["ziel"] == dlg.command.currentData()
    dlg.use_value.setChecked(True)
    dlg.value.setValue(321)
    assert dlg.rule()["wenn"] == {"code": "42", "wert": 321, "toleranz": 3}
    dlg.deleteLater()
