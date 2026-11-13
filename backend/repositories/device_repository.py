"""Danh mục phòng, loại thiết bị và thiết bị đã đăng ký (PostgreSQL)."""
from __future__ import annotations

from backend.repositories.postgres import connection

DEVICE_SELECT = """
    SELECT d.id, r.code AS room, r.name AS room_name, d.code, d.name,
           d.type_code AS type, t.name AS type_name, d.is_simulated,
           r.code || '/' || d.code AS key
    FROM devices d
    JOIN rooms r ON r.id = d.room_id
    JOIN device_types t ON t.code = d.type_code
"""


def list_devices() -> list[dict]:
    with connection() as con:
        return con.execute(DEVICE_SELECT + " ORDER BY r.id, d.id").fetchall()


def get_device(device_id: int) -> dict | None:
    with connection() as con:
        return con.execute(DEVICE_SELECT + " WHERE d.id = %s", (device_id,)).fetchone()


def device_keys() -> set[str]:
    with connection() as con:
        rows = con.execute("SELECT r.code || '/' || d.code AS key FROM devices d JOIN rooms r ON r.id = d.room_id")
        return {row["key"] for row in rows.fetchall()}


def list_rooms() -> list[dict]:
    with connection() as con:
        return con.execute("SELECT code, name FROM rooms ORDER BY id").fetchall()


def list_types() -> list[dict]:
    with connection() as con:
        return con.execute("SELECT code, name FROM device_types ORDER BY name").fetchall()


def find_by_key(room: str, code: str) -> dict | None:
    with connection() as con:
        return con.execute(DEVICE_SELECT + " WHERE r.code = %s AND d.code = %s", (room, code)).fetchone()


def create_device(room: str, code: str, name: str, type_code: str, is_simulated: bool) -> int:
    with connection() as con:
        row = con.execute(
            "INSERT INTO devices (room_id, code, name, type_code, is_simulated) "
            "SELECT id, %s, %s, %s, %s FROM rooms WHERE code = %s RETURNING id",
            (code, name, type_code, is_simulated, room)).fetchone()
        return row["id"]


def update_device(device_id: int, room: str, code: str, name: str, type_code: str, is_simulated: bool) -> None:
    with connection() as con:
        con.execute(
            "UPDATE devices SET room_id = (SELECT id FROM rooms WHERE code = %s), code = %s, name = %s, "
            "type_code = %s, is_simulated = %s WHERE id = %s",
            (room, code, name, type_code, is_simulated, device_id))


def delete_device(device_id: int) -> None:
    with connection() as con:
        con.execute("DELETE FROM devices WHERE id = %s", (device_id,))

