"""Bildschirmschoner zum Thema Programmieren: Matrix, Code-Editor, Terminal, Netzwerk, Sternenflug.

Jeder Stil ist eine kleine Klasse mit `tick(dt)` (Zustand weiterrechnen) und `paint(p, w, h)`.
Gezeichnet wird sparsam (z. B. Matrix: nur die neuen Zeichen, der Rest verblasst in einem Puffer),
damit es auch auf 4K flüssig bleibt.
"""

from __future__ import annotations

import math
import random
import re
import time

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QImage, QLinearGradient, QPainter, QPen, QRadialGradient

FPS = {"matrix": 30, "code": 30, "terminal": 20, "netz": 30, "sterne": 40}


def mono(px: float, bold: bool = False) -> QFont:
    f = QFont("monospace")
    f.setStyleHint(QFont.Monospace)
    f.setFamilies(["JetBrains Mono", "Cascadia Code", "Consolas", "DejaVu Sans Mono", "Menlo", "monospace"])
    f.setPixelSize(max(8, int(px)))
    f.setBold(bold)
    return f


# =========================================================================== Matrix
class Matrix:
    CHARS = "アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワン" \
            "0123456789{}[]<>=+-*/;:#$&ABCDEF"

    def __init__(self, rng: random.Random, color: QColor):
        self.rng = rng
        self.color = color if color.isValid() and color.name() != "#e8ecf3" else QColor("#22ff66")
        self.buffer: QImage | None = None
        self.drops: list[float] = []
        self.speeds: list[float] = []
        self.cell = 20.0

    def _setup(self, w: int, h: int):
        self.cell = max(14.0, h / 48)
        self.buffer = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
        self.buffer.fill(Qt.black)
        cols = int(w / self.cell) + 1
        self.drops = [self.rng.uniform(-h / self.cell, 0) for _ in range(cols)]
        self.speeds = [self.rng.uniform(0.35, 1.0) for _ in range(cols)]
        self.last: list[int] = [-1] * cols

    def tick(self, dt: float, w: int, h: int):
        if self.buffer is None or self.buffer.width() != w or self.buffer.height() != h:
            self._setup(w, h)
        p = QPainter(self.buffer)
        p.fillRect(0, 0, w, h, QColor(0, 0, 0, 34))  # alles ein wenig verblassen lassen → Spuren
        p.setFont(mono(self.cell * 0.9, bold=True))
        rows = h / self.cell
        for i in range(len(self.drops)):
            self.drops[i] += self.speeds[i] * dt * 22
            row = int(self.drops[i])
            if row != self.last[i] and row >= 0:
                x, y = i * self.cell, row * self.cell
                # vorheriges Kopfzeichen in Spurfarbe übermalen, neuen Kopf hell zeichnen
                if self.last[i] >= 0:
                    p.fillRect(QRectF(x, self.last[i] * self.cell, self.cell, self.cell), QColor(0, 0, 0, 160))
                    p.setPen(self.color)
                    p.drawText(QRectF(x, self.last[i] * self.cell, self.cell, self.cell), Qt.AlignCenter,
                               self.rng.choice(self.CHARS))
                p.setPen(QColor(235, 255, 240))
                p.drawText(QRectF(x, y, self.cell, self.cell), Qt.AlignCenter, self.rng.choice(self.CHARS))
                self.last[i] = row
            if self.drops[i] > rows + self.rng.uniform(0, 30):
                self.drops[i] = self.rng.uniform(-12, 0)
                self.speeds[i] = self.rng.uniform(0.35, 1.0)
                self.last[i] = -1
        p.end()

    def paint(self, p: QPainter, w: int, h: int):
        if self.buffer is not None:
            p.drawImage(0, 0, self.buffer)


# =========================================================================== Code-Editor
SNIPPETS = [
    ("monitor2.py", "python", '''# AluPC – Monitor 2 steuern
from dataclasses import dataclass


@dataclass
class Szene:
    name: str
    layout: str = "vollbild"
    felder: list = None

    def zeigen(self, monitor):
        """Szene auf Monitor 2 bringen – mit weichem Übergang."""
        for feld, quelle in zip(layout_felder(self.layout), self.felder or []):
            monitor.lege(quelle, in_bereich=feld)
        monitor.uebergang("blende", ms=400)


def naechste_szene(szenen, aktuell):
    i = szenen.index(aktuell)
    return szenen[(i + 1) % len(szenen)]


if __name__ == "__main__":
    start = Szene("Begrüßung", felder=["Kamera", "Uhr"])
    print(f"Zeige {start.name} …")
'''),
    ("fingerprint.cpp", "cpp", '''// Fingerabdruck prüfen (EF01-Protokoll)
#include <cstdint>
#include <vector>

int identify(Sensor& sensor, unsigned capacity) {
    if (sensor.getImage() != OK) return -1;   // kein Finger
    if (sensor.genChar(1) != OK) return -1;   // Merkmale
    auto hit = sensor.search(1, 0, capacity);
    return hit.found ? hit.slot : -1;
}

int main() {
    Sensor sensor("COM3", 57600);
    while (true) {
        const int slot = identify(sensor, 100);
        if (slot >= 0) {
            std::printf("Willkommen! (Platz %d)\\n", slot);
            return 0;
        }
    }
}
'''),
    ("laser.js", "js", '''// Laserpointer mit Leuchtspur
const spur = [];

function bewege(punkt) {
  spur.push({ ...punkt, zeit: performance.now() });
  while (spur.length && performance.now() - spur[0].zeit > 280) {
    spur.shift();
  }
}

function zeichne(ctx) {
  for (const [i, p] of spur.entries()) {
    const alter = i / spur.length;
    ctx.globalAlpha = 0.45 * alter;
    ctx.beginPath();
    ctx.arc(p.x, p.y, 6 + 4 * alter, 0, Math.PI * 2);
    ctx.fill();
  }
}

export { bewege, zeichne };
'''),
    ("timer.rs", "rust", '''// Countdown für die Präsentation
use std::time::{Duration, Instant};

struct Timer {
    ende: Instant,
}

impl Timer {
    fn neu(minuten: u64) -> Self {
        Timer { ende: Instant::now() + Duration::from_secs(minuten * 60) }
    }

    fn rest(&self) -> Duration {
        self.ende.saturating_duration_since(Instant::now())
    }
}

fn main() {
    let timer = Timer::neu(5);
    while timer.rest() > Duration::ZERO {
        let s = timer.rest().as_secs();
        println!("{:02}:{:02}", s / 60, s % 60);
        std::thread::sleep(Duration::from_secs(1));
    }
    println!("Zeit ist um!");
}
'''),
]

KEYWORDS = {
    "python": r"\b(from|import|class|def|return|for|in|if|else|elif|while|with|as|not|and|or|None|True|False|"
              r"lambda|yield|self)\b",
    "cpp": r"\b(int|unsigned|return|if|while|true|false|const|auto|void|struct|class|for|std)\b",
    "js": r"\b(const|let|function|return|for|of|while|export|import|if|else|new)\b",
    "rust": r"\b(use|struct|impl|fn|let|mut|while|return|Self|self|pub|for|in|if)\b",
}
COMMENT = {"python": "#", "cpp": "//", "js": "//", "rust": "//"}
THEME = {
    "bg": "#0f1320", "gutter": "#0b0e18", "line": "#161b2b", "text": "#d7dae0", "muted": "#4b5470",
    "keyword": "#c678dd", "string": "#98c379", "comment": "#5c6370", "number": "#d19a66",
    "function": "#61afef", "deco": "#e5c07b", "tab": "#1a2033", "accent": "#61afef",
}
TOKEN = re.compile(r'(?P<comment>(#|//).*$)|(?P<string>"[^"]*"|\'[^\']*\'|`[^`]*`)|(?P<number>\b\d+\b)|'
                   r'(?P<deco>@\w+)|(?P<word>[A-Za-z_]\w*)(?P<call>\s*\()?|(?P<other>.)')


def highlight(line: str, lang: str) -> list[tuple[str, str]]:
    """Zeile → [(Text, Farbname)] für einfache Syntaxfarben."""
    keywords = re.compile(KEYWORDS.get(lang, r"$^"))
    parts: list[tuple[str, str]] = []
    for m in TOKEN.finditer(line):
        if m.group("comment") and m.group("comment").startswith(COMMENT.get(lang, "#")):
            parts.append((m.group("comment"), "comment"))
        elif m.group("comment"):  # „#“ in C++ (#include) → wie Schlüsselwort
            parts.append((m.group("comment"), "keyword"))
        elif m.group("string"):
            parts.append((m.group("string"), "string"))
        elif m.group("number"):
            parts.append((m.group("number"), "number"))
        elif m.group("deco"):
            parts.append((m.group("deco"), "deco"))
        elif m.group("word"):
            word = m.group("word")
            color = "keyword" if keywords.fullmatch(word) else ("function" if m.group("call") else "text")
            parts.append((word, color))
            if m.group("call"):
                parts.append((m.group("call"), "text"))
        else:
            parts.append((m.group(0), "text"))
    return parts


class CodeEditor:
    def __init__(self, rng: random.Random, cfg: dict):
        self.rng = rng
        self.order = list(range(len(SNIPPETS)))
        rng.shuffle(self.order)
        self.index = 0
        self.typed = 0.0
        self.pause = 0.0
        self.speed = 38.0  # Zeichen pro Sekunde
        self.caption = cfg.get("text") or ""
        self._load()

    def _load(self):
        self.name, self.lang, text = SNIPPETS[self.order[self.index % len(self.order)]]
        self.text = text
        self.lines_cache: dict[int, list] = {}

    def tick(self, dt: float, w: int, h: int):
        if self.pause > 0:
            self.pause -= dt
            if self.pause <= 0:
                self.index += 1
                self.typed = 0
                self._load()
            return
        # etwas unregelmäßig tippen – wirkt menschlicher
        self.typed += dt * self.speed * self.rng.uniform(0.4, 1.8)
        if self.typed >= len(self.text):
            self.typed = len(self.text)
            self.pause = 4.0

    def paint(self, p: QPainter, w: int, h: int):
        th = {k: QColor(v) for k, v in THEME.items()}
        p.fillRect(0, 0, w, h, th["bg"])
        size = max(12.0, h / 40)
        font = mono(size)
        fm = QFontMetricsF(font)
        line_h = fm.height() * 1.35
        tab_h = line_h * 1.4
        status_h = line_h * 1.1
        gutter = fm.horizontalAdvance("0000") + size
        # Reiter oben
        p.fillRect(QRectF(0, 0, w, tab_h), th["tab"])
        tab_w = fm.horizontalAdvance(self.name) + size * 3
        p.fillRect(QRectF(0, 0, tab_w, tab_h), th["bg"])
        p.fillRect(QRectF(0, 0, tab_w, 3), th["accent"])
        p.setFont(font)
        p.setPen(th["text"])
        p.drawText(QRectF(size, 0, tab_w, tab_h), Qt.AlignVCenter, self.name)
        # Code bis zur aktuellen Tippstelle
        shown = self.text[:int(self.typed)]
        lines = shown.split("\n")
        visible = int((h - tab_h - status_h) / line_h) - 1
        first = max(0, len(lines) - visible)
        top = tab_h + line_h * 0.4
        p.fillRect(QRectF(0, tab_h, gutter, h - tab_h - status_h), th["gutter"])
        for n, line in enumerate(lines[first:], start=first):
            y = top + (n - first) * line_h
            current = n == len(lines) - 1
            if current:
                p.fillRect(QRectF(gutter, y, w - gutter, line_h), th["line"])
            p.setPen(th["text"] if current else th["muted"])
            p.drawText(QRectF(0, y, gutter - size * 0.6, line_h), Qt.AlignRight | Qt.AlignVCenter, str(n + 1))
            x = gutter + size * 0.8
            key = (n, len(line))
            parts = self.lines_cache.get(key) if not current else None
            if parts is None:
                parts = highlight(line, self.lang)
                if not current:
                    self.lines_cache[key] = parts
            for text, color in parts:
                p.setPen(th.get(color, th["text"]))
                p.drawText(QPointF(x, y + line_h * 0.72), text)
                x += fm.horizontalAdvance(text)
            if current and int(time.monotonic() * 2) % 2 == 0:  # blinkender Cursor
                p.fillRect(QRectF(x + 1, y + line_h * 0.15, max(2, size / 7), line_h * 0.7), th["accent"])
        # Statusleiste
        p.fillRect(QRectF(0, h - status_h, w, status_h), th["accent"])
        p.setPen(QColor("#0b0e18"))
        p.setFont(mono(size * 0.8, bold=True))
        left = f"  {self.caption or 'AluPC'}  ·  {self.lang.upper()}  ·  UTF-8"
        right = f"Zeile {len(lines)}, Spalte {len(lines[-1]) + 1}  ·  {time.strftime('%H:%M')}  "
        p.drawText(QRectF(0, h - status_h, w, status_h), Qt.AlignVCenter | Qt.AlignLeft, left)
        p.drawText(QRectF(0, h - status_h, w, status_h), Qt.AlignVCenter | Qt.AlignRight, right)


# =========================================================================== Terminal
class Terminal:
    STEPS = [
        ("$ git pull", "cmd"), ("Already up to date.", "dim"),
        ("$ python -m pytest -q", "cmd"), ("PROGRESS", "bar"), ("{n} passed in {s} s", "ok"),
        ("$ pyinstaller --name AluPC packaging/pyinstaller_entry.py", "cmd"),
        ("INFO: Analyzing modules …", "dim"), ("INFO: Building EXE …", "dim"), ("PROGRESS", "bar"),
        ("✔ dist/AluPC/AluPC erstellt", "ok"),
        ("$ packaging/linux/build_deb.sh {v}", "cmd"), ("dpkg-deb: building package 'alupc'", "dim"),
        ("✔ alupc_{v}_amd64.deb", "ok"),
        ("$ alupc --befehl spiegeln", "cmd"), ("Monitor 2: Spiegeln aktiv · 60 Hz · 1920×1080", "info"),
        ("$ ping -c 3 monitor2.local", "cmd"),
        ("64 bytes from monitor2.local: icmp_seq=1 ttl=64 time={ms} ms", "dim"),
        ("64 bytes from monitor2.local: icmp_seq=2 ttl=64 time={ms} ms", "dim"),
        ("64 bytes from monitor2.local: icmp_seq=3 ttl=64 time={ms} ms", "dim"),
        ("$ neofetch --kurz", "cmd"), ("OS: Kubuntu · WM: KWin · Monitore: 2 · Stimmung: ☕", "info"),
    ]
    COLORS = {"cmd": "#e5e7eb", "dim": "#7c8599", "ok": "#4ade80", "info": "#60a5fa", "bar": "#f59e0b"}

    def __init__(self, rng: random.Random, cfg: dict):
        self.rng = rng
        self.lines: list[tuple[str, str]] = []
        self.step = 0
        self.typing = ""
        self.typed = 0.0
        self.wait = 0.5
        self.progress = -1.0
        from . import __version__

        self.version = __version__

    def _fill(self, text: str) -> str:
        return text.format(n=self.rng.randint(80, 140), s=f"{self.rng.uniform(8, 30):.2f}", v=self.version,
                           ms=f"{self.rng.uniform(0.2, 2.5):.1f}")

    def tick(self, dt: float, w: int, h: int):
        if self.wait > 0:
            self.wait -= dt
            return
        text, kind = self.STEPS[self.step % len(self.STEPS)]
        if kind == "bar":
            self.progress = max(0.0, self.progress) + dt * self.rng.uniform(0.15, 0.6)
            if self.progress >= 1:
                self.lines.append(("[" + "█" * 30 + "] 100 %", "bar"))
                self.progress = -1
                self.step += 1
                self.wait = 0.3
            return
        if kind == "cmd":  # Befehle werden getippt
            full = self._fill(text)
            self.typed += dt * self.rng.uniform(14, 30)
            self.typing = full[:int(self.typed)]
            if self.typed >= len(full):
                self.lines.append((full, "cmd"))
                self.typing, self.typed = "", 0.0
                self.step += 1
                self.wait = 0.35
            return
        self.lines.append((self._fill(text), kind))  # Ausgaben erscheinen sofort
        self.step += 1
        self.wait = self.rng.uniform(0.08, 0.5)
        self.lines = self.lines[-200:]

    def paint(self, p: QPainter, w: int, h: int):
        p.fillRect(0, 0, w, h, QColor("#0a0c10"))
        size = max(12.0, h / 42)
        font = mono(size)
        p.setFont(font)
        fm = QFontMetricsF(font)
        line_h = fm.height() * 1.3
        # Fensterrahmen wie ein Terminal
        bar_h = line_h * 1.3
        p.fillRect(QRectF(0, 0, w, bar_h), QColor("#1a1d24"))
        for i, c in enumerate(("#ff5f57", "#febc2e", "#28c840")):
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(c))
            p.drawEllipse(QPointF(size * (1.2 + i * 1.3), bar_h / 2), size * 0.38, size * 0.38)
        p.setPen(QColor("#9aa3b5"))
        p.drawText(QRectF(0, 0, w, bar_h), Qt.AlignCenter, "alupc@monitor2: ~/alupc")
        rows = self.lines[:]
        if self.progress >= 0:
            filled = int(30 * self.progress)
            rows.append(("[" + "█" * filled + "░" * (30 - filled) + f"] {int(self.progress * 100):3d} %", "bar"))
        prompt = self.typing if self.typing or not rows or rows[-1][1] != "cmd" else ""
        visible = int((h - bar_h) / line_h) - 2
        rows = rows[-visible:]
        y = bar_h + line_h * 0.5
        x = size
        for text, kind in rows:
            p.setPen(QColor(self.COLORS.get(kind, "#e5e7eb")))
            if kind == "cmd":
                self._prompt_line(p, x, y, line_h, text[2:], fm)
            else:
                p.drawText(QPointF(x, y + line_h * 0.75), text)
            y += line_h
        # aktuelle Eingabezeile mit Cursor
        self._prompt_line(p, x, y, line_h, prompt[2:] if prompt.startswith("$ ") else prompt, fm, cursor=True)

    def _prompt_line(self, p, x, y, line_h, text, fm, cursor=False):
        p.setPen(QColor("#4ade80"))
        p.drawText(QPointF(x, y + line_h * 0.75), "➜ ")
        x += fm.horizontalAdvance("➜ ")
        p.setPen(QColor("#60a5fa"))
        p.drawText(QPointF(x, y + line_h * 0.75), "~/alupc ")
        x += fm.horizontalAdvance("~/alupc ")
        p.setPen(QColor("#e5e7eb"))
        p.drawText(QPointF(x, y + line_h * 0.75), text)
        if cursor and int(time.monotonic() * 2) % 2 == 0:
            x += fm.horizontalAdvance(text)
            p.fillRect(QRectF(x + 2, y + line_h * 0.15, fm.horizontalAdvance("M"), line_h * 0.7), QColor("#e5e7eb"))


# =========================================================================== Netzwerk (Plexus)
class Network:
    def __init__(self, rng: random.Random, color: QColor):
        self.rng = rng
        self.color = color if color.isValid() and color.name() != "#e8ecf3" else QColor("#60a5fa")
        self.points: list[list[float]] = []

    def tick(self, dt: float, w: int, h: int):
        count = max(40, min(140, int(w * h / 22000)))
        while len(self.points) < count:
            a = self.rng.uniform(0, math.tau)
            speed = self.rng.uniform(15, 45)
            self.points.append([self.rng.uniform(0, w), self.rng.uniform(0, h), math.cos(a) * speed,
                                math.sin(a) * speed])
        del self.points[count:]
        for pt in self.points:
            pt[0] += pt[2] * dt
            pt[1] += pt[3] * dt
            if not 0 <= pt[0] <= w:
                pt[2] = -pt[2]
                pt[0] = min(max(pt[0], 0), w)
            if not 0 <= pt[1] <= h:
                pt[3] = -pt[3]
                pt[1] = min(max(pt[1], 0), h)

    def paint(self, p: QPainter, w: int, h: int):
        bg = QLinearGradient(0, 0, 0, h)
        bg.setColorAt(0, QColor("#070b16"))
        bg.setColorAt(1, QColor("#0d1326"))
        p.fillRect(0, 0, w, h, bg)
        reach = max(w, h) / 8
        reach2 = reach * reach
        pen = QPen(self.color, max(1.0, h / 900))
        pts = self.points
        for i in range(len(pts)):
            x1, y1 = pts[i][0], pts[i][1]
            for j in range(i + 1, len(pts)):
                dx, dy = pts[j][0] - x1, pts[j][1] - y1
                d2 = dx * dx + dy * dy
                if d2 < reach2:
                    c = QColor(self.color)
                    c.setAlphaF(0.55 * (1 - d2 / reach2))
                    pen.setColor(c)
                    p.setPen(pen)
                    p.drawLine(QPointF(x1, y1), QPointF(pts[j][0], pts[j][1]))
        p.setPen(Qt.NoPen)
        r = max(2.0, h / 320)
        for x, y, _vx, _vy in pts:
            glow = QRadialGradient(QPointF(x, y), r * 4)
            c = QColor(self.color)
            c.setAlphaF(0.5)
            glow.setColorAt(0, c)
            c.setAlphaF(0)
            glow.setColorAt(1, c)
            p.setBrush(glow)
            p.drawEllipse(QPointF(x, y), r * 4, r * 4)
            p.setBrush(QColor("#ffffff"))
            p.drawEllipse(QPointF(x, y), r, r)


# =========================================================================== Sternenflug
class Starfield:
    def __init__(self, rng: random.Random):
        self.rng = rng
        self.stars = [self._new(far=True) for _ in range(420)]

    def _new(self, far: bool = False):
        return [self.rng.uniform(-1, 1), self.rng.uniform(-1, 1), self.rng.uniform(0.1, 1) if far else 1.0]

    def tick(self, dt: float, w: int, h: int):
        for s in self.stars:
            s[2] -= dt * 0.35
            if s[2] <= 0.02:
                s[:] = self._new()

    def paint(self, p: QPainter, w: int, h: int):
        p.fillRect(0, 0, w, h, QColor("#02030a"))
        cx, cy, scale = w / 2, h / 2, max(w, h) / 2
        for x, y, z in self.stars:
            sx, sy = cx + x / z * scale * 0.5, cy + y / z * scale * 0.5
            if not (0 <= sx < w and 0 <= sy < h):
                continue
            # Streifen: von der vorherigen (weiter entfernten) Position zur aktuellen
            pz = z + 0.035
            px, py = cx + x / pz * scale * 0.5, cy + y / pz * scale * 0.5
            bright = max(0.0, min(1.0, 1.2 - z))
            c = QColor.fromRgbF(0.75 + 0.25 * bright, 0.85 + 0.15 * bright, 1.0, bright)
            p.setPen(QPen(c, max(1.0, (1.1 - z) * h / 400), Qt.SolidLine, Qt.RoundCap))
            p.drawLine(QPointF(px, py), QPointF(sx, sy))


def create(style: str, rng: random.Random, cfg: dict):
    color = QColor(cfg.get("color") or "")
    if style == "matrix":
        return Matrix(rng, color)
    if style == "code":
        return CodeEditor(rng, cfg)
    if style == "terminal":
        return Terminal(rng, cfg)
    if style == "netz":
        return Network(rng, color)
    if style == "sterne":
        return Starfield(rng)
    return None
