"""
Controller của logger — minh họa QoS 1 + Persistent Session.

  * client_id CỐ ĐỊNH + clean_session=False  -> broker nhớ subscription của logger.
  * Subscribe QoS 1                            -> khi logger tắt, broker XẾP HÀNG các
    message QoS 1 gửi tới; bật lại logger sẽ nhận bù toàn bộ (không mất dữ liệu).
  * Thử: tắt logger 30s trong khi simulator chạy (--qos 1), bật lại -> thấy
    "session_present=True" và một loạt bản ghi "↺ nhận bù".

Ví dụ:
  python BE/run_logger.py
  python BE/run_logger.py --export history.csv          # xuất toàn bộ rồi thoát
  python BE/run_logger.py --export climate.csv --table climate
  python BE/run_logger.py --report                      # tóm tắt điện năng & lệnh điều khiển
"""
import argparse
import json
import signal
import sys

from BE.common.cli import add_mqtt_args
from BE.common.mqtt_client import new_client
from BE.common.paths import DEFAULT_DB
from BE.repository.message_repository import TABLES, open_db
from BE.service import logger_service


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="MQTT -> SQLite logger (nhà thông minh)")
    add_mqtt_args(p)
    p.add_argument("--client-id", default="history-logger-01")
    p.add_argument("--db", default=DEFAULT_DB)
    p.add_argument("--export", metavar="CSV", help="xuất bảng ra CSV rồi thoát")
    p.add_argument("--table", choices=TABLES, default="messages", help="bảng/view để xuất")
    p.add_argument("--report", action="store_true", help="in báo cáo tóm tắt rồi thoát")
    return p


def main():
    args = build_parser().parse_args()
    db = open_db(args.db)

    if args.export:
        logger_service.export(db, args.table, args.export)
        return
    if args.report:
        logger_service.report(db)
        return

    service = logger_service.LoggerService(db)

    def on_connect(client, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            print(f"Kết nối thất bại: {reason_code}")
            return
        print(f"Đã kết nối. session_present={flags.session_present} "
              f"({'broker còn giữ session cũ -> sẽ nhận bù message' if flags.session_present else 'session mới'})")
        client.subscribe([
            (f"{args.prefix}/+/+/state", 1),
            (f"{args.prefix}/+/+/status", 1),
            (f"{args.prefix}/+/+/set", 1),
            (f"{args.prefix}/_auto/notify/event", 1),
        ])

    def on_message(client, userdata, msg):
        parts = msg.topic.split("/")
        if len(parts) != 4:
            return
        _, room, device, kind = parts
        text = msg.payload.decode(errors="replace")
        try:
            data = json.loads(text) if text else {}
        except ValueError:
            return
        if not isinstance(data, dict):
            return
        service.record(room, device, kind, text, data, msg.qos, msg.retain)

    client = new_client(args.client_id, clean_session=False,          # <-- PERSISTENT SESSION
                        username=args.username, password=args.password)
    client.on_connect = on_connect
    client.on_message = on_message

    def stop(*_):
        print("Dừng logger (session vẫn được broker giữ lại).")
        client.disconnect()
        db.close()
        sys.exit(0)

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    print(f"Logger -> {args.db}")
    client.connect_async(args.host, args.port, keepalive=30)
    client.loop_forever(retry_first_connection=True)


if __name__ == "__main__":
    main()
