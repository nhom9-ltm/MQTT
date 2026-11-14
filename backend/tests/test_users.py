"""Kiểm thử quản lý tài khoản (user_service) — repository được giả lập, không cần database."""
import unittest
from unittest.mock import patch

from backend.services import user_service
from backend.services.user_service import UserError

ME = {"id": 1, "email": "admin@gmail.com", "role": "admin"}


def account(id=2, role="user", active=True):
    return {"id": id, "email": f"u{id}@gmail.com", "full_name": "Tên", "role": role, "role_name": role,
            "is_active": active, "phone": None, "house_id": None if role == "admin" else 1}


def body(**kw):
    data = {"email": "moi@gmail.com", "full_name": "Người mới", "role": "user", "password": "abc123", "house_id": 1}
    data.update(kw)
    return data


class UserServiceTest(unittest.TestCase):
    def setUp(self):
        p = patch.object(user_service, "repo")
        self.repo = p.start()
        self.addCleanup(p.stop)
        self.repo.email_taken.return_value = False
        self.repo.deleted_id_by_email.return_value = None
        self.repo.phone_taken.return_value = False
        h = patch.object(user_service, "house_repository")
        self.houses = h.start()
        self.addCleanup(h.stop)
        self.houses.ids.return_value = {1}
        self.houses.normalize.side_effect = lambda a: " ".join(str(a or "").split())
        self.repo.count_active_admins.return_value = 1

    def test_create_hashes_password(self):
        self.repo.create_user.return_value = 5
        user_service.create(body(email="  Moi@Gmail.com "))
        email, pw_hash, *_ = self.repo.create_user.call_args.args
        self.assertEqual(email, "moi@gmail.com")
        self.assertEqual(pw_hash, user_service.sha256_hex("abc123"))

    def test_create_rejects_bad_input(self):
        for data in (body(email="a@yahoo.com"), body(full_name=""), body(role="guest"),
                     body(password=""), body(password="123")):
            with self.subTest(data=data), self.assertRaises(UserError):
                user_service.create(data)
        self.repo.email_taken.return_value = True
        with self.assertRaises(UserError):
            user_service.create(body())

    def test_update_keeps_password_when_blank(self):
        self.repo.get_user.return_value = account()
        user_service.update(2, body(password=""), ME)
        self.assertIsNone(self.repo.update_user.call_args.args[5])     # password_hash

    def test_cannot_demote_or_lock_self(self):
        self.repo.get_user.return_value = account(id=1, role="admin")
        for data in (body(role="user"), body(role="admin", is_active=False)):
            with self.subTest(data=data), self.assertRaises(UserError):
                user_service.update(1, data, ME)

    def test_keeps_at_least_one_admin(self):
        self.repo.get_user.return_value = account(id=3, role="admin")
        self.repo.count_active_admins.return_value = 0
        with self.assertRaises(UserError):
            user_service.update(3, body(role="user"), ME)
        with self.assertRaises(UserError):
            user_service.delete(3, ME)

    def test_cannot_delete_self(self):
        self.repo.get_user.return_value = account(id=1, role="admin")
        with self.assertRaises(UserError):
            user_service.delete(1, ME)
        self.repo.soft_delete_user.assert_not_called()

    def test_lock_toggle(self):
        self.repo.get_user.return_value = account(id=2)
        user_service.set_active(2, False, ME)
        self.assertIs(self.repo.update_user.call_args.args[4], False)
        self.repo.get_user.return_value = account(id=1, role="admin")
        with self.assertRaises(UserError):
            user_service.set_active(1, False, ME)              # không tự khóa mình
        self.repo.get_user.return_value = account(id=3, role="admin")
        self.repo.count_active_admins.return_value = 0
        with self.assertRaises(UserError):
            user_service.set_active(3, False, ME)              # admin cuối cùng

    def test_user_needs_house_admin_does_not(self):
        self.repo.create_user.return_value = 5
        with self.assertRaises(UserError):
            user_service.create(body(house_id=None))                       # user thiếu địa chỉ
        user_service.create(body(role="admin", house_id=None))             # admin không cần địa chỉ
        self.assertIsNone(self.repo.create_user.call_args.args[-1])
        with self.assertRaises(UserError):
            user_service.create(body(phone="12345"))                       # SĐT sai định dạng

    def test_delete_other_user(self):
        self.repo.get_user.return_value = account(id=2)
        user_service.delete(2, ME)
        self.repo.soft_delete_user.assert_called_once_with(2)


if __name__ == "__main__":
    unittest.main()
