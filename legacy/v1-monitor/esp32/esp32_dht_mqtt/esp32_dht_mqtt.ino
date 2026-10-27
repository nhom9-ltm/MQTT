/*
 * ESP32 / ESP8266 + DHT22 -> MQTT
 * Cùng định dạng topic & payload với sensor_sim.py, nên dashboard dùng chung.
 *
 * Thư viện (Arduino Library Manager):
 *   - PubSubClient (Nick O'Leary)
 *   - DHT sensor library (Adafruit) + Adafruit Unified Sensor
 *   - ArduinoJson (v7)
 *
 * Nối dây DHT22: VCC -> 3V3, GND -> GND, DATA -> GPIO 4 (điện trở kéo lên 10k nếu module trần)
 *
 * Lưu ý: PubSubClient chỉ publish được QoS 0 (subscribe được QoS 0/1).
 * LWT vẫn hỗ trợ QoS 1 + retain.
 */
#if defined(ESP32)
  #include <WiFi.h>
#else
  #include <ESP8266WiFi.h>
#endif
#include <PubSubClient.h>
#include <DHT.h>
#include <ArduinoJson.h>
#include <time.h>

// ---------- cấu hình ----------
const char* WIFI_SSID   = "TEN_WIFI";
const char* WIFI_PASS   = "MAT_KHAU_WIFI";
const char* MQTT_HOST   = "192.168.1.10";   // IP máy chạy Mosquitto
const uint16_t MQTT_PORT = 1883;
const char* MQTT_USER   = nullptr;          // hoặc "sensor-esp32"
const char* MQTT_PASS   = nullptr;

const char* PREFIX      = "iot";
const char* ROOM        = "lab";
const char* DEVICE_ID   = "esp32-01";
const uint16_t KEEPALIVE = 10;              // giây

#define DHT_PIN  4
#define DHT_TYPE DHT22

// ---------- biến toàn cục ----------
WiFiClient net;
PubSubClient mqtt(net);
DHT dht(DHT_PIN, DHT_TYPE);

char tTelemetry[96], tStatus[96], tCmd[96];
uint32_t intervalMs = 2000, lastPub = 0, seq = 0;
bool paused = false;

// epoch ms từ NTP (0 nếu chưa đồng bộ)
uint64_t nowMs() {
  time_t now = time(nullptr);
  return now > 1700000000 ? (uint64_t)now * 1000ULL : 0;
}

void publishStatus(const char* state) {
  JsonDocument doc;
  doc["state"] = state;
  if (nowMs()) doc["ts"] = nowMs();
  doc["interval"] = intervalMs / 1000.0;
  doc["qos"] = 0;
  doc["keepalive"] = KEEPALIVE;
  doc["ip"] = WiFi.localIP().toString();
  doc["fw"] = "esp-1.0.0";
  char buf[200];
  size_t n = serializeJson(doc, buf);
  mqtt.publish(tStatus, (const uint8_t*)buf, n, true);   // retained
}

void onMessage(char* topic, byte* payload, unsigned int len) {
  JsonDocument doc;
  if (deserializeJson(doc, payload, len)) return;
  const char* action = doc["action"] | "";
  Serial.printf("CMD: %s\n", action);
  if (!strcmp(action, "set_interval")) {
    intervalMs = max(500.0f, doc["value"].as<float>() * 1000);
    publishStatus("online");
  } else if (!strcmp(action, "pause"))  { paused = true;  publishStatus("paused"); }
  else if (!strcmp(action, "resume"))   { paused = false; publishStatus("online"); }
  else if (!strcmp(action, "crash"))    { net.stop(); }    // đóng TCP thô -> broker phát LWT
}

void connectWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.print("WiFi");
  while (WiFi.status() != WL_CONNECTED) { delay(400); Serial.print("."); }
  Serial.printf("\nIP: %s\n", WiFi.localIP().toString().c_str());
}

void connectMqtt() {
  static const char* WILL = "{\"state\":\"offline\",\"reason\":\"lwt\"}";
  while (!mqtt.connected()) {
    Serial.print("MQTT connect...");
    // connect(id, user, pass, willTopic, willQos, willRetain, willMessage, cleanSession)
    if (mqtt.connect(DEVICE_ID, MQTT_USER, MQTT_PASS, tStatus, 1, true, WILL, true)) {
      Serial.println("OK");
      publishStatus("online");
      mqtt.subscribe(tCmd, 1);
    } else {
      Serial.printf("lỗi rc=%d, thử lại sau 2s\n", mqtt.state());
      delay(2000);
    }
  }
}

void setup() {
  Serial.begin(115200);
  dht.begin();
  snprintf(tTelemetry, sizeof tTelemetry, "%s/%s/%s/telemetry", PREFIX, ROOM, DEVICE_ID);
  snprintf(tStatus,    sizeof tStatus,    "%s/%s/%s/status",    PREFIX, ROOM, DEVICE_ID);
  snprintf(tCmd,       sizeof tCmd,       "%s/%s/%s/cmd",       PREFIX, ROOM, DEVICE_ID);

  connectWiFi();
  configTime(0, 0, "pool.ntp.org", "time.google.com");   // đồng bộ giờ cho timestamp
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setKeepAlive(KEEPALIVE);
  mqtt.setBufferSize(512);
  mqtt.setCallback(onMessage);
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) connectWiFi();
  if (!mqtt.connected()) connectMqtt();
  mqtt.loop();                                   // xử lý PINGREQ (keep-alive) + message đến

  if (!paused && millis() - lastPub >= intervalMs) {
    lastPub = millis();
    float t = dht.readTemperature();
    float h = dht.readHumidity();
    if (isnan(t) || isnan(h)) { Serial.println("Đọc DHT lỗi"); return; }

    JsonDocument doc;
    doc["device"] = DEVICE_ID;
    doc["room"] = ROOM;
    doc["temperature"] = round(t * 100) / 100.0;
    doc["humidity"] = round(h * 10) / 10.0;
    doc["rssi"] = WiFi.RSSI();
    doc["seq"] = ++seq;
    if (nowMs()) doc["ts"] = nowMs();          // chưa có NTP -> dashboard dùng giờ nhận
    char buf[256];
    size_t n = serializeJson(doc, buf);
    mqtt.publish(tTelemetry, (const uint8_t*)buf, n, true);   // retained
    Serial.printf("-> T=%.2f H=%.1f\n", t, h);
  }
}
