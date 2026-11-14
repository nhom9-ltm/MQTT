"""Người dùng "kết nối thiết bị" vào tài khoản bằng cách nhập mã thiết bị do quản trị viên đã tạo.

Mã nhập được so với các thiết bị thuộc ĐÚNG địa chỉ nhà của người dùng (devices.house_id = users.house_id):
  * nhập mã ngắn ("light") hoặc khóa đầy đủ "phòng/mã" ("living/light"); không phân biệt hoa thường
  * mã ngắn trùng nhiều phòng → yêu cầu nhập "phòng/mã" cho rõ
  * thiết bị đang bị khóa → không cho kết nối
"""
from __future__ import annotations

from backend.repositories import device_repository as devices
from backend.repositories import user_repository as users


class ConnectError(ValueError):
    pass


def _house_of(user: dict) -> int:
    row = users.get_user(user["id"])
    if not row or not row["house_id"]:
        raise ConnectError("Tài khoản của bạn chưa có địa chỉ nhà nên chưa kết nối được thiết bị. Hãy liên hệ quản trị viên.")
    return row["house_id"]


def _public(d: dict) -> dict:
    keep = ("id", "key", "code", "name", "room", "room_name", "type", "type_name", "is_active", "is_simulated",
            "house_address", "connected_at")
    return {k: d[k] for k in keep if k in d}


def list_mine(user: dict) -> list[dict]:
    return [_public(d) for d in devices.connected_devices(user["id"])]


def connect(user: dict, code) -> dict:
    code = "".join(str(code or "").split()).lower()
    if not code:
        raise ConnectError("Nhập mã thiết bị")
    if len(code) > 61:
        raise ConnectError("Mã thiết bị quá dài")
    found = devices.find_in_house(_house_of(user), code)
    if not found:
        raise ConnectError(f"Mã “{code}” không đúng hoặc không thuộc nhà của bạn. Kiểm tra lại mã quản trị viên đã cấp.")
    if len(found) > 1:
        keys = ", ".join(d["key"] for d in found)
        raise ConnectError(f"Có {len(found)} thiết bị cùng mã “{code}” ({keys}). Hãy nhập đầy đủ dạng phòng/mã, vd {found[0]['key']}.")
    device = found[0]
    if not device["is_active"]:
        raise ConnectError(f"Thiết bị “{device['name']}” đang bị quản trị viên khóa, chưa kết nối được.")
    if not devices.connect_user(user["id"], device["id"]):
        raise ConnectError(f"Thiết bị “{device['name']}” ({device['key']}) đã được kết nối với tài khoản của bạn từ trước.")
    return _public(device)
