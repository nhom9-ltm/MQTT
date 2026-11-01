# Cách chạy dự án

Có 3 cách, chọn một:

| Cách | Khi nào dùng |
|---|---|
| [A. Chạy trực tiếp (không Docker)](#a-chạy-trực-tiếp-không-docker) | Máy Windows bình thường — **cách nhóm hay dùng** |
| [B. Chạy bằng Docker](#b-chạy-bằng-docker) | Máy đã có Docker Desktop |
| [C. Chế độ Demo](#c-chế-độ-demo-không-cần-cài-gì) | Chỉ cần xem giao diện, hoặc dự phòng khi thuyết trình |

---

## A. Chạy trực tiếp (không Docker)

### Cài đặt (làm một lần)

1. **Python 3.9+**: <https://www.python.org/downloads/> — nhớ tick **Add Python to PATH**.
2. **Thư viện Python** (trong thư mục repo):

   ```powershell
   pip install -r BE/requirements.txt
   ```

3. **Mosquitto** (broker MQTT):

   ```powershell
   winget install EclipseFoundation.Mosquitto
   ```

4. **Tắt service Mosquitto mặc định.** Bộ cài tự tạo service `mosquitto` chạy nền, chiếm cổng 1883 nhưng
   không mở WebSocket nên dashboard không kết nối được. Mở PowerShell bằng **Run as Administrator**:

   ```powershell
   Stop-Service mosquitto
   Set-Service mosquitto -StartupType Manual
   ```

### Chạy

Mở **5 cửa sổ terminal**, tất cả đứng ở **thư mục gốc repo**, mỗi cửa sổ chạy một lệnh:

```powershell
# 1 — Broker (MQTT :1883, WebSocket :9001)
& "C:\Program Files\mosquitto\mosquitto.exe" -c BE/broker/mosquitto.local.conf -v

# 2 — Web server cho dashboard
python -m http.server 8080 --directory FE

# 3 — 20 thiết bị giả lập
python BE/run_simulator.py

# 4 — Automation engine (luật & kịch bản)
python BE/run_automation.py

# 5 — (tùy chọn) Logger ghi lịch sử vào BE/data/smarthome.db
python BE/run_logger.py
```

Thứ tự: chạy **broker trước**, các lệnh còn lại thứ tự nào cũng được.

Mở trình duyệt: **<http://localhost:8080>** → dashboard tự kết nối broker và hiện 20 thiết bị.

Tắt: bấm `Ctrl+C` ở từng terminal.

### Kiểm tra đã chạy đúng

| Terminal | Dòng cần thấy |
|---|---|
| Broker | `Opening ipv4 listen socket on port 1883` và `... port 9001` |
| `run_simulator.py` | `Đã khởi động 20 thiết bị → localhost:1883` |
| `run_automation.py` | `Đã kết nối localhost:1883 — 11 luật, 5 kịch bản` |
| `run_logger.py` | `Đã kết nối. session_present=...` |

Thử gửi lệnh bật đèn phòng khách:

```powershell
& "C:\Program Files\mosquitto\mosquitto_pub.exe" -t home/living/light/set -q 1 -m '{\"on\":true}'
```

Terminal `run_simulator.py` in `[living/light] ← lệnh ...` và thẻ đèn trên dashboard bật sáng.

---

## B. Chạy bằng Docker

```powershell
pip install -r BE/requirements.txt
docker compose up -d                 # broker + dashboard http://localhost:8080
python BE/run_simulator.py           # terminal 1
python BE/run_automation.py      # terminal 2
python BE/run_logger.py              # terminal 3 (tùy chọn)
```

Hoặc chạy hết trong Docker: `docker compose --profile full up -d`, xem log bằng
`docker compose logs -f automation`.

---

## C. Chế độ Demo (không cần cài gì)

**Link công khai:** <https://nhom9-ltm.github.io/MQTT/> — mở là tự chạy Demo, mỗi người một ngôi nhà
giả lập riêng. Link tự cập nhật mỗi khi có thay đổi trong `FE/` được push lên `main`.

Trên máy mình: mở file `FE/index.html` bằng trình duyệt rồi bấm **Demo** (hoặc thêm `?demo=1` vào URL). Broker,
20 thiết bị và automation đều được giả lập ngay trong trình duyệt. Cần Internet để tải thư viện MQTT.js
và Chart.js.

---

## Chạy chung trên nhiều máy (cùng WiFi)

Một máy chạy broker, các máy khác trỏ vào IP của máy đó:

1. Máy chạy broker: xem IP bằng `ipconfig` (ví dụ `192.168.1.10`). Lần đầu Windows hỏi tường lửa → cho
   phép `mosquitto.exe` trên mạng **Private**.
2. Máy khác:

   ```powershell
   python BE/run_simulator.py --host 192.168.1.10
   python BE/run_automation.py --host 192.168.1.10
   # dashboard: http://localhost:8080/?broker=ws://192.168.1.10:9001
   ```

ESP32 thật: điền IP này vào `MQTT_HOST` trong `esp32/esp32_smarthome_node/secrets.h` (xem
[README § 7](README.md#7-esp32-thật)).

---

## Lỗi hay gặp

| Hiện tượng | Cách xử lý |
|---|---|
| Broker báo `Only one usage of each socket address` / `Address already in use` | Service `mosquitto` vẫn chạy — làm lại bước 4 phần cài đặt. |
| Cổng 8080 bị chiếm (máy có Apache, XAMPP, PostgreSQL PEM…) | Đổi cổng: `python -m http.server 8090 --directory FE`, mở `http://localhost:8090`. |
| Dashboard báo *Mất kết nối broker* | Broker chưa chạy, hoặc đang chạy bằng service mặc định (không có cổng 9001). |
| Kịch bản / chế độ trên dashboard bị mờ | Chưa chạy `run_automation.py`. |
| Tiếng Việt trên terminal bị lỗi / `UnicodeEncodeError` | Chạy `chcp 65001` hoặc `$env:PYTHONUTF8=1` trước. |
| `ModuleNotFoundError: paho` | `pip install -r BE/requirements.txt` |

Các lỗi khác: [README § 10](README.md#10-xử-lý-sự-cố). Tham số các script: [README § 8](README.md#8-tham-chiếu-lệnh).
