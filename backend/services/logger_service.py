"""
Service của logger: ghi mọi message MQTT vào SQLite và in tóm tắt ra màn hình.

Ghi lại:
  state   trạng thái thiết bị (nhiệt độ, công suất, bật/tắt...)
  status  online/offline, LWT
  set     LỆNH ĐIỀU KHIỂN — ai (dashboard / automation) ra lệnh gì cho thiết bị nào
  notify  cảnh báo của automation engine
"""
import json
import time

from backend.repositories import message_repository as repo


class LoggerService:
    def __init__(self, db):
        self.db = db
        self.n = 0
        self.last_report = time.time()

    def record(self, room: str, device: str, kind: str, text: str, data: dict, qos: int, retained: bool):
        if kind == "event":
            kind = "notify"
        now = int(time.time() * 1000)
        repo.insert_message(self.db, now, data.get("ts"), room, device, kind, text, qos, int(retained))
        self.n += 1

        late = data.get("ts") and now - data["ts"] > 5000 and not retained
        if late and kind == "state":
            # message đến trễ do được broker xếp hàng khi logger offline
            print(f"  ↺ nhận bù {room}/{device} (trễ {(now - data['ts']) / 1000:.0f}s)")
        elif kind == "status" and not retained:
            print(f"  ● {room}/{device}: {data.get('state')}"
                  f"{' (' + data['reason'] + ')' if data.get('reason') else ''}")
        elif kind == "set":
            shown = {k: v for k, v in data.items() if k not in ("from", "via", "ts")}
            print(f"  ⌁ {data.get('from', '?')}{' / ' + data['via'] if data.get('via') else ''}"
                  f" → {room}/{device} {json.dumps(shown, ensure_ascii=False)}")
        elif kind == "notify" and data.get("level") != "rule":
            print(f"  🔔 [{data.get('level')}] {data.get('text')}")

        if time.time() - self.last_report > 10:
            print(f"[{time.strftime('%H:%M:%S')}] +{self.n} bản ghi / 10s — tổng {repo.count_messages(self.db)}")
            self.n = 0
            self.last_report = time.time()


def export(db, table: str, path: str):
    n = repo.export_csv(db, table, path)
    print(f"Đã xuất {n} dòng ({table}) -> {path}")


def report(db):
    since = int((time.time() - 24 * 3600) * 1000)
    print("== Điện năng tích lũy (ổ cắm có đo điện) ==")
    for room, dev, kwh in repo.energy_totals(db):
        print(f"  {room}/{dev:<12} {kwh:8.3f} kWh")
    print("\n== Lệnh điều khiển 24h qua (theo nguồn) ==")
    rows = repo.command_counts(db, since)
    for src, n in rows:
        print(f"  {src:<12} {n}")
    if not rows:
        print("  (chưa có)")
    print("\n== Nhiệt độ trung bình 24h qua ==")
    for room, t, h in repo.climate_averages(db, since):
        print(f"  {room:<10} {t:5.1f}°C  {h:4.0f}%")
