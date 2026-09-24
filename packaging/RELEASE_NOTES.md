## AluPC – Monitor 2 steuern (Kubuntu & Windows 11)

### Downloads
| System | Datei | Hinweis |
|---|---|---|
| **Windows 11** | `AluPC-Setup-….exe` | Installer (Startmenü, Deinstallation) |
| Windows 11 | `AluPC-windows-portable-….zip` | ohne Installation: entpacken, `AluPC.exe` starten |
| **Kubuntu / Ubuntu** (22.04, 24.04 und neuer) | `alupc_…_amd64.deb` | `sudo apt install ./alupc_…_amd64.deb` – danach im Startmenü |
| Linux (x86_64) | `AluPC-linux-x86_64-….tar.gz` | ohne Installation: entpacken, `AluPC/AluPC` starten |

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
