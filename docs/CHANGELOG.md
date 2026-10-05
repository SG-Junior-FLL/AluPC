# AluPC – frühere Neuerungen

Die aktuellen Neuerungen stehen in den [Release-Notizen](../packaging/RELEASE_NOTES.md) und auf der
[Release-Seite](https://github.com/SG-Junior-FLL/AluPC/releases).

## Neu in 0.100: Anmeldeseite auch unter Windows, besserer Abgleich
- **Spiele-WLAN mit Anmeldeseite unter Linux und Windows** (einmal Passwort bzw. „Ja“) – klappt auch ohne Internet
  am PC. Hotspot und Spiele-WLAN sind unter Linux unsichtbar (QR-Code oder Name + Passwort).
- **Dual-Boot-Abgleich** führt einzelne Einträge zusammen, übersetzt Bild-/Video-Pfade zwischen Windows und Linux und
  kopiert Dateien, die nur auf einem System liegen, in den Sync-Ordner. Neu dabei: Sprache, Spiele, Hotspot, Extras.

## Neu in 0.96/0.97: PC steuern, Programme, Hotspot, Spiele-WLAN

- **Den ganzen PC steuern** (Sprache, Befehlssuche `Strg+K`, Handy-Karte „PC“): „lauter“, „Lautstärke auf 30“,
  „stumm“, „öffne Firefox/Spotify/…“ (sucht im Startmenü bzw. in den .desktop-Dateien), „öffne YouTube“,
  „suche nach …“, „spiel … auf YouTube“, „Fenster schließen/minimieren“, „zeig den Desktop“, „mach einen
  Screenshot“ (Bilder/AluPC). **Herunterfahren, Neustart, Ruhezustand, Abmelden nur nach Rückfrage** („Sag Ja“) und
  nie vom Handy. Linux: Lautstärke über wpctl/pactl, Fenster über KDE-Kurzbefehle (geht auch unter Wayland) bzw.
  X11-Tasten. Windows: Medientasten (2 %-Schritte) und Tastenkürzel.
- **Programme auf der Startseite** (0.97): Startseite anpassen → „Programm …“ → Kachel im Bereich „Programme“.
- **Hotspot-Kachel** (0.97): eigenes WLAN an/aus, Name/Passwort/QR über den Pfeil.
- **Spiele-WLAN** (0.97, Minispiele-Fenster): offen, Handys bekommen beim Verbinden die Anmeldeseite mit
  „Mitspielen“ und „AluPC steuern“ (nur mit Code); geht aus, wenn die Minispiele enden. Anmeldeseite seit 0.100 auch unter Windows.
- **Handy freigeben** (0.98): statt Code „Am PC freigeben lassen“ → am PC „Erlauben / Ablehnen“; erlaubte Geräte
  steuern danach ohne Code (Setup → Handy & Kamera: Freigaben löschen).
- **Minispiele**: neu **Quiz** (A/B/C/D, schneller = mehr Punkte), **Lichtrenner** (Leuchtspuren wie „Tron“),
  **Schere, Stein, Papier** (alle gegen alle). Spiele-Fenster → **WLAN / Hotspot**: eigenes WLAN starten
  (Linux: NetworkManager; Windows: Mobiler Hotspot) oder vorhandenes WLAN eintragen – die Lobby zeigt dann
  **① WLAN-QR-Code** und **② Spiel-QR-Code**: Handy scannt beide, nichts abtippen.
- **Ausführen-Kacheln (wie Win+R)**: eigene Kachel → „Ausführen“: Programm, Programm mit Argumenten, Datei,
  Ordner, Webseite oder URI (`ms-settings:`) – ein Befehl für beide Systeme oder getrennt für Windows und Linux
  (Dual-Boot: die Kachel gibt es auf beiden). Auch in der Befehlssuche: `>` davor, z. B. `> notepad`.
- **Dual-Boot-Abgleich zuverlässiger**: Haben beide Systeme Verschiedenes geändert, wird zusammengeführt (vorher
  gewann eine Seite ganz). Ordner woanders eingehängt (Linux-Pfad oder Laufwerksbuchstabe geändert) → wird
  wiedergefunden. Abgleich zusätzlich jede Minute. Findet AluPC beim Start den Ordner des anderen Systems, verbindet
  es sich ohne Klicken.
- **Linux mit Wayland**: Handy als Fernbedienung/Touchpad und „Fenster schließen“ gehen jetzt über `ydotool`
  (empfohlenes Paket; der Dienst `ydotoold` muss laufen).
- **QR-Codes besser scannbar**: 4 Module weißer Rand (Norm), jedes Modul gleich viele ganze Pixel, stehen still,
  in der App größer und per Klick bildschirmgroß.

