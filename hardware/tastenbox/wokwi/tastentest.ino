// Test für Arduino Nano: Tasten an Pin 2 bis 10 (jeweils Pin ↔ GND), Drehregler an A0, LEDs an Pin 11.
// Serial Monitor: zeigt Tastendruck und Reglerstellung. LEDs: Helligkeit folgt dem Regler, bei Tastendruck voll an.

const byte ERSTER = 2;
const byte LETZTER = 10;
const byte LED = 11;              // PWM-Pin, damit die Helligkeit regelbar ist
const byte REGLER = A0;
const unsigned long ENTPRELLEN_MS = 20;

bool unten[LETZTER + 1];
unsigned long zuletzt[LETZTER + 1];
int letzterProzent = -1;

void setup() {
  Serial.begin(9600);
  while (!Serial && millis() < 3000) {}
  for (byte p = ERSTER; p <= LETZTER; p++) {
    pinMode(p, INPUT_PULLUP);     // ohne Druck HIGH, gedrückt LOW
    unten[p] = false;
    zuletzt[p] = 0;
  }
  pinMode(LED, OUTPUT);
  Serial.println("Test bereit: Tasten Pin 2-10, Regler A0, LEDs Pin 11");
}

void loop() {
  bool irgendeine = false;
  for (byte p = ERSTER; p <= LETZTER; p++) {
    bool jetzt = digitalRead(p) == LOW;
    if (jetzt != unten[p] && millis() - zuletzt[p] > ENTPRELLEN_MS) {
      unten[p] = jetzt;
      zuletzt[p] = millis();
      Serial.print("Taste ");
      Serial.print(p - ERSTER + 1);
      Serial.print(" (Pin ");
      Serial.print(p);
      Serial.println(jetzt ? "): gedrueckt" : "): losgelassen");
    }
    if (unten[p]) irgendeine = true;
  }

  int prozent = map(analogRead(REGLER), 0, 1023, 0, 100);
  if (letzterProzent < 0 || abs(prozent - letzterProzent) >= 2) {
    letzterProzent = prozent;
    Serial.print("Regler: ");
    Serial.print(prozent);
    Serial.println(" %");
  }

  analogWrite(LED, irgendeine ? 255 : map(letzterProzent, 0, 100, 0, 255));
}
