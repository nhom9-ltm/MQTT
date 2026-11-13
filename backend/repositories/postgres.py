"""Kết nối PostgreSQL dùng chung cho các repository tài khoản và quản trị."""
from __future__ import annotations

import os
import sys
from contextlib import contextmanager

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:
    sys.exit("Thiếu thư viện: pip install -r backend/requirements-extra.txt")

from backend.repositories.history_repository import DatabaseUnavailable

DEFAULT_URL = "postgresql://smarthome:smarthome_dev@127.0.0.1:5434/smarthome"


@contextmanager
def connection():
    """Mở kết nối cho một thao tác: tự commit khi xong, rollback khi lỗi."""
    try:
        con = psycopg.connect(os.getenv("DATABASE_URL", DEFAULT_URL), row_factory=dict_row, connect_timeout=3)
    except psycopg.OperationalError as e:
        raise DatabaseUnavailable("Chưa kết nối được database — hãy chạy: docker compose up -d database") from e
    with con:
        yield con
