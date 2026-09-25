"""Die Seite, die das Handy im Browser öffnet (AluCast). Eine Datei, ohne Internet, ohne App.

Zwei Reiter: „Steuern“ (Live-Bild von Monitor 2 mit Laserpointer per Finger, Schnellknöpfe, Szenen,
Timer, Video, Lautstärke, RGB) und „Senden“ (Foto/Video, Link, Text).
"""

PAGE = r"""<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover, user-scalable=no">
<meta name="theme-color" content="#1e1b4b">
<meta name="apple-mobile-web-app-capable" content="yes">
<title>AluCast – AluPC-Fernbedienung</title>
<style>
:root { --bg:#f1f5f9; --card:#ffffff; --text:#0f172a; --muted:#64748b; --line:#e2e8f0; --accent:#2563eb;
        --accent2:#1d4ed8; --bad:#dc2626; --chip:#eef2ff; --on:#2563eb; }
@media (prefers-color-scheme: dark) {
  :root { --bg:#0b1120; --card:#131c2e; --text:#e2e8f0; --muted:#94a3b8; --line:#1e293b; --accent:#3b82f6;
          --accent2:#93c5fd; --chip:#1e293b; --on:#3b82f6; }
}
* { box-sizing:border-box; -webkit-tap-highlight-color:transparent; }
html, body { margin:0; }
body { font:16px/1.4 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif; background:var(--bg); color:var(--text);
       padding:0 12px calc(86px + env(safe-area-inset-bottom)); -webkit-user-select:none; user-select:none; }
header { position:sticky; top:0; z-index:5; margin:0 -12px 12px; padding:calc(10px + env(safe-area-inset-top)) 16px 10px;
         background:linear-gradient(135deg,#1d4ed8,#7c3aed); color:#fff; display:flex; align-items:center; gap:10px; }
header .dot { width:10px; height:10px; border-radius:50%; background:#94a3b8; flex:none; }
header .dot.on { background:#22c55e; box-shadow:0 0 0 4px rgba(34,197,94,.25); }
header h1 { margin:0; font-size:17px; }
header .now { font-size:12.5px; opacity:.9; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.card { background:var(--card); border:1px solid var(--line); border-radius:18px; padding:14px; margin-bottom:12px; }
.card h2 { margin:0 0 10px; font-size:12.5px; color:var(--muted); font-weight:700; text-transform:uppercase; letter-spacing:.7px; }
.row { display:flex; gap:8px; }
.row > * { flex:1 1 0; min-width:0; }
.grid { display:grid; grid-template-columns:repeat(3,1fr); gap:8px; }
button, .btn { appearance:none; border:0; border-radius:14px; padding:12px 8px; font:inherit; font-weight:600; font-size:14.5px;
         background:var(--chip); color:var(--text); cursor:pointer; text-align:center; display:block; overflow-wrap:anywhere; }
.tile { display:flex; flex-direction:column; align-items:center; gap:4px; padding:12px 4px; }
.tile .i { font-size:22px; line-height:1; }
.tile.on, button.on { background:var(--on); color:#fff; box-shadow:0 4px 14px rgba(37,99,235,.35); }
button.primary, .btn.primary { background:var(--accent); color:#fff; }
button:active, .btn:active { transform:scale(.96); }
input[type=text], input[type=url], textarea { width:100%; border:1px solid var(--line); border-radius:12px; padding:12px;
         font:inherit; background:var(--bg); color:var(--text); -webkit-user-select:text; user-select:text; }
textarea { min-height:70px; resize:vertical; }
input[type=file] { display:none; }
input[type=range] { width:100%; accent-color:var(--accent); height:28px; }
.hint { color:var(--muted); font-size:12.5px; margin-top:8px; }
.bar { height:8px; border-radius:4px; background:var(--line); overflow:hidden; margin-top:10px; display:none; }
.bar > div { height:100%; width:0; background:var(--accent); transition:width .15s; }
.scenes { display:grid; grid-template-columns:repeat(auto-fill,minmax(120px,1fr)); gap:8px; margin-top:8px; }
/* Live-Bild mit Laserpointer */
.preview { position:relative; border-radius:14px; overflow:hidden; background:#000; aspect-ratio:16/9; touch-action:none; }
.preview img { width:100%; height:100%; object-fit:contain; display:block; pointer-events:none; }
.preview .laser { position:absolute; width:22px; height:22px; margin:-11px 0 0 -11px; border-radius:50%;
                  background:radial-gradient(circle,#fff 0 20%,#ef4444 35%,rgba(239,68,68,0) 70%); display:none; pointer-events:none; }
.preview .badge { position:absolute; left:8px; top:8px; background:rgba(0,0,0,.55); color:#fff; font-size:11px;
                  font-weight:700; padding:3px 8px; border-radius:999px; letter-spacing:.4px; }
.timer { font-size:34px; font-weight:800; text-align:center; font-variant-numeric:tabular-nums; margin:2px 0 10px; }
/* Reiter unten */
nav { position:fixed; left:0; right:0; bottom:0; z-index:6; display:flex; background:var(--card); border-top:1px solid var(--line);
      padding:6px 10px calc(6px + env(safe-area-inset-bottom)); gap:8px; }
nav button { flex:1; background:transparent; color:var(--muted); padding:8px 4px; font-size:13px; display:flex;
             flex-direction:column; align-items:center; gap:2px; }
nav button .i { font-size:21px; }
nav button.sel { color:var(--accent); background:var(--chip); }
.page { display:none; }
.page.sel { display:block; }
.toast { position:fixed; left:50%; bottom:calc(90px + env(safe-area-inset-bottom)); transform:translateX(-50%);
         background:#0f172a; color:#fff; padding:10px 16px; border-radius:999px; font-size:14px; opacity:0;
         transition:opacity .2s; pointer-events:none; max-width:90vw; z-index:9; }
.toast.show { opacity:.95; }
.toast.bad { background:var(--bad); }
#login { display:none; }
.big { font-size:28px; letter-spacing:6px; text-align:center; }
.hide { display:none !important; }
</style>
</head>
<body>
<header><span class="dot" id="dot"></span><div style="min-width:0"><h1>AluPC</h1><div class="now" id="now">Verbinde …</div></div></header>

<div class="card" id="login">
  <h2>Code eingeben</h2>
  <p>Den 6-stelligen Code zeigt AluPC unter dem QR-Code an.</p>
  <input type="text" id="code" class="big" inputmode="numeric" maxlength="7" autocomplete="off">
  <button class="primary" style="width:100%;margin-top:10px" onclick="saveCode()">Verbinden</button>
</div>

<div id="main">
<!-- ============================================================ Steuern -->
<div class="page sel" id="p-steuern">
  <div class="card">
    <div class="preview" id="preview"><img id="prev" alt=""><div class="laser" id="laser"></div>
      <span class="badge">LIVE · Finger = Laserpointer</span></div>
  </div>
  <div class="card">
    <div class="grid">
      <button class="tile" id="b-schwarz" onclick="cmd('schwarz')"><span class="i">⬛</span>Schwarz</button>
      <button class="tile" id="b-standbild" onclick="cmd('standbild')"><span class="i">❄️</span>Standbild</button>
      <button class="tile" id="b-spiegeln" onclick="cmd('spiegeln')"><span class="i">🪞</span>Spiegeln</button>
      <button class="tile" id="b-erweitern" onclick="cmd('erweitern')"><span class="i">🖥️</span>Erweitern</button>
      <button class="tile" id="b-schoner" onclick="cmd('bildschirmschoner')"><span class="i">🌙</span>Schoner</button>
      <button class="tile" onclick="cmd('zeichnungen_loeschen')"><span class="i">🧽</span>Radieren</button>
    </div>
  </div>
  <div class="card">
    <h2>Szenen</h2>
    <div class="row">
      <button onclick="cmd('vorherige_szene')">◀ Zurück</button>
      <button onclick="cmd('naechste_szene')">Weiter ▶</button>
    </div>
    <div class="scenes" id="scenes"></div>
  </div>
  <div class="card" id="c-video">
    <h2>Video</h2>
    <div class="row">
      <button onclick="cmd('video_zurueck')">⏪ 10 s</button>
      <button class="primary" onclick="cmd('video_pause')">⏯ Pause</button>
      <button onclick="cmd('video_vor')">10 s ⏩</button>
    </div>
  </div>
  <div class="card" id="c-vol">
    <h2>Lautstärke</h2>
    <input type="range" id="vol" min="0" max="100" step="5" onchange="cmd('lautstaerke:' + this.value)">
  </div>
  <div class="card">
    <h2>Timer</h2>
    <div class="timer" id="timer">–</div>
    <div class="row">
      <button onclick="cmd('timer_minus')">− 1 min</button>
      <button class="primary" onclick="cmd('timer_start_pause')">⏯ Start</button>
      <button onclick="cmd('timer_plus')">+ 1 min</button>
    </div>
    <div class="row" style="margin-top:8px">
      <button onclick="cmd('timer_zeigen')">⏱ Auf Monitor 2</button>
      <button onclick="cmd('timer_neustart')">↺ Neu</button>
    </div>
  </div>
  <div class="card" id="c-rgb">
    <h2>RGB-Licht</h2>
    <div class="row">
      <button id="r-farbe" onclick="cmd('rgb_farbe')">🎨 Farbe</button>
      <button id="r-monitor2" onclick="cmd('rgb_monitor2')">🖥️ Wie Monitor 2</button>
      <button id="r-aus" onclick="cmd('rgb_aus')">⚫ Aus</button>
    </div>
  </div>
</div>

<!-- ============================================================ Senden -->
<div class="page" id="p-senden">
  <div class="card">
    <h2>Foto oder Video zeigen</h2>
    <div class="row">
      <label class="btn primary" for="cam">📷 Foto machen</label>
      <label class="btn" for="gal">🖼️ Aus Galerie</label>
    </div>
    <input type="file" id="cam" accept="image/*" capture="environment">
    <input type="file" id="gal" accept="image/*,video/*">
    <div class="bar" id="bar"><div></div></div>
    <div class="hint" id="upinfo">Wird sofort auf Monitor 2 gezeigt.</div>
  </div>
  <div class="card">
    <h2>Link zeigen</h2>
    <input type="url" id="url" placeholder="https://… (z. B. YouTube-Link)" autocomplete="off">
    <button class="primary" style="width:100%;margin-top:8px" onclick="sendLink()">Auf Monitor 2 öffnen</button>
    <div class="hint">YouTube: „Teilen → Link kopieren“ und hier einfügen – läuft im Vollbild.</div>
  </div>
  <div class="card">
    <h2>Text zeigen</h2>
    <textarea id="text" placeholder="Text für Monitor 2"></textarea>
    <button style="width:100%;margin-top:8px" onclick="sendText()">Text anzeigen</button>
  </div>
</div>
</div>

<nav id="nav">
  <button class="sel" data-p="steuern" onclick="tab('steuern')"><span class="i">🎛️</span>Steuern</button>
  <button data-p="senden" onclick="tab('senden')"><span class="i">📤</span>Senden</button>
</nav>
<div class="toast" id="toast"></div>

<script>
const params = new URLSearchParams(location.search);
const store = {  // privater Modus: Speicher kann fehlen → dann eben nur für diese Seite merken
  get() { try { return localStorage.getItem("alucast-code") || ""; } catch (e) { return ""; } },
  set(v) { try { v ? localStorage.setItem("alucast-code", v) : localStorage.removeItem("alucast-code"); } catch (e) {} },
};
let code = params.get("k") || store.get();
if (params.get("k")) { store.set(code); history.replaceState(null, "", location.pathname); }
const $ = id => document.getElementById(id);
let current = "steuern";

function tab(name) {
  current = name;
  for (const b of document.querySelectorAll("nav button")) b.classList.toggle("sel", b.dataset.p === name);
  for (const p of document.querySelectorAll(".page")) p.classList.toggle("sel", p.id === "p-" + name);
  window.scrollTo(0, 0);
}
function toast(text, bad) {
  const t = $("toast"); t.textContent = text; t.className = "toast show" + (bad ? " bad" : "");
  clearTimeout(t._h); t._h = setTimeout(() => t.className = "toast", 2600);
}
function showLogin(on) {
  $("login").style.display = on ? "block" : "none"; $("main").style.display = on ? "none" : "block";
  $("nav").classList.toggle("hide", on);
}
function forget() {  // falscher/alter Code: nicht weiter damit anfragen (sonst sperrt AluPC das Handy)
  code = ""; store.set(""); showLogin(true);
}
function saveCode() { code = $("code").value.replace(/\D/g, ""); store.set(code); refresh(); }
function buzz() { if (navigator.vibrate) navigator.vibrate(12); }

async function api(path, body, type) {
  const r = await fetch(path, { method: body === undefined ? "GET" : "POST",
    headers: Object.assign({ "X-AluPC-Code": code }, type ? { "Content-Type": type } : {}), body });
  if (r.status === 403) { forget(); throw new Error("Falscher Code"); }
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.error || ("Fehler " + r.status));
  return data;
}
async function post(path, obj, okText) {
  try { await api(path, JSON.stringify(obj), "application/json"); if (okText) toast(okText); setTimeout(refresh, 250); }
  catch (e) { toast(e.message, true); }
}
function cmd(c) { buzz(); post("/api/cmd", { cmd: c }); }
function sendLink() {
  const u = $("url").value.trim(); if (!u) return;
  post("/api/link", { url: u }, "Wird geöffnet …"); $("url").value = "";
}
function sendText() {
  const t = $("text").value.trim(); if (!t) return;
  post("/api/text", { text: t }, "Angezeigt");
}

let scenesKey = "";
async function refresh() {
  if (!code) { showLogin(true); return; }
  try {
    const s = await api("/api/status");
    showLogin(false);
    $("dot").classList.add("on");
    $("now").textContent = "Monitor 2: " + s.now;
    const f = s.flags || {};
    for (const [id, on] of [["b-schwarz", f.schwarz], ["b-standbild", f.standbild], ["b-spiegeln", f.spiegeln],
                            ["b-erweitern", f.erweitern], ["b-schoner", f.schoner]]) $(id).classList.toggle("on", !!on);
    $("c-video").classList.toggle("hide", !s.video);
    $("c-vol").classList.toggle("hide", !s.sound);
    if (document.activeElement !== $("vol")) $("vol").value = s.volume;
    $("timer").textContent = s.timer || "–";
    $("c-rgb").classList.toggle("hide", !s.rgb);
    for (const m of ["farbe", "monitor2", "aus"]) $("r-" + m).classList.toggle("on", s.rgb === m);
    const key = s.scenes.join("\n") + "|" + (s.scene || "");
    if (key !== scenesKey) {
      scenesKey = key; const box = $("scenes"); box.innerHTML = "";
      for (const name of s.scenes) {
        const b = document.createElement("button"); b.textContent = name;
        if (name === s.scene) b.className = "on";
        b.onclick = () => { buzz(); post("/api/cmd", { cmd: "szene:" + name }, name); }; box.appendChild(b);
      }
    }
  } catch (e) {
    $("dot").classList.remove("on");
    if (e.message === "Falscher Code") toast("Falscher oder alter Code – bitte neu eingeben", true);
    else $("now").textContent = /warten|beendet/.test(e.message) ? e.message : "Keine Verbindung zu AluPC";
  }
}

// ---- Live-Bild (nur, solange „Steuern“ offen und die Seite sichtbar ist)
let prevUrl = null, prevBusy = false;
async function loadPreview() {
  if (!code || prevBusy || current !== "steuern" || document.hidden) return;
  prevBusy = true;
  try {
    const r = await fetch("/api/preview", { headers: { "X-AluPC-Code": code } });
    if (r.ok) {
      const url = URL.createObjectURL(await r.blob());
      $("prev").src = url;
      if (prevUrl) URL.revokeObjectURL(prevUrl);
      prevUrl = url;
    }
  } catch (e) {}
  prevBusy = false;
}

// ---- Laserpointer: Finger auf dem Live-Bild
let pending = null, sending = false;
function sendLaser(obj) { pending = obj; if (!sending) flushLaser(); }
function flushLaser() {  // immer nur die neueste Position schicken – so bleibt der Punkt flüssig
  if (!pending) return;
  sending = true; const body = JSON.stringify(pending); pending = null;
  fetch("/api/laser", { method: "POST", headers: { "X-AluPC-Code": code, "Content-Type": "application/json" }, body })
    .catch(() => {}).finally(() => setTimeout(() => { sending = false; flushLaser(); }, 25));
}
function point(e) {
  const box = $("preview").getBoundingClientRect();
  const t = e.touches ? e.touches[0] : e;
  const x = Math.min(1, Math.max(0, (t.clientX - box.left) / box.width));
  const y = Math.min(1, Math.max(0, (t.clientY - box.top) / box.height));
  const l = $("laser"); l.style.display = "block"; l.style.left = (x * 100) + "%"; l.style.top = (y * 100) + "%";
  sendLaser({ x, y });
}
function release() { $("laser").style.display = "none"; sendLaser({ up: true }); }
const pv = $("preview");
pv.addEventListener("pointerdown", e => { pv.setPointerCapture(e.pointerId); point(e); });
pv.addEventListener("pointermove", e => { if (e.buttons || e.pointerType === "touch") point(e); });
pv.addEventListener("pointerup", release);
pv.addEventListener("pointercancel", release);

// Fotos: sehr große Bilder und HEIC (iPhone) vor dem Senden in JPEG umwandeln
function prepare(file) {
  return new Promise(resolve => {
    const heic = /heic|heif/i.test(file.type) || /\.hei[cf]$/i.test(file.name);
    if (!file.type.startsWith("image/") || file.type === "image/gif" || (!heic && file.size < 6e6)) { resolve(file); return; }
    const img = new Image(); const url = URL.createObjectURL(file);
    img.onload = () => {
      const scale = Math.min(1, 3840 / Math.max(img.naturalWidth, img.naturalHeight));
      const c = document.createElement("canvas");
      c.width = Math.round(img.naturalWidth * scale); c.height = Math.round(img.naturalHeight * scale);
      c.getContext("2d").drawImage(img, 0, 0, c.width, c.height); URL.revokeObjectURL(url);
      c.toBlob(b => resolve(b ? new File([b], file.name.replace(/\.[^.]+$/, "") + ".jpg", { type: "image/jpeg" }) : file),
               "image/jpeg", 0.9);
    };
    img.onerror = () => { URL.revokeObjectURL(url); resolve(file); };
    img.src = url;
  });
}
async function upload(input) {
  const original = input.files[0]; input.value = ""; if (!original) return;
  const file = await prepare(original);
  const bar = $("bar"), fill = bar.firstElementChild; bar.style.display = "block"; fill.style.width = "0";
  $("upinfo").textContent = "Wird gesendet …";
  const xhr = new XMLHttpRequest();
  xhr.open("POST", "/api/upload?name=" + encodeURIComponent(file.name || "handy"));
  xhr.setRequestHeader("X-AluPC-Code", code);
  xhr.setRequestHeader("Content-Type", file.type || "application/octet-stream");
  xhr.upload.onprogress = e => { if (e.lengthComputable) fill.style.width = (100 * e.loaded / e.total) + "%"; };
  xhr.onload = () => {
    bar.style.display = "none";
    if (xhr.status === 200) { toast("Auf Monitor 2"); $("upinfo").textContent = "Gesendet: " + file.name; setTimeout(refresh, 500); }
    else if (xhr.status === 403) { forget(); }
    else { let m = "Fehler " + xhr.status; try { m = JSON.parse(xhr.responseText).error || m; } catch (e) {}
           toast(m, true); $("upinfo").textContent = m; }
  };
  xhr.onerror = () => { bar.style.display = "none"; toast("Verbindung abgebrochen", true); };
  xhr.send(file);
}
$("cam").onchange = e => upload(e.target);
$("gal").onchange = e => upload(e.target);
refresh(); setInterval(refresh, 2000);
loadPreview(); setInterval(loadPreview, 1000);
document.addEventListener("visibilitychange", () => { if (!document.hidden) { refresh(); loadPreview(); } });
</script>
</body>
</html>
"""
