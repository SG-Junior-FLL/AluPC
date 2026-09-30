"""Abstimmung per Handy: Frage auf Monitor 2, QR-Code scannen, antippen – Ergebnis erscheint live.

Zum Abstimmen braucht das Handy NICHT den Code der Handy-Steuerung: Der QR-Code enthält nur ein eigenes
Stichwort für diese Abstimmung (damit kann man nur abstimmen, nichts steuern). Jedes Handy hat eine Stimme
(Kennung im Browser gespeichert) und darf sie ändern. Ehrlich: Wer die Browserdaten löscht, kann nochmal
abstimmen – für eine Klassen-/Team-Abstimmung reicht das.
"""

from __future__ import annotations

import re
import secrets
import threading

MAX_OPTIONS = 6
MAX_VOTERS = 2000
VOTER_RE = re.compile(r"[A-Za-z0-9_-]{8,64}")


class Poll:
    def __init__(self, question: str, options: list[str]):
        opts = [" ".join(str(o).split())[:80] for o in options if str(o).strip()][:MAX_OPTIONS]
        if len(opts) < 2:
            raise ValueError("Mindestens zwei Antworten")
        self.question = " ".join(str(question).split())[:160] or "Abstimmung"
        self.options = opts
        self.token = secrets.token_urlsafe(6)
        self.votes: dict[str, int] = {}
        self.open = True
        self.version = 0  # zählt jede Änderung (Monitor 2 zeichnet nur dann neu)
        self._lock = threading.Lock()

    def vote(self, voter: str, choice: int) -> bool:
        if not self.open or not VOTER_RE.fullmatch(voter or "") or not (0 <= choice < len(self.options)):
            return False
        with self._lock:
            if voter not in self.votes and len(self.votes) >= MAX_VOTERS:
                return False
            if self.votes.get(voter) != choice:
                self.votes[voter] = choice
                self.version += 1
        return True

    def counts(self) -> list[int]:
        with self._lock:
            counts = [0] * len(self.options)
            for choice in self.votes.values():
                counts[choice] += 1
        return counts

    def total(self) -> int:
        return len(self.votes)

    def close(self) -> None:
        self.open = False
        self.version += 1

    def reopen(self) -> None:
        self.open = True
        self.version += 1

    def reset(self) -> None:
        with self._lock:
            self.votes.clear()
            self.open = True
            self.version += 1

    def public(self, voter: str = "") -> dict:
        """Was das Handy sieht (Ergebnis erst nach der eigenen Stimme)."""
        mine = self.votes.get(voter)
        data = {"question": self.question, "options": self.options, "open": self.open, "mine": mine}
        if mine is not None or not self.open:
            data["counts"] = self.counts()
        return data


POLL_PAGE = """<!doctype html>
<html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#0b1020"><title>Abstimmung</title>
<style>
:root { color-scheme: dark; }
* { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
body { margin: 0; min-height: 100vh; font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
  background: radial-gradient(circle at 20% 0%, #312e81 0, #0b1020 55%); color: #f1f5f9; }
main { max-width: 520px; margin: 0 auto; padding: 28px 18px 40px; }
.tag { font-size: 13px; letter-spacing: .08em; text-transform: uppercase; color: #a5b4fc; font-weight: 700; }
h1 { font-size: 26px; line-height: 1.25; margin: 8px 0 22px; }
button { display: block; width: 100%; text-align: left; font: inherit; font-size: 18px; font-weight: 600;
  color: #f8fafc; background: rgba(255,255,255,.07); border: 2px solid rgba(255,255,255,.12);
  border-radius: 16px; padding: 16px 18px; margin: 0 0 12px; position: relative; overflow: hidden; }
button:active { transform: scale(.985); }
button.mine { border-color: #818cf8; background: rgba(99,102,241,.25); }
button .bar { position: absolute; inset: 0 auto 0 0; background: rgba(129,140,248,.28); width: 0;
  transition: width .5s ease; }
button span { position: relative; }
button .n { float: right; color: #c7d2fe; font-variant-numeric: tabular-nums; }
button:disabled { opacity: .9; }
p.info { color: #94a3b8; font-size: 15px; text-align: center; margin-top: 18px; }
p.ok { color: #86efac; }
</style></head><body><main>
<div class="tag">Abstimmung</div><h1 id="q">…</h1><div id="opts"></div><p class="info" id="info"></p>
</main><script>
const token = new URLSearchParams(location.search).get("u") || "";
let voter = "";
try { voter = localStorage.getItem("alupc-voter") || ""; } catch (e) {}
if (!voter) {
  voter = Array.from(crypto.getRandomValues(new Uint8Array(12)), b => b.toString(16).padStart(2, "0")).join("");
  try { localStorage.setItem("alupc-voter", voter); } catch (e) {}
}
const $ = id => document.getElementById(id);
function render(d) {
  $("q").textContent = d.question;
  const box = $("opts"); box.innerHTML = "";
  const total = d.counts ? d.counts.reduce((a, b) => a + b, 0) : 0;
  d.options.forEach((text, i) => {
    const b = document.createElement("button");
    if (d.mine === i) b.className = "mine";
    b.disabled = !d.open;
    const bar = document.createElement("div"); bar.className = "bar"; b.appendChild(bar);
    const t = document.createElement("span"); t.textContent = text; b.appendChild(t);
    if (d.counts) {
      const n = document.createElement("span"); n.className = "n";
      n.textContent = total ? Math.round(100 * d.counts[i] / total) + " %" : "0 %"; b.appendChild(n);
      requestAnimationFrame(() => bar.style.width = (total ? 100 * d.counts[i] / total : 0) + "%");
    }
    b.onclick = () => vote(i);
    box.appendChild(b);
  });
  const info = $("info");
  info.className = "info" + (d.mine !== null && d.mine !== undefined ? " ok" : "");
  info.textContent = !d.open ? "Abstimmung beendet" :
    (d.mine !== null && d.mine !== undefined ? "Danke! Du kannst deine Stimme noch ändern." : "Tippe auf eine Antwort.");
}
async function load() {
  try {
    const r = await fetch("/api/umfrage?u=" + encodeURIComponent(token) + "&v=" + voter, {cache: "no-store"});
    if (!r.ok) { $("q").textContent = "Keine laufende Abstimmung"; $("opts").innerHTML = ""; $("info").textContent = ""; return; }
    render(await r.json());
  } catch (e) { $("info").textContent = "Keine Verbindung zu AluPC"; }
}
async function vote(i) {
  try {
    const r = await fetch("/api/umfrage", {method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({u: token, v: voter, c: i})});
    if (r.ok) render(await r.json()); else load();
  } catch (e) { $("info").textContent = "Keine Verbindung zu AluPC"; }
}
load(); setInterval(load, 3000);
</script></body></html>
"""
