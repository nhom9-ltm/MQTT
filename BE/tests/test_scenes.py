"""
Kiểm thử logic kịch bản & chế độ của AutomationService — không cần broker, không cần simulator.

    python -m unittest BE.tests.test_scenes -v        # chạy từ thư mục gốc repo

Dùng 20 thiết bị giả (lấy từ BE/mock/house.py) và một hàm publish giả để ghi lại mọi lệnh được gửi.
Luật được sao ra thư mục tạm nên không bao giờ ghi vào BE/config/rules.json thật.
"""
import contextlib
import io
import json
import os
import shutil
import tempfile
import time
import unittest

from BE.common.paths import CONFIG_DIR
from BE.mock.house import HOUSE
from BE.service.automation_service import AutomationService

SCENES = os.path.join(CONFIG_DIR, "scenes.json")


class FakePublish:
    def __init__(self):
        self.sets, self.modes, self.notifies, self.engines = [], [], [], []

    def __call__(self, topic, payload, qos=0, retain=False):
        p = json.loads(payload)
        if topic.endswith("/engine/status"):
            self.engines.append(p)
        elif topic.endswith("/set"):
            self.sets.append((topic[len("home/"):-len("/set")], {k: v for k, v in p.items() if k not in ("from", "via", "ts")}))
        elif topic.endswith("/mode/state"):
            self.modes.append(p["mode"])
        elif topic.endswith("/notify/event"):
            self.notifies.append((p["level"], p["text"]))

        class Info:
            def wait_for_publish(self, timeout=None):
                pass
        return Info()

    def targets(self):
        return {k for k, _ in self.sets}


class SceneBase(unittest.TestCase):
    """Dựng AutomationService với 20 thiết bị giả + publish giả; không có test riêng."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.rules = os.path.join(self.tmp, "rules.json")
        self.custom = os.path.join(self.tmp, "scenes.custom.json")      # kịch bản người dùng tạo: ghi vào thư mục tạm
        shutil.copy(os.path.join(CONFIG_DIR, "rules.json"), self.rules)

    def build(self, offline=()):
        pub = FakePublish()
        svc = AutomationService("home", self.rules, SCENES, pub, custom_scenes_path=self.custom)
        svc.warm_until = 0
        for room, _, items in HOUSE:
            for cls, dev, name, _opts in items:
                key = f"{room}/{dev}"
                svc.handle_message(room, dev, "status", {"state": "offline" if key in offline else "online",
                                                         "type": cls.TYPE, "name": name})
                svc.handle_message(room, dev, "state", {"on": False} if cls.TYPE in ("light", "fan", "ac", "plug") else {})
        svc.mode = "night"
        return svc, pub

    def run_scene(self, svc, sid, wait=0.4):
        with contextlib.redirect_stdout(io.StringIO()):
            svc.run_scene(sid, "test")
            time.sleep(wait)


class SceneTests(SceneBase):
    # ---------------------------------------------------------------- từng kịch bản
    def test_ve_nha(self):
        svc, pub = self.build()
        self.run_scene(svc, "home")
        self.assertEqual(pub.modes, ["home"])
        self.assertEqual(dict(pub.sets), {
            "entrance/lock": {"locked": False}, "living/light": {"on": True, "brightness": 80},
            "living/curtain": {"position": 100}, "living/ac": {"on": True, "mode": "cool", "target": 26}})

    def test_ra_khoi_nha_tat_het_ke_ca_bep_roi_moi_chuyen_vang_nha(self):
        svc, pub = self.build()
        self.run_scene(svc, "away", wait=3.7)
        off = {k for k, p in pub.sets if p == {"on": False}}
        for key in ("bedroom/light", "kitchen/light", "living/light", "living/fan", "kitchen/hood-fan",
                    "living/ac", "bedroom/ac", "living/tv-plug", "kitchen/stove-plug"):
            self.assertIn(key, off, f"{key} phải được tắt")
        self.assertEqual({k: p for k, p in pub.sets if "curtain" in k}, {"living/curtain": {"position": 0}, "bedroom/curtain": {"position": 0}})
        self.assertIn(("entrance/lock", {"locked": True}), pub.sets)
        self.assertEqual(pub.modes, ["away"])
        self.assertEqual(svc.mode, "away")

    def test_di_ngu(self):
        svc, pub = self.build()
        self.run_scene(svc, "sleep")
        sent = dict(pub.sets)
        self.assertEqual(pub.modes, ["night"])
        self.assertEqual(sent["bedroom/light"], {"on": True, "brightness": 10})   # đèn ngủ KHÔNG bị tắt bởi lệnh "tắt mọi đèn"
        self.assertEqual(sent["bedroom/ac"], {"on": True, "mode": "cool", "target": 27})
        for key in ("living/light", "kitchen/light", "living/ac", "living/fan", "kitchen/hood-fan",
                    "living/tv-plug", "kitchen/stove-plug"):
            self.assertEqual(sent[key], {"on": False}, key)
        self.assertEqual(sent["entrance/lock"], {"locked": True})

    def test_buoi_sang(self):
        svc, pub = self.build()
        self.run_scene(svc, "morning")
        self.assertEqual(pub.modes, ["home"])
        self.assertEqual(dict(pub.sets), {
            "living/curtain": {"position": 100}, "bedroom/curtain": {"position": 100},
            "bedroom/light": {"on": False}, "bedroom/ac": {"on": False}})   # đèn ngủ của đêm qua được TẮT, không bật lên

    def test_xem_phim_khong_doi_che_do(self):
        svc, pub = self.build()
        svc.mode = "home"
        self.run_scene(svc, "movie")
        self.assertEqual(pub.modes, [])
        self.assertEqual(dict(pub.sets), {
            "living/light": {"on": True, "brightness": 15}, "living/curtain": {"position": 0},
            "living/tv-plug": {"on": True}, "living/ac": {"on": True, "mode": "cool", "target": 25}})

    # ---------------------------------------------------------------- thiết bị offline
    def test_khoa_cua_offline_thi_bao_nghiem_trong(self):
        svc, pub = self.build(offline=("entrance/lock",))
        self.run_scene(svc, "away", wait=3.7)
        self.assertNotIn("entrance/lock", pub.targets())
        level, text = pub.notifies[-1]
        self.assertEqual(level, "critical")
        self.assertIn("entrance/lock", text)
        self.assertIn("CHƯA ĐƯỢC KHÓA", text)
        self.assertEqual(svc.mode, "away")              # vẫn chuyển chế độ theo ý người dùng, nhưng đã cảnh báo

    def test_thiet_bi_thuong_offline_thi_canh_bao_muc_warn(self):
        svc, pub = self.build(offline=("living/fan",))
        self.run_scene(svc, "sleep")
        level, text = pub.notifies[-1]
        self.assertEqual(level, "warn")
        self.assertIn("living/fan", text)

    def test_tat_ca_online_thi_khong_co_canh_bao_cuoi_kich_ban(self):
        svc, pub = self.build()
        self.run_scene(svc, "sleep")
        self.assertEqual([n for n in pub.notifies if "chưa điều khiển được" in n[1]], [])

    # ---------------------------------------------------------------- tranh chấp giữa kịch bản / chế độ
    def test_kich_ban_moi_huy_kich_ban_dang_cho(self):
        svc, pub = self.build()
        with contextlib.redirect_stdout(io.StringIO()):
            svc.run_scene("away", "test")
            time.sleep(1.0)
            svc.run_scene("home", "test")
            time.sleep(4.0)
        self.assertEqual(pub.modes, ["home"])           # "Ra khỏi nhà" bị hủy, không ghi đè sang Vắng nhà
        self.assertEqual(svc.mode, "home")

    def test_nguoi_dung_doi_che_do_thi_huy_kich_ban_dang_cho(self):
        svc, pub = self.build()
        with contextlib.redirect_stdout(io.StringIO()):
            svc.run_scene("away", "test")
            time.sleep(1.0)
            svc.on_control("mode", "set", {"mode": "home", "from": "dashboard"})
            time.sleep(3.5)
        self.assertEqual(pub.modes, ["home"])
        self.assertEqual(svc.mode, "home")

    # ---------------------------------------------------------------- người dùng tự chọn chế độ -> chạy kịch bản tương ứng
    def _chon_che_do(self, svc, mode, wait):
        with contextlib.redirect_stdout(io.StringIO()):
            svc.on_control("mode", "set", {"mode": mode, "from": "dashboard"})
            time.sleep(wait)

    def test_chon_vang_nha_chay_ra_khoi_nha(self):
        svc, pub = self.build()
        svc.mode = "home"
        self._chon_che_do(svc, "away", 3.7)
        self.assertIn(("entrance/lock", {"locked": True}), pub.sets)
        self.assertIn(("kitchen/stove-plug", {"on": False}), pub.sets)
        self.assertIn(("living/light", {"on": False}), pub.sets)
        self.assertEqual(pub.modes, ["away"])
        self.assertEqual(svc.mode, "away")

    def test_chon_o_nha_chay_ve_nha(self):
        svc, pub = self.build()                      # đang ở chế độ night
        self._chon_che_do(svc, "home", 0.4)
        self.assertIn(("entrance/lock", {"locked": False}), pub.sets)
        self.assertIn(("living/ac", {"on": True, "mode": "cool", "target": 26}), pub.sets)
        self.assertEqual(pub.modes, ["home"])

    def test_chon_ban_dem_chay_di_ngu(self):
        svc, pub = self.build()
        svc.mode = "home"
        self._chon_che_do(svc, "night", 0.4)
        self.assertIn(("bedroom/light", {"on": True, "brightness": 10}), pub.sets)
        self.assertIn(("kitchen/stove-plug", {"on": False}), pub.sets)
        self.assertEqual(pub.modes, ["night"])

    def test_chon_lai_che_do_hien_tai_khong_dieu_khien_thiet_bi(self):
        svc, pub = self.build()                      # đang ở night
        self._chon_che_do(svc, "night", 0.3)
        self.assertEqual(pub.sets, [])
        self.assertEqual(pub.modes, ["night"])

    def test_kich_ban_tu_doi_che_do_khong_chay_lap(self):
        svc, pub = self.build()
        self.run_scene(svc, "home")                  # kịch bản tự đặt chế độ, không được kích hoạt thêm một kịch bản nữa
        self.assertEqual(pub.modes, ["home"])
        self.assertEqual([x for x in pub.sets if x[0] == "entrance/lock"], [("entrance/lock", {"locked": False})])

    def test_vang_nha_khoa_cua_offline_van_bao_nghiem_trong(self):
        svc, pub = self.build(offline=("entrance/lock",))
        svc.mode = "home"
        self._chon_che_do(svc, "away", 3.7)
        self.assertEqual(pub.notifies[-1][0], "critical")
        self.assertEqual(svc.mode, "away")

    # ---------------------------------------------------------------- báo lỗi
    def test_kich_ban_khong_ton_tai_bao_len_dashboard(self):
        svc, pub = self.build()
        self.run_scene(svc, "khong-co", wait=0.1)
        self.assertEqual(pub.notifies[-1][0], "warn")
        self.assertIn("khong-co", pub.notifies[-1][1])

    def test_che_do_khong_hop_le_bao_len_dashboard(self):
        svc, pub = self.build()
        with contextlib.redirect_stdout(io.StringIO()):
            svc.on_control("mode", "set", {"mode": "bay-bong", "from": "dashboard"})
        self.assertEqual(svc.mode, "night")
        self.assertEqual(pub.notifies[-1][0], "warn")

    # ---------------------------------------------------------------- luật tiết kiệm điện không phá "Xem phim"
    def _idle(self, tv_on):
        svc, pub = self.build()
        svc.mode = "home"
        svc.handle_message("living", "tv-plug", "state", {"on": tv_on})
        svc.handle_message("living", "light", "state", {"on": True, "brightness": 15})
        svc.handle_message("living", "motion", "state", {"motion": True})
        svc.handle_message("living", "motion", "state", {"motion": False})      # cạnh xuống: bắt đầu đếm 120 giây
        svc.rt["living_idle"]["since"] -= 125                                      # tua nhanh 125 giây ngồi yên
        with contextlib.redirect_stdout(io.StringIO()):
            svc.evaluate()
            time.sleep(0.3)
        return pub

    def test_dang_xem_tv_thi_khong_tat_den_quat(self):
        self.assertEqual([x for x in self._idle(tv_on=True).sets if x[0] in ("living/light", "living/fan")], [])

    def test_tv_tat_va_khong_ai_trong_phong_thi_tat_den_quat(self):
        sets = self._idle(tv_on=False).sets
        self.assertIn(("living/light", {"on": False}), sets)
        self.assertIn(("living/fan", {"on": False}), sets)


class AddSceneTests(SceneBase):
    """Thêm kịch bản mới từ dashboard: kiểm tra, lưu file, chạy được, và không cho chèn lệnh nguy hiểm."""

    GOOD = {"name": "Đọc sách", "icon": "📖", "actions": [
        {"device": "bedroom/light", "set": {"on": True, "brightness": 40}},
        {"type": "curtain", "room": "bedroom", "set": {"position": 100}},
        {"mode": "home"},
        {"delay": 1},
        {"notify": "Chúc đọc sách vui {vẻ}", "level": "info"}]}

    def add(self, svc, data):
        with contextlib.redirect_stdout(io.StringIO()):
            svc.on_control("scene", "set", {"add": data, "from": "dashboard"})

    def test_them_kich_ban_hop_le_duoc_luu_va_bao_cho_dashboard(self):
        svc, pub = self.build()
        n = len(svc.scenes)
        self.add(svc, self.GOOD)
        self.assertEqual(len(svc.scenes), n + 1)
        new = svc.scenes[-1]
        self.assertEqual((new["id"], new["name"], new["icon"], new["custom"]), ("custom-doc-sach", "Đọc sách", "📖", True))
        self.assertEqual(pub.notifies[-1], ("info", "Đã thêm kịch bản “Đọc sách”"))
        listed = {s["id"]: s for s in pub.engines[-1]["scenes"]}
        self.assertTrue(listed["custom-doc-sach"]["custom"])           # dashboard nhận được kịch bản mới
        self.assertFalse(listed["home"]["custom"])
        with open(self.custom, encoding="utf-8") as f:                 # đã lưu xuống file riêng
            saved = json.load(f)
        self.assertEqual([s["id"] for s in saved], ["custom-doc-sach"])
        self.assertNotIn("custom", saved[0])

    def test_kich_ban_moi_con_sau_khi_khoi_dong_lai(self):
        svc, _ = self.build()
        self.add(svc, self.GOOD)
        svc2, _ = self.build()                                          # engine khởi động lại, đọc cùng file
        self.assertIn("custom-doc-sach", [s["id"] for s in svc2.scenes])
        self.assertTrue(next(s for s in svc2.scenes if s["id"] == "custom-doc-sach")["custom"])

    def test_chay_kich_ban_moi(self):
        svc, pub = self.build()
        svc.mode = "night"
        self.add(svc, self.GOOD)
        pub.sets.clear()
        self.run_scene(svc, "custom-doc-sach", wait=1.6)
        self.assertEqual(dict(pub.sets), {"bedroom/light": {"on": True, "brightness": 40},
                                          "bedroom/curtain": {"position": 100}})   # room="bedroom": chỉ rèm phòng ngủ
        self.assertEqual(svc.mode, "home")
        self.assertEqual(pub.notifies[-1], ("info", "Chúc đọc sách vui {vẻ}"))     # ngoặc nhọn người dùng gõ không gây lỗi

    def test_tu_choi_du_lieu_sai(self):
        bad = {
            "thiếu tên": {"actions": [{"mode": "home"}]},
            "tên trùng kịch bản có sẵn": {"name": "về nhà", "actions": [{"mode": "home"}]},
            "không có hành động": {"name": "A", "actions": []},
            "chỉ có bước chờ": {"name": "B", "actions": [{"delay": 5}]},
            "thiết bị không tồn tại": {"name": "C", "actions": [{"device": "garage/door", "set": {"on": True}}]},
            "độ sáng vượt giới hạn": {"name": "D", "actions": [{"device": "living/light", "set": {"brightness": 500}}]},
            "khóa lệnh lạ": {"name": "E", "actions": [{"device": "living/light", "set": {"action": "crash"}}]},
            "ghi đè from": {"name": "F", "actions": [{"device": "living/light", "set": {"on": True, "from": "x"}}]},
            "loại không điều khiển được": {"name": "G", "actions": [{"type": "climate", "set": {"on": True}}]},
            "sai kiểu dữ liệu": {"name": "H", "actions": [{"device": "living/light", "set": {"on": "yes"}}]},
            "chế độ sai": {"name": "I", "actions": [{"mode": "bay-bong"}]},
            "mức thông báo sai": {"name": "J", "actions": [{"notify": "hi", "level": "fatal"}]},
            "hành động lạ": {"name": "K", "actions": [{"scene": "home"}]},
            "quá nhiều hành động": {"name": "L", "actions": [{"mode": "home"}] * 31},
            "không phải đối tượng": "xin chào",
        }
        for label, data in bad.items():
            svc, pub = self.build()
            n = len(svc.scenes)
            self.add(svc, data)
            self.assertEqual(len(svc.scenes), n, label)
            self.assertEqual(pub.notifies[-1][0], "warn", label)
            self.assertFalse(os.path.exists(self.custom), f"{label}: không được ghi file")

    def test_hai_ten_cung_slug_van_co_id_khac_nhau(self):
        svc, _ = self.build()
        self.add(svc, {"name": "Đèn!", "actions": [{"mode": "home"}]})
        self.add(svc, {"name": "den", "actions": [{"mode": "away"}]})
        ids = [s["id"] for s in svc.scenes if s.get("custom")]
        self.assertEqual(ids, ["custom-den", "custom-den-2"])

    def test_khong_ghi_duoc_file_thi_khong_them(self):
        svc, pub = self.build()
        svc.custom_scenes_path = os.path.join(self.tmp, "khong-co-thu-muc", "scenes.custom.json")
        n = len(svc.scenes)
        self.add(svc, self.GOOD)
        self.assertEqual(len(svc.scenes), n)
        self.assertEqual(pub.notifies[-1][0], "warn")


if __name__ == "__main__":
    unittest.main()
