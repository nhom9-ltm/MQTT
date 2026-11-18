# Những phần đã làm thêm

Nhánh **`feature/mo-rong`** gộp toàn bộ phần làm thêm sau bản trên `main` (PR #2). Mỗi phần có tài liệu riêng, file
này chỉ tóm tắt để cả nhóm nắm nhanh.

| # | Phần | Ngày | Commit | Tài liệu |
|:-:|---|---|---|---|
| 1 | Báo cáo tiền điện theo bậc EVN + cảnh báo ngân sách | 17/11/2026 | `21f22f1` | [MO_RONG.md mục 4](MO_RONG.md#4-tiền-điện--ngân-sách) |
| 2 | Hệ thống an ninh: canh gác, tắt bằng PIN, báo động | 17/11/2026 | `e31d85e` | [AN_NINH.md](AN_NINH.md) |
| 3 | Mã hóa TLS cho MQTT | 18/11/2026 | `7ee6706` | [TLS.md](TLS.md) |
| – | Chặn commit nhầm mọi file `secrets.h` | 17/11/2026 | `912ebad`, `faee3d1` | — |

Kiểm thử: `python -m unittest discover -s backend/tests -t .` → **109 ca, tất cả qua** (thêm mới 14 ca tiền điện,
24 ca an ninh, 12 ca TLS).

---

## 1. Tiền điện + ngân sách

**Làm được gì:** trang **Lịch sử** có thêm khung **Tiền điện theo tháng**. Hệ thống tính tiền điện theo **biểu giá bậc
thang EVN** (có VAT) từ số kWh logger ghi được, dự báo tiền cả tháng và so với ngân sách. Khi sắp vượt hoặc đã vượt
ngân sách thì gửi cảnh báo, giống các cảnh báo khác của hệ thống.

- Hiển thị: tổng kWh, tiền điện, thanh ngân sách, biểu đồ tiền cộng dồn theo ngày + dự báo cuối tháng, chi tiết từng
  bậc giá, tiền của từng thiết bị.
- Cảnh báo: `warn` khi đạt 80% ngân sách hoặc dự báo sẽ vượt; `critical` khi đã vượt (gửi ra điện thoại qua notifier).
  Mỗi mức chỉ báo một lần mỗi tháng.
- Cấu hình giá điện và ngân sách ở `backend/config/energy.json`, sửa xong có hiệu lực ngay.
- API mới: `GET /api/energy/report?month=YYYY-MM`.

**File chính:** `backend/services/energy_service.py`, `backend/services/energy_watcher.py`,
`backend/config/energy.json`, `backend/common/mqtt_publish.py`, `frontend/js/history.js`.

**Demo nhanh:**
```powershell
python backend/database/seed_history.py
$env:HISTORY_DB="backend/data/demo_history.db"; $env:ENERGY_CHECK_MIN="0.2"; python backend/run_api.py
```
Vào **Lịch sử**: dữ liệu mẫu dự báo khoảng 1,3 triệu đồng/tháng, vượt ngân sách 1 triệu nên vài giây sau có cảnh báo.

---

## 2. Hệ thống an ninh

**Làm được gì:** thay 2 luật báo đột nhập cũ (chỉ gửi một thông báo) bằng một **bộ máy an ninh** chạy trong
automation engine.

- Chọn **Vắng nhà** → đếm ngược 20 giây để ra khỏi nhà → **canh gác** cửa và chuyển động trong nhà.
  Chọn **Ban đêm** → chỉ canh cửa (người nhà vẫn đi lại được).
- Cửa mở khi đang canh gác → có 20 giây để **nhập PIN** (dashboard tự mở hộp nhập PIN); không nhập → **BÁO ĐỘNG**:
  banner đỏ, bật mọi đèn, gửi cảnh báo `critical`, nhắc lại định kỳ. Chuyển động trong nhà khi vắng nhà → báo động ngay.
- Đang canh gác thì **không đổi được chế độ / chạy kịch bản "Về nhà"** nếu chưa nhập PIN.
- PIN mặc định **`1234`**, lưu dạng băm PBKDF2; nhập sai 5 lần bị khóa 60 giây. Đổi PIN:
  `python backend/run_automation.py --set-pin`.
- Thêm: nút **Khẩn cấp**, cảnh báo khi cảm biến mất kết nối lúc đang canh gác, giả lập có người ở nhà (bật/tắt đèn
  ngẫu nhiên buổi tối khi vắng nhà), logger và Message log che PIN (`"pin":"***"`).
- Chế độ **Demo** trên trình duyệt cũng có đủ luồng an ninh.

**File chính:** `backend/services/security_service.py`, `backend/config/security.json`,
`backend/services/automation_service.py`, `frontend/js/security.js`, `frontend/css/security.css`, `frontend/mock/demo.js`.

**Topic MQTT mới:** `home/_auto/security/state` (trạng thái, retained), `home/_auto/security/set` (lệnh tắt bằng PIN,
nút khẩn cấp).

**Demo nhanh:** bấm **Vắng nhà** → chờ đếm ngược → ở cảm biến cửa bấm **Mở cửa** → nhập `1234` (hoặc không nhập để
thấy báo động).

---

## 3. Mã hóa TLS

**Làm được gì:** trước đây mọi gói MQTT đi trên mạng ở dạng chữ thường — bắt gói bằng Wireshark là đọc được cả mã PIN
an ninh. Giờ broker có thêm cổng **mã hóa**, client kiểm tra chứng chỉ để chắc chắn đang nói chuyện với đúng broker
(chống broker giả / tấn công xen giữa).

| Cổng | Dùng cho | Mã hóa |
|---|---|:-:|
| 1883 / 9001 | như cũ (giữ để so sánh khi demo) | ✘ |
| **8883** | script Python, ESP32 | ✔ |
| **8443** | dashboard (`wss://`) | ✔ |

- `infra/broker/gen_certs.py` tạo **CA của nhóm** và chứng chỉ cho broker (tự thêm localhost, tên máy, IP LAN);
  `--install` cài CA cho Chrome/Edge. Chứng chỉ và khóa **không** đưa lên GitHub, mỗi máy tự tạo.
- Script Python: thêm `--tls` (tự đổi sang cổng 8883). Dashboard và trang quản trị: mở với `?tls=1`, góc trên hiện
  **"Đã kết nối · TLS"**.
- ESP32: `#define MQTT_USE_TLS 1` trong `secrets.h` (dùng `WiFiClientSecure`).
- Có bản Docker: `docker-compose.tls.yml`.

**File chính:** `infra/broker/gen_certs.py`, `infra/broker/mosquitto.tls.conf`, `backend/common/tls.py`,
`backend/common/cli.py`, `backend/common/mqtt_client.py`, `frontend/js/session.js`.

**Chạy:**
```powershell
pip install -r backend/requirements-extra.txt        # thêm gói cryptography
python infra/broker/gen_certs.py --install            # một lần, mở lại trình duyệt
& "C:\Program Files\mosquitto\mosquitto.exe" -c infra/broker/mosquitto.tls.conf -v
python backend/run_simulator.py --tls                 # tương tự cho automation, logger, notifier
# dashboard: http://localhost:8080/?tls=1
```

**Demo:** Wireshark so sánh cổng 1883 (đọc được `"pin":"1234"`) với cổng 8883 (chỉ thấy `TLS Application Data`) —
kịch bản chi tiết trong [TLS.md](TLS.md#demo-trên-lớp-wireshark).

---

## Lưu ý cho cả nhóm khi lấy nhánh này về

1. `pip install -r backend/requirements.txt -r backend/requirements-extra.txt` (có thêm gói `cryptography`).
2. Luật `intrusion_door` / `intrusion_motion` đã bị gỡ khỏi `backend/config/rules.json` (thay bằng hệ thống an ninh),
   nên automation báo **9 luật** thay vì 11 như trước ([CACH_CHAY.md](../CACH_CHAY.md) đã cập nhật).
3. Muốn dùng TLS: mỗi máy tự chạy `python infra/broker/gen_certs.py`. Không bật TLS thì mọi thứ chạy như cũ.
4. Chưa thử trên phần cứng: firmware ESP32 có TLS chưa được biên dịch và chạy thử trên bo mạch thật.
