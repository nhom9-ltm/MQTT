"""
Kiểm thử báo cáo tiền điện (energy_service) và cảnh báo ngân sách (energy_watcher) — không cần broker.

    python -m unittest backend.tests.test_energy -v        # chạy từ thư mục gốc repo

Dữ liệu ghi vào một SQLite tạm (cùng schema với logger) qua biến môi trường HISTORY_DB; cấu hình giá và file
trạng thái cảnh báo cũng để ở thư mục tạm nên không đụng tới backend/config/energy.json hay backend/data/.
"""
import contextlib
import io
import json
import os
import shutil
import tempfile
import unittest
from datetime import datetime

from backend.repositories import message_repository
from backend.services import energy_service as es
from backend.services import energy_watcher

CFG = {
    "tiers": [{"up_to": 50, "price": 1984}, {"up_to": 100, "price": 2050}, {"up_to": 200, "price": 2380},
              {"up_to": 300, "price": 2998}, {"up_to": 400, "price": 3350}, {"up_to": None, "price": 3460}],
    "vat": 0.08, "budget_vnd": 1_000_000, "warn_ratio": 0.8,
}


def ms(*args) -> int:
    return int(datetime(*args).timestamp() * 1000)


class BillTest(unittest.TestCase):
    def test_zero(self):
        self.assertEqual(es.bill(0, CFG)["total"], 0)

    def test_first_tier_only(self):
        b = es.bill(50, CFG)
        self.assertEqual(b["subtotal"], 99_200)
        self.assertEqual(b["total"], 107_136)
        self.assertEqual(len(b["tiers"]), 1)

    def test_spans_three_tiers(self):
        b = es.bill(150, CFG)
        self.assertEqual([t["kwh"] for t in b["tiers"]], [50, 50, 50])
        self.assertEqual(b["subtotal"], 320_700)
        self.assertEqual(b["vat"], 25_656)
        self.assertEqual(b["total"], 346_356)

    def test_last_tier_unbounded(self):
        b = es.bill(500, CFG)
        self.assertEqual(b["tiers"][-1]["kwh"], 100)
        # 50×1984 + 50×2050 + 100×2380 + 100×2998 + 100×3350 + 100×3460
        self.assertEqual(b["subtotal"], 1_420_500)
        self.assertEqual(b["total"], 1_534_140)

    def test_shipped_config_is_valid(self):
        es.load_config(es.CONFIG_PATH)


class ConfigTest(unittest.TestCase):
    def bad(self, **change):
        cfg = json.loads(json.dumps(CFG))
        cfg.update(change)
        with self.assertRaises(es.EnergyConfigError):
            es.validate_config(cfg)

    def test_rejects_bad_values(self):
        self.bad(tiers=[])
        self.bad(tiers=[{"up_to": 50, "price": 1}, {"up_to": 40, "price": 2}, {"up_to": None, "price": 3}])
        self.bad(tiers=[{"up_to": 50, "price": 1}])                 # bậc cuối phải không giới hạn
        self.bad(tiers=[{"up_to": None, "price": 0}])
        self.bad(vat=8)
        self.bad(budget_vnd=-1)
        self.bad(warn_ratio=0)


class BudgetStatusTest(unittest.TestCase):
    def test_levels(self):
        self.assertEqual(es.budget_status(100, 200, {**CFG, "budget_vnd": 0}), "off")
        self.assertEqual(es.budget_status(100_000, 500_000, CFG), "ok")
        self.assertEqual(es.budget_status(100_000, 1_200_000, CFG), "warn")     # dự báo vượt
        self.assertEqual(es.budget_status(850_000, None, CFG), "warn")         # tới 80%
        self.assertEqual(es.budget_status(1_000_000, None, CFG), "over")


class MonthTest(unittest.TestCase):
    def test_bounds(self):
        s, e = es.month_bounds("2026-12")
        self.assertEqual(s, ms(2026, 12, 1))
        self.assertEqual(e, ms(2027, 1, 1))
        for bad in ("2026-13", "2026-1", "", None, "abc"):
            with self.assertRaises(ValueError):
                es.month_bounds(bad)


class ReportTest(unittest.TestCase):
    """Ổ cắm A chạy 1000 W và B chạy 500 W trong 10 giờ (08:00–18:00 ngày 2/11) -> 10 + 5 = 15 kWh."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp, "t.db")
        db = message_repository.open_db(self.db_path)
        for h in range(8, 18):
            for m in range(0, 60, 10):
                t = ms(2026, 11, 2, h, m)
                message_repository.insert_message(db, t, t, "living", "a", "state", '{"power": 1000}', 0, 0)
                message_repository.insert_message(db, t, t, "kitchen", "b", "state", '{"power": 500}', 0, 0)
        # tháng trước: không được tính vào tháng 11
        t = ms(2026, 10, 31, 23, 0)
        message_repository.insert_message(db, t, t, "living", "a", "state", '{"power": 9000}', 0, 0)
        db.close()
        self.env = {k: os.environ.get(k) for k in ("HISTORY_DB", "ENERGY_ALERT_STATE", "ENERGY_CONFIG")}
        os.environ["HISTORY_DB"] = self.db_path
        os.environ["ENERGY_ALERT_STATE"] = os.path.join(self.tmp, "alerts.json")
        os.environ["ENERGY_CONFIG"] = os.path.join(self.tmp, "energy.json")
        self.write_cfg(CFG)

    def tearDown(self):
        for k, v in self.env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write_cfg(self, cfg):
        with open(os.environ["ENERGY_CONFIG"], "w", encoding="utf-8") as f:
            json.dump(cfg, f)

    def test_current_month(self):
        r = es.month_report("2026-11", now_ms=ms(2026, 11, 2, 18, 0))
        self.assertAlmostEqual(r["kwh"], 15)
        self.assertEqual(r["bill"]["total"], round(15 * 1984 * 1.08))
        self.assertFalse(r["finished"])
        # 15 kWh trong 10 giờ có dữ liệu -> cả tháng 11 (720 giờ) ≈ 1080 kWh
        self.assertAlmostEqual(r["projected"]["kwh"], 1080, places=1)
        self.assertEqual(r["projected"]["total"], es.bill(1080, CFG)["total"])
        self.assertEqual(r["budget"]["status"], "warn")
        self.assertEqual([d["device"] for d in r["by_device"]], ["living/a", "kitchen/b"])
        self.assertAlmostEqual(r["by_device"][0]["share"], 2 / 3, places=3)
        self.assertEqual(sum(d["vnd"] for d in r["by_device"]), r["bill"]["total"])
        self.assertEqual(r["by_day"], [{"day": "2026-11-02", "kwh": 15.0, "cum_kwh": 15.0,
                                        "cum_vnd": r["bill"]["total"]}])

    def test_too_little_data_no_projection(self):
        r = es.month_report("2026-11", now_ms=ms(2026, 11, 2, 8, 30))
        self.assertIsNone(r["projected"])

    def test_finished_month_projection_is_actual(self):
        r = es.month_report("2026-11", now_ms=ms(2026, 12, 5))
        self.assertTrue(r["finished"])
        self.assertEqual(r["projected"]["total"], r["bill"]["total"])
        self.assertEqual(r["budget"]["status"], "ok")

    def test_empty_month(self):
        r = es.month_report("2026-09", now_ms=ms(2026, 11, 2))
        self.assertEqual(r["kwh"], 0)
        self.assertEqual(r["by_device"], [])

    def test_watcher_alerts_once_per_level(self):
        sent = []

        def pub(topic, payload, **kw):
            sent.append((topic, json.loads(payload)))
            return True

        now = ms(2026, 11, 2, 18, 0)
        with contextlib.redirect_stdout(io.StringIO()):
            first = energy_watcher.check(now, publish=pub)
            again = energy_watcher.check(now, publish=pub)
            self.write_cfg({**CFG, "budget_vnd": 20_000})       # thực tế 32.141 đ > 20.000 đ
            over = energy_watcher.check(now, publish=pub)
        self.assertEqual(first["level"], "warn")
        self.assertIsNone(again)
        self.assertEqual(over["level"], "critical")
        self.assertIn("VƯỢT", over["text"])
        self.assertEqual([t for t, _ in sent], ["home/_auto/notify/event"] * 2)
        self.assertEqual(sent[0][1]["source"], "energy")

    def test_watcher_retries_when_publish_fails(self):
        now = ms(2026, 11, 2, 18, 0)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertIsNone(energy_watcher.check(now, publish=lambda *a, **k: False))
            self.assertIsNotNone(energy_watcher.check(now, publish=lambda *a, **k: True))


if __name__ == "__main__":
    unittest.main()
