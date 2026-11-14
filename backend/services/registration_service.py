"""Đăng ký tài khoản người dùng 3 bước, xác thực số điện thoại bằng OTP GIẢ LẬP (không gửi SMS thật).

  1. request_otp(phone, full_name)  → sinh mã 6 số, "gửi" bằng cách in ra terminal API và trả về cho trang đăng ký
                                      hiển thị như một tin SMS giả. Hết hạn sau OTP_TTL giây, gửi lại cách nhau RESEND_GAP giây.
  2. verify_otp(phone, otp)         → đúng mã thì cấp phiếu đăng ký (token) dùng một lần, hạn TOKEN_TTL giây.
                                      Sai quá MAX_ATTEMPTS lần thì mã bị hủy, phải gửi mã mới.
  3. register(token, email, address, password) → tạo tài khoản vai trò "user", mật khẩu băm SHA-256.

Trạng thái OTP giữ trong bộ nhớ của tiến trình API (đủ cho bản demo; khởi động lại API thì phải gửi mã mới).
"""
from __future__ import annotations

import hmac
import secrets
import threading
import time

from backend.repositories import house_repository
from backend.repositories import user_repository as users
from backend.services.auth_service import GMAIL, sha256_hex
from backend.services.user_service import MIN_PASSWORD, UserError, clean_phone

OTP_TTL = 300          # mã OTP có hiệu lực 5 phút
RESEND_GAP = 30        # gửi lại mã sau ít nhất 30 giây
MAX_ATTEMPTS = 5       # nhập sai tối đa 5 lần
TOKEN_TTL = 900        # sau khi xác thực có 15 phút để hoàn tất đăng ký


class RegistrationError(ValueError):
    pass


class TooSoon(RegistrationError):
    pass


_lock = threading.Lock()
_otps: dict[str, dict] = {}       # phone -> {code_hash, name, expires, sent_at, attempts}
_tokens: dict[str, dict] = {}     # sha256(token) -> {phone, name, expires}


def _clean_name(value) -> str:
    name = " ".join(str(value or "").split())
    if not 2 <= len(name) <= 100:
        raise RegistrationError("Họ tên phải từ 2 đến 100 ký tự")
    return name


def _phone(value) -> str:
    try:
        phone = clean_phone(value)
    except UserError as e:
        raise RegistrationError(str(e)) from None
    if not phone:
        raise RegistrationError("Nhập số điện thoại")
    return phone


def request_otp(phone, full_name) -> dict:
    phone, name = _phone(phone), _clean_name(full_name)
    if users.phone_taken(phone):
        raise RegistrationError(f"Số điện thoại {phone} đã được đăng ký. Hãy đăng nhập.")
    now = time.time()
    with _lock:
        old = _otps.get(phone)
        if old and now - old["sent_at"] < RESEND_GAP:
            wait = int(RESEND_GAP - (now - old["sent_at"])) + 1
            raise TooSoon(f"Vui lòng chờ {wait} giây rồi mới gửi lại mã")
        code = f"{secrets.randbelow(10**6):06d}"
        _otps[phone] = {"code_hash": sha256_hex(code), "name": name, "expires": now + OTP_TTL,
                        "sent_at": now, "attempts": 0}
    print(f"[OTP giả lập] Gửi tới {phone}: mã xác thực của bạn là {code} (hết hạn sau {OTP_TTL // 60} phút)")
    # Bản demo không có cổng SMS: trả mã về để trang đăng ký hiện như một tin nhắn giả.
    return {"phone": phone, "expires_in": OTP_TTL, "resend_after": RESEND_GAP, "mock_sms": code}


def verify_otp(phone, otp) -> dict:
    phone = _phone(phone)
    otp = str(otp or "").strip()
    if len(otp) != 6 or not otp.isdigit():
        raise RegistrationError("Mã OTP gồm đúng 6 chữ số")
    now = time.time()
    with _lock:
        entry = _otps.get(phone)
        if not entry:
            raise RegistrationError("Chưa gửi mã cho số này hoặc mã đã bị hủy. Hãy bấm “Gửi mã OTP”.")
        if now > entry["expires"]:
            _otps.pop(phone, None)
            raise RegistrationError("Mã OTP đã hết hạn. Hãy gửi mã mới.")
        if not hmac.compare_digest(entry["code_hash"], sha256_hex(otp)):
            entry["attempts"] += 1
            left = MAX_ATTEMPTS - entry["attempts"]
            if left <= 0:
                _otps.pop(phone, None)
                raise RegistrationError("Nhập sai quá nhiều lần, mã đã bị hủy. Hãy gửi mã mới.")
            raise RegistrationError(f"Mã OTP không đúng. Còn {left} lần thử.")
        _otps.pop(phone, None)
        token = secrets.token_urlsafe(24)
        _tokens[sha256_hex(token)] = {"phone": phone, "name": entry["name"], "expires": now + TOKEN_TTL}
    return {"token": token, "phone": phone, "full_name": entry["name"], "expires_in": TOKEN_TTL}


def register(token, email, address, password) -> dict:
    email = str(email or "").strip().lower()
    address = house_repository.normalize(address)
    password = str(password or "")
    if len(email) > 254 or not GMAIL.fullmatch(email):
        raise RegistrationError("Email phải là địa chỉ @gmail.com hợp lệ")
    if not 5 <= len(address) <= 200:
        raise RegistrationError("Địa chỉ nhà phải từ 5 đến 200 ký tự")
    if len(password) < MIN_PASSWORD:
        raise RegistrationError(f"Mật khẩu phải có ít nhất {MIN_PASSWORD} ký tự")

    key = sha256_hex(str(token or ""))
    with _lock:
        ticket = _tokens.get(key)
        if not ticket or time.time() > ticket["expires"]:
            _tokens.pop(key, None)
            raise RegistrationError("Phiên đăng ký đã hết hạn. Hãy xác thực lại số điện thoại.")
    if users.email_taken(email):
        raise RegistrationError(f"Email {email} đã có tài khoản. Hãy đăng nhập hoặc dùng email khác.")
    if users.phone_taken(ticket["phone"]):
        raise RegistrationError(f"Số điện thoại {ticket['phone']} đã được đăng ký.")

    house_id = house_repository.get_or_create(address)
    user_id = users.create_user(email, sha256_hex(password), ticket["name"], "user", True, ticket["phone"], house_id)
    with _lock:
        _tokens.pop(key, None)                    # phiếu chỉ dùng một lần
    user = users.get_user(user_id)
    print(f"[Đăng ký] Tài khoản mới {email} · {ticket['phone']} · {address}")
    return {"email": user["email"], "full_name": user["full_name"], "phone": user["phone"],
            "house_address": user["house_address"]}
