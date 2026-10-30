# Hướng dẫn cho thành viên nhóm 9

Tài liệu này dành cho các bạn mới tham gia dự án: cách lấy code về, cách chạy trên máy mình (không cần
Docker), và cách cùng làm việc trên repo [nhom9-ltm/MQTT](https://github.com/nhom9-ltm/MQTT) mà không
giẫm chân nhau. Chi tiết kỹ thuật (kiến trúc, topic, luật tự động, ESP32) xem [README.md](README.md).

---

## 1. Được quyền ghi vào repo

1. Tạo tài khoản GitHub (nếu chưa có) và gửi **username** cho người quản lý repo.
2. Người quản lý vào **github.com/nhom9-ltm** → **People** → **Invite member** (hoặc trong repo:
   **Settings → Collaborators and teams → Add people**), chọn quyền **Write**.
3. Mở email (hoặc <https://github.com/notifications>) và **chấp nhận lời mời**. Chưa chấp nhận thì chưa
   push được.
4. Cài [Git](https://git-scm.com/download/win), rồi khai báo tên/email **trùng với tài khoản GitHub**:

   ```powershell
   git config --global user.name  "ten-github-cua-ban"
   git config --global user.email "email-github-cua-ban@gmail.com"
   ```

5. Lấy code về:

   ```powershell
   git clone https://github.com/nhom9-ltm/MQTT.git
   cd MQTT
   ```

   Lần push đầu tiên Git sẽ mở cửa sổ đăng nhập GitHub trên trình duyệt — đăng nhập là xong.

---

## 2. Cài đặt và chạy dự án

Toàn bộ các bước (cài Python, Mosquitto, chạy 5 thành phần, kiểm tra, lỗi hay gặp, chạy chung nhiều máy)
nằm trong **[CACH_CHAY.md](CACH_CHAY.md)**. Làm theo mục **A** nếu máy không có Docker.

---

## 3. Quy trình làm việc chung trên Git

Repo dùng chung, nên mỗi người **làm trên nhánh riêng** rồi gộp vào `main` qua **Pull Request**.

```powershell
# Trước khi bắt đầu làm: lấy code mới nhất
git checkout main
git pull

# Tạo nhánh cho phần việc của mình
git checkout -b ten-ban/ten-tinh-nang        # ví dụ: thong/esp32-dht22

# ... sửa code, chạy thử ...

git add <file đã sửa>
git commit -m "Mô tả ngắn điều đã làm"
git push -u origin ten-ban/ten-tinh-nang
```

Sau đó lên GitHub bấm **Compare & pull request**, nhờ một bạn khác xem rồi **Merge**.

**Quy tắc:**

- **Không** `git push --force` lên `main` — sẽ xóa mất code của người khác.
- Luôn `git pull` trước khi bắt đầu làm để tránh xung đột.
- **Không** commit file bí mật hay file sinh ra khi chạy: `secrets.h`, `.env`, `*.db`, `*.csv`,
  `broker/data/` (đã có trong `.gitignore`, chỉ cần đừng `git add -f`).
- Bị xung đột (conflict) khi pull/merge mà không chắc cách sửa → hỏi nhóm trước, đừng xóa bừa.

### Ai làm phần nào

Mỗi thành phần nằm trong một thư mục riêng và chỉ nói chuyện với nhau qua broker, nên có thể chia việc
theo thư mục mà ít khi đụng nhau:

| Thư mục | Nội dung |
|---|---|
| `dashboard/` | Giao diện web (HTML/CSS/JS, MQTT.js) |
| `devices/` | Thiết bị giả lập bằng Python |
| `automation/` | Luật tự động (`rules.json`) và kịch bản (`scenes.json`) |
| `logger/` | Lưu lịch sử vào SQLite, xuất báo cáo/CSV |
| `esp32/` | Code Arduino cho mạch ESP32 thật |
| `broker/` | Cấu hình Mosquitto, phân quyền (ACL) |

Thống nhất trong nhóm ai phụ trách thư mục nào; khi cần đổi **tên topic** hay **định dạng JSON** thì báo
cả nhóm, vì mọi thành phần đều phụ thuộc vào đó (xem [README § 4](README.md#4-thiết-kế-topic)).
