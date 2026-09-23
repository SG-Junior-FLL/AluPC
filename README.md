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
| **Website** | Adresse eingeben → Website im Vollbild (die letzten 10 Adressen werden gemerkt) |
| **Bild / Video** | Bild, Video (Endlosschleife) oder Diashow aus einem Ordner |
| **Meine Szenen** | eigene, selbst gebaute Szenen (siehe unten) |
| **Schwarz** | Sichtschutz an/aus – schwarz, eigener Text oder eigenes Bild/Logo |
| **Standbild** | friert das Bild auf Monitor 2 ein; du arbeitest auf Monitor 1 unbemerkt weiter |
| **Bild-in-Bild** | kleines Fenster auf Monitor 1, das live zeigt, was auf Monitor 2 läuft (mit Hinweis „EINGEFROREN“/„SCHWARZ“) |

Außerdem:

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
- **Tastenkürzel** (änderbar im Setup):

  | Aktion | Standard |
  |---|---|
  | Standbild an/aus | `Strg+Alt+S` |
  | Schwarz an/aus | `Strg+Alt+B` |
  | Bild-in-Bild an/aus | `Strg+Alt+P` |
  | Spiegeln | `Strg+Alt+M` |
  | Erweitern | `Strg+Alt+E` |

- **Symbol in der Taskleiste** mit Menü (Standbild, Schwarz, Szenen, Sperren …).
  Fenster schließen = AluPC läuft im Hintergrund weiter.
- **Autostart**, letzten Inhalt beim Start wiederherstellen, Monitor wird nach dem
  Wieder-Anstecken automatisch wieder benutzt.
- **AluPC sperren**: Bedienung nur nach Fingerabdruck (oder Ersatz-PIN).

## Installation

### Kubuntu

```bash
git clone https://github.com/SG-Junior-FLL/AluPC.git
cd AluPC
./packaging/linux/install.sh
```

Das Skript installiert die nötigen Pakete (`fprintd`, `libpam-fprintd`, `wmctrl`, …), legt
AluPC in `~/.local/share/alupc` ab und erstellt einen Eintrag im Startmenü.
Entfernen: `./packaging/linux/uninstall.sh`.

### Windows 11 Pro

- **Installer**: Unter *Actions* → letzter Lauf von „Tests und Windows-Installer“ →
  Artefakt **AluPC-Windows** herunterladen → `AluPC-Setup-….exe` ausführen.
  (Bei einem Git-Tag `v…` landet der Installer zusätzlich unter *Releases*.)
- **Ohne Installer**: Python 3.10+ installieren, dann
  `packaging\windows\start-aus-quellcode.bat` doppelklicken.

## Befehle von außen

Ein laufendes AluPC lässt sich von der Kommandozeile steuern:

```bash
alupc --befehl standbild      # auch: schwarz, bild-in-bild, spiegeln, erweitern, sperren, zeigen
alupc --befehl "szene:Begrüßung"
alupc --minimiert             # nur mit Symbol in der Taskleiste starten
```

**Tastenkürzel überall in KDE:** Unter Windows gelten die Kürzel automatisch systemweit.
In KDE funktionieren sie innerhalb von AluPC sofort; für systemweite Kürzel:
*Systemeinstellungen → Tastatur → Kurzbefehle → Neu hinzufügen → Befehl* und z. B.
`alupc --befehl standbild` eintragen.

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

- **Nicht auf echter Hardware getestet.** Die Logik ist mit automatischen Tests geprüft
  (inkl. Oberfläche mit zwei virtuellen Monitoren). Echte Monitore, Kameras, Fingerabdruck-
  sensoren und Windows selbst konnten beim Entwickeln nicht getestet werden. Bitte Fehler
  mit Meldungstext melden.
- **Fingerabdruck unter Linux** geht nur mit Sensoren, die **libfprint** unterstützt.
  Viele neuere Notebook-Sensoren (z. B. manche von Goodix/Synaptics) werden nicht erkannt.
- **Windows erlaubt Fremdprogrammen nicht**, Finger für die Windows-Anmeldung anzulernen oder
  zu löschen – das geht nur über Windows Hello. Ist „Erweiterte Anmeldesicherheit“ (ESS) aktiv,
  kann Windows den Sensor für AluPC (Test-Scan, Sperre) ganz sperren → dann Ersatz-PIN nutzen.
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
- Die **Sperre** schützt die Bedienung von AluPC, nicht den ganzen Computer.

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
  hotkeys.py, ipc.py
  platform/         Systemschicht: Linux (kscreen-doctor/xrandr, KWin/wmctrl, fprintd/PAM)
                    und Windows (Win32-Anzeige-API, Fenster, Windows Biometric Framework)
  ui/               Hauptfenster (Kacheln), Szenen-Editor, Setup, Fingerabdruck, Bild-in-Bild
    theme.py        Farbschema dunkel/hell + Akzentfarbe, Stylesheet
    icons.py        selbst gezeichnete Linien-Symbole und Programmsymbol
    widgets.py      Kachel, Navigation, Statuskarte, Hinweis, Fortschrittsring, Szenen-Karte
```

Einstellungen liegen in `~/.config/AluPC/config.json` bzw. `%APPDATA%\AluPC\config.json`.
