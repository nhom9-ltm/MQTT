"""Truy cập SQLite của logger: schema, ghi message, xuất CSV và các truy vấn báo cáo."""
import csv
import os
import sqlite3

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


def open_db(path: str) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    db = sqlite3.connect(path, check_same_thread=False)
    db.executescript(SCHEMA)
    return db


def insert_message(db, received_at, sent_at, room, device, kind, payload, qos, retained):
    db.execute(
        "INSERT INTO messages (received_at, sent_at, room, device, kind, payload, qos, retained)"
        " VALUES (?,?,?,?,?,?,?,?)",
        (received_at, sent_at, room, device, kind, payload, qos, retained),
    )
    db.commit()


def count_messages(db) -> int:
    return db.execute("SELECT COUNT(*) FROM messages").fetchone()[0]


def export_csv(db, table: str, path: str) -> int:
    if table not in TABLES:                     # tên bảng không đi qua tham số SQL nên phải kiểm tra
        raise ValueError(f"bảng không hợp lệ: {table}")
    cur = db.execute(f"SELECT * FROM {table} ORDER BY received_at")
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    with open(path, "w", newline="", encoding="utf-8-sig") as f:     # BOM để Excel đọc đúng tiếng Việt
        w = csv.writer(f)
        w.writerow(cols)
        w.writerows(rows)
    return len(rows)


# ---------- truy vấn cho báo cáo ----------
def energy_totals(db):
    return db.execute(
        "SELECT room, device, MAX(energy_kwh) FROM energy WHERE energy_kwh IS NOT NULL "
        "GROUP BY room, device ORDER BY room").fetchall()


def command_counts(db, since_ms: int):
    return db.execute(
        "SELECT COALESCE(source, '?'), COUNT(*) FROM commands WHERE received_at > ? "
        "GROUP BY source ORDER BY 2 DESC", (since_ms,)).fetchall()


def climate_averages(db, since_ms: int):
    return db.execute(
        "SELECT room, AVG(temperature), AVG(humidity) FROM climate WHERE received_at > ? "
        "GROUP BY room ORDER BY room", (since_ms,)).fetchall()
