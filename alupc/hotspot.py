"""Hotspot: der PC macht selbst ein WLAN auf. Zwei Arten:

* **normal** – „Hotspot“-Kachel auf der Startseite: eigener Name/Passwort, an/aus wie ein Lichtschalter – auch mit
  Anmeldeseite (Mitspielen oder AluPC steuern mit Freigabe am PC).
* **spiele** – Spiele-WLAN aus dem Minispiele-Fenster: mit Passwort (steckt im WLAN-QR-Code) und **Anmeldeseite**:
  Wer sich verbindet, bekommt vom Handy sofort die „Im WLAN anmelden“-Seite – und das ist direkt die
  Spielsteuerung. Geht automatisch aus, wenn die Minispiele beendet werden.

Linux: NetworkManager (nmcli), PC-Adresse im Hotspot meist 10.42.0.1. Die Anmeldeseite braucht eine
Weiterleitung (Port 80 → AluPC) – das darf nur root: einmal Passwort (pkexec) beim Start, ein kleiner Wächter
nimmt die Regel wieder raus, sobald der Hotspot aus ist oder AluPC endet.
Damit es auch ohne Internet am PC klappt, beantwortet der Hotspot die Prüf-Adressen der Handys selbst
(dnsmasq-Eintrag „interface-name“ – zeigt auf die eigene Adresse im Hotspot).
Windows: „Mobiler Hotspot“ (WinRT über PowerShell), Passwort ist dort Pflicht, Adresse 192.168.137.1. Die
Anmeldeseite geht genauso wie unter Linux: AluPCs eigener DNS auf 192.168.137.1:53 beantwortet die Namensfragen
der Handys (im Spiele-WLAN jede → PC), einmal „Ja“ (Administrator) für Port 80 → AluPC („netsh portproxy“),
Firewall und (Spiele-WLAN) kein Weiterleiten ins Internet; ein Wächter räumt danach auf.

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
    """Name/Passwort des Hotspots (einmal erzeugt, dann gespeichert). Linux und Windows gleich: immer mit Passwort
    (Windows kann es nicht anders) – per Abgleich ist es dann auf beiden Systemen dasselbe WLAN."""
    if kind == "spiele":
        hs = dict(config["games"].get("hotspot") or {})
    else:
        hs = dict(config.get("hotspot") or {})
    changed = False
    if not hs.get("ssid"):
        hs["ssid"], changed = DEFAULT_SSID[kind], True
    if len(hs.get("password") or "") < 8:
        hs["password"], changed = new_password(), True
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
           "ipv6.method", "disabled",  # kein IPv6 im Hotspot: sonst ginge DNS/Internet an der Anmeldeseite vorbei
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
    import tempfile

    base = Path(os.environ.get("XDG_RUNTIME_DIR") or tempfile.gettempdir())
    return base / f"alupc-portal-{os.getuid() if hasattr(os, 'getuid') else 0}"


# Adressen, mit denen Handys/Laptops prüfen, ob sie „im Internet“ sind (Android, Hersteller, iPhone, Firefox, Linux)
PORTAL_HOSTS = ["connectivitycheck.gstatic.com", "connectivitycheck.android.com", "clients3.google.com",
                "connect.rom.miui.com",
                "connectivitycheck.platform.hicloud.com", "captive.apple.com", "www.appleiana.com",
                "www.itools.info", "www.ibook.info", "www.airport.us", "www.thinkdifferent.us",
                "detectportal.firefox.com", "nmcheck.gnome.org", "connectivity-check.ubuntu.com"]
# Nur im Linux-Hotspot: Windows-Laptops als Gäste. Unter Windows nicht – sonst hielte sich der PC selbst für „im Hotel“.
WINDOWS_CHECK_HOSTS = ["www.msftconnecttest.com", "www.msftncsi.com"]
DNS_PORT = 8753


def portal_script(dev: str, port: int, flag: Path, pid: int, closed: bool = True, dns_port: int = DNS_PORT) -> str:
    """Root-Skript (Linux) – wie ein Hotel-WLAN:
    * jede Namensfrage aus dem Hotspot (UDP/TCP 53) → AluPCs eigener DNS (portal_dns.py),
    * Webseiten (Port 80) → Anmeldeseite von AluPC (geschlossen: JEDE Adresse, offen: nur der PC selbst),
    * geschlossen: nichts ins Internet weiterleiten (auch kein IPv6) – außer für Geräte, die am PC im
      Hotspot-Fenster „Internet“ bekommen haben: deren Adressen stehen in <Flagge>.internet; das Skript schaut
      alle 2 s nach und baut die Regeln (eigene Ketten alupc-nat/alupc-fwd) neu,
    * Ports für AluPC auf dieser Schnittstelle öffnen (falls eine Firewall läuft),
    dann „bereit“ melden, warten bis Flagge weg oder AluPC beendet, alles wieder entfernen."""
    tag = "-m comment --comment alupc-portal"
    local = "" if closed else "-m addrtype --dst-type LOCAL "
    d, f, dp, pp = dev, str(flag), int(dns_port), int(port)
    jumps = [f"-t nat -I PREROUTING -i {d} {tag} -j alupc-nat", f"-I FORWARD -i {d} {tag} -j alupc-fwd",
             f"-I INPUT -i {d} -p tcp --dport {pp} {tag} -j ACCEPT",
             f"-I INPUT -i {d} -p udp --dport {dp} {tag} -j ACCEPT",
             f"-I INPUT -i {d} -p tcp --dport {dp} {tag} -j ACCEPT"]
    undo = "; ".join("iptables " + j.replace(" -I ", " -D ", 1).replace("-I ", "-D ", 1) + " 2>/dev/null"
                     for j in jumps)
    ip6 = f"-I FORWARD -i {d} {tag} -j REJECT"
    final = "iptables -A alupc-fwd -j REJECT" if closed else "true"
    return f"""
F='{f}'
cleanup() {{
  {undo}
  ip6tables {ip6.replace("-I ", "-D ", 1)} 2>/dev/null
  iptables -t nat -F alupc-nat 2>/dev/null; iptables -t nat -X alupc-nat 2>/dev/null
  iptables -F alupc-fwd 2>/dev/null; iptables -X alupc-fwd 2>/dev/null
}}
build() {{
  iptables -t nat -F alupc-nat && iptables -F alupc-fwd || return 1
  for ip in $(cat "$F.internet" 2>/dev/null); do
    case "$ip" in ""|*[!0-9.]*) continue;; esac
    iptables -t nat -A alupc-nat -s "$ip" -j RETURN; iptables -A alupc-fwd -s "$ip" -j ACCEPT
  done
  iptables -t nat -A alupc-nat -p udp --dport 53 -j REDIRECT --to-ports {dp} &&
  iptables -t nat -A alupc-nat -p tcp --dport 53 -j REDIRECT --to-ports {dp} &&
  iptables -t nat -A alupc-nat -p tcp --dport 80 {local}-j REDIRECT --to-ports {pp} &&
  {final}
}}
cleanup
iptables -t nat -N alupc-nat && iptables -N alupc-fwd && build && {" && ".join("iptables " + j for j in jumps)} || {{ cleanup; exit 1; }}
{f"command -v ip6tables >/dev/null && ip6tables {ip6}" if closed else "true"}
echo ok > "$F.ok"
last=$(cat "$F.internet" 2>/dev/null)
while [ -e "$F" ] && kill -0 {int(pid)} 2>/dev/null; do
  sleep 2
  cur=$(cat "$F.internet" 2>/dev/null)
  if [ "$cur" != "$last" ]; then build; last=$cur; fi
done
cleanup
"""


def portal_script_windows(ip: str, port: int, flag: Path, pid: int, closed: bool = True,
                          hosts: bool = False) -> str:
    """Administrator-Skript (Windows) – wie unter Linux ein Hotel-WLAN:
    * Namensfragen der Handys beantwortet AluPCs eigener DNS (bindet 192.168.137.1:53 – genauer als der
      Windows-Hotspot-DNS auf 0.0.0.0:53, bekommt also alle Fragen); hier nur die Firewall dafür öffnen,
    * Webseiten (Port 80 an den PC) → Anmeldeseite von AluPC (portproxy),
    * geschlossen: Hotspot-Schnittstelle leitet nichts ins Internet weiter (Forwarding aus),
    * hosts=True nur als Notlösung, falls der eigene DNS nicht ging (dann nur die Prüf-Adressen → PC),
    „bereit“ melden, warten, alles wieder entfernen – auch wenn AluPC abstürzt."""
    names = ",".join(f"'{h}'" for h in PORTAL_HOSTS) if hosts else ""
    return rf"""
$ErrorActionPreference = 'Continue'
$hosts = "$env:SystemRoot\System32\drivers\etc\hosts"
$mark = '# alupc-portal'
$ip = '{ip}'
$flag = '{flag}'
$closed = ${str(bool(closed)).lower()}
$alias = (Get-NetIPAddress -IPAddress $ip -ErrorAction SilentlyContinue | Select-Object -First 1).InterfaceAlias
function Clean {{
  try {{
    $keep = @(Get-Content -LiteralPath $hosts -ErrorAction Stop | Where-Object {{ $_ -notlike "*$mark*" }})
    Set-Content -LiteralPath $hosts -Value $keep -Encoding ASCII
  }} catch {{}}
  netsh interface portproxy delete v4tov4 listenport=80 listenaddress=$ip | Out-Null
  netsh advfirewall firewall delete rule name=AluPC-Portal | Out-Null
  if ($alias) {{ Set-NetIPInterface -InterfaceAlias $alias -AddressFamily IPv4 -Forwarding Enabled -ErrorAction SilentlyContinue }}
  ipconfig /flushdns | Out-Null
}}
try {{
  Clean
  $names = @({names})
  if ($names.Count -gt 0) {{ Add-Content -LiteralPath $hosts -Value ($names | ForEach-Object {{ "$ip $_ $mark" }}) -Encoding ASCII }}
  netsh interface portproxy add v4tov4 listenport=80 listenaddress=$ip connectport={int(port)} connectaddress=$ip | Out-Null
  netsh advfirewall firewall add rule name=AluPC-Portal dir=in action=allow protocol=TCP localport="80,53,{int(port)}" | Out-Null
  netsh advfirewall firewall add rule name=AluPC-Portal dir=in action=allow protocol=UDP localport=53 | Out-Null
  if ($closed -and $alias) {{ Set-NetIPInterface -InterfaceAlias $alias -AddressFamily IPv4 -Forwarding Disabled -ErrorAction SilentlyContinue }}
  ipconfig /flushdns | Out-Null
  Start-Sleep -Milliseconds 800
  # Port 80 schon von einem anderen Dienst belegt (z. B. IIS/http.sys)? Dann kommt die Prüfung nie bei AluPC an.
  $helper = (Get-CimInstance Win32_Service -Filter "Name='iphlpsvc'").ProcessId
  $other = @(Get-NetTCPConnection -LocalPort 80 -State Listen -ErrorAction SilentlyContinue |
    Where-Object {{ $_.LocalAddress -in @($ip, '0.0.0.0', '::') -and $_.OwningProcess -ne $helper }})
  if ($other.Count -gt 0) {{
    $name = (Get-Process -Id $other[0].OwningProcess -ErrorAction SilentlyContinue).ProcessName
    Set-Content -LiteralPath "$flag.ok" -Value ('belegt:' + $name)
    return
  }}
  Set-Content -LiteralPath "$flag.ok" -Value 'ok'
  while ((Test-Path -LiteralPath $flag) -and (Get-Process -Id {int(pid)} -ErrorAction SilentlyContinue)) {{
    # Internet nur, wenn am PC mindestens ein Gerät freigeschaltet ist (<Flagge>.internet); die anderen Geräte
    # bekommen von AluPCs DNS weiter nur die Anmeldeseite. Der Hotspot schaltet Forwarding evtl. selbst an →
    # alle 2 s wieder auf Soll stellen.
    if ($closed -and $alias) {{
      $allow = ''
      try {{ $allow = ([string](Get-Content -LiteralPath "$flag.internet" -Raw -ErrorAction Stop)).Trim() }} catch {{}}
      $want = if ($allow) {{ 'Enabled' }} else {{ 'Disabled' }}
      Set-NetIPInterface -InterfaceAlias $alias -AddressFamily IPv4 -Forwarding $want -ErrorAction SilentlyContinue
    }}
    Start-Sleep 2
  }}
}} finally {{ Clean }}
"""


def _wait_ready(flag: Path, proc=None, timeout: float = 120, sleep=None) -> str:
    """Bis der Wächter „bereit“ meldet (Passwort/„Ja“ eingegeben) – oder abgebrochen wurde.
    Rückgabe: „ok“, „belegt:<Programm>“ (Windows: Port 80 schon belegt) oder leer."""
    import time

    ok = Path(f"{flag}.ok")
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if ok.exists():
            try:
                text = ok.read_text(encoding="utf-8", errors="replace").strip().lstrip("\ufeff") or "ok"
            except OSError:
                (sleep or time.sleep)(0.2)
                continue
            ok.unlink(missing_ok=True)
            return text
        if proc is not None and proc.poll() is not None and not ok.exists():
            return ""  # Passwort-Abfrage abgebrochen / Fehler
        (sleep or time.sleep)(0.3)
    return ""


def internet_file() -> Path:
    """Liste der Geräte-Adressen mit Internet (eine pro Zeile) – liest das Root-/Administrator-Skript."""
    return Path(f"{portal_flag()}.internet")


def set_internet(ips) -> None:
    """Diese Geräte im AluPC-WLAN dürfen ins Internet (alle anderen nicht). Wirkt in ≤ 2 s."""
    import ipaddress

    clean = sorted({str(ipaddress.IPv4Address(ip)) for ip in ips if ip})
    if _dns is not None:
        _dns.allowed = set(clean)
    path = internet_file()
    text = "\n".join(clean) + ("\n" if clean else "")
    try:
        if not path.exists() or path.read_text(encoding="utf-8") != text:
            path.write_text(text, encoding="utf-8")
    except OSError:
        pass


NAMES: dict[str, str] = {}  # IP → Name, den das Gerät auf der Anmeldeseite eingegeben hat


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
        for m in re.finditer(r"(\d+\.\d+\.\d+\.\d+)\s+([0-9a-fA-F]{2}(?:-[0-9a-fA-F]{2}){5})\s+dynamic", text):
            out[m.group(1)] = m.group(2).replace("-", ":").lower()
    if net is not None:
        out = {k: v for k, v in out.items() if ipaddress.ip_address(k) in net and k != (ip or hotspot.ip)}
    return out


_dns = None  # laufender Anmeldeseiten-DNS


def start_dns(ip_provider, closed: bool = True, host: str = "0.0.0.0", port: int = DNS_PORT,
              check_hosts: list[str] | None = None) -> bool:
    global _dns
    from .portal_dns import PortalDNS

    stop_dns()
    internet_file().unlink(missing_ok=True)  # neuer Start: noch niemand hat Internet (AluPC setzt es gleich)
    hosts = PORTAL_HOSTS + WINDOWS_CHECK_HOSTS if check_hosts is None else check_hosts
    _dns = PortalDNS(ip_provider, closed=closed, hosts=hosts, port=port, host=host, exclusive=IS_WINDOWS)
    if not _dns.start():
        _dns = None
        return False
    return True


def dns_selftest(ip: str, port: int = 53, timeout: float = 2.0) -> bool:
    """Kommt eine Namensfrage an ip:port wirklich bei AluPCs DNS an (und nicht beim DNS des Windows-Hotspots)?"""
    import socket
    import struct

    if _dns is None:
        return False
    before = _dns.queries
    query = struct.pack(">HHHHHH", 0x4155, 0x0100, 1, 0, 0, 0) + b"\x10alupc-selbsttest\x07invalid\x00\x00\x01\x00\x01"
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(timeout)
            sock.sendto(query, (ip, port))
            sock.recvfrom(1500)
    except OSError:
        return False
    return _dns.queries > before


def stop_dns() -> None:
    global _dns
    if _dns is not None:
        _dns.stop()
        _dns = None


def start_portal(dev: str = "", port: int = PORTAL_PORT, spawn=None, wait=_wait_ready,
                 ip: str = WINDOWS_IP, closed: bool = True) -> tuple[bool, str]:
    """Anmeldeseite einschalten (Linux: vor dem Hotspot-Start, Windows: danach). Fragt einmal nach dem
    Passwort (Linux, pkexec) bzw. „Ja“ (Windows, Administrator)."""
    flag = portal_flag()
    Path(f"{flag}.ok").unlink(missing_ok=True)
    if IS_WINDOWS:
        import base64

        # Eigener DNS auf der Hotspot-Adresse (Port 53): wie unter Linux. Unter Windows normal: Zieladresse genauer
        # als der Hotspot-DNS (0.0.0.0) → alle Fragen der Handys kommen bei AluPC an. Geprüft per Selbsttest.
        dns_ok = start_dns(lambda: hotspot.ip or ip, closed, host=ip, port=53,
                           check_hosts=PORTAL_HOSTS + WINDOWS_CHECK_HOSTS) and dns_selftest(ip)
        if not dns_ok:
            stop_dns()
        script = portal_script_windows(ip, port, flag, os.getpid(), closed=closed and dns_ok, hosts=not dns_ok)
        enc = base64.b64encode(script.encode("utf-16-le")).decode()
        launcher = ("try { Start-Process powershell -Verb RunAs -WindowStyle Hidden -ErrorAction Stop -ArgumentList "
                    f"'-NoProfile','-ExecutionPolicy','Bypass','-EncodedCommand','{enc}' }} catch {{ exit 1 }}")
        flag.write_text("an")
        code, out = (spawn or _ps)(launcher)
        if code != 0:
            flag.unlink(missing_ok=True)
            stop_dns()
            return False, "Anmeldeseite aus („Ja“ nicht bestätigt) – Handys nehmen den QR-Code."
        state = wait(flag, None, 60)
        if state is True:
            state = "ok"
        if not state or str(state).startswith("belegt"):
            flag.unlink(missing_ok=True)
            stop_dns()
            if str(state).startswith("belegt"):
                who = str(state).partition(":")[2] or "ein anderes Programm"
                return False, (f"Anmeldeseite aus: Port 80 ist schon belegt ({who}, z. B. ein Webserver) – "
                               "Handys nehmen den QR-Code.")
            return False, "Anmeldeseite ging nicht – Handys nehmen den QR-Code."
        if not dns_ok:
            return True, "Anmeldeseite an (eingeschränkt: Port 53 belegt – nur die Prüf-Adressen zeigen auf den PC)."
        return True, "Anmeldeseite an: Handys öffnen die Spielsteuerung beim Verbinden selbst."
    if not (shutil.which("pkexec") and shutil.which("iptables")):
        return False, "Anmeldeseite braucht pkexec und iptables."
    if not start_dns(lambda: hotspot.ip or _linux_ip(dev), closed):
        return False, f"Anmeldeseite ging nicht: Port {DNS_PORT} ist belegt."
    flag.write_text("an")
    cmd = ["pkexec", "sh", "-c", portal_script(dev, port, flag, os.getpid(), closed=closed)]
    try:
        proc = (spawn or subprocess.Popen)(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                           stderr=subprocess.DEVNULL, start_new_session=True)
    except OSError as exc:
        flag.unlink(missing_ok=True)
        return False, f"Anmeldeseite ging nicht: {exc}"
    if not wait(flag, proc, 120):
        flag.unlink(missing_ok=True)  # Wächter (falls doch noch gestartet) räumt dann sofort auf
        stop_dns()
        return False, "Anmeldeseite aus (Passwort nicht eingegeben) – Handys nehmen den QR-Code."
    return True, "Anmeldeseite an: Handys öffnen die Spielsteuerung beim Verbinden selbst."


def stop_portal() -> None:
    try:
        portal_flag().unlink(missing_ok=True)  # der Wächter nimmt alles in ≤ 2 s wieder raus
        internet_file().unlink(missing_ok=True)
        stop_dns()
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
        portal_msg = ""
        self.portal = False
        if sys.platform.startswith("linux"):
            if portal:  # vor dem Start (Passwort-Abfrage zuerst); geschlossen wie ein Hotel-WLAN (Internet je Gerät)
                dev = wifi_device()
                self.portal, portal_msg = start_portal(dev, closed=True) if dev else (False, "")
            ok, msg, ip = _linux_start(ssid, password, kind=kind, hidden=hidden)
            if not ok and self.portal:
                stop_portal()
                self.portal, portal_msg = False, ""
        else:
            password = password if len(password or "") >= 8 else new_password()
            code, out = _ps(_PS_START, {"ALUPC_SSID": ssid, "ALUPC_PW": password})
            ok, msg = windows_message(out)
            if ok and hidden:  # Windows kann den Namen des Mobilen Hotspots nicht verstecken
                msg += " (Unsichtbar geht unter Windows nicht – der Name ist in der WLAN-Liste zu sehen.)"
            hidden = False
            ip = WINDOWS_IP if ok else ""
            if ok and portal:  # nach dem Start (die Adresse 192.168.137.1 gibt es erst dann)
                self.portal, portal_msg = start_portal(ip=ip, closed=True)
        self.running, self.ip, self.message = ok, ip, msg
        self.kind, self.ssid, self.password = (kind, ssid, password) if ok else ("", "", "")
        self.hidden = bool(ok and hidden and not IS_WINDOWS)
        if ok and portal_msg:
            self.message = msg = f"{msg} {portal_msg}"
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
