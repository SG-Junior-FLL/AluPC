## AluPC – Monitor 2 steuern (Kubuntu & Windows 11)

### Downloads
| System | Datei | Hinweis |
|---|---|---|
| **Windows 11** | `AluPC-Setup-….exe` | Installer (Startmenü, Deinstallation) |
| Windows 11 | `AluPC-windows-portable-….zip` | ohne Installation: entpacken, `AluPC.exe` starten |
| **Kubuntu / Ubuntu** (22.04, 24.04 und neuer) | `alupc_…_amd64.deb` | `sudo apt install ./alupc_…_amd64.deb` – danach im Startmenü |
| Linux (x86_64) | `AluPC-linux-x86_64-….tar.gz` | ohne Installation: entpacken, `AluPC/AluPC` starten |

### Neu in dieser Version (0.6.0) – Linux-Update
- **Spiegeln unter KDE/Wayland ohne Nachfrage**: kein Fenster „Welchen Bildschirm teilen?“ mehr –
  AluPC nimmt Monitor 1 direkt über KWin auf (auch Bild-in-Bild und Standbild). Gilt für das .deb
  und die portable Version; beim Start aus dem Quellcode fragt KDE weiterhin.
- **Fingerabdruck automatisch einrichten**: ein Klick installiert fehlende Pakete, sucht den Sensor,
  lernt den Finger an, testet ihn und schaltet die Anmeldung ein. Kein Treiber? AluPC erkennt den
  Sensor am USB und nennt mögliche Zusatztreiber. Unter Windows: Sensor suchen → Windows Hello → Test.
- **Logo**: Programmsymbol in allen Größen (16–512 px und SVG) für Startmenü, Taskleiste und Fenster;
  die portable Linux-Version trägt sich selbst ins Startmenü ein (vorher Standardsymbol unter Wayland).
  Das Symbol in der Taskleiste zeigt den Zustand mit einem kleinen, scharfen Abzeichen.

### Bekannte Grenzen
Die automatischen Tests laufen ohne echte Monitore, Kameras und Fingerabdrucksensoren. Bitte Fehler
mit Screenshot melden. Details im README unter „Ehrliche Grenzen“.
