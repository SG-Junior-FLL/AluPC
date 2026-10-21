// AluPC-Tasten – Programm für die Tastenbox (Arduino Pro Micro oder Arduino Nano)
//
// 9 Tasten (3 × 3), 1 Drehregler (was er regelt, stellt man in AluPC ein), LEDs oder ein LED-Streifen.
// In der Arduino-IDE das Board wählen – Pro Micro: „Arduino Leonardo“ (technisch gleich), Nano: „Arduino Nano“
// (bei Nachbauten evtl. Prozessor „ATmega328P (Old Bootloader)“) –, Anschluss wählen, hochladen.
// AluPC findet die Box danach von selbst (Seite „Tastenbox“). Die Pins passen sich dem Board an:
//
//                 Pro Micro                        Nano (und Uno/Mega, z. B. in der Wokwi-Simulation)
//   Tasten 1–9 :  D2 D3 D4 D5 D6 D7 D8 D14 D15       D2 D3 D4 D5 D6 D7 D8 D9 D10
//   Regler     :  A0                                 A0
//   LEDs       :  D9                                 D11
//   Streifen   :  D10                                D12
//
//   Tasten: jeweils das andere Bein an GND (keine Widerstände nötig).
//   Regler: Potentiometer 10 kΩ linear – Mitte an A0, die beiden Außenbeine an 5V/VCC und GND.
//   LEDs:   Pin → je LED ein eigener Widerstand (1 kΩ; nur eine LED: 220 Ω) → langes Bein, kurzes Bein an GND.
//   Streifen/RGB-LEDs (WS2812B, PL9823): DIN an den Streifen-Pin, 5V, GND (am USB höchstens ~8–10 LEDs).
//
// Was die Box an den PC schickt (115200 Baud, eine Zeile je Meldung):
//   HALLO ALUPC-TASTEN 3 NANO – Antwort auf „WER?“ (und einmal beim Start); 3 = Programmversion, dann das Board
//   TASTE n                   – Taste n kurz gedrückt (1–9), gemeldet beim Loslassen
//   LANG n                    – Taste n lange gedrückt (ab 0,6 s, noch während sie unten ist)
//   LAUT n                    – Regler steht auf n Prozent (0–100), nur wenn er sich bewegt hat, und auf „LAUT?“
//   ROH 010000000 512         – nur mit „DEBUG 1“: alle 0,1 s jede Taste (1 = unten) und der Regler roh (0–1023)
// Was der PC schickt:
//   WER?  LAUT?  LED n (Helligkeit 0–100, 0 = aus)  EFFEKT n (0 = ruhig, 1 = atmen, 2 = blinken)
//   FARBE r g b (Streifen, je 0–255)  DEBUG 0|1

// #define STREIFEN 8   // Zeile einschalten (// weg) für einen WS2812B-Streifen mit 8 LEDs (Bibliothek „Adafruit NeoPixel“)

#if defined(ARDUINO_AVR_LEONARDO) || defined(ARDUINO_AVR_MICRO) || defined(ARDUINO_AVR_PROMICRO) || defined(__AVR_ATmega32U4__)
const uint8_t TASTEN[9] = {2, 3, 4, 5, 6, 7, 8, 14, 15};
const uint8_t LED = 9;
const uint8_t STREIFEN_PIN = 10;
const char BOARD[] = "PROMICRO";
#else
const uint8_t TASTEN[9] = {2, 3, 4, 5, 6, 7, 8, 9, 10};
const uint8_t LED = 11;
const uint8_t STREIFEN_PIN = 12;
const char BOARD[] = "NANO";
#endif
const uint8_t REGLER = A0;

#ifdef STREIFEN
#include <Adafruit_NeoPixel.h>
Adafruit_NeoPixel streifen(STREIFEN, STREIFEN_PIN, NEO_GRB + NEO_KHZ800);
#endif

const unsigned long LANG_MS = 600;  // ab so langem Drücken: „LANG n“ statt „TASTE n“

bool gedrueckt[9];
bool langGemeldet[9];
unsigned long zuletzt[9];
unsigned long unten_seit[9];
int regler = -1;          // zuletzt gemeldeter Wert (0–100)
float glatt = 0;          // geglätteter Messwert (Poti rauscht etwas)
String zeile;

int hell = 0;             // gewünschte Helligkeit 0–100
int effekt = 0;           // 0 ruhig, 1 atmen, 2 blinken
uint8_t farbe[3] = {0, 255, 160};
bool debug = false;
unsigned long debugZuletzt = 0;

void ledZeigen(int prozent) {
  prozent = constrain(prozent, 0, 100);
  analogWrite(LED, map(prozent, 0, 100, 0, 255));
#ifdef STREIFEN
  for (int i = 0; i < STREIFEN; i++) {
    streifen.setPixelColor(i, streifen.Color((uint16_t)farbe[0] * prozent / 100, (uint16_t)farbe[1] * prozent / 100,
                                             (uint16_t)farbe[2] * prozent / 100));
  }
  streifen.show();
#endif
}

int effektHelligkeit(unsigned long t) {
  if (effekt == 1) {  // atmen: 3 s langsam hell und wieder dunkel (nie ganz aus)
    unsigned long p = t % 3000;
    int stufe = p < 1500 ? p : 3000 - p;           // 0 … 1500 … 0
    return hell * (15 + 85L * stufe / 1500) / 100;
  }
  if (effekt == 2) {  // blinken: 0,4 s an, 0,4 s aus
    return (t / 400) % 2 ? 0 : hell;
  }
  return hell;
}

void hallo() {
  Serial.print("HALLO ALUPC-TASTEN 3 ");
  Serial.println(BOARD);
}

void setup() {
  Serial.begin(115200);
  for (uint8_t i = 0; i < 9; i++) {
    pinMode(TASTEN[i], INPUT_PULLUP);  // offen = HIGH, gedrückt = LOW
    gedrueckt[i] = false;
    langGemeldet[i] = false;
  }
  pinMode(LED, OUTPUT);
#ifdef STREIFEN
  streifen.begin();
#endif
  ledZeigen(0);
  glatt = analogRead(REGLER);
  hallo();  // Nano startet beim Öffnen des Anschlusses neu – so weiß AluPC sofort Bescheid
}

void befehl(String text) {
  text.trim();
  text.toUpperCase();
  if (text == "WER?") {
    hallo();
  } else if (text == "LAUT?") {
    Serial.print("LAUT ");
    Serial.println(regler < 0 ? 0 : regler);
  } else if (text.startsWith("LED ")) {
    hell = constrain(text.substring(4).toInt(), 0, 100);
    ledZeigen(effektHelligkeit(millis()));
  } else if (text.startsWith("EFFEKT ")) {
    effekt = constrain(text.substring(7).toInt(), 0, 2);
  } else if (text.startsWith("FARBE ")) {
    int a = text.indexOf(' ', 6), b = a < 0 ? -1 : text.indexOf(' ', a + 1);
    if (a > 0 && b > 0) {
      farbe[0] = constrain(text.substring(6, a).toInt(), 0, 255);
      farbe[1] = constrain(text.substring(a + 1, b).toInt(), 0, 255);
      farbe[2] = constrain(text.substring(b + 1).toInt(), 0, 255);
      ledZeigen(effektHelligkeit(millis()));
    }
  } else if (text.startsWith("DEBUG ")) {
    debug = text.substring(6).toInt() != 0;
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

  // Tasten (entprellt: 30 ms Ruhe nach jedem Wechsel). Kurz: „TASTE n“ beim Loslassen, lang: „LANG n“ nach 0,6 s
  unsigned long jetzt = millis();
  for (uint8_t i = 0; i < 9; i++) {
    bool unten = digitalRead(TASTEN[i]) == LOW;
    if (unten != gedrueckt[i] && jetzt - zuletzt[i] > 30) {
      gedrueckt[i] = unten;
      zuletzt[i] = jetzt;
      if (unten) {
        unten_seit[i] = jetzt;
        langGemeldet[i] = false;
      } else if (!langGemeldet[i]) {
        Serial.print("TASTE ");
        Serial.println(i + 1);
      }
    }
    if (gedrueckt[i] && !langGemeldet[i] && jetzt - unten_seit[i] >= LANG_MS) {
      langGemeldet[i] = true;
      Serial.print("LANG ");
      Serial.println(i + 1);
    }
  }

  // Regler: glätten, und erst melden, wenn er sich um mindestens 1 % bewegt hat
  int roh = analogRead(REGLER);
  glatt = glatt * 0.85 + roh * 0.15;
  int prozent = round(glatt * 100.0 / 1023.0);
  if (regler < 0 || abs(prozent - regler) >= 1) {
    if (regler < 0 || abs(glatt * 100.0 / 1023.0 - regler) > 0.7) {  // kein Hin-und-her an der Grenze
      regler = prozent;
      Serial.print("LAUT ");
      Serial.println(regler);
    }
  }

  // LED-Effekte laufen hier in der Box (flüssig, ohne den PC)
  if (effekt != 0) ledZeigen(effektHelligkeit(jetzt));

  // Fehlersuche: Rohwerte
  if (debug && jetzt - debugZuletzt >= 100) {
    debugZuletzt = jetzt;
    Serial.print("ROH ");
    for (uint8_t i = 0; i < 9; i++) Serial.print(digitalRead(TASTEN[i]) == LOW ? '1' : '0');
    Serial.print(' ');
    Serial.println(roh);
  }
  delay(5);
}
