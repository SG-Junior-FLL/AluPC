## AluPC – Bildschirm steuern (Kubuntu & Windows 11)

### Downloads
| System | Datei | Hinweis |
|---|---|---|
| **Windows 11** | `AluPC-Setup-….exe` | Installer (Startmenü, Deinstallation) |
| Windows 11 | `AluPC-windows-portable-….zip` | ohne Installation: entpacken, `AluPC.exe` starten |
| **Kubuntu / Ubuntu** (22.04, 24.04 und neuer) | `alupc_…_amd64.deb` | `sudo apt install ./alupc_…_amd64.deb` – danach im Startmenü |
| Linux (x86_64) | `AluPC-linux-x86_64-….tar.gz` | ohne Installation: entpacken, `AluPC/AluPC` starten |
| Kubuntu / Ubuntu | `AluPC-installieren.sh` | installiert die .deb daneben (oder lädt sie), wartet auf laufende Updates |

### Neu in 1.2.0 – mehr Regiepult
- **Regler wie am Mischpult:** Auf der Startseite steht neben dem Programmbild ein Regler-Pult mit senkrechten
  Fadern: „PC“ (Lautstärke des Computers) und „Medien“ (Ton von Video/Website auf dem Bildschirm, nur wenn etwas
  mit Ton läuft). Alle anderen Schieberegler sehen jetzt ebenfalls wie Fader aus (auch auf der Handy-Seite).
- **Mehr Dunkelmodus:** dunklere Graphit-Töne; Dunkel ist Standard. Wer bisher „Wie das System“ hatte (die alte
  Voreinstellung), bekommt einmal Dunkel – „Hell“ bleibt wählbar. Die Handy-/iPad-Seite ist immer dunkel.
- **Nicht getestet** auf echten Geräten. Der PC-Fader braucht einen Audio-Dienst (Windows: Core Audio,
  Linux: PipeWire/PulseAudio); ohne ist er ausgegraut.

### Frühere Versionen
[CHANGELOG](https://github.com/SG-Junior-FLL/AluPC/blob/main/docs/CHANGELOG.md)

### Grenzen
Tests laufen ohne echte Monitore, Kameras und Sensoren. Fehler bitte mit Screenshot melden.
