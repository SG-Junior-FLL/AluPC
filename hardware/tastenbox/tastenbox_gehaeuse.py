"""AluPC-Tastenbox – Einbau-Gehäuse für ein Loch in einer Holzplatte (CadQuery). Entwurf 3.

Flach: nur so hoch wie nötig (Dupont-Stecker ~14 mm stehen senkrecht auf Steckbrett und Tasten).
In der Mitte der Höhe läuft ein dünner Rand (Flansch) rundum 10 mm über – er liegt auf der Holzplatte auf,
die obere Hälfte der Box schaut heraus. In jeder Ecke ein Loch für eine 5-mm-LED.

Oberseite von links nach rechts: 9 Tastatur-Schalter (MX, 3 × 3) → Steckbrett darunter → rechte Spalte mit
Zündschloss (hinten), Fingerabdrucksensor Ø 17 mm (Mitte) und Drehregler (vorne, Bohrung folgt mit den Maßen).

Zwei Teile:
  * Oberteil mit Flansch. Druck: Oberseite nach UNTEN aufs Bett; Stützen NUR unter dem Rand
    (Baumstützen, „nur am Druckbett“) – lassen sich leicht abbrechen.
  * Boden: wird von unten eingesteckt, rastet mit zwei Federlaschen ein (Nasen bündig in Schlitzen der
    Seitenwand – nichts steht über, die Box passt ins Loch). Lösen: Nasen von außen eindrücken, Boden ziehen.
    Auf dem Boden: Rahmen fürs Steckbrett (400 Kontakte) mit Rastleiste für den Bügel aus klemme_pro_micro.py,
    Wanne für den USB-Adapter des Fingerabdrucksensors, Loch unter dem Zündschloss (falls es länger ist).
Kabel: USB-C des Pro Micro hinten (Fenster), USB-Kabel des Fingerabdruck-Adapters hinten (Ausschnitt).
Material: PETG empfohlen (Laschen federn). Alle Maße in mm.
"""

import cadquery as cq

# ============================================================
# PARAMETER
# ============================================================
box_h = 32.0           # Gesamthöhe ohne Flansch-Überstand (innen 26 mm) – Minimum mit Steckbrett + Dupont
wall = 2.4
top_t = 3.0
corner_r = 8.0
flange = 10.0          # Rand rundum über die Box hinaus
flange_t = 2.5         # Dicke des Randes
flange_z = 16.0        # Höhe der Rand-Mitte über der Unterkante: darüber schaut die Box aus der Holzplatte
flange_edge_r = 1.2    # Kanten am Rand gerundet
top_r = 3.0            # obere Kante der Box gerundet (steht über die Holzplatte)

# LEDs in den 4 Ecken (5 mm, stecken von unten im Loch)
led_d = 5.2
led_inset = 7.0        # Abstand der Loch-Mitte von den Außenkanten

# Tastatur-Schalter (MX-kompatibel, z. B. Outemu)
key_pitch = 19.05
mx_cut = 14.0
mx_plate_t = 1.5
mx_relief = 16.2

# Steckbrett 400 Kontakte (längs nach hinten), Rahmen wie die Wanne der Klemme
bb_len = 83.0
bb_w = 55.0
bb_clear = 0.6
rim_wall = 2.0
rim_h = 6.0            # Rahmenhöhe über dem Boden (wie Wanne der Klemme ohne deren Boden)
lip_out = 1.2
lip_h = 1.6

# Rechte Spalte
col_w = 30.0
lock_d = 20.0
lock_clear = 0.4
lock_hole_base_d = 26.0  # Loch im Boden unter dem Schloss (längeres Schloss darf unten herausschauen)
fp_d = 17.0            # Fingerabdrucksensor Ø 17 mm (Angabe)
fp_clear = 0.3
lock_dy, fp_dy, knob_dy = 28.0, 0.0, -28.0   # Lage in der Spalte (hinten / Mitte / vorne)

# Abstände zwischen den Bereichen
gap = 3.0
key_margin = 4.0       # Abstand der Tasten von der linken Wand (Platz für die Rastlasche)

# Boden
base_t = 3.0
base_clear = 0.3

# Rastlaschen (links und rechts, Mitte der Seite), Nase bündig in einem Schlitz
snap_w = 10.0
snap_t = 2.0
snap_len = 18.0
nose_h = 4.0           # Einführschräge
nose_hold = 1.5        # Halteschräge
slot_clear = 0.4

# USB-Adapter des Fingerabdrucksensors – NACHMESSEN
ad_len = 30.0
ad_w = 16.0
ad_wall_h = 7.0

# Kabelausschnitte hinten
usb_win_w = 14.0       # Pro Micro USB-C
usb_win_h = 11.0
ad_cut_w = 14.0        # Adapter-Kabel, offen nach unten
ad_cut_h = 12.0

eps = 0.01

# ============================================================
# ABGELEITETE MASSE / LAGE
# ============================================================
keys_w = 2 * key_pitch + mx_relief
rim_in_w, rim_in_l = bb_w + 2 * bb_clear, bb_len + 2 * bb_clear
rim_out_w, rim_out_l = rim_in_w + 2 * rim_wall, rim_in_l + 2 * rim_wall
inner_w = key_margin + keys_w + gap + rim_out_w + 2 * lip_out + gap + col_w
inner_d = rim_out_l + 2.0
box_w = inner_w + 2 * wall
box_d = inner_d + 2 * wall
x0 = -inner_w / 2                                   # linke Innenwand
grid_cx = x0 + key_margin + keys_w / 2
bb_cx = x0 + key_margin + keys_w + gap + lip_out + rim_out_w / 2
col_cx = inner_w / 2 - col_w / 2 - 1.0
lock_x = fp_x = knob_x = col_cx
ad_x, ad_y = col_cx - 2.0, fp_dy

# ============================================================
# OBERTEIL
# ============================================================
body = (cq.Workplane("XY").box(box_w, box_d, box_h, centered=(True, True, False)).edges("|Z").fillet(corner_r)
        .faces(">Z").edges().fillet(top_r))
rim_top = (cq.Workplane("XY").workplane(offset=flange_z - flange_t / 2)
           .rect(box_w + 2 * flange, box_d + 2 * flange).extrude(flange_t)
           .edges("|Z").fillet(corner_r + flange)
           .edges("not |Z").fillet(flange_edge_r))
shell = body.union(rim_top)
shell = shell.cut(cq.Workplane("XY").workplane(offset=-eps)
                  .box(inner_w, inner_d, box_h - top_t + eps, centered=(True, True, False))
                  .edges("|Z").fillet(corner_r - wall))

keys = [(grid_cx + (c - 1) * key_pitch, (1 - r) * key_pitch) for r in range(3) for c in range(3)]
shell = shell.cut(cq.Workplane("XY").pushPoints(keys).rect(mx_cut, mx_cut).extrude(box_h + 1))
shell = shell.cut(cq.Workplane("XY").workplane(offset=box_h - top_t - eps)
                  .pushPoints(keys).rect(mx_relief, mx_relief).extrude(top_t - mx_plate_t + eps))
shell = shell.cut(cq.Workplane("XY").pushPoints([(lock_x, lock_dy)])
                  .circle((lock_d + lock_clear) / 2).extrude(box_h + 1))
leds = [(sx * (box_w / 2 - led_inset), sy * (box_d / 2 - led_inset)) for sx in (-1, 1) for sy in (-1, 1)]
shell = shell.cut(cq.Workplane("XY").pushPoints(leds).circle(led_d / 2).extrude(box_h + 1))
shell = shell.cut(cq.Workplane("XY").pushPoints([(fp_x, fp_dy)])
                  .circle((fp_d + fp_clear) / 2).extrude(box_h + 1))

nose_z = base_t + snap_len - nose_h - nose_hold
for sx in (-1, 1):
    shell = shell.cut(cq.Workplane("XY").workplane(offset=nose_z - slot_clear)
                      .center(sx * (box_w / 2 - wall / 2), 0)
                      .rect(wall * 3, snap_w + 2 * slot_clear).extrude(nose_hold + nose_h + 2 * slot_clear))

# Pro Micro steckt am hinteren Ende des Steckbretts, USB-C zeigt nach hinten
usb_z = base_t + 8.5 + 2.5 + 1.6 + 1.6               # Mitte USB-C über dem Boden
shell = shell.cut(cq.Workplane("XY").workplane(offset=usb_z - usb_win_h / 2)
                  .center(bb_cx, box_d / 2 - wall / 2).rect(usb_win_w, wall * 3).extrude(usb_win_h))
shell = shell.cut(cq.Workplane("XY").workplane(offset=-eps)
                  .center(ad_x, box_d / 2 - wall / 2).rect(ad_cut_w, wall * 3).extrude(ad_cut_h))

# ============================================================
# BODEN
# ============================================================
bw, bd = inner_w - 2 * base_clear, inner_d - 2 * base_clear
base = (cq.Workplane("XY").box(bw, bd, base_t, centered=(True, True, False))
        .edges("|Z").fillet(corner_r - wall - base_clear))
base = base.cut(cq.Workplane("XY").workplane(offset=-eps).center(lock_x, lock_dy)
                .circle(lock_hole_base_d / 2).extrude(base_t + 2 * eps))

for sx in (-1, 1):
    x_face = inner_w / 2 - 0.2
    base = base.union(cq.Workplane("XY").workplane(offset=base_t - eps)
                      .center(sx * (x_face - snap_t / 2), 0).rect(snap_t, snap_w).extrude(snap_len + eps))
    x_out = box_w / 2 - 0.3                         # Nase endet knapp vor der Außenfläche: nichts steht über
    profile = [(x_face - snap_t, nose_z - 0.01), (x_face, nose_z - 0.01), (x_out, nose_z + nose_hold),
               (x_out, nose_z + nose_hold + 0.8), (x_face, nose_z + nose_hold + nose_h),
               (x_face - snap_t, nose_z + nose_hold + nose_h)]
    base = base.union(cq.Workplane("XZ", origin=(0, snap_w / 2, 0))
                      .polyline([(sx * x, z) for x, z in profile]).close().extrude(snap_w))

# Steckbrett-Rahmen mit Rastleiste (gleiche Maße wie die Wanne der Klemme → derselbe Bügel passt)
frame = (cq.Workplane("XY").workplane(offset=base_t).center(bb_cx, 0)
         .rect(rim_out_w, rim_out_l).extrude(rim_h)
         .cut(cq.Workplane("XY").workplane(offset=base_t - eps).center(bb_cx, 0)
              .rect(rim_in_w, rim_in_l).extrude(rim_h + 2 * eps)))
for s in (-1, 1):
    frame = frame.union(cq.Workplane("XY").workplane(offset=base_t + rim_h - lip_h)
                        .center(bb_cx + s * (rim_out_w / 2 + lip_out / 2), 0)
                        .rect(lip_out, rim_out_l - 8).extrude(lip_h))
base = base.union(frame)

# Wanne für den USB-Adapter (unter dem Fingerabdrucksensor, Kabelseite hinten offen)
cradle = (cq.Workplane("XY").workplane(offset=base_t).center(ad_x, ad_y)
          .rect(ad_w + 0.6 + 4.0, ad_len + 2.0).extrude(ad_wall_h)
          .cut(cq.Workplane("XY").workplane(offset=base_t - eps).center(ad_x, ad_y + 1.0)
               .rect(ad_w + 0.6, ad_len + 2.0).extrude(ad_wall_h + 2 * eps)))
base = base.union(cradle)

# ============================================================
# EXPORT
# ============================================================
cq.exporters.export(shell, "tastenbox_oberteil.stl", tolerance=0.01, angularTolerance=0.1)
cq.exporters.export(base, "tastenbox_boden.stl", tolerance=0.01, angularTolerance=0.1)
cq.exporters.export(shell, "tastenbox_oberteil.step")
cq.exporters.export(base, "tastenbox_boden.step")
cq.exporters.export(shell.union(base), "tastenbox_zusammen.stl", tolerance=0.01, angularTolerance=0.1)
print(f"Box {box_w:.1f} × {box_d:.1f} × {box_h} mm, mit Rand {box_w + 2 * flange:.1f} × {box_d + 2 * flange:.1f} mm · "
      f"Loch in der Holzplatte: {box_w + 1:.0f} × {box_d + 1:.0f} mm, Ecken R{corner_r:.0f}")
