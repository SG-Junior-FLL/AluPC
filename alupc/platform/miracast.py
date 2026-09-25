"""Miracast (Windows): Windows hat einen eigenen Empfänger, die App „Drahtlose Anzeige“ (Wireless Display).

AluPC findet die App, installiert sie bei Bedarf nach (optionales Windows-Feature, Administrator-Abfrage)
und legt ihr Fenster im Vollbild auf Monitor 2. Das Bild selbst empfängt Windows – AluPC kann es nicht
in eigene Szenen einbauen. Unter Linux gibt es keinen brauchbaren Miracast-Empfänger.
"""

from __future__ import annotations

import json
import subprocess
import sys

IS_WINDOWS = sys.platform.startswith("win")
CAPABILITY = "App.WirelessDisplay.Connect~~~~0.0.1.0"
_NO_WINDOW = 0x08000000

FIND_SCRIPT = (
    "Get-StartApps | Where-Object { $_.AppID -like '*WirelessDisplay*' -or $_.AppID -like '*PPIProjection*' "
    "-or $_.Name -in @('Drahtlose Anzeige','Wireless Display','Verbinden','Connect') } | "
    "Select-Object -First 1 Name, AppID | ConvertTo-Json -Compress"
)


def _powershell(script: str, timeout: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                          capture_output=True, text=True, timeout=timeout,
                          creationflags=_NO_WINDOW if IS_WINDOWS else 0)


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
    subprocess.Popen(["explorer.exe", f"shell:AppsFolder\\{app['app_id']}"], creationflags=_NO_WINDOW)


def install_command() -> list[str]:
    """Optionales Feature „Drahtlose Anzeige“ nachinstallieren (UAC-Abfrage, lädt von Windows Update)."""
    return ["powershell", "-NoProfile", "-Command",
            "Start-Process -FilePath dism.exe -Verb RunAs -Wait -ArgumentList "
            f"'/Online','/Add-Capability','/CapabilityName:{CAPABILITY}'"]


def install() -> None:
    proc = subprocess.run(install_command(), capture_output=True, text=True, timeout=1800,
                          creationflags=_NO_WINDOW)
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "abgebrochen").strip().splitlines()[-1])
    if find_app() is None:
        raise RuntimeError("Installation nicht abgeschlossen (abgebrochen oder kein Windows Update erreichbar)")


def parse_wireless_display(output: str) -> bool | None:
    """Ausgabe von „netsh wlan show drivers“ → kann der PC Miracast empfangen? None = kein WLAN-Adapter."""
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
                             creationflags=_NO_WINDOW).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    for enc in ("oem", "utf-8", "cp1252"):
        try:
            return parse_wireless_display(out.decode(enc))
        except (LookupError, UnicodeDecodeError):
            continue
    return None


def open_settings() -> None:
    """Windows-Einstellung „Projizieren auf diesen PC“ (dort „Überall verfügbar“ wählen)."""
    subprocess.Popen(["cmd", "/c", "start", "", "ms-settings:project"], creationflags=_NO_WINDOW)
