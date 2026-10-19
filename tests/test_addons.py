"""Zusatzprogramme: nur was AluPC NEU installiert hat, wird gemerkt und beim Deinstallieren entfernt."""

import subprocess

import pytest

from alupc import addons


@pytest.fixture
def records(tmp_path, monkeypatch):
    monkeypatch.setattr(addons, "record_dirs", lambda: [tmp_path / "zusatz"])
    monkeypatch.setattr(addons, "IS_WINDOWS", True)
    return tmp_path / "zusatz"


def test_track_marks_only_new_installs(records):
    installed = {"openrgb": True, "bonjour": False, "uxplay": False}  # OpenRGB war schon da

    def install():
        installed.update(bonjour=True, uxplay=False, openrgb=True)  # uxplay-Installation schlug fehl
        return "ok"

    assert addons.track(["openrgb", "bonjour", "uxplay"], install, check=lambda k: installed[k]) == "ok"
    assert addons.recorded() == ["bonjour"]
    assert (records / "bonjour.txt").read_text(encoding="utf-8") == addons.ADDONS["bonjour"][0]


def test_track_marks_even_if_action_raises(records):
    state = {"vbcable": False}

    def install():
        state["vbcable"] = True
        raise RuntimeError("Meldung danach kaputt")

    with pytest.raises(RuntimeError):
        addons.track(["vbcable"], install, check=lambda k: state[k])
    assert addons.recorded() == ["vbcable"]


def test_remove_recorded_uninstalls_and_forgets(records, monkeypatch):
    addons.mark("bonjour")
    addons.mark("openrgb")
    there = {"bonjour": True, "openrgb": False}  # OpenRGB hat der Benutzer schon selbst entfernt
    calls = []

    def fake_run(cmd, timeout=900):
        calls.append(cmd)
        if cmd[:2] == ["winget", "uninstall"]:
            there["bonjour"] = False
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(addons, "present", lambda k, run=None: there[k])
    lines = addons.remove_recorded(run=fake_run)
    assert lines == [f"{addons.ADDONS['bonjour'][0]}: entfernt"]
    assert ["winget", "uninstall", "--id", "Apple.Bonjour"] == calls[0][:4]
    assert not any("OpenRGB.OpenRGB" in c for cmd in calls for c in cmd)  # nicht da → nur vergessen
    assert addons.recorded() == []


def test_vbcable_found_language_independent():
    out = ("Veröffentlichter Name: oem12.inf\nOriginalname: vbmmecable64_win7.inf\nAnbieter: VB-Audio\n\n"
           "Published Name: oem7.inf\nOriginal Name: nvhda.inf\n\n"
           "Published Name:     oem31.inf\nOriginal Name:      vbMmeCable64_win10.inf\n")
    run = lambda cmd, timeout=60: subprocess.CompletedProcess(cmd, 0, out, "")  # noqa: E731
    assert addons._vbcable_infs(run) == ["oem12.inf", "oem31.inf"]


def test_main_entfernen_and_bad_args(records, monkeypatch, capsys):
    monkeypatch.setattr(addons, "remove_recorded", lambda: [])
    assert addons.main("entfernen") == 0
    assert "Keine" in capsys.readouterr().out
    assert addons.main("quatsch") == 2


def test_apt_script_marks_only_new_packages_auto():
    script = addons.apt_install_script(["openrgb", "uxplay"])
    assert 'dpkg -s "$p"' in script and "apt-mark auto $new" in script
    assert "install -y openrgb uxplay" in script


def test_self_command_runs_alupc():
    cmd = addons.self_command("--zusatz", "entfernen")
    assert cmd[-2:] == ["--zusatz", "entfernen"] and ("-m" in cmd or cmd[0].lower().endswith(".exe"))


def test_com_errors_do_not_carry_objects_to_other_threads():
    """Windows-Ton (COM): Fehler kommen nur als Text an – Objekte aus dem Ton-Thread werden dort freigegeben,
    nicht später zufällig im Hauptthread (das war ein Absturz unter Windows ohne Audiogerät)."""
    import threading
    import weakref

    from alupc import audio

    freed_in = []

    class ComLike:
        def __del__(self):
            freed_in.append(threading.current_thread().name)

    refs = []

    def boom():
        obj = ComLike()
        refs.append(weakref.ref(obj))
        raise OSError("kein Audiogerät")

    with pytest.raises(RuntimeError, match="OSError: kein Audiogerät"):
        audio._on_com(boom)
    assert refs[0]() is None
    assert freed_in == ["alupc-ton"]
