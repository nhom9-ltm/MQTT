// Mẫu cấu hình riêng của từng người — copy file này thành secrets.h rồi điền thông tin.
// secrets.h đã nằm trong .gitignore nên mật khẩu WiFi không bị đưa lên GitHub.
#pragma once

const char* WIFI_SSID   = "TEN_WIFI";
const char* WIFI_PASS   = "MAT_KHAU_WIFI";
const char* MQTT_HOST   = "192.168.1.10";   // IP LAN của máy chạy Mosquitto
const uint16_t MQTT_PORT = 1883;            // 8883 khi bật TLS bên dưới
const char* MQTT_USER   = nullptr;          // hoặc "esp32-01" khi bật ACL
const char* MQTT_PASS   = nullptr;

// Mã hóa TLS (docs/TLS.md): đổi thành 1, đặt MQTT_PORT = 8883 và chạy
//   python infra/broker/gen_certs.py --host <MQTT_HOST>
// để có ca_cert.h cạnh file .ino. MQTT_HOST phải nằm trong danh sách Tên/IP script in ra.
#define MQTT_USE_TLS 0
