"""Service quản lý thiết bị đã đăng ký: kiểm tra dữ liệu rồi gọi device_repository.

Đăng ký thiết bị nghĩa là khai báo với hệ thống rằng có một thiết bị publish trên topic home/<phòng>/<mã>/...
(ESP32 thật hoặc thiết bị giả lập). Đăng ký không tự tạo thiết bị: thiết bị thật phải tự kết nối broker.

Khóa thiết bị (is_active = FALSE): automation bỏ qua thiết bị đó, dashboard người dùng chặn điều khiển. Danh sách
thiết bị bị khóa được phát lên broker sau mỗi thay đổi (xem device_lock_publisher).
"""
from __future__ import annotations

import re

from backend.repositories import device_repository as repo
from backend.repositories import house_repository, rule_repository
from backend.services.device_lock_publisher import publish_locks

CODE_RE = re.compile(r"[a-z0-9-]{1,30}")


class DeviceError(ValueError):
    pass


class DeviceNotFound(LookupError):
    pass


def resolve_house(data: dict) -> int:
    """Địa chỉ nhà của thiết bị: chọn nhà có sẵn (house_id) hoặc nhập địa chỉ mới (new_address → tạo nếu chưa có)."""
    new_address = house_repository.normalize(data.get("new_address", ""))
    if new_address:
        if not 5 <= len(new_address) <= 200:
            raise DeviceError("Địa chỉ nhà phải từ 5 đến 200 ký tự")
        return house_repository.get_or_create(new_address)
    try:
        house_id = int(data.get("house_id"))
    except (TypeError, ValueError):
        raise DeviceError("Chọn địa chỉ nhà cho thiết bị") from None
    if house_id not in house_repository.ids():
        raise DeviceError("Địa chỉ nhà không tồn tại")
    return house_id


def _clean(data: dict) -> tuple[str, str, str, str, bool, bool]:
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
    return room, code, name, type_code, bool(data.get("is_simulated", False)), bool(data.get("is_active", True))


def _rules_using(key: str) -> list[str]:
    """Tên các luật đang nhắc tới thiết bị `key` (trong trigger, điều kiện hoặc hành động)."""
    def mentions(obj) -> bool:
        if isinstance(obj, dict):
            return obj.get("device") == key or key in obj.get("except", []) or any(mentions(v) for v in obj.values())
        if isinstance(obj, list):
            return any(mentions(v) for v in obj)
        return False
    return [r["name"] for r in rule_repository.load_rules() if mentions(r)]


def _get(device_id: int) -> dict:
    device = repo.get_device(device_id)
    if not device:
        raise DeviceNotFound("Không tìm thấy thiết bị")
    return device


def list_devices() -> list[dict]:
    return repo.list_devices()


def get(device_id: int) -> dict:
    """Chi tiết thiết bị kèm danh sách người dùng đã kết nối thiết bị này."""
    return {**_get(device_id), "connected_users": repo.connected_users(device_id)}


def options() -> dict:
    return {"rooms": repo.list_rooms(), "types": repo.list_types()}


def houses() -> list[dict]:
    return house_repository.list_houses()


def create(data: dict, created_by: int | None = None) -> dict:
    room, code, name, type_code, sim, active = _clean(data)
    if repo.find_by_key(room, code):
        raise DeviceError(f"Thiết bị {room}/{code} đã được đăng ký (topic MQTT dùng chung cho mọi nhà)")
    house_id = resolve_house(data)
    device = repo.get_device(repo.create_device(room, code, name, type_code, sim, active, created_by, house_id))
    if not active:
        publish_locks()
    return device


def update(device_id: int, data: dict) -> dict:
    current = _get(device_id)
    room, code, name, type_code, sim, active = _clean({"is_active": current["is_active"], **data})
    new_key = f"{room}/{code}"
    other = repo.find_by_key(room, code)
    if other and other["id"] != device_id:
        raise DeviceError(f"Thiết bị {new_key} đã được đăng ký")
    house_id = resolve_house({"house_id": current["house_id"], **data})
    if new_key != current["key"] or house_id != current["house_id"]:
        used = _rules_using(current["key"])
        if used:
            raise DeviceError(f"Không đổi được phòng/mã/địa chỉ nhà vì luật đang dùng {current['key']}: {', '.join(used)}")
    repo.update_device(device_id, room, code, name, type_code, sim, active, house_id)
    if new_key != current["key"] or active != current["is_active"]:
        publish_locks()
    return repo.get_device(device_id)


def set_active(device_id: int, active: bool) -> dict:
    _get(device_id)
    repo.set_active(device_id, active)
    publish_locks()
    return repo.get_device(device_id)


def delete(device_id: int) -> None:
    current = _get(device_id)
    used = _rules_using(current["key"])
    if used:
        raise DeviceError(f"Không xóa được vì luật đang dùng {current['key']}: {', '.join(used)}. Sửa hoặc xóa các luật đó trước.")
    repo.delete_device(device_id)
    if not current["is_active"]:
        publish_locks()
