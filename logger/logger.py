#!/usr/bin/env python3
"""
Logger lưu lịch sử nhà thông minh vào SQLite — minh họa QoS 1 + Persistent Session.

  * client_id CỐ ĐỊNH + clean_session=False  -> broker nhớ subscription của logger.
  * Subscribe QoS 1                            -> khi logger tắt, broker XẾP HÀNG các
    message QoS 1 gửi tới; bật lại logger sẽ nhận bù toàn bộ (không mất dữ liệu).
  * Thử: tắt logger 30s trong khi home_sim.py chạy (--qos 1), bật lại -> thấy
    "session_present=True" và một loạt bản ghi "↺ nhận bù".

Ghi lại:
  state   trạng thái thiết bị (nhiệt độ, công suất, bật/tắt...)
  status  online/offline, LWT
  set     LỆNH ĐIỀU KHIỂN — ai (dashboard / automation) ra lệnh gì cho thiết bị nào
  notify  cảnh báo của automation engine

Ví dụ:
  python logger/logger.py
  python logger/logger.py --export history.csv          # xuất toàn bộ rồi thoát
  python logger/logger.py --export climate.csv --table climate
  python logger/logger.py --report                      # tóm tắt điện năng & lệnh điều khiển
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import signal
import sqlite3
import sys
import time

try:
    import paho.mqtt.client as mqtt
except ImportError:
    sys.exit("Thiếu thư viện: pip install -r requirements.txt")

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "smarthome.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    received_at INTEGER NOT NULL,
    sent_at     INTEGER,
    room        TEXT,
    device      TEXT,
    kind        TEXT,          -- state | status | set | notify
    payload     TEXT,          -- JSON gốc
    qos         INTEGER,
    retained    INTEGER
);
CREATE INDEX IF NOT EXISTS idx_dev_time ON messages(room, device, received_at);
CREATE INDEX IF NOT EXISTS idx_kind_time ON messages(kind, received_at);

-- View tiện cho báo cáo / Grafana
CREATE VIEW IF NOT EXISTS climate AS
  SELECT received_at, room, device,
         json_extract(payload, '$.temperature') AS temperature,
         json_extract(payload, '$.humidity')    AS humidity
  FROM messages WHERE kind = 'state' AND json_extract(payload, '$.temperature') IS NOT NULL;
CREATE VIEW IF NOT EXISTS energy AS
  SELECT received_at, room, device,
         json_extract(payload, '$.power')  AS power_w,
         json_extract(payload, '$.energy') AS energy_kwh
  FROM messages WHERE kind = 'state' AND json_extract(payload, '$.power') IS NOT NULL;
CREATE VIEW IF NOT EXISTS commands AS
  SELECT received_at, room, device,
         json_extract(payload, '$.from') AS source,
         json_extract(payload, '$.via')  AS via,
         payload
  FROM messages WHERE kind = 'set';
"""

TABLES = ("messages", "climate", "energy", "commands")


def export(db, table: str, path: str):
    cur = db.execute(f"SELECT * FROM {table} ORDER BY received_at")
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    with open(path, "w", newline="", encoding="utf-8-sig") as f:     # BOM để Excel đọc đúng tiếng Việt
        w = csv.writer(f)
        w.writerow(cols)
        w.writerows(rows)
    print(f"Đã xuất {len(rows)} dòng ({table}) -> {path}")


def report(db):
    since = int((time.time() - 24 * 3600) * 1000)
    print("== Điện năng tích lũy (ổ cắm có đo điện) ==")
    for room, dev, kwh in db.execute(
            "SELECT room, device, MAX(energy_kwh) FROM energy WHERE energy_kwh IS NOT NULL "
            "GROUP BY room, device ORDER BY room"):
        print(f"  {room}/{dev:<12} {kwh:8.3f} kWh")
    print("\n== Lệnh điều khiển 24h qua (theo nguồn) ==")
    rows = db.execute(
        "SELECT COALESCE(source, '?'), COUNT(*) FROM commands WHERE received_at > ? "
        "GROUP BY source ORDER BY 2 DESC", (since,)).fetchall()
    for src, n in rows:
        print(f"  {src:<12} {n}")
    if not rows:
        print("  (chưa có)")
    print("\n== Nhiệt độ trung bình 24h qua ==")
    for room, t, h in db.execute(
            "SELECT room, AVG(temperature), AVG(humidity) FROM climate WHERE received_at > ? "
            "GROUP BY room ORDER BY room", (since,)):
        print(f"  {room:<10} {t:5.1f}°C  {h:4.0f}%")


def main():
    p = argparse.ArgumentParser(description="MQTT -> SQLite logger (nhà thông minh)")
    p.add_argument("--host", default=os.getenv("MQTT_HOST", "localhost"))
    p.add_argument("--port", type=int, default=int(os.getenv("MQTT_PORT", 1883)))
    p.add_argument("--username", default=os.getenv("MQTT_USER"))
    p.add_argument("--password", default=os.getenv("MQTT_PASS"))
    p.add_argument("--prefix", default="home")
    p.add_argument("--client-id", default="history-logger-01")
    p.add_argument("--db", default=DB_PATH)
    p.add_argument("--export", metavar="CSV", help="xuất bảng ra CSV rồi thoát")
    p.add_argument("--table", choices=TABLES, default="messages", help="bảng/view để xuất")
    p.add_argument("--report", action="store_true", help="in báo cáo tóm tắt rồi thoát")
    args = p.parse_args()

    db = sqlite3.connect(args.db, check_same_thread=False)
    db.executescript(SCHEMA)

    if args.export:
        export(db, args.table, args.export)
        return
    if args.report:
        report(db)
        return

    stats = {"n": 0, "last_report": time.time()}

    def on_connect(client, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            print(f"Kết nối thất bại: {reason_code}")
            return
        print(f"Đã kết nối. session_present={flags.session_present} "
              f"({'broker còn giữ session cũ -> sẽ nhận bù message' if flags.session_present else 'session mới'})")
        client.subscribe([
            (f"{args.prefix}/+/+/state", 1),
            (f"{args.prefix}/+/+/status", 1),
            (f"{args.prefix}/+/+/set", 1),
            (f"{args.prefix}/_auto/notify/event", 1),
        ])

    def on_message(client, userdata, msg):
        parts = msg.topic.split("/")
        if len(parts) != 4:
            return
        _, room, device, kind = parts
        text = msg.payload.decode(errors="replace")
        try:
            data = json.loads(text) if text else {}
        except ValueError:
            return
        if not isinstance(data, dict):
            return
        if kind == "event":
            kind = "notify"
        now = int(time.time() * 1000)
        db.execute(
            "INSERT INTO messages (received_at, sent_at, room, device, kind, payload, qos, retained)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (now, data.get("ts"), room, device, kind, text, msg.qos, int(msg.retain)),
        )
        db.commit()
        stats["n"] += 1

        late = data.get("ts") and now - data["ts"] > 5000 and not msg.retain
        if late and kind == "state":
            # message đến trễ do được broker xếp hàng khi logger offline
            print(f"  ↺ nhận bù {room}/{device} (trễ {(now - data['ts']) / 1000:.0f}s)")
        elif kind == "status" and not msg.retain:
            print(f"  ● {room}/{device}: {data.get('state')}"
                  f"{' (' + data['reason'] + ')' if data.get('reason') else ''}")
        elif kind == "set":
            shown = {k: v for k, v in data.items() if k not in ("from", "via", "ts")}
            print(f"  ⌁ {data.get('from', '?')}{' / ' + data['via'] if data.get('via') else ''}"
                  f" → {room}/{device} {json.dumps(shown, ensure_ascii=False)}")
        elif kind == "notify" and data.get("level") != "rule":
            print(f"  🔔 [{data.get('level')}] {data.get('text')}")

        if time.time() - stats["last_report"] > 10:
            total = db.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
            print(f"[{time.strftime('%H:%M:%S')}] +{stats['n']} bản ghi / 10s — tổng {total}")
            stats["n"] = 0
            stats["last_report"] = time.time()

    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=args.client_id,
        clean_session=False,          # <-- PERSISTENT SESSION
        protocol=mqtt.MQTTv311,
    )
    if args.username:
        client.username_pw_set(args.username, args.password)
    client.on_connect = on_connect
    client.on_message = on_message

    def stop(*_):
        print("Dừng logger (session vẫn được broker giữ lại).")
        client.disconnect()
        db.close()
        sys.exit(0)

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    print(f"Logger -> {args.db}")
    client.connect_async(args.host, args.port, keepalive=30)
    client.loop_forever(retry_first_connection=True)


if __name__ == "__main__":
    main()
