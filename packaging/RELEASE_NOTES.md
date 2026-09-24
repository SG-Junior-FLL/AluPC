## AluPC – Monitor 2 steuern (Kubuntu & Windows 11)

### Downloads
| System | Datei | Hinweis |
|---|---|---|
| **Windows 11** | `AluPC-Setup-….exe` | Installer (Startmenü, Deinstallation) |
| Windows 11 | `AluPC-windows-portable-….zip` | ohne Installation: entpacken, `AluPC.exe` starten |
| **Kubuntu / Ubuntu** (22.04, 24.04 und neuer) | `alupc_…_amd64.deb` | `sudo apt install ./alupc_…_amd64.deb` – danach im Startmenü |
| Linux (x86_64) | `AluPC-linux-x86_64-….tar.gz` | ohne Installation: entpacken, `AluPC/AluPC` starten |

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
