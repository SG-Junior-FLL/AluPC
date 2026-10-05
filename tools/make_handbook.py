"""Handbuch-PDF aus den Bildern des Rundgangs (tools/screens_tour.py) bauen.

    python tools/make_handbook.py <Rundgang-Ordner> <Ausgabe.pdf>

Baut eine HTML-Seite (Titelblatt, Inhalt, je Screen: Titel, Funktion, Bild; Handy-Bilder zu dritt) und druckt sie
mit Chromium (Playwright) als PDF. Bilder werden als JPEG eingebettet, damit die Datei klein bleibt.
"""

from __future__ import annotations

import base64
import html
import io
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from alupc import __version__  # noqa: E402

AREAS = [
    ("App", "Die App am PC", "Hauptfenster mit Seitenleiste: Start, Szenen, System, Setup, Fingerabdruck."),
    ("Fenster", "Fenster und Dialoge", "Was sich aus Kacheln, Menüs und dem Setup öffnet."),
    ("Monitor 2", "Was die anderen sehen", "Anzeigen auf dem zweiten Monitor (Beamer, Fernseher, Kundenmonitor)."),
    ("Minispiele", "Minispiele", "Handys sind die Controller, Monitor 2 ist das Spielfeld – gestartet wird nur am PC."),
    ("Handy", "Auf dem Handy", "Im Browser, ohne App: QR-Code scannen oder im AluPC-WLAN die Anmeldeseite."),
]


def img_data(path: Path, max_w: int = 1600) -> str:
    im = Image.open(path).convert("RGB")
    if im.width > max_w:
        im = im.resize((max_w, round(im.height * max_w / im.width)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=84, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def build_html(tour: Path) -> str:
    data = json.loads((tour / "screens.json").read_text(encoding="utf-8"))
    screens = list(data["screens"])
    phone = tour / "phone-shots.json"
    if phone.is_file():
        screens += json.loads(phone.read_text(encoding="utf-8"))
    for s in screens:  # Spiel-Screens als eigener Bereich
        if s["area"] == "Monitor 2" and (s["key"].startswith("spiel") or "Minispiele" in s["title"]):
            s["area"] = "Minispiele"
        if s["key"] == "spiele-fenster":
            s["area"] = "Minispiele"
    logo = img_data(ROOT / "alupc" / "resources" / "icons" / "alupc-256.png", 256)
    toc, body = [], []
    n = 0
    for area, heading, intro in AREAS:
        items = [s for s in screens if s["area"] == area]
        if not items:
            continue
        toc.append(f"<li><b>{html.escape(heading)}</b> – {len(items)} Screens<ul>"
                   + "".join(f"<li>{html.escape(s['title'])}</li>" for s in items) + "</ul></li>")
        body.append(f'<section class="area"><div class="areahead"><span>{html.escape(area)}</span>'
                    f"<h1>{html.escape(heading)}</h1><p>{html.escape(intro)}</p></div></section>")
        if area == "Handy":
            for i in range(0, len(items), 3):
                cells = []
                for s in items[i:i + 3]:
                    n += 1
                    cells.append(f'<figure class="phone"><img src="{img_data(tour / s["file"], 700)}">'
                                 f"<figcaption><b>{n}. {html.escape(s['title'].replace('Handy: ', ''))}</b>"
                                 f"<br>{html.escape(s['text'])}</figcaption></figure>")
                body.append(f'<section class="page phones">{"".join(cells)}</section>')
            continue
        for s in items:
            n += 1
            body.append(f'<section class="page"><div class="head"><span class="tag">{html.escape(area)}</span>'
                        f"<h2>{n}. {html.escape(s['title'])}</h2></div><p class='what'>{html.escape(s['text'])}</p>"
                        f'<div class="shot"><img src="{img_data(tour / s["file"])}"></div></section>')
    today = time.strftime("%d.%m.%Y")
    return f"""<!doctype html><html lang="de"><head><meta charset="utf-8"><title>AluPC – Handbuch</title>
<style>
@page {{ size: A4 landscape; margin: 11mm 13mm; }}
* {{ box-sizing: border-box; }}
body {{ font-family: Inter, "Segoe UI", system-ui, sans-serif; color: #0f172a; margin: 0; }}
.cover {{ height: 186mm; display: flex; flex-direction: column; justify-content: center; align-items: flex-start;
  padding: 0 18mm; background: linear-gradient(135deg, #0b1020 0%, #1e1b4b 60%, #0e7490 100%); color: #fff;
  border-radius: 8mm; page-break-after: always; }}
.cover img {{ width: 34mm; border-radius: 8mm; }}
.cover h1 {{ font-size: 40pt; margin: 8mm 0 2mm; }}
.cover p {{ font-size: 14pt; margin: 1mm 0; color: #cbd5e1; max-width: 200mm; }}
.toc {{ page-break-after: always; columns: 2; column-gap: 12mm; font-size: 10pt; }}
.toc h1 {{ column-span: all; font-size: 22pt; margin: 0 0 4mm; }}
.toc > ul {{ margin: 0; padding-left: 5mm; }} .toc ul ul {{ color: #475569; margin: 1mm 0 3mm; }}
.area {{ height: 186mm; display: flex; align-items: center; page-break-after: always; }}
.areahead span {{ font-size: 11pt; letter-spacing: 2px; text-transform: uppercase; color: #0891b2; font-weight: 800; }}
.areahead h1 {{ font-size: 34pt; margin: 2mm 0; }} .areahead p {{ font-size: 14pt; color: #475569; }}
.page {{ height: 186mm; page-break-after: always; display: flex; flex-direction: column; }}
.head {{ display: flex; align-items: baseline; gap: 4mm; }}
.tag {{ font-size: 8pt; font-weight: 800; letter-spacing: 1.5px; text-transform: uppercase; color: #fff;
  background: #3b82f6; padding: 1mm 2.5mm; border-radius: 2mm; }}
h2 {{ font-size: 18pt; margin: 0 0 1.5mm; }}
.what {{ font-size: 11pt; color: #334155; margin: 0 0 3mm; max-width: 250mm; }}
.shot {{ flex: 1; display: flex; align-items: center; justify-content: center; min-height: 0; }}
.shot img {{ max-width: 100%; max-height: 100%; border-radius: 3mm; box-shadow: 0 1mm 4mm rgba(0,0,0,.25); }}
.phones {{ flex-direction: row; gap: 8mm; justify-content: center; align-items: flex-start; }}
.phone {{ width: 78mm; margin: 0; }} .phone img {{ width: 100%; border-radius: 5mm; box-shadow: 0 1mm 4mm rgba(0,0,0,.25); }}
.phone img {{ max-height: 150mm; object-fit: cover; object-position: top; }}
figcaption {{ font-size: 9.5pt; color: #334155; margin-top: 2mm; }}
</style></head><body>
<section class="cover"><img src="{logo}"><h1>AluPC – Handbuch</h1>
<p>Alle Screens und was sie tun · Version {__version__} · {today}</p>
<p>Monitor 2 steuern, Handy als Fernbedienung und Controller, PC steuern, Minispiele, Dual-Boot-Abgleich.
Für Windows 11 und Kubuntu/Linux.</p>
<p style="font-size:10pt;color:#94a3b8;margin-top:8mm">Bilder automatisch aus der laufenden App erzeugt
(tools/screens_tour.py) – Beispieldaten, ohne echte Monitore/Kameras.</p></section>
<section class="toc"><h1>Inhalt</h1><ul>{"".join(toc)}</ul></section>
{"".join(body)}
</body></html>"""


def main():
    tour, out = Path(sys.argv[1]), Path(sys.argv[2])
    page = tour / "handbuch.html"
    page.write_text(build_html(tour), encoding="utf-8")
    node = shutil.which("node")
    if not node:
        print(f"HTML geschrieben: {page} (kein node/Playwright für das PDF)")
        return
    js = tour / "print.js"
    exe = os.environ.get("CHROMIUM", "")
    js.write_text(f"""const {{ chromium }} = require('playwright');
(async () => {{ const b = await chromium.launch({{ {f"executablePath: {json.dumps(exe)}, " if exe else ""}args: ['--no-sandbox'] }});
const p = await b.newPage(); await p.goto('file://{page.as_posix()}'); await p.waitForTimeout(500);
await p.pdf({{ path: {json.dumps(str(out))}, format: 'A4', landscape: true, printBackground: true }});
await b.close(); }})();""", encoding="utf-8")
    subprocess.run([node, str(js)], check=True)
    print(f"PDF geschrieben: {out} ({out.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
