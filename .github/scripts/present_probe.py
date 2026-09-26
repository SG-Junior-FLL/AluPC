"""CI (Windows, echter Desktop): Legt AluPC ein fremdes Fenster wirklich randlos und im Vordergrund über einen
Monitor? (So wird das iPhone-Bild von UxPlay auf Monitor 2 gelegt.) Ergebnis als GitHub-Hinweis."""

import ctypes
import os
import sys
import time
from ctypes import wintypes

sys.path.insert(0, os.getcwd())

from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from alupc.platform.windows_windows import GWL_STYLE, WS_CAPTION, WindowsWindowBackend  # noqa: E402


def note(text: str) -> None:
    print(f"::notice title=Fenster-Probe::{text}", flush=True)


app = QApplication([])
w = QWidget()
w.setWindowTitle("AluPC CI-Test")
w.setGeometry(100, 100, 400, 300)
w.show()
for _ in range(50):
    app.processEvents()
    time.sleep(0.02)
screen = app.primaryScreen()
g = screen.geometry()
backend = WindowsWindowBackend()
found = [x for x in backend.list_windows() if x.title == "AluPC CI-Test"]
note(f"Fenster in der Liste gefunden: {bool(found)}")
hwnd = int(found[0].id) if found else int(w.winId())
backend.present_window(str(hwnd), screen.name(), (g.x(), g.y(), g.width(), g.height()))
for _ in range(50):
    app.processEvents()
    time.sleep(0.02)
rect = wintypes.RECT()
ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_STYLE)
exstyle = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
dpr = screen.devicePixelRatio()
note(f"Monitor {screen.name()} {g.width()}x{g.height()} (Skalierung {dpr}) · Fenster jetzt "
     f"{rect.left},{rect.top} {rect.right - rect.left}x{rect.bottom - rect.top} · "
     f"Titelleiste weg: {not (style & WS_CAPTION)} · immer vorne: {bool(exstyle & 0x8)}")
