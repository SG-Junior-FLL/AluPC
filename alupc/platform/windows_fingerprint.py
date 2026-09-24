"""Fingerabdruck unter Windows 11 über das Windows Biometric Framework (winbio.dll).

Wichtig: Windows erlaubt Fremdprogrammen NICHT, Finger für die Windows-Anmeldung
anzulernen. Das passiert über Windows Hello in den Einstellungen – AluPC öffnet
diesen Dialog direkt. Sensoren anzeigen, angelernte Finger anzeigen und einen
Test-Scan macht AluPC selbst.
"""

from __future__ import annotations

import ctypes
import os
import threading

from .base import Cancelled, FingerprintBackend, Sensor

WINBIO_TYPE_FINGERPRINT = 0x00000008
WINBIO_POOL_SYSTEM = 1
WINBIO_FLAG_DEFAULT = 0
WINBIO_ID_TYPE_SID = 3
SECURITY_MAX_SID_SIZE = 68

WCHAR = ctypes.c_wchar
ULONG = ctypes.c_uint32
HRESULT_OK = 0

# Positionen nach ANSI 381 (WINBIO_ANSI_381_POS_*)
SUBFACTOR_TO_FINGER = {
    1: "right-thumb", 2: "right-index-finger", 3: "right-middle-finger",
    4: "right-ring-finger", 5: "right-little-finger",
    6: "left-thumb", 7: "left-index-finger", 8: "left-middle-finger",
    9: "left-ring-finger", 10: "left-little-finger",
}

WINBIO_ERRORS = {
    0x80098003: "Fingerabdruck nicht erkannt.",
    0x80098004: "Abgebrochen.",
    0x80098005: "Fingerabdruck passt nicht.",
    0x80098008: "Scan war schlecht – bitte noch einmal.",
    0x80070005: "Zugriff verweigert. Bei aktiver „Erweiterter Anmeldesicherheit“ (ESS) "
                "sperrt Windows den Sensor für andere Programme.",
}


class WINBIO_VERSION(ctypes.Structure):
    _fields_ = [("MajorVersion", ULONG), ("MinorVersion", ULONG)]


class WINBIO_UNIT_SCHEMA(ctypes.Structure):
    _fields_ = [
        ("UnitId", ULONG),
        ("PoolType", ULONG),
        ("BiometricFactor", ULONG),
        ("SensorSubType", ULONG),
        ("Capabilities", ULONG),
        ("DeviceInstanceId", WCHAR * 256),
        ("Description", WCHAR * 256),
        ("Manufacturer", WCHAR * 256),
        ("Model", WCHAR * 256),
        ("SerialNumber", WCHAR * 256),
        ("FirmwareVersion", WINBIO_VERSION),
    ]


class _AccountSid(ctypes.Structure):
    _fields_ = [("Size", ULONG), ("Data", ctypes.c_ubyte * SECURITY_MAX_SID_SIZE)]


class _IdentityValue(ctypes.Union):
    _fields_ = [("Null", ULONG), ("Wildcard", ULONG), ("TemplateGuid", ctypes.c_ubyte * 16),
                ("AccountSid", _AccountSid)]


class WINBIO_IDENTITY(ctypes.Structure):
    _fields_ = [("Type", ULONG), ("Value", _IdentityValue)]


def _hr(code: int) -> int:
    return code & 0xFFFFFFFF


def _error_text(code: int) -> str:
    code = _hr(code)
    return WINBIO_ERRORS.get(code, f"Windows-Fehler 0x{code:08X}")


def current_user_identity() -> WINBIO_IDENTITY:
    """WINBIO_IDENTITY mit der SID des angemeldeten Benutzers."""
    from ctypes import wintypes

    advapi32 = ctypes.windll.advapi32  # type: ignore[attr-defined]
    kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    advapi32.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
    advapi32.GetTokenInformation.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p,
                                             wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    advapi32.GetLengthSid.argtypes = [ctypes.c_void_p]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

    token = wintypes.HANDLE()
    if not advapi32.OpenProcessToken(kernel32.GetCurrentProcess(), 0x0008, ctypes.byref(token)):
        raise OSError("OpenProcessToken fehlgeschlagen")
    try:
        needed = wintypes.DWORD()
        advapi32.GetTokenInformation(token, 1, None, 0, ctypes.byref(needed))
        buf = ctypes.create_string_buffer(needed.value)
        if not advapi32.GetTokenInformation(token, 1, buf, needed, ctypes.byref(needed)):
            raise OSError("GetTokenInformation fehlgeschlagen")
        sid_ptr = ctypes.c_void_p.from_buffer(buf).value  # TOKEN_USER.User.Sid
        length = advapi32.GetLengthSid(sid_ptr)
        identity = WINBIO_IDENTITY()
        identity.Type = WINBIO_ID_TYPE_SID
        identity.Value.AccountSid.Size = length
        ctypes.memmove(identity.Value.AccountSid.Data, sid_ptr, length)
        return identity
    finally:
        kernel32.CloseHandle(token)


def same_sid(a: WINBIO_IDENTITY, b: WINBIO_IDENTITY) -> bool:
    if a.Type != WINBIO_ID_TYPE_SID or b.Type != WINBIO_ID_TYPE_SID:
        return False
    sa, sb = a.Value.AccountSid, b.Value.AccountSid
    return sa.Size == sb.Size and bytes(sa.Data[: sa.Size]) == bytes(sb.Data[: sb.Size])


class WinBioBackend(FingerprintBackend):
    name = "Windows Hello"
    can_enroll = False
    can_delete = False
    can_list_enrolled = True
    login_toggle = False

    def __init__(self):
        self._session = None
        self._lock = threading.Lock()
        self._cancelled = False
        self.winbio = ctypes.windll.winbio  # type: ignore[attr-defined]
        w = self.winbio
        w.WinBioEnumBiometricUnits.argtypes = [ULONG, ctypes.POINTER(ctypes.POINTER(WINBIO_UNIT_SCHEMA)),
                                               ctypes.POINTER(ctypes.c_size_t)]
        w.WinBioOpenSession.argtypes = [ULONG, ULONG, ULONG, ctypes.c_void_p, ctypes.c_size_t,
                                        ctypes.c_void_p, ctypes.POINTER(ULONG)]
        w.WinBioIdentify.argtypes = [ULONG, ctypes.POINTER(ULONG), ctypes.POINTER(WINBIO_IDENTITY),
                                     ctypes.POINTER(ctypes.c_ubyte), ctypes.POINTER(ULONG)]
        w.WinBioEnumEnrollments.argtypes = [ULONG, ULONG, ctypes.POINTER(WINBIO_IDENTITY),
                                            ctypes.POINTER(ctypes.POINTER(ctypes.c_ubyte)),
                                            ctypes.POINTER(ctypes.c_size_t)]
        w.WinBioCancel.argtypes = [ULONG]
        w.WinBioCloseSession.argtypes = [ULONG]
        w.WinBioFree.argtypes = [ctypes.c_void_p]
        for fn in ("WinBioEnumBiometricUnits", "WinBioOpenSession", "WinBioIdentify",
                   "WinBioEnumEnrollments", "WinBioCancel", "WinBioCloseSession", "WinBioFree"):
            getattr(w, fn).restype = ctypes.c_long

    def _open(self) -> int:
        session = ULONG()
        # DatabaseId = WINBIO_DB_DEFAULT ((GUID*)1)
        hr = self.winbio.WinBioOpenSession(WINBIO_TYPE_FINGERPRINT, WINBIO_POOL_SYSTEM, WINBIO_FLAG_DEFAULT,
                                           None, 0, ctypes.c_void_p(1), ctypes.byref(session))
        if hr != HRESULT_OK:
            raise RuntimeError(_error_text(hr))
        return session.value

    def _close(self, session: int) -> None:
        self.winbio.WinBioCloseSession(session)

    def availability(self):
        try:
            sensors = self.list_sensors()
        except Exception as exc:  # noqa: BLE001
            return (False, str(exc))
        if not sensors:
            return (False, "Kein Fingerabdrucksensor gefunden (Windows Hello). Steckt ein USB-Leser, fehlt meist "
                           "nur der Treiber: Einstellungen → Windows Update → Erweiterte Optionen → Optionale "
                           "Updates → Treiberupdates, dort den Fingerabdruck-Treiber installieren und neu starten.")
        return (True, "")

    def list_sensors(self):
        array = ctypes.POINTER(WINBIO_UNIT_SCHEMA)()
        count = ctypes.c_size_t()
        hr = self.winbio.WinBioEnumBiometricUnits(WINBIO_TYPE_FINGERPRINT, ctypes.byref(array), ctypes.byref(count))
        if hr != HRESULT_OK:
            raise RuntimeError(_error_text(hr))
        sensors = []
        try:
            for i in range(count.value):
                unit = array[i]
                name = unit.Description or unit.Model or f"Sensor {unit.UnitId}"
                detail = " ".join(x for x in (unit.Manufacturer, unit.Model) if x)
                sensors.append(Sensor(id=str(unit.UnitId), name=name, detail=detail))
        finally:
            if array:
                self.winbio.WinBioFree(array)
        return sensors

    def list_enrolled(self, sensor_id):
        session = self._open()
        try:
            identity = current_user_identity()
            factors = ctypes.POINTER(ctypes.c_ubyte)()
            count = ctypes.c_size_t()
            hr = self.winbio.WinBioEnumEnrollments(session, int(sensor_id), ctypes.byref(identity),
                                                   ctypes.byref(factors), ctypes.byref(count))
            if _hr(hr) in (0x80098003,):  # unbekannter Benutzer = keine Finger
                return []
            if hr != HRESULT_OK:
                raise RuntimeError(_error_text(hr))
            try:
                return [SUBFACTOR_TO_FINGER.get(factors[i], f"finger-{factors[i]}") for i in range(count.value)]
            finally:
                if factors:
                    self.winbio.WinBioFree(factors)
        finally:
            self._close(session)

    def verify(self, sensor_id, status):
        with self._lock:
            self._cancelled = False
            self._session = self._open()
        try:
            status("Finger auf den Sensor legen …", 0, 0)
            unit = ULONG()
            identity = WINBIO_IDENTITY()
            subfactor = ctypes.c_ubyte()
            reject = ULONG()
            hr = self.winbio.WinBioIdentify(self._session, ctypes.byref(unit), ctypes.byref(identity),
                                            ctypes.byref(subfactor), ctypes.byref(reject))
            if self._cancelled or _hr(hr) == 0x80098004:
                raise Cancelled()
            if hr != HRESULT_OK:
                return (False, _error_text(hr))
            if not same_sid(identity, current_user_identity()):
                return (False, "Finger gehört zu einem anderen Windows-Benutzer.")
            finger = SUBFACTOR_TO_FINGER.get(subfactor.value, "")
            from .base import FINGER_NAMES

            label = FINGER_NAMES.get(finger, "Finger")
            return (True, f"Erkannt – {label}.")
        finally:
            with self._lock:
                self._close(self._session)
                self._session = None

    def cancel(self):
        with self._lock:
            self._cancelled = True
            if self._session is not None:
                self.winbio.WinBioCancel(self._session)

    def open_system_settings(self):
        try:
            os.startfile("ms-settings:signinoptions-launchfingerprintenrollment")  # type: ignore[attr-defined]
        except OSError:
            os.startfile("ms-settings:signinoptions")  # type: ignore[attr-defined]

    def install_hint(self):
        return "Windows-Einstellungen → Konten → Anmeldeoptionen → Fingerabdruckerkennung (Windows Hello)"
