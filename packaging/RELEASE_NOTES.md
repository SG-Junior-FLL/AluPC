## AluPC – Bildschirm steuern (Kubuntu & Windows 11)

### Downloads
| System | Datei | Hinweis |
|---|---|---|
| **Windows 11** | `AluPC-Setup-….exe` | Installer (Startmenü, Deinstallation) |
| Windows 11 | `AluPC-windows-portable-….zip` | ohne Installation: entpacken, `AluPC.exe` starten |
| **Kubuntu / Ubuntu** (22.04, 24.04 und neuer) | `alupc_…_amd64.deb` | `sudo apt install ./alupc_…_amd64.deb` – danach im Startmenü |
| Linux (x86_64) | `AluPC-linux-x86_64-….tar.gz` | ohne Installation: entpacken, `AluPC/AluPC` starten |
| Kubuntu / Ubuntu | `AluPC-installieren.sh` | installiert die .deb daneben (oder lädt sie), wartet auf laufende Updates |

### Neu in 2.0.0 – drei Designs zum Umschalten
- **Setup → Darstellung → Stil:** drei Designs für die ganze App (Hauptfenster, Setup, Dialoge, Handy-/iPad-Seite).
  Umschalten wirkt sofort.
  - **Normal** (Standard): modern, weich und rund – schwebende Seitenleiste, große runde Kacheln, Knöpfe als Pillen,
    dicke runde Lautstärke-Regler.
  - **Technisch:** dicht und eckig, Kacheln als Zeilen, echte Messwerte in Ziffernschrift (Ausgang, Auflösung, Hz,
    „läuft seit 0:12:34“), Regler mit Skala 0–100.
  - **Holz:** echtes Furnier als Grund und Kacheln, **7 Holzarten** (Nussbaum, Kirsche, Wenge, Räuchereiche, Eiche,
    Kiefer, Ahorn), gravierte Schrift, rote Lampe zeigt, was läuft. Helles Holz → dunkle Schrift, dunkles Holz →
    helle Schrift (alle Kombinationen auf Lesbarkeit geprüft).
- **Nur echte Angaben:** keine Fachkürzel wie „CH 07“, „PGM“ oder „STBY“ mehr – Zustände heißen „Läuft“, „An“,
  „Aktiv“ oder zeigen die Zeit.
- **Setup übersichtlicher:** Bereiche mit kurzer Beschreibung darunter, Stil-Auswahl mit Vorschaubildern.
- **Handy-/iPad-Seite** übernimmt Stil, Farben, Holzart und Schrift vom PC.
- **Nicht getestet** auf echten Monitoren, Handys und iPads – nur automatische Tests und Bildschirmfotos.

### Frühere Versionen
[CHANGELOG](https://github.com/SG-Junior-FLL/AluPC/blob/main/docs/CHANGELOG.md)

### Grenzen
Tests laufen ohne echte Monitore, Kameras und Sensoren. Fehler bitte mit Screenshot melden.
