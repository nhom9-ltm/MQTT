# Prompt 04 — Trang Luật tự động

> **Điều kiện tiên quyết:** prompt 01 đã hoàn thành. Trước khi làm, kiểm tra `FE/js/nav.js` tồn tại, `FE/index.html` có `<aside id="sidebar">` và `<section class="page" id="page-rules">`. **Nếu thiếu: dừng lại và báo cáo, không tự làm thay prompt 01.**

## 0. Quy tắc bắt buộc (đọc kỹ trước khi làm)

1. **Chỉ làm đúng những gì prompt này yêu cầu.** Không thêm tính năng, không "tiện tay" sửa chỗ khác, không tối ưu hay refactor ngoài phạm vi.
2. **Chỉ được sửa/tạo các file nêu ở mục 2 "Phạm vi file".** Mọi file khác — đặc biệt `BE/**` (kể cả `BE/config/rules.json`), `FE/js/app.js`, `FE/mock/demo.js`, `FE/css/style.css`, `docker-compose*.yml`, `.github/**`, các file `.md` — là **CẤM SỬA**, kể cả khi bạn thấy lỗi hoặc có cách làm hay hơn.
3. **Không sửa logic hiện có.** Giữ nguyên id phần tử, tên hàm, topic MQTT, định dạng payload và hành vi của dashboard. Có thể di chuyển phần tử nhưng **không đổi/xóa id và class**.
4. **Màu sắc giữ nguyên như đang áp dụng.** Chỉ dùng các biến CSS đã có trong `FE/css/style.css`. Không thêm giá trị màu mới, không đổi giá trị biến, không đổi font. Chế độ sáng/tối phải chạy như cũ. Wireframe chỉ là bố cục thuần xám: **không lấy màu từ wireframe**.
5. **Khi có thắc mắc, mâu thuẫn hoặc phải làm việc ngoài phạm vi: KHÔNG tự đoán, KHÔNG tự quyết theo ý mình.** Nếu điều đó chặn cả công việc thì dừng lại và hỏi người dùng. Nếu chỉ chặn một phần thì bỏ qua phần đó, làm phần còn lại và ghi câu hỏi vào mục "Cần xác nhận" của báo cáo.
6. Không cài thư viện, không thêm CDN/script ngoài, không đổi tên hay di chuyển file, không `git commit`/`git push`.
7. Nếu phải bật/tắt dịch vụ để kiểm tra, trả về đúng trạng thái ban đầu khi xong. **Bật/tắt luật khi kiểm tra sẽ ghi vào `BE/config/rules.json`** (đây là hành vi sẵn có của automation): sau khi kiểm tra phải bật lại đúng các luật như ban đầu và xác nhận `git status` không hiện `BE/config/rules.json` bị thay đổi.

## 1. Bối cảnh

Trang **Luật tự động** (`#/rules`) hiển thị danh sách luật do automation engine phát (retained topic `home/_auto/engine/status`). `app.js` (hàm `renderEngine`) dựng `#rules` thành các `<li>`; mỗi `<li>` có:
- công tắc `button.sw.sm[role="switch"][data-rule]` (bấm → gửi `home/_auto/rule/set`);
- tên luật `<b>`, mô tả và dòng "chạy N giây trước" (`data-ago`) trong `<small>`;
- lớp `disabled` khi luật đang tắt; công tắc bị `disabled` khi engine offline.

Có 11 luật (xem `BE/config/rules.json`, chỉ đọc). Tham chiếu bắt buộc: **wireframe** `FE/layout/sidebar_wireframe.html` (mục 4, hàng "Luật tự động": "danh sách 11 luật, công tắc bật/tắt, lần chạy gần nhất"; "chỗ thích hợp để sau này thêm trình soạn luật").

## 2. Phạm vi file

| Việc | File |
|---|---|
| Được **sửa** | `FE/js/nav.js` (chỉ phần huy hiệu luật), `FE/layout/sidebar.css`, `FE/layout/layout.css`, `FE/index.html` (chỉ phần bên trong `#page-rules`) |
| Chỉ **đọc** | `FE/js/app.js`, `FE/css/style.css`, `BE/config/rules.json`, wireframe |
| **CẤM** | mọi file còn lại |

## 3. Yêu cầu

**3.1. Bố cục trang** theo wireframe: một `.panel` rộng toàn chiều ngang vùng nội dung, tiêu đề "Luật tự động" + chú thích `BE/config/rules.json`; danh sách luật không còn bị giới hạn chiều cao 340px kiểu cuộn trong khung nhỏ — cho hiển thị đủ cả danh sách theo cuộn của trang (chỉ đổi bằng CSS trong phạm vi `#page-rules`). Giữ nguyên nội dung từng dòng (công tắc, tên, mô tả, "chạy … trước").

**3.2. Huy hiệu mục "Luật tự động"** trên sidebar: đổ vào `[data-badge="rules"]` **số luật đang bật** (đếm các `<li>` trong `#rules` không có lớp `disabled` và không phải dòng `.muted`). Ẩn khi chưa có luật. Cập nhật bằng `MutationObserver` trên `#rules`.

**3.3. Trạng thái engine offline:** giữ nguyên hành vi hiện tại (công tắc mờ/vô hiệu, dòng "Automation engine chưa chạy."). Dòng thông báo này căn giữa, rõ ràng, không bị cắt.

**3.4. Responsive:** trên mobile công tắc nằm bên trái và vùng chạm đủ lớn (≥ 44px chiều cao dòng); mô tả luật xuống dòng, không tràn ngang.

### Điểm CHƯA được chốt — KHÔNG tự làm, ghi vào "Cần xác nhận"
- Trình soạn luật (thêm/sửa/xóa luật, ô điều kiện, hành động) — wireframe chỉ ghi "sau này".
- Lọc/tìm kiếm luật, nhóm luật theo loại.
- Nút "Chạy thử luật".

## 4. Tiêu chí nghiệm thu

- [ ] Hiển thị đủ 11 luật với tên, mô tả, "chạy … trước" khi luật đã chạy.
- [ ] Bật/tắt từng luật bằng công tắc: dòng đổi trạng thái, huy hiệu sidebar thay đổi đúng, automation in ra "Luật … TẮT/BẬT". Kiểm tra xong **phục hồi trạng thái luật ban đầu**.
- [ ] Kích hoạt một luật (ví dụ **Rò rỉ gas** ở nhà bếp): dòng luật cập nhật "chạy vài giây trước".
- [ ] Tắt automation → công tắc mờ; bật lại → dùng được.
- [ ] Hiển thị đúng ở 1280px, 900px, 420px; màu sáng/tối không đổi; Console không lỗi.
- [ ] `git status` **không** hiện `BE/config/rules.json` bị sửa; `git diff --stat` chỉ gồm file ở mục 2.

## 5. Cách kiểm tra

1. `docker compose up -d`, `python BE/run_simulator.py`, `python BE/run_automation.py`; mở http://localhost:8080/#/rules (hoặc `?demo=1`, khi đó luật là bản sao trong trình duyệt và không ghi file).
2. Ghi lại trạng thái bật/tắt ban đầu của 11 luật trước khi thử.
3. Thử bật/tắt vài luật rồi phục hồi.

## 6. Báo cáo khi hoàn thành (bắt buộc, đúng định dạng)

```
## Báo cáo — Prompt 04
### 1. Đã làm       (mỗi file: đã thay đổi gì)
### 2. Đã kiểm tra   (từng tiêu chí nghiệm thu: đạt / không đạt + bằng chứng)
### 3. Cần xác nhận  (câu hỏi cho người dùng; ghi rõ phần nào đang bị bỏ lại vì chưa rõ)
### 4. Phát hiện ngoài phạm vi (lỗi/đề xuất bạn thấy nhưng KHÔNG sửa)
```
