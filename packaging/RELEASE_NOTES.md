## AluPC – Bildschirm steuern (Kubuntu & Windows 11)

### Downloads
| System | Datei | Hinweis |
|---|---|---|
| **Windows 11** | `AluPC-Setup-….exe` | Installer (Startmenü, Deinstallation) |
| Windows 11 | `AluPC-windows-portable-….zip` | ohne Installation: entpacken, `AluPC.exe` starten |
| **Kubuntu / Ubuntu** (22.04, 24.04 und neuer) | `alupc_…_amd64.deb` | `sudo apt install ./alupc_…_amd64.deb` – danach im Startmenü |
| Linux (x86_64) | `AluPC-linux-x86_64-….tar.gz` | ohne Installation: entpacken, `AluPC/AluPC` starten |
| Kubuntu / Ubuntu | `AluPC-installieren.sh` | installiert die .deb daneben (oder lädt sie), wartet auf laufende Updates |

### Neu in 2.1.0 – Zusatzprogramme werden beim Deinstallieren mit entfernt
- **Windows:** AluPC merkt sich, welche Zusatzprogramme es **selbst neu** installiert hat – Bonjour und
  uxplay-windows (AirPlay), OpenRGB, FanControl, VB-CABLE (virtuelles Mikro), OBS Studio (virtuelle Kamera).
  Egal ob über den Installer oder später in AluPC. Beim Deinstallieren fragt AluPC, ob diese auch entfernt werden
  sollen. Programme, die du schon vorher hattest, werden nie angefasst.
- **Linux:** Pakete, die AluPC nachinstalliert, werden als „automatisch“ markiert. Nach `sudo apt remove alupc`
  entfernt `sudo apt autoremove` sie mit (der Hinweis steht beim Entfernen da). AluPCs eigene Einstellungsdateien
  für die virtuelle Kamera werden mit entfernt.
- Gilt für Installationen ab 2.1.0 – was ältere Versionen installiert haben, kennt AluPC nicht.
- **Nicht getestet** auf einem echten Windows-PC (Installieren und Deinstallieren mit winget) – nur automatische Tests.

2.0.0: drei Designs (Normal, Technisch, Holz mit 7 Holzarten) – siehe CHANGELOG.

### Frühere Versionen
[CHANGELOG](https://github.com/SG-Junior-FLL/AluPC/blob/main/docs/CHANGELOG.md)

### Grenzen
Tests laufen ohne echte Monitore, Kameras und Sensoren. Fehler bitte mit Screenshot melden.
