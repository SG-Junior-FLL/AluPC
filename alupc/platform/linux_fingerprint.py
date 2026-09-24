"""Fingerabdruck unter Linux über fprintd (D-Bus) und PAM (pam-auth-update)."""

from __future__ import annotations

import shutil
import subprocess
import threading
from pathlib import Path

from . import dbus_util
from .base import Cancelled, FingerprintBackend, Sensor

FPRINT = "net.reactivated.Fprint"
MANAGER_PATH = "/net/reactivated/Fprint/Manager"
MANAGER_IFACE = "net.reactivated.Fprint.Manager"
DEVICE_IFACE = "net.reactivated.Fprint.Device"

ENROLL_TEXT = {
    "enroll-completed": "Fertig! Finger erfolgreich angelernt.",
    "enroll-stage-passed": "Gut! Finger kurz anheben und wieder auflegen.",
    "enroll-retry-scan": "Nicht erkannt – bitte noch einmal auflegen.",
    "enroll-swipe-too-short": "Zu kurz gewischt – bitte noch einmal.",
    "enroll-finger-not-centered": "Finger nicht mittig – bitte mittig auflegen.",
    "enroll-remove-and-retry": "Finger abnehmen und neu auflegen.",
    "enroll-duplicate": "Dieser Finger ist schon angelernt.",
    "enroll-data-full": "Der Sensor ist voll – bitte erst Finger löschen.",
    "enroll-disconnected": "Sensor wurde getrennt.",
    "enroll-failed": "Anlernen fehlgeschlagen.",
    "enroll-unknown-error": "Unbekannter Fehler beim Anlernen.",
}
VERIFY_TEXT = {
    "verify-match": "Erkannt – Fingerabdruck passt.",
    "verify-no-match": "Nicht erkannt – Fingerabdruck passt nicht.",
    "verify-retry-scan": "Bitte noch einmal auflegen.",
    "verify-swipe-too-short": "Zu kurz gewischt – bitte noch einmal.",
    "verify-finger-not-centered": "Finger nicht mittig – bitte noch einmal.",
    "verify-remove-and-retry": "Finger abnehmen und neu auflegen.",
    "verify-disconnected": "Sensor wurde getrennt.",
    "verify-unknown-error": "Unbekannter Fehler.",
}
ENROLL_DONE_OK = "enroll-completed"
PAM_FILE = Path("/etc/pam.d/common-auth")
PACKAGES = {"fprintd": ("/usr/libexec/fprintd", "/usr/lib/fprintd/fprintd"),
            "libpam-fprintd": ("/usr/share/pam-configs/fprintd",)}
SUPPORTED_LIST = "https://fprint.freedesktop.org/supported-devices.html"

# USB-Hersteller von Fingerabdrucksensoren (Synaptics/Elan bauen auch Touchpads → Produkt-IDs prüfen)
FP_VENDORS = {
    "27c6": "Goodix", "138a": "Validity/Synaptics", "1c7a": "EgisTec", "2808": "FocalTech",
    "10a5": "FPC", "147e": "UPEK", "08ff": "AuthenTec", "298d": "Next Biometrics", "06cb": "Synaptics",
    "04f3": "Elan", "2541": "Chipsailing", "3274": "Microarray",
}
DRIVER_HINTS = {
    "27c6": "Goodix: Einige Modelle laufen nur mit dem Zusatztreiber „libfprint-2-tod1-goodix“ "
            "(Dell/Lenovo, Ubuntu-OEM-Paketquelle), viele neuere (noch) gar nicht.",
    "138a": "Validity: Ältere Modelle (138a:0090/0097/009d) gehen mit dem Community-Treiber "
            "„python-validity“ (ohne Gewähr).",
    "06cb": "Synaptics: Neuere libfprint-Versionen (Ubuntu 24.04+) kennen viele Modelle – "
            "ein System-Update kann helfen.",
    "2541": "Chipsailing (z. B. CS9711, typischer günstiger USB-Leser): wird vom normalen Linux-Treiber "
            "(libfprint) nicht unterstützt. Unter Windows geht er mit dem Windows-Hello-Treiber.",
    "3274": "Microarray: wird vom normalen Linux-Treiber (libfprint) nicht unterstützt.",
}


def _is_fingerprint_device(vendor: str, product: str, name: str) -> bool:
    lowered = name.lower()
    if any(word in lowered for word in ("finger", "fprint", "biometric")):
        return True
    if vendor == "04f3":
        return product.startswith("0c")  # Elan-Fingerabdrucksensoren: 04f3:0cxx
    if vendor == "06cb":
        return product.startswith("00")  # Synaptics-Fingerabdrucksensoren: 06cb:00xx
    return vendor in FP_VENDORS


def detect_usb_sensors(root: Path = Path("/sys/bus/usb/devices")) -> list[tuple[str, str]]:
    """Fingerabdrucksensoren am USB (auch ohne passenden Treiber) → [(Name, Hinweis)]."""
    found = []
    try:
        devices = sorted(root.iterdir())
    except OSError:
        return []
    for dev in devices:
        try:
            vendor = (dev / "idVendor").read_text().strip().lower()
            product = (dev / "idProduct").read_text().strip().lower()
        except OSError:
            continue
        try:
            name = (dev / "product").read_text().strip()
        except OSError:
            name = ""
        if not _is_fingerprint_device(vendor, product, name):
            continue
        label = f"{FP_VENDORS.get(vendor, 'Sensor')} {name}".strip() + f" (USB {vendor}:{product})"
        found.append((label, DRIVER_HINTS.get(vendor, "")))
    return found


def _package_installed(pkg: str) -> bool:
    if shutil.which("dpkg-query"):
        proc = subprocess.run(["dpkg-query", "-W", "-f=${Status}", pkg], capture_output=True, text=True)
        if proc.returncode == 0:
            return "install ok installed" in proc.stdout
    return any(Path(p).exists() for p in PACKAGES[pkg])


def _friendly_error(exc: Exception) -> str:
    text = str(exc)
    if isinstance(exc, (FileNotFoundError, ConnectionError)):
        return "Keine Verbindung zum System-D-Bus – fprintd ist nicht erreichbar."
    if "NoEnrolledPrints" in text:
        return "Für diesen Sensor sind noch keine Finger angelernt."
    if "PermissionDenied" in text or "NotAuthorized" in text:
        return "Keine Berechtigung (Passwortabfrage abgelehnt?)."
    if "AlreadyInUse" in text:
        return "Der Sensor wird gerade von einem anderen Programm benutzt."
    if "ServiceUnknown" in text or "was not provided" in text:
        return "fprintd ist nicht installiert oder läuft nicht."
    return text


class FprintdBackend(FingerprintBackend):
    name = "fprintd"
    can_enroll = True
    can_delete = True
    can_list_enrolled = True
    login_toggle = True

    def __init__(self):
        self._cancel = threading.Event()

    # ------------------------------------------------------------ Hilfen
    def _conn(self):
        return dbus_util.connect("SYSTEM")

    def _dev_call(self, conn, dev, method, sig="", args=(), timeout=30, interactive=False):
        return dbus_util.call(conn, FPRINT, dev, DEVICE_IFACE, method, sig, args,
                              timeout=timeout, interactive=interactive)

    def _claim(self, conn, dev):
        # Leerer Benutzername = aktueller Benutzer; evtl. Passwortabfrage (polkit)
        self._dev_call(conn, dev, "Claim", "s", ("",), timeout=120, interactive=True)

    def _release(self, conn, dev):
        try:
            self._dev_call(conn, dev, "Release")
        except Exception:  # noqa: BLE001
            pass

    def _signal_loop(self, conn, dev, member, start_method, start_arg, stop_method, handler):
        from jeepney import MatchRule, message_bus
        from jeepney.io.blocking import Proxy

        # Beim Bus mit Absender anmelden; lokal ohne Absender filtern, weil die
        # Nachrichten die eindeutige Bus-ID (":1.23") statt des Namens tragen
        bus_rule = MatchRule(type="signal", sender=FPRINT, interface=DEVICE_IFACE, member=member, path=dev)
        Proxy(message_bus, conn).AddMatch(bus_rule)
        local_rule = MatchRule(type="signal", interface=DEVICE_IFACE, member=member, path=dev)
        with conn.filter(local_rule) as queue:
            self._dev_call(conn, dev, start_method, "s", (start_arg,), timeout=120, interactive=True)
            try:
                while True:
                    if self._cancel.is_set():
                        raise Cancelled()
                    try:
                        msg = conn.recv_until_filtered(queue, timeout=0.5)
                    except TimeoutError:
                        continue
                    result, done = msg.body[0], bool(msg.body[1])
                    if handler(result, done):
                        return result
            finally:
                try:
                    self._dev_call(conn, dev, stop_method)
                except Exception:  # noqa: BLE001
                    pass

    # ------------------------------------------------------------ API
    def availability(self):
        if not dbus_util.HAVE_JEEPNEY:
            return (False, "Python-Paket 'jeepney' fehlt.")
        try:
            sensors = self.list_sensors()
        except Exception as exc:  # noqa: BLE001
            return (False, _friendly_error(exc))
        if not sensors:
            return (False, "Kein unterstützter Fingerabdrucksensor gefunden. "
                           "Nur Sensoren, die libfprint kennt, funktionieren unter Linux.")
        return (True, "")

    def list_sensors(self):
        with self._conn() as conn:
            (paths,) = dbus_util.call(conn, FPRINT, MANAGER_PATH, MANAGER_IFACE, "GetDevices")
            sensors = []
            for path in paths:
                try:
                    name = dbus_util.get_property(conn, FPRINT, path, DEVICE_IFACE, "name")
                    scan = dbus_util.get_property(conn, FPRINT, path, DEVICE_IFACE, "scan-type")
                except Exception:  # noqa: BLE001
                    name, scan = path.rsplit("/", 1)[-1], ""
                detail = "Wischen" if scan == "swipe" else "Auflegen"
                sensors.append(Sensor(id=path, name=str(name), detail=detail))
            return sensors

    def list_enrolled(self, sensor_id):
        import getpass

        with self._conn() as conn:
            try:
                (fingers,) = self._dev_call(conn, sensor_id, "ListEnrolledFingers", "s", (getpass.getuser(),))
            except Exception as exc:  # noqa: BLE001
                if "NoEnrolledPrints" in str(exc):
                    return []
                raise RuntimeError(_friendly_error(exc)) from exc
            return list(fingers)

    def enroll(self, sensor_id, finger, status):
        self._cancel.clear()
        with self._conn() as conn:
            try:
                total = int(dbus_util.get_property(conn, FPRINT, sensor_id, DEVICE_IFACE, "num-enroll-stages"))
            except Exception:  # noqa: BLE001
                total = 0
            stage = 0
            status("Passwort bestätigen, falls gefragt – dann Finger auflegen.", stage, total)
            try:
                self._claim(conn, sensor_id)
            except Exception as exc:  # noqa: BLE001
                raise RuntimeError(_friendly_error(exc)) from exc
            try:
                status("Finger auf den Sensor legen …", stage, total)

                def handler(result, done):
                    nonlocal stage
                    if result == "enroll-stage-passed":
                        stage += 1
                    if result == ENROLL_DONE_OK:
                        stage = total
                    status(ENROLL_TEXT.get(result, result), stage, total)
                    return done

                result = self._signal_loop(conn, sensor_id, "EnrollStatus", "EnrollStart", finger,
                                           "EnrollStop", handler)
                if result != ENROLL_DONE_OK:
                    raise RuntimeError(ENROLL_TEXT.get(result, result))
            except (Cancelled, RuntimeError):
                raise
            except Exception as exc:  # noqa: BLE001
                raise RuntimeError(_friendly_error(exc)) from exc
            finally:
                self._release(conn, sensor_id)

    def verify(self, sensor_id, status):
        self._cancel.clear()
        with self._conn() as conn:
            try:
                self._claim(conn, sensor_id)
            except Exception as exc:  # noqa: BLE001
                raise RuntimeError(_friendly_error(exc)) from exc
            try:
                status("Finger auf den Sensor legen …", 0, 0)

                def handler(result, done):
                    status(VERIFY_TEXT.get(result, result), 0, 0)
                    return done

                result = self._signal_loop(conn, sensor_id, "VerifyStatus", "VerifyStart", "any",
                                           "VerifyStop", handler)
                return (result == "verify-match", VERIFY_TEXT.get(result, result))
            except (Cancelled, RuntimeError):
                raise
            except Exception as exc:  # noqa: BLE001
                raise RuntimeError(_friendly_error(exc)) from exc
            finally:
                self._release(conn, sensor_id)

    def delete(self, sensor_id, finger):
        with self._conn() as conn:
            try:
                self._claim(conn, sensor_id)
            except Exception as exc:  # noqa: BLE001
                raise RuntimeError(_friendly_error(exc)) from exc
            try:
                if finger == "*":
                    self._dev_call(conn, sensor_id, "DeleteEnrolledFingers2", interactive=True)
                else:
                    self._dev_call(conn, sensor_id, "DeleteEnrolledFinger", "s", (finger,), interactive=True)
            except Exception as exc:  # noqa: BLE001
                if "UnknownMethod" in str(exc):
                    raise RuntimeError("Deine fprintd-Version kann nur alle Finger auf einmal löschen.") from exc
                raise RuntimeError(_friendly_error(exc)) from exc
            finally:
                self._release(conn, sensor_id)

    def cancel(self):
        self._cancel.set()

    # ------------------------------------------------------------ Anmeldung (PAM)
    def login_enabled(self):
        try:
            return "pam_fprintd.so" in PAM_FILE.read_text(encoding="utf-8")
        except OSError:
            return None

    def set_login_enabled(self, enabled):
        if not shutil.which("pam-auth-update"):
            raise RuntimeError("pam-auth-update nicht gefunden (kein Ubuntu/Kubuntu?).")
        if not Path("/usr/share/pam-configs/fprintd").exists():
            raise RuntimeError("Paket libpam-fprintd fehlt: sudo apt install libpam-fprintd")
        action = "--enable" if enabled else "--remove"
        proc = subprocess.run(
            ["pkexec", "env", "DEBIAN_FRONTEND=noninteractive", "pam-auth-update", action, "fprintd"],
            capture_output=True, text=True, timeout=300,
        )
        if proc.returncode != 0:
            raise RuntimeError((proc.stderr or proc.stdout or "Abgebrochen").strip())

    def install_hint(self):
        return "Tipp: „Automatisch einrichten“ installiert fehlende Pakete selbst."

    # ------------------------------------------------------------ Assistent
    @property
    def can_auto_install(self):
        return bool(shutil.which("apt-get") and shutil.which("pkexec"))

    def missing_packages(self):
        return [pkg for pkg in PACKAGES if not _package_installed(pkg)]

    def install_packages(self, packages):
        if not self.can_auto_install:
            raise RuntimeError("Automatisch installieren geht nur unter Ubuntu/Kubuntu. Bitte selbst installieren: "
                               + " ".join(packages))
        names = " ".join(p for p in packages if p in PACKAGES)  # nur bekannte Namen in die Befehlszeile
        script = f"apt-get update -q || true; apt-get install -y {names}"
        proc = subprocess.run(["pkexec", "env", "DEBIAN_FRONTEND=noninteractive", "sh", "-c", script],
                              capture_output=True, text=True, timeout=900)
        if proc.returncode == 126 or proc.returncode == 127:
            raise RuntimeError("Abgebrochen (Passwort nicht bestätigt).")
        if proc.returncode != 0:
            tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-3:]
            raise RuntimeError("Installation fehlgeschlagen: " + " ".join(tail))

    def detect_hardware(self):
        return detect_usb_sensors()
