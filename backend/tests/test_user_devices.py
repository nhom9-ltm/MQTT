"""Kiểm thử kết nối thiết bị bằng mã (user_device_service) — repository được giả lập, không cần database."""
import unittest
from unittest.mock import patch

from backend.services import user_device_service as svc
from backend.services.user_device_service import ConnectError

USER = {"id": 7, "email": "u@gmail.com", "role": "user"}


def device(key="living/light", active=True, id=1):
    room, code = key.split("/")
    return {"id": id, "key": key, "code": code, "name": "Đèn", "room": room, "room_name": "Phòng", "type": "light",
            "type_name": "Đèn", "is_active": active, "house_address": "Nhà A"}


class ConnectTest(unittest.TestCase):
    def setUp(self):
        for name in ("devices", "users"):
            p = patch.object(svc, name)
            setattr(self, name, p.start())
            self.addCleanup(p.stop)
        self.users.get_user.return_value = {"house_id": 3}
        self.devices.connect_user.return_value = True

    def test_connect_ok_and_normalizes_code(self):
        self.devices.find_in_house.return_value = [device()]
        d = svc.connect(USER, "  Living/Light ")
        self.devices.find_in_house.assert_called_once_with(3, "living/light")      # chỉ tìm trong nhà của người dùng
        self.devices.connect_user.assert_called_once_with(7, 1)
        self.assertEqual(d["key"], "living/light")

    def test_errors(self):
        cases = [
            ("", [], "Nhập mã"),
            ("khong-co", [], "không đúng"),
            ("light", [device("living/light"), device("bedroom/light", id=2)], "phòng/mã"),
            ("lock", [device("entrance/lock", active=False)], "khóa"),
        ]
        for code, found, msg in cases:
            with self.subTest(code=code):
                self.devices.find_in_house.return_value = found
                with self.assertRaisesRegex(ConnectError, msg):
                    svc.connect(USER, code)

    def test_already_connected(self):
        self.devices.find_in_house.return_value = [device()]
        self.devices.connect_user.return_value = False
        with self.assertRaisesRegex(ConnectError, "từ trước"):
            svc.connect(USER, "living/light")

    def test_user_without_house(self):
        self.users.get_user.return_value = {"house_id": None}
        with self.assertRaisesRegex(ConnectError, "địa chỉ nhà"):
            svc.connect(USER, "light")


if __name__ == "__main__":
    unittest.main()
