# Prompt 05 — Trang Thông báo (+ huy hiệu chưa đọc)

> **Điều kiện tiên quyết:** prompt 01 đã hoàn thành. Trước khi làm, kiểm tra `FE/js/nav.js` tồn tại, `FE/index.html` có `<aside id="sidebar">`, nút chuông trên thanh trên và `<section class="page" id="page-alerts">`. **Nếu thiếu: dừng lại và báo cáo, không tự làm thay prompt 01.**

## 0. Quy tắc bắt buộc (đọc kỹ trước khi làm)

1. **Chỉ làm đúng những gì prompt này yêu cầu.** Không thêm tính năng, không "tiện tay" sửa chỗ khác, không tối ưu hay refactor ngoài phạm vi.
2. **Chỉ được sửa/tạo các file nêu ở mục 2 "Phạm vi file".** Mọi file khác — đặc biệt `BE/**`, `FE/js/app.js`, `FE/mock/demo.js`, `FE/css/style.css`, `docker-compose*.yml`, `.github/**`, các file `.md` — là **CẤM SỬA**, kể cả khi bạn thấy lỗi hoặc có cách làm hay hơn.
3. **Không sửa logic hiện có.** Giữ nguyên id phần tử, tên hàm, topic MQTT, định dạng payload và hành vi của dashboard (kể cả thông báo nổi `toast`). Có thể di chuyển phần tử nhưng **không đổi/xóa id và class**.
4. **Màu sắc giữ nguyên như đang áp dụng.** Chỉ dùng các biến CSS đã có trong `FE/css/style.css` (đặc biệt `--bad`, `--warn`, `--ok`, `--hum`, `--accent` đang dùng cho viền các mức độ cảnh báo). Không thêm giá trị màu mới, không đổi giá trị biến, không đổi font. Chế độ sáng/tối phải chạy như cũ. Wireframe chỉ là bố cục thuần xám: **không lấy màu từ wireframe**.
5. **Khi có thắc mắc, mâu thuẫn hoặc phải làm việc ngoài phạm vi: KHÔNG tự đoán, KHÔNG tự quyết theo ý mình.** Nếu điều đó chặn cả công việc thì dừng lại và hỏi người dùng. Nếu chỉ chặn một phần thì bỏ qua phần đó, làm phần còn lại và ghi câu hỏi vào mục "Cần xác nhận" của báo cáo.
6. Không cài thư viện, không thêm CDN/script ngoài, không đổi tên hay di chuyển file, không `git commit`/`git push`.
7. Nếu phải bật/tắt dịch vụ để kiểm tra, trả về đúng trạng thái ban đầu khi xong.

## 1. Bối cảnh

`app.js` ghi thông báo vào `#alerts` bằng hàm `addAlert`: mỗi thông báo là `<li class="<level>"><time>HH:MM:SS</time>nội dung</li>` thêm vào **đầu** danh sách (tối đa 80 dòng), với lớp mức độ là một trong: `bad` (nghiêm trọng, ứng với `critical` của automation), `warn`, `ok`, `info`, `rule` (xem `.alerts li.*` trong `style.css`; dòng trống dùng `.muted`). Cùng lúc `toast()` hiện thông báo nổi 6 giây (giữ nguyên). Nút `#alertClear` xóa danh sách. Khi chưa có thông báo, `#alerts` chứa một `<li class="muted">Chưa có thông báo.</li>`.

Tham chiếu bắt buộc: **wireframe** `FE/layout/sidebar_wireframe.html` (mục 1 — huy hiệu đỏ ở mục "Thông báo" và chuông trên thanh trên; mục 4, hàng "Thông báo": "danh sách cảnh báo; huy hiệu đỏ khi có critical chưa đọc").

## 2. Phạm vi file

| Việc | File |
|---|---|
| Được **sửa** | `FE/js/nav.js` (chỉ phần huy hiệu/đếm chưa đọc), `FE/layout/sidebar.css`, `FE/layout/layout.css`, `FE/index.html` (chỉ phần bên trong `#page-alerts` và nút chuông) |
| Chỉ **đọc** | `FE/js/app.js`, `FE/css/style.css`, wireframe |
| **CẤM** | mọi file còn lại |

## 3. Yêu cầu

**3.1. Bố cục trang** theo wireframe: một `.panel` rộng toàn chiều ngang với tiêu đề "Thông báo" và nút `#alertClear` (giữ id, giữ hành vi); danh sách không còn giới hạn chiều cao 340px kiểu khung nhỏ — hiển thị theo cuộn của trang (chỉ đổi bằng CSS trong phạm vi `#page-alerts`). Mỗi dòng giữ nguyên nội dung và màu viền theo mức độ.

**3.2. Đếm thông báo chưa đọc** (làm trong `nav.js`, **chỉ bằng quan sát DOM**):
- Dùng `MutationObserver` trên `#alerts` (`childList`). Mỗi `<li>` mới được thêm mà **không** phải `.muted` và **không** phải mức `rule` thì tính là 1 thông báo chưa đọc **khi người dùng không đang ở trang `#/alerts`**.
- Khi vào `#/alerts`: đặt số chưa đọc về 0. Khi bấm `#alertClear`: đặt về 0.
- Hiển thị số trên `[data-badge="alerts"]` ở sidebar và trên nút chuông thanh trên (giới hạn hiển thị `99+`, ẩn khi 0).
- Nếu trong số chưa đọc có ít nhất một dòng mức nghiêm trọng (lớp `bad`), huy hiệu dùng kiểu **cảnh báo** (nền `--bad`); ngược lại dùng kiểu thường của huy hiệu sidebar. Dùng đúng biến màu có sẵn.
- Số chưa đọc chỉ lưu trong bộ nhớ trang (không dùng `localStorage`), F5 thì về 0.

**3.3. Chuông thanh trên:** bấm → `#/alerts`. Có `aria-label` nêu số chưa đọc (ví dụ "Thông báo, 2 chưa đọc").

**3.4. Trạng thái trống:** dòng "Chưa có thông báo." căn giữa, rõ ràng.

**3.5. Responsive:** mobile — giờ (`<time>`) và nội dung xuống dòng gọn, không tràn ngang.

### Điểm CHƯA được chốt — KHÔNG tự làm, ghi vào "Cần xác nhận"
- Lưu thông báo qua F5 (hiện chỉ có trong bộ nhớ trang).
- Lọc theo mức độ, nút "Đánh dấu đã đọc" riêng, âm thanh/rung khi có cảnh báo.
- Tích hợp Telegram/Email trên giao diện (notifier chạy phía `BE/`, không thuộc phạm vi này).

## 4. Tiêu chí nghiệm thu

- [ ] Khi đang ở trang khác, bấm **Rò rỉ gas** (Nhà bếp → "Rò rỉ gas"): huy hiệu sidebar và chuông tăng, ở kiểu cảnh báo (đỏ). Có thể sẽ tăng 2 (cảnh báo gas của thiết bị và cảnh báo của automation) — ghi lại số thực tế vào báo cáo, không "chỉnh" cho ra 1.
- [ ] Vào `#/alerts`: số về 0, danh sách hiện thông báo mới nhất ở trên cùng, đúng giờ và màu viền theo mức.
- [ ] Bấm **Xóa**: danh sách trống với dòng "Chưa có thông báo."; số về 0.
- [ ] Thông báo `rule` (kiểu "Luật … đã chạy") **không** làm tăng số chưa đọc.
- [ ] Thông báo nổi (toast) hoạt động như trước.
- [ ] Hiển thị đúng ở 1280px, 900px, 420px; màu sáng/tối không đổi; Console không lỗi.
- [ ] `git diff --stat` chỉ gồm file ở mục 2.

## 5. Cách kiểm tra

1. `docker compose up -d`, `python BE/run_simulator.py`, `python BE/run_automation.py`; mở http://localhost:8080/#/home (hoặc `?demo=1`).
2. Ở trang Tổng quan, chạy một kịch bản và kích hoạt gas để tạo thông báo; theo dõi huy hiệu; vào trang Thông báo; thử Xóa.
3. Kiểm tra ở 3 độ rộng và 2 chế độ màu.

## 6. Báo cáo khi hoàn thành (bắt buộc, đúng định dạng)

```
## Báo cáo — Prompt 05
### 1. Đã làm       (mỗi file: đã thay đổi gì)
### 2. Đã kiểm tra   (từng tiêu chí nghiệm thu: đạt / không đạt + bằng chứng)
### 3. Cần xác nhận  (câu hỏi cho người dùng; ghi rõ phần nào đang bị bỏ lại vì chưa rõ)
### 4. Phát hiện ngoài phạm vi (lỗi/đề xuất bạn thấy nhưng KHÔNG sửa)
```
