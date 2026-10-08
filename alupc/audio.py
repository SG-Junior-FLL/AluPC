"""Ton des PCs: Lautsprecher und Mikrofon – genaue Lautstärke, stumm, Gerät wählen (Linux und Windows).

* Linux: pactl (PulseAudio/PipeWire). Geräte mit Namen, Standardgerät setzen.
* Windows: Core Audio (wie die Lautstärke-Regler von Windows) über comtypes; Standardgerät setzen über die
  Schnittstelle, die auch Windows' eigene Sound-Einstellungen benutzen (IPolicyConfig).
„kind“ ist immer "out" (Lautsprecher/Ausgabe) oder "in" (Mikrofon/Eingabe).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import threading
import time

IS_WINDOWS = sys.platform.startswith("win")
_CACHE: dict = {"t": 0.0, "state": None}


def _run(cmd: list[str], timeout: float = 6) -> tuple[int, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except (OSError, subprocess.SubprocessError) as exc:
        return 1, str(exc)


# --------------------------------------------------------------------------- Linux (pactl)
def _pa_kind(kind: str) -> str:
    return "sink" if kind == "out" else "source"


def _pa_devices(kind: str, run=_run) -> list[dict]:
    what = _pa_kind(kind)
    code, out = run(["pactl", "get-default-" + what])
    default = out.strip() if code == 0 else ""
    devices = []
    code, out = run(["pactl", "-f", "json", "list", what + "s"])
    try:
        items = json.loads(out) if code == 0 else None
    except ValueError:
        items = None
    if isinstance(items, list):
        for d in items:
            name = str(d.get("name", ""))
            if not name or name.endswith(".monitor") or d.get("monitor_of_sink") not in (None, "", "n/a"):
                continue  # „Monitor“ = Mitschnitt eines Lautsprechers, kein echtes Mikrofon
            devices.append({"id": name, "name": str(d.get("description") or name), "default": name == default})
        return devices
    code, out = run(["pactl", "list", "short", what + "s"])  # älteres pactl ohne JSON
    for line in out.splitlines() if code == 0 else []:
        parts = line.split("\t")
        if len(parts) >= 2 and not parts[1].endswith(".monitor"):
            devices.append({"id": parts[1], "name": parts[1], "default": parts[1] == default})
    return devices


def _pa_level(kind: str, run=_run) -> tuple[int | None, bool]:
    what = _pa_kind(kind)
    target = "@DEFAULT_SINK@" if kind == "out" else "@DEFAULT_SOURCE@"
    code, out = run(["pactl", f"get-{what}-volume", target])
    vol = None
    for part in out.split("/") if code == 0 else []:
        part = part.strip()
        if part.endswith("%"):
            try:
                vol = int(part.rstrip("%"))
                break
            except ValueError:
                pass
    code, out = run(["pactl", f"get-{what}-mute", target])
    return vol, code == 0 and "yes" in out.lower()


# --------------------------------------------------------------------------- Windows (Core Audio)
_LOCAL = threading.local()  # COM-Objekte gelten nur im Thread, der sie angelegt hat


def _win():
    """Core-Audio-Schnittstellen (je Thread einmal aufgebaut). Fehler, wenn comtypes fehlt."""
    if getattr(_LOCAL, "win", None) is not None:
        return _LOCAL.win
    import ctypes
    from ctypes import POINTER, Structure, c_float, c_uint, c_ushort, c_void_p, c_wchar_p
    from ctypes.wintypes import BOOL, DWORD, LPCWSTR

    import comtypes
    from comtypes import COMMETHOD, GUID, HRESULT, IUnknown

    class PROPERTYKEY(Structure):
        _fields_ = [("fmtid", GUID), ("pid", DWORD)]

    class PROPVARIANT(Structure):
        _fields_ = [("vt", c_ushort), ("r1", c_ushort), ("r2", c_ushort), ("r3", c_ushort),
                    ("val", c_void_p), ("pad", c_void_p)]

    class IAudioEndpointVolume(IUnknown):
        _iid_ = GUID("{5CDF2C82-841E-4546-9722-0CF74078229A}")
        _methods_ = [
            COMMETHOD([], HRESULT, "RegisterControlChangeNotify", (["in"], c_void_p)),
            COMMETHOD([], HRESULT, "UnregisterControlChangeNotify", (["in"], c_void_p)),
            COMMETHOD([], HRESULT, "GetChannelCount", (["out"], POINTER(c_uint))),
            COMMETHOD([], HRESULT, "SetMasterVolumeLevel", (["in"], c_float), (["in"], POINTER(GUID))),
            COMMETHOD([], HRESULT, "SetMasterVolumeLevelScalar", (["in"], c_float), (["in"], POINTER(GUID))),
            COMMETHOD([], HRESULT, "GetMasterVolumeLevel", (["out"], POINTER(c_float))),
            COMMETHOD([], HRESULT, "GetMasterVolumeLevelScalar", (["out"], POINTER(c_float))),
            COMMETHOD([], HRESULT, "SetChannelVolumeLevel", (["in"], c_uint), (["in"], c_float), (["in"], POINTER(GUID))),
            COMMETHOD([], HRESULT, "SetChannelVolumeLevelScalar", (["in"], c_uint), (["in"], c_float),
                      (["in"], POINTER(GUID))),
            COMMETHOD([], HRESULT, "GetChannelVolumeLevel", (["in"], c_uint), (["out"], POINTER(c_float))),
            COMMETHOD([], HRESULT, "GetChannelVolumeLevelScalar", (["in"], c_uint), (["out"], POINTER(c_float))),
            COMMETHOD([], HRESULT, "SetMute", (["in"], BOOL), (["in"], POINTER(GUID))),
            COMMETHOD([], HRESULT, "GetMute", (["out"], POINTER(BOOL))),
        ]

    class IPropertyStore(IUnknown):
        _iid_ = GUID("{886d8eeb-8cf2-4446-8d02-cdba1dbdcf99}")
        _methods_ = [
            COMMETHOD([], HRESULT, "GetCount", (["out"], POINTER(DWORD))),
            COMMETHOD([], HRESULT, "GetAt", (["in"], DWORD), (["out"], POINTER(PROPERTYKEY))),
            COMMETHOD([], HRESULT, "GetValue", (["in"], POINTER(PROPERTYKEY)), (["out"], POINTER(PROPVARIANT))),
        ]

    class IMMDevice(IUnknown):
        _iid_ = GUID("{D666063F-1587-4E43-81F1-B948E807363F}")
        _methods_ = [
            COMMETHOD([], HRESULT, "Activate", (["in"], POINTER(GUID)), (["in"], DWORD), (["in"], c_void_p),
                      (["out"], POINTER(POINTER(IUnknown)))),
            COMMETHOD([], HRESULT, "OpenPropertyStore", (["in"], DWORD), (["out"], POINTER(POINTER(IPropertyStore)))),
            COMMETHOD([], HRESULT, "GetId", (["out"], POINTER(c_wchar_p))),
            COMMETHOD([], HRESULT, "GetState", (["out"], POINTER(DWORD))),
        ]

    class IMMDeviceCollection(IUnknown):
        _iid_ = GUID("{0BD7A1BE-7A1A-44DB-8397-CC5392387B5E}")
        _methods_ = [
            COMMETHOD([], HRESULT, "GetCount", (["out"], POINTER(c_uint))),
            COMMETHOD([], HRESULT, "Item", (["in"], c_uint), (["out"], POINTER(POINTER(IMMDevice)))),
        ]

    class IMMDeviceEnumerator(IUnknown):
        _iid_ = GUID("{A95664D2-9614-4F35-A746-DE8DB63617E6}")
        _methods_ = [
            COMMETHOD([], HRESULT, "EnumAudioEndpoints", (["in"], DWORD), (["in"], DWORD),
                      (["out"], POINTER(POINTER(IMMDeviceCollection)))),
            COMMETHOD([], HRESULT, "GetDefaultAudioEndpoint", (["in"], DWORD), (["in"], DWORD),
                      (["out"], POINTER(POINTER(IMMDevice)))),
            COMMETHOD([], HRESULT, "GetDevice", (["in"], LPCWSTR), (["out"], POINTER(POINTER(IMMDevice)))),
        ]

    class IPolicyConfig(IUnknown):  # nicht offiziell dokumentiert – so setzen auch die Sound-Einstellungen
        _iid_ = GUID("{f8679f50-850a-41cf-9c72-430f290290c8}")
        _methods_ = [COMMETHOD([], HRESULT, name) for name in (
            "GetMixFormat", "GetDeviceFormat", "ResetDeviceFormat", "SetDeviceFormat", "GetProcessingPeriod",
            "SetProcessingPeriod", "GetShareMode", "SetShareMode", "GetPropertyValue", "SetPropertyValue")] + [
            COMMETHOD([], HRESULT, "SetDefaultEndpoint", (["in"], LPCWSTR), (["in"], DWORD)),
        ]

    comtypes.CoInitialize()
    enum = comtypes.CoCreateInstance(GUID("{BCDE0395-E52F-467C-8E3D-C4579291692E}"), IMMDeviceEnumerator,
                                     comtypes.CLSCTX_ALL)
    name_key = PROPERTYKEY(GUID("{a45c254e-df1c-4efd-8020-67d146a850e0}"), 14)
    ole32 = ctypes.windll.ole32

    def friendly(dev) -> str:
        try:
            store = dev.OpenPropertyStore(0)
            pv = store.GetValue(ctypes.byref(name_key))
            text = ctypes.wstring_at(pv.val) if pv.vt == 31 and pv.val else ""
            ole32.PropVariantClear(ctypes.byref(pv))
            return text
        except (OSError, comtypes.COMError):
            return ""

    def volume(dev):
        unk = dev.Activate(IAudioEndpointVolume._iid_, comtypes.CLSCTX_ALL, None)
        return unk.QueryInterface(IAudioEndpointVolume)

    def set_default(dev_id: str) -> None:
        pc = comtypes.CoCreateInstance(GUID("{870af99c-171d-4f9e-af0d-e63df40c2bc9}"), IPolicyConfig,
                                       comtypes.CLSCTX_ALL)
        for role in (0, 1, 2):  # Konsole, Multimedia, Kommunikation
            pc.SetDefaultEndpoint(dev_id, role)

    _LOCAL.win = {"enum": enum, "friendly": friendly, "volume": volume, "set_default": set_default,
                  "COMError": comtypes.COMError}
    return _LOCAL.win


def _flow(kind: str) -> int:
    return 0 if kind == "out" else 1  # eRender / eCapture


def _win_default(kind: str):
    return _win()["enum"].GetDefaultAudioEndpoint(_flow(kind), 0)


def _win_devices(kind: str) -> list[dict]:
    w = _win()
    try:
        default_id = _win_default(kind).GetId()
    except (OSError, w["COMError"]):
        default_id = ""
    coll = w["enum"].EnumAudioEndpoints(_flow(kind), 1)  # nur aktive
    out = []
    for i in range(coll.GetCount()):
        dev = coll.Item(i)
        dev_id = dev.GetId()
        out.append({"id": dev_id, "name": w["friendly"](dev) or dev_id, "default": dev_id == default_id})
    return out


def _win_level(kind: str) -> tuple[int | None, bool]:
    vol = _win()["volume"](_win_default(kind))
    return round(vol.GetMasterVolumeLevelScalar() * 100), bool(vol.GetMute())


# --------------------------------------------------------------------------- gemeinsam
def available() -> bool:
    if IS_WINDOWS:
        try:
            _win()
            return True
        except Exception:  # noqa: BLE001 - comtypes fehlt / kein Audio-Dienst
            return False
    return shutil.which("pactl") is not None


def devices(kind: str) -> list[dict]:
    """[{id, name, default}] – nur aktive Geräte."""
    try:
        return _win_devices(kind) if IS_WINDOWS else _pa_devices(kind)
    except Exception:  # noqa: BLE001
        return []


def level(kind: str) -> tuple[int | None, bool]:
    """(Lautstärke 0–100 oder None, stumm)."""
    try:
        return _win_level(kind) if IS_WINDOWS else _pa_level(kind)
    except Exception:  # noqa: BLE001
        return None, False


def set_level(kind: str, percent: int) -> tuple[bool, str]:
    percent = max(0, min(100, int(percent)))
    _CACHE["t"] = 0
    try:
        if IS_WINDOWS:
            vol = _win()["volume"](_win_default(kind))
            vol.SetMasterVolumeLevelScalar(percent / 100, None)
            vol.SetMute(False, None)
            return True, ""
        what, target = _pa_kind(kind), ("@DEFAULT_SINK@" if kind == "out" else "@DEFAULT_SOURCE@")
        code, out = _run(["pactl", f"set-{what}-volume", target, f"{percent}%"])
        if code == 0:
            _run(["pactl", f"set-{what}-mute", target, "0"])
        return code == 0, out.strip()
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def set_mute(kind: str, on: bool) -> tuple[bool, str]:
    _CACHE["t"] = 0
    try:
        if IS_WINDOWS:
            _win()["volume"](_win_default(kind)).SetMute(bool(on), None)
            return True, ""
        what, target = _pa_kind(kind), ("@DEFAULT_SINK@" if kind == "out" else "@DEFAULT_SOURCE@")
        code, out = _run(["pactl", f"set-{what}-mute", target, "1" if on else "0"])
        return code == 0, out.strip()
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def set_default(kind: str, dev_id: str) -> tuple[bool, str]:
    _CACHE["t"] = 0
    try:
        if IS_WINDOWS:
            _win()["set_default"](dev_id)
            return True, ""
        code, out = _run(["pactl", "set-default-" + _pa_kind(kind), dev_id])
        return code == 0, out.strip()
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def state(max_age: float = 2.0) -> dict | None:
    """Alles auf einmal (fürs Handy, höchstens alle 2 s neu gelesen):
    {"out": {"vol", "muted", "devices"}, "in": {...}} – None, wenn hier nichts geht."""
    now = time.monotonic()
    if _CACHE["state"] is not None and now - _CACHE["t"] < max_age:
        return _CACHE["state"]
    if not available():
        return None
    result = {}
    for kind in ("out", "in"):
        vol, muted = level(kind)
        result[kind] = {"vol": vol, "muted": muted, "devices": devices(kind)}
    _CACHE.update(t=now, state=result)
    return result


def run(cmd: str) -> str:
    """Befehle (Handy/Sprache): ton_laut:N, ton_stumm:0|1, ton_geraet:i, mic_laut:N, mic_stumm:0|1, mic_geraet:i."""
    name, _, arg = cmd.partition(":")
    kind = "out" if name.startswith("ton_") else "in"
    what = "Lautsprecher" if kind == "out" else "Mikrofon"
    try:
        if name.endswith("_laut"):
            ok, why = set_level(kind, int(arg))
            return f"{what} {int(arg)} %." if ok else f"{what}: {why or 'geht nicht'}"
        if name.endswith("_stumm"):
            on = arg == "1"
            ok, why = set_mute(kind, on)
            return (f"{what} stumm." if on else f"{what} wieder an.") if ok else f"{what}: {why or 'geht nicht'}"
        if name.endswith("_geraet"):
            devs = devices(kind)
            i = int(arg)
            if not 0 <= i < len(devs):
                return f"{what}: Gerät nicht gefunden."
            ok, why = set_default(kind, devs[i]["id"])
            return f"{what}: {devs[i]['name']}." if ok else f"{what}: {why or 'geht nicht'}"
    except ValueError:
        pass
    return "Unbekannter Ton-Befehl."
