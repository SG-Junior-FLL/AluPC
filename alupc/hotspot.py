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
Z=''
UFW=''
note() {{ if [ -s "$F.fixed" ]; then printf ', %s' "$1" >> "$F.fixed"; else printf '%s' "$1" > "$F.fixed"; fi; }}
fw_open() {{  # Firewall des Systems für den Hotspot öffnen – nur bis zum Ende (Laufzeit-Regeln)
  if command -v firewall-cmd >/dev/null 2>&1 && firewall-cmd --state >/dev/null 2>&1; then
    Z=$(firewall-cmd --get-zone-of-interface={d} 2>/dev/null)
    if [ "$Z" != trusted ]; then
      firewall-cmd --zone=trusted --change-interface={d} >/dev/null 2>&1 && note "firewalld: Hotspot vertraut"
    fi
  fi
  if command -v ufw >/dev/null 2>&1 && grep -qi '^ENABLED=yes' /etc/ufw/ufw.conf 2>/dev/null; then
    ufw insert 1 allow in on {d} >/dev/null 2>&1 && UFW=1 && note "ufw: Hotspot erlaubt"
    ufw route insert 1 allow in on {d} >/dev/null 2>&1
  fi
}}
fw_close() {{
  if [ -n "$UFW" ]; then ufw delete allow in on {d} >/dev/null 2>&1; ufw route delete allow in on {d} >/dev/null 2>&1; fi
  if command -v firewall-cmd >/dev/null 2>&1 && firewall-cmd --state >/dev/null 2>&1; then
    if [ -n "$Z" ] && [ "$Z" != trusted ]; then firewall-cmd --zone="$Z" --change-interface={d} >/dev/null 2>&1
    elif [ -z "$Z" ]; then firewall-cmd --zone=trusted --remove-interface={d} >/dev/null 2>&1; fi
  fi
}}
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
  {final} &&
  if [ -s "$F.internet" ] || [ "{"1" if closed else ""}" = "" ]; then echo Enabled > "$F.fwd"; else echo Disabled > "$F.fwd"; fi
}}
cleanup
iptables -t nat -N alupc-nat && iptables -N alupc-fwd && build && {" && ".join("iptables " + j for j in jumps)} || {{ cleanup; exit 1; }}
{f"command -v ip6tables >/dev/null && ip6tables {ip6}" if closed else "true"}
fw_open
echo ok > "$F.ok"
last=$(cat "$F.internet" 2>/dev/null)
while [ -e "$F" ] && kill -0 {int(pid)} 2>/dev/null; do
  sleep 2
  cur=$(cat "$F.internet" 2>/dev/null)
  if [ "$cur" != "$last" ]; then build; last=$cur; fi
done
fw_close
cleanup
rm -f "$F.fixed" "$F.fwd"
"""


def portal_script_windows(ip: str, port: int, flag: Path, pid: int, closed: bool = True,
                          program: str = "") -> str:
    """Administrator-Skript (Windows) – wie unter Linux ein Hotel-WLAN:
    * Port 53: Den will auch der DNS des Windows-Hotspots (Dienst „SharedAccess“, lauscht auf 0.0.0.0) – AluPC
      nimmt genau die Hotspot-Adresse, das ist genauer und gewinnt (<Flagge>.frei → AluPC → <Flagge>.dns).
      Den Dienst nie anhalten: das beendet den Mobilen Hotspot (WLAN verschwindet).
    * Firewall: Port 53/80 offen; Sperr-Regeln für AluPC selbst (entstehen, wenn die Windows-Frage „Zugriff
      zulassen?“ weggeklickt wurde) entfernen – die gingen sonst vor,
    * Webseiten (Port 80 an den PC) → Anmeldeseite von AluPC (portproxy),
    * geschlossen: Hotspot-Schnittstelle leitet nichts ins Internet weiter (Forwarding aus),
    „bereit“ melden, warten, alles wieder entfernen – auch wenn AluPC abstürzt."""
    prog = str(program).replace("'", "''")
    return rf"""
$ErrorActionPreference = 'Continue'
$ip = '{ip}'
$flag = '{flag}'
$prog = '{prog}'
$closed = ${str(bool(closed)).lower()}
function Alias {{ (Get-NetIPAddress -IPAddress $ip -ErrorAction SilentlyContinue | Select-Object -First 1).InterfaceAlias }}
function Clean {{
  netsh interface portproxy delete v4tov4 listenport=80 listenaddress=$ip | Out-Null
  netsh advfirewall firewall delete rule name=AluPC-Portal | Out-Null
  $a = Alias
  if ($a) {{ Set-NetIPInterface -InterfaceAlias $a -AddressFamily IPv4 -Forwarding Enabled -ErrorAction SilentlyContinue }}
}}
function Owner53 {{  # wer hält Port 53 (für die Meldung, falls AluPC ihn nicht bekommt)
  $e = @(Get-NetUDPEndpoint -LocalPort 53 -ErrorAction SilentlyContinue | Where-Object {{ $_.LocalAddress -in @('0.0.0.0', $ip) }})
  if ($e.Count -eq 0) {{ return 'frei' }}
  $p = $e[0].OwningProcess
  $n = (Get-Process -Id $p -ErrorAction SilentlyContinue).ProcessName
  $svc = @(Get-CimInstance Win32_Service -Filter "ProcessId=$p" -ErrorAction SilentlyContinue | ForEach-Object {{ $_.Name }}) -join ','
  "belegt:$($e[0].LocalAddress) $n $svc".Trim()
}}
function Unblock {{  # Sperr-Regeln für AluPC (weggeklickte Windows-Frage „Zugriff zulassen?“) gingen vor
  if (-not $prog) {{ return }}
  Get-NetFirewallApplicationFilter -ErrorAction SilentlyContinue | Where-Object {{ $_.Program -ieq $prog }} |
    Get-NetFirewallRule -ErrorAction SilentlyContinue |
    Where-Object {{ $_.Direction -eq 'Inbound' -and $_.Action -eq 'Block' }} | Remove-NetFirewallRule -ErrorAction SilentlyContinue
}}
# Wer sperrt Port 80? Windows schreibt verworfene Pakete/Verbindungen ins Sicherheitsprotokoll (5152/5157), wenn
# die Überwachung dafür an ist. Vorher-Zustand und vorübergehend ausgeschaltete Sperren liegen in ProgramData
# (bleiben liegen, falls der PC abstürzt → beim nächsten Start zurückgestellt).
$store = Join-Path $env:ProgramData 'AluPC'
$auditBak = Join-Path $store 'audit-vorher.csv'
$undoFile = Join-Path $store 'firewall-zurueck.txt'
$since = Get-Date
$seen = @{{}}
$fnames = @{{}}
$prof = 'Public'
$fixed = New-Object System.Collections.ArrayList  # was AluPC automatisch freigemacht hat (zeigt das Hotspot-Fenster)
function Restore {{  # vorübergehend ausgeschaltete Sperren wieder an
  if (-not (Test-Path -LiteralPath $undoFile)) {{ return }}
  foreach ($line in @(Get-Content -LiteralPath $undoFile -ErrorAction SilentlyContinue)) {{
    $k, $v = ([string]$line).Split('|', 2)
    if ($k -eq 'regel' -and $v) {{ Enable-NetFirewallRule -Name $v -ErrorAction SilentlyContinue }}
    if ($k -eq 'profil' -and $v) {{ Set-NetFirewallProfile -Name $v -AllowInboundRules False -ErrorAction SilentlyContinue }}
    if ($k -eq 'dienst' -and $v) {{ Start-Service -Name $v -ErrorAction SilentlyContinue }}
  }}
  Remove-Item -LiteralPath $undoFile -ErrorAction SilentlyContinue
}}
function FilterName($id) {{  # Name der Windows-Filterregel (= Name der Firewall-Regel) zu einer Filter-Nummer
  if ($fnames.ContainsKey($id)) {{ return $fnames[$id] }}
  $name = ''
  $tmp = Join-Path $store 'wfp.xml'
  try {{
    netsh wfp show filters file=$tmp | Out-Null
    $x = [xml](Get-Content -LiteralPath $tmp -Raw)
    $node = $x.SelectSingleNode("//*[filterId='$id']")
    if ($node) {{ $name = [string]$node.displayData.name }}
  }} catch {{}}
  Remove-Item -LiteralPath $tmp -ErrorAction SilentlyContinue
  $fnames[$id] = $name
  $name
}}
function Drops {{  # verworfene Handy-Anfragen an Port 80 → <Flagge>.drop (Zeit|Gerät|Port|Ereignis|Art|Filter)
  $xp = "*[System[(EventID=5152 or EventID=5157) and TimeCreated[timediff(@SystemTime) <= 30000]]] and " +
        "*[EventData[Data[@Name='DestPort']='80' or Data[@Name='SourcePort']='80']]"
  $ev = @(Get-WinEvent -LogName Security -FilterXPath $xp -MaxEvents 100 -ErrorAction SilentlyContinue)
  $out = @()
  foreach ($e in $ev) {{
    if ($seen.ContainsKey($e.RecordId) -or $e.TimeCreated -lt $since) {{ continue }}
    $seen[$e.RecordId] = 1
    $d = @{{}}
    foreach ($x in ([xml]$e.ToXml()).Event.EventData.Data) {{ $d[[string]$x.Name] = [string]$x.'#text' }}
    if ($d['SourceAddress'] -eq $ip) {{ $remote = $d['DestAddress']; $lp = $d['SourcePort'] }}
    elseif ($d['DestAddress'] -eq $ip) {{ $remote = $d['SourceAddress']; $lp = $d['DestPort'] }}
    else {{ continue }}
    if ($lp -ne '80') {{ continue }}
    $name = FilterName $d['FilterRTID']
    $kind = 'fremd'
    if ($name -and @(Get-NetFirewallRule -DisplayName $name -ErrorAction SilentlyContinue |
        Where-Object {{ [string]$_.Direction -eq 'Inbound' -and [string]$_.Action -eq 'Block' }}).Count) {{ $kind = 'regel' }}
    $t = [DateTimeOffset]::new($e.TimeCreated).ToUnixTimeSeconds()
    $out += "$t|$remote|$lp|$($e.Id)|$kind|$($name -replace '\|', '/')"
  }}
  if ($out.Count) {{
    $old = @(Get-Content -LiteralPath "$flag.drop" -ErrorAction SilentlyContinue)
    Set-Content -LiteralPath "$flag.drop" -Encoding UTF8 -Value (@($old) + $out | Select-Object -Last 20)
  }}
  @($out | Where-Object {{ ([string]$_).Split('|')[4] -eq 'regel' }}).Count
}}
function Note($text) {{
  [void]$fixed.Add($text)
  Set-Content -LiteralPath "$flag.fixed" -Encoding UTF8 -Value ($fixed -join ', ')
}}
function FixNow {{  # Firewall-Sperren gegen Handys automatisch ausschalten – nur bis der Hotspot endet
  New-Item -ItemType Directory -Force -Path $store | Out-Null
  $names = @(Get-Content -LiteralPath "$flag.drop" -ErrorAction SilentlyContinue | ForEach-Object {{
    $p = ([string]$_).Split('|'); if ($p.Count -ge 6 -and $p[4] -eq 'regel') {{ $p[5] }} }}) | Select-Object -Unique
  foreach ($n in $names) {{
    Get-NetFirewallRule -DisplayName $n -ErrorAction SilentlyContinue |
      Where-Object {{ [string]$_.Enabled -eq 'True' -and [string]$_.Direction -eq 'Inbound' -and [string]$_.Action -eq 'Block' }} |
      ForEach-Object {{
        Add-Content -LiteralPath $undoFile -Value "regel|$($_.Name)"
        Disable-NetFirewallRule -Name $_.Name -ErrorAction SilentlyContinue
        Note "Sperr-Regel '$n' aus"
      }}
  }}
  $fp = Get-NetFirewallProfile -Name $prof -ErrorAction SilentlyContinue
  if ([string]$fp.AllowInboundRules -eq 'False') {{
    Add-Content -LiteralPath $undoFile -Value "profil|$prof"
    Set-NetFirewallProfile -Name $prof -AllowInboundRules True -ErrorAction SilentlyContinue
    Note "'Alle eingehenden blockieren' ($prof) aus"
  }}
}}
function Free80 {{  # Port 80 hält ein anderer Dienst (z. B. IIS über http.sys) → bis zum Ende anhalten
  $helper = (Get-CimInstance Win32_Service -Filter "Name='iphlpsvc'").ProcessId
  $busy = @(Get-NetTCPConnection -LocalPort 80 -State Listen -ErrorAction SilentlyContinue |
    Where-Object {{ $_.LocalAddress -in @($ip, '0.0.0.0', '::') -and $_.OwningProcess -notin @($helper, {int(pid)}) }})
  foreach ($c in $busy) {{
    $procId = [int]$c.OwningProcess
    $names = if ($procId -eq 4) {{ @('W3SVC', 'WAS', 'WMSVC') }}
             else {{ @(Get-CimInstance Win32_Service -Filter "ProcessId=$procId" -ErrorAction SilentlyContinue | ForEach-Object Name) }}
    if ($names.Count -eq 0 -or $names.Count -gt 3) {{ continue }}  # Sammelprozess vieler Windows-Dienste – nicht anfassen
    $keep = @('SharedAccess', 'iphlpsvc', 'Dnscache', 'BFE', 'mpssvc', 'nsi', 'Tcpip', 'RpcSs', 'LanmanServer')
    foreach ($svc in @(Get-Service -Name $names -ErrorAction SilentlyContinue |
        Where-Object {{ [string]$_.Status -eq 'Running' -and $_.Name -notin $keep }})) {{
      Add-Content -LiteralPath $undoFile -Value "dienst|$($svc.Name)"
      Stop-Service -Name $svc.Name -Force -ErrorAction SilentlyContinue
      Note "Dienst '$($svc.Name)' angehalten (hielt Port 80)"
    }}
  }}
}}
function WaitFile($path, $seconds) {{
  $end = (Get-Date).AddSeconds($seconds)
  while (-not (Test-Path -LiteralPath $path) -and (Get-Date) -lt $end) {{ Start-Sleep -Milliseconds 200 }}
  Test-Path -LiteralPath $path
}}
$n = 0
Set-Content -LiteralPath "$flag.laeuft" -Value 'an'
try {{
  Restore  # Reste eines abgestürzten Laufs
  Clean
  netsh advfirewall firewall add rule name=AluPC-Portal dir=in action=allow protocol=TCP localport="80,443,53,{int(port)}" | Out-Null
  netsh advfirewall firewall add rule name=AluPC-Portal dir=in action=allow protocol=UDP localport=53 | Out-Null
  Unblock
  if ($prog) {{ netsh advfirewall firewall add rule name=AluPC-Portal dir=in action=allow program="$prog" enable=yes | Out-Null }}
  # portproxy (Port 80 → AluPC) braucht den Dienst „IP-Hilfsdienst“
  Set-Service iphlpsvc -StartupType Automatic -ErrorAction SilentlyContinue
  Start-Service iphlpsvc -ErrorAction SilentlyContinue
  # Port 53: AluPC nimmt genau die Hotspot-Adresse (genauer als der Windows-DNS auf 0.0.0.0). Den Windows-Dienst
  # NICHT anhalten – das beendet den Mobilen Hotspot.
  try {{ New-Item -ItemType Directory -Force -Path $store | Out-Null; Free80 }} catch {{}}
  Set-Content -LiteralPath "$flag.frei" -Value (Owner53)
  $null = WaitFile "$flag.dns" 30
  Remove-Item -LiteralPath "$flag.dns" -ErrorAction SilentlyContinue
  Set-Content -LiteralPath "$flag.bereit" -Value 'bereit'
  # Port 80: AluPC lauscht dort meist selbst (dann sieht es, welches Handy prüft) – sonst Weiterleitung (portproxy)
  $mine = @(Get-NetTCPConnection -LocalPort 80 -State Listen -ErrorAction SilentlyContinue |
    Where-Object {{ $_.LocalAddress -eq $ip -and $_.OwningProcess -eq {int(pid)} }})
  if ($mine.Count -eq 0) {{
    netsh interface portproxy add v4tov4 listenport=80 listenaddress=$ip connectport={int(port)} connectaddress=$ip | Out-Null
  }}
  $a = Alias
  if ($closed -and $a) {{ Set-NetIPInterface -InterfaceAlias $a -AddressFamily IPv4 -Forwarding Disabled -ErrorAction SilentlyContinue }}
  ipconfig /flushdns | Out-Null
  Start-Sleep -Milliseconds 800
  # Port 80 schon von einem anderen Dienst belegt (z. B. IIS/http.sys)? Dann kommt die Prüfung nie bei AluPC an.
  $helper = (Get-CimInstance Win32_Service -Filter "Name='iphlpsvc'").ProcessId
  $other = @(Get-NetTCPConnection -LocalPort 80 -State Listen -ErrorAction SilentlyContinue |
    Where-Object {{ $_.LocalAddress -in @($ip, '0.0.0.0', '::') -and $_.OwningProcess -notin @($helper, {int(pid)}) }})
  if ($other.Count -gt 0) {{
    $name = (Get-Process -Id $other[0].OwningProcess -ErrorAction SilentlyContinue).ProcessName
    Set-Content -LiteralPath "$flag.ok" -Value ('belegt:' + $name)
    return
  }}
  # Was könnte Handys blockieren? (für das Hotspot-Fenster): Netzprofil, „alle eingehenden blockieren“, fremde Firewall
  try {{
    $a = Alias
    $cat = if ($a) {{ [string](Get-NetConnectionProfile -InterfaceAlias $a -ErrorAction SilentlyContinue).NetworkCategory }} else {{ '' }}
    $prof = if ($cat -eq 'DomainAuthenticated') {{ 'Domain' }} elseif ($cat) {{ $cat }} else {{ 'Public' }}
    $fp = Get-NetFirewallProfile -Name $prof -ErrorAction SilentlyContinue
    $third = @(Get-CimInstance -Namespace root/SecurityCenter2 -ClassName FirewallProduct -ErrorAction SilentlyContinue |
      ForEach-Object {{ $_.displayName }}) -join ', '
    Set-Content -LiteralPath "$flag.fw" -Value ("profil=$prof;an=$($fp.Enabled);erlaubte=$($fp.AllowInboundRules);fremd=$third")
  }} catch {{}}
  try {{  # Firewall-Überwachung an (nur „verworfen“), damit AluPC sieht, wer Handys an Port 80 abweist
    New-Item -ItemType Directory -Force -Path $store | Out-Null
    if (-not (Test-Path -LiteralPath $auditBak)) {{ auditpol /backup /file:$auditBak | Out-Null }}
    auditpol /set /subcategory:'{{0CCE9225-69AE-11D9-BED3-505054503030}}' /failure:enable | Out-Null
    auditpol /set /subcategory:'{{0CCE9226-69AE-11D9-BED3-505054503030}}' /failure:enable | Out-Null
    if ($LASTEXITCODE -eq 0) {{ Set-Content -LiteralPath "$flag.audit" -Value 'an' }}
  }} catch {{}}
  try {{ FixNow }} catch {{}}  # „Alle eingehenden blockieren“ gleich zu Beginn aus (bis zum Ende)
  $since = Get-Date
  Set-Content -LiteralPath "$flag.ok" -Value ($(if (Alias) {{ 'ok' }} else {{ 'ok:ohne-adresse' }}))
  while ((Test-Path -LiteralPath $flag) -and (Get-Process -Id {int(pid)} -ErrorAction SilentlyContinue)) {{
    # Internet nur, wenn am PC mindestens ein Gerät freigeschaltet ist (<Flagge>.internet); die anderen Geräte
    # bekommen von AluPCs DNS weiter nur die Anmeldeseite. Der Hotspot schaltet Forwarding evtl. selbst an →
    # alle 2 s wieder auf Soll stellen.
    $n++
    if ($n % 10 -eq 0) {{ Unblock }}  # Windows-Frage später doch weggeklickt → Sperre wieder weg
    try {{ if ((Drops) -gt 0) {{ FixNow }} }} catch {{}}  # Sperr-Regel hat ein Handy abgewiesen → gleich aus
    $a = Alias
    if ($closed -and $a) {{
      $allow = ''
      try {{ $allow = ([string](Get-Content -LiteralPath "$flag.internet" -Raw -ErrorAction Stop)).Trim() }} catch {{}}
      $want = if ($allow) {{ 'Enabled' }} else {{ 'Disabled' }}
      $now = [string](Get-NetIPInterface -InterfaceAlias $a -AddressFamily IPv4 -ErrorAction SilentlyContinue).Forwarding
      if ($now -ne $want) {{  # nur ändern, wenn nötig (jedes Setzen meldet Windows als Netzwerkänderung)
        Set-NetIPInterface -InterfaceAlias $a -AddressFamily IPv4 -Forwarding $want -ErrorAction SilentlyContinue
      }}
    }}
    if ($a) {{  # wirklichen Zustand melden (zeigt AluPC im Hotspot-Fenster)
      $f = (Get-NetIPInterface -InterfaceAlias $a -AddressFamily IPv4 -ErrorAction SilentlyContinue).Forwarding
      Set-Content -LiteralPath "$flag.fwd" -Value ([string]$f) -ErrorAction SilentlyContinue
    }}
    Start-Sleep 2
  }}
}} finally {{
  Clean
  Restore
  if (Test-Path -LiteralPath $auditBak) {{
    auditpol /restore /file:$auditBak | Out-Null
    Remove-Item -LiteralPath $auditBak -ErrorAction SilentlyContinue
  }}
  Remove-Item -LiteralPath "$flag.frei","$flag.bereit","$flag.dns","$flag.fwd","$flag.fw","$flag.laeuft","$flag.drop",
    "$flag.fixed","$flag.audit" -ErrorAction SilentlyContinue
}}
"""


def _wait_file(path: Path, timeout: float) -> bool:
    import time

    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if path.exists():
            return True
        time.sleep(0.2)
    return False


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
        # Sprache egal („dynamic“/„dynamisch“): Broadcast und Multicast fallen unten weg
        for m in re.finditer(r"(\d+\.\d+\.\d+\.\d+)\s+([0-9a-fA-F]{2}(?:-[0-9a-fA-F]{2}){5})\b", text):
            mac = m.group(2).replace("-", ":").lower()
            if mac != "ff:ff:ff:ff:ff:ff" and not int(mac[:2], 16) & 1:
                out[m.group(1)] = mac
    if net is not None:
        out = {k: v for k, v in out.items() if ipaddress.ip_address(k) in net and k != (ip or hotspot.ip)}
    return out


_dns = None  # laufender Anmeldeseiten-DNS
DNS_INFO = ""  # Windows: wer Port 53 hatte, wo AluPC lauscht (für Meldungen/Diagnose)


def start_dns(ip_provider, closed: bool = True, host: str = "0.0.0.0", port: int = DNS_PORT,
              check_hosts: list[str] | None = None, restrict: bool = False, exclusive: bool | None = None) -> bool:
    global _dns
    from .portal_dns import PortalDNS

    stop_dns()
    internet_file().unlink(missing_ok=True)  # neuer Start: noch niemand hat Internet (AluPC setzt es gleich)
    hosts = PORTAL_HOSTS + WINDOWS_CHECK_HOSTS if check_hosts is None else check_hosts
    _dns = PortalDNS(ip_provider, closed=closed, hosts=hosts, port=port, host=host,
                     exclusive=IS_WINDOWS if exclusive is None else exclusive, restrict=restrict)
    if not _dns.start():
        _dns = None
        return False
    return True


PROBES: dict[str, float] = {}  # Gerät → Zeitpunkt, an dem seine „Bin ich im Internet?“-Prüfung bei AluPC ankam


HTTP_LOG: list[tuple[float, str, str, str, str]] = []  # (Zeit, Gerät, Methode, Host, Pfad) – letzte 40


def note_http(ip: str, method: str, host: str, path: str) -> None:
    import time

    HTTP_LOG.append((time.time(), ip, method, host.split(":")[0][:60], path[:60]))
    del HTTP_LOG[:-40]


def firewall_info() -> dict:
    """Windows: Firewall am Hotspot laut Wächter – {profil, an, erlaubte, fremd} (leer, wenn unbekannt)."""
    try:
        text = Path(f"{portal_flag()}.fw").read_text(encoding="utf-8", errors="replace").strip().lstrip("\ufeff")
    except OSError:
        return {}
    return dict(part.split("=", 1) for part in text.split(";") if "=" in part)


def _flag_text(suffix: str) -> str:
    try:
        return Path(f"{portal_flag()}{suffix}").read_text(encoding="utf-8", errors="replace").replace("\ufeff", "").strip()
    except OSError:
        return ""


def drop_info(ip: str = "", max_age: float = 600) -> list[dict]:
    """Windows: von der Firewall verworfene Anfragen an Port 80 (laut Wächter, Sicherheitsprotokoll 5152/5157) –
    neueste zuletzt; {t, ip, port, kind ("regel" = Windows-Firewall-Regel, sonst "fremd"), name}."""
    import time

    out = []
    for line in _flag_text(".drop").splitlines():
        parts = line.strip().split("|", 5)
        if len(parts) < 6 or not parts[0].isdigit():
            continue
        t = int(parts[0])
        if time.time() - t > max_age or (ip and parts[1] != ip):
            continue
        out.append({"t": t, "ip": parts[1], "port": parts[2], "kind": parts[4], "name": parts[5].strip()})
    return out


def audit_active() -> bool:
    """Windows: Wächter sieht Firewall-Sperren (Überwachung an)?"""
    return _flag_text(".audit") == "an"


def fix_result() -> str:
    """Was der Wächter automatisch freigemacht hat (Firewall-Sperren, Dienst auf Port 80) – bis der Hotspot endet."""
    return _flag_text(".fixed")


_SELFTEST = {"t": 0.0, "ms": None, "running": False}


def port80_selftest(ip: str, max_age: float = 10.0, port: int = 80) -> int | None:
    """Ruft die Anmeldeseite vom PC aus auf ip:80 ab (im Hintergrund, höchstens alle 10 s) → Millisekunden oder None.
    Geht das am PC, aber nicht am Handy, blockiert etwas dazwischen (Firewall)."""
    import socket
    import threading
    import time

    def run():
        start = time.monotonic()
        ms = None
        try:
            with socket.create_connection((ip, port), timeout=4) as s:
                s.sendall(b"GET /generate_204 HTTP/1.1\r\nHost: connectivitycheck.gstatic.com\r\nConnection: close\r\n\r\n")
                if s.recv(64).startswith(b"HTTP/1."):
                    ms = int((time.monotonic() - start) * 1000)
        except OSError:
            ms = None
        _SELFTEST.update(ms=ms, t=time.monotonic(), running=False)

    if not _SELFTEST["running"] and time.monotonic() - _SELFTEST["t"] > max_age:
        _SELFTEST["running"] = True
        threading.Thread(target=run, name="alupc-port80-test", daemon=True).start()
    return _SELFTEST["ms"]


def forwarding_state() -> str:
    """Windows: Weiterleitung (= Internet) der Hotspot-Schnittstelle laut Wächter: „Enabled“/„Disabled“/""."""
    try:
        return Path(f"{portal_flag()}.fwd").read_text(encoding="utf-8", errors="replace").strip().lstrip("\ufeff")
    except OSError:
        return ""


def portal_status() -> str:
    """Eine Zeile für das Hotspot-Fenster (Windows und Linux gleich): wohin Port 80 geht, ob die Seite am PC antwortet,
    was automatisch freigemacht wurde, Internet-Sperre, letzte Prüfung eines Handys."""
    import time

    from .cast_server import active_port

    if not (hotspot.running and hotspot.portal):
        return ""
    port = active_port()
    parts = [f"Port 80 → AluPC-Seite (Port {port})" if port else "⚠ AluPCs Webserver läuft nicht"]
    fwd = forwarding_state()
    if fwd:
        parts.append("Internet-Sperre: " + {"Disabled": "aktiv", "Enabled": "aus (Gerät freigeschaltet)"}.get(fwd, fwd))
    # Windows: AluPC lauscht selbst auf Port 80; Linux: Port 80 wird nur für Handys umgeleitet → die Seite selbst prüfen
    ms = port80_selftest(hotspot.ip, port=80 if IS_WINDOWS else (port or PORTAL_PORT))
    parts.append(f"Anmeldeseite am PC: {ms} ms" if ms is not None else "Anmeldeseite am PC: antwortet nicht")
    done = fix_result()
    if done:
        parts.append(f"automatisch freigemacht: {done}")
    fw = firewall_info()
    other = [n.strip() for n in fw.get("fremd", "").split(",") if n.strip() and "defender" not in n.lower()]
    if other:
        parts.append(f"⚠ weitere Firewall: {', '.join(other)} – falls Handys nicht durchkommen, dort AluPC erlauben")
    drops = [d for d in drop_info() if d["kind"] != "regel"]
    if drops:
        d = drops[-1]
        parts.append(f"⛔ gesperrt: {d['ip']} → Port 80 (von „{d['name'] or 'unbekannt'}“, vor {int(time.time() - d['t'])} s)")
    recent = [e for e in HTTP_LOG if time.time() - e[0] < 120 and hotspot.ip not in (e[1], e[3])]  # nicht der PC selbst
    if recent:
        t, ip, method, host, path = recent[-1]
        parts.append(f"letzte Prüfung: {ip} {method} {host}{path} (vor {int(time.time() - t)} s)")
    else:
        parts.append("noch keine Prüfung auf Port 80 angekommen")
    return " · ".join(parts)


def note_probe(ip: str) -> None:
    import time

    PROBES[ip] = time.time()


def asked_names(ip: str) -> list[str]:
    """Namen, die dieses Gerät zuletzt bei AluPC gefragt hat (neueste zuletzt)."""
    return list(_dns.names.get(ip, [])) if _dns is not None else []


CHECK_HOSTS = set(PORTAL_HOSTS) | {"www.google.com", "clients1.google.com", "play.googleapis.com"}


def check_hint(ip: str) -> str:
    """Kurzer Hinweis, warum ein Handy die Anmeldeseite nicht bekommt (aus den gefragten Namen und Firewall-Sperren)."""
    names = asked_names(ip)
    drops = drop_info(ip)
    if drops:
        d = drops[-1]
        if (d["kind"] == "regel" or firewall_info().get("erlaubte") == "False") and fix_result():
            return "Firewall-Sperre automatisch aufgehoben → WLAN am Handy kurz trennen und neu verbinden"
        return f"Firewall „{d['name'] or 'unbekannt'}“ sperrt Port 80 – dort AluPC erlauben"
    if not names:
        return ""
    if any(n in CHECK_HOSTS for n in names):
        if audit_active():
            return ("Handy prüft – aber am PC kam auf Port 80 nichts an und die Firewall hat nichts gesperrt "
                    "→ am Handy mobile Daten aus und neu verbinden; sonst andere Sicherheitssoftware?")
        return "Handy prüft – aber nichts kam auf Port 80 an → am Handy mobile Daten aus und neu verbinden"
    dot = [n for n in names if "dns" in n.split(".")[0] or n.startswith(("dns.", "one.one", "1dot1dot1"))]
    if dot:
        return f"Handy nutzt eigenes DNS ({dot[-1]}) – dort „Privates DNS“ auf Automatisch stellen"
    return "Handy hat die Internet-Prüfung noch nicht gefragt"


def client_status(ip: str) -> tuple[int, bool]:
    """(Namensfragen bei AluPC, Anmelde-Prüfung bei AluPC angekommen) für ein Gerät im WLAN."""
    return (_dns.clients.get(ip, 0) if _dns is not None else 0), ip in PROBES


def _bind53(ip: str, closed: bool, order) -> str:
    for host, excl in order:
        if start_dns(lambda: hotspot.ip or ip, closed, host=host, port=53,
                     check_hosts=PORTAL_HOSTS + WINDOWS_CHECK_HOSTS, restrict=True, exclusive=excl):
            return host + (" exklusiv" if excl else "")
    return ""


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


def encoded_command(script: str) -> str:
    """PowerShell -EncodedCommand für ein langes Skript: gzip-komprimiert und im Zielprozess entpackt – sonst wird die
    Befehlszeile zu lang (Windows: höchstens 32767 Zeichen; das Wächter-Skript allein ergäbe über 36000)."""
    import base64
    import gzip

    packed = base64.b64encode(gzip.compress(script.encode("utf-8"), 9)).decode()
    boot = ("$z = New-Object IO.Compression.GZipStream((New-Object IO.MemoryStream(,[Convert]::FromBase64String("
            f"'{packed}'))), [IO.Compression.CompressionMode]::Decompress)\n"
            "Invoke-Expression (New-Object IO.StreamReader($z, [Text.Encoding]::UTF8)).ReadToEnd()\n")
    return base64.b64encode(boot.encode("utf-16-le")).decode()


def start_portal(dev: str = "", port: int | None = None, spawn=None, wait=_wait_ready,
                 ip: str = WINDOWS_IP, closed: bool = True, wait_file=_wait_file) -> tuple[bool, str]:
    """Anmeldeseite einschalten (Linux: vor dem Hotspot-Start, Windows: danach). Fragt einmal nach Administrator-Rechten.
    Gleich auf beiden Systemen: Port 80 der Handys → AluPCs Webserver (auf welchem Port er auch läuft), Firewall-Sperren
    und ein Dienst auf Port 80 werden bis zum Ende automatisch freigemacht, danach ist alles wie vorher."""
    if port is None:
        from .cast_server import active_port

        port = active_port() or PORTAL_PORT
    flag = portal_flag()
    for suffix in (".ok", ".frei", ".bereit", ".dns", ".fixed", ".fwd", ".drop", ".audit", ".fw"):
        Path(f"{flag}{suffix}").unlink(missing_ok=True)
    if IS_WINDOWS:
        import time

        stop_dns()
        end = time.monotonic() + 15  # voriger Wächter räumt noch auf (gibt Port 53 an Windows zurück) → abwarten
        while Path(f"{flag}.laeuft").exists() and time.monotonic() < end:
            time.sleep(0.3)
        script = portal_script_windows(ip, port, flag, os.getpid(), closed=closed, program=sys.executable)
        enc = encoded_command(script)
        launcher = ("try { Start-Process powershell -Verb RunAs -WindowStyle Hidden -ErrorAction Stop -ArgumentList "
                    f"'-NoProfile','-ExecutionPolicy','Bypass','-EncodedCommand','{enc}' }} catch {{ exit 1 }}")
        flag.write_text("an")
        code, out = (spawn or _ps)(launcher)
        if code != 0:
            flag.unlink(missing_ok=True)
            return False, "Anmeldeseite aus (Administrator-Rechte nicht bestätigt)."

        def fail(text):
            from .cast_server import stop_extra

            flag.unlink(missing_ok=True)  # Wächter räumt auf und gibt Port 53 an Windows zurück
            stop_dns()
            stop_extra()
            return False, text

        if not wait_file(Path(f"{flag}.frei"), 90):
            return fail("Anmeldeseite ging nicht (Administrator-Skript hat nicht geantwortet).")

        def read(suffix):
            try:
                return Path(f"{flag}{suffix}").read_text(encoding="utf-8", errors="replace").strip().lstrip("\ufeff")
            except OSError:
                return ""

        def bind53(order) -> str:
            return _bind53(ip, closed, order)

        global DNS_INFO
        from .cast_server import serve_extra

        http80 = serve_extra(ip, 80)  # Anmeldeseite direkt auf Port 80 (sonst übernimmt das die Weiterleitung)
        from .cast_server import refuse_https

        refuse_https(ip)  # HTTPS (443) sofort ablehnen: Browser/Handy fallen gleich auf HTTP zurück statt lange zu warten
        PROBES.clear()
        HTTP_LOG.clear()
        owner = read(".frei")
        # genau die Hotspot-Adresse, exklusiv – genauer als der Windows-DNS auf 0.0.0.0
        bound = bind53([(ip, True)])
        works = bool(bound) and dns_selftest(ip)
        DNS_INFO = f"Port 53 vorher: {owner or '?'} · AluPC: {bound or 'nicht bekommen'}" + \
            ("" if works or not bound else " (kommt nicht an)") + f" · Port 80: {'AluPC' if http80 else 'Weiterleitung'}"
        Path(f"{flag}.dns").write_text("ok" if bound else "fehler")
        wait_file(Path(f"{flag}.bereit"), 60)
        if not bound:
            who = owner.partition(":")[2] if owner.startswith("belegt:") else ""
            return fail("Anmeldeseite ging nicht: Port 53 auf der Hotspot-Adresse ist belegt"
                        + (f" ({who})." if who else ".") + " WLAN läuft trotzdem.")
        state = wait(flag, None, 90)
        if state is True:
            state = "ok"
        if not state or str(state).startswith("belegt"):
            if str(state).startswith("belegt"):
                who = str(state).partition(":")[2] or "ein anderes Programm"
                return fail(f"Anmeldeseite aus: Port 80 ist schon belegt ({who}, z. B. ein Webserver).")
            return fail("Anmeldeseite ging nicht.")
        if not dns_selftest(ip):
            return fail(f"Anmeldeseite ging nicht: Namensfragen an {ip} kommen nicht bei AluPC an ({DNS_INFO}).")
        return True, "Anmeldeseite an: Handys öffnen sie beim Verbinden selbst."
    if not (shutil.which("pkexec") and shutil.which("iptables")):
        return False, "Anmeldeseite braucht pkexec und iptables."
    # Namensfragen der Handys → AluPCs DNS; ist sein Port belegt, nimmt AluPC den nächsten freien (Umleitung folgt)
    dns_port = next((p for p in range(DNS_PORT, DNS_PORT + 10)
                     if start_dns(lambda: hotspot.ip or _linux_ip(dev), closed, port=p)), 0)
    if not dns_port:
        return False, f"Anmeldeseite ging nicht: Ports {DNS_PORT}–{DNS_PORT + 9} sind alle belegt."
    flag.write_text("an")
    cmd = ["pkexec", "sh", "-c", portal_script(dev, port, flag, os.getpid(), closed=closed, dns_port=dns_port)]
    try:
        proc = (spawn or subprocess.Popen)(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                           stderr=subprocess.DEVNULL, start_new_session=True)
    except OSError as exc:
        flag.unlink(missing_ok=True)
        return False, f"Anmeldeseite ging nicht: {exc}"
    if not wait(flag, proc, 120):
        flag.unlink(missing_ok=True)  # Wächter (falls doch noch gestartet) räumt dann sofort auf
        stop_dns()
        return False, "Anmeldeseite aus (Administrator-Rechte nicht bestätigt)."
    return True, "Anmeldeseite an: Handys öffnen sie beim Verbinden selbst."


def stop_portal() -> None:
    try:
        from .cast_server import stop_extra

        stop_extra()
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
# Energiesparen aus: sonst schaltet Windows den Hotspot ab, wenn kurz kein Gerät verbunden ist (Handy-Display aus)
# – dann wäre auch die Anmeldeseite weg
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
            ok, msg = windows_message(_ps(_PS_START, {"ALUPC_SSID": ssid, "ALUPC_PW": password})[1])
            if ok and portal:  # nach dem Start (die Hotspot-Adresse gibt es erst dann)
                self.portal, portal_msg = start_portal(ip=windows_hotspot_ip(), closed=True)
                if "STATE:Off" in _ps(_PS_STATE)[1]:  # Hotspot inzwischen aus? Dann wieder an (WLAN muss sichtbar sein)
                    ok, msg = windows_message(_ps(_PS_START, {"ALUPC_SSID": ssid, "ALUPC_PW": password})[1])
            if ok and hidden:  # Windows kann den Namen des Mobilen Hotspots nicht verstecken
                msg += " (Unsichtbar geht unter Windows nicht – der Name ist in der WLAN-Liste zu sehen.)"
            hidden = False
            ip = windows_hotspot_ip() if ok else ""
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
