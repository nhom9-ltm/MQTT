# 🌡️ [v1 — bản cũ] Hệ thống giám sát Nhiệt độ / Độ ẩm qua MQTT

> **Đây là phiên bản 1 của project**, được giữ lại để tham khảo và so sánh. Phiên bản hiện tại là hệ thống
> **Nhà thông minh** (điều khiển thiết bị, luật tự động, kịch bản, ESP32 nhiều cảm biến). Xem
> [README chính](../../README.md).
>
> | | v1 (thư mục này) | v2 — Nhà thông minh |
> |---|---|---|
> | Topic gốc | `iot/<phòng>/<device>/{telemetry,status,cmd}` | `home/<phòng>/<thiết bị>/{status,state,set}` |
> | Thiết bị | cảm biến nhiệt ẩm | 11 loại: đèn, quạt, điều hòa, rèm, khóa, ổ cắm, gas… |
> | Điều khiển | đổi chu kỳ gửi, tạm dừng, giả lập sự cố | bật/tắt, độ sáng, nhiệt độ đặt, vị trí rèm, khóa cửa |
> | Tự động hóa | — | automation engine + luật + kịch bản |
>
> Hai phiên bản dùng prefix khác nhau (`iot` và `home`) nên có thể chạy chung một broker.

Cảm biến (ESP32 thật hoặc script Python giả lập) publish dữ liệu lên **Mosquitto**; dashboard web
subscribe qua **MQTT over WebSocket** và vẽ biểu đồ thời gian thực bằng **Chart.js**.
Một logger lưu lịch sử vào SQLite để minh họa **QoS 1 + persistent session**.

```
 ┌──────────────┐  MQTT/TCP :1883   ┌──────────────────┐  WebSocket :9001  ┌───────────────────┐
 │ ESP32 + DHT22│ ────────────────▶ │                  │ ────────────────▶ │  Dashboard web    │
 │ sensor_sim.py│ ◀──── cmd ─────── │    Mosquitto     │ ◀──── cmd ─────── │  MQTT.js+Chart.js │
 └──────────────┘                   │  (retain, LWT,   │                   └───────────────────┘
                                    │   persistence)   │  MQTT/TCP :1883   ┌───────────────────┐
                                    │                  │ ────────────────▶ │ logger.py → SQLite│
                                    └──────────────────┘                   └───────────────────┘
```

## Cấu trúc thư mục

```
legacy/v1-monitor/
├── docker-compose.yml        # Mosquitto + nginx phục vụ dashboard
├── broker/
│   ├── mosquitto.conf        # listener 1883 (MQTT) + 9001 (WebSocket), persistence, $SYS
│   └── acl.conf              # phân quyền mẫu (khi bật xác thực)
├── sensor/sensor_sim.py      # cảm biến giả lập (1 hoặc nhiều thiết bị)
├── logger/logger.py          # lưu lịch sử vào SQLite, xuất CSV
├── dashboard/                # index.html + style.css + app.js
└── esp32/esp32_dht_mqtt/     # sketch Arduino cho ESP32/ESP8266 + DHT22
```

## Thiết kế topic

| Topic | Hướng | QoS | Retain | Nội dung |
|---|---|---|---|---|
| `iot/<phòng>/<device>/telemetry` | thiết bị → broker | 0/1/2 (mặc định 1) | ✔ | `{"temperature":28.4,"humidity":61.2,"battery":97.1,"seq":42,"ts":...}` |
| `iot/<phòng>/<device>/status` | thiết bị → broker | 1 | ✔ | `{"state":"online"}` · LWT: `{"state":"offline","reason":"lwt"}` |
| `iot/<phòng>/<device>/cmd` | dashboard → thiết bị | 1 | ✘ | `{"action":"set_interval","value":5}` · `pause` · `resume` · `spike` · `crash` |
| `$SYS/broker/...` | broker → dashboard | 0 | – | số client, số message, uptime |

Dashboard subscribe một wildcard duy nhất `iot/+/+/#` → tự phát hiện thiết bị mới, không cần cấu hình.

## Tính năng MQTT được minh họa ở đâu

| Tính năng | Thể hiện trong project | Cách thấy trên dashboard |
|---|---|---|
| **Topic phân cấp & wildcard** | `iot/<phòng>/<device>/<loại>`, subscribe `+` và `#` | Chạy thêm cảm biến → thẻ mới tự xuất hiện |
| **QoS** | `--qos 0/1/2` ở sensor; logger subscribe QoS 1 | Cột QoS trong *Message log*, tag `QoS n` trên thẻ |
| **Retained message** | telemetry + status đều `retain=True` | F5 dashboard → số liệu hiện ngay, tag **RETAINED**, cột Retain ✓ |
| **Last Will (LWT)** | `will_set()` trước `connect()` | Bấm **Mất điện** → badge đỏ *Offline · LWT* + cảnh báo |
| **Keep-alive** | `--keepalive 10`; broker đóng kết nối sau ~1.5 × 10s nếu im lặng | Rút mạng / `kill -9` → LWT xuất hiện sau ≤15s |
| **Graceful vs. bất thường** | Ctrl+C gửi `offline (graceful)` + DISCONNECT → **không** phát LWT | Badge *Offline* (xám) thay vì *Offline · LWT* |
| **Persistent session** | logger: `clean_session=False`, client id cố định | Tắt logger 30s rồi bật lại → in `session_present=True` và nhận bù |
| **Điều khiển 2 chiều** | dashboard publish `.../cmd`, thiết bị subscribe | Đổi chu kỳ 2s→5s, Tạm dừng, Sự cố (nhiệt độ vọt lên) |
| **$SYS** | `sys_interval 5` trong config | 3 ô KPI có nhãn `$SYS` |

---

## Chạy project

Mọi lệnh bên dưới đều chạy **trong thư mục `legacy/v1-monitor/`**:

```bash
cd legacy/v1-monitor
pip install "paho-mqtt>=2.0,<3"      # hoặc: pip install -r ../../BE/requirements.txt
```

### Cách 1 — Docker (khuyên dùng)

```bash
docker compose up -d                 # broker :1883/:9001 + dashboard http://localhost:8080
python sensor/sensor_sim.py --count 3   # 3 cảm biến: living, bedroom, kitchen
python logger/logger.py                 # (tùy chọn) terminal khác
```

Mở **http://localhost:8080** — dashboard tự kết nối `ws://localhost:9001`.

> ⚠️ File `docker-compose.yml` của v1 và v2 dùng cùng tên container (`mqtt-broker`, `mqtt-dashboard`) và
> cùng các cổng 1883 / 9001 / 8080. Hãy `docker compose down` ở thư mục gốc trước khi chạy v1.
> Muốn chạy v1 song song với v2 thì **không** cần docker của v1: cứ để broker v2 chạy, chạy sensor v1
> như trên (prefix `iot` không đụng `home`), rồi mở dashboard v1 bằng `python -m http.server 8081`
> trong thư mục `dashboard/`.

### Cách 2 — Không dùng Docker (Windows/macOS/Linux)

1. Cài Mosquitto: <https://mosquitto.org/download/> (Windows) · `brew install mosquitto` · `sudo apt install mosquitto mosquitto-clients`
2. Sửa `broker/mosquitto.conf`: đổi `persistence_location` thành thư mục có thật (vd `./data/`), rồi chạy
   `mosquitto -c broker/mosquitto.conf -v`
3. Phục vụ dashboard: `cd dashboard && python -m http.server 8080`
4. Chạy sensor/logger như trên.

### Cách 3 — Chỉ xem giao diện

Mở `dashboard/index.html` rồi bấm **Demo** (hoặc thêm `?demo=1` vào URL). Toàn bộ broker và 3 cảm biến
được giả lập trong trình duyệt — dùng làm phương án dự phòng khi thuyết trình mà mạng/broker trục trặc.

> Dashboard tải MQTT.js, Chart.js và font từ CDN nên cần Internet. Nếu phòng thuyết trình không có mạng,
> tải trước 2 file `mqtt.min.js` và `chart.umd.min.js` vào `dashboard/` rồi sửa 2 thẻ `<script>` trỏ tới file local.

### Tham số hữu ích

```bash
python sensor/sensor_sim.py --room kitchen --id sensor-07 --interval 1 --qos 2
python sensor/sensor_sim.py --keepalive 5 --crash-after 20   # 20s sau tự "mất điện"
python sensor/sensor_sim.py --no-retain                      # thử tắt retain để so sánh
python logger/logger.py --export data.csv                    # xuất lịch sử
# Dashboard: http://localhost:8080/?broker=ws://192.168.1.10:9001&prefix=iot
```

Không có broker riêng? Dùng broker công cộng (đổi prefix để tránh trùng người khác):
```bash
python sensor/sensor_sim.py --host test.mosquitto.org --prefix nhom7_iot --count 2
# dashboard: broker = wss://test.mosquitto.org:8081 , prefix = nhom7_iot
```

### Kiểm tra bằng dòng lệnh

```bash
mosquitto_sub -h localhost -t 'iot/#' -v                 # xem mọi message
mosquitto_sub -h localhost -t 'iot/+/+/status' -v -R      # -R: bỏ qua retained cũ
mosquitto_pub -h localhost -t 'iot/living/sensor-01/cmd' -q 1 -m '{"action":"set_interval","value":5}'
mosquitto_pub -h localhost -t 'iot/living/sensor-01/status' -r -n   # xóa retained (thẻ biến mất)
```

### ESP32 thật

Mở `esp32/esp32_dht_mqtt/esp32_dht_mqtt.ino` bằng Arduino IDE, cài thư viện **PubSubClient**,
**DHT sensor library**, **ArduinoJson**, sửa WiFi + IP broker rồi nạp. Topic/payload giống hệt bản giả lập
nên dashboard hiển thị chung. (PubSubClient chỉ publish QoS 0; LWT vẫn QoS 1 + retain.)

---

## Kịch bản thuyết trình (~7 phút)

1. **Kiến trúc (1')** — sơ đồ trên + bảng topic. Nhấn mạnh publisher và subscriber không biết nhau.
2. **Topic & wildcard (1')** — dashboard đang trống, chạy `sensor_sim.py --count 3` → 3 thẻ tự xuất hiện nhờ `iot/+/+/#`.
3. **Retained (1')** — tắt cảm biến bằng Ctrl+C, F5 dashboard: vẫn có số liệu cuối + tag **RETAINED**, cột Retain ✓ trong log.
   Chạy lại sensor rồi so sánh với `--no-retain`.
4. **LWT + Keep-alive (1.5')** — chạy `sensor_sim.py --keepalive 5`, bấm **Mất điện** (hoặc `kill -9`):
   badge chuyển *Offline · LWT* + cảnh báo đỏ. So sánh với Ctrl+C → chỉ *Offline* (graceful, broker không phát Will).
5. **QoS + persistent session (1.5')** — logger đang chạy, sensor `--qos 1`. Tắt logger 30s, bật lại →
   `session_present=True` và dòng `↺ nhận bù … (trễ 25s)`. Lặp lại với sensor `--qos 0` → dữ liệu khi logger tắt bị mất.
6. **Điều khiển 2 chiều (1')** — đổi chu kỳ 2s → 1s (biểu đồ dày hơn), bấm **Sự cố** → nhiệt độ vượt 35°C → thẻ nhấp nháy đỏ.

## Mở rộng (điểm cộng)

- Bật xác thực + ACL: xem cuối `broker/mosquitto.conf` và `broker/acl.conf` (mỗi cảm biến chỉ ghi vào nhánh của mình).
- TLS (port 8883 / wss 8443) bằng chứng chỉ tự ký.
- Nạp `telemetry.db` vào Grafana hoặc thay SQLite bằng InfluxDB.
- MQTT v5: message expiry, user properties, shared subscription `$share/loggers/iot/+/+/telemetry`.
