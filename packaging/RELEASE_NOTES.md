## AluPC – Monitor 2 steuern (Kubuntu & Windows 11)

### Downloads
| System | Datei | Hinweis |
|---|---|---|
| **Windows 11** | `AluPC-Setup-….exe` | Installer (Startmenü, Deinstallation) |
| Windows 11 | `AluPC-windows-portable-….zip` | ohne Installation: entpacken, `AluPC.exe` starten |
| **Kubuntu / Ubuntu** (22.04, 24.04 und neuer) | `alupc_…_amd64.deb` | `sudo apt install ./alupc_…_amd64.deb` – danach im Startmenü |
| Linux (x86_64) | `AluPC-linux-x86_64-….tar.gz` | ohne Installation: entpacken, `AluPC/AluPC` starten |

### Neu in dieser Version (0.3.0)
- **Mauszeiger** ist auf Monitor 2 wieder sichtbar.
- **Monitor 2 bleibt vorne**: Ein Wächter holt das Bild zurück, wenn es verdeckt oder minimiert wird
  (z. B. Win+D). Windows: Taskleiste auf Monitor 2 wird ausgeblendet, solange AluPC dort etwas zeigt.
  KDE: Fenster wird über die Leisten gelegt.
- **Standbild zuverlässiger**: echtes Bildschirmfoto (auch Websites/Videos), kleines
  Schneeflocken-Symbol oben rechts (abschaltbar).
- **Steuern über die Taskleiste**: Klick aufs AluPC-Symbol = Schnellmenü, das Symbol zeigt den Zustand.
- **Tastenkürzel selbst wählen**: Kürzel anklicken, Tasten drücken – AluPCs eigene Kürzel sind
  währenddessen pausiert (vorher wurden sie beim Aufnehmen „weggeschnappt“).
- **Programm anzeigen**: AluPCs eigene Fenster erscheinen nicht mehr in der Liste; die Aufnahme
  verbindet sich neu, wenn der Fenstertitel wechselt oder kein Bild mehr kommt.
- **Timer neu**: läuft durch statt bei jedem Neuaufbau von vorn zu beginnen; Start/Pause,
  Neustart, ±1 Minute, Countdown oder Stoppuhr, Warnfarben; Schrift springt nicht mehr.
- **Sperren** = Computer sperren (Win+L bzw. Bildschirmsperre unter Linux). Die frühere
  AluPC-eigene Sperre mit PIN wurde entfernt.
- **Bildschirmschoner-Einstellungen** direkt über den Pfeil an der Kachel.

### Bekannte Grenzen
Die automatischen Tests laufen ohne echte Monitore, Kameras und Fingerabdrucksensoren. Bitte Fehler
mit Screenshot melden. Details im README unter „Ehrliche Grenzen“.
