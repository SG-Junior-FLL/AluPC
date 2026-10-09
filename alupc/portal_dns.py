"""Kleiner DNS-Server für die WLAN-Anmeldeseite (Linux-Hotspot).

Im AluPC-WLAN („geschlossen“) beantwortet er JEDE Namensfrage mit der Adresse des PCs – so landet jede Prüfung
der Handys („bin ich im Internet?“) bei AluPC, das Handy erkennt „Anmeldung nötig“ und öffnet die Anmeldeseite.
Im normalen Hotspot („offen“) zeigen nur die Prüf-Adressen auf den PC, alles andere wird normal aufgelöst.

Der Hotspot leitet Port 53 (UDP und TCP) per iptables hierher um (siehe hotspot.portal_script). Unabhängig von
NetworkManagers eigenem dnsmasq – dessen Zusatz-Einstellungen werden je nach Version nicht gelesen.
"""

from __future__ import annotations

import socket
import struct
import sys
import threading

PORT = 8753
TTL = 15


def _qname(data: bytes, pos: int) -> tuple[str, int]:
    labels = []
    while True:
        n = data[pos]
        if n == 0:
            return ".".join(labels), pos + 1
        if n & 0xC0:  # Zeiger kommen in Fragen nicht vor
            raise ValueError("Zeiger")
        labels.append(data[pos + 1:pos + 1 + n].decode("ascii", "replace"))
        pos += 1 + n


def answer(query: bytes, ip_for: callable) -> bytes | None:
    """DNS-Antwort bauen. ip_for(name, qtype) → Liste von IPv4-Adressen (leer = keine Einträge, None = NXDOMAIN)."""
    if len(query) < 12:
        return None
    qid, flags, qd = struct.unpack(">HHH", query[:6])
    if flags & 0x8000 or qd != 1:  # keine Frage
        return None
    try:
        name, pos = _qname(query, 12)
        qtype, qclass = struct.unpack(">HH", query[pos:pos + 4])
    except (ValueError, IndexError, struct.error):
        return None
    question = query[12:pos + 4]
    ips = ip_for(name.lower().rstrip("."), qtype) if qclass == 1 else []
    rcode = 3 if ips is None else 0
    ips = [ip for ip in (ips or []) if qtype == 1]  # nur A-Einträge (der Hotspot hat kein IPv6)
    header = struct.pack(">HHHHHH", qid, 0x8180 | rcode | (flags & 0x0100), 1, len(ips), 0, 0)
    body = b"".join(b"\xc0\x0c" + struct.pack(">HHIH", 1, 1, TTL, 4) + socket.inet_aton(ip) for ip in ips)
    return header + question + body


class PortalDNS:
    def __init__(self, ip_provider, closed: bool = True, hosts: list[str] | None = None, port: int = PORT,
                 host: str = "0.0.0.0", exclusive: bool = False, restrict: bool = False):
        self.ip_provider, self.closed, self.port, self.host = ip_provider, closed, port, host
        self.exclusive = exclusive  # Windows: Port für sich allein (SO_EXCLUSIVEADDRUSE)
        self.restrict = restrict  # nur Geräte im Hotspot-Netz (Windows: lauscht auf allen Adressen)
        self.hosts = {h.lower() for h in (hosts or [])}
        self.udp: socket.socket | None = None
        self.tcp: socket.socket | None = None
        self.queries = 0
        self.error = ""
        self.allowed: set[str] = set()  # Geräte mit Internet: bekommen echte Antworten
        self.clients: dict[str, int] = {}  # Namensfragen je Gerät (zeigt: kommen die Handys hier an?)
        self.names: dict[str, list[str]] = {}  # zuletzt gefragte Namen je Gerät (zeigt, was das Handy prüft)

    def ip_for(self, name: str, qtype: int, client: str = ""):
        if client and client in self.allowed:  # am PC freigeschaltet: echtes Internet
            return self._resolve(name, qtype)
        if self.closed or name in self.hosts:
            return [self.ip_provider()]
        return self._resolve(name, qtype)

    @staticmethod
    def _resolve(name: str, qtype: int):
        if qtype != 1:
            return []
        try:  # offenes WLAN: normal auflösen (über den PC)
            return sorted({a[4][0] for a in socket.getaddrinfo(name, None, socket.AF_INET)})
        except socket.gaierror:
            return None
        except OSError:
            return []

    def start(self) -> bool:
        if self.udp is not None:
            return True
        try:
            udp = self._socket(socket.SOCK_DGRAM)
        except OSError as exc:
            self.error = str(exc)
            return False
        try:
            tcp = self._socket(socket.SOCK_STREAM)
            tcp.listen(16)
        except OSError as exc:
            udp.close()
            self.error = str(exc)
            return False
        udp.settimeout(1.0)  # damit stop() die Schleifen sicher beendet
        tcp.settimeout(1.0)
        self.udp, self.tcp = udp, tcp
        threading.Thread(target=self._serve_udp, name="alupc-dns-udp", daemon=True).start()
        threading.Thread(target=self._serve_tcp, name="alupc-dns-tcp", daemon=True).start()
        return True

    def _socket(self, kind):
        sock = socket.socket(socket.AF_INET, kind)
        try:
            if self.exclusive and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            elif not sys.platform.startswith("win"):  # unter Windows hieße REUSEADDR: fremden Port mitbenutzen
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((self.host, self.port))
        except OSError:
            sock.close()
            raise
        return sock

    def _from_hotspot(self, client: str) -> bool:
        import ipaddress

        try:
            ip = ipaddress.ip_address(client)
            return ip.is_loopback or ip in ipaddress.ip_network(f"{self.ip_provider()}/24", strict=False)
        except ValueError:
            return False

    def _reply(self, data: bytes, client: str = "") -> bytes | None:
        if self.restrict and client and not self._from_hotspot(client):
            return None  # Fragen aus anderen Netzen (LAN) nicht beantworten
        self.queries += 1
        if client and not client.startswith("127.") and client != self.ip_provider():  # PC selbst zählt nicht
            self.clients[client] = self.clients.get(client, 0) + 1
        counted = client in self.clients

        def ip_for(name, qtype):
            if counted and name:
                seen = self.names.setdefault(client, [])
                if name in seen:
                    seen.remove(name)
                seen.append(name)
                del seen[:-12]
            return self.ip_for(name, qtype, client)

        try:
            return answer(data, ip_for)
        except Exception:  # noqa: BLE001 - kaputte Anfrage: ignorieren
            return None

    def _serve_udp(self):
        sock = self.udp
        while sock is self.udp and sock is not None:
            try:
                data, addr = sock.recvfrom(1500)
            except socket.timeout:
                continue
            except OSError:
                return

            def handle(d=data, a=addr):
                out = self._reply(d, a[0])
                if out and sock is self.udp:
                    try:
                        sock.sendto(out, a)
                    except OSError:
                        pass

            if self.closed and addr[0] not in self.allowed:
                handle()
            else:  # offen: Auflösen kann dauern → nicht die anderen aufhalten
                threading.Thread(target=handle, daemon=True).start()

    def _serve_tcp(self):
        sock = self.tcp
        while sock is self.tcp and sock is not None:
            try:
                conn, _addr = sock.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            threading.Thread(target=self._tcp_client, args=(conn, _addr[0]), daemon=True).start()

    def _tcp_client(self, conn, client: str = ""):
        try:
            conn.settimeout(5)
            head = conn.recv(2)
            if len(head) < 2:
                return
            size = struct.unpack(">H", head)[0]
            data = b""
            while len(data) < size:
                chunk = conn.recv(size - len(data))
                if not chunk:
                    return
                data += chunk
            out = self._reply(data, client)
            if out:
                conn.sendall(struct.pack(">H", len(out)) + out)
        except OSError:
            pass
        finally:
            conn.close()

    def stop(self) -> None:
        socks = (self.udp, self.tcp)
        self.udp = self.tcp = None  # Schleifen enden beim nächsten Durchlauf
        for s in socks:
            if s is not None:
                try:
                    s.close()
                except OSError:
                    pass
