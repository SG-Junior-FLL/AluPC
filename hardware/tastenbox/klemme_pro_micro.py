"""Klemm-Halter: Mini-Steckbrett (400 Kontakte) + Pro Micro OHNE Löten (Übergang, bis gelötet ist).

Zwei Teile:
  * Wanne: das Steckbrett liegt darin (Klebeboden geht trotzdem). Oben an den langen Wänden eine Leiste nach außen.
  * Bügel: drückt den Pro Micro auf die Stiftleisten. Die Haken rasten unter der Leiste ein; der Bügel lässt sich
    entlang des Steckbretts verschieben (dorthin, wo der Pro Micro steckt). Zwei Druckleisten liegen genau über den
    beiden Pin-Reihen (mit Rille für die Pin-Spitzen); über dem USB-C-Stecker ist der Bügel hoch genug fürs Kabel.
Die Wanne passt ins Tastenbox-Gehäuse (innen 144 × 86 × 44 mm).
Druck: Wanne flach (Boden aufs Bett). Bügel kopfüber (Oberseite aufs Bett) – keine Stützen.
Material: PETG (federt besser) oder PLA. Alle Maße in mm – Steckbrett nachmessen!
"""

import cadquery as cq

# ============================================================
# PARAMETER
# ============================================================
# Mini-Steckbrett 400 Kontakte (Händlerangaben 82–83 × 55 mm, ca. 8,5 mm hoch) – NACHMESSEN
bb_len = 83.0
bb_w = 55.0
bb_h = 8.5
bb_clear = 0.6         # Spiel rundum

# Wanne
floor_t = 2.0
wall = 2.0
wall_h = 6.0           # Wandhöhe über dem Boden (Steckbrett schaut oben heraus, Kabel frei)
lip_out = 1.2          # Leiste nach außen, oben an den langen Wänden
lip_h = 1.6

# Pro Micro auf Stiftleisten im Steckbrett
header_plastic = 2.5   # Kunststoffsteg der Stiftleiste (liegt auf dem Steckbrett)
pcb_t = 1.6
pin_row_dist = 15.24   # Abstand der beiden Pin-Reihen (0,6 Zoll)
pm_len = 34.0          # Platinenlänge (Stifte über ca. 30,5 mm)
press = 0.4            # so viel drückt der Bügel nach (Vorspannung)

# Bügel
pad_w = 2.4            # Breite der Druckleisten (über den Pin-Reihen) – schmal: Dupont-Stecker daneben passen
pin_groove_w = 1.0     # Rille für die Pin-Spitzen (Stift 0,64 mm)
pin_groove_d = 2.2
usb_clear = 6.5        # Höhe über der Platine: USB-C-Stecker mit Knickschutz passt darunter
top_t = 3.0            # Dicke der Querstege
bar_w = 5.0            # Breite der Querstege (an beiden Platinen-Enden, außerhalb der Pins)
leg_t = 1.8            # Federbeine (Dicke)
leg_w = 10.0
hook = 1.0             # Hakentiefe unter die Leiste

eps = 0.01

# ============================================================
# ABGELEITET
# ============================================================
in_len = bb_len + 2 * bb_clear
in_w = bb_w + 2 * bb_clear
out_len = in_len + 2 * wall
out_w = in_w + 2 * wall
wall_top = floor_t + wall_h
pcb_top = floor_t + bb_h + header_plastic + pcb_t     # Oberseite der Platine (Höhe über dem Wannenboden)
pad_bottom = pcb_top - press
bridge_bottom = pcb_top + usb_clear
bridge_top = bridge_bottom + top_t
lip_bottom = wall_top - lip_h
y_wall_out = out_w / 2

# ============================================================
# WANNE
# ============================================================
tray = cq.Workplane("XY").box(out_len, out_w, wall_top, centered=(True, True, False)).edges("|Z").fillet(3.0)
tray = tray.cut(cq.Workplane("XY").workplane(offset=floor_t)
                .box(in_len, in_w, wall_h + eps, centered=(True, True, False)).edges("|Z").fillet(1.0))
for s in (-1, 1):  # Rastleiste außen an den langen Wänden, über die ganze Länge
    tray = tray.union(cq.Workplane("XY").workplane(offset=lip_bottom)
                      .center(0, s * (y_wall_out + lip_out / 2)).rect(out_len - 8, lip_out).extrude(lip_h))
# Fenster im Boden (spart Material, Klebeband des Steckbretts bleibt erreichbar)
tray = tray.cut(cq.Workplane("XY").workplane(offset=-eps).rect(in_len - 16, in_w - 16).extrude(floor_t + 2 * eps))

# ============================================================
# BÜGEL (quer über das Steckbrett, Platine längs in Steckbrett-Richtung)
# ============================================================
span = out_w + 2 * (lip_out + 0.3)          # Innenmaß zwischen den Federbeinen
bar_x = pm_len / 2 + bar_w / 2 + 0.5        # Querstege knapp vor/hinter der Platine
bridge = cq.Workplane("XY")
parts = []
for sx in (-1, 1):  # zwei Querstege
    parts.append(cq.Workplane("XY").workplane(offset=bridge_bottom)
                 .center(sx * bar_x, 0).rect(bar_w, span + 2 * leg_t).extrude(top_t))
for sy in (-1, 1):  # zwei Druckleisten über den Pin-Reihen, verbinden die Querstege
    y = sy * pin_row_dist / 2
    rail_len = 2 * bar_x + bar_w
    parts.append(cq.Workplane("XY").workplane(offset=pad_bottom)
                 .center(0, y).rect(rail_len, pad_w).extrude(bridge_top - pad_bottom))
for sx in (-1, 1):  # Federbeine an den Enden der Querstege, mit Haken nach innen
    for sy in (-1, 1):
        x = sx * bar_x
        y = sy * (span / 2 + leg_t / 2)
        parts.append(cq.Workplane("XY").workplane(offset=lip_bottom - 2.0)
                     .center(x, y).rect(bar_w, leg_t).extrude(bridge_top - (lip_bottom - 2.0)))
        parts.append(cq.Workplane("XY").workplane(offset=lip_bottom - 2.0)
                     .center(x, sy * (span / 2 - hook / 2)).rect(bar_w, hook + eps).extrude(2.0))
for p in parts:
    bridge = p if bridge.vals() == [] else bridge.union(p)
# Rille in den Druckleisten für die Pin-Spitzen
for sy in (-1, 1):
    bridge = bridge.cut(cq.Workplane("XY").workplane(offset=pad_bottom - eps)
                        .center(0, sy * pin_row_dist / 2).rect(2 * bar_x - bar_w, pin_groove_w)
                        .extrude(pin_groove_d))

# ============================================================
# EXPORT
# ============================================================
cq.exporters.export(tray, "klemme_wanne.stl", tolerance=0.01, angularTolerance=0.1)
cq.exporters.export(bridge, "klemme_buegel.stl", tolerance=0.01, angularTolerance=0.1)
cq.exporters.export(tray.union(bridge), "klemme_zusammen.stl", tolerance=0.01, angularTolerance=0.1)
print(f"Wanne {out_len:.1f} × {out_w:.1f} × {wall_top:.1f} mm · Bügel bis {bridge_top:.1f} mm hoch · "
      f"Platine oben bei {pcb_top:.1f} mm")
