"""Fenster „An Fernseher senden“: Chromecast / AirPlay-Geräte suchen, Bildschirm hinschicken, stoppen."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QVBoxLayout,
)

from ..sender import AIRPLAY, CHROMECAST, SIZES
from . import icons, theme
from .widgets import button, page_header


class AddDeviceDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Gerät per IP-Adresse")
        self.kind = QComboBox()
        self.kind.addItem("Chromecast / Google TV", CHROMECAST)
        self.kind.addItem("AirPlay (Apple TV, Fernseher)", AIRPLAY)
        self.host = QLineEdit()
        self.host.setPlaceholderText("z. B. 192.168.1.40")
        self.name = QLineEdit()
        self.name.setPlaceholderText("optional, z. B. Wohnzimmer")
        form = QFormLayout(self)
        form.addRow("Art:", self.kind)
        form.addRow("IP-Adresse:", self.host)
        form.addRow("Name:", self.name)
        row = QHBoxLayout()
        ok, cancel = button("Hinzufügen", "plus", primary=True), button("Abbrechen")
        ok.clicked.connect(lambda: self.accept() if self.host.text().strip() else self.host.setFocus())
        cancel.clicked.connect(self.reject)
        row.addStretch(1)
        row.addWidget(cancel)
        row.addWidget(ok)
        form.addRow(row)


class SenderDialog(QDialog):
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.sender = controller.sender
        self.setWindowTitle("An Fernseher senden")
        self.setMinimumSize(520, 460)
        lay = QVBoxLayout(self)
        lay.addWidget(page_header("An Fernseher senden", "Chromecast, AirPlay oder Miracast", "cast"))
        note = QLabel("Zeigt den Bildschirm zusätzlich auf einem Chromecast, Google TV, Apple TV oder "
                      "AirPlay-Fernseher im selben Netz – kurz verzögert, ohne Ton.")
        note.setWordWrap(True)
        note.setObjectName("Muted")
        lay.addWidget(note)
        self.list = QListWidget()
        self.list.itemDoubleClicked.connect(lambda _i: self._send())
        self.list.currentItemChanged.connect(lambda *_: self._refresh())
        lay.addWidget(self.list, 1)
        self.status = QLabel()
        self.status.setWordWrap(True)
        lay.addWidget(self.status)
        self.busy = QProgressBar()  # läuft, solange verbunden wird (Schritt steht im Text darüber)
        self.busy.setRange(0, 0)
        self.busy.setTextVisible(False)
        self.busy.setFixedHeight(6)
        self.busy.hide()
        lay.addWidget(self.busy)
        opts = QHBoxLayout()
        self.size = QComboBox()
        for key in SIZES:
            self.size.addItem(key, key)
        self.size.setCurrentIndex(max(0, self.size.findData(self.sender.cfg()["size"])))
        self.size.currentIndexChanged.connect(lambda: self.sender._save(size=self.size.currentData()))
        self.size.setToolTip("Bildgröße – 720p reicht meist und ist am flüssigsten")
        opts.addWidget(QLabel("Qualität:"))
        opts.addWidget(self.size)
        opts.addStretch(1)
        lay.addLayout(opts)
        row = QHBoxLayout()
        self.b_scan = button("Suchen", "refresh")
        self.b_add = button("Per IP …", "plus")
        self.b_send = button("Senden", "cast", primary=True)
        self.b_stop = button("Stoppen", "x", danger=True)
        self.b_scan.clicked.connect(self.sender.scan)
        self.b_add.clicked.connect(self._add)
        self.b_send.clicked.connect(self._send)
        self.b_stop.clicked.connect(self.sender.stop)
        self.b_miracast = button("Miracast …", "cast")
        self.b_miracast.setToolTip("Miracast-Fernseher: Windows „Verbinden“ (Win+K) bzw. GNOME Network Displays")
        self.b_miracast.clicked.connect(controller.send_miracast)
        for b in (self.b_scan, self.b_add, self.b_miracast):
            row.addWidget(b)
        row.addStretch(1)
        row.addWidget(self.b_stop)
        row.addWidget(self.b_send)
        lay.addLayout(row)
        self.sender.devices_found.connect(self._fill)
        self.sender.changed.connect(self._refresh)
        self._fill(self.sender.devices or self.sender.manual_devices())
        self._refresh()

    def showEvent(self, event):
        super().showEvent(event)
        if not self.sender.devices and self.sender.state != "suche":
            self.sender.scan()

    def _fill(self, devices):
        current = self._selected()
        keep = current.key if current else (self.sender.target_dev.key if self.sender.target_dev
                                             else self.sender.cfg().get("last", ""))
        self.list.clear()
        col = theme.current().text
        for dev in devices:
            item = QListWidgetItem(icons.icon("cast" if dev.kind == CHROMECAST else "monitor", col, 20), dev.label())
            item.setData(Qt.UserRole, dev)
            item.setToolTip(f"{dev.host}:{dev.port}")
            self.list.addItem(item)
            if dev.key == keep:
                self.list.setCurrentItem(item)
        if self.list.currentItem() is None and self.list.count():
            self.list.setCurrentRow(0)
        self._refresh()

    def _selected(self):
        item = self.list.currentItem()
        return item.data(Qt.UserRole) if item is not None else None

    def _refresh(self):
        s = self.sender
        text = s.describe()
        if s.state == "suche":
            text = "Suche Chromecast- und AirPlay-Geräte …"
        elif s.state == "aus" and not self.list.count():
            text = ("Keine Geräte gefunden. Fernseher an und im selben Netz? Sonst „Per IP …“. "
                    "(Windows: Firewall-Frage mit „Zulassen“ beantworten.)")
        elif s.state == "aus":
            text = "Gerät wählen und „Senden“."
        self.status.setText(text)
        self.busy.setVisible(s.state in ("verbinde", "suche"))
        self.b_scan.setEnabled(s.state != "suche")
        self.b_send.setEnabled(self._selected() is not None and s.state != "verbinde")
        self.b_send.setText("An dieses Gerät" if s.running else "Senden")
        self.b_stop.setVisible(s.running)

    def _send(self):
        dev = self._selected()
        if dev is not None:
            self.sender.start(dev)

    def _add(self):
        dlg = AddDeviceDialog(self)
        if dlg.exec():
            dev = self.sender.add_manual(dlg.kind.currentData(), dlg.host.text(), dlg.name.text())
            for i in range(self.list.count()):
                if self.list.item(i).data(Qt.UserRole).key == dev.key:
                    self.list.setCurrentRow(i)
