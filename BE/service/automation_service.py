"""
Service của automation engine — "bộ não" chạy luật và kịch bản.

Lớp này KHÔNG biết MQTT client là gì: nó nhận message đã được parse từ controller và gửi đi
bằng hàm `publish` được tiêm vào. Nhờ vậy có thể test luật mà không cần broker.

Luật (BE/config/rules.json):
  trigger    : điều kiện kích hoạt — chỉ chạy ở SƯỜN LÊN (sai → đúng), có thể kèm "for": giữ N giây
  conditions : các điều kiện phụ, tất cả phải đúng tại thời điểm kích hoạt
  actions    : set / scene / mode / notify / delay, chạy tuần tự
  cooldown   : số giây tối thiểu giữa 2 lần chạy
"""
from __future__ import annotations

import json
import threading
import time

from BE.service.rule_helpers import MODES, OPS, WARMUP, SafeDict, in_window, load_json


class AutomationService:
    def __init__(self, prefix: str, rules_path: str, scenes_path: str, publish):
        """publish(topic, payload, qos=…, retain=…) — thường là client.publish của paho."""
        self.p = prefix
        self.rules_path = rules_path
        self.publish = publish
        self.rules: list[dict] = load_json(rules_path)
        self.scenes: list[dict] = load_json(scenes_path)
        self.devices: dict[str, dict] = {}      # "phòng/thiết bị" -> {type, online, node, state, ...}
        self.mode: str | None = None
        self.rt = {r["id"]: {"since": None, "fired": False, "last": 0.0, "last_ms": None} for r in self.rules}
        self.lock = threading.RLock()
        self.warm_until = float("inf")

        self.t_engine = f"{self.p}/_auto/engine/status"
        self.t_mode = f"{self.p}/_auto/mode/state"
        self.t_notify = f"{self.p}/_auto/notify/event"

    # =================================================================
    #  Vòng đời
    # =================================================================
    def begin_warmup(self):
        """Gọi mỗi lần kết nối broker: nạp retained trong WARMUP giây rồi mới chạy luật."""
        self.warm_until = time.time() + WARMUP
        self.publish_engine()
        threading.Timer(WARMUP, self.after_warmup).start()

    def after_warmup(self):
        with self.lock:
            if self.mode is None:               # broker chưa có chế độ nào được lưu
                self.set_mode("home", "khởi động")
            n = len(self.devices)
            print(f"Đã phát hiện {n} thiết bị qua retained message. Chế độ: {MODES.get(self.mode, self.mode)}")

    def tick(self):
        """Gọi mỗi giây: luật có "for" hoặc "at" cần được kiểm tra theo thời gian."""
        with self.lock:
            self.evaluate()

    # =================================================================
    #  Nhận message (đã parse bởi controller)
    # =================================================================
    def handle_message(self, room: str, dev: str, kind: str, data):
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
        self.publish(f"{self.p}/{key}/set", json.dumps(body), qos=1)
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
        self.publish(self.t_mode, json.dumps({"mode": mode, "by": source, "ts": int(time.time() * 1000)}),
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
        with open(self.rules_path, "w", encoding="utf-8") as f:   # lưu lại để lần sau khởi động vẫn giữ
            json.dump(self.rules, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print(f"Luật “{rule['name']}”: {'BẬT' if enabled else 'TẮT'} (từ {source})")
        self.publish_engine()

    def notify(self, level: str, text: str, source: str):
        self.publish(self.t_notify, json.dumps(
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
        return self.publish(self.t_engine, json.dumps(payload, ensure_ascii=False), qos=1, retain=True)
