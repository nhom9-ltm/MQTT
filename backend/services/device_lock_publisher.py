"""Phát danh sách thiết bị bị khóa lên broker để automation và dashboard người dùng áp dụng ngay.

  Topic   : home/_admin/locked/state   (QoS 1, retained — client kết nối sau vẫn nhận được)
  Payload : {"devices": ["kitchen/stove-plug", ...], "ts": 1700000000000}

API gọi publish_locks() sau mỗi lần thêm/sửa/xóa/khóa thiết bị và lúc khởi động. Gửi trên thread riêng để request
không phải chờ broker; broker chưa chạy thì chỉ in cảnh báo, lần thay đổi sau (hoặc lần khởi động API sau) sẽ gửi lại.
Cấu hình broker lấy từ biến môi trường giống các tiến trình khác: MQTT_HOST, MQTT_PORT, MQTT_USER, MQTT_PASS.
"""
from __future__ import annotations

import json
import os
import threading
import time

from backend.repositories import device_repository

PREFIX = os.getenv("MQTT_PREFIX", "home")
TOPIC = f"{PREFIX}/_admin/locked/state"


def _send(payload: str) -> None:
    try:
        from paho.mqtt import publish
        user = os.getenv("MQTT_USER")
        publish.single(TOPIC, payload, qos=1, retain=True,
                       hostname=os.getenv("MQTT_HOST", "localhost"), port=int(os.getenv("MQTT_PORT", 1883)),
                       client_id=f"api-locks-{os.getpid()}",
                       auth={"username": user, "password": os.getenv("MQTT_PASS")} if user else None)
    except Exception as e:          # broker chưa chạy / sai mật khẩu: không làm hỏng request của trang quản trị
        print(f"Không gửi được danh sách thiết bị bị khóa lên broker: {e}")


def publish_locks(wait: bool = False) -> None:
    payload = json.dumps({"devices": device_repository.locked_keys(), "ts": int(time.time() * 1000)})
    t = threading.Thread(target=_send, args=(payload,), daemon=True)
    t.start()
    if wait:
        t.join(timeout=5)
