"""
Service của automation engine — "bộ não" chạy luật và kịch bản.

Lớp này KHÔNG biết MQTT client là gì: nó nhận message đã được parse từ controller và gửi đi
bằng hàm `publish` được tiêm vào. Nhờ vậy có thể test luật mà không cần broker.

Luật (backend/config/rules.json):
  trigger    : điều kiện kích hoạt — chỉ chạy ở SƯỜN LÊN (sai → đúng), có thể kèm "for": giữ N giây
  conditions : các điều kiện phụ, tất cả phải đúng tại thời điểm kích hoạt
  actions    : set / scene / mode / notify / delay, chạy tuần tự
  cooldown   : số giây tối thiểu giữa 2 lần chạy
"""
from __future__ import annotations

import json
import os
import threading
import time

from backend.repositories.rule_repository import save_rules
from backend.repositories.scene_repository import custom_path_for, load_custom_scenes, save_custom_scenes
from backend.services.rule_helpers import MODES, OPS, WARMUP, SafeDict, in_window, load_json
from backend.services.scene_validation import SceneError, validate_scene


class AutomationService:
    def __init__(self, prefix: str, rules_path: str, scenes_path: str, publish, custom_scenes_path: str | None = None):
        """publish(topic, payload, qos=…, retain=…) — thường là client.publish của paho.

        Kịch bản viết tay nằm ở scenes_path; kịch bản người dùng tạo từ dashboard được lưu riêng ở
        custom_scenes_path (mặc định: <scenes_path>.custom.json) và nạp chung vào self.scenes.
        """
        self.p = prefix
        self.rules_path = rules_path
        self.publish = publish
        self.rules: list[dict] = load_json(rules_path)
        self.rules_mtime = self._mtime()
        self.custom_scenes_path = custom_scenes_path or custom_path_for(scenes_path)
        base: list[dict] = load_json(scenes_path)
        taken = {s["id"] for s in base}
        custom = [{**s, "custom": True} for s in load_custom_scenes(self.custom_scenes_path) if s["id"] not in taken]
        self.scenes: list[dict] = base + custom
        self.devices: dict[str, dict] = {}      # "phòng/thiết bị" -> {type, online, node, state, ...}
        self.locked: set[str] = set()           # thiết bị bị quản trị viên khóa (home/_admin/locked/state)
        self.mode: str | None = None
        self.rt = {r["id"]: {"since": None, "fired": False, "last": 0.0, "last_ms": None} for r in self.rules}
        self.lock = threading.RLock()
        self.warm_until = float("inf")
        # Số thứ tự "đợt điều khiển hiện hành": mỗi lần chạy kịch bản hoặc người dùng đổi chế độ thì tăng lên,
        # các kịch bản cũ còn đang chạy dở (ví dụ đang chờ delay) sẽ tự dừng thay vì ghi đè lên kết quả mới.
        self.scene_gen = 0

        self.t_engine = f"{self.p}/_auto/engine/status"
        self.t_mode = f"{self.p}/_auto/mode/state"
        self.t_notify = f"{self.p}/_auto/notify/event"
        self.t_locked = f"{self.p}/_admin/locked/state"

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
        """Gọi mỗi giây: nạp lại luật nếu rules.json đổi, rồi kiểm tra luật có "for" hoặc "at" theo thời gian."""
        with self.lock:
            self.reload_rules_if_changed()
            self.evaluate()

    def _mtime(self) -> float:
        try:
            return os.path.getmtime(self.rules_path)
        except OSError:
            return 0.0

    def reload_rules_if_changed(self):
        """Quản trị viên thêm/sửa/xóa luật trên trang quản trị (API ghi rules.json) → engine nạp lại ngay.

        File lỗi thì giữ nguyên bộ luật đang chạy. Luật cũ giữ trạng thái chạy (lần cuối, cooldown) theo mã luật.
        """
        mtime = self._mtime()
        if mtime == self.rules_mtime:
            return
        self.rules_mtime = mtime
        try:
            rules = load_json(self.rules_path)
            if not isinstance(rules, list):
                raise ValueError("không phải danh sách luật")
        except (OSError, ValueError) as e:
            print(f"Không nạp lại được {self.rules_path}: {e} — giữ bộ luật cũ")
            return
        self.rt = {r["id"]: self.rt.get(r["id"]) or {"since": None, "fired": False, "last": 0.0, "last_ms": None}
                   for r in rules}
        self.rules = rules
        print(f"[{time.strftime('%H:%M:%S')}] ↻ Nạp lại {len(rules)} luật từ {os.path.basename(self.rules_path)}")
        self.publish_engine()

    # =================================================================
    #  Nhận message (đã parse bởi controller)
    # =================================================================
    def handle_message(self, room: str, dev: str, kind: str, data):
        with self.lock:
            if room == "_admin" and dev == "locked" and kind == "state":
                self.locked = set(data.get("devices", [])) if isinstance(data, dict) else set()
                print(f"Thiết bị bị khóa: {', '.join(sorted(self.locked)) or 'không có'}")
                return
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
            if data.get("mode") not in MODES:
                self.notify("warn", f"Chế độ không hợp lệ: {data.get('mode')!r}", src)
                return
            mode = data["mode"]
            # Người dùng tự chọn chế độ -> chạy HẲN kịch bản gắn với chế độ đó (khai báo "for_mode" trong scenes.json):
            # Ở nhà = "Về nhà", Vắng nhà = "Ra khỏi nhà", Ban đêm = "Đi ngủ". Kịch bản tự đặt chế độ ở đúng bước của nó.
            # Chỉ áp dụng ở đây (lệnh từ người dùng); kịch bản/luật đổi chế độ qua set_mode nên không bị chạy lặp.
            scene = next((s for s in self.scenes if s.get("for_mode") == mode), None)
            if scene and mode != self.mode:
                self.run_scene(scene["id"], src)
            else:                           # đã ở chế độ này (hoặc chưa có kịch bản gắn): không điều khiển thiết bị
                self.scene_gen += 1         # nhưng vẫn hủy kịch bản đang chờ đổi chế độ
                self.set_mode(mode, src)
        elif what == "scene" and kind == "set":
            if "add" in data:                       # {"add": {name, icon, actions}} — thêm kịch bản mới từ dashboard
                self.add_scene(data["add"], src)
            else:
                self.run_scene(data.get("scene"), src)
        elif what == "rule" and kind == "set":
            self.set_rule_enabled(data.get("id"), bool(data.get("enabled", True)), src)

    # =================================================================
    #  Đánh giá luật
    # =================================================================
    def is_online(self, key: str) -> bool:
        """Thiết bị bị khóa coi như không dùng được: luật không kích hoạt theo nó, lệnh không gửi tới nó."""
        if key in self.locked:
            return False
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
    def _wait(self, seconds: float, gen) -> bool:
        """Chờ `seconds` giây; trả False nếu trong lúc chờ có kịch bản/chế độ mới thay thế (gen đã đổi)."""
        end = time.time() + seconds
        while True:
            if gen is not None and gen != self.scene_gen:
                return False
            left = end - time.time()
            if left <= 0:
                return True
            time.sleep(min(0.1, left))

    def run_actions(self, actions: list, ctx: dict, source: str, gen=None, report=None, label: str = ""):
        """Chạy trên thread riêng để "delay" không chặn việc nhận message.

        gen    : số thứ tự đợt điều khiển (chỉ kịch bản truyền vào); bị thay thế thì dừng ngay, không chạy tiếp.
        report : danh sách thiết bị không điều khiển được; cuối kịch bản sẽ báo lên dashboard (xem _finish_scene).
        """
        def worker():
            for a in actions:
                if gen is not None and gen != self.scene_gen:
                    return
                if "delay" in a:
                    if not self._wait(a["delay"], gen):
                        return
                    continue
                with self.lock:
                    if gen is not None and gen != self.scene_gen:
                        return
                    self.do_action(a, ctx, source, report)
            if report is not None:
                with self.lock:
                    self._finish_scene(label, report, source)
        threading.Thread(target=worker, daemon=True).start()

    def do_action(self, a: dict, ctx: dict, source: str, report=None):
        if "set" in a:
            for key in self.select(a):
                self.send(key, a["set"], source)
            if report is not None:
                report.extend(self.unreachable(a))
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

    def unreachable(self, a: dict) -> list[str]:
        """Thiết bị mà hành động `a` nhắm tới nhưng đang offline (lệnh chọn theo loại bỏ qua chúng, lệnh gán thẳng
        thiết bị vẫn gửi nhưng có thể bị mất) — dùng để báo cho người dùng biết kịch bản chưa áp dụng đủ."""
        if "device" in a:
            return [] if self.is_online(a["device"]) else [a["device"]]
        skip = set(a.get("except", []))
        return [k for k, d in sorted(self.devices.items())
                if d.get("type") == a["type"] and k not in skip and not self.is_online(k)
                and (not a.get("room") or d["room"] == a["room"])]

    def _finish_scene(self, label: str, report: list, source: str):
        """Cuối kịch bản: nếu có thiết bị không điều khiển được thì báo lên dashboard (khóa cửa → mức nghiêm trọng)."""
        missed = sorted(set(report))
        if not missed:
            return
        locks = [k for k in missed if self.devices.get(k, {}).get("type") == "lock"]
        level = "critical" if locks else "warn"
        extra = " — CỬA CHƯA ĐƯỢC KHÓA, hãy kiểm tra thủ công!" if locks else ""
        self.notify(level, f"Kịch bản “{label}” chưa điều khiển được (đang offline): {', '.join(missed)}{extra}", source)

    def send(self, key: str, payload: dict, source: str):
        if key in self.locked:
            print(f"  ! {key} đang bị khóa — bỏ qua lệnh")
            return
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
            self.notify("warn", f"Không có kịch bản “{scene_id}”", source)
            return
        print(f"[{time.strftime('%H:%M:%S')}] 🎬 Kịch bản “{scene['name']}” (từ {source})")
        self.notify("info", f"Chạy kịch bản “{scene['name']}”", source)
        self.scene_gen += 1                 # kịch bản mới thay thế mọi kịch bản cũ đang chạy dở
        self.run_actions(scene["actions"], SafeDict(), f"scene:{scene_id}",
                         gen=self.scene_gen, report=[], label=scene["name"])

    def add_scene(self, data, source: str):
        """Thêm kịch bản do người dùng tạo: kiểm tra -> lưu file -> nạp vào engine -> báo cho mọi dashboard.

        Sai dữ liệu hoặc không lưu được thì KHÔNG thêm gì và báo lý do lên dashboard.
        """
        custom = [s for s in self.scenes if s.get("custom")]
        try:
            scene = validate_scene(
                data, self.devices, MODES,
                taken_ids={s["id"] for s in self.scenes},
                taken_names={s["name"].casefold() for s in self.scenes},
                custom_count=len(custom))
        except SceneError as e:
            self.notify("warn", f"Không thêm được kịch bản: {e}", source)
            return
        scene["custom"] = True
        try:
            save_custom_scenes(self.custom_scenes_path,
                               [{k: v for k, v in s.items() if k != "custom"} for s in custom + [scene]])
        except OSError as e:
            self.notify("warn", f"Không lưu được kịch bản “{scene['name']}”: {e}", source)
            return
        self.scenes.append(scene)
        print(f"[{time.strftime('%H:%M:%S')}] ➕ Thêm kịch bản “{scene['name']}” ({len(scene['actions'])} hành động, từ {source})")
        self.publish_engine()
        self.notify("info", f"Đã thêm kịch bản “{scene['name']}”", source)

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
        save_rules(self.rules, self.rules_path)     # lưu lại để lần sau khởi động vẫn giữ
        self.rules_mtime = self._mtime()            # tự ghi thì không cần nạp lại
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
            "scenes": [{"id": s["id"], "name": s["name"], "icon": s.get("icon", ""), "custom": bool(s.get("custom"))}
                       for s in self.scenes],
        }
        if reason:
            payload["reason"] = reason
        return self.publish(self.t_engine, json.dumps(payload, ensure_ascii=False), qos=1, retain=True)
