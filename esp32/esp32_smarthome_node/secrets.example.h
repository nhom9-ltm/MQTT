// Mẫu cấu hình riêng của từng người — copy file này thành secrets.h rồi điền thông tin.
// secrets.h đã nằm trong .gitignore nên mật khẩu WiFi không bị đưa lên GitHub.
#pragma once

const char* WIFI_SSID   = "TEN_WIFI";
const char* WIFI_PASS   = "MAT_KHAU_WIFI";
const char* MQTT_HOST   = "192.168.1.10";   // IP LAN của máy chạy Mosquitto
const uint16_t MQTT_PORT = 1883;
const char* MQTT_USER   = nullptr;          // hoặc "esp32-01" khi bật ACL
const char* MQTT_PASS   = nullptr;
