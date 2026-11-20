"""
Kiểm thử hệ thống an ninh (SecurityService) và cách automation engine dùng nó — không cần broker.

    python -m unittest backend.tests.test_security -v        # chạy từ thư mục gốc repo

Đồng hồ giả (FakeClock) giúp kiểm tra exit/entry delay, thời gian báo động... mà không phải chờ thật.
"""
import contextlib
import io
import json
import os
import shutil
import tempfile
import time
import unittest
from datetime import datetime

from backend.common.paths import CONFIG_DIR
from backend.services import security_service as sec
from backend.services.automation_service import AutomationService
from backend.tests.test_scenes import FakePublish

PIN = sec.hash_pin("2468")
SENSORS = [
    {"device": "entrance/door", "field": "open", "value": True, "zone": "entry", "name": "Cửa chính"},
    {"device": "living/motion", "field": "motion", "value": True, "zone": "interior", "name": "Phòng khách"},
    {"device": "entrance/motion", "field": "motion", "value": True, "zone": "perimeter", "name": "Trước cửa"},
]


class FakeClock:
    def __init__(self, t=None):
        self.t = t if t is not None else datetime(2026, 11, 17, 10, 0).timestamp()

    def __call__(self):
        return self.t

    def advance(self, s):
        self.t += s


class Recorder:
    def __init__(self):
        self.states, self.notes, self.actions, self.sends = [], [], [], []

    def levels(self):
        return [lvl for lvl, _ in self.notes]


def make(**cfg):
    clock, rec = FakeClock(), Recorder()
    base = {"pin": PIN, "exit_delay": 20, "entry_delay": 15, "alarm_duration": 300, "repeat_notify": 60,
            "max_attempts": 3, "lockout": 30, "sensors": SENSORS,
            "on_trigger": [{"type": "light", "set": {"on": True}}], "presence": {"enabled": False}}
    base.update(cfg)
    s = sec.SecurityService(base, clock=clock,
                            publish_state=rec.states.append,
                            notify=lambda lvl, text, src: rec.notes.append((lvl, text)),
                            run_actions=lambda actions, src: rec.actions.append(actions),
                            send=lambda key, payload, src: rec.sends.append((key, payload)))
    return s, clock, rec


def armed_away():
    s, clock, rec = make()
    s.on_state("entrance/door", {"open": False})
    s.on_state("living/motion", {"motion": False})
    s.on_mode("away", "test")
    clock.advance(20)
    s.tick()
    return s, clock, rec


class PinTest(unittest.TestCase):
    def test_hash_roundtrip(self):
        self.assertTrue(sec.check_pin("2468", PIN))
        self.assertFalse(sec.check_pin("2469", PIN))
        self.assertFalse(sec.check_pin(None, PIN))
        self.assertNotEqual(sec.hash_pin("2468")["salt"], PIN["salt"])       # mỗi lần băm một salt mới

    def test_save_pin_keeps_other_settings(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        path = os.path.join(tmp, "security.json")
        shutil.copy(os.path.join(CONFIG_DIR, "security.json"), path)
        sec.save_pin(path, "13579")
        cfg = sec.load_config(path)
        self.assertTrue(sec.check_pin("13579", cfg["pin"]))
        self.assertEqual(len(cfg["sensors"]), 4)
        with self.assertRaises(ValueError):
            sec.save_pin(path, "12a4")

    def test_shipped_config_default_pin(self):
        cfg = sec.load_config(os.path.join(CONFIG_DIR, "security.json"))
        self.assertTrue(sec.check_pin("1234", cfg["pin"]))

    def test_rejects_bad_zone(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        path = os.path.join(tmp, "s.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"sensors": [{"device": "a/b", "field": "x", "value": True, "zone": "garden"}]}, f)
        with self.assertRaises(ValueError):
            sec.load_config(path)


class LoggerRedactTest(unittest.TestCase):
    def test_pin_never_stored(self):
        from backend.services.logger_service import redact
        text, data = redact('{"action": "disarm", "pin": "2468", "from": "dashboard"}', {"action": "disarm", "pin": "2468"})
        self.assertNotIn("2468", text)
        self.assertEqual(data["pin"], "***")
        self.assertEqual(redact('{"on": true}', {"on": True}), ('{"on": true}', {"on": True}))


class StateMachineTest(unittest.TestCase):
    def test_exit_delay_then_armed(self):
        s, clock, rec = make()
        s.on_mode("away", "test")
        self.assertEqual(s.state, "arming")
        self.assertEqual(rec.states[-1]["remaining"], 20)
        s.on_state("living/motion", {"motion": True})          # chủ nhà còn đi lại trong exit delay: bỏ qua
        clock.advance(19)
        s.tick()
        self.assertEqual(s.state, "arming")
        clock.advance(1)
        s.tick()
        self.assertEqual(s.state, "armed_away")

    def test_door_gives_entry_delay_then_alarm(self):
        s, clock, rec = armed_away()
        s.on_state("entrance/door", {"open": True})
        self.assertEqual(s.state, "pending")
        self.assertEqual(rec.states[-1]["trigger"]["name"], "Cửa chính")
        s.on_state("living/motion", {"motion": True})           # đi tiếp vào nhà khi đang chờ PIN: vẫn chờ
        self.assertEqual(s.state, "pending")
        clock.advance(15)
        s.tick()
        self.assertEqual(s.state, "triggered")
        self.assertEqual(rec.levels()[-1], "critical")
        self.assertEqual(rec.actions, [[{"type": "light", "set": {"on": True}}]])

    def test_correct_pin_during_entry_delay(self):
        s, clock, rec = armed_away()
        s.on_state("entrance/door", {"open": True})
        self.assertTrue(s.disarm("2468", "test"))
        self.assertEqual(s.state, "disarmed")
        clock.advance(60)
        s.tick()
        self.assertEqual(s.state, "disarmed")
        self.assertEqual(rec.actions, [])

    def test_interior_motion_alarms_immediately_when_away(self):
        s, clock, rec = armed_away()
        s.on_state("living/motion", {"motion": True})
        self.assertEqual(s.state, "triggered")
        self.assertIn("Phòng khách", rec.notes[-1][1])

    def test_night_ignores_interior(self):
        s, clock, rec = make()
        s.on_mode("night", "test")
        self.assertEqual(s.state, "armed_night")
        s.on_state("living/motion", {"motion": True})
        self.assertEqual(s.state, "armed_night")
        s.on_state("entrance/door", {"open": True})
        self.assertEqual(s.state, "pending")

    def test_night_to_home_disarms_without_pin(self):
        s, clock, rec = make()
        s.on_mode("night", "test")
        self.assertTrue(s.mode_allowed("home"))
        s.on_mode("home", "scene:morning")
        self.assertEqual(s.state, "disarmed")

    def test_perimeter_only_warns_and_is_rate_limited(self):
        s, clock, rec = armed_away()
        n = len(rec.notes)
        for _ in range(3):
            s.on_state("entrance/motion", {"motion": True})
            s.on_state("entrance/motion", {"motion": False})
        self.assertEqual(s.state, "armed_away")
        self.assertEqual(rec.levels()[n:], ["warn"])
        clock.advance(61)
        s.on_state("entrance/motion", {"motion": True})
        self.assertEqual(rec.levels()[n:], ["warn", "warn"])

    def test_retained_state_at_startup_is_not_an_event(self):
        s, clock, rec = armed_away()
        s.on_state("entrance/door", {"open": True}, warm=True)
        self.assertEqual(s.state, "armed_away")
        s.on_state("entrance/door", {"open": True})               # vẫn mở: không phải sườn lên
        self.assertEqual(s.state, "armed_away")

    def test_alarm_repeats_then_returns_to_armed(self):
        s, clock, rec = armed_away()
        s.on_state("living/motion", {"motion": True})
        clock.advance(60)
        s.tick()
        self.assertIn("Vẫn đang BÁO ĐỘNG", rec.notes[-1][1])
        clock.advance(240)
        s.tick()
        self.assertEqual(s.state, "armed_away")

    def test_panic_when_disarmed_returns_to_disarmed(self):
        s, clock, rec = make()
        s.panic("dashboard")
        self.assertEqual(s.state, "triggered")
        self.assertFalse(s.mode_allowed("home"))
        clock.advance(300)
        s.tick()
        self.assertEqual(s.state, "disarmed")

    def test_wrong_pin_lockout(self):
        s, clock, rec = armed_away()
        self.assertFalse(s.disarm("0000", "x"))
        self.assertFalse(s.disarm("0000", "x"))
        self.assertFalse(s.disarm("0000", "x"))
        self.assertEqual(rec.levels()[-1], "critical")
        self.assertIsNotNone(rec.states[-1]["locked_until"])
        self.assertFalse(s.disarm("2468", "x"))                    # đúng PIN nhưng đang bị khóa
        self.assertEqual(s.state, "armed_away")
        clock.advance(30)
        s.tick()
        self.assertTrue(s.disarm("2468", "x"))

    def test_sensor_offline_while_armed(self):
        s, clock, rec = armed_away()
        s.on_status("entrance/door", False)
        self.assertEqual(rec.notes[-1][0], "critical")
        s2, _, rec2 = make()
        s2.on_status("entrance/door", False)
        self.assertEqual(rec2.notes, [])

    def test_restore_after_restart(self):
        s, clock, rec = make()
        s.on_mode("away", "test")
        snap = rec.states[-1]
        s2, clock2, _ = make()
        clock2.t = clock.t + 5
        s2.restore(snap)
        self.assertEqual(s2.state, "arming")
        clock2.advance(15)
        s2.tick()
        self.assertEqual(s2.state, "armed_away")

    def test_presence_simulation(self):
        s, clock, rec = make(presence={"enabled": True, "after": "18:00", "before": "23:00",
                                       "lights": ["living/light"], "min_s": 10, "max_s": 10})
        clock.t = datetime(2026, 11, 17, 18, 30).timestamp()
        s.on_mode("away", "test")
        clock.advance(20)
        s.tick()                                                   # armed_away + trong khung giờ -> bật đèn
        self.assertEqual(rec.sends, [("living/light", {"on": True})])
        clock.advance(10)
        s.tick()
        self.assertEqual(rec.sends[-1], ("living/light", {"on": False}))
        clock.advance(10)
        s.tick()
        clock.t = datetime(2026, 11, 17, 23, 1).timestamp()          # hết khung giờ: tắt đèn đã bật giả
        s.tick()
        self.assertEqual(rec.sends[-1], ("living/light", {"on": False}))
        n = len(rec.sends)
        clock.advance(100)
        s.tick()
        self.assertEqual(len(rec.sends), n)


class EngineIntegrationTest(unittest.TestCase):
    """AutomationService + SecurityService: chặn đổi chế độ / kịch bản khi đang canh gác, tắt bằng PIN."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        p = lambda name: os.path.join(self.tmp, name)
        with open(p("rules.json"), "w", encoding="utf-8") as f:
            json.dump([], f)
        with open(p("scenes.json"), "w", encoding="utf-8") as f:
            json.dump([
                {"id": "home", "name": "Về nhà", "for_mode": "home",
                 "actions": [{"mode": "home"}, {"device": "entrance/lock", "set": {"locked": False}}]},
                {"id": "away", "name": "Ra khỏi nhà", "for_mode": "away", "actions": [{"mode": "away"}]},
                {"id": "movie", "name": "Xem phim", "actions": [{"device": "living/light", "set": {"on": True}}]},
            ], f)
        with open(p("security.json"), "w", encoding="utf-8") as f:
            json.dump({"pin": PIN, "exit_delay": 0, "sensors": SENSORS, "on_trigger": []}, f)
        self.pub = FakePublish()
        self.pub.security = []
        orig = self.pub.__call__

        def publish(topic, payload, qos=0, retain=False):
            if topic.endswith("/security/state"):
                self.pub.security.append(json.loads(payload)["state"])
            return orig(topic, payload, qos, retain)

        self.svc = AutomationService("home", p("rules.json"), p("scenes.json"), publish,
                                     custom_scenes_path=p("custom.json"), security_path=p("security.json"))
        self.svc.warm_until = 0
        self.svc.mode = "home"
        for room, dev, typ in (("entrance", "lock", "lock"), ("entrance", "door", "door"),
                               ("living", "light", "light"), ("living", "motion", "motion")):
            self.svc.handle_message(room, dev, "status", {"state": "online", "type": typ})
        self.out = contextlib.redirect_stdout(io.StringIO())
        self.out.__enter__()
        self.addCleanup(self.out.__exit__, None, None, None)

    def ctl(self, what, data):
        self.svc.handle_message("_auto", what, "set", {**data, "from": "dashboard"})
        time.sleep(0.2)                         # kịch bản chạy trên thread riêng

    def test_full_away_and_back_flow(self):
        self.ctl("mode", {"mode": "away"})
        self.svc.tick()                         # exit_delay = 0
        self.assertEqual(self.svc.security.state, "armed_away")
        self.assertEqual(self.pub.security[-1], "armed_away")

        # chưa nhập PIN: không đổi được chế độ, không chạy được kịch bản có đổi chế độ, cửa KHÔNG được mở khóa
        self.ctl("mode", {"mode": "home"})
        self.ctl("scene", {"scene": "home"})
        self.assertEqual(self.svc.mode, "away")
        self.assertNotIn(("entrance/lock", {"locked": False}), self.pub.sets)
        self.ctl("scene", {"scene": "movie"})   # kịch bản không đổi chế độ thì vẫn chạy được
        self.assertIn(("living/light", {"on": True}), self.pub.sets)

        # sai PIN rồi đúng PIN -> tắt an ninh và tự chạy "Về nhà"
        self.ctl("security", {"action": "disarm", "pin": "0000"})
        self.assertEqual(self.svc.security.state, "armed_away")
        self.ctl("security", {"action": "disarm", "pin": "2468"})
        self.assertEqual(self.svc.security.state, "disarmed")
        self.assertEqual(self.svc.mode, "home")
        self.assertIn(("entrance/lock", {"locked": False}), self.pub.sets)

    def test_door_sensor_through_engine(self):
        self.svc.handle_message("entrance", "door", "state", {"open": False})
        self.ctl("mode", {"mode": "away"})
        self.svc.tick()
        self.svc.handle_message("entrance", "door", "state", {"open": True})
        self.assertEqual(self.svc.security.state, "pending")

    def test_locked_device_is_ignored(self):
        self.svc.handle_message("entrance", "door", "state", {"open": False})
        self.ctl("mode", {"mode": "away"})
        self.svc.tick()
        self.svc.handle_message("_admin", "locked", "state", {"devices": ["entrance/door"]})
        self.svc.handle_message("entrance", "door", "state", {"open": True})
        self.assertEqual(self.svc.security.state, "armed_away")

    def test_panic_button(self):
        self.ctl("security", {"action": "panic"})
        self.assertEqual(self.svc.security.state, "triggered")
        self.assertIn("critical", [lvl for lvl, _ in self.pub.notifies])

    def test_engine_status_describes_security(self):
        self.svc.publish_engine()
        self.assertEqual(len(self.svc.security.describe()["sensors"]), 3)


if __name__ == "__main__":
    unittest.main()
