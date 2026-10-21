// Tastentest: Pin 2 bis 9, jede Taste zwischen Pin und GND.
// Schreibt in den Serial Monitor, wenn eine Taste gedrückt oder losgelassen wird.

const byte ERSTER = 2;
const byte LETZTER = 9;
const unsigned long ENTPRELLEN_MS = 20;

bool unten[LETZTER + 1];
unsigned long zuletzt[LETZTER + 1];

void setup() {
  Serial.begin(9600);
  while (!Serial && millis() < 3000) {}  // Pro Micro: kurz auf den Serial Monitor warten
  for (byte p = ERSTER; p <= LETZTER; p++) {
    pinMode(p, INPUT_PULLUP);            // ohne Druck HIGH, gedrückt LOW (Verbindung zu GND)
    unten[p] = false;
    zuletzt[p] = 0;
  }
  Serial.println("Tastentest bereit: Pin 2 bis 9");
}

void loop() {
  for (byte p = ERSTER; p <= LETZTER; p++) {
    bool jetzt = digitalRead(p) == LOW;
    if (jetzt != unten[p] && millis() - zuletzt[p] > ENTPRELLEN_MS) {
      unten[p] = jetzt;
      zuletzt[p] = millis();
      Serial.print("Pin ");
      Serial.print(p);
      Serial.println(jetzt ? ": gedrueckt" : ": losgelassen");
    }
  }
}
