"""Quản lý tài khoản và vai trò cho trang quản trị (PostgreSQL).

Xóa tài khoản là XÓA MỀM: đặt deleted_at, tài khoản bị ẩn khỏi mọi danh sách/số liệu và không đăng nhập được;
bản ghi vẫn còn để giữ lịch sử. Mọi truy vấn ở đây chỉ xét tài khoản chưa xóa (deleted_at IS NULL).
"""
from __future__ import annotations

from backend.repositories.postgres import connection

USER_SELECT = """
    SELECT u.id, u.email, u.full_name, r.code AS role, r.name AS role_name, u.is_active,
           u.created_at, u.last_login_at
    FROM users u JOIN roles r ON r.id = u.role_id
    WHERE u.deleted_at IS NULL
"""


def list_users(q: str = "", role: str = "", status: str = "") -> list[dict]:
    """q: tìm theo email hoặc họ tên (không phân biệt hoa thường); role: mã vai trò; status: active | locked."""
    where, params = [""], []
    if q:
        where.append("(u.email ILIKE %s OR u.full_name ILIKE %s)")
        params += [f"%{q}%", f"%{q}%"]
    if role:
        where.append("r.code = %s")
        params.append(role)
    if status in ("active", "locked"):
        where.append("u.is_active = %s")
        params.append(status == "active")
    sql = USER_SELECT + " AND ".join(where) + " ORDER BY u.id"
    with connection() as con:
        return con.execute(sql, params).fetchall()


def get_user(user_id: int) -> dict | None:
    with connection() as con:
        return con.execute(USER_SELECT + " AND u.id = %s", (user_id,)).fetchone()


def email_taken(email: str, except_id: int | None = None) -> bool:
    """Email đã thuộc tài khoản khác chưa xóa."""
    with connection() as con:
        row = con.execute("SELECT 1 FROM users WHERE email = %s AND id IS DISTINCT FROM %s AND deleted_at IS NULL",
                          (email, except_id)).fetchone()
        return row is not None


def deleted_id_by_email(email: str) -> int | None:
    """Id tài khoản đã xóa mềm đang giữ email này (email là UNIQUE nên tạo lại phải dùng lại bản ghi đó)."""
    with connection() as con:
        row = con.execute("SELECT id FROM users WHERE email = %s AND deleted_at IS NOT NULL", (email,)).fetchone()
        return row["id"] if row else None


def count_active_admins(except_id: int | None = None) -> int:
    with connection() as con:
        return con.execute(
            "SELECT count(*) AS n FROM users u JOIN roles r ON r.id = u.role_id "
            "WHERE r.code = 'admin' AND u.is_active AND u.deleted_at IS NULL AND u.id IS DISTINCT FROM %s",
            (except_id,)).fetchone()["n"]


def create_user(email: str, password_hash: str, full_name: str, role: str, is_active: bool) -> int:
    with connection() as con:
        revived = con.execute(                 # email từng thuộc tài khoản đã xóa → dùng lại bản ghi đó
            "UPDATE users SET password_hash = %s, full_name = %s, role_id = (SELECT id FROM roles WHERE code = %s), "
            "is_active = %s, deleted_at = NULL, created_at = now(), last_login_at = NULL "
            "WHERE email = %s AND deleted_at IS NOT NULL RETURNING id",
            (password_hash, full_name, role, is_active, email)).fetchone()
        if revived:
            return revived["id"]
        return con.execute(
            "INSERT INTO users (email, password_hash, full_name, role_id, is_active) "
            "SELECT %s, %s, %s, id, %s FROM roles WHERE code = %s RETURNING id",
            (email, password_hash, full_name, is_active, role)).fetchone()["id"]


def update_user(user_id: int, email: str, full_name: str, role: str, is_active: bool,
                password_hash: str | None) -> None:
    """Đổi mật khẩu hoặc khóa tài khoản thì xóa luôn các phiên đang mở để người đó phải đăng nhập lại."""
    with connection() as con:
        con.execute(
            "UPDATE users SET email = %s, full_name = %s, role_id = (SELECT id FROM roles WHERE code = %s), "
            "is_active = %s, password_hash = COALESCE(%s, password_hash) WHERE id = %s AND deleted_at IS NULL",
            (email, full_name, role, is_active, password_hash, user_id))
        if password_hash or not is_active:
            con.execute("DELETE FROM sessions WHERE user_id = %s", (user_id,))


def soft_delete_user(user_id: int) -> None:
    """Xóa mềm: ẩn tài khoản và đăng xuất mọi phiên của người đó. Nhật ký đăng nhập vẫn giữ."""
    with connection() as con:
        con.execute("UPDATE users SET deleted_at = now(), is_active = FALSE WHERE id = %s AND deleted_at IS NULL",
                    (user_id,))
        con.execute("DELETE FROM sessions WHERE user_id = %s", (user_id,))


def list_roles() -> list[dict]:
    with connection() as con:
        return con.execute("""
            SELECT r.code, r.name, count(u.id) AS users_total,
                   count(u.id) FILTER (WHERE u.is_active) AS users_active
            FROM roles r LEFT JOIN users u ON u.role_id = r.id AND u.deleted_at IS NULL
            GROUP BY r.id, r.code, r.name ORDER BY r.id
        """).fetchall()


def update_role_name(code: str, name: str) -> bool:
    with connection() as con:
        return con.execute("UPDATE roles SET name = %s WHERE code = %s", (name, code)).rowcount > 0
