# Tastenbox – Verdrahtungsplan (nur stecken, nichts löten)

Teile: Pro Micro (USB-C) **oder Arduino Nano** · Steckbrett 400 Kontakte · 9 MX-Schalter (Outemu) ·
10-Gang-Poti mit Zählwerk · 8 LEDs 5 mm (2 × rot, 2 × grün, 2 × blau, 2 × weiß) + 8 × 1 kΩ ·
Dupont-Kabel Buchse–Stecker und Stecker–Stecker.

Ausnahme: Die Stiftleisten am Pro Micro müssen einmal angelötet werden. Bis dahin hält die gedruckte
Klemme (`klemme_pro_micro.py`) die Platine auf die Stifte gedrückt.

## 0. Welcher Pin wofür (das Programm erkennt das Board selbst)

| | Pro Micro | Nano |
|---|---|---|
| Tasten 1–9 | 2, 3, 4, 5, 6, 7, 8, 14, 15 | 2, 3, 4, 5, 6, 7, 8, 9, 10 |
| Drehregler (Mitte) | A0 | A0 |
| LEDs rot (2 Stück, je 1 kΩ) | 9 | 11 |
| LEDs grün (2 Stück, je 1 kΩ) | 10 | 12 |
| LEDs blau (2 Stück, je 1 kΩ) | 16 | 13 |
| LEDs weiß (2 Stück, je 1 kΩ) | A1 | A1 |
| Plus / Minus | VCC / GND | 5V / GND |

Hochladen: Arduino-IDE → Board „Arduino Leonardo“ (Pro Micro) bzw. „Arduino Nano“ → Programm aus AluPC
(Seite Tastenbox → „Arduino-Programm speichern …“).

## 1. Pro Micro – welcher Pin ist wo

USB-C zeigt nach oben, Bauteile zu dir:

```
              USB-C
          ┌───┴───┴───┐
   TX  1 ─┤           ├─ RAW
   RX  0 ─┤           ├─ GND  ◄── Minus-Leiste
   GND  ──┤           ├─ RST
   GND  ──┤           ├─ VCC  ◄── Plus-Leiste
  Taste1 2 ─┤         ├─ A3
  Taste2 3 ─┤         ├─ A2
  Taste3 4 ─┤         ├─ A1   ◄── LEDs weiß
  Taste4 5 ─┤         ├─ A0   ◄── Regler (Mitte)
  Taste5 6 ─┤         ├─ 15   ◄── Taste 9
  Taste6 7 ─┤         ├─ 14   ◄── Taste 8
  Taste7 8 ─┤         ├─ 16   ◄── LEDs blau
 LEDs rot 9 ─┤        ├─ 10   ◄── LEDs grün
          └───────────┘
```

## 2. Aufs Steckbrett

1. Pro Micro **quer über den Mittelsteg** stecken, ganz ans hintere Ende, USB-C zeigt nach hinten
   (zum Kabelfenster im Gehäuse). Jeder Pin hat dann in seiner Reihe 4 freie Löcher.
2. **GND** (rechts, 2. von oben) → Kabel zur **blauen Leiste (−)**.
3. **VCC** (rechts, 4. von oben) → Kabel zur **roten Leiste (+)**.
4. Die zweite Seite des Steckbretts (andere Längsseite) mit je einem Kabel verbinden:
   blau↔blau, rot↔rot. Dann hast du auf beiden Seiten Plus und Minus.

## 3. Tasten (9 Stück, 3 × 3)

Jeder Schalter hat 2 Beinchen. Auf jedes Beinchen eine **Dupont-Buchse** stecken.

**Beinchen zu dünn, Dupont-Buchse wackelt?** Ohne Löten, in dieser Reihenfolge:
1. **Wickeln (Wire-Wrap):** Litze/Draht 0,14–0,25 mm² 15 mm abisolieren, 4–5 Windungen fest um das Beinchen,
   Schrumpfschlauch oder Isoband drüber. Hält dauerhaft, das andere Ende hat einen Dupont-Stecker fürs Steckbrett.
2. **Minus als ein Draht:** alle 9 „B“-Beinchen nacheinander mit EINEM blanken Draht umwickeln (Masse-Schiene) →
   nur 10 statt 18 Verbindungen, ein Ende in die blaue Leiste.
3. **Buchse enger machen:** Dupont-Buchse mit einer Spitzzange leicht zusammendrücken – klemmt dann auf dem flachen
   Beinchen (schnell, kann sich mit der Zeit lockern).
4. Notlösung zum Testen: Mini-Abgreifklemmen (Prüfklemmen) – passen, sind aber groß.

| Taste (Lage auf der Box) | Beinchen A → Pin | Beinchen B → |
|---|---|---|
| 1 (oben links)   | 2  | blaue Leiste (−) |
| 2 (oben Mitte)   | 3  | blaue Leiste (−) |
| 3 (oben rechts)  | 4  | blaue Leiste (−) |
| 4 (Mitte links)  | 5  | blaue Leiste (−) |
| 5 (Mitte)        | 6  | blaue Leiste (−) |
| 6 (Mitte rechts) | 7  | blaue Leiste (−) |
| 7 (unten links)  | 8  | blaue Leiste (−) |
| 8 (unten Mitte)  | 14 | blaue Leiste (−) |
| 9 (unten rechts) | 15 | blaue Leiste (−) |

Egal, welches Beinchen A oder B ist. Wackelt eine Buchse: ein Tropfen Heißkleber.

**Tastenkappen (3D-Druck):** `tastenkappe.py` → `tastenkappe_1.stl` … `_9.stl` (Ziffer vertieft) und
`tastenkappe_eng/passend/mittel/locker.stl` (leer). Passt auf Outemu/MX (Kreuz „+“). Standard: „passend“ (zwischen eng und mittel). Zum Nachjustieren: „mittel“
und probieren: wackelt → „eng“, geht nicht drauf → „locker“. Druck: Oberseite nach unten, ohne Stützen,
0,12–0,16 mm Schicht. Vorschau: `tastenkappe_preview.png`.

## 4. Drehregler (3 Beinchen)

| Beinchen | → |
|---|---|
| links  | blaue Leiste (−) |
| Mitte  | A0 |
| rechts | rote Leiste (+) |

Dreht er falsch herum: links und rechts tauschen – oder in AluPC „Richtung umkehren“.

**Dein 10-Gang-Poti (DDR, 490.02xx) mit den 3 Drähten:** Vermutung – bitte mit dem Messgerät (Ω) prüfen:
rot und grau (seitliche Fahnen) = die Enden, **gelb (hinten, Mitte der Achse) = Schleifer → A0**.
Prüfen: rot↔grau = immer gleich (z. B. 10 kΩ); gelb↔rot ändert sich beim Drehen. Dann rot → rote Leiste (+),
grau → blaue Leiste (−), gelb → A0. Jeder Wert von 1 kΩ bis 100 kΩ geht; 10 kΩ ist ideal.

**Einbau (tastenbox_gehaeuse.py, Entwurf 4):** Poti steht senkrecht, Gewindehals von unten durch das Loch im
Deckel, oben Zahnscheibe + Mutter, darauf `drehknopf.stl` (M3-Madenschraube seitlich). Das **Zählwerk** hängt an
4 Säulen unter dem Deckel: M3-Schrauben von unten durch seine Langlöcher in die Säulen; die Ziffernzeile liegt
unter dem Fenster. Schnitt: `tastenbox_schnitt.png`. Die Maße von Poti und Zählwerk sind aus Fotos geschätzt –
Werte mit „NACHMESSEN“ im Skript prüfen (v. a. Gewindehals-Ø, Höhe des Zählwerks, Lage der Langlöcher).
Zählwerk und Poti sind **nicht** miteinander verbunden (Zahnräder fehlen) – siehe offene Frage im Chat.

**Zahl 0–999 (für Wenn → Dann):** Ab Programm 5 meldet die Box den Regler zusätzlich fein als `WERT 0–999`.
Gut dafür: ein 10-Gang-Poti (10 kΩ) mit Zählwerk-Drehknopf – gleich angeschlossen wie oben.
In AluPC „Regelt:“ auf „Zahl 0–999“ stellen. Zählwerk und Messwert weichen um ein paar Schritte ab
(Poti-Toleranz, 10-Bit-Messung = 1024 Stufen) – deshalb hat jede Regel „± Toleranz“ (Standard 3).
Mit „Jetzt“ im Regel-Fenster die echte Zahl übernehmen.

**Lautstärke übers Zählwerk:** „Vorlage:“ bzw. „Skala:“ am Regler – „Zählwerk 000–999 ÷ 10“ (Zählwerk 455 = 46 %)
oder „Zählwerk 000–100 = Prozent“ (Zählwerk 073 = 73 %, ab 100 voll).

## 5. Licht – Plan

![LED-Plan](led_plan.png)

**Konzept „Kreuz“:** 8 einfarbige 5-mm-LEDs, **2 pro Ecke**, 4 Farben. Jede Farbe sitzt in zwei
**diagonal gegenüberliegenden** Ecken – so leuchtet jeder Zustand symmetrisch über Kreuz:

| Ecke | außen | innen |
|---|---|---|
| vorne links | rot | weiß |
| hinten rechts | rot | weiß |
| hinten links | blau | grün |
| vorne rechts | blau | grün |

![LED-Farbplan](led_farben.png)

So leuchtet die Box (Farbe und Schema stellst du in AluPC ein: Tastenbox → Box, auch am Handy):

| Zustand | was leuchtet | in AluPC |
|---|---|---|
| Bereit | grün + weiß (alle 4 Ecken) | Grundfarbe z. B. `#80ff80` |
| Live (läuft auf Bildschirm 2) | rot (2 Ecken über Kreuz) | Farbschema „Zustand“ |
| Schwarz / Standbild | rot + grün | Farbschema „Zustand“ |
| Code-Eingabe (Wenn → Dann) | blinkt | automatisch |
| Farbwechsel | rot → grün → blau → weiß wandert über Kreuz | Effekt „Farbwechsel / Regenbogen“ |
| Arbeitslicht | alle 8 | Farbe weiß `#ffffff` |

Wie das geht: AluPC schickt eine Farbe (rot, grün, blau). Die Box schaltet damit die roten, grünen und blauen
LEDs; was alle drei gemeinsam haben, übernehmen die weißen. Reines Weiß = alle 8 an. Helligkeit, Atmen,
Blinken und der Blitz bei Tastendruck gehen wie bisher. (Arduino-Programm 6, `#define VIER_FARBEN` – ist an.)

**LEDs einbauen (ca. 20 Min.):**
1. LED von innen in ihren Halter drücken, bis der Rand anliegt – die Kuppe ist dann bündig mit der Oberseite.
   Farbe nach der Tabelle oben (außen = an der Ecke, innen = 10 mm daneben).
2. Beine zeigen in die Kerbe (Richtung Box-Mitte).
3. **Langes Bein (+):** 1-kΩ-Widerstand anschließen, sein anderes Ende an ein Kabel zum Farb-Pin
   (rot → D11, grün → D12, blau → D13, weiß → A1). Die zwei LEDs einer Farbe gehen an denselben Pin –
   jede mit **eigenem** Widerstand.
4. **Kurzes Bein (−):** an die blaue Minus-Leiste.
5. Kabel über den nächsten Kabelhaken an der Wand entlang zum Steckbrett.

Strom: jede LED ~3 mA, alle 8 zusammen ~25 mA – passt locker an USB. Kleiner als 1 kΩ nicht nötig.
Pin D13 hat auf dem Nano eine eigene kleine LED – die leuchtet mit Blau mit, das ist normal.

Tipp: Wer das Oberteil in hellem Filament druckt, kann in `tastenbox_gehaeuse.py` `led_skin = 0.6` setzen –
dann sind die Löcher oben zu und das Licht scheint weich durch (unsichtbar, solange aus).

Nicht getestet: Programm 6 lief nur in der PC-Simulation (Farben → Pins, Farbwechsel, Helligkeit stimmen dort).

### Andere LEDs (alte Varianten)

- **Alle LEDs an einem Pin** (nur an/aus/Helligkeit): im Programm `#define VIER_FARBEN` ausschalten (`//` davor),
  alle Widerstände an D11 (Pro Micro D9).
- **RGB-LEDs/Streifen (WS2812B, PL9823):** `VIER_FARBEN` aus, `#define STREIFEN n` an, DIN an D12 (Pro Micro D10).

## 6. Fehlersuche in AluPC

Seite **Geräte → Tastenbox → Fehlersuche → Anzeigen**:
- oben: Anschluss, Programmversion, Board (Nano/Pro Micro)
- **Rohwerte live**: Taste unten → leuchtet in der App, solange sie gedrückt ist; Regler als Zahl 0–1023
- **Protokoll**: jede Zeile zwischen AluPC und Box (→ gesendet, ← empfangen), auch „keine Antwort“ bei der Suche
- **LED testen** (blitzt 3×), **Neu verbinden**, **Protokoll kopieren** (zum Schicken)

## 7. Testen ohne Bauteile: Online-Simulation (Wokwi)

1. https://wokwi.com öffnen → „Arduino Mega“ neues Projekt.
   (Einen Pro Micro gibt es dort nicht. Auf Mega/Nano nimmt das Programm die Nano-Belegung: Tasten 2–10, LEDs 11.)
2. Inhalt von `wokwi/sketch.ino` in `sketch.ino` kopieren.
3. Inhalt von `wokwi/diagram.json` in `diagram.json` kopieren (Reiter oben).
4. ▶ starten. Taste anklicken → unten im Serial Monitor erscheint `TASTE 1`, gedrückt halten → `LANG 1`,
   Regler drehen → `LAUT 57`.
