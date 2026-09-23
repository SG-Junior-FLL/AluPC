"""Nur eine AluPC-Instanz; weitere Aufrufe (z. B. `alupc --befehl standbild`) schicken Befehle."""

from __future__ import annotations

import getpass

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket


def server_name() -> str:
    try:
        user = getpass.getuser()
    except Exception:  # noqa: BLE001
        user = "user"
    return f"alupc-{user}"


def send_to_running(command: str, timeout_ms: int = 1000) -> bool:
    """True, wenn eine laufende Instanz den Befehl bekommen hat."""
    sock = QLocalSocket()
    sock.connectToServer(server_name())
    if not sock.waitForConnected(timeout_ms):
        return False
    sock.write((command + "\n").encode("utf-8"))
    sock.flush()
    sock.waitForBytesWritten(timeout_ms)
    sock.disconnectFromServer()
    return True


class SingleInstance(QObject):
    command = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.server = QLocalServer(self)
        name = server_name()
        if not self.server.listen(name):
            QLocalServer.removeServer(name)  # Reste eines abgestürzten Programms entfernen
            self.server.listen(name)
        self.server.newConnection.connect(self._accept)

    def _accept(self):
        while self.server.hasPendingConnections():
            sock = self.server.nextPendingConnection()
            sock.readyRead.connect(lambda s=sock: self._read(s))
            sock.disconnected.connect(sock.deleteLater)

    def _read(self, sock):
        while sock.canReadLine():
            line = bytes(sock.readLine()).decode("utf-8", errors="replace").strip()
            if line:
                self.command.emit(line)
