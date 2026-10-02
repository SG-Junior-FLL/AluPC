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
    ("alu pc bildschirm schwarz", "schwarz"),  # neues Startwort „Alu PC“
    ("alu pc, nächste szene", "naechste_szene"),
    ("alupc spiegeln", "spiegeln"),
    ("alu pe ze glücksrad drehen", "gluecksrad_drehen"),
    ("alu p c monitor schwarz", "schwarz"),
    ("hallo pc schwarz", "schwarz"),  # so hört das kleine Modell „Alu PC“ oft (echt gemessen in der CI)
    ("hallo schwarz", None),  # „Hallo“ allein ist kein Startwort
    ("alpha pc schwarz", None),
    ("bildschirm schwarz", None),  # „Bildschirm“ allein ist kein Startwort
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

    config = {"voice": {"on": True, "device": "", "wake": ["monitor"]}}
    vc = voice.VoiceControl(config, scenes=lambda: ["Pause"], recognizer_factory=FakeRec)
    got, heard = [], []
    vc.command.connect(lambda c, label, text: got.append((c, label)))
    vc.heard.connect(heard.append)
    vc.start()
    assert qtbot_free_app.wait(lambda: vc.state == "hört zu")
    for text in ("hallo zusammen", "monitor schwarz", "monitor szene pause"):
        vc.feed(text.encode())
    assert qtbot_free_app.wait(lambda: len(got) == 2)
    assert got == [("schwarz", "Schwarz"), ("szene:Pause", "Szene „Pause“")]
    assert heard == ["„hallo zusammen“", "„monitor schwarz“", "„monitor szene pause“"]
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


def test_only_monitor_or_only_alupc():
    assert voice.match("alu pc schwarz", [], wakes=("monitor",)) is None
    assert voice.match("monitor schwarz", [], wakes=("alupc",)) is None
    assert voice.match("alu pc schwarz", [], wakes=("alupc",))[0] == "schwarz"


def test_voice_math():
    assert voice.cosine_dist([1, 0], [1, 0]) == 0
    assert abs(voice.cosine_dist([1, 0], [0, 1]) - 1) < 1e-9
    assert voice.cosine_dist([0, 0], [1, 0]) == 2.0
    avg = voice.average_voice([[2, 0], [0, 3]])  # erst normiert, dann gemittelt
    assert avg == [0.5, 0.5]
    assert voice.who_speaks([1, 0.1], [{"name": "Lena", "vec": [1, 0]}, {"name": "Noah", "vec": [0, 1]}])[0] == "Lena"


def test_only_enrolled_voices_and_enrollment(qtbot_free_app):
    """Befehle nur von angelernten Stimmen; Anlernen liefert Stimmabdrücke statt Befehle."""
    lena, noah = [1.0, 0.0, 0.2], [0.0, 1.0, 0.1]

    class FakeRec:
        speaker = True

        def AcceptWaveform(self, data):  # noqa: N802
            text, who, frames = data.decode().split("|")
            self.res = {"text": text, "spk": {"lena": lena, "noah": noah, "kurz": lena}[who],
                        "spk_frames": int(frames)}
            return True

        def Result(self):  # noqa: N802
            return json.dumps(self.res)

    config = {"voice": {"on": True, "wake": ["monitor", "alupc"], "only_voices": True, "strict": "normal",
                        "voices": [{"name": "Lena", "vec": voice.average_voice([lena])}]}}
    vc = voice.VoiceControl(config, recognizer_factory=FakeRec)
    got, rejected, samples = [], [], []
    vc.command.connect(lambda c, label, text: got.append((c, label)))
    vc.rejected.connect(lambda text, why: rejected.append(why))
    vc.sample.connect(lambda vec, frames, text: samples.append(frames))
    vc.start()
    assert qtbot_free_app.wait(lambda: vc.state == "hört zu") and vc.has_spk
    vc.feed(b"alu pc bildschirm schwarz|lena|120")
    vc.feed(b"alu pc bildschirm schwarz|noah|120")  # fremde Stimme
    vc.feed(b"monitor schwarz|kurz|5")  # zu kurz für einen sicheren Abdruck
    assert qtbot_free_app.wait(lambda: len(got) + len(rejected) == 3)
    assert got == [("schwarz_an", "Schwarz · Lena")]  # „Bildschirm schwarz“ = schwarz machen
    assert rejected[0].startswith("fremde Stimme") and rejected[1].startswith("Stimme nicht erkannt")
    config["voice"]["only_voices"] = False  # Filter aus → jeder darf
    vc.feed(b"monitor schwarz|noah|120")
    assert qtbot_free_app.wait(lambda: len(got) == 2)
    vc.enrolling = True  # Anlernen: keine Befehle, nur Abdrücke
    vc.feed(b"monitor schwarz|noah|80")
    assert qtbot_free_app.wait(lambda: samples == [80])
    assert len(got) == 2
    vc.stop()


def test_download_speaker_model(tmp_path):
    src = tmp_path / "spk.zip"
    with zipfile.ZipFile(src, "w") as z:
        for f in ("mfcc.conf", "final.ext.raw", "mean.vec", "transform.mat"):
            z.writestr(f"{voice.SPK_NAME}/{f}", b"x")
    target = tmp_path / "sprache" / voice.SPK_NAME
    voice.download_model(url=src.as_uri(), target=target, ready=voice.spk_ready)
    assert voice.spk_ready(target)


def test_custom_and_game_commands():
    custom = [{"say": "pause machen", "do": "szene:Pause"}, {"say": "schwarz", "do": "kachel:abc"}]
    assert voice.match("alu pc pause machen", [], custom=custom) == ("szene:Pause", "„pause machen“")
    assert voice.match("monitor pause machn", [], custom=custom)[0] == "szene:Pause"  # kleine Hörfehler
    assert voice.match("monitor schwarz", [], custom=custom)[0] == "kachel:abc"  # eigene vor eingebauten
    assert voice.match("alu pc spiel pong", [])[0] == "spiel:pong"
    assert voice.match("alu pc spiel schätzen", [])[0] == "spiel:schaetzen"
    assert voice.match("monitor spiel malen und raten", [])[0] == "spiel:malen"
    assert voice.match("alu pc spiel starten", [])[0] == "spiel_start"  # kein Spielname
    assert voice.match("alu pc nächste frage", [])[0] == "spiel_weiter"
    assert voice.match("alu pc ergebnis zeigen", [])[0] == "spiel_ende"
    assert voice.match("monitor lobby", [])[0] == "spiel_lobby"
    assert voice.match("monitor spiel quatschkram", []) is None


def test_spoken_label():
    from alupc.speech import spoken_label

    assert spoken_label("Schwarz an/aus") == "Schwarz"
    assert spoken_label("Wetter & Uhr") == "Wetter und Uhr"
    assert spoken_label("Schwarz an/aus · Lena") == "Schwarz"


# ---------------------------------------------------------------- 0.83: ganz normale Sätze, Mikrofon-Schalter
@pytest.mark.parametrize("said,command", [
    ("mach mal bitte den bildschirm schwarz", "schwarz_an"),
    ("bildschirm aus", "schwarz_an"),
    ("bild wieder an", "schwarz_aus"),
    ("nicht mehr schwarz", "schwarz_aus"),
    ("kannst du die kamera zeigen", "kamera"),
    ("licht auf blau", "rgb_farbe:#0000ff"),
    ("mach das licht aus", "rgb_aus"),
    ("licht an", "rgb_an"),
    ("timer auf fünf minuten", "timer_set:300"),
    ("stell einen timer für 30 sekunden", "timer_set:30"),
    ("timer auf zwei minuten dreißig", "timer_set:150"),
    ("timer pause", "timer_pause"),
    ("schalte den bildschirmschoner ein", "bildschirmschoner_an"),
    ("bildschirmschoner aus", "bildschirmschoner_aus"),
    ("kein standbild mehr", "standbild_aus"),
    ("wie spät ist es", "frage:uhrzeit"),
    ("welcher tag ist heute", "frage:datum"),
    ("wie warm ist der prozessor", "frage:temperatur"),
    ("wie wird das wetter", "frage:wetter"),
    ("zeig das wetter", "wetter"),
    ("wie geht es dem computer", "frage:system"),
    ("erzähl mir einen witz", "frage:witz"),
    ("lass uns pong spielen", "spiel:pong"),
    ("nächste frage", "spiel_weiter"),
    ("nächstes lied", "musik_weiter"),
    ("hör auf zuzuhören", "zuhoeren_aus"),
    ("hör mir zu", "zuhoeren_an"),
    ("licht wie der bildschirm", "rgb_monitor2"),
    ("szene pause", "szene:Pause"),
    ("blabla irgendwas", None),
])
def test_understand_normal_sentences(said, command):
    from alupc.intents import understand

    hit = understand(voice.fold(said).split(), ["Pause"], [])
    assert (hit[0] if hit else None) == command


def test_parse_duration():
    from alupc.intents import parse_duration

    assert parse_duration("eine halbe stunde".split()) == 1800
    assert parse_duration("fuenfundzwanzig minuten".split()) == 1500
    assert parse_duration("1 stunde 5 minuten".split()) == 3900
    assert parse_duration("ohne zahl".split()) is None


def test_direct_mode_follow_up_and_echo_mute(qtbot_free_app, tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from alupc.config import Config

    class FakeRec:
        def __init__(self):
            self.text = ""

        def AcceptWaveform(self, data):
            self.text = data.decode()
            return True

        def Result(self):
            return json.dumps({"text": self.text})

    config = Config(tmp_path / "c.json")
    config["voice"] = {**config["voice"], "on": True}
    vc = voice.VoiceControl(config, recognizer_factory=FakeRec)
    got, ears = [], []
    vc.command.connect(lambda c, label, t: got.append(c))
    vc.not_understood.connect(ears.append)
    vc.start()
    assert qtbot_free_app.wait(lambda: vc.state == "hört zu")
    vc.feed(b"mach das licht aus")  # ohne Startwort: nichts
    vc.feed(b"alu pc")  # nur das Startwort: „Ja?“
    assert qtbot_free_app.wait(lambda: got == ["frage:ja"])
    vc.listen_on(5)  # nach der Antwort: Nachfragen ohne Startwort
    vc.feed(b"mach das licht aus")
    assert qtbot_free_app.wait(lambda: got == ["frage:ja", "rgb_aus"])
    vc.follow_until = 0
    vc.feed(b"licht an")  # Fenster zu: wieder nichts
    qtbot_free_app.wait(lambda: vc._queue.empty() and False, 0.4)
    assert "rgb_an" not in got
    vc.set_direct(True)  # Mikrofon-Schalter
    vc.feed(b"licht an")
    vc.feed(b"quatsch mit sosse")
    assert qtbot_free_app.wait(lambda: got[-1:] == ["rgb_an"] and ears == ["quatsch mit sosse"])
    vc.set_direct(False)
    vc.mute(5)  # AluPC spricht: alles verwerfen
    vc.feed(b"alu pc licht an")
    qtbot_free_app.wait(lambda: False, 0.3)
    assert got.count("rgb_an") == 1
    vc.stop()


def test_real_ci_transcripts():
    """Was Vosk und Whisper in der CI aus Piper-Sätzen wirklich gemacht haben (0.83, erster Lauf)."""
    from alupc.intents import understand

    for heard, command in [
        ("hallo pc schaltet den bildschirmschoner aus", "bildschirmschoner_aus"),
        ("hallo pc wie spät ist es", "frage:uhrzeit"),
        ("hallo pc mach bitte dem bildschirm schwarz", "schwarz_an"),
        ("Alu PC, schaltet den Bildschirmschutz aus.", "bildschirmschoner_aus"),
        ("Alu PC, Licht auf Blaum.", "rgb_farbe:#0000ff"),
        ("anno pc licht auf blau", "rgb_farbe:#0000ff"),  # 0.84, Vosk verhört das Startwort
        ("alle pc zeigt mir die kamera", "kamera"),
        ("Hallo PC, schaltet den Bildschirm schwarzschoner aus.", "bildschirmschoner_aus"),
    ]:
        words = voice.fold(heard).split()
        span = voice.wake_span(words)
        assert span is not None, heard
        assert understand(words[:span[0]] + words[span[1]:], [], [])[0] == command, heard


def test_convert_audio_from_device_format():
    """Mikrofone, die kein 16 kHz/mono können: 48 kHz Stereo Float → 16 kHz mono 16 Bit."""
    import numpy as np

    t = np.arange(48000) / 48000
    tone = (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    stereo = np.stack([tone, tone], axis=1).ravel().tobytes()
    out = voice.convert_audio(stereo, 48000, 2, "Float")
    pcm = np.frombuffer(out, dtype=np.int16)
    assert abs(len(pcm) - 16000) <= 1
    assert 15000 < np.abs(pcm).max() < 17000  # Lautstärke bleibt (0,5 × 32767)
    same = (np.zeros(160, np.int16)).tobytes()
    assert voice.convert_audio(same, 16000, 1, "Int16") == same


def test_whisper_confirms_misheard_wake_word(qtbot_free_app, tmp_path, monkeypatch):
    """„am pc …“ ist kein Startwort – mit Whisper wird nachgefragt; sagt Whisper „Alu PC“, zählt der Satz."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from alupc.config import Config

    vc = voice.VoiceControl(Config(tmp_path / "c.json"))
    got = []
    vc.command.connect(lambda c, _l, _t: got.append(c))

    class FakeWhisper:
        def __init__(self, text):
            self.text = text

        def transcribe(self, _audio):
            return self.text

    vc._handle("am pc schaltet den bildschirmschoner aus", None, 0, b"")  # ohne Whisper/Ton: nichts
    vc.stt = FakeWhisper("Alu PC, schalte den Bildschirmschoner aus.")
    vc._handle("am pc schaltet den bildschirmschoner aus", None, 0, b"x")
    vc.stt = FakeWhisper("Ich sitze am PC und arbeite.")
    vc._handle("ich sitze am pc und arbeite", None, 0, b"x")  # Whisper: kein Startwort → nichts
    assert got == ["bildschirmschoner_aus"]
