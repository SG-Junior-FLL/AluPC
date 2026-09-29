"""Treiber für Fingerabdruckmodule am seriellen Anschluss (HLK-ZW101 u. a.) gegen ein nachgebautes Modul."""

import json
import sys

import pytest

pytestmark = pytest.mark.skipif(not sys.platform.startswith("linux"), reason="virtueller Anschluss nur unter Linux")
pytest.importorskip("serial")

from alupc.platform import zw_fingerprint as zw  # noqa: E402


@pytest.fixture()
def fake(tmp_path, monkeypatch):
    from fake_zw101 import FakeZW101

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "cfg"))
    module = FakeZW101()
    monkeypatch.setattr(zw, "candidate_ports", lambda: [module.port])
    yield module
    module.close()


def test_packet_roundtrip():
    pkt = zw.build_packet(zw.PID_COMMAND, bytes([zw.CMD_GET_IMAGE]))
    assert pkt.hex() == "ef01ffffffff010003010005"  # wie im Datenblatt (GetImage)
    assert zw.parse_packet(pkt) == (zw.PID_COMMAND, bytes([zw.CMD_GET_IMAGE]))
    broken = pkt[:-1] + b"\x00"
    with pytest.raises(zw.SensorError):
        zw.parse_packet(broken)


def test_probe_and_list(fake):
    backend = zw.SerialFingerprintBackend()
    assert backend.availability() == (True, "")
    sensors = backend.list_sensors()
    assert len(sensors) == 1 and sensors[0].id == fake.port and "50 Plätze" in sensors[0].detail
    fake.password_ok = False  # anderes Gerät/gesperrt → kein Modul
    assert zw.probe(fake.port) is None


def test_enroll_verify_delete(fake):
    backend = zw.SerialFingerprintBackend()
    backend.list_sensors()
    fake.finger = "daumen"
    fake.auto_lift = True
    progress = []
    backend.enroll(fake.port, "right-thumb", lambda text, stage, total: progress.append((text, stage, total)))
    assert fake.library == {0: "daumen"}
    assert progress[-1][1] == progress[-1][2]  # am Ende 100 %
    assert any("abheben" in t for t, _s, _t in progress)
    assert backend.list_enrolled(fake.port) == ["platz:0"]
    assert "Rechter Daumen" in backend.finger_label("platz:0")

    ok, text = backend.verify(fake.port, lambda *_: None)
    assert ok and "Rechter Daumen" in text
    fake.finger = "fremd"
    ok, text = backend.verify(fake.port, lambda *_: None)
    assert not ok and "nicht" in text

    # Denselben Finger neu anlernen → alter Platz wird frei, kein doppelter Eintrag
    fake.finger = "daumen"
    backend.enroll(fake.port, "right-thumb", lambda *_: None)
    assert list(fake.library) == [1]
    backend.delete(fake.port, "platz:1")
    assert fake.library == {} and backend.list_enrolled(fake.port) == []


def test_enroll_detects_different_fingers(fake):
    backend = zw.SerialFingerprintBackend()
    backend.list_sensors()
    fake.auto_lift = True
    fake.finger = "a"
    original = fake._handle

    def swap(cmd, p):  # nach der ersten Aufnahme ein anderer Finger
        if cmd == 0x02 and p[0] == 1:
            result = original(cmd, p)
            fake.finger = "b"
            return result
        return original(cmd, p)

    fake._handle = swap
    with pytest.raises(zw.SensorError, match="passen nicht zusammen"):
        backend.enroll(fake.port, "left-thumb", lambda *_: None)
    assert fake.library == {}


def test_cancel_while_waiting(fake):
    import threading

    from alupc.platform.base import Cancelled

    backend = zw.SerialFingerprintBackend()
    backend.list_sensors()
    fake.finger = None  # niemand legt einen Finger auf
    threading.Timer(0.3, backend.cancel).start()
    with pytest.raises(Cancelled):
        backend.verify(fake.port, lambda *_: None)


def test_pam_check(fake, tmp_path):
    login = tmp_path / "login.json"
    fake.library = {3: "noah", 4: "gast"}
    login.write_text(json.dumps({"users": {"noah": [3]}, "port": fake.port, "baud": 57600, "timeout": 2}))
    fake.finger = "noah"
    assert zw.pam_check({"PAM_USER": "noah"}, login, out=open("/dev/null", "w")) == 0
    fake.finger = "gast"  # gespeichert, aber gehört nicht zu diesem Benutzer
    assert zw.pam_check({"PAM_USER": "noah"}, login, out=open("/dev/null", "w")) == 1
    fake.finger = "noah"
    assert zw.pam_check({"PAM_USER": "jemand"}, login, out=open("/dev/null", "w")) == 1
    fake.finger = None  # kein Finger → nach Zeitlimit ablehnen (Passwort geht dann weiter)
    assert zw.pam_check({"PAM_USER": "noah"}, login, out=open("/dev/null", "w")) == 1
    assert zw.pam_check({"PAM_USER": "noah"}, tmp_path / "fehlt.json") == 1


def test_login_config_and_safety(fake, tmp_path, monkeypatch):
    from alupc.platform import linux_serial_login as login

    zw.save_slots({"0": {"finger": "right-thumb", "user": "noah"}, "2": {"finger": "left-thumb", "user": "noah"},
                   "5": {"finger": "right-thumb", "user": "evil;rm -rf /"}})
    cfg = login.valid_config(zw.login_config("/dev/ttyUSB0", 57600))
    assert cfg["users"] == {} or all(u == zw.current_user() for u in cfg["users"])  # nur eigene Finger
    cfg = login.valid_config({"users": {"noah": [0, 2], "evil;rm -rf /": [5]}, "port": "/dev/ttyUSB0"})
    assert cfg["users"] == {"noah": [0, 2]} and cfg["port"] == "/dev/ttyUSB0"  # unsinnige Namen fliegen raus
    assert login.valid_config({"users": {}, "port": "/etc/shadow"})["port"] == ""
    profile = login.pam_profile("/opt/alupc/AluPC --fingerabdruck-pam")
    assert "pam_exec.so quiet stdout /opt/alupc/AluPC --fingerabdruck-pam" in profile
    assert "Default: no" in profile
    # Start aus dem Quellcode (Python im venv/Home) darf nie als root-Prüfprogramm eingetragen werden
    assert login.helper_is_safe() is False
    monkeypatch.setattr(login, "human_accounts", lambda: ["noah"])
    with pytest.raises(RuntimeError, match=".deb"):
        login.enable_login(cfg)
    # mehrere Konten → nur nach ausdrücklicher Bestätigung (allow_multi), sonst Warnung
    monkeypatch.setattr(login, "human_accounts", lambda: ["noah", "gast"])
    with pytest.raises(login.MultiUserError, match="mehrere Benutzerkonten"):
        login.enable_login(cfg)
    with pytest.raises(RuntimeError, match=".deb"):  # bestätigt → weiter bis zur .deb-Prüfung
        login.enable_login(cfg, allow_multi=True)


def test_garbage_stream_does_not_hang(tmp_path, monkeypatch):
    """Ein Gerät, das ständig anderes sendet (Arduino, GPS …), darf nichts blockieren."""
    import os
    import pty
    import threading
    import time
    import tty

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    master, slave = pty.openpty()
    tty.setraw(slave)
    stop = threading.Event()

    def chatter():
        while not stop.is_set():
            try:
                os.write(master, b"$GPGGA,123519,4807.038,N*47\r\n")
            except OSError:
                return
            time.sleep(0.01)

    threading.Thread(target=chatter, daemon=True).start()
    start = time.monotonic()
    try:
        assert zw.probe(os.ttyname(slave)) is None
    finally:
        stop.set()
        os.close(master)
        os.close(slave)
    assert time.monotonic() - start < 10


def test_login_only_on_single_account_pcs(tmp_path):
    from alupc.platform import linux_serial_login as login

    passwd = tmp_path / "passwd"
    passwd.write_text("root:x:0:0::/root:/bin/bash\nnoah:x:1000:1000::/home/noah:/bin/bash\n"
                      "gdm:x:120:120::/var/lib/gdm3:/bin/false\nsvc:x:1001:1001::/:/usr/sbin/nologin\n")
    assert login.human_accounts(str(passwd)) == ["noah"]
    passwd.write_text(passwd.read_text() + "gast:x:1002:1002::/home/gast:/bin/bash\n")
    assert login.human_accounts(str(passwd)) == ["noah", "gast"]


def test_is_enrolled_uses_finger_names(fake):
    backend = zw.SerialFingerprintBackend()
    backend.list_sensors()
    fake.finger = "x"
    fake.auto_lift = True
    backend.enroll(fake.port, "left-index-finger", lambda *_: None)
    assert backend.is_enrolled(fake.port, "left-index-finger")
    assert not backend.is_enrolled(fake.port, "right-thumb")
    fake.library.clear()  # im Modul gelöscht → nicht mehr angelernt
    assert not backend.is_enrolled(fake.port, "left-index-finger")


def test_multi_user_mapping_is_merged_not_overwritten():
    from alupc.platform import linux_serial_login as login

    existing = {"users": {"anna": [0, 1], "ben": [2]}, "port": "/dev/ttyUSB0", "baud": 57600, "timeout": 6,
                "multi_user": True}
    # Ben lernt neu an (Platz 2 und 5) – Annas Einträge bleiben
    merged = login.merge_config({"users": {"ben": [2, 5]}, "port": "/dev/ttyUSB0", "baud": 57600}, "ben", existing)
    assert merged["users"] == {"anna": [0, 1], "ben": [2, 5]} and merged["multi_user"] is True
    # Ben löscht alle seine Finger → nur Ben verschwindet
    merged = login.merge_config({"users": {}, "port": "/dev/ttyUSB0"}, "ben", existing)
    assert merged["users"] == {"anna": [0, 1]}
    # veralteter Eintrag: Platz 1 war Anna zugeordnet, gehört jetzt Ben → nicht mehr für Anna gültig
    merged = login.merge_config({"users": {"ben": [1]}}, "ben", existing)
    assert merged["users"] == {"anna": [0], "ben": [1]}


def test_foreign_fingers_are_protected(fake, monkeypatch):
    backend = zw.SerialFingerprintBackend()
    backend.list_sensors()
    fake.library = {0: "anna-daumen"}
    monkeypatch.setattr(zw, "foreign_slots", lambda user=None: {0})  # Platz 0 gehört „anna“
    fake.finger = "ben"
    fake.auto_lift = True
    backend.enroll(fake.port, "right-thumb", lambda *_: None)
    assert fake.library == {0: "anna-daumen", 1: "ben"}  # Annas Platz wird nicht belegt
    with pytest.raises(zw.SensorError, match="anderen Benutzer"):
        backend.delete(fake.port, "platz:0")
    backend.delete(fake.port, "*")  # „Alle löschen“ = alle eigenen
    assert fake.library == {0: "anna-daumen"}
    assert "anderen Benutzers" in backend.finger_label("platz:0")


def test_windows_login_config(tmp_path, monkeypatch):
    """Windows-Anmeldung mit dem Modul: Einstellung für den Anmeldebaustein (C++ liest genau dieses Format),
    Einschalten/Finger aktualisieren/Ausschalten – mehrere Benutzer bleiben getrennt."""
    from alupc.platform import windows_serial_login as w

    calls = []
    monkeypatch.setattr(w, "register", lambda dll: calls.append(("register", str(dll))))
    monkeypatch.setattr(w, "unregister", lambda: calls.append(("unregister",)))
    monkeypatch.setattr(w, "secure_file", lambda p: calls.append(("acl", p.name)))
    cfg = tmp_path / "AluPC" / "fingerprint-windows.cfg"
    dll = tmp_path / "AluPCFingerprint.dll"
    w.apply_request({"action": "an", "user": "noah", "domain": ".", "slots": [2, 1], "port": "COM4",
                     "baud": 57600, "capacity": 300, "secret": "aa11"}, path=cfg, dll=dll)
    text = cfg.read_text(encoding="utf-8")
    assert "port=COM4\nbaud=57600\ncapacity=300\n" in text and "user=noah\t.\t2,1\taa11\n" in text
    assert ("acl", cfg.name) in calls and ("register", str(dll)) in calls
    w.apply_request({"action": "an", "user": "lena", "domain": "SCHULE", "slots": [5], "secret": "bb22"},
                    path=cfg, dll=dll)
    w.apply_request({"action": "plaetze", "user": "noah", "slots": [1, 3]}, path=cfg, dll=dll)
    parsed = w.read_config(cfg)
    assert parsed["users"]["noah"] == {"domain": ".", "slots": [1, 3], "secret": "aa11"}  # Passwort bleibt
    assert parsed["users"]["lena"]["domain"] == "SCHULE" and parsed["port"] == "COM4"
    w.apply_request({"action": "aus", "user": "noah", "slots": []}, path=cfg, dll=dll)
    assert list(w.read_config(cfg)["users"]) == ["lena"] and ("unregister",) not in calls
    w.apply_request({"action": "aus", "user": "lena", "slots": []}, path=cfg, dll=dll)
    assert not cfg.exists() and ("unregister",) in calls  # keiner mehr → Baustein abgemeldet
    # Fehlerweg des Admin-Aufrufs: Fehlertext landet neben dem Auftrag
    req = tmp_path / "auftrag.json"
    req.write_text("kein json", encoding="utf-8")
    assert w.run_request_file(str(req)) == 1 and (tmp_path / "auftrag.json.fehler").exists()


def test_windows_login_needs_password(monkeypatch):
    """Windows: Einschalten ohne Passwort geht nicht; mit Passwort wird es geprüft, verschlüsselt und per
    Admin-Auftrag eingetragen – mit den eigenen Fingern."""
    from alupc.platform import windows_serial_login as w
    from alupc.platform import zw_fingerprint as zw

    monkeypatch.setattr(zw.sys, "platform", "win32")
    backend = zw.SerialFingerprintBackend()
    backend._found = {"COM5": (115200, {"capacity": 200})}
    monkeypatch.setattr(zw, "load_slots", lambda: {"1": {"user": "noah"}, "4": {"user": "noah"},
                                                   "9": {"user": "lena"}})
    monkeypatch.setattr(zw, "current_user", lambda: "noah")
    monkeypatch.setattr(w, "current_account", lambda: ("noah", "."))
    monkeypatch.setattr(w, "verify_password", lambda u, d, p: p == "richtig")
    monkeypatch.setattr(w, "protect", lambda p: "verschluesselt")
    sent = []
    monkeypatch.setattr(w, "request_elevated", sent.append)
    with pytest.raises(zw.SensorError, match="Passwort"):
        backend.set_login_enabled(True)
    with pytest.raises(zw.SensorError, match="stimmt nicht"):
        backend.set_login_enabled(True, password="falsch")
    backend.set_login_enabled(True, password="richtig")
    assert sent[-1] == {"action": "an", "user": "noah", "domain": ".", "slots": [1, 4], "port": "COM5",
                        "baud": 115200, "capacity": 200, "secret": "verschluesselt"}
    backend.set_login_enabled(False)
    assert sent[-1]["action"] == "aus"


def test_windows_exclusive_port(fake, monkeypatch):
    """Windows: ein COM-Anschluss lässt sich nur einmal gleichzeitig öffnen. Anlernen, Liste, Prüfen und Löschen
    dürfen ihn deshalb nie doppelt öffnen (Fehler aus 0.51: „Kein Zugriff auf COM16“ beim Anlernen)."""
    real_serial = zw.serial.Serial
    open_ports = set()

    class ExclusiveSerial:
        def __init__(self, port, *a, **kw):
            if port in open_ports:
                raise zw.serial.SerialException(
                    f"could not open port '{port}': PermissionError(13, 'Zugriff verweigert', None, 5)")
            self._inner = real_serial(port, *a, **kw)
            self._port = port
            open_ports.add(port)

        def close(self):
            open_ports.discard(self._port)
            self._inner.close()

        def __getattr__(self, name):
            return getattr(self._inner, name)

    monkeypatch.setattr(zw.serial, "Serial", ExclusiveSerial)
    backend = zw.SerialFingerprintBackend()
    assert backend.list_sensors()
    fake.finger = "zeige"
    fake.auto_lift = True
    backend.enroll(fake.port, "right-index", lambda *_: None)
    assert backend.list_enrolled(fake.port) == ["platz:0"]
    assert backend.verify(fake.port, lambda *_: None)[0]
    backend.delete(fake.port, "platz:0")
    assert not open_ports  # alles wieder geschlossen

    # Belegt von einem anderen Programm (Windows): verständliche Meldung statt Linux-Hinweis
    monkeypatch.setattr(zw.sys, "platform", "win32")
    open_ports.add(fake.port)
    with pytest.raises(zw.SensorError, match="anderen Programm belegt"):
        zw.ZWSensor(fake.port).open(busy_wait=0.3)
    open_ports.discard(fake.port)
