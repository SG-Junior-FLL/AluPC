"""Schiffe versenken – zwei Spieler, zwei Bildschirme.

Spieler 1 spielt am PC (Fenster auf Monitor 1, Maus), Spieler 2 auf Monitor 2 (Beamer) – mit dem Handy über das
AluPC-WLAN oder mit den Pfeiltasten + Enter. Jeder Bildschirm zeigt nur die EIGENEN Schiffe; vom Gegner sieht man
nur, wohin man schon geschossen hat. Treffer = nochmal schießen, Wasser = der andere ist dran.
"""

from __future__ import annotations

import functools
import random
import secrets
import threading

SIZE = 10
SHIPS = (5, 4, 3, 3, 2)  # Schlachtschiff, Kreuzer, 2× Zerstörer, U-Boot
SHIP_NAMES = {5: "Schlachtschiff", 4: "Kreuzer", 3: "Zerstörer", 2: "U-Boot"}
LETTERS = "ABCDEFGHIJ"


def cell_name(x: int, y: int) -> str:
    return f"{LETTERS[x]}{y + 1}"


def ship_cells(x: int, y: int, length: int, horizontal: bool) -> list[tuple[int, int]]:
    return [(x + i, y) if horizontal else (x, y + i) for i in range(length)]


class Fleet:
    """Die Schiffe EINES Spielers und die Schüsse, die auf sein Feld gingen."""

    def __init__(self):
        self.ships: list[list[tuple[int, int]]] = []
        self.hits: set[tuple[int, int]] = set()
        self.misses: set[tuple[int, int]] = set()

    def occupied(self) -> set[tuple[int, int]]:
        return {c for s in self.ships for c in s}

    def remaining_lengths(self) -> list[int]:
        """Längen, die noch gesetzt werden müssen (größte zuerst) – Reihenfolge beim Setzen ist frei."""
        left = list(SHIPS)
        for s in self.ships:
            if len(s) in left:
                left.remove(len(s))
        return sorted(left, reverse=True)

    def next_length(self) -> int | None:
        left = self.remaining_lengths()
        return left[0] if left else None

    def complete(self) -> bool:
        return len(self.ships) == len(SHIPS)

    def can_place(self, cells: list[tuple[int, int]]) -> bool:
        """Im Feld, nicht überlappend und nicht direkt angrenzend (auch nicht schräg) – die übliche Regel."""
        taken = self.occupied()
        for x, y in cells:
            if not (0 <= x < SIZE and 0 <= y < SIZE):
                return False
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if (x + dx, y + dy) in taken:
                        return False
        return True

    def place(self, x: int, y: int, horizontal: bool = True, length: int | None = None) -> bool:
        left = self.remaining_lengths()
        length = left[0] if length is None and left else length
        if length not in left:
            return False
        cells = ship_cells(x, y, length, horizontal)
        if not self.can_place(cells):
            return False
        self.ships.append(cells)
        return True

    def undo(self) -> None:
        if self.ships:
            self.ships.pop()

    def remove_at(self, cell: tuple[int, int]) -> list[tuple[int, int]] | None:
        """Schiff auf diesem Feld wieder wegnehmen (zum Verschieben) – das entfernte Schiff oder None."""
        ship = self.ship_at(cell)
        if ship is not None:
            self.ships.remove(ship)
        return ship

    def randomize(self, rng: random.Random | None = None) -> None:
        rng = rng or random.Random()
        for _attempt in range(200):
            self.ships = []
            ok = True
            for length in SHIPS:
                spots = [(x, y, h) for h in (True, False) for x in range(SIZE) for y in range(SIZE)
                         if self.can_place(ship_cells(x, y, length, h))]
                if not spots:
                    ok = False
                    break
                x, y, h = rng.choice(spots)
                self.ships.append(ship_cells(x, y, length, h))
            if ok:
                return
        raise RuntimeError("Schiffe ließen sich nicht verteilen")

    def ship_at(self, cell: tuple[int, int]) -> list[tuple[int, int]] | None:
        return next((s for s in self.ships if cell in s), None)

    def sunk(self, ship: list[tuple[int, int]]) -> bool:
        return all(c in self.hits for c in ship)

    def all_sunk(self) -> bool:
        return bool(self.ships) and all(self.sunk(s) for s in self.ships)

    def remaining(self) -> int:
        return sum(1 for s in self.ships if not self.sunk(s))


def _locked(fn):
    """Handy (Webserver-Thread) und PC (Oberfläche) ändern denselben Spielstand – immer nur einer gleichzeitig."""
    @functools.wraps(fn)
    def wrapper(self, *args, **kwargs):
        with self.lock:
            return fn(self, *args, **kwargs)
    return wrapper


class Battleship:
    """Spielstand. Phasen: „setzen“ (beide verteilen ihre Schiffe) → „spielen“ → „ende“."""

    lock = threading.RLock()

    def __init__(self, rng: random.Random | None = None):
        self.rng = rng or random.Random()
        self.fleets = {1: Fleet(), 2: Fleet()}
        self.ready = {1: False, 2: False}
        self.names = {1: "Spieler 1", 2: "Spieler 2"}
        self.phase = "setzen"
        self.turn = 1
        self.winner = 0
        self.message = "Schiffe setzen – Spieler 1 am PC, Spieler 2 auf Monitor 2"
        self.last = {1: None, 2: None}  # letzter Schuss je Schütze: (x, y, Ergebnis)
        self.token = secrets.token_urlsafe(6)  # fürs Handy von Spieler 2 (nur übers AluPC-WLAN)
        self.p2_phone = False  # Spieler 2 hat sich mit dem Handy angemeldet
        self.p2_client = ""  # Adresse dieses Handys (ein zweites Handy darf nicht übernehmen)
        self.cursor = (0, 0)  # Tastatur-Spieler 2: gewähltes Feld
        self.horizontal = {1: True, 2: True}
        self.picked: dict[int, int | None] = {1: None, 2: None}  # aufgenommenes Schiff (Länge) – wird als nächstes gesetzt
        self.version = 0  # zählt hoch bei jeder Änderung (Handy/Anzeige neu zeichnen)

    @staticmethod
    def other(p: int) -> int:
        return 2 if p == 1 else 1

    def _changed(self, msg: str | None = None) -> None:
        if msg is not None:
            self.message = msg
        self.version += 1

    # ---- Setzen
    @_locked
    def place(self, p: int, x: int, y: int, horizontal: bool | None = None, length: int | None = None) -> bool:
        if self.phase != "setzen" or self.ready[p]:
            return False
        if length is None and self.picked[p] in self.fleets[p].remaining_lengths():
            length = self.picked[p]
        ok = self.fleets[p].place(x, y, self.horizontal[p] if horizontal is None else horizontal, length)
        if ok:
            self.picked[p] = None
            self._changed()
        return ok

    @_locked
    def remove(self, p: int, x: int, y: int) -> list[tuple[int, int]] | None:
        """Gesetztes Schiff aufnehmen (Handy: antippen, PC: anklicken) – danach woanders neu setzen."""
        if self.phase != "setzen" or self.ready[p]:
            return None
        ship = self.fleets[p].remove_at((x, y))
        if ship is not None:
            self.picked[p] = len(ship)
            self.horizontal[p] = len(ship) < 2 or ship[0][1] == ship[1][1]
            self._changed()
        return ship

    @_locked
    def rotate(self, p: int) -> None:
        self.horizontal[p] = not self.horizontal[p]
        self._changed()

    @_locked
    def randomize(self, p: int) -> None:
        if self.phase != "setzen" or self.ready[p]:
            return
        self.fleets[p].randomize(self.rng)
        self._changed()

    @_locked
    def undo(self, p: int) -> None:
        if self.phase == "setzen" and not self.ready[p]:
            self.fleets[p].undo()
            self._changed()

    @_locked
    def set_ready(self, p: int) -> bool:
        if self.phase != "setzen" or not self.fleets[p].complete():
            return False
        self.ready[p] = True
        if all(self.ready.values()):
            self.phase = "spielen"
            self.turn = self.rng.choice((1, 2))
            self._changed(f"Los geht's – {self.names[self.turn]} beginnt")
        else:
            self._changed(f"{self.names[p]} ist bereit – warte auf {self.names[self.other(p)]}")
        return True

    # ---- Schießen
    @_locked
    def shoot(self, p: int, x: int, y: int) -> str:
        """Ergebnis: „wasser“, „treffer“, „versenkt“, „sieg“ – oder „" (nicht erlaubt)."""
        if self.phase != "spielen" or self.turn != p or not (0 <= x < SIZE and 0 <= y < SIZE):
            return ""
        target = self.fleets[self.other(p)]
        cell = (x, y)
        if cell in target.hits or cell in target.misses:
            return ""
        ship = target.ship_at(cell)
        if ship is None:
            target.misses.add(cell)
            result = "wasser"
            self.turn = self.other(p)
            msg = f"{self.names[p]}: {cell_name(x, y)} – Wasser. {self.names[self.turn]} ist dran"
        else:
            target.hits.add(cell)
            if target.all_sunk():
                result = "sieg"
                self.phase = "ende"
                self.winner = p
                msg = f"🏆 {self.names[p]} gewinnt!"
            elif target.sunk(ship):
                result = "versenkt"
                msg = f"{self.names[p]}: {cell_name(x, y)} – {SHIP_NAMES[len(ship)]} versenkt! Nochmal"
            else:
                result = "treffer"
                msg = f"{self.names[p]}: {cell_name(x, y)} – Treffer! Nochmal"
        self.last[p] = (x, y, result)
        self._changed(msg)
        return result

    @_locked
    def move_cursor(self, dx: int, dy: int) -> None:
        x, y = self.cursor
        self.cursor = (max(0, min(SIZE - 1, x + dx)), max(0, min(SIZE - 1, y + dy)))
        self._changed()

    @_locked
    def release_phone(self) -> None:
        """Am PC: Handy von Spieler 2 abmelden (ein anderes darf dann beitreten, sonst Tastatur)."""
        self.p2_client, self.p2_phone, self.names[2] = "", False, "Spieler 2"
        self._changed("Spieler 2: Handy abgemeldet – Pfeiltasten + Enter oder neues Handy")

    @_locked
    def restart(self) -> None:
        keep = self.names, self.token, self.p2_phone, self.p2_client
        self.__init__(self.rng)
        self.names, self.token, self.p2_phone, self.p2_client = keep
        self._changed()

    # ---- Ansichten
    @_locked
    def ghost(self, p: int, x: int, y: int) -> tuple[list[tuple[int, int]], bool]:
        """Vorschau beim Setzen: Felder des nächsten Schiffs an (x, y) und ob es dort passt."""
        left = self.fleets[p].remaining_lengths()
        length = self.picked[p] if self.picked[p] in left else (left[0] if left else None)
        if self.phase != "setzen" or self.ready[p] or length is None:
            return [], False
        cells = ship_cells(x, y, length, self.horizontal[p])
        return cells, self.fleets[p].can_place(cells)

    @_locked
    def view(self, p: int) -> dict:
        """Was Spieler p sehen darf: eigene Schiffe + Treffer darauf, und vom Gegner NUR die eigenen Schüsse
        (versenkte Schiffe werden aufgedeckt)."""
        own, enemy = self.fleets[p], self.fleets[self.other(p)]
        sunk_cells = [list(c) for s in enemy.ships if enemy.sunk(s) for c in s]
        return {
            "phase": self.phase, "turn": self.turn, "me": p, "winner": self.winner, "message": self.message,
            "name": self.names[p], "other": self.names[self.other(p)], "ready": self.ready[p],
            "other_ready": self.ready[self.other(p)], "next": own.next_length(), "horizontal": self.horizontal[p],
            "left_ships": own.remaining_lengths(),
            "own": {"ships": [[list(c) for c in s] for s in own.ships], "hits": sorted(map(list, own.hits)),
                    "misses": sorted(map(list, own.misses))},
            "target": {"hits": sorted(map(list, enemy.hits)), "misses": sorted(map(list, enemy.misses)),
                       "sunk": sunk_cells, "left": enemy.remaining() if enemy.ships else len(SHIPS)},
            "version": self.version,
        }

    @_locked
    def phone_action(self, data: dict, client: str = "") -> dict | None:
        """Handy von Spieler 2: {action: join|random|rotate|undo|clear|place|remove|ready|shoot, x, y, h, len, name}.
        Nur EIN Handy ist Spieler 2 (das erste, das beitritt) – andere bekommen None."""
        if self.p2_client and client != self.p2_client:
            return None
        action = str(data.get("action", ""))
        if action == "join":
            self.p2_client = client
            name = str(data.get("name") or "").strip()[:16]
            if name:
                self.names[2] = name
            self.p2_phone = True
            self._changed(f"{self.names[2]} spielt mit dem Handy")
        elif action == "random":
            self.randomize(2)
        elif action == "rotate":
            self.rotate(2)
        elif action == "undo":
            self.undo(2)
        elif action == "clear":
            if self.phase == "setzen" and not self.ready[2]:
                self.fleets[2].ships = []
                self._changed()
        elif action == "ready":
            self.set_ready(2)
        elif action in ("place", "shoot", "remove"):
            try:
                x, y = int(data.get("x")), int(data.get("y"))
                length = int(data["len"]) if data.get("len") is not None else None
            except (TypeError, ValueError):
                return {"ok": False, **self.view(2)}
            if action == "remove":
                ship = self.remove(2, x, y)
                return {"ok": ship is not None, "removed": [list(c) for c in ship or []], **self.view(2)}
            h = data.get("h")
            ok = self.place(2, x, y, h if isinstance(h, bool) else None, length) if action == "place" \
                else bool(self.shoot(2, x, y))
            return {"ok": ok, **self.view(2)}
        return {"ok": True, **self.view(2)}


PHONE_PAGE = r"""<!doctype html><html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no,viewport-fit=cover">
<title>AluPC – Schiffe versenken</title><style>
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
html,body{margin:0;height:100%;overscroll-behavior:none}
body{font-family:system-ui,-apple-system,sans-serif;background:#0b1020;color:#f1f5f9;
padding:max(12px,env(safe-area-inset-top)) 14px max(14px,env(safe-area-inset-bottom));display:flex;flex-direction:column;
gap:10px;align-items:center;-webkit-user-select:none;user-select:none}
h1{margin:0;font-size:20px}
.msg{width:min(94vw,560px);font-size:17px;font-weight:800;text-align:center;padding:10px 14px;border-radius:16px;
background:#1e293b}
.msg.turn{background:linear-gradient(135deg,#16a34a,#0d9488)}.msg.win{background:linear-gradient(135deg,#ca8a04,#db2777)}
.sub{font-size:13px;font-weight:600;opacity:.8;display:block;margin-top:2px}
.board{--s:min(92vw,58dvh,560px);display:flex;flex-direction:column;gap:4px;align-items:center}
label{font-size:13px;color:#94a3b8;font-weight:700;text-align:center}
.grid{display:grid;grid-template-columns:repeat(10,minmax(0,1fr));grid-template-rows:repeat(10,minmax(0,1fr));gap:3px;
width:var(--s);height:var(--s);touch-action:none}
.c{border-radius:22%;background:#1e3a5f;border:0;padding:0;font-size:calc(var(--s)/17);font-weight:900;color:#fff;
display:flex;align-items:center;justify-content:center;line-height:1;min-width:0;min-height:0;overflow:hidden;pointer-events:none}
.c.ship{background:#94a3b8}.c.hit{background:#ef4444}.c.sunk{background:#7f1d1d;color:#fca5a5}
.c.miss{background:#0f1e33;color:#38bdf8}.c.ship.hit{background:#b91c1c}
.c.gok{background:#22c55e;box-shadow:inset 0 0 0 3px #bbf7d0}.c.gbad{background:#ef4444;box-shadow:inset 0 0 0 3px #fecaca}
.c.ship.gbad{background:#b91c1c}
.small{--s:min(56vw,30dvh,300px)}.small .c{font-size:calc(var(--s)/14)}
.grid.go .c:not(.hit):not(.miss):not(.sunk){background:#24507d}
.panel{display:flex;flex-direction:column;gap:10px;width:min(94vw,560px)}
.dock{display:flex;gap:8px;flex-wrap:wrap;justify-content:center}
.dock button{display:flex;gap:3px;align-items:center;padding:9px 10px;border-radius:14px;border:2px solid #334155;
background:#111827;color:#cbd5e1;font-weight:800;font-size:14px}
.dock button.on{border-color:#22c55e;background:#14532d;color:#fff}
.dock i{display:inline-block;width:13px;height:13px;border-radius:3px;background:#94a3b8}
.dock button.on i{background:#22c55e}
.hint{font-size:13px;color:#94a3b8;text-align:center;line-height:1.35}
.row{display:flex;gap:8px;width:100%}
button.b{flex:1;padding:14px 6px;border-radius:16px;border:0;font-size:16px;font-weight:800;color:#fff;background:#1e293b}
button.b:active{transform:scale(.97)}button.p{background:linear-gradient(135deg,#6366f1,#ec4899)}
button.ok{background:linear-gradient(135deg,#16a34a,#0d9488)}
button.b:disabled{opacity:.4}
#join{display:none;flex-direction:column;gap:12px;width:min(94vw,420px);margin-top:8vh}
#join input{font-size:20px;padding:14px;border-radius:16px;border:2px solid #334155;background:#0f172a;color:#fff}
body.joining > :not(h1):not(#join){display:none!important}body.joining #join{display:flex}
@media (orientation:landscape) and (min-width:700px){
 body{display:grid;grid-template-columns:auto minmax(260px,420px);grid-template-rows:auto auto 1fr;justify-content:center;
  align-items:start;column-gap:28px}
 h1,.msg{grid-column:1/-1;justify-self:center}
 .board{--s:min(52vw,calc(100dvh - 170px),640px)}
 body.playing .board{--s:min(44vw,calc(100dvh - 170px),640px)}
 body.playing .small{--s:min(30vw,calc(100dvh - 300px),400px)}
 body.playing{grid-template-columns:auto auto}
 .panel{width:100%}
}
</style></head><body>
<h1>🚢 Schiffe versenken</h1>
<div id="join"><input id="jname" maxlength="16" placeholder="Dein Name" autocomplete="off" enterkeyhint="go">
<button class="b p" id="jgo">Mitspielen</button><div class="hint" id="jerr"></div></div>
<div class="msg" id="msg">Verbinde …</div>
<div id="target" class="board"><label>Gegner – antippen = schießen</label><div class="grid" id="tg"></div></div>
<div id="ownbox" class="board small"><label id="ownlabel">Deine Flotte</label><div class="grid" id="og"></div></div>
<div class="panel" id="setup">
 <div class="hint" id="shint">Schiff wählen, dann aufs Feld tippen oder ziehen – grün = passt.</div>
 <div class="dock" id="dock"></div>
 <div class="row"><button class="b" id="rot">↻ Drehen</button><button class="b ok" id="set" disabled>✓ Setzen</button></div>
 <div class="row"><button class="b" id="rnd">🎲 Zufällig</button><button class="b" id="clr">🗑 Alle weg</button></div>
 <button class="b p" id="ready" style="width:100%">Bereit</button>
</div>
<script>
const u = new URLSearchParams(location.search).get("u") || "";
const N = 10, SHIPNAME = {5: "Schlachtschiff", 4: "Kreuzer", 3: "Zerstörer", 2: "U-Boot"};
let st = null, busy = false, joined = false;
let pick = 0, hor = true, anchor = null;  // Vorschau: gewählte Länge, Richtung, Startfeld (nur hier im Handy)
const $ = id => document.getElementById(id);
function store(k, v) { try { if (v === undefined) return localStorage.getItem(k) || ""; localStorage.setItem(k, v); } catch (e) { return ""; } }
function fail(t) { const m = $("msg"); m.className = "msg"; m.textContent = t; }
async function api(body) {
  if (busy) return null; busy = true;
  try {
    const r = await fetch("/api/schiffe?u=" + encodeURIComponent(u), {method: "POST", body: JSON.stringify(body)});
    if (r.status === 423) { fail("Spieler 2 spielt schon mit einem anderen Handy."); return null; }
    if (!r.ok) { fail("Das Spiel ist vorbei oder nicht mehr da."); return null; }
    st = await r.json(); draw(); return st;
  } catch (e) { fail("Keine Verbindung – im AluPC-WLAN?"); return null; } finally { busy = false; }
}
const has = (list, x, y) => list.some(c => c[0] === x && c[1] === y);
function shipCells(x, y, len, h) { const out = []; for (let i = 0; i < len; i++) out.push(h ? [x + i, y] : [x, y + i]); return out; }
function canPlace(cells) {  // wie am PC: im Feld, nicht überlappend, nicht angrenzend (auch nicht schräg)
  const taken = st.own.ships.flat();
  return cells.every(([x, y]) => x >= 0 && y >= 0 && x < N && y < N &&
    !taken.some(([a, b]) => Math.abs(a - x) <= 1 && Math.abs(b - y) <= 1));
}
function ghost() { return anchor && pick ? shipCells(anchor[0], anchor[1], pick, hor) : []; }
function left() { return (st && st.left_ships) || []; }
function fixPick() { const l = left(); if (!l.includes(pick)) { pick = l[0] || 0; anchor = null; } }
function cells(el, cls) {
  if (el.children.length !== 100) { el.innerHTML = "";
    for (let i = 0; i < 100; i++) { const b = document.createElement("div"); b.className = "c"; el.appendChild(b); } }
  [...el.children].forEach((b, i) => { const x = i % 10, y = Math.floor(i / 10); const [c, t] = cls(x, y);
    b.className = "c " + c; b.textContent = t; });
}
function cellAt(el, e) {
  const r = el.getBoundingClientRect();
  const x = Math.floor((e.clientX - r.left) / r.width * N), y = Math.floor((e.clientY - r.top) / r.height * N);
  return x >= 0 && y >= 0 && x < N && y < N ? [x, y] : null;
}
function aim(c) {  // Finger in der Mitte des Schiffs, Schiff bleibt im Feld
  const off = Math.floor((pick - 1) / 2);
  let x = c[0] - (hor ? off : 0), y = c[1] - (hor ? 0 : off);
  x = Math.max(0, Math.min(N - (hor ? pick : 1), x)); y = Math.max(0, Math.min(N - (hor ? 1 : pick), y));
  anchor = [x, y];
}
function drawSetup() {
  fixPick();
  const dock = $("dock"); dock.innerHTML = "";
  for (const [i, len] of left().entries()) {
    const b = document.createElement("button"); b.className = len === pick && (i === left().indexOf(pick)) ? "on" : "";
    b.innerHTML = "<i></i>".repeat(len); b.title = SHIPNAME[len];
    b.onclick = () => { pick = len; anchor = null; draw(); }; dock.appendChild(b);
  }
  const g = ghost(), ok = g.length && canPlace(g);
  $("set").disabled = !ok;
  $("shint").textContent = !left().length ? "Alle Schiffe gesetzt – „Bereit“ drücken. Antippen = Schiff aufnehmen."
    : !anchor ? SHIPNAME[pick] + " (" + pick + ") wählen ✓ – aufs Feld tippen oder ziehen. Gesetztes Schiff antippen = verschieben."
    : ok ? "Passt – „✓ Setzen“ oder nochmal aufs Schiff tippen." : "Geht hier nicht (Rand oder zu nah an einem Schiff) – woanders hin.";
  $("ready").disabled = left().length > 0;
}
function draw() {
  if (!st || !joined) return;
  const own = st.own, t = st.target, setting = st.phase === "setzen", mine = st.phase === "spielen" && st.turn === 2;
  const ships = own.ships.flat(), edit = setting && !st.ready;
  let head, cls = "msg";
  if (st.phase === "ende") { head = st.winner === 2 ? "🏆 Gewonnen!" : "Verloren – " + st.other + " gewinnt"; cls += " win"; }
  else if (setting) head = st.ready ? "Bereit – warte auf " + st.other : left().length ? "Schiffe setzen (" + (5 - left().length) + " von 5)" : "Alle Schiffe gesetzt";
  else if (mine) { head = "Du bist dran – schieß!"; cls += " turn"; }
  else head = st.other + " ist dran …";
  const m = $("msg"); m.className = cls; m.innerHTML = ""; m.append(head);
  if (!setting) { const s = document.createElement("span"); s.className = "sub"; s.textContent = st.message + " · Gegner hat noch " + t.left + " Schiffe"; m.append(s); }
  document.body.classList.toggle("playing", !setting);
  $("setup").style.display = edit ? "flex" : "none";
  $("target").style.display = setting ? "none" : "flex";
  $("ownbox").className = setting ? "board" : "board small";
  $("ownlabel").textContent = setting ? "Deine Flotte" : "Deine Flotte";
  if (edit) drawSetup();
  const g = edit ? ghost() : [], gok = g.length && canPlace(g);
  cells($("og"), (x, y) => {
    if (has(g, x, y)) return [(has(ships, x, y) ? "ship " : "") + (gok ? "gok" : "gbad"), ""];
    return has(own.hits, x, y) ? ["ship hit", "✕"] : has(own.misses, x, y) ? ["miss", "•"] : has(ships, x, y) ? ["ship", ""] : ["", ""]; });
  const tg = $("tg"); tg.classList.toggle("go", mine);
  cells(tg, (x, y) => has(t.sunk, x, y) ? ["sunk", "✕"] : has(t.hits, x, y) ? ["hit", "✕"] : has(t.misses, x, y) ? ["miss", "•"] : ["", ""]);
}
async function place() {
  const g = ghost(); if (!g.length || !canPlace(g)) return;
  if (navigator.vibrate) navigator.vibrate(20);
  const a = anchor, len = pick; anchor = null;
  const r = await api({action: "place", x: a[0], y: a[1], h: hor, len});
  if (r && !r.ok) { anchor = a; draw(); }
}
// Eigenes Feld: tippen/ziehen = Vorschau, Tippen in die passende Vorschau = setzen, Tippen auf ein Schiff = aufnehmen
let downAt = null, moved = false, onGhost = false;
$("og").addEventListener("pointerdown", e => {
  if (!st || st.phase !== "setzen" || st.ready) return;
  const c = cellAt($("og"), e); if (!c) return;
  e.preventDefault(); $("og").setPointerCapture(e.pointerId); downAt = c; moved = false;
  onGhost = has(ghost(), c[0], c[1]);  // nur ein Tipp in eine SCHON gezeigte Vorschau setzt das Schiff
  if (!onGhost && !has(st.own.ships.flat(), c[0], c[1]) && pick) { aim(c); draw(); }
});
$("og").addEventListener("pointermove", e => {
  if (!downAt || !pick) return; const c = cellAt($("og"), e);
  if (c && (c[0] !== downAt[0] || c[1] !== downAt[1])) { moved = true; aim(c); draw(); }
});
$("og").addEventListener("pointerup", async e => {
  const c = downAt; downAt = null; if (!c || moved) return;
  const ship = st.own.ships.find(s => has(s, c[0], c[1]));
  if (onGhost && canPlace(ghost())) return place();
  if (ship && !onGhost) {  // aufnehmen: an derselben Stelle als Vorschau, zum Verschieben
    const h = ship.length < 2 || ship[0][1] === ship[1][1];
    const r = await api({action: "remove", x: c[0], y: c[1]});
    if (r && r.ok) { pick = ship.length; hor = h; anchor = ship[0].slice(); if (navigator.vibrate) navigator.vibrate(15); draw(); }
  }
});
$("tg").addEventListener("click", e => {
  const c = cellAt($("tg"), e); if (!c || !st) return; const t = st.target;
  if (st.turn === 2 && st.phase === "spielen" && !has(t.hits, c[0], c[1]) && !has(t.misses, c[0], c[1])) {
    if (navigator.vibrate) navigator.vibrate(30); api({action: "shoot", x: c[0], y: c[1]}); }
});
$("rot").onclick = () => { hor = !hor; if (anchor) { const a = anchor; aim([a[0], a[1]]); } draw(); };
$("set").onclick = place;
$("rnd").onclick = () => { anchor = null; api({action: "random"}); };
$("clr").onclick = () => { anchor = null; api({action: "clear"}); };
$("ready").onclick = () => api({action: "ready"});
async function join(name) {
  store("alupc-name", name); const r = await api({action: "join", name});
  if (r) { joined = true; document.body.classList.remove("joining"); draw(); }
  else $("jerr").textContent = $("msg").textContent;
}
$("jname").value = store("alupc-name");
$("jgo").onclick = () => { const n = $("jname").value.trim(); if (!n) { $("jname").focus(); return; } join(n); };
$("jname").addEventListener("keydown", e => { if (e.key === "Enter") $("jgo").click(); });
if (store("alupc-name")) join(store("alupc-name")); else document.body.classList.add("joining");
setInterval(async () => { if (busy || !joined) return; try { const r = await fetch("/api/schiffe?u=" + encodeURIComponent(u));
  if (r.ok) { const s = await r.json(); if (!st || s.version !== st.version) { const was = st && st.turn; st = s; draw();
    if (was === 1 && s.turn === 2 && navigator.vibrate) navigator.vibrate([60, 60, 60]); } } } catch (e) {} }, 700);
</script></body></html>"""
