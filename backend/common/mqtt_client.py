"""Tạo MQTT client với cấu hình chung của dự án (paho-mqtt 2.x, MQTT 3.1.1)."""
from __future__ import annotations

import ssl
import sys

from backend.common.tls import check_cafile

try:
    import paho.mqtt.client as mqtt
except ImportError:
    sys.exit("Thiếu thư viện: pip install -r backend/requirements.txt")


def new_client(client_id: str, clean_session: bool = True, username: str | None = None,
               password: str | None = None, tls: bool = False, cafile: str | None = None) -> "mqtt.Client":
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=client_id,
        clean_session=clean_session,
        protocol=mqtt.MQTTv311,
    )
    if username:
        client.username_pw_set(username, password)
    if tls:
        # Kiểm tra chứng chỉ broker do CA của nhóm ký và tên máy khớp SAN (chống giả mạo broker / MITM)
        client.tls_set(ca_certs=check_cafile(cafile), cert_reqs=ssl.CERT_REQUIRED,
                       tls_version=ssl.PROTOCOL_TLS_CLIENT)
    return client


def broker_label(args) -> str:
    """Chuỗi mô tả kết nối để in log, ví dụ 'localhost:8883 (TLS)'."""
    return f"{args.host}:{args.port}" + (" (TLS)" if getattr(args, "tls", False) else "")
