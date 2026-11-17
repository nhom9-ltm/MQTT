# Hệ thống an ninh (chống trộm)

Bộ máy an ninh chạy **bên trong automation engine** (`backend/services/security_service.py`). Nó thay thế 2 luật
cũ `intrusion_door` và `intrusion_motion`. Hai luật này chỉ gửi được một thông báo; bản mới có thêm thời gian chờ
khi ra/vào nhà, tắt bằng mã PIN, giữ trạng thái báo động và phân vùng cảm biến.

| File | Vai trò |
|---|---|
| `backend/config/security.json` | Cấu hình: PIN (băm), thời gian chờ, cảm biến và vùng, hành động khi báo động, giả lập có người |
| `backend/services/security_service.py` | Máy trạng thái an ninh (không biết MQTT, test được không cần broker) |
| `backend/services/automation_service.py` | Chuyển trạng thái cảm biến, đổi chế độ, lệnh `security/set` cho bộ máy an ninh; chặn đổi chế độ khi chưa nhập PIN |
| `frontend/js/security.js`, `frontend/css/security.css` | Khung An ninh trong panel Chế độ, banner báo động, hộp nhập PIN |
| `frontend/mock/demo.js` | Bản rút gọn để chế độ **Demo** cũng có an ninh (PIN `1234`) |
| `backend/tests/test_security.py` | 24 ca kiểm thử |

## Trạng thái

```
disarmed ──(chọn Vắng nhà)──▶ arming ──(hết exit_delay)──▶ armed_away ──┐
    ▲       (chọn Ban đêm)───────────────────────────────▶ armed_night ─┤ cửa mở (vùng entry)
    │                                                                    ▼
    │                                        triggered ◀──(hết entry_delay)── pending
    │                                            ▲
    └────────(nhập đúng PIN)────────────── chuyển động trong nhà khi vắng nhà / nút Khẩn cấp
```

| Trạng thái | Ý nghĩa |
|---|---|
| `disarmed` | Tắt |
| `arming` | Vừa chọn *Vắng nhà*, đếm ngược `exit_delay` giây để ra khỏi nhà; cảm biến chưa được canh |
| `armed_away` | Canh gác khi vắng nhà: cửa và chuyển động trong nhà |
| `armed_night` | Canh gác ban đêm: chỉ canh cửa (người nhà vẫn đi lại trong nhà) |
| `pending` | Cửa vừa mở, đếm ngược `entry_delay` giây để nhập PIN; dashboard tự mở hộp nhập PIN |
| `triggered` | **Báo động**: cảnh báo `critical` (notifier gửi Telegram/Email), bật toàn bộ đèn, nhắc lại mỗi `repeat_notify` giây; sau `alarm_duration` giây tự quay về canh gác |

## Quy tắc

- **Bật an ninh**: tự động khi chế độ nhà chuyển sang *Vắng nhà* / *Ban đêm*, không cần PIN.
- **Tắt an ninh**: phải nhập PIN. Ngoại lệ: *Ban đêm* → *Ở nhà* (ví dụ kịch bản "Buổi sáng") tự tắt, vì chỉ người
  trong nhà mới chuyển được.
- **Đang canh gác vắng nhà / đang chờ PIN / đang báo động** thì engine **từ chối**:
  - lệnh đổi chế độ (trừ *Vắng nhà*),
  - kịch bản có bước đổi chế độ (ví dụ "Về nhà", vì kịch bản này mở khóa cửa),
  - luật hoặc kịch bản tự động chuyển về *Ở nhà*.

  Kịch bản không đổi chế độ (ví dụ "Xem phim") vẫn chạy bình thường.
- Nhập đúng PIN thì an ninh tắt và engine tự chuyển sang chế độ được chọn (mặc định *Ở nhà*, chạy kịch bản "Về nhà").
- Nhập sai `max_attempts` lần (mặc định 5) thì **khóa nhập PIN** `lockout` giây và gửi cảnh báo `critical`.

### Vùng cảm biến (`zone`)
| Vùng | Khi `armed_away` | Khi `armed_night` |
|---|---|---|
| `entry` (cửa chính) | `pending` → hết giờ thì báo động | `pending` → hết giờ thì báo động |
| `interior` (chuyển động trong nhà) | **Báo động ngay** (nếu đang `pending` thì coi như người vừa vào cửa, vẫn chờ PIN) | Bỏ qua |
| `perimeter` (chuyển động trước cửa) | Chỉ cảnh báo `warn`, tối đa 1 lần/phút | Chỉ cảnh báo `warn` |

Chỉ tính **sườn lên** (sai → đúng). Trạng thái retained lúc engine khởi động không bị coi là sự kiện. Thiết bị bị
quản trị viên khóa thì bị bỏ qua.

### Khác
- **Cảm biến mất kết nối** (LWT) khi đang canh gác: cảnh báo `critical`, vì đây có thể là dấu hiệu bị phá.
- **Nút Khẩn cấp** trên dashboard: báo động ngay. Nếu bấm khi an ninh đang tắt, hết giờ báo động sẽ quay về *Tắt*.
- **Giả lập có người ở nhà** (`presence`): khi `armed_away` trong khung giờ (mặc định 18:00–23:00), engine bật/tắt
  ngẫu nhiên các đèn trong danh sách, mỗi 5–15 phút một lần. Hết khung giờ thì tắt các đèn đã bật giả.
- **Bộ giả lập** (`run_simulator.py`) và **Demo** không còn tự sinh chuyển động ngẫu nhiên khi *Vắng nhà* (không có
  người thì không có chuyển động). Nếu không làm vậy sẽ có báo động giả khoảng 90 giây một lần. Nút **Giả lập** trên
  dashboard vẫn kích hoạt được cảm biến để demo.
- Engine khởi động lại thì khôi phục trạng thái từ retained message `home/_auto/security/state`: đang canh gác thì vẫn
  canh gác, đang đếm ngược thì đếm tiếp.

## MQTT

| Topic | Chiều | Retain | Payload |
|---|---|:-:|---|
| `home/_auto/security/state` | engine → | ✔ | `{"state","label","arm_mode","by","since","remaining","trigger":{"device","name"},"locked_until","ts"}` |
| `home/_auto/security/set` | → engine | ✘ | `{"action":"disarm","pin":"1234","mode":"home"}` · `{"action":"panic"}` |
| `home/_auto/engine/status` | engine → | ✔ | thêm khóa `security`: danh sách cảm biến được canh, `exit_delay`, `entry_delay` |

ACL không phải sửa cho dashboard và automation (đã có `home/_auto/+/set` và `home/_auto/#`). Mình chỉ thêm quyền
`topic read home/_auto/mode/state` cho user `simulator`.

**Mã PIN đi qua broker dạng chữ thường.** Logger và trang Message log của dashboard đều che PIN (`"pin":"***"`),
nhưng client nào được đọc `home/#` vẫn thấy được PIN. Khi triển khai thật, hãy bật TLS và giới hạn quyền đọc.

## Cấu hình: `backend/config/security.json`

| Khóa | Mặc định | Ý nghĩa |
|---|---|---|
| `pin` | PIN `1234` | `{"salt","hash"}` băm PBKDF2-SHA256 (100.000 vòng) |
| `exit_delay` / `entry_delay` | 20 / 20 | Giây chờ ra khỏi nhà / chờ nhập PIN sau khi mở cửa |
| `alarm_duration` / `repeat_notify` | 600 / 120 | Báo động kéo dài bao lâu / nhắc lại mỗi bao lâu (giây) |
| `max_attempts` / `lockout` | 5 / 60 | Số lần nhập sai trước khi khóa / thời gian khóa (giây) |
| `sensors` | 4 cảm biến | `{"device","field","value","zone","name"}` |
| `on_trigger` | bật mọi đèn 100% | Danh sách hành động giống `actions` của luật |
| `presence` | bật, 18:00–23:00 | `{"enabled","after","before","lights":[…],"min_s","max_s"}` |

Đổi PIN (lưu dạng băm, không ghi PIN gốc vào file):
```powershell
python backend/run_automation.py --set-pin
```
Sửa `security.json` xong thì khởi động lại automation.

## Demo trên lớp
1. Bấm **Vắng nhà**: mọi thứ tắt, cửa khóa, khung An ninh đếm ngược 20 giây rồi chuyển sang *Đang canh gác*.
2. Bấm **Ở nhà** → hộp PIN hiện ra (đang canh gác thì không đổi chế độ được nếu chưa nhập PIN).
3. Ở cảm biến cửa, bấm **Mở cửa** → banner vàng *"Cửa chính mở — nhập PIN trong 20s"*, hộp PIN tự mở.
   - Nhập `1234` → tắt an ninh, tự chạy *Về nhà*.
   - Không nhập → **BÁO ĐỘNG**: banner đỏ, mọi đèn bật, điện thoại nhận Telegram (nếu chạy notifier).
4. Nhập sai 5 lần → khóa 60 giây, có cảnh báo đỏ.
5. Mở **Message log**: lệnh `home/_auto/security/set` hiện `"pin":"***"`.

## Kiểm thử
```powershell
python -m unittest backend.tests.test_security -v
```
