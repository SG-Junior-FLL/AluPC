// Pin-Finder für die Tastenbox: zeigt im Serial Monitor (115200), an welchem Pin eine Taste WIRKLICH hängt.
// Alle Pins mit Pull-up lesen; Taste drücken → „Pin 14 gedrückt“. Mit Buzzer an A2 piept es zusätzlich.
// Nichts wird auf Plus geschaltet – kann nichts kaputt machen.
//
// Pro Micro: erwartet sind Tasten an 2 3 4 5 6 7 8 14 15. Meldet sich eine Taste an einem anderen Pin
// (oder gar nicht), steckt der Draht in der falschen Reihe oder hat keinen Kontakt.

#if defined(__AVR_ATmega32U4__)
// Alle Pins, die am Pro Micro herausgeführt sind (A0 = 18, A1 = 19, A3 = 21; A2 = Buzzer).
const uint8_t PINS[] = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 14, 15, 16, 18, 19, 21};
const char* NAME[] = {"0 (RX)", "1 (TX)", "2", "3", "4", "5", "6", "7", "8", "9 (LED gruen)", "10 (LED rot)",
                      "14", "15", "16 (LED blau)", "A0 (Regler)", "A1", "A3"};
const char* ERWARTET[] = {"", "", "Taste 1", "Taste 2", "Taste 3", "Taste 4", "Taste 5", "Taste 6", "Taste 7", "",
                          "", "Taste 8", "Taste 9", "", "", "", ""};
#else
const uint8_t PINS[] = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 17};
const char* NAME[] = {"0 (RX)", "1 (TX)", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11 (LED rot)",
                      "12 (LED gruen)", "13 (LED blau)", "A0 (Regler)", "A1", "A3"};
const char* ERWARTET[] = {"", "", "Taste 1", "Taste 2", "Taste 3", "Taste 4", "Taste 5", "Taste 6", "Taste 7",
                          "Taste 8", "Taste 9", "", "", "", "", "", ""};
#endif
const uint8_t N = sizeof(PINS);
const uint8_t BUZZER = A2;

bool unten[N];
uint32_t zuletzt[N];

void jtagAus() {
#if defined(__AVR_ATmega32U4__)
  MCUCR |= (1 << JTD);  // A0–A3 sind auch JTAG-Pins – abschalten
  MCUCR |= (1 << JTD);
#endif
}

void setup() {
  jtagAus();
  for (uint8_t i = 0; i < N; i++) pinMode(PINS[i], INPUT_PULLUP);
  pinMode(BUZZER, OUTPUT);
  Serial.begin(115200);
  while (!Serial && millis() < 4000) {}
  delay(50);
  Serial.println(F("Pin-Finder: Tasten einzeln druecken."));
  Serial.print(F("Schon beim Start auf Minus (LED-Pins sind hier normal): "));
  bool keiner = true;
  for (uint8_t i = 0; i < N; i++) {
    unten[i] = digitalRead(PINS[i]) == LOW;
    if (unten[i]) { Serial.print(NAME[i]); Serial.print(F("  ")); keiner = false; }
  }
  Serial.println(keiner ? F("keiner") : F(""));
  tone(BUZZER, 1047, 80);
}

void loop() {
  for (uint8_t i = 0; i < N; i++) {
    bool jetzt = digitalRead(PINS[i]) == LOW;
    if (jetzt == unten[i] || millis() - zuletzt[i] < 30) continue;  // entprellen
    unten[i] = jetzt;
    zuletzt[i] = millis();
    Serial.print(F("Pin "));
    Serial.print(NAME[i]);
    Serial.print(jetzt ? F(" gedrueckt") : F(" los"));
    if (jetzt && ERWARTET[i][0]) { Serial.print(F("  = ")); Serial.print(ERWARTET[i]); }
    if (jetzt && !ERWARTET[i][0]) Serial.print(F("  <- hier sollte keine Taste sein!"));
    Serial.println();
    if (jetzt) tone(BUZZER, 400 + 60 * i, 60);
  }
}
