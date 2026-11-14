"""
Controller của automation engine: giữ MQTT client, nhận message, chuyển cho AutomationService.

  Subscribe : home/+/+/status, home/+/+/state        discovery + trạng thái thiết bị
              home/_auto/+/set                        đổi chế độ, chạy scene, bật/tắt luật
              home/_auto/mode/state                   khôi phục chế độ đã lưu (retained)
  Publish   : home/<phòng>/<thiết bị>/set              lệnh điều khiển (QoS 1)
              home/_auto/engine/status   retained     danh sách luật + scene, LWT
              home/_auto/mode/state      retained     chế độ nhà: home | away | night
              home/_auto/notify/event                 thông báo / cảnh báo cho dashboard

Ví dụ:
  python backend/run_automation.py
  python backend/run_automation.py --host 192.168.1.10 --rules my_rules.json
"""
import argparse
import json
import os
import signal
import sys
import time

from backend.common.cli import add_mqtt_args
from backend.common.mqtt_client import new_client
from backend.common.paths import CONFIG_DIR
from backend.services.automation_service import AutomationService


class AutomationController:
    def __init__(self, args):
        self.args = args
        self.stopping = False
        self.client = new_client(args.client_id, clean_session=True,
                                 username=args.username, password=args.password)
        self.service = AutomationService(args.prefix, args.rules, args.scenes, publish=self.client.publish)
        # Engine cũng có LWT: dashboard biết ngay khi "bộ não" ngừng hoạt động
        self.client.will_set(self.service.t_engine, json.dumps({"state": "offline", "reason": "lwt"}),
                             qos=1, retain=True)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.reconnect_delay_set(min_delay=1, max_delay=30)

    # ---------- MQTT callbacks ----------
    def on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            print(f"Kết nối thất bại: {reason_code}")
            return
        svc = self.service
        print(f"Đã kết nối {self.args.host}:{self.args.port} — {len(svc.rules)} luật, {len(svc.scenes)} kịch bản")
        client.subscribe([
            (f"{svc.p}/+/+/status", 1),
            (f"{svc.p}/+/+/state", 1),
            (f"{svc.p}/_auto/+/set", 1),
            (svc.t_mode, 1),
            (svc.t_locked, 1),
        ])
        svc.begin_warmup()

    def on_message(self, client, userdata, msg):
        parts = msg.topic.split("/")
        if len(parts) != 4 or parts[0] != self.service.p:
            return
        _, room, dev, kind = parts
        try:
            data = json.loads(msg.payload.decode()) if msg.payload else None
        except ValueError:
            return
        self.service.handle_message(room, dev, kind, data)

    # ---------- vòng đời ----------
    def run(self):
        self.client.connect_async(self.args.host, self.args.port, keepalive=30)
        self.client.loop_start()
        while not self.stopping:
            time.sleep(1)
            self.service.tick()

    def shutdown(self):
        self.stopping = True
        print("Dừng automation (graceful → không phát LWT)")
        if self.client.is_connected():
            info = self.service.publish_engine("offline", "graceful")
            try:
                info.wait_for_publish(timeout=2)
            except (ValueError, RuntimeError):
                pass
        self.client.disconnect()
        self.client.loop_stop()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Automation engine cho nhà thông minh (MQTT)")
    add_mqtt_args(p)
    p.add_argument("--client-id", default="automation-engine")
    p.add_argument("--rules", default=os.path.join(CONFIG_DIR, "rules.json"))
    p.add_argument("--scenes", default=os.path.join(CONFIG_DIR, "scenes.json"))
    return p


def main():
    args = build_parser().parse_args()
    controller = AutomationController(args)

    def stop(*_):
        controller.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    controller.run()


if __name__ == "__main__":
    main()
