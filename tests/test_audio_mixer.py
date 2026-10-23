"""Seite „Audio & Kamera“: Mixer (pactl nachgespielt + echt, falls ein Audio-Dienst läuft), virtuelles Mikro,
Weiterleitungen, virtuelle Kamera (Kamera nachgespielt), Treiber-Skripte."""

import json
import shutil
import subprocess
import sys

import pytest

from test_gui import env  # noqa: F401

from alupc import drivers, mixer

SINKS = [{"index": 0, "name": "alsa_output.pci.analog-stereo", "description": "Lautsprecher",
          "properties": {"device.api": "alsa"}, "mute": False,
          "volume": {"front-left": {"value_percent": "60%"}, "front-right": {"value_percent": "70%"}}},
         {"index": 7, "name": "alupc_out", "description": "AluPC Virtueller Ausgang", "properties": {},
          "mute": True, "volume": {"mono": {"value_percent": "100%"}}},
         {"index": 8, "name": "alupc_mic_mix", "description": "AluPC Mikro-Mischer", "properties": {}, "mute": False,
          "volume": {}}]
SOURCES = [{"index": 1, "name": "alsa_input.usb-headset", "description": "Headset-Mikro",
            "properties": {"device.api": "alsa"}, "mute": False, "volume": {"mono": {"value_percent": "80%"}}},
           {"index": 2, "name": "alsa_output.pci.analog-stereo.monitor", "description": "Monitor of Lautsprecher",
            "properties": {"device.class": "monitor"}, "mute": False, "volume": {}},
           {"index": 9, "name": "alupc_mic", "description": "AluPC Virtuelles Mikro", "properties": {}, "mute": False,
            "volume": {"mono": {"value_percent": "100%"}}}]
INPUTS = [{"index": 31, "sink": 0, "mute": False, "volume": {"l": {"value_percent": "50%"}},
           "properties": {"application.name": "Firefox", "media.name": "YouTube"}},
          {"index": 32, "sink": 0, "mute": False, "volume": {}, "properties": {"media.name": "alupc_route",
                                                                              "application.name": "Loopback"}}]


def fake_run(calls):
    def run(cmd, timeout=6):
        calls.append(cmd)
        data = {"sinks": SINKS, "sources": SOURCES, "sink-inputs": INPUTS, "source-outputs": []}
        if cmd[:4] == ["pactl", "-f", "json", "list"]:
            return 0, json.dumps(data[cmd[4]])
        if cmd[:2] == ["pactl", "get-default-sink"]:
            return 0, "alsa_output.pci.analog-stereo\n"
        if cmd[:2] == ["pactl", "get-default-source"]:
            return 0, "alsa_input.usb-headset\n"
        if cmd[:4] == ["pactl", "list", "short", "modules"]:
            return 0, ("12\tmodule-loopback\tsource=alsa_input.usb-headset sink=alupc_mic_mix "
                       "sink_input_properties=media.name=alupc_route\n13\tmodule-null-sink\tsink_name=x\n")
        return 0, ""
    return run


def test_pactl_parsing():
    calls = []
    run = fake_run(calls)
    outs = mixer._pa_devices("out", run)
    assert [(d["name"], d["virtual"], d["volume"], d["default"]) for d in outs] == [
        ("Lautsprecher", False, 65, True), ("AluPC Virtueller Ausgang", True, 100, False)]  # Mischer versteckt
    ins = mixer._pa_devices("in", run)
    assert [d["name"] for d in ins] == ["Headset-Mikro", "AluPC Virtuelles Mikro"]  # kein „Monitor of …“
    assert ins[1]["alupc"] and ins[0]["default"]
    apps = mixer._pa_streams("out", run)
    assert [(a["app"], a["volume"], a["device"]) for a in apps] == [("Firefox", 50, "alsa_output.pci.analog-stereo")]
    assert mixer._pa_loopbacks(run) == [{"id": "12", "source": "alsa_input.usb-headset", "sink": "alupc_mic_mix"}]
    assert mixer.is_virtual_name("CABLE Input (VB-Audio Virtual Cable)") and not mixer.is_virtual_name("Realtek")
    assert mixer._props("sink", "A B") == """sink_properties='device.description="A B"'"""


@pytest.mark.skipif(sys.platform.startswith("win") or not shutil.which("pactl") or
                    subprocess.run(["pactl", "info"], capture_output=True).returncode != 0,
                    reason="kein PipeWire/PulseAudio")
def test_real_virtual_devices_and_audio_flow():
    """Echt: virtuelles Mikro anlegen, Ton von einem Ausgang hineinleiten, im virtuellen Mikro ankommen."""
    import math
    import struct
    import time

    mixer.remove_virtual()
    ok, why = mixer.create_virtual()
    assert ok, why
    st = mixer.virtual_status()
    assert st["out"] == mixer.OUT_NAME and st["mic"] == mixer.MIC_NAME
    assert mixer.create_virtual()[0]  # zweimal: keine doppelten Geräte
    assert sum(1 for d in mixer.devices("out") if d["id"] == mixer.OUT_NAME) == 1
    # Ton in den virtuellen Ausgang → (Weiterleitung) → virtuelles Mikro
    assert mixer.set_route(mixer.OUT_NAME + ".monitor", mixer.MIX_NAME, True)[0]
    rec = subprocess.Popen(["parec", "-d", mixer.MIC_NAME, "--format=s16le", "--rate=44100", "--channels=2",
                            "--raw"], stdout=subprocess.PIPE)
    time.sleep(0.3)
    tone = b"".join(struct.pack("<hh", v, v) for v in (int(9000 * math.sin(2 * math.pi * 440 * i / 44100))
                                                       for i in range(44100)))
    subprocess.run(["pacat", "-d", mixer.OUT_NAME, "--format=s16le", "--rate=44100", "--channels=2", "--raw"],
                   input=tone, timeout=20)
    time.sleep(0.4)
    rec.terminate()
    data = rec.stdout.read()
    peak = max(abs(v) for v in struct.unpack("<%dh" % (len(data) // 2), data[: len(data) // 2 * 2]))
    assert peak > 5000, peak
    # Pegel (Mischpult): Ton im virtuellen Ausgang → Pegel steigt, wie pavucontrol
    import threading

    from alupc.mixer_meters import Meters

    meters = Meters()
    meters.set_channels([{"key": "o", "kind": "out", "dev": mixer.OUT_NAME, "stream": None, "sink": ""}])
    play = subprocess.Popen(["pacat", "-d", mixer.OUT_NAME, "--format=s16le", "--rate=44100", "--channels=2",
                             "--raw"], stdin=subprocess.PIPE)
    threading.Thread(target=lambda: (play.stdin.write(tone * 3), play.stdin.close()), daemon=True).start()
    seen = 0.0
    t0 = time.monotonic()
    while time.monotonic() - t0 < 3 and seen < 0.2:
        seen = max(seen, meters.peak("o"))
        time.sleep(0.05)
    meters.stop()
    play.terminate()
    assert seen > 0.2, seen
    assert mixer.set_device("out", mixer.OUT_NAME, volume=35, muted=True)[0]
    dev = next(d for d in mixer.devices("out") if d["id"] == mixer.OUT_NAME)
    assert dev["volume"] == 35 and dev["muted"]
    mixer.remove_virtual()
    assert mixer.virtual_status()["mic"] == "" and not mixer.routes()


def test_routing_follows_settings(env, monkeypatch):  # noqa: F811
    controller, window, _ = env
    if sys.platform.startswith("win"):
        pytest.skip("Windows leitet über Qt weiter (VB-CABLE)")
    routing = controller.audio_routing
    routes, made, removed = [], [], []
    present = {"alupc_out", "alupc_mic"}

    def vdevs(configured=None):
        return [{"id": d["id"], "kind": d["kind"], "name": d["name"],
                 "sink": d["id"] + "_mix" if d["kind"] == "mic" else d["id"],
                 "source": d["id"] if d["kind"] == "mic" else d["id"] + ".monitor",
                 "present": d["id"] in present, "removable": d["id"] not in ("alupc_out", "alupc_mic")}
                for d in configured or mixer.DEFAULT_DEVICES]

    def create(devices=None):
        made.append([d["id"] for d in devices or []])
        present.update(d["id"] for d in devices or [])
        return True, ""

    monkeypatch.setattr(mixer, "virtual_devices", vdevs)
    monkeypatch.setattr(mixer, "create_virtual", create)
    monkeypatch.setattr(mixer, "routes", lambda: [{"id": str(i), "source": s, "sink": d}
                                                  for i, (s, d) in enumerate(routes)])

    def set_route(src, dst, on):
        (routes.append((src, dst)) if on else routes.remove((src, dst)))
        return True, ""

    monkeypatch.setattr(mixer, "set_route", set_route)
    monkeypatch.setattr(mixer, "remove_virtual", lambda: (routes.clear(), (True, ""))[1])
    monkeypatch.setattr(mixer, "remove_device", lambda dev: (removed.append(dev), (True, ""))[1])
    monkeypatch.setattr(mixer, "_pa_json", lambda what, run=None: [])
    # alte Einstellung (vor dem Mischpult) wird übernommen
    controller.config["audio_mixer"] = {"virtual": False, "mic_inputs": ["alsa_input.usb-headset"],
                                        "out_to_mic": True, "listen": False}
    assert routing.cfg()["routes"] == [["alsa_input.usb-headset", "alupc_mic"], ["alupc_out", "alupc_mic"]]
    assert routing.set_virtual(True)[0] and made
    assert set(routes) == {("alsa_input.usb-headset", "alupc_mic_mix"), ("alupc_out.monitor", "alupc_mic_mix")}
    routing.set_route("alupc_out", "lautsprecher", True)  # Mithören
    assert ("alupc_out.monitor", "") in routes
    # eigenes virtuelles Mikro „Discord“: anlegen, Headset hinein, wieder entfernen
    ok, msg = routing.add_device("mic", "Discord")
    assert ok and "Discord" in msg
    dev = next(d for d in routing.cfg()["devices"] if d["name"] == "Discord")
    assert dev["id"] == "alupc_mic_discord" and dev["kind"] == "mic"
    routing.set_route("alsa_input.usb-headset", dev["id"], True)
    assert ("alsa_input.usb-headset", "alupc_mic_discord_mix") in routes
    assert routing.add_device("mic", "Discord")[0]  # gleicher Name → eigene ID
    assert len({d["id"] for d in routing.cfg()["devices"]}) == len(routing.cfg()["devices"])
    assert routing.remove_device(dev["id"])[0] and removed == [dev["id"]]
    assert all(dev["id"] not in r for r in routing.cfg()["routes"])
    assert ("alsa_input.usb-headset", "alupc_mic_discord_mix") not in routes
    assert not routing.remove_device("alupc_mic")[0]  # Standard-Geräte bleiben
    assert "mic_inputs" not in controller.config["audio_mixer"]
    routing.set_virtual(False)
    assert routes == []


def test_audio_page_builds(env, monkeypatch):  # noqa: F811
    controller, window, _ = env
    snap = {"out": [{"id": "a", "name": "Lautsprecher", "virtual": False, "volume": 40, "muted": False,
                     "default": True, "alupc": False},
                    {"id": "alupc_out", "name": "AluPC Virtueller Ausgang", "virtual": True, "volume": 100,
                     "muted": False, "default": False, "alupc": True}],
            "in": [{"id": "m", "name": "Headset", "virtual": False, "volume": 70, "muted": True, "default": True,
                    "alupc": False}],
            "apps": [{"id": 3, "app": "Spotify", "title": "Song", "volume": 80, "muted": False, "device": "a"}],
            "rec": [], "virtual": {"supported": True, "out": "alupc_out", "mic": "alupc_mic", "why": ""},
            "routes": [], "ok": (True, "")}
    monkeypatch.setattr(mixer, "virtual_devices", lambda configured=None, outs=None, ins=None: [
        {"id": "alupc_out", "kind": "out", "name": "AluPC Virtueller Ausgang", "sink": "alupc_out",
         "source": "alupc_out.monitor", "present": True, "removable": False},
        {"id": "alupc_mic", "kind": "mic", "name": "AluPC Virtuelles Mikro", "sink": "alupc_mic_mix",
         "source": "alupc_mic", "present": True, "removable": False}])
    calls = []
    monkeypatch.setattr(controller.audio_routing, "apply", lambda: (calls.append(1), (True, ""))[1])
    controller.config["audio_mixer"] = {"virtual": True, "routes": [["m", "alupc_mic"]]}
    from alupc.ui.audio_page import AudioPage

    page = AudioPage(controller)
    snap["vdevs"] = controller.audio_routing.devices(snap)  # wie die Hintergrund-Abfrage in reload()
    page._snap = snap
    page._fill()
    strips = page._strips
    assert strips["out:a"].slider.value() == 40 and strips["in:m"].mute.isChecked()
    assert strips["app:3"].name.text() == "Spotify"
    headset_routes = [strips["in:m"].routes_box.itemAt(i).widget() for i in range(strips["in:m"].routes_box.count())]
    assert [(b.text(), b.isChecked()) for b in headset_routes] == [("→ Mikro", True)]
    vout = [strips["out:alupc_out"].routes_box.itemAt(i).widget().text()
            for i in range(strips["out:alupc_out"].routes_box.count())]
    assert vout == ["→ Mikro", "🔊 Mithören"]  # virtueller Ausgang: ins Mikro + Mithören
    assert strips["out:a"].routes_box.count() == 0  # echter Lautsprecher: keine Weiterleitung
    headset_routes[0].setChecked(False)
    assert controller.config["audio_mixer"]["routes"] == []
    page._fill()  # Weiterleitung geändert → Kanäle neu
    strips = page._strips
    page._snap["out"][0]["volume"] = 55
    page._fill()  # gleiche Kanäle → nur Werte aktualisieren
    assert page._strips["out:a"] is strips["out:a"] and strips["out:a"].slider.value() == 55
    page.close()


def test_audio_page_late_answer_after_delete(env, monkeypatch):  # noqa: F811
    """Antwort von mixer.snapshot kommt erst, nachdem die Seite gelöscht ist (Windows: COM ist langsam) – darf
    nichts mehr an der Seite anfassen (sonst Absturz). Pegelmessung endet auch ohne „hide“."""
    import threading
    import time

    import shiboken6
    from PySide6.QtWidgets import QApplication

    from alupc.ui.audio_page import AudioPage

    controller, _window, _ = env
    gate, filled = threading.Event(), []
    monkeypatch.setattr(mixer, "snapshot", lambda: (gate.wait(5), {"out": [], "in": [], "apps": []})[1])
    page = AudioPage(controller)
    monkeypatch.setattr(page, "_fill", lambda: filled.append(1))
    stopped = []
    monkeypatch.setattr(page.meters, "stop", lambda: stopped.append(1))
    page.reload()
    shiboken6.delete(page)  # wie beim Schließen des Fensters: C++-Seite weg, Python-Hülle bleibt
    assert not shiboken6.isValid(page) and stopped
    gate.set()
    end = time.monotonic() + 2
    while time.monotonic() < end:
        QApplication.processEvents()
        time.sleep(0.02)
    assert filled == []  # späte Antwort ist verworfen


class FakeCam:
    def __init__(self, width, height, fps, fmt=None, device=None, backend=None):
        self.width, self.height, self.frames, self.device = width, height, [], device or "/dev/video42"

    def send(self, arr):
        self.frames.append(arr.shape)

    def close(self):
        pass


def test_virtual_camera_sends_monitor2(env, monkeypatch):  # noqa: F811
    import time

    pytest.importorskip("pyvirtualcam")
    pytest.importorskip("numpy")
    import pyvirtualcam

    from PySide6.QtWidgets import QApplication

    controller, window, _ = env
    cam = controller.vcam
    monkeypatch.setattr(pyvirtualcam, "Camera", FakeCam)
    monkeypatch.setattr("alupc.vcam.vcam_installed", lambda: (True, ""))
    monkeypatch.setattr("alupc.vcam.v4l2_device", lambda: "/dev/video42")
    controller.config["vcam"] = {**cam.cfg(), "size": "540p", "fps": 25}
    ok, why = cam.start()
    assert ok, why
    t0 = time.monotonic()
    while cam.sent < 3 and time.monotonic() - t0 < 5:
        QApplication.processEvents()
        time.sleep(0.02)
    assert cam.sent >= 3 and cam.cam.frames[0] == (540, 960, 3)
    assert controller.config["vcam"]["on"] is True
    img = cam.frame_image(320, 180)
    assert (img.width(), img.height()) == (320, 180)
    controller.run_command("vcam")  # aus
    assert not cam.running and controller.config["vcam"]["on"] is False


def test_driver_scripts():
    script = drivers.linux_script(["kamera"])
    assert "v4l2loopback-dkms" in script and 'card_label="AluPC Bildschirm"' in script and "exclusive_caps=1" in script
    assert subprocess.run(["bash", "-n"], input=script, text=True).returncode == 0 if shutil.which("bash") else True
    assert drivers.linux_script([]) == "true"
    ps = drivers.vbcable_ps() + drivers.obs_vcam_ps()
    assert "VBCABLE_Setup_x64.exe" in ps and "'-i','-h'" in ps and "obs-virtualcam-module64.dll" in ps
    assert "„" not in ps and "“" not in ps  # keine deutschen Anführungszeichen (PowerShell liest sie als Quotes)
    pwsh = shutil.which("pwsh") or shutil.which("powershell")
    if pwsh:  # PowerShell-Syntax prüfen (ohne auszuführen)
        check = ("$e=$null; [void][System.Management.Automation.Language.Parser]::ParseInput($env:S,[ref]$null,"
                 "[ref]$e); if ($e.Count) { $e | % { $_.Message }; exit 1 }")
        r = subprocess.run([pwsh, "-NoProfile", "-Command", check], env={**__import__("os").environ, "S": ps},
                           capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr
    calls = []

    def run(cmd, **kw):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, "Virtuelle Kamera: fertig", "")

    if not sys.platform.startswith("win"):
        ok, msg = drivers.install(["kamera"], elevated=True, run=run)
        assert ok and calls[0][:2] == ["sh", "-c"] and "Virtuelle Kamera" in msg
        assert drivers.install(["unbekannt"])[0]


def test_pactl_missing_offers_install(env, monkeypatch):  # noqa: F811
    """Kubuntu: PipeWire ist da, pactl aber nicht (kommt nur mit pulseaudio-utils) → klare Meldung + „Installieren“,
    das pulseaudio-utils per pkexec nachinstalliert. Das .deb hängt jetzt selbst von pulseaudio-utils ab."""
    from pathlib import Path

    script = drivers.linux_script(["pactl"])
    assert "pulseaudio-utils" in script and "command -v pactl" in script
    if shutil.which("bash"):
        assert subprocess.run(["bash", "-n"], input=drivers.linux_script(["pactl", "kamera"]), text=True).returncode == 0
    deb = (Path(__file__).resolve().parent.parent / "packaging/linux/build_deb.sh").read_text()
    depends = next(ln for ln in deb.splitlines() if ln.startswith("Depends:"))
    assert "pulseaudio-utils" in depends
    if sys.platform.startswith("win"):
        assert drivers.install(["pactl"])[0]  # unter Windows nichts zu tun
        return
    calls = []
    monkeypatch.setattr(drivers.os, "geteuid", lambda: 1000)
    monkeypatch.setattr(drivers.shutil, "which", lambda n: "/usr/bin/pkexec" if n == "pkexec" else None)
    ok, msg = drivers.install(["pactl"], run=lambda cmd, **kw: (calls.append(cmd),
                                                                 subprocess.CompletedProcess(cmd, 0, "fertig", ""))[1])
    assert ok and calls[0][0] == "pkexec" and "pulseaudio-utils" in calls[0][-1] and "Ton-Werkzeuge" in msg
    # Seite: Meldung + Knopf, solange pactl fehlt
    controller, window, _ = env
    import alupc.ui.audio_page as ap

    monkeypatch.setattr(ap.shutil, "which", lambda n: None)
    page = ap.AudioPage(controller)
    page._snap = {"out": [], "in": [], "apps": [], "rec": [], "virtual": {}, "routes": [],
                  "ok": (False, "Ton-Werkzeug „pactl“ fehlt (Paket „pulseaudio-utils“).")}
    page._fill()
    assert page.note.isVisibleTo(page) and page.fix_btn.isVisibleTo(page) and "pulseaudio-utils" in page.note.text()
    page.close()


PA_TEXT_SINKS = """Sink #47
\tState: SUSPENDED
\tName: alsa_output.pci-0000_00_1f.3.analog-stereo
\tDescription: Built-in Audio Analog Stereo
\tDriver: PipeWire
\tSample Specification: s32le 2ch 48000Hz
\tChannel Map: front-left,front-right
\tOwner Module: 4294967295
\tMute: no
\tVolume: front-left: 26214 /  40% / -23.88 dB,   front-right: 26214 /  40% / -23.88 dB
\t        balance 0.00
\tBase Volume: 65536 / 100% / 0.00 dB
\tMonitor Source: alsa_output.pci-0000_00_1f.3.analog-stereo.monitor
\tFlags: HARDWARE HW_MUTE_CTRL DECIBEL_VOLUME LATENCY
\tProperties:
\t\talsa.card = "0"
\t\tdevice.api = "alsa"
\t\tdevice.description = "Built-in Audio Analog Stereo"
\tPorts:
\t\tanalog-output-speaker: Speakers (type: Speaker, priority: 10000, availability unknown)
\tActive Port: analog-output-speaker

Sink #52
\tState: RUNNING
\tName: alupc_out
\tDescription: AluPC Virtueller Ausgang
\tDriver: PipeWire
\tMute: yes
\tVolume: mono: 65536 / 100% / 0.00 dB
\tProperties:
\t\tdevice.class = "filter"
"""

PA_TEXT_INPUTS = """Sink Input #85
\tDriver: PipeWire
\tOwner Module: n/a
\tClient: 84
\tSink: 47
\tMute: no
\tVolume: front-left: 52429 /  80% / -5.81 dB,   front-right: 52429 /  80% / -5.81 dB
\tProperties:
\t\tapplication.name = "Firefox"
\t\tmedia.name = "YouTube"
\t\tapplication.process.id = "4242"
"""


def test_pactl_text_fallback_when_json_missing_or_broken():
    """pactl 15 kennt -f json nicht, pactl 16.1 gibt bei manchen Geräten kaputtes JSON aus → Textausgabe lesen."""
    from alupc import audio, mixer

    calls = []

    def run(cmd, *_a):
        calls.append(cmd)
        if "-f" in cmd:
            return 0, '[{"name": "kaputt", "description": "x\\y"'  # ungültiges JSON
        if cmd[-2:] == ["list", "sinks"]:
            return 0, PA_TEXT_SINKS
        if cmd[-2:] == ["list", "sink-inputs"]:
            return 0, PA_TEXT_INPUTS
        if cmd[1:] == ["get-default-sink"]:
            return 0, "alsa_output.pci-0000_00_1f.3.analog-stereo\n"
        return 1, ""

    devs = mixer._pa_devices("out", run)
    assert [d["name"] for d in devs] == ["Built-in Audio Analog Stereo", "AluPC Virtueller Ausgang"]
    built_in, virt = devs
    assert built_in["volume"] == 40 and not built_in["muted"] and built_in["default"] and not built_in["virtual"]
    assert virt["muted"] and virt["volume"] == 100 and virt["virtual"] and virt["alupc"]
    st = mixer._pa_streams("out", run)
    assert st == [{"id": 85, "app": "Firefox", "title": "YouTube", "volume": 80, "muted": False,
                   "device": "alsa_output.pci-0000_00_1f.3.analog-stereo"}]
    assert [d["id"] for d in audio._pa_devices("out", run)] == ["alsa_output.pci-0000_00_1f.3.analog-stereo",
                                                                 "alupc_out"]
    # pactl 15: -f unbekannt → Fehlercode → gleich Text
    assert audio.pa_list("sinks", lambda cmd, *_: (1, "") if "-f" in cmd else (0, PA_TEXT_SINKS))[0]["index"] == 47


def test_pa_run_reads_stdout_only_in_english(monkeypatch):
    import subprocess

    from alupc import audio

    seen = {}

    class R:
        returncode, stdout, stderr = 0, "[]", "Warning: something"

    def fake(cmd, **kw):
        seen.update(kw.get("env") or {})
        return R()

    monkeypatch.setattr(subprocess, "run", fake)
    assert audio.pa_run(["pactl", "info"]) == (0, "[]")
    assert seen.get("LC_ALL") == "C"


def test_windows_sessions_once_per_program():
    """Windows meldet „Systemklänge“ je Ausgabegerät – in der Liste nur einmal (vorher z. B. 6×)."""
    from alupc import mixer

    raw = [{"id": f"{i}:0", "pid": 0, "app": "Systemklänge", "volume": 100, "muted": False, "device": f"G{i}"}
           for i in range(6)]
    raw += [{"id": "0:42", "pid": 42, "app": "Spotify", "volume": 60, "muted": False, "device": "G0"},
            {"id": "3:42", "pid": 42, "app": "Spotify", "volume": 60, "muted": False, "device": "G3"}]
    merged = mixer.merge_sessions(raw)
    assert [m["app"] for m in merged] == ["Systemklänge", "Spotify"]
    assert [m["id"] for m in merged] == ["p:0", "p:42"]
    assert int(merged[1]["id"].split(":")[-1]) == 42  # set_stream/Pegel lesen die Prozess-Nummer so
