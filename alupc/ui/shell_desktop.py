"""AluPC-Oberfläche – die Desktop-Fläche: Symbole aus dem Desktop-Ordner (Dateien, Ordner, Verknüpfungen,
Programme) und die Widgets. Alles frei verschiebbar (Position wird gemerkt, wahlweise am Raster), neue Dateien im
Desktop-Ordner erscheinen von selbst (QFileSystemWatcher).

Programm-Logos: Windows aus der Verknüpfung (QFileIconProvider), Linux aus dem Icon-Theme – und falls Qt kein Theme
kennt, selbst gesucht (hicolor/Breeze/Adwaita/Papirus …, /usr/share/pixmaps, Flatpak). Erst wenn gar nichts da ist:
farbige Kachel mit Anfangsbuchstaben.
"""

from __future__ import annotations

import os
import sys
import zlib
from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import QFileInfo, QFileSystemWatcher, QPoint, QRect, QRectF, QSize, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QFont, QIcon, QImageReader, QLinearGradient, QPainter, \
    QPainterPath, QPixmap
from PySide6.QtWidgets import QFileIconProvider, QMenu, QRubberBand, QWidget

IS_WINDOWS = sys.platform.startswith("win")
SKIP = {"desktop.ini", "thumbs.db", ".directory", ".ds_store"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}


# --------------------------------------------------------------------------- Logos
def _icon_dirs() -> list[Path]:
    home = Path.home()
    data = [Path(os.environ.get("XDG_DATA_HOME") or home / ".local/share")]
    data += [Path(d) for d in (os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share").split(":") if d]
    data += [Path("/var/lib/flatpak/exports/share"), home / ".local/share/flatpak/exports/share"]
    return [home / ".icons"] + [d / "icons" for d in data]


@lru_cache(maxsize=1)
def icon_index() -> dict[str, str]:
    """Linux: alle Programm-Symbole der Icon-Themes → {Name: beste Datei} (svg vor großem png). Einmal aufgebaut."""
    best: dict[str, tuple[int, str]] = {}
    for base in _icon_dirs():
        if not base.is_dir():
            continue
        for root, _dirs, files in os.walk(base):
            if not root.endswith(("/apps", "/applications")):
                continue
            score = 1000 if "scalable" in root else 0
            for part in Path(root).parts:
                if "x" in part and part.split("x")[0].isdigit():
                    score = max(score, int(part.split("x")[0]))
            if "/hicolor/" in root:
                score += 1  # bei Gleichstand das Standard-Theme
            for f in files:
                stem, ext = os.path.splitext(f)
                if ext.lower() in (".png", ".svg") and best.get(stem, (-1, ""))[0] < score:
                    best[stem] = (score, os.path.join(root, f))
    for pix in (Path("/usr/share/pixmaps"),):
        if pix.is_dir():
            for f in pix.iterdir():
                if f.suffix.lower() in (".png", ".svg", ".xpm"):
                    best.setdefault(f.stem, (0, str(f)))
    return {k: v[1] for k, v in best.items()}


def icon_index_ready() -> bool:
    """Ist der Logo-Index schon gebaut? (Bauen dauert – nie im GUI-Thread anstoßen, nur im Hintergrund.)"""
    return icon_index.cache_info().currsize > 0


def _desktop_field(text: str, key: str) -> str:
    lines = text.splitlines()
    for want in (f"{key}[de]=", f"{key}="):
        for ln in lines:
            if ln.startswith(want):
                return ln.split("=", 1)[1].strip()
    return ""


def icon_file_for(path: str) -> str:
    """Linux: Bilddatei zum Programm (Icon= der .desktop-Datei). Leer = keins gefunden. Ohne Qt – auch im
    Hintergrund aufrufbar."""
    if IS_WINDOWS or not path.endswith(".desktop"):
        return ""
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    name = _desktop_field(text, "Icon")
    if not name:
        return ""
    if name.startswith("/"):
        return name if os.path.isfile(name) else ""
    return icon_index().get(name, "")


def app_icon_for(path: str) -> QIcon:
    """Logo eines Programms: Windows aus der Verknüpfung, Linux aus dem Icon-Theme (oder selbst gesucht)."""
    if IS_WINDOWS:
        return QFileIconProvider().icon(QFileInfo(path))
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return QIcon()
    name = _desktop_field(text, "Icon")
    if not name:
        return QIcon()
    if name.startswith("/"):
        return QIcon(name) if os.path.isfile(name) else QIcon()
    icon = QIcon.fromTheme(name)
    if not icon.isNull() and icon.availableSizes():
        return icon
    found = icon_index().get(name, "") if icon_index_ready() else ""
    return QIcon(found) if found else icon


def letter_icon(name: str, size: int = 96) -> QIcon:
    """Kein Logo gefunden: farbige Kachel mit Anfangsbuchstaben (Farbe fest je Name)."""
    hue = zlib.crc32(name.encode("utf-8")) % 360
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    g = QLinearGradient(0, 0, size, size)
    g.setColorAt(0, QColor.fromHsv(hue, 150, 250))
    g.setColorAt(1, QColor.fromHsv((hue + 35) % 360, 200, 190))
    p.setPen(Qt.NoPen)
    p.setBrush(g)
    p.drawRoundedRect(QRectF(size * 0.06, size * 0.06, size * 0.88, size * 0.88), size * 0.24, size * 0.24)
    f = QFont()
    f.setPixelSize(int(size * 0.44))
    f.setBold(True)
    p.setFont(f)
    p.setPen(QColor("#ffffff"))
    letter = next((ch for ch in name if ch.isalnum()), "?").upper()
    p.drawText(QRectF(0, 0, size, size * 0.98), int(Qt.AlignCenter), letter)
    p.end()
    return QIcon(pm)


def usable(icon: QIcon) -> bool:
    return not icon.isNull() and not icon.pixmap(48, 48).isNull()


@lru_cache(maxsize=4)
def folder_icon(size: int = 96) -> QIcon:
    """Eigenes Ordner-Symbol (auf Windows und Linux gleich): Mappe im Farbverlauf der Akzentfarbe."""
    from . import theme

    t = theme.current()
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    s = size
    back = QPainterPath()
    back.addRoundedRect(QRectF(s * 0.08, s * 0.2, s * 0.84, s * 0.64), s * 0.08, s * 0.08)
    tab = QPainterPath()
    tab.addRoundedRect(QRectF(s * 0.08, s * 0.14, s * 0.36, s * 0.16), s * 0.06, s * 0.06)
    dark = QColor(t.accent).darker(135)
    p.fillPath(back.united(tab), dark)
    front = QPainterPath()
    front.addRoundedRect(QRectF(s * 0.08, s * 0.32, s * 0.84, s * 0.52), s * 0.08, s * 0.08)
    g = QLinearGradient(0, s * 0.32, 0, s * 0.84)
    g.setColorAt(0, QColor(t.accent).lighter(135))
    g.setColorAt(1, QColor(t.accent2))
    p.fillPath(front, g)
    p.setPen(QColor(255, 255, 255, 90))
    p.drawLine(int(s * 0.14), int(s * 0.38), int(s * 0.86), int(s * 0.38))
    p.end()
    return QIcon(pm)


def image_thumb(path: str, size: int = 96) -> QIcon:
    reader = QImageReader(path)
    reader.setAutoTransform(True)
    src = reader.size()
    if src.isValid() and src.width() > 0:
        reader.setScaledSize(src.scaled(QSize(size, size), Qt.KeepAspectRatio))
    img = reader.read()
    if img.isNull():
        return QIcon()
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    r = QRectF((size - img.width()) / 2, (size - img.height()) / 2, img.width(), img.height())
    path_ = QPainterPath()
    path_.addRoundedRect(r, 6, 6)
    p.setClipPath(path_)
    p.drawImage(r, img)
    p.end()
    return QIcon(pm)


# --------------------------------------------------------------------------- Desktop-Ordner
def desktop_dirs() -> list[Path]:
    """Desktop-Ordner des Benutzers (auch „Schreibtisch“, OneDrive-Desktop) + unter Windows der öffentliche Desktop."""
    from PySide6.QtCore import QStandardPaths

    dirs = [Path(QStandardPaths.writableLocation(QStandardPaths.DesktopLocation))]
    if IS_WINDOWS and os.environ.get("PUBLIC"):
        dirs.append(Path(os.environ["PUBLIC"]) / "Desktop")
    out, seen = [], set()
    for d in dirs:
        key = str(d).lower() if IS_WINDOWS else str(d)
        if key not in seen and d.is_dir() and d != Path.home():
            seen.add(key)
            out.append(d)
    return out


def desktop_entries(dirs: list[Path] | None = None) -> list[dict]:
    """Alles, was auf dem Desktop liegt: [{key, name, path, kind}] – kind: folder, app (.desktop/.lnk/.url),
    image, file. Versteckte Dateien und desktop.ini bleiben weg."""
    out = []
    for d in desktop_dirs() if dirs is None else dirs:
        try:
            items = sorted(d.iterdir(), key=lambda f: (not f.is_dir(), f.name.lower()))  # Ordner zuerst
        except OSError:
            continue
        for f in items:
            if f.name.startswith(".") or f.name.lower() in SKIP:
                continue
            ext = f.suffix.lower()
            name, kind = f.name, "file"
            if f.is_dir():
                kind = "folder"
            elif ext == ".desktop":
                kind = "app"
                try:
                    text = f.read_text(encoding="utf-8", errors="replace")
                    name = _desktop_field(text, "Name") or f.stem
                except OSError:
                    name = f.stem
            elif ext in (".lnk", ".url"):
                kind, name = "app", f.stem
            elif ext in IMAGE_EXT:
                kind = "image"
            out.append({"key": str(f), "name": name, "path": str(f), "kind": kind})
    return out


def entry_icon(entry: dict, size: int = 96) -> QIcon:
    kind, path = entry["kind"], entry["path"]
    if kind == "folder":
        return folder_icon(size)
    if kind == "image":
        icon = image_thumb(path, size)
        if usable(icon):
            return icon
    if kind == "app" and path.endswith(".desktop"):
        icon = app_icon_for(path)
        return icon if usable(icon) else letter_icon(entry["name"], size)
    icon = QFileIconProvider().icon(QFileInfo(path))
    return icon if usable(icon) else letter_icon(entry["name"], size)


def open_entry(entry: dict) -> bool:
    """Öffnen wie im System: Ordner im Dateimanager, Dateien mit dem passenden Programm, Programme starten."""
    path = entry["path"]
    if not IS_WINDOWS and path.endswith(".desktop"):
        from ..pc_control import _launch_desktop

        return _launch_desktop(path)
    if IS_WINDOWS:
        try:
            os.startfile(path)  # noqa: S606 – Datei vom eigenen Desktop
            return True
        except OSError:
            return False
    return QDesktopServices.openUrl(QUrl.fromLocalFile(path))


# --------------------------------------------------------------------------- frei verschiebbar
class Movable:
    """Mit der Maus frei verschiebbar (innerhalb des Eltern-Widgets). `moved(key, QPoint)` am Ende."""

    def _init_move(self, key: str):
        self.move_key = key
        self._grab: QPoint | None = None
        self._dragged = False

    def _press(self, e) -> bool:
        if e.button() != Qt.LeftButton:
            return False
        self._grab = e.position().toPoint()
        self._dragged = False
        self.raise_()
        return True

    def _drag(self, e) -> None:
        if self._grab is None or not (e.buttons() & Qt.LeftButton):
            return
        delta = e.position().toPoint() - self._grab
        if not self._dragged and delta.manhattanLength() < 6:
            return
        self._dragged = True
        par = self.parentWidget()
        pos = self.pos() + delta
        pos.setX(max(0, min(par.width() - self.width(), pos.x())))
        pos.setY(max(0, min(par.height() - self.height(), pos.y())))
        self.move(pos)

    def _release(self) -> bool:
        was = self._dragged
        self._grab = None
        self._dragged = False
        if was:
            self.moved.emit(self.move_key, self.pos())
        return was


class DesktopIcon(Movable, QWidget):
    """Ein Symbol auf dem Desktop: Bild + Name (zweizeilig, mit Schatten), Doppelklick öffnet."""

    moved = Signal(str, QPoint)
    opened = Signal(dict)
    menu_requested = Signal(dict, QPoint)

    def __init__(self, entry: dict, size: int, parent=None):
        super().__init__(parent)
        self.entry = entry
        self._init_move("icon:" + entry["key"])
        self.icon_size = size
        self.icon = entry_icon(entry, size * 2)
        self.selected = False
        self._hover = False
        self.setFixedSize(size + 46, size + 50)
        self.setToolTip(entry["name"])
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover)

    def enterEvent(self, _e):
        self._hover = True
        self.update()

    def leaveEvent(self, _e):
        self._hover = False
        self.update()

    def _siblings(self) -> list:
        return [s for s in self.parentWidget().findChildren(DesktopIcon) if s is not self]

    def set_selected(self, on: bool) -> None:
        if self.selected != on:
            self.selected = on
            self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.RightButton:
            self.menu_requested.emit(self.entry, e.globalPosition().toPoint())
            return
        if e.modifiers() & Qt.ControlModifier and e.button() == Qt.LeftButton:  # Strg+Klick: zur Auswahl dazu/weg
            self.set_selected(not self.selected)
            return
        if self._press(e):
            if not self.selected:  # Klick auf ein nicht gewähltes Symbol: nur dieses wählen
                for sib in self._siblings():
                    sib.set_selected(False)
            self.set_selected(True)
            self._group_start = {s: s.pos() for s in self._siblings() if s.selected}
            self._own_start = self.pos()

    def mouseMoveEvent(self, e):
        self._drag(e)
        start = getattr(self, "_own_start", None)
        if self._dragged and start is not None:  # mehrere gewählt: alle mitziehen
            delta = self.pos() - start
            par = self.parentWidget()
            for sib, p in getattr(self, "_group_start", {}).items():
                q = p + delta
                sib.move(max(0, min(par.width() - sib.width(), q.x())), max(0, min(par.height() - sib.height(), q.y())))

    def mouseReleaseEvent(self, _e):
        group = getattr(self, "_group_start", {}) if self._dragged else {}
        self._group_start, self._own_start = {}, None
        if self._release():
            for sib in group:
                sib.moved.emit(sib.move_key, sib.pos())

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.opened.emit(self.entry)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(2, 2, -2, -2)
        if self.selected or self._hover:
            p.setPen(QColor(255, 255, 255, 70 if self.selected else 30))
            p.setBrush(QColor(255, 255, 255, 46 if self.selected else 22))
            p.drawRoundedRect(r, 12, 12)
        s = self.icon_size
        pm = self.icon.pixmap(QSize(s * 2, s * 2))
        target = QRectF((self.width() - s) / 2, 6, s, s)
        p.drawPixmap(target.toRect(), pm)
        f = QFont(self.font())
        f.setPixelSize(12)
        f.setWeight(QFont.DemiBold)
        p.setFont(f)
        text_r = QRectF(4, s + 10, self.width() - 8, self.height() - s - 12)
        fm = p.fontMetrics()
        words = self.entry["name"]
        lines = []
        for _ in range(2):  # höchstens zwei Zeilen, dann „…“
            if not words:
                break
            cut = len(words)
            while cut > 1 and fm.horizontalAdvance(words[:cut]) > text_r.width():
                cut -= 1
            if cut < len(words):  # lieber an Leerzeichen, Punkt, Strich umbrechen als mitten im Wort
                soft = max(words.rfind(ch, 0, cut) for ch in " .-_")
                if soft > cut // 3:
                    cut = soft + (0 if words[soft] == " " else 1)
            lines.append(words[:cut].strip())
            words = words[cut:].strip()
        if words and lines:
            lines[-1] = fm.elidedText(lines[-1] + " " + words, Qt.ElideRight, int(text_r.width()))
        y = text_r.top()
        for ln in lines:
            box = QRectF(text_r.left(), y, text_r.width(), fm.height())
            p.setPen(QColor(0, 0, 0, 170))
            p.drawText(box.translated(0, 1), int(Qt.AlignHCenter | Qt.AlignTop), ln)
            p.setPen(QColor("#ffffff"))
            p.drawText(box, int(Qt.AlignHCenter | Qt.AlignTop), ln)
            y += fm.height()
        p.end()


class DesktopArea(QWidget):
    """Fläche über der Taskleiste: Desktop-Symbole und Widgets, frei verschiebbar; Positionen in der Einstellung
    shell.pos als Anteil der Fläche (passt dann auch bei anderer Bildschirmgröße)."""

    changed_positions = Signal()

    def __init__(self, shell, parent=None):
        super().__init__(parent)
        self.shell = shell
        self.icons: list[DesktopIcon] = []
        self.widgets: dict[str, QWidget] = {}  # key → Widget (Uhr, Monitor 2, AluPC)
        self._watch = QFileSystemWatcher(self)
        self._watch.directoryChanged.connect(lambda _p: self._reload_soon.start())
        self._reload_soon = QTimer(self, singleShot=True, interval=400)
        self._reload_soon.timeout.connect(self.reload)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._area_menu)
        self.setFocusPolicy(Qt.ClickFocus)  # Strg+A, Enter für die gewählten Symbole
        self._band: QRubberBand | None = None
        self._band_from: QPoint | None = None
        self._band_keep: set = set()

    # ---- Einstellungen
    def cfg(self) -> dict:
        return self.shell.cfg()

    def cell(self) -> QSize:
        s = int(self.cfg()["icon_size"])
        return QSize(s + 50, s + 58)

    # ---- Inhalt
    def reload(self) -> None:
        for ic in self.icons:
            ic.deleteLater()
        self.icons = []
        dirs = desktop_dirs()
        old = self._watch.directories()
        if old:
            self._watch.removePaths(old)
        if dirs:
            self._watch.addPaths([str(d) for d in dirs])
        if self.cfg()["desktop_icons"]:
            size = int(self.cfg()["icon_size"])
            for entry in desktop_entries(dirs):
                ic = DesktopIcon(entry, size, self)
                ic.moved.connect(self._moved)
                ic.opened.connect(self._open)
                ic.menu_requested.connect(self._icon_menu)
                ic.show()
                self.icons.append(ic)
        self.place_all()

    def add_widget(self, key: str, w: QWidget) -> None:
        self.widgets[key] = w
        w.setParent(self)
        w.moved.connect(self._moved)

    def place_all(self) -> None:
        """Gemerkte Positionen anwenden, Neues auf den ersten freien Rasterplatz (von links oben, spaltenweise)."""
        pos = self.cfg()["pos"]
        taken: set[tuple[int, int]] = set()
        free_later = []
        for ic in self.icons:
            saved = pos.get(ic.move_key)
            if saved:
                ic.move(self._from_frac(saved, ic))
                taken.add(self._cell_of(ic.pos()))
            else:
                free_later.append(ic)
        c = self.cell()
        rows = max(1, (self.height() - 16) // c.height())
        i = 0
        for ic in free_later:
            while True:
                col, row = divmod(i, rows)
                i += 1
                if (col, row) not in taken:
                    break
            ic.move(16 + col * c.width(), 12 + row * c.height())
            taken.add((col, row))
        for key, w in self.widgets.items():
            on = self.cfg()["widgets"].get(key.split(":", 1)[1], True)
            w.setVisible(on)
            if not on:
                continue
            saved = pos.get(key)
            w.adjustSize()
            if saved:
                w.move(self._from_frac(saved, w))
            else:
                w.move(self._default_widget_pos(key, w))

    def _default_widget_pos(self, key: str, w: QWidget) -> QPoint:
        """Widgets zuerst rechts untereinander (Uhr, Monitor 2, AluPC)."""
        order = [k for k in ("widget:clock", "widget:monitor", "widget:quick") if k in self.widgets]
        y = 18
        for k in order:
            other = self.widgets[k]
            if k == key:
                return QPoint(max(0, self.width() - w.width() - 24), y)
            if other.isVisible():
                y += other.sizeHint().height() + 16
        return QPoint(max(0, self.width() - w.width() - 24), 18)

    def _cell_of(self, p: QPoint) -> tuple[int, int]:
        c = self.cell()
        return (max(0, (p.x() - 16 + c.width() // 2) // c.width()), max(0, (p.y() - 12 + c.height() // 2) // c.height()))

    def _from_frac(self, frac, w: QWidget) -> QPoint:
        x = int(float(frac[0]) * max(1, self.width() - w.width()))
        y = int(float(frac[1]) * max(1, self.height() - w.height()))
        return QPoint(max(0, x), max(0, y))

    def _moved(self, key: str, p: QPoint) -> None:
        w = self.sender()
        if key.startswith("icon:") and self.cfg()["snap"]:
            col, row = self._cell_of(p)
            c = self.cell()
            p = QPoint(16 + col * c.width(), 12 + row * c.height())
            p.setX(min(p.x(), self.width() - w.width()))
            p.setY(min(p.y(), self.height() - w.height()))
            w.move(p)
        pos = dict(self.cfg()["pos"])
        pos[key] = [round(p.x() / max(1, self.width() - w.width()), 4),
                    round(p.y() / max(1, self.height() - w.height()), 4)]
        self.shell.save(pos=pos)

    def arrange(self) -> None:
        """„Automatisch anordnen“: Symbole wieder ins Raster (Widgets bleiben, wo sie sind)."""
        pos = {k: v for k, v in self.cfg()["pos"].items() if not k.startswith("icon:")}
        self.shell.save(pos=pos)
        self.place_all()

    def reset_widgets(self) -> None:
        pos = {k: v for k, v in self.cfg()["pos"].items() if not k.startswith("widget:")}
        self.shell.save(pos=pos)
        self.place_all()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.place_all()

    # ---- Auswahlrahmen: auf freier Fläche ziehen markiert mehrere Symbole (Strg = dazu)
    def mousePressEvent(self, e):
        keep = bool(e.modifiers() & Qt.ControlModifier)
        if not keep:
            for ic in self.icons:  # Klick ins Leere: Auswahl weg
                ic.set_selected(False)
        if e.button() == Qt.LeftButton:
            self._band_from = e.position().toPoint()
            self._band_keep = {ic for ic in self.icons if ic.selected} if keep else set()
            if self._band is None:
                self._band = QRubberBand(QRubberBand.Rectangle, self)
                self._band.setStyleSheet("background: rgba(99,102,241,0.25); border: 1px solid rgba(165,180,252,0.9);")
            self._band.setGeometry(QRect(self._band_from, QSize()))
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self._band_from is None or not (e.buttons() & Qt.LeftButton):
            return super().mouseMoveEvent(e)
        rect = QRect(self._band_from, e.position().toPoint()).normalized()
        if rect.width() + rect.height() < 6:
            return
        self._band.setGeometry(rect)
        self._band.show()
        self._band.raise_()
        for ic in self.icons:
            ic.set_selected(ic in self._band_keep or rect.intersects(ic.geometry()))

    def mouseReleaseEvent(self, e):
        self._band_from = None
        if self._band is not None:
            self._band.hide()
        super().mouseReleaseEvent(e)

    def selected_icons(self) -> list:
        return [ic for ic in self.icons if ic.selected]

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_A and e.modifiers() & Qt.ControlModifier:
            for ic in self.icons:
                ic.set_selected(True)
            return
        if e.key() in (Qt.Key_Return, Qt.Key_Enter):
            for ic in self.selected_icons():
                self._open(ic.entry)
            return
        super().keyPressEvent(e)

    # ---- Aktionen
    def _open(self, entry: dict) -> None:
        if open_entry(entry):
            self.shell.step_aside()

    def _icon_menu(self, entry: dict, at: QPoint) -> None:
        menu = QMenu(self)
        menu.addAction("Öffnen", lambda: self._open(entry))
        menu.addAction("Im Ordner zeigen", lambda: QDesktopServices.openUrl(
            QUrl.fromLocalFile(str(Path(entry["path"]).parent))))
        menu.addSeparator()
        menu.addAction("Symbole automatisch anordnen", self.arrange)
        menu.exec(at)

    def _area_menu(self, at: QPoint) -> None:
        menu = QMenu(self)
        dirs = desktop_dirs()
        if dirs:
            menu.addAction("Desktop-Ordner öffnen", lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(dirs[0]))))
        menu.addAction("Neu laden", self.reload)
        menu.addAction("Symbole automatisch anordnen", self.arrange)
        menu.addAction("Widgets an den Standardplatz", self.reset_widgets)
        menu.addSeparator()
        menu.addAction("Oberfläche anpassen …", self.shell.customize)
        menu.exec(self.mapToGlobal(at))
