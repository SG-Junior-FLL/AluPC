"""AluPC-Tastenbox – Einbau-Gehäuse für ein Loch in einer Holzplatte (CadQuery). Entwurf 4.

So hoch, dass das 10-Gang-Poti (Ø 22 × 39 mm + Lötfahne) stehend hineinpasst. Ein dünner Rand (Flansch) läuft
rundum 10 mm über – er liegt auf der Holzplatte auf; oben schauen 16 mm heraus, der Rest steckt unter dem Holz.

Oberseite von links nach rechts: 9 Tastatur-Schalter (MX, 3 × 3) → Steckbrett darunter → rechte Spalte mit
Zählwerk (Fenster für die 3 Ziffern, hängt an 4 Säulen unter dem Deckel) und dahinter 10-Gang-Poti
(Gewindehals durch den Deckel, Mutter oben). In jeder Ecke ZWEI 5-mm-LEDs nebeneinander (8 Stück, 4 Farben).

Zwei Teile:
  * Oberteil mit Flansch. Druck: Oberseite nach UNTEN aufs Bett; Stützen NUR unter dem Rand
    (Baumstützen, „nur am Druckbett“) – lassen sich leicht abbrechen.
  * Boden: wird von unten eingesteckt, rastet mit zwei Federlaschen ein (Nasen bündig in Schlitzen der
    Seitenwand – nichts steht über, die Box passt ins Loch). Lösen: Nasen von außen eindrücken, Boden ziehen.
    Auf dem Boden: Rahmen fürs Steckbrett (400 Kontakte) mit Rastleiste für den Bügel aus klemme_pro_micro.py,
    Loch unter dem Zündschloss (falls es länger ist).
Kabel: USB-C des Pro Micro hinten (Fenster).
Zählwerk und Poti: Maße aus Fotos geschätzt – mit „NACHMESSEN“ markierte Werte vor dem Druck prüfen.
Material: PETG empfohlen (Laschen federn). Alle Maße in mm.
"""

import cadquery as cq

# ============================================================
# PARAMETER
# ============================================================
box_h = 52.0           # Gesamthöhe (innen 46 mm) – Poti Ø 22 × 39 mm + Lötfahne hinten steht senkrecht darin
wall = 2.4
top_t = 3.0
corner_r = 8.0
flange = 10.0          # Rand rundum über die Box hinaus
flange_t = 2.5         # Dicke des Randes
flange_z = box_h - 16.0  # Höhe der Rand-Mitte über der Unterkante: darüber schaut die Box 16 mm aus dem Holz
flange_edge_r = 1.2    # Kanten am Rand gerundet
top_r = 3.0            # obere Kante der Box gerundet (steht über die Holzplatte)

# LEDs in den 4 Ecken (5 mm). Halter innen am Deckel: LED von unten einstecken, bis der Kragen anliegt –
# die Kuppe schließt dann bündig mit der Oberseite ab. Beine zeigen nach innen (Kerbe), Kabel in die Haken.
led_d = 5.2            # Loch in der Deckplatte (Kuppe)
led_fit = 5.15         # Bohrung im Halter (5-mm-LED klemmt; zu stramm → 5,3)
led_len = 8.6          # LED vom Kragen bis zur Kuppe (Standard 5 mm)
led_boss_d = 9.0
led_inset = 7.0        # Abstand der Loch-Mitte (äußere LED) von den Außenkanten
led_pair = 10.0        # zweite LED je Ecke: so weit zur Mitte hin (entlang der langen Seite)
led_skin = 0.0         # > 0 (z. B. 0,6): Loch oben geschlossen, Licht scheint durch (nur helles Filament)

# Lichtleiste vorne über den Tasten (WS2812B-Streifen, 10 mm breit, z. B. 60 LEDs/m → 3 LEDs, 144/m → 7)
light_bar = False      # keine Lichtleiste (kein LED-Streifen vorhanden)
bar_shift = 5.0        # Leiste etwas nach rechts: Platz für den Halter der Eck-LED
bar_len = 42.0         # Schlitz-Länge (Eck-LED links vorn bleibt frei)
bar_w = 3.0            # Schlitz-Breite
bar_skin = 0.0         # > 0: geschlossen, diffus (helles Filament)
strip_w = 10.4         # Streifen 10 mm + Luft
strip_h = 3.2          # Streifen + LED-Höhe: Abstand Deckel → Boden der Schiene
rail_t = 1.2

# Kabelhaken innen am Deckel (für LED-Kabel zum Steckbrett)
hook_w = 6.0

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
col_w = 56.0

# 10-Gang-Poti (DDR, 490.02xx) – Gewindehals durch den Deckel, Mutter + Zahnscheibe oben
pot_body_d = 22.0      # NACHMESSEN
pot_neck_d = 10.0      # Gewindehals – NACHMESSEN (Loch = Hals + 0,4)
pot_dx, pot_dy = -6.0, 29.0    # Lage relativ zur Spaltenmitte (hinten, frei von den Eck-LEDs)

# Zählwerk (3 Ziffern) – hängt an 4 Säulen unter dem Deckel, M3-Schrauben von unten durch seine Langlöcher
cnt_w, cnt_d = 46.0, 36.0     # Grundplatte (Ziffernachse in x) – NACHMESSEN
cnt_h = 26.0           # Unterkante Grundplatte bis Oberkante Ziffernrollen – NACHMESSEN
cnt_gap = 1.0          # Luft Ziffernrollen ↔ Deckel
cnt_holes = [(-21.0, -11.5), (21.0, -11.5), (-21.0, 11.5), (21.0, 11.5)]  # Langloch-Mitten – NACHMESSEN
cnt_dx = -6.0          # nach links gerückt: rechts vorne sitzen die Eck-LEDs
cnt_dy = -17.0         # Mitte der Grundplatte (vorne bleibt Platz für die LED-Halter)
win_w, win_h = 32.0, 13.0      # Fenster für die Ziffernzeile
win_dy = 15.0          # Ziffernzeile liegt so weit hinter der Plattenmitte – NACHMESSEN
pillar_d = 6.0
pillar_hole = 2.5      # M3 selbstschneidend

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

# Kabelausschnitte hinten
usb_win_w = 14.0       # Pro Micro USB-C
usb_win_h = 11.0

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
pot_x, pot_y = col_cx + pot_dx, pot_dy
cnt_x, cnt_y = col_cx + cnt_dx, cnt_dy

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
leds = [(sx * (box_w / 2 - led_inset - k * led_pair), sy * (box_d / 2 - led_inset))
        for sx in (-1, 1) for sy in (-1, 1) for k in (0, 1)]     # je Ecke: außen (k=0), innen (k=1)
under = box_h - top_t                                 # Unterseite der Deckplatte
boss_h = led_len - top_t                              # Kuppe bündig mit der Oberseite
footprint = (cq.Workplane("XY").rect(inner_w, inner_d).extrude(box_h).edges("|Z").fillet(corner_r - wall))
for (lx, ly) in leds:
    boss = cq.Workplane("XY").workplane(offset=under - boss_h).center(lx, ly).circle(led_boss_d / 2).extrude(boss_h + eps)
    # Kerbe zur Box-Mitte (quer zur Wand): dort kommen die Beine heraus, die Nachbar-LED ist nicht im Weg
    to_mid = 1 if ly < 0 else -1
    boss = boss.cut(cq.Workplane("XY").workplane(offset=under - boss_h - eps).center(lx, ly + to_mid * led_boss_d / 2)
                    .rect(2.2, led_boss_d * 0.5).extrude(2.5))
    shell = shell.union(boss.intersect(footprint))
    shell = shell.cut(cq.Workplane("XY").workplane(offset=under - boss_h - eps).center(lx, ly)
                      .circle(led_fit / 2).extrude(boss_h + 2 * eps))
shell = shell.cut(cq.Workplane("XY").workplane(offset=under).pushPoints(leds).circle(led_d / 2)
                  .extrude(top_t - led_skin + (eps if led_skin == 0 else 0)))
# Poti: Loch für den Gewindehals
shell = shell.cut(cq.Workplane("XY").center(pot_x, pot_y).circle((pot_neck_d + 0.4) / 2).extrude(box_h + 1))
# Zählwerk: Fenster (oben leicht angefast) + 4 Säulen bis zur Grundplatte
shell = shell.cut(cq.Workplane("XY").workplane(offset=under - eps).center(cnt_x, cnt_y + win_dy)
                  .rect(win_w, win_h).extrude(top_t + 2 * eps).edges(">Z").chamfer(0.8))
cnt_bottom = under - cnt_gap - cnt_h                 # Unterkante der Zählwerk-Grundplatte
for hx, hy in cnt_holes:
    col = (cq.Workplane("XY").workplane(offset=cnt_bottom).center(cnt_x + hx, cnt_y + hy)
           .circle(pillar_d / 2).extrude(under - cnt_bottom + eps)
           .cut(cq.Workplane("XY").workplane(offset=cnt_bottom - eps).center(cnt_x + hx, cnt_y + hy)
                .circle(pillar_hole / 2).extrude(10)))
    shell = shell.union(col)

# Lichtleiste: Schlitz vor den Tasten + Schiene darunter (Streifen von rechts einschieben, Klebeseite nach unten)
bar_y = -(19.05 + mx_relief / 2 + (box_d / 2 - wall - 19.05 - mx_relief / 2) / 2)  # Mitte zwischen Tasten und Wand
if light_bar:
    shell = shell.cut(cq.Workplane("XY").workplane(offset=under - eps).center(grid_cx + bar_shift, bar_y)
                      .slot2D(bar_len, bar_w).extrude(top_t - bar_skin + (2 * eps if bar_skin == 0 else eps)))
    rail_len = bar_len + 8
    bx = grid_cx + bar_shift
    rail = (cq.Workplane("XY").workplane(offset=under - strip_h - rail_t).center(bx, bar_y)
            .rect(rail_len, strip_w + 2 * rail_t).extrude(strip_h + rail_t + eps)
            .cut(cq.Workplane("XY").workplane(offset=under - strip_h).center(bx + 2, bar_y)
                 .rect(rail_len, strip_w).extrude(strip_h + eps)))          # rechts offen zum Einschieben
    # Fenster im Schienenboden: Kabel des Streifens nach unten
    rail = rail.cut(cq.Workplane("XY").workplane(offset=under - strip_h - rail_t - eps)
                    .center(bx + rail_len / 2 - 6, bar_y).rect(6, strip_w - 2).extrude(rail_t + 2 * eps))
    shell = shell.union(rail.intersect(footprint))

# Kabelhaken an den Längswänden innen: LED-Kabel von den Ecken zum Steckbrett führen
for hx in (x0 + 25, bb_cx + rim_out_w / 2 + lip_out + gap / 2):  # neben den linken LED-Paaren, rechts neben dem Steckbrett
    for sy in (-1, 1):
        wy = sy * (inner_d / 2)
        hook = (cq.Workplane("XY").workplane(offset=under - 7).center(hx, wy - sy * 2.5)
                .rect(hook_w, 5).extrude(7 + eps)
                .cut(cq.Workplane("XY").workplane(offset=under - 5.5).center(hx, wy - sy * 2.0)
                     .rect(hook_w + 1, 3.2).extrude(4.5)))
        shell = shell.union(hook.intersect(footprint))

nose_z = base_t + snap_len - nose_h - nose_hold
for sx in (-1, 1):
    shell = shell.cut(cq.Workplane("XY").workplane(offset=nose_z - slot_clear)
                      .center(sx * (box_w / 2 - wall / 2), 0)
                      .rect(wall * 3, snap_w + 2 * slot_clear).extrude(nose_hold + nose_h + 2 * slot_clear))

# Pro Micro steckt am hinteren Ende des Steckbretts, USB-C zeigt nach hinten
usb_z = base_t + 8.5 + 2.5 + 1.6 + 1.6               # Mitte USB-C über dem Boden
shell = shell.cut(cq.Workplane("XY").workplane(offset=usb_z - usb_win_h / 2)
                  .center(bb_cx, box_d / 2 - wall / 2).rect(usb_win_w, wall * 3).extrude(usb_win_h))

# ============================================================
# BODEN
# ============================================================
bw, bd = inner_w - 2 * base_clear, inner_d - 2 * base_clear
base = (cq.Workplane("XY").box(bw, bd, base_t, centered=(True, True, False))
        .edges("|Z").fillet(corner_r - wall - base_clear))

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

# ============================================================
# EXPORT
# ============================================================
cq.exporters.export(shell, "tastenbox_oberteil.stl", tolerance=0.01, angularTolerance=0.1)
cq.exporters.export(base, "tastenbox_boden.stl", tolerance=0.01, angularTolerance=0.1)
cq.exporters.export(shell, "tastenbox_oberteil.step")
cq.exporters.export(base, "tastenbox_boden.step")
cq.exporters.export(shell.union(base), "tastenbox_zusammen.stl", tolerance=0.01, angularTolerance=0.1)
print(f"LED-Halter: {boss_h:.1f} mm unter dem Deckel · Lichtleiste {bar_len:.0f} × {bar_w:.0f} mm bei y={bar_y:.1f}")
print(f"Box {box_w:.1f} × {box_d:.1f} × {box_h} mm, mit Rand {box_w + 2 * flange:.1f} × {box_d + 2 * flange:.1f} mm · "
      f"Loch in der Holzplatte: {box_w + 1:.0f} × {box_d + 1:.0f} mm, Ecken R{corner_r:.0f}")
