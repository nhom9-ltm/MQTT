"""Tham số dòng lệnh dùng chung cho mọi tiến trình MQTT của dự án."""
import argparse
import os


def add_mqtt_args(parser: argparse.ArgumentParser, prefix: bool = True) -> argparse.ArgumentParser:
    parser.add_argument("--host", default=os.getenv("MQTT_HOST", "localhost"))
    parser.add_argument("--port", type=int, default=int(os.getenv("MQTT_PORT", 1883)))
    parser.add_argument("--username", default=os.getenv("MQTT_USER"))
    parser.add_argument("--password", default=os.getenv("MQTT_PASS"))
    if prefix:
        parser.add_argument("--prefix", default="home")
    return parser
