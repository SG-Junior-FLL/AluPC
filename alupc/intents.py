"""Ganz normale Sätze verstehen – ohne feste Befehlsliste.

„Mach mal bitte den Bildschirm schwarz“, „Kannst du die Kamera zeigen?“, „Licht auf blau“, „Timer auf fünf
Minuten“, „Bildschirmschoner aus“, „Wie spät ist es?“ … Statt den ganzen Satz mit festen Befehlen zu vergleichen,
sucht AluPC nach Stichwörtern (Thema), nach „an“/„aus“, nach Zahlen und Farben und nach Fragewörtern. Unscharf, damit
kleine Hörfehler nicht stören. Ergebnis ist ein Befehl wie „schwarz_an“, „rgb_farbe:#0000ff“, „timer_set:300“
oder „frage:uhrzeit“ – die Antwort baut assistant.py (sie hängt vom aktuellen Zustand ab).
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass

from .voice import COMMANDS, GAME_NAMES, fold

ON = {"an", "ein", "einschalten", "anschalten", "anmachen", "aktivieren", "aktiviere", "aktiv", "anschalte",
      "einschalte", "starte", "starten", "oeffne", "oeffnen"}
OFF = {"aus", "ausschalten", "abschalten", "ausmachen", "deaktivieren", "deaktiviere", "weg", "beenden",
       "beende", "schliessen", "schliesse", "ausschalte", "abschalte", "verschwinden", "ende", "stoppen", "stopp",
       "stop", "nicht"}
QUESTION = {"wie", "was", "wann", "welche", "welcher", "welches", "wieviel", "wo", "wer", "ob", "wird", "regnet",
            "ist", "sind", "hast", "kannst"}
SKIP = {"bitte", "mal", "doch", "jetzt", "kurz", "noch", "aeh", "aehm", "aeh", "hm", "ja", "nun", "einfach", "gerne",
        "du", "dein", "deine", "mir", "mich", "uns", "den", "die", "das", "der", "dem", "des", "ein", "eine", "einen",
        "auf", "mach", "mache", "machen", "schalte", "schalt", "stell", "stelle", "zeig", "zeige", "zeigen", "mit",
        "und", "dann", "mir", "hey", "hallo"}

NUMBERS = {"null": 0, "ein": 1, "eins": 1, "eine": 1, "einen": 1, "einer": 1, "zwei": 2, "zwo": 2, "drei": 3,
           "vier": 4, "fuenf": 5, "sechs": 6, "sieben": 7, "acht": 8, "neun": 9, "zehn": 10, "elf": 11,
           "zwoelf": 12, "dreizehn": 13, "vierzehn": 14, "fuenfzehn": 15, "sechzehn": 16, "siebzehn": 17,
           "achtzehn": 18, "neunzehn": 19, "zwanzig": 20, "dreissig": 30, "vierzig": 40, "fuenfzig": 50,
           "sechzig": 60, "siebzig": 70, "achtzig": 80, "neunzig": 90, "hundert": 100}

COLORS = {"rot": "#ff0000", "gruen": "#00ff00", "blau": "#0000ff", "gelb": "#ffd000", "orange": "#ff7000",
          "lila": "#8000ff", "violett": "#8000ff", "pink": "#ff1493", "rosa": "#ff69b4", "weiss": "#ffffff",
          "tuerkis": "#00ffc8", "cyan": "#00ffff", "magenta": "#ff00ff", "hellblau": "#40a0ff",
          "dunkelblau": "#0010a0", "warmweiss": "#ffb060"}
COLOR_NAMES = {"#ff0000": "rot", "#00ff00": "grün", "#0000ff": "blau", "#ffd000": "gelb", "#ff7000": "orange",
               "#8000ff": "lila", "#ff1493": "pink", "#ff69b4": "rosa", "#ffffff": "weiß", "#00ffc8": "türkis",
               "#00ffff": "cyan", "#ff00ff": "magenta", "#40a0ff": "hellblau", "#0010a0": "dunkelblau",
               "#ffb060": "warmweiß"}


@dataclass
class Feature:
    """Etwas, das man an- und ausschalten kann."""

    key: str  # Befehle: <key> (umschalten), <key>_an, <key>_aus
    words: tuple[str, ...]
    label: str


FEATURES = [
    Feature("schwarz", ("schwarz", "sichtschutz", "dunkel", "verdecken", "verdeck", "blackout", "abdunkeln",
                        "schwarzbild"), "Schwarz"),
    Feature("standbild", ("standbild", "einfrieren", "eingefroren", "freeze", "festhalten"), "Standbild"),
    Feature("bildschirmschoner", ("bildschirmschoner", "schoner", "screensaver"), "Bildschirmschoner"),
    Feature("overlays", ("overlays", "overlay", "einblendung", "einblendungen"), "Overlays"),
    Feature("bild_in_bild", ("bild in bild", "minivorschau", "mini vorschau", "vorschau"), "Bild-in-Bild"),
    Feature("rgb", ("rgb", "licht", "lichter", "beleuchtung", "led", "leds", "lampe", "lampen", "leuchten"),
            "RGB-Licht"),
    Feature("zuhoeren", ("mikrofon", "zuhoeren", "zuhoerst", "mikro"), "Mikrofon"),
]
TARGETS = ("bildschirm", "monitor", "monitore", "zweiter", "zweite", "anzeige", "bild", "fernseher", "beamer")

# Zeigen / Aktionen: (Stichwörter, Befehl, Anzeige) – das erste passende mit den meisten Treffern gewinnt
SHOW: list[tuple[tuple[str, ...], str, str]] = [
    (("kamera", "webcam"), "kamera", "Kamera"),
    (("wetter", "wettervorhersage"), "wetter", "Wetter & Uhr"),
    (("uhr",), "wetter", "Wetter & Uhr"),
    (("systemstatus", "system", "auslastung", "dashboard", "computerstatus"), "system", "Systemstatus"),
    (("whiteboard", "tafel"), "whiteboard", "Whiteboard"),
    (("gluecksrad", "zufallsrad", "rad"), "gluecksrad", "Glücksrad"),
    (("minispiele", "spiele", "spielen"), "spiele", "Minispiele"),
    (("abstimmung", "umfrage"), "umfrage_zeigen", "Abstimmung"),
    (("bestenliste", "rangliste", "punktestand"), "spiel_bestenliste", "Bestenliste"),
    (("airplay", "iphone", "ipad", "handy"), "airplay", "AirPlay"),
    (("spiegeln", "spiegel", "spiegle", "gespiegelt", "spiegelung"), "spiegeln", "Spiegeln"),
    (("erweitern", "erweitert", "erweiterung", "desktop"), "erweitern", "Erweitern"),
    (("musik", "lied", "song", "titel", "spotify"), "musik_zeigen", "Läuft gerade"),
    (("timer", "countdown", "stoppuhr", "wecker"), "timer_zeigen", "Timer"),
    (("qr", "qrcode", "handysteuerung"), "qr", "QR-Code"),
]


def to_number(words: list[str], i: int) -> tuple[int | None, int]:
    """Zahl ab Position i („5“, „fünf“, „fünfundzwanzig“, „zwanzig“) → (Wert, Wörter verbraucht)."""
    w = words[i]
    if w.isdigit():
        return int(w), 1
    if w in NUMBERS:
        return NUMBERS[w], 1
    if "und" in w:  # „fuenfundzwanzig“
        a, _, b = w.partition("und")
        if a in NUMBERS and b in NUMBERS and NUMBERS[a] < 10 and NUMBERS[b] >= 20:
            return NUMBERS[a] + NUMBERS[b], 1
    return None, 0


def parse_duration(words: list[str]) -> int | None:
    """„5 Minuten“, „eine halbe Stunde“, „30 Sekunden“, „zwei Minuten dreißig“ → Sekunden."""
    total, found = 0, False
    if "halbe" in words and any(w.startswith("stunde") for w in words):
        return 1800
    if "viertelstunde" in words:
        return 900
    i = 0
    while i < len(words):
        value, used = to_number(words, i)
        if value is None:
            i += 1
            continue
        unit = words[i + used] if i + used < len(words) else ""
        if unit.startswith("sek"):
            total, found = total + value, True
        elif unit.startswith("stund"):
            total, found = total + value * 3600, True
        elif unit.startswith("min") or (found and not unit):  # „zwei Minuten dreißig“
            total, found = total + value * (60 if unit.startswith("min") else 1), True
        i += used + 1
    return total if found and total > 0 else None


def _like(word: str, key: str) -> bool:
    if word == key:
        return True
    if len(key) <= 4:  # kurze Wörter nur genau („aus“ ≠ „haus“)
        return False
    if len(key) >= 6 and word.startswith(key):  # „bildschirmschoners“
        return True
    if abs(len(word) - len(key)) > 2:  # „frage“ ≠ „umfrage“
        return False
    return difflib.SequenceMatcher(None, word, key).ratio() >= 0.82


def has(words: list[str], key: str) -> bool:
    """Kommt das Stichwort (auch mehrteilig, unscharf) im Satz vor?"""
    parts = key.split()
    if len(parts) == 1:
        return any(_like(w, key) for w in words)
    n = len(parts)
    for i in range(len(words) - n + 1):
        if all(_like(words[i + k], parts[k]) for k in range(n)):
            return True
    return _like("".join(words), "".join(parts)) if len(words) <= n + 1 else False


def any_of(words: list[str], keys) -> bool:
    return any(has(words, k) for k in keys)


def switch(words: list[str]) -> str | None:
    """'an', 'aus' oder None – das LETZTE Schaltwort zählt („nicht mehr an“ → aus)."""
    state = None
    for i, w in enumerate(words):
        if w in ON or any(_like(w, k) for k in ("einschalten", "anschalten", "aktivieren")):
            state = "an"
        if w in OFF or any(_like(w, k) for k in ("ausschalten", "abschalten", "deaktivieren")):
            state = "aus"
        if w in ("nicht", "kein", "keine", "keinen") and "mehr" in words[i + 1:]:
            state = "aus"
    return state


def is_question(words: list[str]) -> bool:
    return bool(words) and (words[0] in QUESTION or "wieviel" in words or "wie viel" in " ".join(words))


# --------------------------------------------------------------------------- Fragen & Plaudern
def question(words: list[str]) -> tuple[str, str] | None:
    s = " ".join(words)
    q = is_question(words)
    if any(p in s for p in ("wie spaet", "wieviel uhr", "wie viel uhr", "uhrzeit", "welche zeit")):
        return "frage:uhrzeit", "Uhrzeit"
    if any(p in s for p in ("welcher tag", "welches datum", "datum", "der wievielte", "den wievielten",
                            "wochentag", "welchen tag")):
        return "frage:datum", "Datum"
    if q and any_of(words, ("temperatur", "warm", "heiss", "grad", "kalt")) and \
            any_of(words, ("prozessor", "cpu", "computer", "pc", "rechner", "grafikkarte", "system")):
        return "frage:temperatur", "Temperatur"
    if (q and any_of(words, ("wetter", "regnet", "regen", "draussen", "sonne", "schnee", "kalt", "warm"))) or \
            any(p in s for p in ("wird es regnen", "wie wird das wetter", "wie ist das wetter")):
        return "frage:wetter", "Wetter"
    if q and any_of(words, ("auslastung", "ausgelastet", "speicher", "arbeitsspeicher", "ram", "prozessor", "cpu")) or \
            any(p in s for p in ("wie geht es dem computer", "wie gehts dem computer", "wie geht es dem pc",
                                 "wie geht es dem rechner")):
        return "frage:system", "Systemstatus"
    if any(p in s for p in ("was laeuft", "welches lied", "welcher song", "wer singt", "was ist das fuer ein lied",
                            "was spielt")):
        return "frage:musik", "Läuft gerade"
    if any(p in s for p in ("was kannst du", "hilfe", "welche befehle", "was kann ich sagen", "wie funktioniert")):
        return "frage:hilfe", "Hilfe"
    if any(p in s for p in ("wie geht es dir", "wie gehts", "wie geht s", "alles gut bei dir", "wie geht es ihnen")):
        return "frage:befinden", "Plaudern"
    if any(p in s for p in ("wer bist du", "wie heisst du", "was bist du")):
        return "frage:wer", "Plaudern"
    if "witz" in words or "witze" in words:
        return "frage:witz", "Witz"
    if words and words[0] in ("danke", "dankeschoen", "vielen") and len(words) <= 3:
        return "frage:danke", "Danke"
    if s in ("hallo", "hi", "guten morgen", "guten tag", "guten abend", "servus", "moin", "hey"):
        return "frage:hallo", "Hallo"
    return None


# --------------------------------------------------------------------------- verstehen
def understand(words: list[str], scenes: list[str] | None = None,
               custom: list[dict] | None = None) -> tuple[str, str] | None:
    """Gefaltete Wörter (ohne Startwort) → (Befehl, Anzeige) oder None."""
    words = [w for w in words if w]
    if not words:
        return None
    said = " ".join(words)
    core = [w for w in words if w not in SKIP]
    # 1) eigene Sätze zuerst (ganzer Satz ähnlich oder darin enthalten)
    best = (0.0, None)
    for c in custom or []:
        say = fold(c.get("say", ""))
        if not say or not c.get("do"):
            continue
        score = difflib.SequenceMatcher(None, said, say).ratio()
        if len(say.split()) >= 2 and f" {say} " in f" {said} ":
            score = 1.0
        if score > best[0]:
            best = (score, c)
    if best[0] >= 0.8:
        return best[1]["do"], f"„{best[1]['say']}“"
    # 2) Fragen und Plaudern
    hit = question(words)
    if hit:
        return hit
    # 3) Minispiel per Name („Spiel Pong“, „lass uns Pong spielen“)
    for key, names in GAME_NAMES.items():
        if any(has(words, fold(n)) for n in names) and (any_of(words, ("spiel", "spielen", "starte", "nimm", "waehle"))
                                                         or len(core) == 1):
            from .games import GAMES

            if not (key == "malen" and has(words, "whiteboard")):
                return f"spiel:{key}", f"Minispiel: {GAMES[key].title}"
    # 4) Szene per Name
    if any(_like(w, "szene") for w in words) and scenes:
        folded = {fold(n): n for n in scenes}
        after = said.split("szene", 1)[1].strip() if "szene" in said else ""
        for cand in (after, " ".join(core)):
            hit_name = difflib.get_close_matches(cand, list(folded), n=1, cutoff=0.6) if cand else []
            if hit_name:
                name = folded[hit_name[0]]
                return f"szene:{name}", f"Szene „{name}“"
        for f_name, name in folded.items():
            if f_name and f" {f_name} " in f" {said} ":
                return f"szene:{name}", f"Szene „{name}“"
    if any_of(words, ("szene", "szenen")):
        if any_of(words, ("naechste", "naechster", "weiter", "vor")):
            return "naechste_szene", "Nächste Szene"
        if any_of(words, ("vorherige", "zurueck", "letzte", "vorige")):
            return "vorherige_szene", "Vorherige Szene"
    state = switch(words)
    # 5) Licht / RGB: Farben, heller, dunkler, „wie der Bildschirm“
    light = any_of(words, FEATURES[5].words)
    color = next((COLORS[w] for w in words if w in COLORS), None)
    if light or (color and not any_of(words, ("szene", "whiteboard", "hintergrund"))):
        if color:
            return f"rgb_farbe:{color}", f"Licht {COLOR_NAMES.get(color, '')}".strip()
        if any_of(words, ("heller", "hell")):
            return "rgb_heller", "Licht heller"
        if any_of(words, ("dunkler",)):
            return "rgb_dunkler", "Licht dunkler"
        if light and any_of(words, ("bildschirm", "monitor", "passend", "bild")) and state != "aus":
            return "rgb_monitor2", "Licht wie Monitor 2"
    # 6) Timer mit Dauer und Steuerung
    if any_of(words, ("timer", "countdown", "stoppuhr", "wecker")) or (parse_duration(words) and
                                                                      any_of(words, ("stell", "stelle", "minuten"))):
        seconds = parse_duration(words)
        if seconds:
            return f"timer_set:{seconds}", "Timer"
        if any_of(words, ("neu", "zuruecksetzen", "neustart", "nochmal", "reset", "zurueck")):
            return "timer_neustart", "Timer neu"
        if any_of(words, ("verlaengern", "plus", "mehr", "laenger")):
            return "timer_plus", "Timer +1 Minute"
        if any_of(words, ("minus", "weniger", "kuerzer")):
            return "timer_minus", "Timer −1 Minute"
        if any_of(words, ("pause", "anhalten", "stopp", "stop", "stoppen", "halt")):
            return "timer_pause", "Timer Pause"
        if any_of(words, ("start", "starten", "starte", "los", "weiter", "fortsetzen")):
            return "timer_start", "Timer läuft"
    # 7) Musik steuern
    if any_of(words, ("musik", "lied", "song", "titel", "spotify", "track")) or said in ("pause", "weiter spielen"):
        if any_of(words, ("naechste", "naechstes", "naechster", "ueberspringen", "skip")):
            return "musik_weiter", "Nächstes Lied"
        if any_of(words, ("vorherige", "vorheriges", "letzte", "letztes", "zurueck")):
            return "musik_zurueck", "Vorheriges Lied"
        if any_of(words, ("pause", "anhalten", "stopp", "stop", "stoppen", "aus", "leise")):
            return "musik_pause", "Musik Pause"
        if any_of(words, ("weiter", "abspielen", "spielen", "play", "fortsetzen", "an")):
            return "musik_play", "Musik läuft"
    # 8) Schalter: Thema + an/aus
    for f in FEATURES:
        if f.key == "rgb" and not light:
            continue
        if any_of(words, f.words):
            if f.key == "schwarz" and state is None:
                if any_of(words, ("mach", "mache", "machen", "werden", "bitte")) or any_of(words, TARGETS):
                    return "schwarz_an", "Schwarz"  # „Mach den Bildschirm schwarz“ = schwarz machen
                return "schwarz", "Schwarz"  # nur „schwarz“ = umschalten (wie bisher)
            if f.key == "zuhoeren":
                if any_of(words, ("hoer auf", "aufhoeren", "nicht mehr")) or ("auf" in words and "hoer" in words):
                    state = "aus"
                elif state is None:
                    state = "an" if any_of(words, ("zuhoeren", "zuhoerst")) else None
            if state:
                return f"{f.key}_{state}", f"{f.label} {state}"
            return f.key, f.label
    if any_of(words, ("hoer auf", "hoer weg", "nicht mehr zuhoeren")):
        return "zuhoeren_aus", "Mikrofon aus"
    if "hoer" in words and "zu" in words:  # „Hör mir zu“
        return "zuhoeren_an", "Mikrofon an"
    # „Bildschirm aus“ = schwarz machen, „Bildschirm an“ / „Bild zurück“ = wieder zeigen
    if any_of(words, TARGETS):
        if state == "aus":
            return "schwarz_an", "Schwarz"
        if state == "an" or any_of(words, ("zurueck", "wieder")):
            return "schwarz_aus", "Bild wieder da"
    # 9) Glücksrad drehen, Spiel starten, Zeichnungen löschen, sperren
    if any_of(words, ("drehen", "dreh", "drehe")) and (any_of(words, ("rad", "gluecksrad")) or len(core) <= 2):
        return "gluecksrad_drehen", "Glücksrad drehen"
    if any_of(words, ("zeichnung", "zeichnungen", "gekritzel", "gemalte")) and \
            any_of(words, ("loeschen", "weg", "entfernen", "wegmachen", "loesche")):
        return "zeichnungen_loeschen", "Zeichnungen löschen"
    if any_of(words, ("computer", "pc", "rechner", "bildschirm")) and any_of(words, ("sperren", "sperre", "sperr")):
        return "sperren", "Computer sperren"
    if any_of(words, ("abstimmung", "umfrage")) and any_of(words, ("beenden", "ende", "ergebnis", "schliessen")):
        return "umfrage_ende", "Abstimmung beenden"
    if any_of(words, ("spiel", "runde")) and any_of(words, ("starten", "start", "starte", "los", "beginnen")):
        return "spiel_start", "Minispiel starten"
    if any(has(words, p) for p in ("naechste frage", "naechste runde", "naechstes bild", "spiel weiter")):
        return "spiel_weiter", "Minispiel: weiter"
    # 10) Zeigen: Thema mit den meisten Treffern
    best_show, best_hits = None, 0
    for keys, command, label in SHOW:
        hits = sum(1 for k in keys if has(words, k))
        if hits > best_hits:
            best_show, best_hits = (command, label), hits
    if best_show:
        command, label = best_show
        if command == "spiele" and state == "aus":
            return "spiel_ende", "Minispiel beenden"
        return best_show
    # 11) alte feste Sätze irgendwo im Satz (Minispiel-Befehle, „nächste Frage“ …)
    best, best_score = None, 0.0
    for variants, command, label in COMMANDS:
        for v in variants:
            vf = fold(v)
            n = len(vf.split())
            if n > len(core) + 1:
                continue
            if vf == " ".join(core) or (n >= 2 and has(words, vf)):
                score = n + (1 if vf == " ".join(core) else 0)
            elif len(core) <= 2 and len(vf) > 5:
                score = difflib.SequenceMatcher(None, " ".join(core), vf).ratio()
                score = score if score >= 0.8 else 0
            else:
                continue
            if score > best_score:
                best, best_score = (command, label), score
    return best
