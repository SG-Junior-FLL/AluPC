"""Schiffe versenken – zwei Spieler, zwei Bildschirme.

Spieler 1 spielt am PC (Fenster auf Monitor 1, Maus), Spieler 2 auf Monitor 2 (Beamer) – das Handy (über das
AluPC-WLAN) ist dabei nur die Steuerung (Steuerkreuz, OK, Drehen …), die Felder zeigt nur Monitor 2. Ohne Handy
gehen auch die Pfeiltasten + Enter am PC. Jeder Bildschirm zeigt nur die EIGENEN Schiffe; vom Gegner sieht man
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
        self.message = "Schiffe setzen – Spieler 1 am PC, Spieler 2 auf dem Bildschirm"
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
            "cursor": list(self.cursor),  # Feld, das Spieler 2 am Handy/Tastatur gewählt hat (zeigt Monitor 2)
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
        elif action == "move":  # Steuerkreuz am Handy – das Feld zeigt Monitor 2
            try:
                dx, dy = int(data.get("dx", 0)), int(data.get("dy", 0))
            except (TypeError, ValueError):
                dx = dy = 0
            self.move_cursor(max(-1, min(1, dx)), max(-1, min(1, dy)))
        elif action == "ok":  # OK am Handy: setzen (auf einem Schiff: aufnehmen) bzw. schießen
            x, y = self.cursor
            if self.phase == "setzen":
                ok = self.remove(2, x, y) is not None if self.fleets[2].ship_at((x, y)) else self.place(2, x, y)
            else:
                ok = bool(self.shoot(2, x, y))
            return {"ok": ok, "cursor": list(self.cursor), "last": self.last[2], **self.view(2)}
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
        return {"ok": True, "cursor": list(self.cursor), "last": self.last[2], **self.view(2)}


PHONE_PAGE = r"""<!doctype html><html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no,viewport-fit=cover">
<title>AluPC – Schiffe versenken</title><style>
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
html,body{margin:0;height:100%;overscroll-behavior:none}
body{font-family:system-ui,-apple-system,sans-serif;background:#16181c;color:#eceef1;touch-action:manipulation;
padding:max(12px,env(safe-area-inset-top)) 14px max(14px,env(safe-area-inset-bottom));display:flex;flex-direction:column;
gap:12px;align-items:center;-webkit-user-select:none;user-select:none}
h1{margin:0;font-size:20px}
.msg{width:min(94vw,520px);font-size:18px;font-weight:800;text-align:center;padding:12px 14px;border-radius:16px;background:#292d33}
.msg.turn{background:linear-gradient(135deg,#16a34a,#0d9488)}.msg.win{background:linear-gradient(135deg,#ca8a04,#db2777)}
.sub{font-size:13px;font-weight:600;opacity:.85;display:block;margin-top:3px}
.hint{font-size:13px;color:#9aa1ac;text-align:center}
.pad{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;width:min(80vw,46dvh,340px);aspect-ratio:1}
.pad button,.b{border:0;border-radius:20px;font-weight:900;color:#fff;background:#292d33;font-size:30px}
.pad button:active,.b:active{transform:scale(.95);background:#363b42}
.pad .ok{background:linear-gradient(135deg,#5b8def,#ec4899);font-size:20px}
.pad .ok.fire{background:linear-gradient(135deg,#dc2626,#f97316)}
.pad .e{visibility:hidden}
.row{display:flex;gap:10px;width:min(94vw,520px)}
.b{flex:1;padding:14px 6px;font-size:16px;border-radius:16px}
.b.p{background:linear-gradient(135deg,#16a34a,#0d9488)}.b:disabled{opacity:.4}
.cell{font-size:15px;font-weight:800;color:#a5b4fc}
#join{display:none;flex-direction:column;gap:12px;width:min(94vw,420px);margin-top:8vh}
#join input{font-size:20px;padding:14px;border-radius:16px;border:2px solid #363b42;background:#1f2227;color:#fff}
body.joining > :not(h1):not(#join){display:none!important}body.joining #join{display:flex}
@media (orientation:landscape) and (min-width:700px){body{display:grid;grid-template-columns:1fr 1fr;align-items:center;
 justify-items:center;column-gap:28px}h1,.msg{grid-column:1/-1}.pad{width:min(40vw,62dvh,380px)}#side{display:flex;
 flex-direction:column;gap:10px;width:100%}#side .row{width:100%}}
</style></head><body>
<h1>🚢 Schiffe versenken</h1>
<div id="join"><input id="jname" maxlength="16" placeholder="Dein Name" autocomplete="off" enterkeyhint="go">
<button class="b p" id="jgo">Mitspielen</button><div class="hint">Die Felder siehst du auf dem Bildschirm – das Handy ist die Steuerung.</div>
<div class="hint" id="jerr"></div></div>
<div class="msg" id="msg">Verbinde …</div>
<div class="pad" id="pad">
 <button class="e"></button><button data-d="0,-1">▲</button><button class="e"></button>
 <button data-d="-1,0">◀</button><button class="ok" id="ok">OK</button><button data-d="1,0">▶</button>
 <button class="e"></button><button data-d="0,1">▼</button><button class="e"></button>
</div>
<div id="side">
 <div class="hint"><span class="cell" id="cell">A1</span> · <span id="what">Schau auf den Bildschirm</span></div>
 <div class="row" id="setup1"><button class="b" id="rot">↻ Drehen</button><button class="b" id="rnd">🎲 Zufällig</button></div>
 <div class="row" id="setup2"><button class="b" id="undo">↶ Zurück</button><button class="b p" id="ready">Bereit</button></div>
</div>
<script>
const u = new URLSearchParams(location.search).get("u") || "";
const L = "ABCDEFGHIJ";
let st = null, busy = false, joined = false;
const $ = id => document.getElementById(id);
function store(k, v) { try { if (v === undefined) return localStorage.getItem(k) || ""; localStorage.setItem(k, v); } catch (e) { return ""; } }
function fail(t) { $("msg").className = "msg"; $("msg").textContent = t; }
async function api(body) {
  if (busy) return null; busy = true;
  try {
    const r = await fetch("/api/schiffe?u=" + encodeURIComponent(u), {method: "POST", body: JSON.stringify(body)});
    if (r.status === 423) { fail("Spieler 2 spielt schon mit einem anderen Handy."); return null; }
    if (!r.ok) { fail("Das Spiel ist vorbei oder nicht mehr da."); return null; }
    const d = await r.json(); st = Object.assign(st || {}, d); draw(); return d;
  } catch (e) { fail("Keine Verbindung – im AluPC-WLAN?"); return null; } finally { busy = false; }
}
function buzz(p) { if (navigator.vibrate) navigator.vibrate(p); }
function draw() {
  if (!st || !joined) return;
  const setting = st.phase === "setzen", mine = st.phase === "spielen" && st.turn === 2, edit = setting && !st.ready;
  let head, cls = "msg";
  if (st.phase === "ende") { head = st.winner === 2 ? "🏆 Gewonnen!" : "Verloren – " + st.other + " gewinnt"; cls += " win"; }
  else if (setting) head = st.ready ? "Bereit – warte auf " + st.other : st.next ? "Schiff setzen: Länge " + st.next : "Alle gesetzt – „Bereit“";
  else if (mine) { head = "Du bist dran – schieß!"; cls += " turn"; }
  else head = st.other + " ist dran …";
  const m = $("msg"); m.className = cls; m.innerHTML = ""; m.append(head);
  if (!setting) { const s = document.createElement("span"); s.className = "sub"; s.textContent = st.message; m.append(s); }
  const c = st.cursor || [0, 0]; $("cell").textContent = L[c[0]] + (c[1] + 1);
  $("what").textContent = edit ? "OK = setzen · auf einem Schiff: aufnehmen" : mine ? "OK = schießen" : "Schau auf den Bildschirm";
  $("ok").textContent = mine ? "🎯" : "OK"; $("ok").classList.toggle("fire", mine);
  $("setup1").style.display = $("setup2").style.display = edit ? "flex" : "none";
  $("ready").disabled = !!st.next;
}
for (const b of document.querySelectorAll("#pad [data-d]")) b.onclick = () => {
  const [dx, dy] = b.dataset.d.split(",").map(Number); buzz(8); api({action: "move", dx, dy}); };
$("ok").onclick = async () => { buzz(20); const was = st && st.turn; const d = await api({action: "ok"});
  if (d && d.last && st.phase !== "setzen" && was === 2) { const r = d.last[2]; if (r === "treffer" || r === "versenkt" || r === "sieg") buzz([80, 40, 80]); } };
$("rot").onclick = () => api({action: "rotate"});
$("rnd").onclick = () => api({action: "random"});
$("undo").onclick = () => api({action: "undo"});
$("ready").onclick = () => api({action: "ready"});
async function join(name) {
  store("alupc-name", name); const r = await api({action: "join", name});
  if (r) { joined = true; document.body.classList.remove("joining"); draw(); } else $("jerr").textContent = $("msg").textContent;
}
$("jname").value = store("alupc-name");
$("jgo").onclick = () => { const n = $("jname").value.trim(); if (!n) { $("jname").focus(); return; } join(n); };
$("jname").addEventListener("keydown", e => { if (e.key === "Enter") $("jgo").click(); });
if (store("alupc-name")) join(store("alupc-name")); else document.body.classList.add("joining");
setInterval(async () => { if (busy || !joined) return; try { const r = await fetch("/api/schiffe?u=" + encodeURIComponent(u));
  if (r.ok) { const s = await r.json(); if (!st || s.version !== st.version) { const was = st && st.turn; st = Object.assign(st || {}, s); draw();
    if (was === 1 && s.turn === 2) buzz([60, 60, 60]); } } } catch (e) {} }, 700);
</script></body></html>"""
