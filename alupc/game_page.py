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
.grid.quiz, .grid.column { grid-template-columns: 1fr; gap: 10px; }
.grid.quiz button { text-align: left; font-size: 21px; padding: 18px 16px; border-color: var(--b); background: color-mix(in srgb, var(--b) 28%, #0f172a); }
.grid.column button { font-size: 30px; padding: 22px 8px; }
.simon { grid-template-columns: 1fr 1fr; gap: 14px; max-width: min(420px, 52vh); }
.simon button { aspect-ratio: 1; border: 0; padding: 0; background: var(--b); filter: saturate(.75) brightness(.7); }
.simon button.hit { filter: saturate(1.2) brightness(1.3); box-shadow: 0 0 40px var(--b); }
.q { font-size: 21px; font-weight: 700; text-align: center; line-height: 1.3; max-width: 440px; }
.display { font-size: 38px; font-weight: 800; background: #0f172a; border: 2px solid #334155; border-radius: 16px;
  padding: 10px 16px; width: 100%; max-width: 420px; text-align: right; min-height: 64px; }
.display small { font-size: 20px; color: #94a3b8; margin-left: 8px; }
.keys { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; width: 100%; max-width: 420px; }
.keys button { background: #1e293b; border-radius: 14px; font-size: 26px; padding: 14px 0; }
.keys button.ok { grid-column: span 3; background: var(--c); font-size: 22px; }
.keys button.hit { background: #334155; }
.hint { font-size: 30px; font-weight: 800; letter-spacing: 4px; text-align: center; }
.feedback { color: #fbbf24; font-weight: 800; min-height: 22px; }
.canvasbox { width: 100%; max-width: 560px; }
canvas { width: 100%; background: #fff; border-radius: 14px; touch-action: none; display: block; }
.tools { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; margin-top: 10px; }
.tools button { width: 42px; height: 42px; border-radius: 50%; background: var(--b); border: 3px solid transparent; }
.tools button.sel { border-color: #fff; box-shadow: 0 0 0 2px var(--c); }
.tools .txt { width: auto; padding: 0 14px; border-radius: 21px; background: #1e293b; font-size: 15px; }
.word { font-size: 28px; font-weight: 900; color: #fbbf24; }
.track { position: relative; width: min(52vw, 260px); height: min(62vh, 520px); border-radius: 28px; background: #1e293b;
  border: 2px solid #334155; touch-action: none; }
.thumb { position: absolute; left: 8px; right: 8px; height: 26%; border-radius: 20px; background: var(--c);
  box-shadow: 0 0 24px var(--c); top: 37%; }
.balloon { width: 120px; height: 140px; border-radius: 50% 50% 48% 48%; background: radial-gradient(circle at 35% 30%,
  color-mix(in srgb, var(--c) 60%, #fff), var(--c)); transition: transform .12s; transform-origin: 50% 100%; }
.balloon.burst { background: transparent; border: 3px dashed #f87171; }
.row { display: flex; gap: 12px; width: 100%; max-width: 420px; }
.row button { flex: 1; border-radius: 18px; padding: 22px 0; font-size: 22px; }
.pump { background: var(--c); } .stop { background: #1e293b; border: 2px solid #4ade80 !important; color: #4ade80; }
#area { width: 100%; display: flex; flex-direction: column; align-items: center; gap: 14px; min-height: 0; }
.bbox { height: 34vh; display: flex; align-items: flex-end; justify-content: center; padding-bottom: 8px; }
.avatars { display: grid; grid-template-columns: repeat(7, 1fr); gap: 6px; width: 100%; max-width: 380px; }
.avatars button { font-size: 26px; padding: 6px 0; border-radius: 12px; background: #1e293b; border: 2px solid transparent; }
.avatars button.sel { border-color: var(--c); background: #334155; }
#ava { font-size: 22px; line-height: 1; }
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
    const r = await fetch("/api/spiel?u=" + enc(token) + "&p=" + enc(pid), {cache: "no-store"});
    if (r.status === 404) { $("jtitle").textContent = "Keine Spielrunde"; $("jhelp").textContent = "Am PC Minispiele starten"; show(false); return; }
    render(await r.json());
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
    const g = el("div", "grid" + (["simon", "quiz", "column"].includes(ui.layout) ? " " + ui.layout : "")); area.append(g);
    const btns = ui.buttons.map(spec => {
      const b = el("button", "", spec.label); if (spec.color) b.style.setProperty("--b", spec.color);
      press(b, () => { send({btn: spec.id}); vibrate(15); }); g.append(b); return b;
    });
    return {update(u) { for (const b of btns) b.disabled = !u.enabled; }};
  },
  number(ui, area) {
    const q = el("div", "q"), disp = el("div", "display"), keys = el("div", "keys");
    area.append(q, disp, keys);
    let raw = "";
    const fmt = s => { if (!s) return ""; const [a, b] = s.split(","); return a.replace(/\B(?=(\d{3})+(?!\d))/g, ".") + (b !== undefined ? "," + b : ""); };
    const draw = u => { disp.replaceChildren(document.createTextNode(fmt(raw) || "0")); disp.append(el("small", "", u.unit === "Jahr" ? "" : (u.unit || ""))); };
    const add = k => {
      if (k === "⌫") raw = raw.slice(0, -1);
      else if (k === ",") { if (!raw.includes(",")) raw = (raw || "0") + ","; }
      else if (raw.replace(",", "").length < 15) raw = (raw === "0" ? "" : raw) + k;
      draw(state.ui || ui);
    };
    for (const k of ["1","2","3","4","5","6","7","8","9",",","0","⌫"]) { const b = el("button", "", k); press(b, () => add(k)); keys.append(b); }
    const z = el("button", "", "000"); press(z, () => { if (raw && !raw.includes(",")) add("000"); }); keys.append(z);
    const ok = el("button", "ok", "Abgeben"); press(ok, () => { if (raw) send({num: raw}); }); keys.append(ok);
    keys.children[12].style.gridColumn = "span 3";
    return {update(u) { q.textContent = u.question; draw(u);
      const done = !!u.done; keys.classList.toggle("hidden", done);
      if (done) { disp.replaceChildren(document.createTextNode("✓ " + u.done)); } }};
  },
  text(ui, area) {
    const hint = el("div", "hint"), inp = el("input"), b = el("button", "primary", "Raten"), fb = el("div", "feedback");
    inp.placeholder = "Dein Tipp"; inp.maxLength = 40; inp.autocomplete = "off";
    area.append(hint, inp, b, fb);
    const go = () => { const t = inp.value.trim(); if (t) { send({guess: t}); inp.value = ""; inp.focus(); vibrate(10); } };
    b.onclick = go; inp.addEventListener("keydown", e => { if (e.key === "Enter") go(); });
    return {update(u) { hint.textContent = u.hint; fb.textContent = u.feedback || ""; }};
  },
  draw(ui, area) {
    const word = el("div", "word", ui.word), box = el("div", "canvasbox"), cv = el("canvas"), tools = el("div", "tools");
    box.append(cv, tools); area.append(word, box);
    const ctx = cv.getContext("2d");
    let strokes = [], color = "#111827", width = 7, buf = [];
    const size = () => { const r = window.devicePixelRatio || 1, w = box.clientWidth; cv.width = w * r; cv.height = w * 0.75 * r; redraw(); };
    function line(s, a, b) { ctx.strokeStyle = s.c; ctx.lineWidth = s.w / 1000 * cv.width; ctx.lineCap = ctx.lineJoin = "round";
      ctx.beginPath(); ctx.moveTo(a[0] * cv.width, a[1] * cv.height); ctx.lineTo(b[0] * cv.width, b[1] * cv.height); ctx.stroke(); }
    function redraw() { ctx.clearRect(0, 0, cv.width, cv.height); for (const s of strokes) for (let i = 0; i < s.pts.length; i++) line(s, s.pts[Math.max(0, i - 1)], s.pts[i]); }
    const pos = e => { const r = cv.getBoundingClientRect(); return [Math.round(Math.min(1, Math.max(0, (e.clientX - r.left) / r.width)) * 1000) / 1000,
                                                                 Math.round(Math.min(1, Math.max(0, (e.clientY - r.top) / r.height)) * 1000) / 1000]; };
    let down = false;
    cv.addEventListener("pointerdown", e => { down = true; cv.setPointerCapture(e.pointerId); const p = pos(e);
      const s = {c: color, w: width, pts: [p]}; strokes.push(s); line(s, p, p); flush(); send({stroke: {c: color, w: width, p}}); });
    cv.addEventListener("pointermove", e => { if (!down) return; const s = strokes[strokes.length - 1], p = pos(e);
      line(s, s.pts[s.pts.length - 1], p); s.pts.push(p); buf.push(p); });
    const up = () => { down = false; flush(); };
    cv.addEventListener("pointerup", up); cv.addEventListener("pointercancel", up);
    function flush() { if (buf.length) { send({pts: buf}); buf = []; } }
    const timer = setInterval(flush, 40);
    const colors = ["#111827", "#ef4444", "#3b82f6", "#22c55e", "#facc15", "#f97316", "#a855f7", "#92400e"];
    const sel = b => { for (const x of tools.querySelectorAll("button")) x.classList.remove("sel"); b.classList.add("sel"); };
    colors.forEach((c, i) => { const b = el("button"); b.style.setProperty("--b", c); if (!i) b.classList.add("sel");
      b.onclick = () => { color = c; width = width > 20 ? 7 : width; sel(b); }; tools.append(b); });
    const er = el("button", "txt", "Radierer"); er.onclick = () => { color = "#ffffff"; width = 40; sel(er); };
    const thick = el("button", "txt", "Dick"); thick.onclick = () => { width = width === 7 ? 18 : 7; thick.textContent = width === 7 ? "Dick" : "Dünn"; };
    const undo = el("button", "txt", "↶ Zurück"); undo.onclick = () => { strokes.pop(); redraw(); send({undo: 1}); };
    const clear = el("button", "txt", "Alles weg"); clear.onclick = () => { strokes = []; redraw(); send({clear: 1}); };
    tools.append(er, thick, undo, clear);
    setTimeout(size, 0); window.addEventListener("resize", size);
    return {update(u) { word.textContent = u.word; if (!document.body.contains(cv)) clearInterval(timer); }};
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
  balloon(ui, area) {
    const ball = el("div", "balloon"), row = el("div", "row"), pump = el("button", "pump", "PUMPEN"), stop = el("button", "stop", "Sichern");
    const bbox = el("div", "bbox"); bbox.append(ball);
    row.append(pump, stop); area.append(bbox, row);
    let local = 0;
    press(pump, () => { send({pump: 1}); local++; vibrate(10); paint(state.ui || ui); });
    stop.onclick = () => send({stop: 1});
    const paint = u => { const n = Math.max(u.pumps || 0, local); ball.style.transform = "scale(" + Math.min(2.0, 0.6 + n * 0.035) + ")";
      ball.classList.toggle("burst", u.state === "burst"); };
    return {update(u) { if ((u.pumps || 0) < local - 4) local = u.pumps || 0; paint(u);
      const on = u.state === "pump"; pump.disabled = stop.disabled = !on; }};
  },
};
document.addEventListener("keydown", e => {
  const k = {ArrowUp: "up", ArrowDown: "down", ArrowLeft: "left", ArrowRight: "right"}[e.key];
  if (k && state.ui && state.ui.ui === "pad") send({dir: k});
  else if (e.key === " " && state.ui && state.ui.ui === "tap") send({tap: 1});
});
load(); connect();
</script></body></html>
"""
