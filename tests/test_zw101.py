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


def test_login_config_and_safety(fake, tmp_path):
    from alupc.platform import linux_serial_login as login

    zw.save_slots({"0": {"finger": "right-thumb", "user": "noah"}, "2": {"finger": "left-thumb", "user": "noah"},
                   "5": {"finger": "right-thumb", "user": "evil;rm -rf /"}})
    cfg = login.valid_config(zw.login_config("/dev/ttyUSB0", 57600))
    assert cfg["users"] == {"noah": [0, 2]} and cfg["port"] == "/dev/ttyUSB0"  # unsinnige Namen fliegen raus
    assert login.valid_config({"users": {}, "port": "/etc/shadow"})["port"] == ""
    profile = login.pam_profile("/opt/alupc/AluPC --fingerabdruck-pam")
    assert "pam_exec.so quiet stdout /opt/alupc/AluPC --fingerabdruck-pam" in profile
    assert "Default: no" in profile
    # Start aus dem Quellcode (Python im venv/Home) darf nie als root-Prüfprogramm eingetragen werden
    assert login.helper_is_safe() is False
    with pytest.raises(RuntimeError, match=".deb"):
        login.enable_login(cfg)


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
