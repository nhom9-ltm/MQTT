# Prompt 02 — Trang Thiết bị (+ danh sách phòng trên sidebar)

> **Điều kiện tiên quyết:** prompt 01 đã hoàn thành. Trước khi làm, kiểm tra `frontend/js/nav.js` tồn tại, `frontend/index.html` có `<aside id="sidebar">` và `<section class="page" id="page-devices">`. **Nếu thiếu: dừng lại và báo cáo, không tự làm thay prompt 01.**

## 0. Quy tắc bắt buộc (đọc kỹ trước khi làm)

1. **Chỉ làm đúng những gì prompt này yêu cầu.** Không thêm tính năng, không "tiện tay" sửa chỗ khác, không tối ưu hay refactor ngoài phạm vi.
2. **Chỉ được sửa/tạo các file nêu ở mục 2 "Phạm vi file".** Mọi file khác — đặc biệt `backend/**`, `frontend/js/app.js`, `frontend/mock/demo.js`, `frontend/css/style.css`, `docker-compose*.yml`, `.github/**`, các file `.md` — là **CẤM SỬA**, kể cả khi bạn thấy lỗi hoặc có cách làm hay hơn.
3. **Không sửa logic hiện có.** Giữ nguyên id phần tử, tên hàm, topic MQTT, định dạng payload và hành vi của dashboard. Có thể di chuyển phần tử nhưng **không đổi/xóa id và class**.
4. **Màu sắc giữ nguyên như đang áp dụng.** Chỉ dùng các biến CSS đã có trong `frontend/css/style.css` (`--bg`, `--panel`, `--line`, `--text`, `--muted`, `--accent`, `--ok`, `--bad`, …). Không thêm giá trị màu mới, không đổi giá trị biến, không đổi font. Chế độ sáng/tối phải chạy như cũ. Wireframe chỉ là bố cục thuần xám: **không lấy màu từ wireframe**.
5. **Khi có thắc mắc, mâu thuẫn hoặc phải làm việc ngoài phạm vi: KHÔNG tự đoán, KHÔNG tự quyết theo ý mình.** Nếu điều đó chặn cả công việc thì dừng lại và hỏi người dùng. Nếu chỉ chặn một phần thì bỏ qua phần đó, làm phần còn lại và ghi câu hỏi vào mục "Cần xác nhận" của báo cáo.
6. Không cài thư viện, không thêm CDN/script ngoài, không đổi tên hay di chuyển file, không `git commit`/`git push`.
7. Nếu phải bật/tắt dịch vụ để kiểm tra, trả về đúng trạng thái ban đầu khi xong.

## 1. Bối cảnh

Trang **Thiết bị** (`#/devices`) hiển thị các thẻ điều khiển thiết bị theo phòng. `app.js` tự dựng các phần tử này khi phát hiện thiết bị qua MQTT:
- `#roomTabs` — hàng tab phòng ("Tất cả" + từng phòng). **`app.js` dựng lại toàn bộ nội dung `#roomTabs` mỗi khi có phòng mới/mất** (hàm `renderTabs`), bấm tab sẽ lọc phòng.
- `#rooms` — chứa các `section.room[data-room="<id>"]`; trong mỗi phòng là các thẻ `.dev`. Thẻ thiết bị offline có thêm lớp `offline`.
- `#kOnline` — chữ dạng `"19/20"` (online/tổng).

Tham chiếu bắt buộc: **wireframe** `frontend/layout/sidebar_wireframe.html` (mục 1 — nhóm "Thiết bị" xổ xuống; mục 4 — hàng "Thiết bị (+ phòng)"; chú thích số 2).

## 2. Phạm vi file

| Việc | File |
|---|---|
| Được **sửa** | `frontend/js/nav.js`, `frontend/layout/sidebar.css`, `frontend/layout/layout.css`, `frontend/index.html` (chỉ phần bên trong `#page-devices`) |
| Chỉ **đọc** | `frontend/js/app.js`, `frontend/css/style.css`, wireframe |
| **CẤM** | mọi file còn lại |

## 3. Yêu cầu

**3.1. Submenu phòng trên sidebar** (mục "Thiết bị")
- Hiển thị ngay bên dưới mục "Thiết bị" và **luôn mở** khi sidebar ở dạng mở rộng (đúng wireframe mục 1). Khi sidebar thu gọn thì ẩn submenu (wireframe mục 2).
- Mỗi phòng một dòng: **chấm trạng thái** + tên phòng + **huy hiệu số thiết bị** của phòng. Chấm đặc nếu phòng còn ít nhất 1 thiết bị online; chấm rỗng nếu tất cả offline (ví dụ phòng Lab khi ESP32 mất điện: chấm rỗng, huy hiệu "0/7" — dạng `online/tổng`).
- Dữ liệu **chỉ lấy từ DOM**: tên phòng từ các nút trong `#roomTabs`; số thiết bị từ các `.dev` trong `section.room[data-room]` tương ứng; online = `.dev:not(.offline)`. Dùng `MutationObserver` (trên `#roomTabs` và `#rooms`, có chống gọi dồn bằng `requestAnimationFrame`) để cập nhật.
- Dòng "Tất cả" đứng đầu.

**3.2. Lọc phòng**
- Bấm một phòng trong sidebar → đổi hash `#/devices/<roomId>` **và** gọi `.click()` lên nút tab tương ứng trong `#roomTabs` (tái sử dụng logic lọc của `app.js`, **không viết lại logic lọc**). "Tất cả" → `#/devices`.
- Mở thẳng `#/devices/<roomId>` (hoặc F5): áp dụng bộ lọc ngay khi phòng đó xuất hiện (thiết bị được phát hiện sau khi kết nối). Nếu phòng không tồn tại, hiển thị "Tất cả".
- Bấm trực tiếp tab trong `#roomTabs` (nếu còn hiển thị) phải cập nhật hash và dòng đang chọn trên sidebar.
- Dòng phòng đang chọn có kiểu "active" như mục chính.

**3.3. Huy hiệu mục "Thiết bị"**: đổ dữ liệu vào `[data-badge="devices"]` theo nội dung `#kOnline` (dạng `19/20`); ẩn khi `0/0`. Quan sát `#kOnline` bằng `MutationObserver`.

**3.4. Hàng tab phòng** `#roomTabs`: do sidebar đã có danh sách phòng nên **ẩn bằng CSS** hàng tab trên màn hình ≥ 768px (wireframe: "thay cho hàng tab"). **Không xóa khỏi DOM** (`app.js` cần nó). Trên mobile (< 768px) **hiện lại** hàng tab vì sidebar bị ẩn.

**3.5. Bố cục trang** theo wireframe: tiêu đề phòng + dòng tóm tắt, lưới thẻ tự co theo chiều rộng (giữ kích thước cột hiện tại), chưa có thiết bị thì hiện `#emptyDevices` như cũ. Không đổi giao diện bên trong thẻ thiết bị.

### Điểm CHƯA được chốt — KHÔNG tự làm, ghi vào "Cần xác nhận"
1. Ô **tìm thiết bị** trên thanh trên.
2. Nếu không thể lấy dữ liệu chấm/huy hiệu chỉ bằng DOM mà không sửa `app.js` → **không sửa `app.js`**; làm phần còn lại và báo cáo rõ cách bạn đề xuất.

## 4. Tiêu chí nghiệm thu

- [ ] Sidebar liệt kê đúng 4 phòng + (Lab nếu có ESP32/Demo) đúng tên, số thiết bị đúng.
- [ ] Bấm phòng → chỉ phòng đó hiển thị; "Tất cả" → hiển thị đủ; hash đổi tương ứng.
- [ ] F5 ở `#/devices/kitchen` → vẫn lọc đúng phòng bếp sau khi thiết bị xuất hiện.
- [ ] Bấm **Mất điện** ở một thiết bị rồi chờ LWT: huy hiệu phòng/mục Thiết bị giảm đúng; phòng tất cả offline có chấm rỗng.
- [ ] Mọi chức năng điều khiển trên thẻ (bật/tắt, thanh trượt, rèm, khóa, "Giả lập", "Mất điện") hoạt động như cũ.
- [ ] Mobile (< 768px) vẫn lọc được phòng bằng hàng tab.
- [ ] Màu sắc sáng/tối không đổi; Console không lỗi; `git diff --stat` chỉ gồm file ở mục 2.

## 5. Cách kiểm tra

1. `docker compose up -d`, `python backend/run_simulator.py`, `python backend/run_automation.py`; mở http://localhost:8080/#/devices. Hoặc `?demo=1`.
2. Với ESP32/Lab: dùng Demo hoặc simulator; thử tắt một phòng bằng cách bấm "Mất điện" trên thiết bị.
3. Kiểm tra ở 1280px, 900px, 420px và cả hai chế độ sáng/tối.

## 6. Báo cáo khi hoàn thành (bắt buộc, đúng định dạng)

```
## Báo cáo — Prompt 02
### 1. Đã làm       (mỗi file: đã thay đổi gì)
### 2. Đã kiểm tra   (từng tiêu chí nghiệm thu: đạt / không đạt + bằng chứng)
### 3. Cần xác nhận  (câu hỏi cho người dùng; ghi rõ phần nào đang bị bỏ lại vì chưa rõ)
### 4. Phát hiện ngoài phạm vi (lỗi/đề xuất bạn thấy nhưng KHÔNG sửa)
```
