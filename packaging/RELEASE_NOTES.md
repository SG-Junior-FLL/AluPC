## AluPC – Monitor 2 steuern (Kubuntu & Windows 11)

### Downloads
| System | Datei | Hinweis |
|---|---|---|
| **Windows 11** | `AluPC-Setup-….exe` | Installer (Startmenü, Deinstallation) |
| Windows 11 | `AluPC-windows-portable-….zip` | ohne Installation: entpacken, `AluPC.exe` starten |
| **Kubuntu / Ubuntu** (22.04, 24.04 und neuer) | `alupc_…_amd64.deb` | `sudo apt install ./alupc_…_amd64.deb` – danach im Startmenü |
| Linux (x86_64) | `AluPC-linux-x86_64-….tar.gz` | ohne Installation: entpacken, `AluPC/AluPC` starten |

### Neu in dieser Version (0.20.0) – viel mehr Vorlagen
- **28 gestaltete Seiten** (20 neu): Countdown bis Uhrzeit/Datum, Geburtstag mit Konfetti, Tabelle/Stundenplan,
  **Abstimmung/Quiz** (A–F, richtige Antwort hervorheben), Arbeitsauftrag mit Zeit, Regeln, **Gruppeneinteilung**,
  Stillarbeit (ruhige Animation), Danke/Ende, Hausaufgaben, Schlagzeile, Große Zahl, Termine, Türschild,
  Speiseplan, **Siegerehrung** mit Podest, **Stimmungsbarometer**, Pro & Contra, Begriff/Definition,
  Willkommen für Gäste.
- **23 Szenen-Vorlagen** (16 neu): Stillarbeit mit Timer, Gruppenarbeit, Arbeitsauftrag + Timer, Quiz mit Zeit,
  **Abstimmung per Handy** (Frage + QR-Code), Ende der Stunde (Danke + Hausaufgaben), Stundenplan + Uhr,
  Termine + Uhr, Geburtstag, Türschild, Speiseplan, Siegerehrung, Countdown zum Event, Nachrichten mit
  Laufschrift, Willkommen + Handy-QR, Begriff + Kamera.
- Vorlagen-Fenster mit **Kategorien** (Unterricht, Veranstaltung, Info, Pause & Zeit, Spaß), **Seiten/Szenen**
  und **Suche**. Listen und Tabellen: je Zeile ein Eintrag, Spalten mit „|“ trennen.

### Neu in dieser Version (0.19.0)
- **9 neue Bildschirmschoner:** Polarlicht, Lavalampe, Lichtkugeln, Meer bei Sonnenuntergang, Feuerwerk,
  Analoguhr, Klappuhr, Schneefall (mit eigenem Text) und **Sprüche/Zitate im Wechsel** (eigene mit | trennen).
- **Neue Seiten für Monitor 2** („Gestaltete Seite“) – jeweils mit eigenem Text: **Willkommen**,
  **Ablauf/Agenda** (aktueller Punkt markiert, weiterschalten per Kachel, Tastenkürzel oder Handy),
  **Pause** mit Restzeit und „weiter um …“, **Laufschrift**, **Zitat**, **Ankündigung**, **Fragen?** und
  **WLAN-Zugang mit QR-Code** (Handy scannt und verbindet sich).
- **Vorlagen** (neue Kachel, auch unter Szenen „Aus Vorlage …“): Seiten und **fertige Szenen** (Begrüßung mit
  Uhr, Ablauf + Uhr + Hinweis, Pause, Kamera + Laufschrift, Fragerunde, Gäste-WLAN, Countdown bis zum Start) –
  Text eingeben, Vorschau sehen, **sofort zeigen oder als Szene speichern**.
- **Browser steuern:** jetzt mit **Stift, Marker und Radierer** – direkt auf die Website auf Monitor 2 zeichnen
  (mit Farben, Rückgängig, Löschen).
- **Browser bei Standbild:** Die Vorschau zeigt jetzt die **echte Seite hinter dem Standbild** – man kann schon
  weiterklicken/scrollen, während das Publikum noch das eingefrorene Bild sieht; „Standbild aus“ zeigt dann das
  Ergebnis. Vorher zeigte die Vorschau nur das eingefrorene Bild.

### Neu in dieser Version (0.18.0)
**AirPlay repariert**
- Monitor 2 ist bei AirPlay **nicht mehr „Erweitert“**: Er zeigt sofort einen großen **Warte-Bildschirm mit
  Name und Code**. Verbindet sich das iPhone, legt AluPC dessen Bild **randlos und im Vordergrund** genau über
  Monitor 2 – vorher ging das Fenster unter Windows im Hintergrund auf.
- **Einstellungen werden übernommen:** Ändert man Name oder Code, startet der Empfänger sofort neu. Ältere
  uxplay-windows-Versionen (1.x) ignorierten AluPCs Einstellungen – AluPC startet dort jetzt deren
  `uxplay.exe` direkt. Ein schon laufendes uxplay-windows (eigener Autostart) wird vorher beendet.

**Handy-Steuerung – komplett neu**
- Vier Reiter: **Start**, **Zeichnen** (mit dem Finger direkt auf Monitor 2: Stift, Marker, Radierer, Laser,
  Farben, Rückgängig, Vollbild), **Folien** (Klicker + **Touchpad für die PC-Maus**) und **Senden**.
- Vom Handy aus: **Kamera, iPhone-Warte-Bildschirm, QR-Code und Timer** zeigen, **Timer-Vorgaben** 1–15 min.
- Als **App auf den Home-Bildschirm** legen; Anzeige „Keine Verbindung“, wenn das WLAN weg ist.
- **QR-Code:** AluPC nimmt jetzt die richtige WLAN-Adresse (nicht WSL/VPN/VirtualBox) – das war
  wahrscheinlich der Grund, warum das Handy nur „Link kopieren“ anbot. Adresse im Handy-Fenster wählbar.

**Mehr Einstellungen, weniger selbst einrichten**
- **Beim Start zeigen:** zuletzt Gezeigtes, nichts, Spiegeln, Kamera, AirPlay, QR-Code oder **eine Szene**.
- **Standard-Kamera:** vorausgewählt (die erste gefundene), Klick auf „Kamera“ startet sie sofort; der Pfeil
  wählt eine andere. Anzeige „füllen“ oder „ganzes Bild“.
- Neuer Setup-Bereich **Handy & Kamera**: AirPlay-Name, randlos an/aus, **was Handys dürfen** (senden,
  fernsteuern, Live-Bild, Zeichnen), Handy-Steuerung beim Start.
- **Windows-Firewall** wird automatisch freigegeben (Setup.exe bzw. Ersteinrichtung, nur private Netze).

**Design-Update**
- Neue Farbpalette (tiefes Nachtblau im dunklen, klares Weiß-Grau im hellen Design), sanfter Farbverlauf
  hinter den Seiten.
- **Kacheln** mit eigener Farbe je Funktion, Symbol im Farbverlauf, **leuchtender Rand**, wenn aktiv.
- **Seitenleiste:** gewählter Bereich als farbige Fläche; unten eine **Monitor-2-Karte mit Live-Bild** und
  Zustand (LIVE, SCHWARZ …) – auf jeder Seite sichtbar, Klick führt zur Startseite.
- Seitenköpfe mit Symbol (auch in Dialogen), Setup-Bereiche mit Akzentbalken, klarere Abschnitte.

**Ehrlich:** Mit echtem iPhone und echtem Handy-Touchpad am echten PC nicht getestet. Geprüft: die Handy-Seite
im echten Browser (Zeichnen, Touchpad, Klicks, Timer kommen an), AirPlay-Start und Bonjour auf einem echten
Windows-Rechner (GitHub), randloses Platzieren eines Fensters unter Windows (siehe CI).

### Neu in dieser Version (0.17.0) – AirPlay unter Windows
- **AirPlay (iPhone/iPad) geht jetzt auch unter Windows ohne Handarbeit:** AluPC installiert über winget
  **„uxplay-windows“** (Paket `leapbtw.uxplay`, UxPlay fertig für Windows gebaut) und **Bonjour** – in der
  Ersteinrichtung, über „Automatisch einrichten“ im Handy-Fenster oder gleich im Setup.exe.
- AluPC trägt **Name und Code** in dessen Einstellungsdatei ein, startet und beendet den Empfänger selbst und
  legt das iPhone-Fenster **maximiert auf Monitor 2**. Läuft uxplay-windows schon (eigener Autostart), wird es
  dafür beendet – es darf nur einen AirPlay-Empfänger geben.
- Geprüft auf einem echten Windows-Rechner (GitHub): AluPC startet uxplay-windows, Port 7000 ist offen und der
  PC wird per Bonjour als „AluPC CI-Test“ angekündigt – genau das, was ein iPhone in der Liste
  „Bildschirmsynchronisierung“ sieht. **Mit einem echten iPhone ist es nicht getestet.**
- Ehrlich: uxplay-windows ist ein **Community-Paket** eines einzelnen Entwicklers (nicht vom UxPlay-Projekt),
  nicht signiert – Windows Defender kann warnen. Beim ersten Start fragt die Windows-Firewall: „Zugriff
  zulassen“ klicken, sonst sieht das iPhone den PC, kann sich aber nicht verbinden.
- Behoben: Namen mit Leerzeichen (z. B. „AluPC (Mein-PC)“) wären bei uxplay-windows zerbrochen.
- Diagnose zeigt jetzt Pfad, Einstellungsdatei und Meldungen von uxplay-windows.

### Neu in dieser Version (0.16.0)
- **Handy-Stream (Android/scrcpy) und Miracast entfernt** – Kacheln, Einrichtung, Diagnose und Installer.
  Handy auf Monitor 2 heißt jetzt: **AirPlay** (iPhone/iPad) und **Handy-Steuerung** (QR-Code, jedes Handy).
- Installer: kein scrcpy und kein Miracast-Empfänger (DISM) mehr; Setup.exe bietet nur noch Bonjour an.
- Vorbereitet: ein mit dem Installer mitgeliefertes UxPlay für Windows wird automatisch gefunden und mit
  seinen eigenen Video-Bibliotheken gestartet.

### Neu in dieser Version (0.15.2)
- Behoben: **Zeichnungen und Laserpunkt fehlten in Bild-in-Bild** (und in der Live-Vorschau im Hauptfenster
  und im Live-Bild auf dem Handy). Sie liegen in einem eigenen Fenster über Monitor 2 und werden jetzt in
  alle Vorschauen mit eingezeichnet (bei „Schwarz“ wie auf Monitor 2 nicht).

### Neu in dieser Version (0.15.1)
- Behoben: Beim Beenden konnten noch laufende Hintergrundaufgaben (z. B. Android-Suche, Miracast-Prüfung)
  einen Absturz auslösen – AluPC wartet jetzt kurz, bis sie fertig sind.

### Neu in dieser Version (0.15.0) – Reparaturen: AirPlay, Spiegeln, Miracast
- **AirPlay repariert:** UxPlay (Kubuntu 24.04: Version 1.68) öffnet sein Bild-Fenster erst, wenn sich das
  iPhone verbindet – AluPC hat es bisher nur 15 Sekunden lang gesucht (unter KDE sogar gar nicht richtig)
  und dann aufgegeben. Jetzt wird es dauerhaft verfolgt und bei jeder Verbindung auf Monitor 2 gelegt.
  Feste Ports (Firewall), und die Einrichtung installiert/aktiviert auch **avahi** (ohne den findet das
  iPhone den PC nicht), GStreamer-Decoder und öffnet die Firewall. Scheitert UxPlay, sagt AluPC warum.
  Geprüft mit dem echten UxPlay 1.68: „AluPC (Rechnername)“ erscheint im Netz als AirPlay-Gerät.
- **Spiegeln repariert:** Liefert die Bildaufnahme kein Bild (4 s) oder scheitert sie schon beim Start,
  spiegelt AluPC automatisch **über das Betriebssystem** (Windows wie Win+P, KDE per kscreen-doctor).
  Das `.deb` bringt jetzt alle X11-Bibliotheken mit (ohne sie startete Qt unter X11 evtl. gar nicht).
- **Miracast:** prüft vorher, ob WLAN-Adapter/Treiber „Drahtlose Anzeige“ können – viele Desktop-PCs
  (ohne WLAN) können grundsätzlich kein Miracast; AluPC sagt das jetzt klar.
- **Ersteinrichtung:** Beim ersten Start richtet ein Assistent mit einem Klick alles ein (Monitore,
  Spiegel-Test, Handy-Programme, Name/Code, Autostart). Das **.deb** installiert UxPlay, scrcpy,
  GStreamer und avahi gleich mit; **Setup.exe** installiert optional scrcpy/Bonjour (winget) und den
  Miracast-Empfänger.
- **Diagnose kopieren** (Setup → Allgemein): prüft alles und kopiert das Ergebnis – zum Weitergeben.
- **Aufgeräumt:** Links nur noch Start, Szenen, Setup, Fingerabdruck. Handy-Einrichtung über die
  Handy-Kacheln (Pfeil), RGB & Lüfter im Setup.
- **Neues Design:** großer Monitor-2-Bereich mit Live-Bild und Schaltern (Schwarz, Standbild,
  Bild-in-Bild, Zeichnen, Beenden); kompakte Kacheln mit Symbol links.
- **Handy-Oberfläche neu:** App-Look mit echten Symbolen, drei Reiter; neu **„Präsentation“**:
  Folien weiter/zurück, Start, Schwarz, Ende – steuert PowerPoint, Impress, PDF am PC (Windows und
  Kubuntu-X11; unter Wayland nicht möglich).
- Behoben: adb (Android-Erkennung) konnte AluPC/Diagnose einfrieren lassen.
- **Ehrlich:** Geprüft mit echtem UxPlay, echter X11-Aufnahme und echten Tastendrücken unter X11 – aber
  nicht mit echtem iPhone, Android-Handy, Miracast-Gerät oder deinem PC. Wenn etwas nicht geht:
  Setup → Allgemein → „Diagnose kopieren“ und den Text schicken.

### Neu in dieser Version (0.14.1)
- **Eigene Kacheln je Handy-Weg** in der neuen Rubrik „Handy“ auf der Startseite: **AirPlay**
  (iPhone & iPad), **Handy-Stream** (Android per USB), **Handy-Steuerung** (QR-Code, zeigt „LÄUFT“,
  solange Handys verbinden können) und **Miracast** – Klick startet sofort, der Pfeil zeigt Optionen
  (z. B. neuer Code, beenden) und „Einrichten und Hilfe“. Unter Linux steht bei Miracast ehrlich
  „Nur unter Windows“. Die bisherige Sammelkachel „Handy“ entfällt; die Seite „Handy“ bleibt.

### Neu in dieser Version (0.14.0)
- **Neue Seite „Handy“** (links in der Leiste, auch per Klick auf die Kachel „Handy“): vier klar getrennte
  Karten – **Jedes Handy** (Browser/QR-Code), **iPhone & iPad** (AirPlay), **Android** (USB) und
  **Miracast** – jede mit Status („Bereit“, „Einrichten“, „Verbunden“ …), drei Schritten und einem großen
  „Auf Monitor 2 zeigen“.
- **Richtet sich automatisch ein**: Beim ersten Öffnen installiert AluPC fehlende Programme selbst
  (Kubuntu: UxPlay und scrcpy mit einer Passwortabfrage; Windows: scrcpy und Bonjour über winget),
  vergibt einen eindeutigen AirPlay-Namen („AluPC (Rechnername)“) und den Zugangscode. Später reicht
  „Automatisch einrichten“ oben auf der Seite.
- **Android-Handys werden per USB automatisch erkannt** (inkl. Hinweis „am Handy zulassen“).
- **Bessere Handysteuerung** (QR-Code scannen): neues Design mit Reitern „Steuern“ und „Senden“,
  **Live-Bild von Monitor 2** auf dem Handy, **Laserpointer per Finger** auf dem Live-Bild, große Knöpfe
  mit Anzeige, was gerade an ist (Schwarz, Standbild, Spiegeln, Erweitern, Bildschirmschoner),
  aktive Szene hervorgehoben, **Timer** (Start/Pause, ±1 min, auf Monitor 2), Video, Lautstärke,
  **RGB-Licht**. Leichtes Vibrieren beim Tippen (Android).
- **Ehrlich:** AirPlay unter Windows braucht weiterhin UxPlay von Hand (dafür gibt es kein
  winget-Paket). Das Live-Bild aufs Handy ist ein Standbild pro Sekunde, kein Video. Nicht mit echten
  Handys getestet – getestet im Handy-Browser-Simulator und mit echten Anfragen an den Webserver.

### Neu in dieser Version (0.13.0)
- **Einstellungen sichern und laden** (Setup → „Sichern & Sync“): exportieren/importieren als Datei –
  alles oder nur einzelne Bereiche, z. B. **nur die Startseite**.
- **Dual-Boot: Windows ↔ Linux automatisch abgleichen**: Einmal auf beiden Systemen einschalten (Ordner
  „AluPC-Sync“ auf dem Windows-Laufwerk, das andere System findet ihn selbst) – danach gleicht AluPC beim
  Start und nach jeder Änderung ab. Unabhängig von der Uhrzeit (die geht bei Dual-Boot oft falsch);
  haben beide Seiten geändert, wird die andere Fassung als Sicherung aufgehoben. Monitor-Namen, Kameras,
  Programmpfade und Fingerabdruck bleiben je System getrennt.
- **RGB-Beleuchtung** (neue Seite „RGB & Lüfter“) über **OpenRGB**: Farbe, Helligkeit, aus, **Farbe
  folgt Monitor 2**, Geräte einzeln an/aus; Befehle `rgb_farbe`, `rgb_monitor2`, `rgb_aus`.
- **Temperaturen und Lüfter** (Linux): alle Sensoren live mit Farbbalken; steuerbare Lüfter per Regler
  (mindestens 30 %, „Automatisch“ zurück ans Mainboard). Windows: nicht möglich (keine Schnittstelle).
- **Design**: Kacheln mit weichem Schatten und Anheben beim Drüberfahren, aktive Kacheln mit Verlauf,
  Hauptknöpfe mit leichtem Verlauf, neue Symbole (Lüfter, Sync, Export/Import).
- **Ehrlich:** RGB braucht ein installiertes OpenRGB und ist nur gegen einen nachgebauten OpenRGB-Server
  getestet; Lüfter nur unter Linux und nur, wenn der Kernel die Regler kennt; Dual-Boot-Abgleich mit zwei
  simulierten Systemen getestet, nicht mit echtem Dual-Boot.

### Neu in dieser Version (0.12.1)
- **Live-Vorschau von Monitor 2** in der Statuskarte (Klick darauf: Bild-in-Bild) und Knopf
  **„Beenden“**, der Monitor 2 sofort wieder zum normalen Bildschirm macht.
- Kacheln: kürzere, verständliche Untertexte (nichts mehr abgeschnitten), „AKTIV“ und Menü-Pfeil
  überlappen nicht mehr; „Meine Szenen“: Klick öffnet die Szenen-Seite, Pfeil startet eine Szene.
- Hinweis-Banner mit passenden Symbolen (Info/Warnung statt Fingerabdruck), Monitor-Anzeige unten
  links mit Auflösung, Layout-Namen im Szenen-Editor vollständig, Setup-Menü ohne abgeschnittene Texte.
- **AluCast-Korrekturen:** Code mit Leerzeichen („424 242“) wurde abgeschnitten und abgelehnt; ein
  Handy mit altem Code hat sich durch ständiges Nachfragen selbst gesperrt – jetzt fragt es nach dem
  neuen Code; nach „Beenden“ nimmt AluCast auch über noch offene Verbindungen nichts mehr an; startet
  nicht mehr ungefragt bei jedem Programmstart (nur mit Haken „Beim Start mitstarten“); hängende
  Verbindungen werden nach 60 s getrennt.

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
