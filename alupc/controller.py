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
        self.apply_output_settings()

        from .sounds import SoundPlayer

        self.sounds = SoundPlayer(config)
        from .screensaver import ScreensaverManager

        self.screensaver = ScreensaverManager(self)
        self.screensaver.changed.connect(self.changed.emit)

        # Timer beobachten: Ton bei „noch 1 Minute“ und bei Ablauf
        from PySide6.QtCore import QTimer

        self._timer_state = ("", False)
        self._timer_watch = QTimer(self, interval=250)
        self._timer_watch.timeout.connect(self._watch_timer)
        self._timer_watch.start()

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
    def apply_output_settings(self) -> None:
        cfg = self.config["output"]
        self.output.hide_taskbar = bool(cfg.get("hide_taskbar", True))
        self.output.freeze_layer.badge = bool(cfg.get("freeze_badge", True))
        self.output.freeze_layer.update()
        if not self.output.hide_taskbar:
            self.output.taskbar.restore()

    def _guard(self) -> bool:
        # Jede Bedienung zählt als Aktivität und beendet einen laufenden Bildschirmschoner
        self.screensaver.activity()
        return True

    def show_source(self, cfg: dict, remember: bool = True, sound: bool = True) -> None:
        if not self._guard():
            return
        if self.output_screen() is None:
            self.message.emit("Kein zweiter Monitor gefunden.")
        self.ensure_extended()
        self._unfreeze()
        self.screensaver.stop()
        self.output.fade_enabled = bool(self.config["appearance"].get("fade", True))
        self.mode = "content"
        self.content = cfg
        self.output.set_content(create_source(cfg, self.config.get_scene))
        if remember:
            self.config["last_content"] = cfg
        if sound and remember:
            self.sounds.play_event("szene" if cfg.get("type") == "scene" else "inhalt")
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
        self.screensaver.stop()
        self.mode = "desktop"
        self.content = None
        self.desktop_note = note
        self.output.set_content(None)
        self.changed.emit()

    def describe(self) -> str:
        if self.mode == "content" and self.content:
            if self.content.get("mirror"):
                return "Spiegeln (Monitor 1 wird gezeigt)"
            if self.content.get("type") == "countdown":
                from .timer import clock

                return f"Timer {clock.status()}"
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
            self.sounds.play_event("standbild_aus")
            self.changed.emit()
            return
        self.sounds.play_event("standbild_an")
        if self.mode == "content" and self.output.content is not None:
            self.frozen = True
            self.output.set_frozen(self._content_snapshot())
            self.changed.emit()
            return
        if self.screens_overlap():
            self.message.emit("Standbild geht nicht bei System-Spiegeln – nutze „Spiegeln“ in AluPC.")
            return
        # Normaler Desktop auf Monitor 2: Bildschirmfoto machen und darüberlegen
        self.frozen = True
        self.changed.emit()
        self.grabber.grab(self.output_screen())

    def _content_snapshot(self):
        """Bild für das Standbild. Echtes Bildschirmfoto, wo möglich – das erfasst auch Websites
        und Videos zuverlässig, die sich per grab() nicht immer abfotografieren lassen."""
        from .platform.linux_display import is_wayland

        screen = self.output_screen()
        if screen is not None and not is_wayland() and QGuiApplication.platformName() != "offscreen" \
                and self.output.isVisible():
            pixmap = screen.grabWindow(0)
            if not pixmap.isNull():
                return pixmap
        return self.output.snapshot()

    def current_web_view(self):
        """Die Website, die gerade auf Monitor 2 läuft (auch als Teil einer Szene) – oder None."""
        from .sources import WebsiteSource

        content = self.output.content
        if content is None or self.mode != "content":
            return None
        if isinstance(content, WebsiteSource):
            return content.view
        found = content.findChildren(WebsiteSource)
        return found[0].view if found else None

    def save_website(self, title: str, url: str) -> None:
        favs = [f for f in self.config["websites"].get("favorites", []) if f.get("url") != url]
        favs.insert(0, {"title": title, "url": url})
        self.config["websites"] = {**self.config["websites"], "favorites": favs}
        self.message.emit(f"„{title}“ unter „Website“ gespeichert.")
        self.changed.emit()

    def lock_computer(self) -> None:
        """Wie Win+L: Computer sperren (Windows) bzw. Bildschirmsperre (Linux)."""
        from .platform.window_tools import lock_computer

        try:
            lock_computer()
        except Exception as exc:  # noqa: BLE001
            self.message.emit(str(exc))

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
        self.sounds.play_event("schwarz_an" if self.privacy else "schwarz_aus")
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
        if command.startswith("kachel:"):
            self.run_tile(command[7:])
            return
        actions = {
            "standbild": self.toggle_freeze,
            "schwarz": self.toggle_privacy,
            "sichtschutz": self.toggle_privacy,
            "spiegeln": self.mirror,
            "erweitern": self.extend,
            "bild-in-bild": self.toggle_pip,
            "bild_in_bild": self.toggle_pip,
            "bildschirmschoner": self.toggle_screensaver,
            "naechste_szene": lambda: self.step_scene(1),
            "naechste-szene": lambda: self.step_scene(1),
            "vorherige_szene": lambda: self.step_scene(-1),
            "vorherige-szene": lambda: self.step_scene(-1),
            "sperren": self.lock_computer,
            "timer_zeigen": self.show_timer,
            "timer_start_pause": lambda: self.timer_action("toggle"),
            "timer_neustart": lambda: self.timer_action("restart"),
            "timer_plus": lambda: self.timer_action("plus"),
            "timer_minus": lambda: self.timer_action("minus"),
        }
        action = actions.get(command)
        if action:
            action()
        else:
            self.message.emit(f"Unbekannter Befehl: {command}")

    # ------------------------------------------------------------ Timer
    def timer_source(self) -> dict:
        cfg = self.config["timer"]
        return {"type": "countdown", "minutes": cfg.get("minutes", 5), "seconds": cfg.get("seconds", 0),
                "mode": cfg.get("mode", "countdown"), "finished_text": cfg.get("finished_text", ""),
                "warn_colors": cfg.get("warn_colors", True), "size": cfg.get("size", 30),
                "autostart": False, "shared": True, "background": "#000000", "color": "#ffffff"}

    def show_timer(self) -> None:
        """Timer im Vollbild auf Monitor 2 zeigen (Zeit läuft dabei unverändert weiter)."""
        from .timer import clock

        cfg = self.config["timer"]
        if clock.fresh():
            clock.set(float(cfg.get("minutes", 5)) * 60 + float(cfg.get("seconds", 0)),
                      cfg.get("mode", "countdown"), cfg.get("finished_text", ""))
        self.show_source(self.timer_source())

    def timer_action(self, action: str) -> None:
        from .timer import clock

        if not self._guard():
            return
        cfg = self.config["timer"]
        if clock.fresh() and action in ("toggle", "restart"):
            clock.set(float(cfg.get("minutes", 5)) * 60 + float(cfg.get("seconds", 0)),
                      cfg.get("mode", "countdown"), cfg.get("finished_text", ""))
        was_running = clock.running
        {"toggle": clock.toggle, "restart": clock.restart, "reset": clock.reset,
         "plus": lambda: clock.add(60), "minus": lambda: clock.add(-60)}[action]()
        if clock.running and not was_running:
            self.sounds.play_event("timer_start")
        elif was_running and not clock.running and action == "toggle":
            self.sounds.play_event("timer_pause")
        self.changed.emit()

    def _watch_timer(self) -> None:
        from .timer import clock

        state = clock.urgency()
        finished = clock.finished()
        old_state, old_finished = self._timer_state
        if clock.running or finished:
            if state == "bald" and old_state == "normal":
                self.sounds.play_event("timer_minute")
            if finished and not old_finished:
                self.sounds.play_event("timer_ende")
                self.changed.emit()
        self._timer_state = (state, finished)

    def timer_visible(self) -> bool:
        """Zeigt Monitor 2 gerade irgendwo einen Timer (direkt oder in einer Szene)?"""
        def has(cfg, depth=0):
            if not cfg or depth > 4:
                return False
            if cfg.get("type") == "countdown":
                return True
            if cfg.get("type") == "scene":
                scene = self.config.get_scene(cfg.get("scene"))
                return any(has(s, depth + 1) for s in (scene or {}).get("slots", []))
            return False

        return self.mode == "content" and has(self.content)

    def toggle_screensaver(self) -> None:
        if self._guard():
            self.screensaver.toggle()

    def step_scene(self, direction: int) -> None:
        """Zur nächsten/vorherigen eigenen Szene wechseln (in der Reihenfolge der Liste)."""
        names = self.config.scene_names()
        if not names:
            self.message.emit("Es gibt noch keine Szene.")
            return
        current = self.content.get("scene") if self.content and self.content.get("type") == "scene" else None
        if current in names:
            index = (names.index(current) + direction) % len(names)
        else:
            index = 0 if direction > 0 else len(names) - 1
        self.show_source({"type": "scene", "scene": names[index]})

    def run_tile(self, tile_id: str) -> None:
        """Eigene Kachel der Startseite ausführen (auch per Tastenkürzel)."""
        tile = next((t for t in self.config["start_page"].get("custom", []) if t.get("id") == tile_id), None)
        if tile is None:
            self.message.emit("Diese Kachel gibt es nicht mehr.")
            return
        action = tile.get("action") or {}
        kind = action.get("kind")
        # Hat die Kachel einen eigenen Ton (oder gibt es einen Kachel-Ton), ersetzt er die normalen Töne
        tile_sound = tile.get("sound") or self.config["sounds"].get("events", {}).get("kachel", "")
        normal = not tile_sound
        if kind == "command":
            self.run_command(action.get("command", ""))
        elif kind == "source" and action.get("source"):
            self.show_source(action["source"], remember=True, sound=normal)
        elif kind == "screensaver":
            # eigener Bildschirmschoner dieser Kachel: nochmal klicken = beenden
            if not self._guard():
                return
            if self.screensaver.active and self.screensaver.override_id == tile_id:
                self.screensaver.stop()
            else:
                self.screensaver.stop()
                self.screensaver.start(manual=True, override={**(action.get("screensaver") or {}),
                                                              "_id": tile_id})
        elif kind == "timer":
            from .timer import clock

            t = action.get("timer") or {}
            clock.set(float(t.get("minutes", 5)) * 60 + float(t.get("seconds", 0)), t.get("mode", "countdown"),
                      t.get("finished_text", self.config["timer"].get("finished_text", "")))
            self.show_source(self.timer_source(), sound=normal)
            if t.get("autostart", True):
                clock.start()  # direkt starten – timer_action würde auf die Standarddauer zurückstellen
                self.sounds.play_event("timer_start")
                self.changed.emit()
        if tile_sound:
            self.sounds.play_event("kachel", tile_sound)

    def toggle_pip(self) -> None:
        if self.pip is not None and self._guard():
            self.pip.toggle()
            self.changed.emit()

    def shutdown(self) -> None:
        self._timer_watch.stop()
        self.screensaver.timer.stop()
        self.output.set_screensaver(None)
        self.output.set_content(None)
        self.output.shutdown()
        self.output.close()
