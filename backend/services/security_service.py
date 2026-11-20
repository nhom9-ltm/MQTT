"""
Hệ thống an ninh (báo động chống trộm) — chạy bên trong automation engine.

Trạng thái (phát retained lên home/_auto/security/state để dashboard và engine khởi động lại đều biết):

    disarmed ──(chế độ Vắng nhà)──▶ arming ──(hết exit_delay)──▶ armed_away ─┐
        ▲      (chế độ Ban đêm)───────────────────────────────▶ armed_night ─┤
        │                                                                     │ cảm biến vùng "entry" (cửa)
        │                                          ┌──────────── pending ◀────┘
        │                                          │  (hết entry_delay mà chưa nhập PIN)
        └──────(nhập đúng PIN)────────────── triggered ◀── cảm biến vùng "interior" khi armed_away / nút khẩn cấp

  * Bật an ninh: tự động khi chế độ nhà chuyển sang away / night (không cần PIN).
  * Tắt an ninh: phải nhập PIN (home/_auto/security/set {"action": "disarm", "pin": "1234"}).
    Riêng Ban đêm → Ở nhà (ví dụ kịch bản "Buổi sáng") tự tắt, vì người trong nhà mới chuyển được.
  * Vùng cảm biến: entry   — cửa: cho entry_delay giây để nhập PIN rồi mới báo động
                   interior — trong nhà: báo động NGAY khi vắng nhà; ban đêm bỏ qua (người nhà đi lại)
                   perimeter— ngoài nhà: chỉ cảnh báo, không báo động
  * Khi báo động: thông báo critical (notifier gửi ra điện thoại), chạy các hành động "on_trigger" (bật đèn...),
    nhắc lại mỗi repeat_notify giây; sau alarm_duration giây tự quay về trạng thái canh gác.
  * Cảm biến mất kết nối khi đang canh gác → cảnh báo (có thể bị phá).
  * Giả lập có người ở nhà: khi vắng nhà trong khung giờ "presence", bật/tắt ngẫu nhiên vài đèn.

Lớp này không biết MQTT: engine tiêm các hàm publish_state / notify / run_actions / send và đồng hồ `clock`,
nên test được mà không cần broker (backend/tests/test_security.py). Mọi hàm được gọi khi engine đang giữ lock.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import random
import secrets
import time
from datetime import datetime

ARMED = ("armed_away", "armed_night")
ACTIVE = ("arming", "armed_away", "pending", "triggered")      # đang canh gác "cứng": đổi chế độ phải có PIN
STATES = ("disarmed",) + ACTIVE + ("armed_night",)
LABEL = {"disarmed": "Tắt", "arming": "Đang bật (chờ ra khỏi nhà)", "armed_away": "Canh gác — vắng nhà",
         "armed_night": "Canh gác — ban đêm", "pending": "Cửa mở — chờ nhập PIN", "triggered": "BÁO ĐỘNG"}
ZONES = ("entry", "interior", "perimeter")
PBKDF2_ROUNDS = 100_000
DEFAULTS = {"exit_delay": 20, "entry_delay": 20, "alarm_duration": 600, "repeat_notify": 120,
            "max_attempts": 5, "lockout": 60, "sensors": [], "on_trigger": [], "presence": {"enabled": False}}


def hash_pin(pin: str, salt: str | None = None) -> dict:
    salt = salt or secrets.token_hex(8)
    digest = hashlib.pbkdf2_hmac("sha256", pin.encode(), bytes.fromhex(salt), PBKDF2_ROUNDS).hex()
    return {"salt": salt, "hash": digest}


def check_pin(pin, stored: dict) -> bool:
    if not isinstance(pin, str) or not pin or not stored:
        return False
    return hmac.compare_digest(hash_pin(pin, stored["salt"])["hash"], stored["hash"])


def valid_pin(pin) -> bool:
    return isinstance(pin, str) and pin.isdigit() and 4 <= len(pin) <= 8


def load_config(path: str) -> dict:
    """Thiếu file thì an ninh vẫn chạy với mặc định (không cảm biến nào) — engine không bị dừng vì thiếu cấu hình."""
    if not os.path.exists(path):
        print(f"Không có {path} — an ninh chạy với cấu hình mặc định (chưa gán cảm biến)")
        return {}
    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)
    for s in cfg.get("sensors", []):
        if s.get("zone") not in ZONES or not s.get("device") or "field" not in s:
            raise ValueError(f"security.json: cảm biến không hợp lệ {s} (zone phải là {', '.join(ZONES)})")
    return cfg


def save_pin(path: str, pin: str) -> None:
    """Đổi mã PIN: chỉ ghi lại khóa "pin" (salt + hash), giữ nguyên các cấu hình khác."""
    if not valid_pin(pin):
        raise ValueError("PIN phải gồm 4–8 chữ số")
    cfg = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            cfg = json.load(f)
    cfg["pin"] = hash_pin(pin)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)


class SecurityService:
    def __init__(self, cfg: dict, *, publish_state, notify, run_actions, send, clock=time.time, rng=None):
        self.cfg = {**DEFAULTS, **(cfg or {})}
        self.sensors = {s["device"]: s for s in self.cfg["sensors"]}
        self.publish_state = publish_state      # (dict) -> None
        self.notify = notify                    # (level, text, source) -> None
        self.run_actions = run_actions          # (actions, source) -> None
        self.send = send                        # (key, payload, source) -> None
        self.clock = clock
        self.rng = rng or random.Random()

        self.state = "disarmed"
        self.arm_mode: str | None = None        # away | night — để quay lại sau khi hết báo động
        self.since = self.clock()
        self.deadline: float | None = None      # hết exit/entry delay hoặc hết thời gian báo động
        self.trigger: dict | None = None
        self.by = "khởi động"
        self.attempts = 0
        self.locked_until = 0.0
        self.next_repeat = 0.0
        self.last_values: dict[str, object] = {}
        self.perimeter_last: dict[str, float] = {}
        self.presence_on: set[str] = set()
        self.presence_next = 0.0

    # ------------------------------------------------------------------ trạng thái
    def describe(self) -> dict:
        """Thông tin tĩnh cho dashboard (gửi kèm engine/status): cảm biến được canh và thời gian chờ."""
        return {"sensors": [{"device": s["device"], "name": s["name"], "zone": s["zone"]} for s in self.cfg["sensors"]],
                "exit_delay": self.cfg["exit_delay"], "entry_delay": self.cfg["entry_delay"],
                "has_pin": bool(self.cfg.get("pin"))}

    def snapshot(self) -> dict:
        now = self.clock()
        return {
            "state": self.state, "label": LABEL[self.state], "arm_mode": self.arm_mode, "by": self.by,
            "since": int(self.since * 1000),
            "remaining": max(0, round(self.deadline - now)) if self.deadline and self.state in ("arming", "pending") else None,
            "trigger": self.trigger,
            "locked_until": int(self.locked_until * 1000) if self.locked_until > now else None,
            "ts": int(now * 1000),
        }

    def _set(self, state: str, source: str, deadline: float | None = None):
        self.state, self.by, self.since, self.deadline = state, source, self.clock(), deadline
        if state in ("disarmed",) + ARMED:
            self.trigger = None
        self.publish_state(self.snapshot())

    def restore(self, data: dict):
        """Khôi phục từ retained message khi engine khởi động lại (đang canh gác thì vẫn canh gác)."""
        if not isinstance(data, dict) or data.get("state") not in STATES:
            return
        self.state, self.arm_mode = data["state"], data.get("arm_mode")
        self.by, self.trigger = data.get("by", "?"), data.get("trigger")
        self.since = (data.get("since") or 0) / 1000 or self.clock()
        if data.get("remaining") is not None and self.state in ("arming", "pending"):
            self.deadline = data["ts"] / 1000 + data["remaining"]
        elif self.state == "triggered":
            self.deadline = self.since + self.cfg["alarm_duration"]
        print(f"An ninh khôi phục: {LABEL[self.state]}")

    # ------------------------------------------------------------------ liên kết với chế độ nhà
    def mode_allowed(self, mode: str) -> bool:
        """Đang canh gác vắng nhà / báo động thì chỉ được giữ chế độ Vắng nhà; muốn đổi phải tắt bằng PIN trước."""
        return self.state not in ACTIVE or mode == "away"

    def scene_allowed(self, scene: dict) -> bool:
        return all(self.mode_allowed(a["mode"]) for a in scene.get("actions", []) if "mode" in a)

    def on_mode(self, mode: str, source: str):
        if mode == "away" and self.state not in ACTIVE:
            self.arm_mode = "away"
            self._set("arming", source, self.clock() + self.cfg["exit_delay"])
            open_now = [s["name"] for k, s in self.sensors.items()
                        if s["zone"] in ("entry", "interior") and self.last_values.get(k) == s["value"]]
            extra = f" Lưu ý đang kích hoạt: {', '.join(open_now)}." if open_now else ""
            self.notify("info", f"Bật an ninh sau {self.cfg['exit_delay']} giây — hãy ra khỏi nhà.{extra}", "security")
        elif mode == "night" and self.state == "disarmed":
            self.arm_mode = "night"
            self._set("armed_night", source)
            self.notify("info", "Đã bật an ninh ban đêm (canh cửa chính)", "security")
        elif mode == "home" and self.state == "armed_night":
            self.arm_mode = None
            self._set("disarmed", source)
            self.notify("info", "Đã tắt an ninh ban đêm", "security")

    # ------------------------------------------------------------------ lệnh từ dashboard
    def disarm(self, pin, source: str) -> bool:
        now = self.clock()
        if self.state == "disarmed":
            return True
        if now < self.locked_until:
            self.notify("warn", f"Đang khóa nhập PIN, thử lại sau {round(self.locked_until - now)} giây", "security")
            return False
        if self.cfg.get("pin") and not check_pin(pin, self.cfg["pin"]):    # chưa đặt PIN thì không đòi PIN
            self.attempts += 1
            left = self.cfg["max_attempts"] - self.attempts
            if left <= 0:
                self.attempts = 0
                self.locked_until = now + self.cfg["lockout"]
                self.notify("critical", f"Nhập sai PIN {self.cfg['max_attempts']} lần — khóa {self.cfg['lockout']} giây", "security")
                self.publish_state(self.snapshot())
            else:
                self.notify("warn", f"Sai mã PIN (còn {left} lần thử)", "security")
            return False
        was = self.state
        self.attempts, self.arm_mode = 0, None
        self._set("disarmed", source)
        self.notify("info" if was != "triggered" else "warn",
                    "Đã tắt báo động" if was == "triggered" else "Đã tắt an ninh", "security")
        return True

    def panic(self, source: str):
        self._trigger({"device": None, "name": "Nút khẩn cấp"}, source)

    # ------------------------------------------------------------------ cảm biến
    def on_state(self, key: str, state: dict, warm: bool = False):
        """Mỗi state của thiết bị. warm=True: đang nạp retained lúc khởi động — chỉ ghi nhận, không tính là sự kiện."""
        s = self.sensors.get(key)
        if not s or not isinstance(state, dict):
            return
        value = state.get(s["field"])
        rising = value == s["value"] and self.last_values.get(key) != s["value"]
        self.last_values[key] = value
        if warm or not rising:
            return
        zone, st = s["zone"], self.state
        if zone == "perimeter":
            if st in ARMED + ("pending", "triggered") and self.clock() - self.perimeter_last.get(key, 0) >= 60:
                self.perimeter_last[key] = self.clock()
                self.notify("warn", f"{s['name']} khi đang bật an ninh", "security")
            return
        if zone == "entry" and st in ARMED:
            self.trigger = {"device": key, "name": s["name"]}
            self._set("pending", f"sensor:{key}", self.clock() + self.cfg["entry_delay"])
            self.notify("warn", f"{s['name']} được mở — nhập PIN trong {self.cfg['entry_delay']} giây", "security")
        elif zone == "interior" and st == "armed_away":
            self._trigger({"device": key, "name": s["name"]}, f"sensor:{key}")
        # interior khi đang pending: coi như người vừa vào cửa đi tiếp — vẫn chờ PIN

    def on_status(self, key: str, online: bool, warm: bool = False):
        s = self.sensors.get(key)
        if s and not online and not warm and self.state != "disarmed":
            self.notify("critical" if self.state in ("armed_away", "triggered") else "warn",
                        f"{s['name']} mất kết nối khi đang bật an ninh — kiểm tra ngay!", "security")

    def _trigger(self, trigger: dict, source: str):
        if self.state == "triggered":
            return
        self.trigger = trigger
        self._set("triggered", source, self.clock() + self.cfg["alarm_duration"])
        self.next_repeat = self.clock() + self.cfg["repeat_notify"]
        self.notify("critical", f"BÁO ĐỘNG: {trigger['name']} lúc {datetime.fromtimestamp(self.clock()):%H:%M:%S}!", "security")
        if self.cfg["on_trigger"]:
            self.run_actions(self.cfg["on_trigger"], "security")

    # ------------------------------------------------------------------ mỗi giây
    def tick(self):
        now = self.clock()
        if self.locked_until and now >= self.locked_until:
            self.locked_until = 0.0
            self.publish_state(self.snapshot())
        if self.state == "arming" and now >= self.deadline:
            self._set("armed_away", "exit_delay")
            self.notify("info", "An ninh đã bật — đang canh gác nhà", "security")
        elif self.state == "pending" and now >= self.deadline:
            self._trigger(self.trigger or {"device": None, "name": "Cửa"}, "entry_delay")
        elif self.state == "triggered":
            if now >= self.deadline:
                # nút khẩn cấp khi chưa bật an ninh -> quay về "Tắt"; còn lại tiếp tục canh gác như trước
                back = {"away": "armed_away", "night": "armed_night"}.get(self.arm_mode, "disarmed")
                self._set(back, "alarm_duration")
                self.notify("warn", "Hết thời gian báo động" + (" — hệ thống tiếp tục canh gác" if back != "disarmed" else ""),
                            "security")
            elif now >= self.next_repeat:
                self.next_repeat = now + self.cfg["repeat_notify"]
                self.notify("critical", f"Vẫn đang BÁO ĐỘNG ({self.trigger['name'] if self.trigger else '?'}) — chưa ai tắt", "security")
        self._presence(now)

    def _in_window(self, now: float) -> bool:
        p = self.cfg["presence"]
        hm = datetime.fromtimestamp(now).strftime("%H:%M")
        a, b = p.get("after", "18:00"), p.get("before", "23:00")
        return a <= hm < b if a <= b else hm >= a or hm < b

    def _presence(self, now: float):
        p = self.cfg["presence"]
        if not p.get("enabled") or not p.get("lights"):
            return
        active = self.state == "armed_away" and self._in_window(now)
        if not active:
            if self.presence_on and self.state == "armed_away":       # hết khung giờ: tắt các đèn đã bật giả
                for key in sorted(self.presence_on):
                    self.send(key, {"on": False}, "security:presence")
                self.presence_on.clear()
            elif self.state != "armed_away":
                self.presence_on.clear()                               # chủ nhà đã về: để nguyên đèn
            self.presence_next = 0.0
            return
        if now < self.presence_next:
            return
        key = self.rng.choice(p["lights"])
        on = key not in self.presence_on
        self.send(key, {"on": on}, "security:presence")
        (self.presence_on.add if on else self.presence_on.discard)(key)
        self.presence_next = now + self.rng.uniform(p.get("min_s", 300), p.get("max_s", 900))
