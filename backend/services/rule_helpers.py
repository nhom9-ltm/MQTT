"""Hằng số và hàm thuần (không cần MQTT) dùng khi đánh giá luật tự động."""
import json
import operator
import time

MODES = {"home": "Ở nhà", "away": "Vắng nhà", "night": "Ban đêm"}
OPS = {"==": operator.eq, "!=": operator.ne, ">": operator.gt, ">=": operator.ge,
       "<": operator.lt, "<=": operator.le}
WARMUP = 3          # giây sau khi kết nối: chỉ nạp retained, không chạy luật


class SafeDict(dict):
    """format_map không lỗi khi thiếu khóa: '{ppm} ppm' → giữ nguyên '{ppm}'."""
    def __missing__(self, key):
        return "{" + key + "}"


def in_window(after: str, before: str) -> bool:
    now = time.strftime("%H:%M")
    if after <= before:
        return after <= now < before
    return now >= after or now < before         # khung giờ qua nửa đêm, vd 18:00 → 06:00


def load_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)
