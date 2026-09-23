"""Tastenkürzel: in AluPC immer, unter Windows zusätzlich systemweit (RegisterHotKey)."""

from __future__ import annotations

import sys

from PySide6.QtCore import QAbstractNativeEventFilter, QCoreApplication, QObject, Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut

MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN, MOD_NOREPEAT = 0x1, 0x2, 0x4, 0x8, 0x4000
WM_HOTKEY = 0x0312


def to_windows_hotkey(sequence: str) -> tuple[int, int] | None:
    """„Ctrl+Alt+S“ → (Modifikatoren, virtueller Tastencode) für RegisterHotKey."""
    seq = QKeySequence(sequence, QKeySequence.PortableText)
    if seq.isEmpty():
        return None
    combo = seq[0]
    key = combo.key()
    mods = combo.keyboardModifiers()
    win_mods = MOD_NOREPEAT
    if mods & Qt.ControlModifier:
        win_mods |= MOD_CONTROL
    if mods & Qt.AltModifier:
        win_mods |= MOD_ALT
    if mods & Qt.ShiftModifier:
        win_mods |= MOD_SHIFT
    if mods & Qt.MetaModifier:
        win_mods |= MOD_WIN
    k = int(key.value) if hasattr(key, "value") else int(key)
    if 0x30 <= k <= 0x39 or 0x41 <= k <= 0x5A:  # Ziffern und Buchstaben = gleicher Code
        return win_mods, k
    f1 = int(Qt.Key_F1.value)
    if f1 <= k <= f1 + 23:
        return win_mods, 0x70 + (k - f1)
    special = {
        int(Qt.Key_Space.value): 0x20, int(Qt.Key_Pause.value): 0x13,
        int(Qt.Key_Home.value): 0x24, int(Qt.Key_End.value): 0x23,
        int(Qt.Key_Insert.value): 0x2D, int(Qt.Key_Delete.value): 0x2E,
        int(Qt.Key_PageUp.value): 0x21, int(Qt.Key_PageDown.value): 0x22,
        int(Qt.Key_Left.value): 0x25, int(Qt.Key_Up.value): 0x26,
        int(Qt.Key_Right.value): 0x27, int(Qt.Key_Down.value): 0x28,
    }
    if k in special:
        return win_mods, special[k]
    return None


class _WinHotkeyFilter(QAbstractNativeEventFilter):
    def __init__(self, callback):
        super().__init__()
        self.callback = callback

    def nativeEventFilter(self, event_type, message):
        if bytes(event_type) == b"windows_generic_MSG":
            from ctypes import wintypes

            msg = wintypes.MSG.from_address(int(message))
            if msg.message == WM_HOTKEY:
                self.callback(int(msg.wParam))
                return True, 0
        return False, 0


class HotkeyManager(QObject):
    triggered = Signal(str)

    def __init__(self):
        super().__init__()
        self.window = None
        self.shortcuts: list[QShortcut] = []
        self.win_ids: dict[int, str] = {}
        self._filter = None
        if sys.platform.startswith("win"):
            self._filter = _WinHotkeyFilter(self._on_win_hotkey)
            QCoreApplication.instance().installNativeEventFilter(self._filter)

    def attach(self, window) -> None:
        """Fenster, an dem die In-App-Kürzel hängen."""
        self.window = window
        self.setParent(window)

    def _on_win_hotkey(self, hotkey_id: int):
        action = self.win_ids.get(hotkey_id)
        if action:
            self.triggered.emit(action)

    def apply(self, hotkeys: dict[str, str]) -> list[str]:
        """Tastenkürzel neu setzen; liefert Liste mit Problemen (z. B. Kürzel schon belegt)."""
        problems: list[str] = []
        for sc in self.shortcuts:
            sc.setEnabled(False)
            sc.deleteLater()
        self.shortcuts = []
        self._unregister_windows()
        for i, (action, seq) in enumerate(hotkeys.items(), start=1):
            if not seq:
                continue
            if sys.platform.startswith("win"):
                if self._register_windows(i, action, seq):
                    continue  # systemweit registriert → kein zusätzliches In-App-Kürzel nötig
                problems.append(f"„{seq}“ ist in Windows schon belegt – gilt nur, wenn AluPC aktiv ist.")
            if self.window is None:
                continue
            sc = QShortcut(QKeySequence(seq, QKeySequence.PortableText), self.window)
            sc.setContext(Qt.ApplicationShortcut)
            sc.activated.connect(lambda a=action: self.triggered.emit(a))
            self.shortcuts.append(sc)
        return problems

    def _register_windows(self, hotkey_id: int, action: str, seq: str) -> bool:
        import ctypes

        parsed = to_windows_hotkey(seq)
        if parsed is None:
            return False
        mods, vk = parsed
        if ctypes.windll.user32.RegisterHotKey(None, hotkey_id, mods, vk):  # type: ignore[attr-defined]
            self.win_ids[hotkey_id] = action
            return True
        return False

    def _unregister_windows(self):
        if not self.win_ids:
            return
        import ctypes

        for hotkey_id in self.win_ids:
            ctypes.windll.user32.UnregisterHotKey(None, hotkey_id)  # type: ignore[attr-defined]
        self.win_ids = {}
