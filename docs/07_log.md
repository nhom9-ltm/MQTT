# Prompt 07 — Trang Message log

> **Điều kiện tiên quyết:** prompt 01 đã hoàn thành. Trước khi làm, kiểm tra `frontend/js/nav.js` tồn tại, `frontend/index.html` có `<aside id="sidebar">` và `<section class="page" id="page-log">`. **Nếu thiếu: dừng lại và báo cáo, không tự làm thay prompt 01.**

## 0. Quy tắc bắt buộc (đọc kỹ trước khi làm)

1. **Chỉ làm đúng những gì prompt này yêu cầu.** Không thêm tính năng, không "tiện tay" sửa chỗ khác, không tối ưu hay refactor ngoài phạm vi.
2. **Chỉ được sửa/tạo các file nêu ở mục 2 "Phạm vi file".** Mọi file khác — đặc biệt `backend/**`, `frontend/js/app.js`, `frontend/mock/demo.js`, `frontend/css/style.css`, `docker-compose*.yml`, `.github/**`, các file `.md` — là **CẤM SỬA**, kể cả khi bạn thấy lỗi hoặc có cách làm hay hơn.
3. **Không sửa logic hiện có.** Giữ nguyên id phần tử, tên hàm, topic MQTT, định dạng payload và hành vi lọc/tạm dừng/giới hạn 250 dòng của log. Có thể di chuyển phần tử nhưng **không đổi/xóa id và class** (`.log`, `tr.status`, `tr.set`, `tr.event`, `tr.lwt`, `tr.sys`, `td.topic`, `td.payload`, `.yes`).
4. **Màu sắc giữ nguyên như đang áp dụng.** Màu chữ topic theo loại (`status`, `set`, `event`, `lwt`, `sys`) trong `style.css` giữ nguyên; chỉ dùng biến CSS sẵn có. Không thêm giá trị màu mới, không đổi giá trị biến, không đổi font. Chế độ sáng/tối phải chạy như cũ. Wireframe chỉ là bố cục thuần xám: **không lấy màu từ wireframe**.
5. **Khi có thắc mắc, mâu thuẫn hoặc phải làm việc ngoài phạm vi: KHÔNG tự đoán, KHÔNG tự quyết theo ý mình.** Nếu điều đó chặn cả công việc thì dừng lại và hỏi người dùng. Nếu chỉ chặn một phần thì bỏ qua phần đó, làm phần còn lại và ghi câu hỏi vào mục "Cần xác nhận" của báo cáo.
6. Không cài thư viện, không thêm CDN/script ngoài, không đổi tên hay di chuyển file, không `git commit`/`git push`.
7. Nếu phải bật/tắt dịch vụ để kiểm tra, trả về đúng trạng thái ban đầu khi xong.

## 1. Bối cảnh

Trang **Message log** (`#/log`) là bảng theo dõi mọi message MQTT dashboard nhận được, dùng khi thuyết trình để cho khán giả thấy lệnh `…/set` rồi đến `…/state`, cột Retain, QoS, LWT. `app.js` (hàm `logMessage`) thêm mỗi message thành một `<tr>` vào **đầu** `#logBody` (tối đa 250 dòng), gồm 5 cột: Giờ, Topic, QoS, Retain, Payload. Công cụ trên đầu panel: `#logFilter` (lọc topic), `#logHideState` (ẩn state & $SYS), `#logPause` (tạm dừng), `#logClear` (xóa). Khung bảng hiện bị giới hạn chiều cao 300px (`.log-wrap`) và cuộn bên trong.

Tham chiếu bắt buộc: **wireframe** `frontend/layout/sidebar_wireframe.html` (mục 4, hàng "Message log": "bảng topic/QoS/Retain, ô lọc, ẩn state, tạm dừng — dành cho phần thuyết trình MQTT").

## 2. Phạm vi file

| Việc | File |
|---|---|
| Được **sửa** | `frontend/layout/layout.css`, `frontend/index.html` (chỉ phần bên trong `#page-log`) |
| Chỉ **đọc** | `frontend/js/app.js`, `frontend/js/nav.js`, `frontend/css/style.css`, `frontend/layout/sidebar.css`, wireframe |
| **CẤM** | mọi file còn lại |

## 3. Yêu cầu

**3.1. Bố cục trang** theo wireframe: một `.panel` rộng toàn chiều ngang; hàng công cụ (`#logFilter`, hai ô chọn, nút Xóa) nằm cùng hàng với tiêu đề trên desktop và xuống dòng gọn trên mobile.

**3.2. Khung bảng dùng hết chiều cao còn lại** của màn hình: thay giới hạn cố định 300px bằng chiều cao co theo cửa sổ (ví dụ `calc(100vh - …)` tính theo thanh trên và chân trang; chỉ đặt trong phạm vi `#page-log`). Bảng cuộn **bên trong khung**, tiêu đề cột (`thead th`) cố định khi cuộn như hiện tại.

**3.3. Bảng:** giữ nguyên 5 cột và thứ tự; font mono như cũ; cột Payload vẫn cắt bằng dấu "…" và xem đầy đủ bằng `title`. Trên mobile cho phép cuộn ngang bên trong khung bảng (không làm tràn cả trang).

**3.4. Chân trang LWT/keep-alive** (`.foot`) giữ nguyên nội dung và id (`#dashWill`, `#kaInfo`), hiển thị bên dưới như các trang khác.

**3.5.** Message vẫn được ghi vào log **khi người dùng đang ở trang khác** (log là dữ liệu nền): không được dùng cách nào làm `app.js` ngừng ghi (ví dụ tháo `#logBody` khỏi DOM). Ẩn trang bằng CSS là đủ.

### Điểm CHƯA được chốt — KHÔNG tự làm, ghi vào "Cần xác nhận"
- Huy hiệu số message mới trên mục "Message log" của sidebar.
- Xuất log ra CSV/sao chép, tô sáng dòng mới, lọc theo QoS/Retain, tăng/giảm giới hạn 250 dòng.
- Gộp các thông tin $SYS (số client, message/phút) vào trang này.

## 4. Tiêu chí nghiệm thu

- [ ] Vào `#/log` khi hệ thống đang chạy: dòng mới xuất hiện liên tục ở đầu bảng.
- [ ] Bấm **bật/tắt đèn** ở trang Thiết bị rồi vào log: thấy `…/set` (màu cũ) rồi `…/state` ngay sau đó, cột QoS và Retain đúng.
- [ ] Lọc `living/light` chỉ còn các dòng chứa chuỗi đó; "Ẩn state & $SYS" ẩn đúng; "Tạm dừng" dừng ghi và bật lại thì ghi tiếp; "Xóa" xóa sạch.
- [ ] Bấm **Mất điện** một thiết bị: dòng `status` offline LWT có màu như trước.
- [ ] Rời trang log rồi quay lại: các dòng phát sinh trong lúc rời vẫn có mặt.
- [ ] Bảng cuộn trong khung; tiêu đề cột cố định; mobile cuộn ngang trong khung, trang không bị tràn ngang.
- [ ] Màu sáng/tối không đổi; Console không lỗi; `git diff --stat` chỉ gồm file ở mục 2.

## 5. Cách kiểm tra

1. `docker compose up -d`, `python backend/run_simulator.py`, `python backend/run_automation.py`; mở http://localhost:8080/#/log (hoặc `?demo=1`).
2. Thao tác ở trang Thiết bị và Kịch bản để sinh message, rồi quay lại log đối chiếu.
3. Kiểm tra ở 1280px, 900px, 420px và hai chế độ màu.

## 6. Báo cáo khi hoàn thành (bắt buộc, đúng định dạng)

```
## Báo cáo — Prompt 07
### 1. Đã làm       (mỗi file: đã thay đổi gì)
### 2. Đã kiểm tra   (từng tiêu chí nghiệm thu: đạt / không đạt + bằng chứng)
### 3. Cần xác nhận  (câu hỏi cho người dùng; ghi rõ phần nào đang bị bỏ lại vì chưa rõ)
### 4. Phát hiện ngoài phạm vi (lỗi/đề xuất bạn thấy nhưng KHÔNG sửa)
```
