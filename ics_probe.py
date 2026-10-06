"""Experiment: Wer beantwortet DNS an 192.168.137.1:53, wenn Windows-ICS läuft – und kann AluPC das übernehmen?"""
import random, socket, struct, subprocess, sys, time
sys.path.insert(0, ".")
from alupc.portal_dns import PortalDNS

IP = "192.168.137.1"

def ps(cmd):
    r = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True)
    return (r.stdout + r.stderr).strip()

def query(name, server=IP, tcp=False, timeout=3):
    qid = random.randint(1, 65000)
    q = struct.pack(">HHHHHH", qid, 0x0100, 1, 0, 0, 0)
    q += b"".join(bytes([len(p)]) + p.encode() for p in name.split(".")) + b"\0" + struct.pack(">HH", 1, 1)
    try:
        if tcp:
            s = socket.create_connection((server, 53), timeout=timeout)
            s.sendall(struct.pack(">H", len(q)) + q)
            data = s.recv(4096)[2:]
        else:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.settimeout(timeout)
            s.sendto(q, (server, 53)); data, _ = s.recvfrom(4096)
        s.close()
    except OSError as e:
        return f"keine Antwort ({e.__class__.__name__}: {e})"
    rcode = data[3] & 15; an = struct.unpack(">H", data[6:8])[0]
    ips = [socket.inet_ntoa(data[i+12:i+16]) for i in range(len(data)-16) if data[i:i+4] == b"\x00\x01\x00\x01" and data[i+10:i+12] == b"\x00\x04"]
    return f"rcode={rcode} an={an} ips={ips[-an:] if an else []}"

def endpoints():
    print(ps("Get-NetUDPEndpoint -LocalPort 53 -EA 0 | % { $_.LocalAddress + ' pid=' + $_.OwningProcess + ' ' + (Get-CimInstance Win32_Service -Filter \"ProcessId=$($_.OwningProcess)\" | % Name) -join ',' }"))
    print(ps("Get-NetTCPConnection -LocalPort 53 -State Listen -EA 0 | % { 'TCP ' + $_.LocalAddress + ' pid=' + $_.OwningProcess }"))

print("== Endpunkte Port 53 (ICS an)"); endpoints()
print("== ICS-Antwort auf www.example.com:", query("www.example.com"))
print("== ICS-Antwort TCP:", query("www.example.com", tcp=True))
hosts = r"C:\Windows\System32\drivers\etc\hosts"
open(hosts, "a").write(f"\n{IP} alupc-hosts-probe.example\n")
subprocess.run(["ipconfig", "/flushdns"], capture_output=True)
time.sleep(1)
print("== ICS beachtet hosts-Datei?", query("alupc-hosts-probe.example"))

for host, excl in [(IP, False), (IP, True), ("0.0.0.0", False), ("0.0.0.0", True)]:
    d = PortalDNS(lambda: IP, closed=True, port=53, host=host, exclusive=excl)
    ok = d.start()
    print(f"== AluPC-DNS host={host} exclusive={excl}: start={ok} {d.error}")
    if ok:
        res = [query(f"probe{i}.alupc.test") for i in range(6)]
        print("   UDP:", res, "eigene Anfragen:", d.queries)
        print("   TCP:", query("probe.alupc.test", tcp=True), "eigene Anfragen:", d.queries)
        d.stop(); time.sleep(1.5)

print("== Dienst kurz neu: AluPC-DNS zuerst binden, dann ICS-Neustart")
d = PortalDNS(lambda: IP, closed=True, port=53, host=IP, exclusive=True)
print(ps("Restart-Service SharedAccess -Force; Start-Sleep 3; (Get-Service SharedAccess).Status"))
print("start nach Neustart:", d.start(), d.error); endpoints()
if d.udp: print("   UDP:", [query(f"p{i}.alupc.test") for i in range(4)], d.queries)
