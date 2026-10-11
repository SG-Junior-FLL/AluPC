"""Windows-CI: AluPC-Farben für den Desktop ECHT setzen (Registry des Benutzers) und wieder zurückstellen."""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main() -> int:
    from PySide6.QtWidgets import QApplication

    QApplication([])
    from alupc import desktop_theme as dt
    from alupc.ui.theme import make_theme

    state = Path(tempfile.mkdtemp()) / "desktop-theme.json"
    dt._state_file = lambda: state
    before = dt._win_read()
    mode_before, wall_before = dt._win_mode_read(), dt._win_wallpaper_read()
    dt.wallpaper_path = lambda: Path(tempfile.mkdtemp()) / "hintergrund.png"
    ok, msg = dt.apply(True)
    mode_after = dt._win_mode_read()
    if mode_after != {"AppsUseLightTheme": 0, "SystemUsesLightTheme": 0}:
        print(f"::error title=Desktop-Design (Windows)::Dunkel nicht gesetzt: {mode_after}")
        return 1
    print(f"::notice title=Desktop-Design (Windows)::{msg} · Hintergrundbild jetzt: {dt._win_wallpaper_read()}")
    dt.restore()
    if dt._win_mode_read() != mode_before or dt._win_wallpaper_read() != wall_before:
        print(f"::error title=Desktop-Design (Windows)::Zurück unvollständig: {dt._win_mode_read()} / "
              f"{dt._win_wallpaper_read()!r} statt {mode_before} / {wall_before!r}")
        return 1
    ok, msg = dt.apply(False, mode=False, wallpaper=False)
    after = dt._win_read()
    want = dt.windows_values(make_theme("hell", "alupc").accent)
    errors = []
    if not ok:
        errors.append(f"anwenden: {msg}")
    for full, entry in after.items():
        name = full.split("|", 1)[1]
        value = entry[0] if entry else None
        expected = want[name].hex() if isinstance(want[name], bytes) else want[name]
        if value != expected:
            errors.append(f"{name}: {value!r} statt {expected!r}")
    ok, msg = dt.restore()
    if not ok or dt._win_read() != before:
        errors.append(f"zurück: {msg} – vorher {before} / jetzt {dt._win_read()}")
    for e in errors:
        print(f"::error title=Desktop-Farben (Windows)::{e}")
    if not errors:
        print("::notice title=Desktop-Farben (Windows)::Akzentfarbe gesetzt (6 Werte geprüft) und genau wie vorher "
              "zurückgestellt")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
