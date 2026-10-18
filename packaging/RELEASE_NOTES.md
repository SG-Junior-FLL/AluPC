## AluPC – Bildschirm steuern (Kubuntu & Windows 11)

### Downloads
| System | Datei | Hinweis |
|---|---|---|
| **Windows 11** | `AluPC-Setup-….exe` | Installer (Startmenü, Deinstallation) |
| Windows 11 | `AluPC-windows-portable-….zip` | ohne Installation: entpacken, `AluPC.exe` starten |
| **Kubuntu / Ubuntu** (22.04, 24.04 und neuer) | `alupc_…_amd64.deb` | `sudo apt install ./alupc_…_amd64.deb` – danach im Startmenü |
| Linux (x86_64) | `AluPC-linux-x86_64-….tar.gz` | ohne Installation: entpacken, `AluPC/AluPC` starten |
| Kubuntu / Ubuntu | `AluPC-installieren.sh` | installiert die .deb daneben (oder lädt sie), wartet auf laufende Updates |

### Neu in 1.0.0
- **Zeichnen am iPad/Handy ohne spürbare Verzögerung:** dauerhafte Verbindung (WebSocket) statt Abfragen – jedes
  neue Bild vom PC kommt sofort, Striche und Zoom gehen ohne Umweg raus. Der PC zeichnet ein neues Bild, sobald sich
  etwas ändert. Eigene Striche werden nach ~0,05–0,1 s vom PC-Bild übernommen (vorher ~0,25 s, davor über 1 s).
- **Chromecast verbindet schneller:** Verbinden und Player-Start laufen gleichzeitig mit dem Video-Start statt
  danach; im Fenster steht der Schritt („Starte Player …“, „Puffert …“). Kürzere Video-Stücke (0,5 s).
- **Kleines Fenster:** nichts wird mehr rechts abgeschnitten (Audio, Gäste, alle Setup-Bereiche) – Karten
  stapeln sich, Knopfreihen brechen um, Beschriftungen stehen über den Feldern. Mindestbreite 600 px.
- **Handy-Seite „Folien“:** klare Anzeige, wenn Tasten nicht gehen.
- **Nicht getestet** mit echtem iPad, Chromecast oder Apple TV – nur Browser-Test und nachgebaute Geräte
  (Chromecast-Nachbau: Bild-Anfrage nach 0,7 s; ein echter Fernseher braucht für den Player-Start länger).

### Frühere Versionen
[CHANGELOG](https://github.com/SG-Junior-FLL/AluPC/blob/main/docs/CHANGELOG.md)

### Grenzen
Tests laufen ohne echte Monitore, Kameras und Sensoren. Fehler bitte mit Screenshot melden.
