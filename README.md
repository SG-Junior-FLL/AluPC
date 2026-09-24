# AluPC – Monitor 2 steuern

AluPC steuert einen **zweiten Monitor für andere Leute** (Beamer, Kundenmonitor, Fernseher …),
während du am **Hauptmonitor** normal weiterarbeitest. Läuft unter **Kubuntu** (KDE Plasma,
Wayland und X11) und **Windows 11 Pro**.

Bedienung ohne Schnickschnack: große Kacheln, ein Klick – fertig. Keine Vorschau, kein
OBS-Studio-Fenster.

| Dunkel | Hell |
|---|---|
| ![Start – dunkel](docs/start.png) | ![Start – hell](docs/start-hell.png) |

## Design

- Eigenes, modernes Design mit **Seitenleiste**, **Statuskarte** („Was sehen die anderen gerade?“
  mit LIVE / STANDBILD / SCHWARZ) und großen Kacheln, die ihren Zustand zeigen („AKTIV“, „AN“).
- **Dunkel, Hell oder wie das System**, dazu 5 **Akzentfarben** (Setup → Darstellung).
- Alle Symbole sind selbst gezeichnet – sehen unter Kubuntu und Windows gleich scharf aus
  (keine Emojis, die je nach System anders aussehen).
- **Weiche Überblendung** auf Monitor 2, wenn der Inhalt wechselt (abschaltbar).
- Kurze **Hinweise** unten im Fenster statt Fehlerfenster, **Fortschrittsring** beim
  Fingerabdruck, grafische **Monitor-Anordnung** im Setup, **Szenen als Karten** mit Vorschau.

## Funktionen

| Kachel | Was passiert auf Monitor 2 |
|---|---|
| **Spiegeln** | zeigt dasselbe wie Monitor 1 (AluPC nimmt Monitor 1 auf – dadurch gehen Standbild und Sichtschutz) |
| **Erweitern** | Monitor 2 ist ein normaler zweiter Bildschirm |
| **Kamera** | eine Kamera im Vollbild – bei nur einer Kamera sofort, sonst Auswahl |
| **Programm** | ein Programm zeigen: *Anzeigen (Aufnahme)* oder *Fenster wirklich verschieben* |
| **Website** | Adresse eingeben oder gespeicherte Website wählen → Vollbild. Pfeil an der Kachel: gespeicherte Websites, **Browser steuern** (eigenes Fenster: Adresse, Zurück/Vor, Zoom, Scrollen, Live-Vorschau zum Klicken und Tippen), aktuelle Seite **unter „Website“ speichern** |
| **Bild / Video** | Bild, Video (Endlosschleife) oder Diashow aus einem Ordner |
| **Meine Szenen** | eigene, selbst gebaute Szenen (siehe unten) |
| **Schwarz** | Sichtschutz an/aus – schwarz, eigener Text oder eigenes Bild/Logo |
| **Standbild** | friert das Bild auf Monitor 2 ein; du arbeitest auf Monitor 1 unbemerkt weiter |
| **Bild-in-Bild** | kleines Fenster auf Monitor 1, das live zeigt, was auf Monitor 2 läuft (mit Hinweis „STANDBILD“/„SCHWARZ“) |
| **Bildschirmschoner** | Uhr, schwebender Text/Logo, Diashow, Farbverlauf oder eigene Szene – automatisch nach X Minuten ohne Maus/Tastatur oder per Klick |

Außerdem:

- **Startseite anpassen** (Knopf oben rechts auf der Startseite): Kacheln ein-/ausblenden und
  sortieren, eigene Überschrift, Statuskarte an/aus und **eigene Kacheln** – z. B. „Begrüßung“
  (zeigt eine Szene), „Pausen-Uhr“ (zeigt eine Uhr) oder „Standbild“ (führt einen Befehl aus),
  jeweils mit eigenem Symbol, eigener Farbe und eigenem Tastenkürzel.

  | Startseite | Anpassen | Eigene Kachel |
  |---|---|---|
  | ![Startseite](docs/start-v2.png) | ![Anpassen](docs/startseite-anpassen.png) | ![Eigene Kachel](docs/eigene-kachel.png) |

- **Bildschirmschoner** (Setup → Bildschirmschoner): startet nach 1–240 Minuten ohne Maus/Tastatur
  (unter Windows und KDE vom System gemeldet) – wahlweise nur, wenn AluPC gerade nichts zeigt, oder
  immer. Maus bewegen beendet ihn; von Hand gestartet (Kachel/Tastenkürzel) bleibt er, bis man ihn
  wieder ausschaltet. Sichtschutz liegt immer darüber.

  Stile: Uhr, Nachricht (großer Text + kleine Uhr, optional Hintergrundbild), schwebender Text/Logo,
  Diashow, Farbverlauf, eigene Szene; Textfarbe wählbar. Einstellungen auch direkt über den Pfeil
  an der Kachel.

  | Uhr | Farbverlauf |
  |---|---|
  | ![Uhr](docs/bildschirmschoner-uhr.png) | ![Farbverlauf](docs/bildschirmschoner-farben.png) |

- **Eigene Szenen** (Seite *Szenen*): Es gibt keine vorgefertigten Szenen. Du wählst eine
  **Layout-Vorlage** (Vollbild, 2 nebeneinander, 2 übereinander, groß + klein in einer Ecke,
  2 × 2, 1 groß + 2 klein, Vollbild + Textleiste) und legst in jedes Feld eine Quelle:
  Kamera, Programm, Bildschirm, Website, Bild, Video, Diashow, Text, Uhr, Countdown,
  Farbfläche oder eine andere Szene.

  | Szenen | Szenen-Editor | Ergebnis auf Monitor 2 |
  |---|---|---|
  | ![Szenen](docs/szenen.png) | ![Szenen-Editor](docs/szenen-editor.png) | ![Monitor 2](docs/monitor2-beispiel.png) |
- **Setup**: Auflösung, **Bildwiederholrate (Hz)**, Skalierung (KDE/Wayland), Drehung,
  Hauptmonitor, Anordnung (rechts/links/oben/unten/gespiegelt). Nach „Übernehmen“ fragt AluPC
  „Einstellungen behalten?“ – ohne Antwort wird nach 15 Sekunden zurückgesetzt.
  „Monitore identifizieren“ zeigt auf jedem Monitor eine große Nummer.
- **Fingerabdruck** (Seite *Fingerabdruck*): Sensor wählen, Finger anlernen, Test-Scan,
  Finger löschen, Anmelden mit Fingerabdruck ein/aus (Details unten).

  | Setup | Finger anlernen | Bild-in-Bild |
  |---|---|---|
  | ![Setup](docs/setup.png) | ![Fingerabdruck](docs/fingerabdruck.png) | ![Bild-in-Bild](docs/bild-in-bild.png) |
- **Tastenkürzel** (Setup → Tastenkürzel: auf das Kürzel klicken, neue Tasten drücken – fertig;
  „Kein Kürzel“ entfernt es):

  | Aktion | Standard |
  |---|---|
  | Standbild an/aus | `Strg+Alt+S` |
  | Schwarz an/aus | `Strg+Alt+B` |
  | Bild-in-Bild an/aus | `Strg+Alt+P` |
  | Bildschirmschoner an/aus | `Strg+Alt+W` |
  | Nächste / vorherige Szene | `Strg+Alt+Bild↓` / `Strg+Alt+Bild↑` |
  | Timer Start/Pause | `Strg+Alt+T` (Neustart, ±1 Minute frei belegbar) |
  | Spiegeln | `Strg+Alt+M` |
  | Erweitern | `Strg+Alt+E` |
  | jede Szene | frei wählbar im Szenen-Editor |
  | jede eigene Kachel | frei wählbar unter „Startseite anpassen“ |

  Doppelt vergebene Kürzel meldet AluPC.

- **Steuern über die Taskleiste**: Ein Klick auf das AluPC-Symbol öffnet ein Schnellmenü
  (Standbild, Schwarz, Bildschirmschoner, Bild-in-Bild, Timer, Spiegeln, Erweitern, Szenen,
  Computer sperren). Das Symbol zeigt den Zustand (Schneeflocke = Standbild, Auge = Schwarz,
  Mond = Bildschirmschoner). Doppelklick öffnet AluPC.
  Fenster schließen = AluPC läuft im Hintergrund weiter.
- **Autostart**, letzten Inhalt beim Start wiederherstellen, Monitor wird nach dem
  Wieder-Anstecken automatisch wieder benutzt.
- **Computer sperren** (Seitenleiste, Taskleisten-Menü, Befehl `sperren`): wie Win+L bzw. die
  Bildschirmsperre unter Linux – Monitor 2 zeigt dabei weiter, was gerade läuft.
- **Töne** (Setup → Töne): Ton bei Standbild an/aus, Schwarz an/aus, neuem Inhalt, Szenenwechsel,
  Bildschirmschoner, Timer-Start/-Pause, „noch 1 Minute“, Timer-Ende … – 7 eingebaute Klänge oder
  eigene Dateien hochladen (WAV, MP3, OGG …). Lautstärke und Ausgabegerät (z. B. HDMI des Beamers)
  wählbar. Eigene Kacheln können einen eigenen Ton haben.
- **Eigene Kacheln – mehr Möglichkeiten**: etwas anzeigen, **eigener Bildschirmschoner** (z. B.
  „Pause – gleich geht's weiter“ mit Hintergrundbild; nochmal klicken = beenden), **Timer mit eigener
  Dauer** oder ein Befehl – jeweils mit eigenem Symbol, Farbe, Ton und Tastenkürzel.
- **Setup in Bereichen**: Monitore, Monitor 2, Darstellung, Bildschirmschoner, Timer, Töne,
  Tastenkürzel, Allgemein.
- **Timer** (Kachel „Timer“): Countdown oder Stoppuhr, läuft durch – auch wenn Szenen neu
  aufgebaut werden. Klick = Start/Pause (beim ersten Mal wird er auf Monitor 2 gezeigt), Pfeil =
  Neu starten, ±1 Minute, Einstellen. Letzte Minute orange, letzte 10 Sekunden rot, am Ende blinkt
  er. Tastenkürzel: `Strg+Alt+T` = Start/Pause (weitere frei belegbar).
- **Standbild-Symbol**: kleine Schneeflocke oben rechts auf dem eingefrorenen Bild (abschaltbar
  unter Setup → Monitor 2).
- **Monitor 2 bleibt vorne**: Wird das Fenster verdeckt oder minimiert (z. B. Win+D), holt AluPC es
  sofort zurück. Unter Windows wird die Taskleiste auf Monitor 2 ausgeblendet, solange AluPC dort
  etwas zeigt (abschaltbar), unter KDE wird das Fenster über die Leisten gelegt.

## Installation

Fertige Pakete gibt es unter **[Releases](https://github.com/SG-Junior-FLL/AluPC/releases)**:

| System | Datei | So geht's |
|---|---|---|
| **Windows 11** | `AluPC-Setup-….exe` | Doppelklick, installieren – AluPC steht im Startmenü |
| Windows 11 | `AluPC-windows-portable-….zip` | entpacken, `AluPC.exe` starten |
| **Kubuntu / Ubuntu 22.04, 24.04+** | `alupc_…_amd64.deb` | `sudo apt install ./alupc_…_amd64.deb` – AluPC steht im Startmenü |
| Linux x86_64 | `AluPC-linux-x86_64-….tar.gz` | entpacken, `AluPC/AluPC` starten |

Für den Fingerabdruck unter Linux zusätzlich: `sudo apt install fprintd libpam-fprintd`
(das .deb empfiehlt die Pakete, apt installiert sie normalerweise gleich mit).

**Aus dem Quellcode (Kubuntu):**

```bash
git clone https://github.com/SG-Junior-FLL/AluPC.git
cd AluPC
./packaging/linux/install.sh      # entfernen: ./packaging/linux/uninstall.sh
```

**Aus dem Quellcode (Windows):** Python 3.10+ installieren, dann
`packaging\windows\start-aus-quellcode.bat` doppelklicken.

Jeder Build auf GitHub wird automatisch geprüft: Tests, Start der fertigen Programmdatei,
unter Windows zusätzlich der installierte Installer und unter Linux das installierte .deb-Paket.

## Befehle von außen

Ein laufendes AluPC lässt sich von der Kommandozeile steuern:

```bash
alupc --befehl standbild      # auch: schwarz, bild-in-bild, bildschirmschoner, spiegeln, erweitern,
                              #       naechste_szene, vorherige_szene, sperren, zeigen
alupc --befehl "szene:Begrüßung"
alupc --minimiert             # nur mit Symbol in der Taskleiste starten
```

**Tastenkürzel überall in KDE:** Unter Windows gelten die Kürzel automatisch systemweit.
In KDE funktionieren sie innerhalb von AluPC sofort. Für systemweite Kürzel stehen die wichtigsten
Aktionen nach der Installation unter *Systemeinstellungen → Tastatur → Kurzbefehle → AluPC* bereit
(Taste zuweisen, fertig). Setup → Tastenkürzel hat dafür den Knopf „KDE-Kurzbefehle öffnen“.
Für Szenen: *Neu hinzufügen → Befehl* mit `alupc --befehl "szene:Name"`.

## Fingerabdruck – was geht wo

| | Kubuntu | Windows 11 |
|---|---|---|
| Sensor auswählen | ✔ (fprintd) | ✔ (anzeigen) |
| Finger anlernen | ✔ direkt in AluPC | über Windows Hello – AluPC öffnet die Seite direkt |
| Angelernte Finger anzeigen | ✔ | ✔ |
| Test-Scan | ✔ | ✔ |
| Finger löschen | ✔ | nur in den Windows-Einstellungen |
| Anmelden mit Fingerabdruck | ein/aus über `pam-auth-update` (gilt für Anmeldebildschirm, Sperrbildschirm, sudo) | automatisch aktiv, sobald ein Finger in Windows Hello angelernt ist |

## Ehrliche Grenzen

- **Nicht auf echter Hardware getestet.** Die automatischen Tests laufen auf GitHub unter Linux und
  Windows (inkl. Start der fertigen Programme und der installierten Pakete) – aber ohne echte Monitore,
  Kameras und Fingerabdrucksensoren. Bitte Fehler mit Screenshot oder Meldungstext melden.
- **Fingerabdruck unter Linux** geht nur mit Sensoren, die **libfprint** unterstützt.
  Viele neuere Notebook-Sensoren (z. B. manche von Goodix/Synaptics) werden nicht erkannt.
- **Windows erlaubt Fremdprogrammen nicht**, Finger für die Windows-Anmeldung anzulernen oder
  zu löschen – das geht nur über Windows Hello. Ist „Erweiterte Anmeldesicherheit“ (ESS) aktiv,
  kann Windows den Sensor für AluPC (Test-Scan) ganz sperren.
- **Wayland (KDE)**: Beim ersten Aufnehmen des Bildschirms (Spiegeln, Bild-in-Bild,
  Standbild im Modus „Erweitern“) fragt KDE nach einer Freigabe. Einzelne Programmfenster
  kann Qt unter Wayland nicht aufnehmen – dort „Programm → Fenster verschieben“ nutzen
  (klappt über ein kleines KWin-Skript). „Immer im Vordergrund“ für Bild-in-Bild setzt KDE
  unter Wayland evtl. nicht um (Abhilfe: Fensterregel in KDE).
- **System-Spiegeln** (Setup) spiegelt über das Betriebssystem. Dann liegen beide Monitore
  übereinander – Standbild und Sichtschutz sind in diesem Modus nicht möglich. Die Kachel
  „Spiegeln“ nutzt deshalb die Aufnahme durch AluPC.
- **Hz/Auflösung**: Wählbar ist nur, was Monitor, Kabel und Grafikkarte melden. Skalierung
  lässt sich unter Windows/X11 nur in den Systemeinstellungen ändern.
- **Taskleiste ausblenden (Windows)** nutzt die versteckte Taskleiste auf Monitor 2
  („Shell_SecondaryTrayWnd“). Beim Beenden von AluPC wird sie wieder eingeblendet; sollte AluPC
  abstürzen, kommt sie spätestens nach einer Ab-/Anmeldung zurück.
- **Bildschirmschoner – Leerlaufzeit**: Unter Windows und KDE meldet das System, wann zuletzt Maus
  oder Tastatur benutzt wurden. Wo das nicht geht, zählt nur die Bedienung von AluPC (steht im Setup).
- **Websites unter Kubuntu 24.04+**: Das System erlaubt der eingebauten Chromium-Engine ihre Sandbox
  nur mit AppArmor-Profil. Das .deb bringt eins mit. Bei `install.sh` oder Start aus dem Quellcode
  schaltet AluPC die Sandbox der Website-Anzeige deshalb aus (Websites laufen dann mit weniger
  Schutz – nur vertrauenswürdige Seiten anzeigen).

## Entwicklung

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[test]"
pytest            # Logik- und Oberflächentests (Qt „offscreen“ mit zwei virtuellen Monitoren)
python -m alupc
```

Aufbau:

```
alupc/
  app.py            Start, Kommandozeile, eine Instanz
  controller.py     Was läuft auf Monitor 2 (Modi, Standbild, Sichtschutz)
  output_window.py  Vollbild auf Monitor 2 + Standbild-/Sichtschutz-Ebene
  sources.py        Quellen: Kamera, Bildschirm, Programm, Website, Bild, Video, Text, Uhr …
  scenes.py         Layout-Vorlagen und Szenen-Logik
  screensaver.py    Bildschirmschoner: Stile, Leerlaufzeit (Windows, KDE/GNOME, xprintidle)
  startpage.py      Startseite: Kacheln, Reihenfolge, eigene Kacheln
  hotkeys.py, ipc.py
  platform/         Systemschicht: Linux (kscreen-doctor/xrandr, KWin/wmctrl, fprintd/PAM)
                    und Windows (Win32-Anzeige-API, Fenster, Windows Biometric Framework)
  ui/               Hauptfenster (Kacheln), Szenen-Editor, Setup, Fingerabdruck, Bild-in-Bild
    theme.py        Farbschema dunkel/hell + Akzentfarbe, Stylesheet
    icons.py        selbst gezeichnete Linien-Symbole und Programmsymbol
    widgets.py      Kachel, Navigation, Statuskarte, Hinweis, Fortschrittsring, Szenen-Karte
```

Einstellungen liegen in `~/.config/AluPC/config.json` bzw. `%APPDATA%\AluPC\config.json`.
