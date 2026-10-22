"""AluPC-Tastenbox – Stift-Adapter: flaches Schalter-Beinchen (Outemu/MX) ↔ Dupont-Jumper-Stecker (CadQuery). Entwurf 2.

Ohne Löten: unten steckt das Kunststoff-Gehäuse eines normalen Jumper-Kabels (Stecker) in einer Buchse, sein
Metallstift ragt hoch in einen engen Schlitz. Von oben kommt das Schalter-Beinchen in denselben Schlitz und wird
gegen den Stift gepresst (Schlitz etwas schmaler als Stift + Beinchen, unten noch enger → klemmt).

Maße vom MX-Footprint (KiCad-Bibliothek keyswitches.pretty, SW_MX): Beinchen bei (2,54 | −5,08) und (−3,81 | −2,54),
Loch Ø 1,5; Mittelzapfen Ø 4,0; Kunststoffstifte Ø 1,7 bei ±5,08. Neben Beinchen 2 sind bis zum Kunststoffstift nur
~2 mm frei → oben nur ein dünner runder „Finger“ (Ø 3,4, so lang wie das Beinchen + Luft); die breite Buchse fürs
Jumper-Gehäuse sitzt darunter, wo der Schalter nichts mehr hat.

Druck: stehend, Buchse unten aufs Bett, ohne Stützen. PETG oder PLA, Düse 0,4, Schicht 0,1–0,12, 100 % Füllung.
Zuerst den Probestreifen (5 Größen, Kerben 1–5 an der Seite) drucken, mit einem Schalter probieren: die kleinste
Nummer, bei der das Beinchen noch ganz hineingeht, ist richtig. Dann 18 Stück dieser Nummer drucken.
Alle Maße in mm.
"""

import cadquery as cq

# ============================================================
# PARAMETER (Schalter laut Angabe/Footprint)
# ============================================================
blade_w, blade_t = 1.5, 0.5     # Schalter-Beinchen (Angabe; PCB-Loch der MX-Norm ist Ø 1,5)
blade_len = 3.3                 # so weit steht das Beinchen unter dem Schalter heraus (MX-Norm)
dupont = 0.64                   # Vierkant-Stift des Jumper-Kabels
dupont_len = 6.0                # so weit ragt der Stift aus seinem Gehäuse
housing = 2.54                  # Kunststoff-Gehäuse des Jumper-Steckers
housing_fit = 0.2

finger_d = 3.4                  # dünner Teil oben (passt zwischen Beinchen und Kunststoffstift)
finger_h = blade_len + 0.4      # so hoch wie das Beinchen + Luft → die breite Buchse bleibt unter Zapfen/Stiften
socket_h = 5.0                  # so tief steckt das Gehäuse
wall = 0.6
slot_w = 1.55                   # Schlitz quer (Beinchen 1,5) – Entwurf 2 mit 1,65 war zu weit
taper = 0.08                    # Schlitz unten so viel enger als oben → Beinchen klemmt beim Hineinschieben
lead = 0.4                      # Einführschräge oben
# Schlitz-Dicke oben (Platz für Stift 0,64 + Beinchen 0,5 = 1,14). Gedruckte Schlitze werden meist ~0,1 enger.
gaps = [0.72, 0.79, 0.86, 0.93, 1.00]   # Entwurf 2 (1,00–1,24) war bei allen Größen zu weit

eps = 0.01


def total_h() -> float:
    # Stift endet 0,5 unter der Oberkante (darf nicht am Schalterboden anstoßen)
    return socket_h + dupont_len + 0.5


def adapter(gap: float = 1.12, mark: int = 0) -> cq.Workplane:
    h = total_h()
    block = housing + housing_fit + 2 * wall
    neck_top = h - finger_h
    guide = dupont + 0.08                     # Führung für den Stift (Stift-Achse bei x = 0, mittig im Gehäuse)
    x0 = -guide / 2                           # Schlitz: −x-Wand = Wand der Stift-Führung
    sc = x0 + gap / 2                         # Schlitz-Mitte = Finger-Mitte (Stift links, Beinchen rechts)
    body = cq.Workplane("XY").rect(block, block).extrude(neck_top).edges("|Z").fillet(0.5)
    body = body.union(cq.Workplane("XY").workplane(offset=neck_top - eps).center(sc, 0).circle(finger_d / 2)
                      .extrude(finger_h + eps))
    body = body.union(cq.Workplane("XY").workplane(offset=neck_top - 1.0).rect(block, block)
                      .workplane(offset=1.0).center(sc, 0).circle(finger_d / 2).loft())   # weicher Übergang
    # Buchse für das Stecker-Gehäuse
    body = body.cut(cq.Workplane("XY").workplane(offset=-eps).rect(housing + housing_fit, housing + housing_fit)
                    .extrude(socket_h + eps))
    # Führung für den Stift vom Gehäuse bis oben
    body = body.cut(cq.Workplane("XY").workplane(offset=socket_h - eps).rect(guide, guide).extrude(h))
    # Schlitz im Finger (unten um „taper“ enger) + Einführschräge
    body = body.cut(cq.Workplane("XY").workplane(offset=neck_top).center(sc + taper / 2, 0)
                    .rect(gap - taper, slot_w - taper).workplane(offset=finger_h - lead).center(-taper / 2, 0)
                    .rect(gap, slot_w).loft())
    body = body.cut(cq.Workplane("XY").workplane(offset=h - lead).center(sc, 0).rect(gap, slot_w)
                    .workplane(offset=lead + eps).rect(gap + 2 * lead, slot_w + 2 * lead).loft())
    # Kerben an der Seite = Größen-Nummer (zum Wiederfinden)
    for i in range(mark):
        body = body.cut(cq.Workplane("XY").workplane(offset=0.8 + i * 0.9).center(block / 2, 0)
                        .rect(0.8, block + 1).extrude(0.4))
    return body


def strip() -> cq.Workplane:
    out = None
    for i, gap in enumerate(gaps):
        p = adapter(gap, i + 1).translate((i * 6.0, 0, 0))
        out = p if out is None else out.union(p)
    return out


def plate(gap: float, n: int = 18, cols: int = 6, pitch: float = 6.0) -> cq.Workplane:
    one = adapter(gap)
    out = None
    for i in range(n):
        p = one.translate(((i % cols) * pitch, (i // cols) * pitch, 0))
        out = p if out is None else out.union(p)
    return out


if __name__ == "__main__":
    import sys

    cq.exporters.export(strip(), "stift_adapter_probe.stl", tolerance=0.005, angularTolerance=0.05)
    nr = int(sys.argv[1]) if len(sys.argv) > 1 else 3   # Größe aus dem Probestreifen (1–5)
    cq.exporters.export(plate(gaps[nr - 1]), f"stift_adapter_18x_nr{nr}.stl", tolerance=0.005, angularTolerance=0.05)
    bb = adapter().val().BoundingBox()
    print(f"Ein Adapter: {bb.xlen:.1f} × {bb.ylen:.1f} × {bb.zlen:.1f} mm, Finger Ø {finger_d} × {finger_h:.1f}")


# ============================================================
# MINI-VARIANTE (Entwurf 3): ohne das Kunststoff-Gehäuse des Jumper-Steckers
# Gehäuse mit einer Nadel abziehen (Rastnase anheben) → nur der Metallstift + Crimp bleiben.
# Dann ist der Adapter nur noch eine winzige Hülse: Stift von unten, Beinchen von oben, beide nebeneinander gepresst.
# ============================================================
mini_wall = 0.5
mini_h = 6.5          # Beinchen 3,3 von oben, Jumper-Stift ~3,2 von unten → ~2,8 mm aneinander
mini_lead = 0.3


def adapter_mini(gap: float = 0.86) -> cq.Workplane:
    w = gap + 2 * mini_wall
    d = slot_w + 2 * mini_wall
    body = cq.Workplane("XY").rect(w, d).extrude(mini_h).edges("|Z").fillet(0.3)
    body = body.cut(cq.Workplane("XY").workplane(offset=-eps).rect(gap - taper, slot_w - taper)
                    .workplane(offset=mini_h / 2 + eps).rect(gap, slot_w).loft())          # unten etwas enger
    body = body.cut(cq.Workplane("XY").workplane(offset=mini_h / 2).rect(gap, slot_w)
                    .workplane(offset=mini_h / 2 + eps).rect(gap, slot_w).loft())
    for z0, sign in ((0, 1), (mini_h, -1)):                                                  # Einführschrägen
        body = body.cut(cq.Workplane("XY").workplane(offset=z0 - sign * eps).rect(gap + 2 * mini_lead, slot_w + 2 * mini_lead)
                        .workplane(offset=sign * (mini_lead + eps)).rect(gap - taper, slot_w - taper).loft())
    return body


def mini_row(gaps_, pitch: float = 5.0) -> cq.Workplane:
    out = None
    for i, g in enumerate(gaps_):
        p = adapter_mini(g).translate((i * pitch, 0, 0))
        out = p if out is None else out.union(p)
    return out


def export_mini(nr: int = 3) -> None:
    cq.exporters.export(mini_row(gaps), "stift_adapter_mini_probe.stl", tolerance=0.003, angularTolerance=0.05)
    one = gaps[nr - 1]
    grid = None
    for i in range(18):
        p = adapter_mini(one).translate(((i % 6) * 5.0, (i // 6) * 5.0, 0))
        grid = p if grid is None else grid.union(p)
    cq.exporters.export(grid, f"stift_adapter_mini_18x_nr{nr}.stl", tolerance=0.003, angularTolerance=0.05)
