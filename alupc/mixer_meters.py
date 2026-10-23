"""Pegel für das Mischpult (Seite „Audio“): je Ausgang, Eingang und Programm – nur solange die Seite offen ist.

* Linux: je Kanal ein kleiner `parec` (8 kHz, mono) – Ausgänge über ihren „.monitor“, Programme mit
  --monitor-stream (wie pavucontrol). Die Messungen heißen „alupc-pegel“ und tauchen in den Listen nicht auf.
* Windows: Core Audio IAudioMeterInformation für Geräte und Programm-Sitzungen (alle 80 ms abgefragt).
"""

from __future__ import annotations

import shutil
import subprocess
import threading
import time
from array import array

from .audio import IS_WINDOWS

METER_APP = "alupc-pegel"
DEFAULT_OUT = "@default"  # Geräte-ID für „der aktuelle Standard-Ausgang“ (Pegel im Live-Dock)


class _Parec:
    def __init__(self, args: list[str]):
        self.peak = 0.0
        self.at = 0.0  # letzte Daten (ruhende Ausgänge liefern gar nichts → Pegel 0)
        self._stop = False
        self.proc = subprocess.Popen(
            ["parec", *args, "--raw", "--format=s16le", "--rate=8000", "--channels=1", "--latency-msec=40",
             f"--property=application.name={METER_APP}"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        threading.Thread(target=self._read, name="alupc-pegel", daemon=True).start()

    def _read(self):
        out = self.proc.stdout
        while not self._stop:
            data = out.read(320)  # 20 ms
            if not data:
                break
            samples = array("h")
            samples.frombytes(data[: len(data) // 2 * 2])
            if samples:
                self.peak = max(max(samples), -min(samples)) / 32768
                self.at = time.monotonic()

    def close(self):
        self._stop = True
        try:
            self.proc.terminate()
        except OSError:
            pass


class Meters:
    """Kanäle: [{"key", "kind": "out"/"in", "dev": Geräte-ID, "stream": Programm-ID oder None, "sink": Ziel}]."""

    def __init__(self):
        self._procs: dict[str, _Parec] = {}
        self._peaks: dict[str, float] = {}
        self._specs: dict[str, dict] = {}
        self._win_thread = None
        self._running = False

    def set_channels(self, specs: list[dict]) -> None:
        self._specs = {s["key"]: s for s in specs}
        if IS_WINDOWS:
            if not self._running:
                self._running = True
                self._win_thread = threading.Thread(target=self._win_loop, name="alupc-pegel", daemon=True)
                self._win_thread.start()
            return
        if not shutil.which("parec"):
            return
        for key in [k for k in self._procs if k not in self._specs]:
            self._procs.pop(key).close()
        for key, s in self._specs.items():
            if key in self._procs:
                continue
            if s.get("stream") is not None:  # Programm: nur seinen Ton (am Ausgang, auf dem es läuft)
                if not s.get("sink"):
                    continue
                args = ["-d", s["sink"] + ".monitor", f"--monitor-stream={s['stream']}"]
            elif s["kind"] == "out":
                dev = "@DEFAULT_SINK@" if s["dev"] == DEFAULT_OUT else s["dev"]
                args = ["-d", dev + ".monitor"]
            else:
                args = ["-d", s["dev"]]
            try:
                self._procs[key] = _Parec(args)
            except OSError:
                pass

    def peak(self, key: str) -> float:
        if IS_WINDOWS:
            return self._peaks.get(key, 0.0)
        p = self._procs.get(key)
        return p.peak if p is not None and time.monotonic() - p.at < 0.4 else 0.0

    def _win_loop(self) -> None:
        from .audio import _on_com

        while self._running:
            try:
                self._peaks = _on_com(_win_peaks, list(self._specs.values()), timeout=2)
            except Exception:  # noqa: BLE001
                pass
            time.sleep(0.12)

    def stop(self) -> None:
        self._running = False
        for p in self._procs.values():
            p.close()
        self._procs.clear()
        self._peaks = {}


def _win_meter_api():
    from . import audio

    cache = getattr(audio._LOCAL, "meter", None)
    if cache is not None:
        return cache
    from ctypes import POINTER, c_float, c_uint

    from comtypes import COMMETHOD, GUID, HRESULT, IUnknown

    class IAudioMeterInformation(IUnknown):
        _iid_ = GUID("{C02216F6-8C67-4B5B-9D00-D008E73E0064}")
        _methods_ = [
            COMMETHOD([], HRESULT, "GetPeakValue", (["out"], POINTER(c_float))),
            COMMETHOD([], HRESULT, "GetMeteringChannelCount", (["out"], POINTER(c_uint))),
            COMMETHOD([], HRESULT, "GetChannelsPeakValues"),
            COMMETHOD([], HRESULT, "QueryHardwareSupport"),
        ]

    audio._LOCAL.meter = IAudioMeterInformation
    return IAudioMeterInformation


def _win_peaks(specs: list[dict]) -> dict[str, float]:
    """Pegel aller Kanäle. Die Messfühler (COM-Objekte) werden zwischengespeichert und nur alle 2 s (oder nach
    einem Fehler) neu gesucht – vorher wurden bei jeder Abfrage alle Geräte und Sitzungen neu aufgezählt, das
    hielt den Ton-Hilfsprozess dauernd beschäftigt (Lautstärke vom Regler musste warten → Ruckeln)."""
    import comtypes

    from . import audio

    cache = getattr(audio._LOCAL, "meter_cache", None)
    keys = tuple(sorted((s["key"], s["dev"], str(s.get("stream"))) for s in specs))
    if cache is None or cache["keys"] != keys or time.monotonic() - cache["at"] > 2.0:
        cache = audio._LOCAL.meter_cache = {"keys": keys, "at": time.monotonic(), "m": _win_meter_objects(specs)}
    peaks: dict[str, float] = {}
    for key, meters in cache["m"].items():
        for m in meters:
            try:
                peaks[key] = max(peaks.get(key, 0.0), float(m.GetPeakValue()))
            except (OSError, comtypes.COMError):
                cache["at"] = 0.0  # Gerät weg o. Ä. → beim nächsten Mal neu suchen
    return peaks


def _win_meter_objects(specs: list[dict]) -> dict[str, list]:
    """{Kanal-Schlüssel: [IAudioMeterInformation …]} für Geräte und Programm-Sitzungen."""
    import comtypes

    from . import audio
    from .mixer import _win_sessions_api

    w, meter = audio._win(), _win_meter_api()
    found: dict[str, list] = {}
    for s in specs:
        if s.get("stream") is not None:
            continue
        try:
            dev = audio._win_default("out") if s["dev"] == DEFAULT_OUT else w["enum"].GetDevice(s["dev"])
            found[s["key"]] = [dev.Activate(meter._iid_, comtypes.CLSCTX_ALL, None).QueryInterface(meter)]
        except (OSError, comtypes.COMError):
            pass
    wanted = {str(s["stream"]).split(":")[-1]: s["key"] for s in specs if s.get("stream") is not None}
    if wanted:
        api = _win_sessions_api()
        coll = w["enum"].EnumAudioEndpoints(0, 1)
        for i in range(coll.GetCount()):
            try:
                mgr = coll.Item(i).Activate(api["IAudioSessionManager2"]._iid_, comtypes.CLSCTX_ALL,
                                            None).QueryInterface(api["IAudioSessionManager2"])
                sessions = mgr.GetSessionEnumerator()
                for k in range(sessions.GetCount()):
                    unk = sessions.GetSession(k)
                    pid = str(int(unk.QueryInterface(api["IAudioSessionControl2"]).GetProcessId()))
                    if pid in wanted:
                        found.setdefault(wanted[pid], []).append(unk.QueryInterface(meter))
            except (OSError, comtypes.COMError):
                continue
    return found
