## AluPC – Bildschirm steuern (Kubuntu & Windows 11)

### Downloads
| System | Datei | Hinweis |
|---|---|---|
| **Windows 11** | `AluPC-Setup-….exe` | Installer (Startmenü, Deinstallation) |
| Windows 11 | `AluPC-windows-portable-….zip` | ohne Installation: entpacken, `AluPC.exe` starten |
| **Kubuntu / Ubuntu** (22.04, 24.04 und neuer) | `alupc_…_amd64.deb` | `sudo apt install ./alupc_…_amd64.deb` – danach im Startmenü |
| Linux (x86_64) | `AluPC-linux-x86_64-….tar.gz` | ohne Installation: entpacken, `AluPC/AluPC` starten |
| Kubuntu / Ubuntu | `AluPC-installieren.sh` | installiert die .deb daneben (oder lädt sie), wartet auf laufende Updates |

### Neu in 0.141.0
- **Miracast:** empfangen unter Windows (Handy/Laptop → Bildschirm), senden an Miracast-Fernseher unter
  Windows (Win+K) und Linux (GNOME Network Displays). Kachel „Miracast“.
- Empfangen unter Linux geht nicht (kein gepflegter Miracast-Empfänger).
- **Nicht mit echten Miracast-Geräten getestet.**

### Frühere Versionen
[CHANGELOG](https://github.com/SG-Junior-FLL/AluPC/blob/main/docs/CHANGELOG.md)

### Grenzen
Tests laufen ohne echte Monitore, Kameras und Sensoren. Fehler bitte mit Screenshot melden.
