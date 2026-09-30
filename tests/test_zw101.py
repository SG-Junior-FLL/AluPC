"""Treiber für Fingerabdruckmodule am seriellen Anschluss (HLK-ZW101 u. a.) gegen ein nachgebautes Modul."""

import json
import sys

import pytest

pytestmark = pytest.mark.skipif(not sys.platform.startswith("linux"), reason="virtueller Anschluss nur unter Linux")
pytest.importorskip("serial")

from alupc.platform import zw_fingerprint as zw  # noqa: E402


@pytest.fixture(autouse=True)
def _no_person():
    zw.set_person("")
    yield
    zw.set_person("")


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
    seen = []
    assert zw.pam_check({"PAM_USER": "noah"}, login, out=open("/dev/null", "w"),
                        record=lambda u, slot: seen.append((u, slot))) == 0
    assert seen == [("noah", 3)]  # erkannter Platz → „Willkommen, …“ in AluPC
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
                        "baud": 115200, "capacity": 200, "secret": "verschluesselt", "sid": ""}
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


def test_several_persons(fake, monkeypatch):
    """Mehrere Personen lernen am selben Konto an (z. B. 5 Personen × 10 Finger bei 50 Plätzen): derselbe Finger
    zweier Personen belegt zwei Plätze, Neu-Anlernen ersetzt nur den Platz derselben Person."""
    monkeypatch.setattr(zw, "current_user", lambda: "noah")
    backend = zw.SerialFingerprintBackend()
    backend.list_sensors()
    fake.auto_lift = True
    for person, finger in (("Noah", "n"), ("Lena", "l"), ("Noah", "n2")):
        zw.set_person(person)
        fake.finger = finger
        backend.enroll(fake.port, "right-index", lambda *_: None)
    slots = zw.load_slots()
    assert sorted((v["person"], k) for k, v in slots.items()) == [("Lena", "1"), ("Noah", "2")]
    assert fake.library == {1: "l", 2: "n2"}
    assert backend.usage is None or backend.usage[1] == 50
    assert backend.list_enrolled(fake.port) == ["platz:1", "platz:2"]  # nach Person sortiert
    assert backend.usage == (2, 50)
    assert zw.persons() == ["Noah", "Lena"]  # gewählte Person zuerst
    assert backend.is_enrolled(fake.port, "right-index")
    zw.set_person("Mia")
    assert not backend.is_enrolled(fake.port, "right-index")
    assert "Lena · " in backend.finger_label("platz:1")
    # alle Personen dürfen das Konto entsperren
    assert backend._my_slots() == [1, 2]


def test_pam_reads_own_slots_file(fake, tmp_path, monkeypatch):
    """Linux: Neue Finger/Personen gelten sofort – die Prüfung liest die Plätze-Datei des Benutzers
    (ohne erneute Passwortabfrage für /etc). Die Datei muss dem Benutzer gehören."""
    import getpass
    import os
    import pwd

    me = getpass.getuser()
    home = tmp_path / "home"
    f = home / ".config" / "AluPC" / "fingerprint-slots.json"
    f.parent.mkdir(parents=True)
    f.write_text(json.dumps({"3": {"finger": "a", "user": me, "person": "Lena"}, "5": {"finger": "b", "user": "x"}}))
    assert zw.user_slots_from_home(me, str(home)) == {3}
    assert zw.user_slots_from_home("gibt-es-nicht-xyz", str(home)) is None
    real = pwd.getpwnam(me)
    monkeypatch.setattr(pwd, "getpwnam", lambda n: type("P", (), {"pw_dir": str(home), "pw_uid": real.pw_uid})())
    login = tmp_path / "login.json"
    fake.library = {3: "lena", 4: "alt"}
    # /etc kennt nur den alten Platz 4 – die eigene Datei (Platz 3) gilt
    login.write_text(json.dumps({"users": {me: [4]}, "port": fake.port, "baud": 57600, "timeout": 2}))
    fake.finger = "lena"
    assert zw.pam_check({"PAM_USER": me}, login, out=open(os.devnull, "w")) == 0
    fake.finger = "alt"
    assert zw.pam_check({"PAM_USER": me}, login, out=open(os.devnull, "w")) == 1
    # Datei gehört jemand anderem → nicht vertrauen, /etc gilt
    monkeypatch.setattr(pwd, "getpwnam", lambda n: type("P", (), {"pw_dir": str(home), "pw_uid": real.pw_uid + 1})())
    assert zw.user_slots_from_home(me) is None
    # Konto nicht eingeschaltet → nie
    login.write_text(json.dumps({"users": {}, "port": fake.port, "baud": 57600, "timeout": 2}))
    fake.finger = "lena"
    assert zw.pam_check({"PAM_USER": me}, login, out=open(os.devnull, "w")) == 1


def test_windows_slots_file(tmp_path, monkeypatch):
    """Windows: Beim Einschalten entsteht fingerprint-<Benutzer>.slots (Besitzer Administratoren, Benutzer darf
    ändern). AluPC schreibt dort neue Plätze ohne Administratorrechte hinein."""
    from alupc.platform import windows_serial_login as w

    calls = []
    monkeypatch.setattr(w.subprocess, "run", lambda args, **kw: calls.append(args) or
                        type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})())
    monkeypatch.setattr(w, "register", lambda dll: None)
    monkeypatch.setattr(w, "unregister", lambda: None)
    monkeypatch.setattr(w, "config_path", lambda: tmp_path / "fingerprint-windows.cfg")
    cfg, dll = tmp_path / "fingerprint-windows.cfg", tmp_path / "x.dll"
    assert w.slots_path("Jürgen Ö", tmp_path).name == "fingerprint-J_rgen _.slots"
    w.apply_request({"action": "an", "user": "noah", "domain": ".", "slots": [1], "secret": "ab",
                     "sid": "S-1-5-21-11-22-33-1001"}, path=cfg, dll=dll)
    sp = w.slots_path("noah", tmp_path)
    assert sp.read_text() == "1\n"
    assert any("/setowner" in a for a in calls) and any("*S-1-5-21-11-22-33-1001:M" in a for a in calls)
    assert w.write_own_slots([4, 1, 9], "noah") and sp.read_text() == "1,4,9\n"
    # Namen der Personen für „Hallo Lena“ auf dem Sperrbildschirm (Zeilenumbrüche/„=“ im Namen unschädlich)
    assert w.write_own_slots([4, 1], "noah", names={4: "Lena", 1: "Max\n=x"})
    assert sp.read_text() == "1,4\n1=Max -x\n4=Lena\n"
    assert not w.write_own_slots([1], "lena")  # keine Datei → Rückfall auf Administratorrechte
    # ungültige SID → keine Datei
    w.apply_request({"action": "an", "user": "lena", "domain": ".", "slots": [2], "secret": "ab", "sid": "bla"},
                    path=cfg, dll=dll)
    assert not w.slots_path("lena", tmp_path).exists()
    w.apply_request({"action": "aus", "user": "noah", "slots": []}, path=cfg, dll=dll)
    assert not sp.exists()


def test_windows_sync_login_without_admin(fake, monkeypatch):
    """Windows mit eingeschalteter Anmeldung: Anlernen schreibt die Plätze-Datei, kein Admin-Auftrag."""
    from alupc.platform import windows_serial_login as w

    backend = zw.SerialFingerprintBackend()
    backend.list_sensors()
    monkeypatch.setattr(zw.sys, "platform", "win32")
    monkeypatch.setattr(w, "login_enabled", lambda user=None: True)
    monkeypatch.setattr(type(backend), "login_toggle", property(lambda self: True))
    written, elevated = [], []
    monkeypatch.setattr(w, "write_own_slots",
                        lambda slots, user=None, names=None: written.append((slots, names)) or True)
    monkeypatch.setattr(w, "update_slots", lambda *a: elevated.append(a))
    fake.auto_lift = True
    fake.finger = "a"
    zw.set_person("Lena")
    backend.enroll(fake.port, "left-thumb", lambda *_: None)
    assert written == [([0], {0: "Lena"})] and not elevated
    assert backend.usage == (1, 50)  # gleich nach dem Anlernen neu gezählt
    monkeypatch.setattr(w, "write_own_slots", lambda slots, user=None, names=None: False)
    backend._sync_login(fake.port)
    assert elevated  # Datei fehlt (ältere Einrichtung) → wie bisher mit Administratorrechten


def test_dual_boot_sync_of_names(tmp_path, monkeypatch):
    """Namen/Personen gehen per Dual-Boot-Abgleich mit; der Windows-Benutzer wird zum Linux-Benutzer."""
    from alupc import settings_sync as ss

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.setattr(zw, "current_user", lambda: "noah")
    remote = {"user": "Noah", "slots": {"1": {"finger": "right-index", "user": "Noah", "person": "Lena"},
                                        "2": {"finger": "left-thumb", "user": "Noah"},
                                        "7": {"finger": "left-index", "user": "Gast"},
                                        "x": {"finger": "kaputt"}, "9": {"finger": 5}}}
    merged = zw.merge_synced({"3": {"finger": "a", "user": "noah", "person": "Mia"}}, remote, "noah")
    assert merged == {"3": {"finger": "a", "user": "noah", "person": "Mia"},
                      "1": {"finger": "right-index", "user": "noah", "person": "Lena"},
                      "2": {"finger": "left-thumb", "user": "noah", "person": "Noah"},
                      "7": {"finger": "left-index", "user": "Gast"}}
    zw.save_slots({})

    class Cfg:
        data = {}

        def save(self):
            pass

    assert "fingerprint_slots" not in ss.payload(Cfg(), ["fingerprint_slots"])  # nichts angelernt → nichts
    assert ss.apply_payload(Cfg(), {"fingerprint_slots": remote}, ["fingerprint_slots"]) == ["fingerprint_slots"]
    assert zw.load_slots()["1"]["user"] == "noah"
    out = ss.payload(Cfg(), ["fingerprint_slots"])["fingerprint_slots"]
    assert out["user"] == "noah" and out["slots"]["1"]["person"] == "Lena"
    assert ss.apply_payload(Cfg(), {"fingerprint_slots": remote}, ["fingerprint_slots"]) == []  # schon gleich
    assert "fingerabdruck" in ss.SECTIONS


def test_windows_login_state_without_admin_rights(fake, tmp_path, monkeypatch):
    """Fehler bis 0.54: AluPC (ohne Adminrechte) darf die geschützte fingerprint-windows.cfg nicht lesen, hielt die
    Anmeldung deshalb für aus und trug neue Finger nie bei Windows ein – nur der erste Finger ging.
    Jetzt zählt die eigene Plätze-Datei, und AluPC repariert eine veraltete Liste von selbst."""
    from alupc.platform import windows_serial_login as w

    cfg = tmp_path / "fingerprint-windows.cfg"
    cfg.mkdir()  # wie „Zugriff verweigert“: lesen wirft OSError
    monkeypatch.setattr(w, "config_path", lambda: cfg)
    monkeypatch.setattr(w, "registered", lambda: True)
    monkeypatch.setattr(w, "current_account", lambda: ("noah", "."))
    monkeypatch.setattr(zw, "current_user", lambda: "noah")
    assert w.login_enabled() is None  # mit alter Version eingeschaltet → „Neu einrichten“
    sp = w.slots_path("noah")
    sp.write_text("0\n", encoding="utf-8")  # beim Einschalten gab es nur den ersten Finger
    assert w.login_enabled() is True

    backend = zw.SerialFingerprintBackend()
    backend.list_sensors()
    monkeypatch.setattr(zw.sys, "platform", "win32")
    monkeypatch.setattr(type(backend), "login_toggle", property(lambda self: True))
    fake.auto_lift = True
    for person, finger in (("Noah", "a"), ("Lena", "b")):
        zw.set_person(person)
        fake.finger = finger
        backend.enroll(fake.port, "right-index", lambda *_: None)
    assert sp.read_text(encoding="utf-8") == "0,1\n0=Noah\n1=Lena\n"  # beide Personen bei Windows
    sp.write_text("0\n", encoding="utf-8")  # veraltet (z. B. aus 0.53/0.54)
    backend.list_enrolled(fake.port)
    assert backend.login_check == "repariert" and sp.read_text(encoding="utf-8").startswith("0,1\n")
    backend.list_enrolled(fake.port)
    assert backend.login_check == "ok"


def test_welcome_record_and_read(tmp_path):
    """Begrüßung: PAM merkt sich den Platz (als Benutzer im Home, als root in /run/alupc), AluPC liest den neuesten."""
    import os

    from alupc import welcome

    home = tmp_path / "home"
    run = tmp_path / "run"
    assert welcome.record_login("noah", 4, now=100.0, euid=1000, home=str(home))
    assert welcome.last_login("noah", run_dir=run, home=str(home)) == (4, 100.0)
    if os.geteuid() == 0:
        assert welcome.record_login("noah", 9, now=200.0, run_dir=run)
        assert (run / "finger-noah.json").is_file()
        assert welcome.last_login("noah", run_dir=run, home=str(home)) == (9, 200.0)
        os.chmod(run, 0o777)  # von anderen beschreibbar → root schreibt dort nichts
        assert welcome.record_login("noah", 5, now=300.0, run_dir=run) is None
    assert welcome.last_login("jemand", run_dir=run, home=str(tmp_path / "leer")) is None
    assert not list(home.rglob("*.tmp"))


def test_finger_shortcuts(fake):
    """Finger als Schnelltaste: neu aufgelegter Finger → Befehl (einmal); nicht bei gesperrtem PC und nicht, wenn
    der Finger vom Entsperren noch drauf liegt; keine Abfrage, während AluPC das Modul selbst benutzt."""
    import time

    from alupc.finger_shortcuts import FingerShortcuts

    fake.library = {3: "noah", 4: "lena"}
    config = {"finger_shortcuts": {"on": True, "map": {"3": "schwarz", "4": "szene:Pause"}}}
    state = {"locked": False}
    got = []
    fs = FingerShortcuts(config, locked=lambda: state["locked"], port=lambda: (fake.port, 57600), poll=0.05)
    fs.triggered.connect(got.append)

    from PySide6.QtCore import QCoreApplication

    app = QCoreApplication.instance() or QCoreApplication([])

    def pause(seconds):  # Signal kommt (wie in AluPC) über die Qt-Ereignisschleife in diesen Thread
        end = time.time() + seconds
        while time.time() < end:
            app.processEvents()
            time.sleep(0.02)

    def wait(cond, seconds=4):
        end = time.time() + seconds
        while not cond() and time.time() < end:
            pause(0.05)
        return cond()

    fake.finger = "noah"  # liegt schon beim Start drauf → nichts
    fs.apply()
    assert fs.running()
    pause(0.6)
    assert got == []
    fake.finger = None
    pause(1.0)
    fake.finger = "noah"
    assert wait(lambda: got == ["schwarz"])
    pause(0.5)
    assert got == ["schwarz"]  # liegen lassen → nicht nochmal
    fake.finger = None
    pause(1.0)
    fake.finger = "lena"
    assert wait(lambda: got == ["schwarz", "szene:Pause"])
    fake.finger = None
    pause(1.0)
    state["locked"] = True  # Sperrbildschirm: Modul gehört der Anmeldung
    fake.finger = "noah"
    pause(0.8)
    assert got == ["schwarz", "szene:Pause"]
    state["locked"] = False  # entsperrt, Finger liegt noch → nichts
    pause(2.8)
    assert got == ["schwarz", "szene:Pause"]
    fake.finger = None
    # AluPC benutzt das Modul selbst (Anlernen/Test-Scan) → Schnelltasten warten
    lock = zw._port_lock(fake.port)
    lock.acquire()
    pause(0.3)
    fake.finger = "noah"
    pause(0.6)
    assert got == ["schwarz", "szene:Pause"]
    lock.release()
    fake.finger = None
    pause(1.0)
    fake.finger = "noah"
    assert wait(lambda: len(got) == 3, 6)
    config["finger_shortcuts"]["on"] = False
    fs.apply()
    assert not fs.running()
