// AluPC-Tasten – Programm für den Arduino Pro Micro (ATmega32U4)
//
// 9 Tasten (3 × 3), 1 Drehregler (Lautstärke), 1 LED oder ein LED-Streifen.
// In der Arduino-IDE: Board „Arduino Leonardo“ wählen (der Pro Micro ist technisch gleich), Anschluss wählen,
// hochladen. AluPC findet die Box danach von selbst (Setup → Tastenbox).
//
// Anschluss:
//   Tasten 1–9 : D2 D3 D4 D5 D6 D7 D8 D14 D15 – jeweils das andere Bein an GND (keine Widerstände nötig)
//   Regler     : Potentiometer 10 kΩ linear – Mitte an A0, die beiden Außenbeine an VCC und GND
//   LED        : D9 → Widerstand 220 Ω → LED (langes Bein) → kurzes Bein an GND
//   Streifen   : WS2812B: DIN an D10, 5V an VCC, GND an GND (am USB höchstens ~8–10 LEDs, halbe Helligkeit)
//
// Was die Box an den PC schickt (115200 Baud, eine Zeile je Meldung):
//   HALLO ALUPC-TASTEN 1   – Antwort auf „WER?“
//   TASTE n                – Taste n gedrückt (1–9)
//   LAUT n                 – Regler steht auf n Prozent (0–100), nur wenn er sich bewegt hat, und auf „LAUT?“
// Was der PC schickt: „WER?“, „LAUT?“, „LED n“ (Helligkeit 0–100, 0 = aus).

// #define STREIFEN 8   // Zeile einschalten (// weg) für einen WS2812B-Streifen mit 8 LEDs (Bibliothek „Adafruit NeoPixel“)

#ifdef STREIFEN
#include <Adafruit_NeoPixel.h>
Adafruit_NeoPixel streifen(STREIFEN, 10, NEO_GRB + NEO_KHZ800);
#endif

const uint8_t TASTEN[9] = {2, 3, 4, 5, 6, 7, 8, 14, 15};
const uint8_t REGLER = A0;
const uint8_t LED = 9;

bool gedrueckt[9];
unsigned long zuletzt[9];
int regler = -1;          // zuletzt gemeldeter Wert (0–100)
float glatt = 0;          // geglätteter Messwert (Poti rauscht etwas)
String zeile;

void ledSetzen(int prozent) {
  prozent = constrain(prozent, 0, 100);
  analogWrite(LED, map(prozent, 0, 100, 0, 255));
#ifdef STREIFEN
  for (int i = 0; i < STREIFEN; i++) streifen.setPixelColor(i, streifen.Color(0, map(prozent, 0, 100, 0, 120), 40));
  streifen.show();
#endif
}

void setup() {
  Serial.begin(115200);
  for (uint8_t i = 0; i < 9; i++) {
    pinMode(TASTEN[i], INPUT_PULLUP);  // offen = HIGH, gedrückt = LOW
    gedrueckt[i] = false;
  }
  pinMode(LED, OUTPUT);
#ifdef STREIFEN
  streifen.begin();
#endif
  ledSetzen(0);
  glatt = analogRead(REGLER);
}

void befehl(String text) {
  text.trim();
  text.toUpperCase();
  if (text == "WER?") {
    Serial.println("HALLO ALUPC-TASTEN 1");
  } else if (text == "LAUT?") {
    Serial.print("LAUT ");
    Serial.println(regler < 0 ? 0 : regler);
  } else if (text.startsWith("LED ")) {
    ledSetzen(text.substring(4).toInt());
  }
}

void loop() {
  // Befehle vom PC
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') {
      befehl(zeile);
      zeile = "";
    } else if (zeile.length() < 40) {
      zeile += c;
    }
  }

  // Tasten (entprellt: 30 ms Ruhe nach jedem Wechsel)
  unsigned long jetzt = millis();
  for (uint8_t i = 0; i < 9; i++) {
    bool unten = digitalRead(TASTEN[i]) == LOW;
    if (unten != gedrueckt[i] && jetzt - zuletzt[i] > 30) {
      gedrueckt[i] = unten;
      zuletzt[i] = jetzt;
      if (unten) {
        Serial.print("TASTE ");
        Serial.println(i + 1);
      }
    }
  }

  // Regler: glätten, und erst melden, wenn er sich um mindestens 1 % bewegt hat
  glatt = glatt * 0.85 + analogRead(REGLER) * 0.15;
  int prozent = round(glatt * 100.0 / 1023.0);
  if (regler < 0 || abs(prozent - regler) >= 1) {
    if (regler < 0 || abs(glatt * 100.0 / 1023.0 - regler) > 0.7) {  // kein Hin-und-her an der Grenze
      regler = prozent;
      Serial.print("LAUT ");
      Serial.println(regler);
    }
  }
  delay(5);
}
