#!/usr/bin/env python3
"""
Server giả để thử notifier mà không cần tài khoản thật:
  * Telegram giả  http://127.0.0.1:8099   (đặt TELEGRAM_API=http://127.0.0.1:8099)
  * SMTP giả      127.0.0.1:8025          (đặt SMTP_HOST=127.0.0.1 SMTP_PORT=8025 SMTP_MODE=plain)
Mọi tin nhận được được in ra màn hình.

    python backend/simulator/fake_notify_servers.py

Dùng smtpd/asyncore (Python ≤ 3.11). Cảnh báo "deprecated" khi chạy là bình thường.
"""
import asyncore
import smtpd
import threading
import urllib.parse
import warnings
from http.server import BaseHTTPRequestHandler, HTTPServer

warnings.simplefilter("ignore")


class TelegramHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"])).decode()
        print("TELEGRAM", self.path, urllib.parse.parse_qs(body), flush=True)
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"{}")

    def log_message(self, *a):
        pass


class FakeSMTP(smtpd.SMTPServer):
    def process_message(self, peer, mailfrom, rcpttos, data, **kw):
        print("MAIL", mailfrom, rcpttos, data.decode(errors="replace")[:300].replace("\n", " | "), flush=True)


def main():
    threading.Thread(target=HTTPServer(("127.0.0.1", 8099), TelegramHandler).serve_forever, daemon=True).start()
    FakeSMTP(("127.0.0.1", 8025), None, decode_data=False)
    print("Telegram giả :8099, SMTP giả :8025 — đang chờ. Ctrl+C để tắt.", flush=True)
    asyncore.loop()


if __name__ == "__main__":
    main()
