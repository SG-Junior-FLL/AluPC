"""AluPC-Tastenbox – Tastenkappe für die Schalter (Outemu, MX-kompatibel: Kreuz-Stiel „+“) (CadQuery).

1u-Kappe (Raster 19,05 mm), flach-zylindrisch wie DSA, leicht gemuldet oben, abgerundete Kanten.
Unten: runder Stiel mit Kreuzloch für den Schalter. Kreuz hat drei Passungen (eng/mittel/locker) –
erst „mittel“ drucken, ausprobieren: wackelt sie → eng, geht sie nicht drauf → locker.

Druck: Oberseite NACH UNTEN aufs Bett (Kreuzloch zeigt nach oben → wird sauber, keine Stützen).
0,12–0,16 mm Schichthöhe, 100 % Füllung für den Stiel (oder 4 Wände). PLA oder PETG.
Dateien: tastenkappe_{eng,mittel,locker}.stl (leer) und tastenkappe_1 … _9.stl (Ziffer vertieft, Passung mittel).
Ziffern: vertieft 0,6 mm – nach dem Druck mit Farbe/Acrylstift ausfüllen, oder Filamentwechsel bei 0,6 mm.
Alle Maße in mm.
"""

import cadquery as cq

# ============================================================
# PARAMETER
# ============================================================
base = 18.0            # unten (Raster 19,05 → 1 mm Luft zur Nachbartaste)
top = 13.5             # oben
height = 7.6           # Gesamthöhe (wie DSA)
wall = 1.4             # Seitenwand
roof = 2.0             # Deckel über dem Stiel (unter der Ziffer bleiben 0,8 mm)
dish = 0.6             # Mulde oben (Kugel), 0 = flach
edge_r = 1.6           # Rundung der senkrechten Kanten
stem_d = 5.5           # runder Stiel (MX-Norm 5,5 – taucht beim Drücken ins Schaltergehäuse)
cross_l = {"eng": 4.05, "mittel": 4.12, "locker": 4.2}     # Kreuz-Arm-Länge (Schalter: 4,0)
cross_w = {"eng": 1.30, "mittel": 1.36, "locker": 1.44}    # Kreuz-Arm-Breite (Schalter: ~1,2–1,3)
cross_depth = 4.0      # wie tief der Schalterstiel hineingeht
chamfer = 0.3          # Fase am Kreuz-Eingang
digit_depth = 0.6
digit_size = 7.0


def body() -> cq.Workplane:
    outer = cq.Workplane("XY").rect(base, base).workplane(offset=height).rect(top, top).loft()
    outer = outer.edges("not(<Z or >Z)").fillet(edge_r).edges(">Z").fillet(0.8)  # Ecken rund, Oberkante weich
    inner_h = height - roof
    shrink = (base - top) / height * inner_h  # Wand folgt der Schräge
    inner = (cq.Workplane("XY").rect(base - 2 * wall, base - 2 * wall).workplane(offset=inner_h)
             .rect(base - 2 * wall - shrink, base - 2 * wall - shrink).loft())
    cap = outer.cut(inner)
    if dish > 0:  # Kugelmulde: Radius so, dass sie über die Oberseite genau dish tief ist
        r = ((top / 2) ** 2 + dish ** 2) / (2 * dish) * 1.6
        cap = cap.cut(cq.Workplane("XY").sphere(r).translate((0, 0, height + r - dish)))
    return cap


def stem(fit: str) -> cq.Workplane:
    h = height - roof
    s = cq.Workplane("XY").circle(stem_d / 2).extrude(h + 0.2)
    cl, cw = cross_l[fit], cross_w[fit]
    cross = (cq.Workplane("XY").rect(cl, cw).extrude(cross_depth)
             .union(cq.Workplane("XY").rect(cw, cl).extrude(cross_depth)))
    s = s.cut(cross)
    # Fase am Eingang: Pyramidenstumpf je Arm
    lead = (cq.Workplane("XY").rect(cl + 2 * chamfer, cw + 2 * chamfer).workplane(offset=chamfer).rect(cl, cw).loft()
            .union(cq.Workplane("XY").rect(cw + 2 * chamfer, cl + 2 * chamfer).workplane(offset=chamfer)
                   .rect(cw, cl).loft()))
    return s.cut(lead)


def keycap(fit: str = "mittel", digit: str = "") -> cq.Workplane:
    cap = body().union(stem(fit))
    if digit:
        txt = (cq.Workplane("XY").workplane(offset=height - dish - digit_depth)
               .text(digit, digit_size, digit_depth + dish + 1, kind="bold", halign="center", valign="center"))
        cap = cap.cut(txt)
    return cap


if __name__ == "__main__":
    for fit in cross_l:
        cq.exporters.export(keycap(fit), f"tastenkappe_{fit}.stl", tolerance=0.01, angularTolerance=0.1)
    for n in range(1, 10):
        cq.exporters.export(keycap("mittel", str(n)), f"tastenkappe_{n}.stl", tolerance=0.01, angularTolerance=0.1)
    cq.exporters.export(keycap("mittel"), "tastenkappe_mittel.step")
