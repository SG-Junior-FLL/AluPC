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
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, viewport-fit=cover, user-scalable=no">
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
html, body { margin:0; touch-action:manipulation; }  /* kein Doppeltipp-Zoom */
button, .btn, nav, .card { touch-action:manipulation; }
body { font:16px/1.4 -apple-system,system-ui,"Segoe UI",Roboto,sans-serif; color:var(--text); min-height:100vh;
       background:var(--bg); padding:0 14px calc(100px + env(safe-area-inset-bottom));
       -webkit-user-select:none; user-select:none; }
/* Hintergrund: langsam fließende Farbwolken */
body::before { content:""; position:fixed; inset:-20%; z-index:-1; pointer-events:none;
  background:radial-gradient(40% 35% at 20% 10%, rgba(99,102,241,.40), transparent 70%),
             radial-gradient(35% 30% at 85% 20%, rgba(236,72,153,.22), transparent 70%),
             radial-gradient(45% 35% at 60% 95%, rgba(14,165,233,.20), transparent 70%);
  animation:drift 22s ease-in-out infinite alternate; }
@keyframes drift { 0% { transform:translate(0,0) rotate(0deg); } 50% { transform:translate(3%,-2%) rotate(4deg); }
                   100% { transform:translate(-3%,2%) rotate(-3deg); } }
svg.i { width:22px; height:22px; stroke:currentColor; fill:none; stroke-width:1.9; stroke-linecap:round;
        stroke-linejoin:round; flex:none; }
header { display:flex; align-items:center; gap:12px; padding:calc(14px + env(safe-area-inset-top)) 2px 12px;
         position:sticky; top:0; z-index:5; background:linear-gradient(var(--bg) 70%, transparent); }
.logo { width:40px; height:40px; border-radius:12px; background:linear-gradient(135deg,#6366f1,#8b5cf6,#ec4899,#6366f1);
        background-size:300% 300%; animation:shine 8s ease infinite; display:grid; place-items:center; color:#fff;
        box-shadow:0 6px 20px rgba(99,102,241,.45); }
@keyframes shine { 0%,100% { background-position:0% 50%; } 50% { background-position:100% 50%; } }
.logo svg { width:24px; height:24px; }
header .t { min-width:0; flex:1; }
header h1 { margin:0; font-size:18px; letter-spacing:.2px; }
header .now { font-size:13px; color:var(--muted); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.dot { width:9px; height:9px; border-radius:50%; background:#64748b; display:inline-block; margin-right:6px; }
.dot.on { background:var(--ok); animation:ring 2.4s ease-out infinite; }
@keyframes ring { 0% { box-shadow:0 0 0 0 rgba(34,197,94,.55); } 70%,100% { box-shadow:0 0 0 9px rgba(34,197,94,0); } }
.offline { display:none; background:var(--bad); color:#fff; border-radius:14px; padding:10px 12px; margin-bottom:12px;
           font-size:14px; font-weight:600; }
.offline.show { display:block; }
.card { background:var(--card); border:1px solid var(--line); border-radius:22px; padding:14px; margin-bottom:12px;
        backdrop-filter:blur(14px); -webkit-backdrop-filter:blur(14px); box-shadow:0 10px 30px rgba(2,6,23,.18); }
/* Karten fliegen beim Tab-Wechsel nacheinander ein */
.page.sel > .card { animation:rise .42s cubic-bezier(.2,.9,.25,1.15) both; }
.page.sel > .card:nth-child(2) { animation-delay:.05s; } .page.sel > .card:nth-child(3) { animation-delay:.1s; }
.page.sel > .card:nth-child(4) { animation-delay:.15s; } .page.sel > .card:nth-child(5) { animation-delay:.2s; }
.page.sel > .card:nth-child(n+6) { animation-delay:.25s; }
@keyframes rise { from { opacity:0; transform:translateY(14px) scale(.98); } to { opacity:1; transform:none; } }
.card h2 { margin:0 0 10px; font-size:12px; color:var(--muted); font-weight:700; text-transform:uppercase; letter-spacing:.8px;
           display:flex; align-items:center; justify-content:space-between; }
.row { display:flex; gap:8px; }
select { font: inherit; padding: 12px; border-radius: 12px; background: var(--card2); color: var(--text); border: 1px solid var(--line, #334155); }
.row > * { flex:1 1 0; min-width:0; }
.grid { display:grid; grid-template-columns:repeat(3,1fr); gap:8px; }
.grid4 { display:grid; grid-template-columns:repeat(4,1fr); gap:8px; }
button, .btn { appearance:none; border:0; border-radius:16px; padding:13px 8px; font:inherit; font-weight:650; font-size:14.5px;
         background:var(--card2); color:var(--text); cursor:pointer; text-align:center; display:flex; align-items:center;
         justify-content:center; gap:8px; position:relative; overflow:hidden;
         transition:transform .18s cubic-bezier(.3,1.6,.5,1), background .25s, box-shadow .25s, color .25s; }
/* Tipp-Welle */
.ripple { position:absolute; border-radius:50%; background:currentColor; opacity:.25; transform:scale(0);
          animation:ripple .55s ease-out forwards; pointer-events:none; }
@keyframes ripple { to { transform:scale(1); opacity:0; } }
.tile { flex-direction:column; gap:6px; padding:14px 4px; font-size:13px; }
.tile svg.i { width:26px; height:26px; }
button.on, .tile.on { background:var(--on); color:#fff; animation:glow 2.8s ease-in-out infinite; }
@keyframes glow { 0%,100% { box-shadow:0 8px 22px rgba(99,102,241,.35); } 50% { box-shadow:0 8px 30px rgba(139,92,246,.6); } }
.tile.on svg.i { animation:pop .35s cubic-bezier(.3,1.8,.5,1); }
@keyframes pop { from { transform:scale(.6); } to { transform:none; } }
button.primary, .btn.primary { background:var(--on); color:#fff; }
button.small { padding:8px 10px; font-size:13px; border-radius:12px; }
button:active, .btn:active { transform:scale(.93); transition-duration:.06s; }
input[type=text], input[type=url], textarea { width:100%; border:1px solid var(--line); border-radius:14px; padding:13px;
         font:inherit; background:var(--card2); color:var(--text); -webkit-user-select:text; user-select:text; outline:none; }
textarea { min-height:80px; resize:vertical; }
input[type=file] { display:none; }
input[type=range] { width:100%; accent-color:#8b5cf6; height:30px; }
.hint { color:var(--muted); font-size:12.5px; margin-top:8px; }
.live-row { display:flex; align-items:center; gap:8px; margin-top:10px; font-size:14px; color:var(--muted); }
.live-row input { width:22px; height:22px; accent-color:#ef4444; }
.live-row b { color:#ef4444; }
.bar { height:8px; border-radius:4px; background:var(--line); overflow:hidden; margin-top:10px; display:none; }
.bar > div { height:100%; width:0; background:var(--on); transition:width .15s; }
.scenes { display:grid; grid-template-columns:repeat(auto-fill,minmax(120px,1fr)); gap:8px; margin-top:8px; }
#recent { grid-template-columns:repeat(auto-fill,minmax(260px,1fr)); }
.card.empty { text-align:center; padding:28px 18px; }
.card.empty .big { width:44px; height:44px; opacity:.55; margin-bottom:8px; }
.card.empty h3 { margin:4px 0 8px; font-size:17px; }
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
.askrow { display:flex; gap:8px; }
.askrow input { flex:1; font-size:16px; }
.askrow button { flex:0 0 52px; padding:0; }
.reply { margin-top:10px; padding:10px 12px; border-radius:12px; background:var(--soft, rgba(139,92,246,.12));
  font-size:15px; display:none; }
.reply.show { display:block; animation:pop .25s ease-out; }
.reply.bad { background:rgba(239,68,68,.14); }
@keyframes pop { from { transform:scale(.97); opacity:0 } to { transform:none; opacity:1 } }
.chips { display:flex; gap:6px; flex-wrap:wrap; margin-bottom:10px; }
.chips button { flex:1 1 auto; padding:9px 6px; font-size:13.5px; border-radius:12px; }
.big { font-size:30px; letter-spacing:8px; text-align:center; }
/* Zeichnen */
.wbg { display:flex; flex-wrap:wrap; gap:8px; }
.wbg button { flex:1 1 30%; min-width:96px; padding:12px 6px; font-size:14px; overflow-wrap:anywhere; }
.tools { display:grid; grid-template-columns:repeat(4,1fr); gap:8px; }
.tools button { flex-direction:column; gap:4px; padding:10px 4px; font-size:12.5px; }
.colors { display:flex; gap:8px; justify-content:space-between; margin-top:12px; }
/* schrumpfen statt überstehen: 7–8 Farben passen auch aufs kleine Handy */
.colors button { flex:1 1 0; min-width:0; max-width:40px; height:auto; aspect-ratio:1; border-radius:50%; padding:0;
                 border:3px solid transparent; }
.colors button { box-shadow:inset 0 0 0 1px rgba(127,127,127,.35); }  /* Weiß auf heller Karte sichtbar */
.colors button.sel { border-color:var(--text); transform:scale(1.08); }
/* Seitenverhältnis = Bildschirm (per JS aus dem Live-Bild), damit Finger und Monitor genau übereinstimmen */
/* Vergrößern: das Bild hängt dann direkt an der Seite (sonst läge es unter der schwarzen Abdeckung) */
.preview.fullview { position:fixed; left:50%; top:50%; transform:translate(-50%,-50%); border-radius:0; z-index:20;
                    width:min(100vw, calc(100vh * var(--ar, 1.7778))); height:auto; margin:0; touch-action:none; }
body.full::after { content:""; position:fixed; inset:0; background:#000; z-index:19; }
.fullview .corner { display:none; }
#fullclose { display:none; }
body.full #fullclose { display:flex; position:fixed; top:max(12px, env(safe-area-inset-top)); right:12px; z-index:30;
                       width:auto; min-height:44px; padding:8px 16px; border-radius:22px; background:rgba(15,23,42,.8);
                       color:#fff; font-weight:700; }
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
nav button { flex:1; background:transparent; color:var(--muted); padding:8px 4px; font-size:12px; flex-direction:column; gap:3px;
             border-radius:16px; z-index:1; transition:color .25s; }
nav button.sel { color:#fff; }
nav button.sel svg.i { animation:pop .35s cubic-bezier(.3,1.8,.5,1); }
/* Leuchtpunkt, der zum gewählten Tab gleitet */
#nav-pill { position:absolute; top:6px; height:0; left:6px; width:0; border-radius:16px; background:var(--on);
            box-shadow:0 6px 18px rgba(99,102,241,.45);
            transition:left .38s cubic-bezier(.3,1.35,.5,1), top .38s cubic-bezier(.3,1.35,.5,1), width .38s, height .38s; }
.page { display:none; animation:fade .18s ease; }
.page.sel { display:block; }
@keyframes fade { from { opacity:0; transform:translateY(4px); } to { opacity:1; transform:none; } }
.toast { position:fixed; left:50%; bottom:calc(100px + env(safe-area-inset-bottom)); transform:translate(-50%,16px) scale(.96);
         background:#0f172a; color:#fff; padding:10px 16px; border-radius:999px; font-size:14px; opacity:0;
         transition:opacity .25s, transform .35s cubic-bezier(.3,1.5,.5,1); pointer-events:none; max-width:90vw; z-index:30;
         box-shadow:0 10px 30px rgba(0,0,0,.35); }
.toast.show { opacity:.97; transform:translate(-50%,0) scale(1); }
.toast.bad { background:var(--bad); }
#login { display:none; margin-top:20px; }
.hide { display:none !important; }
/* Tafel-Modus (Whiteboard auf dem Bildschirm): zusätzliche Werkzeuge und die Tafel-Karte */
.bonly, .bonly-card { display:none !important; }
body.board .bonly { display:flex !important; }
body.board .bonly.hide { display:none !important; }
body.board .bonly-card { display:block !important; }
body.board .tools { grid-template-columns:repeat(4,1fr); }
body.board #draw-actions .lbl { display:none; }
body.board #draw-actions > #b-undo, body.board #draw-actions > #b-redo { flex:0 0 56px; }
#widths button.on, #guests button.on { background:var(--on); color:#fff; }
#b-zoom { font-variant-numeric:tabular-nums; min-width:76px; }
/* Feinschliff für alle Größen */
.side { min-width:0; }
.page.sel .side > .card, .page.sel #control > .card { animation:rise .42s cubic-bezier(.2,.9,.25,1.15) both; }
.page.sel #control > .card:nth-child(2) { animation-delay:.04s; } .page.sel #control > .card:nth-child(3) { animation-delay:.08s; }
.page.sel #control > .card:nth-child(n+4) { animation-delay:.12s; }
#c-live { background:linear-gradient(160deg, rgba(99,102,241,.22), rgba(236,72,153,.08)); border-color:rgba(139,92,246,.28); }
.card h2 .i { width:16px; height:16px; }
@media (hover:hover) and (pointer:fine) {
  button:hover, .btn:hover { filter:brightness(1.12); }
  nav button:hover { color:var(--text); filter:none; }
}
/* ---- Tablet (iPad hochkant und größer): Leiste links, mehr Platz, größere Flächen */
@media (min-width: 740px) {
  body { padding:0 calc(20px + env(safe-area-inset-right)) calc(28px + env(safe-area-inset-bottom))
         calc(114px + env(safe-area-inset-left)); font-size:16.5px; }
  header { padding-top:calc(18px + env(safe-area-inset-top)); padding-bottom:16px; }
  header h1 { font-size:21px; }
  header .now { font-size:14px; }
  nav { left:calc(14px + env(safe-area-inset-left)); right:auto; top:calc(14px + env(safe-area-inset-top));
        bottom:calc(14px + env(safe-area-inset-bottom)); width:84px; flex-direction:column; justify-content:center;
        gap:8px; padding:8px; border-radius:28px; }
  nav button { flex:0 0 auto; min-height:76px; padding:8px 0; font-size:12px; gap:6px; border-radius:20px; }
  nav button svg.i { width:26px; height:26px; }
  #nav-pill { border-radius:20px; }
  .toast { bottom:calc(26px + env(safe-area-inset-bottom)); left:calc(50% + 50px); }
  #main { max-width:1500px; }
  .card { padding:18px; border-radius:26px; margin-bottom:16px; }
  .card h2 { font-size:12.5px; margin-bottom:12px; }
  button, .btn { padding:15px 10px; font-size:15px; border-radius:18px; }
  .tile { padding:18px 6px; font-size:14px; gap:8px; }
  .tile svg.i { width:30px; height:30px; }
  .grid, .grid4, .tools { gap:10px; }
  .row { gap:10px; }
  .row + .row { margin-top:10px; }
  input[type=range] { height:36px; }
  .timer { font-size:60px; }
  /* Start: Live-Bild + Bildschirm (eine Reihe) oben; breite Karten über die ganze Breite, kleine paarweise */
  #c-mon2 .grid { grid-template-columns:repeat(6,1fr); }
  #control:not(.hide) { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); column-gap:16px;
                        grid-auto-flow:row dense; align-items:start; }
  #control > .card { grid-column:1 / -1; }
  #control > #c-ablauf, #control > #c-scenes, #control > #c-resume, #control > #c-recent, #control > #c-music,
  #control > #c-vol { grid-column:auto; }
  /* Zeichnen: großes Bild, Werkzeuge daneben bzw. darunter nebeneinander */
  #p-zeichnen.sel { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); column-gap:16px; align-items:start; }
  #p-zeichnen > .card:first-child { grid-column:1 / -1; }
  .tools button { padding:14px 4px; font-size:13.5px; }
  .tools svg.i { width:26px; height:26px; }
  .colors { gap:4px; }
  .wbg button { flex-basis:40%; min-width:0; padding:13px 4px; font-size:14px; }
  /* Folien: riesige Knöpfe, großes Touchpad */
  .clicker button { min-height:220px; font-size:20px; border-radius:30px; }
  .clicker button svg.i { width:56px; height:56px; }
  .pad { height:min(52vh, 460px); font-size:15px; border-radius:26px; }
  /* Senden: Karten nebeneinander */
  #p-senden.sel { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); column-gap:16px; align-items:start; }
  #p-senden > .card:last-child { grid-column:1 / -1; }
  textarea { min-height:140px; }
  #login { max-width:520px; margin:40px auto; }
}
/* ---- Tablet: Schnellleiste oben rechts (Schwarz/Standbild/Erweitern auf jedem Reiter außer Start) */
.quick { display:none; }
@media (min-width: 740px) {
  .quick:not(.hide) { display:flex; gap:8px; }
  body[data-tab="start"] .quick { display:none; }
  .quick button { padding:10px 14px; font-size:14px; border-radius:16px; background:var(--card); border:1px solid var(--line);
                  box-shadow:0 4px 14px rgba(2,6,23,.12); }
  .quick button.on { background:var(--on); color:#fff; border-color:transparent; }
  .quick svg.i { width:20px; height:20px; }
}
@media (min-width: 740px) and (max-width: 900px) { .quick button span { display:none; } }
/* ---- iPad quer: Live-Bild bleibt links stehen, Steuerung rechts daneben */
@media (min-width: 1060px) and (min-aspect-ratio: 1/1) {
  #p-start.sel { display:grid; grid-template-columns:minmax(0,1.25fr) minmax(0,1fr); gap:18px; align-items:start; }
  .side { position:sticky; top:calc(84px + env(safe-area-inset-top)); display:block; }
  #c-mon2 .grid { grid-template-columns:repeat(3,1fr); }
  #control:not(.hide) { grid-column:2; display:block; }
  #c-nocontrol { grid-column:2; }
  #p-zeichnen.sel { grid-template-columns:minmax(0,1fr) 330px; }
  #p-zeichnen > .card:first-child { grid-column:1; grid-row:1; }
  #p-zeichnen > .card:not(:first-child):not(#c-wbg) { grid-column:2; }
  #p-zeichnen > #c-wbg { grid-column:1; grid-row:2; }
  #c-wbg .wbg button { flex-basis:18%; }
  #p-zeichnen .tools { grid-template-columns:repeat(2,1fr); }
  #p-zeichnen .colors { gap:6px; }
  #c-keys:not(.hide) { display:grid; grid-template-columns:minmax(0,1fr) minmax(0,1.15fr); gap:16px; align-items:stretch; }
  #c-keys > .card { margin:0; display:flex; flex-direction:column; }
  #c-keys .clicker { flex:1; }
  #c-keys .clicker button { min-height:0; height:100%; }
  .pad { height:min(56vh, 520px); }
  #p-senden.sel { grid-template-columns:repeat(3,minmax(0,1fr)); }
  #p-senden > .card:last-child { grid-column:auto; }
}
@media (min-width: 1500px) and (min-aspect-ratio: 1/1) {
  #control:not(.hide) { display:grid; } #p-start.sel { grid-template-columns:minmax(0,1fr) minmax(0,1.2fr); } }
/* ---- Heft-Ansicht (iPad): Whiteboard wie das Fenster am PC – Leiste oben, Seiten links, Tafel groß */
#heft { position:fixed; inset:0; z-index:25; background:var(--bg); display:flex; flex-direction:column;
        padding:env(safe-area-inset-top) env(safe-area-inset-right) env(safe-area-inset-bottom) env(safe-area-inset-left); }
body.heftmode .toast { z-index:31; bottom:calc(40px + env(safe-area-inset-bottom)); left:50%; }
body.heftmode nav, body.heftmode header { display:none; }
.hbar { display:flex; flex-wrap:wrap; gap:6px 8px; align-items:center; padding:8px 10px; flex:none; }
.hbar::-webkit-scrollbar { display:none; }
.hg { display:flex; gap:2px; align-items:center; background:var(--card); border:1px solid var(--line); border-radius:14px;
      padding:3px; flex:none; }
.hg button { padding:5px 8px; min-width:40px; min-height:40px; border-radius:11px; background:transparent; font-size:14px;
             gap:5px; }
.hg button.on { background:var(--on); color:#fff; }
.hg button:disabled { opacity:.35; }
.hg .sw { min-width:28px; width:28px; height:28px; min-height:28px; padding:0; border-radius:50%; margin:0 2px;
          border:3px solid transparent; box-shadow:inset 0 0 0 1px rgba(127,127,127,.45); }
.hg .sw.sel { border-color:var(--text); transform:scale(1.1); }
.hlab { min-width:56px; text-align:center; font-weight:700; font-variant-numeric:tabular-nums; font-size:14px; }
.hsp { flex:1 0 4px; }
.hbody { flex:1; min-height:0; display:flex; gap:10px; padding:0 10px; }
.hpages { width:150px; flex:none; overflow-y:auto; display:flex; flex-direction:column; gap:8px; padding-bottom:10px; }
.hpages button { flex-direction:column; gap:4px; padding:5px; border-radius:12px; font-size:12px; border:2px solid transparent; }
.hpages button.on { border-color:#8b5cf6; }
.hpages img { width:100%; border-radius:7px; background:#fff; aspect-ratio:16/9; object-fit:contain; }
.hcanvas { flex:1; min-width:0; min-height:0; display:flex; align-items:center; justify-content:center; }
.hcanvas .preview { aspect-ratio:auto; }
.hstatus { font-size:12.5px; color:var(--muted); padding:6px 12px; white-space:nowrap; overflow:hidden;
           text-overflow:ellipsis; flex:none; }
@media (orientation:portrait) { .hpages { display:none; } }
.hsheet { position:fixed; inset:0; z-index:30; background:rgba(2,6,23,.25); }
.hcard { position:absolute; width:min(420px, calc(100vw - 16px)); overflow-y:auto; -webkit-overflow-scrolling:touch;
         background:var(--bg); border:1px solid var(--line); border-radius:20px; padding:12px 14px;
         box-shadow:0 20px 60px rgba(0,0,0,.45); }
.hname { display:flex; gap:8px; margin:4px 0 8px; } .hname input { flex:1; min-width:0; font-size:16px; padding:10px 12px;
         border-radius:12px; border:2px solid var(--line); background:var(--card); color:var(--text); }
#heft.max .hpages, #heft.max .hstatus { display:none; }
#heft.max .hbody { padding:6px; }
.hhead { display:flex; align-items:center; justify-content:space-between; margin-bottom:8px; }
.hhead b { font-size:17px; }
.hhead button { min-width:40px; padding:8px; }
.hrow { display:grid; grid-template-columns:1fr auto; align-items:center; gap:10px; padding:8px 0;
        border-bottom:1px solid var(--line); font-size:14.5px; }
.hrow:last-child { border-bottom:0; }
.hrow input[type=range] { width:170px; }
.hrow select { min-width:170px; }
.hrow input[type=checkbox] { width:24px; height:24px; accent-color:#8b5cf6; }
.hlist { display:grid; gap:6px; }
.hlist button { justify-content:flex-start; }
.hlist button.on { background:var(--on); color:#fff; }
.hpapers { display:grid; grid-template-columns:repeat(2,1fr); gap:6px; }
@media (prefers-reduced-motion: reduce) { *, *::before { animation:none !important; transition:none !important; } }
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
  <symbol id="i-gauge" viewBox="0 0 24 24"><path d="M4.5 17a9 9 0 1 1 15 0"/><path d="M12 14l4-4.5"/><circle cx="12" cy="14" r="1.4"/></symbol>
  <symbol id="i-sun" viewBox="0 0 24 24"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></symbol>
  <symbol id="i-board" viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="12" rx="1.5"/><path d="M9 20l1.5-4M15 20l-1.5-4M7 12c2-4 3 1 5-2s3 1 5-1"/></symbol>
  <symbol id="i-wheel" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 3v18M3 12h18M5.6 5.6l12.8 12.8M18.4 5.6L5.6 18.4"/><circle cx="12" cy="12" r="2"/></symbol>
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
  <symbol id="i-lasso" viewBox="0 0 24 24"><ellipse cx="12" cy="9" rx="8" ry="5" stroke-dasharray="3 2.5"/><path d="M7 13c-1 2 0 4 2 4s2 3 0 4"/></symbol>
  <symbol id="i-shape" viewBox="0 0 24 24"><rect x="3" y="3" width="9" height="9" rx="1.5"/><circle cx="16" cy="16" r="5"/></symbol>
  <symbol id="i-redo" viewBox="0 0 24 24"><path d="M15 14l5-5-5-5"/><path d="M20 9H9.5a5.5 5.5 0 0 0 0 11H13"/></symbol>
  <symbol id="i-plus" viewBox="0 0 24 24"><path d="M12 5v14M5 12h14"/></symbol>
  <symbol id="i-minus" viewBox="0 0 24 24"><path d="M5 12h14"/></symbol>
  <symbol id="i-expand" viewBox="0 0 24 24"><path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/></symbol>
</svg>
<header><div class="logo"><svg class="i"><use href="#i-logo"/></svg></div>
  <div class="t"><h1>AluPC</h1><div class="now"><span class="dot" id="dot"></span><span id="now">Verbinde …</span></div></div>
  <div class="quick hide" id="quick">
    <button id="q-schwarz" onclick="cmd('schwarz')"><svg class="i"><use href="#i-black"/></svg><span>Schwarz</span></button>
    <button id="q-standbild" onclick="cmd('standbild')"><svg class="i"><use href="#i-freeze"/></svg><span>Standbild</span></button>
    <button id="q-erweitern" onclick="cmd('erweitern')"><svg class="i"><use href="#i-extend"/></svg><span>Erweitern</span></button>
  </div></header>
<div class="offline" id="offline">Keine Verbindung zu AluPC – gleiches WLAN? Versuche es weiter …</div>

<div class="card" id="login">
  <h2>Code eingeben</h2>
  <p>Den 6-stelligen Code zeigt AluPC unter dem QR-Code an.</p>
  <input type="text" id="code" class="big" inputmode="numeric" maxlength="7" autocomplete="off">
  <button class="primary" style="width:100%;margin-top:10px" onclick="saveCode()">Verbinden</button>
  <p style="margin:16px 0 8px;text-align:center">– oder ohne Code –</p>
  <input type="text" id="devname" maxlength="30" placeholder="Name dieses Handys" autocomplete="off">
  <button style="width:100%;margin-top:10px" onclick="askAccess()">Am PC freigeben lassen</button>
  <p id="waitmsg" style="text-align:center;margin-top:10px"></p>
</div>

<div id="main">
<!-- ============================================================ Start -->
<div class="page sel" id="p-start">
  <div class="side" id="side">
    <div class="card" style="padding:10px" id="c-live">
      <div class="preview" id="preview"><img id="prev" alt=""><div class="laser" id="laser"></div>
        <span class="badge"><i></i>LIVE · <span id="live-hint">Finger = Laser</span></span>
        <button class="corner small" onclick="toggleFull('preview')" aria-label="Vergrößern"><svg class="i"><use href="#i-expand"/></svg></button></div>
    </div>
    <div class="card" id="c-mon2">
      <h2>Bildschirm</h2>
      <div class="grid">
        <button class="tile" id="b-schwarz" onclick="cmd('schwarz')"><svg class="i"><use href="#i-black"/></svg>Schwarz</button>
        <button class="tile" id="b-standbild" onclick="cmd('standbild')"><svg class="i"><use href="#i-freeze"/></svg>Standbild</button>
        <button class="tile" id="b-schoner" onclick="cmd('bildschirmschoner')"><svg class="i"><use href="#i-moon"/></svg>Schoner</button>
        <button class="tile" id="b-spiegeln" onclick="cmd('spiegeln')"><svg class="i"><use href="#i-mirror"/></svg>Spiegeln</button>
        <button class="tile" id="b-erweitern" onclick="cmd('erweitern')"><svg class="i"><use href="#i-extend"/></svg>Erweitern</button>
        <button class="tile" onclick="cmd('zeichnungen_loeschen')"><svg class="i"><use href="#i-erase"/></svg>Radieren</button>
      </div>
    </div>
  </div>
  <div id="control">
  <div class="card ask">
    <h2>Frag AluPC</h2>
    <form class="askrow" onsubmit="ask(); return false">
      <input type="text" id="ask" placeholder="z. B. Licht blau · Timer 5 Minuten" enterkeyhint="send"
             autocomplete="off" autocapitalize="off">
      <button class="primary" type="submit" aria-label="Senden"><svg class="i"><use href="#i-next"/></svg></button>
    </form>
    <div class="reply" id="reply"></div>
    <div class="chips" style="margin:10px 0 0">
      <button onclick="askText('Bildschirm schwarz')">Schwarz</button><button onclick="askText('Licht aus')">Licht aus</button>
      <button onclick="askText('Timer 5 Minuten')">Timer 5 min</button><button onclick="askText('Wie spät ist es?')">Uhrzeit</button>
    </div>
    <div class="hint">🎤 Sprechen: Mikrofon auf der Handy-Tastatur antippen – AluPC versteht ganze Sätze.</div>
  </div>
  <div class="card" id="c-zeigen">
    <h2>Zeigen</h2>
    <div class="grid4">
      <button class="tile" onclick="cmd('kamera')"><svg class="i"><use href="#i-camera"/></svg>Kamera</button>
      <button class="tile" onclick="cmd('airplay')"><svg class="i"><use href="#i-phone"/></svg>iPhone</button>
      <button class="tile" onclick="cmd('qr')"><svg class="i"><use href="#i-qr"/></svg>QR-Code</button>
      <button class="tile" onclick="cmd('timer_zeigen')"><svg class="i"><use href="#i-timer"/></svg>Timer</button>
      <button class="tile" onclick="cmd('system')"><svg class="i"><use href="#i-gauge"/></svg>System</button>
      <button class="tile" onclick="cmd('wetter')"><svg class="i"><use href="#i-sun"/></svg>Wetter</button>
      <button class="tile" onclick="cmd('whiteboard')"><svg class="i"><use href="#i-board"/></svg>Tafel</button>
      <button class="tile" onclick="cmd('gluecksrad')"><svg class="i"><use href="#i-wheel"/></svg>Glücksrad</button>
    </div>
  </div>
  <div class="card hide" id="c-ablauf">
    <h2>Punkte <span id="punkt" style="float:right;text-transform:none;letter-spacing:0"></span></h2>
    <div class="row">
      <button onclick="cmd('ablauf_zurueck')"><svg class="i"><use href="#i-prev"/></svg>Zurück</button>
      <button class="primary" onclick="cmd('ablauf_weiter')">Weiter<svg class="i"><use href="#i-next"/></svg></button>
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
  <div class="card hide" id="c-resume">
    <h2>Video weiterschauen?</h2>
    <p id="resume-text" style="margin:0 0 10px"></p>
    <div class="row">
      <button onclick="cmd('video_von_vorn')">Von vorn</button>
      <button class="primary" onclick="cmd('video_weiterschauen')">Weiterschauen</button>
    </div>
  </div>
  <div class="card" id="c-video">
    <h2>Video <span id="vid-title" style="font-weight:600;opacity:.7"></span></h2>
    <input type="range" id="vidpos" min="0" max="100" step="1" aria-label="Stelle im Video"
           oninput="$('vid-time').textContent = mmss(this.value) + ' / ' + mmss(this.max)"
           onchange="cmd('video_pos:' + this.value)">
    <p id="vid-time" style="margin:2px 0 8px;opacity:.75;text-align:center"></p>
    <div class="row">
      <button onclick="cmd('video_zurueck30')">−30</button>
      <button onclick="cmd('video_zurueck')"><svg class="i"><use href="#i-back10"/></svg>10</button>
      <button class="primary" id="vid-play" aria-label="Pause/Abspielen" onclick="cmd('video_pause')"><svg class="i"><use href="#i-pause"/></svg></button>
      <button onclick="cmd('video_vor')">10<svg class="i"><use href="#i-fwd10"/></svg></button>
      <button onclick="cmd('video_vor30')">+30</button>
    </div>
    <div class="row" id="vid-rates"></div>
    <div class="row">
      <button onclick="cmd('video_neu')">⏮ Von vorn</button>
      <button id="vid-loop" onclick="cmd('video_wiederholen')">🔁 Wiederholen</button>
    </div>
  </div>
  <div class="card hide" id="c-recent">
    <h2>Weiterschauen</h2>
    <div class="scenes" id="recent"></div>
  </div>
  <div class="card" id="c-music">
    <h2>Musik am PC</h2>
    <div class="row">
      <button onclick="cmd('musik_zurueck')"><svg class="i"><use href="#i-prev"/></svg></button>
      <button class="primary" aria-label="Abspielen/Pause" onclick="cmd('musik_pause')"><svg class="i"><use href="#i-play"/></svg><svg class="i"><use href="#i-pause"/></svg></button>
      <button onclick="cmd('musik_weiter')"><svg class="i"><use href="#i-next"/></svg></button>
    </div>
    <div class="row"><button onclick="cmd('musik_zeigen')">Läuft gerade zeigen</button></div>
  </div>
  <div class="card hide" id="c-audio">
    <h2>Ton am PC</h2>
    <p style="margin:4px 0 2px;font-weight:700">🔊 Lautsprecher <span id="a-out-val" style="opacity:.7"></span></p>
    <input type="range" id="a-out" min="0" max="100" step="1" aria-label="Lautsprecher"
           oninput="$('a-out-val').textContent = this.value + ' %'" onchange="cmd('ton_laut:' + this.value)">
    <div class="row">
      <button id="a-out-mute" onclick="cmd('ton_stumm:' + (this.classList.contains('on') ? 0 : 1))">🔇 Stumm</button>
      <select id="a-out-dev" aria-label="Lautsprecher wählen" onchange="cmd('ton_geraet:' + this.value)"></select>
    </div>
    <p style="margin:10px 0 2px;font-weight:700">🎙 Mikrofon <span id="a-in-val" style="opacity:.7"></span></p>
    <input type="range" id="a-in" min="0" max="100" step="1" aria-label="Mikrofon"
           oninput="$('a-in-val').textContent = this.value + ' %'" onchange="cmd('mic_laut:' + this.value)">
    <div class="row">
      <button id="a-in-mute" onclick="cmd('mic_stumm:' + (this.classList.contains('on') ? 0 : 1))">🎙 Stumm</button>
      <select id="a-in-dev" aria-label="Mikrofon wählen" onchange="cmd('mic_geraet:' + this.value)"></select>
    </div>
  </div>
  <div class="card" id="c-pc">
    <h2>PC <span id="pcvol-val" style="font-weight:600;opacity:.7"></span></h2>
    <input type="range" id="pcvol" min="0" max="100" step="5" aria-label="Lautstärke am PC"
           oninput="$('pcvol-val').textContent = '· ' + this.value + ' %'" onchange="cmd('pc_lautstaerke:' + this.value)">
    <div class="row">
      <button onclick="cmd('pc_leiser')">🔉 Leiser</button>
      <button onclick="cmd('pc_lauter')">🔊 Lauter</button>
      <button onclick="cmd('pc_stumm_an')">🔇 Stumm</button>
    </div>
    <div class="row">
      <button onclick="cmd('pc_desktop')">Desktop</button>
      <button onclick="cmd('pc_fenster_wechseln')">Fenster ⇄</button>
      <button onclick="cmd('pc_screenshot')">📸 Foto</button>
    </div>
    <div class="row">
      <button onclick="cmd('pc_minimieren')">▁ Klein</button>
      <button onclick="cmd('pc_maximieren')">▢ Groß</button>
      <button onclick="if (confirm('Aktives Fenster am PC schließen?')) cmd('pc_fenster_zu')">✕ Schließen</button>
      <button onclick="cmd('pc_sperren')">🔒 Sperren</button>
    </div>
    <div class="row" style="margin-top:6px">
      <select id="apps" onfocus="loadApps()" aria-label="Programm"><option value="">Programm öffnen …</option></select>
      <button style="flex:0 0 auto" onclick="openApp()">Öffnen</button>
    </div>
  </div>
  <div class="card" id="c-vol">
    <h2>Lautstärke <span id="vol-val"></span></h2>
    <input type="range" id="vol" min="0" max="100" step="5" oninput="$('vol-val').textContent = this.value + ' %'"
           onchange="cmd('lautstaerke:' + this.value)">
  </div>
  <div class="card" id="c-timer">
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
      <button class="corner small" onclick="heftOn ? heftMax() : toggleFull('dpreview')" aria-label="Vergrößern"><svg class="i"><use href="#i-expand"/></svg></button></div>
  </div>
  <div class="card">
    <div class="tools">
      <button id="t-laser" onclick="pick('laser')"><svg class="i"><use href="#i-dot"/></svg>Laser</button>
      <button id="t-stift" class="on" onclick="pick('stift')"><svg class="i"><use href="#i-pen"/></svg>Stift</button>
      <button id="t-marker" onclick="pick('marker')"><svg class="i"><use href="#i-marker"/></svg>Marker</button>
      <button id="t-radierer" onclick="pick('radierer')"><svg class="i"><use href="#i-erase"/></svg>Radierer</button>
      <button id="t-lasso" class="bonly" onclick="pick('lasso')"><svg class="i"><use href="#i-lasso"/></svg>Lasso</button>
      <button id="t-form" class="bonly" onclick="pickShape()"><svg class="i"><use href="#i-shape"/></svg><span id="form-name">Linie</span></button>
      <button id="t-text" class="bonly" onclick="pick('text')"><svg class="i"><use href="#i-text"/></svg>Text</button>
    </div>
    <div class="colors" id="colors"></div>
    <div class="chips bonly" id="widths" style="margin:12px 0 0">
      <button data-w="0.6" onclick="setWidth(0.6)">• fein</button><button data-w="1" onclick="setWidth(1)">● mittel</button>
      <button data-w="2.2" onclick="setWidth(2.2)">⬤ dick</button>
    </div>
    <div class="row" id="draw-actions" style="margin-top:12px">
      <button onclick="undoAny()" id="b-undo" aria-label="Rückgängig" title="Rückgängig"><svg class="i"><use href="#i-undo"/></svg><span class="lbl">Rückgängig</span></button>
      <button onclick="redoAny()" id="b-redo" class="bonly" aria-label="Wiederholen" title="Wiederholen"><svg class="i"><use href="#i-redo"/></svg></button>
      <button onclick="clearAny()"><svg class="i"><use href="#i-trash"/></svg><span id="clear-label">Alles löschen</span></button>
    </div>
    <button class="bonly hide" id="b-del" style="width:100%;margin-top:8px" onclick="boardOp('auswahl_loeschen')">
      <svg class="i"><use href="#i-trash"/></svg>Auswahl löschen</button>
    <button class="bonly primary" id="b-heft" style="width:100%;margin-top:10px" onclick="heft(true, true)">
      <svg class="i"><use href="#i-expand"/></svg>Heft-Ansicht – wie am PC</button>
    <div class="hint" id="draw-hint">Mit dem Finger auf das Bild zeichnen – erscheint sofort auf dem Bildschirm.</div>
  </div>
  <div class="card bonly-card" id="c-board">
    <h2>Tafel <span id="b-name" style="text-transform:none;letter-spacing:0;font-weight:600"></span></h2>
    <div class="row">
      <button onclick="boardOp('zoom_out')" aria-label="Herauszoomen"><svg class="i"><use href="#i-minus"/></svg></button>
      <button onclick="boardOp('fit')" id="b-zoom" aria-label="Ganze Seite">100 %</button>
      <button onclick="boardOp('zoom_in')" aria-label="Hineinzoomen"><svg class="i"><use href="#i-plus"/></svg></button>
    </div>
    <div class="row">
      <button onclick="boardOp('seite_zurueck')" aria-label="Vorige Seite"><svg class="i"><use href="#i-prev"/></svg></button>
      <button id="b-page" disabled>1 / 1</button>
      <button onclick="boardOp('seite_vor')" aria-label="Nächste Seite"><svg class="i"><use href="#i-next"/></svg></button>
      <button onclick="boardOp('seite_neu')"><svg class="i"><use href="#i-plus"/></svg>Seite</button>
    </div>
    <div class="hint" style="margin:10px 0 6px">Gäste im AluPC-WLAN (Codes unten rechts auf der Tafel):</div>
    <div class="chips" id="guests">
      <button data-g="aus" onclick="cmd('tafel_gaeste_aus')">Aus</button>
      <button data-g="alle" onclick="cmd('tafel_gaeste_alle')">Alle schreiben</button>
      <button data-g="frage" onclick="cmd('tafel_gaeste_frage')">Nur mit Erlaubnis</button>
    </div>
    <label class="live-row"><input type="checkbox" id="pencil" onchange="setPencil(this.checked)">
      <span>✏️ <b style="color:inherit">Nur Stift zeichnet</b> – Finger verschieben (Handballen-Schutz)</span></label>
    <div class="hint">Zwei Finger: zoomen und verschieben. Apple Pencil: fester drücken = dicker. Lasso: einkreisen,
      dann ziehen zum Verschieben. Form: nochmal tippen wechselt Linie → Pfeil → Rechteck → Kreis.</div>
  </div>
  <div class="card" id="c-wbg">
    <h2>Whiteboard</h2>
    <div class="wbg">
      <button onclick="cmd('whiteboard:weiss')">Weiß</button>
      <button onclick="cmd('whiteboard:kariert')">Kariert</button>
      <button onclick="cmd('whiteboard:liniert')">Liniert</button>
      <button onclick="cmd('whiteboard:punkte')">Punkteraster</button>
      <button onclick="cmd('whiteboard:millimeter')">Millimeter</button>
      <button onclick="cmd('whiteboard:koordinaten')">Koordinaten</button>
      <button onclick="cmd('whiteboard:noten')">Notenlinien</button>
      <button onclick="cmd('whiteboard:tafel')">Tafel (grün)</button>
      <button onclick="cmd('whiteboard:schwarz')">Tafel (schwarz)</button>
      <button onclick="cmd('whiteboard:blaupause')">Blaupause</button>
    </div>
    <div class="hint">Tippen zeigt das Whiteboard mit diesem Hintergrund – dann oben draufzeichnen.</div>
  </div>
</div>

<!-- ============================================================ Heft-Ansicht (iPad): wie das Whiteboard-Fenster am PC -->
<div id="heft" class="hide" aria-label="Whiteboard wie am PC">
  <div class="hbar" id="hbar">
    <div class="hg"><button id="h-board" onclick="hMenu('tafel', this)"><svg class="i"><use href="#i-slides"/></svg>Tafel ▾</button></div>
    <div class="hg" id="h-tools">
      <button data-t="stift" title="Stift"><svg class="i"><use href="#i-pen"/></svg></button>
      <button data-t="marker" title="Marker"><svg class="i"><use href="#i-marker"/></svg></button>
      <button data-t="radierer" title="Radierer"><svg class="i"><use href="#i-erase"/></svg></button>
      <button data-t="lasso" title="Lasso"><svg class="i"><use href="#i-lasso"/></svg></button>
      <button data-t="form" title="Form"><svg class="i"><use href="#i-shape"/></svg><span id="h-shape">Linie</span></button>
      <button data-t="text" title="Text"><svg class="i"><use href="#i-text"/></svg></button>
      <button data-t="laser" title="Laser"><svg class="i"><use href="#i-dot"/></svg></button>
    </div>
    <div class="hg" id="h-colors"></div>
    <div class="hg" id="h-widths"><button data-w="0.6" title="fein">•</button><button data-w="1" title="mittel">●</button>
      <button data-w="2.2" title="dick">⬤</button></div>
    <div class="hg"><button id="h-undo" onclick="undoAny()" title="Rückgängig"><svg class="i"><use href="#i-undo"/></svg></button>
      <button id="h-redo" onclick="redoAny()" title="Wiederholen"><svg class="i"><use href="#i-redo"/></svg></button></div>
    <span class="hsp"></span>
    <div class="hg"><button onclick="boardOp('zoom_out')" title="Herauszoomen"><svg class="i"><use href="#i-minus"/></svg></button>
      <button id="h-zoom" onclick="boardOp('fit')" title="Ganze Seite">100 %</button>
      <button onclick="boardOp('zoom_in')" title="Hineinzoomen"><svg class="i"><use href="#i-plus"/></svg></button></div>
    <div class="hg"><button onclick="boardOp('seite_zurueck')" title="Vorige Seite"><svg class="i"><use href="#i-prev"/></svg></button>
      <span id="h-page" class="hlab">1 / 1</span>
      <button onclick="boardOp('seite_vor')" title="Nächste Seite"><svg class="i"><use href="#i-next"/></svg></button>
      <button onclick="boardOp('seite_neu')" title="Neue Seite"><svg class="i"><use href="#i-plus"/></svg></button>
      <button id="h-paper" onclick="hMenu('papier', this)" title="Papier dieser Seite">Papier ▾</button></div>
    <div class="hg"><button onclick="hMenu('einst', this)" title="Einstellungen">⚙</button>
      <button onclick="heft(false, true)" title="Schließen">✕</button></div>
  </div>
  <div class="hbody"><div class="hpages" id="hpages"></div><div class="hcanvas" id="hcanvas"></div></div>
  <div class="hstatus" id="hstatus"></div>
  <div class="hsheet hide" id="hsheet" onclick="if (event.target === this) hMenu()">
    <div class="hcard"><div class="hhead"><b id="hsheet-title"></b><button onclick="hMenu()">✕</button></div>
      <div id="hsheet-body"></div></div></div>
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
  <div class="card hide empty" id="c-nokeys">
    <svg class="i big"><use href="#i-slides"/></svg>
    <h3>Folien weiterschalten geht hier nicht</h3>
    <div class="hint">Tasten und Maus per Handy erlaubt Wayland nicht – am PC beim Anmelden die Sitzung
      „Plasma (X11)“ wählen. Laserpointer und Zeichnen gehen trotzdem:</div>
    <div class="row" style="margin-top:10px">
      <button onclick="tab('start')"><svg class="i"><use href="#i-dot"/></svg>Laserpointer</button>
      <button class="primary" onclick="tab('zeichnen')"><svg class="i"><use href="#i-pen"/></svg>Zeichnen</button>
    </div>
  </div>
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
    <div class="hint" id="upinfo">Wird sofort auf dem Bildschirm gezeigt.</div>
  </div>
  <div class="card">
    <h2>Link</h2>
    <input type="url" id="url" placeholder="https://… (z. B. YouTube)" autocomplete="off">
    <button class="primary" style="width:100%;margin-top:8px" onclick="sendLink()"><svg class="i"><use href="#i-link"/></svg>Auf dem Bildschirm öffnen</button>
    <div class="hint">YouTube: „Teilen → Link kopieren“ und hier einfügen – läuft im Vollbild.</div>
  </div>
  <div class="card">
    <h2>Text</h2>
    <textarea id="text" placeholder="Text für den Bildschirm" oninput="liveInput()"></textarea>
    <label class="live-row"><input type="checkbox" id="live" onchange="liveToggle()"> <b>Live</b> – sofort auf dem Bildschirm</label>
    <button id="text-btn" style="width:100%;margin-top:8px" onclick="sendText()"><svg class="i"><use href="#i-text"/></svg>Anzeigen</button>
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
// iOS ignoriert user-scalable=no: Seite darf nicht per Zwei-Finger- oder Doppeltipp-Zoom „wegrutschen“
for (const ev of ['gesturestart', 'gesturechange', 'gestureend'])
  document.addEventListener(ev, e => e.preventDefault(), {passive: false});
document.addEventListener('touchmove', e => { if (e.touches.length > 1) e.preventDefault(); }, {passive: false});
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

function movePill() {
  const nav = $("nav"), sel = nav && nav.querySelector("button.sel");
  let pill = $("nav-pill");
  if (!nav || !sel) return;
  if (!pill) { pill = document.createElement("span"); pill.id = "nav-pill"; nav.prepend(pill); }
  pill.style.left = sel.offsetLeft + "px"; pill.style.width = sel.offsetWidth + "px";
  pill.style.top = sel.offsetTop + "px"; pill.style.height = sel.offsetHeight + "px";  // iPad: Leiste links
}
window.addEventListener("resize", movePill);
// Tipp-Welle auf allen Knöpfen
document.addEventListener("pointerdown", e => {
  const b = e.target.closest("button, .btn");
  if (!b || b.closest("nav") || b.closest(".colors")) return;
  const r = b.getBoundingClientRect(), size = Math.max(r.width, r.height) * 2.2;
  const s = document.createElement("span");
  s.className = "ripple"; s.style.width = s.style.height = size + "px";
  s.style.left = (e.clientX - r.left - size / 2) + "px"; s.style.top = (e.clientY - r.top - size / 2) + "px";
  b.appendChild(s); setTimeout(() => s.remove(), 600);
}, { passive: true });
function tab(name) {
  const btn = document.querySelector('nav button[data-p="' + name + '"]');
  if (!btn || btn.classList.contains("hide")) name = "start";
  current = name; store.set("alucast-tab", name); document.body.dataset.tab = name;
  for (const b of document.querySelectorAll("nav button")) b.classList.toggle("sel", b.dataset.p === name);
  movePill();
  for (const p of document.querySelectorAll(".page")) p.classList.toggle("sel", p.id === "p-" + name);
  if (fullEl) toggleFull();
  window.scrollTo(0, 0); loadPreview(); sizeInk();
  if (typeof heft === "function") { if (heftOn && name !== "zeichnen") heft(false); else if (heftWanted()) heft(true); }
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
async function askAccess() {  // ohne Code: am PC erscheint „Erlauben / Ablehnen“
  const name = $("devname").value.trim() || "Handy"; store.set("alucast-name", name);
  const msg = $("waitmsg");
  try {
    const r = await fetch("/api/freigabe", {method: "POST", headers: {"Content-Type": "application/json"},
                                           body: JSON.stringify({name})});
    const d = await r.json();
    if (!r.ok) { msg.textContent = d.error || "Geht gerade nicht"; return; }
    msg.textContent = "Warte auf Freigabe am PC …";
    const poll = async () => {
      const q = await (await fetch("/api/freigabe?id=" + encodeURIComponent(d.id))).json();
      if (q.state === "ok") { code = q.key; store.set("alucast-code", code); msg.textContent = ""; refresh(); }
      else if (q.state === "no") msg.textContent = "Am PC abgelehnt.";
      else if (q.state === "wait") setTimeout(poll, 1500);
      else msg.textContent = "Anfrage abgelaufen – bitte nochmal.";
    };
    poll();
  } catch (e) { msg.textContent = "Keine Verbindung zu AluPC"; }
}
if ($("devname")) $("devname").value = store.get("alucast-name");
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
function mmss(t) { t = Math.max(0, Math.floor(+t || 0)); const h = Math.floor(t / 3600), m = Math.floor(t % 3600 / 60);
  return (h ? h + ":" + String(m).padStart(2, "0") : m) + ":" + String(t % 60).padStart(2, "0"); }
let recentKey = "";
let appsLoaded = false;
async function loadApps() {  // installierte Programme am PC (nur aus dieser Liste lässt sich etwas öffnen)
  if (appsLoaded) return; appsLoaded = true;
  try {
    const r = await fetch("/api/apps", { headers: { "X-AluPC-Code": code } });
    const d = await r.json();
    for (const n of (d.apps || [])) { const o = document.createElement("option"); o.value = o.textContent = n; $("apps").append(o); }
  } catch (e) { appsLoaded = false; }
}
function openApp() { const n = $("apps").value; if (n) cmd("pc_programm:" + n); else { loadApps(); $("apps").focus(); } }
let replyId = -1, waitReply = false;
function askText(t) { $("ask").value = t; ask(); }
async function ask() {
  const t = $("ask").value.trim(); if (!t) return;
  buzz(); waitReply = true;
  const r = $("reply"); r.className = "reply show"; r.textContent = "…";
  try { await api("/api/ask", JSON.stringify({ text: t }), "application/json"); $("ask").value = ""; $("ask").blur(); setTimeout(refresh, 250); }
  catch (e) { r.className = "reply show bad"; r.textContent = e.message; waitReply = false; }
}
function key(k) { buzz(); post("/api/cmd", { cmd: "taste:" + k }); }
function sendLink() {
  const u = $("url").value.trim(); if (!u) return;
  post("/api/link", { url: u }, "Wird geöffnet …"); $("url").value = "";
}
function sendText() {
  const t = $("text").value.trim(); if (!t) return;
  post("/api/text", { text: t }, "Angezeigt");
}
// Live: beim Tippen kurz gebündelt senden (höchstens ~8× pro Sekunde), immer der neueste Stand
let liveTimer = null, liveBusy = false, livePending = false;
function liveToggle() {
  const on = $("live").checked;
  $("text-btn").style.display = on ? "none" : "";
  try { localStorage.setItem("alupc-live", on ? "1" : ""); } catch (e) {}
  if (on) liveSend();
}
function liveInput() {
  if (!$("live").checked) return;
  clearTimeout(liveTimer); liveTimer = setTimeout(liveSend, 120);
}
async function liveSend() {
  if (liveBusy) { livePending = true; return; }
  liveBusy = true;
  try { await api("/api/text", JSON.stringify({ text: $("text").value, live: true }), "application/json"); }
  catch (e) { toast(e.message, true); }
  liveBusy = false;
  if (livePending) { livePending = false; liveSend(); }
}
try { if (localStorage.getItem("alupc-live")) { $("live").checked = true; $("text-btn").style.display = "none"; } } catch (e) {}

let scenesKey = "", failures = 0;
async function refresh() {
  requestAnimationFrame(movePill);
  if (!code) { showLogin(true); return; }
  try {
    const s = await api("/api/status" + (heftOn ? "?heft=1" : ""));
    failures = 0; $("offline").classList.remove("show");
    showLogin(false);
    $("dot").classList.add("on");
    $("now").textContent = s.now;
    allow = Object.assign({ senden: true, steuern: true, live: true, laser: true }, s.allow || {});
    for (const [p, on] of [["zeichnen", allow.laser], ["folien", allow.steuern], ["senden", allow.senden]])
      document.querySelector('nav button[data-p="' + p + '"]').classList.toggle("hide", !on);
    if (document.querySelector('nav button[data-p="' + current + '"]').classList.contains("hide")) tab("start");
    $("control").classList.toggle("hide", !allow.steuern);
    $("c-mon2").classList.toggle("hide", !allow.steuern);
    $("c-nocontrol").classList.toggle("hide", allow.steuern);
    $("c-live").classList.toggle("hide", !allow.live);
    $("live-hint").textContent = allow.laser ? "Finger = Laser" : "Live-Bild";
    const f = s.flags || {};
    for (const [id, on] of [["b-schwarz", f.schwarz], ["b-standbild", f.standbild], ["b-spiegeln", f.spiegeln],
                            ["b-erweitern", f.erweitern], ["b-schoner", f.schoner], ["q-schwarz", f.schwarz],
                            ["q-standbild", f.standbild], ["q-erweitern", f.erweitern]]) $(id).classList.toggle("on", !!on);
    $("quick").classList.toggle("hide", !allow.steuern);
    $("c-video").classList.toggle("hide", !s.video);
    const v = s.vid;
    if (v) {
      $("vid-title").textContent = "· " + v.title;
      if (document.activeElement !== $("vidpos")) { $("vidpos").max = Math.max(1, v.dur); $("vidpos").value = v.pos;
        $("vid-time").textContent = mmss(v.pos) + " / " + mmss(v.dur); }
      $("vid-play").querySelector("use").setAttribute("href", v.playing ? "#i-pause" : "#i-play");
      $("vid-loop").classList.toggle("on", !!v.loop);
      const rates = $("vid-rates");
      if (!rates.childElementCount) for (const r of [0.5, 0.75, 1, 1.25, 1.5, 2]) {
        const b = document.createElement("button"); b.textContent = String(r).replace(".", ",") + "×"; b.dataset.r = r;
        b.onclick = () => cmd("video_tempo:" + r); rates.appendChild(b); }
      for (const b of rates.children) b.classList.toggle("on", +b.dataset.r === v.rate);
    }
    const a = s.audio;
    $("c-audio").classList.toggle("hide", !a);
    if (a) for (const k of ["out", "in"]) {
      const d = a[k] || {}, r = $("a-" + k), sel = $("a-" + k + "-dev");
      if (document.activeElement !== r && d.vol != null) { r.value = d.vol; $("a-" + k + "-val").textContent = d.vol + " %"; }
      $("a-" + k + "-mute").classList.toggle("on", !!d.muted);
      const devs = d.devices || [], dk = JSON.stringify(devs);
      if (sel.dataset.k !== dk && document.activeElement !== sel) {
        sel.dataset.k = dk; sel.innerHTML = "";
        devs.forEach((dv, i) => { const o = document.createElement("option"); o.value = i; o.textContent = dv.name;
          if (dv.default) o.selected = true; sel.appendChild(o); });
        sel.classList.toggle("hide", devs.length < 2);
      }
    }
    const rec = s.recent || [];
    $("c-recent").classList.toggle("hide", !rec.length);
    const rk = JSON.stringify(rec);
    if (rk !== recentKey) {
      recentKey = rk; const box = $("recent"); box.innerHTML = "";
      rec.forEach((r, i) => { const b = document.createElement("button");
        b.textContent = "▶ " + r.title + " · " + mmss(r.pos) + (r.dur ? " / " + mmss(r.dur) : "");
        b.onclick = () => { buzz(); post("/api/cmd", { cmd: "video_fortsetzen:" + i }, r.title); }; box.appendChild(b); });
    }
    $("c-resume").classList.toggle("hide", !s.resume);
    if (s.resume) { const t = s.resume.pos; $("resume-text").textContent = s.resume.title + " – geschaut bis " +
      Math.floor(t / 60) + ":" + String(t % 60).padStart(2, "0"); }
    $("c-ablauf").classList.toggle("hide", !s.ablauf);
    $("punkt").textContent = s.punkt || "";
    $("c-vol").classList.toggle("hide", !s.sound);
    if (document.activeElement !== $("vol")) { $("vol").value = s.volume; $("vol-val").textContent = s.volume + " %"; }
    $("timer").textContent = s.timer || "–";
    if (s.reply) {  // Antwort auf „Frag AluPC“ (nur neue Antworten zeigen)
      if (replyId < 0) replyId = s.reply.id;
      else if (s.reply.id !== replyId) {
        replyId = s.reply.id;
        if (waitReply && s.reply.text) { const r = $("reply"); r.className = "reply show" +
          (/nicht verstanden|nur direkt|nicht geklappt|ging nicht/i.test(s.reply.text) ? " bad" : "");
          r.textContent = s.reply.text; waitReply = false; }
      }
    }
    showBoard(s.board || null);
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
let prevUrl = null, prevBusy = false, fastTimer = 0;
function fastPreview() { return current === "zeichnen"; }  // beim Zeichnen: Live-Bild sofort (WebSocket) bzw. ~9×/s
async function showFrame(blob, seq) {
  if (viewHold && seq < viewHold) return;  // während Zoom-Geste: altes Bild behalten
  const url = URL.createObjectURL(blob);
  $("prev").src = url;
  const im = $("dprev"); im.src = url;
  try { await im.decode(); } catch (e) {}
  const ar = im.naturalWidth / im.naturalHeight;  // Seitenverhältnis vom Bildschirm übernehmen
  if (ar > 0.2 && ar < 5 && Math.abs(ar - (window._ar || 0)) > 0.01) {
    window._ar = ar; document.documentElement.style.setProperty("--ar", ar);
    for (const pv of [$("preview"), $("dpreview")]) pv.style.aspectRatio = String(ar);
    sizeInk(); sizeHeft();
  }
  frameArrived(seq);
  if (prevUrl) URL.revokeObjectURL(prevUrl);
  prevUrl = url;
}
async function loadPreview() {
  if (!code || prevBusy || !allow.live || current === "senden" || current === "folien" || document.hidden) return;
  if (liveOpen()) return;  // Bilder kommen schon über die Live-Verbindung
  if (fastPreview() && allow.live) liveConnect();
  prevBusy = true;
  const fast = fastPreview(), t0 = Date.now();
  try {
    const r = await fetch("/api/preview" + (fast ? "?fast=1" : ""), { headers: { "X-AluPC-Code": code } });
    if (r.ok && r.status === 200) await showFrame(await r.blob(), +(r.headers.get("X-AluPC-Frame") || 0));
  } catch (e) {}
  prevBusy = false;
  if (fast && !fastTimer && !liveOpen())
    fastTimer = setTimeout(() => { fastTimer = 0; loadPreview(); }, Math.max(30, 110 - (Date.now() - t0)));
}
// ---- Live-Verbindung (WebSocket): jedes neue Bild kommt sofort, Striche/Zoom/Laser gehen ohne neue Anfragen raus
let live = null, liveTries = 0, liveAcks = new Map(), liveId = 0;
function liveOpen() { return live && live.readyState === 1; }
function liveConnect() {
  if (live || !code || !window.WebSocket || liveTries > 5) return;
  try { live = new WebSocket((location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/ws/live?c=" + encodeURIComponent(code)); }
  catch (e) { live = null; liveTries++; return; }
  live.binaryType = "blob";
  live.onopen = () => { liveTries = 0; };
  live.onmessage = ev => {
    if (typeof ev.data === "string") {
      try { const m = JSON.parse(ev.data); const cb = liveAcks.get(m.ack); if (cb) { liveAcks.delete(m.ack); cb(m.seq); } } catch (e) {}
      return;
    }
    ev.data.slice(0, 4).arrayBuffer().then(b => showFrame(ev.data.slice(4, ev.data.size, "image/jpeg"),
                                                         new DataView(b).getUint32(0)));
  };
  live.onclose = () => {
    live = null; liveTries++;
    for (const cb of liveAcks.values()) cb(null); liveAcks.clear();
    if (fastPreview()) setTimeout(() => { liveConnect(); loadPreview(); }, 800);
  };
}
setInterval(() => { if (liveOpen()) { if (!fastPreview()) live.close(); else live.send('{"ping":1}'); } }, 4000);
const LIVE_P = { "/api/draw": "draw", "/api/board": "board", "/api/laser": "laser" };
function liveSend(path, body, wantAck) {  // null = geht nicht (dann HTTP)
  if (!liveOpen() || !LIVE_P[path]) return null;
  if (!wantAck) { live.send('{"p":"' + LIVE_P[path] + '","b":' + body + '}'); return Promise.resolve({ ok: true, json: async () => ({}) }); }
  const id = ++liveId;
  return new Promise(res => {
    const t = setTimeout(() => { liveAcks.delete(id); res(null); }, 3000);
    liveAcks.set(id, seq => { clearTimeout(t); res(seq === null ? null : { ok: true, json: async () => ({ seq }) }); });
    live.send('{"p":"' + LIVE_P[path] + '","b":' + body + ',"id":' + id + '}');
  });
}

// ---- Senden mit „immer nur das Neueste“ (Laser, Zeichnen, Maus): nie einen Rückstau aufbauen
function sender(path, merge) {
  // Alles läuft nacheinander über eine Kette: „Anfang“, „weiter“, „Ende“ kommen am PC garantiert in dieser
  // Reihenfolge an (sonst könnte „Ende“ vor „Anfang“ eintreffen und ein Strich bliebe hängen).
  let pending = null, busy = false, chain = Promise.resolve();
  const post = (body, ack) => liveSend(path, body, ack) || fetch(path, { method: "POST", headers: { "X-AluPC-Code": code,
    "Content-Type": "application/json" }, body }).catch(() => {});
  function pump() {
    if (busy || !pending) return;
    busy = true; const body = JSON.stringify(pending); pending = null;
    chain = chain.then(() => post(body)).then(() => new Promise(r => setTimeout(r, liveOpen() ? 0 : 15)))
                 .then(() => { busy = false; pump(); });
  }
  return function (obj, force, done) {
    if (force) {  // Anfang/Ende eines Strichs, Klicks: nie verschmelzen oder verlieren
      if (pending) { const p = JSON.stringify(pending); pending = null; chain = chain.then(() => post(p)); }
      const body = JSON.stringify(obj);
      chain = chain.then(() => post(body, !!done)).then(r => {  // done(seq): Nummer des Live-Bilds, als es ankam
        if (done) r && r.ok ? r.json().then(j => done(j.seq)).catch(() => done(null)) : done(null); });
      return;
    }
    pending = merge && pending ? merge(pending, obj) : obj;
    pump();
  };
}
const sendLaser = sender("/api/laser");
const sendDraw = sender("/api/draw");
const sendMouse = sender("/api/mouse", (a, b) => ({ dx: (a.dx || 0) + (b.dx || 0), dy: (a.dy || 0) + (b.dy || 0) }));
function mouse(obj) { buzz(); sendMouse(obj, true); }

function capture(el, e) { try { el.setPointerCapture(e.pointerId); } catch (err) {} }
function norm(pv, e) {
  const box = pv.getBoundingClientRect();
  return { x: Math.min(1, Math.max(0, (e.clientX - box.left) / box.width)),
           y: Math.min(1, Math.max(0, (e.clientY - box.top) / box.height)) };
}
function laserOn(pv, dot) {
  function point(e) {
    if (!allow.laser || pinching) return;
    const p = norm(pv, e);
    dot.style.display = "block"; dot.style.left = (p.x * 100) + "%"; dot.style.top = (p.y * 100) + "%";
    sendLaser(p);
  }
  function release() { dot.style.display = "none"; if (allow.laser) sendLaser({ up: true }, true); }
  pv.addEventListener("pointerdown", e => { if (e.target.closest("button")) return; capture(pv, e); point(e); });
  pv.addEventListener("pointermove", e => { if (e.buttons || e.pointerType === "touch") point(e); });
  pv.addEventListener("pointerup", release);
  pv.addEventListener("pointercancel", release);
}
laserOn($("preview"), $("laser"));

// ---- Zeichnen: Strich sofort auf dem Handy sehen, gleichzeitig auf dem Bildschirm
const COLORS = ["#ef4444", "#f59e0b", "#22c55e", "#3b82f6", "#a855f7", "#ffffff", "#111827"];
let tool = store.get("alucast-tool") || "stift", color = store.get("alucast-color") || COLORS[0];
const NAMES = { laser: "Laser", stift: "Stift", marker: "Marker", radierer: "Radierer", lasso: "Lasso", form: "Form",
                text: "Text" };
const SHAPES = [["line", "Linie"], ["arrow", "Pfeil"], ["rect", "Rechteck"], ["ellipse", "Kreis"]];
let shape = store.get("alucast-shape") || "line", widthF = +store.get("alucast-width") || 1;
let board = null, paletteKey = "", pencilOnly = store.get("alucast-pencil") === "1";
function buildColors(list) {
  const key = list.join(","); if (key === paletteKey) return; paletteKey = key;
  $("colors").innerHTML = "";
  for (const c of list) {
    const b = document.createElement("button"); b.style.background = c; b.dataset.c = c;
    b.onclick = () => { color = c; store.set("alucast-color", c);
      if (["laser", "radierer", "lasso"].includes(tool)) pick("stift"); showTools(); };
    $("colors").appendChild(b);
  }
  showTools();
}
buildColors(COLORS);
function pick(t) { if (!board && !["laser", "stift", "marker", "radierer"].includes(t)) t = "stift";
  tool = t; store.set("alucast-tool", t); showTools(); buzz(); }
function pickShape() {  // nochmal tippen: nächste Form
  if (tool === "form") { const i = SHAPES.findIndex(s => s[0] === shape); shape = SHAPES[(i + 1) % SHAPES.length][0];
    store.set("alucast-shape", shape); }
  pick("form");
}
function setWidth(f) { widthF = f; store.set("alucast-width", String(f)); showTools(); buzz(); }
function setPencil(on) { pencilOnly = on; store.set("alucast-pencil", on ? "1" : "0"); }
function showTools() {
  for (const t of Object.keys(NAMES)) $("t-" + t).classList.toggle("on", t === tool);
  for (const b of $("colors").children) b.classList.toggle("sel", b.dataset.c === color && !["laser", "radierer", "lasso"].includes(tool));
  const sname = (SHAPES.find(s => s[0] === shape) || SHAPES[0])[1];
  $("form-name").textContent = sname;
  $("tool-name").textContent = tool === "form" ? sname : NAMES[tool];
  for (const b of $("widths").children) b.classList.toggle("on", +b.dataset.w === widthF);
  if (typeof hRender === "function" && heftOn) hRender();
}
showTools();
function boardTool() {
  return { stift: "pen", marker: "marker", radierer: "eraser", laser: "laser", lasso: "lasso", form: shape }[tool] || "pen";
}
function boardWidth() {
  if (!board) return undefined;
  return (tool === "marker" ? board.marker_width : board.width) * widthF;
}
function viewAffine(o) {  // Ansicht-Nachricht → x' = s·x + t (je Achse, 0…1 vom Bildschirm)
  const z = o.zoom || 1, ax = o.ax === undefined ? .5 : o.ax, ay = o.ay === undefined ? .5 : o.ay;
  return { s: z, tx: (1 - z) * ax + (o.dx || 0), ty: (1 - z) * ay + (o.dy || 0) };
}
function mergeView(a, b) {  // erst a, dann b – genau zusammengefasst
  const A = viewAffine(a), B = viewAffine(b), z = A.s * B.s;
  return { op: "view", zoom: z, ax: .5, ay: .5, dx: B.s * A.tx + B.tx - (1 - z) * .5, dy: B.s * A.ty + B.ty - (1 - z) * .5 };
}
const sendBoard = sender("/api/board", (a, b) => (a.op === "view" && b.op === "view") ? mergeView(a, b) : b);
function boardOp(op, arg) { buzz(); sendBoard({ op, arg: arg || "" }, true); setTimeout(refresh, 250); setTimeout(refresh, 1200); }
function undoAny() { if (board) boardOp("rueckgaengig"); else cmd("zeichnung_zurueck"); }
function redoAny() { if (board) boardOp("wiederholen"); }
function clearAny() {
  if (board) { if (confirm("Diese Seite der Tafel leeren?")) boardOp("leeren"); }
  else cmd("zeichnungen_loeschen");
}
function showBoard(b) {
  const was = !!board; board = b;
  document.body.classList.toggle("board", !!b);
  $("clear-label").textContent = b ? "Seite leeren" : "Alles löschen";
  $("draw-hint").textContent = b ? "Auf die Tafel zeichnen – der Bildschirm zeigt genau diese Ansicht."
                                 : "Mit dem Finger auf das Bild zeichnen – erscheint sofort auf dem Bildschirm.";
  if (!b) { if (heftOn) heft(false); if (!["laser", "stift", "marker", "radierer"].includes(tool)) pick("stift");
            buildColors(COLORS); return; }
  if (!was && store.get("alucast-pencil") === "") { pencilOnly = !!b.pencil_only; }
  $("pencil").checked = pencilOnly;
  buildColors(b.colors || COLORS);
  $("b-name").textContent = "· " + b.name;
  $("b-zoom").textContent = b.zoom + " %";
  $("b-page").textContent = b.page + " / " + b.pages;
  $("b-undo").disabled = !b.undo; $("b-redo").disabled = !b.redo;
  $("b-del").classList.toggle("hide", !b.sel);
  for (const g of $("guests").children) g.classList.toggle("on", g.dataset.g === (b.guests || "aus"));
  if (heftWanted() && !heftOn) heft(true); else hRender();
}
// ---- Heft-Ansicht: wie das Whiteboard-Fenster am PC (iPad). Auf dem Tablet öffnet sie sich von selbst, sobald die
// Tafel läuft und „Zeichnen“ offen ist („✕“ merkt sich: nicht mehr von selbst)
var heftOn = false, heftHome = null, thumbsVer = -1;
function heftWanted() { return !!board && current === "zeichnen" && innerWidth >= 740 && store.get("alucast-heft") !== "0"; }
function heft(on, byUser) {
  if (byUser) store.set("alucast-heft", on ? "1" : "0");
  if (on === heftOn || (on && !board)) return;
  if (fullEl) toggleFull();
  heftOn = on;
  const pv = $("dpreview");
  if (on) {
    heftHome = { parent: pv.parentNode, next: pv.nextSibling };
    $("hcanvas").appendChild(pv); $("heft").classList.remove("hide"); document.body.classList.add("heftmode");
    thumbsVer = -1; hRender(); setTimeout(sizeHeft, 30); refresh();
  } else {
    if (heftHome) heftHome.parent.insertBefore(pv, heftHome.next);
    pv.style.width = pv.style.height = "";
    $("heft").classList.add("hide"); $("heft").classList.remove("max");
    document.body.classList.remove("heftmode"); hMenu(); setTimeout(sizeInk, 30);
  }
}
// Vergrößern in der Heft-Ansicht: Tafel so groß wie möglich (Seitenliste und Status weg, Werkzeuge bleiben)
function heftMax(on) {
  const h = $("heft"); h.classList.toggle("max", on === undefined ? !h.classList.contains("max") : on);
  hMenu(); setTimeout(sizeHeft, 30);
}
function sizeHeft() {
  if (!heftOn) return;
  const box = $("hcanvas").getBoundingClientRect(), ar = window._ar || 16 / 9, pv = $("dpreview");
  const w = Math.min(box.width, box.height * ar);
  pv.style.width = Math.floor(w) + "px"; pv.style.height = Math.floor(w / ar) + "px";
  sizeInk();
}
window.addEventListener("resize", () => setTimeout(sizeHeft, 60));
for (const b of document.querySelectorAll("#h-tools button")) b.onclick = () => {
  if (b.dataset.t === "form" && tool === "form") return hMenu("form", b);
  pick(b.dataset.t);
};
for (const b of document.querySelectorAll("#h-widths button")) b.onclick = () => setWidth(+b.dataset.w);
function hRender() {
  if (!heftOn || !board) return;
  for (const b of document.querySelectorAll("#h-tools button")) b.classList.toggle("on", b.dataset.t === tool);
  $("h-shape").textContent = (SHAPES.find(x => x[0] === shape) || SHAPES[0])[1];
  const cols = board.colors || COLORS, hc = $("h-colors");
  if (hc.dataset.k !== cols.join(",")) {
    hc.dataset.k = cols.join(","); hc.innerHTML = "";
    for (const c of cols) { const b = document.createElement("button"); b.className = "sw"; b.style.background = c;
      b.dataset.c = c; b.title = c;
      b.onclick = () => { color = c; store.set("alucast-color", c);
        if (["laser", "radierer", "lasso"].includes(tool)) pick("stift"); showTools(); }; hc.appendChild(b); }
  }
  for (const b of hc.children) b.classList.toggle("sel", b.dataset.c === color && !["laser", "radierer", "lasso"].includes(tool));
  for (const b of document.querySelectorAll("#h-widths button")) b.classList.toggle("on", +b.dataset.w === widthF);
  $("h-undo").disabled = !board.undo; $("h-redo").disabled = !board.redo;
  $("h-zoom").textContent = board.zoom + " %"; $("h-page").textContent = board.page + " / " + board.pages;
  const paper = (board.papers || []).find(p => p[0] === board.bg);
  $("h-paper").textContent = (paper ? paper[1] : "Papier") + " ▾";
  $("hstatus").textContent = "„" + board.name + "“ · Seite " + board.page + " von " + board.pages + " · Zoom " + board.zoom +
    " %" + (board.sel ? " · " + board.sel + " ausgewählt" : "") + " · zwei Finger: zoomen und verschieben · der Bildschirm zeigt genau diese Ansicht";
  loadThumbs();
}
async function loadThumbs() {
  const box = $("hpages");
  if (box.children.length !== board.pages) {
    box.innerHTML = "";
    for (let i = 0; i < board.pages; i++) {
      const b = document.createElement("button"); const img = document.createElement("img"); img.alt = "";
      b.append(img, "Seite " + (i + 1)); b.onclick = () => boardOp("seite", String(i + 1)); box.appendChild(b);
    }
    thumbsVer = -1;
  }
  [...box.children].forEach((b, i) => b.classList.toggle("on", i === board.page - 1));
  if (board.thumbs === thumbsVer || !board.thumbs) return;
  thumbsVer = board.thumbs;
  for (let i = 0; i < box.children.length; i++) {
    try {
      const r = await fetch("/api/board/seite?n=" + i + "&v=" + thumbsVer, { headers: { "X-AluPC-Code": code } });
      if (r.status !== 200) continue;
      const img = box.children[i] && box.children[i].querySelector("img"); if (!img) return;
      const old = img.src; img.src = URL.createObjectURL(await r.blob()); if (old.startsWith("blob:")) URL.revokeObjectURL(old);
    } catch (e) { return; }
  }
}
function setBoard(key, value) { buzz(); post("/api/board", { op: "einstellung", key, value }); }
function hRow(label, control) {
  const row = document.createElement("label"); row.className = "hrow";
  const t = document.createElement("span"); t.textContent = label; row.append(t, control); return row;
}
function hSelect(key, opts, cur) {
  const s = document.createElement("select");
  for (const [v, l] of opts) { const o = document.createElement("option"); o.value = v; o.textContent = l; s.appendChild(o); }
  s.value = String(cur); s.onchange = () => setBoard(key, key === "smooth" ? +s.value : s.value); return s;
}
function hRange(key, lo, hi, cur) {
  const r = document.createElement("input"); r.type = "range"; r.min = lo; r.max = hi; r.value = cur;
  r.onchange = () => setBoard(key, +r.value); return r;
}
function hCheck(key, cur, also) {
  const c = document.createElement("input"); c.type = "checkbox"; c.checked = !!cur;
  c.onchange = () => { setBoard(key, c.checked); if (also) also(c.checked); }; return c;
}
function hMenu(which, anchor) {
  const sheet = $("hsheet"), body = $("hsheet-body"), card = sheet.querySelector(".hcard");
  if (!which || !board) { sheet.classList.add("hide"); return; }
  body.innerHTML = ""; sheet.classList.remove("hide");
  // Als Popover direkt unter dem Knopf (bleibt im Bild; zu lang → scrollt)
  const r = (anchor || $("h-board")).getBoundingClientRect(), w = Math.min(420, innerWidth - 16);
  card.style.left = Math.max(8, Math.min(r.left, innerWidth - w - 8)) + "px";
  card.style.top = Math.round(r.bottom + 6) + "px";
  card.style.maxHeight = Math.max(160, innerHeight - r.bottom - 18) + "px";
  const btn = (text, fn, on) => { const b = document.createElement("button"); b.textContent = text;
    if (on) b.classList.add("on"); b.onclick = () => { fn(); hMenu(); }; return b; };
  const nameRow = (label, value, go) => {  // statt prompt(): geht auch in der Home-Bildschirm-App des iPads
    const row = document.createElement("div"); row.className = "hname";
    const inp = document.createElement("input"); inp.maxLength = 60; inp.placeholder = label; inp.value = value;
    inp.enterKeyHint = "done";
    const ok = document.createElement("button"); ok.className = "primary"; ok.textContent = "OK";
    const send = () => { const n = inp.value.trim(); if (n) { go(n.slice(0, 60)); hMenu(); } else inp.focus(); };
    ok.onclick = send; inp.addEventListener("keydown", e => { if (e.key === "Enter") send(); });
    row.append(inp, ok); return [row, inp];
  };
  if (which === "tafel") {
    $("hsheet-title").textContent = "Tafel";
    const l = document.createElement("div"); l.className = "hlist";
    const [newRow, newInp] = nameRow("Name der neuen Tafel", "", n => boardOp("tafel_neu", n));
    const [renRow, renInp] = nameRow("Neuer Name", board.name, n => boardOp("tafel_umbenennen", n));
    newRow.classList.add("hide"); renRow.classList.add("hide");
    const show = (row, inp) => { newRow.classList.add("hide"); renRow.classList.add("hide"); row.classList.remove("hide");
      inp.focus(); inp.select(); };
    const nb = document.createElement("button"); nb.textContent = "＋ Neue Tafel …"; nb.onclick = () => show(newRow, newInp);
    const rb = document.createElement("button"); rb.textContent = "✎ Umbenennen …"; rb.onclick = () => show(renRow, renInp);
    l.append(nb, newRow, rb, renRow);
    const h = document.createElement("div"); h.className = "hint"; h.textContent = "Öffnen:"; l.append(h);
    for (const n of board.boards || []) l.append(btn(n, () => boardOp("tafel_oeffnen", n), n === board.name));
    body.append(l);
  } else if (which === "papier") {
    $("hsheet-title").textContent = "Papier dieser Seite";
    const g = document.createElement("div"); g.className = "hpapers";
    for (const [k, l] of board.papers || []) g.append(btn(l, () => boardOp("hintergrund", k), k === board.bg));
    body.append(g);
  } else if (which === "form") {
    $("hsheet-title").textContent = "Form";
    const l = document.createElement("div"); l.className = "hlist";
    for (const [k, name] of SHAPES) l.append(btn(name, () => { shape = k; store.set("alucast-shape", k); pick("form"); }, k === shape));
    body.append(l);
  } else if (which === "einst") {
    $("hsheet-title").textContent = "Einstellungen";
    const st = board.settings || {};
    body.append(
      hRow("Format", hSelect("format", board.formats || [], st.format)),
      hRow("Papier für neue Seiten", hSelect("background", board.papers || [], st.background)),
      hRow("Stift-Stärke", hRange("width", 1, 20, st.width)),
      hRow("Marker-Stärke", hRange("marker_width", 6, 60, st.marker_width)),
      hRow("Glätten", hSelect("smooth", [[0, "Aus"], [1, "Leicht"], [2, "Stark"]], st.smooth)),
      hRow("Druckempfindlich (Apple Pencil)", hCheck("pressure", st.pressure)),
      hRow("Nur der Stift zeichnet – Finger verschieben", hCheck("pencil_only", st.pencil_only, on => setPencil(on))),
      hRow("Radierer-Größe", hRange("eraser", 6, 80, st.eraser)),
      hRow("Textgröße", hRange("text_size", 14, 120, st.text_size)),
      hRow("Automatisch speichern", hCheck("autosave", st.autosave)),
      hRow("Gäste im AluPC-WLAN", hSelect("guests", [["aus", "Aus"], ["alle", "Alle schreiben"], ["frage", "Nur mit Erlaubnis"]], st.guests)));
  }
}
const ink = $("ink"), dpv = $("dpreview");
function sizeInk() {
  const box = dpv.getBoundingClientRect();
  ink.width = Math.round(box.width * devicePixelRatio); ink.height = Math.round(box.height * devicePixelRatio);
  redrawInk();
}
window.addEventListener("resize", sizeInk);
// Eigene Striche sofort zeigen (wie in einer Zeichen-App) – sie bleiben, bis das Live-Bild vom PC sie enthält
// (Bildnummer ≥ Nummer beim Ankommen + 2). Zoomen/Verschieben ebenso: das Bild bewegt sich sofort mit den Fingern,
// erst ein Live-Bild mit der neuen Ansicht ersetzt es.
let last = null, strokes = [], cur = null, inkQueued = false;
let vt = { s: 1, tx: 0, ty: 0 }, viewHold = 0, frameSeq = 0;
function applyView() {
  const im = $("dprev");
  im.style.transformOrigin = "0 0";
  im.style.transform = (vt.s === 1 && !vt.tx && !vt.ty) ? "" : "translate(" + vt.tx + "px," + vt.ty + "px) scale(" + vt.s + ")";
  redrawInk();
}
function inkWidth(pr) {  // Strichbreite in Pixeln wie auf dem Bildschirm
  const press = board && board.settings && board.settings.pressure && pr !== undefined && pr !== 0.5 ? 0.35 + pr * 1.3 : 1;
  const h = dpv.getBoundingClientRect().height;
  const px = board && board.page_h ? boardWidth() * (board.zoom_f || 1) * h / board.page_h
                                   : (tool === "marker" ? 14 : 4) * (board ? widthF : 1);
  return Math.max(1.2, px * press);
}
function redrawInk() {
  if (inkQueued) return; inkQueued = true;
  requestAnimationFrame(() => {
    inkQueued = false;
    const g = ink.getContext("2d"), W = ink.width, H = ink.height, d = devicePixelRatio;
    g.clearRect(0, 0, W, H); g.lineCap = "round"; g.lineJoin = "round";
    for (const st of strokes.concat(cur ? [cur] : [])) {
      if (!st.pts.length) continue;
      // Strich von vor einer Zoom-Geste: mit der Geste mitbewegen
      const k = vt.s / st.v.s, ox = vt.tx - st.v.tx * k, oy = vt.ty - st.v.ty * k;
      const X = q => (q.x * W / d * k + ox) * d, Y = q => (q.y * H / d * k + oy) * d;
      g.strokeStyle = st.color; g.globalAlpha = st.tool === "marker" ? .4 : 1;
      const p0 = st.pts[0], pn = st.pts[st.pts.length - 1];
      g.beginPath();
      if (st.shape) {
        g.lineWidth = st.pts[0].w * k * d;
        const x0 = X(p0), y0 = Y(p0), x1 = X(pn), y1 = Y(pn);
        if (st.shape === "rect") g.rect(x0, y0, x1 - x0, y1 - y0);
        else if (st.shape === "ellipse") g.ellipse((x0 + x1) / 2, (y0 + y1) / 2, Math.abs(x1 - x0) / 2, Math.abs(y1 - y0) / 2, 0, 0, 7);
        else { g.moveTo(x0, y0); g.lineTo(x1, y1);
          if (st.shape === "arrow") { const a = Math.atan2(y1 - y0, x1 - x0), L = Math.max(10 * d, g.lineWidth * 3);
            for (const s2 of [-1, 1]) { g.moveTo(x1, y1); g.lineTo(x1 - L * Math.cos(a + s2 * .45), y1 - L * Math.sin(a + s2 * .45)); } } }
        g.stroke(); continue;
      }
      if (st.tool === "marker" || st.pts.length < 2) {  // Marker: ein Pfad (keine dunklen Überlappungen)
        g.lineWidth = p0.w * k * d; g.moveTo(X(p0), Y(p0));
        for (const q of st.pts) g.lineTo(X(q), Y(q));
        if (st.pts.length < 2) g.lineTo(X(p0) + .1, Y(p0));
        g.stroke(); continue;
      }
      for (let i = 1; i < st.pts.length; i++) {  // Stift: Breite folgt dem Druck
        const a1 = st.pts[i - 1], b1 = st.pts[i];
        g.beginPath(); g.lineWidth = b1.w * k * d; g.moveTo(X(a1), Y(a1)); g.lineTo(X(b1), Y(b1)); g.stroke();
      }
    }
    g.globalAlpha = 1;
  });
}
function inkStart(p, e) {
  const local = ["stift", "marker", "form"].includes(tool) || (!board && tool !== "laser" && tool !== "radierer");
  cur = local ? { pts: [{ x: p.x, y: p.y, w: inkWidth(pressureOf(e)) }], color, tool, shape: tool === "form" ? shape : "",
                  v: { ...vt }, clearAt: Infinity } : null;
  redrawInk();
}
function inkAdd(p, e) { if (cur) { cur.pts.push({ x: p.x, y: p.y, w: inkWidth(pressureOf(e)) }); redrawInk(); } }
function inkEnd() {
  if (!cur) return; const st = cur; cur = null; strokes.push(st);
  sendDraw({ phase: "up" }, true, seq => { st.clearAt = seq === null ? 0 : seq; if (seq === null) dropInk(frameSeq); });
}
function dropInk(seq) {  // Live-Bild enthält alle Eingaben bis Nr. seq: Striche, die es schon zeigt, weg
  const n = strokes.length; strokes = strokes.filter(st => st.clearAt > seq);
  if (strokes.length !== n) redrawInk();
}
function frameArrived(seq) {  // neues Live-Bild angezeigt
  frameSeq = seq;
  if (viewHold && seq >= viewHold) {
    viewHold = 0; vt = { s: 1, tx: 0, ty: 0 };
    for (const st of strokes) st.v = { ...vt };
    if (cur) cur.v = { ...vt };
    applyView();
  }
  dropInk(seq);
}
// Tafel: zwei Finger = zoomen/verschieben; „Nur Stift“: ein Finger verschiebt, nur Apple Pencil/Maus zeichnet
const bpts = new Map(); let bgest = null, touchStart = null;
function pinchOf() {
  const box = dpv.getBoundingClientRect(), p = [...bpts.values()];
  return { d: Math.hypot((p[0].x - p[1].x) * box.width, (p[0].y - p[1].y) * box.height),
           m: { x: (p[0].x + p[1].x) / 2, y: (p[0].y + p[1].y) / 2 } };
}
function gestureStart(m, d) { viewHold = Infinity; bgest = { two: d !== undefined, m0: m, d0: d || 1, g0: { ...vt }, prev: { m, d: d || 1 } }; }
function gestureMove(m, d) {  // sofort am iPad (CSS) und als Ansicht-Nachricht an den PC
  const box = dpv.getBoundingClientRect(), rel = (d || bgest.d0) / bgest.d0;
  vt = { s: bgest.g0.s * rel, tx: m.x * box.width + rel * (bgest.g0.tx - bgest.m0.x * box.width),
         ty: m.y * box.height + rel * (bgest.g0.ty - bgest.m0.y * box.height) };
  applyView();
  const pr = bgest.prev, r = d ? d / Math.max(1, pr.d) : 1;
  sendBoard(r !== 1 ? { op: "view", zoom: r, ax: pr.m.x, ay: pr.m.y, dx: m.x - pr.m.x, dy: m.y - pr.m.y }
                    : { op: "view", dx: m.x - pr.m.x, dy: m.y - pr.m.y });
  bgest.prev = { m, d: d || 1 };
}
function gestureEnd() {  // erst ein Live-Bild mit der neuen Ansicht ersetzt das mitbewegte Bild
  bgest = null;
  sendBoard({ op: "view", dx: 0, dy: 0 }, true, seq => { viewHold = seq === null ? frameSeq : seq;
    if (seq === null) frameArrived(frameSeq); });
}
function pressureOf(e) { return e && e.pointerType === "pen" && e.pressure > 0 ? e.pressure : 0.5; }
function drawMsg(phase, p, e) {
  const m = { phase, x: p.x, y: p.y, tool: board ? boardTool() : tool, color };
  if (board) { m.pressure = pressureOf(e); const w = boardWidth(); if (w) m.width = w; }
  return m;
}
dpv.addEventListener("pointerdown", e => {
  if (e.target.closest("button") || pinching) return;
  capture(dpv, e); const p = norm(dpv, e);
  if (board) {
    bpts.set(e.pointerId, p);
    if (bpts.size >= 2) {  // zweiter Finger: ab jetzt zoomen/verschieben (der erste hat noch nicht gezeichnet)
      if (touchStart) touchStart = null;
      else if (last) sendDraw({ phase: "up" }, true);
      last = null; cur = null; redrawInk();
      const pc = pinchOf(); gestureStart(pc.m, pc.d); return;
    }
    if (pencilOnly && e.pointerType === "touch") { gestureStart(p); return; }
    if (tool === "text") {
      const t = prompt("Text für die Tafel:"); bpts.delete(e.pointerId);
      if (t && t.trim()) { buzz(); sendBoard({ op: "text", x: p.x, y: p.y, text: t.slice(0, 500), color }, true); }
      return;
    }
  }
  last = p;
  if (tool === "laser" && !board) { sendLaser(p); dotAt(p); return; }
  inkStart(p, e);
  if (board && e.pointerType === "touch") { touchStart = drawMsg("down", p, e); return; }  // erst bei Bewegung
  sendDraw(drawMsg("down", p, e), true);
});
dpv.addEventListener("pointermove", e => {
  if (board && bpts.has(e.pointerId)) {
    bpts.set(e.pointerId, norm(dpv, e));
    if (bgest && bgest.two && bpts.size >= 2) { const pc = pinchOf(); gestureMove(pc.m, pc.d); return; }
    if (bgest && !bgest.two) { gestureMove(norm(dpv, e)); return; }
  }
  if (!last || pinching) return;
  const evs = e.getCoalescedEvents ? e.getCoalescedEvents() : [e];  // Apple Pencil: alle Zwischenpunkte
  if (tool === "laser" && !board) { const p = norm(dpv, e); sendLaser(p); dotAt(p); return; }
  if (touchStart) { sendDraw(touchStart, true); touchStart = null; }
  for (const ev of evs.length ? evs : [e]) { const p = norm(dpv, ev); inkAdd(p, ev); last = p; }
  sendDraw(drawMsg("move", last, e));
});
function penUp(e) {
  if (e && bpts.has(e.pointerId)) {
    bpts.delete(e.pointerId);
    if (bgest && (!bgest.two || bpts.size < 2)) gestureEnd();
    if (!bpts.size) bgest = null;
  }
  if (!last) return; last = null;
  if (tool === "laser" && !board) { $("dlaser").style.display = "none"; sendLaser({ up: true }, true); return; }
  if (touchStart) { sendDraw(touchStart, true); touchStart = null; }  // nur getippt: ein Punkt
  if (cur) inkEnd(); else sendDraw({ phase: "up" }, true);
  if (board) setTimeout(refresh, 300);
}
dpv.addEventListener("pointerup", penUp);
dpv.addEventListener("pointercancel", penUp);
function dotAt(p) { const d = $("dlaser"); d.style.display = "block"; d.style.left = (p.x * 100) + "%"; d.style.top = (p.y * 100) + "%"; }
// ---- Vergrößern: Live-Bild bildschirmfüllend; zwei Finger = zoomen und verschieben (ein Finger zeigt/zeichnet weiter)
var fullEl = null, fullHome = null, pinching = false;
var zoom = { z: 1, x: 0, y: 0, pts: new Map(), d0: 0, z0: 1, m0: null, x0: 0, y0: 0 };
function applyZoom() {
  if (fullEl) fullEl.style.transform = "translate(calc(-50% + " + zoom.x + "px), calc(-50% + " + zoom.y + "px)) scale(" + zoom.z + ")";
}
function closeButton() {
  let b = $("fullclose");
  if (!b) { b = document.createElement("button"); b.id = "fullclose"; b.textContent = "✕ Schließen";
            b.onclick = () => toggleFull(); document.body.appendChild(b); }
}
function toggleFull(id) {
  closeButton();
  if (fullEl) {
    fullHome.parent.insertBefore(fullEl, fullHome.next);
    fullEl.classList.remove("fullview"); fullEl.style.transform = ""; fullEl = null;
    document.body.classList.remove("full");
  } else {
    const el = $(id || "dpreview");
    fullHome = { parent: el.parentNode, next: el.nextSibling };
    document.body.appendChild(el); el.classList.add("fullview");
    Object.assign(zoom, { z: 1, x: 0, y: 0 }); zoom.pts.clear(); fullEl = el; applyZoom();
    document.body.classList.add("full");
  }
  setTimeout(sizeInk, 50);
}
function pinchInfo() {
  const p = [...zoom.pts.values()];
  return { d: Math.hypot(p[0].x - p[1].x, p[0].y - p[1].y), m: { x: (p[0].x + p[1].x) / 2, y: (p[0].y + p[1].y) / 2 } };
}
window.addEventListener("pointerdown", e => {
  if (board || !fullEl || !fullEl.contains(e.target) || e.target.closest("button")) return;
  zoom.pts.set(e.pointerId, { x: e.clientX, y: e.clientY });
  if (zoom.pts.size === 2) {  // zweiter Finger: ab jetzt zoomen statt zeigen
    pinching = true; const i = pinchInfo();
    Object.assign(zoom, { d0: i.d, z0: zoom.z, m0: i.m, x0: zoom.x, y0: zoom.y });
    $("laser").style.display = "none"; $("dlaser").style.display = "none";
    if (allow.laser) sendLaser({ up: true }, true);
    if (last) { last = null; if (tool !== "laser") sendDraw({ phase: "up" }, true); }
  }
}, true);
window.addEventListener("pointermove", e => {
  if (!zoom.pts.has(e.pointerId)) return;
  zoom.pts.set(e.pointerId, { x: e.clientX, y: e.clientY });
  if (pinching && zoom.pts.size === 2) {
    const i = pinchInfo();
    zoom.z = Math.min(5, Math.max(1, zoom.z0 * i.d / Math.max(1, zoom.d0)));
    zoom.x = zoom.z === 1 ? 0 : zoom.x0 + (i.m.x - zoom.m0.x);
    zoom.y = zoom.z === 1 ? 0 : zoom.y0 + (i.m.y - zoom.m0.y);
    applyZoom();
  }
}, true);
function pinchEnd(e) {
  zoom.pts.delete(e.pointerId);
  if (!zoom.pts.size) setTimeout(() => { pinching = false; }, 60);
}
window.addEventListener("pointerup", pinchEnd, true);
window.addEventListener("pointercancel", pinchEnd, true);
document.addEventListener("keydown", e => { if (e.key === "Escape" && fullEl) toggleFull(); });

// ---- Touchpad: ein Finger bewegt, Tippen klickt; zwei Finger scrollen bzw. Rechtsklick
const pad = $("pad"), touches = new Map();
let moved = 0, downAt = 0, maxFingers = 0, scrollAcc = 0;
pad.addEventListener("pointerdown", e => {
  capture(pad, e); touches.set(e.pointerId, { x: e.clientX, y: e.clientY });
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
    if (xhr.status === 200) { toast("Auf dem Bildschirm"); $("upinfo").textContent = "Gesendet: " + file.name; setTimeout(refresh, 500); }
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
