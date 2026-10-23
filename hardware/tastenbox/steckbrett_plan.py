"""Steckplan der Tastenbox auf dem Steckbrett (400 Kontakte, Reihen 1–30, Spalten a–j) mit Pro Micro in Reihe 1–12
→ steckbrett_plan.png. Nur stecken: Dupont-Kabel, Widerstände ins Steckbrett."""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch, Rectangle  # noqa: E402

COLS = "abcdefghij"
X = {c: (i if i < 5 else i + 1.2) for i, c in enumerate(COLS)}  # Mittelgraben zwischen e und f
RAIL = {"L-": -3.0, "L+": -2.2, "R+": X["j"] + 2.2, "R-": X["j"] + 3.0}


def y(row):
    return -row


fig, ax = plt.subplots(figsize=(13, 15), dpi=110)
ax.add_patch(FancyBboxPatch((-3.8, -31), X["j"] + 7.6, 30.6, boxstyle="round,pad=0,rounding_size=0.5", fc="#f2f2f0",
                            ec="#bbb"))
for r in range(1, 31):
    ax.text(-1.2, y(r), str(r), ha="center", va="center", fontsize=7, color="#888")
    for c in COLS:
        ax.add_patch(Rectangle((X[c] - 0.15, y(r) - 0.15), 0.3, 0.3, fc="#cfcfcf", ec="none"))
for c in COLS:
    ax.text(X[c], 0.2, c, ha="center", fontsize=8, color="#888")
for name, x in RAIL.items():
    ax.plot([x, x], [y(1), y(30)], color="#d33" if "+" in name else "#36c", lw=1.2)
    ax.text(x, 0.4, name[1], ha="center", fontsize=11, color="#d33" if "+" in name else "#36c", fontweight="bold")

# Pro Micro, USB-C oben, Reihen 1–12
LEFT = ["TX", "RX", "GND", "GND", "2", "3", "4", "5", "6", "7", "8", "9"]
RIGHT = ["RAW", "GND", "RST", "VCC", "A3", "A2", "A1", "A0", "15", "14", "16", "10"]
ax.add_patch(FancyBboxPatch((X["b"] - 0.5, y(12) - 0.6), X["i"] - X["b"] + 1.0, 12.4, boxstyle="round,pad=0,rounding_size=0.3",
                            fc="#2a6fcf", ec="#174a8f", alpha=0.9))
ax.add_patch(Rectangle(((X["b"] + X["i"]) / 2 - 1.0, y(0.2)), 2.0, 1.2, fc="#bbb", ec="#777"))
ax.text((X["b"] + X["i"]) / 2, y(-0.4), "USB-C", ha="center", va="center", fontsize=8)
ax.text((X["b"] + X["i"]) / 2, y(7), "Pro Micro", ha="center", va="center", color="white", fontsize=11, rotation=90)
for i, (lft, rgt) in enumerate(zip(LEFT, RIGHT), start=1):
    ax.text(X["b"], y(i), lft, ha="center", va="center", color="white", fontsize=7, fontweight="bold")
    ax.text(X["i"], y(i), rgt, ha="center", va="center", color="white", fontsize=7, fontweight="bold")


def wire(x0, r0, x1, r1, color, label=None, side="r", bow=0.0):
    if bow:  # Brücke seitlich vorbei (Kabel liegt über den anderen Löchern)
        ax.plot([x0, x0 + bow, x1 + bow, x1], [y(r0), y(r0), y(r1), y(r1)], color=color, lw=2.4, zorder=5)
    else:
        ax.plot([x0, x1], [y(r0), y(r1)], color=color, lw=2.4, solid_capstyle="round", zorder=5)
    ax.plot([x0, x1], [y(r0), y(r1)], "o", color=color, ms=5, zorder=6)
    if label:
        ax.text(x1 + (0.35 if side == "r" else -0.35), y(r1), label, va="center", ha="left" if side == "r" else "right",
                fontsize=8.5, color="#222", zorder=7)


def resistor(x0, r0, x1, r1):
    ax.plot([x0, x1], [y(r0), y(r1)], color="#8a6d3b", lw=1.2, zorder=5)
    mx, my = (x0 + x1) / 2, (y(r0) + y(r1)) / 2
    ax.add_patch(FancyBboxPatch((mx - 0.18, my - 0.45), 0.36, 0.9, boxstyle="round,pad=0,rounding_size=0.15",
                                fc="#e8c98a", ec="#8a6d3b", zorder=6))


# Strom: GND → Minus-Leisten, VCC → Plus rechts
wire(X["a"], 3, RAIL["L-"], 3, "#36c")
ax.text(-3.4, y(3), "GND → Minus", ha="right", va="center", fontsize=8.5)
wire(X["j"], 2, RAIL["R-"], 2, "#36c")
wire(X["j"], 4, RAIL["R+"], 4, "#d33")
ax.text(RAIL["R-"] + 0.4, y(2), "GND → Minus", va="center", fontsize=8.5)
ax.text(RAIL["R-"] + 0.4, y(4), "VCC → Plus", va="center", fontsize=8.5)
# Tasten
for i, row in enumerate(range(5, 12), start=1):
    ax.text(-3.4, y(row), f"Taste {i} → in a{row}", ha="right", va="center", fontsize=8.5, color="#060")
ax.text(RAIL["R-"] + 0.4, y(9), "← Taste 9 (in j)", va="center", fontsize=8.5, color="#060")
ax.text(RAIL["R-"] + 0.4, y(10), "← Taste 8 (in j)", va="center", fontsize=8.5, color="#060")
ax.text(RAIL["R-"] + 0.4, y(8), "← Poti gelb (in j)", va="center", fontsize=8.5, color="#a80")
ax.text(RAIL["R-"] + 0.4, y(7), "(A1: frei)", va="center", fontsize=8, color="#999")
ax.text(RAIL["R-"] + 0.4, y(6), "← Buzzer + (in j)", va="center", fontsize=8.5, color="#a80")
# LED-Gruppen: Pin-Reihe → EIN Widerstand 220 Ω → Verteiler-Reihe → 4 Kabel zu den 4 LEDs dieser Farbe
groups = [("grün", "#2a2", "a", 12, 15, "l"), ("rot", "#e33", "j", 12, 15, "r"), ("blau", "#36f", "j", 11, 18, "r")]
for name, col, c_pin, r_pin, r_v, side in groups:
    if name == "blau":  # Beine seitlich am roten Widerstand vorbei biegen
        xo = X[c_pin] + 0.8
        ax.plot([X[c_pin], xo, xo, X[c_pin]], [y(r_pin), y(r_pin), y(r_v), y(r_v)], color="#8a6d3b", lw=1.2, zorder=5)
        resistor(xo, r_pin + 1, xo, r_v - 1)
    else:
        resistor(X[c_pin], r_pin, X[c_pin], r_v)
    holes = list("bcde") if side == "l" else list("fghi")
    corners = ["vorne links", "hinten links", "hinten rechts", "vorne rechts"]
    for k, c in enumerate(holes):
        ax.plot([X[c]], [y(r_v)], "s", color=col, ms=7, zorder=6)
    lx = -3.4 if side == "l" else RAIL["R-"] + 0.4
    ax.text(lx, y(r_v), f"{name}: Pin → 220 Ω → Reihe {r_v}\n■ {'b–e' if side == 'l' else 'f–i'}{r_v}: Kabel zu den 4 {name}en LEDs",
            ha="right" if side == "l" else "left", va="center", fontsize=8.5, color=col)
ax.text(-3.4, y(29.6), "Kurze LED-Beine: je Ecke die 3 zusammen wickeln → 1 Kabel an Minus (4 Kabel)\n"
        "Tasten: anderes Beinchen aller 9 Tasten über EINEN Draht an Minus\n"
        "Poti: rot → Plus, grau → Minus, gelb → A0 (Reihe 8, j)", fontsize=9, va="bottom")
ax.set_xlim(-14, X["j"] + 14)
ax.set_ylim(-31.5, 2)
ax.set_aspect("equal")
ax.axis("off")
ax.set_title("Tastenbox – Steckplan (Pro Micro, Reihe 1–12). ■ = Kabel zur LED, ▭ = 220 Ω (einer je Farbe)", fontsize=12)
fig.tight_layout()
fig.savefig("steckbrett_plan.png")
