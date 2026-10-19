"""Foto-Wand: Handys schicken Fotos übers AluPC-WLAN (Seiten-Code auf Monitor 2), Monitor 2
zeigt sie als Collage oder Diashow – neue Fotos kommen erst groß, dann in die Collage.

Fotos werden geprüft (echtes Bild, höchstens 25 MB, nur ein paar pro Minute je Handy), gedreht wie aufgenommen,
auf höchstens 2048 Pixel verkleinert und als JPEG im Ordner „AluPC Foto-Wand“ gespeichert. Am PC kann man
Fotos entfernen (Datei wird gelöscht), ein Handy sperren oder die Wand leeren (Dateien bleiben im Ordner).
Zum Senden braucht das Handy keinen Steuer-Code – nur das AluPC-WLAN.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

MAX_BYTES = 25 * 1024 * 1024
MAX_SIDE = 2048
RATE_WINDOW = 60.0
RATE_MAX = 8  # Fotos je Handy und Minute
MIN_GAP = 1.5
MAX_WALL = 400


def default_folder() -> Path:
    from PySide6.QtCore import QStandardPaths

    pics = QStandardPaths.writableLocation(QStandardPaths.PicturesLocation) or str(Path.home() / "Pictures")
    return Path(pics) / "AluPC Foto-Wand"


def decode(data: bytes):
    """Bytes → QImage (gedreht wie aufgenommen) oder None, wenn es kein Bild ist."""
    from PySide6.QtCore import QBuffer, QByteArray, QIODevice
    from PySide6.QtGui import QImageReader

    buf = QBuffer()
    buf.setData(QByteArray(data))
    buf.open(QIODevice.ReadOnly)
    reader = QImageReader(buf)
    reader.setAutoTransform(True)  # EXIF-Drehung (Handyfotos hochkant)
    size = reader.size()
    if size.isValid() and size.width() * size.height() > 80_000_000:  # absurd große Bilder gar nicht erst laden
        return None
    img = reader.read()
    if img.isNull() or img.width() < 16 or img.height() < 16:
        return None
    return img


class PhotoWall:
    def __init__(self, folder: Path | None = None):
        self.folder = Path(folder) if folder else default_folder()
        self.photos: list[dict] = []
        self.open = True
        self.version = 0
        self.blocked: set[str] = set()
        self._next = 1
        self._recent: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def add(self, data: bytes, name: str = "", ip: str = "", now: float | None = None) -> tuple[dict | None, str]:
        """Foto vom Handy (oder vom PC, ip="") → (Foto, "") oder (None, Grund)."""
        from PySide6.QtCore import Qt

        from .chat import clean_name

        now = time.time() if now is None else now
        if ip:
            if not self.open:
                return None, "Die Foto-Wand ist gerade geschlossen"
            if ip in self.blocked:
                return None, "Du bist für die Foto-Wand gesperrt"
            with self._lock:
                times = [t for t in self._recent.get(ip, []) if now - t < RATE_WINDOW]
                if times and now - times[-1] < MIN_GAP or len(times) >= RATE_MAX:
                    self._recent[ip] = times
                    return None, "Nicht so schnell – kurz warten"
                times.append(now)
                self._recent[ip] = times
        if not data or len(data) > MAX_BYTES:
            return None, "Foto zu groß (höchstens 25 MB)" if data else "Leere Datei"
        img = decode(data)
        if img is None:
            return None, "Das ist kein Foto (JPEG, PNG, WebP, HEIC als JPEG senden)"
        if max(img.width(), img.height()) > MAX_SIDE:
            img = img.scaled(MAX_SIDE, MAX_SIDE, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        try:
            self.folder.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            return None, f"Ordner nicht beschreibbar: {exc}"
        with self._lock:
            pid = self._next
            self._next += 1
        path = self.folder / (time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime(now)) + f"_{pid}.jpg")
        if not img.convertToFormat(img.Format.Format_RGB32).save(str(path), "JPEG", 88):
            return None, "Foto konnte nicht gespeichert werden"
        thumb = self.folder / ".vorschau" / path.name  # klein fürs Handy (Raster „Auf der Wand“)
        try:
            thumb.parent.mkdir(exist_ok=True)
            img.scaled(360, 360, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation).convertToFormat(
                img.Format.Format_RGB32).save(str(thumb), "JPEG", 80)
        except OSError:
            thumb = path
        photo = {"id": pid, "path": str(path), "thumb": str(thumb), "name": clean_name(name) or "Gast", "t": now,
                 "ip": ip, "w": img.width(), "h": img.height()}
        with self._lock:
            self.photos.append(photo)
            del self.photos[:-MAX_WALL]
            self.version += 1
        if ip:
            from .hotspot import note_name

            note_name(ip, photo["name"])
        return photo, ""

    def remove(self, pid: int, delete_file: bool = True) -> bool:
        with self._lock:
            hit = [p for p in self.photos if p["id"] == pid]
            self.photos = [p for p in self.photos if p["id"] != pid]
            if hit:
                self.version += 1
        for p in hit:
            if delete_file:
                for key in ("path", "thumb"):
                    Path(p.get(key) or p["path"]).unlink(missing_ok=True)
        return bool(hit)

    def block(self, ip: str, remove: bool = True) -> int:
        if not ip:
            return 0
        with self._lock:
            self.blocked.add(ip)
            hit = [p for p in self.photos if p.get("ip") == ip] if remove else []
        for p in hit:
            self.remove(p["id"])
        with self._lock:
            self.version += 1
        return len(hit)

    def unblock_all(self) -> None:
        with self._lock:
            self.blocked.clear()
            self.version += 1

    def clear(self) -> None:
        """Wand leeren – die Dateien bleiben im Ordner."""
        with self._lock:
            self.photos.clear()
            self.version += 1

    def set_open(self, on: bool) -> None:
        self.open = bool(on)
        self.version += 1

    def latest(self, n: int = 12) -> list[dict]:
        with self._lock:
            return list(self.photos[-n:]) if n > 0 else []

    def get(self, pid: int) -> dict | None:
        with self._lock:
            return next((p for p in self.photos if p["id"] == pid), None)

    def public(self, limit: int = 24) -> dict:
        with self._lock:
            items = [{"id": p["id"], "name": p["name"], "t": p["t"]} for p in self.photos[-limit:]]
        return {"open": self.open, "photos": items}


PHOTO_PAGE = """<!doctype html>
<html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#16181c"><title>AluPC – Foto-Wand</title>
<style>
:root { color-scheme: dark; }
* { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
body { margin: 0; min-height: 100vh; font-family: system-ui, -apple-system, "Segoe UI", sans-serif; color: #eceef1;
  background: radial-gradient(circle at 80% 0%, #831843 0, #16181c 55%); }
main { max-width: 520px; margin: 0 auto; padding: 18px 16px 40px; display: flex; flex-direction: column; gap: 14px; }
header { display: flex; align-items: center; gap: 10px; }
header .logo { width: 38px; height: 38px; border-radius: 12px; background: linear-gradient(135deg,#ec4899,#f59e0b);
  display: flex; align-items: center; justify-content: center; font-size: 20px; }
header b { font-size: 19px; } header small { display: block; color: #9aa1ac; font-size: 12.5px; }
header a { margin-left: auto; color: #f9a8d4; text-decoration: none; font-size: 14px; }
input[type=text] { width: 100%; font-size: 17px; padding: 13px 14px; border-radius: 14px; border: 2px solid #363b42;
  background: #1f2227; color: #fff; }
label.pick { display: block; text-align: center; padding: 26px 16px; border-radius: 20px; font-size: 21px; font-weight: 800;
  background: linear-gradient(135deg,#ec4899,#f59e0b); cursor: pointer; }
label.pick small { display: block; font-size: 13px; font-weight: 600; opacity: .9; margin-top: 4px; }
input[type=file] { display: none; }
#bar { height: 8px; border-radius: 4px; background: rgba(255,255,255,.1); overflow: hidden; display: none; }
#bar div { height: 100%; width: 0; background: linear-gradient(90deg,#f472b6,#fbbf24); transition: width .2s; }
#info { text-align: center; color: #9aa1ac; font-size: 14.5px; min-height: 20px; }
#info.ok { color: #86efac; } #info.err { color: #fca5a5; }
h2 { font-size: 15px; color: #cbd5e1; margin: 8px 0 0; }
#grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; }
#grid img { width: 100%; aspect-ratio: 1; object-fit: cover; border-radius: 10px; background: #292d33; }
/* iPad/Tablet: breiter, mehr Fotos pro Reihe */
@media (min-width: 700px) {
  main { max-width: 900px; padding: 28px 28px 48px; gap: 16px; }
  label.pick { padding: 34px 16px; font-size: 24px; }
  #grid { grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 10px; }
  #grid img { border-radius: 14px; }
}
</style></head><body><main>
<header><div class="logo">📷</div><div><b>Foto-Wand</b><small>Deine Fotos erscheinen groß auf dem Bildschirm</small></div>
</header>
<input type="text" id="name" maxlength="20" placeholder="Dein Name" autocomplete="off">
<label class="pick" for="file">📷 Foto senden<small>aufnehmen oder aus der Galerie – auch mehrere</small></label>
<input type="file" id="file" accept="image/*" multiple>
<div id="bar"><div></div></div><div id="info"></div>
<h2>Auf der Wand</h2><div id="grid"></div>
</main><script>
const $ = id => document.getElementById(id);
const store = { get(k) { try { return localStorage.getItem(k) || ""; } catch (e) { return ""; } },
                set(k, v) { try { localStorage.setItem(k, v); } catch (e) {} } };
$("name").value = store.get("alupc-name");
function info(text, cls) { $("info").textContent = text; $("info").className = cls || ""; }
async function shrink(file) {  // auf dem Handy verkleinern: schneller, und HEIC wird JPEG
  try {
    const bmp = await createImageBitmap(file, {imageOrientation: "from-image"});
    const s = Math.min(1, 2048 / Math.max(bmp.width, bmp.height));
    const c = document.createElement("canvas"); c.width = Math.round(bmp.width * s); c.height = Math.round(bmp.height * s);
    c.getContext("2d").drawImage(bmp, 0, 0, c.width, c.height);
    return await new Promise(r => c.toBlob(b => r(b || file), "image/jpeg", 0.86));
  } catch (e) { return file; }
}
function send(blob, name) {
  return new Promise(resolve => {
    const x = new XMLHttpRequest();
    x.open("POST", "/api/fotowand?name=" + encodeURIComponent(name));
    x.setRequestHeader("Content-Type", blob.type || "image/jpeg");
    x.upload.onprogress = e => { if (e.lengthComputable) $("bar").firstChild.style.width = (100 * e.loaded / e.total) + "%"; };
    x.onload = () => { let d = {}; try { d = JSON.parse(x.responseText); } catch (e) {} resolve([x.status, d]); };
    x.onerror = () => resolve([0, {error: "Keine Verbindung zum PC"}]);
    x.send(blob);
  });
}
$("file").onchange = async () => {
  const files = [...$("file").files]; $("file").value = "";
  const name = $("name").value.trim();
  if (!name) { info("Erst deinen Namen eingeben.", "err"); $("name").focus(); return; }
  store.set("alupc-name", name);
  let ok = 0, last = "";
  $("bar").style.display = "block";
  for (const [i, f] of files.entries()) {
    info("Sende Foto " + (i + 1) + " von " + files.length + " …");
    $("bar").firstChild.style.width = "0";
    const [status, d] = await send(await shrink(f), name);
    if (status === 200) ok++; else last = d.error || "Nicht gesendet";
  }
  $("bar").style.display = "none";
  if (ok) info(ok === 1 ? "Gesendet ✓ – gleich auf dem Bildschirm" : ok + " Fotos gesendet ✓", "ok");
  if (last) info((ok ? ok + " gesendet · " : "") + last, "err");
  load();
};
async function load() {
  try {
    const r = await fetch("/api/fotowand", {cache: "no-store"});
    if (!r.ok) { info(r.status === 404 ? "Die Foto-Wand ist gerade aus." : "Keine Verbindung zum PC …", "err"); return; }
    const d = await r.json();
    if (!d.open) info("Die Foto-Wand ist gerade geschlossen.", "err");
    const grid = $("grid"); const have = new Set([...grid.children].map(e => +e.dataset.id));
    const want = d.photos.slice().reverse();
    if (want.length !== have.size || want.some(p => !have.has(p.id))) {
      grid.innerHTML = "";
      for (const p of want) { const im = document.createElement("img"); im.loading = "lazy"; im.dataset.id = p.id;
        im.alt = p.name; im.src = "/api/fotowand/bild?klein=1&id=" + p.id; grid.appendChild(im); }
    }
  } catch (e) {}
}
load(); setInterval(load, 4000);
</script></body></html>"""
