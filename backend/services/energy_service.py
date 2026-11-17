"""
Service điện năng: tính tiền điện theo biểu giá bậc thang EVN, dự báo cuối tháng và so với ngân sách.

  * Biểu giá, VAT, ngân sách đọc từ backend/config/energy.json (đọc lại mỗi lần gọi, sửa file là có hiệu lực ngay).
  * kWh lấy từ view `energy` của logger (backend/data/smarthome.db): mỗi giờ lấy công suất trung bình của từng thiết bị,
    cộng lại rồi chia 1000 — giống cách tính ở trang Lịch sử (history_service.energy).
  * Tiền điện tính trên TỔNG kWh cả nhà (bậc thang không tuyến tính), rồi chia cho từng thiết bị theo tỉ lệ kWh.
  * Dự báo cuối tháng = kWh hiện có / thời gian đã có dữ liệu × độ dài cả tháng (logger chạy giữa tháng vẫn dự báo được).

Mọi mốc thời gian là mili-giây epoch; ngày/tháng tính theo giờ máy (giống SQLite 'localtime').
"""
from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime

from backend.common.paths import CONFIG_DIR
from backend.services.history_service import query

CONFIG_PATH = os.path.join(CONFIG_DIR, "energy.json")
MONTH_RE = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")
MIN_COVERAGE_MS = 3600_000          # cần ít nhất 1 giờ dữ liệu mới dự báo


class EnergyConfigError(ValueError):
    pass


# ---------- cấu hình ----------
def load_config(path: str | None = None) -> dict:
    path = path or os.getenv("ENERGY_CONFIG", CONFIG_PATH)
    try:
        with open(path, encoding="utf-8") as f:
            cfg = json.load(f)
    except (OSError, ValueError) as e:
        raise EnergyConfigError(f"Không đọc được {path}: {e}") from e
    validate_config(cfg)
    return cfg


def validate_config(cfg: dict) -> None:
    tiers = cfg.get("tiers")
    if not isinstance(tiers, list) or not tiers:
        raise EnergyConfigError("tiers phải là danh sách bậc giá, không rỗng")
    prev = 0
    for i, t in enumerate(tiers):
        price, up_to = t.get("price"), t.get("up_to")
        if not isinstance(price, (int, float)) or price <= 0:
            raise EnergyConfigError(f"Bậc {i + 1}: price phải là số dương")
        last = i == len(tiers) - 1
        if last and up_to is not None:
            raise EnergyConfigError("Bậc cuối phải có up_to = null (không giới hạn)")
        if not last and (not isinstance(up_to, (int, float)) or up_to <= prev):
            raise EnergyConfigError(f"Bậc {i + 1}: up_to phải lớn hơn bậc trước ({prev})")
        prev = up_to if up_to is not None else prev
    if not isinstance(cfg.get("vat", 0), (int, float)) or not 0 <= cfg.get("vat", 0) < 1:
        raise EnergyConfigError("vat phải trong khoảng 0 – 1 (ví dụ 0.08)")
    if not isinstance(cfg.get("budget_vnd", 0), (int, float)) or cfg.get("budget_vnd", 0) < 0:
        raise EnergyConfigError("budget_vnd phải là số không âm (0 = tắt ngân sách)")
    if not isinstance(cfg.get("warn_ratio", 0.8), (int, float)) or not 0 < cfg.get("warn_ratio", 0.8) <= 1:
        raise EnergyConfigError("warn_ratio phải trong khoảng (0, 1]")


# ---------- tính tiền ----------
def bill(kwh: float, cfg: dict) -> dict:
    """Hóa đơn cho `kwh` theo bậc thang: chi tiết từng bậc, tiền trước thuế, VAT, tổng (làm tròn đồng)."""
    rows, prev, subtotal = [], 0, 0.0
    for i, t in enumerate(cfg["tiers"]):
        up_to = t["up_to"]
        cap = float("inf") if up_to is None else up_to - prev
        used = max(0.0, min(kwh - prev, cap))
        vnd = used * t["price"]
        subtotal += vnd
        rows.append({"tier": i + 1, "from": prev, "to": up_to, "price": t["price"],
                     "kwh": round(used, 3), "vnd": round(vnd)})
        if up_to is None or kwh <= up_to:
            break
        prev = up_to
    vat = subtotal * cfg.get("vat", 0)
    return {"kwh": round(kwh, 3), "subtotal": round(subtotal), "vat": round(vat),
            "total": round(subtotal + vat), "tiers": rows}


def budget_status(actual_vnd: float, projected_vnd: float | None, cfg: dict) -> str:
    """off = không đặt ngân sách · over = đã vượt · warn = gần chạm hoặc dự báo sẽ vượt · ok."""
    budget = cfg.get("budget_vnd", 0)
    if not budget:
        return "off"
    if actual_vnd >= budget:
        return "over"
    if (projected_vnd is not None and projected_vnd >= budget) or actual_vnd >= budget * cfg.get("warn_ratio", 0.8):
        return "warn"
    return "ok"


# ---------- tháng ----------
def month_bounds(month: str) -> tuple[int, int]:
    """'2026-11' -> (đầu tháng, đầu tháng sau) theo giờ máy, mili-giây."""
    m = MONTH_RE.match(month or "")
    if not m:
        raise ValueError("month phải có dạng YYYY-MM")
    y, mo = int(m.group(1)), int(m.group(2))
    start = datetime(y, mo, 1)
    end = datetime(y + mo // 12, mo % 12 + 1, 1)
    return int(start.timestamp() * 1000), int(end.timestamp() * 1000)


def current_month(now_ms: int | None = None) -> str:
    t = (now_ms / 1000) if now_ms is not None else time.time()
    return datetime.fromtimestamp(t).strftime("%Y-%m")


def _usage(start: int, end: int) -> tuple[list[dict], int | None]:
    rows = query(
        "SELECT day, room||'/'||device AS device, SUM(p)/1000.0 AS kwh FROM ("
        "  SELECT strftime('%Y-%m-%d', received_at/1000, 'unixepoch', 'localtime') AS day,"
        "         strftime('%H', received_at/1000, 'unixepoch', 'localtime') AS h, room, device,"
        "         AVG(power_w) AS p FROM energy WHERE received_at>=? AND received_at<? GROUP BY day, h, room, device"
        ") GROUP BY day, room, device ORDER BY day", start, end)
    first = query("SELECT MIN(received_at) AS t FROM energy WHERE received_at>=? AND received_at<?", start, end)
    return rows, first[0]["t"] if first else None


def month_report(month: str | None = None, now_ms: int | None = None, cfg: dict | None = None) -> dict:
    now = now_ms if now_ms is not None else int(time.time() * 1000)
    month = month or current_month(now)
    cfg = cfg or load_config()
    start, end = month_bounds(month)
    rows, first = _usage(start, end)

    by_day, by_dev = {}, {}
    for r in rows:
        by_day[r["day"]] = by_day.get(r["day"], 0) + r["kwh"]
        by_dev[r["device"]] = by_dev.get(r["device"], 0) + r["kwh"]
    kwh = sum(by_day.values())
    actual = bill(kwh, cfg)

    finished = now >= end
    covered = (min(now, end) - max(start, first)) if first is not None else 0
    projected = None
    if finished:
        projected = {"kwh": actual["kwh"], "total": actual["total"]}
    elif covered >= MIN_COVERAGE_MS:
        p_kwh = kwh / covered * (end - start)
        projected = {"kwh": round(p_kwh, 3), "total": bill(p_kwh, cfg)["total"]}

    cum, days = 0.0, []
    for d in sorted(by_day):
        cum += by_day[d]
        days.append({"day": d, "kwh": round(by_day[d], 3), "cum_kwh": round(cum, 3), "cum_vnd": bill(cum, cfg)["total"]})

    devices = sorted(
        ({"device": d, "kwh": round(v, 3), "share": round(v / kwh, 4) if kwh else 0,
          "vnd": round(actual["total"] * v / kwh) if kwh else 0} for d, v in by_dev.items() if v > 0),
        key=lambda x: -x["kwh"])

    budget = cfg.get("budget_vnd", 0)
    return {
        "month": month, "start": start, "end": end, "finished": finished,
        "coverage": round(covered / (end - start), 4) if covered > 0 else 0,
        "kwh": actual["kwh"], "bill": actual, "projected": projected,
        "budget": {"vnd": budget, "warn_ratio": cfg.get("warn_ratio", 0.8),
                   "used_ratio": round(actual["total"] / budget, 4) if budget else None,
                   "status": budget_status(actual["total"], projected and projected["total"], cfg)},
        "by_day": days, "by_device": devices,
        "price_note": cfg.get("_note", ""),
    }
