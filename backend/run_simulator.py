#!/usr/bin/env python3
"""Điểm vào: python backend/run_simulator.py  (xem backend/controllers/simulator_controller.py)"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.controllers.simulator_controller import main  # noqa: E402

if __name__ == "__main__":
    main()
