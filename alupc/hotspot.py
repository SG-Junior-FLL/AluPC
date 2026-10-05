"""Eigenes WLAN für die Minispiele (Hotspot) – Handys verbinden sich per QR-Code, ganz ohne Router.

* Linux: NetworkManager (`nmcli device wifi hotspot`). Adresse des PCs im Hotspot meist 10.42.0.1.
  Achtung: Viele WLAN-Karten können nicht gleichzeitig Hotspot sein UND mit einem anderen WLAN verbunden – dann
  ist der PC während des Hotspots ohne Internet (über Kabel geht beides).
* Windows: der eingebaute „Mobile Hotspot“ (WinRT NetworkOperatorTetheringManager über PowerShell). Er teilt eine
  bestehende Internetverbindung – ganz ohne Netz lehnt Windows ihn ab. Adresse des PCs: 192.168.137.1.

Alle Funktionen geben (ok, Meldung) zurück und werfen nie – die Meldung ist für Menschen.
"""

from __future__ import annotations

import secrets
import shutil
import subprocess
import sys

CON_NAME = "AluPC-Hotspot"
DEFAULT_SSID = "AluPC-Spiele"
WINDOWS_IP = "192.168.137.1"
_PW_CHARS = "abcdefghjkmnpqrstuvwxyz23456789"  # ohne l/1/o/0 – leicht abzulesen


def new_password() -> str:
    return "".join(secrets.choice(_PW_CHARS) for _ in range(10))


def settings(config) -> dict:
    """Name/Passwort des Hotspots (einmal erzeugt, dann gespeichert)."""
    games = config["games"]
    hs = dict(games.get("hotspot") or {})
    changed = False
    if not hs.get("ssid"):
        hs["ssid"], changed = DEFAULT_SSID, True
    if len(hs.get("password") or "") < 8:
        hs["password"], changed = new_password(), True
    if changed:
        config["games"] = {**games, "hotspot": hs}
    return hs


def supported() -> tuple[bool, str]:
    if sys.platform.startswith("linux"):
        if not shutil.which("nmcli"):
            return False, "NetworkManager (nmcli) fehlt – Hotspot geht nur damit."
        return (True, "") if wifi_device() else (False, "Keine WLAN-Karte gefunden.")
    if sys.platform == "win32":
        return True, ""
    return False, "Hotspot gibt es nur unter Linux und Windows."


def _run(cmd: list[str], timeout: float = 25) -> tuple[int, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return r.returncode, (r.stdout + r.stderr).strip()
    except (OSError, subprocess.SubprocessError) as exc:
        return 1, str(exc)


# --------------------------------------------------------------------------- Linux (NetworkManager)
def wifi_device(run=_run) -> str:
    code, out = run(["nmcli", "-t", "-f", "DEVICE,TYPE", "device"], 8)
    if code != 0:
        return ""
    for line in out.splitlines():
        dev, _, kind = line.partition(":")
        if kind == "wifi":
            return dev
    return ""


def _linux_ip(dev: str, run=_run) -> str:
    code, out = run(["nmcli", "-g", "IP4.ADDRESS", "device", "show", dev], 8)
    first = out.splitlines()[0] if code == 0 and out else ""
    return first.split("/")[0].strip() or "10.42.0.1"


def _linux_start(ssid: str, password: str, run=_run) -> tuple[bool, str, str]:
    dev = wifi_device(run)
    if not dev:
        return False, "Keine WLAN-Karte gefunden.", ""
    code, out = run(["nmcli", "device", "wifi", "hotspot", "ifname", dev, "con-name", CON_NAME,
                     "ssid", ssid, "password", password])
    if code != 0:
        return False, f"Hotspot ging nicht: {out.splitlines()[-1] if out else 'unbekannter Fehler'}", ""
    return True, f"Hotspot „{ssid}“ läuft (über {dev}).", _linux_ip(dev, run)


def _linux_stop(run=_run) -> tuple[bool, str]:
    code, out = run(["nmcli", "connection", "down", CON_NAME], 15)
    return code == 0, "Hotspot aus." if code == 0 else (out or "Hotspot lief nicht.")


def _linux_active(run=_run) -> bool:
    code, out = run(["nmcli", "-t", "-f", "NAME", "connection", "show", "--active"], 8)
    return code == 0 and CON_NAME in out.splitlines()


# --------------------------------------------------------------------------- Windows (Mobiler Hotspot)
_PS_HEAD = r"""
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$m = [System.WindowsRuntimeSystemExtensions].GetMethods()
$opT = ($m | ? { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and
         $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
$actT = ($m | ? { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and
          $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncAction' })[0]
function AwaitOp($op, $type) { $t = $opT.MakeGenericMethod($type).Invoke($null, @($op)); $t.Wait(-1) | Out-Null; $t.Result }
function AwaitAct($a) { $t = $actT.Invoke($null, @($a)); $t.Wait(-1) | Out-Null }
$null = [Windows.Networking.Connectivity.NetworkInformation, Windows.Networking.Connectivity, ContentType=WindowsRuntime]
$null = [Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager, Windows.Networking.NetworkOperators, ContentType=WindowsRuntime]
$p = [Windows.Networking.Connectivity.NetworkInformation]::GetInternetConnectionProfile()
if ($p -eq $null) { Write-Output 'FEHLER:keine Internetverbindung'; exit 2 }
$tm = [Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager]::CreateFromConnectionProfile($p)
"""

_PS_START = _PS_HEAD + r"""
$c = $tm.GetCurrentAccessPointConfiguration()
$c.Ssid = $env:ALUPC_SSID
$c.Passphrase = $env:ALUPC_PW
AwaitAct ($tm.ConfigureAccessPointAsync($c))
$r = AwaitOp ($tm.StartTetheringAsync()) ([Windows.Networking.NetworkOperators.NetworkOperatorTetheringOperationResult])
Write-Output ('STATUS:' + $r.Status + ':' + $r.AdditionalErrorMessage)
"""

_PS_STOP = _PS_HEAD + r"""
$r = AwaitOp ($tm.StopTetheringAsync()) ([Windows.Networking.NetworkOperators.NetworkOperatorTetheringOperationResult])
Write-Output ('STATUS:' + $r.Status)
"""

_PS_STATE = _PS_HEAD + r"""
Write-Output ('STATE:' + $tm.TetheringOperationalState)
"""


def _ps(script: str, env_extra: dict | None = None, timeout: float = 40) -> tuple[int, str]:
    import os

    env = {**os.environ, **(env_extra or {})}
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                            "-Command", script], capture_output=True, text=True, timeout=timeout, env=env,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return r.returncode, (r.stdout + r.stderr).strip()
    except (OSError, subprocess.SubprocessError) as exc:
        return 1, str(exc)


def windows_message(out: str) -> tuple[bool, str]:
    """PowerShell-Ausgabe → (ok, verständliche Meldung)."""
    if "FEHLER:keine Internetverbindung" in out:
        return False, ("Windows startet den Mobilen Hotspot nur, wenn der PC selbst Netz hat (LAN-Kabel oder "
                       "WLAN). Alternativ: Router-WLAN unten eintragen.")
    for line in out.splitlines():
        if line.startswith("STATUS:"):
            status = line.split(":")[1]
            if status == "Success":
                return True, "Mobiler Hotspot läuft."
            return False, f"Windows meldet: {status}. Einstellungen → Netzwerk → Mobiler Hotspot prüfen."
    return False, "Mobiler Hotspot ging nicht: " + (out.splitlines()[-1] if out else "keine Antwort")


# --------------------------------------------------------------------------- gemeinsam
class Hotspot:
    """Merkt sich, ob AluPC den Hotspot gestartet hat und unter welcher Adresse der PC dort erreichbar ist."""

    def __init__(self):
        self.ip = ""
        self.running = False
        self.message = ""

    def start(self, ssid: str, password: str) -> tuple[bool, str]:
        ok, why = supported()
        if not ok:
            self.message = why
            return False, why
        if sys.platform.startswith("linux"):
            ok, msg, ip = _linux_start(ssid, password)
        else:
            code, out = _ps(_PS_START, {"ALUPC_SSID": ssid, "ALUPC_PW": password})
            ok, msg = windows_message(out)
            ip = WINDOWS_IP if ok else ""
        self.running, self.ip, self.message = ok, ip, msg
        return ok, msg

    def stop(self) -> tuple[bool, str]:
        if sys.platform.startswith("linux"):
            ok, msg = _linux_stop()
        elif sys.platform == "win32":
            ok, msg = windows_message(_ps(_PS_STOP)[1])
            msg = "Hotspot aus." if ok else msg
        else:
            ok, msg = False, ""
        self.running, self.ip, self.message = False, "", msg
        return ok, msg

    def active(self) -> bool:
        if sys.platform.startswith("linux"):
            return _linux_active()
        if sys.platform == "win32":
            return "STATE:On" in _ps(_PS_STATE, timeout=20)[1]
        return False


hotspot = Hotspot()
