#!/usr/bin/env python3
"""
Sinh dữ liệu mẫu 7 ngày vào BE/data/demo_history.db để xem trang lịch sử khi chưa chạy hệ thống đủ lâu.
Ghi vào file riêng, KHÔNG đụng tới smarthome.db thật.

    python BE/mock/seed_demo.py
    $env:HISTORY_DB="BE/data/demo_history.db"; python BE/run_api.py
"""
import json
import math
import os
import random
import sys
import time

if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from BE.common.paths import DEMO_DB  # noqa: E402
from BE.repository.message_repository import open_db  # noqa: E402

DAYS, STEP = 7, 600                      # 7 ngày, mỗi 10 phút một mẫu
ROOMS = {"living": 27, "bedroom": 26, "kitchen": 29, "lab": 28}
PLUGS = {("living", "tv-plug"): 90, ("kitchen", "stove-plug"): 1500, ("living", "ac"): 900,
         ("living", "light"): 18, ("bedroom", "light"): 12}
SOURCES = ["dashboard", "automation", "esp32-button", "scene:away", "scene:sleep"]


def main():
    random.seed(7)
    if os.path.exists(DEMO_DB):
        os.remove(DEMO_DB)
    db = open_db(DEMO_DB)
    rows = []
    now = int(time.time())

    def add(ts, room, device, kind, payload):
        rows.append((ts * 1000, ts * 1000, room, device, kind, json.dumps(payload), 1, 0))

    for ts in range(now - DAYS * 86400, now, STEP):
        hour = (ts % 86400) / 3600 + 7                      # ~giờ địa phương VN
        daily = math.sin((hour - 9) / 24 * 2 * math.pi)     # nóng nhất ~15h
        for room, base in ROOMS.items():
            add(ts, room, "climate", "state", {
                "temperature": round(base + 3 * daily + random.uniform(-.4, .4), 2),
                "humidity": round(65 - 8 * daily + random.uniform(-2, 2), 1)})
        for (room, dev), watt in PLUGS.items():
            evening = 18 <= hour % 24 <= 23
            on = random.random() < (0.6 if evening else 0.15)
            add(ts, room, dev, "state", {"on": on, "power": round(watt * random.uniform(.9, 1.1), 1) if on else 0.0})

    for _ in range(260):                                    # lệnh rải ngẫu nhiên, tập trung buổi tối
        ts = now - int(random.triangular(0, DAYS * 86400, 3600))
        room, dev = random.choice([("living", "light"), ("living", "ac"), ("bedroom", "light"),
                                   ("kitchen", "hood-fan"), ("entrance", "lock")])
        add(ts, room, dev, "set", {"on": True, "from": random.choices(SOURCES, [5, 3, 1, 1, 1])[0]})

    for _ in range(6):
        ts = now - random.randint(0, DAYS * 86400)
        add(ts, "_auto", "notify", "notify", {"level": "critical", "source": "rule:gas_leak",
                                              "text": "Phát hiện khí gas 1146 ppm ở nhà bếp! (dữ liệu mẫu)"})

    db.executemany("INSERT INTO messages (received_at, sent_at, room, device, kind, payload, qos, retained)"
                   " VALUES (?,?,?,?,?,?,?,?)", rows)
    db.commit()
    db.close()
    print(f"Đã tạo {len(rows)} bản ghi mẫu → {DEMO_DB}")


if __name__ == "__main__":
    main()
