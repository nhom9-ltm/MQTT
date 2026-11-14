"""Căn nhà giả lập: danh sách phòng/thiết bị và vòng mô phỏng vật lý mỗi giây."""
from __future__ import annotations

import math
import threading
import time

from backend.simulator.devices import (AirCon, Climate, Curtain, Device, Door, Fan, Gas, Light, Lock,
                             Motion, Plug)

# =====================================================================
#  Căn nhà
# =====================================================================
HOUSE = [
    ("living", "Phòng khách", [
        (Climate, "climate", "Nhiệt độ & độ ẩm", {"base_t": 28.0, "base_h": 62.0}),
        (Light, "light", "Đèn trần", {"watt": 18, "dimmable": True}),
        (Fan, "fan", "Quạt đứng", {}),
        (AirCon, "ac", "Điều hòa", {}),
        (Curtain, "curtain", "Rèm cửa sổ", {}),
        (Plug, "tv-plug", "Ổ cắm TV", {"watt": 95, "on": True}),
        (Motion, "motion", "Cảm biến chuyển động", {"rate": 1 / 90}),
    ]),
    ("bedroom", "Phòng ngủ", [
        (Climate, "climate", "Nhiệt độ & độ ẩm", {"base_t": 27.0, "base_h": 60.0}),
        (Light, "light", "Đèn ngủ", {"watt": 12, "dimmable": True}),
        (AirCon, "ac", "Điều hòa", {}),
        (Curtain, "curtain", "Rèm cửa sổ", {}),
    ]),
    ("kitchen", "Nhà bếp", [
        (Climate, "climate", "Nhiệt độ & độ ẩm", {"base_t": 30.0, "base_h": 70.0}),
        (Light, "light", "Đèn bếp", {"watt": 15}),
        (Fan, "hood-fan", "Quạt hút mùi", {}),
        (Plug, "stove-plug", "Bếp điện", {"watt": 1200, "cycle": True}),
        (Gas, "gas", "Cảm biến khí gas", {}),
    ]),
    ("entrance", "Lối vào", [
        (Lock, "lock", "Khóa cửa chính", {}),
        (Door, "door", "Cảm biến cửa chính", {}),
        (Motion, "motion", "Cảm biến chuyển động", {"rate": 1 / 150}),
        (Light, "porch-light", "Đèn hiên", {"watt": 10}),
    ]),
]


class House:
    def __init__(self, args):
        self.args = args
        self.lock = threading.RLock()       # callback paho chạy trên thread khác vòng mô phỏng
        self.stopping = False
        self.devices: list[Device] = []
        only = set(args.rooms.split(",")) if args.rooms else None
        for room, room_name, items in HOUSE:
            if only and room not in only:
                continue
            for cls, dev_id, name, opts in items:
                self.devices.append(cls(self, room, room_name, dev_id, name, **opts))
        for spec in getattr(args, "extra", None) or []:
            self.devices.append(self.extra_device(spec))
        self._index = {(d.room, d.TYPE): d for d in reversed(self.devices)}

    EXTRA_TYPES = {cls.TYPE: cls for cls in (Light, Fan, AirCon, Curtain, Plug, Lock, Door, Motion, Gas, Climate)}

    def extra_device(self, spec: str) -> Device:
        """--extra "phòng/mã:loại:Tên" → một thiết bị giả lập thêm, vd "living/a1:fan:Quạt trần"."""
        try:
            key, type_, name = spec.split(":", 2)
            room, dev_id = key.split("/")
        except ValueError:
            raise SystemExit(f'--extra sai định dạng: {spec!r} (đúng: "phòng/mã:loại:Tên", vd "living/a1:fan:Quạt trần")')
        cls = self.EXTRA_TYPES.get(type_.strip())
        if not cls:
            raise SystemExit(f"--extra: loại “{type_}” không hỗ trợ, chọn một trong: {', '.join(sorted(self.EXTRA_TYPES))}")
        room_name = next((rn for r, rn, _ in HOUSE if r == room), room)
        print(f"Giả lập thêm: {room}/{dev_id} ({type_}) “{name.strip()}”")
        return cls(self, room.strip(), room_name, dev_id.strip(), name.strip())

    def get(self, room: str, type_: str) -> Device | None:
        return self._index.get((room, type_))

    @staticmethod
    def daily(now: float) -> float:
        """-1..1, đỉnh khoảng 15h."""
        lt = time.localtime(now)
        hour = lt.tm_hour + lt.tm_min / 60
        return math.sin((hour - 9) / 24 * 2 * math.pi)

    @staticmethod
    def is_day(now: float) -> bool:
        return 6 <= time.localtime(now).tm_hour < 18

    def run(self):
        for d in self.devices:
            d.start()
        print(f"Đã khởi động {len(self.devices)} thiết bị → {self.args.host}:{self.args.port} "
              f"(prefix '{self.args.prefix}', QoS {self.args.qos}). Ctrl+C để tắt.", flush=True)
        last = time.time()
        while not self.stopping:
            time.sleep(1)
            now = time.time()
            with self.lock:
                for d in self.devices:
                    d.tick(now - last, now)
            last = now

    def shutdown(self):
        self.stopping = True
        print("Tắt có kiểm soát: mỗi thiết bị publish offline (graceful) + DISCONNECT", flush=True)
        for d in self.devices:
            d.shutdown()
