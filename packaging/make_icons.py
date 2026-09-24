"""Erzeugt die Programmsymbole in allen Größen (alupc/resources/icons/alupc-GRÖSSE.png) aus app_icon().

Aufruf (einmalig nach Änderungen am Logo): QT_QPA_PLATFORM=offscreen python packaging/make_icons.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication([])
from alupc.ui.icons import ICON_SIZES, render_app_icon  # noqa: E402

out = ROOT / "alupc" / "resources" / "icons"
out.mkdir(parents=True, exist_ok=True)
for size in ICON_SIZES:
    render_app_icon(size).save(str(out / f"alupc-{size}.png"))
render_app_icon(256).save(str(ROOT / "alupc" / "resources" / "alupc.png"))
print("fertig:", ", ".join(str(s) for s in ICON_SIZES))
