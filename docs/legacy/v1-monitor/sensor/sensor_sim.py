#!/usr/bin/env python3
"""
Cảm biến nhiệt độ / độ ẩm giả lập (thay cho ESP32 + DHT22).

Minh họa đầy đủ các tính năng MQTT:
  * Topic phân cấp : iot/<phong>/<device>/telemetry | status | cmd
  * QoS            : --qos 0/1/2 cho telemetry, status luôn QoS 1
  * Retain         : telemetry + status đều retained -> dashboard mở là có số
  * Last Will      : broker tự publish {"state":"offline"} khi thiết bị mất kết nối bất thường
  * Keep-alive     : --keepalive N giây; broker phát hiện thiết bị "chết" sau ~1.5*N giây
  * Nhận lệnh      : subscribe .../cmd để đổi chu kỳ gửi, bật/tắt, giả lập crash

Ví dụ:
  python sensor_sim.py                                   # 1 cảm biến mặc định
  python sensor_sim.py --room living --id sensor-01 --interval 2 --qos 1
  python sensor_sim.py --count 3                         # 3 cảm biến ở 3 phòng
  python sensor_sim.py --crash-after 20                  # 20s sau "rút điện" -> thấy LWT
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import signal
import socket
import sys
import threading
import time

try:
    import paho.mqtt.client as mqtt
except ImportError:
    sys.exit("Thiếu thư viện: pip install -r requirements.txt")

ROOMS = [
    # (room, base_temp, base_hum)
    ("living", 28.0, 62.0),
    ("bedroom", 26.5, 58.0),
    ("kitchen", 31.0, 70.0),
    ("server", 24.0, 45.0),
    ("garden", 30.0, 78.0),
]


class Sensor:
    def __init__(self, args, room: str, device_id: str, base_t: float, base_h: float):
        self.args = args
        self.room = room
        self.device_id = device_id
        self.base_t = base_t
        self.base_h = base_h
        self.interval = args.interval
        self.paused = False
        self.seq = 0
        self.battery = random.uniform(85, 100)
        self.drift_t = 0.0
        self.drift_h = 0.0
        self.spike_until = 0.0
        self.stop_evt = threading.Event()

        base = f"{args.prefix}/{room}/{device_id}"
        self.t_telemetry = f"{base}/telemetry"
        self.t_status = f"{base}/status"
        self.t_cmd = f"{base}/cmd"

        self.client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"{device_id}-{os.getpid()}",
            clean_session=True,
            protocol=mqtt.MQTTv311,
        )
        if args.username:
            self.client.username_pw_set(args.username, args.password)

        # ---------- LAST WILL & TESTAMENT ----------
        # Phải đặt TRƯỚC connect(). Broker giữ "di chúc" này và chỉ publish
        # khi client mất kết nối KHÔNG đúng quy trình (mất mạng, mất điện,
        # quá hạn keep-alive). Retain=True để client mở sau cũng thấy "offline".
        self.client.will_set(
            self.t_status,
            payload=json.dumps({"state": "offline", "reason": "lwt"}),
            qos=1,
            retain=True,
        )

        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = self.on_message
        self.client.reconnect_delay_set(min_delay=1, max_delay=30)

    # ---------------- callbacks ----------------
    def on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            self.log(f"Kết nối thất bại: {reason_code}")
            return
        self.log(f"Đã kết nối broker {self.args.host}:{self.args.port} "
                 f"(keepalive={self.args.keepalive}s)")
        # Báo "online" (retained) — ghi đè thông điệp "offline" cũ nếu có
        self.publish_status("online")
        client.subscribe(self.t_cmd, qos=1)

    def on_disconnect(self, client, userdata, flags, reason_code, properties):
        if not self.stop_evt.is_set():
            self.log(f"Mất kết nối ({reason_code}) — paho sẽ tự reconnect...")

    def on_message(self, client, userdata, msg):
        try:
            cmd = json.loads(msg.payload.decode() or "{}")
        except ValueError:
            self.log(f"Lệnh không hợp lệ: {msg.payload!r}")
            return
        self.log(f"Nhận lệnh: {cmd}")
        action = cmd.get("action")
        if action == "set_interval":
            self.interval = max(0.5, float(cmd.get("value", self.interval)))
            self.publish_status("online")
        elif action == "pause":
            self.paused = True
            self.publish_status("paused")
        elif action == "resume":
            self.paused = False
            self.publish_status("online")
        elif action == "spike":
            # giả lập sự cố: nhiệt độ tăng vọt 20s -> dashboard bật cảnh báo
            self.spike_until = time.time() + 20
        elif action == "crash":
            self.crash()

    # ---------------- helpers ----------------
    def log(self, text: str):
        print(f"[{time.strftime('%H:%M:%S')}] [{self.device_id}] {text}", flush=True)

    def publish_status(self, state: str, reason: str | None = None):
        payload = {
            "state": state,
            "ts": int(time.time() * 1000),
            "interval": self.interval,
            "qos": self.args.qos,
            "keepalive": self.args.keepalive,
            "ip": local_ip(),
            "fw": "sim-1.2.0",
        }
        if reason:
            payload["reason"] = reason
        self.client.publish(self.t_status, json.dumps(payload), qos=1, retain=True)

    def read_sensor(self):
        """Số liệu "giống thật": dao động theo giờ trong ngày + random walk + nhiễu."""
        hour = time.localtime().tm_hour + time.localtime().tm_min / 60
        daily = math.sin((hour - 9) / 24 * 2 * math.pi)   # đỉnh khoảng 15h
        self.drift_t = max(-1.5, min(1.5, self.drift_t + random.gauss(0, 0.08)))
        self.drift_h = max(-5, min(5, self.drift_h + random.gauss(0, 0.3)))

        temp = self.base_t + 2.5 * daily + self.drift_t + random.gauss(0, 0.15)
        hum = self.base_h - 6 * daily + self.drift_h + random.gauss(0, 0.6)
        if time.time() < self.spike_until:
            temp += 12 + random.uniform(0, 2)
            hum -= 15
        self.battery = max(0.0, self.battery - random.uniform(0.001, 0.01))
        return round(temp, 2), round(max(0, min(100, hum)), 1)

    def crash(self):
        """Ngắt socket đột ngột, KHÔNG gửi DISCONNECT -> broker phát LWT."""
        self.log("💥 Giả lập mất điện: đóng socket không gửi DISCONNECT. "
                 f"Broker sẽ phát LWT sau tối đa ~{int(self.args.keepalive * 1.5)}s "
                 "(hoặc ngay khi phát hiện socket đóng).")
        self.stop_evt.set()
        self.client.loop_stop()
        try:
            sock = self.client.socket()
            if sock:
                sock.close()
        except OSError:
            pass

    # ---------------- main loop ----------------
    def run(self):
        self.client.connect_async(self.args.host, self.args.port, keepalive=self.args.keepalive)
        self.client.loop_start()
        started = time.time()

        while not self.stop_evt.is_set():
            if self.args.crash_after and time.time() - started > self.args.crash_after:
                self.crash()
                break
            if self.client.is_connected() and not self.paused:
                temp, hum = self.read_sensor()
                self.seq += 1
                payload = {
                    "device": self.device_id,
                    "room": self.room,
                    "temperature": temp,
                    "humidity": hum,
                    "battery": round(self.battery, 1),
                    "rssi": random.randint(-75, -45),
                    "seq": self.seq,
                    "ts": int(time.time() * 1000),
                }
                info = self.client.publish(
                    self.t_telemetry, json.dumps(payload),
                    qos=self.args.qos, retain=self.args.retain,
                )
                if not self.args.quiet:
                    self.log(f"→ {self.t_telemetry}  T={temp}°C  H={hum}%  "
                             f"(QoS {self.args.qos}, mid={info.mid})")
            self.stop_evt.wait(self.interval)

    def shutdown(self):
        """Tắt đúng quy trình: tự báo offline rồi gửi DISCONNECT -> LWT KHÔNG được phát."""
        if self.stop_evt.is_set():
            return
        self.stop_evt.set()
        self.log("Tắt có kiểm soát: publish offline (graceful) + DISCONNECT")
        info = self.client.publish(
            self.t_status,
            json.dumps({"state": "offline", "reason": "graceful", "ts": int(time.time() * 1000)}),
            qos=1, retain=True,
        )
        try:
            info.wait_for_publish(timeout=3)
        except (ValueError, RuntimeError):
            pass
        self.client.disconnect()
        self.client.loop_stop()


def local_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def main():
    p = argparse.ArgumentParser(description="Cảm biến nhiệt độ/độ ẩm giả lập (MQTT)")
    p.add_argument("--host", default=os.getenv("MQTT_HOST", "localhost"))
    p.add_argument("--port", type=int, default=int(os.getenv("MQTT_PORT", 1883)))
    p.add_argument("--username", default=os.getenv("MQTT_USER"))
    p.add_argument("--password", default=os.getenv("MQTT_PASS"))
    p.add_argument("--prefix", default="iot", help="topic gốc (đổi nếu dùng broker công cộng)")
    p.add_argument("--room", default=None, help="tên phòng (mặc định: living)")
    p.add_argument("--id", default=None, help="device id (mặc định: sensor-01)")
    p.add_argument("--count", type=int, default=1, help="số cảm biến chạy song song")
    p.add_argument("--interval", type=float, default=2.0, help="chu kỳ gửi (giây)")
    p.add_argument("--qos", type=int, choices=[0, 1, 2], default=1)
    p.add_argument("--no-retain", dest="retain", action="store_false",
                   help="tắt retain cho telemetry")
    p.add_argument("--keepalive", type=int, default=10, help="keep-alive (giây)")
    p.add_argument("--crash-after", type=float, default=0,
                   help="sau N giây giả lập mất điện (để thấy LWT)")
    p.add_argument("--quiet", action="store_true")
    args = p.parse_args()

    sensors = []
    for i in range(args.count):
        room, bt, bh = ROOMS[i % len(ROOMS)]
        if args.count == 1 and args.room:
            room = args.room
        dev = args.id if (args.count == 1 and args.id) else f"sensor-{i + 1:02d}"
        sensors.append(Sensor(args, room, dev, bt, bh))

    threads = [threading.Thread(target=s.run, daemon=True) for s in sensors]
    for t in threads:
        t.start()

    def stop(*_):
        for s in sensors:
            s.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    while any(t.is_alive() for t in threads):
        time.sleep(0.5)


if __name__ == "__main__":
    main()
