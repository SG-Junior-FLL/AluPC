"""Zeichnet den LED-Plan der Tastenbox (Draufsicht, Maße aus tastenbox_gehaeuse.py) → led_plan.png"""

import runpy

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Circle, FancyBboxPatch, Rectangle  # noqa: E402

g = runpy.run_path("tastenbox_gehaeuse.py")
bw, bd = g["box_w"], g["box_d"]
fig, ax = plt.subplots(figsize=(12, 7.6), dpi=130)
ax.add_patch(FancyBboxPatch((-bw / 2 - g["flange"], -bd / 2 - g["flange"]), bw + 2 * g["flange"], bd + 2 * g["flange"],
                            boxstyle=f"round,pad=0,rounding_size={g['corner_r'] + g['flange']}", fc="#efe7da", ec="#b9a888"))
ax.add_patch(FancyBboxPatch((-bw / 2, -bd / 2), bw, bd, boxstyle=f"round,pad=0,rounding_size={g['corner_r']}",
                            fc="#f7f7f8", ec="#555", lw=1.5))
for (kx, ky) in g["keys"]:
    ax.add_patch(Rectangle((kx - 7, ky - 7), 14, 14, fc="#dfe3ea", ec="#777"))
ax.add_patch(Rectangle((g["bb_cx"] - g["rim_in_w"] / 2, -g["rim_in_l"] / 2), g["rim_in_w"], g["rim_in_l"], fc="none",
                       ec="#9aa", ls="--"))
ax.text(g["bb_cx"], 0, "Steckbrett\n(darunter)\nPin 9 / GND", ha="center", va="center", color="#678", fontsize=10)
ax.add_patch(Circle((g["lock_x"], g["lock_dy"]), g["lock_d"] / 2, fc="#e6e6e6", ec="#777"))
ax.text(g["lock_x"], g["lock_dy"], "Schloss", ha="center", va="center", fontsize=8)
ax.add_patch(Circle((g["fp_x"], g["fp_dy"]), g["fp_d"] / 2, fc="#e6e6e6", ec="#777"))
ax.text(g["fp_x"], g["fp_dy"], "Finger", ha="center", va="center", fontsize=8)
ax.text(g["knob_x"], g["knob_dy"], "Regler\n(folgt)", ha="center", va="center", fontsize=8, color="#888")
# Eck-LEDs + Kabelwege zu den Haken und zum Steckbrett
for i, (lx, ly) in enumerate(g["leds"]):
    ax.add_patch(Circle((lx, ly), 4.5, fc="#ffe9a8", ec="#d79a00", lw=1.5))
    ax.add_patch(Circle((lx, ly), 2.6, fc="#ffbf00", ec="none"))
hooks = [(hx, sy * (g["inner_d"] / 2 - 2.5)) for hx in (g["x0"] + 10, g["bb_cx"] + g["rim_out_w"] / 2 + g["lip_out"] + g["gap"] / 2)
         for sy in (-1, 1)]
for hx, hy in hooks:
    ax.add_patch(Rectangle((hx - 3, hy - 2.5), 6, 5, fc="#c9d6ff", ec="#4a64c8"))
for (lx, ly) in g["leds"]:  # Kabel: LED → Haken → an der Wand entlang → Steckbrett-Kante
    hx, hy = min(hooks, key=lambda h: (h[0] - lx) ** 2 + (h[1] - ly) ** 2)
    edge = g["bb_cx"] + (-1 if hx < g["bb_cx"] else 1) * (g["rim_in_w"] / 2 - 4)
    ax.plot([lx, hx, edge, edge], [ly, hy, hy, hy * 0.8], color="#d79a00", lw=1.4, ls=":")
bx = g["grid_cx"] + g["bar_shift"]
ax.add_patch(FancyBboxPatch((bx - g["bar_len"] / 2, g["bar_y"] - g["bar_w"] / 2), g["bar_len"], g["bar_w"],
                            boxstyle="round,pad=0,rounding_size=1.5", fc="#7ee0ff", ec="#0b8fc0", lw=1.5))
ax.annotate("Lichtleiste (WS2812B-Streifen, Pin 10 / Nano 12)\nvon rechts in die Schiene schieben", (bx, g["bar_y"]),
            (bx - 10, -bd / 2 - 16), fontsize=9, ha="center", arrowprops=dict(arrowstyle="->", color="#0b8fc0"))
ax.annotate("Eck-LED (5 mm) im Halter\nPin 9 / Nano 11, je 1 kΩ", g["leds"][1], (g["leds"][1][0] - 30, bd / 2 + 12),
            fontsize=9, ha="center", arrowprops=dict(arrowstyle="->", color="#d79a00"))
ax.annotate("Kabelhaken (innen)", hooks[1], (hooks[1][0] + 32, bd / 2 + 12), fontsize=9, ha="center",
            arrowprops=dict(arrowstyle="->", color="#4a64c8"))
ax.set_xlim(-bw / 2 - 14, bw / 2 + 14)
ax.set_ylim(-bd / 2 - 22, bd / 2 + 20)
ax.set_aspect("equal")
ax.axis("off")
ax.set_title("Tastenbox – LED-Plan (Draufsicht, Maße in mm)", fontsize=13)
fig.tight_layout()
fig.savefig("led_plan.png")
