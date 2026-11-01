"""Đường dẫn dùng chung — tính từ vị trí file, không phụ thuộc thư mục đang đứng khi chạy lệnh."""
import os

BE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT_DIR = os.path.dirname(BE_DIR)
CONFIG_DIR = os.path.join(BE_DIR, "config")      # rules.json, scenes.json
DATA_DIR = os.path.join(BE_DIR, "data")          # smarthome.db và file dữ liệu sinh ra khi chạy
BROKER_DIR = os.path.join(BE_DIR, "broker")      # cấu hình Mosquitto, ACL, passwd

DEFAULT_DB = os.path.join(DATA_DIR, "smarthome.db")
DEMO_DB = os.path.join(DATA_DIR, "demo_history.db")
