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
from .widgets import Banner, button, page_header


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
    box = QGroupBox("Sichern & Laden")
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
    """Dual-Boot: Windows ↔ Linux automatisch abgleichen."""
    config = page.config
    controller = page.controller
    box = QGroupBox("Dual-Boot-Abgleich")
    lay = QVBoxLayout(box)
    how = QLabel(
        "<b>1.</b> Einschalten · Windows-Laufwerk wählen<br>"
        "<b>2.</b> Auf dem anderen System: „Automatisch suchen“<br>"
        "Danach automatisch bei jeder Änderung")
    how.setWordWrap(True)
    lay.addWidget(how)
    status = Banner("", "info")
    lay.addWidget(status)
    enabled = QCheckBox("Automatisch abgleichen")
    lay.addWidget(enabled)
    row = QGridLayout()
    row.setHorizontalSpacing(8)
    row.setVerticalSpacing(8)
    pick = button("Laufwerk/Ordner wählen …", "window", primary=True)
    search = button("Automatisch suchen", "refresh")
    mount = button("Windows-Laufwerk einhängen …", "plus")
    now = button("Jetzt abgleichen", "sync")
    for i, b in enumerate((pick, search, mount, now)):
        row.addWidget(b, i // 2, i % 2)
    row.setColumnStretch(2, 1)
    lay.addLayout(row)
    mount.setVisible(not ss.IS_WINDOWS)

    def refresh():
        s = config.data["sync"]
        enabled.blockSignals(True)
        enabled.setChecked(bool(s.get("enabled")))
        enabled.blockSignals(False)
        if not s.get("folder"):
            status.set("Noch kein gemeinsamer Ordner gewählt.", "info")
        else:
            text = f"Ordner: {s['folder']}"
            if s.get("status"):
                text += f"\n{s['status']}" + (f" (zuletzt {s['last']})" if s.get("last") else "")
            bad = any(w in s.get("status", "") for w in ("nicht", "fehlgeschlagen", "Sicherung"))
            status.set(text, "warn" if bad else ("ok" if s.get("enabled") else "info"))
        now.setEnabled(bool(s.get("folder")) and bool(s.get("enabled")))

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
                               "device": ss.device_of(folder), "base_rev": 0, "base_hash": "", "status": ""}
        config.save()
        msg = controller.run_sync()
        refresh()
        controller.message.emit(("Einstellungen vom anderen System übernommen. " if existing else "") + msg)

    def do_pick():
        menu = QMenu(page)
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
        for part in parts:
            label = f"{part['label'] or part['path']} ({part['fstype']}, {part['size']})"

            def go(p=part):
                run_async(lambda: ss.mount_device(p["path"]), lambda mp: (
                    controller.message.emit(f"Eingehängt: {mp}" if mp else "Einhängen hat nicht geklappt."),
                    do_search() if mp else None))

            menu.addAction(label, go)
        menu.popup(mount.mapToGlobal(mount.rect().bottomLeft()))

    def toggle(on):
        config.data["sync"] = {**config.data["sync"], "enabled": bool(on)}
        config.save()
        if on and config.data["sync"].get("folder"):
            controller.run_sync()
        refresh()

    enabled.toggled.connect(toggle)
    pick.clicked.connect(do_pick)
    search.clicked.connect(do_search)
    mount.clicked.connect(do_mount)
    now.clicked.connect(lambda: (controller.run_sync(), refresh()))
    controller.sync_status.connect(lambda _m: refresh())
    note = QLabel("Mit: Startseite, Szenen, Design, Töne, Handy, RGB · Ohne: Monitore, Kameras, Fingerabdruck")
    note.setWordWrap(True)
    note.setObjectName("Muted")
    lay.addWidget(note)
    refresh()
    box.refresh = refresh
    return box
