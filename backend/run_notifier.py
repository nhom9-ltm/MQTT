#!/usr/bin/env python3
"""Điểm vào: python backend/run_notifier.py  (xem backend/controllers/notifier_controller.py)"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.controllers.notifier_controller import main  # noqa: E402

if __name__ == "__main__":
    main()
