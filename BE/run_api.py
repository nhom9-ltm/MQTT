#!/usr/bin/env python3
"""Điểm vào: python BE/run_api.py [--port 8000]  (xem BE/controller/api_controller.py)"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    p = argparse.ArgumentParser(description="API lịch sử nhà thông minh")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    args = p.parse_args()
    import uvicorn
    from BE.controller.api_controller import app
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
