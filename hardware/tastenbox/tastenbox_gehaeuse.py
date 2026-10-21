"""AluPC-Tastenbox – Gehäuse zum Drucken (CadQuery). Entwurf 1.

Zwei Teile:
  * Oberteil: abgerundeter Kasten, oben 9 Tastatur-Schalter (MX, 3 × 3), Loch fürs Zündschloss (Ø 20 mm),
    Loch für den Fingerabdrucksensor (Ø 5 mm). Platz für den Drehregler ist frei gelassen (Maße kommen noch).
    Druckrichtung: Oberseite nach UNTEN aufs Bett (schöne, glatte Oberfläche, keine Stützen nötig).
  * Boden: Platte mit Halterung für den Pro Micro (Platine schiebt sich in Nuten, USB-C zeigt nach hinten),
    Halterung für den kleinen USB-Adapter des Fingerabdrucksensors, zwei Ösen für Kabelbinder.
    Druckrichtung: flach, Halterungen nach oben.
Zusammenbau: 4 Schrauben M3 × 8 von unten in Gewindeeinsätze (M3, Ø 4 mm) in den Ecksäulen.
Hinten zwei Kabelausschnitte (offen nach unten): USB-C vom Pro Micro und USB-Kabel vom Fingerabdruck-Adapter.

Alle Maße in mm. Nachmessen: Pro Micro, USB-Adapter, Zündschloss-Tiefe – dann oben anpassen.
"""

import cadquery as cq

# ============================================================
# PARAMETER
# ============================================================
# Kasten (außen)
box_w = 150.0          # Breite (links–rechts)
box_d = 92.0           # Tiefe (vorne–hinten)
box_h = 50.0           # Höhe mit Boden – genug Platz hinterm Zündschloss (innen ~44 mm)
corner_r = 10.0        # Rundung der senkrechten Kanten
top_edge_r = 4.0       # Rundung der oberen Kante
wall = 2.6             # Wandstärke
top_t = 3.0            # Dicke der Deckplatte

# Tastatur-Schalter (Cherry-MX-kompatibel)
key_pitch = 19.05      # Abstand Mitte–Mitte (Standard-Tastenkappen)
mx_cut = 14.0          # Ausschnitt im Plattenbereich (MX-Norm 14,0 × 14,0)
mx_plate_t = 1.5       # Schalter rasten nur bei 1,5 mm Plattendicke ein
mx_relief = 16.2       # von unten auf 1,5 mm ausgedünnte Fläche je Schalter
grid_cx = -32.0        # Mitte des 3 × 3-Feldes (x)
grid_cy = 0.0

# Zündschloss (Bohrung laut Angabe Ø 20 mm) – Mutter von innen
lock_d = 20.0
lock_clear = 0.4       # Spiel
lock_x, lock_y = 42.0, 20.0

# Fingerabdrucksensor (laut Angabe Ø 5 mm)
fp_d = 5.0
fp_clear = 0.3
fp_x, fp_y = 15.0, 26.0

# Drehregler: Platz freigehalten, Bohrung kommt später (Maße morgen)
knob_x, knob_y = 42.0, -22.0
knob_keepout_d = 32.0  # hier keine Stützen/Halterungen innen

# Boden
base_t = 3.0
base_clear = 0.3       # Spiel Boden ↔ Wand innen

# Schrauben / Ecksäulen
boss_od = 9.0
insert_d = 4.0         # Loch für Gewindeeinsatz M3 (Ø 4,0)
insert_depth = 6.0
screw_d = 3.4          # Durchgang M3 im Boden
screw_head_d = 6.2     # Senkung für den Kopf
screw_head_depth = 2.0
boss_inset = 8.0       # Säulenmitte von der Außenkante

# Pro Micro (USB-C-Nachbau ca. 33–34 × 18 mm, Platine 1,6 mm) – NACHMESSEN
pm_len = 34.0
pm_w = 18.0
pm_pcb_t = 1.6
pm_fit = 0.4           # Spiel in der Nut
pm_rail_h = 6.0        # Höhe der Seitenwände
pm_groove_z = 2.5      # Platine liegt so hoch über dem Boden (Platz für Bauteile unten)
pm_lip = 1.2           # wie weit die Wände über die Platine greifen
pm_x = -40.0           # Lage auf dem Boden (USB-Ende zeigt nach hinten, +y)
usb_cut_w = 13.0       # Kabelausschnitt hinten (Stecker mit Knickschutz passt durch)
usb_cut_h = 12.0

# USB-Adapter des Fingerabdrucksensors – NACHMESSEN
ad_len = 30.0
ad_w = 16.0
ad_wall_h = 7.0
ad_x = 12.0
ad_cut_w = 14.0        # zweiter Kabelausschnitt hinten
ad_cut_h = 12.0

# Kabelbinder-Ösen
tie_positions = [(-5.0, -20.0), (25.0, -20.0)]

eps = 0.01

# ============================================================
# OBERTEIL
# ============================================================
inner_w = box_w - 2 * wall
inner_d = box_d - 2 * wall
shell_h = box_h  # Oberteil reicht bis z = 0 (Boden sitzt innen zwischen den Wänden)

outer = (cq.Workplane("XY").box(box_w, box_d, shell_h, centered=(True, True, False))
         .edges("|Z").fillet(corner_r)
         .faces(">Z").edges().fillet(top_edge_r))
inner = (cq.Workplane("XY").workplane(offset=-eps)
         .box(inner_w, inner_d, shell_h - top_t + eps, centered=(True, True, False))
         .edges("|Z").fillet(corner_r - wall))
shell = outer.cut(inner)

# Ecksäulen (bis zur Unterkante des Bodens, damit der Boden innen anliegt)
boss_pts = [(sx * (box_w / 2 - boss_inset), sy * (box_d / 2 - boss_inset)) for sx in (-1, 1) for sy in (-1, 1)]
bosses = (cq.Workplane("XY").workplane(offset=base_t)
          .pushPoints(boss_pts).circle(boss_od / 2).extrude(shell_h - top_t - base_t + eps))
shell = shell.union(bosses)
shell = shell.cut(cq.Workplane("XY").workplane(offset=base_t - eps)
                  .pushPoints(boss_pts).circle(insert_d / 2).extrude(insert_depth))

# 3 × 3 Schalter: Ausschnitt durch, von unten auf 1,5 mm ausgedünnt
keys = [(grid_cx + (c - 1) * key_pitch, grid_cy + (1 - r) * key_pitch) for r in range(3) for c in range(3)]
shell = shell.cut(cq.Workplane("XY").pushPoints(keys).rect(mx_cut, mx_cut).extrude(box_h + 1))
shell = shell.cut(cq.Workplane("XY").workplane(offset=box_h - top_t - eps)
                  .pushPoints(keys).rect(mx_relief, mx_relief).extrude(top_t - mx_plate_t + eps))

# Zündschloss und Fingerabdrucksensor
shell = shell.cut(cq.Workplane("XY").pushPoints([(lock_x, lock_y)])
                  .circle((lock_d + lock_clear) / 2).extrude(box_h + 1))
shell = shell.cut(cq.Workplane("XY").pushPoints([(fp_x, fp_y)])
                  .circle((fp_d + fp_clear) / 2).extrude(box_h + 1))

# Kabelausschnitte hinten (+y), offen nach unten
cut_y = box_d / 2 - wall / 2
for cx, w_, h_ in ((pm_x, usb_cut_w, usb_cut_h), (ad_x, ad_cut_w, ad_cut_h)):
    shell = shell.cut(cq.Workplane("XY").workplane(offset=-eps)
                      .center(cx, cut_y).rect(w_, wall * 3).extrude(h_))

# ============================================================
# BODEN
# ============================================================
base = (cq.Workplane("XY")
        .box(inner_w - 2 * base_clear, inner_d - 2 * base_clear, base_t, centered=(True, True, False))
        .edges("|Z").fillet(corner_r - wall - base_clear))
# Aussparungen um die Ecksäulen? Nein: Säulen enden auf dem Boden (z = base_t). Schraublöcher mit Senkung:
base = base.cut(cq.Workplane("XY").workplane(offset=-eps).pushPoints(boss_pts).circle(screw_d / 2)
                .extrude(base_t + 2 * eps))
base = base.cut(cq.Workplane("XY").workplane(offset=-eps).pushPoints(boss_pts).circle(screw_head_d / 2)
                .extrude(screw_head_depth))

# Pro-Micro-Halterung: U-Form, Platine schiebt sich von hinten in die Nut, USB-C an der offenen Seite
slot_w = pm_w + pm_fit
holder_w = slot_w + 2 * 2.0
holder_len = pm_len + 2.0
pm_back = inner_d / 2 - base_clear - 1.5          # offene Seite kurz vor der Rückwand
pm_cy = pm_back - holder_len / 2
holder = (cq.Workplane("XY").workplane(offset=base_t)
          .center(pm_x, pm_cy).rect(holder_w, holder_len).extrude(pm_rail_h))
# Innenraum (unter der Platine schmaler: Platine liegt auf Leisten), Nut für die Platine
holder = holder.cut(cq.Workplane("XY").workplane(offset=base_t)
                    .center(pm_x, pm_cy + 1.0).rect(slot_w - 2 * pm_lip, holder_len).extrude(pm_rail_h + eps))
holder = holder.cut(cq.Workplane("XY").workplane(offset=base_t + pm_groove_z)
                    .center(pm_x, pm_cy + 1.0).rect(slot_w, holder_len).extrude(pm_pcb_t + pm_fit))
base = base.union(holder)

# Halterung USB-Adapter (Fingerabdruck): Wanne, hinten offen fürs Kabel
ad_back = inner_d / 2 - base_clear - 1.5
ad_cy = ad_back - (ad_len + 2.0) / 2
cradle = (cq.Workplane("XY").workplane(offset=base_t)
          .center(ad_x, ad_cy).rect(ad_w + 0.6 + 4.0, ad_len + 2.0).extrude(ad_wall_h))
cradle = cradle.cut(cq.Workplane("XY").workplane(offset=base_t)
                    .center(ad_x, ad_cy + 1.0).rect(ad_w + 0.6, ad_len + 2.0).extrude(ad_wall_h + eps))
base = base.union(cradle)

# Kabelbinder-Ösen (Brücke mit Durchgang 4 × 2 mm)
for tx, ty in tie_positions:
    eye = (cq.Workplane("XY").workplane(offset=base_t).center(tx, ty).rect(8.0, 4.0).extrude(4.0)
           .cut(cq.Workplane("XY").workplane(offset=base_t - eps).center(tx, ty).rect(4.5, 4.0 + 1).extrude(2.2)))
    base = base.union(eye)

# ============================================================
# EXPORT
# ============================================================
cq.exporters.export(shell, "tastenbox_oberteil.stl", tolerance=0.01, angularTolerance=0.1)
cq.exporters.export(base, "tastenbox_boden.stl", tolerance=0.01, angularTolerance=0.1)
cq.exporters.export(shell, "tastenbox_oberteil.step")
cq.exporters.export(base, "tastenbox_boden.step")
# zusammengebaut (nur zum Ansehen)
cq.exporters.export(shell.union(base), "tastenbox_zusammen.stl", tolerance=0.01, angularTolerance=0.1)
print(f"Oberteil {box_w} × {box_d} × {box_h} mm, Boden {inner_w - 2 * base_clear:.1f} × "
      f"{inner_d - 2 * base_clear:.1f} × {base_t} mm, Innenhöhe {box_h - top_t - base_t:.1f} mm")
