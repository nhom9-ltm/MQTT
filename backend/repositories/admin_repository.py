"""Truy vấn chỉ đọc cho trang quản trị (PostgreSQL)."""
from __future__ import annotations

from backend.repositories.postgres import connection


def overview() -> dict:
    with connection() as con:
        return con.execute("""
            SELECT
              (SELECT count(*) FROM users WHERE deleted_at IS NULL)           AS users_total,
              (SELECT count(*) FROM users u JOIN roles r ON r.id = u.role_id
                WHERE r.code = 'admin' AND u.deleted_at IS NULL)              AS users_admin,
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


def sync_rule_catalog(rules: list[tuple[str, str, int | None]]) -> None:
    """Đồng bộ bảng automation_rules (danh mục để đếm/hiển thị) theo đúng nội dung rules.json."""
    with connection() as con:
        codes = [code for code, _, _ in rules]
        con.execute("DELETE FROM automation_rules WHERE NOT (code = ANY(%s))", (codes,))
        con.cursor().executemany(
            "INSERT INTO automation_rules (code, name, cooldown_seconds) VALUES (%s, %s, %s) "
            "ON CONFLICT (code) DO UPDATE SET name = EXCLUDED.name, cooldown_seconds = EXCLUDED.cooldown_seconds",
            rules)
