"""Truy vấn chỉ đọc vào smarthome.db cho API lịch sử (mở mode=ro nên không tranh chấp với logger)."""
import os
import sqlite3


class DatabaseUnavailable(Exception):
    """DB chưa có hoặc chưa được logger tạo bảng."""


def query(db_path: str, sql: str, *params) -> list[dict]:
    if not os.path.exists(db_path):
        raise DatabaseUnavailable(f"Chưa có {db_path} — hãy chạy logger.py trước.")
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in con.execute(sql, params)]
    except sqlite3.OperationalError as e:      # bảng chưa tạo (logger chưa chạy lần nào)
        raise DatabaseUnavailable(f"DB chưa sẵn sàng: {e}") from e
    finally:
        con.close()
