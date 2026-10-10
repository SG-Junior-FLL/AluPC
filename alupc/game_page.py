"""Handy-Bedienfeld der Minispiele (eine Seite für alle Spiele).

Schnelle Verbindung: WebSocket (/ws/spiel) – Eingaben gehen sofort raus, der Stand kommt ohne Nachfragen zurück.
Klappt das nicht (alter Browser, Netz), fragt die Seite den Stand alle 0,4 s ab und schickt Eingaben per POST.
"""

GAME_PAGE = r"""<!doctype html>
<html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no, viewport-fit=cover">
<meta name="theme-color" content="#0b1020"><title>AluPC – Spiel</title>
<style>
:root { color-scheme: dark; --c: #3b82f6; }
* { box-sizing: border-box; -webkit-tap-highlight-color: transparent; user-select: none; -webkit-user-select: none; }
html, body { margin: 0; height: 100%; overflow: hidden; overscroll-behavior: none; touch-action: manipulation; }
body { font-family: system-ui, -apple-system, "Segoe UI", sans-serif; color: #f1f5f9;
  background: radial-gradient(circle at 50% 0%, #1e293b 0, #0b1020 70%); display: flex; flex-direction: column; }
header { padding: 14px 16px 6px; display: flex; align-items: center; gap: 10px; }
.dot { width: 16px; height: 16px; border-radius: 50%; background: var(--c); box-shadow: 0 0 14px var(--c); flex: none; }
header b { font-size: 18px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
header span { color: #94a3b8; font-size: 13px; margin-left: auto; white-space: nowrap; }
#net { width: 8px; height: 8px; border-radius: 50%; background: #64748b; flex: none; }
#net.on { background: #22c55e; }
main { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center;
  padding: 8px 16px 20px; gap: 14px; min-height: 0; }
h1 { font-size: 26px; margin: 0; text-align: center; }
p { color: #94a3b8; text-align: center; margin: 0; font-size: 15px; line-height: 1.4; }
input { font: inherit; font-size: 20px; padding: 14px 16px; border-radius: 14px; border: 2px solid #334155; background: #0f172a;
  color: #fff; width: 100%; max-width: 380px; text-align: center; -webkit-user-select: text; user-select: text; }
button { font: inherit; font-weight: 700; border: 0; color: #fff; cursor: pointer; touch-action: manipulation; }
button:disabled { opacity: .35; }
.primary { font-size: 20px; padding: 16px 28px; border-radius: 16px; background: var(--c); width: 100%; max-width: 380px; }
.status { font-size: 21px; font-weight: 800; text-align: center; min-height: 28px; }
.big { font-size: 64px; font-weight: 900; text-align: center; line-height: 1.05; word-break: break-word;
  animation: pop .35s cubic-bezier(.2,1.6,.4,1); }
.big.good { color: #4ade80; } .big.bad { color: #f87171; }
@keyframes pop { from { transform: scale(.6); opacity: 0; } to { transform: scale(1); opacity: 1; } }
.tap { width: min(78vw, 54vh); height: min(78vw, 54vh); border-radius: 50%; font-size: 34px; letter-spacing: 1px;
  background: radial-gradient(circle at 35% 30%, color-mix(in srgb, var(--c) 70%, #fff), var(--c));
  box-shadow: 0 14px 40px color-mix(in srgb, var(--c) 45%, transparent), inset 0 -8px 0 rgba(0,0,0,.18); }
.tap.go { --c: #16a34a; } .tap.wait { --c: #b91c1c; }
.hit { transform: scale(.94); filter: brightness(1.2); }
.pad { display: grid; grid-template-columns: repeat(3, min(26vw, 18vh)); grid-template-rows: repeat(3, min(26vw, 18vh)); gap: 10px; }
.pad button { border-radius: 22px; background: #1e293b; font-size: 34px; border: 2px solid #334155; }
.pad button.hit { background: var(--c); border-color: var(--c); }
.grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; width: 100%; max-width: 420px; }
.grid button { border-radius: 18px; background: #1e293b; border: 2px solid #334155; font-size: 26px; padding: 26px 8px; }
.grid button.hit { background: #f1f5f9; color: #0b1020; }
.grid.column { grid-template-columns: 1fr; gap: 10px; }
.ttt { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; width: min(92vw, 420px); aspect-ratio: 1; margin: 0 auto; }
.ttt button { font-size: min(18vw, 84px); font-weight: 900; border-radius: 16px; border: 2px solid #334155; background: #1e293b; color: #fff; padding: 0; line-height: 1; }
.ttt button.set.X { color: #ef4444; } .ttt button.set.O { color: #3b82f6; }
.ttt button.vote { border-color: var(--c); color: color-mix(in srgb, var(--c) 60%, transparent); background: color-mix(in srgb, var(--c) 18%, #1e293b); }
.ttt button.win { background: color-mix(in srgb, #facc15 30%, #1e293b); border-color: #facc15; }
.ttt.off button:not(.set) { opacity: .45; }
.grid.column button { font-size: 30px; padding: 22px 8px; }
.simon { grid-template-columns: 1fr 1fr; gap: 14px; max-width: min(420px, 52vh); }
.simon button { aspect-ratio: 1; border: 0; padding: 0; background: var(--b); filter: saturate(.75) brightness(.7); }
.simon button.hit { filter: saturate(1.2) brightness(1.3); box-shadow: 0 0 40px var(--b); }
.track { position: relative; width: min(52vw, 260px); height: min(62vh, 520px); border-radius: 28px; background: #1e293b;
  border: 2px solid #334155; touch-action: none; }
.thumb { position: absolute; left: 8px; right: 8px; height: 26%; border-radius: 20px; background: var(--c);
  box-shadow: 0 0 24px var(--c); top: 37%; }
.tet { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; width: min(94vw, 440px); }
.tet button { border-radius: 20px; background: #1e293b; border: 2px solid #334155; font-size: 34px; padding: 0;
  height: min(17vh, 120px); touch-action: none; }
.tet button.row { grid-column: span 3; height: min(11vh, 80px); }
.tet button.wide { grid-column: span 3; height: min(13vh, 90px); font-size: 26px; font-weight: 800; background: var(--c); border-color: var(--c); }
.tet button.hit { background: var(--c); border-color: var(--c); }
.nextp { display: grid; grid-template-columns: repeat(4, 14px); grid-auto-rows: 14px; gap: 2px; }
.nextp span { border-radius: 3px; } .nextrow { display: flex; align-items: center; gap: 10px; color: #94a3b8; font-size: 14px; }
#area { width: 100%; display: flex; flex-direction: column; align-items: center; gap: 14px; min-height: 0; }
.bbox { height: 34vh; display: flex; align-items: flex-end; justify-content: center; padding-bottom: 8px; }
.avatars { display: grid; grid-template-columns: repeat(7, 1fr); gap: 6px; width: 100%; max-width: 380px; }
.avatars button { font-size: 26px; padding: 6px 0; border-radius: 12px; background: #1e293b; border: 2px solid transparent; }
.avatars button.sel { border-color: var(--c); background: #334155; }
#ava { font-size: 22px; line-height: 1; }
.c4 { display: grid; grid-template-columns: repeat(7, 1fr); gap: 5px; width: min(94vw, 460px); padding: 8px;
  border-radius: 18px; background: #334155; touch-action: none; }
.c4 span { aspect-ratio: 1; border-radius: 50%; background: #0b1020; }
.c4 span.X { background: #ef4444; } .c4 span.O { background: #3b82f6; }
.c4 span.win { box-shadow: 0 0 0 4px #facc15; }
.c4cols { display: grid; grid-template-columns: repeat(7, 1fr); gap: 5px; width: min(94vw, 460px); padding: 0 8px; }
.c4cols button { height: min(13vh, 90px); border-radius: 14px; background: #1e293b; border: 2px solid #334155; font-size: 26px; padding: 0; }
.c4cols button.vote { background: var(--c); border-color: var(--c); }
.c4.off { opacity: .7; }
.htrack { position: relative; width: min(94vw, 460px); height: min(16vh, 110px); border-radius: 26px; background: #1e293b;
  border: 2px solid #334155; touch-action: none; }
.hthumb { position: absolute; top: 8px; bottom: 8px; width: 22%; border-radius: 18px; background: var(--c); box-shadow: 0 0 24px var(--c); left: 39%; }
.fire { width: min(94vw, 460px); height: min(26vh, 200px); border-radius: 26px; font-size: 34px; letter-spacing: 2px;
  background: radial-gradient(circle at 40% 30%, #fb7185, #e11d48); box-shadow: 0 12px 34px rgba(225,29,72,.45); touch-action: none; }
.hidden { display: none !important; }
</style></head><body>
<header><div class="dot" id="dot"></div><span id="ava"></span><b id="who">AluPC-Spiel</b><span id="count"></span><i id="net"></i></header>
<main id="join">
  <h1 id="jtitle">Mitspielen</h1><p id="jhelp"></p>
  <input id="name" maxlength="16" placeholder="Dein Name" autocomplete="off">
  <div class="avatars" id="avatars"></div>
  <button class="primary" id="joinbtn">Mitspielen</button><p id="jerr"></p>
</main>
<main id="play" class="hidden"><div class="status" id="status"></div><div id="area"></div></main>
<script>
const token = new URLSearchParams(location.search).get("u") || "";
const KEY = "alupc-spiel-" + token;
let pid = ""; try { pid = sessionStorage.getItem(KEY) || ""; } catch (e) {}
let state = {}, cur = "", comp = null, ws = null, wsOpen = false, poller = null;
const $ = id => document.getElementById(id);
const enc = encodeURIComponent;
function el(tag, cls, text) { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
function vibrate(ms) { try { navigator.vibrate && navigator.vibrate(ms); } catch (e) {} }
function hit(e) { e.classList.add("hit"); setTimeout(() => e.classList.remove("hit"), 110); }
function press(e, fn) {  // sofort beim Berühren (nicht erst beim Loslassen)
  e.addEventListener("touchstart", ev => { ev.preventDefault(); if (!e.disabled) { fn(); hit(e); } }, {passive: false});
  e.addEventListener("mousedown", () => { if (!e.disabled) { fn(); hit(e); } });
}
function post(body) {
  return fetch("/api/spiel", {method: "POST", headers: {"Content-Type": "application/json"}, keepalive: true,
    body: JSON.stringify(Object.assign({u: token, p: pid}, body))});
}
function send(obj) {
  if (ws && ws.readyState === 1) ws.send(JSON.stringify(obj));
  else post(Object.assign({action: "input"}, obj)).catch(() => {});
}
// ---------------------------------------------------------------- Verbindung
function connect() {
  if (!pid || ws) return;
  try { ws = new WebSocket((location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/ws/spiel?u=" + enc(token) + "&p=" + enc(pid)); }
  catch (e) { ws = null; return; }
  ws.onopen = () => { wsOpen = true; $("net").classList.add("on"); };
  ws.onmessage = ev => { try { render(JSON.parse(ev.data)); } catch (e) {} };
  ws.onclose = () => { ws = null; wsOpen = false; $("net").classList.remove("on"); if (pid) setTimeout(connect, 1200); };
}
setInterval(() => { if (ws && ws.readyState === 1) ws.send('{"ping":1}'); }, 4000);
async function load() {
  if (wsOpen) return;
  try {
    const asked = pid;  // Antwort gehört zu diesem Stand – kam inzwischen ein Beitritt dazwischen, nicht verwenden
    const r = await fetch("/api/spiel?u=" + enc(token) + "&p=" + enc(asked), {cache: "no-store"});
    if (r.status === 404) { $("jtitle").textContent = "Keine Spielrunde"; $("jhelp").textContent = "Am PC Minispiele starten"; show(false); return; }
    const d = await r.json();
    if (asked !== pid) return;  // sonst würde „noch nicht dabei“ den frisch Beigetretenen wieder rauswerfen
    render(d);
  } catch (e) {}
}
setInterval(load, 400);
async function join() {
  const name = $("name").value.trim() || "Spieler";
  $("joinbtn").disabled = true;
  try {
    const r = await post({action: "join", name, avatar});
    const d = await r.json();
    if (!r.ok) { $("jerr").textContent = d.error || "Geht gerade nicht"; return; }
    pid = d.p; try { sessionStorage.setItem(KEY, pid); } catch (e) {}
    connect(); load();
  } catch (e) { $("jerr").textContent = "Keine Verbindung"; }
  finally { $("joinbtn").disabled = false; }
}
$("joinbtn").onclick = join;
// Von der WLAN-Anmeldeseite: Name ist schon eingegeben → gleich mitspielen
const preName = new URLSearchParams(location.search).get("name");
if (preName && !pid) { $("name").value = preName.slice(0, 16); setTimeout(join, 0); }
// Avatar wählen (zufällig vorausgewählt)
const AVATARS = ["🦊","🐼","🐸","🐯","🦁","🐨","🐷","🐵","🐙","🦄","🐲","🐧","🦉","🐝","🐢","🐬","🦖","🐱","🐶","🐰","🦀","🦋","🐻","🐮","🤖","👾","🚀","⚽"];
let avatar = AVATARS[Math.floor(Math.random() * AVATARS.length)];
try { avatar = localStorage.getItem("alupc-avatar") || avatar; } catch (e) {}
for (const a of AVATARS) {
  const b = el("button", a === avatar ? "sel" : "", a);
  b.onclick = () => { avatar = a; try { localStorage.setItem("alupc-avatar", a); } catch (e) {}
    for (const x of $("avatars").children) x.classList.toggle("sel", x === b); };
  $("avatars").append(b);
}
// Vibration (nur Android – iPhones können das im Browser nicht)
let lastBuzz = null;
function buzz(d) {
  const n = d.buzz ? d.buzz[0] : 0;
  if (lastBuzz === null) { lastBuzz = n; return; }  // erster Stand nach dem Laden: nichts nachholen
  if (n !== lastBuzz && d.buzz) vibrate(d.buzz[1]);
  lastBuzz = n;
}
$("name").addEventListener("keydown", e => { if (e.key === "Enter") join(); });
function show(playing) { $("join").classList.toggle("hidden", playing); $("play").classList.toggle("hidden", !playing); }
// ---------------------------------------------------------------- Anzeige
function render(d) {
  state = d;
  document.documentElement.style.setProperty("--c", d.color || "#3b82f6");
  $("who").textContent = d.joined ? d.name : "AluPC-Spiel";
  $("ava").textContent = d.joined ? (d.avatar || "") : "";
  $("dot").classList.toggle("hidden", !!(d.joined && d.avatar));
  if (d.joined) buzz(d);
  $("count").textContent = d.players + " dabei";
  $("jtitle").textContent = d.title || "Mitspielen"; $("jhelp").textContent = d.help || "";
  if (!d.joined) {
    if (pid) { pid = ""; try { sessionStorage.removeItem(KEY); } catch (e) {} if (ws) ws.close(); }
    show(false); cur = ""; return;
  }
  show(true);
  const ui = d.ui || {ui: "msg"};
  const key = ui.ui + "|" + (ui.rid ?? ui.tid ?? ui.qid ?? "") + "|" + (ui.layout || "") + "|" + d.game;
  if (key !== cur) { cur = key; $("area").replaceChildren(); comp = (BUILD[ui.ui] || BUILD.msg)(ui, $("area")); }
  $("status").textContent = ui.status || "";
  if (comp && comp.update) comp.update(ui);
}
const BUILD = {
  msg(ui, area) {
    const big = el("div", "big"); area.append(big);
    let last = null;
    return {update(u) { if (u.big !== last) { last = u.big; big.textContent = u.big || ""; big.className = "big " + (u.tone || "");
      big.style.animation = "none"; big.offsetWidth; big.style.animation = ""; } }};
  },
  tap(ui, area) {
    const b = el("button", "tap", ui.label); area.append(b);
    press(b, () => { send({tap: 1}); vibrate(12); });
    return {update(u) { b.textContent = u.label; b.classList.toggle("go", u.tone === "go"); b.classList.toggle("wait", u.tone === "wait");
      if (u.color) b.style.setProperty("--c", u.color); }};
  },
  pad(ui, area) {
    const pad = el("div", "pad");
    for (const [d, t] of [["", ""], ["up", "▲"], ["", ""], ["left", "◀"], ["", ""], ["right", "▶"], ["", ""], ["down", "▼"], ["", ""]]) {
      if (!d) { pad.append(el("span")); continue; }
      const b = el("button", "", t); press(b, () => { send({dir: d}); vibrate(8); }); pad.append(b);
    }
    area.append(pad);
    let sx = 0, sy = 0;
    area.addEventListener("touchstart", e => { sx = e.touches[0].clientX; sy = e.touches[0].clientY; }, {passive: true});
    area.addEventListener("touchend", e => {
      const dx = e.changedTouches[0].clientX - sx, dy = e.changedTouches[0].clientY - sy;
      if (Math.max(Math.abs(dx), Math.abs(dy)) < 30) return;
      send({dir: Math.abs(dx) > Math.abs(dy) ? (dx > 0 ? "right" : "left") : (dy > 0 ? "down" : "up")});
    });
    return {};
  },
  buttons(ui, area) {
    const g = el("div", "grid" + (["simon", "column"].includes(ui.layout) ? " " + ui.layout : "")); area.append(g);
    const btns = ui.buttons.map(spec => {
      const b = el("button", "", spec.label); if (spec.color) b.style.setProperty("--b", spec.color);
      press(b, () => { send({btn: spec.id}); vibrate(15); }); g.append(b); return b;
    });
    return {update(u) { for (const b of btns) b.disabled = !u.enabled; }};
  },
  board(ui, area) {
    const g = el("div", "ttt"); area.append(g);
    const cells = [];
    for (let i = 0; i < 9; i++) {
      const b = el("button"); press(b, () => { if (!b.disabled) { send({cell: i}); vibrate(15); } });
      g.append(b); cells.push(b);
    }
    return {update(u) {
      cells.forEach((b, i) => {
        const v = u.cells[i];
        b.textContent = v === "X" ? "✕" : v === "O" ? "◯" : (u.vote === i ? (u.mark === "X" ? "✕" : "◯") : "");
        b.className = (v ? "set " + v : (u.vote === i ? "vote" : "")) + ((u.line || []).includes(i) ? " win" : "");
        b.disabled = !u.enabled || !!v;
      });
      g.classList.toggle("off", !u.enabled);
    }};
  },
  paddle(ui, area) {
    const tr = el("div", "track"), th = el("div", "thumb"); tr.append(th); area.append(tr);
    let want = null, y = 0.5;
    const move = e => { const r = tr.getBoundingClientRect(); y = Math.min(1, Math.max(0, (e.clientY - r.top - r.height * 0.13) / (r.height * 0.74)));
      th.style.top = (y * 74) + "%"; if (want === null) want = requestAnimationFrame(() => { want = null; send({y: Math.round(y * 1000) / 1000}); }); };
    tr.addEventListener("pointerdown", e => { tr.setPointerCapture(e.pointerId); move(e); });
    tr.addEventListener("pointermove", e => { if (e.buttons || e.pointerType === "touch") move(e); });
    return {};
  },
  shooter(ui, area) {  // Space Invaders: Raumschiff ziehen + FEUER (gedrückt halten = Dauerfeuer)
    const tr = el("div", "htrack"), th = el("div", "hthumb"); tr.append(th);
    const fire = el("button", "fire", "FEUER");
    area.append(tr, fire);
    let want = null, x = typeof ui.x === "number" ? ui.x : 0.5, t = null;
    th.style.left = (x * 78) + "%";
    const move = e => { const r = tr.getBoundingClientRect(); x = Math.min(1, Math.max(0, (e.clientX - r.left - r.width * 0.11) / (r.width * 0.78)));
      th.style.left = (x * 78) + "%"; if (want === null) want = requestAnimationFrame(() => { want = null; send({x: Math.round(x * 1000) / 1000}); }); };
    tr.addEventListener("pointerdown", e => { try { tr.setPointerCapture(e.pointerId); } catch (err) {} move(e); });
    tr.addEventListener("pointermove", e => { if (e.buttons || e.pointerType === "touch") move(e); });
    const shoot = () => { send({fire: 1}); };
    fire.addEventListener("pointerdown", e => { e.preventDefault(); fire.classList.add("hit"); shoot(); vibrate(10);
      if (!t) t = setInterval(shoot, 120); });
    const stop = () => { fire.classList.remove("hit"); if (t) { clearInterval(t); t = null; } };
    for (const ev of ["pointerup", "pointercancel", "pointerleave"]) fire.addEventListener(ev, stop);
    return {move(dx) { x = Math.min(1, Math.max(0, x + dx)); th.style.left = (x * 78) + "%"; send({x}); }, shoot};
  },
  connect4(ui, area) {  // Vier gewinnt: Spalte antippen
    const cols = el("div", "c4cols"), g = el("div", "c4");
    const btns = [];
    for (let c = 0; c < 7; c++) {
      const b = el("button", "", "▼"); press(b, () => { if (!b.disabled) { send({col: c}); vibrate(15); } });
      cols.append(b); btns.push(b);
    }
    const cells = [];
    for (let i = 0; i < 42; i++) { const s = el("span"); g.append(s); cells.push(s); }
    area.append(cols, g);
    return {update(u) {
      cells.forEach((s, i) => { s.className = (u.cells[i] || "") + ((u.line || []).includes(i) ? " win" : ""); });
      btns.forEach((b, c) => { b.disabled = !u.enabled || (u.full || [])[c]; b.classList.toggle("vote", u.vote === c); });
      g.classList.toggle("off", !u.enabled);
    }};
  },
  tetris(ui, area) {
    const nrow = el("div", "nextrow"), nlabel = el("span", "", "Nächstes"), np = el("div", "nextp");
    nrow.append(nlabel, np);
    const g = el("div", "tet");
    const mk = (label, move, cls, repeat) => {
      const b = el("button", cls || "", label);
      let t = null;
      const go = () => { send({move}); vibrate(8); };
      b.addEventListener("pointerdown", e => { e.preventDefault(); b.classList.add("hit"); go();
        if (repeat) t = setInterval(go, 110); });
      const stop = () => { b.classList.remove("hit"); if (t) { clearInterval(t); t = null; } };
      for (const ev of ["pointerup", "pointercancel", "pointerleave"]) b.addEventListener(ev, stop);
      g.append(b);
    };
    mk("◀", "left", "", true); mk("⟳", "rotate"); mk("▶", "right", "", true);
    mk("▼", "down", "row", true); mk("⤓  FALLEN", "drop", "wide");
    area.append(nrow, g);
    const SH = {I: [[0,1],[1,1],[2,1],[3,1]], O: [[1,0],[2,0],[1,1],[2,1]], T: [[1,0],[0,1],[1,1],[2,1]],
      S: [[1,0],[2,0],[0,1],[1,1]], Z: [[0,0],[1,0],[1,1],[2,1]], J: [[0,0],[0,1],[1,1],[2,1]], L: [[2,0],[0,1],[1,1],[2,1]]};
    const COL = {I: "#22d3ee", O: "#facc15", T: "#a855f7", S: "#22c55e", Z: "#ef4444", J: "#3b82f6", L: "#f97316"};
    let shown = "";
    return {update(u) {
      if (u.next === shown) return; shown = u.next; np.replaceChildren();
      for (const [x, y] of SH[u.next] || []) { const c = el("span"); c.style.gridColumn = x + 1; c.style.gridRow = y + 1;
        c.style.background = COL[u.next]; np.append(c); }
    }};
  },
};
document.addEventListener("keydown", e => {
  const k = {ArrowUp: "up", ArrowDown: "down", ArrowLeft: "left", ArrowRight: "right"}[e.key];
  if (k && state.ui && state.ui.ui === "pad") send({dir: k});
  else if (state.ui && state.ui.ui === "tetris") {
    const m = {ArrowLeft: "left", ArrowRight: "right", ArrowUp: "rotate", ArrowDown: "down", " ": "drop"}[e.key];
    if (m) { e.preventDefault(); send({move: m}); }
  }
  else if (e.key === " " && state.ui && state.ui.ui === "tap") send({tap: 1});
  else if (state.ui && state.ui.ui === "shooter" && comp) {
    if (e.key === "ArrowLeft") comp.move(-0.05); else if (e.key === "ArrowRight") comp.move(0.05);
    else if (e.key === " ") { e.preventDefault(); comp.shoot(); }
  }
});
load(); connect();
</script></body></html>
"""
