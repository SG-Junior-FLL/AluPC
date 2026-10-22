"""LED-Farbkonzept der Tastenbox mit einfarbigen 5-mm-LEDs: je Ecke 2 LEDs, 4 Farben (rot, grün, blau, weiß),
jede Farbe in zwei diagonalen Ecken („Kreuz“). Zeigt, wie die Box bei den Zuständen aus AluPC leuchtet.
Draufsicht, Maße aus tastenbox_gehaeuse.py → led_farben.png"""

import runpy

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Circle, FancyBboxPatch, Rectangle  # noqa: E402

g = runpy.run_path("tastenbox_gehaeuse.py")
bw, bd = g["box_w"], g["box_d"]
HEX = {"rot": "#ff3b30", "grün": "#34e07a", "blau": "#3d7bff", "weiß": "#f4f4f6"}
# g["leds"]: vorne links außen/innen, hinten links außen/innen, vorne rechts außen/innen, hinten rechts außen/innen
FARBE = ["rot", "weiß", "blau", "grün", "blau", "grün", "rot", "weiß"]
PIN = {"rot": "D11", "grün": "D12", "blau": "D13", "weiß": "A1"}

# (Titel, AluPC-Farbe/Einstellung, Helligkeit je Farbkanal 0–1)
STATES = [
    ("Bereit", "Farbe #80ff80 (Grundfarbe)", {"grün": 1, "weiß": 0.6}),
    ("Live", "läuft auf Bildschirm 2 (Schema „Zustand“)", {"rot": 1}),
    ("Schwarz / Standbild", "Schema „Zustand“ (#ffb000)", {"rot": 1, "grün": 0.6}),
    ("Code-Eingabe", "Wenn → Dann: blinkt in der Grundfarbe", {"grün": 1, "weiß": 0.6}),
    ("Farbwechsel", "Effekt „Regenbogen“: rot → grün → blau → weiß", {"blau": 1, "grün": 0.35}),
    ("Arbeitslicht", "Farbe weiß (#ffffff): alle 8 LEDs", {"rot": 1, "grün": 1, "blau": 1, "weiß": 1}),
]

fig, axes = plt.subplots(2, 3, figsize=(17, 8.2), dpi=110)
fig.patch.set_facecolor("#07080a")
for ax, (name, note, on) in zip(axes.flat, STATES):
    ax.set_facecolor("#07080a")
    ax.add_patch(FancyBboxPatch((-bw / 2, -bd / 2), bw, bd, boxstyle=f"round,pad=0,rounding_size={g['corner_r']}",
                                fc="#16171a", ec="#3a3d40", lw=1.2))
    for (kx, ky) in g["keys"]:
        ax.add_patch(Rectangle((kx - 9, ky - 9), 18, 18, fc="#222428", ec="#2f3236"))
    ax.add_patch(Rectangle((g["cnt_x"] - g["win_w"] / 2, g["cnt_y"] + g["win_dy"] - g["win_h"] / 2), g["win_w"],
                           g["win_h"], fc="#0b0c0e", ec="#2f3236"))
    ax.text(g["cnt_x"], g["cnt_y"] + g["win_dy"], "2 5 0", color="#f4f4f6", ha="center", va="center", fontsize=9)
    ax.add_patch(Circle((g["pot_x"], g["pot_y"]), 12, fc="#222428", ec="#2f3236"))
    for (x, y), f in zip(g["leds"], FARBE):
        level = on.get(f, 0)
        c = HEX[f]
        if level:
            ax.add_patch(Circle((x, y), 4 + 7 * level, fc=c, ec="none", alpha=0.10 + 0.12 * level))
            ax.add_patch(Circle((x, y), 2.6, fc=c, ec="white", lw=0.6, alpha=0.4 + 0.6 * level))
        else:
            ax.add_patch(Circle((x, y), 2.6, fc="#0b0c0e", ec=c, lw=0.8, alpha=0.6))
    if name == "Farbwechsel":
        ax.annotate("", (g["leds"][4][0] - 14, g["leds"][4][1] + 8), (g["leds"][0][0] + 14, g["leds"][0][1] + 8),
                    arrowprops=dict(arrowstyle="<->", color="#9c9c9d", connectionstyle="arc3,rad=-0.15"))
    ax.set_xlim(-bw / 2 - 8, bw / 2 + 8)
    ax.set_ylim(-bd / 2 - 16, bd / 2 + 8)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(name, color="#f4f4f6", fontsize=13, loc="left")
    ax.text(-bw / 2, -bd / 2 - 10, note, color="#9c9c9d", fontsize=9)
legend = "   ".join(f"● {f} = Pin {PIN[f]}" for f in HEX)
fig.suptitle("Tastenbox – 8 LEDs, 4 Farben, je Farbe 2 LEDs in diagonalen Ecken („Kreuz“)   " + legend,
             color="#f4f4f6", fontsize=12, x=0.02, ha="left")
fig.tight_layout(rect=(0, 0, 1, 0.94))
fig.savefig("led_farben.png", facecolor=fig.get_facecolor())
