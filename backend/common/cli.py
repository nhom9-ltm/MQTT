"""Tham số dòng lệnh dùng chung cho mọi tiến trình MQTT của dự án."""
import argparse
import os

from backend.common.tls import PLAIN_PORT, TLS_PORT, env_cafile, env_port, env_tls


class _TlsAction(argparse.Action):
    """--tls: bật TLS, đồng thời đổi cổng mặc định 1883 → 8883 (nếu người dùng không tự chọn cổng khác)."""

    def __init__(self, option_strings, dest, **kwargs):
        super().__init__(option_strings, dest, nargs=0, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        namespace.tls = True
        if namespace.port == PLAIN_PORT:
            namespace.port = TLS_PORT


def add_mqtt_args(parser: argparse.ArgumentParser, prefix: bool = True) -> argparse.ArgumentParser:
    parser.add_argument("--host", default=os.getenv("MQTT_HOST", "localhost"))
    parser.add_argument("--port", type=int, default=env_port(),
                        help="mặc định 1883, hoặc 8883 khi bật --tls")
    parser.add_argument("--username", default=os.getenv("MQTT_USER"))
    parser.add_argument("--password", default=os.getenv("MQTT_PASS"))
    parser.add_argument("--tls", action=_TlsAction, default=env_tls(),
                        help="kết nối mã hóa TLS (cổng 8883), kiểm tra broker bằng --cafile. Hoặc đặt MQTT_TLS=1")
    parser.add_argument("--cafile", default=env_cafile(),
                        help="CA để kiểm tra chứng chỉ broker (mặc định infra/broker/certs/ca.crt)")
    if prefix:
        parser.add_argument("--prefix", default="home")
    return parser
