"""Kiểm thử kiểm tra luật (rule_validation) và việc automation tự nạp lại rules.json — không cần broker, DB."""
import json
import os
import tempfile
import time
import unittest

from backend.services.automation_service import AutomationService
from backend.services.rule_validation import RuleError, validate_rule

DEVICES = {"living/light", "living/climate", "entrance/lock"}
TYPES = {"light", "climate", "lock"}
SCENES = {"home", "away"}


def check(rule):
    return validate_rule(rule, devices=DEVICES, types=TYPES, scenes=SCENES)


def base_rule(**kw):
    rule = {
        "id": "hot_room", "name": "Nóng → bật đèn",
        "trigger": {"device": "living/climate", "field": "temperature", "op": ">", "value": 30},
        "actions": [{"device": "living/light", "set": {"on": True}}],
    }
    rule.update(kw)
    return rule


class RuleValidationTest(unittest.TestCase):
    def test_valid_rule_is_normalized(self):
        r = check(base_rule(extra="bỏ đi", cooldown=60, conditions=[{"mode": "home"}]))
        self.assertNotIn("extra", r)
        self.assertEqual(r["conditions"], [{"mode": ["home"]}])
        self.assertEqual(r["cooldown"], 60)
        self.assertTrue(r["enabled"])

    def test_time_trigger(self):
        r = check(base_rule(trigger={"at": "23:00"}))
        self.assertEqual(r["trigger"], {"at": "23:00"})

    def test_rejects_bad_values(self):
        cases = [
            base_rule(id="Có Dấu"),
            base_rule(name=""),
            base_rule(trigger={"device": "kitchen/unknown", "field": "on", "op": "==", "value": True}),
            base_rule(trigger={"device": "living/climate", "field": "t", "op": "=~", "value": 1}),
            base_rule(trigger={"at": "25:00"}),
            base_rule(actions=[]),
            base_rule(actions=[{"device": "living/light"}]),
            base_rule(actions=[{"notify": "x", "level": "loud"}]),
            base_rule(actions=[{"scene": "khong-co"}]),
            base_rule(actions=[{"type": "robot", "set": {"on": True}}]),
            base_rule(conditions=[{"mode": "party"}]),
            base_rule(cooldown=-5),
        ]
        for rule in cases:
            with self.subTest(rule=rule), self.assertRaises(RuleError):
                check(rule)


class RuleReloadTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.rules = os.path.join(self.dir, "rules.json")
        self.scenes = os.path.join(self.dir, "scenes.json")
        with open(self.scenes, "w", encoding="utf-8") as f:
            json.dump([], f)
        self.write([check(base_rule())])
        self.svc = AutomationService("home", self.rules, self.scenes, publish=lambda *a, **k: None)

    def write(self, rules):
        with open(self.rules, "w", encoding="utf-8") as f:
            json.dump(rules, f)

    def bump(self):
        t = time.time() + 5
        os.utime(self.rules, (t, t))

    def test_reloads_when_file_changes(self):
        self.write([check(base_rule()), check(base_rule(id="second", name="Luật 2"))])
        self.bump()
        self.svc.tick()
        self.assertEqual([r["id"] for r in self.svc.rules], ["hot_room", "second"])
        self.assertIn("second", self.svc.rt)

    def test_keeps_old_rules_when_file_broken(self):
        with open(self.rules, "w", encoding="utf-8") as f:
            f.write("{ hỏng")
        self.bump()
        self.svc.tick()
        self.assertEqual([r["id"] for r in self.svc.rules], ["hot_room"])


if __name__ == "__main__":
    unittest.main()
