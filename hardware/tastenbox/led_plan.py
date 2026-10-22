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
    ax.add_patch(Rectangle((kx - 9, ky - 9), 18, 18, fc="#dfe3ea", ec="#777"))
ax.add_patch(Rectangle((g["bb_cx"] - g["rim_in_w"] / 2, -g["rim_in_l"] / 2), g["rim_in_w"], g["rim_in_l"], fc="none",
                       ec="#9aa", ls="--"))
ax.text(g["bb_cx"], 0, "Steckbrett + Pro Micro\n(darunter)", ha="center", va="center", color="#678", fontsize=10)
ax.add_patch(Circle((g["pot_x"], g["pot_y"]), 12, fc="#e6e6e6", ec="#777"))
ax.text(g["pot_x"], g["pot_y"], "Poti\n(Knopf)", ha="center", va="center", fontsize=8)
ax.add_patch(Rectangle((g["cnt_x"] - g["cnt_w"] / 2, g["cnt_y"] - g["cnt_d"] / 2), g["cnt_w"], g["cnt_d"], fc="none",
                       ec="#9aa", ls="--"))
ax.add_patch(Rectangle((g["cnt_x"] - g["win_w"] / 2, g["cnt_y"] + g["win_dy"] - g["win_h"] / 2), g["win_w"], g["win_h"],
                       fc="#222428", ec="#555"))
ax.text(g["cnt_x"], g["cnt_y"] + g["win_dy"], "0 0 0", ha="center", va="center", fontsize=9, color="white")
ax.text(g["cnt_x"], g["cnt_y"] - 8, "Zählwerk\n(darunter)", ha="center", va="center", fontsize=8, color="#678")
# 8 Eck-LEDs (je Ecke 2) in ihren Farben + Kabelwege zu den Haken und zum Steckbrett
HEX = {"rot": "#ff3b30", "grün": "#20b85c", "blau": "#2f6bff", "weiß": "#bbbbbb"}
FARBE = ["rot", "grün", "blau"] * 4   # je Ecke außen → innen: rot, grün, blau
for (lx, ly), f in zip(g["leds"], FARBE):
    ax.add_patch(Circle((lx, ly), 4.5, fc="#ffffff", ec=HEX[f], lw=1.5))
    ax.add_patch(Circle((lx, ly), 2.6, fc=HEX[f], ec="none"))
hooks = [(hx, sy * (g["inner_d"] / 2 - 2.5)) for hx in (g["x0"] + 36, g["bb_cx"] + g["rim_out_w"] / 2 + g["lip_out"] + g["gap"] / 2)
         for sy in (-1, 1)]
for hx, hy in hooks:
    ax.add_patch(Rectangle((hx - 3, hy - 2.5), 6, 5, fc="#c9d6ff", ec="#4a64c8"))
for (lx, ly) in g["leds"][::g["led_per_corner"]]:  # Kabel je Ecke: LEDs → Haken → an der Wand entlang → Steckbrett-Kante
    hx, hy = min(hooks, key=lambda h: (h[0] - lx) ** 2 + (h[1] - ly) ** 2)
    edge = g["bb_cx"] + (-1 if hx < g["bb_cx"] else 1) * (g["rim_in_w"] / 2 - 4)
    ax.plot([lx, hx, edge, edge], [ly, hy, hy, hy * 0.8], color="#d79a00", lw=1.4, ls=":")
ax.annotate("3 LEDs je Ecke (5 mm, im Halter): rot, grün, blau\nPro Micro: rot 10 · grün 9 · blau 16 (Nano: 11 · 12 · 13)\njede LED eigener 1-kΩ-Widerstand",
            g["leds"][4], (g["leds"][4][0] + 6, bd / 2 + 14), fontsize=9, ha="center",
            arrowprops=dict(arrowstyle="->", color="#d79a00"))
ax.annotate("Kabelhaken (innen)", hooks[1], (hooks[1][0] + 40, bd / 2 + 12), fontsize=9, ha="center",
            arrowprops=dict(arrowstyle="->", color="#4a64c8"))
ax.set_xlim(-bw / 2 - 14, bw / 2 + 14)
ax.set_ylim(-bd / 2 - 12, bd / 2 + 26)
ax.set_aspect("equal")
ax.axis("off")
ax.set_title("Tastenbox – LED-Plan (Draufsicht, Maße in mm)", fontsize=13)
fig.tight_layout()
fig.savefig("led_plan.png")
