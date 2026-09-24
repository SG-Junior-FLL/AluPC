## AluPC – Monitor 2 steuern (Kubuntu & Windows 11)

### Downloads
| System | Datei | Hinweis |
|---|---|---|
| **Windows 11** | `AluPC-Setup-….exe` | Installer (Startmenü, Deinstallation) |
| Windows 11 | `AluPC-windows-portable-….zip` | ohne Installation: entpacken, `AluPC.exe` starten |
| **Kubuntu / Ubuntu** (22.04, 24.04 und neuer) | `alupc_…_amd64.deb` | `sudo apt install ./alupc_…_amd64.deb` – danach im Startmenü |
| Linux (x86_64) | `AluPC-linux-x86_64-….tar.gz` | ohne Installation: entpacken, `AluPC/AluPC` starten |

### Neu in dieser Version (0.5.0)
- **Übergänge zwischen Szenen**: Überblenden, über Schwarz, Wegschieben, Wischen, Zoom oder harter
  Schnitt – Dauer einstellbar (Setup → Darstellung, mit „Ausprobieren“), pro Szene überschreibbar.
- **Ton pro Medium**: eigene Lautstärke und „Ton aus“ für jedes Video und jede Website (auch in
  Szenen-Feldern). Live-Regler oben im Hauptfenster und „Ton auf Monitor 2“ im Taskleisten-Menü.
- **Programm** überarbeitet: Suche, Liste aktualisiert sich selbst, Programmname und „minimiert“ werden
  angezeigt, Windows-Systemfenster (z. B. „Program Manager“) tauchen nicht mehr auf.
- **Aufnahme im Hintergrund**: Programm darf hinter anderen Fenstern liegen; minimierte Programme holt
  AluPC unter Windows automatisch im Hintergrund zurück (ohne sie nach vorne zu holen).
- Behoben: Aufnahme eines Programms, in dem sich nichts bewegt, wurde alle paar Sekunden neu gestartet
  (Flackern/„hängt“); „Anklicken (4 Sekunden)“ schloss den Dialog zu früh.
- Hinweis: Bei gesperrtem Computer (Win+L) zeigt kein Programm etwas auf Monitor 2 – das ist eine
  Sperre von Windows/KDE, nicht von AluPC.

### Bekannte Grenzen
Die automatischen Tests laufen ohne echte Monitore, Kameras und Fingerabdrucksensoren. Bitte Fehler
mit Screenshot melden. Details im README unter „Ehrliche Grenzen“.
