# 🏠 Nhà thông minh qua MQTT

Hệ thống điều khiển và giám sát nhà thông minh xây dựng trên giao thức **MQTT**. Các thành phần gồm
broker **Mosquitto**, thiết bị thật (**ESP32**) và thiết bị giả lập (**Python**), **dashboard web**,
**automation engine** chạy luật tự động, và **logger** lưu lịch sử vào SQLite.

Các thành phần không gọi trực tiếp nhau. Tất cả chỉ *publish* và *subscribe* qua broker, nên có thể
thêm, bớt hoặc thay một phần mà không phải sửa các phần còn lại.

---

## Mục lục

1. [Bắt đầu nhanh](#1-bắt-đầu-nhanh)
2. [Kiến trúc](#2-kiến-trúc)
3. [Thiết bị](#3-thiết-bị)
4. [Thiết kế topic](#4-thiết-kế-topic)
5. [Các tính năng MQTT được minh họa](#5-các-tính-năng-mqtt-được-minh-họa)
6. [Luật tự động & kịch bản](#6-luật-tự-động--kịch-bản)
7. [ESP32 thật](#7-esp32-thật)
8. [Tham chiếu lệnh](#8-tham-chiếu-lệnh)
9. [Kịch bản thuyết trình](#9-kịch-bản-thuyết-trình-10-phút)
10. [Xử lý sự cố](#10-xử-lý-sự-cố)
11. [Hướng mở rộng](#11-hướng-mở-rộng)

---

## 1. Bắt đầu nhanh

> Chạy trên Windows không có Docker: xem [CACH_CHAY.md](CACH_CHAY.md). Thành viên mới tham gia nhóm: xem [HUONG_DAN_NHOM.md](HUONG_DAN_NHOM.md).

**Yêu cầu:** Python 3.9+, và Docker *hoặc* Mosquitto cài sẵn.

```bash
pip install -r requirements.txt

docker compose up -d                       # broker :1883 / :9001 + dashboard http://localhost:8080
python devices/home_sim.py                 # terminal 1 — 20 thiết bị giả lập
python automation/automation.py            # terminal 2 — luật & kịch bản
python logger/logger.py                    # terminal 3 — (tùy chọn) lưu lịch sử
```

Mở **http://localhost:8080**. Dashboard tự kết nối `ws://localhost:9001` và tự phát hiện mọi thiết bị.

<details>
<summary><b>Không dùng Docker?</b></summary>

1. Cài Mosquitto: <https://mosquitto.org/download/> · macOS `brew install mosquitto` · Ubuntu `sudo apt install mosquitto mosquitto-clients`
2. Trong `broker/mosquitto.conf`, đổi `persistence_location` thành một thư mục có thật (ví dụ `./data/`).
3. Chạy broker: `mosquitto -c broker/mosquitto.conf -v`
4. Phục vụ dashboard: `cd dashboard && python -m http.server 8080`
5. Chạy `home_sim.py`, `automation.py`, `logger.py` như trên.
</details>

<details>
<summary><b>Chỉ muốn xem giao diện (không cần broker)</b></summary>

Mở `dashboard/index.html` rồi bấm **Demo** (hoặc thêm `?demo=1` vào URL). Broker, 20 thiết bị và
automation engine đều được giả lập trong trình duyệt, dùng cùng topic và cùng luật. Nên dùng làm
phương án dự phòng khi thuyết trình.
</details>

<details>
<summary><b>Chạy toàn bộ trong Docker</b></summary>

```bash
docker compose --profile full up -d       # thêm automation + simulator chạy nền
docker compose logs -f automation         # xem log
```
Khi thuyết trình, nên chạy bằng terminal như ở trên để khán giả thấy log lệnh qua lại.
</details>

---

## 2. Kiến trúc

```
 ┌───────────────────┐ MQTT :1883  ┌──────────────────┐ WebSocket :9001 ┌──────────────────────┐
 │ ESP32 node (lab)  │ ──state───▶ │                  │ ──state───────▶ │ Dashboard web        │
 │ relay, DHT22, PIR │ ◀───set──── │                  │ ◀──set──────────│ điều khiển, biểu đồ  │
 ├───────────────────┤             │    Mosquitto     │                 └──────────────────────┘
 │ home_sim.py       │ ──state───▶ │  retain · LWT    │ MQTT :1883      ┌──────────────────────┐
 │ 20 thiết bị ảo    │ ◀───set──── │  QoS · session   │ ◀─────────────▶ │ automation.py        │
 └───────────────────┘             │                  │                 │ luật + kịch bản      │
                                   │                  │ ──────────────▶ ├──────────────────────┤
                                   └──────────────────┘                 │ logger.py → SQLite   │
                                                                        └──────────────────────┘
```

| Thành phần | File | Vai trò |
|---|---|---|
| Broker | `broker/mosquitto.conf`, `acl.conf` | Mosquitto: cổng 1883 (MQTT/TCP), 9001 (WebSocket), persistence, `$SYS`, ACL mẫu |
| Thiết bị giả lập | `devices/home_sim.py` | 4 phòng, 20 thiết bị; mỗi thiết bị là một MQTT client có LWT riêng |
| Thiết bị thật | `esp32/esp32_smarthome_node/` | ESP32: 2 relay, DHT22, PIR, công tắc từ, MQ-2, nút nhấn |
| Automation | `automation/automation.py` + `rules.json`, `scenes.json` | Chạy luật, kịch bản, quản lý chế độ nhà |
| Dashboard | `dashboard/` | Giao diện web (MQTT.js + Chart.js); `demo.js` dùng cho chế độ Demo |
| Logger | `logger/logger.py` | Lưu state, lệnh và cảnh báo vào `logger/smarthome.db`; xuất CSV, in báo cáo |
| Bản cũ | `legacy/v1-monitor/` | Phiên bản 1: chỉ giám sát nhiệt độ/độ ẩm |

### Hai nguyên tắc thiết kế

**1. Tách lệnh (`set`) khỏi trạng thái (`state`).** Bấm công tắc trên dashboard chỉ gửi lệnh đi.
Giao diện chỉ đổi khi thiết bị báo lại `state` mới. Nhờ vậy dashboard luôn đúng với thực tế, kể cả khi
đèn được bật bằng nút trên ESP32 hay do automation bật. Nếu thiết bị không phản hồi trong 4 giây,
dashboard sẽ cảnh báo.

**2. Tự phát hiện thiết bị (discovery) qua retained `status`.** Mỗi thiết bị tự mô tả loại và khả năng
của nó (`type`, `caps`). Dashboard và automation tự nhận thiết bị mới mà không cần cấu hình, và dashboard
tự dựng thẻ điều khiển phù hợp với từng loại.

---

## 3. Thiết bị

| Phòng | Thiết bị — topic `home/<phòng>/<id>` |
|---|---|
| **Phòng khách** `living` | `climate` nhiệt ẩm · `light` đèn có dimmer · `fan` quạt 3 số · `ac` điều hòa · `curtain` rèm · `tv-plug` ổ cắm đo điện · `motion` cảm biến chuyển động |
| **Phòng ngủ** `bedroom` | `climate` · `light` · `ac` · `curtain` |
| **Nhà bếp** `kitchen` | `climate` · `light` · `hood-fan` quạt hút · `stove-plug` bếp điện · `gas` cảm biến gas |
| **Lối vào** `entrance` | `lock` khóa cửa · `door` cảm biến cửa · `motion` · `porch-light` đèn hiên |
| **Lab** `lab` — *ESP32 thật* | `esp32-01` bo mạch · `climate` DHT22 · `light` relay 1 · `fan` relay 2 · `motion` PIR · `door` reed · `gas` MQ-2 |

Bộ giả lập có mô phỏng vật lý đơn giản để demo trông thật hơn:
- Bật điều hòa thì nhiệt độ phòng hạ dần về mức đặt.
- Mở rèm vào ban ngày thì phòng nóng lên.
- Bếp điện tự đóng/ngắt theo rơ-le nhiệt.
- Ổ cắm cộng dồn số kWh đã dùng.

Các thiết bị giả lập nhận thêm 2 lệnh đặc biệt:
- `{"action":"trigger"}`: giả lập sự kiện vật lý (có chuyển động, mở cửa, rò rỉ gas, nắng nóng).
- `{"action":"crash"}`: giả lập mất điện. Thiết bị ngắt kết nối đột ngột để broker phát LWT, rồi tự bật lại sau `--revive` giây.

---

## 4. Thiết kế topic

Mọi topic đều có đúng **4 cấp** `home/<phòng>/<thiết bị>/<loại>`, nên dashboard chỉ cần subscribe một
wildcard: **`home/+/+/+`**.

| Topic | Chiều | QoS | Retain | Ví dụ payload |
|---|---|:-:|:-:|---|
| `home/<phòng>/<id>/status` | thiết bị → | 1 | ✔ | `{"state":"online","type":"light","name":"Đèn trần","caps":{"dimmable":true}}` |
| ↳ LWT của thiết bị | broker → | 1 | ✔ | `{"state":"offline","reason":"lwt"}` |
| `home/<phòng>/<id>/state` | thiết bị → | 1 | ✔ | `{"on":true,"brightness":80,"power":14.4}` · `{"temperature":28.4,"humidity":61}` |
| `home/<phòng>/<id>/set` | → thiết bị | 1 | ✘ | `{"on":false}` · `{"position":50}` · `{"target":25}` · `{"locked":true}` |
| `home/_auto/engine/status` | engine → | 1 | ✔ | danh sách luật + kịch bản (có LWT) |
| `home/_auto/mode/state` | engine → | 1 | ✔ | `{"mode":"away"}` — `home` / `away` / `night` |
| `home/_auto/mode/set` | → engine | 1 | ✘ | `{"mode":"night"}` |
| `home/_auto/scene/set` | → engine | 1 | ✘ | `{"scene":"sleep"}` |
| `home/_auto/rule/set` | → engine | 1 | ✘ | `{"id":"gas_leak","enabled":false}` |
| `home/_auto/notify/event` | engine → | 1 | ✘ | `{"level":"critical","text":"Phát hiện khí gas…"}` |

**Lệnh dùng giá trị tuyệt đối** (`{"on":true}`), không dùng `toggle`. Lý do: QoS 1 có thể giao một message
hai lần. Với lệnh tuyệt đối, nhận hai lần vẫn cho cùng kết quả (*idempotent*); với `toggle` thì đèn sẽ bị
bật rồi tắt ngay.

Các trường `from` / `via` trong lệnh chỉ để hiển thị và ghi log ai đã ra lệnh. Thiết bị bỏ qua các khóa
mà nó không hiểu.

---

## 5. Các tính năng MQTT được minh họa

| Tính năng | Thể hiện ở đâu | Cách thấy trên hệ thống |
|---|---|---|
| **Topic phân cấp & wildcard** | `home/<phòng>/<id>/<loại>`, subscribe `+` | Chạy `home_sim.py --rooms living` trước, sau đó chạy thêm các phòng khác: phòng mới tự xuất hiện |
| **Retained message** | `status`, `state`, chế độ nhà | F5 dashboard thì trạng thái hiện ngay; cột *Retain* ✓ trong log |
| **Last Will (LWT)** | thiết bị ảo, ESP32, automation, dashboard | Bấm **Mất điện**: sau ≤ 15 giây thẻ chuyển *Offline · LWT* |
| **LWT dùng chung cho nhiều thiết bị** | ESP32 đặt LWT trên `esp32-01/status`; thiết bị con khai `"node"` | Rút điện ESP32: cả 6 thẻ Lab chuyển *Bo mạch offline* |
| **Keep-alive** | `--keepalive 10` | `kill -9` tiến trình: LWT đến sau khoảng 1,5 × keep-alive |
| **Ngắt kết nối có kiểm soát** | Ctrl+C gửi `offline (graceful)` + DISCONNECT | Badge *Offline* (không có LWT) |
| **QoS 0 / 1 / 2** | `--qos` khi publish state; lệnh luôn QoS 1 | Cột *QoS* trong Message log |
| **Persistent session** | logger: `clean_session=False`, client id cố định | Tắt logger 30 giây rồi bật lại: `session_present=True` và các dòng `↺ nhận bù` |
| **Tách rời publisher / subscriber** | automation chỉ là một client như bao client khác | Tắt automation: thiết bị và dashboard vẫn chạy, chỉ mất luật tự động |
| **$SYS** | `sys_interval 5` | Ô KPI *Client trên broker* |
| **Xác thực & ACL** | `broker/acl.conf` | Dashboard chỉ được ghi `…/set`, không thể giả mạo `state` của thiết bị |

> **Vì sao ESP32 cần "node"?** Mỗi kết nối MQTT chỉ khai báo được **một** Last Will. ESP32 dùng một kết nối
> cho 6 thiết bị, nên LWT gắn với bo mạch. Dashboard và automation coi một thiết bị con là offline khi bo
> mạch của nó offline. Ngược lại, mỗi thiết bị giả lập có kết nối riêng nên có LWT riêng, giống thiết bị
> WiFi ngoài thực tế.

---

## 6. Luật tự động & kịch bản

### Cấu trúc một luật (`automation/rules.json`)

```json
{
  "id": "living_hot",
  "name": "Phòng khách nóng → bật điều hòa",
  "trigger":    {"device": "living/climate", "field": "temperature", "op": ">", "value": 31},
  "conditions": [{"mode": ["home"]},
                 {"device": "living/ac", "field": "on", "op": "==", "value": false}],
  "actions":    [{"device": "living/ac", "set": {"on": true, "mode": "cool", "target": 26}},
                 {"notify": "Phòng khách {temperature}°C — đã bật điều hòa", "level": "info"}],
  "cooldown": 120
}
```

| Phần | Ý nghĩa |
|---|---|
| `trigger` | Chỉ kích hoạt ở **sườn lên** (từ sai chuyển sang đúng), nên luật không chạy lặp lại mỗi lần cảm biến gửi số liệu. Có 3 dạng: điều kiện thiết bị, `{"at":"23:00"}`, `{"mode":"away"}`. Thêm `"for": 120` để yêu cầu điều kiện giữ nguyên 120 giây. |
| `conditions` | Tất cả phải đúng: `device` · `mode` · `time: {"after":"18:00","before":"06:00"}` |
| `actions` | Chạy tuần tự: `{"device":…,"set":…}` · `{"type":"light","room"?,"except"?,"set":…}` · `{"scene":…}` · `{"mode":…}` · `{"notify":…,"level":…}` · `{"delay":giây}` |
| `cooldown` | Số giây tối thiểu giữa 2 lần chạy |

Trong `notify`, có thể chèn giá trị từ thiết bị đã kích hoạt luật, ví dụ `{temperature}`, `{ppm}`.

### Luật có sẵn

| Luật | Kích hoạt khi | Hành động |
|---|---|---|
| Phòng khách nóng | > 31°C, đang ở nhà, điều hòa tắt | Bật điều hòa 26°C |
| Rò rỉ gas | Cảm biến gas báo động | Ngắt bếp điện, bật quạt hút số 3, cảnh báo đỏ |
| Đèn hiên | Có chuyển động ở lối vào, 17:30–06:00 | Bật đèn hiên 2 phút |
| Xâm nhập (cửa) | Cửa mở khi *Vắng nhà* / *Ban đêm* | Cảnh báo đỏ, bật toàn bộ đèn |
| Xâm nhập (chuyển động) | Có chuyển động ở phòng khách khi *Vắng nhà* | Cảnh báo đỏ, bật đèn phòng khách |
| Tiết kiệm điện | Phòng khách không có chuyển động 2 phút | Tắt đèn và quạt |
| Quên khóa cửa | 23:00, cửa chưa khóa | Tự khóa cửa, cảnh báo |
| [ESP32] Lab nóng / mát | > 30°C / < 29°C | Bật / tắt relay quạt (chênh 1°C để relay không bật tắt liên tục) |
| [ESP32] Chuyển động | PIR phát hiện | Bật relay đèn 30 giây |
| [ESP32] Gas | MQ-2 vượt ngưỡng | Bật quạt, cảnh báo đỏ |

### Kịch bản (`automation/scenes.json`)

| Kịch bản | Hành động |
|---|---|
| 🏠 **Về nhà** | Chế độ *Ở nhà*, mở khóa, bật đèn phòng khách, mở rèm, bật điều hòa 26°C |
| 🚪 **Ra khỏi nhà** | Tắt mọi đèn/quạt/điều hòa/TV, đóng rèm, khóa cửa, sau đó chuyển sang *Vắng nhà* |
| 🌙 **Đi ngủ** | Chế độ *Ban đêm*, chỉ để đèn ngủ 10%, điều hòa phòng ngủ 27°C, đóng rèm, khóa cửa |
| ☀️ **Buổi sáng** | Chế độ *Ở nhà*, mở rèm, bật đèn phòng ngủ, tắt điều hòa |
| 🎬 **Xem phim** | Đèn phòng khách 15%, đóng rèm, bật TV, điều hòa 25°C |

Bật/tắt luật trên dashboard được lưu thẳng vào `rules.json`. Nếu sửa file bằng tay thì cần khởi động lại engine.

> Chế độ Demo dùng **bản sao** các luật và kịch bản này, nằm trong `dashboard/demo.js`.
> Sửa `rules.json` thì nhớ sửa cả ở đó.

---

## 7. ESP32 thật

### Linh kiện & đấu dây

| Linh kiện | Chân ESP32 | Ghi chú |
|---|---|---|
| DHT22 (DATA) | GPIO 4 | Cần trở kéo lên 10k nếu dùng cảm biến trần (không có module) |
| Relay kênh 1 — đèn | GPIO 26 | Đa số module kích ở mức thấp (`RELAY_ACTIVE_LOW true`) |
| Relay kênh 2 — quạt | GPIO 27 | |
| PIR HC-SR501 (OUT) | GPIO 14 | Vặn biến trở thời gian giữ về mức nhỏ nhất |
| Công tắc từ (reed) | GPIO 13 ↔ GND | Dùng `INPUT_PULLUP` |
| MQ-2 (AO) | GPIO 34 | **Bắt buộc có cầu phân áp**: MQ-2 nuôi 5V nhưng ADC của ESP32 chỉ chịu tối đa 3,3V |
| Nút nhấn | GPIO 0 (nút BOOT có sẵn) | Bật/tắt đèn tại chỗ, trạng thái tự đồng bộ lên dashboard |

### Nạp code

1. Arduino IDE: cài board **esp32** (Espressif) và các thư viện **PubSubClient**, **DHT sensor library**
   (kèm *Adafruit Unified Sensor*), **ArduinoJson** v7.
2. Trong `esp32/esp32_smarthome_node/`, **copy `secrets.example.h` thành `secrets.h`** rồi điền:
   - `WIFI_SSID`, `WIFI_PASS`
   - `MQTT_HOST`: IP LAN của máy chạy Mosquitto (xem bằng `ipconfig` / `ip a`)

   File `secrets.h` đã nằm trong `.gitignore`, nên mật khẩu WiFi của mỗi người không bị đưa lên GitHub.
   Nếu thiếu file này, Arduino IDE sẽ báo lỗi `secrets.h: No such file or directory`.
3. Mở `esp32_smarthome_node.ino`, đặt `#define USE_... 0` cho linh kiện bạn không có.
4. Nạp code và mở Serial Monitor ở 115200. Phòng **Lab (ESP32)** sẽ tự xuất hiện trên dashboard.

> ⚠️ **An toàn:** relay đóng cắt điện 220V rất nguy hiểm. Khi demo nên dùng đèn LED hoặc quạt 5–12V,
> hoặc chỉ cần nghe tiếng relay "tách". Ngưỡng ppm của MQ-2 chỉ là ước lượng thô từ ADC, chưa hiệu chuẩn.
>
> PubSubClient chỉ publish được QoS 0 (subscribe thì được QoS 1). LWT vẫn là QoS 1 + retain.

---

## 8. Tham chiếu lệnh

### Tham số các script

| Script | Tham số hay dùng |
|---|---|
| `devices/home_sim.py` | `--rooms living,kitchen` chỉ chạy vài phòng · `--qos 0/1/2` · `--keepalive 10` · `--interval 5` chu kỳ gửi số liệu cảm biến · `--revive 20` · `--no-random` tắt chuyển động ngẫu nhiên · `--quiet` / `--verbose` |
| `automation/automation.py` | `--rules file.json` · `--scenes file.json` · `--client-id` |
| `logger/logger.py` | `--report` in báo cáo · `--export file.csv --table messages\|climate\|energy\|commands` · `--db` |
| Chung | `--host` · `--port` · `--prefix` (mặc định `home`) · `--username` / `--password` (hoặc biến môi trường `MQTT_HOST`, `MQTT_PORT`, `MQTT_USER`, `MQTT_PASS`) |
| Dashboard (URL) | `?broker=ws://192.168.1.10:9001` · `&prefix=home` · `&demo=1` |

### Thử bằng `mosquitto_pub` / `mosquitto_sub`

```bash
mosquitto_sub -h localhost -t 'home/#' -v                         # xem mọi message
mosquitto_sub -h localhost -t 'home/+/+/set' -v                   # chỉ xem lệnh: ai điều khiển gì
mosquitto_pub -h localhost -t 'home/living/light/set' -q 1 -m '{"on":true,"brightness":30}'
mosquitto_pub -h localhost -t 'home/_auto/scene/set'  -q 1 -m '{"scene":"sleep"}'
mosquitto_pub -h localhost -t 'home/kitchen/gas/set'  -q 1 -m '{"action":"trigger"}'
mosquitto_pub -h localhost -t 'home/living/fan/status' -r -n      # xóa retained → thẻ biến mất
```

### Dùng broker công cộng

Đổi prefix để không trùng với nhóm khác:

```bash
python devices/home_sim.py      --host test.mosquitto.org --prefix nhom7_home
python automation/automation.py --host test.mosquitto.org --prefix nhom7_home
# Dashboard: broker = wss://test.mosquitto.org:8081 , prefix = nhom7_home
```

---

## 9. Kịch bản thuyết trình (~10 phút)

| # | Nội dung | Thao tác |
|---|---|---|
| 1 | **Kiến trúc** (1') | Sơ đồ và bảng topic. Nhấn mạnh: các thành phần không biết nhau, chỉ biết broker. |
| 2 | **Discovery & retained** (1') | Chạy `home_sim.py`: các phòng tự xuất hiện. F5 dashboard: trạng thái hiện ngay (Retain ✓). |
| 3 | **Điều khiển 2 chiều** (1.5') | Bật đèn, kéo độ sáng, chỉnh điều hòa; chỉ trên Message log `…/set` (vàng) rồi đến `…/state`. Bấm nút BOOT trên ESP32: dashboard cập nhật theo. |
| 4 | **Automation** (2') | Bấm **Nắng nóng** ở phòng khách: điều hòa tự bật, nhiệt độ hạ dần trên biểu đồ. Bấm **Rò rỉ gas**: cảnh báo đỏ, bếp ngắt, quạt hút bật. Với ESP32: nắm tay vào DHT22, relay quạt đóng. |
| 5 | **Kịch bản & chế độ** (1.5') | **Ra khỏi nhà**: mọi thứ tắt, cửa khóa, chuyển *Vắng nhà*. Bấm **Mở cửa**: báo động xâm nhập, toàn bộ đèn bật. |
| 6 | **LWT** (1.5') | **Mất điện** một thiết bị: *Offline · LWT* rồi tự online lại. Rút điện ESP32: cả phòng Lab offline. Ctrl+C automation: dashboard thấy engine offline. |
| 7 | **Persistent session** (1') | Tắt logger 30 giây, bật lại: `session_present=True` và `↺ nhận bù`. Kết thúc bằng `logger.py --report`. |

**Mẹo:** chạy `home_sim.py --no-random` để chuyển động ngẫu nhiên không làm rối demo, và luôn mở sẵn
một tab `?demo=1` để dự phòng.

---

## 10. Xử lý sự cố

| Hiện tượng | Nguyên nhân & cách xử lý |
|---|---|
| Dashboard báo *Mất kết nối broker* | Broker chưa chạy hoặc chưa mở cổng 9001 (WebSocket). Kiểm tra `docker compose ps`, hoặc chạy `mosquitto -c broker/mosquitto.conf -v`. |
| *Không tải được MQTT.js* | Máy không có Internet nên không tải được thư viện từ CDN. Tải `mqtt.min.js` và `chart.umd.min.js` về thư mục `dashboard/` rồi sửa 2 thẻ `<script>`. |
| ESP32 báo `lỗi rc=-2` | Không tới được broker: sai `MQTT_HOST`, ESP32 và máy không cùng mạng, hoặc firewall chặn cổng 1883 (Windows: cho phép `mosquitto.exe` qua Windows Defender Firewall). |
| ESP32 báo `lỗi rc=5` | Broker đang bật xác thực: điền `MQTT_USER` / `MQTT_PASS`. |
| Kịch bản / chế độ bị mờ | Automation engine chưa chạy: `python automation/automation.py`. |
| Thiết bị cũ không biến mất | Retained `status` vẫn còn trên broker. Xóa bằng `mosquitto_pub -t 'home/<phòng>/<id>/status' -r -n`. |
| Logger không "nhận bù" | Sensor phải publish QoS ≥ 1 (mặc định `--qos 1`), logger phải giữ nguyên `--client-id`, và broker không được khởi động lại trong lúc logger tắt (trừ khi bật persistence). |
| `ModuleNotFoundError: paho` | Chạy `pip install -r requirements.txt`. |
| Lỗi tiếng Việt trên terminal Windows | Chạy `chcp 65001` hoặc đặt biến môi trường `PYTHONIOENCODING=utf-8`. |

---

## 11. Hướng mở rộng

- **Bảo mật:** bật xác thực + ACL (`broker/acl.conf` có sẵn quyền cho từng loại client); bật TLS (8883 / wss 8443) bằng chứng chỉ tự ký.
- **Dữ liệu:** nạp `logger/smarthome.db` (các view `climate`, `energy`, `commands`) vào Grafana; hoặc thay SQLite bằng InfluxDB.
- **MQTT v5:** message expiry cho lệnh; response topic để thiết bị xác nhận lệnh; shared subscription `$share/loggers/home/#` để chạy nhiều logger song song.
- **Tích hợp:** chuyển `status` sang định dạng MQTT Discovery để Home Assistant tự nhận thiết bị.
- **Thông báo:** gửi cảnh báo `critical` qua Telegram bot hoặc email.
