"""Zentrale Steuerung: Was läuft gerade auf Monitor 2?"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QGuiApplication

from .config import Config
from .output_window import OutputWindow, ScreenGrabber, screen_by_name
from .platform import create_display_backend, create_fingerprint_backend, create_window_backend
from .scenes import describe_source
from .sources import create_source, media_sources, window_settings


HANDY_NOTES = ("iPhone/iPad",)  # Monitor 2 zeigt ein Handy-Fenster (AirPlay)


class Controller(QObject):
    changed = Signal()
    message = Signal(str)
    settings_imported = Signal(list)  # Dual-Boot: Einstellungen vom anderen System übernommen
    sync_status = Signal(str)
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
        self.airplay.failed.connect(self._airplay_failed)
        self.recent_messages: list[str] = []  # für „Diagnose kopieren“
        self.message.connect(lambda m: self.recent_messages.append(m) or
                             self.recent_messages.__delitem__(slice(0, -30)))
        self.last_mirror_problem = ""
        self._handy_window = ""  # „airplay“, solange das iPhone-Fenster auf Monitor 2 liegt
        from .cast_server import cast_server

        self.cast = cast_server(config)
        self.cast.request.connect(self._cast_request)
        from PySide6.QtCore import QTimer as _QTimer

        self._cast_timer = _QTimer(self, interval=900)  # Live-Bild/Status fürs Handy
        self._cast_timer.timeout.connect(self._cast_tick)
        self._cast_timer.start()
        self.changed.connect(self.update_cursor_guard)
        self.changed.connect(self._cast_snapshot)
        if self.cast.settings().get("autostart"):
            self.cast.start()
        from .rgb_manager import RgbManager

        self.rgb = RgbManager(self)
        # Dual-Boot-Abgleich: nach Änderungen (kurz gesammelt) in den gemeinsamen Ordner schreiben
        from PySide6.QtCore import QTimer

        self._syncing = False
        self._sync_timer = QTimer(self, singleShot=True, interval=4000)
        self._sync_timer.timeout.connect(self.run_sync)
        config.listeners.append(self._config_saved)
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
        if cfg.get("type") == "airplay":
            self._follow_airplay_window()
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
        if self.config["output"].get("mirror_method") == "system" and self.display.available():
            self.system_mirror()  # Ersteinrichtung hat festgestellt: Bildaufnahme klappt hier nicht
            return
        main = self.main_screen()
        self.show_source({"type": "screen", "screen_name": main.name() if main else "", "mirror": True})
        content = self.output.content
        if hasattr(content, "no_signal"):
            content.no_signal.connect(self._mirror_no_signal)
            if getattr(content, "problem", ""):  # schon beim Start gescheitert (z. B. Windows ohne Aufnahme)
                self._mirror_no_signal(content.problem)
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

    def _mirror_no_signal(self, reason: str) -> None:
        """Spiegeln per Aufnahme klappt auf diesem PC nicht → automatisch über das Betriebssystem spiegeln."""
        if not (self.content and self.content.get("mirror")):
            return
        self.last_mirror_problem = reason
        if not self.display.available():
            self.message.emit(f"Spiegeln: {reason} Das Betriebssystem-Spiegeln ist hier auch nicht verfügbar – "
                              "bitte „Diagnose kopieren“ (Setup → Allgemein) an den Entwickler schicken.")
            return
        self.message.emit(f"Spiegeln: {reason} AluPC spiegelt jetzt über {self.display.name}.")
        self.system_mirror()

    def system_mirror(self) -> None:
        """Monitor 2 vom Betriebssystem spiegeln lassen (Kubuntu: kscreen-doctor, Windows: wie Win+P)."""
        from .ui.util import run_async

        pair = self.prepare_system_mirror()
        if pair is None:
            return
        main, out = pair
        run_async(lambda: self.display.mirror(main, out), lambda _r: self.changed.emit(),
                  lambda text: self.message.emit(f"System-Spiegeln fehlgeschlagen: {text}"))

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
        """iPhone/iPad auf Monitor 2. Monitor 2 zeigt sofort einen Warte-Bildschirm (Name, Code) – kein
        „Erweitert“. Kann UxPlay das Bild an AluPC weitergeben (ab 1.73), erscheint es direkt darin; sonst legt
        AluPC UxPlays eigenes Fenster randlos und im Vordergrund darüber, sobald sich das iPhone verbindet."""
        if not self.airplay.binary():
            self.message.emit("AirPlay: Der Empfänger fehlt – Handy → „Automatisch einrichten“ installiert ihn.")
            return
        if self.output_screen() is None:
            self.message.emit("Kein zweiter Monitor gefunden.")
            return
        self.show_source({"type": "airplay"})
        name = self.airplay.settings()["airplay_name"]
        code = f" · Code {self.airplay.pin_code}" if self.airplay.pin_code else ""
        self.message.emit(f"AirPlay bereit: am iPhone/iPad „Bildschirmsynchronisierung“ → „{name}“ wählen.{code}")

    def _follow_airplay_window(self) -> None:
        """UxPlay zeigt das Bild im eigenen Fenster → dieses Fenster dauerhaft auf Monitor 2 legen."""
        from .sources import AirPlaySource

        src = self.output.content
        if isinstance(src, AirPlaySource) and src.mode == "fenster":
            self._handy_window = "airplay-quelle"  # UxPlay gehört der Quelle (gibt es beim Wechsel selbst frei)
            self.output.set_yield(True)  # iPhone-Fenster darf über den Warte-Bildschirm
            name = self.airplay.settings()["airplay_name"]
            # uxplay-windows/uxplay.exe: Fenster am Programm erkennen (Titel je nach Version verschieden)
            self._place_handy_window(name, name.replace(" ", "\u00a0"), "UxPlay", "AirPlay Video",
                                     apps=("uxplay-windows", "uxplay"))

    def _airplay_failed(self, reason: str) -> None:
        self.message.emit(f"AirPlay läuft nicht: {reason}")
        if self._handy_window in ("airplay", "airplay-quelle"):
            self._stop_following()
            self._handy_window = ""

    def _config_saved(self) -> None:
        if not self._syncing and self.config.data["sync"].get("enabled"):
            self._sync_timer.start()

    def run_sync(self) -> str:
        from .settings_sync import sync_once

        self._syncing = True
        try:
            msg, changed = sync_once(self.config)
        except Exception as exc:  # noqa: BLE001
            msg, changed = f"Abgleich fehlgeschlagen: {exc}", []
        finally:
            self._syncing = False
        if changed:
            self.settings_imported.emit(changed)
        self.sync_status.emit(msg)
        return msg

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
        from .timer import clock

        state = self.media_state()
        content = self.content or {}
        rgb = self.rgb.settings()["mode"] if self.rgb.connected else ""
        self.cast.snapshot = {
            "now": self.describe(),
            "scenes": self.config.scene_names(),
            "scene": content.get("scene", "") if self.mode == "content" and content.get("type") == "scene" else "",
            "volume": int((state or {}).get("volume", 100)),
            "sound": state is not None,
            "video": bool(video_sources(self.output.content)) if self.mode == "content" else False,
            "timer": clock.text(),
            "keys": __import__("alupc.platform.keys", fromlist=["available"]).available(),
            "allow": {k: self.cast.allowed(k) for k in ("senden", "steuern", "live", "laser")},
            "ablauf": bool(self.agenda_sources()),
            "rgb": rgb,
            "flags": {"schwarz": self.privacy, "standbild": self.frozen, "schoner": self.screensaver.active,
                      "spiegeln": bool(self.mode == "content" and content.get("mirror")),
                      "erweitern": self.mode == "desktop" and self.desktop_note.startswith("Erweitert")},
        }

    def _phone_draw(self, req: dict) -> None:
        """Mit dem Finger auf Monitor 2 zeichnen (Live-Bild auf dem Handy = Monitor 2)."""
        from PySide6.QtCore import QPointF

        phase = req.get("phase")
        if phase == "up":
            self.laser.end_stroke()
            return
        point = QPointF(float(req["x"]), float(req["y"]))
        if req.get("tool") == "radierer":
            self.laser.erase_at(point, 0.03)
            return
        if phase == "down":
            self.laser.begin_stroke("marker" if req.get("tool") == "marker" else "pen", req.get("color", "#ef4444"),
                                    0.005, point)  # Marker: breiter und halb durchsichtig (laser.stroke_pen)
        else:
            self.laser.extend_stroke(point)

    def _phone_mouse(self, req: dict) -> None:
        """Handy als Touchpad: Zeiger bewegen, klicken, scrollen (Windows und Linux/X11)."""
        from PySide6.QtGui import QCursor

        from .platform import keys

        if "click" in req:
            ok = keys.click(req["click"])
        elif "scroll" in req:
            ok = keys.scroll(int(req["scroll"]))
        else:
            pos = QCursor.pos()
            QCursor.setPos(pos.x() + round(float(req.get("dx", 0))), pos.y() + round(float(req.get("dy", 0))))
            ok = True
        if not ok and not getattr(self, "_mouse_hint", False):
            self._mouse_hint = True
            self.message.emit("Klicks vom Handy gehen unter Wayland nicht – bitte die X11-Sitzung nutzen.")

    def _phone_laser(self, x, y) -> None:
        """Laserpointer vom Handy (Finger auf dem Live-Bild)."""
        from PySide6.QtCore import QPointF

        if x is None:
            self.laser.remote_point(None)
            if getattr(self, "_phone_laser_on", False):
                self._phone_laser_on = False
                if not self.laser_owner_open():
                    self.laser.set_remote(False)
            return
        if not self.laser.remote:
            self._phone_laser_on = True
            self.laser.set_remote(True)
        self.laser.remote_point(QPointF(x, y))

    def laser_owner_open(self) -> bool:
        """Ist „Zeigen & Zeichnen“ offen? (dann bleibt der Laser dort an)"""
        return bool(getattr(self, "presenter_open", False))

    def _cast_tick(self) -> None:
        """Solange ein Handy zuschaut: Status und Live-Bild von Monitor 2 auffrischen."""
        import time

        if not self.cast.running() or time.monotonic() - self.cast.preview_wanted > 5:
            return
        self._cast_snapshot()
        self.cast.preview = self._preview_jpeg()

    def _preview_jpeg(self) -> bytes:
        from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QSize, Qt
        from PySide6.QtGui import QColor, QFont, QImage, QPainter

        from .output_window import grab_scaled

        out = self.output
        if out.isVisible() and out.width() > 0:
            img = grab_scaled(out, QSize(640, 360))
            from .laser import draw_overlay

            draw_overlay(self, img)
        else:  # Erweitern: Monitor 2 ist ein normaler Bildschirm – nur ein Hinweis
            img = QImage(640, 360, QImage.Format_RGB32)
            img.fill(QColor("#0f172a"))
            p = QPainter(img)
            p.setPen(QColor("#cbd5e1"))
            f = QFont()
            f.setPixelSize(26)
            p.setFont(f)
            p.drawText(img.rect(), Qt.AlignCenter, "Monitor 2: normaler Bildschirm\n(" + self.describe()[:40] + ")")
            p.end()
        data = QByteArray()
        buf = QBuffer(data)
        buf.open(QIODevice.WriteOnly)
        img.save(buf, "JPEG", 70)
        buf.close()
        return bytes(data)

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
        elif kind == "laser":
            self._phone_laser(req.get("x"), req.get("y"))
            return
        elif kind == "draw":
            self._phone_draw(req)
            return
        elif kind == "mouse":
            self._phone_mouse(req)
            return
        elif kind == "cmd":
            cmd = req.get("cmd", "")
            videos = video_sources(self.output.content) if self.mode == "content" else []
            if cmd.startswith("taste:"):  # Präsentations-Fernbedienung: Taste ans aktive Programm
                from .platform import keys

                if not keys.send(cmd.split(":", 1)[1]):
                    self.message.emit("Tasten vom Handy gehen unter Wayland nicht – bitte die X11-Sitzung nutzen "
                                      "(Anmeldebildschirm: „Plasma (X11)“).")
            elif cmd.startswith("timer:"):  # Timer-Vorgabe vom Handy (Sekunden), gleich zeigen und starten
                from .timer import clock

                seconds = max(1, min(6 * 3600, int(cmd.split(":", 1)[1])))
                clock.set(seconds, "countdown", self.config["timer"].get("finished_text", ""))
                self.show_source(self.timer_source())  # nicht show_timer: setzt frische Timer auf die Setup-Dauer
                clock.start()
                self.sounds.play_event("timer_start")
                self.changed.emit()
            elif cmd == "timer_stopp":
                self.timer_action("reset")
            elif cmd == "zeichnung_zurueck":
                self.laser.undo()
            elif cmd == "kamera":
                self.start_camera()
            elif cmd == "airplay":
                self.start_airplay()
            elif cmd == "qr":
                self.start_cast()
            elif cmd.startswith("lautstaerke:"):
                self.set_media_volume(volume=max(0, min(100, int(cmd.split(":", 1)[1]))), muted=False)
            elif cmd.startswith("video_"):
                if videos:
                    {"video_pause": videos[0].toggle_play, "video_vor": lambda: videos[0].skip(10_000),
                     "video_zurueck": lambda: videos[0].skip(-10_000)}[cmd]()
            else:
                self.run_command(cmd)
        self._cast_snapshot()

    def _place_handy_window(self, *titles: str, apps: tuple[str, ...] = ()) -> None:
        """iPhone-Fenster (UxPlay) auf Monitor 2 legen – dauerhaft: auch wenn es erst
        viel später erscheint (UxPlay 1.68 öffnet sein Fenster erst, wenn sich das iPhone verbindet) oder nach
        einer neuen Verbindung neu aufgeht."""
        from PySide6.QtCore import QTimer

        self._stop_following()
        screen = self.output_screen()
        if screen is None or not self._handy_window:
            return
        g = screen.geometry()
        rect = (g.x(), g.y(), g.width(), g.height())
        titles = [t for t in titles if t]
        try:
            self._follow_token = self.windows.follow_windows(titles, screen.name(), rect)
        except Exception:  # noqa: BLE001
            self._follow_token = None
        if self._follow_token:
            return  # KDE: KWin erledigt das ab jetzt selbst
        placed: set[str] = set()

        def poll():
            if not self._handy_window:
                return
            try:
                windows = self.windows.list_windows()
            except Exception:  # noqa: BLE001
                return
            present = set()
            for w in windows:
                own_app = (w.app or "").lower() in apps and w.title != "uxplay-windows" \
                    and "log" not in w.title.lower()  # nicht dessen Einstellungs-/Protokollfenster
                if own_app or any(t in w.title for t in titles):
                    present.add(w.id)
                    if w.id not in placed:
                        try:
                            place = getattr(self.windows, "present_window", None) \
                                if self.config["handy"].get("airplay_borderless", True) else None
                            if place:  # Windows: randlos, genau Monitor 2, im Vordergrund
                                place(w.id, screen.name(), rect)
                            else:
                                self.windows.move_window(w.id, screen.name(), rect, True)
                            placed.add(w.id)
                        except Exception:  # noqa: BLE001
                            pass
            placed.intersection_update(present)  # geschlossene Fenster vergessen → neue wieder platzieren
            if self._handy_window == "airplay-quelle":  # iPhone-Bild da → Warte-Bildschirm ausblenden
                self.output.set_suspended(bool(present))

        self._follow_timer = QTimer(self, interval=2000)
        self._follow_timer.timeout.connect(poll)
        self._follow_timer.start()
        poll()

    def _stop_following(self) -> None:
        timer = getattr(self, "_follow_timer", None)
        if timer is not None:
            timer.stop()
            self._follow_timer = None
        token = getattr(self, "_follow_token", None)
        if token:
            try:
                self.windows.stop_follow(token)
            except Exception:  # noqa: BLE001
                pass
        self._follow_token = None

    def _stop_handy_window(self) -> None:
        self._stop_following()
        self.output.set_yield(False)
        if self._handy_window == "airplay":
            self.airplay.release()
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

    def default_camera(self) -> dict | None:
        """Kamera für die Kachel: gewählte Standard-Kamera, sonst die erste gefundene (None = keine da)."""
        from PySide6.QtMultimedia import QMediaDevices

        from .sources import camera_id

        devices = QMediaDevices.videoInputs()
        if not devices:
            return None
        wanted = self.config.get("default_camera", "")
        dev = next((d for d in devices if camera_id(d) == wanted), devices[0])
        return {"type": "camera", "device_id": camera_id(dev), "name": dev.description(),
                "fit": self.config.get("camera_fit", "cover") or "cover"}

    def start_camera(self, cfg: dict | None = None) -> None:
        cfg = cfg or self.default_camera()
        if cfg is None:
            self.message.emit("Keine Kamera gefunden.")
            return
        self.show_source(cfg)

    def start_content_setting(self) -> str:
        """Einstellung „Beim Start zeigen“ – ältere Konfigurationen: „letzten Inhalt“ an/aus."""
        value = self.config.get("start_content", "last") or "last"
        if value == "last" and not self.config["restore_last_content"]:
            return "none"
        return value

    def restore_last(self) -> None:
        what = self.start_content_setting()
        last = self.config["last_content"]
        if what == "last" and last:
            self.show_source(last, remember=False)
        elif what == "mirror":
            self.mirror()
        elif what == "camera":
            self.start_camera()
        elif what == "airplay":
            self.start_airplay()
        elif what == "cast":
            self.start_cast()
        elif what.startswith("scene:"):
            name = what.split(":", 1)[1]
            if self.config.get_scene(name):
                self.show_source({"type": "scene", "scene": name}, remember=False)
            else:
                self.message.emit(f"Start-Szene „{name}“ gibt es nicht mehr.")
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
    def agenda_sources(self) -> list:
        """Alle gerade sichtbaren Ablauf-Seiten (direkt oder in einer Szene)."""
        from .screens import DesignSource

        content = self.output.content
        if self.mode != "content" or content is None:
            return []
        found = [content] if isinstance(content, DesignSource) else content.findChildren(DesignSource)
        return [s for s in found if s.cfg.get("design") == "ablauf"]

    def step_agenda(self, delta: int) -> None:
        """Ablauf: nächsten/vorherigen Punkt markieren (Kachel, Tastenkürzel, Handy)."""
        sources = self.agenda_sources()
        if not sources:
            self.message.emit("Auf Monitor 2 ist gerade kein Ablauf zu sehen.")
            return
        for src in sources:
            count = len([line for line in src.cfg.get("text", "").splitlines() if line.strip()])
            src.cfg["current"] = max(1, min(count + 1, int(src.cfg.get("current", 1)) + delta))  # +1 = alles erledigt
            src.update()
        if self.content and self.content.get("type") == "design":  # merken (auch für den nächsten Start)
            self.content = {**self.content, "current": sources[0].cfg["current"]}
            self.config["last_content"] = self.content
        self.changed.emit()

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
            "ablauf_weiter": lambda: self.step_agenda(1),
            "ablauf_zurueck": lambda: self.step_agenda(-1),
            "kamera_zoom_plus": lambda: self.camera_zoom(1.25),
            "kamera_zoom_minus": lambda: self.camera_zoom(0.8),
            "kamera_zoom_aus": lambda: self.camera_zoom(None),
            "rgb_farbe": lambda: self.rgb.set_mode("farbe"),
            "rgb_monitor2": lambda: self.rgb.set_mode("monitor2"),
            "rgb_aus": lambda: self.rgb.set_mode("aus"),
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
        self._cast_timer.stop()
        try:
            self.airplay.failed.disconnect(self._airplay_failed)
        except (RuntimeError, TypeError):
            pass
        try:  # der Server ist ein Einzelstück – nicht an einen beendeten Controller gebunden lassen
            self.cast.request.disconnect(self._cast_request)
        except (RuntimeError, TypeError):
            pass
        self.rgb.shutdown()
        if self.config.data["sync"].get("enabled"):
            self._sync_timer.stop()
            self.run_sync()
        if self._config_saved in self.config.listeners:
            self.config.listeners.remove(self._config_saved)
        from .ui.util import wait_for_background

        wait_for_background(3000)
        self.output.shutdown()
        self.output.close()
