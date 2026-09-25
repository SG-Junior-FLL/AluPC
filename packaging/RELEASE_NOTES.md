## AluPC – Monitor 2 steuern (Kubuntu & Windows 11)

### Downloads
| System | Datei | Hinweis |
|---|---|---|
| **Windows 11** | `AluPC-Setup-….exe` | Installer (Startmenü, Deinstallation) |
| Windows 11 | `AluPC-windows-portable-….zip` | ohne Installation: entpacken, `AluPC.exe` starten |
| **Kubuntu / Ubuntu** (22.04, 24.04 und neuer) | `alupc_…_amd64.deb` | `sudo apt install ./alupc_…_amd64.deb` – danach im Startmenü |
| Linux (x86_64) | `AluPC-linux-x86_64-….tar.gz` | ohne Installation: entpacken, `AluPC/AluPC` starten |

### Neu in dieser Version (0.12.0)
- **AluCast – eigener Handy-Empfang ohne App** (Kachel „Handy“ – Klick): QR-Code auf Monitor 2
  scannen, dann vom iPhone oder Android **Fotos (auch direkt fotografieren), Videos, Links (YouTube im
  Vollbild) und Text** senden und Monitor 2 **fernsteuern** (Szenen, Schwarz, Standbild, Video,
  Lautstärke). Geschützt mit 6-stelligem Code, Sperre nach Fehlversuchen.
- **Miracast (Windows)**: AluPC startet Windows' eigenen Empfänger „Drahtlose Anzeige“ (installiert ihn
  bei Bedarf nach) und legt ihn im Vollbild auf Monitor 2 – z. B. für Samsung „Smart View“ oder
  Laptops mit Windows+K.
- **Kamera-Optionen**: Kamera-Leiste mit Zoom 1–5×, Ausschnitt verschieben, Spiegeln, Drehen,
  Helligkeit; pro Kamera gespeichert; schärferes Kamerabild (bis Full HD). Tastenkürzel/Befehle
  `kamera_zoom_plus`, `kamera_zoom_minus`, `kamera_zoom_aus`.
- Einrichten-Dialog „Handy“ jetzt mit Reitern: Browser (QR-Code), iPhone (AirPlay), Android, Miracast.
- **Ehrlich:** Einen eigenen AirPlay/Chromecast-Empfänger kann AluPC nicht nachbauen (Apple-FairPlay-
  Verschlüsselung bzw. Google-Zertifikate). AluCast überträgt deshalb **nicht den Handy-Bildschirm**,
  sondern Fotos, Videos, Links und Text. Miracast nur unter Windows. Nicht mit echten Handys getestet –
  getestet sind die Handy-Webseite in einem Handy-Browser-Simulator (iPhone- und Pixel-Größe) und der
  Webserver mit echten Anfragen.

### Neu in dieser Version (0.11.0)
- **Handy → Monitor 2** (neue Kachel „Handy“, auch im Taskleisten-Menü):
  - **iPhone/iPad per AirPlay** über das freie UxPlay: am iPhone Kontrollzentrum →
    Bildschirmsynchronisierung → „AluPC“. Mit UxPlay ab 1.73 erscheint das Bild direkt als AluPC-Quelle
    (auch in eigenen Szenen, mit Standbild und Zeichnen); ältere Versionen im eigenen Vollbild-Fenster
    auf Monitor 2. Name und Code (keiner / fest / neu pro Gerät) einstellbar.
  - **Android per scrcpy** (USB-Debugging) im Vollbild auf Monitor 2; Windows zusätzlich Knopf für
    „Projizieren auf diesen PC“ (Miracast).
  - „Einrichten …“ findet die Programme, installiert sie unter Kubuntu per Klick (Passwort) und zeigt
    Schritt-für-Schritt-Anleitungen.
- **Ehrlich:** Chromecast-Empfang ist auf einem PC nicht möglich (nur zertifizierte Geräte). UxPlay und
  scrcpy werden nicht mitgeliefert (unter Windows selbst installieren). Kubuntu 24.04 hat UxPlay 1.68
  (nur Fenster-Modus; vor 1.72.3 laut UxPlay-Projekt mit Sicherheitslücke CVE-2025-60458 – dann nur im
  vertrauenswürdigen WLAN und mit Code nutzen). Nicht mit echten Handys getestet, nur mit einem
  simulierten AirPlay-Videostrom.

### Neu in dieser Version (0.10.0)
- **Mediathek** (Kachel „Bild / Video“): gespeicherte Bilder, Videos und Diashows mit Vorschaubildern,
  „Zuletzt gezeigt“ automatisch, Filter, Suche, Umbenennen; Pfeil an der Kachel startet Gespeichertes direkt.
- **Mediensteuerung**: Läuft ein Video – auch in einer eigenen Szene –, erscheint oben im Hauptfenster
  Pause/Weiter, ±10 s und eine Zeitleiste zum Springen (bei mehreren Videos wählbar).
- **Neue Bildschirmschoner**: Matrix, Code-Editor (Code tippt sich selbst), Terminal (Build-/Test-Log),
  Netzwerk, Sternenflug.
- **Zeigen & Zeichnen**: Der Laserpointer ist jetzt nur noch dort (keine eigene Kachel mehr, Farbe =
  Zeichenfarbe). **Zeichnungen bleiben gespeichert** – auch nach Schließen und Neustart – bis man sie
  löscht oder die Szene wechselt.
- **Fingerabdruck**: Finger per Klick auf eine Handgrafik wählen; angelernte Finger leuchten grün.
- **Maus zu 100 % auf Monitor 1** (außer Erweitern): Windows zusätzlich mit systemweiter Maus-Sperre;
  X11 schneller nachkorrigiert; die Sperre hängt nur noch vom Modus ab. (Wayland: nicht möglich.)
- **Windows 11**: AluPC-Symbol direkt in der Taskleiste statt hinter dem Pfeil (einmalig; lässt sich in
  Windows wieder ändern).
- Statuskarte zeigt bei Medien nur den Namen statt des ganzen Pfads.

### Neu in dieser Version (0.9.1)
- **Fingerabdruckmodul: Anmeldung auch bei mehreren Benutzerkonten** – nach einer deutlichen Warnung
  und ausdrücklicher Bestätigung. Jeder Benutzer verwaltet nur seine eigenen Finger: fremde Finger
  werden weder überschrieben noch gelöscht, und die Zuordnung Finger → Benutzer wird zusammengeführt
  statt ersetzt (vorher hätte jeder Benutzer die Einträge der anderen gelöscht).

### Neu in dieser Version (0.9.0)
- **Fingerabdruckmodul am USB-Seriell-Adapter** (z. B. **Hi-Link HLK-ZW101 / ZW0922**, AS608, R307):
  AluPC findet das Modul selbst (Anschluss und Baudrate), lernt Finger an, zeigt und löscht sie, macht
  Test-Scans – unter **Windows und Linux**.
- **Linux-Anmeldung** mit dem Modul (Anmeldebildschirm, Sperrbildschirm, sudo) über PAM – nur mit
  dem .deb und nur auf PCs mit einem Benutzerkonto (das Modul hat keinen Zugriffsschutz); das Passwort
  geht immer weiter. Das .deb bringt eine udev-Regel mit, damit der Adapter
  benutzt werden darf; blockiert brltty den CH340-Adapter, bietet der Assistent an, es zu entfernen.
- **Windows:** Anmelden mit so einem Modul ist nicht möglich (Windows lässt nur Windows-Hello-Sensoren
  zu) – anlernen und prüfen in AluPC geht.
- Getestet gegen ein nachgebautes Modul mit gleichem Protokoll, nicht gegen echte Hardware.

### Neu in dieser Version (0.8.2)
- Behoben: Mit „Harter Schnitt“ im Setup wurde ein eigener Übergang einer Szene ignoriert.
- Behoben (KDE/Wayland): Hing KWin beim Aufnehmen, konnte AluPC beim Szenenwechsel abstürzen;
  Bilddaten werden jetzt höchstens 5 s abgewartet.
- Behoben (KDE/Wayland): Ließ sich das Maus-Skript für den Laserpointer nicht laden, blieben bei jedem
  Einschalten Verbindung und Hintergrund-Thread übrig.
- Fingerabdruck: günstige USB-Leser von Chipsailing (z. B. CS9711, USB 2541:0236) und Microarray werden
  erkannt und ehrlich benannt (Linux-Standardtreiber unterstützt sie nicht); Windows: Hinweis, wo es den
  Treiber gibt, wenn kein Sensor gefunden wird.

### Neu in dieser Version (0.8.1)
- **Flüssigere Vorschau**: „Zeigen & Zeichnen“ zeigt Monitor 2 jetzt mit 30 Bilder/s (wählbar 10–60,
  daneben steht, wie viele wirklich erreicht werden). Bild-in-Bild: bis 60 Bilder/s (Setup), Standard 20.
  Die Vorschau wird direkt in kleiner Größe gezeichnet statt in voller Auflösung – spart Rechenzeit.
  Spiegeln unter KDE/Wayland (KWin): bis 30 statt 20 Bilder/s.
- **Schneller**: Setup und Fingerabdruck-Seite werden erst beim ersten Öffnen gebaut (Start ca. 40 %
  schneller); Uhr und Countdown zeichnen nur neu, wenn sich die Anzeige ändert (weniger Last,
  Sekunde springt pünktlicher um).
- **Design „Zeigen & Zeichnen“**: Werkzeugleiste in Gruppen, Vorschau mit runden Ecken und Etikett
  LIVE/STANDBILD/SCHWARZ, passt sich schmalen Fenstern an (dann nur Symbole).
- Behoben: Die Uhr-Quelle hielt ihren Takt nach dem Beenden nicht an.

### Neu in dieser Version (0.8.0)
- **Zeigen & Zeichnen**: eigenes Fenster auf Monitor 1 mit Live-Bild von Monitor 2. Darin zeigt man mit
  dem Laserpointer oder kritzelt mit Stift und Textmarker (8 Farben + eigene, Stärke einstellbar),
  Radierer, Rückgängig (Strg+Z), Alles löschen – alles erscheint sofort auf Monitor 2, auch über einem
  Standbild. Öffnen: Kachel „Zeigen & Zeichnen“, Pfeil an der Laserpointer-Kachel, Taskleisten-Menü,
  `Strg+Alt+K`. Zeichnungen verschwinden beim Inhaltswechsel/Schließen (abschaltbar). Funktioniert
  auch unter Wayland ohne KDE (die Maus bleibt ja im eigenen Fenster).
- **Linux**: Das .deb empfiehlt jetzt auch `pkexec` (für die automatische Einrichtung). Der Build prüft,
  dass bei der Installation des .deb fprintd und libpam-fprintd automatisch mitinstalliert werden.

### Neu in dieser Version (0.7.0)
- **Mauszeiger beim Spiegeln sichtbar**: Die Aufnahme unter Windows/X11 enthält den Zeiger nicht –
  AluPC zeichnet ihn jetzt selbst ein (mit seiner echten Form, z. B. Hand oder Textcursor).
- **Maus bleibt auf Monitor 1**, außer bei „Erweitern“ (abschaltbar: Setup → Monitor 2). Geht unter
  Windows und X11; unter Wayland erlaubt das System es nicht.
- **Laserpointer** (Kachel, Taskleisten-Menü, `Strg+Alt+Z`): roter Leuchtpunkt mit Spur auf Monitor 2,
  gesteuert mit der Maus auf Monitor 1. Farbe, Größe und Spur im Setup. Unter Wayland nur mit KDE.
- Neue Standard-Kacheln erscheinen nach einem Update jetzt auch, wenn die Startseite schon angepasst war.
- Korrigiert: Hinweis im Setup behauptete, Monitor 2 zeige beim Sperren weiter etwas – stimmt nicht.

### Bekannte Grenzen
Die automatischen Tests laufen ohne echte Monitore, Kameras und Fingerabdrucksensoren. Bitte Fehler
mit Screenshot melden. Details im README unter „Ehrliche Grenzen“.
