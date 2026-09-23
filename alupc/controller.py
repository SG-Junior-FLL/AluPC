"""Zentrale Steuerung: Was läuft gerade auf Monitor 2?"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QGuiApplication

from .config import Config
from .output_window import OutputWindow, ScreenGrabber, screen_by_name
from .platform import create_display_backend, create_fingerprint_backend, create_window_backend
from .scenes import describe_source
from .sources import create_source


class Controller(QObject):
    changed = Signal()
    message = Signal(str)  # kurze Meldung für die Statusleiste / Benachrichtigung

    def __init__(self, config: Config):
        super().__init__()
        self.config = config
        self.display = create_display_backend()
        self.windows = create_window_backend()
        self.fingerprint = create_fingerprint_backend()
        self.output = OutputWindow()
        self.grabber = ScreenGrabber(self)
        self.grabber.done.connect(self._frozen_grab_done)
        self.grabber.failed.connect(self._frozen_grab_failed)
        self.pip = None  # wird von der Oberfläche gesetzt

        self.mode = "desktop"  # "content" = AluPC zeigt etwas, "desktop" = normaler zweiter Desktop
        self.content: dict | None = None
        self.desktop_note = "Erweitert (normaler zweiter Bildschirm)"
        self.frozen = False
        self.privacy = False
        self.locked = False

        app = QGuiApplication.instance()
        app.screenAdded.connect(self._screen_added)
        app.screenRemoved.connect(lambda _s: self.update_screens())
        for screen in QGuiApplication.screens():
            self._watch(screen)
        self.update_screens()

    def _watch(self, screen) -> None:
        # Auflösung/Position geändert (z. B. über Setup) → Fenster neu platzieren
        screen.geometryChanged.connect(lambda _g: self.update_screens())

    def _screen_added(self, screen) -> None:
        self._watch(screen)
        self.update_screens()

    # ------------------------------------------------------------ Monitore
    def output_screen(self):
        screens = QGuiApplication.screens()
        wanted = self.config["output_screen"]
        if wanted:
            screen = screen_by_name(wanted)
            if screen is not None:
                return screen
        primary = QGuiApplication.primaryScreen()
        for s in screens:
            if s is not primary:
                return s
        return None

    def main_screen(self):
        out = self.output_screen()
        primary = QGuiApplication.primaryScreen()
        if primary is not None and primary is not out:
            return primary
        for s in QGuiApplication.screens():
            if s is not out:
                return s
        return primary

    def update_screens(self) -> None:
        self.output.place_on(self.output_screen())
        self.changed.emit()

    def screens_overlap(self) -> bool:
        out, main = self.output_screen(), self.main_screen()
        return out is not None and main is not None and out.geometry().intersects(main.geometry())

    def ensure_extended(self) -> None:
        """AluPC braucht einen eigenen Bereich auf Monitor 2 – System-Spiegeln ggf. aufheben."""
        if not self.screens_overlap() or not self.display.available():
            return
        try:
            self.display.extend(self.main_screen().name(), self.output_screen().name(), "right")
        except Exception as exc:  # noqa: BLE001
            self.message.emit(f"Konnte nicht auf Erweitern umschalten: {exc}")

    # ------------------------------------------------------------ Modi
    def _guard(self) -> bool:
        if self.locked:
            self.message.emit("AluPC ist gesperrt.")
            return False
        return True

    def show_source(self, cfg: dict, remember: bool = True) -> None:
        if not self._guard():
            return
        if self.output_screen() is None:
            self.message.emit("Kein zweiter Monitor gefunden.")
        self.ensure_extended()
        self._unfreeze()
        self.mode = "content"
        self.content = cfg
        self.output.set_content(create_source(cfg, self.config.get_scene))
        if remember:
            self.config["last_content"] = cfg
        self.changed.emit()

    def mirror(self) -> None:
        main = self.main_screen()
        self.show_source({"type": "screen", "screen_name": main.name() if main else "", "mirror": True})

    def extend(self) -> None:
        if not self._guard():
            return
        self.ensure_extended()
        self._set_desktop("Erweitert (normaler zweiter Bildschirm)")
        self.config["last_content"] = None

    def prepare_system_mirror(self) -> tuple[str, str] | None:
        """AluPC-Anzeige beenden; liefert (Hauptmonitor, Monitor 2) für display.mirror()."""
        if not self._guard():
            return None
        out, main = self.output_screen(), self.main_screen()
        if out is None or main is None:
            self.message.emit("Kein zweiter Monitor gefunden.")
            return None
        if self.privacy:
            self.toggle_privacy()
        self._set_desktop("System-Spiegeln (vom Betriebssystem)")
        self.config["last_content"] = None
        return main.name(), out.name()

    def program_moved(self, title: str) -> None:
        self._set_desktop(f"Programm direkt auf Monitor 2: {title}")

    def _set_desktop(self, note: str) -> None:
        self._unfreeze()
        self.mode = "desktop"
        self.content = None
        self.desktop_note = note
        self.output.set_content(None)
        self.changed.emit()

    def describe(self) -> str:
        if self.mode == "content" and self.content:
            if self.content.get("mirror"):
                return "Spiegeln (Monitor 1 wird gezeigt)"
            return describe_source(self.content)
        return self.desktop_note

    def restore_last(self) -> None:
        last = self.config["last_content"]
        if last and self.config["restore_last_content"]:
            self.show_source(last, remember=False)

    # ------------------------------------------------------------ Standbild
    def toggle_freeze(self) -> None:
        if not self._guard():
            return
        if self.frozen:
            self._unfreeze()
            self.changed.emit()
            return
        if self.mode == "content" and self.output.content is not None:
            self.frozen = True
            self.output.set_frozen(self.output.snapshot())
            self.changed.emit()
            return
        if self.screens_overlap():
            self.message.emit("Standbild geht nicht bei System-Spiegeln – nutze „Spiegeln“ in AluPC.")
            return
        # Normaler Desktop auf Monitor 2: Bildschirmfoto machen und darüberlegen
        self.frozen = True
        self.changed.emit()
        self.grabber.grab(self.output_screen())

    def _frozen_grab_done(self, image) -> None:
        if self.frozen:
            self.output.set_frozen(image)
            self.changed.emit()

    def _frozen_grab_failed(self, error: str) -> None:
        self.frozen = False
        self.changed.emit()
        self.message.emit(f"Standbild nicht möglich: {error}")

    def _unfreeze(self) -> None:
        if self.frozen:
            self.frozen = False
            self.output.set_frozen(None)

    # ------------------------------------------------------------ Sichtschutz
    def toggle_privacy(self) -> None:
        if not self._guard():
            return
        if self.screens_overlap() and not self.privacy:
            self.message.emit("Sichtschutz geht nicht bei System-Spiegeln – nutze „Spiegeln“ in AluPC.")
            return
        self.privacy = not self.privacy
        p = self.config["privacy"]
        self.output.set_privacy(self.privacy, p.get("image", ""), p.get("text", ""))
        self.changed.emit()

    # ------------------------------------------------------------ Befehle (Tastenkürzel, Kommandozeile)
    def run_command(self, command: str) -> None:
        command = command.strip()
        if command.startswith("szene:"):
            name = command[6:]
            if self.config.get_scene(name):
                self.show_source({"type": "scene", "scene": name})
            else:
                self.message.emit(f"Szene „{name}“ gibt es nicht.")
            return
        actions = {
            "standbild": self.toggle_freeze,
            "schwarz": self.toggle_privacy,
            "sichtschutz": self.toggle_privacy,
            "spiegeln": self.mirror,
            "erweitern": self.extend,
            "bild-in-bild": self.toggle_pip,
            "bild_in_bild": self.toggle_pip,
        }
        action = actions.get(command)
        if action:
            action()
        else:
            self.message.emit(f"Unbekannter Befehl: {command}")

    def toggle_pip(self) -> None:
        if self.pip is not None and self._guard():
            self.pip.toggle()
            self.changed.emit()

    def shutdown(self) -> None:
        self.output.set_content(None)
        self.output.close()
