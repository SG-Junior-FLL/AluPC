# Tastenbox – Verdrahtungsplan (nur stecken, nichts löten)

Teile: Pro Micro (USB-C) · Steckbrett 400 Kontakte · 9 MX-Schalter · Drehregler 10 kΩ linear ·
Dupont-Kabel Buchse–Stecker und Stecker–Stecker · optional LED + 220-Ω-Widerstand oder LED-Streifen WS2812B.

Ausnahme: Die Stiftleisten am Pro Micro müssen einmal angelötet werden. Bis dahin hält die gedruckte
Klemme (`klemme_pro_micro.py`) die Platine auf die Stifte gedrückt.

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
  Taste3 4 ─┤         ├─ A1
  Taste4 5 ─┤         ├─ A0   ◄── Regler (Mitte)
  Taste5 6 ─┤         ├─ 15   ◄── Taste 9
  Taste6 7 ─┤         ├─ 14   ◄── Taste 8
  Taste7 8 ─┤         ├─ 16      (frei – später Zündschloss)
     LED 9 ─┤         ├─ 10   ◄── LED-Streifen DIN (optional)
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

## 4. Drehregler (3 Beinchen)

| Beinchen | → |
|---|---|
| links  | blaue Leiste (−) |
| Mitte  | A0 |
| rechts | rote Leiste (+) |

Dreht er falsch herum: links und rechts tauschen – oder in AluPC „Richtung umkehren“.

## 5. Licht (optional, eins von beiden)

- **4 LEDs in den Ecken** (5 mm, Löcher sind im Gehäuse): jede LED bekommt einen **eigenen 1-kΩ-Widerstand**
  (aus deinem Set). Pin 9 → je 1 kΩ → langes LED-Bein; kurze Beine → blaue Leiste (−).
  Alle 4 hängen zusammen an Pin 9, AluPC schaltet sie (Live/An/Aus, Helligkeit, Blitz bei Tastendruck).
  Nicht kleiner als 1 kΩ: Pin 9 verträgt höchstens ca. 40 mA, 4 LEDs mit 1 kΩ brauchen zusammen ca. 12 mA.
  (Einen 3,3-V-Pin hat der Pro Micro 5 V nicht – VCC ist 5 V.)
- **Eine LED:** Pin 9 → 220-Ω-Widerstand → langes LED-Bein. Kurzes Bein → blaue Leiste (−).
- **LED-Streifen WS2812B** (bis ca. 8–10 LEDs): DIN → Pin 10, 5V → rote Leiste (+), GND → blaue Leiste (−).
  Im Arduino-Programm die Zeile `// #define STREIFEN 8` aktivieren (die `//` löschen).

## 6. Nicht am Pro Micro

- **Fingerabdrucksensor:** bleibt an seinem eigenen USB-Adapter → USB-Kabel hinten raus zum PC.
- **Zündschloss:** vorerst nur mechanisch. Wenn es mitmelden soll: ein Kontakt → Pin 16, anderer → Minus.
  (Arduino-Programm und AluPC brauchen dafür noch eine Erweiterung – sag Bescheid.)

## 7. Testen ohne Bauteile: Online-Simulation (Wokwi)

1. https://wokwi.com öffnen → „Arduino Mega“ neues Projekt.
   (Einen Pro Micro gibt es dort nicht. Der Mega hat dieselben Pin-Nummern, das Programm läuft unverändert.)
2. Inhalt von `wokwi/sketch.ino` in `sketch.ino` kopieren.
3. Inhalt von `wokwi/diagram.json` in `diagram.json` kopieren (Reiter oben).
4. ▶ starten. Taste anklicken → unten im Serial Monitor erscheint `TASTE 1`, gedrückt halten → `LANG 1`,
   Regler drehen → `LAUT 57`.
