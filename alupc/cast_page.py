"""Die Seite, die das Handy im Browser öffnet (AluCast). Eine Datei, ohne Internet, ohne App.

Vier Reiter: „Start“ (Live-Bild mit Laserpointer per Finger, Schalter für Monitor 2, Kamera/iPhone/QR-Code/
Timer zeigen, Szenen, Video, Lautstärke, Timer mit Vorgaben, RGB), „Zeichnen“ (mit dem Finger auf Monitor 2:
Stift, Marker, Radierer, Laser, Farben, Rückgängig, Vollbild), „Folien“ (Präsentations-Fernbedienung und
Touchpad für die PC-Maus) und „Senden“ (Foto/Video, Link, Text). Was im Setup ausgeschaltet ist, verschwindet.
Lässt sich als App auf den Home-Bildschirm legen (manifest.json).
"""

PAGE = r"""<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover, user-scalable=no">
<meta name="theme-color" content="#0b1020">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="AluPC">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<link rel="manifest" href="/manifest.json">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="icon" href="/icon.png">
<title>AluCast – AluPC-Fernbedienung</title>
<style>
:root { --bg:#0b1020; --card:rgba(255,255,255,.055); --card2:rgba(255,255,255,.09); --text:#eef2ff; --muted:#94a3b8;
        --line:rgba(255,255,255,.09); --accent:#6366f1; --on:linear-gradient(135deg,#6366f1,#8b5cf6);
        --bad:#ef4444; --ok:#22c55e; --nav:rgba(15,23,42,.78); }
@media (prefers-color-scheme: light) {
  :root { --bg:#eef2f7; --card:#ffffff; --card2:#eef2f7; --text:#0f172a; --muted:#64748b; --line:#e2e8f0;
          --nav:rgba(255,255,255,.86); }
}
* { box-sizing:border-box; -webkit-tap-highlight-color:transparent; }
html, body { margin:0; }
body { font:16px/1.4 -apple-system,system-ui,"Segoe UI",Roboto,sans-serif; color:var(--text); min-height:100vh;
       background:radial-gradient(120% 60% at 50% -10%, rgba(99,102,241,.35), transparent 60%), var(--bg);
       padding:0 14px calc(96px + env(safe-area-inset-bottom)); -webkit-user-select:none; user-select:none; }
svg.i { width:22px; height:22px; stroke:currentColor; fill:none; stroke-width:1.9; stroke-linecap:round;
        stroke-linejoin:round; flex:none; }
header { display:flex; align-items:center; gap:12px; padding:calc(14px + env(safe-area-inset-top)) 2px 12px;
         position:sticky; top:0; z-index:5; background:linear-gradient(var(--bg) 70%, transparent); }
.logo { width:40px; height:40px; border-radius:12px; background:var(--on); display:grid; place-items:center; color:#fff;
        box-shadow:0 6px 20px rgba(99,102,241,.45); }
.logo svg { width:24px; height:24px; }
header .t { min-width:0; flex:1; }
header h1 { margin:0; font-size:18px; letter-spacing:.2px; }
header .now { font-size:13px; color:var(--muted); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.dot { width:9px; height:9px; border-radius:50%; background:#64748b; display:inline-block; margin-right:6px; }
.dot.on { background:var(--ok); box-shadow:0 0 0 4px rgba(34,197,94,.22); }
.offline { display:none; background:var(--bad); color:#fff; border-radius:14px; padding:10px 12px; margin-bottom:12px;
           font-size:14px; font-weight:600; }
.offline.show { display:block; }
.card { background:var(--card); border:1px solid var(--line); border-radius:22px; padding:14px; margin-bottom:12px;
        backdrop-filter:blur(12px); -webkit-backdrop-filter:blur(12px); }
.card h2 { margin:0 0 10px; font-size:12px; color:var(--muted); font-weight:700; text-transform:uppercase; letter-spacing:.8px;
           display:flex; align-items:center; justify-content:space-between; }
.row { display:flex; gap:8px; }
.row > * { flex:1 1 0; min-width:0; }
.grid { display:grid; grid-template-columns:repeat(3,1fr); gap:8px; }
.grid4 { display:grid; grid-template-columns:repeat(4,1fr); gap:8px; }
button, .btn { appearance:none; border:0; border-radius:16px; padding:13px 8px; font:inherit; font-weight:650; font-size:14.5px;
         background:var(--card2); color:var(--text); cursor:pointer; text-align:center; display:flex; align-items:center;
         justify-content:center; gap:8px; transition:transform .08s, background .2s; }
.tile { flex-direction:column; gap:6px; padding:14px 4px; font-size:13px; }
.tile svg.i { width:26px; height:26px; }
button.on, .tile.on { background:var(--on); color:#fff; box-shadow:0 8px 22px rgba(99,102,241,.4); }
button.primary, .btn.primary { background:var(--on); color:#fff; }
button.small { padding:8px 10px; font-size:13px; border-radius:12px; }
button:active, .btn:active { transform:scale(.95); }
input[type=text], input[type=url], textarea { width:100%; border:1px solid var(--line); border-radius:14px; padding:13px;
         font:inherit; background:var(--card2); color:var(--text); -webkit-user-select:text; user-select:text; outline:none; }
textarea { min-height:80px; resize:vertical; }
input[type=file] { display:none; }
input[type=range] { width:100%; accent-color:#8b5cf6; height:30px; }
.hint { color:var(--muted); font-size:12.5px; margin-top:8px; }
.bar { height:8px; border-radius:4px; background:var(--line); overflow:hidden; margin-top:10px; display:none; }
.bar > div { height:100%; width:0; background:var(--on); transition:width .15s; }
.scenes { display:grid; grid-template-columns:repeat(auto-fill,minmax(120px,1fr)); gap:8px; margin-top:8px; }
.preview { position:relative; border-radius:16px; overflow:hidden; background:#000; aspect-ratio:16/9; touch-action:none;
           box-shadow:0 10px 30px rgba(0,0,0,.35); }
.preview img, .preview canvas { position:absolute; inset:0; width:100%; height:100%; object-fit:contain; display:block;
           pointer-events:none; }
.preview .laser { position:absolute; width:26px; height:26px; margin:-13px 0 0 -13px; border-radius:50%;
                  background:radial-gradient(circle,#fff 0 18%,#ef4444 34%,rgba(239,68,68,0) 70%); display:none; pointer-events:none; }
.badge { position:absolute; left:10px; top:10px; background:rgba(0,0,0,.55); color:#fff; font-size:11px; font-weight:700;
         padding:4px 9px; border-radius:999px; letter-spacing:.4px; display:flex; align-items:center; gap:6px; z-index:2; }
.badge i { width:7px; height:7px; border-radius:50%; background:#ef4444; display:inline-block; animation:pulse 1.6s infinite; }
.corner { position:absolute; right:8px; top:8px; z-index:2; background:rgba(0,0,0,.55); color:#fff; padding:7px; border-radius:12px; }
@keyframes pulse { 50% { opacity:.3; } }
.timer { font-size:44px; font-weight:800; text-align:center; font-variant-numeric:tabular-nums; margin:0 0 10px; letter-spacing:1px; }
.chips { display:flex; gap:6px; flex-wrap:wrap; margin-bottom:10px; }
.chips button { flex:1 1 auto; padding:9px 6px; font-size:13.5px; border-radius:12px; }
.big { font-size:30px; letter-spacing:8px; text-align:center; }
/* Zeichnen */
.tools { display:grid; grid-template-columns:repeat(4,1fr); gap:8px; }
.tools button { flex-direction:column; gap:4px; padding:10px 4px; font-size:12.5px; }
.colors { display:flex; gap:10px; justify-content:space-between; margin-top:12px; }
.colors button { width:38px; height:38px; flex:none; border-radius:50%; padding:0; border:3px solid transparent; }
.colors button.sel { border-color:var(--text); transform:scale(1.08); }
/* Seitenverhältnis = Monitor 2 (per JS aus dem Live-Bild), damit Finger und Monitor genau übereinstimmen */
body.full .draw .preview { position:fixed; left:50%; top:50%; transform:translate(-50%,-50%); border-radius:0; z-index:20;
                           width:min(100vw, calc(100vh * var(--ar, 1.7778))); height:auto; }
body.full::after { content:""; position:fixed; inset:0; background:#000; z-index:19; }
body.full nav, body.full header { display:none; }
/* Folien + Touchpad */
.clicker { display:grid; grid-template-columns:1fr 1.6fr; gap:10px; }
.clicker button { min-height:140px; font-size:17px; flex-direction:column; border-radius:24px; }
.clicker button svg.i { width:40px; height:40px; }
.pad { height:240px; border-radius:20px; background:var(--card2); border:1px dashed var(--line); touch-action:none;
       display:grid; place-items:center; color:var(--muted); font-size:13px; text-align:center; padding:10px; }
.pad.active { border-style:solid; border-color:#8b5cf6; }
nav { position:fixed; left:12px; right:12px; bottom:calc(10px + env(safe-area-inset-bottom)); z-index:6; display:flex; gap:6px;
      background:var(--nav); border:1px solid var(--line); border-radius:22px; padding:6px;
      backdrop-filter:blur(16px); -webkit-backdrop-filter:blur(16px); box-shadow:0 12px 30px rgba(0,0,0,.35); }
nav button { flex:1; background:transparent; color:var(--muted); padding:8px 4px; font-size:12px; flex-direction:column; gap:3px; border-radius:16px; }
nav button.sel { background:var(--on); color:#fff; }
.page { display:none; animation:fade .18s ease; }
.page.sel { display:block; }
@keyframes fade { from { opacity:0; transform:translateY(4px); } to { opacity:1; transform:none; } }
.toast { position:fixed; left:50%; bottom:calc(100px + env(safe-area-inset-bottom)); transform:translateX(-50%);
         background:#0f172a; color:#fff; padding:10px 16px; border-radius:999px; font-size:14px; opacity:0;
         transition:opacity .2s; pointer-events:none; max-width:90vw; z-index:30; }
.toast.show { opacity:.96; }
.toast.bad { background:var(--bad); }
#login { display:none; margin-top:20px; }
.hide { display:none !important; }
</style>
</head>
<body>
<svg width="0" height="0" style="position:absolute">
  <symbol id="i-logo" viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="12" rx="2"/><path d="M12 16v4M8 20h8"/></symbol>
  <symbol id="i-black" viewBox="0 0 24 24"><path d="M3 3l18 18M10.6 5.1A10 10 0 0 1 22 12a17 17 0 0 1-3.2 4M6.6 6.6A17 17 0 0 0 2 12s3.6 7 10 7a9.7 9.7 0 0 0 5.4-1.6"/></symbol>
  <symbol id="i-freeze" viewBox="0 0 24 24"><path d="M12 2v20M4.9 4.9l14.2 14.2M2 12h20M4.9 19.1L19.1 4.9M9 3l3 2 3-2M9 21l3-2 3 2"/></symbol>
  <symbol id="i-mirror" viewBox="0 0 24 24"><rect x="2" y="4" width="8" height="7" rx="1.5"/><rect x="14" y="4" width="8" height="7" rx="1.5"/><path d="M7 18h10M15 16l2 2-2 2M9 16l-2 2 2 2"/></symbol>
  <symbol id="i-extend" viewBox="0 0 24 24"><rect x="2" y="5" width="11" height="9" rx="1.5"/><rect x="15" y="5" width="7" height="9" rx="1.5"/><path d="M7 18h10"/></symbol>
  <symbol id="i-moon" viewBox="0 0 24 24"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></symbol>
  <symbol id="i-erase" viewBox="0 0 24 24"><path d="M7 21h10M5 15l9-9 5 5-9 9H7z"/></symbol>
  <symbol id="i-prev" viewBox="0 0 24 24"><path d="M15 6l-6 6 6 6"/></symbol>
  <symbol id="i-next" viewBox="0 0 24 24"><path d="M9 6l6 6-6 6"/></symbol>
  <symbol id="i-play" viewBox="0 0 24 24"><path d="M7 5v14l11-7z"/></symbol>
  <symbol id="i-pause" viewBox="0 0 24 24"><path d="M8 5v14M16 5v14"/></symbol>
  <symbol id="i-back10" viewBox="0 0 24 24"><path d="M11 17l-5-5 5-5M18 17l-5-5 5-5"/></symbol>
  <symbol id="i-fwd10" viewBox="0 0 24 24"><path d="M13 17l5-5-5-5M6 17l5-5-5-5"/></symbol>
  <symbol id="i-timer" viewBox="0 0 24 24"><circle cx="12" cy="13" r="8"/><path d="M12 9v4l2 2M9 2h6"/></symbol>
  <symbol id="i-bulb" viewBox="0 0 24 24"><path d="M9 18h6M10 22h4M12 2a7 7 0 0 0-4 12.7V16h8v-1.3A7 7 0 0 0 12 2z"/></symbol>
  <symbol id="i-sliders" viewBox="0 0 24 24"><path d="M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M1 14h6M9 8h6M17 16h6"/></symbol>
  <symbol id="i-slides" viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="12" rx="2"/><path d="M8 20h8M12 16v4"/><path d="M10 8l4 2-4 2z"/></symbol>
  <symbol id="i-send" viewBox="0 0 24 24"><path d="M22 2L11 13M22 2l-7 20-4-9-9-4z"/></symbol>
  <symbol id="i-camera" viewBox="0 0 24 24"><path d="M3 8a2 2 0 0 1 2-2h2l2-2h6l2 2h2a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><circle cx="12" cy="13" r="4"/></symbol>
  <symbol id="i-image" viewBox="0 0 24 24"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="M21 15l-5-5L5 21"/></symbol>
  <symbol id="i-link" viewBox="0 0 24 24"><path d="M10 13a5 5 0 0 0 7.5.5l3-3a5 5 0 0 0-7-7l-1.7 1.7M14 11a5 5 0 0 0-7.5-.5l-3 3a5 5 0 0 0 7 7l1.7-1.7"/></symbol>
  <symbol id="i-text" viewBox="0 0 24 24"><path d="M4 7V4h16v3M9 20h6M12 4v16"/></symbol>
  <symbol id="i-stop" viewBox="0 0 24 24"><rect x="5" y="5" width="14" height="14" rx="2"/></symbol>
  <symbol id="i-pen" viewBox="0 0 24 24"><path d="M12 20h9M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/></symbol>
  <symbol id="i-marker" viewBox="0 0 24 24"><path d="M9 11l-6 6v3h9l3-3M22 12l-4.6 4.6a2 2 0 0 1-2.8 0l-5.2-5.2a2 2 0 0 1 0-2.8L14 4"/></symbol>
  <symbol id="i-dot" viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/><circle cx="12" cy="12" r="8"/></symbol>
  <symbol id="i-undo" viewBox="0 0 24 24"><path d="M9 14L4 9l5-5"/><path d="M4 9h10.5a5.5 5.5 0 0 1 0 11H11"/></symbol>
  <symbol id="i-trash" viewBox="0 0 24 24"><path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6"/></symbol>
  <symbol id="i-phone" viewBox="0 0 24 24"><rect x="6" y="2" width="12" height="20" rx="2.5"/><path d="M11 18h2"/></symbol>
  <symbol id="i-qr" viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><path d="M14 14h3v3M21 14v7h-4M14 18v3"/></symbol>
  <symbol id="i-home" viewBox="0 0 24 24"><path d="M3 11l9-8 9 8M5 10v10h14V10"/></symbol>
  <symbol id="i-mouse" viewBox="0 0 24 24"><rect x="6" y="3" width="12" height="18" rx="6"/><path d="M12 7v4"/></symbol>
  <symbol id="i-expand" viewBox="0 0 24 24"><path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/></symbol>
</svg>
<header><div class="logo"><svg class="i"><use href="#i-logo"/></svg></div>
  <div class="t"><h1>AluPC</h1><div class="now"><span class="dot" id="dot"></span><span id="now">Verbinde …</span></div></div></header>
<div class="offline" id="offline">Keine Verbindung zu AluPC – gleiches WLAN? Versuche es weiter …</div>

<div class="card" id="login">
  <h2>Code eingeben</h2>
  <p>Den 6-stelligen Code zeigt AluPC unter dem QR-Code an.</p>
  <input type="text" id="code" class="big" inputmode="numeric" maxlength="7" autocomplete="off">
  <button class="primary" style="width:100%;margin-top:10px" onclick="saveCode()">Verbinden</button>
</div>

<div id="main">
<!-- ============================================================ Start -->
<div class="page sel" id="p-start">
  <div class="card" style="padding:10px" id="c-live">
    <div class="preview" id="preview"><img id="prev" alt=""><div class="laser" id="laser"></div>
      <span class="badge"><i></i>LIVE · <span id="live-hint">Finger = Laser</span></span></div>
  </div>
  <div id="control">
  <div class="card">
    <h2>Monitor 2</h2>
    <div class="grid">
      <button class="tile" id="b-schwarz" onclick="cmd('schwarz')"><svg class="i"><use href="#i-black"/></svg>Schwarz</button>
      <button class="tile" id="b-standbild" onclick="cmd('standbild')"><svg class="i"><use href="#i-freeze"/></svg>Standbild</button>
      <button class="tile" id="b-schoner" onclick="cmd('bildschirmschoner')"><svg class="i"><use href="#i-moon"/></svg>Schoner</button>
      <button class="tile" id="b-spiegeln" onclick="cmd('spiegeln')"><svg class="i"><use href="#i-mirror"/></svg>Spiegeln</button>
      <button class="tile" id="b-erweitern" onclick="cmd('erweitern')"><svg class="i"><use href="#i-extend"/></svg>Erweitern</button>
      <button class="tile" onclick="cmd('zeichnungen_loeschen')"><svg class="i"><use href="#i-erase"/></svg>Radieren</button>
    </div>
  </div>
  <div class="card">
    <h2>Zeigen</h2>
    <div class="grid4">
      <button class="tile" onclick="cmd('kamera')"><svg class="i"><use href="#i-camera"/></svg>Kamera</button>
      <button class="tile" onclick="cmd('airplay')"><svg class="i"><use href="#i-phone"/></svg>iPhone</button>
      <button class="tile" onclick="cmd('qr')"><svg class="i"><use href="#i-qr"/></svg>QR-Code</button>
      <button class="tile" onclick="cmd('timer_zeigen')"><svg class="i"><use href="#i-timer"/></svg>Timer</button>
    </div>
  </div>
  <div class="card hide" id="c-ablauf">
    <h2>Ablauf</h2>
    <div class="row">
      <button onclick="cmd('ablauf_zurueck')"><svg class="i"><use href="#i-prev"/></svg>Zurück</button>
      <button class="primary" onclick="cmd('ablauf_weiter')">Nächster Punkt<svg class="i"><use href="#i-next"/></svg></button>
    </div>
  </div>
  <div class="card" id="c-scenes">
    <h2>Szenen</h2>
    <div class="row">
      <button onclick="cmd('vorherige_szene')"><svg class="i"><use href="#i-prev"/></svg>Zurück</button>
      <button onclick="cmd('naechste_szene')">Weiter<svg class="i"><use href="#i-next"/></svg></button>
    </div>
    <div class="scenes" id="scenes"></div>
  </div>
  <div class="card" id="c-video">
    <h2>Video</h2>
    <div class="row">
      <button onclick="cmd('video_zurueck')"><svg class="i"><use href="#i-back10"/></svg>10 s</button>
      <button class="primary" onclick="cmd('video_pause')"><svg class="i"><use href="#i-pause"/></svg>Pause</button>
      <button onclick="cmd('video_vor')">10 s<svg class="i"><use href="#i-fwd10"/></svg></button>
    </div>
  </div>
  <div class="card" id="c-vol">
    <h2>Lautstärke <span id="vol-val"></span></h2>
    <input type="range" id="vol" min="0" max="100" step="5" oninput="$('vol-val').textContent = this.value + ' %'"
           onchange="cmd('lautstaerke:' + this.value)">
  </div>
  <div class="card">
    <h2>Timer</h2>
    <div class="timer" id="timer">–</div>
    <div class="chips">
      <button onclick="cmd('timer:60')">1 min</button><button onclick="cmd('timer:180')">3 min</button>
      <button onclick="cmd('timer:300')">5 min</button><button onclick="cmd('timer:600')">10 min</button>
      <button onclick="cmd('timer:900')">15 min</button>
    </div>
    <div class="row">
      <button onclick="cmd('timer_minus')">− 1</button>
      <button class="primary" onclick="cmd('timer_start_pause')"><svg class="i"><use href="#i-play"/></svg>Los</button>
      <button onclick="cmd('timer_plus')">+ 1</button>
    </div>
    <div class="row" style="margin-top:8px">
      <button onclick="cmd('timer_zeigen')"><svg class="i"><use href="#i-timer"/></svg>Zeigen</button>
      <button onclick="cmd('timer_neustart')">Neu</button>
      <button onclick="cmd('timer_stopp')"><svg class="i"><use href="#i-stop"/></svg>Stopp</button>
    </div>
  </div>
  <div class="card" id="c-rgb">
    <h2>RGB-Licht</h2>
    <div class="row">
      <button id="r-farbe" onclick="cmd('rgb_farbe')"><svg class="i"><use href="#i-bulb"/></svg>Farbe</button>
      <button id="r-monitor2" onclick="cmd('rgb_monitor2')">Wie Bild</button>
      <button id="r-aus" onclick="cmd('rgb_aus')">Aus</button>
    </div>
  </div>
  </div>
  <div class="card hide" id="c-nocontrol"><div class="hint" style="margin:0">Fernsteuern ist in AluPC ausgeschaltet
    (Setup → Handy &amp; Kamera).</div></div>
</div>

<!-- ============================================================ Zeichnen -->
<div class="page draw" id="p-zeichnen">
  <div class="card" style="padding:10px">
    <div class="preview" id="dpreview"><img id="dprev" alt=""><canvas id="ink"></canvas><div class="laser" id="dlaser"></div>
      <span class="badge"><i></i><span id="tool-name">Stift</span></span>
      <button class="corner small" onclick="toggleFull()" aria-label="Vollbild"><svg class="i"><use href="#i-expand"/></svg></button></div>
  </div>
  <div class="card">
    <div class="tools">
      <button id="t-laser" onclick="pick('laser')"><svg class="i"><use href="#i-dot"/></svg>Laser</button>
      <button id="t-stift" class="on" onclick="pick('stift')"><svg class="i"><use href="#i-pen"/></svg>Stift</button>
      <button id="t-marker" onclick="pick('marker')"><svg class="i"><use href="#i-marker"/></svg>Marker</button>
      <button id="t-radierer" onclick="pick('radierer')"><svg class="i"><use href="#i-erase"/></svg>Radierer</button>
    </div>
    <div class="colors" id="colors"></div>
    <div class="row" style="margin-top:12px">
      <button onclick="cmd('zeichnung_zurueck')"><svg class="i"><use href="#i-undo"/></svg>Rückgängig</button>
      <button onclick="cmd('zeichnungen_loeschen')"><svg class="i"><use href="#i-trash"/></svg>Alles löschen</button>
    </div>
    <div class="hint">Mit dem Finger auf das Bild zeichnen – erscheint sofort auf Monitor 2.</div>
  </div>
</div>

<!-- ============================================================ Folien -->
<div class="page" id="p-folien">
  <div id="c-keys">
    <div class="card">
      <div class="clicker">
        <button onclick="key('zurueck')"><svg class="i"><use href="#i-prev"/></svg>Zurück</button>
        <button class="primary" onclick="key('weiter')"><svg class="i"><use href="#i-next"/></svg>Weiter</button>
      </div>
      <div class="row" style="margin-top:10px">
        <button onclick="key('start')"><svg class="i"><use href="#i-play"/></svg>Start</button>
        <button onclick="key('schwarz')"><svg class="i"><use href="#i-black"/></svg>Schwarz</button>
        <button onclick="key('ende')"><svg class="i"><use href="#i-stop"/></svg>Ende</button>
      </div>
      <div class="hint">PowerPoint, LibreOffice Impress, PDF-Anzeigen … – das Programm muss am PC im Vordergrund sein.
        Lautstärketasten des Handys gehen nicht (das erlauben Browser nicht).</div>
    </div>
    <div class="card">
      <h2>Touchpad <span>Maus des PCs</span></h2>
      <div class="pad" id="pad">Wischen = Maus bewegen · Tippen = Klick<br>Zwei Finger: Tippen = Rechtsklick, Wischen = Scrollen</div>
      <div class="row" style="margin-top:8px">
        <button onclick="mouse({click:'links'})">Linksklick</button>
        <button onclick="mouse({click:'rechts'})">Rechtsklick</button>
      </div>
    </div>
  </div>
  <div class="card hide" id="c-nokeys"><div class="hint" style="margin:0">Tasten und Maus per Handy gehen unter Wayland nicht –
    am PC die Sitzung „Plasma (X11)“ wählen. Laserpointer, Zeichnen und alles andere funktionieren trotzdem.</div></div>
</div>

<!-- ============================================================ Senden -->
<div class="page" id="p-senden">
  <div class="card">
    <h2>Foto oder Video</h2>
    <div class="row">
      <label class="btn primary" for="cam"><svg class="i"><use href="#i-camera"/></svg>Foto machen</label>
      <label class="btn" for="gal"><svg class="i"><use href="#i-image"/></svg>Galerie</label>
    </div>
    <input type="file" id="cam" accept="image/*" capture="environment">
    <input type="file" id="gal" accept="image/*,video/*">
    <div class="bar" id="bar"><div></div></div>
    <div class="hint" id="upinfo">Wird sofort auf Monitor 2 gezeigt.</div>
  </div>
  <div class="card">
    <h2>Link</h2>
    <input type="url" id="url" placeholder="https://… (z. B. YouTube)" autocomplete="off">
    <button class="primary" style="width:100%;margin-top:8px" onclick="sendLink()"><svg class="i"><use href="#i-link"/></svg>Auf Monitor 2 öffnen</button>
    <div class="hint">YouTube: „Teilen → Link kopieren“ und hier einfügen – läuft im Vollbild.</div>
  </div>
  <div class="card">
    <h2>Text</h2>
    <textarea id="text" placeholder="Text für Monitor 2"></textarea>
    <button style="width:100%;margin-top:8px" onclick="sendText()"><svg class="i"><use href="#i-text"/></svg>Anzeigen</button>
  </div>
</div>
</div>

<nav id="nav">
  <button class="sel" data-p="start" onclick="tab('start')"><svg class="i"><use href="#i-home"/></svg>Start</button>
  <button data-p="zeichnen" onclick="tab('zeichnen')"><svg class="i"><use href="#i-pen"/></svg>Zeichnen</button>
  <button data-p="folien" onclick="tab('folien')"><svg class="i"><use href="#i-slides"/></svg>Folien</button>
  <button data-p="senden" onclick="tab('senden')"><svg class="i"><use href="#i-send"/></svg>Senden</button>
</nav>
<div class="toast" id="toast"></div>

<script>
const params = new URLSearchParams(location.search);
const store = {  // privater Modus: Speicher kann fehlen → dann eben nur für diese Seite merken
  get(k) { try { return localStorage.getItem(k) || ""; } catch (e) { return ""; } },
  set(k, v) { try { v ? localStorage.setItem(k, v) : localStorage.removeItem(k); } catch (e) {} },
};
let code = params.get("k") || store.get("alucast-code");
if (params.get("k")) { store.set("alucast-code", code); history.replaceState(null, "", location.pathname); }
const $ = id => document.getElementById(id);
let current = store.get("alucast-tab") || "start";
let allow = { senden: true, steuern: true, live: true, laser: true };

function tab(name) {
  const btn = document.querySelector('nav button[data-p="' + name + '"]');
  if (!btn || btn.classList.contains("hide")) name = "start";
  current = name; store.set("alucast-tab", name);
  for (const b of document.querySelectorAll("nav button")) b.classList.toggle("sel", b.dataset.p === name);
  for (const p of document.querySelectorAll(".page")) p.classList.toggle("sel", p.id === "p-" + name);
  document.body.classList.remove("full");
  window.scrollTo(0, 0); loadPreview(); sizeInk();
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
  code = ""; store.set("alucast-code", ""); showLogin(true);
}
function saveCode() { code = $("code").value.replace(/\D/g, ""); store.set("alucast-code", code); refresh(); }
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
function key(k) { buzz(); post("/api/cmd", { cmd: "taste:" + k }); }
function sendLink() {
  const u = $("url").value.trim(); if (!u) return;
  post("/api/link", { url: u }, "Wird geöffnet …"); $("url").value = "";
}
function sendText() {
  const t = $("text").value.trim(); if (!t) return;
  post("/api/text", { text: t }, "Angezeigt");
}

let scenesKey = "", failures = 0;
async function refresh() {
  if (!code) { showLogin(true); return; }
  try {
    const s = await api("/api/status");
    failures = 0; $("offline").classList.remove("show");
    showLogin(false);
    $("dot").classList.add("on");
    $("now").textContent = s.now;
    allow = Object.assign({ senden: true, steuern: true, live: true, laser: true }, s.allow || {});
    for (const [p, on] of [["zeichnen", allow.laser], ["folien", allow.steuern], ["senden", allow.senden]])
      document.querySelector('nav button[data-p="' + p + '"]').classList.toggle("hide", !on);
    if (document.querySelector('nav button[data-p="' + current + '"]').classList.contains("hide")) tab("start");
    $("control").classList.toggle("hide", !allow.steuern);
    $("c-nocontrol").classList.toggle("hide", allow.steuern);
    $("c-live").classList.toggle("hide", !allow.live);
    $("live-hint").textContent = allow.laser ? "Finger = Laser" : "Live-Bild";
    const f = s.flags || {};
    for (const [id, on] of [["b-schwarz", f.schwarz], ["b-standbild", f.standbild], ["b-spiegeln", f.spiegeln],
                            ["b-erweitern", f.erweitern], ["b-schoner", f.schoner]]) $(id).classList.toggle("on", !!on);
    $("c-video").classList.toggle("hide", !s.video);
    $("c-ablauf").classList.toggle("hide", !s.ablauf);
    $("c-vol").classList.toggle("hide", !s.sound);
    if (document.activeElement !== $("vol")) { $("vol").value = s.volume; $("vol-val").textContent = s.volume + " %"; }
    $("timer").textContent = s.timer || "–";
    $("c-rgb").classList.toggle("hide", !s.rgb);
    for (const m of ["farbe", "monitor2", "aus"]) $("r-" + m).classList.toggle("on", s.rgb === m);
    $("c-keys").classList.toggle("hide", s.keys === false);
    $("c-nokeys").classList.toggle("hide", s.keys !== false);
    $("c-scenes").classList.toggle("hide", !s.scenes.length);
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
    else if (/warten|beendet/.test(e.message)) $("now").textContent = e.message;
    else if (++failures >= 2) { $("now").textContent = "Keine Verbindung"; $("offline").classList.add("show"); }
  }
}

// ---- Live-Bild (nur, solange ein Reiter mit Bild offen und die Seite sichtbar ist)
let prevUrl = null, prevBusy = false;
async function loadPreview() {
  if (!code || prevBusy || !allow.live || current === "senden" || current === "folien" || document.hidden) return;
  prevBusy = true;
  try {
    const r = await fetch("/api/preview", { headers: { "X-AluPC-Code": code } });
    if (r.ok && r.status === 200) {
      const url = URL.createObjectURL(await r.blob());
      $("prev").src = url; $("dprev").src = url;
      $("dprev").onload = () => {  // Seitenverhältnis von Monitor 2 übernehmen
        const ar = $("dprev").naturalWidth / $("dprev").naturalHeight;
        if (ar > 0.2 && ar < 5 && Math.abs(ar - (window._ar || 0)) > 0.01) {
          window._ar = ar; document.documentElement.style.setProperty("--ar", ar);
          for (const pv of [$("preview"), $("dpreview")]) pv.style.aspectRatio = String(ar);
          sizeInk();
        }
      };
      if (prevUrl) URL.revokeObjectURL(prevUrl);
      prevUrl = url;
    }
  } catch (e) {}
  prevBusy = false;
}

// ---- Senden mit „immer nur das Neueste“ (Laser, Zeichnen, Maus): nie einen Rückstau aufbauen
function sender(path, merge) {
  let pending = null, busy = false;
  function flush() {
    if (!pending) return;
    busy = true; const body = JSON.stringify(pending); pending = null;
    fetch(path, { method: "POST", headers: { "X-AluPC-Code": code, "Content-Type": "application/json" }, body })
      .catch(() => {}).finally(() => setTimeout(() => { busy = false; flush(); }, 20));
  }
  return function (obj, force) {
    if (force) {  // Anfang/Ende eines Strichs, Klicks: nie verschmelzen oder verlieren
      const body = JSON.stringify(obj);
      const go = () => fetch(path, { method: "POST", headers: { "X-AluPC-Code": code, "Content-Type": "application/json" }, body }).catch(() => {});
      if (pending) { const p = pending; pending = null; fetch(path, { method: "POST", headers: { "X-AluPC-Code": code, "Content-Type": "application/json" }, body: JSON.stringify(p) }).catch(() => {}).finally(go); }
      else go();
      return;
    }
    pending = merge && pending ? merge(pending, obj) : obj;
    if (!busy) flush();
  };
}
const sendLaser = sender("/api/laser");
const sendDraw = sender("/api/draw");
const sendMouse = sender("/api/mouse", (a, b) => ({ dx: (a.dx || 0) + (b.dx || 0), dy: (a.dy || 0) + (b.dy || 0) }));
function mouse(obj) { buzz(); sendMouse(obj, true); }

function norm(pv, e) {
  const box = pv.getBoundingClientRect();
  return { x: Math.min(1, Math.max(0, (e.clientX - box.left) / box.width)),
           y: Math.min(1, Math.max(0, (e.clientY - box.top) / box.height)) };
}
function laserOn(pv, dot) {
  function point(e) {
    if (!allow.laser) return;
    const p = norm(pv, e);
    dot.style.display = "block"; dot.style.left = (p.x * 100) + "%"; dot.style.top = (p.y * 100) + "%";
    sendLaser(p);
  }
  function release() { dot.style.display = "none"; if (allow.laser) sendLaser({ up: true }, true); }
  pv.addEventListener("pointerdown", e => { pv.setPointerCapture(e.pointerId); point(e); });
  pv.addEventListener("pointermove", e => { if (e.buttons || e.pointerType === "touch") point(e); });
  pv.addEventListener("pointerup", release);
  pv.addEventListener("pointercancel", release);
}
laserOn($("preview"), $("laser"));

// ---- Zeichnen: Strich sofort auf dem Handy sehen, gleichzeitig auf Monitor 2
const COLORS = ["#ef4444", "#f59e0b", "#22c55e", "#3b82f6", "#a855f7", "#ffffff", "#111827"];
let tool = store.get("alucast-tool") || "stift", color = store.get("alucast-color") || COLORS[0];
const NAMES = { laser: "Laser", stift: "Stift", marker: "Marker", radierer: "Radierer" };
for (const c of COLORS) {
  const b = document.createElement("button"); b.style.background = c; b.dataset.c = c;
  b.onclick = () => { color = c; store.set("alucast-color", c); if (tool === "laser" || tool === "radierer") pick("stift"); showTools(); };
  $("colors").appendChild(b);
}
function pick(t) { tool = t; store.set("alucast-tool", t); showTools(); buzz(); }
function showTools() {
  for (const t of Object.keys(NAMES)) $("t-" + t).classList.toggle("on", t === tool);
  for (const b of $("colors").children) b.classList.toggle("sel", b.dataset.c === color && tool !== "laser" && tool !== "radierer");
  $("tool-name").textContent = NAMES[tool];
}
showTools();
const ink = $("ink"), dpv = $("dpreview");
function sizeInk() {
  const box = dpv.getBoundingClientRect();
  ink.width = Math.round(box.width * devicePixelRatio); ink.height = Math.round(box.height * devicePixelRatio);
}
window.addEventListener("resize", sizeInk);
let last = null, fadeTimer = null;
function inkLine(a, b) {
  const g = ink.getContext("2d"); g.lineCap = "round"; g.lineJoin = "round";
  g.strokeStyle = color; g.globalAlpha = tool === "marker" ? .4 : 1;
  g.lineWidth = (tool === "marker" ? 14 : 4) * devicePixelRatio;
  g.beginPath(); g.moveTo(a.x * ink.width, a.y * ink.height); g.lineTo(b.x * ink.width, b.y * ink.height); g.stroke();
}
dpv.addEventListener("pointerdown", e => {
  if (e.target.closest("button")) return;
  dpv.setPointerCapture(e.pointerId); const p = norm(dpv, e); last = p; clearTimeout(fadeTimer);
  if (tool === "laser") { sendLaser(p); dotAt(p); return; }
  sendDraw({ phase: "down", x: p.x, y: p.y, tool, color }, true);
});
dpv.addEventListener("pointermove", e => {
  if (!last) return;
  const p = norm(dpv, e);
  if (tool === "laser") { sendLaser(p); dotAt(p); return; }
  if (tool !== "radierer") inkLine(last, p);
  last = p; sendDraw({ phase: "move", x: p.x, y: p.y, tool, color });
});
function penUp() {
  if (!last) return; last = null;
  if (tool === "laser") { $("dlaser").style.display = "none"; sendLaser({ up: true }, true); return; }
  sendDraw({ phase: "up" }, true);
  // eigener Strich verschwindet, sobald das Live-Bild ihn zeigt
  fadeTimer = setTimeout(() => ink.getContext("2d").clearRect(0, 0, ink.width, ink.height), 1600);
}
dpv.addEventListener("pointerup", penUp);
dpv.addEventListener("pointercancel", penUp);
function dotAt(p) { const d = $("dlaser"); d.style.display = "block"; d.style.left = (p.x * 100) + "%"; d.style.top = (p.y * 100) + "%"; }
function toggleFull() { document.body.classList.toggle("full"); setTimeout(sizeInk, 50); }

// ---- Touchpad: ein Finger bewegt, Tippen klickt; zwei Finger scrollen bzw. Rechtsklick
const pad = $("pad"), touches = new Map();
let moved = 0, downAt = 0, maxFingers = 0, scrollAcc = 0;
pad.addEventListener("pointerdown", e => {
  pad.setPointerCapture(e.pointerId); touches.set(e.pointerId, { x: e.clientX, y: e.clientY });
  if (touches.size === 1) { moved = 0; downAt = Date.now(); maxFingers = 1; scrollAcc = 0; }
  maxFingers = Math.max(maxFingers, touches.size); pad.classList.add("active");
});
pad.addEventListener("pointermove", e => {
  const t = touches.get(e.pointerId); if (!t) return;
  const dx = e.clientX - t.x, dy = e.clientY - t.y; t.x = e.clientX; t.y = e.clientY;
  moved += Math.abs(dx) + Math.abs(dy);
  if (touches.size >= 2) {  // zwei Finger: scrollen
    scrollAcc += dy / touches.size;
    if (Math.abs(scrollAcc) > 18) { sendMouse({ scroll: scrollAcc > 0 ? 1 : -1 }, true); scrollAcc = 0; }
    return;
  }
  const speed = 1 + Math.min(2.5, Math.hypot(dx, dy) / 12);  // schnell wischen = weiter
  sendMouse({ dx: dx * 1.8 * speed, dy: dy * 1.8 * speed });
});
function padUp(e) {
  touches.delete(e.pointerId);
  if (touches.size) return;
  pad.classList.remove("active");
  if (moved < 10 && Date.now() - downAt < 300) mouse({ click: maxFingers >= 2 ? "rechts" : "links" });
}
pad.addEventListener("pointerup", padUp);
pad.addEventListener("pointercancel", padUp);

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
tab(current);
refresh(); setInterval(refresh, 2000);
loadPreview(); setInterval(loadPreview, 700);
document.addEventListener("visibilitychange", () => { if (!document.hidden) { refresh(); loadPreview(); } });
</script>
</body>
</html>
"""
