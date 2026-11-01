# Prompt 06 — Trang Lịch sử (áp dụng khung sidebar cho `history.html`)

> **Điều kiện tiên quyết:** prompt 01 đã hoàn thành. Trước khi làm, kiểm tra `FE/js/nav.js` tồn tại và hỗ trợ render sidebar vào `<aside id="sidebar" data-active="…">` ở trang khác `index.html`. **Nếu thiếu: dừng lại và báo cáo, không tự làm thay prompt 01.**

## 0. Quy tắc bắt buộc (đọc kỹ trước khi làm)

1. **Chỉ làm đúng những gì prompt này yêu cầu.** Không thêm tính năng, không "tiện tay" sửa chỗ khác, không tối ưu hay refactor ngoài phạm vi.
2. **Chỉ được sửa/tạo các file nêu ở mục 2 "Phạm vi file".** Mọi file khác — đặc biệt `BE/**`, `FE/js/app.js`, `FE/js/history.js` (logic gọi API/vẽ biểu đồ), `FE/mock/demo.js`, `FE/css/style.css`, `docker-compose*.yml`, `.github/**`, các file `.md` — là **CẤM SỬA**, kể cả khi bạn thấy lỗi hoặc có cách làm hay hơn.
3. **Không sửa logic hiện có.** Giữ nguyên id phần tử, tên hàm, đường dẫn và tham số API (`/api/summary`, `/api/climate`, `/api/energy`, `/api/commands`, `/api/alerts`), cách tính số liệu. Có thể di chuyển phần tử nhưng **không đổi/xóa id** mà `history.js` đang dùng.
4. **Màu sắc giữ nguyên như đang áp dụng.** Chỉ dùng các biến CSS đã có trong `FE/css/style.css`; màu các biểu đồ lấy từ biến như hiện tại. Không thêm giá trị màu mới, không đổi giá trị biến, không đổi font. Chế độ sáng/tối phải chạy như cũ. Wireframe chỉ là bố cục thuần xám: **không lấy màu từ wireframe**.
5. **Khi có thắc mắc, mâu thuẫn hoặc phải làm việc ngoài phạm vi: KHÔNG tự đoán, KHÔNG tự quyết theo ý mình.** Nếu điều đó chặn cả công việc thì dừng lại và hỏi người dùng. Nếu chỉ chặn một phần thì bỏ qua phần đó, làm phần còn lại và ghi câu hỏi vào mục "Cần xác nhận" của báo cáo.
6. Không cài thư viện, không thêm CDN/script ngoài, không đổi tên hay di chuyển file, không `git commit`/`git push`.
7. Nếu phải bật/tắt dịch vụ để kiểm tra, trả về đúng trạng thái ban đầu khi xong. Dữ liệu mẫu chỉ ghi vào `BE/data/demo_history.db` (đã bị `.gitignore`); không đụng `BE/data/smarthome.db`.

## 1. Bối cảnh

`FE/history.html` là **trang riêng** (không nằm trong ứng dụng một trang `index.html`), dùng `FE/js/history.js` để gọi API `BE/run_api.py` (mặc định `http://<host>:8000`) và vẽ: 4 ô KPI, nhiệt độ/độ ẩm theo phòng, điện năng theo ngày và theo thiết bị, "Ai ra lệnh?", "Thiết bị bị điều khiển nhiều nhất", danh sách cảnh báo. Hiện nó có thanh trên riêng với nút "← Dashboard", chưa có sidebar.

**Quyết định đã chốt:** giữ `history.html` là **trang riêng** (không nhúng vào `index.html`). Mục "Lịch sử" trên sidebar của `index.html` là liên kết sang `history.html`.

Tham chiếu bắt buộc: **wireframe** `FE/layout/sidebar_wireframe.html` (mục 1–3 để dựng khung; mục 4, hàng "Lịch sử"; mục 5, gạch đầu dòng về GitHub Pages).

## 2. Phạm vi file

| Việc | File |
|---|---|
| Được **sửa** | `FE/history.html`, `FE/css/history.css`, `FE/layout/sidebar.css` (chỉ nếu cần để sidebar hiển thị đúng ở trang này) |
| Chỉ **đọc** | `FE/js/nav.js`, `FE/js/history.js`, `FE/css/style.css`, `FE/layout/layout.css`, wireframe |
| **CẤM** | mọi file còn lại (kể cả `nav.js` và `history.js` — nếu cần đổi, ghi vào "Cần xác nhận") |

## 3. Yêu cầu

**3.1. Áp dụng khung sidebar:** `history.html` có `<aside id="sidebar" data-active="history">` và nạp `js/nav.js` + `layout/sidebar.css`, hiển thị cùng sidebar, thu gọn/ngăn kéo/thanh tab dưới như `index.html` (prompt 01). Mục "Lịch sử" ở trạng thái active. Các mục khác là liên kết `index.html#/…`. Thứ tự nạp CSS giữ: `style.css` → `layout.css` → `sidebar.css` → `history.css`.

**3.2. Thanh trên của trang:** thay nút "← Dashboard" bằng cấu trúc thanh trên tương tự `index.html` (đường dẫn trang "Lịch sử", nút ☰ trên mobile). **Giữ nguyên** các điều khiển hiện có: ô địa chỉ API `#apiUrl`, chọn khoảng thời gian `#range`, nút "Tải lại", `#apiPill` (trạng thái API). Không thêm điều khiển mới.

**3.3. Bố cục nội dung** theo wireframe mục 4 hàng "Lịch sử": giữ lưới hiện tại (KPI → nhiệt độ/độ ẩm → điện năng 2 cột → lệnh 2 cột → cảnh báo); đảm bảo không tràn ngang khi sidebar mở/thu gọn và trên mobile; biểu đồ vẫn co giãn đúng khi sidebar thu gọn/mở (phát sự kiện `resize` đã do nav.js xử lý — chỉ kiểm tra).

**3.4. Khi API không chạy** (ví dụ mở trên GitHub Pages hoặc chưa chạy `python BE/run_api.py`): hiển thị thông báo lỗi hiện có của `history.js` trong ô KPI, **không bị vỡ bố cục**. Không sửa nội dung thông báo.

**3.5. Chế độ mở bằng `file://`:** vẫn dùng được như hiện tại (API mặc định `http://localhost:8000`); sidebar hiển thị đúng và các liên kết sang `index.html#/…` hoạt động.

### Điểm CHƯA được chốt — KHÔNG tự làm, ghi vào "Cần xác nhận"
- Nhúng nội dung Lịch sử vào `index.html` (ứng dụng một trang).
- Bản Demo có dữ liệu giả cho trang Lịch sử trên GitHub Pages.
- Xuất CSV/ảnh biểu đồ, so sánh nhiều khoảng thời gian.

## 4. Tiêu chí nghiệm thu

- [ ] `history.html` hiển thị sidebar đúng như `index.html` ở 1280px, 900px, 420px; mục "Lịch sử" active.
- [ ] Bấm các mục khác của sidebar chuyển được sang `index.html#/…` đúng trang.
- [ ] Từ `index.html`, bấm "Lịch sử" mở `history.html`.
- [ ] Với API đang chạy (dữ liệu mẫu): đủ 4 KPI và 6 biểu đồ/danh sách như trước; đổi khoảng 1h/24h/7 ngày, đổi phòng vẫn chạy; `#apiPill` báo "API OK".
- [ ] Không chạy API: hiện thông báo lỗi trong ô KPI, bố cục không vỡ.
- [ ] Màu sắc sáng/tối và màu biểu đồ **giống hệt trước khi sửa** (so sánh ảnh chụp); Console không lỗi (ngoài lỗi mạng khi API tắt là hợp lệ).
- [ ] `git diff --stat` chỉ gồm file ở mục 2.

## 5. Cách kiểm tra

1. Chụp ảnh `history.html` hiện tại (trước khi sửa) ở chế độ sáng và tối để đối chiếu.
2. Sinh dữ liệu mẫu: `python BE/mock/seed_demo.py`; chạy API với dữ liệu mẫu: `$env:HISTORY_DB="BE/data/demo_history.db"; python BE/run_api.py` (PowerShell).
3. `docker compose up -d`; mở http://localhost:8080/history.html. Thử cả khi tắt API.
4. Dừng API khi xong.

## 6. Báo cáo khi hoàn thành (bắt buộc, đúng định dạng)

```
## Báo cáo — Prompt 06
### 1. Đã làm       (mỗi file: đã thay đổi gì)
### 2. Đã kiểm tra   (từng tiêu chí nghiệm thu: đạt / không đạt + bằng chứng)
### 3. Cần xác nhận  (câu hỏi cho người dùng; ghi rõ phần nào đang bị bỏ lại vì chưa rõ)
### 4. Phát hiện ngoài phạm vi (lỗi/đề xuất bạn thấy nhưng KHÔNG sửa)
```
