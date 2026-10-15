"""Miracast: empfangen (Windows „Drahtlose Anzeige“) und senden (Windows Win+K, Linux GNOME Network Displays).
Echte Miracast-Geräte gibt es im Test nicht – geprüft werden Erkennung, Befehle und die Bedienung."""

from __future__ import annotations

import subprocess

import pytest

from alupc.platform import miracast
from test_gui import env, pump  # noqa: F401


def test_parse_app_and_driver_support():
    assert miracast.parse_app('{"Name":"Drahtlose Anzeige","AppID":"Microsoft.WirelessDisplay_8wekyb3d8bbwe!App"}') \
        == {"name": "Drahtlose Anzeige", "app_id": "Microsoft.WirelessDisplay_8wekyb3d8bbwe!App"}
    assert miracast.parse_app("") is None and miracast.parse_app("[]") is None
    de = "Unterstützte drahtlose Anzeige: Ja (Grafiktreiber: Ja, WLAN-Treiber: Ja)"
    en = "    Wireless Display Supported: No (Graphics Driver: Yes, Wi-Fi Driver: No)"
    assert miracast.parse_wireless_display(de) is True
    assert miracast.parse_wireless_display(en) is False
    assert miracast.parse_wireless_display("Es ist kein WLAN-Adapter vorhanden") is None


def test_install_command_uses_dism_capability():
    cmd = " ".join(miracast.install_command())
    assert "dism.exe" in cmd and "-Verb RunAs" in cmd and miracast.CAPABILITY in cmd


def test_linux_sender_detection():
    assert miracast.linux_sender_command(which=lambda n: "/usr/bin/x" if n == "gnome-network-displays" else None) \
        == ["gnome-network-displays"]
    flatpak = lambda n: "/usr/bin/flatpak" if n == "flatpak" else None  # noqa: E731
    ok = lambda *a, **k: subprocess.CompletedProcess(a, 0)  # noqa: E731
    bad = lambda *a, **k: subprocess.CompletedProcess(a, 1)  # noqa: E731
    assert miracast.linux_sender_command(which=flatpak, run=ok) == ["flatpak", "run", miracast.FLATPAK_ID]
    assert miracast.linux_sender_command(which=flatpak, run=bad) == []
    assert miracast.linux_sender_command(which=lambda n: None) == []
    assert miracast.linux_install_command(which=lambda n: "/x" if n == "apt-get" else None) == \
        ["pkexec", "apt-get", "install", "-y", "gnome-network-displays"]
    assert miracast.linux_install_command(which=lambda n: None) == []


def test_start_sending_linux(monkeypatch):
    monkeypatch.setattr(miracast, "IS_WINDOWS", False)
    monkeypatch.setattr(miracast, "linux_sender_command", lambda: [])
    assert miracast.start_sending().startswith("!GNOME Network Displays fehlt")
    started = []
    monkeypatch.setattr(miracast, "linux_sender_command", lambda: ["gnome-network-displays"])
    note = miracast.start_sending(popen=lambda cmd, **k: started.append(cmd))
    assert started == [["gnome-network-displays"]] and not note.startswith("!")


def test_start_sending_windows_presses_win_k(monkeypatch):
    monkeypatch.setattr(miracast, "IS_WINDOWS", True)
    pressed = []
    monkeypatch.setattr(miracast, "press_win_k", lambda: pressed.append(1))
    note = miracast.start_sending()
    assert pressed == [1] and "Verbinden" in note


def test_receive_on_linux_says_windows_only(env, monkeypatch):  # noqa: F811
    controller, window, _ = env
    monkeypatch.setattr(miracast, "IS_WINDOWS", False)
    got = []
    controller.message.connect(got.append)
    controller.run_command("miracast")
    assert got and "nur unter Windows" in got[-1]


def test_receive_on_windows_places_window(env, monkeypatch):  # noqa: F811
    controller, window, _ = env
    if controller.output_screen() is None:
        pytest.skip("kein zweiter Bildschirm in dieser Testumgebung")
    monkeypatch.setattr(miracast, "IS_WINDOWS", True)
    monkeypatch.setattr(miracast, "find_app", lambda: {"name": "Drahtlose Anzeige", "app_id": "X!App"})
    monkeypatch.setattr(miracast, "wireless_display_support", lambda: True)
    launched, placed = [], []
    monkeypatch.setattr(miracast, "launch", launched.append)
    monkeypatch.setattr(controller, "ensure_extended", lambda: None)
    monkeypatch.setattr(controller, "_place_handy_window", lambda *t, **k: placed.append(t))
    controller.run_command("miracast")
    for _ in range(100):
        pump()
        if launched:
            break
        import time

        time.sleep(0.02)
    assert launched and launched[0]["app_id"] == "X!App"
    assert placed and "Drahtlose Anzeige" in placed[0]
    assert controller.desktop_note.startswith("Miracast") and controller._handy_window == "miracast"


def test_receive_without_wifi_direct(env, monkeypatch):  # noqa: F811
    controller, window, _ = env
    if controller.output_screen() is None:
        pytest.skip("kein zweiter Bildschirm in dieser Testumgebung")
    monkeypatch.setattr(miracast, "IS_WINDOWS", True)
    monkeypatch.setattr(miracast, "find_app", lambda: None)
    monkeypatch.setattr(miracast, "wireless_display_support", lambda: False)
    got = []
    controller.message.connect(got.append)
    controller.run_command("miracast")
    for _ in range(100):
        pump()
        if got:
            break
    assert got and "geht auf diesem PC nicht" in got[-1]


def test_tile_menu_and_dialog_button(env, monkeypatch):  # noqa: F811
    controller, window, _ = env
    sent = []
    monkeypatch.setattr(miracast, "start_sending", lambda: sent.append(1) or "ok")
    menu = window.t_miracast._menu if hasattr(window.t_miracast, "_menu") else None
    from PySide6.QtWidgets import QMenu

    menu = QMenu()
    window._fill_miracast_menu(menu)
    texts = [a.text() for a in menu.actions() if a.text()]
    assert any(t.startswith("Senden") for t in texts) and any("installieren" in t for t in texts)
    monkeypatch.setattr(controller.sender, "scan", lambda: None)
    window.open_sender()
    window.sender_dialog.b_miracast.click()
    assert sent == [1]
    window.sender_dialog.hide()
