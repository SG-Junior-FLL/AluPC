"""AluPC-Tastenbox – Stift-Adapter: flaches Schalter-Beinchen (Outemu, ca. 1,5 × 0,5 mm) ↔ Dupont-Stecker (CadQuery).

Ohne Löten: Unten steckt man ein normales Jumper-Kabel (Stecker, Kunststoff-Gehäuse 2,5 × 2,5 mm) hinein, oben das
Schalter-Beinchen. Beide Metallteile liegen im selben Schlitz nebeneinander, eine federnde Zunge drückt sie
zusammen → Kontakt. 18 Stück: je Schalter 2 Beinchen.

    oben:  Schlitz mit Einführschräge für das Schalter-Beinchen
           [Wand] [Dupont-Stift | Beinchen] [Feder-Zunge] [Luft] [Wand]
    unten: viereckige Buchse für das Kunststoff-Gehäuse des Jumper-Kabels

Druck: stehend, Buchse unten auf dem Bett, ohne Stützen. PETG (federt besser) oder PLA, Düse 0,4, Schicht 0,12–0,16,
100 % Füllung. Zuerst die drei Probestücke eng/mittel/locker drucken und mit einem echten Schalter probieren:
   Beinchen geht nicht rein → locker · wackelt / kein Kontakt → eng.
Prüfen: Durchgangsprüfer (Piepser) zwischen Jumper-Stift und Beinchen, dabei leicht am Kabel wackeln.
Alle Maße in mm.
"""

import cadquery as cq

# ============================================================
# PARAMETER
# ============================================================
blade_w, blade_t = 1.5, 0.5     # Schalter-Beinchen (Angabe)
dupont = 0.64                   # Vierkant-Stift des Jumper-Kabels
housing = 2.5                   # Kunststoff-Gehäuse des Jumper-Steckers
housing_fit = 0.2               # Luft am Gehäuse (klemmt leicht)
socket_h = 6.0                  # so tief steckt das Gehäuse
slot_h = 7.0                    # Schlitz über der Buchse (Dupont-Stift ragt ~6 mm aus seinem Gehäuse)
slot_w = 2.0                    # Schlitzbreite (Beinchen 1,5 + Luft)
wall = 1.0
tongue_t = 0.9                  # Feder-Zunge (Dicke)
flex_gap = 0.6                  # Luft hinter der Zunge zum Ausweichen
slit = 0.6                      # Schlitze links/rechts der Zunge (Düse 0,4 → 0,6 bleibt offen)
lead = 0.6                      # Einführschräge oben
# Schlitz-Dicke = Platz für Dupont-Stift + Beinchen. Kleiner als 0,64 + 0,5 = 1,14 → Zunge muss federn = Druck.
gaps = {"eng": 0.95, "mittel": 1.02, "locker": 1.10}

eps = 0.01


def adapter(fit: str = "mittel") -> cq.Workplane:
    gap = gaps[fit]
    x_wall = -dupont / 2 - 0.05               # feste Schlitzwand (Dupont-Stift liegt daran an)
    x_tongue = x_wall + gap                   # Zungen-Innenseite
    x_back = x_tongue + tongue_t + flex_gap   # Ende der Luft hinter der Zunge
    sock = housing + housing_fit
    x0 = min(-sock / 2 - wall, x_wall - wall)
    x1 = x_back + wall
    tw = slot_w                                # Zungenbreite = Schlitzbreite
    y_half = tw / 2 + slit + wall
    h = socket_h + slot_h
    body = cq.Workplane("XY").center((x0 + x1) / 2, 0).rect(x1 - x0, 2 * y_half).extrude(h)
    body = body.edges("|Z").fillet(0.6)
    # Buchse unten für das Stecker-Gehäuse (Stift sitzt mittig bei x = 0)
    body = body.cut(cq.Workplane("XY").workplane(offset=-eps).rect(sock, sock).extrude(socket_h + eps))
    # Schlitz für beide Metallteile, durch bis oben
    body = body.cut(cq.Workplane("XY").workplane(offset=socket_h - eps).center((x_wall + x_tongue) / 2, 0)
                    .rect(gap, slot_w).extrude(slot_h + 2 * eps))
    # Luft hinter der Zunge + Schlitze links/rechts: Zunge hängt nur unten am Körper und federt nach außen
    z_free = socket_h + 1.2
    body = body.cut(cq.Workplane("XY").workplane(offset=z_free).center(x_tongue + tongue_t + flex_gap / 2, 0)
                    .rect(flex_gap, tw + 2 * slit).extrude(h))
    for sy in (-1, 1):  # Schlitze vom Schlitz bis hinter die Zunge – sonst hängt die Zunge seitlich fest
        body = body.cut(cq.Workplane("XY").workplane(offset=z_free).center((x_wall + x_back) / 2, sy * (tw / 2 + slit / 2))
                        .rect(x_back - x_wall, slit).extrude(h))
    # Einführschräge oben (Trichter)
    body = body.cut(cq.Workplane("XY").workplane(offset=h - lead).center((x_wall + x_tongue) / 2, 0)
                    .rect(gap, slot_w).workplane(offset=lead + eps).rect(gap + 2 * lead, slot_w + 2 * lead)
                    .loft())
    return body


def plate(fit: str = "mittel", n: int = 18, cols: int = 6, pitch: float = 9.0) -> cq.Workplane:
    one = adapter(fit)
    out = None
    for i in range(n):
        p = one.translate(((i % cols) * pitch, (i // cols) * pitch, 0))
        out = p if out is None else out.union(p)
    return out


if __name__ == "__main__":
    for fit in gaps:
        cq.exporters.export(adapter(fit), f"stift_adapter_{fit}.stl", tolerance=0.005, angularTolerance=0.05)
    cq.exporters.export(plate("mittel"), "stift_adapter_18x.stl", tolerance=0.005, angularTolerance=0.05)
    bb = adapter().val().BoundingBox()
    print(f"Ein Adapter: {bb.xlen:.1f} × {bb.ylen:.1f} × {bb.zlen:.1f} mm")
