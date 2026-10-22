"""Seite „Updates“ (unter Geräte): PC nach Updates und Treibern durchsuchen – Windows und Linux gleich.

Nur prüfen und zeigen; installiert wird mit den Werkzeugen des Systems (Knöpfe „… öffnen“). Siehe pc_updates.
"""

from __future__ import annotations

import time

from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from . import icons, theme
from .util import run_async
from .widgets import button, font, page_header


def _card(title: str, icon_name: str) -> tuple[QFrame, QVBoxLayout, QHBoxLayout, QLabel]:
    card = QFrame()
    card.setObjectName("Card")
    lay = QVBoxLayout(card)
    lay.setContentsMargins(18, 16, 18, 16)
    lay.setSpacing(10)
    head = QHBoxLayout()
    ic = QLabel()
    ic.setPixmap(icons.pixmap(icon_name, theme.current().accent, 22))
    head.addWidget(ic)
    lab = QLabel(f"<b>{title}</b>")
    lab.setFont(font(12.5))
    head.addWidget(lab)
    count = QLabel()
    head.addWidget(count)
    head.addStretch(1)
    lay.addLayout(head)
    return card, lay, head, count


def _tree(columns: list[str]) -> QTreeWidget:
    tree = QTreeWidget()
    tree.setHeaderLabels(columns)
    tree.setRootIsDecorated(False)
    tree.setUniformRowHeights(True)
    tree.setAlternatingRowColors(True)
    tree.setSelectionMode(QTreeWidget.NoSelection)
    tree.setMinimumHeight(140)
    h = tree.header()
    h.setStretchLastSection(False)
    h.setSectionResizeMode(0, QHeaderView.Stretch)
    for i in range(1, len(columns)):
        h.setSectionResizeMode(i, QHeaderView.ResizeToContents)
    return tree


class UpdatesPage(QWidget):
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.busy = False
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(14)
        root.addWidget(page_header("Updates", "PC nach Updates und Treibern durchsuchen", "download"))

        top = QHBoxLayout()
        self.scan_btn = button("Jetzt prüfen", "search", primary=True)
        self.scan_btn.clicked.connect(self.scan)
        top.addWidget(self.scan_btn)
        self.status = QLabel("Noch nicht geprüft. Nur nachsehen – installiert wird nichts ohne dich.")
        self.status.setObjectName("Muted")
        self.status.setWordWrap(True)
        top.addWidget(self.status, 1)
        root.addLayout(top)

        card, lay, head, self.upd_count = _card("System und Programme", "download")
        self.updates = _tree(["Name", "Jetzt", "Neu", "Quelle"])
        lay.addWidget(self.updates)
        row = QHBoxLayout()
        self.open_upd = button("Aktualisieren öffnen", "refresh")
        self.open_upd.clicked.connect(lambda: self._open("updates"))
        row.addWidget(self.open_upd)
        self.winget_btn = button("Alle Programme aktualisieren (winget)", "download")
        self.winget_btn.setToolTip("Öffnet ein Fenster mit „winget upgrade --all“ – man sieht, was passiert")
        self.winget_btn.clicked.connect(lambda: self._open("programme"))
        self.winget_btn.hide()
        row.addWidget(self.winget_btn)
        row.addStretch(1)
        lay.addLayout(row)
        root.addWidget(card)

        card, lay, head, self.drv_count = _card("Treiber und Firmware", "sliders")
        self.drivers = _tree(["Gerät / Treiber", "Hinweis", "Quelle"])
        lay.addWidget(self.drivers)
        row = QHBoxLayout()
        open_drv = button("Treiber-Updates öffnen", "refresh")
        open_drv.clicked.connect(lambda: self._open("drivers"))
        row.addWidget(open_drv)
        row.addStretch(1)
        lay.addLayout(row)
        root.addWidget(card)

        self.notes = QLabel()
        self.notes.setObjectName("Muted")
        self.notes.setWordWrap(True)
        root.addWidget(self.notes)
        root.addStretch(1)
        last = getattr(controller, "pc_update_result", None)
        if last:
            self.show_result(*last)

    # ------------------------------------------------------------ Prüfen
    def scan(self) -> None:
        if self.busy:
            return
        from .. import pc_updates

        self.busy = True
        self.scan_btn.setEnabled(False)
        self.status.setText("Prüfe …")

        def work(status):
            return pc_updates.scan(lambda text: status(text, 0, 0))

        def done(result):
            self.busy = False
            self.scan_btn.setEnabled(True)
            self.controller.pc_update_result = (result, time.time())
            self.show_result(result, time.time())

        def failed(err):
            self.busy = False
            self.scan_btn.setEnabled(True)
            self.status.setText(f"Prüfen ging nicht: {err}")

        run_async(work, done, failed, on_progress=lambda text, *_a: self.status.setText(text), owner=self)

    def show_result(self, result: dict, at: float) -> None:
        t = theme.current()
        self.updates.clear()
        for u in result.get("updates", []):
            QTreeWidgetItem(self.updates, [u["name"], u["current"] or "–", u["new"] or "–", u["source"]]) \
                .setToolTip(0, u.get("note") or u["name"])
        self.drivers.clear()
        for d in result.get("drivers", []):
            hint = d.get("note") or (f"{d['current']} → {d['new']}" if d.get("new") else "Update verfügbar")
            QTreeWidgetItem(self.drivers, [d["name"], hint, d["source"]])
        nu, nd = len(result.get("updates", [])), len(result.get("drivers", []))
        for label, n in ((self.upd_count, nu), (self.drv_count, nd)):
            color = t.warning if n else t.success
            label.setText(f"{n} offen" if n else "✓ aktuell")
            label.setStyleSheet(f"color:{color}; background:{t.soft(color, 0.14)}; border-radius:10px; "
                                "padding:2px 10px; font-weight:700;")
        self.winget_btn.setVisible(any(u["source"] == "winget" for u in result.get("updates", [])))
        when = time.strftime("%H:%M", time.localtime(at))
        checked = ", ".join(result.get("checked", [])) or "nichts"
        if nu or nd:
            self.status.setText(f"Geprüft um {when}: {nu} Updates, {nd} bei Treibern/Firmware.")
        else:
            self.status.setText(f"Geprüft um {when}: alles aktuell.")
        notes = [f"Geprüft: {checked}."] + result.get("errors", [])
        self.notes.setText("\n".join(notes))

    def _open(self, kind: str) -> None:
        from .. import pc_updates

        try:
            _ok, text = pc_updates.open_updater(kind)
        except OSError as exc:
            text = str(exc)
        self.controller.message.emit(text)
