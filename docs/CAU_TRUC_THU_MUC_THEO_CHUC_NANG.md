# Cấu trúc thư mục theo chức năng: Nhà thông minh qua MQTT

> **Mục đích:** Bản đồ cho biết thư mục/file nào xử lý chức năng nào. Khi cần sửa hoặc tìm hiểu một chức năng, tra
> mục 3 để biết ngay phải mở controller, service, repository, file cấu hình, màn hình frontend và tài liệu nào.
>
> **Thời điểm chụp:** 2026-11-13, nhánh `T-2`, ngay sau khi sắp xếp lại `BE/` → `backend/` và `FE/` → `frontend/`.
> Danh sách lấy từ `git ls-files` (bỏ `__pycache__/`, file `*.db`). Khi repo thêm hoặc xoá file, cần cập nhật lại.
>
> **Quy ước trạng thái:**
> - ✅ **Đã triển khai**: có code chạy được và có màn hình hoặc lệnh dùng thật.
> - 🟡 **Một phần**: có code nhưng còn phụ thuộc giả lập, hoặc có lỗi đã biết.
> - ⬜ **Chỉ có khung**: thư mục rỗng hoặc file chưa được dùng ở đâu.

---

## 1. Tổng quan gốc repo

```
MQTT/
├── backend/          Python: thiết bị giả lập, automation, logger, notifier, API đăng nhập/quản trị/lịch sử
├── frontend/         Web tĩnh (HTML/CSS/JS thuần, không build): đăng nhập, dashboard điều khiển, trang quản trị
├── infra/broker/     Cấu hình broker Mosquitto, ACL, script tạo tài khoản MQTT
├── firmware/esp32/   Code Arduino cho mạch ESP32 thật
├── docs/             Tài liệu: prompt từng màn hình, hướng dẫn nhóm, phần mở rộng, bản cũ (legacy/)
├── .github/workflows/pages.yml   Đưa frontend/ lên GitHub Pages (bản Demo công khai)
├── docker-compose.yml            Broker, PostgreSQL, nginx phục vụ frontend (+ automation/simulator khi --profile full)
├── docker-compose.secure.yml     Ghép thêm khi bật xác thực + ACL cho broker
├── README.md                     Giới thiệu, kiến trúc, topic, kịch bản thuyết trình
└── CACH_CHAY.md                  Hướng dẫn chạy từng bước
```

---

## 2. Cấu trúc theo tầng (nơi đặt từng loại file)

### 2.1 Backend: `backend/`

```
backend/
├── run_api.py            Điểm vào API HTTP (FastAPI, cổng 8001); tự nạp seed khi khởi động
├── run_simulator.py      Điểm vào 20 thiết bị giả lập
├── run_automation.py     Điểm vào automation engine (luật + kịch bản)
├── run_logger.py         Điểm vào logger ghi lịch sử SQLite
├── run_notifier.py       Điểm vào notifier (Telegram / Email)
├── requirements.txt      Thư viện bắt buộc (paho-mqtt)
├── requirements-extra.txt  Thư viện cho API (fastapi, uvicorn, psycopg)
├── controllers/          Tầng vào: nhận HTTP / MQTT / tham số dòng lệnh rồi gọi services
├── services/             Logic nghiệp vụ
├── repositories/         Truy vấn dữ liệu: PostgreSQL (tài khoản, quản trị) và SQLite (lịch sử)
├── database/             schema.sql (tạo bảng) · seed.py (dữ liệu demo) · seed_history.py (lịch sử mẫu)
├── simulator/            Căn nhà + thiết bị giả lập, server Telegram/SMTP giả
├── config/               rules.json, scenes.json: luật & kịch bản automation thực thi
├── common/               Dùng chung: tham số CLI, tạo MQTT client, đường dẫn
├── tests/                Kiểm thử (unittest)
└── data/                 *.db sinh ra khi chạy (không commit)
```

Luồng chuẩn:
- **HTTP:** `run_api.py` → `controllers/*_controller.py` (kiểm phiên/vai trò) → `services/` → `repositories/` → PostgreSQL / SQLite.
- **MQTT:** `run_<tên>.py` → `controllers/<tên>_controller.py` (giữ MQTT client, subscribe) → `services/<tên>_service.py` → publish lại qua broker.

Các tiến trình không gọi trực tiếp nhau, chỉ giao tiếp qua broker.

### 2.2 Frontend: `frontend/`

```
frontend/
├── login.html            Trang đăng nhập (mở đầu tiên)
├── index.html            Dashboard người dùng: ứng dụng một trang, 7 màn hình theo #hash
├── admin.html            Trang quản trị (chỉ vai trò admin)
├── history.html          Chỉ chuyển hướng sang index.html#/history
├── js/
│   ├── session.js        Lưu token, gọi API, chặn trang theo vai trò (nạp trong <head> mọi trang)
│   ├── login.js          Xử lý form đăng nhập, nút hiện/ẩn mật khẩu, chuyển trang theo vai trò
│   ├── admin.js          Trang quản trị — lõi: sidebar, điều hướng #hash, gọi API, kết nối broker dùng chung
│   ├── admin-overview.js Tổng quan (số tài khoản, thiết bị, thông báo) + trang Thông báo
│   ├── admin-devices.js  Thiết bị: thêm/sửa/xóa, lọc theo phòng, trạng thái online từ broker
│   ├── admin-rules.js    Luật tự động: thêm/sửa/xóa/bật-tắt luật
│   ├── admin-users.js    Quản lý người dùng: Tài khoản (tìm, lọc, thêm/sửa/xóa) + Vai trò (admin, user)
│   ├── admin-logins.js   Lịch sử đăng nhập (chỉ xem)
│   ├── nav.js            Sidebar, router #hash, thanh trên
│   ├── app.js            Kết nối MQTT over WebSocket, thẻ thiết bị, chế độ, kịch bản, luật, thông báo, log
│   ├── scene-editor.js   Tạo kịch bản mới ngay trên dashboard
│   ├── history.js        Màn hình Lịch sử: gọi API và vẽ biểu đồ Chart.js
│   └── auth.js           Gắn tài khoản MQTT khi broker bật xác thực
├── mock/demo.js          Chế độ Demo: giả lập broker + 20 thiết bị + automation ngay trong trình duyệt
├── css/                  style.css (biến màu, thẻ, nút) · auth.css (đăng nhập) · admin.css (trang quản trị) · history.css · scene-editor.css
└── layout/               layout.css, sidebar.css (bố cục) · sidebar_wireframe.html (bản vẽ khung, chỉ tham khảo)
```

### 2.3 Hạ tầng: `infra/broker/`

| File | Xử lý vấn đề gì |
|---|---|
| `mosquitto.local.conf` | Broker chạy trực tiếp trên máy (không Docker): cổng 1883 + WebSocket 9001, cho anonymous |
| `mosquitto.conf` | Broker trong Docker (`docker-compose.yml`): thêm persistence |
| `mosquitto.secure.conf`, `acl.conf` | Bật xác thực + phân quyền topic theo tài khoản |
| `setup_auth.py` | Sinh `passwd` + `credentials.env` (không commit) cho chế độ bảo mật |
| `test_acl.py` | Kiểm tra ACL trên broker đang chạy |
| `data/` | Dữ liệu broker khi chạy không Docker (không commit) |

### 2.4 Thiết bị thật: `firmware/esp32/`

`esp32_smarthome_node/esp32_smarthome_node.ino`: ESP32 với 2 relay, DHT22, PIR, công tắc từ, MQ-2, nút nhấn; publish
cùng định dạng topic với thiết bị giả lập. Copy `secrets.example.h` thành `secrets.h` (không commit) để điền WiFi, IP broker.

---

## 3. Bản đồ chức năng → file

### 3.1 Đăng nhập & phiên làm việc ✅

| Tầng | File |
|---|---|
| API | `POST /api/auth/login`, `GET /api/auth/me`, `POST /api/auth/logout`: `backend/controllers/auth_controller.py` |
| Service | `backend/services/auth_service.py`: chỉ nhận email `@gmail.com`, so mật khẩu SHA-256, phiên 8 giờ |
| Repository | `backend/repositories/auth_repository.py`, `backend/repositories/postgres.py` (kết nối) |
| Bảng | `users`, `roles`, `sessions`, `login_history` (`backend/database/schema.sql`) |
| Frontend | `frontend/login.html`, `js/login.js`, `js/session.js`, `css/auth.css` |
| Chuyển trang | `session.js` → `homeOf()`: `user` → `index.html` (broker thật), `admin` → `admin.html`. Mỗi vai trò chỉ vào được trang của mình (mở nhầm trang thì bị đưa về) |
| Cache | Link JS/CSS trong các trang có `?v=<số>`; sửa JS/CSS thì tăng số này để trình duyệt tải bản mới |
| Kiểm thử | `backend/tests/test_auth.py` |

### 3.2 Dữ liệu demo (seed) ✅

| Tầng | File |
|---|---|
| Khai báo | `backend/database/seed.py`: **nơi duy nhất** khai báo tài khoản, phòng, loại thiết bị, thiết bị ban đầu và kịch bản |
| Quy tắc | Kịch bản: luôn cập nhật theo seed. Vai trò: chỉ thêm nếu chưa có. Tài khoản, phòng, thiết bị: chỉ nạp lần đầu (database trống), sau đó admin quản lý; nếu không còn admin hoạt động thì seed khôi phục tài khoản admin. Luật: ban đầu là `backend/config/rules.json`, seed chỉ đồng bộ danh mục vào bảng `automation_rules` |
| Nạp | Tự chạy khi `python backend/run_api.py`; chạy tay: `python backend/database/seed.py` |
| Bảng | `schema.sql` chỉ tạo bảng, không chứa dữ liệu |
| Lịch sử mẫu | `backend/database/seed_history.py` → `backend/data/demo_history.db` (7 ngày dữ liệu giả cho màn hình Lịch sử) |

Tài khoản demo:

| Vai trò | Email | Mật khẩu |
|---|---|---|
| admin | `admmqtt@gmail.com` | `Admin@1` |
| user | `user1@gmail.com` | `User@1` |

### 3.3 Trang quản trị (Admin) ✅

Trang quản trị có sidebar giống trang người dùng; mỗi mục là một trang theo `#hash` (`frontend/js/admin.js`).

| Mục sidebar (`#hash`) | API | Service → Repository | Frontend |
|---|---|---|---|
| Tổng quan `#/home` | `GET /api/admin/overview`, `/api/admin/devices`, `/api/alerts` | `repositories/admin_repository.py` | `js/admin-overview.js` |
| Thiết bị `#/devices` | `GET/POST /api/admin/devices`, `PUT/DELETE /api/admin/devices/{id}`, `GET /api/admin/device-options` | `services/device_service.py` → `repositories/device_repository.py` | `js/admin-devices.js` |
| Luật tự động `#/rules` | `GET/POST /api/admin/rules`, `PUT/DELETE /api/admin/rules/{id}`, `PUT /api/admin/rules/{id}/enabled` | `services/rule_service.py` + `rule_validation.py` → `repositories/rule_repository.py` (rules.json) + `admin_repository.sync_rule_catalog` | `js/admin-rules.js` |
| Thông báo `#/alerts` | `GET /api/alerts` (lịch sử, cần logger) + MQTT `home/_auto/notify/event` (trực tiếp) | `services/history_service.py` | `js/admin-overview.js` |
| Quản lý người dùng / Tài khoản `#/accounts` | `GET /api/admin/users?q=&role=&status=`, `POST /api/admin/users`, `PUT/DELETE /api/admin/users/{id}` | `services/user_service.py` → `repositories/user_repository.py` | `js/admin-users.js` |
| Quản lý người dùng / Vai trò `#/roles` | `GET /api/admin/roles`, `PUT /api/admin/roles/{code}` (đổi tên hiển thị) | `services/user_service.py` (`ROLE_PERMISSIONS`) → `repositories/user_repository.py` | `js/admin-users.js` |
| Lịch sử đăng nhập `#/logins` | `GET /api/admin/login-history` | `repositories/admin_repository.py` | `js/admin-logins.js` |

- Trang: `frontend/admin.html` (các trang có id `admin-<mục>` để không dính CSS của dashboard người dùng), `css/admin.css`, dùng chung `layout/sidebar.css`. Lỗi dữ liệu trả HTTP 400 kèm thông báo tiếng Việt, không tìm thấy trả 404.
- **Thiết bị:** trạng thái Online/Offline/Chưa thấy lấy trực tiếp từ broker (subscribe `home/+/+/status` qua WebSocket).
  Thiết bị gửi status mà chưa đăng ký hiện ở bảng riêng để bấm “Đăng ký”. Không xóa / đổi mã được thiết bị đang được luật dùng.
- **Luật:** ghi `backend/config/rules.json`; automation engine tự nạp lại khi file đổi (`AutomationService.reload_rules_if_changed`).
  Thiết bị trong luật phải đã đăng ký. Kiểm thử: `backend/tests/test_rules.py`.
- **Người dùng:** 2 vai trò cố định `admin`, `user` (mã không đổi được, tên hiển thị đổi được). Ràng buộc: không tự xóa / tự khóa /
  tự hạ quyền; luôn còn ≥ 1 admin hoạt động; đổi mật khẩu hoặc khóa thì xóa phiên đang mở của người đó.
  **Xóa là xóa mềm** (cột `users.deleted_at`): tài khoản bị ẩn khỏi danh sách, số liệu, vai trò và không đăng nhập được;
  tạo lại cùng email thì dùng lại bản ghi cũ. Seed tự thêm cột này vào database cũ (`ALTER TABLE ... IF NOT EXISTS`). Kiểm thử: `backend/tests/test_users.py`.

### 3.4 Thiết bị giả lập ✅

| Tầng | File |
|---|---|
| Điểm vào | `backend/run_simulator.py` → `backend/controllers/simulator_controller.py` |
| Logic | `backend/simulator/house.py` (phòng, vòng mô phỏng vật lý mỗi giây), `backend/simulator/devices.py` (20 thiết bị, mỗi thiết bị một MQTT client có LWT) |
| Topic | `home/<phòng>/<thiết bị>/status` (retained, discovery), `/state` (retained), `/set` (nhận lệnh) |
| Dùng chung | `backend/common/cli.py`, `backend/common/mqtt_client.py` |
| Tài liệu | `docs/02_thiet_bi.md`, README §3 |

### 3.5 Automation: luật tự động & kịch bản ✅

| Tầng | File |
|---|---|
| Điểm vào | `backend/run_automation.py` → `backend/controllers/automation_controller.py` |
| Service | `backend/services/automation_service.py` (chạy luật, kịch bản, chế độ nhà), `rule_helpers.py` (hàm thuần đánh giá điều kiện), `scene_validation.py` (kiểm tra kịch bản người dùng tạo) |
| Cấu hình thực thi | `backend/config/rules.json` (admin sửa qua trang quản trị, engine tự nạp lại), `backend/config/scenes.json`; kịch bản người dùng thêm lưu ở `scenes.custom.json` (không commit) qua `backend/repositories/scene_repository.py` |
| Topic điều khiển | `home/_auto/mode/set`, `home/_auto/scene/set`, `home/_auto/rule/set`; phát ra `home/_auto/engine/status`, `home/_auto/mode/state`, `home/_auto/notify/event` |
| Frontend | `frontend/js/app.js` (màn hình Kịch bản, Luật), `js/scene-editor.js` (tạo kịch bản) |
| Kiểm thử | `backend/tests/test_scenes.py` |
| Tài liệu | `docs/03_kich_ban.md`, `docs/04_luat_tu_dong.md`, README §6 |
| Lưu ý | Mã kịch bản trong `seed.py` phải trùng `id` trong `scenes.json` |

### 3.6 Dashboard điều khiển (người dùng) ✅

| Màn hình (`#hash`) | File chính | Tài liệu |
|---|---|---|
| Trang chủ `#/home` | `js/nav.js` (khung), `js/app.js` | `docs/01_trang_chu.md` |
| Thiết bị `#/devices` | `js/app.js` (`renderDevice`, `renderRoomSummary`) | `docs/02_thiet_bi.md` |
| Kịch bản `#/scenes` | `js/app.js`, `js/scene-editor.js` | `docs/03_kich_ban.md` |
| Luật `#/rules` | `js/app.js` (`renderEngine`) | `docs/04_luat_tu_dong.md` |
| Thông báo `#/alerts` | `js/app.js` | `docs/05_thong_bao.md` |
| Lịch sử `#/history` | `js/history.js`, `css/history.css` | `docs/06_lich_su.md` |
| Log `#/log` | `js/app.js` | `docs/07_log.md` |

- Người dùng đăng nhập xong vào `index.html`, tự kết nối broker thật `ws://localhost:9001` (đổi bằng `?broker=ws://IP:9001`).
- Thiết bị hiện trên dashboard là thiết bị thật đang publish lên broker (simulator Python và/hoặc ESP32). Nút **Demo** chuyển sang giả lập trong trình duyệt.
- Chỉ tài khoản `user` vào được trang này; admin bị đưa về `admin.html`.

### 3.7 Chế độ Demo trong trình duyệt (dự phòng) ✅

| Tầng | File |
|---|---|
| Giả lập | `frontend/mock/demo.js`: broker, 20 thiết bị và automation chạy trong trình duyệt, cùng topic và luật với backend |
| Bật | Nút **Demo** trên trang người dùng (hoặc `index.html?demo=1`), hoặc tự bật trên GitHub Pages. Trang quản trị không có Demo |
| Triển khai | `.github/workflows/pages.yml` đưa `frontend/` lên https://nhom9-ltm.github.io/MQTT/ (bỏ qua đăng nhập vì không có API) |

### 3.8 Logger & lịch sử ✅

| Tầng | File |
|---|---|
| Ghi | `backend/run_logger.py` → `controllers/logger_controller.py` → `services/logger_service.py` → `repositories/message_repository.py` → `backend/data/smarthome.db` |
| Minh họa MQTT | Client id cố định + `clean_session=False` + QoS 1: tắt logger rồi bật lại vẫn nhận bù message |
| Đọc (API) | `/api/summary`, `/api/climate`, `/api/energy`, `/api/commands`, `/api/alerts`: `controllers/api_controller.py` → `services/history_service.py` → `repositories/history_repository.py` (mở SQLite chỉ đọc) |
| Frontend | `frontend/js/history.js` |
| Xuất CSV / báo cáo | `python backend/run_logger.py --export file.csv` / `--report` |

### 3.9 Thông báo Telegram / Email 🟡

| Tầng | File |
|---|---|
| Điểm vào | `backend/run_notifier.py` → `controllers/notifier_controller.py` |
| Service | `services/notification_service.py` (lọc mức độ, chống spam), `services/notify_channels.py` (Telegram Bot, SMTP) |
| Cấu hình | Biến môi trường `TELEGRAM_TOKEN`, `TELEGRAM_CHAT`, `SMTP_USER`, `SMTP_PASS`, `MAIL_TO` |
| Server giả | `backend/simulator/fake_notify_servers.py`: **lỗi trên Python 3.12+** (dùng module `asyncore` đã bị bỏ) |
| Tài liệu | `docs/MO_RONG.md` mục 1, `docs/05_thong_bao.md` |

### 3.10 Bảo mật broker (xác thực + ACL) ✅

| Tầng | File |
|---|---|
| Cấu hình | `infra/broker/mosquitto.secure.conf`, `infra/broker/acl.conf`, `docker-compose.secure.yml` |
| Tạo tài khoản | `python infra/broker/setup_auth.py` |
| Kiểm tra | `python infra/broker/test_acl.py` |
| Frontend | `frontend/js/auth.js` (`?user=dashboard&pass=...`) |
| Tài liệu | `docs/MO_RONG.md` mục 2 |

### 3.11 ESP32 thật ✅

| Tầng | File |
|---|---|
| Firmware | `firmware/esp32/esp32_smarthome_node/` |
| Luật riêng | Các luật `lab_*` trong `backend/config/rules.json` |
| Danh mục | Phòng `lab`, 7 thiết bị `is_simulated = False` trong `backend/database/seed.py` |
| Tài liệu | README §7 |

### 3.12 Chỉ có khung / tham khảo ⬜

| Thư mục / file | Tình trạng |
|---|---|
| `docs/legacy/v1-monitor/` | Phiên bản 1 (chỉ giám sát nhiệt độ/độ ẩm), không còn chạy cùng hệ thống |
| `frontend/layout/sidebar_wireframe.html` | Bản vẽ khung để tham khảo bố cục, không phải trang dùng thật |
| `frontend/history.html` | Chỉ chuyển hướng sang `index.html#/history` |

---

## 4. Bảng dữ liệu theo nhóm

**PostgreSQL** (`backend/database/schema.sql`, container `mqtt-database`, cổng 5434):

| Nhóm | Bảng |
|---|---|
| Tài khoản & phiên | `roles`, `users` (có `deleted_at` cho xóa mềm), `sessions`, `login_history` |
| Thiết bị | `rooms`, `device_types`, `devices` |
| Tự động hóa (danh mục) | `automation_rules`, `scenes` |

**SQLite** (`backend/data/smarthome.db`, do logger tạo): bảng `messages` và các view `climate`, `energy`, `commands`
(`backend/repositories/message_repository.py`).

---

## 5. Thư mục `docs/`: tài liệu nào nói về gì

| File | Nội dung |
|---|---|
| `CAU_TRUC_THU_MUC_THEO_CHUC_NANG.md` | Tài liệu này |
| `01_trang_chu.md` … `07_log.md` | Prompt xây dựng từng màn hình của dashboard |
| `HUONG_DAN_NHOM.md` | Phân công, quy ước làm việc nhóm |
| `MO_RONG.md` | Thông báo Telegram/Email, xác thực + ACL, biểu đồ lịch sử |
| `legacy/` | Mã nguồn phiên bản 1 |

Ở gốc repo: `README.md` (tổng quan, kiến trúc, topic) và `CACH_CHAY.md` (lệnh chạy).

---

## 6. Cách dùng file này

1. Chọn chức năng ở mục 3.
2. Mở đúng các file trong bảng tương ứng: controller để xem đầu vào (HTTP/MQTT), service để xem luồng xử lý,
   repository + mục 4 để xem dữ liệu đọc/ghi, frontend để xem màn hình.
3. Phần đánh dấu 🟡/⬜ phải ghi rõ là "một phần / chưa triển khai", không suy ra hành vi từ code mẫu.
4. Khi thêm, xoá hoặc di chuyển file, cập nhật lại bảng tương ứng.
