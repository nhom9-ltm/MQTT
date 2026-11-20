"""Gửi nhanh MỘT message lên broker từ tiến trình không giữ kết nối MQTT thường trực (ví dụ API).

Cấu hình broker lấy từ biến môi trường giống các tiến trình khác: MQTT_HOST, MQTT_PORT, MQTT_USER, MQTT_PASS,
MQTT_TLS=1 (mã hóa, mặc định cổng 8883) và MQTT_CAFILE (xem backend/common/tls.py).
Lỗi (broker chưa chạy, sai mật khẩu, sai chứng chỉ...) chỉ in cảnh báo và trả False, không ném ngoại lệ ra ngoài.
"""
from __future__ import annotations

import os

from backend.common.tls import env_cafile, env_port, env_tls


def publish_once(topic: str, payload: str, *, qos: int = 1, retain: bool = False, client_prefix: str = "api") -> bool:
    try:
        from paho.mqtt import publish
        user = os.getenv("MQTT_USER")
        publish.single(topic, payload, qos=qos, retain=retain,
                       hostname=os.getenv("MQTT_HOST", "localhost"), port=env_port(),
                       client_id=f"{client_prefix}-{os.getpid()}",
                       auth={"username": user, "password": os.getenv("MQTT_PASS")} if user else None,
                       tls={"ca_certs": env_cafile()} if env_tls() else None)
        return True
    except Exception as e:
        print(f"Không gửi được {topic} lên broker: {e}")
        return False
