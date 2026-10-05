"""Setup → „Sichern & Sync“: Einstellungen exportieren/importieren und Dual-Boot-Abgleich."""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QVBoxLayout,
)

from .. import settings_sync as ss
from .util import error_box, run_async
from . import theme
from .widgets import button, flow_row, page_header


class SectionPicker(QDialog):
    """Welche Bereiche exportieren/importieren? (Häkchen)"""

    def __init__(self, title: str, available: list[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 20, 22, 18)
        lay.addWidget(page_header(title, "Häkchen setzen, was dabei sein soll."))
        grid = QGridLayout()
        self.boxes: dict[str, QCheckBox] = {}
        for i, name in enumerate(available):
            box = QCheckBox(ss.SECTIONS[name][0])
            box.setChecked(True)
            self.boxes[name] = box
            grid.addWidget(box, i // 2, i % 2)
        lay.addLayout(grid)
        row = QHBoxLayout()
        only_start = button("Nur Startseite", "home")
        only_start.clicked.connect(lambda: [b.setChecked(n == "startseite") for n, b in self.boxes.items()])
        row.addWidget(only_start)
        row.addStretch(1)
        lay.addLayout(row)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Weiter")
        buttons.button(QDialogButtonBox.Cancel).setText("Abbrechen")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)

    def chosen(self) -> list[str]:
        return [n for n, b in self.boxes.items() if b.isChecked()]


def backup_group(page) -> QGroupBox:
    """Einstellungen in eine Datei sichern bzw. daraus laden (auch nur die Startseite)."""
    config = page.config
    box = QGroupBox("Sichern && Laden")
    lay = QVBoxLayout(box)
    info = QLabel("Alle Einstellungen als Datei · Sicherung oder zweiter PC")
    info.setWordWrap(True)
    info.setObjectName("Muted")
    lay.addWidget(info)
    row = QHBoxLayout()
    export = button("Exportieren …", "download", primary=True)
    imp = button("Importieren …", "upload")
    row.addWidget(export)
    row.addWidget(imp)
    row.addStretch(1)
    lay.addLayout(row)

    def do_export():
        picker = SectionPicker("Einstellungen exportieren", list(ss.SECTIONS), page)
        if picker.exec() != QDialog.Accepted or not picker.chosen():
            return
        chosen = picker.chosen()
        name = "AluPC-Startseite.json" if chosen == ["startseite"] else "AluPC-Einstellungen.json"
        path, _ = QFileDialog.getSaveFileName(page, "Einstellungen speichern", str(Path.home() / name),
                                              "AluPC-Einstellungen (*.json)")
        if not path:
            return
        try:
            Path(path).write_text(json.dumps(ss.export_settings(config, chosen), indent=1, ensure_ascii=False),
                                  encoding="utf-8")
        except OSError as exc:
            error_box(page, f"Speichern fehlgeschlagen: {exc}")
            return
        page.controller.message.emit(f"Einstellungen gespeichert: {Path(path).name}")

    def do_import():
        path, _ = QFileDialog.getOpenFileName(page, "Einstellungen laden", str(Path.home()),
                                              "AluPC-Einstellungen (*.json)")
        if not path:
            return
        try:
            exported = ss.read_export(path)
        except (OSError, ValueError) as exc:
            error_box(page, f"Datei kann nicht geladen werden: {exc}")
            return
        available = ss.sections_in(exported)
        picker = SectionPicker(f"Laden aus {Path(path).name}", available, page)
        if picker.exec() != QDialog.Accepted or not picker.chosen():
            return
        changed = ss.import_settings(config, exported, picker.chosen())
        page.controller.settings_imported.emit(changed)
        page.controller.message.emit("Einstellungen geladen." if changed else "Nichts geändert – war schon gleich.")

    export.clicked.connect(do_export)
    imp.clicked.connect(do_import)
    return box


def sync_group(page) -> QGroupBox:
    """Dual-Boot: Windows ↔ Linux automatisch abgleichen – Status-Karte, Bereiche zum An-/Abwählen, Verlauf."""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QFrame

    from . import icons

    config = page.config
    controller = page.controller
    box = QGroupBox("Dual-Boot-Abgleich")
    lay = QVBoxLayout(box)
    lay.setSpacing(12)
    # ---- Status-Karte
    card = QFrame()
    card.setObjectName("Card")
    cl = QHBoxLayout(card)
    cl.setContentsMargins(16, 14, 16, 14)
    cl.setSpacing(14)
    badge = QLabel()
    badge.setFixedSize(52, 52)
    badge.setAlignment(Qt.AlignCenter)
    cl.addWidget(badge, 0, Qt.AlignTop)
    texts = QVBoxLayout()
    texts.setSpacing(2)
    title = QLabel()
    title.setStyleSheet("font-size: 17px; font-weight: 800;")
    sub = QLabel()
    sub.setObjectName("Muted")
    sub.setWordWrap(True)
    sub.setTextInteractionFlags(Qt.TextSelectableByMouse)
    texts.addWidget(title)
    texts.addWidget(sub)
    cl.addLayout(texts, 1)
    enabled = QCheckBox("An")
    enabled.setToolTip("Automatisch abgleichen: beim Start, nach jeder Änderung, jede Minute und beim Beenden")
    cl.addWidget(enabled, 0, Qt.AlignTop)
    lay.addWidget(card)
    now = button("Jetzt abgleichen", "sync", primary=True)
    pick = button("Ordner wählen …", "window")
    search = button("Automatisch suchen", "refresh")
    mount = button("Windows-Laufwerk einhängen …", "plus")
    mount.setVisible(not ss.IS_WINDOWS)
    lay.addWidget(flow_row(now, pick, search, mount))
    # ---- Bereiche
    what = QLabel("<b>Was abgeglichen wird</b>")
    lay.addWidget(what)
    short = {"startseite": "Startseite", "szenen": "Szenen", "favoriten": "Websites & Medien",
             "tasten": "Tastenkürzel", "aussehen": "Darstellung", "schoner": "Schoner & Timer", "toene": "Töne",
             "monitor2": "Monitor 2", "handy": "Handy", "rgb": "RGB", "overlays": "Overlays",
             "fingerabdruck": "Fingerabdruck", "sprache": "Sprache", "spiele": "Spiele & WLAN", "extras": "Extras",
             "start": "App-Start"}
    section_boxes: dict[str, QCheckBox] = {}
    for name, (label, _keys) in ss.SECTIONS.items():
        cb = QCheckBox(short.get(name, label.split(" (")[0]).replace("&", "&&"))  # & sonst = Tastenkürzel
        cb.setToolTip(label)
        section_boxes[name] = cb
    lay.addWidget(flow_row(*section_boxes.values(), spacing=14))
    never = QLabel("Nie dabei: Monitore, Kameras, Mikrofon, Programmpfade – die sind je System anders.")
    never.setObjectName("Muted")
    never.setWordWrap(True)
    lay.addWidget(never)
    # ---- Verlauf
    lay.addWidget(QLabel("<b>Zuletzt</b>"))
    history = QLabel()
    history.setObjectName("Muted")
    history.setWordWrap(True)
    history.setTextInteractionFlags(Qt.TextSelectableByMouse)
    lay.addWidget(history)
    how = QLabel("So geht's: hier einschalten und das Windows-Laufwerk wählen. Auf dem anderen System verbindet "
                 "sich AluPC beim Start selbst (oder „Automatisch suchen“).")
    how.setObjectName("Muted")
    how.setWordWrap(True)
    lay.addWidget(how)

    def set_badge(color: str, icon_name: str):
        badge.setStyleSheet(f"background: {theme.current().soft(color, 0.16)}; border-radius: 16px;")
        badge.setPixmap(icons.pixmap(icon_name, color, 28))

    def refresh():
        t = theme.current()
        s = config.data["sync"]
        enabled.blockSignals(True)
        enabled.setChecked(bool(s.get("enabled")))
        enabled.blockSignals(False)
        status_text = s.get("status", "")
        bad = any(w in status_text for w in ("nicht", "fehlgeschlagen", "nur lesbar"))
        if not s.get("folder"):
            title.setText("Noch nicht eingerichtet")
            sub.setText("Einschalten und das Windows-Laufwerk wählen – das andere System findet den Ordner dann selbst.")
            set_badge(t.muted, "sync")
        elif not s.get("enabled"):
            title.setText("Aus")
            sub.setText(f"Ordner: {s['folder']}")
            set_badge(t.muted, "sync")
        elif bad:
            reachable = "erreichbar" not in status_text
            title.setText("Problem beim Abgleich" if reachable else "Ordner nicht erreichbar")
            hint = status_text if reachable else ("Windows-Laufwerk einhängen oder „Automatisch suchen“."
                                                  if not ss.IS_WINDOWS else "Ist das Laufwerk da?")
            sub.setText(f"{hint}\nOrdner: {s['folder']}")
            set_badge(t.warning, "sync")
        else:
            title.setText("Verbunden ✓")
            last = f"Zuletzt: {s['last']} · " if s.get("last") else ""
            sub.setText(f"{last}{status_text}\nOrdner: {s['folder']}")
            set_badge(t.success, "sync")
        skip = set(s.get("skip") or [])
        for name, cb in section_boxes.items():
            cb.blockSignals(True)
            cb.setChecked(name not in skip)
            cb.blockSignals(False)
        lines = list(reversed(s.get("history") or []))[:6]
        history.setText("\n".join(lines) if lines else "Noch nichts abgeglichen.")
        now.setEnabled(bool(s.get("folder")) and bool(s.get("enabled")))

    def set_section(name: str, on: bool):
        skip = set(config.data["sync"].get("skip") or [])
        (skip.discard if on else skip.add)(name)
        config.data["sync"] = {**config.data["sync"], "skip": sorted(skip)}
        config.save()
        refresh()

    for name, cb in section_boxes.items():
        cb.toggled.connect(lambda on, n=name: set_section(n, on))

    def use_folder(folder: Path):
        folder = ss.folder_for(folder)
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            error_box(page, f"Ordner kann nicht angelegt werden: {exc}\n\nUnter Linux: ist das Windows-Laufwerk "
                            "vielleicht nur lesbar (Windows-„Schnellstart“)?")
            return
        existing = ss.sync_file(folder).is_file()
        config.data["sync"] = {**config.data["sync"], "enabled": True, "folder": str(folder),
                               "device": ss.device_of(folder), "rel": "", "base_rev": 0, "base_hash": "",
                               "status": "", "declined": False}
        config.save()
        msg = controller.run_sync()
        refresh()
        controller.message.emit(("Einstellungen vom anderen System übernommen. " if existing else "") + msg)

    def do_pick():
        menu = QMenu(page)
        theme.round_popup(menu)
        for drive in ss.drives():
            menu.addAction(f"Laufwerk {drive}", lambda d=drive: use_folder(Path(d)))
        menu.addSeparator()

        def other():
            path = QFileDialog.getExistingDirectory(page, "Gemeinsamen Ordner wählen", str(Path.home()))
            if path:
                use_folder(Path(path))

        menu.addAction("Anderer Ordner …", other)
        menu.popup(pick.mapToGlobal(pick.rect().bottomLeft()))

    def do_search():
        hits = ss.find_existing()
        if not hits:
            QMessageBox.information(page, "AluPC", "Kein „AluPC-Sync“-Ordner gefunden.\n\nIst der Abgleich auf dem "
                                    "anderen System schon eingeschaltet? Unter Linux muss das Windows-Laufwerk "
                                    "eingehängt sein („Windows-Laufwerk einhängen …“).")
            return
        use_folder(hits[0])

    def do_mount():
        parts = ss.unmounted_partitions()
        if not parts:
            QMessageBox.information(page, "AluPC", "Kein weiteres Windows-/Daten-Laufwerk gefunden – alle sind "
                                    "schon eingehängt (oder es gibt keins).")
            return
        menu = QMenu(page)
        theme.round_popup(menu)
        for part in parts:
            label = f"{part['label'] or part['path']} ({part['fstype']}, {part['size']})"

            def go(p=part):
                run_async(lambda: ss.mount_device(p["path"]), lambda mp: (
                    controller.message.emit(f"Eingehängt: {mp}" if mp else "Einhängen hat nicht geklappt."),
                    do_search() if mp else None))

            menu.addAction(label, go)
        menu.popup(mount.mapToGlobal(mount.rect().bottomLeft()))

    def toggle(on):
        # selbst ausgeschaltet → beim Start nicht wieder automatisch verbinden
        config.data["sync"] = {**config.data["sync"], "enabled": bool(on), "declined": not on}
        config.save()
        if on and not config.data["sync"].get("folder"):
            hits = ss.find_existing()
            if hits:
                use_folder(hits[0])
                return
            do_pick()
        elif on:
            controller.run_sync()
        refresh()

    enabled.toggled.connect(toggle)
    pick.clicked.connect(do_pick)
    search.clicked.connect(do_search)
    mount.clicked.connect(do_mount)
    now.clicked.connect(lambda: (controller.run_sync(), refresh()))
    controller.sync_status.connect(lambda _m: refresh())
    refresh()
    box.refresh = refresh
    return box
