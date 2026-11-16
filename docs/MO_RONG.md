# Phần mở rộng

Ba tính năng bổ sung, **không thay đổi hành vi mặc định** của dự án (broker vẫn mở, dashboard và
các script cũ chạy như trước). Làm theo thứ tự:

| # | Tính năng | File mới | Chạy |
|:-:|---|---|---|
| 1 | [Thông báo Telegram / Email](#1-thông-báo-telegram--email) | `backend/controllers/notifier_controller.py`, `backend/services/notification_service.py`, `backend/services/notify_channels.py` | `python backend/run_notifier.py` |
| 2 | [Xác thực + ACL](#2-xác-thực--acl) | `infra/broker/mosquitto.secure.conf`, `docker-compose.secure.yml`, `infra/broker/setup_auth.py`, `infra/broker/test_acl.py`, `frontend/js/auth.js` | xem bên dưới |
| 3 | [Lịch sử + biểu đồ](#3-lịch-sử--biểu-đồ) | `backend/controllers/api_controller.py`, `backend/services/history_service.py`, `backend/repositories/history_repository.py`, `backend/database/seed_history.py`, `frontend/index.html` (trang `#/history`), `frontend/js/history.js`, `frontend/css/history.css` | `python backend/run_api.py` |

Thay đổi nhỏ ở file cũ (chỉ thêm, không sửa): `infra/broker/acl.conf` (+ user `notifier`), `.gitignore`
(+ `infra/broker/credentials.env`), `frontend/index.html` (+ nút **Lịch sử**, + thẻ `<script src="js/auth.js">`).

---

## 1. Thông báo Telegram / Email

`backend/run_notifier.py` subscribe `home/_auto/notify/event` (do automation phát) và gửi các sự kiện có
`level = critical` ra điện thoại / hộp thư. Kênh nào thiếu cấu hình thì tự tắt; có thể bật cả hai.

### Telegram
1. Chat với `@BotFather` → `/newbot` → lấy **token**.
2. Nhắn một tin bất kỳ cho bot vừa tạo.
3. Mở `https://api.telegram.org/bot<TOKEN>/getUpdates`, lấy `message.chat.id`.

### Email (Gmail)
1. Bật xác minh 2 bước cho tài khoản dùng để gửi.
2. Tạo **App Password** tại <https://myaccount.google.com/apppasswords> (mật khẩu Gmail thường không dùng được).

### Chạy
```powershell
$env:PYTHONUTF8=1
$env:TELEGRAM_TOKEN="123456:ABC..."; $env:TELEGRAM_CHAT="987654321"
$env:SMTP_USER="gui@gmail.com"; $env:SMTP_PASS="app-password-16-ky-tu"; $env:MAIL_TO="a@x.com,b@y.com"

python backend/run_notifier.py --test      # gửi thử 1 tin qua các kênh đã bật rồi thoát
python backend/run_notifier.py             # chạy thật
```
Bấm **Rò rỉ gas** trên dashboard → vài giây sau điện thoại / hộp thư nhận cảnh báo.

| Tham số / biến | Ý nghĩa |
|---|---|
| `--levels critical,warning` | Các level cần gửi (mặc định `critical`) |
| `--cooldown 60` | Giây tối thiểu giữa 2 thông báo **cùng nguồn** (chống spam khi cảm biến báo liên tục) |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_MODE` | Mặc định `smtp.gmail.com` / 465 / `ssl`. Outlook: `smtp.office365.com`, `587`, `starttls` |
| `--client-id` | Mặc định `notifier-01`, dùng persistent session nên cảnh báo phát lúc notifier tắt sẽ được gửi bù |

Lưu ý: token và mật khẩu chỉ đọc từ biến môi trường, **đừng ghi vào code hay commit**. Mail lần đầu có thể
vào *Spam*. Một kênh gửi lỗi (mất mạng, sai mật khẩu) chỉ in log, không làm sập kênh kia hay notifier.

---

## 2. Xác thực + ACL

Mặc định broker cho phép anonymous. Chế độ bảo mật bắt buộc đăng nhập và phân quyền theo
`infra/broker/acl.conf`:

| User | Được đọc | Được ghi |
|---|---|---|
| `dashboard` | `home/#`, `$SYS/#` | **chỉ** `…/set`, `home/_auto/+/set`, `home/_dashboard/#` |
| `automation` | `…/status`, `…/state` | `…/set`, `home/_auto/#` |
| `logger` | `home/#` | không |
| `simulator` | `…/set` | `…/status`, `…/state` |
| `esp32-01` | `home/lab/+/set` | `home/lab/+/status`, `…/state` |
| `notifier` | `home/_auto/notify/event` | không |

Ý nghĩa: dashboard **không thể giả mạo `state` / `status`** của thiết bị, chỉ gửi được lệnh.

### Bật
```powershell
python infra/broker/setup_auth.py              # tạo infra/broker/passwd + infra/broker/credentials.env (cần Docker)
docker compose --env-file infra/broker/credentials.env -f docker-compose.yml -f docker-compose.secure.yml up -d --force-recreate mosquitto
```
Mật khẩu ngẫu nhiên được in ra và lưu trong `infra/broker/credentials.env` (đã `.gitignore`).

Mỗi thành phần phải đăng nhập:
```powershell
$env:PYTHONUTF8=1
python backend/run_simulator.py       --username simulator  --password <PASS_SIMULATOR>
python backend/run_automation.py  --username automation --password <PASS_AUTOMATION>
python backend/run_logger.py          --username logger     --password <PASS_LOGGER>
python backend/run_notifier.py      --username notifier   --password <PASS_NOTIFIER>
```
(hoặc biến môi trường `MQTT_USER` / `MQTT_PASS`).

- **Dashboard:** mở `http://localhost:8080/?user=dashboard&pass=<PASS_DASHBOARD>`. `frontend/js/auth.js` giữ tài khoản
  trong `sessionStorage` (đóng tab là mất) và xóa mật khẩu khỏi thanh địa chỉ. Chế độ Demo không bị ảnh hưởng.
- **ESP32:** điền `MQTT_USER = "esp32-01"` và `MQTT_PASS` trong `secrets.h`.
- **Docker profile `full`:** `docker-compose.secure.yml` đã truyền tài khoản cho `automation` và `simulator`;
  nhớ thêm `--env-file infra/broker/credentials.env`.

### Kiểm tra tự động
```powershell
python infra/broker/test_acl.py
```
Chạy 10 ca: không / sai mật khẩu bị từ chối; dashboard gửi `…/set` được nhưng giả mạo `…/state`, `…/status`
bị chặn; simulator ghi `state` được nhưng không ra lệnh được; logger chỉ đọc.

### Demo trên lớp
```powershell
# Không tài khoản → bị từ chối
docker exec mqtt-broker mosquitto_pub -t home/living/light/set -m "x"
# Dashboard giả mạo trạng thái đèn → broker lặng lẽ bỏ qua, đèn KHÔNG đổi
docker exec mqtt-broker mosquitto_pub -u dashboard -P <PASS_DASHBOARD> -t home/living/light/state -m '{\"on\":true}'
# Cũng user đó gửi lệnh → đèn bật bình thường
docker exec mqtt-broker mosquitto_pub -u dashboard -P <PASS_DASHBOARD> -t home/living/light/set -q 1 -m '{\"on\":true}'
```
Mosquitto **không báo lỗi cho client** khi ACL chặn publish (MQTT 3.1.1); kết quả chỉ là "không có tác dụng".
Mở `docker logs -f mqtt-broker` để khán giả thấy các lần `not authorised`.

### Quay lại chế độ mở
```powershell
docker compose up -d --force-recreate mosquitto
```
Rồi chạy lại các script không cần mật khẩu.

Ghi chú: nếu có tab dashboard cũ đang mở lúc bật bảo mật, nó sẽ liên tục báo `not authorised` trong log broker
cho tới khi bạn mở lại bằng URL có `?user=…&pass=…`.

---

## 3. Lịch sử + biểu đồ

```
run_logger.py ──ghi──▶ backend/data/smarthome.db ──(đọc, chỉ đọc)──▶ backend/run_api.py :8011 ──JSON──▶ frontend/index.html#/history
```

```powershell
pip install -r backend/requirements-extra.txt                 # fastapi + uvicorn
python backend/run_api.py                       # từ thư mục gốc repo
```
Bấm mục **Lịch sử** ở sidebar của dashboard (hoặc mở `http://localhost:8080/#/history`; đường dẫn cũ `history.html` tự chuyển hướng tới đây). Sidebar và thanh trên được giữ nguyên, chỉ phần nội dung đổi. Trang hiển thị:
nhiệt độ / độ ẩm theo phòng, điện năng theo ngày và theo thiết bị, thống kê ai ra lệnh, thiết bị bị
điều khiển nhiều nhất, và các cảnh báo gần đây. Chọn khoảng 1 giờ / 24 giờ / 7 ngày ở góc phải.

| Endpoint | Nội dung |
|---|---|
| `GET /api/summary?hours=24` | Tổng bản ghi, số lệnh, số cảnh báo critical, danh sách phòng |
| `GET /api/climate?room=living&hours=24` | Nhiệt độ / độ ẩm trung bình theo nhóm thời gian (~120 điểm) |
| `GET /api/energy?days=7` | kWh ước tính theo ngày và theo thiết bị |
| `GET /api/commands?hours=24` | Lệnh theo nguồn (`from`) và theo thiết bị |
| `GET /api/alerts?limit=20` | Thông báo gần nhất của automation |

Tài liệu tương tác của FastAPI: `http://localhost:8011/docs`.

### Khi chưa có đủ dữ liệu
DB mới chạy thì biểu đồ còn trống. Sinh 7 ngày dữ liệu mẫu **vào file riêng** (không đụng DB thật):
```powershell
python backend/database/seed_history.py
$env:HISTORY_DB="backend/data/demo_history.db"; python backend/run_api.py
```

### Lưu ý
- Điện năng là **ước tính**: lấy công suất trung bình từng giờ của mỗi thiết bị rồi cộng lại, không phải số đo từ đồng hồ.
- Trang lịch sử cần API chạy, nên **không** có trên bản GitHub Pages (Demo). Trên Pages, nút Lịch sử sẽ báo lỗi kết nối API.
- API chỉ có `GET`, mở CORS `*`, mở DB `mode=ro`. Nếu đưa ra ngoài Internet cần thêm xác thực riêng.
- Khi chạy với bảo mật bật, logger vẫn ghi DB bình thường; API không đi qua broker nên không cần tài khoản MQTT.
