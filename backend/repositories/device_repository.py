"""Danh mục phòng, loại thiết bị và thiết bị đã đăng ký (PostgreSQL)."""
from __future__ import annotations

from backend.repositories.postgres import connection

DEVICE_SELECT = """
    SELECT d.id, r.code AS room, r.name AS room_name, d.code, d.name,
           d.type_code AS type, t.name AS type_name, d.is_simulated, d.is_active,
           d.created_by, c.email AS created_by_email, d.created_at,
           d.house_id, h.address AS house_address,
           r.code || '/' || d.code AS key
    FROM devices d
    JOIN rooms r ON r.id = d.room_id
    JOIN device_types t ON t.code = d.type_code
    LEFT JOIN users c ON c.id = d.created_by
    LEFT JOIN houses h ON h.id = d.house_id
"""


def list_devices() -> list[dict]:
    with connection() as con:
        return con.execute(DEVICE_SELECT + " ORDER BY r.id, d.id").fetchall()


def get_device(device_id: int) -> dict | None:
    with connection() as con:
        return con.execute(DEVICE_SELECT + " WHERE d.id = %s", (device_id,)).fetchone()


def device_keys(house_id: int | None = None) -> set[str]:
    """Khóa "phòng/mã" của mọi thiết bị, hoặc chỉ thiết bị thuộc một địa chỉ nhà."""
    with connection() as con:
        rows = con.execute("SELECT r.code || '/' || d.code AS key FROM devices d JOIN rooms r ON r.id = d.room_id "
                           "WHERE %s::int IS NULL OR d.house_id = %s", (house_id, house_id))
        return {row["key"] for row in rows.fetchall()}


def locked_keys() -> list[str]:
    """Các thiết bị đang bị khóa, dạng "phòng/mã"."""
    with connection() as con:
        rows = con.execute("SELECT r.code || '/' || d.code AS key FROM devices d JOIN rooms r ON r.id = d.room_id "
                           "WHERE NOT d.is_active ORDER BY 1")
        return [row["key"] for row in rows.fetchall()]


def list_rooms() -> list[dict]:
    with connection() as con:
        return con.execute("SELECT code, name FROM rooms ORDER BY id").fetchall()


def list_types() -> list[dict]:
    with connection() as con:
        return con.execute("SELECT code, name FROM device_types ORDER BY name").fetchall()


def find_by_key(room: str, code: str) -> dict | None:
    with connection() as con:
        return con.execute(DEVICE_SELECT + " WHERE r.code = %s AND d.code = %s", (room, code)).fetchone()


def create_device(room: str, code: str, name: str, type_code: str, is_simulated: bool, is_active: bool,
                  created_by: int | None, house_id: int) -> int:
    with connection() as con:
        row = con.execute(
            "INSERT INTO devices (room_id, code, name, type_code, is_simulated, is_active, created_by, house_id) "
            "SELECT id, %s, %s, %s, %s, %s, %s, %s FROM rooms WHERE code = %s RETURNING id",
            (code, name, type_code, is_simulated, is_active, created_by, house_id, room)).fetchone()
        return row["id"]


def update_device(device_id: int, room: str, code: str, name: str, type_code: str, is_simulated: bool,
                  is_active: bool, house_id: int) -> None:
    with connection() as con:
        con.execute(
            "UPDATE devices SET room_id = (SELECT id FROM rooms WHERE code = %s), code = %s, name = %s, "
            "type_code = %s, is_simulated = %s, is_active = %s, house_id = %s WHERE id = %s",
            (room, code, name, type_code, is_simulated, is_active, house_id, device_id))


def set_active(device_id: int, is_active: bool) -> None:
    with connection() as con:
        con.execute("UPDATE devices SET is_active = %s WHERE id = %s", (is_active, device_id))


def delete_device(device_id: int) -> None:
    with connection() as con:
        con.execute("DELETE FROM devices WHERE id = %s", (device_id,))


# ---------------- thiết bị người dùng đã kết nối ----------------
def find_in_house(house_id: int, code: str) -> list[dict]:
    """Thiết bị thuộc một nhà có mã `code` (vd "light") hoặc khóa đầy đủ "phòng/mã" (vd "living/light")."""
    with connection() as con:
        return con.execute(DEVICE_SELECT + " WHERE d.house_id = %s AND (d.code = %s OR r.code || '/' || d.code = %s) "
                           "ORDER BY r.id, d.id", (house_id, code, code)).fetchall()


def connect_user(user_id: int, device_id: int) -> bool:
    """Ghi nhận kết nối; trả False nếu thiết bị đã được kết nối với tài khoản này từ trước."""
    with connection() as con:
        return con.execute("INSERT INTO user_devices (user_id, device_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                           (user_id, device_id)).rowcount > 0


def connected_devices(user_id: int) -> list[dict]:
    with connection() as con:
        return con.execute(DEVICE_SELECT.replace("SELECT d.id,", "SELECT ud.connected_at, d.id,")
                           + " JOIN user_devices ud ON ud.device_id = d.id WHERE ud.user_id = %s ORDER BY ud.connected_at DESC",
                           (user_id,)).fetchall()


def connected_users(device_id: int) -> list[dict]:
    with connection() as con:
        return con.execute("SELECT u.id, u.email, u.full_name, ud.connected_at FROM user_devices ud "
                           "JOIN users u ON u.id = ud.user_id WHERE ud.device_id = %s AND u.deleted_at IS NULL "
                           "ORDER BY ud.connected_at", (device_id,)).fetchall()
