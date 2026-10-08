"""Linux (CI): Ton-Steuerung ECHT mit PulseAudio – zwei virtuelle Lautsprecher, zwei virtuelle Mikrofone.

Prüft über AluPCs audio-Modul (wie Handy und System-Seite): Geräte mit Namen, Standard wechseln, Lautstärke genau
setzen, stumm an/aus – und liest das Ergebnis unabhängig mit pactl zurück.
"""

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
results = []


def ok(cond, text):
    results.append(bool(cond))
    print(("  ✓ " if cond else "  ✗ ") + text, flush=True)


def pactl(*args):
    return subprocess.run(["pactl", *args], capture_output=True, text=True).stdout.strip()


def main() -> int:
    run_dir = tempfile.mkdtemp()
    os.environ["XDG_RUNTIME_DIR"] = run_dir
    os.environ.pop("PULSE_SERVER", None)
    daemon = subprocess.Popen(["pulseaudio", "-n", "--daemonize=no", "--exit-idle-time=-1", "--disallow-exit",
                               "-L", "module-native-protocol-unix", "-L", "module-null-sink sink_name=lautsprecher_a "
                               "sink_properties=device.description=Lautsprecher-A",
                               "-L", "module-null-sink sink_name=lautsprecher_b sink_properties=device.description=Kopfhoerer-B",
                               "-L", "module-null-source source_name=mikro_a description=Mikrofon-A",
                               "-L", "module-null-source source_name=mikro_b description=Headset-B"],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            if pactl("info"):
                break
            time.sleep(0.1)
        from alupc import audio

        ok(audio.available(), "pactl da")
        outs, ins = audio.devices("out"), audio.devices("in")
        names_out, names_in = [d["name"] for d in outs], [d["name"] for d in ins]
        ok({"Lautsprecher-A", "Kopfhoerer-B"} <= set(names_out), f"Lautsprecher mit Namen: {names_out}")
        ok({"Mikrofon-A", "Headset-B"} <= set(names_in) and not any("Monitor" in n for n in names_in),
           f"Mikrofone mit Namen (ohne „Monitor of …“): {names_in}")
        i = names_out.index("Kopfhoerer-B")
        print(" ", audio.run(f"ton_geraet:{i}"))
        ok(pactl("get-default-sink") == "lautsprecher_b", f"Standard-Lautsprecher → {pactl('get-default-sink')}")
        j = [d["name"] for d in audio.devices("in")].index("Headset-B")
        print(" ", audio.run(f"mic_geraet:{j}"))
        ok(pactl("get-default-source") == "mikro_b", f"Standard-Mikrofon → {pactl('get-default-source')}")
        print(" ", audio.run("ton_laut:37"), audio.run("mic_laut:62"))
        ok("37%" in pactl("get-sink-volume", "lautsprecher_b"), f"Lautsprecher 37 % → {pactl('get-sink-volume', 'lautsprecher_b')}")
        ok("62%" in pactl("get-source-volume", "mikro_b"), f"Mikrofon 62 % → {pactl('get-source-volume', 'mikro_b')}")
        audio.run("ton_stumm:1")
        audio.run("mic_stumm:1")
        ok("yes" in pactl("get-sink-mute", "lautsprecher_b") and "yes" in pactl("get-source-mute", "mikro_b"),
           "Stumm an (Lautsprecher und Mikrofon)")
        st = audio.state(max_age=0)
        ok(st["out"]["vol"] == 37 and st["out"]["muted"] and st["in"]["vol"] == 62 and st["in"]["muted"]
           and any(d["default"] and d["name"] == "Kopfhoerer-B" for d in st["out"]["devices"]),
           f"Zustand fürs Handy stimmt: {st['out']['vol']} %/{st['in']['vol']} %, stumm")
        audio.run("ton_stumm:0")
        audio.run("mic_stumm:0")
        ok("no" in pactl("get-sink-mute", "lautsprecher_b") and "no" in pactl("get-source-mute", "mikro_b"),
           "Stumm aus")
        from alupc import pc_control

        pc_control.set_volume(55)
        ok(pc_control.get_volume() == 55, f"PC-Lautstärke (System-Seite/Sprache) 55 % → {pc_control.get_volume()}")
    finally:
        daemon.terminate()
    print(f"{sum(results)}/{len(results)} Prüfungen bestanden")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
