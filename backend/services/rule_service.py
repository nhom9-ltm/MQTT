"""Service quản lý luật tự động cho trang quản trị: thêm / sửa / xóa / bật-tắt luật trong rules.json.

Automation engine tự nạp lại rules.json khi file thay đổi (xem AutomationService.reload_rules_if_changed),
nên sửa ở đây là có hiệu lực ngay mà không phải khởi động lại engine.
"""
from __future__ import annotations

import os

from backend.common.paths import CONFIG_DIR
from backend.repositories import admin_repository, device_repository, house_repository, rule_repository
from backend.repositories.scene_repository import custom_path_for, load_custom_scenes
from backend.services.rule_helpers import MODES, load_json
from backend.services.rule_validation import RuleError, validate_rule

SCENES_PATH = os.path.join(CONFIG_DIR, "scenes.json")


class RuleNotFound(LookupError):
    pass


def _scenes() -> list[dict]:
    return load_json(SCENES_PATH) + load_custom_scenes(custom_path_for(SCENES_PATH))


def _scene_ids() -> set[str]:
    return {s["id"] for s in _scenes()}


def options() -> dict:
    """Dữ liệu cho form luật trên trang quản trị: kịch bản và chế độ nhà."""
    return {"scenes": [{"id": s["id"], "name": s.get("name", s["id"])} for s in _scenes()], "modes": MODES}


def _validate(data: dict) -> dict:
    """Luật thuộc một địa chỉ nhà và chỉ được dùng thiết bị của nhà đó."""
    try:
        house_id = int(data.get("house_id"))
    except (TypeError, ValueError):
        raise RuleError("Chọn địa chỉ nhà cho luật") from None
    return validate_rule(
        {**data, "house_id": house_id},
        devices=device_repository.device_keys(house_id),
        types={t["code"] for t in device_repository.list_types()},
        scenes=_scene_ids(),
        houses=house_repository.ids(),
    )


def _save(rules: list[dict]) -> None:
    rule_repository.save_rules(rules)
    sync_catalog(rules)


def sync_catalog(rules: list[dict] | None = None) -> None:
    rules = rule_repository.load_rules() if rules is None else rules
    admin_repository.sync_rule_catalog([(r["id"], r["name"], r.get("cooldown")) for r in rules])


def list_rules() -> list[dict]:
    return rule_repository.load_rules()


def create(data: dict) -> dict:
    rule = _validate(data)
    rules = rule_repository.load_rules()
    if any(r["id"] == rule["id"] for r in rules):
        raise RuleError(f"Mã luật “{rule['id']}” đã tồn tại")
    _save(rules + [rule])
    return rule


def update(rule_id: str, data: dict) -> dict:
    rules = rule_repository.load_rules()
    idx = next((i for i, r in enumerate(rules) if r["id"] == rule_id), None)
    if idx is None:
        raise RuleNotFound("Không tìm thấy luật")
    # không cho đổi mã luật khi sửa; không gửi địa chỉ nhà thì giữ địa chỉ cũ
    rule = _validate({"house_id": rules[idx].get("house_id"), **data, "id": rule_id})
    rules[idx] = rule
    _save(rules)
    return rule


def set_enabled(rule_id: str, enabled: bool) -> dict:
    rules = rule_repository.load_rules()
    rule = next((r for r in rules if r["id"] == rule_id), None)
    if rule is None:
        raise RuleNotFound("Không tìm thấy luật")
    rule["enabled"] = bool(enabled)
    _save(rules)
    return rule


def delete(rule_id: str) -> None:
    rules = rule_repository.load_rules()
    kept = [r for r in rules if r["id"] != rule_id]
    if len(kept) == len(rules):
        raise RuleNotFound("Không tìm thấy luật")
    _save(kept)
