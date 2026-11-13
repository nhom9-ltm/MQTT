"""
Thiết bị giả lập (mock) của căn nhà thông minh — thay cho phần cứng thật.

Mỗi thiết bị là MỘT MQTT client riêng — client id riêng, Last Will riêng — giống ngoài đời
mỗi bóng đèn / ổ cắm thông minh có chip WiFi riêng. Bấm "Mất điện" trên dashboard chỉ làm
đúng thiết bị đó rớt mạng và broker phát LWT của riêng nó.

Thiết bị không quan tâm ai ra lệnh (dashboard, automation hay mosquitto_pub): nó thực hiện
rồi báo lại trạng thái mới trên .../state — đó là nguồn sự thật duy nhất.

Lệnh đặc biệt cho mọi thiết bị giả lập:
  {"action":"crash"}    đóng socket không gửi DISCONNECT → broker phát LWT; tự bật lại sau --revive giây
  {"action":"trigger"}  giả lập sự kiện: có chuyển động, mở cửa, rò rỉ gas, nắng nóng đột ngột
"""
from __future__ import annotations

import json
import math
import os
import random
import socket
import time

from backend.common.mqtt_client import new_client

FW = "sim-2.0.0"


def now_ms() -> int:
    return int(time.time() * 1000)


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def local_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


LOCAL_IP = local_ip()


# =====================================================================
#  Thiết bị gốc: kết nối MQTT, LWT, nhận lệnh, publish trạng thái
# =====================================================================
class Device:
    TYPE = "generic"
    REPORT = False          # True: publish state định kỳ (cảm biến, thiết bị đo điện)

    def __init__(self, house: "House", room: str, room_name: str, dev_id: str, name: str, **opts):
        self.house = house
        self.args = house.args
        self.room = room
        self.room_name = room_name
        self.id = dev_id
        self.name = name
        self.opts = opts
        self.state = self.initial_state()
        self.dirty = True
        self.last_report = 0.0
        self.dead_until = 0.0     # > 0: đang "mất điện"
        self.client = None

        base = f"{self.args.prefix}/{room}/{dev_id}"
        self.t_status = f"{base}/status"
        self.t_state = f"{base}/state"
        self.t_set = f"{base}/set"

    # ---------- phần riêng của từng loại thiết bị ----------
    def initial_state(self) -> dict:
        return {}

    def caps(self) -> dict:
        """Khả năng của thiết bị — gửi kèm status để dashboard tự dựng giao diện (discovery)."""
        return {}

    def apply(self, cmd: dict):
        """Thực hiện lệnh set."""

    def trigger(self):
        """Giả lập sự kiện vật lý (nút 'Giả lập' trên dashboard)."""

    def update(self, dt: float, now: float) -> bool:
        """Mô phỏng mỗi giây. Trả True nếu có thay đổi quan trọng cần publish ngay."""
        return False

    # ---------- MQTT ----------
    def build_client(self):
        c = new_client(f"sim-{self.room}-{self.id}-{os.getpid()}", clean_session=True,
                       username=self.args.username, password=self.args.password)
        # LAST WILL — đặt TRƯỚC connect(). Broker chỉ phát khi thiết bị mất kết nối bất thường.
        c.will_set(self.t_status, json.dumps({"state": "offline", "reason": "lwt"}), qos=1, retain=True)
        c.on_connect = self.on_connect
        c.on_disconnect = self.on_disconnect
        c.on_message = self.on_message
        c.reconnect_delay_set(min_delay=1, max_delay=30)
        return c

    def start(self):
        self.client = self.build_client()
        self.client.connect_async(self.args.host, self.args.port, keepalive=self.args.keepalive)
        self.client.loop_start()

    def on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            self.log(f"Kết nối thất bại: {reason_code}")
            return
        if self.args.verbose:
            self.log(f"Đã kết nối {self.args.host}:{self.args.port}")
        with self.house.lock:
            self.publish_status("online")     # ghi đè thông điệp offline/LWT cũ (retained)
            self.publish_state(quiet=True)
        client.subscribe(self.t_set, qos=1)

    def on_disconnect(self, client, userdata, flags, reason_code, properties):
        if not self.house.stopping and not self.dead_until:
            self.log(f"Mất kết nối ({reason_code}) — paho tự reconnect...")

    def on_message(self, client, userdata, msg):
        if msg.topic != self.t_set:         # phòng thủ: chỉ nhận lệnh đúng topic của mình
            return
        try:
            cmd = json.loads(msg.payload.decode() or "{}")
        except ValueError:
            self.log(f"Lệnh không hợp lệ: {msg.payload!r}")
            return
        if not isinstance(cmd, dict):
            return
        src = cmd.get("from", "?")
        shown = {k: v for k, v in cmd.items() if k not in ("from", "ts")}
        self.log(f"← lệnh từ {src}: {json.dumps(shown, ensure_ascii=False)}")
        with self.house.lock:
            action = cmd.get("action")
            if action == "crash":
                self.crash()
                return
            if action == "trigger":
                self.trigger()
            else:
                self.apply(cmd)
            self.publish_state()

    def publish_status(self, state: str, reason: str | None = None):
        payload = {
            "state": state,
            "type": self.TYPE,
            "name": self.name,
            "room_name": self.room_name,
            "caps": self.caps(),
            "sim": True,
            "fw": FW,
            "ip": LOCAL_IP,
            "ts": now_ms(),
        }
        if reason:
            payload["reason"] = reason
        return self.client.publish(self.t_status, json.dumps(payload, ensure_ascii=False), qos=1, retain=True)

    def publish_state(self, quiet: bool = False):
        if not self.client or not self.client.is_connected():
            self.dirty = True
            return
        payload = {**self.state, "ts": now_ms()}
        self.client.publish(self.t_state, json.dumps(payload), qos=self.args.qos, retain=True)
        self.dirty = False
        self.last_report = time.time()
        if not quiet and not self.args.quiet:
            self.log(f"→ state {json.dumps(self.state, ensure_ascii=False)}")

    def tick(self, dt: float, now: float):
        if self.dead_until:
            if now >= self.dead_until:
                self.revive()
            return
        if self.update(dt, now):
            self.dirty = True
        if self.dirty:
            self.publish_state()
        elif self.REPORT and now - self.last_report >= self.args.interval:
            self.publish_state(quiet=not self.args.verbose)

    def crash(self):
        """Ngắt socket đột ngột, KHÔNG gửi DISCONNECT → broker phát LWT."""
        self.log(f"💥 Mất điện! Broker sẽ phát LWT (≤ {int(self.args.keepalive * 1.5)}s). "
                 f"Tự bật lại sau {self.args.revive:.0f}s")
        self.dead_until = time.time() + self.args.revive
        c = self.client
        c.loop_stop()
        try:
            sock = c.socket()
            if sock:
                sock.close()
        except OSError:
            pass

    def revive(self):
        self.log("🔌 Có điện trở lại — kết nối lại broker")
        self.dead_until = 0.0
        self.start()

    def shutdown(self):
        """Tắt đúng quy trình: tự báo offline rồi DISCONNECT → broker KHÔNG phát LWT."""
        if self.dead_until or not self.client:
            return
        if self.client.is_connected():
            info = self.publish_status("offline", reason="graceful")
            try:
                info.wait_for_publish(timeout=2)
            except (ValueError, RuntimeError):
                pass
        self.client.disconnect()
        self.client.loop_stop()

    def log(self, text: str):
        print(f"[{time.strftime('%H:%M:%S')}] [{self.room}/{self.id}] {text}", flush=True)

    # tiện ích cho lệnh bật/tắt
    def apply_on(self, cmd: dict):
        if cmd.get("toggle"):
            self.state["on"] = not self.state["on"]
        if "on" in cmd:
            self.state["on"] = bool(cmd["on"])


# =====================================================================
#  Các loại thiết bị
# =====================================================================
class Climate(Device):
    """Cảm biến nhiệt độ / độ ẩm. Nhiệt độ phòng chịu ảnh hưởng của điều hòa, quạt, rèm."""
    TYPE = "climate"
    REPORT = True

    def initial_state(self):
        self.base_t = self.opts["base_t"]
        self.base_h = self.opts["base_h"]
        daily = self.house.daily(time.time())
        self.t = self.base_t + 2.5 * daily + random.uniform(-0.5, 0.5)
        self.h = self.base_h - 6 * daily
        self.battery = random.uniform(80, 100)
        return self.snapshot()

    def snapshot(self):
        return {"temperature": round(self.t, 2), "humidity": round(clamp(self.h, 0, 100), 1),
                "battery": round(self.battery, 1)}

    def caps(self):
        return {"temperature": "°C", "humidity": "%"}

    def trigger(self):
        self.t += 6            # nắng gắt chiếu vào phòng: nhiệt độ vọt lên rồi hạ dần
        self.state = self.snapshot()

    def update(self, dt, now):
        h = self.house
        daily = h.daily(now)
        goal_t = self.base_t + 2.5 * daily
        goal_h = self.base_h - 6 * daily
        k_t = k_h = 0.004                       # tốc độ hội tụ về nhiệt độ "tự nhiên"

        fan = h.get(self.room, "fan")
        if fan and fan.state["on"]:
            goal_t -= 0.4 * fan.state.get("speed", 1)
        curtain = h.get(self.room, "curtain")
        if curtain and h.is_day(now) and curtain.state["position"] > 50:
            goal_t += 1.0
        ac = h.get(self.room, "ac")
        if ac and ac.state["on"]:
            if ac.state["mode"] == "cool":
                goal_t, k_t = ac.state["target"], 0.02
                goal_h -= 8
            elif ac.state["mode"] == "dry":
                goal_t -= 1
                goal_h, k_h = 50, 0.02

        self.t += (goal_t - self.t) * k_t * dt + random.gauss(0, 0.03)
        self.h += (goal_h - self.h) * k_h * dt + random.gauss(0, 0.1)
        self.battery = max(0.0, self.battery - 0.0005 * dt)
        self.state = self.snapshot()
        return False


class Light(Device):
    TYPE = "light"

    def initial_state(self):
        return {"on": False, "brightness": 100, "power": 0.0}

    def caps(self):
        return {"dimmable": self.opts.get("dimmable", False), "watt": self.opts["watt"]}

    def apply(self, cmd):
        self.apply_on(cmd)
        if "brightness" in cmd and self.opts.get("dimmable"):
            self.state["brightness"] = int(clamp(float(cmd["brightness"]), 1, 100))
            if "on" not in cmd:
                self.state["on"] = True
        self.recalc()

    def recalc(self):
        s = self.state
        s["power"] = round(self.opts["watt"] * s["brightness"] / 100, 1) if s["on"] else 0.0


class Fan(Device):
    TYPE = "fan"
    WATT = [0, 18, 28, 40]

    def initial_state(self):
        return {"on": False, "speed": 2, "power": 0.0}

    def caps(self):
        return {"speeds": 3}

    def apply(self, cmd):
        self.apply_on(cmd)
        if "speed" in cmd:
            self.state["speed"] = int(clamp(int(cmd["speed"]), 1, 3))
        self.state["power"] = float(self.WATT[self.state["speed"]]) if self.state["on"] else 0.0


class AirCon(Device):
    TYPE = "ac"
    REPORT = True
    MODES = ("cool", "dry", "fan")

    def initial_state(self):
        return {"on": False, "mode": "cool", "target": 26, "power": 0.0}

    def caps(self):
        return {"modes": list(self.MODES), "min": 16, "max": 30}

    def apply(self, cmd):
        self.apply_on(cmd)
        if cmd.get("mode") in self.MODES:
            self.state["mode"] = cmd["mode"]
        if "target" in cmd:
            self.state["target"] = int(clamp(round(float(cmd["target"])), 16, 30))
        self.update(0, time.time())

    def update(self, dt, now):
        s = self.state
        old = s["power"]
        if not s["on"]:
            s["power"] = 0.0
        elif s["mode"] == "fan":
            s["power"] = 45.0
        else:
            climate = self.house.get(self.room, "climate")
            gap = climate.t - s["target"] if climate else 2
            # máy nén chạy mạnh khi phòng còn nóng hơn nhiệt độ đặt
            s["power"] = round(320 + clamp(gap, 0, 4) * 220 + random.uniform(-15, 15), 0)
        return old == 0.0 and s["power"] > 0


class Curtain(Device):
    TYPE = "curtain"
    SPEED = 10                  # %/giây

    def initial_state(self):
        self.target = 0
        return {"position": 0, "moving": False}

    def caps(self):
        return {"position": True}

    def apply(self, cmd):
        s = self.state
        if "position" in cmd:
            self.target = int(clamp(float(cmd["position"]), 0, 100))
        if "open" in cmd:
            self.target = 100 if cmd["open"] else 0
        if cmd.get("toggle"):
            self.target = 0 if s["position"] >= 50 else 100
        if cmd.get("stop"):
            self.target = s["position"]
        s["moving"] = self.target != s["position"]

    def update(self, dt, now):
        s = self.state
        if self.target == s["position"]:
            return False
        step = self.SPEED * dt
        diff = self.target - s["position"]
        s["position"] = int(self.target if abs(diff) <= step else s["position"] + math.copysign(step, diff))
        s["moving"] = s["position"] != self.target
        return True


class Lock(Device):
    TYPE = "lock"

    def initial_state(self):
        return {"locked": True, "battery": round(random.uniform(70, 100), 0), "by": None}

    def apply(self, cmd):
        if cmd.get("toggle"):
            self.state["locked"] = not self.state["locked"]
        if "locked" in cmd:
            self.state["locked"] = bool(cmd["locked"])
        self.state["by"] = cmd.get("from")


class Plug(Device):
    """Ổ cắm thông minh có đo điện năng. 'cycle': thiết bị có rơ-le nhiệt (bếp điện) bật/tắt theo chu kỳ."""
    TYPE = "plug"
    REPORT = True

    def initial_state(self):
        self.heat_on = True
        self.heat_next = 0.0
        return {"on": self.opts.get("on", False), "power": 0.0, "energy": round(random.uniform(1, 40), 3),
                "voltage": 220.0}

    def caps(self):
        return {"watt": self.opts["watt"], "metering": True}

    def apply(self, cmd):
        self.apply_on(cmd)
        self.update(0, time.time())

    def update(self, dt, now):
        s = self.state
        w = self.opts["watt"]
        if not s["on"]:
            p = 0.0
        elif self.opts.get("cycle"):
            if now >= self.heat_next:
                self.heat_on = not self.heat_on
                self.heat_next = now + random.uniform(8, 20)
            p = w * random.uniform(0.95, 1.02) if self.heat_on else 2.0
        else:
            p = w * random.uniform(0.9, 1.1)
        s["power"] = round(p, 1)
        s["energy"] = round(s["energy"] + p * dt / 3_600_000, 4)       # W·s → kWh
        s["voltage"] = round(random.uniform(218, 226), 1)
        return False


class Motion(Device):
    """Cảm biến chuyển động PIR: báo motion=true, tự về false sau HOLD giây không có chuyển động."""
    TYPE = "motion"
    HOLD = 15

    def initial_state(self):
        self.last = 0.0
        return {"motion": False, "last_motion": None}

    def trigger(self):
        self.last = time.time()
        self.state.update(motion=True, last_motion=now_ms())

    def update(self, dt, now):
        if not self.args.no_random and random.random() < self.opts.get("rate", 0.01) * dt:
            was = self.state["motion"]
            self.trigger()
            return not was
        if self.state["motion"] and now - self.last > self.HOLD:
            self.state["motion"] = False
            return True
        return False


class Door(Device):
    """Cảm biến cửa (công tắc từ)."""
    TYPE = "door"

    def initial_state(self):
        self.close_at = 0.0
        return {"open": False}

    def trigger(self):
        self.state["open"] = True
        self.close_at = time.time() + 8

    def update(self, dt, now):
        if self.state["open"] and self.close_at and now >= self.close_at:
            self.state["open"] = False
            self.close_at = 0.0
            return True
        return False


class Gas(Device):
    """Cảm biến khí gas MQ-2: alarm=true khi nồng độ vượt ngưỡng."""
    TYPE = "gas"
    REPORT = True
    THRESHOLD = 1000

    def initial_state(self):
        self.leak_until = 0.0
        return {"ppm": 180, "alarm": False}

    def caps(self):
        return {"threshold": self.THRESHOLD}

    def trigger(self):
        self.leak_until = time.time() + 40

    def update(self, dt, now):
        goal = 2200 if now < self.leak_until else 180
        ppm = self.state["ppm"] + (goal - self.state["ppm"]) * 0.15 * dt + random.gauss(0, 6)
        self.state["ppm"] = int(max(0, ppm))
        alarm = self.state["ppm"] > self.THRESHOLD
        changed = alarm != self.state["alarm"]
        self.state["alarm"] = alarm
        return changed
