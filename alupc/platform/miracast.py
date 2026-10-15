"""Miracast – empfangen (Handy/Laptop → Bildschirm) und senden (AluPC → Miracast-Fernseher).

Empfangen geht nur unter Windows: Windows hat einen eigenen Empfänger, die App „Drahtlose Anzeige“ (Wireless
Display). AluPC findet die App, installiert sie bei Bedarf nach (optionales Windows-Feature, Administrator-Abfrage)
und legt ihr Fenster im Vollbild auf den Bildschirm. Das Bild empfängt Windows selbst. Unter Linux gibt es keinen
gepflegten Miracast-Empfänger (MiracleCast ist seit Jahren still) – dort bleibt es bei AirPlay.

Senden: Windows verbindet Miracast-Fernseher über „Verbinden“ (Win+K) – der Fernseher wird wie ein weiterer
Monitor angeschlossen. Linux: „GNOME Network Displays“ (Paket gnome-network-displays bzw. Flatpak), läuft auch
unter KDE; dort wählt man den Monitor, der gesendet wird.
Beides braucht WLAN mit Wi-Fi Direct (Adapter und Treiber müssen es können).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys

IS_WINDOWS = sys.platform.startswith("win")
CAPABILITY = "App.WirelessDisplay.Connect~~~~0.0.1.0"
FLATPAK_ID = "org.gnome.NetworkDisplays"
_NO_WINDOW = 0x08000000

FIND_SCRIPT = (
    "Get-StartApps | Where-Object { $_.AppID -like '*WirelessDisplay*' -or $_.AppID -like '*PPIProjection*' "
    "-or $_.Name -in @('Drahtlose Anzeige','Wireless Display') } | "
    "Select-Object -First 1 Name, AppID | ConvertTo-Json -Compress"
)


def _flags() -> int:
    return _NO_WINDOW if IS_WINDOWS else 0


def _powershell(script: str, timeout: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                          capture_output=True, text=True, timeout=timeout, creationflags=_flags())


# --------------------------------------------------------------------------- Empfangen (Windows)
def parse_app(output: str) -> dict | None:
    """Ausgabe von FIND_SCRIPT → {"name", "app_id"} oder None."""
    try:
        data = json.loads(output.strip() or "null")
    except json.JSONDecodeError:
        return None
    if isinstance(data, list):
        data = data[0] if data else None
    if not isinstance(data, dict) or not data.get("AppID"):
        return None
    return {"name": str(data.get("Name") or "Drahtlose Anzeige"), "app_id": str(data["AppID"])}


def find_app() -> dict | None:
    if not IS_WINDOWS:
        return None
    try:
        return parse_app(_powershell(FIND_SCRIPT).stdout)
    except (OSError, subprocess.SubprocessError):
        return None


def launch(app: dict) -> None:
    subprocess.Popen(["explorer.exe", f"shell:AppsFolder\\{app['app_id']}"], creationflags=_flags())


def install_command() -> list[str]:
    """Optionales Feature „Drahtlose Anzeige“ nachinstallieren (UAC-Abfrage, lädt von Windows Update)."""
    return ["powershell", "-NoProfile", "-Command",
            "Start-Process -FilePath dism.exe -Verb RunAs -Wait -ArgumentList "
            f"'/Online','/Add-Capability','/CapabilityName:{CAPABILITY}'"]


def install(run=subprocess.run) -> None:
    proc = run(install_command(), capture_output=True, text=True, timeout=1800, creationflags=_flags())
    if proc.returncode != 0:
        raise RuntimeError(((proc.stderr or proc.stdout or "abgebrochen").strip().splitlines() or ["abgebrochen"])[-1])
    if find_app() is None:
        raise RuntimeError("Installation nicht abgeschlossen (abgebrochen oder kein Windows Update erreichbar)")


def parse_wireless_display(output: str) -> bool | None:
    """Ausgabe von „netsh wlan show drivers“ → kann der PC Miracast? None = kein WLAN-Adapter."""
    low = output.lower()
    if "wireless display" not in low and "drahtlose anzeige" not in low:
        return None
    for line in output.splitlines():
        key, _, value = line.partition(":")
        k = key.lower()
        if ("wireless display" in k or "drahtlose anzeige" in k) and value.strip():
            first = value.strip().split()[0].lower().strip("(,")
            return first in ("yes", "ja", "oui", "sí", "si")
    return None


def wireless_display_support() -> bool | None:
    """Unterstützen WLAN-Adapter und Grafiktreiber „Drahtlose Anzeige“ (Miracast)? Nur Windows."""
    if not IS_WINDOWS:
        return None
    try:
        out = subprocess.run(["netsh", "wlan", "show", "drivers"], capture_output=True, timeout=15,
                             creationflags=_flags()).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    for enc in ("oem", "utf-8", "cp1252"):
        try:
            return parse_wireless_display(out.decode(enc))
        except (LookupError, UnicodeDecodeError):
            continue
    return None


def open_receive_settings() -> None:
    """Windows-Einstellung „Projizieren auf diesen PC“ (dort „Überall verfügbar“ wählen)."""
    subprocess.Popen(["cmd", "/c", "start", "", "ms-settings:project"], creationflags=_flags())


# --------------------------------------------------------------------------- Senden
def press_win_k() -> None:
    """Windows: „Verbinden“ öffnen (wie Win+K) – listet Miracast-Fernseher und verbindet sie."""
    import ctypes

    user32 = ctypes.windll.user32
    vk_lwin, vk_k, keyup = 0x5B, 0x4B, 0x0002
    user32.keybd_event(vk_lwin, 0, 0, 0)
    user32.keybd_event(vk_k, 0, 0, 0)
    user32.keybd_event(vk_k, 0, keyup, 0)
    user32.keybd_event(vk_lwin, 0, keyup, 0)


def linux_sender_command(which=shutil.which, run=subprocess.run) -> list[str]:
    """Linux: Befehl für GNOME Network Displays ([] = nicht installiert)."""
    if which("gnome-network-displays"):
        return ["gnome-network-displays"]
    if which("flatpak"):
        try:
            if run(["flatpak", "info", FLATPAK_ID], capture_output=True, timeout=15).returncode == 0:
                return ["flatpak", "run", FLATPAK_ID]
        except (OSError, subprocess.SubprocessError):
            pass
    return []


def linux_install_command(which=shutil.which) -> list[str]:
    """Linux: GNOME Network Displays nachinstallieren (Administrator-Abfrage)."""
    if which("apt-get"):
        return ["pkexec", "apt-get", "install", "-y", "gnome-network-displays"]
    if which("dnf"):
        return ["pkexec", "dnf", "install", "-y", "gnome-network-displays"]
    if which("flatpak"):
        return ["flatpak", "install", "-y", "--user", "flathub", FLATPAK_ID]
    return []


def start_sending(popen=subprocess.Popen) -> str:
    """Miracast-Senden öffnen. Rückgabe: Hinweis für die Meldung (oder Fehler, beginnt mit „!“)."""
    if IS_WINDOWS:
        try:
            press_win_k()
        except Exception as exc:  # noqa: BLE001
            return f"!„Verbinden“ ging nicht auf ({exc}) – bitte Win+K drücken."
        return ("Windows „Verbinden“ ist offen: Fernseher wählen. Er wird wie ein weiterer Monitor verbunden "
                "(Win+P: „Erweitern“, dann Setup → Bildschirm: den Fernseher wählen).")
    cmd = linux_sender_command()
    if not cmd:
        return "!GNOME Network Displays fehlt – „Installieren“ drücken (Paket gnome-network-displays)."
    try:
        popen(cmd, start_new_session=True)
    except OSError as exc:
        return f"!GNOME Network Displays startet nicht: {exc}"
    return "GNOME Network Displays ist offen: Fernseher wählen, dann den Monitor „Bildschirm“ zum Senden wählen."
