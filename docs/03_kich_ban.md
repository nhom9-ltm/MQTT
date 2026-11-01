# Prompt 03 — Trang Kịch bản

> **Điều kiện tiên quyết:** prompt 01 đã hoàn thành. Trước khi làm, kiểm tra `FE/js/nav.js` tồn tại, `FE/index.html` có `<aside id="sidebar">` và `<section class="page" id="page-scenes">`. **Nếu thiếu: dừng lại và báo cáo, không tự làm thay prompt 01.**

## 0. Quy tắc bắt buộc (đọc kỹ trước khi làm)

1. **Chỉ làm đúng những gì prompt này yêu cầu.** Không thêm tính năng, không "tiện tay" sửa chỗ khác, không tối ưu hay refactor ngoài phạm vi.
2. **Chỉ được sửa/tạo các file nêu ở mục 2 "Phạm vi file".** Mọi file khác — đặc biệt `BE/**`, `FE/js/app.js`, `FE/mock/demo.js`, `FE/css/style.css`, `docker-compose*.yml`, `.github/**`, các file `.md` — là **CẤM SỬA**, kể cả khi bạn thấy lỗi hoặc có cách làm hay hơn.
3. **Không sửa logic hiện có.** Giữ nguyên id phần tử, tên hàm, topic MQTT, định dạng payload và hành vi của dashboard. Có thể di chuyển phần tử nhưng **không đổi/xóa id và class**.
4. **Màu sắc giữ nguyên như đang áp dụng.** Chỉ dùng các biến CSS đã có trong `FE/css/style.css`. Không thêm giá trị màu mới, không đổi giá trị biến, không đổi font. Chế độ sáng/tối phải chạy như cũ. Wireframe chỉ là bố cục thuần xám: **không lấy màu từ wireframe**. Màu theo chế độ (`ở nhà`/`vắng nhà`/`ban đêm`) trong `style.css` giữ nguyên.
5. **Khi có thắc mắc, mâu thuẫn hoặc phải làm việc ngoài phạm vi: KHÔNG tự đoán, KHÔNG tự quyết theo ý mình.** Nếu điều đó chặn cả công việc thì dừng lại và hỏi người dùng. Nếu chỉ chặn một phần thì bỏ qua phần đó, làm phần còn lại và ghi câu hỏi vào mục "Cần xác nhận" của báo cáo.
6. Không cài thư viện, không thêm CDN/script ngoài, không đổi tên hay di chuyển file, không `git commit`/`git push`.
7. Nếu phải bật/tắt dịch vụ để kiểm tra, trả về đúng trạng thái ban đầu khi xong.

## 1. Bối cảnh

Trang **Kịch bản** (`#/scenes`) chỉ còn **một khối**, `.panel.scene-panel`. (**Chế độ nhà** — `#modeSeg`, `#enginePill` — đã được chuyển sang **Trang chủ**, không còn ở trang này; không đưa lại về đây.)
- **Kịch bản:** `#scenes` — `app.js` dựng các nút `button.scene[data-scene]` từ dữ liệu retained của automation (5 kịch bản: Về nhà, Ra khỏi nhà, Đi ngủ, Buổi sáng, Xem phim); `#sceneTopic` hiển thị topic.
- Khi automation engine **chưa chạy/offline**, các nút bị `disabled` và `#scenes` hiện câu hướng dẫn chạy `python BE/run_automation.py`. **Hành vi này giữ nguyên.**

Tham chiếu bắt buộc: **wireframe** `FE/layout/sidebar_wireframe.html` (mục 4, hàng "Kịch bản": "5 kịch bản dạng nút lớn" (phần "3 chế độ" trong wireframe nay thuộc Trang chủ); ghi chú "hiện đang mờ khi automation chưa chạy → giữ trạng thái này, kèm câu hướng dẫn").

## 2. Phạm vi file

| Việc | File |
|---|---|
| Được **sửa** | `FE/layout/layout.css`, `FE/layout/sidebar.css` (nếu cần cho mục menu), `FE/index.html` (chỉ phần bên trong `#page-scenes`) |
| Chỉ **đọc** | `FE/js/app.js`, `FE/js/nav.js`, `FE/css/style.css`, wireframe |
| **CẤM** | mọi file còn lại (kể cả `nav.js` — nếu cần đổi nó, hãy ghi vào "Cần xác nhận") |

## 3. Yêu cầu

**3.1. Bố cục trang** theo wireframe: một `.panel` rộng toàn chiều ngang vùng nội dung, có tiêu đề "Kịch bản" và chú thích topic như hiện tại.

**3.2. (Đã bỏ)** Chế độ nhà không còn thuộc trang này. Không thêm, không sửa khối Chế độ ở đây.

**3.3. Kịch bản dạng nút lớn:** các `button.scene` hiển thị dạng lưới nút lớn (biểu tượng emoji + tên), 5 nút xếp lưới tự co (ví dụ 2–3 cột desktop, 1–2 cột mobile). **Chỉ đổi kích thước/bố cục bằng CSS** gắn vào phạm vi `#page-scenes`; không đổi HTML do `app.js` sinh ra.

**3.4. Trạng thái "engine chưa chạy":** các nút mờ (disabled) giống hiện tại; câu hướng dẫn `<span class="muted">Chạy <code>python BE/run_automation.py</code> …` hiển thị rõ, căn giữa khối, không bị cắt.

**3.5. Đồng bộ với trang Trang chủ:** nút "Kịch bản nhanh" ở Trang chủ chỉ **ủy quyền** (`.click()`) sang các nút ở trang này. Vì vậy `#scenes` **phải luôn còn trong DOM** (ẩn bằng `display:none` khi không ở trang này là đủ; **không** dùng cách xóa khỏi DOM).

### Điểm CHƯA được chốt — KHÔNG tự làm, ghi vào "Cần xác nhận"
- Việc thêm, sửa, xóa kịch bản từ giao diện (hiện kịch bản chỉ sửa được trong `BE/config/scenes.json`).
- Hiển thị danh sách hành động của từng kịch bản.

## 4. Tiêu chí nghiệm thu

- [ ] Bấm từng kịch bản: lệnh được gửi (xem trang Message log hoặc terminal `run_automation.py`), thông báo "Chạy kịch bản …" xuất hiện.
- [ ] Tắt automation (`Ctrl+C`): nút chuyển mờ, `#enginePill` báo offline, câu hướng dẫn hiện; bật lại thì dùng được.
- [ ] Nút "Kịch bản nhanh" ở Trang chủ vẫn hoạt động; chế độ nhà (ở Trang chủ và thanh trên) không bị ảnh hưởng.
- [ ] Hiển thị đúng ở 1280px, 900px, 420px; màu sáng/tối không đổi; Console không lỗi.
- [ ] `git diff --stat` chỉ gồm file ở mục 2.

## 5. Cách kiểm tra

1. `docker compose up -d`, `python BE/run_simulator.py`, `python BE/run_automation.py`; mở http://localhost:8080/#/scenes (hoặc `?demo=1`).
2. Thử từng kịch bản; thử tắt/bật automation.
3. Kiểm tra ở 3 độ rộng và 2 chế độ màu.

## 6. Báo cáo khi hoàn thành (bắt buộc, đúng định dạng)

```
## Báo cáo — Prompt 03
### 1. Đã làm       (mỗi file: đã thay đổi gì)
### 2. Đã kiểm tra   (từng tiêu chí nghiệm thu: đạt / không đạt + bằng chứng)
### 3. Cần xác nhận  (câu hỏi cho người dùng; ghi rõ phần nào đang bị bỏ lại vì chưa rõ)
### 4. Phát hiện ngoài phạm vi (lỗi/đề xuất bạn thấy nhưng KHÔNG sửa)
```
