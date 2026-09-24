import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Chromium (QtWebEngine) verweigert als root den Start mit Sandbox – nur im Test-Container relevant
if hasattr(os, "geteuid") and os.geteuid() == 0:
    os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")


# Auf GitHub: fehlgeschlagene Tests zusätzlich als Anmerkung (::error::) ausgeben – die sind ohne
# Anmeldung sichtbar, die Protokolle nicht.
def pytest_runtest_logreport(report):
    if not os.environ.get("GITHUB_ACTIONS") or not report.failed:
        return
    text = str(report.longrepr).strip().splitlines()
    tail = " | ".join(line.strip() for line in text[-25:] if line.strip())
    tail = tail.replace("%", "%25").replace("\r", "").replace("\n", "%0A")
    sys.__stdout__.write(f"\n::error title={report.nodeid}::{tail[:3500]}\n")
    sys.__stdout__.flush()
