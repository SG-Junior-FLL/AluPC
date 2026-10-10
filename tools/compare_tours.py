"""Linux ↔ Windows: Rundgang-Bilder und sichtbare Texte Seite für Seite vergleichen.

    python tools/compare_tours.py <Rundgang Linux> <Rundgang Windows> [<Ausgabeordner>]

Für jede Seite (gleicher Schlüssel in beiden screens.json): Anteil abweichender Bildpunkte (nach leichtem
Weichzeichnen – Kantenglättung zählt nicht) und Texte, die es nur auf einem System gibt. Schreibt eine Übersicht
(vergleich.md) und je Seite ein Bild „Linux | Windows | Unterschied“. Ausgabe als GitHub-Hinweise (::notice/::warning).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageFilter

WARN_AT = 0.06  # mehr als 6 % der Fläche sieht anders aus → Hinweis


def load(folder: Path) -> dict[str, dict]:
    path = folder / "screens.json"
    if not path.is_file():
        files = sorted(p.name for p in folder.glob("*"))[:10] if folder.is_dir() else []
        print(f"::error title=Vergleich::{path} fehlt (Ordner: {files or 'leer/fehlt'})")
        raise SystemExit(1)
    data = json.loads(path.read_text(encoding="utf-8"))
    out = {}
    for s in data["screens"]:
        key = s["key"]
        n = 2
        while key in out:  # gleicher Schlüssel mehrfach → durchnummerieren (in beiden Läufen gleich)
            key = f"{s['key']}#{n}"
            n += 1
        out[key] = s
    return out


def diff_ratio(a: Path, b: Path) -> tuple[float, Image.Image | None]:
    ia, ib = Image.open(a).convert("RGB"), Image.open(b).convert("RGB")
    if ia.size != ib.size:
        ib = ib.resize(ia.size)
    blur = ImageFilter.GaussianBlur(1.5)
    d = ImageChops.difference(ia.filter(blur), ib.filter(blur)).convert("L").point(lambda v: 255 if v > 40 else 0)
    hist = d.histogram()
    ratio = hist[255] / max(1, ia.size[0] * ia.size[1])
    side = Image.new("RGB", (ia.width * 3, ia.height))
    side.paste(ia, (0, 0))
    side.paste(ib, (ia.width, 0))
    side.paste(Image.merge("RGB", (d, Image.new("L", d.size), Image.new("L", d.size))), (ia.width * 2, 0))
    return ratio, side


def main() -> int:
    lin, win = Path(sys.argv[1]), Path(sys.argv[2])
    out = Path(sys.argv[3]) if len(sys.argv) > 3 else win.parent / "vergleich"
    out.mkdir(parents=True, exist_ok=True)
    a, b = load(lin), load(win)
    rows, text_rows = [], []
    for key in a:
        if key not in b:
            print(f"::warning title=Nur unter Linux::{a[key]['title']}")
            continue
        ratio, side = diff_ratio(lin / a[key]["file"], win / b[key]["file"])
        if side is not None:
            side.thumbnail((2400, 800))
            side.save(out / f"{key.replace('#', '-')}.png")
        ta, tb = set(a[key].get("ui_text", [])), set(b[key].get("ui_text", []))
        only_l, only_w = sorted(ta - tb), sorted(tb - ta)
        rows.append((ratio, key, a[key]["title"]))
        if only_l or only_w:
            text_rows.append((a[key]["title"], only_l, only_w))
    for key in b:
        if key not in a:
            print(f"::warning title=Nur unter Windows::{b[key]['title']}")
    rows.sort(reverse=True)
    lines = ["# Linux ↔ Windows", "", "| Abweichung | Seite |", "|---:|---|"]
    lines += [f"| {r * 100:.1f} % | {title} |" for r, _k, title in rows]
    lines += ["", "## Texte, die es nur auf einem System gibt", ""]
    for title, only_l, only_w in text_rows:
        lines.append(f"### {title}")
        lines += [f"- nur Linux: {t}" for t in only_l] + [f"- nur Windows: {t}" for t in only_w] + [""]
    (out / "vergleich.md").write_text("\n".join(lines), encoding="utf-8")
    same = sum(1 for r, _k, _t in rows if r < WARN_AT)
    print(f"::notice title=Oberfläche Linux ↔ Windows::{same} von {len(rows)} Seiten gleich (< {WARN_AT * 100:.0f} % "
          f"Abweichung) · {len(text_rows)} Seiten mit unterschiedlichen Texten")
    for r, _k, title in rows:
        if r >= WARN_AT:
            print(f"::notice title=Abweichung {r * 100:.0f} %::{title}")
    for title, only_l, only_w in text_rows[:40]:
        parts = [f"nur Linux: {t[:80]}" for t in only_l[:4]] + [f"nur Windows: {t[:80]}" for t in only_w[:4]]
        print(f"::notice title=Text – {title}::" + " | ".join(parts))
    return 0


if __name__ == "__main__":
    sys.exit(main())
