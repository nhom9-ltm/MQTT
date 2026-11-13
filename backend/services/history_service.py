"""
Service lịch sử: gom nhóm dữ liệu từ SQLite thành số liệu cho biểu đồ.
Mọi mốc thời gian trả về là mili-giây epoch (JS: new Date(t)).
"""
from __future__ import annotations

import json
import os
import time

from backend.common.paths import DEFAULT_DB
from backend.repositories.history_repository import query as _query


def db_path() -> str:
    # đọc mỗi lần gọi để đổi HISTORY_DB (vd dữ liệu mẫu) mà không phải sửa code
    return os.getenv("HISTORY_DB", DEFAULT_DB)


def query(sql, *params):
    return _query(db_path(), sql, *params)


def since_ms(hours):
    return int((time.time() - hours * 3600) * 1000)


def bucket_ms(hours, points=120):
    """Cỡ nhóm để biểu đồ có khoảng `points` điểm, tối thiểu 1 phút."""
    return max(60_000, int(hours * 3600_000 / points))


def summary(hours: int) -> dict:
    t = since_ms(hours)
    msgs = query("SELECT COUNT(*) n, MIN(received_at) first, MAX(received_at) last FROM messages")[0]
    return {
        "messages_total": msgs["n"], "first": msgs["first"], "last": msgs["last"],
        "commands": query("SELECT COUNT(*) n FROM commands WHERE received_at>?", t)[0]["n"],
        "alerts": query("SELECT COUNT(*) n FROM messages WHERE kind='notify' AND received_at>? "
                        "AND payload LIKE '%\"critical\"%'", t)[0]["n"],
        "rooms": [r["room"] for r in query(
            "SELECT DISTINCT room FROM climate WHERE room NOT LIKE '\\_%' ESCAPE '\\' ORDER BY room")],
    }


def climate(room: str, hours: int) -> dict:
    """Nhiệt độ / độ ẩm trung bình theo nhóm thời gian của một phòng."""
    b = bucket_ms(hours)
    rows = query(
        "SELECT (received_at/?)*? AS t, ROUND(AVG(temperature),1) AS temperature, "
        "ROUND(AVG(humidity),1) AS humidity FROM climate "
        "WHERE room=? AND received_at>? GROUP BY t ORDER BY t", b, b, room, since_ms(hours))
    return {"room": room, "bucket_ms": b, "points": rows}


def energy(days: int) -> dict:
    """Điện năng ước tính (kWh) = tổng công suất trung bình từng giờ của mỗi thiết bị."""
    rows = query(
        "SELECT day, room||'/'||device AS device, ROUND(SUM(p)/1000.0, 3) AS kwh FROM ("
        "  SELECT strftime('%Y-%m-%d', received_at/1000, 'unixepoch', 'localtime') AS day,"
        "         strftime('%H', received_at/1000, 'unixepoch', 'localtime') AS h, room, device,"
        "         AVG(power_w) AS p FROM energy WHERE received_at>? GROUP BY day, h, room, device"
        ") GROUP BY day, room, device", since_ms(days * 24))
    by_day, by_device = {}, {}
    for r in rows:
        by_day[r["day"]] = round(by_day.get(r["day"], 0) + r["kwh"], 3)
        by_device[r["device"]] = round(by_device.get(r["device"], 0) + r["kwh"], 3)
    return {
        "by_day": [{"day": d, "kwh": v} for d, v in sorted(by_day.items())],
        "by_device": sorted(({"device": d, "kwh": v} for d, v in by_device.items() if v > 0),
                            key=lambda x: -x["kwh"]),
    }


def commands(hours: int) -> dict:
    """Thống kê lệnh: ai ra lệnh nhiều nhất, thiết bị nào bị điều khiển nhiều nhất."""
    t = since_ms(hours)
    return {
        "by_source": query("SELECT COALESCE(source,'?') AS source, COUNT(*) AS n FROM commands "
                           "WHERE received_at>? GROUP BY source ORDER BY n DESC", t),
        "by_device": query("SELECT room||'/'||device AS device, COUNT(*) AS n FROM commands "
                           "WHERE received_at>? GROUP BY room, device ORDER BY n DESC LIMIT 10", t),
    }


def alerts(limit: int) -> list[dict]:
    """Các thông báo gần nhất do automation phát (info / rule / critical)."""
    out = []
    for r in query("SELECT received_at, payload FROM messages WHERE kind='notify' "
                   "ORDER BY received_at DESC LIMIT ?", limit):
        try:
            p = json.loads(r["payload"])
        except ValueError:
            continue
        out.append({"t": r["received_at"], "level": p.get("level"), "text": p.get("text")})
    return out
