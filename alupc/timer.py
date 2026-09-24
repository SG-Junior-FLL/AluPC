"""Ein gemeinsamer Timer (Countdown oder Stoppuhr), der unabhängig von der Anzeige weiterläuft.

Früher startete jede Countdown-Anzeige ihre eigene Zeit – wurde die Szene neu aufgebaut
(Bearbeiten, Szene erneut zeigen …), begann der Countdown von vorn. Jetzt gibt es genau
einen Timer; alle Anzeigen zeigen ihn nur an. Steuerbar über Kachel und Tastenkürzel.
"""

from __future__ import annotations

import time


class TimerClock:
    def __init__(self):
        self.mode = "countdown"  # "countdown" oder "stoppuhr"
        self.duration = 5 * 60.0  # Sekunden (nur Countdown)
        self._started: float | None = None  # monotone Zeit des (Wieder-)Starts
        self._accumulated = 0.0  # bereits gelaufene Sekunden vor der letzten Pause
        self.finished_text = "Zeit ist um!"

    # ------------------------------------------------------------ Zustand
    @property
    def running(self) -> bool:
        return self._started is not None

    def elapsed(self) -> float:
        extra = time.monotonic() - self._started if self._started is not None else 0.0
        return self._accumulated + extra

    def remaining(self) -> float:
        return max(0.0, self.duration - self.elapsed())

    def finished(self) -> bool:
        return self.mode == "countdown" and self.remaining() <= 0

    def fresh(self) -> bool:
        """Noch nie gestartet bzw. zurückgesetzt."""
        return self._started is None and self._accumulated == 0

    # ------------------------------------------------------------ Steuerung
    def set(self, seconds: float, mode: str = "countdown", finished_text: str | None = None) -> None:
        self.mode = mode
        self.duration = max(1.0, float(seconds))
        if finished_text is not None:
            self.finished_text = finished_text
        self.reset()

    def start(self) -> None:
        if self._started is None and not self.finished():
            self._started = time.monotonic()

    def pause(self) -> None:
        if self._started is not None:
            self._accumulated += time.monotonic() - self._started
            self._started = None

    def toggle(self) -> None:
        if self.running:
            self.pause()
        elif self.finished():
            self.reset()
            self.start()
        else:
            self.start()

    def reset(self) -> None:
        self._started = None
        self._accumulated = 0.0

    def restart(self) -> None:
        self.reset()
        self.start()

    def add(self, seconds: float) -> None:
        """Zeit dazugeben/abziehen (Countdown: Restzeit, Stoppuhr: angezeigte Zeit)."""
        if self.mode == "countdown":
            self.duration = max(1.0, self.duration + seconds)
            if self.elapsed() > self.duration:
                self._accumulated = self.duration
                if self._started is not None:
                    self._started = time.monotonic()
        else:
            self._accumulated = max(0.0, self._accumulated + seconds)

    # ------------------------------------------------------------ Anzeige
    def display_seconds(self) -> int:
        if self.mode == "stoppuhr":
            return int(self.elapsed())
        # aufrunden: 4,2 s Rest werden als 0:05 gezeigt, 0:00 erst wenn wirklich abgelaufen
        rem = self.remaining()
        return int(rem) + (1 if rem - int(rem) > 1e-6 else 0)

    def text(self) -> str:
        if self.finished():
            return self.finished_text or "00:00"
        return format_time(self.display_seconds())

    def urgency(self) -> str:
        """Für die Farbe: normal, bald (letzte Minute), gleich (letzte 10 s), ende."""
        if self.mode != "countdown":
            return "normal"
        if self.finished():
            return "ende"
        rem = self.remaining()
        if rem <= 10:
            return "gleich"
        if rem <= 60:
            return "bald"
        return "normal"

    def status(self) -> str:
        state = "läuft" if self.running else ("abgelaufen" if self.finished() else
                                               ("bereit" if self.fresh() else "pausiert"))
        return f"{self.text()} ({state})" if not self.finished() else self.text()


def format_time(seconds: int) -> str:
    h, rest = divmod(max(0, int(seconds)), 3600)
    m, s = divmod(rest, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


# Der eine Timer des Programms
clock = TimerClock()
