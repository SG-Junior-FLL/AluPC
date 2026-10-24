// Buzzer-Test für die Tastenbox: jede Taste spielt ein anderes Lied, die LEDs blinken im Takt mit.
// Taste während eines Lieds drücken = Lied stoppt.
//
// Anschluss:   Buzzer + (langes Bein) → A2      Buzzer − → Minus (GND)
//              Tasten wie im Tastenbox-Programm (anderes Beinchen an Minus), LEDs wie gehabt.
//              Der Regler wird hier nicht benutzt.
//
//                 Pro Micro (Leonardo)                 Nano
//   Tasten 1–9 :  D2 D3 D4 D5 D6 D7 D8 D14 D15         D2 D3 D4 D5 D6 D7 D8 D9 D10
//   LEDs       :  rot D10 · grün D9 · blau D16         rot D11 · grün D12 · blau D13
//   Buzzer     :  A2                                   A2
//
// Passiver Buzzer (unten grüne Platine sichtbar): spielt richtige Töne.
// Aktiver Buzzer (unten schwarz vergossen): piept nur im Rhythmus, Töne klingen alle ähnlich.
// Serial Monitor (115200) zeigt, welches Lied läuft.

#if defined(__AVR_ATmega32U4__)
const uint8_t TASTE[9] = {2, 3, 4, 5, 6, 7, 8, 14, 15};
const uint8_t LED[3] = {10, 9, 16};   // rot, grün, blau
#else
const uint8_t TASTE[9] = {2, 3, 4, 5, 6, 7, 8, 9, 10};
const uint8_t LED[3] = {11, 12, 13};
#endif
const uint8_t BUZZER = A2;

// Noten (Hz). 0 = Pause.
#define PAUSE 0
#define NC4 262
#define NE4 330
#define NGS4 415
#define NA4 440
#define NAS4 466
#define NB4 494
#define NC5 523
#define NCS5 554
#define ND5 587
#define NDS5 622
#define NE5 659
#define NF5 698
#define NFS5 740
#define NG5 784
#define NGS5 831
#define NA5 880
#define NB5 988
#define NC6 1047
#define ND6 1175
#define NE6 1319
#define NG6 1568

// Je Note: Tonhöhe, Länge (4 = Viertel, 8 = Achtel, 2 = Halbe; negativ = punktiert).
// Bekannte Stücke aus Spielen, Filmen und Werbung – alle gemeinfrei (gleiche Liste wie in AluPC).
const int16_t TETRIS[] PROGMEM = {
  NE5, 4, NB4, 8, NC5, 8, ND5, 4, NC5, 8, NB4, 8, NA4, 4, NA4, 8, NC5, 8, NE5, 4, ND5, 8, NC5, 8, NB4, -4, NC5, 8,
  ND5, 4, NE5, 4, NC5, 4, NA4, 4, NA4, 4, PAUSE, 4, PAUSE, 8, ND5, 4, NF5, 8, NA5, 4, NG5, 8, NF5, 8, NE5, -4,
  NC5, 8, NE5, 4, ND5, 8, NC5, 8, NB4, 4, NB4, 8, NC5, 8, ND5, 4, NE5, 4, NC5, 4, NA4, 4, NA4, 4};
const int16_t BERGKOENIG[] PROGMEM = {
  NA4, 8, NB4, 8, NC5, 8, ND5, 8, NE5, 8, NC5, 8, NE5, 4, NDS5, 8, NB4, 8, NDS5, 4, ND5, 8, NAS4, 8, ND5, 4,
  NA4, 8, NB4, 8, NC5, 8, ND5, 8, NE5, 8, NC5, 8, NE5, 8, NA5, 8, NG5, 8, NE5, 8, NC5, 8, NE5, 8, NG5, 2};
const int16_t CANCAN[] PROGMEM = {
  NC5, 4, ND5, 8, NF5, 8, NE5, 8, ND5, 8, NG5, 4, NG5, 4, NG5, 8, NA5, 8, NE5, 8, NF5, 8, ND5, 4, ND5, 4, ND5, 8,
  NF5, 8, NE5, 8, ND5, 8, NC5, 8, NC6, 8, NB5, 8, NA5, 8, NG5, 8, NF5, 8, NE5, 8, ND5, 8, NC5, 2};
const int16_t TURCA[] PROGMEM = {
  NB4, 16, NA4, 16, NGS4, 16, NA4, 16, NC5, 8, PAUSE, 8, ND5, 16, NC5, 16, NB4, 16, NC5, 16, NE5, 8, PAUSE, 8,
  NF5, 16, NE5, 16, NDS5, 16, NE5, 16, NB5, 16, NA5, 16, NGS5, 16, NA5, 16, NB5, 16, NA5, 16, NGS5, 16, NA5, 16,
  NC6, 4, NA5, 8, NC6, 8, NB5, 8, NA5, 8, NG5, 8, NA5, 8, NB5, 8, NA5, 8, NG5, 8, NA5, 8, NG5, 8, NFS5, 8, NE5, 4};
const int16_t TELL[] PROGMEM = {
  NG5, 16, NG5, 16, NG5, 8, NG5, 16, NG5, 16, NG5, 8, NG5, 16, NG5, 16, NC6, 8, ND6, 8, NE6, 8, NG5, 16, NG5, 16,
  NG5, 8, NG5, 16, NG5, 16, NG5, 8, NC6, 16, NE6, 16, ND6, 8, NB5, 8, NG5, 8, NG5, 16, NG5, 16, NG5, 8, NG5, 16,
  NG5, 16, NG5, 8, NG5, 16, NG5, 16, NC6, 8, ND6, 8, NE6, 8, NC6, 8, NE6, 8, NG6, 4, NE6, 8, NC6, 8, ND6, 8,
  NB5, 8, NC6, 4};
const int16_t TOCCATA[] PROGMEM = {
  NA5, 32, NG5, 32, NA5, -4, PAUSE, 8, NG5, 32, NF5, 32, NE5, 32, ND5, 32, NCS5, 8, ND5, 4, PAUSE, 4, NA5, 32,
  NG5, 32, NA5, -4, PAUSE, 8, NE5, 8, NF5, 8, NCS5, 8, ND5, 2};
const int16_t ELISE[] PROGMEM = {
  NE5, 16, NDS5, 16, NE5, 16, NDS5, 16, NE5, 16, NB4, 16, ND5, 16, NC5, 16, NA4, -8, NC4, 16, NE4, 16, NA4, 16,
  NB4, -8, NE4, 16, NGS4, 16, NB4, 16, NC5, -8, NE4, 16, NE5, 16, NDS5, 16, NE5, 16, NDS5, 16, NE5, 16, NB4, 16,
  ND5, 16, NC5, 16, NA4, -8, NC4, 16, NE4, 16, NA4, 16, NB4, -8, NE4, 16, NC5, 16, NB4, 16, NA4, 2};
const int16_t FREUDE[] PROGMEM = {
  NE5, 4, NE5, 4, NF5, 4, NG5, 4, NG5, 4, NF5, 4, NE5, 4, ND5, 4, NC5, 4, NC5, 4, ND5, 4, NE5, 4, NE5, -4, ND5, 8,
  ND5, 2, NE5, 4, NE5, 4, NF5, 4, NG5, 4, NG5, 4, NF5, 4, NE5, 4, ND5, 4, NC5, 4, NC5, 4, ND5, 4, NE5, 4, ND5, -4,
  NC5, 8, NC5, 2};
const int16_t GAMEOVER[] PROGMEM = {
  NC5, 4, NC5, -8, NC5, 16, NC5, 4, NDS5, -8, ND5, 16, ND5, -8, NC5, 16, NC5, -8, NB4, 16, NC5, 2};

struct Lied { const int16_t* noten; uint8_t anzahl; uint16_t tempo; const char* name; };
#define LIED(n, t, name) {n, sizeof(n) / sizeof(n[0]) / 2, t, name}
const Lied LIEDER[9] = {
  LIED(TETRIS, 144, "Tetris (Korobeiniki)"),
  LIED(BERGKOENIG, 140, "In der Halle des Bergkoenigs"),
  LIED(CANCAN, 150, "Can-Can"),
  LIED(TURCA, 120, "Tuerkischer Marsch"),
  LIED(TELL, 150, "Wilhelm Tell"),
  LIED(TOCCATA, 60, "Toccata d-Moll"),
  LIED(ELISE, 80, "Fuer Elise"),
  LIED(FREUDE, 120, "Ode an die Freude"),
  LIED(GAMEOVER, 60, "Game Over (Trauermarsch)"),
};

void jtagAus() {
#if defined(__AVR_ATmega32U4__)
  // A0–NA3 sind beim ATmega32U4 auch JTAG-Pins; ohne Abschalten bleibt A2 bei manchen Nachbauten stumm.
  MCUCR |= (1 << JTD);
  MCUCR |= (1 << JTD);
#endif
}

int8_t gedrueckt() {  // Nummer der gedrückten Taste (0–8) oder -1
  for (uint8_t i = 0; i < 9; i++)
    if (digitalRead(TASTE[i]) == LOW) return i;
  return -1;
}

void warteLos() {  // bis alle Tasten losgelassen sind (+ entprellen)
  while (gedrueckt() >= 0) delay(5);
  delay(30);
}

void leds(uint8_t farbe) {  // 0 = rot, 1 = grün, 2 = blau, 3 = aus
  for (uint8_t i = 0; i < 3; i++) digitalWrite(LED[i], i == farbe ? HIGH : LOW);
}

// Spielt ein Lied. Rückgabe false = abgebrochen (Taste gedrückt).
bool spiele(const Lied& lied) {
  uint32_t ganze = 240000UL / lied.tempo;  // ms für eine ganze Note
  for (uint8_t i = 0; i < lied.anzahl; i++) {
    int16_t ton = pgm_read_word(&lied.noten[2 * i]);
    int16_t teil = pgm_read_word(&lied.noten[2 * i + 1]);
    uint32_t dauer = ganze / abs(teil);
    if (teil < 0) dauer = dauer * 3 / 2;
    if (ton) {
      tone(BUZZER, ton, dauer * 9 / 10);  // 10 % Pause, damit gleiche Töne getrennt klingen
      leds(i % 3);
    } else {
      leds(3);
    }
    uint32_t start = millis();
    while (millis() - start < dauer) {
      if (gedrueckt() >= 0) { noTone(BUZZER); leds(3); return false; }
    }
  }
  noTone(BUZZER);
  leds(3);
  return true;
}

void setup() {
  jtagAus();
  for (uint8_t i = 0; i < 9; i++) pinMode(TASTE[i], INPUT_PULLUP);
  for (uint8_t i = 0; i < 3; i++) pinMode(LED[i], OUTPUT);
  pinMode(BUZZER, OUTPUT);
  Serial.begin(115200);
  // Startsignal: kurzer Dreiklang
  const uint16_t start[4] = {NC5, NE5, NG5, NC6};
  for (uint8_t i = 0; i < 4; i++) { tone(BUZZER, start[i], 90); leds(i % 3); delay(110); }
  leds(3);
  Serial.println(F("Buzzer-Test: Taste 1-9 druecken. Nochmal druecken = Stopp."));
}

void loop() {
  int8_t t = gedrueckt();
  if (t < 0) return;
  warteLos();
  Serial.print(F("Taste "));
  Serial.print(t + 1);
  Serial.print(F(": "));
  Serial.println(LIEDER[t].name);
  if (!spiele(LIEDER[t])) {
    Serial.println(F("  gestoppt"));
    warteLos();
  }
}
