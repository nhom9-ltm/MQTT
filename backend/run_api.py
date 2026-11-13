#!/usr/bin/env python3
"""Điểm vào: python backend/run_api.py [--port 8000]  (xem backend/controllers/api_controller.py)"""
import argparse
import os
import sys

if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    p = argparse.ArgumentParser(description="API lịch sử nhà thông minh")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8001)
    args = p.parse_args()

    # Nạp dữ liệu demo (tài khoản, thiết bị, luật...) từ backend/database/seed.py trước khi nhận request
    from backend.database import seed
    from backend.repositories.history_repository import DatabaseUnavailable
    try:
        counts = seed.run()
        print("Đã nạp dữ liệu demo: " + ", ".join(f"{v} {k}" for k, v in counts.items()))
    except DatabaseUnavailable as e:
        print(f"Bỏ qua seed: {e}")

    import uvicorn
    from backend.controllers.api_controller import app
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
