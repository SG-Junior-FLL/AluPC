"""Sprachbefehle: Erkennen der Befehle (ohne Mikrofon), Zuhören mit nachgebauter Erkennung, Modell-Download."""

import json
import zipfile

import pytest

from alupc import voice


@pytest.fixture
def qtbot_free_app():
    """Qt-Ereignisschleife ohne Fenster (Signale aus dem Zuhör-Thread kommen darüber an)."""
    import time

    from PySide6.QtCore import QCoreApplication

    app = QCoreApplication.instance() or QCoreApplication([])

    class Helper:
        @staticmethod
        def wait(cond, seconds=4.0):
            end = time.time() + seconds
            while not cond() and time.time() < end:
                app.processEvents()
                time.sleep(0.02)
            return cond()

    return Helper()


@pytest.mark.parametrize("said, command", [
    ("monitor schwarz", "schwarz"),
    ("Monitor zwei schwarz", "schwarz"),
    ("äh monitor spiegeln bitte", "spiegeln"),  # Füllwörter wie „bitte“, „mal“ stören nicht
    ("monitor mal kurz schwarz", "schwarz"),
    ("monitor spiegeln", "spiegeln"),
    ("monitor nächste szene", "naechste_szene"),
    ("monitor nächste zene", "naechste_szene"),  # kleine Hörfehler gehen
    ("monitor glücksrad drehen", "gluecksrad_drehen"),
    ("monitor tafel", "whiteboard"),
    ("monitor spiel starten", "spiel_start"),
    ("monitor bestenliste", "spiel_bestenliste"),
    ("monitor timer starten", "timer_start_pause"),
    ("monitor haus", None),  # kurze Wörter nur genau („aus“ ≠ „haus“)
    ("schwarz", None),  # ohne „Monitor“ passiert nie etwas
    ("monitor", None),
    ("das ist ein schöner monitor", None),
])
def test_match(said, command):
    hit = voice.match(said, [])
    assert (hit[0] if hit else None) == command


def test_match_scenes():
    scenes = ["Pause", "Mission 3", "Begrüßung"]
    assert voice.match("monitor szene pause", scenes)[0] == "szene:Pause"
    assert voice.match("monitor szene begruessung", scenes)[0] == "szene:Begrüßung"
    assert voice.match("monitor szene gibtsnicht", scenes) is None


def test_listen_with_fake_recognizer(qtbot_free_app):
    class FakeRec:
        def __init__(self):
            self.n = 0

        def AcceptWaveform(self, data):  # noqa: N802 – Name wie bei Vosk
            self.text = data.decode()
            return True

        def Result(self):  # noqa: N802
            return json.dumps({"text": self.text})

    config = {"voice": {"on": True, "device": ""}}
    vc = voice.VoiceControl(config, scenes=lambda: ["Pause"], recognizer_factory=FakeRec)
    got, heard = [], []
    vc.command.connect(lambda c, label, text: got.append((c, label)))
    vc.heard.connect(heard.append)
    vc.start()
    assert qtbot_free_app.wait(lambda: vc.state == "hört zu")
    for text in ("hallo zusammen", "monitor schwarz", "monitor szene pause"):
        vc.feed(text.encode())
    assert qtbot_free_app.wait(lambda: len(got) == 2)
    assert got == [("schwarz", "Schwarz an/aus"), ("szene:Pause", "Szene „Pause“")]
    assert heard == ["hallo zusammen", "monitor schwarz", "monitor szene pause"]
    vc.stop()
    assert not vc.running() and vc.state == "aus"


def test_download_model(tmp_path):
    src = tmp_path / "model.zip"
    with zipfile.ZipFile(src, "w") as z:
        z.writestr(f"{voice.MODEL_NAME}/am/final.mdl", b"x" * 10)
        z.writestr(f"{voice.MODEL_NAME}/conf/model.conf", b"--x")
    seen = []
    target = tmp_path / "sprache" / voice.MODEL_NAME
    path = voice.download_model(lambda d, t: seen.append(d), url=src.as_uri(), target=target)
    assert path == target and voice.model_ready(target) and seen
    assert not list((tmp_path / "sprache").glob("*.part"))
    bad = tmp_path / "bad.zip"
    with zipfile.ZipFile(bad, "w") as z:
        z.writestr("../../boese.txt", b"x")
    with pytest.raises(RuntimeError):
        voice.download_model(url=bad.as_uri(), target=tmp_path / "x" / voice.MODEL_NAME)
    assert not (tmp_path / "boese.txt").exists()
    empty = tmp_path / "empty.zip"
    with zipfile.ZipFile(empty, "w") as z:
        z.writestr("readme.txt", b"x")
    with pytest.raises(RuntimeError, match="kein Sprachmodell"):
        voice.download_model(url=empty.as_uri(), target=tmp_path / "y" / voice.MODEL_NAME)
