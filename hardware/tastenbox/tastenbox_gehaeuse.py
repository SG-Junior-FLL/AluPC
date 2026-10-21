"""AluPC-Tastenbox – Gehäuse zum Drucken (CadQuery). Entwurf 2.

Oberseite von links nach rechts: 9 Tastatur-Schalter (MX, 3 × 3) → Fingerabdrucksensor (Ø 5 mm) → Drehregler
(Platz frei gelassen, Bohrung kommt mit den Maßen) und Zündschloss (Ø 20 mm).

Zwei Teile:
  * Oberteil: abgerundeter Kasten. Druck: Oberseite nach UNTEN aufs Bett (glatte Oberfläche, keine Stützen).
  * Boden: wird von unten eingesteckt und rastet links und rechts mit je einer Federlasche ein, deren Nase seitlich
    aus dem Gehäuse schaut (die „Vorsprünge“). Herausnehmen: beide Nasen eindrücken und am Boden ziehen – die
    Nasen sind unten angeschrägt, mit etwas Kraft geht der Boden auch so heraus. Druck: flach, Laschen nach oben.
    Auf dem Boden: Mulde für die Steckbrett-Wanne (klemme_pro_micro.py, 400 Kontakte), Wanne für den USB-Adapter
    des Fingerabdrucksensors, Ösen für Kabelbinder.
Kabel: USB-C des Pro Micro links seitlich (Fenster), USB-Kabel des Fingerabdruck-Adapters hinten.

Material: PETG empfohlen (die Rastlaschen federn), PLA geht. Alle Maße in mm.
"""

import cadquery as cq

# ============================================================
# PARAMETER
# ============================================================
# Kasten (außen)
box_w = 150.0          # Breite (links–rechts)
box_d = 92.0           # Tiefe (vorne–hinten)
box_h = 60.0           # Höhe – Dupont-Stecker unter den Tasten und auf dem Steckbrett berühren sich nicht; innen 54 mm
corner_r = 10.0
top_edge_r = 4.0
wall = 2.6
top_t = 3.0

# Tastatur-Schalter (Cherry-MX-kompatibel, z. B. Outemu)
key_pitch = 19.05
mx_cut = 14.0
mx_plate_t = 1.5       # Schalter rasten nur bei 1,5 mm Plattendicke ein
mx_relief = 16.2
grid_cx = -42.0        # 3 × 3 links
grid_cy = 0.0

# Fingerabdrucksensor (Ø 5 mm) – Mitte
fp_d = 5.0
fp_clear = 0.3
fp_x, fp_y = 6.0, 0.0

# Rechts: Drehregler (Platz frei, Bohrung folgt) und Zündschloss (Ø 20 mm)
knob_x, knob_y = 46.0, -18.0
lock_d = 20.0
lock_clear = 0.4
lock_x, lock_y = 46.0, 22.0

# Boden
base_t = 3.0
base_clear = 0.3

# Ecksäulen: Anschlag für den Boden (optional zusätzlich M3-Schrauben in Gewindeeinsätze)
boss_od = 9.0
insert_d = 4.0
insert_depth = 6.0
screw_d = 3.4
boss_inset = 8.0

# Rastlaschen (links/rechts) mit Nase durch die Seitenwand
snap_y = 28.0          # Lage entlang der Seite (zwischen Steckbrett-Mulde und Ecksäule)
snap_w = 10.0          # Breite der Lasche
snap_t = 2.0           # Dicke (federt)
snap_len = 30.0        # Länge ab Bodenoberseite – lang = weich, bricht nicht
nose_out = 2.0         # so weit schaut die Nase außen heraus („Vorsprung“)
nose_h = 5.0           # Höhe der Einführschräge
nose_hold = 2.0        # Höhe der Halte-Schräge unten (steil, lässt sich mit Kraft lösen)
slot_clear = 0.4

# Steckbrett-Wanne (aus klemme_pro_micro.py: 88,2 × 60,2 mm) – Mulde im Boden
tray_len = 88.2
tray_w = 60.2
tray_rim_h = 2.0
tray_cx = -25.7        # links, Pro Micro am linken Ende (USB-C zeigt nach links)
tray_cy = -10.7

# USB-C des Pro Micro: Fenster in der linken Seitenwand
usb_win_w = 14.0       # Stecker mit Knickschutz passt durch
usb_win_z0 = 14.0      # über Gehäuseunterkante
usb_win_h = 11.0

# USB-Adapter des Fingerabdrucksensors – NACHMESSEN
ad_len = 30.0
ad_w = 16.0
ad_wall_h = 7.0
ad_x, ad_y = 46.0, -16.0     # rechts vorne, unter dem Regler (Regler ragt nur oben hinein)
ad_cut_x = 30.0              # Kabelausschnitt hinten, offen nach unten
ad_cut_w = 14.0
ad_cut_h = 12.0

# Kabelbinder-Ösen
tie_positions = [(26.0, 0.0), (26.0, 30.0)]

eps = 0.01

# ============================================================
# OBERTEIL
# ============================================================
inner_w = box_w - 2 * wall
inner_d = box_d - 2 * wall

outer = (cq.Workplane("XY").box(box_w, box_d, box_h, centered=(True, True, False))
         .edges("|Z").fillet(corner_r)
         .faces(">Z").edges().fillet(top_edge_r))
inner = (cq.Workplane("XY").workplane(offset=-eps)
         .box(inner_w, inner_d, box_h - top_t + eps, centered=(True, True, False))
         .edges("|Z").fillet(corner_r - wall))
shell = outer.cut(inner)

boss_pts = [(sx * (box_w / 2 - boss_inset), sy * (box_d / 2 - boss_inset)) for sx in (-1, 1) for sy in (-1, 1)]
shell = shell.union(cq.Workplane("XY").workplane(offset=base_t)
                    .pushPoints(boss_pts).circle(boss_od / 2).extrude(box_h - top_t - base_t + eps))
shell = shell.cut(cq.Workplane("XY").workplane(offset=base_t - eps)
                  .pushPoints(boss_pts).circle(insert_d / 2).extrude(insert_depth))

keys = [(grid_cx + (c - 1) * key_pitch, grid_cy + (1 - r) * key_pitch) for r in range(3) for c in range(3)]
shell = shell.cut(cq.Workplane("XY").pushPoints(keys).rect(mx_cut, mx_cut).extrude(box_h + 1))
shell = shell.cut(cq.Workplane("XY").workplane(offset=box_h - top_t - eps)
                  .pushPoints(keys).rect(mx_relief, mx_relief).extrude(top_t - mx_plate_t + eps))

shell = shell.cut(cq.Workplane("XY").pushPoints([(lock_x, lock_y)])
                  .circle((lock_d + lock_clear) / 2).extrude(box_h + 1))
shell = shell.cut(cq.Workplane("XY").pushPoints([(fp_x, fp_y)])
                  .circle((fp_d + fp_clear) / 2).extrude(box_h + 1))

# Schlitze für die Rastnasen (links und rechts)
nose_z = base_t + snap_len - nose_h - nose_hold          # Unterkante der Nase (Boden ganz eingesteckt)
for sx in (-1, 1):
    shell = shell.cut(cq.Workplane("XY").workplane(offset=nose_z - slot_clear)
                      .center(sx * (box_w / 2 - wall / 2), snap_y)
                      .rect(wall * 3, snap_w + 2 * slot_clear).extrude(nose_hold + nose_h + 2 * slot_clear))

# USB-C-Fenster links (Pro Micro am linken Ende des Steckbretts)
shell = shell.cut(cq.Workplane("XY").workplane(offset=usb_win_z0)
                  .center(-(box_w / 2 - wall / 2), tray_cy).rect(wall * 3, usb_win_w).extrude(usb_win_h))
# Kabelausschnitt hinten für den Fingerabdruck-Adapter (offen nach unten)
shell = shell.cut(cq.Workplane("XY").workplane(offset=-eps)
                  .center(ad_cut_x, box_d / 2 - wall / 2).rect(ad_cut_w, wall * 3).extrude(ad_cut_h))

# ============================================================
# BODEN
# ============================================================
bw, bd = inner_w - 2 * base_clear, inner_d - 2 * base_clear
base = (cq.Workplane("XY").box(bw, bd, base_t, centered=(True, True, False))
        .edges("|Z").fillet(corner_r - wall - base_clear))
base = base.cut(cq.Workplane("XY").workplane(offset=-eps).pushPoints(boss_pts).circle(screw_d / 2)
                .extrude(base_t + 2 * eps))

# Rastlaschen: Federzunge an der Bodenkante, oben eine Nase mit Schrägen (Profil in XZ, über die Breite gezogen)
for sx in (-1, 1):
    x_face = inner_w / 2 - 0.2                      # Außenseite der Zunge, knapp an der Wand
    tongue = (cq.Workplane("XY").workplane(offset=base_t - eps)
              .center(sx * (x_face - snap_t / 2), snap_y).rect(snap_t, snap_w).extrude(snap_len + eps))
    x_out = box_w / 2 + nose_out
    profile = [(x_face - snap_t, nose_z - 0.01), (x_face, nose_z - 0.01),   # Fuß an der Zunge
               (x_out, nose_z + nose_hold), (x_out, nose_z + nose_hold + 1.0),
               (x_face, nose_z + nose_hold + nose_h), (x_face - snap_t, nose_z + nose_hold + nose_h)]
    pts = [(sx * x, z) for x, z in profile]
    nose = (cq.Workplane("XZ", origin=(0, snap_y + snap_w / 2, 0)).polyline(pts).close().extrude(snap_w))
    base = base.union(tongue).union(nose)

# Mulde (Rand) für die Steckbrett-Wanne
rim_in_l, rim_in_w = tray_len + 0.6, tray_w + 0.6
rim = (cq.Workplane("XY").workplane(offset=base_t).center(tray_cx, tray_cy)
       .rect(rim_in_l + 4.0, rim_in_w + 4.0).extrude(tray_rim_h)
       .cut(cq.Workplane("XY").workplane(offset=base_t - eps).center(tray_cx, tray_cy)
            .rect(rim_in_l, rim_in_w).extrude(tray_rim_h + 2 * eps)))
footprint = (cq.Workplane("XY").box(bw, bd, base_t + tray_rim_h + 1, centered=(True, True, False))
             .edges("|Z").fillet(corner_r - wall - base_clear))
rim = rim.intersect(footprint)  # an den runden Ecken nichts überstehen lassen
rim = rim.cut(cq.Workplane("XY").pushPoints(boss_pts).circle(boss_od / 2 + 0.5).extrude(base_t + tray_rim_h + 1))
base = base.union(rim)

# Wanne für den USB-Adapter des Fingerabdrucksensors (Kabelseite offen, zeigt nach hinten)
cradle = (cq.Workplane("XY").workplane(offset=base_t).center(ad_x, ad_y)
          .rect(ad_w + 0.6 + 4.0, ad_len + 2.0).extrude(ad_wall_h)
          .cut(cq.Workplane("XY").workplane(offset=base_t - eps).center(ad_x, ad_y + 1.0)
               .rect(ad_w + 0.6, ad_len + 2.0).extrude(ad_wall_h + 2 * eps)))
base = base.union(cradle)

for tx, ty in tie_positions:
    eye = (cq.Workplane("XY").workplane(offset=base_t).center(tx, ty).rect(8.0, 4.0).extrude(4.0)
           .cut(cq.Workplane("XY").workplane(offset=base_t - eps).center(tx, ty).rect(4.5, 5.0).extrude(2.2)))
    base = base.union(eye)

# ============================================================
# EXPORT
# ============================================================
cq.exporters.export(shell, "tastenbox_oberteil.stl", tolerance=0.01, angularTolerance=0.1)
cq.exporters.export(base, "tastenbox_boden.stl", tolerance=0.01, angularTolerance=0.1)
cq.exporters.export(shell, "tastenbox_oberteil.step")
cq.exporters.export(base, "tastenbox_boden.step")
cq.exporters.export(shell.union(base), "tastenbox_zusammen.stl", tolerance=0.01, angularTolerance=0.1)
print(f"Oberteil {box_w} × {box_d} × {box_h} mm · Boden {bw:.1f} × {bd:.1f} mm · Nasen bei z={nose_z:.1f} mm, "
      f"stehen {nose_out} mm über")
