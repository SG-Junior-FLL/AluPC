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
    ok, msg = dt.apply(False)
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
