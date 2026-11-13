#!/usr/bin/env python3
"""
Dữ liệu demo của hệ thống: tài khoản, phòng, loại thiết bị, thiết bị và kịch bản.
Đây là NƠI DUY NHẤT khai báo dữ liệu ban đầu cho PostgreSQL; schema.sql chỉ tạo bảng.

    python backend/database/seed.py     # nạp/cập nhật dữ liệu vào PostgreSQL
    python backend/run_api.py           # API cũng tự chạy seed mỗi lần khởi động

Chạy lại bao nhiêu lần cũng được:
  * Kịch bản: luôn cập nhật theo file này.
  * Vai trò: chỉ thêm nếu chưa có (tên hiển thị do quản trị viên đổi được, seed không ghi đè).
  * Tài khoản, phòng, loại thiết bị, thiết bị: chỉ nạp khi database còn trống (lần đầu). Sau đó quản trị viên
    quản lý trên trang quản trị; seed không ghi đè và không thêm lại bản ghi đã bị xóa.
    Ngoại lệ an toàn: nếu không còn quản trị viên nào hoạt động, seed khôi phục tài khoản admin bên dưới.
  * Luật tự động: dữ liệu ban đầu là backend/config/rules.json (file automation engine thực thi). Quản trị viên
    thêm/sửa/xóa luật trên trang quản trị; seed chỉ đồng bộ danh mục luật từ file đó vào database.

Mật khẩu ghi ở dạng chữ để tiện demo; khi nạp vào database chỉ lưu mã băm SHA-256.
"""
from __future__ import annotations

import hashlib
import os
import sys

if __name__ == "__main__":
    if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


# ==========================================================
#  TÀI KHOẢN
# ==========================================================
ROLES = [
    # (id, code, tên)
    (1, "admin", "Quản trị viên"),
    (2, "user",  "Người dùng"),
]

USERS = [
    # (email, mật khẩu, họ tên, vai trò)
    ("admmqtt@gmail.com", "Admin@1", "Quản trị viên", "admin"),
    ("user1@gmail.com",   "User@1",  "Người dùng 1",  "user"),
]


# ==========================================================
#  PHÒNG & THIẾT BỊ (chỉ nạp lần đầu; khớp backend/simulator/house.py và ESP32)
# ==========================================================
ROOMS = [
    # (mã, tên)
    ("living",   "Phòng khách"),
    ("bedroom",  "Phòng ngủ"),
    ("kitchen",  "Nhà bếp"),
    ("entrance", "Lối vào"),
    ("lab",      "Lab (ESP32)"),
]

DEVICE_TYPES = [
    ("climate", "Nhiệt độ & độ ẩm"),
    ("light",   "Đèn"),
    ("fan",     "Quạt"),
    ("ac",      "Điều hòa"),
    ("curtain", "Rèm"),
    ("plug",    "Ổ cắm"),
    ("lock",    "Khóa cửa"),
    ("door",    "Cảm biến cửa"),
    ("motion",  "Cảm biến chuyển động"),
    ("gas",     "Cảm biến gas"),
    ("node",    "Bo mạch"),
]

DEVICES = [
    # (phòng, mã, tên, loại, giả lập?)
    ("living",   "climate",     "Nhiệt độ & độ ẩm",     "climate", True),
    ("living",   "light",       "Đèn trần",             "light",   True),
    ("living",   "fan",         "Quạt đứng",            "fan",     True),
    ("living",   "ac",          "Điều hòa",             "ac",      True),
    ("living",   "curtain",     "Rèm cửa sổ",           "curtain", True),
    ("living",   "tv-plug",     "Ổ cắm TV",             "plug",    True),
    ("living",   "motion",      "Cảm biến chuyển động", "motion",  True),
    ("bedroom",  "climate",     "Nhiệt độ & độ ẩm",     "climate", True),
    ("bedroom",  "light",       "Đèn ngủ",              "light",   True),
    ("bedroom",  "ac",          "Điều hòa",             "ac",      True),
    ("bedroom",  "curtain",     "Rèm cửa sổ",           "curtain", True),
    ("kitchen",  "climate",     "Nhiệt độ & độ ẩm",     "climate", True),
    ("kitchen",  "light",       "Đèn bếp",              "light",   True),
    ("kitchen",  "hood-fan",    "Quạt hút mùi",         "fan",     True),
    ("kitchen",  "stove-plug",  "Bếp điện",             "plug",    True),
    ("kitchen",  "gas",         "Cảm biến khí gas",     "gas",     True),
    ("entrance", "lock",        "Khóa cửa chính",       "lock",    True),
    ("entrance", "door",        "Cảm biến cửa chính",   "door",    True),
    ("entrance", "motion",      "Cảm biến chuyển động", "motion",  True),
    ("entrance", "porch-light", "Đèn hiên",             "light",   True),
    ("lab",      "esp32-01",    "Bo mạch ESP32",        "node",    False),
    ("lab",      "climate",     "DHT22",                "climate", False),
    ("lab",      "light",       "Relay đèn",            "light",   False),
    ("lab",      "fan",         "Relay quạt",           "fan",     False),
    ("lab",      "motion",      "PIR",                  "motion",  False),
    ("lab",      "door",        "Công tắc từ",          "door",    False),
    ("lab",      "gas",         "MQ-2",                 "gas",     False),
]


# ==========================================================
#  KỊCH BẢN (danh mục; các bước chi tiết nằm ở backend/config/scenes.json, mã phải trùng "id" ở đó)
# ==========================================================
SCENES = [
    # (mã, tên, biểu tượng)
    ("home",    "Về nhà",      "🏠"),
    ("away",    "Ra khỏi nhà", "🚪"),
    ("sleep",   "Đi ngủ",      "🌙"),
    ("morning", "Buổi sáng",   "☀️"),
    ("movie",   "Xem phim",    "🎬"),
]


# ==========================================================
#  NẠP VÀO DATABASE
# ==========================================================
def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def run() -> dict:
    """Nạp dữ liệu demo vào PostgreSQL. Trả về số bản ghi mỗi loại đang có trong database."""
    from backend.repositories.postgres import connection
    from backend.services import rule_service

    role_id = {code: rid for rid, code, _ in ROLES}
    with connection() as con:
        # Nâng cấp database đã tạo từ schema cũ (trước khi có xóa mềm tài khoản)
        con.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ")
        con.cursor().executemany(
            "INSERT INTO roles (id, code, name) VALUES (%s, %s, %s) ON CONFLICT (id) DO NOTHING", ROLES)
        if con.execute("SELECT count(*) AS n FROM users").fetchone()["n"] == 0:      # lần đầu
            con.cursor().executemany(
                "INSERT INTO users (email, password_hash, full_name, role_id) VALUES (%s, %s, %s, %s)",
                [(email, sha256_hex(pw), name, role_id[role]) for email, pw, name, role in USERS])
        no_admin = con.execute("SELECT count(*) AS n FROM users u JOIN roles r ON r.id = u.role_id "
                               "WHERE r.code = 'admin' AND u.is_active AND u.deleted_at IS NULL").fetchone()["n"] == 0
        if no_admin:                # lỡ khóa/xóa hết quản trị viên → khôi phục tài khoản admin trong seed
            for email, pw, name, role in USERS:
                if role == "admin":
                    con.execute(
                        "INSERT INTO users (email, password_hash, full_name, role_id) VALUES (%s, %s, %s, %s) "
                        "ON CONFLICT (email) DO UPDATE SET password_hash = EXCLUDED.password_hash, "
                        "role_id = EXCLUDED.role_id, is_active = TRUE, deleted_at = NULL",
                        (email, sha256_hex(pw), name, role_id[role]))
                    print(f"Không còn quản trị viên hoạt động → khôi phục {email} / {pw}")

        if con.execute("SELECT count(*) AS n FROM rooms").fetchone()["n"] == 0:      # lần đầu
            con.cursor().executemany("INSERT INTO rooms (code, name) VALUES (%s, %s)", ROOMS)
            con.cursor().executemany(
                "INSERT INTO device_types (code, name) VALUES (%s, %s) ON CONFLICT (code) DO NOTHING",
                DEVICE_TYPES)
            con.cursor().executemany(
                "INSERT INTO devices (room_id, code, name, type_code, is_simulated) "
                "SELECT id, %s, %s, %s, %s FROM rooms WHERE code = %s",
                [(code, name, typ, sim, room) for room, code, name, typ, sim in DEVICES])

        con.cursor().executemany(
            "INSERT INTO scenes (code, name, icon) VALUES (%s, %s, %s) "
            "ON CONFLICT (code) DO UPDATE SET name = EXCLUDED.name, icon = EXCLUDED.icon", SCENES)

    rule_service.sync_catalog()

    with connection() as con:
        n = con.execute("SELECT (SELECT count(*) FROM users WHERE deleted_at IS NULL) AS u, (SELECT count(*) FROM rooms) AS r, "
                        "(SELECT count(*) FROM devices) AS d, (SELECT count(*) FROM automation_rules) AS l, "
                        "(SELECT count(*) FROM scenes) AS s").fetchone()
    return {"tài khoản": n["u"], "phòng": n["r"], "thiết bị": n["d"], "luật": n["l"], "kịch bản": n["s"]}


if __name__ == "__main__":
    counts = run()
    print("Đã nạp dữ liệu demo: " + ", ".join(f"{v} {k}" for k, v in counts.items()))
    for email, pw, _, role in USERS:
        print(f"  {role:<5}  {email:<20}  {pw}")
