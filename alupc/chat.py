"""Chat übers AluPC-WLAN: Handys schreiben (Seiten-Code auf Monitor 2), die Nachrichten erscheinen
sofort auf Monitor 2 – als Overlay über allem oder als Chat-Wand.

Weil alles direkt groß zu sehen ist, filtert AluPC: Schimpfwörter (eingebaute Liste + eigene Wörter) werden zu
„***“, Links werden ausgeblendet, jedes Handy darf nur ein paar Nachrichten pro Zeit schicken. Am PC kann man
einzelne Nachrichten löschen, ein Handy sperren, den Chat leeren oder schließen.

Zum Schreiben braucht das Handy keinen Steuer-Code – nur das AluPC-WLAN (wie Abstimmen und Mitspielen).
"""

from __future__ import annotations

import re
import threading
import time

MAX_KEEP = 300  # so viele Nachrichten bleiben im Speicher (ältere fallen raus)
MAX_TEXT = 200
MAX_NAME = 20
RATE_WINDOW = 10.0  # Sekunden
RATE_MAX = 4  # Nachrichten je Handy im Fenster
MIN_GAP = 0.8  # Sekunden zwischen zwei Nachrichten eines Handys

# Kurze eingebaute Liste (ganze Wörter und Wortanfänge, ohne Groß/Klein) – eigene Wörter kommen im Chat-Fenster dazu
BUILTIN_WORDS = [
    "arsch", "arschloch", "fick", "ficken", "fotze", "hurensohn", "hure", "wichser", "wixer", "schlampe", "missgeburt",
    "spast", "spasti", "behindert", "schwuchtel", "nazi", "hitler", "kanake", "neger", "nigger", "fuck", "fucking",
    "bitch", "shit", "scheiß", "scheiss", "pisser", "vollidiot", "porno", "porn", "pussy", "cunt", "whore", "slut",
    "motherfucker", "nutte",
]
URL_RE = re.compile(r"(https?://\S+|www\.\S+|\b[\w-]+\.(?:de|com|net|org|io|ly|tv|me|gg|app|info)\b\S*)", re.I)
NAME_RE = re.compile(r"[^\w .\-'äöüÄÖÜß]")


def clean_text(text: str) -> str:
    """Eine Zeile, ohne Steuerzeichen, gekürzt."""
    text = "".join(ch for ch in str(text or "") if ch.isprintable() or ch == " ")
    return " ".join(text.split())[:MAX_TEXT]


def clean_name(name: str) -> str:
    return NAME_RE.sub("", " ".join(str(name or "").split()))[:MAX_NAME].strip()


class WordFilter:
    def __init__(self, words: list[str] | None = None, builtin: bool = True, hide_links: bool = True):
        self.hide_links = hide_links
        words = [w.strip().lower() for w in (words or []) if w and w.strip()]
        words += BUILTIN_WORDS if builtin else []
        words = sorted(set(words), key=len, reverse=True)
        # Wortanfang: „Arschloch“, „Fickt“ … (aber nicht „Klassenarbeit“ wegen „arsch“ mitten im Wort)
        self._re = re.compile(r"(?<!\w)(" + "|".join(re.escape(w) for w in words) + r")\w*", re.I) if words else None

    def apply(self, text: str) -> tuple[str, bool]:
        """(gefilterter Text, ob etwas ersetzt wurde)"""
        changed = False
        if self.hide_links:
            text, n = URL_RE.subn("[Link]", text)
            changed |= n > 0
        if self._re is not None:
            text, n = self._re.subn(lambda m: "*" * min(6, max(3, len(m.group(0)))), text)
            changed |= n > 0
        return text, changed


class Chat:
    def __init__(self, words: list[str] | None = None, builtin: bool = True, hide_links: bool = True):
        self.messages: list[dict] = []
        self.open = True
        self.version = 0  # zählt jede Änderung (Overlay/Chat-Wand zeichnen nur dann neu)
        self.blocked: set[str] = set()  # gesperrte Handys (IP im AluPC-WLAN)
        self._next = 1
        self._recent: dict[str, list[float]] = {}
        self._lock = threading.Lock()
        self.filter = WordFilter(words, builtin, hide_links)

    def set_filter(self, words: list[str], builtin: bool = True, hide_links: bool = True) -> None:
        self.filter = WordFilter(words, builtin, hide_links)

    # ------------------------------------------------------------ Schreiben
    def post(self, name: str, text: str, ip: str = "", avatar: str = "", host: bool = False,
             now: float | None = None) -> tuple[dict | None, str]:
        """Neue Nachricht → (Nachricht, "") oder (None, Grund)."""
        from .games import AVATARS

        now = time.time() if now is None else now
        text = clean_text(text)
        if not text:
            return None, "Leere Nachricht"
        if not host:
            if not self.open:
                return None, "Der Chat ist gerade geschlossen"
            if ip in self.blocked:
                return None, "Du bist im Chat gesperrt"
            with self._lock:
                times = [t for t in self._recent.get(ip, []) if now - t < RATE_WINDOW]
                if times and now - times[-1] < MIN_GAP or len(times) >= RATE_MAX:
                    self._recent[ip] = times
                    return None, "Nicht so schnell – kurz warten"
                times.append(now)
                self._recent[ip] = times
        text, filtered = self.filter.apply(text)
        name = clean_name(name) or ("AluPC" if host else "Gast")
        name, name_filtered = self.filter.apply(name)
        msg = {"id": 0, "name": name, "avatar": avatar if avatar in AVATARS else ("📢" if host else ""),
               "text": text, "t": now, "ip": ip, "host": host, "filtered": filtered or name_filtered}
        with self._lock:
            msg["id"] = self._next
            self._next += 1
            self.messages.append(msg)
            del self.messages[:-MAX_KEEP]
            self.version += 1
        if ip and not host:
            from .hotspot import note_name

            note_name(ip, name)
        return msg, ""

    # ------------------------------------------------------------ Verwalten (am PC)
    def delete(self, mid: int) -> bool:
        with self._lock:
            before = len(self.messages)
            self.messages = [m for m in self.messages if m["id"] != mid]
            changed = len(self.messages) != before
            if changed:
                self.version += 1
        return changed

    def block(self, ip: str, remove: bool = True) -> int:
        """Handy sperren (und seine Nachrichten entfernen) → Anzahl entfernter Nachrichten."""
        if not ip:
            return 0
        with self._lock:
            self.blocked.add(ip)
            before = len(self.messages)
            if remove:
                self.messages = [m for m in self.messages if m.get("ip") != ip]
            self.version += 1
            return before - len(self.messages)

    def unblock_all(self) -> None:
        with self._lock:
            self.blocked.clear()
            self.version += 1

    def clear(self) -> None:
        with self._lock:
            self.messages.clear()
            self.version += 1

    def set_open(self, on: bool) -> None:
        self.open = bool(on)
        self.version += 1

    # ------------------------------------------------------------ Lesen
    def latest(self, n: int = 6, max_age: float = 0.0, now: float | None = None) -> list[dict]:
        now = time.time() if now is None else now
        with self._lock:
            items = list(self.messages[-n:]) if n > 0 else []
        if max_age > 0:
            items = [m for m in items if now - m["t"] <= max_age]
        return items

    @staticmethod
    def public(msg: dict) -> dict:
        return {k: msg[k] for k in ("id", "name", "avatar", "text", "t", "host")}

    def since(self, after: int = 0, limit: int = 60) -> dict:
        """Was das Handy sieht: Nachrichten nach `after` (höchstens `limit`), offen ja/nein."""
        with self._lock:
            items = [self.public(m) for m in self.messages if m["id"] > after][-limit:]
            last = self.messages[-1]["id"] if self.messages else 0
        return {"open": self.open, "messages": items, "last": last}


def name_color(name: str) -> str:
    """Feste Farbe je Name (gut lesbar auf dunklem Grund)."""
    palette = ["#60a5fa", "#f472b6", "#34d399", "#fbbf24", "#a78bfa", "#f87171", "#22d3ee", "#fb923c", "#a3e635"]
    return palette[sum(ord(c) for c in name) % len(palette)]


CHAT_PAGE = """<!doctype html>
<html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover, interactive-widget=resizes-content">
<meta name="theme-color" content="#0b1020"><title>AluPC – Chat</title>
<style>
:root { color-scheme: dark; }
* { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
html, body { height: 100%; }
body { margin: 0; font-family: system-ui, -apple-system, "Segoe UI", sans-serif; color: #f1f5f9;
  background: radial-gradient(circle at 20% 0%, #1e3a8a 0, #0b1020 55%); display: flex; flex-direction: column; }
header { display: flex; align-items: center; gap: 10px; padding: 14px 16px 10px; }
header .logo { width: 38px; height: 38px; border-radius: 12px; background: linear-gradient(135deg,#6366f1,#06b6d4);
  display: flex; align-items: center; justify-content: center; font-size: 20px; }
header b { font-size: 19px; } header small { display: block; color: #94a3b8; font-size: 12.5px; }
header a { margin-left: auto; color: #a5b4fc; text-decoration: none; font-size: 14px; }
#list { flex: 1; overflow-y: auto; padding: 6px 12px 12px; display: flex; flex-direction: column; gap: 8px; }
.m { max-width: 84%; background: rgba(255,255,255,.07); border: 1px solid rgba(255,255,255,.08);
  border-radius: 16px 16px 16px 6px; padding: 8px 12px; align-self: flex-start; animation: pop .25s ease; }
.m.me { align-self: flex-end; background: rgba(99,102,241,.32); border-color: rgba(129,140,248,.4);
  border-radius: 16px 16px 6px 16px; }
.m.host { align-self: center; background: rgba(245,158,11,.18); border-color: rgba(245,158,11,.4); }
.m .n { font-size: 12.5px; font-weight: 700; margin-bottom: 2px; }
.m .t { font-size: 16px; line-height: 1.35; word-wrap: break-word; }
@keyframes pop { from { transform: translateY(6px); opacity: 0; } to { transform: none; opacity: 1; } }
.empty { color: #94a3b8; text-align: center; margin: auto; font-size: 15px; padding: 30px; }
form { display: flex; gap: 8px; padding: 10px 12px calc(10px + env(safe-area-inset-bottom)); background: rgba(11,16,32,.92);
  border-top: 1px solid rgba(255,255,255,.08); }
input { flex: 1; min-width: 0; font-size: 17px; padding: 13px 14px; border-radius: 14px; border: 2px solid #334155;
  background: #0f172a; color: #fff; }
input:focus { outline: none; border-color: #6366f1; }
button { border: 0; border-radius: 14px; padding: 0 18px; font-size: 17px; font-weight: 800; color: #fff;
  background: linear-gradient(135deg,#6366f1,#ec4899); }
button:disabled { opacity: .45; }
#who { display: flex; gap: 8px; padding: 0 12px 8px; }
#who input { font-size: 15px; padding: 9px 12px; }
#info { color: #fca5a5; font-size: 13.5px; text-align: center; min-height: 18px; padding: 0 12px; }
/* iPad/Tablet: Gespräch als Spalte in der Mitte, Eingabe als schwebende Leiste */
@media (min-width: 700px) {
  header, #who, #list, #info, form { width: min(100% - 32px, 760px); margin-left: auto; margin-right: auto; }
  header { padding: 22px 4px 14px; } #who { padding: 0 0 10px; } #list { padding: 6px 0 14px; }
  .m { max-width: 72%; } .m .t { font-size: 17px; }
  form { border: 1px solid rgba(255,255,255,.1); border-radius: 22px; margin-bottom: calc(16px + env(safe-area-inset-bottom));
         padding: 10px; background: rgba(15,23,42,.85); box-shadow: 0 14px 40px rgba(0,0,0,.35); }
}
</style></head><body>
<header><div class="logo">💬</div><div><b>Chat</b><small>Erscheint groß auf Monitor 2 · bitte freundlich</small></div>
</header>
<div id="who"><input id="name" maxlength="20" placeholder="Dein Name" autocomplete="off"></div>
<div id="list"><div class="empty" id="empty">Noch keine Nachrichten – schreib die erste!</div></div>
<div id="info"></div>
<form id="f"><input id="text" maxlength="200" placeholder="Nachricht …" autocomplete="off" enterkeyhint="send">
<button id="send">➤</button></form>
<script>
const $ = id => document.getElementById(id);
const store = { get(k) { try { return localStorage.getItem(k) || ""; } catch (e) { return ""; } },
                set(k, v) { try { localStorage.setItem(k, v); } catch (e) {} } };
$("name").value = store.get("alupc-name");
let last = 0, mine = new Set(JSON.parse(store.get("alupc-chat-mine") || "[]")), busy = false;
function el(tag, cls, text) { const e = document.createElement(tag); if (cls) e.className = cls; if (text !== undefined) e.textContent = text; return e; }
const colors = ["#60a5fa","#f472b6","#34d399","#fbbf24","#a78bfa","#f87171","#22d3ee","#fb923c","#a3e635"];
function color(n) { let s = 0; for (const c of n) s += c.codePointAt(0); return colors[s % colors.length]; }
function add(m) {
  $("empty") && $("empty").remove();
  const box = el("div", "m" + (mine.has(m.id) ? " me" : "") + (m.host ? " host" : ""));
  const n = el("div", "n", (m.avatar ? m.avatar + " " : "") + m.name); n.style.color = m.host ? "#fbbf24" : color(m.name);
  box.appendChild(n); box.appendChild(el("div", "t", m.text));
  const list = $("list"); const atEnd = list.scrollHeight - list.scrollTop - list.clientHeight < 80;
  list.appendChild(box);
  if (atEnd || mine.has(m.id)) list.scrollTop = list.scrollHeight;
}
async function load() {
  try {
    const r = await fetch("/api/chat?after=" + last, {cache: "no-store"});
    if (!r.ok) { $("info").textContent = r.status === 404 ? "Der Chat ist gerade aus." : "Keine Verbindung zum PC …"; return; }
    const d = await r.json();
    for (const m of d.messages) { if (m.id > last) { add(m); last = m.id; } }
    if (!d.open) $("info").textContent = "Der Chat ist gerade geschlossen.";
    else if ($("info").dataset.err !== "1") $("info").textContent = "";
  } catch (e) { $("info").textContent = "Keine Verbindung zum PC …"; }
}
$("f").onsubmit = async e => {
  e.preventDefault();
  const text = $("text").value.trim(), name = $("name").value.trim();
  if (!text || busy) return;
  if (!name) { $("name").focus(); $("info").textContent = "Erst deinen Namen eingeben."; return; }
  store.set("alupc-name", name);
  busy = true; $("send").disabled = true;
  try {
    const r = await fetch("/api/chat", {method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({name, text, avatar: store.get("alupc-avatar")})});
    const d = await r.json().catch(() => ({}));
    if (r.ok) { mine.add(d.id); store.set("alupc-chat-mine", JSON.stringify([...mine].slice(-200)));
      $("text").value = ""; $("info").dataset.err = ""; $("info").textContent = d.filtered ? "Ein paar Wörter wurden ausgeblendet." : ""; await load(); }
    else { $("info").dataset.err = "1"; $("info").textContent = d.error || "Nicht gesendet"; setTimeout(() => $("info").dataset.err = "", 4000); }
  } catch (err) { $("info").textContent = "Nicht gesendet – keine Verbindung"; }
  busy = false; $("send").disabled = false; $("text").focus();
};
load(); setInterval(load, 1500);
</script></body></html>"""
