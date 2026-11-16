"""Kiểm thử đăng ký 3 bước với OTP giả lập — repository được giả lập, không cần database."""
import contextlib
import io
import unittest
from unittest.mock import patch

from backend.services import registration_service as reg
from backend.services.registration_service import RegistrationError, TooSoon


class RegistrationTest(unittest.TestCase):
    def setUp(self):
        reg._otps.clear()
        reg._tokens.clear()
        for name in ("users", "house_repository"):
            p = patch.object(reg, name)
            setattr(self, name, p.start())
            self.addCleanup(p.stop)
        self.users.phone_taken.return_value = False
        self.users.email_taken.return_value = False
        self.users.create_user.return_value = 9
        self.users.get_user.return_value = {"email": "moi@gmail.com", "full_name": "Nguyễn Văn A", "phone": "0901234567",
                                            "house_address": "12 Lê Lợi"}
        self.house_repository.normalize.side_effect = lambda a: " ".join(str(a or "").split())
        self.house_repository.get_or_create.return_value = 3

    def otp(self, phone="0901234567", name="Nguyễn Văn A"):
        with contextlib.redirect_stdout(io.StringIO()):
            return reg.request_otp(phone, name)["mock_sms"]

    def test_full_flow(self):
        code = self.otp()
        ticket = reg.verify_otp("0901234567", code)
        with contextlib.redirect_stdout(io.StringIO()):
            user = reg.register(ticket["token"], "Moi@Gmail.com", "12  Lê Lợi", "abc123")
        self.assertEqual(user["email"], "moi@gmail.com")
        args = self.users.create_user.call_args.args
        self.assertEqual(args[0], "moi@gmail.com")
        self.assertEqual(args[1], reg.sha256_hex("abc123"))            # mật khẩu băm SHA-256
        self.assertEqual(args[2:], ("Nguyễn Văn A", "user", True, "0901234567", 3))
        with self.assertRaises(RegistrationError):                     # phiếu đăng ký chỉ dùng một lần
            reg.register(ticket["token"], "khac@gmail.com", "12 Lê Lợi", "abc123")

    def test_wrong_otp_and_lockout(self):
        code = self.otp()
        wrong = "000000" if code != "000000" else "111111"
        for _ in range(reg.MAX_ATTEMPTS - 1):
            with self.assertRaises(RegistrationError):
                reg.verify_otp("0901234567", wrong)
        with self.assertRaisesRegex(RegistrationError, "hủy"):
            reg.verify_otp("0901234567", wrong)
        with self.assertRaises(RegistrationError):                     # mã cũ đã bị hủy, đúng cũng không dùng được
            reg.verify_otp("0901234567", code)

    def test_resend_too_soon_and_bad_input(self):
        self.otp()
        with self.assertRaises(TooSoon):
            self.otp()
        for phone, name in (("12345", "Tên"), ("0901234567", "A")):
            with self.subTest(phone=phone, name=name), self.assertRaises(RegistrationError):
                reg.request_otp(phone, name)
        self.users.phone_taken.return_value = True
        with self.assertRaisesRegex(RegistrationError, "đã được đăng ký"):
            reg.request_otp("0911111111", "Nguyễn B")

    def test_expired_otp(self):
        code = self.otp()
        reg._otps["0901234567"]["expires"] = 0
        with self.assertRaisesRegex(RegistrationError, "hết hạn"):
            reg.verify_otp("0901234567", code)


if __name__ == "__main__":
    unittest.main()
