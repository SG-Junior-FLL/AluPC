## AluPC – Monitor 2 steuern (Kubuntu & Windows 11)

### Downloads
| System | Datei | Hinweis |
|---|---|---|
| **Windows 11** | `AluPC-Setup-….exe` | Installer (Startmenü, Deinstallation) |
| Windows 11 | `AluPC-windows-portable-….zip` | ohne Installation: entpacken, `AluPC.exe` starten |
| **Kubuntu / Ubuntu** (22.04, 24.04 und neuer) | `alupc_…_amd64.deb` | `sudo apt install ./alupc_…_amd64.deb` – danach im Startmenü |
| Linux (x86_64) | `AluPC-linux-x86_64-….tar.gz` | ohne Installation: entpacken, `AluPC/AluPC` starten |

### Neu in dieser Version (0.115.0)
- **Anmeldeseite (Windows):** Beim Test kamen Namensfragen an, Port 80 aber nicht bzw. nur sehr langsam.
  - Browser versuchen zuerst HTTPS (Port 443) – das lief bisher ins Leere und dauerte. Jetzt lehnt AluPC 443
    sofort ab → Browser und Handy-Prüfung nehmen gleich HTTP.
  - Hotspot-Fenster zeigt jetzt: „Port 80 am PC: … ms“ (AluPC ruft seine Anmeldeseite selbst ab), Warnung bei
    fremder Firewall (z. B. Antivirus) und bei „Alle eingehenden Verbindungen blockieren“ in Windows.
    Geht es am PC, aber nicht am Handy, blockiert etwas dazwischen – die Zeile sagt, was.
- Ehrlich: Ob die Anmeldeseite jetzt auf deinem PC kommt, hängt davon ab, was dort blockiert – das zeigt die
  neue Zeile im Hotspot-Fenster. Geprüft in CI (Windows mit nachgebautem Hotspot) und lokal.

### Neu in Version 0.114.0
- **Anmeldeseite immer erreichbar:** Android öffnet sie oft nur beim ersten Verbinden von selbst (danach nur die
  Benachrichtigung „Im WLAN anmelden“). Jetzt geht immer: im Browser die Hotspot-Adresse eingeben (z. B.
  192.168.137.1) → Anmeldeseite. Monitor 2 zeigt die Adresse unter dem WLAN-Code („Nicht offen? …“).
- **Anmeldeseite bleibt offen:** Windows schaltete den Hotspot im Energiesparmodus ab, wenn kurz kein Gerät
  verbunden war – jetzt abgeschaltet. Die Internet-Sperre wird nur noch geändert, wenn nötig (vorher alle 2 s neu
  gesetzt = jedes Mal eine Netzwerk-Meldung).
- **„AluPC steuern“ immer am PC bestätigen** – auch wenn das Handy schon mal erlaubt war.
- **Vergrößern repariert:** zeigte nur Schwarz. Jetzt Live-Bild bildschirmfüllend (auch auf „Start“), mit zwei
  Fingern zoomen und verschieben, fester „Schließen“-Knopf.
- **Keine eigene Kachel „Handy-Steuerung“ mehr** – steckt im Hotspot (WLAN-Code → Anmeldeseite → „AluPC steuern“).
- Geprüft: Anmeldeseite Linux 26/26 (neu: Hotspot-Adresse → Anmeldeseite), Handy-Seite im echten Browser
  (Vergrößern, Zoom, Schließen, Bestätigen), alle Tests, Einstellungen 21/21, Ton 11/11, Rundgang 55 Bilder.
- Ehrlich, nicht prüfbar ohne dein Handy: ob die Anmeldeseite jetzt dauerhaft offen bleibt.

### Neu in Version 0.113.0
- **Videosteuerung am Handy:** Stelle per Leiste wählen (mit Zeit), −30/−10/+10/+30 s, Abspielen/Pause,
  Tempo 0,5×–2×, „Von vorn“, „Wiederholen“ an/aus. Neu: **„Weiterschauen“** – die zuletzt geschauten Videos mit
  gemerkter Stelle; antippen = auf Monitor 2 genau dort weiter.
- **Auch am PC:** Medienleiste → „Mehr“ (±30 s, Tempo, Wiederholen, Von vorn, Weiterschauen); Medien-Menü →
  „Weiterschauen“.
- **Ton am PC (Handy und System-Seite):** Lautsprecher und Mikrofon getrennt – genaue Lautstärke, stumm an/aus und
  **Gerät wählen** (z. B. Kopfhörer statt Lautsprecher, Headset statt eingebautem Mikrofon).
  - Linux: über pactl (PulseAudio/PipeWire) – echt geprüft mit 2 virtuellen Lautsprechern und 2 Mikrofonen.
  - Windows: über Core Audio (wie Windows' eigene Regler) statt Medientasten – Lautstärke jetzt genau statt in
    2-%-Schritten. Gerät wechseln über dieselbe Schnittstelle wie die Sound-Einstellungen von Windows. Alle
    Windows-Ton-Aufrufe laufen in einem eigenen Thread (sonst konnte AluPC abstürzen – in CI gefunden und behoben).
- **Anmeldeseite (Hotspot-Fenster):** zeigt je Handy, welche Namen es gefragt hat, und einen Hinweis:
  „Handy nutzt eigenes DNS (…)“ oder „Handy prüft – aber nichts kam auf Port 80 an“.
- Geprüft: echtes Testvideo (Stelle, Tempo, Wiederholen, Von vorn, Weiterschauen), Handy-Seite im echten Browser
  (jeder Knopf schickt den richtigen Befehl, keine Fehler), Ton mit echtem PulseAudio 11/11.
- Ehrlich, nicht geprüft: Ton unter Windows mit echten Geräten (der CI-Rechner hat keine Soundkarte – geprüft ist
  nur, dass Core Audio startet und nicht abstürzt); Anmeldeseite mit echtem Handy weiterhin offen.

### Neu in Version 0.112.0
- Hotspot-Fenster zeigt unter „Geräte im WLAN“, wo die Anmeldeseite hakt: Port 80 (AluPC direkt oder
  Weiterleitung), ob die Internet-Sperre wirklich aktiv ist (Zustand von Windows) und die letzte Prüfung eines
  Handys auf Port 80. Auch in „Diagnose kopieren“ (mit den letzten Anfragen).
- Anfragen „HEAD“ werden jetzt beantwortet (manche Handys prüfen „bin ich im Internet?“ nur so).
- Ehrlich: Die Anmeldeseite kam beim Test (Windows + Android) noch nicht – DNS kommt an, die Prüfung auf Port 80
  nicht. Diese Version ist zum Finden der Ursache; ein Handy mit „Privatem DNS“ (eigener Anbieter) kann die
  Erkennung verhindern.

### Neu in Version 0.111.0
- **Windows: WLAN verschwand („nicht verfügbar“) – behoben.** 0.109/0.110 hielten im Notfall den Windows-Dienst
  „Internetverbindungsfreigabe“ an (beim Start bzw. als „Selbstreparatur“). Auf echten PCs beendet das den
  Mobilen Hotspot. AluPC fasst diesen Dienst jetzt nie mehr an; zusätzlich prüft AluPC nach dem Einrichten der
  Anmeldeseite, ob der Hotspot noch läuft, und startet ihn sonst wieder.
- **Taskleisten-Symbol wieder direkt in der Taskleiste:** AluPC holte es nur einmal pro Programmpfad nach vorne –
  nach einem Update legt Windows aber einen neuen, versteckten Eintrag an. Jetzt bei jedem Start.
- Geblieben: Anzeige je Gerät im Hotspot-Fenster, Port 80 direkt, Firewall-Wächter, echte Hotspot-Adresse.
- Ehrlich, nicht geprüft: echter Mobiler Hotspot mit echtem Handy. Ob die Anmeldeseite jetzt kommt, zeigt das
  Hotspot-Fenster in der Zeile des Handys.

### Neu in Version 0.110.0
- **Windows: Anmeldeseite repariert sich selbst.** Ist ein Handy seit 20 s im WLAN, aber keine einzige
  Namensfrage kam bei AluPC an (Handys fragen Windows statt AluPC), übernimmt AluPC Port 53 im laufenden Betrieb –
  ohne neues „Ja“. Läuft der Hotspot danach nicht mehr, startet AluPC ihn wieder.
- **Hotspot-Fenster zeigt je Gerät, wo es hängt:** „DNS ✗ (fragt Windows statt AluPC)“, „DNS ✓ · Anmeldeseite noch
  nicht“ oder „Anmeldeseite ✓“.
- Windows: AluPC lauscht selbst auf Port 80 der Hotspot-Adresse (sieht so jedes Handy); echte Hotspot-Adresse aus der Registry (statt fest 192.168.137.1); Firewall-Sperre für AluPC wird alle
  20 s erneut entfernt (falls die Windows-Frage später weggeklickt wird); IP-Hilfsdienst (für Port 80) wird gestartet.
- Geprüft: Windows-CI mit nachgebautem Hotspot inkl. Selbstreparatur im Betrieb, alle Tests.
- Ehrlich, nicht geprüft: echter Mobiler Hotspot mit echtem Android-Handy. Kommt die Anmeldeseite nicht, zeigt
  das Hotspot-Fenster jetzt, an welcher Stelle – bitte die Zeile des Handys schicken.

### Neu in Version 0.109.0
- **Windows: Anmeldeseite repariert** (Handys bekamen Internet statt der Anmeldeseite):
  - Fragen die Handys Windows' eigenen Hotspot-DNS statt AluPC, gibt es keine Anmeldeseite (und Internet für
    alle). AluPC nimmt Port 53 jetzt genau auf der Hotspot-Adresse; geht das nicht, hält AluPC den Windows-Dienst
    „Internetverbindungsfreigabe“ kurz an, nimmt Port 53 und startet ihn wieder. Weiter nur ein „Ja“.
  - Wurde die Windows-Frage „Zugriff zulassen?“ für AluPC einmal weggeklickt, sperrte die Firewall die Handys.
    Diese Sperre für AluPC wird jetzt entfernt.
  - Klappt es trotzdem nicht, sagt AluPC das klar („Anmeldeseite ging nicht …“) statt still „an“ zu melden.
- **Windows: „Geräte im WLAN“ (Internet pro Gerät) war leer** – deutsches Windows schreibt „dynamisch“ statt
  „dynamic“. Geht jetzt in jeder Sprache.
- Unsichtbares WLAN mit unsichtbaren Zeichen (Windows) wieder entfernt. Unter Windows ist der Name sichtbar.
- „Diagnose kopieren“ zeigt jetzt „WLAN / Anmeldeseite“: wer Port 53 hatte, wo AluPC lauscht, wie viele
  Namensfragen ankamen, Geräte im WLAN – bitte schicken, falls es nicht geht.
- Fingerabdruck-Anmeldung (Windows): Finger muss nach einer Anmeldung erst abgehoben werden (sonst evtl. doppelt).
- Geprüft: Windows-CI mit nachgebautem Hotspot (Handy-Container: Anmeldeseite, Internet pro Gerät, Firewall-
  Sperre, Notweg mit angehaltenem Dienst), Linux 25/25, alle Tests.
- Ehrlich, nicht geprüft: echter Mobiler Hotspot mit echtem Android-Handy – bitte testen. Beim Notweg (Dienst
  angehalten) ist offen, ob „Internet pro Gerät“ danach noch geht.

### Neu in Version 0.108.0
- **AluPC ist jetzt ins System eingebunden** (Linux und Windows gleich; Einstellungen → Allgemein → „Im System“,
  an ab Werk, abschaltbar, wird bei Deinstallation/„Alle Daten löschen“ entfernt):
  - **Rechtsklick auf Bild, Video oder PDF → „Auf Monitor 2 zeigen“**, auf einen Ordner → „Als Diashow auf
    Monitor 2“. Dolphin (KDE) bzw. Explorer (Windows 11: unter „Weitere Optionen anzeigen“).
  - **Links `alupc://…`** steuern AluPC von überall (Browser-Lesezeichen, Verknüpfung, Stream Deck …):
    `alupc://standbild`, `alupc://schwarz`, `alupc://szene/Pause`, `alupc://naechste-szene` … Nur harmlose
    Befehle – nichts, was Programme startet, den PC sperrt oder ausschaltet.
  - Auch im Terminal: `alupc --zeigen Datei.pdf`. Läuft AluPC schon, geht alles an das laufende Programm.
- Geprüft: Rechtsklick-Befehl und Link kommen beim laufenden AluPC an (Linux echt; Windows in CI mit echter
  Registry und `start alupc://standbild`), Ein/Aus in den Einstellungen, alle Tests.
- Ehrlich, nicht geprüft: Anzeige im echten Dolphin/Explorer-Menü (kein KDE/Desktop hier) und ob Windows und
  Handys den Namen aus unsichtbaren Zeichen annehmen – das ging ohne echtes WLAN-Gerät nicht. Geht es nicht,
  „Unsichtbar“ ausschalten.

### Neu in Version 0.107.0
- **Das AluPC-WLAN ist kein Internet-WLAN mehr – Internet gibt es nur, wenn du es einem Gerät erlaubst.**
  - Standard (normaler Hotspot und Spiele-WLAN): kein Internet, kein Weg an der Anmeldeseite vorbei – auch nicht
    über IPv6 (unter Linux jetzt ausgeschaltet bzw. gesperrt). So bleibt das Anmeldefenster offen.
  - Hotspot-Fenster → **„Geräte im WLAN“**: jedes Gerät mit Name (von der Anmeldeseite), Adresse und MAC – Haken
    setzen = dieses Gerät darf ins Internet. Gilt für das Gerät, auch beim nächsten Mal.
- **Abstimmen nur noch übers WLAN** – wie alles andere: Monitor 2 zeigt den WLAN-Code, auf der Anmeldeseite
  erscheint „📊 Abstimmen“.
- **Fotos senden geht wieder:** „AluPC steuern“ → am PC erlauben → Foto. Geht die Kamera im Anmeldefenster nicht
  (manche Handys erlauben dort keine Dateien), steht auf der Seite, wie man in den Browser wechselt – dort ist das
  Handy dann schon erlaubt, ohne neue Frage am PC.
- **WLAN wieder unsichtbar** (Linux, Standard; abschaltbar im Hotspot-Fenster). Windows kann den Namen des
  Mobilen Hotspots technisch nicht verstecken.
- Geprüft vor der Auslieferung (echtes Netz, echter Browser):
  - Linux: 29/29 – Abstimmen übers WLAN, Foto senden mit Browser, Internet pro Gerät an/aus, IPv6 gesperrt,
    Handy aus anderem Netz bekommt überall 403 (auch Abstimmen).
  - Windows: dieselben Prüfungen mit nachgebautem Mobilen Hotspot.
- Ehrlich, nicht prüfbar ohne echte Geräte: ob iPad/iPhone/Android das Anmeldefenster von selbst öffnen, ob die
  Kamera im Anmeldefenster geht. Unter Windows sperrt „Internet pro Gerät“ die Namensauflösung je Gerät; die
  Weiterleitung selbst ist an, sobald mindestens ein Gerät Internet hat (Windows kann sie nicht je Gerät
  trennen) – ein Gerät ohne Haken kommt dann höchstens mit fest eingetragenen IP-Adressen raus.

### Neu in Version 0.106.0
- **Nur noch EIN Weg fürs Handy: das AluPC-WLAN mit Anmeldeseite.**
  - Steuern und Mitspielen geht nur aus dem AluPC-WLAN: ein QR-Code (WLAN) → Anmeldeseite → Mitspielen oder
    „AluPC steuern“ (am PC erlauben).
  - Der Server lehnt alles andere ab (Link, Router-WLAN, LAN → „Nur über das AluPC-WLAN“).
  - Entfernt: Link-QR-Codes, „vorhandenes WLAN“, der Schalter „nur über WLAN“, Adress-Auswahl.
  - „Handy-Steuerung“ startet das AluPC-WLAN und zeigt dessen QR-Code.
  - Abstimmungen bleiben per eigenem QR-Code (die steuern nichts).
- **Tetris statt Ballon:** jeder hat sein Feld, alle bekommen dieselben Teile in derselben Reihenfolge, es wird
  schneller – wer am längsten durchhält, gewinnt. Handy: ◀ ▶, drehen, schneller, fallen lassen.
- **Eigenes AluPC-Theme** (Standard): Logo-Blau → Indigo, unter Windows und Linux gleich.
  - Neu: „AluPC-Farben für den Desktop“ (KDE-Farbschema bzw. Windows-Akzentfarbe), mit „Zurück“.
- **Windows und Linux gleicher:**
  - Tastenkürzel gelten jetzt auch unter KDE überall (wie unter Windows).
  - Hotspot auf beiden mit Passwort und sichtbarem Namen (dasselbe WLAN per Abgleich).
  - „Anzeige-Einstellungen“-Knopf auf beiden.
- **Geprüft vor der Auslieferung:**
  - Neues Skript bedient jede Einstellung im Setup echt (gespeichert, zurückstellbar, wirkt) – Linux und Windows.
    Dabei gefunden und behoben:
    - Windows: Autostart ging nicht, wenn der „Run“-Eintrag in der Registry noch fehlte (neues Benutzerkonto).
    - Fette Texte auf Monitor 2 wurden manchmal abgeschnitten.
    - Ein altes Testfenster färbte das Theme um (nur Tests betroffen).
  - Anmeldeseite echt (Linux-Netz bzw. Windows-Internetfreigabe + Container-Handy):
    - Monitor 2 zeigt genau 1 QR-Code = WLAN (echter Decoder),
    - Anmeldeseite → mitspielen, „AluPC steuern“ → am PC fragen,
    - ein Handy aus einem anderen Netz bekommt überall 403.
    Dabei gefunden und behoben: Geräte außerhalb des WLANs wurden zur Anmeldeseite umgeleitet.
  - Tetris am Handy mit echtem Browser (Knöpfe bewegen/drehen/fallen lassen).
  - Tastenkürzel mit dem echten KDE-Dienst, KDE-Farbschema mit dem echten KDE-Werkzeug,
    Windows-Akzentfarbe in der Windows-Registry (setzen und zurück).
- Ehrlich, nicht prüfbar ohne echte Hardware:
  - echte WLAN-Karte, ob das Handy das Anmeldefenster von selbst öffnet,
  - die „Ja“-Abfrage (UAC),
  - wie Windows/KDE mit den neuen Farben aussehen.
  - Ohne WLAN-Karte (oder wenn der Hotspot nicht startet) gibt es jetzt keinen Handy-Zugang mehr.

### Neu in Version 0.105.0
- **Windows wie Linux: Spiele-WLAN wie ein Hotel-WLAN.** Windows nutzt jetzt denselben Weg wie Linux:
  - AluPCs eigener DNS beantwortet **jede** Namensfrage der Handys im Mobilen Hotspot
    (lauscht auf 192.168.137.1:53, der Windows-Hotspot-DNS bekommt dann nichts mehr),
  - jede Webseite (http) führt zur Anmeldeseite,
  - das Spiele-WLAN leitet **nichts ins Internet** weiter (Weiterleitung am Hotspot aus; der Wächter hält sie aus).
  - Keine Einträge mehr in der hosts-Datei (nur noch als Notlösung, falls Port 53 belegt ist – dann meldet
    AluPC „eingeschränkt“).
  - Beim normalen Hotspot bleibt das Internet an, nur die Prüf-Adressen führen zur Anmeldeseite.
- **Geprüft vor der Auslieferung, auch unter Windows:**
  - Neuer CI-Schritt baut den Mobilen Hotspot nach: echte Windows-Internetfreigabe mit 192.168.137.1 und
    Windows-DNS; das „Handy“ ist ein Windows-Container im Hotspot-Netz.
  - Durchgespielt mit dem echten AluPC und dem echten Administrator-Skript:
    - Handy-DNS → PC,
    - Android-/iPhone-Prüfung → Anmeldeseite,
    - Name → Mitspielen → im Spiel,
    - fremder DNS (8.8.8.8) und Internet per IP gesperrt,
    - nach dem Ausschalten alles wieder weg,
    - normaler Hotspot behält Internet.
- Ehrlich, weiterhin nicht prüfbar ohne echte Hardware:
  - die WLAN-Karte,
  - ob das Handy das Anmeldefenster von selbst öffnet,
  - die „Ja“-Abfrage (UAC).

### Neu in Version 0.104.0
- **Spiele-WLAN wie ein Hotel-WLAN (Linux), damit sich die Anmeldeseite wirklich öffnet:** Bisher zeigten nur
  einige Prüf-Adressen auf den PC – Handys mit eigener (verschlüsselter) Namensauflösung oder wenn der PC Internet
  hatte, gingen daran vorbei, und die Anmeldeseite kam nicht. Jetzt:
  - AluPC beantwortet **jede** Namensfrage aus dem Spiele-WLAN selbst (eigener kleiner DNS, unabhängig von
    NetworkManager),
  - **jede** Webseite (http) führt zur Anmeldeseite,
  - das Spiele-WLAN leitet **nichts ins Internet** weiter – so kommt kein Handy an der Anmeldeseite vorbei.
- **Mitspielen nur über das Spiele-WLAN und die Anmeldeseite:** Lobby, „Einsteigen“ und „QR groß“ zeigen keinen
  Link mehr, nur den WLAN-Code (läuft das WLAN nicht, steht dort der Grund). Der Server lässt nur Handys aus dem
  Spiele-WLAN beitreten. Abschaltbar unter „Spiele-WLAN …“.
- **Geprüft vor der Auslieferung:** neues Prüfskript spielt es echt durch – ein virtuelles Handy in einem eigenen
  Netz (wie im Hotspot), das echte AluPC und das echte Root-Skript: Android- und iPhone-Prüfung → Anmeldeseite,
  fremde DNS-Server abgefangen, Name → Mitspielen → Spielsteuerung (auch mit echtem Chromium), Mitspielen von außen
  abgelehnt, nach dem Ausschalten alle Regeln weg (17/17). Läuft jetzt bei jedem Build in der Linux-CI.
- Ehrlich: Ob das Handy-Betriebssystem das Anmeldefenster dann **von selbst** öffnet, lässt sich ohne echtes Handy
  und WLAN-Karte nicht prüfen (iPhone meist sofort, Android oft erst über die Meldung „Im WLAN anmelden“).
  Windows: in 0.104 noch der alte Weg (hosts-Datei) – seit 0.105 wie Linux.

### Neu in Version 0.103.0
- **PC steuern wie mit einer Kontroll-App:** System-Seite → Karte **„PC steuern“**: Lautstärke-Regler, Stumm, Musik
  (⏮ ⏯ ⏭), Desktop, Fenster wechseln, Bildschirmfoto und ein Feld **„Programm oder Befehl“** (wie Win+R, mit
  Vorschlägen aus den installierten Programmen). **Handy-Karte „PC“**: Lautstärke-Regler, Fenster klein/groß/schließen,
  **PC sperren**, **Programm öffnen** (nur aus der Liste der installierten Programme – keine freien Befehle vom Handy).
- **Zurücksetzen besser:** vorher automatisch eine **Sicherung** (Dokumente/AluPC-Sicherungen, nach dem Neustart wird
  gesagt, wo sie liegt – zurückholen über „Importieren“), auf Wunsch **Szenen, Startseite, Mediathek und Overlays
  behalten** (nur Einstellungen zurücksetzen).
- **Sync besser:** **„Prüfen“** (Ordner da? beschreibbar? Stand und AluPC-Version des anderen Systems), die Status-Karte
  zeigt, welches System zuletzt geschrieben hat, **Konflikt-Sicherungen zurückholen** („Sicherungen …“).
- **Alles durchgeprüft:** neues Rundgang-Skript öffnet jede Seite, jeden Setup-Bereich, alle Fenster, alle
  Monitor-2-Anzeigen und alle Spiele (läuft jetzt bei jedem Build in der CI mit). Dabei gefunden und behoben:
  - Szenen ohne „layout“ (z. B. aus alten Sicherungen) ließen die App beim Start abstürzen – werden jetzt repariert.
  - Handy: Beitreten zu einem Spiel konnte durch eine gleichzeitige Abfrage sofort wieder rückgängig gemacht werden.
  - Tipp-Rennen: Namen wurden von der Kugel verdeckt; Siegertreppchen: Texte überlappten bei niedrigem Podest.
- **README neu** (Übersicht mit Screenshots) und **Handbuch als PDF** mit allen Screens und ihrer Funktion
  (docs/AluPC-Handbuch.pdf).
- Ehrlich: Screenshots und Prüfungen laufen ohne echte Monitore, Kameras, Handys und WLAN-Karte; die PC-Steuerung
  (Lautstärke, Fenster, Sperren) ist nur mit nachgespielten Systembefehlen getestet.

### Neu in Version 0.102.0
- **Minispiele = eigenes WLAN:** Mit den Minispielen startet das Spiele-WLAN (einmal bestätigen: Linux Passwort,
  Windows „Ja“). Die Lobby zeigt dann **einen** Code: das WLAN. Scannen → das Handy öffnet die
  **WLAN-Anmeldeseite** wie im Hotel → **Name eingeben** → **Mitspielen** (gleich in der Spielsteuerung) oder
  **AluPC steuern** (Anfrage erscheint am PC: Erlauben/Ablehnen). Abschaltbar unter „Spiele-WLAN …“.
- **Spiele neu sortiert:** **Snake** (der Rand ist jetzt tödlich), **Tic-Tac-Toe** (neu: Team Rot ✕ gegen Team
  Blau ◯, das Team stimmt per Handy ab), **Pong**, **Ballon**, **Tipp-Rennen**, **Simon sagt**,
  **Schere, Stein, Papier**. Entfernt: Schätzen, Malen & Raten, Farb-Chaos, Tauziehen, Schnellster Finger, Quiz,
  Lichtrenner. Steuerfenster mit Symbolen und Anzeige, ob das Spiele-WLAN läuft.
- **„Alle Daten löschen“ repariert:** Nach dem Neustart holte der Dual-Boot-Abgleich die Einstellungen vom anderen
  System zurück – es sah aus, als wäre nichts gelöscht. Jetzt (Häkchen, Standard an) werden auch die abgeglichenen
  Einstellungen im Sync-Ordner gelöscht und der Abgleich bleibt aus, bis man ihn wieder einschaltet. Dateien, die
  beim Löschen noch blockiert sind, löscht der Neustart als Allererstes.
- **Sync-Seite neu:** Status-Karte (Verbunden / Aus / Ordner nicht erreichbar, letzter Abgleich), **Bereiche einzeln
  an/aus** (abgewählte werden weder geschickt noch übernommen), **Verlauf** der letzten Abgleiche, „Jetzt abgleichen“.
- **Design:** dezenter Farbschimmer im Hauptbereich, Logo in der schmalen Seitenleiste nicht mehr abgeschnitten.
- Ehrlich, nicht auf echter Hardware geprüft: ob Handys die Anmeldeseite von selbst öffnen (Linux und Windows), ob
  der Windows-Hotspot die Umleitung an die Handys weitergibt, der echte Dual-Boot-Abgleich nach dem Zurücksetzen.

### Neu in Version 0.101.0
- **WLAN-QR-Code auf Monitor 2:** Hotspot-Kachel → Pfeil → „WLAN-QR-Code auf Monitor 2“ (oder im Hotspot-Fenster
  „QR auf Monitor 2“). Groß, mit Name und Passwort – Handys scannen ihn von dort.
- **Minispiele ohne WLAN-QR-Code:** Lobby auf Monitor 2 und „QR groß“ zeigen nur noch den Spiel-Code.
- **Anmeldeseite auch beim normalen Hotspot:** WLAN-QR scannen → das Handy öffnet „Im WLAN anmelden“ →
  **Mitspielen** (wenn Minispiele laufen) oder **AluPC steuern** (Freigabe am PC).
- Linux: Umgeleitet werden nur noch Anfragen an den PC selbst – normales Surfen über den Hotspot bleibt unberührt.
- Ehrlich: mit echten Handys noch nicht ausprobiert.

### Neu in Version 0.100.1
- **„Alle Daten löschen“ unter Windows repariert:** Es blieben `absturz.log` und der Ordner
  `%APPDATA%\AluPC` übrig („wird von einem anderen Prozess verwendet“) – AluPC hielt das eigene
  Absturz-Protokoll offen. Jetzt wird es vor dem Löschen geschlossen; klemmt noch eine Datei (z. B. vom
  eingebauten Browser), versucht AluPC es einige Male erneut.

### Neu in Version 0.100.0
- **WLAN-Anmeldeseite jetzt auch unter Windows** – Linux und Windows machen es gleich: Spiele-WLAN starten →
  einmal bestätigen (Linux: Passwort, Windows: „Ja“ für Administrator) → Handys, die sich verbinden, bekommen
  „Im WLAN anmelden“ mit **Mitspielen** und **AluPC steuern** (Freigabe am PC). Nach dem Ausschalten (oder wenn
  AluPC endet) räumt ein Wächter alles wieder auf.
- Ist Port 80 unter Windows schon von einem anderen Programm belegt (z. B. ein Webserver), sagt AluPC das klar
  („Port 80 ist schon belegt …“) – die Handys nehmen dann den QR-Code.
- **Anmeldeseite auch ohne Internet am PC:** Die Prüf-Adressen der Handys (Android, iPhone, Xiaomi, Huawei …)
  beantwortet jetzt der PC selbst (Linux: Eintrag für den Hotspot, Windows: hosts-Datei).
- **Besserer Dual-Boot-Abgleich:**
  - Zusammenführen **bis auf einzelne Einträge**: Szene unter Windows angelegt, Kachel unter Linux → beides bleibt.
    Nur wenn genau dieselbe Einstellung auf beiden Seiten verschieden geändert wurde, gewinnt die eigene (Sicherung
    der anderen liegt daneben).
  - **Bilder, Videos, Musik** funktionieren auf beiden Systemen: Pfade werden laufwerksneutral gespeichert
    (C:\Bilder ↔ /media/…/Bilder). Dateien, die nur auf einem System liegen (z. B. Linux-Home), kopiert AluPC
    im Hintergrund in den Sync-Ordner (Unterordner „Dateien“, bis 500 MB pro Datei).
  - Mehr wird abgeglichen: **Sprachsteuerung** (Startwörter, eigene Befehle – ohne Mikrofon), **Minispiele, Hotspot,
    Spiele-WLAN**, Begrüßung, Wetter, Glücksrad, Umfrage, Whiteboard, Finger-Kürzel, Video-Positionen, Start der App.
- Ehrlich, nicht auf echter Hardware geprüft: ob Handys die Anmeldeseite wirklich von selbst öffnen (Linux und
  Windows), ob der Windows-Hotspot die hosts-Datei an die Handys weitergibt, die „Ja“-Abfrage. Windows Defender kann
  hosts-Änderungen melden. In der Windows-CI läuft das Skript echt (hosts, Port 80 → AluPC, Aufräumen).
  Unter Windows bleibt das WLAN sichtbar und braucht ein Passwort (geht dort nicht anders).

### Neu in Version 0.99.0
- **Unsichtbare WLANs:** Hotspot und Spiele-WLAN senden ihren Namen nicht mehr (Linux). Verbinden nur per
  **WLAN-QR-Code** oder durch Eintippen von Name + Passwort. Abschaltbar im Hotspot-Fenster.
  Windows: der Mobile Hotspot kann seinen Namen nicht verstecken – dort bleibt er sichtbar (Hinweis im Fenster).
- **Aussehen wie das System (Windows + Linux):** neue Akzentfarbe **„Wie das System“** (jetzt Standard) –
  übernimmt die Farbe aus Windows (Personalisierung → Farben), KDE Plasma oder GNOME. Wechselt man im System
  Hell/Dunkel oder die Farbe, zieht AluPC nach ein paar Sekunden mit. Wer bisher Blau (alter Standard) hatte,
  bekommt einmalig die Systemfarbe; andere Farben bleiben.
- **Windows-Titelleiste passend:** dunkel im dunklen Design, unter Windows 11 in der App-Hintergrundfarbe.
- Hotspot-Fenster aufgeräumt: Status „AN / AUS“, kürzere Hinweise, Eingabefelder nicht mehr gequetscht.
- Ehrlich: Unsichtbares WLAN, Titelleiste und Systemfarbe aus Windows/GNOME sind nur im Test nachgespielt, nicht
  auf echter Hardware geprüft. Unter Linux zeichnet KWin/GNOME die Titelleiste selbst (folgt dem System-Design).

### Neu in Version 0.98.0
- **Handy freigeben statt Code eintippen:** Auf der Handy-Seite (und der WLAN-Anmeldeseite → „AluPC steuern“)
  gibt es jetzt **„Am PC freigeben lassen“**. Am PC erscheint eine Benachrichtigung und die Frage **„Erlauben /
  Ablehnen“**. Erlaubte Geräte steuern ab dann ohne Code (gemerkt im Handy-Browser; am PC nur als Prüfsumme
  gespeichert). Setup → Handy & Kamera zeigt die freigegebenen Geräte und kann alle Freigaben löschen.
  Der 6-stellige Code funktioniert weiterhin.
- Ehrlich: mit nachgespielten Handy-Anfragen getestet, nicht mit echten Handys. Löscht das Handy seine
  Browserdaten (oder privater Modus), muss es neu angefragt werden.

### Neu in Version 0.97.0
- **Desktop-Widgets entfernt** (die dauerhaft eingeblendeten Karten auf Monitor 1) – waren anders gemeint.
- **Programme auf der Startseite:** Startseite anpassen → **„Programm …“**: installiertes Programm aus der Liste wählen
  (mit Suche) → Kachel im neuen Bereich **„Programme“**. Ein Klick startet es. Gilt für das System, auf dem du es
  hinzufügst (Dual-Boot: auf dem anderen System dort das Programm wählen).
- **Hotspot-Kachel** (Bereich Handy): Klick = eigenes WLAN an/aus, Pfeil = Name, Passwort und WLAN-QR-Code.
- **Spiele-WLAN** (Minispiele-Fenster → „Spiele-WLAN …“), getrennt vom normalen Hotspot:
  - Linux: offen (ohne Passwort) – Handy tippt das WLAN an und bekommt sofort **„Im WLAN anmelden“**: eine
    Seite mit **„Mitspielen“** und **„AluPC steuern“** (nur mit dem Zugangscode vom PC).
  - geht **automatisch aus, wenn die Minispiele beendet werden** (auch beim Beenden von AluPC).
  - Die Anmeldeseite braucht unter Linux beim Start einmal das PC-Passwort (Weiterleitung von Port 80).
- Ehrlich: nicht mit echter Hardware getestet. Die Anmeldeseite ist mit nachgespielten Handy-Anfragen geprüft
  (Android/iPhone fragen beim Verbinden fremde Adressen ab → Weiterleitung). Sie erscheint nur, wenn das Handy
  diese Adressen auflösen kann – also wenn der PC selbst Internet hat (z. B. per Kabel). Unter Windows gibt es
  keine Anmeldeseite (Windows lässt das nicht umleiten) – dort helfen die QR-Codes.

### Neu in Version 0.96.0
- **QR-Code war nicht scannbar – behoben:** In der App war er nur 84 px groß mit zu schmalem weißen Rand (2 statt
  4 Module) – auf dunklem Hintergrund erkennen viele Handy-Kameras das nicht. Jetzt: Rand nach Norm, jedes Modul
  gleich viele ganze Pixel, Code steht still (wippte vorher in der Lobby), in der App größer und per Klick
  bildschirmgroß. In den Tests liest ein echter QR-Decoder alle Codes.
- **Minispiele: eigenes WLAN per QR-Code.** Spiele-Fenster → „WLAN / Hotspot“: Hotspot starten (Linux:
  NetworkManager, Windows: Mobiler Hotspot) oder vorhandenes WLAN eintragen. Die Lobby zeigt dann ① WLAN-Code und
  ② Spiel-Code – nichts abtippen.
- **Neue klassische Minispiele:** Quiz (A/B/C/D, schneller = mehr Punkte), Lichtrenner (Leuchtspuren wie „Tron“),
  Schere-Stein-Papier (alle gegen alle).
- **Den ganzen PC steuern** (Sprache, Strg+K, Handy-Karte „PC“): Lautstärke („lauter“, „auf 30“, „stumm“),
  Programme und Webseiten öffnen, „suche nach …“, YouTube, Fenster schließen/minimieren, Desktop zeigen,
  Bildschirmfoto. Herunterfahren/Neustart/Ruhezustand nur nach „Ja“ und nie vom Handy.
- **Ausführen-Kacheln wie Win+R:** Programm, Datei, Ordner, Webseite oder Befehl – gemeinsam oder getrennt für
  Windows und Linux (Dual-Boot). In der Befehlssuche: „> notepad“.
- **Desktop-Widgets:** Uhr, Systemstatus, Musik, Sprach- und Lautstärke-Anzeige auf Monitor 1 – halb durchsichtig,
  Stile Glas dunkel/hell/Neon, einzeln an/aus (Setup → Desktop-Widgets oder „Widgets an“).
- **Dual-Boot-Abgleich zuverlässiger:** zusammenführen statt eine Seite verwerfen; Ordner wird wiedergefunden, wenn
  Linux das Laufwerk woanders einhängt; Abgleich zusätzlich jede Minute; verbindet sich beim Start automatisch,
  wenn das andere System schon einen Sync-Ordner hat.
- **Linux (Wayland):** Handy als Fernbedienung/Touchpad und „Fenster schließen“ über ydotool (empfohlenes Paket,
  Dienst ydotoold muss laufen).
- **Schneller:** Setup öffnet ~2,5× schneller (Bereiche erst beim Öffnen, Sprachpakete nicht zum Prüfen laden);
  Minispiel-Grafik teils doppelt so schnell (Lichtrenner 28 → 15 ms je Bild, Full HD), Lobby mit 30 statt 60 Bildern/s.
- **Sprache:** Echttest jetzt mit PC-Befehlen („Computer, mach lauter“, „Alu PC, öffne Firefox“) – 10/10 verstanden,
  0/8 Fehlalarme (CI, Windows und Linux).
- Ehrlich – nicht mit echter Hardware getestet: Hotspot (in der CI hat Windows kein WLAN; dort kommt nur eine
  verständliche Fehlermeldung), Desktop-Widgets unter Wayland (Positionen legt KWin fest), ydotool, Lautstärke
  unter Windows (Medientasten, 2 %-Schritte), Dual-Boot mit echten Laufwerken.

### Neu in Version 0.95.0
- **Fingerabdruck: EIN Auflegen reicht öfter.** War das erste Bild schlecht (Finger halb aufgelegt, verwischt),
  musste man den Finger heben und neu auflegen. Jetzt nimmt AluPC sofort bis zu 3 Bilder, solange der Finger liegt –
  beim Entsperren (Linux), am Sperrbildschirm/sudo (PAM), bei Finger-Schnelltasten und beim „Finger prüfen“.
- **Fingerabdruck: Licht am Modul.** Grün blinken = erkannt, rot blinken = nicht erkannt. Module ohne diesen
  Befehl bleiben einfach dunkel (kein Fehler).
- **Animationen:**
  - Seitenleiste: die Markierung gleitet weich zur gewählten Seite (auch im schmalen Fenster).
  - Fingerabdruck-Ring: Scan-Strahl beim Warten, Haken „ploppt“ mit Lichtring bei Erfolg, Ring schüttelt bei Fehler.
- **Überprüft:** alle Seiten in Hell, Dunkel und im kleinen Fenster durchgesehen; 322 Tests grün.
- Ehrlich: Die LED-Befehle stammen aus der ZW101-Beschreibung und sind nur mit dem nachgebauten Modul getestet –
  ob dein Modul blinkt, kann ich ohne Hardware nicht prüfen. Das Entsperren selbst ebenfalls nur mit nachgebautem
  Modul und nachgebautem Sperrbildschirm.

### Neu in Version 0.94.0
- **Neuer Echttest gegen Fehlalarme:** In jedem Build spricht eine Computerstimme 8 normale Gesprächssätze ohne
  Startwort („Ich sitze gerade am Computer …“, „Mach mal das Licht aus, Mama“, „Wie spät ist es eigentlich?“).
  Ergebnis vor diesem Release: 0 von 8 Fehlalarmen (Windows und Linux).
- **„Computer, …“ echt geprüft** (Computerstimme → Spracherkennung → Befehl).
- **Genauer verstehen:** Hört die normale Erkennung nur „Licht“, der Wortschatz-Erkenner aber „Licht rot“, nimmt AluPC
  jetzt das Genauere (vorher wurde nur das Licht umgeschaltet).
- **Knopf „Zuhören“ zeigt „Ich höre …“**, solange AluPC nach „Ja?“ ohne Startwort zuhört.
- Ehrlich: geprüft mit erzeugter Stimme, nicht mit deinem Mikrofon und echten Gesprächen im Raum.

### Neu in Version 0.93.0
- **Fehler behoben: AluPC reagierte auf normales Reden ohne Startwort.** Ursachen und Lösung:
  - Nach jeder Antwort hörte AluPC 8 s ohne Startwort weiter. Jeder Befehl öffnete das Fenster neu, so ging es
    endlos weiter. Jetzt passiert das nur noch nach „Ja?“ (nur das Startwort gesagt), und nur für EINEN Satz.
    Wer das alte Verhalten will: Setup → Sprache → „Nach jeder Antwort 8 s ohne Startwort weiterhören“ (aus).
  - Das Startwort zählte irgendwo im Satz („… der Monitor ist …“). Jetzt nur noch am Satzanfang, davor höchstens
    „hey“, „ok“, „hallo“ o. ä.
  - Der Wortschatz-Erkenner aus 0.92 konnte normale Wörter wie „alles“ oder „halt“ als „Alu PC“ deuten. Jetzt nur noch,
    wenn die normale Erkennung auch wirklich „PC“, „Monitor“, „Computer“ oder „Alu…“ gehört hat.
- **Neues Startwort „Computer“** – z. B. „Computer, Licht blau“. Ist automatisch an, im Setup abwählbar.
- Ehrlich: mit erzeugten Sprachaufnahmen und Tests geprüft, nicht mit deinem Mikrofon im echten Gespräch.

### Neu in Version 0.92.0
- **Befehlssuche (Strg+K / „Suchen“ oben links):** einfach tippen, was passieren soll – „Licht blau“, „Timer 5
  Minuten“, „Szene Pause“, „Setup Sprache“. Ganze Sätze werden wie bei der Sprachsteuerung verstanden, dazu passende
  Befehle, Szenen, Seiten und Setup-Bereiche. Enter führt aus.
- **Handy: „Frag AluPC“** – Satz eintippen oder mit dem Mikrofon der Handy-Tastatur diktieren, AluPC führt ihn aus und
  zeigt die Antwort auf dem Handy. Schnellknöpfe: Schwarz, Licht aus, Timer 5 min, Uhrzeit. Sperren, Zuhören und
  Spiele-Start gehen aus Sicherheitsgründen nur direkt am PC.
- **Handy: neue Kacheln** unter „Zeigen“: System, Wetter, Tafel, Glücksrad.
- **Spracherkennung: zweiter Erkenner mit festem AluPC-Wortschatz.** Er hört parallel nur auf bekannte Wörter
  (Befehle, Farben, Zahlen, eigene Szenen) und hilft, wenn die freie Erkennung einen Befehl verhört hat.
- Ehrlich: Der Wortschatz-Erkenner ist nur mit erzeugten Sprachaufnahmen (CI) geprüft, nicht mit deinem Mikrofon.
  Diktieren auf dem Handy hängt von der Handy-Tastatur ab (iPhone/Gboard können das) – nicht auf echtem Handy getestet.

### Neu in Version 0.91.0
- **Startwort noch zuverlässiger** – aus den echten Sprachtests der installierten Linux-Version:
  - „Alopezie …“ (so hörte das Sprachmodell „Alu PC“) zählt als Startwort.
  - „Am PC …“ am Satzanfang zählt, wenn danach ein Befehl kommt („Am PC sitzen …“ löst nichts aus).
  - „… spät ist es?“ allein wird als Frage nach der Uhrzeit verstanden.

### Neu in Version 0.90.0
- **Linux: Entsperren mit EINMAL Finger auflegen.** Vorher kam beim ersten Auflegen oft nur der Knopf „Entsperren“
  (der Sperrbildschirm nahm das erste Signal nur zum Aufwachen), erst das zweite Auflegen entsperrte. Jetzt weckt
  AluPC den Sperrbildschirm zuerst, entsperrt, prüft nach und wiederholt automatisch (bis zu 4×). Auch nach der
  Prüfung am Sperrbildschirm selbst (nach Enter) entsperrt AluPC zusätzlich – kein „Entsperren“-Knopf mehr.
- **Design & Prüfung:** alle Seiten in Hell/Dunkel und im kleinen Fenster durchgesehen und korrigiert:
  - RGB-Seite wurde rechts abgeschnitten; Farbfelder und Modus-Knöpfe brechen jetzt um.
  - Setup → Allgemein: Hilfe-Knöpfe und „Alle Daten löschen“ abgeschnitten – behoben.
  - Lange Auswahllisten (z. B. Stimme) verbreitern das Fenster nicht mehr.
  - Sprache: „Schritt 1: Sprachmodell herunterladen“ steht jetzt oben und ist hervorgehoben (ohne Modell ließen
    sich die Sprachbefehle gar nicht einschalten – stand vorher weiter unten).
  - Überschrift „Erkennung & Stimme“ zeigte einen Unterstrich statt „&“.
  - Systemseite: kleine Werte (z. B. 4 %) zeigten einen Farbklecks am Ring.
- Ehrlich: Das Entsperren konnte ich ohne echten KDE-Sperrbildschirm nur mit nachgebautem Ablauf testen.

### Neu in Version 0.89.0
- **„Sprache testen …“** (Setup → Sprache): prüft jeden Schritt live und zeigt mit ✓/✗, wo es hängt –
  Spracherkennung im Programm, Sprachmodell, Zuhören, welches Mikrofon, ob Ton ankommt (Pegelanzeige), was erkannt
  wird (live mitgeschrieben), ob das Startwort erkannt wurde, welcher Befehl ausgeführt würde. Im Test wird nichts
  ausgeführt; startet das Zuhören auch, wenn Sprachbefehle aus sind. „Bericht kopieren“ für die Fehlersuche.
  Warnt, wenn „Nur angelernte Stimmen“ an ist, die Stimmerkennung aber fehlt (dann würde alles abgelehnt).
- Geprüft: Das fertige Linux-Programm (PyInstaller) empfängt Mikrofon-Ton auch unter **PipeWire** (wie Kubuntu)
  sauber – vorher war nur PulseAudio im fertigen Programm geprüft.
- Ehrlich: Warum die Sprache bei dir unter Linux nicht geht, weiß ich noch nicht – Mikrofon, Erkennung und
  Verstehen funktionieren in allen Tests (auch im installierten .deb). Der neue Test zeigt, an welcher Stelle es
  bei dir hängt.

### Neu in Version 0.88.0
- **Grafikkarte unter Linux:**
  - NVIDIA: `nvidia-smi` läuft jetzt dauerhaft im Hintergrund und liefert jede Sekunde Werte. Vorher wurde es jede
    Sekunde neu gestartet – das dauert ohne „nvidia-persistenced“ oft länger als die erlaubten 2 s, dann kamen nie
    Daten.
  - AMD: bei Ryzen-Prozessoren mit eingebauter Grafik nimmt AluPC die Grafikkarte mit dem meisten Speicher.
  - Ohne Auslastung (Intel-Grafik, NVIDIA mit freiem nouveau-Treiber) zeigt AluPC trotzdem Karte und Temperatur
    und sagt, warum die Auslastung fehlt (Tooltip auf der Karte).
- **Sprache in der fertigen Linux-Version wird jetzt geprüft:** Die CI installiert das .deb, lässt Piper über ein
  virtuelles Mikrofon sprechen und prüft, dass das installierte AluPC die Befehle versteht.
- Ehrlich: Echte Grafikkarten und dein Mikrofon kann ich nicht testen; PulseAudio/PipeWire mit virtuellem Mikrofon
  ja (PipeWire nur aus dem Quellcode).

### Neu in Version 0.87.0
- **Mainboard-RGB (z. B. ASUS TUF B650):**
  - AluPC holt spät erkannte Geräte nach. OpenRGB findet Maus/Tastatur sofort, das Mainboard („ASUS Aura USB“)
    erst nach ein paar Sekunden – AluPC hatte die Liste aber schon beim Verbinden übernommen. Jetzt schaut es nach
    3, 8, 15 und 30 s nochmal nach; dazu Knopf „Geräte neu suchen“.
  - ARGB-Anschlüsse (Streifen, Lüfter am Mainboard) stehen in OpenRGB oft auf **0 LEDs** – dann leuchtet nichts.
    Die LED-Anzahl lässt sich jetzt direkt in AluPC einstellen (RGB & Lüfter → unter dem Gerät) und wird gemerkt.
  - Fehlt das Mainboard ganz, steht ein Hinweis da, woran es meist liegt (Windows: Armoury Crate/„LightingService“;
    Linux: udev-Regeln von OpenRGB; OpenRGB 1.0 oder neuer für AM5-Boards).
- Ehrlich: Getestet gegen einen nachgebauten OpenRGB-Server, nicht mit deinem Board. Ob OpenRGB selbst dein
  TUF B650-PLUS WIFI erkennt, hängt von der OpenRGB-Version ab – das kann AluPC nicht ändern.

### Neu in Version 0.86.0
- **Mikrofon wird wieder erkannt – bei jedem Mikrofon.** Fehler aus 0.84/0.85: PySide 6.11 meldet den
  Mikrofon-Zustand mit einem anderen Aufzählungstyp (QtAudio statt QAudio); „kein Fehler“ war dadurch nie gleich
  „kein Fehler“ und AluPC hielt jedes Mikrofon für defekt („lässt sich nicht öffnen“). Behoben.
- Dazu ein PySide-Fehler beim Zustandswechsel des Mikrofons (TypeError bei jedem Wechsel) – umgangen; der Wächter
  prüft das Mikrofon stattdessen alle 3 Sekunden.
- **Jetzt mit echtem Mikrofon-Weg geprüft:** über PulseAudio mit virtuellem Mikrofon – Ton kommt an, Umrechnen
  (44,1 kHz Stereo → 16 kHz) stimmt, nach Abziehen und Wieder-Anstecken öffnet AluPC das Mikrofon selbst neu.
  Die CI lässt Piper jetzt auch über dieses Mikrofon sprechen und prüft, dass AluPC die Befehle versteht.
- Ehrlich: Das ist ein virtuelles Mikrofon unter Linux, kein echtes im Raum; Windows-Mikrofone konnte ich nicht
  prüfen (die Windows-CI hat kein Audiogerät).

### Neu in Version 0.85.0
- **Startwort zuverlässiger:** Im echten Sprachtest der CI hat das kleine Modell „Alu PC“ auch als „anno pc“,
  „alle pc“ oder „am pc“ gehört – dann passierte gar nichts. „Anno PC“/„Alle PC“ zählen jetzt; bei unklaren
  Fällen wie „am PC …“ fragt Whisper (falls heruntergeladen) nach und lässt den Satz nur zu, wenn es „Alu PC“ hört.
- Ehrlich: Die CI-Ergebnisse schwanken von Lauf zu Lauf (Piper spricht jedes Mal etwas anders) – zuletzt 4–6 von
  6 Sätzen. Mit echtem Mikrofon im Raum habe ich es nicht testen können.

### Neu in Version 0.84.0
- **Leistung richtig messen (Seite „System“ und Dashboard):**
  - Windows: Prozessor-Auslastung jetzt mit denselben Zählern wie der Task-Manager („% Processor Utility“) –
    vorher deutlich zu niedrig. Takt jetzt der aktuelle statt immer der feste Basistakt.
  - Windows: Grafikkarten-Auslastung und Grafikspeicher auch ohne NVIDIA (AMD, Intel) über die Zähler des
    Task-Managers.
  - Netzwerk: nur echte Anschlüsse – vorher zählte der interne Verkehr (127.0.0.1, z. B. AirPlay/Handy-Steuerung
    von AluPC selbst), Docker, VPN und virtuelle Adapter mit; dadurch viel zu hohe Werte.
  - Laufwerke: Lesen/Schreiben nur über ganze Laufwerke – vorher zählten Partitionen, Loop- und LVM-Geräte doppelt.
  - Prozessor-Auslastung wird unabhängig gerechnet (eine Sprachfrage „Wie geht es dem Computer?“ konnte die
    Messung verstellen). Ryzen: echte Temperatur (Tdie) statt der um bis zu 20 °C erhöhten Regel-Temperatur.
- **Sprachsteuerung stabiler:**
  - „Alu PC, Kamera“, „… AirPlay“, „… QR-Code“ meldeten „Unbekannter Befehl“ (gab es nur fürs Handy) – behoben.
  - Mikrofone, die kein 16 kHz/Mono können (häufig unter Windows), lieferten Stille oder einen Fehler – AluPC rechnet
    jetzt um. Ein Wächter öffnet das Mikrofon neu, wenn nach Energiesparen, Abstecken oder Gerätewechsel kein Ton
    mehr kommt. „Hört zu“ steht nur noch da, wenn das Mikrofon wirklich offen ist.
  - Vosk zuerst, Whisper nur als zweite Meinung (in der CI war Vosk bei klaren Sätzen zuverlässiger).
  - Fehler beim Zuhören werden nicht mehr verschluckt: Antwort „Das ging nicht: …“ mit Grund, Eintrag im
    Fehlerprotokoll (Fehlerbericht). Kein „Läuft“-Satz mehr, wenn es gar nicht geklappt hat.
- **Stimme anlernen geht jetzt immer:** Knopf ist nicht mehr gesperrt; der Dialog lädt die Stimmerkennung selbst,
  startet das Zuhören kurz selbst (auch wenn Sprachbefehle aus sind) und zeigt, was er hört.
- **Bildschirmschoner:** neue Zeile „Zustand“ im Setup sagt, ob er läuft und warum er gerade nicht startet (z. B.
  „Automatisch: aus“, „Monitor 2 zeigt gerade etwas – „Wann: Immer“ wählen“, Leerlauf in Sekunden).
- Ehrlich: in der CI läuft das nur in virtuellen Maschinen ohne echtes Mikrofon; ob die Leistungswerte auf deinem
  PC genau zum Task-Manager bzw. KDE-Systemmonitor passen, konnte ich nicht vergleichen.

### Neu in Version 0.83.0
- **Ganz normal sprechen** statt fester Befehle: „Alu PC, mach mal den Bildschirm schwarz“, „… Licht auf blau“,
  „… Timer auf fünf Minuten“, „… kein Standbild mehr“, „… zeig mir die Kamera“. An und aus gehen gezielt.
- **Bessere Antworten:** passend zum Zustand („Monitor 2 ist schon schwarz“), echte Antworten auf Fragen
  (Uhrzeit, Datum, Wetter, Prozessor-Temperatur, Auslastung, was läuft, „Was kannst du?“, Witz).
- **Startwort zuverlässiger:** Das kleine Sprachmodell hört „Alu PC“ oft als „Hallo PC“ (in der CI gemessen) –
  das zählt jetzt auch. „Hallo“ allein nicht.
- **Gespräch:** Nur „Alu PC“ → „Ja?“. Nach jeder Antwort 8 s ohne Startwort nachfragen.
- **Mikrofon-Schalter:** Knopf „Zuhören“ links oder Strg+Alt+H – solange an, kein Startwort nötig.
- **Genauere Erkennung (optional):** Whisper Base (ca. 145 MB) oder Small (ca. 485 MB), offline.
- **Natürliche Stimme (optional):** Piper-Stimmen Thorsten, Kerstin, Ramona, Eva – offline, Tempo wählbar.
  Echo-Sperre, damit AluPC sich nicht selbst hört.
- Ehrlich: In der CI geprüft mit synthetischer Stimme (Piper → Vosk/Whisper), nicht mit echtem Mikrofon im Raum.
  Das Verstehen ist regelbasiert, keine Online-KI. Das Programm wird durch Piper/Whisper deutlich größer.

### Neu in Version 0.82.0
- **Neue Seite „System“** (links): Prozessor, Arbeitsspeicher, Grafikkarte und Temperatur als animierte
  Ringe mit 60-s-Kurven, dazu alle Prozessorkerne, Netzwerk (↓/↑, IP), Laufwerke, Akku, Temperaturen &
  Lüfter und die Programme mit der meisten Last (mit „Beenden“).
- **Steuerung:** Sperren, Energie sparen, Neu starten, Herunterfahren (mit Rückfrage), RGB an/aus und
  Farbe, „RGB & Lüfter …“, Systemüberwachung öffnen.
- **System-Dashboard auf Monitor 2:** Knopf „Auf Monitor 2“, neue Kachel „System“ und Sprachbefehl
  „Alu PC, System“.
- **Installer mit RGB & Lüftern:** Windows-Installer bietet OpenRGB (vorausgewählt) und FanControl
  (abgewählt) über winget an. Das .deb empfiehlt lm-sensors, i2c-tools, openrgb und lädt `i2c-dev`.
  Neuer Knopf „OpenRGB installieren“ auf der Seite „RGB & Lüfter“.
- Ehrlich: Windows meldet ohne Hersteller-Programm keine CPU-Temperatur und keine Lüfter (NVIDIA-Werte
  gehen). Getestet nur in einer VM ohne Grafikkarte/Sensoren; Neustart/Herunterfahren, die winget-
  Installation und OpenRGB in Ubuntu 24.04 (dort nicht in den Paketquellen) nicht echt ausprobiert.

### Neu in Version 0.81.0
- **Antwort per Stimme:** Nach einem Sprachbefehl sagt AluPC kurz „Okay. Schwarz“ (offline, Sprachausgabe des
  Systems; Linux braucht `speech-dispatcher` und `espeak-ng`). Setup → Sprache: an/aus, Stimme, „Probehören“.
- **Eigene Sprachbefehle:** Setup → Sprache → „Befehl hinzufügen …“ – Satz eintippen, Aktion wählen (alle
  Befehle, Szenen, eigene Kacheln). Eigene Sätze gehen vor den eingebauten.
- **Minispiele per Sprache:** „Alu PC, Spiel Pong“ (Spiel wählen), „… nächste Frage“, „… Ergebnis zeigen“,
  „… Lobby“, „… Teams mischen“, „… Töne aus“. „Alu PC, weiter“ im laufenden Spiel = nächste Frage/Runde.
- **Minispiele: Avatare** – beim Beitreten ein Tier oder Symbol wählen, es erscheint auf Monitor 2.
- **Minispiele: Vibration** bei „raus“, falsch, Treffer, Tor, Plopp, Sieg … – nur Android (iPhones können das im
  Browser nicht).
- **Videos weiterschauen oder von vorn:** Bei Videos ab 2 Minuten merkt sich AluPC die Stelle. Beim nächsten
  Öffnen kommt die Frage am PC und in der Handy-Steuerung; ohne Antwort geht es nach 15 s weiter.
- Ehrlich: Sprachausgabe und Vibration habe ich hier nicht hören bzw. fühlen können (kein Lautsprecher, kein
  echtes Handy) – getestet sind die Abläufe dahinter.

### Neu in Version 0.80.0
- **Neues Startwort „Alu PC“:** „Alu PC, Bildschirm schwarz“, „Alu PC, nächste Szene“ … „Monitor“ geht weiter;
  beide lassen sich im Setup → *Sprache* einzeln an- und ausschalten. „Bildschirm“/„Monitor“ nach dem Startwort
  darf man sagen, muss man aber nicht.
- **Nur auf bestimmte Stimmen hören:** Stimmerkennung einmal herunterladen (ca. 13 MB), „Stimme anlernen …“ –
  sechs kurze Sätze vorlesen – und „Befehle nur von angelernten Stimmen annehmen“ einschalten. Mehrere Stimmen
  möglich, Genauigkeit streng/normal/locker. Unter „Zuletzt gehört“ steht, wen AluPC erkannt hat und wie sicher.
- Ehrlich:
  - Das ist ein Komfort-Filter gegen Zurufe aus dem Raum, **kein Schutz** – eine Aufnahme oder eine sehr
    ähnliche Stimme kann ihn täuschen.
  - Getestet nur mit nachgebauter Erkennung; mit echten Stimmen und Mikrofon konnte ich es hier nicht
    ausprobieren. Die Grenzwerte für „streng/normal/locker“ sind Startwerte – ggf. anpassen, wenn AluPC dich
    nicht erkennt (locker) oder andere durchlässt (streng).
  - Wie gut „Alu PC“ verstanden wird, hängt davon ab, wie das kleine Sprachmodell es hört; AluPC akzeptiert
    dafür mehrere Schreibweisen („alu pc“, „alu pe ze“ …).

### Neu in Version 0.79.0
- **Sprachbefehle am PC (offline):** „Monitor schwarz“, „Monitor spiegeln“, „Monitor nächste Szene“,
  „Monitor Szene Pause“, „Monitor Glücksrad drehen“, „Monitor Spiel starten“ … Setup → *Sprache*: Sprachmodell
  einmal herunterladen (ca. 45 MB), einschalten, Mikrofon wählen. Alles bleibt auf dem PC (Vosk). Ohne das Wort
  „Monitor“ passiert nichts; „Monitor zwei …“ geht auch.
- **Bestenliste des Abends** für die Minispiele: Punkte aus allen Spielen, Taste **B** im Steuerfenster zeigt sie
  animiert auf Monitor 2, Lobby und Handys zeigen den Stand. Bleibt bis 6 Uhr früh erhalten (auch nach Neustart).
- **Töne für die Minispiele:** 3-2-1, Los, richtig/falsch, raus, Plopp, Treffer, Tor, Fanfare, Simon-Töne.
  An/aus mit Taste **S** im Steuerfenster.
- **Whiteboard vom Handy:** im Tab *Zeichnen* Hintergrund antippen → Whiteboard auf Monitor 2.
- Ehrlich: Die Spracherkennung habe ich nur mit nachgebauter Erkennung getestet – das echte Sprachmodell und ein
  echtes Mikrofon konnte ich hier nicht ausprobieren. Wie gut sie dich versteht, zeigt sich erst bei dir
  (unter Setup → Sprache steht, was AluPC gehört hat).

### Neu in Version 0.78.0
- **Linux: Sperrbildschirm mit dem Finger entsperren, ohne Enter** – wie unter Windows. Bisher musste man am
  KDE-Sperrbildschirm erst Enter drücken, dann den Finger auflegen. Jetzt wacht AluPC, solange gesperrt ist, und
  entsperrt bei einem eigenen Anmelde-Finger direkt (über logind, klappt mit Plasma 5 und 6).
  - Nur, wenn „Anmelden mit Fingerabdruck“ für dich an ist, und nur mit deinen Fingern.
  - Lag der Finger beim Sperren schon drauf, passiert nichts – erst neu auflegen.
  - Abschaltbar: Fingerabdruck → „Sperrbildschirm: Finger auflegen genügt (ohne Enter)“.
  - Nicht beim Anmelden nach dem Einschalten (dort läuft AluPC noch nicht) – da wie bisher Enter, dann Finger.
- AluPC und die Anmelde-Prüfung lesen das Modul nie mehr gleichzeitig (Linux: exklusiver Zugriff, kurzes Warten).
- Ehrlich: getestet mit einem nachgebauten Modul; mit dem echten ZW101 am echten KDE-Sperrbildschirm konnte ich
  es hier nicht ausprobieren.

### Neu in Version 0.77.0
- **7 neue Minispiele** (jetzt 10):
  - **Schätzen** – knapp 300 Fragen in 8 Themen, Thema und Anzahl wählbar; Auflösung auf einem Zahlenstrahl.
  - **Malen & Raten** – einer malt auf dem Handy (live auf Monitor 2), die anderen raten.
  - **Farb-Chaos** (Stroop) – Farbe oder Wort tippen; wer falsch liegt, ist raus.
  - **Simon sagt** – Farbfolge merken; alle gleichzeitig, ein Fehler und man ist raus.
  - **Tauziehen** und **Pong** – Team Rot gegen Team Blau.
  - **Ballon** – aufpumpen und rechtzeitig sichern.
- **Nur der PC startet:** Handys können nichts mehr starten. Neues **Steuerfenster** (Kachel „Minispiele“) mit Spielwahl,
  Einstellungen, Spielerliste (Team wechseln, entfernen) und Tasten (Leertaste = Start, N = Weiter, E = Ergebnis,
  L = Lobby, T = Teams mischen, 1 … 0 = Spiel).
- **Schnellere Steuerung:** Handys sind per WebSocket verbunden statt ständig nachzufragen; Rückfall auf die alte Art,
  falls das nicht geht.
- **Animationen:** 3-2-1 vor jedem Spiel, Konfetti und wachsendes Siegertreppchen, Funken, platzende Ballons,
  Tor-Blitz, ausscheidende Spieler wackeln …
- Ehrlich: getestet mit automatischen Tests und einem simulierten iPhone in Chromium (über die schnelle Verbindung),
  noch nicht mit vielen echten Handys gleichzeitig im WLAN.

### Neu in Version 0.76.0
- **Minispiele – das Handy ist der Controller:** neue Kachel *Minispiele* (Bereich Handy). Monitor 2 zeigt eine
  Lobby mit QR-Code → scannen, Namen eingeben, mitspielen (ohne App, bis 12 Spieler). Start am Handy oder am PC.
  - **Schlangen-Party** – Steuerkreuz oder wischen, 90 Sekunden, wer am meisten frisst, gewinnt.
  - **Schnellster Finger** – bei GRÜN zuerst tippen (3/2/1 Punkte, zu früh = −1), 5 Runden.
  - **Tipp-Rennen** – 60 Tipps bis zum Ziel.
  - Danach Siegertreppchen; „Nochmal“ auf dem Handy. Wer zu spät kommt, steigt über den kleinen QR-Code ein.
  - Pfeil der Kachel: Spiel wählen, Runde starten, zurück zur Lobby, beenden. Befehle „spiele“ und „spiel_start“
    auch für eigene Kacheln und Finger-Schnelltasten.
  - Der QR-Code erlaubt nur Mitspielen – nicht die Handy-Steuerung.
  - Hinweis: getestet mit automatischen Tests und einem simulierten iPhone im Browser, noch nicht mit vielen echten
    Handys im WLAN. Bei schlechtem WLAN kann die Steuerung etwas verzögert sein.

### Neu in Version 0.75.0
- **Glücksrad für alles, nicht nur Namen:** keine Anzeige „7 Namen“ mehr; im Fenster heißt es „Ein Eintrag pro Zeile –
  Namen, Aufgaben, Zahlen …“, im Menü „Einträge bearbeiten …“ und „Jeden Eintrag nur einmal“.
- **Geburtstage auch ohne Fingerabdruck:** Fingerabdruck → Begrüßung → Einstellen … → unter „Namen & Geburtstage“
  eine Person eintippen → **Hinzufügen** → Geburtstag (TT.MM.). Bisher ging das nur für Personen mit angelerntem
  Finger. „Ausprobieren“ kennt die neue Person auch.

### Neu in Version 0.74.0
- **Design-Tour durch alle Seiten und Fenster** – alles im neuen, ruhigen Stil:
  - **Szenen:** Vorschauen weich eingefärbt mit runden Feldern statt knalliger Flächen mit harten schwarzen Rändern;
    Szenen-Karten flacher mit runden Ecken.
  - **Vorlagen („Neue Szene“):** drei Spalten statt zwei, Vorschaubilder mit runden Ecken, das Etikett „✦ ANIMIERT“
    sitzt unten rechts und verdeckt keine Überschriften mehr.
  - **Listen mit Häkchen** (z. B. „Startseite anpassen“): runde Häkchen-Kästchen wie im Rest von AluPC.
  - **Reiter, Schieberegler, Setup-Liste:** Markierung in der Akzentfarbe statt Lila.
  - **Setup → Darstellung** ragte rechts aus der Karte (sehr lange Einträge in der Liste „Szenenwechsel“) – behoben.
  - **„&“ in Texten** erschien als Unterstrich („Speichern_zeigen“, „Sichern_Laden“, „Lüfter_Temperaturen“,
    „Zeigen _Zeichnen“ bei den Tastenkürzeln) – behoben.
- GitHub-Seite: neue Bilder von Startseite, Szenen, Setup, Fingerabdruck und „Startseite anpassen“.

### Neu in Version 0.73.0
- **Neues, frisches Design:** Startseite mit Karten wie ein modernes Kontrollzentrum – Symbol oben, Titel unten,
  mehr Karten pro Zeile. Was gerade läuft, ist **ganz in seiner Farbe** eingefärbt. Ruhige, neutrale Farben (kein
  Lila-Schimmer mehr), flache Karten mit feinem Rand, schlichte Bereichs-Überschriften, Seitenleiste mit ruhiger
  Markierung statt leuchtendem Verlauf, einfarbige Knöpfe.
- **Menüs luftiger:** mehr Abstand, ruhige Markierung beim Drüberfahren, größere Mindestbreite.
- Test „Bildschirmschoner“ robuster (Feuerwerk ist zufällig – 0.72.0 war daran im Windows-Build gescheitert und
  wurde deshalb nicht veröffentlicht; alles aus 0.72 steht hier mit drin):
- **Glücksrad dreht nicht mehr von selbst:** Die Kachel zeigt das Rad nur. Gedreht wird mit **„Drehen“** – neuer
  Knopf in der Seitenleiste (erscheint, solange das Rad auf Monitor 2 ist), im Pfeil-Menü, per Befehl
  `gluecksrad_drehen`, Finger-Schnelltaste oder Handy.
- **Menüs überarbeitet:** runde Ecken, Überschriften (z. B. HINTERGRUND, TAFEL), die aktuelle Auswahl ist fett mit
  Haken (Kamera, Whiteboard-Hintergrund), sichtbare Häkchen-Kästchen, Symbole im Timer-Menü, runde
  Hintergrund-Vorschauen. Auswahllisten (Dropdowns) mit neuem Pfeil und ruhiger Markierung.
- **„Läuft gerade“ neu:** neue Musiknote, weicherer Hintergrund aus dem Cover (keine Schlieren mehr), Text mittig
  neben dem Cover, hüpfende Equalizer-Balken, Titel bis zu zwei Zeilen, Restzeit, runder Pause-Knopf.
- Statuskarte zeigt „Glücksrad“, „Wetter & Uhr“, „Abstimmung“, „Whiteboard“ statt interner Namen; schmale
  Seitenleiste zeigt das Symbol des Inhalts.

### Neu in Version 0.71.0
- **Wetter: Postleitzahl = Deutschland.** Eine 5-stellige PLZ (z. B. 80331 oder „80331 München“) sucht nur noch in
  Deutschland – vorher kam manchmal ein Ort in den USA heraus. Kennt der Wetterdienst die PLZ nicht, fragt AluPC
  OpenStreetMap. Ortsnamen suchen weiter weltweit.
  Ort neu eintragen: Kachel „Wetter & Uhr“ → Pfeil → „Ort ändern …“.

### Neu in Version 0.70.0
- **„Ausprobieren“ ist zurück** im Fenster *Begrüßung* (Seite Fingerabdruck): Name wählen oder eintippen →
  Animation sofort sehen, auch ohne Fingerabdrucksensor.

### Neu in Version 0.69.0
- **Begrüßung ist nicht mehr geheim:** Aus dem „geheimen Menü“ wird das Fenster **Begrüßung** – zu finden auf der
  Seite *Fingerabdruck* → „Begrüßung“ → *Einstellen …*. Der Klick-Trick auf die Versionsnummer und
  Strg+Alt+Umschalt+G sind weg.
- „Ausprobieren“ ist entfernt – die Begrüßung kommt nur noch nach der Anmeldung mit dem Finger.

### Neu in Version 0.68.0
- **Geburtstage:** im geheimen Menü je Person (TT.MM.). Am Tag: Konfetti und „Alles Gute zum Geburtstag!“.
- **Finger als Schnelltaste** (Modul am USB-Seriell-Adapter): Seite Fingerabdruck → „Finger als Schnelltaste“.
  Jeder angelernte Finger kann einen Befehl auslösen (Schwarz, Szene, Glücksrad, Computer sperren …).
  Nur bei entsperrtem PC; ein Befehl kommt erst beim erneuten Auflegen (nicht, wenn der Finger noch vom
  Entsperren draufliegt). AluPC lässt das Modul in Ruhe, solange es selbst anlernt oder testet.
  *Ehrlich:* mit einem nachgebauten Modul getestet, nicht mit dem echten ZW101. Unter Linux kann eine
  gleichzeitige sudo-Abfrage per Finger mit der Schnelltaste kollidieren (dann einfach nochmal auflegen).
- **Abstimmung per Handy** (neue Kachel): Frage + 2–6 Antworten → Monitor 2 zeigt QR-Code und Live-Balken.
  Abstimmen ohne App und ohne den Code der Handy-Steuerung. Beenden zeigt das Ergebnis.
  *Ehrlich:* Wer die Browserdaten löscht, kann nochmal abstimmen.
- **Glücksrad** (neue Kachel): Namen eintragen oder die Personen vom Fingerabdruck nehmen; fair gezogen;
  „Gezogene herausnehmen“ = jeder kommt einmal dran.
- **Wetter & Uhr** (neue Kachel): Uhr, Wetter jetzt und 3 Tage (Open-Meteo, kostenlos, ohne Anmeldung).
  Ort über den Pfeil der Kachel. Der echte Abruf wird im CI geprüft.
- **Fehlerbericht per Knopf:** Setup → „Fehlerbericht …“ → ZIP auf dem Desktop (Codes/PINs geschwärzt).
  AluPC schreibt dafür ab jetzt Programmfehler und Abstürze in ein Protokoll mit.
- Begrüßung: Der Name hat einen leichten Schatten (besser lesbar über den Farbwolken).

### Neu in Version 0.67.0
- **Willkommen nach dem Fingerabdruck:** Wer sich mit dem Finger anmeldet oder entsperrt, bekommt auf Monitor 1
  eine Vollbild-Animation mit Namen („Guten Morgen – Lena“). Klick oder Taste schließt sie sofort.
  Drei Stile: **Aurora**, **Konfetti**, **Scan** (oder zufällig).
- **Geheimes Menü:** 5× schnell auf die Versionsnummer unten links klicken (oder Strg+Alt+Umschalt+G).
  Dort: Begrüßung an/aus, Stil, eigene Überschrift, Ton, **eigene Namen je Person** (z. B. „Noah“ → „Chef“)
  und **Ausprobieren**.
- So weiß AluPC, wer es war: Linux – die Fingerabdruck-Prüfung beim Anmelden merkt sich den erkannten Platz
  (/run/alupc bzw. ~/.cache/alupc). Windows – der Anmeldebaustein schreibt ihn in die Registry
  (HKLM\SOFTWARE\AluPC\Fingerprint). Die Person kommt aus den Namen auf der Fingerabdruck-Seite.
  *Ehrlich:* Animation und Menü sind getestet, die Windows-Anmeldung im CI mit nachgebautem Sensor. Mit dem
  echten Sensor beim echten Anmelden/Entsperren ist es nicht ausprobiert. Unter Windows muss die
  Fingerabdruck-Anmeldung nach dem Update **neu eingeschaltet** werden, falls der alte Baustein noch geladen ist
  (Neustart reicht meist).

### Neu in Version 0.66.0
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
