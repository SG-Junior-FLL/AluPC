"""PC prüfen: Updates und Treiber – Auswertung der Werkzeuge (Windows + Linux) und die Seite unter „Geräte“."""

from test_gui import _until, env, pump  # noqa: F401

from alupc import pc_updates as pu

WINGET = """Name                       Id                         Version      Verfügbar    Quelle
-----------------------------------------------------------------------------------------
Mozilla Firefox (x64 de)   Mozilla.Firefox            128.0        129.0.1      winget
7-Zip 23.01 (x64)          7zip.7zip                  23.01        24.07        winget
2 Aktualisierungen verfügbar.
"""


def test_parse_windows_tools():
    items = pu.parse_winget(WINGET)
    assert [(i["name"], i["current"], i["new"], i["note"]) for i in items] == [
        ("Mozilla Firefox (x64 de)", "128.0", "129.0.1", "Mozilla.Firefox"), ("7-Zip 23.01 (x64)", "23.01", "24.07",
                                                                              "7zip.7zip")]
    assert pu.parse_winget("Es wurden keine installierten Pakete gefunden.") == []


def test_parse_linux_tools():
    apt = ("Auflistung… Fertig\nfirefox/noble-updates 129.0+build1 amd64 [aktualisierbar von: 128.0+build2]\n"
           "base-files/noble-updates 13ubuntu10.5 amd64 [upgradable from: 13ubuntu10.4]\n")
    assert [(i["name"], i["current"], i["new"]) for i in pu.parse_apt(apt)] == [
        ("firefox", "128.0+build2", "129.0+build1"), ("base-files", "13ubuntu10.4", "13ubuntu10.5")]
    dnf = "\nkernel.x86_64    6.9.1-200.fc40    updates\nObsoleting Packages\n"
    assert [(i["name"], i["new"]) for i in pu.parse_dnf(dnf)] == [("kernel", "6.9.1-200.fc40")]
    assert pu.parse_pacman("linux 6.9.1-1 -> 6.9.2-1\n")[0]["new"] == "6.9.2-1"
    assert pu.parse_flatpak("VLC\torg.videolan.VLC\t3.0.21\n")[0]["note"] == "org.videolan.VLC"
    assert pu.parse_snap("Name  Version  Rev  Publisher  Notes\ncore22  20240801  1612  canonical✓  base\n")[0][
        "name"] == "core22"
    fw = '{"Devices": [{"Name": "UEFI dbx", "Version": "217", "Releases": [{"Version": "371"}]}]}'
    assert pu.parse_fwupd(fw)[0]["new"] == "371" and pu.parse_fwupd("kein json") == []
    assert pu.parse_ubuntu_drivers("nvidia-driver-550, (kernel modules provided by linux-modules-nvidia)\n")[0][
        "name"] == "nvidia-driver-550"
    lspci = ("00:02.0 VGA compatible controller: Intel UHD\n\tKernel driver in use: i915\n"
             "03:00.0 Network controller: Broadcom BCM4360\n\tSubsystem: Apple\n"
             "00:14.0 USB controller: Intel xHCI\n")
    assert [d["name"] for d in pu.parse_lspci(lspci)] == ["Broadcom BCM4360"]


def test_scan_linux_uses_available_tools():
    calls = []

    def run(cmd, timeout):
        calls.append(cmd[0])
        return 0, {"apt": "x/y 2 amd64 [upgradable from: 1]\n", "lspci": "01:00.0 Audio device: X\n"}.get(cmd[0], "")

    result = {"updates": [], "drivers": [], "checked": [], "errors": []}
    pu._scan_linux(result, lambda _t: None, run=run, which=lambda p: p in ("apt", "lspci"))
    assert calls == ["apt", "lspci"] and result["checked"] == ["apt", "Geräte"]
    assert result["updates"][0]["name"] == "x" and result["drivers"][0]["note"] == "Kein Treiber geladen"
    empty = {"updates": [], "drivers": [], "checked": [], "errors": []}
    pu._scan_linux(empty, lambda _t: None, run=run, which=lambda p: False)
    assert empty["errors"]  # keine Paketverwaltung: ehrlich sagen, dass das System nicht geprüft wurde


def test_updates_page(env, monkeypatch):  # noqa: F811
    controller, window, _ = env
    fake = {"updates": [pu._item("Firefox", "128", "129", "winget", "Mozilla.Firefox")],
            "drivers": [pu._item("WLAN-Karte", source="Geräte-Manager", note="kein Treiber installiert")],
            "checked": ["winget", "Geräte-Manager"], "errors": []}
    monkeypatch.setattr(pu, "scan", lambda progress=None: (progress("…"), fake)[1])
    opened = []
    monkeypatch.setattr(pu, "open_updater", lambda kind="updates": opened.append(kind) or (True, "ok"))
    window.open_setup_section("Updates")
    pump()
    from alupc.ui.updates_page import UpdatesPage

    page = window.findChild(UpdatesPage)
    assert page is not None and window.stack.currentIndex() == 8
    assert window.subnav.isVisible() and window.subnav_group.button(8).isChecked()
    page.scan()
    assert _until(lambda: page.updates.topLevelItemCount() == 1)
    assert page.drivers.topLevelItem(0).text(1) == "kein Treiber installiert"
    assert "1 Updates" in page.status.text() and not page.winget_btn.isHidden()
    page.winget_btn.click()
    assert opened == ["programme"]
    window._go(0)
