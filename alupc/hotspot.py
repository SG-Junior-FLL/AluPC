"""Hotspot: der PC macht selbst ein WLAN auf – EIN AluPC-WLAN für alles (Minispiele, Abstimmen, Chat, Foto-Wand,
Whiteboard, Steuern): Name/Passwort stecken im WLAN-QR-Code. Jede Seite hat auf Monitor 2 ihren eigenen QR-Code
(direkt die Seite – eine Anmeldeseite gibt es nicht mehr). Das WLAN bleibt an, wenn Minispiele starten oder enden.

Linux: NetworkManager (nmcli, „geteilt“), PC-Adresse im Hotspot meist 10.42.0.1.
Windows: „Mobiler Hotspot“ (WinRT über PowerShell), Passwort ist dort Pflicht, Adresse 192.168.137.1.
Hat der PC Internet, haben es die Handys im AluPC-WLAN auch (wie bei jedem Hotspot) – dann bleiben sie verbunden.

Achtung: Viele WLAN-Karten können nicht gleichzeitig Hotspot sein UND mit einem anderen WLAN verbunden – dann ist
der PC während des Hotspots ohne Internet (über Kabel geht beides). Alle Funktionen geben (ok, Meldung) zurück.
"""

from __future__ import annotations

import os
import secrets
import shutil
import subprocess
import sys
import time
from pathlib import Path

CON_NAMES = {"normal": "AluPC-Hotspot", "spiele": "AluPC-Spiele"}
DEFAULT_SSID = {"normal": "AluPC", "spiele": "AluPC-Spiele"}
CON_NAME = CON_NAMES["spiele"]  # (älterer Name)
WINDOWS_IP = "192.168.137.1"
_PW_CHARS = "abcdefghjkmnpqrstuvwxyz23456789"  # ohne l/1/o/0 – leicht abzulesen
IS_WINDOWS = sys.platform.startswith("win")


# Warum Handys das AluPC-WLAN verlassen und was hilft – EIN Text für Hotspot-Fenster und Monitor 2.
# Android und iOS verlassen bzw. meiden WLANs ohne Internet; eine Einstellung, die das überall abstellt, gibt es nicht.
STAY_WHY = ("Hat der PC selbst kein Internet (z. B. weil seine WLAN-Karte gerade das AluPC-WLAN macht und kein Kabel "
            "steckt), hat auch das AluPC-WLAN keins. Android und iPhone/iPad verlassen solche WLANs manchmal nach ein "
            "paar Sekunden (oder nehmen mobile Daten) – später verbinden sie sich wieder.")
STAY_STEPS = [
    ("Android", ["Mobile Daten ausschalten (Schnelleinstellungen) – dann weicht das Handy nicht aus.",
                 "Fragt das Handy „Kein Internet – verbunden bleiben?“: Ja."]),
    ("iPhone / iPad", ["„WLAN-Unterstützung“ aus: Einstellungen → Mobilfunk → ganz unten.",
                       "Fragt das Gerät nach „Ohne Internet verwenden“: ja."]),
    ("Klappt immer", ["PC per LAN-Kabel ins Internet – dann hat auch das AluPC-WLAN Internet und jedes Handy bleibt."]),
]


def stay_help_html() -> str:
    """Anleitung als HTML (Hotspot-Fenster)."""
    import html

    out = [html.escape(STAY_WHY), "<br>"]
    for title, lines in STAY_STEPS:
        out.append(f"<br><b>{html.escape(title)}</b><ul style='margin:4px 0 0 0'>")
        out += [f"<li>{html.escape(line)}</li>" for line in lines]
        out.append("</ul>")
    return "".join(out)


def new_password() -> str:
    return "".join(secrets.choice(_PW_CHARS) for _ in range(10))


def settings(config, kind: str = "normal") -> dict:
    """Name/Passwort des AluPC-WLANs (einmal erzeugt, dann gespeichert) – es gibt nur eins (kind wird ignoriert).
    Linux und Windows gleich: immer mit Passwort (Windows kann es nicht anders) – per Abgleich ist es dann auf beiden
    Systemen dasselbe WLAN."""
    hs = dict(config.get("hotspot") or {})
    changed = False
    if not hs.get("ssid"):
        hs["ssid"], changed = DEFAULT_SSID["normal"], True
    if len(hs.get("password") or "") < 8:
        hs["password"], changed = new_password(), True
    if changed:
        config["hotspot"] = hs
    return hs


def supported() -> tuple[bool, str]:
    if sys.platform.startswith("linux"):
        if not shutil.which("nmcli"):
            return False, "NetworkManager (nmcli) fehlt – Hotspot geht nur damit."
        if not shutil.which("dnsmasq") and not Path("/usr/sbin/dnsmasq").exists():
            # ohne dnsmasq kann NetworkManager keinen Hotspot verteilen (DHCP) – er fällt dann aufs normale WLAN zurück
            return False, "Für den Hotspot fehlt „dnsmasq-base“ (sudo apt install dnsmasq-base) – NetworkManager braucht es."
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


VISIBLE_NOTE = "Unsichtbar ging mit dieser WLAN-Karte nicht – der Name ist in der WLAN-Liste zu sehen."


def _ap_capable(dev: str, run=_run) -> bool | None:
    """Kann die WLAN-Karte einen Hotspot aufmachen (AP-Modus)? None = unbekannt."""
    code, out = run(["nmcli", "-g", "WIFI-PROPERTIES.AP", "device", "show", dev], 8)
    value = out.strip().lower() if code == 0 else ""
    return True if value == "yes" else False if value == "no" else None


def _connection_on(dev: str, run=_run) -> str:
    code, out = run(["nmcli", "-g", "GENERAL.CONNECTION", "device", "show", dev], 8)
    return out.strip() if code == 0 else ""


def _linux_start(ssid: str, password: str, run=_run, kind: str = "spiele",
                 hidden: bool = True) -> tuple[bool, str, str]:
    """Hotspot als eigene NetworkManager-Verbindung (AP-Modus, geteilt). hidden=True: Name wird nicht ausgestrahlt –
    das WLAN taucht in keiner Liste auf, man kommt nur per QR-Code oder mit Name + Passwort hinein."""
    dev = wifi_device(run)
    if not dev:
        return False, "Keine WLAN-Karte gefunden.", ""
    if _ap_capable(dev, run) is False:
        return False, (f"Diese WLAN-Karte ({dev}) kann keinen Hotspot aufmachen (kein AP-Modus) – sie kann sich nur "
                       "mit einem WLAN verbinden. Abhilfe: ein USB-WLAN-Stick, der AP-Modus kann."), ""
    con = CON_NAMES[kind]
    run(["nmcli", "connection", "delete", con], 10)
    cmd = ["nmcli", "connection", "add", "type", "wifi", "ifname", dev, "con-name", con, "autoconnect", "no",
           "ssid", ssid, "802-11-wireless.mode", "ap", "802-11-wireless.band", "bg", "ipv4.method", "shared",
           "ipv6.method", "disabled",  # nur IPv4 (eine feste PC-Adresse für die QR-Codes)
           "802-11-wireless.hidden", "yes" if hidden else "no"]
    if password:
        cmd += ["wifi-sec.key-mgmt", "wpa-psk", "wifi-sec.psk", password]
    code, out = run(cmd)
    if code == 0:
        code, out = run(["nmcli", "connection", "up", con])
    note = ""
    if code != 0 and hidden:  # manche WLAN-Karten/Treiber können keinen unsichtbaren Hotspot → sichtbar versuchen
        run(["nmcli", "connection", "modify", con, "802-11-wireless.hidden", "no"], 10)
        retry, retry_out = run(["nmcli", "connection", "up", con])
        if retry == 0:
            code, out, hidden, note = 0, retry_out, False, " " + VISIBLE_NOTE
    if code != 0:
        return False, f"Hotspot ging nicht: {out.splitlines()[-1] if out else 'unbekannter Fehler'}", ""
    now = _connection_on(dev, run)
    if now and now != con:  # NetworkManager hat sich stattdessen mit einem WLAN verbunden
        run(["nmcli", "connection", "down", con], 10)
        return False, (f"Hotspot ging nicht: die WLAN-Karte ist mit „{now}“ verbunden statt das WLAN „{ssid}“ "
                       "aufzumachen."), ""
    seen = "unsichtbar – nur per QR-Code oder Name + Passwort" if hidden else f"über {dev}"
    return True, f"Hotspot „{ssid}“ läuft ({seen}).{note}", _linux_ip(dev, run)


def _linux_stop(run=_run, kind: str = "spiele") -> tuple[bool, str]:
    code, out = run(["nmcli", "connection", "down", CON_NAMES[kind]], 15)
    return code == 0, "Hotspot aus." if code == 0 else (out or "Hotspot lief nicht.")


def _linux_active(run=_run) -> str:
    """Welcher AluPC-Hotspot läuft gerade („normal“/„spiele“, leer = keiner)?"""
    code, out = run(["nmcli", "-t", "-f", "NAME", "connection", "show", "--active"], 8)
    names = out.splitlines() if code == 0 else []
    return next((k for k, con in CON_NAMES.items() if con in names), "")


# ---- Geräte im AluPC-WLAN
NAMES: dict[str, str] = {}  # IP → Name, den das Gerät beim Mitmachen eingegeben hat (Spiel, Chat …)


def note_name(ip: str, name: str) -> None:
    name = " ".join(str(name or "").split())[:30]
    if ip and name:
        NAMES[ip] = name


def neighbors(dev: str = "", ip: str = "") -> dict[str, str]:
    """Geräte im Hotspot-Netz: IP → MAC (aus der ARP-Tabelle des PCs)."""
    import ipaddress
    import re

    net = None
    try:
        net = ipaddress.ip_network(f"{ip or hotspot.ip}/24", strict=False)
    except ValueError:
        pass
    out: dict[str, str] = {}
    if sys.platform.startswith("linux"):
        try:
            for line in Path("/proc/net/arp").read_text().splitlines()[1:]:
                parts = line.split()
                if len(parts) >= 6 and parts[3] != "00:00:00:00:00:00" and (not dev or parts[5] == dev):
                    out[parts[0]] = parts[3].lower()
        except OSError:
            pass
    elif IS_WINDOWS:
        code, text = _run(["arp", "-a"], 8)
        # Sprache egal („dynamic“/„dynamisch“): Broadcast und Multicast fallen unten weg
        for m in re.finditer(r"(\d+\.\d+\.\d+\.\d+)\s+([0-9a-fA-F]{2}(?:-[0-9a-fA-F]{2}){5})\b", text):
            mac = m.group(2).replace("-", ":").lower()
            if mac != "ff:ff:ff:ff:ff:ff" and not int(mac[:2], 16) & 1:
                out[m.group(1)] = mac
    if net is not None:
        out = {k: v for k, v in out.items() if ipaddress.ip_address(k) in net and k != (ip or hotspot.ip)}
    return out


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
$TM = [Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager]
$p = [Windows.Networking.Connectivity.NetworkInformation]::GetInternetConnectionProfile()
if ($p -eq $null) {
  # kein Internet: eine andere Verbindung nehmen, über die Windows einen Hotspot aufmachen kann (z. B. LAN ohne Internet)
  foreach ($q in [Windows.Networking.Connectivity.NetworkInformation]::GetConnectionProfiles()) {
    try { if ([string]($TM::GetTetheringCapabilityFromConnectionProfile($q)) -eq 'Enabled') { $p = $q; break } } catch {}
  }
}
if ($p -eq $null) { Write-Output 'FEHLER:keine Internetverbindung'; exit 2 }
$cap = [string]($TM::GetTetheringCapabilityFromConnectionProfile($p))
if ($cap -ne 'Enabled') { Write-Output ('KANN:' + $cap); exit 4 }
$tm = $TM::CreateFromConnectionProfile($p)
"""

_PS_START = _PS_HEAD + r"""
$c = $tm.GetCurrentAccessPointConfiguration()
$c.Ssid = $env:ALUPC_SSID
$c.Passphrase = $env:ALUPC_PW
AwaitAct ($tm.ConfigureAccessPointAsync($c))
# Energiesparen aus: sonst schaltet Windows den Hotspot ab, wenn kurz kein Gerät verbunden ist (Handy-Display aus)
try { [Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager]::DisableNoConnectionsTimeout() } catch {}
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


# Windows: Gründe, warum der Mobile Hotspot nicht geht (TetheringCapability / Ergebnis von StartTetheringAsync)
WINDOWS_REASONS = {
    "DisabledByGroupPolicy": "per Gruppenrichtlinie gesperrt (Schul-/Firmen-PC?)",
    "DisabledByHardwareLimitation": "die WLAN-Karte kann keinen Hotspot",
    "DisabledByOperator": "vom Mobilfunkanbieter gesperrt",
    "DisabledBySku": "diese Windows-Version kann keinen Mobilen Hotspot",
    "DisabledByRequiredAppNotInstalled": "eine nötige App fehlt",
    "DisabledDueToUnknownCause": "Windows nennt keinen Grund",
    "DisabledBySystemCapability": "vom System gesperrt",
    "WiFiDeviceOff": "WLAN ist ausgeschaltet – erst WLAN einschalten (Taskleiste oder Flugmodus aus)",
    "OperationInProgress": "Windows startet ihn gerade schon – kurz warten und nochmal",
    "NetworkLimitedConnectivity": "die geteilte Verbindung hat nur eingeschränkten Zugang",
    "EntitlementCheckFailure": "vom Anbieter nicht freigegeben",
    "EntitlementCheckTimeout": "Freigabe-Prüfung dauerte zu lange",
    "MobileBroadbandDeviceOff": "Mobilfunk ist aus",
    "BluetoothDeviceOff": "Bluetooth ist aus",
}


def _last_try_file() -> Path:
    from .config import config_dir

    return config_dir() / "hotspot-letzter-versuch.txt"


def note_windows_try(out: str) -> None:
    """Rohe Antwort von Windows aufheben (für den Fehlerbericht) – ohne Passwort, das steht nie in der Ausgabe."""
    try:
        path = _last_try_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(time.strftime("%d.%m.%Y %H:%M:%S") + "\n" + (out or "(keine Ausgabe)")[-4000:], "utf-8")
    except OSError:
        pass


def windows_message(out: str) -> tuple[bool, str]:
    """PowerShell-Ausgabe → (ok, verständliche Meldung)."""
    if "FEHLER:keine Internetverbindung" in out:
        return False, ("Windows startet den Mobilen Hotspot nur, wenn der PC selbst Netz hat (LAN-Kabel oder "
                       "WLAN). Alternativ: Router-WLAN eintragen.")
    for line in out.splitlines():
        if line.startswith("KANN:"):
            code = line[5:].strip()
            return False, f"Mobiler Hotspot geht nicht: {WINDOWS_REASONS.get(code, code)} ({code})."
        if line.startswith("FEHLER:"):  # z. B. kein WLAN-Adapter, Funktion fehlt (Windows Server)
            why = line[7:].strip().split("(Exception from HRESULT")[0].strip().rstrip(".") or "unbekannter Fehler"
            return False, (f"Mobiler Hotspot geht auf diesem PC nicht ({why}). Hat er einen WLAN-Adapter? "
                           "Alternativ: vorhandenes WLAN eintragen.")
        if line.startswith("STATUS:"):
            status = line.split(":")[1]
            if status == "Success":
                return True, "Mobiler Hotspot läuft."
            extra = line.split(":", 2)[2].strip() if line.count(":") >= 2 else ""
            why = WINDOWS_REASONS.get(status, "")
            return False, (f"Windows meldet: {status}" + (f" – {why}" if why else "") + (f" ({extra})" if extra else "")
                           + ". Einstellungen → Netzwerk und Internet → Mobiler Hotspot prüfen.")
    return False, "Mobiler Hotspot ging nicht: " + (out.splitlines()[-1] if out else "keine Antwort")


# Windows-Firewall: Handys im AluPC-WLAN müssen AluPCs Seiten erreichen (Port 8765–8774). Windows stuft das Netz des
# Mobilen Hotspots oft als „öffentlich“ ein – dann käme ohne Freigabe nichts an. Der Installer legt sie an; fehlt sie
# (z. B. ZIP-Version), fragt AluPC beim ersten WLAN-Start einmal nach Administrator-Rechten.
FIREWALL_RULE = "AluPC WLAN"


def firewall_rule_ok(run=None) -> bool:
    code, out = (run or _run)(["netsh", "advfirewall", "firewall", "show", "rule", f"name={FIREWALL_RULE}"], 15)
    return code == 0 and FIREWALL_RULE in out


def ensure_firewall_rule(run=None, ps=None) -> str:
    """Windows: Freigabe anlegen, falls sie fehlt (einmal „Ja“). Rückgabe: Hinweis, falls es nicht geklappt hat."""
    if not IS_WINDOWS or firewall_rule_ok(run):
        return ""
    args = (f'advfirewall firewall add rule name="{FIREWALL_RULE}" dir=in action=allow protocol=TCP '
            'localport=8765-8774 profile=any')
    (ps or _ps)(f"Start-Process -FilePath netsh -ArgumentList '{args}' -Verb RunAs -WindowStyle Hidden -Wait",
                timeout=180)
    if firewall_rule_ok(run):
        return ""
    return ("Firewall-Freigabe fehlt (Administrator-Frage abgelehnt?) – Handys erreichen AluPC dann evtl. nicht. "
            "Beim nächsten WLAN-Start fragt AluPC nochmal.")


# --------------------------------------------------------------------------- gemeinsam
def windows_hotspot_ip() -> str:
    """Adresse des PCs im Mobilen Hotspot: Windows nimmt die der Internetfreigabe (Standard 192.168.137.1,
    änderbar in der Registry „ScopeAddress“)."""
    import ipaddress

    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            r"SYSTEM\CurrentControlSet\Services\SharedAccess\Parameters") as key:
            value = str(winreg.QueryValueEx(key, "ScopeAddress")[0]).strip()
        return str(ipaddress.IPv4Address(value))
    except (ImportError, OSError, ValueError):
        return WINDOWS_IP


class Hotspot:
    """Merkt sich, ob AluPCs Hotspot läuft, seine Adresse, Name und Passwort."""

    def __init__(self):
        self.ip = ""
        self.running = False
        self.kind = ""
        self.ssid = ""
        self.password = ""
        self.hidden = False
        self.message = ""

    def start(self, ssid: str, password: str, kind: str = "normal", hidden: bool = True, **_old) -> tuple[bool, str]:
        kind = "normal"  # nur noch EIN AluPC-WLAN (früher eigenes Spiele-WLAN)
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
            out = _ps(_PS_START, {"ALUPC_SSID": ssid, "ALUPC_PW": password})[1]
            note_windows_try(out)
            ok, msg = windows_message(out)
            if ok:
                fw = ensure_firewall_rule()
                msg += f" {fw}" if fw else ""
            if ok and hidden:  # Windows kann den Namen des Mobilen Hotspots nicht verstecken
                msg += " (Unsichtbar geht unter Windows nicht – der Name ist in der WLAN-Liste zu sehen.)"
            hidden = False
            ip = windows_hotspot_ip() if ok else ""
        self.running, self.ip, self.message = ok, ip, msg
        self.kind, self.ssid, self.password = (kind, ssid, password) if ok else ("", "", "")
        self.hidden = bool(ok and hidden and not IS_WINDOWS and VISIBLE_NOTE not in msg)
        return ok, msg

    def stop(self) -> tuple[bool, str]:
        if sys.platform.startswith("linux"):
            ok, msg = _linux_stop(kind="normal")
            _linux_stop(kind="spiele")  # Rest einer älteren Version (eigenes Spiele-WLAN)
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
