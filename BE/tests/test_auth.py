"""
Kiểm thử logic đăng nhập, không cần database (repository được giả lập).

Chạy từ thư mục gốc repo:  python -m unittest BE.tests.test_auth -v
"""
import hashlib
import unittest
from unittest.mock import patch

from BE.service import auth_service
from BE.service.auth_service import INVALID_CREDENTIALS, InvalidCredentials


def account(password="User@1", role="user", is_active=True):
    return {"id": 2, "email": "user1@gmail.com", "full_name": "Người dùng 1", "role": role, "is_active": is_active,
            "password_hash": hashlib.sha256(password.encode()).hexdigest()}


@patch("BE.service.auth_service.auth_repository")
class LoginTests(unittest.TestCase):
    def assert_rejected(self, email, password):
        with self.assertRaises(InvalidCredentials) as ctx:
            auth_service.login(email, password, "127.0.0.1")
        self.assertEqual(str(ctx.exception), INVALID_CREDENTIALS)

    def test_correct_credentials_create_session(self, repo):
        repo.find_user_by_email.return_value = account()
        result = auth_service.login("user1@gmail.com", "User@1", "127.0.0.1")
        self.assertEqual(result["user"]["role"], "user")
        self.assertNotIn("password_hash", result["user"])
        repo.record_login.assert_called_once_with("user1@gmail.com", 2, True, "127.0.0.1")
        stored_hash = repo.create_session.call_args.args[1]
        self.assertEqual(stored_hash, hashlib.sha256(result["token"].encode()).hexdigest())

    def test_email_is_normalized(self, repo):
        repo.find_user_by_email.return_value = account()
        auth_service.login("  User1@Gmail.com ", "User@1", None)
        repo.find_user_by_email.assert_called_once_with("user1@gmail.com")

    def test_non_gmail_is_rejected_without_query(self, repo):
        for email in ("user1@yahoo.com", "user1@gmail.com.vn", "user1@gmailxcom", "@gmail.com", "user1", "",
                      "a b@gmail.com", "x@evil.com@gmail.com"):
            with self.subTest(email=email):
                self.assert_rejected(email, "User@1")
        repo.find_user_by_email.assert_not_called()

    def test_wrong_password(self, repo):
        repo.find_user_by_email.return_value = account()
        self.assert_rejected("user1@gmail.com", "sai-mat-khau")
        repo.record_login.assert_called_once_with("user1@gmail.com", 2, False, "127.0.0.1")
        repo.create_session.assert_not_called()

    def test_empty_password(self, repo):
        repo.find_user_by_email.return_value = account()
        self.assert_rejected("user1@gmail.com", "")

    def test_unknown_account(self, repo):
        repo.find_user_by_email.return_value = None
        self.assert_rejected("khongco@gmail.com", "User@1")
        repo.record_login.assert_called_once_with("khongco@gmail.com", None, False, "127.0.0.1")

    def test_inactive_account(self, repo):
        repo.find_user_by_email.return_value = account(is_active=False)
        self.assert_rejected("user1@gmail.com", "User@1")
        repo.create_session.assert_not_called()

    def test_token_lookup_uses_hash(self, repo):
        repo.find_session_user.return_value = account(role="admin")
        user = auth_service.user_from_token("abc")
        repo.find_session_user.assert_called_once_with(hashlib.sha256(b"abc").hexdigest())
        self.assertEqual(user["role"], "admin")

    def test_unknown_token(self, repo):
        repo.find_session_user.return_value = None
        self.assertIsNone(auth_service.user_from_token("abc"))


if __name__ == "__main__":
    unittest.main()
