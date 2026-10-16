/*
 * Wristband firmware — Phase S1-A / S1-B (A2.6, B1.4)
 *
 * Implements the FROZEN 12-byte command format from
 * contracts/HapticCommand.kt. Any change to this layout requires a
 * formatVersion bump and reflashing BOTH bands.
 *
 * SIDE IDENTITY is set at flash time below — never inferred.
 * Flash one board with BAND_SIDE 0, the other with 1.
 */

#include <NimBLEDevice.h>
#include <Wire.h>
#include <Adafruit_DRV2605.h>

// ===================== FLASH-TIME CONFIGURATION =====================
#define BAND_SIDE      0        // 0 = LEFT, 1 = RIGHT.  CHANGE PER BOARD.
#define INTENSITY_CAP  85       // FIRMWARE-SIDE comfort cap. The app cannot exceed this.
// ====================================================================

#define PIN_LED        3
#define PIN_BUZZER     4
#define PIN_BATT       2
#define PIN_SDA        8
#define PIN_SCL        9

#define FORMAT_VERSION 1
#define WIRE_SIZE      12

#define SVC_UUID    "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
#define CMD_UUID    "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
#define STATUS_UUID "6e400003-b5a3-f393-e0a9-e50e24dcca9e"
#define ECHO_UUID   "6e400004-b5a3-f393-e0a9-e50e24dcca9e"

// pattern ids — must match PatternId.wire in HapticCommand.kt
enum PatternId : uint8_t {
  P_TURN_LEFT = 1, P_TURN_RIGHT = 2, P_FOUND = 3,
  P_OBSTACLE_NEAR = 4, P_URGENT = 5, P_FAULT = 6, P_LOW_BATTERY = 7
};
enum TargetId : uint8_t { T_LEFT = 0, T_RIGHT = 1, T_BOTH = 2 };
enum Mode { M_BOOT, M_IDLE, M_CONNECTED, M_FAULT, M_LOW_BATTERY };

Adafruit_DRV2605 drv;
NimBLECharacteristic* statusChar = nullptr;
NimBLECharacteristic* echoChar = nullptr;

Mode      mode            = M_BOOT;
bool      driverOk        = false;
bool      clientConnected = false;
uint32_t  droppedPackets  = 0;
uint32_t  playedPackets   = 0;
uint32_t  lastBattMs      = 0;
uint8_t   battPercent     = 100;

// ---------------- scheduled command (one slot, latest wins) ----------------
struct PendingCmd {
  bool     active       = false;
  uint8_t  patternId    = 0;
  uint8_t  intensity    = 0;
  uint8_t  pulseHz      = 0;
  uint16_t durationMs   = 0;
  uint32_t scheduledAt  = 0;   // hub's clock, low 32 bits
};
PendingCmd pending;

// Hub-clock offset. Learned from the first command: we assume it was sent
// "now", which bounds the error to the one-way BLE delay. Good enough to
// coordinate L/R to the ~15 ms target; a proper sync is a Phase 7 task.
int64_t clockOffsetMs   = 0;
bool    clockOffsetKnown = false;

inline uint32_t hubNowMs() { return (uint32_t)((int64_t)millis() + clockOffsetMs); }

// -------------------------------- indicators --------------------------------
void beep(uint16_t freq, uint16_t ms) {
  tone(PIN_BUZZER, freq, ms);
  delay(ms);
  noTone(PIN_BUZZER);
}

void ledPattern(uint8_t blinks, uint16_t onMs) {
  for (uint8_t i = 0; i < blinks; i++) {
    digitalWrite(PIN_LED, HIGH); delay(onMs);
    digitalWrite(PIN_LED, LOW);  delay(onMs);
  }
}

void showMode() {
  switch (mode) {
    case M_IDLE:        digitalWrite(PIN_LED, LOW);  break;
    case M_CONNECTED:   digitalWrite(PIN_LED, HIGH); break;
    case M_FAULT:       ledPattern(3, 120); break;
    case M_LOW_BATTERY: ledPattern(1, 400); break;
    default: break;
  }
}

// ------------------------------ haptic playback ------------------------------
void driveOnce(uint8_t intensity, uint16_t ms) {
  if (!driverOk) return;
  uint8_t capped = intensity > INTENSITY_CAP ? INTENSITY_CAP : intensity;
  drv.setRealtimeValue(map(capped, 0, 100, 0, 127));
  delay(ms);
  drv.setRealtimeValue(0);
}

void playPattern(uint8_t patternId, uint8_t intensity, uint8_t pulseHz, uint16_t durationMs) {
  uint8_t  pulses = 1;
  uint16_t pulseMs = durationMs;
  uint16_t gapMs = 0;
  uint8_t  repeat = 1;

  // mirrors config/haptic_patterns.yaml
  switch (patternId) {
    case P_TURN_LEFT:
    case P_TURN_RIGHT:     pulses = 2; pulseMs = 90;  gapMs = 110; break;
    case P_FOUND:          pulses = 1; pulseMs = 280; gapMs = 0;   break;
    case P_OBSTACLE_NEAR:  pulses = 3; pulseMs = 70;  gapMs = 90;  break;
    case P_URGENT:         pulses = 6; pulseMs = 60;  gapMs = 50; repeat = 2; break;
    case P_FAULT:          pulses = 2; pulseMs = 400; gapMs = 250; break;
    case P_LOW_BATTERY:    pulses = 1; pulseMs = 150; gapMs = 0;   break;
    default:               droppedPackets++; return;
  }

  if (pulseHz > 0 && patternId != P_FOUND) {
    uint16_t period = 1000 / pulseHz;
    if (period > pulseMs) gapMs = period - pulseMs;
  }

  for (uint8_t r = 0; r < repeat; r++) {
    for (uint8_t p = 0; p < pulses; p++) {
      driveOnce(intensity, pulseMs);
      if (p + 1 < pulses) delay(gapMs);
    }
    if (r + 1 < repeat) delay(gapMs * 2);
  }
  playedPackets++;
}

void publishStatus() {
  if (!statusChar) return;
  // side, formatVersion, battery, driverOk, dropped(16), played(16)
  uint8_t s[8];
  s[0] = BAND_SIDE;
  s[1] = FORMAT_VERSION;
  s[2] = battPercent;
  s[3] = driverOk ? 1 : 0;
  s[4] = droppedPackets & 0xFF;
  s[5] = (droppedPackets >> 8) & 0xFF;
  s[6] = playedPackets & 0xFF;
  s[7] = (playedPackets >> 8) & 0xFF;
  statusChar->setValue(s, sizeof(s));
  statusChar->notify();
}

/*
 * B1.4 — motor-start echo.
 *
 * Reports, in the HUB's own clock, the moment this band actually started
 * its motor. The hub subtracts the two bands' values to get the real
 * left/right offset. Without this the "15 ms" figure would be a guess,
 * and the whole directional-haptic claim rests on it being measured.
 *
 * 10 bytes: side(1) pattern(1) motorStartHubMs(4) lateByMs(2) seq(2)
 */
void publishEcho(uint8_t patternId, uint32_t motorStartHubMs,
                 int32_t lateBy, uint16_t seq) {
  if (!echoChar) return;
  int16_t late = (int16_t)constrain(lateBy, -32768, 32767);
  uint8_t e[10];
  e[0] = BAND_SIDE;
  e[1] = patternId;
  e[2] = motorStartHubMs & 0xFF;
  e[3] = (motorStartHubMs >> 8) & 0xFF;
  e[4] = (motorStartHubMs >> 16) & 0xFF;
  e[5] = (motorStartHubMs >> 24) & 0xFF;
  e[6] = late & 0xFF;
  e[7] = (late >> 8) & 0xFF;
  e[8] = seq & 0xFF;
  e[9] = (seq >> 8) & 0xFF;
  echoChar->setValue(e, sizeof(e));
  echoChar->notify();
}

// ------------------------------ command decoder ------------------------------
// Validates EVERY field. A malformed packet is dropped and counted, never played.
void decodeCommand(const uint8_t* d, size_t len) {
  if (len != WIRE_SIZE) { droppedPackets++; return; }

  uint8_t ver = d[0];
  if (ver != FORMAT_VERSION) {
    droppedPackets++;
    // Version mismatch is announced AUDIBLY rather than failing silently.
    beep(2600, 120); delay(80); beep(1800, 120);
    publishStatus();
    return;
  }

  uint8_t target    = d[1];
  uint8_t patternId = d[2];
  uint8_t intensity = d[3];
  uint8_t pulseHz   = d[4];
  uint16_t durationMs = (uint16_t)d[6] | ((uint16_t)d[7] << 8);
  uint32_t scheduledAt = (uint32_t)d[8]  | ((uint32_t)d[9]  << 8)
                       | ((uint32_t)d[10] << 16) | ((uint32_t)d[11] << 24);

  if (target > T_BOTH)                 { droppedPackets++; return; }
  if (patternId < 1 || patternId > 7)  { droppedPackets++; return; }
  if (intensity > 100)                 { droppedPackets++; return; }
  if (durationMs > 5000)               { droppedPackets++; return; }

  // is this command for THIS band?
  bool forUs = (target == T_BOTH) ||
               (target == T_LEFT  && BAND_SIDE == 0) ||
               (target == T_RIGHT && BAND_SIDE == 1);
  if (!forUs) return;

  if (!clockOffsetKnown) {
    clockOffsetMs = (int64_t)scheduledAt - (int64_t)millis();
    clockOffsetKnown = true;
  }

  pending.active      = true;
  pending.patternId   = patternId;
  pending.intensity   = intensity;
  pending.pulseHz     = pulseHz;
  pending.durationMs  = durationMs;
  pending.scheduledAt = scheduledAt;
}

// --------------------------------- BLE glue ---------------------------------
class CmdCallbacks : public NimBLECharacteristicCallbacks {
  void onWrite(NimBLECharacteristic* c) override {
    std::string v = c->getValue();
    decodeCommand((const uint8_t*)v.data(), v.length());
  }
};

class ServerCallbacks : public NimBLEServerCallbacks {
  void onConnect(NimBLEServer* s, ble_gap_conn_desc* desc) override {
    clientConnected = true;
    mode = M_CONNECTED;
    // Request a short connection interval. This directly affects the
    // haptic.sent -> haptic.motor.start segment of the latency budget.
    s->updateConnParams(desc->conn_handle, 6, 12, 0, 60);   // 7.5-15 ms
    showMode();
    beep(2000, 60);
  }
  void onDisconnect(NimBLEServer* s) override {
    clientConnected = false;
    clockOffsetKnown = false;
    mode = M_IDLE;
    showMode();
    NimBLEDevice::startAdvertising();
  }
};

// ----------------------------------- boot -----------------------------------
void selfTest() {
  ledPattern(2, 100);
  beep(1500, 80);
  if (driverOk) { driveOnce(45, 160); }
  else {
    // self-test failure shown on LED AND buzzer
    mode = M_FAULT;
    ledPattern(5, 80);
    beep(600, 300);
  }
}

void setup() {
  pinMode(PIN_LED, OUTPUT);
  pinMode(PIN_BUZZER, OUTPUT);
  digitalWrite(PIN_LED, LOW);

  Wire.begin(PIN_SDA, PIN_SCL);
  driverOk = drv.begin();
  if (driverOk) {
    drv.selectLibrary(6);            // LRA library
    drv.setMode(DRV2605_MODE_REALTIME);
    drv.useLRA();
  }

  selfTest();

  char name[20];
  snprintf(name, sizeof(name), "Assistive-%c", BAND_SIDE == 0 ? 'L' : 'R');
  NimBLEDevice::init(name);
  NimBLEDevice::setPower(ESP_PWR_LVL_P9);

  NimBLEServer* server = NimBLEDevice::createServer();
  server->setCallbacks(new ServerCallbacks());

  NimBLEService* svc = server->createService(SVC_UUID);

  NimBLECharacteristic* cmd = svc->createCharacteristic(
    CMD_UUID, NIMBLE_PROPERTY::WRITE | NIMBLE_PROPERTY::WRITE_NR);
  cmd->setCallbacks(new CmdCallbacks());

  statusChar = svc->createCharacteristic(
    STATUS_UUID, NIMBLE_PROPERTY::READ | NIMBLE_PROPERTY::NOTIFY);

  echoChar = svc->createCharacteristic(
    ECHO_UUID, NIMBLE_PROPERTY::READ | NIMBLE_PROPERTY::NOTIFY);

  svc->start();

  NimBLEAdvertising* adv = NimBLEDevice::getAdvertising();
  adv->addServiceUUID(SVC_UUID);
  adv->setName(name);
  adv->start();

  if (mode != M_FAULT) mode = M_IDLE;
  showMode();
}

void loop() {
  static uint16_t echoSeq = 0;

  if (pending.active) {
    if (!clockOffsetKnown || (int32_t)(hubNowMs() - pending.scheduledAt) >= 0) {
      PendingCmd c = pending;
      pending.active = false;

      uint32_t motorStartHub = hubNowMs();
      int32_t  lateBy = (int32_t)(motorStartHub - c.scheduledAt);

      playPattern(c.patternId, c.intensity, c.pulseHz, c.durationMs);

      publishEcho(c.patternId, motorStartHub, lateBy, ++echoSeq);
      publishStatus();
    }
  }

  // battery every 10 s
  if (millis() - lastBattMs > 10000) {
    lastBattMs = millis();
    int raw = analogRead(PIN_BATT);
    float v = (raw / 4095.0f) * 3.3f * 2.0f;          // /2 divider
    battPercent = (uint8_t)constrain((v - 3.30f) / (4.20f - 3.30f) * 100.0f, 0, 100);
    if (battPercent <= 15 && mode == M_CONNECTED) {
      mode = M_LOW_BATTERY;
      playPattern(P_LOW_BATTERY, 35, 1, 150);
      showMode();
      mode = M_CONNECTED;
    }
    publishStatus();
  }

  delay(2);
}
