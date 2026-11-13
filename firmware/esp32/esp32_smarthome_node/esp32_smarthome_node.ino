/*
 * ESP32 Smart Home Node — 1 bo mạch, nhiều thiết bị, 1 kết nối MQTT
 * Cùng topic & payload với devices/home_sim.py nên dashboard + automation dùng chung.
 *
 * Thư viện (Arduino Library Manager):
 *   - PubSubClient (Nick O'Leary)
 *   - DHT sensor library (Adafruit) + Adafruit Unified Sensor
 *   - ArduinoJson (v7)
 *
 * Phần cứng (tắt bớt bằng các #define USE_... nếu không có):
 *   lab/climate   DHT22                  DATA -> GPIO 4  (kéo lên 10k nếu là module trần)
 *   lab/light     Relay kênh 1 (đèn)     IN   -> GPIO 26
 *   lab/fan       Relay kênh 2 (quạt)    IN   -> GPIO 27
 *   lab/motion    PIR HC-SR501           OUT  -> GPIO 14
 *   lab/door      Công tắc từ (reed)     GPIO 13 <-> GND (dùng INPUT_PULLUP)
 *   lab/gas       MQ-2 (chân AO)         AO   -> GPIO 34 qua cầu phân áp (MQ-2 nuôi 5V, ADC ESP32 tối đa 3.3V!)
 *   Nút nhấn tại chỗ                     GPIO 0 (nút BOOT có sẵn) -> bật/tắt đèn
 *
 * Vì sao có "node"?  Mỗi kết nối MQTT chỉ có MỘT Last Will. ESP32 dùng 1 kết nối cho 6 thiết bị,
 * nên LWT được đặt trên topic của bo mạch: home/lab/esp32-01/status (type "node").
 * Mỗi thiết bị con khai báo "node":"esp32-01" trong status; dashboard và automation coi thiết bị
 * con là offline khi bo mạch offline.
 *
 * Lưu ý: PubSubClient chỉ publish QoS 0 (subscribe được QoS 1). LWT vẫn QoS 1 + retain.
 */
#include <WiFi.h>
#include <PubSubClient.h>
#include <DHT.h>
#include <ArduinoJson.h>
#include <time.h>

// ---------- cấu hình ----------
// WiFi + địa chỉ broker nằm trong secrets.h (không đưa lên git).
// Lần đầu: copy secrets.example.h thành secrets.h rồi điền thông tin của bạn.
#include "secrets.h"

const char* PREFIX      = "home";
const char* ROOM        = "lab";
const char* ROOM_NAME   = "Phòng Lab (ESP32)";
const char* NODE_ID     = "esp32-01";
const char* FW          = "esp32-2.0.0";
const uint16_t KEEPALIVE = 10;              // giây

#define USE_DHT    1
#define USE_LIGHT  1
#define USE_FAN    1
#define USE_PIR    1
#define USE_DOOR   1
#define USE_GAS    1

#define PIN_DHT     4
#define PIN_LIGHT   26
#define PIN_FAN     27
#define PIN_PIR     14
#define PIN_DOOR    13
#define PIN_GAS     34
#define PIN_BUTTON  0
#define RELAY_ACTIVE_LOW  true              // đa số module relay kích mức thấp
#define GAS_ALARM_PPM     1000              // ước lượng thô từ ADC, chưa hiệu chuẩn
#define CLIMATE_EVERY_MS  5000
#define GAS_EVERY_MS      2000
#define NODE_EVERY_MS     30000

// ---------- biến toàn cục ----------
WiFiClient net;
PubSubClient mqtt(net);
DHT dht(PIN_DHT, DHT22);

bool lightOn = false, fanOn = false, motion = false, doorOpen = false, gasAlarm = false;
int gasPpm = 0;
uint32_t lastClimate = 0, lastGas = 0, lastNode = 0, lastMqttTry = 0, lastBtn = 0;
char tNodeStatus[80], tNodeSet[80], tLightSet[80], tFanSet[80];

// ---------- tiện ích ----------
void topicOf(char* buf, size_t n, const char* dev, const char* kind) {
  snprintf(buf, n, "%s/%s/%s/%s", PREFIX, ROOM, dev, kind);
}

uint64_t nowMs() {                              // epoch ms từ NTP (0 nếu chưa đồng bộ)
  time_t now = time(nullptr);
  return now > 1700000000 ? (uint64_t)now * 1000ULL : 0;
}

void publishDoc(const char* dev, const char* kind, JsonDocument& doc, bool retained = true) {
  char topic[80], buf[384];
  topicOf(topic, sizeof topic, dev, kind);
  if (nowMs()) doc["ts"] = nowMs();
  size_t n = serializeJson(doc, buf);
  mqtt.publish(topic, (const uint8_t*)buf, n, retained);
}

void writeRelay(int pin, bool on) {
  digitalWrite(pin, (on ^ RELAY_ACTIVE_LOW) ? HIGH : LOW);
}

// ---------- status (discovery) ----------
void publishEntityStatus(const char* dev, const char* type, const char* name, void (*caps)(JsonObject)) {
  JsonDocument doc;
  doc["state"] = "online";
  doc["type"] = type;
  doc["name"] = name;
  doc["room_name"] = ROOM_NAME;
  doc["node"] = NODE_ID;
  doc["fw"] = FW;
  JsonObject c = doc["caps"].to<JsonObject>();
  if (caps) caps(c);
  publishDoc(dev, "status", doc);
}

void publishNodeStatus() {
  JsonDocument doc;
  doc["state"] = "online";
  doc["type"] = "node";
  doc["name"] = "ESP32 DevKit";
  doc["room_name"] = ROOM_NAME;
  doc["fw"] = FW;
  doc["ip"] = WiFi.localIP().toString();
  doc["keepalive"] = KEEPALIVE;
  doc["caps"].to<JsonObject>();
  publishDoc(NODE_ID, "status", doc);
}

// ---------- state ----------
void publishNodeState() {
  JsonDocument doc;
  doc["rssi"] = WiFi.RSSI();
  doc["uptime"] = millis() / 1000;
  doc["heap"] = ESP.getFreeHeap();
  publishDoc(NODE_ID, "state", doc);
}

void publishLight() {
  JsonDocument doc;
  doc["on"] = lightOn;
  publishDoc("light", "state", doc);
}

void publishFan() {
  JsonDocument doc;
  doc["on"] = fanOn;
  doc["speed"] = 1;
  publishDoc("fan", "state", doc);
}

void publishMotion() {
  JsonDocument doc;
  doc["motion"] = motion;
  if (motion && nowMs()) doc["last_motion"] = nowMs();
  publishDoc("motion", "state", doc);
}

void publishDoor() {
  JsonDocument doc;
  doc["open"] = doorOpen;
  publishDoc("door", "state", doc);
}

void publishGas() {
  JsonDocument doc;
  doc["ppm"] = gasPpm;
  doc["alarm"] = gasAlarm;
  doc["raw"] = analogRead(PIN_GAS);
  publishDoc("gas", "state", doc);
}

void publishClimate() {
  float t = dht.readTemperature(), h = dht.readHumidity();
  if (isnan(t) || isnan(h)) { Serial.println("Đọc DHT22 lỗi"); return; }
  JsonDocument doc;
  doc["temperature"] = round(t * 100) / 100.0;
  doc["humidity"] = round(h * 10) / 10.0;
  publishDoc("climate", "state", doc);
  Serial.printf("-> climate T=%.2f H=%.1f\n", t, h);
}

// ---------- nhận lệnh ----------
// Hỗ trợ {"on":true}, {"toggle":true}. Thiết bị bỏ qua các khóa không hiểu ("from", "via", "ts"...)
bool applyOnOff(JsonDocument& doc, bool current) {
  if (doc["toggle"] | false) current = !current;
  if (doc["on"].is<bool>()) current = doc["on"].as<bool>();
  return current;
}

void onMessage(char* topic, byte* payload, unsigned int len) {
  JsonDocument doc;
  if (deserializeJson(doc, payload, len)) return;
  Serial.printf("<- %s từ %s\n", topic, (const char*)(doc["from"] | "?"));

  if (!strcmp(topic, tLightSet)) {
    lightOn = applyOnOff(doc, lightOn);
    writeRelay(PIN_LIGHT, lightOn);
    publishLight();
  } else if (!strcmp(topic, tFanSet)) {
    fanOn = applyOnOff(doc, fanOn);
    writeRelay(PIN_FAN, fanOn);
    publishFan();
  } else if (!strcmp(topic, tNodeSet)) {
    const char* action = doc["action"] | "";
    if (!strcmp(action, "crash")) net.stop();           // đóng TCP thô, không DISCONNECT -> broker phát LWT
    else if (!strcmp(action, "restart")) ESP.restart();
  }
}

// ---------- kết nối ----------
void connectWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.print("WiFi");
  while (WiFi.status() != WL_CONNECTED) { delay(400); Serial.print("."); }
  Serial.printf("\nIP: %s\n", WiFi.localIP().toString().c_str());
}

void announceAll() {
  publishNodeStatus();
  publishNodeState();
#if USE_DHT
  publishEntityStatus("climate", "climate", "Nhiệt độ & độ ẩm (DHT22)", [](JsonObject c) { c["temperature"] = "°C"; c["humidity"] = "%"; });
  publishClimate();
#endif
#if USE_LIGHT
  publishEntityStatus("light", "light", "Đèn (relay 1)", [](JsonObject c) { c["dimmable"] = false; });
  publishLight();
#endif
#if USE_FAN
  publishEntityStatus("fan", "fan", "Quạt (relay 2)", [](JsonObject c) { c["speeds"] = 1; });
  publishFan();
#endif
#if USE_PIR
  publishEntityStatus("motion", "motion", "Cảm biến PIR", nullptr);
  publishMotion();
#endif
#if USE_DOOR
  publishEntityStatus("door", "door", "Công tắc từ cửa", nullptr);
  publishDoor();
#endif
#if USE_GAS
  publishEntityStatus("gas", "gas", "Cảm biến gas MQ-2", [](JsonObject c) { c["threshold"] = GAS_ALARM_PPM; });
  publishGas();
#endif
}

// Không chặn: thử lại mỗi 2s để nút nhấn tại chỗ vẫn hoạt động khi mất broker
void maintainMqtt() {
  if (mqtt.connected() || millis() - lastMqttTry < 2000) return;
  lastMqttTry = millis();
  static const char* WILL = "{\"state\":\"offline\",\"reason\":\"lwt\"}";
  Serial.print("MQTT connect...");
  // connect(id, user, pass, willTopic, willQos, willRetain, willMessage, cleanSession)
  if (mqtt.connect(NODE_ID, MQTT_USER, MQTT_PASS, tNodeStatus, 1, true, WILL, true)) {
    Serial.println("OK");
    announceAll();
    mqtt.subscribe(tNodeSet, 1);
#if USE_LIGHT
    mqtt.subscribe(tLightSet, 1);
#endif
#if USE_FAN
    mqtt.subscribe(tFanSet, 1);
#endif
  } else {
    Serial.printf("lỗi rc=%d\n", mqtt.state());
  }
}

// ---------- setup / loop ----------
void setup() {
  Serial.begin(115200);
  topicOf(tNodeStatus, sizeof tNodeStatus, NODE_ID, "status");
  topicOf(tNodeSet, sizeof tNodeSet, NODE_ID, "set");
  topicOf(tLightSet, sizeof tLightSet, "light", "set");
  topicOf(tFanSet, sizeof tFanSet, "fan", "set");

  pinMode(PIN_LIGHT, OUTPUT); writeRelay(PIN_LIGHT, false);
  pinMode(PIN_FAN, OUTPUT);   writeRelay(PIN_FAN, false);
  pinMode(PIN_PIR, INPUT);
  pinMode(PIN_DOOR, INPUT_PULLUP);
  pinMode(PIN_BUTTON, INPUT_PULLUP);
  dht.begin();

  connectWiFi();
  configTime(0, 0, "pool.ntp.org", "time.google.com");     // timestamp cho payload
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setKeepAlive(KEEPALIVE);
  mqtt.setBufferSize(512);
  mqtt.setCallback(onMessage);
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) connectWiFi();
  maintainMqtt();
  mqtt.loop();                                   // xử lý PINGREQ (keep-alive) + message đến
  uint32_t now = millis();

  // Nút tại chỗ: đổi trạng thái đèn rồi BÁO LÊN broker -> dashboard luôn đúng với thực tế
  if (USE_LIGHT && digitalRead(PIN_BUTTON) == LOW && now - lastBtn > 400) {
    lastBtn = now;
    lightOn = !lightOn;
    writeRelay(PIN_LIGHT, lightOn);
    if (mqtt.connected()) publishLight();
  }
#if USE_PIR
  bool m = digitalRead(PIN_PIR) == HIGH;
  if (m != motion) { motion = m; if (mqtt.connected()) publishMotion(); }
#endif
#if USE_DOOR
  static uint32_t doorChanged = 0;
  bool d = digitalRead(PIN_DOOR) == HIGH;       // nam châm rời xa -> mạch hở -> HIGH = cửa mở
  if (d != doorOpen && now - doorChanged > 100) {
    doorChanged = now; doorOpen = d;
    if (mqtt.connected()) publishDoor();
  }
#endif
#if USE_GAS
  if (now - lastGas >= GAS_EVERY_MS) {
    lastGas = now;
    gasPpm = analogRead(PIN_GAS) * 10000L / 4095;  // ước lượng tuyến tính 0..10000 ppm
    bool alarm = gasAlarm ? gasPpm > GAS_ALARM_PPM * 0.9 : gasPpm > GAS_ALARM_PPM;   // trễ 10% chống nhấp nháy
    static uint32_t lastGasPub = 0;
    if ((alarm != gasAlarm || now - lastGasPub >= CLIMATE_EVERY_MS) && mqtt.connected()) {
      gasAlarm = alarm; lastGasPub = now;
      publishGas();
    }
    gasAlarm = alarm;
  }
#endif
#if USE_DHT
  if (now - lastClimate >= CLIMATE_EVERY_MS && mqtt.connected()) { lastClimate = now; publishClimate(); }
#endif
  if (now - lastNode >= NODE_EVERY_MS && mqtt.connected()) { lastNode = now; publishNodeState(); }
}
