"""Kahoot (das echte) auf Monitor 2: Adresse aus Link/Quiz-ID, Website mit gespeicherter Anmeldung, Browser-Steuerung."""

from test_gui import env, pump  # noqa: F401

from alupc.kahoot import CREATE, host_url

QID = "1b2c3d4e-5f60-4718-9a0b-c1d2e3f4a5b6"


def test_host_url():
    assert host_url("") == CREATE
    assert host_url(QID) == f"https://play.kahoot.it/v2/?quizId={QID}"
    assert host_url(f"https://create.kahoot.it/details/mathe/{QID.upper()}") == f"https://play.kahoot.it/v2/?quizId={QID}"
    assert host_url(f"https://create.kahoot.it/share/quiz/{QID}") == f"https://play.kahoot.it/v2/?quizId={QID}"
    assert host_url("kahoot.it/challenge/123") == "https://kahoot.it/challenge/123"
    assert host_url("https://boese.example/kahoot.it") == CREATE  # nur echte Kahoot-Adressen


def test_command_shows_kahoot_with_login_profile(env, monkeypatch):  # noqa: F811
    controller, window, tmp = env
    opened = []
    monkeypatch.setattr(window, "open_browser_control", lambda: opened.append(1))
    controller.browser_control_requested.disconnect()
    controller.browser_control_requested.connect(window.open_browser_control)
    controller.start_kahoot(QID)
    pump()
    assert controller.content["type"] == "website" and controller.content["keep_login"]
    assert controller.content["url"].endswith(QID) and opened
    view = controller.output.content.view
    profile = view.page().profile()
    assert not profile.isOffTheRecord() and profile.persistentStoragePath().endswith("web-profil")
    controller.run_command("kahoot")
    pump()
    assert controller.content["url"] == CREATE
    from alupc import intents

    assert intents.understand(["kahoot"])[0] == "kahoot"
    controller.extend()
    pump()
