"""
Service đăng nhập: kiểm tra email/mật khẩu, tạo và xác thực phiên.

Mọi trường hợp sai (email không phải @gmail.com, không có tài khoản, sai mật khẩu, tài khoản bị khóa) đều
báo cùng một thông báo để không lộ email nào đã có tài khoản.
"""
from __future__ import annotations

import hashlib
import hmac
import re
import secrets

from backend.repositories import auth_repository

INVALID_CREDENTIALS = "Email hoặc mật khẩu không đúng"
SESSION_HOURS = 8
GMAIL = re.compile(r"[a-z0-9._%+-]+@gmail\.com")


class InvalidCredentials(Exception):
    pass


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def public_user(user: dict) -> dict:
    return {"id": user["id"], "email": user["email"], "full_name": user["full_name"], "role": user["role"]}


def login(email: str, password: str, ip: str | None) -> dict:
    email = email.strip().lower()
    if len(email) > 254 or not GMAIL.fullmatch(email):
        raise InvalidCredentials(INVALID_CREDENTIALS)

    user = auth_repository.find_user_by_email(email)
    ok = bool(user and user["is_active"] and hmac.compare_digest(user["password_hash"], sha256_hex(password)))
    auth_repository.record_login(email, user["id"] if user else None, ok, ip)
    if not ok:
        raise InvalidCredentials(INVALID_CREDENTIALS)

    token = secrets.token_urlsafe(32)
    auth_repository.create_session(user["id"], sha256_hex(token), SESSION_HOURS)
    return {"token": token, "user": public_user(user)}


def user_from_token(token: str) -> dict | None:
    user = auth_repository.find_session_user(sha256_hex(token))
    return public_user(user) if user else None


def logout(token: str) -> None:
    auth_repository.delete_session(sha256_hex(token))
