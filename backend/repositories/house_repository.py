"""Địa chỉ nhà (PostgreSQL). Địa chỉ trùng nhau không phân biệt hoa thường/khoảng trắng thừa được coi là một nhà."""
from __future__ import annotations

import re

from backend.repositories.postgres import connection


def normalize(address: str) -> str:
    return re.sub(r"\s+", " ", str(address or "")).strip()


def list_houses() -> list[dict]:
    with connection() as con:
        return con.execute("""
            SELECT h.id, h.address,
                   (SELECT count(*) FROM devices d WHERE d.house_id = h.id)                       AS devices,
                   (SELECT count(*) FROM users u WHERE u.house_id = h.id AND u.deleted_at IS NULL) AS users,
                   -- họ tên người dùng ở địa chỉ này (để hiện "Họ tên - Địa chỉ" khi chọn nhà)
                   (SELECT string_agg(u.full_name, ', ' ORDER BY u.id) FROM users u JOIN roles r ON r.id = u.role_id
                     WHERE u.house_id = h.id AND u.deleted_at IS NULL AND r.code = 'user')        AS owners
            FROM houses h ORDER BY h.id
        """).fetchall()


def ids() -> set[int]:
    with connection() as con:
        return {r["id"] for r in con.execute("SELECT id FROM houses").fetchall()}


def get_or_create(address: str) -> int:
    address = normalize(address)
    with connection() as con:
        row = con.execute("SELECT id FROM houses WHERE lower(address) = lower(%s)", (address,)).fetchone()
        if row:
            return row["id"]
        return con.execute("INSERT INTO houses (address) VALUES (%s) RETURNING id", (address,)).fetchone()["id"]
