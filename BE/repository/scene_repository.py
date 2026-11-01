"""Lưu/đọc các kịch bản do người dùng tạo từ dashboard (BE/config/scenes.custom.json).

Tách khỏi scenes.json để file kịch bản viết tay không bị định dạng lại mỗi lần người dùng thêm kịch bản.
"""
import json
import os


def custom_path_for(scenes_path: str) -> str:
    return os.path.splitext(scenes_path)[0] + ".custom.json"


def load_custom_scenes(path: str) -> list:
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        print(f"Không đọc được {path}: {e}")
        return []
    return [s for s in data if isinstance(s, dict) and s.get("id") and s.get("actions")] if isinstance(data, list) else []


def save_custom_scenes(path: str, scenes: list) -> None:
    """Ghi nguyên tử (ghi file tạm rồi thay thế) để mất điện giữa chừng không làm hỏng file."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(scenes, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)
