## AluPC – Monitor 2 steuern (Kubuntu & Windows 11)

### Downloads
| System | Datei | Hinweis |
|---|---|---|
| **Windows 11** | `AluPC-Setup-….exe` | Installer (Startmenü, Deinstallation) |
| Windows 11 | `AluPC-windows-portable-….zip` | ohne Installation: entpacken, `AluPC.exe` starten |
| **Kubuntu / Ubuntu** (22.04, 24.04 und neuer) | `alupc_…_amd64.deb` | `sudo apt install ./alupc_…_amd64.deb` – danach im Startmenü |
| Linux (x86_64) | `AluPC-linux-x86_64-….tar.gz` | ohne Installation: entpacken, `AluPC/AluPC` starten |

### Neu in dieser Version (0.66.0)
- **Helligkeit entfernt** (Kachel, Menü, Fenster und Befehle „heller/dunkler“) – hat nicht zuverlässig funktioniert.
  Gespeicherte Startseiten ohne die Kachel laden normal weiter.
- **Bild-in-Bild bleibt unter Linux (KDE) oben:** Solange es offen ist, läuft ein KWin-Skript, das „immer oben“
  bei jedem neu geöffneten oder angeklickten Fenster erneut setzt (vorher nur einmal kurz nach dem Öffnen).
  Das Fenster ist unter Linux kein „Hilfsfenster“ mehr, erscheint aber trotzdem nicht in der Taskleiste und
  auf allen Arbeitsflächen. Beim Schließen wird das Skript entfernt.
  *Ehrlich:* nur mit Tests und nachgebautem KWin geprüft, nicht auf einem echten KDE-Desktop. Vollbild-Programme
  (z. B. Video im Vollbild), die gerade aktiv sind, legt KDE trotzdem darüber.

### Neu in Version 0.65.0
- **Behoben: AluPC „stürzte ab“, wenn man AirPlay verlassen hat.** Genauer: Es fror ein – Qts Videoplayer wartete
  beim Aufräumen auf seinen Lese-Thread, der auf Netzwerkdaten hing (das Lebenszeichen des Relais hielt ihn am
  Leben). KDE beendete AluPC dann als „reagiert nicht“. Jetzt wird der Player vom Strom getrennt, bevor er
  aufgeräumt wird – Rausgehen dauert Sekundenbruchteile.
- **Behoben: Bild fror nach dem Drehen des iPads ein.** Ändert sich das Bildformat (Drehen, neue Verbindung),
  blieb der Player beim alten stehen. AluPC erkennt das jetzt und startet ihn mit dem neuen Bild neu.

### Neu in Version 0.64.0
- **AirPlay flüssiger (vor allem Linux/VM):** AluPC meldet dem iPhone/iPad jetzt die Größe von Monitor 2
  (höchstens 1920×1080). Das Gerät schickt dann nicht mehr Pixel als nötig. Gemessen bei 1280×720 statt iPad-
  Auflösung: ~3,7 statt ~10 ms Rechenzeit je Bild in AluPC – dazu weniger Arbeit beim Dekodieren. Gilt auch
  für ältere UxPlay-Versionen mit eigenem Fenster.

### Neu in Version 0.63.0
- **Behoben (Linux): AluPC öffnete sich auf Monitor 2** – man musste es jedes Mal zurückziehen. Wayland lässt
  Programme ihr Fenster nicht selbst platzieren; AluPC bittet jetzt KDE, es mittig auf Monitor 1 zu legen (auch
  wenn es beim Wiederholen aus der Taskleiste auf Monitor 2 landet).

### Neu in Version 0.62.0
- **Behoben: Bild-in-Bild wurde von anderen Fenstern verdeckt.** KDE (Wayland) ignoriert „immer im
  Vordergrund“ von Qt – AluPC setzt es jetzt über KDE selbst (wie beim Monitor-2-Fenster). Unter Windows holt
  AluPC das Fenster regelmäßig wieder ganz nach vorne.
- **Entfernt: Displays ausschalten** (funktionierte nicht zuverlässig). Die Kachel heißt jetzt „Helligkeit“ und
  regelt nur noch die Helligkeit je Monitor.

### Neu in Version 0.61.0
**Neu: Whiteboard**
- Kachel „Whiteboard“: Monitor 2 wird zur Tafel, „Zeigen & Zeichnen“ öffnet sich gleich mit dem Stift.
  Hintergründe (Pfeil an der Kachel): Weiß, Kariert, Liniert, Punkteraster, Millimeterpapier,
  Koordinatensystem, Notenlinien, grüne Tafel, schwarze Tafel, Blaupause. Die Stiftfarbe passt sich an
  (hell auf Tafeln, dunkel auf Papier). „Tafel wischen“ löscht alles Gezeichnete.

**Neu: Displays – Helligkeit und Ausschalten**
- Kachel „Displays“: Helligkeit je Monitor, einzelne Monitore oder alle ausschalten. **Eine Taste oder die Maus
  schaltet wieder ein.**
- Helligkeit, je Monitor der erste Weg, der geht: echte Monitor-Helligkeit über das Kabel (DDC/CI – unter Linux mit
  dem Programm `ddcutil`), Laptop-Bildschirm, sonst dunkelt AluPC das Bild selbst ab (z. B. in einer VM; man
  kann weiter durchklicken). Das Fenster zeigt, welcher Weg gilt.
- „Alle aus“ nutzt das Energiesparen des Systems (Windows, KDE, X11). Einzelne Monitore schaltet AluPC per
  DDC/CI aus (wenn der Monitor das kann) und deckt sie schwarz ab.
- Auch als eigene Kachel-Befehle: Alle Displays aus, Monitor 2 aus, Heller, Dunkler.

**Design-Update**
- Farbverläufe statt Einzelfarben: Jede Akzentfarbe hat eine Partnerfarbe (z. B. Blau → Violett) – Hauptknöpfe,
  aktive Navigation, Seitensymbole, Häkchen, Regler, Menüs, Bereichs-Zähler.
- Tieferer Hintergrund mit Polarlicht-Leuchten, Glas-Karten mit Lichtkante, leuchtende Monitor-2-Karte.
- Kacheln mit zweifarbigen Symbolen, leuchtendem Rand und Glanz beim Drüberfahren.
- **Behoben:** Die Schalter „Bild-in-Bild“ und „Zeichnen“ im Monitor-2-Kasten wurden abgeschnitten
  („Bild-in-Bil“). Die Breite wird jetzt selbst berechnet und nach dem Aufbau nachgeprüft.

### Neu in Version 0.60.0
**Bildschirmschoner zuverlässig – und das System dunkelt nicht mehr ab**
- Linux und Windows dimmen bzw. schalten die Monitore nicht mehr selbst ab, solange der Bildschirmschoner
  eingeschaltet ist oder Monitor 2 etwas zeigt (wie bei einem Videoplayer). Einstellung: Setup →
  Bildschirmschoner → „System nicht abdunkeln lassen“ (Standard an). Hinweis: Der PC sperrt sich dann auch nicht
  von selbst. Beim Beenden von AluPC darf das System wieder abdunkeln.
- KDE meldet die Leerlaufzeit je nach Version in Millisekunden statt Sekunden (oder unter Wayland immer 0).
  AluPC glaubte das bisher – der Schoner startete dann bei kurzen Pausen und ging nicht mehr weg. Jetzt misst AluPC
  die Einheit selbst und nutzt den Wert erst, wenn er stimmt.
- Mausbewegung zählt immer als Aktivität (beendet den Schoner bzw. verhindert den Start).
- „Diagnose kopieren“ zeigt, woher AluPC die Leerlaufzeit nimmt und ob das Abdunkeln verhindert wird.

### Neu in Version 0.59.0
**Behoben (Linux): AirPlay verbunden, Ton da – aber kein Bild**
- Ursache: Ein iPhone/iPad schickt beim Bildschirm-Spiegeln das vollständige Bild (Schlüsselbild) nur einmal,
  direkt beim Verbinden. AluPCs Player gab ohne Daten nach ~20 s auf und wurde erst nach 30 s neu gestartet.
  Verband sich das iPad in dieser Lücke, ging das Schlüsselbild verloren – und es kam nie ein Bild.
- Jetzt: Ein kleines Relais zwischen UxPlay und AluPC merkt sich das letzte Schlüsselbild samt allem danach und
  reicht es einem neu gestarteten Player sofort nach. Es hält die Verbindung wach, und fällt der Player aus,
  startet AluPC ihn sofort neu (nicht erst nach 30 s).
- Ein ruhiger iPad-Bildschirm (keine neuen Bilder) schaltet nicht mehr zurück auf „AirPlay bereit“ – das passiert
  nur noch, wenn sich das iPad wirklich trennt.
- Geprüft mit nachgestelltem iPad (nur ein Schlüsselbild, Verbinden in der Lücke) und Bildern in iPad-Größe
  (2048×1536). Mit einem echten iPad konnte ich nicht testen.

### Neu in Version 0.58.0
- **Programme: „Verschieben“ entfernt.** „Programm auf Monitor 2“ zeigt jetzt nur noch die Liste der Programme –
  auswählen, „Anzeigen“, fertig (AluPC zeigt eine Kopie des Fensters; das Programm bleibt, wo es ist).

### Neu in Version 0.57.0
- **Browser steuern läuft flüssig:** Die Vorschau zeigt beim Klicken, Scrollen und Tippen jetzt ~20 Bilder/s
  (vorher 5). Bewegte man die Maus ständig, kam bisher gar kein neues Bild, bis man still hielt – das war das
  Ruckeln. Ohne Eingabe bleibt es sparsam (4 Bilder/s). Das Vorschaubild wird zudem nur noch einmal verkleinert
  statt bei jedem Neuzeichnen umgewandelt.

### Neu in Version 0.56.0
- **Behoben: „Vollbildmodus nicht verfügbar“** bei YouTube & Co. auf Monitor 2. Der eingebaute Browser erlaubt
  jetzt Vollbild: Der Vollbild-Knopf der Seite lässt das Video die ganze Website-Fläche füllen (Esc oder der
  Knopf beendet es). Ist die Website Teil einer Szene mit mehreren Feldern, füllt das Video sein Feld.

### Neu in Version 0.55.0
**Behoben (Windows): Nur der erste Finger konnte entsperren**
- AluPC läuft ohne Administratorrechte und darf die geschützte Anmelde-Datei nicht lesen. Es hielt die Anmeldung
  deshalb für ausgeschaltet und hat neu angelernte Finger/Personen nie bei Windows eingetragen.
- Jetzt prüft AluPC bei jedem Öffnen der Fingerabdruck-Seite, ob Windows alle Finger kennt, und trägt fehlende
  von selbst nach („✓ Windows kennt alle angelernten Finger“).
- Mit 0.51–0.54 eingeschaltet? Die Seite zeigt dann **„Neu einrichten“** – einmal klicken, Windows-Passwort
  eingeben, fertig. Danach gehen alle Finger aller Personen.

**Neu: Alle Daten löschen**
- Setup → Allgemein → **„Alle Daten löschen …“**: setzt AluPC zurück wie frisch installiert – Einstellungen,
  Szenen, Startseite, Overlays, vom Handy empfangene Dateien, Namen der Fingerabdrücke, Browser-Daten, Autostart.
  Wahlweise auch die Fingerabdrücke im Modul und die Fingerabdruck-Anmeldung. Zweimal nachfragen, dann startet
  AluPC neu mit der Ersteinrichtung. Das Programm selbst bleibt installiert.

### Neu in Version 0.54.0
**Fingerabdruck unter Windows**
- **Behoben: komische Zeichen** auf dem Sperrbildschirm („Finger auf den Sensor legen â€¦“). Der Anmeldebaustein
  wurde nicht als UTF-8 übersetzt – jetzt schon, und der Bau bricht ab, falls das je wieder passiert.
- **Kein Anklicken mehr nötig:** Der Fingerabdruck hängt jetzt als Anmeldeoption an deiner **eigenen
  Benutzerkachel** (statt als eigene Kachel) und ist vorausgewählt. Auf dem Sperrbildschirm genügt: Finger auflegen.
  Mit Passwort/PIN geht es weiter über „Anmeldeoptionen“.
  Wer die Anmeldung schon eingeschaltet hat: in AluPC einmal **aus- und wieder einschalten** (setzt die Vorauswahl).
- Beim Erkennen steht der Name der Person: „Hallo Lena – melde an …“.

**Personen**
- Personen sind Menschen, keine Benutzerkonten: Es wird kein Kontoname mehr als Person vorgeschlagen, und
  darunter steht, als welches Konto sich alle anmelden.
- Die Belegung zeigt jetzt „12 belegt · 38 frei“ und aktualisiert sich sofort nach Anlernen und Löschen
  (und beim Öffnen der Seite).

### Neu in Version 0.53.0
**Fingerabdruckmodul: mehrere Personen**
- Bei „Fingerabdruck“ gibt es jetzt **Person:** – Namen wählen oder neu eintippen, dann Finger anlernen.
  So passen z. B. 5 Personen × 10 Finger auf ein Modul mit 50 Plätzen. Daneben steht die Belegung
  („12 von 50 Plätzen“), die Liste zeigt „Lena · Rechter Zeigefinger“. Die Hand zeigt die Finger der gewählten Person.
- Alle Personen entsperren **das Konto, unter dem AluPC läuft** (kein eigenes Konto pro Person nötig).
- Neue Finger/Personen gelten **ohne neue Passwort-/Administratorabfrage**: Linux liest beim Anmelden die
  Plätze-Datei des Kontos direkt (nur bei mehreren Linux-Konten fragt es weiter), Windows eine Datei, die
  beim Einschalten für das Konto angelegt wird.
  Wer die Windows-Anmeldung mit 0.51/0.52 eingeschaltet hat: einmal aus- und wieder einschalten, sonst fragt
  Windows weiter bei jeder Änderung nach Administratorrechten.
- **Dual-Boot:** Namen und Zuordnung gehen mit dem Abgleich Windows ↔ Linux mit (neuer Bereich
  „Fingerabdruck“). Die Fingerabdrücke selbst liegen im Modul, beide Systeme sehen also dieselben. Der
  Windows-Benutzer wird dabei auf den Linux-Benutzer umgeschrieben. Anmelden mit Fingerabdruck muss auf
  jedem System einmal eingeschaltet werden.

**Behoben:** Der Assistent „Automatisch einrichten“ fragt unter Windows jetzt nach dem Windows-Passwort,
statt mit „…wird dein Windows-Passwort gebraucht“ abzubrechen.

### Neu in dieser Version (0.52.0)
- **Behoben (Windows): „Kein Zugriff auf COM…“ beim Anlernen** mit dem Fingerabdruckmodul. AluPC öffnete den
  Anschluss beim Anlernen, Anzeigen, Prüfen und Löschen versehentlich zweimal – Linux erlaubt das, Windows
  nicht (nur das Suchen klappte deshalb). Neuer Test stellt Windows' „nur einmal öffnen“ nach.
- AluPC greift jetzt nacheinander auf das Modul zu (Fingerabdruck-Seite und Assistent kommen sich nicht mehr in
  die Quere) und wartet kurz, falls der Anschluss gerade belegt ist.
- Ist der Anschluss wirklich von einem anderen Programm belegt, sagt AluPC das unter Windows jetzt so
  (z. B. Arduino-IDE, serieller Monitor) statt des Linux-Hinweises „Automatisch einrichten“.

### Neu in dieser Version (0.51.0)
**Fingerabdruckmodul (HLK-ZW101 u. a.): jetzt auch unter Windows anmelden und entsperren**
- Windows Hello nimmt solche Module nicht an – AluPC bringt deshalb einen eigenen **Anmeldebaustein**
  („Credential Provider“, wie ihn auch Hersteller von Karten- und Fingerabdrucklesern nutzen) mit: Auf dem
  Anmelde- und Sperrbildschirm erscheint die Kachel **„Fingerabdruck (AluPC)“**. Finger auflegen → erkennt das
  Modul einen angelernten Finger, meldet die Kachel den zugehörigen Benutzer an.
- Einschalten: Fingerabdruck → „Anmelden mit Fingerabdruck“ → Windows-Passwort eingeben (nicht die PIN).
  AluPC prüft es bei Windows und speichert es verschlüsselt (DPAPI); die Datei dürfen nur Windows selbst und
  Administratoren lesen. Windows fragt einmal nach Administratorrechten. Das Passwort funktioniert weiter.
- Passwort geändert → in AluPC neu einschalten (die Kachel sagt es dann auch). Ausschalten bzw. AluPC
  deinstallieren entfernt Baustein und gespeichertes Passwort.
- Linux: wie bisher über PAM (Anmeldebildschirm, Sperrbildschirm, sudo).
- **Treiber:** Steckt ein USB-Seriell-Adapter (CH340, CP210x, FTDI, PL2303) ohne Treiber, sagt AluPC unter
  Windows jetzt, welcher Chip es ist und wo es den Treiber gibt (Linux hat ihn eingebaut).
- Geprüft: Baustein auf Windows (CI) gebaut und gegen ein nachgebautes Modul getestet – Finger erkannt,
  Anmeldedaten für Windows korrekt gebaut, Passwort aus DPAPI korrekt; Einrichten/Abmelden in der
  Registry. Nicht geprüft: echter Anmeldebildschirm mit echtem ZW101 (keine Hardware).

### Neu in dieser Version (0.50.0)
Enthält auch den AirPlay-Fix aus 0.49.0 (0.49.0 wurde wegen eines CI-Prüfschritts nicht veröffentlicht).

**Design-Update und Rundum-Prüfung**
- **Startseite ragte rechts über den Rand**, sobald etwas auf Monitor 2 lief (die Statuskarte verlangte ~925 px).
  Die Karte wählt ihre Form jetzt selbst: breit mit beschrifteten Schnellschaltern, mittel nur mit Symbolen
  (Name als Tooltip), schmal untereinander. Nichts wird mehr abgeschnitten („Bild-in-Bil…“).
- **Overlay-Editor:** Schnellwahl unter der Vorschau (Musik, Uhr, Bauchbinde, Laufschrift, LIVE) – ein Klick
  legt das Overlay an; freundlicherer Hinweis, solange noch keins da ist.
- Selbsttest und „Diagnose kopieren“ zeigen den AirPlay-Bildweg (-vrtp, RTP über -vd/-vc/-vs oder Fenster).
- Geprüft: alle Seiten in Hell/Dunkel bei 820, 1180 und 1400 px Breite, Mini-Menü, Dialoge, Monitor-2-Anzeigen;
  162 automatische Tests; Selbsttest der App.
- CI: Die Prüfung des neuen AirPlay-Bildwegs läuft nur, wenn die UxPlay-Version ihn kennt (UxPlay 1.46 aus
  Ubuntu 22.04 nicht – dort nimmt AluPC wie bisher UxPlays Fenster).

### Neu in dieser Version (0.49.0)
**Linux: AirPlay-Bild jetzt direkt in AluPC (auch mit UxPlay 1.68 aus Kubuntu)**
- Bisher zeigte UxPlay 1.68 das iPhone-Bild in einem eigenen Fenster, das AluPC auf Monitor 2 schieben musste –
  unter Wayland und in VMs kam es oft nicht an (verbunden, Ton ja, Bild nein). Jetzt baut AluPC UxPlays
  Bildweg selbst: `-vd identity -vc identity -vs "rtph264pay … ! udpsink …"` – UxPlay reicht das H.264 vom
  iPhone unverändert an AluPC weiter (wie `-vrtp` ab UxPlay 1.73), AluPC zeigt es als normale Quelle.
- Dadurch auf Monitor 2 ohne Fensterschieben, mit Übergängen, Standbild, Bild-in-Bild und Overlays darüber.
- Geprüft: echtes UxPlay 1.68 nimmt den Bildweg an („Initialized GStreamer video renderer“, auch in der CI);
  genau diese Pipeline liefert Bilder an AluPCs Player. Ein echtes iPhone konnte nicht getestet werden.
- „Diagnose kopieren“ zeigt, welcher Weg genutzt wird.

### Neu in dieser Version (0.48.0)
- **Overlays als eigene Kacheln auf der Startseite** – wie die Bildschirmschoner-Kacheln: Startseite anpassen →
  „Overlay“ → Vorlage wählen. Beliebig viele, jede mit eigenem Overlay (Stelle, Größe, Stil, Text …
  unter „Bearbeiten …“ → „Einstellen …“). Klick blendet das Overlay ein, nochmal klicken aus; die Kachel zeigt
  dann „AN“. Unabhängig von den Overlays aus dem Editor – „Overlays aus“ blendet aber alle aus.
- Auch als Aktion jeder eigenen Kachel wählbar („Overlay einblenden“), mit Tastenkürzel.

### Neu in dieser Version (0.47.0)
**Overlays – Einblendungen über allem, was Monitor 2 zeigt**
- Neue Kachel **Overlays** (Bereich Werkzeuge): Klick = an/aus, Pfeil = einzelne Overlays an/aus und
  „Bearbeiten …“. Overlays liegen in einem eigenen durchsichtigen Fenster über Monitor 2 – also auch über dem
  iPhone-Bild (AirPlay), einem Programm, Video, Website oder der Kamera.
- **15 Vorlagen:** Musik (kompakt, Leiste, großes Cover, schlicht – zeigt, was der PC abspielt), Uhr, Uhr mit
  Datum, Timer, Bauchbinde, Überschrift, Laufschrift, Hinweis, Logo/Bild, QR-Code, LIVE, REC.
- **Verschieben:** in der Vorschau ziehen – rastet in den Ecken, an den Kanten-Mitten und in der Mitte ein,
  jede Stelle dazwischen geht auch (Alt gedrückt = ohne Einrasten). Oder per 3×3-Knöpfen. Mausrad = Größe.
- Je Overlay: Größe, Stil (Glas, Hell, Farbe, ohne Hintergrund), Farbe, Text, Bild, Link …
- Bei „Schwarz“ und beim Bildschirmschoner verschwinden Overlays. Bild-in-Bild, Live-Vorschau und Handy zeigen
  sie mit. Befehle für Tastenkürzel/eigene Kacheln/Handy: `overlays`, `overlays_an`, `overlays_aus`.
- Sparsam: gezeichnet wird nur der Bereich eines Overlays, die Uhr einmal pro Sekunde; bewegt sind nur
  Laufschrift und LIVE-Punkt.

### Neu in dieser Version (0.46.0)
**„Läuft gerade“ – was der PC abspielt, groß auf Monitor 2**
- Neue Kachel **Läuft gerade**: Cover, Titel, Künstler, Album und Zeitleiste – von jedem Player, nicht nur
  Spotify: YouTube im Browser, VLC, Musik-Apps … Der Hintergrund ist das weichgezeichnete Cover; bei Pause
  erscheint ein Pause-Zeichen. Läuft nichts, steht dort „Gerade läuft nichts“.
- Steuern: Pfeil an der Kachel (Abspielen/Pause, nächster/vorheriger Titel), Handy-Steuerung (neue Karte
  „Musik am PC“), eigene Kacheln und Tastenkürzel (Befehle `musik_pause`, `musik_weiter`, `musik_zurueck`,
  `musik_zeigen`).
- Auch als Quelle in Szenen („Läuft gerade (Musik am PC)“), z. B. neben Uhr oder Kamera.
- Linux: über MPRIS (wie das Medien-Widget von KDE). Windows: über die Windows-Mediensteuerung (wie das
  Medien-Popup bei den Lautstärketasten). Fragt nur ab, solange es angezeigt wird (etwa 1× pro Sekunde).

### Neu in dieser Version (0.45.0)
**Linux: iPad/iPhone verbunden (Ton kommt), aber kein Bild auf Monitor 2**
- In einer virtuellen Maschine startet AluPC UxPlay jetzt mit Software-Decoder und ohne Zeitstempel-Abgleich
  (`-avdec -vsync no`, nur wenn die UxPlay-Version das kennt). Die Uhr einer VM läuft ungleichmäßig – UxPlay hat
  dann jedes Bild als „zu spät“ verworfen: Ton ja, Bild nein.
- KDE: Sobald sich das Gerät verbindet, verschwindet der „AirPlay bereit“-Bildschirm, damit er UxPlays Fenster
  nicht verdecken kann; beim Trennen kommt er wieder. Das UxPlay-Fenster wird außerdem nach vorne geholt.
- „Diagnose kopieren“ zeigt, ob AluPC eine virtuelle Maschine erkannt hat und welche UxPlay-Zusätze gelten.

### Neu in dieser Version (0.44.0)
- **Websites/YouTube auf Monitor 2 jetzt mit Ton.** Der eingebaute Browser (Chromium) spielte Ton erst nach einem
  Klick auf die Seite – auf Monitor 2 klickt aber niemand, also blieb es stumm („NotAllowedError“). Jetzt dürfen
  Websites auf Monitor 2 sofort mit Ton abspielen. Geprüft mit echtem Ton-Server: vorher blockiert, jetzt läuft ein
  Ton-Stream.
- **Diagnose: Ton für AirPlay (Linux).** „Diagnose kopieren“ zeigt jetzt, ob UxPlay Ton ausgeben kann
  (AAC-Decoder, GStreamer-Ausgabe, Ton-Server mit Standard-Ausgang) und UxPlays Meldungen zum Ton.

### Neu in dieser Version (0.43.0)
- **Linux (KDE, Wayland): Maus bleibt auf Monitor 1.** Wayland erlaubt keinem Programm, die Maus festzuhalten –
  KWin lässt sie aber nicht über eine Lücke zwischen zwei Monitoren springen. AluPC rückt Monitor 2 darum mit
  Abstand weg, sobald die Maus auf Monitor 1 ist, und schließt die Lücke bei „Erweitern“ und beim Beenden wieder.
  Landet die Maus doch auf Monitor 2 (z. B. Grafiktablett), geht die Lücke zu, damit sie zurück kann.
  In einer virtuellen Maschine mit Mausintegration hilft das nicht (dort setzt der echte PC die Maus direkt).

### Neu in dieser Version (0.42.0)
- **Linux: Spiegeln immer noch falsch herum** – eigentliche Ursache: Unter KDE/Wayland hielt AluPC den
  falschen Monitor für den Hauptmonitor (Qt meldet einfach den zuerst gefundenen). Jetzt gilt, was KDE in den
  Anzeige-Einstellungen als Hauptmonitor (Priorität 1) führt. „Diagnose kopieren“ zeigt beides an.
- **Dual-Boot: Videos/Bilder aus Windows-Szenen gehen unter Linux.** Ein Pfad wie `C:\Users\…\Film.mp4` wird
  unter Linux automatisch auf dem eingehängten Windows-Laufwerk gesucht (auch bei anderer Groß-/Kleinschreibung),
  umgekehrt genauso. Statt „Could not open file“ steht da „Video nicht gefunden“ mit Hinweis, falls das
  Windows-Laufwerk nicht eingehängt ist.

### Neu in dieser Version (0.41.0)
- **Linux: Spiegeln war falsch herum** (der Hauptbildschirm zeigte Monitor 2). KDE-Spiegeln legte beide Monitore
  nur an dieselbe Stelle – welcher welchen zeigt, entschied KDE. Jetzt sagt AluPC KDE ausdrücklich „Monitor 2 ist
  eine Kopie von Monitor 1“ (KDE Plasma ab 6.1) und prüft das Ergebnis; ältere KDE-Versionen nutzen wie bisher
  die Position. „Erweitern“ hebt die Kopie wieder auf.

### Neu in dieser Version (0.40.0)
**Windows: iPhone/iPad sieht „AluPC“, Verbinden lädt aber endlos → „Verbindung nicht möglich“**
- Die Firewall-Freigabe für AirPlay galt nur für „private“ Netzwerke. Windows stuft WLANs aber oft als
  „öffentlich“ ein – dann ist der Name sichtbar (Bonjour hat eine eigene Freigabe), die Verbindung zu UxPlay
  wird aber blockiert. Jetzt gilt die AirPlay-Freigabe für alle Netzwerktypen.
- Hat man beim ersten Start von uxplay-windows die Windows-Nachfrage weggeklickt, legt Windows Sperr-Regeln
  für das Programm an – die gewinnen immer. AluPC ersetzt sie jetzt durch eine Freigabe.
- Nach dem Update fragt Windows beim Start **einmal** nach Admin-Rechten (Firewall-Freigabe fürs iPhone).
- Die CI prüft auf einem echten Windows: Freigabe für alle Profile, keine Sperr-Regel für UxPlay übrig.

### Neu in dieser Version (0.39.0)
**Linux installieren: „Sperrung nicht möglich“**
- Die Meldung kommt von der Paketverwaltung: Ein anderes Programm (Discover, automatische Updates) installiert
  gerade. Neu im Release: **AluPC-installieren.sh** – zusammen mit der `.deb` in einen Ordner laden, dann
  Rechtsklick → „Als Programm ausführen“ (oder im Terminal `bash AluPC-installieren.sh`). Es wartet, bis die
  Paketverwaltung frei ist (bis 15 Min.), repariert eine abgebrochene Installation und installiert AluPC.
  Ohne .deb daneben lädt es die neueste selbst.
- Auch AluPCs eigene Einrichtung (UxPlay, Fingerabdruck) wartet jetzt auf die Sperre statt abzubrechen.
- Geprüft: mit gehaltener Sperre wartet das Skript und installiert danach (lokal mit 0.38.0 und in der CI).

### Neu in dieser Version (0.38.0)
- **Linux: AirPlay „UxPlay hat sich beendet, Exit-Code 127“ behoben.** Die fertige Linux-Version gab gestarteten
  Programmen ihren eigenen Bibliotheksordner mit (LD_LIBRARY_PATH) – UxPlay lud dadurch AluPCs ältere GLib und
  brach mit „symbol lookup error“ ab. Jetzt bekommen UxPlay, kscreen-doctor, wmctrl & Co. die Bibliotheken des
  Systems. Nachgestellt und geprüft mit der echten Version 0.36 und UxPlay 1.68; die CI testet das künftig mit
  echtem UxPlay aus dem fertigen .deb.
- **Linux/Wayland: Bild-in-Bild erscheint direkt unten rechts** auf Monitor 1 (KDE legt es per KWin dorthin –
  Wayland erlaubt Programmen das nicht selbst).
- **Schnellfenster der Taskleiste:** öffnet jetzt auch unter Windows modern mit Kacheln **in der Bildschirmmitte**
  – wie unter Linux.

### Neu in dieser Version (0.37.0)
**Linux (KDE/Wayland)**
- **Spiegeln zeigte keine Fenster:** Läuft AluPC unter Wayland als X11-Programm und hat keine KDE-Freigabe für
  Aufnahmen, sieht die X11-Aufnahme nur alte X11-Programme – echte Wayland-Fenster fehlten. Jetzt versucht AluPC
  das gar nicht erst, sondern lässt KDE selbst spiegeln (kscreen-doctor): alle Fenster, Maus inklusive.
- **Programm spiegeln statt verschieben:** Unter KDE/Wayland nimmt AluPC das gewählte Fenster jetzt über KWin
  auf – es bleibt auf Monitor 1 und erscheint als Kopie auf Monitor 2 (auch verdeckt; nach Schließen/neuem
  Dokument findet es das Programm wieder). Die Reiter heißen jetzt „Spiegeln (Kopie)“ und „Verschieben (weg
  von Monitor 1)“. Braucht die KDE-Freigabe, die das .deb einrichtet.
- **Maus auf Monitor 2:** KDE erlaubt unter Wayland keinem Programm, die Maus festzuhalten. Mit der Sitzung
  „Plasma (X11)“ beim Anmelden hält AluPC sie auf Monitor 1 (Hinweis im Setup).

### Neu in dieser Version (0.36.0)
- **Behoben: Statt „AirPlay bereit“ erschien manchmal ein offenes Browserfenster auf Monitor 2.** AluPC hat das
  iPhone-Fenster über den Titel gesucht – und jedes Fenster genommen, in dessen Titel „AluPC“ vorkam (z. B. die
  Handy-Steuerung im Browser oder die GitHub-Seite). Jetzt zählt nur noch UxPlays eigenes Fenster oder ein Fenster,
  das **genau** so heißt; Browser, Explorer, Editoren und AluPC selbst sind ausgeschlossen – auf Windows, unter
  Linux und im KWin-Skript (KDE).

### Neu in dieser Version (0.35.0)
**Flüssig und sparsam – auch auf schwachen PCs**
- Animierte Seiten zeichnen bis zu **8× schneller**: Leuchtschrift, Schriftgrößen und unbewegte Hintergründe
  werden einmal berechnet und dann nur noch kopiert (Neon: 70 → 13 ms pro Bild, Synthwave: 74 → 10 ms).
  Gemessen: Neon auf Monitor 2 vorher über 100 % eines Prozessorkerns, jetzt ~15 %.
- **Leistung** (Setup → Darstellung): Automatisch · Flüssig · Sparsam. „Automatisch“ erkennt schwache PCs
  (≤ 4 Kerne) und zeichnet Animationen dann mit 15 statt 30 Bildern pro Sekunde; „Sparsam“ schaltet auch die
  Übergänge in der App ab.
- Jede Animation misst ihre Zeichenzeit und wird von selbst langsamer, wenn der PC nicht hinterherkommt.
- Im Hintergrund: Fortschrittsring lief unsichtbar mit 60 Bildern/s weiter (behoben); AirPlay „immer bereit“
  fragt unter Linux die Fensterliste nur noch alle 5 s ab.
- Leerlauf, Uhr, Text, Timer: 2–3 % eines Kerns.

### Neu in dieser Version (0.34.0)
**AirPlay: einfach bereit**
- Keine Einstellungen mehr für Name und Code: AirPlay heißt einmalig und fest **„AluPC“**, ohne Code, und ist
  immer bereit (fremde UxPlay-Autostarts übernimmt AluPC weiterhin). Fenster „Handy“ zeigt nur noch
  „‚AluPC‘ wählen“; die AirPlay-Einstellungen im Setup sind weg.

**Handy-Steuerung: Design-Update**
- Fließende Farbwolken im Hintergrund, schimmerndes Logo, pulsierender Verbunden-Punkt.
- Karten fliegen beim Tab-Wechsel nacheinander ein; in der unteren Leiste gleitet ein Leuchtpunkt zum Tab.
- Knöpfe mit Tipp-Welle und federndem Druck, aktive Kacheln leuchten sanft; Meldungen gleiten hoch.
- Respektiert „Bewegung reduzieren“ am Handy.

**App: mehr Animationen**
- Seitenwechsel blenden weich ein, Kacheln fliegen beim Öffnen nacheinander ein, Bereiche klappen animiert
  auf und zu, das Schnellfenster der Taskleiste ploppt sanft auf.

### Neu in dieser Version (0.33.0)
- **Text live schreiben:** Beim Text anzeigen (Kachel „Text“ am PC und Handy → Senden → Text) gibt es den
  Schalter **„Live“**. Dann erscheint jeder getippte Buchstabe sofort auf Monitor 2 – auch Löschen. Der Text
  wird dabei nur ausgetauscht (kein Flackern, keine Überblendung). Am PC wird „Anzeigen“ zu „Fertig“; der
  Schalter bleibt gespeichert, der fertige Text landet in „Zuletzt“.

### Neu in dieser Version (0.32.0)
**AirPlay: Name und Code gelten jetzt immer**
- Ursache für „iPhone zeigt den normalen UxPlay-Namen und fragt nicht nach dem Code“: Ein UxPlay, das nicht
  AluPC gestartet hat (z. B. uxplay-windows mit eigenem Autostart), lief mit Standardname und ohne Code.
  AluPC hat es bisher erst beendet, wenn man in AluPC auf AirPlay klickte.
- Neu **„Immer bereit“** (Standard, Setup → Handy & Kamera → AirPlay): AluPC startet UxPlay beim Start selbst
  im Hintergrund – mit **deinem Namen und Code** – und schaltet fremde UxPlay-Autostarts ab (Windows:
  Autostart-Eintrag, Autostart-Ordner, Aufgabenplanung; Linux: ~/.config/autostart, systemd). Dateien werden
  nur umbenannt („.aus-durch-AluPC“), also umkehrbar.
- **Verbindet sich ein iPhone, schaltet Monitor 2 von selbst aufs iPhone-Bild** („Bei Verbindung sofort auf
  Monitor 2“, abschaltbar).
- Windows: Name/Code landen bei jeder Änderung sofort in der Einstellungsdatei von uxplay-windows – auch wenn
  AirPlay gerade nicht läuft.
- Geprüft unter Linux mit echtem UxPlay 1.68: vorher „UxPlay@Rechner“ ohne Code im Netz, danach nur noch der
  AluPC-Name mit Code.

### Neu in dieser Version (0.31.0)
**Neues Schnellfenster in der Taskleiste**
- Klick aufs AluPC-Symbol öffnet statt der langen Liste ein gestaltetes Schnellfenster: Live-Bild von Monitor 2
  mit Zustand, Schalter (Standbild, Schwarz, Schoner, Mini-Bild), Kacheln zum Zeigen (Spiegeln, Erweitern,
  Kamera, Text, iPhone, Handy, Timer, Zeichnen), Weiter/Zurück bei Ablauf & Co., bis zu 6 Szenen, Ton-Regler
  (wenn etwas mit Ton läuft) und AluPC öffnen / Sperren / Beenden. Hell und dunkel, passend zur App.
- Schalter lassen das Fenster offen, Aktionen schließen es; Esc, Klick daneben oder nochmal aufs Symbol = zu.
- Rechtsklick zeigt weiter das klassische Menü – jetzt mit Abschnitten und „Text …“ (unter KDE zeichnet
  Plasma dieses Menü selbst).
- Linux: unter X11 öffnet es am Mauszeiger; unter Wayland bestimmt KWin die Position (unten rechts).

**Linux geprüft – mit echtem UxPlay 1.68 (wie in Kubuntu 24.04)**
- Name und Code kommen an (per avahi im Netz sichtbar), Umbenennen im Betrieb wirkt sofort, ein altes
  UxPlay wird beendet.
- Behoben: fälschliche Meldung „anderes AirPlay-Programm lässt sich nicht beenden“, obwohl es beendet wurde.

### Neu in dieser Version (0.30.0)
- **Text anzeigen am PC – wie am Handy:** neue Kachel **„Text“** auf der Startseite. Text eintippen,
  „Anzeigen“ (oder Strg+Enter) – steht groß auf Monitor 2. Die letzten Texte (auch vom Handy gesendete)
  sind als „Zuletzt“ antippbar und über den Pfeil der Kachel mit einem Klick wieder da.
- **Neue Szene → Filter „✦ Animiert“:** zeigt alle Vorlagen mit dauerhafter Bewegung (Laufschrift, Konfetti,
  Neon-Flackern, Synthwave, Glitch, Equalizer …) – Seiten und Szenen. Vorschaubilder tragen ein
  „✦ ANIMIERT“-Schild; auch die Suche nach „animiert“ findet sie.

### Neu in dieser Version (0.29.0)
**AirPlay-/UxPlay-Einstellungen greifen zuverlässig**
- Ein übrig gebliebenes UxPlay (z. B. nach einem Absturz) wird jetzt auch **unter Linux** beendet. Vorher lief
  es weiter, belegte die Ports – das iPhone sah weiter den alten Namen, AluPCs neues UxPlay startete nicht.
- Lässt sich ein fremdes UxPlay nicht beenden (z. B. mit Adminrechten gestartet), sagt AluPC das jetzt klar.
- Windows: Liegt eine vorrangige Einstellungsdatei von uxplay-windows unter ProgramData, schreibt AluPC Name
  und Code auch dort hinein (bzw. meldet, dass sie schreibgeschützt ist).
- Name geändert, während AirPlay läuft: AluPC sucht das iPhone-Fenster jetzt unter dem **neuen** Namen
  (vorher blieb es dann auf Monitor 1).
- „Randlos im Vollbild“ wirkt jetzt auch unter KDE (aus = maximiert statt Vollbild).
- Nach einem Neustart wegen geänderter Einstellungen beendet sich UxPlay wieder, wenn AirPlay aus ist.
- Fenster „Handy“ zeigt, womit UxPlay **wirklich** läuft: „Läuft als „Name“ · Code …“.

### Neu in dieser Version (0.28.0)
**Eigene Bereiche auf der Startseite**
- Startseite anpassen → Reiter **„Bereiche“**: eigene Bereiche anlegen (z. B. „Party“), umbenennen, sortieren,
  löschen (Kacheln rutschen in den ersten Bereich, nichts geht verloren).
- **Jede Kachel** – auch Spiegeln, Kamera, AirPlay … – lässt sich in jeden Bereich verschieben
  (Reiter „Kacheln“ → „Bereich der Kachel“).
- Bereiche **einklappen**: Klick auf die Überschrift. Eingeklappt zeigt sie ihre Kacheln als Mini-Symbole;
  Zustand bleibt gespeichert. Rechtsklick: Umbenennen · Alle ein-/ausklappen · Startseite anpassen.

**Design**
- Neue Bereichs-Überschriften mit Anzahl und Linie; Kacheln sind in allen Bereichen gleich breit.
- „Startseite anpassen“ aufgeräumt in drei Reiter: Kacheln · Bereiche · Texte.

### Neu in dieser Version (0.27.0)
**Weiterschalten bei Seiten mit mehreren Punkten**
- Nicht mehr nur der Ablauf: auch **Tabelle / Line-up, Termine, Abstimmung / Quiz** (Lösung aufdecken),
  **Siegerehrung** (Platz 3 → 2 → 1 aufdecken), **Pro & Contra** (Zeile für Zeile) und **Willkommen Gäste**.
- Steuern über **◀ ▶ in der Seitenleiste** (unter dem Monitor-2-Bild, mit Stand wie „Punkt 2/4“), die
  Handy-Seite (Karte „Punkte“), Tastenkürzel und Kacheln („Weiter“ / „Zurück“). Klappt auch in Szenen.

**Animationen**
- Punkte, Zeilen und Namen fliegen beim Anzeigen nacheinander ein; die Markierung **gleitet** zum nächsten Punkt.
- Quiz: Antworten ploppen auf, beim Aufdecken verblassen die falschen und die richtige hüpft.
- Siegerehrung: Podeste wachsen nacheinander hoch. Große Zahl: **zählt hoch**. Willkommen, Zitat,
  Ankündigung, Danke, Stichwort, Schlagzeile: Titel und Text gleiten weich herein.
- Vorschaubilder zeigen immer das fertige Bild.

### Neu in dieser Version (0.26.0)
- **AirPlay-Name wird übernommen:** Name und Code stehen in Setup und im Fenster „Handy“. Beide haben beim
  Speichern bisher *alle* Werte geschrieben – ein noch offenes Fenster setzte so den alten Namen zurück. Jetzt
  speichert jedes Feld nur sich selbst, beide Stellen zeigen sofort den neuen Stand, und läuft AirPlay gerade,
  startet es mit dem neuen Namen neu. Wer bewusst „AluPC“ einträgt, behält den Namen auch nach „Einrichten“.
- **Mehrere Bildschirmschoner auf der Startseite:** Startseite anpassen → „Bildschirmschoner“ → Stil wählen.
  Beliebig viele, jeder als eigene Kachel; Klick startet ihn, anderer Schoner wechselt, nochmal = aus.

### Neu in dieser Version (0.25.0)
- **AirPlay ohne iPhone:** Solange kein iPhone verbunden ist, zeigt Monitor 2 nur noch schlicht **„AirPlay bereit“**
  (schwarz, kleines Symbol, Name und ggf. Code) statt der großen Anleitung. Einstellbar unter
  Setup → Handy & Kamera → AirPlay → „Ohne iPhone“: „AirPlay bereit“ · Schwarz · Anleitung.
- **Handy-Seite zoomt nicht mehr ungewollt:** Doppeltippen und Zwei-Finger-Gesten vergrößern die Seite nicht mehr
  (iPhone ignoriert die alte Sperre), Zeichnen und Touchpad bleiben stabil.

### Neu in dieser Version (0.24.0)
- **Vorlagen nach Kategorien geordnet:** In „Neue Szene“ stehen bei „Alle“ die Vorlagen jetzt sortiert unter
  Überschriften (Style · Party & Event · Präsentation · Info · Zeit) mit Anzahl. Filter-Knöpfe und Suche wie bisher.
- **Bildschirmschoner in Gruppen:** Stil-Auswahl gegliedert in Uhr · Text · Natur · Farben & Licht · Tech · Eigenes,
  mit kurzen Namen.

### Neu in dieser Version (0.23.0)
- **Vorlagen nur beim Anlegen einer Szene:** Kachel „Vorlagen“ entfernt. **Szenen → „Neue Szene“** öffnet die
  Auswahl: „Leer“ oder Vorlage · Text eintragen · „Weiter“ → Szenen-Editor → Speichern. Echte Vorschaubilder.
- **Kurze Texte überall:** Kacheln, Menüs, Setup, Dialoge und Meldungen in Stichpunkten statt Sätzen
  (Details stehen in den Tooltips).
- Design: Setup-Bereiche ohne abgeschnittene Texte, „&“ in Knöpfen richtig dargestellt, leere Szene mit Plus.

### Neu in dieser Version (0.22.0)
**AirPlay repariert**
- Das AluPC-Fenster auf Monitor 2 hat sich alle paar Sekunden selbst wieder „ganz nach vorne“ geholt und dabei
  das iPhone-Bild verdeckt (Windows: „immer oben“, KDE: „über anderen halten“). Jetzt gibt AluPC bei AirPlay den
  Vordergrund ab, das iPhone-Fenster bekommt ihn (auch unter KDE), und sobald es da ist, blendet sich der
  Warte-Bildschirm aus. Trennt sich das iPhone, ist der Warte-Bildschirm wieder da.
- Behoben: Nach dem ersten Verbinden wurde das iPhone-Fenster bei einer neuen Verbindung nicht mehr richtig
  platziert (Programmfehler in der Fenster-Verfolgung seit 0.18).

**Vorlagen statt fertiger Szenen**
- Vorlagen legen keine Szenen mehr an. „Jetzt zeigen“ zeigt die Vorlage direkt auf Monitor 2 (live, ohne
  Speichern). **„Als eigene Szene anlegen …“** öffnet den Szenen-Editor mit der Vorlage – anpassen, dann
  speichern. Auf der Szenen-Seite: **„Neue Szene aus Vorlage …“** und „Leere Szene“.

**Design**
- **Kleines Fenster:** unter ca. 1000 px Breite schmale Seitenleiste nur mit Symbolen (Monitor 2 als kleines
  Live-Bild), weniger Rand, Kacheln passen sich an (bis zu einer Spalte), Statuskarte gestapelt, Schnellschalter
  als Symbole, Setup-Bereiche als Symbolleiste. AluPC lässt sich jetzt bis ca. 480 px schmal machen.
- **Gleiches Aussehen unter Windows und Linux:** AluPC bringt seine Schriften mit (Inter und JetBrains Mono,
  freie Lizenz SIL OFL) und nutzt überall denselben Stil – vorher je nach System Segoe UI bzw. DejaVu Sans.
  Nur die Fensterrahmen (Titelleiste) kommen weiterhin vom Betriebssystem.

### Neu in 0.21.0 (nicht einzeln veröffentlicht, in 0.22.0 enthalten) – Design-Karten statt Schul-Vorlagen
- **12 neue Design-Karten** für alles Mögliche: **Neon-Schild** (leuchtet und flackert), **Glitch** (Cyberpunk),
  **Synthwave** (80er-Sonnenuntergang mit Raster), **Poster**, **Minimal**, **Spotlight** (wandernder
  Scheinwerfer), **Now Playing** (Musik-Karte mit Equalizer), **LIVE**-Overlay, **Versus** (Duell/Gaming),
  **Link-Karte** mit QR-Code, **Coming soon** und **Glas-Karte**. Alle animiert und mit eigenem Text.
- **9 neue Szenen:** Stream-Overlay (LIVE + Kamera), Stream startet gleich, Partynacht, Musik läuft,
  Gaming-Duell, Retro-Abend, Link teilen, Präsentation startet, Kamera + Neon-Titel.
- **Entfernt:** Vorlagen für Lehrer (Arbeitsauftrag, Regeln, Gruppeneinteilung, Hausaufgaben,
  Stimmungsbarometer, Türschild, Speiseplan, Stillarbeit) und die dazugehörigen Szenen. Beispieltexte ohne
  Schulbezug. Gespeicherte Szenen mit einer entfernten Vorlage zeigen weiterhin Titel und Text.
- Neue Kategorien: Style, Party & Event, Präsentation, Info, Zeit.

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
