"""Wetter & Uhr auf Monitor 2 – Daten von Open-Meteo (kostenlos, ohne Anmeldung/Schlüssel).

Ort einmal eintragen (z. B. „Berlin“), AluPC sucht die Koordinaten und holt alle 15 Minuten das Wetter.
Ohne Internet zeigt die Seite trotzdem die Uhr (und das zuletzt geholte Wetter mit Uhrzeit).
"""

from __future__ import annotations

import json
import math
import threading
import time
import urllib.parse
import urllib.request

from PySide6.QtCore import QObject, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from .sources import fitted_font, format_date_de

GEO_URL = "https://geocoding-api.open-meteo.com/v1/search"
API_URL = "https://api.open-meteo.com/v1/forecast"
REFRESH = 15 * 60
WEEKDAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]

# WMO-Wettercodes → (Text, Symbol)
CODES = {
    0: ("Klar", "sonne"), 1: ("Überwiegend klar", "sonne"), 2: ("Teilweise bewölkt", "wolke_sonne"),
    3: ("Bedeckt", "wolke"), 45: ("Nebel", "nebel"), 48: ("Nebel mit Reif", "nebel"),
    51: ("Leichter Nieselregen", "regen"), 53: ("Nieselregen", "regen"), 55: ("Starker Nieselregen", "regen"),
    56: ("Gefrierender Niesel", "regen"), 57: ("Gefrierender Niesel", "regen"),
    61: ("Leichter Regen", "regen"), 63: ("Regen", "regen"), 65: ("Starker Regen", "regen"),
    66: ("Gefrierender Regen", "regen"), 67: ("Gefrierender Regen", "regen"),
    71: ("Leichter Schnee", "schnee"), 73: ("Schnee", "schnee"), 75: ("Starker Schnee", "schnee"),
    77: ("Schneegriesel", "schnee"), 80: ("Regenschauer", "regen"), 81: ("Regenschauer", "regen"),
    82: ("Heftige Schauer", "regen"), 85: ("Schneeschauer", "schnee"), 86: ("Schneeschauer", "schnee"),
    95: ("Gewitter", "gewitter"), 96: ("Gewitter mit Hagel", "gewitter"), 99: ("Gewitter mit Hagel", "gewitter"),
}


def describe(code: int) -> tuple[str, str]:
    return CODES.get(int(code), ("Wetter", "wolke"))


def _get_json(url: str, params: dict, timeout: float = 10) -> dict:
    full = url + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(full, headers={"User-Agent": "AluPC"})
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 - feste https-Adresse
        return json.loads(r.read().decode("utf-8"))


NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"


def _place(r: dict, fallback: str, postcode: str = "") -> dict:
    label = ", ".join(x for x in (f"{postcode} {r.get('name', '')}".strip() if postcode else r.get("name"),
                                  r.get("admin1"), r.get("country")) if x)
    return {"name": r.get("name", fallback), "lat": float(r["latitude"]), "lon": float(r["longitude"]),
            "label": label}


def geocode(name: str) -> dict | None:
    """Ort suchen → {"name", "lat", "lon", "label"} oder None.
    Eine 5-stellige Zahl ist eine deutsche Postleitzahl (nicht eine aus den USA): Suche nur in Deutschland."""
    import re

    text = " ".join(name.split())
    m = re.match(r"^(\d{5})(?:\s+(.*))?$", text)
    if m:  # „80331“ oder „80331 München“
        plz = m.group(1)
        data = _get_json(GEO_URL, {"name": plz, "count": 10, "language": "de", "format": "json",
                                   "countryCode": "DE"})
        results = [r for r in (data.get("results") or []) if r.get("country_code", "DE").upper() == "DE"]
        exact = [r for r in results if plz in (r.get("postcodes") or [])]
        if exact:  # nur Treffer, zu denen die PLZ wirklich gehört (keine ähnlich klingenden Orte)
            return _place(exact[0], text, plz)
        # Open-Meteo kennt die PLZ nicht → OpenStreetMap (Nominatim) fragen, ebenfalls nur Deutschland
        hits = _get_json(NOMINATIM_URL, {"postalcode": plz, "country": "de", "format": "json", "limit": 1,
                                         "addressdetails": 1, "accept-language": "de"})
        if not hits:
            return None
        h = hits[0]
        addr = h.get("address") or {}
        town = addr.get("city") or addr.get("town") or addr.get("village") or addr.get("municipality") or plz
        return _place({"name": town, "admin1": addr.get("state"), "country": addr.get("country", "Deutschland"),
                       "latitude": h["lat"], "longitude": h["lon"]}, text, plz)
    data = _get_json(GEO_URL, {"name": text, "count": 1, "language": "de", "format": "json"})
    results = data.get("results") or []
    return _place(results[0], text) if results else None


def parse_forecast(data: dict) -> dict:
    cur = data.get("current") or {}
    daily = data.get("daily") or {}
    days = []
    for i, day in enumerate(daily.get("time") or []):
        try:
            days.append({"date": day, "code": int(daily["weather_code"][i]),
                         "max": float(daily["temperature_2m_max"][i]), "min": float(daily["temperature_2m_min"][i])})
        except (KeyError, IndexError, TypeError, ValueError):
            continue
    return {"temp": float(cur.get("temperature_2m", math.nan)), "code": int(cur.get("weather_code", 3)),
            "wind": float(cur.get("wind_speed_10m", 0) or 0), "day": bool(cur.get("is_day", 1)), "days": days,
            "fetched": time.time()}


def fetch(lat: float, lon: float) -> dict:
    return parse_forecast(_get_json(API_URL, {
        "latitude": f"{lat:.4f}", "longitude": f"{lon:.4f}", "timezone": "auto", "forecast_days": 4,
        "current": "temperature_2m,weather_code,wind_speed_10m,is_day",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min"}))


class WeatherService(QObject):
    """Holt das Wetter im Hintergrund (alle 15 min, solange es jemand anzeigt)."""

    updated = Signal()

    def __init__(self, config, parent=None, fetcher=fetch):
        super().__init__(parent)
        self.config = config
        self.fetcher = fetcher
        self.data: dict | None = None
        self.error = ""
        self._busy = False
        self._for: tuple | None = None

    def place(self) -> dict:
        return self.config["weather"]

    def refresh(self, force: bool = False) -> None:
        place = self.place()
        if "lat" not in place:
            return
        key = (place["lat"], place["lon"])
        fresh = self.data is not None and self._for == key and time.time() - self.data["fetched"] < REFRESH
        if self._busy or (fresh and not force):
            return
        self._busy = True

        def work():
            try:
                self.data, self.error, self._for = self.fetcher(*key), "", key
            except Exception as exc:  # noqa: BLE001 - kein Internet o. Ä.
                self.error = f"Wetter nicht erreichbar ({type(exc).__name__})"
            finally:
                self._busy = False
                self.updated.emit()

        threading.Thread(target=work, name="wetter", daemon=True).start()


_service: WeatherService | None = None


def service(config=None) -> WeatherService:
    global _service
    if _service is None:
        from PySide6.QtWidgets import QApplication

        _service = WeatherService(config, QApplication.instance())
    elif config is not None:
        _service.config = config
    return _service


# --------------------------------------------------------------------------- Symbole
def draw_icon(p: QPainter, rect: QRectF, kind: str, day: bool = True) -> None:
    s = min(rect.width(), rect.height())
    cx, cy = rect.center().x(), rect.center().y()
    p.save()
    p.setPen(Qt.NoPen)

    def sun(x, y, r):
        p.setBrush(QColor("#fbbf24" if day else "#e2e8f0"))
        if day:
            pen = QPen(QColor("#fbbf24"), r * 0.18, Qt.SolidLine, Qt.RoundCap)
            p.setPen(pen)
            for i in range(8):
                a = math.radians(i * 45)
                p.drawLine(QPointF(x + math.cos(a) * r * 1.35, y + math.sin(a) * r * 1.35),
                           QPointF(x + math.cos(a) * r * 1.7, y + math.sin(a) * r * 1.7))
            p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(x, y), r, r)
        else:  # Mond
            path = QPainterPath()
            path.addEllipse(QPointF(x, y), r, r)
            cut = QPainterPath()
            cut.addEllipse(QPointF(x + r * 0.55, y - r * 0.35), r * 0.9, r * 0.9)
            p.drawPath(path.subtracted(cut))

    def cloud(x, y, w, color="#e2e8f0"):
        p.setBrush(QColor(color))
        path = QPainterPath()
        path.addEllipse(QPointF(x - w * 0.22, y + w * 0.05), w * 0.24, w * 0.24)
        path.addEllipse(QPointF(x + w * 0.05, y - w * 0.1), w * 0.32, w * 0.32)
        path.addEllipse(QPointF(x + w * 0.3, y + w * 0.08), w * 0.2, w * 0.2)
        path.addRoundedRect(QRectF(x - w * 0.46, y + w * 0.02, w * 0.96, w * 0.28), w * 0.14, w * 0.14)
        path.setFillRule(Qt.WindingFill)  # überlappende Kreise ohne Löcher
        p.drawPath(path)

    if kind == "sonne":
        sun(cx, cy, s * 0.22)
    elif kind == "wolke_sonne":
        sun(cx - s * 0.14, cy - s * 0.12, s * 0.17)
        cloud(cx + s * 0.05, cy + s * 0.05, s * 0.62)
    elif kind in ("wolke", "nebel"):
        cloud(cx, cy - s * 0.05, s * 0.7, "#cbd5e1")
        if kind == "nebel":
            p.setPen(QPen(QColor("#94a3b8"), s * 0.045, Qt.SolidLine, Qt.RoundCap))
            for i in range(2):
                y = cy + s * (0.3 + i * 0.1)
                p.drawLine(QPointF(cx - s * 0.3, y), QPointF(cx + s * 0.3, y))
    elif kind in ("regen", "schnee", "gewitter"):
        cloud(cx, cy - s * 0.12, s * 0.7, "#94a3b8" if kind != "schnee" else "#e2e8f0")
        if kind == "regen":
            p.setPen(QPen(QColor("#38bdf8"), s * 0.045, Qt.SolidLine, Qt.RoundCap))
            for i in range(3):
                x = cx - s * 0.18 + i * s * 0.18
                p.drawLine(QPointF(x, cy + s * 0.25), QPointF(x - s * 0.05, cy + s * 0.38))
        elif kind == "schnee":
            p.setBrush(QColor("#f8fafc"))
            for i in range(3):
                p.drawEllipse(QPointF(cx - s * 0.18 + i * s * 0.18, cy + s * 0.32), s * 0.035, s * 0.035)
        else:
            bolt = QPainterPath(QPointF(cx + s * 0.02, cy + s * 0.18))
            for dx, dy in ((-0.1, 0.16), (0.0, 0.16), (-0.06, 0.34), (0.12, 0.12), (0.02, 0.12), (0.08, 0.18)):
                bolt.lineTo(QPointF(cx + s * dx, cy + s * dy))
            p.setBrush(QColor("#facc15"))
            p.drawPath(bolt)
    p.restore()


class WeatherSource(QWidget):
    """Monitor 2: große Uhr, dazu Wetter jetzt und die nächsten Tage."""

    def __init__(self, cfg, parent=None):
        super().__init__(parent)
        self.service = service()  # vom Controller mit den Einstellungen angelegt
        self.service.updated.connect(self.update)
        self._shown = ""
        self.timer = QTimer(self, interval=500)
        self.timer.timeout.connect(self._tick)
        self.timer.start()
        self.refresh_timer = QTimer(self, interval=60_000)
        self.refresh_timer.timeout.connect(self.service.refresh)
        self.refresh_timer.start()
        self.service.refresh()
        self.setAttribute(Qt.WA_OpaquePaintEvent)

    def stop(self):
        self.timer.stop()
        self.refresh_timer.stop()

    def _tick(self):
        now = time.strftime("%H:%M")
        if now != self._shown:
            self._shown = now
            self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        data = self.service.data
        day = data["day"] if data else True
        g = QLinearGradient(0, 0, 0, h)
        g.setColorAt(0, QColor("#0c4a6e" if day else "#0b1020"))
        g.setColorAt(1, QColor("#1e3a8a" if day else "#1e1b4b"))
        p.fillRect(self.rect(), g)
        wide = w > h * 1.2
        m = max(12, int(min(w, h) * 0.06))
        left = QRectF(m, m, (w - 3 * m) * 0.52, h - 2 * m) if wide else QRectF(m, m, w - 2 * m, h * 0.4)
        right = QRectF(left.right() + m, m, w - left.right() - 2 * m, h - 2 * m) if wide else \
            QRectF(m, left.bottom() + m * 0.5, w - 2 * m, h - left.bottom() - m * 1.5)
        # Uhr
        now = time.localtime()
        clock = time.strftime("%H:%M", now)
        big = fitted_font(p, "88:88", int(left.width()), int(left.height() * 0.42))
        big.setWeight(QFont.DemiBold)
        p.setFont(big)
        p.setPen(QColor("#ffffff"))
        p.drawText(QRectF(left.x(), left.y(), left.width(), left.height() * 0.7), Qt.AlignCenter, clock)
        small = fitted_font(p, format_date_de(now), int(left.width()), max(10, big.pixelSize() // 4))
        p.setFont(small)
        p.setPen(QColor("#e0f2fe"))
        p.drawText(QRectF(left.x(), left.y() + left.height() * 0.62, left.width(), left.height() * 0.2),
                   Qt.AlignHCenter | Qt.AlignTop, format_date_de(now))
        # Wetter-Karte
        card = right.adjusted(0, right.height() * 0.04, 0, -right.height() * 0.04)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 26))
        p.drawRoundedRect(card, m * 0.6, m * 0.6)
        inner = card.adjusted(m * 0.6, m * 0.5, -m * 0.6, -m * 0.5)
        place = self.service.place() if self.service.config is not None else {}
        if "lat" not in place:
            self._message(p, inner, "Wetter: Ort noch nicht eingestellt",
                          "Kachel „Wetter & Uhr“ → Pfeil → „Ort ändern …“")
        elif data is None:
            self._message(p, inner, "Wetter wird geladen …" if not self.service.error else self.service.error,
                          place.get("label", ""))
        else:
            self._paint_weather(p, inner, data, place)
        p.end()

    def _message(self, p, rect, title, sub):
        f = fitted_font(p, title, int(rect.width()), max(12, int(rect.height() * 0.08)))
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor("#ffffff"))
        p.drawText(QRectF(rect.x(), rect.y(), rect.width(), rect.height() * 0.55), Qt.AlignHCenter | Qt.AlignBottom
                   | Qt.TextWordWrap, title)
        p.setFont(fitted_font(p, sub, int(rect.width()), max(10, int(rect.height() * 0.05))))
        p.setPen(QColor("#bae6fd"))
        p.drawText(QRectF(rect.x(), rect.y() + rect.height() * 0.58, rect.width(), rect.height() * 0.3),
                   Qt.AlignHCenter | Qt.AlignTop | Qt.TextWordWrap, sub)

    def _paint_weather(self, p, r, data, place):
        text, kind = describe(data["code"])
        top_h = r.height() * 0.58
        icon = QRectF(r.x(), r.y(), top_h * 0.9, top_h * 0.9)
        draw_icon(p, icon, kind, data["day"])
        tx = icon.right() + r.width() * 0.03
        tw = r.right() - tx
        temp = f"{round(data['temp'])}°" if not math.isnan(data["temp"]) else "–"
        tf = fitted_font(p, "-88°", int(tw), int(top_h * 0.5))
        tf.setBold(True)
        p.setFont(tf)
        p.setPen(QColor("#ffffff"))
        p.drawText(QRectF(tx, r.y(), tw, top_h * 0.55), Qt.AlignLeft | Qt.AlignBottom, temp)
        df = fitted_font(p, text, int(tw), max(10, int(top_h * 0.13)))
        p.setFont(df)
        p.setPen(QColor("#e0f2fe"))
        p.drawText(QRectF(tx, r.y() + top_h * 0.56, tw, top_h * 0.2), Qt.AlignLeft | Qt.AlignTop, text)
        sub = f"{place.get('name', '')} · Wind {round(data['wind'])} km/h"
        sf = fitted_font(p, sub, int(tw), max(9, int(top_h * 0.09)))
        p.setFont(sf)
        p.setPen(QColor("#bae6fd"))
        p.drawText(QRectF(tx, r.y() + top_h * 0.76, tw, top_h * 0.18), Qt.AlignLeft | Qt.AlignTop, sub)
        # nächste Tage (heute überspringen)
        days = data["days"][1:4]
        if not days:
            return
        y0 = r.y() + top_h + r.height() * 0.04
        col_w = r.width() / len(days)
        box_h = r.bottom() - y0
        for i, d in enumerate(days):
            x = r.x() + i * col_w
            try:
                wd = WEEKDAYS[time.strptime(d["date"], "%Y-%m-%d").tm_wday]
            except ValueError:
                wd = ""
            p.setPen(QColor("#e0f2fe"))
            p.setFont(fitted_font(p, "Mo", int(col_w * 0.5), max(9, int(box_h * 0.17))))
            p.drawText(QRectF(x, y0, col_w, box_h * 0.24), Qt.AlignCenter, wd)
            draw_icon(p, QRectF(x + col_w * 0.3, y0 + box_h * 0.24, col_w * 0.4, box_h * 0.42), describe(d["code"])[1])
            p.setPen(QColor("#ffffff"))
            p.setFont(fitted_font(p, "-88° / -88°", int(col_w * 0.9), max(9, int(box_h * 0.15))))
            p.drawText(QRectF(x, y0 + box_h * 0.68, col_w, box_h * 0.28), Qt.AlignCenter,
                       f"{round(d['max'])}° / {round(d['min'])}°")
