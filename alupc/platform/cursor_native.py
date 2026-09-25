"""Mauszeiger systemnah: Aussehen des echten Zeigers holen und die Maus auf einen Monitor begrenzen.

* Windows: GetCursorInfo/DrawIconEx (Aussehen), ClipCursor (Begrenzen).
* X11: XFixesGetCursorImage (Aussehen), XFixes-Zeigersperren („pointer barriers“, Begrenzen).
* Wayland: Programme dürfen weder den Zeiger abfragen noch festhalten – dort gibt es nichts davon.

Alles ist vorsichtig gebaut: Geht etwas nicht, kommt None bzw. False zurück, nie ein Absturz.
"""

from __future__ import annotations

import ctypes
import sys

from PySide6.QtGui import QImage

IS_WINDOWS = sys.platform.startswith("win")


# =========================================================================== Windows
if IS_WINDOWS:
    from ctypes import wintypes

    class _CURSORINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("flags", wintypes.DWORD), ("hCursor", wintypes.HANDLE),
                    ("ptScreenPos", wintypes.POINT)]

    class _ICONINFO(ctypes.Structure):
        _fields_ = [("fIcon", wintypes.BOOL), ("xHotspot", wintypes.DWORD), ("yHotspot", wintypes.DWORD),
                    ("hbmMask", wintypes.HBITMAP), ("hbmColor", wintypes.HBITMAP)]

    class _BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
                    ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD),
                    ("biCompression", wintypes.DWORD), ("biSizeImage", wintypes.DWORD),
                    ("biXPelsPerMeter", wintypes.LONG), ("biYPelsPerMeter", wintypes.LONG),
                    ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]

    _win_ready = False

    def _win():
        global _win_ready
        u, g = ctypes.windll.user32, ctypes.windll.gdi32  # type: ignore[attr-defined]
        if not _win_ready:
            u.GetCursorInfo.argtypes = [ctypes.POINTER(_CURSORINFO)]
            u.GetIconInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(_ICONINFO)]
            u.DrawIconEx.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int, wintypes.HANDLE, ctypes.c_int,
                                     ctypes.c_int, wintypes.UINT, wintypes.HANDLE, wintypes.UINT]
            u.GetDC.argtypes = [wintypes.HWND]
            u.GetDC.restype = wintypes.HDC
            u.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
            u.ClipCursor.argtypes = [ctypes.c_void_p]
            g.CreateCompatibleDC.argtypes = [wintypes.HDC]
            g.CreateCompatibleDC.restype = wintypes.HDC
            g.CreateDIBSection.argtypes = [wintypes.HDC, ctypes.c_void_p, wintypes.UINT,
                                           ctypes.POINTER(ctypes.c_void_p), wintypes.HANDLE, wintypes.DWORD]
            g.CreateDIBSection.restype = wintypes.HBITMAP
            g.SelectObject.argtypes = [wintypes.HDC, wintypes.HANDLE]
            g.SelectObject.restype = wintypes.HANDLE
            g.DeleteObject.argtypes = [wintypes.HANDLE]
            g.DeleteDC.argtypes = [wintypes.HDC]
            _win_ready = True
        return u, g

    _BUF = 128  # Zeiger bis 128 px (auch bei großer Skalierung/Barrierefreiheit)

    def _draw_on(hcursor, background: int) -> bytes | None:
        u, g = _win()
        screen = u.GetDC(None)
        hdc = g.CreateCompatibleDC(screen)
        bmi = _BITMAPINFOHEADER(ctypes.sizeof(_BITMAPINFOHEADER), _BUF, -_BUF, 1, 32, 0, 0, 0, 0, 0, 0)
        bits = ctypes.c_void_p()
        bmp = g.CreateDIBSection(hdc, ctypes.byref(bmi), 0, ctypes.byref(bits), None, 0)
        try:
            if not bmp or not bits.value:
                return None
            old = g.SelectObject(hdc, bmp)
            ctypes.memset(bits, background, _BUF * _BUF * 4)
            ok = u.DrawIconEx(hdc, 0, 0, hcursor, 0, 0, 0, None, 3)  # DI_NORMAL
            data = ctypes.string_at(bits, _BUF * _BUF * 4) if ok else None
            g.SelectObject(hdc, old)
            return data
        finally:
            if bmp:
                g.DeleteObject(bmp)
            g.DeleteDC(hdc)
            u.ReleaseDC(None, screen)

    def _windows_cursor():
        u, g = _win()
        info = _CURSORINFO()
        info.cbSize = ctypes.sizeof(_CURSORINFO)
        if not u.GetCursorInfo(ctypes.byref(info)) or not (info.flags & 1) or not info.hCursor:
            return None  # Zeiger ausgeblendet (z. B. beim Tippen) oder nicht abfragbar
        key = int(info.hCursor)
        if key in _cache:
            return _cache[key]
        icon = _ICONINFO()
        if not u.GetIconInfo(info.hCursor, ctypes.byref(icon)):
            return None
        for bmp in (icon.hbmMask, icon.hbmColor):
            if bmp:
                g.DeleteObject(bmp)
        # Zweimal zeichnen (auf Weiß und auf Schwarz) → daraus Deckkraft und Farbe berechnen.
        # So klappen auch alte einfarbige Zeiger (Textcursor), die Windows „invertiert“ zeichnet.
        white, black = _draw_on(info.hCursor, 255), _draw_on(info.hCursor, 0)
        if white is None or black is None:
            return None
        out = bytearray(len(black))
        for i in range(0, len(black), 4):
            w, b = white[i + 1], black[i + 1]
            alpha = 255 - (w - b)
            if alpha > 255:  # invertierender Bereich → schwarz mit weißem Rand wäre ideal; schwarz reicht
                out[i:i + 4] = b"\x00\x00\x00\xff"
            elif alpha > 0:
                k = 255 / alpha
                out[i] = min(255, round(black[i] * k))
                out[i + 1] = min(255, round(black[i + 1] * k))
                out[i + 2] = min(255, round(black[i + 2] * k))
                out[i + 3] = alpha
        image = QImage(bytes(out), _BUF, _BUF, _BUF * 4, QImage.Format_ARGB32).copy()
        result = (image, (int(icon.xHotspot), int(icon.yHotspot)), key)
        if len(_cache) > 64:
            _cache.clear()
        _cache[key] = result
        return result

    class _MSLLHOOKSTRUCT(ctypes.Structure):
        _fields_ = [("pt", wintypes.POINT), ("mouseData", wintypes.DWORD), ("flags", wintypes.DWORD),
                    ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]

    _HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
    WH_MOUSE_LL = 14
    WM_MOUSEMOVE = 0x0200

    class MouseBlock:
        """Systemweite Maus-Sperre (Low-Level-Hook): Jede Bewegung, die auf Monitor 2 landen würde, wird
        abgefangen und an den Rand von Monitor 1 gesetzt. Ergänzt ClipCursor, das Windows bei manchen
        Ereignissen (Fensterwechsel, Strg+Alt+Entf …) selbst zurücksetzt.

        Läuft in einem eigenen Thread mit eigener Nachrichtenschleife: Windows ruft den Hook für JEDE
        Mausbewegung am PC auf und wartet darauf – wäre er im (manchmal beschäftigten) Oberflächen-Thread,
        würde die Maus am ganzen PC ruckeln."""

        WM_QUIT = 0x0012
        WM_APP_REHOOK = 0x8001

        def __init__(self):
            import threading

            u = self.u = ctypes.windll.user32  # type: ignore[attr-defined]
            u.SetWindowsHookExW.argtypes = [ctypes.c_int, _HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD]
            u.SetWindowsHookExW.restype = wintypes.HHOOK
            u.CallNextHookEx.argtypes = [wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
            u.CallNextHookEx.restype = ctypes.c_ssize_t
            u.UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]
            u.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
            u.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
            u.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
            k = self.k = ctypes.windll.kernel32  # type: ignore[attr-defined]
            k.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
            k.GetModuleHandleW.restype = wintypes.HMODULE
            self.module = k.GetModuleHandleW(None)
            self.hook = None
            self.block = None  # (x, y, b, h) Monitor 2 in echten Bildpunkten
            self.home = None   # Monitor 1
            self._proc = _HOOKPROC(self._callback)  # Verweis behalten, sonst räumt Python ihn weg
            self._thread = None
            self._thread_id = 0
            self._ready = threading.Event()
            self._threading = threading

        def _callback(self, code, wparam, lparam):
            try:
                block, home = self.block, self.home
                if code == 0 and wparam == WM_MOUSEMOVE and block and home:
                    info = ctypes.cast(lparam, ctypes.POINTER(_MSLLHOOKSTRUCT)).contents
                    x, y = info.pt.x, info.pt.y
                    bx, by, bw, bh = block
                    if bx <= x < bx + bw and by <= y < by + bh:
                        hx, hy, hw, hh = home
                        self.u.SetCursorPos(min(max(x, hx), hx + hw - 1), min(max(y, hy), hy + hh - 1))
                        return 1  # Bewegung auf Monitor 2 verschlucken
            except Exception:  # noqa: BLE001 - im Hook darf nie etwas hochgehen
                pass
            return self.u.CallNextHookEx(None, code, wparam, lparam)

        def _run(self):
            self._thread_id = self.k.GetCurrentThreadId()
            self.hook = self.u.SetWindowsHookExW(WH_MOUSE_LL, self._proc, self.module, 0)
            self._ready.set()
            msg = wintypes.MSG()
            while self.u.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.message == self.WM_APP_REHOOK:  # neu einhängen (falls Windows ihn entfernt hat)
                    if self.hook:
                        self.u.UnhookWindowsHookEx(self.hook)
                    self.hook = self.u.SetWindowsHookExW(WH_MOUSE_LL, self._proc, self.module, 0)
            if self.hook:
                self.u.UnhookWindowsHookEx(self.hook)
                self.hook = None

        def install(self, block, home) -> bool:
            self.block, self.home = block, home
            if self._thread is None or not self._thread.is_alive():
                self._ready.clear()
                self._thread = self._threading.Thread(target=self._run, name="alupc-maus-sperre", daemon=True)
                self._thread.start()
                self._ready.wait(2)
            else:
                self.u.PostThreadMessageW(self._thread_id, self.WM_APP_REHOOK, 0, 0)
            return bool(self.hook)

        def uninstall(self, keep_rects: bool = False) -> None:
            if not keep_rects:
                self.block = self.home = None
            if self._thread is not None and self._thread.is_alive():
                self.u.PostThreadMessageW(self._thread_id, self.WM_QUIT, 0, 0)
                self._thread.join(2)
            self._thread = None

    def clip_cursor(rect) -> bool:
        """Maus auf `rect` (x, y, breite, höhe in echten Bildpunkten) begrenzen; None = frei."""
        u, _g = _win()
        if rect is None:
            return bool(u.ClipCursor(None))
        x, y, w, h = rect
        r = wintypes.RECT(x, y, x + w, y + h)
        return bool(u.ClipCursor(ctypes.byref(r)))

_cache: dict = {}


# =========================================================================== X11
class _XFixesCursorImage(ctypes.Structure):
    _fields_ = [("x", ctypes.c_short), ("y", ctypes.c_short), ("width", ctypes.c_ushort),
                ("height", ctypes.c_ushort), ("xhot", ctypes.c_ushort), ("yhot", ctypes.c_ushort),
                ("cursor_serial", ctypes.c_ulong), ("pixels", ctypes.POINTER(ctypes.c_ulong)),
                ("atom", ctypes.c_ulong), ("name", ctypes.c_char_p)]


class _X11:
    """Eigene, kleine Verbindung zum X-Server (unabhängig von Qt)."""

    def __init__(self):
        import ctypes.util

        xlib = ctypes.util.find_library("X11")
        xfixes = ctypes.util.find_library("Xfixes")
        if not xlib or not xfixes:
            raise OSError("libX11/libXfixes fehlen")
        self.x = ctypes.CDLL(xlib)
        self.f = ctypes.CDLL(xfixes)
        self.x.XOpenDisplay.restype = ctypes.c_void_p
        self.x.XOpenDisplay.argtypes = [ctypes.c_char_p]
        self.x.XDefaultRootWindow.restype = ctypes.c_ulong
        self.x.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
        self.x.XFlush.argtypes = [ctypes.c_void_p]
        self.x.XFree.argtypes = [ctypes.c_void_p]
        self.f.XFixesGetCursorImage.restype = ctypes.POINTER(_XFixesCursorImage)
        self.f.XFixesGetCursorImage.argtypes = [ctypes.c_void_p]
        self.f.XFixesCreatePointerBarrier.restype = ctypes.c_ulong
        self.f.XFixesCreatePointerBarrier.argtypes = [ctypes.c_void_p, ctypes.c_ulong] + [ctypes.c_int] * 5 + [
            ctypes.c_int, ctypes.c_void_p]
        self.f.XFixesDestroyPointerBarrier.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        self.dpy = self.x.XOpenDisplay(None)
        if not self.dpy:
            raise OSError("Keine Verbindung zum X-Server")
        self.root = self.x.XDefaultRootWindow(self.dpy)

    def cursor(self):
        img = self.f.XFixesGetCursorImage(self.dpy)
        if not img:
            return None
        try:
            c = img.contents
            key = ("x11", int(c.cursor_serial))
            if key in _cache:
                return _cache[key]
            n = c.width * c.height
            argb = bytearray(n * 4)
            for i in range(n):
                v = c.pixels[i] & 0xFFFFFFFF  # „unsigned long“, nur die unteren 32 Bit zählen
                argb[i * 4:i * 4 + 4] = v.to_bytes(4, "little")
            image = QImage(bytes(argb), c.width, c.height, c.width * 4,
                           QImage.Format_ARGB32_Premultiplied).copy()
            result = (image, (int(c.xhot), int(c.yhot)), key)
            if len(_cache) > 64:
                _cache.clear()
            _cache[key] = result
            return result
        finally:
            self.x.XFree(img)

    def barriers(self, lines) -> list[int]:
        made = []
        for x1, y1, x2, y2 in lines:
            b = self.f.XFixesCreatePointerBarrier(self.dpy, self.root, x1, y1, x2, y2, 0, 0, None)
            if b:
                made.append(b)
        self.x.XFlush(self.dpy)
        return made

    def remove(self, barriers) -> None:
        for b in barriers:
            self.f.XFixesDestroyPointerBarrier(self.dpy, b)
        self.x.XFlush(self.dpy)


_x11: _X11 | None = None
_x11_failed = False


def _x11_conn() -> _X11 | None:
    global _x11, _x11_failed
    if _x11 is None and not _x11_failed:
        try:
            _x11 = _X11()
        except Exception:  # noqa: BLE001
            _x11_failed = True
    return _x11


def is_x11() -> bool:
    from PySide6.QtGui import QGuiApplication

    return sys.platform.startswith("linux") and QGuiApplication.platformName() == "xcb"


# =========================================================================== gemeinsam
def cursor_image():
    """(Bild, (Hotspot-x, Hotspot-y), Schlüssel) des echten Mauszeigers in echten Bildpunkten – oder None."""
    try:
        if IS_WINDOWS:
            return _windows_cursor()
        if is_x11():
            conn = _x11_conn()
            return conn.cursor() if conn else None
    except Exception:  # noqa: BLE001
        return None
    return None


def barrier_lines(rect) -> list[tuple[int, int, int, int]]:
    """Die vier Kanten eines Rechtecks (x, y, b, h) als Sperrlinien."""
    x, y, w, h = rect
    return [(x, y, x, y + h), (x + w, y, x + w, y + h), (x, y, x + w, y), (x, y + h, x + w, y + h)]


class X11Barriers:
    """Unsichtbare Wände um Monitor 2 (X11). Die Maus kommt nicht mehr hinein."""

    def __init__(self):
        self.active: list[int] = []
        self.rect = None

    def set(self, rect) -> bool:
        if rect == self.rect and self.active:
            return True
        self.clear()
        conn = _x11_conn()
        if conn is None or rect is None:
            return False
        try:
            self.active = conn.barriers(barrier_lines(rect))
            self.rect = rect
        except Exception:  # noqa: BLE001
            self.active = []
        return bool(self.active)

    def clear(self) -> None:
        conn = _x11_conn()
        if conn is not None and self.active:
            try:
                conn.remove(self.active)
            except Exception:  # noqa: BLE001
                pass
        self.active = []
        self.rect = None
