"""Cấu hình TLS dùng chung cho mọi client MQTT Python của dự án (xem docs/TLS.md).

Bật TLS bằng tham số --tls (các script run_*.py) hoặc biến môi trường MQTT_TLS=1 (mọi tiến trình, kể cả API).
Khi bật mà không chỉ định cổng, client tự dùng 8883 — cổng chuẩn của MQTT over TLS.
Client kiểm tra chứng chỉ broker bằng CA ở infra/broker/certs/ca.crt (tạo bằng infra/broker/gen_certs.py),
đổi bằng --cafile hoặc MQTT_CAFILE.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

PLAIN_PORT = 1883
TLS_PORT = 8883
DEFAULT_CA = Path(__file__).resolve().parents[2] / "infra" / "broker" / "certs" / "ca.crt"


def env_tls() -> bool:
    return os.getenv("MQTT_TLS", "").strip().lower() in ("1", "true", "yes", "on")


def env_cafile() -> str:
    return os.getenv("MQTT_CAFILE") or str(DEFAULT_CA)


def env_port() -> int:
    """MQTT_PORT nếu có, ngược lại 8883 khi bật TLS, 1883 khi không."""
    return int(os.getenv("MQTT_PORT") or (TLS_PORT if env_tls() else PLAIN_PORT))


def check_cafile(cafile: str) -> str:
    """Trả lại đường dẫn CA; thoát với hướng dẫn nếu chưa tạo chứng chỉ."""
    if not Path(cafile).is_file():
        sys.exit(f"Không thấy file CA: {cafile}\n"
                 "Tạo chứng chỉ trước:  python infra/broker/gen_certs.py   (xem docs/TLS.md)")
    return cafile
