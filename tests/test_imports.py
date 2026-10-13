"""Späte Importe (`from .modul import name` in Funktionen) zeigen auf etwas, das es gibt. Solche Fehler fallen sonst
erst auf, wenn genau diese Funktion läuft – z. B. beim Installieren unter Windows (0.137: entfernte Hilfsfunktion)."""

import ast
import importlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1] / "alupc"


def _imports():
    for path in sorted(ROOT.rglob("*.py")):
        mod = ".".join(("alupc",) + path.relative_to(ROOT).with_suffix("").parts)
        if mod.endswith(".__init__"):
            mod = mod[: -len(".__init__")]
        package = mod if path.name == "__init__.py" else mod.rsplit(".", 1)[0]
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and node.level:
                base = package.split(".")
                base = base[: len(base) - (node.level - 1)]
                target = ".".join(base + ([node.module] if node.module else []))
                for alias in node.names:
                    yield f"{path.name}:{node.lineno}", target, alias.name


def _defined_in_source(target: str, name: str) -> bool:
    """Name irgendwo im Modul definiert (auch unter „if IS_WINDOWS:“ – unter Linux dann nicht als Attribut da)."""
    path = ROOT.parent / (target.replace(".", "/") + ".py")
    if not path.exists():
        path = ROOT.parent / target.replace(".", "/") / "__init__.py"
    if not path.exists():
        return False
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == name:
            return True
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return True
        if isinstance(node, (ast.Import, ast.ImportFrom)) and any((a.asname or a.name) == name for a in node.names):
            return True
    return False


def test_every_relative_import_exists():
    missing = []
    for where, target, name in _imports():
        try:
            module = importlib.import_module(target)
        except ImportError as exc:  # nur unter Windows ladbar (winreg, ctypes.windll …) – Modul selbst gibt es
            if (ROOT.parent / (target.replace(".", "/") + ".py")).exists() or \
                    (ROOT.parent / target.replace(".", "/") / "__init__.py").exists():
                continue
            missing.append(f"{where}: Modul {target} fehlt ({exc})")
            continue
        if hasattr(module, name) or _defined_in_source(target, name):
            continue
        try:
            importlib.import_module(f"{target}.{name}")  # Untermodul
        except ImportError:
            missing.append(f"{where}: {target}.{name} gibt es nicht")
    assert not missing, "\n".join(missing)


def test_driver_install_builds_encoded_script(monkeypatch):
    from alupc import drivers

    monkeypatch.setattr(drivers, "IS_WINDOWS", True)
    seen = []
    ok, _msg = drivers.install(["vbcable"], elevated=True,
                               run=lambda cmd, **kw: seen.append(cmd) or type("R", (), {"stdout": "", "stderr": "",
                                                                                        "returncode": 0})())
    assert ok and seen and seen[0][-2] == "-EncodedCommand"


if __name__ == "__main__":
    pytest.main([__file__])
