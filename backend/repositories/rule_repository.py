"""Đọc/ghi luật tự động trong backend/config/rules.json.

File này là nguồn dữ liệu mà automation engine thực thi. Trang quản trị (API) và automation (bật/tắt luật từ
dashboard) cùng ghi vào đây, nên luôn ghi nguyên tử: ghi file tạm rồi thay thế, không để file dở dang.
"""
from __future__ import annotations

import json
import os
import threading

from backend.common.paths import CONFIG_DIR

RULES_PATH = os.path.join(CONFIG_DIR, "rules.json")
_lock = threading.Lock()


def load_rules(path: str = RULES_PATH) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"{path} phải là một danh sách luật")
    return data


def save_rules(rules: list[dict], path: str = RULES_PATH) -> None:
    tmp = path + ".tmp"
    with _lock:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(rules, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp, path)
