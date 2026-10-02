"""Sprachassistent: führt verstandene Sätze aus und antwortet natürlich – passend zum Zustand.

„Mach den Bildschirm schwarz“ → „Alles klar, Monitor 2 ist jetzt schwarz.“ – und wenn er schon schwarz ist:
„Monitor 2 ist schon schwarz.“ Fragen („Wie spät ist es?“, „Wie warm ist der Prozessor?“, „Wie wird das Wetter?“)
bekommen eine echte Antwort. Nach jeder Antwort hört AluPC ein paar Sekunden ohne Startwort weiter (Nachfragen).
"""

from __future__ import annotations

import random
import sys
import time

from .intents import COLOR_NAMES
from .speech import spoken_label

ACK = ("Okay.", "Alles klar.", "Mach ich.", "Gern.")
WEEKDAYS = ("Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag")
MONTHS = ("Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober",
          "November", "Dezember")
ORDINALS = ("ersten", "zweiten", "dritten", "vierten", "fünften", "sechsten", "siebten", "achten", "neunten",
            "zehnten", "elften", "zwölften", "dreizehnten", "vierzehnten", "fünfzehnten", "sechzehnten",
            "siebzehnten", "achtzehnten", "neunzehnten", "zwanzigsten", "einundzwanzigsten", "zweiundzwanzigsten",
            "dreiundzwanzigsten", "vierundzwanzigsten", "fünfundzwanzigsten", "sechsundzwanzigsten",
            "siebenundzwanzigsten", "achtundzwanzigsten", "neunundzwanzigsten", "dreißigsten",
            "einunddreißigsten")
JOKES = (
    "Warum können Geister so schlecht lügen? Weil man durch sie hindurchsieht.",
    "Was ist rot und schlecht für die Zähne? Ein Ziegelstein.",
    "Treffen sich zwei Monitore. Sagt der eine: Du siehst heute aber blass aus. Sagt der andere: Ich bin halt "
    "im Energiesparmodus.",
    "Wie nennt man einen Bumerang, der nicht zurückkommt? Stock.",
    "Warum war der Computer müde? Er hatte zu viele Fenster offen.",
)
NOT_UNDERSTOOD = ("Das habe ich nicht verstanden.", "Wie bitte?", "Sag das bitte noch mal anders.")
HELP = ("Sag zum Beispiel: Mach den Bildschirm schwarz. Zeig die Kamera. Licht auf blau. Timer auf fünf Minuten. "
        "Bildschirmschoner aus. Oder frag mich, wie spät es ist.")

# (an, aus, schon an, schon aus)
FLAG_TEXT = {
    "schwarz": ("Monitor 2 ist jetzt schwarz.", "Das Bild ist wieder da.", "Monitor 2 ist schon schwarz.",
                "Monitor 2 ist gar nicht schwarz."),
    "standbild": ("Das Bild ist eingefroren.", "Das Bild läuft wieder.", "Das Standbild ist schon an.",
                  "Es ist kein Standbild an."),
    "bildschirmschoner": ("Der Bildschirmschoner läuft.", "Der Bildschirmschoner ist aus.",
                          "Der Bildschirmschoner läuft schon.", "Der Bildschirmschoner ist schon aus."),
    "bild_in_bild": ("Bild-in-Bild ist an.", "Bild-in-Bild ist aus.", "Bild-in-Bild ist schon an.",
                     "Bild-in-Bild ist schon aus."),
    "overlays": ("Die Overlays sind an.", "Die Overlays sind aus.", "Die Overlays sind schon an.",
                 "Die Overlays sind schon aus."),
    "rgb": ("Das Licht ist an.", "Das Licht ist aus.", "Das Licht ist schon an.", "Das Licht ist schon aus."),
}
SHOW_TEXT = {
    "kamera": "Hier ist die Kamera.", "wetter": "Hier ist das Wetter.", "system": "Hier ist der Systemstatus.",
    "whiteboard": "Das Whiteboard ist da.", "gluecksrad": "Hier ist das Glücksrad.",
    "gluecksrad_drehen": "Und los!", "spiele": "Die Minispiele sind bereit. Scannt den QR-Code.",
    "umfrage_zeigen": "Hier ist die Abstimmung.", "umfrage_ende": "Die Abstimmung ist beendet.",
    "spiel_bestenliste": "Hier ist die Bestenliste.", "airplay": "AirPlay ist bereit.",
    "spiegeln": "Monitor 2 spiegelt jetzt.", "erweitern": "Monitor 2 ist jetzt erweitert.",
    "musik_zeigen": "Hier ist die Musik.", "timer_zeigen": "Hier ist der Timer.", "qr": "Hier ist der QR-Code.",
    "naechste_szene": "Nächste Szene.", "vorherige_szene": "Vorherige Szene.", "timer_start": "Der Timer läuft.",
    "timer_pause": "Timer angehalten.", "timer_neustart": "Der Timer startet neu.",
    "timer_plus": "Eine Minute mehr.", "timer_minus": "Eine Minute weniger.", "musik_weiter": "Nächstes Lied.",
    "musik_zurueck": "Vorheriges Lied.", "musik_pause": "Pause.", "musik_play": "Weiter geht's.",
    "rgb_heller": "Etwas heller.", "rgb_dunkler": "Etwas dunkler.",
    "rgb_monitor2": "Das Licht folgt jetzt Monitor 2.", "zeichnungen_loeschen": "Die Zeichnungen sind weg.",
    "sperren": "Der Computer wird gesperrt.", "spiel_start": "Los geht's!", "spiel_weiter": "Weiter.",
    "spiel_ende": "Hier ist das Ergebnis.", "spiel_lobby": "Zurück zur Lobby.", "spiel_teams": "Teams gemischt.",
}


def say_duration(seconds: int) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    parts = []
    if h:
        parts.append("eine Stunde" if h == 1 else f"{h} Stunden")
    if m:
        parts.append("eine Minute" if m == 1 else f"{m} Minuten")
    if s:
        parts.append("eine Sekunde" if s == 1 else f"{s} Sekunden")
    return " und ".join(parts) or "null Sekunden"


def say_time(t: time.struct_time) -> str:
    if t.tm_min == 0:
        return f"Es ist genau {t.tm_hour} Uhr."
    return f"Es ist {t.tm_hour} Uhr {t.tm_min}."


def say_date(t: time.struct_time) -> str:
    return f"Heute ist {WEEKDAYS[t.tm_wday]}, der {ORDINALS[t.tm_mday - 1]} {MONTHS[t.tm_mon - 1]}."


def say_weather(data: dict, place: str = "") -> str:
    from .weather import describe

    text = describe(data["code"])[0]
    where = f" in {place}" if place else ""
    out = f"Gerade sind es{where} {round(data['temp'])} Grad, {text.lower()}."
    if data.get("days"):
        today = data["days"][0]
        out += f" Heute höchstens {round(today['max'])}, tiefstens {round(today['min'])} Grad."
    return out


class Assistant:
    def __init__(self, controller):
        self.c = controller
        self.random = random.Random()

    # ------------------------------------------------------------ Zustand
    def flag(self, key: str) -> bool:
        c = self.c
        if key == "schwarz":
            return bool(c.privacy)
        if key == "standbild":
            return bool(c.frozen)
        if key == "bildschirmschoner":
            return bool(c.screensaver.active)
        if key == "bild_in_bild":
            return bool(c.pip is not None and c.pip.isVisible())
        if key == "overlays":
            return bool(c.config["overlays"].get("on"))
        if key == "rgb":
            return c.rgb.settings()["mode"] != "aus"
        return False

    def ack(self) -> str:
        return self.random.choice(ACK)

    # ------------------------------------------------------------ Befehl → Antwort
    def handle(self, command: str, label: str, text: str = "") -> str:
        """Ausführen und die gesprochene Antwort zurückgeben (wird auch gleich gesagt). Geht etwas schief, sagt
        AluPC das – mit Grund statt stiller oder „unbekannter“ Fehler."""
        c = self.c
        messages: list[str] = []
        catch = messages.append
        c.message.connect(catch)  # Meldungen während des Befehls („Kein zweiter Monitor“ …) mitlesen
        try:
            reply = self._run(command, label)
        except Exception as exc:  # noqa: BLE001 – ein Sprachbefehl darf AluPC nie stören
            c.voice._note_error(exc)
            reply = "Das hat leider nicht geklappt."
            c.message.emit(f"🎤 Fehler bei „{label}“: {type(exc).__name__}: {exc}")
        finally:
            try:
                c.message.disconnect(catch)
            except (RuntimeError, TypeError):
                pass
        problem = next((m for m in messages if any(w in m.lower() for w in ("kein", "nicht", "fehl", "geht nicht"))),
                       "")
        if problem and not command.startswith("frage:"):
            reply = f"Das ging nicht: {problem.rstrip('.')}."
        if reply:
            c.speaker.say(reply)
        if command != "zuhoeren_aus":
            c.voice.listen_on()
        return reply

    def _run(self, command: str, label: str) -> str:
        c = self.c
        if command.startswith("frage:"):
            return self.answer(command[6:])
        base, _, state = command.rpartition("_")
        if state in ("an", "aus") and base in FLAG_TEXT:
            want = state == "an"
            if self.flag(base) == want:
                return FLAG_TEXT[base][2 if want else 3]
            c.run_command(command)
            if base != "rgb" and self.flag(base) != want:  # hat nicht geklappt (Grund kommt als Meldung)
                return f"{FLAG_TEXT[base][0 if want else 1].rstrip('.')} – das ging gerade nicht."
            return f"{self.ack()} {FLAG_TEXT[base][0 if want else 1]}"
        if command in FLAG_TEXT:  # nur umschalten
            before = self.flag(command)
            c.run_command(command)
            if command != "rgb" and self.flag(command) == before:
                return "Das ging gerade nicht."
            return f"{self.ack()} {FLAG_TEXT[command][1 if before else 0]}"
        if command in ("zuhoeren_an", "zuhoeren_aus"):
            c.run_command(command)
            if command == "zuhoeren_an":
                return "Ich höre zu – du brauchst kein Startwort." if c.voice.direct else ""
            return "Okay, ich höre nur noch auf das Startwort." if c.config["voice"].get("on") else \
                "Mikrofon ist aus."
        c.run_command(command)
        return self.done_text(command, label)

    def done_text(self, command: str, label: str) -> str:
        if command in SHOW_TEXT:
            return SHOW_TEXT[command]
        if command.startswith("rgb_farbe:"):
            return f"{self.ack()} Das Licht ist jetzt {COLOR_NAMES.get(command[10:], 'in der Farbe')}."
        if command.startswith("timer_set:"):
            return f"{self.ack()} Timer auf {say_duration(int(command[10:]))}."
        if command.startswith("szene:"):
            return f"Szene {command[6:]}."
        if command.startswith("spiel:"):
            return f"{self.ack()} {spoken_label(label).replace('Minispiel: ', '')}."
        return f"{self.ack()} {spoken_label(label)}."

    def not_understood(self, text: str) -> str:
        reply = self.random.choice(NOT_UNDERSTOOD)
        self.c.speaker.say(reply)
        self.c.voice.listen_on()
        return reply

    # ------------------------------------------------------------ Fragen
    def answer(self, kind: str) -> str:
        now = time.localtime()
        if kind == "ja":
            return "Ja?"
        if kind == "uhrzeit":
            return say_time(now)
        if kind == "datum":
            return say_date(now)
        if kind == "wetter":
            return self._weather()
        if kind == "temperatur":
            return self._temperature()
        if kind == "system":
            return self._system()
        if kind == "musik":
            try:
                from .now_playing_view import feed

                t = feed().track
            except Exception:  # noqa: BLE001
                t = None
            if t is None or not t.title:
                return "Ich sehe gerade keine Musik."
            return f"Gerade läuft {t.title}" + (f" von {t.artist}." if t.artist else ".")
        if kind == "hilfe":
            return HELP
        if kind == "befinden":
            return "Mir geht's gut, danke! Und dir?"
        if kind == "wer":
            return "Ich bin AluPC. Ich steuere deinen zweiten Monitor – und ein bisschen mehr."
        if kind == "witz":
            return self.random.choice(JOKES)
        if kind == "danke":
            return "Gern geschehen."
        if kind == "hallo":
            return "Hallo! Was kann ich für dich tun?"
        return ""

    def _weather(self) -> str:
        cfg = self.c.config["weather"]
        if "lat" not in cfg:
            return "Für das Wetter brauche ich erst einen Ort. Den stellst du an der Kachel Wetter ein."
        from .weather import service

        svc = service(self.c.config)
        data = svc.data
        if data and time.time() - data.get("fetched", 0) < 3600:
            return say_weather(data, cfg.get("name", ""))

        def arrived(*_):
            try:
                svc.updated.disconnect(arrived)
            except (RuntimeError, TypeError):
                pass
            if svc.data:
                self.c.speaker.say(say_weather(svc.data, cfg.get("name", "")))
                self.c.voice.listen_on()

        svc.updated.connect(arrived)
        svc.refresh()
        return "Moment, ich schaue nach."

    def _temperature(self) -> str:
        from . import sysinfo

        if sys.platform.startswith("linux"):
            from .platform import fans

            temp = sysinfo.pick_cpu_temp(fans.read_sensors())
            if temp is not None:
                return f"Der Prozessor hat {round(temp)} Grad." + (" Ganz schön warm!" if temp >= 80 else "")
        gpu = sysinfo.Sampler().read_gpu(time.monotonic()) if sysinfo.psutil else None
        if gpu is not None and gpu.temp is not None:
            return f"Die Grafikkarte hat {round(gpu.temp)} Grad. Die Prozessor-Temperatur meldet mir das System nicht."
        if sys.platform == "win32":
            return "Die Prozessor-Temperatur meldet mir Windows leider nicht."
        return "Ich finde keinen Temperatur-Sensor."

    def _system(self) -> str:
        from . import sysinfo

        if sysinfo.psutil is None:
            return "Das kann ich gerade nicht messen."
        cpu = sysinfo.psutil.cpu_percent(interval=0.25)
        ram = sysinfo.psutil.virtual_memory().percent
        mood = "Alles entspannt." if cpu < 50 and ram < 80 else "Der Computer hat gut zu tun."
        return f"Der Prozessor ist zu {round(cpu)} Prozent ausgelastet, der Arbeitsspeicher zu {round(ram)} " \
               f"Prozent. {mood}"
