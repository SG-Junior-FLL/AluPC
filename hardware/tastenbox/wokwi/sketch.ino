// AluPC-Tasten – Programm für die Tastenbox (Arduino Pro Micro oder Arduino Nano)
//
// 9 Tasten (3 × 3), 1 Drehregler (was er regelt, stellt man in AluPC ein), LEDs: 3 Farben (rot, grün, blau –
// normale 5-mm-LEDs, je Farbe ein Pin) oder ein einfarbiger LED-Pin oder RGB-LEDs (Streifen).
// In der Arduino-IDE das Board wählen – Pro Micro: „Arduino Leonardo“ (technisch gleich), Nano: „Arduino Nano“
// (bei Nachbauten evtl. Prozessor „ATmega328P (Old Bootloader)“) –, Anschluss wählen, hochladen.
// AluPC findet die Box danach von selbst (Seite „Tastenbox“). Die Pins passen sich dem Board an:
//
//                 Pro Micro                        Nano (und Uno/Mega, z. B. in der Wokwi-Simulation)
//   Tasten 1–9 :  D2 D3 D4 D5 D6 D7 D8 D14 D15       D2 D3 D4 D5 D6 D7 D8 D9 D10
//   Regler     :  A0                                 A0
//   3 Farben   :  rot D10 · grün D9 · blau D16          rot D11 · grün D12 · blau D13   (Standard)
//   LEDs       :  D9                                 D11       (nur ohne DREI_FARBEN: alle LEDs an einem Pin)
//   Streifen   :  D10                                D12       (nur mit STREIFEN, statt DREI_FARBEN)
//   Buzzer     :  A2                                 A2        (optional: + an A2, − an GND)
//
//   Tasten: jeweils das andere Bein an GND (keine Widerstände nötig).
//   Regler: Potentiometer 10 kΩ linear – Mitte an A0, die beiden Außenbeine an 5V/VCC und GND.
//   LEDs:   je Farbe ein 220-Ω-Widerstand vom Pin zu den 4 LEDs dieser Farbe (langes Bein), kurze Beine an GND.
//           3 Farben: je Ecke 3 LEDs rot, grün, blau („Farbmischer“, wie eine RGB-LED) – alle LEDs einer Farbe am
//           selben Farb-Pin. Farbe aus AluPC (FARBE r g b) → rot/grün/blau direkt, Mischfarben (auch Weiß = alle
//           drei) entstehen in jeder Ecke; Regenbogen = Farbkreis.
//   Streifen/RGB-LEDs (WS2812B, PL9823): DIN an den Streifen-Pin, 5V, GND (am USB höchstens ~8–10 LEDs).
//   Buzzer: passiver Buzzer spielt Töne und Melodien (AluPC schickt Note für Note), aktiver piept nur.
//           (Nano ohne DREI_FARBEN: Buzzer und LED-Pin D11 teilen sich Timer 2 – dann flackert die LED beim Ton.)
//
// Was die Box an den PC schickt (115200 Baud, eine Zeile je Meldung):
//   HALLO ALUPC-TASTEN 8 NANO – Antwort auf „WER?“ (und einmal beim Start); 8 = Programmversion, dann das Board
//   TASTE n                   – Taste n kurz gedrückt (1–9), gemeldet beim Loslassen
//   LANG n                    – Taste n lange gedrückt (ab 0,6 s, noch während sie unten ist)
//   LAUT n                    – Regler steht auf n Prozent (0–100), nur wenn er sich bewegt hat, und auf „LAUT?“
//   WERT n                    – derselbe Regler fein als Zahl 0–999 (z. B. 10-Gang-Poti mit Zählwerk), nur bei
//                               Änderung und auf „WERT?“ (16-fach gemittelt, mit Hysterese gegen Zittern)
//   ROH 010000000 512         – nur mit „DEBUG 1“: alle 0,1 s jede Taste (1 = unten) und der Regler roh (0–1023)
// Was der PC schickt:
//   WER?  LAUT?  WERT?  LED n (Helligkeit 0–100, 0 = aus)  EFFEKT n (0 = ruhig, 1 = atmen, 2 = blinken, 3 = Regenbogen)
//   FARBE r g b (alle RGB-LEDs, je 0–255)  PIXEL i r g b (eine RGB-LED, i ab 0)  DEBUG 0|1
//   TON f ms (Buzzer: f Hz für ms Millisekunden, TON 0 0 = Stille)
//
// RGB-LEDs (Farben je LED): eine Kette aus adressierbaren LEDs am Streifen-Pin. Reihenfolge wie im LED-Plan:
//   0 = Ecke vorne links, 1 = hinten links, 2 = hinten rechts, 3 = vorne rechts, ab 4 = Lichtleiste.
// STREIFEN = Anzahl aller LEDs der Kette (z. B. 4 Ecken + 7 Leiste = 11).

#define DREI_FARBEN  // 3 einfarbige LED-Gruppen (rot, grün, blau) – ausschalten (// davor) für eine LED-Gruppe an D11
// #define STREIFEN 11  // Zeile einschalten (// weg) für RGB-LEDs, hier 11 Stück (Bibliothek „Adafruit NeoPixel“)
// #define ECKEN_PL9823 // einschalten, wenn die 4 Ecken 5-mm-LEDs vom Typ PL9823 sind (andere Farbreihenfolge als WS2812B)

#if defined(ARDUINO_AVR_LEONARDO) || defined(ARDUINO_AVR_MICRO) || defined(ARDUINO_AVR_PROMICRO) || defined(__AVR_ATmega32U4__)
const uint8_t TASTEN[9] = {2, 3, 4, 5, 6, 7, 8, 14, 15};
const uint8_t LED = 9;
const uint8_t STREIFEN_PIN = 10;
const uint8_t KANAL_PIN[3] = {10, 9, 16};   // rot, grün, blau
const char BOARD[] = "PROMICRO";
#else
const uint8_t TASTEN[9] = {2, 3, 4, 5, 6, 7, 8, 9, 10};
const uint8_t LED = 11;
const uint8_t STREIFEN_PIN = 12;
const uint8_t KANAL_PIN[3] = {11, 12, 13};  // rot, grün, blau
const char BOARD[] = "NANO";
#endif
const uint8_t REGLER = A0;
const uint8_t BUZZER = A2;

#if defined(DREI_FARBEN) && defined(STREIFEN)
#error "DREI_FARBEN und STREIFEN gehen nicht zusammen (gleicher Pin) – eins von beiden ausschalten"
#endif

#ifdef DREI_FARBEN
// Helligkeit je Farbe weich (64 Stufen, 125 Hz) für alle 4 Pins – auch die ohne PWM: Timer 1 schaltet sie
volatile uint8_t kanal[3];
ISR(TIMER1_COMPA_vect) {
  static uint8_t schritt = 0;
  schritt = (schritt + 1) & 63;
  for (uint8_t k = 0; k < 3; k++) digitalWrite(KANAL_PIN[k], kanal[k] > schritt ? HIGH : LOW);
}
void kanaeleStarten() {
  for (uint8_t k = 0; k < 3; k++) pinMode(KANAL_PIN[k], OUTPUT);
  noInterrupts();
  TCCR1A = 0;
  TCCR1B = _BV(WGM12) | _BV(CS11);  // CTC, 16 MHz / 8
  OCR1A = F_CPU / 8 / 8000 - 1;     // → 8 kHz Takt, 64 Stufen = 125 Hz (16 MHz: 249; 8-MHz-Boards: 124)
  TIMSK1 = _BV(OCIE1A);
  interrupts();
}
uint8_t stufe(uint16_t v, int prozent) {  // 0–255 → 0–63, quadratisch (das Auge sieht dunkle Stufen feiner)
  v = v * prozent / 100;
  return (uint32_t)v * v / 1032;
}
#endif

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
float fein = 0;           // stärker geglättet für WERT (0–999)
int wert = -1;            // zuletzt gemeldeter WERT
String zeile;

int hell = 0;             // gewünschte Helligkeit 0–100
int effekt = 0;           // 0 ruhig, 1 atmen, 2 blinken
uint8_t farbe[3] = {0, 255, 160};
#ifdef STREIFEN
uint8_t px[STREIFEN][3];  // Farbe je LED (FARBE setzt alle, PIXEL eine)
#endif
bool debug = false;
unsigned long debugZuletzt = 0;

void ledZeigen(int prozent) {
  prozent = constrain(prozent, 0, 100);
#ifdef DREI_FARBEN
  uint16_t r = farbe[0], g = farbe[1], b = farbe[2];
  if (effekt == 3) {  // Regenbogen: rot/grün/blau mischen sich in jeder Ecke zum Farbkreis (6 s rundum)
    uint16_t hue = (millis() / 24) % 256;
    uint8_t seg = hue / 43, f = (hue % 43) * 6;
    uint8_t q = 255 - f;
    const uint8_t rgb[6][3] = {{255, f, 0}, {q, 255, 0}, {0, 255, f}, {0, q, 255}, {f, 0, 255}, {255, 0, q}};
    r = rgb[seg % 6][0]; g = rgb[seg % 6][1]; b = rgb[seg % 6][2];
  }
  kanal[0] = stufe(r, prozent);
  kanal[1] = stufe(g, prozent);
  kanal[2] = stufe(b, prozent);
#else
  analogWrite(LED, map(prozent, 0, 100, 0, 255));
#endif
#ifdef STREIFEN
  for (int i = 0; i < STREIFEN; i++) {
    uint16_t r = px[i][0], g = px[i][1], b = px[i][2];
    if (effekt == 3) {  // Regenbogen: Farbe wandert über die Kette
      uint16_t hue = (millis() / 8 + i * 65536UL / STREIFEN / 256) % 256;
      uint8_t seg = hue / 43, f = (hue % 43) * 6;
      uint8_t q = 255 - f;
      const uint8_t rgb[6][3] = {{255, f, 0}, {q, 255, 0}, {0, 255, f}, {0, q, 255}, {f, 0, 255}, {255, 0, q}};
      r = rgb[seg % 6][0]; g = rgb[seg % 6][1]; b = rgb[seg % 6][2];
    }
    r = r * prozent / 100; g = g * prozent / 100; b = b * prozent / 100;
#ifdef ECKEN_PL9823
    if (i < 4) { streifen.setPixelColor(i, (uint32_t)g << 16 | (uint32_t)r << 8 | b); continue; }
#endif
    streifen.setPixelColor(i, streifen.Color(r, g, b));
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
  return hell;  // ruhig und Regenbogen: volle eingestellte Helligkeit
}

void hallo() {
  Serial.print("HALLO ALUPC-TASTEN 8 ");
  Serial.println(BOARD);
}

void setup() {
#if defined(__AVR_ATmega32U4__)
  // Pro Micro: A0–A3 sind auch JTAG-Pins; bei manchen Nachbauten ist JTAG an → Regler (A0) und Buzzer (A2)
  // gingen nicht. Abschalten: JTD zweimal kurz hintereinander setzen.
  MCUCR |= (1 << JTD);
  MCUCR |= (1 << JTD);
#endif
  Serial.begin(115200);
  for (uint8_t i = 0; i < 9; i++) {
    pinMode(TASTEN[i], INPUT_PULLUP);  // offen = HIGH, gedrückt = LOW
    gedrueckt[i] = false;
    langGemeldet[i] = false;
  }
#ifdef DREI_FARBEN
  kanaeleStarten();
#else
  pinMode(LED, OUTPUT);
#endif
#ifdef STREIFEN
  streifen.begin();
  for (int i = 0; i < STREIFEN; i++) for (int k = 0; k < 3; k++) px[i][k] = farbe[k];
#endif
  ledZeigen(0);
  glatt = analogRead(REGLER);
  fein = glatt;
  hallo();  // Nano startet beim Öffnen des Anschlusses neu – so weiß AluPC sofort Bescheid
}

void befehl(String text) {
  text.trim();
  text.toUpperCase();
  if (text == "WER?") {
    hallo();
  } else if (text == "WERT?") {
    Serial.print("WERT ");
    Serial.println(wert < 0 ? 0 : wert);
  } else if (text == "LAUT?") {
    Serial.print("LAUT ");
    Serial.println(regler < 0 ? 0 : regler);
  } else if (text.startsWith("LED ")) {
    hell = constrain(text.substring(4).toInt(), 0, 100);
    ledZeigen(effektHelligkeit(millis()));
  } else if (text.startsWith("EFFEKT ")) {
    effekt = constrain(text.substring(7).toInt(), 0, 3);
  } else if (text.startsWith("FARBE ")) {
    int a = text.indexOf(' ', 6), b = a < 0 ? -1 : text.indexOf(' ', a + 1);
    if (a > 0 && b > 0) {
      farbe[0] = constrain(text.substring(6, a).toInt(), 0, 255);
      farbe[1] = constrain(text.substring(a + 1, b).toInt(), 0, 255);
      farbe[2] = constrain(text.substring(b + 1).toInt(), 0, 255);
#ifdef STREIFEN
      for (int i = 0; i < STREIFEN; i++) for (int k = 0; k < 3; k++) px[i][k] = farbe[k];
#endif
      ledZeigen(effektHelligkeit(millis()));
    }
  } else if (text.startsWith("PIXEL ")) {
    int v[4], start = 6;
    for (int k = 0; k < 4; k++) {
      int e = text.indexOf(' ', start);
      v[k] = text.substring(start, e < 0 ? text.length() : e).toInt();
      start = e + 1;
      if (e < 0 && k < 3) return;
    }
#ifdef STREIFEN
    if (v[0] >= 0 && v[0] < STREIFEN) {
      for (int k = 0; k < 3; k++) px[v[0]][k] = constrain(v[k + 1], 0, 255);
      ledZeigen(effektHelligkeit(millis()));
    }
#endif
  } else if (text.startsWith("TON ")) {
    int a = text.indexOf(' ', 4);
    long f = text.substring(4, a < 0 ? text.length() : a).toInt();
    long ms = a < 0 ? 200 : text.substring(a + 1).toInt();
    if (f < 31 || ms <= 0) {
      noTone(BUZZER);
    } else {
      tone(BUZZER, min(f, 20000L), min(ms, 10000L));
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

  // Feiner Wert 0–999: 16 Messungen mitteln, stark glätten, erst bei mehr als 0,6 Schritten Abstand melden
  long summe = 0;
  for (uint8_t k = 0; k < 16; k++) summe += analogRead(REGLER);
  fein = fein * 0.8 + (summe / 16.0) * 0.2;
  float genau = fein * 999.0 / 1023.0;
  if (wert < 0 || fabs(genau - wert) > 0.6) {
    int neu = constrain((int)round(genau), 0, 999);
    if (neu != wert) {
      wert = neu;
      Serial.print("WERT ");
      Serial.println(wert);
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
