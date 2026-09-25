"""Zentrale Steuerung: Was läuft gerade auf Monitor 2?"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QGuiApplication

from .config import Config
from .output_window import OutputWindow, ScreenGrabber, screen_by_name
from .platform import create_display_backend, create_fingerprint_backend, create_window_backend
from .scenes import describe_source
from .sources import create_source, media_sources, window_settings


HANDY_NOTES = ("iPhone/iPad", "Android", "Miracast")  # Monitor 2 zeigt ein Handy-Fenster


class Controller(QObject):
    changed = Signal()
    message = Signal(str)
    presenter_requested = Signal()  # Fenster „Zeigen & Zeichnen“ öffnen (macht die Oberfläche)  # kurze Meldung für die Statusleiste / Benachrichtigung

    def __init__(self, config: Config):
        super().__init__()
        self.config = config
        self.display = create_display_backend()
        self.windows = create_window_backend()
        self.fingerprint = create_fingerprint_backend()
        self._scene_volume: dict | None = None
        self._mirror_hint_shown = False
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
        from .cursor import CursorGuard
        from .laser import LaserWindow

        self.cursor_guard = CursorGuard(self)
        self.laser = LaserWindow(self)
        self.output.after_raise.append(self.laser.raise_above)
        self.laser.changed_cb = self.save_drawings
        from .handy import airplay_server

        self.airplay = airplay_server(config)
        self._handy_window = ""  # „airplay“/„android“, solange ein Handy-Fenster auf Monitor 2 liegt
        self._scrcpy = None
        from .cast_server import cast_server

        self.cast = cast_server(config)
        self.cast.request.connect(self._cast_request)
        self.changed.connect(self.update_cursor_guard)
        self.changed.connect(self._cast_snapshot)
        if self.cast.settings().get("autostart"):
            self.cast.start()
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
        if self.laser.needed():
            self.laser.place()
        self.changed.emit()

    # ------------------------------------------------------------ Maus
    def cursor_should_stay_home(self) -> bool:
        """Maus auf Monitor 1 festhalten? Ja, solange Monitor 2 nicht der normale Desktop („Erweitern“) ist."""
        # Nur der Modus zählt – nicht, ob das Fenster auf Monitor 2 gerade (z. B. beim Umschalten) kurz
        # unsichtbar ist. „Programm direkt auf Monitor 2“ ist Erweitern → dort darf die Maus hin.
        saver = getattr(self, "screensaver", None)
        showing = self.mode == "content" or self.frozen or self.privacy or bool(saver and saver.active)
        return bool(self.config["output"].get("confine_cursor", True)) and showing \
            and self.output_screen() is not None

    def update_cursor_guard(self) -> None:
        self.cursor_guard.set_active(self.cursor_should_stay_home(), self.main_screen(), self.output_screen())

    # ------------------------------------------------------------ Zeichnungen
    def _content_key(self) -> str:
        import json

        return json.dumps(self.content, sort_keys=True) if self.mode == "content" and self.content else "desktop"

    def save_drawings(self) -> None:
        """Zeichnungen merken – sie bleiben, bis man sie löscht oder etwas anderes auf Monitor 2 kommt
        (auch über einen Neustart von AluPC hinweg)."""
        strokes = [dict(s, points=[list(p) for p in s["points"]]) for s in self.laser.strokes]
        self.config["draw"] = {**self.config["draw"], "strokes": strokes,
                               "strokes_for": self._content_key() if strokes else ""}
        self.changed.emit()

    def _restore_drawings(self) -> None:
        d = self.config["draw"]
        if d.get("strokes") and d.get("strokes_for") == self._content_key():
            self.laser.strokes = [dict(s, points=[tuple(p) for p in s.get("points", [])]) for s in d["strokes"]]
            self.laser.place()
            self.laser.update()

    # ------------------------------------------------------------ Kamera: Zoom, Ausschnitt, Drehen …
    def _sync_camera_settings(self) -> None:
        from .sources import camera_settings

        camera_settings.clear()
        camera_settings.update({k: dict(v) for k, v in self.config["camera"].items()})

    def cameras_on_output(self) -> list:
        from .sources import camera_sources

        return camera_sources(self.output.content) if self.mode == "content" else []

    def set_camera_option(self, device_id: str, **changes) -> dict:
        """Kamera-Einstellung ändern (gilt sofort und bleibt gespeichert). Rückgabe: neue Einstellungen."""
        from .sources import CAMERA_DEFAULTS, MAX_ZOOM, clamp_center

        opts = {**CAMERA_DEFAULTS, **self.config["camera"].get(device_id, {}), **changes}
        opts["zoom"] = round(max(1.0, min(MAX_ZOOM, float(opts["zoom"]))), 2)
        opts["x"], opts["y"] = clamp_center(opts["zoom"], float(opts["x"]), float(opts["y"]))
        opts["rotate"] = int(opts["rotate"]) % 360
        opts["exposure"] = max(-2.0, min(2.0, float(opts["exposure"])))
        self.config["camera"] = {**self.config["camera"], device_id: opts}
        self._sync_camera_settings()
        for cam in self.cameras_on_output():
            if cam.device_id == device_id:
                cam.apply_options()
        return opts

    def reset_camera(self, device_id: str) -> None:
        from .sources import CAMERA_DEFAULTS

        keep = self.config["camera"].get(device_id, {}).get("quality", CAMERA_DEFAULTS["quality"])
        self.set_camera_option(device_id, **{**CAMERA_DEFAULTS, "quality": keep})

    def camera_zoom(self, factor: float | None) -> None:
        """Zoom der (ersten) Kamera auf Monitor 2: mal `factor`, None = zurück auf 1×."""
        cams = self.cameras_on_output()
        if not cams:
            self.message.emit("Keine Kamera auf Monitor 2.")
            return
        cam = cams[0]
        zoom = 1.0 if factor is None else cam.options()["zoom"] * factor
        self.set_camera_option(cam.device_id, zoom=zoom)

    def _apply_cursor_settings(self) -> None:
        """Mauszeiger beim Spiegeln einzeichnen – aber nicht, wenn der Laserpointer an ist."""
        from .sources import ScreenSource, screen_settings

        show = bool(self.config["output"].get("mirror_cursor", True))
        screen_settings["cursor"] = show
        content = self.output.content
        if isinstance(content, ScreenSource):
            if content.feed is not None:
                content.feed.cursor = show
            content.update()

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
        self._apply_cursor_settings()
        self.update_cursor_guard()

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
        self.mode = "content"
        self.content = cfg
        self._scene_volume = None
        self._content_switched()
        self._stop_handy_window()
        window_settings["restore_minimized"] = bool(self.config["program"].get("restore_minimized", True))
        self._sync_camera_settings()
        self.output.set_content(create_source(cfg, self.config.get_scene), self.transition_for(cfg))
        if remember:
            self.config["last_content"] = cfg
            from . import media_library

            media_library.remember(self.config, cfg)
        if sound and remember:
            self.sounds.play_event("szene" if cfg.get("type") == "scene" else "inhalt")
        self.changed.emit()

    # ------------------------------------------------------------ Ton der Medien auf Monitor 2
    def media_state(self) -> dict | None:
        """Lautstärke des aktuellen Inhalts (Video/Website, auch in Szenen) – None, wenn ohne Ton."""
        if self.mode != "content" or not media_sources(self.output.content):
            return None
        cfg = self.content or {}
        if cfg.get("type") == "scene":
            cfg = self._scene_volume or {}
        return {"volume": int(cfg.get("volume", 100)), "muted": bool(cfg.get("muted", False))}

    def set_media_volume(self, volume: int | None = None, muted: bool | None = None) -> None:
        """Lautstärke live ändern. Bei einer einzelnen Quelle wird sie in deren Einstellung gemerkt;
        in Szenen gilt sie für alle Videos/Websites bis zum nächsten Wechsel."""
        sources = media_sources(self.output.content)
        if not sources:
            return
        for src in sources:
            src.set_volume(volume, muted)
        changes = {k: v for k, v in (("volume", volume), ("muted", muted)) if v is not None}
        if self.content and self.content.get("type") in ("video", "website"):
            self.content = {**self.content, **changes}
            self.config["last_content"] = self.content
        else:
            self._scene_volume = {**(self._scene_volume or {}), **changes}
        self.changed.emit()

    def transition_for(self, cfg: dict | None) -> tuple[str, int]:
        """Übergang zum neuen Inhalt: Einstellung im Setup, eine Szene kann sie überschreiben."""
        from .transitions import resolve

        base = dict(self.config["transition"])
        if not self.config["appearance"].get("fade", True):
            base["type"] = "schnitt"  # alte Einstellung „nicht überblenden“ = harter Schnitt …
        scene = self.config.get_scene(cfg.get("scene")) if cfg and cfg.get("type") == "scene" else None
        # … aber ein Übergang, der bei der Szene selbst eingestellt ist, gilt trotzdem
        return resolve(base, (scene or {}).get("transition"))

    def mirror(self) -> None:
        main = self.main_screen()
        self.show_source({"type": "screen", "screen_name": main.name() if main else "", "mirror": True})
        content = self.output.content
        if getattr(content, "method", "") == "qt" and not self._mirror_hint_shown:
            from .platform.linux_display import is_wayland

            if is_wayland():
                self._mirror_hint_shown = True
                self.message.emit("Wayland fragt beim Spiegeln nach dem Bildschirm. Ohne Nachfrage geht es unter "
                                  "KDE mit dem installierten .deb-Paket von AluPC.")

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

    # ------------------------------------------------------------ Handy → Monitor 2
    def start_airplay(self) -> None:
        """iPhone/iPad: als Quelle (UxPlay ≥ 1.73) oder im eigenen Vollbild-Fenster (ältere Versionen)."""
        from .handy import supports_vrtp

        uxplay = self.airplay.binary()
        if not uxplay:
            self.message.emit("AirPlay: UxPlay fehlt – Kachel „Handy“ → „Einrichten …“.")
            return
        if supports_vrtp(uxplay):
            self.show_source({"type": "airplay"})
            return
        if self.output_screen() is None:
            self.message.emit("Kein zweiter Monitor gefunden.")
            return
        self._stop_handy_window()
        self.ensure_extended()
        self.airplay.acquire(want_stream=False)
        self._handy_window = "airplay"
        self._set_desktop("iPhone/iPad (AirPlay, eigenes Fenster)")
        name = self.airplay.settings()["airplay_name"]
        self.message.emit(f"AirPlay bereit: am iPhone/iPad „Bildschirmsynchronisierung“ → „{name}“ wählen.")
        self._place_handy_window(name)

    def start_android(self) -> None:
        """Android per scrcpy (USB-Debugging nötig) – Fenster im Vollbild auf Monitor 2."""
        from PySide6.QtCore import QProcess

        from .handy import WINDOW_TITLE_ANDROID, find_program, scrcpy_args

        scrcpy = find_program("scrcpy", self.config["handy"].get("scrcpy_path", ""))
        if not scrcpy:
            self.message.emit("Android: scrcpy fehlt – Kachel „Handy“ → „Einrichten …“.")
            return
        screen = self.output_screen()
        if screen is None:
            self.message.emit("Kein zweiter Monitor gefunden.")
            return
        self._stop_handy_window()
        self.ensure_extended()
        g = screen.geometry()
        self._scrcpy = QProcess(self)
        self._scrcpy.start(scrcpy, scrcpy_args((g.x(), g.y(), g.width(), g.height())))
        self._handy_window = "android"
        self._set_desktop("Android-Handy (scrcpy)")
        self._place_handy_window(WINDOW_TITLE_ANDROID)

    def start_miracast(self) -> None:
        """Windows: eingebaute „Drahtlose Anzeige“ starten und ihr Fenster auf Monitor 2 legen."""
        from .platform import miracast
        from .ui.util import run_async

        if not miracast.IS_WINDOWS:
            self.message.emit("Miracast-Empfang gibt es nur unter Windows. Linux: QR-Code (AluCast) oder AirPlay.")
            return
        if self.output_screen() is None:
            self.message.emit("Kein zweiter Monitor gefunden.")
            return

        def found(app):
            if app is None:
                self.message.emit("Miracast: Windows-App „Drahtlose Anzeige“ fehlt – Kachel „Handy“ → "
                                  "„Einrichten …“ → Miracast → Installieren.")
                return
            self._stop_handy_window()
            self.ensure_extended()
            miracast.launch(app)
            self._handy_window = "miracast"
            self._set_desktop("Miracast (Windows „Drahtlose Anzeige“)")
            self.message.emit("Miracast bereit: am Handy/Laptop „Bildschirm übertragen“ bzw. „Smart View“ → "
                              "diesen PC wählen.")
            self._place_handy_window(app["name"])

        run_async(miracast.find_app, found, lambda text: self.message.emit(f"Miracast: {text}"))

    # ------------------------------------------------------------ AluCast (Handy per Browser)
    def start_cast(self) -> None:
        """QR-Code auf Monitor 2 zeigen – Handy scannt und kann senden."""
        if not self.cast.start():
            self.message.emit("AluCast konnte nicht starten: Netzwerk-Anschluss belegt.")
            return
        self._cast_snapshot()
        self.show_source({"type": "cast"})

    def stop_cast(self) -> None:
        self.cast.stop()
        self.config["cast"] = {**self.config["cast"], "autostart": False}
        if self.content and self.content.get("type") == "cast":
            self.extend()
        self.message.emit("AluCast beendet – Handys können nichts mehr senden.")

    def _cast_snapshot(self) -> None:
        from .sources import video_sources

        state = self.media_state() or {}
        self.cast.snapshot = {
            "now": self.describe(),
            "scenes": self.config.scene_names(),
            "volume": int(state.get("volume", 100)),
            "video": bool(video_sources(self.output.content)) if self.mode == "content" else False,
        }

    def _cast_request(self, req: dict) -> None:
        """Anfrage vom Handy (kommt aus dem Webserver-Thread, läuft hier im Qt-Hauptthread)."""
        from .sources import video_sources

        kind = req.get("kind")
        if kind == "file":
            cfg = {"type": req["type"], "path": req["path"]}
            if req["type"] == "video":
                cfg.update(loop=False, volume=100)
            self.show_source(cfg)
            self.message.emit(("Foto" if req["type"] == "image" else "Video") + " vom Handy auf Monitor 2.")
        elif kind == "link":
            self.show_source({"type": "website", "url": req["url"]})
            self.message.emit(f"Link vom Handy: {req.get('original', req['url'])}")
        elif kind == "text":
            self.show_source({"type": "text", "text": req["text"]})
        elif kind == "cmd":
            cmd = req.get("cmd", "")
            videos = video_sources(self.output.content) if self.mode == "content" else []
            if cmd.startswith("lautstaerke:"):
                self.set_media_volume(volume=max(0, min(100, int(cmd.split(":", 1)[1]))), muted=False)
            elif cmd.startswith("video_"):
                if videos:
                    {"video_pause": videos[0].toggle_play, "video_vor": lambda: videos[0].skip(10_000),
                     "video_zurueck": lambda: videos[0].skip(-10_000)}[cmd]()
            else:
                self.run_command(cmd)
        self._cast_snapshot()

    def _place_handy_window(self, title: str, tries: int = 6) -> None:
        """Fenster suchen, sobald es erscheint, und im Vollbild auf Monitor 2 legen."""
        from PySide6.QtCore import QTimer

        screen = self.output_screen()
        if screen is None or not self._handy_window or tries <= 0:
            return
        g = screen.geometry()

        def attempt():
            if not self._handy_window:
                return
            try:
                if self.windows.move_by_title(title, screen.name(), (g.x(), g.y(), g.width(), g.height()), True):
                    return
            except Exception:  # noqa: BLE001
                pass
            self._place_handy_window(title, tries - 1)

        QTimer.singleShot(2500, attempt)

    def _stop_handy_window(self) -> None:
        if self._handy_window == "airplay":
            self.airplay.release()
        if self._scrcpy is not None:
            self._scrcpy.terminate()
            if not self._scrcpy.waitForFinished(2000):
                self._scrcpy.kill()
            self._scrcpy = None
        self._handy_window = ""

    def _content_switched(self) -> None:
        """Neuer Inhalt auf Monitor 2 (Szenenwechsel) → alte Zeichnungen weg."""
        if self.laser.strokes:
            self.laser.clear_strokes()

    def _set_desktop(self, note: str) -> None:
        self._content_switched()
        if not note.startswith(HANDY_NOTES):
            self._stop_handy_window()  # Handy-Fenster schließen, wenn etwas anderes kommt
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
        self._restore_drawings()  # Zeichnungen zum wiederhergestellten Inhalt wieder anzeigen

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

    def current_media(self) -> dict | None:
        """Bild/Video/Diashow, die gerade auf Monitor 2 läuft (sonst None)."""
        cfg = self.content if self.mode == "content" else None
        return cfg if cfg and cfg.get("type") in ("image", "video", "slideshow") else None

    def save_media(self, cfg: dict, title: str | None = None) -> None:
        from . import media_library

        item = media_library.save(self.config, cfg, title)
        self.message.emit(f"„{item['title']}“ in der Mediathek gespeichert.")
        self.changed.emit()

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
            # Laserpointer gibt es nur noch im Fenster „Zeigen & Zeichnen“
            "laserpointer": self.presenter_requested.emit,
            "laser": self.presenter_requested.emit,
            "zeichnen": self.presenter_requested.emit,
            "zeichnungen_loeschen": lambda: self.laser.clear_strokes(),
            "kamera_zoom_plus": lambda: self.camera_zoom(1.25),
            "kamera_zoom_minus": lambda: self.camera_zoom(0.8),
            "kamera_zoom_aus": lambda: self.camera_zoom(None),
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
        self._stop_handy_window()
        self.laser.close()
        self.cursor_guard.shutdown()
        from .cursor import tracker

        tracker().shutdown()
        self.screensaver.timer.stop()
        self.output.set_screensaver(None)
        self.output.set_content(None)
        self.airplay.shutdown()
        self.cast.stop()
        self.output.shutdown()
        self.output.close()
