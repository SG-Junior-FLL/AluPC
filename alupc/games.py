"""Minispiele: Handys sind die Controller, Monitor 2 ist das Spielfeld.

Ablauf: Kachel „Minispiele“ → Monitor 2 zeigt eine Lobby mit QR-Code → jeder scannt, gibt einen Namen ein und ist
dabei → Start (am PC oder auf einem Handy) → Spiel → Siegertreppchen → nochmal.

Zum Mitspielen braucht das Handy nur das Stichwort der Spielrunde im QR-Code – NICHT den Code der Handy-Steuerung.
Diese Datei enthält nur die Spiel-Logik (ohne Qt); gezeichnet wird in game_source.py, das Handy-Bedienfeld steht
in GAME_PAGE (unten).
"""

from __future__ import annotations

import random
import re
import secrets
import threading
import time
from collections import deque

GAMES = {
    "schlangen": ("Schlangen-Party", "Steuerkreuz oder wischen · Punkte fressen · 90 Sekunden"),
    "reaktion": ("Schnellster Finger", "Erst rot, dann GRÜN: sofort tippen · zu früh = Minuspunkt · 5 Runden"),
    "rennen": ("Tipp-Rennen", "So schnell tippen wie möglich · wer zuerst im Ziel ist, gewinnt"),
}
COLORS = ["#ef4444", "#3b82f6", "#22c55e", "#f59e0b", "#a855f7", "#ec4899", "#06b6d4", "#f97316", "#84cc16",
          "#eab308", "#14b8a6", "#e11d48"]
MAX_PLAYERS = len(COLORS)
NAME_RE = re.compile(r"[^\w .\-!?äöüÄÖÜß]", re.UNICODE)
DIRS = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}


class Player:
    def __init__(self, pid: str, name: str, color: str, now: float):
        self.pid, self.name, self.color = pid, name, color
        self.seen = now

    def public(self) -> dict:
        return {"name": self.name, "color": self.color}


# --------------------------------------------------------------------------- Schlangen-Party
class SnakeGame:
    W, H = 40, 22
    STEP = 0.12  # Sekunden pro Feld
    DURATION = 90.0
    RESPAWN = 2.0

    def __init__(self, players: dict, now: float, rng: random.Random | None = None):
        self.rng = rng or random.Random()
        self.start, self.last_step = now, now
        self.snakes: dict[str, dict] = {}
        self.food: set[tuple[int, int]] = set()
        for i, pid in enumerate(players):
            self.snakes[pid] = {"body": deque(), "dir": (1, 0), "next": (1, 0), "alive": False, "respawn": now,
                                "score": 0}
            self._spawn(pid, i)
        self._fill_food(len(players))
        self.over = False

    def remaining(self, now: float) -> float:
        return max(0.0, self.DURATION - (now - self.start))

    def _occupied(self) -> set:
        return {c for s in self.snakes.values() if s["alive"] for c in s["body"]}

    def _spawn(self, pid: str, index: int | None = None) -> None:
        s = self.snakes[pid]
        busy = self._occupied() | self.food
        for _ in range(200):
            x, y = self.rng.randrange(4, self.W - 4), self.rng.randrange(2, self.H - 2)
            d = self.rng.choice(list(DIRS.values()))
            cells = [((x - d[0] * k) % self.W, (y - d[1] * k) % self.H) for k in range(3)]
            if not busy & set(cells):
                break
        s["body"] = deque(cells)
        s["dir"] = s["next"] = d
        s["alive"] = True

    def _fill_food(self, players: int) -> None:
        want = max(3, players + 2)
        busy = self._occupied()
        while len(self.food) < want:
            c = (self.rng.randrange(self.W), self.rng.randrange(self.H))
            if c not in busy:
                self.food.add(c)

    def input(self, pid: str, data: dict, now: float) -> None:
        s = self.snakes.get(pid)
        d = DIRS.get(str(data.get("dir", "")))
        if s is None or d is None:
            return
        if (d[0] + s["dir"][0], d[1] + s["dir"][1]) != (0, 0):  # nicht in sich selbst umdrehen
            s["next"] = d

    def update(self, now: float) -> None:
        if self.over:
            return
        if now - self.start >= self.DURATION:
            self.over = True
            return
        steps = 0
        while now - self.last_step >= self.STEP and steps < 10:
            self.last_step += self.STEP
            steps += 1
            self._step(self.last_step)

    def _step(self, now: float) -> None:
        for pid, s in self.snakes.items():
            if not s["alive"] and now >= s["respawn"]:
                self._spawn(pid)
        heads = {}
        for pid, s in self.snakes.items():
            if not s["alive"]:
                continue
            s["dir"] = s["next"]
            hx, hy = s["body"][0]
            heads[pid] = ((hx + s["dir"][0]) % self.W, (hy + s["dir"][1]) % self.H)
        bodies = {c for s in self.snakes.values() if s["alive"] for c in list(s["body"])[:-1]}
        crashed = set()
        for pid, head in heads.items():
            others = [p for p, h in heads.items() if h == head and p != pid]
            if head in bodies or others:
                crashed.add(pid)
        for pid, head in heads.items():
            s = self.snakes[pid]
            if pid in crashed:
                s["alive"] = False
                s["respawn"] = now + self.RESPAWN
                self.food |= set(list(s["body"])[::3])  # was übrig bleibt, wird Futter
                continue
            s["body"].appendleft(head)
            if head in self.food:
                self.food.discard(head)
                s["score"] += 1
            else:
                s["body"].pop()
        self._fill_food(len(self.snakes))

    def scores(self) -> dict[str, int]:
        return {pid: s["score"] for pid, s in self.snakes.items()}

    def status(self, pid: str, now: float) -> str:
        s = self.snakes.get(pid)
        if s is None:
            return ""
        if not s["alive"]:
            return f"Crash! Gleich wieder da · {s['score']} Punkte"
        return f"{s['score']} Punkte"


# --------------------------------------------------------------------------- Schnellster Finger
class ReactionGame:
    ROUNDS = 5
    GO_WINDOW = 3.0
    RESULT = 2.5

    def __init__(self, players: dict, now: float, rng: random.Random | None = None):
        self.rng = rng or random.Random()
        self.score = {pid: 0 for pid in players}
        self.round = 0
        self.over = False
        self.last: list[tuple[str, float]] = []  # (pid, Reaktionszeit) der letzten Runde
        self.early: set[str] = set()
        self._next_round(now)

    def _next_round(self, now: float) -> None:
        self.round += 1
        self.phase = "warte"
        self.go_at = now + self.rng.uniform(2.0, 5.0)
        self.taps: list[tuple[str, float]] = []
        self.early = set()
        self.until = 0.0

    def input(self, pid: str, data: dict, now: float) -> None:
        if pid not in self.score or not data.get("tap"):
            return
        if self.phase == "warte" and now < self.go_at:
            if pid not in self.early:  # zu früh – einmal pro Runde ein Minuspunkt
                self.early.add(pid)
                self.score[pid] -= 1
        elif self.phase == "los" and pid not in self.early and all(p != pid for p, _ in self.taps):
            self.taps.append((pid, now - self.go_at))

    def update(self, now: float) -> None:
        if self.over:
            return
        if self.phase == "warte" and now >= self.go_at:
            self.phase = "los"
        elif self.phase == "los":
            everyone = len(self.taps) + len(self.early) >= len(self.score)
            if everyone or now >= self.go_at + self.GO_WINDOW:
                for rank, (pid, _t) in enumerate(self.taps[:3]):
                    self.score[pid] += 3 - rank
                self.last = list(self.taps)
                self.phase = "ergebnis"
                self.until = now + self.RESULT
        elif self.phase == "ergebnis" and now >= self.until:
            if self.round >= self.ROUNDS:
                self.over = True
            else:
                self._next_round(now)

    def scores(self) -> dict[str, int]:
        return dict(self.score)

    def status(self, pid: str, now: float) -> str:
        if self.phase == "warte":
            return "Zu früh! −1" if pid in self.early else "Warte auf GRÜN …"
        if self.phase == "los":
            return "JETZT TIPPEN!" if all(p != pid for p, _ in self.taps) else "Getippt ✓"
        place = next((i for i, (p, _) in enumerate(self.last) if p == pid), None)
        return f"Platz {place + 1}" if place is not None else "–"


# --------------------------------------------------------------------------- Tipp-Rennen
class RaceGame:
    GOAL = 60
    MIN_GAP = 0.045  # schneller als ~22 Tipps/s zählt nicht (gegen Tricks)
    END_DELAY = 4.0

    def __init__(self, players: dict, now: float, rng: random.Random | None = None):
        self.progress = {pid: 0 for pid in players}
        self.last_tap = {pid: 0.0 for pid in players}
        self.finish: list[str] = []
        self.start = now + 3.0  # 3-2-1-Los
        self.end_at = None
        self.over = False

    def input(self, pid: str, data: dict, now: float) -> None:
        if pid not in self.progress or not data.get("tap") or now < self.start or pid in self.finish:
            return
        if now - self.last_tap[pid] < self.MIN_GAP:
            return
        self.last_tap[pid] = now
        self.progress[pid] += 1
        if self.progress[pid] >= self.GOAL:
            self.finish.append(pid)
            if self.end_at is None:
                self.end_at = now + self.END_DELAY

    def update(self, now: float) -> None:
        if not self.over and self.end_at is not None and (now >= self.end_at or len(self.finish) == len(self.progress)):
            self.over = True

    def scores(self) -> dict[str, int]:
        # Ziel zuerst erreicht zählt mehr als Fortschritt
        bonus = {pid: (len(self.progress) - i) * 1000 for i, pid in enumerate(self.finish)}
        return {pid: p + bonus.get(pid, 0) for pid, p in self.progress.items()}

    def status(self, pid: str, now: float) -> str:
        if now < self.start:
            return f"Gleich geht's los … {int(self.start - now) + 1}"
        if pid in self.finish:
            return f"Im Ziel! Platz {self.finish.index(pid) + 1}"
        return f"{self.progress.get(pid, 0)} / {self.GOAL}"


GAME_CLASSES = {"schlangen": SnakeGame, "reaktion": ReactionGame, "rennen": RaceGame}


# --------------------------------------------------------------------------- Spielrunde
class GameHub:
    """Spieler, Lobby und das laufende Spiel. Wird vom Webserver-Thread und vom Qt-Thread benutzt (Lock)."""

    LOBBY_TIMEOUT = 25.0  # so lange ohne Lebenszeichen → aus der Lobby

    def __init__(self, game: str = "schlangen", clock=time.monotonic, rng: random.Random | None = None):
        self.game_key = game if game in GAMES else "schlangen"
        self.clock = clock
        self.rng = rng or random.Random()
        self.token = secrets.token_urlsafe(6)
        self.players: dict[str, Player] = {}
        self.phase = "lobby"  # lobby | running | over
        self.game = None
        self.ranking: list[tuple[str, int]] = []
        self.lock = threading.RLock()

    # ---- Spieler
    def join(self, name: str) -> Player | None:
        name = NAME_RE.sub("", " ".join(str(name).split()))[:16].strip() or "Spieler"
        with self.lock:
            now = self.clock()
            if len(self.players) >= MAX_PLAYERS:
                return None
            taken = {p.name for p in self.players.values()}
            base, n = name, 2
            while name in taken:
                name = f"{base[:13]} {n}"
                n += 1
            used = {p.color for p in self.players.values()}
            color = next(c for c in COLORS if c not in used)
            player = Player(secrets.token_urlsafe(8), name, color, now)
            self.players[player.pid] = player
            if self.phase == "running" and self.game is not None:
                self._add_to_game(player.pid)
            return player

    def _add_to_game(self, pid: str) -> None:
        g = self.game
        if isinstance(g, SnakeGame):
            g.snakes[pid] = {"body": deque(), "dir": (1, 0), "next": (1, 0), "alive": False, "respawn": self.clock(),
                             "score": 0}
        elif isinstance(g, ReactionGame):
            g.score[pid] = 0
        elif isinstance(g, RaceGame):
            g.progress[pid] = 0
            g.last_tap[pid] = 0.0

    def seen(self, pid: str) -> Player | None:
        with self.lock:
            p = self.players.get(pid)
            if p is not None:
                p.seen = self.clock()
            return p

    def _prune(self, now: float) -> None:
        if self.phase != "lobby":
            return
        for pid in [pid for pid, p in self.players.items() if now - p.seen > self.LOBBY_TIMEOUT]:
            del self.players[pid]

    # ---- Ablauf
    def set_game(self, key: str) -> None:
        with self.lock:
            if key in GAMES:
                self.game_key = key
            self.phase, self.game = "lobby", None

    def start(self, restart: bool = False) -> bool:
        """Runde starten. Läuft schon eine, nur mit restart=True (am PC) – zwei Handys gleichzeitig starten nicht doppelt."""
        with self.lock:
            if self.phase == "running" and not restart:
                return False
            now = self.clock()
            self._prune(now)
            if not self.players:
                return False
            self.game = GAME_CLASSES[self.game_key](dict(self.players), now, self.rng)
            self.phase = "running"
            self.ranking = []
            return True

    def to_lobby(self) -> None:
        with self.lock:
            self.phase, self.game = "lobby", None

    def input(self, pid: str, data: dict) -> bool:
        with self.lock:
            if pid not in self.players:
                return False
            self.players[pid].seen = self.clock()
            if self.phase == "running" and self.game is not None:
                self.game.input(pid, data, self.clock())
            return True

    def tick(self) -> None:
        with self.lock:
            now = self.clock()
            self._prune(now)
            if self.phase == "running" and self.game is not None:
                self.game.update(now)
                if self.game.over:
                    scores = self.game.scores()
                    self.ranking = sorted(scores.items(), key=lambda kv: -kv[1])
                    self.phase = "over"

    # ---- Anzeige
    def state_for(self, pid: str) -> dict:
        with self.lock:
            now = self.clock()
            p = self.players.get(pid)
            data = {"game": self.game_key, "title": GAMES[self.game_key][0], "help": GAMES[self.game_key][1],
                    "phase": self.phase, "players": len(self.players), "joined": p is not None}
            if p is None:
                return data
            data.update(name=p.name, color=p.color)
            if self.phase == "running" and self.game is not None:
                data["status"] = self.game.status(pid, now)
                if isinstance(self.game, ReactionGame):
                    data["signal"] = self.game.phase
            elif self.phase == "over":
                place = next((i for i, (q, _) in enumerate(self.ranking) if q == pid), None)
                data["status"] = f"Platz {place + 1} von {len(self.ranking)}" if place is not None else "–"
            return data


GAME_PAGE = """<!doctype html>
<html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no, viewport-fit=cover">
<meta name="theme-color" content="#0b1020"><title>AluPC – Spiel</title>
<style>
:root { color-scheme: dark; --c: #3b82f6; }
* { box-sizing: border-box; -webkit-tap-highlight-color: transparent; user-select: none; -webkit-user-select: none; }
html, body { margin: 0; height: 100%; overflow: hidden; overscroll-behavior: none; touch-action: manipulation; }
body { font-family: system-ui, -apple-system, "Segoe UI", sans-serif; color: #f1f5f9;
  background: radial-gradient(circle at 50% 0%, #1e293b 0, #0b1020 70%); display: flex; flex-direction: column; }
header { padding: 16px 18px 8px; display: flex; align-items: center; gap: 10px; }
.dot { width: 16px; height: 16px; border-radius: 50%; background: var(--c); box-shadow: 0 0 14px var(--c); }
header b { font-size: 18px; } header span { color: #94a3b8; font-size: 14px; margin-left: auto; }
main { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 14px 18px 24px; gap: 16px; }
h1 { font-size: 26px; margin: 0; text-align: center; }
p { color: #94a3b8; text-align: center; margin: 0; font-size: 15px; line-height: 1.4; }
input { font: inherit; font-size: 20px; padding: 14px 16px; border-radius: 14px; border: 2px solid #334155; background: #0f172a;
  color: #fff; width: 100%; max-width: 360px; text-align: center; -webkit-user-select: text; user-select: text; }
button { font: inherit; font-weight: 700; border: 0; color: #fff; cursor: pointer; }
.primary { font-size: 20px; padding: 16px 28px; border-radius: 16px; background: var(--c); width: 100%; max-width: 360px; }
.status { font-size: 22px; font-weight: 800; text-align: center; min-height: 30px; }
.tap { width: min(78vw, 56vh); height: min(78vw, 56vh); border-radius: 50%; font-size: 34px; letter-spacing: 1px;
  background: radial-gradient(circle at 35% 30%, color-mix(in srgb, var(--c) 70%, #fff), var(--c));
  box-shadow: 0 14px 40px color-mix(in srgb, var(--c) 45%, transparent), inset 0 -8px 0 rgba(0,0,0,.18); }
.tap:active, .tap.hit { transform: scale(.95); filter: brightness(1.15); }
.pad { display: grid; grid-template-columns: repeat(3, min(26vw, 19vh)); grid-template-rows: repeat(3, min(26vw, 19vh)); gap: 10px; }
.pad button { border-radius: 22px; background: #1e293b; font-size: 34px; border: 2px solid #334155; }
.pad button:active, .pad button.hit { background: var(--c); border-color: var(--c); }
.pad .c { background: transparent; border: 0; }
.go { background: #16a34a !important; } .wait { background: #b91c1c !important; }
.hidden { display: none !important; }
</style></head><body>
<header><div class="dot" id="dot"></div><b id="who">AluPC-Spiel</b><span id="count"></span></header>
<main id="join">
  <h1 id="jtitle">Mitspielen</h1><p id="jhelp"></p>
  <input id="name" maxlength="16" placeholder="Dein Name" autocomplete="off">
  <button class="primary" id="joinbtn">Mitspielen</button><p id="jerr"></p>
</main>
<main id="lobby" class="hidden">
  <h1 id="ltitle"></h1><p id="lhelp"></p><div class="status">Du bist dabei!</div>
  <p>Warte, bis alle drin sind – dann starten.</p>
  <button class="primary" id="startbtn">Spiel starten</button>
</main>
<main id="play" class="hidden">
  <div class="status" id="status"></div>
  <button class="tap" id="tap">TIPP!</button>
  <div class="pad hidden" id="pad">
    <span class="c"></span><button data-d="up">▲</button><span class="c"></span>
    <button data-d="left">◀</button><span class="c"></span><button data-d="right">▶</button>
    <span class="c"></span><button data-d="down">▼</button><span class="c"></span>
  </div>
</main>
<main id="over" class="hidden">
  <h1>Fertig!</h1><div class="status" id="ostatus"></div>
  <button class="primary" id="againbtn">Nochmal</button>
</main>
<script>
const token = new URLSearchParams(location.search).get("u") || "";
let pid = ""; try { pid = sessionStorage.getItem("alupc-spiel-" + token) || ""; } catch (e) {}
let state = {};
const $ = id => document.getElementById(id);
function show(id) { for (const m of ["join","lobby","play","over"]) $(m).classList.toggle("hidden", m !== id); }
function post(body) {
  return fetch("/api/spiel", {method: "POST", headers: {"Content-Type": "application/json"}, keepalive: true,
    body: JSON.stringify(Object.assign({u: token, p: pid}, body))});
}
function vibrate(ms) { try { navigator.vibrate && navigator.vibrate(ms); } catch (e) {} }
async function join() {
  const name = $("name").value.trim() || "Spieler";
  const r = await post({action: "join", name});
  if (!r.ok) { $("jerr").textContent = (await r.json()).error || "Geht gerade nicht"; return; }
  const d = await r.json(); pid = d.p; try { sessionStorage.setItem("alupc-spiel-" + token, pid); } catch (e) {}
  load();
}
$("joinbtn").onclick = join;
$("name").addEventListener("keydown", e => { if (e.key === "Enter") join(); });
$("startbtn").onclick = () => post({action: "start"}).then(load);
$("againbtn").onclick = () => post({action: "start"}).then(load);
function hit(el) { el.classList.add("hit"); setTimeout(() => el.classList.remove("hit"), 90); }
$("tap").addEventListener("touchstart", e => { e.preventDefault(); post({action: "input", tap: 1}); hit($("tap")); vibrate(15); }, {passive: false});
$("tap").addEventListener("mousedown", () => { post({action: "input", tap: 1}); hit($("tap")); });
function dir(d) { post({action: "input", dir: d}); vibrate(10); }
for (const b of document.querySelectorAll("#pad button")) {
  b.addEventListener("touchstart", e => { e.preventDefault(); dir(b.dataset.d); hit(b); }, {passive: false});
  b.addEventListener("mousedown", () => { dir(b.dataset.d); hit(b); });
}
let sx = 0, sy = 0;
$("play").addEventListener("touchstart", e => { sx = e.touches[0].clientX; sy = e.touches[0].clientY; }, {passive: true});
$("play").addEventListener("touchend", e => {
  if (state.game !== "schlangen") return;
  const dx = e.changedTouches[0].clientX - sx, dy = e.changedTouches[0].clientY - sy;
  if (Math.max(Math.abs(dx), Math.abs(dy)) < 30) return;
  dir(Math.abs(dx) > Math.abs(dy) ? (dx > 0 ? "right" : "left") : (dy > 0 ? "down" : "up"));
});
document.addEventListener("keydown", e => {
  const k = {ArrowUp: "up", ArrowDown: "down", ArrowLeft: "left", ArrowRight: "right"}[e.key];
  if (k && state.game === "schlangen") dir(k); else if (e.key === " ") post({action: "input", tap: 1});
});
function render(d) {
  state = d;
  document.documentElement.style.setProperty("--c", d.color || "#3b82f6");
  $("who").textContent = d.joined ? d.name : "AluPC-Spiel";
  $("count").textContent = d.players + " dabei";
  $("jtitle").textContent = d.title; $("jhelp").textContent = d.help;
  if (!d.joined) { show("join"); return; }
  if (d.phase === "lobby") { show("lobby"); $("ltitle").textContent = d.title; $("lhelp").textContent = d.help; return; }
  if (d.phase === "over") { show("over"); $("ostatus").textContent = d.status || ""; return; }
  show("play");
  $("status").textContent = d.status || "";
  const snake = d.game === "schlangen";
  $("pad").classList.toggle("hidden", !snake); $("tap").classList.toggle("hidden", snake);
  $("tap").classList.toggle("go", d.signal === "los"); $("tap").classList.toggle("wait", d.signal === "warte");
  $("tap").textContent = d.game === "reaktion" ? (d.signal === "los" ? "JETZT!" : "warte …") : "TIPP!";
}
async function load() {
  try {
    const r = await fetch("/api/spiel?u=" + encodeURIComponent(token) + "&p=" + encodeURIComponent(pid), {cache: "no-store"});
    if (r.status === 404) { $("jtitle").textContent = "Keine Spielrunde"; $("jhelp").textContent = "Am PC Minispiele starten"; show("join"); return; }
    render(await r.json());
  } catch (e) {}
}
load(); setInterval(load, 350);
</script></body></html>
"""
