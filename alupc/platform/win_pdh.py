"""Windows-Leistungsindikatoren (PDH) – dieselben Zahlen wie im Task-Manager.

- Prozessor: „% Processor Utility“ (so rechnet der Task-Manager seit Windows 8; berücksichtigt Turbo-Takt,
  deshalb höher als die klassische „% Processor Time“, die psutil liefert).
- Grafikkarte: „GPU Engine(*)\\Utilization Percentage“ – für jede Engine-Art (3D, Copy, VideoDecode …) die
  Summe über alle Programme, davon das Maximum (so zeigt es der Task-Manager), dazu „GPU Adapter Memory“.
Nur Windows; überall sonst liefert available() False.
"""

from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes

PDH_FMT_DOUBLE = 0x00000200
PDH_FMT_LARGE = 0x00000400
PDH_FMT_NOCAP100 = 0x00008000
PDH_MORE_DATA = 0x800007D2
ERROR_SUCCESS = 0

CPU_TOTAL = r"\Processor Information(_Total)\% Processor Utility"
CPU_CORES = r"\Processor Information(*)\% Processor Utility"
CPU_PERF = r"\Processor Information(_Total)\% Processor Performance"  # aktueller Takt in % des Basistakts
GPU_ENGINES = r"\GPU Engine(*)\Utilization Percentage"
GPU_DEDICATED = r"\GPU Adapter Memory(*)\Dedicated Usage"


class _Value(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [("longValue", ctypes.c_long), ("doubleValue", ctypes.c_double),
                    ("largeValue", ctypes.c_longlong), ("AnsiStringValue", ctypes.c_char_p),
                    ("WideStringValue", ctypes.c_wchar_p)]

    _fields_ = [("CStatus", wintypes.DWORD), ("u", _U)]


class _Item(ctypes.Structure):
    _fields_ = [("szName", ctypes.c_wchar_p), ("FmtValue", _Value)]


def available() -> bool:
    return sys.platform == "win32"


def engine_load(rows: list[tuple[str, float]]) -> float:
    """GPU-Engine-Zeilen („pid_12_luid_0x…_phys_0_eng_0_engtype_3D“, Wert) → Auslastung wie im Task-Manager."""
    per_type: dict[str, float] = {}
    for name, value in rows:
        kind = name.rsplit("engtype_", 1)[-1] if "engtype_" in name else "?"
        per_type[kind] = per_type.get(kind, 0.0) + max(0.0, value)
    return min(100.0, max(per_type.values(), default=0.0))


class Pdh:
    """Eine PDH-Abfrage mit Prozessor- und (falls vorhanden) Grafikkarten-Zählern. Werte gibt es ab dem 2. collect()."""

    def __init__(self):
        self.dll = ctypes.WinDLL("pdh.dll")
        self.query = wintypes.HANDLE()
        if self.dll.PdhOpenQueryW(None, None, ctypes.byref(self.query)) != ERROR_SUCCESS:
            raise OSError("PdhOpenQuery fehlgeschlagen")
        self.counters: dict[str, wintypes.HANDLE] = {}
        for key, path in (("cpu", CPU_TOTAL), ("cores", CPU_CORES), ("perf", CPU_PERF), ("gpu", GPU_ENGINES),
                          ("vram", GPU_DEDICATED)):
            h = wintypes.HANDLE()
            if self.dll.PdhAddEnglishCounterW(self.query, path, None, ctypes.byref(h)) == ERROR_SUCCESS:
                self.counters[key] = h
        self.collect()

    def collect(self) -> None:
        self.dll.PdhCollectQueryData(self.query)

    def value(self, key: str, fmt: int = PDH_FMT_DOUBLE | PDH_FMT_NOCAP100) -> float | None:
        h = self.counters.get(key)
        if h is None:
            return None
        v = _Value()
        if self.dll.PdhGetFormattedCounterValue(h, fmt, None, ctypes.byref(v)) != ERROR_SUCCESS or v.CStatus > 1:
            return None
        return v.u.largeValue if fmt & PDH_FMT_LARGE else v.u.doubleValue

    def array(self, key: str, fmt: int = PDH_FMT_DOUBLE | PDH_FMT_NOCAP100) -> list[tuple[str, float]]:
        h = self.counters.get(key)
        if h is None:
            return []
        size, count = wintypes.DWORD(0), wintypes.DWORD(0)
        rc = self.dll.PdhGetFormattedCounterArrayW(h, fmt, ctypes.byref(size), ctypes.byref(count), None)
        rc &= 0xFFFFFFFF  # ctypes liefert int mit Vorzeichen – PDH_MORE_DATA (0x800007D2) wäre sonst negativ
        if rc not in (PDH_MORE_DATA, ERROR_SUCCESS) or size.value == 0:
            return []
        buf = (ctypes.c_byte * size.value)()
        rc = self.dll.PdhGetFormattedCounterArrayW(h, fmt, ctypes.byref(size), ctypes.byref(count), buf)
        if rc != ERROR_SUCCESS:
            return []
        items = ctypes.cast(buf, ctypes.POINTER(_Item))
        out = []
        for i in range(count.value):
            it = items[i]
            if it.FmtValue.CStatus <= 1:
                val = it.FmtValue.u.largeValue if fmt & PDH_FMT_LARGE else it.FmtValue.u.doubleValue
                out.append((it.szName or "", float(val)))
        return out

    # ------------------------------------------------------------ Messwerte
    def cpu(self) -> tuple[float | None, list[float]]:
        total = self.value("cpu")
        cores = []
        for name, val in self.array("cores"):
            if "_Total" in name:
                continue
            cores.append((name, min(100.0, max(0.0, val))))

        def order(item):  # „0,10“ → (0, 10)
            try:
                return tuple(int(x) for x in item[0].split(","))
            except ValueError:
                return (99, 99)

        cores.sort(key=order)
        return (None if total is None else min(100.0, max(0.0, total))), [v for _n, v in cores]

    def gpu(self) -> tuple[float | None, float | None]:
        """(Auslastung %, belegter Grafikspeicher in MiB) – None, wenn Windows keine GPU-Zähler hat."""
        if "gpu" not in self.counters:
            return None, None
        rows = self.array("gpu")
        load = engine_load(rows) if rows else None
        vram = None
        mem = self.array("vram", PDH_FMT_LARGE)
        if mem:
            vram = max(v for _n, v in mem) / 2**20
        return load, vram

    def close(self) -> None:
        try:
            self.dll.PdhCloseQuery(self.query)
        except OSError:
            pass


def gpu_name_and_memory() -> tuple[str, float | None]:
    """Name und Grafikspeicher (MiB) der ersten echten Grafikkarte aus der Registry."""
    import winreg

    base = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"
    best = ("", None)
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base) as cls:
            for i in range(32):
                try:
                    sub = winreg.EnumKey(cls, i)
                except OSError:
                    break
                if not sub.isdigit():
                    continue
                try:
                    with winreg.OpenKey(cls, sub) as k:
                        name = winreg.QueryValueEx(k, "DriverDesc")[0]
                        mem = None
                        for value in ("HardwareInformation.qwMemorySize", "HardwareInformation.MemorySize"):
                            try:
                                raw = winreg.QueryValueEx(k, value)[0]
                                mem = (int.from_bytes(raw, "little") if isinstance(raw, bytes) else int(raw)) / 2**20
                                break
                            except OSError:
                                continue
                except OSError:
                    continue
                if "basic" in name.lower() or "remote" in name.lower() or "hyper-v" in name.lower():
                    continue
                if mem and (best[1] or 0) < mem:
                    best = (name, mem)
                elif not best[0]:
                    best = (name, mem)
    except OSError:
        pass
    return best
