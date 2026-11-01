"""Các kênh gửi cảnh báo ra bên ngoài: Telegram Bot và Email (SMTP).

Cấu hình đọc từ biến môi trường (không ghi bí mật vào code):
  Telegram : TELEGRAM_TOKEN, TELEGRAM_CHAT            (TELEGRAM_API chỉ để trỏ vào server giả khi test)
  Email    : SMTP_USER, SMTP_PASS, MAIL_TO            (SMTP_HOST, SMTP_PORT, SMTP_MODE = ssl|starttls|plain)
"""
import os
import smtplib
import ssl
import time
import urllib.parse
import urllib.request
from email.message import EmailMessage

LEVEL_ICON = {"critical": "🚨", "warning": "⚠️", "info": "ℹ️"}


class Telegram:
    name = "telegram"

    def __init__(self):
        self.token = os.getenv("TELEGRAM_TOKEN")
        self.chat = os.getenv("TELEGRAM_CHAT")
        self.api = os.getenv("TELEGRAM_API", "https://api.telegram.org")

    @property
    def enabled(self):
        return bool(self.token and self.chat)

    def send(self, ev):
        icon = LEVEL_ICON.get(ev.get("level"), "")
        body = urllib.parse.urlencode({
            "chat_id": self.chat,
            "text": f"{icon} {ev.get('text', '')}\n— {time.strftime('%H:%M:%S %d/%m/%Y')}",
        }).encode()
        req = urllib.request.Request(f"{self.api}/bot{self.token}/sendMessage", data=body)
        with urllib.request.urlopen(req, timeout=10) as r:
            r.read()


class Email:
    name = "email"

    def __init__(self):
        self.user = os.getenv("SMTP_USER")
        self.password = os.getenv("SMTP_PASS")
        self.to = [a.strip() for a in os.getenv("MAIL_TO", "").split(",") if a.strip()]
        self.host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.mode = os.getenv("SMTP_MODE", "ssl").lower()          # ssl | starttls | plain
        self.port = int(os.getenv("SMTP_PORT", {"ssl": 465, "starttls": 587, "plain": 25}[self.mode]))

    @property
    def enabled(self):
        return bool(self.user and self.password and self.to)

    def send(self, ev):
        msg = EmailMessage()
        icon = LEVEL_ICON.get(ev.get("level"), "")
        msg["Subject"] = f"[Nhà thông minh] {icon} {ev.get('text', '')[:80]}"
        msg["From"], msg["To"] = self.user, ", ".join(self.to)
        msg.set_content(
            f"{ev.get('text', '')}\n\n"
            f"Mức độ : {ev.get('level', '?')}\n"
            f"Nguồn  : {ev.get('source', '?')}\n"
            f"Lúc    : {time.strftime('%H:%M:%S %d/%m/%Y')}\n"
        )
        if self.mode == "ssl":
            s = smtplib.SMTP_SSL(self.host, self.port, context=ssl.create_default_context(), timeout=15)
        else:
            s = smtplib.SMTP(self.host, self.port, timeout=15)
            if self.mode == "starttls":
                s.starttls(context=ssl.create_default_context())
        with s:
            if self.mode != "plain":
                s.login(self.user, self.password)
            s.send_message(msg)


def enabled_channels():
    return [c for c in (Telegram(), Email()) if c.enabled]
