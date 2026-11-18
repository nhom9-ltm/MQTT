# Mã hóa TLS cho MQTT

Mặc định mọi gói MQTT đi trên mạng ở dạng **chữ thường**: ai bắt được gói tin (cùng WiFi, Wireshark...) đều đọc được
topic, trạng thái thiết bị, mật khẩu MQTT và cả **mã PIN tắt an ninh** (xem [AN_NINH.md](AN_NINH.md)). Phần này bật
**TLS** để:

- **Mã hóa** toàn bộ kết nối giữa client và broker: người nghe lén chỉ thấy dữ liệu ngẫu nhiên.
- **Xác thực broker**: client kiểm tra chứng chỉ của broker do **CA của nhóm** ký và đúng tên/IP đang kết nối,
  nên kẻ gian không dựng được broker giả để nhận lệnh hoặc lấy PIN (chống tấn công xen giữa, MITM).

Không thay đổi hành vi mặc định: không bật TLS thì mọi thứ chạy như cũ.

| Cổng | Giao thức | Mã hóa | Ai dùng |
|---|---|:-:|---|
| 1883 | MQTT/TCP | ✘ | như cũ; giữ lại để so sánh khi demo |
| 9001 | MQTT/WebSocket (`ws://`) | ✘ | dashboard như cũ |
| **8883** | **MQTT/TLS** | ✔ | script Python (`--tls`), ESP32 (`MQTT_USE_TLS 1`) |
| **8443** | **MQTT/WebSocket/TLS (`wss://`)** | ✔ | dashboard (`?tls=1`) |

8883 là cổng chuẩn (IANA) của MQTT over TLS.

## File

| File | Vai trò |
|---|---|
| `infra/broker/gen_certs.py` | Tạo CA của nhóm + chứng chỉ broker (SAN: `localhost`, `127.0.0.1`, tên máy, các IP LAN); sinh `ca_cert.h` cho ESP32; `--install` cài CA cho Chrome/Edge |
| `infra/broker/mosquitto.tls.conf` | Broker chạy trực tiếp: 4 listener ở bảng trên |
| `infra/broker/mosquitto.tls.docker.conf`, `docker-compose.tls.yml` | Như trên nhưng chạy bằng Docker |
| `backend/common/tls.py`, `backend/common/cli.py`, `backend/common/mqtt_client.py`, `backend/common/mqtt_publish.py` | Tham số `--tls` / `--cafile`, biến `MQTT_TLS` / `MQTT_CAFILE`; gọi `tls_set()` của paho |
| `frontend/js/session.js`, `frontend/js/app.js`, `frontend/js/admin.js` | `?tls=1` → kết nối `wss://<máy>:8443`, pill hiện "Đã kết nối · TLS" |
| `firmware/esp32/.../esp32_smarthome_node.ino`, `secrets.example.h` | `WiFiClientSecure` + `setCACert()` khi `MQTT_USE_TLS 1` |
| `backend/tests/test_tls.py` | 12 ca: tham số, chứng chỉ, kết nối thật qua broker TLS, từ chối CA lạ / sai tên máy |

Sinh ra khi chạy (đã `.gitignore`, **mỗi máy tự tạo, không đưa lên GitHub**): `infra/broker/certs/`
(`ca.crt`, `ca.key`, `server.crt`, `server.key`) và `firmware/esp32/esp32_smarthome_node/ca_cert.h`.

## Cách chạy (không Docker)

**1. Tạo chứng chỉ** (một lần, trong thư mục gốc repo):

```powershell
pip install -r backend/requirements-extra.txt        # cần gói cryptography
python infra/broker/gen_certs.py --install
```

`--install` thêm CA vào kho tin cậy của tài khoản Windows (Windows hỏi xác nhận → **Yes**) để Chrome/Edge chấp nhận
`wss://`. Sau đó **đóng hẳn và mở lại trình duyệt**. Script in danh sách tên/IP hợp lệ; client phải kết nối bằng
một trong các tên/IP đó.

**2. Broker** — thay lệnh broker trong [CACH_CHAY.md](../CACH_CHAY.md) bằng:

```powershell
& "C:\Program Files\mosquitto\mosquitto.exe" -c infra/broker/mosquitto.tls.conf -v
```

Thấy thêm `Opening ipv4 listen socket on port 8883` và `... port 8443` là được.

**3. Các script Python** — thêm `--tls` (tự dùng cổng 8883):

```powershell
python backend/run_simulator.py --tls
python backend/run_automation.py --tls
python backend/run_logger.py --tls
python backend/run_notifier.py --tls
```

Dòng log đổi thành `Đã kết nối localhost:8883 (TLS) — ...`. Hoặc đặt biến môi trường một lần cho cả terminal:
`$env:MQTT_TLS="1"`. API (`run_api.py`) chỉ đọc biến môi trường: `$env:MQTT_TLS="1"; python backend/run_api.py`.

**4. Dashboard** — mở <http://localhost:8080/?tls=1>. Pill trên thanh trên hiện **Đã kết nối · TLS**. Lựa chọn
được nhớ trong trình duyệt (cả trang quản trị); mở `?tls=0` để quay lại `ws://`.

### Máy khác / ESP32 kết nối qua IP LAN

Chứng chỉ phải chứa đúng IP mà client dùng. Script tự thêm các IP hiện có của máy; nếu IP đổi (đổi WiFi) hoặc
muốn thêm tên miền thì cấp lại (CA giữ nguyên, các máy đã cài CA không phải cài lại):

```powershell
python infra/broker/gen_certs.py --host 192.168.1.10
```

rồi khởi động lại broker. Máy khác cần file `infra/broker/certs/ca.crt` (copy sang, **không** copy `ca.key`):

```powershell
python backend/run_simulator.py --host 192.168.1.10 --tls --cafile D:\ca.crt
# dashboard: cài ca.crt (nháy đúp → Install Certificate → Current User → Trusted Root Certification Authorities)
#            rồi mở http://192.168.1.10:8080/?tls=1
```

### ESP32

1. Chạy `gen_certs.py --host <IP máy chạy broker>`: file `ca_cert.h` được tạo cạnh `esp32_smarthome_node.ino`.
2. Trong `secrets.h`: `MQTT_PORT = 8883` và `#define MQTT_USE_TLS 1` (xem `secrets.example.h`).
3. Nạp lại firmware. ESP32 chờ có giờ từ NTP rồi mới bắt tay TLS (chứng chỉ có hạn dùng).

`secrets.h` cũ không có `MQTT_USE_TLS` vẫn biên dịch được (mặc định tắt).

## Cách chạy bằng Docker

```powershell
python infra/broker/gen_certs.py --install
docker compose -f docker-compose.yml -f docker-compose.tls.yml up -d --force-recreate mosquitto
# chạy hết trong Docker (automation/simulator kết nối "mosquitto:8883" qua TLS):
docker compose -f docker-compose.yml -f docker-compose.tls.yml --profile full up -d
```

Quay lại không mã hóa: `docker compose up -d --force-recreate mosquitto`.

## Demo trên lớp: Wireshark

Cần Wireshark có **Npcap** (cài kèm, tick *Support loopback traffic*). Chọn card **Adapter for loopback traffic
capture** (broker trên cùng máy), filter `tcp.port in {1883 9001 8883 8443}`.

1. Chạy broker TLS, **không** bật TLS ở simulator/automation và mở dashboard thường (`?tls=0`).
   Trên Wireshark các gói `MQTT` ở cổng 1883 hiện rõ topic và payload, ví dụ `home/living/climate/state {"temp": 27.1, ...}`.
2. Bấm **Vắng nhà**, đợi canh gác rồi nhập PIN để tắt. Filter `mqtt.topic contains "security/set"`: gói `PUBLISH`
   broker chuyển cho automation chứa `"pin":"1234"` — **ai cùng mạng cũng đọc được PIN**.
3. Tắt simulator và automation, chạy lại với `--tls`; mở dashboard `?tls=1`. Lặp lại bước 2: các gói ở cổng
   8883 / 8443 chỉ còn `TLSv1.3 Application Data`, không đọc được topic, payload hay PIN. Đầu mỗi kết nối có
   `Client Hello` / `Server Hello` (bắt tay TLS; `Client Hello` vẫn lộ tên máy chủ qua SNI, nội dung thì không).
4. Client từ chối broker không khớp chứng chỉ: kết nối bằng địa chỉ không có trong chứng chỉ (vẫn là máy này)
   ```powershell
   & "C:\Program Files\mosquitto\mosquitto_pub.exe" -h 127.0.0.2 -p 8883 --cafile infra/broker/certs/ca.crt -t test -m x
   ```
   → bị từ chối. Đây chính là điều chặn được broker giả (MITM).

Thử nhanh bằng dòng lệnh (không cần code):

```powershell
& "C:\Program Files\mosquitto\mosquitto_sub.exe" -h localhost -p 8883 --cafile infra/broker/certs/ca.crt -t "home/#" -v
& "C:\Program Files\mosquitto\mosquitto_pub.exe" -h localhost -p 8883 -t test -m x       # không có CA → bị từ chối
```

## Lưu ý

- **`ca.key` là chìa khóa của cả hệ thống**: ai có nó tạo được broker giả mà mọi client tin. Không gửi, không commit.
- Chứng chỉ broker hết hạn sau 397 ngày (giới hạn của trình duyệt); chạy lại `gen_certs.py` để cấp mới. CA dùng 10 năm.
- Đây là CA tự ký cho mạng nội bộ. Đưa ra Internet với tên miền thật thì nên dùng chứng chỉ Let's Encrypt.
- TLS chỉ mã hóa đường truyền và xác thực **broker**. Xác thực **client** vẫn dùng tài khoản + ACL
  ([MO_RONG.md mục 2](MO_RONG.md#2-xác-thực--acl)); kết hợp cả hai thì thêm `password_file` / `acl_file` vào
  `mosquitto.tls.conf`. Muốn chặn hẳn kết nối không mã hóa thì xóa listener 1883 và 9001.
- Lỗi hay gặp:

| Hiện tượng | Nguyên nhân / cách xử lý |
|---|---|
| Dashboard `?tls=1` báo *Mất kết nối broker TLS* | Trình duyệt chưa tin CA (chạy `gen_certs.py --install`, mở lại trình duyệt) hoặc broker chưa chạy `mosquitto.tls.conf` |
| `certificate verify failed: IP address mismatch` / `Hostname mismatch` | Kết nối bằng IP/tên không có trong chứng chỉ → `gen_certs.py --host <IP>`, khởi động lại broker |
| `certificate verify failed: unable to get local issuer` | `--cafile` không phải CA đã ký chứng chỉ broker (vừa tạo CA mới?) — dùng `infra/broker/certs/ca.crt` hiện tại |
| `Không thấy file CA` | Chưa chạy `python infra/broker/gen_certs.py` |
| Broker báo `Unable to load server certificate` | Chạy broker không đứng ở thư mục gốc repo (đường dẫn chứng chỉ là tương đối) |

## Kiểm thử

```powershell
python -m unittest backend.tests.test_tls -v
```
