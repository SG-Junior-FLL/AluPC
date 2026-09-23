"""Monitor-Einstellungen unter Linux: KDE (kscreen-doctor, X11 + Wayland) oder xrandr (X11)."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess

from .base import DisplayBackend, DisplayMode, Output

KSCREEN_ROTATION = {1: "normal", 2: "left", 4: "inverted", 8: "right"}


def _run(cmd: list[str], timeout: int = 20) -> str:
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "Unbekannter Fehler").strip())
    return proc.stdout


def is_wayland() -> bool:
    return os.environ.get("XDG_SESSION_TYPE") == "wayland" or bool(os.environ.get("WAYLAND_DISPLAY"))


# --------------------------------------------------------------------------- KDE
def parse_kscreen_json(text: str) -> list[Output]:
    start = text.find("{")
    data = json.loads(text[start:] if start >= 0 else text)
    outputs: list[Output] = []
    for o in data.get("outputs", []):
        if not o.get("connected", True):
            continue
        modes = []
        for m in o.get("modes", []):
            size = m.get("size", {})
            modes.append(
                DisplayMode(
                    id=str(m.get("id")),
                    width=int(size.get("width", 0)),
                    height=int(size.get("height", 0)),
                    refresh=round(float(m.get("refreshRate", 0)), 2),
                )
            )
        pos = o.get("pos", {})
        primary = bool(o.get("primary")) or o.get("priority") == 1
        outputs.append(
            Output(
                name=o.get("name", str(o.get("id"))),
                description=" ".join(
                    x for x in (o.get("vendor", ""), o.get("model", "")) if x
                ).strip(),
                enabled=bool(o.get("enabled", True)),
                primary=primary,
                x=int(pos.get("x", 0)),
                y=int(pos.get("y", 0)),
                scale=float(o.get("scale", 1.0) or 1.0),
                rotation=KSCREEN_ROTATION.get(int(o.get("rotation", 1) or 1), "normal"),
                mode_id=str(o.get("currentModeId", "")),
                modes=modes,
            )
        )
    return outputs


def kscreen_args(outputs: list[Output], supports_scale: bool = True) -> list[str]:
    args: list[str] = []
    for o in outputs:
        prefix = f"output.{o.name}"
        if not o.enabled:
            args.append(f"{prefix}.disable")
            continue
        args.append(f"{prefix}.enable")
        if o.mode_id:
            args.append(f"{prefix}.mode.{o.mode_id}")
        args.append(f"{prefix}.position.{o.x},{o.y}")
        args.append(f"{prefix}.rotation.{o.rotation}")
        if supports_scale:
            args.append(f"{prefix}.scale.{o.scale:g}")
    for o in outputs:
        if o.enabled and o.primary:
            args.append(f"output.{o.name}.primary")
    return args


class KScreenBackend(DisplayBackend):
    name = "KDE (kscreen-doctor)"

    def __init__(self):
        self.supports_scale = is_wayland()
        self.logical_positions = is_wayland()

    def available(self) -> bool:
        return shutil.which("kscreen-doctor") is not None

    def list_outputs(self) -> list[Output]:
        return parse_kscreen_json(_run(["kscreen-doctor", "-j"]))

    def apply(self, outputs: list[Output]) -> None:
        _run(["kscreen-doctor", *kscreen_args(outputs, self.supports_scale)], timeout=30)


# --------------------------------------------------------------------------- xrandr
_OUTPUT_RE = re.compile(r"^(\S+) (connected|disconnected)( primary)?(?: (\d+)x(\d+)\+(-?\d+)\+(-?\d+))?(?: (left|right|inverted|normal))?")
_MODE_RE = re.compile(r"^\s+(\d+)x(\d+)(i?)\S*\s+(.*)$")


def parse_xrandr(text: str) -> list[Output]:
    outputs: list[Output] = []
    current: Output | None = None
    for line in text.splitlines():
        match = _OUTPUT_RE.match(line)
        if match:
            name, state, primary, w, h, x, y, rot = match.groups()
            if state != "connected":
                current = None
                continue
            current = Output(
                name=name,
                enabled=w is not None,
                primary=bool(primary),
                x=int(x or 0),
                y=int(y or 0),
                rotation=rot or "normal",
            )
            outputs.append(current)
            continue
        mode = _MODE_RE.match(line)
        if mode and current is not None:
            w, h, interlaced, rest = mode.groups()
            for token in rest.split():
                rate_text = token.rstrip("*+")
                try:
                    rate = float(rate_text)
                except ValueError:
                    continue
                mode_name = f"{w}x{h}{interlaced}"
                mode_id = f"{mode_name}@{rate_text}"
                current.modes.append(DisplayMode(mode_id, int(w), int(h), rate))
                if "*" in token:
                    current.mode_id = mode_id
    return outputs


def xrandr_args(outputs: list[Output]) -> list[str]:
    args: list[str] = []
    for o in outputs:
        args += ["--output", o.name]
        if not o.enabled:
            args.append("--off")
            continue
        if o.mode_id:
            name, _, rate = o.mode_id.partition("@")
            args += ["--mode", name]
            if rate:
                args += ["--rate", rate]
        else:
            args.append("--auto")
        args += ["--pos", f"{o.x}x{o.y}", "--rotate", o.rotation]
        if o.primary:
            args.append("--primary")
    return args


class XrandrBackend(DisplayBackend):
    name = "X11 (xrandr)"

    def available(self) -> bool:
        return shutil.which("xrandr") is not None and not is_wayland()

    def list_outputs(self) -> list[Output]:
        return parse_xrandr(_run(["xrandr", "--query"]))

    def apply(self, outputs: list[Output]) -> None:
        _run(["xrandr", *xrandr_args(outputs)], timeout=30)


def create_display_backend() -> DisplayBackend:
    for backend in (KScreenBackend(), XrandrBackend()):
        if backend.available():
            return backend
    return DisplayBackend()
