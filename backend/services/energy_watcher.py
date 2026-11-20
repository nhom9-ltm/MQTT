"""
Theo dõi ngân sách tiền điện: chạy nền trong tiến trình API, định kỳ tính báo cáo tháng hiện tại và phát cảnh báo
lên cùng topic với automation để notifier (Telegram/Email), logger và dashboard đều nhận được.

  Topic   : home/_auto/notify/event   (QoS 1)
  Payload : {"level": "warn" | "critical", "text": "...", "source": "energy", "ts": ...}

  warn     — tiền điện đã tới warn_ratio × ngân sách, hoặc dự báo cuối tháng sẽ vượt
  critical — tiền điện thực tế đã vượt ngân sách (notifier mặc định gửi mức này ra điện thoại)

Mỗi mức chỉ báo MỘT lần mỗi tháng; đã báo gì được lưu trong backend/data/energy_alerts.json nên khởi động lại API
không bị báo lặp. Đổi chu kỳ kiểm tra bằng ENERGY_CHECK_MIN (phút, mặc định 10; 0 = tắt).
"""
from __future__ import annotations

import json
import os
import threading
import time

from backend.common.mqtt_publish import publish_once
from backend.common.paths import DATA_DIR
from backend.repositories.history_repository import DatabaseUnavailable
from backend.services import energy_service

PREFIX = os.getenv("MQTT_PREFIX", "home")
TOPIC = f"{PREFIX}/_auto/notify/event"
LEVEL = {"warn": "warn", "over": "critical"}
RANK = {"off": 0, "ok": 0, "warn": 1, "over": 2}


def vnd(n: float) -> str:
    return f"{round(n):,}".replace(",", ".") + " đ"


def state_path() -> str:
    return os.getenv("ENERGY_ALERT_STATE", os.path.join(DATA_DIR, "energy_alerts.json"))


def _load_state() -> dict:
    try:
        with open(state_path(), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _save_state(state: dict) -> None:
    os.makedirs(os.path.dirname(state_path()), exist_ok=True)
    with open(state_path(), "w", encoding="utf-8") as f:
        json.dump(state, f)


def message(report: dict) -> str:
    mm = report["month"][5:] + "/" + report["month"][:4]
    b = report["budget"]
    now = report["bill"]["total"]
    if b["status"] == "over":
        return f"Tiền điện tháng {mm} đã {vnd(now)} ({report['kwh']:.1f} kWh), VƯỢT ngân sách {vnd(b['vnd'])}"
    proj = report["projected"]
    tail = f", dự báo cuối tháng {vnd(proj['total'])}" if proj else ""
    return f"Tiền điện tháng {mm} đã {vnd(now)} / ngân sách {vnd(b['vnd'])}{tail}"


def check(now_ms: int | None = None, publish=publish_once) -> dict | None:
    """Kiểm tra một lần. Trả về payload đã phát (hoặc None nếu không có gì mới để báo)."""
    report = energy_service.month_report(now_ms=now_ms)
    status = report["budget"]["status"]
    state = _load_state()
    sent = state.get(report["month"], "ok")
    if RANK[status] <= RANK.get(sent, 0):
        return None
    payload = {"level": LEVEL[status], "text": message(report), "source": "energy",
               "ts": now_ms if now_ms is not None else int(time.time() * 1000)}
    if not publish(TOPIC, json.dumps(payload, ensure_ascii=False), qos=1, client_prefix="api-energy"):
        return None                     # broker chưa sẵn sàng: lần kiểm tra sau gửi lại
    state[report["month"]] = status
    _save_state(state)
    print(f"  🔔 [{payload['level']}] {payload['text']}")
    return payload


def start(interval_min: float | None = None) -> threading.Thread | None:
    minutes = float(os.getenv("ENERGY_CHECK_MIN", 10)) if interval_min is None else interval_min
    if minutes <= 0:
        return None

    def loop():
        while True:
            try:
                check()
            except (DatabaseUnavailable, energy_service.EnergyConfigError) as e:
                print(f"Bỏ qua kiểm tra ngân sách điện: {e}")
            except Exception as e:      # không để lỗi bất ngờ làm chết luồng theo dõi
                print(f"Lỗi kiểm tra ngân sách điện: {e!r}")
            time.sleep(minutes * 60)

    t = threading.Thread(target=loop, name="energy-watcher", daemon=True)
    t.start()
    print(f"Theo dõi ngân sách tiền điện mỗi {minutes:g} phút")
    return t
