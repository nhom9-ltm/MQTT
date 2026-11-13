"""Truy vấn tài khoản, phiên đăng nhập và nhật ký đăng nhập (PostgreSQL)."""
from __future__ import annotations

from backend.repositories.postgres import connection

USER_COLUMNS = "u.id, u.email, u.full_name, r.code AS role"


def find_user_by_email(email: str) -> dict | None:
    with connection() as con:
        return con.execute(
            f"SELECT {USER_COLUMNS}, u.password_hash, u.is_active "
            "FROM users u JOIN roles r ON r.id = u.role_id WHERE u.email = %s AND u.deleted_at IS NULL",
            (email,),
        ).fetchone()


def record_login(email: str, user_id: int | None, success: bool, ip: str | None) -> None:
    with connection() as con:
        con.execute("INSERT INTO login_history (email, user_id, success, ip_address) VALUES (%s, %s, %s, %s)",
                    (email, user_id, success, ip))


def create_session(user_id: int, token_hash: str, ttl_hours: int) -> None:
    """Tạo phiên mới, dọn các phiên đã hết hạn và ghi lại thời điểm đăng nhập."""
    with connection() as con:
        con.execute("DELETE FROM sessions WHERE expires_at <= now()")
        con.execute("INSERT INTO sessions (token_hash, user_id, expires_at) "
                    "VALUES (%s, %s, now() + make_interval(hours => %s))",
                    (token_hash, user_id, ttl_hours))
        con.execute("UPDATE users SET last_login_at = now() WHERE id = %s", (user_id,))


def find_session_user(token_hash: str) -> dict | None:
    with connection() as con:
        return con.execute(
            f"SELECT {USER_COLUMNS} FROM sessions s "
            "JOIN users u ON u.id = s.user_id JOIN roles r ON r.id = u.role_id "
            "WHERE s.token_hash = %s AND s.expires_at > now() AND u.is_active AND u.deleted_at IS NULL",
            (token_hash,),
        ).fetchone()


def delete_session(token_hash: str) -> None:
    with connection() as con:
        con.execute("DELETE FROM sessions WHERE token_hash = %s", (token_hash,))
