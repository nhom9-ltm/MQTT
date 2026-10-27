#!/usr/bin/env python3
"""
Automation engine cho nhà thông minh — "bộ não" chạy luật và kịch bản.

Nó chỉ là một MQTT client như mọi client khác: subscribe trạng thái của tất cả thiết bị, khi
luật thỏa thì publish lệnh xuống .../set. Thiết bị không biết (và không cần biết) ai ra lệnh —
đó là ưu điểm của mô hình publish/subscribe: thêm "bộ não" mà không sửa thiết bị hay dashboard.

  Subscribe : home/+/+/status, home/+/+/state        discovery + trạng thái thiết bị
              home/_auto/+/set                        đổi chế độ, chạy scene, bật/tắt luật
              home/_auto/mode/state                   khôi phục chế độ đã lưu (retained)
  Publish   : home/<phòng>/<thiết bị>/set              lệnh điều khiển (QoS 1)
              home/_auto/engine/status   retained     danh sách luật + scene, LWT
              home/_auto/mode/state      retained     chế độ nhà: home | away | night
              home/_auto/notify/event                 thông báo / cảnh báo cho dashboard

Luật (rules.json):
  trigger    : điều kiện kích hoạt — chỉ chạy ở SƯỜN LÊN (sai → đúng), có thể kèm "for": giữ N giây
  conditions : các điều kiện phụ, tất cả phải đúng tại thời điểm kích hoạt
  actions    : set / scene / mode / notify / delay, chạy tuần tự
  cooldown   : số giây tối thiểu giữa 2 lần chạy

Ví dụ:
  python automation/automation.py
  python automation/automation.py --host 192.168.1.10 --rules my_rules.json
"""
from __future__ import annotations

import argparse
import json
import operator
import os
import signal
import sys
import threading
import time

try:
    import paho.mqtt.client as mqtt
except ImportError:
    sys.exit("Thiếu thư viện: pip install -r requirements.txt")

HERE = os.path.dirname(os.path.abspath(__file__))
MODES = {"home": "Ở nhà", "away": "Vắng nhà", "night": "Ban đêm"}
OPS = {"==": operator.eq, "!=": operator.ne, ">": operator.gt, ">=": operator.ge,
       "<": operator.lt, "<=": operator.le}
WARMUP = 3          # giây sau khi kết nối: chỉ nạp retained, không chạy luật


class SafeDict(dict):
    """format_map không lỗi khi thiếu khóa: '{ppm} ppm' → giữ nguyên '{ppm}'."""
    def __missing__(self, key):
        return "{" + key + "}"


def in_window(after: str, before: str) -> bool:
    now = time.strftime("%H:%M")
    if after <= before:
        return after <= now < before
    return now >= after or now < before         # khung giờ qua nửa đêm, vd 18:00 → 06:00


def load_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


class Engine:
    def __init__(self, args):
        self.args = args
        self.p = args.prefix
        self.rules: list[dict] = load_json(args.rules)
        self.scenes: list[dict] = load_json(args.scenes)
        self.devices: dict[str, dict] = {}      # "phòng/thiết bị" -> {type, online, node, state, ...}
        self.mode: str | None = None
        self.rt = {r["id"]: {"since": None, "fired": False, "last": 0.0, "last_ms": None} for r in self.rules}
        self.lock = threading.RLock()
        self.warm_until = float("inf")
        self.stopping = False

        self.t_engine = f"{self.p}/_auto/engine/status"
        self.t_mode = f"{self.p}/_auto/mode/state"
        self.t_notify = f"{self.p}/_auto/notify/event"

        self.client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=args.client_id,
            clean_session=True,
            protocol=mqtt.MQTTv311,
        )
        if args.username:
            self.client.username_pw_set(args.username, args.password)
        # Engine cũng có LWT: dashboard biết ngay khi "bộ não" ngừng hoạt động
        self.client.will_set(self.t_engine, json.dumps({"state": "offline", "reason": "lwt"}), qos=1, retain=True)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.reconnect_delay_set(min_delay=1, max_delay=30)

    # =================================================================
    #  MQTT
    # =================================================================
    def on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            print(f"Kết nối thất bại: {reason_code}")
            return
        print(f"Đã kết nối {self.args.host}:{self.args.port} — {len(self.rules)} luật, {len(self.scenes)} kịch bản")
        client.subscribe([
            (f"{self.p}/+/+/status", 1),
            (f"{self.p}/+/+/state", 1),
            (f"{self.p}/_auto/+/set", 1),
            (self.t_mode, 1),
        ])
        self.warm_until = time.time() + WARMUP
        self.publish_engine()
        threading.Timer(WARMUP, self.after_warmup).start()

    def after_warmup(self):
        with self.lock:
            if self.mode is None:               # broker chưa có chế độ nào được lưu
                self.set_mode("home", "khởi động")
            n = len(self.devices)
            print(f"Đã phát hiện {n} thiết bị qua retained message. Chế độ: {MODES.get(self.mode, self.mode)}")

    def on_message(self, client, userdata, msg):
        parts = msg.topic.split("/")
        if len(parts) != 4 or parts[0] != self.p:
            return
        _, room, dev, kind = parts
        try:
            data = json.loads(msg.payload.decode()) if msg.payload else None
        except ValueError:
            return
        with self.lock:
            if room == "_auto":
                self.on_control(dev, kind, data if isinstance(data, dict) else {})
                return
            if room.startswith("_"):
                return
            key = f"{room}/{dev}"
            if kind == "status":
                if data is None:                # retained bị xóa → thiết bị bị gỡ khỏi hệ thống
                    self.devices.pop(key, None)
                    return
                d = self.devices.setdefault(key, {"room": room, "id": dev, "state": {}})
                d.update(online=data.get("state") != "offline", type=data.get("type"),
                         node=data.get("node"), name=data.get("name", dev))
            elif kind == "state" and isinstance(data, dict):
                self.devices.setdefault(key, {"room": room, "id": dev, "online": True})["state"] = data
            self.evaluate()

    def on_control(self, what: str, kind: str, data: dict):
        src = data.get("from", "?")
        if what == "mode" and kind == "state":
            if data.get("mode") in MODES and data["mode"] != self.mode:
                self.mode = data["mode"]
                self.evaluate()
        elif what == "mode" and kind == "set":
            self.set_mode(data.get("mode"), src)
        elif what == "scene" and kind == "set":
            self.run_scene(data.get("scene"), src)
        elif what == "rule" and kind == "set":
            self.set_rule_enabled(data.get("id"), bool(data.get("enabled", True)), src)

    # =================================================================
    #  Đánh giá luật
    # =================================================================
    def is_online(self, key: str) -> bool:
        d = self.devices.get(key)
        if not d or d.get("online") is False:
            return False
        node = d.get("node")        # thiết bị con của 1 bo mạch (ESP32): offline theo bo mạch
        if node:
            n = self.devices.get(f"{d['room']}/{node}")
            if n and n.get("online") is False:
                return False
        return True

    def check(self, c: dict) -> bool:
        if "device" in c:
            if not self.is_online(c["device"]):
                return False
            v = self.devices[c["device"]].get("state", {}).get(c["field"])
            if v is None:
                return False
            try:
                return OPS[c.get("op", "==")](v, c["value"])
            except TypeError:
                return False
        if "mode" in c:
            modes = c["mode"] if isinstance(c["mode"], list) else [c["mode"]]
            return self.mode in modes
        if "time" in c:
            return in_window(c["time"]["after"], c["time"]["before"])
        if "at" in c:
            return time.strftime("%H:%M") == c["at"]
        return False

    def evaluate(self):
        now = time.time()
        for rule in self.rules:
            rt = self.rt[rule["id"]]
            if not rule.get("enabled", True):
                rt["since"], rt["fired"] = None, False
                continue
            trig = rule["trigger"]
            if not self.check(trig):
                rt["since"], rt["fired"] = None, False
                continue
            if rt["since"] is None:
                rt["since"] = now
            if rt["fired"] or now - rt["since"] < trig.get("for", 0):
                continue
            rt["fired"] = True              # chỉ chạy 1 lần cho tới khi trigger trở lại "sai"
            if now < self.warm_until and not trig.get("for"):
                continue                    # trạng thái có sẵn lúc khởi động không tính là "sự kiện"
            if now - rt["last"] < rule.get("cooldown", 0):
                continue
            if all(self.check(c) for c in rule.get("conditions", [])):
                self.fire(rule)

    def fire(self, rule: dict):
        rt = self.rt[rule["id"]]
        rt["last"], rt["last_ms"] = time.time(), int(time.time() * 1000)
        trig = rule["trigger"]
        ctx = SafeDict()
        if "device" in trig:
            ctx.update(self.devices[trig["device"]].get("state", {}))
            ctx["value"] = ctx.get(trig["field"])
        print(f"[{time.strftime('%H:%M:%S')}] ⚡ Luật “{rule['name']}”")
        self.notify("rule", f"Luật “{rule['name']}” đã chạy", f"rule:{rule['id']}")
        self.publish_engine()
        self.run_actions(rule["actions"], ctx, f"rule:{rule['id']}")

    # =================================================================
    #  Hành động
    # =================================================================
    def run_actions(self, actions: list, ctx: dict, source: str):
        """Chạy trên thread riêng để "delay" không chặn việc nhận message."""
        def worker():
            for a in actions:
                if "delay" in a:
                    time.sleep(a["delay"])
                    continue
                with self.lock:
                    self.do_action(a, ctx, source)
        threading.Thread(target=worker, daemon=True).start()

    def do_action(self, a: dict, ctx: dict, source: str):
        if "set" in a:
            for key in self.select(a):
                self.send(key, a["set"], source)
        elif "scene" in a:
            self.run_scene(a["scene"], source)
        elif "mode" in a:
            self.set_mode(a["mode"], source)
        elif "notify" in a:
            self.notify(a.get("level", "info"), a["notify"].format_map(SafeDict(ctx)), source)

    def select(self, a: dict) -> list[str]:
        """{"device": "living/light"} hoặc chọn theo loại {"type": "light", "room"?, "except"?}."""
        if "device" in a:
            return [a["device"]]
        skip = set(a.get("except", []))
        return [k for k, d in sorted(self.devices.items())
                if d.get("type") == a["type"] and k not in skip and self.is_online(k)
                and (not a.get("room") or d["room"] == a["room"])]

    def send(self, key: str, payload: dict, source: str):
        if not self.is_online(key):
            print(f"  ! {key} đang offline — lệnh có thể bị mất")
        # "from"/"via" chỉ để hiển thị & ghi log: thiết bị bỏ qua các khóa không hiểu
        body = {**payload, "from": "automation", "via": source, "ts": int(time.time() * 1000)}
        self.client.publish(f"{self.p}/{key}/set", json.dumps(body), qos=1)
        print(f"  → {key}/set {json.dumps(payload, ensure_ascii=False)}")

    def run_scene(self, scene_id: str, source: str):
        scene = next((s for s in self.scenes if s["id"] == scene_id), None)
        if not scene:
            print(f"Không có kịch bản '{scene_id}'")
            return
        print(f"[{time.strftime('%H:%M:%S')}] 🎬 Kịch bản “{scene['name']}” (từ {source})")
        self.notify("info", f"Chạy kịch bản “{scene['name']}”", source)
        self.run_actions(scene["actions"], SafeDict(), f"scene:{scene_id}")

    def set_mode(self, mode: str, source: str):
        if mode not in MODES:
            return
        changed = mode != self.mode
        self.mode = mode
        self.client.publish(self.t_mode, json.dumps({"mode": mode, "by": source, "ts": int(time.time() * 1000)}),
                            qos=1, retain=True)
        if changed:
            print(f"[{time.strftime('%H:%M:%S')}] 🏠 Chế độ: {MODES[mode]} (từ {source})")
            self.notify("info", f"Chuyển sang chế độ “{MODES[mode]}”", source)
            self.evaluate()

    def set_rule_enabled(self, rule_id: str, enabled: bool, source: str):
        rule = next((r for r in self.rules if r["id"] == rule_id), None)
        if not rule:
            return
        rule["enabled"] = enabled
        with open(self.args.rules, "w", encoding="utf-8") as f:   # lưu lại để lần sau khởi động vẫn giữ
            json.dump(self.rules, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print(f"Luật “{rule['name']}”: {'BẬT' if enabled else 'TẮT'} (từ {source})")
        self.publish_engine()

    def notify(self, level: str, text: str, source: str):
        self.client.publish(self.t_notify, json.dumps(
            {"level": level, "text": text, "source": source, "ts": int(time.time() * 1000)},
            ensure_ascii=False), qos=1)
        if level != "rule":
            print(f"  🔔 [{level}] {text}")

    def publish_engine(self, state: str = "online", reason: str | None = None):
        payload = {
            "state": state,
            "ts": int(time.time() * 1000),
            "modes": MODES,
            "rules": [{"id": r["id"], "name": r["name"], "description": r.get("description", ""),
                       "enabled": r.get("enabled", True), "last_fired": self.rt[r["id"]]["last_ms"]}
                      for r in self.rules],
            "scenes": [{"id": s["id"], "name": s["name"], "icon": s.get("icon", "")} for s in self.scenes],
        }
        if reason:
            payload["reason"] = reason
        return self.client.publish(self.t_engine, json.dumps(payload, ensure_ascii=False), qos=1, retain=True)

    # =================================================================
    def run(self):
        self.client.connect_async(self.args.host, self.args.port, keepalive=30)
        self.client.loop_start()
        while not self.stopping:
            time.sleep(1)
            with self.lock:             # luật có "for" hoặc "at" cần được kiểm tra theo thời gian
                self.evaluate()

    def shutdown(self):
        self.stopping = True
        print("Dừng automation (graceful → không phát LWT)")
        if self.client.is_connected():
            info = self.publish_engine("offline", "graceful")
            try:
                info.wait_for_publish(timeout=2)
            except (ValueError, RuntimeError):
                pass
        self.client.disconnect()
        self.client.loop_stop()


def main():
    p = argparse.ArgumentParser(description="Automation engine cho nhà thông minh (MQTT)")
    p.add_argument("--host", default=os.getenv("MQTT_HOST", "localhost"))
    p.add_argument("--port", type=int, default=int(os.getenv("MQTT_PORT", 1883)))
    p.add_argument("--username", default=os.getenv("MQTT_USER"))
    p.add_argument("--password", default=os.getenv("MQTT_PASS"))
    p.add_argument("--prefix", default="home")
    p.add_argument("--client-id", default="automation-engine")
    p.add_argument("--rules", default=os.path.join(HERE, "rules.json"))
    p.add_argument("--scenes", default=os.path.join(HERE, "scenes.json"))
    args = p.parse_args()

    engine = Engine(args)

    def stop(*_):
        engine.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    engine.run()


if __name__ == "__main__":
    main()
