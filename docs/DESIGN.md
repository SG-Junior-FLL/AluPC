# AluPC – Gestaltung (ab 2.0)

Drei Designs, umschaltbar unter **Setup → Darstellung → Stil**. Alle drei teilen Aufbau und Funktionen; sie
unterscheiden sich in Flächen, Rundungen, Schrift und Kachelform. Code: `alupc/ui/theme.py` (Farben, Stylesheet,
Holz), `alupc/ui/widgets.py` (gezeichnete Teile), `alupc/cast_page.py` (Handy-/iPad-Seite).

## Gemeinsame Regeln

- **Rot heißt nur eins:** läuft gerade auf dem Bildschirm (Kachelrand, Lampe, Vorschau-Rahmen, Etikett „Live“).
- **Nur echte Angaben:** Zustände in Worten („Läuft“, „An“, „Aktiv“) oder als echte Werte (Auflösung, Hz,
  Lautstärke, Laufzeit). Keine Fachkürzel wie „CH 07“, „PGM“, „STBY“, kein erfundener Timecode.
- **Lesbarkeit geprüft** (`tests/test_theme.py`): Schrift/Grund ≥ 7:1, leise Schrift/Karte ≥ 4,5:1,
  Schrift auf Akzentfarbe ≥ 4,5:1 – für jeden Stil, hell und dunkel, und jede Holzart.
- Keine Verläufe als Schmuck, keine Bewegung ohne Anlass; Satzschreibweise statt GROSSBUCHSTABEN.

## Normal (Standard) – modern, weich, rund

| Rolle | Dunkel | Hell |
|---|---|---|
| Grund | `#131417` | `#ECEEF2` |
| Fläche (Karten, Seitenleiste) | `#1E2024` | `#FFFFFF` |
| Feld (Knöpfe, Eingaben) | `#2A2D33` | `#F1F2F5` |
| Schrift / leise | `#F2F3F5` / `#9AA0AA` | `#16181C` / `#5F6670` |
| Akzent (AluPC) | `#5B8CFF` | `#2F62E9` |

- Rundungen: Karten 20, Knöpfe 17 (Pillen), Felder 12. Flächen ohne Rand – Ebenen unterscheiden sich nur in der Helligkeit.
- Seitenleiste schwebt als runde Fläche. Kacheln: Symbol im getönten Kreis oben links, Menü als kleiner runder
  Knopf oben rechts, Name unten. Lautstärke als dicke runde Säule.
- Schrift: Inter.

## Technisch – dicht, mit Messwerten

- Mittelgrau (`#18191B` / `#E6E6E2`), Akzent Signalgelb (`#F5C400` / `#C99A00`) mit dunkler Schrift darauf.
- Rundungen 2–3 px, feine Ränder. Kacheln als Zeilen (Symbol, Name, Untertitel), läuft = rote Leiste links.
- Ziffernschrift (JetBrains Mono) nur für echte Werte: Ausgang/Auflösung/Hz, „läuft seit 0:12:34“, Regler 0–100.

## Holz – echtes Furnier

- **7 Holzarten** (`WOODS`): Nussbaum, Kirsche, Wenge, Räuchereiche (dunkel → helle Schrift), Eiche, Kiefer,
  Ahorn (hell → dunkle Schrift). Die Holzart bestimmt hell/dunkel; die Auswahl Hell/Dunkel ist dann gesperrt.
- Maserung wird beim Start gerechnet (fester Zufallswert, nahtlos kachelbar): Jahresringe als Bänder, Fasern als
  Wellen, je Holzart eigene Zeichnung (Poren bei Eiche, enge Streifen bei Wenge, Flamme bei Kirsche …).
  Jede Fläche (Grund, Seitenleiste, Platte, Platte hell/gedrückt) wird auf eine feste Helligkeit gebracht –
  so bleibt die Schrift auf jedem Holz lesbar.
- Kacheln sind Furnierplatten mit Lichtkante und Schatten, Namen graviert (Barlow Semi Condensed), oben links
  eine Kontrolllampe (aus = dunkles Glas, läuft = leuchtet rot). Akzent Messing.
- Reglerkappen aus gebürstetem Aluminium, Vorschau in dunklem Gehäuse wie ein kleiner Fernseher.

## Handy-/iPad-Seite

Der PC liefert die Seite mit seinen Farben, Rundungen, Schriften und (Holz) den Holzflächen aus
(`themed_page`, `/fonts/…`, `/holz/<art>/<fläche>.jpg`). Bei „Wie das System“ entscheidet das Handy hell/dunkel.

## Verworfen

„Regiepult“ (1.1), „Kontrollzentrum“ (zu bunt) und „Signal“ (zu viel Fachjargon: CH/PGM/STBY, Timecode).
