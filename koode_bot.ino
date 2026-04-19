// ===================== ULTRASONIC =====================
const int trigPin = 4;
const int echoPin = 5;
// ===================== MOTOR DRIVER =====================
const int in1 = 25, in2 = 26, in3 = 27, in4 = 14;

// ===================== SETTINGS =====================
const int obstacleLimit       = 20;
const unsigned long TURN_90_MS      = 420;   // Tune for your bot
const unsigned long FORWARD_20CM_MS = 800;   // Tune after calibration

char command         = 'S';
bool commandExecuted = false;
int  consecObstacle  = 0;
const int OBSTACLE_CONFIRM = 3;

// ===================== SETUP =====================
void setup() {
  Serial.begin(115200);
  pinMode(trigPin, OUTPUT);
  pinMode(echoPin, INPUT);
  pinMode(in1,OUTPUT); pinMode(in2,OUTPUT);
  pinMode(in3,OUTPUT); pinMode(in4,OUTPUT);
  motorStop();

  // --- Quick self-test: blink each motor 300ms so you can verify direction ---
  Serial.println("Self-test: Motor A forward...");
  digitalWrite(in1, LOW); digitalWrite(in2, HIGH);   // Motor A forward (swapped)
  delay(300); motorStop(); delay(200);

  Serial.println("Self-test: Motor B forward...");
  digitalWrite(in3, HIGH); digitalWrite(in4, LOW);   // Motor B forward
  delay(300); motorStop(); delay(200);

  Serial.println("Self-test: Both forward...");
  motorForward(); delay(400); motorStop();

  Serial.println("Ready. X=Forward  L=Left+20cm  R=Right+20cm  S=Stop");
}

// ===================== LOOP =====================
void loop() {

  if (Serial.available()) {
    char c = Serial.read();
    if (c=='X' || c=='L' || c=='R' || c=='S') {
      command = c;
      commandExecuted = false;
      Serial.print("CMD: "); Serial.println(command);
    }
  }

  int dist = getMedianDistance();
  Serial.print("Dist: "); Serial.println(dist);

  if (dist > 0 && dist <= obstacleLimit) consecObstacle++;
  else consecObstacle = 0;

  if (consecObstacle >= OBSTACLE_CONFIRM) {
    consecObstacle = 0;
    avoidObstacle();
    command = 'S';
    commandExecuted = true;
    return;
  }

  if (!commandExecuted) {
    if (command == 'X') {
      motorForward();

    } else if (command == 'L') {
      turnLeft();
      delay(TURN_90_MS);
      motorStop(); delay(60);
      moveForwardCm();
      motorStop();
      commandExecuted = true;
      command = 'S';
      Serial.println("L done.");

    } else if (command == 'R') {
      turnRight();
      delay(TURN_90_MS);
      motorStop(); delay(60);
      moveForwardCm();
      motorStop();
      commandExecuted = true;
      command = 'S';
      Serial.println("R done.");

    } else {
      motorStop();
      commandExecuted = true;
    }
  }

  delay(40);
}

// ===================== MOVE 20 CM =====================
void moveForwardCm() {
  unsigned long start = millis();
  while (millis() - start < FORWARD_20CM_MS) {
    int d = getMedianDistance();
    if (d > 0 && d <= obstacleLimit) {
      motorStop();
      Serial.println("Obstacle mid-move — stopped.");
      return;
    }
    motorForward();
    delay(30);
  }
}

// ===================== OBSTACLE AVOIDANCE =====================
void avoidObstacle() {
  Serial.println("OBSTACLE — avoiding...");
  motorStop(); delay(80);
  motorBack();  delay(200);   // Reverse away
  motorStop(); delay(60);

  for (int attempt = 0; attempt < 3; attempt++) {
    turnRight();
    delay(TURN_90_MS);
    motorStop(); delay(80);

    int clearDist = getMedianDistance();
    Serial.print("Post-turn dist: "); Serial.println(clearDist);

    if (clearDist == -1 || clearDist > obstacleLimit + 10) {
      Serial.println("Path clear.");
      return;
    }
    Serial.println("Still blocked, retrying...");
  }
  motorStop();
  Serial.println("Fully blocked — waiting.");
}

// ===================== ULTRASONIC: MEDIAN OF 3 =====================
int getMedianDistance() {
  int r[3];
  for (int i = 0; i < 3; i++) {
    digitalWrite(trigPin, LOW);
    delayMicroseconds(2);
    digitalWrite(trigPin, HIGH);
    delayMicroseconds(10);
    digitalWrite(trigPin, LOW);
    long dur = pulseIn(echoPin, HIGH, 20000);
    if (dur == 0) { r[i] = 999; delay(10); continue; }
    int cm = dur * 0.034 / 2;
    r[i] = (cm > 2 && cm < 150) ? cm : 999;
    delay(10);
  }
  if (r[0]>r[1]) { int t=r[0]; r[0]=r[1]; r[1]=t; }
  if (r[1]>r[2]) { int t=r[1]; r[1]=r[2]; r[2]=t; }
  if (r[0]>r[1]) { int t=r[0]; r[0]=r[1]; r[1]=t; }
  return (r[1] == 999) ? -1 : r[1];
}

// ===================== MOTOR FUNCTIONS (Motor A pins swapped) =====================
void motorForward() {
  digitalWrite(in1, LOW);  digitalWrite(in2, HIGH);  // Motor A — swapped
  digitalWrite(in3, HIGH); digitalWrite(in4, LOW);   // Motor B — unchanged
}
void motorBack() {
  digitalWrite(in1, HIGH); digitalWrite(in2, LOW);   // Motor A — swapped
  digitalWrite(in3, LOW);  digitalWrite(in4, HIGH);  // Motor B — unchanged
}
void turnLeft() {
  digitalWrite(in1, HIGH); digitalWrite(in2, LOW);   // Motor A backward
  digitalWrite(in3, HIGH); digitalWrite(in4, LOW);   // Motor B forward
}
void turnRight() {
  digitalWrite(in1, LOW);  digitalWrite(in2, HIGH);  // Motor A forward
  digitalWrite(in3, LOW);  digitalWrite(in4, HIGH);  // Motor B backward
}
void motorStop() {
  digitalWrite(in1, LOW); digitalWrite(in2, LOW);
  digitalWrite(in3, LOW); digitalWrite(in4, LOW);
}
