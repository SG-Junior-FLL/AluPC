"""Handbuch-PDF aus den Bildern des Rundgangs (tools/screens_tour.py) bauen.

    python tools/make_handbook.py <Rundgang-Ordner> <Ausgabe.pdf>

Teil 1 (A4 hoch): Anleitung aus docs/handbuch-anleitung.html mit Bildern aus dem Rundgang. Teil 2 (A4 quer): alle
Screens – je Screen Titel, Funktion, Bild; Handy-Bilder zu dritt. Druck mit Chromium (Playwright); Bilder als JPEG,
Schriften (Inter, JetBrains Mono) eingebettet – sieht überall gleich aus.
"""

from __future__ import annotations

import base64
import html
import io
import json
import os
import re
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


FONTS = [("Inter", 400, "normal", "Inter-Regular.ttf"), ("Inter", 500, "normal", "Inter-Medium.ttf"),
         ("Inter", 600, "normal", "Inter-SemiBold.ttf"), ("Inter", 700, "normal", "Inter-Bold.ttf"),
         ("Inter", 800, "normal", "Inter-ExtraBold.ttf"), ("Inter", 400, "italic", "Inter-Italic.ttf"),
         ("JetBrains Mono", 400, "normal", "JetBrainsMono-Regular.ttf"),
         ("JetBrains Mono", 700, "normal", "JetBrainsMono-Bold.ttf")]


def font_css() -> str:
    folder = ROOT / "alupc" / "assets" / "fonts"
    out = []
    for family, weight, style, name in FONTS:
        f = folder / name
        if f.is_file():
            data = base64.b64encode(f.read_bytes()).decode()
            out.append(f"@font-face {{ font-family: '{family}'; font-weight: {weight}; font-style: {style}; "
                       f"src: url(data:font/ttf;base64,{data}) format('truetype'); }}")
    return "\n".join(out)


def guide_html(tour: Path, screens: list[dict]) -> str:
    """Anleitung (docs/handbuch-anleitung.html): IMG(schlüssel) → Bild aus dem Rundgang, VERSION → Version."""
    src = ROOT / "docs" / "handbuch-anleitung.html"
    if not src.is_file():
        return ""
    files = {s["key"]: s["file"] for s in screens}

    def img(m):
        key = m.group(1)
        if key not in files:
            raise SystemExit(f"Anleitung: Bild „{key}“ fehlt im Rundgang")
        return img_data(tour / files[key], 1400)

    text = re.sub(r"<!--.*?-->", "", src.read_text(encoding="utf-8"), flags=re.S)  # Erklärung oben weg
    text = re.sub(r"IMG\(([\w-]+)\)", img, text)
    return f'<div class="guide">{text.replace("VERSION", __version__)}</div>'


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
    guide = guide_html(tour, screens)
    fonts = font_css()
    return f"""<!doctype html><html lang="de"><head><meta charset="utf-8"><title>AluPC – Handbuch</title>
<style>
{fonts}
@page {{ size: A4 portrait; margin: 16mm 17mm 15mm; }}
@page quer {{ size: A4 landscape; margin: 11mm 13mm; }}
.quer {{ page: quer; break-before: page; }}
* {{ box-sizing: border-box; }}
body {{ font-family: Inter, "Segoe UI", system-ui, sans-serif; color: #0f172a; margin: 0; }}
/* Anleitung (A4 hoch) */
.guide {{ font-size: 10.5pt; line-height: 1.5; }}
.guide h1 {{ font-size: 26pt; letter-spacing: -0.02em; margin: 0 0 2mm; }}
.guide h2 {{ font-size: 17pt; margin: 0 0 3mm; break-after: avoid; }}
.guide h3 {{ font-size: 12pt; margin: 4mm 0 1.5mm; break-after: avoid; }}
.guide section {{ break-before: page; }}
.guide section:first-of-type {{ break-before: auto; }}
.guide .lead {{ font-size: 12.5pt; color: #475569; }}
.guide .version {{ font-family: "JetBrains Mono", monospace; font-size: 9pt; color: #64748b; }}
.guide p {{ margin: 0 0 2.5mm; }}
.guide ul, .guide ol {{ margin: 0 0 3mm; padding-left: 6mm; }}
.guide li {{ margin-bottom: 1.2mm; }}
.guide figure {{ margin: 3mm 0; break-inside: avoid; }}
.guide figure img {{ width: 100%; border-radius: 2mm; border: 0.3mm solid #cbd5e1; }}
.guide figcaption {{ font-size: 9pt; color: #475569; margin-top: 1.2mm; }}
.guide .figs {{ display: grid; grid-template-columns: 1fr 1fr; gap: 5mm; }}
.guide table {{ border-collapse: collapse; width: 100%; font-size: 9.5pt; margin: 2mm 0 4mm; break-inside: avoid; }}
.guide th, .guide td {{ text-align: left; padding: 1.6mm 2mm; border-bottom: 0.3mm solid #cbd5e1; vertical-align: top; }}
.guide th {{ font-size: 8pt; text-transform: uppercase; letter-spacing: 0.06em; color: #64748b; }}
.guide code {{ font-family: "JetBrains Mono", monospace; font-size: 0.9em; }}
.guide kbd {{ font-family: "JetBrains Mono", monospace; font-size: 0.85em; border: 0.3mm solid #cbd5e1;
  border-bottom-width: 0.6mm; border-radius: 1mm; padding: 0 1mm; background: #f1f5f9; }}
.guide .callout {{ background: #eef2ff; border-radius: 2mm; padding: 2.5mm 4mm; margin: 3mm 0; break-inside: avoid; }}
.guide .callout.warn {{ background: #fff7ed; border-left: 1.2mm solid #f59e0b; }}
.cover {{ height: 255mm; display: flex; flex-direction: column; justify-content: center; align-items: flex-start;
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
<p>Anleitung und alle Screens · Version {__version__} · {today}</p>
<p>Monitor 2 steuern, Handy als Fernbedienung und Controller, PC steuern, Minispiele, Dual-Boot-Abgleich.
Für Windows 11 und Kubuntu/Linux.</p>
<p style="font-size:10pt;color:#94a3b8;margin-top:8mm">Bilder automatisch aus der laufenden App erzeugt
(tools/screens_tour.py) – Beispieldaten, ohne echte Monitore/Kameras.</p></section>
{guide}
<div class="quer">
<section class="toc"><h1>Anhang: alle Screens</h1><ul>{"".join(toc)}</ul></section>
{"".join(body)}
</div>
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
await p.pdf({{ path: {json.dumps(str(out))}, preferCSSPageSize: true, printBackground: true }});
await b.close(); }})();""", encoding="utf-8")
    subprocess.run([node, str(js)], check=True)
    print(f"PDF geschrieben: {out} ({out.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
