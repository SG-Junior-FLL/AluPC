# AluPC – Design „Regiepult“

AluPC entscheidet, was ein zweiter Bildschirm (Beamer, Fernseher) zeigt. Das Vorbild ist ein Bildmischer im
TV-Regieraum: ein großes Programmbild, darunter Tasten, und eine Leuchte zeigt, was gerade auf Sendung ist.
Aufbau und Funktionen bleiben wie bisher; das Aussehen folgt diesem Bild.

## Farben

| Name | Dunkel | Hell | Wofür |
|---|---|---|---|
| Grund | `#111316` Graphit | `#E6E8EB` Alu | Fensterhintergrund |
| Pult | `#191C20` | `#F6F7F8` | Karten, Gruppen, Seitenleiste |
| Taste | `#23272C` | `#FFFFFF` | Knöpfe, Eingabefelder, Kacheln |
| Fuge | `#30353C` | `#C9CED5` | Ränder, Trennlinien |
| Schrift / leise | `#ECEEF1` / `#9AA1AC` | `#15181C` / `#59616C` | Text |
| Akzent | wählbar (AluPC: `#5B8DEF`) | wählbar (AluPC: `#2F6FDB`) | Bedienung: Auswahl, Hauptknopf, Fokus |
| Sendung | `#E5484D` | `#D93A40` | nur „läuft auf dem Bildschirm“ (Tally-Leuchte) |
| Bereit | `#30A46C` | `#218358` | nur „bereit/verbunden“ |

Dunkel ist Standard (Regieräume sind dunkel); Hell „Alu“ bleibt wählbar. Die Handy-Seite ist immer dunkel.

Akzent = Bedienung, Rot = Sendung. Rot erscheint nirgends sonst als Schmuck (Löschen-Knöpfe nutzen
Rot nur als Schrift).

## Schrift

- **Barlow Semi Condensed** (SemiBold/Bold): Seitentitel, Gruppentitel, Kachel- und Tastenbeschriftung – schmal
  und technisch wie Pultbeschriftungen.
- **Inter**: Fließtext, Formulare, Erklärungen.
- **JetBrains Mono**: nur echte Werte (Zeiten, Adressen, Codes).
- Keine Großbuchstaben-Etiketten mit Sperrung; Abschnittsnamen in normaler Schreibweise.

Größen (pt): Seitentitel 22 · Gruppentitel 12 · Kachel 12 · Text 10 · klein 8.5.

## Aufbau

```
┌──────┬──────────────────────────────────────┐
│ Logo │ Titel der Seite                       │
│ ──── │ ┌──────────────────────────────────┐  │
│ Navi │ │ Programmbild (Monitor 2)  ● Live │  │  ← Startseite: das Programmbild ist der Mittelpunkt
│      │ └──────────────────────────────────┘  │
│      │ [● Taste][  Taste ][  Taste ][ … ]    │  ← Kacheln = Tasten mit Leuchte
│ Bild │                                       │
└──────┴──────────────────────────────────────┘
```

- Links ausgerichtet, keine zentrierten Inhalte (außer Anzeigen auf Monitor 2).
- Rundungen nach Rang: Pult 10 px, Taste/Feld 6 px, Etikett ganz rund. Keine Schatten, keine Verläufe, kein Glas –
  Tiefe nur über Fugen und eine hellere Oberkante an Tasten.
- Aktive Kachel: rote Leuchte oben links + roter Balken an der Oberkante, Fläche bleibt ruhig.

## Regler

Schieberegler sind Fader wie am Mischpult: dunkler Schlitz, Akzentfarbe bis zur Kappe, Kappe mit Griffrille.
Auf der Startseite steht neben dem Programmbild ein kleines Regler-Pult (senkrechte Fader mit Skala):
„PC“ (Lautstärke des Computers) und „Medien“ (Ton von Video/Website auf Monitor 2, nur wenn etwas mit Ton läuft).

## Grundsätze

1. Mutig nur an einer Stelle: das Programmbild mit der Sendungsleuchte. Alles andere ist ruhig.
2. Rot bedeutet immer „läuft gerade“ – überall gleich (App, Handy-Seite, Anzeigen).
3. Keine Deko-Bewegung; Bewegung nur als Antwort auf eine Aktion.
4. Klare, kurze Texte in normaler Schreibweise; Knöpfe sagen, was passiert.

## Abgleich mit dem Auftrag

- Erster Entwurf war fast schwarz mit einer grellen Farbe – zu nah am Standard „dunkel + eine Neonfarbe“.
  Geändert: Graphit statt Schwarz, ein ruhiger Hellmodus „Alu“ gleichwertig, Rot nur als Zustandsfarbe.
- Großbuchstaben-Etiketten über Abschnitten (bisher z. B. „ANZEIGEN“) entfernt – reine Vorlagen-Optik.
- Gleich runde Karten mit weichem Schatten überall (bisher) ersetzt durch Rang-Rundungen ohne Schatten.
