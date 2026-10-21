## AluPC – Bildschirm steuern (Kubuntu & Windows 11)

### Downloads
| System | Datei | Hinweis |
|---|---|---|
| **Windows 11** | `AluPC-Setup-….exe` | Installer (Startmenü, Deinstallation) |
| Windows 11 | `AluPC-windows-portable-….zip` | ohne Installation: entpacken, `AluPC.exe` starten |
| **Kubuntu / Ubuntu** (22.04, 24.04 und neuer) | `alupc_…_amd64.deb` | `sudo apt install ./alupc_…_amd64.deb` – danach im Startmenü |
| Linux (x86_64) | `AluPC-linux-x86_64-….tar.gz` | ohne Installation: entpacken, `AluPC/AluPC` starten |
| Kubuntu / Ubuntu | `AluPC-installieren.sh` | installiert die .deb daneben (oder lädt sie), wartet auf laufende Updates |

### Neu in 2.2.0 – neuer Aufbau, Design-Profile, mehr Schalter, einheitliche Publikumsansicht
- **Tastenbox** (Arduino Pro Micro, 9 Tasten + Drehregler + LED): eigene Seite „Tastenbox“. AluPC findet die Box
  von selbst. Die Tasten erscheinen 3 × 3 wie auf der Box und leuchten beim Drücken; jede bekommt einen Befehl
  (auch Szenen, Studio-Übergang). Der Regler regelt wahlweise PC-Ton, Ton auf Bildschirm 2, Mikrofon oder ein
  Programm. Beim Wechsel startet das neue Ziel bei 0 und folgt erst, wenn der Regler auch auf 0 steht (Skala am
  Regler). Regelt er den PC-Ton, stellt AluPC andere Wege (Windows, Tastatur, Handy, Sprache) zurück.
  Arduino-Programm: Seite Tastenbox → „Arduino-Programm speichern“. Noch nicht mit echter Box getestet.
- **Seitenleiste aufgeräumt:** 6 statt 8 Punkte. „Geräte“ bündelt PC-Status, Tastenbox und Fingerabdruck als
  Reiter; „Zuhören“ und „Sperren“ stehen in einer Zeile.
- **Vorlagen ohne Überdeckung:** Uhr, Countdown und Laufschrift stehen in einer Info-Leiste unter der Seite statt als
  Kasten darüber. Im Szenen-Editor für jede gestaltete Seite einstellbar.
- **Tastenbox-Optionen:** lang drücken (eigener Befehl, Arduino-Programm Version 2), Regler umkehren, Höchstwert,
  Null-Abgleich an/aus, LED-Helligkeit, LED blitzt bei Tastendruck. Arduino-Programm nur am PC simuliert,
  nicht auf echter Hardware getestet.
- **Studio-Modus** (Knopf „Studio“ auf der Startseite, wie in OBS): Über dem Live-Bild klappt eine Vorschau auf.
  Kacheln und Szenen landen erst dort, „Übergang“ (oder Strg+Enter) schaltet live, „Schnitt“ ohne Überblenden.
  Live-Kachel rot, Vorschau-Kachel grün. Kamera, Bildschirm-Aufnahme und AirPlay zeigt die Vorschau nur als Schema.
- **Neues Design „Matrix“:** grüne Ziffernschrift auf Schwarz, Code-Regen im Hintergrund.
- **Bildschirm 2 neu gestaltet:** alle Vorlagen mit neuem Hintergrund und neuer Schrift; Ablauf, Pause, Hinweis,
  WLAN, Laufschrift, Listen und Pro & Contra neu aufgebaut.
- **Technisch wie ein DJ-Pult:** Kacheln als beleuchtete Pads, leuchtende Tasten, Pegel für den PC-Ton.
- **Alle Seiten überarbeitet:** Szenen mit Suche und Detail-Spalte, Setup mit Gruppen und Suche, neuer Szenen-Editor.
- **Design-Knopf** unten links: Stil, Hell/Dunkel, Profil (abschaltbar in Darstellung).
- **Lautstärkeregler nicht mehr auf der Startseite** – PC-Ton: System → PC steuern; Programme: Audio.
- **Neuer Aufbau der Startseite („Studio“):**
  - Breites Fenster (ab ca. 1240 px): rechts ein festes **Live-Dock** mit großem Live-Bild, allen Schnellschaltern
    mit Namen, Reglern und „Beenden“. Es bleibt stehen, während man die Kacheln scrollt.
  - Oben eine große **Befehlsleiste** („Suchen oder schreiben, was laufen soll …“, Strg+K).
  - Schmaleres Fenster: wie bisher eine Karte über den Kacheln.
  - Technisch: echte Messwerte im Dock (Prozessor, Speicher, Temperatur mit Verlauf), feines Punktraster im
    Hintergrund, gelbe Signalkante.
- **Design anpassen und speichern** (Setup → Darstellung):
  - Rundung (eckig bis sehr rund), Schriftgröße (85–130 %), Abstände (kompakt, normal, luftig)
  - eigene Akzentfarbe („Farbe wählen …“)
  - Profile: fertige Profile („Werkstatt“, „Wohnzimmer“, „Hell & rund“ …) oder eigene speichern, wechseln,
    löschen. „Aktuelle Einstellungen“ holt den Stand von vor dem Profil zurück.
- **Designs aufgefrischt:**
  - Normal: Leuchten in der Akzentfarbe, Kacheln heben sich beim Überfahren, laufende Kacheln leuchten rot.
  - Technisch: Signalkante an Karten.
  - Holz: Messing-Einlegeleiste.
- **Mehr Schnellschalter oben:** neu sind Schoner, Overlays, Stumm (PC-Ton) und Weiter (nächste Szene). Bei Platz
  mit Namen auf zwei Zeilen, sonst nur Symbole.
- **Publikum sieht immer dasselbe:**
  - Gilt für Abstimmung, Glücksrad, WLAN-Code, Uhr, Text, Timer, System, Musik, Spiele und AirPlay-Warten.
  - Einheitliche dunkle „Bühne“, unabhängig vom PC-Design.
  - Setup → Bildschirm → „Publikum sieht“: Bühne oder reines Schwarz.
- **Linux: Spiegeln ohne Bildschirm-Auswahl.** Würde die Aufnahme nach dem Bildschirm fragen (Wayland ohne
  KWin-Freigabe), spiegelt KDE direkt, ohne Nachfrage.
- **Nicht getestet** auf echten Geräten (Spiegeln unter KDE/Wayland, PC-Stummschalten, Temperatur, Ton-Pegel, Studio-Modus) – nur automatische Tests
  und Bildschirmfotos.

### Frühere Versionen
[CHANGELOG](https://github.com/SG-Junior-FLL/AluPC/blob/main/docs/CHANGELOG.md)

### Grenzen
Tests laufen ohne echte Monitore, Kameras und Sensoren. Fehler bitte mit Screenshot melden.
