"""LED-Farbplan der Tastenbox: RGB-LEDs (4 Ecken + Lichtleiste in einer Kette) und die Farbschemata aus AluPC
(Eine Farbe, Ecken bunt, Zustand, Regenbogen) – Draufsicht, Maße aus tastenbox_gehaeuse.py → led_farben.png"""

import colorsys
import runpy

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Circle, FancyBboxPatch, Rectangle  # noqa: E402

g = runpy.run_path("tastenbox_gehaeuse.py")
bw, bd = g["box_w"], g["box_d"]
BAR = 7  # LEDs in der Lichtleiste (144 LEDs/m)
# Reihenfolge der Kette (wie im Arduino-Programm): 0 vorne links, 1 hinten links, 2 hinten rechts, 3 vorne rechts
order = [(-1, -1), (-1, 1), (1, 1), (1, -1)]
corners = [(sx * (bw / 2 - g["led_inset"]), sy * (bd / 2 - g["led_inset"])) for sx, sy in order]
bx = g["grid_cx"] + g["bar_shift"]
bar = [(bx - g["bar_len"] / 2 + 3 + i * (g["bar_len"] - 6) / (BAR - 1), g["bar_y"]) for i in range(BAR)]


def rainbow(i, n):
    r, gg, b = colorsys.hsv_to_rgb(i / n, 1, 1)
    return (r, gg, b)


SCHEMES = [
    ("Eine Farbe", "Alle LEDs gleich (Farbe in AluPC wählbar)", ["#57c1ff"] * 4, ["#57c1ff"] * BAR),
    ("Ecken bunt", "Jede Ecke eigene Farbe, Leiste in der Grundfarbe",
     ["#57c1ff", "#ff6161", "#59d499", "#ffc533"], ["#ffffff"] * BAR),
    ("Zustand: live", "Rot = läuft auf Bildschirm 2 (Gelb = Schwarz/Standbild)", ["#ff2020"] * 4, ["#ff2020"] * BAR),
    ("Regenbogen", "Farben wandern durch die Kette (Effekt in der Box)",
     [rainbow(i, 4 + BAR) for i in range(4)], [rainbow(i + 4, 4 + BAR) for i in range(BAR)]),
]

fig, axes = plt.subplots(2, 2, figsize=(14, 9.4), dpi=120)
fig.patch.set_facecolor("#07080a")
for ax, (name, note, cc, bc) in zip(axes.flat, SCHEMES):
    ax.set_facecolor("#07080a")
    ax.add_patch(FancyBboxPatch((-bw / 2, -bd / 2), bw, bd, boxstyle=f"round,pad=0,rounding_size={g['corner_r']}",
                                fc="#16171a", ec="#3a3d40", lw=1.2))
    for (kx, ky) in g["keys"]:
        ax.add_patch(Rectangle((kx - 7, ky - 7), 14, 14, fc="#222428", ec="#2f3236"))
    ax.add_patch(Circle((g["lock_x"], g["lock_dy"]), g["lock_d"] / 2, fc="#222428", ec="#2f3236"))
    ax.add_patch(Circle((g["pot_x"], g["pot_y"]), 6, fc="#222428", ec="#2f3236"))  # Mutter/Knopf
    ax.add_patch(Rectangle((g["cnt_x"] - g["win_w"] / 2, g["cnt_y"] + g["win_dy"] - g["win_h"] / 2), g["win_w"],
                           g["win_h"], fc="#0b0c0e", ec="#2f3236"))
    ax.text(g["cnt_x"], g["cnt_y"] + g["win_dy"], "2 5 0", color="#f4f4f6", ha="center", va="center", fontsize=9)
    for (x, y), c in zip(corners, cc):  # Leuchten = großer weicher Kreis + heller Kern
        ax.add_patch(Circle((x, y), 9, fc=c, ec="none", alpha=0.18))
        ax.add_patch(Circle((x, y), 2.6, fc=c, ec="white", lw=0.6))
    ax.add_patch(FancyBboxPatch((bx - g["bar_len"] / 2, g["bar_y"] - 1.5), g["bar_len"], 3,
                                boxstyle="round,pad=0,rounding_size=1.5", fc="#0b0c0e", ec="#3a3d40", lw=0.8))
    for (x, y), c in zip(bar, bc):
        ax.add_patch(Circle((x, y), 4, fc=c, ec="none", alpha=0.22))
        ax.add_patch(Circle((x, y), 1.2, fc=c, ec="none"))
    for i, (x, y) in enumerate(corners):
        ax.text(x + (6 if x < 0 else -6), y + (-6 if y > 0 else 6), str(i), color="#9c9c9d", fontsize=8,
                ha="center", va="center")
    ax.set_xlim(-bw / 2 - 8, bw / 2 + 8)
    ax.set_ylim(-bd / 2 - 16, bd / 2 + 8)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(name, color="#f4f4f6", fontsize=13, loc="left")
    ax.text(-bw / 2, -bd / 2 - 10, note, color="#9c9c9d", fontsize=9)
fig.suptitle("Tastenbox – RGB-LEDs: 4 Ecken + Lichtleiste in einer Kette (Zahlen = Reihenfolge 0–3, Leiste ab 4)",
             color="#f4f4f6", fontsize=12, x=0.02, ha="left")
fig.tight_layout(rect=(0, 0, 1, 0.95))
fig.savefig("led_farben.png", facecolor=fig.get_facecolor())
