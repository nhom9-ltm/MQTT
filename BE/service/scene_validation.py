"""
Kiểm tra dữ liệu kịch bản do NGƯỜI DÙNG tạo (từ dashboard) trước khi nhận vào engine.

Dữ liệu đến từ MQTT nên không được tin: chỉ chấp nhận các dạng hành động và khóa lệnh nằm trong danh sách
cho phép bên dưới. Nhờ đó không ai chèn được lệnh nguy hiểm như {"action":"crash"} hay ghi đè trường "from".

Dạng hành động hợp lệ (cùng cú pháp với BE/config/scenes.json):
  {"device": "phòng/thiết bị", "set": {...}}                          điều khiển một thiết bị
  {"type": "light", "set": {...}, "room"?: "living"}                  điều khiển cả nhóm theo loại
  {"mode": "home|away|night"}                                         đổi chế độ nhà
  {"delay": giây}                                                     chờ
  {"notify": "nội dung", "level"?: "info|warn|critical"}              gửi thông báo
"""
from __future__ import annotations

import re
import unicodedata

MAX_NAME = 40
MAX_ICON = 8
MAX_ACTIONS = 30
MAX_DELAY = 3600
MAX_NOTIFY = 200
MAX_CUSTOM_SCENES = 30
LEVELS = ("info", "warn", "critical")
ID_RE = re.compile(r"^[a-z0-9_-]{1,40}$")
DEVICE_RE = re.compile(r"^[a-z0-9_-]{1,40}/[a-z0-9_-]{1,40}$")

# Loại thiết bị điều khiển được + các khóa lệnh và giá trị cho phép (bool | (min, max) | tuple các giá trị)
SET_SPEC = {
    "light": {"on": bool, "brightness": (1, 100)},
    "fan": {"on": bool, "speed": (1, 3)},
    "ac": {"on": bool, "mode": ("cool", "dry", "fan"), "target": (16, 30)},
    "curtain": {"position": (0, 100)},
    "lock": {"locked": bool},
    "plug": {"on": bool},
}


class SceneError(ValueError):
    """Dữ liệu kịch bản không hợp lệ; thông điệp hiển thị thẳng cho người dùng."""


def slugify(text: str) -> str:
    s = unicodedata.normalize("NFKD", text.replace("đ", "d").replace("Đ", "D"))
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:30] or "kich-ban"


def make_scene_id(name: str, taken: set) -> str:
    """id duy nhất cho kịch bản tự tạo: 'custom-<tên không dấu>', trùng thì thêm -2, -3…"""
    base = f"custom-{slugify(name)}"
    sid, n = base, 2
    while sid in taken:
        sid = f"{base}-{n}"
        n += 1
    return sid


def _check_value(key: str, rule, value):
    if rule is bool:
        if not isinstance(value, bool):
            raise SceneError(f"“{key}” phải là bật/tắt (true/false)")
    elif isinstance(rule, tuple) and rule and isinstance(rule[0], str):
        if value not in rule:
            raise SceneError(f"“{key}” chỉ nhận một trong: {', '.join(rule)}")
    else:
        lo, hi = rule
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not lo <= value <= hi:
            raise SceneError(f"“{key}” phải là số từ {lo} đến {hi}")


def _check_set(dev_type: str, payload) -> dict:
    spec = SET_SPEC.get(dev_type) if isinstance(dev_type, str) else None
    if spec is None:
        raise SceneError(f"Loại thiết bị “{dev_type}” không điều khiển được")
    if not isinstance(payload, dict) or not payload:
        raise SceneError("Hành động điều khiển phải có ít nhất một thông số")
    clean = {}
    for key, value in payload.items():
        if key not in spec:
            raise SceneError(f"Thiết bị loại “{dev_type}” không có thông số “{key}”")
        _check_value(key, spec[key], value)
        clean[key] = value
    return clean


def _check_action(a, devices: dict, modes) -> dict:
    if not isinstance(a, dict):
        raise SceneError("Mỗi hành động phải là một đối tượng")
    if "delay" in a:
        d = a["delay"]
        if isinstance(d, bool) or not isinstance(d, (int, float)) or not 0 < d <= MAX_DELAY:
            raise SceneError(f"Thời gian chờ phải lớn hơn 0 và tối đa {MAX_DELAY} giây")
        return {"delay": d}
    if "mode" in a:
        if a["mode"] not in modes:
            raise SceneError(f"Chế độ “{a['mode']}” không hợp lệ")
        return {"mode": a["mode"]}
    if "notify" in a:
        text = a["notify"]
        if not isinstance(text, str) or not text.strip() or len(text) > MAX_NOTIFY:
            raise SceneError(f"Nội dung thông báo phải có chữ và tối đa {MAX_NOTIFY} ký tự")
        level = a.get("level", "info")
        if level not in LEVELS:
            raise SceneError(f"Mức thông báo phải là: {', '.join(LEVELS)}")
        # engine dùng str.format_map cho nội dung thông báo -> nhân đôi ngoặc nhọn để chữ người dùng gõ không gây lỗi
        return {"notify": text.strip().replace("{", "{{").replace("}", "}}"), "level": level}
    if "set" in a and "device" in a:
        key = a["device"]
        if not isinstance(key, str) or not DEVICE_RE.match(key):
            raise SceneError("Tên thiết bị không hợp lệ")
        dev = devices.get(key)
        if not dev or not dev.get("type"):
            raise SceneError(f"Chưa tìm thấy thiết bị “{key}” trong hệ thống")
        return {"device": key, "set": _check_set(dev["type"], a["set"])}
    if "set" in a and "type" in a:
        dev_type = a["type"]
        out = {"type": dev_type, "set": _check_set(dev_type, a["set"])}
        if a.get("room") is not None:
            if not isinstance(a["room"], str) or not ID_RE.match(a["room"]):
                raise SceneError("Tên phòng không hợp lệ")
            out["room"] = a["room"]
        return out
    raise SceneError("Hành động không đúng dạng cho phép (thiết bị, nhóm thiết bị, chế độ, chờ hoặc thông báo)")


def validate_scene(data, devices: dict, modes, taken_ids: set, taken_names: set, custom_count: int) -> dict:
    """Trả về kịch bản đã làm sạch {id, name, icon, actions}; sai thì ném SceneError."""
    if not isinstance(data, dict):
        raise SceneError("Dữ liệu kịch bản không hợp lệ")
    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        raise SceneError("Hãy nhập tên kịch bản")
    name = " ".join(name.split())
    if len(name) > MAX_NAME:
        raise SceneError(f"Tên kịch bản tối đa {MAX_NAME} ký tự")
    if name.casefold() in taken_names:
        raise SceneError(f"Đã có kịch bản tên “{name}”")
    if custom_count >= MAX_CUSTOM_SCENES:
        raise SceneError(f"Chỉ tạo được tối đa {MAX_CUSTOM_SCENES} kịch bản riêng")
    icon = data.get("icon") or "▶"
    if not isinstance(icon, str) or len(icon.strip()) > MAX_ICON:
        raise SceneError(f"Biểu tượng tối đa {MAX_ICON} ký tự")
    actions = data.get("actions")
    if not isinstance(actions, list) or not actions:
        raise SceneError("Kịch bản cần ít nhất một hành động")
    if len(actions) > MAX_ACTIONS:
        raise SceneError(f"Kịch bản tối đa {MAX_ACTIONS} hành động")
    clean = []
    for i, a in enumerate(actions, 1):
        try:
            clean.append(_check_action(a, devices, modes))
        except SceneError as e:
            raise SceneError(f"Hành động {i}: {e}") from None
    if all("delay" in a for a in clean):
        raise SceneError("Kịch bản chỉ có bước chờ thì không làm gì cả")
    return {"id": make_scene_id(name, taken_ids), "name": name, "icon": icon.strip() or "▶", "actions": clean}
