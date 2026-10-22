"""AluPC-Tastenbox – Drehknopf für das 10-Gang-Poti (Welle Ø 6 mm, glatt) (CadQuery).

Griffig gerippt, Markierung oben. Hält mit einer M3-Madenschraube (oder M3-Schraube) von der Seite.
Druck: Oberseite nach unten, ohne Stützen. Alle Maße in mm.
"""

import cadquery as cq

knob_d = 24.0
knob_h = 15.0
shaft_d = 6.0          # Welle – NACHMESSEN
shaft_clear = 0.2      # zu stramm → 0,3; zu locker → 0,1
bore_depth = 12.0
skirt_in = 13.0        # unten hohl: Platz für Mutter + Zahnscheibe des Potis (Ø ~ 13 mm) – NACHMESSEN
skirt_h = 3.0
ribs = 24
screw_d = 2.5          # M3 selbstschneidend
screw_z = 6.0

knob = cq.Workplane("XY").circle(knob_d / 2).extrude(knob_h).edges(">Z").fillet(2.0)
for i in range(ribs):  # Griffrillen
    knob = knob.cut(cq.Workplane("XY").transformed(rotate=(0, 0, i * 360 / ribs))
                    .center(knob_d / 2 + 0.3, 0).circle(0.9).extrude(knob_h - 2.5))
knob = knob.cut(cq.Workplane("XY").workplane(offset=-0.01).circle(skirt_in / 2).extrude(skirt_h))
knob = knob.cut(cq.Workplane("XY").workplane(offset=-0.01).circle((shaft_d + shaft_clear) / 2).extrude(bore_depth))
knob = knob.cut(cq.Workplane("YZ").workplane(offset=0).center(0, screw_z).circle(screw_d / 2).extrude(knob_d))
# Markierung oben: Kerbe von der Mitte zum Rand, gegenüber der Schraube
knob = knob.cut(cq.Workplane("XY").workplane(offset=knob_h - 0.8).center(-knob_d / 4 - 1, 0).rect(knob_d / 2 - 2, 1.4)
                .extrude(1))

if __name__ == "__main__":
    cq.exporters.export(knob, "drehknopf.stl", tolerance=0.01, angularTolerance=0.1)
    print("valid", knob.val().isValid(), "Volumen %.0f mm³" % knob.val().Volume())
