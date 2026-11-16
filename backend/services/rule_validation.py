"""Kiểm tra một luật tự động do quản trị viên gửi lên trước khi ghi vào rules.json.

Chỉ nhận đúng các dạng mà AutomationService biết chạy (xem automation_service.check / do_action); trả về bản đã
chuẩn hóa (bỏ khóa lạ) hoặc báo RuleError với thông báo tiếng Việt để hiện lên trang quản trị.
"""
from __future__ import annotations

import re

from backend.services.rule_helpers import MODES, OPS

ID_RE = re.compile(r"[a-z0-9_]{2,50}")
DEVICE_RE = re.compile(r"[a-z0-9-]+/[a-z0-9-]+")
TIME_RE = re.compile(r"([01]\d|2[0-3]):[0-5]\d")
LEVELS = ("info", "warn", "critical")
SCALAR = (bool, int, float, str)


class RuleError(ValueError):
    pass


def _device(value, where: str, devices: set[str]) -> str:
    if not isinstance(value, str) or not DEVICE_RE.fullmatch(value):
        raise RuleError(f"{where}: thiết bị phải có dạng phòng/mã, ví dụ living/light")
    if value not in devices:
        raise RuleError(f"{where}: thiết bị “{value}” chưa được đăng ký ở địa chỉ nhà này")
    return value


def _time(value, where: str) -> str:
    if not isinstance(value, str) or not TIME_RE.fullmatch(value):
        raise RuleError(f"{where}: giờ phải có dạng HH:MM, ví dụ 23:00")
    return value


def _compare(c: dict, where: str, devices: set[str]) -> dict:
    out = {"device": _device(c.get("device"), where, devices)}
    field = c.get("field")
    if not isinstance(field, str) or not field.strip():
        raise RuleError(f"{where}: thiếu trường trạng thái (field), ví dụ temperature, on, motion")
    out["field"] = field.strip()
    op = c.get("op", "==")
    if op not in OPS:
        raise RuleError(f"{where}: phép so sánh phải là một trong {', '.join(OPS)}")
    out["op"] = op
    if "value" not in c or not isinstance(c["value"], SCALAR):
        raise RuleError(f"{where}: giá trị so sánh phải là số, chữ hoặc true/false")
    out["value"] = c["value"]
    return out


def _trigger(t, devices: set[str]) -> dict:
    if not isinstance(t, dict):
        raise RuleError("Thiếu điều kiện kích hoạt (trigger)")
    if "at" in t:
        return {"at": _time(t["at"], "Kích hoạt")}
    out = _compare(t, "Kích hoạt", devices)
    if t.get("for") not in (None, 0, ""):
        if not isinstance(t["for"], int) or isinstance(t["for"], bool) or not 0 < t["for"] <= 86400:
            raise RuleError("Kích hoạt: “giữ trong” phải là số giây từ 1 đến 86400")
        out["for"] = t["for"]
    return out


def _condition(c, i: int, devices: set[str]) -> dict:
    where = f"Điều kiện {i}"
    if not isinstance(c, dict):
        raise RuleError(f"{where}: phải là một đối tượng JSON")
    if "device" in c:
        return _compare(c, where, devices)
    if "mode" in c:
        modes = c["mode"] if isinstance(c["mode"], list) else [c["mode"]]
        if not modes or any(m not in MODES for m in modes):
            raise RuleError(f"{where}: chế độ phải thuộc {', '.join(MODES)}")
        return {"mode": modes}
    if "time" in c:
        t = c["time"] if isinstance(c["time"], dict) else {}
        return {"time": {"after": _time(t.get("after"), where), "before": _time(t.get("before"), where)}}
    if "at" in c:
        return {"at": _time(c["at"], where)}
    raise RuleError(f"{where}: phải có một trong các khóa device, mode, time, at")


def _action(a, i: int, devices: set[str], types: set[str], scenes: set[str]) -> dict:
    where = f"Hành động {i}"
    if not isinstance(a, dict):
        raise RuleError(f"{where}: phải là một đối tượng JSON")
    if "set" in a:
        if not isinstance(a["set"], dict) or not a["set"]:
            raise RuleError(f"{where}: “set” phải là đối tượng lệnh, ví dụ {{\"on\": true}}")
        if "device" in a:
            return {"device": _device(a["device"], where, devices), "set": a["set"]}
        if a.get("type") not in types:
            raise RuleError(f"{where}: cần “device” hoặc “type” là loại thiết bị đã có ({', '.join(sorted(types))})")
        out = {"type": a["type"], "set": a["set"]}
        if a.get("room"):
            out["room"] = str(a["room"])
        if a.get("except"):
            if not isinstance(a["except"], list):
                raise RuleError(f"{where}: “except” phải là danh sách thiết bị")
            out["except"] = [_device(d, where, devices) for d in a["except"]]
        return out
    if "notify" in a:
        if not isinstance(a["notify"], str) or not a["notify"].strip():
            raise RuleError(f"{where}: nội dung thông báo không được để trống")
        level = a.get("level", "info")
        if level not in LEVELS:
            raise RuleError(f"{where}: mức thông báo phải là {', '.join(LEVELS)}")
        return {"notify": a["notify"].strip(), "level": level}
    if "delay" in a:
        d = a["delay"]
        if not isinstance(d, (int, float)) or isinstance(d, bool) or not 0 < d <= 3600:
            raise RuleError(f"{where}: thời gian chờ phải từ 1 đến 3600 giây")
        return {"delay": d}
    if "scene" in a:
        if a["scene"] not in scenes:
            raise RuleError(f"{where}: không có kịch bản “{a['scene']}”")
        return {"scene": a["scene"]}
    if "mode" in a:
        if a["mode"] not in MODES:
            raise RuleError(f"{where}: chế độ phải thuộc {', '.join(MODES)}")
        return {"mode": a["mode"]}
    raise RuleError(f"{where}: phải có một trong các khóa set, notify, delay, scene, mode")


def validate_rule(data, *, devices: set[str], types: set[str], scenes: set[str], houses: set[int] | None = None) -> dict:
    """devices: các khóa "phòng/mã" được dùng (thường là thiết bị cùng nhà với luật); types: loại thiết bị;
    scenes: mã kịch bản; houses: id các địa chỉ nhà hợp lệ (None = không kiểm tra địa chỉ)."""
    if not isinstance(data, dict):
        raise RuleError("Dữ liệu luật không hợp lệ")
    rule_id = str(data.get("id", "")).strip()
    if not ID_RE.fullmatch(rule_id):
        raise RuleError("Mã luật chỉ gồm chữ thường không dấu, số và dấu gạch dưới (2–50 ký tự)")
    name = str(data.get("name", "")).strip()
    if not 1 <= len(name) <= 150:
        raise RuleError("Tên luật phải từ 1 đến 150 ký tự")

    conditions = data.get("conditions") or []
    actions = data.get("actions") or []
    if not isinstance(conditions, list):
        raise RuleError("Điều kiện phải là danh sách")
    if not isinstance(actions, list) or not actions:
        raise RuleError("Luật phải có ít nhất một hành động")

    rule = {
        "id": rule_id,
        "name": name,
        "description": str(data.get("description", "")).strip()[:300],
        "enabled": bool(data.get("enabled", True)),
    }
    if houses is not None:
        house_id = data.get("house_id")
        if isinstance(house_id, bool) or not isinstance(house_id, int) or house_id not in houses:
            raise RuleError("Chọn địa chỉ nhà cho luật")
        rule["house_id"] = house_id
    rule["trigger"] = _trigger(data.get("trigger"), devices)
    if conditions:
        rule["conditions"] = [_condition(c, i, devices) for i, c in enumerate(conditions, 1)]
    rule["actions"] = [_action(a, i, devices, types, scenes) for i, a in enumerate(actions, 1)]
    cooldown = data.get("cooldown")
    if cooldown not in (None, 0, ""):
        if not isinstance(cooldown, int) or isinstance(cooldown, bool) or not 0 < cooldown <= 86400:
            raise RuleError("Thời gian nghỉ giữa 2 lần chạy phải từ 1 đến 86400 giây")
        rule["cooldown"] = cooldown
    return rule
