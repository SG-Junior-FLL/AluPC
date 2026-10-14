"""Kahoot (das echte, kahoot.com) auf Monitor 2: Gastgeber-Seite als Website, bedient am PC über „Browser steuern“.

AluPC baut kein eigenes Kahoot nach: Monitor 2 zeigt create.kahoot.it bzw. direkt die Gastgeber-Seite eines Quiz
(play.kahoot.it/v2/?quizId=…). Anmelden, Quiz wählen, Starten und Weiter geht am PC im Fenster „Browser steuern“ –
die Anmeldung bleibt gespeichert (eigenes Browser-Profil). Die Mitspieler öffnen kahoot.it am Handy und geben die PIN
von Monitor 2 ein – dafür brauchen die Handys Internet (das AluPC-WLAN hat Internet, wenn der PC welches hat).
"""

from __future__ import annotations

import re

CREATE = "https://create.kahoot.it/"
PLAY = "https://play.kahoot.it/v2/?quizId={}"
_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)


def host_url(text: str = "") -> str:
    """Eingabe → Adresse für Monitor 2. Leer = Kahoot-Startseite (anmelden, Quiz wählen). Ein Kahoot-Link
    (…/details/<id>, …/share/<name>/<id>, play.kahoot.it/…quizId=<id>) oder nur die Quiz-ID → gleich die
    Gastgeber-Seite dieses Quiz. Andere Adressen von kahoot.it/kahoot.com bleiben, wie sie sind."""
    text = (text or "").strip()
    if not text:
        return CREATE
    m = _UUID.search(text)
    if m:
        return PLAY.format(m.group(0).lower())
    if re.match(r"^(https?://)?([a-z0-9-]+\.)*kahoot\.(it|com)(/|$)", text, re.I):
        return text if text.startswith("http") else "https://" + text
    return CREATE
