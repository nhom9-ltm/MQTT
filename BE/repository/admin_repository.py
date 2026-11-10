"""Truy vấn chỉ đọc cho trang quản trị (PostgreSQL)."""
from __future__ import annotations

from BE.repository.postgres import connection


def overview() -> dict:
    with connection() as con:
        return con.execute("""
            SELECT
              (SELECT count(*) FROM users)                                    AS users_total,
              (SELECT count(*) FROM users u JOIN roles r ON r.id = u.role_id
                WHERE r.code = 'admin')                                       AS users_admin,
              (SELECT count(*) FROM rooms)                                    AS rooms_total,
              (SELECT count(*) FROM devices)                                  AS devices_total,
              (SELECT count(*) FROM devices WHERE is_simulated)               AS devices_simulated,
              (SELECT count(*) FROM automation_rules)                         AS rules_total,
              (SELECT count(*) FROM scenes)                                   AS scenes_total,
              (SELECT count(*) FROM sessions WHERE expires_at > now())        AS sessions_active,
              (SELECT count(*) FROM login_history
                WHERE success AND created_at > now() - interval '24 hours')   AS logins_ok_24h,
              (SELECT count(*) FROM login_history
                WHERE NOT success AND created_at > now() - interval '24 hours') AS logins_failed_24h
        """).fetchone()


def users() -> list[dict]:
    with connection() as con:
        return con.execute("""
            SELECT u.id, u.email, u.full_name, r.code AS role, r.name AS role_name, u.is_active,
                   u.created_at, u.last_login_at
            FROM users u JOIN roles r ON r.id = u.role_id
            ORDER BY u.id
        """).fetchall()


def devices_by_room() -> list[dict]:
    with connection() as con:
        return con.execute("""
            SELECT r.code, r.name, count(d.id) AS total,
                   count(d.id) FILTER (WHERE d.is_simulated) AS simulated
            FROM rooms r LEFT JOIN devices d ON d.room_id = r.id
            GROUP BY r.id, r.code, r.name
            ORDER BY r.id
        """).fetchall()


def login_history(limit: int) -> list[dict]:
    with connection() as con:
        return con.execute("""
            SELECT id, email, success, ip_address, created_at
            FROM login_history ORDER BY created_at DESC, id DESC LIMIT %s
        """, (limit,)).fetchall()
