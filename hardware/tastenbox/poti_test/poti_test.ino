// Poti-Test für die Tastenbox: findet heraus, welcher der 3 Drähte der Schleifer (Mitte) ist,
// und zeigt dann die Stellung 0–1000 im Seriellen Monitor (115200 Baud).
//
// ANSCHLIESSEN (Reihenfolge egal – nur merken, welche Farbe wo steckt):
//   Draht 1 → A0     Draht 2 → A1     Draht 3 → A2       (KEIN 5V, KEIN GND nötig)
// Unten bei FARBE die Farben in derselben Reihenfolge eintragen, dann steht im Monitor gleich die Farbe.
//
// SICHER: Es wird nie ein Pin hart auf 5 V geschaltet. „Plus“ kommt nur über den eingebauten Pull-up
// (~35 kΩ) – selbst wenn der Schleifer ganz am Ende steht, fließen höchstens ~0,15 mA. Nichts kann kurzschließen.
//
// SO MISST ES: Für jedes Draht-Paar: ein Draht über Pull-up auf Plus, einer auf Minus, Spannung messen.
// Die beiden Enden haben IMMER den größten Widerstand zueinander (ganzer Poti) → größter Messwert.
// Der Draht, der in diesem Paar NICHT dabei ist, ist der Schleifer.
// Läuft auf Pro Micro (Board „Arduino Leonardo“) und Nano.
//
// KONTAKT-TEST ohne Poti: A0 und A1 direkt mit einem Jumper-Kabel verbinden → „A0-A1“ muss fast 0 zeigen.
// Zeigt es 1023, kommt das Kabel nicht am Pin an (falsche Reihe, falsche Seite vom Graben, Pin nicht angelötet).

const uint8_t PIN[3] = {A0, A1, A2};
const char* FARBE[3] = {"rot", "grau", "gelb"};   // ← hier deine Farben eintragen (Draht an A0, A1, A2)
const char* NAME[3] = {"A0", "A1", "A2"};

void alleLos() {
  for (uint8_t i = 0; i < 3; i++) pinMode(PIN[i], INPUT);  // alles hochohmig
}

// Paar messen: a über Pull-up an Plus, b auf Minus. Rückgabe: Spannung an a (0–1023), 16-fach gemittelt.
// Größerer Widerstand zwischen a und b → größerer Wert.
int paar(uint8_t a, uint8_t b) {
  alleLos();
  pinMode(PIN[b], OUTPUT);
  digitalWrite(PIN[b], LOW);
  pinMode(PIN[a], INPUT_PULLUP);
  delay(2);
  long s = 0;
  for (uint8_t k = 0; k < 16; k++) s += analogRead(PIN[a]);
  return s / 16;
}

// Stellung 0–1000: Ende e1 über Pull-up, Ende e2 auf Minus, Schleifer w messen, ins Verhältnis setzen
int stellung(uint8_t e1, uint8_t e2, uint8_t w) {
  alleLos();
  pinMode(PIN[e2], OUTPUT);
  digitalWrite(PIN[e2], LOW);
  pinMode(PIN[e1], INPUT_PULLUP);
  delay(2);
  long oben = 0, mitte = 0;
  for (uint8_t k = 0; k < 16; k++) {
    oben += analogRead(PIN[e1]);
    mitte += analogRead(PIN[w]);
  }
  if (oben < 16) return -1;  // nichts angeschlossen
  return (long)mitte * 1000 / oben;
}

void setup() {
  Serial.begin(115200);
  while (!Serial && millis() < 4000) {}  // Pro Micro: kurz auf den Seriellen Monitor warten
  Serial.println(F("Poti-Test: Draehte an A0, A1, A2. Poti einmal etwas drehen."));
}

void loop() {
  int ab = paar(0, 1), ac = paar(0, 2), bc = paar(1, 2);  // Paare: A0–A1, A0–A2, A1–A2
  int werte[3] = {bc, ac, ab};  // werte[i] = Paar OHNE Draht i
  uint8_t w = 0;
  for (uint8_t i = 1; i < 3; i++) if (werte[i] > werte[w]) w = i;  // größtes Paar → der fehlende Draht ist der Schleifer
  int zweit = 0;
  for (uint8_t i = 0; i < 3; i++) if (i != w && werte[i] > zweit) zweit = werte[i];

  Serial.print(F("Paare  A0-A1: ")); Serial.print(ab);
  Serial.print(F("  A0-A2: ")); Serial.print(ac);
  Serial.print(F("  A1-A2: ")); Serial.print(bc);

  uint8_t offen = 0, verbunden = 3;  // Paare ohne Verbindung zählen (Pull-up kommt ungebremst durch)
  for (uint8_t i = 0; i < 3; i++) {
    if (werte[i] > 1000) offen++;
    else verbunden = i;               // werte[i] = Paar OHNE Draht i
  }
  if (offen == 3) {
    Serial.println(F("   -> KEINE Verbindung: mind. 2 Draehte ohne Kontakt (Reihe/Seite am Steckbrett? Pro Micro angeloetet?)"));
  } else if (offen == 2) {
    Serial.print(F("   -> Draht an ")); Serial.print(NAME[verbunden]); Serial.print(F(" (")); Serial.print(FARBE[verbunden]);
    Serial.println(F(") hat KEINEN Kontakt – die anderen zwei sind ok"));
  } else if (werte[w] - zweit < werte[w] / 20) {
    Serial.println(F("   -> Schleifer steht am Ende – Poti etwas in die Mitte drehen"));
  } else {
    uint8_t e1 = (w + 1) % 3, e2 = (w + 2) % 3;
    Serial.print(F("   -> SCHLEIFER = ")); Serial.print(NAME[w]); Serial.print(F(" (")); Serial.print(FARBE[w]);
    Serial.print(F(")  Enden = ")); Serial.print(FARBE[e1]); Serial.print(F(" + ")); Serial.print(FARBE[e2]);
    Serial.print(F("   Stellung: ")); Serial.print(stellung(e1, e2, w)); Serial.println(F(" / 1000"));
  }
  alleLos();
  delay(300);
}
