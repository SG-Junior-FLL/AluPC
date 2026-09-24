## AluPC – Monitor 2 steuern (Kubuntu & Windows 11)

### Downloads
| System | Datei | Hinweis |
|---|---|---|
| **Windows 11** | `AluPC-Setup-….exe` | Installer (Startmenü, Deinstallation) |
| Windows 11 | `AluPC-windows-portable-….zip` | ohne Installation: entpacken, `AluPC.exe` starten |
| **Kubuntu / Ubuntu** (22.04, 24.04 und neuer) | `alupc_…_amd64.deb` | `sudo apt install ./alupc_…_amd64.deb` – danach im Startmenü |
| Linux (x86_64) | `AluPC-linux-x86_64-….tar.gz` | ohne Installation: entpacken, `AluPC/AluPC` starten |

### Neu in dieser Version (0.4.0)
- **Töne bei Aktionen** (Setup → Töne): Standbild, Schwarz, neuer Inhalt, Szene, Bildschirmschoner,
  Timer (Start, Pause, noch 1 Minute, Ende) … – 7 eingebaute Klänge oder eigene Dateien hochladen.
  Lautstärke und Ausgabegerät (z. B. HDMI des Beamers) einstellbar.
- **Eigene Kacheln**: jetzt auch mit **eigenem Bildschirmschoner** oder **Timer mit eigener Dauer**,
  dazu ein eigener Ton pro Kachel.
- **Website**: gespeicherte Websites (Favoriten), aktuelle Seite „Unter Website speichern“ und ein
  eigenes Fenster **„Browser steuern“** (Adresse, Zurück/Vor, Zoom, Scrollen, Live-Vorschau, in die
  man klicken und tippen kann).
- **Bildschirmschoner**: neuer Stil „Nachricht“ (großer Text, kleine Uhr, Hintergrundbild), Textfarbe.
- **Setup** in übersichtliche Bereiche aufgeteilt; neue Bereiche „Timer“ und „Töne“.
- Behoben: Kachel-Timer sprang auf die Standarddauer; Website-Adressen mit `data:` wurden verfälscht.

### Bekannte Grenzen
Die automatischen Tests laufen ohne echte Monitore, Kameras und Fingerabdrucksensoren. Bitte Fehler
mit Screenshot melden. Details im README unter „Ehrliche Grenzen“.
