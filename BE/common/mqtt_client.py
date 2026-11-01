"""Tạo MQTT client với cấu hình chung của dự án (paho-mqtt 2.x, MQTT 3.1.1)."""
from __future__ import annotations

import sys

try:
    import paho.mqtt.client as mqtt
except ImportError:
    sys.exit("Thiếu thư viện: pip install -r BE/requirements.txt")


def new_client(client_id: str, clean_session: bool = True, username: str | None = None,
               password: str | None = None) -> "mqtt.Client":
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=client_id,
        clean_session=clean_session,
        protocol=mqtt.MQTTv311,
    )
    if username:
        client.username_pw_set(username, password)
    return client
