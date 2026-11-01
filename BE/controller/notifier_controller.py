"""
Controller của notifier — đẩy cảnh báo từ automation ra điện thoại / hộp thư.

Subscribe home/_auto/notify/event và gửi các sự kiện có level nằm trong --levels (mặc định: critical)
qua Telegram và/hoặc Email. Kênh nào thiếu cấu hình thì tự tắt (xem BE/service/notify_channels.py).
Client id cố định + clean_session=False, nên cảnh báo phát lúc notifier đang tắt sẽ được gửi bù.

Ví dụ:
  $env:TELEGRAM_TOKEN="123:ABC"; $env:TELEGRAM_CHAT="987654321"
  $env:SMTP_USER="gui@gmail.com"; $env:SMTP_PASS="app-password"; $env:MAIL_TO="a@x.com,b@y.com"
  python BE/run_notifier.py
  python BE/run_notifier.py --test        # gửi thử 1 tin rồi thoát
"""
import argparse
import json
import sys

from BE.common.cli import add_mqtt_args
from BE.common.mqtt_client import new_client
from BE.service.notification_service import NotificationService
from BE.service.notify_channels import enabled_channels


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Gửi cảnh báo MQTT qua Telegram / Email")
    add_mqtt_args(p)
    p.add_argument("--client-id", default="notifier-01")
    p.add_argument("--levels", default="critical", help="các level cần gửi, cách nhau dấu phẩy")
    p.add_argument("--cooldown", type=int, default=60, help="giây tối thiểu giữa 2 thông báo cùng nguồn")
    p.add_argument("--test", action="store_true", help="gửi 1 thông báo thử qua các kênh đã bật rồi thoát")
    return p


def main():
    args = build_parser().parse_args()

    channels = enabled_channels()
    if not channels:
        sys.exit("Chưa kênh nào được cấu hình. Đặt TELEGRAM_TOKEN+TELEGRAM_CHAT và/hoặc "
                 "SMTP_USER+SMTP_PASS+MAIL_TO (xem MO_RONG.md).")

    levels = [x.strip() for x in args.levels.split(",")]
    service = NotificationService(channels, levels, args.cooldown)

    if args.test:
        sys.exit(0 if service.send_test() else 1)

    topic = f"{args.prefix}/_auto/notify/event"

    def on_message(client, userdata, msg):
        try:
            ev = json.loads(msg.payload)
        except ValueError:
            return
        service.handle(ev)

    def on_connect(client, userdata, flags, rc, props=None):
        if rc != 0:
            print(f"Kết nối broker thất bại: {rc}")
            return
        client.subscribe(topic, qos=1)
        print(f"Đã kết nối {args.host}:{args.port} — nghe {topic}, "
              f"level={sorted(service.levels)}, kênh={[c.name for c in channels]}, "
              f"session_present={flags.session_present}")

    client = new_client(args.client_id, clean_session=False,
                        username=args.username, password=args.password)
    client.on_connect = on_connect
    client.on_message = on_message
    client.reconnect_delay_set(1, 10)
    client.connect(args.host, args.port, keepalive=30)
    try:
        client.loop_forever()
    except KeyboardInterrupt:
        client.disconnect()


if __name__ == "__main__":
    main()
