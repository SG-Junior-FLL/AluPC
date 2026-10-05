"""Hotspot: der PC macht selbst ein WLAN auf. Zwei Arten:

* **normal** – „Hotspot“-Kachel auf der Startseite: eigener Name/Passwort, an/aus wie ein Lichtschalter.
* **spiele** – Spiele-WLAN aus dem Minispiele-Fenster: offen (ohne Passwort, Linux) und mit **Anmeldeseite**:
  Wer sich verbindet, bekommt vom Handy sofort die „Im WLAN anmelden“-Seite – und das ist direkt die
  Spielsteuerung. Geht automatisch aus, wenn die Minispiele beendet werden.

Linux: NetworkManager (nmcli), PC-Adresse im Hotspot meist 10.42.0.1. Die Anmeldeseite braucht eine
Weiterleitung (Port 80 → AluPC) – das darf nur root: einmal Passwort (pkexec) beim Start, ein kleiner Wächter
nimmt die Regel wieder raus, sobald der Hotspot aus ist oder AluPC endet.
Windows: „Mobiler Hotspot“ (WinRT über PowerShell), Passwort ist dort Pflicht, Adresse 192.168.137.1. Eine
Anmeldeseite geht unter Windows nicht (Windows lässt fremden Verkehr nicht umleiten) – dann helfen die QR-Codes.

Achtung: Viele WLAN-Karten können nicht gleichzeitig Hotspot sein UND mit einem anderen WLAN verbunden – dann ist
der PC während des Hotspots ohne Internet (über Kabel geht beides). Alle Funktionen geben (ok, Meldung) zurück.
"""

from __future__ import annotations

import os
import secrets
import shutil
import subprocess
import sys
from pathlib import Path

CON_NAMES = {"normal": "AluPC-Hotspot", "spiele": "AluPC-Spiele"}
DEFAULT_SSID = {"normal": "AluPC", "spiele": "AluPC-Spiele"}
CON_NAME = CON_NAMES["spiele"]  # (älterer Name)
WINDOWS_IP = "192.168.137.1"
PORTAL_PORT = 8765
_PW_CHARS = "abcdefghjkmnpqrstuvwxyz23456789"  # ohne l/1/o/0 – leicht abzulesen
IS_WINDOWS = sys.platform.startswith("win")


def new_password() -> str:
    return "".join(secrets.choice(_PW_CHARS) for _ in range(10))


def settings(config, kind: str = "spiele") -> dict:
    """Name/Passwort des Hotspots (einmal erzeugt, dann gespeichert). Spiele-WLAN unter Linux: offen."""
    if kind == "spiele":
        hs = dict(config["games"].get("hotspot") or {})
    else:
        hs = dict(config.get("hotspot") or {})
    changed = False
    if not hs.get("ssid"):
        hs["ssid"], changed = DEFAULT_SSID[kind], True
    need_pw = kind == "normal" or IS_WINDOWS or hs.get("password")
    if "password" not in hs or (need_pw and len(hs.get("password") or "") < 8):
        hs["password"], changed = (new_password() if need_pw else ""), True
    if changed:
        if kind == "spiele":
            config["games"] = {**config["games"], "hotspot": hs}
        else:
            config["hotspot"] = hs
    return hs


def supported() -> tuple[bool, str]:
    if sys.platform.startswith("linux"):
        if not shutil.which("nmcli"):
            return False, "NetworkManager (nmcli) fehlt – Hotspot geht nur damit."
        return (True, "") if wifi_device() else (False, "Keine WLAN-Karte gefunden.")
    if IS_WINDOWS:
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


def _linux_start(ssid: str, password: str, run=_run, kind: str = "spiele",
                 hidden: bool = True) -> tuple[bool, str, str]:
    """Hotspot als eigene NetworkManager-Verbindung (AP-Modus, geteilt). hidden=True: Name wird nicht ausgestrahlt –
    das WLAN taucht in keiner Liste auf, man kommt nur per QR-Code oder mit Name + Passwort hinein."""
    dev = wifi_device(run)
    if not dev:
        return False, "Keine WLAN-Karte gefunden.", ""
    con = CON_NAMES[kind]
    run(["nmcli", "connection", "delete", con], 10)
    cmd = ["nmcli", "connection", "add", "type", "wifi", "ifname", dev, "con-name", con, "autoconnect", "no",
           "ssid", ssid, "802-11-wireless.mode", "ap", "802-11-wireless.band", "bg", "ipv4.method", "shared",
           "802-11-wireless.hidden", "yes" if hidden else "no"]
    if password:
        cmd += ["wifi-sec.key-mgmt", "wpa-psk", "wifi-sec.psk", password]
    code, out = run(cmd)
    if code == 0:
        code, out = run(["nmcli", "connection", "up", con])
    if code != 0:
        return False, f"Hotspot ging nicht: {out.splitlines()[-1] if out else 'unbekannter Fehler'}", ""
    seen = "unsichtbar – nur per QR-Code oder Name + Passwort" if hidden else f"über {dev}"
    return True, f"Hotspot „{ssid}“ läuft ({seen}).", _linux_ip(dev, run)


def _linux_stop(run=_run, kind: str = "spiele") -> tuple[bool, str]:
    code, out = run(["nmcli", "connection", "down", CON_NAMES[kind]], 15)
    return code == 0, "Hotspot aus." if code == 0 else (out or "Hotspot lief nicht.")


def _linux_active(run=_run) -> str:
    """Welcher AluPC-Hotspot läuft gerade („normal“/„spiele“, leer = keiner)?"""
    code, out = run(["nmcli", "-t", "-f", "NAME", "connection", "show", "--active"], 8)
    names = out.splitlines() if code == 0 else []
    return next((k for k, con in CON_NAMES.items() if con in names), "")


# ---- Anmeldeseite (Captive Portal): Port 80 aus dem Hotspot → AluPC
def portal_flag() -> Path:
    base = Path(os.environ.get("XDG_RUNTIME_DIR") or "/tmp")
    return base / f"alupc-portal-{os.getuid() if hasattr(os, 'getuid') else 0}"


def portal_script(dev: str, port: int, flag: Path, pid: int) -> str:
    """Root-Skript: Weiterleitung setzen, warten bis Flagge weg oder AluPC beendet, Weiterleitung entfernen."""
    rule = f"-i {dev} -p tcp --dport 80 -j REDIRECT --to-ports {int(port)} -m comment --comment alupc-portal"
    return (f"iptables -t nat -I PREROUTING {rule} || exit 1; "
            f"while [ -e '{flag}' ] && kill -0 {int(pid)} 2>/dev/null; do sleep 2; done; "
            f"iptables -t nat -D PREROUTING {rule}")


def start_portal(dev: str, port: int = PORTAL_PORT, spawn=None) -> tuple[bool, str]:
    if IS_WINDOWS:
        return False, "Anmeldeseite geht unter Windows nicht – die Handys nehmen den QR-Code."
    if not (shutil.which("pkexec") and shutil.which("iptables")):
        return False, "Anmeldeseite braucht pkexec und iptables."
    flag = portal_flag()
    flag.write_text("an")
    cmd = ["pkexec", "sh", "-c", portal_script(dev, port, flag, os.getpid())]
    try:
        (spawn or subprocess.Popen)(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL, start_new_session=True)
    except OSError as exc:
        flag.unlink(missing_ok=True)
        return False, f"Anmeldeseite ging nicht: {exc}"
    return True, "Anmeldeseite an: Handys öffnen die Spielsteuerung beim Verbinden selbst."


def stop_portal() -> None:
    try:
        portal_flag().unlink(missing_ok=True)  # der Wächter nimmt die Regel in ≤ 2 s raus
    except OSError:
        pass


# --------------------------------------------------------------------------- Windows (Mobiler Hotspot)
_PS_HEAD = r"""
$ErrorActionPreference = 'Stop'
trap { Write-Output ('FEHLER:' + $_.Exception.Message); exit 3 }
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
                       "WLAN). Alternativ: Router-WLAN eintragen.")
    for line in out.splitlines():
        if line.startswith("FEHLER:"):  # z. B. kein WLAN-Adapter, Funktion fehlt (Windows Server)
            why = line[7:].strip().split("(Exception from HRESULT")[0].strip().rstrip(".") or "unbekannter Fehler"
            return False, (f"Mobiler Hotspot geht auf diesem PC nicht ({why}). Hat er einen WLAN-Adapter? "
                           "Alternativ: vorhandenes WLAN eintragen.")
        if line.startswith("STATUS:"):
            status = line.split(":")[1]
            if status == "Success":
                return True, "Mobiler Hotspot läuft."
            return False, f"Windows meldet: {status}. Einstellungen → Netzwerk → Mobiler Hotspot prüfen."
    return False, "Mobiler Hotspot ging nicht: " + (out.splitlines()[-1] if out else "keine Antwort")


# --------------------------------------------------------------------------- gemeinsam
class Hotspot:
    """Merkt sich, welcher Hotspot von AluPC läuft (normal/spiele), seine Adresse und ob die Anmeldeseite an ist."""

    def __init__(self):
        self.ip = ""
        self.running = False
        self.kind = ""
        self.ssid = ""
        self.password = ""
        self.hidden = False
        self.portal = False
        self.message = ""

    def start(self, ssid: str, password: str, kind: str = "spiele", portal: bool = False,
              hidden: bool = True) -> tuple[bool, str]:
        ok, why = supported()
        if not ok:
            self.message = why
            return False, why
        if self.running and self.kind != kind:
            self.stop()  # nur ein Hotspot auf einmal (eine WLAN-Karte)
        if sys.platform.startswith("linux"):
            ok, msg, ip = _linux_start(ssid, password, kind=kind, hidden=hidden)
        else:
            password = password if len(password or "") >= 8 else new_password()
            code, out = _ps(_PS_START, {"ALUPC_SSID": ssid, "ALUPC_PW": password})
            ok, msg = windows_message(out)
            if ok and hidden:  # Windows kann den Namen des Mobilen Hotspots nicht verstecken
                msg += " (Unsichtbar geht unter Windows nicht – der Name ist in der WLAN-Liste zu sehen.)"
            ip = WINDOWS_IP if ok else ""
        self.running, self.ip, self.message = ok, ip, msg
        self.kind, self.ssid, self.password = (kind, ssid, password) if ok else ("", "", "")
        self.hidden = bool(ok and hidden and not IS_WINDOWS)
        self.portal = False
        if ok and portal:
            dev = wifi_device() if sys.platform.startswith("linux") else ""
            p_ok, p_msg = start_portal(dev) if dev else (False, "")
            self.portal = p_ok
            if p_msg:
                self.message = msg = f"{msg} {p_msg}"
        return ok, msg

    def stop(self) -> tuple[bool, str]:
        stop_portal()
        self.portal = False
        kind = self.kind or "spiele"
        if sys.platform.startswith("linux"):
            ok, msg = _linux_stop(kind=kind)
        elif IS_WINDOWS:
            ok, msg = windows_message(_ps(_PS_STOP)[1])
            msg = "Hotspot aus." if ok else msg
        else:
            ok, msg = False, ""
        self.running, self.ip, self.kind, self.message = False, "", "", msg
        return ok, msg

    def active(self) -> bool:
        if sys.platform.startswith("linux"):
            return bool(_linux_active())
        if IS_WINDOWS:
            return "STATE:On" in _ps(_PS_STATE, timeout=20)[1]
        return False


hotspot = Hotspot()
