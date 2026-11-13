"""Service quản lý thiết bị đã đăng ký: kiểm tra dữ liệu rồi gọi device_repository.

Đăng ký thiết bị nghĩa là khai báo với hệ thống rằng có một thiết bị publish trên topic home/<phòng>/<mã>/...
(ESP32 thật hoặc thiết bị giả lập). Đăng ký không tự tạo thiết bị: thiết bị thật phải tự kết nối broker.
"""
from __future__ import annotations

import re

from backend.repositories import device_repository as repo
from backend.repositories import rule_repository

CODE_RE = re.compile(r"[a-z0-9-]{1,30}")


class DeviceError(ValueError):
    pass


class DeviceNotFound(LookupError):
    pass


def _clean(data: dict) -> tuple[str, str, str, str, bool]:
    room = str(data.get("room", "")).strip()
    code = str(data.get("code", "")).strip().lower()
    name = str(data.get("name", "")).strip()
    type_code = str(data.get("type", "")).strip()
    if room not in {r["code"] for r in repo.list_rooms()}:
        raise DeviceError("Phòng không tồn tại")
    if not CODE_RE.fullmatch(code):
        raise DeviceError("Mã thiết bị chỉ gồm chữ thường không dấu, số và dấu gạch ngang (1–30 ký tự)")
    if not 1 <= len(name) <= 100:
        raise DeviceError("Tên thiết bị phải từ 1 đến 100 ký tự")
    if type_code not in {t["code"] for t in repo.list_types()}:
        raise DeviceError("Loại thiết bị không hợp lệ")
    return room, code, name, type_code, bool(data.get("is_simulated", False))


def _rules_using(key: str) -> list[str]:
    """Tên các luật đang nhắc tới thiết bị `key` (trong trigger, điều kiện hoặc hành động)."""
    def mentions(obj) -> bool:
        if isinstance(obj, dict):
            return obj.get("device") == key or key in obj.get("except", []) or any(mentions(v) for v in obj.values())
        if isinstance(obj, list):
            return any(mentions(v) for v in obj)
        return False
    return [r["name"] for r in rule_repository.load_rules() if mentions(r)]


def list_devices() -> list[dict]:
    return repo.list_devices()


def options() -> dict:
    return {"rooms": repo.list_rooms(), "types": repo.list_types()}


def create(data: dict) -> dict:
    room, code, name, type_code, sim = _clean(data)
    if repo.find_by_key(room, code):
        raise DeviceError(f"Thiết bị {room}/{code} đã được đăng ký")
    return repo.get_device(repo.create_device(room, code, name, type_code, sim))


def update(device_id: int, data: dict) -> dict:
    current = repo.get_device(device_id)
    if not current:
        raise DeviceNotFound("Không tìm thấy thiết bị")
    room, code, name, type_code, sim = _clean(data)
    new_key = f"{room}/{code}"
    other = repo.find_by_key(room, code)
    if other and other["id"] != device_id:
        raise DeviceError(f"Thiết bị {new_key} đã được đăng ký")
    if new_key != current["key"]:
        used = _rules_using(current["key"])
        if used:
            raise DeviceError(f"Không đổi được phòng/mã vì luật đang dùng {current['key']}: {', '.join(used)}")
    repo.update_device(device_id, room, code, name, type_code, sim)
    return repo.get_device(device_id)


def delete(device_id: int) -> None:
    current = repo.get_device(device_id)
    if not current:
        raise DeviceNotFound("Không tìm thấy thiết bị")
    used = _rules_using(current["key"])
    if used:
        raise DeviceError(f"Không xóa được vì luật đang dùng {current['key']}: {', '.join(used)}. Sửa hoặc xóa các luật đó trước.")
    repo.delete_device(device_id)
