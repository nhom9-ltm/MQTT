"""Gửi nhanh MỘT message lên broker từ tiến trình không giữ kết nối MQTT thường trực (ví dụ API).

Cấu hình broker lấy từ biến môi trường giống các tiến trình khác: MQTT_HOST, MQTT_PORT, MQTT_USER, MQTT_PASS.
Lỗi (broker chưa chạy, sai mật khẩu...) chỉ in cảnh báo và trả False, không ném ngoại lệ ra ngoài.
"""
from __future__ import annotations

import os


def publish_once(topic: str, payload: str, *, qos: int = 1, retain: bool = False, client_prefix: str = "api") -> bool:
    try:
        from paho.mqtt import publish
        user = os.getenv("MQTT_USER")
        publish.single(topic, payload, qos=qos, retain=retain,
                       hostname=os.getenv("MQTT_HOST", "localhost"), port=int(os.getenv("MQTT_PORT", 1883)),
                       client_id=f"{client_prefix}-{os.getpid()}",
                       auth={"username": user, "password": os.getenv("MQTT_PASS")} if user else None)
        return True
    except Exception as e:
        print(f"Không gửi được {topic} lên broker: {e}")
        return False
