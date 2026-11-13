#!/usr/bin/env python3
"""
Logger lưu lịch sử vào SQLite — minh họa QoS 1 + Persistent Session.

  * client_id CỐ ĐỊNH + clean_session=False  -> broker nhớ subscription của logger.
  * Subscribe QoS 1                            -> khi logger tắt, broker XẾP HÀNG các
    message QoS 1 gửi tới; bật lại logger sẽ nhận bù toàn bộ (không mất dữ liệu).
  * Thử: tắt logger 30s trong khi sensor chạy với --qos 1, bật lại -> thấy
    "session_present=True" và một loạt bản ghi được nhận bù ngay lập tức.

Lưu ý: chỉ message được publish với QoS >= 1 VÀ subscription QoS >= 1 mới được
xếp hàng. Chạy sensor với --qos 0 sẽ thấy dữ liệu trong lúc logger tắt bị mất.

Ví dụ:
  python logger.py
  python logger.py --export data.csv     # xuất CSV rồi thoát
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

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "telemetry.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS telemetry (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    received_at INTEGER NOT NULL,
    sent_at     INTEGER,
    room        TEXT,
    device      TEXT,
    temperature REAL,
    humidity    REAL,
    battery     REAL,
    seq         INTEGER,
    qos         INTEGER,
    retained    INTEGER
);
CREATE INDEX IF NOT EXISTS idx_dev_time ON telemetry(device, received_at);
CREATE TABLE IF NOT EXISTS status_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    received_at INTEGER NOT NULL,
    room        TEXT,
    device      TEXT,
    state       TEXT,
    reason      TEXT
);
"""


def main():
    p = argparse.ArgumentParser(description="MQTT -> SQLite logger")
    p.add_argument("--host", default=os.getenv("MQTT_HOST", "localhost"))
    p.add_argument("--port", type=int, default=int(os.getenv("MQTT_PORT", 1883)))
    p.add_argument("--username", default=os.getenv("MQTT_USER"))
    p.add_argument("--password", default=os.getenv("MQTT_PASS"))
    p.add_argument("--prefix", default="iot")
    p.add_argument("--client-id", default="history-logger-01")
    p.add_argument("--db", default=DB_PATH)
    p.add_argument("--export", metavar="CSV", help="xuất bảng telemetry ra CSV rồi thoát")
    args = p.parse_args()

    db = sqlite3.connect(args.db, check_same_thread=False)
    db.executescript(SCHEMA)

    if args.export:
        rows = db.execute("SELECT * FROM telemetry ORDER BY received_at").fetchall()
        cols = [d[0] for d in db.execute("SELECT * FROM telemetry LIMIT 0").description]
        with open(args.export, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(cols)
            w.writerows(rows)
        print(f"Đã xuất {len(rows)} dòng -> {args.export}")
        return

    stats = {"n": 0, "last_report": time.time()}

    def on_connect(client, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            print(f"Kết nối thất bại: {reason_code}")
            return
        print(f"Đã kết nối. session_present={flags.session_present} "
              f"({'broker còn giữ session cũ -> sẽ nhận bù message' if flags.session_present else 'session mới'})")
        client.subscribe([
            (f"{args.prefix}/+/+/telemetry", 1),
            (f"{args.prefix}/+/+/status", 1),
        ])

    def on_message(client, userdata, msg):
        parts = msg.topic.split("/")
        if len(parts) != 4:
            return
        _, room, device, kind = parts
        try:
            data = json.loads(msg.payload.decode() or "{}")
        except ValueError:
            return
        now = int(time.time() * 1000)
        if kind == "telemetry":
            db.execute(
                "INSERT INTO telemetry (received_at, sent_at, room, device, temperature,"
                " humidity, battery, seq, qos, retained) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (now, data.get("ts"), room, device, data.get("temperature"),
                 data.get("humidity"), data.get("battery"), data.get("seq"),
                 msg.qos, int(msg.retain)),
            )
            stats["n"] += 1
            # message đến trễ (do được xếp hàng khi logger offline)
            if data.get("ts") and now - data["ts"] > 5000 and not msg.retain:
                print(f"  ↺ nhận bù {device} seq={data.get('seq')} "
                      f"(trễ {(now - data['ts']) / 1000:.0f}s)")
        elif kind == "status":
            db.execute(
                "INSERT INTO status_events (received_at, room, device, state, reason)"
                " VALUES (?,?,?,?,?)",
                (now, room, device, data.get("state"), data.get("reason")),
            )
            print(f"  ● {device}: {data.get('state')}"
                  f"{' (' + data['reason'] + ')' if data.get('reason') else ''}")
        db.commit()
        if time.time() - stats["last_report"] > 10:
            total = db.execute("SELECT COUNT(*) FROM telemetry").fetchone()[0]
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
