## AluPC – Monitor 2 steuern (Kubuntu & Windows 11)

### Downloads
| System | Datei | Hinweis |
|---|---|---|
| **Windows 11** | `AluPC-Setup-….exe` | Installer (Startmenü, Deinstallation) |
| Windows 11 | `AluPC-windows-portable-….zip` | ohne Installation: entpacken, `AluPC.exe` starten |
| **Kubuntu / Ubuntu** (22.04, 24.04 und neuer) | `alupc_…_amd64.deb` | `sudo apt install ./alupc_…_amd64.deb` – danach im Startmenü |
| Linux (x86_64) | `AluPC-linux-x86_64-….tar.gz` | ohne Installation: entpacken, `AluPC/AluPC` starten |

### Neu in dieser Version
- **Bildschirmschoner für Monitor 2**: Uhr (wandert, schont den Bildschirm), schwebender Text/Logo,
  Diashow, Farbverlauf oder eine eigene Szene. Startet automatisch nach einstellbarer Zeit ohne
  Maus/Tastatur oder per Kachel/Tastenkürzel.
- **Startseite anpassen**: Kacheln ein-/ausblenden und sortieren, eigene Kacheln (z. B. „Begrüßung“
  → Szene, „Pausen-Uhr“ → Uhr, oder ein Befehl), eigene Überschrift.
- **Mehr Tastenkürzel**: Bildschirmschoner, nächste/vorherige Szene, eigenes Kürzel pro Szene und pro
  eigener Kachel; doppelt vergebene Kürzel werden gemeldet. Unter KDE stehen die wichtigsten Aktionen
  nach der Installation direkt unter *Systemeinstellungen → Kurzbefehle → AluPC* bereit.
- Jeder Build wird auf GitHub automatisch gestartet und geprüft (Windows: auch der installierte
  Installer; Linux: auch das installierte .deb).

### Bekannte Grenzen
Die automatischen Tests laufen ohne echte Monitore, Kameras und Fingerabdrucksensoren. Bitte Fehler
mit Screenshot melden. Details im README unter „Ehrliche Grenzen“.
