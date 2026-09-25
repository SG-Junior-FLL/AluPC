"""Die Seite, die das Handy im Browser öffnet (AluCast). Eine Datei, ohne Internet, ohne App."""

PAGE = r"""<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#2563eb">
<title>AluCast</title>
<style>
:root { --bg:#f1f5f9; --card:#ffffff; --text:#0f172a; --muted:#64748b; --line:#e2e8f0; --accent:#2563eb;
        --accent2:#1d4ed8; --ok:#16a34a; --bad:#dc2626; --chip:#eff6ff; }
@media (prefers-color-scheme: dark) {
  :root { --bg:#0b1120; --card:#131c2e; --text:#e2e8f0; --muted:#94a3b8; --line:#1e293b; --accent:#3b82f6;
          --accent2:#60a5fa; --chip:#172554; }
}
* { box-sizing:border-box; -webkit-tap-highlight-color:transparent; }
body { margin:0; font:16px/1.4 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif; background:var(--bg);
       color:var(--text); padding:0 14px calc(24px + env(safe-area-inset-bottom)); }
header { position:sticky; top:0; z-index:5; margin:0 -14px 12px; padding:calc(12px + env(safe-area-inset-top)) 16px 12px;
         background:linear-gradient(135deg,#2563eb,#7c3aed); color:#fff; }
header h1 { margin:0; font-size:20px; letter-spacing:.2px; }
header .now { margin-top:4px; font-size:13px; opacity:.92; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.card { background:var(--card); border:1px solid var(--line); border-radius:16px; padding:14px; margin-bottom:12px; }
.card h2 { margin:0 0 10px; font-size:15px; color:var(--muted); font-weight:600; text-transform:uppercase; letter-spacing:.6px; }
.row { display:flex; gap:8px; flex-wrap:wrap; }
.row > * { flex:1 1 0; min-width:0; }
button, .btn { overflow-wrap:anywhere; appearance:none; border:0; border-radius:12px; padding:13px 12px; font:inherit; font-weight:600;
         background:var(--chip); color:var(--accent2); cursor:pointer; text-align:center; display:block; }
button.primary, .btn.primary { background:var(--accent); color:#fff; }
button:active, .btn:active { transform:scale(.97); }
button.small { padding:9px 10px; font-size:14px; }
input[type=text], input[type=url], textarea { width:100%; border:1px solid var(--line); border-radius:12px; padding:12px;
         font:inherit; background:var(--bg); color:var(--text); }
textarea { min-height:70px; resize:vertical; }
input[type=file] { display:none; }
input[type=range] { width:100%; accent-color:var(--accent); }
.hint { color:var(--muted); font-size:13px; margin-top:8px; }
.bar { height:8px; border-radius:4px; background:var(--line); overflow:hidden; margin-top:10px; display:none; }
.bar > div { height:100%; width:0; background:var(--accent); transition:width .15s; }
.scenes { display:grid; grid-template-columns:repeat(auto-fill,minmax(130px,1fr)); gap:8px; margin-top:8px; }
.toast { position:fixed; left:50%; bottom:calc(20px + env(safe-area-inset-bottom)); transform:translateX(-50%);
         background:#0f172a; color:#fff; padding:10px 16px; border-radius:999px; font-size:14px; opacity:0;
         transition:opacity .2s; pointer-events:none; max-width:90vw; }
.toast.show { opacity:.95; }
.toast.bad { background:var(--bad); }
#login { display:none; }
.big { font-size:28px; letter-spacing:6px; text-align:center; }
</style>
</head>
<body>
<header><h1>AluCast → Monitor 2</h1><div class="now" id="now">Verbinde …</div></header>

<div class="card" id="login">
  <h2>Code eingeben</h2>
  <p>Den 6-stelligen Code zeigt AluPC unter dem QR-Code an.</p>
  <input type="text" id="code" class="big" inputmode="numeric" maxlength="6" autocomplete="off">
  <button class="primary" style="width:100%;margin-top:10px" onclick="saveCode()">Verbinden</button>
</div>

<div id="main">
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
  <div class="hint">Tipp: In YouTube „Teilen → Link kopieren“ und hier einfügen – läuft im Vollbild.</div>
</div>

<div class="card">
  <h2>Text zeigen</h2>
  <textarea id="text" placeholder="Text für Monitor 2"></textarea>
  <button style="width:100%;margin-top:8px" onclick="sendText()">Text anzeigen</button>
</div>

<div class="card">
  <h2>Fernbedienung</h2>
  <div class="row">
    <button onclick="cmd('vorherige_szene')">◀ Szene</button>
    <button onclick="cmd('naechste_szene')">Szene ▶</button>
  </div>
  <div class="row" style="margin-top:8px">
    <button onclick="cmd('schwarz')">⬛ Schwarz</button>
    <button onclick="cmd('standbild')">❄️ Standbild</button>
    <button onclick="cmd('zeichnungen_loeschen')" title="Zeichnungen auf Monitor 2 löschen">🧽 Radieren</button>
  </div>
  <div id="video" style="display:none;margin-top:12px">
    <div class="row">
      <button class="small" onclick="cmd('video_zurueck')">⏪ 10 s</button>
      <button class="small primary" onclick="cmd('video_pause')">⏯ Pause</button>
      <button class="small" onclick="cmd('video_vor')">10 s ⏩</button>
    </div>
  </div>
  <div style="margin-top:12px">
    <label class="hint" for="vol">Lautstärke</label>
    <input type="range" id="vol" min="0" max="100" step="5" onchange="cmd('lautstaerke:' + this.value)">
  </div>
  <div class="hint" id="scenes-title" style="margin-top:12px;display:none">Szenen</div>
  <div class="scenes" id="scenes"></div>
</div>
</div>
<div class="toast" id="toast"></div>

<script>
const params = new URLSearchParams(location.search);
let code = params.get("k") || localStorage.getItem("alucast-code") || "";
if (params.get("k")) { localStorage.setItem("alucast-code", code); history.replaceState(null, "", location.pathname); }
const $ = id => document.getElementById(id);

function toast(text, bad) {
  const t = $("toast"); t.textContent = text; t.className = "toast show" + (bad ? " bad" : "");
  clearTimeout(t._h); t._h = setTimeout(() => t.className = "toast", 2600);
}
function showLogin(on) { $("login").style.display = on ? "block" : "none"; $("main").style.display = on ? "none" : "block"; }
function saveCode() { code = $("code").value.trim(); localStorage.setItem("alucast-code", code); refresh(); }

async function api(path, body, type) {
  const r = await fetch(path, { method: body === undefined ? "GET" : "POST",
    headers: Object.assign({ "X-AluPC-Code": code }, type ? { "Content-Type": type } : {}), body });
  if (r.status === 403) { showLogin(true); throw new Error("Falscher Code"); }
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.error || ("Fehler " + r.status));
  return data;
}
async function post(path, obj, okText) {
  try { await api(path, JSON.stringify(obj), "application/json"); if (okText) toast(okText); setTimeout(refresh, 400); }
  catch (e) { toast(e.message, true); }
}
function cmd(c) { post("/api/cmd", { cmd: c }); }
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
    $("now").textContent = "Monitor 2: " + s.now;
    $("video").style.display = s.video ? "block" : "none";
    if (document.activeElement !== $("vol")) $("vol").value = s.volume;
    const key = s.scenes.join("\n");
    if (key !== scenesKey) {
      scenesKey = key; const box = $("scenes"); box.innerHTML = "";
      $("scenes-title").style.display = s.scenes.length ? "block" : "none";
      for (const name of s.scenes) {
        const b = document.createElement("button"); b.className = "small"; b.textContent = name;
        b.onclick = () => post("/api/cmd", { cmd: "szene:" + name }, name); box.appendChild(b);
      }
    }
  } catch (e) { if (e.message !== "Falscher Code") $("now").textContent = "Keine Verbindung zu AluPC"; }
}

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
    else if (xhr.status === 403) { showLogin(true); }
    else { let m = "Fehler " + xhr.status; try { m = JSON.parse(xhr.responseText).error || m; } catch (e) {}
           toast(m, true); $("upinfo").textContent = m; }
  };
  xhr.onerror = () => { bar.style.display = "none"; toast("Verbindung abgebrochen", true); };
  xhr.send(file);
}
$("cam").onchange = e => upload(e.target);
$("gal").onchange = e => upload(e.target);
refresh(); setInterval(refresh, 3000);
</script>
</body>
</html>
"""
