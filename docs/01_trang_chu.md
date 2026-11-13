# Prompt 01 — Trang chủ + khung sidebar dùng chung

> Đây là prompt **nền tảng**. Các prompt 02–07 đều dựa vào khung sidebar/thanh trên/router mà prompt này tạo ra, nên phải làm xong prompt này trước.

## 0. Quy tắc bắt buộc (đọc kỹ trước khi làm)

1. **Chỉ làm đúng những gì prompt này yêu cầu.** Không thêm tính năng, không "tiện tay" sửa chỗ khác, không tối ưu hay refactor ngoài phạm vi.
2. **Chỉ được sửa/tạo các file nêu ở mục 2 "Phạm vi file".** Mọi file khác — đặc biệt `backend/**`, `frontend/js/app.js`, `frontend/mock/demo.js`, `frontend/css/style.css`, `docker-compose*.yml`, `.github/**`, các file `.md` — là **CẤM SỬA**, kể cả khi bạn thấy lỗi hoặc có cách làm hay hơn.
3. **Không sửa logic hiện có.** Giữ nguyên id phần tử, tên hàm, topic MQTT, định dạng payload và hành vi của dashboard. `app.js` tìm phần tử theo id, nên được phép **di chuyển** phần tử sang chỗ khác trong HTML nhưng **không đổi/xóa id và class**.
4. **Màu sắc giữ nguyên như đang áp dụng.** Chỉ dùng các biến CSS đã có trong `frontend/css/style.css` (`--bg`, `--bg-2`, `--panel`, `--line`, `--text`, `--muted`, `--accent`, `--ok`, `--warn`, `--bad`, `--c-*`…). Không thêm giá trị màu mới (hex/rgb/hsl), không đổi giá trị biến, không đổi font. Chế độ sáng/tối (`prefers-color-scheme`) phải chạy như cũ. File wireframe chỉ là bố cục thuần xám: **không lấy màu từ wireframe**.
5. **Khi có thắc mắc, mâu thuẫn hoặc phải làm việc ngoài phạm vi: KHÔNG tự đoán, KHÔNG tự quyết theo ý mình.** Nếu điều đó chặn cả công việc thì dừng lại và hỏi người dùng. Nếu chỉ chặn một phần thì bỏ qua phần đó, làm phần còn lại và ghi câu hỏi vào mục "Cần xác nhận" của báo cáo.
6. Không cài thư viện, không thêm CDN/script ngoài, không đổi tên hay di chuyển file, không `git commit`/`git push`.
7. Nếu phải bật/tắt dịch vụ để kiểm tra, trả về đúng trạng thái ban đầu khi xong.

## 1. Bối cảnh

Dự án nhà thông minh dùng MQTT. Giao diện nằm trong `frontend/` (HTML/CSS/JS thuần, không build). Hiện `frontend/index.html` là **một trang cuộn dài** gồm: chế độ + kịch bản, KPI, thiết bị theo phòng, 2 biểu đồ, luật tự động, thông báo, message log. Cần chuyển thành **ứng dụng một trang có sidebar trái** để mỗi mục là một "màn hình", **không tải lại trang** (để giữ kết nối MQTT).

Tài liệu tham chiếu bắt buộc đọc:
- **Wireframe:** `frontend/layout/sidebar_wireframe.html` — mở bằng trình duyệt; dùng mục 1 (desktop), 2 (thu gọn), 3 (mobile), 4 (nội dung từng mục), 5 (hành vi).
- Code hiện tại: `frontend/index.html`, `frontend/css/style.css`, `frontend/layout/layout.css`, `frontend/js/app.js` (chỉ đọc).

## 2. Phạm vi file

| Việc | File |
|---|---|
| Được **sửa** | `frontend/index.html`, `frontend/layout/layout.css` |
| Được **tạo** | `frontend/layout/sidebar.css`, `frontend/js/nav.js` |
| Chỉ **đọc** | `frontend/layout/sidebar_wireframe.html`, `frontend/css/style.css`, `frontend/js/app.js`, `frontend/mock/demo.js`, `frontend/history.html` |
| **CẤM** | mọi file còn lại |

## 3. Yêu cầu

### A. Khung dùng chung (theo wireframe mục 1, 2, 3, 5)

**A1. Cấu trúc trang.** Bố cục: `<aside id="sidebar">` bên trái + vùng chính gồm thanh trên (`.topbar`), nội dung (`<main>`), chân trang (`.foot`). Nội dung chia thành các **trang** `<section class="page" id="page-…">`:

| Trang | Id | Chứa (di chuyển từ HTML hiện có, giữ nguyên id bên trong) |
|---|---|---|
| Trang chủ | `page-home` | khối KPI (`.kpis`), **Chế độ nhà** (`#modeSeg`, `#enginePill`), "Kịch bản nhanh" (mới, xem B), khối biểu đồ (`.charts`) |
| Thiết bị | `page-devices` | section chứa `#roomTabs`, `#wcHint`, `#rooms`, `#emptyDevices` |
| Kịch bản | `page-scenes` | panel Kịch bản (`#scenes`, `#sceneTopic`) — Chế độ nhà không còn ở đây |
| Luật tự động | `page-rules` | panel chứa `#rules` |
| Thông báo | `page-alerts` | panel chứa `#alerts`, `#alertClear` |
| Message log | `page-log` | panel chứa `#logBody`, `#logFilter`, `#logHideState`, `#logPause`, `#logClear` |

Ở prompt này chỉ **di chuyển** các khối vào đúng trang và giữ nguyên giao diện bên trong; việc tinh chỉnh từng trang thuộc prompt 02–07.

**A2. Sidebar** — do `frontend/js/nav.js` render vào `<aside id="sidebar" data-active="…">` (để `history.html` dùng lại ở prompt 06). Gồm:
- Logo + tên "Nhà thông minh" + dòng phụ "MQTT · Mosquitto · ESP32" (lấy từ `.brand` hiện có; `.brand` chuyển vào sidebar).
- Mục: **Trang chủ** (`#/home`) · **Thiết bị** (`#/devices`) · **Kịch bản** (`#/scenes`) · **Luật tự động** (`#/rules`) · **Thông báo** (`#/alerts`) · nhóm nhãn **Dữ liệu** → **Lịch sử** (liên kết `history.html`) · nhóm nhãn **Hệ thống** → **Message log** (`#/log`).
- Mỗi mục có icon SVG inline (stroke `currentColor`, cùng kiểu icon logo hiện có) và chỗ cho huy hiệu: `<span class="badge" data-badge="devices|rules|alerts" hidden>`. Prompt này **chỉ tạo chỗ**, không đổ dữ liệu (prompt 02, 04, 05 làm).
- Trên `history.html`, các mục điều hướng là liên kết `index.html#/…`; trên `index.html` là hash route.
- Chân sidebar: dời `#connPill` và `#btnDemo` (giữ nguyên id, `btnDemo` là `type="button"`) xuống đây + nút thu gọn «/».
- Mục đang chọn: kiểu "active" của wireframe (nền nhạt + viền), có `aria-current="page"`.

**A3. Router hash trong `nav.js`.** Chỉ hiện trang tương ứng hash; mặc định/hash lạ → `#/home`; **không tải lại trang, không ngắt MQTT**. Sau mỗi lần đổi trang, phát `window.dispatchEvent(new Event("resize"))` để Chart.js tính lại kích thước. Hỗ trợ hash con dạng `#/devices/<roomId>` (chỉ nhận dạng; xử lý lọc phòng là việc của prompt 02).

**A4. Responsive (wireframe mục 1–3).**
- ≥ 1024px: sidebar mở rộng 240px.
- 768–1023px: tự thu gọn (chỉ icon, 60px, tooltip tên mục khi rê chuột).
- < 768px: sidebar ẩn; nút ☰ ở thanh trên mở ngăn kéo có lớp phủ; **thanh tab dưới** gồm 4 mục: Trang chủ, Thiết bị, Kịch bản, Thêm (Thêm = mở ngăn kéo). Đóng ngăn kéo bằng Esc, bấm lớp phủ, hoặc chọn mục.
- Nút thu gọn do người dùng bấm được nhớ trong `localStorage` khóa `sh.sidebar.collapsed`.
- Truy cập: `<nav aria-label="Điều hướng chính">`, điều hướng được bằng Tab, focus nhìn thấy rõ.

**A5. Thanh trên.** Từ trái sang phải: nút ☰ (chỉ mobile) · đường dẫn trang đang xem (tên trang) · khoảng trống · **điều khiển Chế độ nhà** (`Chế độ: Ở nhà ▾`) · **nút chuông** liên kết `#/alerts` (chưa có số đếm — prompt 05 làm) · **form kết nối hiện có giữ nguyên** (`#brokerUrl`, `#topicPrefix`, `#btnConnect`).
- Điều khiển Chế độ **không có logic riêng**: bấm chọn chế độ nào thì gọi `.click()` lên nút tương ứng trong `#modeSeg`; hiển thị chế độ hiện tại bằng cách quan sát lớp `on` và `disabled` của các nút đó (khi automation chưa chạy thì vô hiệu hóa).
- Xóa nút "Lịch sử" cũ trong form kết nối (đã có trong menu).
- `.toasts` (thông báo nổi) giữ nguyên hành vi; kiểm tra vị trí `top` vẫn không che thanh trên.

**A6. Chân trang** `.foot` (LWT, keep-alive…) giữ nguyên nội dung, hiện ở cuối vùng nội dung của mọi trang.

### B. Trang chủ `#/home` (wireframe mục 4, hàng "Trang chủ")

- **KPI:** giữ **cả 8 ô** hiện có (`#kTemp`, `#kHum`, `#kPower`, `#kLights`, `#kDoor`, `#kOnline`, `#kClients`, `#kRate`), xếp lưới theo `layout.css`.
- **Chế độ nhà:** khối "Chế độ" (`#modeSeg` + `#enginePill`) nằm ở Trang chủ, cùng một hàng với "Kịch bản nhanh" (lưới 2 cột như `.control`). Không còn ở trang Kịch bản.
- **Kịch bản nhanh:** hộp tiêu đề "Kịch bản nhanh" chứa bản **sao** các nút từ `#scenes`. Dùng `MutationObserver` trên `#scenes` để dựng lại khi nội dung đổi; bấm bản sao thì gọi `.click()` lên nút gốc (cùng `data-scene`); trạng thái `disabled` đồng bộ theo nút gốc. Không đổi logic gửi lệnh.
- **Biểu đồ:** giữ `#climateChart`, `#powerChart`, `#rangeSeg`, `#energyHint` (không đổi id); thu nhỏ chiều cao khung biểu đồ trên trang này còn khoảng **180px** (chỉ áp dụng cho `#page-home`).
- Bố cục: KPI → (Chế độ | Kịch bản nhanh) → 2 biểu đồ cạnh nhau.

### C. Điểm CHƯA được chốt — KHÔNG tự làm, phải ghi vào "Cần xác nhận"

1. Ô **tìm thiết bị** ở thanh trên (có trong wireframe nhưng chưa được duyệt).
2. Các mục **"Biểu đồ trực tiếp"** và **"Broker & bảo mật"** trong wireframe: chưa có prompt → **không thêm vào menu**. Vì vậy form kết nối broker và 2 biểu đồ vẫn nằm ở chỗ nêu trên.
3. **6 thẻ thiết bị** trên Trang chủ trong wireframe: không thể làm mà không sửa `app.js` hoặc nhân bản thẻ → **không làm**.
4. Có giữ nhãn nhóm **"Hệ thống"** hay bỏ.
5. Nhúng trang Lịch sử vào cùng khung hay giữ trang riêng (xem prompt 06).

## 4. Tiêu chí nghiệm thu

- [ ] `index.html` mở được ở 1280px, 900px, 420px; bố cục đúng wireframe mục 1, 2, 3.
- [ ] Đổi giữa các mục **không tải lại trang**; kết nối MQTT giữ nguyên (pill vẫn "Đã kết nối", dữ liệu tiếp tục cập nhật).
- [ ] Tất cả chức năng cũ vẫn chạy: kết nối/ngắt, Demo, chọn chế độ, chạy kịch bản, bật/tắt luật, lọc phòng, điều khiển thẻ thiết bị, xóa thông báo, lọc/tạm dừng/xóa log, đổi khoảng thời gian biểu đồ.
- [ ] Không có lỗi trong Console của trình duyệt.
- [ ] Màu sắc ở cả chế độ sáng và tối **giống hệt trước khi sửa** (so sánh ảnh chụp trước/sau).
- [ ] `git diff --stat` chỉ liệt kê các file ở mục 2.

## 5. Cách kiểm tra

1. Chụp ảnh `frontend/index.html` hiện tại (trước khi sửa) ở chế độ sáng và tối để đối chiếu màu.
2. Chạy hệ thống: `docker compose up -d` (dashboard ở http://localhost:8080), rồi `python backend/run_simulator.py` và `python backend/run_automation.py`. Hoặc dùng `http://localhost:8080/?demo=1` nếu không có broker.
3. Duyệt từng mục sidebar, thử thu gọn, thử thu nhỏ cửa sổ xuống < 768px.
4. Mở Console, xác nhận không có lỗi.

## 6. Báo cáo khi hoàn thành (bắt buộc, đúng định dạng)

```
## Báo cáo — Prompt 01
### 1. Đã làm       (mỗi file: đã thay đổi gì)
### 2. Đã kiểm tra   (từng tiêu chí nghiệm thu: đạt / không đạt + bằng chứng)
### 3. Cần xác nhận  (câu hỏi cho người dùng; ghi rõ phần nào đang bị bỏ lại vì chưa rõ)
### 4. Phát hiện ngoài phạm vi (lỗi/đề xuất bạn thấy nhưng KHÔNG sửa)
```
