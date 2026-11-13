"""Service quản lý người dùng: tài khoản (thêm/sửa/xóa, khóa) và vai trò.

Hệ thống có đúng 2 vai trò cố định: admin và user (mã vai trò được dùng trong code phân quyền nên không thêm/xóa
được; chỉ đổi được tên hiển thị). Các ràng buộc an toàn:
  * Quản trị viên không tự xóa, tự khóa hay tự hạ quyền chính mình.
  * Luôn còn ít nhất một quản trị viên đang hoạt động.
Xóa tài khoản là xóa mềm (xem user_repository.soft_delete_user).
"""
from __future__ import annotations

from backend.repositories import user_repository as repo
from backend.services.auth_service import GMAIL, sha256_hex

ROLES = ("admin", "user")
ROLE_PERMISSIONS = {
    "admin": [
        "Vào trang quản trị",
        "Quản lý thiết bị, luật tự động",
        "Quản lý tài khoản và vai trò",
        "Xem thông báo, lịch sử đăng nhập",
        "Dùng bảng điều khiển nhà",
    ],
    "user": [
        "Dùng bảng điều khiển nhà",
        "Xem và điều khiển thiết bị",
        "Chạy kịch bản, đổi chế độ nhà, bật/tắt luật",
        "Xem thông báo và lịch sử",
    ],
}
MIN_PASSWORD = 6


class UserError(ValueError):
    pass


class UserNotFound(LookupError):
    pass


def _clean(data: dict, *, creating: bool) -> tuple[str, str, str, bool, str | None]:
    email = str(data.get("email", "")).strip().lower()
    full_name = str(data.get("full_name", "")).strip()
    role = str(data.get("role", "")).strip()
    password = str(data.get("password") or "")
    if len(email) > 254 or not GMAIL.fullmatch(email):
        raise UserError("Email phải là địa chỉ @gmail.com hợp lệ")
    if not 1 <= len(full_name) <= 100:
        raise UserError("Họ tên phải từ 1 đến 100 ký tự")
    if role not in ROLES:
        raise UserError("Vai trò phải là admin hoặc user")
    if creating and not password:
        raise UserError("Cần nhập mật khẩu cho tài khoản mới")
    if password and len(password) < MIN_PASSWORD:
        raise UserError(f"Mật khẩu phải có ít nhất {MIN_PASSWORD} ký tự")
    return email, full_name, role, bool(data.get("is_active", True)), (sha256_hex(password) if password else None)


# ---------------- tài khoản ----------------
def list_users(q: str = "", role: str = "", status: str = "") -> list[dict]:
    return repo.list_users(q.strip(), role if role in ROLES else "", status)


def create(data: dict) -> dict:
    email, full_name, role, active, pw_hash = _clean(data, creating=True)
    if repo.email_taken(email):
        raise UserError(f"Email {email} đã có tài khoản")
    return repo.get_user(repo.create_user(email, pw_hash, full_name, role, active))


def update(user_id: int, data: dict, current_admin: dict) -> dict:
    user = repo.get_user(user_id)
    if not user:
        raise UserNotFound("Không tìm thấy tài khoản")
    email, full_name, role, active, pw_hash = _clean(data, creating=False)
    if repo.email_taken(email, except_id=user_id):
        raise UserError(f"Email {email} đã có tài khoản")
    if email != user["email"] and repo.deleted_id_by_email(email):
        raise UserError(f"Email {email} thuộc một tài khoản đã xóa — hãy tạo tài khoản mới với email này thay vì đổi email")
    if user_id == current_admin["id"] and (role != "admin" or not active):
        raise UserError("Không thể tự hạ quyền hoặc tự khóa tài khoản đang đăng nhập")
    losing_admin = user["role"] == "admin" and user["is_active"] and (role != "admin" or not active)
    if losing_admin and repo.count_active_admins(except_id=user_id) == 0:
        raise UserError("Phải còn ít nhất một quản trị viên đang hoạt động")
    repo.update_user(user_id, email, full_name, role, active, pw_hash)
    return repo.get_user(user_id)


def set_active(user_id: int, active: bool, current_admin: dict) -> dict:
    """Khóa / mở khóa nhanh (nút ổ khóa). Khóa thì người đó bị đăng xuất ngay."""
    user = repo.get_user(user_id)
    if not user:
        raise UserNotFound("Không tìm thấy tài khoản")
    if user_id == current_admin["id"] and not active:
        raise UserError("Không thể tự khóa tài khoản đang đăng nhập")
    if user["role"] == "admin" and user["is_active"] and not active and repo.count_active_admins(except_id=user_id) == 0:
        raise UserError("Phải còn ít nhất một quản trị viên đang hoạt động")
    repo.update_user(user_id, user["email"], user["full_name"], user["role"], active, None)
    return repo.get_user(user_id)


def delete(user_id: int, current_admin: dict) -> None:
    user = repo.get_user(user_id)
    if not user:
        raise UserNotFound("Không tìm thấy tài khoản")
    if user_id == current_admin["id"]:
        raise UserError("Không thể xóa tài khoản đang đăng nhập")
    if user["role"] == "admin" and user["is_active"] and repo.count_active_admins(except_id=user_id) == 0:
        raise UserError("Phải còn ít nhất một quản trị viên đang hoạt động")
    repo.soft_delete_user(user_id)


# ---------------- vai trò ----------------
def list_roles() -> list[dict]:
    return [{**r, "permissions": ROLE_PERMISSIONS.get(r["code"], [])} for r in repo.list_roles()]


def rename_role(code: str, name: str) -> dict:
    name = str(name or "").strip()
    if not 1 <= len(name) <= 50:
        raise UserError("Tên vai trò phải từ 1 đến 50 ký tự")
    if not repo.update_role_name(code, name):
        raise UserNotFound("Không tìm thấy vai trò")
    return next(r for r in list_roles() if r["code"] == code)
