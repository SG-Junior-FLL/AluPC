"""Experiment 2: echtes „Handy“ (Windows-Container im transparenten Netz am ICS-Adapter)."""
import json, subprocess, sys, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
sys.path.insert(0, ".")
from alupc.portal_dns import PortalDNS

IP = "192.168.137.1"
def ps(cmd, t=300):
    r = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True, timeout=t)
    return (r.stdout + r.stderr).strip()

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(302); self.send_header("Location", f"http://{IP}:8765/anmelden"); self.send_header("Content-Length", "0"); self.end_headers()
    def log_message(self, *a): pass

d = PortalDNS(lambda: IP, closed=True, port=53, host=IP, exclusive=True)
print("DNS start:", d.start(), d.error)
print(ps(f"Stop-Service W3SVC,WAS -Force -EA 0; netsh interface portproxy add v4tov4 listenport=80 listenaddress={IP} connectport=8765 connectaddress={IP}; netsh advfirewall firewall add rule name=exp80 dir=in action=allow protocol=TCP localport=80"))
srv = ThreadingHTTPServer((IP, 8765), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
print(ps("New-NetFirewallRule -DisplayName exp -Direction Inbound -Action Allow -Program '" + sys.executable + "' | Out-Null; 'fw ok'"))

PHONE = r"""
$ErrorActionPreference='Continue'
$ProgressPreference='SilentlyContinue'
$o=[ordered]@{}
$o.ip=(Get-NetIPAddress -AddressFamily IPv4 | ? IPAddress -ne '127.0.0.1' | % IPAddress) -join ','
$o.dnsserver=(Get-DnsClientServerAddress -AddressFamily IPv4 | % ServerAddresses) -join ','
$o.gw=(Get-NetRoute -DestinationPrefix 0.0.0.0/0 -EA 0 | % NextHop) -join ','
try { $o.dns_check=(Resolve-DnsName connectivitycheck.gstatic.com -Type A -DnsOnly -QuickTimeout -EA Stop | ? Type -eq 'A' | % IPAddress) -join ',' } catch { $o.dns_check='ERR '+$_ }
try { $o.dns_any=(Resolve-DnsName www.beispiel-irgendwas.de -Type A -DnsOnly -QuickTimeout -EA Stop | ? Type -eq 'A' | % IPAddress) -join ',' } catch { $o.dns_any='ERR '+$_ }
try { $o.dns_8888=(Resolve-DnsName example.org -Server 8.8.8.8 -Type A -DnsOnly -QuickTimeout -EA Stop | ? Type -eq 'A' | % IPAddress) -join ',' } catch { $o.dns_8888='ERR '+$_.Exception.Message }
try { $r=Invoke-WebRequest http://connectivitycheck.gstatic.com/generate_204 -MaximumRedirection 0 -UseBasicParsing -TimeoutSec 8 -EA Stop; $o.android=''+$r.StatusCode } catch { $o.android='' + $_.Exception.Response.StatusCode.value__ + ' ' + $_.Exception.Response.Headers['Location'] + ' ' + $_.Exception.Message }
try { $r=Invoke-WebRequest http://93.184.216.34/ -MaximumRedirection 0 -UseBasicParsing -TimeoutSec 8 -EA Stop; $o.raw_ip=''+$r.StatusCode } catch { $o.raw_ip='' + $_.Exception.Response.StatusCode.value__ + ' ' + $_.Exception.Message }
$o.tcp_1111_443=(Test-NetConnection 1.1.1.1 -Port 443 -WarningAction SilentlyContinue).TcpTestSucceeded
'JSON:' + ($o | ConvertTo-Json -Compress)
'IPCONFIG:' + ((ipconfig /all) -join ' ; ')
"""
import base64
enc = base64.b64encode(PHONE.encode("utf-16-le")).decode()
img = sys.argv[1]
def phone(label):
    out = ps(f"docker run --rm --network tnet {img} powershell -NoProfile -EncodedCommand {enc}", 600)
    lines = [l for l in out.splitlines() if l.startswith(("JSON:", "IPCONFIG:"))]
    print(f"== Handy ({label}):", "\n".join(lines) or out[-800:], "| AluPC-DNS-Anfragen:", d.queries)

phone("Weiterleitung an")
iface = ps(f"(Get-NetIPAddress -IPAddress {IP}).InterfaceAlias")
print("Hotspot-Schnittstelle:", iface)
print(ps(f"Set-NetIPInterface -InterfaceAlias '{iface}' -Forwarding Disabled; Get-NetIPInterface -InterfaceAlias '{iface}' -AddressFamily IPv4 | % Forwarding"))
phone("Weiterleitung aus")
print("Forwarding danach:", ps(f"Get-NetIPInterface -InterfaceAlias '{iface}' -AddressFamily IPv4 | % Forwarding"))
print("ICS-Dienst:", ps("(Get-Service SharedAccess).Status"))
